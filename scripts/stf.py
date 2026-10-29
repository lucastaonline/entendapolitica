"""Ministros do Supremo Tribunal Federal (STF): quem está no tribunal hoje, como cada um chegou lá e até quando fica.

Gera dados/stf.json (contrato no README) e as fotos img/pessoas/stf-<slug>.jpg (240 px de largura).

Fontes (só oficiais; cada página é aberta e a data da consulta fica na fonte):
- STF, página "O STF" (portal.stf.jus.br/ostf/): quem está no Plenário e a data da posse de cada um, a presidência, as
  Turmas e o link do gabinete de cada ministro.
- STF, "Pastas dos Ministros" (Biblioteca do STF): "Composição Atual" (a ordem oficial: presidente, vice e os outros por
  antiguidade) e, de cada ministro, a página principal (nome completo, nascimento, datas da indicação, da nomeação e da
  posse, foto oficial) e "Dados e Datas" (a mensagem do presidente da República ao Senado, o decreto de nomeação no Diário
  Oficial da União e a vaga). Quando uma cadeira fica vazia, a pasta de quem saiu diz a data.
- STF, "Turmas" (quem está em cada Turma e quem preside), "Presidentes" (o período da presidência) e a lista de ministros
  por antiguidade (o número de cada ministro no STF, que deixa o endereço do perfil sempre o mesmo).
- Senado Federal, Dados Abertos (legis.senado.leg.br/dadosabertos): a mensagem (MSF) de cada indicação, o resultado na
  Comissão de Constituição, Justiça e Cidadania (CCJ) e no Plenário (votação secreta: só o placar é público) e as
  indicações para o STF dos últimos dois anos (para explicar uma cadeira vazia).
- Regras: Constituição Federal (arts. 12 § 3º IV, 52 III "a", 84 XIV, 93 I, 101 e 102), Emenda Constitucional 88/2015
  (aposentadoria obrigatória aos 75 anos) e Regimento Interno do STF (11 ministros, Turmas de 5, presidente e vice por
  2 anos, antiguidade).

O que não entra (e o motivo, que o site mostra): os números de cada gabinete (decisões, processos) estão só nos painéis
do Corte Aberta, que funcionam no navegador, sem um arquivo de dados com endereço fixo (o perfil leva o link); a carreira
antes do STF não é resumida, porque o STF publica a biografia em texto só de alguns ministros (o perfil leva o link dos
currículos oficiais de cada um, na Biblioteca do STF).

Rede educada: robots.txt de cada servidor (o do Senado responde 403 para qualquer um; só a API de Dados Abertos, feita para
programas e já usada pelos outros coletores do site, é lida), um pedido por vez em cada servidor, 2 s entre pedidos (ou o
Crawl-delay), User-Agent do projeto e cache em .cache/stf/.

Roda no robô diário, mas só lê os sites uma vez por semana: se dados/stf.json foi conferido há menos de 7 dias, sai sem
pedir nada. Se o STF ou o Senado estiver fora do ar, ou se a leitura vier incompleta, fica o arquivo de antes. Quando a
composição muda (aposentadoria, posse, presidência, Turmas, nova indicação no Senado), avisa no log (e no resumo do robô).

Uso: python scripts/stf.py             (lê se já passou uma semana desde a última conferência)
     python scripts/stf.py --agora     (lê já)
     python scripts/stf.py --cache     (só o que está em .cache/stf/, sem rede: refaz o arquivo)
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (CACHE, DADOS, FOTOS, UA, fonte, hoje, ler_json, limpa, log, nome_proprio, salvar_json,  # noqa: E402
                   sem_acento, sem_mudar_data, slug)

ARQ = DADOS / "stf.json"
CS = CACHE / "stf"
STF = "https://portal.stf.jus.br"
BIB = STF + "/textos/verTexto.asp?servico=bibliotecaConsultaProdutoBibliotecaPastaMinistro&pagina="
SEN = "https://legis.senado.leg.br/dadosabertos"
SEN_MATERIA = "https://www25.senado.leg.br/web/atividade/materias/-/materia/"
CORTE_ABERTA = "https://transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html"
CORTE_ABERTA_SOBRE = STF + "/hotsites/corteaberta/"

URL = {
    "ostf": STF + "/ostf/",
    "composicao": BIB + "ComposicaoAtual",
    "antiguidade_bib": BIB + "OrdemAntiguidade",
    "turmas": STF + "/textos/verTexto.asp?servico=sobreStfComposicaoTurma&pagina=principal",
    "presidentes": STF + "/ministro/listarPresidente.asp",
    "antiguidade": STF + "/ostf/ministros/ministro.asp?periodo=STF&consulta=ANTIGUIDADE",
}

CADEIRAS = 11            # CF art. 101 e Regimento Interno do STF, art. 2º
CADEIRAS_TURMA = 5       # Regimento Interno do STF, art. 4º
IDADE_LIMITE = 75        # aposentadoria obrigatória: EC 88/2015 (ADCT art. 100) e LC 152/2015
MAIORIA_SENADO = 41      # maioria absoluta dos 81 senadores (CF art. 101, parágrafo único)
DIAS_ENTRE_LEITURAS = 7
PAUSA = 2.0              # segundos entre dois pedidos ao mesmo servidor (ou o Crawl-delay do robots.txt, se for maior)
FOLGA_H = 6 * 24         # páginas guardadas há menos de 6 dias não são pedidas de novo

# As regras do jogo: leis e o Regimento Interno, conferidos em 29/10/2026 (a Constituição no Planalto é o endereço que o
# site já usa; nesse dia o Planalto não abriu daqui, e o texto foi conferido nas páginas de legislação do Senado).
CF = fonte("Planalto", "Constituição Federal de 1988 (arts. 12, § 3º, IV; 52, III, “a”; 84, XIV; 93, I; 101; e 102)",
           "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art101", "1988-10-05")
CF_SENADO = fonte("Senado Federal", "Constituição Federal, texto atualizado (os mesmos artigos, conferidos aqui em 29/10/2026)",
                  "https://legis.senado.leg.br/norma/579494/publicacao/16434817", "2026-10-29")
EC122 = fonte("Senado Federal", "Emenda Constitucional nº 122, de 2022: texto atual do art. 101 da Constituição (11 ministros, de 35 a 70 anos)",
              "https://legis.senado.leg.br/norma/35857592/publicacao/35861027", "2022-05-17")
EC88 = fonte("Senado Federal", "Emenda Constitucional nº 88, de 2015: aposentadoria obrigatória dos ministros do STF aos 75 anos (ADCT, art. 100)",
             "https://legis.senado.leg.br/norma/540691/publicacao/15624167", "2015-05-07")
RISTF = fonte("Supremo Tribunal Federal", "Regimento Interno do STF (arts. 2º, 4º, 12 e 17)",
              "https://www.stf.jus.br/arquivo/cms/legislacaoRegimentoInterno/anexo/RISTF.pdf", "2026-10-29")

# Nome de cada presidente da República como assinava os decretos no Diário Oficial (o mesmo dos mandatos anteriores do
# site); a Biblioteca do STF às vezes escreve diferente ("Dilma Roussef", "Luís Inácio").
PRESIDENTES = {
    "fernando henrique cardoso": "Fernando Henrique Cardoso",
    "luiz inacio lula da silva": "Luiz Inácio Lula da Silva", "luis inacio lula da silva": "Luiz Inácio Lula da Silva",
    "dilma rousseff": "Dilma Rousseff", "dilma roussef": "Dilma Rousseff", "dilma vana rousseff": "Dilma Rousseff",
    "michel temer": "Michel Temer", "michel miguel elias temer lulia": "Michel Temer",
    "jair messias bolsonaro": "Jair Messias Bolsonaro", "jair bolsonaro": "Jair Messias Bolsonaro",
}
MESES = {"jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "marco": 3, "abr": 4, "abril": 4, "mai": 5, "maio": 5,
         "jun": 6, "junho": 6, "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "setembro": 9, "out": 10, "outubro": 10,
         "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12}
DATA_BR = r"(\d{1,2})º?\s*/\s*(\d{1,2})\s*/\s*(\d{4})"
DATA_EXT = r"(\d{1,2})º?\s+de\s+([a-zçA-ZÇ]+)\s+de\s+(\d{4})"


class Falha(Exception):
    """Uma página essencial não abriu (ou não deixou ler): fica o arquivo de antes."""


# ---------------------------------------------------------------- rede educada
class Rede:
    """Um pedido por vez em cada servidor, com pausa; robots.txt lido uma vez por rodada; cache em disco."""
    # A API de Dados Abertos do Senado é feita para leitura por programas (o senado.py e o executivo.py também a usam); o
    # robots.txt do servidor responde 403 ("Request forbidden by administrative rules") para qualquer um, até para
    # navegadores. Quando o robots.txt não abre, só esse caminho é lido.
    SEM_ROBOTS_OK = {"legis.senado.leg.br": "/dadosabertos/"}

    def __init__(self, so_cache: bool = False):
        self.so_cache = so_cache
        self.regras: dict[str, object] = {}
        self.ultimo: dict[str, float] = {}
        self.pedidos = 0

    def _abre(self, url: str, tentativas: int = 3) -> bytes:
        host = urllib.parse.urlsplit(url).netloc
        erro = None
        for t in range(tentativas):
            espera = self._atraso(host) - (time.time() - self.ultimo.get(host, 0))
            if espera > 0:
                time.sleep(espera)
            self.ultimo[host] = time.time()
            self.pedidos += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                erro = e
                e.close()
                if e.code in (401, 403, 404, 410):
                    raise
            except Exception as e:  # rede instável
                erro = e
            time.sleep(5 * (t + 1))
        raise Falha(f"{url}: {erro}")

    def _atraso(self, host: str) -> float:
        r = self.regras.get(host)
        cd = r.crawl_delay(UA) if isinstance(r, urllib.robotparser.RobotFileParser) else None
        return max(PAUSA, float(cd or 0))

    def _robots(self, url: str):
        u = urllib.parse.urlsplit(url)
        if u.netloc in self.regras:
            return self.regras[u.netloc]
        self.regras[u.netloc] = None
        try:
            corpo = self._abre(f"{u.scheme}://{u.netloc}/robots.txt", tentativas=2)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(corpo.decode("utf-8", "replace").splitlines())
            r = rp
        except urllib.error.HTTPError as e:
            r = "livre" if e.code in (404, 410) else "fechado"
        except Falha:
            r = "erro"  # robots.txt fora do ar: nada desse servidor nesta rodada
        self.regras[u.netloc] = r
        return r

    def pode(self, url: str) -> bool:
        r = self._robots(url)
        u = urllib.parse.urlsplit(url)
        if isinstance(r, urllib.robotparser.RobotFileParser):
            return r.can_fetch(UA, url)
        if r == "livre":
            return True
        if r == "fechado":
            return u.path.startswith(self.SEM_ROBOTS_OK.get(u.netloc, "\0"))
        return False

    def get(self, url: str, nome: str, max_idade_h: float | None = FOLGA_H) -> bytes:
        """Conteúdo de `url`, guardado em .cache/stf/<nome> (None = guardado vale para sempre)."""
        arq = CS / nome
        if arq.exists() and arq.stat().st_size > 0:
            idade = (time.time() - arq.stat().st_mtime) / 3600
            if self.so_cache or max_idade_h is None or idade < max_idade_h:
                return arq.read_bytes()
        if self.so_cache:
            raise Falha(f"fora do cache: {url}")
        if self._robots(url) == "erro":
            raise Falha(f"{urllib.parse.urlsplit(url).netloc} não respondeu (nem o robots.txt abriu)")
        if not self.pode(url):
            raise Falha(f"o robots.txt não deixa ler {url}")
        try:
            corpo = self._abre(url)
        except urllib.error.HTTPError as e:
            raise Falha(f"{url}: HTTP {e.code}") from None
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(arq.suffix + ".part")
        tmp.write_bytes(corpo)
        os.replace(tmp, arq)
        return corpo

    def texto(self, url: str, nome: str, max_idade_h: float | None = FOLGA_H) -> str:
        b = self.get(url, nome, max_idade_h)
        m = re.search(rb'charset=["\']?([\w-]+)', b[:3000])
        for cod in ([m.group(1).decode()] if m else []) + ["utf-8", "cp1252"]:
            try:
                return b.decode(cod)
            except (UnicodeDecodeError, LookupError):
                continue
        return b.decode("utf-8", "replace")

    def json(self, url: str, nome: str, max_idade_h: float | None = FOLGA_H):
        import json as _json
        return _json.loads(self.get(url, nome, max_idade_h).decode("utf-8-sig"))


# ---------------------------------------------------------------- texto e datas
def sem_tags(h: str) -> str:
    """HTML -> texto, uma linha por parágrafo."""
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?is)<br\s*/?>|</p>|</li>|</tr>|</h\d>|</div>", "\n", h)
    h = html.unescape(re.sub(r"(?s)<[^>]+>", " ", h))
    h = re.sub(r"[ \t\r\f\v\xa0]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()


def chave(nome: str) -> str:
    """'Alexandre de Moraes' e 'Ministro Alexandre de Moraes' -> 'alexandre moraes' (para casar as páginas)."""
    s = re.sub(r"^(ministr[oa]|min\.)\s+", "", sem_acento(nome or "").lower().strip())
    return " ".join(p for p in re.findall(r"[a-z]+", s) if p not in {"de", "da", "do", "dos", "das", "e"})


def iso(d: int, m: int, a: int) -> str | None:
    try:
        return dt.date(int(a), int(m), int(d)).isoformat()
    except ValueError:
        return None


def data_br(s: str | None) -> str | None:
    m = re.search(DATA_BR, s or "")
    return iso(m.group(1), m.group(2), m.group(3)) if m else None


def data_ext(s: str | None) -> str | None:
    m = re.search(DATA_EXT, s or "", re.I)
    if not m:
        return None
    mes = MESES.get(sem_acento(m.group(2)).lower())
    return iso(m.group(1), mes, m.group(3)) if mes else None


def data_abrev(s: str | None) -> str | None:
    """'22 out. 2020', '28 maio 2002', '1º jun. 2023' -> ISO."""
    m = re.search(r"(\d{1,2})º?\s+([a-zç]+)\.?\s+(\d{4})", sem_acento(s or "").lower())
    if not m or m.group(2) not in MESES:
        return None
    return iso(m.group(1), MESES[m.group(2)], m.group(3))


def faz_anos(nascimento: str, anos: int) -> str:
    n = dt.date.fromisoformat(nascimento)
    try:
        return n.replace(year=n.year + anos).isoformat()
    except ValueError:  # 29 de fevereiro
        return dt.date(n.year + anos, 3, 1).isoformat()


def absoluta(base: str, href: str) -> str:
    u = urllib.parse.urljoin(base, html.unescape(href or "").strip())
    # os links das páginas do STF ainda vêm com http://; os dois servidores abrem com https (conferido em 29/10/2026)
    return re.sub(r"^http://(www|portal)\.stf\.jus\.br/", r"https://\1.stf.jus.br/", u)


# ---------------------------------------------------------------- páginas do STF
def ler_ostf(h: str) -> dict:
    """Página "O STF": o Plenário (nome, Ministro/Ministra, data da posse; para quem preside, a data da posse na
    presidência), as Turmas, a presidência (Gestão), o link do gabinete e os números do tribunal."""
    ini, fim = h.find("Composição do Plenário"), h.find("card-turmas-ostf")
    if ini < 0 or fim < 0:
        raise Falha("página O STF: não achei a composição do Plenário")
    plen = []
    for c in re.split(r'class="ministro-conteudo', h[ini:fim])[1:]:
        m = re.search(r"<p[^>]*>\s*(Ministr[oa])\s*</p>\s*<strong[^>]*>\s*([^<]+?)\s*</strong>(.*?)\((\d{1,2}/\d{1,2}/\d{4})\)", c, re.S)
        if not m:
            continue
        a = re.search(r'<a[^>]+href="([^"]+)"', c)
        plen.append({"nome": html.unescape(m.group(2)).strip(), "genero": "F" if m.group(1) == "Ministra" else "M",
                     "presidente": "Presidente" in sem_tags(m.group(3)), "data": data_br(m.group(4)),
                     "gabinete": absoluta(STF + "/ostf/", a.group(1)) if a else None})
    turmas = ler_turmas(h[fim:h.find("Histórico de Presidentes", fim)], STF + "/ostf/")
    gestao = {}
    g = h.find(">Gestão<")
    if g > 0:
        for bloco in re.split(r'class="mb-4 gestao-min"', h[g:g + 6000])[1:]:
            t = sem_tags(bloco)
            m = re.search(r"Min\.\s*([^\n]+?)\s*\n\s*(Vice-Presidente|Presidente)", t)
            if m:
                gestao["vice" if m.group(2).startswith("Vice") else "presidente"] = m.group(1).strip()
    m = re.search(r"([\d.]+)\s*</[^>]+>\s*(?:<[^>]+>\s*)*Decis[õo]es em (\d{4})", h)
    decisoes = {"total": int(m.group(1).replace(".", "")), "ano": int(m.group(2))} if m else None
    links = {}
    for k, padrao in (("corteAberta", r'href="(https://transparencia\.stf\.jus\.br/extensions/corte_aberta/[^"]+)"'),):
        m = re.search(padrao, h)
        links[k] = m.group(1) if m else None
    return {"plenario": plen, "turmas": turmas, "gestao": gestao, "decisoes": decisoes, "links": links}


def ler_turmas(h: str, base: str) -> dict:
    """Blocos "1ª TURMA"/"2ª TURMA" (ou "Primeira Turma"/"Segunda Turma"): quem está em cada uma, em ordem, e quem preside."""
    out = {}
    partes = re.split(r"(?i)(1ª\s*TURMA|2ª\s*TURMA|Primeira\s+Turma|Segunda\s+Turma)", h)
    for k in range(1, len(partes) - 1, 2):
        n = 1 if re.match(r"(?i)1|primeira", partes[k]) else 2
        if n in out:
            continue
        membros = []
        for a in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>(?=(.{0,160}))', partes[k + 1], re.S):
            nome = sem_tags(a.group(2))
            m = re.match(r"(Ministr[oa])\s+(.+?)(?:\s*-\s*Presidente)?\s*$", nome)
            if not m:
                continue
            presidente = "Presidente" in nome or bool(re.match(r"\s*(?:</?\w[^>]*>\s*)*PRESIDENTE", a.group(3)))
            membros.append({"nome": m.group(2).strip(), "presidente": presidente, "link": absoluta(base, a.group(1))})
        out[n] = membros
    return out


def com_pastas(h: str) -> str:
    """Texto de uma página das Pastas dos Ministros com cada link de pasta marcado: [[PASTA:FlavioDino]]."""
    h = re.sub(r'(?is)<a[^>]+pagina=([A-Za-z]+)Principal[^>]*>', lambda m: f" [[PASTA:{m.group(1)}]] ", h)
    return re.sub(r"\s+", " ", sem_tags(h))


def ler_composicao(h: str) -> list[dict]:
    """"Composição Atual" das Pastas dos Ministros: ordem oficial, papel (Presidente, Vice-Presidente, Decano) e a pasta."""
    out = []
    t = com_pastas(h)
    for m in re.finditer(r"(Ministr[oa])\s*\[\[PASTA:(\w+)\]\]\s*([^\[\]()]+?)\s*(?:\((Presidente|Vice-Presidente|Decan[oa])\)|"
                         r"(?=\s*(?:Ministr[oa]\s*\[\[|\[\[|Essa informa|$)))", t):
        nome = m.group(3).strip()
        if not nome or any(x["pasta"] == m.group(2) for x in out):
            continue
        out.append({"nome": nome, "pasta": m.group(2), "genero": "F" if m.group(1) == "Ministra" else "M", "papel": m.group(4)})
    return out


def ler_pastas_antiguidade(h: str) -> dict[str, dict]:
    """Pastas dos Ministros em ordem de antiguidade (todos, de 1891 a hoje): chave do nome -> {pasta, nome}."""
    out = {}
    for m in re.finditer(r"\[\[PASTA:(\w+)\]\]\s*([^\[\]()]+?)\s*\(", com_pastas(h)):
        out[chave(m.group(2))] = {"pasta": m.group(1), "nome": m.group(2).strip()}
    return out


def ler_ids_stf(h: str) -> dict[str, dict]:
    """Lista de ministros por antiguidade (banco do STF): chave do nome -> {id, nomeCivil} (fica o mais novo, se repetir)."""
    out = {}
    for m in re.finditer(r'verMinistro\.asp\?periodo=STF&(?:amp;)?id=(\d+)"><strong>([^<]+)</strong>&nbsp;\(([^)]+)\)', h):
        k = chave(html.unescape(m.group(2)))
        if k not in out or int(m.group(1)) > out[k]["id"]:
            out[k] = {"id": int(m.group(1)), "nome": html.unescape(m.group(2)).strip(), "nomeCivil": html.unescape(m.group(3)).strip()}
    return out


def ler_presidencia(h: str, nome: str) -> str | None:
    """Lista de presidentes: o período de quem preside hoje ("2025 - 2027")."""
    t = sem_tags(h)
    m = re.search(re.escape(nome) + r"\s*\n\s*(\d{4}(?:\s*-\s*\d{4})?)", t)
    return re.sub(r"\s*-\s*", "–", m.group(1)) if m else None


def linhas_com_link(h: str, base: str) -> list[tuple[str, str | None]]:
    """(texto, link) de cada linha (parágrafo) de uma página das Pastas dos Ministros."""
    out = []
    for parte in re.split(r"(?i)<br\s*/?>|</p>|</li>|</tr>|</td>", h):
        t = sem_tags(parte)
        if not t:
            continue
        links = [x for x in re.findall(r'href="([^"]+)"', parte) if not x.startswith(("#", "javascript", "mailto"))]
        out.append((re.sub(r"\s+", " ", t), absoluta(base, links[0]) if links else None))
    return out


def ler_pasta(h: str, url: str) -> dict:
    """Página principal da pasta: nome completo, nascimento, datas (indicação, nomeação, posse, presidência,
    aposentadoria) com o documento de cada uma, e a foto oficial."""
    d = {"nomeCivil": None, "nascimento": None, "naturalidade": None, "datas": {}, "docs": {}, "foto": None}
    for t, link in linhas_com_link(h, url):
        m = re.search(r"Nome Completo:\s*(.+)", t)
        if m:
            d["nomeCivil"] = m.group(1).strip()
        m = re.search(r"Data de Nascimento:\s*" + DATA_BR + r"\s*,?\s*(.*)", t)
        if m:
            d["nascimento"] = iso(m.group(1), m.group(2), m.group(3))
            lugar = m.group(4).strip()
            m2 = re.match(r"(.+?)\s*/\s*([A-Z]{2})$", lugar)
            d["naturalidade"] = f"{m2.group(1)} ({m2.group(2)})" if m2 else (lugar or None)
        for k, rot in (("indicacao", r"Indicação para o Supremo"), ("nomeacao", r"Nomeação para o Supremo"),
                       ("posse", r"Posse no Supremo"), ("vice", r"Posse na Vice-Presid"), ("presidencia", r"Posse na Presid[eê]ncia do Supremo"),
                       ("aposentadoria", r"Aposentadoria do Supremo"), ("falecimento", r"Falecimento")):
            if re.search(rot, t, re.I) and ":" in t:
                data = data_br(t.split(":")[-1])
                if data:
                    d["datas"][k] = data
                    if link:
                        d["docs"][k] = link
    m = re.search(r'<img[^>]+src="([^"]*/imagem/foto_[^"]+)"', h)
    if m:
        d["foto"] = absoluta(url, m.group(1)).replace("http://www.stf.jus.br", "https://www.stf.jus.br")
    m = re.search(r'pagina=([A-Za-z]+CurriculoBiografia)"', h)
    d["curriculo"] = BIB + m.group(1) if m else None
    return d


def secoes_dd(t: str) -> dict[str, str]:
    """Divide o texto de "Dados e Datas" nas seções (indicação, Senado, nomeação, posse), ficando com a que tem a citação."""
    marcas = [("indicacao", r"INDICAÇÃO PARA O SUPREMO"), ("senado", r"APRECIAÇÃO"), ("nomeacao", r"NOMEAÇÃO PARA O SUPREMO"),
              ("posse", r"POSSE NO SUPREMO"), ("outra", r"POSSE NA |APOSENTADORIA|FALECIMENTO")]
    pos = sorted((m.start(), k) for k, rx in marcas for m in re.finditer(rx, t))
    out = {}
    for i, (p, k) in enumerate(pos):
        trecho = t[p:pos[i + 1][0]] if i + 1 < len(pos) else t[p:]
        if k != "outra" and re.search(r"\d\s*\.\s*(BRASIL|CURRICULUM|SESSÃO)", trecho) and k not in out:
            out[k] = re.sub(r"\s+", " ", trecho).strip()
    return out


def ler_dados_datas(h: str, url: str) -> dict:
    t = sem_tags(re.sub(r'(?is)<a[^>]+href="([^"]+\.pdf)"[^>]*>', lambda m: f" [[PDF:{absoluta(url, m.group(1))}]] ", h))
    s = secoes_dd(t)
    d = {"presidente": None, "presidenteGenero": None, "mensagem": None, "mensagemData": None, "msf": None, "parecer": None, "decreto": None,
         "decretoData": None, "aPartirDe": None, "dou": None, "douData": None, "douIndicacao": None, "vaga": None,
         "pdf": {}}
    ind, sen, nom = s.get("indicacao", ""), s.get("senado", ""), s.get("nomeacao", "")
    m = re.search(r"\[(O|A)\s+President[ea](?:\s+da\s+Rep[úu]blica)?\s+([^\]]+?)\s*\]", ind)
    if m:
        bruto = re.sub(r",.*$", "", m.group(2)).strip()
        d["presidente"] = PRESIDENTES.get(chave_presidente(bruto)) or nome_proprio(bruto)
        d["presidenteGenero"] = "F" if m.group(1) == "A" else "M"
        if chave_presidente(bruto) not in PRESIDENTES:
            log(f"  ⚠️ nome de presidente da República fora da lista: {bruto!r} (confira a grafia no Diário Oficial)")
    m = re.search(r"Mensagem\s+n[ºo°]\.?\s*([\d.]+)\s*,?\s*de\s+" + DATA_EXT, ind, re.I)
    if m:
        d["mensagem"] = f"Mensagem nº {m.group(1)}, de {m.group(2)}{'º' if m.group(2) == '1' else ''} de {m.group(3).lower()} de {m.group(4)}"
        d["mensagemData"] = data_ext(m.group(0))
    m = re.search(r"Di[áa]rio\s+Oficial\s+da\s+Uni[ãa]o\s*[,:]?\s*(.+?)\s*(?:\[\[PDF|$)", ind)
    if m:
        d["douIndicacao"] = "Diário Oficial da União, " + m.group(1).strip(" .,") + "."
    m = re.search(r"\[\[PDF:([^\]]+)\]\]", ind)
    if m:
        d["pdf"]["indicacao"] = m.group(1)
    m = re.search(r"Mensagem\s+n[ºo°]\.?\s*([\d.]+)\s*,?\s*(?:de\s+)?(?:\d{1,2}º?\s+de\s+[a-zç]+\s+de\s+)?(\d{4})", sen, re.I)
    if m:
        d["msf"] = {"numero": int(m.group(1).replace(".", "")), "ano": int(m.group(2))}
    m = re.search(r"Parecer\s+n[ºo°]\.?\s*([\d./]+)", sen)
    if m:
        d["parecer"] = m.group(1).strip(".")
    m = re.search(r"\[\[PDF:([^\]]+)\]\]", sen)
    if m:
        d["pdf"]["senado"] = m.group(1)
    m = re.search(r"Decreto\s+de\s+" + DATA_EXT, nom, re.I)
    if m:
        d["decreto"] = f"Decreto de {m.group(1)}{'º' if m.group(1) == '1' else ''} de {m.group(2).lower()} de {m.group(3)}"
        d["decretoData"] = data_ext(m.group(0))
    m = re.search(r"a partir de\s+" + DATA_EXT, nom, re.I)
    if m:
        d["aPartirDe"] = data_ext(m.group(0))
    m = re.search(r"Di[áa]rio\s+Oficial\s+da\s+Uni[ãa]o\s*[,:]?\s*(.+?)\s*(?:\[\[PDF|$)", nom)
    if m:
        d["dou"] = "Diário Oficial da União, " + m.group(1).strip(" .,") + "."
        d["douData"] = data_abrev(m.group(1))
    m = re.search(r"\[\[PDF:([^\]]+)\]\]", nom)
    if m:
        d["pdf"]["nomeacao"] = m.group(1)
    for trecho in (sen, ind, nom):
        vg = vaga_de(trecho)
        if vg:
            d["vaga"] = vg
            break
    return d


def chave_presidente(s: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(s or "").lower()).strip()


# ---------------------------------------------------------------- Senado (Dados Abertos)
def numero_antes(t: str, fim: int) -> int | None:
    """O último número escrito em algarismos nos ~45 caracteres antes de `fim` ("17 (dezessete) votos", "vinte (20) votos")."""
    nums = re.findall(r"\d+", t[max(0, fim - 45):fim])
    return int(nums[-1]) if nums else None


def votos_ccj(t: str) -> dict | None:
    """'com 17 (dezessete) votos favoráveis e 10 (dez) votos contrários', 'por unanimidade, com 23 votos favoráveis'."""
    fav = re.search(r"votos?\s+favor[áa]ve(?:is|l)", t)
    if not fav:
        return None
    sim = numero_antes(t, fav.start())
    con = re.search(r"votos?\s+contr[áa]rios?", t)
    nao = numero_antes(t, con.start()) if con else (0 if re.search(r"unanimidade", t, re.I) else None)
    ab = re.search(r"absten[çc](?:[ãa]o|[õo]es)", t)
    return {"sim": sim, "nao": nao, "abstencao": numero_antes(t, ab.start()) if ab else None,
            "unanimidade": bool(re.search(r"unanimidade", t, re.I))}


def placar_plenario(t: str) -> dict | None:
    """'Sim - 47; Não - 31; Abst. - 2; Total – 80' / 'Sim 52, Não 27, Total 79' / 'Sim - 57, Nco - 15' (sic)."""
    sim = re.search(r"\bSim\s*[-–:]?\s*(\d+)", t)
    nao = re.search(r"\bN(?:ão|ao|co)\s*[-–:]?\s*(\d+)", t)
    if not (sim and nao):
        return None
    ab = re.search(r"Abst(?:\.|en[çc](?:ão|ões|oes|ao))?\s*[-–:]?\s*(\d+)", t)
    tot = re.search(r"Total\s*[-–:]?\s*(\d+)", t)
    p = {"sim": int(sim.group(1)), "nao": int(nao.group(1)), "abstencao": int(ab.group(1)) if ab else None,
         "total": int(tot.group(1)) if tot else None}
    if p["abstencao"] is None and p["total"] is not None:
        p["abstencao"] = p["total"] - p["sim"] - p["nao"]
    return p


# a frase do resultado da indicação no Plenário (o mesmo registro pode ter antes o resultado de um requerimento)
FRASE_PLENARIO = re.compile(r"(?:(?:Aprovad[oa]|Rejeitad[oa]) (?:a indica\w+|o Parecer)(?:[^.]|\.(?=\d))*?|Encerrada a vota\w+,?\s*)"
                            r"com o seguinte resultado:?\s*((?:Abst?\.|[^.]|\.(?=\d))+?Total\s*[-–:]?\s*\d+)")


def placar_do_texto(t: str) -> tuple[dict, str] | None:
    m = FRASE_PLENARIO.search(t)
    if not m:
        return None
    p = placar_plenario(m.group(1))
    return (p, m.group(1).strip()) if p else None


def senado(rede: Rede, numero: int, ano: int, nome: str) -> dict:
    """A indicação no Senado (MSF numero/ano): quando chegou, CCJ (data e placar), Plenário (data, placar e resultado)."""
    lista = rede.json(f"{SEN}/processo?sigla=MSF&numero={numero}&ano={ano}", f"senado/msf-{numero}-{ano}.json", FOLGA_H)
    lista = [x for x in (lista or []) if re.search(r"Supremo Tribunal Federal", x.get("ementa") or "")]
    if not lista:
        raise Falha(f"Senado: MSF {numero}/{ano} não achada")
    pr = lista[0]
    final = pr.get("tramitando") == "Não" and bool(pr.get("dataDeliberacao"))
    det = rede.json(f"{SEN}/processo/{pr['id']}", f"senado/processo-{pr['id']}.json", None if final else FOLGA_H)
    vot = rede.json(f"{SEN}/votacao?idProcesso={pr['id']}", f"senado/votacao-{pr['id']}.json", None if final else FOLGA_H)
    url = SEN_MATERIA + str(pr["codigoMateria"])
    f = fonte("Senado Federal", f"{pr['identificacao']}: indicação de {nome} para o STF (tramitação e votações)", url)
    f_api = fonte("Senado Federal (Dados Abertos)", f"{pr['identificacao']}: processo e votações na API de Dados Abertos",
                  f"{SEN}/processo/{pr['id']}")
    ccj = plen = None
    for a in det.get("autuacoes") or []:
        for i in a.get("informesLegislativos") or []:
            t = re.sub(r"\s+", " ", i.get("descricao") or "")
            col = (i.get("colegiado") or {}).get("sigla")
            if ccj is None and re.search(r"escrut[íi]nio secreto|votos? favor[áa]ve", t, re.I) and (col in (None, "CCJ")) and \
                    re.search(r"Parecer da CCJ|comiss[ãa]o aprova|CCJ", t, re.I) and not t.startswith("("):
                v = votos_ccj(t)
                frase = re.search(r"(?:com|por)\s+(?:unanimidade,\s*com\s+)?[^.;]*?votos?\s+favor[^.;]*", t)
                ccj = {"data": (i.get("data") or "")[:10] or None, **(v or {"sim": None, "nao": None, "abstencao": None, "unanimidade": False}),
                       "aprovado": bool(re.search(r"aprova", t, re.I)), "texto": frase.group(0).strip() if frase else None}
            pt = placar_do_texto(t)
            if pt:
                plen = {"data": (i.get("data") or "")[:10] or None, **pt[0],
                        "resultado": "rejeitada" if re.search(r"Rejeitad[oa] a indica", t) else "aprovada", "texto": pt[1]}
    # o placar estruturado da votação (quando existe) vale mais que o texto; os dois são conferidos
    for x in vot or []:
        if x.get("totalVotosSim") is None:
            continue
        p = {"sim": x["totalVotosSim"], "nao": x.get("totalVotosNao"), "abstencao": x.get("totalVotosAbstencao")}
        if plen and (plen["sim"], plen["nao"]) != (p["sim"], p["nao"]):
            log(f"  ⚠️ {pr['identificacao']}: placar do texto ({plen['sim']}x{plen['nao']}) ≠ placar da votação ({p['sim']}x{p['nao']}); vale o da votação")
        pt = placar_do_texto(re.sub(r"\s+", " ", (x.get("informeLegislativo") or {}).get("texto") or ""))
        base = plen or {"texto": pt[1] if pt else None}
        plen = {**base, **p, "data": x.get("dataSessao") or base.get("data"),
                "total": (p["sim"] or 0) + (p["nao"] or 0) + (p["abstencao"] or 0),
                "resultado": "rejeitada" if x.get("resultadoVotacao") == "R" else "aprovada" if x.get("resultadoVotacao") == "A" else base.get("resultado")}
        break
    if plen and plen.get("total") is not None and plen["sim"] + plen["nao"] + (plen["abstencao"] or 0) != plen["total"]:
        log(f"  ⚠️ {pr['identificacao']}: sim + não + abstenções ≠ total ({plen})")
    return {"materia": pr["identificacao"], "codigoMateria": pr["codigoMateria"], "url": url, "ementa": pr.get("ementa"),
            "chegou": pr.get("dataApresentacao"), "tramitando": pr.get("tramitando") == "Sim",
            "ccj": ccj, "plenario": plen, "minimoSim": MAIORIA_SENADO, "fontes": [f, f_api]}


VAGA = (r"vaga\s+decorrente\s+d[aoe]\s+(aposentadoria(?:\s+volunt[áa]ria)?|falecimento)\s+(?:d[aoe]\s+)?(?:Ministr[oa]\s+)?"
        r"([^.;,\[]+?)\s*(?:[.;,\[]|$)")


def vaga_de(texto: str | None) -> dict | None:
    """'na vaga decorrente da aposentadoria do Ministro Luís Roberto Barroso.' -> {motivo, de}."""
    m = re.search(VAGA, texto or "")
    if not m:
        return None
    return {"motivo": "falecimento" if m.group(1).startswith("falec") else "aposentadoria", "de": m.group(2).strip()}


def indicacoes_recentes(rede: Rede) -> list[dict]:
    """Mensagens (MSF) com indicação para o STF neste ano e no anterior (para explicar uma cadeira vazia)."""
    out = []
    ano = int(hoje()[:4])
    for a in (ano - 1, ano):
        for x in rede.json(f"{SEN}/processo?sigla=MSF&ano={a}", f"senado/msf-{a}.json", FOLGA_H) or []:
            e = x.get("ementa") or ""
            n = re.match(r"MSF\s+(\d+)/(\d{4})", x.get("identificacao") or "")
            if n and re.search(r"Ministr[oa] do Supremo Tribunal Federal", e):
                # o nome de quem foi indicado é o trecho todo em maiúsculas ("o nome do Senhor JORGE RODRIGO ARAÚJO MESSIAS")
                caps = re.findall(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}|D[AEO]S?|E))+", e)
                out.append({"numero": int(n.group(1)), "ano": int(n.group(2)), "nome": nome_proprio(max(caps, key=len)) if caps else None,
                            "ementa": e, "id": x["id"]})
    return out


# ---------------------------------------------------------------- foto
def foto(rede: Rede, url: str | None, pid: str) -> str | None:
    """Foto oficial reduzida para 240 px em img/pessoas/<pid>.jpg (a mesma regra das outras fotos do site)."""
    destino, rel = FOTOS / f"{pid}.jpg", f"img/pessoas/{pid}.jpg"
    if not url:
        return rel if destino.exists() else None
    try:
        from PIL import Image
        nome = "fotos/" + (f"stf-imagem-{url.rsplit('=', 1)[-1]}.jpg" if "imagem.asp" in url else re.sub(r"[^\w.-]", "_", url.rsplit("/", 1)[-1]))
        bruto = rede.get(url, nome, 30 * 24)
        im = Image.open(io.BytesIO(bruto)).convert("RGB")
        if im.width > 240:
            im = im.resize((240, round(im.height * 240 / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
        if not destino.exists() or destino.read_bytes() != buf.getvalue():
            destino.write_bytes(buf.getvalue())
        return rel
    except Exception as e:
        log(f"  [foto] {pid}: {e}")
        return rel if destino.exists() else None


# ---------------------------------------------------------------- montagem
def montar(rede: Rede, antigo: dict) -> dict:
    hoje_ = hoje()
    h_ostf = rede.texto(URL["ostf"], "stf/ostf.html")
    ostf = ler_ostf(h_ostf)
    comp = ler_composicao(rede.texto(URL["composicao"], "stf/composicao-atual.html"))
    h_turmas = rede.texto(URL["turmas"], "stf/turmas.html")
    turmas = ler_turmas(h_turmas[h_turmas.find("Primeira Turma"):], URL["turmas"])
    ids = ler_ids_stf(rede.texto(URL["antiguidade"], "stf/antiguidade.html"))
    pastas_todas = ler_pastas_antiguidade(rede.texto(URL["antiguidade_bib"], "stf/pastas-antiguidade.html"))
    h_pres = rede.texto(URL["presidentes"], "stf/presidentes.html")
    if len(ostf["plenario"]) < 8:
        raise Falha(f"página O STF: só {len(ostf['plenario'])} ministros")

    f_ostf = fonte("Supremo Tribunal Federal", "O STF: composição do Plenário, Turmas e presidência", URL["ostf"])
    f_comp = fonte("Supremo Tribunal Federal", "Pastas dos Ministros: Composição Atual (ordem oficial)", URL["composicao"])
    f_turmas = fonte("Supremo Tribunal Federal", "Composição das Turmas", URL["turmas"])
    f_pres = fonte("Supremo Tribunal Federal", "Histórico de Presidentes do STF", URL["presidentes"])

    por_chave = {chave(x["nome"]): x for x in comp}
    curtos = {chave(v["nomeCivil"]): v["nome"] for v in ids.values()}
    antigos = {m.get("idStf"): m for m in (antigo.get("ministros") or []) if m.get("idStf")}
    antigos_id = {m["id"]: m for m in (antigo.get("ministros") or [])}
    ministros = []
    for p in ostf["plenario"]:
        k = chave(p["nome"])
        c = por_chave.get(k) or {}
        pasta = c.get("pasta") or (pastas_todas.get(k) or {}).get("pasta")
        if not pasta:
            raise Falha(f"sem pasta na Biblioteca do STF: {p['nome']}")
        if not p["gabinete"]:  # quem preside não tem o link no cartão da página O STF: o link do gabinete tem o nome da pasta
            m = re.search(r'href="([^"]*servico=sobreStfMinistr[oa]' + pasta + r'&[^"]*)"', h_ostf)
            p["gabinete"] = absoluta(URL["ostf"], m.group(1)) if m else None
        # o link do gabinete nas Turmas da página O STF é o completo ("...&pagina=principal"); no cartão, às vezes falta
        lt = next((x["link"] for t in ostf["turmas"].values() for x in t if chave(x["nome"]) == k and "sobreStfMinistr" in x["link"]), None)
        if lt:
            p["gabinete"] = lt
        url_p, url_dd = BIB + pasta + "Principal", BIB + pasta + "DadosDatas"
        pa = ler_pasta(rede.texto(url_p, f"stf/pasta-{pasta}.html"), url_p)
        dd = ler_dados_datas(rede.texto(url_dd, f"stf/dados-datas-{pasta}.html"), url_dd)
        idb = ids.get(k) or {}
        id_stf = idb.get("id")
        # a foto oficial é a da página do ministro no STF ("Ministros do STF"): o mesmo tipo de retrato para todos
        foto_url = pa["foto"]
        if id_stf:
            try:
                hv = rede.texto(f"{STF}/ostf/ministros/verMinistro.asp?periodo=STF&id={id_stf}", f"stf/ministro-{id_stf}.html")
                mi = re.search(r"imagem\.asp\?(?:tamanho=miniatura&(?:amp;)?)?id=(\d+)", hv)
                if mi:
                    foto_url = f"{STF}/util/imagem.asp?id={mi.group(1)}"
            except Falha as e:
                log(f"  ⚠️ {p['nome']}: {e}; fica a foto da Biblioteca")
        ant = antigos.get(id_stf) or {}
        pid = ant.get("id") or "stf-" + slug(p["nome"])
        if not ant and pid in antigos_id and antigos_id[pid].get("idStf") not in (None, id_stf):
            pid += f"-{id_stf}"  # outra pessoa com o mesmo nome curto
        posse = pa["datas"].get("posse") or (p["data"] if not p["presidente"] else None)
        if posse and p["data"] and not p["presidente"] and posse != p["data"]:
            log(f"  ⚠️ {p['nome']}: posse {posse} (Pasta) ≠ {p['data']} (página O STF); vale a da Pasta")
        f_pasta = fonte("Supremo Tribunal Federal (Biblioteca)", f"Pasta do Ministro {p['nome']}: dados biográficos e datas", url_p)
        f_dd = fonte("Supremo Tribunal Federal (Biblioteca)", f"Pasta do Ministro {p['nome']}: Dados e Datas (indicação, Senado, nomeação e posse)", url_dd)
        sen = None
        if dd["msf"]:
            try:
                sen = senado(rede, dd["msf"]["numero"], dd["msf"]["ano"], p["nome"])
            except Falha as e:
                log(f"  ⚠️ {p['nome']}: {e}; fica o bloco do Senado de antes")
                sen = ant.get("senado")
        else:
            log(f"  ⚠️ {p['nome']}: Dados e Datas sem o número da mensagem no Senado")
            sen = ant.get("senado")
        # a vaga: a ementa da mensagem no Senado primeiro (a citação do decreto na Biblioteca às vezes encurta o nome), com o
        # nome que o STF usa para quem saiu ("Rosa Maria Pires Weber" -> "Rosa Weber")
        vaga = vaga_de((sen or {}).get("ementa")) or dd["vaga"]
        if vaga:
            vaga["nome"] = curtos.get(chave(vaga["de"])) or vaga["de"]
        nasc = pa["nascimento"]
        ministros.append({
            "id": pid, "idStf": id_stf, "pasta": pasta,
            "nome": p["nome"], "nomeCivil": pa["nomeCivil"] or idb.get("nomeCivil"), "genero": p["genero"] or c.get("genero"),
            "papel": "presidente" if p["presidente"] else None, "decano": False, "turma": None, "presideTurma": False,
            "foto": None, "fotoUrl": foto_url, "fotoCredito": "Supremo Tribunal Federal",
            "nascimento": nasc, "naturalidade": pa["naturalidade"],
            "aposentadoria": {"data": faz_anos(nasc, IDADE_LIMITE), "idade": IDADE_LIMITE, "fontes": [EC88, f_pasta]} if nasc else None,
            "indicacao": {"presidente": dd["presidente"], "presidenteGenero": dd["presidenteGenero"], "data": dd["mensagemData"] or pa["datas"].get("indicacao"),
                          "mensagem": dd["mensagem"], "dou": dd["douIndicacao"], "vaga": vaga,
                          "fontes": [f_dd] + ([fonte("Diário Oficial da União (cópia na Biblioteca do STF)", f"{dd['mensagem'] or 'Mensagem ao Senado'}", dd["pdf"]["indicacao"])]
                                              if dd["pdf"].get("indicacao") else [])},
            "senado": sen,
            "nomeacao": {"data": dd["decretoData"] or pa["datas"].get("nomeacao"), "decreto": dd["decreto"], "aPartirDe": dd["aPartirDe"],
                         "dou": dd["dou"], "douData": dd["douData"],
                         "fontes": [f_dd] + ([fonte("Diário Oficial da União (cópia na Biblioteca do STF)", f"{dd['decreto'] or 'Decreto de nomeação'}: {dd['dou'] or ''}".strip(": "),
                                                    dd["pdf"]["nomeacao"])] if dd["pdf"].get("nomeacao") else [])},
            "posse": {"data": posse, "fontes": [f_pasta, f_ostf]},
            "presidencia": {"posse": pa["datas"].get("presidencia")} if p["presidente"] else None,
            "links": {"gabinete": p["gabinete"], "pasta": url_p, "curriculo": pa["curriculo"],
                      "biografia": f"{STF}/ostf/ministros/verMinistro.asp?periodo=STF&id={id_stf}" if id_stf else None},
            "fontes": [f_pasta, f_dd, f_ostf],
        })

    # papéis: presidente e vice (página O STF, "Gestão"; Composição Atual), Turmas, decano
    gest = ostf["gestao"]
    papeis_comp = {chave(x["nome"]): x["papel"] for x in comp if x["papel"]}
    for m in ministros:
        k = chave(m["nome"])
        if gest.get("vice") and chave(gest["vice"]) == k:
            m["papel"] = "vice"
        if gest.get("presidente") and chave(gest["presidente"]) == k:
            m["papel"] = "presidente"
        pc = {"Presidente": "presidente", "Vice-Presidente": "vice"}.get(papeis_comp.get(k) or "")
        if pc and pc != m["papel"]:
            log(f"  ⚠️ {m['nome']}: papel na Composição Atual ({papeis_comp[k]}) ≠ página O STF ({m['papel']})")
    if sum(1 for m in ministros if m["papel"] == "presidente") != 1 or sum(1 for m in ministros if m["papel"] == "vice") != 1:
        raise Falha("não achei um presidente e um vice")
    if not turmas or len(turmas) < 2:
        log("  ⚠️ página Turmas sem as duas Turmas; vale a página O STF")
        turmas = ostf["turmas"]
    elif {n: [chave(x["nome"]) for x in t] for n, t in turmas.items()} != {n: [chave(x["nome"]) for x in t] for n, t in ostf["turmas"].items()}:
        log("  ⚠️ as Turmas da página Turmas ≠ as da página O STF; vale a página Turmas")
    por_k = {chave(m["nome"]): m for m in ministros}
    lista_turmas = []
    for n in sorted(turmas):
        membros = []
        for x in turmas[n]:
            m = por_k.get(chave(x["nome"]))
            if not m:
                log(f"  ⚠️ {n}ª Turma: {x['nome']} não está na composição")
                continue
            m["turma"], m["presideTurma"] = n, bool(x["presidente"])
            membros.append(m)
        if sum(1 for m in membros if m["presideTurma"]) != 1:
            log(f"  ⚠️ {n}ª Turma sem um presidente claro")
        lista_turmas.append({"numero": n, "nome": "Primeira Turma" if n == 1 else "Segunda Turma",
                             "presidente": next((m["id"] for m in membros if m["presideTurma"]), None),
                             "membros": [m["id"] for m in sorted(membros, key=lambda m: (not m["presideTurma"], antiguidade(m)))],
                             "cadeiras": CADEIRAS_TURMA})
    sem_turma = [m["nome"] for m in ministros if m["turma"] is None and m["papel"] != "presidente"]
    if sem_turma:
        log(f"  ⚠️ sem Turma: {', '.join(sem_turma)}")
    # ordem oficial: presidente, vice e os outros por antiguidade (RISTF art. 17: posse, nomeação, idade)
    ministros.sort(key=lambda m: ({"presidente": 0, "vice": 1}.get(m["papel"] or "", 2), antiguidade(m)))
    decano = min(ministros, key=antiguidade)
    decano["decano"] = True
    if papeis_comp and not any(v in ("Decano", "Decana") and k == chave(decano["nome"]) for k, v in papeis_comp.items()):
        log(f"  ⚠️ decano calculado ({decano['nome']}) ≠ o da Composição Atual")
    ordem_comp = [chave(x["nome"]) for x in comp]
    if ordem_comp and ordem_comp != [chave(m["nome"]) for m in ministros]:
        log("  ⚠️ a ordem calculada ≠ a ordem da Composição Atual da Biblioteca: " + " | ".join(m["nome"] for m in ministros))

    pres = next(m for m in ministros if m["papel"] == "presidente")
    vice = next(m for m in ministros if m["papel"] == "vice")
    presidencia = {"presidente": pres["id"], "vice": vice["id"], "desde": (pres.get("presidencia") or {}).get("posse"),
                   "periodo": ler_presidencia(h_pres, pres["nome"]), "anos": 2,
                   "fontes": [f_ostf, f_pres, fonte("Supremo Tribunal Federal (Biblioteca)", f"Pasta do Ministro {pres['nome']}: posse na Presidência",
                                                      BIB + pres["pasta"] + "Principal"), RISTF]}
    if not presidencia["desde"]:
        log("  ⚠️ sem a data da posse na presidência")

    vagas = montar_vagas(rede, ministros, antigo, pastas_todas)
    for m in ministros:  # sem a foto nova (site fora do ar), fica a de antes
        m["foto"] = foto(rede, m["fotoUrl"], m["id"]) or (antigos_id.get(m["id"]) or {}).get("foto")
    return {
        "tribunal": "Supremo Tribunal Federal", "sigla": "STF", "cadeiras": CADEIRAS, "cadeirasTurma": CADEIRAS_TURMA,
        "idadeLimite": IDADE_LIMITE, "maioriaSenado": MAIORIA_SENADO,
        "presidencia": presidencia,
        "turmas": lista_turmas, "fonteTurmas": [f_turmas, f_ostf, RISTF],
        "ministros": ministros,
        "vagas": vagas,
        "decisoes": {**ostf["decisoes"], "fonte": f_ostf} if ostf["decisoes"] else None,
        "links": {"corteAberta": ostf["links"].get("corteAberta") or CORTE_ABERTA, "corteAbertaSobre": CORTE_ABERTA_SOBRE,
                  "composicao": URL["composicao"], "turmas": URL["turmas"], "ostf": URL["ostf"]},
        "regras": {"fontes": [CF, CF_SENADO, EC122, EC88, RISTF]},
        "fontes": [f_ostf, f_comp, f_turmas, f_pres],
        "conferido": hoje_, "atualizado": hoje_,
    }


def antiguidade(m: dict) -> tuple:
    """RISTF art. 17: a antiguidade conta pela posse; depois, pela nomeação; depois, pela idade (o mais velho primeiro)."""
    return ((m.get("posse") or {}).get("data") or "9999", (m.get("nomeacao") or {}).get("data") or "9999", m.get("nascimento") or "9999")


def montar_vagas(rede: Rede, ministros: list[dict], antigo: dict, pastas_todas: dict) -> list[dict]:
    """Cadeiras vazias (11 menos quem está no tribunal): de quem era a cadeira, desde quando, e as indicações que o Senado
    recebeu para ela (com o resultado). A pista vem das mensagens ao Senado ("na vaga decorrente da aposentadoria do
    Ministro X") e de quem saiu desde a última leitura."""
    faltam = CADEIRAS - len(ministros)
    if faltam <= 0:
        return []
    atuais = {chave(m["nome"]) for m in ministros} | {chave(m.get("nomeCivil") or "") for m in ministros}
    vagas: dict[str, dict] = {}
    try:
        recentes = indicacoes_recentes(rede)
    except Falha as e:
        log(f"  ⚠️ Senado (indicações recentes): {e}; ficam as vagas de antes")
        return antigo.get("vagas") or [{"de": None}] * faltam
    for x in recentes:
        if x["nome"] and chave(x["nome"]) in atuais:
            continue
        vg = vaga_de(x["ementa"])
        if not vg or chave(vg["de"]) in atuais:
            continue
        de = vg["de"]
        v = vagas.setdefault(chave(de), {"de": de, "motivo": vg["motivo"], "indicacoes": []})
        try:
            s = senado(rede, x["numero"], x["ano"], x["nome"] or "")
        except Falha as e:
            log(f"  ⚠️ {e}")
            continue
        s["nome"] = x["nome"]
        v["indicacoes"].append(s)
    # quem estava na leitura anterior e não está mais (aposentadoria, falecimento...)
    for m in antigo.get("ministros") or []:
        k = chave(m["nome"])
        if k not in atuais and k not in vagas and len(vagas) < faltam:
            vagas[k] = {"de": m["nome"], "motivo": None, "indicacoes": []}
    out = []
    for k, v in vagas.items():
        info = pastas_todas.get(k) or {}
        pasta, saida = info.get("pasta"), None
        if info.get("nome"):
            v["de"] = info["nome"]  # o nome que o STF usa (o da mensagem ao Senado pode ser o nome completo)
        if pasta:
            try:
                url = BIB + pasta + "Principal"
                pa = ler_pasta(rede.texto(url, f"stf/pasta-{pasta}.html"), url)
                tipo = "aposentadoria" if pa["datas"].get("aposentadoria") else "falecimento" if pa["datas"].get("falecimento") else None
                if tipo:
                    v["motivo"] = v.get("motivo") or tipo
                    saida = {"data": pa["datas"][tipo],
                             "fonte": fonte("Supremo Tribunal Federal (Biblioteca)", f"Pasta do Ministro {v['de']}: {tipo}", url)}
            except Falha as e:
                log(f"  ⚠️ pasta de {v['de']}: {e}")
        v["desde"] = saida["data"] if saida else None
        v["fontes"] = [saida["fonte"]] if saida else []
        v["indicacoes"].sort(key=lambda s: s.get("chegou") or "")
        v["pendente"] = any(s.get("tramitando") for s in v["indicacoes"])
        out.append(v)
    out.sort(key=lambda v: v.get("desde") or "9999")
    while len(out) < faltam:
        out.append({"de": None, "motivo": None, "desde": None, "indicacoes": [], "pendente": False, "fontes": []})
    return out[:faltam]


# ---------------------------------------------------------------- conferências e avisos
def conferir(novo: dict) -> list[str]:
    """Problemas que impedem gravar (fica o arquivo de antes)."""
    prob = []
    ms = novo["ministros"]
    if not 8 <= len(ms) <= CADEIRAS:
        prob.append(f"{len(ms)} ministros")
    for m in ms:
        for campo in ("nome", "nascimento"):
            if not m.get(campo):
                prob.append(f"{m.get('nome')}: sem {campo}")
        if not (m.get("posse") or {}).get("data"):
            prob.append(f"{m.get('nome')}: sem a data da posse")
        if not (m.get("indicacao") or {}).get("presidente"):
            prob.append(f"{m.get('nome')}: sem quem indicou")
        p = (m.get("senado") or {}).get("plenario") or {}
        if p.get("sim") is None:
            prob.append(f"{m.get('nome')}: sem o placar do Plenário do Senado")
    if len({m["id"] for m in ms}) != len(ms):
        prob.append("ids repetidos")
    return prob


def mudancas(antigo: dict, novo: dict) -> list[str]:
    """O que mudou no tribunal desde a leitura anterior (para o log e o resumo do robô)."""
    if not antigo.get("ministros"):
        return []
    a = {m["id"]: m for m in antigo["ministros"]}
    n = {m["id"]: m for m in novo["ministros"]}
    out = [f"saiu do STF: {a[k]['nome']}" for k in a if k not in n]
    out += [f"entrou no STF: {n[k]['nome']} (posse em {(n[k].get('posse') or {}).get('data')})" for k in n if k not in a]
    for papel, nome in (("presidente", "presidência"), ("vice", "vice-presidência")):
        x, y = (antigo.get("presidencia") or {}).get(papel), (novo.get("presidencia") or {}).get(papel)
        if x != y:
            out.append(f"{nome}: {a.get(x, {}).get('nome', x)} → {n.get(y, {}).get('nome', y)}")
    for k in n:
        if k in a and (a[k].get("turma"), a[k].get("presideTurma")) != (n[k].get("turma"), n[k].get("presideTurma")):
            out.append(f"{n[k]['nome']}: Turma {a[k].get('turma')}{' (presidente)' if a[k].get('presideTurma') else ''} → "
                       f"{n[k].get('turma')}{' (presidente)' if n[k].get('presideTurma') else ''}")
    ind_a = {(s.get("materia"), (s.get("plenario") or {}).get("resultado"), s.get("tramitando")) for v in antigo.get("vagas") or [] for s in v.get("indicacoes") or []}
    for v in novo.get("vagas") or []:
        for s in v.get("indicacoes") or []:
            if (s.get("materia"), (s.get("plenario") or {}).get("resultado"), s.get("tramitando")) not in ind_a:
                res = (s.get("plenario") or {}).get("resultado") or ("em análise" if s.get("tramitando") else "sem resultado")
                out.append(f"indicação no Senado: {s.get('nome')} ({s.get('materia')}): {res}")
    if len(antigo.get("vagas") or []) != len(novo.get("vagas") or []):
        out.append(f"cadeiras vazias: {len(antigo.get('vagas') or [])} → {len(novo.get('vagas') or [])}")
    return out


def avisa(txt: str) -> None:
    log("⚠️ STF: " + txt)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=STF::{txt}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agora", action="store_true", help="lê já, mesmo sem ter passado uma semana")
    ap.add_argument("--cache", action="store_true", help="só o que já está em .cache/stf/, sem rede")
    a = ap.parse_args()
    antigo = ler_json(ARQ, {}) or {}
    conf = antigo.get("conferido")
    if conf and not (a.agora or a.cache):
        dias = (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(conf)).days
        if dias < DIAS_ENTRE_LEITURAS:
            log(f"STF: conferido em {conf} (há {dias} dia(s)); a próxima leitura é daqui a {DIAS_ENTRE_LEITURAS - dias} dia(s). "
                "Para ler já: --agora")
            return
    rede = Rede(so_cache=a.cache)
    try:
        novo = montar(rede, antigo)
    except Falha as e:
        log(f"STF: {e}. Fica o arquivo de antes ({conf or 'nenhum'}).")
        return
    prob = conferir(novo)
    if prob:
        log("STF: leitura incompleta, fica o arquivo de antes: " + "; ".join(prob))
        return
    if a.cache and conf:  # sem rede, os sites não foram conferidos de novo: fica a data da última leitura
        novo["conferido"] = conf
    for txt in mudancas(antigo, novo):
        avisa(txt)
    salvar_json(ARQ, sem_mudar_data(novo, ARQ))
    log(f"STF: {len(novo['ministros'])} ministros, {len(novo['vagas'])} cadeira(s) vazia(s); presidente "
        f"{next(m['nome'] for m in novo['ministros'] if m['papel'] == 'presidente')}; {rede.pedidos} pedidos")


if __name__ == "__main__":
    main()
