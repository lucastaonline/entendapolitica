"""Assembleia Legislativa do Estado do Ceará (Alece): páginas oficiais (não há API de proposições).

Lista: https://www.al.ce.gov.br/deputados ("Em Exercício e Licenciados"): quem está marcado como licenciado fica de fora
(46 pessoas no cargo, inclusive os suplentes que assumiram), com partido de hoje, foto e página de cada um.
Propostas: as listas oficiais de proposições da 31ª legislatura (2023-2027) em https://www2.al.ce.gov.br/legislativo/
proposicoes/ (projetos de lei, de lei complementar, de emenda constitucional, de decreto legislativo e de resolução;
"Deliberados" e "Tramitando"), com número, autor, data de entrada, ementa (com o link do texto), histórico, autógrafo,
número da lei e veto. São páginas de 20 em 20: elas são lidas em rodízio (a 1ª página de cada lista todo dia e um
cursor que passa por todas as outras até um limite de tempo), com cache em .cache/alece/. Primeira carga (cache vazio,
como no robô do GitHub): o cursor usa a rodada toda (_carga.py) e, enquanto alguma lista não foi lida inteira, nada é
gravado em dados/ (ficam os arquivos de antes; o coletor devolve "em andamento").
"""
from __future__ import annotations

import codecs
import html
import re
import time

import regional
from comum import chave_nome, fonte, hoje, log, sem_acento

from . import _carga
from . import _ne_gov as gv
from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, legislatura_estadual, membro,
                        nome_lei, partido_sigla, resumo_status)

SITE = "https://www.al.ce.gov.br"
LISTAS = "https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php?nome={leg}_legislatura&tabela={t}&opcao={o}"
VEICULO = "Assembleia Legislativa do Ceará (Alece)"
TABELAS = {"projeto_lei": ("PL", "PL", "Lei"), "projeto_compl": ("PLP", "PLC", "Lei Complementar"),
           "projeto_emen": ("PEC", "PEC", "Emenda Constitucional"), "projeto_decre": ("PDL", "PDL", "Decreto Legislativo"),
           "projeto_reso": ("PRC", "PR", "Resolução")}
ORCAMENTO_S = 150


def _cp1252(e: UnicodeDecodeError):
    return e.object[e.start:e.end].decode("cp1252", "replace"), e.end


codecs.register_error("ne_cp1252", _cp1252)


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<br\s*/?>", " | ", re.sub(r"<(?!br)[^>]+>", " ", s)))).strip()


def _campo(bloco: str, rotulo: str) -> str | None:
    m = re.search(rotulo + r"\s*:?\s*</b>\s*</font>\s*(?:<br>|&nbsp;)?\s*<font[^>]*>(.*?)</font>", bloco, re.S | re.I)
    return _txt(m.group(1)) if m else None


def _data(s: str | None) -> str | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2,4})", s or "")
    if not m:
        return None
    a = m.group(3)
    return f"{'20' + a if len(a) == 2 else a}-{m.group(2)}-{m.group(1)}"


