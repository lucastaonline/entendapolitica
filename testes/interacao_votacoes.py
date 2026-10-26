"""Testes das votações (votacoes.html, votacao.html, o bloco do Brasil e a parte "Como votou" do perfil):
teclado, filtros com busca, "Mostrar mais" com o foco, números que batem com os dados, inglês, 320 px e axe-core
nos estados que só aparecem depois de rolar ou clicar. Playwright + Edge; precisa do servidor em 8770.
Uso: python testes/interacao_votacoes.py"""
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8771/
RAIZ = Path(__file__).resolve().parent.parent
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []

CAMARA = "2236186-60"     # PLP 281/2019: texto principal, regra de lei complementar, orientações de partido, bloco e federação
SENADO = "7107"           # PEC 221/2019, 2º turno: 81 senadores, quem presidia, orientações
DEP_PL = "dep-221328"     # deputado com orientação do partido em quase todas as votações


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(caminho):
    return json.loads((RAIZ / caminho).read_text(encoding="utf-8"))


async def axe(pg, nome):
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                          resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    ok(f"axe sem problemas: {nome}", not v, "; ".join(v)[:300])


async def sem_rolar_de_lado(pg, nome):
    larg = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    ok(f"320 px sem rolar para os lados: {nome}", larg[0] <= larg[1] + 1, str(larg))


# a mesma procura de português solto (e "undefined"/"null") de testes/verifica_texto.py, mas depois de rolar até as partes
# que só aparecem perto da tela
JS_TEXTO = re.search(r'JS = r"""(.*?)"""', (RAIZ / "testes" / "verifica_texto.py").read_text(encoding="utf-8"), re.S).group(1)


async def texto_en(pg, nome):
    achados = await pg.evaluate(JS_TEXTO)
    ok(f"inglês sem português solto: {nome}", not achados, "; ".join(f"[{k}] {t}" for k, t in achados)[:300])


