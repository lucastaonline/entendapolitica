"""Câmara Municipal de São Paulo (SP): dados abertos oficiais do SPLegis (web service JSON em
https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) + lista de vereadores do portal oficial (fotos e páginas).

- Quem está no cargo hoje: OcupacaoGabineteJSON (quem ocupa cada um dos 55 gabinetes, com início e fim: mostra também os
  suplentes que assumiram); partido de hoje: VereadoresCMSPJSON (filiações); foto e página: www.saopaulo.sp.leg.br/vereadores/membros/.
- Propostas (PL, PDL, PR e PLO = emenda à Lei Orgânica) desde 1º/1/2025: ProjetosAutoresJSON (autores), ProjetosPorAnoJSON
  (data e ementa), ProjetosEncerradosJSON (motivo do encerramento: promulgado, retirado, arquivado, apensado...),
  FasesDeDeliberacaoJSON (aprovações em plenário), LeisAprovadasPorPromoventeJSON e ProjetosVetadosPorPromoventeJSON.
- O SPLegis lista os autores de cada projeto em ordem de código, sem dizer quem assinou primeiro: projeto de um autor só
  conta como "autor"; projeto de vários autores conta como "assinou junto" para todos (está explicado na página).
- Votações nominais desde 1º/1/2025: o arquivo anual da página "Votação em Plenário" (VOTACOES_<ano>.xml), com o voto de
  cada vereador pelo código do SPLegis; entram as de projetos, emendas a projetos e vetos (votacoes_sp).
- Gastos do mandato: os débitos do Auxílio-Encargos Gerais de Gabinete no SisGV (web service, um pedido por mês), somados por
  vereador, por ano e por tipo de despesa (gastos_sp).
"""
from __future__ import annotations

import html
import json
import re
import time

import regional
from comum import baixar, fonte, hoje, log, sem_acento

from . import _base as B
from ._capitais import publicados
from ._sapl import data_en, data_pt

IBGE, UF = "3550308", "SP"
WS = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
PORTAL = "https://www.saopaulo.sp.leg.br"
CONSULTA = "https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/DetailsDetalhado?COD_MTRA_LEGL={t}&COD_PCSS_CMSP={n}&ANO_PCSS_CMSP={a}"
CASA = "Câmara Municipal de São Paulo"
TIPOS = {"PL": "PL", "PDL": "PDL", "PR": "PRC", "PLO": "PELO"}
PASTA = B.PASTA_CACHE / IBGE

# motivo do encerramento (ProjetosEncerradosJSON) -> (status, chave de _base.TXT ou None)
MOTIVOS = [
    (r"promulgad", "lei", None),
    (r"retirad", "retirada", None),
    (r"apensad", "junta", None),
    (r"arquivad", "arquivada", None),
    (r"ilegalidade|devolucao|devolvid", "parada", None),
    (r"rejeitad", "rejeitada", None),
    (r"prejudicad", "parada", None),
]
_n = 0


