"""Câmara Municipal de Curitiba (PR): só a lista oficial de vereadores em exercício (www.cmc.pr.gov.br/vereadores/conheca-os-vereadores).

O partido vem do logotipo de cada cartão ("Logo União"). As proposições ficam só no Sistema de Proposições Legislativas (SPL,
www.cmc.pr.gov.br/wspl), que pede um código de imagem (CAPTCHA) para entrar — conferido em 27/10/2026 na consulta de
proposições e na de votações; este site não contorna esse tipo de bloqueio: as propostas e o que a prefeitura mandou à
Câmara não entram (nota da Câmara abaixo). O portal novo da Câmara não tem página de proposição (só notícias e o "Painel de
Atividades", um gráfico de terceiros). Gastos: a página de perguntas frequentes da Câmara diz que o vereador recebe só o
subsídio, sem verba de gabinete nem cota de ressarcimento (conferido em 27/10/2026).
O site da Câmara não aceita o acesso do robô do GitHub (servidores nos EUA): Curitiba é atualizada de um computador no
Brasil (scripts/atualizar_do_brasil.py). Se o site não responder, o coletor lança a exceção e fica o arquivo de antes.
"""
import html
import re

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "4106902", "PR", "https://www.cmc.pr.gov.br"
PAGINA = f"{SITE}/vereadores/conheca-os-vereadores"
CASA = {"casa": "Câmara Municipal de Curitiba", "casa_en": "Curitiba City Council", "sigla": "CMC", "site": SITE,
        "sistema": "Portal oficial (HTML)", "sic": f"{SITE}/atendimento/acesso-a-informacao-sic"}


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
    notas = [("As propostas dos vereadores e os projetos da prefeitura não entram neste site: a Câmara publica as proposições "
              "só no seu Sistema de Proposições Legislativas (SPL), que pede um código de imagem (CAPTCHA) para entrar, e este "
              "site não contorna esse tipo de bloqueio. As proposições podem ser vistas no próprio SPL "
              "(www.cmc.pr.gov.br/wspl).",
              "Councilors' bills and the mayor's bills are not included on this site: the City Council publishes its bills "
              "only in its Legislative Bills System (SPL), which asks for an image code (CAPTCHA) to get in, and this site "
              "does not get around that kind of block. The bills can be seen in the SPL itself (www.cmc.pr.gov.br/wspl).")]
    # conferido à mão: "Pier Petruzziello" no portal da Câmara = PIER no TSE (Pierpaolo Petruzziello, eleito em 2024)
    return B.so_lista(IBGE, UF, CASA, pessoas, 38, notas, tse_manual={"pier-petruzziello": "160002073993"})
