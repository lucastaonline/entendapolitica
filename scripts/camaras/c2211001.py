"""Câmara Municipal de Teresina (PI): lista oficial de vereadores do Processo Legislativo Eletrônico (Ágape), https://teresina.camarasempapel.com.br/spl/parlamentares.aspx."""
from ._agape import coletar_agape

CASA = {"casa": "Câmara Municipal de Teresina", "casa_en": "Teresina City Council", "sigla": "CMT", "site": "https://www.teresina.pi.leg.br"}


def coletar() -> dict:
    return coletar_agape("2211001", "PI", "https://teresina.camarasempapel.com.br/spl", CASA, 29)
