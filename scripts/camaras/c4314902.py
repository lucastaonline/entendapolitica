"""Câmara Municipal de Porto Alegre (RS): a lista oficial de vereadores em exercício (www.camarapoa.rs.gov.br/vereadores) e
as votações nominais do Plenário (sistema de votações da Câmara, votacoes.camarapoa.rs.gov.br).

A página separa quem está no cargo ("titulares", com os suplentes que assumiram) de quem está de licença. As proposições
ficam no sistema de processos da Câmara (páginas HTML), sem dados abertos para baixar: não entram (nota da Câmara abaixo).

Votações: a lista das nominais (20 por página, da mais nova para a mais antiga) e a página de cada uma (o que foi votado,
o placar, o resultado e o voto de cada vereador, pelo nome). Entram as de projetos, emendas, subemendas, substitutivos,
mensagens retificativas e vetos desde 1º/1/2025; chamadas de presença, verificações de quórum, requerimentos e votações
anuladas ou sem resultado ficam fora. O que já foi lido fica em .cache/camaras/4314902/votos.json: a primeira leitura
(umas 750 páginas, 1 s entre elas: uns 15 minutos) pode levar mais de uma rodada; até terminar, ficam publicadas as votações
de antes (nada pela metade). Depois, só as novas.
"""
import datetime as dt
import html
import re
import time

from comum import baixar, fonte, hoje, ler_json, log, salvar_json

from . import _base as B

IBGE, UF, SITE = "4314902", "RS", "https://www.camarapoa.rs.gov.br"
VOT = "https://votacoes.camarapoa.rs.gov.br"
CASA = {"casa": "Câmara Municipal de Porto Alegre", "casa_en": "Porto Alegre City Council", "sigla": "CMPA", "site": SITE,
        "sistema": "Portal oficial (HTML) e sistema de votações"}
ESTADO = B.PASTA_CACHE / IBGE / "votos.json"
ESCOPO_VOTOS = ("Votações nominais (em que o voto de cada vereador fica registrado) de projetos, emendas, subemendas, "
                "substitutivos, mensagens retificativas e vetos no Plenário desde 1º/1/2025, segundo o sistema de votações da "
                "Câmara. As chamadas de presença, as verificações de quórum, os requerimentos e as votações anuladas ou sem "
                "resultado não entram.",
                "Roll-call votes (where each councilor's vote is recorded) on bills, amendments, sub-amendments, substitute "
                "bills, corrective messages from the mayor and vetoes in the full City Council since January 1, 2025, according "
                "to the City Council's voting system. Attendance calls, quorum checks, requests and votes that were annulled or "
                "had no result are not included.")
# "PLE 016/26 - PROC. 0296/26 - EMENDA 01", "PLCE 012/25 - PROC. 0201/25 - VETO PARCIAL"
_PROJ = re.compile(r"^(PLL|PLE|PLCL|PLCE|PR|PELO|PDL)\s*(\d+)\s*/\s*(\d{2,4})\b")
_DECIDIU = re.compile(r"aprovad|rejeitad|veto mantido|veto derrubado")
_n = 0


def _ano(a: str) -> int:
    a = int(a)
    return a + 2000 if a < 100 else a


def _pagina(url: str) -> str:
    global _n
    B.esperar_vez(url, 1.0)
    try:
        t = baixar(url, tentativas=3, timeout=90).decode("utf-8", "replace")
    finally:
        B.pedido_feito(url)
    _n += 1
    return t


def _linhas(t: str) -> list[list]:
    """[data ISO, título, resultado, id] de cada linha da lista de votações."""
    corpo = t.split("<tbody", 1)[1].split("</tbody>", 1)[0] if "<tbody" in t else ""
    out = []
    for r in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", corpo):
        cels = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip() for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", r)]
        idm = re.search(r'href="/votacoes/(\d+)"', r)
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", cels[0]) if cels else None
        if m and idm and len(cels) >= 6:
            out.append([f"{m.group(3)}-{m.group(2)}-{m.group(1)}", cels[1], cels[5], idm.group(1)])
    return out


