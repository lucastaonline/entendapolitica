"""Câmara Municipal de Goiânia (GO): só a lista oficial de vereadores em exercício
(www.goiania.go.leg.br/institucional/parlamentares, seção "20ª Legislatura"; quem está de licença fica na seção
"Parlamentares fora de exercício", que não entra). As proposições não têm dados abertos para baixar.
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "5208707", "GO", "https://www.goiania.go.leg.br"
PAGINA = f"{SITE}/institucional/parlamentares"
CASA = {"casa": "Câmara Municipal de Goiânia", "casa_en": "Goiânia City Council", "sigla": "CMG", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(PAGINA, IBGE, "parlamentares")
    ini = re.search(r"<h3>\s*\d+ª Legislatura:[^<]*</h3>", t)
    fim = t.find("Parlamentares fora de exerc")
    if not ini or fim < 0:
        raise RuntimeError("a página de parlamentares mudou")
    secao = t[ini.end():fim]
    pessoas = []
    for href, foto, nome, resto in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>\s*<strong>(.*?)</strong>(.*?)</a>', secao, re.S):
        nome = html.unescape(re.sub(r"<[^>]+>", " ", nome)).strip()
        sigla = html.unescape(re.sub(r"<[^>]+>", " ", resto)).strip(" ,\n")
        pessoas.append({"chave": href.rstrip("/").rsplit("/", 1)[-1], "nome": nome, "partido": sigla or None, "foto": foto, "url": href})
    CASA["fonte"] = fonte(CASA["casa"], "Parlamentares da 20ª Legislatura em exercício (portal oficial)", PAGINA, hoje())
    notas = [("As propostas dos vereadores não entram neste site: a Câmara não publica as proposições em dados abertos, só em "
              "páginas e PDFs.",
              "Councilors' bills are not included on this site: the City Council does not publish its bills as open data, "
              "only as web pages and PDFs.")]
    return B.so_lista(IBGE, UF, CASA, pessoas, 37, notas)
