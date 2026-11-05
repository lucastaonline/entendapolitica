"""A casca do site no visual do protótipo D (frente site-d-r13): menu lateral com as 4 portas numeradas e os itens da seção
atual, barra de baixo no celular (o ☰ Menu abre o menu lateral como gaveta, prende o foco e deixa o resto inerte), caminho
na barra do topo, busca rápida (Ctrl+K, ⌘K, "/", botão; resultados; Enter; a pesquisa volta), idioma e Leitura no pé do
menu (guardados), 🔊 Ouvir; página inicial só com as 4 portas (sem o conteúdo delas); a gaveta (abrir e fechar, Esc, foco,
?ver=, Voltar e Avançar do navegador, gaveta sobre gaveta, "Ver a página inteira" e a volta para a lista); 320 px sem rolar
para os lados; nenhum servidor novo; axe com a busca, a gaveta e o menu do celular abertos.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/) e do axe-core em ../ferramentas.
Uso: python testes/interacao_casca.py"""
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
LOCAL = urlparse(BASE).hostname
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
PAGINAS = [("index.html", 0), ("entenda.html", 1), ("brasil.html", 2), ("estado.html", 3), ("estado.html?uf=SP", 3), ("cidade.html", 4),
           ("cidade.html?ibge=3550308", 4), ("pessoa.html?id=dep-178866", 2), ("votacoes.html", 2), ("votacao.html?casa=camara&id=2236186-60", 2),
           ("dados.html", 0), ("imparcialidade.html", 0), ("404.html", 0)]
PORTAS = ["entenda.html", "brasil.html", "estado.html", "cidade.html"]
CDN = ("fontawesome", "jsdelivr", "unpkg", "cdnjs", "webawesome.com", "googleapis", "gstatic", "cloudflare")


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def lang(u, l="pt"):
    base, _, h = u.partition("#")
    return base + ("&" if "?" in base else "?") + "lang=" + l + (("#" + h) if h else "")


def q(url, k):
    return (parse_qs(urlparse(url).query).get(k) or [None])[0]


async def ctx_novo(nav, **op):
    ctx = await nav.new_context(**op)
    await ctx.add_init_script("try{if(!localStorage.getItem('ep-lang'))localStorage.setItem('ep-lang','pt')}catch(e){}")
    return ctx


async def axe(pg, nome):
    if not AXE.exists():
        print("  (sem axe-core em ../ferramentas)")
        return
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] }, resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    ok(f"axe 0 — {nome}", not v, "; ".join(v)[:400])


