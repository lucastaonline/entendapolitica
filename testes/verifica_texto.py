"""Procura texto quebrado e português solto nas páginas.

- Em todas: "undefined", "null", "NaN", "[object" no texto visível.
- Em ?lang=en: palavras que só existem em português, fora de elementos marcados com lang="pt-BR"
  (textos oficiais, como ementas e nomes de órgãos, ficam marcados e não contam).
Uso: python testes/verifica_texto.py "pessoa.html?id=pres-lula&lang=en" ...   (precisa do servidor em 8770)
"""
import asyncio
import collections
import sys

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
sys.stdout.reconfigure(encoding="utf-8")

JS = r"""() => {
  const PT = /(?<!\p{L})(não|é|para|com|que|uma|foi|está|ainda|outra|outro|mais|como|quem|sobre|também|você|anos|eleit[oa]s?|deputad[oa]s?|senador[a]?|vereador[a]?|prefeit[oa]|governador[a]?|projeto|proposta|propostas|votaç[aã]o|votações|cargo|mandato|partido|cidade|estado|fonte|fontes|ver mais|aprovad[oa]|arquivad[oa]|discussão|junto|desde|até|pelo|pela|nos|nas|ao|aos|à|às)(?!\p{L})/iu;
  const QUEBRADO = /\b(undefined|null|NaN)\b|\[object/;
  const en = document.documentElement.lang === "en";
  const achados = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = n.textContent.replace(/\s+/g, " ").trim();
    if (!t) continue;
    const el = n.parentElement;
    if (!el || el.closest("script,style,noscript,[hidden],[aria-hidden=true]")) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    if (QUEBRADO.test(t)) achados.push(["QUEBRADO", t.slice(0, 160)]);
    if (en) {
      const l = el.closest("[lang]");
      if (l && /^pt/i.test(l.getAttribute("lang"))) continue;
      // endereços de sites ("facebook.com/...") não são texto em português
      const m = PT.exec(t.replace(/(?:https?:\/\/)?[\w-]+(?:\.[\w-]+)+(?:\/\S*)?/g, " "));
      if (m) achados.push(["PT", t.slice(0, 160)]);
    }
  }
  // atributos lidos por leitor de tela
  if (en) for (const el of document.querySelectorAll("[aria-label],[title],[alt],[placeholder]")) {
    for (const a of ["aria-label", "title", "alt", "placeholder"]) {
      const v = el.getAttribute(a);
      if (!v) continue;
      const l = el.closest("[lang]");
      if (l && /^pt/i.test(l.getAttribute("lang"))) continue;
      if (/(?<!\p{L})(não|é|para|com|que|uma|você|abre em outra aba|página|aumentar|voltar)(?!\p{L})/iu.test(v)) achados.push(["PT-ATRIBUTO " + a, v.slice(0, 160)]);
    }
  }
  return achados;
}"""


async def main():
    urls = sys.argv[1:]
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        pg = await nav.new_page(viewport={"width": 1280, "height": 900})
        total = 0
        for url in urls:
            await pg.goto("about:blank")
            await pg.goto(BASE + url, wait_until="networkidle")
            await pg.wait_for_timeout(1800)
            # abre "mostrar mais" e blocos recolhidos, para conferir o texto escondido também
            await pg.evaluate("""() => { document.querySelectorAll('details').forEach(d => d.open = true); }""")
            achados = await pg.evaluate(JS)
            c = collections.Counter((k, t) for k, t in achados)
            total += len(c)
            print(f"\n=== {url}: {len(c)} trecho(s)")
            for (k, t), q in sorted(c.items()):
                print(f"  [{k}] x{q}: {t}")
        await nav.close()
        print(f"\nTOTAL: {total}")


asyncio.run(main())
