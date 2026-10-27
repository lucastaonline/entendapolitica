"""Câmara Municipal do Recife (PE): as votações nominais do Plenário, pela API JSON pública do SAGL
(https://publico.recife.pe.leg.br/@@sessoes).

A lista de quem está no cargo fica a dos eleitos em 2024 (TSE): a API lista os titulares e os suplentes que assumiram, mas não
diz quais titulares estão de licença (nota da Câmara). Os votos entram no perfil de quem a página da cidade mostra (eleitos
em 2024), ligado pelo nome ao candidato do TSE; os de suplentes que assumiram ficam fora.

Votações: as reuniões plenárias desde 1º/1/2025 (ordinárias e extraordinárias, uma lista por tipo e ano) e as votações de
cada uma ("@id_votacao": o que foi votado, o turno, a apuração e os vereadores de cada voto). Entram as nominais de projetos,
emendas, substitutivos e vetos que decidiram alguma coisa (aprovado, rejeitado, veto mantido ou derrubado); requerimentos,
indicações, moções e votações sem a lista de votos ficam fora. O que já foi lido fica em .cache/camaras/2611606/votos.json
(a primeira leitura, umas 200 reuniões, pode levar mais de uma rodada; até terminar, ficam publicadas as votações de antes,
nada pela metade); depois, só as reuniões novas e as dos últimos 7 dias.
"""
import datetime as dt
import json
import re
import time

from comum import baixar, fonte, hoje, ler_json, log, salvar_json

from . import _base as B

IBGE, UF = "2611606", "PE"
API = "https://publico.recife.pe.leg.br"
SITE = "https://www.recife.pe.leg.br"
CASA = {"casa": "Câmara Municipal do Recife", "casa_en": "Recife City Council", "sigla": "CMR", "site": SITE,
        "sistema": "SAGL (API JSON)", "api": f"{API}/@@sessoes"}
TIPOS_SESSAO = (1, 2, 9)  # Ordinária, Extraordinária, Convocação Extraordinária
ESTADO = B.PASTA_CACHE / IBGE / "votos.json"
ESCOPO_VOTOS = ("Votações nominais (em que o voto de cada vereador fica registrado) de projetos, emendas, substitutivos e vetos "
                "no Plenário desde 1º/1/2025, segundo o sistema oficial da Câmara (SAGL). Votações de requerimentos, "
                "indicações e moções, e as que não têm a lista de votos, não entram.",
                "Roll-call votes (where each councilor's vote is recorded) on bills, amendments, substitute bills and vetoes in "
                "the full City Council since January 1, 2025, according to the City Council's official system (SAGL). Votes on "
                "requests, recommendations and motions, and votes without the list of how each member voted, are not included.")
_PROJ = re.compile(r"^(projeto|proposta de emenda|emenda|subemenda|substitutivo|veto|redacao final)")
_DECIDIU = re.compile(r"aprovad|rejeitad|veto mantido|veto derrubado|mantid|derrubad")
VOTOS = (("favoravel", "Sim"), ("contrario", "Não"), ("abstencao", "Abstenção"), ("ausente", "NCom"), ("presidencia", "PS"))
_n = 0


def _json(url: str):
    global _n
    B.esperar_vez(url, 1.0)
    try:
        b = baixar(url, tentativas=3, timeout=120, headers={"Accept": "application/json"})
    finally:
        B.pedido_feito(url)
    _n += 1
    return json.loads(b.decode("utf-8"))


def _menos(h: str, dias: int) -> str:
    return (dt.date.fromisoformat(h) - dt.timedelta(days=dias)).isoformat()


def _itens(d: dict) -> list[dict]:
    """As votações nominais de uma reunião que têm a lista de votos (as outras não servem para o perfil)."""
    out = []
    for it in d.get("items") or []:
        if B.norm(it.get("tipo_votacao")) != "nominal":
            continue
        for ap in it.get("apuracao") or []:
            grupos = (ap.get("votos") or [{}])[0] or {}
            votos = [[str(v.get("id")), v.get("title"), v.get("description"), ((v.get("partido") or [{}])[0] or {}).get("token"), codigo]
                     for campo, codigo in VOTOS for v in grupos.get(campo) or []]
            if votos:
                out.append({"materia": str(it.get("id")), "titulo": it.get("title"), "ementa": it.get("description"),
                            "turno": it.get("turno"), "resultado": ap.get("resultado"), "sim": ap.get("favoravel") or 0,
                            "nao": ap.get("contrario") or 0, "abst": ap.get("abstencao") or 0, "votos": votos})
    return out


