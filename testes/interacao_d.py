"""O visual do protótipo D na página do Brasil e no perfil (frente site-d-r14, passos 4 e 5).
Brasil: os números grandes do topo (iguais em todo mandato, com fonte, levando às abas); o carregamento por aba (ao abrir, só
os arquivos da aba aberta; nunca mais do que antes); os ministérios numa grade de ícones (todos à vista, em ordem alfabética, a
gaveta de cada um com ?ver=min:); o presidente na gaveta; o plenário clicável (etiquetas dos partidos de ≥ 44 px, em ordem
alfabética, só dois tons, a gaveta com as pessoas do partido e os filtros, a pessoa por cima com "‹ Voltar", a cadeira que abre
o partido, ?ver=partido:, a tabela do "Saber mais" que soma o total); o placar das votações (6 cartões, "Mostrar mais", o filtro
da Casa, a gaveta com o voto de cada partido e "Ver a votação inteira", ?ver=vot:); as 11 cadeiras do STF (a ordem oficial, a
gaveta do ministro e a da cadeira vazia com o placar, as Turmas, ?ver=stf:); os mandatos 2019 e 2027 com as mesmas peças.
Perfil: moldura, números grandes (iguais aos dados e levando às abas), "Quem é" em blocos e "Mais sobre", a barra colorida da
situação (cada cor filtra), os assuntos em barras, a barra dupla dos vetos, as colunas dos votos (com a legenda em texto), os
gastos, a faixa do tempo da História (um mandato por linha, o aberto marcado, o link leva àquele mandato) e todos os tipos de
perfil. Também: tablet com o menu lateral, 320 px, inglês, "menos movimento", rede e axe com as gavetas abertas.
4/11 (pedido do Lucas): os botões ‹ › da barra das abas em 320/390/620/768 px (só quando a barra rola, só do lado em que há
aba escondida, fora da parte que rola, ≥ 44 px, rótulos pt/en, o › traz a aba seguinte inteira, o foco que não se perde, a aba
aberta à vista também pelo endereço e pelo teclado, a janela que muda de largura e a letra maior) e o desenho do cabeçalho
menor na tela estreita.
Playwright + Edge; precisa do servidor (EP_BASE, padrão http://127.0.0.1:8770/) e do axe-core em ../ferramentas.
Uso: python testes/interacao_d.py [brasil|perfil|outros|abas|passos|suave]"""
import asyncio
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
LOCAL = urlparse(BASE).hostname
AXE = Path(__file__).resolve().parents[2] / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
SO = sys.argv[1] if len(sys.argv) > 1 else ""
RES = []
# o JSON baixado ao abrir cada aba antes desta frente (KB, sem compressão; files/site-d-r14/mede-antes.json): não pode crescer
# publica-r15: com os dados de 4/11 os mesmos arquivos cresceram (manual/ministros.json +1,2 KB; votacoes/senado.json +2,3 KB):
# a conta continua sendo "os mesmos arquivos de antes", com o tamanho que eles têm hoje
ANTES_JSON = {"": 222.7 + 1.2, "#senado": 190.4, "#camara": 308.2, "#votacoes": 704.0 + 2.3, "#judiciario": 230.2}
# os arquivos que cada aba pode pedir ao abrir (os outros só quando a aba deles abre)
POR_ABA = {"": {"executivo.json", "manual/ministros.json"}, "#senado": {"senado.json"}, "#camara": {"camara.json"},
           "#votacoes": {"votacoes/camara.json", "votacoes/senado.json"}, "#judiciario": {"stf.json"}}
SEMPRE = {"eleitos/BR.json", "historico/indice.json"}


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def dados(arq):
    return json.loads(urllib.request.urlopen(BASE + "dados/" + arq).read().decode("utf-8"))


def q(url, k):
    return (parse_qs(urlparse(url).query).get(k) or [None])[0]


def norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


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
    await pg.evaluate("id => { const t = document.querySelector('[role=tab][data-aba=\"' + id_ + '\"]'); if (t) t.click(); }".replace("id_", "id"), id_)
    await pg.wait_for_timeout(1200)


