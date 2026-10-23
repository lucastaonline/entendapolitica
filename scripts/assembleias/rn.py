"""Assembleia Legislativa do Estado do Rio Grande do Norte (ALRN): API do portal "Transparência Legislativa"
(https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/, a mesma que alimenta
https://transparencialegislativa.al.rn.leg.br) e API do site (https://www.al.rn.leg.br/api/deputados).

Lista: /parlamentar (os 24 deputados com mandato em vigor, com o partido de hoje pela filiação sem data de fim e o nome
completo), ligada pelo nome à lista do site (página oficial e e-mail de cada um). Foto: a da própria API.
Propostas: /processo?tipoPropositura=..&dataInicio=2023-02-01 (projetos de lei, de lei complementar, de emenda
constitucional, de decreto legislativo, de resolução e de resolução de título honorífico), com o autor (iniciativa), o
número da lei quando virou lei (informacaoLei) e a data de arquivamento. A situação das outras vem da tramitação de cada
processo (/processo/<id>/tramitacao), relida em rodízio (as novas na hora, as que ainda andam a cada 21 dias). Vetos do
governador: processos do tipo VETO ("Veto Integral ao Projeto de Lei 296/2026 ...").
"""
from __future__ import annotations

import datetime as dt
import os
import re
import time

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, nome_proprio, sem_acento, slug

from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, membro, nome_lei,
                        partido_sigla, resumo_status)

API = "https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa"
SITE = "https://www.al.rn.leg.br"
PORTAL = "https://transparencialegislativa.al.rn.leg.br"
VEICULO = "Assembleia Legislativa do Rio Grande do Norte (ALRN)"
TIPOS = {1: ("PL", "PL", "Lei"), 2: ("PLP", "PLC", "Lei Complementar"), 7: ("PEC", "PEC", "Emenda Constitucional"),
         6: ("PDL", "PDL", "Decreto Legislativo"), 8: ("PRC", "PRES", "Resolução"), 22: ("PRC", "PRTH", "Resolução")}
VETO = 21
RELER_ANDANDO, ORCAMENTO_S = 21, 150

# situação da última tramitação (texto oficial sem acento, minúsculas) -> status do site (conferido numa amostra: ver as
# notas da frente ale-nordeste)
REGRAS = [
    (r"transformad[ao] em (lei|norma)|lei sancionada|promulgad|sancionad", "lei", "Virou lei", None),
    (r"veto (total|integral)|vetad[ao] (totalmente|integralmente)", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"retirad[ao] (pel[oa] autor|a pedido|de tramitacao)", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"anuncio de prejudicialidade", "parada", "Vai ser declarada prejudicada (aguarda o anúncio)",
     "About to be declared moot (awaiting the announcement)"),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"sugerido o arquivamento", "andando", "Foi sugerido o arquivamento; ainda falta a decisão",
     "Shelving was suggested; there is no final decision yet"),
    (r"arquivad|arquivamento", "arquivada", "Arquivada", None),
    (r"desapensad", "andando", None, None),
    (r"apensad|apensamento|anexad|tramitacao conjunta", "junta", None, None),
    (r"sancao|autografo|aguardando promulgacao", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"aprovad[ao] (em|no|pelo) plenario|aprovad[ao] em (discussao|votacao|turno unico|segundo turno|2)", "aprovada", None, None),
    (r".", "andando", None, None),
]


def _lei(info: str | None, nome: str) -> dict | None:
    """'Nº 12835 de 13/07/2026 - DOE 14/07/2026' -> {"nome": "Lei nº 12.835/2026", ...}"""
    m = re.search(r"n[º°o]\.?\s*([\d.]+)\s*(?:,?\s*de\s*(\d{2}/\d{2}/(\d{4})))?", sem_acento(info or "").lower().replace("º", "o"))
    if not m:
        return None
    num = m.group(1).replace(".", "")
    return {"nome": nome_lei(nome, num, m.group(3)), "data": data_iso(m.group(2)) if m.group(2) else None}


