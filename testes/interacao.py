"""Testes de interação (teclado e busca) com Playwright + Edge. Precisa do servidor em 8770.
Uso: python testes/interacao.py"""
import asyncio
import sys

from playwright.async_api import async_playwright

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ajuda_abas import pagina_inteira  # site-d-r13

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8771/
sys.stdout.reconfigure(encoding="utf-8")
RES = []


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. busca de político na página inicial (site-d-r13: o campo grande abre a busca rápida)
        await pg.goto(BASE + "index.html", wait_until="networkidle")
        await pg.click(".ini-busca")
        await pg.fill("#br-q", "lula")
        await pg.wait_for_timeout(900)
        ok("busca 'lula' acha o presidente", await pg.locator('#br-lista a[href*="id=pres-lula"]').count() > 0)
        await pg.fill("#br-q", "salvador")
        await pg.wait_for_timeout(900)
        n = await pg.locator("#br-lista a").count()
        ok("busca por cidade ('salvador') traz resultados", n > 0, f"{n} resultados")

        # 2. escolher cidade só com o teclado (página do estado -> página da cidade)
        await pg.goto(BASE + "estado.html?uf=BA#cidade", wait_until="networkidle")  # ui-r9: a cidade é uma aba do estado
        await pg.focus("#campo-cid")
        await pg.keyboard.type("feira de", delay=40)
        await pg.wait_for_timeout(700)
        ativo = await pg.evaluate("(document.getElementById(document.getElementById('campo-cid').getAttribute('aria-activedescendant')) || {}).textContent")
        ok("digitando, a 1ª cidade fica marcada", ativo and "Feira de Santana" in ativo, ativo and ativo[:40])
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**/cidade.html?ibge=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        await pg.wait_for_timeout(1500)
        nome = await pg.locator("#nome-cidade").text_content() if await pg.locator("#nome-cidade").count() else ""
        ok("Enter abre a página da cidade", "cidade.html?ibge=2910800" in pg.url and "Feira de Santana" in (nome or ""), pg.url.split("/")[-1])
        await pg.evaluate("EP.abas && EP.abas.mostra('camara-mun')")  # ui-r9: os vereadores ficam na aba Câmara Municipal
        await pg.wait_for_timeout(800)
        n = await pg.locator("#cidade .pessoa-grande, #cidade .pessoa-card").count()
        ok("cidade mostra prefeito/vereadores", n > 3, f"{n} cartões")

        # 2b. página da cidade: busca no Brasil todo, com o estado para desempatar
        await pg.goto(BASE + "cidade.html", wait_until="networkidle")
        await pg.focus("#campo-cidade")
        await pg.keyboard.type("bom jesus pi", delay=30)
        await pg.wait_for_timeout(900)
        ops = await pg.locator("#campo-cidade-lista [role=option]").all_inner_texts()
        ok("“bom jesus pi” põe a do Piauí em 1º e não acha “pi” no meio da palavra", ops and "Piauí" in ops[0] and not any("Espírito" in o for o in ops), " | ".join(o.replace("\n", " ") for o in ops))
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1500)
        foco = await pg.evaluate("document.activeElement && document.activeElement.id")
        ok("escolher abre a cidade e leva o foco para o nome", "ibge=2201903" in pg.url and foco == "nome-cidade", f"{pg.url.split('?')[-1]} foco={foco}")
        await pg.focus("#campo-cidade")
        await pg.keyboard.press("Control+A")
        await pg.keyboard.type("brasilia", delay=30)
        await pg.wait_for_timeout(800)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#cidade").inner_text()
        ok("Brasília explica por que não tem prefeito", "Distrito Federal" in txt and "estado.html?uf=DF" in (await pg.locator("#cidade").inner_html()))

        # 2c. página do estado: lista de estados com busca; endereço antigo com cidade vai para a página da cidade
        await pg.goto(BASE + "estado.html", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        n_uf = await pg.locator("#mapa a.uf").count()
        await pg.locator('#mapa a.uf[data-uf="AC"]').focus()
        await pg.keyboard.press("Tab")
        rot = await pg.locator("#rotulo-uf").inner_text()
        ok("mapa real: 27 estados; o Tab passa de um estado para o outro e mostra o nome", n_uf == 27 and "Amapá" in rot and await pg.locator("#mapa .realce.ligado").count() == 1, f"{n_uf} | {rot}")
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**/estado.html?uf=*", timeout=15000)
        ok("Enter no estado do mapa abre o estado", "uf=AP" in pg.url, pg.url.split("/")[-1])
        await pg.goto(BASE + "estado.html", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        await pg.locator('#mapa a.selo-link[data-uf="SE"] rect').click()
        await pg.wait_for_url("**/estado.html?uf=*", timeout=15000)
        ok("clicar no selo de um estado pequeno (SE) abre o estado", "uf=SE" in pg.url, pg.url.split("/")[-1])
        await pg.goto(BASE + "estado.html", wait_until="networkidle")
        await pg.focus("#sel-uf-campo")
        await pg.keyboard.type("pern", delay=40)
        await pg.wait_for_timeout(600)
        await pg.keyboard.press("Enter")
        await pg.wait_for_url("**/estado.html?uf=*", timeout=15000)
        await pg.wait_for_load_state("networkidle")
        ok("digitar “pern” + Enter abre Pernambuco", "estado.html?uf=PE" in pg.url, pg.url.split("/")[-1])
        await pg.goto(BASE + "estado.html?uf=BA&cidade=2927408")
        await pg.wait_for_url("**/cidade.html?ibge=*", timeout=15000)
        ok("endereço antigo (estado + cidade) abre a página da cidade", "cidade.html?ibge=2927408" in pg.url, pg.url.split("/")[-1])

        # 2d. página inicial: 4 portas; a 4ª leva para a cidade
        await pg.goto(BASE + "index.html", wait_until="networkidle")
        portas = await pg.locator(".portas .porta").evaluate_all("l => l.map(a => a.getAttribute('href'))")
        ok("página inicial tem 4 portas, a 4ª é a cidade", portas == ["entenda.html", "brasil.html", "estado.html", "cidade.html"], str(portas))

        # 2e. filtros das listas (Senado): campo de estado com busca (o Senado é uma aba: brasil.html#senado)
        await pg.goto(BASE + "brasil.html#senado", wait_until="networkidle")
        campo = pg.locator("#senado .combo input").first
        await campo.click()
        await pg.keyboard.type("rio", delay=40)
        await pg.wait_for_timeout(700)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        cont = await pg.locator("#senado .contagem").inner_text()
        ok("filtro de estado com busca filtra a lista", await campo.input_value() == "Rio de Janeiro" and "3 de 81" in cont, f"{await campo.input_value()} | {cont}")

        # 3. filtro de propostas no perfil
        await pg.goto(BASE + "pessoa.html?id=pres-lula#propostas", wait_until="networkidle")  # ui-r9: as propostas são uma aba do perfil
        await pg.wait_for_timeout(800)
        antes = await pg.locator("#propostas").inner_text()
        await pg.click('[data-status="lei"]')
        await pg.wait_for_timeout(600)
        pressed = await pg.get_attribute('[data-status="lei"]', "aria-pressed")
        depois = await pg.locator("#propostas").inner_text()
        ok("filtro 'virou lei' fica marcado (aria-pressed)", pressed == "true")
        ok("filtro muda a lista", antes != depois)

        # 4. mapa: abrir parada pelo teclado, voltar com Esc
        await pg.goto(BASE + "entenda.html", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.focus('.lugar[data-n="1"] .placa')
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(2200)
        ok("Enter na placa abre a aula", await pg.evaluate("document.body.classList.contains('modo-aula')"))
        await pg.keyboard.press("ArrowRight")
        await pg.wait_for_timeout(700)
        ok("seta → passa o slide", "#parte-1-2" in pg.url, pg.url.split("#")[-1])
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(1800)
        ok("Esc volta ao mapa", not await pg.evaluate("document.body.classList.contains('modo-aula')"))
        foco = await pg.evaluate("document.activeElement && document.activeElement.className")
        ok("foco volta para a placa da parada", "placa" in (foco or ""), foco)

        # 5. menu de acessibilidade (ui-r9: o ♿ virou o menu suspenso "Aa Leitura" da barra)
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        await pg.click("#menu-leitura-btn")
        await pg.wait_for_timeout(500)
        ok("menu de leitura e acessibilidade abre", await pg.locator("#menu-leitura").is_visible() and await pg.get_attribute("#menu-leitura-btn", "aria-expanded") == "true")
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(400)
        foco = await pg.evaluate("document.activeElement && document.activeElement.id")
        ok("Esc fecha e devolve o foco ao botão", foco == "menu-leitura-btn" and await pg.locator("#menu-leitura").is_hidden(), foco)

        # 6. trocar idioma mantém a página
        await pg.goto(BASE + "pessoa.html?id=sen-5672", wait_until="networkidle")
        await pg.click("#menu-idioma-btn")  # ui-r9: o 🌐 virou um menu de idioma
        await pg.click('#menu-idioma [data-idioma="en"]')
        await pg.wait_for_load_state("networkidle")
        ok("botão EN mantém o perfil e troca o idioma", "id=sen-5672" in pg.url and "lang=en" in pg.url
           and await pg.evaluate("document.documentElement.lang") == "en", pg.url.split("/")[-1])

        # 7. "Voltar" do perfil volta para a página de onde a pessoa veio (e põe o foco em quem foi aberto)
        await pg.goto(BASE + "index.html?lang=pt", wait_until="networkidle")
        async def abre_e_volta(url, sel_card, espera_href, espera_nome):
            await pg.goto(BASE + url, wait_until="networkidle")
            card = pg.locator(sel_card).first
            await card.scroll_into_view_if_needed()
            await pg.wait_for_timeout(500)
            href = await card.get_attribute("href")
            hist0 = await pg.evaluate("history.length")
            await card.click()
            await pagina_inteira(pg)  # site-d-r13: o cartão abre a gaveta; o perfil fica no “Ver a página inteira”
            await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
            await pg.wait_for_load_state("networkidle")
            await pg.wait_for_timeout(600)
            volta = pg.locator("#voltar-lista")
            vh, vn = await volta.get_attribute("href"), await volta.get_attribute("aria-label")
            ok(f"perfil aberto de {url}: Voltar aponta para lá", vh.startswith(espera_href) and espera_nome in vn, f"{vh} | {vn}")
            await volta.click()
            await pg.wait_for_url(lambda u: url.split("#")[0] in u, timeout=15000)
            await pg.wait_for_timeout(2500)
            foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('href')")
            visivel = await pg.evaluate("(() => { const a = document.activeElement; if (!a || !a.getBoundingClientRect) return false; const r = a.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()")
            ok(f"Voltar leva a {url} com o foco em quem foi aberto", foco == href and visivel and await pg.evaluate("history.length") == hist0 + 1, f"foco={foco} visível={visivel}")
            return href
        # ui-r9: estado e cidade em abas: o endereço abre a aba da lista
        dep = await abre_e_volta("estado.html?uf=BA#federais", "#federais .pessoa-card", "estado.html?uf=BA", "Bahia")
        await abre_e_volta("brasil.html#senado", "#senado .pessoa-card", "brasil.html#senado", "Brasil")
        await abre_e_volta("cidade.html?ibge=2927408#camara-mun", "#casa-ver .pessoa-card", "cidade.html?ibge=2927408", "cidade")
        # trocar o idioma no perfil não perde o caminho de volta
        await pg.goto(BASE + "estado.html?uf=BA#federais", wait_until="networkidle")
        await pg.locator(f'#federais a[href="{dep}"]').first.click()
        await pagina_inteira(pg)  # site-d-r13: o cartão abre a gaveta; o perfil fica no “Ver a página inteira”
        await pg.wait_for_url("**/pessoa.html?id=*")
        await pg.click("#menu-idioma-btn")
        await pg.click('#menu-idioma [data-idioma="en"]')
        await pg.wait_for_url("**lang=en*")
        await pg.wait_for_load_state("networkidle")
        vh = await pg.locator("#voltar-lista").get_attribute("href")
        ok("depois de trocar o idioma, Voltar ainda vai para o estado", vh.startswith("estado.html?uf=BA") and "lang=en" in vh, vh)
        await pg.evaluate("sessionStorage.clear()")
        await pg.goto(BASE + dep + "&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(500)
        vh = await pg.locator("#voltar-lista").get_attribute("href")
        ok("aberto por link direto (sem caminho), Voltar vai para a lista do cargo", vh.startswith("brasil.html#camara"), vh)

        # 8. plenário por partido: passar o mouse, o teclado e o clique acendem as cadeiras do partido (o Senado é uma aba)
        await pg.goto(BASE + "brasil.html#senado", wait_until="networkidle")
        await pg.locator("#senado .plen-area").scroll_into_view_if_needed()
        await pg.wait_for_timeout(2200)
        sen = pg.locator("#senado")
        n_pt = int(await sen.locator('.d-partido[data-g="3"] > span:not(.sr)').inner_text())  # site-d-r14: etiquetas dos partidos
        await sen.locator('.d-partido[data-g="3"]').hover()
        await pg.wait_for_timeout(300)
        acesas = await sen.locator(".plenario i.aceso").count()
        sigla = await sen.locator(".rot-p.ativo").inner_text()
        ok("passar o mouse num partido acende as cadeiras dele e a sigla", acesas == n_pt and sigla.replace("\n", " ").endswith(str(n_pt)), f"{acesas} de {n_pt} | {sigla!r}")
        await pg.mouse.move(5, 5)
        await pg.wait_for_timeout(300)
        ok("tirar o mouse apaga", await sen.locator(".plenario i.aceso").count() == 0)
        await sen.locator('.plenario i[data-g="9"]').first.hover(force=True)
        await pg.wait_for_timeout(300)
        ok("passar o mouse numa cadeira marca o partido na lista", await sen.locator('.d-partido.realce[data-g="9"]').count() == 1)
        await sen.locator('.plenario i[data-g="9"]').first.click(force=True)
        await pg.wait_for_timeout(700)
        # site-d-r14: clicar numa cadeira abre a gaveta só com quem é do partido (antes, filtrava a lista da página)
        n9 = int(await sen.locator('.d-partido[data-g="9"] > span:not(.sr)').inner_text())
        cont = await pg.locator("#gaveta .contagem").inner_text() if await pg.locator("#gaveta[open]").count() else ""
        ok("clicar numa cadeira mostra só quem é do partido", await pg.locator("#gaveta .pessoa-card").count() == n9 and "em ordem alfabética" in cont, cont)
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(1300)  # a gaveta devolve o foco à etiqueta (e confere de novo até 1 s depois)
        await pg.evaluate("document.activeElement && document.activeElement.blur()")  # o foco voltou para a etiqueta (o teclado acenderia)
        await pg.mouse.move(5, 5)
        await pg.wait_for_timeout(400)
        # sem filtro, a contagem fala dos 81 (na página do Brasil, a lista começa com um resumo: "os 12 primeiros de 81 senadores")
        cont = await sen.locator(".contagem").inner_text()
        ok("clicar de novo mostra todos e apaga", ("todos os 81" in cont or "de 81 senadores" in cont) and await sen.locator(".plenario i.aceso").count() == 0, cont)
        await sen.locator('.d-partido[data-g="0"]').focus()
        await pg.keyboard.press("Tab")
        await pg.wait_for_timeout(300)
        n_psd = int(await sen.locator('.d-partido[data-g="1"] > span:not(.sr)').inner_text())
        ok("com o teclado (Tab), o partido com foco acende", await sen.locator(".plenario i.aceso").count() == n_psd, f"{n_psd} cadeiras")

        ok("sem erros de JavaScript", not erros, "; ".join(erros)[:200])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")


asyncio.run(main())
