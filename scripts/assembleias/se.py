"""Assembleia Legislativa do Estado de Sergipe (Alese): portal legislativo (SPL) com API pública
(https://aleselegis.al.se.leg.br/api/publico/, documentada em https://aleselegis.al.se.leg.br/spl/dados-abertos.aspx).

Lista: parlamentares da legislatura atual com situação "Ativo" (24; quem saiu aparece como "Deputados que não encerraram
o mandato"). Propostas: projetos de lei (PL), de lei complementar (PLC), de emenda constitucional (PEC), de decreto
legislativo (PDL) e de resolução (PR) desde 1º/2/2023, com autor, coautores, situação e tramitações.
"Virou lei": a situação da API para em "Aprovado"; a lei que o projeto virou vem do módulo de Legislação da Alese
(consulta por autor: cada lei tem o link para o projeto de origem), lido aos poucos (cada autor a cada 7 dias).
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request

import regional
from comum import UA, data_iso, fonte, hoje, log, sem_acento

from . import _ne_gov as gv
from ._carga import SemTempo
from ._ne_comum import com_status_en, feito, nome_lei, vez
from ._ne_nopaper import NoPaper, texto_tramitacoes, ultima

BASE = "https://aleselegis.al.se.leg.br"
LEIS_DIAS = 7
AUTOR_EXECUTIVO = 83  # "Poder Executivo" como autor interno (até 2024; depois, autor externo "Poder Executivo")
TIPO_VETO = 10  # "Veto Governamental" (VET)

# situação + últimas tramitações (sem acento, minúsculas) -> status do site. Na Alese a situação da API só tem
# "Tramitando", "Aprovado", "Retirado" e "Arquivado"; "Aprovado" = aprovado no Plenário (o processo depois é arquivado).
REGRAS = [
    (r"veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"^retirad", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"^aprovad", "aprovada", "Aprovada no Plenário; o portal da Alese não mostra lei ligada a ela",
     "Approved by the full Assembly; the Alese website shows no law linked to it"),
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
        e = re.search(r'class="kt-widget5__desc">\s*(.*?)\s*</a>', blk, re.S)
        out.append({"id": m.group(1), "tipo": re.sub(r"\s+", " ", html.unescape(m.group(2))).strip(), "n": m.group(3).replace(".", ""),
                    "a": m.group(4), "d": data_iso(d.group(1)) if d else None, "orig": orig.group(1) if orig else None,
                    "e": re.sub(r"\s+", " ", html.unescape(e.group(1))).strip()[:400] if e else None})
    return out


def _chave_ementa(e: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sem_acento((e or "").lower())).strip()


def _campos(t: str) -> dict:
    c = {}
    for m in re.finditer(r'<input[^>]+type="hidden"[^>]*>', t):
        n = re.search(r'name="([^"]+)"', m.group(0))
        v = re.search(r'value="([^"]*)"', m.group(0))
        if n:
            c[n.group(1)] = html.unescape(v.group(1)) if v else ""
    return c


def _abrir(op, url: str, dados: dict | None = None, pausa: float = 0.8, timeout: int = 180) -> str:
    """Um pedido ao portal (GET, ou POST do ASP.NET com os campos do formulário), respeitando o robots.txt e o intervalo
    entre pedidos (vez/feito de _ne_comum)."""
    if dados is None:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(),
                                     headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    iv = vez(url, pausa)
    try:
        return op.open(req, timeout=timeout).read().decode("utf-8", "replace")
    finally:
        feito(url, iv)


def leis_do_autor(autor: int, pausa: float = 0.8) -> list[dict]:
    """Leis de um autor desde 2023 (consulta por autor do módulo de Legislação; as páginas seguintes vêm por "postback"
    do ASP.NET, como no navegador)."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    url = f"{BASE}/legislacao/consulta-legislacao.aspx?autor={autor}"
    t = _abrir(op, url, None, pausa, 120)
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
        t = _abrir(op, url, campos, pausa, 120)
        pagina += 1
    return [i for i in out if i["a"] >= "2023"]


def _postback(op, url: str, t: str, alvo: str, extra: dict | None = None, pausa: float = 0.8) -> str:
    campos = _campos(t)
    campos["__EVENTTARGET"], campos["__EVENTARGUMENT"] = alvo, ""
    campos.update(extra or {})
    return _abrir(op, url, campos, pausa)


