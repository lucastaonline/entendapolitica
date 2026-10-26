"""Assembleia Legislativa do Estado do Maranhão (Alema): sistema legislativo AlemaLegis, com API pública
(https://alemalegis.al.ma.leg.br/api/v1/public/, a mesma que alimenta https://alemalegis.al.ma.leg.br/; o endereço antigo
sapl.al.ma.leg.br leva para lá).

Lista: /parliamentary?activeInHouse=ACTIVE&legislature=<atual> (42 pessoas, com o partido de hoje). As fotos do sistema
são links temporários (expiram em uma hora), então ficam as fotos do TSE.
Propostas: /legislative-matter/filter/access?legislativeMatterTypeId=..&year=.. (projetos de lei ordinária, de lei
complementar, de emenda constitucional, de decreto legislativo e de resolução legislativa) desde 1º/2/2023, com os
autores, a situação ("situation") e a norma que a proposta virou ("legalNorms"). Vetos: tipos Veto Total e Veto Parcial.
"""
from __future__ import annotations

import re

import regional
from comum import chave_nome, fonte, hoje, log, sem_acento

from . import _ne_gov as gv
from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, legislatura_estadual, membro,
                        nome_lei, partido_sigla, resumo_status)

API = "https://alemalegis.al.ma.leg.br/api/v1/public"
SITE = "https://alemalegis.al.ma.leg.br"
VEICULO = "Assembleia Legislativa do Maranhão (Alema)"
TIPOS = {10110: ("PL", "PLO"), 10114: ("PLP", "PLC"), 10123: ("PEC", "PEC"), 10115: ("PDL", "PDL"), 10111: ("PRC", "PRE")}
TIPOS_GOV = {10110: ("PL", "PLO"), 10114: ("PLP", "PLC"), 10123: ("PEC", "PEC"), 10115: ("PDL", "PDL"), 10118: ("MPV", "MPV")}
VETOS = {10120: True, 10124: False}
NORMA = [(r"lei complementar", "Lei Complementar"), (r"emenda", "Emenda Constitucional"), (r"decreto legislativo", "Decreto Legislativo"),
         (r"resolu", "Resolução"), (r"^lei", "Lei")]

# situação oficial (sem acento, minúsculas) -> status do site
REGRAS = [
    (r"transformad[ao] em (lei|norma)|lei sancionada|promulgad|sancionad", "lei", "Virou lei", None),
    (r"veto .*mantido|veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto .*rejeitado|veto .*derrubado", "aprovada", "Aprovada; o veto do governador foi derrubado e falta promulgar",
     "Approved; the governor's veto was overridden and it still has to be promulgated"),
    (r"retirad[ao] (pel[oa] autor|a pedido)", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"arquivad", "arquivada", "Arquivada", None),
    (r"anexad|apensad", "junta", None, None),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando sancao|autografo", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"parecer contrario", "andando", "Uma comissão deu parecer contra; falta a decisão final",
     "A committee recommended rejecting it; the final decision is pending"),
    (r"aprovad[ao] (em|no|pelo) plenario|aprovad[ao] em (discussao|votacao|turno unico|segundo turno|2)", "aprovada", None, None),
    (r"tramitacao inicial", "andando", "Apresentada; ainda vai começar a ser analisada", None),
    (r".", "andando", None, None),
]


def _norma(desc: str | None) -> str | None:
    d = sem_acento((desc or "").lower()).strip()
    for exp, nome in NORMA:
        if re.search(exp, d):
            return nome
    return None


def _legislatura(rede: Rede) -> dict:
    """A legislatura em curso pelo número (a Alema cadastra as legislaturas de 1º de janeiro a 31 de dezembro, mas a posse
    é em 1º de fevereiro: art. 29, § 3º, da Constituição do Maranhão)."""
    legs = rede.json(f"{API}/legislature", "legislaturas.json", 24 * 7)
    n = str(legislatura_estadual(20))
    for l in legs:
        if str(l.get("legislatureNumber")) == n:
            return l
    raise RuntimeError(f"Alema: legislatura {n} não encontrada")


