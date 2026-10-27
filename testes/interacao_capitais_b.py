"""Testes de interação da frente capitais-b-r6 (Rio de Janeiro, Belo Horizonte, Curitiba e Porto Alegre): propostas dos
vereadores e da prefeitura lidas nas páginas oficiais das Câmaras, gastos dos gabinetes (Porto Alegre), o quadro da Câmara
na página da cidade, inglês e celular de 320 px. Playwright + Edge, com o servidor em 8770 e os dados gerados
(python scripts/legislativos.py 3304557 3106200 4106902 4314902; python scripts/montar.py).
Uso: python testes/interacao_capitais_b.py [IBGE ...]   (sem códigos: as quatro cidades)"""
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
# cidade -> (UF, padrão do link oficial de cada proposta, trecho da nota das propostas em pt e em en)
CIDADES = {
    "3304557": ("RJ", r"^https://aplicnt\.camara\.rj\.gov\.br/APL/Legislativos/scpro\.nsf/", "sistema de proposições da Câmara",
                "City Council's bills system"),
    "3106200": ("MG", r"^https://www\.cmbh\.mg\.gov\.br/atividade-legislativa/pesquisar-proposicoes/", "pesquisa de proposições do portal",
                "bills search on the City Council's portal"),
    "4314902": ("RS", r"^https://www\.camarapoa\.rs\.gov\.br/processos/\d+$", "consulta de projetos do site da Câmara",
                "City Council's bills search"),
}
SO = [a for a in sys.argv[1:] if a.isdigit()] or list(CIDADES) + ["4106902"]


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


