"""Assembleia Legislativa do Estado do Acre (Aleac): SAPL 3 (https://sapl.al.ac.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL. Propostas: matérias do SAPL desde 1º/2/2023; situação = a
da última tramitação. A Aleac não cadastra no SAPL as leis que saem dos projetos (uma norma desde 2023), então "virou lei"
não aparece: o último passo registrado costuma ser "Autógrafo enviado" (o texto aprovado foi enviado ao governador),
que o site mostra como "aprovada". As votações registradas no SAPL são poucas e irregulares: não entram.
"""
from __future__ import annotations

from ._nco_sapl import Sapl

REGRAS = [
    (r"aprovado pela inconstitucionalidade", "rejeitada", "Rejeitada por ser considerada inconstitucional",
     "Rejected for being considered unconstitutional"),
    (r"aprovado pela rejeicao", "rejeitada", "Rejeitada", None),
    (r"veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"autografo enviado", "aprovada", "Aprovada; o texto final foi enviado ao governador",
     "Approved; the final text was sent to the governor"),
    (r"encaminhado ao poder executivo para sancao|encaminhar para sancao", "aprovada", "Aprovada; enviada para a sanção do governador",
     "Approved; sent to the governor to be signed"),
    (r"expedicao do autografo|aguardando redacao final", "aprovada", "Aprovada; falta o texto final (autógrafo)",
     "Approved; the final text (autograph) is still pending"),
    (r"aprovado 1. (discussao|votacao)", "andando", "Aprovada na 1ª votação; falta a 2ª", "Approved in the first vote; the second is still pending"),
    (r"^aprovado( 2. (discussao|votacao))?$", "aprovada", None, None),
    (r"apensado", "junta", None, None),
    (r"retirado de pauta", "andando", None, None),
    (r"retirado mediante requerimento", "retirada", "Retirada a pedido (requerimento)", "Withdrawn on request"),
    (r"arquivad|arquivar", "arquivada", None, None),
    (r"parecer pela inconstitucionalidade", "andando", "Recebeu parecer pela inconstitucionalidade",
     "Received an opinion that it is unconstitutional"),
    (r"despachado a secretaria executiva", "andando", "Apresentada; em análise inicial na Assembleia",
     "Filed; under initial review in the state assembly"),
    (r"vista|redistribuido|comissoes conjuntas|distribuicao|ordem do dia|aguardando votacao|apresentado no plenario|parecer",
     "andando", None, None),
]
AMBIGUOS = [r"^deferido$", r"secretaria executiva para providencias", r"oficio (expedido|recebido)",
            r"servi publico", r"nao tramitou"]


def coletar() -> dict:
    return Sapl(
        "AC", "https://sapl.al.ac.leg.br",
        "Assembleia Legislativa do Estado do Acre", "Legislative Assembly of the State of Acre",
        "Aleac", "https://www.al.ac.leg.br", "Assembleia Legislativa do Acre (Aleac)", "aleac",
        {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "aleac",
        ambiguos=AMBIGUOS,
        notas=[("A Aleac não registra no seu sistema (SAPL) as leis que saem dos projetos: o último passo que aparece costuma ser "
                "o envio do texto aprovado ao governador.",
                "The Aleac does not record in its system (SAPL) the laws that come out of the bills: the last step shown is "
                "usually the approved text being sent to the governor.")],
    ).coletar()
