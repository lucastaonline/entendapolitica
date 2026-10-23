"""Câmara Municipal de Belo Horizonte (MG): só a lista oficial de vereadores em exercício (www.cmbh.mg.gov.br/vereadores).

As proposições ficam na pesquisa do site (www.cmbh.mg.gov.br/atividade-legislativa/pesquisar-proposicoes), em páginas
HTML, sem API nem arquivo de dados abertos: ainda não entram aqui. A Câmara publica a verba indenizatória de cada
vereador (www.cmbh.mg.gov.br/transparencia/vereadores/verba-indenizatoria), também só em páginas.
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "3106200", "MG", "https://www.cmbh.mg.gov.br"
CASA = {"casa": "Câmara Municipal de Belo Horizonte", "casa_en": "Belo Horizonte City Council", "sigla": "CMBH", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    pessoas = []
    for bloco in t.split('<div class="vereador">')[1:]:
        foto = re.search(r'<img[^>]+src="([^"]+)"', bloco)
        sigla = re.search(r'views-field-field-sigla">\s*<div class="field-content">(.*?)</div>', bloco, re.S)
        nome = re.search(r'views-field-title">\s*<span class="field-content"><a href="([^"]+)">(.*?)</a>', bloco, re.S)
        if not nome:
            continue
        pessoas.append({"chave": nome.group(1).rsplit("/", 1)[-1], "nome": html.unescape(nome.group(2)).strip(),
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                        "foto": html.unescape(foto.group(1)) if foto else None, "url": SITE + nome.group(1)})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores em exercício (portal oficial)", f"{SITE}/vereadores", hoje())
    notas = [("A Câmara mostra as proposições e a verba indenizatória em páginas do site, sem API nem arquivo de dados "
              "abertos: por enquanto, só a lista oficial de quem está no cargo.",
              "The City Council shows its bills and office allowance spending as web pages, with no API or open data file: "
              "for now, only the official list of who is in office.")]
    # conferidos à mão (nome no portal da Câmara = nome de urna no TSE, eleitos em 2024): "Trópia" = MARCELA TRÓPIA (NOVO);
    # "Vile Santos" = VILE (Wili dos Santos, PL)
    return B.so_lista(IBGE, UF, CASA, pessoas, 41, notas, tse_manual={"tr%C3%B3pia": "130001976053", "vile-santos": "130002172736"})
