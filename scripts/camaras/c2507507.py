"""Câmara Municipal de João Pessoa (PB): SAPL 3 do Interlegis, API pública em https://sapl.joaopessoa.pb.leg.br/api/."""
from ._sapl import Sapl


def coletar() -> dict:
    return Sapl("2507507", "PB", "https://sapl.joaopessoa.pb.leg.br", casa="Câmara Municipal de João Pessoa",
                casa_en="João Pessoa City Council", sigla="CMJP", site="https://www.joaopessoa.pb.leg.br", prefixo="cmjoaopessoa", pausa=1.0,
                nota_gastos=("Os gastos do mandato de cada vereador não entram neste site: o SAPL da Câmara não tem esse dado, e o "
                             "site da Câmara mostra a verba indenizatória numa tabela de página (um valor por mês, com os serviços "
                             "descritos em texto livre), sem dados abertos.",
                             "Each councilor's office spending is not included on this site: the City Council's SAPL system does "
                             "not have it, and the City Council's website shows the office allowance in a table on a web page (one "
                             "amount per month, with the services described in free text), with no open data.")).coletar()
