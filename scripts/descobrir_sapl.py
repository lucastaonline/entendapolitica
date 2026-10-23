"""Descobre quais Câmaras Municipais têm o SAPL do Interlegis com a API pública funcionando (não roda sozinho todo dia).

Para cada uma das 5.569 cidades de dados/cidades.json, testa o endereço padrão do Interlegis, https://sapl.<cidade>.<uf>.leg.br
(nome da cidade sem acentos, espaços, hífens e apóstrofos: "Santa Bárbara d'Oeste" -> sapl.santabarbaradoeste.sp.leg.br):
1. o nome existe (DNS)? 2. /api/parlamentares/legislatura/ responde em JSON? 3. a legislatura atual (2025–2028) está
cadastrada? 4. quantos projetos (PL, PLC, PELO, PDL, PR...) foram cadastrados desde 1º/1/2025 e quantos vereadores estão ativos?

Educado: no máximo 8 cidades ao mesmo tempo (cada uma num servidor diferente), 1 a 4 requisições por cidade, pausa entre
elas, e resultado guardado em .cache/camaras/descoberta/<IBGE>.json (só testa de novo depois de --dias, padrão 30).

Uso:
  python scripts/descobrir_sapl.py                 todas as cidades (a primeira vez leva ~10–20 min, quase tudo é DNS)
  python scripts/descobrir_sapl.py --uf RN PB      só estes estados
  python scripts/descobrir_sapl.py --dias 0        ignora o cache
Grava o resumo em .cache/camaras/descoberta.json (não vai para o site).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import CACHE, DADOS, UA, hoje, ler_json, log, salvar_json, sem_acento  # noqa: E402

PASTA = CACHE / "camaras" / "descoberta"
PROPOSTAS = re.compile(r"projeto de (lei|decreto legislativo|resolucao|emenda)|proposta de emenda|emenda a lei organica")


def host(nome: str, uf: str) -> str:
    s = sem_acento(nome).lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return f"sapl.{s}.{uf.lower()}.leg.br"


def _json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tipo = r.headers.get("Content-Type") or ""
        corpo = r.read(2_000_000)
    if "json" not in tipo:
        raise ValueError(f"não é JSON ({tipo[:40]})")
    return json.loads(corpo.decode("utf-8"))


def testar(ibge: str, nome: str, uf: str) -> dict:
    h = host(nome, uf)
    r = {"ibge": ibge, "nome": nome, "uf": uf, "host": h, "data": hoje(), "dns": False, "api": False,
         "legislaturaAtual": False, "vereadoresAtivos": None, "projetos2025": None, "segundos": None, "erro": None}
    t0 = time.time()
    try:
        socket.getaddrinfo(h, 443)
        r["dns"] = True
    except OSError:
        return r
    base = f"https://{h}"
    try:
        legs = _json(f"{base}/api/parlamentares/legislatura/?page_size=100")
        r["api"] = isinstance(legs, dict) and "results" in legs
        d = hoje()
        atual = [l for l in legs.get("results") or [] if (l.get("data_inicio") or "") <= d <= (l.get("data_fim") or "")]
        r["legislaturaAtual"] = bool(atual)
        time.sleep(0.5)
        if atual:
            vinc = _json(f"{base}/api/parlamentares/legislatura/{atual[0]['id']}/parlamentares/?page_size=100")
            r["vereadoresAtivos"] = sum(1 for v in vinc.get("results") or [] if v.get("ativo"))
            time.sleep(0.5)
        tipos = _json(f"{base}/api/materia/tipomaterialegislativa/?page_size=100")
        ids = [t["id"] for t in tipos.get("results") or [] if PROPOSTAS.search(sem_acento((t.get("descricao") or "").lower()))]
        if ids:
            time.sleep(0.5)
            m = _json(f"{base}/api/materia/materialegislativa/?page_size=1&data_apresentacao__gte=2025-01-01&tipo__in={','.join(map(str, ids))}")
            r["projetos2025"] = (m.get("pagination") or {}).get("total_entries")
        else:
            r["projetos2025"] = 0
    except ssl.SSLError as e:
        r["erro"] = f"SSL: {str(e)[:80]}"
    except urllib.error.HTTPError as e:
        r["erro"] = f"HTTP {e.code}"
    except Exception as e:
        r["erro"] = f"{type(e).__name__}: {str(e)[:80]}"
    r["segundos"] = round(time.time() - t0, 1)
    return r


def estimativa(r: dict) -> float:
    """Segundos por dia, com cache, para a Câmara (medido nas capitais: ~30 requisições fixas + 1 página por 100 projetos,
    ~1 s cada com a pausa)."""
    n = r.get("projetos2025") or 0
    return 30 + n / 100 + 5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="*")
    ap.add_argument("--dias", type=float, default=30)
    ap.add_argument("--max", type=int, default=0, help="testa só as primeiras N cidades (para experimentar)")
    a = ap.parse_args()
    cidades = ler_json(DADOS / "cidades.json", []) or []
    if a.uf:
        ufs = {u.upper() for u in a.uf}
        cidades = [c for c in cidades if c[2] in ufs]
    if a.max:
        cidades = cidades[:a.max]
    PASTA.mkdir(parents=True, exist_ok=True)
    feitos, fila = [], []
    for ibge, nome, uf in cidades:
        arq = PASTA / f"{ibge}.json"
        if arq.exists() and (time.time() - arq.stat().st_mtime) / 86400 < a.dias:
            feitos.append(ler_json(arq))
        else:
            fila.append((ibge, nome, uf))
    log(f"descoberta SAPL: {len(cidades)} cidades, {len(fila)} para testar agora ({len(feitos)} no cache)")
    t0 = time.time()
    with cf.ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(lambda c: testar(*c), fila), 1):
            salvar_json(PASTA / f"{r['ibge']}.json", r)
            feitos.append(r)
            if i % 250 == 0:
                log(f"  {i}/{len(fila)} ({time.time() - t0:.0f} s)")
    ok = [r for r in feitos if r.get("api")]
    atuais = [r for r in ok if r.get("legislaturaAtual")]
    com_proj = [r for r in atuais if (r.get("projetos2025") or 0) > 0]
    resumo = {
        "data": hoje(), "cidades": len(feitos), "dns": sum(1 for r in feitos if r.get("dns")), "api": len(ok),
        "legislaturaAtual": len(atuais), "comProjetos2025": len(com_proj),
        "segundosPorDia": round(sum(estimativa(r) for r in com_proj)),
        "porUF": {}, "lista": sorted(({k: r[k] for k in ("ibge", "nome", "uf", "host", "vereadoresAtivos", "projetos2025")}
                                      for r in com_proj), key=lambda x: (x["uf"], x["nome"])),
        "erros": sorted({r["erro"].split(":")[0] for r in feitos if r.get("erro")}),
    }
    for r in com_proj:
        resumo["porUF"][r["uf"]] = resumo["porUF"].get(r["uf"], 0) + 1
    salvar_json(CACHE / "camaras" / "descoberta.json", resumo, indentado=True)
    log(f"descoberta SAPL: {resumo['dns']} com DNS, {resumo['api']} com API, {resumo['legislaturaAtual']} com a legislatura atual, "
        f"{resumo['comProjetos2025']} com projetos desde 2025; estimativa diária com cache: "
        f"{resumo['segundosPorDia'] / 60:.0f} min ({time.time() - t0:.0f} s agora)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