# ------------------------------------------------------------------ 1. casca em todas as páginas (computador)
async def casca(nav):
    print("\n— 1. casca em todas as páginas (computador 1440 px) —")
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    for url, porta in PAGINAS:
        await pg.goto(BASE + lang(url), wait_until="networkidle")
        await pg.wait_for_timeout(900)
        r = await pg.evaluate("""() => {
          const l = document.getElementById('casca-lado'), vis = e => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
          const portas = [...document.querySelectorAll('#casca-lado .cl-portas a[data-porta]')];
          return { lado: vis(l), portas: portas.map(a => [a.getAttribute('href'), a.querySelector('.cl-num').textContent, a.getAttribute('aria-current')]),
            baixo: vis(document.querySelector('.casca-baixo')), busca: vis(document.querySelector('header.topo [data-abre-busca]')),
            ouvir: vis(document.querySelector('header.topo #btn-ouvir')), trilha: !!document.querySelector('header.topo #trilha'),
            idioma: !!document.querySelector('#casca-lado #menu-idioma-btn'), leitura: !!document.querySelector('#casca-lado #menu-leitura-btn'),
            secao: [...document.querySelectorAll('#cl-secao:not([hidden]) a .cl-txt')].map(a => a.textContent.trim()),
            atualSecao: ((document.querySelector('#cl-secao a[aria-current] .cl-txt') || {}).textContent || '').trim(),
            sobreAtual: ((document.querySelector('#casca-lado .cl-nav a[aria-current="page"]:not([data-porta]) .cl-txt') || {}).textContent || '').trim(),
            menuAntigo: !!document.querySelector('#menu-site-btn'), largura: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1 };
        }""")
        hrefs = [x[0].lstrip("/") for x in r["portas"]]
        nums = [x[1] for x in r["portas"]]
        atuais = [i + 1 for i, x in enumerate(r["portas"]) if x[2]]
        ok(f"{url}: menu lateral com as 4 portas numeradas (1 Entenda, 2 Brasil, 3 Estado, 4 Cidade)", r["lado"] and hrefs == PORTAS and nums == ["1", "2", "3", "4"], str(r["portas"]))
        ok(f"{url}: porta da seção marcada ({porta or 'nenhuma'})", atuais == ([porta] if porta else []), str(atuais))
        ok(f"{url}: busca e 🔊 Ouvir na barra do topo; idioma e Leitura no pé do menu; sem o ☰ antigo; barra de baixo escondida",
           r["busca"] and r["ouvir"] and r["idioma"] and r["leitura"] and not r["menuAntigo"] and not r["baixo"])
        interna = url.split("?")[0] not in ("index.html", "entenda.html")
        ok(f"{url}: caminho {'na barra do topo' if interna else 'não aparece (é o começo)'}", r["trilha"] == interna)
        ok(f"{url}: nada passa da tela", r["largura"])
        if url == "brasil.html":
            ok("Brasil: itens da seção = as abas (Quem governa, Senado, Câmara, Como votaram, STF), a aberta marcada",
               r["secao"][:5] == ["Quem governa", "Senado", "Câmara", "Como votaram", "STF"] and r["atualSecao"] == "Quem governa", str(r["secao"]) + " | " + r["atualSecao"])
        if url.startswith("pessoa.html"):
            ok("perfil: itens da seção = as abas do perfil", "Quem é" in r["secao"] and "O que propôs" in " ".join(r["secao"]), str(r["secao"]))
        if url == "votacoes.html":
            # site-d-r16 (pedido do Lucas, 14h35): antes, “Todas as votações” era um item a mais, marcado, só nesta página; agora a
            # lista faz parte de “Como votaram” (mesma intenção: a seção certa marcada; detalhes no bloco 8, menu estável)
            ok("votações: itens da seção = os mesmos da página do Brasil, “Como votaram” marcado",
               r["secao"] == ["Quem governa", "Senado", "Câmara", "Como votaram", "STF"] and r["atualSecao"] == "Como votaram", str(r["secao"]) + " | " + r["atualSecao"])
        if url in ("dados.html", "imparcialidade.html"):
            ok(f"{url}: sem itens de seção; a página marcada em “Sobre o site”", not r["secao"] and r["sobreAtual"], r["sobreAtual"])
        if url == "index.html":
            ok("início: sem itens de seção", not r["secao"])
    # o item da seção acompanha a aba aberta, e clicar nele troca de aba
    await pg.goto(BASE + lang("brasil.html"), wait_until="networkidle")
    await pg.wait_for_timeout(800)
    await pg.locator('#cl-secao a[data-item="senado"]').click()
    await pg.wait_for_timeout(900)
    ok("clicar em “Senado” no menu abre a aba Senado e o item fica marcado",
       await pg.evaluate("EP.abas.ativa()") == "senado" and await pg.locator('#cl-secao a[data-item="senado"]').get_attribute("aria-current") == "location")
    # perfil: a porta acompanha de onde a pessoa é (estado e cidade)
    ids = await pg.evaluate("""async () => { const r = await fetch('dados/busca.json'); const l = await r.json();
      return [ (l.find(x => /^dest-/.test(x[0])) || [])[0], (l.find(x => /^ver-|^vereador/.test(x[0]) || (x[5] && /vereador/i.test(x[2]))) || [])[0] ]; }""")
    for pid, porta in zip(ids, (3, 4)):
        if not pid:
            continue
        await pg.goto(BASE + lang("pessoa.html?id=" + pid), wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        at = await pg.evaluate("[...document.querySelectorAll('#casca-lado [data-porta][aria-current]')].map(a => +a.dataset.porta)")
        ok(f"perfil {pid}: a porta {porta} fica marcada (pelo caminho)", at == [porta], str(at))
    ok("nenhum erro de JavaScript (computador)", not erros, " | ".join(erros[:3]))
    # Entenda: nas aulas a tela é só da aula (como antes); de volta ao mapa, o menu volta
    await pg.goto(BASE + lang("entenda.html#parte-3"), wait_until="networkidle")
    await pg.wait_for_timeout(2500)
    vis = "(() => { const l = document.getElementById('casca-lado'); return l.getClientRects().length > 0; })()"
    ok("Entenda: numa aula, o menu lateral sai (a tela é só da aula)", await pg.evaluate("document.body.classList.contains('modo-aula')") and not await pg.evaluate(vis))
    await pg.locator("#aula-mapa").click()
    await pg.wait_for_timeout(1500)
    ok("Entenda: de volta ao mapa, o menu lateral volta (porta 1 marcada)", not await pg.evaluate("document.body.classList.contains('modo-aula')") and await pg.evaluate(vis)
       and await pg.get_attribute('#casca-lado [data-porta="1"]', "aria-current") == "page")
    await ctx.close()


# ------------------------------------------------------------------ 2. celular: barra de baixo e menu em gaveta
async def celular(nav):
    print("\n— 2. celular: barra de baixo, menu que prende o foco —")
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    for url, porta in (("brasil.html", 2), ("cidade.html?ibge=3550308", 4), ("index.html", 0)):
        await pg.goto(BASE + lang(url), wait_until="networkidle")
        await pg.wait_for_timeout(800)
        r = await pg.evaluate("""() => { const b = document.querySelector('.casca-baixo');
          return { vis: !!b && b.getClientRects().length > 0, itens: [...b.querySelectorAll('a, button')].map(x => { const r = x.getBoundingClientRect(); return [x.textContent.trim(), Math.round(r.width), Math.round(r.height), x.getAttribute('aria-current')]; }),
            ladoVis: getComputedStyle(document.getElementById('casca-lado')).visibility, fundo: Math.round(b.getBoundingClientRect().bottom), h: innerHeight }; }""")
        ok(f"{url}: barra de baixo com 1 Entenda, 2 Brasil, 3 Estado, 4 Cidade e Menu (alvos ≥ 44 px), presa embaixo",
           r["vis"] and len(r["itens"]) == 5 and all(i[1] >= 44 and i[2] >= 44 for i in r["itens"]) and r["fundo"] == r["h"], str(r["itens"]))
        ok(f"{url}: a porta {porta or 'nenhuma'} marcada na barra de baixo", [i + 1 for i, x in enumerate(r["itens"][:4]) if x[3]] == ([porta] if porta else []))
        ok(f"{url}: o menu lateral fica escondido até abrir", r["ladoVis"] == "hidden")
    await pg.goto(BASE + lang("brasil.html"), wait_until="networkidle")
    await pg.wait_for_timeout(800)
    await pg.locator("#casca-menu-btn").tap()
    await pg.wait_for_timeout(450)
    r = await pg.evaluate("""() => ({ exp: document.getElementById('casca-menu-btn').getAttribute('aria-expanded'), foco: document.activeElement.id,
      inerte: document.querySelector('main').inert && document.querySelector('body > header.topo').inert && document.querySelector('.casca-baixo').inert,
      vis: getComputedStyle(document.getElementById('casca-lado')).visibility })""")
    ok("☰ Menu abre o menu (aria-expanded, foco no ✕ Fechar, o resto da página inerte)", r["exp"] == "true" and r["foco"] == "casca-fecha" and r["inerte"] and r["vis"] == "visible", str(r))
    fora = 0
    for _ in range(40):
        await pg.keyboard.press("Tab")
        if not await pg.evaluate("document.getElementById('casca-lado').contains(document.activeElement) || document.activeElement === document.body"):
            fora += 1
    ok("Tab não sai do menu aberto (40 vezes)", fora == 0, str(fora))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)
    ok("Esc fecha o menu e o foco volta para o ☰ Menu", await pg.evaluate("document.activeElement.id") == "casca-menu-btn"
       and await pg.get_attribute("#casca-menu-btn", "aria-expanded") == "false" and not await pg.evaluate("document.querySelector('main').inert"))
    await pg.locator("#casca-menu-btn").tap()
    await pg.wait_for_timeout(400)
    await pg.touchscreen.tap(370, 400)
    await pg.wait_for_timeout(400)
    ok("tocar fora (no véu) fecha o menu", await pg.get_attribute("#casca-menu-btn", "aria-expanded") == "false")
    # Leitura dentro do menu do celular: o painel cabe na tela
    await pg.locator("#casca-menu-btn").tap()
    await pg.wait_for_timeout(400)
    await pg.locator("#menu-leitura-btn").tap()
    await pg.wait_for_timeout(350)
    lr = await pg.evaluate("(() => { const r = document.getElementById('menu-leitura').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.top), Math.round(r.bottom)]; })()")
    ok("menu do celular: o painel Leitura abre e cabe na tela", await pg.locator("#menu-leitura").is_visible() and lr[0] >= 0 and lr[1] <= 390 and lr[2] >= 0 and lr[3] <= 844, str(lr))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    ok("Esc fecha primeiro o painel (o menu continua aberto)", await pg.locator("#menu-leitura").is_hidden() and await pg.get_attribute("#casca-menu-btn", "aria-expanded") == "true")
    await axe(pg, "menu do celular aberto (Brasil)")
    await pg.keyboard.press("Escape")
    # um item da seção (aba) fecha o menu e abre a aba
    await pg.locator("#casca-menu-btn").tap()
    await pg.wait_for_timeout(400)
    await pg.locator('#cl-secao a[data-item="camara"]').tap()
    await pg.wait_for_timeout(900)
    ok("no celular, tocar numa aba do menu fecha o menu e abre a aba", await pg.get_attribute("#casca-menu-btn", "aria-expanded") == "false" and await pg.evaluate("EP.abas.ativa()") == "camara")
    # a barra do topo do celular: marca, nome da página, busca e Ouvir
    await pg.goto(BASE + lang("pessoa.html?id=dep-178866"), wait_until="networkidle")
    await pg.wait_for_timeout(1000)
    r = await pg.evaluate("""() => ({ onde: document.querySelector('header.topo .onde').innerText.trim(), trilhaVis: document.getElementById('trilha').getClientRects().length > 0,
      marca: document.querySelector('header.topo .marca-cel').getClientRects().length > 0, volta: document.getElementById('voltar-lista').getClientRects().length > 0 })""")
    ok("celular: a barra do topo mostra a marca, ◀ Voltar e o nome da página (o caminho fica para telas maiores)", r["onde"].endswith("Luizianne Lins") and not r["trilhaVis"] and r["marca"] and r["volta"], str(r))
    await ctx.close()


