"""Resumo da fase 4 (leis e vetos das prefeituras pelos Diários Oficiais): tabela por estado e por plataforma, motivos de
quem ficou fora e tempos das rodadas. Sem rede.

  python scripts/municipios/diarios_resumo.py            tabelas em Markdown (para as notas)
  python scripts/municipios/diarios_resumo.py --conferir confere o formato de dados/prefeituras/*.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from comum import CACHE, DADOS, ler_json  # noqa: E402

PROIBIDAS = re.compile(r"(?i)ainda n[aã]o|em breve|por enquanto|not yet|coming soon")


def conferir() -> int:
    erros = []
    com_url = [0, 0]
    for arq in sorted((DADOS / "prefeituras").glob("*.json")):
        d = ler_json(arq) or {}
        for campo in ("uf", "atualizado", "fontes", "cidades", "fora"):
            if campo not in d:
                erros.append(f"{arq.name}: falta {campo}")
        for ibge, c in (d.get("cidades") or {}).items():
            ex = c.get("executivo") or {}
            p = ex.get("periodo") or {}
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.get("inicio") or "") or p.get("fim") is not None:
                erros.append(f"{arq.name} {ibge}: período")
            if not isinstance(ex.get("leisSancionadas"), int) or ex["leisSancionadas"] < 1:
                erros.append(f"{arq.name} {ibge}: leisSancionadas")
            if "vetos" in ex and (not isinstance(ex["vetos"], int) or ex["vetos"] < 1):
                erros.append(f"{arq.name} {ibge}: vetos")
            f = ex.get("fonte") or {}
            if not all(f.get(k) for k in ("veiculo", "titulo", "url", "data")) or not f["url"].startswith("http"):
                erros.append(f"{arq.name} {ibge}: fonte")
            for k in ("nota", "nota_en"):
                if not ex.get(k) or PROIBIDAS.search(ex[k]):
                    erros.append(f"{arq.name} {ibge}: {k}")
        for ibge, x in (d.get("fora") or {}).items():
            for k in ("motivo", "motivo_en"):
                if not x.get(k) or PROIBIDAS.search(x[k]):
                    erros.append(f"{arq.name} {ibge} (fora): {k}")
            # o link do quadro "Onde ver mais": tipo, rótulo nos dois idiomas e, quando há, o endereço da lista
            if x.get("tipo") not in ("diario", "legislacao"):
                erros.append(f"{arq.name} {ibge} (fora): tipo")
            for k in ("nome", "nome_en"):
                if not x.get(k) or PROIBIDAS.search(x[k]):
                    erros.append(f"{arq.name} {ibge} (fora): {k}")
            if "url" in x and not str(x["url"]).startswith("http"):
                erros.append(f"{arq.name} {ibge} (fora): url")
            com_url[0] += 1 if x.get("url") else 0
            com_url[1] += 1
            if ibge in (d.get("cidades") or {}):
                erros.append(f"{arq.name} {ibge}: nas duas listas")
    for e in erros[:50]:
        print("ERRO:", e)
    print(f"fora: {com_url[0]} de {com_url[1]} entradas com url")
    print(f"{len(erros)} problema(s)")
    return 1 if erros else 0


def main() -> int:
    if "--conferir" in sys.argv:
        return conferir()
    mapa_plat = collections.Counter()
    por_uf = {}
    plats = collections.Counter()
    motivos = collections.Counter()
    vetos = 0
    for arq in sorted((DADOS / "municipios").glob("*.json")):
        d = ler_json(arq) or {}
        uf = d.get("uf")
        if not uf:
            continue
        n = len(d.get("cidades") or {})
        p = ler_json(DADOS / "prefeituras" / f"{uf}.json") or {}
        ok = p.get("cidades") or {}
        fora = p.get("fora") or {}
        por_uf[uf] = (n, len(ok), len(fora))
        for x in ok.values():
            plats[(x["executivo"].get("conferencia") or {}).get("plataforma") or "?"] += 1
            vetos += "vetos" in x["executivo"]
        for x in fora.values():
            motivos[(x.get("plataforma"), x.get("codigo"))] += 1
            mapa_plat[x.get("plataforma")] += 1
    print("| UF | Cidades | Com a contagem | Fora (com o motivo) |")
    print("|---|---|---|---|")
    t = [0, 0, 0]
    for uf, (n, ok, fo) in sorted(por_uf.items()):
        print(f"| {uf} | {n} | {ok} | {fo} |")
        t = [t[0] + n, t[1] + ok, t[2] + fo]
    print(f"| **Total** | **{t[0]}** | **{t[1]}** | **{t[2]}** |")
    print()
    print("| Plataforma | Com a contagem | Fora |")
    print("|---|---|---|")
    for p in sorted(set(plats) | set(mapa_plat)):
        print(f"| {p} | {plats[p]} | {mapa_plat[p]} |")
    print(f"\nCom vetos: {vetos} cidades.\n")
    print("| Plataforma | Motivo | Cidades |")
    print("|---|---|---|")
    for (p, m), n in sorted(motivos.items()):
        print(f"| {p} | {m} | {n} |")
    rod = ler_json(CACHE / "municipios" / "diarios" / "atos" / "rodadas.json", []) or []
    if rod:
        print("\nRodadas:")
        for r in rod[-10:]:
            print(f"- {r['inicio']}: {r['segundos']} s, {r['pedidos']} pedidos, {r['cidades']} cidades com a contagem")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