def votacoes(tse: "B.Tse", h: str):
    """(catálogo, {id no site: [[chave, voto], ...]}, escopo, fonte) ou None se a leitura não terminou nesta rodada."""
    from ._sapl import _prazo
    est = ler_json(ESTADO, {}) or {}
    ses, det, listas = est.setdefault("sessoes", {}), est.setdefault("det", {}), est.setdefault("listas", {})
    prazo = _prazo()
    ano_h = int(h[:4])
    try:
        for ano in range(int(B.INICIO[:4]), ano_h + 1):
            for t in TIPOS_SESSAO:
                k = f"{t}-{ano}"
                if ano < ano_h and (listas.get(k) or "") >= _menos(h, 30):
                    continue  # ano passado: a lista é lida de novo uma vez por mês
                for s in _json(f"{API}/@@sessoes/tipo/{t}/ano/{ano}").get("items") or []:
                    if B.INICIO <= (s.get("date") or "") <= h:
                        ses[str(s["id"])] = [s["date"], s.get("title")]
                listas[k] = h
        recentes = _menos(h, 7)  # as reuniões dos últimos dias podem ganhar votações depois
        faltam = sorted((i for i, (d, _) in ses.items() if i not in det or d >= recentes), key=int)
        for k, i in enumerate(faltam):
            if prazo and time.time() > prazo - 120:
                raise TimeoutError("fim do tempo da rodada")
            det[i] = _itens(_json(f"{API}/@@sessoes/id/{i}/votacao"))
            if k % 20 == 19:
                salvar_json(ESTADO, est)
    except (TimeoutError, RuntimeError, OSError, ValueError) as erro:
        salvar_json(ESTADO, est)
        log(f"  CMR: votações pela metade ({type(erro).__name__}: {str(erro)[:120]}; {_n} pedidos): continuam na próxima rodada")
        return None
    salvar_json(ESTADO, est)
    validos = tse.ids_eleitos()
    pessoa: dict[str, str | None] = {}
    cat, por = {}, {}
    for sid, itens in det.items():
        data = (ses.get(sid) or [None])[0]
        if not data or data < B.INICIO:
            continue
        vistos: dict[str, int] = {}
        for it in itens:
            if not _PROJ.match(B.norm(it.get("titulo"))) or not _DECIDIU.search(B.norm(it.get("resultado"))):
                continue
            n = vistos[it["materia"]] = vistos.get(it["materia"], 0) + 1
            chave = f"cmr-vot:{sid}-{it['materia']}" + (f"-{n}" if n > 1 else "")
            oficial = {"Sim": it["sim"], "Não": it["nao"], "Abstenção": it["abst"]}
            brutos = []
            for vid, titulo, descr, partido, voto in it["votos"]:
                if vid not in pessoa:
                    pid, cand = tse.casar(f"sagl-{vid}", [titulo, descr], B.partido(partido))
                    pessoa[vid] = pid if cand and pid in validos else None
                brutos.append((pessoa[vid] or f"?{vid}", voto))
            votos = B.votos_unicos(brutos, oficial)
            contado = {k: sum(1 for v in votos.values() if v == k) for k in oficial}
            ementa = re.sub(r"\s+", " ", it.get("ementa") or "").strip()
            desc = f"{ementa} (Turno: {it['turno']})" if ementa and it.get("turno") else ementa or None
            x = {"data": data, "proposta": re.sub(r"\s+", " ", it.get("titulo") or "").strip() or None,
                 "propostaId": f"cmr:{it['materia']}", "descricao": desc, "resultado": it.get("resultado"),
                 "placar": dict(oficial, total=sum(oficial.values())),
                 "url": f"{API}/consultas/materia/materia_mostrar_proc?cod_materia={it['materia']}"}
            if contado != oficial:
                x["aviso"] = {"oficial": oficial, "contado": contado}
            cat[chave] = x
            for pid, vt in votos.items():
                if not str(pid).startswith("?"):
                    por.setdefault(pid, []).append([chave, vt])
    for lst in por.values():
        lst.sort(key=lambda kv: (cat[kv[0]]["data"], kv[0]), reverse=True)
    f = fonte(CASA["casa"], "SAGL: reuniões plenárias e votações nominais (API pública)", f"{API}/@@sessoes", h)
    return cat, por, ESCOPO_VOTOS, f


def coletar() -> dict:
    global _n
    _n = 0
    h = hoje()
    CASA["fonte"] = fonte(CASA["casa"], "SAGL: reuniões plenárias (API pública)", f"{API}/@@sessoes", h)
    tse = B.Tse(IBGE, UF)
    vot = votacoes(tse, h)
    notas = [("A lista de vereadores desta página é a dos eleitos em 2024 (TSE): o sistema da Câmara (SAGL) lista os titulares "
              "e os suplentes que assumiram, mas não diz quais titulares estão de licença.",
              "The list of councilors on this page is the one of those elected in 2024 (TSE): the City Council's system (SAGL) "
              "lists the full members and the substitutes who took office, but does not say which full members are on leave."),
             ("Os gastos do mandato de cada vereador não entram neste site: a Câmara publica a verba indenizatória (CEAP) num "
              "sistema de consulta (ceap.recife.pe.leg.br), feito para pesquisar na tela, sem arquivo de dados abertos.",
              "Each councilor's office spending is not included on this site: the City Council publishes its office allowance "
              "(CEAP) in a search system (ceap.recife.pe.leg.br), made for searching on screen, with no open data file.")]
    extras = {}
    if vot:
        cat, por, escopo, f_vot = vot
        for pid, lst in por.items():
            extras[pid] = {"fontes": [f_vot], "votacoes": B.bloco_votacoes(lst, escopo, f_vot, IBGE)}
    else:  # a leitura não terminou nesta rodada: ficam as votações já publicadas
        cat, blocos = B.votos_publicados(IBGE)
        extras = {pid: {"fontes": [b.get("fonte")], "votacoes": b} for pid, b in blocos.items()}
    cobertura = {"lista": False, "propostas": False, "votacoes": bool(extras), "gastos": False}
    r = B.salvar(IBGE, UF, CASA, [], extras, cobertura, notas, oficial=False, ids_validos=tse.ids_eleitos(),
                 votacoes=cat if extras else None)
    r["requisicoes"] = _n
    if tse.sem_ligacao:
        log(f"  CMR: votos sem ligação com os eleitos de 2024 (suplentes que assumiram, ficam fora): {len(tse.sem_ligacao)}")
    log(f"  CMR: {len(extras)} eleitos de 2024 com votações nominais, {r.get('votacoes', 0)} votações, {_n} pedidos")
    return r
