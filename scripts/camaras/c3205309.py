"""Câmara Municipal de Vitória (ES): lista oficial de vereadores do Processo Legislativo Eletrônico (Ágape), https://camarasempapel.cmv.es.gov.br/spl/parlamentares.aspx."""
from ._agape import coletar_agape

CASA = {"casa": "Câmara Municipal de Vitória", "casa_en": "Vitória City Council", "sigla": "CMV", "site": "https://www.cmv.es.gov.br"}


def coletar() -> dict:
    return coletar_agape("3205309", "ES", "https://camarasempapel.cmv.es.gov.br/spl", CASA, 21)
