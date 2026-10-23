"""Câmara Municipal de Cuiabá (MT): lista oficial de vereadores do Processo Legislativo Eletrônico (Ágape), https://legislativo.camaracuiaba.mt.gov.br/spl/parlamentares.aspx."""
from ._agape import coletar_agape

CASA = {"casa": "Câmara Municipal de Cuiabá", "casa_en": "Cuiabá City Council", "sigla": "CMC-MT", "site": "https://www.camaracuiaba.mt.gov.br"}
# conferidos à mão (mesmo partido; nome de urna no TSE, eleitos em 2024): "Marcus Brito Junior" (id 23) = MARCUS BRITO JR (PV);
# "Ranalli" (id 60) = POLICIALFEDERAL RAFAEL RANALLI (PL)
TSE = {"23": "110002017741", "60": "110002182549"}


def coletar() -> dict:
    return coletar_agape("5103403", "MT", "https://legislativo.camaracuiaba.mt.gov.br/spl", CASA, 27, TSE)
