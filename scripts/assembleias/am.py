"""Assembleia Legislativa do Estado do Amazonas (Aleam): SAPL 3 (https://sapl.al.am.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL (a mesma lista de https://www.aleam.gov.br/deputados/).
Propostas: matérias do SAPL desde 1º/2/2023; situação = a da última tramitação (quando ela não diz nada sozinha, como
"Para Providências", vale o texto dela ou a tramitação de antes); "virou lei" = norma jurídica ligada à proposta no SAPL.
Votações nominais: voto de cada deputado registrado no SAPL (painel do Plenário).
"""
from __future__ import annotations

from ._nco_sapl import Sapl

# situação da última tramitação (texto oficial sem acento, minúsculas) -> status do site; a primeira que bater vale.
# Conferido à mão em outubro de 2026 (ex.: PL 521/2023 "Comenda Entregue pelo Plenário" depois de virar lei;
# PL 555/2024 "Veto sobre a proposição mantido" sem lei; PL 1170/2023 "Para Providências" com texto "Arquivado").
REGRAS = [
    (r"transformada em lei|norma promulgada|lei promulgada|veto total ou parcial promulgado|comenda entregue", "lei", None, None),
    (r"retirad[ao] de tramitacao pelo autor|retirad[ao] pelo autor|requerimento de retirada", "retirada", None, None),
    (r"aguardando promulgacao de lei com veto rejeitado|veto sobre a proposicao rejeitado", "aprovada",
     "Aprovada; o veto do governador foi derrubado e falta promulgar", "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"aguardando sancao|a sancao governamental", "aprovada", "Aprovada; esperando a sanção do governador",
     "Approved; waiting for the governor to sign it"),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando assinatura do autografo", "aprovada", "Aprovada; esperando a assinatura do texto final (autógrafo)",
     "Approved; waiting for the final text (autograph) to be signed"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"^proposicao aprovada\.?$", "aprovada", None, None),
    (r"com veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto sobre a proposicao mantido", "rejeitada", "Vetada pelo governador; a Assembleia manteve o veto",
     "Vetoed by the governor; the state assembly upheld the veto"),
    (r"veto sobre a proposicao aplicado|veto distribuido|veto\s+incluso|parecer pel[ao] (rejeicao|manutencao) do veto",
     "andando", "Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
     "Vetoed by the governor; the state assembly has yet to decide on the veto"),
    (r"retirada da ordem do dia|adiada", "andando", None, None),
    (r"desarquivada", "andando", None, None),
    (r"devolvida ao autor para correc", "parada", "Devolvida ao autor para correções", "Returned to the author for corrections"),
    (r"pelo arquivamento", "arquivada", "Arquivada (parecer de comissão pelo arquivamento)",
     "Shelved (a committee recommended shelving it)"),
    (r"rejeitada pela comissao", "rejeitada", "Rejeitada por uma comissão", "Rejected by a committee"),
    (r"rejeitada pelo plenario", "rejeitada", "Rejeitada pelo Plenário", "Rejected by the full assembly"),
    (r"^parecer contrario", "andando", "Recebeu parecer contrário de uma comissão", "Received an unfavorable opinion from a committee"),
    (r"autuada e cumprindo prazo de pauta", "andando", "Apresentada; aberta para receber emendas", "Filed; open for amendments"),
    (r"prejudicialidade|ordem do dia|em pauta|comissao", "andando", None, None),
]
# situações que não dizem nada sozinhas: vale o texto da tramitação ou a tramitação de antes
AMBIGUOS = [r"para providencias", r"requerimento deferido", r"deferido pela presidencia", r"^parecer contrario",
            r"assinatura do secretario geral"]


def coletar() -> dict:
    return Sapl(
        "AM", "https://sapl.al.am.leg.br",
        "Assembleia Legislativa do Estado do Amazonas", "Legislative Assembly of the State of Amazonas",
        "Aleam", "https://www.aleam.gov.br", "Assembleia Legislativa do Amazonas (Aleam)", "aleam",
        {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "aleam",
        ambiguos=AMBIGUOS, votacoes=True,
    ).coletar()