# ------------------------------------------------------------------ 1. Brasil
async def brasil(nav):
    print("\n— 1. Brasil: números, carregamento por aba, ministérios, plenário, votações, STF —")
    sen, cam, mins, stf = dados("senado.json"), dados("camara.json"), dados("manual/ministros.json"), dados("stf.json")
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    erros, fora = [], []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.on("request", lambda r: fora.append(r.url) if urlparse(r.url).hostname not in (LOCAL, None) and r.resource_type != "image" else None)

    # 1a. carregamento por aba: só os arquivos da aba aberta (e nunca mais JSON do que antes)
    for h, antes in ANTES_JSON.items():
        c2 = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
        p2 = await c2.new_page()
        tam = {}

        async def resp(r, tam=tam):
            if "/dados/" in r.url and r.url.split("?")[0].endswith(".json"):
                try:
                    tam[r.url.split("/dados/")[-1].split("?")[0]] = len(await r.body())
                except Exception:
                    pass
        p2.on("response", lambda r: asyncio.ensure_future(resp(r)))
        await vai(p2, "brasil.html?lang=pt" + h, 2500)
        arqs = set(tam)
        kb = round(sum(tam.values()) / 1024, 1)
        ok(f"carregamento por aba ({h or '#executivo'}): só os arquivos da aba ({', '.join(sorted(arqs))})", arqs <= POR_ABA[h] | SEMPRE and POR_ABA[h] <= arqs)
        ok(f"carregamento por aba ({h or '#executivo'}): JSON ao abrir {kb} KB ≤ {antes} KB (antes)", kb <= antes + 0.5)
        await c2.close()

    # 1b. números grandes do topo
    await vai(pg, "brasil.html?lang=pt")
    ks = await pg.locator("#numeros .d-kpi").all_inner_texts()
    nums = [re.sub(r"^\D+", "", re.sub(r"\s+", " ", k)).strip() for k in ks]
    ok("números do topo: 5, com o ano da eleição (2022), 4 anos, 81 senadores, 513 deputados e 11 cadeiras no STF",
       len(nums) == 5 and nums[0].startswith("2022") and nums[1].startswith("4") and nums[2].startswith("81") and nums[3].startswith("513") and nums[4].startswith("11"), " | ".join(nums))
    ok("números do topo: o ícone é enfeite (aria-hidden) e o número fica escrito", await pg.locator("#numeros .d-kpi .d-ic[aria-hidden=true]").count() == 5)
    await pg.locator('#numeros a.d-kpi[href="#senado"]').click()
    await pg.wait_for_timeout(1200)
    ok("números do topo: “81 senadores” abre a aba Senado", await pg.locator('[role=tab][data-aba="senado"]').get_attribute("aria-selected") == "true")
    await pg.locator("#numeros .fontes-btn").click()
    await pg.wait_for_timeout(500)
    links = await pg.locator(".janela a").evaluate_all("l => l.map(a => a.href)")
    ok("números do topo: “De onde vêm estes números?” com a Constituição, a LC 78/1993 e o TSE",
       any("constituicao.htm" in u for u in links) and any("lcp78" in u for u in links) and any("tse.jus.br" in u for u in links), f"{len(links)} links")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    for m, ano in (("2019", "2018"), ("2027", "2026"), ("1995", "1994")):
        await vai(pg, f"brasil.html?mandato={m}&lang=pt")
        t = [re.sub(r"^\D+", "", re.sub(r"\s+", " ", k)).strip() for k in await pg.locator("#numeros .d-kpi").all_inner_texts()]
        ok(f"números do topo no mandato {m}: os mesmos 5, com a eleição de {ano}", len(t) == 5 and t[0].startswith(ano) and t[2].startswith("81"), " | ".join(t))

    # 1c. Quem governa: ministérios em ícones e o presidente na gaveta
    await vai(pg, "brasil.html?lang=pt")
    n_min = len(mins["ministerios"])
    tiles = pg.locator("#ministros .min-card.d-min")
    ok(f"ministérios: todos os {n_min} ícones à vista, sem “Ver todos”", await tiles.count() == n_min and await pg.locator(".ver-todos-min").count() == 0)
    areas = [a.strip() for a in await pg.locator("#ministros .d-min-area").all_inner_texts()]
    ordem = await pg.evaluate("l => l.slice().sort((a, b) => a.localeCompare(b, 'pt', {sensitivity: 'base'}))", areas)
    ok("ministérios: em ordem alfabética do nome da área", areas == ordem, " / ".join(areas[:5]))
    ok("ministérios: o nome inteiro está no ícone para o leitor de tela", await pg.locator("#ministros .min-card b.sr").count() == n_min)
    alvo = tiles.nth(3)
    nome_b = (await alvo.locator("b").inner_text()).strip()
    await alvo.click()
    await pg.wait_for_timeout(700)
    gt = await pg.locator("#gaveta").inner_text() if await gaveta_aberta(pg) else ""
    m3 = next((m for m in mins["ministerios"] if (m.get("ministerio") or "") == nome_b), None)
    ok("ministério: a gaveta abre com o nome, quem comanda, o partido e a fonte", await gaveta_aberta(pg) and nome_b in gt and (m3 is None or (m3.get("nome") or "") in gt)
       and await pg.locator("#gaveta .fontes-btn").count() >= 1, nome_b)
    ok("ministério: o endereço guarda a gaveta (?ver=min:…)", (q(pg.url, "ver") or "").startswith("min:"), pg.url.split("/")[-1])
    ver_min = q(pg.url, "ver")
    await fecha_gaveta(pg)
    ok("ministério: Esc fecha e o foco volta para o ícone", not await gaveta_aberta(pg) and await pg.evaluate("document.activeElement && document.activeElement.classList.contains('min-card')"))
    await vai(pg, f"brasil.html?ver={ver_min}&lang=pt", 2500)
    ok("ministério: abrir o endereço com ?ver=min:… abre a gaveta", await gaveta_aberta(pg) and nome_b in await pg.locator("#gaveta").inner_text())
    await fecha_gaveta(pg)
    await pg.locator("#exec-topo a.pessoa-grande").first.click()
    await pg.wait_for_timeout(1500)
    ok("presidente (cartão grande): abre a gaveta com os números e “Ver a página inteira”", await gaveta_aberta(pg) and await pg.locator("#gaveta .gv-kpi").count() >= 2
       and await pg.locator("#gaveta a.gv-pagina").count() == 1 and q(pg.url, "ver") == "p:pres-lula")
    await axe(pg, "Brasil com a gaveta do presidente aberta")
    await fecha_gaveta(pg)
    await pg.locator("#ministros .min-card").first.click()
    await pg.wait_for_timeout(600)
    await axe(pg, "Brasil com a gaveta de um ministério aberta")
    await fecha_gaveta(pg)

    # 1d. Senado e Câmara: o plenário clicável
    for casa, d, total in (("senado", sen, 81), ("camara", cam, 513)):
        await vai(pg, f"brasil.html?lang=pt#{casa}", 2500)
        cont = {}
        for m in d["membros"]:
            p = m.get("partido") or "Sem partido"
            cont[p] = cont.get(p, 0) + 1
        et = pg.locator(f"#{casa} .d-partido")
        n_et = await et.count()
        ok(f"{casa}: uma etiqueta por partido ({len(cont)})", n_et == len(cont), str(n_et))
        nomes = [t.strip() for t in await et.locator("b").all_inner_texts()]
        ordem = await pg.evaluate("l => l.slice().sort((a, b) => a.localeCompare(b, 'pt', {sensitivity: 'base'}))", nomes)
        ok(f"{casa}: etiquetas em ordem alfabética", nomes == ordem, " ".join(nomes[:6]))
        alturas = await et.evaluate_all("l => l.map(b => b.getBoundingClientRect().height)")
        ok(f"{casa}: etiquetas com pelo menos 44 px de altura (o caminho principal)", min(alturas) >= 44, f"menor {min(alturas):.0f}px")
        await pg.mouse.move(2, 2)
        await pg.wait_for_timeout(300)
        cores = await et.evaluate_all("l => [...new Set(l.map(b => getComputedStyle(b).backgroundColor))]")
        ok(f"{casa}: só dois tons para todos os partidos (nenhum partido com cor própria)", len(cores) == 2, str(cores))
        await pg.wait_for_timeout(1500)  # as cadeiras terminam de mudar de cor (a transição de quando o mouse passou)
        tons = await pg.locator(f"#{casa} .plenario i[data-g]").evaluate_all("l => [...new Set(l.map(i => getComputedStyle(i).backgroundColor))]")
        ok(f"{casa}: o plenário também só com dois tons", len(tons) <= 2, str(tons))
        ok(f"{casa}: o plenário é desenho (aria-hidden)", await pg.locator(f"#{casa} .plenario[aria-hidden=true]").count() == 1)
        linhas = await pg.locator(f"#{casa} .d-saiba-casa table tbody tr td").evaluate_all("l => l.map(td => td.textContent)")
        soma = sum(int(re.sub(r"\D", "", l) or 0) for l in linhas)
        ok(f"{casa}: a tabela do “Saber mais” tem todos os partidos e soma {total}", len(linhas) == len(cont) and soma == len(d["membros"]), f"{len(linhas)} linhas, soma {soma}")
        # a gaveta do partido
        maior = max(cont, key=lambda k: (cont[k], k))
        b = pg.locator(f"#{casa} .d-partido", has=pg.locator("b", has_text=re.compile("^" + re.escape(maior) + "$")))
        await b.first.click()
        await pg.wait_for_timeout(900)
        gt = await pg.locator("#gaveta").inner_text() if await gaveta_aberta(pg) else ""
        n_cards = await pg.locator("#gaveta .pessoa-card").count()
        ok(f"{casa}: a etiqueta {maior} abre a gaveta com {cont[maior]} pessoas (“{cont[maior]} de {total}”)", await gaveta_aberta(pg) and n_cards == cont[maior]
           and re.search(rf"\b{cont[maior]}\s*de {total}\b", gt.replace(".", "")), f"{n_cards} cartões")
        ok(f"{casa}: o endereço guarda a gaveta (?ver=partido:{casa}:{maior})", q(pg.url, "ver") == f"partido:{casa}:{maior}", q(pg.url, "ver"))
        primeiro = (await pg.locator("#gaveta .pessoa-card b").first.inner_text()).strip()
        await pg.locator("#gaveta .f-nome").fill(primeiro[:5])
        await pg.wait_for_timeout(500)
        ok(f"{casa}: o filtro de nome dentro da gaveta", 1 <= await pg.locator("#gaveta .pessoa-card").count() < max(2, cont[maior]) or cont[maior] == 1)
        await pg.locator("#gaveta .f-nome").fill("")
        await pg.wait_for_timeout(400)
        if casa == "senado":
            await pg.locator("#gaveta .pessoa-card").first.click()
            await pg.wait_for_timeout(1500)
            ok("senado: a pessoa abre por cima, com “‹ Voltar” (e o endereço com ?ver=p:)", await pg.locator("#gaveta .gv-volta").is_visible() and (q(pg.url, "ver") or "").startswith("p:"))
            await pg.locator("#gaveta .gv-volta").click()
            await pg.wait_for_timeout(700)
            ok("senado: “‹ Voltar” volta para o partido", await pg.locator("#gaveta .pessoa-card").count() == cont[maior] and q(pg.url, "ver") == f"partido:senado:{maior}")
            await axe(pg, "Brasil com a gaveta de um partido aberta")
        await fecha_gaveta(pg)
        foco = await pg.evaluate("document.activeElement && document.activeElement.classList.contains('d-partido') && document.activeElement.querySelector('b').textContent")
        ok(f"{casa}: Esc fecha e o foco volta para a etiqueta do partido", not await gaveta_aberta(pg) and foco == maior, str(foco))
        # tocar numa cadeira do plenário abre o partido dela
        await pg.locator(f"#{casa} .plenario i[data-g]").nth(0).click(force=True)
        await pg.wait_for_timeout(900)
        g0 = nomes[0]
        ok(f"{casa}: tocar numa cadeira abre a gaveta do partido dela ({g0})", await gaveta_aberta(pg) and q(pg.url, "ver") == f"partido:{casa}:{g0}")
        await fecha_gaveta(pg)
        # a lista de sempre continua embaixo (filtros, resumo de 12, "Ver todos")
        ok(f"{casa}: a lista com os filtros continua na página (resumo de 12 e “Ver todos”)", await pg.locator(f"#{casa} .grade-pessoas .pessoa-card").count() == 12
           and await pg.locator(f"#{casa} .f-partido").count() == 1 and await pg.locator(f"#{casa} .ver-mais").count() == 1)
    await vai(pg, "brasil.html?ver=partido:camara:PL&lang=pt", 3500)
    ok("abrir brasil.html?ver=partido:camara:PL abre a aba Câmara e a gaveta do PL", await gaveta_aberta(pg) and "PL" in await pg.locator("#gaveta-tit").inner_text()
       and await pg.locator('[role=tab][data-aba="camara"]').get_attribute("aria-selected") == "true")
    await fecha_gaveta(pg)

    # 1e. Como votaram: o placar
    await vai(pg, "brasil.html?lang=pt#votacoes", 3500)
    cards = pg.locator("#votos-recentes .d-vot")
    ok("votações: 6 cartões de placar, todos do texto principal", await cards.count() == 6 and all("Texto principal" in t for t in await cards.all_inner_texts()))
    ok("votações: cada cartão com os números do placar escritos (Sim × Não)", all(re.search(r"\d+\s*Sim.*\d+\s*Não", t.replace("\n", " ")) for t in await cards.all_inner_texts()))
    await pg.locator("[data-vot-mais]").click()
    await pg.wait_for_timeout(600)
    ok("votações: “Mostrar mais” põe mais 6 e o foco no 7º", await cards.count() == 12 and await pg.evaluate("document.activeElement === document.querySelectorAll('#votos-recentes .d-vot')[6]"))
    await pg.locator('[data-vot-casa="senado"]').click()
    await pg.wait_for_timeout(500)
    casas = await cards.evaluate_all("l => l.map(b => b.getAttribute('data-vot').split(':')[0])")
    ok("votações: o filtro “Senado” mostra só o Senado", casas and set(casas) == {"senado"} and await pg.locator('[data-vot-casa="senado"]').get_attribute("aria-pressed") == "true")
    await pg.locator('[data-vot-casa=""]').click()
    await pg.wait_for_timeout(400)
    await cards.first.click()
    await pg.wait_for_timeout(1500)
    linhas = await pg.locator("#gaveta .gv-tab-partidos tbody tr").count()
    vk = q(pg.url, "ver") or ""
    ok("votação: a gaveta abre com o placar e o voto de cada partido (tabela)", await gaveta_aberta(pg) and linhas >= 3 and await pg.locator("#gaveta .d-placar").count() == 1, f"{linhas} partidos")
    href = await pg.locator("#gaveta a.gv-pagina").get_attribute("href")
    ok("votação: “Ver a votação inteira” leva a votacao.html", bool(href) and href.startswith("votacao.html?casa=") and vk.startswith("vot:"), f"{href} | {vk}")
    m = re.match(r"vot:(camara|senado):(.+)$", vk)
    if m:
        v = dados(f"votacoes/{m.group(1)}/{m.group(2)}.json")
        tot_tab = await pg.locator("#gaveta .gv-tab-partidos tbody td").evaluate_all("l => l.reduce((s, td) => s + (parseInt(td.textContent.replace(/\\D/g, '')) || 0), 0)")
        ok("votação: a tabela dos partidos soma todos os votos da lista oficial", tot_tab == len(v["votos"]), f"{tot_tab} x {len(v['votos'])}")
    await axe(pg, "Brasil com a gaveta de uma votação aberta")
    await fecha_gaveta(pg)
    await vai(pg, f"brasil.html?ver={vk}&lang=pt", 3500)
    ok("votação: abrir o endereço com ?ver=vot:… abre a gaveta", await gaveta_aberta(pg))
    await fecha_gaveta(pg)

    # 1f. STF: as 11 cadeiras
    await vai(pg, "brasil.html?lang=pt#judiciario", 2500)
    ids = [h.split("id=")[-1] for h in await pg.locator("#stf .d-cadeiras a.stf-card").evaluate_all("l => l.map(a => a.getAttribute('href'))")]
    vagas = len(stf.get("vagas") or [])
    ok("STF: uma cadeira por ministro, na ordem oficial, e a cadeira vazia (11 no total)", ids == [m["id"] for m in stf["ministros"]] and
       await pg.locator("#stf .d-cadeira.vaga").count() == vagas and len(ids) + vagas == 11, f"{len(ids)} + {vagas}")
    dino = next(m for m in stf["ministros"] if m["id"] == "stf-flavio-dino")
    await pg.locator('#stf a.stf-card[href="pessoa.html?id=stf-flavio-dino"]').click()
    await pg.wait_for_timeout(800)
    gt = await pg.locator("#gaveta").inner_text() if await gaveta_aberta(pg) else ""
    br = lambda iso: "/".join(reversed(iso.split("-")))
    ok("STF: a cadeira abre a gaveta (posse, quem indicou, aposentadoria, Turma) e o endereço ?ver=stf:",
       br(dino["posse"]["data"]) in gt and dino["indicacao"]["presidente"] in gt and br(dino["aposentadoria"]["data"]) in gt and "1ª Turma" in gt
       and q(pg.url, "ver") == "stf:stf-flavio-dino", gt.replace("\n", " | ")[:160])
    ok("STF: “Ver a página inteira” leva ao perfil", (await pg.locator("#gaveta a.gv-pagina").get_attribute("href") or "").endswith("pessoa.html?id=stf-flavio-dino"))
    await fecha_gaveta(pg)
    if vagas:
        await pg.locator("#stf .d-cadeira.vaga").click()
        await pg.wait_for_timeout(700)
        gt = await pg.locator("#gaveta").inner_text()
        pl = stf["vagas"][0]["indicacoes"][0]["plenario"]
        ok("STF: a cadeira vazia abre a gaveta com de quem era e o placar do Senado", stf["vagas"][0]["de"] in gt and str(pl["sim"]) in gt and str(pl["nao"]) in gt)
        await axe(pg, "Brasil com a gaveta da cadeira vazia do STF")
        await fecha_gaveta(pg)
    for t in stf["turmas"]:
        n = await pg.locator(f"#t-turma-{t['numero']}").locator("xpath=..").locator("li a").count()
        ok(f"STF: a {t['numero']}ª Turma em rostos, com {len(t['membros'])} ministros", n == len(t["membros"]))
    ok("STF: como chegar, quem preside e o trabalho no “Saber mais”", await pg.locator("#stf details.stf-como-det .stf-passos li").count() == 5 and
       await pg.locator("#stf details.stf-preside-det .stf-presidencia").count() == 1 and await pg.locator("#stf details.stf-trabalho-det .links-onde a").count() >= 1)
    await vai(pg, "brasil.html?ver=stf:stf-flavio-dino&lang=pt", 2500)
    ok("STF: abrir o endereço com ?ver=stf:… abre a aba e a gaveta", await gaveta_aberta(pg) and await pg.locator('[role=tab][data-aba="judiciario"]').get_attribute("aria-selected") == "true")
    await fecha_gaveta(pg)

    # 1g. mandatos 2019 e 2027: as mesmas peças
    await vai(pg, "brasil.html?mandato=2019&lang=pt", 2500)
    n = await pg.locator("#min-hist .min-card.d-min").count()
    ok("2019: os ministérios do governo em ícones, todos à vista", n > 20 and await pg.locator("[data-min-todos]").count() == 0, str(n))
    await pg.locator("#min-hist .min-card", has_text="Ministério da Economia").first.click()
    await pg.wait_for_timeout(700)
    gt = await pg.locator("#gaveta").inner_text() if await gaveta_aberta(pg) else ""
    ok("2019: o ministério abre a gaveta com quem chefiou e as datas (?ver=minh:…)", "Paulo Roberto Nunes Guedes" in gt and "01/01/2019" in gt and (q(pg.url, "ver") or "").startswith("minh:"))
    await fecha_gaveta(pg)
    await aba(pg, "senado")
    ok("2019: o Senado com as etiquetas dos partidos", await pg.locator("#senado .d-partido").count() >= 10)
    await pg.locator("#senado .d-partido").first.click()
    await pg.wait_for_timeout(700)
    ok("2019: a etiqueta abre a gaveta com os eleitos do partido (cartões sem link)", await gaveta_aberta(pg) and await pg.locator("#gaveta .pessoa-card.passado").count() >= 1
       and await pg.locator("#gaveta a.pessoa-card").count() == 0)
    await fecha_gaveta(pg)
    await vai(pg, "brasil.html?mandato=2027&lang=pt#senado", 3000)
    ok("2027: o Senado com as etiquetas dos partidos", await pg.locator("#senado .d-partido").count() >= 10)
    await pg.locator("#senado .d-partido").nth(1).click()
    await pg.wait_for_timeout(700)
    ok("2027: a etiqueta abre a gaveta com as pessoas", await gaveta_aberta(pg) and await pg.locator("#gaveta .pessoa-card").count() >= 1)
    await axe(pg, "Brasil 2027 com a gaveta de um partido aberta")
    await fecha_gaveta(pg)
    ok("Brasil: nenhum erro de JavaScript", not erros, "; ".join(erros)[:300])
    ok("Brasil: nenhum pedido a outro servidor (fora fotos)", not fora, "; ".join(fora)[:200])
    await ctx.close()


