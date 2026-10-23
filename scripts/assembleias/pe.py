"""Assembleia Legislativa do Estado de Pernambuco (Alepe): Portal de Dados Abertos (https://dadosabertos.alepe.pe.gov.br).

Lista: /api/v1/parlamentares (os deputados da legislatura atual, com o partido de hoje), com foto e página de cada um
tiradas da página oficial https://www.alepe.pe.gov.br/parlamentares/ (ligadas pelo nome).
Propostas: /api/v1/proposicoes/projetos/?legislatura=20 (todos os projetos da legislatura, com os autores: o primeiro é o
autor principal) e, para a situação, o detalhe de cada projeto (/api/v1/proposicoes/projetos/?docid=..&tipoprop=p: histórico,
resultado final, tramitação conjunta e o autógrafo, que traz o número da lei). O detalhe é grande (traz o texto inteiro),
então só o resumo fica no cache e ele é relido em rodízio: os novos na hora, os que ainda andam a cada 21 dias e os que já
terminaram (lei, arquivado...) a cada 90 dias.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time
import xml.etree.ElementTree as ET

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, sem_acento

from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, legislatura_estadual, membro,
                        nome_lei, partido_sigla, resumo_status)

API = "https://dadosabertos.alepe.pe.gov.br/api/v1"
SITE = "https://www.alepe.pe.gov.br"
VEICULO = "Assembleia Legislativa de Pernambuco (Alepe)"
TIPOS = {"PROJETO DE LEI ORDINARIA": ("PL", "PLO"), "PROJETO DE LEI COMPLEMENTAR": ("PLP", "PLC"),
         "PROPOSTA DE EMENDA A CONSTITUICAO": ("PEC", "PEC"), "PROJETO DE DECRETO LEGISLATIVO": ("PDL", "PDL"),
         "PROJETO DE RESOLUCAO": ("PRC", "PR")}
NORMA = {"PL": ("Lei", 1), "PLP": ("Lei Complementar", 2), "PRC": ("Resolução", 4), "PEC": ("Emenda Constitucional", None),
         "PDL": ("Decreto Legislativo", None)}
RELER_ANDANDO, RELER_FIM, ORCAMENTO_S = 21, 90, 150


def _tipo(t: str) -> tuple[str, str] | None:
    t = re.sub(r"\s+(DESARQUIVAD[OA])$", "", sem_acento(t or "").upper().strip())
    return TIPOS.get(t)


def _foto_e_pagina(rede: Rede) -> dict[str, dict]:
    t = rede.texto(f"{SITE}/parlamentares/", "site-parlamentares.html", 20)
    i = t.find('id="parlamentares-modo-fotos"')
    out = {}
    for li in re.findall(r"<li>(.*?)</li>", t[i:], re.S):
        m = re.search(r"href='(/parlamentar/[^']+)'", li)
        n = re.search(r'class="title parlamentares-nome">(.*?)<', li)
        f = re.search(r'<img[^>]+src="([^"]+)"', li)
        if m and n:
            out[chave_nome(html.unescape(n.group(1)))] = {"url": SITE + m.group(1), "foto": html.unescape(f.group(1)) if f else None}
    return out


def _resumo_detalhe(xml: str) -> dict:
    d = ET.fromstring(xml.encode("utf-8"))
    ev = [(data_iso(e.get("data")), (e.findtext("acao") or "").strip()) for e in d.iter("evento")]
    aut = d.find("autografo")
    return {"res": (d.findtext("resultadoFinal") or "").strip() or None, "conj": (d.findtext("tramitacaoConjunta") or "").strip().rstrip(".") or None,
            "lei": (aut.findtext("lei") or "").strip() if aut is not None else None,
            "lres": (aut.findtext("resultado") or "").strip() if aut is not None else None,
            "ev": ev[-6:], "lido": hoje()}


def _lei_en(nome: str, numero: str, ano: str | None) -> str:
    tipo = {"Lei Complementar": "complementary law", "Resolução": "resolution", "Emenda Constitucional": "constitutional amendment",
            "Decreto Legislativo": "legislative decree"}.get(nome, "law")
    n = f"{int(numero):,}" if numero.isdigit() else numero
    return f"{tipo} no. {n}" + (f" of {ano}" if ano else "")


def _situacao(v: dict, principal: dict | None = None) -> dict:
    det = v.get("det") or {}
    ev = det.get("ev") or []
    data = ev[-1][0] if ev else None
    res = sem_acento((det.get("res") or "").lower())
    lres = sem_acento((det.get("lres") or "").lower())
    acoes = sem_acento(" | ".join(a for _, a in ev).lower())
    if det.get("lei") and det["lei"].isdigit() and "veto total" not in lres:
        nome, tn = NORMA[v["t"]]
        quando = next((d for d, a in reversed(ev) if re.search(r"tran[s]?formado em|promulgad|sancionad", sem_acento(a.lower()))), None) or data
        ano = (quando or "")[:4] or None
        nl = nome_lei(nome, det["lei"], ano)
        url = (f"https://legis.alepe.pe.gov.br/texto.aspx?tiponorma={tn}&numero={det['lei']}&complemento=0&ano={ano}&tipo="
               if tn and ano else None)
        parcial = "parcial" in lres
        return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}" + (" (com partes vetadas)" if parcial else ""),
                "en": None, "data": quando, "lei": {"nome": nl, "url": url}, "en_lei": _lei_en(nome, det["lei"], ano)}
    if "veto total" in lres or "veto total" in res:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor", "data": data, "lei": None}
    # votada junto com outro projeto (tramitação conjunta): a Alepe dá o número da lei só ao projeto principal; os outros
    # ficam em "Enviado para redação final"
    if principal and re.search(r"redacao final|aprovad", res):
        art = "o" if principal["lei"]["nome"].startswith("Decreto") else "a"
        art_p = "a" if principal["sigla"].startswith("PEC") else "o"
        return {"status": "aprovada", "txt": f"Aprovada junto com {art_p} {principal['sigla']}, que virou {art} {principal['lei']['nome']}",
                "en": f"Approved together with {principal['sigla']}, which became {principal['en_lei']}", "data": data, "lei": principal["lei"]}
    regras = [
        (r"desarquivad", "andando", None, None),
        (r"retirad", "retirada", None, None),
        (r"rejeitad", "rejeitada", "Rejeitada", None),
        (r"prejudicad", "parada", "Ficou prejudicada", None),
        (r"arquivad", "arquivada", "Arquivada", None),
        (r"autografo (promulgado|sancionado)", "lei", "Virou norma; o número ainda não foi informado",
         "Became law; the number has not been published yet"),
        (r"autografo (criado|enviado)|sancao|promulgacao", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
         "Approved; sent to the governor to sign or veto"),
        (r"redacao final", "aprovada", "Aprovada; falta votar a redação final", "Approved; the final wording still needs a vote"),
        (r"retornad[oa] para o autor|devolvid[oa] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    ]
    for exp, st, pt, en in regras:
        if re.search(exp, res):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    if det.get("conj"):
        return {"status": "junta", "txt": f"Andando junto com outra proposta parecida ({det['conj']})", "en": None, "data": data, "lei": None}
    if res or acoes:
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


def coletar() -> dict:
    rede = Rede("alepe", pausa=0.5, timeout=120)
    oficiais = rede.json(f"{API}/parlamentares?formato=json", "parlamentares.json", 20)
    if not isinstance(oficiais, list) or not 40 <= len(oficiais) <= 55:
        raise RuntimeError(f"Alepe: lista de parlamentares inesperada ({type(oficiais).__name__})")
    site = _foto_e_pagina(rede)
    # projetos da legislatura (lista completa, 1 pedido) + detalhe em rodízio
    lst = ET.fromstring(rede.bruto(f"{API}/proposicoes/projetos/?legislatura={legislatura_estadual(20)}",
                                   f"projetos-leg{legislatura_estadual(20)}.xml", 20))
    est = rede.estado("estado.json", {}) or {}
    det: dict = est.get("det") or {}
    projetos = {}
    for p in lst:
        tp = _tipo(p.get("tipo"))
        autores = [(a.get("nome") or "").strip() for a in p.iter("autor")]
        if not tp or not any(a.get("tipo") == "DEPUTADO" for a in p.iter("autor")):
            continue
        d = data_iso(p.get("dataPublicacao"))
        # projetos de legislaturas passadas que foram desarquivados também aparecem na lista: ficam de fora (escopo: desde 1º/2/2023)
        if (d and d < INICIO) or int(p.get("ano") or 0) < int(INICIO[:4]):
            continue
        projetos[p.get("docid")] = {"t": tp[0], "s": tp[1], "n": p.get("numero"), "a": p.get("ano"), "d": d,
                                    "e": (p.get("ementa") or "").strip(), "au": autores}
    h = dt.date.fromisoformat(hoje())

    def vencido(docid: str) -> bool:
        x = det.get(docid)
        if not x:
            return True
        terminou = re.search(r"autografo (promulgado|sancionado)|(?<!des)arquivad|retirad|rejeitad|prejudicad", sem_acento((x.get("res") or "").lower()))
        dias = (h - dt.date.fromisoformat(x["lido"])).days
        return dias >= (RELER_FIM if terminou else RELER_ANDANDO)

    fila = sorted([k for k in projetos if vencido(k)], key=lambda k: (k in det, (det.get(k) or {}).get("lido") or "", -int(k)))
    t0, lidos = time.time(), 0
    sem_limite = __import__("os").environ.get("NE_SEM_LIMITE") == "1"
    for k in fila:
        if time.time() - t0 > ORCAMENTO_S and not sem_limite:
            break
        try:
            det[k] = _resumo_detalhe(rede.texto(f"{API}/proposicoes/projetos/?docid={k}&tipoprop=p"))
            lidos += 1
        except Exception as e:
            log(f"  PE: detalhe {k} falhou ({e})")
        if lidos % 50 == 0:
            rede.guardar({"det": det}, "estado.json")
    det = {k: v for k, v in det.items() if k in projetos}
    rede.guardar({"det": det}, "estado.json")
    sem_det = sum(1 for k in projetos if k not in det)
    log(f"  PE: {len(projetos)} projetos de deputados na legislatura; {lidos} detalhes lidos hoje; {sem_det} ainda sem detalhe")
    # pessoas
    pessoas = []
    for o in oficiais:
        nome = (o.get("nomeParlamentar") or "").strip()
        s = site.get(chave_nome(nome)) or {}
        pessoas.append({"chave": nome, "nome": nome, "nomeCivil": None, "partido": partido_sigla(o.get("partido")), **s})
    ligados, avisos = casar_membros("PE", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  PE TSE: {a}")
    por_nome: dict[str, list[tuple[str, str]]] = {}
    for k, v in projetos.items():
        for i, a in enumerate(v["au"]):
            por_nome.setdefault(chave_nome(a), []).append((k, "autor" if i == 0 else "coautor"))
    por_numero = {(v["s"], v["n"], v["a"]): k for k, v in projetos.items()}

    def principal(v: dict) -> dict | None:
        """O projeto da tramitação conjunta que virou lei (a Alepe só põe o número da lei nele)."""
        conj = (v.get("det") or {}).get("conj") or ""
        pares = re.findall(r"(\d+)/(\d{4})", conj) or [(n, v["a"]) for n in re.findall(r"\b(\d+)\b", conj)]
        for n, a in pares:
            k = por_numero.get((v["s"], n, a))
            if k and det.get(k):
                s = _situacao(dict(projetos[k], det=det[k]))
                if s["status"] == "lei" and s["lei"]:
                    return {"sigla": f"{projetos[k]['s']} {n}/{a}", "lei": s["lei"], "en_lei": s["en_lei"]}
        return None

    membros, extras, listas = [], {}, []
    fonte_l = fonte(VEICULO, "Parlamentares da legislatura atual (Portal de Dados Abertos)", f"{API}/parlamentares?formato=json")
    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "PE", cand, p["nome"])
        url = p.get("url") or f"{SITE}/parlamentares/"
        membros.append(membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p.get("foto"), url))
        lista = []
        for k, papel in por_nome.get(chave_nome(p["nome"]), []):
            v = dict(projetos[k], det=det.get(k))
            s = _situacao(v, principal(v)) if v["det"] else {"status": "outra", "txt": "Situação ainda não consultada", "en": "Status not checked yet",
                                                                "data": None, "lei": None}
            prop = regional.proposta(f"alepe:{k}", f"{v['s']} {v['n']}/{v['a']}", v["t"], v["d"], v["e"],
                                     (v["det"] or {}).get("res"), f"https://proposicoes.alepe.pe.gov.br/proposicoes/detalhes?docid={k}&tipoprop=p",
                                     papel=papel, status=s["status"], data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Projetos de {p['nome']} na {legislatura_estadual(20)}ª legislatura (Portal de Dados Abertos)",
                        f"https://proposicoes.alepe.pe.gov.br/")
        extras[pid] = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
                       "links": {"oficial": url, "email": None, "redes": []}, "fontes": [fonte_l, fonte_p]}
    log(f"  PE: situações {resumo_status(listas)}")
    notas = [("A lista de projetos vem do Portal de Dados Abertos da Alepe; a situação de cada um é relida aos poucos "
              "(os que ainda tramitam, a cada 21 dias).",
              "The list of bills comes from the Alepe Open Data Portal; the status of each one is re-read gradually "
              "(those still under discussion, every 21 days).")]
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = gravar("PE", {"casa": "Assembleia Legislativa do Estado de Pernambuco", "casa_en": "Legislative Assembly of the State of Pernambuco",
                      "sigla": "Alepe", "site": SITE}, membros, extras, cobertura, fonte_l, notas)
    log(f"  PE: {rede.pedidos} pedidos ao site oficial")
    return r


TSE_MANUAL: dict[str, str] = {}
