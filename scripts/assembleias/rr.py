"""Assembleia Legislativa do Estado de Roraima (ALE-RR): SAPL 3 (https://sapl.al.rr.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL (no SAPL de Roraima a 9ª legislatura vai de 1º/1/2023 a
31/12/2026: em Roraima a posse dos deputados é em 1º de janeiro, Constituição do Estado, art. 30, § 4º, redação da EC nº
75/2021). Propostas: matérias do SAPL desde 1º/2/2023; situação = a da última
tramitação (quando ela não diz nada sozinha, vale o texto dela ou a tramitação de antes); "virou lei" = norma jurídica
ligada à proposta no SAPL. O SAPL de Roraima não tem votações registradas.
Governador (gov-RR): projetos do governador de hoje, leis e vetos desde a posse dele (GOVERNO, abaixo).
"""
from __future__ import annotations

from . import _nco_gov as G
from ._nco_sapl import Sapl

VETO_PENDENTE = ("Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
                 "Vetoed by the governor; the state assembly has yet to decide on the veto")
REGRAS = [
    (r"transformada em norma|transformada em lei|lei promulgada|norma promulgada", "lei", None, None),
    (r"solicitacao de retirada de tramitacao", "retirada", "O autor pediu para retirar a proposta", "The author asked to withdraw the bill"),
    (r"^veto rejeitado$", "aprovada", "Aprovada; o veto do governador foi derrubado e falta promulgar",
     "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"^veto mantido$", "rejeitada", "Vetada pelo governador; a Assembleia manteve o veto",
     "Vetoed by the governor; the state assembly upheld the veto"),
    (r"veto", "andando", *VETO_PENDENTE),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"encaminha autografo|para autografo", "aprovada", "Aprovada; o texto final (autógrafo) vai ao governador",
     "Approved; the final text (autograph) goes to the governor"),
    (r"para sancao governamental|encaminhado ao executivo", "aprovada", "Aprovada; enviada para a sanção do governador",
     "Approved; sent to the governor to be signed"),
    (r"para redacao final", "aprovada", "Aprovada; falta a redação final", "Approved; the final wording is still pending"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"aprovada em 2.? turno|^aprovado$|^proposicao aprovada$", "aprovada", None, None),
    (r"aprovado na ccj|aprovado na comissao|aprovado pelo conselho|parecer (aprovado|rejeitado) pela comissao", "andando",
     None, None),
    (r"rejeitado na (ccj|comissao)", "rejeitada", "Rejeitada por uma comissão", "Rejected by a committee"),
    (r"desarquivada", "andando", None, None),
    (r"para arquivar|arquivada", "arquivada", None, None),
    (r"prejudicada", "parada", None, None),
    (r"retirada da ordem do dia|nao deliberada|inserida no sistema|leitura|lido no expediente|ordem do dia|devolvido|"
     r"encaminhado para|aguardando|para emissao de parecer|para aprovacao|para inclusao|impacto orcamentario|"
     r"para manifestacao|para analise", "andando", None, None),
]
AMBIGUOS = [r"^para providencias$", r"para conhecimento", r"oficio encaminhado", r"para elaboracao de oficio",
            r"para emissao de certidao", r"para criacao de comissao", r"^transferido$", r"proposicao deliberada",
            r"prazo expirado"]

# o que o governo do estado fez (perfil gov-RR): no SAPL de Roraima cada governador é um autor do tipo "Poder Executivo"
# (Soldado Sampaio = "Francisco dos Santos Sampaio"); entram os projetos de todos eles no período (mesma régua do
# presidente: inclusive de quem estava no exercício do cargo; a nota diz quantos). Vetos: "Mensagem Governamental" (MGOV)
# com a ementa começando por "Veto total ao..." ou "Veto parcial ao..." (as outras mensagens não contam); leis = normas
# "Lei Ordinária" (2) e "Lei Complementar" (3). Conferido à mão em 23/10/2026.
GOVERNO = {
    "autores": "tipo", "tipo_autor": r"^poder executivo$",
    "tipos": {1: "PL", 2: "PLP", 5: "PEC", 6: "PDL"},
    "vetos": {"tipos": [17], "filtro": r"^veto", "parcial": r"^veto parcial", "total": r"^veto total",
              "de_onde": ("mensagens governamentais de veto que chegaram à ALE-RR no período, pela data em que foram lidas",
                          "government veto messages received by the ALE-RR in the period, by the date they were read")},
    "leis": {"tipos": {2: "LO", 3: "LC"},
             "de_onde": ("cadastradas no sistema da ALE-RR (SAPL) com data no período",
                         "recorded in the ALE-RR's system (SAPL) with a date in the period"),
             "promulgadas": G.PROMULGADAS_INCLUIDAS},
    "nota": [G.EM_EXERCICIO],
}


def coletar() -> dict:
    return Sapl(
        "RR", "https://sapl.al.rr.leg.br",
        "Assembleia Legislativa do Estado de Roraima", "Legislative Assembly of the State of Roraima",
        "ALE-RR", "https://al.rr.leg.br", "Assembleia Legislativa de Roraima (ALE-RR)", "alerr",
        {1: "PL", 2: "PLP", 5: "PEC", 6: "PDL", 7: "PRC"}, REGRAS, "alerr",
        ambiguos=AMBIGUOS, posse="01-01", governo=GOVERNO, notas=[NOTA_VOTOS_GASTOS],
    ).coletar()


NOTA_VOTOS_GASTOS = (
    "As votações e os gastos não entram. Votações: o SAPL da ALE-RR não tem nenhuma votação registrada. Gastos: a ALE-RR "
    "publica o ressarcimento de despesas de cada deputado só a partir de setembro de 2025 (um arquivo por deputado e por mês "
    "no Portal da Transparência); a página do período anterior estava fora do ar quando foi conferida, em 26/10/2026.",
    "Votes and spending are not included. Votes: the ALE-RR SAPL system has no votes recorded. Spending: the ALE-RR "
    "publishes each deputy's expense reimbursements only from September 2025 on (one file per deputy and month on its "
    "transparency portal); the page for the earlier period was down when checked, on October 26, 2026.")