def coletar() -> dict:
    rede = Rede("alrn", pausa=0.5, timeout=90)
    parls = rede.json(f"{API}/parlamentar", "parlamentar.json", 20).get("dados") or []
    h = hoje()
    vigentes = [p for p in parls if (p.get("vigencia") or {}).get("inicio", "")[:10] <= h
                and ((p.get("vigencia") or {}).get("fim") or "9999")[:10] >= h]
    if not 20 <= len(vigentes) <= 30:
        raise RuntimeError(f"ALRN: {len(vigentes)} deputados com mandato em vigor (esperado: 24)")
    site = {chave_nome(d["nome"]): d for d in rede.json(f"{SITE}/api/deputados", "site-deputados.json", 20)}
    # propostas
    est = rede.estado("estado.json", {}) or {}
    tram: dict = est.get("tram") or {}
    procs: dict[str, dict] = {}
    for tp in list(TIPOS) + [VETO]:
        pag = 0
        while True:
            d = rede.json(f"{API}/processo?pagina={pag}&tamanhoPagina=100&tipoPropositura={tp}&dataInicio={INICIO}")
            for x in d.get("dados") or []:
                procs[str(x["id"])] = {"tp": tp, "n": (x.get("propositura") or {}).get("numero"), "a": (x.get("propositura") or {}).get("ano"),
                                       "d": data_iso(x.get("dataEntrada")), "e": (x.get("ementa") or "").strip(),
                                       "ini": (x.get("iniciativa") or {}).get("id"), "lei": x.get("informacaoLei"),
                                       "arq": data_iso(x.get("dataArquivamento")), "proc": f"{x.get('numero')}/{x.get('ano')}",
                                       "ap": (x.get("apensamento") or {}).get("id") if isinstance(x.get("apensamento"), dict) else None}
            if (pag + 1) * 100 >= int(d.get("total") or 0):
                break
            pag += 1
    vetos = {}
    for k, v in procs.items():
        if v["tp"] != VETO:
            continue
        e = sem_acento(v["e"].lower())
        m = re.search(r"veto (integral|total|parcial)[^.]{0,40}?projeto de (lei complementar|lei|resolucao)\D{0,8}([\d.]+)\s*/\s*(\d{4})", e)
        if m:
            tipo = {"lei complementar": 2, "lei": 1, "resolucao": 8}[m.group(2)]
            vetos[(tipo, int(m.group(3).replace(".", "")), int(m.group(4)))] = {"total": m.group(1) != "parcial", "d": v["d"]}
    ids_dep = {i["id"] for p in vigentes for i in p.get("iniciativas") or []}
    alvo = [k for k, v in procs.items() if v["tp"] != VETO and v["ini"] in ids_dep and not v["lei"] and not v["arq"]]
    hoje_d = dt.date.fromisoformat(h)

    def vencido(k: str) -> bool:
        x = tram.get(k)
        return not x or (hoje_d - dt.date.fromisoformat(x["lido"])).days >= RELER_ANDANDO

    fila = sorted([k for k in alvo if vencido(k)], key=lambda k: (k in tram, (tram.get(k) or {}).get("lido") or "", -int(k)))
    t0, lidos, sem_limite = time.time(), 0, os.environ.get("NE_SEM_LIMITE") == "1"
    for k in fila:
        if time.time() - t0 > ORCAMENTO_S and not sem_limite:
            break
        try:
            tr = rede.json(f"{API}/processo/{k}/tramitacao")
        except Exception as e:
            log(f"  RN: tramitação {k} falhou ({e})")
            continue
        ult = max(tr, key=lambda t: ((t.get("origem") or {}).get("data") or "", t.get("id") or 0)) if tr else None
        tram[k] = {"lido": h, "st": ((ult or {}).get("situacaoProcesso") or {}).get("nome"),
                   "d": data_iso(((ult or {}).get("origem") or {}).get("data")), "n": len(tr),
                   "tudo": sem_acento(" | ".join(((t.get("situacaoProcesso") or {}).get("nome") or "") for t in tr).lower())[:1500]}
        lidos += 1
        if lidos % 50 == 0:
            rede.guardar({"tram": tram}, "estado.json")
    tram = {k: v for k, v in tram.items() if k in procs}
    rede.guardar({"tram": tram}, "estado.json")
    log(f"  RN: {sum(1 for v in procs.values() if v['tp'] != VETO)} propostas desde 2023; {lidos} tramitações lidas hoje; "
        f"{sum(1 for k in alvo if k not in tram)} ainda sem tramitação")
    # pessoas
    pessoas = []
    for p in vigentes:
        nome = re.sub(r"^\s*deputad[oa]\s+", "", p.get("nomeParlamentar") or "", flags=re.I).strip()
        nome = nome_proprio(nome) if nome == nome.upper() else nome
        filiacao = [f for f in p.get("filiacoes") or [] if not (f.get("vigencia") or {}).get("fim")]
        partido = partido_sigla(((filiacao or [{}])[-1].get("partido") or {}).get("nome")) if filiacao else None
        civil = ((p.get("pessoa") or {}).get("nome") or "").strip()
        s = site.get(chave_nome(nome)) or {}
        pessoas.append({"chave": str(p["id"]), "nome": s.get("nome") or nome, "nomeCivil": nome_proprio(civil) if civil else None,
                        "partido": partido, "ini": {i["id"] for i in p.get("iniciativas") or []}, "elegis": p["id"], "site": s,
                        "inicio": ((p.get("vigencia") or {}).get("inicio") or "")[:10] or None,
                        "fim": ((p.get("vigencia") or {}).get("fim") or "")[:10] or None})
    ligados, avisos = casar_membros("RN", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  RN TSE: {a}")
    membros, extras, listas = [], {}, []
    fonte_l = fonte(VEICULO, "Deputados com mandato em vigor (Transparência Legislativa, API)", f"{PORTAL}/")
    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "RN", cand, p["nome"])
        s = p["site"]
        url = f"{SITE}/deputado/{s['id']}/{slug(s['nome'])}" if s.get("id") else f"{SITE}/deputados"
        foto = f"{API}/parlamentar/fotografia/{p['elegis']}"
        membros.append(membro(pid, p["nome"], p["nomeCivil"], p["partido"], (cand or {}).get("genero"), foto, url))
        lista = []
        for k, v in procs.items():
            if v["tp"] == VETO or v["ini"] not in p["ini"]:
                continue
            tipo, sigla, nome_norma = TIPOS[v["tp"]]
            s_ = _situacao(k, v, tram.get(k), vetos, nome_norma)
            prop = regional.proposta(f"alrn:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], s_["sit"],
                                     f"{PORTAL}/projeto/{k}", papel="autor", status=s_["status"], data_status=s_["data"],
                                     status_txt=s_["txt"], lei=s_["lei"])
            lista.append(com_status_en(prop, s_["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Projetos de {p['nome']} (Transparência Legislativa)", f"{PORTAL}/")
        x = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
             "links": {"oficial": url, "email": (s.get("email") or "").strip() or None, "redes": []},
             "fontes": [fonte_l, fonte_p]}
        if p["inicio"]:
            x["mandato"] = {"inicio": p["inicio"], "fim": p["fim"] or "2027-01-31", "situacao": "Em exercício", "obs": None, "fonte": fonte_l}
        extras[pid] = x
    log(f"  RN: situações {resumo_status(listas)}")
    notas = [("A ALRN registra só o autor principal de cada projeto (sem coautores). A situação dos projetos que ainda "
              "tramitam é relida aos poucos (cada um a cada 21 dias).",
              "The ALRN only records the main author of each bill (no co-authors). The status of bills still under "
              "discussion is re-read gradually (each one every 21 days).")]
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = gravar("RN", {"casa": "Assembleia Legislativa do Estado do Rio Grande do Norte",
                      "casa_en": "Legislative Assembly of the State of Rio Grande do Norte", "sigla": "ALRN", "site": SITE},
               membros, extras, cobertura, fonte_l, notas)
    log(f"  RN: {rede.pedidos} pedidos ao site oficial")
    return r


def _situacao(k: str, v: dict, tr: dict | None, vetos: dict, nome_norma: str) -> dict:
    if v.get("lei"):
        l = _lei(v["lei"], nome_norma)
        if l:
            return {"status": "lei", "txt": f"Virou {'o' if nome_norma.startswith('Decreto') else 'a'} {l['nome']}", "en": None,
                    "data": l["data"], "lei": {"nome": l["nome"], "url": None}, "sit": v["lei"]}
        return {"status": "lei", "txt": "Virou lei", "en": None, "data": None, "lei": None, "sit": v["lei"]}
    vt = vetos.get((v["tp"] if v["tp"] != 22 else 8, int(v["n"] or 0), int(v["a"] or 0)))
    if vt and vt["total"]:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor",
                "data": vt["d"], "lei": None, "sit": "Veto integral"}
    if v.get("arq"):
        return {"status": "arquivada", "txt": "Arquivada", "en": None, "data": v["arq"], "lei": None, "sit": "Arquivado"}
    if v.get("ap"):
        return {"status": "junta", "txt": None, "en": None, "data": None, "lei": None, "sit": "Anexado a outro processo"}
    if not tr:
        return {"status": "outra", "txt": "Situação ainda não consultada", "en": "Status not checked yet", "data": None, "lei": None, "sit": None}
    t = sem_acento((tr.get("st") or "").lower())
    for exp, st, pt, en in REGRAS:
        if re.search(exp, t):
            return {"status": st, "txt": pt, "en": en, "data": tr.get("d"), "lei": None, "sit": tr.get("st")}
    return {"status": "outra", "txt": None, "en": None, "data": tr.get("d"), "lei": None, "sit": tr.get("st")}


TSE_MANUAL: dict[str, str] = {}
