"""Testes da frente prefeitos-r7: quem governa hoje as cidades cujo prefeito concorreu em 2026 (Constituição, art. 14,
§ 6º) e as eleições suplementares. Confere os dados (dados/manual/prefeitos.json, as fichas das cidades e
dados/eleitos/) e as páginas: Contagem (o cartão de quem governa hoje, com a fonte e "como assumiu"; "A próxima eleição"
e o "Quem assume" de MG levam Marília ao perfil e26-), Itaguaí (a suplementar de 25/10/2026 na ficha), Martinópolis (o
interino até a posse dos eleitos na suplementar), o perfil pref- de uma cidade corrigida e o caso automático do robô
(scripts/tse.py, deixou_prefeitura: a ficha que diz que a pessoa deixou a prefeitura para concorrer e que quem governa
hoje não foi conferido; gerada aqui, sem rede, e servida no lugar da ficha de Contagem). Português e inglês, 320 px,
nenhum erro de JavaScript.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/).
Uso: python testes/interacao_prefeitos.py"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8775/
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
CONTAGEM, ITAGUAI, MARTINOPOLIS = "3118601", "3302007", "3529203"
# os 28 prefeitos eleitos em 2026 que o site mostrava como prefeitos em 29/10/2026 (frente eleitos-r7): IBGE -> nome de urna
ELEITOS_2026 = {
    "1500800": "Dr. Daniel", "2101509": "Gleydson", "2206803": "Zé Fernando", "2309300": "Giordanna Mano", "2602209": "Janjão",
    "2604155": "Juliana de Chaparral", "2703304": "Tenorinho Malta", "2908200": "João de Furão", "3118601": "Marília",
    "3119302": "Fernando Breno", "3120904": "Luiz Paulo", "3122306": "Gleidson Azevedo", "3147006": "Igor Santos",
    "3148004": "Falcão", "3168002": "Denerval", "3203403": "Peter Costa", "3300456": "Márcio Canella",
    "3301009": "Wladimir Garotinho", "3302502": "Renato Cozzolino", "3305752": "Rodrigo Medeiros", "4118006": "Beto Vizzotto",
    "4203808": "Juliana Maciel", "4204301": "Massocco", "4209102": "Adriano Silva", "4302105": "Diogo Siqueira",
    "4317103": "Delegada Ana Tarouco", "5106653": "Adelcino Lopo", "5204854": "Graciele da Arte Trigo"}
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
           "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
           "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(caminho):
    return json.loads((RAIZ / caminho).read_text(encoding="utf-8"))


def ficha(cod):
    return dados(f"dados/cidades/{UF_IBGE[cod[:2]]}/{cod}.json")


def norm(s):
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().split())


JS_TEXTO = re.search(r'JS = r"""(.*?)"""', (RAIZ / "testes" / "verifica_texto.py").read_text(encoding="utf-8"), re.S).group(1)


async def texto(pg, nome):
    achados = await pg.evaluate(JS_TEXTO)
    ok(f"texto sem quebra{' e sem português solto' if 'lang=en' in nome else ''}: {nome}", not achados,
       "; ".join(f"[{k}] {t}" for k, t in achados)[:300])


async def sem_rolar_de_lado(pg, nome):
    larg = await pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    ok(f"320 px sem rolar para os lados: {nome}", larg[0] <= larg[1] + 1, str(larg))


AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"


async def axe(pg, nome):
    """axe-core (WCAG 2.2 A/AA e boas práticas) na página do caso automático, que o testes/acessibilidade.py não alcança
    (a ficha é servida por este teste)."""
    if not AXE.exists():
        print(f"(axe-core não achado em {AXE}: pulei {nome})")
        return
    await pg.evaluate("async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 450) { scrollTo(0, y); "
                      "await new Promise(r => setTimeout(r, 50)); } }")
    await pg.wait_for_timeout(1600)
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                          resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    ok(f"axe sem problemas: {nome}", not v, "; ".join(v)[:300])


async def ir(pg, url):
    if "lang=" not in url:  # a escolha do idioma fica salva no navegador: as páginas em português pedem lang=pt
        url += ("&" if "?" in url else "?") + "lang=pt"
    await pg.goto("about:blank")
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(900)


async def fontes_da_janela(pg, botao):
    await botao.click()
    await pg.wait_for_timeout(400)
    jan = await pg.locator(".janela").inner_text()
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(200)
    return jan


def ficha_automatica():
    """A ficha de Contagem como o robô a faria sem a pesquisa à mão: tse.deixou_prefeitura com a candidatura de 2026 de
    Marília (sem rede: só o que está em .cache/)."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    import tse
    tse._sem_rede()
    b26 = tse.Base2026()
    c = ficha(CONTAGEM)
    p = dict(c["prefeito"]["eleito2024"], id=f"pref-{CONTAGEM}")
    v = dict(c["vice"]["eleito2024"], id=f"vpref-{CONTAGEM}")
    chaves = (None, p["nomeCivil"].upper(), "1961-09-14")
    assert b26.achar(*chaves), "candidatura de 2026 de Marília não achada"
    prazo = tse.seis_meses_antes(b26.turno1)
    novo, vice, av, _ = tse.deixou_prefeitura(p, None, None, v, chaves, b26, prazo)
    return dict(c, prefeito=novo, vice=vice, aviso=av[0], aviso_en=av[1]), prazo


