"""Câmara Municipal de Cuiabá (MT): o Processo Legislativo Eletrônico da Ágape (https://legislativo.camaracuiaba.mt.gov.br/spl):
a lista oficial de vereadores, as propostas de cada um desde 1º/1/2025 e os projetos que a prefeitura mandou à Câmara
(scripts/camaras/_agape.py).

A página de cada proposição de Cuiabá tem de 2 a 6 MB (uns 0,5 MB comprimidos): ela repete o desenho do fluxo do processo em
cada passo. Por isso a situação vem, nesta ordem: (1) da norma ligada à proposição no módulo de Legislação da Câmara ("virou
lei"); (2) da página da proposição, lida só quando a lista não basta (arquivada sem norma, "expedição de certificado" sem
norma), até o fim da tabela da tramitação e com um limite de bytes por rodada (regras de eventos_cuiaba, conferidas à mão);
(3) da fase atual na lista oficial (FASES abaixo).
"""
from ._agape import Agape

IBGE, UF, HOST = "5103403", "MT", "https://legislativo.camaracuiaba.mt.gov.br"
CASA = {"casa": "Câmara Municipal de Cuiabá", "casa_en": "Cuiabá City Council", "sigla": "CMC-MT", "site": "https://www.camaracuiaba.mt.gov.br"}
# conferidos à mão (mesmo partido; nome de urna no TSE, eleitos em 2024): "Marcus Brito Junior" (id 23) = MARCUS BRITO JR (PV);
# "Ranalli" (id 60) = POLICIALFEDERAL RAFAEL RANALLI (PL)
TSE = {"23": "110002017741", "60": "110002182549"}
# tipo no sistema → (tipo comum, sigla). Fora: substitutivos (113, 121, 157), emendas e subemendas (108, 158), veto (112),
# requerimentos, indicações e moções
TIPOS = {"103": ("PL", "PL"), "101": ("PLP", "PLC"), "107": ("PELO", "PELO"), "105": ("PDL", "PDL"), "106": ("PRC", "PR")}
# espécies do módulo de Legislação que nascem desses projetos (consulta-legislacao.aspx?tipo=...)
NORMAS = {"1": "Emenda à Lei Orgânica", "5": "Lei Ordinária", "3": "Lei Complementar", "4": "Decreto Legislativo", "2": "Resolução"}
# fase atual na lista oficial → situação, para as proposições sem norma cuja página não é lida (as que ainda andam):
# conferido nas fases de 2025 e 2026 (ver as notas da frente)
FASES = {
    r"arquivado a pedido do autor": ("retirada", None),
    r"tomar conhecimento e providencias|enviar autografo": ("aprovada", "na_prefeitura"),
    r"redacao final": ("aprovada", "sancao"),
}
NOTAS = [
    ("As propostas vêm do Processo Legislativo Eletrônico, o sistema oficial da Câmara: a lista de cada tipo de proposição "
     "(planilha da própria consulta), as normas do módulo de Legislação (que ligam cada lei, decreto legislativo ou resolução "
     "ao projeto de origem) e, para as proposições arquivadas sem norma, a página de cada uma, com o histórico da tramitação "
     "(rejeição, veto, prejuízo, retirada). Para as que ainda andam, vale a fase atual mostrada na lista. Entram projetos de "
     "lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução apresentados desde 1º/1/2025; "
     "substitutivos, emendas, requerimentos, indicações e moções não entram. O primeiro nome da lista de autores de cada "
     "proposição aparece como autor principal, e os outros como quem assinou junto.",
     "Bills come from the Processo Legislativo Eletrônico, the City Council's official system: the list of each type of bill "
     "(the search's own spreadsheet), the laws in its Legislation module (which link each law, legislative decree or resolution "
     "to the bill it came from) and, for bills shelved without becoming law, each bill's page with the history of its progress "
     "(rejected, vetoed, set aside, withdrawn). For bills still moving, the current stage shown in the list is used. Included: "
     "bills for ordinary and complementary laws, amendments to the city's Organic Law, legislative decrees and resolutions "
     "filed since January 1, 2025; substitute bills, amendments, requests, recommendations and motions are not included. The "
     "first name on each bill's list of authors is shown as its main author, and the others as co-signers."),
    ("As votações de cada vereador não entram neste site: a Câmara publica as atas das sessões em PDF escaneado (imagem), "
     "sem dados abertos das votações.",
     "Each councilor's votes are not included on this site: the City Council publishes the session minutes as scanned "
     "PDFs (images), with no open data on the votes."),
    ("Os gastos do mandato não entram neste site: a verba indenizatória da Câmara de Cuiabá é um valor fixo por mês, "
     "definido em lei (Lei 6.910/2023: 75% do subsídio, para ressarcir despesas da atividade parlamentar), e não uma lista das "
     "despesas de cada gabinete; além disso, o portal da transparência da Câmara (gp.srv.br) pede, no arquivo de regras para "
     "robôs (robots.txt), que robôs não leiam as páginas dele.",
     "Office spending is not included on this site: the Cuiabá City Council's allowance is a fixed monthly amount set by law "
     "(Law 6,910/2023: 75% of the councilor's salary, to reimburse expenses of parliamentary work), not a list of each "
     "office's expenses; also, the City Council's transparency portal (gp.srv.br) asks robots, in its rules file "
     "(robots.txt), not to read its pages."),
]


def coletar() -> dict:
    return Agape(IBGE, UF, HOST, CASA, 27, TIPOS, "cuiaba", tse_manual=TSE, notas=NOTAS, paginas="duvida", normas=NORMAS,
                 nota_fase=FASES, executivo=r"^executivo|^prefeit|^poder executivo", max_mb_paginas=300,
                 pausa_paginas=2.0).coletar()
