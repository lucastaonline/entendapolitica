"""Testes de interação da frente mandatos-r11 (pedidos do Lucas de 3/11): todo mandato com o MESMO layout (as mesmas abas, na
mesma ordem, os mesmos componentes e títulos; a faixa amarela "Você está vendo" com "Voltar para hoje"; as abas sem dados daquele
período dizendo isso), a barra das abas (sem rolagem, nenhuma aba cortada nem esmaecida; com rolagem, o esmaecimento só no lado
onde há mais abas) e o espaço em branco depois de uma aba curta. Playwright + Edge; precisa do servidor (EP_BASE, padrão
http://127.0.0.1:8770/).
Uso: python testes/interacao_mandatos_layout.py [parte...]   (partes: layout, enderecos, barra, vazio, celular; sem nada = todas)"""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
PARTES = set(sys.argv[1:]) or {"layout", "enderecos", "barra", "vazio", "celular"}


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def url(u, lang="pt"):
    base, _, aba = u.partition("#")
    return base + ("&" if "?" in base else "?") + "lang=" + lang + ("#" + aba if aba else "")


async def ir(pg, u, lang="pt", espera=1300):
    await pg.goto(BASE + url(u, lang), wait_until="networkidle")
    await pg.wait_for_timeout(espera)


async def aba(pg, nome, espera=900):
    await pg.evaluate("n => window.EP && EP.abas && EP.abas.mostra(n)", nome)
    await pg.wait_for_timeout(espera)


# o que a página mostra: as abas, o título de cada seção (sem os números entre parênteses) e os componentes de cada aba
RETRATO = """async () => {
  const abas = [...document.querySelectorAll('.abas-grupo > .abas-barra > [role=tablist] > [role=tab]')].filter(t => !t.hidden);
  const out = { abas: abas.map(t => [t.getAttribute('data-aba'), t.textContent.trim()]), secoes: {} };
  for (const t of abas) {
    const id = t.getAttribute('data-aba');
    EP.abas.mostra(id);
    await new Promise(r => setTimeout(r, 650));
    const p = document.getElementById('painel-' + id), h = p.querySelector('h2');
    const tit = h ? [...h.childNodes].filter(n => !(n.nodeType === 1 && /^(SMALL|SPAN)$/.test(n.tagName) && (n.matches('small, .h1-periodo')))).map(n => n.textContent).join('').trim() : '';
    const conta = s => p.querySelectorAll(s).length;
    out.secoes[id] = { tit, grandes: conta('.exec-topo .pessoa-grande'), plenario: conta('.plen-box'), partidos: conta('.barras-p'), filtros: conta('.filtros-casa'),
      contagem: conta('.contagem'), verTodos: conta('.grade-pessoas .ver-mais'), cartoes: conta('.pessoa-card'), semDados: conta('.sem-dados-mandato'),
      minCards: conta('.min-card'), stf: conta('.stf-passos, .stf-grade'), combo: conta('.combo input[role=combobox]'), texto: p.innerText.length };
  }
  EP.abas.mostra(abas[0].getAttribute('data-aba'));
  const f = document.getElementById('faixa-mandato');
  out.faixa = f ? f.innerText.trim() : '';
  out.faixaHoje = f ? f.querySelector('.fm-hoje').getAttribute('href') : '';
  out.faixaPresa = f ? getComputedStyle(f).position : '';
  out.nota = (document.querySelector('.nota-mandato') || {}).innerText || '';
  out.seletor = (document.querySelector('#mandato-lugar input[role=combobox]') || {}).value || '';
  return out;
}"""


async def retrato(pg):
    return await pg.evaluate(RETRATO)


