"""CESPRO (cespro.com.br, "Portais de Legislação"): a legislação consolidada de ~140 municípios (quase todos do RS), com
busca por tipo de norma e por ano (fase 4: o que cada prefeitura fez).

A página que uma pessoa abre (pesquisaLegislacao.php?cdMunicipio=<código>&cdTipo=<tipo>&AnoInicio=&AnoFinal=...) busca
os resultados no próprio site com um pedido POST (_data/api.php?<os mesmos filtros>&operacao=content-pesquisa, corpo
{"ID": <código>}): 50 normas por página, da mais nova para a mais antiga, com o título "LEI MUNICIPAL Nº 2.659, DE
06/10/2026". Os tipos de norma (com o código de cada um) vêm da mesma busca sem filtros. Robots.txt: só /cgi-bin/ e
/wusage fechados. É a legislação publicada pelo portal oficial do município, não o Diário.

A rede educada (_rede.py) só faz GET: post_json() abaixo faz o POST com as mesmas regras (robots.txt e Crawl-delay,
pausa entre pedidos ao mesmo site, um pedido por vez ao servidor, disjuntor do servidor).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import _rede
from _diario_listas import CidadeLista, _limpa

API = "https://cespro.com.br/_data/api.php"
SITE = "https://cespro.com.br"
POR_PAGINA = 50


def post_json(rede: _rede.Rede, url: str, corpo: dict) -> _rede.Resposta:
    """Um POST com corpo JSON, com as regras da rede educada (sem seguir redirecionamentos)."""
    r = _rede.Resposta(url=url, final=url)
    pode, atraso = rede.robots(url)
    if not pode:
        r.erro = "robots"
        return r
    host = _rede.host_de(url)
    ip = rede.ip(host)
    if not ip:
        r.erro = "dns"
        return r
    if ip in rede.suspensos:
        r.erro = "suspenso"
        return r
    rede._esperar_vez(host, atraso)
    rede._esperar_ip(ip)
    hdr = {"User-Agent": _rede.UA, "Accept": "application/json, text/plain, */*", "Accept-Encoding": "gzip, deflate",
           "Accept-Language": "pt-BR,pt;q=0.9", "Content-Type": "application/json"}
    with rede._sem_ip[ip]:
        with rede._lock:
            rede.pedidos += 1
        inicio = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers=hdr, method="POST")
            with _rede._OPENERS["seguro"].open(req, timeout=_rede.TIMEOUT) as resp:
                r.status = resp.status
                r.tipo = resp.headers.get("Content-Type") or ""
                r.charset = resp.headers.get_content_charset()
                partes, n = [], 0
                while True:
                    bloco = resp.read(65536)
                    if not bloco:
                        break
                    partes.append(bloco)
                    n += len(bloco)
                    if n >= _rede.MAX_BYTES or time.time() - inicio > _rede.TOTAL:
                        r.cortado = True
                        break
                r.corpo = _rede._descomprimir(b"".join(partes), (resp.headers.get("Content-Encoding") or "").lower())
        except urllib.error.HTTPError as e:
            r.status, r.erro = e.code, f"http {e.code}"
        except Exception as e:  # noqa: BLE001 (tempo esgotado, conexão cortada...)
            r.erro = "timeout" if "timed out" in str(e).lower() else "conexao"
    rede._anotar(ip, r)
    return r


class CesproCidade(CidadeLista):
    """Um município no CESPRO (chave = o código do município no CESPRO)."""
    plataforma = "CESPRO"
    pasta_nome = "cespro"
    SITE = SITE
    MAX_PAGINAS = 30     # por tipo de norma (50 por página)
    REVER_DIAS = 45

    @staticmethod
    def codigo_de(url: str) -> str | None:
        """A chave do município: o código no endereço do CESPRO (…cespro.com.br/…?cdMunicipio=2602…) ou, quando o link é
        o endereço próprio do município (https://<cidade>.cespro.com.br/), esse endereço (o código sai da página, uma vez)."""
        if "cespro.com.br" not in (url or ""):
            return None
        m = re.search(r"[?&]cdMunicipio=(\d+)", url)
        if m:
            return m.group(1) if m.group(1) != "0" else None
        m = re.match(r"https?://((?:www\.)?[a-z0-9-]+\.cespro\.com\.br)/?$", url.strip().lower())
        return f"https://{m.group(1)}" if m else None

    @property
    def cod(self) -> str | None:
        return self.chave if self.chave.isdigit() else self.d.get("codigo")

    def _resolver_codigo(self) -> str | None:
        t = self._baixar(self.chave + "/")
        if t is None:
            return None
        cods = set(re.findall(r"cdMunicipio=(\d+)", t)) - {"0"}
        if len(cods) != 1:
            self.erro = "código do município não achado na página"
            return None
        return cods.pop()

    @staticmethod
    def tipo_lei(rotulo: str) -> tuple[bool, bool] | None:
        """(complementar?, promulgada?) para um tipo de norma que é lei; None para os outros."""
        from _diario_listas import InstarCidade
        c = InstarCidade.categoria(rotulo)
        return (c[0], c[1]) if c and not c[2] else None

    def tem_lista(self) -> bool:
        return bool(self.d.get("tipos"))

    def _filtros(self, tipo: str, ano1: int, ano2: int, pagina: int = 0) -> str:
        q = {"cdMunicipio": self.cod, "LocalPesquisa": "Ementa", "cdTipo": tipo, "dsStatus": "Todos",
             "AnoInicio": str(ano1), "AnoFinal": str(ano2), "Word": "", "Submit": "Pesquisar"}
        if pagina > 1:
            q["nPage"] = str(pagina)
        return urllib.parse.urlencode(q)

    def _api(self, filtros: str | None) -> dict | None:
        url = f"{API}?{(filtros + '&') if filtros else 'cdMunicipio=' + self.cod + '&'}operacao=content-pesquisa"
        r = post_json(self.rede, url, {"ID": int(self.cod), "lmdp": 0})
        self.pedidos += 1
        if not r.ok or not r.corpo:
            self.erro = r.erro or f"http {r.status}"
            return None
        try:
            j = json.loads(r.corpo.decode("utf-8-sig", "replace"))
        except ValueError:
            self.erro = "resposta não é JSON"
            return None
        if not isinstance(j, dict):
            self.erro = "resposta sem a lista de leis"
            return None
        return j

    def url_lista(self, ini: str | None = None, fim: str | None = None) -> str:
        ini, fim = ini or self.desde, fim or self.hoje
        tipos = sorted(self.d.get("tipos") or {}, key=lambda k: (self.d["tipos"][k][1], k))
        if not tipos:
            return f"{SITE}/pesquisaLegislacao.php?cdMunicipio={self.cod}"
        return f"{SITE}/pesquisaLegislacao.php?{self._filtros(tipos[0], int(ini[:4]), int(fim[:4]))}"

    def fontes_lista(self, ini: str, fim: str) -> list[tuple[str, str]]:
        """(tipo de norma, endereço da busca desse tipo nos anos do período): uma pessoa abre cada uma."""
        tipos = sorted((self.d.get("tipos") or {}).items(), key=lambda z: (z[1][1], z[0]))
        return [(v[0], f"{SITE}/pesquisaLegislacao.php?{self._filtros(k, int(ini[:4]), int(fim[:4]))}")
                for k, v in tipos]

    def ler_listas(self) -> dict | None:
        if not self.cod:
            cod = self._resolver_codigo()
            if not cod:
                return None
            self.d["codigo"] = cod
        cheio = self.ler_cheio()
        leis, de = {}, self.desde
        if not cheio:
            de = max(self.desde, (date.fromisoformat(self.d["lido"]) - timedelta(days=self.REVER_DIAS)).isoformat())
            leis = {k: v for k, v in (self.d.get("lei") or {}).items() if v[3] < de}
        tipos = None if cheio else self.d.get("tipos")
        if tipos is None:
            j = self._api(None)
            if j is None:
                return None
            if "dados_tipo_diplomas" not in j:
                self.erro = "resposta sem os tipos de norma"
                return None
            tipos = {}
            for t in j.get("dados_tipo_diplomas") or []:
                rot = _limpa(t.get("ds_municipio_tipo_diploma"))
                c = self.tipo_lei(rot)
                if c:
                    tipos[str(t.get("cd_municipio_tipo_diploma"))] = [rot, *c]
        import _atos as A
        a1, a2 = int(de[:4]), int(self.hoje[:4])
        for tipo, (rot, lc, prom) in sorted(tipos.items()):
            vistos = set()
            for pagina in range(1, self.MAX_PAGINAS + 1):
                j = self._api(self._filtros(tipo, a1, a2, pagina))
                if j is None:
                    return None
                # a resposta da busca sempre traz a lista (vazia, se não há normas); sem ela, é erro ou bloqueio
                if "dados_legislacao_resultado_pesquisa_json" not in j:
                    self.erro = "resposta sem a lista de leis"
                    return None
                res = j.get("dados_legislacao_resultado_pesquisa_json") or {}
                itens = list(res.values()) if isinstance(res, dict) else list(res or [])
                parar = False
                for x in itens:
                    ident = str(x.get("id") or x.get("ds_link") or "")
                    if not ident or ident in vistos:
                        parar = True
                        break
                    vistos.add(ident)
                    tit = _limpa(x.get("ds_title"))
                    lei = A.ler_titulo(tit) or {}
                    data = lei.get("data") or ""
                    if data and data < de:
                        parar = True
                        continue
                    # o tipo da norma vem do filtro (o título às vezes diz só "LEI Nº")
                    leis[f"{tipo}|{ident}"] = [f"{rot}|{tit}", "", "", data]
                m = re.search(r"em\s*(?:<[^>]+>)*\s*(\d+)\s*(?:<[^>]+>)*\s*p[áa]gina", j.get("dados_paginacao_resultado_new")
                              or j.get("dados_paginacao_resultado") or "")
                total_pags = int(m.group(1)) if m else None
                if parar:
                    break
                if total_pags is not None:
                    if pagina >= total_pags:
                        break
                    if len(itens) < POR_PAGINA:     # página do meio com menos normas: resposta cortada
                        self.erro = "página da busca incompleta"
                        return None
                elif len(itens) < POR_PAGINA:
                    break
            else:
                self.erro = "páginas demais"
                return None
        return {"lei": leis, "veto": {}, "tipos": tipos, "codigo": self.cod, "_cheio": cheio}

    @staticmethod
    def ler_titulo(titulo: str) -> dict | None:
        """O "título" guardado no cache é "<tipo de norma>|<título da norma no CESPRO>"."""
        import _atos as A
        rot, _, tit = str(titulo or "").partition("|")
        c = CesproCidade.tipo_lei(rot)
        if not c:
            return None
        lei = A.ler_titulo(tit)
        if not lei or lei.get("tipo") != "lei":
            # o título não começa por "LEI" (ex.: só o número): o número e a data do jeito que der
            lei = A.ler_titulo_lista(tit) or {"tipo": "lei", "num": None, "ano": None, "data": None, "prova": False}
        lei = dict(lei, tipo="lei", lc=c[0] or bool(lei.get("lc")), promulgada=c[1] or bool(lei.get("promulgada")))
        return lei


__all__ = ["CesproCidade", "post_json"]
