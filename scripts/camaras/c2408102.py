"""Câmara Municipal de Natal (RN): SAPL 3 do Interlegis, API pública em https://sapl.natal.rn.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("2408102", "RN", "https://sapl.natal.rn.leg.br", casa="Câmara Municipal de Natal",
                casa_en="Natal City Council", sigla="CMN", site="https://www.cmnat.rn.gov.br", prefixo="cmnatal").coletar()
