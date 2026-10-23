"""Câmara Municipal do Rio de Janeiro (RJ): só a lista oficial de vereadores atuais
(www.camara.rio/vereadores/quem-sao, que mostra a tabela www.camara.rio/includes_php/vereadores_atuais.php).

A foto vem embutida na própria tabela; o partido vem do logotipo de cada linha. As proposições ficam no sistema Lotus Notes
da Câmara (aplicnt.camara.rj.gov.br/APL/Legislativos/scpro.nsf), que até entrega as listas em JSON (?ReadViewEntries), mas
a situação de cada projeto só aparece na página de cada um, em texto livre: ainda não entram aqui.
O site usa uma cadeia de certificados incompleta (o navegador completa sozinho; o Python não): por isso esta página é lida
sem conferir o certificado; o resultado é conferido pelo número de vagas (51) e pelos nomes do TSE.
"""
import html
import re
import ssl

from comum import fonte, hoje

from . import _base as B

IBGE, UF, SITE = "3304557", "RJ", "https://www.camara.rio"
PAGINA = f"{SITE}/includes_php/vereadores_atuais.php?imprimir=N"
CASA = {"casa": "Câmara Municipal do Rio de Janeiro", "casa_en": "Rio de Janeiro City Council", "sigla": "CMRJ", "site": SITE,
        "sistema": "Portal oficial (HTML)"}


def coletar() -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    t = B.baixar_pagina(PAGINA, IBGE, "vereadores", contexto=ctx)
    pessoas = []
    for linha in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", t):
        cvd = re.search(r"vereador\.php\?cvd=(\d+)'[^>]*>\s*([^<]+?)\s*</a>", linha)
        foto = re.search(r'<img src="(data:image/[^"]+)"', linha)
        sigla = re.search(r'partido_politico/[^"]+"\s+alt="([^"]*)"', linha)
        email = re.search(r'href="mailto:([^"]+)"', linha)
        if not cvd:
            continue
        pessoas.append({"chave": cvd.group(1), "nome": html.unescape(cvd.group(2)).strip(),
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                        "foto": foto.group(1) if foto else None,
                        "url": f"{SITE}/includes_php/vereador.php?cvd={cvd.group(1)}",
                        "email": html.unescape(email.group(1)).strip() if email else None})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores atuais (portal oficial)", f"{SITE}/vereadores/quem-sao", hoje())
    notas = [("A Câmara publica a lista de projetos no sistema Lotus Notes (aplicnt.camara.rj.gov.br), mas a situação de cada "
              "um só aparece na página do projeto, em texto livre: por enquanto, só a lista oficial de quem está no cargo.",
              "The City Council lists its bills in its Lotus Notes system (aplicnt.camara.rj.gov.br), but the status of each one "
              "only appears on the bill's own page, as free text: for now, only the official list of who is in office.")]
    return B.so_lista(IBGE, UF, CASA, pessoas, 51, notas)
