"""Câmara Municipal de Belém (PA): só a lista oficial de vereadores (www.cmb.pa.gov.br/vereadores).

O site oficial lista os projetos por tipo em páginas HTML (www.cmb.pa.gov.br/legislacao/projetos-de-lei), sem dizer o
autor de forma estruturada nem oferecer dados abertos: as propostas ainda não entram aqui.
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
    notas = [("O site da Câmara lista os projetos em páginas HTML, sem o autor de forma organizada e sem dados abertos: "
              "por enquanto, só a lista oficial de quem está no cargo.",
              "The City Council's website lists bills as web pages, without structured author information or open data: "
              "for now, only the official list of who is in office.")]
    return B.so_lista(IBGE, UF, CASA, pessoas, 35, notas)
