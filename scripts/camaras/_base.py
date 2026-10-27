"""Ajudas comuns dos coletores das Câmaras Municipais (scripts/camaras/c<IBGE>.py), por cima de scripts/regional.py.

- partido(): a sigla que cada Câmara usa ("UNIÃO BRASIL", "REPUB", "Podemos"...) -> a sigla atual do TSE ("UNIÃO", "PODE"...),
  para o mesmo partido não aparecer com dois nomes no plenário da cidade;
- nome_limpo(): tira "Vereador(a)" do começo e arruma nomes TODOS EM MAIÚSCULAS;
- Tse: liga cada pessoa da lista oficial ao candidato do TSE de 2024 (id ver-<IBGE>-<SQ>), pelo nome, só na cidade certa;
- situacao(): texto oficial da última tramitação -> um dos 9 status do site, com regras pensadas para Câmaras de uma casa só
  (o "aprovado" final vai para a sanção do prefeito; "veto rejeitado" quer dizer que a Câmara derrubou o veto...);
- salvar(): grava dados/camaras/<IBGE>.json (lista oficial) e dados/camaras/extras/<IBGE>.json (um arquivo por cidade, com
  o que a Câmara publica a mais sobre cada vereador e sobre o prefeito) e devolve o resumo para dados/legislativos.json.
Arquivos que começam com "_" não são coletores (scripts/legislativos.py pula).
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

import regional
from comum import (CACHE, DADOS, EXTRAS_CIDADES, FOTOS, UA, baixar, fonte, hoje, ler_json, log, nome_proprio, salvar_json,
                   sem_acento, sem_mudar_data, slug)

INICIO = regional.INICIO_MUNICIPAL  # 2025-01-01, começo da legislatura municipal atual
# o que cada Câmara já leu (estado da carga, páginas guardadas, fotos): .cache/camaras/<IBGE>/. CAMARAS_CACHE no ambiente
# escolhe outra pasta (ex.: simular o robô do GitHub, que começa com o cache vazio, sem mexer no cache da pasta de trabalho)
PASTA_CACHE = Path(os.environ["CAMARAS_CACHE"]).resolve() if os.environ.get("CAMARAS_CACHE") else CACHE / "camaras"
# formato dos robôs de busca: alguns sites barram quem não começa com "Mozilla/5.0", mas continua dizendo quem somos
UA_COMPAT = "Mozilla/5.0 (compatible; EntendaPolitica/1.0; +https://entendapolitica.vercel.app)"
TOKEN_ROBOTS = "EntendaPolitica"  # o nome do nosso robô nas regras do robots.txt
# só as capitais guardam a foto oficial reduzida em img/pessoas/ (limite de arquivos do site); nas outras cidades vale a foto
# do TSE (que a lista da cidade já tem) ou o endereço oficial da foto na Câmara
CAPITAIS = {"3550308", "3304557", "3106200", "2927408", "2304400", "2611606", "4106902", "4314902", "1302603", "1501402",
            "5208707", "2111300", "2704302", "2211001", "2408102", "5002704", "2507507", "2800308", "5103403", "4205407",
            "1100205", "1600303", "1200401", "3205309", "1400100", "1721000"}


# ---------------------------------------------------------------- robots.txt e intervalo entre pedidos
class Regras:
    """O que o robots.txt de um servidor permite ao nosso robô e o intervalo pedido (Crawl-delay, em segundos).
    As regras de caminho seguem a RFC 9309 (o "*" vale qualquer sequência, "$" marca o fim, a regra mais longa vale), que o
    urllib.robotparser não entende sozinho."""

    def __init__(self, parser: urllib.robotparser.RobotFileParser | None = None, atraso: float | None = None):
        self.parser, self.atraso = parser, float(atraso or 0)

    def pode(self, url: str) -> bool:
        if self.parser is None:
            return True
        grupo = next((g for g in self.parser.entries if g.applies_to(TOKEN_ROBOTS)), None) or self.parser.default_entry
        if grupo is None:
            return True
        p = urllib.parse.urlsplit(url)
        caminho = urllib.parse.unquote(p.path or "/") + (f"?{urllib.parse.unquote(p.query)}" if p.query else "")
        melhor = None
        for regra in grupo.rulelines:
            r = urllib.parse.unquote(regra.path or "")
            if not r:
                continue
            exp = re.escape(r).replace(r"\*", ".*")
            if exp.endswith(r"\$"):
                exp = exp[:-2] + "$"
            if re.match(exp, caminho):
                if melhor is None or len(r) > melhor[0] or (len(r) == melhor[0] and regra.allowance):
                    melhor = (len(r), regra.allowance)
        return True if melhor is None else bool(melhor[1])


_ROBOTS: dict[str, Regras] = {}
_ROBOTS_TRAVAS: dict[str, threading.Lock] = {}
_TRAVA = threading.Lock()
_ULTIMO: dict[str, float] = {}  # servidor -> hora do último pedido (todas as Casas desta rodada)


def raiz(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


def robots(url: str, ua: str | None = None, contexto=None) -> Regras:
    """robots.txt do servidor de `url`, lido uma vez por rodada (RFC 9309): 2xx = as regras dele; 4xx = pode ler tudo;
    5xx ou sem resposta = RuntimeError (não lê nada desse servidor nesta rodada)."""
    r = raiz(url)
    with _TRAVA:
        trava = _ROBOTS_TRAVAS.setdefault(r, threading.Lock())
    with trava:
        if r in _ROBOTS:
            return _ROBOTS[r]
        try:
            req = urllib.request.Request(r + "/robots.txt", headers={"User-Agent": ua or UA})
            with urllib.request.urlopen(req, timeout=30, context=contexto) as resp:
                texto = resp.read(500_000).decode("utf-8", "replace")
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(texto.splitlines())
            regras = Regras(rp, rp.crawl_delay(TOKEN_ROBOTS))
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                regras = Regras()
            else:
                raise RuntimeError(f"robots.txt de {r}: HTTP {e.code}; nada é lido desse servidor nesta rodada")
        except Exception as e:
            raise RuntimeError(f"robots.txt de {r} não respondeu ({type(e).__name__}); nada é lido desse servidor nesta rodada")
        with _TRAVA:
            _ULTIMO[r] = time.time()
        _ROBOTS[r] = regras
        return regras


def esperar_vez(url: str, pausa: float = 0.5, ua: str | None = None, contexto=None) -> None:
    """Antes de um pedido: confere o robots.txt (Disallow) e espera o intervalo do servidor (o maior entre o Crawl-delay e
    a pausa do coletor), contado do fim do pedido anterior ao mesmo servidor."""
    regras = robots(url, ua, contexto)
    if not regras.pode(url):
        raise RuntimeError(f"o robots.txt de {raiz(url)} não deixa ler {urllib.parse.urlsplit(url).path}")
    r = raiz(url)
    intervalo = max(pausa, regras.atraso)
    while True:
        with _TRAVA:
            falta = _ULTIMO.get(r, 0) + intervalo - time.time()
            if falta <= 0:
                _ULTIMO[r] = time.time()
                return
        time.sleep(min(falta, 5))


def pedido_feito(url: str) -> None:
    """Depois de um pedido: o intervalo até o próximo conta a partir daqui."""
    with _TRAVA:
        _ULTIMO[raiz(url)] = time.time()

# ---------------------------------------------------------------- partidos
# siglas atuais (TSE, eleição de 2026) + fusões e mudanças de nome já registradas no TSE
_PARTIDOS = {
    "UNIAO": "UNIÃO", "UNIAO BRASIL": "UNIÃO", "UB": "UNIÃO", "DEM": "UNIÃO", "PSL": "UNIÃO",
    "REPUBLICANOS": "REPUBLICANOS", "REP": "REPUBLICANOS", "REPUB": "REPUBLICANOS", "REPUBLICA": "REPUBLICANOS",
    "PRB": "REPUBLICANOS", "REPUBLICANO": "REPUBLICANOS",
    "PODEMOS": "PODE", "PODE": "PODE", "PSC": "PODE", "PHS": "PODE",
    "PCDOB": "PCdoB", "PC DO B": "PCdoB", "PC B": "PCdoB",
    "SD": "SOLIDARIEDADE", "SDD": "SOLIDARIEDADE", "SOLIDARIEDADE": "SOLIDARIEDADE", "PROS": "SOLIDARIEDADE",
    "PROGRESSISTAS": "PP", "PP": "PP",
    "PTB": "PRD", "PATRIOTA": "PRD", "PATRI": "PRD", "PEN": "PRD", "PRD": "PRD",
    "PMN": "MOBILIZA", "MOBILIZA": "MOBILIZA", "PTC": "AGIR", "AGIR": "AGIR", "PPS": "CIDADANIA", "CIDADANIA": "CIDADANIA",
    "PR": "PL", "PL": "PL", "PMDB": "MDB", "MDB": "MDB", "MISSAO": "MISSÃO", "PARTIDO MISSAO": "MISSÃO",
    "NOVO": "NOVO", "PARTIDO NOVO": "NOVO", "REDE": "REDE", "REDE SUSTENTABILIDADE": "REDE",
    "PARTIDO DOS TRABALHADORES": "PT", "PARTIDO LIBERAL": "PL", "PARTIDO SOCIAL DEMOCRATICO": "PSD",
    "PARTIDO SOCIALISTA BRASILEIRO": "PSB", "PARTIDO DEMOCRATICO TRABALHISTA": "PDT", "PARTIDO VERDE": "PV",
    "DEMOCRACIA CRISTA": "DC", "MOVIMENTO DEMOCRATICO BRASILEIRO": "MDB", "PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA": "PSDB",
    "PARTIDO SOCIALISMO E LIBERDADE": "PSOL", "PARTIDO RENOVACAO DEMOCRATICA": "PRD", "MOBILIZACAO NACIONAL": "MOBILIZA",
}
SEM_PARTIDO = "Sem partido"


def partido(sigla: str | None) -> str | None:
    """Sigla como a Câmara escreve -> sigla atual do TSE. None quando a Câmara não informa."""
    s = re.sub(r"\s+", " ", (sigla or "").strip())
    if not s:
        return None
    k = re.sub(r"[^A-Z0-9 ]", "", sem_acento(s).upper()).strip()
    if re.search(r"NAO POSSUI|SEM PARTIDO|SEM FILIACAO|^S ?P$|^SP$", k):
        return SEM_PARTIDO
    if k in _PARTIDOS:
        return _PARTIDOS[k]
    junto = k.replace(" ", "")
    achados = {sig for nome, sig in _PARTIDOS.items()  # "UNIAOBRASIL", "REPUBLIC." (abreviado), "CIDAD."
               if junto == nome.replace(" ", "") or (len(junto) >= 5 and nome.replace(" ", "").startswith(junto))}
    if len(achados) == 1:
        return achados.pop()
    return s.upper() if len(s) <= 14 else s


# ---------------------------------------------------------------- nomes
_TITULO = re.compile(r"^(vereador[a]?|ver\.|vereadora?\(?a?\)?)\s+", re.I)


def nome_limpo(nome: str | None) -> str | None:
    """'Vereador Fulano' -> 'Fulano'; 'FULANO DA SILVA' -> 'Fulano da Silva' (só quando está todo em maiúsculas)."""
    n = re.sub(r"\s+", " ", (nome or "").strip())
    n = _TITULO.sub("", n).strip()
    n = re.sub(r"\s*\(c[aâ]mara digital\)\s*$", "", n, flags=re.I).strip(" .")  # rótulos do sistema, não fazem parte do nome
    if not n:
        return None
    letras = [c for c in n if c.isalpha()]
    if letras and all(c.isupper() for c in letras) and len(letras) > 3:
        n = nome_proprio(n)
        n = re.sub(r"\b(DR|DRA|PROF|PROFA|SGT|CEL|CAP|TEN|PR|PRA)\b", lambda m: m.group(1).capitalize(), n, flags=re.I)
    return n


# ---------------------------------------------------------------- TSE
def cidade(ibge: str, uf: str) -> dict:
    """dados/cidades/<UF>/<IBGE>.json (prefeito, vice e a lista de vereadores da página da cidade)."""
    return ler_json(DADOS / "cidades" / uf / f"{ibge}.json") or {}


def _fotos_e_fontes(c: dict) -> list[str]:
    textos = []
    for p in [c.get("prefeito") or {}, c.get("vice") or {}] + list((c.get("vereadores") or {}).get("membros") or []):
        textos.append(p.get("foto") or "")
        for f in p.get("fontes") or []:
            textos.append(f.get("url") or "")
    return textos


def ue_da_cidade(ibge: str, uf: str) -> str | None:
    """Código TSE do município (SG_UE), tirado das fotos/fontes do DivulgaCandContas em dados/cidades/<UF>/<IBGE>.json."""
    for t in _fotos_e_fontes(cidade(ibge, uf)):
        m = re.search(r"divulgacandcontas\.tse\.jus\.br/divulga/rest/arquivo/img/\d+/\d+/(\d+)", t)
        if m:
            return m.group(1)
        m = re.search(r"/candidato/[A-Z-]+/[A-Z]{2}/\d+/\d+/\d{4}/(\d+)", t)
        if m:
            return m.group(1)
    return None


def modelo_foto_tse(ibge: str, uf: str) -> str | None:
    """Endereço da foto de candidato no DivulgaCandContas (TSE) com {sq} no lugar do número do candidato, tirado de uma foto
    da própria cidade (ex.: https://divulgacandcontas.tse.jus.br/divulga/rest/arquivo/img/2045202024/{sq}/49590)."""
    for p in list((cidade(ibge, uf).get("vereadores") or {}).get("membros") or []):
        m = re.match(r"(https://divulgacandcontas\.tse\.jus\.br/divulga/rest/arquivo/img/\d+/)\d+(/\d+)$", p.get("foto") or "")
        if m:
            return m.group(1) + "{sq}" + m.group(2)
    return None


_CANDS: dict[str, dict[str, list]] = {}
_CANDS_TRAVA = threading.Lock()


def _candidatos(uf: str, ue: str) -> list[dict]:
    with _CANDS_TRAVA:  # várias cidades ao mesmo tempo (legislativos.py --paralelo): o arquivo do estado é lido uma vez só
        if uf not in _CANDS:
            por_ue: dict[str, list] = {}
            for c in regional.candidatos_tse(2024, {"VEREADOR"}, uf):
                por_ue.setdefault(c["ue"], []).append(c)
            _CANDS[uf] = por_ue
        return list(_CANDS[uf].get(ue) or [])


class Tse:
    """Liga a lista oficial aos candidatos do TSE de 2024 (vereador) na cidade, para usar o mesmo id do site
    (ver-<IBGE>-<SQ_CANDIDATO>). manual = {chave oficial: SQ} para quem foi conferido à mão; "-" = sem ligação."""

    def __init__(self, ibge: str, uf: str, manual: dict | None = None):
        self.ibge, self.uf = ibge, uf
        self.ue = ue_da_cidade(ibge, uf)
        if not self.ue:
            raise RuntimeError(f"não achei o código TSE (ue) de {ibge}")
        self.cands = _candidatos(uf, self.ue)
        self.por_sq = {c["sq"]: c for c in self.cands}
        self.manual = {str(k): v for k, v in (manual or {}).items()}
        self.sem_ligacao: list[str] = []

    @property
    def vagas(self) -> int:
        return sum(1 for c in self.cands if c.get("sit", "").startswith("ELEITO"))

    def ids_eleitos(self) -> set[str]:
        """ids da lista do TSE que a página da cidade mostra quando não há lista oficial (eleitos em 2024)."""
        return {f"ver-{self.ibge}-{c['sq']}" for c in self.cands if c.get("sit", "").startswith("ELEITO")}

    def casar(self, chave: str, nomes: list[str | None], partido_hoje: str | None = None) -> tuple[str, dict | None]:
        """(id no site, candidato do TSE ou None)."""
        nomes = [n for n in nomes if n]
        m = self.manual.get(str(chave))
        if m == "-":
            cand = None
        elif m:
            cand = self.por_sq.get(str(m))
            if cand is None:
                raise RuntimeError(f"SQ {m} (manual) não é candidato a vereador em {self.ibge}")
        else:
            cand = regional.casar_tse(nomes, self.cands, ue=self.ue, partido=partido_hoje)
        if cand is None:
            self.sem_ligacao.append(f"{nomes[0] if nomes else chave} ({chave})")
        return regional.id_pessoa("ver", self.ibge, cand, nomes[0] if nomes else str(chave)), cand


# ---------------------------------------------------------------- situação das propostas
# Textos (statusTxt) com tradução: os que já existem em js/traducoes.js ficam iguais; os novos levam statusTxt_en.
TXT = {
    "sancao": ("Aprovada pela Câmara; esperando a sanção do prefeito", "Approved by the City Council; waiting for the mayor to sign it"),
    "promulgar": ("Aprovada; esperando ser promulgada", "Approved; waiting to be promulgated"),
    "veto_derrubado": ("A Câmara derrubou o veto do prefeito; falta promulgar", "The City Council overrode the mayor's veto; it still has to be promulgated"),
    "veto_total": ("O prefeito vetou a proposta inteira", "The mayor vetoed the whole bill"),
    "veto_mantido": ("O prefeito vetou e a Câmara manteve o veto", "The mayor vetoed it and the City Council upheld the veto"),
    "veto_total_pendente": ("O prefeito vetou tudo; a Câmara ainda vai decidir sobre o veto", "The mayor vetoed all of it; the City Council has yet to decide on the veto"),
    "veto_pendente": ("Esperando a Câmara decidir sobre um veto do prefeito", "Waiting for the City Council to decide on a veto by the mayor"),
    "veto_parcial": ("Virou lei, com partes vetadas pelo prefeito", "Became law, with some parts vetoed by the mayor"),
    "sem_tramitacao": ("Apresentada; ainda vai começar a ser analisada", "Filed; the review has not started"),
}

# (expressão sem acento, em minúsculas) -> (status, chave de TXT ou None). A primeira que bater vale.
# Escritas olhando as listas oficiais de situações do SAPL de várias capitais (Natal, Fortaleza, Manaus, João Pessoa,
# Porto Velho, Rio Branco, Boa Vista): cada Câmara cria as suas, mas muitas vêm do modelo do Interlegis.
REGRAS = [
    # ainda falta promulgar (vem antes de "norma jurídica" e de "promulgada")
    (r"aguardando (a )?promulga|(decreto legislativo|resolucao) elaborad", "aprovada", "promulgar"),
    # esperando a sanção (vem antes das regras de veto: "Aguardando sanção/veto do Executivo")
    (r"aguardando (a )?sancao|sancao ?[/,] ?veto|sancao ou veto|(encaminhad[oa]|enviad[oa]|encaminhar|remetid[oa]) (para|a) sancao", "aprovada", "sancao"),
    # virou norma
    (r"sancionad|norma (numerada|promulgada|publicada)|transformad[oa] em (lei|decreto|resolu|norma|emenda)|"
     r"lei promulgada|veto (total ou parcial|integral ou parcial) promulgad|^(lei|lei complementar|lei ordinaria|resolucao|"
     r"decreto legislativo|emenda a lei organica)$", "lei", None),
    # veto (o "rejeitado" aqui é do veto: a proposta segue para virar lei)
    (r"solicitacao de devolucao do autografo", "outra", None),
    (r"veto.{0,40}(rejeitad|derrubad)|(rejeitad|derrubad)[oa]? o veto|rejeicao do veto pelo plenario", "aprovada", "veto_derrubado"),
    (r"veto parcial|vetad[oa] parcialmente", "lei", "veto_parcial"),
    (r"veto (total|integral)|vetad[oa] (totalmente|integralmente)", "rejeitada", "veto_total"),
    (r"veto (sobre a (proposicao|materia) )?mantido|sobre veto mantido|veto mantido", "rejeitada", "veto_mantido"),
    # "Veto acatado", "Veto acolhido tacitamente pelo Poder Legislativo", "Ofício ... comunicando a manutenção do Veto": a
    # Câmara aceitou o veto (se ele foi parcial, a norma ligada à proposta já faz dela "lei" antes de chegar aqui)
    (r"veto .{0,20}(acatad|acolhid)|(acatad|acolhid)[oa] o veto|manutencao do veto", "rejeitada", "veto_mantido"),
    (r"\bveto\b|vetad", "veto?", None),  # veto pendente: decide pelo histórico (ver situacao())
    # desistência
    (r"retirad[oa] pel[oa] autor|retirad[oa] a pedido d[oa] autor|a pedido d[oa] autor|arquivamento solicitado pelo autor|"
     r"^proposicao retirada$|^retirad[oa]$", "retirada", None),
    (r"retirad[oa] (da|de) (ordem do dia|pauta)|retirado de pauta|retirad[oa] pelo presidente", "andando", None),
    (r"desarquivad", "andando", None),
    (r"arquivad|arquivamento", "arquivada", None),
    (r"prejudicad|prejudicialidade|materia vencida", "parada", None),
    (r"anexad[oa]|apensad|tramitacao conjunta|tramitando em conjunto", "junta", None),
    # pareceres: só a decisão final conta
    (r"parecer (contrario|desfavoravel) (mantido|acatado)|parecer d[ao] .{0,40}desfavoravel acatad|aprovado parecer contrario", "rejeitada", None),
    (r"parecer (contrario|desfavoravel) rejeitad|parecer d[ao] .{0,40}(desfavoravel|contrario) rejeitad|rejeitado parecer contrario|"
     r"parecer rejeitado pela comissao", "andando", None),
    (r"parecer.{0,40}rejeitad|rejeitad[oa] (o )?parecer|parecer.{0,40}mantido|recurso (rejeitado|provido)", "outra", None),
    (r"rejeitad|nao aprovad", "rejeitada", None),
    # aprovações que não são a final
    (r"aprovad[oa] (em )?(1|primeir[oa])|aprovad[oa] em 1|1o turno|1 turno|primeira (discussao|votacao)|"
     r"aprovad[oa] o regime de urgencia|regime de urgencia aprovad|votacao do regime de urgencia|parecer.{0,30}aprovad|"
     r"aprovad[oa] (o )?parecer|aprovado voto em separado|aprovado recurso|requerimento aprovado|ata aprovada", "andando", None),
    # aprovada: vai para a sanção do prefeito (ou para a promulgação, no caso de decretos legislativos e resoluções)
    (r"sancao|autografo|enviad[oa] (ao|para o) (poder )?executivo e arquivad|^materia enviada (ao|para o) (poder )?executivo$",
     "aprovada", "sancao"),
    (r"aprovad|numero de lei", "aprovada", None),
    # ainda em discussão
    (r"aguardando|parecer|relator|comiss|pauta|ordem do dia|discuss|votac|vista|leitura|\blid[oa]\b|ciencia|protocolad|autuad|"
     r"apresentad|distribu|encaminhad|tramit|prazo|emenda|substitutiv|redacao final|procuradoria|despacho|recurso|devolvid|"
     r"devoluc|adiad|sobrestad|suspens|retorn|plenario|expediente|secretaria|gabinete|consultoria|elaboracao|analise|"
     r"audiencia|subscri|recebid|regime de urgencia|diligencia", "andando", None),
]


def norm(texto: str | None) -> str:
    """Minúsculas, sem acento, ordinais ("1ª", "2º", "2°") como letras e espaços simples, para as regras."""
    t = sem_acento((texto or "").lower()).replace("ª", "a").replace("º", "o").replace("°", "o")
    return re.sub(r"\s+", " ", t).strip()


def situacao(texto: str | None, regras_casa: list | None = None, vetos: set | None = None,
             em_tramitacao: bool | None = None, tipo: str | None = None) -> tuple[str, str | None, str | None]:
    """(status, statusTxt, statusTxt_en) a partir do texto oficial da última situação.
    vetos: o que já apareceu no histórico ({"vt"} veto total, {"vp"} veto parcial, {"vd"} veto derrubado).
    em_tramitacao: o que o sistema da Câmara diz ("em tramitação: sim/não"), usado só quando o texto não diz nada claro."""
    t = norm(texto)
    st, chave = None, None
    if not t:
        if em_tramitacao is not False:
            return "andando", *TXT["sem_tramitacao"]
        return "outra", None, None
    for exp, s, k in list(regras_casa or []) + REGRAS:
        if re.search(exp, t):
            st, chave = s, k
            break
    vetos = vetos or set()
    if st == "veto?":
        if "vd" in vetos:
            st, chave = "aprovada", "veto_derrubado"
        elif "vt" in vetos:
            st, chave = "rejeitada", "veto_total_pendente"
        elif "vp" in vetos:
            st, chave = "lei", "veto_parcial"
        else:
            st, chave = "outra", "veto_pendente"
    if chave == "sancao" and tipo in ("PDL", "PRC", "PELO"):
        chave = "promulgar"  # decreto legislativo, resolução e emenda à Lei Orgânica não vão à sanção: a Câmara promulga
    if st is None:
        st = regional.situacao_para_status(texto)
    if st == "outra" and chave is None and em_tramitacao:
        st = "andando"  # o próprio sistema da Câmara diz que ainda está em tramitação
    if chave:
        return st, TXT[chave][0], TXT[chave][1]
    return st, None, None


def flags_veto(texto: str | None) -> set:
    t = norm(texto)
    f = set()
    if re.search(r"veto.{0,40}(rejeitad|derrubad)|(rejeitad|derrubad)[oa]? o veto", t):
        f.add("vd")
    elif re.search(r"veto (total|integral)|vetad[oa] (totalmente|integralmente)", t):
        f.add("vt")
    elif re.search(r"veto parcial|vetad[oa] parcialmente", t):
        f.add("vp")
    return f


def nome_norma(tipo: str | None, numero, ano) -> str:
    """'Lei Ordinária', 8223, 2026 -> 'Lei Ordinária nº 8.223/2026'."""
    tipo = re.sub(r"\s+", " ", (tipo or "Norma").strip())
    if tipo.isupper():
        tipo = nome_proprio(tipo)
        tipo = re.sub(r"\b(Da|De|Do|Das|Dos|E|A|À)\b", lambda m: m.group(1).lower(), tipo)
    n = str(numero or "").strip()
    if n.isdigit() and len(n) > 3:
        n = f"{int(n):,}".replace(",", ".")
    return f"{tipo} nº {n}/{ano}" if ano else f"{tipo} nº {n}"


def virou(nome_lei: str, veto_parcial: bool = False) -> str:
    art = "o" if re.match(r"(decreto|ato)\b", sem_acento(nome_lei.lower())) else "a"
    return f"Virou {art} {nome_lei}" + (" (com partes vetadas)" if veto_parcial else "")


ESCOPO = ("Projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução "
          "apresentados desde 1º/1/2025 (começo da legislatura atual)")
ESCOPO_EN = ("Bills (ordinary and complementary laws, amendments to the city's Organic Law, legislative decrees and "
             "resolutions) filed since January 1, 2025 (start of the current term)")


# ---------------------------------------------------------------- fotos
def foto(url: str | None, pid: str, ibge: str, largura: int = 240, antes_de_baixar=None) -> str | None:
    """Foto oficial reduzida para 240 px em img/pessoas/<id>.jpg, como as dos perfis federais (as originais de algumas
    Câmaras têm vários MB). Só baixa de novo quando o endereço oficial da foto muda (guardado em fotos.json, no cache).
    Com o cache vazio (o robô do GitHub na primeira vez), a foto que já está no site vale e o endereço de hoje fica anotado:
    nada de baixar de novo todas as fotos, cada uma esperando o intervalo do servidor.
    antes_de_baixar: função chamada antes de um download (o orçamento e o prazo do coletor; pode lançar uma exceção).
    Devolve o caminho no site ou None."""
    if not url:
        return None
    rel, destino = f"img/pessoas/{pid}.jpg", FOTOS / f"{pid}.jpg"
    mapa_arq = PASTA_CACHE / ibge / "fotos.json"
    mapa = ler_json(mapa_arq, {}) or {}
    chave = url
    if url.startswith("data:"):  # foto embutida na própria página oficial (base64)
        import base64
        import hashlib
        bruto_b64 = url.split(",", 1)[1] if "," in url else ""
        chave = "data:" + hashlib.sha1(bruto_b64.encode()).hexdigest()
    if mapa.get(pid) == chave and destino.exists():
        return rel
    if pid not in mapa and destino.exists():
        mapa[pid] = chave
        salvar_json(mapa_arq, mapa)
        return rel
    if antes_de_baixar is not None and not url.startswith("data:"):
        antes_de_baixar()
    try:
        from PIL import Image
        if url.startswith("data:"):
            bruto = base64.b64decode(bruto_b64)
        else:
            esperar_vez(url, 0.3, UA_COMPAT)
            try:
                bruto = baixar(url, tentativas=1, timeout=90, headers={"User-Agent": UA_COMPAT})
            finally:
                pedido_feito(url)
        im = Image.open(io.BytesIO(bruto))
        im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fundo = Image.new("RGB", im.size, (255, 255, 255))
            fundo.paste(im, mask=im.split()[-1])
            im = fundo
        else:
            im = im.convert("RGB")
        if im.width > largura:
            im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
        im.save(destino, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception as e:
        print(f"  [foto] {pid}: {e}", file=sys.stderr)
        return rel if destino.exists() else None
    mapa[pid] = chave
    salvar_json(mapa_arq, mapa)
    return rel


# ---------------------------------------------------------------- só a lista oficial (Câmaras sem dados abertos de propostas)
def baixar_pagina(url: str, ibge: str, nome_cache: str, idade_h: float = 20, contexto=None, ua_navegador: bool = False) -> str:
    """Página HTML oficial, guardada em .cache/camaras/<IBGE>/http/<nome>.html (uma requisição por dia), respeitando o
    robots.txt do site (Disallow e Crawl-delay).
    ua_navegador: alguns sites barram robôs que não começam com "Mozilla/5.0"; aí usamos o formato dos robôs de busca
    ("Mozilla/5.0 (compatible; EntendaPolitica/1.0; +site)"), que continua dizendo quem somos."""
    arq = PASTA_CACHE / ibge / "http" / f"{nome_cache}.html"
    if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < idade_h:
        return arq.read_text(encoding="utf-8")
    ua = UA_COMPAT if ua_navegador else UA
    esperar_vez(url, 0.5, ua, contexto)
    try:
        if contexto is None:
            t = baixar(url, tentativas=1, timeout=120, headers={"User-Agent": ua}).decode("utf-8", "replace")
        else:  # site com a cadeia de certificados incompleta (o navegador completa sozinho; o Python não)
            import gzip
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=120, context=contexto) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
            t = b.decode("utf-8", "replace")
    finally:
        pedido_feito(url)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(t, encoding="utf-8")
    return t


# As votações de cada vereador e os gastos do mandato nas capitais que publicam só a lista em formato que dá para ler: o que
# não entra e por quê (levantamento nos sites oficiais em outubro de 2026; notas em files/plano-100/notas/camaras-r4.md).
# so_lista junta estas notas às da Câmara.
NOTAS_VOTOS_GASTOS = {
    "3304557": [  # Rio de Janeiro
        ("As votações de cada vereador não entram neste site: a Câmara registra o voto de cada vereador só nas atas das "
         "sessões (arquivos PDF e Word), sem dados abertos das votações.",
         "Each councilor's votes are not included on this site: the City Council records each councilor's vote only in the "
         "session minutes (PDF and Word files), with no open data on the votes."),
        ("Os gastos do mandato de cada vereador não entram neste site: a Câmara publica a cota de gabinete em planilhas "
         "separadas por tipo de despesa (abastecimento, alimentação, veículos blindados, selos) e por ano, sem um arquivo "
         "com os gastos de cada vereador.",
         "Each councilor's office spending is not included on this site: the City Council publishes its office allowance in "
         "separate spreadsheets by type of expense (fuel, meals, armored vehicles, postage) and by year, with no file of "
         "each councilor's spending.")],
    "4106902": [  # Curitiba
        ("As votações de cada vereador não entram neste site: o sistema de proposições da Câmara (SPL), onde ficam as "
         "votações, pede um código de imagem (CAPTCHA) a cada consulta.",
         "Each councilor's votes are not included on this site: the City Council's bills system (SPL), where the votes are, "
         "asks for an image code (CAPTCHA) for every search."),
        ("Gastos do mandato: segundo a própria Câmara, o vereador de Curitiba recebe do Legislativo só o subsídio, sem verba "
         "de gabinete nem indenizações (há apenas diárias de viagem).",
         "Office spending: according to the City Council itself, Curitiba councilors receive only their salary from the "
         "legislature, with no office allowance or reimbursements (there are only travel per diems).")],
    "3106200": [  # Belo Horizonte
        ("As votações de cada vereador não entram neste site: a Câmara publica o voto de cada vereador num arquivo PDF por "
         "votação, sem dados abertos.",
         "Each councilor's votes are not included on this site: the City Council publishes each councilor's vote in one PDF "
         "file per vote, with no open data."),
        ("Gastos do mandato: a Câmara de Belo Horizonte extinguiu a verba indenizatória em 2015 (Resolução 2.076/2015); "
         "desde então, o material e os serviços dos gabinetes são contratados e pagos pela própria Câmara (o \"custeio "
         "parlamentar\", em páginas do portal da transparência).",
         "Office spending: the Belo Horizonte City Council abolished its office allowance in 2015 (Resolution 2,076/2015); "
         "since then, the supplies and services of each office are bought and paid for by the City Council itself (shown on "
         "pages of its transparency portal).")],
    "2927408": [  # Salvador
        ("As votações de cada vereador não entram neste site: o sistema legislativo da Câmara não tem uma consulta das "
         "votações nominais (o voto de cada vereador).",
         "Each councilor's votes are not included on this site: the City Council's legislative system has no search for "
         "roll-call votes (how each councilor voted)."),
        ("Os gastos do mandato não entram neste site: a Câmara publica a Verba Compensatória de Atividade Parlamentar só "
         "como pagamentos numa tabela de despesas do portal, sem um arquivo de dados abertos por vereador.",
         "Office spending is not included on this site: the City Council publishes its office allowance only as payments in "
         "an expenses table on its portal, with no open data file per councilor.")],
    "1501402": [  # Belém
        ("As votações de cada vereador não entram neste site: a Câmara publica as votações nominais em arquivos PDF, sem "
         "dados abertos.",
         "Each councilor's votes are not included on this site: the City Council publishes its roll-call votes as PDF files, "
         "with no open data."),
        ("Gastos do mandato: a Câmara de Belém publica no portal da transparência declarações mensais de que não houve cotas "
         "parlamentares.",
         "Office spending: the Belém City Council publishes monthly statements on its transparency portal saying there were "
         "no office allowances.")],
    "2111300": [  # São Luís
        ("As votações de cada vereador não entram neste site: as atas das sessões (PDF) trazem o placar e só o nome de quem "
         "votou diferente da maioria, sem a lista completa dos votos.",
         "Each councilor's votes are not included on this site: the session minutes (PDF) give the tally and only the names "
         "of those who voted differently from the majority, without the full list of votes."),
        ("Os gastos do mandato não entram neste site: a Câmara publica a verba indenizatória (VIEP) num sistema de consulta "
         "com filtros, uma consulta por vez, sem arquivo de dados abertos.",
         "Office spending is not included on this site: the City Council publishes its office allowance (VIEP) in a search "
         "system with filters, one search at a time, with no open data file.")],
}


def bloco_votacoes(lst: list, escopo: tuple[str, str], fonte_vot: dict, ibge: str) -> dict:
    """O bloco "votacoes" do perfil de um vereador (o mesmo formato do Congresso e das Assembleias): [[chave, voto], ...]
    da mais nova para a mais antiga; o que foi votado fica no catálogo do arquivo da cidade ("arquivo")."""
    resumo = {"total": len(lst)}
    for k in ("Sim", "Não", "Abstenção"):
        resumo[k] = sum(1 for _, vt in lst if vt == k)
    resumo["Outro"] = resumo["total"] - resumo["Sim"] - resumo["Não"] - resumo["Abstenção"]
    return {"escopo": escopo[0], "escopo_en": escopo[1], "resumo": resumo, "fonte": fonte_vot,
            "arquivo": f"dados/camaras/extras/{ibge}.json", "votos": lst}


def so_lista(ibge: str, uf: str, casa: dict, pessoas: list[dict], vagas: int, notas: list[tuple[str, str]],
             tse_manual: dict | None = None, minimo: float = 0.8, votacoes=None, manter_votos: bool = False) -> dict:
    """Câmara que publica só a lista de vereadores (sem propostas em dados abertos).
    pessoas = [{chave, nome, nomeCivil?, partido (como a Câmara escreve), foto (URL), url, genero?}] tiradas da página oficial.
    Confere o tamanho (pelo menos 80% das vagas e no máximo as vagas + 3) para não gravar uma página quebrada.
    votacoes = (catálogo, {chave da pessoa: [[chave da votação, voto], ...]}, escopo (pt, en), fonte) ou None;
    manter_votos: sem votacoes (a leitura não terminou nesta rodada), ficam as votações já publicadas (votos_publicados)."""
    if not (vagas * minimo <= len(pessoas) <= vagas + 3):
        raise RuntimeError(f"a lista oficial tem {len(pessoas)} pessoas para {vagas} vagas: a página deve ter mudado")
    notas = list(notas) + NOTAS_VOTOS_GASTOS.get(ibge, [])
    tse = Tse(ibge, uf, tse_manual)
    membros, extras = [], {}
    for p in pessoas:
        nome = nome_limpo(p["nome"])
        civil = nome_limpo(p.get("nomeCivil")) if p.get("nomeCivil") else None
        sigla = partido(p.get("partido"))
        pid, cand = tse.casar(p["chave"], [nome, civil], sigla)
        supl = (cand or {}).get("sit") == "SUPLENTE"
        if not civil and cand and cand.get("nome"):
            civil = nome_limpo(cand["nome"])
        if civil and re.sub(r"\W", "", sem_acento(civil).lower()) == re.sub(r"\W", "", sem_acento(nome).lower()):
            civil = None
        g = p.get("genero") or (cand or {}).get("genero")
        m = {"id": pid, "nome": nome, "nomeCivil": civil, "partido": sigla, "genero": g if g in ("F", "M") else None,
             "foto": foto(p.get("foto"), pid, ibge), "url": p.get("url"),
             "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None}
        membros.append(m)
        x = {"links": {"oficial": p.get("url"), "email": p.get("email"), "redes": []}, "fontes": [casa["fonte"]]}
        if m["foto"]:
            x["fotoCredito"] = casa["casa"]
        if votacoes and votacoes[1].get(p["chave"]):
            x["votacoes"] = bloco_votacoes(votacoes[1][p["chave"]], votacoes[2], votacoes[3], ibge)
            x["fontes"].append(votacoes[3])
        extras[pid] = x
    ids = [m["id"] for m in membros]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"duas pessoas com o mesmo id: {sorted(i for i in ids if ids.count(i) > 1)}")
    if tse.sem_ligacao:
        log(f"  {casa.get('sigla')}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
    catalogo = votacoes[0] if votacoes else None
    if votacoes is None and manter_votos:
        catalogo, blocos = votos_publicados(ibge)
        for pid, x in extras.items():
            if pid in blocos:
                x["votacoes"] = blocos[pid]
                x["fontes"].append(blocos[pid].get("fonte"))
    com_votos = any(x.get("votacoes") for x in extras.values())
    cobertura = {"lista": True, "propostas": False, "votacoes": com_votos, "gastos": False}
    r = salvar(ibge, uf, casa, membros, extras, cobertura, notas, votacoes=catalogo if com_votos else None)
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  {casa.get('sigla')}: {len(membros)} no cargo (lista oficial, sem propostas)"
        + (f", {r.get('votacoes', 0)} votações nominais" if com_votos else ""))
    return r


# ---------------------------------------------------------------- votações nominais
def votos_publicados(ibge: str) -> tuple[dict, dict]:
    """(catálogo, {id: bloco "votacoes"}) do arquivo da cidade já publicado: quando a leitura das votações (a primeira, ou a
    da lista inteira) ainda não terminou numa rodada (no robô, que começa com o cache vazio, por exemplo), fica publicado o
    que já estava, em vez de nada."""
    d = ler_json(EXTRAS_CIDADES / f"{ibge}.json", {}) or {}
    blocos = {pid: x["votacoes"] for pid, x in (d.get("pessoas") or {}).items() if (x.get("votacoes") or {}).get("votos")}
    return (d.get("votacoes") or {}) if blocos else {}, blocos


def votos_unicos(pares, oficial: dict | None = None) -> dict:
    """{quem: voto} de uma votação, a partir dos pares (quem, voto) da fonte. Quem aparece mais de uma vez com o mesmo voto
    conta uma vez; com votos diferentes (erro da fonte), vale o voto que faz a soma bater com o placar publicado
    (``oficial`` = {"Sim": n, "Não": n, "Abstenção": n}); se nenhum (ou mais de um) fizer bater, o voto dessa pessoa
    nessa votação fica fora."""
    import itertools
    por: dict = {}
    for q, v in pares:
        if v not in por.setdefault(q, []):
            por[q].append(v)
    certos = {q: vs[0] for q, vs in por.items() if len(vs) == 1}
    duvida = {q: vs for q, vs in por.items() if len(vs) > 1}
    if duvida and oficial and len(duvida) <= 3:
        def conta(d):
            return {k: sum(1 for x in d.values() if x == k) for k in oficial}
        boas = [e for e in (dict(zip(duvida, c)) for c in itertools.product(*duvida.values()))
                if conta({**certos, **e}) == oficial]
        if len(boas) == 1:
            return {**certos, **boas[0]}
    return certos


# ---------------------------------------------------------------- gravar
def salvar_extras_cidade(ibge: str, pessoas: dict[str, dict], fontes: list | None = None, votacoes: dict | None = None) -> bool:
    """dados/camaras/extras/<IBGE>.json (regional.salvar_extras_cidade, o mesmo formato) e, quando há votações nominais, o
    catálogo delas no mesmo arquivo ("votacoes": {chave: o que foi votado, data, resultado, placar, endereço}): o perfil de
    cada vereador guarda só [chave, voto] e lê o resto daqui ("arquivo" do bloco "votacoes"). Um arquivo por cidade."""
    if not votacoes:
        return regional.salvar_extras_cidade(ibge, pessoas, fontes=fontes)
    caminho = EXTRAS_CIDADES / f"{ibge}.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {"ibge": str(ibge), "pessoas": {pid: dict(d, id=pid) for pid, d in sorted(pessoas.items())}, "atualizado": hoje()}
    if fontes:
        dados["fontes"] = fontes
    dados["votacoes"] = votacoes
    return salvar_json(caminho, sem_mudar_data(dados, caminho))


def salvar(ibge: str, uf: str, casa: dict, membros: list[dict], extras: dict[str, dict], cobertura: dict,
           notas: list[tuple[str, str]] | None = None, escopo: tuple[str, str] | None = None,
           prefeito: tuple[str, dict] | None = None, oficial: bool = True, ids_validos: set[str] | None = None,
           votacoes: dict | None = None) -> dict:
    """casa = {casa, casa_en, sigla, site, fonte}; membros = lista oficial (contrato); extras = {id: dados a mais da pessoa};
    prefeito = (id, dados) com o que a prefeitura mandou à Câmara ("propostas") e as leis e vetos ("executivo");
    votacoes = catálogo das votações nominais (salvar_extras_cidade).
    Grava dados/camaras/<IBGE>.json (a lista oficial) e dados/camaras/extras/<IBGE>.json (um arquivo por cidade).
    oficial=False: a lista da Câmara não passou na conferência; o arquivo da Câmara fica sem "membros" (a página da cidade
    continua com a lista do TSE) e os dados a mais entram só para quem está nela (ids_validos).
    Devolve o resumo para dados/legislativos.json."""
    dados = {"uf": uf, "ibge": ibge, **casa, "cobertura": cobertura}
    if escopo:
        dados["escopoPropostas"], dados["escopoPropostas_en"] = escopo
    dados["membros"] = sorted(membros, key=lambda m: sem_acento(m["nome"]).lower())
    if notas:
        dados["notas"] = [n[0] for n in notas]
        dados["notas_en"] = [n[1] for n in notas]
    if oficial:
        regional.salvar_casa("camara", ibge, dados)
        ids = {m["id"] for m in membros}
    else:
        # sem a lista oficial: o arquivo da Câmara fica só com o que ela publica (cobertura, notas, site), sem "membros"; o
        # montar.py mantém a lista do TSE na página da cidade
        dados["membros"] = []
        regional.salvar_casa("camara", ibge, dados)
        ids = set(ids_validos or ())
    pessoas = {pid: x for pid, x in extras.items() if pid in ids}
    if prefeito and prefeito[1]:
        pessoas[prefeito[0]] = prefeito[1]
    if pessoas:
        usadas = {par[0] for x in pessoas.values() for par in ((x.get("votacoes") or {}).get("votos") or [])}
        votacoes = {k: x for k, x in (votacoes or {}).items() if k in usadas}
        salvar_extras_cidade(ibge, pessoas, fontes=[casa["fonte"]] if casa.get("fonte") else None, votacoes=votacoes or None)
    elif (EXTRAS_CIDADES / f"{ibge}.json").exists():
        (EXTRAS_CIDADES / f"{ibge}.json").unlink()
    # formato antigo (até outubro de 2026): um arquivo por vereador em dados/pessoas/; agora fica tudo no arquivo da cidade
    apagados = regional.limpar_extras(f"ver-{ibge}-", set())
    if apagados:
        log(f"  {apagados} arquivos antigos dados/pessoas/ver-{ibge}-*.json apagados (agora é um arquivo por cidade)")
    locais = {m["id"] for m in membros if oficial and (m.get("foto") or "").startswith("img/pessoas/")}
    for arq in FOTOS.glob(f"ver-{ibge}-*.jpg"):  # fotos de quem saiu
        if arq.stem not in locais:
            arq.unlink()
    nprop = len({p["id"] for pid, x in pessoas.items() if pid.startswith("ver-")
                 for p in ((x.get("propostas") or {}).get("lista") or [])})
    r = {"casa": casa.get("sigla"), "nome": casa.get("casa"), "membros": len(membros) if oficial else 0, "propostas": nprop,
         "cobertura": cobertura, "fonte": casa.get("fonte")}
    if votacoes:
        r["votacoes"] = len(votacoes)
    gastos = sum(1 for pid, x in pessoas.items() if pid.startswith("ver-") and (x.get("gastos") or {}).get("total") is not None)
    if gastos:
        r["vereadoresComGastos"] = gastos
    if prefeito and prefeito[1]:
        x = prefeito[1]
        ex = x.get("executivo") or {}
        r["prefeito"] = {"propostas": len(((x.get("propostas") or {}).get("lista") or [])) if x.get("propostas") else None,
                         "leis": ex.get("leisSancionadas"), "vetos": ex.get("vetos")}
    return r


__all__ = ["INICIO", "PASTA_CACHE", "SEM_PARTIDO", "CAPITAIS", "TOKEN_ROBOTS", "Regras", "robots", "esperar_vez", "pedido_feito", "partido", "nome_limpo", "cidade", "ue_da_cidade", "modelo_foto_tse", "Tse",
           "TXT", "REGRAS", "norm", "situacao", "flags_veto", "nome_norma", "virou", "ESCOPO", "ESCOPO_EN", "foto",
           "baixar_pagina", "so_lista", "salvar", "fonte", "hoje", "log", "slug", "CACHE"]
