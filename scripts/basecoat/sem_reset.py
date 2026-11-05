"""Prova de que o CSS do Basecoat não muda nada fora dos componentes: abre a mesma página com e sem
vendor/basecoat/basecoat.css (trocado por um arquivo vazio) e compara o estilo calculado (letra, cor, margens, espaços,
listas, bordas, caixa) de TODOS os elementos fora dos componentes (cabeçalho, campos, abas, blocos que abrem, janela,
botões .btn). Também guarda capturas da página com o Basecoat (capturas/reset-*.png)."""
import asyncio, sys, json
from pathlib import Path
from playwright.async_api import async_playwright
sys.stdout.reconfigure(encoding="utf-8")
BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")
CAP = Path(__import__("tempfile").gettempdir()) / "sem_reset"
PAGS = ["entenda.html", "imparcialidade.html", "dados.html", "index.html", "votacoes.html", "brasil.html", "estado.html?uf=BA", "pessoa.html?id=dep-178866"]
PROPS = ["font-family", "font-size", "font-weight", "line-height", "color", "background-color", "margin-top", "margin-bottom", "margin-left",
         "padding-top", "padding-left", "list-style-type", "border-top-width", "border-top-style", "box-sizing", "display", "text-decoration-line",
         "letter-spacing", "outline-style", "vertical-align", "max-width", "width"]
JS = """(props) => {
  document.querySelectorAll('.rev').forEach(e => e.classList.add('visivel'));
  const fora = '.abas-ep:not(.abas-grupo > [role=tabpanel] *), .tabs:not(.abas-grupo > [role=tabpanel] *), .topo, .combo, .busca, .abas-lista, details.bloco-abre, .janela-dialog, .btn, [data-popover], .menu-painel, input, select, button, .formas';
  const r = {};
  let i = 0;
  for (const e of document.querySelectorAll('main *, footer *')) {
    i++;
    if (e.matches('.abas-ep, .abas-grupo') || e.closest('.abas-lista, .topo, .combo, .busca, details.bloco-abre > summary, .janela-dialog, .btn, [data-popover], .menu-painel, input, select, button, .formas')) continue;
    const cs = getComputedStyle(e);
    r[i + ':' + e.tagName + '.' + (typeof e.className === 'string' ? e.className : '')] = props.map(p => cs.getPropertyValue(p)).join('|');
  }
  return r;
}"""
async def estilos(nav, url, w, sem, foto=None):
    ctx = await nav.new_context(viewport={"width": w, "height": 800}, reduced_motion="reduce")
    if sem:
        await ctx.route("**/vendor/basecoat/basecoat.css*", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg = await ctx.new_page()
    sep = "&" if "?" in url else "?"
    await pg.goto(BASE + url + sep + "lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1800)
    r = await pg.evaluate(JS, PROPS)
    if foto:
        await pg.screenshot(path=str(CAP / foto), full_page=False)
    await ctx.close()
    return r
async def main():
    ruim = 0
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        for url in PAGS:
            for w in (1366, 390):
                nome = url.split(".")[0] + ("-" + url.split("=")[-1] if "=" in url else "")
                a = await estilos(nav, url, w, False, f"reset-{nome}-{w}.png" if url.split("?")[0] in ("entenda.html", "imparcialidade.html", "dados.html") else None)
                b = await estilos(nav, url, w, True)
                dif = [(k, a[k], b.get(k)) for k in a if a[k] != b.get(k)]
                faltam = len(set(a) ^ set(b))
                bom = not dif and not faltam
                ruim += not bom
                print(("✅ " if bom else "❌ ") + f"{url} {w}px: {len(a)} elementos fora dos componentes, {len(dif)} com estilo diferente com e sem o CSS do Basecoat" + (f", {faltam} a mais/menos" if faltam else ""))
                for k, x, y in dif[:4]:
                    dd = [f"{PROPS[j]}: {u} → {v}" for j, (u, v) in enumerate(zip(x.split('|'), (y or '').split('|'))) if u != v]
                    print("     ", k[:60], "; ".join(dd)[:200])
        await nav.close()
    sys.exit(1 if ruim else 0)
asyncio.run(main())
