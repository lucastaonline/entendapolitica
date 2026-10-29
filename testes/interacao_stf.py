"""Ministros do STF (dados/stf.json, scripts/stf.py): a seção da página do Brasil (#judiciario), o perfil de cada ministro
(pessoa.html?id=stf-...) e a busca. Confere os números da página com os dados, a ordem oficial, os links, os textos em
português e em inglês, o teclado (cartão -> perfil -> Voltar com o foco de volta no cartão), a janela das fontes, a página
de um mandato que já acabou, 320 px sem rolar para os lados, nenhum erro de JavaScript e o axe-core depois de rolar e clicar.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/) e do axe-core em ../ferramentas.
Uso: python testes/interacao_stf.py"""
import asyncio
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8774/
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def br(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def longa(iso, en=False):
    a, m, d = (int(x) for x in iso.split("-"))
    return f"{MONTHS[m - 1]} {d}, {a}" if en else f"{'1º' if d == 1 else d} de {MESES[m - 1]} de {a}"


def antiguidade(m):
    return ((m.get("posse") or {}).get("data") or "9999", (m.get("nomeacao") or {}).get("data") or "9999", m.get("nascimento") or "9999")


async def axe(pg, rotulo):
    # tudo o que aparece ao rolar (.rev) fica visível antes (o axe rola a página e pegaria a animação no meio)
    await pg.evaluate("document.querySelectorAll('.rev').forEach(e => e.classList.add('visivel'))")
    await pg.wait_for_timeout(1300)
    await pg.add_script_tag(path=str(AXE))
    r = await pg.evaluate("""async () => {
      const res = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                            resultTypes: ['violations'] });
      return res.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => (n.target || []).join(' ')).join(' | '));
    }""")
    ok(f"axe-core: 0 problemas ({rotulo})", not r, "; ".join(r)[:300])


async def rola(pg, sel):
    """Rola a seção inteira, devagar, para tudo o que aparece ao rolar (.rev) ficar visível."""
    await pg.evaluate("""async (sel) => {
      const el = document.querySelector(sel); if (!el) return;
      const ini = el.getBoundingClientRect().top + scrollY, fim = ini + el.offsetHeight;
      for (let y = ini - 100; y < fim; y += 300) { scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }
    }""", sel)
    await pg.wait_for_timeout(1300)  # a animação de aparecer (.rev) leva 0,7 s


async def main():
    d = json.loads(urllib.request.urlopen(BASE + "dados/stf.json").read().decode("utf-8"))
    ms = d["ministros"]
    por = {m["id"]: m for m in ms}
    pres, vice = d["presidencia"]["presidente"], d["presidencia"]["vice"]

    # 0. os dados: ordem oficial (presidente, vice, os outros por antiguidade) e cadeiras
    ordem = [pres, vice] + [m["id"] for m in sorted((m for m in ms if m["id"] not in (pres, vice)), key=antiguidade)]
    ok("dados: ordem oficial (presidente, vice e os outros por antiguidade)", [m["id"] for m in ms] == ordem, " | ".join(ordem))
    ok("dados: ministros + cadeiras vazias = 11", len(ms) + len(d.get("vagas") or []) == d["cadeiras"] == 11, f"{len(ms)} + {len(d.get('vagas') or [])}")
    ok("dados: todo ministro tem fonte na indicação, no Senado, na nomeação e na posse",
       all((m.get("indicacao") or {}).get("fontes") and (m.get("senado") or {}).get("fontes") and (m.get("nomeacao") or {}).get("fontes") and
           (m.get("posse") or {}).get("fontes") for m in ms))
    ok("dados: aposentadoria obrigatória = nascimento + 75 anos",
       all(m["aposentadoria"]["data"][4:] == m["nascimento"][4:] and int(m["aposentadoria"]["data"][:4]) - int(m["nascimento"][:4]) == 75 for m in ms))
    ok("dados: placar do Plenário soma o total e passa de 41 votos sim (aprovados)",
       all(m["senado"]["plenario"]["sim"] + m["senado"]["plenario"]["nao"] + (m["senado"]["plenario"]["abstencao"] or 0) == m["senado"]["plenario"]["total"] and
           m["senado"]["plenario"]["sim"] >= 41 for m in ms))
    ok("dados: as Turmas têm todos os ministros, menos quem preside o STF",
       sorted(i for t in d["turmas"] for i in t["membros"]) == sorted(m["id"] for m in ms if m["id"] != pres))

    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 900})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. a seção da página do Brasil (português)
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        await pg.wait_for_selector("#stf a.stf-card", timeout=15000)
        hrefs = await pg.locator("#stf .stf-grade a.stf-card").evaluate_all("els => els.map(a => a.getAttribute('href'))")
        ids = [h.split("id=")[-1] for h in hrefs]
        ok("Brasil: um cartão por ministro, na mesma ordem dos dados", ids == [m["id"] for m in ms], f"{len(ids)} cartões")
        ok("Brasil: cadeira vazia aparece (uma por vaga)", await pg.locator("#stf .stf-card.vaga").count() == len(d.get("vagas") or []))
        txt = await pg.locator("#judiciario").inner_text()
        ok("Brasil: o título diz quantos estão no tribunal", f"{len(ms)} de 11 cadeiras" in txt)
        m0 = por[pres]
        cart0 = await pg.locator("#stf .stf-grade li").first.inner_text()
        ok("Brasil: o 1º cartão é quem preside, com Turma, quem indicou, posse e aposentadoria",
           m0["nome"] in cart0 and "Presidente do STF" in cart0 and br(m0["posse"]["data"]) in cart0 and m0["indicacao"]["presidente"] in cart0
           and br(m0["aposentadoria"]["data"]) in cart0, cart0.replace("\n", " | ")[:200])
        dino = next((m for m in ms if m["id"] == "stf-flavio-dino"), ms[-1])
        cart = await pg.locator(f'#stf a.stf-card[href="pessoa.html?id={dino["id"]}"]').inner_text()
        ok(f"Brasil: cartão de {dino['nome']} com a {dino['turma']}ª Turma, quem indicou e as datas",
           f"{dino['turma']}ª Turma" in cart and dino["indicacao"]["presidente"] in cart and br(dino["posse"]["data"]) in cart and br(dino["aposentadoria"]["data"]) in cart)
        for v in d.get("vagas") or []:
            vt = await pg.locator("#stf .stf-card.vaga").first.inner_text()
            ok("Brasil: a cadeira vazia diz de quem era e o que o Senado fez", (v.get("de") or "") in vt and
               all(((s.get("nome") or "") in vt) for s in v.get("indicacoes") or []), vt.replace("\n", " | ")[:220])
            for s in v.get("indicacoes") or []:
                pl = s.get("plenario") or {}
                if pl.get("sim") is not None:
                    ok("Brasil: placar da indicação na cadeira vazia igual ao dos dados", f"{pl['sim']} votos sim" in vt and f"{pl['nao']} não" in vt)
        pr = await pg.locator("#stf .stf-presidencia").inner_text()
        ok("Brasil: quem preside e o vice, com a data da posse na presidência",
           por[pres]["nome"] in pr and por[vice]["nome"] in pr and longa(d["presidencia"]["desde"]) in pr, pr.replace("\n", " | ")[:160])
        for t in d["turmas"]:
            n = await pg.locator(f"#t-turma-{t['numero']}").locator("xpath=..").locator("li a").count()
            ok(f"Brasil: {t['numero']}ª Turma com {len(t['membros'])} ministros", n == len(t["membros"]))
        ok("Brasil: o link para a parada 8 do mapa continua", await pg.locator('#judiciario a[href="entenda.html#parte-8"]').count() == 1)
        ok("Brasil: atalho do topo leva à seção", await pg.locator('nav.atalhos a[href="#judiciario"]').count() == 1)
        ok("Brasil: 5 passos de como alguém chega ao STF", await pg.locator("#stf .stf-passos li").count() == 5)
        # a janela das fontes das regras (Constituição, EC 88, Regimento): abre, mostra os links e fecha com Esc
        b = pg.locator("#stf .fontes-btn").first
        await b.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(400)
        jan = pg.locator(".janela")
        jl = await jan.locator("a").evaluate_all("els => els.map(a => a.href)") if await jan.count() else []
        ok("Brasil: as regras têm fonte (Constituição, EC 88/2015 e Regimento do STF)",
           any("planalto.gov.br" in u for u in jl) and any("540691" in u for u in jl) and any("RISTF" in u for u in jl), f"{len(jl)} links")
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(300)
        ok("Brasil: Esc fecha a janela e o foco volta ao botão", await pg.evaluate("document.activeElement && document.activeElement.classList.contains('fontes-btn')"))
        await rola(pg, "#judiciario")
        await axe(pg, "Brasil, depois de rolar a seção do STF")

        # 2. teclado: cartão -> perfil -> Voltar (o foco volta ao cartão)
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        await pg.wait_for_selector("#stf a.stf-card")
        alvo = pg.locator(f'#stf a.stf-card[href="pessoa.html?id={dino["id"]}"]')
        await alvo.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_url(f"**/pessoa.html?id={dino['id']}", timeout=15000)
        await pg.wait_for_selector("#nome-pessoa")
        ok("Teclado: Enter no cartão abre o perfil", dino["nome"] in await pg.locator("#nome-pessoa").inner_text())
        await pg.locator("#voltar-lista").click()
        await pg.wait_for_url("**/brasil.html*", timeout=15000)
        await pg.wait_for_timeout(2500)
        foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('href')")
        ok("Teclado: Voltar leva ao Brasil com o foco no cartão de quem foi aberto", foco == f"pessoa.html?id={dino['id']}", str(foco))

        # 3. perfil em português
        await pg.goto(BASE + f"pessoa.html?id={dino['id']}", wait_until="networkidle")
        await pg.wait_for_selector("#como-chegou")
        t = await pg.locator("#perfil").inner_text()
        s, c = dino["senado"]["plenario"], dino["senado"]["ccj"]
        ok("Perfil: cargo e nome", "Ministro do Supremo Tribunal Federal".upper() in t.upper() and dino["nome"] in t)
        ok("Perfil: 5 passos (indicação, CCJ, Plenário, nomeação e posse)", await pg.locator("#como-chegou .stf-linha > li").count() == 5)
        plac = f"{s['sim']} votos sim, {s['nao']} não" + (f" e {s['abstencao']} abstenç" if s.get("abstencao") else "")
        ok("Perfil: placar do Plenário do Senado igual ao dos dados", plac in t, plac)
        ok("Perfil: placar da CCJ igual ao dos dados", f"{c['sim']} votos sim e {c['nao']} não" in t)
        ok("Perfil: datas (indicação, Plenário, posse e aposentadoria)",
           br(dino["indicacao"]["data"]) in t and br(s["data"]) in t and br(dino["posse"]["data"]) in t and longa(dino["aposentadoria"]["data"]) in t)
        ok("Perfil: quem indicou e a mensagem ao Senado", dino["indicacao"]["presidente"] in t and (dino["indicacao"].get("mensagem") or "") in t)
        ok("Perfil: decreto de nomeação no Diário Oficial", (dino["nomeacao"].get("decreto") or "?") in t and "Diário Oficial da União" in t)
        nf = await pg.locator("#perfil .fontes-btn").count()
        ok("Perfil: botão de fonte em cada bloco", nf >= 10, f"{nf} botões")
        links = await pg.locator("#perfil .fontes-lista a").evaluate_all("els => els.map(a => a.href)")
        ok("Perfil: todas as fontes (STF, Senado e Diário Oficial)",
           any("portal.stf.jus.br" in u for u in links) and any("senado.leg.br" in u for u in links) and any("DadosDatas/003.pdf" in u for u in links), f"{len(links)} fontes")
        onde = await pg.locator(".onde-ver a").evaluate_all("els => els.map(a => a.href)")
        ok("Perfil: Onde ver mais com a página oficial do ministro no STF", dino["links"]["gabinete"] in onde and dino["links"]["pasta"] in onde)
        volta = await pg.locator("#voltar-lista").get_attribute("href")
        ok("Perfil aberto direto: Voltar leva à seção do STF", volta == "brasil.html#judiciario", volta)
        ok("Perfil: título da aba", dino["nome"] in await pg.title() and "Supremo" in await pg.title())
        await axe(pg, "perfil em português")

        # 4. perfil em inglês (uma ministra, com a CCJ por unanimidade quando houver)
        f = next((m for m in ms if m.get("genero") == "F"), ms[0])
        await pg.goto(BASE + f"pessoa.html?id={f['id']}&lang=en", wait_until="networkidle")
        await pg.wait_for_selector("#como-chegou")
        t = await pg.locator("#perfil").inner_text()
        ok("Perfil (en): cargo e datas no formato americano", "JUSTICE OF THE FEDERAL SUPREME COURT" in t.upper() and longa(f["posse"]["data"], True) in t, f["nome"])
        sp = f["senado"]["plenario"]
        ok("Perfil (en): placar do Plenário", f"{sp['sim']} votes in favor" in t and f"{sp['nao']} against" in t)
        if f["senado"]["ccj"].get("unanimidade"):
            ok("Perfil (en): CCJ sem nenhum voto contra (unanimidade)", "no votes against" in t)
        ok("Perfil (en): nome marcado como português para o leitor de tela",
           await pg.locator('#nome-pessoa [lang="pt-BR"], #nome-pessoa[lang="pt-BR"]').count() > 0)
        await axe(pg, "perfil em inglês")

        # 5. busca: "fachin" acha o ministro, com o cargo
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="networkidle")
        await pg.fill("#busca", "fachin")
        await pg.wait_for_timeout(1200)
        r = pg.locator('#resultados a[href="pessoa.html?id=stf-edson-fachin"]')
        ok("Busca: 'fachin' acha o ministro do STF", await r.count() == 1)
        ok("Busca: o cargo aparece", "Ministro do Supremo Tribunal Federal" in (await r.inner_text() if await r.count() else ""))
        await pg.fill("#busca", "supremo")
        await pg.wait_for_timeout(1200)
        n = await pg.locator('#resultados a[href^="pessoa.html?id=stf-"]').count()
        ok("Busca: 'supremo' acha os ministros pelo cargo", n >= min(len(ms), 10), f"{n}")
        # em inglês, o cargo da busca sai do EP.cargo (js/comum.js); sem a tradução lá, o cargo aparece em português
        await pg.goto(BASE + "brasil.html?lang=en", wait_until="networkidle")
        traduz = await pg.evaluate("EP.cargo('Ministra do Supremo Tribunal Federal') !== 'Ministra do Supremo Tribunal Federal'")
        await pg.fill("#busca", "fachin")
        await pg.wait_for_timeout(1200)
        r = pg.locator('#resultados a[href="pessoa.html?id=stf-edson-fachin"]')
        if traduz:
            ok("Busca (en): o cargo aparece em inglês", "Justice" in (await r.inner_text() if await r.count() else ""))
        else:
            ok("Busca (en): acha o ministro (o cargo em inglês depende do pedido para o js/comum.js)", await r.count() == 1)
            print("   ⚠️ pendente: CARGOS_EN do js/comum.js ainda não traduz o cargo dos ministros do STF")

        # 6. página do Brasil em inglês e de um mandato que já acabou
        await pg.goto(BASE + "brasil.html?lang=en", wait_until="networkidle")
        await pg.wait_for_selector("#stf a.stf-card")
        t = await pg.locator("#judiciario").inner_text()
        ok("Brasil (en): textos em inglês", "How someone gets to the STF" in t and "The justices" in t and ("Empty seat" in t if d.get("vagas") else True))
        await pg.goto(BASE + "brasil.html?mandato=2019&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        t = await pg.locator("#judiciario").inner_text()
        ok("Mandato que acabou: só as regras, sem os ministros de hoje, com o link para hoje",
           await pg.locator("#stf a.stf-card").count() == 0 and await pg.locator("#stf .stf-passos li").count() == 5 and
           await pg.locator('#stf a[href="brasil.html#judiciario"]').count() == 1, t.replace("\n", " | ")[:120])
        ok("Nenhum erro de JavaScript (computador)", not erros, "; ".join(erros)[:300])
        await ctx.close()

        # 7. celular de 320 px: nada de rolar para os lados
        ctx = await nav.new_context(viewport={"width": 320, "height": 760}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        for u in ("brasil.html", "brasil.html?lang=en", f"pessoa.html?id={dino['id']}", f"pessoa.html?id={pres}&lang=en"):
            await pg.goto(BASE + u, wait_until="networkidle")
            await pg.wait_for_timeout(1200)
            await rola(pg, "#judiciario" if u.startswith("brasil") else "#perfil")
            larg = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(f"320 px sem rolar para os lados: {u}", larg <= 0, f"{larg}px")
        await axe(pg, "perfil em inglês, 320 px")
        ok("Nenhum erro de JavaScript (celular)", not erros, "; ".join(erros)[:300])
        await nav.close()

    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
