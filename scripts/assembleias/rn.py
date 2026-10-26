"""Assembleia Legislativa do Estado do Rio Grande do Norte (ALRN): API do portal "Transparência Legislativa"
(https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/, a mesma que alimenta
https://transparencialegislativa.al.rn.leg.br) e API do site (https://www.al.rn.leg.br/api/deputados).

Lista: /parlamentar (os 24 deputados com mandato em vigor, com o partido de hoje pela filiação sem data de fim e o nome
completo), ligada pelo nome à lista do site (página oficial e e-mail de cada um). Foto: a da própria API.
Propostas: /processo?tipoPropositura=..&dataInicio=2023-02-01 (projetos de lei, de lei complementar, de emenda
constitucional, de decreto legislativo, de resolução e de resolução de título honorífico), com o autor (iniciativa), o
número da lei quando virou lei (informacaoLei) e a data de arquivamento. A situação das outras vem da tramitação de cada
processo (/processo/<id>/tramitacao), relida em rodízio (as novas na hora, as que ainda andam a cada 21 dias). Vetos do
governador: processos do tipo VETO ("Veto Integral ao Projeto de Lei 296/2026 ...").
Votações nominais do Plenário (votacoes(), desde 1º/2/2023): as sessões plenárias realizadas (/reuniao?tipoReuniao=..),
a pauta do dia de cada uma (/processo?reuniao=<id>&faseReuniao=1: cada projeto e emenda diz o tipo de votação: "A" =
aberta, com o voto de cada um; "O" = simbólica; "S" = secreta) e o voto de cada deputado nas abertas
(/processo/<id>/detalhamento-votacao/<reunião>[/<emenda>], o mesmo "Extrato de Votação" do portal). Em muitas votações de
2023 e 2024 essa consulta dá erro no próprio sistema da ALRN (HTTP 500): elas ficam fora, a nota da Casa e o escopo dizem
quantas, e elas são tentadas de novo aos poucos (se o sistema for corrigido, entram sozinhas).
Gastos: não entram (a página de cotas da transparência da ALRN usa um serviço que exige chave de acesso).
"""
from __future__ import annotations

import datetime as dt
import re
import time

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, nome_proprio, sem_acento, slug

from . import _carga
from . import _ne_gov as gv
from . import _votos_gastos as VG
from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, membro, nome_lei,
                        partido_sigla, resumo_status)

API = "https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa"
SITE = "https://www.al.rn.leg.br"
PORTAL = "https://transparencialegislativa.al.rn.leg.br"
VEICULO = "Assembleia Legislativa do Rio Grande do Norte (ALRN)"
TIPOS = {1: ("PL", "PL", "Lei"), 2: ("PLP", "PLC", "Lei Complementar"), 7: ("PEC", "PEC", "Emenda Constitucional"),
         6: ("PDL", "PDL", "Decreto Legislativo"), 8: ("PRC", "PRES", "Resolução"), 22: ("PRC", "PRTH", "Resolução")}
VETO = 21
RELER_ANDANDO, ORCAMENTO_S = 21, 150

# situação da última tramitação (texto oficial sem acento, minúsculas) -> status do site (conferido numa amostra: ver as
# notas da frente ale-nordeste)
REGRAS = [
    (r"transformad[ao] em (lei|norma)|lei sancionada|promulgad|sancionad", "lei", "Virou lei", None),
    (r"veto (total|integral)|vetad[ao] (totalmente|integralmente)", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"retirad[ao] (pel[oa] autor|a pedido|de tramitacao)", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"anuncio de prejudicialidade", "parada", "Vai ser declarada prejudicada (aguarda o anúncio)",
     "About to be declared moot (awaiting the announcement)"),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"sugerido o arquivamento", "andando", "Foi sugerido o arquivamento; falta a decisão",
     "Shelving was suggested; the decision is pending"),
    (r"arquivad|arquivamento", "arquivada", "Arquivada", None),
    (r"desapensad", "andando", None, None),
    (r"apensad|apensamento|anexad|tramitacao conjunta", "junta", None, None),
    (r"sancao|autografo|aguardando promulgacao", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"aprovad[ao] (em|no|pelo) plenario|aprovad[ao] em (discussao|votacao|turno unico|segundo turno|2)", "aprovada", None, None),
    (r".", "andando", None, None),
]