def checa_dados():
    man = dados("dados/manual/prefeitos.json")["cidades"]
    mun = dados("dados/eleitos/municipal.json")["cidades"]
    hoje = __import__("datetime").date.today().isoformat()
    sem_fonte = [k for k, v in man.items() for x in (v.get("prefeito"), v.get("vice")) if isinstance(x, dict) and x and
                 not all(f.get("url") and f.get("data") and f.get("veiculo") for f in (x.get("fonte") or [{}]))]
    ok("prefeitos.json: toda entrada tem prefeito e vice com fonte (veículo, endereço e data)", not sem_fonte, str(sem_fonte[:5]))
    ok("prefeitos.json: toda entrada tem o dia da pesquisa (conferido) e nenhuma passou do \"ate\"",
       all(v.get("conferido") for v in man.values()) and all(not v.get("ate") or v["ate"] >= hoje for v in man.values()))
    ainda = []
    for cod, quem in ELEITOS_2026.items():
        p = ficha(cod).get("prefeito") or {}
        if norm(p.get("nome")) == norm(quem) or not (p.get("fontes") or p.get("vago")):
            ainda.append(f"{cod} {quem}")
    ok("os 28 prefeitos eleitos em 2026 não aparecem mais como prefeitos (e a ficha tem fonte)", not ainda, str(ainda))
    auto = [c for c in (RAIZ / "dados" / "cidades").glob("*/*.json")
            if '"deixou"' in c.read_text(encoding="utf-8")]
    ok("nenhuma cidade com o aviso automático (todas têm pesquisa à mão)", not auto, str([a.stem for a in auto][:5]))
    # suplementares feitas (dados/eleitos/municipal.json): a ficha mostra quem foi eleito ou, até a posse, o interino
    erradas, n = [], 0
    for cod, v in mun.items():
        for s in v.get("suplementares") or []:
            el = (s.get("eleitos") or {}).get("prefeito") or []
            if s.get("situacao") != "feita" or not el:
                continue
            n += 1
            c = ficha(cod)
            p, vi = c.get("prefeito") or {}, c.get("vice") or {}
            ok_tse = norm(p.get("nome")) == norm(el[0]["nome"]) and f"suplementar de {s['data'][8:10]}/{s['data'][5:7]}/{s['data'][:4]}" in (c.get("aviso") or "")
            ok_man = cod in man and norm((p.get("eleito2024") or {}).get("nome")) == norm(el[0]["nome"]) and "tomam posse" in (c.get("aviso") or "")
            if not (ok_tse or ok_man) or not (vi.get("nome") or vi.get("vago")):
                erradas.append(f"{cod} {c['nome']}")
    ok(f"as {n} eleições suplementares feitas para prefeito aparecem nas fichas (eleitos ou o interino até a posse)",
       n >= 40 and not erradas, str(erradas))
    e26 = next(m for m in dados("dados/eleitos/MG.json")["senado"]["eleitos"] if m["nome"].startswith("Marília"))
    ok("Marília (MG): perfil e26- e “Era prefeita” de Contagem no Quem assume", e26["link"] == e26["id"] and e26["id"].startswith("e26-MG-")
       and (e26.get("antes") or {}).get("id") == f"pref-{CONTAGEM}", json.dumps({k: e26.get(k) for k in ("id", "link", "antes")}, ensure_ascii=False))
    mc = [x for x in mun[CONTAGEM]["eleitos2026"] if x["nome"].startswith("Marília")]
    ok("Contagem: Marília em “A próxima eleição” (municipal.json) com o perfil e26- e “deixou”", mc and mc[0]["link"] == e26["id"] and mc[0].get("deixou"))
    return e26


