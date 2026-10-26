"""Ajudas comuns dos coletores das Assembleias do Nordeste (BA, PE, CE, MA, PB, RN, AL, SE, PI).

- Rede: uma requisição por vez, com pausa entre as que vão ao site oficial, e cache em .cache/<pasta>/.
- partido_sigla: o partido como cada Casa escreve -> a sigla usada no resto do site (a mesma da lista da Câmara).
- casar_membros: liga cada pessoa da lista oficial ao candidato do TSE de 2022 (é ele que dá o id do site).
- gravar: grava dados/assembleias/<UF>.json e dados/pessoas/dest-<UF>-*.json com as ajudas de scripts/regional.py.
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

import regional
from comum import CACHE, STATUS_TXT, UA, baixar, chave_nome, fonte, hoje, log, sem_acento

from . import _carga
from ._carga import SemTempo

INICIO = regional.INICIO_ESTADUAL  # 2023-02-01


def posse_atual(h: str | None = None) -> str:
    """Data da posse da legislatura estadual em curso. Nas 9 Assembleias do Nordeste a Constituição do estado manda a
    Assembleia se reunir "a partir de 1º de fevereiro" do primeiro ano da legislatura para a posse dos deputados (2023,
    2027, 2031...). Antes de 1º/2/2027 a legislatura em curso é a que tomou posse em 2023."""
    h = h or hoje()
    a = int(h[:4])
    while (a - 2023) % 4:
        a -= 1
    if h < f"{a}-02-01":
        a -= 4
    return f"{a}-02-01"


def legislatura_estadual(numero_2023: int, h: str | None = None) -> int:
    """Número da legislatura em curso, sabendo o número da que tomou posse em 2023 (20ª na maioria; 31ª no Ceará)."""
    return numero_2023 + (int(posse_atual(h)[:4]) - 2023) // 4

ESCOPO = ("Projetos apresentados desde 1º/2/2023 (começo da legislatura atual): projetos de lei (PL), de lei complementar "
          "(PLP), de emenda à Constituição do estado (PEC), de decreto legislativo (PDL) e de resolução (PRC). "
          "Requerimentos, indicações, moções e emendas não entram.")
ESCOPO_EN = ("Bills filed since February 1, 2023 (start of the current term): bills (PL), complementary bills (PLP), "
             "amendments to the state Constitution (PEC), legislative decrees (PDL) and resolutions (PRC). Requests, "
             "suggestions to the government, motions and amendments are not included.")

SUPLENTE = ("Suplente em exercício", "Substitute in office")

# canal oficial de pedido de informação (Lei de Acesso à Informação) de cada Assembleia, achado no site oficial de cada uma
# (conferido em 23/10/2026); o montar.py leva para o quadro "Onde ver mais" do perfil
SIC = {
    "BA": "https://atendimento.al.ba.gov.br/e-sic",
    "PE": "https://transparencia.alepe.pe.gov.br/ouvidoria",
    "CE": "https://canalalece.al.ce.gov.br/inicio",
    "MA": "https://sistemas.al.ma.leg.br/ouvidoria/public/index.html",
    "PB": "https://sic.al.pb.leg.br/sact/",
    "RN": "https://transparencia.al.rn.leg.br/ouvidoria",
    "AL": "https://www.al.al.leg.br/ouvidoria",
    "SE": "https://al.se.leg.br/sic-ouvidoria/",
    "PI": "https://www.al.pi.leg.br/servicos/ouvidoria",
}


# ---------------------------------------------------------------- robots.txt e intervalo entre pedidos
# Seção 6 do contrato: o robots.txt de cada site é lido uma vez por rodada (RFC 9309: 4xx = pode ler tudo; 5xx ou sem
# resposta = não lê nada nesta rodada); "Disallow" e "Crawl-delay" valem para o nosso robô (TOKEN_ROBOTS, o mesmo de
# scripts/municipios/_rede.py). O intervalo entre dois pedidos ao mesmo servidor é o maior entre o Crawl-delay e a pausa
# do coletor, e vale também para as novas tentativas. Vale para todos os pedidos dos coletores ale-nordeste (Rede e as
# leituras próprias de ba.py, se.py e _ne_nopaper.py, que chamam vez() e feito()).
TOKEN_ROBOTS = "EntendaPolitica"
MAX_ATRASO = 120  # Crawl-delay maior que isso: o site não é lido
_robots: dict[str, tuple] = {}            # "https://host" -> ("tudo" | "nada" | RobotFileParser, atraso)
_prox: dict[str, float] = {}              # host -> quando pode sair o próximo pedido
_trava = threading.Lock()
_travas_robots: dict[str, threading.Lock] = collections.defaultdict(threading.Lock)
pedidos_por_host: collections.Counter = collections.Counter()


class Bloqueado(RuntimeError):
    """O robots.txt não deixa ler este endereço (ou não respondeu nesta rodada)."""


def _ctx_antigo() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.set_ciphers("DEFAULT@SECLEVEL=1")
    c.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return c


def _ler_robots(base: str) -> tuple:
    corpo, status = b"", None
    for ctx in (None, _ctx_antigo()):  # alguns sites oficiais só falam TLS antigo (ex.: Legisla Bahia)
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA, "Accept": "text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                corpo, status = r.read(500_000), r.status
            break
        except urllib.error.HTTPError as e:
            status = e.code
            break
        except Exception as e:
            if ctx is None and ("SSL" in type(e).__name__ or "SSL" in str(e)):
                continue
            return ("nada", 0.0)
    if status is None or status >= 500:
        return ("nada", 0.0)
    if status >= 400:
        return ("tudo", 0.0)
    if corpo[:2] == b"\x1f\x8b":  # alguns servidores mandam o robots.txt comprimido mesmo sem pedir
        try:
            corpo = gzip.decompress(corpo)
        except Exception:
            return ("tudo", 0.0)
    texto = corpo.decode("utf-8", "replace")
    if "<html" in texto[:3000].lower() or "<!doctype" in texto[:300].lower():
        return ("tudo", 0.0)  # o site devolve uma página no lugar do robots.txt: não há regras
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(texto.splitlines())
    try:
        atraso = float(rp.crawl_delay(TOKEN_ROBOTS) or 0)
    except Exception:
        atraso = 0.0
    if atraso > MAX_ATRASO:
        return ("nada", atraso)
    return (rp, atraso)


def regra_robots(url: str) -> tuple:
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}".lower()
    with _travas_robots[base]:
        if base not in _robots:
            _robots[base] = _ler_robots(base)
            with _trava:  # o intervalo pedido vale também depois de ler o próprio robots.txt
                h = (p.hostname or "").lower()
                _prox[h] = max(_prox.get(h, 0.0), time.time() + _robots[base][1])
                pedidos_por_host[h] += 1
    return _robots[base]


def atraso_pedido(url: str) -> float:
    """O Crawl-delay do site (0 se não houver)."""
    return regra_robots(url)[1]


def vez(url: str, pausa: float = 0.6) -> float:
    """Confere o robots.txt e espera a vez deste pedido ao servidor. Devolve o intervalo a respeitar depois dele. Depois
    do fim da rodada (legislativos.py --minutos; ver _carga.py), nenhum pedido novo começa: SemTempo."""
    regra, atraso = regra_robots(url)
    if regra == "nada":
        raise Bloqueado(f"{url}: o robots.txt do site não respondeu (ou pede mais de {MAX_ATRASO} s entre pedidos); "
                        "nada é lido dele nesta rodada")
    if regra != "tudo" and not regra.can_fetch(TOKEN_ROBOTS, url):
        raise Bloqueado(f"{url}: o robots.txt do site não permite")
    intervalo = max(pausa, atraso)
    h = (urllib.parse.urlsplit(url).hostname or "").lower()
    fim = _carga.fim_rodada()
    while True:
        with _trava:
            agora = time.time()
            prox = _prox.get(h, 0.0)
            if fim is not None and max(agora, prox) >= fim:
                raise SemTempo(f"acabou o tempo desta rodada; {url} fica para a próxima")
            if agora >= prox:
                _prox[h] = agora + intervalo  # reserva a vez; feito() conta o intervalo a partir do fim do pedido
                break
            falta = prox - agora
        time.sleep(min(falta, 5))
    return intervalo


def feito(url: str, intervalo: float) -> None:
    h = (urllib.parse.urlsplit(url).hostname or "").lower()
    with _trava:
        _prox[h] = max(_prox.get(h, 0.0), time.time() + intervalo)
        pedidos_por_host[h] += 1


# ---------------------------------------------------------------- rede
class Rede:
    """Pede uma coisa por vez ao site oficial, respeitando o robots.txt e o intervalo pedido (vez/feito), e guarda tudo
    em .cache/<pasta>/."""

    def __init__(self, pasta: str, pausa: float = 0.6, timeout: int = 60, tentativas: int = 3):
        self.pasta = CACHE / pasta
        self.pausa, self.timeout, self.tentativas = pausa, timeout, tentativas
        self.pedidos = 0  # quantos foram à rede nesta execução

    def _fresco(self, destino: Path | None, max_idade_h: float | None) -> bool:
        if destino is None or not destino.exists() or destino.stat().st_size == 0:
            return False
        return max_idade_h is None or (time.time() - destino.stat().st_mtime) / 3600 < max_idade_h

    def atraso(self, url: str) -> float:
        """O intervalo entre pedidos a este site (o maior entre o Crawl-delay e a pausa do coletor)."""
        return max(self.pausa, atraso_pedido(url))

    def bruto(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, headers: dict | None = None,
              dados: bytes | None = None) -> bytes:
        destino = self.pasta / cache if cache else None
        if self._fresco(destino, max_idade_h):
            return destino.read_bytes()
        erro = None
        for t in range(self.tentativas):  # cada nova tentativa também espera a vez (o Crawl-delay vale para ela)
            iv = vez(url, self.pausa)
            try:
                return baixar(url, destino, max_idade_h=0, tentativas=1, timeout=self.timeout, headers=headers, dados=dados)
            except RuntimeError as e:
                erro = e
                if re.search(r"HTTP Error (400|401|403|404|410)\b", str(e)):
                    break
            finally:
                feito(url, iv)
                self.pedidos += 1
        raise erro

    def json(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, **kw):
        h = {"Accept": "application/json"}
        h.update(kw.pop("headers", None) or {})
        return json.loads(self.bruto(url, cache, max_idade_h, headers=h, **kw).decode("utf-8-sig"))

    def texto(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, codificacao: str = "utf-8", **kw) -> str:
        return self.bruto(url, cache, max_idade_h, **kw).decode(codificacao, "replace")

    def estado(self, nome: str = "estado.json", padrao=None):
        arq = self.pasta / nome
        if arq.exists():
            try:
                return json.loads(arq.read_text(encoding="utf-8"))
            except Exception:
                pass
        return padrao

    def guardar(self, obj, nome: str = "estado.json") -> None:
        arq = self.pasta / nome
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(arq)


def https(url: str | None) -> str | None:
    """Fotos e páginas oficiais em https (o site é https; endereço http seria bloqueado pelo navegador)."""
    if not url:
        return None
    return re.sub(r"^http://", "https://", url.strip())


# ---------------------------------------------------------------- partidos
_PARTIDOS = [
    (r"UNIAO( BRASIL)?|UB", "UNIÃO"), (r"REP|REPUBLICA|REPUBLICANOS|PRB", "REPUBLICANOS"),
    (r"PC ?DO ?B|PARTIDO COMUNISTA DO BRASIL", "PCdoB"), (r"SD|SDD|SOLIDARIEDADE", "SOLIDARIEDADE"),
    (r"PODE|PODEMOS", "PODE"), (r"PP|PROGRESSISTAS?|PARTIDO PROGRESSISTA", "PP"), (r"PL|PARTIDO LIBERAL", "PL"),
    (r"PT|PARTIDO DOS TRABALHADORES", "PT"), (r"P?MDB|(PARTIDO DO )?MOVIMENTO DEMOCRATICO BRASILEIRO", "MDB"),
    (r"PSB|PARTIDO SOCIALISTA BRASILEIRO", "PSB"), (r"PSD|PARTIDO SOCIAL DEMOCRATICO", "PSD"),
    (r"PSDB|PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA", "PSDB"), (r"PDT|PARTIDO DEMOCRATICO TRABALHISTA", "PDT"),
    (r"PV|PARTIDO VERDE", "PV"), (r"PSOL|PARTIDO SOCIALISMO E LIBERDADE", "PSOL"), (r"AVANTE", "AVANTE"),
    (r"CIDADANIA", "CIDADANIA"), (r"REDE( SUSTENTABILIDADE)?", "REDE"), (r"PRD|PARTIDO RENOVACAO DEMOCRATICA", "PRD"),
    (r"AGIR", "AGIR"), (r"NOVO|PARTIDO NOVO", "NOVO"), (r"MOBILIZA", "MOBILIZA"), (r"DC|DEMOCRACIA CRISTA", "DC"),
    (r"PMB|PARTIDO DA MULHER BRASILEIRA", "PMB"), (r"MISSAO|PARTIDO MISSAO", "MISSÃO"),
    (r"S/? ?PARTIDO|SEM PARTIDO", "Sem partido"),
]


def partido_sigla(txt: str | None) -> str | None:
    """'União Brasil', 'UNIAO', 'Progressistas', 'PC do B'... -> a sigla do resto do site ('UNIÃO', 'PP', 'PCdoB')."""
    t = re.sub(r"\s+", " ", sem_acento(txt or "").upper()).strip(" -")
    if not t:
        return None
    for exp, sigla in _PARTIDOS:
        if re.fullmatch(exp, t):
            return sigla
    return (txt or "").strip().upper()


# ---------------------------------------------------------------- TSE
def candidatos(uf: str) -> list[dict]:
    """Candidatos a deputado estadual de 2022 que foram eleitos ou ficaram como suplentes (quem está no cargo hoje só
    pode ter vindo daí)."""
    return [c for c in regional.candidatos_tse(2022, {"DEPUTADO ESTADUAL"}, uf)
            if c["sit"].startswith("ELEITO") or c["sit"] == "SUPLENTE"]


def _parecido(a: str | None, b: str | None) -> bool:
    pa, pb = set(regional.palavras(a)), set(regional.palavras(b))
    return bool(pa and pb) and (len(pa & pb) >= min(2, len(pa), len(pb)))


def casar_membros(uf: str, pessoas: list[dict], manual: dict | None = None) -> tuple[dict, list[str]]:
    """pessoas = [{"chave", "nome", "nomeCivil", "partido"}] da lista oficial; manual = {chave: SQ do TSE ou "-"}
    (conferido à mão). Devolve ({chave: candidato do TSE ou None}, avisos para conferir)."""
    cands = candidatos(uf)
    por_sq = {c["sq"]: c for c in regional.candidatos_tse(2022, {"DEPUTADO ESTADUAL"}, uf)}
    manual = {str(k): v for k, v in (manual or {}).items()}
    out, avisos, usados = {}, [], {}
    for p in pessoas:
        k = str(p["chave"])
        if k in manual:
            sq = manual[k]
            out[k] = por_sq.get(sq) if sq and sq != "-" else None
            if sq and sq != "-" and not out[k]:
                avisos.append(f"{p['nome']}: SQ manual {sq} não está no TSE de 2022 ({uf})")
            continue
        c = regional.casar_tse([p.get("nome"), p.get("nomeCivil")], cands, partido=p.get("partido"))
        # conferência: se a Casa dá o nome completo, ele tem de bater com o nome do candidato no TSE
        if c and p.get("nomeCivil") and not _parecido(p["nomeCivil"], c["nome"]) and not _parecido(p["nomeCivil"], c["urna"]):
            avisos.append(f"{p['nome']} ({p.get('nomeCivil')}): o nome civil não bate com o TSE ({c['nome']}); sem ligação")
            c = None
        if c and c["sq"] in usados:
            avisos.append(f"{p['nome']} e {usados[c['sq']]} caíram no mesmo candidato do TSE ({c['urna']}); sem ligação")
            c = None
        if c:
            usados[c["sq"]] = p["nome"]
        else:
            avisos.append(f"{p['nome']} ({p.get('nomeCivil') or '-'}): sem candidato do TSE de 2022 ligado")
        out[k] = c
    return out, avisos


# ---------------------------------------------------------------- propostas
def com_status_en(p: dict, en: str | None) -> dict:
    if en:
        p["statusTxt_en"] = en
    return p


def nome_lei(tipo: str, numero, ano) -> str:
    """('Lei Complementar', '123', 2024) -> 'Lei Complementar nº 123/2024'."""
    n = str(numero or "").strip()
    if n.isdigit() and len(n) > 3:
        n = f"{int(n):,}".replace(",", ".")
    return f"{tipo} nº {n}/{ano}" if ano else f"{tipo} nº {n}"


def artigo(tipo: str) -> str:
    return "o" if re.match(r"(?i)decreto", tipo) else "a"


def vazio_para_none(v):
    return v if v not in ("", [], {}) else None


# ---------------------------------------------------------------- gravar
def gravar(uf: str, casa: dict, membros: list[dict], extras: dict[str, dict], cobertura: dict, fonte_lista: dict,
           notas: list[tuple[str, str]] | None = None, escopo: str = ESCOPO, escopo_en: str = ESCOPO_EN) -> dict:
    """casa = {"casa", "casa_en", "sigla", "site"}; membros no formato do contrato; extras = {id: dados do perfil};
    notas = [(português, inglês)]. Devolve o resumo que vai para dados/legislativos.json."""
    membros = sorted(membros, key=lambda m: chave_nome(m.get("nome") or ""))
    ids = [m["id"] for m in membros]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{uf}: ids repetidos na lista oficial")
    notas = notas or []
    _suplentes_2022(uf, membros, extras)
    dados = {
        "uf": uf, "ibge": None, "casa": casa["casa"], "casa_en": casa["casa_en"], "sigla": casa["sigla"], "site": casa["site"],
        "sic": casa.get("sic") or SIC.get(uf),
        "fonte": fonte_lista, "cobertura": cobertura, "escopoPropostas": escopo, "escopoPropostas_en": escopo_en,
        "membros": membros, "notas": [n[0] for n in notas], "notas_en": [n[1] for n in notas],
    }
    regional.salvar_casa("assembleia", uf, dados)
    for pid, x in extras.items():
        regional.salvar_extras(pid, x)
    apagados = regional.limpar_extras(f"dest-{uf}-", set(extras))
    total = sum(len(((x.get("propostas") or {}).get("lista") or [])) for x in extras.values())
    if apagados:
        log(f"  {uf}: {apagados} perfis antigos apagados (saíram da lista)")
    return {"casa": casa["sigla"], "membros": len(membros), "propostas": total, "cobertura": cobertura, "fonte": fonte_lista}


def _suplentes_2022(uf: str, membros: list[dict], extras: dict[str, dict]) -> None:
    """Quem está no cargo, mas ficou como suplente na eleição de 2022, não aparece na lista de eleitos do TSE: o perfil
    ganha a situação dele na eleição (TSE) e uma frase dizendo como chegou ao cargo."""
    por_sq = {c["sq"]: c for c in regional.candidatos_tse(2022, {"DEPUTADO ESTADUAL"}, uf)}
    for m in membros:
        c = por_sq.get(m["id"].rsplit("-", 1)[-1])
        x = extras.get(m["id"])
        if not c or x is None or c["sit"] != "SUPLENTE":
            continue
        x.setdefault("eleicao", {"ano": 2022, "cargo": None, "votos": None, "situacao": "Suplente",
                                 "fonte": fonte("TSE", f"Dados Abertos: candidaturas de 2022 ({uf}), situação de cada candidato",
                                                "https://dadosabertos.tse.jus.br/dataset/candidatos-2022")})
        x.setdefault("comoAssumiu", "Ficou como suplente na eleição de 2022 e depois assumiu uma vaga na Assembleia Legislativa")
        x.setdefault("comoAssumiu_en", "Was an alternate in the 2022 election and later took a seat in the Legislative Assembly")


def membro(pid: str, nome: str, nome_civil: str | None, partido: str | None, genero: str | None, foto: str | None,
           url: str | None, suplente: bool = False) -> dict:
    return {"id": pid, "nome": nome, "nomeCivil": nome_civil or None, "partido": partido, "genero": genero if genero in ("F", "M") else None,
            "foto": https(foto), "url": url, "exercicio": SUPLENTE[0] if suplente else None,
            "exercicio_en": SUPLENTE[1] if suplente else None}


def resumo_status(listas: list[list[dict]]) -> dict:
    """Contagem de status de todas as propostas (para conferir as regras de cada Casa)."""
    c: dict[str, int] = {}
    for l in listas:
        for p in l:
            c[p["status"]] = c.get(p["status"], 0) + 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))


__all__ = ["Rede", "SemTempo", "https", "partido_sigla", "candidatos", "casar_membros", "com_status_en", "nome_lei", "artigo",
           "gravar", "membro", "resumo_status", "posse_atual", "legislatura_estadual", "INICIO", "ESCOPO", "ESCOPO_EN",
           "SUPLENTE", "STATUS_TXT", "fonte", "hoje", "log"]