def _lei(info: str | None, nome: str) -> dict | None:
    """'Nº 12835 de 13/07/2026 - DOE 14/07/2026' -> {"nome": "Lei nº 12.835/2026", ...}"""
    m = re.search(r"n[º°o]\.?\s*([\d.]+)\s*(?:,?\s*de\s*(\d{2}/\d{2}/(\d{4})))?", sem_acento(info or "").lower().replace("º", "o"))
    if not m:
        return None
    num = m.group(1).replace(".", "")
    return {"nome": nome_lei(nome, num, m.group(3)), "data": data_iso(m.group(2)) if m.group(2) else None}


def coletar() -> dict:
    rede = Rede("alrn", pausa=0.5, timeout=90)
    parls = rede.json(f"{API}/parlamentar", "parlamentar.json", 20).get("dados") or []
    h = hoje()
    vigentes = [p for p in parls if (p.get("vigencia") or {}).get("inicio", "")[:10] <= h
                and ((p.get("vigencia") or {}).get("fim") or "9999")[:10] >= h]
    if not 20 <= len(vigentes) <= 30:
        raise RuntimeError(f"ALRN: {len(vigentes)} deputados com mandato em vigor (esperado: 24)")
    try:
        lista_site = rede.json(f"{SITE}/api/deputados", "site-deputados.json", 20)
    except _carga.SemTempo:
        raise
    except Exception as e:  # o site da ALRN fora do ar (ex.: manutenção programada): vale a lista guardada da última vez
        log(f"  RN: lista do site fora do ar ({e}); vale a da última leitura")
        lista_site = rede.json(f"{SITE}/api/deputados", "site-deputados.json", None)
    site = {chave_nome(d["nome"]): d for d in lista_site}
    # propostas
    est = rede.estado("estado.json", {}) or {}
    tram: dict = est.get("tram") or {}
    procs: dict[str, dict] = {}
    for tp in list(TIPOS) + [VETO]:
        pag = 0
        while True:
            # desde 1º de janeiro do ano da posse: os projetos que o governador mandou em janeiro também entram (no perfil dele);
            # os vetos, desde 2019 (há veto com a data de entrada errada, de anos antes do número)
            desde = "2019-01-01" if tp == VETO else f"{INICIO[:4]}-01-01"
            d = rede.json(f"{API}/processo?pagina={pag}&tamanhoPagina=100&tipoPropositura={tp}&dataInicio={desde}")
            for x in d.get("dados") or []:
                procs[str(x["id"])] = {"tp": tp, "n": (x.get("propositura") or {}).get("numero"), "a": (x.get("propositura") or {}).get("ano"),
                                       "d": data_iso(x.get("dataEntrada")), "e": (x.get("ementa") or "").strip(),
                                       "ini": (x.get("iniciativa") or {}).get("id"), "lei": x.get("informacaoLei"),
                                       "idesc": (x.get("iniciativa") or {}).get("descricao"),
                                       "arq": data_iso(x.get("dataArquivamento")), "proc": f"{x.get('numero')}/{x.get('ano')}",
                                       "ap": (x.get("apensamento") or {}).get("id") if isinstance(x.get("apensamento"), dict) else None}
            if (pag + 1) * 100 >= int(d.get("total") or 0):
                break
            pag += 1
    vetos = {}
    for k, v in procs.items():
        if v["tp"] != VETO:
            continue
        e = sem_acento(v["e"].lower())
        m = re.search(r"veto (integral|total|parcial)[^.]{0,40}?projeto de (lei complementar|lei|resolucao)\D{0,8}([\d.]+)\s*/\s*(\d{4})", e)
        if m:
            tipo = {"lei complementar": 2, "lei": 1, "resolucao": 8}[m.group(2)]
            vetos[(tipo, int(m.group(3).replace(".", "")), int(m.group(4)))] = {"total": m.group(1) != "parcial", "d": v["d"]}
    ids_dep = {i["id"] for p in vigentes for i in p.get("iniciativas") or []}
    per = gv.periodo("RN")
    gov = {k for k, v in procs.items() if v["tp"] != VETO and gv.autor_do_executivo(v.get("idesc"), per) and (v["d"] or "") >= per["inicio"]}
    alvo = [k for k, v in procs.items() if v["tp"] != VETO and (v["ini"] in ids_dep or k in gov) and not v["lei"] and not v["arq"]]
    hoje_d = dt.date.fromisoformat(h)

    def vencido(k: str) -> bool:
        x = tram.get(k)
        return not x or (hoje_d - dt.date.fromisoformat(x["lido"])).days >= RELER_ANDANDO

    fila = sorted([k for k in alvo if vencido(k)], key=lambda k: (k in tram, (tram.get(k) or {}).get("lido") or "", -int(k)))
    # primeira carga (mais de 1% das propostas sem a tramitação, como no robô que começa com o cache vazio): a rodada toda
    primeira = sum(1 for k in alvo if k not in tram) > 0.01 * max(1, len(alvo))
    limite = _carga.limite_diario(ORCAMENTO_S, primeira)
    t0, lidos = time.time(), 0
    for k in fila:
        if time.time() - t0 > limite or _carga.acabou():
            break
        try:
            tr = rede.json(f"{API}/processo/{k}/tramitacao")
        except _carga.SemTempo:
            break
        except Exception as e:
            log(f"  RN: tramitação {k} falhou ({e})")
            continue
        ult = max(tr, key=lambda t: ((t.get("origem") or {}).get("data") or "", t.get("id") or 0)) if tr else None
        tram[k] = {"lido": h, "st": ((ult or {}).get("situacaoProcesso") or {}).get("nome"),
                   "d": data_iso(((ult or {}).get("origem") or {}).get("data")), "n": len(tr),
                   "tudo": sem_acento(" | ".join(((t.get("situacaoProcesso") or {}).get("nome") or "") for t in tr).lower())[:1500]}
        lidos += 1
        if lidos % 50 == 0:
            rede.guardar({"tram": tram}, "estado.json")
    tram = {k: v for k, v in tram.items() if k in procs}
    rede.guardar({"tram": tram}, "estado.json")
    sem_tram = sum(1 for k in alvo if k not in tram)
    log(f"  RN: {sum(1 for v in procs.values() if v['tp'] != VETO)} propostas desde 2023; {lidos} tramitações lidas hoje; "
        f"{sem_tram} ainda sem tramitação")
    if sem_tram > 0.01 * max(1, len(alvo)):  # primeira carga em andamento: nada pela metade no site
        log(f"  RN: primeira carga das tramitações em andamento; os arquivos de antes continuam; {rede.pedidos} pedidos ao site oficial")
        return _carga.pendente("ALRN", f"primeira carga: {sem_tram} propostas sem a tramitação", rede.pedidos)
    # pessoas
    pessoas = []
    for p in vigentes:
        nome = re.sub(r"^\s*deputad[oa]\s+", "", p.get("nomeParlamentar") or "", flags=re.I).strip()
        nome = nome_proprio(nome) if nome == nome.upper() else nome
        filiacao = [f for f in p.get("filiacoes") or [] if not (f.get("vigencia") or {}).get("fim")]
        partido = partido_sigla(((filiacao or [{}])[-1].get("partido") or {}).get("nome")) if filiacao else None
        civil = ((p.get("pessoa") or {}).get("nome") or "").strip()
        s = site.get(chave_nome(nome)) or {}
        pessoas.append({"chave": str(p["id"]), "nome": s.get("nome") or nome, "nomeCivil": nome_proprio(civil) if civil else None,
                        "partido": partido, "ini": {i["id"] for i in p.get("iniciativas") or []}, "elegis": p["id"], "site": s,
                        "inicio": ((p.get("vigencia") or {}).get("inicio") or "")[:10] or None,
                        "fim": ((p.get("vigencia") or {}).get("fim") or "")[:10] or None})
    ligados, avisos = casar_membros("RN", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  RN TSE: {a}")
    membros, extras, listas = [], {}, []
    pid_de_elegis: dict[int, str] = {}
    fonte_l = fonte(VEICULO, "Deputados com mandato em vigor (Transparência Legislativa, API)", f"{PORTAL}/")
    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "RN", cand, p["nome"])
        pid_de_elegis[int(p["elegis"])] = pid
        s = p["site"]
        url = f"{SITE}/deputado/{s['id']}/{slug(s['nome'])}" if s.get("id") else f"{SITE}/deputados"
        foto = f"{API}/parlamentar/fotografia/{p['elegis']}"
        membros.append(membro(pid, p["nome"], p["nomeCivil"], p["partido"], (cand or {}).get("genero"), foto, url))
        lista = []
        for k, v in procs.items():
            if v["tp"] == VETO or v["ini"] not in p["ini"] or (v["d"] or "") < INICIO:
                continue
            tipo, sigla, nome_norma = TIPOS[v["tp"]]
            s_ = _situacao(k, v, tram.get(k), vetos, nome_norma)
            prop = regional.proposta(f"alrn:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], s_["sit"],
                                     f"{PORTAL}/projeto/{k}", papel="autor", status=s_["status"], data_status=s_["data"],
                                     status_txt=s_["txt"], lei=s_["lei"])
            lista.append(com_status_en(prop, s_["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Projetos de {p['nome']} (Transparência Legislativa)", f"{PORTAL}/")
        x = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
             "links": {"oficial": url, "email": (s.get("email") or "").strip() or None, "redes": []},
             "fontes": [fonte_l, fonte_p]}
        if p["inicio"]:
            x["mandato"] = {"inicio": p["inicio"], "fim": p["fim"] or "2027-01-31", "situacao": "Em exercício", "obs": None, "fonte": fonte_l}
        extras[pid] = x
    log(f"  RN: situações {resumo_status(listas)}")
    notas = [("A ALRN registra só o autor principal de cada projeto (sem coautores). A situação dos projetos que ainda "
              "tramitam é relida aos poucos (cada um a cada 21 dias).",
              "The ALRN only records the main author of each bill (no co-authors). The status of bills still under "
              "discussion is re-read gradually (each one every 21 days).")]
    try:
        vot, info_v = votacoes(rede, pid_de_elegis)
    except Exception as e:  # o sistema de votações fora do ar não derruba a Casa: ficam as votações publicadas antes
        vot, info_v = None, (rede.estado("votos.json", {}) or {}).get("info")
        log(f"  RN: ATENÇÃO: votações não atualizadas ({type(e).__name__}: {e}); ficam as de antes")
    com_votos = VG.aplicar(extras, vot, "votacoes")
    if com_votos:
        notas.append(_nota_votacoes(info_v))
    notas.append(NOTA_GASTOS)
    cobertura = {"lista": True, "propostas": True, "votacoes": com_votos, "gastos": False}
    r = gravar("RN", {"casa": "Assembleia Legislativa do Estado do Rio Grande do Norte",
                      "casa_en": "Legislative Assembly of the State of Rio Grande do Norte", "sigla": "ALRN", "site": SITE},
               membros, extras, cobertura, fonte_l, notas)
    try:
        _governo(per, procs, gov, tram, vetos)
    except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
        log(f"  RN: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
    log(f"  RN: {rede.pedidos} pedidos ao site oficial")
    return r


VETOS_DESDE = "2025-01-01"  # primeiro ano inteiro com os vetos registrados como processos VET (o 1º é o VET nº 2/2024, de julho)


def _governo(per: dict, procs: dict, gov: set, tram: dict, vetos: dict) -> dict:
    """dados/pessoas/gov-RN.json: os processos de iniciativa "GOVERNO DO ESTADO" e os vetos do governo (processos VET)."""
    lista = []
    for k in gov:
        v = procs[k]
        tipo, sigla, nome_norma = TIPOS[v["tp"]]
        s_ = _situacao(k, v, tram.get(k), vetos, nome_norma)
        prop = regional.proposta(f"alrn:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], s_["sit"],
                                 f"{PORTAL}/projeto/{k}", papel="autor", status=s_["status"], data_status=s_["data"],
                                 status_txt=s_["txt"], lei=s_["lei"])
        lista.append(com_status_en(prop, s_["en"]))
    fonte_prop = fonte(VEICULO, "Processos de iniciativa do Governo do Estado (Transparência Legislativa)", f"{PORTAL}/")
    ini_v = max(per["inicio"], VETOS_DESDE)
    # conta pela data de entrada do veto; o número/ano do VET só quando não há data (os VET 25 e 26/2025 são vetos de
    # setembro de 2020, aos PL 175/19 e 266/19, registrados no fim de 2025: ficam fora)
    vts = [v for v in procs.values() if v["tp"] == VETO and gv.autor_do_executivo(v.get("idesc"), per)
           and (v["d"] >= ini_v if v["d"] else bool(v["a"] and int(v["a"]) >= int(ini_v[:4])))]
    totais = sum(1 for v in vts if re.search(r"veto (integral|total)", sem_acento(v["e"].lower())))
    parciais = sum(1 for v in vts if re.search(r"veto parcial", sem_acento(v["e"].lower())))
    nota = (f"Vetos: os processos do tipo veto (VET) que o governo mandou à Assembleia desde {gv.data_pt(ini_v)}, pela data "
            f"de entrada (vetos antigos registrados depois, como os VET 25 e 26/2025, que são de 2020, ficam fora). A ALRN "
            f"passou a registrar cada veto como um processo VET em julho de 2024 (o primeiro é o VET nº 2/2024), por isso a "
            f"conta começa em 2025, o primeiro ano inteiro. As leis sancionadas não entram: a ALRN não publica em dados "
            f"abertos a lista das leis do estado.")
    nota_en = (f"Vetoes: the veto items (VET) the government sent to the Assembly since {gv.data_en(ini_v)}, by date received "
               f"(old vetoes recorded later, such as VET 25 and 26/2025, which are from 2020, are left out). The ALRN started "
               f"recording each veto as a VET item in July 2024 (the first one is VET 2/2024), so the count starts in 2025, the "
               f"first full year. Laws signed are not included: the ALRN does not publish the list of state laws as open data.")
    fontes = [fonte(VEICULO, "Processos do tipo veto (Transparência Legislativa, API)", f"{API}/processo?tipoPropositura={VETO}")]
    ex = gv.bloco_executivo(dict(per, inicio=ini_v), None, len(vts), fontes, nota, nota_en,
                            totais if totais + parciais == len(vts) else None, parciais if totais + parciais == len(vts) else None)
    esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature")
    return gv.gravar_gov("RN", per, lista, esc, esc_en, fonte_prop, ex, fontes)


def _situacao(k: str, v: dict, tr: dict | None, vetos: dict, nome_norma: str) -> dict:
    if v.get("lei"):
        l = _lei(v["lei"], nome_norma)
        if l:
            return {"status": "lei", "txt": f"Virou {'o' if nome_norma.startswith('Decreto') else 'a'} {l['nome']}", "en": None,
                    "data": l["data"], "lei": {"nome": l["nome"], "url": None}, "sit": v["lei"]}
        return {"status": "lei", "txt": "Virou lei", "en": None, "data": None, "lei": None, "sit": v["lei"]}
    vt = vetos.get((v["tp"] if v["tp"] != 22 else 8, int(v["n"] or 0), int(v["a"] or 0)))
    if vt and vt["total"]:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor",
                "data": vt["d"], "lei": None, "sit": "Veto integral"}
    if v.get("arq"):
        return {"status": "arquivada", "txt": "Arquivada", "en": None, "data": v["arq"], "lei": None, "sit": "Arquivado"}
    if v.get("ap"):
        return {"status": "junta", "txt": None, "en": None, "data": None, "lei": None, "sit": "Anexado a outro processo"}
    if not tr:
        return {"status": "outra", "txt": "Situação não consultada nesta atualização", "en": "Status not checked in this update", "data": None, "lei": None, "sit": None}
    t = sem_acento((tr.get("st") or "").lower())
    for exp, st, pt, en in REGRAS:
        if re.search(exp, t):
            return {"status": st, "txt": pt, "en": en, "data": tr.get("d"), "lei": None, "sit": tr.get("st")}
    return {"status": "outra", "txt": None, "en": None, "data": tr.get("d"), "lei": None, "sit": tr.get("st")}


# ---------------------------------------------------------------- votações nominais do Plenário
# tipos de reunião plenária (entidade-base/tipo-reuniao) -> horas de cache da 1ª página da lista de sessões realizadas:
# 1 = Sessão Plenária Ordinária, 2 = Extraordinária, 12 = Extraordinária - Vetos (todo dia); 6, 9 e 11 = sessões
# preparatórias (posse, eleição da Mesa: uma vez por semana). As reuniões de comissão não entram.
VOT_TIPOS = {1: 20, 2: 20, 12: 20, 6: 24 * 7, 9: 24 * 7, 11: 24 * 7}
VOT_RELER_DIAS = 15       # a pauta das sessões dos últimos 15 dias é relida (o resultado pode ser lançado depois)
VOT_VARRER_DIAS = 30      # a lista inteira das sessões desde a posse é relida a cada 30 dias (para achar sessões atrasadas)
VOT_ORCAMENTO_S = 120     # limite diário das votações (na primeira carga, o resto da rodada: _carga.limite_diario)
VOT_ERROS_POR_RODADA = 20  # votações cuja consulta deu erro no sistema da ALRN: tentadas de novo aos poucos
VOT_VOTO = {1: "Sim", 0: "Não", 2: "Abstenção"}           # como o portal mostra o voto (0 = Não, 1 = Sim, 2 = Abstenção)
VOT_RESULTADO = {"A": "Aprovado", "R": "Rejeitado"}       # "A proposta foi aprovada/rejeitada em plenário"
NOTA_GASTOS = ("Os gastos não entram: a ALRN mostra as cotas parlamentares na página \"Verbas\" do seu Portal da "
               "Transparência (transparencia.al.rn.leg.br/verbas), mas os dados vêm de um serviço que exige chave de acesso, "
               "e este site não contorna esse tipo de proteção.",
               "Spending is not included: the ALRN shows the office allowances on the \"Verbas\" page of its transparency "
               "portal (transparencia.al.rn.leg.br/verbas), but the data comes from a service that requires an access key, "
               "and this site does not get around that kind of protection.")


def _data_local(iso: str | None) -> str | None:
    """'2026-09-22T10:30:00.000Z' (UTC) -> '2026-09-22' (horário de Brasília)."""
    if not iso:
        return None
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) - dt.timedelta(hours=3)
    return t.date().isoformat()