def _registros(t: str, tabela: str, opcao: str) -> list[dict]:
    out = []
    partes = re.split(r"(?=<b>N&ordm; do Proj\.:</b>)", t)
    for p in partes[1:]:
        num = _campo(p, r"N&ordm; do Proj\.")
        if not num:
            continue
        m = re.match(r"(\d+)\s*/\s*(\d{2,4})", num)
        if not m:
            continue
        ano = m.group(2) if len(m.group(2)) == 4 else "20" + m.group(2)
        ementa = re.search(r"<b>Ementa:</b>.*?<font[^>]*>\s*(?:<a href='([^']+)'>)?(.*?)(?:</a>)?\s*</font>", p, re.S)
        lei = re.search(r"<b>Lei:</b>.*?<font[^>]*>\s*(?:<a href='([^']+)'>)?(.*?)(?:</a>)?\s*</font>", p, re.S)
        veto = _campo(p, r"Veto n&ordm;")
        aut = re.search(r"<b>Aut&oacute;grafo:</b>.*?<font[^>]*>\s*(?:<a href='[^']+'>)?(.*?)(?:</a>)?\s*</font>", p, re.S)
        hist = re.search(r"Localiza&ccedil;&atilde;o:</b></font>&nbsp;<font[^>]*>(.*?)</font><br><font[^>]*>(.*?)</font>", p, re.S)
        out.append({"tab": tabela, "op": opcao, "n": str(int(m.group(1))), "a": ano, "au": _campo(p, "Autor"),
                    "d": _data(_campo(p, "Entrada")), "dx": _data(_campo(p, "Expediente")),
                    "e": _txt(ementa.group(2)) if ementa else None,
                    "url": ementa.group(1) if ementa and ementa.group(1) else None,
                    "lei": _txt(lei.group(2)) if lei else None, "lei_url": lei.group(1) if lei and lei.group(1) else None,
                    "veto": veto if veto and veto != "-" else None, "autografo": _txt(aut.group(1)) if aut else None,
                    "obs": _campo(p, "OBS"), "loc": _txt(hist.group(1)) if hist else None,
                    "hist": _txt(hist.group(2))[-600:] if hist else None})
    return out


def _paginas(t: str) -> int:
    m = re.search(r"P&aacute;gina \d+ de (\d+)|Página \d+ de (\d+)", t)
    return int(next(g for g in m.groups() if g)) if m else 1


def _data_entrada(r: dict) -> str | None:
    """A data de entrada só vale se cair no ano do número da proposição (a Alece tem erros de digitação, como "26.06.26"
    numa proposição de 2023); senão, a data do expediente, com a mesma conferência."""
    for d in (r.get("d"), r.get("dx")):
        if d and d[:4] == r["a"] and d <= hoje():
            return d
    return None


