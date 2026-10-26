"""Roda os coletores das Assembleias Legislativas e das Câmaras Municipais.

Uso:
  python scripts/legislativos.py                 todas as Casas que têm coletor próprio (Assembleias e capitais)
  python scripts/legislativos.py assembleias     só as Assembleias
  python scripts/legislativos.py camaras         só as Câmaras Municipais com coletor próprio (as capitais)
  python scripts/legislativos.py SP 2927408      só estas (sigla do estado ou código IBGE da cidade, de qualquer grupo)
  python scripts/legislativos.py sapl            as outras Câmaras Municipais com SAPL (lista em scripts/camaras/sapl_cidades.json)
  python scripts/legislativos.py sapl --parte 3/7    só a 3ª de 7 partes (cada cidade cai sempre na mesma parte)
  python scripts/legislativos.py sapl --parte hoje   a parte do dia da semana (segunda = 1 ... domingo = 7): rodízio, cada
                                                     cidade atualizada uma vez por semana; depois dela, as cidades cuja
                                                     primeira carga ainda não terminou (--pendentes)
Opções: --paralelo N (N Casas ao mesmo tempo, cada uma no seu servidor e com uma requisição por vez; padrão 1),
--minutos M (depois de M minutos não começa Casa nova e as Câmaras com SAPL param no meio, guardando o que leram; as que
ficarem para trás mantêm os dados da última rodada) e --pendentes (junta as cidades com a primeira carga por terminar).
Cada Câmara com SAPL respeita o robots.txt do servidor (intervalo "Crawl-delay" entre pedidos: 60 s no SAPL do Interlegis)
e um orçamento de pedidos por rodada (SAPL_PEDIDOS no ambiente; padrão 60): ver scripts/camaras/_sapl.py.

Cada Casa com coletor próprio é um arquivo: scripts/assembleias/<uf>.py (ex.: sp.py) ou scripts/camaras/c<IBGE>.py (ex.:
c2927408.py), com a função coletar() -> dict (resumo: membros, propostas, cobertura). As Câmaras do grupo "sapl" não têm
arquivo: são uma linha de dados cada (scripts/camaras/_lista.py). Se uma Casa falhar (site fora do ar, formato mudou), as
outras continuam e o arquivo de antes fica como estava.
Também grava dados/legislativos.json: o que cada Casa já tem (lista oficial, propostas, votações, gastos), para a página
"De onde vêm os dados" mostrar a cobertura sem esconder o que falta.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import importlib
import os
import sys
import time
import traceback
from pathlib import Path

from comum import DADOS, hoje, ler_json, log, salvar_json, sem_mudar_data

AQUI = Path(__file__).resolve().parent
GRUPOS = {"assembleias": "assembleia", "camaras": "camara"}


def coletores(filtro: set[str], parte: tuple[int, int] | None = None, pendentes: bool = False) -> list[tuple[str, str, str, tuple]]:
    """[(grupo, chave, módulo, argumentos de coletar())] — chave = UF (assembleias) ou código IBGE (câmaras)."""
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
            out.append((grupo, chave, f"{grupo}.{arq.stem}", ()))
    # Câmaras com SAPL sem arquivo próprio: só quando pedidas ("sapl" ou o código IBGE de uma cidade sem coletor próprio)
    if filtro - set(GRUPOS) - {c[1] for c in out}:
        from camaras import _lista
        proprias = {c[1] for c in out} | {a.stem.lstrip("c") for a in (AQUI / "camaras").glob("c*.py")}
        do_dia, atrasadas = [], []
        falta = _lista.pendentes() if pendentes and "sapl" in filtro else set()
        for ibge in sorted(_lista.cidades(todas=bool(filtro - {"sapl"}))):
            if ibge in proprias or not ("sapl" in filtro or ibge in filtro):
                continue
            if pendentes and not parte:  # só as que ainda não terminaram a primeira carga
                if ibge in falta:
                    atrasadas.append(("camaras", ibge, "camaras._lista", (ibge,)))
            elif not parte or _lista.parte(ibge, parte[1]) == parte[0]:
                do_dia.append(("camaras", ibge, "camaras._lista", (ibge,)))
            elif ibge in falta:
                atrasadas.append(("camaras", ibge, "camaras._lista", (ibge,)))
        out += do_dia + atrasadas  # primeiro as do dia; depois as que ainda não terminaram a primeira carga
    return out


def _parte(texto: str | None) -> tuple[int, int] | None:
    if not texto:
        return None
    if texto == "hoje":
        return dt.date.today().isoweekday(), 7
    k, n = (int(x) for x in texto.split("/"))
    if not 1 <= k <= n:
        raise SystemExit(f"--parte {texto}: use k/n com 1 <= k <= n")
    return k, n


def rodar(item: tuple, prazo: float | None) -> tuple[str, str, dict | None]:
    grupo, chave, modulo, args = item
    if prazo and time.time() > prazo:
        return grupo, chave, None  # passou do limite de tempo: fica para a próxima rodada
    t0 = time.time()
    try:
        mod = importlib.import_module(modulo)
        r = mod.coletar(*args) or {}
        r["segundos"] = round(time.time() - t0)
        r["ok"] = True
        if r.get("pendente"):
            log(f"{grupo} {chave}: em andamento, parou em \"{r.get('etapa')}\" ({r.get('requisicoes')} pedidos, {r['segundos']} s)")
        else:
            log(f"{grupo} {chave}: {r.get('membros', '?')} pessoas, {r.get('propostas', 0)} propostas ({r['segundos']} s)")
    except Exception as e:  # uma Casa fora do ar não derruba as outras
        r = {"ok": False, "erro": f"{type(e).__name__}: {e}"[:300], "segundos": round(time.time() - t0)}
        log(f"{grupo} {chave}: FALHOU ({r['erro']})")
        traceback.print_exc(limit=3)
    return grupo, chave, r


def main(args: list[str]) -> int:
    sys.path.insert(0, str(AQUI))
    opcoes = {"--parte": None, "--paralelo": "1", "--minutos": None}
    resto = []
    pendentes = False
    i = 0
    while i < len(args):
        if args[i] in opcoes and i + 1 < len(args):
            opcoes[args[i]] = args[i + 1]
            i += 2
        else:
            if args[i] == "--pendentes":
                pendentes = True
            else:
                resto.append(args[i])
            i += 1
    filtro = {a if a in GRUPOS or a == "sapl" else a.upper() for a in resto}
    lista = coletores(filtro, _parte(opcoes["--parte"]), pendentes or opcoes["--parte"] == "hoje")
    if not lista:
        log("legislativos: nenhum coletor encontrado")
        return 0
    paralelo = max(1, int(opcoes["--paralelo"]))
    prazo = time.time() + 60 * float(opcoes["--minutos"]) if opcoes["--minutos"] else None
    if prazo:  # as Câmaras com SAPL param no meio quando o tempo acaba (scripts/camaras/_sapl.py)
        os.environ["LEGISLATIVOS_PRAZO"] = str(prazo)
    indice_arq = DADOS / "legislativos.json"
    indice = ler_json(indice_arq, {}) or {}
    indice.setdefault("assembleias", {})
    indice.setdefault("camaras", {})
    log(f"legislativos: {len(lista)} Casas ({paralelo} ao mesmo tempo)")
    feitos, falhas, adiadas, andamento = [], 0, 0, 0
    with cf.ThreadPoolExecutor(paralelo) as ex:
        for grupo, chave, r in ex.map(lambda it: rodar(it, prazo), lista):
            if r is None:
                adiadas += 1
                continue
            if not r.get("ok"):
                falhas += 1
                r = dict(indice[grupo].get(chave, {}), **r)
            elif r.get("pendente"):  # primeira carga em andamento: fica o resumo de antes, com a marca
                andamento += 1
                r = dict(indice[grupo].get(chave, {}), **r)
            else:
                r.pop("pendente", None)
                # a data da última leitura completa do site oficial: é a que o site mostra como "atualizado em" (uma
                # Casa que falha ou que ainda está na primeira carga fica com a data da última leitura que deu certo)
                r["conferido"] = hoje()
            indice[grupo][chave] = {k: v for k, v in r.items() if k != "segundos"}
            feitos.append((grupo, chave))
    # lê de novo antes de gravar: outra execução pode ter gravado enquanto esta rodava; só troca as Casas desta execução
    fresco = ler_json(indice_arq, {}) or {}
    for grupo, chave in feitos:
        fresco.setdefault(grupo, {})[chave] = indice[grupo][chave]
    fresco["atualizado"] = hoje()
    salvar_json(indice_arq, sem_mudar_data(fresco, indice_arq), indentado=True)
    log(f"legislativos: {len(feitos) - falhas - andamento} de {len(lista)} Casas atualizadas"
        + (f"; {andamento} com a primeira carga em andamento" if andamento else "")
        + (f"; {falhas} falharam" if falhas else "")
        + (f"; {adiadas} ficaram para a próxima rodada (limite de tempo)" if adiadas else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
