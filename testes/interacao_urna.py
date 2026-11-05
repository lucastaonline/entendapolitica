"""Testes da parada 10 do Mapa da Política ("A urna eletrônica por dentro"), com Playwright + Edge. Precisa do servidor em 8770.

- Mapa: 10 placas, nenhum lote encavalado, a placa 10 visível (computador, 390 px e 320 px), a lista com as 10 paradas,
  o progresso de quem já tinha feito as 9 paradas e o fim do mapa ("visitou as 10 paradas").
- A parada 10 abre pelo mapa (teclado) e pelo botão "Ver a urna por dentro" da parada 7 (português e inglês).
- O caminho simples (o padrão, ≈10 slides, como as outras paradas) e a parte avançada ("avancado" no JSON): o botão
  "Quer ir a fundo na parte técnica?" no fim do caminho simples abre a parte avançada, com endereço próprio
  (#parte-10-avancado, -avancado-2...), contagem própria, a faixa "Parte avançada" e o botão de voltar ao caminho simples;
  os endereços antigos (#parte-10-15, #parte-10-22...) levam aos slides novos.
- Todos os slides pelo teclado (nas duas trilhas); os joguinhos: o caminho do voto, o lacre digital (o hash da página confere
  com o SHA-256 e o SHA-512 do Python, e uma letra trocada muda o lacre), o boletim de exemplo e os quizzes.
- Inglês sem palavras em português soltas (em todos os slides das duas trilhas), 320 px sem rolar para os lados,
  "menos movimento", axe-core nos estados dos joguinhos e nenhum erro de JavaScript.
Uso: python testes/interacao_urna.py"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("EP_BASE", "http://127.0.0.1:8770/")  # outro servidor: EP_BASE=http://127.0.0.1:8772/
RAIZ = Path(__file__).resolve().parent.parent
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
ERROS = []

PT = json.loads((RAIZ / "conteudo" / "entenda" / "parte-10.json").read_text(encoding="utf-8"))
EN = json.loads((RAIZ / "conteudo" / "entenda" / "en" / "parte-10.json").read_text(encoding="utf-8"))
N = len(PT["slides"]) + 1  # caminho simples + o slide final da parada
AV = PT["avancado"]["slides"]
NA = len(AV) + 1  # parte avançada (começa com a sua abertura) + o slide final dela
assert len(EN["slides"]) == len(PT["slides"]) and len(EN["avancado"]["slides"]) == len(AV), "o inglês tem de ter a mesma estrutura"


def acha(pred, lista=None):
    return next(i for i, s in enumerate(PT["slides"] if lista is None else lista) if pred(s))


I_CV = acha(lambda s: s.get("id") == "caminho-voto")
I_LACRE = acha(lambda s: s.get("id") == "lacre-digital", AV)  # na parte avançada
I_CB = acha(lambda s: s.get("id") == "confira-boletim")
QUIZ = {i: s["certa"] for i, s in enumerate(PT["slides"]) if s["tipo"] == "quiz"}
QUIZ_AV = {i: s["certa"] for i, s in enumerate(AV) if s["tipo"] == "quiz"}
ETAPAS = len(PT["slides"][I_CV]["etapas"])
LINHA_ERRADA = next(k for k, l in enumerate(PT["slides"][I_CB]["linhas"]) if l["papel"] != l["site"])
I_FRAUDE = acha(lambda s: (s.get("titulo") or "").startswith("O que alguém teria de vencer"))


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def sha(txt, algo="sha256"):
    return hashlib.new(algo, txt.encode("utf-8")).hexdigest()


def ouve(pg, rotulo):
    pg.on("pageerror", lambda e: ERROS.append(f"{rotulo}: {e}"))
    pg.on("console", lambda m: ERROS.append(f"{rotulo}: console.error: {m.text}") if m.type == "error" else None)


# palavras que só existem em português, fora de elementos com lang="pt-BR" (a mesma régua de testes/verifica_texto.py)
JS_PT = r"""(raiz) => {
  const PT = /(?<!\p{L})(não|é|para|com|que|uma|foi|está|ainda|outra|outro|mais|como|quem|sobre|também|você|anos|eleit[oa]s?|deputad[oa]s?|senador[a]?|vereador[a]?|prefeit[oa]|governador[a]?|projeto|proposta|propostas|votaç[aã]o|votações|cargo|mandato|partido|cidade|estado|fonte|fontes|ver mais|aprovad[oa]|arquivad[oa]|discussão|junto|desde|até|pelo|pela|nos|nas|ao|aos|à|às)(?!\p{L})/iu;
  const QUEBRADO = /\b(undefined|null|NaN)\b|\[object/;
  const achados = [];
  for (const base of document.querySelectorAll(raiz)) {
    const w = document.createTreeWalker(base, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      const t = n.textContent.replace(/\s+/g, " ").trim();
      if (!t) continue;
      const el = n.parentElement;
      if (!el || el.closest("script,style,[hidden],[aria-hidden=true]")) continue;
      if (QUEBRADO.test(t)) achados.push("QUEBRADO: " + t.slice(0, 120));
      const l = el.closest("[lang]");
      if (l && /^pt/i.test(l.getAttribute("lang"))) continue;
      const m = PT.exec(t.replace(/(?:https?:\/\/)?[\w-]+(?:\.[\w-]+)+(?:\/\S*)?/g, " "));
      if (m) achados.push(m[0] + " :: " + t.slice(0, 120));
    }
    for (const el of base.querySelectorAll("[aria-label],[title],[alt]")) {
      for (const a of ["aria-label", "title", "alt"]) {
        const v = el.getAttribute(a);
        const l = el.closest("[lang]");
        if (!v || (l && /^pt/i.test(l.getAttribute("lang")))) continue;
        if (/(?<!\p{L})(não|é|para|com|que|uma|você|página|voltar)(?!\p{L})/iu.test(v)) achados.push(a + ": " + v.slice(0, 120));
      }
    }
  }
  return achados;
}"""

# nada sai da tela para os lados no slide aberto (o slide corta o que passa, então a conta é feita elemento por elemento;
# o cubo 3D com o número da parada, enfeite de todas as aberturas, passa uns 3 px da borda em todas as paradas e fica de fora)
JS_LARGURA = """() => {
  const s = document.querySelector('.slide.ativo'), W = innerWidth;
  const fora = [...s.querySelectorAll('*')].filter(e => {
    if (e.closest('.sr, [hidden], .formas, .cubo-num')) return false;
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (r.right > W + 1 || r.left < -1);
  }).slice(0, 4).map(e => e.tagName + '.' + String(e.className).slice(0, 30) + ' ' + Math.round(e.getBoundingClientRect().left) + '..' + Math.round(e.getBoundingClientRect().right));
  scrollTo(300, 0);
  const sx = scrollX;
  const nav = document.getElementById('btn-proximo').getBoundingClientRect();
  return { fora, sx, rol: s.scrollWidth - s.clientWidth, nav: Math.round(nav.right) <= W + 1 };
}"""


async def termina_animacoes(pg):
    # as animações de entrada (peças que sobem, páginas que viram) terminam na hora: mede e audita o estado final, o que a pessoa vê
    await pg.evaluate("""() => { for (const a of document.getAnimations()) { try { const t = a.effect && a.effect.getComputedTiming(); if (t && isFinite(t.endTime)) a.finish(); } catch (e) {} } }""")


async def axe(pg, rotulo):
    if not AXE.exists():
        ok(f"axe-core: {rotulo}", True, "axe-core não encontrado; pulei")
        return
    await termina_animacoes(pg)
    if not await pg.evaluate("!!window.axe"):
        await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                          resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + '): ' + (v.nodes[0].target || []).join(' '));
    }""")
    ok(f"axe-core sem problemas: {rotulo}", not v, "; ".join(v)[:300])


