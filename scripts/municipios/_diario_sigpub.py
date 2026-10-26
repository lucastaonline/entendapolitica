"""SIGPub (www.diariomunicipal.com.br/<associação>): as matérias com "lei" e com "veto" no título, de todas as cidades
de uma associação de municípios, mês a mês (fase 4: o que cada prefeitura fez).

Por que por associação e não cidade por cidade: a busca do SIGPub aceita só o título e o período (sem a cidade) e
devolve as matérias de todas as cidades da associação, 25 por página, com a cidade (entidade) e o órgão de cada uma.
Na primeira carga isso dá quase o mesmo número de páginas que buscar cidade por cidade, mas toda semana basta ler as
matérias novas da associação inteira (poucas páginas), em vez de uma página por cidade.

- Robots.txt do site: libera tudo (sem Crawl-delay). Mesmo assim: um pedido por vez, PAUSA segundos entre pedidos.
- Janelas de um mês, em ordem "mais antigas primeiro" (as páginas de um mês que já passou não mudam): a leitura pára no
  limite de tempo e continua de onde parou na rodada seguinte (estado em .cache/municipios/diarios/atos/sigpub-<assoc>/).
- Um mês lido inteiro mais de 7 dias depois de acabar não é lido de novo; o mês em curso é lido só a partir do último dia
  já lido. A busca não mostra mais de 10.000 resultados: um mês com mais que isso seria dividido em semanas.
- Títulos sem o número da lei ("Lei Municipal"): o número está no texto da matéria, lido uma vez (cache para sempre).
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

import _atos as A

BASE = "https://www.diariomunicipal.com.br/"
PAUSA = 1.5              # segundos entre dois pedidos ao SIGPub (um servidor para ~1.200 cidades)
LIMITE_BUSCA = 10_000    # a busca não pagina além disso
POR_PAGINA = 25

_CARD = re.compile(r'(?s)<li class="materia-card">(.*?)</li>\s*(?=<li class="materia-card">|</ul>)')
_TOTAL = re.compile(r"(?s)Mostrando\s*<strong>\s*\d+\s*</strong>\s*a\s*<strong>\s*\d+\s*</strong>\s*de\s*<strong>\s*([\d.]+)")
_OPT = re.compile(r'<option value="(\d+)">([^<]*)</option>')


def _limpa(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s or ""))).strip()


def _iso(d: str) -> str:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def ler_pagina(t: str) -> dict | None:
    """{"total": n, "itens": [[código, título, entidade, órgão, circulação]], "entidades": {id: nome}} ou None (página que
    não é de resultado: erro, manutenção...)."""
    total = None
    m = _TOTAL.search(t)
    if m:
        total = int(m.group(1).replace(".", ""))
    elif "Nenhuma matéria encontrada" in t:
        total = 0
    if total is None:
        return None
    itens = []
    for c in _CARD.findall(t):
        a = re.search(r'(?s)materia-card__titulo">\s*<a href="[^"]*/materia/([A-Z0-9]+)"[^>]*>(.*?)</a>', c)
        if not a:
            continue
        ent = re.search(r'(?s)materia-card__entidade">(.*?)</span>', c)
        org = re.search(r'(?s)materia-card__orgao">(.*?)</span>', c)
        dt = re.search(r'(?s)<dt>Circula[^<]*</dt>\s*<dd>([^<]+)</dd>', c)
        itens.append([a.group(1), _limpa(a.group(2)), _limpa(ent.group(1)) if ent else "",
                      _limpa(org.group(1)) if org else "", _iso(dt.group(1).strip()) if dt else ""])
    ents = {}
    i = t.find('id="busca_avancada_entidade"')
    if i >= 0:
        j = t.find("</select>", i)
        ents = {k: _limpa(v) for k, v in _OPT.findall(t[i:j])}
    return {"total": total, "itens": itens, "entidades": ents}


def url_busca(assoc: str, titulo: str, ini: str, fim: str, pagina: int = 1, entidade: str | None = None,
              ordem: str = "antiga") -> str:
    q = []
    if entidade:
        q.append(("busca_avancada[entidade]", entidade))
    q += [("busca_avancada[titulo]", titulo), ("busca_avancada[dataInicio]", ini), ("busca_avancada[dataFim]", fim)]
    if ordem != "recente":
        q.append(("busca_avancada[ordenacao]", ordem))
    q.append(("busca_avancada[pagina]", str(pagina)))
    return f"{BASE}{assoc}/pesquisar?" + urllib.parse.urlencode(q)


def url_pessoa(assoc: str, entidade: str, titulo: str, ini: str, fim: str) -> str:
    """A busca que uma pessoa abre para conferir: a cidade, o título e o período (mais recentes primeiro)."""
    return url_busca(assoc, titulo, ini, fim, 1, entidade, ordem="recente").replace("&busca_avancada%5Bpagina%5D=1", "")


def _meses(ini: str, fim: str) -> list[tuple[str, str, str]]:
    """[(mês "AAAA-MM", primeiro dia, último dia)] de ini até fim."""
    out = []
    d = date.fromisoformat(ini[:8] + "01")
    f = date.fromisoformat(fim)
    while d <= f:
        prox = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((d.isoformat()[:7], d.isoformat(), (prox - timedelta(days=1)).isoformat()))
        d = prox
    return out


class Associacao:
    """O que já foi lido do Diário de uma associação no SIGPub (cache) e a leitura do que falta."""

    def __init__(self, rede, assoc: str, pasta: Path, hoje: str, desde: str, log=None):
        self.rede, self.assoc, self.hoje, self.desde = rede, assoc, hoje, desde
        self.log = log
        self.pasta = pasta / f"sigpub-{assoc}"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arq_estado = self.pasta / "estado.json"
        self.estado = self._ler(self.arq_estado, {}) or {}
        self.estado.setdefault("meses", {})
        self.estado.setdefault("vetos", {})
        self.pedidos = 0
        self.segundos = 0.0
        self.erro = None

    # ------------------------------------------------------------ arquivos
    @staticmethod
    def _ler(arq: Path, padrao=None):
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            return padrao

    @staticmethod
    def _gravar(arq: Path, obj):
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for _ in range(20):          # no Windows, outro programa lendo o arquivo impede a troca por um instante
            try:
                tmp.replace(arq)
                return
            except PermissionError:
                time.sleep(0.25)
        arq.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp.unlink(missing_ok=True)

    def _salvar_estado(self):
        self._gravar(self.arq_estado, self.estado)

    def itens_mes(self, mes: str, tipo: str = "lei") -> dict:
        return self._ler(self.pasta / f"{tipo}-{mes}.json", {}) or {}

    # ------------------------------------------------------------ rede
    def _pagina(self, url: str) -> dict | None:
        t0 = time.time()
        r = self.rede.pagina(url)
        self.pedidos += 1
        self.segundos += time.time() - t0
        if not r.ok or not r.corpo:
            self.erro = r.erro or f"http {r.status}"
            return None
        p = ler_pagina(r.corpo.decode(r.charset or "utf-8", "replace"))
        if p is None:
            self.erro = "pagina sem resultado"
            return None
        if p["entidades"]:
            self.estado["entidades"] = p["entidades"]
        return p

    # ------------------------------------------------------------ leitura
    def pendente(self) -> bool:
        """Falta ler algum mês (ou a semana corrente)?"""
        for mes, ini, fim in _meses(self.desde, self.hoje):
            e = self.estado["meses"].get(mes) or {}
            if not self._fechado(e, fim):
                return True
        return False

    def completo(self) -> bool:
        """Todos os meses do período até o mês passado foram lidos inteiros ao menos uma vez (dá para contar). O mês em
        curso pode faltar: aí a contagem vai até o último dia lido do mês passado."""
        meses = _meses(self.desde, self.hoje)
        return all((self.estado["meses"].get(m) or {}).get("completo") for m, _, _ in meses[:-1])

    def falta_carga(self) -> bool:
        """A primeira carga ainda não terminou (algum mês até o mês passado não foi lido inteiro)?"""
        return not self.completo()

    def _fechado(self, e: dict, fim_mes: str) -> bool:
        if not e.get("completo"):
            return False
        lido = e.get("lido") or ""
        if fim_mes < self.hoje:
            return lido > (date.fromisoformat(fim_mes) + timedelta(days=7)).isoformat()
        return lido >= self.hoje   # o mês em curso: já lido hoje

    def ler(self, prazo: float, max_paginas: int | None = None) -> str:
        """Lê o que falta, até o prazo (time.time()). Devolve "ok", "prazo" ou "erro"."""
        lidas = 0
        for mes, ini, fim_mes in _meses(self.desde, self.hoje):
            e = self.estado["meses"].setdefault(mes, {})
            if self._fechado(e, fim_mes):
                continue
            fim = min(fim_mes, self.hoje)
            # já lido inteiro: só o que é novo, com uma semana de folga (uma resposta ruim que passou como boa numa rodada
            # não deixa um buraco para sempre)
            de = (max(ini, (date.fromisoformat(e["ate"]) - timedelta(days=7)).isoformat())
                  if e.get("completo") and e.get("ate") else ini)
            itens = self.itens_mes(mes)
            pagina = e.get("pagina", 0) + 1 if e.get("janela") == [de, fim] else 1
            total = e.get("total") if e.get("janela") == [de, fim] else None
            while True:
                if time.time() > prazo or (max_paginas is not None and lidas >= max_paginas):
                    self._salvar_estado()
                    return "prazo"
                p = self._pagina(url_busca(self.assoc, "lei", de, fim, pagina))
                lidas += 1
                if p is None:
                    self._salvar_estado()
                    return "erro"
                if total is not None and p["total"] < total and pagina > 1:
                    pagina, total = 1, None   # sumiram matérias no meio: lê de novo (as repetidas são ignoradas)
                    continue
                total = p["total"]
                if total >= LIMITE_BUSCA:
                    self.erro = f"mais de {LIMITE_BUSCA} resultados em {mes}"
                    self._salvar_estado()
                    return "erro"
                if not p["itens"] and (pagina - 1) * POR_PAGINA < total:
                    # o total diz que há matérias nesta página e ela veio sem nenhuma: resposta cortada, não é o fim
                    self.erro = f"página {pagina} de {mes} sem matérias"
                    self._salvar_estado()
                    return "erro"
                for cod, tit, ent, org, circ in p["itens"]:
                    itens[cod] = [tit, ent, org, circ]
                self._gravar(self.pasta / f"lei-{mes}.json", itens)
                e.update({"janela": [de, fim], "pagina": pagina, "total": total})
                if pagina * POR_PAGINA >= total:
                    if de == ini and len(itens) < total and e.get("curto", 0) < 2:
                        # o mês lido inteiro tem menos matérias que a busca diz: lê de novo na próxima rodada (depois
                        # de 3 tentativas, fica como está: a conferência da numeração das leis mostra o que faltar)
                        self.erro = f"{mes}: {len(itens)} de {total} matérias"
                        e["curto"] = e.get("curto", 0) + 1
                        e.pop("janela", None)
                        e.pop("pagina", None)
                        self._salvar_estado()
                        return "erro"
                    e.pop("curto", None)
                    e.update({"completo": True, "lido": self.hoje, "ate": fim, "n": len(itens)})
                    e.pop("janela", None)
                    e.pop("pagina", None)
                    self._salvar_estado()
                    if self.log:
                        self.log(f"    [sigpub] {self.assoc} {mes}: {len(itens)} matérias ({pagina} página(s) de {de} a {fim})")
                    break
                pagina += 1
                self._salvar_estado()
        return self.ler_vetos(prazo)

    def ler_vetos(self, prazo: float) -> str:
        """Os vetos são poucos: a busca "veto" do período inteiro é lida de novo a cada rodada (umas 2 páginas). Se a
        leitura falhar, fica a anterior; se der certo, junta com a anterior (um veto já lido não some)."""
        v = self.estado["vetos"]
        if v.get("lido") == self.hoje and v.get("completo"):
            return "ok"
        itens = {}
        pagina = 1
        while True:
            if time.time() > prazo:
                return "prazo"
            p = self._pagina(url_busca(self.assoc, "veto", self.desde, self.hoje, pagina))
            if p is None:
                return "erro"
            if not p["itens"] and (pagina - 1) * POR_PAGINA < p["total"]:
                self.erro = f"página {pagina} dos vetos sem matérias"
                return "erro"
            for cod, tit, ent, org, circ in p["itens"]:
                itens[cod] = [tit, ent, org, circ]
            if pagina * POR_PAGINA >= p["total"]:
                break
            pagina += 1
        if v.get("completo"):
            itens = {**(self._ler(self.pasta / "veto.json", {}) or {}), **itens}
        self._gravar(self.pasta / "veto.json", itens)
        self.estado["vetos"] = {"completo": True, "lido": self.hoje, "n": len(itens)}
        self._salvar_estado()
        return "ok"

    # ------------------------------------------------------------ matérias sem número no título
    def materia(self, cod: str, prazo: float) -> dict | None:
        """O começo do texto de uma matéria ("LEI Nº 346/2026, DE 15 DE OUTUBRO DE 2026..."), lido uma vez."""
        pasta = self.pasta / "materias"
        arq = pasta / f"{cod}.json"
        d = self._ler(arq)
        if d is not None:
            return d
        if time.time() > prazo:
            return None
        t0 = time.time()
        r = self.rede.pagina(f"{BASE}{self.assoc}/materia/{cod}")
        self.pedidos += 1
        self.segundos += time.time() - t0
        if not r.ok or not r.corpo:
            return None
        t = r.corpo.decode(r.charset or "utf-8", "replace")
        t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
        texto = _limpa(t)
        i = texto.find("Baixar a edição completa")
        if i < 0:
            # toda página de matéria tem o link da edição; sem ele, é erro ou página de bloqueio: não guarda nada
            return None
        corpo = texto[i:]
        lei = None
        for m in re.finditer(r"(?i)\blei\b", corpo[:6000]):
            cand = A.ler_titulo(corpo[m.start():m.start() + 160])
            if cand and cand.get("tipo") == "lei" and cand.get("num") is not None:
                lei = cand
                break
        d = {"inicio": corpo[:400], "lei": lei}
        pasta.mkdir(exist_ok=True)
        self._gravar(arq, d)
        return d

    # ------------------------------------------------------------ o que já foi lido
    def todos_itens(self, tipo: str = "lei") -> dict:
        if tipo == "veto":
            return self._ler(self.pasta / "veto.json", {}) or {}
        out = {}
        for mes, _, _ in _meses(self.desde, self.hoje):
            out.update(self.itens_mes(mes))
        return out

    def data_leitura(self) -> str | None:
        """Até que dia as matérias foram lidas (o fim do período da contagem)."""
        meses = [m for m, _, _ in _meses(self.desde, self.hoje)]
        for m in reversed(meses):
            e = self.estado["meses"].get(m) or {}
            if e.get("completo"):
                return e.get("ate")
        return None


__all__ = ["Associacao", "BASE", "PAUSA", "ler_pagina", "url_busca", "url_pessoa"]
