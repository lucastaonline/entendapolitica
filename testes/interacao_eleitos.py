"""Testes de "Quem assume" (eleitos em 2026, até a posse): o mandato 2027 do Brasil e do estado (desde a mandatos-r11, as mesmas\nabas da página de hoje; os endereços antigos #quem-assume levam para lá), a próxima
eleição da cidade (#proxima-eleicao), o perfil e26- de quem foi eleito e não tem cargo hoje, o selo de quem já tem cargo,
a busca e o sitemap. Números da página x dados/eleitos/, filtros pelo teclado, links, inglês, 320 px, axe-core e nenhum
erro de JavaScript. Também simula o dia seguinte às posses (scripts/eleitos.py --hoje) e um arquivo que não existe mais.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/).
Uso: python testes/interacao_eleitos.py"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8773/
RAIZ = Path(__file__).resolve().parent.parent
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
UF = "AP"  # estado pequeno, com governador e vice sem cargo hoje (perfis e26-)


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(caminho):
    return json.loads((RAIZ / caminho).read_text(encoding="utf-8"))


def num(n):
    return f"{n:,}".replace(",", ".")


def num_en(n):
    return f"{n:,}"


async def axe(pg, nome, onde=None):
    """axe-core na página inteira ou só numa parte (onde = seletor CSS: no brasil.html, outras frentes mexem em outras seções)."""
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async (onde) => {
      const r = await axe.run(onde ? document.querySelector(onde) : document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                          resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""", onde)
    ok(f"axe sem problemas: {nome}", not v, "; ".join(v)[:300])


async def sem_rolar_de_lado(pg, nome):
    larg = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    ok(f"320 px sem rolar para os lados: {nome}", larg[0] <= larg[1] + 1, str(larg))


JS_TEXTO = re.search(r'JS = r"""(.*?)"""', (RAIZ / "testes" / "verifica_texto.py").read_text(encoding="utf-8"), re.S).group(1)


async def texto_en(pg, nome):
    achados = await pg.evaluate(JS_TEXTO)
    ok(f"inglês sem português solto: {nome}", not achados, "; ".join(f"[{k}] {t}" for k, t in achados)[:300])


async def rola_tudo(pg):
    await pg.evaluate("""async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 450) { scrollTo(0, y);
      await new Promise(r => setTimeout(r, 50)); } }""")
    await pg.wait_for_timeout(1600)  # as partes que aparecem ao rolar terminam de surgir (o axe mede o contraste no fim)


async def ir(pg, url, ate=None):
    if "lang=" not in url:  # a escolha do idioma fica salva no navegador: as páginas em português pedem lang=pt
        base, _, aba = url.partition("#")  # o endereço da aba (brasil.html#quem-assume) fica no fim
        url = base + ("&" if "?" in base else "?") + "lang=pt" + ("#" + aba if aba else "")
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(900)
    # ui-r9: estado, cidade e perfil em abas: abre a aba de onde está o que se quer ver (como quem clica nela)
    if ate and await pg.evaluate("s => !!(window.EP && EP.abas && EP.abas.ativa() && EP.abas.mostra(s.slice(1)))", ate):
        await pg.wait_for_timeout(1200)
    if ate and await pg.locator(ate).count():
        await pg.locator(ate).first.scroll_into_view_if_needed()
        await pg.wait_for_timeout(500)


def fichas(d):
    l = []
    for g in (d.get("presidencia"), d.get("governo")):
        for k in ("presidente", "vice", "governador"):
            if g and g.get(k):
                l.append(g[k])
    for s in (d.get("senado") or {}).get("eleitos") or []:
        l += [s] + list(s.get("suplentes") or [])
    for k in ("camara", "assembleia"):
        l += list((d.get(k) or {}).get("membros") or [])
    return l


def contas_txt(c):
    chegam = c["troca"] + c["novo"]
    if not chegam or not c["reeleicao"]:
        return num(c["total"]) + " eleit"
    return f"{num(c['total'])} eleitos. {num(c['reeleicao'])} " + ("foi reeleito" if c["reeleicao"] == 1 else "foram reeleitos") + \
        f" e {num(chegam)} " + ("chega agora" if chegam == 1 else "chegam agora")


