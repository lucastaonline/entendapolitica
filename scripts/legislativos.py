"""Roda os coletores das Assembleias Legislativas e das Câmaras Municipais.

Uso:
  python scripts/legislativos.py                 todas as Casas que já têm coletor
  python scripts/legislativos.py assembleias     só as Assembleias
  python scripts/legislativos.py camaras         só as Câmaras Municipais
  python scripts/legislativos.py SP 2927408      só estas (sigla do estado ou código IBGE da cidade)

Cada Casa é um arquivo: scripts/assembleias/<uf>.py (ex.: sp.py) ou scripts/camaras/c<IBGE>.py (ex.: c2927408.py),
com a função coletar() -> dict (resumo: membros, propostas, cobertura). Se uma Casa falhar (site fora do ar, formato
mudou), as outras continuam e o arquivo de antes fica como estava.
Também grava dados/legislativos.json: o que cada Casa já tem (lista oficial, propostas, votações, gastos), para a página
"De onde vêm os dados" mostrar a cobertura sem esconder o que falta.
"""
from __future__ import annotations

import importlib
import sys
import time
import traceback
from pathlib import Path

from comum import DADOS, hoje, ler_json, log, salvar_json, sem_mudar_data

AQUI = Path(__file__).resolve().parent
GRUPOS = {"assembleias": "assembleia", "camaras": "camara"}


def coletores(filtro: set[str]) -> list[tuple[str, str, str]]:
    """[(grupo, chave, módulo)] — chave = UF (assembleias) ou código IBGE (câmaras)."""
    out = []
    for grupo in GRUPOS:
        pasta = AQUI / grupo
        if not pasta.exists():
            continue
        for arq in sorted(pasta.glob("*.py")):
            if arq.stem.startswith("_"):
                continue
            chave = arq.stem.upper() if grupo == "assembleias" else arq.stem.lstrip("c")
            if filtro and not ({grupo, chave} & filtro):
                continue
            out.append((grupo, chave, f"{grupo}.{arq.stem}"))
    return out


def main(args: list[str]) -> int:
    sys.path.insert(0, str(AQUI))
    filtro = {a if a in GRUPOS else a.upper() for a in args}
    lista = coletores(filtro)
    if not lista:
        log("legislativos: nenhum coletor encontrado")
        return 0
    indice_arq = DADOS / "legislativos.json"
    indice = ler_json(indice_arq, {}) or {}
    indice.setdefault("assembleias", {})
    indice.setdefault("camaras", {})
    falhas = 0
    for grupo, chave, modulo in lista:
        t0 = time.time()
        try:
            mod = importlib.import_module(modulo)
            r = mod.coletar() or {}
            r["segundos"] = round(time.time() - t0)
            r["ok"] = True
            log(f"{grupo} {chave}: {r.get('membros', '?')} pessoas, {r.get('propostas', 0)} propostas ({r['segundos']} s)")
        except Exception as e:  # uma Casa fora do ar não derruba as outras
            falhas += 1
            r = dict(indice[grupo].get(chave, {}))
            r.update({"ok": False, "erro": f"{type(e).__name__}: {e}"[:300], "segundos": round(time.time() - t0)})
            log(f"{grupo} {chave}: FALHOU ({r['erro']})")
            traceback.print_exc(limit=3)
        indice[grupo][chave] = {k: v for k, v in r.items() if k != "segundos"}
    # lê de novo antes de gravar: outra execução pode ter gravado enquanto esta rodava; só troca as Casas desta execução
    fresco = ler_json(indice_arq, {}) or {}
    for grupo, chave, _ in lista:
        fresco.setdefault(grupo, {})[chave] = indice[grupo][chave]
    fresco["atualizado"] = hoje()
    salvar_json(indice_arq, sem_mudar_data(fresco, indice_arq), indentado=True)
    log(f"legislativos: {len(lista) - falhas} de {len(lista)} Casas atualizadas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
