"""Base comum dos coletores das Assembleias Legislativas (scripts/assembleias/) e das Câmaras Municipais (scripts/camaras/).

Cada Casa tem um arquivo pequeno com a função coletar(), que usa estas ajudas e grava:
  dados/assembleias/<UF>.json  ou  dados/camaras/<IBGE>.json   lista oficial de quem está no cargo hoje e o que dá para ver
  dados/pessoas/<id>.json                                       só de quem tem dados a mais (propostas, votações, gastos),
                                                                com os mesmos campos dos perfis federais
O scripts/montar.py junta a lista oficial à página do estado ou da cidade (no lugar da lista de eleitos do TSE) e marca
"extras": true em quem tem o arquivo próprio. Contrato completo: README, seção "Assembleias e Câmaras Municipais".

Regras (as mesmas dos perfis federais):
- fonte oficial em tudo (comum.fonte), com link que uma pessoa consegue abrir;
- os mesmos tipos de proposta (TIPOS_REGIONAIS) e a mesma tabela de situações (comum.STATUS);
- nada inventado: o que não existe fica null;
- o id de cada pessoa é o mesmo da lista do TSE (dest-<UF>-<SQ 2022> e ver-<IBGE>-<SQ 2024>), achado pelo nome.
"""
from __future__ import annotations

import csv
import difflib
import io
import json
import re
import zipfile
from pathlib import Path

from comum import (CACHE, DADOS, PESSOAS, STATUS, STATUS_TXT, classificar_situacao, fonte, hoje, ler_json, log,
                   ordenar_propostas, resumo_propostas, salvar_json, sem_acento, sem_mudar_data, slug)

ASSEMBLEIAS = DADOS / "assembleias"
CAMARAS = DADOS / "camaras"
INICIO_ESTADUAL = "2023-02-01"   # começo da legislatura estadual atual
INICIO_MUNICIPAL = "2025-01-01"  # começo da legislatura municipal atual

# tipos de proposta que entram na lista, já com o nome comum do site. O "sigla" de cada proposta continua o oficial da Casa.
TIPOS_REGIONAIS = {
    "PL": "Projeto de lei", "PLP": "Projeto de lei complementar", "PEC": "Proposta de emenda à Constituição do estado",
    "PELO": "Proposta de emenda à Lei Orgânica do município", "PDL": "Projeto de decreto legislativo", "PRC": "Projeto de resolução",
}

_TSE_CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
_COMUNS = {"da", "de", "do", "das", "dos", "e", "d"}


# ---------------------------------------------------------------- nomes e TSE
def palavras(nome: str | None) -> list[str]:
    s = sem_acento(nome or "").lower()
    s = re.sub(r"\b(dr|dra|pr|pra|prof|profa|sgt|cel|cap|ten|del|delegad[oa]|pastor[a]?|vereador[a]?|deputad[oa]|irmao|irma|mestre)\b\.?", " ", s)
    return [p for p in re.sub(r"[^a-z0-9 ]", " ", s).split() if p not in _COMUNS]


