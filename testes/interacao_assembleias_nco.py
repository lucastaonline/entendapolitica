"""Testes de interação das Assembleias do Norte e do Centro-Oeste (lista oficial, perfis com propostas, votações e gastos)
e do perfil dos governadores desses estados (projetos do Executivo, leis sancionadas e vetos).
Precisa do servidor em 8770 e dos dados gerados por scripts/legislativos.py (AM, AC, RO, RR, TO, PA, GO, MT, MS, AP).
Uso: python testes/interacao_assembleias_nco.py"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8771/
RAIZ = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
RES = []
UFS = ["AM", "AC", "RO", "RR", "TO", "PA", "GO", "MT", "MS", "AP"]


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def casa(uf):
    return json.loads((RAIZ / "dados" / "assembleias" / f"{uf}.json").read_text(encoding="utf-8"))


def com_extra(uf, campo):
    """Primeiro deputado da lista oficial que tem o campo no perfil (propostas, votacoes, gastos)."""
    for m in casa(uf)["membros"]:
        arq = RAIZ / "dados" / "pessoas" / f"{m['id']}.json"
        if arq.exists():
            p = json.loads(arq.read_text(encoding="utf-8"))
            if p.get(campo) and (campo != "propostas" or len(p[campo].get("lista") or []) > 25):
                return m
    return None


async def ir(pg, url):
    """Abre a página e espera a rede parar; se uma foto de site oficial demorar demais, segue com a página já montada."""
    try:
        await pg.goto(BASE + url, wait_until="networkidle", timeout=25000)
    except Exception:
        await pg.wait_for_timeout(1500)


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(f"{pg.url}: {e}"))

        # 1. página do estado: a lista oficial substitui a lista do TSE, com todos os nomes da Casa
        for uf in UFS:
            c = casa(uf)
            await ir(pg, f"estado.html?uf={uf}")
            await pg.wait_for_timeout(1200)
            n = await pg.locator('#casa-est a[href*="pessoa.html?id=dest-"]').count()
            aviso = await pg.locator("#estaduais").inner_text()
            ok(f"{uf}: lista oficial com {len(c['membros'])} nomes", n >= len(c["membros"]) and "Lista oficial" in aviso,
               f"{n} links; {c['sigla']}")

        # 2. perfil com propostas: filtros de autoria e de situação mudam a lista; link da fonte oficial
        m = com_extra("AM", "propostas")
        await ir(pg, f"pessoa.html?id={m['id']}")
        await pg.wait_for_timeout(1200)
        antes = await pg.locator("#contagem-prop").inner_text()
        ok("AM: perfil mostra as propostas", await pg.locator("#lista-prop li.prop").count() > 0, antes)
        chip = pg.locator("#status-chips button").first
        await chip.click()
        await pg.wait_for_timeout(400)
        depois = await pg.locator("#contagem-prop").inner_text()
        ok("filtro de situação muda a lista e fica marcado", depois != antes and await chip.get_attribute("aria-pressed") == "true", depois)
        links = await pg.locator('#lista-prop a[href^="https://sapl.al.am.leg.br/materia/"]').count()
        ok("cada proposta tem o link oficial (SAPL)", links > 0, f"{links} links")
        await pg.fill("#busca-prop", "título")
        await pg.wait_for_timeout(500)
        ok("busca nas propostas filtra", await pg.locator("#contagem-prop").inner_text() != depois)

        # 3. perfil com votações (AM, RO, GO, PA): a lista carrega do catálogo da Casa
        for uf in ["AM", "RO", "GO", "PA"]:
            m = com_extra(uf, "votacoes")
            await ir(pg, f"pessoa.html?id={m['id']}")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(2500)
            n = await pg.locator("#lista-votos li:not(.carregando):not(.vazio)").count()
            ok(f"{uf}: votações nominais aparecem no perfil", n > 0, f"{m['nome']}: {n} itens")

        # 4. perfil com gastos (MS: CEAP; GO: verba indenizatória)
        for uf in ["MS", "GO"]:
            m = com_extra(uf, "gastos")
            await ir(pg, f"pessoa.html?id={m['id']}")
            await pg.wait_for_timeout(1000)
            ok(f"{uf}: gastos aparecem no perfil", await pg.locator("#gastos .gasto").count() > 0, m["nome"])

        # 5. em inglês: o escopo das propostas vem traduzido e o perfil sem propostas mostra onde ver (sem "Coming soon")
        m = com_extra("RO", "propostas")
        await ir(pg, f"pessoa.html?id={m['id']}&lang=en")
        await pg.wait_for_timeout(1000)
        txt = await pg.locator("#propostas").inner_text()
        ok("RO em inglês: escopo das propostas em inglês", "Bills filed since February 1, 2023" in txt)
        m = casa("MT")["membros"][0]
        await ir(pg, f"pessoa.html?id={m['id']}&lang=en")
        await pg.wait_for_timeout(1000)
        corpo = await pg.locator("#perfil").inner_text()
        ok("MT em inglês: sem propostas, aparece 'Where to find more' (sem 'Coming soon') e o link oficial",
           "Coming soon" not in corpo and "Where to find more" in corpo
           and await pg.locator('#perfil a[href^="https://www.al.mt.gov.br/parlamento/deputados/"]').count() > 0)

        # 6. perfil do governador (dados/pessoas/gov-<UF>.json): projetos do Executivo, leis sancionadas e vetos; o que não
        # entra aparece em "Onde ver mais" (sem "Em breve")
        def num_pt(n):
            return f"{n:,}".replace(",", ".")
        for uf in UFS:
            arq = RAIZ / "dados" / "pessoas" / f"gov-{uf}.json"
            if not arq.exists():
                ok(f"gov-{uf}: arquivo do governador existe", False)
                continue
            gv = json.loads(arq.read_text(encoding="utf-8"))
            ex = gv.get("executivo") or {}
            await ir(pg, f"pessoa.html?id=gov-{uf}&lang=pt")
            await pg.wait_for_timeout(1200)
            corpo = " ".join((await pg.locator("#perfil").inner_text()).split())
            partes, info = [], []
            if gv.get("propostas"):
                n = await pg.locator("#lista-prop li.prop").count()
                partes.append(n > 0)
                info.append(f"{len(gv['propostas']['lista'])} projetos")
            if ex.get("leisSancionadas") is not None:
                partes.append(f"{num_pt(ex['leisSancionadas'])} leis sancionadas" in corpo)
                info.append(f"{ex['leisSancionadas']} leis")
            if ex.get("vetos") is not None:
                partes.append(f"{num_pt(ex['vetos'])} vetos" in corpo)
                info.append(f"{ex['vetos']} vetos")
            if not gv.get("propostas") or not ex:
                partes.append("Onde ver mais" in corpo)
            ok(f"gov-{uf}: o perfil mostra o que o governo fez", partes and all(partes) and "Em breve" not in corpo,
               ", ".join(info) or "só onde ver")
        await ir(pg, "pessoa.html?id=gov-MT&lang=pt")
        await pg.wait_for_timeout(1000)
        ok("gov-MT: 'Onde ver mais' leva ao Diário Oficial (Iomat)",
           await pg.locator('#perfil a[href^="https://www.iomat.mt.gov.br"]').count() > 0)
        await ir(pg, "pessoa.html?id=gov-TO&lang=en")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#propostas").inner_text()
        ok("gov-TO em inglês: escopo e nota das medidas provisórias em inglês",
           "Bills the state government sent" in txt and "Provisional measures (MPV)" in txt)
        await ir(pg, "pessoa.html?id=gov-AM&lang=pt")
        await pg.wait_for_timeout(1200)
        links = await pg.locator('#lista-prop a[href^="https://sapl.al.am.leg.br/materia/"]').count()
        ok("gov-AM: cada projeto do Executivo tem o link oficial (SAPL)", links > 0, f"{links} links")

        # 7. Amapá (e-Legis da Alap): perfis com propostas (filtros de autoria e de situação, link oficial de cada uma) e o
        # governador com os projetos do Executivo, "Leis sancionadas e vetos" e "Como contamos", com os números dos dados
        def perfil(pid):
            return json.loads((RAIZ / "dados" / "pessoas" / f"{pid}.json").read_text(encoding="utf-8"))

        async def com_link_oficial():
            """Quantas propostas mostradas têm o link da página oficial delas no e-Legis (sem contar o link do texto da lei)."""
            return await pg.evaluate("""() => [...document.querySelectorAll('#lista-prop li.prop')].filter(li =>
              [...li.querySelectorAll('a[href]')].some(a => /^https:\\/\\/elegis\\.al\\.ap\\.leg\\.br\\/portal\\/proposicao\\/\\d+$/.test(a.href))).length""")
        com_prop = [m for m in casa("AP")["membros"] if (RAIZ / "dados" / "pessoas" / f"{m['id']}.json").exists()
                    and len((perfil(m["id"]).get("propostas") or {}).get("lista") or []) > 0]
        com_prop.sort(key=lambda m: -len(perfil(m["id"])["propostas"]["lista"]))
        ok("AP: deputados com propostas do e-Legis", len(com_prop) >= 20, f"{len(com_prop)} de {len(casa('AP')['membros'])}")
        coautor = next((m for m in com_prop[1:] if any(x["papel"] == "coautor" for x in perfil(m["id"])["propostas"]["lista"])), None)
        for m in [com_prop[0], coautor or com_prop[1]]:
            lista = perfil(m["id"])["propostas"]["lista"]
            n_aut = sum(1 for x in lista if x["papel"] == "autor")
            n_co = len(lista) - n_aut
            await ir(pg, f"pessoa.html?id={m['id']}&lang=pt")
            await pg.wait_for_timeout(1200)
            cont = " ".join((await pg.locator("#contagem-prop").inner_text()).split())
            vis = await pg.locator("#lista-prop li.prop").count()
            links = await com_link_oficial()
            botoes = [" ".join((await pg.locator(f'[data-papel="{p}"] b').inner_text()).split()) for p in ("autor", "coautor")]
            ok(f"AP {m['nome']}: propostas na tela iguais aos dados ({n_aut} como autor, {n_co} junto)",
               f"de {num_pt(n_aut if n_aut else n_co)} proposta" in cont and botoes == [num_pt(n_aut), num_pt(n_co)], cont)
            ok(f"AP {m['nome']}: cada proposta mostrada tem o link oficial do e-Legis", vis > 0 and links == vis, f"{links}/{vis}")
            if n_co and n_aut:
                await pg.locator('[data-papel="coautor"]').click()
                await pg.wait_for_timeout(400)
                cont2 = " ".join((await pg.locator("#contagem-prop").inner_text()).split())
                ok(f"AP {m['nome']}: filtro \"Assinou junto\" mostra as {n_co} em que assinou junto",
                   f"de {num_pt(n_co)} proposta" in cont2 and await pg.locator('[data-papel="coautor"]').get_attribute("aria-pressed") == "true", cont2)
                await pg.locator('[data-papel="autor"]').click()
                await pg.wait_for_timeout(400)
            chip = pg.locator("#status-chips button").first
            st = await chip.get_attribute("data-status")
            await chip.click()
            await pg.wait_for_timeout(400)
            n_st = sum(1 for x in lista if x["papel"] == ("autor" if n_aut else "coautor") and x["status"] == st)
            cont3 = " ".join((await pg.locator("#contagem-prop").inner_text()).split())
            ok(f"AP {m['nome']}: filtro de situação \"{st}\" ({n_st}) muda a lista e fica marcado",
               f"de {num_pt(n_st)} proposta" in cont3 and await chip.get_attribute("aria-pressed") == "true", cont3)
        gv = perfil("gov-AP")
        ex = gv.get("executivo") or {}
        for lang in ("pt", "en"):
            await ir(pg, f"pessoa.html?id=gov-AP&lang={lang}")
            await pg.wait_for_timeout(1300)
            corpo = " ".join((await pg.locator("#perfil").inner_text()).split())
            n_proj = len(gv["propostas"]["lista"])
            cont = " ".join((await pg.locator("#contagem-prop").inner_text()).split())
            de_n = (f"de {num_pt(n_proj)} proposta" if lang == "pt" else f"of {n_proj:,} proposal")
            ok(f"gov-AP ({lang}): projetos do Executivo iguais aos dados ({n_proj})", de_n in cont, cont)
            vis = await pg.locator("#lista-prop li.prop").count()
            links = await com_link_oficial()
            ok(f"gov-AP ({lang}): cada projeto mostrado tem o link oficial do e-Legis", vis > 0 and links == vis, f"{links}/{vis}")
            leis_link = await pg.locator('#lista-prop a[href$="/texto-integral"]').count()
            ok(f"gov-AP ({lang}): os projetos que viraram lei têm o link do texto da lei", leis_link > 0, f"{leis_link} links")
            tit = "Leis sancionadas e vetos" if lang == "pt" else "Laws signed and vetoes"
            nums = []
            if ex.get("leisSancionadas") is not None:
                nums.append((f"{num_pt(ex['leisSancionadas'])} leis sancionadas" if lang == "pt"
                             else f"{ex['leisSancionadas']:,} laws signed") in corpo)
            if ex.get("vetos") is not None:
                if lang == "pt":
                    nums.append(f"{num_pt(ex['vetos'])} vetos" in corpo)
                    if ex.get("vetosTotais") is not None:
                        nums.append(f"{num_pt(ex['vetosTotais'])} totais e {num_pt(ex['vetosParciais'])} parciais" in corpo)
                else:
                    nums.append(f"{ex['vetos']:,} vetoes" in corpo)
            if ex.get("leisPromulgadasPelaCasa"):
                nums.append((f"{num_pt(ex['leisPromulgadasPelaCasa'])} leis promulgadas" if lang == "pt"
                             else f"{ex['leisPromulgadasPelaCasa']:,} laws promulgated") in corpo)
            ok(f"gov-AP ({lang}): \"{tit}\" com os números dos dados", tit in corpo and nums and all(nums),
               f"{ex.get('leisSancionadas')} leis, {ex.get('vetos')} vetos")
            como = pg.locator("details.como-contou")
            await como.locator("summary").click()
            await pg.wait_for_timeout(300)
            txt = " ".join((await como.locator("p").inner_text()).split())
            nota = " ".join((ex.get("nota") if lang == "pt" else ex.get("nota_en") or "").split())
            ok(f"gov-AP ({lang}): \"{'Como contamos' if lang == 'pt' else 'How we counted'}\" abre e é a nota dos dados "
               "(leis + vetos)", await como.get_attribute("open") is not None and txt == nota
               and nota == " ".join(f"{ex.get('notaLeis' + ('' if lang == 'pt' else '_en'))} {ex.get('notaVetos' + ('' if lang == 'pt' else '_en'))}".split()),
               txt[:90])
            ok(f"gov-AP ({lang}): sem \"Em breve\" e sem \"Onde ver mais\" (tudo entrou)",
               "Em breve" not in corpo and "Coming soon" not in corpo and "Onde ver mais" not in corpo and "Where to find more" not in corpo)
        m = com_prop[0]
        await ir(pg, f"pessoa.html?id={m['id']}&lang=en")
        await pg.wait_for_timeout(1000)
        txt = await pg.locator("#propostas").inner_text()
        ok("AP em inglês: escopo das propostas em inglês", "Bills filed since February 1, 2023" in txt)
        # celular de 320 px: sem rolar para os lados (página do estado, governador e dois deputados com propostas)
        ctx2 = await nav.new_context(viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True)
        pg2 = await ctx2.new_page()
        for url in ["estado.html?uf=AP", "pessoa.html?id=gov-AP", f"pessoa.html?id={com_prop[0]['id']}",
                    f"pessoa.html?id={(coautor or com_prop[1])['id']}"]:
            for lang in ("pt", "en"):
                try:
                    await pg2.goto(BASE + url + f"&lang={lang}", wait_until="networkidle", timeout=25000)
                except Exception:
                    await pg2.wait_for_timeout(1500)
                await pg2.wait_for_timeout(1200)
                larg = await pg2.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
                ok(f"320 px sem rolar para os lados: {url} ({lang})", larg[0] <= larg[1] + 1, str(larg))
        await ctx2.close()

        ok("sem erros de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