SEM_TEXTO = {"fontes", "ic", "tipo", "id", "ilustracao", "emoji", "quem"}


def tamanho(slides):
    """caracteres do texto dos slides (a mesma conta do textoDoSlide do js/entenda.js)"""
    def anda(v):
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [x for y in v for x in anda(y)]
        if isinstance(v, dict):
            return [x for k, y in v.items() if k not in SEM_TEXTO for x in anda(y)]
        return []
    return sum(len(" ".join(anda(s))) for s in slides)


async def confere_slide(pg, i, total, s, prefixo, fim_url):
    cab = await pg.locator(".slide.ativo h1, .slide.ativo h2").count()
    fontes = await pg.locator(".slide.ativo .pe-slide [data-fontes]").count()
    cont = await pg.locator("#contador").inner_text()
    ok(f"{prefixo}slide {i + 1} de {total} abre pela seta → (título{' e fontes' if s else ''}; {fim_url})",
       cab > 0 and (fontes == 1 if s else True) and pg.url.endswith(fim_url) and cont == f"{i + 1} de {total}", f"{pg.url.split('#')[1]} | {cont}")
    await termina_animacoes(pg)
    lg = await pg.evaluate(JS_LARGURA)
    if lg["fora"] or lg["rol"] > 1:
        ok(f"{prefixo}slide {i + 1}: nada passa da largura da tela no computador", False, str(lg))
    if s and s["tipo"] == "numeros":
        cabe = await pg.evaluate("[...document.querySelectorAll('.slide.ativo .n-val')].every(v => v.getBoundingClientRect().width <= v.closest('.face-num').getBoundingClientRect().width)")
        ok(f"{prefixo}slide {i + 1}: os números grandes cabem nos cartões", cabe)


async def slide_ativo(pg):
    return await pg.evaluate("(() => { const s = document.querySelector('.slide.ativo'); return s ? +s.getAttribute('data-i') : -1; })()")


async def vai_para(pg, i):
    await pg.wait_for_function("i => { const s = document.querySelector('.slide.ativo'); return s && +s.getAttribute('data-i') === i; }", arg=i, timeout=8000)


async def proximo(pg):
    # o foco volta para o slide (no campo de texto, as setas mexem no texto e não passam o slide)
    i = await slide_ativo(pg)
    await pg.focus(".slide.ativo .miolo")
    await pg.keyboard.press("ArrowRight")
    await vai_para(pg, i + 1)


async def tecla(pg, sel, tecla_="Enter"):
    await pg.locator(sel).first.focus()
    await pg.keyboard.press(tecla_)


async def codigo(pg):
    return (await pg.locator(".slide.ativo .lacre-codigo:not(.g)").inner_text()).replace(" ", "").replace("\n", "")


async def espera_codigo(pg, h):
    await pg.wait_for_function("h => { const c = document.querySelector('.slide.ativo .lacre-codigo:not(.g)'); return c && c.textContent.replace(/\\s/g, '') === h; }", arg=h, timeout=6000)


async def responde_quiz(pg, i, rotulo, quiz=None):
    await tecla(pg, f".slide.ativo .opcao[data-op=\"{(quiz or QUIZ)[i]}\"]")
    await pg.wait_for_timeout(250)
    certa = await pg.locator(".slide.ativo .opcao.certa").count()
    resp = await pg.locator(".slide.ativo .resposta.ok").count()
    ok(f"{rotulo}: quiz do slide {i + 1} respondido pelo teclado", certa == 1 and resp == 1)


