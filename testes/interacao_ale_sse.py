"""Testes de interação das Assembleias do Sudeste, do Sul e do DF (lista oficial, propostas, gastos e o perfil de cada
governador), com Playwright + Edge.
Precisa do servidor em 8770 e dos dados gerados (python scripts/legislativos.py MG SP RJ ES PR SC RS DF; python scripts/montar.py).
Uso: python testes/interacao_ale_sse.py"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
UFS = ["MG", "SP", "RJ", "ES", "PR", "SC", "RS", "DF"]
COM_GASTOS = {"MG", "SP", "SC"}
PT = ("Ainda em", "Aprovada", "Arquivada", "Virou", "governador", "Assembleia", "Câmara Legislativa", "Rejeitada", "desistiu")


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def casa(uf):
    return json.loads((RAIZ / "dados" / "assembleias" / f"{uf}.json").read_text(encoding="utf-8"))


def pessoa(pid):
    arq = RAIZ / "dados" / "pessoas" / f"{pid}.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def com_propostas(uf, minimo=25):
    """O primeiro membro (em ordem alfabética) com mais de `minimo` propostas e com leis, para testar os filtros."""
    for m in sorted(casa(uf)["membros"], key=lambda x: x["nome"]):
        lista = (pessoa(m["id"]).get("propostas") or {}).get("lista") or []
        if len(lista) > minimo and any(p["status"] == "lei" for p in lista):
            return m
    return None


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. página de cada estado: a lista oficial substitui a do TSE (um cartão por pessoa) e diz o que a Casa tem
        for uf in UFS:
            k = casa(uf)
            await pg.goto(BASE + f"estado.html?uf={uf}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(900)
            for _ in range(5):  # a lista mostra 60 de cada vez: "Mostrar mais"
                mais = pg.locator("#casa-est .ver-mais")
                if not await mais.count():
                    break
                await mais.first.click()
                await pg.wait_for_timeout(400)
            n = await pg.locator("#casa-est .pessoa-card").count()
            aviso = await pg.locator("#aviso-est").inner_text()
            ok(f"{uf}: lista oficial com todos ({k['sigla']})", n == len(k["membros"]) and "Lista oficial" in aviso,
               f"{n} de {len(k['membros'])}")
            sup = [m for m in k["membros"] if m.get("exercicio")]
            if sup:
                txt = await pg.locator("#casa-est").inner_text()
                ok(f"{uf}: suplentes no cargo aparecem como tal", sup[0]["exercicio"] in txt, sup[0]["nome"])

        # 2. do cartão para o perfil, só com o teclado (MG): propostas com filtros, link oficial e gastos
        m = com_propostas("MG")
        await pg.goto(BASE + "estado.html?uf=MG&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(900)
        card = pg.locator(f'#casa-est a.pessoa-card[href*="{m["id"]}"]')
        await card.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        await pg.wait_for_timeout(1000)
        n_prop = await pg.locator("#lista-prop li.prop").count()
        ok("MG: perfil mostra as propostas (20 por vez)", n_prop == 20, f"{n_prop} na tela")
        cont0 = await pg.locator("#contagem-prop").inner_text()
        chip = pg.locator('#status-chips button[data-status="lei"]')
        await chip.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        cont1 = await pg.locator("#contagem-prop").inner_text()
        leis = await pg.locator("#lista-prop li.prop.s-lei").count()
        todas = await pg.locator("#lista-prop li.prop").count()
        ok("MG: filtro \"Virou lei\" muda a lista e mantém o foco",
           cont0 != cont1 and leis == todas > 0 and await pg.evaluate("document.activeElement.hasAttribute('data-status')"), cont1)
        ok("MG: lei com link para o texto oficial", await pg.locator('#lista-prop a[href*="almg.gov.br/legislacao-mineira/"]').count() > 0)
        ok("MG: cada proposta leva à página oficial", await pg.locator('#lista-prop a[href*="almg.gov.br/projetos-de-lei/"]').count() > 0)
        ok("MG: link da página oficial do deputado", await pg.locator('.contatos a[href*="almg.gov.br"]').count() >= 1)
        ok("MG: gastos da verba indenizatória", await pg.locator("#gastos").count() == 1)

        # 3. um perfil por estado (o primeiro com propostas e leis), em português e em inglês
        for uf in UFS:
            m = com_propostas(uf, 5)
            if not m:
                ok(f"{uf}: sem propostas (só a lista oficial)", uf == "RJ")
                continue
            dados = pessoa(m["id"])
            await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(900)
            n = await pg.locator("#lista-prop li.prop").count()
            links = await pg.locator("#lista-prop a.fora, #lista-prop a[target=_blank]").count()
            ok(f"{uf}: perfil com propostas e links oficiais ({m['nome']})", n > 0 and links > 0, f"{n} propostas, {links} links")
            fontes = await pg.locator("#propostas button, #propostas a").count()
            ok(f"{uf}: bloco de propostas tem fonte", fontes > 0)
            if uf in COM_GASTOS:
                ok(f"{uf}: gastos aparecem", await pg.locator("#gastos").count() == 1 and bool(dados.get("gastos")))
            await pg.goto(BASE + f"pessoa.html?id={m['id']}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(900)
            sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
            pt = [s for s in sts if any(w in s for w in PT)]
            ok(f"{uf}: situações em inglês", sts and not pt, " | ".join(pt[:3]))
            esc = await pg.locator("#propostas > p.muted").first.inner_text()
            ok(f"{uf}: escopo das propostas em inglês", "filed since" in esc, esc[:70])

        # 4. Rio de Janeiro: só a lista oficial; o perfil leva à página oficial e diz onde ver as propostas (sem "Em breve")
        k = casa("RJ")
        sup = next((x for x in k["membros"] if x.get("exercicio")), k["membros"][0])
        await pg.goto(BASE + f"pessoa.html?id={sup['id']}&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(900)
        corpo = await pg.locator("#perfil").inner_text()
        ok("RJ: perfil com link oficial e o quadro \"Onde ver mais\" com o motivo e o site da Alerj",
           await pg.locator('.contatos a[href*="alerj.rj.gov.br"]').count() >= 1 and "Em breve" not in corpo
           and "Onde ver mais" in corpo and "Alerj" in await pg.locator(".onde-ver .notas-casa").inner_text()
           and await pg.locator('.onde-ver a[href*="alerj.rj.gov.br"]').count() >= 1)
        ok("RJ: suplente em exercício marcado no perfil", sup.get("exercicio") in corpo, sup["nome"])

        # 5. o perfil de cada governador: projetos que o governo mandou e "Leis sancionadas e vetos" (pt e en)
        for uf in UFS:
            g = pessoa(f"gov-{uf}")
            ex, lista = g.get("executivo") or {}, (g.get("propostas") or {}).get("lista") or []
            await pg.goto(BASE + f"pessoa.html?id=gov-{uf}&lang=pt", wait_until="networkidle")
            await pg.wait_for_timeout(900)
            corpo = await pg.locator("#perfil").inner_text()
            sec = await pg.locator("#t-exec").count() and await pg.locator("section:has(#t-exec)").inner_text() or ""
            nums = [f"{ex[c]:,}".replace(",", ".") for c in ("leisSancionadas", "vetos") if ex.get(c) is not None]
            n = await pg.locator("#lista-prop li.prop").count()
            ok(f"{uf}: governo com projetos e leis no perfil", lista and n > 0 and all(x in sec for x in nums)
               and "Em breve" not in corpo, f"{n} projetos na tela; {', '.join(nums)}")
            await pg.goto(BASE + f"pessoa.html?id=gov-{uf}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(900)
            sec = await pg.locator("#t-exec").count() and await pg.locator("section:has(#t-exec)").inner_text() or ""
            sts = await pg.locator("#lista-prop .status-txt").all_inner_texts()
            pt = [s for s in sts if any(w in s for w in PT)]
            esc = await pg.locator("#propostas > p.muted").first.inner_text()
            ok(f"{uf}: governo em inglês", "Laws signed and vetoes" in sec and sts and not pt and esc.startswith("Bills the "),
               (" | ".join(pt[:2]) or esc[:60]))

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
