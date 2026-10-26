"""Assembleia Legislativa do Estado de Goiás (Alego).

Lista oficial: https://portal.al.go.leg.br/deputados/em-exercicio (nome, partido, página de cada um: /deputados/perfil/<id>,
com nome civil, e-mail e foto). Em outubro de 2026 a página trazia 43 nomes para 41 vagas; a página oficial "Deputados
fora do exercício" (/deputados/fora-exercicio) mostra quem saiu (falecimento, renúncia, cassação, suplente que saiu com a
volta do titular). Quando a lista passa de 41, o coletor tira quem aparece lá com saída definitiva sem data de retorno,
da saída mais recente para a mais antiga, até ficar com 41 (e avisa no log).
Votações nominais: dados abertos do Portal da Transparência da Alego (JSON por mês: voto de cada deputado e o resumo de
cada votação), https://transparencia.al.go.leg.br/gestao-parlamentar/painel-votacao-parlamentar.
Gastos: verba indenizatória (API do Portal da Transparência: valor indenizado por deputado e por mês, e o detalhamento
por grupo de despesa do ano mais recente).
Propostas: NÃO entram. O sistema de processo legislativo da Alego (SPL, https://alegodigital.al.go.leg.br/spl/) proíbe
robôs no robots.txt ("Disallow: /"), e a lista de processos do Portal da Transparência (Opine Cidadão) parou em 2023.
Governador (gov-GO): leis sancionadas, pelos dados abertos da Casa Civil de Goiás (governo()).
"""
from __future__ import annotations

import datetime as dt
import re
import time

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, salvar_json, sem_acento, sem_mudar_data, DADOS

from ._nco_comum import (INICIO, Rede, casar_membros, conferir_virada, gravar, legislatura_por_data, limpa_civil, limpa_nome,
                         membro, nome_civil, partido_sigla, sigla_votacao, texto_html)

SITE = "https://portal.al.go.leg.br"
TRANSP = "https://transparencia.al.go.leg.br"
API = f"{TRANSP}/api/transparencia"
VEICULO = "Assembleia Legislativa de Goiás (Alego)"
VAGAS = 41
# saídas definitivas na página "Deputados fora do exercício" (sem acento, minúsculas)
SAIDAS = r"falecimento|renuncia|cassacao|perda (do|de) mandato|retorno do titular|suplencia"
TSE_MANUAL: dict[str, str] = {}
VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "obstrucao": "Obstrução"}


def _nome_voto(n: str) -> set[str]:
    return set(regional.palavras((n or "").replace("ª", "a").replace("º", "o")))


# ---------------------------------------------------------------- quem está no cargo
def lista_oficial(rede: Rede) -> tuple[list[dict], list[str]]:
    em = rede.texto(f"{SITE}/deputados/em-exercicio", "em-exercicio.html", 20)
    lista = []
    for r in re.findall(r'<tr data-target="search.filterable"[^>]*>(.*?)</tr>', em, re.S):
        m = re.search(r'href=/deputados/perfil/(\d+)>(.*?)</a>', r)
        p = re.search(r'data-title="Partido">(.*?)</td>', r, re.S)
        if m:
            partido = texto_html(p.group(1)) if p else ""
            sig = re.search(r"\(([^)]+)\)\s*$", partido)
            lista.append({"id": m.group(1), "nome": texto_html(m.group(2)), "partido": sig.group(1) if sig else partido})
    if len(lista) < VAGAS - 5:
        raise RuntimeError(f"GO: a página de deputados em exercício mudou (só {len(lista)} pessoas)")
    tirados = []
    if len(lista) > VAGAS:
        fora = texto_html(re.sub(r"<script.*?</script>|<style.*?</style>", " ",
                                 rede.texto(f"{SITE}/deputados/fora-exercicio", "fora-exercicio.html", 20), flags=re.S))
        ultima: dict[str, tuple] = {}
        for nome, tipo, data, volta in re.findall(r"Nome:\W*([^:]+?)\s+Tipo do afastamento:\W*(.+?)\s+Data do afastamento:\W*"
                                                  r"(\d\d/\d\d/\d{4})\s+Data de retorno:\W*(\d\d/\d\d/\d{4})?", fora):
            k, d = chave_nome(nome), data_iso(data)
            if k not in ultima or d > ultima[k][0]:
                ultima[k] = (d, sem_acento(tipo.lower()), volta, tipo.strip().lower())
        sair = sorted(((u[0], l) for l in lista for u in [ultima.get(chave_nome(l["nome"]))]
                       if u and re.search(SAIDAS, u[1]) and not u[2]), key=lambda x: x[0], reverse=True)
        for d, l in sair:
            if len(lista) <= VAGAS:
                break
            lista.remove(l)
            tirados.append(f"{l['nome']} ({ultima[chave_nome(l['nome'])][3]} em {d[8:10]}/{d[5:7]}/{d[:4]})")
        if tirados:
            log(f"  GO: a página 'em exercício' tinha {len(lista) + len(tirados)} nomes; tirados pela página 'fora do exercício': "
                f"{'; '.join(tirados)}")
        if len(lista) != VAGAS:
            log(f"  GO: ATENÇÃO: {len(lista)} pessoas na lista oficial (a Casa tem {VAGAS} vagas)")
    for l in lista:
        html = rede.texto(f"{SITE}/deputados/perfil/{l['id']}", f"perfil/{l['id']}.html", 24 * 7)
        txt = texto_html(re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S))
        m = re.search(r"Nome Civil:\s*(.+?)\s+(?:Número do Gabinete|Telefones|E-mail|Atividade parlamentar)", txt)
        l["civil"] = m.group(1).strip() if m else None
        f = re.search(r'src="(https://saba\.al\.go\.leg\.br/v1/view/portal/public/[^"?]+)', html)
        l["foto"] = f.group(1) if f else None
        e = re.search(r"mailto:([^\"'>\s]+)", html)
        l["email"] = e.group(1) if e else None
    return lista, tirados


