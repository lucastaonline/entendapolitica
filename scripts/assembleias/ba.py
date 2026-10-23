"""Assembleia Legislativa do Estado da Bahia (Alba): portal legislativo (SPL) com API pública
(https://albalegis.nopapercloud.com.br/api/publico/, documentada em https://albalegis.nopapercloud.com.br/dados-abertos.aspx).
Desde 1º/8/2025 a Alba publica os dados dos deputados e das proposições nesse portal (aviso na página "Deputados" do site).

Lista: parlamentares da 20ª legislatura com situação "Ativo" (filtro da própria API: 63 pessoas, inclusive suplentes que
assumiram), conferida com a lista "Em exercício" do site da Alba. A API de parlamentares é muito lenta (cerca de 40 s por
página de 10), então ela fica guardada por até 3 dias; a lista do site, que é rápida, é lida todo dia e, se as duas não
baterem, a da API é baixada de novo.
Propostas: projetos de lei (PL), de lei complementar (PLC), de emenda constitucional (PEC), de decreto legislativo (PDL) e
de resolução (PRS) desde 1º/2/2023, com autor, coautores, situação e tramitações.
"""
from __future__ import annotations

import html
import re

from comum import chave_nome, log, sem_acento

from ._ne_comum import legislatura_estadual, nome_lei
from ._ne_nopaper import NoPaper, texto_tramitacoes, ultima

SITE_LISTA = "https://www.al.ba.gov.br/deputados/deputados-estaduais"


def _nomes_site(col) -> set[str]:
    t = col.rede.texto(SITE_LISTA, "site-em-exercicio.html", 20)
    nomes = re.findall(r'<option value="/deputados/deputado-estadual/\d+">\s*<span>(.*?)</span>', t, re.S)
    return {chave_nome(html.unescape(n)) for n in nomes if n.strip()}


def em_exercicio(col, ps: list[dict]) -> list[dict]:
    ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
    try:
        site = _nomes_site(col)
    except Exception as e:  # o site fora do ar não impede a lista da API
        log(f"  BA: lista do site indisponível ({e})")
        return ativos
    api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
    if site and site != api:
        ps = col.parlamentares(max_idade_h=20)
        ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
        api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
        if site != api:
            log(f"  BA: lista da API e do site diferentes. Só na API: {sorted(api - site)}; só no site: {sorted(site - api)}")
    return ativos


# Na Alba a "situação" da API não acompanha o fim do processo (projeto que virou lei pode continuar "TRAMITANDO"), então a
# situação vem das tramitações (frases conferidas à mão numa amostra; ver as notas da frente ale-nordeste):
# "Promulgada/Publicada a Lei nº ..." e "Sancionada Lei nº ..." = virou lei (o número da lei vem junto); o mesmo para
# Resolução; "Expedido autógrafo ao Governador" = aprovada e enviada para sanção; "Devolvido sem sanção ou veto" = o
# governador não decidiu no prazo e falta promulgar; "Aprovado em 1ª/2ª discussão" ou "em discussão única" = aprovada no
# Plenário; "Retirado de tramitação a pedido do autor" = o autor desistiu.
_NORMA = re.compile(r"(?:promulgad|publicad|sancionad)[ao]?\s+(?:a\s+)?(lei complementar|lei|resolucao|emenda constitucional|"
                    r"decreto legislativo)\s+n[o°º]?\.?\s*([\d.,]+)")
NOMES = {"lei complementar": "Lei Complementar", "lei": "Lei", "resolucao": "Resolução",
         "emenda constitucional": "Emenda Constitucional", "decreto legislativo": "Decreto Legislativo"}
REGRAS = [
    (r"(?<!pedido de )retirad[ao] de tramitacao|retirad[ao] pel[oa] autor|(?<!pedido de retirada )a pedido do autor", "retirada", None, None),
    (r"veto total|veto integral|vetad[oa] (totalmente|integralmente)", "rejeitada", "Vetada por inteiro pelo governador",
     "Fully vetoed by the governor"),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] sem sancao ou veto", "aprovada", "Aprovada; o governador não sancionou nem vetou no prazo, e falta promulgar",
     "Approved; the governor did not sign or veto it in time, and it still has to be promulgated"),
    (r"expedido autografo|autografo expedido", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"aprovad[ao] em (\S+ )?(e \S+ )?discussao|aprovad[ao] em plenario", "aprovada",
     "Aprovada no Plenário", "Approved by the full Assembly"),
    (r"apensad", "junta", None, None),
]


def situacao(v: dict) -> dict:
    data = (ultima(v)[0] or "")[:10] or None
    for t in reversed(v.get("tr") or []):  # a norma que a proposição virou, com número e data
        m = _NORMA.search(sem_acento((t[3] or "").lower()))
        if m:
            nome = NOMES[m.group(1)]
            num = re.sub(r"\D", "", m.group(2))
            ano = (re.search(r"(?:de|em)\s+\d{1,2}[º°o]?/\d{2}/(\d{4})|de (\d{4})", sem_acento((t[3] or "").lower()[m.end():m.end() + 40])) or None)
            ano = next((g for g in ano.groups() if g), None) if ano else (t[0] or "")[:4] or None
            nl = nome_lei(nome, num, ano)
            return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None,
                    "data": (t[0] or "")[:10] or data, "lei": {"nome": nl, "url": None}}
    tx = texto_tramitacoes(v)
    for exp, st, pt, en in REGRAS:
        if re.search(exp, tx):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    sit = sem_acento((v.get("sit") or "").lower())
    if sit.startswith("arquivad"):
        return {"status": "arquivada", "txt": "Arquivada", "en": None, "data": data, "lei": None}
    if sit.startswith("tramitando") or v.get("tr"):
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


def coletar() -> dict:
    return NoPaper(
        uf="BA", base="https://albalegis.nopapercloud.com.br", casa="Assembleia Legislativa do Estado da Bahia",
        casa_en="Legislative Assembly of the State of Bahia", sigla="Alba", site="https://www.al.ba.gov.br",
        veiculo="Assembleia Legislativa da Bahia (Alba)", prefixo="alba", pasta="alba",
        tipos={1: "PL", 6: "PLP", 10: "PEC", 2: "PDL", 13: "PRC"}, situacao=situacao, em_exercicio=em_exercicio,
        filtro_pessoas=f"&parlamentarLegislatura={legislatura_estadual(20)}&parlamentarSituacao=1", idade_pessoas_h=72, qtd_pessoas=10,
    ).coletar()
