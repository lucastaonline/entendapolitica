"""Assembleia Legislativa do Estado de Rondônia (Ale-RO): SAPL 3 (https://sapl.al.ro.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL (a mesma lista de https://www.al.ro.leg.br/deputados/perfil/).
Propostas: matérias do SAPL desde 1º/2/2023; situação = a da última tramitação (quando ela não diz nada sozinha, vale o
texto dela ou a tramitação de antes); "virou lei" = norma jurídica ligada à proposta no SAPL.
Votações nominais: voto de cada deputado registrado no SAPL. Em Rondônia, a maioria das votações é simbólica (sem o voto
de cada um); as nominais (vetos, por exemplo) têm o voto de cada deputado.
Governador (gov-RO): projetos do Poder Executivo, leis e vetos desde 1º/1/2023 (GOVERNO, abaixo).
"""
from __future__ import annotations

from . import _nco_gov as G
from ._nco_sapl import Sapl

VETO_PENDENTE = ("Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
                 "Vetoed by the governor; the state assembly has yet to decide on the veto")
REGRAS = [
    (r"transformada em lei|norma promulgada|lei promulgada|veto total ou parcial promulgado", "lei", None, None),
    (r"retirado pela secretaria legislativa", "parada", "Retirada pela Secretaria Legislativa (não pôde seguir)",
     "Withdrawn by the Legislative Secretariat (could not go ahead)"),
    (r"retirad[ao] pelo autor|projeto retirado pelo autor", "retirada", None, None),
    (r"aguardando promulgacao de lei com veto rejeitado|veto sobre a proposicao rejeitado", "aprovada",
     "Aprovada; o veto do governador foi derrubado e falta promulgar", "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"aguardando deliberacao do poder executivo", "aprovada", "Aprovada; esperando a decisão do governador",
     "Approved; waiting for the governor's decision"),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando assinatura do autografo", "aprovada", "Aprovada; esperando a assinatura do texto final (autógrafo)",
     "Approved; waiting for the final text (autograph) to be signed"),
    (r"redacao\s+final inclusa na ordem do dia|vai a redacao final|aprovada a redacao final", "aprovada",
     "Aprovada; falta votar a redação final", "Approved; the final wording still needs a vote"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"aprovada em 2.? turno|^proposicao aprovada\.?$", "aprovada", None, None),
    (r"projeto aprovado na comissao", "andando", "Aprovada numa comissão", "Approved by a committee"),
    (r"com veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto sobre a proposicao mantido", "rejeitada", "Vetada pelo governador; a Assembleia manteve o veto",
     "Vetoed by the governor; the state assembly upheld the veto"),
    (r"veto|mensagem sobre o veto", "andando", *VETO_PENDENTE),
    (r"retirada da ordem do dia|adiada|vista|anulacao de votacao", "andando", None, None),
    (r"desarquiv", "andando", None, None),
    (r"vai ao arquivo|ao arquivo|pelo arquivamento", "arquivada", "Arquivada", None),
    (r"anexada", "junta", None, None),
    (r"rejeitada pela comissao", "rejeitada", "Rejeitada por uma comissão", "Rejected by a committee"),
    (r"rejeitada pelo plenario", "rejeitada", "Rejeitada pelo Plenário", "Rejected by the full assembly"),
    (r"^parecer contrario", "andando", "Recebeu parecer contrário de uma comissão", "Received an unfavorable opinion from a committee"),
    (r"autuada e cumprindo prazo de pauta", "andando", "Apresentada; aberta para receber emendas", "Filed; open for amendments"),
    (r"autuada|avocada|prazo|sem parecer|recurso|redistribuicao|despachada|decurso", "andando", None, None),
    (r"ordem do dia|em pauta|comissao|comissoes|parecer", "andando", None, None),
]
AMBIGUOS = [r"para providencias", r"requerimento deferido", r"^parecer contrario"]

# o que o governo do estado fez (perfil gov-RO): autor 29 = "Poder Executivo"; vetos = matérias "Veto Total" (17) e
# "Veto Parcial" (18); leis = normas "Lei ordinária" e "Lei Complementar". Conferido à mão em 23/10/2026.
GOVERNO = {
    "autores": [29],
    "tipos": {1: "PL", 5: "PLP", 12: "PEC", 6: "PDL"},
    "vetos": {"tipos": [17, 18], "tipos_totais": [17], "tipos_parciais": [18],
              "de_onde": ("matérias \"Veto Total\" e \"Veto Parcial\" que chegaram à Ale-RO no período, pela data em que foram lidas",
                          "\"Veto Total\" and \"Veto Parcial\" items received by the Ale-RO in the period, by the date they were read")},
    "leis": {"tipos": {1: "LO", 2: "LC"},
             "de_onde": ("cadastradas no sistema da Ale-RO (SAPL) com data no período",
                         "recorded in the Ale-RO's system (SAPL) with a date in the period"),
             "promulgadas": G.PROMULGADAS_INCLUIDAS},
    "nota": [G.EM_EXERCICIO],
}


def coletar() -> dict:
    return Sapl(
        "RO", "https://sapl.al.ro.leg.br",
        "Assembleia Legislativa do Estado de Rondônia", "Legislative Assembly of the State of Rondônia",
        "Ale-RO", "https://www.al.ro.leg.br", "Assembleia Legislativa de Rondônia (Ale-RO)", "alero",
        {1: "PL", 5: "PLP", 12: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "alero",
        ambiguos=AMBIGUOS, votacoes=True, governo=GOVERNO, sic="https://transparencia.al.ro.leg.br/AcessoInformacao/",
    ).coletar()
