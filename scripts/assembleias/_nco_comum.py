"""Ajudas comuns dos coletores das Assembleias do Norte e do Centro-Oeste (AM, PA, AC, RO, RR, AP, TO, GO, MT, MS).

- Rede: um pedido por vez a cada site oficial, respeitando o robots.txt (Disallow e Crawl-delay: 60 s nos SAPL do
  Interlegis), com limite de tempo por rodada e cache em .cache/<pasta>/.
- partido_sigla: o partido como cada Casa escreve -> a sigla usada no resto do site (a mesma da lista da Câmara).
- casar_membros: liga cada pessoa da lista oficial ao candidato do TSE de 2022 (é ele que dá o id do site); na dúvida,
  não liga (ligar errado é pior do que não ligar).
- gravar: grava dados/assembleias/<UF>.json e dados/pessoas/dest-<UF>-*.json com as ajudas de scripts/regional.py.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import regional
from comum import CACHE, STATUS_TXT, UA, baixar, chave_nome, fonte, hoje, log, nome_proprio, sem_acento

from . import _carga

INICIO = regional.INICIO_ESTADUAL  # 2023-02-01

ESCOPO = ("Projetos apresentados desde 1º/2/2023 (começo da legislatura atual): projetos de lei (PL), de lei complementar "
          "(PLP), de emenda à Constituição do estado (PEC), de decreto legislativo (PDL) e de resolução (PRC). "
          "Requerimentos, indicações, moções e emendas não entram.")
ESCOPO_EN = ("Bills filed since February 1, 2023 (start of the current term): bills (PL), complementary bills (PLP), "
             "amendments to the state Constitution (PEC), legislative decrees (PDL) and resolutions (PRC). Requests, "
             "suggestions to the government, motions and amendments are not included.")

SUPLENTE = ("Suplente em exercício", "Substitute in office")
OUTROS_TXT = ("Requerimentos, indicações, moções, emendas e outros documentos (não são projetos)",
              "requests, suggestions to the government, motions, amendments and other documents (these are not bills)")


# ---------------------------------------------------------------- rede
TOKEN_ROBOTS = "entendapolitica"  # o nome do nosso robô no robots.txt (o User-Agent é comum.UA)
# tempo máximo de rede de uma Casa numa rodada, em minutos (variável de ambiente NCO_MINUTOS); o que não der fica para a
# rodada seguinte: o cache guarda o que já foi lido e cada coletor continua de onde parou. Vale também o fim da rodada
# inteira (legislativos.py --minutos; ver _carga.py): o que acabar primeiro.
PRAZO_MIN = float(os.environ.get("NCO_MINUTOS") or 25)

SemTempo = _carga.SemTempo  # o limite de tempo da rodada acabou: o que faltou fica para a próxima rodada


class RobotsFechado(RuntimeError):
    """O robots.txt do site não respondeu (erro 5xx ou sem resposta): nessa rodada o site não é lido (RFC 9309)."""


class Robots:
    """robots.txt (RFC 9309): o grupo do nosso robô ou, se não houver, o de "*"; Allow/Disallow com * e $ (vale a regra
    mais longa; no empate, Allow) e Crawl-delay."""

    def __init__(self, texto: str | None):
        grupos: list[tuple[list[str], list[tuple[str, str]]]] = []
        agentes: list[str] = []
        linhas: list[tuple[str, str]] = []
        ultimo_ua = False
        for bruta in (texto or "").splitlines():
            linha = bruta.split("#", 1)[0].strip()
            if ":" not in linha:
                continue
            k, v = (x.strip() for x in linha.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if not ultimo_ua and (agentes or linhas):
                    grupos.append((agentes, linhas))
                    agentes, linhas = [], []
                agentes.append(v.lower())
                ultimo_ua = True
            else:
                ultimo_ua = False
                linhas.append((k, v))
        if agentes or linhas:
            grupos.append((agentes, linhas))
        nossos = [g for g in grupos if TOKEN_ROBOTS in g[0]] or [g for g in grupos if "*" in g[0]]
        self.regras: list[tuple[int, bool, re.Pattern]] = []
        self.atraso = 0.0
        for _, ls in nossos:
            for k, v in ls:
                if k in ("allow", "disallow") and v:
                    exp = re.escape(v).replace(r"\*", ".*")
                    exp = exp[:-2] + "$" if exp.endswith(r"\$") else exp
                    self.regras.append((len(v), k == "allow", re.compile(exp)))
                elif k == "crawl-delay" and not self.atraso:
                    try:
                        self.atraso = float(v)
                    except ValueError:
                        pass

    def pode(self, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        caminho = (p.path or "/") + (f"?{p.query}" if p.query else "")
        if caminho == "/robots.txt":
            return True
        achadas = [(n, permite) for n, permite, exp in self.regras if exp.match(caminho)]
        return max(achadas)[1] if achadas else True


class Rede:
    """Pede uma coisa por vez a cada site oficial e guarda em .cache/<pasta>/. Antes do primeiro pedido a um site, lê o
    robots.txt dele (uma vez por rodada): respeita os Disallow e o Crawl-delay (o intervalo entre dois pedidos ao mesmo
    servidor é o maior entre o Crawl-delay e a pausa da Casa; nos SAPL do Interlegis, 60 s). Para quando acaba o tempo da
    rodada (SemTempo). Tentativas de novo (erro de rede, 404 passageiro do SAPL) também esperam o intervalo."""

    def __init__(self, pasta: str, pausa: float = 1.0, timeout: int = 60, tentativas: int = 3, headers: dict | None = None,
                 minutos: float | None = None):
        self.pasta = CACHE / pasta
        self.pausa, self.timeout, self.tentativas = pausa, timeout, tentativas
        self.headers = headers or {}
        self._ult: dict[str, float] = {}
        self._robots: dict[str, Robots] = {}
        self.inicio = time.time()
        self.prazo = self.inicio + 60 * (PRAZO_MIN if minutos is None else minutos)
        fim = _carga.fim_rodada()  # o fim da rodada inteira (legislativos.py --minutos) também vale
        if fim is not None:
            self.prazo = min(self.prazo, fim)
        self.pedidos = 0  # quantos foram à rede nesta execução (com os robots.txt)
        self.por_host: dict[str, int] = {}

    @staticmethod
    def _host(url: str) -> str:
        return urllib.parse.urlsplit(url).netloc.lower()

    def robots(self, url: str) -> Robots:
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}".lower()
        if base not in self._robots:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            texto = ""
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    texto = r.read(500_000).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code >= 500:
                    raise RobotsFechado(f"robots.txt de {p.netloc}: erro {e.code}; o site não é lido nesta rodada")
                # 4xx: não há robots.txt; pode ler (RFC 9309)
            except (urllib.error.URLError, OSError) as e:
                raise RobotsFechado(f"robots.txt de {p.netloc} sem resposta ({e}); o site não é lido nesta rodada")
            finally:
                self.feito(base + "/robots.txt")
            self._robots[base] = Robots(texto)
        return self._robots[base]

    def intervalo(self, url: str) -> float:
        return max(self.pausa, self.robots(url).atraso)

    def esperar(self, url: str) -> None:
        """Antes de um pedido: robots.txt (Disallow), intervalo desde o último pedido ao mesmo servidor e limite de tempo."""
        r = self.robots(url)
        if not r.pode(url):
            raise RuntimeError(f"o robots.txt de {self._host(url)} não permite ler {url}")
        espera = max(0.0, max(self.pausa, r.atraso) - (time.time() - self._ult.get(self._host(url), 0)))
        if time.time() + espera > self.prazo:
            raise SemTempo(f"acabou o tempo desta rodada ({self.pedidos} pedidos)")
        if espera:
            time.sleep(espera)

    def feito(self, url: str) -> None:
        h = self._host(url)
        self._ult[h] = time.time()
        self.pedidos += 1
        self.por_host[h] = self.por_host.get(h, 0) + 1

    def tem_tempo(self, pedidos: int = 1, url: str | None = None) -> bool:
        """Dá para fazer mais 'pedidos' pedidos (a este servidor) antes do fim do tempo da rodada?"""
        passo = self.intervalo(url) if url else self.pausa
        return time.time() + pedidos * passo <= self.prazo

    def _fresco(self, destino: Path | None, max_idade_h: float | None) -> bool:
        if destino is None or not destino.exists() or destino.stat().st_size == 0:
            return False
        return max_idade_h is None or (time.time() - destino.stat().st_mtime) / 3600 < max_idade_h

    def bruto(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, headers: dict | None = None,
              dados: bytes | None = None) -> bytes:
        destino = self.pasta / cache if cache else None
        if self._fresco(destino, max_idade_h):
            return destino.read_bytes()
        h = {"User-Agent": UA}
        h.update(self.headers)
        h.update(headers or {})
        for tentativa in range(self.tentativas):
            self.esperar(url)
            try:
                return baixar(url, destino, max_idade_h=0, tentativas=1, timeout=self.timeout, headers=h, dados=dados)
            except RuntimeError as e:
                # erro de rede, 5xx e o 404 passageiro do SAPL ganham nova chance (depois do intervalo); 400/401/403/410 não
                if tentativa == self.tentativas - 1 or re.search(r"HTTP Error (400|401|403|410)\b", str(e)):
                    raise
            finally:
                self.feito(url)
        raise RuntimeError(f"Falha ao baixar {url}")

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


def texto_html(s: str | None) -> str:
    """Tira as etiquetas HTML e junta os espaços."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def limpa_nome(nome: str | None) -> str:
    """'DEPUTADA ÂNGELA GARROTE' -> 'Ângela Garrote' (o título "Deputado(a)" já aparece no cargo)."""
    n = re.sub(r"^\s*(deputad[oa]|dep\.)\s+", "", (nome or "").strip(), flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    if n and (_quase_maiusculo(n) or any(p.isupper() for p in re.findall(r"[^\W\d_]{4,}", n))):  # "Dra. TAÍSSA" também
        n = nome_proprio(n)
    return re.sub(r"\b(Dr|Dra|Prof|Profa|Pr|Sgt|Cel|Cap|Ten|Cb|Sd)\b(?!\.)", r"\1.", n)  # "Dr Fulano" -> "Dr. Fulano"


def _quase_maiusculo(s: str) -> bool:
    letras = [c for c in s if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.6


def limpa_civil(civil: str | None) -> str | None:
    c = re.sub(r"\s+", " ", (civil or "").strip())
    if not c:
        return None
    return nome_proprio(c) if _quase_maiusculo(c) else c  # "JOSÉ DA SILVA" e também "aDAILTON FLORENTINO" (caps lock)


def nome_civil(civil: str | None, nome: str, cand: dict | None) -> str | None:
    """Nome completo: o da Casa; se a Casa não dá ou só repete o nome usado no cargo, o do TSE (candidatura de 2022)."""
    c = limpa_civil(civil)
    if cand and (not c or chave_nome(c) == chave_nome(nome)):
        return limpa_civil(cand["nome"])
    return c


# ---------------------------------------------------------------- partidos
_PARTIDOS = [
    (r"UNIAO( BRASIL)?|UB|UNIAO BRASIL \(UNIAO\)", "UNIÃO"), (r"REP|REPUBLICANOS|PRB", "REPUBLICANOS"),
    (r"PC ?DO ?B|PCDOB|PARTIDO COMUNISTA DO BRASIL", "PCdoB"), (r"SD|SDD|SOLIDARIEDADE", "SOLIDARIEDADE"),
    (r"PODE|PODEMOS", "PODE"), (r"PP|PROGRESSISTAS?|PARTIDO PROGRESSISTA", "PP"), (r"PL|PARTIDO LIBERAL", "PL"),
    (r"PT|PARTIDO DOS TRABALHADORES", "PT"), (r"P?MDB|(PARTIDO DO )?MOVIMENTO DEMOCRATICO BRASILEIRO", "MDB"),
    (r"PSB|PARTIDO SOCIALISTA BRASILEIRO", "PSB"), (r"PSD|PARTIDO SOCIAL DEMOCRATICO", "PSD"),
    (r"PSDB|PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA", "PSDB"), (r"PDT|PARTIDO DEMOCRATICO TRABALHISTA", "PDT"),
    (r"PV|PARTIDO VERDE", "PV"), (r"PSOL|PARTIDO SOCIALISMO E LIBERDADE", "PSOL"), (r"AVANTE", "AVANTE"),
    (r"CIDADANIA", "CIDADANIA"), (r"REDE( SUSTENTABILIDADE)?", "REDE"), (r"PRD|PARTIDO RENOVACAO DEMOCRATICA", "PRD"),
    (r"AGIR", "AGIR"), (r"NOVO|PARTIDO NOVO", "NOVO"), (r"MOBILIZA|PMN", "MOBILIZA"), (r"DC|DEMOCRACIA CRISTA", "DC"),
    (r"PMB|PARTIDO DA MULHER BRASILEIRA", "PMB"), (r"MISSAO|PARTIDO MISSAO", "MISSÃO"), (r"PRTB", "PRTB"),
    (r"S/? ?PARTIDO|SEM PARTIDO|NAO POSSUI FILIACAO", "Sem partido"),
]


def partido_sigla(txt: str | None) -> str | None:
    """'União Brasil', 'UB', 'Progressistas', 'PC do B'... -> a sigla do resto do site ('UNIÃO', 'PP', 'PCdoB')."""
    t = re.sub(r"\s+", " ", sem_acento(txt or "").upper()).strip(" -")
    if not t:
        return None
    for exp, sigla in _PARTIDOS:
        if re.fullmatch(exp, t):
            return sigla
    return (txt or "").strip().upper()


# ---------------------------------------------------------------- TSE
def ano_eleicao(posse: str = "02-01") -> int:
    """A eleição que escolheu a legislatura de hoje (2022 até a posse de 2027; depois, 2026)."""
    return int(legislatura_por_data(posse)["inicio"][:4]) - 1


def candidatos(uf: str, ano: int | None = None) -> list[dict]:
    """Candidatos a deputado estadual que foram eleitos ou ficaram como suplentes na eleição da legislatura de hoje (quem
    está no cargo só pode ter vindo daí)."""
    return [c for c in regional.candidatos_tse(ano or ano_eleicao(), {"DEPUTADO ESTADUAL"}, uf)
            if c["sit"].startswith("ELEITO") or c["sit"] == "SUPLENTE"]


def _variantes(nomes: list[str | None]) -> list[str]:
    """Os nomes da lista oficial e, quando têm apóstrofo, também sem ele: o TSE escreve "DANGELO" e a Casa, "D’Angelo"."""
    out = [n for n in nomes if n]
    out += [re.sub(r"['’`´]", "", n) for n in out if re.search(r"['’`´]", n)]
    return out


def _parecido(a: str | None, b: str | None) -> bool:
    pa, pb = set(regional.palavras(a)), set(regional.palavras(b))
    if not (pa and pb):
        return False
    if len(pa & pb) >= min(2, len(pa), len(pb)):
        return True
    pa, pb = set(regional.palavras(re.sub(r"['’`´]", "", a or ""))), set(regional.palavras(re.sub(r"['’`´]", "", b or "")))
    return len(pa & pb) >= min(2, len(pa), len(pb))


def casar_membros(uf: str, pessoas: list[dict], manual: dict | None = None, posse: str = "02-01") -> tuple[dict, list[str]]:
    """pessoas = [{"chave", "nome", "nomeCivil", "partido"}] da lista oficial; manual = {chave ou nome: SQ do TSE ou "-"}
    (conferido à mão, vale para a eleição de 2022). Devolve ({chave: candidato do TSE ou None}, avisos para conferir)."""
    ano = ano_eleicao(posse)
    cands = candidatos(uf, ano)
    por_sq = {c["sq"]: c for c in regional.candidatos_tse(ano, {"DEPUTADO ESTADUAL"}, uf)}
    manual = {chave_nome(str(k)): v for k, v in (manual or {}).items()} if ano == 2022 else {}
    out, avisos, usados = {}, [], {}
    for p in pessoas:
        k = str(p["chave"])
        sq = manual.get(chave_nome(k), manual.get(chave_nome(p.get("nome") or "")))
        if sq is not None:
            out[k] = por_sq.get(sq) if sq and sq != "-" else None
            if sq and sq != "-" and not out[k]:
                avisos.append(f"{p['nome']}: SQ manual {sq} não está no TSE de 2022 ({uf})")
            if out[k]:
                usados[out[k]["sq"]] = p["nome"]
            continue
        c = regional.casar_tse(_variantes([p.get("nome"), p.get("nomeCivil")]), cands, partido=p.get("partido"))
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
_NORMAS = [
    (r"lei complementar", "Lei Complementar"), (r"^lei( ordinaria)?( promulgada)?( estadual)?$", "Lei"),
    (r"emenda (a )?constitucional|emenda a constituicao", "Emenda Constitucional"),
    (r"decreto legislativo", "Decreto Legislativo"), (r"^resolu[cç][aã]o", "Resolução"),
]


def nome_norma(descricao: str | None) -> str | None:
    """Descrição oficial do tipo de norma -> nome usado no site (None: não conta como "virou lei", ex.: autógrafo)."""
    d = sem_acento((descricao or "").lower()).strip()
    for exp, nome in _NORMAS:
        if re.search(exp, d):
            return nome
    return None


def nome_lei(tipo: str, numero, ano) -> str:
    """('Lei Complementar', '123', 2024) -> 'Lei Complementar nº 123/2024'."""
    n = str(numero or "").strip()
    if n.isdigit() and len(n) > 3:
        n = f"{int(n):,}".replace(",", ".")
    return f"{tipo} nº {n}/{ano}" if ano else f"{tipo} nº {n}"


def artigo(tipo: str) -> str:
    return "o" if re.match(r"(?i)decreto", tipo) else "a"


def com_status_en(p: dict, en: str | None) -> dict:
    if en:
        p["statusTxt_en"] = en
    return p


_SIGLAS_VOT = [(r"(proposta|projeto) de emenda (a )?constitu", "PEC"), (r"projeto de lei complementar", "PLC"),
               (r"projeto de lei", "PL"), (r"projeto de decreto legislativo", "PDL"), (r"projeto de resolucao", "PR"),
               (r"processo", "Proc.")]


def sigla_votacao(texto: str | None) -> str | None:
    """Nome curto do que foi votado, sem palavras em português (a página em inglês mostra este campo sem marcação):
    'PROJETO DE LEI COMPLEMENTAR nº 9/2026' -> 'PLC 9/2026'; 'PROCESSO 16243/2026 - 1ª DV' -> 'Proc. 16243/2026'.
    Votação em bloco, emenda ou texto sem número -> None (o texto oficial completo vai na descrição)."""
    t = sem_acento(texto or "").lower().strip()
    num = re.search(r"(\d+)\s*/\s*(\d{4})", t)
    if not num or t.startswith("emenda") or "bloco" in t:
        return None
    for exp, sig in _SIGLAS_VOT:
        if re.match(exp, t):
            return f"{sig} {int(num.group(1))}/{num.group(2)}"
    return None


def resumo_status(listas: list[list[dict]]) -> dict:
    """Contagem de status de todas as propostas (para conferir as regras de cada Casa)."""
    c: dict[str, int] = {}
    for l in listas:
        for p in l:
            c[p["status"]] = c.get(p["status"], 0) + 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))