def _cand_csv(ano: int):
    from comum import baixar_arquivo
    caminho = baixar_arquivo(f"{_TSE_CDN}consulta_cand_{ano}.zip", f"tse/consulta_cand_{ano}.zip", max_idade_h=None)
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
        brasil = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
        for nome in brasil or nomes:
            with z.open(nome) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def candidatos_tse(ano: int, cargos: set[str], uf: str) -> list[dict]:
    """Todos os candidatos (eleitos, suplentes e não eleitos) de um estado, num ano, para os cargos pedidos (DS_CARGO do TSE,
    em maiúsculas). Fica guardado em .cache/tse/regional/ para não ler o arquivo grande do TSE toda vez."""
    pasta = CACHE / "tse" / "regional"
    chave = f"{ano}-{'+'.join(sorted(c.replace(' ', '_') for c in cargos))}-{uf}.json"
    arq = pasta / chave
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))
    log(f"  TSE {ano}: lendo candidatos ({', '.join(sorted(cargos))}) para {uf}…")
    por_uf: dict[str, list] = {}
    for r in _cand_csv(ano):
        c = (r.get("DS_CARGO") or "").upper()
        if c not in cargos:
            continue
        por_uf.setdefault(r["SG_UF"], []).append({
            "sq": r["SQ_CANDIDATO"], "ue": r["SG_UE"], "nm_ue": r.get("NM_UE"), "cargo": c, "turno": r.get("NR_TURNO"),
            "nome": (r.get("NM_CANDIDATO") or "").strip(), "urna": (r.get("NM_URNA_CANDIDATO") or "").strip(),
            "social": (r.get("NM_SOCIAL_CANDIDATO") or "").strip(), "partido": (r.get("SG_PARTIDO") or "").strip(),
            "sit": (r.get("DS_SIT_TOT_TURNO") or "").upper().strip(), "genero": (r.get("DS_GENERO") or "")[:1] or None,
            "numero": r.get("NR_CANDIDATO"),
        })
    pasta.mkdir(parents=True, exist_ok=True)
    for u, lista in por_uf.items():  # grava todos os estados de uma vez: a próxima chamada já acha pronto
        salvar_json(pasta / f"{ano}-{'+'.join(sorted(c.replace(' ', '_') for c in cargos))}-{u}.json", lista)
    return por_uf.get(uf, [])


def _pontos(nomes_oficiais: list[str], c: dict) -> float:
    """Quanto um nome da lista oficial parece com um candidato do TSE (0 a 1)."""
    alvo = [set(palavras(n)) for n in nomes_oficiais if n]
    if not alvo:
        return 0.0
    melhor = 0.0
    for campo in ("urna", "nome", "social"):
        cand = set(palavras(c.get(campo)))
        if not cand:
            continue
        for a in alvo:
            if not a:
                continue
            if a == cand:
                return 1.0
            if a <= cand or cand <= a:  # todas as palavras de um estão no outro ("Fulano Silva" e "Fulano da Silva Souza")
                melhor = max(melhor, 0.9 if min(len(a), len(cand)) >= 2 else 0.6)
            r = difflib.SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(cand))).ratio()
            melhor = max(melhor, r * 0.88)
    return melhor


def casar_tse(nomes: list[str], candidatos: list[dict], ue: str | None = None, partido: str | None = None) -> dict | None:
    """Acha o candidato do TSE que é esta pessoa. nomes = [nome parlamentar, nome civil, ...] da lista oficial.
    Só devolve quando a resposta é clara (sem empate); na dúvida, devolve None (melhor não ligar do que ligar errado)."""
    lista = [c for c in candidatos if not ue or c["ue"] == ue]
    notas = sorted(((_pontos(nomes, c), c) for c in lista), key=lambda x: -x[0])
    notas = [(p, c) for p, c in notas if p >= 0.85]
    if not notas:
        return None
    topo = notas[0][0]
    empatados = [c for p, c in notas if p >= topo - 0.02]
    if len({c["sq"] for c in empatados}) > 1:
        # desempata: mesmo partido, depois quem foi eleito ou ficou como suplente
        if partido:
            mp = [c for c in empatados if c["partido"].replace(" ", "").upper() == partido.replace(" ", "").upper()]
            if len({c["sq"] for c in mp}) == 1:
                return mp[0]
        el = [c for c in empatados if c["sit"].startswith("ELEITO") or c["sit"] == "SUPLENTE"]
        if len({c["sq"] for c in el}) == 1:
            return el[0]
        return None
    return notas[0][1]


def id_pessoa(prefixo: str, chave: str, cand: dict | None, nome: str) -> str:
    """dest-<UF>-<SQ> / ver-<IBGE>-<SQ>; sem o TSE, usa o nome (com 'x' na frente para nunca confundir com um SQ)."""
    return f"{prefixo}-{chave}-{cand['sq']}" if cand else f"{prefixo}-{chave}-x{slug(nome)}"


