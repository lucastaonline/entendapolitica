"""Ajudas das capitais que publicam as propostas só em páginas do site da Câmara (Rio de Janeiro, Belo Horizonte, Porto
Alegre; frente "capitais-b-r6", 27/10/2026). Por cima de scripts/camaras/_base.py, sem mudar nada dele:

- Rede: um pedido por vez a cada servidor, com o robots.txt (Disallow e Crawl-delay) e a pausa do coletor (o maior dos
  dois), o User-Agent do projeto, novas tentativas só para erro de rede ou 5xx, contagem de pedidos e de bytes, e o fim da
  rodada (LEGISLATIVOS_PRAZO, de scripts/legislativos.py --minutos): perto do fim, lança SemTempo e o resto fica para a
  próxima rodada;
- estado da carga em .cache/camaras/<IBGE>/<nome>.json (o que já foi lido, já interpretado: nada de guardar páginas
  inteiras), gravado aos poucos, para uma carga longa continuar de onde parou;
- lista(): a lista oficial de quem está no cargo, do mesmo jeito que _base.so_lista (conferência do tamanho, ligação com o
  TSE, foto, suplentes em exercício), mas sem gravar: o coletor junta as propostas, os gastos e as votações e grava com
  _base.salvar;
- Nomes: liga o nome de um autor, como o sistema da Câmara escreve ("VEREADOR DR. ROGERIO AMORIM", "Ver.(a) Neném da
  Farmácia", "JESSE SANGALLI"), à pessoa da lista oficial (nome no cargo ou nome civil), só quando não há dúvida;
- proposta(), escopo_prefeito(), inicio_prefeito(): cada proposta e o escopo do bloco do prefeito no formato de sempre
  (regional.proposta / regional.bloco_propostas, como nas Câmaras com SAPL).

Primeira carga: enquanto a leitura das propostas não termina (no robô do GitHub, que começa com o cache vazio, ou num site
lento), o coletor não grava nada (devolve "pendente" e a etapa): ficam publicados os arquivos de antes, inteiros.
"""
from __future__ import annotations

import gzip
import os
import re
import time
import urllib.error
import urllib.request

import regional
from comum import UA, hoje, ler_json, log, salvar_json, sem_acento

from . import _base as B


class SemTempo(Exception):
    """Acabou o tempo da rodada (ou o orçamento de pedidos): o que foi lido fica guardado e o resto fica para a próxima."""


def prazo() -> float | None:
    """Fim do tempo desta rodada (scripts/legislativos.py --minutos), em segundos desde 1970."""
    try:
        return float(os.environ.get("LEGISLATIVOS_PRAZO") or 0) or None
    except ValueError:
        return None


class Rede:
    """Pedidos educados a um site oficial (contrato, seção 6)."""

    def __init__(self, ibge: str, pausa: float = 1.0, ua: str | None = None, contexto=None, margem: float = 90,
                 orcamento: int | None = None):
        self.ibge, self.pausa, self.ua, self.ctx, self.margem = ibge, pausa, ua or UA, contexto, margem
        self.orcamento = orcamento
        self.n = self.bytes = 0
        self.pasta = B.PASTA_CACHE / ibge

    def checar_tempo(self) -> None:
        p = prazo()
        if p and time.time() > p - self.margem:
            raise SemTempo("fim do tempo da rodada")
        if self.orcamento is not None and self.n >= self.orcamento:
            raise SemTempo(f"orçamento de {self.orcamento} pedidos")

    def pedir(self, url: str, dados: bytes | None = None, cabecalhos: dict | None = None, tentativas: int = 3,
              timeout: int = 120) -> bytes:
        """Um pedido (com o robots.txt e o intervalo do servidor). Erro de rede ou 5xx: tenta de novo depois de uma pausa;
        4xx: para logo (RuntimeError). O coletor deixa a exceção subir: o legislativos.py mantém os arquivos de antes."""
        self.checar_tempo()
        erro = None
        for t in range(tentativas):
            B.esperar_vez(url, self.pausa, self.ua, self.ctx)
            try:
                h = {"User-Agent": self.ua, "Accept-Encoding": "gzip"}
                h.update(cabecalhos or {})
                req = urllib.request.Request(url, data=dados, headers=h)
                with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as r:
                    b = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        b = gzip.decompress(b)
                self.n += 1
                self.bytes += len(b)
                return b
            except urllib.error.HTTPError as e:
                erro = f"HTTP {e.code}"
                if e.code < 500 or e.code == 503 and t:
                    break
            except Exception as e:  # rede instável, tempo esgotado
                erro = f"{type(e).__name__}: {e}"
            finally:
                B.pedido_feito(url)
            time.sleep(min(30, 5 * (t + 1)))
        raise RuntimeError(f"{url[:160]}: {erro}")

    def guardado(self, url: str, nome: str, idade_h: float | None, **kw) -> bytes:
        """O pedido guardado em .cache/camaras/<IBGE>/http/<nome> (de novo só depois de idade_h horas; None = para sempre)."""
        arq = self.pasta / "http" / nome
        if arq.exists() and arq.stat().st_size and (idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < idade_h):
            return arq.read_bytes()
        b = self.pedir(url, **kw)
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(arq.suffix + ".part")
        tmp.write_bytes(b)
        os.replace(tmp, arq)
        return b

    def resumo(self, t0: float) -> str:
        return f"{self.n} pedidos, {self.bytes / 1e6:.1f} MB, {time.time() - t0:.0f} s"


