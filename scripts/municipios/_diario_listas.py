"""Listas de leis por cidade em Diários Oficiais que separam as matérias por tipo (fase 4: o que cada prefeitura fez).

- DOSP / Imprensa Oficial Municipal (imprensaoficialmunicipal.com.br/<cidade>): a página "Lista de Leis"
  (/listaatos.php?c=<cidade>&s=Leis) traz, numa página só, todas as leis publicadas desde que a cidade entrou no Diário,
  com o título (que muitas vezes é o nome do arquivo: "LEI 1767 PARA DOM") e a data da edição. Não há lista de vetos.
  Robots.txt: só os "sinais de conteúdo" do Cloudflare (sem regras de Disallow); um pedido por cidade.

- ADiários, Instar e Digitaliza (sites de prefeituras): a página de leis do próprio site, com filtro por período ou por
  categoria e ano (ver as classes).

Cada cidade é lida de novo depois de DIAS dias (nas listas em várias páginas, só as últimas semanas, e o período inteiro
a cada 4 semanas); cache em .cache/municipios/diarios/atos/<plataforma>/<cidade>.json.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

DIAS = 6
PAUSA = 1.5


def _limpa(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s or ""))).strip()


def _iso(br: str) -> str:
    m = re.match(r"\s*(\d{2})/(\d{2})/(\d{4})", br or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _gravar(arq: Path, obj):
    arq.parent.mkdir(parents=True, exist_ok=True)
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


class CidadeLista:
    """Base: uma cidade numa plataforma que lista as leis numa página (ou poucas)."""
    plataforma = ""
    pasta_nome = ""

    def __init__(self, rede, chave: str, pasta: Path, hoje: str, desde: str):
        self.rede, self.chave, self.hoje, self.desde = rede, chave, hoje, desde
        self.arq = pasta / self.pasta_nome / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', chave)}.json"
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

    def completo(self) -> bool:
        return bool(self.d.get("lido")) and self.d.get("desde") == self.desde

    def tem_lista(self) -> bool:
        """A página lida tem uma lista de leis (sempre, nas plataformas em que a falta da lista é um erro de leitura)."""
        return True

    def itens(self, tipo: str) -> dict:
        return self.d.get(tipo) or {}

    def data_leitura(self) -> str | None:
        return self.d.get("ate")

    def _baixar(self, url: str) -> str | None:
        r = self.rede.pagina(url)
        self.pedidos += 1
        if not r.ok or not r.corpo:
            self.erro = r.erro or f"http {r.status}"
            return None
        return r.corpo.decode(r.charset or "utf-8", "replace")

    def ler_listas(self) -> dict | None:   # {"lei": {id: [titulo, entidade, orgao, data]}, "veto": {...}}
        raise NotImplementedError

    def ler(self) -> bool:
        """Lê de novo; se a leitura falhar (erro de rede, bloqueio, página de bloqueio no lugar da lista, resposta vazia
        ou quebrada), nada muda no cache: a cidade continua com a última leitura boa (ou pendente)."""
        x = self.ler_listas()
        if x is None:
            return False
        # "cheio": o dia da última leitura do período inteiro (as outras releem só as últimas semanas)
        cheio = self.hoje if x.pop("_cheio", True) else (self.d.get("cheio") or self.d.get("lido"))
        if self.completo():
            # no mesmo período, o que já foi lido não some: uma leitura nova só acrescenta (ou corrige) leis e categorias
            # (um site com problema que mostra menos leis não faz a contagem diminuir)
            for k in ("lei", "veto", "cats", "tipos"):
                if k in x or k in self.d:
                    x[k] = {**(self.d.get(k) or {}), **(x.get(k) or {})}
        self.d = {"lido": self.hoje, "desde": self.desde, "ate": self.hoje, "cheio": cheio, **x}
        _gravar(self.arq, self.d)
        return True

    CHEIO_DIAS = 28      # o período inteiro é relido uma vez a cada 4 semanas (leis cadastradas com atraso)

    def ler_cheio(self) -> bool:
        """Ler o período inteiro (primeira leitura, outro período, ou a última leitura inteira tem 4 semanas)?"""
        if not self.completo():
            return True
        cheio = self.d.get("cheio") or self.d.get("lido")
        return (date.fromisoformat(self.hoje) - date.fromisoformat(cheio)).days >= self.CHEIO_DIAS


# ---------------------------------------------------------------------------------------------------- DOSP
class DospCidade(CidadeLista):
    plataforma = "DOSP (Imprensa Oficial Municipal)"
    pasta_nome = "dosp"
    SITE = "https://imprensaoficialmunicipal.com.br"

    @staticmethod
    def slug_de(url: str) -> str | None:
        m = re.match(r"https?://(?:www\.)?imprensaoficialmunicipal\.com\.br/([A-Za-z0-9_-]+)/?$", (url or "").strip())
        return m.group(1).lower() if m else None

    def url_lista(self, ini: str | None = None, fim: str | None = None) -> str:
        return f"{self.SITE}/listaatos.php?c={self.chave}&s=Leis"

    def ler_listas(self) -> dict | None:
        t = self._baixar(self.url_lista())
        if t is None:
            return None
        if "<th>Título</th>" not in t and "<th>T&iacute;tulo</th>" not in t:
            self.erro = "página sem a lista de leis"
            return None
        leis = {}
        for i, row in enumerate(re.findall(r"(?s)<tr>(.*?)</tr>", t)):
            tds = re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)
            if len(tds) < 2:
                continue
            tit, dt = _limpa(tds[0]), _iso(_limpa(tds[1]))
            if not dt or dt < self.desde:
                continue
            link = re.search(r"href=['\"]([^'\"]+)['\"]", tds[4] if len(tds) > 4 else "")
            ident = f"{dt}|{link.group(1) if link else ''}|{tit}"
            leis[ident] = [tit, "", "", dt]
        return {"lei": leis, "veto": {}}


__all__ = ["CidadeLista", "DospCidade", "AdiariosCidade", "InstarCidade", "DigitalizaCidade", "PAUSA"]


# ---------------------------------------------------------------------------------------------------- ADiários
class AdiariosCidade(CidadeLista):
    """Sites de prefeituras do fornecedor ADiários (o Diário fica em /diariooficial.php): a página de leis do próprio site
    (/leis.php) lista as leis com número, data e ementa, com filtro por período (dtini/dtfim) e 30 por página
    (?pagina=N). É a legislação publicada no site oficial da prefeitura, não o Diário."""
    plataforma = "ADiários"
    pasta_nome = "adiarios"
    MAX_PAGINAS = 40

    @staticmethod
    def base_de(url: str) -> str | None:
        m = re.match(r"(https?://[^/]+)/(?:diariooficial\.php|jornal\.php|portal/diarioOficial\.php)", (url or "").strip())
        return m.group(1) if m else None

    @property
    def SITE(self) -> str:
        return self.chave

    @staticmethod
    def ler_titulo(titulo: str) -> dict | None:
        """"LEI MUNICIPAL: 422/2025", "LEI COMPLEMENTAR: 12/2025", "LEI PROMULGADA: 30/2025". Outras categorias da página
        (estrutura organizacional, diárias, regime jurídico, instrução normativa, lei federal...) não contam."""
        import _atos as A
        m = re.match(r"^\s*(?P<cat>[^:]+):\s*(?P<num>[\d.]*)\s*/?\s*(?P<ano>\d{2,4})?\s*$", titulo or "")
        if not m:
            return A.ler_titulo_lista(titulo)
        cat = A.norm(m["cat"])
        if not re.fullmatch(r"(?:LC - )?LEIS?(?: MUNICIPA(?:L|IS))?(?: (?:ORDINARIAS?|COMPLEMENTAR(?:ES)?|PROMULGADAS?))?"
                            r"(?: MUNICIPA(?:L|IS))?\.?", cat):
            return None
        lc = "COMPLEMENTAR" in cat
        num = (m["num"] or "").replace(".", "")
        ano = m["ano"]
        if ano and len(ano) == 2:
            ano = "20" + ano
        x = {"tipo": "lei", "lc": lc, "num": int(num) if num.isdigit() and int(num) > 0 else None,
             "ano": int(ano) if ano and 1950 <= int(ano) <= 2100 else None, "data": None, "prova": False,
             "promulgada": "PROMULGAD" in cat}
        return x

    REVER_DIAS = 45      # numa leitura nova, as leis com data desde 45 dias antes da última leitura (o resto fica do cache)

    def _url(self, pagina: int = 0, de: str | None = None) -> str:
        de = de or self.desde
        fim = f"{self.hoje[8:10]}/{self.hoje[5:7]}/{self.hoje[:4]}"
        ini = f"{de[8:10]}/{de[5:7]}/{de[:4]}"
        q = f"?dtini={ini}&dtfim={fim}" + (f"&pagina={pagina}" if pagina else "")
        return f"{self.chave}/leis.php{q}"

    def url_lista(self, ini: str | None = None, fim: str | None = None) -> str:
        """A lista que uma pessoa abre: as leis do período (de ini a fim), da mais nova para a mais antiga."""
        if not ini:
            return self._url(0)
        fim = fim or self.hoje
        return f"{self.chave}/leis.php?dtini={ini[8:10]}/{ini[5:7]}/{ini[:4]}&dtfim={fim[8:10]}/{fim[5:7]}/{fim[:4]}"

    def ler_listas(self) -> dict | None:
        # já lida inteira antes (mesmo período): só as leis dos últimos dias, juntando com as que já estavam no cache
        leis, de = {}, self.desde
        cheio = self.ler_cheio()
        if not cheio:
            de = max(self.desde, (date.fromisoformat(self.d["lido"]) - timedelta(days=self.REVER_DIAS)).isoformat())
            leis = {k: v for k, v in (self.d.get("lei") or {}).items() if v[3] < de}
        for pagina in range(self.MAX_PAGINAS):
            t = self._baixar(self._url(pagina, de))
            if t is None:
                return None
            # toda página da lista tem o formulário de filtro ou os cartões das leis; senão é erro ou página de bloqueio
            if "card-clean" not in t and 'name="cat"' not in t:
                self.erro = "página sem a lista de leis"
                return None
            cards = re.findall(r"(?s)<a class='card-clean' href='([^']+)'>.*?card-clean__title'>(.*?)</strong>.*?</i>\s*"
                               r"([0-9]{2}/[0-9]{2}/[0-9]{4})", t)
            for href, tit, dt in cards:
                leis[href] = [_limpa(tit), "", "", _iso(dt)]
            if len(cards) < 30 or f"pagina={pagina + 1}" not in t:
                return {"lei": leis, "veto": {}, "_cheio": cheio}
        self.erro = "páginas demais"
        return None


# ---------------------------------------------------------------------------------------------------- Instar
_SELECT_CAT = re.compile(r'(?s)<select id="form_categoria_simples" name="form_categoria">(.*?)</select>')
_OPCAO = re.compile(r'(?s)<option value="(\d+)"[^>]*>\s*(.*?)\s*</option>')
_CAT_LEI = re.compile(r"^LEIS?(?P<tipo>(?: MUNICIPA(?:L|IS)| ORDINARIAS?| COMPLEMENTAR(?:ES)?| PROMULGADAS?)*)"
                      r"(?:\s*-?\s*(?P<ano>(?:19|20)\d{2}))?$")
_CAT_ORC = re.compile(r"^(?:(?:LDO|LOA|PPA)\s*-\s*)?(?:LEIS? DE DIRETRIZES ORCAMENTARIAS|LEIS? ORCAMENTARIAS? ANUA(?:L|IS)|"
                      r"PLANOS? PLURIANUA(?:L|IS))(?:\s*-?\s*(?P<ano>(?:19|20)\d{2}))?$|^(?:LDO|LOA|PPA)$")
_NUM_INSTAR = re.compile(r"^\s*(?:N\s*[ºo°.]*\s*)?(?P<num>\d{1,3}(?:\.\d{3})+(?!\d)|\d+)(?:\s*[/\-]\s*(?P<ano>(?:19|20)\d{2}|\d{2})(?!\d))?", re.I)


def ordem_categoria(ident: str, v: list) -> tuple:
    """Ordem das categorias de lei nas fontes: a de leis ordinárias primeiro, depois as complementares, as orçamentárias
    e as promulgadas; dentro de cada uma, o ano e o código."""
    import _atos as A
    orc = bool(_CAT_ORC.match(A.norm(v[0])))
    return (bool(v[2]), orc, bool(v[1]), v[3] or 0, int(ident) if str(ident).isdigit() else 0, str(ident))


class InstarCidade(CidadeLista):
    """Sites de prefeituras do fornecedor Instar: a página de legislação (/portal/leis_decretos) lista as normas com
    número, categoria e data (a data da lei), filtradas por categoria e por ano (os filtros vão no próprio endereço), 50
    por página, da mais nova para a mais antiga. As categorias variam de um site para outro ("Lei", "Lei Ordinária",
    "Leis 2025", "LOA - Lei Orçamentária Anual"...): entram as de lei ordinária, complementar e orçamentária; as de lei
    promulgada entram marcadas (não contam como sancionadas); lei orgânica, emenda, projeto de lei, decreto etc. não.
    É a legislação publicada no site oficial da prefeitura, não o Diário. Robots.txt dos sites: /portal/ é liberado."""
    plataforma = "Instar"
    pasta_nome = "instar"
    MAX_PAGINAS = 30     # por categoria (50 leis por página)
    POR_PAGINA = 50
    REVER_DIAS = 45

    @staticmethod
    def base_de(url: str) -> str | None:
        m = re.match(r"(https?://[^/]+)/portal/leis_decretos(?:/|$)", (url or "").strip())
        return m.group(1) if m else None

    @property
    def SITE(self) -> str:
        return self.chave

    def tem_lista(self) -> bool:
        """O formulário do site tem alguma categoria de lei (há sites que só põem decretos e portarias ali)."""
        return bool(self.d.get("cats"))

    @staticmethod
    def categoria(rotulo: str) -> tuple[bool, bool, int | None] | None:
        """(complementar?, promulgada?, ano da categoria) para uma categoria de lei; None para as outras."""
        import _atos as A
        c = A.norm(rotulo)
        m = _CAT_LEI.match(c)
        if m:
            tipo = m.group("tipo") or ""
            return "COMPLEMENTAR" in tipo, "PROMULGAD" in tipo, int(m.group("ano")) if m.group("ano") else None
        m = _CAT_ORC.match(c)
        if m:
            return False, False, int(m.group("ano")) if m.group("ano") else None
        return None

    @classmethod
    def categorias(cls, t: str) -> dict | None:
        """{id: [rótulo, complementar?, promulgada?, ano]} das categorias de lei do formulário; None sem formulário."""
        s = _SELECT_CAT.search(t or "")
        if not s:
            return None
        out = {}
        for ident, rot in _OPCAO.findall(s.group(1)):
            rot = _limpa(rot)
            c = cls.categoria(rot)
            if c:
                out[ident] = [rot, *c]
        return out

    @staticmethod
    def ler_titulo(titulo: str) -> dict | None:
        """O "título" guardado no cache é "<categoria>|<número>|<data da lei>"."""
        rot, num, data = (str(titulo or "").split("|") + ["", "", ""])[:3]
        c = InstarCidade.categoria(rot)
        if not c:
            return None
        lc, prom, _ = c
        m = _NUM_INSTAR.match(num or "")
        num_s = m.group("num").replace(".", "") if m else ""
        ano = None
        if m and m.group("ano"):
            ano = int(m.group("ano")) + (2000 if len(m.group("ano")) == 2 else 0)
            ano = ano if 1950 <= ano <= 2100 else None
        # "Nº 5882025": o número colado com o ano (588/2025)
        if m and "." not in m.group("num") and len(num_s) >= 6 and data[:4].isdigit():
            for a in (int(data[:4]), int(data[:4]) - 1):
                if num_s.endswith(str(a)):
                    num_s, ano = num_s[:-4], ano or a
                    break
        n = int(num_s) if num_s else 0
        return {"tipo": "lei", "lc": lc, "num": n or None, "ano": ano, "data": data or None, "prova": False,
                "promulgada": prom}

    def _url(self, cat: str, pagina: int, ano1: int, ano2: int) -> str:
        u = (f"{self.chave}/portal/leis_decretos/{pagina}/0/0/0/{cat}/0/0/0/0/0/0/0/0/0/0/0/{ano1}/{ano2}/E/"
             "data-decrescente/avancada")
        return u + ("/0" if pagina > 1 else "")

    def _cats_periodo(self, ini: str, fim: str) -> list[tuple[str, list]]:
        a1, a2 = int(ini[:4]), int(fim[:4])
        return [(k, v) for k, v in sorted((self.d.get("cats") or {}).items(), key=lambda z: ordem_categoria(*z))
                if not v[3] or a1 <= v[3] <= a2]

    def url_lista(self, ini: str | None = None, fim: str | None = None) -> str:
        ini, fim = ini or self.desde, fim or self.hoje
        cats = self._cats_periodo(ini, fim)
        if not cats:
            return f"{self.chave}/portal/leis_decretos"
        return self._url(cats[0][0], 1, int(ini[:4]), int(fim[:4]))

    def fontes_lista(self, ini: str, fim: str) -> list[tuple[str, str]]:
        """(categoria, endereço da lista dessa categoria nos anos do período): uma pessoa abre cada uma."""
        return [(v[0], self._url(k, 1, int(ini[:4]), int(fim[:4]))) for k, v in self._cats_periodo(ini, fim)]

    @staticmethod
    def _itens(t: str) -> list[tuple[str, str, str]]:
        out = []
        for b in t.split('<div class="leg_norma_listagem')[1:]:
            # a identidade da norma no site (alguns sites não têm a página de cada norma, só o arquivo para baixar)
            h = (re.search(r'class="leg_id_norma" value="(\d+)"', b) or re.search(r'href="([^"]*/portal/[^"]+)"', b))
            n = re.search(r'leg_numero_norma"><span>([^<]*)</span>', b)
            d = re.search(r"<strong>Data:</strong>\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", b)
            num, data = (_limpa(n.group(1)) if n else ""), (_iso(d.group(1)) if d else "")
            out.append((h.group(1) if h else f"{num}|{data}", num, data))
        return out

    def ler_listas(self) -> dict | None:
        cheio = self.ler_cheio()
        leis, de = {}, self.desde
        if not cheio:
            de = max(self.desde, (date.fromisoformat(self.d["lido"]) - timedelta(days=self.REVER_DIAS)).isoformat())
            leis = {k: v for k, v in (self.d.get("lei") or {}).items() if v[3] < de}
        cats = None if cheio else self.d.get("cats")
        if cats is None:
            t = self._baixar(f"{self.chave}/portal/leis_decretos")
            if t is None:
                return None
            cats = self.categorias(t)
            if cats is None:
                self.erro = "página sem a lista de leis"
                return None
        a1, a2 = int(de[:4]), int(self.hoje[:4])
        fila, feitas = list(cats), set()
        while fila:
            cid = fila.pop(0)
            if cid in feitas:
                continue
            feitas.add(cid)
            rot, lc, prom, ano_cat = cats[cid]
            if ano_cat and not a1 <= ano_cat <= a2:
                continue
            vistos = set()
            for pagina in range(1, self.MAX_PAGINAS + 1):
                t = self._baixar(self._url(cid, pagina, a1, a2))
                if t is None:
                    return None
                # toda página de resultado tem o formulário com as categorias; sem ele, é erro ou página de bloqueio
                cats_pag = self.categorias(t)
                if cats_pag is None:
                    self.erro = "página sem a lista de leis"
                    return None
                # uma categoria nova (ex.: "Leis 2027") aparece no formulário de qualquer página
                for k, v in cats_pag.items():
                    if k not in cats:
                        cats[k] = v
                        fila.append(k)
                itens = self._itens(t)
                parar = False
                for href, num, data in itens:
                    if href in vistos:          # passou da última página: o site mostra a primeira de novo
                        parar = True
                        break
                    vistos.add(href)
                    if data and data < de:      # da mais nova para a mais antiga: daqui para a frente, só antigas
                        parar = True
                        continue
                    leis[href] = [f"{rot}|{num}|{data}", "", "", data]
                if parar or len(itens) < self.POR_PAGINA:
                    break
            else:
                self.erro = "páginas demais"
                return None
        return {"lei": leis, "veto": {}, "cats": cats, "_cheio": cheio}


# ---------------------------------------------------------------------------------------------------- Digitaliza
class DigitalizaCidade(CidadeLista):
    """Sites de prefeituras do fornecedor Digitaliza (quase todos de MG): a página de legislação
    (/legislacoes/todas/Todas as Leis, /legislacoes/<tipo>/<nome>) mostra uma tabela que o próprio site preenche com uma
    lista em JSON (/legislacoes/get/<tipo>, o mesmo pedido que a página faz), com número, ano, tipo e ementa de cada
    norma, filtrável por ano. A lista não traz a data de cada lei: vale o ano do número e, para a lei mais nova, a data em
    que o arquivo dela foi posto no site. Robots.txt dos sites: tudo liberado."""
    plataforma = "Digitaliza"
    pasta_nome = "digitaliza"
    POR_PAGINA = 200
    MAX_PAGINAS = 10     # por tipo e ano
    REVER_DIAS = 45

    @staticmethod
    def base_de(url: str) -> str | None:
        m = re.match(r"(https?://[^/]+)/legislacoes/(?:todas|\d+)(?:/|$)", (url or "").strip())
        return m.group(1) if m else None

    @property
    def SITE(self) -> str:
        return self.chave

    def tem_lista(self) -> bool:
        return bool(self.d.get("tipos"))

    @staticmethod
    def tipos_de(t: str) -> dict:
        """{id: [rótulo, complementar?, promulgada?, ano]} dos tipos de lei nos links do menu de legislação."""
        import urllib.parse
        out = {}
        for ident, nome in re.findall(r'href="[^"]*/legislacoes/(\d+)/([^"/?#]+)"', t or ""):
            rot = _limpa(urllib.parse.unquote(nome))
            c = InstarCidade.categoria(rot)
            if c:
                out[ident] = [rot, *c]
        return out

    def _url_api(self, tipo: str, ano: int | None, inicio: int = 0) -> str:
        import urllib.parse
        q = {"draw": "1", "start": str(inicio), "length": str(self.POR_PAGINA)}
        if ano:
            q.update({"columns[1][data]": "ano", "columns[1][searchable]": "true", "columns[1][search][value]": str(ano)})
        return f"{self.chave}/legislacoes/get/{tipo}?{urllib.parse.urlencode(q)}"

    def url_lista(self, ini: str | None = None, fim: str | None = None) -> str:
        return f"{self.chave}/legislacoes/todas/Todas%20as%20Leis"

    def fontes_lista(self, ini: str, fim: str) -> list[tuple[str, str]]:
        """(tipo, página do tipo no site): a tabela de cada tipo, com o filtro por ano na própria página."""
        import urllib.parse
        tipos = sorted((self.d.get("tipos") or {}).items(), key=lambda z: ordem_categoria(*z))
        return [(v[0], f"{self.chave}/legislacoes/{k}/{urllib.parse.quote(v[0])}") for k, v in tipos
                if not v[3] or int(ini[:4]) <= v[3] <= int(fim[:4])]

    @staticmethod
    def ler_titulo(titulo: str) -> dict | None:
        """O "título" guardado no cache é "<tipo>|<número>|<ano>"."""
        rot, num, ano = (str(titulo or "").split("|") + ["", "", ""])[:3]
        c = InstarCidade.categoria(rot)
        if not c:
            return None
        m = re.match(r"^\s*(\d{1,3}(?:\.\d{3})+(?!\d)|\d+)", num or "")
        n = int(m.group(1).replace(".", "")) if m else 0
        a = int(ano) if ano.isdigit() and 1950 <= int(ano) <= 2100 else None
        return {"tipo": "lei", "lc": c[0], "num": n or None, "ano": a, "data": None, "prova": False, "promulgada": c[1]}

    def ler_listas(self) -> dict | None:
        cheio = self.ler_cheio()
        leis, a1 = {}, int(self.desde[:4])
        if not cheio:
            # os anos desde 45 dias antes da última leitura são relidos inteiros; os anteriores ficam do cache
            a1 = max(a1, (date.fromisoformat(self.d["lido"]) - timedelta(days=self.REVER_DIAS)).year)
            leis = {k: v for k, v in (self.d.get("lei") or {}).items() if v[0].rsplit("|", 1)[-1] < str(a1)}
        tipos = None if cheio else self.d.get("tipos")
        if tipos is None:
            t = self._baixar(f"{self.chave}/legislacoes/todas/Todas%20as%20Leis")
            if t is None:
                return None
            if "/legislacoes/get/" not in t:
                self.erro = "página sem a lista de leis"
                return None
            tipos = self.tipos_de(t)
        import _atos as A
        a2 = int(self.hoje[:4])
        for tipo, (rot, lc, prom, ano_cat) in sorted(tipos.items()):
            # as leis ordinárias, ano a ano (filtro da própria tabela); complementares e orçamentárias (poucas), de uma vez
            por_ano = not (lc or _CAT_ORC.match(A.norm(rot)))
            for ano in (range(a1, a2 + 1) if por_ano else [None]):
                if ano and ano_cat and ano_cat != ano:
                    continue
                inicio = 0
                for _ in range(self.MAX_PAGINAS):
                    r = self.rede.pagina(self._url_api(tipo, ano, inicio),
                                         aceitar="application/json, text/javascript, */*; q=0.01",
                                         extra={"X-Requested-With": "XMLHttpRequest"})
                    self.pedidos += 1
                    if not r.ok or not r.corpo:
                        self.erro = r.erro or f"http {r.status}"
                        return None
                    try:
                        j = json.loads(r.corpo.decode(r.charset or "utf-8", "replace"))
                    except ValueError:
                        self.erro = "resposta não é JSON"
                        return None
                    # a resposta da tabela tem "data" (a lista) e o total; outra coisa (erro, bloqueio) não vale
                    if not isinstance(j, dict) or not isinstance(j.get("data"), list) or not (
                            str(j.get("recordsFiltered", j.get("recordsTotal", ""))).isdigit()):
                        self.erro = "resposta sem a lista de leis"
                        return None
                    dados = j["data"]
                    total = int(j.get("recordsFiltered", j.get("recordsTotal")))
                    if not dados and inicio < total:
                        self.erro = "página da lista vazia antes do fim"
                        return None
                    for x in dados:
                        xa = str(x.get("ano") or "")
                        if (ano and xa != str(ano)) or (not ano and not (xa.isdigit() and a1 <= int(xa) <= a2)):
                            continue
                        circ = str((x.get("arquivo") or {}).get("created_at") or "")[:10]
                        leis[str(x.get("id"))] = [f"{rot}|{x.get('numero') or ''}|{x.get('ano') or ''}", "", "", circ]
                    # pelo total (o site pode mandar menos linhas por página do que o pedido)
                    inicio += len(dados)
                    if inicio >= total:
                        break
                else:
                    self.erro = "páginas demais"
                    return None
        return {"lei": leis, "veto": {}, "tipos": tipos, "_cheio": cheio}
