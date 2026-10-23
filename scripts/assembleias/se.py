"""Assembleia Legislativa do Estado de Sergipe (Alese): portal legislativo (SPL) com API pública
(https://aleselegis.al.se.leg.br/api/publico/, documentada em https://aleselegis.al.se.leg.br/spl/dados-abertos.aspx).

Lista: parlamentares da legislatura atual com situação "Ativo" (24; quem saiu aparece como "Deputados que não encerraram
o mandato"). Propostas: projetos de lei (PL), de lei complementar (PLC), de emenda constitucional (PEC), de decreto
legislativo (PDL) e de resolução (PR) desde 1º/2/2023, com autor, coautores, situação e tramitações.
"Virou lei": a situação da API para em "Aprovado"; a lei que o projeto virou vem do módulo de Legislação da Alese
(consulta por autor: cada lei tem o link para o projeto de origem), lido aos poucos (cada autor a cada 7 dias).
"""
from __future__ import annotations

import datetime as dt
import html
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request

from comum import UA, data_iso, hoje, log

from ._ne_comum import nome_lei
from ._ne_nopaper import NoPaper, texto_tramitacoes, ultima

BASE = "https://aleselegis.al.se.leg.br"
LEIS_DIAS = 7

# situação + últimas tramitações (sem acento, minúsculas) -> status do site. Na Alese a situação da API só tem
# "Tramitando", "Aprovado", "Retirado" e "Arquivado"; "Aprovado" = aprovado no Plenário (o processo depois é arquivado).
REGRAS = [
    (r"veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"^retirad", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"^aprovad", "aprovada", "Aprovada no Plenário; ainda não aparece como lei no portal da Alese",
     "Approved by the full Assembly; it does not appear as a law on the Alese website yet"),
    (r"^arquivad", "arquivada", "Arquivada", None),
    (r"^tramitando", "andando", None, None),
]


def _itens(t: str) -> list[dict]:
    out = []
    for blk in t.split('class="kt-widget5__item')[1:]:
        m = re.search(r'norma\.aspx\?id=(\d+)[^"]*"\s+class="kt-widget5__title">\s*(.*?)\s*n[°º]\s*([\d.]+)/(\d{4})', blk, re.S)
        if not m:
            continue
        d = re.search(r'<span class="kt-font-info">(\d{2}/\d{2}/\d{4})</span>', blk)
        orig = re.search(r"href='/spl/processo\.aspx\?id=(\d+)'", blk)
        out.append({"id": m.group(1), "tipo": re.sub(r"\s+", " ", html.unescape(m.group(2))).strip(), "n": m.group(3).replace(".", ""),
                    "a": m.group(4), "d": data_iso(d.group(1)) if d else None, "orig": orig.group(1) if orig else None})
    return out


def _campos(t: str) -> dict:
    c = {}
    for m in re.finditer(r'<input[^>]+type="hidden"[^>]*>', t):
        n = re.search(r'name="([^"]+)"', m.group(0))
        v = re.search(r'value="([^"]*)"', m.group(0))
        if n:
            c[n.group(1)] = html.unescape(v.group(1)) if v else ""
    return c