# ------------------------------------------------------------------ 2. Perfil
async def perfil(nav):
    print("\n— 2. Perfil: moldura, números, Quem é, propostas, leis, votos, gastos, faixa do tempo —")
    lula, dep = dados("pessoas/pres-lula.json"), dados("pessoas/dep-178866.json")
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))

    await vai(pg, "pessoa.html?id=pres-lula&lang=pt", 2500)
    ok("Lula: a foto na moldura", await pg.locator(".perfil-topo .moldura .av").count() == 1 and
       "rgb(242, 183, 5)" in await pg.locator(".perfil-topo .moldura .av").evaluate("e => getComputedStyle(e).boxShadow"))
    ks = [re.sub(r"^\D+", "", re.sub(r"\s+", " ", k)).strip() for k in await pg.locator(".d-numeros-perfil .d-kpi").all_inner_texts()]
    n_prop = len(lula["propostas"]["lista"])
    n_lei = sum(1 for x in lula["propostas"]["lista"] if x.get("status") == "lei")
    fmt = lambda n: f"{n:,}".replace(",", ".")
    ok("Lula: os números grandes batem com os dados (propostas, viraram lei, leis sancionadas, vetos)",
       any(k.startswith(fmt(n_prop) + " propostas") for k in ks) and any(k.startswith(fmt(n_lei) + " ") for k in ks) and
       any(k.startswith(fmt(lula["executivo"]["leisSancionadas"]) + " leis sancionadas") for k in ks) and any(k.startswith(fmt(lula["executivo"]["vetos"]) + " vetos") for k in ks), " | ".join(ks))
    await pg.locator('.d-numeros-perfil a.d-kpi[href="#leis"]').first.click()
    await pg.wait_for_timeout(900)
    ok("Lula: o número “leis sancionadas” abre a aba Leis e vetos", await pg.locator('[role=tab][data-aba="leis"]').get_attribute("aria-selected") == "true")
    ok("Lula: Leis e vetos com a barra dupla dos vetos (só desenho) e os números escritos", await pg.locator("#leis .d-dupla[aria-hidden=true]").count() == 1
       and fmt(lula["executivo"]["leisSancionadas"]) in await pg.locator("#leis .grandes-n").inner_text())
    await aba(pg, "sobre")
    ok("Lula: “Quem é” em blocos com ícone, e o resto em “Mais sobre ele”", await pg.locator("#sobre .fatos .fato").count() >= 3
       and await pg.locator("#sobre details.d-mais-sobre").count() <= 1 and await pg.locator("#sobre details.oque-faz").count() == 1)
    await aba(pg, "propostas")
    seg = await pg.locator("#status-chips .d-status-barra i").count()
    bts = await pg.locator("#status-chips button[data-status]").count()
    ok("Lula: a barra colorida da situação tem uma cor por botão", seg == bts and seg >= 2, f"{seg} cores, {bts} botões")
    c0 = await pg.locator("#contagem-prop").inner_text()
    b = pg.locator("#status-chips button[data-status]").first
    await b.click()
    await pg.wait_for_timeout(600)
    c1 = await pg.locator("#contagem-prop").inner_text()
    ok("Lula: tocar numa cor filtra a lista (e o botão fica marcado)", c0 != c1 and await pg.locator("#status-chips button[aria-pressed=true]").count() == 1, f"{c0} → {c1}")
    await pg.locator("#status-chips button[aria-pressed=true]").click()
    await pg.wait_for_timeout(400)
    ok("Lula: o “💡” das propostas diz o essencial no título", "quantidade não mede qualidade" in (await pg.locator("#propostas details.d-saiba-prop summary").inner_text()).lower())
    await aba(pg, "trajetoria")
    linhas = pg.locator("#trajetoria .d-tempo > li")
    n_l = await linhas.count()
    ok("Lula: a faixa do tempo com uma linha por mandato (4) e o de hoje marcado", n_l == 4 and await pg.locator("#trajetoria .d-tempo > li.aqui").count() == 1, str(n_l))
    ok("Lula: os números da História (eleições, vezes eleito, mandatos)", await pg.locator("#trajetoria .traj-kpis .d-kpi").count() == 3)
    ok("Lula: a linha do tempo completa continua (com “Ver este mandato”)", await pg.locator("#trajetoria .traj-item").count() >= 5 and await pg.locator("#trajetoria a.traj-ver-btn").count() == 3)
    await axe(pg, "perfil de Lula, História com a faixa do tempo")
    await pg.locator('#trajetoria a.d-tempo-item[data-mandato="dep-1987"]').click()
    await pg.wait_for_url("**mandato=dep-1987**", timeout=15000)
    await pg.wait_for_timeout(2000)
    ok("Lula: a linha de 1987 leva ao mandato de deputado (a faixa amarela diz)", "1987" in await pg.locator("#faixa-mandato").inner_text())
    ks = [re.sub(r"^\D+", "", re.sub(r"\s+", " ", k)).strip() for k in await pg.locator(".d-numeros-perfil .d-kpi").all_inner_texts()]
    ok("Lula em 1987: os números são daquele mandato (propostas no mandato e a idade no começo)", any("neste mandato" in k for k in ks) and any("no começo do mandato" in k for k in ks), " | ".join(ks))
    await aba(pg, "trajetoria")
    ok("Lula em 1987: na faixa do tempo, a linha de 1987 marcada", "1987" in await pg.locator("#trajetoria .d-tempo > li.aqui").inner_text())
    await pg.locator("#voltar-lista").count()

    # deputada: votos em colunas, gastos
    await vai(pg, "pessoa.html?id=dep-178866&lang=pt#votacoes", 3000)
    r = dep["votacoes"]["resumo"]
    cols = await pg.locator("#votacoes .d-colunas .d-coluna").count()
    ok("deputada: uma coluna por tipo de voto (só desenho) e a legenda em texto", cols == sum(1 for k in ("Sim", "Não", "Abstenção", "Obstrução", "Outro") if r.get(k))
       and await pg.locator("#votacoes .d-colunas[aria-hidden=true]").count() == 1 and f"Total: {fmt(r['total'])}" in await pg.locator("#votacoes .legenda-votos").inner_text())
    alt = await pg.locator("#votacoes .d-coluna i").evaluate_all("l => l.map(i => i.getBoundingClientRect().height)")
    ok("deputada: a coluna mais alta é a do voto mais comum", alt.index(max(alt)) == [k for k in ("Sim", "Não", "Abstenção", "Obstrução", "Outro") if r.get(k)].index(max((k for k in ("Sim", "Não", "Abstenção", "Obstrução", "Outro") if r.get(k)), key=lambda k: r[k])))
    await aba(pg, "gastos")
    ok("deputada: gastos com os números grandes, “Não é salário” à vista e as barras", "Não é salário" in await pg.locator("#gastos").inner_text()
       and await pg.locator("#gastos .grandes-n .grande-n").count() >= 1 and await pg.locator("#gastos li.gasto").count() >= 1)
    await aba(pg, "propostas")
    temas = await pg.locator("#temas-chips button.d-tema").count()
    if temas:
        b = pg.locator("#temas-chips button.d-tema").first
        await b.click()
        await pg.wait_for_timeout(500)
        ok("deputada: os assuntos em barras (botões que filtram)", await pg.locator("#temas-chips button.d-tema[aria-pressed=true]").count() == 1 and await pg.locator("#temas-chips .d-tema-trilho i").count() == temas)
    await axe(pg, "perfil da deputada, propostas")

    # todos os tipos de perfil
    for pid in ("pres-lula", "vp-alckmin", "min-advocacia-geral-da-uniao", "sen-5207", "dep-178866", "gov-SP", "vgov-SP", "dest-SP-250001610141",
                "pref-3105202", "ver-1500347-140002038381", "e26-BA-50002532504", "stf-flavio-dino"):
        await vai(pg, f"pessoa.html?id={pid}&lang=pt", 1800)
        h1 = await pg.locator("h1").count()
        mold = await pg.locator(".perfil-topo .moldura .av").count()
        nk = await pg.locator(".d-numeros-perfil .d-kpi").count()
        ok(f"perfil {pid}: nome, foto na moldura e números grandes ({nk})", h1 == 1 and mold == 1 and (nk >= 1 or pid.startswith("min-")))
    ok("Perfil: nenhum erro de JavaScript", not erros, "; ".join(erros)[:300])
    await ctx.close()


