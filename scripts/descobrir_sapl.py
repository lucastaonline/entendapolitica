"""Descobre quais Câmaras Municipais têm o SAPL do Interlegis com a API pública funcionando (não roda sozinho todo dia).

Para cada uma das 5.569 cidades de dados/cidades.json, testa o endereço padrão do Interlegis, https://sapl.<cidade>.<uf>.leg.br
(nome da cidade sem acentos, espaços, hífens e apóstrofos: "Santa Bárbara d'Oeste" -> sapl.santabarbaradoeste.sp.leg.br),
e também os endereços diferentes que o mapa das cidades (dados/municipios/<UF>.json, campo camara.api com sistema "sapl")
encontrou: 1. o nome existe (DNS)? 2. /api/parlamentares/legislatura/ responde em JSON? 3. a legislatura atual (2025–2028)
está cadastrada? 4. quantos projetos (PL, PLC, PELO, PDL, PR...) foram cadastrados desde 1º/1/2025 e quantos vereadores
estão ativos?

Educado: o robots.txt de cada servidor é respeitado (Disallow e o intervalo "Crawl-delay": 60 s entre pedidos no SAPL do
Interlegis; robots.txt com erro 5xx ou sem resposta = a cidade não é testada nessa rodada), 2 a 5 pedidos por cidade, cidades
diferentes ao mesmo tempo (--paralelo, padrão 32: cada uma num servidor) e resultado guardado em
.cache/camaras/descoberta/<IBGE>.json (só testa de novo depois de --dias, padrão 30). Com o intervalo de 60 s, a descoberta
inteira leva ~3 h (quase todas as cidades param no DNS, sem nenhum pedido).

Uso:
  python scripts/descobrir_sapl.py                 todas as cidades (a primeira vez leva ~10–20 min, quase tudo é DNS)
  python scripts/descobrir_sapl.py --uf RN PB      só estes estados
  python scripts/descobrir_sapl.py --dias 0        ignora o cache
  python scripts/descobrir_sapl.py --lista         também atualiza scripts/camaras/sapl_cidades.json (a lista que o
                                                   "legislativos.py sapl" roda), sem apagar os ajustes feitos à mão
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
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import DADOS, UA, hoje, ler_json, log, salvar_json, sem_acento  # noqa: E402
from camaras import _base as B  # noqa: E402  (robots.txt e intervalo entre pedidos)

PASTA = B.PASTA_CACHE / "descoberta"
PASTA_OUTROS = B.PASTA_CACHE / "descoberta-outros"  # endereços que vieram do mapa das cidades
LISTA = Path(__file__).resolve().parent / "camaras" / "sapl_cidades.json"
PROPOSTAS = re.compile(r"projeto de (lei|decreto legislativo|resolucao|emenda)|proposta de emenda|emenda a lei organica")


def host(nome: str, uf: str) -> str:
    s = sem_acento(nome).lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return f"sapl.{s}.{uf.lower()}.leg.br"


def _json(url: str, timeout: int = 20):
    """Um pedido educado: confere o robots.txt do servidor (Disallow) e espera o intervalo dele (Crawl-delay: 60 s no SAPL
    do Interlegis) desde o pedido anterior ao mesmo servidor."""
    B.esperar_vez(url, 0.5)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            tipo = r.headers.get("Content-Type") or ""
            corpo = r.read(2_000_000)
    finally:
        B.pedido_feito(url)
    if "json" not in tipo:
        raise ValueError(f"não é JSON ({tipo[:40]})")
    return json.loads(corpo.decode("utf-8"))


def outros_enderecos() -> dict[str, tuple[str, str, str]]:
    """{ibge: (nome, uf, base)} das Câmaras que, pelo mapa das cidades (dados/municipios/<UF>.json), usam o SAPL num endereço
    diferente do padrão (ex.: sapl.cmm.am.gov.br em Manaus). Só domínios oficiais (.leg.br, .gov.br)."""
    nomes = {c[0]: (c[1], c[2]) for c in ler_json(DADOS / "cidades.json", []) or []}
    out = {}
    for arq in sorted((DADOS / "municipios").glob("*.json")):
        m = ler_json(arq) or {}
        for ibge, o in (m.get("cidades") or {}).items():
            cam = (o or {}).get("camara") if isinstance(o, dict) else None
            if not isinstance(cam, dict) or (cam.get("sistema") or "").lower() != "sapl" or not cam.get("api"):
                continue
            u = urllib.parse.urlparse(str(cam["api"]).strip())
            if not u.hostname or not re.search(r"\.(leg|gov)\.br$", u.hostname) or ibge not in nomes:
                continue
            if u.hostname != host(*nomes[ibge]):
                out[ibge] = (nomes[ibge][0], nomes[ibge][1], f"https://{u.hostname}")
    return out


def testar(ibge: str, nome: str, uf: str, base: str | None = None) -> dict:
    h = urllib.parse.urlparse(base).hostname if base else host(nome, uf)
    r = {"ibge": ibge, "nome": nome, "uf": uf, "host": h, "data": hoje(), "dns": False, "api": False,
         "legislaturaAtual": False, "vereadoresAtivos": None, "projetos2025": None, "segundos": None, "erro": None}
    t0 = time.time()
    try:
        socket.getaddrinfo(h, 443)
        r["dns"] = True
    except OSError:
        return r
    base = base or f"https://{h}"
    r["base"] = base
    try:
        legs = _json(f"{base}/api/parlamentares/legislatura/?page_size=100")
        r["api"] = isinstance(legs, dict) and "results" in legs
        d = hoje()
        atual = [l for l in legs.get("results") or [] if (l.get("data_inicio") or "") <= d <= (l.get("data_fim") or "")]
        r["legislaturaAtual"] = bool(atual)
        if atual:
            vinc = _json(f"{base}/api/parlamentares/legislatura/{atual[0]['id']}/parlamentares/?page_size=100")
            r["vereadoresAtivos"] = sum(1 for v in vinc.get("results") or [] if v.get("ativo"))
        tipos = _json(f"{base}/api/materia/tipomaterialegislativa/?page_size=100")
        ids = [t["id"] for t in tipos.get("results") or [] if PROPOSTAS.search(sem_acento((t.get("descricao") or "").lower()))]
        if ids:
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


def escrever_lista(com_proj: list[dict], ufs: set[str]) -> int:
    """scripts/camaras/sapl_cidades.json: as cidades com SAPL usável, menos as que têm coletor próprio (capitais). Mantém os
    ajustes feitos à mão; uma cidade dos estados testados que sumiu da descoberta (SAPL fora do ar no dia do teste)
    continua, marcada com a data."""
    proprios = {p.stem[1:] for p in (LISTA.parent).glob("c*.py")}
    antes = (ler_json(LISTA, {}) or {}).get("cidades") or {}
    novo = {}
    for r in com_proj:
        if r["ibge"] in proprios:
            continue
        e = dict(antes.get(r["ibge"]) or {})
        e.pop("foraDaDescoberta", None)
        e.setdefault("nome", r["nome"])
        e.setdefault("uf", r["uf"])
        e.setdefault("base", r.get("base") or f"https://{r['host']}")
        novo[r["ibge"]] = e
    for k, e in antes.items():
        if k not in novo and k not in proprios:
            novo[k] = dict(e, foraDaDescoberta=e.get("foraDaDescoberta") or hoje()) if e.get("uf") in ufs else e
    ordem = ("nome", "uf", "base")
    linhas = []
    for k in sorted(novo):
        e = {**{c: novo[k][c] for c in ordem if c in novo[k]}, **{c: v for c, v in novo[k].items() if c not in ordem}}
        linhas.append(f"  {json.dumps(k)}: {json.dumps(e, ensure_ascii=False)}")
    texto = ('{\n "sobre": "Câmaras Municipais com o SAPL (Interlegis) e API pública funcionando, menos as capitais (que têm '
             'coletor próprio). Feita por scripts/descobrir_sapl.py --lista; rodada por scripts/legislativos.py sapl. Campos: '
             'scripts/camaras/_lista.py.",\n "atualizado": ' + json.dumps(hoje()) + ',\n "cidades": {\n' + ",\n".join(linhas) +
             "\n }\n}\n")
    LISTA.write_text(texto, encoding="utf-8")
    return len(novo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="*")
    ap.add_argument("--dias", type=float, default=30)
    ap.add_argument("--max", type=int, default=0, help="testa só as primeiras N cidades (para experimentar)")
    ap.add_argument("--lista", action="store_true", help="atualiza scripts/camaras/sapl_cidades.json")
    ap.add_argument("--paralelo", type=int, default=32, help="cidades testadas ao mesmo tempo (cada uma no seu servidor)")
    a = ap.parse_args()
    cidades = ler_json(DADOS / "cidades.json", []) or []
    if a.uf:
        ufs = {u.upper() for u in a.uf}
        cidades = [c for c in cidades if c[2] in ufs]
    if a.max:
        cidades = cidades[:a.max]
    outros = outros_enderecos()
    if a.uf:
        outros = {k: v for k, v in outros.items() if v[1] in ufs}
    PASTA.mkdir(parents=True, exist_ok=True)
    PASTA_OUTROS.mkdir(parents=True, exist_ok=True)
    feitos, fila = [], []
    for ibge, nome, uf in cidades:
        arq = PASTA / f"{ibge}.json"
        if arq.exists() and (time.time() - arq.stat().st_mtime) / 86400 < a.dias:
            feitos.append(ler_json(arq))
        else:
            fila.append((ibge, nome, uf, None))
    feitos_outros = []
    for ibge, (nome, uf, base) in sorted(outros.items()):
        arq = PASTA_OUTROS / f"{ibge}.json"
        velho = ler_json(arq) if arq.exists() else None
        if velho and velho.get("base") == base and (time.time() - arq.stat().st_mtime) / 86400 < a.dias:
            feitos_outros.append(velho)
        else:
            fila.append((ibge, nome, uf, base))
    log(f"descoberta SAPL: {len(cidades)} cidades + {len(outros)} endereços do mapa das cidades, {len(fila)} para testar agora "
        f"({len(feitos) + len(feitos_outros)} no cache)")
    t0 = time.time()
    with cf.ThreadPoolExecutor(max(1, a.paralelo)) as ex:
        for i, r in enumerate(ex.map(lambda c: testar(*c), fila), 1):
            if r["host"] != host(r["nome"], r["uf"]):  # endereço que veio do mapa das cidades
                r.setdefault("base", outros.get(r["ibge"], (None, None, f"https://{r['host']}"))[2])
                salvar_json(PASTA_OUTROS / f"{r['ibge']}.json", r)
                feitos_outros.append(r)
            else:
                salvar_json(PASTA / f"{r['ibge']}.json", r)
                feitos.append(r)
            if i % 250 == 0:
                log(f"  {i}/{len(fila)} ({time.time() - t0:.0f} s)")
    # a mesma cidade nos dois: vale o endereço que funciona (o padrão primeiro)
    por_ibge = {}
    for r in feitos_outros + feitos:
        v = por_ibge.get(r["ibge"])
        if v is None or (r.get("projetos2025") or 0) > 0 and r.get("legislaturaAtual"):
            por_ibge[r["ibge"]] = r
    feitos = list(por_ibge.values())
    ok = [r for r in feitos if r.get("api")]
    atuais = [r for r in ok if r.get("legislaturaAtual")]
    com_proj = [r for r in atuais if (r.get("projetos2025") or 0) > 0]
    resumo = {
        "data": hoje(), "cidades": len(feitos), "dns": sum(1 for r in feitos if r.get("dns")), "api": len(ok),
        "legislaturaAtual": len(atuais), "comProjetos2025": len(com_proj),
        "segundosPorDia": round(sum(estimativa(r) for r in com_proj)),
        "porUF": {}, "lista": sorted(({**{k: r[k] for k in ("ibge", "nome", "uf", "host", "vereadoresAtivos", "projetos2025")},
                                       "base": r.get("base") or f"https://{r['host']}"} for r in com_proj),
                                     key=lambda x: (x["uf"], x["nome"])),
        "erros": sorted({r["erro"].split(":")[0] for r in feitos if r.get("erro")}),
    }
    for r in com_proj:
        resumo["porUF"][r["uf"]] = resumo["porUF"].get(r["uf"], 0) + 1
    if not a.uf and not a.max:
        salvar_json(B.PASTA_CACHE / "descoberta.json", resumo, indentado=True)
    log(f"descoberta SAPL: {resumo['dns']} com DNS, {resumo['api']} com API, {resumo['legislaturaAtual']} com a legislatura atual, "
        f"{resumo['comProjetos2025']} com projetos desde 2025; estimativa diária com cache: "
        f"{resumo['segundosPorDia'] / 60:.0f} min ({time.time() - t0:.0f} s agora)")
    if a.lista:
        n = escrever_lista(resumo["lista"], {c[2] for c in cidades})
        log(f"scripts/camaras/sapl_cidades.json: {n} cidades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
