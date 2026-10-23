"""Câmara Municipal de Curitiba (PR): só a lista oficial de vereadores em exercício (www.cmc.pr.gov.br/vereadores/conheca-os-vereadores).

O partido vem do logotipo de cada cartão ("Logo União"). As proposições ficam no sistema SPL da Câmara
(www.cmc.pr.gov.br/wspl/sistema/ProposicaoConsultaForm.do), em páginas HTML, sem dados abertos: ainda não entram aqui.
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "4106902", "PR", "https://www.cmc.pr.gov.br"
PAGINA = f"{SITE}/vereadores/conheca-os-vereadores"
CASA = {"casa": "Câmara Municipal de Curitiba", "casa_en": "Curitiba City Council", "sigla": "CMC", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(PAGINA, IBGE, "vereadores", ua_navegador=True)  # o site barra robôs sem "Mozilla/5.0" (erro 403)
    pessoas = []
    for bloco in t.split('item-vereador">')[1:]:
        href = re.search(r'<a href="(/vereadores/[^"]+)"', bloco)
        foto = re.search(r'<img[^>]+src="([^"]+)"', bloco)
        logo = re.search(r'alt="Logo ([^"]+)"', bloco)
        nome = re.search(r"<h3[^>]*>(.*?)</h3>", bloco, re.S)
        if not (href and nome):
            continue
        f = html.unescape(foto.group(1)) if foto else None
        pessoas.append({"chave": href.group(1).rsplit("/", 1)[-1], "nome": html.unescape(re.sub(r"<[^>]+>", "", nome.group(1))).strip(),
                        "partido": html.unescape(logo.group(1)).strip() if logo else None,
                        "foto": SITE + f if f and f.startswith("/") else f, "url": SITE + href.group(1)})
    CASA["fonte"] = fonte(CASA["casa"], "Conheça os vereadores (portal oficial)", PAGINA, hoje())
    notas = [("As proposições estão no sistema SPL da Câmara, em páginas HTML, sem dados abertos: por enquanto, só a lista "
              "oficial de quem está no cargo.",
              "The City Council's bills are in its SPL system, as web pages, without open data: for now, only the official "
              "list of who is in office.")]
    # conferido à mão: "Pier Petruzziello" no portal da Câmara = PIER no TSE (Pierpaolo Petruzziello, eleito em 2024)
    return B.so_lista(IBGE, UF, CASA, pessoas, 38, notas, tse_manual={"pier-petruzziello": "160002073993"})