async def joga_caminho(pg, rotulo, auto=True):
    box = ".slide.ativo [data-cv]"
    pos = lambda: pg.locator(box).get_attribute("data-pos")
    balao = (await pg.locator(".slide.ativo .cv-balao").inner_text()).lower()
    ok(f"{rotulo}: caminho do voto começa na etapa 1 de {ETAPAS}", await pos() == "0" and f"1 {'de' if 'lang=en' not in pg.url else 'of'} {ETAPAS}" in balao
       and await pg.locator(".slide.ativo [data-cv-ant]").is_disabled(), balao.split("\n")[0])
    await pg.locator(".slide.ativo [data-cv-prox]").focus()
    for _ in range(ETAPAS - 1):
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(60)
    corrente = await pg.locator(".slide.ativo .cv-casa[aria-current='step']").get_attribute("data-cv-ir")
    foco = await pg.evaluate("document.activeElement && document.activeElement.hasAttribute('data-cv-zera')")
    ok(f"{rotulo}: Enter em “Próxima etapa” anda até a etapa {ETAPAS} (aria-current) e o foco vai para “Recomeçar”",
       await pos() == str(ETAPAS - 1) and corrente == str(ETAPAS - 1) and await pg.locator(".slide.ativo [data-cv-prox]").is_disabled() and foco)
    await tecla(pg, ".slide.ativo [data-cv-ant]")
    ok(f"{rotulo}: “Etapa anterior” volta uma", await pos() == str(ETAPAS - 2))
    await tecla(pg, ".slide.ativo .cv-casa[data-cv-ir='4']", " ")
    await pg.wait_for_timeout(900)
    fx = await pg.evaluate("""() => { const f = document.querySelector('.slide.ativo .cv-ficha').getBoundingClientRect(),
      c = document.querySelector('.slide.ativo .cv-casa.aqui').getBoundingClientRect(); return Math.abs((f.left + f.width / 2) - (c.left + c.width / 2)); }""")
    ok(f"{rotulo}: Espaço numa casa pula para ela e a ficha 🗳️ fica em cima dela", await pos() == "4" and fx < 8, f"{fx:.1f}px")
    if auto:
        await tecla(pg, ".slide.ativo [data-cv-auto]")
        ok(f"{rotulo}: “Ver o caminho todo” fica apertado (aria-pressed)", await pg.locator(".slide.ativo [data-cv-auto]").get_attribute("aria-pressed") == "true")
        await pg.wait_for_function("() => +document.querySelector('.slide.ativo [data-cv]').getAttribute('data-pos') >= 5", timeout=7000)
        await tecla(pg, ".slide.ativo [data-cv-auto]")
        ok(f"{rotulo}: a animação anda sozinha e pausa", await pg.locator(".slide.ativo [data-cv-auto]").get_attribute("aria-pressed") == "false")
    await tecla(pg, ".slide.ativo [data-cv-zera]")
    ok(f"{rotulo}: “Recomeçar” volta para a etapa 1", await pos() == "0")


async def joga_lacre(pg, rotulo, inicial):
    ta = pg.locator(".slide.ativo .lacre-txt")
    txt = await ta.input_value()
    ok(f"{rotulo}: o texto inicial do lacre é o do conteúdo", txt == inicial, txt)
    await espera_codigo(pg, sha(txt))
    ok(f"{rotulo}: o lacre (SHA-256) confere com o do Python", await codigo(pg) == sha(txt))
    await tecla(pg, ".slide.ativo [data-lacre-guarda]")
    await pg.wait_for_timeout(200)
    ok(f"{rotulo}: “Guardar este lacre” mostra o lacre guardado", await pg.locator(".slide.ativo .lacre-guardado").is_visible())
    await tecla(pg, ".slide.ativo [data-lacre-troca]")
    novo = await ta.input_value()
    dif = sum(1 for a, b in zip(txt, novo) if a != b)
    await espera_codigo(pg, sha(novo))
    mud = sum(1 for a, b in zip(sha(txt), sha(novo)) if a != b)
    status = await pg.locator(".slide.ativo .lacre-status").inner_text()
    marcados = await pg.locator(".slide.ativo .lacre-codigo:not(.g) mark").count()
    ok(f"{rotulo}: trocar UMA letra muda o lacre inteiro ({mud} de 64 caracteres)", len(novo) == len(txt) and dif == 1 and mud > 40 and marcados > 0)
    ok(f"{rotulo}: o leitor de tela ouve que o lacre é diferente do guardado", await pg.locator(".slide.ativo .lacre-guardado.diferente").count() == 1
       and ("Diferente" in status or "Different" in status), status[:100])
    # escrever no campo: as setas e as letras ficam no texto (não passam o slide)
    await ta.focus()
    await pg.keyboard.press("End")
    await pg.keyboard.press("ArrowRight")
    await pg.keyboard.type(" 123", delay=15)
    novo2 = await ta.input_value()
    await espera_codigo(pg, sha(novo2))
    ok(f"{rotulo}: digitar recalcula o lacre e não passa o slide", novo2 == novo + " 123" and await slide_ativo(pg) == I_LACRE)
    await tecla(pg, ".slide.ativo [data-lacre-algo='SHA-512']")
    await espera_codigo(pg, sha(novo2, "sha512"))
    ok(f"{rotulo}: SHA-512 (o tipo das listas do TSE) também confere com o Python (128 caracteres)",
       await codigo(pg) == sha(novo2, "sha512") and await pg.locator(".slide.ativo [data-lacre-algo='SHA-512']").get_attribute("aria-pressed") == "true")
    await tecla(pg, ".slide.ativo [data-lacre-algo='SHA-256']")
    await espera_codigo(pg, sha(novo2))


async def joga_boletim(pg, rotulo, en=False):
    s = (EN if en else PT)["slides"][I_CB]
    aviso = await pg.locator(".slide.ativo .cb-aviso").inner_text()
    ok(f"{rotulo}: o boletim diz claramente que é exemplo", ("EXAMPLE" if en else "EXEMPLO") in aviso and s["secao"]["municipio"] in await pg.locator(".slide.ativo .cb-bu").inner_text(), aviso)
    soma_p = sum(l["papel"] for l in s["linhas"])
    soma_s = sum(l["site"] for l in s["linhas"])
    tot_p = await pg.locator(".slide.ativo .cb-tab tfoot td").inner_text()
    tot_s = await pg.locator(".slide.ativo .cb-total b").inner_text()
    ok(f"{rotulo}: os totais do papel e do site são as somas das linhas", tot_p == str(soma_p) and tot_s == str(soma_s), f"{tot_p} × {tot_s}")
    certa = next(k for k, l in enumerate(s["linhas"]) if l["papel"] == l["site"])
    await tecla(pg, f".slide.ativo .cb-linha[data-cb-linha='{certa}']")
    ok(f"{rotulo}: uma linha igual diz “tente outra”", await pg.locator(".slide.ativo .cb-resp.nao").count() == 1
       and await pg.locator(f".slide.ativo .cb-linha[data-cb-linha='{certa}']").get_attribute("aria-pressed") == "true")
    await tecla(pg, f".slide.ativo .cb-linha[data-cb-linha='{LINHA_ERRADA}']")
    resp = await pg.locator(".slide.ativo .cb-resp").inner_text()
    l = s["linhas"][LINHA_ERRADA]
    ok(f"{rotulo}: achar a linha diferente marca o papel e o site", await pg.locator(".slide.ativo .cb-resp.ok").count() == 1 and str(l["papel"]) in resp and str(l["site"]) in resp
       and await pg.locator(".slide.ativo .cb-tab tr.achou").count() == 1 and await pg.locator(".slide.ativo .cb-total.achou").count() == 1, resp[:90])
    await tecla(pg, ".slide.ativo [data-cb-qr]")
    ok(f"{rotulo}: o botão do QR Code explica a cópia digital", await pg.locator(".slide.ativo .cb-resp.info").count() == 1)