def _dias_desde(iso: str | None) -> int:
    if not iso:
        return 10 ** 6
    return (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(iso[:10])).days


def _limpa(t: str | None) -> str | None:
    """Texto oficial sem os caracteres de controle que a API às vezes traz (aspas curvas viram \\x1c e \\x1d)."""
    if not t:
        return None
    t = t.replace("\x1c", "“").replace("\x1d", "”")
    t = re.sub(r"[\x00-\x1f\x7f]+", " ", t)
    return re.sub(r"\s+", " ", t).strip() or None


def _abertas(pauta: dict) -> list[dict]:
    """Os itens de votação aberta (com o voto de cada deputado) da pauta do dia de uma sessão: projetos e emendas."""
    out = []
    for x in pauta.get("dados") or []:
        prop = x.get("propositura") or {}
        tipo = prop.get("tipo") or {}
        base = {"p": x["id"], "t": tipo.get("id"), "sig": tipo.get("sigla"), "n": prop.get("numero"), "a": prop.get("ano"),
                "ementa": _limpa(x.get("ementa"))}
        if x.get("tipoVotacao") == "A":
            out.append(dict(base, e=None, res=(x.get("resultadoVotacao") or {}).get("resultadoVotacao")))
        for e in x.get("emenda") or []:
            if e.get("tipoVotacao") != "A":
                continue
            doc = e.get("documento") or {}
            em = doc.get("emenda") or {}
            out.append(dict(base, e=em.get("id"), en=em.get("numero"), ea=em.get("ano"),
                            etipo=_limpa((em.get("tipoEmenda") or {}).get("descricao")),
                            eautor=_limpa((em.get("iniciativa") or {}).get("descricao")),
                            eementa=_limpa(doc.get("ementa")),
                            res=(e.get("resultadoVotacao") or {}).get("resultadoVotacao")))
    return out


