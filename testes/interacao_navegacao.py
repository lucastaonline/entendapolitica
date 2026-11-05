"""Navegação, entradas e leitura no site inteiro (frente ui-r9): a pesquisa, os filtros, a aba, quantos "Ver todos"/"Mostrar
mais" estavam abertos e a rolagem voltam depois de abrir um perfil (ou uma votação) e voltar (Voltar do navegador e o "◀ Voltar"
do perfil); a barra do topo com menus suspensos (idioma, letra e leitura, menu do site: mouse, toque, teclado, Esc, clique
fora; o idioma e a letra ficam guardados; interruptores com role="switch"); o caminho "Você está aqui"; os campos de escolha
(sem texto selecionado ao entrar, o "Escolha…" não é opção, a lista fica por cima do rodapé, ✓ na mesma linha, ×, teclado);
o mapa dos estados (toque, teclado, setas, nome à vista sem mouse, sem contorno em volta do mapa inteiro ao clicar fora); as
abas do estado, da cidade e do perfil; os enfeites 3D do fundo nunca por cima de texto, campo ou botão (de 320 a 1920 px);
320 px sem rolar para os lados; nenhum pedido a um servidor novo; nenhum erro de JavaScript.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/). Uso: python testes/interacao_navegacao.py"""
import asyncio
import json
import os
import sys
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright

from ajuda_abas import pagina_inteira  # site-d-r13: o cartão de uma lista abre a gaveta; o perfil fica no “Ver a página inteira”

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8775/
LOCAL = urlparse(BASE).hostname
sys.stdout.reconfigure(encoding="utf-8")
RES = []
CDN = ("fontawesome", "jsdelivr", "unpkg", "cdnjs", "webawesome.com", "googleapis", "gstatic", "cloudflare")
PAGINAS = ["index.html", "entenda.html", "brasil.html", "estado.html", "estado.html?uf=SP", "cidade.html", "cidade.html?ibge=3550308",
           "pessoa.html?id=dep-178866", "votacoes.html", "votacao.html?casa=camara&id=2236186-60", "dados.html", "imparcialidade.html", "404.html"]


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


async def ctx_novo(nav, **op):
    ctx = await nav.new_context(**op)
    # quem nunca escolheu o idioma e usa o navegador em inglês vê um aviso de idioma em cima da página: aqui, já escolheu
    await ctx.add_init_script("try{if(!localStorage.getItem('ep-lang'))localStorage.setItem('ep-lang','pt')}catch(e){}")
    return ctx


def q(url, k):
    return (parse_qs(urlparse(url).query).get(k) or [None])[0]


async def espera(pg, ms=1500):
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(ms)


async def foco(pg):
    return await pg.evaluate("""(() => { const a = document.activeElement; if (!a || a === document.body) return null;
      const r = a.getBoundingClientRect(); return { href: a.getAttribute('href'), id: a.id, vis: r.top >= 0 && r.bottom <= innerHeight + 2, cls: a.className }; })()""")


async def abre_card_e_volta(pg, card, como="navegador"):
    """Clica num cartão (pessoa ou votação), espera a outra página e volta (pelo navegador ou pelo ◀ Voltar do perfil)."""
    await card.scroll_into_view_if_needed()
    href = await card.get_attribute("href")
    await card.click()
    await pagina_inteira(pg, 1200)  # site-d-r13: nas listas do Brasil, do estado e da cidade, o cartão abre a gaveta primeiro
    await pg.wait_for_url(lambda u: href.split("?")[0] in u, timeout=15000)
    await espera(pg, 900)
    if como == "navegador":
        await pg.go_back()
    else:
        await pg.locator("#voltar-lista").click()
    await pg.wait_for_timeout(500)
    await espera(pg, 2200)
    return href


