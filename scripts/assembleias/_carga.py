"""Tempo de cada rodada e primeira carga dos coletores das Assembleias (vale para os três grupos: _ne_*, _sse_*, _nco_*).

O robô diário (GitHub Actions) roda `python scripts/legislativos.py assembleias --paralelo N --minutos M` e começa com o
cache vazio (a pasta .cache/ não vai para o repositório). Por isso:
- nenhum pedido novo a um site oficial começa depois do fim da rodada (LEGISLATIVOS_PRAZO, que o legislativos.py põe no
  ambiente quando recebe --minutos), menos uma folga para gravar os arquivos (MARGEM_S);
- enquanto a primeira carga de uma Casa não termina, o coletor guarda o que já leu em .cache/<casa>/ e devolve
  pendente(...): os arquivos publicados de antes (dados/assembleias/<UF>.json e os perfis) continuam como estavam, o
  legislativos.py mostra "em andamento" e a carga continua na rodada seguinte, de onde parou (nada pela metade no site);
- na primeira carga, a Casa pode usar o tempo todo da rodada (cada Casa fala com um servidor diferente); nas rodadas
  seguintes, cada coletor usa o seu limite diário, bem menor.
Sem --minutos (rodando um estado à mão), a primeira carga usa `padrao` segundos por rodada; NE_SEM_LIMITE=1 tira o
limite (para encher o cache de uma vez).
"""
from __future__ import annotations

import os
import time

MARGEM_S = 120  # folga antes do fim da rodada: depois disso, nenhum pedido novo (dá tempo de gravar os arquivos)


class SemTempo(RuntimeError):
    """O tempo desta rodada acabou: o que faltou fica para a próxima (o cache guarda o que já foi lido)."""


def fim_rodada() -> float | None:
    """Até quando (time.time()) esta rodada pode fazer pedidos; None quando não há limite (sem --minutos)."""
    p = os.environ.get("LEGISLATIVOS_PRAZO")
    if not p:
        return None
    try:
        return float(p) - MARGEM_S
    except ValueError:
        return None


def sem_limite() -> bool:
    return os.environ.get("NE_SEM_LIMITE") == "1"


def acabou() -> bool:
    """O fim da rodada já passou?"""
    f = fim_rodada()
    return f is not None and time.time() >= f


def conferir(pedidos: int = 1, intervalo: float = 0.0) -> None:
    """Antes de um pedido: se ele (e os `pedidos` - 1 seguintes, com `intervalo` entre eles) não cabem mais na rodada,
    SemTempo."""
    f = fim_rodada()
    if f is not None and time.time() + max(0, pedidos - 1) * intervalo >= f:
        raise SemTempo("acabou o tempo desta rodada (legislativos.py --minutos); o resto fica para a próxima")


def segundos(padrao: float) -> float:
    """Quantos segundos a primeira carga pode usar a partir de agora: até o fim da rodada (com --minutos), `padrao`
    rodando sozinho, sem limite com NE_SEM_LIMITE=1."""
    if sem_limite():
        return float("inf")
    f = fim_rodada()
    return max(0.0, f - time.time()) if f is not None else float(padrao)


def limite_diario(normal: float, primeira: bool, padrao_carga: float = 30 * 60) -> float:
    """O limite de tempo (segundos) de um laço de leitura: o diário (`normal`) ou, na primeira carga, o resto da rodada.
    Nunca passa do fim da rodada."""
    if sem_limite():
        return float("inf")
    base = segundos(padrao_carga) if primeira else float(normal)
    f = fim_rodada()
    return min(base, max(0.0, f - time.time())) if f is not None else base


def pendente(sigla: str, etapa: str, pedidos: int | None = None, **extra) -> dict:
    """Resumo de uma Casa com a primeira carga em andamento (o legislativos.py guarda o resumo de antes, com esta marca)."""
    r = {"casa": sigla, "pendente": True, "etapa": etapa, "requisicoes": pedidos}
    r.update(extra)
    return r


__all__ = ["MARGEM_S", "SemTempo", "fim_rodada", "sem_limite", "acabou", "conferir", "segundos", "limite_diario", "pendente"]
