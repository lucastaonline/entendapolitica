"""Câmara Municipal de Belém (PA): só a lista oficial de vereadores (www.cmb.pa.gov.br/vereadores).

O site oficial lista os projetos por tipo em páginas HTML (www.cmb.pa.gov.br/legislacao/projetos-de-lei), sem dizer o
autor de forma estruturada nem oferecer dados abertos: as propostas não entram (nota da Câmara abaixo).
"""
import html
import re

from comum import fonte, hoje, nome_proprio

from . import _base as B

IBGE, UF, SITE = "1501402", "PA", "https://www.cmb.pa.gov.br"
CASA = {"casa": "Câmara Municipal de Belém", "casa_en": "Belém City Council", "sigla": "CMB", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    pessoas = []
    for href, dnome, dpart, corpo in re.findall(r'<a href="([^"]+/vereador/[^"]+)"\s+class="vereador-card[^"]*"\s+data-name="([^"]*)"\s+data-partido="([^"]*)">(.*?)</a>', t, re.S):
        foto = re.search(r'<img[^>]+src="([^"]+)"', corpo)
        nome = re.search(r"<h3[^>]*>(.*?)</h3>", corpo, re.S)
        sigla = re.search(r"</h3>\s*<span[^>]*>(.*?)</span>", corpo, re.S)
        nome = html.unescape(nome.group(1)).strip() if nome else None
        if not nome:
            continue
        dnome = html.unescape(dnome).strip()
        civil = dnome[len(nome):].strip() if dnome.lower().startswith(nome.lower()) else None
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": nome, "nomeCivil": nome_proprio(civil) if civil else None,
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else dpart.upper(),
                        "foto": foto.group(1) if foto else None, "url": href})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores (portal oficial)", f"{SITE}/vereadores", hoje())
    notas = [("As propostas dos vereadores não entram neste site: a Câmara lista os projetos só em páginas do site, sem o "
              "autor de forma organizada e sem dados abertos.",
              "Councilors' bills are not included on this site: the City Council lists bills only as web pages, without "
              "structured author information or open data.")]
    return B.so_lista(IBGE, UF, CASA, pessoas, 35, notas)
