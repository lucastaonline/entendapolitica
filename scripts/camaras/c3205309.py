"""Câmara Municipal de Vitória (ES): o Processo Legislativo Eletrônico da Ágape (https://camarasempapel.cmv.es.gov.br/spl):
a lista oficial de vereadores, as propostas de cada um desde 1º/1/2025 e os projetos que a prefeitura mandou à Câmara
(scripts/camaras/_agape.py; situação pelas regras de eventos_vitoria, conferidas à mão)."""
from ._agape import Agape

IBGE, UF, HOST = "3205309", "ES", "https://camarasempapel.cmv.es.gov.br"
CASA = {"casa": "Câmara Municipal de Vitória", "casa_en": "Vitória City Council", "sigla": "CMV", "site": "https://www.cmv.es.gov.br"}
# tipo no sistema → (tipo comum, sigla oficial: a das pastas de documentos do sistema). Ficam fora: Projeto de Lei de
# iniciativa popular (72), Projeto Substitutivo (56), Emenda (55), Veto (58), Sanção (63), requerimentos, indicações e moções
TIPOS = {"1": ("PL", "PL"), "18": ("PLP", "PLC"), "4": ("PELO", "ELO"), "2": ("PDL", "PDL"), "3": ("PRC", "PR")}
# a planilha escreve "Armando Fontoura"; o cartão do vereador é "Armandinho Fontoura" (parlamentar.aspx?id=52), e a página
# de cada proposição liga o nome a esse código (conferido em 27/10/2026)
AUTORES = {"Armando Fontoura": "52"}
NOTAS = [
    ("As propostas vêm do Processo Legislativo Eletrônico, o sistema oficial da Câmara: a lista de cada tipo de proposição "
     "(planilha da própria consulta) e a página de cada uma, com o histórico da tramitação, de onde sai a situação (sanção, "
     "veto, parecer da Comissão de Justiça, arquivamento). Entram projetos de lei, de lei complementar, de emenda à Lei "
     "Orgânica, de decreto legislativo e de resolução apresentados desde 1º/1/2025; projetos de iniciativa popular, "
     "substitutivos, emendas, requerimentos, indicações e moções não entram. O primeiro nome da lista de autores de cada "
     "proposição aparece como autor principal, e os outros como quem assinou junto. Quando uma proposta é aprovada com "
     "mudanças (emendas), ela volta ao Plenário para a votação do texto final (a redação final), e o perfil mostra isso.",
     "Bills come from the Processo Legislativo Eletrônico, the City Council's official system: the list of each type of bill "
     "(the search's own spreadsheet) and each bill's page, with the history of its progress, which gives its status (signed, "
     "vetoed, Justice Committee opinion, shelved). Included: bills for ordinary and complementary laws, amendments to the "
     "city's Organic Law, legislative decrees and resolutions filed since January 1, 2025; citizen-initiative bills, "
     "substitute bills, amendments, requests, recommendations and motions are not included. The first name on each bill's "
     "list of authors is shown as its main author, and the others as co-signers. When a bill is approved with changes "
     "(amendments), it goes back to the full Council for a vote on the final text (the redação final), and the profile shows "
     "this."),
    ("As votações de cada vereador não entram neste site: a Câmara publica um boletim de votação por projeto, em PDF "
     "escaneado (imagem), sem dados abertos.",
     "Each councilor's votes are not included on this site: the City Council publishes one voting report per bill, as a "
     "scanned PDF (image), with no open data."),
    ("Gastos do mandato: segundo o portal da transparência, a Câmara de Vitória não instituiu cotas parlamentares desde "
     "1º/1/2023 (a verba de gabinete paga a equipe de cada gabinete).",
     "Office spending: according to its transparency portal, the Vitória City Council has had no office allowances since "
     "January 1, 2023 (the office budget pays each office's staff)."),
]


def coletar() -> dict:
    return Agape(IBGE, UF, HOST, CASA, 21, TIPOS, "vitoria", autores_manual=AUTORES, notas=NOTAS,
                 executivo=r"^prefeitura municipal|^prefeit|^poder executivo").coletar()
