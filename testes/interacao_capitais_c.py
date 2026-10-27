"""Testes de interação da frente capitais-c-r6 (Recife, Salvador, Belém e João Pessoa), com Playwright + Edge: propostas dos
vereadores (números da página = dados, filtros, link oficial), o prefeito (projetos que mandou à Câmara), o quadro da Câmara
na página da cidade (cobertura e notas), os gastos de João Pessoa, a versão em inglês e o celular de 320 px sem rolar para os
lados; em Recife, as votações continuam aparecendo.
Precisa do servidor em 8770 e dos dados gerados (python scripts/legislativos.py 2611606 2927408 1501402 2507507; python
scripts/montar.py). Só olha o que o montar.py já juntou à página da cidade.
Uso: python testes/interacao_capitais_c.py"""
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
CIDADES = {"2611606": ("PE", "Recife"), "2927408": ("BA", "Salvador"), "1501402": ("PA", "Belém"), "2507507": ("PB", "João Pessoa")}
PT_SOLTO = ("Ainda", "Aprovada", "Arquivada", "Virou", "prefeito", "Câmara", "Situação", "publica")


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def ler(arq):
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def casa(ibge):
    return ler(RAIZ / "dados" / "camaras" / f"{ibge}.json") or {}


def extras(ibge):
    return (ler(RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json") or {}).get("pessoas") or {}


def cidade(ibge):
    uf = CIDADES[ibge][0]
    return ler(RAIZ / "dados" / "cidades" / uf / f"{ibge}.json") or {}


def marcados(ibge):
    c = cidade(ibge)
    return {m["id"] for m in (c.get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}


def mais_propostas(ibge):
    """O vereador (já marcado pelo montar.py) com mais propostas como autor principal."""
    ex, mk = extras(ibge), marcados(ibge)
    cands = [(sum(1 for x in (p.get("propostas") or {}).get("lista") or [] if x["papel"] == "autor"), pid)
             for pid, p in ex.items() if pid.startswith("ver-") and pid in mk and (p.get("propostas") or {}).get("lista")]
    return max(cands)[1] if cands else None


def com_coautor(ibge):
    ex, mk = extras(ibge), marcados(ibge)
    cands = [(sum(1 for x in (p.get("propostas") or {}).get("lista") or [] if x["papel"] == "coautor"), pid)
             for pid, p in ex.items() if pid.startswith("ver-") and pid in mk]
    c = max(cands) if cands else (0, None)
    return c[1] if c[0] else None


async def sem_rolagem(pg):
    return await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


async def propostas_vereador(pg, ibge, pid):
    nome = CIDADES[ibge][1]
    p = extras(ibge)[pid]
    lista = p["propostas"]["lista"]
    n_aut = sum(1 for x in lista if x["papel"] == "autor")
    n_co = len(lista) - n_aut
    await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    ok(f"{nome}: o perfil mostra as propostas", await pg.locator("#propostas").count() == 1)
    bts = await pg.locator(".papel-btn b").all_inner_texts()
    ok(f"{nome}: autor principal e \"assinou junto\" = dados ({n_aut} e {n_co})",
       [int(re.sub(r"\D", "", b) or 0) for b in bts] == [n_aut, n_co], " / ".join(bts))
    cont = await pg.locator("#contagem-prop").inner_text()
    padrao = n_aut if n_aut else n_co
    ok(f"{nome}: a contagem da lista = dados", f"de {padrao:,}".replace(",", ".") in cont, cont)
    autor = sorted([x for x in lista if x["papel"] == ("autor" if n_aut else "coautor")],
                   key=lambda x: (x.get("data") or "", x.get("id") or ""), reverse=True)
    sig0 = await pg.locator("#lista-prop .sigla").first.inner_text()
    ok(f"{nome}: a proposta mais nova vem primeiro ({autor[0]['sigla']})", sig0.strip() == autor[0]["sigla"], sig0)
    url0 = autor[0]["url"]
    ok(f"{nome}: cada proposta leva ao site oficial", await pg.locator(f'#lista-prop a[href="{url0}"]').count() >= 1, url0)
    if p["propostas"].get("nota"):
        aviso = await pg.locator("#propostas .aviso").all_inner_texts()
        ok(f"{nome}: a nota do bloco de propostas aparece (por que a situação fica sem classificar)",
           any(p["propostas"]["nota"][:60] in a for a in aviso), " | ".join(aviso)[:100])
    st0 = await pg.locator("#lista-prop .status-txt").first.inner_text()
    esperado = autor[0].get("statusTxt") or ""
    ok(f"{nome}: a situação da proposta mais nova = dados", esperado[:30] in st0, st0[:80])
    chips = pg.locator("#status-chips button[data-status]")
    if await chips.count() > 1:
        c0 = await pg.locator("#contagem-prop").inner_text()
        ch = chips.nth(1)
        st = await ch.get_attribute("data-status")
        q = int(re.sub(r"\D", "", await ch.locator(".q").inner_text()) or 0)
        await ch.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        c1 = await pg.locator("#contagem-prop").inner_text()
        n_st = sum(1 for x in lista if x["papel"] == ("autor" if n_aut else "coautor") and x["status"] == st)
        ok(f"{nome}: filtro de situação ({st}) pelo teclado: {q} = dados ({n_st}), com o foco no botão",
           q == n_st and c0 != c1 and await pg.evaluate("document.activeElement.hasAttribute('data-status')"), c1)
    # inglês
    await pg.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
    pt = [s for s in sts if any(w in s for w in PT_SOLTO)]
    ok(f"{nome}: situações em inglês", sts and not pt, " | ".join(pt[:2]))
    esc = await pg.locator("#propostas > p.muted").first.inner_text()
    ok(f"{nome}: escopo das propostas em inglês", "filed since January 1, 2025" in esc, esc[:90])
    if p["propostas"].get("nota_en"):
        aviso = await pg.locator("#propostas .aviso").all_inner_texts()
        ok(f"{nome}: a nota do bloco de propostas em inglês", any(p["propostas"]["nota_en"][:60] in a for a in aviso),
           " | ".join(aviso)[:100])
    return p


async def main():
    async with async_playwright() as pw:
        nav = await pw.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        cel = await nav.new_context(viewport={"width": 320, "height": 700}, is_mobile=True)
        pc = await cel.new_page()
        pc.on("pageerror", lambda e: erros.append(str(e)))

        for ibge, (uf, nome) in CIDADES.items():
            k = casa(ibge)
            # 1. o quadro da Câmara na página da cidade: cobertura e notas (pt e en)
            await pg.goto(BASE + f"cidade.html?ibge={ibge}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1200)
            cob = k.get("cobertura") or {}
            itens = pg.locator(".info-casa .cobertura-casa li")
            classes = [await itens.nth(i).get_attribute("class") for i in range(await itens.count())]
            esperado = ["tem" if cob.get(c) else "falta" for c in ("lista", "propostas", "votacoes", "gastos")]
            ok(f"{nome}: o quadro da Câmara mostra a cobertura dos dados ({', '.join(c for c in cob if cob[c])})",
               classes == esperado, f"{classes}")
            notas = await pg.locator(".info-casa .notas-casa li").all_inner_texts()
            ok(f"{nome}: as notas da Câmara = dados ({len(k.get('notas') or [])})",
               [n.strip() for n in notas] == [n.strip() for n in k.get("notas") or []], f"{len(notas)}")
            corpo = await pg.locator("#cidade").inner_text()
            ok(f"{nome}: nada de \"Em breve\"/\"ainda não\" na página da cidade", not re.search(r"Em breve|ainda não", corpo))
            await pg.goto(BASE + f"cidade.html?ibge={ibge}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            notas_en = await pg.locator(".info-casa .notas-casa li").all_inner_texts()
            ok(f"{nome}: as notas em inglês", [n.strip() for n in notas_en] == [n.strip() for n in k.get("notas_en") or []])

            # 2. um vereador com propostas
            if ibge != "2507507":
                pid = mais_propostas(ibge)
                ok(f"{nome}: há um vereador com propostas (já juntado pelo montar)", pid)
                if pid:
                    await propostas_vereador(pg, ibge, pid)
                    pc_url = BASE + f"pessoa.html?id={pid}&lang=pt"
                    await pc.goto(pc_url, wait_until="networkidle")
                    await pc.wait_for_timeout(1000)
                    ok(f"{nome}: perfil do vereador a 320 px sem rolar para os lados", await sem_rolagem(pc))
                co = com_coautor(ibge)
                if co:
                    await pg.goto(BASE + f"pessoa.html?id={co}&lang=pt", wait_until="networkidle")
                    await pg.wait_for_timeout(1000)
                    b = pg.locator('.papel-btn[data-papel="coautor"]')
                    await b.focus()
                    await pg.keyboard.press("Enter")
                    await pg.wait_for_timeout(500)
                    n_co = sum(1 for x in extras(ibge)[co]["propostas"]["lista"] if x["papel"] == "coautor")
                    cont = await pg.locator("#contagem-prop").inner_text()
                    ok(f"{nome}: \"Assinou junto\" pelo teclado mostra as {n_co} como coautor", f"de {n_co:,}".replace(",", ".") in cont, cont)

            # 3. o prefeito
            pref = (cidade(ibge).get("prefeito") or {})
            pp = extras(ibge).get(pref.get("id") or "") or {}
            await pg.goto(BASE + f"pessoa.html?id={pref.get('id')}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1200)
            corpo = await pg.locator("#perfil").inner_text()
            if pp.get("propostas"):
                n = len(pp["propostas"]["lista"])
                d = int(re.sub(r"\D", "", await pg.locator("#funil .d1 .q").inner_text()) or 0)
                ok(f"{nome}: o prefeito mostra os {n} projetos que mandou à Câmara", d == n and "O que " in corpo, f"{d}")
                await pg.goto(BASE + f"pessoa.html?id={pref.get('id')}&lang=en", wait_until="networkidle")
                await pg.wait_for_timeout(1000)
                ok(f"{nome}: o prefeito em inglês (escopo)", "mayor's office sent" in await pg.locator("#propostas").inner_text())
            elif ibge != "2507507":
                nota = next((n for n in k.get("notas") or [] if re.search(r"prefeit|executivo", n, re.I)), None)
                ok(f"{nome}: sem projetos do prefeito, o motivo aparece em \"Onde ver mais\"",
                   nota and "Onde ver mais" in corpo and nota[:50] in corpo and "Em breve" not in corpo)

        # 4. Recife: as votações nominais continuam no perfil (o mesmo vereador pode ter propostas e votos)
        ex = extras("2611606")
        mk = marcados("2611606")
        cand = [(len(p["votacoes"]["votos"]), pid) for pid, p in ex.items() if pid in mk and (p.get("votacoes") or {}).get("votos")
                and (p.get("propostas") or {}).get("lista")]
        ok("Recife: há um vereador com propostas e votações", cand)
        if cand:
            pid = max(cand)[1]
            vv = ex[pid]["votacoes"]
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            leg = await pg.locator("#votacoes .legenda-votos").inner_text()
            ok(f"Recife: o resumo dos votos = dados (total {vv['resumo']['total']})", f"Total: {vv['resumo']['total']}" in leg.replace(".", ""))
            ok("Recife: as votações e as propostas aparecem juntas no perfil",
               await pg.locator("#lista-votos > li").count() > 0 and await pg.locator("#lista-prop li.prop").count() > 0)

        # 5. João Pessoa: os gastos do mandato (só os totais: a tabela da Câmara tem um valor por mês)
        ex = extras("2507507")
        mk = marcados("2507507")
        cand = sorted((p["gastos"]["mandatoTotal"], pid) for pid, p in ex.items() if pid in mk and p.get("gastos"))
        if casa("2507507").get("cobertura", {}).get("gastos"):
            ok("João Pessoa: há vereadores com gastos", cand)
            pid = cand[-1][1]
            g = ex[pid]["gastos"]
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pg.locator("#gastos").scroll_into_view_if_needed()
            await pg.wait_for_timeout(800)
            gs = (await pg.locator("#gastos").inner_text()).replace("\u00a0", " ")
            ok("João Pessoa: gastos do mandato com o que entra e a nota de que só há totais",
               "Gastos do mandato" in gs and g["nome"] in gs and "não separa estes gastos por tipo" in gs, gs.replace("\n", " ")[:120])
            mil = round(g["total"] / 1000)
            ok(f"João Pessoa: o total do ano ({g['total']:.2f}) aparece", f"{mil}" in re.sub(r"\D", " ", gs), gs[:80])
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
            await pg.locator("#gastos").scroll_into_view_if_needed()
            await pg.wait_for_timeout(800)
            gs = await pg.locator("#gastos").inner_text()
            ok("João Pessoa: gastos em inglês", "Office spending" in gs and g["nome_en"] in gs and "only the totals" in gs)
            await pc.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
            await pc.wait_for_timeout(800)
            ok("João Pessoa: perfil com gastos a 320 px sem rolar para os lados", await sem_rolagem(pc))
        else:
            ok("João Pessoa: sem gastos no site, a nota da Câmara diz por quê",
               any("gastos" in n for n in casa("2507507").get("notas") or []))

        # 6. 320 px: páginas das cidades em inglês
        for ibge, (uf, nome) in CIDADES.items():
            await pc.goto(BASE + f"cidade.html?ibge={ibge}&lang=en", wait_until="networkidle")
            await pc.wait_for_timeout(800)
            ok(f"{nome}: página da cidade a 320 px sem rolar para os lados", await sem_rolagem(pc))

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