# ------------------------------------------------------------------ 1. a pesquisa e os filtros voltam
async def volta(pg):
    print("\n— 1. pesquisa, filtros, aba, listas abertas e rolagem voltam depois de abrir um perfil —")
    # busca geral da página do Brasil (site-d-r13: a página inicial não tem mais campo próprio; a busca dela é a busca rápida, abaixo)
    for pag in ("brasil.html",):
        await pg.goto(BASE + pag + "?lang=pt", wait_until="networkidle")
        await pg.locator("#busca").fill("silva")
        await pg.wait_for_timeout(1300)
        ok(f"{pag}: a pesquisa vai para o endereço (?q=silva)", q(pg.url, "q") == "silva", pg.url.split("/")[-1])
        n0 = await pg.locator("#resultados a").count()
        card = pg.locator("#resultados a").nth(2)
        href = await abre_card_e_volta(pg, card)
        val = await pg.locator("#busca").input_value()
        n1 = await pg.locator("#resultados a").count()
        f = await foco(pg)
        ok(f"{pag}: depois de abrir um perfil e voltar, a pesquisa e os resultados estão lá", val == "silva" and n1 == n0 and n0 > 3, f"'{val}' {n0}→{n1}")
        ok(f"{pag}: o foco volta para quem foi aberto (à vista)", f and f["href"] == href and f["vis"], str(f))
    # página inicial: a busca rápida (o campo grande) também volta como estava
    await pg.goto(BASE + "index.html?lang=pt", wait_until="networkidle")
    await pg.locator(".ini-busca").click()
    await pg.locator("#br-q").fill("silva")
    await pg.wait_for_timeout(1300)
    n0 = await pg.locator("#br-lista [role=option]").count()
    op = pg.locator('#br-lista [role=option][data-tipo="pessoa"]').nth(2)
    href = await op.get_attribute("href")
    await op.click()
    await pg.wait_for_url(lambda u: href in u, timeout=15000)
    await espera(pg, 900)
    await pg.go_back()
    await espera(pg, 2200)
    r = await pg.evaluate("""() => ({ aberta: document.getElementById('busca-rapida').open, q: document.getElementById('br-q').value, n: document.querySelectorAll('#br-lista [role=option]').length,
      ativo: (document.getElementById(document.getElementById('br-q').getAttribute('aria-activedescendant') || '_') || { getAttribute: () => null }).getAttribute('href') })""")
    ok("index.html: depois de abrir um perfil pela busca e voltar, a busca, os resultados e quem foi aberto estão lá", r["aberta"] and r["q"] == "silva" and r["n"] == n0 and r["ativo"] == href, str(r))
    await pg.keyboard.press("Escape")
    await pg.keyboard.press("Escape")
    # endereço com ?q= (compartilhável)
    await pg.goto(BASE + "index.html?lang=pt&q=lula", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    ok("link com ?q=lula já abre com a pesquisa feita", await pg.locator("#br-q").input_value() == "lula" and await pg.locator('#br-lista a[href*="pres-lula"]').count() > 0)

    # filtros do Senado (aba), com o "Ver todos" aberto
    await pg.goto(BASE + "brasil.html?lang=pt#senado", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    part = pg.locator("#senado .f-partido-campo, #senado .combo input").nth(1)
    await pg.locator("#senado .f-nome").fill("a")
    await pg.wait_for_timeout(600)
    await part.click()
    await pg.keyboard.type("PL", delay=40)
    await pg.wait_for_timeout(500)
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(700)
    if await pg.locator("#senado .ver-mais").count():
        await pg.locator("#senado .ver-mais").click()
        await pg.wait_for_timeout(600)
    cont0 = await pg.locator("#senado .contagem").inner_text()
    n0 = await pg.locator("#senado .pessoa-card").count()
    url0 = pg.url
    ok("Senado: nome e partido vão para o endereço", q(url0, "senado-nome") == "a" and q(url0, "senado-partido") == "PL", url0.split("/")[-1])
    card = pg.locator("#senado .pessoa-card").nth(n0 - 1)
    href = await abre_card_e_volta(pg, card)
    cont1 = await pg.locator("#senado .contagem").inner_text()
    n1 = await pg.locator("#senado .pessoa-card").count()
    ativa = await pg.evaluate("EP.abas && EP.abas.ativa()")
    f = await foco(pg)
    ok("Senado: voltando, a aba, o nome, o partido e a lista inteira estão como antes",
       ativa == "senado" and await pg.locator("#senado .f-nome").input_value() == "a" and (await part.input_value()).startswith("PL") and cont1 == cont0 and n1 == n0,
       f"{ativa} | {cont1} | {n0}→{n1}")
    ok("Senado: foco no cartão aberto", f and f["href"] == href, str(f))

    # Câmara: "Ver todos" aberto e alguém lá embaixo (pelo ◀ Voltar do perfil, depois de trocar de aba no perfil)
    await pg.goto(BASE + "brasil.html?lang=pt#camara", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    await pg.locator("#camara .ver-mais").click()
    await pg.wait_for_timeout(800)
    n0 = await pg.locator("#camara .pessoa-card").count()
    card = pg.locator("#camara .pessoa-card").nth(300)
    await card.scroll_into_view_if_needed()
    href = await card.get_attribute("href")
    await card.click()
    await pagina_inteira(pg)  # site-d-r13: o cartão abre a gaveta; o perfil fica no “Ver a página inteira”
    await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
    await espera(pg, 900)
    # troca de aba no perfil duas vezes (passos no histórico) e usa o ◀ Voltar
    for aba in ("propostas", "votacoes"):
        t = pg.locator(f'.abas-lista [role=tab][data-aba="{aba}"]')
        if await t.count():
            await t.click()
            await pg.wait_for_timeout(400)
    await pg.locator("#voltar-lista").click()
    await pg.wait_for_url("**/brasil.html*", timeout=15000)
    await espera(pg, 2500)
    n1 = await pg.locator("#camara .pessoa-card").count()
    f = await foco(pg)
    ok("◀ Voltar do perfil (depois de trocar de aba lá) volta de uma vez para a Câmara, com todos os 513 e o foco no cartão",
       "brasil.html" in pg.url and n1 == n0 and f and f["href"] == href and f["vis"], f"{pg.url.split('/')[-1]} {n0}→{n1} {f}")

    # estado: filtro e "Ver todos" nos deputados federais (aba)
    await pg.goto(BASE + "estado.html?uf=SP&lang=pt#federais", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    await pg.locator("#federais .f-nome").fill("ma")
    await pg.wait_for_timeout(600)
    if await pg.locator("#federais .ver-mais").count():
        await pg.locator("#federais .ver-mais").click()
        await pg.wait_for_timeout(500)
    n0 = await pg.locator("#federais .pessoa-card").count()
    card = pg.locator("#federais .pessoa-card").nth(n0 - 1)
    href = await abre_card_e_volta(pg, card)
    n1 = await pg.locator("#federais .pessoa-card").count()
    f = await foco(pg)
    ok("estado SP (aba Deputados federais): voltando, o filtro e a lista inteira estão lá, foco no cartão",
       await pg.evaluate("EP.abas.ativa()") == "federais" and await pg.locator("#federais .f-nome").input_value() == "ma" and n1 == n0 and f and f["href"] == href,
       f"{n0}→{n1} {f}")

    # cidade: filtro de partido dos vereadores (aba)
    await pg.goto(BASE + "cidade.html?ibge=3550308&lang=pt#camara-mun", wait_until="networkidle")
    await pg.wait_for_timeout(1800)
    campo = pg.locator("#camara-mun .combo input").first
    await campo.click()
    await pg.keyboard.type("PT", delay=40)
    await pg.wait_for_timeout(500)
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(600)
    cont0 = await pg.locator("#camara-mun .contagem").inner_text()
    card = pg.locator("#camara-mun .pessoa-card").first
    await abre_card_e_volta(pg, card)
    cont1 = await pg.locator("#camara-mun .contagem").inner_text()
    ok("cidade de São Paulo (aba Câmara Municipal): voltando, o filtro de partido continua", cont1 == cont0 and (await campo.input_value()).startswith("PT"), cont1)

    # votacoes.html: pesquisa, filtro e "Mostrar mais"; abre uma votação e volta
    await pg.goto(BASE + "votacoes.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    await pg.locator("#f-q").fill("lei")
    await pg.wait_for_timeout(800)
    await pg.locator("#ver-mais-vot").click()
    await pg.wait_for_timeout(600)
    n0 = await pg.locator("#lista-votacoes .vot-tit a").count()
    card = pg.locator("#lista-votacoes .vot-tit a").nth(n0 - 2)
    await abre_card_e_volta(pg, card)
    n1 = await pg.locator("#lista-votacoes .vot-tit a").count()
    ok("votações: voltando de uma votação, a pesquisa e o 'Mostrar mais' estão como antes", await pg.locator("#f-q").input_value() == "lei" and n1 == n0, f"{n0}→{n1}")

    # votação: "Quem votou o quê" com filtro de voto
    await pg.goto(BASE + "votacao.html?casa=camara&id=2236186-60&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    v = pg.locator("#quem .combo input").first
    await v.click()
    await pg.keyboard.type("Não", delay=40)
    await pg.wait_for_timeout(400)
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(600)
    cont0 = await pg.locator("#contagem-quem").inner_text()
    card = pg.locator("#lista-quem a.pessoa-card").first
    await abre_card_e_volta(pg, card)
    ok("votação: voltando de um perfil, o filtro de voto continua", await pg.locator("#contagem-quem").inner_text() == cont0 and "Não" in await v.input_value(), cont0)

    # perfil: filtro das propostas e das votações (aba Como votou) voltam depois de abrir uma votação
    await pg.goto(BASE + "pessoa.html?id=dep-178866&lang=pt#votacoes", wait_until="networkidle")
    await pg.wait_for_timeout(2000)
    b = pg.locator('[data-vcat="principal"]')
    if await b.count():
        await b.click()
        await pg.wait_for_timeout(400)
    if await pg.locator("#ver-mais-votos").count():
        await pg.locator("#ver-mais-votos").click()
        await pg.wait_for_timeout(400)
    n0 = await pg.locator("#lista-votos > li").count()
    card = pg.locator('#lista-votos a[href^="votacao.html"]').nth(n0 - 3)
    await abre_card_e_volta(pg, card)
    n1 = await pg.locator("#lista-votos > li").count()
    ok("perfil: voltando de uma votação, a aba 'Como votou', o tipo escolhido e o 'Mostrar mais' estão como antes",
       await pg.evaluate("EP.abas.ativa()") == "votacoes" and await pg.get_attribute('[data-vcat="principal"]', "aria-pressed") == "true" and n1 == n0, f"{n0}→{n1}")
    await pg.goto(BASE + "pessoa.html?id=dep-178866&lang=pt#propostas", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    await pg.locator("#busca-prop").fill("saúde")
    await pg.wait_for_timeout(600)
    cont0 = await pg.locator("#contagem-prop").inner_text()
    await pg.goto(BASE + "dados.html?lang=pt", wait_until="networkidle")
    await pg.go_back()
    await espera(pg, 1500)
    ok("perfil: a pesquisa nas propostas volta (Voltar do navegador)", await pg.locator("#busca-prop").input_value() == "saúde" and await pg.locator("#contagem-prop").inner_text() == cont0, cont0)

    # rolagem: lá embaixo de uma lista, sai por um link do menu e volta
    await pg.goto(BASE + "brasil.html?lang=pt#camara", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    await pg.locator("#camara .ver-mais").click()
    await pg.wait_for_timeout(600)
    await pg.evaluate("window.scrollTo(0, 9000)")
    await pg.wait_for_timeout(400)
    y0 = await pg.evaluate("scrollY")
    # site-d-r13: o ☰ menu do topo virou o menu lateral (a porta 3 leva ao estado)
    await pg.locator('#casca-lado a[data-porta="3"]').click()
    await pg.wait_for_url("**/estado.html*")
    await espera(pg, 600)
    await pg.go_back()
    await espera(pg, 2500)
    y1 = await pg.evaluate("scrollY")
    ok("rolagem: voltando, a página fica no mesmo lugar (lista aberta inteira)", abs(y1 - y0) < 60 and await pg.locator("#camara .pessoa-card").count() > 500, f"{y0}→{y1}")


# ------------------------------------------------------------------ 2. menus do topo
async def menus(nav):
    print("\n— 2. barra do topo: menus suspensos, idioma, letra, interruptores, caminho —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    await pg.goto(BASE + "estado.html?uf=BA&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1000)
    ids = ["menu-idioma", "menu-leitura"]  # site-d-r13: o ☰ menu do topo virou o menu lateral; idioma e Leitura ficam no pé dele
    for i in ids:
        b = pg.locator(f"#{i}-btn")
        ok(f"{i}: botão com aria-expanded e aria-controls, painel escondido", await b.get_attribute("aria-expanded") == "false" and await b.get_attribute("aria-controls") == i and await pg.locator(f"#{i}").is_hidden())
    # mouse
    await pg.click("#menu-leitura-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("clique abre o menu Leitura", await pg.locator("#menu-leitura").is_visible() and await pg.get_attribute("#menu-leitura-btn", "aria-expanded") == "true")
    await pg.click("#menu-idioma-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("abrir outro menu fecha o primeiro", await pg.locator("#menu-leitura").is_hidden() and await pg.locator("#menu-idioma").is_visible())
    await pg.mouse.click(860, 30)  # site-d-r13: um ponto vazio da barra do topo
    await pg.wait_for_timeout(250)
    ok("clicar fora fecha", await pg.locator("#menu-idioma").is_hidden())
    # teclado
    await pg.focus("#menu-idioma-btn")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("Enter abre", await pg.locator("#menu-idioma").is_visible())
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    f = await pg.evaluate("document.activeElement.id")
    ok("Esc fecha e devolve o foco ao botão", await pg.locator("#menu-idioma").is_hidden() and f == "menu-idioma-btn", f)
    await pg.keyboard.press("ArrowDown")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    f1 = await pg.evaluate("document.activeElement.textContent.trim()")
    await pg.keyboard.press("ArrowDown")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    f2 = await pg.evaluate("document.activeElement.textContent.trim()")
    ok("seta para baixo abre e vai para o 1º item; outra seta vai para o 2º", "Português" in f1 and "English" in f2, f"{f1} | {f2}")
    cur = await pg.locator('#casca-lado [data-porta][aria-current]').inner_text()
    ok("menu do site marca a parte atual (aria-current)", "estado" in cur, cur)
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    # Tab para fora fecha
    await pg.focus("#menu-idioma-btn")
    await pg.keyboard.press("Space")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("espaço abre o menu de idioma", await pg.locator("#menu-idioma").is_visible())
    n = await pg.locator("#menu-idioma a, #menu-idioma button").count()
    for _ in range(n + 1):
        await pg.keyboard.press("Tab")
        await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("Tab para fora do painel fecha o menu", await pg.locator("#menu-idioma").is_hidden())
    # interruptores (role=switch) e tamanho da letra, guardados
    await pg.click("#menu-leitura-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    sw = pg.locator('#menu-leitura [role="switch"]')
    ok("Leitura: 3 interruptores (role=switch; o do Basecoat é um input com role=switch), nenhum checkbox", await sw.count() == 3
       and await pg.locator('#menu-leitura input[type="checkbox"]:not([role="switch"]), #menu-leitura [role="checkbox"]').count() == 0)
    await pg.locator('#menu-leitura [data-a11y="contraste"]').focus()
    await pg.keyboard.press("Space")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("espaço liga o alto contraste (o interruptor marcado e a classe na página)", await pg.locator('#menu-leitura [data-a11y="contraste"]').is_checked()
       and await pg.evaluate("document.documentElement.classList.contains('alto-contraste')"))
    await pg.keyboard.press("Space")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.click('#menu-leitura [data-escala="1.3"]')
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    esc = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--escala').trim()")
    ok("Tamanho 'Bem maior' muda a letra (--escala 1.3) e fica marcado", esc == "1.3" and await pg.get_attribute('#menu-leitura [data-escala="1.3"]', "aria-pressed") == "true", esc)
    await pg.reload(wait_until="domcontentloaded")
    esc2 = await pg.evaluate("document.documentElement.style.getPropertyValue('--escala')")
    ok("a letra fica guardada (ep-a11y) e o script do <head> aplica antes de pintar", esc2 == "1.3" and json.loads(await pg.evaluate("localStorage.getItem('ep-a11y')")).get("escala") == 1.3, esc2)
    await pg.wait_for_timeout(800)
    await pg.click("#menu-leitura-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.click('#menu-leitura [data-escala="1"]')
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    # ouvir sempre à vista
    ok("🔊 Ouvir fica à vista na barra (fora dos menus)", await pg.locator("header.topo > .ferramentas-topo > #btn-ouvir").is_visible())
    # idioma: troca, guarda e mantém aba, pesquisa e filtros
    await pg.goto(BASE + "brasil.html?lang=pt#senado", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    await pg.locator("#senado .f-nome").fill("ana")
    await pg.wait_for_timeout(600)
    await pg.click("#menu-idioma-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    cur = await pg.locator('#menu-idioma [aria-checked="true"]').inner_text()
    ok("menu de idioma marca o atual (Português)", "Português" in cur, cur)
    await pg.click('#menu-idioma [data-idioma="en"]')
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.wait_for_url("**lang=en**")
    await espera(pg, 1500)
    ok("English: mesma página, mesma aba e mesmo filtro, em inglês", await pg.evaluate("document.documentElement.lang") == "en" and "#senado" in pg.url
       and q(pg.url, "senado-nome") == "ana" and await pg.locator("#senado .f-nome").input_value() == "ana", pg.url.split("/")[-1])
    ok("o idioma fica guardado (ep-lang)", await pg.evaluate("localStorage.getItem('ep-lang')") == "en")
    await pg.goto(BASE + "dados.html", wait_until="networkidle")
    ok("outra página abre em inglês sem ?lang", await pg.evaluate("document.documentElement.lang") == "en" and "EN" in await pg.locator("#menu-idioma-btn").inner_text())
    await pg.click("#menu-idioma-btn")
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.click('#menu-idioma [data-idioma="pt"]')
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.wait_for_url("**lang=pt**")
    # caminho
    # site-d-r16 (pedido do Lucas, 14h35): a lista de votações é parte de “Como votaram”, na página do Brasil
    for url, partes in (("estado.html?uf=BA", ["Início", "Estados", "Bahia"]), ("cidade.html?ibge=2927408", ["Início", "Bahia", "Salvador"]),
                        ("pessoa.html?id=dep-178866", ["Início", "A política do Brasil", "Luizianne Lins"]),
                        ("votacoes.html", ["Início", "A política do Brasil", "Como votaram", "Todas as votações"]),
                        ("dados.html", ["Início", "De onde vêm os dados"])):
        await pg.goto(BASE + url + ("&" if "?" in url else "?") + "lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        t = [x.replace("🏠", "").strip() for x in await pg.locator("#trilha li").all_inner_texts()]
        atual = await pg.locator('#trilha [aria-current="page"]').count()
        ok(f"caminho em {url}: {' › '.join(partes)}", [x.strip() for x in t] == partes and atual == 1, " › ".join(t))
    await ctx.close()

    # toque e 320 px
    ctx = await ctx_novo(nav, viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto(BASE + "pessoa.html?id=dep-178866&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    alvos = await pg.evaluate("""[...document.querySelectorAll('header.topo a, header.topo button')].filter(b => b.getClientRects().length && !b.closest('.menu-painel'))
      .map(b => { const r = b.getBoundingClientRect(); return [b.id || b.textContent.trim().slice(0, 8), Math.round(r.width), Math.round(r.height), Math.round(r.right)]; })""")
    ok("320 px: a barra cabe (nada passa da tela) e todo botão tem pelo menos 44×44", all(a[1] >= 44 and a[2] >= 44 and a[3] <= 320 for a in alvos)
       and await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), str(alvos))
    # site-d-r13: a Leitura e o idioma ficam no pé do menu (no celular, o ☰ Menu da barra de baixo abre o menu)
    await pg.locator("#casca-menu-btn").tap()
    await pg.wait_for_timeout(400)
    await pg.locator("#menu-leitura-btn").tap()
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("toque abre o menu Leitura", await pg.locator("#menu-leitura").is_visible())
    larg = await pg.evaluate("(() => { const r = document.getElementById('menu-leitura').getBoundingClientRect(); return [r.left, r.right]; })()")
    ok("no celular, o painel cabe na tela", larg[0] >= 0 and larg[1] <= 320, str(larg))
    await pg.locator('#menu-leitura [data-a11y="espaco"]').tap()
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("toque liga 'Mais espaço no texto'", await pg.evaluate("document.documentElement.classList.contains('espacado')"))
    await pg.locator('#menu-leitura [data-a11y="espaco"]').tap()
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    await pg.locator("#menu-leitura [data-fecha-menu]").tap()
    await pg.wait_for_timeout(250)  # os painéis do Basecoat aparecem e somem com uma transição curta
    ok("o botão ✕ Fechar do painel fecha e devolve o foco ao botão do menu", await pg.locator("#menu-leitura").is_hidden() and await pg.evaluate("document.activeElement.id") == "menu-leitura-btn")
    # o idioma: fora da barra do topo (que cabe numa linha só), dentro do menu
    ok("320 px: o botão de idioma não fica na barra do topo", not await pg.evaluate("!!document.querySelector('header.topo #menu-idioma-btn')"))
    await pg.locator("#menu-idioma-btn").tap()
    await pg.wait_for_timeout(250)
    ok("320 px: o menu tem Português e English", await pg.locator('#menu-idioma [data-idioma="en"]').is_visible() and await pg.locator('#menu-idioma [data-idioma="pt"]').is_visible())
    t = await pg.evaluate("(() => { const r = document.getElementById('cl-portas-t').getBoundingClientRect(); return [r.left + 10, r.top + r.height / 2]; })()")
    await pg.touchscreen.tap(t[0], t[1])  # um título do menu (fora do painel, sem link)
    await pg.wait_for_timeout(250)
    ok("tocar fora fecha", await pg.locator("#menu-idioma").is_hidden())
    await ctx.close()


# ------------------------------------------------------------------ 3. campos de escolha
async def combos(nav):
    print("\n— 3. campos de escolha (EP.combo) —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    await pg.goto(BASE + "estado.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    c = pg.locator("#sel-uf-campo")
    await c.scroll_into_view_if_needed()
    await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    await pg.wait_for_timeout(300)
    await c.click()
    await pg.wait_for_timeout(500)
    ops = await pg.locator("#sel-uf-campo-lista [role=option]").all_inner_texts()
    ok("estado: o 'Escolha um estado…' não é opção (é o placeholder) e a lista tem os 27", len(ops) == 27 and not any("Escolha" in o for o in ops)
       and "estado" in (await c.get_attribute("placeholder") or ""), f"{len(ops)} opções")
    meio = await pg.evaluate("""(() => { const l = document.getElementById('sel-uf-campo-lista'); const r = l.getBoundingClientRect();
      const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return [!!(e && l.contains(e)), getComputedStyle(l.closest('.combo-pop')).backgroundColor, Math.round(r.bottom), innerHeight]; })()""")
    ok("a lista fica por cima de tudo (elementFromPoint no meio dela é a própria lista) e tem fundo branco", meio[0] and meio[1] == "rgb(255, 255, 255)", str(meio))
    await pg.keyboard.press("Escape")
    # Ver outro mandato: sem texto selecionado ao entrar, ✓ na mesma linha, digitar começa busca nova, ×
    await pg.goto(BASE + "estado.html?uf=BA&lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    m = pg.locator(".mandato-campo input")
    await m.click()
    await pg.wait_for_timeout(400)
    sel = await m.evaluate("i => [i.selectionStart, i.selectionEnd, i.value.length, String(getSelection())]")
    ok("mandato: ao entrar no campo, o texto não fica todo selecionado", sel[0] == sel[1] and sel[3] == "", str(sel))
    # o ✓ do Basecoat é a imagem de fundo da opção escolhida (aria-selected="true"), no meio da altura, à direita do texto
    lin = await pg.evaluate("""(() => { const li = document.querySelector('.mandato-campo li.escolhido'), cs = getComputedStyle(li), t = li.querySelector('.combo-t');
      return [li.getAttribute('aria-selected'), /svg/.test(cs.backgroundImage), cs.backgroundPositionY, t.getClientRects().length, Math.round(t.getBoundingClientRect().right), Math.round(li.getBoundingClientRect().right)]; })()""")
    ok("mandato: '2023 a 2026 (atual)' numa linha só e o ✓ na mesma linha, à direita", lin[0] == "true" and lin[1] and lin[2] == "50%" and lin[3] == 1 and lin[4] < lin[5] - 20, str(lin))
    await pg.keyboard.press("Escape")
    await m.press("End")
    await pg.keyboard.type("19")
    await pg.wait_for_timeout(400)
    ok("com uma opção escolhida, digitar começa uma busca nova (não vira '2023 a 2026 (atual)19')", await m.input_value() == "19", await m.input_value())
    ops = await pg.locator(".mandato-campo [role=option]").all_inner_texts()
    ok("… e a lista filtra ('19' acha 2019 a 2022 e os da década de 1990)", ops and all("19" in o for o in ops), " | ".join(ops[:4]))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    ok("Esc fecha e volta ao texto escolhido", "2026" in await m.input_value() and await pg.locator(".mandato-campo .combo-lista").is_hidden())
    ok("mandato: explicação curta à vista e o resto num bloco que abre", await pg.locator(".mandato-box details.mandato-mais").count() == 1
       and len(await pg.locator(".mandato-box .mandato-dica").inner_text()) < 70)
    # filtro com "Todos": × aparece só com escolha, limpa e volta para Todos
    await pg.goto(BASE + "brasil.html?lang=pt#senado", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    part = pg.locator("#senado .combo").nth(1)
    inp = part.locator("input")
    ok("filtro de partido começa em 'Todos os partidos' sem ×", await inp.input_value() == "Todos os partidos" and await part.locator(".combo-limpa").is_hidden())
    await inp.focus()
    await pg.keyboard.press("ArrowDown")
    await pg.wait_for_timeout(300)
    ok("seta para baixo abre a lista e marca uma opção (aria-activedescendant)", await inp.get_attribute("aria-expanded") == "true" and bool(await inp.get_attribute("aria-activedescendant")))
    await pg.keyboard.type("PT")
    await pg.wait_for_timeout(300)
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(500)
    ok("Enter escolhe PT; aparece o × para limpar", (await inp.input_value()).startswith("PT") and await part.locator(".combo-limpa").is_visible())
    nome = await part.locator(".combo-limpa").get_attribute("aria-label")
    await part.locator(".combo-limpa").click()
    await pg.wait_for_timeout(500)
    ok("× (com nome acessível) volta para 'Todos os partidos' e deixa o foco no campo", nome and await inp.input_value() == "" and await pg.evaluate("document.activeElement.getAttribute('role')") == "combobox"
       and "81" in await pg.locator("#senado .contagem").inner_text(), f"{nome} | {await pg.locator('#senado .contagem').inner_text()}")
    await pg.keyboard.press("Escape")
    await pg.keyboard.press("Tab")
    await pg.wait_for_timeout(300)
    ok("saindo com o campo vazio, volta a mostrar 'Todos os partidos'", await inp.input_value() == "Todos os partidos", await inp.input_value())
    # cidade: lista perto do fim da tela abre para cima e não sai da tela; toque
    await ctx.close()
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto(BASE + "estado.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    c = pg.locator("#sel-uf-campo")
    await c.scroll_into_view_if_needed()
    await c.tap()
    await pg.wait_for_timeout(600)
    r = await pg.evaluate("""(() => { const i = document.getElementById('sel-uf-campo').getBoundingClientRect(), l = document.getElementById('sel-uf-campo-lista').getBoundingClientRect();
      return [Math.round(i.top), Math.round(l.top), Math.round(l.bottom), innerHeight, Math.round(l.left), Math.round(l.right)]; })()""")
    ok("celular: tocando no campo (no fim da página), a lista abre inteira dentro da tela, sem cobrir o campo", r[2] <= r[3] and r[4] >= 0 and r[5] <= 390 and (r[1] > r[0] or r[2] < r[0]), str(r))
    await pg.locator("#sel-uf-campo-lista [role=option]", has_text="Bahia").tap()
    await pg.wait_for_url("**uf=BA*", timeout=15000)
    ok("tocar numa opção abre o estado", "uf=BA" in pg.url)
    await ctx.close()


# ------------------------------------------------------------------ 4. mapa dos estados
async def mapa(nav):
    print("\n— 4. mapa dos estados —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 900})
    pg = await ctx.new_page()
    await pg.goto(BASE + "estado.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    rot = await pg.locator("#rotulo-uf").inner_text()
    ok("a dica serve para toque, mouse e teclado (sem 'Passe o mouse')", "Toque" in rot and "teclado" in rot and "mouse" not in rot.lower(), rot.replace("\n", " | "))
    svg = pg.locator("svg.mapa-br")
    await svg.scroll_into_view_if_needed()
    b = await svg.bounding_box()
    for nome, x, y in (("canto de baixo", b["x"] + 15, b["y"] + b["height"] - 15), ("canto de cima", b["x"] + 20, b["y"] + 20), ("mar", b["x"] + b["width"] - 25, b["y"] + b["height"] * .45)):
        await pg.mouse.click(x, y)
        await pg.wait_for_timeout(250)
        st = await pg.evaluate("""(() => { const s = document.querySelector('svg.mapa-br'), a = document.activeElement, cs = getComputedStyle(s);
          return [a.tagName, s.matches(':focus'), cs.outlineStyle, cs.boxShadow, [...document.querySelectorAll(':focus-visible')].length]; })()""")
        ok(f"clicar fora de um estado ({nome}) não põe foco nem contorno no mapa inteiro", st[0] != "svg" and not st[1] and st[2] == "none" and st[3] == "none" and st[4] == 0, str(st))
    # depois de usar o teclado, o clique fora também não deixa contorno
    await pg.locator('#mapa a.uf[data-uf="BA"]').focus()
    await pg.keyboard.press("Tab")
    await pg.mouse.click(b["x"] + 15, b["y"] + b["height"] - 15)
    await pg.wait_for_timeout(250)
    st = await pg.evaluate("(() => { const s = document.querySelector('svg.mapa-br'); return [document.activeElement.tagName, getComputedStyle(s).outlineStyle]; })()")
    ok("depois de usar o Tab, clicar fora também não deixa contorno no mapa", st[0] != "svg" and st[1] == "none", str(st))
    # teclado: nome à vista, borda mais forte, setas
    await pg.locator('#mapa a.uf[data-uf="MG"]').focus()
    await pg.keyboard.press("Shift+Tab")
    await pg.keyboard.press("Tab")
    await pg.wait_for_timeout(300)
    rot = await pg.locator("#rotulo-uf").inner_text()
    ok("Tab num estado: o nome aparece em cima do mapa (sem mouse) e o estado levanta com a borda do teclado",
       "Minas Gerais" in rot and await pg.locator("#mapa .realce.ligado.teclado").count() == 1, rot.replace("\n", " | "))
    await pg.keyboard.press("ArrowRight")
    d = await pg.evaluate("document.activeElement.getAttribute('data-uf')")
    await pg.keyboard.press("ArrowDown")
    d2 = await pg.evaluate("document.activeElement.getAttribute('data-uf')")
    ok("setas andam para o estado vizinho (MG → direita: ES; depois para baixo)", d == "ES" and d2 not in ("ES", "MG", None), f"{d} {d2}")
    nome = await pg.evaluate("document.activeElement.getAttribute('aria-label')")
    ok("o leitor de tela ouve o nome, a sigla e a região", "região" in (nome or ""), nome)
    await pg.keyboard.press("Enter")
    await pg.wait_for_url("**estado.html?uf=*", timeout=15000)
    ok("Enter abre o estado", f"uf={d2}" in pg.url, pg.url.split("/")[-1])
    await ctx.close()
    # toque
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto(BASE + "estado.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    ok("celular: a dica aparece (antes ficava escondida em telas de toque)", await pg.locator("#rotulo-uf").is_visible())
    await pg.locator('#mapa a.uf[data-uf="MG"] path').tap()
    await pg.wait_for_url("**uf=MG*", timeout=15000)
    ok("celular: tocar num estado abre o estado", "uf=MG" in pg.url)
    await ctx.close()


# ------------------------------------------------------------------ 5. abas do estado, da cidade e do perfil
async def abas(nav):
    print("\n— 5. abas do estado, da cidade e do perfil —")
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    # ui-r9 (decisão do Lucas, 11h57): "Quem assume em 2027" deixou de ser aba (é o mandato 2027 do "Ver outro mandato")
    # site-d-r16: a aba nova "Como votaram" (#votacoes) no estado e na cidade
    for url, esperadas in (("estado.html?uf=SP", ["governo", "senadores", "federais", "estaduais", "votacoes", "cidade"]),
                           ("cidade.html?ibge=3550308", ["governo-cidade", "camara-mun", "votacoes", "proxima-eleicao", "papeis"]),
                           ("pessoa.html?id=dep-178866", ["sobre", "trajetoria", "propostas", "votacoes", "gastos", "fontes"])):
        await pg.goto(BASE + url + "&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        nomes = await pg.locator(".abas-lista [role=tab]").evaluate_all("l => l.filter(t => !t.hidden).map(t => t.getAttribute('data-aba'))")
        ok(f"{url}: abas {', '.join(esperadas)}", nomes == esperadas, str(nomes))
        await pg.goto(BASE + url + "&lang=pt#" + esperadas[2], wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        ok(f"{url}#{esperadas[2]}: o endereço abre a aba certa", await pg.evaluate("EP.abas.ativa()") == esperadas[2])
        sw = await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        ok(f"{url}: nada rola para os lados (390 px)", sw)
    # o resumo e o "Ver todos" no estado
    await pg.goto(BASE + "estado.html?uf=SP&lang=pt#estaduais", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    n = await pg.locator("#estaduais .pessoa-card").count()
    bt = await pg.locator("#estaduais .ver-mais").inner_text()
    await pg.locator("#estaduais .ver-mais").click()
    await pg.wait_for_timeout(600)
    n2 = await pg.locator("#estaduais .pessoa-card").count()
    ok("estado: deputados estaduais começam com um resumo de 12 e 'Ver todos' mostra todos", n == 12 and "Ver todos" in bt and n2 > 60, f"{n} → {n2} ({bt.strip()})")
    ok("estado: a lista de todos os partidos continua inteira", await pg.locator("#estaduais .barra-partido:not([hidden])").count() == await pg.locator("#estaduais .barra-partido").count())
    # "Quem assume em 2027" no estado: aviso nas abas de hoje e o mandato 2027 no "Ver outro mandato"
    av = await pg.locator("#estaduais .aviso-futuro a").get_attribute("href") if await pg.locator("#estaduais .aviso-futuro a").count() else ""
    ok("estado: aviso “Veja quem assume em 2027” na aba da Assembleia, com link para o mandato 2027 (na mesma aba)", av.endswith("mandato=2027#estaduais"), av)
    await pg.goto(BASE + "estado.html?uf=SP&lang=pt#quem-assume", wait_until="networkidle")
    await pg.wait_for_timeout(1800)
    # mandatos-r11: o mandato 2027 tem as mesmas abas de hoje, com a faixa amarela "Você está vendo"
    await pg.evaluate("EP.abas.mostra('senadores')")
    await pg.wait_for_timeout(800)
    ok("estado: o endereço antigo #quem-assume abre o mandato 2027 (as mesmas abas, com a faixa e o campo em 2027)",
       "mandato=2027" in pg.url and await pg.locator(".abas-grupo").count() == 1 and await pg.locator("#faixa-mandato").is_visible()
       and await pg.locator(".mandato-campo input").input_value() == "2027 a 2030 (eleitos em 2026)" and await pg.locator("#lista-sen .pessoa-card").count() > 0, pg.url.split("/")[-1])
    sw = await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    ok("estado no mandato 2027: nada rola para os lados (390 px)", sw)
    await ctx.close()


# ------------------------------------------------------------------ 6. enfeites do fundo nunca por cima de texto
ENFEITES_JS = """async () => {
  const sobre = [];
  const formas = () => [...document.querySelectorAll('.formas.fundo-fixo .forma')].filter(f => !f.hidden && f.getClientRects().length).map(f => f.getBoundingClientRect());
  function textos() {
    const r = [];
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: n => n.nodeValue.trim() ? 1 : 2 });
    let n;
    while ((n = w.nextNode())) {
      const el = n.parentElement;
      if (!el || el.closest('.formas, [hidden], script, style, .sr') || getComputedStyle(el).visibility === 'hidden') continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const q of rg.getClientRects()) if (q.width > 1 && q.height > 1 && q.bottom > 0 && q.top < innerHeight) r.push([q, el.tagName + '.' + el.className]);
    }
    for (const el of document.querySelectorAll('input, select, textarea, button, a[href], [role=combobox], [role=tab]')) {
      if (!el.getClientRects().length || el.closest('[hidden]') || getComputedStyle(el).visibility === 'hidden') continue;
      const q = el.getBoundingClientRect();
      if (q.width > 1 && q.bottom > 0 && q.top < innerHeight) r.push([q, el.tagName + '#' + el.id]);
    }
    return r;
  }
  const H = document.documentElement.scrollHeight;
  for (let y = 0; y < H; y += Math.max(300, innerHeight * 0.8)) {
    scrollTo(0, y);
    await new Promise(r => setTimeout(r, 60));
    const fs = formas();
    if (!fs.length) continue;
    for (const [t, nome] of textos()) for (const f of fs)
      if (t.left < f.right && t.right > f.left && t.top < f.bottom && t.bottom > f.top) { sobre.push([Math.round(y), nome.slice(0, 40)]); break; }
    if (sobre.length > 5) break;
  }
  scrollTo(0, 0);
  return [sobre, document.querySelectorAll('.formas.fundo-fixo .forma:not([hidden])').length];
}"""


async def enfeites(nav):
    print("\n— 6. enfeites 3D do fundo nunca por cima de texto, campo ou botão —")
    for w in (320, 390, 768, 1024, 1280, 1366, 1600, 1920):
        ctx = await ctx_novo(nav, viewport={"width": w, "height": 800 if w > 500 else 760}, is_mobile=w < 500, has_touch=w < 500)
        pg = await ctx.new_page()
        ruins, vistos = [], 0
        for pag in ("index.html", "brasil.html", "estado.html", "estado.html?uf=SP", "cidade.html?ibge=3550308", "votacoes.html", "dados.html", "imparcialidade.html"):
            await pg.goto(BASE + pag, wait_until="networkidle")
            await pg.wait_for_timeout(900)
            await pg.evaluate("document.querySelectorAll('.rev,.r3d').forEach(e => e.classList.add('visivel')); document.documentElement.style.scrollBehavior = 'auto'")
            sobre, n = await pg.evaluate(ENFEITES_JS)
            vistos += n
            if sobre:
                ruins.append(f"{pag}: {sobre[:2]}")
        ok(f"{w} px: nenhum enfeite por cima de texto/campo/botão em 8 páginas ({vistos} enfeites à vista)", not ruins, "; ".join(ruins)[:300])
        await ctx.close()


# ------------------------------------------------------------------ 7. 320 px, rede e erros
async def geral(nav):
    print("\n— 7. 320 px sem rolar para os lados, nenhum servidor novo, nenhum erro —")
    ctx = await ctx_novo(nav, viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    erros, fora = [], set()
    pg.on("pageerror", lambda e: erros.append(str(e)))

    def pedido(r):
        h = urlparse(r.url).hostname
        if h and h != LOCAL and (r.resource_type != "image" or any(c in r.url for c in CDN)):
            fora.add(f"{h} ({r.resource_type})")
    pg.on("request", pedido)
    largas = []
    for pag in PAGINAS:
        for lang in ("pt", "en"):
            await pg.goto(BASE + pag + ("&" if "?" in pag else "?") + "lang=" + lang, wait_until="networkidle")
            await pg.wait_for_timeout(700)
            # site-d-r13: o ☰ Menu (barra de baixo) abre o menu lateral; a Leitura fica no pé dele
            for menu in (None, "casca-menu", "menu-leitura"):
                if menu and await pg.locator(f"#{menu}-btn").count():
                    await pg.locator(f"#{menu}-btn").tap()
                    await pg.wait_for_timeout(300)
                if not await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"):
                    largas.append(f"{pag} {lang} {menu or ''}")
            await pg.keyboard.press("Escape")
            await pg.keyboard.press("Escape")
    ok(f"320 px: {len(PAGINAS)} páginas (pt e en, com e sem menus abertos) sem rolar para os lados", not largas, ", ".join(largas))
    ok("nenhum pedido a outro servidor além das fotos dos dados (nada de CDN)", not fora, ", ".join(sorted(fora)))
    ok("nenhum erro de JavaScript", not erros, " | ".join(erros[:3]))
    await ctx.close()


# ------------------------------------------------------------------ 8. larguras, letra grande, barra das abas, 1ª abertura da lista e STF
# (retorno do Lucas às 11h57: página cortada à direita, barra de rolagem cinza nas abas, lista do "Ver outro mandato" abrindo do
# outro lado da tela na 1ª vez, setinha no alto do campo, cartões do STF cinza)
URLS_ABAS = ["index.html", "entenda.html", "dados.html", "imparcialidade.html", "404.html", "votacoes.html", "votacao.html?casa=camara&id=2236186-60",
             "estado.html", "brasil.html?mandato=2027", "estado.html?uf=SP&mandato=2027"] + \
    [f"brasil.html#{a}" for a in ("executivo", "senado", "camara", "votacoes", "judiciario")] + \
    [f"estado.html?uf=SP#{a}" for a in ("governo", "senadores", "federais", "estaduais", "votacoes", "cidade")] + \
    [f"cidade.html?ibge=3550308#{a}" for a in ("governo-cidade", "camara-mun", "votacoes", "proxima-eleicao", "papeis")] + \
    [f"pessoa.html?id=dep-178866#{a}" for a in ("sobre", "trajetoria", "propostas", "votacoes", "gastos", "fontes")]
CORTADO_JS = """() => { const W = document.documentElement.clientWidth, r = [];
  const preso = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) if (getComputedStyle(p).overflowX !== 'visible') return true; return false; };
  for (const e of document.querySelectorAll('main *, footer *, header *')) {
    if (e.closest('[aria-hidden=true], .formas, [popover], dialog')) continue;
    const q = e.getBoundingClientRect();
    if (q.width && q.right > W + 1 && getComputedStyle(e).visibility !== 'hidden' && !preso(e)) r.push(e.tagName + '.' + String(e.className.baseVal ?? e.className).slice(0, 30));
  }
  return [document.documentElement.scrollWidth - W, r.slice(0, 3)]; }"""


def com_lang(u, lang="pt"):
    base, _, h = u.partition("#")
    return base + ("&" if "?" in base else "?") + "lang=" + lang + ("#" + h if h else "")


async def larguras(nav):
    print("\n— 8. sem rolar para os lados (várias larguras e letra grande), barra das abas, 1ª abertura da lista, STF —")
    for w, esc in ((390, None), (768, None), (880, None), (1366, None), (390, 1.5), (880, 1.5)):
        ctx = await ctx_novo(nav, viewport={"width": w, "height": 800}, is_mobile=w < 600, has_touch=w < 600)
        if esc:
            await ctx.add_init_script(f"try {{ localStorage.setItem('ep-a11y', JSON.stringify({{ escala: {esc} }})) }} catch (e) {{}}")
        pg = await ctx.new_page()
        ruins = []
        for u in URLS_ABAS:
            await pg.goto("about:blank")
            await pg.goto(BASE + com_lang(u), wait_until="networkidle")
            await pg.wait_for_timeout(700)
            await pg.evaluate("document.querySelectorAll('.rev').forEach(e => e.classList.add('visivel'))")
            await pg.wait_for_timeout(150)
            d, quem = await pg.evaluate(CORTADO_JS)
            if d > 0 or quem:
                ruins.append(f"{u} +{d}px {quem}")
        ok(f"{w} px{' com a letra ' + str(esc) + '×' if esc else ''}: {len(URLS_ABAS)} páginas e abas sem rolar para os lados e sem texto cortado à direita",
           not ruins, "; ".join(ruins)[:300])
        await ctx.close()
    # a barra das abas: sem barra de rolagem à vista; a roda do mouse e as setas rolam a barra; a borda esmaece onde há mais abas
    ctx = await ctx_novo(nav, viewport={"width": 700, "height": 800})
    pg = await ctx.new_page()
    await pg.goto(BASE + "brasil.html?lang=pt#senado", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    b = await pg.evaluate("""() => { const l = document.querySelector('.abas-lista'), cs = getComputedStyle(l);
      return [l.offsetHeight - l.clientHeight - parseFloat(cs.borderTopWidth) - parseFloat(cs.borderBottomWidth), cs.scrollbarWidth, l.scrollWidth > l.clientWidth, l.className]; }""")
    ok("barra das abas sem a barra de rolagem cinza (e as abas passam da largura: dá para rolar)", b[0] == 0 and b[1] == "none" and b[2], str(b))
    caixa = await pg.locator(".abas-lista").bounding_box()
    await pg.mouse.move(caixa["x"] + 100, caixa["y"] + caixa["height"] / 2)
    antes = await pg.evaluate("document.querySelector('.abas-lista').scrollLeft")
    await pg.mouse.wheel(0, 300)
    await pg.wait_for_timeout(400)
    depois = await pg.evaluate("[document.querySelector('.abas-lista').scrollLeft, document.querySelector('.abas-lista').className]")
    ok("a roda do mouse rola a barra das abas para o lado, e a borda da esquerda esmaece", depois[0] > antes and "mais-esq" in depois[1], f"{antes} → {depois}")
    await pg.locator('.abas-lista [role=tab][data-aba="senado"]').focus()
    await pg.keyboard.press("End")
    await pg.wait_for_timeout(600)
    vis = await pg.evaluate("""() => { const t = document.querySelector('.abas-lista [aria-selected=true]').getBoundingClientRect(), l = document.querySelector('.abas-lista').getBoundingClientRect();
      return t.left >= l.left - 1 && t.right <= l.right + 1; }""")
    ok("as setas do teclado (End) levam à última aba e a barra rola até ela", vis)
    await ctx.close()
    # a lista do "Ver outro mandato" na 1ª abertura (cache vazio): ancorada no campo, no computador e no celular; setinha no meio
    for w, h, toque in ((910, 614, False), (1366, 768, False), (390, 844, True)):
        ctx = await ctx_novo(nav, viewport={"width": w, "height": h}, is_mobile=toque, has_touch=toque)
        pg = await ctx.new_page()
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="domcontentloaded")
        await pg.wait_for_selector(".mandato-campo input")
        await pg.wait_for_timeout(300)
        inp = pg.locator(".mandato-campo input")
        await inp.scroll_into_view_if_needed()
        if toque:
            await inp.tap()
        else:
            await inp.click()
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => { const c = document.querySelector('.mandato-campo .combo'), i = c.querySelector('input').getBoundingClientRect(),
            p = c.querySelector('.combo-pop'), l = p.getBoundingClientRect(), s = c.querySelector('.combo-seta').getBoundingClientRect();
          return { aberto: p.matches(':popover-open') || c.classList.contains('aberto'), campo: [Math.round(i.left), Math.round(i.right), Math.round(i.top), Math.round(i.bottom)],
            lista: [Math.round(l.left), Math.round(l.right), Math.round(l.top), Math.round(l.bottom)], W: document.documentElement.clientWidth, H: innerHeight,
            seta: Math.round((s.top + s.height / 2) - (i.top + i.height / 2)) }; }""")
        c, li = r["campo"], r["lista"]
        junto = abs(li[0] - c[0]) <= 2 or abs(li[1] - c[1]) <= 2
        encosta = abs(li[2] - c[3]) <= 10 or abs(c[2] - li[3]) <= 10
        ok(f"{w} px{' (toque)' if toque else ''}: 1ª abertura do “Ver outro mandato” abre a lista colada no campo (alinhada a ele, em cima ou embaixo, dentro da tela)",
           r["aberto"] and junto and encosta and li[0] >= 0 and li[1] <= r["W"] and li[3] <= r["H"], str(r))
        ok(f"{w} px: a setinha do campo fica no meio da altura", abs(r["seta"]) <= 1, str(r["seta"]))
        await ctx.close()
    # STF: fotos como o tribunal publica (preto e branco), mas o cartão com as cores do site; nenhuma etiqueta cinza
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 800})
    pg = await ctx.new_page()
    await pg.goto(BASE + "brasil.html?lang=pt#judiciario", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    s = await pg.evaluate("""() => { const cs = [...document.querySelectorAll('#stf .stf-card:not(.vaga)')];
      return [cs.length, document.querySelectorAll('#stf .stf-card .chip.neutro').length, cs.every(c => !!c.querySelector('.d-assento')),
        cs.every(c => /rgb\\(242, 183, 5\\)/.test(getComputedStyle(c.querySelector('.d-moldura')).boxShadow))]; }""")  # site-d-r14: moldura e assento
    ok("STF: cartões com a faixa e o anel em volta da foto nas cores do site, iguais para todos, e nenhuma etiqueta cinza", s[0] >= 10 and s[1] == 0 and s[2] and s[3], str(s))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await ctx_novo(nav, viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        so = sys.argv[1:]
        if not so or "volta" in so:
            await volta(pg)
        await ctx.close()
        if not so or "menus" in so:
            await menus(nav)
        if not so or "combos" in so:
            await combos(nav)
        if not so or "mapa" in so:
            await mapa(nav)
        if not so or "abas" in so:
            await abas(nav)
        if not so or "enfeites" in so:
            await enfeites(nav)
        if not so or "geral" in so:
            await geral(nav)
        if not so or "larguras" in so:
            await larguras(nav)
        ok("nenhum erro de JavaScript (voltas)", not erros, " | ".join(erros[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