def coletar() -> dict:
    rede = Rede("alece", pausa=0.6, timeout=90)
    t = rede.texto(f"{SITE}/deputados", "deputados.html", 20)
    cards = re.findall(r'<div\s+class="deputado_card([^"]*)"(.*?)</div>', t, re.S)
    pessoas = []
    for cls, c in cards:
        if "licenciado" in cls:
            continue
        n = re.search(r'href="(https://www\.al\.ce\.gov\.br/deputados/[a-z0-9\-]+)">\s*(.*?)\s*</a>', c, re.S)
        if not n or n.group(1).endswith("/mesa-diretora"):
            continue
        part = re.search(r'deputado_card--partido[^>]*>\s*(.*?)\s*</p>', c, re.S)
        img = re.search(r'src="([^"]+)"', c)
        nome = html.unescape(n.group(2)).strip()
        pessoas.append({"chave": n.group(1).rsplit("/", 1)[1], "nome": nome, "nomeCivil": None, "url": n.group(1),
                        "partido": partido_sigla(html.unescape(part.group(1)).strip()) if part else None,
                        "foto": img.group(1) if img else None})
    if not 40 <= len(pessoas) <= 50:
        raise RuntimeError(f"Alece: {len(pessoas)} deputados em exercício na página oficial (esperado: 46)")
    # proposições: rodízio pelas páginas de todas as listas
    est = rede.estado("estado.json", {}) or {}
    regs: dict[str, dict] = est.get("regs") or {}
    paginas: dict[str, int] = est.get("paginas") or {}
    lidas_em: dict[str, str] = est.get("lidas") or {}
    cursor = est.get("cursor") or [0, 1]
    listas = [(tb, op) for tb in list(TABELAS) + [MENSAGENS] for op in ("T", "D")]
    # primeira carga (alguma lista nunca lida inteira, como no robô que começa com o cache vazio): a rodada toda
    primeira = any(not lidas_em.get(f"{tb}-{op}") for tb, op in listas)
    limite = _carga.limite_diario(ORCAMENTO_S, primeira)
    t0, pags = time.time(), 0

    def ler(tb: str, op: str, pag: int) -> int:
        url = LISTAS.format(leg=legislatura_estadual(31), t=tb, o=op) + (f"&absolutepage={pag}" if pag > 1 else "")
        # a página é UTF-8, mas alguns campos (OBS, histórico) vêm do banco em Windows-1252
        h = rede.bruto(url).decode("utf-8", "ne_cp1252")
        for r in _registros(h, tb, op):
            regs[f"{tb}:{r['n']}/{r['a']}"] = r
        n = _paginas(h)
        paginas[f"{tb}-{op}"] = n
        return n

    for tb, op in listas:  # 1ª página de cada lista, todo dia
        ler(tb, op, 1)
        pags += 1
    w, p = cursor
    if w >= len(listas):
        w, p = 0, 1
    inicio = (w, p)
    try:
        while time.time() - t0 < limite:
            tb, op = listas[w]
            n = ler(tb, op, p) if p > 1 else paginas.get(f"{tb}-{op}", 1)
            pags += 1 if p > 1 else 0
            if p >= n:
                lidas_em[f"{tb}-{op}"] = hoje()
                w, p = (w + 1) % len(listas), 1
            else:
                p += 1
            if pags % 20 == 0:
                rede.guardar({"regs": regs, "paginas": paginas, "lidas": lidas_em, "cursor": [w, p]}, "estado.json")
            if (w, p) == inicio:
                break
    except _carga.SemTempo:  # o fim da rodada chegou: o cursor guarda onde parou
        pass
    rede.guardar({"regs": regs, "paginas": paginas, "lidas": lidas_em, "cursor": [w, p]}, "estado.json")
    faltam = [f"{tb}-{op}" for tb, op in listas if not lidas_em.get(f"{tb}-{op}")]
    log(f"  CE: {len(regs)} proposições no cache; {pags} páginas lidas hoje" + (f"; listas sem leitura completa: {faltam}" if faltam else ""))
    if faltam:  # primeira carga em andamento: nada pela metade no site (ficam os arquivos de antes)
        log(f"  CE: primeira carga das listas em andamento; os arquivos de antes continuam; {rede.pedidos} pedidos ao site oficial")
        return _carga.pendente("Alece", f"primeira carga: {len(faltam)} de {len(listas)} listas por ler", rede.pedidos)
    # TSE e propostas por pessoa
    ligados, avisos = casar_membros("CE", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  CE TSE: {a}")
    por_nome: dict[str, list[tuple[str, str]]] = {}
    for k, r in regs.items():
        # "FULANO", "FULANO E BELTRANO", "FULANO, COAUTORIA: BELTRANO, SICRANO": o primeiro é o autor principal
        au = re.sub(r"(?i)\bco-?autori?a?s?\s*:?", ",", r.get("au") or "")
        nomes = [x.strip() for x in re.split(r",|;|/| E (?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", au) if x.strip()]
        for i, nm in enumerate(nomes):
            por_nome.setdefault(chave_nome(re.sub(r"^DEP(UTAD[OA])?\.?\s+", "", nm)), []).append((k, "autor" if i == 0 else "coautor"))
    membros, extras, listas_p = [], {}, []
    fonte_l = fonte(VEICULO, "Deputados em exercício (página oficial)", f"{SITE}/deputados")
    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "CE", cand, p["nome"])
        membros.append(membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], p["url"]))
        chaves = {chave_nome(p["nome"]), chave_nome(re.sub(r"^(Dra?|Ap|Pr)\.?\s+", "", p["nome"]))}
        if cand:
            chaves.add(chave_nome(cand["urna"]))
        lista, vistos = [], set()
        for ch in chaves:
            for k, papel in por_nome.get(ch, []):
                if k in vistos:
                    continue
                vistos.add(k)
                r = regs[k]
                if (_data_entrada(r) or "9999") < INICIO or r["tab"] not in TABELAS:
                    continue
                tipo, sigla, norma = TABELAS[r["tab"]]
                s = _situacao(r, norma)
                prop = regional.proposta(f"alece:{r['tab']}:{r['n']}-{r['a']}", f"{sigla} {r['n']}/{r['a']}", tipo, _data_entrada(r), r["e"],
                                         r.get("obs") or ("Tramitando" if r["op"] == "T" else "Deliberado"),
                                         r.get("url") or LISTAS.format(leg=legislatura_estadual(31), t=r["tab"], o=r["op"]),
                                         papel=papel, status=s["status"],
                                         data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
                lista.append(com_status_en(prop, s["en"]))
        listas_p.append(lista)
        fonte_p = fonte(VEICULO, f"Proposições de {p['nome']} na {legislatura_estadual(31)}ª legislatura (listas oficiais)",
                        "https://www.al.ce.gov.br/paginas/proposicoes?menu=96")
        extras[pid] = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
                       "links": {"oficial": p["url"], "email": None, "redes": []}, "fontes": [fonte_l, fonte_p]}
    log(f"  CE: situações {resumo_status(listas_p)}")
    notas = [("A Alece não tem API de proposições: as listas oficiais (páginas de 20 em 20) são lidas aos poucos, "
              "e cada proposição é relida a cada poucos dias.",
              "Alece has no API for bills: the official lists (pages of 20) are read gradually, and each bill is re-read "
              "every few days.")]
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = gravar("CE", {"casa": "Assembleia Legislativa do Estado do Ceará", "casa_en": "Legislative Assembly of the State of Ceará",
                      "sigla": "Alece", "site": SITE}, membros, extras, cobertura, fonte_l, notas + [NOTA_GOVERNO])
    try:
        _governo(rede, regs)
    except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
        log(f"  CE: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
    log(f"  CE: {rede.pedidos} pedidos ao site oficial")
    return r


MENSAGENS = "projeto_mens"  # lista "Mensagens": os projetos de lei que o Executivo (e os outros Poderes) mandam à Assembleia
LEIS_ANO = "https://www2.al.ce.gov.br/legislativo/legislacao5/leis{a}/LEIS{a}.htm"
LEIS_LC = "https://www2.al.ce.gov.br/legislativo/ementario/lc.htm"
NOTA_GOVERNO = ("Os vetos do governador não entram no perfil dele: a Alece não publica uma lista dos vetos (o campo \"Veto nº\" "
                "das proposições quase nunca vem preenchido). Os vetos saem no Diário Oficial do Estado do Ceará.",
                "The governor's vetoes are not shown on his profile: the Alece does not publish a list of vetoes (the \"Veto nº\" "
                "field of bills is almost never filled in). Vetoes are published in the Ceará State Official Gazette.")
_TIPO_MSG = [(r"lei complementar", "PLP", "PLC", "Lei Complementar"), (r"emenda (a|à) constitui|emenda constitucional", "PEC", "PEC", "Emenda Constitucional"),
             (r"decreto legislativo", "PDL", "PDL", "Decreto Legislativo"), (r"resolu", "PRC", "PR", "Resolução")]


def _linhas_leis(h: str, base: str, tipo: str) -> list[dict]:
    """Linhas das listas oficiais de leis da Alece ("LEI N.° 19.167, DE 30.12.24 ( D.O. 02.01.25)" com o link do texto)."""
    import urllib.parse
    padrao = r"LEI\s+COMPLEMENTAR\s+N\D{0,5}?(\d[\d.]*)" if tipo == "LC" else r"LEI\s+N\D{0,5}?(\d[\d.]*)"
    ancoras = [(m.start(), m.end(), m.group(1), _txt(m.group(2)))
               for m in re.finditer(r"<a\b[^>]*?href=['\"]?([^'\" >]+)['\"]?[^>]*>(.*?)</a>", h, re.S | re.I)]
    out = []
    for i, (_, fim, href, txt) in enumerate(ancoras):
        m = re.match(padrao, txt, re.I)
        if not m or not re.search(r"\.html?$", href, re.I):
            continue
        n = str(int(re.sub(r"\D", "", m.group(1))))
        prox = ancoras[i + 1][0] if i + 1 < len(ancoras) else len(h)
        seg = txt + " " + _txt(h[fim:prox])[:80]
        # "DE 30.12.24", "DE 1°.04.2026", "DE 29/12/99" (e um "DFE 24.03.25" na lista de 2025)
        d = re.search(r"\bD\w{0,2}\s+(\d{1,2})\s*[°ºo]?\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{2,4})", seg, re.I)
        if not d:
            continue
        a = d.group(3)
        a = a if len(a) == 4 else str((2000 if int(a) <= int(hoje()[2:4]) + 1 else 1900) + int(a))
        data = f"{a}-{int(d.group(2)):02d}-{int(d.group(1)):02d}"
        url = urllib.parse.urljoin(base, href)
        num_href = re.search(r"(\d+)\.html?$", href, re.I)
        if not num_href or str(int(num_href.group(1))) != n:  # o link de uma linha às vezes aponta para a lei vizinha
            url = (f"https://www2.al.ce.gov.br/legislativo/ementario/lc{n}.htm" if tipo == "LC"
                   else f"https://www2.al.ce.gov.br/legislativo/legislacao5/leis{data[:4]}/{n}.htm")
        out.append({"n": n, "d": data, "url": url, "tipo": tipo})
    return out


def _ler_lei(rede: Rede, url: str) -> str:
    h = rede.bruto(url, None, None).decode("utf-8", "ne_cp1252")
    return _txt(re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", h))


def _quem_assinou(texto: str) -> bool | None:
    """Como gv.quem_assinou; algumas páginas de lei da Alece não trazem o "Faço saber... eu sanciono", mas terminam com a
    assinatura "<nome> GOVERNADOR DO ESTADO" (conferido à mão nas leis 18.337, 18.368, 18.630 e 19.064)."""
    q = gv.quem_assinou(texto)
    if q is None:
        fim = sem_acento((texto or "")[-400:].lower())
        if re.search(r"\bgovernador(a)? do estado\b", fim) and "presidente" not in fim and "promulgo" not in fim:
            return False
    return q


def _leis(rede: Rede, inicio: str) -> dict[str, dict]:
    """Leis ordinárias (lista oficial de cada ano) e complementares (ementário) com data a partir de inicio."""
    out: dict[str, dict] = {}
    atual = int(hoje()[:4])
    for a in range(int(inicio[:4]) - 1, atual + 1):  # o ano anterior também: uma lei de 2 de janeiro pode estar na lista dele
        url = LEIS_ANO.format(a=a)
        idade = 20 if a == atual else 24 * 7 if a == atual - 1 else 24 * 30
        h = rede.bruto(url, f"gov-leis-{a}.htm", idade).decode("utf-8", "ne_cp1252")
        for lei in _linhas_leis(h, url, "LO"):
            if lei["d"] >= inicio:
                out[f"LO {lei['n']}"] = lei
    h = rede.bruto(LEIS_LC, "gov-leis-lc.htm", 20).decode("utf-8", "ne_cp1252")
    for lei in _linhas_leis(h, LEIS_LC, "LC"):
        if lei["d"] >= inicio:
            out[f"LC {lei['n']}"] = lei
    return out


def _governo(rede: Rede, regs: dict) -> dict:
    """dados/pessoas/gov-CE.json: projetos do "PODER EXECUTIVO" (projetos de lei na lista "Mensagens"; os de lei complementar
    e de emenda à Constituição nas listas deles) e leis sancionadas (contadas pelo texto oficial de cada lei)."""
    per = gv.periodo("CE")
    ini = per["inicio"]
    lista, msgs = [], set()
    ordem = sorted(regs.items(), key=lambda kv: kv[1]["tab"] == MENSAGENS)  # as listas próprias primeiro
    for k, r in ordem:
        if r["tab"] not in (MENSAGENS, "projeto_compl", "projeto_emen"):
            continue
        if (_data_entrada(r) or f"{r['a']}-12-31") < ini or not gv.autor_do_executivo(r.get("au"), per):
            continue
        cab = sem_acento((r.get("e") or "")[:160].lower())
        msg = re.search(r"mensagem n\D{0,5}?(\d[\d.]*\d)", cab)
        if msg and msg.group(1) in msgs:
            continue
        if msg:
            msgs.add(msg.group(1))
        if r["tab"] == MENSAGENS:
            tipo, sigla, norma = "PL", "PL", "Lei"
            for exp, t, s, n in _TIPO_MSG:
                if re.search(exp, cab.split(" - ")[0]):
                    tipo, sigla, norma = t, s, n
                    break
            tab = "projeto_compl" if tipo == "PLP" else "projeto_lei" if tipo == "PL" else r["tab"]
        else:
            (tipo, sigla, norma), tab = TABELAS[r["tab"]], r["tab"]
        s_ = _situacao(dict(r, tab=tab), norma)
        prop = regional.proposta(f"alece:{r['tab']}:{r['n']}-{r['a']}",
                                 f"{sigla} {r['n']}/{r['a']}" + (f" (Mensagem nº {msg.group(1)})" if msg else ""),
                                 tipo, _data_entrada(r), r["e"], r.get("obs") or ("Tramitando" if r["op"] == "T" else "Deliberado"),
                                 r.get("url") or LISTAS.format(leg=legislatura_estadual(31), t=r["tab"], o=r["op"]), papel="autor",
                                 status=s_["status"], data_status=s_["data"], status_txt=s_["txt"], lei=s_["lei"])
        lista.append(com_status_en(prop, s_["en"]))
    fonte_prop = fonte(VEICULO, "Proposições do Poder Executivo (listas \"Mensagens\", \"Projetos de Lei Complementar\" e "
                       "\"Propostas de Emenda Constitucional\")", "https://www.al.ce.gov.br/paginas/proposicoes?menu=96")
    fontes = [fonte(VEICULO, "Leis ordinárias de cada ano e ementário das leis complementares",
                    "https://www2.al.ce.gov.br/legislativo/lei_ordinaria.htm")]
    leis = _leis(rede, ini)
    quem, faltam = gv.classificar_leis(rede, {k: v["url"] for k, v in leis.items()}, lambda u: _ler_lei(rede, u), orcamento_s=120,
                                       decidir=_quem_assinou)
    if faltam or not leis:  # sem a conta das leis, o perfil ficaria pela metade: fica o arquivo da última vez
        log("  CE: " + (f"{faltam} leis com o texto ainda não lido" if faltam else "as listas de leis não vieram")
            + "; o perfil do governador fica como estava")
        return {}
    import collections
    c = collections.Counter(quem.values())
    pt, en = gv.nota_leis(per, len(leis), c[False], c[True], c[None], "nas listas oficiais da Alece",
                          "in the Alece's official lists",
                          ("em que o texto oficial diz \"eu sanciono\" ou termina com a assinatura do governador",
                           "whose official text says \"I sign\" (\"eu sanciono\") or ends with the governor's signature"))
    pt += " Os vetos não entram: a Alece não publica uma lista deles."
    en += " Vetoes are not included: the Alece does not publish a list of them."
    ex = gv.bloco_executivo(per, c[False], None, fontes, pt, en, promulgadas_pela_casa=c[True])
    esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature")
    return gv.gravar_gov("CE", per, lista, esc, esc_en, fonte_prop, ex, fontes)


def _situacao(r: dict, norma: str) -> dict:
    hist = sem_acento((r.get("hist") or "").lower())
    obs = sem_acento((r.get("obs") or "").lower())
    datas = re.findall(r"em (\d{2}\.\d{2}\.\d{2,4})", hist)
    data = _data(datas[-1]) if datas else None
    if r.get("lei") and re.search(r"\d", r["lei"]):
        # "18.376", "LC 322 D.O. 11.04.24", "EC 116 D.O. 21.12.23": o número é o primeiro; a data do Diário Oficial dá o ano
        num = re.sub(r"\D", "", re.search(r"\d[\d.]*", r["lei"]).group(0))
        do = re.search(r"D\.\s*O\.?\s*(\d{1,2})[./](\d{1,2})[./](\d{2,4})", r["lei"])
        ano = ((re.search(r"leis(\d{4})", r.get("lei_url") or "") or [None, None])[1]
               or (("20" + do.group(3))[-4:] if do else None) or (data or "")[:4] or None)
        nl = nome_lei(norma, num, ano)
        return {"status": "lei", "txt": f"Virou {'o' if norma.startswith('Decreto') else 'a'} {nl}", "en": None, "data": data,
                "lei": {"nome": nl, "url": r.get("lei_url")}}
    if r.get("veto"):
        return {"status": "rejeitada", "txt": "Vetada pelo governador", "en": "Vetoed by the governor", "data": data, "lei": None}
    regras = [
        (r"retirad", "retirada", None, None), (r"rejeitad", "rejeitada", "Rejeitada", None),
        (r"prejudicad", "parada", "Ficou prejudicada", None), (r"arquivad", "arquivada", "Arquivada", None),
        (r"anexad|apensad|tramitacao conjunta", "junta", None, None),
    ]
    for exp, st, pt, en in regras:
        if re.search(exp, obs):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    if r.get("autografo") and re.search(r"\d", r["autografo"]):
        if r["tab"] == "projeto_lei" or r["tab"] == "projeto_compl":
            return {"status": "aprovada", "txt": "Aprovada; enviada ao governador para sanção ou veto",
                    "en": "Approved; sent to the governor to sign or veto", "data": data, "lei": None}
        # emenda à Constituição, decreto legislativo e resolução são promulgados pela própria Assembleia
        return {"status": "aprovada", "txt": "Aprovada no Plenário", "en": "Approved by the full Assembly", "data": data, "lei": None}
    ult = hist.split("|")[-1] if hist else ""
    if re.search(r"plenario.*aprovad|aprovad.*plenario", ult):
        return {"status": "aprovada", "txt": "Aprovada no Plenário", "en": "Approved by the full Assembly", "data": data, "lei": None}
    for exp, st, pt, en in regras:
        if re.search(exp, ult):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    if r["op"] == "D" and re.search(r"parecer contrario/aprovad", ult):
        # "Deliberado" depois de a Comissão de Constituição, Justiça e Redação aprovar o parecer contrário
        return {"status": "rejeitada", "txt": "Rejeitada na Comissão de Constituição, Justiça e Redação",
                "en": "Rejected by the Constitution, Justice and Drafting Committee", "data": data, "lei": None}
    if r["op"] == "T" or hist:
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


# conferidos à mão (endereço da página na Alece -> candidato do TSE de 2022): "Ap Luiz Henrique" é APÓSTOLO LUIZ HENRIQUE
# (Luiz Henrique Castelo Lima); "Carmelo Bolsonaro" é CARMELO NETO (Carmelo Silveira Carneiro Leão Neto); "Júlio César
# Filho" (nome completo na Alece: Júlio César Costa Lima Filho) é JULINHO (no TSE: Julio Cesar Costa Lima Junior), com os
# mesmos 46.082 votos de 2022 informados pela Alece.
TSE_MANUAL: dict[str, str] = {"ap-luiz-henrique": "60001608819", "carmelo-bolsonaro": "60001633791",
                              "julio-cesar-filho": "60001633659"}
