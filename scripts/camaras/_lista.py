"""Câmaras Municipais com SAPL (Interlegis) que não têm arquivo próprio: todas as que dá para ler, menos as capitais.

A lista fica em scripts/camaras/sapl_cidades.json (uma linha por cidade), feita por "python scripts/descobrir_sapl.py --lista"
a partir da descoberta (endereço padrão sapl.<cidade>.<uf>.leg.br) e do mapa das cidades (dados/municipios/<UF>.json, quando
a Câmara usa o SAPL em outro endereço). Cada cidade é só dados: nada de um arquivo .py por cidade.

Campos de cada cidade: nome, uf, base (endereço do SAPL) e, quando alguém conferiu à mão, os ajustes do coletor genérico
(scripts/camaras/_sapl.py): casa, casa_en, sigla, site, prefixo, pausa, tipos, regras, tse_manual, incluir, excluir,
vagas ([mínimo, máximo] aceitos na conferência), notas ([[português, inglês], ...]), conferido (data e o que foi visto) e
ativo (false = fica fora, com o motivo em "obs").

Rodar: "python scripts/legislativos.py sapl" (todas) ou "... sapl --parte hoje" (rodízio: cada cidade num dia da semana).
"""
from __future__ import annotations

import json
from pathlib import Path

from comum import hoje, ler_json, salvar_json

from . import _base as B
from ._sapl import Sapl

ARQ = Path(__file__).resolve().parent / "sapl_cidades.json"
FALHAS_MAX = 3  # dias seguidos com falha: a cidade sai da fila das pendentes (volta no dia dela do rodízio)


def cidades(todas: bool = False) -> dict[str, dict]:
    d = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    return {k: v for k, v in (d.get("cidades") or {}).items() if todas or v.get("ativo", True)}


def pendentes() -> set[str]:
    """Cidades cuja primeira carga ainda não terminou (ou que nunca rodaram): com o intervalo de 60 s do robots.txt do SAPL,
    a carga de uma cidade grande leva várias rodadas; "legislativos.py sapl --parte hoje" põe estas na fila todo dia, depois
    das cidades do dia. O estado de cada uma fica em .cache/camaras/<IBGE>/estado.json (ou na pasta de CAMARAS_CACHE).
    Uma cidade que falhou em FALHAS_MAX dias seguidos (servidor fora do ar, robots.txt sem resposta) sai desta fila e volta
    a ser tentada só no dia dela do rodízio; quando der certo, volta para a fila."""
    out = set()
    for ibge in cidades():
        e = ler_json(B.PASTA_CACHE / ibge / "estado.json", {}) or {}
        if e.get("completo") is not True and len(e.get("falhas") or []) < FALHAS_MAX:
            out.add(ibge)
    return out


def parte(ibge: str, n: int = 7) -> int:
    """Dia do rodízio (1..n) desta cidade. Fixo (pelo código IBGE), para cada cidade ser atualizada sempre no mesmo dia da
    semana, mesmo quando outras cidades entram na lista."""
    return int(ibge) % n + 1


def coletar(ibge: str) -> dict:
    c = cidades(todas=True).get(ibge)
    if not c:
        raise RuntimeError(f"{ibge} não está em {ARQ.name}")
    excluir = {int(k): v for k, v in (c.get("excluir") or {}).items()}
    try:
        r = Sapl(ibge, c["uf"], c["base"], casa=c.get("casa"), casa_en=c.get("casa_en"), sigla=c.get("sigla"),
                 site=c.get("site"), prefixo=c.get("prefixo"), tipos=c.get("tipos"), regras=c.get("regras"),
                 tse_manual=c.get("tse_manual"), incluir={int(i) for i in c.get("incluir") or []}, excluir=excluir,
                 pausa=float(c.get("pausa") or 0.5), notas=c.get("notas"), sem_lista_se_falhar=True,
                 vagas=c.get("vagas"), fotos_locais=False).coletar()
    except Exception as erro:  # anota o dia da falha (uma por dia) e deixa o legislativos.py tratar o erro
        _anotar_falha(ibge, f"{type(erro).__name__}: {erro}")
        raise
    _anotar_falha(ibge, None)
    return r


def _anotar_falha(ibge: str, erro: str | None) -> None:
    arq = B.PASTA_CACHE / ibge / "estado.json"
    e = ler_json(arq, {}) or {}
    if erro is None:
        if e.pop("falhas", None) is not None:
            salvar_json(arq, e)
        return
    dia = hoje()
    e["falhas"] = ([f for f in e.get("falhas") or [] if f[0] != dia] + [[dia, erro[:200]]])[-FALHAS_MAX:]
    salvar_json(arq, e)


__all__ = ["ARQ", "FALHAS_MAX", "cidades", "pendentes", "parte", "coletar"]
