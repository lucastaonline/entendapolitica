"""Câmara Municipal de São Paulo (SP): dados abertos oficiais do SPLegis (web service JSON em
https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) + lista de vereadores do portal oficial (fotos e páginas).

- Quem está no cargo hoje: OcupacaoGabineteJSON (quem ocupa cada um dos 55 gabinetes, com início e fim: mostra também os
  suplentes que assumiram); partido de hoje: VereadoresCMSPJSON (filiações); foto e página: www.saopaulo.sp.leg.br/vereadores/membros/.
- Propostas (PL, PDL, PR e PLO = emenda à Lei Orgânica) desde 1º/1/2025: ProjetosAutoresJSON (autores), ProjetosPorAnoJSON
  (data e ementa), ProjetosEncerradosJSON (motivo do encerramento: promulgado, retirado, arquivado, apensado...),
  FasesDeDeliberacaoJSON (aprovações em plenário), LeisAprovadasPorPromoventeJSON e ProjetosVetadosPorPromoventeJSON.
- O SPLegis lista os autores de cada projeto em ordem de código, sem dizer quem assinou primeiro: projeto de um autor só
  conta como "autor"; projeto de vários autores conta como "assinou junto" para todos (está explicado na página).
"""
from __future__ import annotations

import html
import json
import re
import time

import regional
from comum import baixar, fonte, hoje, log, sem_acento

from . import _base as B

IBGE, UF = "3550308", "SP"
WS = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
PORTAL = "https://www.saopaulo.sp.leg.br"
CONSULTA = "https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/DetailsDetalhado?COD_MTRA_LEGL={t}&COD_PCSS_CMSP={n}&ANO_PCSS_CMSP={a}"
CASA = "Câmara Municipal de São Paulo"
TIPOS = {"PL": "PL", "PDL": "PDL", "PR": "PRC", "PLO": "PELO"}
PASTA = B.CACHE / "camaras" / IBGE

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
    d = json.loads(baixar(WS + metodo, tentativas=4, timeout=240).decode("utf-8-sig"))
    _n += 1
    time.sleep(0.4)
    if arq:
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def chave_nome(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", sem_acento((s or "").lower()))


def portal_membros() -> dict[str, dict]:
    """Cartões da página oficial de vereadores: {nome sem acento: {nome, url, foto}}."""
    arq = PASTA / "http" / "membros.html"
    if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < 20:
        t = arq.read_text(encoding="utf-8")
    else:
        t = baixar(f"{PORTAL}/vereadores/membros/", tentativas=4, timeout=120).decode("utf-8", "replace")
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
    for cod in por_cod:
        for x in ws(f"LeisAprovadasPorPromoventeJSON?Codigo={cod}", f"leis-{cod}", 20):
            p = x.get("projeto") or {}
            if p.get("tipo") in TIPOS and (p.get("ano") or 0) >= anos[0]:
                leis[(p["tipo"], p["numero"], p["ano"])] = {"numero": x.get("numero"), "publicacao": x.get("publicacao") or ""}
        for x in ws(f"ProjetosVetadosPorPromoventeJSON?Codigo={cod}", f"vetos-{cod}", 20):
            if x.get("tipo") in TIPOS and (x.get("ano") or 0) >= anos[0]:
                vetos[(x["tipo"], x["numero"], x["ano"])] = "total" if "total" in sem_acento(((x.get("veto") or {}).get("nome") or "").lower()) else "parcial"

    por_parl = {cod: [] for cod in por_cod}
    for k, p in projetos.items():
        autores = p["autores"]
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
        if (g.get("inicio") or "")[:10] > "2025-01-01":
            x["desde"] = g["inicio"][:10]
        extras[m["id"]] = x
    if tse.sem_ligacao:
        log(f"  CMSP: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    casa = {"casa": CASA, "casa_en": "São Paulo City Council", "sigla": "CMSP", "site": PORTAL, "fonte": fonte_lista,
            "sistema": "SPLegis (web service de dados abertos)", "api": "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx"}
    notas = [("A Câmara publica as votações de cada vereador (arquivo XML por ano) e os gastos do mandato (SisGV), "
              "mas eles ainda não estão neste site.",
              "The City Council publishes each councilor's votes (one XML file per year) and office spending (SisGV), "
              "but they are not on this site yet.")]
    r = B.salvar(IBGE, UF, casa, membros, extras, cobertura, notas, escopo)
    r["requisicoes"] = _n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMSP: {len(membros)} no cargo, {r['propostas']} propostas, {_n} requisições, {time.time() - t0:.0f} s")
    return r
