"""Assembleia Legislativa do Paraná (Alep): API de Dados Abertos da Alep (http://webservices.assembleia.pr.leg.br/api/public,
documentada em transparencia.assembleia.pr.leg.br/servicos/dados-abertos) e a página oficial dos deputados.

Lista: página oficial "Conheça os deputados" (www.assembleia.pr.leg.br/deputados/conheca): nome, partido, foto e
página de cada deputado em exercício (54 cadeiras).
Propostas: POST /proposicao/filtrar por tipo (PRO = projeto de lei, PLC = PLP, PDL, RES = PRC e PEC), recebidas desde
1º/2/2023. A autoria vem numa lista ("DEPUTADO A, DEPUTADO B"): o primeiro é o autor principal.
Situação: a Alep só informa "TRAMITANDO" ou "ARQUIVADA" e o local atual. Projeto que virou lei é arquivado depois da
sanção; por isso "virou lei" vem das normas legais (POST /norma-legal/filtrar e GET /norma-legal/<código>, que diz de
quais proposições a norma veio). Sem norma, "ARQUIVADA" fica como arquivada; "TRAMITANDO" fica em discussão, a não ser
no local "DL - ENVIO PARA SANÇÃO" (aprovada, esperando o governador). A API do detalhe de cada proposição (com a
tramitação) estava fora do ar em outubro de 2026 ("ORA-00942"); por isso não dá para separar, entre as arquivadas, as
rejeitadas, retiradas ou vetadas.
Cada norma é consultada uma vez só (não muda); cada rodada consulta no máximo ALEP_NORMAS_MAX normas novas (300).
Gastos (verbas de ressarcimento) e votações nominais: o Portal da Transparência da Alep mostra, mas não pela API de
dados abertos; por isso não entram.
O governo do estado (perfil do governador, dados/pessoas/gov-PR.json), desde o começo do mandato: os projetos do
autor "PODER EXECUTIVO" da lista de proposições; as leis com a conclusão "Sancionada" nas normas legais (as promulgadas
pela Assembleia ficam de fora). Os vetos não entram: a lista de vetos da API vai só até fevereiro de 2024.
"""
from __future__ import annotations

import json
import os
import re

import regional
from comum import PESSOAS, chave_nome, hoje, ler_json, log, sem_acento

from ._sse_comum import (Rede, SemTempo, bloco_executivo, casar_membros, com_status_en, desde, escopo, escopo_governo, fonte,
                         gravar, gravar_governo, legislatura, membro, nome_lei, partido_sigla, periodo_governo, resumo_status,
                         sem_html, virou)

UF = "PR"
SITE = "https://www.assembleia.pr.leg.br"
API = "http://webservices.assembleia.pr.leg.br/api/public"  # o https desse endereço tem certificado próprio (não reconhecido)
CONSULTA = "https://consultas.assembleia.pr.leg.br/#/pesquisa-legislativa"
VEICULO = "Assembleia Legislativa do Paraná (Alep)"
CASA = {"casa": "Assembleia Legislativa do Estado do Paraná", "casa_en": "Legislative Assembly of the State of Paraná",
        "sigla": "Alep", "site": SITE,
        "sic": "https://alep.sisgop.pr.gov.br/cidadao/acesso-informacao/1"}  # pedido de informação (Lei de Acesso à Informação)
INICIO = legislatura(UF)["inicio"]
TIPOS = {1: ("PL", "PL"), 2: ("PLC", "PLP"), 3: ("PDL", "PDL"), 4: ("PR", "PRC"), 6: ("PEC", "PEC")}
NORMAS = {1: "Lei", 2: "Lei Complementar", 3: "Resolução", 4: "Decreto Legislativo", 5: "Emenda Constitucional"}

