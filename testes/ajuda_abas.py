"""Ajuda para as suítes antigas (ui-r9): o estado, a cidade e o perfil agora são divididos em abas (js/abas.js), cada aba
monta o seu conteúdo quando abre, e as listas grandes começam com um resumo ("Ver todos"). As suítes que conferem o conteúdo
(dados, textos, links, contagens) usam abre_tudo(pg) depois de abrir a página: abre cada aba uma vez (o conteúdo é montado),
deixa todas à vista, uma embaixo da outra, e aperta os "Ver todos" — a página fica como era antes das abas.
O comportamento das abas em si é conferido em testes/interacao_abas.py e testes/interacao_navegacao.py."""

TUDO = """async () => {
  if (!window.EP || !EP.abas || !EP.abas.ativa || !EP.abas.ativa()) return 0;
  const ativa = EP.abas.ativa(), paineis = [...document.querySelectorAll('.abas-grupo > [role=tabpanel][data-aba]')];
  for (const p of paineis) { EP.abas.mostra(p.getAttribute('data-aba')); await new Promise(r => setTimeout(r, 30)); }
  EP.abas.mostra(ativa);
  // painéis de seções que existem (a aba não está escondida) ficam todos à vista
  for (const p of paineis) { const t = document.getElementById('aba-' + p.getAttribute('data-aba')); if (t && !t.hidden) { p.hidden = false; p.style.display = 'block'; } }
  return paineis.length;
}"""
VER_TODOS = """() => { let n = 0; document.querySelectorAll('.ver-mais').forEach(b => { if (/Ver tod|See all/.test(b.textContent)) { b.click(); n++; } }); return n; }"""


async def abre_tudo(pg, espera=700):
    n = await pg.evaluate(TUDO)
    if n:
        await pg.wait_for_timeout(espera)
    # os "Ver todos" também nas páginas sem abas (ex.: o mandato 2027, estado.html?uf=SP&mandato=2027)
    for _ in range(3):
        if not await pg.evaluate(VER_TODOS):
            break
        await pg.wait_for_timeout(300)
    return n


async def aba(pg, nome, espera=600):
    """Abre uma aba (pelo nome da seção ou um id de dentro dela), como quem clica nela."""
    await pg.evaluate("n => window.EP && EP.abas && EP.abas.mostra(n)", nome)
    await pg.wait_for_timeout(espera)


def liga(pg):
    """Depois de cada pg.goto() para o estado, a cidade ou um perfil, abre todas as abas e os "Ver todos" (abre_tudo)."""
    original = pg.goto

    async def goto(url, **kw):
        # mesmo quando o "networkidle" demora demais (muitas fotos de fora) e o goto desiste, as abas são abertas
        try:
            return await original(url, **kw)
        finally:
            if any(x in url for x in ("estado.html?", "cidade.html?", "pessoa.html?")):
                try:
                    await pg.wait_for_timeout(900)
                    await abre_tudo(pg)
                except Exception:
                    pass
    pg.goto = goto
    return pg


async def pagina_inteira(pg, espera=2500, teclado=False):
    """site-d-r13: nas listas do Brasil, do estado e da cidade, clicar numa pessoa abre a gaveta (o resumo, sem sair da página);
    o perfil fica no botão “Ver a página inteira” dela. Depois do clique no cartão, esta ajuda aperta esse botão (se a gaveta
    não abriu, a página já está indo para o perfil e nada muda)."""
    try:
        await pg.wait_for_selector("#gaveta[open] .gv-pagina", timeout=espera)
    except Exception:
        return False
    if teclado:
        await pg.locator("#gaveta .gv-pagina").focus()
        await pg.keyboard.press("Enter")
    else:
        await pg.locator("#gaveta .gv-pagina").click()
    return True
