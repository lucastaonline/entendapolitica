"""Abas da página do Brasil (js/abas.js + o componente "tabs" do Basecoat em vendor/basecoat; até a ui-r9, Web Awesome): endereço de cada aba (#executivo ... #judiciario,
#os-ministros, #procurar), clique (pushState), Voltar e Avançar do navegador, setas do teclado, barra presa no topo depois de
rolar, "Ver todos" de cada lista (com o foco no primeiro item novo), blocos que abrem, o "Ouvir" lendo só a aba aberta, voltar
de um perfil para a aba e o cartão (também de alguém depois do resumo), nenhum pedido a um servidor novo, textos (inclusive os
internos da biblioteca) em português e em inglês, 320 px sem rolar para os lados, "Quem assume em 2027" como o mandato 2027 do
"Ver outro mandato" (ui-r9, decisão do Lucas: deixou de ser aba; os links antigos #quem-assume levam para lá) e que some com os dados, a
página de um mandato antigo (?mandato=2019: desde a mandatos-r11, as mesmas abas de hoje), axe-core depois de abrir e clicar e nenhum erro de JavaScript.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/) e do axe-core em ../ferramentas.
Uso: python testes/interacao_abas.py"""
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ajuda_abas import pagina_inteira  # site-d-r13

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8775/
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
ABAS = ["executivo", "senado", "camara", "votacoes", "judiciario"]
ROTULOS_PT = ["Quem governa", "Senado", "Câmara", "Como votaram", "STF"]
ROTULOS_EN = ["Who governs", "Senate", "Chamber of Deputies", "How Congress voted", "Supreme Court"]
CDN = ("fontawesome", "jsdelivr", "unpkg", "cdnjs", "webawesome.com", "basecoatui.com", "googleapis", "gstatic")


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(arq):
    return json.loads(urllib.request.urlopen(BASE + arq).read().decode("utf-8"))


