"""Câmara Municipal de João Pessoa (PB): SAPL 3 do Interlegis, API pública em https://sapl.joaopessoa.pb.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("2507507", "PB", "https://sapl.joaopessoa.pb.leg.br", casa="Câmara Municipal de João Pessoa",
                casa_en="João Pessoa City Council", sigla="CMJP", site="https://www.joaopessoa.pb.leg.br", prefixo="cmjoaopessoa", pausa=1.0).coletar()
