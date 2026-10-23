"""Assembleia Legislativa da Paraíba (ALPB): SAPL 3 (https://sapl.al.pb.leg.br/api/).

Lista: deputados com "ativo" na legislatura atual do SAPL (é a mesma lista da página inicial da ALPB, com 36 pessoas,
inclusive os suplentes que assumiram). Propostas: projetos de lei ordinária (PLO), de lei complementar (PLC), de emenda
constitucional (PEC), de decreto legislativo (PDL) e de resolução (PRE) desde 1º/2/2023. Situação: a da última tramitação;
"virou lei" pela norma jurídica ligada ao projeto; "vetada por inteiro" pelas matérias do tipo Veto (ligadas ao projeto).
"""
from __future__ import annotations

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
    (r"pela reprovacao", "andando", "Uma comissão deu parecer contra; ainda falta a decisão final",
     "A committee recommended rejecting it; the final decision is still pending"),
    (r"^aprovado$", "andando", "Aprovada numa etapa (comissão ou Plenário); ainda não foi enviada ao governador",
     "Approved at one stage (committee or full Assembly); not yet sent to the governor"),
    (r"despachad|aguardando|incluir|constou|costou|indicacao de relator|recebido em plenario|protocolad|destacad|adiad|"
     r"retirado pauta|retirado de pauta|retirado por ausencia|aprovado a urgencia|materia regimental", "andando", None, None),
    (r".", "outra", None, None),
]


def coletar() -> dict:
    return SaplAssembleia(
        uf="PB", base="https://sapl.al.pb.leg.br", casa="Assembleia Legislativa do Estado da Paraíba",
        casa_en="Legislative Assembly of the State of Paraíba", sigla="ALPB", site="https://www.al.pb.leg.br",
        veiculo="Assembleia Legislativa da Paraíba (ALPB)", prefixo="alpb", pasta="alpb",
        tipos={1: "PL", 6: "PLP", 2: "PEC", 7: "PDL", 3: "PRC"}, tipos_veto={13: None}, regras=REGRAS,
    ).coletar()
