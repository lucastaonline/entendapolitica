"""Assembleia Legislativa do Estado de Mato Grosso (ALMT).

Lista oficial: https://www.al.mt.gov.br/parlamento/deputados (os 24 em exercício, com partido e foto) e a página de cada
um (/parlamento/deputados/<id>/perfil: nome civil, nome parlamentar, partido).
Propostas e votações: NÃO entram. A busca de proposições do site (/proposicao?...) é proibida para robôs no robots.txt da
ALMT, a página de cada deputado só mostra as 10 mais recentes, e a API da Casa (https://api.al.mt.gov.br/) exige
cadastro (OAuth 2.0): sem credencial, responde 403. Gastos: a verba indenizatória de MT é um valor mensal fixo (Lei
9.493/2010); o site publica só as leis, não um gasto por deputado (a pesquisa do Portal da Transparência também é
proibida para robôs).
"""
from __future__ import annotations

import html as _html
import re

import regional
from comum import fonte, log

from ._nco_comum import (Rede, casar_membros, conferir_virada, gravar, legislatura_por_data, limpa_civil, limpa_nome, membro,
                         nome_civil, partido_sigla, texto_html)

SITE = "https://www.al.mt.gov.br"
VEICULO = "Assembleia Legislativa de Mato Grosso (ALMT)"
TSE_MANUAL: dict[str, str] = {}


def _campo(txt: str, rotulo: str) -> str | None:
    m = re.search(rotulo + r"\s*:\s*(.+?)\s+(?:Nome civil|Nome parlamentar|Filiação partidária|Votação|Perfil)\b", txt)
    return m.group(1).strip() if m else None


def coletar() -> dict:
    rede = Rede("almt", pausa=1.5)
    pagina = rede.texto(f"{SITE}/parlamento/deputados", "deputados.html", 20)
    cards = re.findall(r'<a href="/parlamento/deputados/(\d+)/perfil">\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)".*?'
                       r'<span class="badge[^"]*">\s*(.*?)\s*</span>.*?<h6[^>]*>(.*?)</h6>', pagina, re.S)
    vistos, lista = set(), []
    for did, foto, alt, partido, nome in cards:
        if did in vistos:
            continue
        vistos.add(did)
        perfil = rede.texto(f"{SITE}/parlamento/deputados/{did}/perfil", f"perfil/{did}.html", 24 * 7)
        txt = texto_html(re.sub(r"<script.*?</script>|<style.*?</style>", " ", perfil, flags=re.S))
        lista.append({"id": did, "foto": _html.unescape(foto), "partido": texto_html(partido),
                      "nome": _campo(txt, "Nome parlamentar") or texto_html(alt) or texto_html(nome),
                      "civil": _campo(txt, "Nome civil"), "partido_perfil": _campo(txt, "Filiação partidária")})
    if len(lista) < 20:
        raise RuntimeError(f"MT: a página de deputados mudou (só {len(lista)} pessoas)")
    casar = [{"chave": d["id"], "nome": limpa_nome(d["nome"]), "nomeCivil": limpa_civil(d["civil"]),
              "partido": partido_sigla(d["partido"] or d["partido_perfil"])} for d in lista]
    ligados, avisos = casar_membros("MT", casar, TSE_MANUAL)
    for a in avisos:
        log(f"  MT TSE: {a}")
    fonte_lista = fonte(VEICULO, "Deputados em exercício (página oficial)", f"{SITE}/parlamento/deputados")
    membros, extras = [], {}
    for d, c in zip(lista, casar):
        cand = ligados.get(c["chave"])
        pid = regional.id_pessoa("dest", "MT", cand, c["nome"])
        url = f"{SITE}/parlamento/deputados/{d['id']}/perfil"
        membros.append(membro(pid, c["nome"], nome_civil(c["nomeCivil"], c["nome"], cand), c["partido"],
                              (cand or {}).get("genero"), d["foto"], url, bool(cand and cand["sit"] == "SUPLENTE")))
        extras[pid] = {"links": {"oficial": url, "email": None, "redes": []},
                       "fontes": [fonte_lista, fonte(VEICULO, f"Perfil de {c['nome']} (página oficial)", url)]}
    cobertura = {"lista": True, "propostas": False, "votacoes": False, "gastos": False}
    leg = legislatura_por_data("02-01")
    conferir_virada(rede, "MT", [d["id"] for d in lista], leg)
    notas = [
        ("As propostas e as votações de cada deputado ainda não entram: a busca de proposições do site da ALMT é fechada "
         "para robôs e a API da Casa exige cadastro.",
         "Each deputy's bills and votes are not included yet: the ALMT website's bill search is closed to robots and the "
         "assembly's API requires registration."),
    ]
    r = gravar("MT", {"casa": "Assembleia Legislativa do Estado de Mato Grosso", "casa_en": "Legislative Assembly of the State of Mato Grosso",
                      "sigla": "ALMT", "site": SITE}, membros, extras, cobertura, fonte_lista, notas, minimo=20, legislatura=leg)
    log(f"  MT: {rede.pedidos} pedidos ao site oficial")
    return r
