"""Ajudas das capitais sem SAPL lidas pela frente "capitais-a" (Vitória, Teresina, Cuiabá e Goiânia), por cima de _base.py:

- Rede: pedidos educados a um servidor (robots.txt com Disallow e Crawl-delay, um pedido por vez, pausa mínima, cookies para
  os formulários, redirecionamento só para onde o robots.txt deixa, o fim da rodada e a contagem de pedidos e bytes);
- membros(): a lista oficial no formato do site, ligada ao TSE de 2024 (o mesmo que _base.so_lista faz, mas devolvendo
  as fichas para cada coletor juntar propostas e gastos);
- bloco_gastos(): o bloco "gastos" do perfil (o mesmo formato dos vereadores de São Paulo e das Assembleias);
- publicados(): o que já está publicado no arquivo da cidade (para não apagar um bloco quando uma leitura falha).
"""
from __future__ import annotations

import gzip
import http.cookiejar
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

from comum import EXTRAS_CIDADES, ler_json, log, sem_acento

from . import _base as B

PAUSA = float(os.environ.get("CAPITAIS_PAUSA") or 1.5)  # segundos entre pedidos ao mesmo servidor (ou o Crawl-delay, se maior)
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]


class SemTempo(Exception):
    """Acabou o tempo (ou o orçamento) desta rodada: o resto fica para a próxima."""


def prazo_da_rodada() -> float | None:
    try:
        return float(os.environ.get("LEGISLATIVOS_PRAZO") or 0) or None
    except ValueError:
        return None


class _Redirecionamento(urllib.request.HTTPRedirectHandler):
    """Só segue um redirecionamento se o robots.txt do destino deixar (senão, para com erro)."""

    def __init__(self, ua: str):
        super().__init__()
        self.ua = ua

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not B.robots(newurl, self.ua).pode(newurl):
            raise RuntimeError(f"redirecionamento para {newurl}, que o robots.txt de lá não deixa ler: não seguido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Rede:
    """Pedidos a um servidor: cookies (formulários), robots.txt, pausa, prazo da rodada, contagem de pedidos e bytes.
    O User-Agent é o do projeto no formato dos robôs de busca (_base.UA_COMPAT): alguns servidores barram quem não começa
    com "Mozilla/5.0"; ele continua dizendo quem somos."""

    def __init__(self, prazo: float | None = None, pausa: float = PAUSA):
        self.ua = B.UA_COMPAT
        self.prazo, self.pausa = prazo if prazo is not None else prazo_da_rodada(), pausa
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj), _Redirecionamento(self.ua))
        self.n, self.bytes, self.fio, self.segundos = 0, 0, 0, 0.0

    def tempo(self, folga: float = 0) -> None:
        if self.prazo and time.time() + folga > self.prazo:
            raise SemTempo("fim do tempo da rodada")

    def pedir(self, url: str, dados: dict | None = None, headers: dict | None = None, timeout: int = 120,
              tentativas: int = 2, parar_em: tuple[bytes, bytes] | None = None) -> tuple[bytes, str]:
        """(corpo, Content-Type). Erro de rede ou HTTP = RuntimeError (depois de uma nova tentativa nos erros 5xx e de rede).
        parar_em = (marca do começo, marca do fim): para de ler a resposta quando a marca do fim aparece depois da do começo
        (o resto da página não interessa e não precisa vir pela rede)."""
        self.tempo()
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        h = {"User-Agent": self.ua, "Accept-Encoding": "gzip", "Accept-Language": "pt-BR,pt;q=0.9"}
        if corpo is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        h.update(headers or {})
        erro = None
        for t in range(tentativas):
            B.esperar_vez(url, self.pausa, self.ua)
            t0 = time.time()
            try:
                req = urllib.request.Request(url, data=corpo, headers=h)
                with self.op.open(req, timeout=timeout) as r:
                    gz = r.headers.get("Content-Encoding") == "gzip"
                    ct = r.headers.get("Content-Type") or ""
                    if parar_em is None:
                        b = r.read()
                        self.fio += len(b)  # bytes que vieram pela rede (comprimidos, quando o servidor comprime)
                        if gz:
                            b = gzip.decompress(b)
                    else:
                        b = self._ler_ate(r, gz, parar_em)
                self.n += 1
                self.bytes += len(b)
                return b, ct
            except urllib.error.HTTPError as e:
                self.n += 1
                erro = RuntimeError(f"HTTP {e.code} em {url}")
                if e.code < 500:
                    break
            except Exception as e:  # rede instável, servidor fora do ar, redirecionamento proibido
                self.n += 1
                erro = RuntimeError(f"{type(e).__name__} em {url}: {str(e)[:160]}")
                if "robots.txt" in str(e):
                    break
            finally:
                self.segundos += time.time() - t0
                B.pedido_feito(url)
            if t + 1 < tentativas:
                self.tempo(20)
                time.sleep(10)
        raise erro

    def _ler_ate(self, r, gz: bool, parar_em: tuple[bytes, bytes]) -> bytes:
        inicio, fim = parar_em
        dz = zlib.decompressobj(16 + zlib.MAX_WBITS) if gz else None
        buf, achou = bytearray(), -1
        while True:
            bloco = r.read(65536)
            if not bloco:
                break
            self.fio += len(bloco)
            buf += dz.decompress(bloco) if dz else bloco
            if achou < 0:
                achou = buf.find(inicio)
            if achou >= 0 and buf.find(fim, achou) >= 0:
                break
        return bytes(buf)