def _detalhe(t: str) -> dict:
    """O que foi votado, o placar, o resultado e o voto de cada vereador (página /votacoes/<id>)."""
    campos = {}
    for dt_, dd in re.findall(r"(?s)<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", t):
        campos[B.norm(re.sub(r"<[^>]+>", "", dt_))] = html.unescape(re.sub(r"<[^>]+>|\s+", " ", dd)).strip()
    votos = []
    tab = t.split('id="votos"', 1)[1] if 'id="votos"' in t else ""
    for r in re.findall(r"(?s)<tr>(.*?)</tr>", tab):
        cels = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip() for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", r)]
        if len(cels) >= 3 and cels[0]:
            votos.append([cels[0], cels[1], cels[2]])
    num = lambda k: int(campos.get(k) or 0) if (campos.get(k) or "0").isdigit() else 0  # noqa: E731
    return {"sessao": campos.get("sessao"), "proposicao": campos.get("proposicao"), "ementa": campos.get("ementa"),
            "tipo": campos.get("tipo de votacao"), "sim": num("sim"), "nao": num("nao"), "abst": num("abstencoes"),
            "resultado": campos.get("resultado"), "veto": "apreciação de veto" in t, "votos": votos}


def _entra(titulo: str, resultado: str | None) -> bool:
    """Votação de projeto (ou de emenda, veto...) que decidiu alguma coisa; requerimentos e votações anuladas, fora."""
    resto = " - ".join(titulo.split(" - ")[2:])
    return bool(_PROJ.match(titulo)) and not re.search(r"\bREQ\b|REQUERIMENTO|NULA", resto.upper()) \
        and bool(_DECIDIU.search(B.norm(resultado)))


def votacoes(chaves: dict[str, str], h: str):
    """(catálogo, {chave da pessoa: [[chave, voto], ...]}, escopo, fonte) das votações nominais desde 1º/1/2025, ou None
    se a primeira leitura não terminou nesta rodada (nada pela metade: fica o que já estava publicado). chaves = {nome sem
    acento: chave}."""
    from ._sapl import _prazo, voto_normal
    est = ler_json(ESTADO, {}) or {}
    lista, det = est.setdefault("lista", {}), est.setdefault("det", {})
    prazo = _prazo()
    n = 1
    try:
        while True:  # da página 1 até chegar a 2025 (primeira vez) ou a uma página só com votações já vistas
            linhas = _linhas(_pagina(f"{VOT}/votacoes?filtro=nominais&page={n}"))
            novas = [x for x in linhas if x[3] not in lista]
            for d, tit, res, i in linhas:
                lista[i] = [d, tit, res]
            if not linhas or linhas[-1][0] < B.INICIO or (est.get("completa") and not novas and n >= 2) or n > 400:
                break
            n += 1
            if prazo and time.time() > prazo - 120:
                raise TimeoutError("fim do tempo da rodada")
        est["completa"] = True
        tres_dias = (dt.date.fromisoformat(h) - dt.timedelta(days=3)).isoformat()  # as mais novas podem ser corrigidas
        recentes = {i for i, (d, _, _) in lista.items() if d >= tres_dias}
        faltam = sorted((i for i, (d, tit, res) in lista.items() if d >= B.INICIO and _entra(tit, res)
                         and (i not in det or i in recentes)), key=int)
        for k, i in enumerate(faltam):
            if prazo and time.time() > prazo - 120:
                raise TimeoutError("fim do tempo da rodada")
            det[i] = _detalhe(_pagina(f"{VOT}/votacoes/{i}"))
            if k % 25 == 24:
                salvar_json(ESTADO, est)
    except (TimeoutError, RuntimeError, OSError) as erro:
        salvar_json(ESTADO, est)
        log(f"  CMPA: votações pela metade ({type(erro).__name__}: {str(erro)[:120]}; {_n} pedidos): continuam na próxima rodada")
        return None
    salvar_json(ESTADO, est)
    cat, por = {}, {}
    sem_ligacao = set()
    for i, (d, tit, res) in lista.items():
        x = det.get(i)
        if d < B.INICIO or not _entra(tit, res) or not x or B.norm(x.get("tipo")) != "nominal":
            continue
        pj = _PROJ.match(x.get("proposicao") or tit) or _PROJ.match(tit)
        sig, num, ano = pj.group(1), int(pj.group(2)), _ano(pj.group(3))
        oficial = {"Sim": x["sim"], "Não": x["nao"], "Abstenção": x["abst"]}
        brutos = []
        for nome, _, voto in x["votos"]:
            c = chaves.get(B.norm(re.sub(r"\s+", " ", nome)))
            brutos.append((c or f"?{nome}", voto_normal(voto)))
            if not c:
                sem_ligacao.add(nome)
        votos = B.votos_unicos(brutos, oficial)
        contado = {k: sum(1 for v in votos.values() if v == k) for k in oficial}
        ementa = re.sub(r"^\d{3}\.\d{5}/\d{4}-\d{2}\s*-\s*", "", x.get("ementa") or "").strip()
        desc = f"{x.get('proposicao') or tit}: {ementa}" if ementa else (x.get("proposicao") or tit)
        if x.get("veto"):
            desc = "Esta votação é uma apreciação de veto. Nesse caso, vota-se novamente a proposição vetada. " + desc
        chave = f"cmpa-vot:{i}"
        item = {"data": d, "proposta": f"{sig} {num}/{ano}", "propostaId": f"cmpa:{sig}-{num}-{ano}", "descricao": desc,
                "resultado": x.get("resultado") or res, "placar": dict(oficial, total=sum(oficial.values())),
                "url": f"{VOT}/votacoes/{i}"}
        if contado != oficial:
            item["aviso"] = {"oficial": oficial, "contado": contado}
        cat[chave] = item
        for c, vt in votos.items():
            if not str(c).startswith("?"):
                por.setdefault(c, []).append([chave, vt])
    for lst in por.values():
        lst.sort(key=lambda kv: (cat[kv[0]]["data"], kv[0]), reverse=True)
    if sem_ligacao:
        log(f"  CMPA: votos de quem não está no cargo hoje (ficam fora): {len(sem_ligacao)} nomes")
    f = fonte(CASA["casa"], "Sistema de votações da Câmara: votações nominais em Plenário", f"{VOT}/votacoes?filtro=nominais", h)
    return cat, por, ESCOPO_VOTOS, f


