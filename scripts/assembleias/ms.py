"""Assembleia Legislativa do Estado de Mato Grosso do Sul (Alems).

Lista oficial: https://www.al.ms.gov.br/api/v2/deputados (os 24 deputados em exercício: nome, partido, foto, e-mail, cargo
na Mesa), a mesma lista do site da Casa (página de cada um: /Deputados/Visualizar/<id>).
Gastos: CEAP (Cota para o Exercício da Atividade Parlamentar, a "verba indenizatória" de MS) no Portal da Transparência,
em arquivo CSV aberto com cada nota (https://transparencia2.al.ms.gov.br/ceap/notas/exportar-csv?ano=<ano>): total do ano
mais recente por categoria oficial e total desde fevereiro de 2023.
Propostas: NÃO entram. O sistema público de proposições da Alems (SGPL, http://sgpl.consulta.al.ms.gov.br/sgpl-publico/)
só responde depois de um desafio anti-robô (prova de trabalho) em cada acesso à API; não contornamos proteções dos sites
oficiais. Votações nominais: não há publicação aberta com o voto de cada deputado.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re

import regional
from comum import chave_nome, fonte, hoje, log, sem_acento

from ._nco_comum import (Rede, casar_membros, conferir_virada, gravar, legislatura_por_data, limpa_nome, membro, nome_civil,
                         partido_sigla)

SITE = "https://al.ms.gov.br"
API = "https://www.al.ms.gov.br/api/v2/deputados"
CEAP = "https://transparencia2.al.ms.gov.br/ceap"
VEICULO = "Assembleia Legislativa de Mato Grosso do Sul (Alems)"
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                     "outubro", "novembro", "dezembro"], 1)}
# conferido à mão (outubro de 2026): {nome na lista oficial: SQ do TSE de 2022 ou "-"}
# "Hashioka": o único Hashioka entre os candidatos de 2022 em MS é ROBERTO HASHIOKA SOLER (urna "Roberto Hashioka",
# eleito pelo União); a planilha da CEAP o chama de "DEP. HASHIOKA".
TSE_MANUAL: dict[str, str] = {"Hashioka": "120001609587"}


def _valor(s: str) -> float:
    return float(re.sub(r"[^\d,]", "", s or "0").replace(",", ".") or 0)


def _palavras_ceap(nome: str) -> set[str]:
    n = re.sub(r"(?i)^\s*dep\.?\s*", "", nome or "")
    n = re.sub(r"(?i)\bcel\.?\s", "Coronel ", n)
    n = re.sub(r"(?i)\bprof\.?\s", "Professor ", n)
    return set(regional.palavras(n))


def _liga_ceap(nome_ceap: str, membros: list[dict]) -> str | None:
    """Nome na planilha da CEAP ("Dep. Cel. David", "Dep. Pedro Arlei Caravina") -> id da pessoa na lista oficial."""
    alvo = _palavras_ceap(nome_ceap)
    achados = []
    for m in membros:
        p = set(regional.palavras(m["nome"]))
        if not p or not alvo:
            continue
        comum = p & alvo
        if p == alvo or ((p <= alvo or alvo <= p) and (len(comum) >= 2 or (len(comum) == 1 and len(next(iter(comum))) >= 5))):
            achados.append(m["id"])
    return achados[0] if len(achados) == 1 else None


def gastos(rede: Rede, membros: list[dict]) -> dict[str, dict]:
    """{id: bloco "gastos" do perfil} a partir das notas da CEAP (desde o começo da legislatura em curso)."""
    ano_atual = int(hoje()[:4])
    ini = regional.inicio_estadual("MS")
    ini_a, ini_m = int(ini[:4]), int(ini[5:7])
    por_pessoa: dict[str, dict] = {}
    sem_ligacao: dict[str, float] = {}
    for ano in range(ini_a, ano_atual + 1):
        txt = rede.texto(f"{CEAP}/notas/exportar-csv?ano={ano}", f"ceap/notas-{ano}.csv",
                         20 if ano >= ano_atual - (1 if hoje()[5:7] <= "02" else 0) else 24 * 30, codificacao="utf-8-sig")
        linhas = txt.splitlines()
        cab = next((k for k, l in enumerate(linhas) if l.startswith("Deputado;")), None)
        if cab is None:
            raise RuntimeError(f"MS: a planilha da CEAP de {ano} mudou de formato")
        for r in csv.DictReader(io.StringIO("\n".join(linhas[cab:])), delimiter=";"):
            mes = MESES.get(sem_acento((r.get("Mês") or "").lower()).strip())
            if not mes or (ano, mes) < (ini_a, ini_m):
                continue
            nome = (r.get("Deputado") or "").strip()
            pid = _liga_ceap(nome, membros)
            v = _valor(r.get("Valor (R$)"))
            if not pid:
                sem_ligacao[nome] = sem_ligacao.get(nome, 0) + v
                continue
            g = por_pessoa.setdefault(pid, {"anos": {}, "cat": {}, "meses": {}})
            g["anos"][ano] = g["anos"].get(ano, 0) + v
            g["meses"].setdefault(ano, set()).add(mes)
            cat = re.sub(r"\s+", " ", (r.get("Categoria") or "").strip()) or "Outros"
            g["cat"].setdefault(ano, {})
            g["cat"][ano][cat] = g["cat"][ano].get(cat, 0) + v
    if sem_ligacao:
        log(f"  MS CEAP: nomes da planilha sem pessoa na lista de hoje (quem saiu): {sorted(sem_ligacao)}")
    out = {}
    for pid, g in por_pessoa.items():
        ano = max(g["anos"])
        out[pid] = {
            "ano": ano, "total": round(g["anos"][ano], 2),
            "porTipo": [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(g["cat"][ano].items(), key=lambda x: (-x[1], x[0]))],
            "mandatoTotal": round(sum(g["anos"].values()), 2), "desde": ini[:7],
            "nome": "CEAP (cota para o exercício da atividade parlamentar)", "nome_en": "Office allowance (CEAP, cota parlamentar)",
            "meses": [f"{ano}-{min(g['meses'][ano]):02d}", f"{ano}-{max(g['meses'][ano]):02d}"],
            "fonte": fonte(VEICULO, "CEAP: notas de cada deputado (Portal da Transparência da Alems)", CEAP, hoje()),
        }
    return out


def coletar() -> dict:
    rede = Rede("alems", pausa=1.0)
    lista = rede.json(API, "deputados.json", 20)
    if not isinstance(lista, list) or len(lista) < 20:
        raise RuntimeError(f"MS: a lista oficial veio com {len(lista) if isinstance(lista, list) else '?'} pessoas")
    casar = [{"chave": str(d["id"]), "nome": limpa_nome(d.get("nome")), "nomeCivil": None,
              "partido": partido_sigla(d.get("sigla") or d.get("partido"))} for d in lista]
    ligados, avisos = casar_membros("MS", casar, TSE_MANUAL)
    for a in avisos:
        log(f"  MS TSE: {a}")
    fonte_lista = fonte(VEICULO, "Deputados em exercício (lista oficial do site da Alems)", f"{SITE}/Partidos/Lista")
    membros, extras = [], {}
    for d, c in zip(lista, casar):
        cand = ligados.get(c["chave"])
        pid = regional.id_pessoa("dest", "MS", cand, c["nome"])
        genero = {"deputada": "F", "deputado": "M"}.get(sem_acento((d.get("genero") or "").lower()).strip()) or (cand or {}).get("genero")
        url = f"{SITE}/Deputados/Visualizar/{d['id']}"
        civil = nome_civil(None, c["nome"], cand)
        membros.append(membro(pid, c["nome"], civil, c["partido"], genero, d.get("imagem"), url,
                              bool(cand and cand["sit"] == "SUPLENTE")))
    g = gastos(rede, membros)
    for m, d in zip(membros, lista):
        x = {"links": {"oficial": m["url"], "email": (d.get("email") or "").strip() or None, "redes": []},
             "fontes": [fonte_lista, fonte(VEICULO, f"Página oficial de {m['nome']}", m["url"])]}
        if m["id"] in g:
            x["gastos"] = dict(g[m["id"]], fonte=fonte(VEICULO, f"CEAP (cota parlamentar) de {m['nome']}: notas no Portal da Transparência",
                                                        f"{CEAP}?ano={g[m['id']]['ano']}"))
            x["fontes"].append(x["gastos"]["fonte"])
        extras[m["id"]] = x
    cobertura = {"lista": True, "propostas": False, "votacoes": False, "gastos": bool(g)}
    leg = legislatura_por_data("02-01")
    conferir_virada(rede, "MS", [str(d["id"]) for d in lista], leg)
    notas = [
        ("As propostas de cada deputado ainda não entram: o sistema de proposições da Alems (SGPL) exige um teste anti-robô "
         "a cada consulta, e o site não contorna proteções.",
         "Each deputy's bills are not included yet: the Alems bill system (SGPL) requires an anti-bot test for every "
         "query, and this site does not get around such protections."),
        ("Gastos: CEAP (cota parlamentar), com as notas publicadas no Portal da Transparência da Alems.",
         "Spending: CEAP (the office allowance), from the receipts published on the Alems transparency portal."),
    ]
    r = gravar("MS", {"casa": "Assembleia Legislativa do Estado de Mato Grosso do Sul",
                      "casa_en": "Legislative Assembly of the State of Mato Grosso do Sul", "sigla": "Alems",
                      "site": "https://www.al.ms.gov.br"},
               membros, extras, cobertura, fonte_lista, notas, minimo=20, legislatura=leg)
    log(f"  MS: {len(g)} pessoas com gastos da CEAP; {rede.pedidos} pedidos ao site oficial")
    return r