def lista_100(url: str, itens_de, pausa: float = 0.8, max_paginas: int = 40) -> list:
    """Uma consulta do portal (legislação ou proposições) com 100 itens por página, página por página (postback do ASP.NET)."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    t = _abrir(op, url, None, pausa)
    dd = "ctl00$ContentPlaceHolder1$ddl_ItensExibidos"
    if dd in t:
        t = _postback(op, url, t, dd, {dd: "100"}, pausa)
    out, pagina, vistos = [], 1, set()
    while True:
        novos = [i for i in itens_de(t) if repr(i) not in vistos]
        if not novos:
            break
        vistos.update(repr(i) for i in novos)
        out += novos
        alvos = re.findall(r"__doPostBack\(&#39;(ctl00\$ContentPlaceHolder1\$rptPaging\$ctl(\d+)\$lbPaging)&#39;", t)
        seguinte = next((a for a, k in alvos if int(k) == pagina), None)
        if not seguinte:
            nx = re.search(r"__doPostBack\(&#39;(ctl00\$ContentPlaceHolder1\$lbNext)&#39;", t)
            seguinte = nx.group(1) if nx and pagina < max_paginas else None
        if not seguinte:
            break
        t = _postback(op, url, t, seguinte, {dd: "100"}, pausa)
        pagina += 1
    return out


def _ids_processos(t: str) -> list[str]:
    out = []
    for blk in t.split('class="kt-widget5__item')[1:]:
        m = re.search(r"processo\.aspx\?id=(\d+)", blk)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _texto_lei(b: bytes) -> str:
    """As páginas de texto das leis da Alese são exportações do Word, às vezes em UTF-16."""
    h = b.decode("utf-16", "replace") if b[:2] in (b"\xff\xfe", b"\xfe\xff") else b.decode("utf-8", "replace")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style).*?</\1>", "", h, flags=re.S | re.I))))


class Alese(NoPaper):
    _leis: dict = {}
    _leis_ano: list = []

    def coletar(self) -> dict:
        self._leis = self.leis()
        try:
            self._leis_ano = self.leis_por_ano()
            for i in self._leis_ano:  # as listas por ano ligam também leis de quem não está mais na Casa e do governo
                if i.get("orig"):
                    self._leis.setdefault(i["orig"], i)
            # leis sem o link do projeto de origem: ligadas pela ementa idêntica (só quando há uma única lei com ela)
            por_ementa: dict[str, list] = {}
            for i in self._leis_ano:
                if not i.get("orig") and i.get("e"):
                    por_ementa.setdefault(_chave_ementa(i["e"]), []).append(i)
            self._por_ementa = {k: v[0] for k, v in por_ementa.items() if len(v) == 1 and len(k) > 30}
        except SemTempo:  # o fim da rodada chegou: nada pela metade (ficam os arquivos de antes)
            raise
        except Exception as e:
            log(f"  SE: listas de leis por ano falharam ({type(e).__name__}: {e})")
            self._leis_ano, self._por_ementa = [], {}
        r = super().coletar()
        if r.get("pendente"):  # primeira carga das propostas em andamento: o perfil do governador fica como estava
            return r
        try:
            self.governo()
        except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
            log(f"  SE: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
        return r

    def leis_por_ano(self) -> list[dict]:
        """Leis ordinárias e complementares de cada ano desde o começo do mandato do governador (consulta por espécie
        do módulo de Legislação; o ano em curso todo dia, os anteriores a cada 30 dias)."""
        est = self.rede.estado("leis-ano.json", {}) or {}
        h = dt.date.fromisoformat(hoje())
        ini = gv.periodo("SE")["mandato"]
        out = []
        for ano in range(int(ini[:4]), h.year + 1):
            for tipo in (4, 3):  # Lei Ordinária, Lei Complementar
                k = f"{tipo}-{ano}"
                x = est.get(k)
                velho = not x or (h - dt.date.fromisoformat(x["lido"])).days >= (1 if ano == h.year else 30)
                if velho:
                    itens = lista_100(f"{BASE}/legislacao/consulta-legislacao.aspx?tipo={tipo}&ano={ano}", _itens)
                    x = est[k] = {"lido": hoje(), "itens": [dict(i, tl=tipo) for i in itens]}
                    self.rede.guardar(est, "leis-ano.json")
                out += x["itens"]
        return out

    def governo(self) -> dict:
        per = gv.periodo("SE")
        ini = per["inicio"]
        props = (self.rede.estado("estado.json", {}) or {}).get("props") or {}
        # projetos do Executivo: autor "Poder Executivo" (até 2024) ou autor externo "Poder Executivo" (lista do portal)
        cache = self.rede.estado("gov-executivo.json", {}) or {}
        if cache.get("lido") != hoje():
            ids = lista_100(f"{BASE}/spl/consulta-producao.aspx?autor_externo=Poder%20Executivo", _ids_processos)
            cache = {"lido": hoje(), "ids": ids}
            self.rede.guardar(cache, "gov-executivo.json")
        externos = set(cache.get("ids") or [])
        lista = []
        for k, v in props.items():
            tipo = self.tipos.get(v["tid"])
            if not tipo or (v.get("d") or "") < ini or not (v.get("au") == AUTOR_EXECUTIVO or k in externos):
                continue
            s = situacao(dict(v, _id=k))
            prop = regional.proposta(f"{self.prefixo}:{k}", f"{v['s']} {v['n']}/{v['a']}", tipo, v.get("d"), v.get("e"),
                                     v.get("sit"), f"{self.base}/spl/processo.aspx?id={k}", papel="autor", status=s["status"],
                                     data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        fonte_prop = fonte(self.veiculo, "Proposições do Poder Executivo (portal legislativo)",
                           f"{self.base}/spl/consulta-producao.aspx?autor_externo=Poder%20Executivo")
        # leis do período: quem assinou, pelo texto oficial de cada uma (lido uma vez)
        leis = {i["id"]: i for i in self._leis_ano if (i.get("d") or "") >= ini}
        enderecos = {k: f"{BASE}/Arquivo/Documents/legislacao/html/{'C' if i['tl'] == 3 else 'L'}{i['n']}{i['a']}.html?identificador="
                        + "".join(f"{ord(c):02X}00" for c in f"{k}:L") for k, i in leis.items()}
        quem, faltam = gv.classificar_leis(self.rede, enderecos, lambda u: _texto_lei(self.rede.bruto(u, None, None)))
        fontes = [fonte(self.veiculo, "Legislação estadual: leis ordinárias e complementares por ano", f"{BASE}/legislacao/consulta-tipo.aspx")]
        if not self._leis_ano or faltam:  # sem a conta das leis, o perfil ficaria pela metade: fica o arquivo da última vez
            log("  SE: " + (f"{faltam} leis ainda sem leitura do texto" if faltam else "as listas de leis por ano não vieram")
                + "; o perfil do governador fica como estava")
            return {}
        n_leis, nota, nota_en = None, [], []
        c = collections.Counter(quem.values())
        n_leis = c[False]
        pt, en = gv.nota_leis(per, len(leis), c[False], c[True], c[None], "no módulo de Legislação da Alese",
                              "in the Alese legislation portal")
        nota.append(pt)
        nota_en.append(en)
        # vetos: o registro "Veto Governamental" (VET) da Alese está incompleto (ver NOTA_VETOS); ficam fora
        ex = gv.bloco_executivo(per, n_leis, None, fontes, " ".join(nota), " ".join(nota_en),
                                promulgadas_pela_casa=c[True] if n_leis is not None else None)
        esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature")
        return gv.gravar_gov("SE", per, lista, esc, esc_en, fonte_prop, ex, fontes)

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
            except SemTempo:  # o fim da rodada chegou: nada pela metade (ficam os arquivos de antes)
                self.rede.guardar(est, "leis.json")
                raise
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

    def situacao_lei(self, pid: str, ementa: str | None = None, desde: str | None = None) -> dict | None:
        i = self._leis.get(pid)
        if not i and ementa:
            i = (getattr(self, "_por_ementa", None) or {}).get(_chave_ementa(ementa))
            if i and desde and (i.get("d") or "") < desde:
                i = None
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
    lei = COLETOR.situacao_lei(str(v.get("_id") or ""), v.get("e") if v.get("sit") == "Aprovado" else None, v.get("d")) if COLETOR else None
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


# aprovada no Plenário sem norma achada no módulo de Legislação (que não traz as resoluções e os decretos
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
        tse_manual=TSE_MANUAL, notas=[NOTA_VETOS, NOTA_VOTOS_GASTOS],
    )
    return COLETOR.coletar()


NOTA_VOTOS_GASTOS = ("As votações e os gastos não entram. Votações: a Alese publica, para cada sessão, a pauta, a ordem do "
                     "dia e a presença em Plenário (no sistema legislativo), além do áudio e da ata no site, sem o voto de "
                     "cada deputado em formato aberto. Gastos: a Alese publica o ressarcimento de despesas dos deputados só "
                     "em PDF, um relatório por mês, no Portal da Transparência.",
                     "Votes and spending are not included. Votes: for each session the Alese publishes the agenda, the order "
                     "of business and attendance (in its legislative system), plus the audio and the minutes on its website, "
                     "but not each deputy's vote in an open format. Spending: the Alese publishes the deputies' expense "
                     "reimbursements only as PDF files, one report per month, on its transparency portal.")


NOTA_VETOS = ("Os vetos do governador não entram no perfil dele: o registro de vetos da Alese (proposições \"Veto "
              "Governamental\") está incompleto. De 2025 só aparece o veto nº 5 e de 2026 nenhum, e os vetos de um ano são "
              "registrados meses depois. Os vetos saem no Diário Oficial do Estado de Sergipe.",
              "The governor's vetoes are not shown on his profile: the Alese's record of vetoes (\"Veto Governamental\" items) "
              "is incomplete. For 2025 only veto no. 5 appears and for 2026 none, and a year's vetoes are recorded months "
              "later. Vetoes are published in the Sergipe State Official Gazette.")


# conferidos à mão (id do parlamentar na Alese -> candidato do TSE de 2022): "Luizão Donatrampi" é LUIZAO DONA TRAMPI
# (José Luiz da Mota Cruz); "Carminha Paiva" é CARMINHA (Maria do Carmo Paiva da Silva).
TSE_MANUAL = {"569": "260001646927", "563": "260001618237"}
