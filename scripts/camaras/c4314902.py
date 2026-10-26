"""Câmara Municipal de Porto Alegre (RS): só a lista oficial de vereadores em exercício (www.camarapoa.rs.gov.br/vereadores).

A página separa quem está no cargo ("titulares", com os suplentes que assumiram) de quem está de licença. As proposições
ficam no sistema de processos da Câmara (páginas HTML), sem dados abertos para baixar: não entram (nota da Câmara abaixo).
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "4314902", "RS", "https://www.camarapoa.rs.gov.br"
CASA = {"casa": "Câmara Municipal de Porto Alegre", "casa_en": "Porto Alegre City Council", "sigla": "CMPA", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    lista = t.split('id="titulares"', 1)[1].split("</ul>", 1)[0]
    pessoas = []
    for href, foto, alt, nome in re.findall(r'<a href="(/vereadores/[^"]+)"><img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>\s*<h2>(.*?)</h2>', lista):
        nome = html.unescape(re.sub(r"<[^>]+>", "", nome)).strip()
        m = re.match(r"(.*?)\s*\(([^)]+)\)\s*$", nome)
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": m.group(1) if m else nome, "partido": m.group(2) if m else None,
                        "foto": foto, "url": SITE + href})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores em exercício (portal oficial)", f"{SITE}/vereadores", hoje())
    notas = [("As propostas dos vereadores não entram neste site: a Câmara publica as proposições só no sistema de processos "
              "do site (páginas HTML), sem arquivo nem API de dados abertos.",
              "Councilors' bills are not included on this site: the City Council publishes its bills only as web pages in its "
              "case system, with no open data file or API.")]
    return B.so_lista(IBGE, UF, CASA, pessoas, 35, notas)