async def main():
    cam = dados("dados/votacoes/camara.json")["votacoes"]
    sen = dados("dados/votacoes/senado.json")["votacoes"]
    det = dados(f"dados/votacoes/camara/{CAMARA}.json")
    det_s = dados(f"dados/votacoes/senado/{SENADO}.json")
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda e: erros.append(str(e)))
        await pg.goto(BASE + "index.html?lang=pt", wait_until="networkidle")

        # ------------------------------------------------------------ 1. lista de todas as votações
        await pg.goto(BASE + "votacoes.html", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        total = len(cam) + len(sen)
        cont = await pg.locator("#contagem-vot").inner_text()
        n = await pg.locator("#lista-votacoes .vot-card").count()
        ok("lista: 30 cartões e a contagem das duas Casas", n == 30 and f"de {total:,}".replace(",", ".") in cont, f"{n} | {cont}")
        primeiro = await pg.locator("#lista-votacoes .vot-card").first.inner_text()
        mais_nova = max(list(cam.values()) + list(sen.values()), key=lambda v: (v["data"], v.get("hora") or ""))
        ok("lista: a mais nova vem primeiro", mais_nova["proposta"] in primeiro, primeiro.split("\n")[1:3])
        # filtro com busca, só com o teclado
        await pg.focus("#f-casa-campo")
        await pg.keyboard.type("sen", delay=40)
        await pg.wait_for_timeout(500)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        casas = await pg.locator("#lista-votacoes .chip-casa").all_inner_texts()
        cont = await pg.locator("#contagem-vot").inner_text()
        ok("filtro Casa = Senado (teclado): só Senado e a contagem muda", casas and all("Senado" in c for c in casas) and f"de {len(sen)} " in cont and "casa=senado" in pg.url,
           f"{len(casas)} | {cont} | {pg.url.split('/')[-1]}")
        await pg.focus("#f-cat-campo")
        await pg.keyboard.type("texto", delay=40)
        await pg.wait_for_timeout(500)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        cats = await pg.locator("#lista-votacoes .chip-cat").all_inner_texts()
        n_ok = sum(1 for v in sen.values() if v["categoria"] == "principal")
        cont = await pg.locator("#contagem-vot").inner_text()
        ok("filtro tipo = texto principal: só texto principal", cats and all("Texto principal" in c for c in cats) and f"de {n_ok} " in cont, cont)
        await axe(pg, "votacoes.html com filtros")
        # endereço com filtros abre a lista já filtrada
        await pg.goto(BASE + "votacoes.html?casa=camara&cat=procedimento&ano=2025", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        esperado = sum(1 for v in cam.values() if v["categoria"] == "procedimento" and v["data"].startswith("2025"))
        cont = await pg.locator("#contagem-vot").inner_text()
        valor = await pg.locator("#f-cat-campo").input_value()
        ok("endereço com filtros (casa, tipo, ano) já abre filtrado", f"de {esperado} " in cont and valor == "Procedimento", f"{cont} | {valor}")
        # busca por proposta
        await pg.goto(BASE + "votacoes.html", wait_until="networkidle")
        await pg.wait_for_timeout(600)
        await pg.fill("#f-q", "PEC 45")
        await pg.wait_for_timeout(900)
        tits = await pg.locator("#lista-votacoes .vot-card").all_inner_texts()
        ok("busca “PEC 45” acha só votações de PEC com o número 45", tits and all("PEC" in t and re.search(r"(?<![\d.])45\b", t) for t in tits), f"{len(tits)} cartões")
        await pg.fill("#f-q", "")
        await pg.wait_for_timeout(900)
        # "Mostrar mais": o foco vai para a primeira votação nova
        await pg.focus("#ver-mais-vot")
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        n = await pg.locator("#lista-votacoes .vot-card").count()
        foco = await pg.evaluate("document.activeElement && document.activeElement.closest('.vot-card') && [...document.querySelectorAll('#lista-votacoes .vot-card')].indexOf(document.activeElement.closest('.vot-card'))")
        ok("“Mostrar mais” traz mais 30 e põe o foco na 31ª", n == 60 and foco == 30, f"{n} cartões, foco no {foco}")
        # abrir uma votação pelo cartão
        href = await pg.locator("#lista-votacoes .vot-tit a").first.get_attribute("href")
        await pg.locator("#lista-votacoes .vot-card").first.click()
        await pg.wait_for_url("**/votacao.html?*", timeout=15000)
        ok("clicar no cartão abre a votação", href in pg.url, pg.url.split("/")[-1])

        # ------------------------------------------------------------ 2. uma votação da Câmara
        await pg.goto(BASE + f"votacao.html?casa=camara&id={CAMARA}", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        h1 = await pg.locator("h1").inner_text()
        ok("votação: o título é a proposta", h1 == det["proposta"]["sigla"], h1)
        numeros = await pg.locator(".placar-grande li").all_inner_texts()
        sim = det["placar"]["Sim"]
        ok("placar grande bate com os dados (Sim, Não e quem não registrou voto)", any(f"Sim\n{sim}" in t or (str(sim) in t and "Sim" in t) for t in numeros)
           and any(str(513 - det["placar"]["total"]) in t for t in numeros), " | ".join(t.replace("\n", " ") for t in numeros))
        cad = await pg.locator(".plen-voto .plenario i").count()
        cad_sim = await pg.locator('.plen-voto .plenario i[data-g="0"]').count()
        cad_nao = await pg.locator('.plen-voto .plenario i[data-g="5"]').count()
        ok("plenário 3D: 513 cadeiras, as do Sim e as do Não batem", cad == 513 and cad_sim == sim and cad_nao == det["placar"]["Não"], f"{cad} / {cad_sim} / {cad_nao}")
        ok("plenário é só desenho (aria-hidden)", await pg.locator(".plen-voto .plenario").get_attribute("aria-hidden") == "true")
        quorum = await pg.locator(".quorum-vot").inner_text()
        ok("regra da lei complementar (257) com o número de Sim", "257" in quorum and str(sim) in quorum, quorum[:90])
        linhas = await pg.locator(".partidos-vot .pv-n").all_inner_texts()
        ns = [int(t.split()[0].replace(".", "")) for t in linhas]
        ok("partidos: soma = total e do maior para o menor", sum(ns) == det["placar"]["total"] and ns == sorted(ns, reverse=True), f"{sum(ns)} em {len(ns)} partidos")
        pl = pg.locator(".pv", has=pg.locator(".pv-nome", has_text="PL")).first
        ori_pl = await pl.locator(".pv-ori").inner_text()
        pt = await pg.locator(".pv", has=pg.locator('.pv-nome:text-is("PT")')).first.locator(".pv-ori").inner_text()
        ok("orientação como fato: do partido (PL) e da federação (PT)", "partido: " + det["orientacaoPartidos"]["PL"]["orientacao"] in ori_pl and "federação" in pt, f"{ori_pl} | {pt}")
        lids = await pg.locator("#orientacoes .lid-lista li").count()
        ok("lista de todas as orientações publicadas", lids == len(det["orientacoes"]), f"{lids} de {len(det['orientacoes'])}")
        # quem votou o quê: filtros com busca (teclado), nome e "Mostrar mais"
        await pg.focus("#q-voto-campo")
        await pg.keyboard.type("não", delay=40)
        await pg.wait_for_timeout(500)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        chips = await pg.locator("#lista-quem .voto-chip").all_inner_texts()
        cont = await pg.locator("#contagem-quem").inner_text()
        ok("filtro de voto = Não (teclado): só Não", chips and all(c.strip().endswith("Não") for c in chips) and f"de {det['placar']['Não']} " in cont, cont)
        await pg.focus("#q-partido-campo")
        await pg.keyboard.type("pt", delay=40)
        await pg.wait_for_timeout(500)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        cards = await pg.locator("#lista-quem .voto-card small").all_inner_texts()
        n_pt = sum(1 for v in det["votos"] if v[2] == "PT" and v[4] == "Não")
        cont = await pg.locator("#contagem-quem").inner_text()
        ok("filtro de partido = PT junto com Não", f"de {n_pt} " in cont and all(c.startswith("PT ·") for c in cards if "·" in c), cont)
        await axe(pg, "votação com filtros aplicados")
        await pg.goto(BASE + f"votacao.html?casa=camara&id={CAMARA}", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        await pg.fill("#q-nome", "silva")
        await pg.wait_for_timeout(600)
        nomes = await pg.locator("#lista-quem .voto-card b").all_inner_texts()
        ok("procurar pelo nome (“silva”)", nomes and all("silva" in x.lower() for x in nomes), f"{len(nomes)} pessoas")
        await pg.fill("#q-nome", "")
        await pg.wait_for_timeout(600)
        await pg.focus("#ver-mais-quem")
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(500)
        foco = await pg.evaluate("[...document.querySelectorAll('#lista-quem > *')].indexOf(document.activeElement)")
        ok("“Mostrar mais” em quem votou: foco na 61ª pessoa", foco == 60, str(foco))
        # combobox aberto também passa no axe
        await pg.click("#q-uf-campo")
        await pg.wait_for_timeout(400)
        await axe(pg, "votação com a lista de estados aberta")
        await pg.keyboard.press("Escape")
        # fontes: janela abre e fecha com Esc, devolvendo o foco
        b = pg.locator("#resultado .fontes-btn").first
        await b.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(400)
        aberta = await pg.locator('[role="dialog"]:visible').count()
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(300)
        volta = await pg.evaluate("document.activeElement && document.activeElement.classList.contains('fontes-btn')")
        ok("“De onde vem essa regra?” abre a janela; Esc fecha e devolve o foco", aberta and volta)
        # o cartão de quem está no cargo leva ao perfil
        a = pg.locator("#lista-quem a.voto-card").first
        href = await a.get_attribute("href")
        await a.click()
        await pg.wait_for_url("**/pessoa.html?id=*", timeout=15000)
        ok("cartão de quem votou abre o perfil", href in pg.url, href)

        # ------------------------------------------------------------ 3. uma votação do Senado (em inglês)
        await pg.goto(BASE + f"votacao.html?casa=senado&id={SENADO}&lang=en", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        cont = await pg.locator("#contagem-quem").inner_text()
        rot = await pg.locator(".placar-grande .pg-rot").all_inner_texts()
        pres = await pg.locator("#resultado").inner_text()
        ok("Senado em inglês: 81 senadores, “Yes/No” e quem presidia", "of 81" in cont and "Yes" in rot and "No" in rot and (det_s["presidente"] or "") in pres, f"{cont} | {rot}")
        ok("Senado: 81 cadeiras no plenário", await pg.locator(".plen-voto .plenario i").count() == 81)
        ok("Senado: regra da PEC (49) em inglês", "49" in await pg.locator(".quorum-vot").inner_text())
        # endereço inválido (de volta ao português: a escolha do idioma fica salva no aparelho)
        await pg.goto(BASE + "votacao.html?casa=camara&id=999999-1&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        ok("votação que não existe: aviso e caminho para a lista", await pg.locator('a[href="votacoes.html"]').count() > 0 and "Não encontramos" in await pg.locator("main").inner_text())

        # ------------------------------------------------------------ 4. perfil: "Como votou" com filtro por tipo, link e orientação
        await pg.goto(BASE + f"pessoa.html?id={DEP_PL}", wait_until="networkidle")
        await pg.locator("#votacoes").scroll_into_view_if_needed()
        await pg.wait_for_selector("#lista-votos .voto-chip", timeout=15000)
        await pg.wait_for_timeout(500)
        botoes = await pg.locator("#filtro-votos [data-vcat]").count()
        ok("perfil: 4 botões de tipo (Todas, Texto principal, Mudanças, Procedimentos)", botoes == 4, str(botoes))
        b = pg.locator('#filtro-votos [data-vcat="principal"]')
        await b.focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(400)
        pressed = await b.get_attribute("aria-pressed")
        outros = await pg.locator('#filtro-votos [data-vcat=""]').get_attribute("aria-pressed")
        etiquetas = await pg.locator("#lista-votos li .chip").all_inner_texts()
        foco = await pg.evaluate("document.activeElement && document.activeElement.getAttribute('data-vcat')")
        ok("perfil: “Texto principal” fica marcado, só ele aparece e o foco continua no botão",
           pressed == "true" and outros == "false" and etiquetas and all("Texto principal" in e for e in etiquetas) and foco == "principal", f"{len(etiquetas)} itens")
        ori = await pg.locator("#lista-votos li small", has_text="Orientação").count()
        ok("perfil: a orientação do partido aparece como fato", ori > 0, f"{ori} itens com orientação")
        await axe(pg, "perfil com as votações carregadas e filtradas")
        await pg.focus("#ver-mais-votos")
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(400)
        foco = await pg.evaluate("[...document.querySelectorAll('#lista-votos > li')].indexOf(document.activeElement)")
        ok("perfil: “Mostrar mais votações” põe o foco na 16ª", foco == 15, str(foco))
        link = pg.locator("#lista-votos li .v-txt > a").first
        href = await link.get_attribute("href")
        voto = (await pg.locator("#lista-votos li .voto-chip").first.inner_text()).replace("Voto:", "").strip()
        await link.click()
        await pg.wait_for_url("**/votacao.html?*", timeout=15000)
        await pg.wait_for_timeout(1200)
        await pg.fill("#q-nome", "Adilson Barroso")
        await pg.wait_for_timeout(600)
        chip = (await pg.locator("#lista-quem .voto-chip").first.inner_text()).replace("Voto:", "").strip()
        ok("perfil → votação: a página certa, com o mesmo voto da pessoa", "votacao.html?casa=camara&id=" in href and chip == voto, f"{href} | {voto} = {chip}")

        # ------------------------------------------------------------ 5. Brasil: "Como o Congresso votou"
        await pg.goto(BASE + "brasil.html", wait_until="networkidle")
        await pg.locator("#votacoes").scroll_into_view_if_needed()
        await pg.wait_for_selector("#votos-recentes .vot-card", timeout=15000)
        await pg.wait_for_timeout(1500)  # espera o bloco terminar de aparecer (animação ao rolar)
        cards = await pg.locator("#votos-recentes .vot-card").all_inner_texts()
        tits = await pg.locator("#votos-recentes .vot-tit").all_inner_texts()
        ok("Brasil: 3 votações do texto principal, de propostas diferentes", len(cards) == 3 and all("Texto principal" in c for c in cards) and len(set(tits)) == 3, " | ".join(t.split(",")[0] for t in tits))
        ok("Brasil: botão para todas as votações", await pg.locator('#votacoes a[href="votacoes.html"]').count() == 1)
        await axe(pg, "Brasil com as votações carregadas")

        # ------------------------------------------------------------ 6. inglês: o perfil e a lista
        await pg.goto(BASE + f"pessoa.html?id={DEP_PL}&lang=en", wait_until="networkidle")
        await pg.locator("#votacoes").scroll_into_view_if_needed()
        await pg.wait_for_selector("#lista-votos .voto-chip", timeout=15000)
        await pg.wait_for_timeout(1200)
        txt = await pg.locator("#votacoes").inner_text()
        ok("perfil em inglês: tipos e orientação em inglês", "Main text" in txt and "Party's orientation" in txt and "Texto principal" not in txt)
        await texto_en(pg, "perfil com as votações")
        await axe(pg, "perfil em inglês com as votações")
        await pg.goto(BASE + "brasil.html?lang=en", wait_until="networkidle")
        await pg.locator("#votacoes").scroll_into_view_if_needed()
        await pg.wait_for_selector("#votos-recentes .vot-card", timeout=15000)
        await pg.wait_for_timeout(1500)
        await texto_en(pg, "Brasil com as votações")
        await pg.goto(BASE + "votacoes.html?lang=en&casa=camara&q=mantido", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("“Mantido o texto”: o resultado vem da descrição (Text kept)", "text kept" in (await pg.locator("#lista-votacoes").inner_text()).lower())
        await texto_en(pg, "lista filtrada")
        await pg.goto(BASE + "index.html?lang=pt", wait_until="networkidle")

        # ------------------------------------------------------------ 7. celular de 320 px: nada rola para os lados
        ctx2 = await nav.new_context(viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True)
        pc = await ctx2.new_page()
        pc.on("pageerror", lambda e: erros.append(str(e)))
        for url, sec in (("votacoes.html", "#todas"), (f"votacao.html?casa=camara&id={CAMARA}", "#quem"), (f"votacao.html?casa=senado&id={SENADO}&lang=en", "#partidos"),
                         (f"pessoa.html?id={DEP_PL}", "#votacoes"), ("brasil.html", "#votacoes")):
            await pc.goto(BASE + url, wait_until="networkidle")
            await pc.locator(sec).scroll_into_view_if_needed()
            await pc.wait_for_timeout(1800)
            await sem_rolar_de_lado(pc, url + " " + sec)
        await ctx2.close()

        ok("sem erros de JavaScript", not erros, "; ".join(erros)[:200])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")


asyncio.run(main())