def vereador_com_propostas(ibge, uf):
    """O vereador com mais propostas (com autor e coautor), já marcado pelo montar.py ("extras": "cidade")."""
    marcados = {m["id"] for m in (cidade(ibge, uf).get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}
    cands = []
    for pid, x in extras(ibge).items():
        r = (x.get("propostas") or {}).get("resumo") or {}
        if pid in marcados and r.get("autor") and r.get("coautor"):
            cands.append((r["total"], pid))
    return max(cands)[1] if cands else None


def sem_nbsp(t):
    return t.replace("\u00a0", " ").replace("\u202f", " ")


def reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def sem_rolagem_lateral(pg):
    return await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


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

        for ibge, (uf, padrao, nota_pt, nota_en) in CIDADES.items():
            if ibge not in SO:
                continue
            k = casa(ibge)
            nome = k.get("casa", ibge)
            ok(f"{nome}: o arquivo da Câmara marca as propostas e tem o escopo nos dois idiomas",
               (k.get("cobertura") or {}).get("propostas") and k.get("escopoPropostas") and k.get("escopoPropostas_en"))
            ok(f"{nome}: nenhuma nota com promessa (\"ainda não\", \"em breve\"...)",
               not any(re.search(r"ainda não|em breve|por enquanto|not yet|coming soon", n, re.I)
                       for n in (k.get("notas") or []) + (k.get("notas_en") or [])))
            ok(f"{nome}: a nota antiga \"As propostas ... não entram\" saiu",
               not any(re.search(r"propostas dos vereadores não entram", n) for n in k.get("notas") or []))

            # 1. página da cidade: a lista oficial e o quadro da Câmara (cobertura e notas)
            v = cidade(ibge, uf).get("vereadores") or {}
            await pg.goto(BASE + f"cidade.html?ibge={ibge}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            n = await pg.locator("#casa-ver .pessoa-card").count()
            ok(f"{nome}: a página da cidade mostra a lista oficial", v.get("oficial") and n == len(v.get("membros") or []),
               f"{n} cartões")
            info = sem_nbsp(await pg.locator(".info-casa").first.inner_text())
            ok(f"{nome}: o quadro da Câmara marca \"O que cada um propôs\" e mostra a nota da fonte",
               await pg.locator(".info-casa li.tem", has_text="O que cada um propôs").count() == 1 and nota_pt in info, info[:90])

            # 2. perfil do vereador com mais propostas: números da página = dados, filtros e link oficial
            pid = vereador_com_propostas(ibge, uf)
            ok(f"{nome}: há um vereador com propostas como autor e coautor, já juntado pelo montar", pid)
            if not pid:
                continue
            b = extras(ibge)[pid]["propostas"]
            lista = b["lista"]
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1200)
            n_aut = sum(1 for x in lista if x["papel"] == "autor")
            n_co = len(lista) - n_aut
            botoes = await pg.locator("#propostas button[data-papel]").all_inner_texts()
            ok(f"{nome}: os botões de autoria têm os números dos dados ({n_aut} e {n_co})",
               len(botoes) == 2 and botoes[0].startswith(f"{n_aut:,}".replace(",", ".")) and botoes[1].startswith(f"{n_co:,}".replace(",", ".")),
               " | ".join(x.split("\n")[0] for x in botoes))
            cont = await pg.locator("#contagem-prop").inner_text()
            ok(f"{nome}: a contagem da lista é a dos dados", f"de {n_aut:,}".replace(",", ".") in cont, cont)
            # filtro de situação (pelo teclado): a contagem é a dos dados
            chip = pg.locator("#status-chips button[data-status]").first
            st = await chip.get_attribute("data-status")
            await chip.focus()
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(500)
            cont2 = await pg.locator("#contagem-prop").inner_text()
            esperado = sum(1 for x in lista if x["papel"] == "autor" and x["status"] == st)
            ok(f"{nome}: o filtro \"{st}\" mostra o número dos dados ({esperado})", f"de {esperado:,}".replace(",", ".") in cont2, cont2)
            await chip.focus()
            await pg.keyboard.press("Enter")
            co = pg.locator("#propostas button[data-papel='coautor']")
            await co.focus()
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(500)
            cont3 = await pg.locator("#contagem-prop").inner_text()
            ok(f"{nome}: \"Assinou junto\" mostra as {n_co} em que assinou junto", f"de {n_co:,}".replace(",", ".") in cont3, cont3)
            hrefs = await pg.locator("#lista-prop li.prop a.fora, #lista-prop li.prop a[target=_blank]").evaluate_all(
                "els => els.map(e => e.href)")
            oficiais = [h for h in hrefs if re.search(padrao, h)]
            ok(f"{nome}: cada proposta tem o link da página oficial", len(oficiais) >= min(20, n_co), f"{len(oficiais)} links")
            # a proposta mais nova da lista é a dos dados (sigla e situação)
            primeira = next(x for x in lista if x["papel"] == "coautor")
            t0 = await pg.locator("#lista-prop li.prop").first.inner_text()
            ok(f"{nome}: a primeira proposta da lista é a dos dados ({primeira['sigla']})", primeira["sigla"] in t0, t0[:80].replace("\n", " "))
            lei = next((x for x in lista if x.get("lei") and x["lei"].get("url")), None)
            if lei:
                await pg.locator("#propostas button[data-papel='coautor']").click()
                await pg.locator("#propostas button[data-papel='autor']").click()
                await pg.locator("#status-chips button[data-status='lei']").click()
                await pg.wait_for_timeout(500)
                ok(f"{nome}: a proposta que virou lei leva ao texto da norma", await pg.locator(f'#lista-prop a[href="{lei["lei"]["url"]}"]').count() >= 1
                   or lei["papel"] != "autor", lei["lei"]["nome"])

            # 3. em inglês: escopo, situações e nota da Câmara
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(1200)
            esc = await pg.locator("#propostas > p.muted").first.inner_text()
            ok(f"{nome}: escopo das propostas em inglês", b["escopo_en"][:50] in esc, esc[:80])
            sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
            pt = [s for s in sts if re.search(r"Ainda|Aprovada|Arquivada|Virou|prefeito|Câmara|Rejeitada|desistiu", s)]
            ok(f"{nome}: situações em inglês", sts and not pt, " | ".join(pt[:3]))
            await pg.goto(BASE + f"cidade.html?ibge={ibge}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            info = sem_nbsp(await pg.locator(".info-casa").first.inner_text())
            ok(f"{nome}: o quadro da Câmara em inglês, com a nota da fonte", nota_en in info and "What each member proposed" in info)

            # 4. o prefeito: os projetos que mandou à Câmara
            pref = cidade(ibge, uf).get("prefeito") or {}
            bp = (extras(ibge).get(pref.get("id")) or {}).get("propostas")
            if bp:
                await pg.goto(BASE + f"pessoa.html?id={pref['id']}&lang=pt", wait_until="networkidle")
                await pg.wait_for_timeout(1200)
                corpo = await pg.locator("#perfil").inner_text()
                n_l = await pg.locator("#lista-prop li.prop").count()
                ok(f"{nome}: o prefeito mostra os projetos que mandou à Câmara ({bp['resumo']['total']})",
                   n_l == min(20, bp["resumo"]["total"]) and "Projetos que a prefeitura mandou" in corpo, f"{n_l} na tela")
                await pg.goto(BASE + f"pessoa.html?id={pref['id']}&lang=en", wait_until="networkidle")
                await pg.wait_for_timeout(1000)
                ok(f"{nome}: o prefeito em inglês", "mayor's office sent" in await pg.locator("#propostas").inner_text())

            # 5. celular de 320 px: sem rolar para os lados (cidade e perfil)
            for url in (f"cidade.html?ibge={ibge}&lang=pt", f"pessoa.html?id={pid}&lang=pt", f"pessoa.html?id={pid}&lang=en"):
                await pc.goto(BASE + url, wait_until="networkidle")
                await pc.wait_for_timeout(800)
                ok(f"{nome}: 320 px sem rolar para os lados ({url.split('?')[0]}, {url[-2:]})", await sem_rolagem_lateral(pc))

        # 6. Porto Alegre: gastos dos gabinetes (os números da página = dados) e as votações continuam
        ex = extras("4314902") if "4314902" in SO else {}
        marcados = {m["id"] for m in (cidade("4314902", "RS").get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}
        cands = [(x["gastos"]["total"], pid) for pid, x in ex.items() if pid in marcados and (x.get("gastos") or {}).get("total")
                 and (x.get("votacoes") or {}).get("votos")]
        if "4314902" in SO:
            ok("Porto Alegre: vereadores com gastos e votações", cands and len(cands) >= 25, f"{len(cands)}")
        if cands:
            pid = max(cands)[1]
            g, vv = ex[pid]["gastos"], ex[pid]["votacoes"]
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pg.locator("#gastos").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1200)
            gs = sem_nbsp(await pg.locator("#gastos").inner_text())
            ok(f"Porto Alegre: gastos com o nome da verba e o valor de cada tipo ({reais(g['porTipo'][0]['valor'])})",
               reais(g["porTipo"][0]["valor"]) in gs and g["nome"] in gs and "Gastos do mandato" in gs, gs[:120].replace("\n", " "))
            ok("Porto Alegre: um item para cada tipo de gasto (até 8)", await pg.locator("#gastos li.gasto").count() == min(8, len(g["porTipo"])))
            ok("Porto Alegre: o total do ano é a soma dos tipos", abs(sum(t["valor"] for t in g["porTipo"]) - g["total"]) < 0.01)
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            leg = (await pg.locator("#votacoes .legenda-votos").inner_text()).replace(".", "")
            ok(f"Porto Alegre: as votações nominais continuam (total {vv['resumo']['total']})", f"Total: {vv['resumo']['total']}" in leg)
            n = await pg.locator("#lista-votos > li").count()
            ok("Porto Alegre: a lista de votações aparece (15 por vez)", n == min(15, len(vv["votos"])), f"{n}")
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
            await pg.locator("#gastos").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1000)
            gs = await pg.locator("#gastos").inner_text()
            ok("Porto Alegre: gastos em inglês", "Office spending" in gs and g["nome_en"] in gs)
            await pc.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pc.locator("#gastos").scroll_into_view_if_needed()
            await pc.wait_for_timeout(800)
            ok("Porto Alegre: perfil com gastos e votações em 320 px sem rolar para os lados", await sem_rolagem_lateral(pc))

        # 7. Curitiba: só a lista oficial; a nota diz por que as propostas não entram (CAPTCHA) e o perfil mostra "Onde ver mais"
        if "4106902" in SO:
            await curitiba(pg, pc)

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


async def curitiba(pg, pc):
    k = casa("4106902")
    ok("Curitiba: sem propostas, com a nota do CAPTCHA (pt e en)", not (k.get("cobertura") or {}).get("propostas")
       and any("CAPTCHA" in n for n in k.get("notas") or []) and any("CAPTCHA" in n for n in k.get("notas_en") or []))
    v = cidade("4106902", "PR").get("vereadores") or {}
    m0 = (v.get("membros") or [{}])[0]
    await pg.goto(BASE + f"pessoa.html?id={m0.get('id')}&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1000)
    corpo = await pg.locator("#perfil").inner_text()
    ok("Curitiba: o perfil mostra \"Onde ver mais\" com a nota (sem \"Em breve\")", "Onde ver mais" in corpo and "CAPTCHA" in corpo
       and "Em breve" not in corpo)
    await pg.goto(BASE + "cidade.html?ibge=4106902&lang=en", wait_until="networkidle")
    await pg.wait_for_timeout(1000)
    info = await pg.locator(".info-casa").first.inner_text()
    ok("Curitiba: o quadro da Câmara em inglês, com o pedido de informação", "CAPTCHA" in info and "Access to Information Law" in info)
    await pc.goto(BASE + "cidade.html?ibge=4106902&lang=pt", wait_until="networkidle")
    await pc.wait_for_timeout(800)
    ok("Curitiba: 320 px sem rolar para os lados", await sem_rolagem_lateral(pc))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
