"""O passo 6 do visual D (estado e cidade) e o "Como votaram" com o voto de cada pessoa (frente site-d-r16).
estado: os números grandes do topo (iguais em todo mandato, com fonte, levando às abas); o carregamento por aba (ao abrir, só
  o arquivo do estado; as listas do Senado, da Câmara e as votações só quando a aba delas abre; nunca mais JSON do que antes);
  as abas na mesma ordem (com "Como votaram"); o governador em moldura e na gaveta; os senadores em cartões com moldura; os
  deputados federais e a Assembleia com o plenário clicável (etiquetas em ordem alfabética, ≥ 44 px, a gaveta do partido com o
  número certo de pessoas); "Leis e vetos" (o arquivo só é baixado quando o bloco abre; os números iguais aos dados); "Onde ver
  mais" em cartões; "Minha cidade"; o mapa (toque e teclado); BA, SP, RR, DF; 2019 e 2027 com as mesmas peças.
cidade: Salvador, São Paulo, uma cidade pequena com votações (Alta Floresta D'Oeste), uma sem lista oficial (Abaíra), uma com
  eleição suplementar (Itaguaí), o prefeito pesquisado à mão (Contagem) e as leis e vetos de um prefeito (Cacoal); 2021 e 1997.
votos: no Brasil (Câmara e Senado), numa Assembleia com votações (CE; AM, que não publica o placar junto), numa Câmara com
  votações (Alta Floresta D'Oeste) e numa Casa sem (BA, Salvador, Abaíra): as pessoas agrupadas pelo voto (Sim, Não, Abstenção,
  Obstrução, "Não votou ou outro motivo"), em ordem alfabética dentro de cada grupo, os números iguais aos dados, o plenário
  pintado pelo voto com a legenda em texto, a busca e os filtros, a pessoa que abre por cima, "Ver todos" com o foco, ?ver=,
  as cores iguais para todos os partidos, inglês, 320 px e axe com a gaveta aberta.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/) e do axe-core em ../ferramentas.
O tamanho do JSON de antes vem do servidor com o site de antes (EP_ANTES; sem ele, a conta usa os números de 5/11/2026).
Uso: python testes/interacao_d_regional.py [estado|cidade|votos]"""
import asyncio
import json
import os
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
ANTES = os.environ.get("EP_ANTES", "")
LOCAL = urlparse(BASE).hostname
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
SO = sys.argv[1] if len(sys.argv) > 1 else ""
RES = []
# JSON baixado ao abrir, antes desta frente (KB, sem compressão; files/site-d-r16/mede-antes.json, 5/11/2026)
JSON_ANTES = {"estado.html?uf=BA": 298.1, "estado.html?uf=SP": 354.7, "estado.html?uf=CE": 265.5, "cidade.html?ibge=2927408": 199.5, "cidade.html?ibge=1100015": 192.6}
FEDERAIS = {"SP": 70, "MG": 53, "RJ": 46, "BA": 39, "RS": 31, "PR": 30, "PE": 25, "CE": 22, "MA": 18, "GO": 17, "PA": 17, "SC": 16, "PB": 12, "ES": 10,
            "PI": 10, "AL": 9, "AM": 8, "RN": 8, "MT": 8, "MS": 8, "DF": 8, "SE": 8, "RO": 8, "TO": 8, "AC": 8, "AP": 8, "RR": 8}
ORDEM_VOTO = ["Sim", "Não", "Abstenção", "Obstrução", "Outro"]


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(arq):
    return json.loads(urllib.request.urlopen(BASE + "dados/" + arq).read().decode("utf-8"))


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def cat(v):
    if v in ("Sim", "Não", "Abstenção"):
        return v
    return "Obstrução" if v in ("Obstrução", "P-OD", "OB") else "Outro"


async def ctx_novo(nav, lang="pt", **op):
    ctx = await nav.new_context(**op)
    await ctx.add_init_script(f"try{{localStorage.setItem('ep-lang','{lang}')}}catch(e){{}}")
    return ctx


async def vai(pg, url, espera=1500):
    try:
        await pg.goto(BASE + url, wait_until="networkidle", timeout=45000)
    except Exception:
        await pg.wait_for_timeout(2500)
    await pg.wait_for_timeout(espera)


async def axe(pg, nome):
    if not AXE.exists():
        print("  (sem axe-core em ../ferramentas)")
        return
    await pg.evaluate("document.querySelectorAll('.rev,.r3d').forEach(e => e.classList.add('visivel'))")
    await pg.wait_for_timeout(400)  # o aparecer dos cartões (250 ms) termina antes da conta do contraste
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] }, resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    ok(f"axe 0 — {nome}", not v, "; ".join(v)[:400])


async def gaveta_aberta(pg):
    return await pg.evaluate("!!(document.getElementById('gaveta') && document.getElementById('gaveta').open)")