def coletar() -> dict:
    rede = Rede("alema", pausa=0.5, timeout=90)
    leg = _legislatura(rede)
    d = rede.json(f"{API}/parliamentary?page=0&size=100&sort=parliamentaryName,asc&activeInHouse=ACTIVE&legislature={leg['id']}",
                  f"parlamentares-{leg['id']}.json", 20)
    ativos = d.get("content") or []
    if not 35 <= len(ativos) <= 50:
        raise RuntimeError(f"Alema: {len(ativos)} deputados ativos (esperado: 42)")
    # propostas: por tipo e por ano
    mats: dict[str, dict] = {}
    anos = range(int(INICIO[:4]), int(hoje()[:4]) + 1)
    for tp in list(TIPOS) + [10118] + list(VETOS):
        for ano in anos:
            pag = 0
            while True:
                r = rede.json(f"{API}/legislative-matter/filter/access?page={pag}&size=200&sort=number,desc&legislativeMatterTypeId={tp}&year={ano}")
                for x in r.get("content") or []:
                    mats[str(x["id"])] = {"tp": tp, "n": x.get("number"), "a": x.get("year"), "d": x.get("presentationDate"),
                                          "e": (x.get("ement") or "").strip(), "au": (x.get("authorNames") or "").strip(),
                                          "sit": (x.get("situation") or "").strip() or None, "da": x.get("forwardingDate"),
                                          "leis": x.get("legalNorms") or []}
                if pag + 1 >= int(r.get("totalPages") or 0):
                    break
                pag += 1
    vetos = {}
    for k, v in mats.items():
        if v["tp"] not in VETOS:
            continue
        m = re.search(r"projeto de lei( complementar)?( ordinaria)?\D{0,10}([\d.]+)\s*/\s*(\d{4})", sem_acento(v["e"].lower()))
        if m:
            vetos[(10114 if m.group(1) else 10110, str(int(m.group(3).replace(".", ""))), m.group(4))] = {"total": VETOS[v["tp"]], "d": v["d"]}
    log(f"  MA: {sum(1 for v in mats.values() if v['tp'] in TIPOS)} propostas desde 2023 (todas as autorias); {len(vetos)} vetos ligados")
    # pessoas
    pessoas = [{"chave": str(p["id"]), "nome": re.sub(r"\s+", " ", (p.get("parliamentaryName") or "").strip()),
                "nomeCivil": re.sub(r"\s+", " ", (p.get("fullName") or "").strip()) or None,
                "partido": partido_sigla(((p.get("partyAffiliationId") or {}).get("partyAcronym"))), "id": p["id"]} for p in ativos]
    ligados, avisos = casar_membros("MA", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  MA TSE: {a}")
    por_nome: dict[str, list[tuple[str, str]]] = {}
    for k, v in mats.items():
        if v["tp"] not in TIPOS or (v["d"] or "") < INICIO:
            continue
        nomes = [n.strip() for n in re.split(r",|;| e (?=[A-ZÁÉÍÓÚ])", v["au"]) if n.strip()]
        for i, n in enumerate(nomes):
            por_nome.setdefault(chave_nome(n), []).append((k, "autor" if i == 0 else "coautor"))
    membros, extras, listas = [], {}, []
    fonte_l = fonte(VEICULO, f"Parlamentares em atividade na {leg.get('legislatureNumber')}ª legislatura (AlemaLegis)",
                    f"{SITE}/sapl/protocol/parliamentary/research")
    from tse import url_foto  # as fotos do sistema da Alema expiram; a do TSE (pública) vale para eleitos e suplentes

    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "MA", cand, p["nome"])
        url = f"{SITE}/sapl/protocol/parliamentary/details/{p['id']}"
        membros.append(membro(pid, p["nome"], p["nomeCivil"] if p["nomeCivil"] != p["nome"] else None, p["partido"],
                              (cand or {}).get("genero"), url_foto(2022, cand["sq"], "MA") if cand else None, url))
        lista = []
        for k, papel in por_nome.get(chave_nome(p["nome"]), []):
            v = mats[k]
            tipo, sigla = TIPOS[v["tp"]]
            s = _situacao(v, vetos)
            prop = regional.proposta(f"alema:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], v["sit"],
                                     f"{SITE}/sapl/protocol/legislative-matter/view/{k}", papel=papel, status=s["status"],
                                     data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Matérias legislativas de {p['nome']} (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")
        extras[pid] = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
                       "links": {"oficial": url, "email": None, "redes": []}, "fontes": [fonte_l, fonte_p]}
    log(f"  MA: situações {resumo_status(listas)}")
    notas = [("As fotos do sistema da Alema são links que expiram em uma hora; por isso aparecem as fotos do TSE.",
              "The photos in the Alema system are links that expire after one hour, so the photos from the TSE are shown.")]
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = gravar("MA", {"casa": "Assembleia Legislativa do Estado do Maranhão", "casa_en": "Legislative Assembly of the State of Maranhão",
                      "sigla": "Alema", "site": "https://www.al.ma.leg.br"}, membros, extras, cobertura, fonte_l, notas)
    try:
        _governo(rede, mats, vetos)
    except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
        log(f"  MA: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
    log(f"  MA: {rede.pedidos} pedidos ao site oficial")
    return r


def _governo(rede: Rede, mats: dict, vetos: dict) -> dict:
    """dados/pessoas/gov-MA.json: matérias do "PODER EXECUTIVO" (projetos e medidas provisórias), as leis do período no
    AlemaLegis e os vetos (matérias Veto Total e Veto Parcial)."""
    per = gv.periodo("MA")
    ini = per["inicio"]
    lista = []
    for k, v in mats.items():
        if v["tp"] not in TIPOS_GOV or (v["d"] or "") < ini or not gv.autor_do_executivo(v["au"], per):
            continue
        tipo, sigla = TIPOS_GOV[v["tp"]]
        s = _situacao(v, vetos)
        prop = regional.proposta(f"alema:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], v["sit"],
                                 f"{SITE}/sapl/protocol/legislative-matter/view/{k}", papel="autor", status=s["status"],
                                 data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
        lista.append(com_status_en(prop, s["en"]))
    fonte_prop = fonte(VEICULO, "Matérias de autoria do Poder Executivo (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")
    # vetos do governador recebidos no período
    vts = [v for v in mats.values() if v["tp"] in VETOS and (v["d"] or "") >= ini]
    totais = sum(1 for v in vts if VETOS[v["tp"]])
    # leis do período (o AlemaLegis não diz quem assinou cada uma: entram também as promulgadas pelo presidente da Assembleia)
    leis = 0
    for ano in range(int(ini[:4]), int(hoje()[:4]) + 1):
        pag = 0
        while True:
            d = rede.json(f"{API}/legal-norm/filter?page={pag}&size=100&year={ano}", f"gov-normas-{ano}-{pag}.json", 20)
            for x in d.get("content") or []:
                if ((x.get("legalNormType") or {}).get("description") in ("Lei", "Lei Ordinária", "Lei Complementar")
                        and (x.get("date") or "")[:10] >= ini):
                    leis += 1
            pag += 1
            if pag >= int(d.get("totalPages") or 0):
                break
    nota = (f"Leis: as {leis} leis ordinárias e complementares com data a partir de {gv.data_pt(ini)} registradas no AlemaLegis "
            f"(o sistema legislativo da Alema). O sistema não diz quem assinou cada lei, então entram também as promulgadas pelo "
            f"presidente da Assembleia (quando o governador não sanciona no prazo ou quando o veto é derrubado). Vetos: as matérias "
            f"\"Veto Total\" e \"Veto Parcial\" recebidas pela Assembleia desde {gv.data_pt(ini)}.")
    nota_en = (f"Laws: the {leis} ordinary and complementary laws dated from {gv.data_en(ini)} on in AlemaLegis (the Alema "
               f"legislative system). The system does not say who signed each law, so this also includes laws promulgated by the "
               f"Assembly's president (when the governor does not sign in time or a veto is overridden). Vetoes: the \"Veto Total\" "
               f"and \"Veto Parcial\" items received by the Assembly since {gv.data_en(ini)}.")
    fontes = [fonte(VEICULO, "Normas jurídicas (AlemaLegis)", f"{SITE}/sapl/protocol/legal-norm/research"),
              fonte(VEICULO, "Matérias Veto Total e Veto Parcial (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")]
    ex = gv.bloco_executivo(per, leis, len(vts), fontes, nota, nota_en, totais, len(vts) - totais)
    esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature",
                            "projetos de lei, de lei complementar e de emenda à Constituição do estado e medidas provisórias",
                            "bills, complementary bills, amendments to the state Constitution and provisional measures")
    nota_prop = ("Medidas provisórias (MP) valem como lei assim que o governador as publica, mas perdem a validade se a "
                 "Assembleia não as aprovar no prazo da Constituição do estado.",
                 "Provisional measures (MP) take effect as law as soon as the governor publishes them, but they expire if the "
                 "state legislature does not approve them within the deadline set by the state Constitution.")
    return gv.gravar_gov("MA", per, lista, esc, esc_en, fonte_prop, ex, fontes, nota_prop)


def _situacao(v: dict, vetos: dict) -> dict:
    for l in v.get("leis") or []:
        nome = _norma(l.get("description"))
        if nome and l.get("number"):
            nl = nome_lei(nome, l["number"], l.get("year"))
            return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None, "data": v.get("da"),
                    "lei": {"nome": nl, "url": None}}
    vt = vetos.get((v["tp"], str(v["n"]), str(v["a"])))
    if vt and vt["total"]:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor",
                "data": vt["d"], "lei": None}
    t = sem_acento((v.get("sit") or "").lower())
    if not t:
        return {"status": "outra", "txt": None, "en": None, "data": v.get("da"), "lei": None}
    for exp, st, pt, en in REGRAS:
        if re.search(exp, t):
            return {"status": st, "txt": pt, "en": en, "data": v.get("da"), "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": v.get("da"), "lei": None}


# conferidos à mão (nome na Alema -> candidato do TSE de 2022): "Ariston" é ARISTON GONÇALO (Ariston Ribeiro de Sousa,
# eleito pelo PSB); "Dra Vivianne" é DRA VIVIANNE (Vivianne Martins Coelho e Silva, eleita pelo PDT; a Alema escreve o nome
# civil como "Dra. Viviane").
TSE_MANUAL: dict[str, str] = {"107": "100001607069", "129": "100001599580"}
