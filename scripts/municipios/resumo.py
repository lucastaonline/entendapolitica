"""Resumo do mapa das cidades (para as notas e o README): tabela por estado, plataformas de Diário Oficial e sistemas
de proposições das Câmaras. Lê só dados/municipios/*.json e o cache de .cache/municipios/ (sem rede).

Uso: python scripts/municipios/resumo.py [--md arquivo.md]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
from comum import CACHE, DADOS, ler_json  # noqa: E402

PASTA = CACHE / "municipios"
PROIBIDAS = re.compile(r"ainda n[aã]o|em breve|por enquanto|not yet|coming soon", re.I)
OFICIAL = re.compile(r"\.(leg|gov|jus)\.br$")
SISTEMAS = {"sapl", "sagl", "nopaper", "outro", None}


def conferir() -> list[str]:
    """Regras do formato (seção 3 do contrato) e da rodada (textos sem promessa, só domínios oficiais no site)."""
    erros = []
    for f in sorted((DADOS / "municipios").glob("*.json")):
        d = ler_json(f) or {}
        for k in ("uf", "atualizado", "fontes", "cidades"):
            if k not in d:
                erros.append(f"{f.name}: falta {k}")
        for fo in d.get("fontes") or []:
            if not all(fo.get(k) for k in ("veiculo", "titulo", "url", "data")):
                erros.append(f"{f.name}: fonte incompleta {fo}")
        for ibge, c in (d.get("cidades") or {}).items():
            ca, pr = c.get("camara") or {}, c.get("prefeitura") or {}
            for k in ("site", "sistema", "api", "propostas", "propostasOnline", "sic", "conferido", "motivo", "motivo_en"):
                if k not in ca:
                    erros.append(f"{ibge}: camara sem {k}")
            for k in ("site", "transparencia", "sic", "diarioOficial"):
                if k not in pr:
                    erros.append(f"{ibge}: prefeitura sem {k}")
            if ca.get("sistema") not in SISTEMAS:
                erros.append(f"{ibge}: sistema {ca.get('sistema')}")
            if ca.get("site") and not OFICIAL.search(host(ca["site"])):
                erros.append(f"{ibge}: site da Câmara fora de domínio oficial {ca['site']}")
            if pr.get("site") and not OFICIAL.search(host(pr["site"])):
                erros.append(f"{ibge}: site da prefeitura fora de domínio oficial {pr['site']}")
            if ca.get("propostasOnline") and not ca.get("propostas"):
                erros.append(f"{ibge}: propostasOnline sem link de propostas")
            if ca.get("propostasOnline") and ca.get("motivo"):
                erros.append(f"{ibge}: propostasOnline com motivo")
            if not ca.get("propostasOnline") and not ca.get("motivo"):
                erros.append(f"{ibge}: sem proposições e sem motivo")
            if bool(ca.get("motivo")) != bool(ca.get("motivo_en")):
                erros.append(f"{ibge}: motivo sem inglês")
            for k in ("motivo", "motivo_en"):
                if ca.get(k) and PROIBIDAS.search(ca[k]):
                    erros.append(f"{ibge}: texto com promessa: {ca[k]}")
            if ca.get("sistema") == "sapl" and ca.get("api") and not ca["api"].endswith("/api/"):
                erros.append(f"{ibge}: api do SAPL estranha {ca['api']}")
            do = pr.get("diarioOficial")
            if do and not all(do.get(k) for k in ("nome", "url", "plataforma")):
                erros.append(f"{ibge}: diarioOficial incompleto {do}")
    for k in ("nota", "nota_en"):
        for f in (DADOS / "municipios").glob("*.json"):
            v = (ler_json(f) or {}).get(k)
            if v and PROIBIDAS.search(v):
                erros.append(f"{f.name}: {k} com promessa")
    return erros


def host(u: str | None) -> str:
    return re.sub(r"^https?://", "", u or "").split("/")[0].lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--conferir", action="store_true", help="só confere o formato dos arquivos")
    a = ap.parse_args()
    if a.conferir:
        erros = conferir()
        for e in erros[:200]:
            print(e)
        tam = sum(f.stat().st_size for f in (DADOS / "municipios").glob("*.json"))
        print(f"{len(erros)} problema(s); {len(list((DADOS / 'municipios').glob('*.json')))} arquivos, {tam / 1024:.0f} KB")
        return 1 if erros else 0
    linhas: list[str] = []
    p = linhas.append
    ufs = sorted(f.stem for f in (DADOS / "municipios").glob("*.json"))
    tot = collections.Counter()
    p("| UF | Cidades | Câmara com site | Proposições na internet (SAPL / outro sistema) | SAPL sem 2025 | "
      "Prefeitura com site | Diário Oficial ligado (não confirmado) | Transparência | e-SIC prefeitura | e-SIC Câmara |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    plataformas = collections.Counter()
    exemplos: dict[str, list] = collections.defaultdict(list)
    assoc = collections.Counter()
    sistemas = collections.Counter()
    fornec = collections.Counter()
    motivos = collections.Counter()
    for uf in ufs:
        d = ler_json(DADOS / "municipios" / f"{uf}.json") or {}
        cs = d.get("cidades") or {}
        n = len(cs)
        if not n:
            continue
        c_site = sum(1 for x in cs.values() if x["camara"]["site"])
        on = [x for x in cs.values() if x["camara"]["propostasOnline"]]
        on_sapl = sum(1 for x in on if x["camara"]["sistema"] == "sapl")
        sapl_sem = sum(1 for x in cs.values() if x["camara"]["sistema"] == "sapl" and not x["camara"]["propostasOnline"])
        p_site = sum(1 for x in cs.values() if x["prefeitura"]["site"])
        do = [x["prefeitura"]["diarioOficial"] for x in cs.values() if x["prefeitura"]["diarioOficial"]]
        do_nc = sum(1 for x in do if x.get("confirmado") is False)
        tr = sum(1 for x in cs.values() if x["prefeitura"]["transparencia"])
        sic_p = sum(1 for x in cs.values() if x["prefeitura"]["sic"])
        sic_c = sum(1 for x in cs.values() if x["camara"]["sic"])
        p(f"| {uf} | {n} | {c_site} | {len(on)} ({on_sapl} / {len(on) - on_sapl}) | {sapl_sem} | {p_site} | "
          f"{len(do)}{f' ({do_nc})' if do_nc else ''} | {tr} | {sic_p} | {sic_c} |")
        tot.update({"n": n, "c_site": c_site, "on": len(on), "on_sapl": on_sapl, "sapl_sem": sapl_sem, "p_site": p_site,
                    "do": len(do), "do_nc": do_nc, "tr": tr, "sic_p": sic_p, "sic_c": sic_c})
        for ibge, x in cs.items():
            ca = x["camara"]
            sistemas[(ca["sistema"] or "—", bool(ca["propostasOnline"]))] += 1
            if ca["sistema"] == "outro":
                fornec[ca.get("plataforma") or "não identificado"] += 1
            motivos[ca["motivo"] or ("(proposições na internet)" if ca["propostasOnline"] else "—")] += 1
            dd = x["prefeitura"]["diarioOficial"]
            if dd:
                plataformas[dd["plataforma"]] += 1
                if len(exemplos[dd["plataforma"]]) < 3 and dd["url"] not in exemplos[dd["plataforma"]]:
                    exemplos[dd["plataforma"]].append(dd["url"])
                if "diariomunicipal.com.br/" in dd["url"] or dd["plataforma"].startswith("Diário Oficial MS"):
                    assoc[(uf, dd["nome"])] += 1
    t = tot
    nc = f" ({t['do_nc']})" if t["do_nc"] else ""
    p(f"| **Total** | **{t['n']}** | **{t['c_site']}** | **{t['on']} ({t['on_sapl']} / {t['on'] - t['on_sapl']})** | "
      f"**{t['sapl_sem']}** | **{t['p_site']}** | **{t['do']}{nc}** | **{t['tr']}** | **{t['sic_p']}** | **{t['sic_c']}** |")
    p("")
    p("### Diário Oficial das prefeituras, por plataforma")
    p("")
    p("| Plataforma | Cidades | Exemplos |")
    p("|---|---|---|")
    for k, v in plataformas.most_common():
        p(f"| {k} | {v} | {' · '.join(exemplos[k])} |")
    p("")
    p("### Associações de municípios (Diário Oficial único), cidades ligadas (publicaram nos últimos 6 meses)")
    p("")
    # atividade conferida no Diário de cada associação (cache): quantas cidades publicaram e quantas têm "lei" no título
    ativ = collections.defaultdict(lambda: collections.Counter())
    for f in (PASTA / "diarios").glob("*/*.json"):
        x = ler_json(f) or {}
        a_ = x.get("assoc")
        ativ[a_]["listadas"] += 1
        if (x.get("materias6m") or 0) > 0:
            ativ[a_]["ativas"] += 1
            if (x.get("leis2025") or 0) > 0:
                ativ[a_]["comLeis"] += 1
                ativ[a_]["leis"] += x["leis2025"]
    p("| Associação (endereço) | Na lista de entidades | Publicaram nos últimos 6 meses | Com matérias \"lei\" desde 1º/1/2025 (total) |")
    p("|---|---|---|---|")
    for a_, c in sorted(ativ.items(), key=lambda kv: -kv[1]["listadas"]):
        p(f"| {a_} | {c['listadas']} | {c['ativas']} | {c['comLeis']} ({c['leis']}) |")
    p("")
    p("| UF | Diário | Cidades ligadas no mapa |")
    p("|---|---|---|")
    for (uf, nome), v in sorted(assoc.items()):
        p(f"| {uf} | {nome} | {v} |")
    p("")
    p("### Câmaras: sistema de proposições")
    p("")
    p("| Sistema | Proposições na internet | Cidades |")
    p("|---|---|---|")
    for (s, on), v in sorted(sistemas.items(), key=lambda kv: (-kv[1])):
        p(f"| {s} | {'sim' if on else 'não/não conferido'} | {v} |")
    p("")
    p("Fornecedores (sistema \"outro\"): " + ", ".join(f"{k} {v}" for k, v in fornec.most_common()))
    p("")
    p("### Câmaras: por que as proposições não aparecem")
    p("")
    p("| Motivo | Cidades |")
    p("|---|---|")
    for k, v in motivos.most_common():
        p(f"| {k} | {v} |")
    p("")
    # robots.txt fechados: agrupa pelo conteúdo (mesmo fornecedor)
    marcas = collections.Counter()
    ex_marca = {}
    diario_fora = collections.Counter()
    for f in (PASTA / "cidades").glob("*/*.json"):
        b = ler_json(f) or {}
        for v in (b.get("camara") or {}).get("visitas") or []:
            if v.get("robotsMarca") and v.get("robots") == "regras":
                marcas[v["robotsMarca"]] += 1
                ex_marca.setdefault(v["robotsMarca"], v["host"])
        pref = b.get("prefeitura") or {}
        link = pref.get("diarioLink")
        if link and not re.search(r"\.(gov|leg|jus)\.br$", host(link)):
            diario_fora[host(link)] += 1
    p("### Sites de Câmaras que pedem no robots.txt para não serem lidos (agrupados pelo conteúdo do robots.txt)")
    p("")
    p("| Caminhos fechados | Câmaras | Exemplo |")
    p("|---|---|---|")
    for k, v in marcas.most_common(12):
        p(f"| `{k[:90]}` | {v} | {ex_marca[k]} |")
    p("")
    p("### Diários Oficiais em domínios que não são .gov.br (link no site da prefeitura), por endereço")
    p("")
    p(", ".join(f"{k} ({v})" for k, v in diario_fora.most_common(40)))
    p("")
    rod = ler_json(PASTA / "rodadas.json", {}) or {}
    p("### Tempo das rodadas (por estado)")
    p("")
    p("| UF | Data | Cidades conferidas | Segundos | Pedidos |")
    p("|---|---|---|---|---|")
    for uf in sorted(rod):
        for r in rod[uf][-2:]:
            p(f"| {uf} | {r['data']} | {r['cidades']} | {r['segundos']} | {r.get('pedidos')} |")
    texto = "\n".join(linhas)
    if a.md:
        Path(a.md).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
