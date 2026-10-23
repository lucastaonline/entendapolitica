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
        ok("ministros e busca de hoje ficam escondidos; aparecem os ministros do governo Bolsonaro", not await pg.locator("#ministros").is_visible()
           and not await pg.locator("#procurar").is_visible() and await pg.locator("#min-hist").is_visible()
           and "Ministros de Jair Messias Bolsonaro" in await pg.locator("#min-hist").inner_text()
           and "ainda não aparecem" not in await pg.locator("#executivo").inner_text())
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

        # 3b. ministros dos governos anteriores (Biblioteca da Presidência e Diário Oficial)
        gov = pg.locator("#min-hist .min-gov")
        cab = [t.replace("\n", " ") for t in await gov.locator("h4").all_inner_texts()]
        ok("2015 a 2018: duas listas de ministros (Dilma até 12/5/2016, Temer desde 12/5/2016)", len(cab) == 2
           and "Dilma Rousseff" in cab[0] and "De 1º de janeiro de 2015 a 12 de maio de 2016" in cab[0]
           and "Michel Temer" in cab[1] and "De 12 de maio de 2016 a 31 de dezembro de 2018" in cab[1]
           and "O governo mudou em 12 de maio de 2016" in await pg.locator("#min-hist").inner_text(), " | ".join(cab))

        async def cartao(g, nome):
            for c in await pg.locator("#min-hist .min-gov").nth(g).locator(".min-hist-card").all():
                if (await c.locator("h5").inner_text()).strip() == nome:
                    return c
            return None
        faz = await cartao(1, "Ministério da Fazenda")
        txt = await faz.inner_text() if faz else ""
        ok("Temer: Fazenda com Henrique Meirelles (12/05/2016 a 06/04/2018) e Eduardo Guardia", "Henrique de Campos Meirelles" in txt
           and "12/05/2016 a 06/04/2018" in txt and "Eduardo Refinetti Guardia" in txt, txt.replace("\n", " ")[:160])
        cc = await cartao(0, "Casa Civil da Presidência da República")
        txt = await cc.inner_text() if cc else ""
        ok("Dilma: Casa Civil com Lula (16/03 a 11/05/2016) e a nota do STF sobre a nomeação", "Luiz Inácio Lula da Silva" in txt
           and "Supremo Tribunal Federal" in txt, txt.replace("\n", " ")[:160])
        nomes = [t.strip() for t in await pg.locator("#min-hist .min-gov").nth(1).locator(".min-hist-card h5").all_inner_texts()]
        ordem = await pg.evaluate("l => l.slice().sort((a, b) => a.localeCompare(b, 'pt', {sensitivity: 'base'}))", nomes)
        ok("cartões em ordem alfabética do ministério", nomes == ordem and len(nomes) > 20, " / ".join(nomes[:4]))
        n_cart = await pg.locator(".min-hist-card").count()
        ok("cartões sem link, cada um com a sua fonte", n_cart > 50 and await pg.locator(".min-hist-card a").count() == 0
           and await pg.locator(".min-hist-card .fontes-btn").count() == n_cart, f"{n_cart} cartões")
        # interinos pelo teclado (detalhes fechados que abrem com Enter)
        resumo = faz.locator("summary").first if faz and await faz.locator("summary").count() else pg.locator(".min-hist-card summary").first
        await resumo.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(300)
        aberto = await resumo.evaluate("s => s.parentElement.open")
        ok("“Interinos” abre pelo teclado", aberto and await resumo.evaluate("s => document.activeElement === s"))
        # fonte do cartão: decretos do Diário Oficial
        await faz.locator(".fontes-btn").click()
        await pg.wait_for_timeout(500)
        dlg = pg.locator("dialog[open], [role=dialog]").last
        txt = await dlg.inner_text()
        ok("a fonte do cartão abre com os decretos do Diário Oficial", "Diário Oficial da União" in txt and await dlg.locator("a[href*='in.gov.br']").count() >= 2, txt.replace("\n", " ")[:120])
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(300)
        # nomeação tornada sem efeito: linha no cartão, as duas fontes no botão e o aviso de intervalo sem contradição
        async def fontes_do(c):
            await c.locator(".fontes-btn").click()
            await pg.wait_for_timeout(500)
            d = pg.locator("[role=dialog]").last
            t = await d.inner_text()
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
            return t
        trab = await cartao(1, "Ministério do Trabalho")
        txt = await trab.inner_text() if trab else ""
        ok("Temer, Trabalho: a nomeação de Cristiane Brasil (3/1/2018), tornada sem efeito em 22/2/2018, aparece numa linha",
           "A nomeação de Cristiane Brasil Francisco, em 03/01/2018, foi tornada sem efeito (anulada) por um decreto de 22/02/2018." in txt,
           txt.replace("\n", " ")[:200])
        ok("Temer, Trabalho: o aviso de intervalo fala de nomeação válida (não contradiz a linha)",
           "O Diário Oficial não traz nomeação válida de ministro de 28/12/2017 a 09/04/2018." in txt
           and "não traz nomeação de ministro de 28/12/2017" not in txt)
        f = await fontes_do(trab) if trab else ""
        ok("Temer, Trabalho: as fontes têm os dois decretos (nomeação de 3/1/2018 e o que a tornou sem efeito, de 22/2/2018)",
           "Decreto de 03/01/2018: nomeação de Cristiane Brasil Francisco" in f and "Decreto de 22/02/2018: torna sem efeito a nomeação de Cristiane Brasil Francisco" in f,
           f.replace("\n", " ")[:160])
        ok("Cristiane Brasil não aparece como ministra (sem período)", "Cristiane Brasil Francisco" not in (await trab.locator(".mh-lista").all_inner_texts() if trab else [""])[0])
        mh = await pg.locator("#min-hist .min-gov").nth(0).inner_text()
        ok("Dilma, Integração Nacional: nomeação interina anulada (13/4/2016), com o outro decreto igual de 15/4/2016",
           "A nomeação interina de José Rodrigues Pinheiro Dória, em 13/04/2016, foi tornada sem efeito (anulada) por um decreto de 14/04/2016. Outro decreto, de 15/04/2016, diz o mesmo." in mh)
        # 1995: o que falta na lista da Biblioteca veio do Diário Oficial, com nota
        await pg.goto(BASE + "brasil.html?mandato=1995&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        mh = await pg.locator("#min-hist").inner_text()
        ok("1995 a 1998: ministros de FHC (Malan na Fazenda, com a nota de onde veio) e a fonte da Biblioteca", "Ministros de Fernando Henrique Cardoso" in mh
           and "Pedro Sampaio Malan" in mh and "não traz o Ministério da Fazenda no 1º mandato" in mh and "Biblioteca da Presidência" in mh)
        ok("1995 a 1998: cartão avisa quando a lista não traz ninguém (Justiça, abril e maio de 1997)", "não traz ninguém à frente desta pasta de 08/04/1997 a 22/05/1997" in mh)
        # 320 px: sem rolar para os lados
        await pg.set_viewport_size({"width": 320, "height": 800})
        await pg.goto(BASE + "brasil.html?mandato=2015&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        larg = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        ok("celular de 320 px: os ministros cabem sem rolar para os lados", larg[0] <= larg[1], f"{larg[0]} <= {larg[1]}")
        await pg.set_viewport_size({"width": 1280, "height": 860})
        # inglês: nomes de ministério traduzidos; sem tradução segura, o nome fica marcado como português
        await pg.goto(BASE + "brasil.html?mandato=2019&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        mh = await pg.locator("#min-hist").inner_text()
        ok("2019–2022 (inglês): “The ministers”, Ministry of the Economy com Paulo Guedes e datas em inglês", "The ministers" in mh
           and "Ministers of Jair Messias Bolsonaro" in mh and "Ministry of the Economy" in mh and "Paulo Roberto Nunes Guedes" in mh and "Jan 1, 2019" in mh)
        ok("2019–2022 (inglês): Decotelli na Educação, nomeação de 25/6/2020 tornada sem efeito em 30/6/2020, e intervalo sem nomeação válida",
           "The appointment of Carlos Alberto Decotelli da Silva on Jun 25, 2020 was made void by a decree of Jun 30, 2020." in mh
           and "The Official Gazette shows no valid minister appointment from Jun 20, 2020 to Jul 10, 2020." in mh)
        await pg.goto(BASE + "brasil.html?mandato=2019&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        edu = None
        for c in await pg.locator("#min-hist .min-hist-card").all():
            if (await c.locator("h5").inner_text()).strip() == "Ministério da Educação":
                edu = c
        txt = await edu.inner_text() if edu else ""
        f = await fontes_do(edu) if edu else ""
        ok("2019 a 2022: Decotelli na Educação, com a linha e as duas fontes (25/6/2020 e 30/6/2020)",
           "A nomeação de Carlos Alberto Decotelli da Silva, em 25/06/2020, foi tornada sem efeito (anulada) por um decreto de 30/06/2020." in txt
           and "Decreto de 25/06/2020: nomeação de Carlos Alberto Decotelli da Silva" in f
           and "Decreto de 30/06/2020: torna sem efeito a nomeação de Carlos Alberto Decotelli da Silva" in f, f.replace("\n", " ")[:160])
        await pg.goto(BASE + "brasil.html?mandato=1999&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("1999–2002 (inglês): ministério sem tradução segura aparece em português, marcado com lang=pt-BR",
           await pg.locator(".min-hist-card h5 [lang='pt-BR']", has_text="Ministério da Política e do Desenvolvimento Agrário").count() == 1)
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
        ok("em 2027, o mandato de 2023 sem lista de ministros diz isso (sem prometer)", "não tem a lista de ministros deste mandato" in await pg.locator("#min-hist").inner_text())

        ok("sem erros de JavaScript", not erros, "; ".join(erros)[:300])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")


asyncio.run(main())
