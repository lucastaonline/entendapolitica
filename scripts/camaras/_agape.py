"""Câmaras que usam o "Processo Legislativo Eletrônico" da Ágape (páginas /spl/ em ASP.NET): Vitória, Teresina e Cuiabá.

O sistema mostra, em /spl/parlamentares.aspx, os vereadores da legislatura atual em dois grupos: "Ativo" (quem está no
cargo, inclusive suplentes que assumiram) e "Suplente" (suplentes que já exerceram e saíram). Aqui entra só o grupo "Ativo".
As proposições estão no mesmo sistema (consulta-producao.aspx?autor=...), mas só em páginas HTML lentas (cerca de 20 s
cada), paginadas por formulário (postback) e com milhares de indicações misturadas: as propostas não entram (a nota da
Câmara diz isso na página da cidade e no perfil).
"""
from __future__ import annotations

import html
import re

from comum import fonte, hoje

from . import _base as B


def coletar_agape(ibge: str, uf: str, base: str, casa: dict, vagas: int, tse_manual: dict | None = None) -> dict:
    """base = endereço do sistema até /spl (ex.: https://camarasempapel.cmv.es.gov.br/spl)."""
    pagina = f"{base}/parlamentares.aspx"
    t = B.baixar_pagina(pagina, ibge, "parlamentares", ua_navegador=True)
    leg = re.search(r'id="ContentPlaceHolder1_legislatura_data"[^>]*>([^<]+)<', t)
    partes = re.split(r"<div class='custom-legend[^']*'>\s*", t)
    ativos = next((p for p in partes[1:] if p.strip().lower().startswith("ativo")), None)
    if ativos is None:
        raise RuntimeError("o sistema não mostrou o grupo de vereadores ativos")
    pessoas = []
    for bloco in ativos.split("custom-user-profile'>")[1:]:
        pid = re.search(r"href='parlamentar\.aspx\?id=(\d+)'", bloco)
        nome = re.search(r"class='kt-widget__username pb-1'>\s*(.*?)\s*</a>", bloco, re.S)
        sigla = re.search(r"<small>\((.*?)\)</small>", bloco)
        foto = re.search(r"<img class='kt-widget__img' src='([^']+)'", bloco)
        if not (pid and nome):
            continue
        f = html.unescape(foto.group(1)) if foto else None
        if f and re.search(r"sem[-_]?foto|avatar|default", f, re.I):
            f = None
        pessoas.append({"chave": pid.group(1), "nome": html.unescape(nome.group(1)).strip(),
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                        "foto": f, "url": f"{base}/parlamentar.aspx?id={pid.group(1)}"})
    casa = dict(casa, sistema="Processo Legislativo Eletrônico (Ágape)",
                fonte=fonte(casa["casa"], "Vereadores ativos na legislatura atual" + (f" ({leg.group(1).strip()})" if leg else ""),
                            pagina, hoje()))
    notas = [("As propostas dos vereadores não entram neste site: a Câmara mostra as proposições só em páginas do sistema de "
              "processo legislativo (lentas e paginadas por formulário), sem dados abertos. Dá para procurar cada uma lá.",
              "Councilors' bills are not included on this site: the City Council shows its bills only as web pages in its "
              "legislative system (slow and paginated through forms), without open data. You can look each one up there.")]
    return B.so_lista(ibge, uf, casa, pessoas, vagas, notas, tse_manual=tse_manual)