def hosts_dos_dados():
    """Os servidores de fora que a página já usava antes das abas: os das fotos que estão nos dados."""
    h = set()

    def anda(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ("foto", "fotoUrl") and isinstance(x, str) and x.startswith("http"):
                    h.add(urlparse(x).hostname)
                else:
                    anda(x)
        elif isinstance(v, list):
            for x in v:
                anda(x)
    for arq in ("dados/executivo.json", "dados/senado.json", "dados/camara.json", "dados/stf.json", "dados/eleitos/BR.json"):
        try:
            anda(dados(arq))
        except Exception:
            pass
    return h


async def ativa(pg):
    return await pg.evaluate("""() => { const t = document.querySelector('.abas-lista [role=tab][aria-selected=true]'); return t ? t.getAttribute('data-aba') : null; }""")


async def visiveis(pg):
    return await pg.evaluate("""() => [...document.querySelectorAll('.abas-grupo > [role=tabpanel]')].filter(p => p.getClientRects().length).map(p => p.getAttribute('data-aba'))""")


async def ir(pg, url, espera=1600):
    await pg.goto("about:blank")
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_function("() => document.readyState === 'complete'", timeout=15000)
    await pg.wait_for_timeout(espera)


async def axe(pg, rotulo):
    await pg.evaluate("document.querySelectorAll('.rev').forEach(e => e.classList.add('visivel'))")
    await pg.wait_for_timeout(900)
    await pg.add_script_tag(path=str(AXE))
    r = await pg.evaluate("""async () => {
      const res = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                            resultTypes: ['violations'] });
      return res.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => (n.target || []).join(' ')).join(' | '));
    }""")
    ok(f"axe-core: 0 problemas ({rotulo})", not r, "; ".join(r)[:300])


async def main():
    mins = dados("dados/manual/ministros.json")["ministerios"]
    n_min = len(mins)
    n_sen = len(dados("dados/senado.json")["membros"])
    n_dep = len(dados("dados/camara.json")["membros"])
    br26 = dados("dados/eleitos/BR.json")
    n_sen27 = len(br26["senado"]["eleitos"]) + len(br26["senado"]["continuam"])
    permitidos = hosts_dos_dados() | {urlparse(BASE).hostname}
    pedidos = []

    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1366, "height": 768})
        ctx.on("request", lambda r: pedidos.append(r.url))
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. sem endereço: a primeira aba; a biblioteca carregou do próprio site; a barra tem as 5 abas, na ordem (ui-r9: "Quem
        # assume em 2027" deixou de ser aba; é o mandato 2027 do "Ver outro mandato")
        await ir(pg, "brasil.html?lang=pt")
        rot = await pg.locator(".abas-lista [role=tab]").evaluate_all("l => l.map(t => t.textContent.trim())")
        ok("5 abas, na ordem de antes, com emoji e texto", [r[r.find(next(c for c in r if c.isalpha())):] for r in rot] == ROTULOS_PT, " | ".join(rot))
        ok("sem endereço, abre a primeira aba (Quem governa) e não muda o endereço", await ativa(pg) == "executivo" and await visiveis(pg) == ["executivo"]
           and "#" not in pg.url, pg.url.split("/")[-1])
        ok("o componente de abas (Basecoat) funciona: div.tabs > [role=tablist] > button[role=tab], só uma aba com aria-selected e tabindex 0",
           # site-d-r14 (4/11): o tablist fica dentro da barra presa (div.abas-barra), com os botões ‹ › nas pontas
           await pg.evaluate("""() => !!window.basecoat && !!document.querySelector('.tabs.abas-grupo > .abas-barra > .abas-lista[role=tablist]')
             && document.querySelectorAll('.abas-lista [role=tab][aria-selected=true]').length === 1
             && document.querySelector('.abas-lista [role=tab][aria-selected=true]').tagName === 'BUTTON'
             && document.querySelectorAll('.abas-lista [role=tab][tabindex="0"]').length === 1"""))
        ok("cada painel tem role=tabpanel e o nome da sua aba (aria-labelledby e aria-controls)", await pg.evaluate("""() => [...document.querySelectorAll('.abas-grupo > [role=tabpanel]')].every(p =>
             p.getAttribute('role') === 'tabpanel' && document.getElementById(p.getAttribute('aria-labelledby')).getAttribute('data-aba') === p.getAttribute('data-aba')
             && document.getElementById(p.getAttribute('aria-labelledby')).getAttribute('aria-controls') === p.id)"""))
        ok("um h1 na página e um h2 em cada aba", await pg.locator("h1").count() == 1 and
           await pg.evaluate("() => [...document.querySelectorAll('.abas-grupo > [role=tabpanel]')].every(p => p.querySelector('section > .cab-bloco h2'))"))
        ok("o menu antigo (nav.atalhos) saiu: as abas fazem o papel dele", await pg.locator("nav.atalhos").count() == 0)
        ok("a busca fica fora das abas, na primeira tela", await pg.evaluate("""() => { const b = document.getElementById('busca'); const r = b.getBoundingClientRect();
             return !b.closest('.abas-grupo') && r.bottom <= innerHeight; }"""))
        ok("cada aba monta o conteúdo só quando abre (Senado e STF ainda não montados)", await pg.evaluate(
            "() => !document.querySelector('#senado .pessoa-card') && !document.querySelector('#stf .stf-card') && !!document.querySelector('#exec-topo .pessoa-grande')"))
        ok("o data-ler continua no conteúdo principal", await pg.locator("main[data-ler]").count() == 1)

        # 2. cada endereço abre a aba certa
        for a in ABAS:
            await ir(pg, f"brasil.html?lang=pt#{a}")
            sec_ok = await pg.evaluate(f"() => {{ const s = document.getElementById('{a}'); return !!s && s.getClientRects().length > 0; }}")
            ok(f"brasil.html#{a} abre a aba {a}", await ativa(pg) == a and await visiveis(pg) == [a] and sec_ok)
        await ir(pg, "brasil.html?lang=pt#os-ministros", 2500)
        pos = await pg.evaluate("""() => { const h = document.getElementById('os-ministros').getBoundingClientRect();
             const barra = document.querySelector('.abas-lista').getBoundingClientRect();
             return [Math.round(h.top), Math.round(barra.bottom)]; }""")
        ok("#os-ministros (de dentro de uma seção) abre a aba Quem governa e rola até ele, logo abaixo da barra",
           await ativa(pg) == "executivo" and pos[1] <= pos[0] < pos[1] + 140, f"título em {pos[0]}px, barra até {pos[1]}px")
        await ir(pg, "brasil.html?lang=pt#procurar")
        ok("#procurar não é aba: fica na primeira aba e põe o foco no campo da busca",
           await ativa(pg) == "executivo" and await pg.evaluate("document.activeElement && document.activeElement.id") == "busca")
        await ir(pg, "brasil.html?lang=pt#nao-existe")
        ok("um endereço que não é de aba abre a primeira", await ativa(pg) == "executivo")

        # 3. clique, Voltar e Avançar
        await ir(pg, "brasil.html?lang=pt")
        h0 = await pg.evaluate("history.length")
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').click()
        await pg.wait_for_timeout(1500)
        ok("clicar numa aba troca a aba e o endereço (com um passo novo no histórico)",
           await ativa(pg) == "senado" and pg.url.endswith("#senado") and await pg.evaluate("history.length") == h0 + 1, pg.url.split("/")[-1])
        # ui-r9: o 🌐 virou um menu de idioma (#menu-idioma); o link "English" acompanha a aba
        bi = await pg.locator('#menu-idioma [data-idioma="en"]').get_attribute("href")
        ok("o menu 🌐 leva para a mesma aba no outro idioma", bi.endswith("lang=en#senado"), bi)
        ok("a aba aberta monta o conteúdo na hora (Senado com o plenário e as pessoas)",
           await pg.locator("#senado .pessoa-card").count() > 0 and await pg.locator("#senado .plenario").count() == 1)
        await pg.wait_for_timeout(1200)
        SIGLAS = """() => { const a = document.querySelector('#senado .plen-area').getBoundingClientRect();
             const s = [...document.querySelectorAll('#senado .rot-p.cabe')];
             return [s.length, s.every(x => { const r = x.getBoundingClientRect(); return r.width > 0 && r.left >= a.left - 2 && r.right <= a.right + 2; })]; }"""
        sig = await pg.evaluate(SIGLAS)
        ok("o plenário montado ao abrir a aba põe as siglas dos partidos no lugar (dentro do desenho)", sig[0] > 0 and sig[1], str(sig))
        await pg.locator('.abas-lista [role=tab][data-aba="judiciario"]').click()
        await pg.wait_for_timeout(1200)
        # a janela muda de tamanho com o Senado escondido: ao voltar para ele, as siglas são postas de novo
        await pg.set_viewport_size({"width": 900, "height": 768})
        await pg.wait_for_timeout(500)
        await pg.go_back()
        await pg.wait_for_timeout(900)
        ok("Voltar do navegador volta para a aba anterior (Senado)", await ativa(pg) == "senado" and pg.url.endswith("#senado"), pg.url.split("/")[-1])
        await pg.wait_for_timeout(600)
        sig = await pg.evaluate(SIGLAS)
        ok("a janela mudou de tamanho com a aba escondida: ao voltar, as siglas continuam dentro do plenário", sig[0] > 0 and sig[1], str(sig))
        await pg.set_viewport_size({"width": 1366, "height": 768})
        await pg.go_back()
        await pg.wait_for_timeout(900)
        ok("Voltar de novo volta para a primeira aba (sem endereço)", await ativa(pg) == "executivo" and "#" not in pg.url, pg.url.split("/")[-1])
        await pg.go_forward()
        await pg.wait_for_timeout(900)
        ok("Avançar vai de novo para o Senado", await ativa(pg) == "senado", pg.url.split("/")[-1])

        # 4. teclado: setas, Home e End (sem encher o histórico)
        await ir(pg, "brasil.html?lang=pt#senado")
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').focus()
        h0 = await pg.evaluate("history.length")
        await pg.keyboard.press("ArrowRight")
        await pg.wait_for_timeout(700)
        foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('data-aba')")
        ok("seta → abre a próxima aba (Câmara) e leva o foco para ela", await ativa(pg) == "camara" and foco == "camara" and pg.url.endswith("#camara"), f"foco={foco}")
        await pg.keyboard.press("End")
        await pg.wait_for_timeout(700)
        ok("End vai para a última aba (STF)", await ativa(pg) == "judiciario")
        await pg.keyboard.press("Home")
        await pg.wait_for_timeout(700)
        ok("Home vai para a primeira aba", await ativa(pg) == "executivo")
        await pg.keyboard.press("ArrowLeft")
        await pg.wait_for_timeout(700)
        ok("seta ← na primeira volta para a última", await ativa(pg) == "judiciario")
        ok("as setas não enchem o histórico (o endereço acompanha a aba)", await pg.evaluate("history.length") == h0 and pg.url.endswith("#judiciario"))
        await pg.keyboard.press("Tab")
        dentro = await pg.evaluate("() => !!document.activeElement.closest('.abas-grupo > [role=tabpanel]:not([hidden])')")
        ok("Tab sai da barra para o conteúdo da aba aberta", dentro, await pg.evaluate("document.activeElement.tagName + '.' + document.activeElement.className"))
        # o link "Pular para o conteúdo" continua funcionando
        await ir(pg, "brasil.html?lang=pt#camara")
        await pg.evaluate("window.scrollTo(0, 0)")
        await pg.locator("a.pular").focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        ok("“Pular para o conteúdo” leva ao conteúdo e não troca de aba", pg.url.endswith("#conteudo") and await ativa(pg) == "camara")

        # 5. barra presa no topo depois de rolar
        await ir(pg, "brasil.html?lang=pt#camara")
        await pg.evaluate("window.scrollTo(0, 2600)")
        await pg.wait_for_timeout(600)
        b = await pg.evaluate("""() => { const t = document.querySelector('header.topo').getBoundingClientRect();
             const n = document.querySelector('.abas-lista').getBoundingClientRect(); return [t.bottom, n.top, n.bottom]; }""")
        ok("rolando a página, a barra das abas fica presa logo abaixo do cabeçalho (sem cobrir o cabeçalho)", abs(b[1] - b[0]) <= 2 and b[2] > b[1], f"cabeçalho até {b[0]:.0f}, barra {b[1]:.0f}–{b[2]:.0f}")
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').click()
        await pg.wait_for_timeout(900)
        y = await pg.evaluate("""() => { const s = document.getElementById('senado').getBoundingClientRect();
             const n = document.querySelector('.abas-lista').getBoundingClientRect(); return [s.top, n.bottom]; }""")
        ok("trocar de aba lá embaixo leva ao começo da aba nova (logo abaixo da barra)", abs(y[0] - y[1]) <= 4, f"seção em {y[0]:.0f}, barra até {y[1]:.0f}")
        await pg.evaluate("window.scrollTo(0, 2400)")
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').click()
        await pg.wait_for_timeout(700)
        y2 = await pg.evaluate("() => document.getElementById('senado').getBoundingClientRect().top")
        ok("clicar na aba que já está aberta leva ao começo dela", abs(y2 - y[1]) <= 4, f"{y2:.0f}")

        # 6. "Ver todos" de cada lista: resumo, quantos são e o foco no primeiro item novo
        await ir(pg, "brasil.html?lang=pt#executivo")
        n0 = await pg.locator("#ministros .min-card").count()
        bt = pg.locator("#executivo .ver-todos-min button")
        # site-d-r14: os ministérios viraram uma grade de ícones, todos à vista (sem o resumo de 8 e o "Ver todos")
        ok(f"ministros: os {n_min} ministérios à vista (ícones), sem “Ver todos”", n0 == n_min and await bt.count() == 0, str(n0))
        await pg.locator('#ministros [data-min="8"]').focus()
        ok("ministros: o 9º ícone recebe o foco pelo teclado", await pg.evaluate("document.activeElement.getAttribute('data-min')") == "8")
        for aba, n, txt in (("senado", n_sen, f"Ver todos os {n_sen} senadores"), ("camara", n_dep, f"Ver todos os {n_dep} deputados")):
            await ir(pg, f"brasil.html?lang=pt#{aba}")
            g = pg.locator(f"#{aba} .grade-pessoas .pessoa-card")
            b = pg.locator(f"#{aba} .ver-mais")
            n_part = await pg.locator(f"#{aba} .d-partido").count()  # site-d-r14: as etiquetas dos partidos
            ok(f"{aba}: resumo com 12 pessoas, botão “{txt}” e a lista de TODOS os partidos inteira",
               await g.count() == 12 and txt in await b.inner_text() and n_part == len(dados(f"dados/{aba}.json")["porPartido"]) and
               await pg.locator(f"#{aba} .d-partido[hidden]").count() == 0, f"{await g.count()} | {n_part} partidos")
            cont = await pg.locator(f"#{aba} .contagem").inner_text()
            ok(f"{aba}: a contagem diz que é o começo da lista", f"os 12 primeiros de {n}" in cont, cont)
            await b.click()
            await pg.wait_for_timeout(900)
            foco = await pg.evaluate(f"() => [...document.querySelectorAll('#{aba} .pessoa-card')].indexOf(document.activeElement)")
            ok(f"{aba}: “Ver todos” mostra os {n} e põe o foco na 13ª pessoa", await g.count() == n and foco == 12, f"{await g.count()} | foco no {foco}")
            # filtro: com menos gente, o botão diz quantos foram encontrados
            await pg.locator(f"#{aba} .combo-sel input").last.click()
            await pg.keyboard.type("PL", delay=40)
            await pg.wait_for_timeout(500)
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(700)
            bt2 = await pg.locator(f"#{aba} .ver-mais").inner_text() if await pg.locator(f"#{aba} .ver-mais").count() else ""
            ok(f"{aba}: com um filtro, o resumo volta e o botão diz quantos foram encontrados", "encontrados" in bt2 or await g.count() <= 12, bt2)

        # 6b. "Quem assume" (o mandato 2027 do "Ver outro mandato"): o aviso nas abas de hoje, o endereço antigo, a opção no campo,
        # contagens e cada Casa. mandatos-r11: o mandato 2027 tem as mesmas abas de hoje (o mesmo resumo de 12 e "Ver todos", com o
        # plenário, os partidos e os filtros à vista, como hoje), com a faixa amarela "Você está vendo"
        await ir(pg, "brasil.html?lang=pt#senado")
        av = pg.locator("#senado .aviso-futuro a")
        href = await av.get_attribute("href") if await av.count() else ""
        ok("aba Senado: aviso curto “Veja quem assume em 2027”, com link para o mandato 2027 (na mesma aba)",
           await av.count() == 1 and "Veja quem assume em 2027" in await av.inner_text() and href.endswith("mandato=2027#senado"), href)
        ok("avisos também em Quem governa e na Câmara (e não em Como votaram nem no STF)", await pg.locator("#executivo .aviso-futuro, #camara .aviso-futuro").count() == 2
           and await pg.locator("#votacoes .aviso-futuro, #judiciario .aviso-futuro").count() == 0)
        await pg.locator(".mandato-campo input").click()
        await pg.wait_for_timeout(400)
        ops = await pg.locator(".mandato-campo [role=option]").all_inner_texts()
        ok("“Ver outro mandato” tem “2027 a 2030 (eleitos em 2026)” em primeiro", bool(ops) and ops[0].strip() == "2027 a 2030 (eleitos em 2026)", " | ".join(ops[:3]))
        await pg.locator(".mandato-campo [role=option]").first.click()
        await pg.wait_for_url("**mandato=2027*", timeout=15000)
        await pg.wait_for_timeout(2000)
        ok("escolher 2027 abre o mandato 2027: as mesmas abas, na mesma aba (Senado), com a faixa “próximo mandato”", await pg.locator(".abas-grupo").count() == 1
           and await pg.locator("#faixa-mandato").is_visible() and "próximo mandato" in await pg.locator("#faixa-mandato").inner_text() and await ativa(pg) == "senado")
        await ir(pg, "brasil.html?lang=pt#quem-assume", 2500)
        ok("o endereço antigo brasil.html#quem-assume leva ao mandato 2027 (endereço corrigido), na primeira aba", "mandato=2027" in pg.url and await ativa(pg) == "executivo"
           and await pg.locator(".mandato-campo input").input_value() == "2027 a 2030 (eleitos em 2026)", pg.url.split("/")[-1])
        ok("Quem assume: linha do tempo (num bloco que abre, em cima das abas) e a contagem da aba", await pg.locator(".nota-mandato .posses li").count() >= 3
           and await pg.locator("#executivo .contas-e26 li").count() >= 1)
        await pg.evaluate("EP.abas.mostra('senado')")
        await pg.wait_for_timeout(1200)
        sen = pg.locator("#qa-casa-sen")
        ok(f"Quem assume: Senado com o mesmo resumo de hoje (12 pessoas) e “Ver todos os {n_sen27} senadores”",
           await sen.locator(".pessoa-card").count() == 12 and f"Ver todos os {n_sen27} senadores" in await sen.locator(".ver-mais").inner_text())
        ok("Quem assume: plenário, todos os partidos (nenhum escondido) e os filtros à vista, como hoje", await sen.locator("details.casa-recolhe").count() == 0
           and await sen.locator(".d-partidos").is_visible() and await sen.locator(".d-partido").count() >= 5 and await sen.locator(".d-partido[hidden]").count() == 0
           and await sen.locator(".f-nome").is_visible())
        await sen.locator(".ver-mais").click()
        await pg.wait_for_timeout(800)
        foco = await pg.evaluate("() => [...document.querySelectorAll('#qa-casa-sen .pessoa-card')].indexOf(document.activeElement)")
        ok(f"Quem assume: “Ver todos” mostra os {n_sen27} e põe o foco na 13ª pessoa", await sen.locator(".pessoa-card").count() == n_sen27 and foco == 12, str(foco))
        await axe(pg, "Quem assume, com o bloco aberto e a lista inteira")

        # 6c. STF: cartões compactos e os detalhes longos em blocos que abrem
        await ir(pg, "brasil.html?lang=pt#judiciario", 2000)
        stf = pg.locator("#stf")
        n_stf = len(dados("dados/stf.json")["ministros"])
        ok("STF: um cartão por ministro, à vista", await stf.locator(".stf-grade a.stf-card").count() == n_stf)
        # site-d-r14: as Turmas (em rostos) ficam à vista; os 3 blocos que abrem são os passos, quem preside e o que o STF publica
        ok("STF: 3 blocos que abrem (os passos, quem preside e o que o STF publica), fechados; as Turmas à vista",
           await stf.locator("details").count() == 3 and not await stf.locator(".stf-passos").is_visible() and await stf.locator(".stf-turmas").is_visible())
        for d in await stf.locator("details").all():
            await d.evaluate("d => { d.open = true; }")
        await pg.wait_for_timeout(1200)
        ok("STF: abertos, mostram os 5 passos, as 2 Turmas e os links do STF",
           await stf.locator(".stf-passos li").count() == 5 and await stf.locator(".stf-passos").is_visible() and
           await stf.locator(".stf-turma").count() == 2 and await stf.locator(".stf-turmas").is_visible() and await stf.locator(".stf-trabalho .links-onde a").count() >= 1)
        await pg.locator("details.stf-como-det").evaluate("d => { d.open = false; }")
        await pg.wait_for_timeout(600)
        await pg.locator("details.stf-como-det > summary").focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(900)
        ok("STF: o bloco abre pelo teclado (Enter)", await pg.evaluate("document.querySelector('details.stf-como-det').open"))
        await axe(pg, "STF, com os blocos abertos")

        # 7. "Ouvir" lê só a aba aberta
        await ir(pg, "brasil.html?lang=pt#senado", 2000)
        t = await pg.evaluate("EP.textoParaLer(EP.alvoLeitura())")
        ok("Ouvir (Senado): lê o título e a busca, e nada das outras abas nem os nomes das abas",
           "O Senado Federal" in t and "Procurar qualquer político" in t and "Quem governa o país" not in t and "Supremo Tribunal Federal" not in t
           and "Como votaram" not in t and "Quem assume em 2027" not in t, t[:160])
        await pg.locator('.abas-lista [role=tab][data-aba="judiciario"]').click()
        await pg.wait_for_timeout(1500)
        t = await pg.evaluate("EP.textoParaLer(EP.alvoLeitura())")
        ok("Ouvir (STF): agora lê o STF e não o Senado", "Supremo Tribunal Federal" in t and "O Senado Federal" not in t, t[:120])

        # 8. voltar de um perfil: a aba certa e o foco no cartão (também de alguém depois do resumo)
        await ir(pg, "brasil.html?lang=pt#senado")
        await pg.locator("#senado .ver-mais").click()
        await pg.wait_for_timeout(700)
        card = pg.locator("#senado .pessoa-card").nth(40)
        href = await card.get_attribute("href")
        await card.scroll_into_view_if_needed()
        await card.click()
        await pagina_inteira(pg)  # site-d-r13: o cartão abre a gaveta; o perfil fica no “Ver a página inteira”
        await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        await pg.locator("#voltar-lista").click()
        await pg.wait_for_url("**/brasil.html*", timeout=15000)
        await pg.wait_for_timeout(2500)
        foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('href')")
        vis = await pg.evaluate("(() => { const a = document.activeElement; const r = a.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()")
        ok("Voltar do perfil (41º senador, depois do resumo): aba Senado e o foco no cartão, à vista", await ativa(pg) == "senado" and foco == href and vis, f"foco={foco}")
        # sem a memória do navegador: o perfil volta por um link (a página carrega de novo)
        await ir(pg, "brasil.html?lang=pt#camara")
        await pg.locator("#camara .ver-mais").click()
        await pg.wait_for_timeout(900)
        card = pg.locator("#camara .pessoa-card").nth(200)
        href = await card.get_attribute("href")
        await card.scroll_into_view_if_needed()
        await card.click()
        await pagina_inteira(pg)  # site-d-r13: o cartão abre a gaveta; o perfil fica no “Ver a página inteira”
        await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        await pg.evaluate("location.hash = 'x'")  # um link dentro do perfil: o Voltar passa a ser um link comum
        await pg.wait_for_timeout(300)
        await pg.locator("#voltar-lista").click()
        await pg.wait_for_url("**/brasil.html*camara*", timeout=15000)
        await pg.wait_for_timeout(3500)
        foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('href')")
        ok("Voltar por link (201º deputado): a página abre na aba Câmara, com a lista inteira e o foco no cartão",
           await ativa(pg) == "camara" and foco == href and await pg.locator("#camara .pessoa-card").count() == n_dep, f"foco={foco}")
        # a aba do Senado, aberta por um perfil que voltou para "brasil.html" sem o endereço da aba (ep-volta na memória da aba)
        await pg.evaluate("""(h) => sessionStorage.setItem('ep-volta', JSON.stringify({ pagina: 'brasil.html', secao: 'senado', id: h.split('id=')[1], y: 0, voltando: Date.now() }))""",
                          "pessoa.html?id=" + dados("dados/senado.json")["membros"][0]["id"])
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        ok("voltando para brasil.html sem o endereço da aba, a aba de onde a pessoa saiu abre (e o endereço fica certo)",
           await ativa(pg) == "senado" and pg.url.endswith("#senado"), pg.url.split("/")[-1])

        ok("nenhum erro de JavaScript (computador)", not erros, "; ".join(erros)[:300])

        # 9. nenhum pedido a um servidor novo (a biblioteca e os ícones vêm do próprio site)
        hosts = {urlparse(u).hostname for u in pedidos if u.startswith("http")}
        novos = sorted(h for h in hosts if h not in permitidos)
        ok("nenhum pedido a um servidor novo (só o site e os servidores das fotos, que a página já usava)", not novos, ", ".join(novos))
        ok("nenhum pedido a CDN (Font Awesome, jsDelivr, unpkg, webawesome.com...)", not [u for u in pedidos if any(c in u for c in CDN)])
        ok("a biblioteca vem de vendor/basecoat/ (um .css e um .js) e a Web Awesome não é mais pedida",
           len({u.split("?")[0] for u in pedidos if "/vendor/basecoat/" in u}) == 2 and not [u for u in pedidos if "webawesome" in u])
        await ctx.close()

        # 10. inglês: abas e botões; no celular a barra rola para o lado (sem botões de rolar: a barra rola com o dedo)
        ctx = await nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        for lang, rotulos in (("en", ROTULOS_EN), ("pt", ROTULOS_PT)):
            await ir(pg, f"brasil.html?lang={lang}#senado")
            rot = await pg.locator(".abas-lista [role=tab]").evaluate_all("l => l.map(t => t.textContent.trim())")
            ok(f"({lang}) nomes das abas", [r[r.find(next(c for c in r if c.isalpha())):] for r in rot] == rotulos, " | ".join(rot))
            lab = await pg.evaluate("() => document.querySelector('.abas-lista').getAttribute('aria-label')")
            ok(f"({lang}) o nome da barra das abas (leitor de tela) no idioma da página", lab and (("page" in lab) if lang == "en" else ("página" in lab)), str(lab))
            rola = await pg.evaluate("() => { const l = document.querySelector('.abas-lista'); return [l.scrollWidth > l.clientWidth, getComputedStyle(l).overflowX]; }")
            ok(f"({lang}) no celular, a barra das abas rola para o lado", rola[0] and rola[1] in ("auto", "scroll"), str(rola))
            ver = await pg.locator("#senado .ver-mais").inner_text()
            ok(f"({lang}) botão “Ver todos” no idioma da página", ("See all" in ver) if lang == "en" else ("Ver todos" in ver), ver)
            ativo = await pg.evaluate("""() => { const t = document.querySelector('.abas-lista [role=tab][aria-selected=true]').getBoundingClientRect();
                 const n = document.querySelector('.abas-lista').getBoundingClientRect(); return t.left >= n.left - 1 && t.right <= n.right + 1; }""")
            ok(f"({lang}) no celular, as abas rolam dentro da barra e a aba aberta fica à vista", ativo)
        await ir(pg, "brasil.html?lang=en&mandato=2027#senado", 2500)
        t = await pg.locator("#senado").inner_text()
        ok("(en) Quem assume: o Senado (resumo e “See all”) e a faixa em inglês", "See all" in t and "The Federal Senate" in t
           and "You are viewing" in await pg.locator("#faixa-mandato").inner_text())
        await ir(pg, "brasil.html?lang=en#judiciario", 2000)
        t = await pg.locator("#stf").inner_text()
        # site-d-r14: os blocos que abrem têm outros títulos (o "💡" do D); os ministérios não têm mais "See all"
        ok("(en) STF: blocos que abrem em inglês", "How someone gets to the STF" in t and "Who presides over the court" in t and "The Chambers" in t)
        await ir(pg, "brasil.html?lang=en#executivo")
        ok("(en) ministros: os ícones com o nome da área em inglês", "Health" in await pg.locator("#ministros").inner_text())
        ok("nenhum erro de JavaScript (celular)", not erros, "; ".join(erros)[:300])
        await ctx.close()

        # 11. 320 px: nada de rolar para os lados, em nenhuma aba
        ctx = await nav.new_context(viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        for a in ABAS:
            await ir(pg, f"brasil.html?lang=pt#{a}", 1500)
            larg = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(f"320 px sem rolar para os lados: #{a}", larg <= 0, f"{larg}px")
        await ctx.close()

        # 12. "Quem assume" some com os dados (depois das posses o arquivo deixa de existir): sem opção 2027, sem avisos, e os
        # endereços de 2027 levam para hoje
        ctx = await nav.new_context(viewport={"width": 1366, "height": 768})
        await ctx.route("**/dados/eleitos/BR.json*", lambda r: r.fulfill(status=404, body="não existe"))
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        await ir(pg, "brasil.html?lang=pt", 1500)
        await pg.locator(".mandato-campo input").click()
        await pg.wait_for_timeout(400)
        ops = await pg.locator(".mandato-campo [role=option]").all_inner_texts()
        ok("sem dados/eleitos/BR.json: nada de 2027 no “Ver outro mandato” e nenhum aviso nas abas",
           not any("2027" in o for o in ops) and await pg.locator(".aviso-futuro").count() == 0 and await pg.locator(".abas-lista [role=tab]:visible").count() == 5, " | ".join(ops[:2]))
        await pg.keyboard.press("Escape")
        for u in ("brasil.html?lang=pt#quem-assume", "brasil.html?lang=pt&mandato=2027"):
            await ir(pg, u, 1500)
            ok(f"{u} sem os dados: leva para a página de hoje, na primeira aba", await ativa(pg) == "executivo" and "mandato" not in pg.url and "quem-assume" not in pg.url, pg.url.split("/")[-1])
        await pg.keyboard.press("Tab")
        await pg.locator('.abas-lista [role=tab][data-aba="camara"]').focus()
        await pg.keyboard.press("ArrowRight")
        await pg.wait_for_timeout(600)
        ok("as setas pulam a aba que sumiu", await ativa(pg) == "votacoes")
        ok("nenhum erro de JavaScript (sem a seção)", not erros, "; ".join(erros)[:300])
        await ctx.close()

        # 13. mandato antigo (?mandato=2019): mandatos-r11 (pedido do Lucas, 3/11): as mesmas abas de hoje, com a faixa amarela
        ctx = await nav.new_context(viewport={"width": 1366, "height": 768})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        await pg.goto(BASE + "brasil.html?mandato=2019&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(2000)
        ok("?mandato=2019: as mesmas 5 abas de hoje, na mesma ordem",
           await pg.locator(".abas-grupo").count() == 1 and await pg.evaluate("[...document.querySelectorAll('.abas-lista [role=tab]')].filter(t => !t.hidden).map(t => t.dataset.aba).join()")
           == ",".join(ABAS))
        await pg.evaluate("EP.abas.mostra('senado')")
        await pg.wait_for_timeout(1200)
        ok("?mandato=2019: a faixa “Você está vendo”, o campo de mandatos e as listas (resumo de 12)", await pg.locator("#faixa-mandato").count() == 1 and
           await pg.locator("#senado .pessoa-card").count() == 12 and await pg.locator("#mandato-lugar .mandato-box").count() == 1)
        ok("?mandato=2019: a busca continua à vista (como hoje)", await pg.locator("#procurar").is_visible())
        ok("nenhum erro de JavaScript (mandato antigo)", not erros, "; ".join(erros)[:300])
        await ctx.close()

        # 14. se o js do Basecoat não carregar (arquivo fora do ar), as abas continuam (o js/abas.js cuida do clique e das setas)
        ctx = await nav.new_context(viewport={"width": 1366, "height": 768})
        await ctx.route("**/vendor/basecoat/basecoat.js*", lambda r: r.fulfill(status=404, body="não existe"))
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        ok("sem o js do Basecoat: as abas aparecem do mesmo jeito", await pg.locator(".abas-lista [role=tab]").count() == 5 and await ativa(pg) == "executivo")
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').click()
        await pg.wait_for_timeout(1200)
        ok("sem o js do Basecoat: o clique troca de aba e o Senado monta", await ativa(pg) == "senado" and pg.url.endswith("#senado") and await pg.locator("#senado .pessoa-card").count() > 0)
        await pg.locator('.abas-lista [role=tab][data-aba="senado"]').focus()
        await pg.keyboard.press("ArrowRight")
        await pg.wait_for_timeout(600)
        ok("sem o js do Basecoat: as setas trocam de aba e levam o foco", await ativa(pg) == "camara" and await pg.evaluate("document.activeElement.getAttribute('data-aba')") == "camara")
        ok("nenhum erro de JavaScript (sem o js do Basecoat)", not erros, "; ".join(erros)[:300])
        await nav.close()

    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
