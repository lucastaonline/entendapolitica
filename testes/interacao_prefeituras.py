"""Testes de interação das leis e vetos das prefeituras pelos Diários Oficiais (scripts/municipios/diarios.py ->
dados/prefeituras/<UF>.json -> montar.py -> prefeito.executivo e onde.prefeitura.leis em dados/cidades/<UF>/<IBGE>.json):
perfil do prefeito com a contagem, vetos totais e parciais, fontes, "Como contamos", o motivo e o link em "Onde ver mais",
quem assumiu numa eleição suplementar (sem a conta), inglês, 320 px e axe-core com as caixas abertas.
Precisa do servidor em 8770 (ou EP_BASE) e do montar.py rodado. Uso: python testes/interacao_prefeituras.py"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8771/
RAIZ = Path(__file__).resolve().parents[1]
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def ler(arq):
    return json.loads(Path(arq).read_text(encoding="utf-8"))


def cidade(ibge):
    arqs = list((RAIZ / "dados" / "cidades").glob(f"*/{ibge}.json"))
    return ler(arqs[0]) if arqs else None


def escolher():
    """Cidades de exemplo, tiradas dos dados (o teste continua valendo quando os números mudam)."""
    com_vetos = sem_vetos = suplementar = juncao = None
    fora = {}
    for arq in sorted((RAIZ / "dados" / "prefeituras").glob("*.json")):
        d = ler(arq)
        for ibge, c in (d.get("cidades") or {}).items():
            ci = cidade(ibge)
            p = (ci or {}).get("prefeito") or {}
            ex = p.get("executivo") or {}
            if not juncao and ex and p.get("extras"):
                # o SAPL da Câmara (arquivo extra) tem só os vetos ou só as leis: o perfil junta as duas contas
                x = ler(RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json") if p["extras"] == "cidade" else ler(RAIZ / "dados" / "pessoas" / f"pref-{ibge}.json")
                sx = (((x.get("pessoas") or {}).get(f"pref-{ibge}") if p["extras"] == "cidade" else x) or {}).get("executivo") or {}
                if sx and (sx.get("leisSancionadas") is None or sx.get("vetos") is None):
                    juncao = (ibge, ci, sx)
            if com_vetos and sem_vetos and suplementar:
                continue
            if not com_vetos and ex.get("vetosTotais") is not None and ex.get("vetosParciais") is not None and len(ex.get("fontes") or []) >= 2:
                com_vetos = (ibge, ci)
            elif not sem_vetos and ex and ex.get("vetos") is None and not ex.get("fontes") and not p.get("extras"):
                sem_vetos = (ibge, ci)
            elif not suplementar and not ex and "suplementar" in (p.get("situacao") or ""):
                suplementar = (ibge, ci)
        for ibge, f in (d.get("fora") or {}).items():
            tipo = f.get("tipo")
            if tipo in ("diario", "legislacao") and tipo not in fora and f.get("url"):
                ci = cidade(ibge)
                if ci and (ci.get("prefeito") or {}).get("nome") and ((ci.get("onde") or {}).get("prefeitura") or {}).get("leis"):
                    fora[tipo] = (ibge, ci)
    return com_vetos, sem_vetos, suplementar, fora, juncao


async def ir(pg, url):
    try:
        await pg.goto(BASE + url, wait_until="networkidle", timeout=25000)
    except Exception:
        await pg.wait_for_timeout(1500)
    await pg.wait_for_timeout(900)


async def axe(pg):
    await pg.add_script_tag(path=str(AXE))
    return await pg.evaluate("""async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
      resultTypes: ['violations'] })).violations.map(v => v.id + ' (' + v.nodes.length + ')')""")


def data_longa(iso):
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    a, m, d = iso.split("-")
    return f"{int(d)} de {meses[int(m) - 1]} de {a}"


async def main():
    com_vetos, sem_vetos, suplementar, fora, juncao = escolher()
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(f"{pg.url}: {e}"))
        # o idioma escolhido fica salvo no aparelho: as páginas em português levam &lang=pt

        # 1. prefeito com leis e vetos (totais e parciais) e duas fontes (busca de "lei" e de "veto")
        ok("dados: há cidade com vetos totais e parciais e duas fontes", com_vetos)
        if com_vetos:
            ibge, ci = com_vetos
            ex = ci["prefeito"]["executivo"]
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=pt")
            sec = pg.locator("section[aria-labelledby='t-exec']")
            txt = await sec.inner_text() if await sec.count() else ""
            ok(f"{ci['nome']}/{ci['uf']}: seção \"Leis sancionadas e vetos\"", "Leis sancionadas e vetos" in txt)
            n = f"{ex['leisSancionadas']:,}".replace(",", ".")
            ok("número de leis igual ao dos dados", f"{n}\nleis sancionadas desde 2025" in txt, f"{n} leis")
            tot, par = ex["vetosTotais"], ex["vetosParciais"]
            ok("vetos com totais e parciais", f"{tot} {'total' if tot == 1 else 'totais'} e {par} {'parcial' if par == 1 else 'parciais'}" in txt, f"{ex['vetos']} vetos")
            ok("data da lei mais recente na fonte", "A lei mais recente na fonte é de " + data_longa(ex["periodo"]["ultimaLei"]) in txt)
            ok("sem o quadro de propostas, o texto não manda procurar por ele",
               "isso está em" not in txt and await pg.locator("#t-propostas").count() == 0)
            det = sec.locator("details.como-contou")
            await det.locator("summary").click()
            ok("\"Como contamos\" abre com a nota da contagem", await det.get_attribute("open") is not None and ex["nota"][:60] in await det.inner_text())
            btn = sec.locator("button.fontes-btn")
            await btn.click()
            await pg.wait_for_timeout(500)
            dlg = pg.locator(".janela-corpo")
            hrefs = await dlg.locator("a[href^='http']").evaluate_all("as => as.map(a => a.href)") if await dlg.count() else []
            ok("\"De onde veio isso?\" mostra as duas fontes", all(any(f["url"] in h or h in f["url"] for h in hrefs) for f in ex["fontes"]), f"{len(hrefs)} links")
            r = await axe(pg)
            ok("axe-core com \"Como contamos\" e as fontes abertos: 0 problemas", not r, ", ".join(r))
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
            onde = pg.locator("section.onde-ver")
            otxt = await onde.inner_text() if await onde.count() else ""
            ok("\"Onde ver mais\" não diz que faltam as leis", "As leis que" not in otxt, otxt[:80].replace("\n", " "))

            # em inglês
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=en")
            txt = await pg.locator("section[aria-labelledby='t-exec']").inner_text()
            ok("inglês: título, leis e vetos", "Laws signed and vetoes" in txt and "laws signed since 2025" in txt and f"{tot} full and {par} partial" in txt)
            det = pg.locator("details.como-contou")
            await det.locator("summary").click()
            ok("inglês: \"How we counted\" com a nota em inglês", ex["nota_en"][:50] in await det.inner_text())
            r = await axe(pg)
            ok("inglês: axe-core 0 problemas", not r, ", ".join(r))

            # 320 px: nada vaza para os lados
            p320 = await ctx.new_page()
            await p320.set_viewport_size({"width": 320, "height": 800})
            await ir(p320, f"pessoa.html?id=pref-{ibge}&lang=pt")
            larg = await p320.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
            ok("320 px sem rolagem para os lados", larg[0] <= larg[1], f"{larg[0]} x {larg[1]}")
            await p320.close()

        # 2. prefeito com leis e sem vetos (a prefeitura não publica os vetos numerados): sem número de vetos
        if sem_vetos:
            ibge, ci = sem_vetos
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=pt")
            txt = await pg.locator("section[aria-labelledby='t-exec']").inner_text()
            ok(f"{ci['nome']}/{ci['uf']}: leis sem número de vetos", "leis sancionadas desde" in txt and "vetos desde" not in txt and "vetos (totais ou parciais)" not in txt)

        # 3. cidades fora: o motivo e o link para conferir no "Onde ver mais"
        for tipo, (ibge, ci) in sorted(fora.items()):
            lf = ci["onde"]["prefeitura"]["leis"]
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=pt")
            onde = pg.locator("section.onde-ver")
            otxt = await onde.inner_text() if await onde.count() else ""
            ok(f"fora ({tipo}) {ci['nome']}/{ci['uf']}: sem a seção de leis", await pg.locator("section[aria-labelledby='t-exec']").count() == 0)
            ok(f"fora ({tipo}): o motivo aparece em \"Onde ver mais\"", lf["motivo"][:60] in otxt, lf["motivo"][:60])
            link = onde.locator(f"a[href='{lf['url']}']")
            ok(f"fora ({tipo}): o link para conferir, com o rótulo", await link.count() == 1 and (lf.get("nome") or "")[:20] in await link.inner_text())
            dio = (((ci.get("onde") or {}).get("prefeitura") or {}).get("diarioOficial") or {}).get("url")
            if tipo == "diario" and dio and dio != lf["url"]:
                ok("fora (diario): o Diário não aparece duas vezes", await onde.locator(f"a[href='{dio}']").count() == 0)
            if tipo == "legislacao" and dio:
                ok("fora (legislacao): o Diário Oficial continua no quadro", await onde.locator(f"a[href='{dio}']").count() == 1)
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=en")
            otxt = await pg.locator("section.onde-ver").inner_text()
            ok(f"fora ({tipo}): motivo em inglês", lf["motivo_en"][:50] in otxt)
            r = await axe(pg)
            ok(f"fora ({tipo}): axe-core 0 problemas (inglês)", not r, ", ".join(r))
        ok("dados: há cidade fora com link nos dois tipos (Diário e página de leis)", set(fora) == {"diario", "legislacao"}, ", ".join(sorted(fora)))

        # 4. eleição suplementar: a conta juntaria as leis de quem governava antes, então não aparece
        if suplementar:
            ibge, ci = suplementar
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=pt")
            otxt = await pg.locator("section.onde-ver").inner_text()
            ok(f"suplementar {ci['nome']}/{ci['uf']}: sem a conta, e o quadro diz que as leis não estão aqui",
               await pg.locator("section[aria-labelledby='t-exec']").count() == 0 and "As leis que" in otxt)

        # 5. SAPL da Câmara com só os vetos (ou só as leis) + Diário Oficial: com a explicação de cada número separada
        # (notaLeis, notaVetos), o perfil junta as duas contas, com as duas fontes; sem ela, fica só a do SAPL
        if juncao:
            ibge, ci, sx = juncao
            ex = ci["prefeito"]["executivo"]
            de_leis = ex if sx.get("leisSancionadas") is None and ex.get("leisSancionadas") is not None else sx
            de_vetos = ex if sx.get("vetos") is None and ex.get("vetos") is not None else sx
            junta = bool(de_leis.get("notaLeis") and de_vetos.get("notaVetos"))
            await ir(pg, f"pessoa.html?id=pref-{ibge}&lang=pt")
            sec = pg.locator("section[aria-labelledby='t-exec']")
            txt = await sec.inner_text() if await sec.count() else ""
            leis = de_leis.get("leisSancionadas") if junta else sx.get("leisSancionadas")
            vetos = de_vetos.get("vetos") if junta else sx.get("vetos")
            ok(f"junção {ci['nome']}/{ci['uf']} ({'junta as duas contas' if junta else 'só o SAPL: falta a explicação separada'}): números certos",
               (leis is None or f"{leis:,}".replace(",", ".") + "\nleis sancionadas desde" in txt) and
               (vetos is None or f"{vetos:,}".replace(",", ".") + "\nvetos" in txt), f"leis {leis}, vetos {vetos}")
            det = sec.locator("details.como-contou")
            await det.locator("summary").click()
            como = await det.inner_text()
            esperado = (de_leis["notaLeis"] + " " + de_vetos["notaVetos"]) if junta else sx.get("nota") or ""
            ok("junção: \"Como contamos\" com a explicação de cada número, sem contradição", esperado[:200] in como and
               (not junta or "fica fora do perfil" not in como), como[:90].replace("\n", " "))
            if junta:
                await sec.locator("button.fontes-btn").click()
                await pg.wait_for_timeout(500)
                hrefs = await pg.locator(".janela-corpo a[href^='http']").evaluate_all("as => as.map(a => a.href)")
                urls = [f["url"] for f in [*(ex.get("fontes") or [ex.get("fonte")]), *(sx.get("fontes") or [sx.get("fonte")])] if f and f.get("url")]
                ok("junção: \"De onde veio isso?\" com as fontes das duas contas", all(any(u in h or h in u for h in hrefs) for u in urls), f"{len(hrefs)} links")
                await pg.keyboard.press("Escape")
        else:
            print("ℹ️ nenhuma cidade com o SAPL da Câmara e o Diário juntos nestes dados (a junção só é conferida com as Câmaras carregadas)")

        ok("sem erros de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
