"""Ajudas comuns dos coletores de Recife, Salvador e Belém (frente das capitais, outubro de 2026): o que já foi publicado
no arquivo da cidade (para não publicar nada pela metade numa primeira carga), o fim da rodada, textos das páginas oficiais
e um pedido educado com cache (robots.txt, intervalo do servidor e User-Agent do projeto, como em _base.baixar_pagina).
Arquivos que começam com "_" não são coletores (scripts/legislativos.py pula)."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import time

from comum import EXTRAS_CIDADES, UA, baixar, ler_json

from . import _base as B


def prazo() -> float | None:
    """Fim do tempo desta rodada (scripts/legislativos.py --minutos), em segundos desde 1970."""
    try:
        return float(os.environ.get("LEGISLATIVOS_PRAZO") or 0) or None
    except ValueError:
        return None


def sem_tempo(margem: float = 120) -> bool:
    p = prazo()
    return bool(p) and time.time() > p - margem


def publicados(ibge: str, campo: str = "propostas") -> dict[str, dict]:
    """{id: bloco} de um campo ("propostas", "gastos") no arquivo da cidade já publicado: enquanto a primeira carga não
    termina (no robô, que começa com o cache vazio, por exemplo), fica o que já estava, em vez de nada ou de metade."""
    d = ler_json(EXTRAS_CIDADES / f"{ibge}.json", {}) or {}
    return {pid: x[campo] for pid, x in (d.get("pessoas") or {}).items() if isinstance(x, dict) and x.get(campo)}


def texto(s: str | None) -> str:
    """HTML (às vezes escapado duas vezes, como no SAGL) -> texto simples numa linha."""
    t = html.unescape(html.unescape(s or ""))
    t = re.sub(r"<br\s*/?>|</p>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def data_iso(s: str | None) -> str | None:
    """'23/12/2025' (ou '23/12/2025 14:35') -> '2025-12-23'."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def menos(h: str, dias: int) -> str:
    return (dt.date.fromisoformat(h) - dt.timedelta(days=dias)).isoformat()