async def main():
    e26 = checa_dados()
    auto, prazo = ficha_automatica()
    c = ficha(CONTAGEM)
    p = c["prefeito"]
    erros = []
    async with async_playwright() as pw:
        nav = await pw.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 900})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: erros.append(str(e)))

        # ------------------------------------------------------------ 1. Contagem: quem governa hoje
        await ir(pg, f"cidade.html?ibge={CONTAGEM}")
        topo = pg.locator(".exec-topo")
        cartao = topo.locator("a.pessoa-grande").first
        txt = await cartao.inner_text()
        ok("Contagem: o cartão do prefeito mostra quem governa hoje, desde quando e como assumiu",
           p["nome"] in txt and "No cargo desde 26/03/2026" in txt and "renunciou" in txt and "Marília" in txt
           and await cartao.get_attribute("href") == f"pessoa.html?id=pref-{CONTAGEM}", txt[:200].replace("\n", " | "))
        vice = await topo.locator(".pessoa-grande").nth(1).inner_text()
        ok("Contagem: o cargo de vice aparece vago, com a explicação", "Cargo vago" in vice and "26/03/2026" in vice, vice[:160].replace("\n", " | "))
        corpo = await pg.locator("main").inner_text()
        ok("Contagem: sem o aviso “Estamos conferindo” e com o aviso da pesquisa à mão",
           "Estamos conferindo" not in corpo and "conferido à mão" in corpo)
        jan = await fontes_da_janela(pg, pg.locator(".exec-topo ~ p .fontes-btn").first)
        ok("Contagem: a fonte de quem governa hoje (site da prefeitura) abre na janela de fontes",
           "Prefeitura de Contagem" in jan and "empossado" in jan, jan[:200].replace("\n", " | "))
        card = pg.locator(f'#proxima-eleicao a.pessoa-card[href="pessoa.html?id={e26["id"]}"]')
        ctxt = await card.inner_text() if await card.count() else ""
        ok("Contagem: “A próxima eleição” leva Marília ao perfil e26- (“Era prefeita”, eleita senadora)",
           await card.count() == 1 and "Era prefeita" in ctxt and "senadora" in ctxt, ctxt[:160].replace("\n", " | "))
        await texto(pg, f"cidade.html?ibge={CONTAGEM}")
        await ir(pg, f"cidade.html?ibge={CONTAGEM}&lang=en")
        txt = await pg.locator(".exec-topo a.pessoa-grande").first.inner_text()
        ok("Contagem em inglês: “Mayor”, a data e “como assumiu” em inglês", "Mayor" in txt and "March 26, 2026" in txt
           and "resigned" in txt, txt[:200].replace("\n", " | "))
        await texto(pg, f"cidade.html?ibge={CONTAGEM}&lang=en")

        # ------------------------------------------------------------ 2. MG: "Quem assume"
        await ir(pg, "estado.html?uf=MG")
        card = pg.locator(f'#quem-assume a.pessoa-card[href="pessoa.html?id={e26["id"]}"]')
        ctxt = await card.first.inner_text() if await card.count() else ""
        ok("MG, “Quem assume”: Marília leva ao perfil e26- e diz “Era prefeita em Contagem (MG)”",
           await card.count() >= 1 and "Era prefeita em Contagem (MG)" in ctxt, ctxt[:160].replace("\n", " | "))
        await ir(pg, f"pessoa.html?id={e26['id']}")
        topo_p = await pg.locator("#perfil").inner_text()
        ok("perfil e26- de Marília: eleita senadora em 2026", "Marília Campos" in topo_p and re.search(r"ELEITA SENADORA EM 2026", topo_p.upper()),
           topo_p[:160].replace("\n", " | "))

        # ------------------------------------------------------------ 3. perfil pref- de uma cidade corrigida
        await ir(pg, f"pessoa.html?id=pref-{CONTAGEM}")
        perfil = await pg.locator("#perfil").inner_text()
        ok("perfil pref-: quem governa hoje, com “No cargo desde” e “Como chegou ao cargo”",
           p["nome"] in perfil and "26 de março de 2026" in perfil and "Como chegou ao cargo" in perfil, perfil[:200].replace("\n", " | "))
        await ir(pg, f"pessoa.html?id=pref-{CONTAGEM}&lang=en")
        perfil = await pg.locator("#perfil").inner_text()
        ok("perfil pref- em inglês", p["nome"] in perfil and "March 26, 2026" in perfil and "MAYOR" in perfil.upper(), perfil[:200].replace("\n", " | "))
        await texto(pg, f"pessoa.html?id=pref-{CONTAGEM}&lang=en")

        # ------------------------------------------------------------ 4. Itaguaí: a suplementar de 25/10/2026
        it = ficha(ITAGUAI)
        await ir(pg, f"cidade.html?ibge={ITAGUAI}")
        txt = await pg.locator(".exec-topo").inner_text()
        corpo = await pg.locator("main").inner_text()
        ok("Itaguaí: prefeito e vice eleitos na suplementar de 25/10/2026, com o aviso",
           "Haroldinho Jesus" in txt and "Fabinho Taciano" in txt and "suplementar de 25/10/2026" in txt
           and "escolhidos na eleição suplementar de 25/10/2026" in corpo and it["prefeito"]["nome"] == "Haroldinho Jesus", txt[:200].replace("\n", " | "))
        await ir(pg, f"cidade.html?ibge={ITAGUAI}&lang=en")
        txt = await pg.locator(".exec-topo").inner_text()
        ok("Itaguaí em inglês: “special election held on October 25, 2026”", "October 25, 2026" in txt, txt[:200].replace("\n", " | "))
        await texto(pg, f"cidade.html?ibge={ITAGUAI}&lang=en")

        # ------------------------------------------------------------ 5. Martinópolis: o interino até a posse dos eleitos
        await ir(pg, f"cidade.html?ibge={MARTINOPOLIS}")
        txt = await pg.locator(".exec-topo").inner_text()
        corpo = await pg.locator("main").inner_text()
        ok("Martinópolis: governa o presidente da Câmara até a posse (26/11/2026) dos eleitos na suplementar",
           "Gabriel Valões" in txt and "Beto Leite" in txt and "tomam posse em 26/11/2026" in corpo and "Fernanda Crepaldi" in txt,
           txt[:200].replace("\n", " | "))

        # ------------------------------------------------------------ 6. o caso automático do robô (ficha gerada aqui)
        async def serve(route):
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(auto, ensure_ascii=False))

        ctx2 = await nav.new_context(viewport={"width": 1280, "height": 900})
        await ctx2.route(f"**/dados/cidades/MG/{CONTAGEM}.json", serve)
        pg2 = await ctx2.new_page()
        pg2.on("pageerror", lambda e: erros.append(str(e)))
        await ir(pg2, f"cidade.html?ibge={CONTAGEM}")
        topo = await pg2.locator(".exec-topo").inner_text()
        corpo = await pg2.locator("main").inner_text()
        site = c["onde"]["prefeitura"]["site"]
        link = await pg2.locator(f'.exec-topo a[href="{site}"]').count()
        ok("automático: o cartão diz que quem governa hoje não foi conferido e por quê, com o link do site oficial",
           "Quem governa hoje: não conferido" in topo and "deixou a prefeitura para concorrer a senadora em 2026 e foi eleita" in topo
           and link == 1, topo[:260].replace("\n", " | "))
        nomes = await pg2.locator(".exec-topo .pessoa-grande b").all_inner_texts()
        ok("automático: Marília não aparece como prefeita (o cartão do prefeito não tem o nome dela nem leva ao perfil pref-)",
           "Marília" not in nomes and await pg2.locator(f'.exec-topo a[href="pessoa.html?id=pref-{CONTAGEM}"]').count() == 0, str(nomes))
        ok("automático: o vice diz que o site não conferiu se ele assumiu a prefeitura",
           "não conferiu se Ricardo Faria assumiu a prefeitura" in topo, topo[-200:].replace("\n", " | "))
        ok("automático: o aviso ⚠️ com a Constituição (art. 14, § 6º) e o prazo, sem o “Estamos conferindo”",
           "art. 14, § 6º" in corpo and f"{prazo[8:10]}/{prazo[5:7]}/{prazo[:4]}" in corpo and "Estamos conferindo" not in corpo)
        jan = await fontes_da_janela(pg2, pg2.locator(".exec-topo ~ p .fontes-btn").first)
        ok("automático: as fontes são a candidatura de 2026 no TSE e a Constituição", "TSE" in jan and "Constituição" in jan, jan[:200].replace("\n", " | "))
        await texto(pg2, f"cidade.html?ibge={CONTAGEM} (automático)")
        await axe(pg2, f"cidade.html?ibge={CONTAGEM} (automático)")
        await pg2.set_viewport_size({"width": 320, "height": 800})
        await pg2.wait_for_timeout(500)
        await sem_rolar_de_lado(pg2, f"cidade.html?ibge={CONTAGEM} (automático)")
        await pg2.set_viewport_size({"width": 1280, "height": 900})
        await ir(pg2, f"cidade.html?ibge={CONTAGEM}&lang=en")
        topo = await pg2.locator(".exec-topo").inner_text()
        ok("automático em inglês", "Current mayor: not checked" in topo and "left office to run for senator in 2026 and was elected" in topo,
           topo[:200].replace("\n", " | "))
        await texto(pg2, f"cidade.html?ibge={CONTAGEM}&lang=en (automático)")
        await axe(pg2, f"cidade.html?ibge={CONTAGEM}&lang=en (automático)")
        await ir(pg2, f"pessoa.html?id=pref-{CONTAGEM}")
        perfil = await pg2.locator("#perfil").inner_text()
        volta = await pg2.locator(f'#perfil a[href^="cidade.html?ibge={CONTAGEM}"]').count()
        ok("automático: o perfil pref- explica e leva à página da cidade (sem “undefined”)",
           "Prefeitura de Contagem (MG)" in perfil and "deixou a prefeitura" in perfil and volta == 1 and "undefined" not in perfil,
           perfil[:200].replace("\n", " | "))
        await axe(pg2, f"pessoa.html?id=pref-{CONTAGEM} (automático)")
        await ir(pg2, f"pessoa.html?id=pref-{CONTAGEM}&lang=en")
        perfil = await pg2.locator("#perfil").inner_text()
        ok("automático: o perfil pref- em inglês", "Mayor of Contagem (MG)" in perfil and "left office" in perfil, perfil[:200].replace("\n", " | "))
        await texto(pg2, f"pessoa.html?id=pref-{CONTAGEM}&lang=en (automático)")
        await ctx2.close()

        # ------------------------------------------------------------ 7. 320 px e um vice vago no perfil
        await pg.set_viewport_size({"width": 320, "height": 800})
        for url in (f"cidade.html?ibge={CONTAGEM}", f"cidade.html?ibge={ITAGUAI}", f"pessoa.html?id=pref-{CONTAGEM}"):
            await ir(pg, url)
            await sem_rolar_de_lado(pg, url)
        await pg.set_viewport_size({"width": 1280, "height": 900})
        await ir(pg, f"pessoa.html?id=vpref-{CONTAGEM}")
        perfil = await pg.locator("#perfil").inner_text()
        ok("perfil vpref- de um vice vago: diz que o cargo está vago e leva à cidade", "Vice-prefeitura de Contagem (MG)" in perfil
           and "vago" in perfil and "undefined" not in perfil, perfil[:200].replace("\n", " | "))
        await texto(pg, f"pessoa.html?id=vpref-{CONTAGEM}")
        await nav.close()
    ok("nenhum erro de JavaScript", not erros, "; ".join(erros)[:300])
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
