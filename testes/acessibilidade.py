"""Auditoria automática de acessibilidade (axe-core, WCAG 2.2 A/AA) com Playwright + Edge.

Uso: python testes/acessibilidade.py index.html "brasil.html?lang=en" ... [--mobile]
Precisa do axe-core em ../ferramentas/node_modules/axe-core/axe.min.js (fora do site).
"""
import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8771/
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")


async def audita(pg, url):
    await pg.goto("about:blank")  # se só o "#" mudar, a página não recarregaria
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(2500)
    await pg.add_script_tag(path=str(AXE))
    r = await pg.evaluate("""async () => {
      const res = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                            resultTypes: ['violations'] });
      return res.violations.map(v => ({ id: v.id, impacto: v.impact, ajuda: v.help, n: v.nodes.length,
        exemplos: v.nodes.slice(0, 3).map(n => (n.target || []).join(' ') + ' :: ' + (n.failureSummary || '').split('\\n').slice(1, 3).join(' | ')) }));
    }""")
    return r


def urls_aulas() -> list[str]:
    """Todos os slides de todas as paradas, em português e em inglês (+ o slide final de cada parada)."""
    import json
    raiz = Path(__file__).resolve().parent.parent
    out = []
    for pasta, q in (("", ""), ("en/", "?lang=en")):
        for n in range(1, 11):
            arq = raiz / "conteudo" / "entenda" / f"{pasta}parte-{n}.json"
            if arq.exists():
                total = len(json.loads(arq.read_text(encoding="utf-8"))["slides"]) + 1
                out += [f"entenda.html{q}#parte-{n}" + (f"-{k}" if k > 1 else "") for k in range(1, total + 1)]
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--aulas", action="store_true", help="audita todos os slides de todas as paradas (pt e en)")
    a = ap.parse_args()
    if a.aulas:
        a.urls += urls_aulas()
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        opts = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True) if a.mobile else dict(viewport={"width": 1280, "height": 860})
        ctx = await nav.new_context(**opts)
        pg = await ctx.new_page()
        total = 0
        for url in a.urls:
            v = await audita(pg, url)
            total += len(v)
            print(f"\n=== {url}: {len(v)} problema(s)")
            for x in v:
                print(f"  [{x['impacto']}] {x['id']} ({x['n']}): {x['ajuda']}")
                for e in x["exemplos"]:
                    print("      -", e[:240])
        await nav.close()
        print(f"\nTOTAL: {total}")


asyncio.run(main())
