"""Câmara Municipal de São Luís (MA): só a lista oficial de vereadores (www.cmsaoluis.ma.gov.br/vereadores).

As proposições ficam na pesquisa do site (www.cmsaoluis.ma.gov.br/atividade-legislativa/proposicoes/pesquisa), em
páginas HTML, sem dados abertos: ainda não entram aqui.
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "2111300", "MA", "https://www.cmsaoluis.ma.gov.br"
CASA = {"casa": "Câmara Municipal de São Luís", "casa_en": "São Luís City Council", "sigla": "CMSL", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    pessoas = []
    for href, foto, civil, sigla, nome in re.findall(
            r'<a href="([^"]+/vereadores/[^"]+)"[^>]*>\s*<img src="([^"]+)" alt="([^"]*)"[^>]*>\s*<div class="panel-footer">\s*'
            r'<strong class="sigla-partido">(.*?)</strong>\s*<strong class="panel-title[^"]*">(.*?)</strong>', t, re.S):
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": html.unescape(nome).strip(),
                        "nomeCivil": html.unescape(civil).strip() or None, "partido": html.unescape(sigla).strip() or None,
                        "foto": foto, "url": href})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores (portal oficial)", f"{SITE}/vereadores", hoje())
    notas = [("A Câmara mostra as proposições numa pesquisa do site (páginas HTML), sem dados abertos: por enquanto, só a "
              "lista oficial de quem está no cargo.",
              "The City Council shows its bills in a search on its website (web pages), without open data: for now, only "
              "the official list of who is in office.")]
    # conferido à mão: "Nato Júnior" no site da Câmara = NATO JR no TSE (José Raimundo Alves Sena Junior, PSB, eleito em 2024)
    return B.so_lista(IBGE, UF, CASA, pessoas, 31, notas, tse_manual={"nato-junior": "100001943522"})
