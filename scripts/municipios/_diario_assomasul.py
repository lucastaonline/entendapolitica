"""Diário Oficial MS da Assomasul (www.diariooficialms.com.br): as matérias com "lei" e com "veto" no título de cada
cidade (fase 4: o que cada prefeitura fez).

A lista vem do "filtro avançado" do site (município, título e período): é o mesmo pedido que a página faz no navegador
(https://www.diariooficialms.com.br/filtro, com o cabeçalho X-Requested-With), que devolve a lista em JSON. Baixar o texto
de uma matéria pede reCAPTCHA: isso não é feito (só os títulos da lista são lidos). O Diário não diz o órgão de cada
matéria: as leis que a própria Câmara promulga só ficam de fora quando o título diz "promulgada".

Robots.txt: libera tudo. Um pedido por vez, PAUSA segundos entre pedidos; cada cidade é lida de novo depois de DIAS dias.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import date
from pathlib import Path

SITE = "https://www.diariooficialms.com.br"
FILTRO = SITE + "/filtro"
PAGINA_HUMANA = SITE + "/assomasul?pagina=filtro-avancado"
PAUSA = 1.5
POR_PEDIDO = 500
DIAS = 6


def _br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _iso(br: str) -> str:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", br or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def url_filtro(entidade: str, titulo: str, ini: str, fim: str, start: int = 0, length: int = POR_PEDIDO) -> str:
    q = {"draw": 1, "start": start, "length": length, "filtro[municipio_id]": entidade, "filtro[titulo]": titulo,
         "filtro[data_de_inicio]": _br(ini), "filtro[data_de_fim]": _br(fim)}
    return FILTRO + "?" + urllib.parse.urlencode(q)


class Cidade:
    """As matérias de uma cidade no Diário Oficial MS (cache em .cache/municipios/diarios/atos/assomasul/<entidade>.json)."""

    def __init__(self, rede, entidade: str, pasta: Path, hoje: str, desde: str):
        self.rede, self.ent, self.hoje, self.desde = rede, str(entidade), hoje, desde
        self.pasta = pasta / "assomasul"
        self.arq = self.pasta / f"{self.ent}.json"
        try:
            self.d = json.loads(self.arq.read_text(encoding="utf-8"))
        except Exception:
            self.d = {}
        self.pedidos = 0
        self.erro = None

    def precisa(self) -> bool:
        lido = self.d.get("lido") or ""
        if not lido or self.d.get("desde") != self.desde:
            return True
        return (date.fromisoformat(self.hoje) - date.fromisoformat(lido)).days >= DIAS

    def _lista(self, titulo: str) -> list | None:
        out, start = [], 0
        while True:
            r = self.rede.pagina(url_filtro(self.ent, titulo, self.desde, self.hoje, start), aceitar="application/json",
                                 extra={"X-Requested-With": "XMLHttpRequest"})
            self.pedidos += 1
            if not r.ok:
                self.erro = r.erro or f"http {r.status}"
                return None
            try:
                j = json.loads(r.corpo.decode("utf-8"))
            except Exception:
                self.erro = "json"
                return None
            # a resposta do filtro tem "data" (a lista) e o total; outra coisa (erro, aviso de bloqueio) não vale
            if not isinstance(j, dict) or not isinstance(j.get("data"), list) or not (
                    str(j.get("recordsFiltered", "")).isdigit()):
                self.erro = "resposta sem a lista"
                return None
            dados = j["data"]
            for x in dados:
                if x.get("consorcio_id"):
                    continue
                tit = re.sub(r"(?is)<br.*$", "", x.get("titulo") or "").strip()
                out.append([str(x.get("id")), tit, x.get("nome_da_cidade_ou_do_consorcio") or "", "",
                            _iso(x.get("data_de_circulacao") or "")])
            total = int(j["recordsFiltered"])
            if not dados and start < total:
                self.erro = "página da lista vazia antes do fim"
                return None
            start += len(dados)
            if start >= total:
                return out

    def ler(self) -> bool:
        """Lê de novo; se falhar (erro de rede, bloqueio, resposta vazia ou quebrada), o cache não muda. No mesmo período,
        o que já foi lido não some: a leitura nova só acrescenta (ou corrige) matérias."""
        leis = self._lista("lei")
        if leis is None:
            return False
        vetos = self._lista("veto")
        if vetos is None:
            return False
        antes = self.d if self.completo() else {}
        self.d = {"lido": self.hoje, "desde": self.desde, "ate": self.hoje,
                  "lei": {**(antes.get("lei") or {}), **{c: [t, e, o, d] for c, t, e, o, d in leis}},
                  "veto": {**(antes.get("veto") or {}), **{c: [t, e, o, d] for c, t, e, o, d in vetos}}}
        self.pasta.mkdir(parents=True, exist_ok=True)
        tmp = self.arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for _ in range(20):          # no Windows, outro programa lendo o arquivo impede a troca por um instante
            try:
                tmp.replace(self.arq)
                return True
            except PermissionError:
                time.sleep(0.25)
        self.arq.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp.unlink(missing_ok=True)
        return True

    def completo(self) -> bool:
        return bool(self.d.get("lido")) and self.d.get("desde") == self.desde

    def itens(self, tipo: str) -> dict:
        return self.d.get(tipo) or {}

    def data_leitura(self) -> str | None:
        return self.d.get("ate")


__all__ = ["Cidade", "PAGINA_HUMANA", "PAUSA", "url_filtro"]