async def fecha_gaveta(pg):
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(500)


async def aba(pg, id_):
    await pg.evaluate("id => { const t = document.querySelector('[role=tab][data-aba=\"' + id + '\"]'); if (t) t.click(); }", id_)
    await pg.wait_for_timeout(1200)


async def abas(pg):
    return await pg.evaluate("() => [...document.querySelectorAll('[role=tab][data-aba]')].filter(t => !t.hidden).map(t => t.getAttribute('data-aba'))")


async def kpis(pg, sel):
    ks = await pg.locator(sel + " .d-kpi").all_inner_texts()
    return [re.sub(r"^\D+", "", re.sub(r"\s+", " ", k)).strip() for k in ks]


async def json_ao_abrir(nav, base, url):
    """Os arquivos de dados/ pedidos ao abrir a página (sem tocar em nada) e o total em KB."""
    c = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    p = await c.new_page()
    tam = {}

    async def resp(r):
        if "/dados/" in r.url and r.url.split("?")[0].endswith(".json"):
            try:
                tam[r.url.split("/dados/")[-1].split("?")[0]] = len(await r.body())
            except Exception:
                pass
    p.on("response", lambda r: asyncio.ensure_future(resp(r)))
    try:
        await p.goto(base + url + ("&" if "?" in url else "?") + "lang=pt", wait_until="networkidle", timeout=45000)
    except Exception:
        pass
    await p.wait_for_timeout(2500)
    await c.close()
    return set(tam), round(sum(tam.values()) / 1024, 1)


async def etiquetas_ok(pg, sec, total_esperado, nome):
    """O plenário clicável de uma Casa: etiquetas dos partidos em ordem alfabética, ≥ 44 px, que somam o total; a gaveta do
    partido com o número certo de pessoas e ?ver=partido:<seção>:<partido>."""
    et = await pg.evaluate("""s => [...document.querySelectorAll('#' + s + ' .d-partido')].map(b => ({ p: b.querySelector('b').textContent.trim(),
      n: +b.querySelector('span:not(.sr)').textContent.replace(/\\D/g, ''), h: b.getBoundingClientRect().height }))""", sec)
    nomes = [x["p"] for x in et]
    ok(f"{nome}: etiquetas dos partidos em ordem alfabética, ≥ 44 px, somando {total_esperado}",
       et and nomes == sorted(nomes, key=norm) and all(x["h"] >= 44 for x in et) and sum(x["n"] for x in et) == total_esperado,
       f"{len(et)} partidos, soma {sum(x['n'] for x in et)}")
    if not et:
        return
    alvo = max(et, key=lambda x: x["n"])
    await pg.locator(f"#{sec} .d-partido", has_text=alvo["p"]).first.click()
    await pg.wait_for_timeout(900)
    n = await pg.locator("#gaveta .gv-lista-partido .pessoa-card").count()
    url = pg.url
    ok(f"{nome}: tocar num partido abre a gaveta com as {alvo['n']} pessoas dele e ?ver=partido:{sec}:…", await gaveta_aberta(pg) and n == alvo["n"] and f"ver=partido%3A{sec}%3A" in url.replace(":", "%3A"), f"{n} · {url[-60:]}")
    await fecha_gaveta(pg)


