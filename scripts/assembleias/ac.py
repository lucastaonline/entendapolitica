"""Assembleia Legislativa do Estado do Acre (Aleac): SAPL 3 (https://sapl.al.ac.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL. Propostas: matérias do SAPL desde 1º/2/2023; situação = a
da última tramitação. A Aleac não cadastra no SAPL as leis que saem dos projetos (uma norma desde 2023), então "virou lei"
não aparece: o último passo registrado costuma ser "Autógrafo enviado" (o texto aprovado foi enviado ao governador),
que o site mostra como "aprovada". As votações registradas no SAPL são poucas e irregulares: não entram.
Governadora (gov-AC): projetos do Poder Executivo e vetos desde a posse de quem governa hoje (GOVERNO, abaixo).
"""
from __future__ import annotations

from . import _nco_gov as G
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

# o que o governo do estado fez (perfil gov-AC): autor 38 = "PODER EXECUTIVO"; vetos = matérias "Veto" (a ementa é a
# mensagem: "decidi vetar" ou "decidi vetar parcialmente"). Leis: não entram (a Aleac não cadastra as leis no SAPL; o
# Legis, portal de legislação do Acre, proíbe no robots.txt as buscas com parâmetros e a página de leis dá erro 500; o
# Diário Oficial só tem busca por edição inteira, misturando atos do estado e dos municípios). Conferido em 23/10/2026.
SEM_LEIS = ("Governo do estado: entram os projetos que o Poder Executivo mandou à Assembleia e os vetos. As leis sancionadas "
            "não entram: a Aleac não cadastra as leis no seu sistema (SAPL), e o portal de legislação do Acre (Legis) não "
            "oferece uma lista das leis que o site consiga ler.",
            "State government: the bills the executive branch sent to the state assembly and the vetoes are included. Signed "
            "laws are not: the Aleac does not record laws in its system (SAPL), and Acre's legislation portal (Legis) does "
            "not offer a list of laws this site can read.")
GOVERNO = {
    "autores": [38],
    "tipos": {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL"},
    "vetos": {"tipos": [13], "parcial": r"parcial", "total": r"vet",
              "de_onde": ("mensagens de veto que chegaram à Aleac no período, pela data em que foram lidas",
                          "veto messages received by the Aleac in the period, by the date they were read")},
    "leis": None,
    "nota": [G.EM_EXERCICIO, SEM_LEIS],
}


def coletar() -> dict:
    return Sapl(
        "AC", "https://sapl.al.ac.leg.br",
        "Assembleia Legislativa do Estado do Acre", "Legislative Assembly of the State of Acre",
        "Aleac", "https://www.al.ac.leg.br", "Assembleia Legislativa do Acre (Aleac)", "aleac",
        {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "aleac",
        ambiguos=AMBIGUOS, governo=GOVERNO, sic="https://www.al.ac.leg.br/?page_id=41640",
        notas=[("A Aleac não registra no seu sistema (SAPL) as leis que saem dos projetos: o último passo que aparece costuma ser "
                "o envio do texto aprovado ao governador.",
                "The Aleac does not record in its system (SAPL) the laws that come out of the bills: the last step shown is "
                "usually the approved text being sent to the governor."), SEM_LEIS, NOTA_VOTOS_GASTOS],
    ).coletar()


NOTA_VOTOS_GASTOS = (
    "As votações e os gastos não entram. Votações: o SAPL da Aleac tem o voto de cada deputado só de 26/6/2025 a 30/3/2026 "
    "(cerca de 40 votações) e nada de 2023 e 2024. Gastos: o Portal da Transparência da Aleac (app.al.ac.leg.br) desativou "
    "a página da verba indenizatória e publica só a regulamentação.",
    "Votes and spending are not included. Votes: the Aleac SAPL system has each deputy's vote only from June 26, 2025 to "
    "March 30, 2026 (about 40 votes) and nothing from 2023 or 2024. Spending: the Aleac transparency portal "
    "(app.al.ac.leg.br) has taken down its expense allowance page and publishes only the rules.")
