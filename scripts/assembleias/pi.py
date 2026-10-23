"""Assembleia Legislativa do Estado do Piauí (Alepi): SAPL 3 (https://sapl.al.pi.leg.br/api/).

Lista: deputados com "ativo" na legislatura atual do SAPL (a página "Parlamentares" do site da Alepi mostra o próprio SAPL;
a Casa anota no mandato cada afastamento e cada retorno, e marca como ativo só quem está no cargo; são 30, inclusive os
suplentes que assumiram). Propostas: projetos de lei ordinária (PLO), de lei complementar (PLC), de emenda à Constituição
(PEC), de decreto legislativo (PDL) e de resolução (PRE) desde 1º/2/2023 (os tipos "do Governo" ficam de fora: não têm
deputado como autor). Situação: a da última tramitação; "virou lei" pela norma jurídica ligada ao projeto; "vetada por
inteiro" pelas mensagens de veto do governador (ligadas ao projeto pelo campo "anexadas").
"""
from __future__ import annotations

from ._ne_sapl import SaplAssembleia

# situação da última tramitação na Alepi (texto oficial sem acento, minúsculas) -> status do site
REGRAS = [
    (r"transformada em lei com veto parcial", "lei", "Virou lei (com partes vetadas)", "Became law (with some parts vetoed)"),
    (r"transformada em lei|norma promulgada|veto total ou parcial promulgado", "lei", "Virou lei", None),
    (r"veto sobre a proposicao rejeitado", "aprovada", "Aprovada; o veto do governador foi derrubado e falta promulgar",
     "Approved; the governor's veto was overridden and it still has to be promulgated"),
    (r"proposicao com veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"aguardando sancao", "aprovada", "Aprovada; esperando a sanção do governador", "Approved; waiting for the governor to sign it"),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando assinatura do autografo|proposicao +aprovada$|aprovada com emenda|aprovada em 2", "aprovada", None, None),
    (r"transformada em indicacao", "outra", "Foi transformada em indicação (sugestão ao governo)", None),
    (r"indicativo encaminhado", "outra", "Aprovada como sugestão ao governador (indicativo)",
     "Approved as a suggestion to the governor"),
    (r"devolvid[oa] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"retirada pelo autor", "retirada", None, None),
    (r"rejeitada pelo plenario", "rejeitada", "Rejeitada pelo Plenário", "Rejected by the full Assembly"),
    (r"arquivad|pelo arquivamento", "arquivada", "Arquivada", None),
    (r"proposicao anexada", "junta", None, None),
    (r"aprovada em 1", "andando", "Aprovada em 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"aguardando|parecer|encaminhad|inclusa na ordem|apresentada em plenario|autuada|despachada|devolvida|pedido de vista|"
     r"retirada da ordem|comissao|relator|desarquivada|publicada|manutencao do veto|rejeicao do veto|oficio", "andando", None, None),
    (r".", "outra", None, None),
]


def coletar() -> dict:
    return SaplAssembleia(
        uf="PI", base="https://sapl.al.pi.leg.br", casa="Assembleia Legislativa do Estado do Piauí",
        casa_en="Legislative Assembly of the State of Piauí", sigla="Alepi", site="https://www.al.pi.leg.br",
        veiculo="Assembleia Legislativa do Piauí (Alepi)", prefixo="alepi", pasta="alepi",
        tipos={1: "PL", 5: "PLP", 15: "PEC", 6: "PDL", 2: "PRC"}, tipos_veto={17: None, 18: "parcial"}, regras=REGRAS,
    ).coletar()