async def fluxo_pt(nav):
    ctx = await nav.new_context(viewport={"width": 1280, "height": 860}, locale="pt-BR")
    pg = await ctx.new_page()
    ouve(pg, "pt")
    await pg.goto(BASE + "entenda.html?lang=pt", wait_until="networkidle")
    await pg.evaluate("localStorage.clear(); localStorage.setItem('ep-lang', 'pt')")
    await pg.reload(wait_until="networkidle")
    await pg.wait_for_timeout(2600)

    # 1. o mapa com 10 paradas
    n = await pg.locator(".lugar").count()
    rot = await pg.locator(".mundo").get_attribute("aria-label")
    prog = await pg.locator("#progresso-mapa").inner_text()
    ok("mapa tem 10 paradas, e os textos dizem 10", n == 10 and "10 paradas" in rot and prog.endswith("0/10")
       and "de 10 paradas" in await pg.locator("#progresso-mapa").get_attribute("aria-label"), f"{n} | {rot} | {prog}")
    lotes = await pg.evaluate("""() => [...document.querySelectorAll('.lugar')].map(l => [+l.dataset.n, parseFloat(l.style.getPropertyValue('--x')), parseFloat(l.style.getPropertyValue('--y'))])""")
    encav = [(a[0], b[0]) for k, a in enumerate(lotes) for b in lotes[k + 1:] if abs(a[1] - b[1]) < 220 and abs(a[2] - b[2]) < 220]
    ok("nenhum lote (220 × 220) encavala em outro", not encav, str(encav))
    placas = await pg.evaluate("""() => [...document.querySelectorAll('.lugar .placa')].map(p => { const r = p.getBoundingClientRect(); return [+p.closest('.lugar').dataset.n, r.left, r.top, r.right, r.bottom]; })""")
    sobre = [(a[0], b[0]) for k, a in enumerate(placas) for b in placas[k + 1:] if min(a[3], b[3]) - max(a[1], b[1]) > 1 and min(a[4], b[4]) - max(a[2], b[2]) > 1]
    ok("no computador, nenhuma placa cobre outra", not sobre, str(sobre))
    await confere_placa10(pg, "computador")
    await axe(pg, "mapa com 10 paradas (computador)")
    await pg.click("#ver-lista")
    await pg.wait_for_timeout(400)
    tit = await pg.locator('[role="dialog"]:visible').first.inner_text()
    nl = await pg.locator('[role="dialog"]:visible [data-abrir-parada]').count()
    ok("a lista do mapa mostra as 10 paradas", "As 10 paradas" in tit and nl == 10 and "A urna eletrônica por dentro" in tit, f"{nl} botões")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)

    # 2. abrir a parada 10 pelo mapa, com o teclado
    await pg.focus('.lugar[data-n="10"] .placa')
    await pg.keyboard.press("Enter")
    await pg.wait_for_function("document.body.classList.contains('modo-aula')", timeout=6000)
    await vai_para(pg, 0)
    await pg.wait_for_timeout(600)
    etq = await pg.locator(".slide.ativo .etiqueta").first.inner_text()
    ok("Enter na placa 10 abre a parada 10 (Parada 10 de 10)", pg.url.endswith("#parte-10") and "PARADA 10 DE 10" in etq.upper(), etq)
    ok("a abertura mostra a urna com o boletim saindo (modelo 3D)", await pg.locator(".slide.ativo .urna-boletim3d .bu-papel").count() == 1)

    # 3. o caminho simples: do tamanho das outras paradas, todos os slides pelo teclado, com os joguinhos
    outras = [tamanho(json.loads((RAIZ / f"conteudo/entenda/parte-{k}.json").read_text(encoding="utf-8"))["slides"]) for k in range(1, 10)]
    tam, tam_av = tamanho(PT["slides"]), tamanho(AV)
    ok(f"caminho simples: {len(PT['slides'])} slides (≈10, como as outras paradas, que têm 9 a 11)", 9 <= len(PT["slides"]) <= 11)
    ok(f"caminho simples: {tam} caracteres de texto, dentro do tamanho das outras paradas ({min(outras)} a {max(outras)}); a parte avançada tem {tam_av}",
       tam <= max(outras) and tam_av > tam)
    ok("caminho simples: abertura, explicações, joguinhos (caminho do voto e boletim), quizzes e o voto impresso",
       PT["slides"][0]["tipo"] == "abertura" and len(QUIZ) >= 2 and any(s["tipo"] == "historia" for s in PT["slides"]) and not any(s.get("pular") for s in PT["slides"]))
    ok("“O que alguém teria de vencer para fraudar?” está no caminho simples, com a avaliação atribuída ao TSE e as fontes (inclusive tse-lacracao-2026)",
       PT["slides"][I_FRAUDE]["texto"].startswith("Segundo o TSE") and "tse-lacracao-2026" in PT["slides"][I_FRAUDE]["fontes"])
    tit_av = " | ".join(s.get("titulo") or s.get("pergunta") or "" for s in AV)
    ok("a parte avançada tem a parte técnica (hash, assinatura, cadeia de confiança, RDV e log, QR Code, arquivos) e os detalhes que saíram do caminho simples",
       all(x in tit_av for x in ("lacre digital", "assinatura digital", "Cadeia de confiança", "RDV", "QR Code", "Onde baixar", "Teste Público", "Preparando", "2026", "Perguntas")), tit_av[:200])
    for i in range(1, N):
        await proximo(pg)
        await pg.wait_for_timeout(350)
        await confere_slide(pg, i, N, PT["slides"][i] if i < len(PT["slides"]) else None, "", f"#parte-10-{i + 1}")
        if i == I_CV:
            await joga_caminho(pg, "pt")
            await tecla(pg, ".slide.ativo [data-cv-prox]")
            await axe(pg, "caminho do voto")
        elif i == I_CB:
            await joga_boletim(pg, "pt")
            await axe(pg, "confira o boletim (achado)")
        elif i in QUIZ:
            await responde_quiz(pg, i, "pt")
            if i == max(QUIZ):
                await axe(pg, "quiz respondido")
    fim = await pg.locator(".slide.ativo").inner_text()
    feitos = await pg.evaluate("JSON.parse(localStorage.getItem('ep-mapa-feitos') || '{}')")
    ok("o último slide é o fim da parada e marca a parada 10 como feita", "Parada concluída" in fim and feitos.get("10") is True, str(feitos))
    bt = pg.locator('.slide.ativo .convite-avancado [data-acao="avancado"]')
    desc = await pg.locator("#" + (await bt.get_attribute("aria-describedby"))).inner_text()
    ok("no fim do caminho simples, o botão “Quer ir a fundo na parte técnica?” (com o que tem na parte avançada e quantas páginas)",
       await bt.count() == 1 and "Quer ir a fundo na parte técnica?" in await bt.inner_text() and f"({NA - 1} páginas)" in desc, desc[-60:])
    ok("o fim continua com a próxima parada e o mapa (quem não clica termina a parada como nas outras)",
       await pg.locator(".slide.ativo [data-proxima]").count() == 1 and await pg.locator('.slide.ativo [data-acao="mapa"]').count() == 1)
    await axe(pg, "fim do caminho simples, com o convite")

    # 4. a parte avançada: endereço, contagem e faixa próprios, todos os slides, os joguinhos e a volta
    await tecla(pg, '.slide.ativo [data-acao="avancado"]')
    await vai_para(pg, 0)
    await pg.wait_for_timeout(500)
    etq = await pg.locator(".slide.ativo .etiqueta").first.inner_text()
    ok("o botão abre a parte avançada: endereço próprio, contagem própria, “Parte avançada” no topo e na abertura",
       pg.url.endswith("#parte-10-avancado") and await pg.locator("#contador").inner_text() == f"1 de {NA}"
       and "Parte avançada" in await pg.locator("#nome-parte").inner_text() and "PARADA 10 · PARTE AVANÇADA" in etq.upper()
       and await pg.locator("#aula.trilha-avancada").count() == 1, f"{pg.url.split('#')[1]} | {etq}")
    ok("a abertura da parte avançada tem o botão de voltar ao caminho simples", await pg.locator('.slide.ativo [data-acao="simples"]').count() == 1)
    foco = await pg.evaluate("!!(document.activeElement && document.activeElement.closest('.slide.ativo'))")
    ok("o foco vai para o slide novo (leitor de tela)", foco)
    sem_faixa = []
    for i in range(1, NA):
        await proximo(pg)
        await pg.wait_for_timeout(350)
        s = AV[i] if i < len(AV) else None
        await confere_slide(pg, i, NA, s, "parte avançada: ", f"#parte-10-avancado-{i + 1}")
        if s:
            fx = pg.locator(".slide.ativo .faixa-avancada")
            if not (await fx.count() == 1 and "PARTE AVANÇADA" in (await fx.inner_text()).upper() and await fx.locator('[data-acao="simples"]').count() == 1):
                sem_faixa.append(i + 1)
        if i == I_LACRE:
            await joga_lacre(pg, "pt", AV[I_LACRE]["inicial"])
            await axe(pg, "lacre digital (guardado e comparado)")
        elif i in QUIZ_AV:
            await responde_quiz(pg, i, "pt (parte avançada)", QUIZ_AV)
    ok(f"a faixa “Parte avançada” e o botão de voltar estão em todos os {len(AV) - 1} slides da parte avançada (fora a abertura)", not sem_faixa, str(sem_faixa))
    fim = await pg.locator(".slide.ativo").inner_text()
    ok("o fim da parte avançada: concluída, voltar ao caminho simples, próxima parada e mapa",
       "Parte avançada concluída" in fim and await pg.locator('.slide.ativo [data-acao="simples"]').count() == 1
       and await pg.locator(".slide.ativo [data-proxima]").count() == 1 and await pg.locator('.slide.ativo [data-acao="mapa"]').count() == 1, fim[:80].replace("\n", " "))
    await axe(pg, "fim da parte avançada")
    await tecla(pg, '.slide.ativo [data-acao="simples"]')
    await vai_para(pg, N - 1)
    await pg.wait_for_timeout(300)
    ok("“Voltar ao caminho simples” volta ao fim do caminho simples, de onde a pessoa veio (endereço e contagem do caminho simples)",
       pg.url.endswith(f"#parte-10-{N}") and await pg.locator("#contador").inner_text() == f"{N} de {N}"
       and await pg.locator("#aula.trilha-avancada").count() == 0 and "Parte avançada" not in await pg.locator("#nome-parte").inner_text())
    # o menu ☰ Páginas também leva de uma trilha à outra
    await pg.click("#btn-menu")
    await pg.wait_for_timeout(300)
    dlg = pg.locator('[role="dialog"]:visible').first
    ok("menu ☰ do caminho simples: as páginas do caminho simples e o botão da parte avançada",
       await dlg.locator("[data-ir]").count() == N and await dlg.locator('[data-acao="avancado"]').count() == 1)
    await dlg.locator('[data-acao="avancado"]').click()
    await vai_para(pg, 0)
    await pg.click("#btn-menu")
    await pg.wait_for_timeout(300)
    dlg = pg.locator('[role="dialog"]:visible').first
    ok("menu ☰ da parte avançada: “Páginas da parte avançada”, as páginas dela e o botão de voltar",
       "Páginas da parte avançada" in await dlg.inner_text() and await dlg.locator("[data-ir]").count() == NA and await dlg.locator('[data-acao="simples"]').count() == 1)
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    # endereço direto da parte avançada (recarregar a página) e voltar ao caminho simples pela faixa
    await pg.goto("about:blank")
    await pg.goto(BASE + f"entenda.html?lang=pt#parte-10-avancado-{I_LACRE + 1}", wait_until="networkidle")
    await vai_para(pg, I_LACRE)
    ok("endereço direto (#parte-10-avancado-N) abre a parte avançada no slide certo", await pg.locator("#contador").inner_text() == f"{I_LACRE + 1} de {NA}"
       and await pg.locator(".slide.ativo [data-lacre]").count() == 1)
    await tecla(pg, '.slide.ativo .faixa-avancada [data-acao="simples"]')
    await vai_para(pg, 0)
    ok("quem chegou direto na parte avançada volta para o começo do caminho simples", pg.url.endswith("#parte-10") and await pg.locator("#contador").inner_text() == f"1 de {N}")
    # endereços antigos (de quando a parada tinha 28 slides) levam aos slides novos
    antigos = PT["enderecos_antigos"]
    ok("os endereços antigos que passam do fim do caminho simples (até o fim antigo, 29) estão todos mapeados", all(str(k) in antigos for k in range(N + 1, 30)), str(antigos))
    for velho, texto in ((15, "O que alguém teria de vencer"), (22, "Hash e assinatura digital"), (27, "Onde baixar os arquivos"), (29, "Parada concluída")):
        alvo = antigos[str(velho)]
        trilha, k = ("-avancado", int(alvo.split("-")[1]) - 1) if alvo.startswith("avancado-") else ("", int(alvo) - 1)
        await pg.goto("about:blank")
        await pg.goto(BASE + f"entenda.html?lang=pt#parte-10-{velho}", wait_until="networkidle")
        await vai_para(pg, k)
        txt = await pg.locator(".slide.ativo").inner_text()
        ok(f"endereço antigo #parte-10-{velho} leva a #parte-10{trilha}-{k + 1} (“{texto}”)", texto in txt and pg.url.endswith(f"#parte-10{trilha}-{k + 1}"), pg.url.split("#")[1])
    # o Esc e o Voltar do navegador fecham a parada também na parte avançada
    await pg.goto("about:blank")
    await pg.goto(BASE + "entenda.html?lang=pt#parte-10-avancado-3", wait_until="networkidle")
    await vai_para(pg, 2)
    await pg.keyboard.press("Escape")
    await pg.wait_for_function("!document.body.classList.contains('modo-aula')", timeout=6000)
    ok("Esc na parte avançada volta ao mapa (e o endereço fica sem #parte)", "#parte" not in pg.url and await pg.locator("#aula.trilha-avancada").count() == 0)

    # 5. quem já tinha feito as 9 paradas continua com as 9 marcadas; a 10 vira a próxima sugerida; o fim do mapa conta 10
    await pg.goto("about:blank")
    await pg.goto(BASE + "entenda.html?lang=pt", wait_until="networkidle")
    await pg.evaluate("localStorage.setItem('ep-mapa-feitos', JSON.stringify({1: true, 2: true, 3: true, 4: true, 5: true, 6: true, 7: true, 8: true, 9: true}))")
    await pg.reload(wait_until="networkidle")
    await pg.wait_for_timeout(1500)
    bolha = await pg.locator("#bolha").inner_text()
    ok("quem fez as 9: 9 placas com estrela, a 10 é a próxima e a Coruja conta 9 de 10", await pg.locator(".lugar.feito").count() == 9
       and await pg.locator('.lugar.proximo[data-n="10"]').count() == 1 and "9 de 10" in bolha and "parada 10" in bolha
       and (await pg.locator("#progresso-mapa").inner_text()).endswith("9/10"), bolha.replace("\n", " ")[:120])
    await pg.goto("about:blank")
    await pg.goto(BASE + f"entenda.html?lang=pt#parte-10-{N}", wait_until="networkidle")
    await vai_para(pg, N - 1)
    fim = await pg.locator(".slide.ativo").inner_text()
    ok("ao terminar a 10ª, o fim fala do mapa completo (e da urna)", "completou o Mapa da Política" in fim and "urna eletrônica" in fim, fim[:80].replace("\n", " "))
    ok("o fim do mapa completo também tem o botão da parte avançada", await pg.locator('.slide.ativo .convite-avancado [data-acao="avancado"]').count() == 1)
    await pg.keyboard.press("Escape")
    await pg.wait_for_function("!document.body.classList.contains('modo-aula')", timeout=6000)
    await pg.wait_for_timeout(1200)
    bolha = await pg.locator("#bolha").inner_text()
    ok("a Coruja diz que a pessoa visitou as 10 paradas (e aparece o troféu)", "visitou as 10 paradas" in bolha
       and (await pg.locator("#progresso-mapa").inner_text()).endswith("10/10") and await pg.locator(".mapa-tela.todos-feitos").count() == 1, bolha[:80])

    # 6. o botão da parada 7 ("Como o voto é protegido") leva à parada 10
    await pg.evaluate("localStorage.removeItem('ep-mapa-feitos')")
    await pg.goto("about:blank")
    await pg.goto(BASE + "entenda.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    await pg.focus('.lugar[data-n="7"] .placa')
    await pg.keyboard.press("Enter")
    await vai_para(pg, 0)
    i7 = next(i for i, s in enumerate(json.loads((RAIZ / "conteudo/entenda/parte-7.json").read_text(encoding="utf-8"))["slides"]) if s.get("link", {}).get("url") == "entenda.html#parte-10")
    for _ in range(i7):
        await proximo(pg)
    a = pg.locator(".slide.ativo .link-slide a")
    href, txt = await a.get_attribute("href"), await a.inner_text()
    seta = await a.locator("span[aria-hidden='true']").last.inner_text()
    ok("parada 7, slide “Como o voto é protegido”: botão “Ver a urna por dentro ▶”", href == "entenda.html#parte-10" and "Ver a urna por dentro" in txt and seta == "▶", f"{href} | {txt.strip()}")
    await a.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_function("() => /#parte-10$/.test(location.hash) && document.querySelector('.slide.ativo') && document.querySelector('.slide.ativo').dataset.i === '0' && /10/.test(document.querySelector('.slide.ativo .etiqueta').textContent)", timeout=9000)
    ok("Enter no botão fecha a parada 7, o mapa voa e abre a parada 10", "PARADA 10 DE 10" in (await pg.locator(".slide.ativo .etiqueta").first.inner_text()).upper())
    await pg.go_back()
    await pg.wait_for_function("!document.body.classList.contains('modo-aula')", timeout=6000)
    await pg.wait_for_timeout(600)
    foco = await pg.evaluate("document.activeElement && document.activeElement.closest('.lugar') && document.activeElement.closest('.lugar').dataset.n")
    ok("o Voltar do navegador fecha a parada 10 e o foco fica na placa 10", foco == "10", str(foco))
    await ctx.close()


async def confere_placa10(pg, rotulo):
    r = await pg.evaluate("""() => {
      const p = document.querySelector('.lugar[data-n="10"] .placa'), r = p.getBoundingClientRect();
      const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      const todas = [...document.querySelectorAll('.lugar .placa')].map(q => q.getBoundingClientRect());
      return { dentro: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, livre: !!(el && el.closest('.lugar[data-n="10"]')),
               lados: todas.every(q => q.left >= -2 && q.right <= innerWidth + 2) };
    }""")
    ok(f"{rotulo}: a placa 10 aparece inteira, sem nada por cima, e nenhuma placa sai pelos lados", r["dentro"] and r["livre"] and r["lados"], str(r))


async def fluxo_en(nav):
    ctx = await nav.new_context(viewport={"width": 1280, "height": 860}, locale="en-US")
    pg = await ctx.new_page()
    ouve(pg, "en")
    await pg.goto(BASE + "entenda.html?lang=en#parte-10", wait_until="networkidle")
    await vai_para(pg, 0)
    await pg.wait_for_timeout(600)
    etq = await pg.locator(".slide.ativo .etiqueta").first.inner_text()
    ok("inglês: a parada 10 abre traduzida (Stop 10 of 10)", "STOP 10 OF 10" in etq.upper() and await pg.locator(".chip.amarelo").count() == 0, etq)
    achados = []
    for i in range(0, N):
        if i:
            await proximo(pg)
            await pg.wait_for_timeout(300)
        if i == I_CV:
            await joga_caminho(pg, "en", auto=False)
        elif i == I_CB:
            await joga_boletim(pg, "en", en=True)
            await axe(pg, "inglês: confira o boletim")
        elif i in QUIZ:
            await responde_quiz(pg, i, "en")
        a = await pg.evaluate(JS_PT, ".slide.ativo, #nome-parte, .nav")
        achados += [f"slide {i + 1}: {x}" for x in a]
    fim = await pg.locator(".slide.ativo").inner_text()
    ok("inglês: o fim da parada", "Stop completed" in fim or "completed the Politics Map" in fim, fim[:60])
    bt = pg.locator('.slide.ativo .convite-avancado [data-acao="avancado"]')
    ok("inglês: no fim, o botão “Want to dig into the technical details?” (com as páginas)", "Want to dig into the technical details?" in await bt.inner_text()
       and f"({NA - 1} pages)" in await pg.locator(".slide.ativo .convite-avancado p").inner_text())
    await tecla(pg, '.slide.ativo [data-acao="avancado"]')
    await vai_para(pg, 0)
    await pg.wait_for_timeout(400)
    ok("inglês: a parte avançada abre (Stop 10 · Advanced part, endereço e contagem próprios)",
       pg.url.endswith("#parte-10-avancado") and "lang=en" in pg.url and "STOP 10 · ADVANCED PART" in (await pg.locator(".slide.ativo .etiqueta").first.inner_text()).upper()
       and await pg.locator("#contador").inner_text() == f"1 of {NA}" and "Advanced part" in await pg.locator("#nome-parte").inner_text())
    for i in range(0, NA):
        if i:
            await proximo(pg)
            await pg.wait_for_timeout(300)
        if i == I_LACRE:
            await joga_lacre(pg, "en", EN["avancado"]["slides"][I_LACRE]["inicial"])
        elif i in QUIZ_AV:
            await responde_quiz(pg, i, "en (parte avançada)", QUIZ_AV)
        elif 0 < i < len(AV) and i % 6 == 0:
            await axe(pg, f"inglês: parte avançada, slide {i + 1}")
        a = await pg.evaluate(JS_PT, ".slide.ativo, #nome-parte, .nav")
        achados += [f"avançada {i + 1}: {x}" for x in a]
    ok("inglês: nenhuma palavra em português solta em nenhum slide das duas trilhas (nem nos joguinhos)", not achados, " | ".join(achados)[:400])
    fim = await pg.locator(".slide.ativo").inner_text()
    ok("inglês: o fim da parte avançada", "Advanced part completed" in fim and "Back to the simple path" in fim, fim[:60])
    await tecla(pg, '.slide.ativo [data-acao="simples"]')
    await vai_para(pg, N - 1)
    ok("inglês: “Back to the simple path” volta ao fim do caminho simples", pg.url.endswith(f"#parte-10-{N}") and await pg.locator("#contador").inner_text() == f"{N} of {N}")
    # o botão da parada 7 em inglês
    await pg.goto("about:blank")
    await pg.goto(BASE + "entenda.html?lang=en#parte-7-4", wait_until="networkidle")
    await vai_para(pg, 3)
    a = pg.locator(".slide.ativo .link-slide a")
    href, txt = await a.get_attribute("href"), await a.inner_text()
    ok("inglês: parada 7 tem “See inside the voting machine”, com ?lang=en", href == "entenda.html?lang=en#parte-10" and "See inside the voting machine" in txt, f"{href} | {txt.strip()}")
    await a.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_function("() => /#parte-10$/.test(location.hash) && document.querySelector('.slide.ativo') && document.querySelector('.slide.ativo').dataset.i === '0'", timeout=9000)
    ok("inglês: o botão abre a parada 10 em inglês", "lang=en" in pg.url and "STOP 10 OF 10" in (await pg.locator(".slide.ativo .etiqueta").first.inner_text()).upper(), pg.url.split("/")[-1])
    await pg.keyboard.press("Escape")
    await pg.wait_for_function("!document.body.classList.contains('modo-aula')", timeout=6000)
    await pg.wait_for_timeout(1500)
    a = await pg.evaluate(JS_PT, ".mapa-ui, .mundo")
    rot = await pg.locator(".mundo").get_attribute("aria-label")
    ok("inglês: o mapa diz 10 stops e não tem português solto", "10 stops" in rot and not a, f"{rot} | {' | '.join(a)[:200]}")
    await ctx.close()


async def fluxo_celular(nav, larg, lang):
    ctx = await nav.new_context(viewport={"width": larg, "height": 640 if larg == 320 else 844}, is_mobile=True, has_touch=True, locale="pt-BR" if lang == "pt" else "en-US")
    pg = await ctx.new_page()
    ouve(pg, f"{larg}px {lang}")
    await pg.goto(BASE + f"entenda.html?lang={lang}", wait_until="networkidle")
    await pg.wait_for_timeout(2400)
    await confere_placa10(pg, f"{larg} px ({lang})")
    await pg.goto("about:blank")
    await pg.goto(BASE + f"entenda.html?lang={lang}#parte-10", wait_until="networkidle")
    await vai_para(pg, 0)
    ruins = []
    for trilha, total in (("", N), ("-avancado", NA)):
        if trilha:
            await pg.goto("about:blank")
            await pg.goto(BASE + f"entenda.html?lang={lang}#parte-10{trilha}", wait_until="networkidle")
            await vai_para(pg, 0)
        for i in range(0, total):
            if i:
                await proximo(pg)
            await pg.wait_for_timeout(750)
            if trilha and i == I_LACRE:
                await tecla(pg, ".slide.ativo [data-lacre-guarda]")
                await tecla(pg, ".slide.ativo [data-lacre-troca]")
                await pg.wait_for_timeout(300)
            elif not trilha and i == I_CB:
                await tecla(pg, f".slide.ativo .cb-linha[data-cb-linha='{LINHA_ERRADA}']")
                await pg.wait_for_timeout(200)
            await termina_animacoes(pg)
            r = await pg.evaluate(JS_LARGURA)
            if r["fora"] or r["sx"] or r["rol"] > 1 or not r["nav"]:
                ruins.append(f"{trilha or 'simples'} {i + 1}: {r}")
    ok(f"{larg} px ({lang}): nenhum slide da parada 10 (caminho simples e parte avançada) passa da largura da tela (nem a barra de baixo)", not ruins, " | ".join(ruins)[:400])
    if larg == 390:
        await pg.goto("about:blank")
        await pg.goto(BASE + f"entenda.html?lang={lang}#parte-10-avancado-{I_LACRE + 1}", wait_until="networkidle")
        await vai_para(pg, I_LACRE)
        await pg.wait_for_timeout(700)
        await axe(pg, f"celular {lang}: lacre digital (parte avançada)")
        await pg.goto("about:blank")
        await pg.goto(BASE + f"entenda.html?lang={lang}#parte-10-{N}", wait_until="networkidle")
        await vai_para(pg, N - 1)
        await pg.wait_for_timeout(700)
        bt = await pg.evaluate("""() => { const b = document.querySelector('.slide.ativo [data-acao="avancado"]').getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth && b.height >= 44; }""")
        ok(f"celular {lang}: o botão da parte avançada cabe na tela e é fácil de tocar (≥ 44 px)", bt)
        await axe(pg, f"celular {lang}: fim do caminho simples, com o convite")
    await ctx.close()


async def fluxo_movimento(nav):
    # "menos movimento" do sistema
    ctx = await nav.new_context(viewport={"width": 1280, "height": 860}, reduced_motion="reduce", locale="pt-BR")
    pg = await ctx.new_page()
    ouve(pg, "menos movimento")
    await pg.goto(BASE + "entenda.html?lang=pt", wait_until="networkidle")
    await pg.wait_for_timeout(1200)
    ok("menos movimento: o bonequinho da trilha não anda", await pg.locator(".andarilho").is_hidden())
    await pg.focus('.lugar[data-n="10"] .placa')
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(250)
    ok("menos movimento: a parada abre na hora, sem o voo da câmera", await pg.evaluate("document.body.classList.contains('modo-aula')"))
    anim = await pg.evaluate("getComputedStyle(document.querySelector('.slide.ativo .bu-sai')).animationName")
    ok("menos movimento: o boletim da abertura fica parado", anim == "none", anim)
    await pg.goto("about:blank")
    await pg.goto(BASE + f"entenda.html?lang=pt#parte-10-{I_CV + 1}", wait_until="networkidle")
    await vai_para(pg, I_CV)
    tr_ = await pg.evaluate("getComputedStyle(document.querySelector('.slide.ativo .cv-ficha')).transitionDuration")
    ok("menos movimento: a ficha do caminho do voto pula sem deslizar", all(x.strip() == "0s" for x in tr_.split(",")), tr_)
    await joga_caminho(pg, "menos movimento", auto=True)
    await ctx.close()
    # "menos movimento" do menu ♿ do site (html.sem-movimento)
    ctx = await nav.new_context(viewport={"width": 1280, "height": 860}, locale="pt-BR")
    await ctx.add_init_script("try { localStorage.setItem('ep-a11y', JSON.stringify({ movimento: true })); localStorage.setItem('ep-lang', 'pt'); } catch (e) {}")
    pg = await ctx.new_page()
    ouve(pg, "sem-movimento")
    await pg.goto(BASE + f"entenda.html#parte-10-{I_CV + 1}", wait_until="networkidle")
    await vai_para(pg, I_CV)
    r = await pg.evaluate("""() => { const seg = v => Math.max(...v.split(',').map(x => parseFloat(x) * (/ms/.test(x) ? .001 : 1)));
      const f = getComputedStyle(document.querySelector('.slide.ativo .cv-ficha')), c = getComputedStyle(document.querySelector('.slide.ativo .cv-fase'));
      return { cls: document.documentElement.classList.contains('sem-movimento'), tr: seg(f.transitionDuration), an: seg(c.animationDuration) }; }""")
    ok("menu ♿ “menos movimento”: nada desliza nem anima no caminho do voto", r["cls"] and r["tr"] <= .01 and r["an"] <= .01, str(r))
    await tecla(pg, ".slide.ativo [data-cv-prox]")
    ok("menu ♿ “menos movimento”: o caminho do voto continua funcionando", await pg.locator(".slide.ativo [data-cv]").get_attribute("data-pos") == "1")
    await ctx.close()


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        await fluxo_pt(nav)
        await fluxo_en(nav)
        for larg, lang in ((390, "pt"), (320, "pt"), (320, "en")):
            await fluxo_celular(nav, larg, lang)
        await fluxo_movimento(nav)
        ok("sem erros de JavaScript", not ERROS, "; ".join(ERROS)[:400])
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    sys.exit(0 if all(RES) else 1)


asyncio.run(main())