async def filtra(pg, sel_casa, n_combo, texto):
    """Escolhe uma opção num campo com busca da Casa só com o teclado (Tab até ele, digita, Enter)."""
    campo = pg.locator(sel_casa + " .combo input").nth(n_combo)
    # ui-r9: com abas, os filtros de cada Casa do "Quem assume" (também no estado) ficam num bloco que abre
    await pg.evaluate("s => { const d = document.querySelector(s + ' details.casa-recolhe'); if (d) d.open = true; }", sel_casa)
    await pg.wait_for_timeout(300)
    await campo.focus()
    await pg.keyboard.press("Control+a")
    await pg.keyboard.type(texto, delay=35)
    await pg.wait_for_timeout(500)
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(600)
    return await campo.input_value()


async def main():
    br, uf, mun = dados("dados/eleitos/BR.json"), dados(f"dados/eleitos/{UF}.json"), dados("dados/eleitos/municipal.json")
    busca = dados("dados/busca.json")
    todas = {p["id"]: p for p in fichas(uf)}
    e26_dep = max((p for p in uf["camara"]["membros"] if p["link"] == p["id"]), key=lambda p: len(p["bens"]["itens"]))
    e26_supl = next((x for s in uf["senado"]["eleitos"] for x in s.get("suplentes") or [] if x["link"] == x["id"]), None)
    reeleito = next(p for p in br["camara"]["membros"] if p["chegada"] == "reeleicao")
    cid_sup = next(k for k, v in mun["cidades"].items() if any(s["situacao"] == "feita" and s["eleitos"].get("prefeito") for s in v.get("suplementares") or []))
    cid_e26 = next(k for k, v in mun["cidades"].items() if any(str(x["link"]).startswith("ver-") for x in v.get("eleitos2026") or []))
    ver_e26 = next(x for x in mun["cidades"][cid_e26]["eleitos2026"] if str(x["link"]).startswith("ver-"))
    cid_uf = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE",
              27: "AL", 28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO"}
    erros = []
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 900})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: erros.append(str(e)))
        await pg.goto(BASE + "index.html?lang=pt", wait_until="networkidle")

        # ------------------------------------------------------------ 1. Brasil: "Quem assume em 2027"
        # ui-r9 (decisão do Lucas): deixou de ser aba; é o mandato 2027 do "Ver outro mandato" (brasil.html?mandato=2027), com um
        # aviso curto nas abas de hoje; o endereço antigo (brasil.html#quem-assume) leva para lá
        # mandatos-r11 (pedido do Lucas, 3/11): o mandato 2027 tem as mesmas abas da página de hoje (Quem governa, Senado, Câmara...),
        # com a faixa amarela "Você está vendo"; cada parte do antigo "Quem assume" está na aba do mesmo assunto
        await ir(pg, "brasil.html")
        ok("Brasil (hoje): o aviso “Veja quem assume em 2027” leva ao mandato 2027, na mesma aba",
           (await pg.locator("#executivo .aviso-futuro a").get_attribute("href") or "").endswith("mandato=2027#executivo"))
        await ir(pg, "brasil.html#quem-assume")
        sec = pg.locator("#executivo")
        ok("Brasil: o endereço antigo leva ao mandato 2027 (as mesmas abas, com a faixa)", await sec.is_visible() and "mandato=2027" in pg.url
           and await pg.locator("#faixa-mandato").is_visible(), pg.url.split("/")[-1])
        pres = br["presidencia"]["presidente"]
        cards = sec.locator(".exec-topo .pessoa-grande")
        hrefs = await cards.evaluate_all("l => l.map(a => a.getAttribute('href'))")
        txt = await sec.locator(".exec-topo").inner_text()
        ok("Brasil: presidente e vice eleitos, com votos e posse, levam ao perfil de hoje",
           hrefs == [f"pessoa.html?id={pres['link']}", f"pessoa.html?id={br['presidencia']['vice']['link']}"] and num(pres["votos"]) in txt and "5 de janeiro de 2027" in txt,
           f"{hrefs} | {txt[:120]!r}")
        c = br["contas"]
        contas = ""
        for a in ("senado", "camara"):
            await ir(pg, f"brasil.html?mandato=2027#{a}", f"#{a}")
            contas += await pg.locator(f"#{a} .contas-e26").inner_text()
        ok("Brasil: as contagens de cada aba são as dos dados (Senado e Câmara)",
           all(contas_txt(c[k]) in contas for k in ("camara", "senado")) and "não é bom nem ruim" in contas, contas[:240])
        datas = await pg.locator(".nota-mandato .posses > li").count()
        ok("Brasil: linha do tempo com uma data por item (no bloco “Quando cada um toma posse”, em cima das abas)", datas >= 3, str(datas))
        # Câmara a partir de 1º/2/2027 (com abas, a lista começa com um resumo e o plenário, os partidos e os filtros ficam num
        # bloco que abre: abre o bloco antes de usar os filtros)
        await ir(pg, "brasil.html?mandato=2027#camara", "#camara")
        cam = pg.locator("#qa-casa-cam")
        if await cam.locator("details.casa-recolhe").count():
            await cam.locator("details.casa-recolhe").evaluate("d => { d.open = true; }")
            await pg.wait_for_timeout(700)
        n_cad = await cam.locator(".plenario i[data-g]").count()
        cont = await cam.locator(".contagem").inner_text()
        ok("Câmara 2027: 513 cadeiras no plenário e na contagem", n_cad == len(br["camara"]["membros"]) == 513 and "513" in cont, f"{n_cad} | {cont}")
        pp = {}
        for m in br["camara"]["membros"]:
            pp[m["partido"]] = pp.get(m["partido"], 0) + 1
        maior = max(pp.items(), key=lambda x: (x[1], x[0]))
        n0 = await cam.locator('.d-partido', has=pg.locator("b", has_text=maior[0])).first.locator("span:not(.sr)").inner_text()  # site-d-r14: etiquetas
        ok("Câmara 2027: o maior partido na lista tem o número dos dados", n0 == num(maior[1]), f"{n0} x {maior}")
        valor = await filtra(pg, "#qa-casa-cam", 1, maior[0])
        cont = await cam.locator(".contagem").inner_text()
        ok("Câmara 2027: filtro de partido pelo teclado", valor.startswith(maior[0]) and (f"Mostrando {num(maior[1])} de 513" in cont or
                                                                                          f"de {num(maior[1])} encontrados (de 513)" in cont), f"{valor} | {cont}")
        await filtra(pg, "#qa-casa-cam", 1, "todos")
        n_uf = sum(1 for m in br["camara"]["membros"] if m["uf"] == "SP")
        valor = await filtra(pg, "#qa-casa-cam", 0, "são paulo")
        cont = await cam.locator(".contagem").inner_text()
        ok("Câmara 2027: filtro de estado pelo teclado", valor == "São Paulo" and (f"Mostrando {n_uf} de 513" in cont or f"de {n_uf} encontrados (de 513)" in cont),
           f"{valor} | {cont}")
        await filtra(pg, "#qa-casa-cam", 0, "todos")
        # cartões: quem tem cargo leva ao perfil de hoje; quem não tem, ao perfil e26-
        primeiro = br["camara"]["membros"][0]
        h0 = await cam.locator(".pessoa-card").first.get_attribute("href")
        novo = next(m for m in br["camara"]["membros"] if m["link"] == m["id"])
        await pg.fill("#qa-casa-cam .f-nome", novo["nome"])
        await pg.wait_for_timeout(700)
        h1 = await cam.locator(".pessoa-card").first.get_attribute("href")
        chip = await cam.locator(".pessoa-card").first.inner_text()
        ok("Câmara 2027: o cartão leva ao perfil certo e mostra de onde a pessoa vem",
           h0 == f"pessoa.html?id={primeiro['link']}" and h1 == f"pessoa.html?id={novo['id']}" and "Sem cargo eletivo hoje" in chip, f"{h0} | {h1} | {chip!r}")
        await pg.fill("#qa-casa-cam .f-nome", "")
        await pg.wait_for_timeout(600)
        # "Mostrar mais" (com abas, "Ver todos"): o foco vai para o primeiro cartão novo
        antes = await cam.locator(".pessoa-card").count()
        await cam.locator(".ver-mais").focus()
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(600)
        foco = await pg.evaluate("document.activeElement && document.activeElement.closest('#qa-casa-cam .pessoa-card') ? [...document.querySelectorAll('#qa-casa-cam .pessoa-card')].indexOf(document.activeElement) : -1")
        ok(f"Câmara 2027: “Mostrar mais” pelo teclado leva o foco ao {antes + 1}º cartão", foco == antes, str(foco))
        # Senado a partir de 1º/2/2027 (com abas, "Ver todos" antes de contar os cartões)
        await ir(pg, "brasil.html?mandato=2027#senado", "#senado")
        sen = pg.locator("#qa-casa-sen")
        if await sen.locator(".ver-mais").count():
            await sen.locator(".ver-mais").click()
            await pg.wait_for_timeout(600)
        n_sen = await sen.locator(".plenario i[data-g]").count()
        cont = await sen.locator(".contagem").inner_text()
        saem = [m for m in br["senado"]["continuam"] if m.get("eleito2026") and m.get("assume")]
        assume = await sen.locator(".pessoa-card", has_text="Assume a vaga").count()
        ok("Senado 2027: 81 cadeiras (54 eleitos + 27 que continuam) e os suplentes que assumem", n_sen == 81 and "81" in cont and len(br["senado"]["eleitos"]) == 54
           and assume == len(saem), f"{n_sen} | {cont} | assume {assume}/{len(saem)}")
        await rola_tudo(pg)
        await axe(pg, "brasil.html?mandato=2027, aba Senado", "main")

        # ------------------------------------------------------------ 2. Brasil em inglês
        await ir(pg, "brasil.html?lang=en#quem-assume")
        await ir(pg, "brasil.html?lang=en&mandato=2027#camara", "#camara")
        tit = await pg.locator("#faixa-mandato").inner_text()
        contas = await pg.locator("#camara .contas-e26").inner_text()
        cc = c["camara"]
        ok("Brasil em inglês: faixa e contagem", "the next term, 2027–2030" in tit and f"{num_en(cc['total'])} elected. {num_en(cc['reeleicao'])} were re-elected" in contas,
           f"{tit} | {contas[:160]!r}")
        await rola_tudo(pg)
        await texto_en(pg, "brasil.html?lang=en&mandato=2027")
        await axe(pg, "brasil.html?lang=en&mandato=2027, aba Câmara", "main")

        # ------------------------------------------------------------ 3. estado
        await ir(pg, f"estado.html?uf={UF}&mandato=2027", "#governo")
        sec = pg.locator("#estado")
        gv = uf["governo"]["governador"]
        txt = await sec.locator(".exec-topo").inner_text()
        hrefs = await sec.locator(".exec-topo .pessoa-grande").evaluate_all("l => l.map(a => a.getAttribute('href'))")
        ok("estado: governador e vice eleitos, com a posse (6/1/2027)", gv["nome"] in txt and "6 de janeiro de 2027" in txt and
           hrefs[0] == f"pessoa.html?id={gv['link']}", f"{hrefs} | {txt[:100]!r}")
        await ir(pg, f"estado.html?uf={UF}&mandato=2027#senadores", "#senadores")
        sup = await sec.locator(".suplentes-e26 a").evaluate_all("l => l.map(a => a.getAttribute('href'))")
        esperado = [f"pessoa.html?id={x['link']}" for s in uf["senado"]["eleitos"] for x in s.get("suplentes") or []]
        # mandatos-r11: na aba Senadores, os eleitos e quem continua ficam em ordem alfabética, como na página de hoje
        ok("estado: senadores eleitos com os 2 suplentes (links)", sorted(sup) == sorted(esperado) and len(sup) == 2 * len(uf["senado"]["eleitos"]), str(sup))
        await ir(pg, f"estado.html?uf={UF}&mandato=2027#federais", "#federais")
        cont_fed = await sec.locator("#casa-fed .contagem").inner_text()
        txt = await sec.locator("#federais .contas-e26").inner_text()
        await ir(pg, f"estado.html?uf={UF}&mandato=2027#estaduais", "#estaduais")
        cont_est = await sec.locator("#casa-est .contagem").inner_text()
        # ui-r9: com abas, a lista começa com um resumo ("Mostrando os 6 primeiros de 70 deputados")
        # mandatos-r11: o resumo é o de hoje (12); com 12 ou menos, a contagem diz "todos os N"
        ok("estado: deputados federais e Assembleia com o número dos dados", any(f"{x} {len(uf['camara']['membros'])} " in cont_fed for x in ("de", "todos os")) and
           any(f"{x} {len(uf['assembleia']['membros'])} " in cont_est for x in ("de", "todos os")), f"{cont_fed} | {cont_est}")
        pe = {}
        for m in uf["assembleia"]["membros"]:
            pe[m["partido"]] = pe.get(m["partido"], 0) + 1
        part, n_p = max(pe.items(), key=lambda x: (x[1], x[0]))
        valor = await filtra(pg, "#casa-est", 0, part)
        cont = await sec.locator("#casa-est .contagem").inner_text()
        ok("estado: filtro de partido da Assembleia pelo teclado", valor.startswith(part) and f"{n_p} de {len(uf['assembleia']['membros'])}" in cont, f"{valor} | {cont}")
        txt += await sec.locator("#estaduais .contas-e26").inner_text()
        ok("estado: contagens da Câmara e da Assembleia (cada uma na sua aba)", contas_txt(uf["contas"]["camara"]) in txt and contas_txt(uf["contas"]["assembleia"]) in txt, txt[:200])
        await rola_tudo(pg)
        await axe(pg, f"estado.html?uf={UF}")
        await ir(pg, f"estado.html?uf={UF}&lang=en&mandato=2027", "#governo")
        await rola_tudo(pg)
        await texto_en(pg, f"estado.html?uf={UF}&lang=en")
        await axe(pg, f"estado.html?uf={UF}&lang=en")
        await ir(pg, "estado.html?uf=DF&mandato=2027#estaduais", "#estaduais")
        txt = await pg.locator("#estaduais").inner_text()
        ok("DF: Câmara Legislativa e posse em 6 de janeiro (Lei Orgânica)", "Câmara Legislativa" in txt and "deputados distritais" in txt and "6 de janeiro de 2027" in txt)

        # ------------------------------------------------------------ 4. cidade: a próxima eleição e as suplementares
        uf_c = cid_uf[int(cid_sup[:2])]
        await ir(pg, f"cidade.html?ibge={cid_sup}", "#proxima-eleicao")
        sec = pg.locator("#proxima-eleicao")
        txt = await sec.inner_text()
        prox = mun["proxima"]
        s = next(s for s in mun["cidades"][cid_sup]["suplementares"] if s["situacao"] == "feita" and s["eleitos"].get("prefeito"))
        pref = s["eleitos"]["prefeito"][0]
        ok("cidade: próxima eleição (1º/10/2028), 2º turno, posse e mandato", "1º de outubro de 2028" in txt and "29 de outubro de 2028" in txt
           and "1º de janeiro de 2029" in txt and "2029 a 2032" in txt and prox["turno1"] == "2028-10-01", txt[:160].replace("\n", " "))
        link = await sec.locator(f'a[href="{pref["tse"]}"]').count()
        ok("cidade: eleição suplementar com a data e quem foi eleito (link do TSE)", pref["nome"] in txt and link == 1, f"{pref['nome']} | {link}")
        fontes = await sec.locator(".fonte-casa [data-fontes]").first.get_attribute("data-fontes")
        await sec.locator(".fonte-casa [data-fontes]").first.click()
        await pg.wait_for_timeout(400)
        jan = await pg.locator(".janela").inner_text()
        await pg.keyboard.press("Escape")
        ok("cidade: fontes da data (Constituição, Lei 9.504/1997 e o quadro das Emendas)", "art. 29" in jan and "9.504" in jan and "Emendas Constitucionais" in jan, fontes)
        await axe(pg, f"cidade.html?ibge={cid_sup}")
        await ir(pg, f"cidade.html?ibge={cid_sup}&lang=en", "#proxima-eleicao")
        txt = await pg.locator("#proxima-eleicao").inner_text()
        ok("cidade em inglês: data americana", "October 1, 2028" in txt, txt[:120].replace("\n", " "))
        await texto_en(pg, f"cidade.html?ibge={cid_sup}&lang=en")
        await axe(pg, f"cidade.html?ibge={cid_sup}&lang=en")
        await ir(pg, f"cidade.html?ibge={cid_e26}", "#proxima-eleicao")  # ui-r9: a aba monta quando abre (o #pe-e26 vem depois)
        await pg.wait_for_timeout(800)
        hrefs = await pg.locator("#proxima-eleicao .grade-pessoas .pessoa-card").evaluate_all("l => l.map(a => a.getAttribute('href'))")
        ok("cidade: quem tem cargo na cidade e foi eleito em 2026 leva ao perfil de hoje", f"pessoa.html?id={ver_e26['link']}" in hrefs and
           len(hrefs) == len(mun["cidades"][cid_e26]["eleitos2026"]), str(hrefs[:3]))
        # ui-r9: a Câmara Municipal é outra aba da cidade, com um resumo de 12 e "Ver todos"
        await pg.evaluate("EP.abas && EP.abas.mostra('camara-mun')")
        await pg.wait_for_timeout(900)
        if await pg.locator("#casa-ver .ver-mais").count():
            await pg.locator("#casa-ver .ver-mais").click()
            await pg.wait_for_timeout(500)
        chips = await pg.locator(f'#casa-ver a[href="pessoa.html?id={ver_e26["link"]}"] .chip').all_inner_texts()
        ok("cidade: o cartão do vereador na Câmara Municipal tem o selo de eleito em 2026", any("2026" in x for x in chips), str(chips))

        # ------------------------------------------------------------ 5. perfil e26- (português)
        await ir(pg, f"pessoa.html?id={e26_dep['id']}")
        topo = await pg.locator(".perfil-topo").inner_text()
        ok("perfil e26: nome, “Eleita/Eleito <cargo> em 2026 · toma posse em <data>” e o partido",
           e26_dep["nome"] in topo and re.search(r"ELEIT[OA] DEPUTAD[OA] FEDERAL EM 2026 · TOMA POSSE EM 1º DE FEVEREIRO DE 2027", topo.upper()) and e26_dep["partido"] in topo,
           topo[:160].replace("\n", " | "))
        fatos = await pg.locator(".fatos").first.inner_text()  # site-d-r14: o 1º bloco (à vista) tem a eleição
        ok("perfil e26: votos e situação da eleição de 2026", num(e26_dep["votos"]) in fatos and e26_dep["situacao"] in fatos, fatos[:200].replace("\n", " | "))
        n_itens = len(e26_dep["bens"]["itens"])
        vis = await pg.locator("#bens-e26 li:visible").count()
        ok("perfil e26: bens declarados (até 12 à vista, o total no texto)", vis == min(12, n_itens) and
           f"{n_itens} bens" in await pg.locator("#t-bens-e26 + p").inner_text(), f"{vis}/{n_itens}")
        if n_itens > 12:
            await pg.locator("[data-bens-todos]").focus()
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(400)
            vis = await pg.locator("#bens-e26 li:visible").count()
            foco = await pg.evaluate("[...document.querySelectorAll('#bens-e26 li')].indexOf(document.activeElement)")
            ok("perfil e26: “Mostrar os outros” pelo teclado mostra todos e leva o foco ao 13º", vis == n_itens and foco == 12, f"{vis} | foco {foco}")
        tse = await pg.locator(f'.e26-perfil a[href="{e26_dep["tse"]}"]').count()
        ok("perfil e26: link oficial da candidatura no TSE (abre em outra aba)", tse == 1 and await pg.locator(f'.e26-perfil a[href="{e26_dep["tse"]}"]').get_attribute("target") == "_blank")
        volta = await pg.get_attribute("#voltar-lista", "href")
        ok("perfil e26 aberto direto: “Voltar” leva à aba Deputados federais do mandato 2027 do estado", volta in (f"estado.html?uf={UF}&mandato=2027#federais", f"estado.html?uf={UF}&mandato=2027&lang=pt#federais"), volta)
        await axe(pg, "perfil e26 (pt)")
        if e26_supl:
            await ir(pg, f"pessoa.html?id={e26_supl['id']}")
            txt = await pg.locator("#perfil").inner_text()
            ok("perfil e26 de suplente: diz de quem é a chapa e quando assume", e26_supl["chapa"]["nome"] in txt and "suplente" in txt.lower()
               and "assume a vaga se o senador sair" in txt, txt[:160].replace("\n", " | "))

        # ------------------------------------------------------------ 6. perfil e26- (inglês) e 320 px
        await ir(pg, f"pessoa.html?id={e26_dep['id']}&lang=en")
        topo = await pg.locator(".perfil-topo").inner_text()
        ok("perfil e26 em inglês: “Elected federal deputy in 2026 · takes office on February 1, 2027”",
           "ELECTED FEDERAL DEPUTY IN 2026 · TAKES OFFICE ON FEBRUARY 1, 2027" in topo.upper(), topo[:140].replace("\n", " | "))
        await texto_en(pg, "perfil e26 (en)")
        await axe(pg, "perfil e26 (en)")

        # ------------------------------------------------------------ 7. quem já tem cargo: o perfil de hoje, com o selo
        await ir(pg, f"pessoa.html?id={ver_e26['link']}")
        chips = await pg.locator(".perfil-topo .chips").inner_text()
        ok("perfil de quem já tem cargo (vereador): selo de eleito em 2026", "em 2026" in chips and re.search(r"Eleit[oa] ", chips), chips.replace("\n", " | "))
        await pg.goto(BASE + f"pessoa.html?id={reeleito['id']}&lang=pt", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        ok("endereço e26- de quem já tem cargo vai para o perfil de hoje", f"pessoa.html?id={reeleito['link']}" in pg.url, pg.url)
        await ir(pg, "pessoa.html?id=e26-SP-1")
        txt = await pg.locator("#perfil").inner_text()
        busca_l = await pg.locator('#perfil a[href="brasil.html#procurar"]').count()
        ok("endereço e26- que não existe: mensagem simples com o link para a busca", "não está mais aqui" in txt and busca_l == 1, txt[:100])

        # ------------------------------------------------------------ 8. depois da posse: os arquivos somem e a seção também
        await pg.route("**/dados/eleitos/BR.json*", lambda r: r.fulfill(status=404, body="404"))
        await ir(pg, "brasil.html")
        ok("sem dados/eleitos/BR.json (depois das posses): a seção e os avisos somem",
           await pg.locator("#quem-assume").is_hidden() and await pg.locator(".aviso-futuro").count() == 0)
        await ir(pg, "brasil.html?mandato=2027")
        ok("sem dados/eleitos/BR.json: o endereço do mandato 2027 leva para a página de hoje", "mandato" not in pg.url and await pg.locator("#quem-assume").is_hidden(), pg.url.split("/")[-1])
        await pg.unroute("**/dados/eleitos/BR.json*")
        await pg.route(f"**/dados/eleitos/{UF}.json*", lambda r: r.fulfill(status=404, body="404"))
        await ir(pg, f"pessoa.html?id={e26_dep['id']}")
        ok("perfil e26 depois da posse: mensagem com o link para a busca", await pg.locator('#perfil a[href="brasil.html#procurar"]').count() == 1)
        await pg.unroute(f"**/dados/eleitos/{UF}.json*")

        # ------------------------------------------------------------ 9. busca e sitemap
        await ir(pg, "brasil.html", "#procurar")
        await pg.fill("#busca", e26_dep["nome"])
        await pg.wait_for_timeout(900)
        res = await pg.locator("#resultados a").evaluate_all("l => l.map(a => [a.getAttribute('href'), a.innerText])")
        alvo = [r for r in res if r[0] == f"pessoa.html?id={e26_dep['id']}"]
        ok("busca: quem ganhou o perfil e26- aparece, com o cargo de eleito", alvo and "eleit" in alvo[0][1].lower(), str(res[:2]))
        await ir(pg, "brasil.html?lang=en", "#procurar")
        await pg.fill("#busca", e26_dep["nome"])
        await pg.wait_for_timeout(900)
        res = await pg.locator("#resultados a").evaluate_all("l => l.map(a => [a.getAttribute('href'), a.innerText])")
        alvo = [r for r in res if r[0] == f"pessoa.html?id={e26_dep['id']}"]
        ok("busca em inglês: “Federal Deputy-elect”", alvo and "Deputy-elect" in alvo[0][1], str(alvo))
        ids = [x[0] for x in busca]
        ok("busca: nenhum id repetido", len(ids) == len(set(ids)))
        e26_busca = [x for x in busca if x[0].startswith("e26-")]
        pres_vice = [x for x in (br.get("presidencia") or {}).values() if isinstance(x, dict)]
        com_perfil = sum(1 for p in pres_vice + [y for u in sorted((RAIZ / "dados" / "eleitos").glob("[A-Z][A-Z].json")) if u.stem != "BR"
                                                  for y in fichas(dados(f"dados/eleitos/{u.name}"))] if p.get("link") == p.get("id"))
        ok("busca: um e26- por perfil novo, sem ninguém de cargo atual", len(e26_busca) == com_perfil and not any(p["link"] != p["id"] for p in todas.values() if p["id"] in {x[0] for x in e26_busca}),
           f"{len(e26_busca)} x {com_perfil}")
        sm = (RAIZ / "sitemap.xml").read_text(encoding="utf-8")
        ok("sitemap: o perfil e26- em português e em inglês", f"pessoa.html?id={e26_dep['id']}</loc>" in sm and f"pessoa.html?id={e26_dep['id']}&amp;lang=en</loc>" in sm)

        # ------------------------------------------------------------ 10. celular (320 px)
        cel = await nav.new_context(viewport={"width": 320, "height": 740})
        pc = await cel.new_page()
        pc.on("pageerror", lambda e: erros.append(str(e)))
        for url, ate in (("brasil.html#quem-assume", "#camara"), (f"estado.html?uf={UF}&mandato=2027", "#estaduais"), (f"pessoa.html?id={e26_dep['id']}", None),
                         (f"cidade.html?ibge={cid_sup}", "#proxima-eleicao")):
            await ir(pc, url, ate)
            await rola_tudo(pc)
            await sem_rolar_de_lado(pc, url)
        await ir(pc, "brasil.html?mandato=2027#senado", "#senado")
        await rola_tudo(pc)
        await axe(pc, "brasil.html?mandato=2027 (320 px), aba Senado", "main")
        await ir(pc, f"pessoa.html?id={e26_dep['id']}")
        await axe(pc, "perfil e26 (320 px)")
        await cel.close()
        await nav.close()

    # ------------------------------------------------------------ 11. a posse no robô: cada cargo sai do arquivo na sua data
    tmp = RAIZ / ".cache" / "eleitos" / "teste-posse"
    for dia, some in (("2027-01-07", ("presidencia", "governo")), ("2027-02-02", None)):
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for f in (RAIZ / "dados" / "eleitos").glob("*.json"):
            shutil.copy(f, tmp / f.name)
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "eleitos.py"), "--hoje", dia, "--saida", str(tmp)], capture_output=True, text=True,
                           encoding="utf-8", timeout=900)
        if some:
            b = json.loads((tmp / "BR.json").read_text(encoding="utf-8"))
            u = json.loads((tmp / f"{UF}.json").read_text(encoding="utf-8"))
            ok(f"posse simulada ({dia}): presidente, vice e governo saem; Senado e Câmara ficam", r.returncode == 0 and "presidencia" not in b and "governo" not in u
               and "camara" in b and "senado" in u, r.stdout[-200:])
        else:
            restam = sorted(f.stem for f in tmp.glob("*.json"))
            ok(f"posse simulada ({dia}): só fica a próxima eleição municipal", r.returncode == 0 and restam == ["municipal"], f"{restam} | {r.stdout[-200:]}")
    shutil.rmtree(tmp, ignore_errors=True)

    ok("nenhum erro de JavaScript", not erros, "; ".join(erros)[:300])
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