# ------------------------------------------------------------------------------------------------ lista oficial
def membros(ibge: str, uf: str, casa: dict, pessoas: list[dict], vagas: int, tse_manual: dict | None = None,
            minimo: float = 0.8) -> tuple[list[dict], dict[str, dict], "B.Tse"]:
    """A lista oficial no formato do site (como _base.so_lista), ligada ao TSE de 2024.
    pessoas = [{chave, nome, nomeCivil?, partido (como a Câmara escreve), foto (URL), url, genero?, email?}].
    Devolve (membros, {chave oficial: membro}, Tse). Confere o tamanho (de 80% das vagas até as vagas + 3)."""
    if not (vagas * minimo <= len(pessoas) <= vagas + 3):
        raise RuntimeError(f"a lista oficial tem {len(pessoas)} pessoas para {vagas} vagas: a página deve ter mudado")
    tse = B.Tse(ibge, uf, tse_manual)
    lista, por_chave = [], {}
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
        lista.append(m)
        por_chave[str(p["chave"])] = dict(m, _cand=cand, _p=p)
    ids = [m["id"] for m in lista]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"duas pessoas com o mesmo id: {sorted(i for i in ids if ids.count(i) > 1)}")
    if tse.sem_ligacao:
        log(f"  {casa.get('sigla')}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
    return lista, por_chave, tse


def extras_base(m: dict, casa: dict) -> dict:
    """O começo do registro de uma pessoa no arquivo da cidade: página oficial e a fonte da lista."""
    x = {"links": {"oficial": m.get("url"), "email": (m.get("_p") or {}).get("email"), "redes": []}, "fontes": [casa["fonte"]]}
    if m.get("foto"):
        x["fotoCredito"] = casa["casa"]
    return x


def publicados(ibge: str, campo: str) -> dict[str, dict]:
    """{id: bloco} de um campo ("gastos", "propostas") no arquivo da cidade já publicado."""
    d = ler_json(EXTRAS_CIDADES / f"{ibge}.json", {}) or {}
    return {pid: x[campo] for pid, x in (d.get("pessoas") or {}).items() if x.get(campo)}


# ------------------------------------------------------------------------------------------------ gastos
def bloco_gastos(por_mes: dict[tuple[int, int], dict[str, float]], nome: tuple[str, str], f: dict) -> dict | None:
    """O bloco "gastos" do perfil (o formato de São Paulo): o ano mais recente com gastos (total e por tipo), o total desde o
    primeiro mês com gastos, os meses do ano mostrado. por_mes = {(ano, mês): {tipo: valor}} ("" = sem tipo)."""
    meses = sorted(k for k, v in por_mes.items() if round(sum(v.values()), 2) > 0)
    if not meses:
        return None
    ano = meses[-1][0]
    do_ano = [k for k in meses if k[0] == ano]
    por_tipo: dict[str, float] = {}
    for k in do_ano:
        for t, val in por_mes[k].items():
            por_tipo[t] = por_tipo.get(t, 0.0) + val
    tipos = [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(por_tipo.items(), key=lambda kv: (-kv[1], kv[0])) if t and round(v, 2)]
    if "" in por_tipo and len(por_tipo) == 1:
        tipos = []  # a Câmara não divide por tipo: o perfil mostra só o total (como na Alece)
    return {"ano": ano, "total": round(sum(por_tipo.values()), 2), "porTipo": tipos,
            "mandatoTotal": round(sum(sum(por_mes[k].values()) for k in meses), 2),
            "desde": f"{meses[0][0]}-{meses[0][1]:02d}", "meses": [f"{ano}-{do_ano[0][1]:02d}", f"{ano}-{do_ano[-1][1]:02d}"],
            "nome": nome[0], "nome_en": nome[1], "fonte": f}


def brl(s: str | None) -> float | None:
    """'R$ 1.234,56' → 1234.56 (aceita também '1.234,5' e '1.234.56', erros de digitação que aparecem nas planilhas)."""
    t = re.sub(r"[^\d.,-]", "", (s or "").replace("R$", ""))
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d{1,2}|-?\d+,\d{1,2}", t):
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*\.\d{2}", t):
        return float(t[:-3].replace(".", "") + t[-3:])
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+|-?\d+", t):
        return float(t.replace(".", ""))
    return None


def nome_mes(m: int) -> str:
    return MESES[m - 1]


__all__ = ["Rede", "SemTempo", "prazo_da_rodada", "membros", "extras_base", "publicados", "bloco_gastos", "brl", "nome_mes",
           "MESES", "PAUSA"]
