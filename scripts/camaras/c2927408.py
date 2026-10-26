"""Câmara Municipal de Salvador (BA): só a lista oficial de vereadores da legislatura atual (www.cms.ba.gov.br/vereadores,
aba "Vereadores - 20ª Legislatura"; quem saiu ou está de licença fica em outra aba, que não entra).

As proposições estão no sistema legislativo da Câmara, em páginas HTML, sem dados abertos: não entram (nota da Câmara abaixo).
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "2927408", "BA", "https://www.cms.ba.gov.br"
CASA = {"casa": "Câmara Municipal de Salvador", "casa_en": "Salvador City Council", "sigla": "CMS", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    i, j = t.find('id="vereadores"'), t.find('id="exvereadores_licenciados"')
    if i < 0 or j < i:
        raise RuntimeError("a página de vereadores mudou")
    secao = t[i:j]
    emails = {}
    for nome, email in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", secao, re.S):
        emails[re.sub(r"\W", "", html.unescape(nome).lower())] = html.unescape(email).strip() or None
    pessoas = []
    for href, foto, nome, sigla in re.findall(r"getUrl\('([^']+)'.*?background-image: url\('([^']+)'\).*?"
                                              r'<div class="name">\s*<p>(.*?)</p>.*?<div class="partido">\s*<p>(.*?)</p>', secao, re.S):
        nome = html.unescape(nome).strip()
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": nome, "partido": html.unescape(sigla).strip() or None,
                        "foto": SITE + foto if foto.startswith("/") else foto, "url": SITE + href,
                        "email": emails.get(re.sub(r"\W", "", nome.lower()))})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores - 20ª Legislatura (portal oficial)", f"{SITE}/vereadores", hoje())
    notas = [("As propostas dos vereadores não entram neste site: a Câmara publica as proposições só no sistema legislativo "
              "dela, em páginas HTML, sem dados abertos.",
              "Councilors' bills are not included on this site: the City Council publishes its bills only in its legislative "
              "system, as web pages, without open data.")]
    # conferidos à mão (mesmo partido; nome de urna no TSE): "Omarzinho Gordilho" = OMARZINHO (Omar Antonio Gordilho de Britto,
    # PDT); "Téo Senna" = THEO SENNA (Theofilo Virgilio de Senna, PSDB), eleitos em 2024
    return B.so_lista(IBGE, UF, CASA, pessoas, 43, notas,
                      tse_manual={"omarzinho-gordilho": "50001921919", "teo-senna": "50001884200"})
