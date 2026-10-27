"""Câmara Municipal de João Pessoa (PB): SAPL 3 do Interlegis, API pública em https://sapl.joaopessoa.pb.leg.br/api/ (lista
oficial, propostas, prefeito e votações), e os gastos do mandato pela tabela de verbas indenizatórias do site da Câmara
(scripts/camaras/_jp_gastos.py: um pedido por dia; se falhar, ficam os gastos publicados antes)."""
from . import _capitais_c as C
from . import _jp_gastos as J
from ._sapl import Sapl


def coletar() -> dict:
    antes = C.publicados(J.IBGE, "gastos")  # o SAPL regrava o arquivo da cidade: os gastos de antes ficam guardados aqui
    r = Sapl("2507507", "PB", "https://sapl.joaopessoa.pb.leg.br", casa="Câmara Municipal de João Pessoa",
             casa_en="João Pessoa City Council", sigla="CMJP", site="https://www.joaopessoa.pb.leg.br", prefixo="cmjoaopessoa",
             pausa=1.0, nota_gastos=J.NOTA_SEM).coletar()
    return J.aplicar(r, antes, C.Rede(J.IBGE, 1.0))