# nomes da autoria na API que não batem sozinhos com o nome da página oficial: {nome na API: nome na lista oficial}
APELIDOS: dict[str, str] = {}
# ligações com o TSE conferidas à mão: {endereço da página oficial (final): SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {
    "doutor-antenor": "160001614994",  # = "DR. ANTENOR" (Antenor Gomes de Lima, PT)
    "paulo-gomes": "160001603358",     # = "PAULO GOMES DA TV" (2022: PP, 55.302 votos, os mesmos da biografia oficial)
}


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], list[str]]:
    t = rede.texto(f"{SITE}/deputados/conheca", "deputados.html", 20)
    pessoas = []
    for c in t.split('<div class="deputado-card')[1:]:
        url = (re.search(r'href="(https://www\.assembleia\.pr\.leg\.br/deputados/perfil/[^"]+)"', c) or [None, None])[1]
        img = re.search(r'<img src="([^"]+)"[^>]*alt="Foto d[oa] deputad([oa]) ([^"]+)"', c)
        if not url or not img:
            continue
        sigla = sem_html((re.search(r'<p class="text-gray-500 text-sm italic">(.*?)</p>', c, re.S) or [None, ""])[1])
        pessoas.append({"chave": url.rsplit("/", 1)[-1], "nome": img.group(3).strip(), "nomeCivil": None,
                        "partido": partido_sigla(sigla), "url": url, "foto": img.group(1),
                        "genero": "F" if img.group(2) == "a" else "M"})
    if not 45 <= len(pessoas) <= 60:
        raise RuntimeError(f"Alep: a lista oficial veio com {len(pessoas)} pessoas")
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        membros.append(membro(pid, p["nome"], None, p["partido"], p["genero"], p["foto"], p["url"],
                              (cand or {}).get("sit") == "SUPLENTE"))
    return membros, ids, avisos


def _post(rede: Rede, caminho: str, corpo: dict, cache: str, ttl):
    return rede.json(f"{API}{caminho}", cache, ttl, dados=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})


def _proposicoes(rede: Rede) -> list[dict]:
    out = []
    for cod in TIPOS:
        d = _post(rede, "/proposicao/filtrar", {"codigoTipoProposicao": cod, "dataInicial": f"{INICIO}T03:00:00.000Z",
                                                 "numeroMaximoRegistro": 50000}, f"proposicoes-{cod}.json", 20)
        if not d.get("sucesso", True):
            raise RuntimeError(f"Alep: erro na API de proposições ({(d.get('erro') or '')[:120]})")
        out += [dict(x, _cod=cod) for x in d.get("lista") or []]
    if len(out) < 1000:
        raise RuntimeError(f"Alep: só {len(out)} proposições na API")
    return out


def _normas(rede: Rede) -> tuple[dict[str, dict], list[dict]]:
    """({código da proposição: {"nome", "url"}}, [leis e leis complementares desde 2023: tipo, número, data, conclusão])
    pelas normas legais (cada norma consultada uma vez). Só as normas com deputado ou o Poder Executivo entre os autores
    têm o detalhe lido (as outras não entram em nenhum perfil)."""
    est = rede.estado("normas.json", {}) or {}
    limite = int(os.environ.get("ALEP_NORMAS_MAX", "300"))
    lista, leis = [], []
    for cod, tn in NORMAS.items():
        for ano in range(int(INICIO[:4]), int(hoje()[:4]) + 1):
            d = _post(rede, "/norma-legal/filtrar", {"codigoTipoNormaLegal": cod, "ano": ano, "numeroMaximoRegistro": 50000},
                      f"normas/{cod}-{ano}.json", 20 if ano == int(hoje()[:4]) else 24 * 7)
            for x in d.get("lista") or []:
                if re.search(r"\bDEPUTAD[OA]\b|PODER EXECUTIVO", x.get("autores") or ""):
                    lista.append((str(x["codigo"]), tn, x.get("numero"), x.get("ano")))
                if cod in (1, 2):
                    leis.append({"tipo": tn, "numero": x.get("numero"), "data": (x.get("data") or "")[:10],
                                 "conclusao": x.get("conclusaoMovimentacao") or ""})
    novos = [x for x in lista if x[0] not in est]
    for cod, tn, num, ano in novos[:limite]:
        try:
            v = rede.json(f"{API}/norma-legal/{cod}").get("valor") or {}
        except SemTempo:  # o fim da rodada chegou: as normas que faltam ficam para a próxima
            break
        except Exception as e:
            log(f"  PR: norma {cod}: {e}")
            continue
        est[cod] = {"props": [str(p["codigo"]) for p in v.get("proposicoes") or []], "nome": nome_lei(tn, num, ano)}
    if len(novos) > limite:
        log(f"  PR: {len(novos) - limite} normas ficam para as próximas rodadas")
    rede.guardar(est, "normas.json")
    out = {}
    for cod, v in est.items():
        for p in v.get("props") or []:
            out[p] = {"nome": v["nome"], "url": CONSULTA}
    return out, leis


