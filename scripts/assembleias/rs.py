"""Assembleia Legislativa do Estado do Rio Grande do Sul (ALRS): o serviço de dados do portal da ALRS (o mesmo que a
página "Deputados" usa) e as páginas oficiais de proposições de cada deputado.

Lista: https://ww4.al.rs.gov.br:5000/listarDestaqueDeputados (JSON usado pela página oficial "Deputados"): nome,
partido de hoje, e-mail, foto e código de cada deputado em exercício (55 cadeiras).
Propostas: a página oficial "Proposições" de cada deputado (ww4.al.rs.gov.br/deputados/<código>/proposicoes) traz,
dentro dela, a lista do sistema de processo legislativo da ALRS (ePRO) em JSON: tipo, número, ano, proponente,
situação atual e histórico, ementa. Entram PL, PLC (= PLP), PEC, PDL e PR (= PRC) protocolados desde 1º/2/2023. O
proponente principal é o autor; quando a lista mostra "Deputado(a) X + N Deputado(s)", X é o autor principal.
As páginas são lentas (~8 s cada): cada deputado é conferido a cada 3 dias (um terço por dia, em rodízio).
Situação: o texto oficial ("descricao") com as regras REGRAS.
Votações nominais: a página de cada proposição mostra a "Planilha de Votação" (voto de cada deputado), mas só em HTML,
proposição por proposição; não entram por enquanto. Gastos: não há publicação aberta da verba de cada gabinete.
"""
from __future__ import annotations

import json
import re

import regional
from comum import PESSOAS, chave_nome, data_iso, hoje, ler_json, log

from ._sse_comum import (Rede, casar_membros, com_status_en, desde, dia_rodizio, escopo, fonte, gravar, legislatura,
                         membro, partido_sigla, resumo_status)

UF = "RS"
SITE = "https://ww4.al.rs.gov.br"
VEICULO = "Assembleia Legislativa do Estado do Rio Grande do Sul (ALRS)"
CASA = {"casa": "Assembleia Legislativa do Estado do Rio Grande do Sul",
        "casa_en": "Legislative Assembly of the State of Rio Grande do Sul", "sigla": "ALRS", "site": SITE}
INICIO = legislatura(UF)["inicio"]  # 2023-01-31 (posse no RS: Constituição do RS, art. 49, § 3º)
TIPOS = {"PL": "PL", "PLC": "PLP", "PEC": "PEC", "PDL": "PDL", "PR": "PRC"}

REGRAS = [
    (r"^(sancionad|promulgad)", "lei"),
    (r"^vetad|veto total", "rejeitada"),
    (r"^retirad", "retirada"),
    (r"^(prejudicad|devolvid)", "parada"),
    (r"^rejeitad", "rejeitada"),
    (r"^arquivad", "arquivada"),
    (r"^(apensad|anexad)", "junta"),
    (r"^aprovad|^aguardando sancao|^encaminhad[oa] a sancao|^redacao final aprovada", "aprovada"),
    # "Tramitação Concluída" e "Solucionado(a)" aparecem sem votação nem norma na página oficial: não dá para dizer
    # como acabou (conferido em PR 3/2023 e PL 293/2025)
    (r"^(tramitacao concluida|solucionad)", "outra"),
    (r"^(entrada|autuad|pauta|para parecer|ordem do dia|publicad|diligencia|comissao|em tramitacao|para redacao|"
     r"redacao final|leitura|recebid|distribu|aguardando|em discussao|em votacao|baixad|vista|com parecer|pedido de vista|"
     r"votacao conclusiva|tramitacao suspensa)", "andando"),
]

# ligações com o TSE conferidas à mão: {código do deputado na ALRS: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], list[str]]:
    d = rede.json(f"{SITE}:5000/listarDestaqueDeputados", "deputados.json", 20)
    lista = [x for x in d.get("lista") or [] if str(x.get("codStatus")) == "1"]
    if not 45 <= len(lista) <= 60:
        raise RuntimeError(f"ALRS: a lista oficial veio com {len(lista)} pessoas")
    pessoas = [{"chave": str(x["idDeputado"]), "nome": (x.get("nomeDeputado") or "").strip(), "nomeCivil": None,
                "partido": partido_sigla(x.get("siglaPartido")), "email": x.get("emailDeputado"),
                "foto": x.get("fotoGrandeDeputado")} for x in lista]
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], f"{SITE}/deputados/{p['chave']}",
                   (cand or {}).get("sit") == "SUPLENTE")
        m["_email"] = p["email"]
        membros.append(m)
    return membros, ids, avisos


