"""Cliente educado para os sistemas ScriptCase (grades com pesquisa refinada, paginação por AJAX e janelas de detalhe), como
o sistema legislativo da Câmara de Salvador (cmsalvador.sys.inf.br). Uma sessão com cookie, como um navegador; robots.txt
(Disallow e Crawl-delay) e intervalo entre pedidos pelo _base; User-Agent do projeto.
Arquivos que começam com "_" não são coletores (scripts/legislativos.py pula)."""
from __future__ import annotations

import html
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from comum import UA

from . import _base as B


class Sessao:
    def __init__(self, app: str, pausa: float = 2.0):
        self.app = app.rstrip("/") + "/"
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.pausa = pausa
        self.n = 0
        self.init: str | None = None

    def pedir(self, url: str, dados: str | None = None, tentativas: int = 3) -> str:
        erro = None
        for t in range(tentativas):
            B.esperar_vez(url, self.pausa, UA)
            try:
                h = {"User-Agent": UA}
                if dados is not None:
                    h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                    h["X-Requested-With"] = "XMLHttpRequest"
                req = urllib.request.Request(url, data=dados.encode("utf-8") if dados is not None else None, headers=h)
                with self.op.open(req, timeout=180) as r:
                    b = r.read()
                self.n += 1
                return b.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                self.n += 1
                erro = e
                if e.code in (400, 401, 403, 404, 410):
                    break
            except Exception as e:  # rede instável
                self.n += 1
                erro = e
            finally:
                B.pedido_feito(url)
            time.sleep(min(30, 5 * (t + 1)))
        raise RuntimeError(f"{url}: {erro}")

    def abrir(self) -> str:
        t = self.pedir(self.app)
        m = re.search(r'name="script_case_init" value="(\d+)"', t)
        if not m:
            raise RuntimeError(f"{self.app}: a página mudou (sem script_case_init)")
        self.init = m.group(1)
        return t

    def nav(self, opc: str, parm: str) -> dict:
        """Uma ação da grade (pesquisa refinada, linhas por página, página): o JSON que a grade devolve."""
        p = parm.replace("+", "__NM_PLUS__").replace("&", "__NM_AMP__").replace("%", "__NM_PRC__")
        dados = ("nmgp_opcao=ajax_navigate&script_case_init=" + (self.init or "") + "&opc=" + urllib.parse.quote(opc)
                 + "&parm=" + urllib.parse.quote(p, safe=""))
        t = self.pedir(self.app + "index.php", dados).strip()
        if not t.startswith("{"):
            raise RuntimeError(f"{self.app}: resposta fora do formato ({t[:80]!r})")
        d = json.loads(t)
        if d.get("ss_time_out"):
            raise RuntimeError(f"{self.app}: a sessão expirou")
        return d


def campo_html(d: dict, campo: str) -> str:
    return next((v["value"] for v in d.get("setValue") or [] if v.get("field") == campo), "")


def total(d_ou_html) -> tuple[int, int, int] | None:
    """(primeiro, último, total) do rodapé "[1 a 50 de 581]"."""
    t = d_ou_html if isinstance(d_ou_html, str) else " ".join(v.get("value") or "" for v in d_ou_html.get("setValue") or [])
    m = re.search(r"\[\s*(\d+)\s*a\s*(\d+)\s*de\s*(\d+)\s*\]", re.sub(r"<[^>]+>", " ", t))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def linhas(h: str) -> list[str]:
    return re.findall(r'<TR\s+class="scGridField(?:Odd|Even)".*?(?=<TR\s+class="scGridField(?:Odd|Even)"|$)', h, re.S)


def valor(linha: str, campo: str) -> str:
    """Texto de um campo da linha da grade (span id="id_sc_field_<campo>_<n>"), sem o rótulo."""
    m = re.search(r'<span id="id_sc_field_%s_\d+">(.*?)</span>\s*</TD>' % re.escape(campo), linha, re.S)
    if not m:
        return ""
    v = re.sub(r'<span class="scGridLabel[^"]*"[^>]*>.*?</span>', "", m.group(1), flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", v))).strip()
