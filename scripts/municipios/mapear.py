"""Mapa das 5.569 Câmaras Municipais e prefeituras (fase 1 da rodada "nenhum Em breve").

Para cada cidade de dados/cidades.json, descobre e confere no site oficial:
- Câmara Municipal: o site (.leg.br ou .gov.br), o sistema de proposições (SAPL do Interlegis, SAGL, SPL da Ágape
  "Câmara sem Papel" ou outro), se as proposições estão na internet (e, quando não, por quê) e a página de pedido de
  informação (e-SIC / Lei de Acesso à Informação);
- prefeitura: o site (.gov.br), o portal da transparência, o e-SIC e o Diário Oficial (o próprio ou o da associação de
  municípios que o publica por lei).

Pistas oficiais usadas antes de olhar os sites: a lista do Interlegis (domínios .leg.br, SAPL, Portal Modelo e o e-mail de
cada Câmara), a descoberta do SAPL (scripts/descobrir_sapl.py) e as listas de municípios dos Diários Oficiais das
associações (SIGPub em www.diariomunicipal.com.br e Assomasul). Ver _fontes.py.

Educado: robots.txt de cada site (e o "Crawl-delay"), 1 s entre pedidos ao mesmo site, até 3 pedidos ao mesmo tempo
para o mesmo servidor, até --paralelo cidades ao mesmo tempo (sites diferentes), tempo limite curto (_rede.py).
O que foi visto em cada cidade fica em .cache/municipios/cidades/<UF>/<IBGE>.json; só é refeito depois de --dias.
dados/municipios/<UF>.json é montado a partir desse cache (formato na seção 3 do contrato da rodada).

Uso:
  python scripts/municipios/mapear.py                  todos os estados (sem cache: algumas horas)
  python scripts/municipios/mapear.py AC BA            só estes estados
  python scripts/municipios/mapear.py --rodizio        o grupo de estados do dia da semana (cada estado 1 vez por semana)
  python scripts/municipios/mapear.py --montar         só remonta dados/municipios/ a partir do cache (sem rede)
  python scripts/municipios/mapear.py --ibge 1200013   uma cidade (para conferir): mostra o que achou
  python scripts/municipios/mapear.py --so-faltando    confere de novo só as cidades em que faltou o site da Câmara ou
                                                       da prefeitura
Opções: --dias N (refaz as cidades conferidas há mais de N dias; padrão 6), --paralelo N (padrão 16), --max N.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import queue
import random
import re
import sys
import threading
import time
import urllib.parse
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
from comum import CACHE, DADOS, fonte, hoje, ler_json, log, salvar_json, sem_mudar_data  # noqa: E402

import _fontes as F  # noqa: E402
import _paginas as P  # noqa: E402
import _rede  # noqa: E402

PASTA = CACHE / "municipios"
PASTA_CIDADES = PASTA / "cidades"
SAIDA = DADOS / "municipios"
RODADAS = PASTA / "rodadas.json"
VERSAO = 3
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ",
       "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
MANTER_DIAS = 45   # se o site não abrir numa rodada, vale o que foi conferido até este tanto de dias atrás
INICIO_LEGISLATURA = "2025-01-01"
CIGA_CONSORCIADOS: set = set()   # municípios de SC consorciados ao Ciga (preenchido em main)

# Por que as proposições da Câmara não aparecem (texto curto, que dá para conferir; sem "ainda não"/"em breve")
MOTIVOS = {
    "sem_site": ("Não achamos um site oficial da Câmara (endereço .leg.br ou .gov.br).",
                 "We found no official website for the City Council (.leg.br or .gov.br address)."),
    "fora_do_ar": ("O site oficial da Câmara não respondeu direito quando foi conferido.",
                   "The City Council's official website did not respond properly when it was checked."),
    "robots": ("O site da Câmara pede que programas automáticos não o leiam (robots.txt); por isso não foi conferido.",
               "The City Council's website asks automated programs not to read it (robots.txt), so it was not checked."),
    "bloqueio": ("O site da Câmara bloqueia a leitura por programas automáticos.",
                 "The City Council's website blocks reading by automated programs."),
    "site_so_navegador": ("O site oficial da Câmara só mostra o conteúdo num navegador comum; não foi conferido "
                          "automaticamente.",
                          "The City Council's official website only shows its content in a regular web browser; it was "
                          "not checked automatically."),
    "sem_link": ("Não achamos as proposições (projetos) a partir da página inicial do site oficial da Câmara.",
                 "We did not find the bills from the home page of the City Council's official website."),
    "sapl_sem_legislatura": ("O sistema de proposições da Câmara (SAPL) não tem a legislatura de 2025 a 2028.",
                             "The City Council's bill system (SAPL) does not include the 2025–2028 term."),
    "sapl_vazio": ("O sistema de proposições da Câmara (SAPL) não tem projetos apresentados desde 2025.",
                   "The City Council's bill system (SAPL) has no bills filed since 2025."),
    "sapl_fora": ("O sistema de proposições da Câmara (SAPL) não abriu quando foi conferido.",
                  "The City Council's bill system (SAPL) did not open when it was checked."),
    "antigas": ("A página de proposições da Câmara só mostra projetos até 2024.",
                "The City Council's bills page only shows bills up to 2024."),
    "sem_evidencia": ("A página de proposições da Câmara só mostra a lista num navegador comum; não foi conferida "
                      "automaticamente.",
                      "The City Council's bills page only shows its list in a regular web browser; it was not checked "
                      "automatically."),
    "propostas_fora": ("A página de proposições da Câmara não abriu quando foi conferida.",
                       "The City Council's bills page did not open when it was checked."),
}
# True = dá para ver as proposições; False = conferido que não estão onde deviam; None = não deu para conferir
ONLINE = {"sem_link": False, "sapl_sem_legislatura": False, "sapl_vazio": False, "antigas": False}

BLOQUEIO_CORPO = re.compile(r"cf-chl-|/cdn-cgi/challenge-platform/h/|cf_chl_opt|just a moment\.\.\.|attention required! \| "
                            r"cloudflare|ddos-guard|sucuri website firewall|incapsula incident|_incapsula_resource|"
                            r"request unsuccessful\. incapsula|bot verification|are you a robot|"
                            r"verifica[cç][aã]o de seguran[cç]a|confirme que voc[eê] n[aã]o [eé] um rob[oô]")
BLOQUEIO_TITULO = re.compile(r"just a moment|attention required|um momento|verifica|captcha|access denied|acesso negado|"
                             r"bot verification|security check|ddos")
# links "Câmara" no site da prefeitura que não são da Câmara Municipal (Câmara dos Deputados, Senado, Assembleia)
FORA_CAMARA = re.compile(r"(^|\.)camara\.leg\.br$|senado\.(leg|gov)\.br$|^(www\d?\.)?al[a-z]{0,3}\.[a-z]{2}\.(gov|leg)\.br$|"
                         r"alesp|assembleia|^(www\.)?cl\.df\.gov\.br$")


# ---------------------------------------------------------------------------------------------------- candidatos
def hosts_camara(ibge: str, uf: str, slugs: list[str], sigi: dict, curto: list[str] | None = None) -> list[tuple[str, str]]:
    """Endereços para testar, na ordem: os do Interlegis (domínio, Portal Modelo, e-mail) e os padrões de nome."""
    u = uf.lower()
    out: list[tuple[str, str]] = []

    def add(h: str, origem: str):
        h = (h or "").lower().strip(". /")
        # só endereços do próprio estado (um e-mail cadastrado errado já apontou a Câmara de outro estado)
        if h and h not in {x[0] for x in out} and h.endswith((f".{u}.leg.br", f".{u}.gov.br")):
            out.append((h, origem))

    d = sigi.get(ibge) or {}
    if d.get("ciga"):
        add(_rede.host_de(d["ciga"]), "ciga")
    if d.get("portal"):
        add(_rede.host_de(d["portal"]), "interlegis")
    for dom in d.get("leg", []) + d.get("gov", []):
        add(dom if dom.startswith("www.") else "www." + dom, "interlegis")
        add(dom, "interlegis")
    if d.get("email"):
        dom = d["email"]
        add(dom if dom.startswith("www.") else "www." + dom, "interlegis-email")
        add(dom, "interlegis-email")
    for s in slugs:
        add(f"www.{s}.{u}.leg.br", "padrao")
        add(f"{s}.{u}.leg.br", "padrao")
    s = slugs[0]
    for pre in ("camara", "cm", "camarade", "camaramunicipalde", "cmde", "cmv"):
        add(f"www.{pre}{s}.{u}.gov.br", "padrao")
        add(f"{pre}{s}.{u}.gov.br", "padrao")
    add(f"www.camara{s}.{u}.leg.br", "padrao")
    add(f"camara{s}.{u}.leg.br", "padrao")
    add(f"camara.{s}.{u}.gov.br", "padrao")
    for c in [P.compacto(x) for x in (curto or [])]:
        for h in (f"www.{c}.{u}.leg.br", f"{c}.{u}.leg.br", f"www.camara{c}.{u}.gov.br", f"camara{c}.{u}.gov.br",
                  f"www.cm{c}.{u}.gov.br", f"cm{c}.{u}.gov.br"):
            add(h, "curto")
    return out


def hosts_prefeitura(uf: str, slugs: list[str], curto: list[str] | None = None) -> list[tuple[str, str]]:
    u = uf.lower()
    out: list[tuple[str, str]] = []
    for s in slugs:
        for h in (f"www.{s}.{u}.gov.br", f"{s}.{u}.gov.br"):
            if h not in {x[0] for x in out}:
                out.append((h, "padrao"))
    s = slugs[0]
    for pre in ("prefeitura", "pm", "prefeiturade", "pmde"):
        out.append((f"www.{pre}{s}.{u}.gov.br", "padrao"))
        out.append((f"{pre}{s}.{u}.gov.br", "padrao"))
    for c in [P.compacto(x) for x in (curto or [])]:
        for h in (f"www.{c}.{u}.gov.br", f"{c}.{u}.gov.br", f"www.prefeitura{c}.{u}.gov.br", f"prefeitura{c}.{u}.gov.br"):
            if h not in {x[0] for x in out}:
                out.append((h, "curto"))
    return out


def nomes_curtos(cidades: list) -> dict[str, list[str]]:
    """{ibge: [nomes curtos]} só os que nenhuma outra cidade do estado tem (como nome ou como parte do nome)."""
    por_uf: dict[str, list[tuple[str, str]]] = {}
    for ibge, nome, uf in cidades:
        por_uf.setdefault(uf, []).append((ibge, " " + P.norm(nome) + " "))
    out = {}
    for ibge, nome, uf in cidades:
        bons = []
        for c in P.nome_curto(nome):
            outros = [i for i, n in por_uf[uf] if i != ibge and f" {c} " in n]
            if not outros:
                bons.append(c)
        if bons:
            out[ibge] = bons
    return out


# Endereço com o nome de outra cidade: o cadastro do Interlegis de algumas Câmaras traz o e-mail ou o domínio da Câmara
# vizinha (ex.: São José do Rio Preto com o e-mail da Câmara de Nova Aliança). Um endereço assim só vale se a página
# disser no topo o nome da cidade, e um bloco publicado com ele não é mantido.
SLUGS_UF: dict[str, dict[str, list[str]]] = {}   # {UF: {IBGE: formas do nome nos endereços}} (preparar_slugs)


def preparar_slugs(cidades: list):
    SLUGS_UF.clear()
    curtos = nomes_curtos(cidades)
    for ibge, nome, uf in cidades:
        formas = P.slugs_cidade(nome) + [P.compacto(c) for c in curtos.get(ibge) or []]
        SLUGS_UF.setdefault(uf, {})[ibge] = [f for f in dict.fromkeys(formas) if f]


def _host_nome(endereco: str | None) -> str:
    h = urllib.parse.urlsplit(endereco if "//" in (endereco or "") else "https://" + (endereco or "")).hostname or ""
    return h.lower().replace("-", "")


def proprio(endereco: str | None, uf: str | None, ibge: str | None) -> bool:
    """O endereço tem uma forma do nome desta cidade."""
    h = _host_nome(endereco)
    return bool(h) and any(m in h for m in (SLUGS_UF.get(uf or "") or {}).get(ibge) or [])


def alheio(endereco: str | None, uf: str | None, ibge: str | None) -> str | None:
    """O endereço tem o nome de outra cidade do estado, e nenhuma forma do nome desta: devolve o IBGE da outra cidade.
    Só nomes com 6 letras ou mais, e não conta o nome de outra cidade que é parte do nome desta ("Divino" em
    "Divinolândia de Minas", "São Luís" em "São Luís Gonzaga do Maranhão")."""
    formas = SLUGS_UF.get(uf or "") or {}
    if not endereco or not formas or ibge not in formas:
        return None
    h = _host_nome(endereco)
    meus = formas[ibge]
    if not h or any(m in h for m in meus):
        return None
    achado, tam = None, 0
    for outro, sl in formas.items():
        if outro == ibge:
            continue
        for s in sl:
            if len(s) >= 6 and len(s) > tam and s in h and not any(s in m for m in meus):
                achado, tam = outro, len(s)
    return achado


def oficial(host: str) -> bool:
    return host.endswith(".leg.br") or host.endswith(".gov.br") or host.endswith(".jus.br")


# ---------------------------------------------------------------------------------------------------- visitar
def visitar(rede: _rede.Rede, url: str) -> dict:
    """Página de um endereço (https; se a conexão falhar, http). Segue 'meta refresh', redirecionamento por script e
    página feita só de frames, uma vez."""
    p = urllib.parse.urlsplit(url)
    tentativas = [url]
    if p.scheme == "https" and p.path in ("", "/"):
        tentativas.append(urllib.parse.urlunsplit(("http", p.netloc, p.path or "/", p.query, "")))
    r = None
    for u in tentativas:
        r = rede.pagina(u)
        if r.erro == "robots" and rede.robots_estado(r.final) == "nada" and u != tentativas[-1]:
            continue   # o robots.txt não respondeu por https (certificado, TLS antigo): tenta por http
        if r.erro in ("dns", "robots") or r.ok:
            break
        if r.status is not None and r.status < 500 and r.erro != "tls":
            break
    v = {"url": r.final, "status": r.status, "erro": r.erro, "tls": r.tls, "pagina": None}
    if r.erro == "robots":
        v["robots"] = rede.robots_estado(r.final)
        marca = rede.robots_marca(r.final)
        if marca:
            v["robotsMarca"] = marca
        return v
    if not r.ok:
        corpo = r.corpo[:30000].decode("utf-8", "replace").lower() if r.corpo else ""
        if r.status in (401, 403, 405, 406, 429, 503) and BLOQUEIO_CORPO.search(corpo):
            v["erro"] = "bloqueio"
        return v
    pg = P.ler(r.corpo, r.charset, r.final)
    seguir = pg.refresh or pg.js_redir or (pg.frames[0] if pg.frames and len(pg.texto) < 400 else None)
    if seguir and seguir.split("#")[0] != r.final.split("#")[0]:
        r2 = rede.pagina(seguir)
        if r2.ok and r2.corpo:
            pg = P.ler(r2.corpo, r2.charset, r2.final)
            v.update({"url": r2.final, "status": r2.status, "tls": r2.tls})
    if len(pg.links) < 5 and len(pg.texto) < 600 and (BLOQUEIO_TITULO.search(P.norm(pg.titulo))
                                                       or BLOQUEIO_CORPO.search(pg.bruto[:30000])):
        v["erro"] = "bloqueio"
        return v
    v["pagina"] = pg
    return v


def resolver_todos(rede: _rede.Rede, dns_pool: cf.ThreadPoolExecutor, hosts: list[str]) -> dict[str, str | None]:
    futuros = {h: dns_pool.submit(rede.ip, h) for h in hosts}
    return {h: f.result() for h, f in futuros.items()}


def achar_site(rede, dns_pool, nome: str, cands: list[tuple[str, str]], tipo: str, max_visitas: int = 6,
               curto: list[str] | None = None, uf: str | None = None, ibge: str | None = None) -> dict:
    """Testa os endereços na ordem e devolve o primeiro que é mesmo da Câmara (ou da prefeitura) da cidade."""
    ips = resolver_todos(rede, dns_pool, [h for h, _ in cands])
    visitas = []
    achado = None
    ja_ip_ok: dict[str, bool] = {}
    for host, origem in cands:
        ip = ips.get(host)
        if not ip:
            continue
        par = host[4:] if host.startswith("www.") else "www." + host
        if par in ja_ip_ok and ips.get(par) == ip and ja_ip_ok[par] in (True, "morto"):
            continue   # mesmo servidor do par www/sem www já visitado
        if len(visitas) >= max_visitas:
            break
        v = visitar(rede, f"https://{host}/")
        info = {"host": host, "origem": origem, "url": v["url"], "status": v["status"], "erro": v["erro"],
                "tls": v["tls"]}
        if v.get("robots"):
            info["robots"] = v["robots"]
            if v.get("robotsMarca"):
                info["robotsMarca"] = v["robotsMarca"]
        pg = v["pagina"]
        # o par www/sem www (mesmo servidor) é pulado quando este respondeu com uma página (que não era da cidade) ou
        # quando o servidor nem respondeu; com erro de certificado, robots.txt ou 4xx, o par ainda é tentado
        ja_ip_ok[host] = True if pg is not None else ("morto" if v["erro"] in ("timeout", "conexao", "suspenso") else None)
        if pg is not None:
            d = P.dono(pg, nome)
            info.update({"titulo": pg.titulo[:120], "dono": d})
            forte = origem not in ("link", "curto")
            meu, outro = (d["camara"], d["prefeitura"]) if tipo == "camara" else (d["prefeitura"], d["camara"])
            if origem == "curto":   # endereço com o nome curto da cidade (único no estado): a página tem de dizer o nome
                cidade_ok = d["cidade"] or any(P.tem_cidade(pg.cabeca(), c) for c in (curto or []))
            elif origem == "interlegis-email" and not d["cidade"] and not proprio(host, uf, ibge):
                # o e-mail cadastrado no Interlegis às vezes é de outra Câmara (a da capital, a vizinha): o endereço tirado
                # dele só vale se a página falar da cidade ou se ele tiver o nome dela
                cidade_ok = False
            else:
                cidade_ok = forte or d["cidadeNoTopo"] or (d["cidade"] and meu >= 10)
            ok = not d["estacionada"] and not d["vazia"] and meu >= 3 and meu > outro and cidade_ok
            if (not ok and tipo == "prefeitura" and origem == "padrao" and not d["estacionada"]
                    and (not d["vazia"] or d["spa"]) and (d["cidadeNoTopo"] or d["cidade"]) and outro < 10):
                ok = True   # endereço com o nome da cidade (reservado ao município) e a página fala da cidade
            if (not ok and d["spa"] and not d["estacionada"] and meu >= 10 and meu > outro
                    and (d["cidadeNoTopo"] or (forte and origem != "curto"
                                               and (origem != "interlegis-email" or proprio(host, uf, ibge))))):
                ok = True   # site montado no navegador: vale o título (que diz de quem é)
                info["spa"] = True
            final = _rede.host_de(v["url"])   # o endereço final só vira o site publicado se for oficial (origem_site)
            outra = alheio(host, uf, ibge) or (alheio(final, uf, ibge) if final and oficial(final) else None)
            if outra:
                info["outraCidade"] = outra
                if not d["cidadeNoTopo"]:
                    ok = False   # endereço de outra cidade (cadastro errado) e a página não diz o nome desta no topo
            info["ok"] = ok
            if ok:
                visitas.append(info)
                achado = (host, v, pg)
                break
        visitas.append(info)
    return {"visitas": visitas, "achado": achado}


def origem_site(host: str, v: dict) -> str:
    """Endereço que vai para o mapa: o do domínio oficial (se o site redireciona para outro domínio, fica o oficial)."""
    final = _rede.host_de(v["url"])
    esquema = urllib.parse.urlsplit(v["url"]).scheme or "https"
    if final and oficial(final):
        return f"{esquema}://{final}/"
    return f"https://{host}/"


def checar_pagina(rede, url: str, estrito: bool = False) -> dict:
    """Abre uma página de proposições (ou de Diário Oficial) e devolve o que dá para saber dela."""
    v = visitar(rede, url)
    out = {"url": v["url"], "status": v["status"], "erro": v["erro"]}
    pg = v["pagina"]
    if pg is not None:
        out.update({"titulo": pg.titulo[:120], "evidencia": P.evidencia_propostas(pg, estrito),
                    "fornecedor": P.fornecedor(pg), "sistemas": P.achar_sistemas(pg)[:5], "texto": len(pg.texto),
                    "marcas": P.marcas(pg)})
        if estrito:
            out["estrito"] = True
        out["_pagina"] = pg
    return out


# ---------------------------------------------------------------------------------------------------- uma cidade
def mapear_cidade(rede: _rede.Rede, dns_pool, cidade: tuple, sigi: dict, curto: list[str] | None = None) -> dict:
    ibge, nome, uf = cidade
    t0 = time.time()
    slugs = P.slugs_cidade(nome)
    bruto = {"ibge": ibge, "nome": nome, "uf": uf, "data": hoje(), "versao": VERSAO}

    # prefeitura primeiro: o site dela às vezes tem o link da Câmara
    pref = {"site": None}
    cands_p = hosts_prefeitura(uf, slugs, curto)
    r = achar_site(rede, dns_pool, nome, cands_p, "prefeitura", curto=curto, uf=uf, ibge=ibge)
    pref["visitas"] = r["visitas"]
    links_camara = []
    if r["achado"]:
        host, v, pg = r["achado"]
        pref.update(_dados_prefeitura(rede, host, v, pg, uf, nome))
        links_camara = [u for u, txt, _ in pg.links
                        if re.search(r"\bcamara\b|legislativo", txt) and oficial(_rede.host_de(u))
                        and _rede.host_de(u) != host and not FORA_CAMARA.search(_rede.host_de(u))]
    bruto["prefeitura"] = pref

    cam = {"site": None}
    cands = hosts_camara(ibge, uf, slugs, sigi, curto)
    for u in links_camara[:3]:
        h = _rede.host_de(u)
        if h and h not in {x[0] for x in cands} and h.endswith((f".{uf.lower()}.leg.br", f".{uf.lower()}.gov.br")):
            cands.append((h, "link"))
    r = achar_site(rede, dns_pool, nome, cands, "camara", curto=curto, uf=uf, ibge=ibge)
    cam["visitas"] = r["visitas"]
    if r["achado"]:
        host, v, pg = r["achado"]
        cam.update(_dados_camara(rede, host, v, pg))
    bruto["camara"] = cam

    # sem site da prefeitura: o site da Câmara às vezes tem o link
    if not pref.get("site") and r["achado"]:
        _, _, pgc = r["achado"]
        ja = {x[0] for x in cands_p}
        lp = [u for u, txt, _ in pgc.links if re.search(r"\bprefeitura\b", txt) and oficial(_rede.host_de(u))
              and _rede.host_de(u) not in ja and _rede.host_de(u).endswith(f".{uf.lower()}.gov.br")]
        if lp:
            hc = [(_rede.host_de(lp[0]), "link")]
            r2 = achar_site(rede, dns_pool, nome, hc, "prefeitura", max_visitas=1, uf=uf, ibge=ibge)
            pref["visitas"] += r2["visitas"]
            if r2["achado"]:
                host, v, pg = r2["achado"]
                pref.update(_dados_prefeitura(rede, host, v, pg, uf, nome))
    bruto["segundos"] = round(time.time() - t0, 1)
    return bruto


def _dados_camara(rede, host: str, v: dict, pg: P.Pagina) -> dict:
    d = {"site": origem_site(host, v), "final": v["url"], "titulo": pg.titulo[:150], "tls": v["tls"],
         "gerador": pg.gerador[:60], "rodape": pg.rodape, "fornecedor": P.fornecedor(pg), "marcas": P.marcas(pg),
         "sic": P.achar_sic(pg), "transparencia": P.achar_transparencia(pg),
         "sistemas": P.achar_sistemas(pg)[:6], "conferido": hoje()}
    if pg.so_navegador():
        d["spa"] = True
    cands = P.achar_propostas(pg, quantos=6, com_peso=True)
    d["propostasLink"] = cands[0][1] if cands else None
    # página de proposições que não é o SAPL (o SAPL é conferido pela API, em outra etapa)
    alvos = [(u, False) for sis, u in d["sistemas"] if sis in ("sagl", "nopaper")][:1]
    fortes = [u for peso, u in cands if peso >= 7 and not re.search(r"//sapl|/sapl\b", u.lower())]
    alvos += [(u, False) for u in fortes if u not in [a[0] for a in alvos]][:2]
    legis = [u for peso, u in cands if peso < 7]
    if legis:
        alvos.append((legis[0], True))   # "Legislação": só vale se listar projetos numerados
    abertas = 0
    for alvo, estrito in alvos:
        if estrito and any(x.get("evidencia") in ("recentes", "antigas", "navegador")
                           for x in d.get("propostasPaginas", [])):
            break
        if abertas >= 3:
            break
        c = checar_pagina(rede, alvo, estrito)
        abertas += 1
        pgp = c.pop("_pagina", None)
        c["link"] = alvo
        d.setdefault("propostasPaginas", []).append(c)
        if pgp is not None:
            for sis, u in P.achar_sistemas(pgp)[:3]:   # a página de proposições às vezes leva ao SAPL
                if (sis, u) not in d["sistemas"]:
                    d["sistemas"].append((sis, u))
        if c.get("evidencia") in ("recentes", "navegador"):
            break
    return d


def _dados_prefeitura(rede, host: str, v: dict, pg: P.Pagina, uf: str, nome: str) -> dict:
    d = {"site": origem_site(host, v), "final": v["url"], "titulo": pg.titulo[:150], "tls": v["tls"],
         "gerador": pg.gerador[:60], "rodape": pg.rodape, "fornecedor": P.fornecedor(pg),
         "sic": P.achar_sic(pg), "transparencia": P.achar_transparencia(pg),
         "legislacao": P.achar_legislacao(pg), "conferido": hoje()}
    if pg.so_navegador():
        d["spa"] = True
    for k in ("transparencia", "sic", "legislacao"):   # link que só volta para a página inicial não serve
        if d[k] and urllib.parse.urlsplit(d[k]).path in ("", "/") and _rede.host_de(d[k]) in (host, _rede.host_de(v["url"])):
            d[k] = None
    du, dt_ = P.achar_diario(pg)
    if du:
        d["diarioLink"], d["diarioTexto"] = du, dt_
        pid, _ = P.plataforma_diario(du)
        # link para uma página do próprio site: abre para ver se ela leva a uma plataforma conhecida
        if pid == "propria" and not P.eh_doe_estado(du, uf):
            c = checar_pagina(rede, du)
            pgd = c.pop("_pagina", None)
            info = {"url": c["url"], "status": c["status"], "erro": c["erro"], "titulo": c.get("titulo")}
            if pgd is not None:
                for u in [x[0] for x in pgd.links] + pgd.frames:
                    p2, _ = P.plataforma_diario(u)
                    if p2 not in ("propria",) and not re.search(r"in\.gov\.br|imprensanacional", u.lower()):
                        info["plataforma"] = u
                        break
                info["final"] = c["url"]
            d["diarioPagina"] = info
    return d


# ---------------------------------------------------------------------------------------------------- montar
def _so_origem(url: str | None) -> str | None:
    return url or None


def sapl_info(ibge: str, cam: dict, sigi: dict, slugs: list[str], uf: str) -> list[dict]:
    """Os SAPL ligados à Câmara (descoberta, Interlegis, links do site), com o resultado da API se já conferido."""
    hosts = []
    sufixos = (f".{uf.lower()}.leg.br", f".{uf.lower()}.gov.br")
    for sis, u in cam.get("sistemas") or []:
        if sis == "sapl":
            h = _rede.host_de(u)
            if h and h.startswith("sapl") and h not in hosts:
                hosts.append(h)
    for h in (sigi.get(ibge) or {}).get("sapl", []):
        if h not in hosts and h.endswith(sufixos):
            hosts.append(h)
    padrao = f"sapl.{slugs[0]}.{uf.lower()}.leg.br"
    if padrao not in hosts:
        hosts.append(padrao)
    out = []
    for h in hosts:
        info = F.sapl_descoberta(ibge, h) or F.sapl_cache(h)
        out.append({"host": h, "info": info})
    return out


def sapl_pendentes(brutos: list[dict], sigi: dict) -> list[str]:
    """SAPLs que aparecem nas pistas e ainda não foram conferidos pela API (nem pela descoberta)."""
    falta = []
    for b in brutos:
        slugs = P.slugs_cidade(b["nome"])
        for s in sapl_info(b["ibge"], b.get("camara") or {}, sigi, slugs, b["uf"]):
            if s["info"] is None and s["host"] not in falta:
                # o padrão sapl.<cidade>.<uf>.leg.br só é testado se o DNS existir
                falta.append(s["host"])
    return falta


def montar_cidade(b: dict, sigi: dict, diarios: dict, nomes_assoc: dict) -> dict:
    ibge, nome, uf = b["ibge"], b["nome"], b["uf"]
    slugs = P.slugs_cidade(nome)
    cam = b.get("camara") or {}
    pref = b.get("prefeitura") or {}

    # ---------------- Câmara
    saplz = [s for s in sapl_info(ibge, cam, sigi, slugs, uf) if s["info"] and s["info"].get("dns", True)]
    sapl_ok = next((s for s in saplz if s["info"].get("api") and s["info"].get("legislaturaAtual")
                    and (s["info"].get("projetos2025") or 0) > 0), None)
    sapl_api = sapl_ok or next((s for s in saplz if s["info"].get("api")), None)
    site = cam.get("site")
    sistema = plataforma = api = propostas = None
    online, motivo = None, None
    sis_links = cam.get("sistemas") or []
    pp_sis = next((s for s, u in sis_links if s in ("sagl", "nopaper")), None)
    # das páginas de proposições abertas, a que diz mais: com projetos recentes > só antigos > só no navegador
    paginas = cam.get("propostasPaginas") or ([cam["propostasPagina"]] if cam.get("propostasPagina") else [])
    paginas = [x for x in paginas if not P.parece_noticia(x.get("link") or x.get("url") or "")]
    ordem = {"recentes": 0, "antigas": 1, "navegador": 2}
    abertas = sorted([x for x in paginas if x.get("status") and not x.get("erro") and x.get("evidencia") in ordem],
                     key=lambda x: ordem[x["evidencia"]])
    pp = abertas[0] if abertas else None
    pp_fora = bool(paginas) and all(x.get("erro") or not x.get("status") for x in paginas)

    def usa_sapl(s):
        base = f"https://{s['host']}"
        return "sapl", base + "/api/", base + "/materia/pesquisar-materia"

    if sapl_ok:
        sistema, api, propostas = usa_sapl(sapl_ok)
        online = True
        site = site or f"https://{sapl_ok['host']}/"
    elif pp and pp["evidencia"] == "recentes":
        sistema, propostas, online = pp_sis or "outro", pp.get("link") or pp.get("url"), True
    elif pp and pp["evidencia"] == "antigas" and not sapl_api:
        sistema, propostas, motivo = pp_sis or "outro", pp.get("link") or pp.get("url"), "antigas"
    elif pp and pp["evidencia"] == "navegador":
        sistema, propostas, motivo = pp_sis or "outro", pp.get("link") or pp.get("url"), "sem_evidencia"
    elif sapl_api:
        sistema, api, propostas = usa_sapl(sapl_api)
        motivo = "sapl_sem_legislatura" if not sapl_api["info"].get("legislaturaAtual") else "sapl_vazio"
        site = site or f"https://{sapl_api['host']}/"
    elif site and pp_fora:
        sistema, motivo = pp_sis or "outro", "propostas_fora"
    elif site and cam.get("spa") and not paginas:
        motivo = "site_so_navegador"
    elif site:
        sapl_link = next((u for s, u in sis_links if s == "sapl"), None)
        if sapl_link:   # link para um SAPL que não respondeu pela API (fora do ar ou SAPL 2.x)
            sistema, propostas, motivo = "sapl", sapl_link, "sapl_fora"
        else:
            motivo = "sem_link"
    else:
        vis = cam.get("visitas") or []
        erros = [x.get("erro") for x in vis]
        if any(x.get("erro") == "robots" and x.get("robots") == "regras" for x in vis):
            motivo = "robots"
        elif "bloqueio" in erros or any(e in ("http 401", "http 403", "http 429") for e in erros):
            motivo = "bloqueio"
        elif any(e in ("timeout", "conexao", "tls", "robots", "redirecionamentos", "suspenso")
                 or (e or "").startswith("http 5") for e in erros):
            motivo = "fora_do_ar"
        else:
            motivo = "sem_site"
    if sistema == "outro" and pp:
        plataforma = (P.fornecedor_marcas(pp.get("marcas")) or pp.get("fornecedor")
                      or P.fornecedor_marcas(cam.get("marcas")) or None)
    if online is None and motivo:
        online = ONLINE.get(motivo)
    if site is None and motivo in ("robots", "bloqueio", "fora_do_ar"):
        # o endereço oficial existe (respondeu com erro ou pediu para não ser lido): mostra o endereço
        v = next((x for x in cam.get("visitas") or [] if x.get("origem") in ("interlegis", "padrao", "ciga") and (
            x.get("erro") in ("robots", "bloqueio", "timeout", "conexao", "tls", "suspenso", "http 401", "http 403",
                              "http 429") or (x.get("erro") or "").startswith("http 5"))),
            None)
        if v:
            site = f"https://{v['host']}/"
    camara = {"site": iri(site), "sistema": sistema, "api": api, "propostas": iri(propostas), "propostasOnline": online,
              "sic": iri(cam.get("sic")), "conferido": cam.get("conferido") or b.get("data"),
              "motivo": MOTIVOS[motivo][0] if motivo and not online else None,
              "motivo_en": MOTIVOS[motivo][1] if motivo and not online else None}
    if plataforma:
        camara["plataforma"] = plataforma

    # ---------------- prefeitura
    diario = _escolher_diario(b, pref, diarios, nomes_assoc)
    if diario:
        diario["url"] = iri(diario["url"])
    site_p, lido = pref.get("site"), True
    if not site_p:
        # o endereço com o nome da cidade existe mas não pôde ser lido (robots.txt, bloqueio, erro do servidor):
        # vale o endereço, sem o que estaria na página
        u_ = uf.lower()
        reservados = set()
        for s in slugs:
            for pre in ("", "pm", "prefeitura", "prefeiturade", "pmde"):
                reservados |= {f"{pre}{s}.{u_}.gov.br", f"www.{pre}{s}.{u_}.gov.br"}
        v = next((x for x in pref.get("visitas") or [] if x.get("host") in reservados and x.get("erro") and (
            x["erro"] in ("robots", "bloqueio", "tls", "suspenso") or x["erro"].startswith("http "))),
            None)
        if v:
            site_p, lido = f"https://{v['host']}/", False
    prefeitura = {"site": iri(site_p), "transparencia": iri(pref.get("transparencia")),
                  "sic": iri(pref.get("sic")), "diarioOficial": diario,
                  "conferido": pref.get("conferido") or b.get("data")}
    if not lido:
        prefeitura["lido"] = False
    return {"camara": camara, "prefeitura": prefeitura}


def iri(url: str | None) -> str | None:
    """Endereço mais curto e legível: '%C3%A7' vira 'ç' (os navegadores aceitam os dois). Só as letras acentuadas são
    trocadas; '%20', '%2F' e outros sinais continuam como estão."""
    if not url:
        return None

    def troca(m):
        try:
            s = bytes.fromhex(m.group(0).replace("%", "")).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return m.group(0)
        return s if all(ord(ch) > 127 and ch.isprintable() for ch in s) else m.group(0)

    return re.sub(r"(?:%[89A-Fa-f][0-9A-Fa-f]%[89ABab][0-9A-Fa-f](?:%[89ABab][0-9A-Fa-f]){0,2})+", troca, url)


def _nome_proprio_diario(nome_cidade: str) -> str:
    return f"Diário Oficial do Município de {nome_cidade}"


# Diários em domínios que não são .gov.br: só entram quando ao menos 3 prefeituras indicam o mesmo endereço no site
# oficial (é uma plataforma de Diário Oficial usada por várias cidades); um endereço que só uma cidade indica fica de fora.
MIN_CIDADES_PLATAFORMA = 3
NAO_DIARIO = re.compile(r"in\.gov\.br|e-diariooficial\.com|play\.google|apps\.apple|esic\.|/esic|ouvidoria|"
                        r"controlepublicacao|/login|painel\.|:\d{3,5}/|noticia|/blog/|/post/")
NOMES_HOST = {  # plataformas compartilhadas que não estão em _paginas.PLATAFORMAS (nome que aparece no próprio site)
    "diarioficialdosmunicipios.org": "Diário Oficial dos Municípios (diarioficialdosmunicipios.org)",
    "diariooficialdasprefeituras.org": "Diário Oficial das Prefeituras, Municípios e Câmaras (diariooficialdasprefeituras.org)",
    "doempi.org": "Diário Oficial Eletrônico dos Municípios do Piauí (DOEMPI)",
}
_HOSTS_DIARIO: dict[str, int] | None = None


def hosts_diario() -> dict[str, int]:
    """Quantas prefeituras indicam cada endereço (fora de .gov.br) como Diário Oficial (lê o cache, sem rede)."""
    global _HOSTS_DIARIO
    if _HOSTS_DIARIO is None:
        cont: dict[str, set] = {}
        for f in PASTA_CIDADES.glob("*/*.json"):
            b = ler_json(f) or {}
            p = b.get("prefeitura") or {}
            for u in {p.get("diarioLink"), (p.get("diarioPagina") or {}).get("plataforma")} - {None}:
                h = _rede.host_de(u).removeprefix("www.")
                if h and not oficial(h):
                    cont.setdefault(h, set()).add(b.get("ibge"))
        _HOSTS_DIARIO = {h: len(v) for h, v in cont.items()}
    return _HOSTS_DIARIO


def _link_de_diario(link: str | None, texto: str | None) -> bool:
    """O link é mesmo do Diário Oficial? (não é notícia, nem a cidade "Dom Expedito Lopes", nem o DOU)"""
    if not link or NAO_DIARIO.search(link.lower()) or P.parece_noticia(link) or re.search(r"/20\d\d/\d\d/", link):
        return False
    if re.search(r"diario|imprensa-?oficial|jornaloficial|jornal-oficial|doem\.|/dom\b|//dom\.|diariomunicipal",
                 link.lower()):
        return True    # o próprio endereço diz que é Diário Oficial
    t = P.norm(texto or "")
    return len(t) <= 70 and bool(re.search(r"diario|imprensa oficial|jornal oficial|\bdom\b|\bdoe\b|\bdoem\b|"
                                           r"publicac(ao|oes) (oficia|lega)|atos oficiais", t))


def _diario_associacao(x: dict) -> dict:
    plat = {"assomasul": "Diário Oficial MS (Assomasul)", "amm-mt-jornal": "DexaTec (Jornal Oficial AMM-MT)"}
    out = {"nome": x["nome"], "url": x["url"], "plataforma": plat.get(x["assoc"], "SIGPub (diariomunicipal.com.br)")}
    if x.get("entidade"):
        out["entidade"] = x["entidade"]
    return out


def _escolher_diario(b: dict, pref: dict, diarios: dict, nomes_assoc: dict) -> dict | None:
    """O Diário Oficial da prefeitura: (1) o que o site da prefeitura indica, quando é uma plataforma conhecida;
    (2) o da associação de municípios em que a cidade publicou nos últimos 6 meses; (3) a página própria que o site
    indica. Uma cidade que só aparece na lista da associação, sem publicar há 6 meses, não é ligada a ela."""
    ibge, nome, uf = b["ibge"], b["nome"], b["uf"]
    listas = diarios.get(ibge) or []
    ativas = []
    for x in listas:
        a = F.atividade_cache(x["assoc"], x["entidade"]) or {}
        if (a.get("materias6m") or 0) > 0:
            ativas.append((a.get("materias6m") or 0, x))
    ativas = [x for _, x in sorted(ativas, key=lambda t: -t[0])]
    link = pref.get("diarioLink")
    if not _link_de_diario(link, pref.get("diarioTexto")):
        link = None
    pag = pref.get("diarioPagina") or {}
    alvo = (pag.get("plataforma") if link else None) or link
    pid, pnome = P.plataforma_diario(alvo) if alvo else (None, None)
    if alvo and pid != "propria":
        if pid == "sigpub":
            m = re.search(r"diariomunicipal\.com\.br/([a-z0-9\-]+)", alvo.lower())
            slug = m.group(1) if m else None
            ent = next((x for x in listas if x["assoc"] == slug), None)
            nm = (ent or {}).get("nome") or nomes_assoc.get(slug) or "Diário Oficial dos Municípios (SIGPub)"
            out = {"nome": nm, "url": f"{F.SIGPUB_BASE}{slug}/" if slug else alvo, "plataforma": pnome}
            if ent:
                out["entidade"] = ent["entidade"]
            return out
        if pid == "assomasul":
            ent = next((x for x in listas if x["assoc"] == "assomasul"), None)
            out = {"nome": "Diário Oficial MS (Assomasul)", "url": F.ASSOMASUL, "plataforma": pnome}
            if ent:
                out["entidade"] = ent["entidade"]
            return out
        if pid == "dexatec":
            ent = next((x for x in listas if x["assoc"] == "amm-mt-jornal"), None)
            out = {"nome": "Jornal Oficial AMM-MT (Associação Mato-grossense dos Municípios)", "url": f"{F.AMM_MT}/",
                   "plataforma": pnome}
            if ent:
                out["entidade"] = ent["entidade"]
            return out
        if pid == "dom-sc":
            return {"nome": "Diário Oficial dos Municípios de Santa Catarina (DOM/SC)",
                    "url": "https://diariomunicipal.sc.gov.br/", "plataforma": pnome}
        if pid == "dio-es":
            return {"nome": "Diário Oficial dos Municípios do Espírito Santo (DOM/ES, Amunes)",
                    "url": "https://ioes.dio.es.gov.br/dom", "plataforma": pnome}
        if pid == "siganet" and "famem" in alvo.lower():
            return {"nome": "Diário Oficial dos Municípios do Maranhão (Famem)",
                    "url": "https://diariooficial.famem.org.br/", "plataforma": pnome}
        return {"nome": _nome_proprio_diario(nome), "url": alvo, "plataforma": pnome}
    if alvo and P.eh_doe_estado(alvo, uf):
        return {"nome": P.DOE_ESTADO.get(uf, "Diário Oficial do Estado"), "url": alvo,
                "plataforma": "Diário Oficial do Estado"}
    if ativas:
        return _diario_associacao(ativas[0])
    if alvo and oficial(_rede.host_de(alvo)):
        return {"nome": _nome_proprio_diario(nome), "url": link, "plataforma": pnome}
    if alvo:
        h = _rede.host_de(alvo).removeprefix("www.")
        if hosts_diario().get(h, 0) >= MIN_CIDADES_PLATAFORMA:
            return {"nome": NOMES_HOST.get(h) or _nome_proprio_diario(nome), "url": alvo,
                    "plataforma": NOMES_HOST.get(h, h).split(" (")[0] if h in NOMES_HOST else h}
    if uf == "SC" and ibge in CIGA_CONSORCIADOS:
        # o DOM/SC não deixa robôs lerem: a cidade é consorciada ao Ciga, que mantém o DOM/SC (291 municípios o usam)
        return {"nome": "Diário Oficial dos Municípios de Santa Catarina (DOM/SC)", "url": "https://diariomunicipal.sc.gov.br/",
                "plataforma": "DOM/SC (Consórcio CIGA)", "confirmado": False}
    return None


def montar_uf(uf: str, cidades: list, sigi: dict, diarios: dict, nomes_assoc: dict, fontes_base: list) -> dict:
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"{uf}.json"
    out = {"uf": uf, "atualizado": hoje(), "fontes": [], "cidades": {}}
    if uf == "DF":
        out["nota"] = ("O Distrito Federal não tem municípios: Brasília não tem prefeitura nem Câmara Municipal. "
                       "O Governo do Distrito Federal e a Câmara Legislativa do DF fazem esse papel.")
        out["nota_en"] = ("The Federal District has no municipalities: Brasília has no city hall and no City Council. "
                          "The Federal District Government and the Legislative Chamber of the Federal District play "
                          "that role.")
        out["fontes"] = [fonte("Planalto", "Constituição Federal, art. 32 (o Distrito Federal não pode ser dividido em "
                               "municípios)", "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
                               "1988-10-05")]
    datas = []
    # o que já estava publicado: no robô (que roda fora do Brasil e pode começar com o cache vazio), um site que não abriu
    # por um erro passageiro não apaga o que já tinha sido conferido (fica o bloco anterior, com a data dele)
    publicado = (ler_json(destino) or {}).get("cidades") or {}
    for ibge, nome, uf_ in cidades:
        b = ler_json(PASTA_CIDADES / uf / f"{ibge}.json")
        if not b:
            if ibge in publicado:
                out["cidades"][ibge] = publicado[ibge]
            continue
        out["cidades"][ibge] = manter_publicado(montar_cidade(b, sigi, diarios, nomes_assoc), publicado.get(ibge), b)
        datas.append(b.get("data") or "")
    if uf != "DF":
        fs = []
        for f in fontes_base:
            if not f or f.get("uf") not in (None, uf):
                continue
            f = {k: v for k, v in f.items() if k != "uf"}
            if f["url"] == F.SIGI_URL:
                f["url"] = f"{F.SIGI_URL}{uf}/"
            fs.append(f)
        # uma lista que não abriu nesta rodada continua citada: os endereços que vieram dela continuam no mapa
        urls = {f["url"] for f in fs}
        fs += [f for f in (ler_json(destino) or {}).get("fontes") or [] if f.get("url") not in urls]
        out["fontes"] = fs
        out["nota"] = ("Cada endereço foi conferido no próprio site oficial (Câmara, prefeitura, sistema de proposições ou "
                       "Diário Oficial) na data de \"conferido\". As listas acima só indicam onde procurar.")
        out["nota_en"] = ("Each address was checked on the official website itself (City Council, city hall, bill system "
                          "or official gazette) on the \"conferido\" (checked) date. The lists above only show where to look.")
    if datas:
        out["atualizado"] = max(datas)
    novo = sem_mudar_data(out, destino)
    salvar_json(destino, novo)
    return out


# ---------------------------------------------------------------------------------------------------- manter o que valia
MANTER_PUBLICADO_DIAS = 90   # o bloco já publicado vale por este tanto de dias, se a rodada nova achar menos


def _host(u: str | None) -> str:
    h = (urllib.parse.urlsplit(u or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _pontos(parte: str, x: dict) -> int:
    """Quanto um bloco diz: site, sistema, página das proposições (na internet vale mais), pedido de informação..."""
    if parte == "camara":
        return (bool(x.get("site")) + bool(x.get("sistema")) + bool(x.get("propostas"))
                + 2 * (x.get("propostasOnline") is True) + bool(x.get("sic")))
    return (bool(x.get("site")) + (bool(x.get("site")) and x.get("lido") is not False) + bool(x.get("transparencia"))
            + bool(x.get("sic")) + bool(x.get("diarioOficial")))


def _leu(parte: str, x: dict) -> bool:
    """A rodada conseguiu ler o site (não ficou só no endereço, por bloqueio ou erro)."""
    if not x.get("site"):
        return False
    if parte == "camara":
        return x.get("motivo") not in (MOTIVOS["bloqueio"][0], MOTIVOS["fora_do_ar"][0])
    return x.get("lido") is not False


CAMPOS_PROPOSTAS = ("sistema", "plataforma", "api", "propostas", "propostasOnline", "motivo", "motivo_en")


def _so_sapl(x: dict) -> bool:
    """O "site" da Câmara no bloco é só o endereço do SAPL: a rodada não achou (ou não conseguiu ler) o site da Câmara e
    pôs o do sistema de proposições no lugar (montar_cidade)."""
    return (bool(x.get("site")) and x.get("sistema") == "sapl"
            and _host(x["site"]) == _host(x.get("api") or x.get("propostas")))


def _com_sapl(v: dict, n: dict) -> dict:
    """Fica o bloco publicado da Câmara (o site dela e o pedido de informação); as proposições passam a ser as do SAPL só
    quando ele tem a legislatura atual e o publicado não tinha proposições na internet."""
    if n.get("propostasOnline") is not True or v.get("propostasOnline") is True:
        return v
    out = {k: x for k, x in v.items() if k not in CAMPOS_PROPOSTAS}
    out.update({k: n[k] for k in CAMPOS_PROPOSTAS if k in n})
    return out


def manter_publicado(novo: dict, velho: dict | None, b: dict) -> dict:
    """O robô do GitHub roda fora do Brasil, e muitos sites de prefeituras e Câmaras bloqueiam esse acesso (ou demoram);
    ele também pode começar com o cache vazio. Por isso, um bloco já publicado em dados/municipios/ (Câmara ou prefeitura)
    só é trocado quando a rodada nova achou pelo menos o mesmo tanto (_pontos), quando o site mudou de endereço e o novo foi
    lido, quando o endereço publicado não existe mais (erro de DNS), quando o publicado tem mais de MANTER_PUBLICADO_DIAS
    dias ou quando o endereço publicado é de outra cidade (alheio). Se a rodada nova só achou o SAPL da Câmara (e o pôs
    como site), o site e o pedido de informação publicados continuam, e as proposições do SAPL entram se forem melhores
    (_com_sapl). Senão fica o bloco publicado, com a data em que foi conferido."""
    if not velho:
        return novo
    limite = (dt.date.fromisoformat(hoje()) - dt.timedelta(days=MANTER_PUBLICADO_DIAS)).isoformat()
    uf, ibge = b.get("uf"), b.get("ibge")
    for parte in ("camara", "prefeitura"):
        n, v = novo.get(parte) or {}, velho.get(parte) or {}
        if not v.get("site") or (v.get("conferido") or "") < limite or alheio(v["site"], uf, ibge):
            continue
        h = _host(v["site"])
        if any(x.get("erro") == "dns" and _host("https://" + (x.get("host") or "")) == h
               for x in (b.get(parte) or {}).get("visitas") or []):
            continue
        if parte == "camara" and _so_sapl(n) and not _so_sapl(v):
            novo[parte] = _com_sapl(v, n)
            continue
        if _pontos(parte, n) >= _pontos(parte, v):
            continue
        if n.get("site") and _host(n["site"]) != h and _leu(parte, n):
            continue
        novo[parte] = v
    return novo


def juntar_com_antigo(novo: dict, antigo: dict | None) -> dict:
    """Se o site não abriu agora (fora do ar, tempo esgotado) mas abriu há pouco, vale o que foi conferido antes. Não volta
    um site que esta rodada abriu e viu que não é da cidade, nem um com o nome de outra cidade (alheio)."""
    if not antigo:
        return novo
    limite = (dt.date.fromisoformat(hoje()) - dt.timedelta(days=MANTER_DIAS)).isoformat()
    for parte in ("camara", "prefeitura"):
        n, a = novo.get(parte) or {}, antigo.get(parte) or {}
        if n.get("site") or not a.get("site") or (a.get("conferido") or "") < limite:
            continue
        h = _host(a["site"])
        if alheio(a["site"], novo.get("uf"), novo.get("ibge")) or any(
                x.get("ok") is False and not x.get("erro") and _host("https://" + (x.get("host") or "")) == h
                for x in n.get("visitas") or []):
            continue
        erros = [x.get("erro") for x in n.get("visitas") or []]
        transitorio = any(e in ("timeout", "conexao", "tls", "redirecionamentos", "suspenso", "http 403", "http 429")
                          or (e or "").startswith("http 5") for e in erros) or any(
            x.get("erro") == "robots" and x.get("robots") == "nada" for x in n.get("visitas") or []) or not erros
        if transitorio:
            a = dict(a)
            a["mantido"] = hoje()
            a["visitasHoje"] = n.get("visitas")
            novo[parte] = a
    return novo


def salvar_bruto(b: dict):
    arq = PASTA_CIDADES / b["uf"] / f"{b['ibge']}.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(b, ensure_ascii=False, default=list), encoding="utf-8")


def precisa(ibge: str, uf: str, dias: float) -> bool:
    arq = PASTA_CIDADES / uf / f"{ibge}.json"
    if not arq.exists():
        return True
    b = ler_json(arq) or {}
    if b.get("versao") != VERSAO:
        return True
    try:
        idade = (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(b.get("data") or "2000-01-01")).days
    except ValueError:
        return True
    return idade >= dias


def grupos_rodizio(cidades: list) -> list[list[str]]:
    """7 grupos de estados com tamanhos parecidos (um por dia da semana)."""
    n = {}
    for _, _, uf in cidades:
        n[uf] = n.get(uf, 0) + 1
    grupos = [[] for _ in range(7)]
    soma = [0] * 7
    for uf in sorted(n, key=lambda u: (-n[u], u)):
        i = soma.index(min(soma))
        grupos[i].append(uf)
        soma[i] += n[uf]
    grupos[min(range(7), key=lambda i: soma[i])].append("DF")
    return grupos


# ---------------------------------------------------------------------------------------------------- principal
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ufs", nargs="*")
    ap.add_argument("--dias", type=float, default=6)
    ap.add_argument("--paralelo", type=int, default=16)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--montar", action="store_true")
    ap.add_argument("--rodizio", action="store_true")
    ap.add_argument("--ibge")
    ap.add_argument("--embaralhar", action="store_true", help="ordem aleatória (amostras)")
    ap.add_argument("--so-faltando", action="store_true",
                    help="confere de novo só as cidades sem site da Câmara ou da prefeitura no cache (mesmo se recentes)")
    ap.add_argument("--marcas", action="store_true",
                    help="só completa as marcas do fornecedor das Câmaras (rodadas antigas) e remonta")
    ap.add_argument("--diarios", action="store_true",
                    help="só confere em que Diário de associação cada cidade publica (cache de 30 dias) e remonta")
    a = ap.parse_args()

    cidades = ler_json(DADOS / "cidades.json", []) or []
    nomes = F.Nomes(cidades)
    preparar_slugs(cidades)
    if a.rodizio:
        ufs = grupos_rodizio(cidades)[dt.date.fromisoformat(hoje()).weekday()]
    elif a.ibge:
        ufs = [nomes.nome[a.ibge][1]]
    else:
        ufs = [u.upper() for u in a.ufs] or UFS
    for u in ufs:
        if u not in UFS:
            ap.error(f"estado desconhecido: {u}")

    rede = _rede.Rede()
    t_ini = time.time()
    if a.montar:
        F.SO_CACHE = True
    sigi, f_sigi = F.sigi(rede, nomes)
    sp, f_sp = F.sigpub(rede, nomes, set(ufs))
    am, f_am = F.assomasul(rede, nomes) if "MS" in ufs else ({}, [])
    amt, f_amt = F.amm_mt(rede, nomes) if "MT" in ufs else ({}, [])
    f_ciga = []
    if "SC" in ufs:
        cons, cams, f_ciga = F.ciga(rede, nomes)
        CIGA_CONSORCIADOS.update(cons)
        for ibge, link in cams.items():
            sigi.setdefault(ibge, {"leg": [], "gov": [], "portal": None, "sapl": [], "email": None})["ciga"] = link
    diarios = {}
    for d in (sp, am, amt):
        for k, v in d.items():
            diarios.setdefault(k, []).extend(v)
    nomes_assoc = {}
    for lst in sp.values():
        for x in lst:
            nomes_assoc[x["assoc"]] = x["nome"]
    fontes_base = []
    if f_sigi:
        fontes_base.append(f_sigi)
    for f in f_sp:
        uf_f = next((u for s, u in F.SIGPUB.items() if f"/{s}/" in f["url"]), None)
        fontes_base.append(dict(f, uf=uf_f))
    for f in f_am:
        fontes_base.append(dict(f, uf="MS"))
    for f in f_amt:
        fontes_base.append(dict(f, uf="MT"))
    for f in f_ciga:
        fontes_base.append(dict(f, uf="SC"))

    if a.ibge:
        c = next(x for x in cidades if x[0] == a.ibge)
        curtos = nomes_curtos(cidades)
        with cf.ThreadPoolExecutor(32) as dns_pool:
            b = mapear_cidade(rede, dns_pool, tuple(c), sigi, curtos.get(c[0]))
        b = juntar_com_antigo(b, ler_json(PASTA_CIDADES / c[2] / f"{c[0]}.json"))
        salvar_bruto(b)
        for h in sapl_pendentes([b], sigi):
            F.sapl_testar(rede, h)
        for x in diarios.get(c[0]) or []:
            print("atividade", x["assoc"], F.atividade(rede, x["assoc"], x["entidade"]))
        print(json.dumps({k: v for k, v in b.items()}, ensure_ascii=False, indent=1, default=str)[:6000])
        print(json.dumps(montar_cidade(b, sigi, diarios, nomes_assoc), ensure_ascii=False, indent=1))
        return 0

    curtos = nomes_curtos(cidades)
    rodadas = ler_json(RODADAS, {}) or {}
    if a.diarios:
        for uf in ufs:
            lista = [tuple(c) for c in cidades if c[2] == uf]
            ents = [x for c in lista for x in diarios.get(c[0]) or []]
            t0 = time.time()
            for x in ents:   # um site por associação, um pedido por vez
                F.atividade(rede, x["assoc"], x["entidade"])
            log(f"{uf}: Diários das associações conferidos para {len(ents)} entidades ({time.time() - t0:.0f} s)")
            montar_uf(uf, lista, sigi, diarios, nomes_assoc, fontes_base)
        log(f"fim: {time.time() - t_ini:.0f} s, {rede.pedidos} pedidos")
        return 0
    if a.marcas:
        for uf in ufs:
            lista = [tuple(c) for c in cidades if c[2] == uf]
            brutos = [ler_json(PASTA_CIDADES / uf / f"{c[0]}.json") for c in lista]
            brutos = [b for b in brutos if b and (b.get("camara") or {}).get("site")]
            t0 = time.time()
            with cf.ThreadPoolExecutor(a.paralelo) as ex:
                for b, mudou in zip(brutos, ex.map(lambda b: completar_marcas(rede, b), brutos)):
                    if mudou:
                        salvar_bruto(b)
            log(f"{uf}: marcas de {len(brutos)} Câmaras ({time.time() - t0:.0f} s)")
            montar_uf(uf, lista, sigi, diarios, nomes_assoc, fontes_base)
        log(f"fim: {time.time() - t_ini:.0f} s, {rede.pedidos} pedidos")
        return 0
    # Em segundo plano, para não segurar a rodada: (1) os Diários das associações (um site só, um pedido por vez);
    # (2) os SAPL novos pela API (o robots.txt do SAPL pede 60 s entre pedidos; cada um num servidor diferente)
    fila_ativ: "queue.Queue" = queue.Queue()
    fio_ativ = threading.Thread(target=_trabalhar_atividade, args=(rede, fila_ativ), daemon=True)
    fio_ativ.start()
    pool_sapl = cf.ThreadPoolExecutor(32)
    sapl_pedidos: set = set()
    feitos_uf: list[str] = []

    def mostrar(uf, res, lista):
        n = len(res["cidades"])
        cs = sum(1 for x in res["cidades"].values() if x["camara"]["site"])
        on = sum(1 for x in res["cidades"].values() if x["camara"]["propostasOnline"])
        ps = sum(1 for x in res["cidades"].values() if x["prefeitura"]["site"])
        do = sum(1 for x in res["cidades"].values() if x["prefeitura"]["diarioOficial"])
        log(f"{uf}: {n}/{len(lista)} no mapa; Câmara com site {cs}, proposições na internet {on}; "
            f"prefeitura com site {ps}; Diário Oficial ligado {do}")

    for uf in ufs:
        lista = [tuple(c) for c in cidades if c[2] == uf]
        if not a.montar and uf != "DF":
            if a.so_faltando:
                fila = [c for c in lista if _falta_site(c)]
            else:
                fila = [c for c in lista if precisa(c[0], uf, a.dias)]
            if a.embaralhar:
                random.shuffle(fila)
            if a.max:
                fila = fila[:a.max]
            t0 = time.time()
            ped0 = rede.pedidos
            log(f"{uf}: {len(lista)} cidades, {len(fila)} para conferir agora")
            for c in fila:
                for x in diarios.get(c[0]) or []:
                    fila_ativ.put(x)
            with cf.ThreadPoolExecutor(48) as dns_pool, cf.ThreadPoolExecutor(a.paralelo) as ex:
                futuros = {ex.submit(mapear_cidade, rede, dns_pool, c, sigi, curtos.get(c[0])): c for c in fila}
                for i, fut in enumerate(cf.as_completed(futuros), 1):
                    c = futuros[fut]
                    try:
                        b = fut.result()
                    except Exception as e:  # um site estranho não para a rodada
                        log(f"  {c[0]} {c[1]}: erro {type(e).__name__}: {str(e)[:120]}")
                        continue
                    b = juntar_com_antigo(b, ler_json(PASTA_CIDADES / uf / f"{c[0]}.json"))
                    salvar_bruto(b)
                    for h in sapl_pendentes([b], sigi):
                        if h not in sapl_pedidos:
                            sapl_pedidos.add(h)
                            pool_sapl.submit(F.sapl_testar, rede, h)
                    if i % 50 == 0 or i == len(fila):
                        susp = f", {len(rede.suspensos)} servidor(es) deixado(s) em paz" if rede.suspensos else ""
                        log(f"  {uf}: {i}/{len(fila)} ({time.time() - t0:.0f} s, {rede.pedidos - ped0} pedidos{susp})")
            seg = round(time.time() - t0)
            rodadas.setdefault(uf, []).append({"data": hoje(), "cidades": len(fila), "segundos": seg,
                                               "pedidos": rede.pedidos - ped0})
            rodadas[uf] = rodadas[uf][-10:]
            salvar_json(RODADAS, rodadas, indentado=True)
            feitos_uf.append(uf)
        res = montar_uf(uf, lista, sigi, diarios, nomes_assoc, fontes_base)
        mostrar(uf, res, lista)
    if not a.montar:
        log(f"esperando as conferências em segundo plano (Diários das associações: {fila_ativ.qsize()} na fila; "
            f"SAPL: {len(sapl_pedidos)} pedidos)")
        fila_ativ.join()
        pool_sapl.shutdown(wait=True)
        for uf in feitos_uf:   # remonta com o que as conferências em segundo plano acharam
            lista = [tuple(c) for c in cidades if c[2] == uf]
            mostrar(uf, montar_uf(uf, lista, sigi, diarios, nomes_assoc, fontes_base), lista)
    log(f"fim: {time.time() - t_ini:.0f} s, {rede.pedidos} pedidos")
    if rede.suspensos:
        log(f"servidores deixados em paz nesta rodada (pararam de responder ou recusaram): {len(rede.suspensos)} — "
            + ", ".join(f"{ip} ({m})" for ip, m in list(rede.suspensos.items())[:20]))
        salvar_json(PASTA / "suspensos.json", {"data": hoje(), "servidores": rede.suspensos}, indentado=True)
    return 0


def _falta_site(c: tuple) -> bool:
    b = ler_json(PASTA_CIDADES / c[2] / f"{c[0]}.json")
    if not b:
        return True
    return not (b.get("camara") or {}).get("site") or not (b.get("prefeitura") or {}).get("site")


def completar_marcas(rede: _rede.Rede, b: dict) -> bool:
    """Para rodadas feitas antes das "marcas" do fornecedor: abre de novo a página inicial da Câmara e a página de
    proposições que contou, e guarda as marcas (gerador, rodapé, domínios dos scripts). Devolve True se mudou."""
    cam = b.get("camara") or {}
    if not cam.get("site"):
        return False
    boas = [pp for pp in cam.get("propostasPaginas") or [] if pp.get("evidencia") in ("recentes", "antigas", "navegador")]
    if not boas:
        return False    # o fornecedor só aparece no mapa quando a Câmara tem um sistema "outro"
    mudou = False
    if "marcas" not in cam:
        v = visitar(rede, cam.get("final") or cam["site"])
        if v["pagina"] is not None:
            cam["marcas"] = P.marcas(v["pagina"])
            mudou = True
    for pp in cam.get("propostasPaginas") or []:
        if pp.get("evidencia") in ("recentes", "antigas", "navegador") and "marcas" not in pp:
            v = visitar(rede, pp.get("link") or pp["url"])
            if v["pagina"] is not None:
                pp["marcas"] = P.marcas(v["pagina"])
                pp["fornecedor"] = P.fornecedor(v["pagina"])
                mudou = True
            break
    return mudou


def _trabalhar_atividade(rede, fila):
    while True:
        x = fila.get()
        try:
            F.atividade(rede, x["assoc"], x["entidade"])
        except Exception as e:
            log(f"  [diário] {x.get('assoc')} {x.get('entidade')}: {type(e).__name__}: {str(e)[:80]}")
        finally:
            fila.task_done()


if __name__ == "__main__":
    sys.exit(main())
