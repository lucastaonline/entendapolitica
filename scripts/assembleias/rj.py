"""Assembleia Legislativa do Estado do Rio de Janeiro (Alerj): página oficial "Quem são" (deputados em exercício).

Lista: www.alerj.rj.gov.br/Deputados/QuemSao: nome, partido, foto e página de cada deputado da legislatura atual
(70 cadeiras, inclusive suplentes que assumiram).
Propostas: a Alerj não tem API nem arquivo aberto do processo legislativo. O sistema oficial de proposições
(Lotus Notes, alerjln1.alerj.rj.gov.br/scpro2327.nsf: "LeiInt", "LeiCompInt", "EmendaInt", "DecretoInt",
"ResolucaoInt") só mostra as 15 proposições mais recentes de cada tipo; o servidor fecha a conexão quando se pede
outra página ("&Start=") ou mais itens ("&Count=") e não aceita a saída estruturada do Notes ("?ReadViewEntries"); a
página de cada projeto leva ~20 s e não tem um campo de situação (só a lista de despachos). Por isso as propostas, as
votações e os gastos da Alerj ainda não entram (testado em 23/10/2026).
"""
from __future__ import annotations

import re

import regional
from comum import hoje, log, nome_proprio

from ._sse_comum import Rede, casar_membros, fonte, gravar, membro, partido_sigla, sem_html

UF = "RJ"
SITE = "https://www.alerj.rj.gov.br"
VEICULO = "Assembleia Legislativa do Estado do Rio de Janeiro (Alerj)"
CASA = {"casa": "Assembleia Legislativa do Estado do Rio de Janeiro", "casa_en": "Legislative Assembly of the State of Rio de Janeiro",
        "sigla": "Alerj", "site": SITE}

# ligações com o TSE conferidas à mão: {código do deputado na Alerj: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def coletar() -> dict:
    rede = Rede("alerj", pausa=1.5, timeout=120)
    t = rede.texto(f"{SITE}/Deputados/QuemSao", "quemsao.html", 20)
    pessoas = []
    for bloco in re.findall(r'<div class="controle_deputado[^"]*">(.*?)<span></span>', t, flags=re.S):
        m = re.search(r'href="/Deputados/PerfilDeputado/(\d+)\?Legislatura=(\d+)"', bloco)
        nome = sem_html((re.search(r'<div class="nome">(.*?)</div>', bloco, re.S) or [None, ""])[1])
        if not m or not nome:
            continue
        foto = (re.search(r'<img src="([^"]+)"', bloco) or [None, None])[1]
        pessoas.append({"chave": m.group(1), "nome": nome_proprio(nome), "nomeCivil": None,
                        "partido": partido_sigla(sem_html((re.search(r'<div class="partido">(.*?)</div>', bloco, re.S) or [None, ""])[1])),
                        "url": f"{SITE}/Deputados/PerfilDeputado/{m.group(1)}?Legislatura={m.group(2)}",
                        "foto": (SITE + foto) if foto and foto.startswith("/") else foto})
    if not 60 <= len(pessoas) <= 75:
        raise RuntimeError(f"Alerj: a lista oficial veio com {len(pessoas)} pessoas")
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    for a in avisos:
        log(f"  RJ: {a}")
    membros = []
    for p in pessoas:
        cand = casados.get(p["chave"])
        membros.append(membro(regional.id_pessoa("dest", UF, cand, p["nome"]), p["nome"], None, p["partido"],
                              (cand or {}).get("genero"), p["foto"], p["url"], (cand or {}).get("sit") == "SUPLENTE"))
    hj = hoje()
    f_lista = fonte(VEICULO, "Deputados da legislatura atual (página oficial \"Quem são\")", f"{SITE}/Deputados/QuemSao", hj)
    # o perfil ganha só o link da página oficial de cada um (e a fonte), para quem quiser ver o resto no site da Alerj
    extras = {m["id"]: {"links": {"oficial": m["url"], "email": None, "redes": []},
                        "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da Alerj", m["url"], hj)]} for m in membros}
    notas = [("A Alerj não publica o processo legislativo em formato aberto: o sistema oficial de proposições só mostra as "
              "15 mais recentes de cada lista e não deixa ver as outras páginas de forma automática. Propostas e votações "
              "ainda não entram.",
              "The Alerj does not publish its legislative process in an open format: the official bill system only shows the "
              "15 latest items of each list and does not allow automated access to the other pages. Bills and votes are not "
              "included yet."),
             ("Os deputados estaduais do Rio não recebem verba indenizatória (Portal da Transparência da Alerj, perguntas "
              "frequentes): por isso não há gastos dessa verba para mostrar.",
              "Rio de Janeiro's state deputies do not receive an expense allowance (Alerj transparency portal, FAQ), so there is "
              "no allowance spending to show.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": False, "votacoes": False, "gastos": False},
                  f_lista, None, None, notas)