def coletar() -> dict:
    global _n
    _n = 0
    h = hoje()
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    lista = t.split('id="titulares"', 1)[1].split("</ul>", 1)[0]
    pessoas = []
    for href, foto, alt, nome in re.findall(r'<a href="(/vereadores/[^"]+)"><img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>\s*<h2>(.*?)</h2>', lista):
        nome = html.unescape(re.sub(r"<[^>]+>", "", nome)).strip()
        m = re.match(r"(.*?)\s*\(([^)]+)\)\s*$", nome)
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": m.group(1) if m else nome, "partido": m.group(2) if m else None,
                        "foto": foto, "url": SITE + href})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores em exercício (portal oficial)", f"{SITE}/vereadores", h)
    chaves = {B.norm(re.sub(r"\s+", " ", p["nome"])): p["chave"] for p in pessoas}
    vot = votacoes(chaves, h)
    notas = [("As propostas dos vereadores não entram neste site: a Câmara publica as proposições só no sistema de processos "
              "do site (páginas HTML), sem arquivo nem API de dados abertos.",
              "Councilors' bills are not included on this site: the City Council publishes its bills only as web pages in its "
              "case system, with no open data file or API."),
             ("Os gastos do mandato de cada vereador não entram neste site: o Portal Transparência da Câmara mostra os gastos "
              "de um gabinete por mês, numa consulta da página, sem um arquivo de dados abertos com os de todos os gabinetes.",
              "Each councilor's office spending is not included on this site: the City Council's Transparency Portal shows the "
              "spending of one office per month, through a search on the page, with no open data file covering all offices.")]
    r = B.so_lista(IBGE, UF, CASA, pessoas, 35, notas, votacoes=vot, manter_votos=True)
    r["requisicoes"] = _n
    return r