# ---------------------------------------------------------------- meses desde fevereiro de 2023
def _meses() -> list[tuple[int, int]]:
    a, m = int(INICIO[:4]), int(INICIO[5:7])
    h = dt.date.fromisoformat(hoje())
    out = []
    while (a, m) <= (h.year, h.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _recente(a: int, m: int, meses: int = 3) -> bool:
    h = dt.date.fromisoformat(hoje())
    return (h.year * 12 + h.month) - (a * 12 + m) < meses


def _fresco(rede: Rede, nome: str, horas: float) -> bool:
    arq = rede.pasta / nome
    return arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < horas


# ---------------------------------------------------------------- votações nominais
def votacoes(rede: Rede, membros: list[dict]) -> dict[str, dict]:
    """{id da pessoa: bloco "votacoes"}; grava o catálogo dados/votacoes/alego.json (cada votação uma vez)."""
    catalogo, por_pessoa, sem_nome = {}, {}, {}
    indice = [(m["id"], set(regional.palavras(m["nome"]))) for m in membros]
    liga: dict[str, str | None] = {}

    def quem(nome: str) -> str | None:
        k = chave_nome(nome)
        if k not in liga:
            alvo = _nome_voto(nome)
            achados = [pid for pid, p in indice if p and alvo and (p == alvo or ((p <= alvo or alvo <= p) and len(p & alvo) >= 2)
                                                                     or (len(p & alvo) == 1 and min(len(p), len(alvo)) == 1 and len(next(iter(p & alvo))) >= 4))]
            liga[k] = achados[0] if len(set(achados)) == 1 else None
        return liga[k]

    for a, m in _meses():
        nome = f"votos/{a}-{m:02d}.json"
        mes = rede.estado(nome) if _fresco(rede, nome, 20 if _recente(a, m) else 24 * 30) else None
        if mes is None:
            det = rede.json(f"{API}/votacoes.json?todos=true&ano={a}&mes={m}&tipo=detalhes")
            res = rede.json(f"{API}/votacoes.json?todos=true&ano={a}&mes={m}&tipo=resumo")
            mes = {"res": {}, "v": {}}
            for x in res or []:
                assunto = re.split(r"ASSUNTO\s*-\s*", x.get("ementa_projeto") or "", maxsplit=1)
                mes["res"][str(x["pauta_id"])] = {"d": x.get("data_sessao"), "p": re.sub(r"\s+", " ", x.get("numero_processo_projeto") or "").strip(),
                                                   "e": re.sub(r"\s+", " ", assunto[-1]).strip(), "r": (x.get("resultado_votacao") or "").strip(),
                                                   "t": x.get("tipo_votacao"), "s": x.get("nome_sessao")}
            for x in det or []:
                if (x.get("tipo_votacao") or "").upper() != "NOMINAL":
                    continue
                mes["v"].setdefault(str(x["pauta_id"]), {})[chave_nome(x.get("parlamentar"))] = x.get("tipo_voto")
            rede.guardar(mes, nome)
        for pauta, vs in mes["v"].items():
            r = mes["res"].get(pauta) or {}
            chave = f"alego-vot:{pauta}"
            oficial = r.get("p") or ""
            descricao = " – ".join(x for x in [r.get("e"), oficial] if x) or None
            catalogo[chave] = {"data": r.get("d"), "propostaId": None, "proposta": sigla_votacao(oficial), "descricao": descricao,
                               "resultado": r.get("r") or None, "url": f"{TRANSP}/gestao-parlamentar/painel-votacao-parlamentar"}
            for nome_v, voto in vs.items():
                pid = quem(nome_v)
                if not pid:
                    sem_nome[nome_v] = sem_nome.get(nome_v, 0) + 1
                    continue
                v = VOTO.get(sem_acento((voto or "").lower()).strip(), voto or "Outro")
                por_pessoa.setdefault(pid, {})[chave] = [chave, v, r.get("d") or ""]
    if sem_nome:
        log(f"  GO votações: nomes sem pessoa na lista de hoje (quem saiu): {sorted(sem_nome)[:12]}{'...' if len(sem_nome) > 12 else ''}")
    arq = DADOS / "votacoes" / "alego.json"
    fonte_v = fonte(VEICULO, "Votações nominais do Plenário (dados abertos do Portal da Transparência)",
                    f"{TRANSP}/gestao-parlamentar/painel-votacao-parlamentar")
    if catalogo:
        dados = {"votacoes": dict(sorted(catalogo.items(), key=lambda kv: (kv[1]["data"] or "", kv[0]), reverse=True)),
                 "fonte": fonte_v, "atualizado": hoje()}
        salvar_json(arq, sem_mudar_data(dados, arq))
    out = {}
    for pid, d in por_pessoa.items():
        lista = sorted(d.values(), key=lambda x: (x[2], x[0]), reverse=True)
        resumo = {"total": len(lista), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
        for _, v, _ in lista:
            resumo[v if v in resumo else "Outro"] += 1
        out[pid] = {"escopo": "Votações nominais (com o voto de cada deputado) no Plenário da Alego desde 1º/2/2023",
                    "escopo_en": "Roll-call votes (where each member's vote is recorded) in the full Alego since February 1, 2023",
                    "resumo": resumo, "fonte": fonte_v, "arquivo": "dados/votacoes/alego.json", "votos": [[c, v] for c, v, _ in lista]}
    log(f"  GO: {len(catalogo)} votações nominais; votos de {len(out)} deputados")
    return out


# ---------------------------------------------------------------- verba indenizatória
def _grupo(desc: str) -> str:
    """'02 -  COMUNICAÇÃO, TELEFONE E DADOS' -> 'Comunicação, telefone e dados'."""
    d = re.sub(r"^\s*\d+\s*-\s*", "", re.sub(r"\s+", " ", desc or "")).strip()
    return (d[:1].upper() + d[1:].lower()) if d else "Outros"


def gastos(rede: Rede, membros: list[dict], ids: dict[str, str]) -> dict[str, dict]:
    """{id da pessoa: bloco "gastos"} a partir da verba indenizatória (valor indenizado)."""
    por_dep: dict[str, dict] = {}
    for a, m in _meses():
        lista = rede.json(f"{API}/verbas_indenizatorias?ano={a}&mes={m}&pagina=1&por_pagina=200", f"vi/lista-{a}-{m:02d}.json",
                          20 if _recente(a, m) else 24 * 30)
        for x in lista or []:
            dep = str((x.get("deputado") or {}).get("id"))
            v = float(x.get("valor_indenizado") or 0)
            por_dep.setdefault(dep, {}).setdefault(a, {})[m] = v
    out = {}
    for m in membros:
        dep = ids.get(m["id"])
        anos = por_dep.get(dep) or {}
        if not anos:
            continue
        ano = max(anos)
        cats: dict[str, float] = {}
        for mes, total in sorted(anos[ano].items()):
            nome = f"vi/exibir-{dep}-{ano}-{mes:02d}.json"
            c = rede.estado(nome)
            if not c or abs(c.get("total", -1) - total) > 0.005:
                d = rede.json(f"{API}/verbas_indenizatorias/exibir?ano={ano}&mes={mes}&deputado_id={dep}")
                g = {}
                for gr in d.get("grupos") or []:
                    v = float(gr.get("valor_indenizado") or 0)
                    if v:
                        g[_grupo(gr.get("descricao"))] = g.get(_grupo(gr.get("descricao")), 0) + v
                c = {"total": float(d.get("valor_indenizado") or 0), "g": g}
                rede.guardar(c, nome)
            for k, v in c["g"].items():
                cats[k] = cats.get(k, 0) + v
        out[m["id"]] = {"ano": ano, "total": round(sum(anos[ano].values()), 2),
                        "porTipo": [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(cats.items(), key=lambda x: (-x[1], x[0]))],
                        "mandatoTotal": round(sum(sum(x.values()) for x in anos.values()), 2), "desde": INICIO[:7],
                        "nome": "Verba indenizatória", "nome_en": "Expense allowance (verba indenizatória)",
                        "meses": [f"{ano}-{min(anos[ano]):02d}", f"{ano}-{max(anos[ano]):02d}"],
                        "fonte": fonte(VEICULO, f"Verba indenizatória de {m['nome']} (Portal da Transparência)",
                                       f"{TRANSP}/gestao-parlamentar/verba-indenizatoria?deputado_id={dep}&ano={ano}")}
    return out


# ---------------------------------------------------------------- tudo
def coletar() -> dict:
    rede = Rede("alego", pausa=1.0)
    lista, tirados = lista_oficial(rede)
    casar = [{"chave": l["id"], "nome": limpa_nome(l["nome"]), "nomeCivil": limpa_civil(l.get("civil")),
              "partido": partido_sigla(l["partido"])} for l in lista]
    ligados, avisos = casar_membros("GO", casar, TSE_MANUAL)
    for a in avisos:
        log(f"  GO TSE: {a}")
    fonte_lista = fonte(VEICULO, "Deputados em exercício (página oficial)", f"{SITE}/deputados/em-exercicio")
    membros, ids, extras = [], {}, {}
    for l, c in zip(lista, casar):
        cand = ligados.get(c["chave"])
        pid = regional.id_pessoa("dest", "GO", cand, c["nome"])
        url = f"{SITE}/deputados/perfil/{l['id']}"
        membros.append(membro(pid, c["nome"], nome_civil(c["nomeCivil"], c["nome"], cand), c["partido"],
                              (cand or {}).get("genero"), l.get("foto"), url, bool(cand and cand["sit"] == "SUPLENTE")))
        ids[pid] = l["id"]
        extras[pid] = {"links": {"oficial": url, "email": l.get("email"), "redes": []},
                       "fontes": [fonte_lista, fonte(VEICULO, f"Perfil de {c['nome']} (página oficial)", url)]}
    vot = votacoes(rede, membros)
    gas = gastos(rede, membros, ids)
    for pid, x in extras.items():
        if pid in vot:
            x["votacoes"] = vot[pid]
            x["fontes"].append(vot[pid]["fonte"])
        if pid in gas:
            x["gastos"] = gas[pid]
            x["fontes"].append(gas[pid]["fonte"])
    cobertura = {"lista": True, "propostas": False, "votacoes": bool(vot), "gastos": bool(gas)}
    leg = legislatura_por_data("02-01")
    conferir_virada(rede, "GO", [l["id"] for l in lista], leg)
    notas = [
        ("As propostas de cada deputado não entram: o sistema de processo legislativo da Alego (SPL) proíbe consultas por "
         "robôs (robots.txt). Cada proposta pode ser consultada no próprio SPL, pelo site da Alego.",
         "Each deputy's bills are not included: the Alego legislative system (SPL) forbids queries by robots (robots.txt). "
         "Each bill can be looked up in the SPL itself, through the Alego website."),
        ("Gastos: verba indenizatória (valor indenizado), do Portal da Transparência da Alego.",
         "Spending: the expense allowance (verba indenizatória, amount reimbursed), from the Alego transparency portal."),
        GOV_NOTA,
    ]
    if tirados:
        notas.append(("A página oficial de deputados em exercício ainda trazia: " + "; ".join(tirados) +
                      ". Eles não aparecem aqui, segundo a página oficial de deputados fora do exercício.",
                      "The official page of deputies in office still listed people who, according to the official page of "
                      "deputies out of office, have left; they are not shown here."))
    r = gravar("GO", {"casa": "Assembleia Legislativa do Estado de Goiás", "casa_en": "Legislative Assembly of the State of Goiás",
                      "sigla": "Alego", "site": SITE}, membros, extras, cobertura, fonte_lista, notas, minimo=VAGAS - 5,
               legislatura=leg)
    log(f"  GO: {rede.pedidos} pedidos aos sites oficiais")
    try:
        governo(Rede("go-dadosabertos"))  # o robots.txt de dadosabertos.go.gov.br pede 10 s entre pedidos: a Rede respeita
    except Exception as e:  # o arquivo do governador de antes continua (se for do mesmo período)
        from . import _nco_gov as G
        log(f"  GO: ATENÇÃO: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
        G.descartar_se_velho("GO")
    return r


# ---------------------------------------------------------------- o que o governo do estado fez (perfil gov-GO)
# Leis: dados abertos da Casa Civil de Goiás (https://dadosabertos.go.gov.br, conjuntos "leis-ordinarias" e
# "leis-complementares"): um CSV por período, o do ano corrente atualizado uma vez por mês; a página de cada conjunto dá o
# endereço de cada arquivo e o período no nome. O robots.txt proíbe /api/ (não usado) e pede 10 s entre pedidos.
# Conferido em 23/10/2026: Lei nº 24.189, de 3/4/2026, a nº 24.501, de 27/8/2026, sem faltas (o arquivo vai até 31/8).
# Vetos e projetos do Executivo: não há lista aberta (SPL da Alego fechado a robôs; os dados abertos não têm vetos).
DADOS_GO = "https://dadosabertos.go.gov.br"
GOV_VEICULO = "Governo de Goiás (Casa Civil)"
GOV_NOTA = ("Governo do estado: entram as leis sancionadas, pelos dados abertos da Casa Civil de Goiás. Os vetos e os projetos "
            "que o governo mandou à Assembleia não entram: a Alego não publica uma lista aberta deles (o sistema de processo "
            "legislativo, SPL, proíbe consultas por robôs) e os dados abertos do estado não trazem os vetos.",
            "State government: signed laws are included, from the Goiás Casa Civil open data. Vetoes and the bills the "
            "government sent to the state assembly are not: the Alego does not publish an open list of them (its legislative "
            "system, SPL, forbids queries by robots) and the state's open data does not include vetoes.")


def _arquivos_go(rede: Rede, ds: str) -> list[tuple[str, str, str]]:
    """[(início, fim, endereço do CSV)] de um conjunto de dados, pelo período escrito no nome de cada arquivo."""
    html = rede.texto(f"{DADOS_GO}/dataset/{ds}", f"{ds}.html", 20)
    titulos = dict(re.findall(r'href="/dataset/[^/"]+/resource/([0-9a-f-]+)"[^>]*title="([^"]+)"', html))
    urls = {rid: u for u, rid in re.findall(
        r'href="(https://dadosabertos\.go\.gov\.br/dataset/[^"]+/resource/([0-9a-f-]+)/download/[^"]+\.csv)"', html, re.I)}
    out = []
    for rid, t in titulos.items():
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})-a-(\d{2})-(\d{2})-(\d{4})", t)
        if m and rid in urls:
            out.append((f"{m[3]}-{m[2]}-{m[1]}", f"{m[6]}-{m[5]}-{m[4]}", urls[rid]))
    return out


def governo(rede: Rede) -> None:
    import csv
    import io
    from . import _nco_gov as G
    g = G.governo_atual("GO")
    ini = g["inicio"]
    leis, ate, fontes = [], [], []
    for ds, tipo, nome in (("leis-ordinarias", "LO", "leis ordinárias"), ("leis-complementares", "LC", "leis complementares")):
        arqs = [a for a in _arquivos_go(rede, ds) if a[1] >= ini]
        if not arqs:
            raise RuntimeError(f"GO: nenhum arquivo de {ds} cobre o período")
        for a_ini, a_fim, url in arqs:
            txt = rede.texto(url, f"{tipo}-{a_ini}-{a_fim}.csv", 20)
            for r in csv.DictReader(io.StringIO(txt.lstrip("\ufeff")), delimiter=";"):
                num, d = re.sub(r"\D", "", r.get("numero") or ""), data_iso(r.get("data_legislacao"))
                if num and d:
                    leis.append({"tipo": tipo, "numero": int(num), "data": d})
        ate.append(max(a[1] for a in arqs))
        fontes.append(fonte(GOV_VEICULO, f"Dados abertos: {nome} (um arquivo por período)", f"{DADOS_GO}/dataset/{ds}"))
    c = G.contar_leis(leis, ini, hoje())
    if not c["total"]:
        raise RuntimeError("GO: nenhuma lei no período")
    fim = min(ate)
    pt, en = G.texto_leis(c, (f"publicadas nos dados abertos da Casa Civil de Goiás (um arquivo por ano, atualizado uma vez "
                              f"por mês: o mais recente vai até {G.data_pt(fim)})",
                              f"published in the Goiás Casa Civil open data (one file per year, updated once a month: the "
                              f"latest one goes up to {G.data_en(fim)})"), G.PROMULGADAS_INCLUIDAS)
    fontes.append(fonte(GOV_VEICULO, "Legisla Goiás: texto de cada lei", "https://legisla.casacivil.go.gov.br"))
    ex = G.bloco_executivo(g, c, None, fontes, [pt, G.EM_EXERCICIO[0], GOV_NOTA[0]], [en, G.EM_EXERCICIO[1], GOV_NOTA[1]])
    G.gravar_gov("GO", None, ex, fontes, inicio=ini)