def _autores(txt: str, por_nome: dict[str, str]) -> list[str]:
    out = []
    for a in (txt or "").split(","):
        a = re.sub(r"(?i)^\s*deputad[oa]\s+", "", a).strip()
        a = APELIDOS.get(a.upper(), a)
        k = por_nome.get(chave_nome(a))
        if not k:  # "DELEGADO TITO BARICHELLO" x "Tito Barichello", "ARILSON CHIORATO" x "Arilson Maroldi Chiorato"
            pa = set(regional.palavras(a))
            achados = [c for n, c in por_nome.items() if pa and (pa <= set(regional.palavras(n)) or set(regional.palavras(n)) <= pa)]
            k = achados[0] if len(set(achados)) == 1 else None
        if k and k not in out:
            out.append(k)
    return out


def coletar() -> dict:
    rede = Rede("alep", pausa=1.0)
    membros, ids, avisos = _membros(rede)
    for a in avisos:
        log(f"  PR: {a}")
    props = _proposicoes(rede)
    normas, leis = _normas(rede)
    hj = hoje()
    per = periodo_governo(UF)
    por_nome = {chave_nome(m["nome"]): k for k, pid in ids.items() for m in membros if m["id"] == pid}
    anteriores = {}
    for pid in list(ids.values()) + [f"gov-{UF}"]:
        for p in ((ler_json(PESSOAS / f"{pid}.json", {}) or {}).get("propostas") or {}).get("lista") or []:
            if p.get("status") == "lei" and p.get("lei"):
                anteriores[p["id"]] = p["lei"]

    def proposta(x: dict, papel: str) -> dict:
        sig, tipo = TIPOS[x["_cod"]]
        pid_prop = f"alep:{x['codigo']}"
        status_of = (x.get("status") or "").strip().upper()
        local = (x.get("localAtual") or "").strip()
        lei = normas.get(str(x["codigo"])) or anteriores.get(pid_prop)
        if lei:
            st = "lei"
        elif status_of == "ARQUIVADA":
            st = "arquivada"
        elif re.search(r"envio para sancao", sem_acento(local.lower())):
            st = "aprovada"
        else:
            st = "andando"
        situacao = f"{status_of.capitalize()} ({local})" if local else status_of.capitalize() or None
        # a consulta oficial da Alep não tem endereço próprio para cada proposição: o link leva à pesquisa legislativa
        p = regional.proposta(pid_prop, f"{sig} {x.get('numero')}/{x.get('ano')}", tipo, (x.get("dataRecebimento") or "")[:10] or None,
                              x.get("ementa"), situacao, CONSULTA, papel=papel, status=st)
        if lei:
            virou(p, lei["nome"], lei["url"])
        elif st == "aprovada":
            com_status_en(p, "Aprovada pela Assembleia; enviada para a sanção do governador",
                          "Approved by the Assembly; sent to the governor to sign or veto")
        return p

    por_dep: dict[str, list] = {}
    governo: list[dict] = []
    sem_dono = set()
    for x in props:
        if re.search(r"(?i)poder executivo|governad", x.get("autor") or "") and \
                ((x.get("dataRecebimento") or "")[:10] or "") >= per["inicio"]:
            governo.append(proposta(x, "autor"))
        autores = _autores(x.get("autor"), por_nome)
        if not autores:
            if re.match(r"(?i)deputad", x.get("autor") or ""):
                sem_dono.add((x.get("autor") or "").split(",")[0])
            continue
        primeiro = _autores((x.get("autor") or "").split(",")[0], por_nome)
        for k in autores:
            por_dep.setdefault(k, []).append(proposta(x, "autor" if primeiro and k == primeiro[0] else "coautor"))
    if sem_dono:
        log(f"  PR: autores da API sem par na lista oficial (ex-deputados ou nomes diferentes): {sorted(sem_dono)[:12]}")
    f_lista = fonte(VEICULO, "Deputados estaduais em exercício (página oficial)", f"{SITE}/deputados/conheca", hj)
    f_prop = [fonte(VEICULO, "Pesquisa legislativa da Alep (proposições e normas legais)", CONSULTA, hj),
              fonte(VEICULO, "API de Dados Abertos da Alep (proposições e normas legais)",
                    "https://transparencia.assembleia.pr.leg.br/servicos/dados-abertos", hj)]
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"))
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        extras[m["id"]] = {"links": {"oficial": m["url"], "email": None, "redes": []},
                           "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                           "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da Alep", m["url"], hj)]}
    log(f"  PR: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    try:
        # o governo: projetos do Poder Executivo e as leis sancionadas no período (a API separa sancionadas e promulgadas)
        no_periodo = {}
        for x in leis:
            if per["inicio"] <= x["data"] <= hj:
                no_periodo[(x["tipo"], x["numero"])] = x  # leis republicadas aparecem de novo com o mesmo número
        sancionadas = sorted((x for x in no_periodo.values() if re.match(r"(?i)sancionad", x["conclusao"])), key=lambda x: x["data"])
        promulgadas = [x for x in no_periodo.values() if re.match(r"(?i)promulgad", x["conclusao"])]
        d_pt, d_en = desde(per["inicio"])
        n = len(promulgadas)
        prom_pt = (f"Ficam fora as {n} promulgadas pela própria Assembleia no período" if n > 1 else
                   "Fica fora 1 promulgada pela própria Assembleia no período" if n == 1 else
                   "Nenhuma foi promulgada pela própria Assembleia no período")
        prom_en = (f"The {n} laws promulgated by the Assembly itself in the period are left out" if n > 1 else
                   "The 1 law promulgated by the Assembly itself in the period is left out" if n == 1 else
                   "No law was promulgated by the Assembly itself in the period")
        esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                               "Na Alep, o autor desses projetos aparece como \"Poder Executivo\".",
                               "At the Alep, the author of these bills is listed as the executive branch.")
        executivo = bloco_executivo(
            per, [fonte(VEICULO, "API de Dados Abertos da Alep: normas legais (leis e leis complementares)",
                        "https://transparencia.assembleia.pr.leg.br/servicos/dados-abertos", hj),
                  fonte(VEICULO, "Pesquisa legislativa da Alep (normas legais)", CONSULTA, hj)],
            f"Leis ordinárias e complementares com a conclusão \"Sancionada\" desde {d_pt}, pela data da lei, nas normas legais "
            f"da Alep. {prom_pt} (quando ela derruba um veto ou o governador não responde no prazo). Os vetos não entram: a "
            "lista de vetos da API da Alep vai só até fevereiro de 2024, e o detalhe de cada projeto na API (com a tramitação) "
            "devolve erro.",
            f"Ordinary and complementary laws marked as signed since {d_en}, by the law's date, in the Alep's register of laws. "
            f"{prom_en} (when it overrides a veto or the governor does not answer in time). Vetoes are not included: the veto "
            "list in the Alep API only goes up to February 2024, and the API's page for each bill (with its history) returns "
            "an error.",
            leis=len(sancionadas), ultima_lei=sancionadas[-1]["data"] if sancionadas else None)
        gravar_governo(UF, per, governo, *esc_g, f_prop, executivo)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  PR: governo: {e}")
    notas = [("A Alep só informa se a proposta está tramitando ou arquivada; projeto que virou lei aparece pela norma legal ligada a ele.",
              "The Alep only says whether a proposal is moving or shelved; bills that became law are found through the law linked to them."),
             ("As votações e os gastos não entram: o Portal da Transparência da Alep mostra os dois (\"Controle de Votações\" e "
              "verbas de ressarcimento), mas os dados vêm de serviços protegidos por um teste anti-robô (reCAPTCHA) e fechados "
              "a robôs no robots.txt, e este site não contorna esse tipo de proteção. A API de dados abertos da Alep traz só "
              "proposições e normas.",
              "Votes and spending are not included: the Alep transparency portal shows both (the vote control page and "
              "the expense reimbursements), but the data comes from services protected by an anti-bot test (reCAPTCHA) and closed "
              "to robots in robots.txt, and this site does not get around that kind of protection. The Alep open data API only "
              "has bills and laws."),
             ("Os vetos do governador não entram no perfil dele: a lista de vetos da API da Alep vai só até fevereiro de 2024, "
              "e o detalhe de cada projeto na API (com a tramitação) devolve erro.",
              "The governor's vetoes are not included in his profile: the veto list in the Alep API only goes up to February "
              "2024, and the API's page for each bill (with its history) returns an error.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
