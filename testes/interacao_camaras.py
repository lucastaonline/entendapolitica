"""Testes de interação das Câmaras Municipais das capitais (lista oficial e propostas), com Playwright + Edge.
Precisa do servidor em 8770 e dos dados gerados (python scripts/legislativos.py camaras; python scripts/montar.py).
Uso: python testes/interacao_camaras.py"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def casa(ibge):
    return json.loads((RAIZ / "dados" / "camaras" / f"{ibge}.json").read_text(encoding="utf-8"))


def com_propostas(ibge):
    """Um membro da Câmara que tem propostas (para abrir o perfil)."""
    for m in casa(ibge)["membros"]:
        arq = RAIZ / "dados" / "pessoas" / f"{m['id']}.json"
        if arq.exists():
            p = json.loads(arq.read_text(encoding="utf-8"))
            if len((p.get("propostas") or {}).get("lista") or []) > 25:
                return m
    return None


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. cidade com SAPL: a lista oficial substitui a do TSE
        k = casa("2408102")
        await pg.goto(BASE + "cidade.html?ibge=2408102&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#cidade").inner_text()
        n = await pg.locator("#casa-ver .pessoa-card").count()
        ok("Natal: aviso de lista oficial da Câmara", "Lista oficial da Câmara Municipal de Natal" in txt)
        ok("Natal: um cartão para cada pessoa da lista oficial", n == len(k["membros"]), f"{n} de {len(k['membros'])}")

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

        # 5. cidade só com a lista oficial (sem propostas): perfil com link oficial e "Em breve"
        k = casa("3106200")
        await pg.goto(BASE + "cidade.html?ibge=3106200&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        n = await pg.locator("#casa-ver .pessoa-card").count()
        ok("Belo Horizonte: lista oficial com todos", n == len(k["membros"]) == 41, f"{n}")
        sup = next((x for x in k["membros"] if x.get("exercicio")), k["membros"][0])
        await pg.goto(BASE + f"pessoa.html?id={sup['id']}&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        corpo = await pg.locator("#perfil").inner_text()
        ok("perfil só com a lista: link oficial e aviso de que as propostas ainda não estão aqui",
           await pg.locator('.contatos a[href*="cmbh.mg.gov.br"]').count() == 1 and "Em breve" in corpo)

        # 6. todas as capitais com coletor: a página da cidade abre e usa a lista oficial
        falhas = []
        for arq in sorted((RAIZ / "dados" / "camaras").glob("*.json")):
            k = json.loads(arq.read_text(encoding="utf-8"))
            await pg.goto(BASE + f"cidade.html?ibge={k['ibge']}&lang=en", wait_until="networkidle")
            await pg.wait_for_timeout(700)
            n = await pg.locator("#casa-ver .pessoa-card").count()
            t = await pg.locator("#cidade").inner_text()
            if n != len(k["membros"]) or "Official list from the" not in t:
                falhas.append(f"{k['ibge']} ({n}/{len(k['membros'])})")
        ok("todas as Câmaras com coletor mostram a lista oficial (em inglês)", not falhas, ", ".join(falhas))

        ok("nenhum erro de JavaScript", not erros, "; ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
