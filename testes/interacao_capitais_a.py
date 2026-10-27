"""Testes de interação da frente capitais-a-r6 (Vitória, Teresina, Cuiabá e Goiânia): propostas dos vereadores e da
prefeitura lidas no Processo Legislativo Eletrônico das Câmaras (Ágape), a verba de atividade parlamentar de Teresina, a
cota (CEAP) de Goiânia, o quadro da Câmara na página da cidade, inglês e celular de 320 px. Playwright + Edge, com o
servidor em 8770 e os dados gerados (python scripts/legislativos.py 3205309 2211001 5103403 5208707;
python scripts/montar.py).
Uso: python testes/interacao_capitais_a.py [IBGE ...]   (sem códigos: as quatro cidades)"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
# cidade -> (UF, padrão do link oficial de cada proposta)
AGAPE = {
    "3205309": ("ES", r"^https://camarasempapel\.cmv\.es\.gov\.br/spl/processo\.aspx\?id=\d+$"),
    "2211001": ("PI", r"^https://teresina\.camarasempapel\.com\.br/spl/processo\.aspx\?id=\d+$"),
    "5103403": ("MT", r"^https://legislativo\.camaracuiaba\.mt\.gov\.br/spl/processo\.aspx\?id=\d+$"),
}
NOTA_PT, NOTA_EN = "Processo Legislativo Eletrônico", "Processo Legislativo Eletrônico"
SO = [a for a in sys.argv[1:] if a.isdigit()] or list(AGAPE) + ["5208707"]
PROMESSA = re.compile(r"ainda não|em breve|por enquanto|not yet|coming soon", re.I)


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def ler(arq):
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def casa(ibge):
    return ler(RAIZ / "dados" / "camaras" / f"{ibge}.json") or {}


def extras(ibge):
    return (ler(RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json") or {}).get("pessoas") or {}


def cidade(ibge, uf):
    return ler(RAIZ / "dados" / "cidades" / uf / f"{ibge}.json") or {}


def marcados(ibge, uf):
    return {m["id"] for m in (cidade(ibge, uf).get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}


def vereador_com_propostas(ibge, uf):
    """O vereador com mais propostas (com autor e coautor), já marcado pelo montar.py ("extras": "cidade")."""
    ms = marcados(ibge, uf)
    cands = []
    for pid, x in extras(ibge).items():
        r = (x.get("propostas") or {}).get("resumo") or {}
        if pid in ms and r.get("autor") and r.get("coautor"):
            cands.append((r["total"], pid))
    return max(cands)[1] if cands else None


def sem_nbsp(t):
    return t.replace("\u00a0", " ").replace("\u202f", " ")


def num(v):
    return f"{v:,}".replace(",", ".")


def reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def curto(v):
    """EP.dinheiroCurto em português."""
    a = abs(v)
    if a >= 1e6:
        return "R$ " + f"{v / 1e6:.1f}".replace(".", ",") + (" milhão" if a < 2e6 else " milhões")
    if a >= 1e4:
        return "R$ " + num(round(v / 1e3)) + " mil"
    return reais(v)


async def sem_rolagem_lateral(pg):
    return await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


async def abrir(pg, url, espera=1200):
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(espera)


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        cel = await nav.new_context(viewport={"width": 320, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pc = await cel.new_page()
        pc.on("pageerror", lambda e: erros.append(str(e)))

        for ibge, (uf, padrao) in AGAPE.items():
            if ibge in SO:
                await cidade_agape(pg, pc, ibge, uf, padrao)
        if "2211001" in SO:
            await gastos(pg, pc, "2211001", "PI", "Teresina", por_tipo=False)
        if "5208707" in SO:
            await goiania(pg, pc)

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


async def cidade_agape(pg, pc, ibge, uf, padrao):
    k = casa(ibge)
    nome = k.get("casa", ibge)
    ok(f"{nome}: o arquivo da Câmara marca as propostas e tem o escopo nos dois idiomas",
       (k.get("cobertura") or {}).get("propostas") and k.get("escopoPropostas") and k.get("escopoPropostas_en"))
    ok(f"{nome}: nenhuma nota com promessa (\"ainda não\", \"em breve\"...)",
       not any(PROMESSA.search(n) for n in (k.get("notas") or []) + (k.get("notas_en") or [])))
    ok(f"{nome}: a nota antiga \"As propostas ... não entram\" saiu",
       not any(re.search(r"propostas dos vereadores não entram|proposições só em páginas", n) for n in k.get("notas") or []))
    ok(f"{nome}: notas em português e em inglês, uma para uma", len(k.get("notas") or []) == len(k.get("notas_en") or []))

    # 1. página da cidade: a lista oficial e o quadro da Câmara (cobertura e notas)
    v = cidade(ibge, uf).get("vereadores") or {}
    await abrir(pg, f"cidade.html?ibge={ibge}&lang=pt", 1000)
    n = await pg.locator("#casa-ver .pessoa-card").count()
    ok(f"{nome}: a página da cidade mostra a lista oficial", v.get("oficial") and n == len(v.get("membros") or []), f"{n} cartões")
    info = sem_nbsp(await pg.locator(".info-casa").first.inner_text())
    ok(f"{nome}: o quadro da Câmara marca \"O que cada um propôs\" e mostra a nota da fonte",
       await pg.locator(".info-casa li.tem", has_text="O que cada um propôs").count() == 1 and NOTA_PT in info, info[:90])

    # 2. perfil do vereador com mais propostas: números da página = dados, filtros e link oficial
    pid = vereador_com_propostas(ibge, uf)
    ok(f"{nome}: há um vereador com propostas como autor e coautor, já juntado pelo montar", pid)
    if not pid:
        return
    b = extras(ibge)[pid]["propostas"]
    lista = b["lista"]
    ok(f"{nome}: o resumo das propostas bate com a lista ({b['resumo']['total']})",
       b["resumo"]["total"] == len(lista) and b["resumo"]["autor"] == sum(1 for x in lista if x["papel"] == "autor"))
    ok(f"{nome}: só os tipos da lista comum (PL, PLP, PELO, PDL, PRC)", all(x["tipo"] in ("PL", "PLP", "PELO", "PDL", "PRC") for x in lista))
    ok(f"{nome}: os ids seguem o padrão cm{ibge}:<ID oficial>", all(re.fullmatch(rf"cm{ibge}:\d+", x["id"]) for x in lista))
    await abrir(pg, f"pessoa.html?id={pid}&lang=pt")
    n_aut = sum(1 for x in lista if x["papel"] == "autor")
    n_co = len(lista) - n_aut
    botoes = await pg.locator("#propostas button[data-papel]").all_inner_texts()
    ok(f"{nome}: os botões de autoria têm os números dos dados ({n_aut} e {n_co})",
       len(botoes) == 2 and botoes[0].startswith(num(n_aut)) and botoes[1].startswith(num(n_co)),
       " | ".join(x.split("\n")[0] for x in botoes))
    cont = await pg.locator("#contagem-prop").inner_text()
    ok(f"{nome}: a contagem da lista é a dos dados", f"de {num(n_aut)}" in cont, cont)
    chip = pg.locator("#status-chips button[data-status]").first
    st = await chip.get_attribute("data-status")
    await chip.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(500)
    cont2 = await pg.locator("#contagem-prop").inner_text()
    esperado = sum(1 for x in lista if x["papel"] == "autor" and x["status"] == st)
    ok(f"{nome}: o filtro \"{st}\" (teclado) mostra o número dos dados ({esperado})", f"de {num(esperado)}" in cont2, cont2)
    await chip.focus()
    await pg.keyboard.press("Enter")
    co = pg.locator("#propostas button[data-papel='coautor']")
    await co.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(500)
    cont3 = await pg.locator("#contagem-prop").inner_text()
    ok(f"{nome}: \"Assinou junto\" mostra as {n_co} em que assinou junto", f"de {num(n_co)}" in cont3, cont3)
    hrefs = await pg.locator("#lista-prop li.prop a.fora, #lista-prop li.prop a[target=_blank]").evaluate_all("els => els.map(e => e.href)")
    oficiais = [h for h in hrefs if re.search(padrao, h)]
    ok(f"{nome}: cada proposta tem o link da página oficial", len(oficiais) >= min(20, n_co), f"{len(oficiais)} links")
    primeira = next(x for x in lista if x["papel"] == "coautor")
    t0 = await pg.locator("#lista-prop li.prop").first.inner_text()
    ok(f"{nome}: a primeira proposta da lista é a dos dados ({primeira['sigla']})", primeira["sigla"] in t0, t0[:80].replace("\n", " "))
    lei = next((x for x in lista if x["papel"] == "autor" and x.get("lei") and x["lei"].get("url")), None)
    if lei:
        await pg.locator("#propostas button[data-papel='autor']").click()
        await pg.locator("#status-chips button[data-status='lei']").click()
        await pg.wait_for_timeout(500)
        ok(f"{nome}: a proposta que virou lei leva ao texto da norma ({lei['lei']['nome']})",
           await pg.locator(f'#lista-prop a[href="{lei["lei"]["url"]}"]').count() >= 1)

    # 3. em inglês: escopo, situações e nota da Câmara
    await abrir(pg, f"pessoa.html?id={pid}&lang=en")
    esc = await pg.locator("#propostas > p.muted").first.inner_text()
    ok(f"{nome}: escopo das propostas em inglês", b["escopo_en"][:50] in esc, esc[:80])
    sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
    pt = [s for s in sts if re.search(r"Ainda|Aprovada|Arquivada|Virou|prefeito|Câmara|Rejeitada|desistiu|prejudicada", s)]
    ok(f"{nome}: situações em inglês", sts and not pt, " | ".join(pt[:3]))
    await abrir(pg, f"cidade.html?ibge={ibge}&lang=en", 1000)
    info = sem_nbsp(await pg.locator(".info-casa").first.inner_text())
    ok(f"{nome}: o quadro da Câmara em inglês, com a nota da fonte", NOTA_EN in info and "What each member proposed" in info)

    # 4. o prefeito: os projetos que mandou à Câmara
    pref = cidade(ibge, uf).get("prefeito") or {}
    bp = (extras(ibge).get(pref.get("id")) or {}).get("propostas")
    ok(f"{nome}: o prefeito tem os projetos que mandou à Câmara", bp and bp["resumo"]["total"] > 0 and
       all(x["papel"] == "autor" for x in bp["lista"]), bp and bp["resumo"]["total"])
    if bp:
        await abrir(pg, f"pessoa.html?id={pref['id']}&lang=pt")
        corpo = await pg.locator("#perfil").inner_text()
        n_l = await pg.locator("#lista-prop li.prop").count()
        ok(f"{nome}: a página do prefeito mostra os projetos ({bp['resumo']['total']})",
           n_l == min(20, bp["resumo"]["total"]) and "Projetos que a prefeitura mandou" in corpo, f"{n_l} na tela")
        hrefs = await pg.locator("#lista-prop li.prop a.fora, #lista-prop li.prop a[target=_blank]").evaluate_all("els => els.map(e => e.href)")
        ok(f"{nome}: os projetos do prefeito levam à página oficial", any(re.search(padrao, h) for h in hrefs))
        await abrir(pg, f"pessoa.html?id={pref['id']}&lang=en", 1000)
        ok(f"{nome}: o prefeito em inglês", "mayor's office sent" in await pg.locator("#propostas").inner_text())

    # 5. celular de 320 px: sem rolar para os lados (cidade e perfil)
    for url in (f"cidade.html?ibge={ibge}&lang=pt", f"pessoa.html?id={pid}&lang=pt", f"pessoa.html?id={pid}&lang=en"):
        await abrir(pc, url, 800)
        ok(f"{nome}: 320 px sem rolar para os lados ({url.split('?')[0]}, {url[-2:]})", await sem_rolagem_lateral(pc))


async def gastos(pg, pc, ibge, uf, rotulo, por_tipo):
    """Os gastos do vereador que mais gastou no ano: os números da página = dados, em português e em inglês, e 320 px."""
    ex = extras(ibge)
    ms = marcados(ibge, uf)
    cands = [(x["gastos"]["total"], pid) for pid, x in ex.items() if pid in ms and (x.get("gastos") or {}).get("total")]
    ok(f"{rotulo}: vereadores com gastos", len(cands) >= len(ms) - 3, f"{len(cands)} de {len(ms)}")
    if not cands:
        return
    pid = max(cands)[1]
    g = ex[pid]["gastos"]
    await abrir(pg, f"pessoa.html?id={pid}&lang=pt", 600)
    await pg.locator("#gastos").scroll_into_view_if_needed()
    await pg.wait_for_timeout(900)
    gs = sem_nbsp(await pg.locator("#gastos").inner_text())
    ok(f"{rotulo}: o total do ano na página é o dos dados ({curto(g['total'])})", curto(g["total"]) in gs, gs[:160].replace("\n", " "))
    ok(f"{rotulo}: o total desde o começo do mandato ({curto(g['mandatoTotal'])})", curto(g["mandatoTotal"]) in gs)
    ok(f"{rotulo}: o nome da verba aparece", g["nome"] in gs and "Gastos do mandato" in gs)
    if por_tipo:
        ok(f"{rotulo}: um item para cada tipo de gasto (até 8), com o valor dos dados ({reais(g['porTipo'][0]['valor'])})",
           await pg.locator("#gastos li.gasto").count() == min(8, len(g["porTipo"])) and reais(g["porTipo"][0]["valor"]) in gs)
        ok(f"{rotulo}: o total do ano é a soma dos tipos", abs(sum(t["valor"] for t in g["porTipo"]) - g["total"]) < 0.01)
    else:
        ok(f"{rotulo}: a página diz que a Câmara não separa os gastos por tipo", "não separa estes gastos por tipo" in gs)
    await abrir(pg, f"pessoa.html?id={pid}&lang=en", 600)
    await pg.locator("#gastos").scroll_into_view_if_needed()
    await pg.wait_for_timeout(900)
    gs = await pg.locator("#gastos").inner_text()
    ok(f"{rotulo}: gastos em inglês", "Office spending" in gs and g["nome_en"] in gs)
    await abrir(pc, f"pessoa.html?id={pid}&lang=pt", 600)
    await pc.locator("#gastos").scroll_into_view_if_needed()
    await pc.wait_for_timeout(800)
    ok(f"{rotulo}: perfil com gastos em 320 px sem rolar para os lados", await sem_rolagem_lateral(pc))


async def goiania(pg, pc):
    k = casa("5208707")
    notas = k.get("notas") or []
    ok("Goiânia: sem propostas, com o motivo (robots.txt do SUAP) em pt e en", not (k.get("cobertura") or {}).get("propostas")
       and any("robots.txt" in n and "SUAP" in n for n in notas) and any("robots.txt" in n for n in k.get("notas_en") or []))
    ok("Goiânia: gastos marcados e explicados (CEAP)", (k.get("cobertura") or {}).get("gastos") and any("CEAP" in n for n in notas))
    ok("Goiânia: nenhuma nota com promessa", not any(PROMESSA.search(n) for n in notas + (k.get("notas_en") or [])))
    await abrir(pg, "cidade.html?ibge=5208707&lang=pt", 1000)
    info = sem_nbsp(await pg.locator(".info-casa").first.inner_text())
    ok("Goiânia: o quadro da Câmara marca os gastos e mostra a nota do SUAP", "SUAP" in info and
       await pg.locator(".info-casa li.tem", has_text="Gastos com a verba do mandato").count() == 1, info[:90])
    await gastos(pg, pc, "5208707", "GO", "Goiânia", por_tipo=True)
    await abrir(pc, "cidade.html?ibge=5208707&lang=pt", 800)
    ok("Goiânia: página da cidade em 320 px sem rolar para os lados", await sem_rolagem_lateral(pc))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