# ---------------------------------------------------------------- estado da carga
def ler_estado(ibge: str, nome: str = "propostas") -> dict:
    return ler_json(B.PASTA_CACHE / ibge / f"{nome}.json", {}) or {}


def guardar_estado(ibge: str, e: dict, nome: str = "propostas") -> None:
    salvar_json(B.PASTA_CACHE / ibge / f"{nome}.json", e)


def dias_desde(data: str | None, h: str | None = None) -> float:
    """Dias entre uma data ISO (AAAA-MM-DD) e hoje; sem data = muito tempo."""
    import datetime as dt
    if not data:
        return 1e9
    try:
        return (dt.date.fromisoformat((h or hoje())[:10]) - dt.date.fromisoformat(data[:10])).days
    except ValueError:
        return 1e9


def data_br(d: str | None) -> str | None:
    """'16/12/2025' -> '2025-12-16'; 'MM/DD/YYYY' não (cada sistema diz o formato)."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", d or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


# ---------------------------------------------------------------- lista oficial (como _base.so_lista, sem gravar)
def lista(ibge: str, uf: str, casa: dict, pessoas: list[dict], vagas: int, tse_manual: dict | None = None,
          minimo: float = 0.8) -> tuple[list[dict], dict[str, dict], dict[str, str], "B.Tse"]:
    """(membros, extras {id: links, fontes, foto}, {chave oficial: id}, Tse) — a mesma montagem de _base.so_lista."""
    if not (vagas * minimo <= len(pessoas) <= vagas + 3):
        raise RuntimeError(f"a lista oficial tem {len(pessoas)} pessoas para {vagas} vagas: a página deve ter mudado")
    tse = B.Tse(ibge, uf, tse_manual)
    membros, extras, por_chave = [], {}, {}
    for p in pessoas:
        nome = B.nome_limpo(p["nome"])
        civil = B.nome_limpo(p.get("nomeCivil")) if p.get("nomeCivil") else None
        sigla = B.partido(p.get("partido"))
        pid, cand = tse.casar(p["chave"], [nome, civil], sigla)
        supl = (cand or {}).get("sit") == "SUPLENTE"
        if not civil and cand and cand.get("nome"):
            civil = B.nome_limpo(cand["nome"])
        if civil and re.sub(r"\W", "", sem_acento(civil).lower()) == re.sub(r"\W", "", sem_acento(nome).lower()):
            civil = None
        g = p.get("genero") or (cand or {}).get("genero")
        m = {"id": pid, "nome": nome, "nomeCivil": civil, "partido": sigla, "genero": g if g in ("F", "M") else None,
             "foto": B.foto(p.get("foto"), pid, ibge), "url": p.get("url"),
             "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None}
        membros.append(m)
        x = {"links": {"oficial": p.get("url"), "email": p.get("email"), "redes": []}, "fontes": [casa["fonte"]]}
        if m["foto"]:
            x["fotoCredito"] = casa["casa"]
        extras[pid] = x
        por_chave[p["chave"]] = pid
        if cand:
            m["_urna"] = cand.get("urna")
    ids = [m["id"] for m in membros]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"duas pessoas com o mesmo id: {sorted(i for i in ids if ids.count(i) > 1)}")
    if tse.sem_ligacao:
        log(f"  {casa.get('sigla')}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
    return membros, extras, por_chave, tse


def limpar_membros(membros: list[dict]) -> None:
    for m in membros:
        m.pop("_urna", None)


# ---------------------------------------------------------------- nomes dos autores
# títulos antes do nome: "Vereador", "Vereadora", "Ver.", "Ver.(a)", "Ver.ª", "Verª.", "VER " (sem ponto), "Vre." (erro de
# digitação visto em Porto Alegre) e "Conselheiro(a)" (de nome de urna). "Vera ..." não é título.
_TITULOS = re.compile(r"^(?:vereador(?:a|es|as)?|vereador\(a\)|ver\.?\s*\(a\)\.?|ver\.?\s*[ªº]\.?|vers?\.|ver|vre\.|"
                      r"conselheir[oa])\s+", re.I)


def sem_titulo(n: str | None) -> str:
    """'Ver.ª Atena Roveda' -> 'Atena Roveda'; 'VEREADOR DR. ROGERIO AMORIM' -> 'DR. ROGERIO AMORIM'."""
    t = re.sub(r"\s+", " ", (n or "").strip())
    for _ in range(2):
        t = _TITULOS.sub("", t).strip()
    return t


def chave_nome(n: str | None) -> str:
    """'VEREADOR DR. ROGERIO AMORIM' -> 'dr rogerio amorim'; 'Ver.(a) Neném da Farmácia' -> 'nenem da farmacia'."""
    t = sem_acento(sem_titulo(n).lower()).replace("º", "").replace("ª", "")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class Nomes:
    """Liga o nome de um autor (como a Câmara escreve) à pessoa da lista oficial: pelo nome no cargo, pelo nome de urna e
    pelo nome civil; primeiro igual (sem acento, sem "Vereador"), depois pelas palavras (regional.palavras: sem títulos como
    "Dr.", "Pastor"), depois pelas palavras do autor contidas no nome de uma pessoa só (com duas palavras ou mais: "TANISE
    PAZZIM" = Tanise Amália Pazzim; "Giovani e Coletivo" = Giovani Culau e Coletivo), e só quando uma pessoa só bate.
    manual = {nome do sistema: id ou None} para os conferidos à mão (None = não é ninguém da lista de hoje)."""

    def __init__(self, membros: list[dict], manual: dict[str, str | None] | None = None):
        self.exato: dict[str, set] = {}
        self.palavras: dict[str, set] = {}
        self.conjuntos: list[tuple[str, set]] = []
        for m in membros:
            for n in (m.get("nome"), m.get("nomeCivil"), m.get("_urna")):
                if not n:
                    continue
                self.exato.setdefault(chave_nome(n), set()).add(m["id"])
                ps = set(regional.palavras(sem_titulo(n)))
                if ps:
                    self.palavras.setdefault(" ".join(sorted(ps)), set()).add(m["id"])
                    self.conjuntos.append((m["id"], ps))
        self.manual = {chave_nome(k): v for k, v in (manual or {}).items()}
        self.sem: dict[str, int] = {}

    def id(self, nome: str | None) -> str | None:
        k = chave_nome(nome)
        if not k:
            return None
        if k in self.manual:
            return self.manual[k]
        ids = self.exato.get(k)
        if ids and len(ids) == 1:
            return next(iter(ids))
        ps = set(regional.palavras(sem_titulo(nome)))
        ids = self.palavras.get(" ".join(sorted(ps)))
        if ids and len(ids) == 1:
            return next(iter(ids))
        if len(ps) >= 2:
            ids = {i for i, cj in self.conjuntos if ps <= cj}
            if len(ids) == 1:
                return next(iter(ids))
        self.sem[nome.strip()] = self.sem.get(nome.strip(), 0) + 1
        return None


# ---------------------------------------------------------------- blocos de propostas
def proposta(pid: str, sigla: str, tipo: str, data: str | None, ementa: str | None, situacao: str | None, url: str,
             papel: str, st: tuple[str, str | None, str | None], data_status: str | None, lei: dict | None) -> dict:
    """regional.proposta com o status já decidido (st = (status, statusTxt, statusTxt_en))."""
    x = regional.proposta(pid, sigla, tipo, data, ementa, situacao, url, papel, status=st[0], data_status=data_status,
                          status_txt=st[1], lei=lei)
    if st[2]:
        x["statusTxt_en"] = st[2]
    return x


def escopo_prefeito(inicio: str, sistema_pt: str, sistema_en: str, tipos_pt: str, tipos_en: str) -> tuple[str, str]:
    from ._sapl import data_en, data_pt
    desde_pt = (f"desde {data_pt(inicio)}, quando assumiu a prefeitura" if inicio > B.INICIO
                else f"desde {data_pt(inicio)}, começo do mandato")
    desde_en = (f"since {data_en(inicio)}, when the current mayor took office" if inicio > B.INICIO
                else f"since {data_en(inicio)}, start of the term")
    return (f"Projetos que a prefeitura mandou à Câmara Municipal {desde_pt} ({tipos_pt}), segundo {sistema_pt}",
            f"Bills the mayor's office sent to the City Council {desde_en} ({tipos_en}), according to {sistema_en}")


def inicio_prefeito(ibge: str, uf: str) -> tuple[str | None, str]:
    """(id do prefeito de hoje, data do começo da conta: 1º/1/2025 ou o "desde" da ficha, para quem assumiu depois)."""
    pref = B.cidade(ibge, uf).get("prefeito") or {}
    return pref.get("id"), max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)


__all__ = ["SemTempo", "prazo", "Rede", "ler_estado", "guardar_estado", "dias_desde", "data_br", "lista", "limpar_membros",
           "chave_nome", "Nomes", "proposta", "escopo_prefeito", "inicio_prefeito"]
