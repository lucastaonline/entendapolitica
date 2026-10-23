"""Câmara Municipal de Fortaleza (CE): SAPL 3 do Interlegis, API pública em https://sapl.fortaleza.ce.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("2304400", "CE", "https://sapl.fortaleza.ce.leg.br", casa="Câmara Municipal de Fortaleza",
                casa_en="Fortaleza City Council", sigla="CMFor", site="https://www.cmfor.ce.gov.br", prefixo="cmfortaleza").coletar()