# ------------------------------------------------------------------ 3. busca rápida
async def busca(nav):
    print("\n— 3. busca rápida —")
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    pedidos = []
    pg.on("request", lambda r: pedidos.append(r.url))
    await pg.goto(BASE + lang("brasil.html#senado"), wait_until="networkidle")
    await pg.wait_for_timeout(800)
    ok("a lista de nomes (dados/busca.json) e a de cidades não são baixadas ao abrir a página", not any("busca.json" in u or "cidades.json" in u for u in pedidos))
    await pg.keyboard.press("Control+k")
    await pg.wait_for_timeout(500)
    ok("Ctrl+K abre a busca (janela) com o foco no campo", await pg.evaluate("document.getElementById('busca-rapida').open && document.activeElement.id === 'br-q'"))
    await pg.wait_for_timeout(600)
    ok("ao abrir, a lista de nomes é baixada", any("busca.json" in u for u in pedidos))
    n0 = await pg.locator("#br-lista [role=option]").count()
    ok("campo vazio mostra “Ir para” (as partes do site)", n0 >= 6 and "ir para" in (await pg.locator("#br-lista").inner_text()).lower(), str(n0))
    await pg.keyboard.type("lula", delay=30)
    await pg.wait_for_timeout(900)
    hrefs = await pg.locator("#br-lista [role=option]").evaluate_all("l => l.map(a => a.getAttribute('href'))")
    st = await pg.locator("#br-status").inner_text()
    ok("“lula” acha o presidente; o leitor de tela ouve quantos resultados", "pessoa.html?id=pres-lula" in hrefs and "resultado" in st, f"{hrefs[:3]} | {st}")
    await pg.keyboard.press("ArrowDown")
    ativo = await pg.evaluate("document.getElementById('br-q').getAttribute('aria-activedescendant')")
    ok("seta para baixo marca um resultado (aria-activedescendant, aria-selected)", ativo and await pg.get_attribute("#" + ativo, "aria-selected") == "true")
    alvo = await pg.get_attribute("#" + ativo, "href")
    await pg.keyboard.press("Enter")
    await pg.wait_for_url("**/" + alvo.split("/")[-1] + "*", timeout=15000)
    ok("Enter abre o resultado", alvo.split("?")[-1] in pg.url, pg.url.split("/")[-1])
    await pg.wait_for_timeout(800)
    await pg.go_back()
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    r = await pg.evaluate("""() => ({ aberta: document.getElementById('busca-rapida').open, q: document.getElementById('br-q').value,
      ativo: (document.getElementById(document.getElementById('br-q').getAttribute('aria-activedescendant') || '_') || {}).getAttribute?.('href') })""")
    ok("a pesquisa volta: voltando, a busca abre de novo com “lula” e o resultado aberto marcado", r["aberta"] and r["q"] == "lula" and r["ativo"] == alvo, str(r))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(200)
    ok("Esc limpa o campo primeiro", await pg.evaluate("document.getElementById('busca-rapida').open && document.getElementById('br-q').value === ''"))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    ok("Esc de novo fecha", not await pg.evaluate("document.getElementById('busca-rapida').open"))
    # botão e foco que volta
    await pg.locator("header.topo [data-abre-busca]").click()
    await pg.wait_for_timeout(400)
    ok("o botão 🔍 da barra abre a busca", await pg.evaluate("document.getElementById('busca-rapida').open"))
    await axe(pg, "busca aberta (Brasil)")
    await pg.keyboard.type("bahia", delay=20)
    await pg.wait_for_timeout(800)
    ok("estados e cidades também aparecem", await pg.locator('#br-lista [role=option][href="estado.html?uf=BA"]').count() == 1)
    await pg.keyboard.press("Escape")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    ok("fechando, o foco volta para o botão que abriu", await pg.evaluate("document.activeElement.matches('header.topo [data-abre-busca]')"))
    await pg.locator("main h1, main h2").first.click()
    await pg.keyboard.press("/")
    await pg.wait_for_timeout(300)
    ok("a tecla “/” abre a busca", await pg.evaluate("document.getElementById('busca-rapida').open"))
    await pg.keyboard.press("Control+k")
    await pg.wait_for_timeout(300)
    ok("Ctrl+K de novo fecha", not await pg.evaluate("document.getElementById('busca-rapida').open"))
    await pg.keyboard.press("Meta+k")
    await pg.wait_for_timeout(300)
    ok("⌘K (Meta+K) também abre", await pg.evaluate("document.getElementById('busca-rapida').open"))
    await pg.keyboard.press("Escape")
    # "/" dentro de um campo é só uma letra
    await pg.locator("#busca").fill("")
    await pg.locator("#busca").type("a/b")
    ok("dentro de um campo, “/” é só uma letra", await pg.locator("#busca").input_value() == "a/b" and not await pg.evaluate("document.getElementById('busca-rapida').open"))
    # clique num resultado
    await pg.locator("header.topo [data-abre-busca]").click()
    await pg.keyboard.type("Salvador", delay=20)
    await pg.wait_for_timeout(900)
    await pg.locator('#br-lista [role=option][href="cidade.html?ibge=2927408"]').click()
    await pg.wait_for_url("**/cidade.html?ibge=2927408*")
    ok("clicar num resultado abre a página (cidade)", "ibge=2927408" in pg.url)
    # página inicial: o botão grande e ?q=
    await pg.goto(BASE + "index.html?lang=pt&q=lula", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    ok("início: link com ?q=lula já abre a busca feita", await pg.evaluate("document.getElementById('busca-rapida').open") and
       await pg.locator('#br-lista [role=option][href="pessoa.html?id=pres-lula"]').count() == 1)
    await pg.keyboard.press("Escape")
    await pg.keyboard.press("Escape")
    await pg.locator(".ini-busca").click()
    await pg.wait_for_timeout(400)
    ok("início: o campo grande abre a busca", await pg.evaluate("document.getElementById('busca-rapida').open"))
    await pg.keyboard.press("Escape")
    # inglês
    await pg.goto(BASE + "dados.html?lang=en", wait_until="networkidle")
    await pg.keyboard.press("Control+k")
    await pg.keyboard.type("senate", delay=20)
    await pg.wait_for_timeout(900)
    t = (await pg.locator("#busca-rapida").inner_text()).lower()
    ok("em inglês: a busca fala inglês e acha as partes do site em inglês", "federal senate" in t and "parts of the site" in t, t[:120])
    await pg.goto(BASE + "dados.html?lang=pt", wait_until="networkidle")
    await ctx.close()


# ------------------------------------------------------------------ 4. idioma, Leitura e Ouvir
async def leitura(nav):
    print("\n— 4. idioma, Leitura (guardados) e Ouvir —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 800})
    await ctx.add_init_script("""window.__falas = []; try { const s = window.speechSynthesis; if (s) { s.speak = u => { window.__falas.push(u.text); }; } } catch (e) {}""")
    pg = await ctx.new_page()
    await pg.goto(BASE + lang("estado.html?uf=BA"), wait_until="networkidle")
    await pg.wait_for_timeout(800)
    await pg.click("#menu-leitura-btn")
    await pg.wait_for_timeout(300)
    r = await pg.evaluate("""() => { const p = document.getElementById('menu-leitura').getBoundingClientRect(), b = document.getElementById('menu-leitura-btn').getBoundingClientRect();
      return { vis: p.width > 0, emCima: p.bottom <= b.top + 1, dentro: p.top >= 0 && p.left >= 0 && p.right <= innerWidth,
        sw: document.querySelectorAll('#menu-leitura [role=switch]').length, cb: document.querySelectorAll('#menu-leitura input[type=checkbox]:not([role=switch]), #menu-leitura [role=checkbox]').length }; }""")
    ok("Leitura (no pé do menu) abre para cima, dentro da tela, com 3 interruptores (switch), nenhum checkbox", r["vis"] and r["emCima"] and r["dentro"] and r["sw"] == 3 and r["cb"] == 0, str(r))
    await pg.locator('#menu-leitura [data-a11y="movimento"]').focus()
    await pg.keyboard.press("Space")
    await pg.click('#menu-leitura [data-escala="1.15"]')
    await pg.wait_for_timeout(200)
    a11y = json.loads(await pg.evaluate("localStorage.getItem('ep-a11y')"))
    ok("“Menos movimento” e a letra maior ficam guardados (ep-a11y)", a11y.get("movimento") is True and a11y.get("escala") == 1.15, str(a11y))
    await pg.goto(BASE + lang("dados.html"), wait_until="commit")
    cls = await pg.evaluate("[document.documentElement.classList.contains('sem-movimento'), document.documentElement.style.getPropertyValue('--escala')]")
    ok("outra página já abre com eles (o script do <head> aplica antes de pintar)", cls == [True, "1.15"], str(cls))
    await pg.wait_for_load_state("networkidle")
    await pg.click("#menu-leitura-btn")
    await pg.wait_for_timeout(250)
    await pg.locator('#menu-leitura [data-a11y="movimento"]').click()
    await pg.click('#menu-leitura [data-escala="1"]')
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)
    ok("Esc fecha o painel e devolve o foco ao botão Leitura", await pg.evaluate("document.activeElement.id") == "menu-leitura-btn" and await pg.locator("#menu-leitura").is_hidden())
    # idioma
    await pg.click("#menu-idioma-btn")
    await pg.wait_for_timeout(250)
    await pg.click('#menu-idioma [data-idioma="en"]')
    await pg.wait_for_url("**lang=en**")
    await pg.wait_for_load_state("networkidle")
    ok("idioma (no pé do menu): English abre a mesma página em inglês e fica guardado", await pg.evaluate("document.documentElement.lang") == "en"
       and await pg.evaluate("localStorage.getItem('ep-lang')") == "en" and "where to go" in (await pg.locator("#casca-lado").inner_text()).lower())
    await pg.goto(BASE + "brasil.html", wait_until="networkidle")
    ok("outra página abre em inglês sem ?lang (menu, barra de baixo e busca em inglês)", await pg.evaluate("document.documentElement.lang") == "en"
       and "brazil's politics" in (await pg.locator("#casca-lado").inner_text()).lower() and "Search for a politician" in await pg.locator("header.topo").inner_text())
    await pg.click("#menu-idioma-btn")
    await pg.wait_for_timeout(250)
    await pg.click('#menu-idioma [data-idioma="pt"]')
    await pg.wait_for_url("**lang=pt**")
    await pg.wait_for_load_state("networkidle")
    # Ouvir
    await pg.goto(BASE + lang("dados.html"), wait_until="networkidle")
    await pg.click("#btn-ouvir")
    await pg.wait_for_timeout(300)
    falas = await pg.evaluate("window.__falas")
    h1 = (await pg.locator("main h1").first.inner_text()).strip()
    ok("🔊 Ouvir (na barra) lê o conteúdo da página (e não o menu)", falas and h1.split()[0] in falas[-1] and "Por onde ir" not in falas[-1] and "POR ONDE IR" not in falas[-1], (falas[-1][:80] if falas else "nada"))
    await ctx.close()


# ------------------------------------------------------------------ 5. página inicial
async def inicio(nav):
    print("\n— 5. página inicial: só as 4 portas —")
    for w, h, m in ((1440, 900, False), (390, 844, True)):
        ctx = await ctx_novo(nav, viewport={"width": w, "height": h}, is_mobile=m, has_touch=m)
        pg = await ctx.new_page()
        await pg.goto(BASE + lang("index.html"), wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""() => { const m = document.querySelector('main');
          return { portas: [...m.querySelectorAll('.portas .porta')].map(a => a.getAttribute('href')),
            cubos: [...m.querySelectorAll('.portas .p-cubo')].map(c => c.getAttribute('data-cubo').split('|')[0]),
            desenhos: [...m.querySelectorAll('.portas .p-ilu')].filter(e => e.querySelector('.cena3d')).length,
            comece: (m.querySelector('.portas li:first-child .fita') || {}).textContent || '',
            pessoas: m.querySelectorAll('a[href*="pessoa.html"], .pessoa-card, img').length,
            numeros: (m.innerText.match(/\\d{2,}/g) || []), enfeiteClique: [...m.querySelectorAll('.p-topo, .ini-hero-3d')].every(e => getComputedStyle(e).pointerEvents === 'none'),
            largura: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1 }; }""")
        nome = "computador" if not m else "celular"
        ok(f"início ({nome}): 4 portas numeradas 1–4 (Entenda, Brasil, Estado, Cidade), cada uma com desenho 3D", r["portas"] == PORTAS and r["cubos"] == ["1", "2", "3", "4"] and r["desenhos"] == 4, str(r["portas"]))
        ok(f"início ({nome}): a porta 1 tem “Comece por aqui”", "comece por aqui" in r["comece"].lower())
        ok(f"início ({nome}): nada do conteúdo das portas (sem pessoas, fotos nem números)", r["pessoas"] == 0 and not r["numeros"], str(r["numeros"][:5]))
        ok(f"início ({nome}): desenhos 3D não recebem clique; nada passa da tela", r["enfeiteClique"] and r["largura"])
        if not m:
            await axe(pg, "início (computador)")
            await pg.locator(".portas .porta").nth(1).click()
            await pg.wait_for_url("**/brasil.html*")
            ok("clicar na porta 2 abre a página do Brasil", "brasil.html" in pg.url)
        await ctx.close()


# ------------------------------------------------------------------ 6. gaveta
async def gaveta(nav):
    print("\n— 6. gaveta —")
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    await pg.goto(BASE + lang("brasil.html#senado"), wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    card = pg.locator("#senado .pessoa-card").first
    href = await card.get_attribute("href")
    pid = q("x?" + href.split("?")[1], "id")
    nome = (await card.locator("b").inner_text()).strip()
    h0 = await pg.evaluate("history.length")
    await card.click()
    await pg.wait_for_timeout(1200)
    r = await pg.evaluate("""() => { const g = document.getElementById('gaveta'), b = g.getBoundingClientRect();
      return { aberta: g.open, modal: g.matches(':modal'), tit: document.getElementById('gaveta-tit').innerText, foco: document.activeElement.id,
        pagina: (g.querySelector('.gv-pagina') || {}).getAttribute?.('href'), lado: g.dataset.lado, direita: Math.round(b.right) === innerWidth && b.left > innerWidth / 2,
        kpis: g.querySelectorAll('.gv-kpi').length, voltaVis: !g.querySelector('.gv-volta').hidden }; }""")
    ok("clicar numa pessoa do Senado abre a gaveta (modal, do lado direito) com o nome e os números", r["aberta"] and r["modal"] and nome in r["tit"] and r["direita"] and r["kpis"] >= 2, str(r))
    ok("o foco vai para o título da gaveta; “‹ Voltar” só aparece numa gaveta sobre outra", r["foco"] == "gaveta-tit" and not r["voltaVis"])
    ok("o endereço guarda a gaveta (?ver=p:…) e ganha um passo no histórico", q(pg.url, "ver") == "p:" + pid and await pg.evaluate("history.length") == h0 + 1, pg.url.split("/")[-1])
    ok("“Ver a página inteira” leva ao perfil", r["pagina"] == f"pessoa.html?id={pid}", str(r["pagina"]))
    await axe(pg, "gaveta aberta (pessoa do Senado)")
    # fontes por cima da gaveta (a janela continua para as fontes)
    await pg.locator("#gaveta [data-fontes]").click()
    await pg.wait_for_timeout(400)
    ok("“De onde veio isso?” abre a janela das fontes por cima da gaveta", await pg.evaluate("EP.janelaAberta() && document.getElementById('gaveta').open"))
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    ok("Esc fecha só a janela das fontes", await pg.evaluate("!EP.janelaAberta() && document.getElementById('gaveta').open"))
    # gaveta sobre gaveta
    await pg.evaluate("EP.gaveta({ tit: 'Teste de cima', corpo: '<p>oi</p>' })")
    await pg.wait_for_timeout(300)
    ok("gaveta sobre gaveta: aparece “‹ Voltar” com o foco nele", await pg.evaluate("!document.querySelector('#gaveta .gv-volta').hidden && document.activeElement.classList.contains('gv-volta')"))
    await pg.locator("#gaveta .gv-volta").click()
    await pg.wait_for_timeout(300)
    ok("“‹ Voltar” volta para a gaveta de antes", nome in await pg.locator("#gaveta-tit").inner_text() and q(pg.url, "ver") == "p:" + pid)
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(500)
    f = await pg.evaluate("document.activeElement.getAttribute('href')")
    ok("Esc fecha; o endereço perde o ?ver= e o foco volta para a pessoa clicada", not await pg.evaluate("document.getElementById('gaveta').open") and q(pg.url, "ver") is None and f == href, f"{pg.url.split('/')[-1]} | {f}")
    ok("fechar desfaz o passo do histórico", await pg.evaluate("history.length") == h0 + 1 and await pg.evaluate("!(history.state && history.state.gaveta)"))
    # Voltar e Avançar do navegador
    await card.click()
    await pg.wait_for_timeout(900)
    await pg.go_back()
    await pg.wait_for_timeout(600)
    ok("Voltar do navegador fecha a gaveta (e fica na mesma página)", not await pg.evaluate("document.getElementById('gaveta').open") and "brasil.html" in pg.url and q(pg.url, "ver") is None)
    await pg.go_forward()
    await pg.wait_for_timeout(1200)
    ok("Avançar abre a gaveta de novo", await pg.evaluate("document.getElementById('gaveta').open") and nome in await pg.locator("#gaveta-tit").inner_text())
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    # clicar fora fecha
    await card.click()
    await pg.wait_for_timeout(700)
    await pg.mouse.click(300, 450)
    await pg.wait_for_timeout(500)
    ok("clicar fora da gaveta fecha", not await pg.evaluate("document.getElementById('gaveta').open"))
    # endereço com ?ver= (compartilhar)
    await pg.goto(BASE + "brasil.html?lang=pt&ver=p:dep-178866#camara", wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    ok("um endereço com ?ver=p:dep-178866 abre a página com a gaveta da pessoa", await pg.evaluate("document.getElementById('gaveta').open") and "Luizianne Lins" in await pg.locator("#gaveta-tit").inner_text())
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)
    ok("fechando, o endereço fica sem ?ver=", q(pg.url, "ver") is None and "#camara" in pg.url)
    # Ctrl + clique abre a página inteira (em outra aba), sem gaveta
    async with ctx.expect_page() as nova:
        await pg.locator("#camara .pessoa-card").first.click(modifiers=["Control"])
    p2 = await nova.value
    await p2.wait_for_load_state()
    ok("Ctrl + clique abre o perfil em outra aba, sem gaveta", "pessoa.html?id=" in p2.url and not await pg.evaluate("document.getElementById('gaveta') && document.getElementById('gaveta').open"))
    await p2.close()
    # "Ver a página inteira" e a volta para a lista
    await pg.goto(BASE + lang("estado.html?uf=BA#federais"), wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    h0 = await pg.evaluate("history.length")
    card = pg.locator("#federais .pessoa-card").nth(4)
    await card.scroll_into_view_if_needed()
    href = await card.get_attribute("href")
    await card.click()
    await pg.wait_for_timeout(900)
    await pg.locator("#gaveta .gv-pagina").click()
    await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
    await pg.wait_for_load_state("networkidle")
    ok("“Ver a página inteira” abre o perfil (no lugar do passo da gaveta)", href.split("?")[1] in pg.url and await pg.evaluate("history.length") == h0 + 1)
    await pg.wait_for_timeout(600)
    await pg.go_back()
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(2200)
    r = await pg.evaluate("""() => ({ g: !!document.getElementById('gaveta') && document.getElementById('gaveta').open, foco: document.activeElement.getAttribute('href'), url: location.search + location.hash })""")
    ok("Voltar do perfil volta para a lista sem a gaveta, com o foco em quem foi aberto", not r["g"] and r["foco"] == href and "ver=" not in r["url"] and "#federais" in r["url"], str(r))
    # celular: a gaveta sobe de baixo
    await ctx.close()
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto(BASE + lang("cidade.html?ibge=3550308#camara-mun"), wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    c = pg.locator("#camara-mun .pessoa-card").first
    await c.scroll_into_view_if_needed()
    await c.tap()
    await pg.wait_for_timeout(1000)
    r = await pg.evaluate("""() => { const g = document.getElementById('gaveta'), b = g.getBoundingClientRect(); return { aberta: g.open, lado: g.dataset.lado, embaixo: Math.round(b.bottom) === innerHeight && b.top > 40,
      largura: Math.round(b.width), tit: document.getElementById('gaveta-tit').innerText, pagina: !!g.querySelector('.gv-pagina') }; }""")
    ok("celular: a gaveta sobe de baixo (vereador de São Paulo, com o nome e “Ver a página inteira”)", r["aberta"] and r["lado"] == "baixo" and r["embaixo"] and r["largura"] == 390 and r["tit"] and r["pagina"], str(r))
    await axe(pg, "gaveta aberta no celular (vereador)")
    await pg.locator("#gaveta .gv-fecha").tap()
    await pg.wait_for_timeout(400)
    ok("celular: ✕ fecha a gaveta", not await pg.evaluate("document.getElementById('gaveta').open"))
    ok("nenhum erro de JavaScript (gaveta)", not erros, " | ".join(erros[:3]))
    await ctx.close()


# ------------------------------------------------------------------ 7. 320 px e rede
async def geral(nav):
    print("\n— 7. 320 px sem rolar para os lados, nenhum servidor novo —")
    ctx = await ctx_novo(nav, viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    erros, fora = [], set()
    pg.on("pageerror", lambda e: erros.append(str(e)))

    def pedido(r):
        h = urlparse(r.url).hostname
        if h and h != LOCAL and (r.resource_type != "image" or any(c in r.url for c in CDN)):
            fora.add(f"{h} ({r.resource_type})")
    pg.on("request", pedido)
    largas, pequenos = [], []
    for url, _ in PAGINAS:
        for l in ("pt", "en"):
            await pg.goto(BASE + lang(url, l), wait_until="networkidle")
            await pg.wait_for_timeout(500)
            for estado in ("", "menu", "busca"):
                if estado == "menu":
                    await pg.locator("#casca-menu-btn").tap()
                    await pg.wait_for_timeout(300)
                if estado == "busca":
                    await pg.evaluate("EP.abreBusca(null, 'silva')")
                    await pg.wait_for_timeout(700)
                if not await pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"):
                    largas.append(f"{url} {l} {estado}")
                if estado == "":
                    p = await pg.evaluate("""[...document.querySelectorAll('header.topo > a, header.topo .ferramentas-topo > button, .casca-baixo a, .casca-baixo button')]
                      .filter(b => b.getClientRects().length).filter(b => { const r = b.getBoundingClientRect(); return r.width < 44 || r.height < 44 || r.right > 321; })
                      .map(b => (b.id || b.className || b.textContent.trim()).slice(0, 20))""")
                    if p:
                        pequenos.append(f"{url}: {p}")
                if estado:
                    await pg.keyboard.press("Escape")
                    await pg.keyboard.press("Escape")
                    await pg.wait_for_timeout(200)
    ok(f"320 px: {len(PAGINAS)} páginas (pt e en; com o menu e a busca abertos) sem rolar para os lados", not largas, ", ".join(largas))
    ok("320 px: botões da barra do topo e da barra de baixo com pelo menos 44×44 e dentro da tela", not pequenos, "; ".join(pequenos)[:300])
    ok("nenhum pedido a outro servidor (nada de CDN)", not fora, ", ".join(sorted(fora)))
    await ctx.close()


# ------------------------------------------------------------------ 8. menu estável (site-d-r16, pedido do Lucas de 4/11, 14h35)
MENU_JS = """() => { const q = s => [...document.querySelectorAll(s)], s = document.getElementById('cl-secao');
  const item = a => ({ id: a.getAttribute('data-item') || '', ic: (a.querySelector('.cl-ic') || {}).textContent || '', t: (a.querySelector('.cl-txt') || a).textContent.trim(),
    href: a.getAttribute('href'), atual: a.getAttribute('aria-current') });
  return { portas: q('#casca-lado .cl-portas a').map(a => a.getAttribute('href').replace(/^\\//, '').replace(/\\?lang=en$/, '') + '|' + a.textContent.trim()),
    tit: s && !s.hidden ? s.querySelector('.cl-tit').textContent.trim() : null, secao: s && !s.hidden ? q('#cl-secao a').map(item) : [],
    sobre: q('[aria-labelledby=cl-sobre-t] a').map(a => a.getAttribute('href').replace(/^\\//, '').replace(/\\?lang=en$/, '') + '|' + a.textContent.trim()),
    trilha: q('#trilha li').map(l => { const a = l.querySelector('a'); return [l.textContent.trim(), a ? a.getAttribute('href') : null, !!l.querySelector('[aria-current=page]')]; }) }; }"""


async def menu_estavel(nav):
    print("\n— 8. menu estável: a lista de votações e a votação são parte de “Como votaram” (mesmos itens do Brasil) —")
    ITENS = {"pt": ["Quem governa", "Senado", "Câmara", "Como votaram", "STF"], "en": ["Who governs", "Senate", "Chamber of Deputies", "How Congress voted", "Supreme Court"]}
    TRILHA = {"pt": ["Início", "A política do Brasil", "Como votaram", "Todas as votações"], "en": ["Home", "Brazil's politics", "How Congress voted", "All the votes"]}
    IDS = ["executivo", "senado", "camara", "votacoes", "judiciario"]
    VOT = "votacao.html?casa=senado&id=7107"
    for l in ("pt", "en"):
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        m = {}
        for url in ("brasil.html", "brasil.html#votacoes", "votacoes.html", "votacoes.html?casa=senado&ano=2025", VOT, "votacao.html?casa=camara&id=2236186-60",
                    "votacao.html", "estado.html?uf=BA", "estado.html?uf=BA#votacoes", "cidade.html?ibge=2927408", "dados.html", "imparcialidade.html", "404.html", "index.html", "entenda.html"):
            await pg.goto(BASE + lang(url, l), wait_until="networkidle")
            await pg.wait_for_timeout(900)
            m[url] = await pg.evaluate(MENU_JS)
        b = m["brasil.html"]
        sem = lambda s: [(x["id"], x["ic"], x["t"]) for x in s]
        ok(f"[{l}] Brasil: título do grupo = nome da porta e itens = as 5 abas", b["tit"] == ("A política do Brasil" if l == "pt" else "Brazil's politics")
           and [x["t"] for x in b["secao"]] == ITENS[l] and [x["id"] for x in b["secao"]] == IDS, str(b["tit"]) + " " + str([x["t"] for x in b["secao"]]))
        for url in ("votacoes.html", "votacoes.html?casa=senado&ano=2025", VOT, "votacao.html?casa=camara&id=2236186-60", "votacao.html"):
            r = m[url]
            ok(f"[{l}] {url}: mesmo título e mesmos itens (id, emoji, nome) da página do Brasil, sem item a mais",
               r["tit"] == b["tit"] and sem(r["secao"]) == sem(b["secao"]), str([x["t"] for x in r["secao"]]))
            ok(f"[{l}] {url}: os itens levam a brasil.html#<aba>", [x["href"] for x in r["secao"]] == ["brasil.html#" + i for i in IDS], str([x["href"] for x in r["secao"]]))
            ok(f"[{l}] {url}: “{ITENS[l][3]}” marcado (e só ele)", [x["id"] for x in r["secao"] if x["atual"]] == ["votacoes"], str([(x["id"], x["atual"]) for x in r["secao"] if x["atual"]]))
        ok(f"[{l}] brasil.html#votacoes: “{ITENS[l][3]}” marcado", [x["id"] for x in m["brasil.html#votacoes"]["secao"] if x["atual"]] == ["votacoes"])
        t = m["votacoes.html"]["trilha"]
        ok(f"[{l}] trilha da lista: {' › '.join(TRILHA[l])}", [x[0].replace("🏠", "").strip() for x in t] == TRILHA[l]
           and [x[1] for x in t[1:3]] == ["brasil.html", "brasil.html#votacoes"] and t[-1][2], str(t))
        t = m[VOT]["trilha"]
        ok(f"[{l}] trilha da votação: … › {TRILHA[l][2]} › {TRILHA[l][3]} › PEC 221/2019", [x[0].replace("🏠", "").strip() for x in t[:4]] == TRILHA[l]
           and t[3][1] == "votacoes.html" and t[4][0].startswith("PEC 221/2019") and t[4][2], str(t))
        ok(f"[{l}] estado: mesmo título (nome da porta) com e sem aba aberta", m["estado.html?uf=BA"]["tit"] == m["estado.html?uf=BA#votacoes"]["tit"]
           == ("A política do meu estado" if l == "pt" else "Politics in my state") and sem(m["estado.html?uf=BA"]["secao"]) == sem(m["estado.html?uf=BA#votacoes"]["secao"]))
        ok(f"[{l}] cidade: título do grupo = nome da porta", m["cidade.html?ibge=2927408"]["tit"] == ("A política da minha cidade" if l == "pt" else "Politics in my city"))
        ok(f"[{l}] as 4 portas e “Sobre o site” iguais em todas as {len(m)} páginas", len({tuple(r["portas"]) for r in m.values()}) == 1
           and len({tuple(r["sobre"]) for r in m.values()}) == 1, str({tuple(r["sobre"]) for r in m.values()})[:300])
        ok(f"[{l}] dados, imparcialidade, 404, início e Entenda sem itens de seção", all(not m[u]["secao"] for u in ("dados.html", "imparcialidade.html", "404.html", "index.html", "entenda.html")))
        # clicar em “Como votaram” no menu da lista leva à aba da página do Brasil
        await pg.goto(BASE + lang("votacoes.html", l), wait_until="networkidle")
        await pg.wait_for_timeout(800)
        await pg.locator('#cl-secao a[data-item="votacoes"]').click()
        await pg.wait_for_load_state("networkidle")
        await pg.wait_for_timeout(900)
        ok(f"[{l}] na lista, “{ITENS[l][3]}” no menu abre brasil.html#votacoes com a aba aberta", urlparse(pg.url).path.endswith("brasil.html") and await pg.evaluate("EP.abas.ativa()") == "votacoes", pg.url)
        # links antigos continuam funcionando
        await pg.goto(BASE + lang("votacoes.html?casa=senado&ano=2025&q=pec", l), wait_until="networkidle")
        await pg.wait_for_timeout(900)
        ok(f"[{l}] link antigo votacoes.html?casa=…&ano=…&q=… abre a lista filtrada", await pg.locator("#lista-votacoes li").count() > 0 and await pg.input_value("#f-q") == "pec")
        await pg.goto(BASE + lang(VOT, l), wait_until="networkidle")
        await pg.wait_for_timeout(900)
        ok(f"[{l}] link antigo votacao.html?casa=senado&id=7107 abre a votação", "PEC 221/2019" in await pg.inner_text("#votacao"))
        await pg.goto(BASE + lang("brasil.html?ver=vot:senado:7107", l), wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        ok(f"[{l}] brasil.html?ver=vot:senado:7107 abre a mesma votação no modal", await pg.locator("dialog.gv-modal[open]").count() == 1
           and "PEC 221/2019" in await pg.inner_text("dialog.gv-modal[open]"))
        await pg.keyboard.press("Escape")
        await pg.goto(BASE + lang("votacoes.html", l), wait_until="networkidle")
        await pg.wait_for_timeout(900)
        await axe(pg, f"[{l}] lista de votações com o menu novo (computador)")
        await pg.goto(BASE + lang(VOT, l), wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        await axe(pg, f"[{l}] votação com o menu novo (computador)")
        ok(f"[{l}] nenhum erro de JavaScript", not erros, " | ".join(erros[:3]))
        await ctx.close()
        # celular: o menu aberto (gaveta) mostra os mesmos itens, com “Como votaram” marcado
        ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        for url in ("votacoes.html", VOT):
            await pg.goto(BASE + lang(url, l), wait_until="networkidle")
            await pg.wait_for_timeout(900)
            await pg.locator("#casca-menu-btn").tap()
            await pg.wait_for_timeout(450)
            r = await pg.evaluate(MENU_JS)
            ok(f"[{l}] celular, {url}: menu aberto com os mesmos itens do Brasil e “{ITENS[l][3]}” marcado",
               sem(r["secao"]) == sem(b["secao"]) and [x["id"] for x in r["secao"] if x["atual"]] == ["votacoes"])
            await axe(pg, f"[{l}] celular, {url} com o menu aberto")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
            await axe(pg, f"[{l}] celular, {url}")
        await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        for f in (casca, celular, busca, leitura, inicio, gaveta, geral, menu_estavel):
            try:
                await f(nav)
            except Exception as e:  # um bloco que quebra não esconde os outros
                ok(f"{f.__name__}: terminou sem erro do teste", False, repr(e)[:300])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
