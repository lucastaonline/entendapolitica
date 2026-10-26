"""Assembleia Legislativa da Paraíba (ALPB): SAPL 3 (https://sapl.al.pb.leg.br/api/).

Lista: deputados com "ativo" na legislatura atual do SAPL (é a mesma lista da página inicial da ALPB, com 36 pessoas,
inclusive os suplentes que assumiram). Propostas: projetos de lei ordinária (PLO), de lei complementar (PLC), de emenda
constitucional (PEC), de decreto legislativo (PDL) e de resolução (PRE) desde 1º/2/2023. Situação: a da última tramitação;
"virou lei" pela norma jurídica ligada ao projeto; "vetada por inteiro" pelas matérias do tipo Veto (ligadas ao projeto).
"""
from __future__ import annotations

import re

from . import _ne_gov as gv
from ._ne_sapl import SaplAssembleia

# situação da última tramitação na ALPB (texto oficial sem acento, minúsculas) -> status do site. Conferido à mão numa
# amostra (ver as notas da frente ale-nordeste): na ALPB, "Aprovado" sozinho quase sempre é o parecer de uma comissão
# aprovado (quando o Plenário aprova, a tramitação seguinte, "Sanção e ou Veto", vem em um ou dois dias).
REGRAS = [
    (r"sancao e ou veto|redacao final e autografo|redacao final aprovad", "aprovada",
     "Aprovada; enviada ao governador para sanção ou veto", "Approved; sent to the governor to sign or veto"),
    (r"mantido o veto", "rejeitada", "Vetada pelo governador; o veto foi mantido", "Vetoed by the governor; the veto was upheld"),
    (r"retirado a pedido do autor", "retirada", None, None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"igual teor", "parada", "Saiu da pauta porque já existe outro projeto igual",
     "Taken off the agenda because an identical bill already exists"),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"arquivad", "arquivada", "Arquivada", None),
    (r"pela reprovacao", "andando", "Uma comissão deu parecer contra; falta a decisão final",
     "A committee recommended rejecting it; the final decision is pending"),
    (r"^aprovado$", "andando", "Aprovada numa etapa (comissão ou Plenário); faltam as outras etapas antes de ir ao governador",
     "Approved at one stage (committee or full Assembly); other stages remain before it goes to the governor"),
    (r"despachad|aguardando|incluir|constou|costou|indicacao de relator|recebido em plenario|protocolad|destacad|adiad|"
     r"retirado pauta|retirado de pauta|retirado por ausencia|aprovado a urgencia|materia regimental", "andando", None, None),
    (r".", "outra", None, None),
]


def _classificar(col, normas: list[dict]) -> list[bool | None]:
    """Quem assinou cada lei na Paraíba (True = o presidente da Assembleia promulgou; False = o governador sancionou).
    O SAPL da ALPB não tem esse campo, e o texto da lei só existe em PDF. Regra, conferida com o texto (PDF) de 28 leis de
    2026: (1) a tramitação do projeto anota onde a lei saiu; quando cita o Diário do Poder Legislativo ("DPL"), quem
    promulgou foi o presidente da Assembleia (sanção tácita ou veto derrubado); (2) as leis que vêm de medidas provisórias
    são, quase sempre, promulgadas pelo presidente da Assembleia (13 de 14 na conferência) e ficam de fora da conta das
    sancionadas; (3) as outras foram sancionadas pelo governador. As anotações com "DPL" do período vêm numa consulta só
    (filtro de texto e data da API de tramitações: uma ou duas páginas por rodada)."""
    ini = gv.periodo("PB")["inicio"]
    mats = (getattr(col, "est", None) or {}).get("materias") or {}
    mps = {int(k) for k, v in mats.items() if v["t"] == 15}  # medidas provisórias (só o governador as edita)
    marcadas = set()
    for t in col.todos(f"/api/materia/tramitacao/?texto__icontains=DPL&data_tramitacao__gte={ini}", "gov-dpl", 20):
        x = t.get("texto") or ""
        if re.search(r"\bDPL\b", x) and re.search(r"(?i)\blei\b.{0,30}n", x):
            marcadas.add(t.get("materia"))
    return [n.get("materia") in mps or n.get("materia") in marcadas for n in normas]


GOV = {
    "autores": [74],  # "Governador do Estado da Paraíba"
    "tipos": {1: "PL", 6: "PLP", 2: "PEC", 15: "MPV"},
    "tipos_lei": [2, 1],  # Lei Ordinária, Lei Complementar
    "classificar": _classificar,
    "criterio_leis": ("que não saíram no Diário do Poder Legislativo e não vêm de medidas provisórias (regra conferida com o "
                      "texto de 28 leis)", "that did not appear in the Legislative Gazette and do not come from provisional "
                      "measures (rule checked against the text of 28 laws)"),
    "tipos_txt": ("projetos de lei, de lei complementar e de emenda à Constituição do estado e medidas provisórias",
                  "bills, complementary bills, amendments to the state Constitution and provisional measures"),
    "nota_prop": ("Medidas provisórias (MP) valem como lei assim que o governador as publica, mas perdem a validade se a "
                  "Assembleia não as aprovar no prazo da Constituição do estado.",
                  "Provisional measures (MP) take effect as law as soon as the governor publishes them, but they expire if "
                  "the state legislature does not approve them within the deadline set by the state Constitution."),
}


def coletar() -> dict:
    return SaplAssembleia(
        uf="PB", base="https://sapl.al.pb.leg.br", casa="Assembleia Legislativa do Estado da Paraíba",
        casa_en="Legislative Assembly of the State of Paraíba", sigla="ALPB", site="https://www.al.pb.leg.br",
        veiculo="Assembleia Legislativa da Paraíba (ALPB)", prefixo="alpb", pasta="alpb",
        tipos={1: "PL", 6: "PLP", 2: "PEC", 7: "PDL", 3: "PRC"}, tipos_veto={13: None}, regras=REGRAS, gov=GOV,
    ).coletar()
