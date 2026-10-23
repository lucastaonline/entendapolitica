"""Câmara Municipal de Boa Vista (RR): SAPL 3 do Interlegis, API pública em https://sapl.boavista.rr.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("1400100", "RR", "https://sapl.boavista.rr.leg.br", casa="Câmara Municipal de Boa Vista",
                casa_en="Boa Vista City Council", sigla="CMBV", site="https://www.boavista.rr.leg.br", prefixo="cmboavista").coletar()