async def layout(nav):
    ctx = await nav.new_context(viewport={"width": 1366, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    # [nome, página de hoje, mandatos (antigo recente, antigo mais velho, 2027 ou None), o que cada aba tem de ter]
    casos = [
        ("Brasil", "brasil.html", ["2019", "1995", "2027"]),
        ("Bahia", "estado.html?uf=BA", ["2019", "1995", "2027"]),
        ("São Paulo (estado)", "estado.html?uf=SP", ["2015", "1995", "2027"]),
        ("Salvador", "cidade.html?ibge=2927408", ["2021", "1997", None]),
        ("São Paulo (cidade)", "cidade.html?ibge=3550308", ["2017", "1997", None]),
    ]
    for lang in ("pt", "en"):
        for nome, pag, mands in casos:
            if lang == "en" and nome not in ("Brasil", "Bahia", "Salvador"):
                continue
            await ir(pg, pag, lang)
            hoje = await retrato(pg)
            sufixo = f" [{lang}]"
            ok(f"{nome} hoje: abas e nenhuma faixa{sufixo}", len(hoje["abas"]) >= 4 and not hoje["faixa"] and not hoje["nota"], " / ".join(a[1] for a in hoje["abas"]))
            for m in mands:
                if m is None:
                    continue
                sep = "&" if "?" in pag else "?"
                await ir(pg, f"{pag}{sep}mandato={m}", lang)
                r = await retrato(pg)
                ok(f"{nome} {m}: as mesmas abas, na mesma ordem{sufixo}", r["abas"] == hoje["abas"], " / ".join(a[1] for a in r["abas"]))
                tit_iguais = all(r["secoes"][k]["tit"] == hoje["secoes"][k]["tit"] for k, _ in hoje["abas"] if k in r["secoes"])
                ok(f"{nome} {m}: os mesmos títulos em cada aba{sufixo}", tit_iguais,
                   "; ".join(f"{k}: {hoje['secoes'][k]['tit']!r} x {r['secoes'].get(k, {}).get('tit')!r}" for k, _ in hoje["abas"]
                             if r["secoes"].get(k, {}).get("tit") != hoje["secoes"][k]["tit"])[:300])
                # os mesmos componentes: cartões grandes de quem governa, e em cada Casa o plenário, os partidos, os filtros, a contagem
                # e o resumo com "Ver todos"; onde não há dado, o quadro "sem dados" no mesmo lugar
                difs = []
                for k, _ in hoje["abas"]:
                    a, b = hoje["secoes"][k], r["secoes"].get(k, {})
                    if a["plenario"] and not b.get("semDados"):
                        for c in ("plenario", "partidos", "filtros", "contagem"):
                            if a[c] != b.get(c):
                                difs.append(f"{k}.{c}: {a[c]} x {b.get(c)}")
                        if a["verTodos"] and not b.get("verTodos"):
                            difs.append(f"{k}: sem 'Ver todos'")
                    if a["grandes"] and not (b.get("grandes") or b.get("semDados")):
                        difs.append(f"{k}: sem os cartões de quem governa")
                    if a["combo"] and not b.get("combo"):
                        difs.append(f"{k}: sem o campo")
                    if not b.get("texto"):
                        difs.append(f"{k}: aba vazia")
                ok(f"{nome} {m}: os mesmos componentes em cada aba (ou o quadro sem dados){sufixo}", not difs, "; ".join(difs)[:300])
                faixa_ok = ("Você está vendo:" if lang == "pt" else "You are viewing:") in r["faixa"] and ("Voltar para hoje" if lang == "pt" else "Back to today") in r["faixa"]
                periodo = {"2027": "2027"}.get(m, m)
                ok(f"{nome} {m}: faixa “Você está vendo” presa embaixo das abas, com o período e “Voltar para hoje”{sufixo}",
                   faixa_ok and periodo in r["faixa"] and r["faixaPresa"] == "sticky" and "mandato" not in r["faixaHoje"], r["faixa"][:120])
                ok(f"{nome} {m}: o campo “Ver outro mandato” mostra o mandato{sufixo}", r["seletor"].startswith(m), r["seletor"])
                ok(f"{nome} {m}: o aviso de onde vêm os dados, em cima das abas{sufixo}", "TSE" in r["nota"], r["nota"][:100])
                # o que não existe para aquele período diz isso, sem prometer
                if pag == "brasil.html":
                    vot = r["secoes"]["votacoes"]
                    ok(f"Brasil {m}: “Como votaram” diz que o site guarda só as votações de hoje (sem prometer){sufixo}", vot["semDados"] == 1 and vot["cartoes"] == 0)
                    stf = r["secoes"]["judiciario"]
                    ok(f"Brasil {m}: STF com as regras e o aviso de que a composição é a de hoje{sufixo}", stf["stf"] >= 1)
                    if m == "2027":
                        ok(f"Brasil 2027: ministros: o quadro diz que o presidente nomeia depois da posse{sufixo}", r["secoes"]["executivo"]["semDados"] == 1)
                    else:
                        ok(f"Brasil {m}: os ministros no mesmo cartão de hoje (.min-card){sufixo}", r["secoes"]["executivo"]["minCards"] >= 8)
                txt = await pg.locator("main").inner_text()
                proibidas = [p for p in ("ainda não", "em breve", "por enquanto", "not yet", "coming soon") if p in txt.lower()]
                ok(f"{nome} {m}: nenhum texto que promete{sufixo}", not proibidas, str(proibidas))
            # cidade: não há mandato de 2027 (os eleitos de 2026 não são da cidade): o endereço leva para hoje
            if pag.startswith("cidade") and lang == "pt":
                await pg.goto(BASE + url(pag + "&mandato=2027"), wait_until="networkidle")
                await pg.wait_for_timeout(1200)
                ok(f"{nome}: ?mandato=2027 leva para hoje (as cidades não elegeram ninguém em 2026)", "mandato" not in pg.url, pg.url.split("/")[-1])
    # cartões: no passado, sem link (os dados do TSE de mandatos antigos não trazem CPF nem nascimento para ligar ao perfil com
    # segurança); em 2027, quem tem perfil leva ao perfil de hoje e quem não tem, ao perfil e26-
    await ir(pg, "brasil.html?mandato=2019")
    await aba(pg, "senado")
    ok("passado: cartões sem link para perfil", await pg.locator("#senado .grade-pessoas a").count() == 0 and await pg.locator("#senado .pessoa-card.passado").count() >= 12)
    br = json.loads((RAIZ / "dados" / "eleitos" / "BR.json").read_text(encoding="utf-8"))
    await ir(pg, "brasil.html?mandato=2027")
    await aba(pg, "camara")
    await pg.locator("#camara .ver-mais").click()
    await pg.wait_for_timeout(700)
    hrefs = set(await pg.locator("#camara .grade-pessoas a.pessoa-card").evaluate_all("l => l.map(a => a.getAttribute('href'))"))
    esperado = {f"pessoa.html?id={m['link']}" for m in br["camara"]["membros"]}
    e26 = sum(1 for m in br["camara"]["membros"] if m["link"] == m["id"])
    ok("2027: cada cartão leva ao perfil de hoje ou ao perfil e26- (os 513)", hrefs == esperado and e26 > 0, f"{len(hrefs)} links, {e26} e26-")
    # ministros do passado: o mesmo cartão de hoje, e a janela com quem chefiou, as datas e as fontes
    await ir(pg, "brasil.html?mandato=2015")
    n0 = await pg.locator("#min-grade-1 .min-card").count()
    # site-d-r14: os ministérios do passado também viraram ícones, todos à vista (sem o resumo de 8 e o "Ver todos")
    await pg.locator('#min-grade-1 [data-min-hist="1:8"]').focus()
    foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('data-min-hist')")
    ok("ministros do passado: todos os ícones à vista e o foco pelo teclado", n0 > 8 and await pg.locator('[data-min-todos]').count() == 0 and foco == "1:8", f"{n0} | {foco}")
    await pg.locator('#min-grade-1 .min-card', has_text="Ministério da Fazenda").first.click()
    await pg.wait_for_timeout(500)
    jan = await pg.locator("#gaveta").inner_text()  # site-d-r14: a janela virou a gaveta
    ok("ministros do passado: a gaveta mostra quem chefiou, as datas e as fontes", "Henrique de Campos Meirelles" in jan and "12/05/2016 a 06/04/2018" in jan
       and ("Fontes" in jan) and await pg.locator("#gaveta a[href*='in.gov.br'], #gaveta a[href*='biblioteca.presidencia']").count() >= 1, jan.replace("\n", " ")[:160])
    await pg.keyboard.press("Escape")
    ok("nenhum erro de JavaScript (layout)", not erros, "; ".join(erros)[:300])
    await ctx.close()


async def enderecos(nav):
    ctx = await nav.new_context(viewport={"width": 1366, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    ativa = "() => EP.abas && EP.abas.ativa()"
    # os endereços que já existiam continuam funcionando
    for u, espera in (("brasil.html?mandato=2019", "mandato=2019"), ("brasil.html?mandato=2027", "mandato=2027"), ("estado.html?uf=BA&mandato=2019", "mandato=2019"),
                      ("cidade.html?ibge=2927408&mandato=2021", "mandato=2021"), ("estado.html?uf=SP&mandato=2027", "mandato=2027")):
        await ir(pg, u)
        ok(f"{u}: abre aquele mandato, com abas e a faixa", espera in pg.url and await pg.locator(".abas-grupo [role=tab]").count() >= 4 and await pg.locator("#faixa-mandato").count() == 1)
    await ir(pg, "brasil.html#quem-assume")
    ok("brasil.html#quem-assume: leva ao mandato 2027, na primeira aba", "mandato=2027" in pg.url and await pg.evaluate(ativa) == "executivo", pg.url.split("/")[-1])
    await ir(pg, "brasil.html#qa-senado")
    ok("brasil.html#qa-senado: leva ao mandato 2027, na aba Senado", "mandato=2027" in pg.url and pg.url.endswith("#senado") and await pg.evaluate(ativa) == "senado", pg.url.split("/")[-1])
    await ir(pg, "estado.html?uf=SP#qa-assembleia")
    ok("estado.html?uf=SP#qa-assembleia: leva ao mandato 2027, na aba Deputados estaduais", "mandato=2027" in pg.url and await pg.evaluate(ativa) == "estaduais", pg.url.split("/")[-1])
    await ir(pg, "estado.html?uf=SP&mandato=2027#quem-assume")
    ok("estado.html?uf=SP&mandato=2027#quem-assume: a primeira aba", await pg.evaluate(ativa) == "governo")
    # o aviso de hoje leva para a mesma aba no mandato 2027
    await ir(pg, "brasil.html#senado")
    href = await pg.locator("#senado .aviso-futuro a").get_attribute("href") if await pg.locator("#senado .aviso-futuro a").count() else ""
    ok("hoje: “Veja quem assume em 2027” leva à mesma aba em 2027", href.endswith("mandato=2027#senado"), href)
    # trocar de mandato pelo campo continua na mesma aba; Voltar e Avançar do navegador
    campo = pg.locator("#mandato-lugar input[role=combobox]")
    await campo.focus()
    await pg.keyboard.press("Control+A")
    await pg.keyboard.type("2019", delay=40)
    await pg.wait_for_timeout(500)
    async with pg.expect_navigation():
        await pg.keyboard.press("Enter")
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1000)
    ok("trocar de mandato pelo campo continua na mesma aba (Senado)", "mandato=2019" in pg.url and pg.url.endswith("#senado") and await pg.evaluate(ativa) == "senado", pg.url.split("/")[-1])
    await aba(pg, "camara")
    hoje = await pg.locator("#faixa-mandato .fm-hoje").get_attribute("href")
    ok("“Voltar para hoje” leva para a aba aberta (Câmara), sem o mandato", hoje.endswith("brasil.html?lang=pt#camara"), hoje)
    await pg.go_back()
    await pg.wait_for_timeout(1500)
    if "mandato=2019" in pg.url:  # a troca de aba também é um passo do histórico
        await pg.go_back()
        await pg.wait_for_timeout(1500)
    ok("Voltar do navegador: volta para hoje", "mandato" not in pg.url and await pg.locator("#faixa-mandato").count() == 0, pg.url.split("/")[-1])
    await pg.go_forward()
    await pg.wait_for_timeout(1500)
    ok("Avançar do navegador: volta para 2019", "mandato=2019" in pg.url and await pg.locator("#faixa-mandato").count() == 1, pg.url.split("/")[-1])
    # filtros de uma lista não passam de um mandato para outro
    await ir(pg, "brasil.html?senado-partido=PT#senado")
    await campo.focus()
    await pg.keyboard.press("Control+A")
    await pg.keyboard.type("2015", delay=40)
    await pg.wait_for_timeout(500)
    async with pg.expect_navigation():
        await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(1500)
    ok("os filtros da lista ficam no mandato de onde vieram", "senado-partido" not in pg.url and "mandato=2015" in pg.url, pg.url.split("/")[-1])
    # cidade: trocar de mandato e de cidade
    await ir(pg, "cidade.html?ibge=2927408&mandato=1997#camara-mun")
    ok("cidade 1997: abre a aba Câmara Municipal pelo endereço", await pg.evaluate(ativa) == "camara-mun" and "35" in await pg.locator("#casa-ver .contagem").inner_text())
    await aba(pg, "proxima-eleicao")
    txt = await pg.locator("#proxima-eleicao").inner_text()
    lk = await pg.locator("#proxima-eleicao .links-onde a").get_attribute("href")
    ok("cidade 1997: “A próxima eleição” diz quando o mandato acabou e leva ao mandato seguinte", "Este mandato acabou em 31/12/2000" in txt.replace("31 de dezembro de 2000", "31/12/2000")
       or "acabou em" in txt, f"{txt[:120]!r} | {lk}")
    ok("cidade 1997: o link vai para o mandato de 2001 a 2004", (lk or "").endswith("mandato=2001"), lk)
    # o perfil e26-: "Voltar" leva à aba onde a pessoa está no mandato 2027
    uf = json.loads((RAIZ / "dados" / "eleitos" / "AP.json").read_text(encoding="utf-8"))
    dep = next(p for p in uf["camara"]["membros"] if p["link"] == p["id"])
    await ir(pg, f"pessoa.html?id={dep['id']}")
    volta = await pg.get_attribute("#voltar-lista", "href")
    ok("perfil e26 aberto direto: “Voltar” leva à aba Deputados federais do mandato 2027", "estado.html?uf=AP&mandato=2027" in volta and volta.endswith("#federais"), volta)
    ok("nenhum erro de JavaScript (endereços)", not erros, "; ".join(erros)[:300])
    await ctx.close()


# (site-d-r14, 4/11: o tablist fica dentro da barra presa, div.abas-barra, com os botões ‹ ›)
# barra das abas: sem rolagem, a última aba inteira e nada esmaecido; com rolagem, toda aba cortada tem o esmaecimento do lado dela
BARRA = """() => {
  const l = document.querySelector('.abas-grupo > .abas-barra > [role=tablist]');
  if (!l) return null;
  const tabs = [...l.querySelectorAll('[role=tab]')].filter(t => !t.hidden);
  const olha = () => {
    const rl = l.getBoundingClientRect(), esq = l.classList.contains('mais-esq'), dir = l.classList.contains('mais-dir');
    const cortadas = tabs.map(t => t.getBoundingClientRect()).map(r => [r.left < rl.left - 1, r.right > rl.right + 1]);
    return { esq, dir, cortaEsq: cortadas.some(c => c[0]), cortaDir: cortadas.some(c => c[1]) };
  };
  const rola = l.scrollWidth > l.clientWidth + 1;
  const res = { rola, sw: l.scrollWidth, cw: l.clientWidth, estados: [] };
  for (const x of [0, 0.5, 1]) {
    l.scrollLeft = (l.scrollWidth - l.clientWidth) * x;
    l.dispatchEvent(new Event('scroll'));
    res.estados.push(olha());
  }
  l.scrollLeft = 0;
  l.dispatchEvent(new Event('scroll'));
  const t = tabs[tabs.length - 1].getBoundingClientRect(), rl = l.getBoundingClientRect();
  res.ultimaInteira = t.left >= rl.left - 1 && t.right <= rl.right + 1;
  return res;
}"""


def barra_ok(r):
    if r is None:
        return False, "sem barra"
    erros = []
    for e in r["estados"]:
        if e["cortaDir"] != e["dir"] or e["cortaEsq"] != e["esq"]:
            erros.append(str(e))
    if not r["rola"] and not r["ultimaInteira"]:
        erros.append("sem rolagem, mas a última aba está cortada")
    if not r["rola"] and any(e["esq"] or e["dir"] for e in r["estados"]):
        erros.append("sem rolagem, mas esmaecida")
    return not erros, f"rola={r['rola']} {r['sw']}/{r['cw']} " + "; ".join(erros)[:200]


async def barra(nav):
    paginas = ["brasil.html", "brasil.html?mandato=2019", "brasil.html?mandato=2027", "estado.html?uf=BA", "estado.html?uf=SP&mandato=2027", "estado.html?uf=DF",
               "estado.html?uf=BA&mandato=1995", "cidade.html?ibge=2927408", "cidade.html?ibge=3550308&mandato=1997", "pessoa.html?id=pres-lula", "pessoa.html?id=dep-178866"]
    larguras = [1920, 1440, 1366, 768, 390, 320]
    falhas, total = [], 0
    for escala in (1, 1.5):
        for lang in ("pt", "en"):
            ctx = await nav.new_context(viewport={"width": larguras[0], "height": 900})
            if escala != 1:
                await ctx.add_init_script("localStorage.setItem('ep-a11y', JSON.stringify({escala: %s}))" % escala)
            pg = await ctx.new_page()
            for p in paginas:
                await pg.set_viewport_size({"width": larguras[0], "height": 900})
                await ir(pg, p, lang, 1200)
                for w in larguras:
                    await pg.set_viewport_size({"width": w, "height": 900})
                    await pg.wait_for_timeout(350)
                    r = await pg.evaluate(BARRA)
                    bom, info = barra_ok(r)
                    total += 1
                    if not bom:
                        falhas.append(f"{p} {lang} letra {escala} {w}px: {info}")
            await ctx.close()
    ok(f"barra das abas: sem rolagem, nada cortado nem esmaecido; com rolagem, o esmaecimento só do lado das abas escondidas ({total} combinações: "
       f"{len(paginas)} páginas × 6 larguras × letra normal e 1,5× × pt/en)", not falhas, " | ".join(falhas)[:900])
    # o caso do print do Lucas: estado.html?uf=BA a 1440 px, a última aba ("Minha cidade") inteira e sem esmaecer
    ctx = await nav.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await ir(pg, "estado.html?uf=BA")
    r = await pg.evaluate(BARRA)
    ok("estado.html?uf=BA a 1440 px: “Minha cidade” inteira, sem rolagem e sem esmaecer", r and not r["rola"] and r["ultimaInteira"] and not any(e["dir"] or e["esq"] for e in r["estados"]), str(r)[:200])
    # recalcula quando a letra muda (A+) sem recarregar e quando as fontes chegam
    await pg.set_viewport_size({"width": 900, "height": 900})
    await pg.wait_for_timeout(400)
    antes = await pg.evaluate(BARRA)
    await pg.evaluate("() => { document.documentElement.style.setProperty('--escala', 1.5); window.dispatchEvent(new Event('ep-a11y')); }")
    await pg.wait_for_timeout(500)
    depois = await pg.evaluate(BARRA)
    bom, info = barra_ok(depois)
    ok("letra maior sem recarregar: a barra mede de novo (rola e esmaece do lado certo)", bom and depois["sw"] > antes["sw"], f"{antes['sw']} → {depois['sw']} {info}")
    await pg.evaluate("() => { document.documentElement.style.setProperty('--escala', 1); window.dispatchEvent(new Event('ep-a11y')); }")
    await pg.wait_for_timeout(500)
    bom, info = barra_ok(await pg.evaluate(BARRA))
    ok("letra normal de novo: a barra volta a caber", bom, info)
    await ctx.close()


# espaço entre o fim do conteúdo da aba aberta e o rodapé (sem contar o que vem depois das abas, como os links da cidade)
VAZIO = """() => {
  const p = document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden])'), foot = document.querySelector('footer.rodape');
  if (!p || !foot) return null;
  let fim = 0;
  p.querySelectorAll('*').forEach(e => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || e.closest('[hidden]')) return;
    const r = e.getBoundingClientRect();
    if (r.height > 0 && r.width > 0) fim = Math.max(fim, r.bottom);
  });
  let meio = 0;
  let x = document.querySelector('.abas-ep').nextElementSibling;
  for (; x; x = x.nextElementSibling) { const r = x.getBoundingClientRect(); if (r.height) meio += r.height; }
  // na cidade, as abas ficam dentro de #cidade: o que vem depois de #cidade também conta como "meio"
  const cid = document.getElementById('cidade');
  if (cid && cid.contains(p)) for (let y = cid.nextElementSibling; y; y = y.nextElementSibling) { const r = y.getBoundingClientRect(); if (r.height && !y.contains(p)) meio += r.height; }
  return Math.round(foot.getBoundingClientRect().top - fim - meio);
}"""


async def vazio(nav):
    ctx = await nav.new_context(viewport={"width": 1830, "height": 1000})
    pg = await ctx.new_page()
    paginas = ["brasil.html", "brasil.html?mandato=2019", "brasil.html?mandato=1995", "brasil.html?mandato=2027", "estado.html?uf=BA", "estado.html?uf=BA&mandato=2019",
               "estado.html?uf=BA&mandato=1995", "estado.html?uf=BA&mandato=2027", "estado.html?uf=SP", "estado.html?uf=DF&mandato=2027",
               "cidade.html?ibge=2927408", "cidade.html?ibge=2927408&mandato=2021", "cidade.html?ibge=2927408&mandato=1997", "pessoa.html?id=pres-lula",
               "pessoa.html?id=pres-lula&mandato=dep-1987"]
    falhas, n, maior = [], 0, 0
    for p in paginas:
        await ir(pg, p)
        abas = await pg.evaluate("() => [...document.querySelectorAll('.abas-grupo [role=tab]')].filter(t => !t.hidden).map(t => t.getAttribute('data-aba'))")
        for a in abas:
            await aba(pg, a, 1000)
            await pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
            await pg.wait_for_timeout(500)
            g = await pg.evaluate(VAZIO)
            n += 1
            maior = max(maior, g if g is not None else 0)
            if g is None or g > 120:
                falhas.append(f"{p}#{a}: {g} px")
    ok(f"espaço em branco entre o fim da aba e o rodapé ≤ 120 px ({n} abas em {len(paginas)} páginas, hoje, antigos e 2027; o maior: {maior} px)", not falhas, " | ".join(falhas)[:600])
    # o "Ver mais ›" dos cartões grandes sempre numa linha só dele (governador e vice iguais)
    for w in (1830, 1366, 1100, 390):
        await pg.set_viewport_size({"width": w, "height": 1000})
        await ir(pg, "estado.html?uf=BA")
        r = await pg.evaluate("""() => [...document.querySelectorAll('#gov .pessoa-grande')].map(c => {
            const v = c.querySelector('.ver'), ant = v.previousElementSibling; const a = v.getBoundingClientRect(), b = ant.getBoundingClientRect();
            return a.top >= b.bottom - 1; })""")
        ok(f"estado BA a {w} px: o “Ver mais ›” do governador e do vice numa linha só dele", r and all(r), str(r))
    await ctx.close()


async def celular(nav):
    ctx = await nav.new_context(viewport={"width": 320, "height": 740}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    for lang in ("pt", "en"):
        for p in ("brasil.html?mandato=2019", "brasil.html?mandato=1995", "brasil.html?mandato=2027", "estado.html?uf=BA&mandato=2019", "estado.html?uf=SP&mandato=2027",
                  "cidade.html?ibge=2927408&mandato=1997", "cidade.html?ibge=3550308&mandato=2021"):
            await ir(pg, p, lang)
            abas = await pg.evaluate("() => [...document.querySelectorAll('.abas-grupo [role=tab]')].filter(t => !t.hidden).map(t => t.getAttribute('data-aba'))")
            piores = []
            for a in abas:
                await aba(pg, a, 700)
                larg = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
                if larg[0] > larg[1] + 1:
                    piores.append(f"{a}: {larg}")
            faixa = await pg.locator("#faixa-mandato").bounding_box()
            ok(f"320 px ({lang}) {p}: sem rolar para os lados em nenhuma aba, faixa inteira na tela", not piores and faixa and faixa["x"] >= 0 and faixa["x"] + faixa["width"] <= 321,
               "; ".join(piores) + f" faixa={faixa}")
    ok("nenhum erro de JavaScript (celular)", not erros, "; ".join(erros)[:300])
    await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        if "layout" in PARTES:
            await layout(nav)
        if "enderecos" in PARTES:
            await enderecos(nav)
        if "barra" in PARTES:
            await barra(nav)
        if "vazio" in PARTES:
            await vazio(nav)
        if "celular" in PARTES:
            await celular(nav)
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
