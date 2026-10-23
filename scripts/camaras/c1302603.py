"""Câmara Municipal de Manaus (AM): SAPL 3 do Interlegis, API pública em https://sapl.cmm.am.gov.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("1302603", "AM", "https://sapl.cmm.am.gov.br", casa="Câmara Municipal de Manaus",
                casa_en="Manaus City Council", sigla="CMM", site="https://www.cmm.am.gov.br", prefixo="cmmanaus").coletar()