# ------------------------------------------------------------------ estado
async def estado(nav):
    print("\n— estado: números, carregamento por aba, abas, quem governa, Casas, leis e vetos, onde ver mais, mapa, mandatos —")
    cam = dados("camara.json")
    for uf in ("BA", "SP", "RR", "DF"):
        e = dados(f"estados/{uf}.json")
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda x: erros.append(str(x)))
        await vai(pg, f"estado.html?uf={uf}&lang=pt", 2000)
        ks = await kpis(pg, "#numeros-uf")
        nf, ne = FEDERAIS[uf], (3 * FEDERAIS[uf] if FEDERAIS[uf] <= 12 else 36 + FEDERAIS[uf] - 12)
        fed_dados = sum(1 for m in cam["membros"] if m.get("uf") == uf)
        est_dados = len((e.get("deputadosEstaduais") or {}).get("membros") or [])
        ok(f"{uf}: 5 números grandes (2022, 4 anos, 3 senadores, {nf} deputados federais, {ne} estaduais)",
           len(ks) == 5 and ks[0].startswith("2022") and ks[1].startswith("4") and ks[2].startswith("3") and ks[3].startswith(str(nf)) and ks[4].startswith(str(ne)), " | ".join(ks))
        ok(f"{uf}: os números batem com as listas (deputados federais {fed_dados}, Assembleia {est_dados})", fed_dados == nf and est_dados == ne)
        ok(f"{uf}: os números têm fonte", await pg.locator("#numeros-uf .fontes-btn, #numeros-uf button").count() >= 1)
        esperadas = ["governo", "senadores", "federais", "estaduais", "votacoes"] + ([] if uf == "DF" else ["cidade"])
        ok(f"{uf}: as abas na ordem, com “Como votaram”", await abas(pg) == esperadas, await abas(pg))
        if uf == "BA":
            # o número leva à aba dele
            await pg.locator("#numeros-uf a.d-kpi[href='#federais']").click()
            await pg.wait_for_timeout(1500)
            ok("BA: tocar no número dos deputados federais abre a aba", await pg.evaluate("document.querySelector('[role=tab][data-aba=federais]').getAttribute('aria-selected')") == "true")
            await vai(pg, "estado.html?uf=BA&lang=pt", 1800)
            # governador em moldura e na gaveta
            sombra = await pg.evaluate("getComputedStyle(document.querySelector('#gov .pessoa-grande .av')).boxShadow")
            ok("BA: o governador com a foto em moldura (contorno amarelo e azul)", "242, 183, 5" in sombra and "143, 179, 217" in sombra, sombra[:80])
            # leis e vetos: o arquivo só vem quando o bloco abre
            pedidos = []
            pg.on("request", lambda r: pedidos.append(r.url))
            d = pg.locator("#gov-mais details.d-leis")
            ok("BA: “Leis e vetos” do governador fechado, sem baixar o arquivo", await d.count() == 1 and not any("gov-BA.json" in u for u in pedidos))
            await d.locator("summary").click()
            await pg.wait_for_timeout(1500)
            g = dados("pessoas/gov-BA.json")["executivo"]
            txt = await d.inner_text()
            ok("BA: aberto, baixa o arquivo e mostra as leis sancionadas e os vetos iguais aos dados",
               any("gov-BA.json" in u for u in pedidos) and f"{g['leisSancionadas']}" in txt.replace(".", "") and "veto" in norm(txt), txt[:120].replace("\n", " "))
            await pg.locator("#gov a.pessoa-grande").first.click()
            await pg.wait_for_timeout(1200)
            ok("BA: o cartão do governador abre a gaveta", await gaveta_aberta(pg))
            await fecha_gaveta(pg)
            cards = await pg.evaluate("[...document.querySelectorAll('#gov-mais .d-onde-card')].map(a => ({ h: a.getBoundingClientRect().height, t: a.target, r: a.rel, u: a.href }))")
            ok("BA: “Onde ver mais” em cartões (≥ 44 px, abrem em outra aba, só endereços oficiais)", cards and all(c["h"] >= 44 and c["t"] == "_blank" and "noopener" in c["r"] for c in cards), len(cards))
            # senadores
            await aba(pg, "senadores")
            ok("BA: os 3 senadores em cartões com moldura", await pg.locator("#lista-sen .pessoa-card").count() == 3 and
               "242, 183, 5" in await pg.evaluate("getComputedStyle(document.querySelector('#lista-sen .pessoa-card .av')).boxShadow"))
            # deputados federais e estaduais: plenário clicável
            await aba(pg, "federais")
            await etiquetas_ok(pg, "federais", nf, "BA deputados federais")
            await aba(pg, "estaduais")
            await etiquetas_ok(pg, "estaduais", est_dados, "BA Assembleia")
            # Minha cidade: o campo leva à cidade
            await aba(pg, "cidade")
            await pg.fill("#campo-cid", "Salvad")
            await pg.wait_for_timeout(1200)
            await pg.keyboard.press("ArrowDown")
            await pg.keyboard.press("Enter")
            await pg.wait_for_timeout(2500)
            ok("BA: “Minha cidade” leva à página da cidade escolhida", "cidade.html?ibge=2927408" in pg.url, pg.url)
        if uf == "DF":
            await aba(pg, "votacoes")
            t = await pg.locator("#vot-casa").inner_text()
            ok("DF: “Como votaram” diz que o site não tem o voto de cada deputado distrital, com o site oficial", "não tem o voto de cada deputado distrital" in t and await pg.locator("#vot-casa .links-onde a").count() >= 1, t[:120])
        ok(f"{uf}: nenhum erro de JavaScript", not erros, "; ".join(erros)[:200])
        await ctx.close()

    # carregamento por aba
    for u in ("estado.html?uf=BA", "estado.html?uf=SP", "estado.html?uf=CE"):
        arqs, kb = await json_ao_abrir(nav, BASE, u)
        antes = JSON_ANTES[u]
        if ANTES:  # o servidor com o site de antes (fora do ar: valem os números guardados)
            _, a2 = await json_ao_abrir(nav, ANTES, u)
            antes = a2 or antes
        proibidos = [a for a in arqs if a in ("senado.json", "camara.json") or a.startswith("votacoes/") or a.startswith("pessoas/")]
        ok(f"{u}: ao abrir, nada das outras abas ({', '.join(sorted(arqs))})", not proibidos, proibidos)
        ok(f"{u}: JSON ao abrir {kb} KB ≤ {antes} KB (antes)", kb <= antes + 0.5)

    # o mapa dos estados (toque e teclado)
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await vai(pg, "estado.html?lang=pt", 2000)
    ok("mapa: os 27 estados são links", await pg.locator("#mapa a.uf").count() == 27)
    await pg.locator('#mapa a.uf[data-uf="BA"]').focus()
    await pg.keyboard.press("ArrowRight")
    foco = await pg.evaluate("document.activeElement.getAttribute('data-uf')")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(2500)
    ok("mapa: setas andam pelos estados e Enter abre o escolhido", foco and f"uf={foco}" in pg.url, f"{foco} · {pg.url}")
    await ctx.close()

    # mandatos: o mesmo layout
    for u, ano in (("estado.html?uf=BA&mandato=2019", "2018"), ("estado.html?uf=BA&mandato=2027", "2026"), ("estado.html?uf=SP&mandato=2027", "2026"), ("estado.html?uf=BA&mandato=1995", "1994")):
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda x: erros.append(str(x)))
        await vai(pg, u + "&lang=pt", 2200)
        ks = await kpis(pg, "#numeros-uf")
        ok(f"{u}: as mesmas abas de hoje e os 5 números (eleição de {ano})", await abas(pg) == ["governo", "senadores", "federais", "estaduais", "votacoes", "cidade"] and len(ks) == 5 and ks[0].startswith(ano), " | ".join(ks[:1]))
        await aba(pg, "estaduais")
        ok(f"{u}: a Assembleia com o plenário clicável (etiquetas)", await pg.locator("#estaduais .d-partido").count() >= 2)
        await aba(pg, "votacoes")
        t = await pg.locator("#vot-casa").inner_text()
        ok(f"{u}: “Como votaram” no lugar, dizendo que o site guarda só as de hoje, com o link para hoje",
           ("só do mandato de hoje" in t or "tomam posse em 2027" in t) and await pg.locator("#vot-casa a[href*='#votacoes']").count() == 1, t[:100])
        ok(f"{u}: nenhum erro de JavaScript", not erros, "; ".join(erros)[:200])
        await ctx.close()

    # inglês
    ctx = await ctx_novo(nav, "en", viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await vai(pg, "estado.html?uf=BA&lang=en", 2000)
    ks = await kpis(pg, "#numeros-uf")
    ok("inglês: os números do estado em inglês", "year this term was elected" in ks[0] and "state deputies" in ks[4], ks[0])
    await aba(pg, "votacoes")
    ok("inglês: “How they voted” e o texto sem o voto", "How the Assembly voted" in await pg.locator("#t-votacoes").inner_text() and "does not have each state deputy" in await pg.locator("#vot-casa").inner_text())
    await ctx.close()


# ------------------------------------------------------------------ cidade
async def cidade(nav):
    print("\n— cidade: números, abas, quem governa, Câmara, leis e vetos, onde ver mais, casos especiais, mandatos —")
    for ibge, uf in (("2927408", "BA"), ("3550308", "SP"), ("1100015", "RO"), ("2900108", "BA"), ("3302007", "RJ"), ("3118601", "MG")):
        c = dados(f"cidades/{uf}/{ibge}.json")
        nv = len((c.get("vereadores") or {}).get("membros") or [])
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        erros = []
        pg.on("pageerror", lambda x: erros.append(str(x)))
        await vai(pg, f"cidade.html?ibge={ibge}&lang=pt", 2000)
        ks = await kpis(pg, "#numeros-cid")
        ok(f"{c['nome']}: 3 números grandes (2024, 4 anos, {nv} vereadores)", len(ks) == 3 and ks[0].startswith("2024") and ks[1].startswith("4") and ks[2].startswith(str(nv)), " | ".join(ks))
        ok(f"{c['nome']}: as abas na ordem, com “Como votaram”", await abas(pg) == ["governo-cidade", "camara-mun", "votacoes", "proxima-eleicao", "papeis"], await abas(pg))
        if c.get("prefeito", {}).get("nome"):
            sombra = await pg.evaluate("(document.querySelector('#governo-cidade .pessoa-grande .av') && getComputedStyle(document.querySelector('#governo-cidade .pessoa-grande .av')).boxShadow) || ''")
            ok(f"{c['nome']}: o prefeito com a foto em moldura", "242, 183, 5" in sombra)
        pf = (c.get("onde") or {}).get("prefeitura") or {}
        n_onde = sum(1 for k in ("site", "transparencia", "sic") if (pf.get(k) or "").startswith("http")) + (1 if ((pf.get("diarioOficial") or {}).get("url") or "").startswith("http") else 0)
        n_cards = await pg.locator("#governo-cidade .d-onde-card").count()
        ok(f"{c['nome']}: “Onde ver mais” com os sites oficiais da prefeitura ({n_onde})", n_cards == len({pf.get('site'), pf.get('transparencia'), pf.get('sic'), (pf.get('diarioOficial') or {}).get('url')} - {None, ''}) or n_cards == n_onde, n_cards)
        await aba(pg, "camara-mun")
        await etiquetas_ok(pg, "camara-mun", nv, f"{c['nome']} Câmara")
        await aba(pg, "votacoes")
        tem = ((c.get("vereadores") or {}).get("infoCasa") or {}).get("cobertura", {}).get("votacoes")
        if tem:
            ok(f"{c['nome']}: “Como votaram” com os cartões das votações", await pg.locator("#vot-casa .d-vot").count() >= 1)
        else:
            t = await pg.locator("#vot-casa").inner_text()
            ok(f"{c['nome']}: “Como votaram” diz que o site não tem o voto de cada vereador, com o link oficial",
               "não tem o voto de cada vereador" in t and await pg.locator("#vot-casa .links-onde a[target=_blank]").count() >= 1, t[:120])
        if ibge == "2900108":
            ok("Abaíra (sem lista oficial): o aviso de hoje continua e “Como votaram” diz que ela não está entre as Câmaras com dados abertos",
               "não está entre as Câmaras com dados abertos" in await pg.locator("#vot-casa").inner_text())
        if ibge == "3302007":
            await aba(pg, "proxima-eleicao")
            ok("Itaguaí (eleição suplementar): a aba “A próxima eleição” continua com a suplementar", "suplementar" in norm(await pg.locator("#proxima-eleicao").inner_text()))
        if ibge == "3118601":
            t = await pg.locator("#governo-cidade").inner_text()
            ok("Contagem (prefeito pesquisado à mão): o cartão de quem governa continua com a fonte", await pg.locator("#governo-cidade .pessoa-grande").count() >= 1 and await pg.locator("#governo-cidade .fontes-btn, #governo-cidade button").count() >= 1, t[:80])
        ok(f"{c['nome']}: nenhum erro de JavaScript", not erros, "; ".join(erros)[:200])
        await ctx.close()

    # leis e vetos de um prefeito (o arquivo da cidade só vem quando o bloco abre)
    ex = dados("camaras/extras/1100049.json")["pessoas"]["pref-1100049"]["executivo"]
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    pedidos = []
    pg.on("request", lambda r: pedidos.append(r.url))
    await vai(pg, "cidade.html?ibge=1100049&lang=pt", 2000)
    ok("Cacoal: sem abrir “Leis e vetos”, o arquivo da cidade não é baixado", not any("extras/1100049" in u for u in pedidos))
    await pg.locator("#governo-cidade details.d-leis summary").click()
    await pg.wait_for_timeout(1800)
    t = (await pg.locator("#governo-cidade details.d-leis").inner_text()).replace(".", "")
    ok(f"Cacoal: aberto, “Leis e vetos” mostra {ex['leisSancionadas']} leis sancionadas e {ex['vetos']} vetos, com fonte",
       str(ex["leisSancionadas"]) in t and str(ex["vetos"]) in t and await pg.locator("#governo-cidade details.d-leis .fontes-btn, #governo-cidade details.d-leis button").count() >= 1, t[:120].replace("\n", " "))
    await ctx.close()

    # carregamento por aba
    for u in ("cidade.html?ibge=2927408", "cidade.html?ibge=1100015"):
        arqs, kb = await json_ao_abrir(nav, BASE, u)
        antes = JSON_ANTES[u]
        if ANTES:  # o servidor com o site de antes (fora do ar: valem os números guardados)
            _, a2 = await json_ao_abrir(nav, ANTES, u)
            antes = a2 or antes
        ok(f"{u}: ao abrir, nada das outras abas ({', '.join(sorted(arqs))})", not [a for a in arqs if a.startswith("votacoes/") or a.startswith("camaras/")])
        ok(f"{u}: JSON ao abrir {kb} KB ≤ {antes} KB (antes)", kb <= antes + 0.5)

    # mandatos: o mesmo layout
    for u, ano in (("cidade.html?ibge=2927408&mandato=2021", "2020"), ("cidade.html?ibge=2927408&mandato=1997", "1996"), ("cidade.html?ibge=3550308&mandato=2021", "2020")):
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        await vai(pg, u + "&lang=pt", 2200)
        ks = await kpis(pg, "#numeros-cid")
        ok(f"{u}: as mesmas abas e os números (eleição de {ano})", await abas(pg) == ["governo-cidade", "camara-mun", "votacoes", "proxima-eleicao", "papeis"] and ks and ks[0].startswith(ano), " | ".join(ks))
        await aba(pg, "camara-mun")
        ok(f"{u}: a Câmara com o plenário clicável", await pg.locator("#camara-mun .d-partido").count() >= 2)
        await aba(pg, "votacoes")
        ok(f"{u}: “Como votaram” no lugar, com o link para hoje", "só do mandato de hoje" in await pg.locator("#vot-casa").inner_text() and await pg.locator("#vot-casa a[href*='#votacoes']").count() == 1)
        await ctx.close()


# ------------------------------------------------------------------ votos
async def confere_gaveta(pg, nome, esperado, sem_registro=0):
    """esperado = { voto oficial -> [nomes] }: os grupos, os números, a ordem alfabética e o plenário."""
    grupos = await pg.evaluate("""() => [...document.querySelectorAll('#gaveta .vp-grupo[data-g]')].map(s => ({ g: s.getAttribute('data-g'),
      n: +s.querySelector('.vp-gn').textContent.replace(/\\D/g, ''), nomes: [...s.querySelectorAll('.pessoa-card b')].map(b => b.textContent.trim()),
      cores: [...new Set([...s.querySelectorAll('.voto-chip')].map(c => c.style.getPropertyValue('--cv')))] }))""")
    por_cat = {}
    for v, nomes in esperado.items():
        por_cat.setdefault(cat(v), []).extend(nomes)
    ordem = [g["g"] for g in grupos]
    ok(f"{nome}: os grupos na ordem Sim, Não, Abstenção, Obstrução, “Não votou ou outro motivo”", ordem == [k for k in ORDEM_VOTO if k in por_cat], ordem)
    ok(f"{nome}: o número de cada grupo igual aos dados", all(g["n"] == len(por_cat.get(g["g"], [])) for g in grupos), [(g["g"], g["n"], len(por_cat.get(g["g"], []))) for g in grupos])
    ok(f"{nome}: ordem alfabética dentro de cada grupo e uma só cor por voto (a mesma para todos os partidos)",
       all(g["nomes"] == sorted(g["nomes"], key=norm) and len(g["cores"]) == 1 for g in grupos))
    total = sum(len(x) for x in por_cat.values()) + sem_registro
    cad = await pg.locator("#gaveta .vp-plen .plenario i").count()
    leg = await pg.locator("#gaveta .vp-legenda").inner_text()
    ok(f"{nome}: o plenário com uma cadeira por pessoa ({total}) e a legenda em texto", cad == total and all(n in leg for n in (("Sim", "Não", "Abstenção", "Obstrução", "Não votou")[ORDEM_VOTO.index(k)] for k in por_cat)) and await pg.locator("#gaveta .vp-plen .plenario").get_attribute("aria-hidden") == "true", f"{cad} · {leg[:60]}")


async def votos(nav):
    print("\n— votos: o voto de cada pessoa no Brasil, numa Assembleia, numa Câmara e numa Casa sem votações —")
    # Brasil: uma votação da Câmara e uma do Senado
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda x: erros.append(str(x)))
    await vai(pg, "brasil.html?lang=pt#votacoes", 2500)
    ok("Brasil: os cartões dizem “Ver como cada pessoa votou”", "Ver como cada pessoa votou" in await pg.locator("#votos-recentes .d-vot").first.inner_text())
    for casa in ("camara", "senado"):
        chave = await pg.evaluate("c => [...document.querySelectorAll('[data-vot]')].map(b => b.dataset.vot).find(v => v.startsWith(c))", casa)
        if not chave:
            await pg.click(f"[data-vot-casa='{casa}']")
            await pg.wait_for_timeout(600)
            chave = await pg.evaluate("c => [...document.querySelectorAll('[data-vot]')].map(b => b.dataset.vot).find(v => v.startsWith(c))", casa)
        d = dados(f"votacoes/{casa}/{chave.split(':')[1]}.json")
        esp = {}
        for x in d["votos"]:
            esp.setdefault(x[4], []).append(x[1])
        await pg.locator(f"[data-vot='{chave}']").click()
        await pg.wait_for_timeout(2500)
        sr = max(0, 513 - d["placar"]["total"]) if casa == "camara" else 0
        await confere_gaveta(pg, f"Brasil ({casa})", esp, sr)
        if casa == "camara":
            ok("Brasil (camara): quem não registrou voto aparece só na conta, com a explicação", (sr == 0) or ("Não registraram voto" in await pg.locator("#gaveta .vp-sr").inner_text()))
            # busca pelo nome
            alvo = d["votos"][len(d["votos"]) // 2]
            await pg.fill("#gaveta .vp-nome", alvo[1])
            await pg.wait_for_timeout(700)
            nomes = await pg.locator("#gaveta .vp-grupo .pessoa-card b").all_inner_texts()
            ok("Brasil: a busca pelo nome acha a pessoa", alvo[1] in nomes and "Mostrando" in await pg.locator("#gaveta .vp-conta").inner_text(), nomes[:3])
            await pg.fill("#gaveta .vp-nome", "")
            await pg.wait_for_timeout(500)
            # filtro de partido (o select de verdade, com o combo por cima)
            p0 = sorted({x[2] for x in d["votos"] if x[2]}, key=norm)[0]
            await pg.evaluate("p => { const s = document.querySelector('#gaveta .vp-partido'); s.value = p; s.dispatchEvent(new Event('change')); }", p0)
            await pg.wait_for_timeout(600)
            linhas = await pg.locator("#gaveta .vp-grupo .pessoa-card small").all_inner_texts()
            n_p = sum(1 for x in d["votos"] if x[2] == p0)
            ok(f"Brasil: o filtro de partido ({p0}) mostra só quem é dele", await pg.locator("#gaveta .vp-grupo .pessoa-card").count() == n_p, n_p)
            await pg.evaluate("() => { const s = document.querySelector('#gaveta .vp-partido'); s.value = ''; s.dispatchEvent(new Event('change')); }")
            await pg.wait_for_timeout(500)
            # "Ver todos" de um grupo: o foco vai para a 13ª pessoa
            mais = pg.locator("#gaveta .vp-mais").first
            if await mais.count():
                g = await mais.get_attribute("data-g")
                await mais.click()
                await pg.wait_for_timeout(900)
                foco = await pg.evaluate("g => { const s = document.querySelector('#gaveta .vp-grupo[data-g=\"' + g + '\"]'); return [...s.querySelectorAll('.pessoa-card')].indexOf(document.activeElement); }", g)
                ok("Brasil: “Ver todos” de um grupo mostra todos e o foco vai para a primeira pessoa nova", foco == 12, foco)
            # a pessoa abre por cima, com "‹ Voltar"
            await pg.locator("#gaveta .vp-grupo a.pessoa-card").first.click()
            await pg.wait_for_timeout(1500)
            ok("Brasil: tocar numa pessoa abre a gaveta dela por cima, com “‹ Voltar”", await pg.locator("#gaveta .gv-volta").is_visible())
            await pg.locator("#gaveta .gv-volta").click()
            await pg.wait_for_timeout(1200)
            ok("Brasil: “‹ Voltar” volta para a votação com as pessoas", await pg.locator("#gaveta .vp-grupo").count() >= 1)
            await axe(pg, "Brasil, gaveta da votação com as pessoas (computador)")
            ok("Brasil: ?ver=vot: no endereço", "ver=vot" in pg.url)
        await fecha_gaveta(pg)
    ok("Brasil: nenhum erro de JavaScript", not erros, "; ".join(erros)[:200])
    await ctx.close()

    # Assembleias e Câmara
    for url, arq, nome, gente in (("estado.html?uf=CE", "votacoes/assembleias/CE.json", "CE", "deputado estadual"), ("estado.html?uf=AM", "votacoes/assembleias/AM.json", "AM", "deputado estadual"),
                                  ("cidade.html?ibge=1100015", "votacoes/camaras/1100015.json", "Alta Floresta D'Oeste", "vereador")):
        d = dados(arq)
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        erros, pedidos = [], []
        pg.on("pageerror", lambda x: erros.append(str(x)))
        pg.on("request", lambda r: pedidos.append(r.url))
        await vai(pg, url + "&lang=pt", 2000)
        ok(f"{nome}: o arquivo das votações não é baixado ao abrir a página", not any(arq in u for u in pedidos))
        await aba(pg, "votacoes")
        await pg.wait_for_timeout(1000)
        n = await pg.locator("#vot-casa .d-vot").count()
        ok(f"{nome}: a aba abre com 6 cartões (de {d['recentes']}), da mais nova para a mais antiga", n == min(6, len(d["votacoes"])) and any(arq in u for u in pedidos)
           and "o site tem " + f"{d['total']:,}".replace(",", ".") in await pg.locator("#vot-casa .vl-linha").inner_text())
        if len(d["votacoes"]) > 6:
            await pg.locator("#vot-casa [data-vl-mais]").click()
            await pg.wait_for_timeout(800)
            ok(f"{nome}: “Mostrar mais 6” e o foco no 7º cartão", await pg.locator("#vot-casa .d-vot").count() == 12 and await pg.evaluate("document.activeElement === document.querySelectorAll('#vot-casa .d-vot')[6]"))
        v = d["votacoes"][0]
        esp = {voto: [d["pessoas"][i][1] for i in idx] for voto, idx in v["votos"].items()}
        await pg.locator("#vot-casa [data-vl='0']").click()
        await pg.wait_for_timeout(1500)
        await confere_gaveta(pg, nome, esp)
        t = await pg.locator("#gaveta .gv-corpo").inner_text()
        if v["placar"] is None:
            ok(f"{nome}: sem placar oficial junto, a gaveta diz que os números são a conta de quem está na Casa hoje", "não publica o placar" in t)
        elif v["placar"]["total"] > sum(len(x) for x in v["votos"].values()):
            ok(f"{nome}: o placar oficial maior que a lista é explicado", "O placar oficial tem" in t)
        # site-d-r16 (5/11): os links oficiais ficam em "Do que se trata" (a votação e, quando o site tem, a proposta)
        lks = await pg.locator("#gaveta .vot-links a[target=_blank]").evaluate_all("l => l.map(a => a.href)")
        ok(f"{nome}: o link oficial da votação abre em outra aba", (v["url"] in lks) if (v.get("url") or "").startswith("http") else not lks, lks)
        ok(f"{nome}: ?ver=vl:<id> no endereço", "ver=vl" in pg.url)
        await axe(pg, f"{nome}, gaveta da votação com as pessoas")
        # pelo endereço
        await fecha_gaveta(pg)
        await vai(pg, url + "&lang=pt&ver=vl:" + v["id"] + "#votacoes", 3000)
        ok(f"{nome}: ?ver=vl: abre a gaveta da votação ao carregar a página", await gaveta_aberta(pg) and await pg.locator("#gaveta .vp-grupo").count() >= 1)
        ok(f"{nome}: nenhum erro de JavaScript", not erros, "; ".join(erros)[:200])
        await ctx.close()

    # Casas sem votação nominal
    for url, txt in (("estado.html?uf=BA#votacoes", "não tem o voto de cada deputado estadual"), ("cidade.html?ibge=2927408#votacoes", "não tem o voto de cada vereador")):
        ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        await vai(pg, url.replace("#", "&lang=pt#"), 2200)
        t = await pg.locator("#vot-casa").inner_text()
        ok(f"{url}: a aba fica no lugar e diz que a Casa não publica, sem prometer, com o link oficial",
           txt in t and not re.search(r"ainda não|em breve|por enquanto", t) and await pg.locator("#vot-casa a[target=_blank]").count() >= 1, t[:120])
        await axe(pg, f"{url} (sem votações)")
        await ctx.close()

    # o arquivo de uma Casa que sumiu (404): a aba diz que o site não tem o voto de cada um (sem a mensagem de erro)
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    async def nao_existe(r):
        await r.fulfill(status=404, body="404")
    await pg.route("**/dados/votacoes/assembleias/CE.json*", nao_existe)
    await vai(pg, "estado.html?uf=CE&lang=pt#votacoes", 2500)
    t = await pg.locator("#vot-casa").inner_text()
    ok("CE sem o arquivo das votações (404): a aba diz que o site não tem o voto de cada deputado, sem erro", "não tem o voto de cada deputado estadual" in t and "Não foi possível" not in t, t[:100])
    # RS: a última leitura da ALRS falhou, mas a página e os perfis têm as votações da última que deu certo
    await pg.unroute("**/dados/votacoes/assembleias/CE.json*")
    await vai(pg, "estado.html?uf=RS&lang=pt#votacoes", 2500)
    ok("RS: “Como votaram” com os cartões (o arquivo é feito dos perfis)", await pg.locator("#vot-casa .d-vot").count() == 6)
    await ctx.close()

    # inglês e celular
    for lang in ("en", "pt"):
        ctx = await ctx_novo(nav, lang, viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        for url in ("brasil.html#votacoes", "estado.html?uf=CE#votacoes", "cidade.html?ibge=1100015#votacoes"):
            await vai(pg, url.replace("#", ("&" if "?" in url else "?") + "lang=" + lang + "#"), 2500)
            await pg.locator("#votos-recentes .d-vot, #vot-casa .d-vot").first.click()
            await pg.wait_for_timeout(2500)
            larg = await pg.evaluate("[document.documentElement.scrollWidth, innerWidth, document.querySelector('#gaveta .gv-corpo').scrollWidth, document.querySelector('#gaveta .gv-corpo').clientWidth]")
            ok(f"320 px {lang} {url}: nada passa da tela, nem na gaveta", larg[0] <= larg[1] and larg[2] <= larg[3] + 1, larg)
            if lang == "en":
                t = await pg.locator("#gaveta .gv-corpo").inner_text()
                ok(f"inglês {url}: “How each person voted” e os grupos em inglês", "How each person voted" in t and ("Yes" in t or "No" in t) and "Como cada pessoa" not in t)
            await axe(pg, f"celular {lang} {url} com a gaveta aberta")
            await fecha_gaveta(pg)
        await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        if SO in ("", "estado"):
            await estado(nav)
        if SO in ("", "cidade"):
            await cidade(nav)
        if SO in ("", "votos"):
            await votos(nav)
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