def classificar(texto: str | None, regras: list[tuple]) -> tuple[str, str | None, str | None]:
    """Texto oficial da situação -> (status, frase pt ou None, frase en ou None). regras = [(expressão sem acento em
    minúsculas, status, frase pt ou None, frase en ou None)] da Casa; depois, a tabela comum."""
    t = sem_acento((texto or "").lower()).strip()
    for r in regras:
        exp, st = r[0], r[1]
        if re.search(exp, t):
            return st, (r[2] if len(r) > 2 else None), (r[3] if len(r) > 3 else None)
    return regional.situacao_para_status(texto), None, None


# ---------------------------------------------------------------- legislatura e troca de mandatos
def legislatura_por_data(posse: str = "02-01") -> dict:
    """A legislatura de hoje pelo calendário: começa na posse (1º de fevereiro; em Roraima, 1º de janeiro) do ano seguinte
    à eleição (2023, 2027, 2031...) e dura 4 anos."""
    h = hoje()
    ano = 2023 + 4 * ((int(h[:4]) - 2023) // 4)
    if h < f"{ano}-{posse}":
        ano -= 4
    fim = (dt.date.fromisoformat(f"{ano + 4}-{posse}") - dt.timedelta(days=1)).isoformat()
    return {"inicio": f"{ano}-{posse}", "fim": fim}


def conferir_virada(rede: "Rede", uf: str, chaves: list[str], leg: dict) -> None:
    """Para listas tiradas do site da Casa (sem legislatura cadastrada): depois da posse da legislatura nova, só aceita a
    lista quando ela mudou em relação à da legislatura anterior (senão a Casa ainda não atualizou o site, e mostrar a
    lista velha como "quem está no cargo hoje" seria errado). Lança a exceção: o legislativos.py mantém o arquivo de antes."""
    arq = "lista-da-legislatura.json"
    d = rede.estado(arq, {}) or {}
    atual = sorted(set(chaves))
    if d.get("inicio") and d["inicio"] < leg["inicio"] and sorted(d.get("chaves") or []) == atual:
        raise RuntimeError(f"{uf}: a legislatura nova começou em {leg['inicio']}, mas a lista oficial do site ainda é a da anterior")
    if d.get("inicio") != leg["inicio"] or d.get("chaves") != atual:
        rede.guardar({"inicio": leg["inicio"], "chaves": atual}, arq)


# ---------------------------------------------------------------- gravar
def membro(pid: str, nome: str, nome_civil: str | None, partido: str | None, genero: str | None, foto: str | None,
           url: str | None, suplente: bool = False) -> dict:
    return {"id": pid, "nome": nome, "nomeCivil": nome_civil or None, "partido": partido,
            "genero": genero if genero in ("F", "M") else None, "foto": https(foto), "url": url,
            "exercicio": SUPLENTE[0] if suplente else None, "exercicio_en": SUPLENTE[1] if suplente else None}


def gravar(uf: str, casa: dict, membros: list[dict], extras: dict[str, dict], cobertura: dict, fonte_lista: dict,
           notas: list[tuple[str, str]] | None = None, escopo: str = ESCOPO, escopo_en: str = ESCOPO_EN,
           minimo: int = 1, legislatura: dict | None = None) -> dict:
    """casa = {"casa", "casa_en", "sigla", "site", "sic" (canal oficial de pedido de informação, Lei de Acesso à
    Informação, se houver)}; membros no formato do contrato; extras = {id: dados do perfil}; notas = [(português,
    inglês)]; legislatura = {"numero", "inicio", "fim"} (vai no arquivo, para a troca de mandatos).
    Devolve o resumo que vai para dados/legislativos.json."""
    if len(membros) < minimo:
        raise RuntimeError(f"{uf}: só {len(membros)} pessoas na lista oficial (esperado pelo menos {minimo}); nada gravado")
    membros = sorted(membros, key=lambda m: chave_nome(m.get("nome") or ""))
    ids = [m["id"] for m in membros]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{uf}: ids repetidos na lista oficial")
    notas = notas or []
    dados = {
        "uf": uf, "ibge": None, "casa": casa["casa"], "casa_en": casa["casa_en"], "sigla": casa["sigla"], "site": casa["site"],
        "sic": casa.get("sic"),
        "fonte": fonte_lista, "cobertura": cobertura, "escopoPropostas": escopo if cobertura.get("propostas") else None,
        "escopoPropostas_en": escopo_en if cobertura.get("propostas") else None, "legislatura": legislatura,
        "membros": membros, "notas": [n[0] for n in notas], "notas_en": [n[1] for n in notas],
    }
    regional.salvar_casa("assembleia", uf, dados)
    for pid, x in extras.items():
        regional.salvar_extras(pid, x)
    apagados = regional.limpar_extras(f"dest-{uf}-", set(extras))
    total = sum(len(((x.get("propostas") or {}).get("lista") or [])) for x in extras.values())
    if apagados:
        log(f"  {uf}: {apagados} perfis antigos apagados (saíram da lista)")
    r = {"casa": casa["sigla"], "membros": len(membros), "propostas": total, "cobertura": cobertura, "fonte": fonte_lista}
    if legislatura:
        r["legislatura"] = legislatura
    return r


__all__ = ["Rede", "Robots", "SemTempo", "RobotsFechado", "PRAZO_MIN", "https", "texto_html", "limpa_nome", "limpa_civil",
           "nome_civil", "partido_sigla", "candidatos", "casar_membros",
           "nome_norma", "nome_lei", "artigo", "com_status_en", "resumo_status", "classificar", "membro", "gravar",
           "legislatura_por_data", "conferir_virada", "sigla_votacao",
           "INICIO", "ESCOPO", "ESCOPO_EN", "SUPLENTE", "OUTROS_TXT", "STATUS_TXT", "fonte", "hoje", "log"]