def votacoes(rede: Rede, pid_de_elegis: dict[int, str]) -> tuple[dict | None, dict | None]:
    """({id da pessoa: bloco "votacoes"} ou None, resumo para a nota da Casa). None enquanto a primeira carga (todas as
    sessões desde a posse e o voto de cada votação aberta) não termina: os perfis ficam com o bloco publicado antes.
    O progresso fica em .cache/alrn/votos.json; as respostas da API, em .cache/alrn/votos/."""
    rede1 = Rede("alrn", pausa=rede.pausa, timeout=90, tentativas=1)  # uma tentativa: os erros 500 voltam aos poucos
    est = rede.estado("votos.json", {}) or {}
    if est.get("inicio") != INICIO:  # legislatura nova: tudo de novo
        est = {"inicio": INICIO}
    sess: dict = est.setdefault("sess", {})      # id da sessão -> {"d": data, "t": tipo, "n": número}
    erros: dict = est.setdefault("erros", {})    # chave do extrato -> {"ult": data da última tentativa, "n": tentativas}
    primeira = not est.get("completo")
    limite = _carga.limite_diario(VOT_ORCAMENTO_S, primeira)
    t0, pedidos0 = time.time(), rede.pedidos + rede1.pedidos

    def tempo() -> bool:
        return time.time() - t0 < limite and not _carga.acabou()

    def guardar() -> None:
        rede.guardar(est, "votos.json")

    def extrato(it: dict, sid: str) -> str:
        return f"{it['p']}-{sid}" + (f"-{it['e']}" if it.get("e") else "")

    try:
        # 1. sessões plenárias realizadas desde a posse
        varrer = primeira or _dias_desde(est.get("varrido")) >= VOT_VARRER_DIAS
        varridos = 0
        for tp, horas in VOT_TIPOS.items():
            pag = 0
            while tempo():
                url = f"{API}/reuniao?tamanhoPagina=100&pagina={pag}&situacao=R&tipoOrdenacao=DESC&tipoReuniao={tp}"
                d = rede.json(url, f"votos/reunioes-{tp}.json", horas) if pag == 0 else rede.json(url)
                ds = d.get("dados") or []
                for x in ds:
                    dia = _data_local(x.get("dataInicio"))
                    if dia and dia >= INICIO and dia <= hoje():
                        sess[str(x["id"])] = {"d": dia, "t": tp, "n": x.get("numero")}
                if not varrer or len(ds) < 100 or (ds and (_data_local(ds[-1].get("dataInicio")) or "") < INICIO):
                    varridos += 1
                    break
                pag += 1
        if varrer and varridos == len(VOT_TIPOS):
            est["varrido"] = hoje()
        guardar()
        # 2. a pauta do dia de cada sessão (as dos últimos dias são relidas) e 3. o extrato de cada votação aberta
        lidas = est.setdefault("pautas", {})   # id da sessão -> data da leitura da pauta
        ordem = sorted(sess, key=lambda s: (sess[s]["d"], int(s)), reverse=True)
        for sid in ordem:
            if not tempo():
                break
            recente = _dias_desde(sess[sid]["d"]) <= VOT_RELER_DIAS
            if sid in lidas and not (recente and _dias_desde(lidas[sid]) >= 1):
                continue
            rede.json(f"{API}/processo?reuniao={sid}&faseReuniao=1", f"votos/pauta/{sid}.json", 20 if recente else None)
            lidas[sid] = hoje()
            if len(lidas) % 25 == 0:
                guardar()
        guardar()
        faltam = []
        for sid in ordem:
            if sid not in lidas:
                continue
            for it in _abertas(rede.estado(f"votos/pauta/{sid}.json", {}) or {}):
                k = extrato(it, sid)
                if (rede.pasta / "votos" / "extrato" / f"{k}.json").exists():
                    continue
                faltam.append((k in erros, (erros.get(k) or {}).get("n", 0), (erros.get(k) or {}).get("ult") or "", k, it, sid))
        novos = [f for f in faltam if not f[0]]
        velhos = sorted((f for f in faltam if f[0] and _dias_desde(f[2]) >= 1), key=lambda f: (f[1], f[2]))
        for _, _, _, k, it, sid in novos + velhos[:VOT_ERROS_POR_RODADA]:
            if not tempo():
                break
            url = f"{API}/processo/{it['p']}/detalhamento-votacao/{sid}" + (f"/{it['e']}" if it.get("e") else "")
            try:
                rede1.json(url, f"votos/extrato/{k}.json", None)
                erros.pop(k, None)
            except _carga.SemTempo:
                raise
            except RuntimeError as e:  # o sistema da ALRN responde erro (HTTP 500) em muitas votações de 2023 e 2024
                x = erros.setdefault(k, {"n": 0, "desde": hoje()})
                x["n"], x["ult"], x["erro"] = x["n"] + 1, hoje(), str(e)[-60:]
        guardar()
    except _carga.SemTempo:
        guardar()
    pedidos = rede.pedidos + rede1.pedidos - pedidos0
    # completo: todas as sessões com a pauta lida e cada votação aberta com o extrato (ou com erro registrado)
    pendentes = [s for s in sess if s not in (est.get("pautas") or {})]
    sem_extrato, com_erro, itens = 0, [], []
    for sid in sess:
        if sid in pendentes:
            continue
        for it in _abertas(rede.estado(f"votos/pauta/{sid}.json", {}) or {}):
            k = extrato(it, sid)
            ex = rede.estado(f"votos/extrato/{k}.json")
            if ex is None:
                if k in erros:
                    com_erro.append(sess[sid]["d"])
                else:
                    sem_extrato += 1
                continue
            itens.append((k, it, sid, ex))
    if pendentes or sem_extrato:
        log(f"  RN votações: primeira carga em andamento ({len(pendentes)} sessões sem a pauta, {sem_extrato} votações sem o "
            f"extrato; {pedidos} pedidos nesta rodada); os perfis ficam com as votações publicadas antes")
        return None, est.get("info")
    est["completo"] = hoje()
    # 4. os blocos dos perfis
    por_pessoa: dict[str, list] = {}
    divergentes = 0
    for k, it, sid, ex in itens:
        dados = (ex.get("votacao") or {}).get("dados") or []
        obst = (ex.get("obstrucao") or {}).get("dados") or []
        if not dados and not obst:
            continue  # sem o voto de cada um (o extrato diz que não houve votação aberta)
        votos = {}
        for v in dados:
            voto, parl = VOT_VOTO.get(v.get("voto")), (v.get("parlamentar") or {}).get("id")
            if voto and parl is not None:
                votos[int(parl)] = voto
        for v in obst:
            p = v.get("parlamentar") or v
            if p.get("id") is not None:
                votos.setdefault(int(p["id"]), "Obstrução")
        pl = VG.placar(votos.values())
        rs = (ex.get("votacao") or {}).get("resumo") or {}
        if (pl["Sim"], pl["Não"], pl["Abstenção"]) != (rs.get("sim"), rs.get("nao"), rs.get("abstencao")):
            divergentes += 1
            log(f"  RN votações: o resumo do extrato {k} ({rs}) não bate com a soma dos votos ({pl})")
        sigla = f"{it['sig']} {it['n']}/{it['a']}" if it.get("sig") and it.get("n") else None
        if it.get("e"):
            desc = " ".join(x for x in ["Emenda", it.get("etipo"), f"nº {it['en']}/{it['ea']}" if it.get("en") else None] if x)
            desc += f" ({it['eautor']})" if it.get("eautor") else ""
            desc += f": {it['eementa']}" if it.get("eementa") else ""
            desc += f" — {sigla}: {it['ementa']}" if sigla and it.get("ementa") else ""
        else:
            desc = it.get("ementa") or None
        chave = f"alrn-vot:{k}"
        prop_id = f"alrn:{it['p']}" if it.get("t") in TIPOS else None
        for parl, voto in votos.items():
            pid = pid_de_elegis.get(parl)
            if pid:
                por_pessoa.setdefault(pid, []).append(VG.item_voto(chave, voto, sess[sid]["d"], sigla, desc,
                                                                   VOT_RESULTADO.get(it.get("res")), pl,
                                                                   f"{PORTAL}/projeto/{it['p']}", prop_id))
    periodo = VG.periodo_meses(com_erro)
    info = {"votacoes": sum(1 for *_, ex in itens if ((ex.get("votacao") or {}).get("dados") or (ex.get("obstrucao") or {}).get("dados"))),
            "erros": len(com_erro), "periodo": list(periodo) if periodo else None}
    est["info"] = info
    guardar()
    extra_pt = ["Nas votações de vetos, quem vota “sim” mantém o veto e quem vota “não” o derruba"]
    extra_en = ["In votes on vetoes, a “yes” vote keeps the veto and a “no” vote overturns it"]
    if com_erro:
        extra_pt.append(f"Ficam fora {len(com_erro)} votações abertas, {periodo[0]}, em que o sistema da ALRN dá erro ao "
                        "mostrar o voto de cada deputado")
        extra_en.append(f"{len(com_erro)} open votes, {periodo[1]}, are left out because the ALRN system returns an error "
                        "when showing each deputy's vote")
    esc, esc_en = VG.escopo_votos("ALRN", extra=(". ".join(extra_pt), ". ".join(extra_en)))
    fonte_v = fonte(VEICULO, "Votações abertas do Plenário: extrato de votação (Transparência Legislativa)", f"{PORTAL}/")
    blocos = {pid: VG.bloco_votacoes(l, esc, esc_en, fonte_v) for pid, l in por_pessoa.items()}
    log(f"  RN votações: {info['votacoes']} votações abertas com o voto de cada deputado desde {INICIO}; "
        f"{info['erros']} com erro no sistema da ALRN; {divergentes} com resumo diferente da soma; votos de {len(blocos)} "
        f"deputados; {pedidos} pedidos nesta rodada")
    return blocos, info


