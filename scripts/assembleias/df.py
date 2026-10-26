"""Câmara Legislativa do Distrito Federal (CLDF): página oficial dos deputados distritais e a API pública do Processo
Legislativo Eletrônico (PLe), documentada no Portal de Dados Abertos da CLDF (dados.cl.df.gov.br, conjuntos
"Proposições" e "Normas").

Lista: página oficial "Legislatura atual" (www.cl.df.gov.br/deputados-2023-2026): nome, partido, foto e página de cada
deputado distrital em exercício (24 cadeiras).
Propostas: POST /proposicao/filter da API do PLe, por tipo, lidas desde 1º/1/2023: projetos de lei (PL), de lei
complementar (PLC = PLP), propostas de emenda à Lei Orgânica do DF (PELO), projetos de decreto legislativo (PDL) e de
resolução (PR = PRC). Autor principal = o primeiro da autoria; os outros são coautores.
Situação: a etapa oficial da proposta no PLe (Apresentação, Comissões, Plenário, Redação Final, Sanção, Veto ou
Promulgação, Arquivar). "Virou lei" vem das normas da CLDF (POST /norma/buscar e GET /norma/<id>, que diz de qual
proposição a norma veio). Algumas normas vêm sem a proposição de origem: elas são ligadas à proposta só quando a ementa
é idêntica, o tipo é o mesmo, há um autor em comum e não existe outra proposta nem outra norma com a mesma ementa.
O PLe não diz em formato aberto se uma proposta na etapa de sanção foi vetada: ela fica como
"aprovada pela Câmara Legislativa" até a norma aparecer.
Cada norma é consultada uma vez só (não muda); cada rodada consulta no máximo CLDF_NORMAS_MAX normas novas (300).
Gastos (verba indenizatória): a CLDF publica planilhas anuais no portal de dados abertos, mas em formatos diferentes a
cada ano (CSV num ano, XLSX em outro, com endereço novo a cada atualização); por isso não entram.
Votações nominais: não há publicação aberta do voto de cada deputado distrital.
O governo do DF (perfil da governadora, dados/pessoas/gov-DF.json), desde o dia em que quem governa assumiu: as
proposições de autoria do Poder Executivo no PLe (lidas desde a data de leitura) e as leis e leis complementares do
cadastro de normas (pela data de assinatura). Os vetos não entram: o PLe não registra o veto.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter

import mandatos
import regional
from comum import PESSOAS, chave_nome, hoje, ler_json, log, sem_acento

from ._sse_comum import (Rede, SemTempo, bloco_executivo, casar_membros, com_status_en, desde, escopo, escopo_governo, fonte,
                         gravar, gravar_governo, legislatura, membro, nome_lei, partido_sigla, periodo_governo, resumo_status,
                         sem_html, virou)

UF = "DF"
SITE = "https://www.cl.df.gov.br"
API = "https://ple.cl.df.gov.br/pleservico/api/public"
PLE = "https://ple.cl.df.gov.br"
VEICULO = "Câmara Legislativa do Distrito Federal (CLDF)"
CASA = {"casa": "Câmara Legislativa do Distrito Federal", "casa_en": "Legislative Chamber of the Federal District",
        "sigla": "CLDF", "site": SITE,
        "sic": "https://www.cl.df.gov.br/faca-seu-pedido"}  # pedido de informação (Lei de Acesso à Informação)
INICIO = legislatura(UF)["inicio"]  # 2023-01-01 (Lei Orgânica do DF, art. 66; a partir de 2027, 6 de janeiro)
LISTA = f"/deputados-{INICIO[:4]}-{int(INICIO[:4]) + 3}"  # página "Legislatura atual" (hoje /deputados-2023-2026)
TIPOS = {"Projeto de Lei": ("PL", "PL"), "Projeto de Lei Complementar": ("PLC", "PLP"),
         "Proposta de Emenda à Lei Orgânica": ("PELO", "PELO"), "Projeto de Decreto Legislativo": ("PDL", "PDL"),
         "Projeto de Resolução": ("PR", "PRC")}
NORMAS = ("Lei", "Lei Complementar", "Emenda à Lei Orgânica", "Decreto Legislativo", "Resolução")
NORMA_TIPO = {"Lei": "PL", "Lei Complementar": "PLP", "Emenda à Lei Orgânica": "PELO", "Decreto Legislativo": "PDL",
              "Resolução": "PRC"}
# etapa oficial (sem acento, minúsculas) -> status do site
ETAPAS = [
    (r"^arquivar", "arquivada"),
    (r"^sancao veto ou promulgacao", "aprovada"),
    (r"^(apresentacao|comissoes|plenario|aguardando inclusao|redacao final|leitura)", "andando"),
]

# ligações com o TSE conferidas à mão: {nome na lista oficial: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], list[str]]:
    t = rede.texto(f"{SITE}{LISTA}", "deputados.html", 20)
    i = t.find("Legislatura Atual")
    if i < 0:
        raise RuntimeError("CLDF: não achei a lista da legislatura atual")
    cartoes = re.findall(r'<a class="card[^"]*"\s+href="([^"]+)">(.*?)</a>', t[i:], flags=re.S)
    pessoas = []
    for href, corpo in cartoes:
        nome = sem_html((re.search(r'card-title">(.*?)</span>', corpo, re.S) or [None, ""])[1])
        if not nome:
            continue
        ptxt = sem_html((re.search(r'card-text">(.*?)</span>', corpo, re.S) or [None, ""])[1]) or ""
        sig = re.search(r"\(([^)]+)\)\s*$", ptxt)
        foto = (re.search(r'<img src="([^"]+)"', corpo) or [None, None])[1]
        pessoas.append({"chave": nome, "nome": nome, "nomeCivil": None, "partido": partido_sigla(sig.group(1) if sig else ptxt),
                        "url": href if href.startswith("http") else SITE + href, "foto": foto.replace("&amp;", "&") if foto else None})
    if not 20 <= len(pessoas) <= 30:
        raise RuntimeError(f"CLDF: a lista oficial veio com {len(pessoas)} pessoas")
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        membros.append(membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], p["url"],
                              (cand or {}).get("sit") == "SUPLENTE"))
    return membros, ids, avisos


def _proposicoes(rede: Rede) -> list[dict]:
    out = []
    for tipo in TIPOS:
        pagina = 0
        while True:
            corpo = json.dumps({"tipoProposicao": tipo, "dataInicio": INICIO}).encode()
            d = rede.json(f"{API}/proposicao/filter?page={pagina}&size=500&sort=dataLeitura,ASC",
                          f"proposicoes/{tipo}-{pagina}.json", 20, dados=corpo, headers={"Content-Type": "application/json"})
            out += [dict(x, _tipo=tipo) for x in d.get("content") or []]
            pagina += 1
            if d.get("last", True) or not d.get("content"):
                break
    if len(out) < 500:
        raise RuntimeError(f"CLDF: só {len(out)} proposições na API do PLe")
    return out


def _ementa(t: str | None) -> str:
    return re.sub(r"\W+", " ", sem_acento((t or "").lower())).strip()


def _normas(rede: Rede) -> tuple[dict[str, dict], dict[tuple, list], list[tuple[str, str, str]]]:
    """({id da proposição no PLe: {"nome", "url"}}, {(tipo da proposição, ementa): [normas sem proposição ligada]},
    [(tipo, sigla, data de assinatura) de todas as normas]) pelas normas da CLDF desde 2023. Cada norma é consultada uma
    vez. A API não liga algumas normas à proposição de origem (proposicaoNorma vazio): essas voltam à parte, com ementa e
    autores, para a ligação pela ementa idêntica."""
    est = rede.estado("normas.json", {}) or {}
    limite = int(os.environ.get("CLDF_NORMAS_MAX", "300"))
    ids, info, atos = [], {}, []
    for tn in NORMAS:
        for ano in range(int(INICIO[:4]), int(hoje()[:4]) + 1):
            pagina = 0
            while True:
                corpo = json.dumps({"operadorLogico": "AND", "tipoNorma": tn, "ano": str(ano)}).encode()
                d = rede.json(f"{API}/norma/buscar?page={pagina}&size=500", f"normas/{tn}-{ano}-{pagina}.json",
                              20 if ano == int(hoje()[:4]) else 24 * 7, dados=corpo, headers={"Content-Type": "application/json"})
                for x in d.get("content") or []:
                    ids.append((str(x["id"]), x.get("siglaNumeroAno"), tn))
                    info[str(x["id"])] = (tn, x.get("ementa"), x.get("autores"))
                    atos.append((tn, x.get("siglaNumeroAno") or "", (x.get("dataAssinatura") or "")[:10]))
                pagina += 1
                if d.get("last", True) or not d.get("content"):
                    break
    novos = [x for x in ids if x[0] not in est]
    for nid, sigla, tn in novos[:limite]:
        try:
            n = rede.json(f"{API}/norma/{nid}")
        except SemTempo:  # o fim da rodada chegou: as normas que faltam ficam para a próxima
            break
        except Exception as e:
            log(f"  DF: norma {nid}: {e}")
            continue
        prop = (n.get("proposicaoNorma") or {}).get("id")
        est[nid] = {"prop": str(prop) if prop else None, "nome": nome_lei(tn, n.get("numero"), n.get("ano")),
                    "url": f"{PLE}/#/norma/consultar/{nid}"}
    if len(novos) > limite:
        log(f"  DF: {len(novos) - limite} normas ficam para as próximas rodadas")
    rede.guardar(est, "normas.json")
    soltas: dict[tuple, list] = {}
    for nid, v in est.items():
        if not v.get("prop") and nid in info:
            tn, em, au = info[nid]
            soltas.setdefault((NORMA_TIPO[tn], _ementa(em)), []).append(dict(v, autores=au or ""))
    return {v["prop"]: v for v in est.values() if v.get("prop")}, soltas, atos


def _pela_ementa(x: dict, tipo: str, soltas: dict[tuple, list], usadas: set) -> dict | None:
    """Norma sem proposição ligada, com a mesma ementa (palavra por palavra) e do mesmo tipo, e com um autor em comum.
    Só liga se houver uma única norma assim (uma ligação errada é pior que nenhuma)."""
    cands = soltas.get((tipo, _ementa(x.get("ementa")))) or []
    autores = {chave_nome(re.sub(r"(?i)^\s*deputad[oa]\s+", "", a)) for a in (x.get("autoria") or "").split(",") if a.strip()}
    cands = [n for n in cands if autores & {chave_nome(re.sub(r"(?i)^\s*deputad[oa]\s+", "", a)) for a in n["autores"].split(",")}]
    if len(cands) == 1 and cands[0]["url"] not in usadas:
        return cands[0]
    return None


def _status(etapa: str) -> str:
    t = sem_acento((etapa or "").lower()).strip()
    for exp, st in ETAPAS:
        if re.search(exp, t):
            return st
    return "outra"


def coletar() -> dict:
    rede = Rede("cldf", pausa=0.6)
    membros, ids, avisos = _membros(rede)
    for a in avisos:
        log(f"  DF: {a}")
    props = _proposicoes(rede)
    normas, soltas, atos = _normas(rede)
    hj = hoje()
    per = periodo_governo(UF)
    por_nome = {chave_nome(k): k for k in ids}
    anteriores = {}  # situação da rodada anterior (para não perder "virou lei" enquanto faltam normas no cache)
    for pid in list(ids.values()) + [f"gov-{UF}"]:
        for p in ((ler_json(PESSOAS / f"{pid}.json", {}) or {}).get("propostas") or {}).get("lista") or []:
            if p.get("status") == "lei" and p.get("lei"):
                anteriores[p["id"]] = p["lei"]
    usadas = {v["url"] for v in normas.values()}
    mesma_ementa = Counter((TIPOS[x["_tipo"]][1], _ementa(x.get("ementa"))) for x in props)
    pela_ementa = 0
    situacoes: dict[str, tuple] = {}

    def situacao(x: dict) -> tuple[str, dict | None, str]:
        """(status, lei, etapa) de uma proposição, calculado uma vez só."""
        nonlocal pela_ementa
        if str(x["id"]) in situacoes:
            return situacoes[str(x["id"])]
        tipo = TIPOS[x["_tipo"]][1]
        etapa = (x.get("etapa") or "").split(",")[0].strip()
        st = _status(etapa)
        lei = normas.get(str(x["id"]))
        if not lei and st in ("aprovada", "arquivada") and mesma_ementa[(tipo, _ementa(x.get("ementa")))] == 1:
            lei = _pela_ementa(x, tipo, soltas, usadas)
            if lei:
                usadas.add(lei["url"])
                pela_ementa += 1
        if not lei and anteriores.get(f"cldf:{x['id']}"):
            lei = {"nome": anteriores[f"cldf:{x['id']}"]["nome"], "url": anteriores[f"cldf:{x['id']}"]["url"]}
        situacoes[str(x["id"])] = (st, lei, etapa)
        return situacoes[str(x["id"])]

    def proposta(x: dict, papel: str) -> dict:
        st, lei, etapa = situacao(x)
        sig, tipo = TIPOS[x["_tipo"]]
        num = (x.get("siglaNumeroAno") or "").split(" ", 1)[-1]
        p = regional.proposta(f"cldf:{x['id']}", f"{sig} {num}", tipo, x.get("dataLeitura"), x.get("ementa"), etapa or None,
                              f"{PLE}/#/proposicao/{x['id']}/consultar", papel=papel, status="lei" if lei else st)
        if lei:
            virou(p, lei["nome"], lei["url"])
        elif st == "aprovada":
            com_status_en(p, "Aprovada pela Câmara Legislativa; na etapa de sanção, veto ou promulgação",
                          "Approved by the Legislative Chamber; at the stage of signing, veto or promulgation")
        return p

    por_dep: dict[str, list] = {}
    governo: list[dict] = []
    for x in props:
        if re.search(r"(?i)poder executivo|governad", x.get("autoria") or "") and (x.get("dataLeitura") or "") >= per["inicio"]:
            governo.append(proposta(x, "autor"))
        autores = []
        for a in (x.get("autoria") or "").split(","):
            k = por_nome.get(chave_nome(re.sub(r"(?i)^\s*deputad[oa]\s+", "", a)))
            if k and k not in autores:
                autores.append(k)
        if not autores:
            continue
        primeiro = por_nome.get(chave_nome(re.sub(r"(?i)^\s*deputad[oa]\s+", "", (x.get("autoria") or "").split(",")[0])))
        for k in autores:
            por_dep.setdefault(k, []).append(proposta(x, "autor" if k == primeiro else "coautor"))
    f_lista = fonte(VEICULO, "Deputados distritais da legislatura atual (página oficial)", f"{SITE}{LISTA}", hj)
    f_prop = [fonte(VEICULO, "Busca de proposições no Processo Legislativo Eletrônico (PLe)", f"{PLE}/#/buscar-proposicao?buscar=true", hj),
              fonte(VEICULO, "Dados Abertos: API pública de proposições e de normas do PLe", "https://dados.cl.df.gov.br/dataset/proposicoes", hj)]
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PELO", "PDL", "PRC"))
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        x: dict = {"links": {"oficial": m["url"], "email": None, "redes": []},
                   "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                   "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da CLDF", m["url"], hj)]}
        extras[m["id"]] = x
    log(f"  DF: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {pela_ementa} leis ligadas "
        f"pela ementa; {rede.pedidos} pedidos à rede")
    try:
        # o governo: projetos do Poder Executivo e as leis assinadas no período (pela data de assinatura no cadastro de normas)
        leis = sorted((a for a in atos if a[0] in ("Lei", "Lei Complementar") and per["inicio"] <= a[2] <= hj), key=lambda a: a[2])
        d_pt, d_en = desde(per["inicio"])
        esc_g = escopo_governo(UF, per, "Câmara Legislativa", "Legislative Chamber", ("PL", "PLP", "PELO"),
                               "A data é a da leitura no Plenário, a que o PLe informa.",
                               "The date is when the bill was read in the plenary session, as the PLe records it.")
        executivo = bloco_executivo(
            per, [fonte(VEICULO, "Dados Abertos: normas do PLe (leis e leis complementares, com a data de assinatura)",
                        "https://dados.cl.df.gov.br/dataset/proposicoes", hj),
                  fonte(VEICULO, "Pesquisa de normas no Processo Legislativo Eletrônico (PLe)", f"{PLE}/#/norma/buscar", hj)],
            f"Leis ordinárias e complementares assinadas desde {d_pt}, pela data de assinatura no cadastro de normas da Câmara "
            f"Legislativa (a última, em {mandatos.data_br(leis[-1][2]) if leis else '-'}). O cadastro não separa as poucas "
            "leis promulgadas pela própria Câmara Legislativa (quando ela derruba um veto ou o governo não responde no "
            "prazo): elas estão na conta. Os vetos não entram: o PLe não registra o veto (a tramitação para na etapa de "
            "sanção, que acontece no governo).",
            f"Ordinary and complementary laws signed since {d_en}, by signing date in the Legislative Chamber's register of "
            f"laws (the latest on {mandatos.extenso(leis[-1][2])[1] if leis else '-'}). The register does not single out the "
            "few laws promulgated by the Legislative Chamber itself (when it overrides a veto or the government does not "
            "answer in time): they are included. Vetoes are not included: the PLe does not record them (the process stops at "
            "the signing stage, which happens in the government).",
            leis=len(leis), ultima_lei=leis[-1][2] if leis else None)
        gravar_governo(UF, per, governo, *esc_g, f_prop, executivo)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  DF: governo: {e}")
    notas = [("A CLDF não diz, em formato aberto, se um projeto na etapa de sanção foi vetado; ele aparece como aprovado até a lei sair.",
              "The CLDF does not say, in an open format, whether a bill at the signing stage was vetoed; it shows as approved until the law comes out."),
             ("A verba indenizatória não entra: a CLDF a publica em planilhas anuais no portal de dados abertos "
              "(dados.cl.df.gov.br), cada ano num formato diferente (CSV num ano, XLSX em outro) e só com parte dos deputados; "
              "o quadro mensal completo sai só em PDF, no Portal da Transparência.",
              "The expense allowance is not included: the CLDF publishes it in yearly spreadsheets on its open data portal "
              "(dados.cl.df.gov.br), each year in a different format (CSV one year, XLSX another) and with only some of the "
              "deputies; the complete monthly table is only published as a PDF, on its transparency portal."),
             ("As votações não entram: a CLDF não publica o voto de cada deputado em formato aberto; a página \"Sessões "
              "Plenárias\" traz as atas, o áudio e a lista de presença de cada sessão, em documentos.",
              "Votes are not included: the CLDF does not publish each deputy's vote in an open format; its \"Sessões "
              "Plenárias\" page has the minutes, the audio and the attendance list of each session, as documents."),
             ("Os vetos do governo do DF não entram no perfil da governadora: o PLe não registra o veto (a tramitação para na "
              "etapa de sanção, que acontece no governo); o veto sai só no Diário Oficial do DF.",
              "The Federal District government's vetoes are not included in the governor's profile: the PLe does not record "
              "them (the process stops at the signing stage, which happens in the government); vetoes only appear in the "
              "Federal District's official gazette.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