def leis_do_autor(autor: int, pausa: float = 0.8) -> list[dict]:
    """Leis de um autor desde 2023 (consulta por autor do módulo de Legislação; as páginas seguintes vêm por "postback"
    do ASP.NET, como no navegador)."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    url = f"{BASE}/legislacao/consulta-legislacao.aspx?autor={autor}"
    t = op.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120).read().decode("utf-8", "replace")
    out, pagina = [], 1
    while True:
        itens = _itens(t)
        out += itens
        if not itens or min(i["a"] for i in itens) < "2023":
            break
        alvos = re.findall(r"__doPostBack\(&#39;(ctl00\$ContentPlaceHolder1\$rptPaging\$ctl(\d+)\$lbPaging)&#39;", t)
        seguinte = next((a for a, k in alvos if int(k) == pagina), None)  # ctl01 = página 2
        if not seguinte:
            nx = re.search(r"__doPostBack\(&#39;(ctl00\$ContentPlaceHolder1\$lbNext)&#39;", t)
            seguinte = nx.group(1) if nx else None
        if not seguinte or pagina > 60:
            break
        campos = _campos(t)
        campos["__EVENTTARGET"], campos["__EVENTARGUMENT"] = seguinte, ""
        time.sleep(pausa)
        req = urllib.request.Request(url, data=urllib.parse.urlencode(campos).encode(),
                                     headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
        t = op.open(req, timeout=120).read().decode("utf-8", "replace")
        pagina += 1
    return [i for i in out if i["a"] >= "2023"]


class Alese(NoPaper):
    _leis: dict = {}

    def coletar(self) -> dict:
        self._leis = self.leis()
        return super().coletar()

    def leis(self) -> dict[str, dict]:
        """{id da proposição de origem: lei}, para os autores de hoje (cache em .cache/alese/leis.json)."""
        est = self.rede.estado("leis.json", {}) or {}
        h = dt.date.fromisoformat(hoje())
        autores = [int(p["autorID"]) for p in self.pessoas() if p.get("autorID")]
        fila = sorted(autores, key=lambda a: (est.get(str(a)) or {}).get("lido") or "")
        t0 = time.time()
        for a in fila:
            x = est.get(str(a))
            if x and (h - dt.date.fromisoformat(x["lido"])).days < LEIS_DIAS:
                continue
            if time.time() - t0 > 60 and x:
                break
            try:
                est[str(a)] = {"lido": hoje(), "itens": leis_do_autor(a)}
            except Exception as e:
                log(f"  SE: leis do autor {a} falharam ({e})")
            self.rede.guardar(est, "leis.json")
        out = {}
        for x in est.values():
            for i in x.get("itens") or []:
                if i.get("orig"):
                    out[i["orig"]] = i
        log(f"  SE: {len(out)} leis ligadas ao projeto de origem")
        return out

    def situacao_lei(self, pid: str) -> dict | None:
        i = self._leis.get(pid)
        if not i:
            return None
        t = i["tipo"].lower()
        nome = ("Lei Complementar" if "complementar" in t else "Emenda Constitucional" if "emenda" in t else
                "Decreto Legislativo" if "decreto" in t else "Resolução" if "resolu" in t else "Lei")
        nl = nome_lei(nome, i["n"], i["a"])
        return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None, "data": i["d"],
                "lei": {"nome": nl, "url": f"{BASE}/legislacao/norma.aspx?id={i['id']}"}}


COLETOR: Alese | None = None


def situacao(v: dict) -> dict:
    lei = COLETOR.situacao_lei(str(v.get("_id") or "")) if COLETOR else None
    if lei:
        return lei
    t = texto_tramitacoes(v)
    sit = (v.get("sit") or "")
    data = (ultima(v)[0] or "")[:10] or None
    for exp, st, pt, en in REGRAS:
        alvo = re.sub(r"[^a-z ]", "", sit.lower()) if exp.startswith("^") else t
        if re.search(exp, alvo):
            if exp == "^aprovad" and v.get("tid") in APROVADA_SEM_NORMA:
                pt, en = APROVADA_SEM_NORMA[v["tid"]]
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


# aprovada no Plenário sem norma achada no módulo de Legislação (que ainda não traz as resoluções e os decretos
# legislativos depois de 2022)
APROVADA_SEM_NORMA = {
    6: ("Aprovada no Plenário; o número da resolução não aparece no portal da Alese",
        "Approved by the full Assembly; the resolution number does not appear on the Alese website"),
    3: ("Aprovada no Plenário; o número do decreto legislativo não aparece no portal da Alese",
        "Approved by the full Assembly; the legislative decree number does not appear on the Alese website"),
    7: ("Aprovada no Plenário; o número da emenda à Constituição não aparece no portal da Alese",
        "Approved by the full Assembly; the constitutional amendment number does not appear on the Alese website"),
}


def coletar() -> dict:
    global COLETOR
    COLETOR = Alese(
        uf="SE", base=BASE, casa="Assembleia Legislativa do Estado de Sergipe",
        casa_en="Legislative Assembly of the State of Sergipe", sigla="Alese", site="https://al.se.leg.br",
        veiculo="Assembleia Legislativa de Sergipe (Alese)", prefixo="alese", pasta="alese",
        tipos={5: "PL", 4: "PLP", 7: "PEC", 3: "PDL", 6: "PRC"}, situacao=situacao, qtd_pessoas=30,
        tse_manual=TSE_MANUAL,
    )
    return COLETOR.coletar()


# conferidos à mão (id do parlamentar na Alese -> candidato do TSE de 2022): "Luizão Donatrampi" é LUIZAO DONA TRAMPI
# (José Luiz da Mota Cruz); "Carminha Paiva" é CARMINHA (Maria do Carmo Paiva da Silva).
TSE_MANUAL = {"569": "260001646927", "563": "260001618237"}