def _lista(rede: Rede, cod: str) -> list[dict]:
    t = rede.texto(f"{SITE}/deputados/{cod}/proposicoes", f"proposicoes/{cod}.html", 20 if dia_rodizio(cod, 3) else 24 * 4,
                   timeout=180)
    m = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', t, re.S)
    if not m:
        raise RuntimeError(f"ALRS: página de proposições do deputado {cod} sem a lista")
    p = (json.loads(m.group(1)).get("alergs_deputados") or {}).get("proposicoes") or {}
    if str(p.get("statusCodeRequest")) != "200":
        raise RuntimeError(f"ALRS: o sistema de proposições respondeu {p.get('statusCodeRequest')} para o deputado {cod}")
    return (p.get("body") or {}).get("lista") or []


def coletar() -> dict:
    rede = Rede("alrs", pausa=1.0)
    membros, ids, avisos = _membros(rede)
    for a in avisos:
        log(f"  RS: {a}")
    hj = hoje()
    nomes = {chave_nome(m["nome"]): k for k, pid in ids.items() for m in membros if m["id"] == pid}
    por_dep: dict[str, list] = {}
    falhas = 0
    for k in ids:
        try:
            lista = _lista(rede, k)
        except Exception as e:  # um deputado fora do ar não derruba os outros: fica a lista da rodada anterior
            falhas += 1
            log(f"  RS: {e}")
            antes = ((ler_json(PESSOAS / f"{ids[k]}.json", {}) or {}).get("propostas") or {}).get("lista")
            if antes:
                por_dep[k] = antes
            continue
        for x in lista:
            sig = (x.get("siglaTipoProposicao") or "").strip().upper()
            data = data_iso(x.get("dthProtocolo")) or data_iso((x.get("situacoesPorPeriodo") or [{}])[-1].get("data"))
            if sig not in TIPOS or (data or "") < INICIO:
                continue
            prop = re.sub(r"(?i)^deputad[oa]\(a\)\s*|\s*\+\s*\d+\s*deputad.*$", "", x.get("nomeProponente") or "").strip()
            papel = "autor" if nomes.get(chave_nome(prop)) == k else "coautor"
            num, ano = x.get("nroProposicao"), x.get("anoProposicao")
            p = regional.proposta(f"alrs:{sig}-{num}-{ano}", f"{sig} {num}/{ano}", TIPOS[sig], data, x.get("ementa"),
                                  (x.get("descricao") or "").strip() or None, f"{SITE}/proposicao/{sig}/{num}/{ano}",
                                  papel=papel, data_status=data_iso(x.get("dthSituacaoProposicao")), regras=REGRAS)
            if p["status"] == "aprovada":
                com_status_en(p, "Aprovada pela Assembleia; segue para a sanção ou o veto do governador",
                              "Approved by the Assembly; it goes to the governor to sign or veto")
            elif p["status"] == "rejeitada" and re.match(r"(?i)vetad", p["situacao"] or ""):
                com_status_en(p, "Aprovada pela Assembleia, mas vetada pelo governador", "Approved by the Assembly, but vetoed by the governor")
            elif re.match(r"(?i)tramita[cç][aã]o suspensa", p["situacao"] or ""):
                com_status_en(p, "Ainda em discussão, mas com a tramitação suspensa", "Still under discussion, but its processing is on hold")
            por_dep.setdefault(k, []).append(p)
    if falhas > len(ids) // 3:
        raise RuntimeError(f"ALRS: {falhas} páginas de proposições falharam")
    f_lista = fonte(VEICULO, "Deputados em exercício (serviço de dados da página oficial \"Deputados\")", f"{SITE}/deputados", hj)
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"))
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        f_prop = fonte(VEICULO, f"Proposições de {m['nome']} (página oficial)", f"{SITE}/deputados/{k}/proposicoes", hj)
        extras[m["id"]] = {"links": {"oficial": m["url"], "email": m.pop("_email", None), "redes": []},
                           "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                           "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da ALRS", m["url"], hj)]}
    log(f"  RS: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    notas = [("A ALRS mostra o voto de cada deputado na página de cada proposição (HTML); as votações ainda não entram.",
              "The ALRS shows each deputy's vote on each bill's page (HTML only); votes are not included yet."),
             ("A lista de propostas de cada deputado mostra quem apresentou; quem só assinou junto pode não aparecer.",
              "Each deputy's list shows the bills they filed; co-signers may not appear.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
