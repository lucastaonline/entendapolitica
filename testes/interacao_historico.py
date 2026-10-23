"""Testes de interação dos mandatos anteriores ("Ver outro mandato"), com Playwright + Edge. Precisa do servidor em 8770.
Uso: python testes/interacao_historico.py"""
import asyncio
import datetime
import sys

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
sys.stdout.reconfigure(encoding="utf-8")
RES = []


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


async def escolhe_mandato(pg, texto):
    """Escolhe um mandato no campo "Ver outro mandato" só com o teclado e espera a página trocar."""
    campo = pg.locator(".mandato-box input[role=combobox]").first
    await campo.focus()
    await pg.keyboard.press("Control+A")
    await pg.keyboard.type(texto, delay=40)
    await pg.wait_for_timeout(600)
    async with pg.expect_navigation(timeout=15000):
        await pg.keyboard.press("Enter")
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # 1. Brasil hoje: o campo aparece com o mandato atual escolhido
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        campo = pg.locator("#mandato-lugar input[role=combobox]")
        val = await campo.input_value() if await campo.count() else ""
        rot = await pg.locator("#mandato-lugar label").inner_text() if await campo.count() else ""
        ok("Brasil: campo “Ver outro mandato” mostra o mandato atual", "(atual)" in val and "Ver outro mandato" in rot, val)
        ok("Brasil hoje continua igual (ministros e busca aparecem, sem faixa do passado)",
           await pg.locator("#ministros .min-card").count() > 10 and await pg.locator(".faixa-passado").count() == 0
           and await pg.locator("#procurar").is_visible())
        await campo.click()
        await pg.wait_for_timeout(500)
        ops = await pg.locator("#mandato-lugar [role=option]").all_inner_texts()
        ok("a lista tem os mandatos desde 1995, do mais novo para o mais velho", len(ops) >= 8 and ops[0].startswith("2023") and ops[-1].startswith("1995"), " | ".join(o.strip() for o in ops))
        await pg.keyboard.press("Escape")

        # 2. escolher 2019 a 2022 com o teclado leva ao passado
        await escolhe_mandato(pg, "2019")
        ok("escolher “2019” abre brasil.html?mandato=2019", "brasil.html?" in pg.url and "mandato=2019" in pg.url, pg.url.split("/")[-1])
        h1 = await pg.locator("h1").inner_text()
        ok("o título (h1) diz o período", "2019 a 2022" in h1, h1.replace("\n", " "))
        ok("a aba do navegador diz o período", "2019 a 2022" in await pg.title(), await pg.title())
        faixa = await pg.locator(".faixa-passado").inner_text()
        ok("faixa em texto: “Você está vendo o passado”", "Você está vendo o passado" in faixa and "2019 a 2022" in faixa)
        can = await pg.locator('link[rel="canonical"]').get_attribute("href")
        ok("endereço canônico com o mandato", can.endswith("brasil.html?mandato=2019"), can)
        cards = await pg.locator("#exec-topo .pessoa-grande").all_inner_texts()
        ok("presidente e vice eleitos em 2018 (sem link para perfil)", len(cards) == 2 and "Jair Bolsonaro" in cards[0] and "Mourão" in cards[1]
           and await pg.locator("#exec-topo a.pessoa-grande").count() == 0, " / ".join(c.split("\n")[1] for c in cards if "\n" in c))
        ok("ministros e busca ficam escondidos, com aviso", not await pg.locator("#ministros").is_visible() and not await pg.locator("#procurar").is_visible()
           and "ministros de governos anteriores" in await pg.locator("#executivo").inner_text())
        sen = await pg.locator("#senado .contagem").inner_text()
        cam = await pg.locator("#camara .contagem").inner_text()
        ok("Senado de 2019 a 2022: 80 eleitos + aviso da eleição suplementar de MT; Câmara: 513", "80" in sen and "513" in cam
           and "Mato Grosso" in await pg.locator("#senado").inner_text(), f"{sen} | {cam}")
        ok("cartões das listas sem link para perfil", await pg.locator("#senado .grade-pessoas a").count() == 0 and await pg.locator("#senado .pessoa-card.passado").count() > 10)
        # filtro de estado na lista do passado
        fuf = pg.locator("#senado .filtros-casa .combo input").first
        await fuf.click()
        await pg.keyboard.type("bahia", delay=40)
        await pg.wait_for_timeout(500)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        ok("filtro de estado no Senado do passado", "3 de 80" in await pg.locator("#senado .contagem").inner_text(), await pg.locator("#senado .contagem").inner_text())
        # "Mostrar mais" leva o foco para o primeiro cartão novo
        mais = pg.locator("#camara .ver-mais")
        await mais.scroll_into_view_if_needed()
        await mais.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        foco = await pg.evaluate("document.activeElement && document.activeElement.className")
        ok("“Mostrar mais” põe o foco no primeiro cartão novo", "pessoa-card" in (foco or ""), foco)
        # voltar para hoje
        await pg.locator(".faixa-passado a").click()
        await pg.wait_for_load_state("networkidle")
        ok("“Voltar para hoje” volta para brasil.html sem mandato", "brasil.html" in pg.url and "mandato" not in pg.url, pg.url.split("/")[-1])

        # 3. 2016: o que mudou no mandato de 2015 a 2018, com fonte
        await pg.goto(BASE + "brasil.html?mandato=2015", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        mud = await pg.locator(".mudancas").inner_text() if await pg.locator(".mudancas").count() else ""
        ok("2015 a 2018: as mudanças de 2016 aparecem com data e fonte", "12 de maio de 2016" in mud and "31 de agosto de 2016" in mud
           and await pg.locator(".mudancas .fontes-btn").count() == 2)
        await pg.goto(BASE + "brasil.html?mandato=1995&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#exec-topo").inner_text()
        ok("1995–1998 (inglês): FHC e o vice da galeria oficial (o TSE de 1994 não liga o vice)", "Fernando Henrique Cardoso" in txt and "Marco Maciel" in txt
           and "Party at the election" in txt and "81" in await pg.locator("#senado .contagem").inner_text(), txt.replace("\n", " ")[:120])
        ok("1995–1998 (inglês): faixa e título em inglês", "You are looking at the past" in await pg.locator(".faixa-passado").inner_text()
           and "1995–1998" in await pg.title(), await pg.title())

        # 4. mandato de hoje ou que não existe: a página volta para hoje
        await pg.goto(BASE + "brasil.html?mandato=2023&lang=pt")
        await pg.wait_for_url(lambda u: "mandato" not in u, timeout=15000)
        ok("?mandato=2023 (o de hoje) volta para a página de hoje", pg.url.endswith("brasil.html?lang=pt"), pg.url.split("/")[-1])
        await pg.goto(BASE + "brasil.html?mandato=1990")
        await pg.wait_for_url(lambda u: "mandato" not in u, timeout=15000)
        ok("?mandato=1990 (sem dados) volta para a página de hoje", "mandato" not in pg.url, pg.url.split("/")[-1])

        # 5. estado: escolher 1995 a 1998 pelo campo
        await pg.goto(BASE + "estado.html?uf=BA&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("Estado hoje: campo com o mandato atual", "(atual)" in await pg.locator("#mandato-lugar input").input_value())
        await escolhe_mandato(pg, "1995")
        ok("estado: escolher 1995 abre estado.html?uf=BA&mandato=1995", "uf=BA" in pg.url and "mandato=1995" in pg.url, pg.url.split("/")[-1])
        gov = await pg.locator("#governo").inner_text()
        ok("Bahia 1995 a 1998: governador eleito em 1994 e aviso de que o TSE não liga o vice", "Paulo Ganem Souto" in gov and "não liga o vice" in gov)
        nsen = await pg.locator("#lista-sen .pessoa-card").count()
        fed = await pg.locator("#casa-fed .contagem").inner_text()
        est = await pg.locator("#casa-est .contagem").inner_text()
        ok("Bahia 1995 a 1998: 3 senadores, 39 deputados federais e 63 estaduais", nsen == 3 and "39" in fed and "63" in est, f"{nsen} | {fed} | {est}")
        await pg.goto(BASE + "estado.html?uf=DF&mandato=2003&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        h1 = await pg.locator("#titulo-uf").inner_text()
        ok("DF 2003–2006 (inglês): título com o período e deputados distritais", "2003–2006" in h1 and "district deputies" in (await pg.locator("#estaduais").inner_text()).lower()
           and "24" in await pg.locator("#casa-est .contagem").inner_text(), h1.replace("\n", " "))

        # 6. cidade: passado, trocar de cidade mantém o mandato; cidade que ainda não existia
        await pg.goto(BASE + "cidade.html?ibge=2927408&mandato=1997&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        txt = await pg.locator("#cidade").inner_text()
        ok("Salvador 1997 a 2000: prefeito eleito em 1996 e 35 vereadores", "Imbassahy" in txt and "35" in await pg.locator("#casa-ver .contagem").inner_text())
        await pg.focus("#campo-cidade")
        await pg.keyboard.press("Control+A")
        await pg.keyboard.type("feira de", delay=40)
        await pg.wait_for_timeout(700)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1800)
        nome = await pg.locator("#nome-cidade").inner_text()
        foco = await pg.evaluate("document.activeElement && document.activeElement.id")
        ok("trocar de cidade mantém o mandato (Feira de Santana em 1997 a 2000) e leva o foco ao nome", "ibge=2910800" in pg.url and "mandato=1997" in pg.url
           and "Feira de Santana" in nome and foco == "nome-cidade", pg.url.split("?")[-1])
        await pg.goto(BASE + "cidade.html?ibge=1504752&mandato=1997", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#cidade").inner_text()
        ok("Mojuí dos Campos (criada depois): “ainda não era um município”, com a 1ª eleição (2012)", "ainda não era um município" in txt and "2012" in txt)
        await pg.goto(BASE + "cidade.html?ibge=3518800&mandato=2017", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#cidade").inner_text()
        ok("Guarulhos 2017 a 2020: o TSE não mostra os vereadores (34 cadeiras) e a lista diz isso", "34 cadeiras" in txt and "não mostra os vereadores" in txt)
        await pg.goto(BASE + "cidade.html?ibge=5300108&mandato=2021", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        ok("Brasília com mandato: explica que não tem prefeito e tira o mandato do endereço", "Distrito Federal" in await pg.locator("#cidade").inner_text() and "mandato" not in pg.url)
        await pg.goto(BASE + "cidade.html?ibge=2927408", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("cidade hoje: campo “Ver outro mandato” com 2025 a 2028 (atual)", "2025 a 2028 (atual)" in await pg.locator("#mandato-lugar input").input_value())

        # 7. virada de mandato pelas datas (relógio do navegador em 10/2/2027, depois da posse de 5/1/2027)
        await ctx.clock.set_fixed_time(datetime.datetime(2027, 2, 10, 12, 0, tzinfo=datetime.timezone.utc))
        await pg.goto(BASE + "brasil.html?lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        val = await pg.locator("#mandato-lugar input").input_value()
        ok("em 2027, o mandato atual vira 2027 a 2030 e 2023 a 2026 passa a ser passado", val.startswith("2027 a 2030") and "(atual)" in val, val)
        await pg.goto(BASE + "brasil.html?mandato=2023&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("em 2027, brasil.html?mandato=2023 mostra o passado (Lula e Alckmin)", "mandato=2023" in pg.url and "Lula" in await pg.locator("#exec-topo").inner_text()
           and await pg.locator(".faixa-passado").count() == 1)

        ok("sem erros de JavaScript", not erros, "; ".join(erros)[:300])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")


asyncio.run(main())
