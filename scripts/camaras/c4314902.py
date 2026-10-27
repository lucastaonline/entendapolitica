"""Câmara Municipal de Porto Alegre (RS): a lista oficial de vereadores em exercício (www.camarapoa.rs.gov.br/vereadores), as
propostas de cada vereador e da prefeitura desde 1º/1/2025 (consulta de projetos do site da Câmara; leitura e situação em
scripts/camaras/_cmpa.py), os gastos da cota mensal de cada gabinete (Portal Transparência da Câmara) e as votações
nominais do Plenário (sistema de votações da Câmara, votacoes.camarapoa.rs.gov.br).

A página de vereadores separa quem está no cargo ("titulares", com os suplentes que assumiram) de quem está de licença.

Votações: a lista das nominais (20 por página, da mais nova para a mais antiga) e a página de cada uma (o que foi votado,
o placar, o resultado e o voto de cada vereador, pelo nome). Entram as de projetos, emendas, subemendas, substitutivos,
mensagens retificativas e vetos desde 1º/1/2025; chamadas de presença, verificações de quórum, requerimentos e votações
anuladas ou sem resultado ficam fora. O que já foi lido fica em .cache/camaras/4314902/votos.json: a primeira leitura
(umas 750 páginas, 1 s entre elas: uns 15 minutos) pode levar mais de uma rodada; até terminar, ficam publicadas as votações
de antes (nada pela metade). Depois, só as novas.

Propostas e gastos (frente capitais-b-r6, 27/10/2026): primeira carga ~1.750 pedidos (~50 minutos); depois, por dia, os 7
CSV da busca, as páginas dos processos que tiveram tramitação nova e os 3 meses mais recentes dos gastos. O site da Câmara
não aceita o acesso do robô do GitHub (servidores nos EUA): Porto Alegre é atualizada de um computador no Brasil
(scripts/atualizar_do_brasil.py). Se o site não responder, o coletor lança a exceção e os arquivos publicados ficam como
estavam.
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
        "sistema": "Portal oficial (HTML), consulta de projetos (CSV e páginas), Portal Transparência e sistema de votações",
        "sic": "https://transparencia.camarapoa.rs.gov.br/acesso_a_informacao"}
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


def vereadores() -> list[dict]:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    lista = t.split('id="titulares"', 1)[1].split("</ul>", 1)[0]
    pessoas = []
    for href, foto, alt, nome in re.findall(r'<a href="(/vereadores/[^"]+)"><img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>\s*<h2>(.*?)</h2>', lista):
        nome = html.unescape(re.sub(r"<[^>]+>", "", nome)).strip()
        m = re.match(r"(.*?)\s*\(([^)]+)\)\s*$", nome)
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": m.group(1) if m else nome, "partido": m.group(2) if m else None,
                        "foto": foto, "url": SITE + href})
    return pessoas


# ------------------------------------------------ propostas e gastos (frente capitais-b-r6)
ESCOPO = (B.ESCOPO + ", segundo a consulta de projetos da Câmara (a data é a da abertura do processo).",
          B.ESCOPO_EN + ", according to the City Council's bills search (the date is when the case was opened).")
NOTA_PROPOSTAS = (
    "As propostas vêm da consulta de projetos do site da Câmara (a exportação em CSV da busca e a página de cada processo): o "
    "primeiro nome em \"Autores\" é o autor principal e os outros assinaram junto; quando o processo diz só \"e outros\", "
    "entram só os nomes escritos. A situação vem da página do processo (situação, situação plenária, o documento da lei e o "
    "veto). Projetos da Mesa Diretora e das comissões não entram no perfil de nenhum vereador.",
    "Bills come from the City Council's bills search (the search's CSV export and each case's page): the first name under "
    "\"Authors\" is the main author and the others co-signed; when the case only says \"and others\", only the written names "
    "are included. The status comes from the case page (status, status in the full Council, the law document and the veto). "
    "Bills by the City Council's board or committees are not shown on any councilor's profile.")
NOTA_GASTOS = (
    "Os gastos do mandato são os da cota mensal de cada gabinete (QBM) no Portal Transparência da Câmara: reprografia, "
    "material de expediente, indenização pelo uso de veículo particular, viagens, telefone, internet e correio. Entram os "
    "meses desde janeiro de 2025 em que a pessoa ocupava o gabinete, com a mesma conta da página oficial (\"Valores "
    "utilizados\"). Quem não usou a cota nesse tempo fica sem esta parte no perfil. Os gastos das bancadas e das comissões "
    "não entram no perfil de ninguém.",
    "Office spending is each office's monthly allowance (QBM) on the City Council's Transparency Portal: photocopies, office "
    "supplies, reimbursement for using a private vehicle, travel, phone, internet and postage. The months since January 2025 "
    "in which the person held the office are included, counted the same way as on the official page (\"amounts used\"). "
    "People who did not use the allowance in that time have no spending section on their profile. Spending by party caucuses "
    "and committees is not shown on anyone's profile.")
_ORGAO = re.compile(r"^(mesa|comiss|tribunal|bancada|lideranca|frente|procuradoria|defensoria|ministerio|governo|executivo|"
                    r"prefeit|poder)")
_EXECUTIVO = re.compile(r"^(governo municipal|executivo|prefeit|poder executivo)")
# nomes conferidos à mão (como o sistema escreve -> id do vereador, ou None = não é ninguém da lista de hoje)
AUTORES_MANUAL: dict[str, str | None] = {}


def coletar() -> dict:
    global _n
    _n = 0
    t0 = time.time()
    h = hoje()
    from . import _cmpa as M
    from . import _paginas as P
    import collections
    import regional
    pessoas = vereadores()
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores em exercício (portal oficial)", f"{SITE}/vereadores", h)
    membros, extras, por_chave, tse = P.lista(IBGE, UF, CASA, pessoas, 35)

    # ------------------------------------------------ propostas (consulta de projetos)
    rede = P.Rede(IBGE, M.PAUSA)
    e = P.ler_estado(IBGE)
    try:
        M.ler_propostas(rede, e, h)
    except P.SemTempo as motivo:
        P.guardar_estado(IBGE, e)
        log(f"  CMPA: propostas pela metade ({motivo}; {rede.resumo(t0)}): continuam na próxima rodada; nada foi gravado")
        return {"ok": True, "pendente": True, "etapa": "propostas", "requisicoes": rede.n}
    except Exception:
        P.guardar_estado(IBGE, e)  # site fora do ar no meio: o que já foi lido fica para a próxima rodada
        raise
    itens = e.get("itens") or {}
    protegidos = [m["nome"] for m in membros] + [m.get("_urna") or "" for m in membros]
    nomes = P.Nomes(membros, AUTORES_MANUAL)
    pref_id, pref_ini = P.inicio_prefeito(IBGE, UF)
    por_id: dict[str, list] = {m["id"]: [] for m in membros}
    do_pref, fora = [], collections.Counter()
    for k, x in sorted(itens.items()):
        if not x.get("pid"):
            continue
        st, situ, d_st, lei = M.situacao(x)
        comum = M.TIPOS[x["tipo"]]
        data = (x.get("pag") or {}).get("abertura")
        texto = (x.get("pag") or {}).get("autores") or x.get("autores_csv")
        lista_aut, _ = M.autores(texto, protegidos)
        pid_prop = f"cm{IBGE}:{x['pid']}"
        vistos = set()
        for i, a in enumerate(lista_aut):
            n = re.sub(r"^ver(eador|a|\.|ª|º|\s|\(|\))*\s*", "", B.norm(a))
            if _EXECUTIVO.match(n):
                if i == 0 and comum in ("PL", "PLP", "PELO") and (data or "") >= pref_ini and pref_id:
                    do_pref.append(P.proposta(pid_prop, M.sigla(x), comum, data, M.ementa(x), situ, M.url_processo(x),
                                              "autor", st, d_st, lei))
                continue
            if _ORGAO.match(n):
                continue
            pid = nomes.id(a)
            if not pid:
                fora[a] += 1
                continue
            if pid in vistos or pid not in por_id:
                continue
            vistos.add(pid)
            por_id[pid].append(P.proposta(pid_prop, M.sigla(x), comum, data, M.ementa(x), situ, M.url_processo(x),
                                          "autor" if i == 0 else "coautor", st, d_st, lei))
    if fora:
        log(f"  CMPA: autores fora da lista oficial de hoje ({len(fora)} nomes): "
            + ", ".join(f"{n} ({q})" for n, q in fora.most_common(12)))
    for m in membros:
        f_prop = fonte(CASA["casa"], f"Consulta de projetos: projetos de {m['nome']}", f"{SITE}/processos", h)
        x = extras[m["id"]]
        x["propostas"] = regional.bloco_propostas(por_id[m["id"]], ESCOPO[0], ESCOPO[1], f_prop)
        x["fontes"].append(f_prop)
    prefeito = None
    if pref_id:
        esc = P.escopo_prefeito(pref_ini, "a consulta de projetos da Câmara", "the City Council's bills search",
                                "projetos de lei, de lei complementar e de emenda à Lei Orgânica",
                                "ordinary and complementary bills and amendments to the city's Organic Law")
        f_pref = fonte(CASA["casa"], "Consulta de projetos: projetos do Executivo (PLE e PLCE)", f"{SITE}/processos", h)
        prefeito = (pref_id, {"propostas": regional.bloco_propostas(do_pref, esc[0], esc[1], f_pref), "fontes": [f_pref]})

    # ------------------------------------------------ gastos (cota mensal dos gabinetes, Portal Transparência)
    rede_g = P.Rede(IBGE, 1.0)
    eg = P.ler_estado(IBGE, "gastos")
    tem_gastos = False
    try:
        meses = M.ler_gastos(rede_g, eg, h)
        por_gab = M.gastos_por_gabinete(meses)
        nomes_g = P.Nomes(membros, AUTORES_MANUAL)
        por_pessoa: dict[str, dict] = {}
        sem_gab = collections.Counter()
        for gab, por_mes in por_gab.items():
            if not gab.lower().startswith("gab."):
                continue  # bancadas e comissões
            pid = nomes_g.id(re.sub(r"(?i)^gab\.\s*", "", gab))
            if not pid or pid not in por_id:
                sem_gab[gab] += 1
                continue
            alvo = por_pessoa.setdefault(pid, {})
            for mes, tipos in por_mes.items():
                t = alvo.setdefault(mes, {})
                for tp, v in tipos.items():
                    t[tp] = t.get(tp, 0.0) + v
        if sem_gab:
            log(f"  CMPA: gabinetes de quem não está no cargo hoje (ficam fora): {', '.join(sorted(sem_gab))}")
        ano_h, mes_h = int(h[:4]), int(h[5:7])
        f_g = fonte(CASA["casa"], f"Portal Transparência: gastos de vereadores (cota mensal dos gabinetes, QBM), de janeiro de "
                    f"{B.INICIO[:4]} a {M.MESES_PT[mes_h - 1]} de {ano_h}", f"{M.TRANSPARENCIA}/gastos/vereadores", h)
        for pid, por_mes in por_pessoa.items():
            b = M.bloco_gastos(por_mes, f_g)
            if b:
                extras[pid]["gastos"] = b
                extras[pid]["fontes"].append(f_g)
                tem_gastos = True
    except P.SemTempo as motivo:
        P.guardar_estado(IBGE, eg, "gastos")
        log(f"  CMPA: gastos pela metade ({motivo}): continuam na próxima rodada; nada foi gravado")
        return {"ok": True, "pendente": True, "etapa": "gastos", "requisicoes": rede.n + rede_g.n}
    P.limpar_membros(membros)

    # ------------------------------------------------ votações nominais (sistema de votações)
    chaves = {B.norm(re.sub(r"\s+", " ", p["nome"])): p["chave"] for p in pessoas}
    vot = votacoes(chaves, h)
    if vot is not None:
        catalogo, votos_chave, escopo_v, f_vot = vot
        for chave, lst in votos_chave.items():
            pid = por_chave.get(chave)
            if pid in extras and lst:
                extras[pid]["votacoes"] = B.bloco_votacoes(lst, escopo_v, f_vot, IBGE)
                extras[pid]["fontes"].append(f_vot)
    else:  # a leitura das votações não terminou nesta rodada: ficam as publicadas antes
        catalogo, blocos = B.votos_publicados(IBGE)
        for pid, x in extras.items():
            if pid in blocos:
                x["votacoes"] = blocos[pid]
                x["fontes"].append(blocos[pid].get("fonte"))
    com_votos = any(x.get("votacoes") for x in extras.values())

    notas = [NOTA_PROPOSTAS] + ([NOTA_GASTOS] if tem_gastos else [])
    cobertura = {"lista": True, "propostas": True, "votacoes": com_votos, "gastos": tem_gastos}
    r = B.salvar(IBGE, UF, CASA, membros, extras, cobertura, notas, ESCOPO, prefeito=prefeito,
                 votacoes=catalogo if com_votos else None)
    r["requisicoes"] = _n + rede.n + rede_g.n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMPA: {len(membros)} no cargo, {r['propostas']} propostas de {sum(1 for v in por_id.values() if v)} vereadores, "
        f"prefeito {len(do_pref)} projetos, {r.get('vereadoresComGastos', 0)} com gastos, {r.get('votacoes', 0)} votações; "
        f"{r['requisicoes']} pedidos, {time.time() - t0:.0f} s")
    return r
