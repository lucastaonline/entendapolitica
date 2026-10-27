"""Testes de interação das Câmaras Municipais (lista oficial, propostas, o que o prefeito fez, votações nominais e gastos do
mandato), com Playwright + Edge.
Precisa do servidor em 8770 e dos dados gerados (python scripts/legislativos.py camaras; python scripts/legislativos.py sapl
ou só as cidades usadas aqui; python scripts/montar.py).
Tudo de uma cidade (vereadores e prefeito) fica num arquivo só: dados/camaras/extras/<IBGE>.json.
O teste só olha as Câmaras que o montar.py já juntou à página da cidade (dados/cidades/<UF>/<IBGE>.json com a lista oficial):
uma Câmara recém-coletada entra na página na próxima rodada do montar.
Uso: python testes/interacao_camaras.py"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
CAPITAIS = {"3550308", "3304557", "3106200", "2927408", "2304400", "2611606", "4106902", "4314902", "1302603", "1501402",
            "5208707", "2111300", "2704302", "2211001", "2408102", "5002704", "2507507", "2800308", "5103403", "4205407",
            "1100205", "1600303", "1200401", "3205309", "1400100", "1721000"}


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def ler(arq):
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def casa(ibge):
    return ler(RAIZ / "dados" / "camaras" / f"{ibge}.json")


def extras(ibge):
    return (ler(RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json") or {}).get("pessoas") or {}


def cidade(ibge):
    """dados/cidades/<UF>/<IBGE>.json: o que a página da cidade mostra (o montar.py junta a lista oficial aqui)."""
    k = casa(ibge) or {}
    uf = k.get("uf") or SAPL.get(ibge, {}).get("uf")
    return (ler(RAIZ / "dados" / "cidades" / uf / f"{ibge}.json") or {}) if uf else {}


def juntada(ibge):
    """A lista oficial da Câmara já foi juntada à página da cidade pelo montar.py (as Câmaras novas só aparecem na página
    depois da próxima rodada do montar)."""
    return bool((cidade(ibge).get("vereadores") or {}).get("oficial"))


def com_propostas(ibge, minimo=25):
    """Um vereador da cidade que tem propostas no arquivo da cidade e que a página da cidade já marca com "extras": "cidade"
    (o perfil só busca o arquivo da cidade para quem tem a marca)."""
    ex = extras(ibge)
    marcados = {m["id"] for m in (cidade(ibge).get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}
    for pid, p in sorted(ex.items()):
        if pid.startswith("ver-") and pid in marcados and len((p.get("propostas") or {}).get("lista") or []) > minimo:
            return {"id": pid, **p}
    return None


def tem_lista(ibge):
    return bool((casa(ibge) or {}).get("membros"))


SAPL = (ler(RAIZ / "scripts" / "camaras" / "sapl_cidades.json") or {}).get("cidades") or {}


def cidade_sapl(oficial=True, prefeito_completo=False):
    """Uma cidade da lista SAPL (não capital) já coletada e já juntada pelo montar.py: com ou sem lista oficial; com o
    prefeito completo (projetos, leis e vetos) se pedido."""
    for ibge in sorted(SAPL):
        if not (RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json").exists() or casa(ibge) is None:
            continue
        if oficial != tem_lista(ibge) or (oficial and not juntada(ibge)):
            continue
        pref = extras(ibge).get(f"pref-{ibge}") or {}
        ex = pref.get("executivo") or {}
        if prefeito_completo and not (pref.get("propostas") and ex.get("leisSancionadas") is not None and ex.get("vetos") is not None
                                      and (cidade(ibge).get("prefeito") or {}).get("extras") == "cidade"):
            continue
        if com_propostas(ibge, 3 if oficial else 0):
            return ibge
    return None


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. cidade com SAPL: a lista oficial substitui a do TSE
        v = cidade("2408102").get("vereadores") or {}
        await pg.goto(BASE + "cidade.html?ibge=2408102&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#cidade").inner_text()
        n = await pg.locator("#casa-ver .pessoa-card").count()
        ok("Natal: aviso de lista oficial da Câmara", "Lista oficial da Câmara Municipal de Natal" in txt)
        ok("Natal: um cartão para cada pessoa da lista oficial", v.get("oficial") and n == len(v.get("membros") or []),
           f"{n} de {len(v.get('membros') or [])}")

        # 2. do cartão para o perfil, só com o teclado: propostas com filtros
        m = com_propostas("2408102")
        card = pg.locator(f'#casa-ver a.pessoa-card[href*="{m["id"]}"]')
        await card.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        await pg.wait_for_timeout(1000)
        n_prop = await pg.locator("#lista-prop li.prop").count()
        ok("perfil do vereador mostra propostas (20 por vez)", n_prop == 20, f"{n_prop} na tela")
        cont0 = await pg.locator("#contagem-prop").inner_text()
        chip = pg.locator("#status-chips button[data-status]").first
        await chip.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        cont1 = await pg.locator("#contagem-prop").inner_text()
        ok("filtro de situação muda a lista e mantém o foco", cont0 != cont1 and await pg.evaluate("document.activeElement.hasAttribute('data-status')"), cont1)
        links = await pg.locator('#lista-prop a[href*="sapl.natal.rn.leg.br/materia/"]').count()
        ok("cada proposta leva à página oficial no SAPL", links > 0, f"{links} links")
        oficial = await pg.locator('.contatos a[href*="sapl.natal.rn.leg.br/parlamentar/"]').count()
        ok("perfil tem o link da página oficial do vereador", oficial == 1)

        # 3. em inglês: a situação das propostas sai em inglês
        await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
        pt = [s for s in sts if any(w in s for w in ("Ainda", "Aprovada", "Arquivada", "Virou", "prefeito", "Câmara"))]
        ok("situações em inglês (sem frase em português)", sts and not pt, " | ".join(pt[:3]))
        esc = await pg.locator("#propostas > p.muted").first.inner_text()
        ok("escopo das propostas em inglês", "filed since January 1, 2025" in esc, esc[:80])

        # 4. São Paulo (SPLegis): nota sobre os vários autores, nos dois idiomas
        # (o idioma escolhido fica salvo no aparelho: as páginas em português levam ?lang=pt)
        m = com_propostas("3550308")
        await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        ok("São Paulo: nota sobre projetos com vários autores", "assinou junto" in await pg.locator("#propostas").inner_text())
        await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        ok("São Paulo: a nota também em inglês", "co-signed" in await pg.locator("#propostas").inner_text())

        # 5. cidade só com a lista oficial (sem propostas): perfil com link oficial e "Onde ver mais" (sem "Em breve")
        v = cidade("4106902").get("vereadores") or {}
        await pg.goto(BASE + "cidade.html?ibge=4106902&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        n = await pg.locator("#casa-ver .pessoa-card").count()
        ok("Curitiba: lista oficial com todos", v.get("oficial") and n == len(v.get("membros") or []) == 38, f"{n}")
        sup = next((x for x in v.get("membros") or [] if x.get("exercicio")), (v.get("membros") or [{}])[0])
        await pg.goto(BASE + f"pessoa.html?id={sup['id']}&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        corpo = await pg.locator("#perfil").inner_text()
        ok("perfil só com a lista: link oficial e o quadro \"Onde ver mais\" (sem \"Em breve\")",
           await pg.locator('.contatos a[href*="cmc.pr.gov.br"]').count() == 1 and "Em breve" not in corpo and "Onde ver mais" in corpo)

        # 6. as capitais com coletor e uma amostra das cidades com SAPL: a página da cidade abre e usa a lista oficial.
        # Só as Câmaras que o montar.py já juntou à página (uma Câmara nova entra na página na próxima rodada do montar).
        falhas = []
        lista = sorted(a.stem for a in (RAIZ / "dados" / "camaras").glob("*.json") if tem_lista(a.stem))
        juntadas = [i for i in lista if juntada(i)]
        if len(juntadas) < len(lista):
            print(f"   ({len(lista) - len(juntadas)} Câmaras com lista oficial ainda não juntadas à página: rode python scripts/montar.py)")
        amostra = [i for i in juntadas if i in CAPITAIS] + [i for i in juntadas if i not in CAPITAIS][:12]
        for ibge in amostra:
            v = cidade(ibge).get("vereadores") or {}
            await pg.goto(BASE + f"cidade.html?ibge={ibge}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(700)
            n = await pg.locator("#casa-ver .pessoa-card").count()
            t = await pg.locator("#cidade").inner_text()
            if n != len(v.get("membros") or []) or "Official list from the" not in t:
                falhas.append(f"{ibge} ({n}/{len(v.get('membros') or [])})")
        ok(f"{len(amostra)} Câmaras com lista oficial (já juntadas pelo montar) mostram a lista (em inglês)", amostra and not falhas,
           ", ".join(falhas))

        # 7. cidade com SAPL (não capital), lista oficial: perfil do vereador com propostas do arquivo da cidade
        ib = cidade_sapl(oficial=True, prefeito_completo=True)
        ok("há uma cidade com SAPL, lista oficial e prefeito completo", ib)
        if ib:
            m = com_propostas(ib, 3)
            await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            corpo = await pg.locator("#perfil").inner_text()
            n_prop = await pg.locator("#lista-prop li.prop").count()
            ok(f"{ib}: perfil do vereador com propostas (arquivo da cidade)", n_prop > 0 and "Onde ver mais" not in corpo, f"{n_prop}")
            base = json.loads((RAIZ / "scripts" / "camaras" / "sapl_cidades.json").read_text(encoding="utf-8"))["cidades"][ib]["base"]
            ok(f"{ib}: cada proposta leva ao SAPL da Câmara", await pg.locator(f'#lista-prop a[href^="{base}/materia/"]').count() > 0)
            # 8. o prefeito: projetos que mandou à Câmara e o quadro de leis e vetos, nos dois idiomas
            ex = (extras(ib).get(f"pref-{ib}") or {}).get("executivo") or {}
            await pg.goto(BASE + f"pessoa.html?id=pref-{ib}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            corpo = await pg.locator("#perfil").inner_text()
            ok(f"{ib}: prefeito com os projetos que mandou à Câmara", await pg.locator("#lista-prop li.prop").count() > 0)
            ok(f"{ib}: prefeito com \"Leis sancionadas e vetos\"", "Leis sancionadas e vetos" in corpo and "Em breve" not in corpo)
            ok(f"{ib}: \"Como contamos\" (a nota de como as leis e os vetos foram contados)",
               await pg.locator("details.como-contou").count() == 1 and "Como contamos" in corpo)
            if (ex.get("periodo") or {}).get("ultimaLei"):
                ok(f"{ib}: a data da lei mais recente na fonte", "A lei mais recente na fonte é de" in corpo)
            await pg.goto(BASE + f"pessoa.html?id=pref-{ib}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            corpo = await pg.locator("#perfil").inner_text()
            ok(f"{ib}: em inglês também", "Laws signed and vetoes" in corpo and "mayor's office sent" in corpo
               and "How we counted" in corpo, corpo[:0])

        # 9. cidade com SAPL sem lista oficial (a conferência de vagas falhou): fica a lista do TSE, com as propostas
        ib = cidade_sapl(oficial=False)
        if ib:
            await pg.goto(BASE + f"cidade.html?ibge={ib}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            t = await pg.locator("#cidade").inner_text()
            ok(f"{ib}: sem lista oficial, a página mostra a lista do TSE", "Lista oficial da" not in t and "eleito em 2024" in t)
            m = com_propostas(ib, 0)
            await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(1000)
            ok(f"{ib}: o perfil (lista do TSE) mostra as propostas do SAPL", await pg.locator("#propostas").count() == 1)

        # 10. votações nominais e gastos do mandato (São Paulo e uma cidade com SAPL): os números da página batem com os dados
        def com_votos(ibge, gastos=False):
            ex = extras(ibge)
            marcados = {m["id"] for m in (cidade(ibge).get("vereadores") or {}).get("membros") or [] if m.get("extras") == "cidade"}
            cands = [(len(p["votacoes"]["votos"]), pid) for pid, p in ex.items() if pid in marcados and (p.get("votacoes") or {}).get("votos")
                     and (not gastos or p.get("gastos"))]
            return max(cands)[1] if cands else None

        def reais(v):
            return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def sem_nbsp(t):
            return t.replace("\u00a0", " ").replace("\u202f", " ")

        CURTO = {"NR": "Não votou", "NCom": "Ausente", "PS": "Presidia"}
        sapl_v = next((i for i in sorted(SAPL) if i not in CAPITAIS and juntada(i) and com_votos(i)), None)
        for ibge in [i for i in ("3550308", "4314902", "2611606", sapl_v) if i]:
            pid = com_votos(ibge, gastos=ibge == "3550308")
            ok(f"{ibge}: há um vereador com votações nominais (já juntado pelo montar)", pid)
            if not pid:
                continue
            p = extras(ibge)[pid]
            cat = (ler(RAIZ / "dados" / "camaras" / "extras" / f"{ibge}.json") or {}).get("votacoes") or {}
            vv = p["votacoes"]
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=pt", wait_until="networkidle")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            leg = await pg.locator("#votacoes .legenda-votos").inner_text()
            ok(f"{ibge}: o resumo dos votos bate com os dados (total {vv['resumo']['total']})",
               f"Total: {vv['resumo']['total']}" in leg.replace(".", "") and all(f"{k}: {vv['resumo'][k]}" in leg.replace(".", "")
                                                                              for k in ("Sim", "Não") if vv["resumo"].get(k)), leg.replace("\n", " ")[:120])
            itens = pg.locator("#lista-votos > li")
            n = await itens.count()
            ok(f"{ibge}: a lista mostra as votações 15 por vez", n == min(15, len(vv["votos"])), f"{n}")
            k0, voto0 = vv["votos"][0]
            x0 = cat.get(k0) or {}
            t0 = await itens.first.inner_text()
            ok(f"{ibge}: a votação mais nova (proposta, voto e resultado) é a do arquivo da cidade",
               x0 and (x0.get("proposta") or "") in t0 and CURTO.get(voto0, voto0) in t0 and (x0.get("resultado") or "") in t0,
               t0.replace("\n", " ")[:120])
            ok(f"{ibge}: cada votação leva à página oficial", await pg.locator(f'#lista-votos a[href="{x0.get("url")}"]').count() >= 1)
            pl = x0.get("placar") or {}
            ok(f"{ibge}: o placar guardado é o publicado (Sim + Não + Abstenção = total)",
               all(sum(c["placar"][a] for a in ("Sim", "Não", "Abstenção")) == c["placar"]["total"] for c in cat.values()) and pl)
            if len(vv["votos"]) > 15:
                b = pg.locator("#ver-mais-votos")
                await b.focus()
                await pg.keyboard.press("Enter")
                await pg.wait_for_timeout(500)
                ok(f"{ibge}: \"Mostrar mais votações\" com o teclado", await itens.count() == min(30, len(vv["votos"])))
            g = p.get("gastos")
            if g:
                gs = sem_nbsp(await pg.locator("#gastos").inner_text())
                primeiro = g["porTipo"][0]
                ok(f"{ibge}: gastos do mandato com o valor de cada tipo (o maior: {reais(primeiro['valor'])})",
                   reais(primeiro["valor"]) in gs and "Gastos do mandato" in gs and g["nome"] in gs, gs.replace("\n", " ")[:120])
                n_t = await pg.locator("#gastos li.gasto").count()
                ok(f"{ibge}: um item para cada tipo de gasto (até 8)", n_t == min(8, len(g["porTipo"])), f"{n_t}")
                ok(f"{ibge}: o total do ano é a soma dos tipos", abs(sum(t["valor"] for t in g["porTipo"]) - g["total"]) < 0.01)
            await pg.goto(BASE + f"pessoa.html?id={pid}&lang=en", wait_until="networkidle")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            sec = await pg.locator("#votacoes").inner_text()
            ok(f"{ibge}: em inglês, o escopo e o resultado em inglês", vv["escopo_en"][:60] in sec and
               ("Result: Approved" in sec or "Result: Rejected" in sec), sec.replace("\n", " ")[:120])
            if g:
                gs = await pg.locator("#gastos").inner_text()
                ok(f"{ibge}: gastos em inglês (o que entra)", "Office spending" in gs and g["nome_en"] in gs)

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