# ---------------------------------------------------------------- propostas
def tipo_comum(tipo_oficial: str, mapa: dict[str, str]) -> str | None:
    """Sigla oficial da Casa -> um dos TIPOS_REGIONAIS (ou None, que vira só contagem em "outros")."""
    t = (tipo_oficial or "").upper().strip()
    return mapa.get(t, t if t in TIPOS_REGIONAIS else None)


def situacao_para_status(texto: str | None, regras: list[tuple[str, str]] | None = None) -> str:
    """Regras próprias da Casa primeiro (expressão regular sem acento, em minúsculas -> status), depois a tabela comum."""
    t = sem_acento((texto or "").lower())
    for exp, st in regras or []:
        if re.search(exp, t):
            assert st in STATUS, st
            return st
    return classificar_situacao(texto)


def proposta(pid: str, sigla: str, tipo: str, data: str | None, ementa: str | None, situacao: str | None, url: str,
             papel: str = "autor", status: str | None = None, data_status: str | None = None, status_txt: str | None = None,
             regras: list | None = None, lei: dict | None = None, temas: list[str] | None = None) -> dict:
    """Uma proposta no mesmo formato dos perfis federais (README: "propostas.lista").
    pid: "<casa>:<id oficial>", por exemplo "alesp:1000473" ou "cmsp:PL-123-2025" (único no site todo)."""
    st = status or situacao_para_status(situacao, regras)
    return {
        "id": pid, "sigla": sigla, "tipo": tipo, "data": data, "ementa": (ementa or "").strip() or None,
        "status": st, "statusTxt": status_txt or STATUS_TXT[st], "situacao": situacao, "dataStatus": data_status,
        "papel": papel if papel in ("autor", "coautor") else "coautor", "temas": temas or [], "url": url, "lei": lei,
    }


def bloco_propostas(lista: list[dict], escopo: str, escopo_en: str, fonte_lista: dict, outros: dict | None = None) -> dict:
    lista = ordenar_propostas(lista)
    por_tipo: dict[str, int] = {}
    for p in lista:
        por_tipo[p["tipo"]] = por_tipo.get(p["tipo"], 0) + 1
    b = {"escopo": escopo, "escopo_en": escopo_en, "resumo": resumo_propostas(lista), "porTipo": por_tipo,
         "porTema": [], "fonte": fonte_lista, "lista": lista}
    if outros:
        b["outros"] = outros
    return b


# ---------------------------------------------------------------- gravar
def salvar_casa(tipo: str, chave: str, dados: dict) -> bool:
    """tipo "assembleia" -> dados/assembleias/<UF>.json; "camara" -> dados/camaras/<IBGE>.json."""
    pasta = ASSEMBLEIAS if tipo == "assembleia" else CAMARAS
    dados.setdefault("atualizado", hoje())
    caminho = pasta / f"{chave}.json"
    return salvar_json(caminho, sem_mudar_data(dados, caminho))


def salvar_extras(pid: str, dados: dict) -> bool:
    """dados/pessoas/<id>.json com o que a Casa publica a mais (propostas, votacoes, gastos, links, fontes)."""
    dados = dict(dados)
    dados["id"] = pid
    dados.setdefault("atualizado", hoje())
    caminho = PESSOAS / f"{pid}.json"
    return salvar_json(caminho, sem_mudar_data(dados, caminho))


def limpar_extras(prefixo: str, manter: set[str]) -> int:
    """Apaga arquivos de pessoas desta Casa que saíram da lista (ex.: prefixo "dest-SP-")."""
    n = 0
    for arq in PESSOAS.glob(f"{prefixo}*.json"):
        if arq.stem not in manter:
            arq.unlink()
            n += 1
    return n


__all__ = ["ASSEMBLEIAS", "CAMARAS", "INICIO_ESTADUAL", "INICIO_MUNICIPAL", "TIPOS_REGIONAIS", "palavras", "candidatos_tse",
           "casar_tse", "id_pessoa", "tipo_comum", "situacao_para_status", "proposta", "bloco_propostas", "salvar_casa",
           "salvar_extras", "limpar_extras", "fonte", "hoje", "log", "ler_json"]
