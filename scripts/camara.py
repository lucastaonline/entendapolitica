#!/usr/bin/env python3
"""Câmara dos Deputados -> dados/camara.json, dados/pessoas/dep-<id>.json e dados/votacoes/camara.json.

Gera, para os 513 deputados federais EM EXERCÍCIO hoje:
  dados/camara.json               lista (total, porPartido, membros)
  dados/pessoas/dep-<id>.json     perfil completo (contrato no README); em "votacoes" só os pares
                                  [id da votação, voto] ("votos") e o caminho do catálogo ("arquivo")
  dados/votacoes/camara.json      catálogo das votações nominais do Plenário (cada uma uma única vez;
                                  chave = id da votação na Câmara, ex. "2236186-60", sem prefixo)
  dados/votacoes/camara/<id>.json uma votação por arquivo: placar, orientações e o voto de cada deputado
                                  (feito com scripts/votacoes.py, que também refaz só as votações a partir do cache)
  img/pessoas/dep-<id>.jpg        foto oficial (240 px)
  .cache/camara/situacoes.txt     situação oficial -> status do site (para conferir as regras)

Fontes (todas da Câmara dos Deputados):
  - API de Dados Abertos v2: lista dos deputados em exercício, ficha e histórico de cada um.
  - Arquivos em lote dos Dados Abertos: deputados, profissões, órgãos (comissões), proposições,
    autores, temas e votações. Um arquivo por ano, refeito todo dia pela Câmara.
  - Cota parlamentar (CEAP): arquivos Ano-AAAA.csv.zip e a página de consulta do portal
    (o arquivo não traz as passagens aéreas emitidas pelo sistema da Câmara, o SIGEPA; o portal traz).

Uso:
  python scripts/camara.py                       tudo
  python scripts/camara.py --so-lista            só dados/camara.json (e fotos)
  python scripts/camara.py --ids 204379,220714   só esses perfis (testes rápidos)
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import *  # noqa: E402,F401,F403
from comum import (CACHE, FOTOS, PESSOAS, DADOS, RAIZ, STATUS_TXT, TIPOS_PROPOSTA, UA, aplicar_simples,  # noqa: E402
                   baixar, baixar_json, carregar_simples, chave_nome, classificar_situacao, fonte, foto_local,
                   hoje, limpa, log, ler_json, nome_proprio, ordenar_propostas, resumo_propostas, salvar_json,
                   sem_acento, sem_mudar_data)
import votacoes as V  # noqa: E402  (categoria, placar, orientações e arquivos de cada votação)
import datetime  # noqa: E402
from mandatos import mes_ano, vigente  # noqa: E402

API = "https://dadosabertos.camara.leg.br/api/v2"
ARQ = "https://dadosabertos.camara.leg.br/arquivos"
PORTAL = "https://www.camara.leg.br"
DOC_ARQUIVOS = "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile"
CC = CACHE / "camara"
VEIC = "Câmara dos Deputados"
# legislatura em curso, pelas datas de posse (scripts/mandatos.py): 57ª de 1º/2/2023 a 31/1/2027, 58ª depois
_VIG = vigente("deputado_federal")
LEG_ATUAL = _VIG["legislatura"]
INICIO_LEG = _VIG["inicio"]
FIM_LEG = (datetime.date.fromisoformat(_VIG["fim"]) - datetime.timedelta(days=1)).isoformat()
DESDE_PT, DESDE_EN = mes_ano(INICIO_LEG)   # "fevereiro de 2023", "February 2023"
HOJE = hoje()
ANO = int(HOJE[:4])
ANO_VOT = int(INICIO_LEG[:4])
PAUSA = 0.05          # entre chamadas à API/portal, por linha de execução
LINHAS = 4            # downloads/chamadas em paralelo

# Cadeiras por UF (LC 78/1993; vale para a 57ª legislatura). Serve para conferir a lista.
CADEIRAS = {"AC": 8, "AL": 9, "AM": 8, "AP": 8, "BA": 39, "CE": 22, "DF": 8, "ES": 10, "GO": 17, "MA": 18,
            "MG": 53, "MS": 8, "MT": 8, "PA": 17, "PB": 12, "PE": 25, "PI": 10, "PR": 30, "RJ": 46, "RN": 8,
            "RO": 8, "RR": 8, "RS": 31, "SC": 16, "SE": 8, "SP": 70, "TO": 8}

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]

csv.field_size_limit(2 ** 31 - 1)
TRAVA = threading.Lock()
DIF_COTA: list[str] = []


# =================================================================== rede e cache
def baixar_lote(url: str, nome: str, max_idade_h: float | None = 20, tentativas: int = 6) -> Path:
    """Igual a comum.baixar_arquivo, mas confere o tamanho recebido (Content-Length).

    O servidor da Câmara às vezes fecha a conexão no meio do arquivo e o urllib, lendo por partes,
    não acusa erro: sem essa conferência ficaríamos com arquivos cortados."""
    destino = CC / nome
    if destino.exists() and destino.stat().st_size > 0:
        if max_idade_h is None or (time.time() - destino.stat().st_mtime) / 3600 < max_idade_h:
            return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    erro = None
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                esperado = r.headers.get("Content-Length")
                n = 0
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
                    n += len(bloco)
            if esperado is not None and n != int(esperado):
                raise IOError(f"download incompleto ({n} de {esperado} bytes)")
            os.replace(tmp, destino)
            return destino
        except urllib.error.HTTPError as e:
            erro = e
            if e.code in (400, 401, 403, 404, 410):
                break
        except Exception as e:  # rede instável
            erro = e
        time.sleep(min(30, 2 ** t))
    if tmp.exists():
        tmp.unlink()
    if destino.exists():
        log(f"  AVISO: não consegui atualizar {nome} ({erro}); usando a cópia anterior")
        return destino
    raise RuntimeError(f"Falha ao baixar {url}: {erro}")


def lote(nome: str, sufixo=None) -> Path:
    arq = f"{nome}-{sufixo}.csv" if sufixo is not None else f"{nome}.csv"
    return baixar_lote(f"{ARQ}/{nome}/csv/{arq}", arq)


def cota_zip(ano: int) -> Path:
    return baixar_lote(f"{PORTAL}/cotas/Ano-{ano}.csv.zip", f"cota-{ano}.csv.zip")


def ler_csv(caminho: Path):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def api(caminho: str, cache: str, max_idade_h: float | None = 20):
    time.sleep(PAUSA)
    return baixar_json(f"{API}/{caminho}", cache=f"camara/api/{cache}", max_idade_h=max_idade_h)


def em_paralelo(func, itens, linhas: int = LINHAS):
    with ThreadPoolExecutor(linhas) as ex:
        return list(ex.map(func, itens))


def id_de(uri: str | None) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


# =================================================================== lista dos deputados em exercício
def lista_em_exercicio() -> list[dict]:
    membros, vistos = [], set()
    for pg in range(1, 20):
        d = api(f"deputados?itens=100&pagina={pg}&ordem=ASC&ordenarPor=nome", f"deputados-p{pg}.json", max_idade_h=1)
        for m in d["dados"]:
            if m["id"] not in vistos:
                vistos.add(m["id"])
                membros.append(m)
        if not any(l.get("rel") == "next" for l in d.get("links", [])):
            break
    por_uf = Counter(m["siglaUf"] for m in membros)
    dif = {uf: (por_uf.get(uf, 0), n) for uf, n in CADEIRAS.items() if por_uf.get(uf, 0) != n}
    if len(membros) != 513 or dif:
        log(f"  AVISO: {len(membros)} deputados em exercício (esperado 513). UF (tem, cadeiras): {dif}")
    return membros


# =================================================================== textos e nomes
def nome_civil(s: str | None) -> str | None:
    n = nome_proprio(limpa(s))
    if not n:
        return None
    n = re.sub(r"([-'’])(\w)", lambda m: m.group(1) + m.group(2).upper(), n)
    return re.sub(r"\b(Ii|Iii|Iv|Vi|Vii)\b", lambda m: m.group(1).upper(), n)


def cargo_dep(genero: str | None) -> str:
    return {"F": "Deputada federal", "M": "Deputado federal"}.get(genero or "", "Deputado(a) federal")


def url_rede(u: str | None) -> str | None:
    u = limpa(u)
    if not u:
        return None
    if not re.match(r"https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    return u


def fmt_milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def nome_despesa(s: str) -> str:
    """'HOSPEDAGEM ,EXCETO DO PARLAMENTAR NO DISTRITO FEDERAL.' -> 'Hospedagem, exceto do parlamentar no Distrito Federal'.
    Só muda maiúsculas/minúsculas e pontuação solta: as palavras são as da descrição oficial."""
    t = limpa(s) or ""
    t = re.sub(r"\s*,\s*", ", ", t).strip().rstrip(".").strip()
    t = t[:1].upper() + t[1:].lower()
    for a, b in (("sigepa", "SIGEPA"), ("rpa", "RPA"), ("distrito federal", "Distrito Federal")):
        t = re.sub(rf"\b{a}\b", b, t)
    return t


# =================================================================== mandato e mandatos anteriores
def legislaturas() -> dict[int, tuple[str, str]]:
    return {int(r["idLegislatura"]): (r["dataInicio"][:10], r["dataFim"][:10]) for r in ler_csv(lote("legislaturas"))}


def _eventos(hist: list[dict], leg: int) -> list[dict]:
    ev = [e for e in hist if e.get("idLegislatura") == leg
          and (e.get("descricaoStatus") or "").startswith(("Entrada", "Saída"))]
    return sorted(ev, key=lambda e: e.get("dataHora") or "")


def mandato_atual(det: dict, hist: list[dict]) -> tuple[str | None, str | None, str | None]:
    """(inicio, obs, condicao). Titular eleito: data da posse. Os demais (suplente, suplente efetivado,
    quem virou titular depois de recontagem): data em que começou o exercício que está valendo agora."""
    st = det.get("ultimoStatus") or {}
    cond = (st.get("condicaoEleitoral") or "").capitalize() or None
    ev = sorted([e for e in hist if e.get("idLegislatura") == LEG_ATUAL and e.get("situacao")],
                key=lambda e: e.get("dataHora") or "")
    posse = next((e for e in ev if "Posse de Eleito Titular" in (e.get("descricaoStatus") or "")), None)
    estado, inicio_periodo = None, None
    for e in ev:
        if e["situacao"] == "Exercício" and estado != "Exercício":
            inicio_periodo = e["dataHora"][:10]
        estado = e["situacao"]
    inicio = posse["dataHora"][:10] if posse else (inicio_periodo or (st.get("data") or "")[:10] or None)
    obs = None
    recontagem = any(re.search(r"recontagem|retotaliza", sem_acento((e.get("descricaoStatus") or "").lower()))
                     and "titular" in (e.get("descricaoStatus") or "").lower() for e in ev)
    if cond == "Suplente":
        obs = "Suplente em exercício"
    elif cond == "Efetivado":
        obs = "Era suplente e virou titular (efetivado)"
    elif recontagem:
        obs = "Virou titular depois da recontagem dos votos"
    return inicio, obs, cond


def mandatos_anteriores(hist: list[dict], legs: dict, genero: str | None) -> list[dict]:
    cargo = cargo_dep(genero)
    out = []
    for leg in sorted({e.get("idLegislatura") for e in hist if e.get("idLegislatura")}, reverse=True):
        if leg >= LEG_ATUAL or leg not in legs:
            continue
        li, lf = legs[leg]
        ev = _eventos(hist, leg)
        if ev:
            entradas = [e for e in ev if e["descricaoStatus"].startswith("Entrada")]
            inicio = (entradas[0] if entradas else ev[0])["dataHora"][:10]
            ult = ev[-1]
            fim = ult["dataHora"][:10] if ult["descricaoStatus"].startswith("Saída") else lf
            inicio, fim = max(inicio, li), min(fim, lf)
            if fim < inicio:
                fim = lf
            out.append({"cargo": cargo, "inicio": inicio, "fim": fim})
        else:
            # a Câmara só registra que a pessoa fez parte da legislatura, sem as datas de entrada e saída
            out.append({"cargo": cargo, "inicio": li, "fim": lf,
                        "obs": "Datas da legislatura: a Câmara não informa as datas exatas deste mandato"})
    return out


# =================================================================== comissões
TIPOS_COMISSAO = {
    "Comissão Permanente", "Comissão Especial", "Comissão Externa", "Comissão Parlamentar de Inquérito",
    "Comissão Parlamentar Mista de Inquérito", "Comissão Mista Permanente", "Comissão Mista Especial",
    "Comissão Mista", "Comissão Medida Provisória", "Comissão Representativa do CN", "Comissão de Sindicância",
    "Subcomissão", "Conselho", "Grupo de Trabalho", "MISTA CPI",
}
PRIORIDADE_PAPEL = ["Presidente", "Vice-Presidente", "Relator", "Coordenador", "Secretário", "Titular", "Suplente"]


def _rank_papel(p: str) -> int:
    for i, k in enumerate(PRIORIDADE_PAPEL):
        if k.lower() in (p or "").lower():
            return i
    return len(PRIORIDADE_PAPEL)


def comissoes_atuais(ids: set[str]) -> dict[str, list[dict]]:
    orgaos = {id_de(r["uri"]): r for r in ler_csv(lote("orgaos"))}
    por_dep: dict[str, dict] = defaultdict(dict)
    for r in ler_csv(lote("orgaosDeputados", f"L{LEG_ATUAL}")):
        dep = id_de(r["uriDeputado"])
        if dep not in ids or (r["dataFim"] and r["dataFim"][:10] < HOJE):
            continue
        oid = id_de(r["uriOrgao"])
        o = orgaos.get(oid, {})
        sigla = limpa(r["siglaOrgao"]) or limpa(o.get("sigla"))
        tipo = o.get("tipoOrgao")
        if sigla == "MESA":
            tipo = "Comissão Diretora"
        elif tipo not in TIPOS_COMISSAO:
            continue  # Mesa (já entra pela sigla MESA), secretarias, procuradorias, ouvidoria, bancadas...
        nome = limpa(r["nomePublicacaoOrgao"]) or limpa(r["nomeOrgao"]) or limpa(o.get("nomePublicacao")) or limpa(o.get("nome"))
        if nome and nome.isupper():  # alguns vêm em maiúsculas no arquivo de membros; o cadastro do órgão tem a grafia normal
            nome = next((n for n in (limpa(o.get("nomePublicacao")), limpa(o.get("nome"))) if n and not n.isupper()), nome)
        if not nome or not sigla:
            continue
        textos = " ".join(filter(None, (sigla, nome, o.get("nome"), o.get("nomePublicacao"), o.get("apelido"))))
        if re.search(r"\bTESTE\b|FICT[IÍ]CI", sem_acento(textos).upper()):
            continue  # órgão de teste do sistema da Câmara ("COMISSÃO FICTÍCIA")
        papel = limpa(r["cargo"]) or "Titular"
        atual = por_dep[dep].get(oid)
        if atual is None or _rank_papel(papel) < _rank_papel(atual["papel"]):
            por_dep[dep][oid] = {"sigla": sigla, "nome": nome, "papel": papel}
    return {d: sorted(v.values(), key=lambda c: (chave_nome(c["nome"]), c["sigla"])) for d, v in por_dep.items()}


# =================================================================== propostas
RANK_PAPEL = {"autor": 0, "coautor": 1, "apoio": 2}
RE_NORMA = re.compile(
    r"transformad[oa]\s+n[oa]\s+"
    r"(lei\s+ordin[aá]ria|lei\s+complementar|lei\s+delegada|lei|decreto\s+legislativo|emenda\s+constitucional|"
    r"emenda\s+[àa]\s+constitui[cç][aã]o|resolu[cç][aã]o(?:\s+d[aoe]\s+(?:c[aâ]mara(?:\s+dos\s+deputados)?|"
    r"senado(?:\s+federal)?|congresso(?:\s+nacional)?))?)"
    r"\s*(?:n[º°o.]*\s*)?(\d[\d.]*)\s*/\s*(\d{2,4})", re.I)
RE_NORMA_EC = re.compile(r"(emenda\s+constitucional)\s*n?[º°o.]*\s*(\d+)\s*(?:/|,\s*de\s+(?:\d{1,2}\s+de\s+\w+\s+de\s+)?)(\d{4})", re.I)


def norma(texto: str | None, tipo_prop: str) -> dict | None:
    """Acha 'Transformado na Lei Ordinária 14801/2024' (e variações) e devolve {nome, url}."""
    if not texto:
        return None
    m = RE_NORMA.search(texto)
    if m:
        especie, num, ano = m.group(1), m.group(2), m.group(3)
    else:
        m = RE_NORMA_EC.search(texto) if tipo_prop == "PEC" else None
        if not m:
            return None
        especie, num, ano = m.group(1), m.group(2), m.group(3)
    num = int(re.sub(r"\D", "", num) or 0)
    ano = int(ano)
    if ano < 100:
        ano += 1900 if ano >= 30 else 2000
    if not num or not (1946 <= ano <= ANO):
        return None
    e = sem_acento(re.sub(r"\s+", " ", especie.lower()))
    if e in ("lei", "lei ordinaria"):
        nome, urn = f"Lei nº {fmt_milhar(num)}/{ano}", f"federal:lei:{ano};{num}"
    elif e == "lei complementar":
        nome, urn = f"Lei Complementar nº {num}/{ano}", f"federal:lei.complementar:{ano};{num}"
    elif e == "lei delegada":
        nome, urn = f"Lei Delegada nº {num}/{ano}", f"federal:lei.delegada:{ano};{num}"
    elif e == "decreto legislativo":
        nome, urn = f"Decreto Legislativo nº {num}/{ano}", f"federal:decreto.legislativo:{ano};{num}"
    elif e.startswith("emenda"):
        nome, urn = f"Emenda Constitucional nº {num}/{ano}", f"federal:emenda.constitucional:{ano};{num}"
    elif "senado" in e:
        nome, urn = f"Resolução do Senado Federal nº {num}/{ano}", f"senado.federal:resolucao:{ano};{num}"
    elif "congresso" in e:
        nome, urn = f"Resolução do Congresso Nacional nº {num}/{ano}", f"congresso.nacional:resolucao:{ano};{num}"
    else:  # resolução (de projeto de resolução da Câmara)
        nome, urn = f"Resolução da Câmara dos Deputados nº {num}/{ano}", f"camara.deputados:resolucao:{ano};{num}"
    return {"nome": nome, "url": f"https://www.lexml.gov.br/urn/urn:lex:br:{urn}"}


def norma_tramitacoes(pid: str, tipo_prop: str, principal: str | None = None) -> tuple[dict | None, bool]:
    """(norma, veto_total) pelo histórico de tramitação. Só para as poucas propostas que viraram norma
    sem o número no último despacho (ou que esperam a análise de um veto). Cache permanente: o número
    de uma lei publicada não muda. Projeto de lei de conversão (PLV): a norma fica registrada na MPV."""
    time.sleep(PAUSA)
    try:
        d = baixar_json(f"{API}/proposicoes/{pid}/tramitacoes", cache=f"camara/tramitacoes/{pid}.json", max_idade_h=None)
    except Exception as e:
        log(f"  [tramitações] {pid}: {e}")
        return None, False
    eventos = sorted(d.get("dados") or [], key=lambda e: (e.get("dataHora") or "", e.get("sequencia") or 0), reverse=True)
    veto_total = any(re.search(r"vetad[oa]\s+totalmente", sem_acento((e.get("despacho") or "") + " " + (e.get("descricaoTramitacao") or "")), re.I)
                     for e in eventos)
    for ev in eventos:
        n = norma(ev.get("despacho"), tipo_prop)
        if n:
            return n, veto_total
    if principal and tipo_prop == "PLV":
        n, vt = norma_tramitacoes(principal, "MPV")
        return n, veto_total or vt
    return None, veto_total


def ler_autores(ids: set[str], anos) -> tuple[dict, dict]:
    """papel[dep][pid] = autor | coautor | apoio ; primeiro[pid] = id do 1º signatário (se deputado).

    Regra (RICD, art. 102, e o próprio portal da Câmara): o 1º signatário é o AUTOR; quem assina como
    proponente depois dele é COAUTOR; quem só dá 'apoiamento' (proponente = 0, como nas assinaturas
    exigidas para apresentar uma PEC) é APOIO e não entra na lista de propostas."""
    papel: dict[str, dict] = defaultdict(dict)
    primeiro: dict[str, str | None] = {}
    for ano in anos:
        linhas = defaultdict(list)
        for r in ler_csv(lote("proposicoesAutores", ano)):
            linhas[r["idProposicao"]].append(r)
        for pid, rs in linhas.items():
            nossos = [r for r in rs if r["idDeputadoAutor"] in ids and r["codTipoAutor"] == "10000"]
            if not nossos:
                continue
            props = [r for r in rs if r["proponente"] == "1"]
            com_ordem = [r for r in props if (r["ordemAssinatura"] or "").isdigit() and int(r["ordemAssinatura"]) > 0]
            p1 = None
            if com_ordem:
                p1 = min(com_ordem, key=lambda r: int(r["ordemAssinatura"]))
            elif len(props) == 1:
                p1 = props[0]
            primeiro[pid] = p1["idDeputadoAutor"] if (p1 is not None and p1["codTipoAutor"] == "10000") else None
            for r in nossos:
                p = ("autor" if r is p1 else "coautor") if r["proponente"] == "1" else "apoio"
                dep = r["idDeputadoAutor"]
                if pid not in papel[dep] or RANK_PAPEL[p] < RANK_PAPEL[papel[dep][pid]]:
                    papel[dep][pid] = p
    return papel, primeiro


CAMPOS_PROP = ("siglaTipo", "numero", "ano", "ementa", "dataApresentacao", "uriPropPrincipal",
               "ultimoStatus_dataHora", "ultimoStatus_descricaoTramitacao", "ultimoStatus_descricaoSituacao",
               "ultimoStatus_despacho")


def ler_proposicoes(pids: set[str], anos) -> tuple[dict, dict, dict]:
    """dados[pid] (campos completos só para os tipos da lista), sigla[pid] de todas as propostas da lista
    (para dizer com qual proposta uma apensada anda junto) e temas[pid]."""
    dados, sigla = {}, {}
    for ano in anos:
        for r in ler_csv(lote("proposicoes", ano)):
            t = r["siglaTipo"]
            if t in TIPOS_PROPOSTA:
                sigla[r["id"]] = f"{t} {r['numero']}/{r['ano']}"
            if r["id"] in pids:
                dados[r["id"]] = {k: r[k] for k in CAMPOS_PROP} if t in TIPOS_PROPOSTA else {"siglaTipo": t}
    temas = defaultdict(set)
    for ano in anos:
        for r in ler_csv(lote("proposicoesTemas", ano)):
            pid = id_de(r["uriProposicao"])
            if pid in dados and "ementa" in dados[pid] and limpa(r["tema"]):
                temas[pid].add(limpa(r["tema"]))
    return dados, sigla, {k: sorted(v, key=chave_nome) for k, v in temas.items()}


TXT_VETO_TOTAL_PENDENTE = "O presidente vetou tudo; o Congresso ainda vai decidir sobre o veto"
TXT_DEVOLVIDA = "Devolvida ao autor: a Presidência da Câmara não deixou seguir"
TXT_PREJUDICADA = "Ficou prejudicada (outra decisão fez ela perder o sentido)"


def txt_arquivada(d: str, tram: str, data_st: str, com_ano: bool) -> str:
    """d e tram já em minúsculas e sem acento."""
    no_senado = "comunica o arquivamento" in d or (re.search(r"\bsf\b|senado federal", d) and "arquiv" in d)
    base = "Arquivada no Senado" if no_senado else "Arquivada"
    return f"{base} em {data_st[:4]}" if (data_st and (com_ano or no_senado)) else base


def status_proposta(p: dict, sigla: dict, genero_primeiro: str | None) -> tuple[str, str, str]:
    """(status, statusTxt, motivo). Regras da Câmara antes de comum.classificar_situacao()."""
    sit = limpa(p["ultimoStatus_descricaoSituacao"]) or ""
    s = sem_acento(sit.lower())
    tram = sem_acento((p["ultimoStatus_descricaoTramitacao"] or "").lower())
    desp = p["ultimoStatus_despacho"] or ""
    d = sem_acento(desp.lower())
    data_st = (p["ultimoStatus_dataHora"] or "")[:10]
    principal = sigla.get(id_de(p["uriPropPrincipal"])) if p["uriPropPrincipal"] else None
    junto = f"Andando junto com outra proposta parecida ({principal})" if principal else "Andando junto com outra proposta parecida"

    if s in ("", "<nao definido>"):
        texto = d + " " + tram
        if p["uriPropPrincipal"]:
            return "junta", junto, "vazia + apensada (uriPropPrincipal)"
        if re.search(r"(?<!des)arquiva(d|mento)|arquive-se|\barquivo\b", texto) and "desarquiv" not in texto:
            return "arquivada", txt_arquivada(d, tram, data_st, True), "vazia + arquivamento"
        if re.search(r"devolva-se|devolvid[oa] ao autor|devolucao ao autor", texto):
            return "parada", TXT_DEVOLVIDA, "vazia + devolvida ao autor"
        if "prejudicad" in texto and "pela prejudicialidade" not in texto:
            return "parada", TXT_PREJUDICADA, "vazia + prejudicada"
        if re.search(r"veto total|vetad[oa] totalmente", texto):
            return "rejeitada", "O presidente vetou a proposta inteira", "vazia + veto total"
        if re.search(r"solicitando a retirada|retirad[oa] pel[oa] autor", texto):
            return "retirada", ("A autora desistiu" if genero_primeiro == "F" else "O autor desistiu"), "vazia + retirada"
        if re.search(r"remessa ao senado|remetid[oa] ao senado", texto):
            return "aprovada", "Aprovada na Câmara; agora está no Senado", "vazia + remetida ao Senado"
        if data_st >= INICIO_LEG:
            if ("apresentacao de proposicao" in tram and re.match(r"apresentacao d[oa] ", d)
                    and (p["dataApresentacao"] or "")[:10] == data_st):
                return "andando", "Apresentada; ainda vai começar a ser analisada", "vazia + acabou de ser apresentada"
            return "andando", "Ainda em discussão", "vazia + movimento nesta legislatura"
        return "outra", "A Câmara não informa a situação", "vazia + antiga"
    if s.startswith("transformado em norma"):
        return "lei", "", "norma"
    if s == "arquivada":
        return "arquivada", txt_arquivada(d, tram, data_st, "arquivamento" in tram), "regra comum"
    if s.startswith("transformado em nova proposicao"):
        m = re.search(r"renumerad[oa] como\s+([A-Z]{2,4})\s*(\d+)\s*/\s*(\d{2,4})", desp, re.I)
        if m:
            a = int(m.group(3))
            a = a + 2000 if a < 100 else a
            return "outra", f"Virou outra proposta: {m.group(1).upper()} {m.group(2)}/{a}", "renumerada"
        return "outra", "Virou outra proposta", "renumerada"
    if "devolvid" in s and "autor" in s:
        return "parada", TXT_DEVOLVIDA, "devolvida ao autor"
    if "apreciacao do veto" in s:
        if "parcial" in d or "parcial" in tram:
            return "lei", "", "veto parcial (norma)"
        if "totalmente" in d or "vetado totalmente" in tram:
            return "rejeitada", TXT_VETO_TOTAL_PENDENTE, "veto total pendente"
        return "veto?", "", "veto pendente (ver tramitação)"
    if "aguardando autografos" in s or "envio ao senado" in s:
        return "aprovada", "Aprovada na Câmara; esperando ser enviada para a próxima etapa", "aprovada (autógrafos)"
    if "redacao final" in s:
        return "andando", "Aprovada; falta votar o texto final na Câmara", "aguardando redação final"
    if "analise de inconstitucionalidade" in s:
        return "andando", "Apresentada; em análise inicial na Câmara", "análise inicial"
    if "perdeu a eficacia" in s or "sem eficacia" in s:
        return "parada", "Perdeu a validade antes de virar lei", "perdeu a eficácia"
    if "vetado totalmente" in s:
        return "rejeitada", "O presidente vetou a proposta inteira", "veto total"

    st = classificar_situacao(sit)
    if st == "aprovada":
        if "senado" in s:
            txt = "Aprovada na Câmara; agora está no Senado"
        elif "sancao" in s:
            txt = "Aprovada; esperando a decisão do presidente da República"
        elif "promulga" in s:
            txt = "Aprovada; esperando ser promulgada"
        else:
            txt = STATUS_TXT["aprovada"]
        return st, txt, "regra comum"
    if st == "junta":
        return st, junto, "regra comum"
    if st == "arquivada":
        return st, txt_arquivada(d, tram, data_st, "arquivamento" in tram), "regra comum"
    if st == "retirada":
        return st, ("A autora desistiu" if genero_primeiro == "F" else "O autor desistiu"), "regra comum"
    if st == "andando":
        if "pronta para pauta" in s:
            return st, "Pronta para ser votada", "regra comum"
        return st, "Ainda em discussão", "regra comum"
    if st == "parada":
        if "prejudicad" in s:
            return st, TXT_PREJUDICADA, "regra comum"
        if "devolvid" in s:
            return st, TXT_DEVOLVIDA, "regra comum"
        if "eficacia" in s or "convertid" in s:
            return st, "Perdeu a validade antes de virar lei", "regra comum"
        return st, "Parou (não vai mais ser votada)", "regra comum"
    if st == "rejeitada":
        return st, "Rejeitada", "regra comum"
    return st, STATUS_TXT.get(st, ""), "regra comum"


def verificar_lexml(urls: set[str]) -> dict[str, bool | None]:
    """Confere se cada link do LexML abre a norma (o LexML não tem todas as resoluções da Câmara, e leis
    muito recentes podem demorar a entrar). Cache: positivo para sempre, negativo por 7 dias."""
    arq = CC / "lexml.json"
    cache = ler_json(arq, {}) or {}
    agora = time.time()
    faltam = [u for u in urls if u not in cache or (not cache[u]["ok"] and agora - cache[u]["t"] > 7 * 86400)]

    def um(u):
        time.sleep(PAUSA)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read(400_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return u, (False if e.code == 404 else None)
        except Exception:
            return u, None
        t = re.search(r"<title>(.*?)</title>", b, re.S | re.I)
        titulo = sem_acento((t.group(1) if t else "").lower())
        if "nao encontrad" in titulo:
            return u, False
        if "verificacao de seguranca" in titulo or not titulo.strip():
            return u, None  # página de proteção ou vazia: não dá para saber agora
        return u, True

    for u, ok in em_paralelo(um, faltam):
        if ok is not None:
            cache[u] = {"ok": ok, "t": agora}
    if faltam:
        salvar_json(arq, cache)
    return {u: (cache[u]["ok"] if u in cache else None) for u in urls}


def txt_lei(lei: dict | None, tipo: str) -> str:
    if lei:
        artigo = "o" if lei["nome"].startswith("Decreto") else "a"
        return f"Virou {artigo} {lei['nome']}"
    return {"PEC": "Virou emenda à Constituição", "PDL": "Virou decreto legislativo", "PDC": "Virou decreto legislativo",
            "PDS": "Virou decreto legislativo", "PRC": "Virou resolução da Câmara",
            "PRN": "Virou resolução do Congresso", "PRS": "Virou resolução do Senado"}.get(tipo, "Virou lei")


# =================================================================== votações
def lote_vot(nome: str, ano: int, idade: float | None = 20) -> Path:
    """Arquivo anual de votações (idade = horas até baixar de novo; None = usa o cache como estiver)."""
    arq = f"{nome}-{ano}.csv"
    return baixar_lote(f"{ARQ}/{nome}/csv/{arq}", arq, max_idade_h=idade)


def ler_votacoes(ids: set[str], idade: float | None = 20) -> tuple[dict, dict]:
    """Votações nominais do Plenário desde o início da legislatura (arquivos votacoes, votacoesProposicoes,
    votacoesVotos e votacoesOrientacoes). Devolve (itens, {"votos": {deputado: [(id da votação, voto)]}, "secretas"}).
    Além dos campos do catálogo, cada item leva o que scripts/votacoes.py precisa para o arquivo de detalhes:
    _votos (todos que votaram, inclusive quem não está mais no mandato), _orient, _ementa, _portal, _fontes..."""
    vot = {}
    for ano in range(ANO_VOT, ANO + 1):
        for r in ler_csv(lote_vot("votacoes", ano, idade)):
            if r["siglaOrgao"] == "PLEN" and r["data"] >= INICIO_LEG:
                vot[r["id"]] = {"data": r["data"][:10], "dh": r["dataHoraRegistro"] or r["data"],
                                "descricao": limpa(r["descricao"]), "aprovacao": r["aprovacao"],
                                "evento": (r.get("idEvento") or "").strip()}
    objs = defaultdict(list)
    for ano in range(ANO_VOT, ANO + 1):
        for r in ler_csv(lote_vot("votacoesProposicoes", ano, idade)):
            if r["idVotacao"] in vot:
                objs[r["idVotacao"]].append(r)
    votos = defaultdict(list)
    todos = defaultdict(list)
    com_voto = Counter()
    for ano in range(ANO_VOT, ANO + 1):
        for r in ler_csv(lote_vot("votacoesVotos", ano, idade)):
            if r["idVotacao"] not in vot:
                continue
            voto = limpa(r["voto"])
            if voto:
                com_voto[r["idVotacao"]] += 1
                todos[r["idVotacao"]].append((f"dep-{r['deputado_id']}", limpa(r["deputado_nome"]),
                                              V.nome_partido(r["deputado_siglaPartido"]), limpa(r["deputado_siglaUf"]), voto))
            if r["deputado_id"] in ids:
                votos[r["deputado_id"]].append((r["idVotacao"], voto))
    orient = defaultdict(list)
    for ano in range(ANO_VOT, ANO + 1):
        for r in ler_csv(lote_vot("votacoesOrientacoes", ano, idade)):
            if r["idVotacao"] in vot:
                orient[r["idVotacao"]].append((r["siglaBancada"], r["orientacao"]))
    # votações secretas: a Câmara registra a presença, mas nenhum voto (não mostram o voto de cada um)
    secretas = {v for v in {i for lst in votos.values() for i, _ in lst} if not com_voto[v]}
    itens = {}
    for vid, v in vot.items():
        if not com_voto[vid]:
            continue
        principal = None
        cands = objs.get(vid, [])
        if cands:
            boas = [c for c in cands if c["proposicao_siglaTipo"] in TIPOS_PROPOSTA]
            prefixo = vid.split("-")[0]
            principal = (next((c for c in boas if c["proposicao_id"] == prefixo), None) or (boas[0] if boas else None)
                         or next((c for c in cands if c["proposicao_id"] == prefixo), None) or cands[0])
        pid = principal["proposicao_id"] if principal else None
        sig = None
        if principal:
            if principal["proposicao_numero"] and principal["proposicao_ano"] and principal["proposicao_ano"] != "0":
                sig = f"{principal['proposicao_siglaTipo']} {principal['proposicao_numero']}/{principal['proposicao_ano']}"
            else:
                sig = limpa(principal["proposicao_titulo"])
        ev = v["evento"] if v["evento"] not in ("", "0") else None
        dia = f"{v['data'][8:10]}/{v['data'][5:7]}/{v['data'][:4]}"
        portal = f"{PORTAL}/presenca-comissoes/votacao-portal?reuniao={ev}" if ev else None
        prop_url = f"{PORTAL}/propostas-legislativas/{pid}" if pid else None
        itens[vid] = {
            "data": v["data"], "hora": v["dh"][11:16] or None, "propostaId": f"camara:{pid}" if pid else None,
            "proposta": sig, "descricao": v["descricao"],
            "resultado": {"1": "Aprovado", "0": "Rejeitado"}.get(v["aprovacao"]),
            "url": prop_url or f"{API}/votacoes/{vid}",
            "_dh": v["dh"],
            "_votos": todos.get(vid, []), "_orient": orient.get(vid, []),
            "_ementa": limpa(principal["proposicao_ementa"]) if principal else None,
            "_propUrl": prop_url, "_portal": portal,
            "_oficial": V.placar_da_descricao(v["descricao"]),
            "_fontes": ([fonte(VEIC, f"Votação nominal no portal da Câmara (sessão de {dia}: escolha a votação na lista)", portal, HOJE)]
                        if portal else []) +
                       [fonte(VEIC, f"Dados Abertos: votação {vid} (o que foi votado, votos de cada deputado e orientações)",
                              f"{API}/votacoes/{vid}", HOJE)] +
                       ([fonte(VEIC, f"Página da proposta {sig}", prop_url, HOJE)] if prop_url else []),
        }
    return itens, {"votos": votos, "secretas": secretas}


ARQ_VOTACOES = "dados/votacoes/camara.json"   # caminho relativo ao site (vai em votacoes.arquivo)
# "hora", "categoria" e "placar" vêm de scripts/votacoes.py (preparar); os outros campos são os de antes
CAMPOS_VOTACAO = ("data", "hora", "propostaId", "proposta", "descricao", "resultado", "categoria", "placar", "url")


def _ordem_votacao(itens: dict):
    """Da mais nova para a mais antiga: data, hora do registro e id (desempate estável)."""
    return lambda vid: (itens[vid]["data"], itens[vid]["_dh"], vid)


def catalogo_votacoes(itens: dict) -> dict:
    """dados/votacoes/camara.json: cada votação uma única vez. Chave = id da votação na Câmara
    (ex.: "2236186-60", o mesmo de /api/v2/votacoes/{id}), sem prefixo. Os detalhes de cada uma (quem votou o quê,
    orientações) ficam em dados/votacoes/camara/<id>.json. Precisa de votacoes.preparar() antes."""
    return {
        "atualizado": HOJE,
        "fonte": fonte(VEIC, f"Dados Abertos: votações nominais do Plenário de fevereiro de {ANO_VOT} a "
                             f"{HOJE[8:10]}/{HOJE[5:7]}/{ANO} (arquivos votacoes, votacoesProposicoes, votacoesVotos e "
                             "votacoesOrientacoes)",
                       DOC_ARQUIVOS, HOJE),
        "votacoes": {vid: {k: itens[vid].get(k) for k in CAMPOS_VOTACAO}
                     for vid in sorted(itens, key=_ordem_votacao(itens), reverse=True)},
    }


def bloco_votacoes(dep: str, itens: dict, votos: dict) -> dict:
    """Só o voto de cada um: [["<id da votação>", "Sim"], ...]. Os detalhes ficam em dados/votacoes/camara.json.
    Quando o partido do deputado NA ÉPOCA recebeu orientação publicada, o par ganha mais dois elementos:
    ["<id>", "Sim", "Não", "b"] = orientação e de quem veio (p = do partido, f = da federação, b = do bloco)."""
    pares, vistos = [], set()
    for vid, voto in votos.get(dep, []):
        if vid in itens and vid not in vistos:
            vistos.add(vid)
            pares.append([vid, voto] + (V.orientacao_da_pessoa(itens[vid], f"dep-{dep}") or []))
    ordem = _ordem_votacao(itens)
    pares.sort(key=lambda p: ordem(p[0]), reverse=True)
    resumo = {"total": len(pares), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
    for par in pares:
        voto = par[1]
        resumo[voto if voto in ("Sim", "Não", "Abstenção", "Obstrução") else "Outro"] += 1
    return {
        "escopo": f"Votações com voto de cada um (nominais) no Plenário da Câmara desde {DESDE_PT}",
        "escopo_en": f"Roll-call votes (where each member's vote is recorded) in the full Chamber of Deputies since {DESDE_EN}.",
        "resumo": resumo,
        "fonte": fonte(VEIC, f"Dados Abertos: votações nominais do Plenário de fevereiro de {ANO_VOT} a {HOJE[8:10]}/{HOJE[5:7]}/{ANO} (votos de cada deputado)",
                       f"{PORTAL}/deputados/{dep}/votacoes-nominais-plenario/{ANO}", HOJE),
        "arquivo": ARQ_VOTACOES,
        "votos": pares,
    }


# =================================================================== gastos (cota parlamentar)
RE_TIPO_COTA = re.compile(r'id="linkSumarizado(\d+)"[^>]*>\s*([^<]+?)\s*</a>', re.S)
RE_VAL_COTA = re.compile(r'id="sumarizado(\d+)"[^>]*>\s*(-?)\s*R\$\s*(-?[\d.,]+)', re.S)  # "-R$ 158,41" = estorno


def valor_br(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def ler_cota_csv(ids: set[str]) -> dict:
    """Soma do valor líquido por deputado, ano, mês e tipo (arquivos oficiais). Serve de conferência
    e de reserva se a página do portal falhar. Também dá o nuDeputadoId usado pelo portal."""
    nu, soma = {}, defaultdict(lambda: defaultdict(float))
    ultimo = 0
    for ano in range(ANO_VOT, ANO + 1):
        z = zipfile.ZipFile(cota_zip(ano))
        with z.open(z.namelist()[0]) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", newline=""), delimiter=";"):
                ide = r["ideCadastro"]
                mes = int(r["numMes"] or 0)
                a = int(r["numAno"] or 0)
                if a == ANO and mes:
                    ultimo = max(ultimo, mes)
                if ide not in ids:
                    continue
                if r["nuDeputadoId"]:
                    nu[ide] = r["nuDeputadoId"]
                if (a, mes) < (ANO_VOT, 2):
                    continue  # janeiro de 2023 ainda é a legislatura anterior
                soma[ide][(a, mes, r["txtDescricao"])] += float(r["vlrLiquido"] or 0)
    return {"nu": nu, "soma": soma, "ultimo_mes": ultimo or None}


def nu_pelo_portal(dep: str) -> str | None:
    """nuDeputadoId (código da cota) pela página de consulta, para quem não aparece nos arquivos."""
    url = f"{PORTAL}/cota-parlamentar/consulta-cota-parlamentar?ideDeputado={dep}&dataInicio=02{ANO_VOT}&dataFim=12{ANO}"
    try:
        b = baixar(url, CC / "cota" / f"{dep}-consulta.html", max_idade_h=20, tentativas=3, timeout=60).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r"nuDeputadoId=(\d+)", b)
    return m.group(1) if m else None


def cota_portal(dep: str, nu: str, ini: str, fim: str) -> dict | None:
    """Página 'sumarizado' do portal (mesmos valores do arquivo + passagens SIGEPA). {tipo: valor}."""
    url = (f"{PORTAL}/cota-parlamentar/sumarizado?nuDeputadoId={nu}&dataInicio={ini}&dataFim={fim}&despesa="
           f"&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf="
           f"&filtroNivel1=1&filtroNivel2=2&filtroNivel3=3")
    time.sleep(PAUSA)
    try:
        b = baixar(url, CC / "cota" / f"{dep}-{ini.replace('/', '')}-{fim.replace('/', '')}.html",
                   max_idade_h=20, tentativas=2, timeout=60).decode("utf-8", "replace")
    except Exception as e:
        # o portal devolve erro 500 quando o período não tem despesas (tratado em bloco_gastos)
        return None
    tipos = {m.group(1): html.unescape(m.group(2)) for m in RE_TIPO_COTA.finditer(b)}
    vals = {m.group(1): (-1 if m.group(2) else 1) * valor_br(m.group(3)) for m in RE_VAL_COTA.finditer(b)}
    if tipos.keys() != vals.keys():
        return None
    if not tipos and "Resultado da pesquisa" not in b:
        return None  # página diferente do esperado
    out = defaultdict(float)
    for k, t in tipos.items():
        out[limpa(t)] += vals[k]
    return dict(out)


def bloco_gastos(dep: str, cota: dict, conferencia: Counter) -> dict:
    nu = cota["nu"].get(dep) or nu_pelo_portal(dep)
    soma = cota["soma"].get(dep, {})
    mes = cota["ultimo_mes"] or int(HOJE[5:7])

    def do_csv(a0, m0, a1, m1):
        out = defaultdict(float)
        for (a, m, t), v in soma.items():
            if (a0, m0) <= (a, m) <= (a1, m1):
                out[t] += v
        return out

    ano_csv = do_csv(ANO, 1, ANO, 12)
    mand_csv = do_csv(ANO_VOT, 2, ANO, 12)
    ano_p = cota_portal(dep, nu, f"1/{ANO}", f"12/{ANO}") if nu else None
    mand_p = cota_portal(dep, nu, f"2/{ANO_VOT}", f"12/{ANO}") if nu else None
    if nu and ano_p is None and mand_p is not None:
        # o portal responde erro 500 quando o período não tem nenhuma despesa: ano = mandato - anos anteriores
        antes = cota_portal(dep, nu, f"2/{ANO_VOT}", f"12/{ANO - 1}")
        if antes is not None:
            ano_p = {t: v - antes.get(t, 0.0) for t, v in mand_p.items()}
    url = f"{PORTAL}/cota-parlamentar/consulta-cota-parlamentar?ideDeputado={dep}&dataInicio=01{ANO}&dataFim=12{ANO}"
    periodo = f"janeiro a {MESES[mes - 1]} de {ANO}" if mes > 1 else f"janeiro de {ANO}"
    ate = f"lançamentos até {HOJE[8:10]}/{HOJE[5:7]}/{ANO}"
    if ano_p is not None and mand_p is not None:
        dif = False
        # conferência: o que está no arquivo deve bater com o portal (o portal tem a mais SIGEPA e outros itens)
        for base, port in ((ano_csv, ano_p), (mand_csv, mand_p)):
            for t, v in base.items():
                if abs(port.get(limpa(t), 0.0) - v) > 0.01:
                    dif = True
        with TRAVA:
            conferencia["portal"] += 1
            if dif:
                conferencia["diferenca"] += 1
                DIF_COTA.append(dep)
        por_tipo, total, total_m = ano_p, sum(ano_p.values()), sum(mand_p.values())
        titulo = (f"Cota parlamentar (CEAP) de {ANO}: valor líquido de {periodo} ({ate}), "
                  f"pela consulta oficial do portal da Câmara")
    elif not nu and not soma:
        with TRAVA:
            conferencia["sem_despesa"] += 1
        por_tipo, total, total_m = {}, 0.0, 0.0
        titulo = f"Cota parlamentar (CEAP) de {ANO}: nenhuma despesa lançada para este mandato ({ate})"
    else:
        with TRAVA:
            conferencia["arquivo"] += 1
            DIF_COTA.append(f"{dep}(arquivo)")
        por_tipo, total, total_m = ano_csv, sum(ano_csv.values()), sum(mand_csv.values())
        titulo = (f"Cota parlamentar (CEAP) de {ANO}: valor líquido de {periodo} ({ate}), pelo arquivo de dados abertos "
                  f"(a consulta do portal falhou; o arquivo não traz passagens aéreas do sistema da Câmara, o SIGEPA)")
    lista = [{"tipo": nome_despesa(t), "valor": round(v, 2)} for t, v in por_tipo.items() if abs(v) >= 0.005]
    lista.sort(key=lambda x: (-x["valor"], chave_nome(x["tipo"])))
    return {"ano": ANO, "total": round(total, 2), "porTipo": lista, "mandatoTotal": round(total_m, 2), "desde": INICIO_LEG[:7],
            "fonte": fonte(VEIC, titulo, url, HOJE)}


# =================================================================== montagem
def fontes_perfil(dep: str) -> list[dict]:
    return [
        fonte(VEIC, f"Página do(a) deputado(a) {dep} no portal da Câmara", f"{PORTAL}/deputados/{dep}", HOJE),
        fonte(VEIC, f"Dados Abertos: ficha e histórico do(a) deputado(a) {dep}", f"{API}/deputados/{dep}", HOJE),
        fonte(VEIC, "Dados Abertos: arquivos de proposições, autores, temas, órgãos e votações", DOC_ARQUIVOS, HOJE),
        fonte(VEIC, "Cota parlamentar (CEAP): consulta no portal e arquivos Ano-AAAA.csv.zip",
              f"{PORTAL}/cota-parlamentar/", HOJE),
    ]


def _sem_datas(o):
    """Para comparar perfis ignorando só as datas de consulta das fontes e o 'atualizado'."""
    if isinstance(o, dict):
        return {k: _sem_datas(v) for k, v in o.items()
                if not (k == "atualizado" or (k == "data" and "veiculo" in o))}
    if isinstance(o, list):
        return [_sem_datas(v) for v in o]
    return o


def salvar_sem_ruido(caminho: Path, novo: dict) -> bool:
    """salvar_json() só quando há mudança real. Como comum.sem_mudar_data(), mas ignora também a data de
    consulta das fontes (fonte.data), que muda todo dia mesmo sem o dado mudar."""
    antigo = ler_json(caminho)
    if isinstance(antigo, dict):
        # campos que outros coletores preenchem (TSE): não apagar
        for k in ("eleicao", "eleicao2026", "bens"):
            if novo.get(k) is None and antigo.get(k) is not None:
                novo[k] = antigo[k]
        if _sem_datas(antigo) == _sem_datas(novo):
            return False
    return salvar_json(caminho, sem_mudar_data(novo, caminho))


def montar_lista(membros: list[dict], info: dict) -> dict:
    caminho = DADOS / "camara.json"
    antigo = ler_json(caminho, {}) or {}
    e26 = {m["id"]: m.get("eleicao2026") for m in antigo.get("membros", []) if isinstance(m, dict)}
    lst = []
    for m in membros:
        pid = f"dep-{m['id']}"
        i = info[str(m["id"])]
        lst.append({"id": pid, "nome": i["nome"], "partido": i["partido"], "uf": i["uf"], "foto": i["foto"],
                    "genero": i["genero"], "eleicao2026": e26.get(pid)})
    lst.sort(key=lambda x: (chave_nome(x["nome"]), x["id"]))
    pp = Counter(x["partido"] or "Sem partido" for x in lst)
    return {
        "total": len(lst),
        "porPartido": [{"partido": p, "n": n} for p, n in sorted(pp.items(), key=lambda x: (-x[1], chave_nome(x[0])))],
        "membros": lst,
        "fonte": fonte(VEIC, "Dados Abertos: deputados federais em exercício", f"{PORTAL}/deputados/quem-sao", HOJE),
        "atualizado": HOJE,
    }


def info_basica(membros: list[dict]) -> dict:
    """Nome, partido, UF, gênero e foto de cada um (o que a lista precisa)."""
    sexo = {id_de(r["uri"]): r["siglaSexo"] for r in ler_csv(lote("deputados"))}

    def um(m):
        return str(m["id"]), foto_local(m.get("urlFoto"), f"dep-{m['id']}")

    fotos = dict(em_paralelo(um, membros))
    info = {}
    for m in membros:
        d = str(m["id"])
        info[d] = {"nome": limpa(m["nome"]), "partido": limpa(m.get("siglaPartido")), "uf": m.get("siglaUf"),
                   "foto": fotos.get(d), "genero": sexo.get(d) or None, "email": m.get("email")}
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-lista", action="store_true", help="só dados/camara.json (e fotos)")
    ap.add_argument("--ids", help="só esses deputados (ids da Câmara separados por vírgula)")
    a = ap.parse_args()
    t0 = time.time()
    CC.mkdir(parents=True, exist_ok=True)

    log("Câmara: lista dos deputados em exercício")
    membros = lista_em_exercicio()
    log(f"  {len(membros)} em exercício")
    info = info_basica(membros)
    if a.so_lista or not a.ids:
        lst = montar_lista(membros, info)
        if lst["total"] >= 500:
            salvar_sem_ruido(DADOS / "camara.json", lst)
            log(f"  dados/camara.json: {lst['total']} membros")
        else:
            log("  AVISO: lista pequena demais, dados/camara.json não foi reescrito")
    if a.so_lista:
        log(f"Pronto em {time.time() - t0:.0f}s")
        return

    todos = {str(m["id"]) for m in membros}
    if a.ids:
        alvo = [x.strip() for x in a.ids.split(",") if x.strip()]
        fora = [x for x in alvo if x not in todos]
        if fora:
            log(f"  AVISO: não estão em exercício (ignorados): {fora}")
        ids = {x for x in alvo if x in todos}
    else:
        ids = todos
    if not ids:
        return

    log(f"Ficha e histórico de {len(ids)} deputados (API)")
    def ficha(d):
        det = api(f"deputados/{d}", f"deputado-{d}.json")["dados"]
        hist = api(f"deputados/{d}/historico", f"historico-{d}.json")["dados"]
        return d, det, hist
    fichas = {d: (det, hist) for d, det, hist in em_paralelo(ficha, sorted(ids))}

    legs = legislaturas()
    leg_ini = min(int(r["idLegislaturaInicial"]) for r in ler_csv(lote("deputados")) if id_de(r["uri"]) in ids)
    ano_ini = int(legs[leg_ini][0][:4])
    anos = range(ano_ini, ANO + 1)
    log(f"Arquivos em lote: proposições de {ano_ini} a {ANO} (1º mandato mais antigo: {leg_ini}ª legislatura), votações e cota")
    tarefas = [(n, ano) for ano in reversed(anos) for n in ("proposicoesAutores", "proposicoes", "proposicoesTemas")]
    tarefas += [(n, ano) for ano in range(ANO_VOT, ANO + 1)
                for n in ("votacoes", "votacoesVotos", "votacoesProposicoes", "votacoesOrientacoes")]
    tarefas += [(n, None) for n in ("orgaos", "deputadosProfissoes")] + [("orgaosDeputados", f"L{LEG_ATUAL}")]
    em_paralelo(lambda t: lote(*t), tarefas)
    em_paralelo(cota_zip, list(range(ANO_VOT, ANO + 1)))
    log(f"  arquivos prontos ({time.time() - t0:.0f}s)")

    profissoes = defaultdict(set)
    for r in ler_csv(lote("deputadosProfissoes")):
        if r["id"] in ids and limpa(r["titulo"]):
            profissoes[r["id"]].add(limpa(r["titulo"]))
    comissoes = comissoes_atuais(ids)
    sexo_todos = {id_de(r["uri"]): r["siglaSexo"] for r in ler_csv(lote("deputados"))}

    log("Propostas: autores")
    papel, primeiro = ler_autores(ids, anos)
    pids = {pid for dep in papel.values() for pid in dep}
    log(f"  {sum(len(v) for v in papel.values())} assinaturas em {len(pids)} proposições ({time.time() - t0:.0f}s)")
    log("Propostas: proposições e temas")
    dados_prop, sigla, temas = ler_proposicoes(pids, anos)
    log(f"  {len(dados_prop)} encontradas nos arquivos; {len(pids - set(dados_prop))} sem registro nos arquivos anuais ({time.time() - t0:.0f}s)")

    # status de cada proposta da lista (uma vez por proposta)
    st_prop = {}
    for pid, p in dados_prop.items():
        if "ementa" not in p:
            continue
        g1 = sexo_todos.get(primeiro.get(pid) or "")
        st, txt, motivo = status_proposta(p, sigla, g1)
        lei = None
        if st == "lei":
            lei = norma(p["ultimoStatus_despacho"], p["siglaTipo"])
        st_prop[pid] = [st, txt, motivo, lei]
    faltam = [pid for pid, v in st_prop.items() if (v[0] == "lei" and not v[3]) or v[0] == "veto?"]
    log(f"Normas: {sum(1 for v in st_prop.values() if v[0] == 'lei')} viraram norma; {len(faltam)} sem número no último despacho "
        f"(ou com veto pendente) -> histórico de tramitação (cache permanente)")
    res = em_paralelo(lambda pid: norma_tramitacoes(pid, dados_prop[pid]["siglaTipo"], id_de(dados_prop[pid]["uriPropPrincipal"]) or None), faltam)
    for pid, (n, veto_total) in zip(faltam, res):
        v = st_prop[pid]
        if v[0] == "veto?":
            if n:
                v[0], v[2] = "lei", "veto parcial (norma, pela tramitação)"
            elif veto_total:
                v[0], v[1], v[2] = "rejeitada", TXT_VETO_TOTAL_PENDENTE, "veto total pendente (pela tramitação)"
            else:
                v[0], v[1], v[2] = "outra", "Esperando o Congresso decidir sobre um veto do presidente", "veto pendente sem detalhe"
        v[3] = n if v[0] == "lei" else None
    for pid, v in st_prop.items():
        if v[0] == "lei":
            v[1] = txt_lei(v[3], dados_prop[pid]["siglaTipo"])
    links = verificar_lexml({v[3]["url"] for v in st_prop.values() if v[0] == "lei" and v[3]})
    for v in st_prop.values():
        if v[0] == "lei" and v[3] and links.get(v[3]["url"]) is False:
            v[3] = {"nome": v[3]["nome"], "url": None}
    log(f"  com número: {sum(1 for v in st_prop.values() if v[0] == 'lei' and v[3])}; links do LexML conferidos: "
        f"{sum(1 for x in links.values() if x)} ok, {sum(1 for x in links.values() if x is False)} não encontrados (url = null), "
        f"{sum(1 for x in links.values() if x is None)} sem resposta ({time.time() - t0:.0f}s)")

    log("Votações nominais do Plenário")
    itens_vot, vv = ler_votacoes(ids)
    V.preparar("camara", itens_vot)   # categoria, placar, quórum e orientações ligadas aos partidos
    log(f"  {len(itens_vot)} votações nominais com votos abertos; {len(vv['secretas'])} secretas fora ({time.time() - t0:.0f}s)")
    if len(itens_vot) >= 100:  # o catálogo não depende de quais deputados foram processados
        caminho_vot = RAIZ / ARQ_VOTACOES
        mudou = salvar_sem_ruido(caminho_vot, catalogo_votacoes(itens_vot))
        log(f"  {ARQ_VOTACOES}: {len(itens_vot)} votações, {caminho_vot.stat().st_size / 1024:.0f} KB ({'reescrito' if mudou else 'sem mudança'})")
        g, a_ = V.salvar_detalhes("camara", itens_vot)
        log(f"  dados/votacoes/camara/: um arquivo por votação ({g} gravados, {a_} apagados)")
    else:
        log(f"  AVISO: poucas votações ({len(itens_vot)}); {ARQ_VOTACOES} e dados/votacoes/camara/ não foram reescritos")

    log("Cota parlamentar")
    cota = ler_cota_csv(ids)
    conferencia = Counter()
    gastos = dict(zip(sorted(ids), em_paralelo(lambda d: bloco_gastos(d, cota, conferencia), sorted(ids))))
    log(f"  portal: {conferencia['portal']}, sem nenhuma despesa: {conferencia['sem_despesa']}, só arquivo: {conferencia['arquivo']}, "
        f"categorias do arquivo diferentes do portal: {conferencia['diferenca']} deputados ({time.time() - t0:.0f}s)")
    if conferencia["arquivo"]:
        log(f"  AVISO: gastos pelo arquivo (portal falhou): {[d for d in DIF_COTA if d.endswith('(arquivo)')]}")

    simples = carregar_simples()
    escritos = 0
    situacoes = Counter()
    tamanhos = {}
    for dep in sorted(ids):
        det, hist = fichas[dep]
        i = info[dep]
        st = det.get("ultimoStatus") or {}
        genero = det.get("sexo") or i["genero"]
        cargo = cargo_dep(genero)
        inicio, obs, _cond = mandato_atual(det, hist)
        mun, ufn = limpa(det.get("municipioNascimento")), limpa(det.get("ufNascimento"))
        redes = []
        for u in (det.get("redeSocial") or []) + [det.get("urlWebsite")]:
            u = url_rede(u)
            if u and u not in redes:
                redes.append(u)
        email = limpa((st.get("gabinete") or {}).get("email")) or limpa(st.get("email")) or limpa(i.get("email"))

        lista, outros, apoios = [], Counter(), Counter()
        for pid, pp in papel.get(dep, {}).items():
            p = dados_prop.get(pid)
            if not p:
                continue
            tipo = p["siglaTipo"]
            if pp == "apoio":
                apoios[tipo] += 1
                continue
            if "ementa" not in p:
                outros[tipo] += 1
                continue
            stt, txt, motivo, lei = st_prop[pid]
            lista.append({
                "id": f"camara:{pid}", "sigla": f"{tipo} {p['numero']}/{p['ano']}", "tipo": tipo,
                "data": (p["dataApresentacao"] or "")[:10] or None, "ementa": limpa(p["ementa"]), "s": None,
                "status": stt, "statusTxt": txt, "situacao": limpa(p["ultimoStatus_descricaoSituacao"]),
                "dataStatus": (p["ultimoStatus_dataHora"] or "")[:10] or None, "papel": pp,
                "temas": temas.get(pid, []), "url": f"{PORTAL}/propostas-legislativas/{pid}", "lei": lei,
            })
        lista = aplicar_simples(ordenar_propostas(lista), simples)
        por_tipo = Counter(x["tipo"] for x in lista)
        por_tema = Counter(t for x in lista for t in x["temas"])
        ela = genero == "F"
        busca = f"{PORTAL}/busca-portal?contextoBusca=BuscaProposicoes&pagina=1&order=data&abaEspecifica=true&q=autores.ideCadastro%3A%20{dep}"
        propostas = {
            "escopo": "Propostas apresentadas como deputada federal" if ela else "Propostas apresentadas como deputado federal",
            "resumo": resumo_propostas(lista),
            "porTipo": dict(sorted(por_tipo.items(), key=lambda x: (-x[1], x[0]))),
            "porTema": [{"tema": t, "n": n} for t, n in sorted(por_tema.items(), key=lambda x: (-x[1], chave_nome(x[0])))],
            "outros": {"total": sum(outros.values()), "porTipo": dict(sorted(outros.items(), key=lambda x: (-x[1], x[0]))),
                       "url": busca, "txt": "Pedidos de informação, requerimentos, indicações e outros documentos"},
            "apoios": {"total": sum(apoios.values()), "porTipo": dict(sorted(apoios.items(), key=lambda x: (-x[1], x[0]))),
                       "txt": ("Assinaturas só de apoio: a deputada assinou para que a proposta de outra pessoa pudesse ser apresentada "
                               if ela else
                               "Assinaturas só de apoio: o deputado assinou para que a proposta de outra pessoa pudesse ser apresentada ")
                              + "(uma PEC precisa de 171 assinaturas). Quem só apoia não é autor nem coautor."},
            "fonte": fonte(VEIC, f"Dados Abertos: proposições, autores e temas (arquivos anuais de {ano_ini} a {ANO}); "
                                 "autor = 1º a assinar, coautor = quem assinou junto como proponente", busca, HOJE),
            "lista": lista,
        }
        for x in lista:
            situacoes[x["id"]] = (x["situacao"] or "", x["status"], st_prop[x["id"].split(":")[1]][2])

        perfil = {
            "id": f"dep-{dep}", "tipo": "dep", "nome": i["nome"], "nomeCivil": nome_civil(det.get("nomeCivil")),
            "cargo": cargo, "genero": genero if genero in ("F", "M") else None, "uf": i["uf"], "municipio": None,
            "partido": i["partido"], "foto": i["foto"], "fotoCredito": VEIC if i["foto"] else None,
            "nascimento": (det.get("dataNascimento") or "")[:10] or None,
            "naturalidade": (f"{mun} ({ufn})" if mun and ufn else mun) or None,
            "escolaridade": limpa(det.get("escolaridade")),
            "profissoes": sorted(profissoes.get(dep, []), key=chave_nome),
            "mandato": {"inicio": inicio, "fim": FIM_LEG, "situacao": "Em exercício", "obs": obs,
                        "fonte": fonte(VEIC, f"Biografia e histórico de mandatos do(a) deputado(a) {dep}",
                                       f"{PORTAL}/deputados/{dep}/biografia", HOJE)},
            "mandatosAnteriores": mandatos_anteriores(hist, legs, genero),
            "eleicao": None, "eleicao2026": None, "bens": None,
            "links": {"oficial": f"{PORTAL}/deputados/{dep}", "email": email, "redes": redes},
            "comissoes": comissoes.get(dep, []),
            "propostas": propostas,
            "gastos": gastos[dep],
            "votacoes": bloco_votacoes(dep, itens_vot, vv["votos"]),
            "fontes": fontes_perfil(dep),
            "atualizado": HOJE,
        }
        caminho = PESSOAS / f"dep-{dep}.json"
        if salvar_sem_ruido(caminho, perfil):
            escritos += 1
        tamanhos[dep] = caminho.stat().st_size
    log(f"Perfis: {len(ids)} prontos, {escritos} reescritos ({time.time() - t0:.0f}s)")

    if not a.ids:
        relatorio_situacoes(situacoes, len(ids))
        # perfis de quem saiu do exercício
        if 500 <= len(ids) <= 520:
            for f in PESSOAS.glob("dep-*.json"):
                if f.stem[4:] not in ids:
                    log(f"  removendo {f.name} (não está mais em exercício)")
                    f.unlink()
                    foto = FOTOS / f"{f.stem}.jpg"
                    if foto.exists():
                        foto.unlink()
    maiores = sorted(tamanhos.items(), key=lambda x: -x[1])[:5]
    log("Maiores perfis: " + ", ".join(f"dep-{d} {t / 1024:.0f} KB" for d, t in maiores))
    todos_dep = list(PESSOAS.glob("dep-*.json"))
    log(f"dados/pessoas/dep-*.json: {len(todos_dep)} arquivos, {sum(f.stat().st_size for f in todos_dep) / 1e6:.1f} MB")
    log(f"Pronto em {time.time() - t0:.0f}s")


def relatorio_situacoes(situacoes: dict, n_dep: int):
    c = Counter((sit, st) for sit, st, _ in situacoes.values())
    motivos = defaultdict(Counter)
    exemplos = defaultdict(list)
    for pid, (sit, st, motivo) in sorted(situacoes.items()):
        if sit in ("", "<Não Definido>") or motivo != "regra comum":
            motivos[(sit, st)][motivo] += 1
            if len(exemplos[motivo]) < 3:
                exemplos[motivo].append(pid.split(":")[1])
    linhas = [
        f"# Situação oficial da Câmara -> status do site. Gerado por scripts/camara.py em {HOJE}.",
        f"# Propostas distintas (tipos da lista) de {n_dep} deputados em exercício: {len(situacoes)}",
        "# quantidade | status | situação oficial (ultimoStatus_descricaoSituacao) | regra",
    ]
    por_sit = Counter()
    for (sit, st), n in c.items():
        por_sit[sit] += n
    for (sit, st), n in sorted(c.items(), key=lambda x: (-por_sit[x[0][0]], x[0][0], -x[1])):
        m = ", ".join(f"{k}: {v}" for k, v in motivos.get((sit, st), {}).items())
        linhas.append(f"{n:7d} | {st:9s} | {sit or '(vazia)'}" + (f" | {m}" if m else ""))
    tot = Counter(st for _, st, _ in situacoes.values())
    linhas.append("# total por status: " + ", ".join(f"{k}: {v}" for k, v in tot.most_common()))
    linhas.append("# exemplos (id da proposição) das regras específicas da Câmara:")
    for motivo, ex in sorted(exemplos.items()):
        linhas.append(f"#   {motivo}: " + ", ".join(f"{PORTAL}/propostas-legislativas/{e}" for e in ex))
    (CC / "situacoes.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    log(f"  .cache/camara/situacoes.txt: {len(c)} combinações; outra = {tot.get('outra', 0)}")


if __name__ == "__main__":
    main()