def _nota_votacoes(info: dict | None) -> tuple[str, str]:
    pt = ("Votações: entram as votações abertas do Plenário (com o voto de cada deputado) desde 1º/2/2023, pelo \"Extrato "
          "de Votação\" da Transparência Legislativa da ALRN, inclusive as de emendas e de vetos (nas de vetos, quem vota "
          "“sim” mantém o veto e quem vota “não” o derruba). As votações simbólicas e as secretas não entram: nelas o voto "
          "de cada um não fica registrado.")
    en = ("Votes: open votes in the full Assembly (with each deputy's vote) since February 1, 2023 are included, from the "
          "vote records of the ALRN Transparência Legislativa portal, including votes on amendments "
          "and vetoes (in votes on vetoes, a “yes” vote keeps the veto and a “no” vote overturns it). Voice votes and secret "
          "votes are not included: in them, each member's vote is not recorded.")
    if info and info.get("erros") and info.get("periodo"):
        pt += (f" Ficam fora também {info['erros']} votações abertas, {info['periodo'][0]}, em que o sistema da ALRN dá erro "
               "ao mostrar o voto de cada deputado (elas são consultadas de novo aos poucos).")
        en += (f" Also left out are {info['erros']} open votes, {info['periodo'][1]}, for which the ALRN system returns an "
               "error when showing each deputy's vote (they are checked again from time to time).")
    return pt, en


TSE_MANUAL: dict[str, str] = {}