# ------------------------------------------------------------------ 3. tablet, celular, 320 px, inglês, menos movimento
async def outros(nav):
    print("\n— 3. Tablet, celular, 320 px, inglês e “menos movimento” —")
    ctx = await ctx_novo(nav, viewport={"width": 820, "height": 1180}, has_touch=True)
    pg = await ctx.new_page()
    await vai(pg, "brasil.html?lang=pt")
    ok("tablet (820 px): o menu lateral à vista e sem a barra de baixo", await pg.locator("#casca-lado").is_visible() and
       await pg.evaluate("getComputedStyle(document.querySelector('.casca-baixo')).display") == "none" and
       await pg.evaluate("document.querySelector('#casca-lado').getBoundingClientRect().left") >= 0)
    ok("tablet: o conteúdo começa depois do menu", await pg.evaluate("document.querySelector('main').getBoundingClientRect().left >= document.querySelector('#casca-lado').getBoundingClientRect().right - 1"))
    ok("tablet: sem rolar para os lados", await pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    await vai(pg, "pessoa.html?id=dep-178866&lang=pt")
    ok("tablet: o perfil sem rolar para os lados", await pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    await ctx.close()

    for w in (390, 320):
        ctx = await ctx_novo(nav, viewport={"width": w, "height": 760}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        for u in ("brasil.html?lang=pt#senado", "brasil.html?lang=pt#votacoes", "brasil.html?lang=pt#judiciario", "brasil.html?lang=en", "brasil.html?mandato=2019&lang=pt",
                  "pessoa.html?id=pres-lula&lang=pt#trajetoria", "pessoa.html?id=dep-178866&lang=pt#propostas", "pessoa.html?id=dep-178866&lang=en#votacoes"):
            await vai(pg, u, 2000)
            lado = await pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            ok(f"{w} px sem rolar para os lados: {u}", lado <= 0, f"{lado}px")
        await vai(pg, "brasil.html?lang=pt#senado", 2500)
        await pg.locator("#senado .d-partido").first.tap()
        await pg.wait_for_timeout(900)
        ok(f"{w} px: a gaveta do partido sobe de baixo", await gaveta_aberta(pg) and await pg.locator("#gaveta").get_attribute("data-lado") == "baixo")
        lado = await pg.evaluate("Math.max(document.documentElement.scrollWidth, document.getElementById('gaveta').scrollWidth) - innerWidth")
        ok(f"{w} px: a gaveta do partido cabe na tela", lado <= 0, f"{lado}px")
        if w == 390:
            await axe(pg, "celular, Brasil com a gaveta de um partido aberta")
            alturas = await pg.locator("#senado .d-partido").evaluate_all("l => l.map(b => b.getBoundingClientRect().height)")
            ok("celular: etiquetas dos partidos com pelo menos 44 px", min(alturas) >= 44)
        await fecha_gaveta(pg)
        await ctx.close()

    # inglês
    ctx = await ctx_novo(nav, lang="en", viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await vai(pg, "brasil.html?lang=en", 2000)
    t = await pg.locator("#numeros").inner_text()
    ok("inglês: os números do topo em inglês", "senators" in t and "federal deputies" in t and "Supreme Court" in t, t.replace("\n", " ")[:120])
    await aba(pg, "senado")
    et = await pg.locator("#senado .d-partido").first.inner_text()
    nm = await pg.locator("#senado .d-partido").first.evaluate("b => b.textContent")
    ok("inglês: a etiqueta do partido diz “senators” para o leitor de tela", "senator" in nm, nm)
    await pg.locator("#senado .d-partido").first.click()
    await pg.wait_for_timeout(800)
    gt = await pg.locator("#gaveta").inner_text()
    ok("inglês: a gaveta do partido em inglês", "of 81 senators" in gt and "alphabetical order" in gt, gt.replace("\n", " ")[:120])
    await fecha_gaveta(pg)
    await vai(pg, "pessoa.html?id=pres-lula&lang=en", 2000)
    t = await pg.locator(".d-numeros-perfil").inner_text()
    ok("inglês: os números do perfil em inglês", "proposals" in t and "became law" in t and "laws signed" in t, t.replace("\n", " ")[:120])
    await aba(pg, "trajetoria")
    t = await pg.locator("#trajetoria").inner_text()
    ok("inglês: a faixa do tempo em inglês", "The timeline" in t and "terms served" in t)
    await ctx.close()

    # menos movimento
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = await ctx.new_page()
    await vai(pg, "pessoa.html?id=dep-178866&lang=pt#votacoes", 2000)
    a = await pg.evaluate("[getComputedStyle(document.querySelector('.d-kpi b')).animationName, getComputedStyle(document.querySelector('.d-coluna i')).animationName]")
    ok("menos movimento (prefers-reduced-motion): sem a animação dos números e das colunas", a == ["none", "none"], str(a))
    await ctx.close()
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    await ctx.add_init_script("try{localStorage.setItem('ep-a11y', JSON.stringify({movimento: true}))}catch(e){}")
    pg = await ctx.new_page()
    await vai(pg, "pessoa.html?id=pres-lula&lang=pt", 2000)
    a = await pg.evaluate("[getComputedStyle(document.querySelector('.d-kpi b')).animationName, getComputedStyle(document.querySelector('.perfil-topo .moldura .av')).transform]")
    ok("menos movimento (Leitura): sem animação nos números e a moldura sem girar", a[0] == "none" and a[1] in ("none", "matrix(1, 0, 0, 1, 0, 0)"), str(a))
    await ctx.close()


# ------------------------------------------------------------------ 4. os botões ‹ › da barra das abas (pedido do Lucas, 4/11)
# o estado da barra: se rola, os dois botões (à vista? fora da parte que rola? tamanho, rótulo), a aba aberta à vista e a
# primeira aba que não aparece inteira à direita (a que o › deve trazer)
ESTADO_BARRA = """() => {
  const l = document.querySelector('.abas-lista'), b = l.closest('.abas-barra'), rl = l.getBoundingClientRect();
  const s = [...b.querySelectorAll(':scope > .abas-seta')].map(x => { const r = x.getBoundingClientRect(), cs = getComputedStyle(x);
    return { mostra: cs.display !== 'none', vis: cs.display !== 'none' && !x.disabled, w: r.width, h: r.height, l: r.left, r: r.right, lab: x.getAttribute('aria-label'),
      dentro: l.contains(x), ctl: x.getAttribute('aria-controls') === l.id, fundo: cs.backgroundColor === getComputedStyle(b).backgroundColor }; });
  const tabs = [...l.querySelectorAll('[role=tab]')].filter(t => !t.hidden);
  const at = l.querySelector('[role=tab][aria-selected=true]').getBoundingClientRect();
  const prox = tabs.find(t => t.getBoundingClientRect().right > rl.right + 1);
  const pl = parseFloat(getComputedStyle(l).paddingLeft) || 0;
  const alinhada = tabs.some(t => Math.abs(t.getBoundingClientRect().left - rl.left - pl) <= 1) || l.scrollLeft <= 1 || l.scrollLeft >= l.scrollWidth - l.clientWidth - 1;
  return { rola: l.scrollWidth > l.clientWidth + 1, classe: b.classList.contains('rola'), sl: l.scrollLeft, max: l.scrollWidth - l.clientWidth,
    esq: s[0], dir: s[1], ll: rl.left, lr: rl.right, ativa: at.left >= rl.left - 1 && at.right <= rl.right + 1,
    prox: prox ? prox.dataset.aba : null, sobra: document.documentElement.scrollWidth - window.innerWidth, alinhada,
    esmaece: ['::before', '::after'].map(p => getComputedStyle(l, p).display !== 'none' && getComputedStyle(l, p).opacity !== '0') };
}"""
INTEIRA = """a => { const l = document.querySelector('.abas-lista'), rl = l.getBoundingClientRect(), r = l.querySelector('[role=tab][data-aba="' + a + '"]').getBoundingClientRect();
  return r.left >= rl.left - 1 && r.right <= rl.right + 1; }"""
# as bordas limpas: nos 8 px de fora de cada botão e no meio dele, nada de aba (nada da lista fora da área entre os botões nem por
# trás deles); na área entre os botões, nenhuma aba à vista pela metade (a não ser a que sozinha é mais larga que a área)
LIMPO = """() => {
  const l = document.querySelector('.abas-lista'), b = l.closest('.abas-barra'), rl = l.getBoundingClientRect(), prob = [];
  const ehAba = (x, y) => { const e = document.elementFromPoint(x, y); return !!(e && e.closest('[role=tab]')); };
  for (const s of b.querySelectorAll(':scope > .abas-seta')) {
    const r = s.getBoundingClientRect();
    if (getComputedStyle(s).display === 'none') continue;
    for (const y of [r.top + 4, r.top + r.height / 2, r.bottom - 4]) {
      const esq = s.classList.contains('abas-seta-esq'), nome = esq ? '‹' : '›';
      for (let k = 1; k <= 8; k++) {
        if (esq && ehAba(r.left - k, y)) prob.push('aba à esquerda do ‹ (' + k + ' px)');
        if (!esq && ehAba(r.right + k, y)) prob.push('aba à direita do › (' + k + ' px)');
      }
      for (const x of [r.left + 2, r.left + r.width / 2, r.right - 2]) if (ehAba(x, y)) prob.push('aba por trás do ' + nome);
    }
  }
  for (const t of l.querySelectorAll('[role=tab]')) {
    if (t.hidden || getComputedStyle(t).opacity === '0') continue;
    const r = t.getBoundingClientRect(), vis = Math.min(r.right, rl.right) - Math.max(r.left, rl.left);
    if (vis > 0.5 && vis < r.width - 1 && r.width <= rl.width) prob.push('aba cortada: ' + t.dataset.aba + ' (' + Math.round(vis) + ' de ' + Math.round(r.width) + ' px)');
  }
  return [...new Set(prob)];
}"""


async def abas_botoes(nav):
    print("\n== 4. Os botões ‹ › da barra das abas ==")
    PAGS = [("estado BA", "estado.html?uf=BA"), ("Brasil", "brasil.html"), ("cidade Salvador", "cidade.html?ibge=2927408"),
            ("perfil", "pessoa.html?id=dep-178866"), ("Brasil 2027", "brasil.html?mandato=2027")]
    for w, h in ((320, 640), (390, 844), (620, 900), (768, 1024)):
        movel = w < 768
        ctx = await ctx_novo(nav, viewport={"width": w, "height": h}, is_mobile=movel, has_touch=movel)
        pg = await ctx.new_page()
        for nome, url in PAGS:
            if w in (620, 768) and nome == "Brasil 2027":
                continue
            await vai(pg, url, 1800)
            await pg.evaluate("() => { const a = document.querySelector('.abas-ep'); window.scrollTo(0, a.getBoundingClientRect().top + scrollY - 160); }")
            await pg.wait_for_timeout(300)
            e = await pg.evaluate(ESTADO_BARRA)
            onde = f"{w} px, {nome}"
            ok(f"{onde}: os botões só existem quando a barra rola", e["classe"] == e["rola"] and e["esq"]["mostra"] == e["rola"] and e["dir"]["mostra"] == e["rola"], f"rola={e['rola']} classe={e['classe']}")
            if not e["rola"]:
                continue
            ok(f"{onde}: no começo, o › ativo e o ‹ desativado (apagado)", e["sl"] <= 1 and not e["esq"]["vis"] and e["dir"]["vis"], f"sl={e['sl']}")
            d = e["dir"]
            ok(f"{onde}: o › fica fora da parte que rola, ≥ 44 px, com o fundo da barra, rótulo e aria-controls",
               not d["dentro"] and d["l"] >= e["lr"] - 1 and d["w"] >= 44 and d["h"] >= 44 and d["fundo"] and d["lab"] == "Ver mais abas" and d["ctl"], str(d))
            ok(f"{onde}: sem esmaecimento por cima das abas (os botões já mostram que há mais)", e["esmaece"] == [False, False], str(e["esmaece"]))
            ok(f"{onde}: a aba aberta está à vista", e["ativa"])
            ok(f"{onde}: nada passa da tela", e["sobra"] <= 0, str(e["sobra"]))
            lp = await pg.evaluate(LIMPO)
            ok(f"{onde}, no começo: bordas limpas (nada de aba fora da área entre os botões, nem cortada)", not lp, "; ".join(lp))
            prox = e["prox"]
            await pg.locator(".abas-seta-dir").click()
            await pg.wait_for_timeout(900)
            e2 = await pg.evaluate(ESTADO_BARRA)
            ok(f"{onde}: o › rola a barra e a aba seguinte ({prox}) aparece inteira, alinhada à borda; o ‹ fica ativo",
               e2["sl"] > e["sl"] + 20 and await pg.evaluate(INTEIRA, prox) and e2["alinhada"] and e2["esq"]["vis"] and not e2["esq"]["dentro"] and e2["esq"]["r"] <= e2["ll"] + 1,
               f"{e['sl']} → {e2['sl']}")
            lp = await pg.evaluate(LIMPO)
            ok(f"{onde}, no meio (depois do ›): bordas limpas", not lp, "; ".join(lp))
            # até o fim: o › fica desativado e o foco não se perde
            for _ in range(10):
                if not (await pg.evaluate(ESTADO_BARRA))["dir"]["vis"]:
                    break
                await pg.locator(".abas-seta-dir").click()
                await pg.wait_for_timeout(800)
                lp = await pg.evaluate(LIMPO)
                if lp:
                    ok(f"{onde}, depois de um ›: bordas limpas", False, "; ".join(lp))
            e3 = await pg.evaluate(ESTADO_BARRA)
            foco = await pg.evaluate("document.activeElement === document.body ? 'body' : (document.activeElement.className || document.activeElement.tagName)")
            ok(f"{onde}: no fim, o › desativado, o ‹ ativo e o foco vai para o ‹", e3["sl"] >= e3["max"] - 1 and not e3["dir"]["vis"] and e3["esq"]["vis"] and "abas-seta-esq" in foco, f"{e3['sl']}/{e3['max']} foco={foco}")
            lp = await pg.evaluate(LIMPO)
            ok(f"{onde}, no fim: bordas limpas", not lp, "; ".join(lp))
            await pg.locator(".abas-seta-esq").click()
            await pg.wait_for_timeout(900)
            lp = await pg.evaluate(LIMPO)
            e5 = await pg.evaluate(ESTADO_BARRA)
            ok(f"{onde}, depois do ‹: bordas limpas e uma aba alinhada à borda", not lp and e5["alinhada"], "; ".join(lp))
            for _ in range(10):
                if not (await pg.evaluate(ESTADO_BARRA))["esq"]["vis"]:
                    break
                await pg.locator(".abas-seta-esq").click()
                await pg.wait_for_timeout(800)
            e4 = await pg.evaluate(ESTADO_BARRA)
            ok(f"{onde}: o ‹ volta ao começo e fica desativado", e4["sl"] <= 1 and not e4["esq"]["vis"] and e4["dir"]["vis"], str(e4["sl"]))
        await ctx.close()

    # aba pelo endereço (a última): fica à vista, com o ‹ ativo e o › desativado
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await vai(pg, "estado.html?uf=BA#cidade", 2200)
    await pg.evaluate("() => { const a = document.querySelector('.abas-ep'); window.scrollTo(0, a.getBoundingClientRect().top + scrollY - 160); }")
    await pg.wait_for_timeout(300)
    e = await pg.evaluate(ESTADO_BARRA)
    ult = await pg.evaluate("[...document.querySelectorAll('.abas-lista [role=tab]')].filter(t => !t.hidden).pop().dataset.aba")
    ok("390 px, estado BA#cidade (a última aba pelo endereço): ela está aberta e à vista; o ‹ ativo, o › não",
       e["ativa"] and await pg.evaluate("document.querySelector('.abas-lista [aria-selected=true]').dataset.aba") == ult and e["esq"]["vis"] and not e["dir"]["vis"], str(e["sl"]))
    lp = await pg.evaluate(LIMPO)
    ok("390 px, a última aba pelo endereço: bordas limpas", not lp, "; ".join(lp))
    # trocar de aba pelo teclado (setas) continua levando a aba aberta para a vista
    await pg.locator(".abas-lista [role=tab][aria-selected=true]").focus()
    await pg.keyboard.press("Home")
    await pg.wait_for_timeout(900)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("390 px: Home nas abas abre a primeira, à vista; o ‹ desativado", e["ativa"] and e["sl"] <= 1 and not e["esq"]["vis"], str(e["sl"]))
    # arrastar com o dedo (rolar direto) até o meio de uma aba: a barra para alinhada (scroll-snap) e o ‹ fica ativo
    larg = await pg.evaluate("document.querySelector('.abas-lista [role=tab]').getBoundingClientRect().width")
    await pg.evaluate(f"document.querySelector('.abas-lista').scrollLeft = {int(larg * 0.7)}")
    await pg.wait_for_timeout(900)
    e = await pg.evaluate(ESTADO_BARRA)
    lp = await pg.evaluate(LIMPO)
    ok("390 px: rolar a barra direto (dedo) para alinhada a uma aba, com o ‹ ativo e as bordas limpas", e["esq"]["vis"] and e["sl"] > 1 and e["alinhada"] and not lp, f"sl={e['sl']} {'; '.join(lp)}")
    await axe(pg, "celular, estado BA com os dois botões à vista")
    await ctx.close()

    # inglês: os rótulos
    ctx = await ctx_novo(nav, "en", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await vai(pg, "estado.html?uf=BA&lang=en", 1800)
    await pg.locator(".abas-seta-dir").click()
    await pg.wait_for_timeout(800)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("inglês: “Previous tabs” e “More tabs”", e["esq"]["lab"] == "Previous tabs" and e["dir"]["lab"] == "More tabs", f"{e['esq']['lab']} / {e['dir']['lab']}")
    await axe(pg, "celular em inglês, estado BA com os botões")
    await vai(pg, "pessoa.html?id=dep-178866&lang=en", 1800)
    await axe(pg, "celular em inglês, perfil com os botões")
    await ctx.close()

    # computador: tudo cabe, sem botões; a janela que estreita ganha os botões; a letra maior também recalcula
    ctx = await ctx_novo(nav, viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await vai(pg, "brasil.html", 1800)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("1440 px, Brasil: as abas cabem, sem botões", not e["rola"] and not e["classe"] and not e["esq"]["vis"] and not e["dir"]["vis"])
    await pg.set_viewport_size({"width": 620, "height": 900})
    await pg.wait_for_timeout(900)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("a janela estreita para 620 px: a barra rola e ganha o ›", e["rola"] and e["classe"] and e["dir"]["vis"] and not e["esq"]["vis"] and e["ativa"])
    await pg.set_viewport_size({"width": 1440, "height": 900})
    await pg.wait_for_timeout(900)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("de volta a 1440 px: os botões somem", not e["classe"] and not e["dir"]["vis"])
    await pg.evaluate("EP.a11y('escala', 1.5)")
    await pg.wait_for_timeout(1200)
    e = await pg.evaluate(ESTADO_BARRA)
    ok("letra maior (Leitura): os botões acompanham (só quando a barra passa a rolar)", e["classe"] == e["rola"] and e["dir"]["vis"] == (e["rola"] and e["sl"] < e["max"] - 1), f"rola={e['rola']}")
    await pg.evaluate("EP.a11y('escala', 1)")
    await ctx.close()

    # o desenho do cabeçalho fica menor na tela estreita: o título aparece mais cedo
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    for nome, url in (("estado BA", "estado.html?uf=BA"), ("cidade Salvador", "cidade.html?ibge=2927408"), ("Brasil", "brasil.html")):
        await vai(pg, url, 1500)
        m = await pg.evaluate("""() => { const c = document.querySelector('html.com-abas .cab-pagina > .cab-3d'), cab = c.closest('.cab-pagina'), h = cab.querySelector('h1');
          const sel = cab.querySelector('.selo-topo, .selo'); const r = c.getBoundingClientRect();
          return [Math.round(r.height), Math.round(h.getBoundingClientRect().top), sel ? Math.round(sel.getBoundingClientRect().top - r.bottom) : 0]; }""")
        ok(f"390 px, {nome}: o desenho do cabeçalho tem no máximo 140 px e não fica por cima do texto", m[0] <= 140 and m[2] >= -2, str(m))
    await ctx.close()

# ------------------------------------------------------------------ 5. "‹ parte anterior" e "próxima parte ›" no fim de cada aba
PASSOS = """() => {
  const vis = [...document.querySelectorAll('.abas-lista [role=tab]')].filter(t => !t.hidden);
  const nome = t => { const c = t.cloneNode(true); c.querySelectorAll('[aria-hidden="true"], .sr').forEach(x => x.remove()); return c.textContent.replace(/\\s+/g, ' ').trim(); };
  const p = document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden])'), nav = p.querySelector(':scope > .abas-passos');
  const bs = nav ? [...nav.querySelectorAll('.abas-passo')].map(b => { const r = b.getBoundingClientRect(); return { cls: b.className, vai: b.dataset.vai, lab: b.getAttribute('aria-label'), h: r.height, w: r.width, l: r.left, r: r.right }; }) : [];
  return { abas: vis.map(t => t.dataset.aba), nomes: vis.map(nome), ativa: p.dataset.aba, bs, sobra: document.documentElement.scrollWidth - window.innerWidth,
    ultimoNoPainel: nav ? p.lastElementChild === nav : null };
}"""


async def abas_passos(nav):
    print("\n== 5. Anterior e próxima no fim de cada aba ==")
    PAGS = [("Brasil", "brasil.html", (320, 390, 1440)), ("estado BA", "estado.html?uf=BA", (390, 1440)), ("cidade Salvador", "cidade.html?ibge=2927408", (390,)),
            ("perfil", "pessoa.html?id=dep-178866", (320, 1440)), ("Brasil 2019", "brasil.html?mandato=2019", (390,)), ("Brasil 2027", "brasil.html?mandato=2027", (390,))]
    for nome, url, ws in PAGS:
        for w in ws:
            movel = w < 768
            ctx = await ctx_novo(nav, viewport={"width": w, "height": 844 if movel else 900}, is_mobile=movel, has_touch=movel)
            pg = await ctx.new_page()
            await vai(pg, url, 1800)
            e = await pg.evaluate(PASSOS)
            onde = f"{w} px, {nome}"
            vis, nomes = e["abas"], e["nomes"]
            ok(f"{onde}: na 1ª aba, só “Próxima parte: {nomes[1]}”, no fim do painel", e["ativa"] == vis[0] and len(e["bs"]) == 1 and e["bs"][0]["vai"] == vis[1]
               and e["bs"][0]["lab"] == f"Próxima parte: {nomes[1]}" and e["ultimoNoPainel"], str(e["bs"]))
            ok(f"{onde}: botões ≥ 44 px e nada passa da tela", all(b["h"] >= 44 for b in e["bs"]) and e["sobra"] <= 0, f"sobra={e['sobra']}")
            # clicar na próxima: troca a aba, o endereço muda, rola ao começo das abas e o foco vai ao título
            await pg.locator(".abas-grupo > [role=tabpanel]:not([hidden]) .abas-passo-prox").click()
            await pg.wait_for_timeout(900)
            e2 = await pg.evaluate(PASSOS)
            st = await pg.evaluate("""() => { const g = document.querySelector('.abas-grupo'), t = document.querySelector('header.topo'), a = document.activeElement;
              return [location.hash, Math.round(g.getBoundingClientRect().top - t.getBoundingClientRect().bottom), a.tagName, !!a.closest('[role=tabpanel]:not([hidden])'),
                document.querySelector('.abas-lista [aria-selected=true]').dataset.aba]; }""")
            ok(f"{onde}: “próxima” abre a 2ª aba como o menu (endereço #{vis[1]}, aba marcada na barra, começo das abas à vista, foco no título)",
               e2["ativa"] == vis[1] and st[0] == "#" + vis[1] and st[4] == vis[1] and -3 <= st[1] <= 16 and st[2] in ("H2", "H3") and st[3], str(st))
            if len(vis) > 2:
                ok(f"{onde}: numa aba do meio, os dois botões (‹ {nomes[0]} e {nomes[2]} ›)", [b["vai"] for b in e2["bs"]] == [vis[0], vis[2]]
                   and e2["bs"][0]["lab"] == f"Parte anterior: {nomes[0]}" and ("abas-passo-ant" in e2["bs"][0]["cls"]), str(e2["bs"]))
                if w == 320:
                    ok(f"{onde}: no celular estreito, um embaixo do outro, sem passar da tela", e2["bs"][1]["l"] < e2["bs"][0]["r"] and e2["sobra"] <= 0, str(e2["bs"]))
            # o Voltar do navegador volta para a aba anterior
            await pg.go_back()
            await pg.wait_for_timeout(900)
            ok(f"{onde}: o Voltar do navegador volta para a 1ª aba", (await pg.evaluate(PASSOS))["ativa"] == vis[0])
            # a última aba: só "anterior"
            await pg.evaluate("a => document.querySelector('.abas-lista [role=tab][data-aba=\"' + a + '\"]').click()", vis[-1])
            await pg.wait_for_timeout(1500)
            e3 = await pg.evaluate(PASSOS)
            ok(f"{onde}: na última aba, só “Parte anterior: {nomes[-2]}”", len(e3["bs"]) == 1 and e3["bs"][0]["vai"] == vis[-2] and e3["bs"][0]["lab"] == f"Parte anterior: {nomes[-2]}", str(e3["bs"]))
            await pg.locator(".abas-grupo > [role=tabpanel]:not([hidden]) .abas-passo-ant").click()
            await pg.wait_for_timeout(900)
            ok(f"{onde}: “anterior” abre a penúltima aba", (await pg.evaluate(PASSOS))["ativa"] == vis[-2] and await pg.evaluate("location.hash") == "#" + vis[-2])
            if w == 390 and nome == "Brasil":
                await pg.evaluate("() => { const n = document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden]) > .abas-passos'); n.scrollIntoView({block: 'center'}); }")
                await pg.wait_for_timeout(1200)
                await axe(pg, "celular, Brasil com os botões de anterior e próxima")
            await ctx.close()
    # inglês
    ctx = await ctx_novo(nav, "en", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await vai(pg, "brasil.html?lang=en#senado", 2000)
    e = await pg.evaluate(PASSOS)
    labs = [b["lab"] for b in e["bs"]]
    ok("inglês: “Previous: …” e “Next: …”", len(labs) == 2 and labs[0] == f"Previous: {e['nomes'][0]}" and labs[1] == f"Next: {e['nomes'][2]}", str(labs))
    # (o axe confere a página toda; no topo, nada fica por baixo do cabeçalho e da barra presos, que confundem a conta do contraste)
    await pg.evaluate("window.scrollTo(0, 0)")
    await pg.wait_for_timeout(1200)
    await axe(pg, "celular em inglês, Brasil com os botões de anterior e próxima")
    await vai(pg, "estado.html?uf=BA&lang=en#federais", 3500)
    await pg.mouse.wheel(0, -50000)
    await pg.evaluate("window.scrollTo(0, 0)")
    # (o 'visivel' que o axe() põe começa a animação de aparecer: espera ela acabar antes de medir o contraste)
    await pg.evaluate("document.querySelectorAll('.rev,.r3d').forEach(e => e.classList.add('visivel'))")
    await pg.wait_for_timeout(1500)
    await axe(pg, "celular em inglês, estado BA")
    await ctx.close()

# ------------------------------------------------------------------ 6. o site suave (rolagem e transições)
# clica (pelo JS, sem o mousedown que para a rolagem) e anota a posição da página a cada quadro, por ~40 quadros
AMOSTRA = """async sel => {
  const ys = [], el = document.querySelector(sel), g0 = document.querySelector('.abas-grupo'), t0 = document.querySelector('header.topo');
  const inicio = Math.round(g0.getBoundingClientRect().top - t0.getBoundingClientRect().bottom);
  el.click();
  await new Promise(r => { let n = 0; (function f() { ys.push(Math.round(scrollY)); if (++n < 45) requestAnimationFrame(f); else r(); })(); });
  await new Promise(r => setTimeout(r, 450));
  const g = document.querySelector('.abas-grupo'), t = document.querySelector('header.topo'), b = document.querySelector('.abas-barra');
  const h = document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden]) h2');
  return { ys, inicio, distintos: new Set(ys).size, fimGrupo: Math.round(g.getBoundingClientRect().top - t.getBoundingClientRect().bottom),
    tituloAbaixo: h ? Math.round(h.getBoundingClientRect().top - b.getBoundingClientRect().bottom) : null };
}"""
# a maior duração de transição na página (só as que valem: elementos à vista; a câmera do mapa do Entenda é o passeio entre as
# paradas e fica de fora)
MAIOR_TRANS = """() => {
  const seg = v => v.split(',').map(x => x.trim()).map(x => x.endsWith('ms') ? parseFloat(x) : parseFloat(x) * 1000);
  let pior = [0, ''];
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el), ds = seg(cs.transitionDuration), ps = cs.transitionProperty.split(',').map(x => x.trim());
    ds.forEach((d, i) => { const pr = ps[i] || ps[0] || ''; if (pr.startsWith('--') || pr === 'left' || pr === 'top') return;
      if (d > pior[0]) pior = [d, (el.id || el.className || el.tagName) + ' ' + pr]; });
  }
  return pior;
}"""


async def suave(nav):
    print("\n== 6. O site suave ==")
    for w in (1440, 390):
        movel = w < 768
        for modo in ("normal", "sem-movimento", "reduced"):
            op = dict(viewport={"width": w, "height": 900 if not movel else 844}, is_mobile=movel, has_touch=movel)
            if modo == "reduced":
                op["reduced_motion"] = "reduce"
            ctx = await ctx_novo(nav, **op)
            pg = await ctx.new_page()
            await vai(pg, "brasil.html", 2000)
            await pg.evaluate("document.querySelector('.abas-lista [role=tab][data-aba=\"senado\"]').click()")
            await pg.wait_for_timeout(1500)
            if modo == "sem-movimento":
                await pg.evaluate("EP.a11y('movimento', true)")
            # lá embaixo da aba (a barra presa), troca de aba pela barra (a aba ganha altura, para haver o que rolar em qualquer tela)
            await pg.evaluate("document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden])').style.paddingBottom = '2400px'")
            await pg.evaluate("window.scrollTo({top: document.querySelector('.abas-grupo').getBoundingClientRect().top + scrollY + 900, behavior: 'instant'})")
            await pg.wait_for_timeout(600)
            r = await pg.evaluate(AMOSTRA, '.abas-lista [role=tab][data-aba="camara"]')
            onde = f"{w} px, {modo}"
            fim_ok = -6 <= r["fimGrupo"] <= 16 and r["tituloAbaixo"] is not None and r["tituloAbaixo"] >= -1
            if modo == "normal":
                ok(f"{onde}: trocar de aba pela barra desliza (a posição muda ao longo de vários quadros) e termina no começo das abas, o título abaixo da barra",
                   r["distintos"] >= 5 and fim_ok, f"{r['distintos']} posições; grupo {r['fimGrupo']}; título {r['tituloAbaixo']}; {r['ys'][:6]}…")
            else:
                ok(f"{onde}: trocar de aba é na hora (sem deslizar)", r["distintos"] <= 2 and fim_ok, f"{r['distintos']} posições; {r['ys'][:4]}")
            # o botão "Próxima parte" no fim da aba
            await pg.evaluate("document.querySelector('.abas-grupo > [role=tabpanel]:not([hidden]) > .abas-passos').scrollIntoView({block: 'center', behavior: 'instant'})")
            await pg.wait_for_timeout(500)
            r = await pg.evaluate(AMOSTRA, '.abas-grupo > [role=tabpanel]:not([hidden]) .abas-passo-prox')
            fim_ok = -6 <= r["fimGrupo"] <= 16 and r["tituloAbaixo"] is not None and r["tituloAbaixo"] >= -1
            if modo == "normal":
                # (se o começo das abas já estava quase no lugar, não há o que deslizar)
                ok(f"{onde}: “Próxima parte” desliza até o começo das abas e o título fica abaixo da barra", (r["distintos"] >= 5 or abs(r["inicio"]) < 60) and fim_ok, f"início {r['inicio']}; {r['distintos']} posições; grupo {r['fimGrupo']}; título {r['tituloAbaixo']}")
                foco = await pg.evaluate("document.activeElement.tagName")
                ok(f"{onde}: o foco foi para o título da aba nova", foco == "H2", foco)
            else:
                ok(f"{onde}: “Próxima parte” é na hora", r["distintos"] <= 2 and fim_ok, f"{r['distintos']} posições")
            if modo != "normal":
                tr = await pg.evaluate("getComputedStyle(document.querySelector('.abas-lista [role=tab]')).transitionDuration")
                ok(f"{onde}: sem transições (as abas mudam de cor na hora)", all(float(x.strip().rstrip('ms').rstrip('s') or 0) < 0.01 for x in tr.split(',')) or tr.startswith('1e-'), tr)
            await ctx.close()
    # nenhuma transição passa de 300 ms, em todas as páginas
    ctx = await ctx_novo(nav, viewport={"width": 1280, "height": 900})
    pg = await ctx.new_page()
    for u in ("index.html", "entenda.html", "brasil.html", "estado.html?uf=BA", "cidade.html?ibge=2927408", "pessoa.html?id=dep-178866",
              "votacoes.html", "votacao.html?casa=camara&id=2236186-60", "dados.html", "imparcialidade.html", "404.html"):
        await vai(pg, u, 1200)
        m = await pg.evaluate(MAIOR_TRANS)
        ok(f"{u}: nenhuma transição passa de 300 ms", m[0] <= 300, f"{m[0]:.0f} ms em {m[1]}")
    await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        if SO in ("", "brasil"):
            await brasil(nav)
        if SO in ("", "perfil"):
            await perfil(nav)
        if SO in ("", "outros"):
            await outros(nav)
        if SO in ("", "abas"):
            await abas_botoes(nav)
        if SO in ("", "passos"):
            await abas_passos(nav)
        if SO in ("", "suave"):
            await suave(nav)
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
