"""Testes de interação (teclado e busca) com Playwright + Edge. Precisa do servidor em 8770.
Uso: python testes/interacao.py"""
import asyncio
import sys

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
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

        # 1. busca de político na página inicial
        await pg.goto(BASE + "index.html", wait_until="networkidle")
        await pg.fill("#busca", "lula")
        await pg.wait_for_timeout(900)
        ok("busca 'lula' acha o presidente", await pg.locator('#resultados a[href*="id=pres-lula"]').count() > 0)
        await pg.fill("#busca", "salvador")
        await pg.wait_for_timeout(900)
        n = await pg.locator("#resultados a").count()
        ok("busca por cidade ('salvador') traz resultados", n > 0, f"{n} resultados")

        # 2. escolher cidade só com o teclado (página do estado -> página da cidade)
        await pg.goto(BASE + "estado.html?uf=BA", wait_until="networkidle")
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

        # 2e. filtros das listas (Senado): campo de estado com busca
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        campo = pg.locator("#senado .combo input").first
        await campo.click()
        await pg.keyboard.type("rio", delay=40)
        await pg.wait_for_timeout(700)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        cont = await pg.locator("#senado .contagem").inner_text()
        ok("filtro de estado com busca filtra a lista", await campo.input_value() == "Rio de Janeiro" and "3 de 81" in cont, f"{await campo.input_value()} | {cont}")

        # 3. filtro de propostas no perfil
        await pg.goto(BASE + "pessoa.html?id=pres-lula", wait_until="networkidle")
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

        # 5. menu de acessibilidade
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        await pg.click("#btn-a11y")
        await pg.wait_for_timeout(500)
        ok("menu ♿ abre como diálogo", await pg.locator('[role="dialog"]:visible').count() > 0)
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(400)
        foco = await pg.evaluate("document.activeElement && document.activeElement.id")
        ok("Esc fecha e devolve o foco ao botão", foco == "btn-a11y", foco)

        # 6. trocar idioma mantém a página
        await pg.goto(BASE + "pessoa.html?id=sen-5672", wait_until="networkidle")
        await pg.click("#btn-idioma")
        await pg.wait_for_load_state("networkidle")
        ok("botão EN mantém o perfil e troca o idioma", "id=sen-5672" in pg.url and "lang=en" in pg.url
           and await pg.evaluate("document.documentElement.lang") == "en", pg.url.split("/")[-1])

        ok("sem erros de JavaScript", not erros, "; ".join(erros)[:200])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")


asyncio.run(main())
