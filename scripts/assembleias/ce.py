"""Assembleia Legislativa do Estado do Ceará (Alece): páginas oficiais (não há API de proposições).

Lista: https://www.al.ce.gov.br/deputados ("Em Exercício e Licenciados"): quem está marcado como licenciado fica de fora
(46 pessoas no cargo, inclusive os suplentes que assumiram), com partido de hoje, foto e página de cada um.
Propostas: as listas oficiais de proposições da 31ª legislatura (2023-2027) em https://www2.al.ce.gov.br/legislativo/
proposicoes/ (projetos de lei, de lei complementar, de emenda constitucional, de decreto legislativo e de resolução;
"Deliberados" e "Tramitando"), com número, autor, data de entrada, ementa (com o link do texto), histórico, autógrafo,
número da lei e veto. São páginas de 20 em 20: elas são lidas em rodízio (a 1ª página de cada lista todo dia e um
cursor que passa por todas as outras até um limite de tempo), com cache em .cache/alece/.
"""
from __future__ import annotations

import codecs
import html
import os
import re
import time

import regional
from comum import chave_nome, fonte, hoje, log, sem_acento

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
                    "d": _data(_campo(p, "Entrada")), "e": _txt(ementa.group(2)) if ementa else None,
                    "url": ementa.group(1) if ementa and ementa.group(1) else None,
                    "lei": _txt(lei.group(2)) if lei else None, "lei_url": lei.group(1) if lei and lei.group(1) else None,
                    "veto": veto if veto and veto != "-" else None, "autografo": _txt(aut.group(1)) if aut else None,
                    "obs": _campo(p, "OBS"), "loc": _txt(hist.group(1)) if hist else None,
                    "hist": _txt(hist.group(2))[-600:] if hist else None})
    return out


def _paginas(t: str) -> int:
    m = re.search(r"P&aacute;gina \d+ de (\d+)|Página \d+ de (\d+)", t)
    return int(next(g for g in m.groups() if g)) if m else 1


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
    listas = [(tb, op) for tb in TABELAS for op in ("T", "D")]
    sem_limite = os.environ.get("NE_SEM_LIMITE") == "1"
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
    while sem_limite or time.time() - t0 < ORCAMENTO_S:
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
    rede.guardar({"regs": regs, "paginas": paginas, "lidas": lidas_em, "cursor": [w, p]}, "estado.json")
    faltam = [f"{tb}-{op}" for tb, op in listas if not lidas_em.get(f"{tb}-{op}")]
    log(f"  CE: {len(regs)} proposições no cache; {pags} páginas lidas hoje" + (f"; listas sem leitura completa: {faltam}" if faltam else ""))
    if len(faltam) > len(listas) // 2:
        raise RuntimeError("Alece: menos da metade das listas de proposições lidas; rode de novo (cache em andamento)")
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
                if (r.get("d") or "9999") < INICIO:
                    continue
                tipo, sigla, norma = TABELAS[r["tab"]]
                s = _situacao(r, norma)
                prop = regional.proposta(f"alece:{r['tab']}:{r['n']}-{r['a']}", f"{sigla} {r['n']}/{r['a']}", tipo, r["d"], r["e"],
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
                      "sigla": "Alece", "site": SITE}, membros, extras, cobertura, fonte_l, notas)
    log(f"  CE: {rede.pedidos} pedidos ao site oficial")
    return r


def _situacao(r: dict, norma: str) -> dict:
    hist = sem_acento((r.get("hist") or "").lower())
    obs = sem_acento((r.get("obs") or "").lower())
    datas = re.findall(r"em (\d{2}\.\d{2}\.\d{2,4})", hist)
    data = _data(datas[-1]) if datas else None
    if r.get("lei") and re.search(r"\d", r["lei"]):
        num = re.sub(r"\D", "", r["lei"])
        ano = (re.search(r"leis(\d{4})", r.get("lei_url") or "") or [None, None])[1] or (data or "")[:4] or None
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
