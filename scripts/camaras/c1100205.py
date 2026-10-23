"""Câmara Municipal de Porto Velho (RO): SAPL 3 do Interlegis, API pública em https://sapl.portovelho.ro.leg.br/api/."""
from ._sapl import Sapl

# Conferido à mão em 23/10/2026: o SAPL marca como ativos os 23 eleitos e mais dois suplentes, mas a Câmara tem 23 vagas.
# - Dr. Gilber (id 28) está afastado (mandato com "Afastamento para tratar de assuntos particulares") e Léo Alencar (id 59)
#   assumiu de 3/8 a 1º/12/2026: fica Léo Alencar e sai Dr. Gilber até 1º/12/2026;
# - Claudio da Padaria (id 61, suplente no TSE) aparece como titular desde 1º/1/2025, sem nenhuma proposta e sem vaga
#   aberta para ele: fica de fora até a Câmara corrigir o cadastro.
EXCLUIR = {28: "2026-12-01", 61: None}


def coletar() -> dict:
    return Sapl("1100205", "RO", "https://sapl.portovelho.ro.leg.br", casa="Câmara Municipal de Porto Velho",
                casa_en="Porto Velho City Council", sigla="CMPV", site="https://www.portovelho.ro.leg.br",
                prefixo="cmportovelho", excluir=EXCLUIR).coletar()
