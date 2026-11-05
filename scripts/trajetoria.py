"""Trajetória de cada pessoa com perfil no site: todas as candidaturas no TSE desde 1994 (ganhou, perdeu, suplente), com
o resultado de cada uma, os mandatos que a pessoa exerceu e, onde há dado oficial, o que ela fez em cada mandato.

Grava dados/trajetoria/<00-ff>.json (256 "baldes": o perfil abre só o balde da pessoa; o número do balde sai do id, com a
mesma conta em Python e em JavaScript, `balde()` aqui e em js/trajetoria.js). Um arquivo por pessoa passaria do limite
de arquivos da Vercel (são ~75 mil perfis, contando vereadores, prefeitos e vices).

Quem entra: todo perfil do site — presidente e vice (pres-, vp-), senadores (sen-), deputados federais (dep-),
governadores e vices (gov-, vgov-), deputados estaduais e distritais (dest-), prefeitos e vices (pref-, vpref-),
vereadores (ver-), eleitos em 2026 sem cargo hoje (e26-) e os ministros do STF (stf-: eles não são eleitos para o STF,
mas alguns já concorreram a outros cargos). Ministros de Estado (min-): a lista oficial não traz o nome completo nem a
data de nascimento, então não dá para ligar as eleições com segurança; a trajetória deles mostra só o cargo de hoje.

Ligação entre eleições (a mesma régua para todos; nunca só pelo nome):
  1. CPF, quando os dois lados têm CPF válido (o TSE escreve "-4" quando não divulga: 1994, 1996 e 2024 não têm);
  2. número do título de eleitor, quando os dois lados têm (2000 em diante; nunca sai do cache) e o nascimento também
     bate (ou o nome bate e o nascimento difere em um só algarismo, ou com dia e mês trocados: erro de digitação);
  3. nome civil + data de nascimento, exatos (maiúsculas, sem acento e sem pontuação), só quando não há conflito:
     se o mesmo nome + nascimento aparece com dois CPFs (ou dois títulos) diferentes, são pessoas diferentes e as
     linhas sem CPF/título desse nome ficam de fora (vão para a lista de conferência do log).
  Nos arquivos de 1994 e 1996, o nome vem cortado em 30 letras: aí vale o começo do nome + a data de nascimento.
Casos duvidosos (mesmo nome e nascimento diferente, ou mesmo nome e nascimento com pessoas diferentes) não entram e
vão para .cache/trajetoria/conferir.txt.

Mandatos exercidos que não vêm do TSE: Câmara dos Deputados (quem exerceu em cada legislatura desde 1987, inclusive
suplentes que assumiram; propostas de cada legislatura pelos arquivos anuais de proposições e autores) e Senado
(mandatos e exercícios de cada senador; propostas apresentadas no Senado em cada mandato). Para vice que assumiu e
suplente em exercício nas Assembleias e Câmaras Municipais: o que as fichas do site já dizem, com as fontes delas.

Fontes: TSE (Dados Abertos: candidaturas e votação nominal por município e zona de cada eleição; DivulgaCandContas
para o link de cada candidatura de 2004 em diante), Câmara dos Deputados (Dados Abertos), Senado Federal (Dados Abertos).

Uso:
    python scripts/trajetoria.py              # tudo (sem o cache, baixa as candidaturas e os votos de 1994 a 2020, ~2 GB,
                                              # que viram um índice de ~280 MB em .cache/trajetoria/ e são apagados)
    python scripts/trajetoria.py --cache      # sem rede: só o que já está em .cache/
    python scripts/trajetoria.py --id dep-204379 sen-5672   # mostra a trajetória de algumas pessoas (não grava)
    python scripts/trajetoria.py --forcar     # grava mesmo se a rodada achar bem menos que a publicada (a trava, abaixo)
No robô diário, depois do montar.py: quem tem perfil muda (listas oficiais, suplentes, posses) e as eleições novas entram;
com o cache .cache/trajetoria, leva ~1,5 min. Trava: se a rodada tiver menos de 97% dos itens ou dos mandatos publicados
(cache faltando, Câmara ou Senado fora do ar), nada é gravado e fica o que está publicado.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import *  # noqa: E402,F401
import ibge  # noqa: E402
import mandatos  # noqa: E402
from tse import cpf_valido, membros_csv  # noqa: E402

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
PORTAL = "https://dadosabertos.tse.jus.br/dataset/"
DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_ARQ = "https://dadosabertos.camara.leg.br/arquivos"
SENADO_API = "https://legis.senado.leg.br/dadosabertos"
CT = CACHE / "trajetoria"
CACHE_TSE = CACHE / "tse"
SAIDA = DADOS / "trajetoria"
N_BALDES = 256
ANOS = list(range(1994, 2027, 2))
GERAIS = set(range(1994, 2027, 4))
VERSAO_INDICE = 1
SEM_REDE = False

# o id de cada eleição ordinária no DivulgaCandContas (lido de /rest/v1/eleicao/ordinarias em 30/10/2026; de 2004 em diante)
ID_DIVULGA = {2004: "14431", 2006: "14423", 2008: "14422", 2010: "14417", 2012: "1699", 2014: "680", 2016: "2",
              2018: "2022802018", 2020: "2030402020", 2022: "2040602022", 2024: "2045202024", 2026: "20322002026"}

# cargo do TSE -> código curto
CARGO = {"PRESIDENTE": "pres", "VICE-PRESIDENTE": "vp", "GOVERNADOR": "gov", "VICE-GOVERNADOR": "vgov", "SENADOR": "sen",
         "1º SUPLENTE": "s1", "1º SUPLENTE SENADOR": "s1", "2º SUPLENTE": "s2", "2º SUPLENTE SENADOR": "s2",
         "DEPUTADO FEDERAL": "dep", "DEPUTADO ESTADUAL": "dest", "DEPUTADO DISTRITAL": "ddist", "PREFEITO": "pref",
         "VICE-PREFEITO": "vpref", "VEREADOR": "ver"}
VICES = {"vp": "pres", "vgov": "gov", "vpref": "pref", "s1": "sen", "s2": "sen"}  # cargo de chapa -> cargo do titular
TITULAR_TSE = {"pres": "PRESIDENTE", "gov": "GOVERNADOR", "pref": "PREFEITO", "sen": "SENADOR"}
SEM_VICE_LIGADO = {1994, 1996, 1998}  # o TSE não liga o vice à chapa (scripts/historico.py)
CORTADOS = {1994, 1996}               # nome civil cortado em 30 letras

CAMPOS = ("el", "ord", "turno", "dt", "uf", "ue", "nm_ue", "cargo", "sq", "num", "nome", "urna", "partido", "sit",
          "sitc", "det", "cpf", "tit", "nasc", "g", "nk", "sk", "mk")
I = {c: i for i, c in enumerate(CAMPOS)}


def _limpo(s) -> str:
    s = limpa(s) or ""
    return "" if s.startswith("#") else s.replace("\t", " ")


def titulo_valido(s: str | None) -> str | None:
    s = (s or "").strip()
    if not s or s.startswith(("-", "#")):
        return None
    d = re.sub(r"\D", "", s)
    return (d.lstrip("0") or None) if d and int(d) > 0 else None


def chave_nn(nome: str | None, nasc: str | None) -> str:
    k = chave_nome(nome or "")
    return f"{k}|{nasc}" if k and nasc else ""


def chave_corte(nome: str | None, nasc: str | None) -> str:
    """Nome civil cortado em 30 letras (1994 e 1996) + nascimento."""
    k = chave_nome((nome or "")[:30])
    return f"{k}|{nasc}" if k and nasc else ""


# ---------------------------------------------------------------- índice compacto das candidaturas (cache)
def zip_cand(ano: int) -> Path:
    """O zip das candidaturas: o que o tse.py/historico.py já guardou em .cache/tse/; senão, baixa para .cache/trajetoria/
    (apagado depois de virar índice, para não engordar o cache do robô)."""
    p = CACHE_TSE / f"consulta_cand_{ano}.zip"
    if p.exists() and p.stat().st_size > 0:
        return p
    if SEM_REDE:
        raise RuntimeError(f"sem rede (--cache): {p.name} não está no cache")
    return baixar_arquivo(f"{CDN}consulta_cand/{p.name}", f"trajetoria/{p.name}", max_idade_h=None, timeout=900)


def indice(ano: int) -> Path:
    """.cache/trajetoria/cand_<ano>.tsv.gz: todas as candidaturas do ano, só as colunas usadas (refeito se o zip mudar).
    Sem o zip no cache (ex.: no robô, que guarda só o índice), vale o índice que já existe: o passado não muda."""
    destino = CT / f"cand_{ano}.tsv.gz"
    meta = ler_json(CT / "cand_meta.json", {}) or {}
    if destino.exists() and str(ano) in meta and not (CACHE_TSE / f"consulta_cand_{ano}.zip").exists():
        return destino
    z = zip_cand(ano)
    if destino.exists() and destino.stat().st_mtime >= z.stat().st_mtime and str(ano) in meta:
        with gzip.open(destino, "rt", encoding="utf-8") as f:
            cab = json.loads(f.readline())
        if cab.get("versao") == VERSAO_INDICE:
            return destino
    t = time.time()
    CT.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".part")
    data, n = None, 0
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=5) as out:
        out.write(json.dumps({"versao": VERSAO_INDICE, "ano": ano}) + "\n")

        class _L:
            @staticmethod
            def append(l):
                out.write("\t".join(x.replace("#", "") if x.startswith("#") else x for x in l) + "\n")
        linhas = _L()
        with zipfile.ZipFile(z) as zz:
            for nome in membros_csv(zz):
                with zz.open(nome) as f:
                    for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                        cargo = (r.get("DS_CARGO") or "").upper().strip()
                        if cargo not in CARGO:
                            continue
                        data = data or data_iso(r.get("DT_GERACAO"))
                        nasc = data_iso(r.get("DT_NASCIMENTO")) or ""
                        nome_c = _limpo(r.get("NM_CANDIDATO"))
                        social = _limpo(r.get("NM_SOCIAL_CANDIDATO"))
                        if social and "DIVULG" in sem_acento(social).upper():
                            social = ""
                        g = (r.get("DS_GENERO") or "").upper()
                        linhas.append((
                            r["CD_ELEICAO"], "1" if "ORDIN" in sem_acento(r.get("NM_TIPO_ELEICAO") or "").upper() else "0",
                            str(int(r.get("NR_TURNO") or 1)), data_iso(r.get("DT_ELEICAO")) or "", r["SG_UF"], r["SG_UE"],
                            _limpo(r.get("NM_UE")), cargo, r["SQ_CANDIDATO"], _limpo(r.get("NR_CANDIDATO")), nome_c,
                            _limpo(r.get("NM_URNA_CANDIDATO")), _limpo(r.get("SG_PARTIDO")),
                            (r.get("DS_SIT_TOT_TURNO") or "").upper().strip(),
                            (r.get("DS_SITUACAO_CANDIDATURA") or "").upper().strip(),
                            (r.get("DS_DETALHE_SITUACAO_CAND") or "").upper().strip(),
                            cpf_valido(r.get("NR_CPF_CANDIDATO")) or "", titulo_valido(r.get("NR_TITULO_ELEITORAL_CANDIDATO")) or "",
                            nasc, "F" if g.startswith("FEM") else "M" if g.startswith("MASC") else "",
                            chave_nn(nome_c, nasc), chave_nn(social, nasc) if social else "",
                            chave_corte(nome_c, nasc) if ano in CORTADOS and len(nome_c) >= 30 else ""))
                        n += 1
    os.replace(tmp, destino)
    if z.parent == CT:
        z.unlink()  # baixado só para o índice
    meta = ler_json(CT / "cand_meta.json", {}) or {}
    meta[str(ano)] = data
    salvar_json(CT / "cand_meta.json", dict(sorted(meta.items())), indentado=True)
    log(f"  índice {ano}: {n} candidaturas ({time.time() - t:.0f}s)")
    return destino


def ler_indice(ano: int):
    """(cabeçalho, gerador de linhas já separadas)."""
    p = indice(ano)
    f = gzip.open(p, "rt", encoding="utf-8")
    cab = json.loads(f.readline())

    def linhas():
        with f:
            for l in f:
                yield l.rstrip("\n").split("\t")
    return cab, linhas()


# ---------------------------------------------------------------- votos (votação nominal por município e zona)
def votos(ano: int) -> dict:
    """{"data", "votos": {"UF|SQ|turno" ou "SQ|turno": votos}}. 2018, 2022 e 2024 vêm do resumo do scripts/tse.py; 2026, do
    scripts/eleitos.py; os outros anos são baixados uma vez, somados aqui e apagados (o resumo fica no cache)."""
    for p in (CACHE_TSE / f"votos_{ano}.json", CACHE / "eleitos" / f"votos_{ano}.json", CT / f"votos_{ano}.json"):
        if p.exists():
            return ler_json(p) or {"data": None, "votos": {}}
    if SEM_REDE:
        log(f"  [aviso] votos de {ano}: sem rede (--cache) e sem resumo no cache; as candidaturas de {ano} saem sem votos")
        return {"data": None, "votos": {}}
    nome = f"votacao_candidato_munzona_{ano}.zip"
    try:
        z = baixar_arquivo(f"{CDN}votacao_candidato_munzona/{nome}", f"trajetoria/{nome}", max_idade_h=None, timeout=900)
    except Exception as e:  # noqa: BLE001
        log(f"  [aviso] votos de {ano}: o TSE não respondeu ({e}); as candidaturas de {ano} saem sem votos")
        return {"data": None, "votos": {}}
    t = time.time()
    soma, data = collections.Counter(), None
    with zipfile.ZipFile(z) as zz:
        for nm in membros_csv(zz):
            with zz.open(nm) as f:
                for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                    data = data or data_iso(r.get("DT_GERACAO"))
                    v = r.get("QT_VOTOS_NOMINAIS_VALIDOS")
                    if v is None or v == "" or v.startswith("#"):
                        v = r.get("QT_VOTOS_NOMINAIS") or "0"
                    try:
                        # o SQ_CANDIDATO dos arquivos antigos só é único dentro da UE (município, estado ou BR)
                        soma[f"{r['SG_UE']}|{r['SQ_CANDIDATO']}|{int(r['NR_TURNO'] or 1)}"] += int(v)
                    except ValueError:
                        pass
    d = {"data": data, "chave": "ue", "votos": dict(soma)}
    salvar_json(CT / f"votos_{ano}.json", d)
    z.unlink()
    log(f"  votos {ano}: {len(soma)} candidaturas somadas ({time.time() - t:.0f}s); o arquivo grande foi apagado")
    return d


def votos_de(vot: dict, ue: str, uf: str, sq: str, turno: int) -> int | None:
    """Os votos de uma candidatura num turno. Chaves: "UE|SQ|turno" (resumos feitos aqui, novos), "UF|SQ|turno" (resumos
    daqui feitos antes, só eleições gerais: UF = estado, BR = presidente) ou "SQ|turno" (resumos do tse.py e do eleitos.py)."""
    v = vot.get("votos") or {}
    for k in ((f"{ue}|{sq}|{turno}", f"{sq}|{turno}") if vot.get("chave") == "ue" else (f"{uf}|{sq}|{turno}", f"{sq}|{turno}")):
        if k in v:
            return v[k]
    return None


# ---------------------------------------------------------------- quem tem perfil no site
def _sq_da_url(p: dict, ano: int) -> str | None:
    """O número da candidatura (SQ_CANDIDATO) no endereço da foto ou da página do DivulgaCandContas da ficha (o da eleição
    ordinária ou o de uma suplementar: nos dados abertos modernos o SQ não se repete)."""
    urls = [p.get("foto") or ""] + [f.get("url") or "" for f in (p.get("fontes") or []) if isinstance(f, dict)]
    for u in urls:
        m = (re.search(r"/rest/arquivo/img/\d+/(\d{6,})/", u) or re.search(rf"/candidato/[A-Z]+/[A-Z]{{2}}/\d+/(\d{{6,}})/{ano}/", u))
        if m:
            return m.group(1)
    return None


def _pessoa(pid: str, tipo: str, nome, nome_civil, nasc, uf, **extra) -> dict:
    d = {"id": pid, "tipo": tipo, "nome": nome, "nomeCivil": nome_civil, "nasc": nasc, "uf": uf, "cpf": None,
         "seeds": set(), "esperado": None, "hoje": None, "assumiu": None}
    d.update(extra)
    if nome_civil and nasc:
        d["seeds"].add("N" + chave_nn(nome_civil, nasc))
    return d


def pessoas_do_site() -> list[dict]:
    """Todo mundo que tem perfil no site hoje, com o que serve para achar a pessoa nos dados do TSE."""
    out = []
    # deputados federais (CPF, nome civil e nascimento da API da Câmara, guardados pelo scripts/tse.py)
    for m in (ler_json(DADOS / "camara.json") or {}).get("membros") or []:
        i = str(m["id"]).replace("dep-", "")
        det = (ler_json(CACHE_TSE / "camara" / f"{i}.json") or {}).get("dados") or {}
        if not isinstance(det, dict):
            det = {}
        perf = ler_json(PESSOAS / f"dep-{i}.json") or {}
        p = _pessoa(f"dep-{i}", "dep", m.get("nome"), limpa(det.get("nomeCivil")) or perf.get("nomeCivil"),
                    data_iso(det.get("dataNascimento")) or perf.get("nascimento"), m.get("uf"), camara=i,
                    esperado={"c": {"dep"}, "uf": m.get("uf")})
        p["cpf"] = cpf_valido(det.get("cpf"))
        if p["cpf"]:
            p["seeds"].add("C" + p["cpf"])
        out.append(p)
    # senadores (nome completo e nascimento da API do Senado)
    for m in (ler_json(DADOS / "senado.json") or {}).get("membros") or []:
        cod = str(m["id"]).replace("sen-", "")
        det = ((ler_json(CACHE_TSE / "senado" / f"{cod}.json") or {}).get("DetalheParlamentar") or {}).get("Parlamentar") or {}
        ident = det.get("IdentificacaoParlamentar") or {}
        perf = ler_json(PESSOAS / f"sen-{cod}.json") or {}
        out.append(_pessoa(f"sen-{cod}", "sen", m.get("nome"), limpa(ident.get("NomeCompletoParlamentar")) or perf.get("nomeCivil"),
                           data_iso((det.get("DadosBasicosParlamentar") or {}).get("DataNascimento")) or perf.get("nascimento"),
                           m.get("uf"), senado=cod, esperado={"c": {"sen", "s1", "s2"}, "uf": m.get("uf")}))
    # presidente e vice: quem foi eleito na eleição do mandato em curso, se o nome confere (a mesma régua do scripts/tse.py:
    # a data de nascimento do Planalto e a do TSE podem ser diferentes, como a do presidente: 27 e 6 de outubro de 1945)
    from tse import _mesmo_nome
    ex = ler_json(DADOS / "executivo.json") or {}
    a_pres = mandatos.vigente("presidente")["eleicao"]
    _, linhas_p = ler_indice(a_pres)
    eleitos_p = [f for f in linhas_p if f[I["cargo"]] in ("PRESIDENTE", "VICE-PRESIDENTE") and f[I["sit"]].startswith("ELEITO")]
    for chave, tipo, c, cargo_tse in (("presidente", "pres", "pres", "PRESIDENTE"), ("vice", "vp", "vp", "VICE-PRESIDENTE")):
        r = ex.get(chave) or {}
        if not r.get("id"):
            continue
        perf = ler_json(PESSOAS / f"{r['id']}.json") or {}
        p = _pessoa(r["id"], tipo, r.get("nome"), perf.get("nomeCivil"), perf.get("nascimento"), "BR",
                    esperado={"c": {c}, "uf": "BR"})
        el = [f for f in eleitos_p if f[I["cargo"]] == cargo_tse and _mesmo_nome(r.get("nome") or "", f"{f[I['urna']]} {f[I['nome']]}")]
        if len({f[I["sq"]] for f in el}) == 1:
            p["seeds"].add(f"S{a_pres}|{el[0][I['sq']]}")
        out.append(p)
    # governadores, vices e deputados estaduais
    for f in sorted((DADOS / "estados").glob("*.json")):
        est = ler_json(f) or {}
        uf = est.get("uf") or f.stem
        for papel, tipo in (("governador", "gov"), ("vice", "vgov")):
            g = est.get(papel) or {}
            if not g.get("id") or not g.get("nome"):
                continue
            p = _pessoa(g["id"], tipo, g.get("nome"), g.get("nomeCivil"), g.get("nascimento"), uf,
                        esperado={"c": {tipo}, "uf": uf}, ficha=g)
            if g.get("sq2022"):
                p["seeds"].add(f"S2022|{g['sq2022']}")
            out.append(p)
        dest = est.get("deputadosEstaduais") or {}
        ano_d = dest.get("eleicao") or 2022
        for m in dest.get("membros") or []:
            mm = re.match(r"dest-[A-Z]{2}-(\d+)$", m.get("id") or "")
            p = _pessoa(m["id"], "dest", m.get("nome"), m.get("nomeCivil"), m.get("nascimento"), uf,
                        esperado={"c": {"dest", "ddist"}, "uf": uf}, ficha=m)
            if mm:
                p["seeds"].add(f"S{ano_d}|{mm.group(1)}")
            out.append(p)
    # prefeitos, vices e vereadores
    for f in sorted((DADOS / "cidades").glob("*/*.json")):
        c = ler_json(f) or {}
        uf, cod = f.parent.name, f.stem
        for papel, tipo in (("prefeito", "pref"), ("vice", "vpref")):
            g = c.get(papel) or {}
            if not g.get("id") or not g.get("nome") or g.get("vago"):
                continue
            p = _pessoa(g["id"], tipo, g.get("nome"), g.get("nomeCivil"), g.get("nascimento"), uf, ibge=cod,
                        esperado={"c": {tipo}, "uf": uf}, ficha=g)
            sq = _sq_da_url(g, 2024)
            if sq:
                p["seeds"].add(f"S2024|{sq}")
            out.append(p)
        for m in (c.get("vereadores") or {}).get("membros") or []:
            mm = re.match(r"ver-\d{7}-(\d+)$", m.get("id") or "")
            p = _pessoa(m["id"], "ver", m.get("nome"), m.get("nomeCivil"), m.get("nascimento"), uf, ibge=cod,
                        esperado={"c": {"ver"}, "uf": uf}, ficha=m)
            if mm:
                p["seeds"].add(f"S2024|{mm.group(1)}")
            out.append(p)
    # eleitos em 2026 sem cargo hoje (perfis e26-): o mesmo eleito aparece no arquivo do estado (completo) e no do Brasil
    e26 = {}
    for f in sorted((DADOS / "eleitos").glob("*.json")):
        def anda(v):
            if isinstance(v, dict):
                if str(v.get("id") or "").startswith("e26-") and v.get("link") == v.get("id"):
                    if v["id"] not in e26 or (v.get("nomeCivil") and not e26[v["id"]].get("nomeCivil")):
                        e26[v["id"]] = v
                for x in v.values():
                    anda(x)
            elif isinstance(v, list):
                for x in v:
                    anda(x)
        anda(ler_json(f))
    vistos = {p["id"] for p in out}
    for pid, v in sorted(e26.items()):
        if pid in vistos:
            continue
        mm = re.match(r"e26-[A-Z]{2}-(\d+)$", pid)
        p = _pessoa(pid, "e26", v.get("nome"), v.get("nomeCivil"), v.get("nascimento"), v.get("uf"), esperado=None, ficha=v)
        if mm:
            p["seeds"].add(f"S2026|{mm.group(1)}")
        out.append(p)
    # ministros do STF (não são eleitos; alguns já concorreram a outros cargos)
    stf = ler_json(DADOS / "stf.json") or {}
    for m in stf.get("ministros") or []:
        out.append(_pessoa(m["id"], "stf", m.get("nome"), m.get("nomeCivil"), m.get("nascimento"), None, ficha=m,
                           fontesStf=stf.get("fontes")))
    # ministros de Estado: sem nome completo e sem nascimento na lista oficial (não dá para ligar com segurança)
    for m in (ler_json(DADOS / "manual" / "ministros.json") or {}).get("ministerios") or []:
        if m.get("nome"):
            out.append(_pessoa(m["id"], "min", m.get("nome"), None, None, "BR", ficha=m))
    return out


if __name__ == "__main__" and "--so-indice" in sys.argv:
    for a in ANOS:
        indice(a)
    for a in ANOS:
        votos(a)
    sys.exit(0)


# ---------------------------------------------------------------- varrer o índice atrás das chaves
VICE_TSE = {"VICE-PRESIDENTE", "VICE-GOVERNADOR", "VICE-PREFEITO", "1º SUPLENTE", "1º SUPLENTE SENADOR", "2º SUPLENTE",
            "2º SUPLENTE SENADOR"}
TIT_DO_VICE = {"VICE-PRESIDENTE": "PRESIDENTE", "VICE-GOVERNADOR": "GOVERNADOR", "VICE-PREFEITO": "PREFEITO",
               "1º SUPLENTE": "SENADOR", "1º SUPLENTE SENADOR": "SENADOR", "2º SUPLENTE": "SENADOR", "2º SUPLENTE SENADOR": "SENADOR"}
TITULARES_TSE = set(TIT_DO_VICE.values())
MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}


def chave_k(ano: int, f: list, cargo: str | None = None) -> str:
    """A chapa: mesmo ano, lugar e número. Na eleição ordinária, o 1º e o 2º turno têm códigos de eleição diferentes (fica
    sem o código); numa suplementar, o código separa uma eleição da outra."""
    ordi = f[I["ord"]] == "1"
    return f"K{ano}|{'o' if ordi else 's' + f[I['el']]}|{f[I['ue']]}|{f[I['num']]}|{cargo or f[I['cargo']]}"


def varrer(chaves: set[str], nomes_d: set[str] | None, ues: dict | None) -> tuple[dict, dict]:
    """Uma passada por todos os anos: as linhas que têm alguma das chaves (C cpf, T título, N nome+nascimento,
    M nome cortado+nascimento, S ano|SQ, K chapa). Em nomes_d (nomes de quem tem perfil), guarda um resumo das linhas com o
    mesmo nome e outro nascimento (para a lista de conferência). Em ues, os municípios de cada ano (TSE -> nome)."""
    achadas, mesmos_nomes = {}, collections.defaultdict(list)
    ic, it, ink, isk, imk, isq, icg, inas, inm = (I[k] for k in ("cpf", "tit", "nk", "sk", "mk", "sq", "cargo", "nasc", "nome"))
    for ano in ANOS:
        _, linhas = ler_indice(ano)
        for n, f in enumerate(linhas):
            como = None
            if f[ic] and "C" + f[ic] in chaves:
                como = "C"
            elif f[it] and "T" + f[it] in chaves:
                como = "T"
            elif f[ink] and "N" + f[ink] in chaves:
                como = "N"
            elif f[isk] and "N" + f[isk] in chaves:
                como = "N"
            elif f[imk] and "M" + f[imk] in chaves:
                como = "M"
            elif f"S{ano}|{f[isq]}" in chaves:
                como = "S"
            elif f[icg] in TITULARES_TSE and chave_k(ano, f) in chaves:
                como = "K"
            if como:
                achadas[(ano, n)] = (f, ano, como)
            if ues is not None and f[icg] in MUNICIPAIS:
                ues.setdefault(ano, {}).setdefault(f[I["ue"]], (f[I["uf"]], f[I["nm_ue"]]))
            if nomes_d:
                k = f[ink].split("|", 1)[0] if f[ink] else chave_nome(f[inm])
                if k in nomes_d and len(mesmos_nomes[k]) < 40:
                    mesmos_nomes[k].append((ano, f[I["uf"]], f[inas], f[icg], bool(f[ic] or f[it]), (ano, n)))
    return achadas, mesmos_nomes


def chaves_da_linha(f: list, ano: int) -> set[str]:
    out = set()
    if f[I["cpf"]]:
        out.add("C" + f[I["cpf"]])
    if f[I["tit"]]:
        out.add("T" + f[I["tit"]])
    for k in ("nk", "sk"):
        if f[I[k]]:
            out.add("N" + f[I[k]])
    if f[I["mk"]]:
        out.add("M" + f[I["mk"]])
    elif ano not in CORTADOS and len(f[I["nome"]]) >= 30 and f[I["nasc"]]:
        out.add("M" + chave_corte(f[I["nome"]], f[I["nasc"]]))
    if f[I["cargo"]] in VICE_TSE:
        out.add(chave_k(ano, f, TIT_DO_VICE[f[I["cargo"]]]))
    return out


def coletar(pessoas: list[dict]) -> tuple[dict, dict, dict]:
    """Todas as linhas que podem ser de alguém com perfil, em passadas sucessivas (as chaves de cada linha achada
    trazem as outras candidaturas da mesma pessoa)."""
    chaves = set().union(*(p["seeds"] for p in pessoas))
    nomes_d = {chave_nome(p["nomeCivil"]) for p in pessoas if p.get("nomeCivil")}
    linhas, ues, mesmos = {}, {}, {}
    novas, passada = set(chaves), 0
    while novas and passada < 5:
        passada += 1
        t = time.time()
        achadas, mn = varrer(novas, nomes_d if passada == 1 else None, ues if passada == 1 else None)
        if passada == 1:
            mesmos = mn
        antes = len(linhas)
        for rid, x in achadas.items():
            if rid not in linhas or (linhas[rid][2] == "K" and x[2] != "K"):
                linhas[rid] = x
        derivadas = set()
        for rid, (f, ano, como) in achadas.items():
            if como != "K":  # a linha do titular da chapa só serve para o resultado do vice
                derivadas |= chaves_da_linha(f, ano)
        novas = derivadas - chaves
        chaves |= novas
        log(f"  passada {passada}: {len(linhas) - antes} linhas novas ({len(linhas)} no total), {len(novas)} chaves novas "
            f"({time.time() - t:.0f}s)")
    return linhas, ues, mesmos


# ---------------------------------------------------------------- quem é quem (ligação)
class Uniao:
    def __init__(self):
        self.pai = {}

    def acha(self, x):
        p = self.pai.setdefault(x, x)
        while p != self.pai.setdefault(p, p):
            self.pai[p] = self.pai[self.pai[p]]
            p = self.pai[p]
        self.pai[x] = p
        return p

    def junta(self, a, b):
        ra, rb = self.acha(a), self.acha(b)
        if ra != rb:
            self.pai[max(ra, rb)] = min(ra, rb)


def quase_igual(a: str, b: str) -> bool:
    """Nascimentos iguais, sem um dos dois, ou diferentes em um só algarismo ou com dia e mês trocados (erro de digitação)."""
    if not a or not b or a == b:
        return True
    if len(a) != len(b):
        return False
    if sum(x != y for x, y in zip(a, b)) == 1:
        return True
    return a[:4] == b[:4] and a[5:7] == b[8:10] and a[8:10] == b[5:7]


def ligar(linhas: dict) -> tuple[Uniao, list]:
    """Junta as linhas da mesma pessoa: CPF e título juntam sempre; nome civil + nascimento só quando não há conflito."""
    u = Uniao()
    por, por_t = collections.defaultdict(list), collections.defaultdict(list)
    proprias = [rid for rid, (_, _, como) in linhas.items() if como != "K"]
    for rid in proprias:
        f, ano, _ = linhas[rid]
        u.acha(rid)
        if f[I["cpf"]]:
            por["C" + f[I["cpf"]]].append(rid)
        if f[I["tit"]]:
            por_t[f[I["tit"]]].append(rid)
    for k, rids in por.items():
        for r in rids[1:]:
            u.junta(rids[0], r)
    # o título junta quando o nascimento bate, ou quando o nome bate e o nascimento difere em um só algarismo (erro de
    # digitação); mesmo título com nascimentos bem diferentes fica separado (pode ser erro de cadastro)
    for rids in por_t.values():
        for i, a in enumerate(rids):
            fa = linhas[a][0]
            for b in rids[i + 1:]:
                fb = linhas[b][0]
                if fa[I["nasc"]] and fa[I["nasc"]] == fb[I["nasc"]] or (
                        chave_nome(fa[I["nome"]]) == chave_nome(fb[I["nome"]]) and quase_igual(fa[I["nasc"]], fb[I["nasc"]])):
                    u.junta(a, b)
    # nome civil + nascimento (e o nome cortado de 1994/1996): só se as linhas com CPF/título forem todas da mesma pessoa
    grupos = collections.defaultdict(set)
    for rid in proprias:
        f, ano, _ = linhas[rid]
        for k in ("nk", "sk"):
            if f[I[k]]:
                grupos["N" + f[I[k]]].add(rid)
        mk = f[I["mk"]] or (chave_corte(f[I["nome"]], f[I["nasc"]]) if ano not in CORTADOS and len(f[I["nome"]]) >= 30 and f[I["nasc"]] else "")
        if mk:
            grupos["M" + mk].add(rid)
    conflitos = []
    for k in sorted(grupos, key=lambda k: (k[0] != "N", k)):  # primeiro o nome inteiro, depois o cortado
        rids = grupos[k]
        fortes = {u.acha(r) for r in rids if linhas[r][0][I["cpf"]] or linhas[r][0][I["tit"]]}
        if len(fortes) <= 1:
            rs = sorted(rids)
            for r in rs[1:]:
                u.junta(rs[0], r)
        else:
            conflitos.append((k, rids))
    return u, conflitos


# ---------------------------------------------------------------- resultado de cada candidatura
ELEITO_SIT = {"ELEITO": "e", "ELEITO POR QP": "eqp", "ELEITO POR MÉDIA": "emed", "MÉDIA": "emed"}
PRIORIDADE = {"e": 0, "eqp": 0, "emed": 0, "2t": 1, "sup": 2, "ne": 3, "sub": 4, "rena": 5, "nega": 5, "cas": 5,
              "ren": 6, "neg": 6, "inapto": 7, "sr": 8}


def cod_sit(f: list) -> str:
    """Código curto do resultado (o texto, em português e inglês, fica no js/trajetoria.js)."""
    sit = f[I["sit"]]
    if sit in ELEITO_SIT:
        return ELEITO_SIT[sit]
    s = sem_acento(sit).upper()
    if s == "SUPLENTE":
        return "sup"
    if s == "NAO ELEITO":
        return "ne"
    if "TURNO" in s and "2" in s:
        return "2t"
    apos = "APOS" in s
    if "REGISTRO NEGADO" in s or "INDEFERIDO" in s:
        return "nega" if apos else "neg"
    if "SUBSTITU" in s:
        return "sub"
    if "CASSADO" in s:
        return "cas"
    if "RENUNCIA" in s:
        return "rena" if apos else "ren"
    c = sem_acento(f[I["sitc"]] + " " + f[I["det"]]).upper()
    if any(x in c for x in ("INDEFERID", "NEGAD", "CANCELA", "NAO CONHECIMENTO", "INELEGIVEL", "IMPUGNA")):
        return "neg"
    if "RENUNCIA" in c or "DESISTENCIA" in c:
        return "ren"
    if "CASSA" in c:
        return "cas"
    if "INAPTO" in c:
        return "inapto"
    return "sr"


def resultado(rows: list) -> tuple[str, int, list]:
    """(código, turno final, linha da candidatura) de um grupo de linhas da mesma candidatura (1º e 2º turno)."""
    rows = sorted(rows, key=lambda x: (x[0][I["turno"]], PRIORIDADE.get(cod_sit(x[0]), 9)))
    t1 = [x for x in rows if x[0][I["turno"]] == "1"]
    t2 = [x for x in rows if x[0][I["turno"]] == "2"]
    base = (t1 or rows)[0]
    r = min((cod_sit(x[0]) for x in (t1 or rows)), key=lambda c: PRIORIDADE.get(c, 9))
    base = min(t1 or rows, key=lambda x: PRIORIDADE.get(cod_sit(x[0]), 9))
    if t2:
        r2 = min((cod_sit(x[0]) for x in t2), key=lambda c: PRIORIDADE.get(c, 9))
        f2 = min(t2, key=lambda x: PRIORIDADE.get(cod_sit(x[0]), 9))
        if r2 in ("e", "eqp", "emed"):
            return "e", 2, f2[0]
        if r2 == "ne":
            return "ne", 2, f2[0]
        return ("2t" if r in ("2t", "sr") else r), 2, f2[0]
    return r, 1, base[0]


def resultado_final(rows: list, ano: int, vot) -> tuple[str, int, list, list | None]:
    """resultado() + o 2º turno de 2006 para presidente, que os dados abertos do TSE não marcam: o vencedor vem de
    dados/manual/presidentes.json (Biblioteca da Presidência, com fonte); quem foi ao 2º turno, dos votos do TSE."""
    r, turno, f = resultado(rows)
    fontes = None
    if r == "sr" and f[I["cargo"]] == "PRESIDENTE":
        man = ((ler_json(DADOS / "manual" / "presidentes.json") or {}).get("mandatos") or {}).get(str(ano + 1)) or {}
        venc = man.get("vencedor")
        if venc:
            v1 = votos_de(vot(ano), f[I["ue"]], "BR", f[I["sq"]], 1)
            v2 = votos_de(vot(ano), f[I["ue"]], "BR", f[I["sq"]], 2)
            if v2 is not None:
                r, turno, fontes = ("e" if f[I["num"]] == venc["numero"] else "ne"), 2, man.get("fontes")
            elif v1 is not None:
                r, turno = "ne", 1
    return r, turno, f, fontes


def balde(pid: str, n: int = N_BALDES) -> str:
    """O balde da pessoa (FNV-1a de 32 bits do id, resto por n): a mesma conta do js/trajetoria.js."""
    h = 0x811C9DC5
    for b in pid.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h % n:02x}"


# ---------------------------------------------------------------- montar a trajetória de cada pessoa
def indices(linhas: dict, u: Uniao):
    comps, idx, tits = collections.defaultdict(list), collections.defaultdict(set), collections.defaultdict(list)
    for rid, (f, ano, como) in linhas.items():
        if f[I["cargo"]] in TITULARES_TSE:
            tits[chave_k(ano, f)].append((f, ano))
        if como == "K":
            continue
        comps[u.acha(rid)].append(rid)
        idx[f"S{ano}|{f[I['sq']]}"].add(rid)
        if f[I["cpf"]]:
            idx["C" + f[I["cpf"]]].add(rid)
        for k in ("nk", "sk"):
            if f[I[k]]:
                idx["N" + f[I[k]]].add(rid)
    return comps, idx, tits


def _casa_esperado(rids: list, linhas: dict, esp: dict | None) -> bool:
    if not esp:
        return True
    for r in rids:
        f, ano, _ = linhas[r]
        if CARGO.get(f[I["cargo"]]) in esp["c"] and (not esp.get("uf") or f[I["uf"]] in (esp["uf"], "BR")):
            return True
    return False


def ancora(p: dict, idx, comps, u: Uniao, linhas: dict) -> tuple:
    """(raiz da pessoa nos dados do TSE ou None, como foi achada: sq | cpf | nome | duvida | nao-achou)."""
    for tipo, como in (("S", "sq"), ("C", "cpf"), ("N", "nome")):
        seeds = [s for s in p["seeds"] if s[0] == tipo]
        rids = set().union(*(idx.get(s, set()) for s in seeds)) if seeds else set()
        if not rids:
            continue
        cs = {u.acha(r) for r in rids}
        if len(cs) > 1:
            cs = {c for c in cs if _casa_esperado(comps[c], linhas, p.get("esperado"))}
        if p.get("cpf"):  # pela Câmara a pessoa tem CPF: fica a pessoa do TSE que tem esse CPF
            cs = {c for c in cs if any(linhas[r][0][I["cpf"]] == p["cpf"] for r in comps[c])}
        if len(cs) == 1:
            return next(iter(cs)), como
        return None, "duvida"
    return None, "nao-achou"


def _nome_titular(f: list) -> str:
    from tse import nome_tse
    return nome_tse(f[I["urna"]] or f[I["nome"]]) or ""


def itens_tse(rids: list, linhas: dict, tits: dict, vot, p: dict) -> list[dict]:
    grupos = collections.defaultdict(list)
    for r in rids:
        f, ano, _ = linhas[r]
        if f[I["ord"]] == "1":  # o 1º e o 2º turno da eleição ordinária têm códigos de eleição diferentes
            grupos[(ano, "o", f[I["ue"]], f[I["cargo"]])].append((f, ano))
        else:
            grupos[(ano, "s" + f[I["el"]], f[I["ue"]], f[I["cargo"]])].append((f, ano))
    # suplementar: o 2º turno (outro código de eleição) vai junto do 1º turno anterior mais perto, no mesmo lugar e cargo
    for k in [k for k, rs in grupos.items() if k[1] != "o" and all(x[0][I["turno"]] == "2" for x in rs)]:
        dt = grupos[k][0][0][I["dt"]]
        antes = [k2 for k2, rs in grupos.items() if k2 != k and k2[1] != "o" and k2[0] == k[0] and k2[2:] == k[2:]
                 and any(x[0][I["turno"]] == "1" and x[0][I["dt"]] < dt for x in rs)]
        if antes:
            alvo = max(antes, key=lambda k2: max(x[0][I["dt"]] for x in grupos[k2]))
            grupos[alvo] += grupos.pop(k)
    out = []
    for (ano, _el, ue, cargo), rows in grupos.items():
        c = CARGO[cargo]
        r, turno, f, fontes_man = resultado_final(rows, ano, vot)
        dt = min((x[0][I["dt"]] for x in rows if x[0][I["dt"]]), default="")
        it = {"k": "c", "a": int(dt[:4]) if dt else ano, "c": c, "uf": f[I["uf"]], "p": f[I["partido"]] or None, "r": r}
        if fontes_man:
            it["fontes"] = fontes_man
        if cargo in MUNICIPAIS:
            it["ue"] = ue
        if f[I["ord"]] != "1":
            it["s"] = 1
            it["dt"] = dt
        if c in VICES:
            tit = tits.get(chave_k(ano, rows[0][0], TIT_DO_VICE[cargo]))
            if tit:
                rt, tt, ft, fontes_man = resultado_final(tit, ano, vot)
                if fontes_man:
                    it["fontes"] = fontes_man
                propria = r
                r = {"e": "e", "eqp": "e", "emed": "e", "ne": "ne", "2t": "2t"}.get(rt, rt)
                if propria in ("neg", "nega", "ren", "rena", "cas", "sub", "inapto"):
                    r = propria  # a candidatura do vice caiu (o resultado da chapa não é dele)
                it["r"], turno = r, tt
                it["ch"] = {"n": _nome_titular(ft)}
                vt = votos_de(vot(ano), ft[I["ue"]], "BR" if ft[I["cargo"]] == "PRESIDENTE" else ft[I["uf"]], ft[I["sq"]], tt)
                if vt is not None:
                    it["ch"]["v"] = vt
            elif ano in SEM_VICE_LIGADO:
                it["r"] = r = "sv"  # o TSE não liga o vice à chapa neste ano: o resultado da chapa não aparece
                turno = 1
        else:
            v = votos_de(vot(ano), f[I["ue"]], "BR" if cargo == "PRESIDENTE" else f[I["uf"]], f[I["sq"]], turno)
            if v is not None and r not in ("neg", "ren", "inapto", "sub"):
                it["v"] = v
        if turno == 2:
            it["t"] = 2
        if f[I["ord"]] == "1" and ano in ID_DIVULGA:
            it["sq"] = f[I["sq"]]
        urna = f[I["urna"]]
        if urna and chave_nome(urna) not in (chave_nome(p.get("nome") or ""), chave_nome(p.get("nomeCivil") or "")):
            from tse import nome_tse
            it["n"] = nome_tse(urna)
        it["_sq"] = f[I["sq"]]
        out.append(it)
    return out


ORDEM_CARGO = ["pres", "vp", "gov", "vgov", "sen", "s1", "s2", "dep", "dest", "ddist", "pref", "vpref", "ver"]
OFICIAIS = re.compile(r"https?://([a-z0-9-]+\.)*(gov\.br|leg\.br|jus\.br|mp\.br|def\.br)(/|$)", re.I)


def fontes_oficiais(fs) -> list:
    return [f for f in (fs if isinstance(fs, list) else [fs] if fs else []) if isinstance(f, dict) and OFICIAIS.match(f.get("url") or "")]


def trajetoria(p: dict, raiz, como: str, comps, linhas, tits, vot) -> dict:
    itens = itens_tse(comps[raiz], linhas, tits, vot, p) if raiz is not None else []
    g = p.get("ficha") or {}
    hoje_ = hoje()
    # o mandato de hoje
    alvo = None
    if p["tipo"] in ("dep",):
        alvo = lambda it: it["c"] == "dep" and it["a"] == mandatos.vigente("deputado_federal")["eleicao"]
    elif p["tipo"] == "sen":
        perf = ler_json(PESSOAS / f"{p['id']}.json") or {}
        fim = ((perf.get("mandato") or {}).get("fim") or "")[:4]
        if fim.isdigit():  # o mandato de 8 anos termina em janeiro do 9º ano depois da eleição (2018 -> 2027)
            alvo = lambda it, e=int(fim) - 9: it["c"] in ("sen", "s1", "s2") and it["a"] == e
    elif p["tipo"] in ("pres", "vp"):
        alvo = lambda it: it["c"] == p["tipo"] and it["a"] == mandatos.vigente("presidente")["eleicao"]
    elif p["tipo"] in ("gov", "vgov", "dest", "pref", "vpref", "ver"):
        sqs = {s.split("|", 1)[1] for s in p["seeds"] if s.startswith("S")}
        assumiu = g.get("desde") and g.get("comoAssumiu") and not re.match(r"Eleit", g.get("comoAssumiu") or "")
        if not assumiu:
            alvo = lambda it: it.get("_sq") in sqs and it["a"] in (2022, 2024)
    if alvo:
        cand = [it for it in itens if alvo(it) and it["r"] in ("e", "eqp", "emed", "sup", "2t")]
        cand.sort(key=lambda it: -it["a"])
        if cand:
            cand[0]["hoje"] = 1
            if g.get("exercicio"):
                cand[0]["ex"] = g["exercicio"]
                if g.get("exercicio_en"):
                    cand[0]["ex_en"] = g["exercicio_en"]
    # vice que assumiu, presidente da Câmara que governa até a posse...: o que a ficha do site diz, com as fontes oficiais dela
    if g.get("desde") and g.get("comoAssumiu") and not re.match(r"Eleit", g["comoAssumiu"]) and p["tipo"] in ("gov", "vgov", "pref", "vpref"):
        fs = fontes_oficiais(g.get("fontes") or g.get("fonte"))
        a = {"k": "a", "c": p["tipo"], "uf": p["uf"], "i": g["desde"], "txt": g["comoAssumiu"], "hoje": 1}
        if g.get("comoAssumiu_en"):
            a["txt_en"] = g["comoAssumiu_en"]
        if p.get("ibge"):
            a["cid"] = p["ibge"]
        if fs:
            a["fontes"] = fs
        itens.append(a)
    if p["tipo"] == "stf":
        po = g.get("posse") or {}
        if po.get("data"):
            itens.append({"k": "stf", "i": po["data"], "hoje": 1, "fontes": fontes_oficiais(po.get("fontes")) or None})
    if p["tipo"] == "min":
        itens.append({"k": "min", "i": g.get("desde"), "hoje": 1, "min": g.get("ministerio"), "min_en": g.get("ministerio_en"),
                      "fontes": fontes_oficiais(g.get("fonte")) or None})
    # 2026: quem foi eleito e ainda não tomou posse
    for it in itens:
        if it.get("k") == "c" and it["a"] >= 2026 and it["r"] in ("e", "eqp", "emed") and not it.get("s"):
            cargo_m = {"s1": "sen", "s2": "sen", "ddist": "dest"}.get(it["c"], it["c"])
            po = mandatos.posse(cargo_m, it["a"], it["uf"])
            if po > hoje_:
                it["po"] = po
    itens.sort(key=lambda it: (-(it.get("a") or int((it.get("i") or "0000")[:4]) - 1),
                               -int(bool(it.get("hoje"))), (it.get("dt") or ""), ORDEM_CARGO.index(it["c"]) if it.get("c") in ORDEM_CARGO else 99))
    for it in itens:
        it.pop("_sq", None)
    return {"liga": como if raiz is not None else None, "it": [{k: v for k, v in it.items() if v is not None} for it in itens]}


# ---------------------------------------------------------------- gravar
def cidades_dos_ues(ues: dict) -> dict:
    """{SG_UE do TSE: [código IBGE, nome do município hoje, UF]} (o casamento TSE x IBGE do scripts/historico.py)."""
    import historico
    try:
        mapa = historico.mapa_municipios({a: v for a, v in ues.items() if v})
        locs = ibge.municipios()
    except Exception as e:  # noqa: BLE001
        log(f"  [aviso] municípios TSE x IBGE: {e}")
        mapa, locs = {}, {}
    out = {}
    for ano in sorted(ues):
        for ue, (uf, nome) in ues[ano].items():
            cod = mapa.get(ue)
            out[ue] = [cod, (locs.get(cod) or {}).get("nome") or nome_proprio(nome), uf]
    return out


def compacto(it: dict):
    """Candidatura em lista curta (o arquivo fica com metade do tamanho): [ano, cargo, lugar, partido, resultado, votos,
    SQ, extras]. lugar = código do município no TSE (cidades) ou UF (BR para presidente). js/trajetoria.js desfaz."""
    if it.get("k") != "c":
        return it
    x = {k: v for k, v in it.items() if k not in ("k", "a", "c", "uf", "ue", "p", "r", "v", "sq")}
    out = [it["a"], it["c"], it.get("ue") or it["uf"], it.get("p"), it["r"], it.get("v"), it.get("sq")]
    if x:
        out.append(x)
    while out and out[-1] is None:
        out.pop()
    return out


def gravar(res: dict, ues_cid: dict, meta: dict) -> tuple[int, int]:
    baldes, ues_b = collections.defaultdict(dict), collections.defaultdict(set)
    for pid, t in res.items():
        b = balde(pid)
        baldes[b][pid] = dict(t, it=[compacto(it) for it in t["it"]])
        ues_b[b] |= {it["ue"] for it in t["it"] if it.get("ue")}
    tse_cab = {str(a): {"data": meta.get(str(a)), **({"divulga": ID_DIVULGA[a]} if a in ID_DIVULGA else {})} for a in ANOS}
    SAIDA.mkdir(parents=True, exist_ok=True)
    n, total = 0, 0
    for b in [f"{i:02x}" for i in range(N_BALDES)]:
        pessoas = dict(sorted(baldes.get(b, {}).items()))
        usados = sorted(ues_b.get(b, ()))
        obj = {"v": 1, "tse": tse_cab, "ues": {ue: ues_cid.get(ue) for ue in usados}, "pessoas": pessoas, "atualizado": hoje()}
        caminho = SAIDA / f"{b}.json"
        n += salvar_json(caminho, sem_mudar_data(obj, caminho))
        total += caminho.stat().st_size
    for f in SAIDA.glob("*.json"):
        if not re.fullmatch(r"[0-9a-f]{2}", f.stem) or int(f.stem, 16) >= N_BALDES:
            f.unlink()
    return n, total


def conferencia(pessoas, achou, linhas, comps, conflitos, mesmos, u) -> tuple[list[str], dict]:
    """Lista de conferência (só log, nunca no site): ligações recusadas e nomes parecidos. Devolve também, por pessoa, os
    anos em que há uma candidatura com o mesmo nome, no mesmo estado, sem data de nascimento (não ligada)."""
    out, faltas = [], {}
    raiz_de = {p["id"]: achou[p["id"]][0] for p in pessoas}
    chaves_alvo = collections.defaultdict(list)
    for p in pessoas:
        for s in p["seeds"]:
            chaves_alvo[s].append(p["id"])
        r = raiz_de[p["id"]]
        if r is not None:
            for rid in comps[r]:
                f = linhas[rid][0]
                for k in ("nk", "sk"):
                    if f[I[k]]:
                        chaves_alvo["N" + f[I[k]]].append(p["id"])
    for k, rids in conflitos:
        quem = sorted(set(chaves_alvo.get(k, [])))
        if not quem:
            continue
        soltas = [r for r in rids if not (linhas[r][0][I["cpf"]] or linhas[r][0][I["tit"]])]
        if not soltas:
            continue  # cada uma das pessoas já está ligada pelo CPF/título: nada ficou de fora
        out.append(f"CONFLITO {k[1:]} ({', '.join(quem)}): mesmo nome e nascimento com pessoas diferentes (CPF/título); "
                   f"{len(soltas)} linha(s) sem CPF/título ficaram de fora: " +
                   "; ".join(f"{linhas[r][1]} {linhas[r][0][I['cargo']]} {linhas[r][0][I['uf']]}" for r in sorted(soltas)[:6]))
    for p in pessoas:
        r, como = achou[p["id"]]
        if como == "duvida":
            out.append(f"DÚVIDA {p['id']} ({p.get('nomeCivil')}, {p.get('nasc')}): mais de uma pessoa possível no TSE; fica sem candidaturas")
        if como == "nao-achou" and p["tipo"] not in ("stf",):
            motivo = ("sem número do TSE e sem nome civil + nascimento na ficha" if not p["seeds"] else
                      "o número do TSE ou o nome civil + nascimento da ficha não aparecem nos dados do TSE")
            out.append(f"SEM LIGAÇÃO {p['id']} ({p.get('nome')}): {motivo}")
        if r is not None:
            cpfs = {linhas[x][0][I["cpf"]] for x in comps[r] if linhas[x][0][I["cpf"]]}
            if len(cpfs) > 1:
                out.append(f"CPF DIFERENTE {p['id']} ({p.get('nomeCivil')}): {len(cpfs)} CPFs nas candidaturas ligadas pelo título de "
                           "eleitor (provável erro de digitação no TSE; ficam juntas)")
        if not p.get("nomeCivil"):
            continue
        k = chave_nome(p["nomeCivil"])
        meus = set(comps[r]) if r is not None else set()
        perto = [x for x in mesmos.get(k, []) if x[5] not in meus and x[2] != p.get("nasc") and x[1] in (p.get("uf"), "BR")]
        # mesmo nome, no mesmo estado, numa linha sem data de nascimento e sem CPF/título: pode ser a pessoa, mas não dá
        # para saber (1996, quase sempre). A trajetória avisa que pode faltar uma candidatura daquele ano.
        sem_nasc = sorted({x[0] for x in perto if not x[2] and not x[4]})
        if sem_nasc and r is not None:
            faltas[p["id"]] = sem_nasc
        if perto and p.get("nasc"):
            def dias(a, b):
                try:
                    import datetime as _d
                    return abs((_d.date.fromisoformat(a) - _d.date.fromisoformat(b)).days)
                except Exception:  # noqa: BLE001
                    return None
            pp = [x for x in perto if x[2] and (dias(x[2], p["nasc"]) or 9999) <= 400]
            if pp:
                out.append(f"PARECIDO {p['id']} ({p['nomeCivil']}, {p['nasc']}): mesmo nome no mesmo estado com nascimento "
                           "perto, não ligado: " + "; ".join(f"{x[0]} {x[3]} {x[1]} nasc={x[2]}" for x in pp[:6]))
    return out, faltas


def main():
    global SEM_REDE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", action="store_true", help="sem rede: só o que já está em .cache/")
    ap.add_argument("--id", nargs="*", help="mostra a trajetória destas pessoas e não grava nada")
    ap.add_argument("--sem-casas", action="store_true", help="sem Câmara e Senado (mais rápido, para testar)")
    ap.add_argument("--forcar", action="store_true", help="grava mesmo se a rodada achar bem menos que a publicada")
    args = ap.parse_args()
    if args.cache:
        SEM_REDE = True
    t0 = time.time()
    log("Trajetória: quem tem perfil no site...")
    pessoas = pessoas_do_site()
    cont = collections.Counter(p["tipo"] for p in pessoas)
    log(f"  {len(pessoas)} perfis: {dict(cont)}")
    log("Trajetória: candidaturas no TSE (1994 a 2026)...")
    for a in ANOS:
        indice(a)
    linhas, ues, mesmos = coletar(pessoas)
    u, conflitos = ligar(linhas)
    comps, idx, tits = indices(linhas, u)
    votos_cache = {}

    def vot(ano):
        if ano not in votos_cache:
            votos_cache[ano] = votos(ano)
        return votos_cache[ano]

    achou, res = {}, {}
    for p in pessoas:
        if p["tipo"] == "min":
            achou[p["id"]] = (None, "sem-dados")
        else:
            achou[p["id"]] = ancora(p, idx, comps, u, linhas)
        r, como = achou[p["id"]]
        res[p["id"]] = trajetoria(p, r, como, comps, linhas, tits, vot)
    if not args.sem_casas:
        casas(pessoas, achou, comps, linhas, res)
    # perfil-mandato-r10: onde está a lista do que a pessoa propôs em cada mandato da Câmara e do Senado
    listas = {}
    if not args.sem_casas:
        try:
            listas = propostas_por_mandato(res)
        except Exception as e:  # noqa: BLE001
            log(f"  [aviso] propostas dos mandatos antigos: {e}; a trajetória sai sem as listas")
            listas = None
    # números
    por_tipo = collections.defaultdict(collections.Counter)
    for p in pessoas:
        r, como = achou[p["id"]]
        por_tipo[p["tipo"]][como] += 1
        n = sum(1 for it in res[p["id"]]["it"] if it["k"] == "c")
        por_tipo[p["tipo"]]["com mais de 1 candidatura" if n > 1 else "1 candidatura" if n == 1 else "nenhuma candidatura"] += 1
    for t, c in sorted(por_tipo.items()):
        log(f"  {t}: {dict(c)}")
    conf, faltas = conferencia(pessoas, achou, linhas, comps, conflitos, mesmos, u)
    for pid, anos in faltas.items():
        res[pid]["falta"] = anos
    log(f"  {len(faltas)} pessoas com uma candidatura possível sem data de nascimento no TSE (mesmo nome e estado), não ligada")
    CT.mkdir(parents=True, exist_ok=True)
    (CT / "conferir.txt").write_text("\n".join(conf) + "\n", encoding="utf-8")
    log(f"  lista de conferência: {len(conf)} linhas em .cache/trajetoria/conferir.txt "
        f"({sum(l.startswith('CONFLITO') for l in conf)} conflitos, {sum(l.startswith('DÚVIDA') for l in conf)} dúvidas, "
        f"{sum(l.startswith('PARECIDO') for l in conf)} nomes parecidos)")
    if args.id:
        for pid in args.id:
            print(json.dumps({pid: res.get(pid)}, ensure_ascii=False, indent=1))
        return
    ues_cid = cidades_dos_ues(ues)
    meta = ler_json(CT / "cand_meta.json", {}) or {}
    # trava: se esta rodada achou bem menos que a publicada (cache faltando, site fora do ar), fica o que está publicado
    antes = {"it": 0, "m": 0}
    for f in SAIDA.glob("*.json"):
        for t in ((ler_json(f) or {}).get("pessoas") or {}).values():
            antes["it"] += len(t["it"])
            antes["m"] += sum(1 for x in t["it"] if (isinstance(x, dict) and x.get("m")) or (isinstance(x, list) and len(x) > 7 and x[7].get("m")))
    agora = {"it": sum(len(t["it"]) for t in res.values()), "m": sum(1 for t in res.values() for x in t["it"] if x.get("m"))}
    if antes["it"] and not args.forcar and (agora["it"] < .97 * antes["it"] or agora["m"] < .97 * antes["m"]):
        log(f"⚠️ Trajetória: esta rodada tem {agora} contra {antes} publicados; nada foi gravado (fica o que está publicado)")
        return
    n, total = gravar(res, ues_cid, meta)
    log(f"dados/trajetoria: {N_BALDES} arquivos ({n} mudaram), {total / 1e6:.1f} MB; pronto em {time.time() - t0:.0f}s")
    if listas is not None and not args.sem_casas:
        n2, total2 = gravar_propostas(listas)
        log(f"dados/trajetoria/propostas: {N_BALDES_PROP} arquivos ({n2} mudaram), {total2 / 1e6:.1f} MB")


def casas(pessoas, achou, comps, linhas, res):
    """Câmara e Senado: mandatos exercidos e o que a pessoa propôs em cada um."""
    chaves_de = {}  # id da pessoa -> chaves nome civil + nascimento (as do site e as do TSE)
    concorreu_senado = set()  # quem já concorreu a senador ou suplente (só esses podem ter sido senadores desde 1995)
    for p in pessoas:
        r, _ = achou[p["id"]]
        ks = {s[1:] for s in p["seeds"] if s.startswith("N")}
        if r is not None:
            for rid in comps[r]:
                f = linhas[rid][0]
                ks |= {f[I[k]] for k in ("nk", "sk") if f[I[k]]}
                if CARGO.get(f[I["cargo"]]) in ("sen", "s1", "s2"):
                    concorreu_senado.add(p["id"])
        chaves_de[p["id"]] = ks
    try:
        camara(pessoas, chaves_de, res)
    except Exception as e:  # noqa: BLE001
        log(f"  [aviso] Câmara: {e}; a trajetória sai sem os mandatos da Câmara")
    try:
        senado(pessoas, {pid: ks for pid, ks in chaves_de.items() if pid in concorreu_senado or pid.startswith(("sen-", "stf-"))}, res)
    except Exception as e:  # noqa: BLE001
        log(f"  [aviso] Senado: {e}; a trajetória sai sem os mandatos do Senado")


def _ligar_casa(ids_por_chave: dict, chaves_de: dict, diretos: dict) -> dict:
    """{id da pessoa: id na Casa}: direto (quem tem perfil da Casa) ou pelo nome civil + nascimento, quando a chave leva
    a um só parlamentar da Casa e todas as chaves da pessoa levam ao mesmo (nunca só pelo nome)."""
    out = dict(diretos)
    cand, amb = collections.defaultdict(set), set()
    for pid, ks in chaves_de.items():
        if pid in out:
            continue
        for k in ks:
            ids = ids_por_chave.get(k)
            if not ids:
                continue
            if len(ids) > 1:
                amb.add(pid)
            cand[pid] |= ids
    for pid, ids in cand.items():
        if len(ids) == 1 and pid not in amb:
            out[pid] = next(iter(ids))
        else:
            log(f"  [conferir] {pid}: mais de um parlamentar com o mesmo nome civil e nascimento ({sorted(ids)}); não ligado")
    return out


def _anexar(res_p: dict, cargos: set, ano_el: int | None, m: dict, avulso: dict) -> None:
    """Põe o mandato na candidatura que levou a ele (mesmo cargo, eleição do ano); sem ela, vira um item à parte."""
    alvo = [it for it in res_p["it"] if it.get("k") == "c" and it["c"] in cargos and it["a"] == ano_el
            and it["r"] in ("e", "eqp", "emed", "sup", "2t", "ne")] if ano_el else []
    alvo.sort(key=lambda it: PRIORIDADE.get(it["r"], 9))
    if alvo and "m" not in alvo[0]:
        alvo[0]["m"] = m
    else:
        res_p["it"].append(dict(avulso, m=m))


def _ordena(res_p: dict) -> None:
    res_p["it"].sort(key=lambda it: (-(it.get("a") or int(((it.get("m") or {}).get("i") or it.get("i") or "0000")[:4]) - 1),
                                     -int(bool(it.get("hoje"))), it.get("dt") or "",
                                     ORDEM_CARGO.index(it["c"]) if it.get("c") in ORDEM_CARGO else 99))


def _arq_camara(nome: str) -> Path:
    """Os arquivos da Câmara que o scripts/camara.py já guardou em .cache/camara/ (só leitura); se faltar, baixa para o
    cache desta frente."""
    p = CACHE / "camara" / nome
    if p.exists() and p.stat().st_size > 0:
        return p
    if SEM_REDE and not (CT / "camara" / nome).exists():
        raise RuntimeError(f"sem rede (--cache): {nome} não está no cache")
    pasta = nome.rsplit("-", 1)[0] if re.search(r"-\d{4}\.csv$", nome) else nome[:-4]
    return baixar_arquivo(f"{CAMARA_ARQ}/{pasta}/csv/{nome}", f"trajetoria/camara/{nome}", max_idade_h=None if SEM_REDE else 24 * 30)


def _csv(p: Path):
    with open(p, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def camara(pessoas, chaves_de, res):
    t = time.time()
    legs = {int(r["idLegislatura"]): (r["dataInicio"][:10], r["dataFim"][:10], int(r["anoEleicao"]))
            for r in _csv(_arq_camara("legislaturas.csv"))}
    leg_atual = mandatos.vigente("deputado_federal")["legislatura"]
    # quem exerceu o mandato em cada legislatura desde 1987 (inclusive suplentes que assumiram): a API da Câmara
    membros = collections.defaultdict(dict)
    for L in range(48, leg_atual + 1):
        for pg in range(1, 30):
            cache = f"trajetoria/camara/leg{L}-p{pg}.json"
            if SEM_REDE and not (CACHE / cache).exists():
                break
            d = baixar_json(f"{CAMARA_API}/deputados?idLegislatura={L}&itens=100&pagina={pg}&ordem=ASC&ordenarPor=nome",
                            cache=cache, max_idade_h=None if (L < leg_atual or SEM_REDE) else 24)
            if not (CACHE / cache).exists() or (time.time() - (CACHE / cache).stat().st_mtime) < 5:
                time.sleep(1)
            for m in d.get("dados") or []:
                membros[str(m["id"])][L] = m.get("siglaUf")
            if not any(l.get("rel") == "next" for l in d.get("links") or []):
                break
    # nome civil + nascimento de todo mundo que já foi deputado (arquivo deputados.csv)
    por_chave = collections.defaultdict(set)
    for r in _csv(_arq_camara("deputados.csv")):
        i = id_de_uri(r["uri"])
        k = chave_nn(r.get("nomeCivil"), data_iso(r.get("dataNascimento")))
        if k and i in membros:
            por_chave[k].add(i)
    diretos = {p["id"]: p["camara"] for p in pessoas if p.get("camara")}
    liga = _ligar_casa(por_chave, chaves_de, diretos)
    ids = set(liga.values())
    fez = camara_fez(ids, legs)
    parcial = bool(fez.pop("_parcial", False))
    n_m = 0
    for pid, cid in liga.items():
        perf = ler_json(PESSOAS / f"dep-{cid}.json") or {}
        datas = {}
        for mm in (perf.get("mandatosAnteriores") or []) + ([perf["mandato"]] if perf.get("mandato") else []):
            if mm.get("inicio"):
                for L, (li, lf, _) in legs.items():
                    if li <= mm["inicio"] <= lf:
                        datas[L] = (mm["inicio"], mm.get("fim"), "legislatura" not in (mm.get("obs") or ""))
        for L in sorted(membros.get(cid, {})):
            if L not in legs:
                continue
            li, lf, ano_el = legs[L]
            i, f, exatas = datas.get(L, (li, lf, False))
            if f and f > lf:
                f = lf
            fz = fez.get(f"{cid}|{L}")
            m = {"casa": "camara", "id": cid, "leg": L, "i": i, "f": f if f and f < hoje() else None}
            if fz is not None or not parcial:  # contagem guardada de outra rodada: sem a pessoa, fica sem o número
                fz = fz or {}
                m["fez"] = {"prop": fz.get("prop", 0), "autor": fz.get("autor", 0), "lei": fz.get("lei", 0)}
            if not exatas:
                m["dl"] = 1  # as datas são as da legislatura (a Câmara não diz o dia em que a pessoa entrou e saiu)
            if L == leg_atual and pid.startswith("dep-"):
                m["hoje"] = 1
            _anexar(res[pid], {"dep"}, ano_el if ano_el >= 1994 else None, m,
                    {"k": "m", "c": "dep", "uf": membros[cid][L]})
            n_m += 1
        _ordena(res[pid])
    log(f"  Câmara: {len(liga)} pessoas ligadas a um(a) deputado(a) federal ({len(diretos)} pelo perfil, "
        f"{len(liga) - len(diretos)} pelo nome civil + nascimento), {n_m} mandatos ({time.time() - t:.0f}s)")


def id_de_uri(uri: str | None) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def camara_fez(ids: set, legs: dict) -> dict:
    """{"<id>|<legislatura>": {"prop", "autor", "lei"}}: propostas (os tipos que o site conta como proposta) apresentadas
    pela pessoa em cada legislatura, como autor(a) principal (1º a assinar) ou coautor(a), e quantas viraram lei. A mesma
    regra do scripts/camara.py (RICD, art. 102): quem só deu apoio (proponente = 0) não conta."""
    anos = range(1987, int(hoje()[:4]) + 1)
    try:
        arqs = [_arq_camara(f"proposicoesAutores-{a}.csv") for a in anos] + [_arq_camara(f"proposicoes-{a}.csv") for a in anos]
    except Exception as e:  # noqa: BLE001
        guardado = ler_json(CT / "camara_fez.json") or {}
        if guardado.get("fez"):
            log(f"  [aviso] Câmara: arquivos de proposições indisponíveis ({e}); valem as contagens guardadas")
            return dict(guardado["fez"], _parcial=True)
        raise
    assinatura = json.dumps([sorted(ids), [(p.name, p.stat().st_size) for p in arqs]])
    import hashlib
    h = hashlib.sha1(assinatura.encode()).hexdigest()
    guardado = ler_json(CT / "camara_fez.json") or {}
    if guardado.get("h") == h:
        return guardado["fez"]
    t = time.time()
    papel = collections.defaultdict(dict)  # pid -> {dep: autor|coautor}
    for a in anos:
        linhas = collections.defaultdict(list)
        for r in _csv(_arq_camara(f"proposicoesAutores-{a}.csv")):
            linhas[r["idProposicao"]].append(r)
        for pid, rs in linhas.items():
            nossos = [r for r in rs if r["idDeputadoAutor"] in ids and r["codTipoAutor"] == "10000" and r["proponente"] == "1"]
            if not nossos:
                continue
            props = [r for r in rs if r["proponente"] == "1"]
            com_ordem = [r for r in props if (r["ordemAssinatura"] or "").isdigit() and int(r["ordemAssinatura"]) > 0]
            p1 = min(com_ordem, key=lambda r: int(r["ordemAssinatura"])) if com_ordem else (props[0] if len(props) == 1 else None)
            for r in nossos:
                papel[pid][r["idDeputadoAutor"]] = "autor" if r is p1 else "coautor"
    fez = collections.defaultdict(lambda: {"prop": 0, "autor": 0, "lei": 0})
    for a in anos:
        for r in _csv(_arq_camara(f"proposicoes-{a}.csv")):
            pid = r["id"]
            if pid not in papel or r["siglaTipo"] not in TIPOS_PROPOSTA:
                continue
            d = (r.get("dataApresentacao") or "")[:10]
            L = next((L for L, (li, lf, _) in legs.items() if li <= d <= lf), None)
            if L is None:
                continue
            lei = classificar_situacao(r.get("ultimoStatus_descricaoSituacao")) == "lei"
            for dep, pp in papel.pop(pid).items():
                x = fez[f"{dep}|{L}"]
                x["prop"] += 1
                x["autor"] += pp == "autor"
                x["lei"] += lei
    salvar_json(CT / "camara_fez.json", {"h": h, "fez": fez})
    log(f"  Câmara: propostas de {len(ids)} deputados(as) em cada legislatura, 1987 a hoje ({time.time() - t:.0f}s)")
    return dict(fez)


def _senado_api(caminho: str, cache: str, idade):
    p = CACHE / cache
    if p.exists() and p.stat().st_size > 0 and (idade is None or SEM_REDE or (time.time() - p.stat().st_mtime) / 3600 < idade):
        return json.loads(p.read_bytes().decode("utf-8-sig"))
    if SEM_REDE:
        raise RuntimeError(f"sem rede (--cache): {cache} não está no cache")
    time.sleep(1)
    return baixar_json(f"{SENADO_API}{caminho}", cache=cache, max_idade_h=0, headers={"Accept": "application/json"}, timeout=90,
                       tentativas=2)


def _L(x) -> list:
    return [] if x is None else x if isinstance(x, list) else [x]


def senado(pessoas, chaves_de, res):
    t = time.time()
    leg_atual = mandatos.vigente("senador")["legislatura"]
    lst = _senado_api(f"/senador/lista/legislatura/48/{leg_atual}.json", f"trajetoria/senado/lista_48_{leg_atual}.json", 24 * 7)
    ps = _L(((lst.get("ListaParlamentarLegislatura") or {}).get("Parlamentares") or {}).get("Parlamentar"))
    nomes = {}
    for x in ps:
        ident = x.get("IdentificacaoParlamentar") or {}
        nomes[str(ident.get("CodigoParlamentar"))] = chave_nome(ident.get("NomeCompletoParlamentar") or "")
    diretos = {p["id"]: p["senado"] for p in pessoas if p.get("senado")}
    # só pede o nascimento de quem tem o mesmo nome civil de alguém do site (não de todos os ~960)
    nomes_site = {k.split("|", 1)[0] for ks in chaves_de.values() for k in ks}
    por_chave = collections.defaultdict(set)
    pedidos = [cod for cod, nk in nomes.items() if nk in nomes_site or cod in diretos.values()]
    log(f"  Senado: {len(pedidos)} senadores(as) com o mesmo nome civil de alguém do site que já concorreu ao Senado")
    for n, cod in enumerate(pedidos, 1):
        if n % 50 == 0:
            log(f"    ... {n} de {len(pedidos)}")
        try:
            det = _detalhe_senador(cod)
        except Exception as e:  # noqa: BLE001
            log(f"  [aviso] Senado {cod}: {e}")
            continue
        ident = det.get("IdentificacaoParlamentar") or {}
        k = chave_nn(ident.get("NomeCompletoParlamentar"), data_iso((det.get("DadosBasicosParlamentar") or {}).get("DataNascimento")))
        if k:
            por_chave[k].add(cod)
    liga = _ligar_casa(por_chave, chaves_de, diretos)
    n_m = 0
    for pid, cod in liga.items():
        try:
            man = _mandatos_senador(cod)
            procs = _processos_senador(cod)
        except Exception as e:  # noqa: BLE001
            log(f"  [aviso] Senado {cod} ({pid}): {e}")
            continue
        for mm in man:
            exs = sorted([e for e in _L((mm.get("Exercicios") or {}).get("Exercicio")) if e.get("DataInicio")],
                         key=lambda e: e["DataInicio"])
            part = mm.get("DescricaoParticipacao") or ""
            if not exs and "titular" not in part.lower():
                continue  # suplente que não assumiu
            l1 = mm.get("PrimeiraLegislaturaDoMandato") or {}
            l2 = mm.get("SegundaLegislaturaDoMandato") or {}
            try:
                L1 = int(l1.get("NumeroLegislatura"))
            except (TypeError, ValueError):
                continue
            ano_el = 1994 + 4 * (L1 - 50)
            i = exs[0]["DataInicio"][:10] if exs else (l1.get("DataInicio") or "")[:10]
            f = (exs[-1].get("DataFim") or "")[:10] if exs else ""
            fim_mand = (l2.get("DataFim") or l1.get("DataFim") or "")[:10]
            if not f and fim_mand and fim_mand < hoje():
                f = fim_mand
            atual = not f or f >= hoje()
            ate = f or hoje()
            fz = {"prop": 0, "lei": 0}
            for x in procs:
                sig = (x.get("identificacao") or "").split(" ")[0]
                d = (x.get("dataApresentacao") or "")[:10]
                if sig in TIPOS_PROPOSTA | {"PRN"} and x.get("objetivo") != "Revisora" and i <= d <= ate:
                    fz["prop"] += 1
                    fz["lei"] += bool(x.get("normaGerada")) or classificar_situacao(x.get("situacaoAtual")) == "lei"
            m = {"casa": "senado", "id": cod, "i": i, "f": None if atual else f, "como": "titular" if "titular" in part.lower() else "suplente",
                 "fez": fz}
            if atual and pid.startswith("sen-"):
                m["hoje"] = 1
            cargos = {"sen"} if m["como"] == "titular" else {"s1", "s2"}
            _anexar(res[pid], cargos, ano_el if ano_el >= 1994 else None, m,
                    {"k": "m", "c": "sen", "uf": mm.get("UfParlamentar")})
            n_m += 1
        _ordena(res[pid])
    log(f"  Senado: {len(liga)} pessoas ligadas a um(a) senador(a) ({len(diretos)} pelo perfil, {len(liga) - len(diretos)} pelo "
        f"nome civil + nascimento), {n_m} mandatos ({time.time() - t:.0f}s)")


def _detalhe_senador(cod: str) -> dict:
    p = CACHE / "tse" / "senado" / f"{cod}.json"  # o scripts/tse.py já guardou o dos senadores de hoje
    d = ler_json(p) if p.exists() else _senado_api(f"/senador/{cod}.json", f"trajetoria/senado/{cod}.json", None)
    return (d.get("DetalheParlamentar") or {}).get("Parlamentar") or {}


def _mandatos_senador(cod: str) -> list:
    p = CACHE / "senado" / "senador" / f"{cod}_mandatos.json"  # o scripts/senado.py já guardou o dos senadores de hoje
    d = ler_json(p) if p.exists() else _senado_api(f"/senador/{cod}/mandatos.json", f"trajetoria/senado/{cod}_mandatos.json", 24 * 7)
    return _L((((d.get("MandatoParlamentar") or {}).get("Parlamentar") or {}).get("Mandatos") or {}).get("Mandato"))


def _processos_senador(cod: str) -> list:
    p = CACHE / "senado" / "processos" / f"{cod}.json"  # o scripts/senado.py já guardou o dos senadores de hoje
    if p.exists():
        return _L(json.loads(p.read_bytes().decode("utf-8-sig")))
    return _L(_senado_api(f"/processo.json?codigoParlamentarAutor={cod}", f"trajetoria/senado/processos_{cod}.json", 24 * 7))


# ---------------------------------------------------------------- perfil-mandato-r10: o que propôs em cada mandato antigo
# O perfil filtrado por mandato (js/pessoa.js, ?mandato=) mostra a lista das propostas daquele mandato. Onde ela já está no
# site, o mandato aponta para o arquivo: "pf" = dados/pessoas/<dep|sen>-<id>.json (o perfil de hoje daquele parlamentar:
# filtrar pelas datas do mandato). Onde não está (quem foi deputado ou senador e hoje tem outro cargo ou nenhum), a lista
# vai para dados/trajetoria/propostas/<00-3f>.json (64 baldes pela conta FNV-1a de "<casa>-<id>"), com a mesma régua do
# scripts/camara.py e do scripts/senado.py, e o mandato ganha "pl": 1.
N_BALDES_PROP = 64
SAIDA_PROP = SAIDA / "propostas"


def _mandatos_casas(res: dict):
    """Cada mandato da Câmara e do Senado (o mesmo objeto pode aparecer em mais de um perfil da mesma pessoa)."""
    for t in res.values():
        for it in t["it"]:
            if it.get("m"):
                yield it["m"]


def chave_lista(m: dict) -> str:
    return f"camara:{m['id']}:{m['leg']}" if m["casa"] == "camara" else f"senado:{m['id']}:{m['i']}"


def propostas_por_mandato(res: dict) -> dict:
    """Marca "pf" nos mandatos com perfil de hoje e devolve {chave_lista: [propostas]} dos outros (marcados com "pl")."""
    alvo_c, alvo_s = {}, {}
    for m in _mandatos_casas(res):
        pref = "dep" if m["casa"] == "camara" else "sen"
        if (PESSOAS / f"{pref}-{m['id']}.json").exists():
            m["pf"] = f"{pref}-{m['id']}"
            continue
        if (m.get("fez") or {}).get("prop") == 0:
            continue
        (alvo_c if m["casa"] == "camara" else alvo_s)[chave_lista(m)] = m
    listas = {}
    if alvo_c:
        listas.update(_listas_camara(alvo_c))
    if alvo_s:
        listas.update(_listas_senado(alvo_s))
    for k, m in list(alvo_c.items()) + list(alvo_s.items()):
        if listas.get(k):
            m["pl"] = 1
        if k in listas and m["casa"] == "senado":
            # a contagem do Senado passa a ser a da lista (a régua de autoria do scripts/senado.py: fica de fora o que a
            # pessoa assinou como deputado(a) e o que veio da Câmara), para a linha do tempo e a lista dizerem o mesmo
            m["fez"] = {"prop": len(listas[k]), "lei": sum(1 for x in listas[k] if x.get("status") == "lei")}
    log(f"  propostas por mandato: {sum(len(v) for v in listas.values())} propostas em {sum(1 for v in listas.values() if v)} "
        f"mandatos antigos sem perfil de hoje (Câmara {len(alvo_c)}, Senado {len(alvo_s)})")
    return {k: v for k, v in listas.items() if v}


def _compacta(x: dict) -> dict:
    out = {k: x[k] for k in ("id", "sigla", "data", "ementa", "status", "statusTxt", "papel") if x.get(k)}
    if x.get("temas"):
        out["temas"] = x["temas"]
    return out


def _listas_camara(alvo: dict) -> dict:
    import camara as cam  # a régua de situação das propostas (status_proposta) é a mesma do perfil dos deputados de hoje
    legs = {int(r["idLegislatura"]): (r["dataInicio"][:10], r["dataFim"][:10]) for r in _csv(_arq_camara("legislaturas.csv"))}
    quer = collections.defaultdict(set)  # id do deputado -> legislaturas
    for m in alvo.values():
        quer[m["id"]].add(m["leg"])
    anos = sorted({a for L in {m["leg"] for m in alvo.values()} if L in legs
                   for a in range(int(legs[L][0][:4]), min(int(legs[L][1][:4]), int(hoje()[:4])) + 1)})
    arqs = [_arq_camara(f"{n}-{a}.csv") for a in anos for n in ("proposicoes", "proposicoesAutores", "proposicoesTemas")]
    import hashlib
    h = hashlib.sha1(json.dumps([sorted(alvo), [(p.name, p.stat().st_size) for p in arqs], 1]).encode()).hexdigest()
    guardado = ler_json(CT / "propostas_camara.json") or {}
    if guardado.get("h") == h:
        return guardado["listas"]
    t = time.time()
    ids = set(quer)
    papel = collections.defaultdict(dict)  # idProposicao -> {deputado: autor|coautor}
    for a in anos:
        linhas = collections.defaultdict(list)
        for r in _csv(_arq_camara(f"proposicoesAutores-{a}.csv")):
            linhas[r["idProposicao"]].append(r)
        for pid, rs in linhas.items():
            nossos = [r for r in rs if r["idDeputadoAutor"] in ids and r["codTipoAutor"] == "10000" and r["proponente"] == "1"]
            if not nossos:
                continue
            props = [r for r in rs if r["proponente"] == "1"]
            com_ordem = [r for r in props if (r["ordemAssinatura"] or "").isdigit() and int(r["ordemAssinatura"]) > 0]
            p1 = min(com_ordem, key=lambda r: int(r["ordemAssinatura"])) if com_ordem else (props[0] if len(props) == 1 else None)
            for r in nossos:
                papel[pid][r["idDeputadoAutor"]] = "autor" if r is p1 else "coautor"
    sigla, linhas_p = {}, {}
    for a in anos:
        for r in _csv(_arq_camara(f"proposicoes-{a}.csv")):
            if r["siglaTipo"] in TIPOS_PROPOSTA:
                sigla[r["id"]] = f"{r['siglaTipo']} {r['numero']}/{r['ano']}"
                if r["id"] in papel:
                    linhas_p[r["id"]] = {k: r.get(k) for k in cam.CAMPOS_PROP}
    temas = collections.defaultdict(list)
    for a in anos:
        for r in _csv(_arq_camara(f"proposicoesTemas-{a}.csv")):
            pid = id_de_uri(r.get("uriProposicao"))
            tm = limpa(r.get("tema"))
            if pid in linhas_p and tm and tm not in temas[pid]:
                temas[pid].append(tm)
    listas = collections.defaultdict(list)
    for pid, p in linhas_p.items():
        d = (p.get("dataApresentacao") or "")[:10]
        L = next((L for L, (li, lf) in legs.items() if li <= d <= lf), None)
        for dep, pp in papel[pid].items():
            if L not in quer.get(dep, ()):
                continue
            st, txt, _ = cam.status_proposta(p, sigla, None)
            if st not in STATUS_TXT:
                st, txt = classificar_situacao(p.get("ultimoStatus_descricaoSituacao")), ""
            listas[f"camara:{dep}:{L}"].append(_compacta({
                "id": f"camara:{pid}", "sigla": f"{p['siglaTipo']} {p['numero']}/{p['ano']}", "data": d or None,
                "ementa": limpa(p.get("ementa")), "status": st, "statusTxt": txt or STATUS_TXT.get(st), "papel": pp,
                "temas": sorted(temas.get(pid, []), key=chave_nome)}))
    out = {k: sorted(v, key=lambda x: (x.get("data") or "", x["id"]), reverse=True) for k, v in listas.items()}
    salvar_json(CT / "propostas_camara.json", {"h": h, "listas": out})
    log(f"  Câmara: listas de propostas de {len(alvo)} mandatos antigos ({time.time() - t:.0f}s)")
    return out


def _listas_senado(alvo: dict) -> dict:
    from senado import papel_no_processo  # a mesma régua de autoria do perfil dos senadores de hoje
    out = {}
    for k, m in alvo.items():
        cod = m["id"]
        try:
            procs = _processos_senador(cod)
            det = _detalhe_senador(cod)
        except Exception as e:  # noqa: BLE001
            log(f"  [aviso] Senado {cod}: {e}; sem a lista do mandato")
            continue
        ident = det.get("IdentificacaoParlamentar") or {}
        nomes = {chave_nome(n) for n in (ident.get("NomeParlamentar"), ident.get("NomeCompletoParlamentar")) if n}
        ate = m.get("f") or hoje()
        lista, vistos = [], set()
        for x in procs:
            idt = x.get("identificacao") or ""
            sig = idt.split(" ")[0]
            d = (x.get("dataApresentacao") or "")[:10]
            if sig not in TIPOS_PROPOSTA | {"PRN"} or x.get("objetivo") == "Revisora" or not (m["i"] <= d <= ate):
                continue
            if "(Substitutivo" in idt or "(Emenda" in idt or (x.get("autoria") or "").startswith("Câmara dos Deputados"):
                continue
            pp = papel_no_processo(None, x, int(cod), nomes)
            cm = x.get("codigoMateria") or x.get("id")
            if pp is None or cm in vistos:
                continue
            vistos.add(cm)
            if x.get("normaGerada"):
                st = "lei"
            else:
                st = classificar_situacao(limpa(x.get("situacaoAtual")))
            lista.append(_compacta({"id": f"senado:{cm}", "sigla": idt, "data": d, "ementa": limpa(x.get("ementa")),
                                    "status": st, "statusTxt": STATUS_TXT.get(st), "papel": pp}))
        out[k] = sorted(lista, key=lambda x: (x.get("data") or "", x["id"]), reverse=True)
    return out


def gravar_propostas(listas: dict) -> tuple[int, int]:
    baldes = collections.defaultdict(dict)
    for k, v in listas.items():
        casa, cid = k.split(":")[:2]
        baldes[balde(f"{casa}-{cid}", N_BALDES_PROP)][k] = v
    SAIDA_PROP.mkdir(parents=True, exist_ok=True)
    n, total = 0, 0
    for b in [f"{i:02x}" for i in range(N_BALDES_PROP)]:
        obj = {"v": 1, "m": dict(sorted(baldes.get(b, {}).items())), "atualizado": hoje()}
        caminho = SAIDA_PROP / f"{b}.json"
        n += salvar_json(caminho, sem_mudar_data(obj, caminho))
        total += caminho.stat().st_size
    for f in SAIDA_PROP.glob("*.json"):
        if not re.fullmatch(r"[0-9a-f]{2}", f.stem) or int(f.stem, 16) >= N_BALDES_PROP:
            f.unlink()
    return n, total


if __name__ == "__main__":
    main()