def lista_oficial(ibge: str, uf: str, casa: dict, pessoas: list[dict], vagas: int, tse_manual: dict | None = None,
                  minimo: float = 0.8) -> tuple[list, dict, "B.Tse"]:
    """A lista oficial de quem está no cargo, como em _base.so_lista (mesma conferência do tamanho, mesma ligação com o TSE,
    mesmos campos), para as Câmaras que publicam também propostas ou gastos: (membros, {id: dados a mais}, Tse).
    pessoas = [{chave, nome, nomeCivil?, partido, foto, url, email?, genero?}]; cada item de membros ganha "_chave"."""
    if not (vagas * minimo <= len(pessoas) <= vagas + 3):
        raise RuntimeError(f"a lista oficial tem {len(pessoas)} pessoas para {vagas} vagas: a página deve ter mudado")
    tse = B.Tse(ibge, uf, tse_manual)
    membros, extras = [], {}
    for p in pessoas:
        nome = B.nome_limpo(p["nome"])
        civil = B.nome_limpo(p.get("nomeCivil")) if p.get("nomeCivil") else None
        sigla = B.partido(p.get("partido"))
        pid, cand = tse.casar(p["chave"], [nome, civil], sigla)
        supl = (cand or {}).get("sit") == "SUPLENTE"
        if not civil and cand and cand.get("nome"):
            civil = B.nome_limpo(cand["nome"])
        if civil and re.sub(r"\W", "", B.sem_acento(civil).lower()) == re.sub(r"\W", "", B.sem_acento(nome).lower()):
            civil = None
        g = p.get("genero") or (cand or {}).get("genero")
        m = {"id": pid, "nome": nome, "nomeCivil": civil, "partido": sigla, "genero": g if g in ("F", "M") else None,
             "foto": B.foto(p.get("foto"), pid, ibge), "url": p.get("url"),
             "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None,
             "_chave": p["chave"], "_cand": cand}
        membros.append(m)
        x = {"links": {"oficial": p.get("url"), "email": p.get("email"), "redes": []}, "fontes": [casa["fonte"]]}
        if m["foto"]:
            x["fotoCredito"] = casa["casa"]
        extras[pid] = x
    ids = [m["id"] for m in membros]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"duas pessoas com o mesmo id: {sorted(i for i in ids if ids.count(i) > 1)}")
    if tse.sem_ligacao:
        from comum import log
        log(f"  {casa.get('sigla')}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
    return membros, extras, tse


def chave_nome(s: str | None) -> str:
    """Nome sem acento, sem título ("Ver.", "Ver.ª", "Vereador(a)") e sem o partido entre parênteses, para comparar."""
    t = B.sem_acento((s or "").lower())
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*(ver(eador[a]?)?\.?\s*a?\b\.?|vereador\(a\))\s*", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def ligar_nome(nome: str, membros: list[dict], tse: "B.Tse | None" = None, manual: dict | None = None) -> str | None:
    """id da pessoa da lista oficial que é este autor (nome civil ou parlamentar, como a Câmara escreve). Igual; ou quase
    igual (erro de digitação: "Guimaçães" x "Guimarães", "Segunda" x "Segundo": parecença de 0,92 ou mais, sem empate); ou
    com todas as palavras de um nome dentro do outro (pelo menos 2, sem empate: "Hélio Lula Ferreira" x "Helio Ferreira").
    Compara também com o nome civil e o nome de urna da candidatura de 2024 (TSE). manual = {nome como a Câmara escreve:
    id}, conferido à mão. Na dúvida, None (melhor não ligar do que ligar errado)."""
    import difflib
    alvo = chave_nome(nome)
    if not alvo:
        return None
    if manual and alvo in {chave_nome(k): v for k, v in manual.items()}:
        return {chave_nome(k): v for k, v in manual.items()}[alvo]
    nomes: dict[str, list[str]] = {}
    for m in membros:
        ns = [m.get("nomeCivil"), m.get("nome")]
        if tse is not None:
            c = tse.por_sq.get(m["id"].rsplit("-", 1)[-1])
            if c:
                ns += [c.get("nome"), c.get("urna")]
        nomes[m["id"]] = [chave_nome(n) for n in ns if n]
    iguais = {pid for pid, ns in nomes.items() if alvo in ns}
    if len(iguais) == 1:
        return iguais.pop()
    if iguais:
        return None
    notas = sorted(((max(difflib.SequenceMatcher(None, alvo, n).ratio() for n in ns), pid) for pid, ns in nomes.items() if ns),
                   reverse=True)
    if notas and notas[0][0] >= 0.92 and (len(notas) == 1 or notas[1][0] < notas[0][0] - 0.05):
        return notas[0][1]
    sw = {"da", "de", "do", "das", "dos", "e"}
    pa = set(alvo.split()) - sw
    sub = set()
    for pid, ns in nomes.items():
        for n in ns:
            pb = set(n.split()) - sw
            if min(len(pa), len(pb)) >= 2 and (pa <= pb or pb <= pa):
                sub.add(pid)
    return sub.pop() if len(sub) == 1 else None


class Rede:
    """Pedidos a um servidor oficial: robots.txt (Disallow e Crawl-delay) e intervalo entre pedidos pelo _base
    (esperar_vez/pedido_feito), User-Agent do projeto, novas tentativas espaçadas, contagem de pedidos e cache opcional em
    .cache/camaras/<IBGE>/http/."""

    def __init__(self, ibge: str, pausa: float = 1.0, ua: str | None = None):
        self.ibge, self.pausa, self.ua = ibge, pausa, ua or UA
        self.n = 0

    def bruto(self, url: str, dados: bytes | None = None, headers: dict | None = None, tentativas: int = 3) -> bytes:
        h = {"User-Agent": self.ua}
        h.update(headers or {})
        if dados is not None:
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        erro = None
        for t in range(tentativas):
            B.esperar_vez(url, self.pausa, self.ua)
            try:
                b = baixar(url, tentativas=1, timeout=120, headers=h, dados=dados)
                self.n += 1
                return b
            except RuntimeError as e:
                self.n += 1
                erro = e
                if re.search(r"HTTP Error (4\d\d)", str(e)) and "429" not in str(e):
                    break  # erro do pedido (página que não existe): tentar de novo não adianta
                time.sleep(min(30, 5 * (t + 1)))
            finally:
                B.pedido_feito(url)
        raise RuntimeError(str(erro))

    def json(self, url: str, **kw):
        return json.loads(self.bruto(url, headers={"Accept": "application/json"}, **kw).decode("utf-8-sig"))

    def pagina(self, url: str, nome: str | None = None, idade_h: float | None = None, dados: bytes | None = None) -> str:
        """Texto da página; com nome, guardada em .cache/camaras/<IBGE>/http/<nome> (idade_h: horas que vale)."""
        arq = B.PASTA_CACHE / self.ibge / "http" / nome if nome else None
        if arq and arq.exists() and (idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < idade_h):
            return arq.read_text(encoding="utf-8")
        t = self.bruto(url, dados=dados).decode("utf-8", "replace")
        if arq:
            arq.parent.mkdir(parents=True, exist_ok=True)
            tmp = arq.with_suffix(arq.suffix + ".part")
            tmp.write_text(t, encoding="utf-8")
            os.replace(tmp, arq)
        return t
