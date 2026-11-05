"""Testes do perfil filtrado por mandato (frente perfil-mandato-r10) com Playwright + Edge.

O seletor "Mandato" no topo do perfil (teclado e toque), a mesma tela filtrada em cada aba (Lula, um senador que foi
deputado, uma deputada reeleita, um deputado estadual que foi vereador, um prefeito que foi vereador, um vereador e um eleito
de 2026), a faixa amarela (aparece, fica presa ao rolar, "Voltar para hoje"), o endereço próprio (abrir direto, Voltar e
Avançar do navegador, o "◀ Voltar" até a lista), o botão "Ver este mandato" da aba História, as abas que dizem que o site
não tem o dado daquele período, português e inglês, 320 px, nenhum servidor novo e nenhum erro de JavaScript.

Uso: python testes/interacao_perfil_mandato.py   (servidor em EP_BASE, padrão http://127.0.0.1:8770/)
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright
from ajuda_abas import pagina_inteira  # site-d-r14

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")
LOCAL = urlparse(BASE).hostname
RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = []
ERROS, FORA = [], set()


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def q(url, k):
    return (parse_qs(urlparse(url).query).get(k) or [None])[0]


def pessoa(pid):
    return json.loads((RAIZ / "dados" / "pessoas" / f"{pid}.json").read_text(encoding="utf-8"))


def entre(lista, de, ate):
    return [x for x in lista if de <= (x.get("data") or "")[:10] <= ate]


async def ctx_novo(nav, lang="pt", **op):
    ctx = await nav.new_context(**op)
    await ctx.add_init_script(f"try{{localStorage.setItem('ep-lang','{lang}')}}catch(e){{}}")
    return ctx


def vigia(pg):
    pg.on("pageerror", lambda e: ERROS.append(str(e)))

    def pedido(r):
        h = urlparse(r.url).hostname
        if h and h != LOCAL and r.resource_type != "image":
            FORA.add(f"{h} ({r.resource_type})")
    pg.on("request", pedido)


async def abre(pg, url, ms=900):
    await pg.goto(BASE + url, wait_until="networkidle")
    await pg.wait_for_timeout(ms)


async def estado(pg):
    return await pg.evaluate("""() => {
      const f = document.getElementById('faixa-mandato'), c = document.getElementById('mp-campo');
      const ativa = document.querySelector('[role=tab][aria-selected=true]');
      return { faixa: f ? f.innerText.replace(/\\s+/g, ' ').trim() : null, campo: c ? c.value : null,
        ativa: ativa ? ativa.getAttribute('data-aba') : null, foco: document.activeElement && (document.activeElement.id || document.activeElement.className),
        aviso: (document.getElementById('mandato-aviso') || {}).textContent || '',
        abas: [...document.querySelectorAll('[role=tab][data-aba]')].filter(t => !t.hidden).map(t => t.getAttribute('data-aba')),
        larg: document.documentElement.scrollWidth - document.documentElement.clientWidth };
    }""")


async def opcoes(pg):
    await pg.locator("#mp-campo").focus()
    await pg.keyboard.press("ArrowDown")
    await pg.wait_for_timeout(300)
    l = await pg.locator("#mp-campo-lista [role=option]").all_inner_texts()
    await pg.keyboard.press("Escape")
    return [x.replace("\n", " ").strip() for x in l]


async def escolhe_teclado(pg, texto, espera_url):
    await pg.locator("#mp-campo").focus()
    await pg.keyboard.type(texto, delay=40)
    await pg.wait_for_timeout(500)
    await pg.keyboard.press("Enter")
    await pg.wait_for_url(espera_url, timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)


async def aba(pg, nome):
    await pg.evaluate(f"EP.abas && EP.abas.mostra('{nome}')")
    await pg.wait_for_timeout(500)


async def texto(pg, sel):
    return (await pg.locator(sel).first.inner_text()) if await pg.locator(sel).count() else ""


async def n_props(pg):
    """quantas propostas a lista do mandato tem (autor principal + assinou junto; sem os botões, a contagem da lista)."""
    ns = await pg.locator("#propostas [data-papel] > b").all_inner_texts()
    if ns:
        return sum(int(x.replace(".", "").replace(",", "")) for x in ns)
    import re
    m = re.search(r"(?:de|of) ([\d.,]+) ", await texto(pg, "#contagem-prop"))
    return int(m.group(1).replace(".", "").replace(",", "")) if m else 0


# ------------------------------------------------------------------ 1. Lula: seletor, faixa, endereço, História
async def lula(nav):
    print("\n— 1. Lula: seletor (teclado), a mesma tela filtrada, faixa, endereço, Voltar/Avançar e a aba História —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    vigia(pg)
    await abre(pg, "pessoa.html?id=pres-lula#propostas")
    e = await estado(pg)
    ok("hoje: o seletor mostra “2023 a 2026 – Presidente (atual)” e não há faixa", e["campo"] == "2023 a 2026 – Presidente (atual)" and e["faixa"] is None, e["campo"])
    ops = await opcoes(pg)
    ok("a lista tem os 4 mandatos exercidos, do mais novo para o mais velho",
       len(ops) == 4 and ops[0].startswith("2023 a 2026") and "2007 a 2010 – Presidente" in ops[1] and "2003 a 2006 – Presidente" in ops[2] and ops[3].startswith("1987 a 1991 – Deputado federal"), " | ".join(ops))
    rot = await pg.evaluate("document.getElementById('mp-campo').labels[0] && document.getElementById('mp-campo').labels[0].innerText.trim()")
    ok("o campo tem nome (rótulo “Mandato”) e descrição", "Mandato" in (rot or "") and await pg.locator("#mp-campo[aria-describedby=mp-dica]").count() == 1, rot)
    n_hoje = await n_props(pg)
    lula_p = pessoa("pres-lula")
    ok("hoje: “O que propôs” é o do mandato de hoje", n_hoje == len(lula_p["propostas"]["lista"]), f"{n_hoje}")
    # teclado: escolher o mandato de deputado
    await escolhe_teclado(pg, "1987", "**mandato=dep-1987**")
    e = await estado(pg)
    ok("Enter no seletor abre o endereço do mandato (pessoa.html?id=pres-lula&mandato=dep-1987)", q(pg.url, "mandato") == "dep-1987" and q(pg.url, "id") == "pres-lula", pg.url.split("/")[-1])
    ok("faixa: “📅 Você está vendo: Deputado federal (São Paulo), 1987 a 1991 · Voltar para hoje”",
       e["faixa"] and "Você está vendo: Deputado federal (São Paulo), 1987 a 1991" in e["faixa"] and "Voltar para hoje" in e["faixa"], e["faixa"])
    ok("a aba continua a mesma (O que propôs) e o foco volta para o seletor", e["ativa"] == "propostas" and e["foco"] == "mp-campo", f"{e['ativa']} / {e['foco']}")
    await pg.wait_for_timeout(600)
    e = await estado(pg)
    ok("o leitor de tela ouve a troca (“Agora você está vendo o mandato de Deputado federal…”)", "1987 a 1991" in e["aviso"] and "Agora" in e["aviso"], e["aviso"])
    ok("as abas do mandato de deputado: Quem é, História, O que propôs, Como votou, Gastos, Fontes",
       e["abas"] == ["sobre", "trajetoria", "propostas", "votacoes", "gastos", "fontes"], ",".join(e["abas"]))
    ok("“O que propôs” de 1987 a 1991: as 6 propostas da Câmara (dados/trajetoria/propostas)", await n_props(pg) == 6, f"{await n_props(pg)}")
    esc = await texto(pg, "#propostas .muted")
    ok("o texto diz de qual mandato é a lista", "no mandato de 1987 a 1991" in esc, esc[:90])
    links = await pg.locator("#lista-prop a[href^='https://www.camara.leg.br/propostas-legislativas/']").count()
    ok("cada proposta tem o link oficial da Câmara", links >= 6, f"{links}")
    ok("sem “Explicação simples em preparo” nos mandatos antigos sem explicação", await pg.locator("#lista-prop .preparando").count() == 0)
    await aba(pg, "votacoes")
    t = await texto(pg, "#votacoes")
    ok("“Como votou”: diz que o site guarda as votações só de quem está no cargo hoje e leva à página oficial",
       "só de quem está no cargo hoje" in t and await pg.locator("#votacoes a[href='https://www.camara.leg.br/deputados/139289']").count() == 1, t[:120].replace("\n", " "))
    await aba(pg, "gastos")
    t = await texto(pg, "#gastos")
    ok("“Gastos”: diz que o site não tem os gastos daquele mandato, sem prometer nada", "só de quem está no cargo hoje" in t and "ainda" not in t.lower() and "em breve" not in t.lower(), t[:100].replace("\n", " "))
    await aba(pg, "sobre")
    t = await texto(pg, "#sobre")
    ok("“Quem é”: cargo, período da legislatura, a eleição antes de 1994, a idade no começo do mandato",
       "Deputado federal (São Paulo)" in t and "legislatura de 1987 a 1991" in t and "anterior a 1994" in t and "41 anos" in t, t[:160].replace("\n", " "))
    await aba(pg, "fontes")
    ok("“Fontes”: as fontes daquele mandato (Câmara)", await pg.locator("#fontes a[href*='camara.leg.br']").count() >= 2)
    # a faixa fica presa ao rolar, logo abaixo da barra das abas, sem cobrir a barra
    await aba(pg, "propostas")
    await pg.evaluate("window.scrollTo(0, 1600)")
    await pg.wait_for_timeout(400)
    r = await pg.evaluate("""() => { const f = document.getElementById('faixa-mandato').getBoundingClientRect(), b = document.querySelector('[role=tablist]').getBoundingClientRect();
      return { ft: f.top, fb: f.bottom, bb: b.bottom, bt: b.top }; }""")
    ok("ao rolar, a faixa continua à vista, colada embaixo da barra das abas", r["bt"] >= 0 and abs(r["ft"] - r["bb"]) <= 2 and r["fb"] < 300, json.dumps(r))
    # a faixa não cobre o lugar para onde a página rola (o scroll-padding conta a faixa)
    pad = await pg.evaluate("parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)")
    ok("a rolagem até um item desconta o cabeçalho, a barra e a faixa", pad >= r["fb"], f"{pad} >= {r['fb']}")
    # Voltar para hoje
    await pg.locator("#faixa-mandato a.fm-hoje").click()
    await pg.wait_for_url(lambda u: "mandato=" not in u, timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1400)
    e = await estado(pg)
    ok("“Voltar para hoje” abre o mandato de hoje (sem faixa, mesma aba), com o foco no seletor e o aviso",
       e["faixa"] is None and e["ativa"] == "propostas" and e["foco"] == "mp-campo" and "mandato de hoje" in e["aviso"], f"{e['ativa']} / {e['foco']} / {e['aviso']}")
    # Voltar e Avançar do navegador
    await pg.go_back()
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    e = await estado(pg)
    ok("Voltar do navegador volta para o mandato de deputado (faixa de volta)", q(pg.url, "mandato") == "dep-1987" and e["faixa"] and "1987" in e["faixa"], pg.url.split("/")[-1])
    await pg.go_forward()
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    e = await estado(pg)
    ok("Avançar volta para hoje", "mandato=" not in pg.url and e["faixa"] is None, pg.url.split("/")[-1])
    # endereço direto: presidente 2003-2006, aba Leis e vetos
    await abre(pg, "pessoa.html?id=pres-lula&mandato=pres-2003#leis", 1200)
    e = await estado(pg)
    t = await texto(pg, "#leis")
    ok("endereço direto (…&mandato=pres-2003#leis): faixa, seletor e a aba Leis e vetos",
       e["faixa"] and "Presidente, 2003 a 2006" in e["faixa"] and e["campo"] == "2003 a 2006 – Presidente" and e["ativa"] == "leis", e["faixa"])
    ok("“Leis e vetos” de 2003 a 2006: o site conta só as do mandato de hoje e aponta o Planalto e o Congresso",
       "só do mandato de hoje" in t and await pg.locator("#leis a[href*='planalto.gov.br']").count() == 1 and await pg.locator("#leis a[href*='congressonacional.leg.br']").count() == 1, t[:90].replace("\n", " "))
    await aba(pg, "propostas")
    t = await texto(pg, "#propostas")
    ok("“O que propôs” de 2003 a 2006 diz que a lista não está aqui", "As deste mandato não estão aqui" in t, t[:120].replace("\n", " "))
    await aba(pg, "sobre")
    t = await texto(pg, "#sobre")
    ok("“Quem é” de 2003 a 2006: eleito no 2º turno de 2002, 52.793.364 votos, partido na época, aviso de datas",
       "2002" in t and "52.793.364" in t and "Partido na época" in t and "O site não tem o dia" in t, t[:200].replace("\n", " "))
    # um mandato de presidente → deputado: a aba Leis e vetos não existe lá; vai para "Quem é"
    await pg.goto(BASE + "pessoa.html?id=pres-lula#leis", wait_until="networkidle")
    await pg.wait_for_timeout(900)
    await escolhe_teclado(pg, "1987", "**mandato=dep-1987**")
    ok("de “Leis e vetos” para o mandato de deputado (que não tem essa aba): abre “Quem é”", urlparse(pg.url).fragment == "sobre" and (await estado(pg))["ativa"] == "sobre", pg.url.split("/")[-1])
    # endereço com um mandato que não existe: volta para hoje e tira o parâmetro
    await abre(pg, "pessoa.html?id=pres-lula&mandato=dep-1900#sobre")
    e = await estado(pg)
    ok("mandato que não existe no endereço: mostra hoje e tira o parâmetro", "mandato=" not in pg.url and e["faixa"] is None and e["campo"].startswith("2023"), pg.url.split("/")[-1])
    await abre(pg, "pessoa.html?id=pres-lula&mandato=pres-2023#sobre")
    ok("o mandato de hoje no endereço vira o endereço de hoje", "mandato=" not in pg.url and (await estado(pg))["faixa"] is None, pg.url.split("/")[-1])
    # História: os botões "Ver este mandato"
    await abre(pg, "pessoa.html?id=pres-lula#trajetoria", 1400)
    bts = await pg.locator("#trajetoria a.traj-ver-btn").count()
    vendo = await texto(pg, "#trajetoria .traj-vendo")
    ok("História: “Ver este mandato” nos 3 mandatos antigos e “Você está vendo este mandato” no de hoje", bts == 3 and "Você está vendo este mandato" in vendo, f"{bts} / {vendo}")
    nomes = await pg.locator("#trajetoria a.traj-ver-btn").evaluate_all("l => l.map(a => a.innerText.replace(/\\s+/g, ' ').trim())")
    ok("cada botão tem nome único para o leitor de tela (o mandato entre parênteses)", len(set(nomes)) == 3 and all("Ver este mandato (" in n for n in nomes), " | ".join(nomes))
    ok("a História não repete o detalhe (sem o bloco “O que fez nesse mandato”)", await pg.locator("#trajetoria .traj-fez").count() == 0)
    curto = await texto(pg, "#trajetoria .traj-fez-curto")
    ok("o mandato de deputado tem o resumo de uma linha (6 propostas; 0 viraram lei)", "6</b>" in (await pg.locator("#trajetoria .traj-fez-curto").first.inner_html()) or "6 propostas" in curto, curto[:90])
    b = pg.locator("#trajetoria a.traj-ver-btn[data-mandato='dep-1987']")
    await b.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_url("**mandato=dep-1987**", timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1300)
    e = await estado(pg)
    ok("“Ver este mandato” (Enter) troca o seletor e leva à aba “Quem é” filtrada, com o foco na faixa",
       e["campo"].startswith("1987 a 1991") and e["ativa"] == "sobre" and e["foco"] == "faixa-mandato-txt", f"{e['campo']} / {e['ativa']} / {e['foco']}")
    await aba(pg, "trajetoria")
    vendo = await pg.locator("#trajetoria li[data-mandato='dep-1987'] .traj-vendo").count()
    ok("na História do mandato antigo, o de 1987 aparece como o que você está vendo", vendo == 1)
    await ctx.close()


# ------------------------------------------------------------------ 2. inglês
async def ingles(nav):
    print("\n— 2. inglês —")
    ctx = await ctx_novo(nav, lang="en", viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    vigia(pg)
    await abre(pg, "pessoa.html?id=pres-lula&mandato=dep-1987&lang=en#sobre", 1200)
    e = await estado(pg)
    ok("faixa em inglês: “📅 You are viewing: Federal Deputy (São Paulo), 1987–1991 · Back to today”",
       e["faixa"] and "You are viewing: Federal Deputy (São Paulo), 1987–1991" in e["faixa"] and "Back to today" in e["faixa"], e["faixa"])
    ok("seletor em inglês (“Term”, “1987–1991 – Federal Deputy · São Paulo”)", e["campo"] == "1987–1991 – Federal Deputy · São Paulo" and
       "Term" in await texto(pg, "#mp-rot"), e["campo"])
    ops = await opcoes(pg)
    ok("a lista em inglês marca o de hoje como “(current)”", ops and ops[0] == "2023–2026 – President (current)", ops[0] if ops else "")
    await aba(pg, "votacoes")
    t = await texto(pg, "#votacoes")
    ok("abas sem dado, em inglês", "only keeps the votes of those in office today" in t, t[:100].replace("\n", " "))
    await aba(pg, "trajetoria")
    ok("“See this term” na História (o de hoje e os 2 de presidente)", await pg.locator("#trajetoria a.traj-ver-btn:has-text('See this term')").count() == 3)
    await ctx.close()


# ------------------------------------------------------------------ 3. senador que foi deputado, governador e prefeito
async def senador(nav):
    print("\n— 3. sen-5207 (senador; antes deputado federal, governador e prefeito) —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    vigia(pg)
    await abre(pg, "pessoa.html?id=sen-5207#propostas")
    ops = await opcoes(pg)
    ok("6 mandatos: senador (atual), governador 2019 e 2015, deputado 2011, prefeito 2009 e 2005",
       len(ops) == 6 and "Senador" in ops[0] and "(atual)" in ops[0] and "Governador" in ops[1] and "Deputado federal" in ops[3] and "Prefeito · Murici, AL" in ops[4], " | ".join(ops))
    await escolhe_teclado(pg, "2011", "**mandato=dep-2011**")
    ok("deputado 2011–2015: as 9 propostas da Câmara", await n_props(pg) == 9, f"{await n_props(pg)}")
    await abre(pg, "pessoa.html?id=sen-5207&mandato=gov-2015#sobre", 1200)
    e = await estado(pg)
    t = await texto(pg, "#sobre")
    ok("governador 2015–2018: faixa, eleito em 2014, partido da época (PMDB) e o aviso de que as datas são as do mandato",
       "Governador (Alagoas), 2015 a 2018" in (e["faixa"] or "") and "2014" in t and "PMDB" in t and "O site não tem o dia" in t, e["faixa"])
    ok("governador: abas Quem é, História, O que propôs, Leis e vetos, Fontes", e["abas"] == ["sobre", "trajetoria", "propostas", "leis", "fontes"], ",".join(e["abas"]))
    await aba(pg, "propostas")
    t = await texto(pg, "#propostas")
    ok("“O que propôs” do governador: o site não reúne, com o site oficial da Assembleia", "não reúne as propostas que o governo do estado" in t and
       await pg.locator("#propostas a[href*='al.al.leg.br']").count() >= 1, t[:120].replace("\n", " "))
    await abre(pg, "pessoa.html?id=sen-5207&mandato=pref-2009#propostas", 1200)
    t = await texto(pg, "#propostas")
    ok("prefeito de Murici: a aba diz que o site não reúne o que a prefeitura mandou à Câmara", "prefeitura mandou à Câmara Municipal" in t, t[:100].replace("\n", " "))
    await ctx.close()


# ------------------------------------------------------------------ 4. deputada reeleita: a lista de hoje deixa de misturar mandatos
async def deputada(nav):
    print("\n— 4. dep-178866 (deputada federal em 3 legislaturas) —")
    p = pessoa("dep-178866")
    l = p["propostas"]["lista"]
    n57, n56, n55 = len(entre(l, "2023-02-01", "2027-01-31")), len(entre(l, "2019-02-01", "2023-01-31")), len(entre(l, "2015-02-01", "2019-01-31"))
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    vigia(pg)
    await abre(pg, "pessoa.html?id=dep-178866#propostas")
    t = await texto(pg, "#propostas .muted")
    ok(f"hoje: só as {n57} propostas do mandato de hoje (antes: as {len(l)} de todos os mandatos juntas)", await n_props(pg) == n57, f"{await n_props(pg)}")
    ok("o texto diz “no mandato de 2023 a 2027”", "no mandato de 2023 a 2027" in t, t[:100])
    outros = await texto(pg, "#propostas .aviso.azul")
    ok("“outros documentos” dizem que somam todos os mandatos na Câmara", "somando todos os mandatos na Câmara" in outros, outros[:100])
    ops = await opcoes(pg)
    ok("8 mandatos: deputada (3), prefeita (2), deputada estadual, vereadora (2)", len(ops) == 8 and sum("Deputada federal" in o for o in ops) == 3 and
       sum("Prefeita" in o for o in ops) == 2 and sum("Vereadora" in o for o in ops) == 2 and any("Deputada estadual" in o for o in ops), " | ".join(ops))
    await escolhe_teclado(pg, "2019 a 2023", "**mandato=dep-2019**")
    ok(f"2019–2023: as {n56} propostas daquela legislatura (do próprio perfil, filtradas pelas datas)", await n_props(pg) == n56, f"{await n_props(pg)}")
    ok("mandato antigo: os outros documentos só com o link da lista oficial (sem número somado)", "lista oficial" in await texto(pg, "#propostas .aviso.azul") and
       "somando" not in await texto(pg, "#propostas"))
    await abre(pg, "pessoa.html?id=dep-178866&mandato=dep-2015#propostas", 1200)
    ok(f"2015–2019: as {n55} propostas", await n_props(pg) == n55, f"{await n_props(pg)}")
    await aba(pg, "trajetoria")
    curto = await pg.locator("#trajetoria li[data-mandato='dep-2019'] .traj-fez-curto").inner_text()
    ok("a História conta o mesmo número da lista filtrada", f"{n56:,}".replace(",", ".") in curto, curto[:80])
    await ctx.close()


# ------------------------------------------------------------------ 5. deputado estadual, prefeito, vereador e eleito de 2026
async def regionais(nav):
    print("\n— 5. deputado estadual, prefeito, vereador e eleito de 2026 —")
    ctx = await ctx_novo(nav, viewport={"width": 1366, "height": 768})
    pg = await ctx.new_page()
    vigia(pg)
    # deputado estadual de SP que foi vereador de São Paulo
    await abre(pg, "pessoa.html?id=dest-SP-250001610141")
    ops = await opcoes(pg)
    ok("dest-SP: mandatos de deputado estadual e de vereador de São Paulo", ops and "(atual)" in ops[0] and any("Vereador · São Paulo, SP" in o for o in ops) and
       any(o.startswith("1995 a 1999") for o in ops), " | ".join(ops))
    await escolhe_teclado(pg, "2017 a 2020", "**mandato=ver-2017**")
    e = await estado(pg)
    ok("vereador 2017–2020: faixa com a cidade", "Vereador (São Paulo, SP), 2017 a 2020" in (e["faixa"] or ""), e["faixa"])
    await aba(pg, "propostas")
    t = await texto(pg, "#propostas")
    ok("“O que propôs”: o site só tem o mandato de hoje das Câmaras Municipais; link oficial da Câmara de São Paulo",
       "Câmaras Municipais no mandato de hoje" in t and await pg.locator("#propostas .links-onde a").count() >= 1, t[:90].replace("\n", " "))
    await aba(pg, "votacoes")
    ok("“Como votou” do vereador: a aba diz que o site não tem", "só tem as votações das Câmaras Municipais no mandato de hoje" in await texto(pg, "#votacoes"))
    # prefeito que foi vereador
    await abre(pg, "pessoa.html?id=pref-3105202")
    ops = await opcoes(pg)
    ok("pref-3105202: prefeito (2) e vereador (3)", len(ops) == 5 and "Prefeito" in ops[0] and sum("Vereador" in o for o in ops) == 3, " | ".join(ops))
    await abre(pg, "pessoa.html?id=pref-3105202&mandato=ver-2009#sobre", 1200)
    t = await texto(pg, "#sobre")
    ok("vereador 2009–2012: partido da época (PT) e votos", "PT" in t and "155 votos" in t, t[:150].replace("\n", " "))
    # vereador com 7 mandatos
    await abre(pg, "pessoa.html?id=ver-1500347-140002038381")
    ops = await opcoes(pg)
    ok("ver-1500347: 7 mandatos de vereador", len(ops) == 7 and all("Vereador" in o for o in ops), str(len(ops)))
    await abre(pg, "pessoa.html?id=ver-1500347-140002038381&mandato=ver-2005#sobre", 1200)
    t = await texto(pg, "#sobre")
    ok("vereador 2005–2008: o nome na urna e o partido da época estão na ficha do mandato", "PSDB" in t, t[:150].replace("\n", " "))
    # publica-r15: com os dados de 4/11, Léo Prates (e26-BA-50002532504) é deputado federal hoje (dep-80815) e o robô ligou o
    # perfil e26- ao de hoje; o caso "eleito de 2026 sem cargo hoje, com mandatos antigos" passou para Perpétua Almeida
    await abre(pg, "pessoa.html?id=e26-BA-50002532504")
    ok("e26- de quem tem cargo hoje leva ao perfil de hoje", "id=dep-80815" in pg.url, pg.url)
    # eleito de 2026 sem posse: o "hoje" é a eleição; os outros, os mandatos exercidos
    await abre(pg, "pessoa.html?id=e26-AC-10002538358")
    e = await estado(pg)
    ops = await opcoes(pg)
    ok("e26: a 1ª opção é a eleição de 2026 (com a posse), sem faixa", e["faixa"] is None and ops and "eleita em 2026" in ops[0] and "posse" in ops[0], ops[0] if ops else "")
    ok("e26: depois, os 4 mandatos de deputada federal e o de vereadora", len(ops) == 6 and ops[1].startswith("2019 a 2023 – Deputada federal")
       and sum("Deputada federal" in o for o in ops[1:]) == 4 and "Vereadora" in ops[5], " | ".join(ops))
    h = 0x811c9dc5  # o balde: FNV-1a do id, como no js/trajetoria.js
    for b in "e26-AC-10002538358".encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xffffffff
    tr = json.loads((RAIZ / "dados" / "trajetoria" / f"{h % 256:02x}.json").read_text(encoding="utf-8"))["pessoas"]["e26-AC-10002538358"]["it"]
    ms = [(x[7] or {}).get("m") if isinstance(x, list) and len(x) > 7 and isinstance(x[7], dict) else (x.get("m") if isinstance(x, dict) else None) for x in tr]
    fez = next(((m.get("fez") or {}).get("prop") for m in ms if m and m.get("casa") == "camara" and str(m.get("i", "")).startswith("2019")), None)
    await escolhe_teclado(pg, "2019 a 2023", "**mandato=dep-2019**")
    e = await estado(pg)
    await aba(pg, "propostas")
    n = await n_props(pg)
    ok("e26 → deputada 2019–2023: faixa e a lista da Câmara daquele mandato (o número da História)",
       "Deputada federal (Acre), 2019 a 2023" in (e["faixa"] or "") and fez and n == fez, f"{n} na lista, {fez} na História")
    await pg.locator("#faixa-mandato a.fm-hoje").click()
    await pg.wait_for_url(lambda u: "mandato=" not in u, timeout=15000)
    await pg.wait_for_timeout(1200)
    ok("e26: “Voltar para hoje” volta para a eleição de 2026", (await estado(pg))["faixa"] is None)
    # quem só tem um mandato não tem seletor
    await abre(pg, "pessoa.html?id=min-casa-civil")
    ok("ministro (um cargo só): sem seletor", await pg.locator("#mp-campo").count() == 0)
    await ctx.close()


# ------------------------------------------------------------------ 6. celular (toque), 320 px e o "◀ Voltar" até a lista
async def celular(nav):
    print("\n— 6. celular: toque, 320 px e o “◀ Voltar” até a lista —")
    ctx = await ctx_novo(nav, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    vigia(pg)
    await abre(pg, "brasil.html#executivo", 1200)
    card = pg.locator('a[href*="id=pres-lula"]').first
    await card.scroll_into_view_if_needed()
    await card.tap()
    await pagina_inteira(pg)  # site-d-r14: o cartão grande abre a gaveta; o perfil fica no “Ver a página inteira”
    await pg.wait_for_url("**id=pres-lula**", timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1000)
    await pg.locator("#mp-campo").scroll_into_view_if_needed()
    await pg.locator("#mp-campo").tap()
    await pg.wait_for_timeout(700)
    aberto = await pg.locator("#mp-campo[aria-expanded=true]").count()
    ok("toque no seletor abre a lista", aberto == 1)
    await pg.locator("#mp-campo-lista [role=option]", has_text="2007 a 2010").tap()
    await pg.wait_for_url("**mandato=pres-2007**", timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    e = await estado(pg)
    ok("toque numa opção abre o mandato (faixa “Presidente, 2007 a 2010”)", "Presidente, 2007 a 2010" in (e["faixa"] or ""), e["faixa"])
    ok("390 px: sem rolar para os lados", e["larg"] <= 1, str(e["larg"]))
    # troca de novo pela História e volta para a lista de uma vez
    await aba(pg, "trajetoria")
    b = pg.locator("#trajetoria a.traj-ver-btn[data-mandato='dep-1987']")
    await b.scroll_into_view_if_needed()
    await b.tap()
    await pg.wait_for_url("**mandato=dep-1987**", timeout=15000)
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(1200)
    await pg.locator("#voltar-lista").tap()
    await pg.wait_for_url("**brasil.html**", timeout=15000)
    await pg.wait_for_timeout(800)
    ok("“◀ Voltar” leva de volta à lista do Brasil de uma vez, depois de trocar de mandato duas vezes", "brasil.html" in pg.url, pg.url.split("/")[-1])
    await ctx.close()
    ctx = await ctx_novo(nav, viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    vigia(pg)
    largas = []
    for u in ("pessoa.html?id=pres-lula", "pessoa.html?id=pres-lula&mandato=dep-1987", "pessoa.html?id=sen-5207&mandato=gov-2015", "pessoa.html?id=dep-178866&mandato=dep-2019"):
        for lang in ("pt", "en"):
            for a in ("sobre", "propostas", "votacoes", "trajetoria"):
                await abre(pg, f"{u}&lang={lang}#{a}", 500)
                if (await estado(pg))["larg"] > 1:
                    largas.append(f"{u} {lang} {a}")
    ok("320 px: perfis de hoje e de mandatos antigos (pt e en, 4 abas cada) sem rolar para os lados", not largas, ", ".join(largas))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        for f in (lula, ingles, senador, deputada, regionais, celular):
            try:
                await f(nav)
            except Exception as e:  # noqa: BLE001
                ok(f"{f.__name__}: terminou sem erro", False, repr(e)[:300])
        print("\n— geral —")
        ok("nenhum pedido a outro servidor (além das fotos)", not FORA, ", ".join(sorted(FORA)))
        ok("nenhum erro de JavaScript", not ERROS, " | ".join(ERROS[:3]))
        await nav.close()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} conferências passaram")
    sys.exit(0 if n == len(RES) else 1)


if __name__ == "__main__":
    asyncio.run(main())
