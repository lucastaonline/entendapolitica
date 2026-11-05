"""Teste da trajetória (frente trajetoria-r9): a linha do tempo de candidaturas e mandatos no perfil (aba "História").

Se o js/pessoa.js e o pessoa.html ainda não têm o trecho de integração, o teste aplica o trecho (as trocas exatas de
TROCAS_PESSOA_JS e TROCAS_PESSOA_HTML, iguais às das notas da frente) na resposta do servidor, só dentro do navegador do
teste; depois da integração, as trocas não fazem nada.

Confere, para perfis variados (senador que foi deputado federal, deputado que foi vereador ou prefeito, prefeito que foi
vereador, quem nunca concorreu antes, ministro sem eleição, ministro do STF, eleito em 2026): o número de itens e o
resumo contra dados/trajetoria/<balde>.json, o resumo e o botão "Ver este mandato" de cada mandato, os filtros pelo teclado, o inglês (sem
português solto), 320 px sem rolar para os lados, alto contraste, menos movimento, axe-core (WCAG 2.2 AA) no computador e
no celular e nenhum erro de JavaScript.

Uso: python testes/trajetoria.py [ids...]   (servidor: EP_BASE, padrão http://127.0.0.1:8786/)
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8786/")
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
PADRAO = os.environ.get("TRAJ_IDS", "").split() or [
    "sen-5672",            # senador que foi deputado federal (e concorreu a governador em 2026)
    "dep-204353",          # deputada federal que já concorreu na cidade
    "pref-2606309",        # prefeito que foi vereador
    "ver-4127858-160001975392",  # vereador que nunca tinha concorrido antes de 2024
    "dest-GO-90001648402", # deputado estadual suplente em exercício
    "pref-3119302",        # prefeito que assumiu o cargo sem ser o eleito (pesquisa à mão, com fonte)
    "e26-MG-130002539932", # eleito em 2026 sem cargo hoje
    "pres-lula",           # presidente: 1994 a 2026, com o 2º turno de 2006 (Biblioteca da Presidência)
    "stf-flavio-dino",     # ministro do STF que já foi deputado, governador e senador
    "stf-gilmar-mendes",   # ministro do STF que nunca concorreu
    "min-saude",           # ministro de Estado (sem ligação com o TSE)
]
erros_js = []
falhas = []


def balde(pid: str) -> str:
    h = 0x811C9DC5
    for b in pid.encode():
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h % 256:02x}"


def dados(pid: str) -> dict | None:
    d = json.loads((RAIZ / "dados" / "trajetoria" / f"{balde(pid)}.json").read_text(encoding="utf-8"))
    t = d["pessoas"].get(pid)
    if t:  # as candidaturas vêm em lista curta (como o js/trajetoria.js desfaz)
        its = []
        for x in t["it"]:
            if isinstance(x, list):
                it = {"k": "c", "a": x[0], "c": x[1], "p": x[3] if len(x) > 3 else None, "r": x[4], "v": x[5] if len(x) > 5 else None,
                      "sq": x[6] if len(x) > 6 else None}
                it.update(x[7] if len(x) > 7 else {})
                x = it
            its.append(x)
        t["it"] = its
    return t


def ok(cond, msg):
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


MONTA = None  # (antes da integração, o teste montava a seção à mão; agora aplica o trecho de integração, abaixo)

# O trecho de integração (o mesmo das notas da frente, files/plano-100/notas/trajetoria-r9.md). Enquanto o js/pessoa.js e o
# pessoa.html do lab não tiverem o trecho, o teste aplica estas trocas na resposta do servidor (só no navegador do teste;
# nada é gravado). Depois da integração, as trocas não fazem nada e o teste vale para o site de verdade.
TROCAS_PESSOA_JS = [
    ('    if (p.tipo === "stf" && EP.stf) { raiz.innerHTML = EP.stf.perfilHtml(p); return; }  // ministros do STF: o perfil vem do js/stf.js\n',
     '    if (p.tipo === "stf" && EP.stf) {  // ministros do STF: o perfil vem do js/stf.js\n'
     '      raiz.innerHTML = EP.stf.perfilHtml(p) + (EP.trajetoria ? \'<section class="secao-perfil traj" id="trajetoria"></section>\' : "");  // trajetoria\n'
     '      if (EP.trajetoria) EP.trajetoria(document.getElementById("trajetoria"), p);  // trajetoria\n'
     '      return;\n'
     '    }\n'),
    ('fatosHtml(p) + anterioresHtml(p) + contatosHtml(p)', 'fatosHtml(p) + (EP.trajetoria ? "" : anterioresHtml(p)) + contatosHtml(p)'),
    ('comissoesHtml(p) + avisoEMinisterio(p)],\n',
     'comissoesHtml(p) + avisoEMinisterio(p)],\n'
     '      // trajetoria (js/trajetoria.js): a história na política; enquanto carrega (ou se não houver dados), "Mandatos anteriores"\n'
     '      ["trajetoria", "🧭", EP.tr("História", "Career"), EP.trajetoria ? \'<section class="secao-perfil traj" id="trajetoria">\' + anterioresHtml(p) + "</section>" : ""],\n'),
    ('    montaAbas(p);\n  }\n',
     '    montaAbas(p);\n'
     '    if (EP.trajetoria) EP.trajetoria(document.getElementById("trajetoria"), p);  // trajetoria: a história na política\n  }\n'),
]
TROCAS_PESSOA_HTML = [
    ('<link rel="stylesheet" href="css/abas.css', '<link rel="stylesheet" href="css/trajetoria.css?v=1"><!-- trajetoria: a história na política -->\n  <link rel="stylesheet" href="css/abas.css'),
    ('<script src="js/pessoa.js', '<script src="js/trajetoria.js?v=1"></script><!-- trajetoria: a história na política -->\n<script src="js/pessoa.js'),
]


def troca(txt: str, trocas, marca: str) -> str:
    if marca in txt:
        return txt  # já integrado
    for a, b in trocas:
        if a not in txt:
            falhas.append(f"o trecho de integração não acha no arquivo: {a[:70]!r}")
            print(f"  FALHA trecho de integração não encontrado: {a[:70]!r}")
            continue
        txt = txt.replace(a, b, 1)
    return txt


async def integra(ctx):
    async def js(route):
        r = await route.fetch()
        await route.fulfill(response=r, body=troca(await r.text(), TROCAS_PESSOA_JS, "EP.trajetoria"), headers={**r.headers, "cache-control": "no-store"})

    async def html(route):
        r = await route.fetch()
        await route.fulfill(response=r, body=troca(await r.text(), TROCAS_PESSOA_HTML, "js/trajetoria.js"), headers={**r.headers, "cache-control": "no-store"})
    await ctx.route(re.compile(r".*/js/pessoa\.js(\?.*)?$"), js)
    await ctx.route(re.compile(r".*/pessoa\.html(\?.*)?$"), html)


async def abre(pg, pid, lang="pt"):
    await pg.goto("about:blank")
    await pg.goto(f"{BASE}pessoa.html?id={pid}&lang={lang}#trajetoria", wait_until="networkidle")
    await pg.wait_for_selector("#perfil .perfil-topo, #perfil h1", timeout=20000)
    await pg.wait_for_function("() => { const s = document.getElementById('trajetoria'); return s && (s.hidden || s.querySelector('.traj-lista')); }", timeout=20000)
    # com abas: a aba "História" aberta (o endereço #trajetoria já abre; garante)
    await pg.evaluate("() => { if (window.EP && EP.abas && EP.abas.mostra) EP.abas.mostra('trajetoria'); }")
    await pg.wait_for_timeout(300)
    return {"tem": await pg.evaluate("!!document.querySelector('#trajetoria .traj-lista')")}


async def axe(pg, rotulo):
    if not AXE.exists():
        print("  (sem axe-core em ../ferramentas)")
        return
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run({ include: [['#trajetoria']] }, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] }, resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    ok(not v, f"axe-core na trajetória ({rotulo}): {len(v)} problema(s) {v[:4]}")


async def confere(pg, pid, mobile=False):
    t = dados(pid)
    print(f"\n=== {pid}{' (celular)' if mobile else ''}")
    ok(t is not None, f"{pid} está em dados/trajetoria/{balde(pid)}.json")
    if t is None:
        return
    r = await abre(pg, pid)
    ok(r["tem"], "a seção foi montada pelo perfil (trecho de integração)")
    if await pg.locator("[role=tab]").count():
        aba = pg.locator("[role=tab][data-aba='trajetoria'], [role=tab][aria-controls*='trajetoria']")
        ok(await aba.count() == 1 and await aba.first.get_attribute("aria-selected") == "true", "a aba “História” existe e abre por #trajetoria")
    ok(await pg.locator("#sobre .anteriores").count() == 0, "“Mandatos anteriores” não aparece duas vezes")
    n_it = await pg.locator("#trajetoria .traj-item").count()
    ok(n_it == len(t["it"]), f"itens na tela ({n_it}) = itens nos dados ({len(t['it'])})")
    cands = [it for it in t["it"] if it["k"] == "c"]
    resumo = await pg.locator("#trajetoria .traj-resumo, #trajetoria > p:not(.traj-intro)").first.inner_text()
    if len(cands) > 1:
        ok(f"{len(cands)} vezes" in resumo or f"{len(cands):,}".replace(",", ".") + " vezes" in resumo, f"resumo diz {len(cands)} candidaturas: {resumo[:90]!r}")
    anos = await pg.locator("#trajetoria .traj-ano").all_inner_texts()
    ok([a for a in anos] == [str(it.get("a") or (it.get("i") or (it.get("m") or {}).get("i") or "")[:4]) for it in t["it"]],
       "os anos aparecem na ordem dos dados (do mais novo para o mais velho)")
    # o que fez em cada mandato (perfil-mandato-r10: o bloco que abria virou um resumo de uma linha e o botão “Ver este
    # mandato”, que abre o perfil inteiro filtrado por aquele mandato)
    curtos = await pg.locator("#trajetoria .traj-fez-curto").count()
    n_m = sum(1 for it in t["it"] if (it.get("m") or {}).get("fez"))
    ok(curtos >= n_m, f"resumos do que fez em cada mandato ({curtos}) >= mandatos com contagem ({n_m})")
    vers = pg.locator("#trajetoria a.traj-ver-btn")
    if await vers.count():
        await vers.first.focus()
        ok(await vers.first.evaluate("a => a === document.activeElement && /[?&]id=/.test(a.getAttribute('href'))"),
           "o botão “Ver este mandato” recebe o foco pelo teclado e leva ao perfil filtrado")
    mm = next((it["m"] for it in t["it"] if (it.get("m") or {}).get("fez")), None)
    if mm and curtos:
        txt = await pg.locator("#trajetoria .traj-fez-curto").first.inner_text()
        # no próprio perfil, a conta é a da lista do perfil (a mesma da aba “O que propôs”)
        ok(str(mm["fez"]["prop"]) in txt.replace(".", "") or mm["fez"]["prop"] == 0 or mm.get("pf") == pid, f"o número de propostas ({mm['fez']['prop']}) aparece: {txt[:80]!r}")
    # filtros (lista longa)
    if await pg.locator("[data-traj-filtro]").count():
        b = pg.locator("[data-traj-filtro='ganhou']")
        await b.focus()
        await pg.keyboard.press("Enter")
        ok(await b.get_attribute("aria-pressed") == "true", "filtro 'Só eleições ganhas e mandatos' pelo teclado")
        vis = await pg.locator("#trajetoria .traj-item:not([hidden])").count()
        esperado = sum(1 for it in t["it"] if it["k"] != "c" or it.get("m") or it.get("hoje") or it["r"] in ("e", "eqp", "emed"))
        ok(vis == esperado, f"o filtro mostra {vis} itens (esperado {esperado})")
        conta = await pg.locator("[data-traj-conta]").inner_text()
        ok(str(vis) in conta, f"o leitor de tela ouve a contagem: {conta!r}")
        await pg.locator("[data-traj-filtro='todos']").click()
    # fonte: abre a janela
    fb = pg.locator("#trajetoria .fontes-btn").first
    if await fb.count():
        await fb.click()
        await pg.wait_for_timeout(200)
        ok(await pg.locator("dialog[open] a[href*='tse.jus.br'], dialog[open] a[href*='leg.br'], dialog[open] a[href*='gov.br'], dialog[open] a[href*='stf.jus.br']").count() > 0,
           "a fonte abre com link oficial")
        await pg.keyboard.press("Escape")
    # 320 px, alto contraste, menos movimento
    if mobile:
        await pg.set_viewport_size({"width": 320, "height": 700})
        await pg.wait_for_timeout(200)
        lado = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(lado <= 0, f"320 px sem rolar para os lados (sobra {lado}px)")
        await pg.set_viewport_size({"width": 390, "height": 844})
    await pg.evaluate("document.documentElement.classList.add('alto-contraste','sem-movimento')")
    await axe(pg, ("celular" if mobile else "computador") + ", alto contraste")
    await pg.evaluate("document.documentElement.classList.remove('alto-contraste','sem-movimento')")
    await axe(pg, "celular" if mobile else "computador")
    # "Ver a lista na parte “O que propôs”": leva para a aba das propostas
    lk = pg.locator("#trajetoria a[href='#propostas']").first
    if await lk.count():
        await lk.evaluate("a => a.closest('details') && (a.closest('details').open = true)")
        await lk.click()
        await pg.wait_for_timeout(400)
        ok(await pg.locator("#propostas").is_visible(), "o link “Ver a lista” abre a parte “O que propôs”")
    # inglês
    await abre(pg, pid, "en")
    solto = await pg.evaluate("""() => {
      const pt = /\\b(Concorreu|Eleit[oa]|Não eleit|Suplente|Partido na época|votos|vezes|mandato|Assumiu|Fonte|Como montamos)\\b/;
      const w = document.createTreeWalker(document.getElementById('trajetoria'), NodeFilter.SHOW_TEXT);
      const out = [];
      while (w.nextNode()) { const n = w.currentNode; if (n.parentElement.closest('[lang="pt-BR"]')) continue; if (pt.test(n.textContent)) out.push(n.textContent.trim().slice(0, 60)); }
      return out;
    }""")
    ok(not solto, f"inglês sem português solto: {solto[:4]}")
    tit = await pg.locator("#t-traj").inner_text()
    ok("career" in tit.lower(), f"título em inglês: {tit!r}")


async def main():
    ids = sys.argv[1:] or PADRAO
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        for mobile in (False, True):
            opts = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True) if mobile else dict(viewport={"width": 1280, "height": 900})
            ctx = await nav.new_context(**opts)
            await integra(ctx)
            pg = await ctx.new_page()
            pg.on("pageerror", lambda e: erros_js.append(str(e)))
            pg.on("console", lambda m: erros_js.append(m.text) if m.type == "error" and "trajet" in m.text.lower() else None)
            for pid in ids:
                await confere(pg, pid, mobile)
            await ctx.close()
        await nav.close()
    ok(not erros_js, f"nenhum erro de JavaScript: {erros_js[:3]}")
    print(f"\n{'TUDO CERTO' if not falhas else str(len(falhas)) + ' FALHA(S)'}")
    sys.exit(1 if falhas else 0)


asyncio.run(main())
