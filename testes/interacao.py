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

        # 2. escolher cidade só com o teclado
        await pg.goto(BASE + "estado.html?uf=BA", wait_until="networkidle")
        await pg.focus("#busca-cidade")
        await pg.keyboard.type("feira de", delay=40)
        await pg.wait_for_timeout(700)
        await pg.keyboard.press("ArrowDown")
        foco = await pg.evaluate("document.activeElement && document.activeElement.textContent")
        ok("seta para baixo leva à 1ª sugestão", foco and "Feira de Santana" in foco, foco and foco[:40])
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1500)
        nome = await pg.locator("#nome-cidade").text_content() if await pg.locator("#nome-cidade").count() else ""
        ok("Enter abre a cidade", "Feira de Santana" in (nome or ""), nome)
        ok("endereço guarda a cidade", "cidade=2910800" in pg.url, pg.url.split("?")[-1])
        n = await pg.locator("#cidade-caixa a, #cidade-caixa .pessoa-grande").count()
        ok("cidade mostra prefeito/vereadores", n > 3, f"{n} cartões")

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