def ws(metodo: str, cache: str | None = None, idade_h: float | None = 20):
    global _n
    arq = PASTA / "http" / f"{cache}.json" if cache else None
    if arq and arq.exists() and (idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < idade_h):
        return json.loads(arq.read_text(encoding="utf-8"))
    B.esperar_vez(WS + metodo, 0.4)  # robots.txt (Disallow e Crawl-delay) e intervalo entre pedidos
    try:
        d = json.loads(baixar(WS + metodo, tentativas=4, timeout=240).decode("utf-8-sig"))
    finally:
        B.pedido_feito(WS + metodo)
    _n += 1
    if arq:
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def chave_nome(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", sem_acento((s or "").lower()))


def nome_ws_pref(executivos: list[dict], cod) -> str:
    n = next((p.get("nome") for p in executivos if p["chave"] == cod), "") or ""
    return B.nome_limpo(n) or "Poder Executivo"


def portal_membros() -> dict[str, dict]:
    """Cartões da página oficial de vereadores: {nome sem acento: {nome, url, foto}}."""
    arq = PASTA / "http" / "membros.html"
    if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < 20:
        t = arq.read_text(encoding="utf-8")
    else:
        B.esperar_vez(f"{PORTAL}/vereadores/membros/", 0.5)
        try:
            t = baixar(f"{PORTAL}/vereadores/membros/", tentativas=4, timeout=120).decode("utf-8", "replace")
        finally:
            B.pedido_feito(f"{PORTAL}/vereadores/membros/")
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(t, encoding="utf-8")
    out = {}
    for card in re.findall(r'(?s)<div class="card-vereador">(.*?)<div class="infos-vereador.*?href="([^"]+)"', t):
        corpo, url = card
        foto = re.search(r'<img class="thumbnail" src="([^"]+)"', corpo)
        nome = re.search(r"<h3[^>]*>(.*?)</h3>", corpo, re.S)
        if nome:
            n = html.unescape(re.sub(r"<[^>]+>|\s+", " ", nome.group(1))).strip()
            out[chave_nome(n)] = {"nome": n, "url": url, "foto": foto.group(1) if foto else None}
    if len(out) < 40:
        raise RuntimeError(f"a página de vereadores mudou ({len(out)} cartões)")
    return out


def no_cargo() -> list[dict]:
    """Quem ocupa cada gabinete hoje (legislatura atual, sem data de fim)."""
    g = ws("OcupacaoGabineteJSON", "gabinetes", 6)
    leg = max(x["legislatura"] for x in g)
    h = hoje()
    atuais = [x for x in g if x["legislatura"] == leg and (x.get("inicio") or "")[:10] <= h and not x.get("fim")]
    por_gab = {}
    for x in atuais:  # se um gabinete aparecer duas vezes sem fim, vale quem entrou por último
        if x["gabinete"] not in por_gab or x["inicio"] > por_gab[x["gabinete"]]["inicio"]:
            por_gab[x["gabinete"]] = x
    return list(por_gab.values())


def status_de(p: dict, encerr: dict, delib: dict, leis: dict, vetos: dict) -> tuple:
    """(status, statusTxt, statusTxt_en, situação oficial, data, lei)."""
    k = (p["tipo"], p["numero"], p["ano"])
    lei = leis.get(k)
    lei_d = {"nome": f"Lei nº {int(lei['numero']):,}/{lei['publicacao'][:4]}".replace(",", "."), "url": None} if lei else None
    e = encerr.get(k)
    if e:
        mot = re.sub(r"^Encerrado-", "", e.get("motivo") or "").strip()
        t = sem_acento(mot.lower())
        data = (e.get("encerramento") or "")[:10] or None
        for exp, st, _ in MOTIVOS:
            if re.search(exp, t):
                if st == "lei":
                    txt = B.virou(lei_d["nome"], vetos.get(k) == "parcial") if lei_d else None
                    return "lei", txt, None, e.get("motivo"), data, lei_d
                return st, None, None, e.get("motivo"), data, None
        return "outra", f"Situação na Câmara: {e.get('motivo')}", None, e.get("motivo"), data, None
    if lei_d:
        return "lei", B.virou(lei_d["nome"], vetos.get(k) == "parcial"), None, "Lei aprovada", lei["publicacao"][:10], lei_d
    if vetos.get(k) == "total":
        return "rejeitada", *B.TXT["veto_total"], "Veto Total", None, None
    ds = delib.get(k) or []
    if ds:
        ult = ds[-1]
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", ult)
        data = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
        t = B.norm(ult)
        if re.search(r"aprovad[oa].*(2a|3a|segunda|terceira) discussao|discussao unica|redacao final|por pareceres", t):
            ch = "sancao" if p["tipo"] == "PL" else "promulgar"
            return "aprovada", *B.TXT[ch], ult, data, None
        return "andando", None, None, ult, data, None
    return "andando", None, None, "Em tramitação", None, None


# ------------------------------------------------ votações nominais e gastos do mandato
VOT_XML = "https://splegispdarmazenamento.blob.core.windows.net/containersip/VOTACOES_{ano}.xml"
PAG_VOTOS = f"{PORTAL}/atividade-legislativa/sessao-plenaria/votacao-em-plenario/"
SISGV = "https://sisgvconsulta.saopaulo.sp.leg.br/ws/ws2.asmx/ObterDebitoVereadorJSON"
# a página "Prestação de contas dos vereadores" lista só os anos de 2010 a 2023 (atualizada pela última vez em agosto de
# 2024); as contas mais novas a Câmara publica pelo SisGV, que está na página de dados abertos
PAG_GASTOS = f"{PORTAL}/transparencia/dados-abertos/dados-disponibilizados-em-formato-aberto/"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
ESCOPO_VOTOS = ("Votações nominais (em que o voto de cada vereador fica registrado) de projetos, emendas a projetos e vetos no "
                "Plenário desde 1º/1/2025, segundo o arquivo de votações dos dados abertos da Câmara (SPLegis). Votações de "
                "requerimentos, de outros documentos, de procedimentos da sessão (adiamento, suspensão, inversão da pauta), as "
                "eleições da Mesa e as votações que ficaram sem resultado (\"Pendente de Votação\") não entram.",
                "Roll-call votes (where each councilor's vote is recorded) on bills, amendments to bills and vetoes in the full "
                "City Council since January 1, 2025, according to the votes file in the City Council's open data (SPLegis). Votes "
                "on requests, on other documents, on session procedures (postponing, suspending, reordering the agenda), the "
                "elections of the Council's board and the votes left without a result (marked as pending) are not included.")
NOME_GASTOS = ("Auxílio-Encargos Gerais de Gabinete (custos do mandato), prestação de contas no SisGV",
               "General office expenses allowance (office costs), as accounted for in the City Council's SisGV system")
_PROJ = re.compile(r"\b(PL|PDL|PR|PLO)\s*(\d+)\s*/\s*(\d{4})", re.I)
# o que não é votação de projeto: procedimentos da sessão, eleições da Mesa, CPIs, requerimentos
_PROCEDIMENTO = re.compile(r"^(adiamento|suspens|invert|prorroga|requerimento|considerar|eleicao|instalacao|minuto|manutencao|cria)")


def baixar_guardado(url: str, nome: str, idade_h: float, dados: bytes | None = None) -> bytes:
    """Um pedido (com o robots.txt e o intervalo do servidor), guardado em .cache/camaras/3550308/http/<nome>."""
    global _n
    arq = PASTA / "http" / nome
    if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < idade_h:
        return arq.read_bytes()
    B.esperar_vez(url, 0.5)
    try:
        b = baixar(url, tentativas=4, timeout=240, dados=dados,
                   headers={"Content-Type": "application/x-www-form-urlencoded"} if dados else None)
    finally:
        B.pedido_feito(url)
    _n += 1
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_bytes(b)
    return b


def votacoes_sp(por_cod: dict, anos: list[int], h: str) -> tuple[dict, dict]:
    """(catálogo {chave: votação}, {código do SPLegis: [[chave, voto], ...]}) das votações nominais desde 1º/1/2025, pelo
    arquivo anual de votações (VOTACOES_<ano>.xml, o mesmo da página "Votação em Plenário"). O voto de cada vereador vem
    com o código dele no SPLegis (IDParlamentar), o mesmo da ocupação dos gabinetes: a ligação é exata. Placar = o
    publicado; se a soma dos votos for diferente, vai junto o "aviso". Votação ainda "Pendente de Votação" não entra."""
    import xml.etree.ElementTree as ET
    from ._sapl import voto_normal
    cat, por = {}, {}
    for ano in anos:
        b = baixar_guardado(VOT_XML.format(ano=ano), f"votacoes-{ano}.xml", 20 if ano >= int(h[:4]) - 1 else 24 * 7)
        raiz = ET.fromstring(b.decode("utf-8-sig"))
        for ses in raiz.iter("Sessao"):
            m = re.match(r"(\d{2})/(\d{2})/(\d{4})", ses.get("Data") or "")
            if not m:
                continue
            data = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            if data < B.INICIO or data > h:
                continue
            for v in ses.iter("Votacao"):
                mat = re.sub(r"\s+", " ", v.get("Materia") or "").strip()
                nm = B.norm(mat)
                pj = _PROJ.search(mat)
                res = (v.get("Resultado") or "").strip()
                if (v.get("TipoVotacao") or "").strip().lower() != "nominal" or not (pj or re.search(r"\bveto", nm)) \
                        or _PROCEDIMENTO.match(nm) or B.norm(res).startswith("pendente"):
                    continue
                brutos = [(int(x.get("IDParlamentar")), voto_normal(x.get("Voto"))) for x in v.findall("Vereador")
                          if (x.get("IDParlamentar") or "").isdigit()]
                if not brutos:
                    continue
                chave = f"cmsp-vot:{v.get('VotacaoID')}"
                nres = B.norm(res)
                resultado = "Aprovado" if nres.startswith("aprovad") else "Rejeitado" if re.match(r"(reprovad|rejeitad)", nres) else (res or None)
                oficial = {"Sim": int(v.get("Sim") or 0), "Não": int(v.get("Nao") or 0), "Abstenção": int(v.get("Abstencao") or 0)}
                # o arquivo às vezes traz a mesma pessoa duas vezes na mesma votação, com votos diferentes
                votos = B.votos_unicos(brutos, oficial)
                contado = {k: sum(1 for x in votos.values() if x == k) for k in oficial}
                ementa = re.sub(r"\s+", " ", v.get("Ementa") or "").strip()
                sg = pj.group(1).upper() if pj else None  # a sigla do SPLegis, como nas propostas ("PLO 8/2017")
                x = {"data": data, "proposta": f"{sg} {int(pj.group(2))}/{pj.group(3)}" if pj else None,
                     "propostaId": f"cmsp:{sg}-{int(pj.group(2))}-{pj.group(3)}" if pj else None,
                     "descricao": f"{mat}: {ementa}" if ementa else mat, "resultado": resultado,
                     "placar": dict(oficial, total=sum(oficial.values())), "url": PAG_VOTOS}
                if contado != oficial:
                    x["aviso"] = {"oficial": oficial, "contado": contado}
                cat[chave] = x
                for cod, voto in votos.items():
                    if cod in por_cod:
                        por.setdefault(cod, []).append([chave, voto])
    for lst in por.values():
        lst.sort(key=lambda kv: (cat[kv[0]]["data"], kv[0]), reverse=True)
    return cat, por


_SIGLAS_DESPESA = {"ottcs": "OTTCS", "onix": "Onix"}


def _tipo_despesa(t: str) -> str:
    """Nome oficial do tipo de despesa, com as partes em CAIXA ALTA passadas para minúsculas (como os da Câmara dos
    Deputados): "LOCAÇÃO DE IMÓVEL DE PESSOA FÍSICA - Inciso XVI do Art 3º do Ato 971/07" →
    "Locação de imóvel de pessoa física - Inciso XVI do Art 3º do Ato 971/07"."""
    partes = re.sub(r"\s+", " ", t or "").strip().split(" - ")
    for i, p in enumerate(partes):
        if p.isupper():
            p = re.sub(r"[^\W\d_]+", lambda m: _SIGLAS_DESPESA.get(m.group(0).lower(), m.group(0).lower()), p)
            partes[i] = p[:1].upper() + p[1:] if i == 0 else p
    return " - ".join(partes)


def gastos_sp(por_cod: dict, h: str) -> tuple[dict, set]:
    """({código do SPLegis: bloco "gastos"}, nomes do SisGV sem ligação): os débitos do Auxílio-Encargos Gerais de Gabinete
    de cada vereador (SisGV, ObterDebitoVereadorJSON, um pedido por mês desde janeiro de 2025; os meses passados ficam
    guardados por 30 dias). Ligação pelo nome (o SisGV não traz o código do SPLegis), conferida com os nomes dos gabinetes.
    O ano mostrado é o mais recente com gastos; o total do mandato soma tudo desde o primeiro mês com gastos."""
    ano_h, mes_h = int(h[:4]), int(h[5:7])
    nome_cod: dict[str, int] = {}
    for cod, (m, g) in por_cod.items():
        for n in (m.get("nome"), g.get("vereador"), m.get("nomeCivil")):
            if n:
                nome_cod.setdefault(chave_nome(n), cod)
    soma: dict[int, dict[tuple, dict[str, float]]] = {}
    sem = set()
    for ano in range(int(B.INICIO[:4]), ano_h + 1):
        for mes in range(1, 13):
            if (ano, mes) > (ano_h, mes_h):
                break
            recente = (ano * 12 + mes) >= (ano_h * 12 + mes_h - 2)  # os 3 meses mais novos ainda podem mudar
            b = baixar_guardado(SISGV, f"sisgv-{ano}-{mes:02d}.json", 20 if recente else 24 * 30,
                                dados=f"ano={ano}&mes={mes}".encode())
            for x in json.loads(b.decode("utf-8-sig") or "[]"):
                cod = nome_cod.get(chave_nome(x.get("VEREADOR")))
                if cod is None:
                    sem.add(x.get("VEREADOR") or "?")
                    continue
                tipos = soma.setdefault(cod, {}).setdefault((ano, mes), {})
                t = _tipo_despesa(x.get("DESPESA"))
                tipos[t] = tipos.get(t, 0.0) + float(x.get("VALOR") or 0)
    f = fonte(CASA, f"SisGV (custos de mandato dos vereadores): débitos do Auxílio-Encargos Gerais de Gabinete de "
                    f"janeiro de {B.INICIO[:4]} a {MESES[mes_h - 1]} de {ano_h}, nos dados abertos da Câmara", PAG_GASTOS, h)
    out = {}
    for cod, por_mes in soma.items():
        meses = sorted(por_mes)
        if not meses or round(sum(sum(t.values()) for t in por_mes.values()), 2) <= 0:
            continue
        ano = meses[-1][0]
        do_ano = [k for k in meses if k[0] == ano]
        por_tipo: dict[str, float] = {}
        for k in do_ano:
            for t, val in por_mes[k].items():
                por_tipo[t] = por_tipo.get(t, 0.0) + val
        out[cod] = {"ano": ano, "total": round(sum(por_tipo.values()), 2),
                    "porTipo": [{"tipo": t, "valor": round(val, 2)} for t, val in sorted(por_tipo.items(), key=lambda kv: (-kv[1], kv[0])) if round(val, 2)],
                    "mandatoTotal": round(sum(sum(por_mes[k].values()) for k in meses), 2),
                    "desde": f"{meses[0][0]}-{meses[0][1]:02d}", "meses": [f"{ano}-{do_ano[0][1]:02d}", f"{ano}-{do_ano[-1][1]:02d}"],
                    "nome": NOME_GASTOS[0], "nome_en": NOME_GASTOS[1], "fonte": f}
    return out, sem


def coletar() -> dict:
    global _n
    _n = 0
    t0 = time.time()
    h = hoje()
    ano_atual = int(h[:4])
    anos = list(range(int(B.INICIO[:4]), ano_atual + 1))

    # ------------------------------------------------ quem está no cargo
    gab = no_cargo()
    if len(gab) < 50:
        raise RuntimeError(f"só {len(gab)} gabinetes ocupados")
    vers = {v["chave"]: v for v in ws("VereadoresCMSPJSON", "vereadores", 20)}
    cards = portal_membros()
    # conferido à mão: "Silvinho Leite" no portal da Câmara = SILVINHO no TSE (nome completo Silvio Ricardo Pereira dos
    # Santos, na página oficial https://www.saopaulo.sp.leg.br/vereador/silvinho-leite/)
    tse = B.Tse(IBGE, UF, {2279: "250001881810"})
    fonte_lista = fonte(CASA, "Vereadores em exercício (portal oficial; SPLegis: ocupação dos gabinetes)", f"{PORTAL}/vereadores/membros/", h)
    membros, por_cod = [], {}
    for g in gab:
        v = vers.get(g["codigo"]) or {}
        nome_ws = g.get("vereador") or v.get("nome")
        card = cards.get(chave_nome(nome_ws)) or next((c for k, c in cards.items() if chave_nome(nome_ws) in k or k in chave_nome(nome_ws)), None)
        nome = card["nome"] if card else B.nome_limpo(nome_ws)
        fil = sorted([f for f in v.get("filiacoes") or [] if not f.get("fim") or f["fim"][:10] >= h], key=lambda f: f.get("inicio") or "")
        sigla = B.partido(fil[-1]["partido"]["sigla"]) if fil else None
        pid, cand = tse.casar(g["codigo"], [nome, nome_ws], sigla)
        supl = bool(cand) and cand.get("sit") == "SUPLENTE"
        m = {"id": pid, "nome": nome, "nomeCivil": None, "partido": sigla, "genero": (cand or {}).get("genero"),
             "foto": B.foto(card["foto"], pid, IBGE) if card and card.get("foto") else None,
             "url": card["url"] if card else f"{PORTAL}/vereadores/membros/",
             "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None}
        if m["genero"] not in ("F", "M"):
            m["genero"] = None
        if cand and cand.get("nome"):
            civil = B.nome_limpo(cand["nome"])
            if chave_nome(civil) != chave_nome(nome):
                m["nomeCivil"] = civil
        membros.append(m)
        por_cod[g["codigo"]] = (m, g)

    # ------------------------------------------------ propostas
    projetos = {}
    for ano in anos:
        idade = 20 if ano >= ano_atual - 1 else 24 * 7
        info = {(x["tipo"], x["numero"]): x for x in ws(f"ProjetosPorAnoJSON?ano={ano}", f"projetos-{ano}", idade) if x["tipo"] in TIPOS}
        for tipo in TIPOS:
            for x in ws(f"ProjetosAutoresJSON?ano={ano}&tipo={tipo}&numero=", f"autores-{ano}-{tipo}", idade):
                i = info.get((tipo, x["numero"])) or {}
                projetos[(tipo, x["numero"], ano)] = {
                    "tipo": tipo, "_tipo": x.get("_tipo") or i.get("_tipo"), "numero": x["numero"], "ano": ano,
                    "data": (i.get("data") or x.get("leitura") or "")[:10] or None, "ementa": (i.get("ementa") or "").strip() or None,
                    "autores": [a["chave"] for a in x.get("autores") or []]}
    encerr, delib = {}, {}
    for ano in anos:
        for x in ws(f"ProjetosEncerradosJSON?ano={ano}", f"encerrados-{ano}", 20):
            if x["tipo"] in TIPOS:
                encerr[(x["tipo"], x["numero"], x["ano"])] = x
        for x in ws(f"FasesDeDeliberacaoJSON?ano={ano}", f"fases-{ano}", 20):
            if x["tipo"] in TIPOS:
                delib[(x["tipo"], x["numero"], x["ano"])] = [d.get("resultado") or "" for d in x.get("deliberacoes") or [] if d.get("resultado")]
    leis, vetos = {}, {}
    # o prefeito de hoje no SPLegis: promovente do tipo EXECUTIVO com o nome dele (dados/cidades/SP/3550308.json)
    pref = B.cidade(IBGE, UF).get("prefeito") or {}
    executivos = [p for p in ws("PromoventesCMSPJSON", "promoventes", 24 * 7) if ((p.get("tipo") or {}).get("nome") or "") == "EXECUTIVO"]
    cod_pref = next((p["chave"] for p in executivos if chave_nome(p.get("nome")) in {chave_nome(pref.get("nome")),
                                                                                    chave_nome(pref.get("nomeCivil"))}), None)
    for cod in list(por_cod) + ([cod_pref] if cod_pref else []):
        for x in ws(f"LeisAprovadasPorPromoventeJSON?Codigo={cod}", f"leis-{cod}", 20):
            p = x.get("projeto") or {}
            if p.get("tipo") in TIPOS and (p.get("ano") or 0) >= anos[0]:
                leis[(p["tipo"], p["numero"], p["ano"])] = {"numero": x.get("numero"), "publicacao": x.get("publicacao") or ""}
        for x in ws(f"ProjetosVetadosPorPromoventeJSON?Codigo={cod}", f"vetos-{cod}", 20):
            if x.get("tipo") in TIPOS and (x.get("ano") or 0) >= anos[0]:
                vetos[(x["tipo"], x["numero"], x["ano"])] = "total" if "total" in sem_acento(((x.get("veto") or {}).get("nome") or "").lower()) else "parcial"

    por_parl = {cod: [] for cod in por_cod}
    inicio_pref = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
    do_pref = []
    for k, p in projetos.items():
        autores = p["autores"]
        if cod_pref and cod_pref in autores and (p["data"] or "") >= inicio_pref:
            st, txt, txt_en, situ, data_st, lei = status_de(p, encerr, delib, leis, vetos)
            x = regional.proposta(f"cmsp:{p['tipo']}-{p['numero']}-{p['ano']}", f"{p['tipo']} {p['numero']}/{p['ano']}",
                                  TIPOS[p["tipo"]], p["data"], p["ementa"], situ, CONSULTA.format(t=p["_tipo"], n=p["numero"], a=p["ano"]),
                                  "autor", status=st, data_status=data_st, status_txt=txt, lei=lei)
            if txt_en:
                x["statusTxt_en"] = txt_en
            do_pref.append(x)
        if not any(a in por_parl for a in autores):
            continue
        st, txt, txt_en, situ, data_st, lei = status_de(p, encerr, delib, leis, vetos)
        url = CONSULTA.format(t=p["_tipo"], n=p["numero"], a=p["ano"])
        for a in autores:
            if a not in por_parl:
                continue
            papel = "autor" if len(autores) == 1 else "coautor"
            x = regional.proposta(f"cmsp:{p['tipo']}-{p['numero']}-{p['ano']}", f"{p['tipo']} {p['numero']}/{p['ano']}", TIPOS[p["tipo"]],
                                  p["data"], p["ementa"], situ, url, papel, status=st, data_status=data_st, status_txt=txt, lei=lei)
            if txt_en:
                x["statusTxt_en"] = txt_en
            por_parl[a].append(x)

    escopo = (B.ESCOPO + ", segundo o SPLegis, o sistema oficial da Câmara.",
              B.ESCOPO_EN + ", according to SPLegis, the City Council's official system.")
    nota = ("Na Câmara de São Paulo, um projeto pode ter vários autores, e o sistema oficial não diz quem assinou primeiro. "
            "Por isso, os projetos com mais de um autor aparecem como \"assinou junto\" para todos eles.")
    nota_en = ("At the São Paulo City Council a bill can have several authors, and the official system does not say who signed "
               "first. So bills with more than one author are shown as \"co-signed\" for all of them.")
    extras = {}
    for cod, (m, g) in por_cod.items():
        f_prop = fonte(CASA, f"SPLegis (dados abertos): projetos de {m['nome']}", WS.replace("/ws2.asmx/", "/ws2.asmx?op=") + "ProjetosAutoresJSON", h)
        bloco = regional.bloco_propostas(por_parl[cod], escopo[0], escopo[1], f_prop)
        bloco["nota"], bloco["nota_en"] = nota, nota_en
        x = {"propostas": bloco, "links": {"oficial": m["url"], "email": None, "redes": []}, "fontes": [fonte_lista, f_prop]}
        if m.get("foto"):
            x["fotoCredito"] = CASA
        if (g.get("inicio") or "")[:10] > regional.INICIO_MUNICIPAL:  # assumiu depois do começo da legislatura
            x["desde"] = g["inicio"][:10]
        extras[m["id"]] = x
    if tse.sem_ligacao:
        log(f"  CMSP: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")

    # ------------------------------------------------ votações nominais e gastos do mandato
    # um sistema fora do ar não derruba a Câmara (o SisGV deu "erro 500" em todos os meses em 27 e 28/10/2026): as propostas
    # seguem, e ficam publicadas as votações ou os gastos de antes, para quem continua no cargo
    votos_antes: dict[str, dict] = {}
    gastos_antes: dict[str, dict] = {}
    try:
        cat_vot, votos_cod = votacoes_sp(por_cod, anos, h)
    except Exception as erro:
        log(f"  CMSP: votações: {type(erro).__name__}: {str(erro)[:200]}; ficam as votações publicadas antes")
        cat_vot, votos_antes = B.votos_publicados(IBGE)
        votos_cod = {}
    try:
        gastos_cod, sem_gastos = gastos_sp(por_cod, h)
    except Exception as erro:
        log(f"  CMSP: gastos: {type(erro).__name__}: {str(erro)[:200]}; ficam os gastos publicados antes")
        gastos_cod, sem_gastos = {}, set()
        gastos_antes = publicados(IBGE, "gastos")
    if sem_gastos:
        log(f"  CMSP: gastos de quem não está no cargo hoje (ficam fora): {', '.join(sorted(sem_gastos))}")
    f_vot = fonte(CASA, "Votação em Plenário: arquivo de votações (dados abertos, XML por ano)", PAG_VOTOS, h)
    for cod, (m, g) in por_cod.items():
        x = extras[m["id"]]
        lst = votos_cod.get(cod) or []
        if lst:
            resumo = {"total": len(lst)}
            for k in ("Sim", "Não", "Abstenção"):
                resumo[k] = sum(1 for _, vt in lst if vt == k)
            resumo["Outro"] = resumo["total"] - resumo["Sim"] - resumo["Não"] - resumo["Abstenção"]
            x["votacoes"] = {"escopo": ESCOPO_VOTOS[0], "escopo_en": ESCOPO_VOTOS[1], "resumo": resumo, "fonte": f_vot,
                             "arquivo": f"dados/camaras/extras/{IBGE}.json", "votos": lst}
            x["fontes"].append(f_vot)
        elif votos_antes.get(m["id"]):
            x["votacoes"] = votos_antes[m["id"]]
            x["fontes"].append(votos_antes[m["id"]].get("fonte"))
        g_bloco = gastos_cod.get(cod) or gastos_antes.get(m["id"])
        if g_bloco:
            x["gastos"] = g_bloco
            x["fontes"].append(g_bloco["fonte"])
    if votos_antes:  # no catálogo, só o que foi votado por quem continua no cargo
        usadas = {k for x in extras.values() for k, _ in (x.get("votacoes") or {}).get("votos") or []}
        cat_vot = {k: v for k, v in cat_vot.items() if k in usadas}
    cobertura = {"lista": True, "propostas": True, "votacoes": bool(votos_cod or votos_antes),
                 "gastos": bool(gastos_cod or gastos_antes)}
    casa = {"casa": CASA, "casa_en": "São Paulo City Council", "sigla": "CMSP", "site": PORTAL, "fonte": fonte_lista,
            "sistema": "SPLegis (web service de dados abertos)", "api": "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx"}
    notas = [("O número de leis que o prefeito sancionou e o de vetos não entram neste site: o SPLegis lista as leis e os vetos "
              "só por autor de cada projeto, e não todos os do município de uma vez.",
              "The number of laws the mayor signed and of vetoes are not included on this site: SPLegis lists laws and vetoes "
              "only by the author of each bill, not all of the city's at once.")]
    prefeito = None
    if cod_pref:
        desde_pt = ("desde 1º/1/2025, começo do mandato" if inicio_pref == B.INICIO
                    else f"desde {data_pt(inicio_pref)}, quando assumiu a prefeitura")
        desde_en = ("since January 1, 2025 (start of the term)" if inicio_pref == B.INICIO
                    else f"since {data_en(inicio_pref)}, when the current mayor took office")
        f_pref = fonte(CASA, f"SPLegis (dados abertos): projetos do Executivo ({nome_ws_pref(executivos, cod_pref)})",
                       WS.replace("/ws2.asmx/", "/ws2.asmx?op=") + "ProjetosAutoresJSON", h)
        prefeito = (pref["id"], {"propostas": regional.bloco_propostas(
            do_pref, f"Projetos que a prefeitura mandou à Câmara Municipal {desde_pt} (projetos de lei e de emenda à Lei "
                     "Orgânica), segundo o SPLegis, o sistema oficial da Câmara",
            f"Bills the mayor's office sent to the City Council {desde_en} (bills and amendments to the city's Organic Law), "
            "according to SPLegis, the City Council's official system", f_pref), "fontes": [f_pref]})
    else:
        log("  CMSP: não achei o prefeito entre os promoventes do tipo EXECUTIVO do SPLegis")
    r = B.salvar(IBGE, UF, casa, membros, extras, cobertura, notas, escopo, prefeito=prefeito, votacoes=cat_vot)
    r["requisicoes"] = _n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMSP: {len(membros)} no cargo, {r['propostas']} propostas, {r.get('votacoes', 0)} votações nominais, "
        f"{r.get('vereadoresComGastos', 0)} vereadores com gastos, {_n} requisições, {time.time() - t0:.0f} s")
    return r
