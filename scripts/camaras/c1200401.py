"""Câmara Municipal de Rio Branco (AC): SAPL 3 do Interlegis, API pública em https://sapl.riobranco.ac.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("1200401", "AC", "https://sapl.riobranco.ac.leg.br", casa="Câmara Municipal de Rio Branco",
                casa_en="Rio Branco City Council", sigla="CMRB", site="https://www.riobranco.ac.leg.br", prefixo="cmriobranco").coletar()
