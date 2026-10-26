"""Assembleia Legislativa do Estado de Pernambuco (Alepe): Portal de Dados Abertos (https://dadosabertos.alepe.pe.gov.br).

Lista: /api/v1/parlamentares (os deputados da legislatura atual, com o partido de hoje), com foto e página de cada um
tiradas da página oficial https://www.alepe.pe.gov.br/parlamentares/ (ligadas pelo nome).
Propostas: /api/v1/proposicoes/projetos/?legislatura=20 (todos os projetos da legislatura, com os autores: o primeiro é o
autor principal) e, para a situação, o detalhe de cada projeto (/api/v1/proposicoes/projetos/?docid=..&tipoprop=p: histórico,
resultado final, tramitação conjunta e o autógrafo, que traz o número da lei). O detalhe é grande (traz o texto inteiro),
então só o resumo fica no cache e ele é relido em rodízio: os novos na hora, os que ainda andam a cada 21 dias e os que já
terminaram (lei, arquivado...) a cada 90 dias.
Gastos: a cota para o exercício da atividade parlamentar (CEAP), que o Portal da Transparência da Alepe mostra na página
"Verbas Indenizatórias": os pedidos de reembolso e os complementos de cada mês desde fevereiro de 2023, com as notas e as
rubricas (os tipos de despesa) do ano mais recente (ver "gastos: CEAP" abaixo).
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import json
import re
import time
import xml.etree.ElementTree as ET

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, sem_acento
from mandatos import mes_ano

from . import _carga as gv_carga
from . import _ne_gov as gv
from . import _votos_gastos as VG
from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, legislatura_estadual, membro,
                        nome_lei, partido_sigla, resumo_status)

API = "https://dadosabertos.alepe.pe.gov.br/api/v1"
SITE = "https://www.alepe.pe.gov.br"
VEICULO = "Assembleia Legislativa de Pernambuco (Alepe)"
TIPOS = {"PROJETO DE LEI ORDINARIA": ("PL", "PLO"), "PROJETO DE LEI COMPLEMENTAR": ("PLP", "PLC"),
         "PROPOSTA DE EMENDA A CONSTITUICAO": ("PEC", "PEC"), "PROJETO DE DECRETO LEGISLATIVO": ("PDL", "PDL"),
         "PROJETO DE RESOLUCAO": ("PRC", "PR"),
         # os projetos do orçamento (só o governo apresenta)
         "PROJETO DE LEI DE DIRETRIZES ORCAMENTARIAS": ("PL", "PLDO"), "PROJETO DE LEI ORCAMENTARIA ANUAL": ("PL", "PLOA"),
         "PROJETO DE PLANO PLURIANUAL": ("PL", "PPA")}
NORMA = {"PL": ("Lei", 1), "PLP": ("Lei Complementar", 2), "PRC": ("Resolução", 4), "PEC": ("Emenda Constitucional", None),
         "PDL": ("Decreto Legislativo", None)}
RELER_ANDANDO, RELER_FIM, ORCAMENTO_S = 21, 90, 150


def _tipo(t: str) -> tuple[str, str] | None:
    t = re.sub(r"\s+(DESARQUIVAD[OA])$", "", sem_acento(t or "").upper().strip())
    return TIPOS.get(t)


def _foto_e_pagina(rede: Rede) -> dict[str, dict]:
    t = rede.texto(f"{SITE}/parlamentares/", "site-parlamentares.html", 20)
    i = t.find('id="parlamentares-modo-fotos"')
    out = {}
    for li in re.findall(r"<li>(.*?)</li>", t[i:], re.S):
        m = re.search(r"href='(/parlamentar/[^']+)'", li)
        n = re.search(r'class="title parlamentares-nome">(.*?)<', li)
        f = re.search(r'<img[^>]+src="([^"]+)"', li)
        if m and n:
            out[chave_nome(html.unescape(n.group(1)))] = {"url": SITE + m.group(1), "foto": html.unescape(f.group(1)) if f else None}
    return out


def _resumo_detalhe(xml: str) -> dict:
    d = ET.fromstring(xml.encode("utf-8"))
    ev = [(data_iso(e.get("data")), (e.findtext("acao") or "").strip()) for e in d.iter("evento")]
    aut = d.find("autografo")
    return {"res": (d.findtext("resultadoFinal") or "").strip() or None, "conj": (d.findtext("tramitacaoConjunta") or "").strip().rstrip(".") or None,
            "lei": (aut.findtext("lei") or "").strip() if aut is not None else None,
            "lres": (aut.findtext("resultado") or "").strip() if aut is not None else None,
            "ev": ev[-6:], "lido": hoje()}


def _lei_en(nome: str, numero: str, ano: str | None) -> str:
    tipo = {"Lei Complementar": "complementary law", "Resolução": "resolution", "Emenda Constitucional": "constitutional amendment",
            "Decreto Legislativo": "legislative decree"}.get(nome, "law")
    n = f"{int(numero):,}" if numero.isdigit() else numero
    return f"{tipo} no. {n}" + (f" of {ano}" if ano else "")


def _situacao(v: dict, principal: dict | None = None) -> dict:
    det = v.get("det") or {}
    ev = det.get("ev") or []
    data = ev[-1][0] if ev else None
    res = sem_acento((det.get("res") or "").lower())
    lres = sem_acento((det.get("lres") or "").lower())
    acoes = sem_acento(" | ".join(a for _, a in ev).lower())
    if det.get("lei") and det["lei"].isdigit() and "veto total" not in lres:
        nome, tn = NORMA[v["t"]]
        quando = next((d for d, a in reversed(ev) if re.search(r"tran[s]?formado em|promulgad|sancionad", sem_acento(a.lower()))), None) or data
        ano = (quando or "")[:4] or None
        nl = nome_lei(nome, det["lei"], ano)
        url = (f"https://legis.alepe.pe.gov.br/texto.aspx?tiponorma={tn}&numero={det['lei']}&complemento=0&ano={ano}&tipo="
               if tn and ano else None)
        parcial = "parcial" in lres
        return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}" + (" (com partes vetadas)" if parcial else ""),
                "en": None, "data": quando, "lei": {"nome": nl, "url": url}, "en_lei": _lei_en(nome, det["lei"], ano)}
    if "veto total" in lres or "veto total" in res:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor", "data": data, "lei": None}
    # votada junto com outro projeto (tramitação conjunta): a Alepe dá o número da lei só ao projeto principal; os outros
    # ficam em "Enviado para redação final"
    if principal and re.search(r"redacao final|aprovad", res):
        art = "o" if principal["lei"]["nome"].startswith("Decreto") else "a"
        art_p = "a" if principal["sigla"].startswith("PEC") else "o"
        return {"status": "aprovada", "txt": f"Aprovada junto com {art_p} {principal['sigla']}, que virou {art} {principal['lei']['nome']}",
                "en": f"Approved together with {principal['sigla']}, which became {principal['en_lei']}", "data": data, "lei": principal["lei"]}
    regras = [
        (r"desarquivad", "andando", None, None),
        (r"retirad", "retirada", None, None),
        (r"rejeitad", "rejeitada", "Rejeitada", None),
        (r"prejudicad", "parada", "Ficou prejudicada", None),
        (r"arquivad", "arquivada", "Arquivada", None),
        (r"autografo (promulgado|sancionado)", "lei", "Virou norma; o número não aparece nos dados da Alepe",
         "Became law; the number does not appear in the Alepe data"),
        (r"autografo (criado|enviado)|sancao|promulgacao", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
         "Approved; sent to the governor to sign or veto"),
        (r"redacao final", "aprovada", "Aprovada; falta votar a redação final", "Approved; the final wording still needs a vote"),
        (r"retornad[oa] para o autor|devolvid[oa] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    ]
    for exp, st, pt, en in regras:
        if re.search(exp, res):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    if det.get("conj"):
        return {"status": "junta", "txt": f"Andando junto com outra proposta parecida ({det['conj']})", "en": None, "data": data, "lei": None}
    if res or acoes:
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


def coletar() -> dict:
    rede = Rede("alepe", pausa=0.5, timeout=120)
    oficiais = rede.json(f"{API}/parlamentares?formato=json", "parlamentares.json", 20)
    if not isinstance(oficiais, list) or not 40 <= len(oficiais) <= 55:
        raise RuntimeError(f"Alepe: lista de parlamentares inesperada ({type(oficiais).__name__})")
    site = _foto_e_pagina(rede)
    # projetos da legislatura (lista completa, 1 pedido) + detalhe em rodízio
    lst = ET.fromstring(rede.bruto(f"{API}/proposicoes/projetos/?legislatura={legislatura_estadual(20)}",
                                   f"projetos-leg{legislatura_estadual(20)}.xml", 20))
    est = rede.estado("estado.json", {}) or {}
    det: dict = est.get("det") or {}
    per = gv.periodo("PE")
    projetos, gov = {}, set()
    for p in lst:
        tp = _tipo(p.get("tipo"))
        autores = [(a.get("nome") or "").strip() for a in p.iter("autor")]
        do_executivo = any(a.get("tipo") != "DEPUTADO" and gv.autor_do_executivo(a.get("nome"), per) for a in p.iter("autor"))
        if not tp or not (do_executivo or any(a.get("tipo") == "DEPUTADO" for a in p.iter("autor"))):
            continue
        d = data_iso(p.get("dataPublicacao"))
        # projetos de legislaturas passadas que foram desarquivados também aparecem na lista: ficam de fora (escopo: desde 1º/2/2023)
        if (d and d < min(INICIO, per["inicio"])) or int(p.get("ano") or 0) < int(INICIO[:4]):
            continue
        projetos[p.get("docid")] = {"t": tp[0], "s": tp[1], "n": p.get("numero"), "a": p.get("ano"), "d": d,
                                    "e": (p.get("ementa") or "").strip(), "au": autores}
        if do_executivo:
            gov.add(p.get("docid"))
    h = dt.date.fromisoformat(hoje())

    def vencido(docid: str) -> bool:
        x = det.get(docid)
        if not x:
            return True
        terminou = re.search(r"autografo (promulgado|sancionado)|(?<!des)arquivad|retirad|rejeitad|prejudicad", sem_acento((x.get("res") or "").lower()))
        dias = (h - dt.date.fromisoformat(x["lido"])).days
        return dias >= (RELER_FIM if terminou else RELER_ANDANDO)

    fila = sorted([k for k in projetos if vencido(k)], key=lambda k: (k in det, (det.get(k) or {}).get("lido") or "", -int(k)))
    # primeira carga (mais de 1% dos projetos sem o detalhe, como no robô que começa com o cache vazio): a rodada toda
    primeira = sum(1 for k in projetos if k not in det) > 0.01 * max(1, len(projetos))
    limite = gv_carga.limite_diario(ORCAMENTO_S, primeira)
    t0, lidos = time.time(), 0
    for k in fila:
        if time.time() - t0 > limite or gv_carga.acabou():
            break
        try:
            det[k] = _resumo_detalhe(rede.texto(f"{API}/proposicoes/projetos/?docid={k}&tipoprop=p"))
            lidos += 1
        except gv_carga.SemTempo:
            break
        except Exception as e:
            log(f"  PE: detalhe {k} falhou ({e})")
        if lidos % 50 == 0:
            rede.guardar({"det": det}, "estado.json")
    det = {k: v for k, v in det.items() if k in projetos}
    rede.guardar({"det": det}, "estado.json")
    sem_det = sum(1 for k in projetos if k not in det)
    log(f"  PE: {len(projetos)} projetos de deputados na legislatura; {lidos} detalhes lidos hoje; {sem_det} ainda sem detalhe")
    if sem_det > 0.01 * max(1, len(projetos)):  # primeira carga em andamento: nada pela metade no site
        log(f"  PE: primeira carga dos detalhes em andamento; os arquivos de antes continuam; {rede.pedidos} pedidos ao site oficial")
        return gv_carga.pendente("Alepe", f"primeira carga: {sem_det} projetos sem o detalhe", rede.pedidos)
    # pessoas
    pessoas = []
    for o in oficiais:
        nome = (o.get("nomeParlamentar") or "").strip()
        s = site.get(chave_nome(nome)) or {}
        pessoas.append({"chave": nome, "nome": nome, "nomeCivil": None, "partido": partido_sigla(o.get("partido")), **s})
    ligados, avisos = casar_membros("PE", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  PE TSE: {a}")
    por_nome: dict[str, list[tuple[str, str]]] = {}
    for k, v in projetos.items():
        for i, a in enumerate(v["au"]):
            por_nome.setdefault(chave_nome(a), []).append((k, "autor" if i == 0 else "coautor"))
    por_numero = {(v["s"], v["n"], v["a"]): k for k, v in projetos.items()}

    def principal(v: dict) -> dict | None:
        """O projeto da tramitação conjunta que virou lei (a Alepe só põe o número da lei nele)."""
        conj = (v.get("det") or {}).get("conj") or ""
        pares = re.findall(r"(\d+)/(\d{4})", conj) or [(n, v["a"]) for n in re.findall(r"\b(\d+)\b", conj)]
        for n, a in pares:
            k = por_numero.get((v["s"], n, a))
            if k and det.get(k):
                s = _situacao(dict(projetos[k], det=det[k]))
                if s["status"] == "lei" and s["lei"]:
                    return {"sigla": f"{projetos[k]['s']} {n}/{a}", "lei": s["lei"], "en_lei": s["en_lei"]}
        return None

    membros, extras, listas = [], {}, []
    fonte_l = fonte(VEICULO, "Parlamentares da legislatura atual (Portal de Dados Abertos)", f"{API}/parlamentares?formato=json")
    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "PE", cand, p["nome"])
        url = p.get("url") or f"{SITE}/parlamentares/"
        membros.append(membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p.get("foto"), url))
        lista = []
        for k, papel in por_nome.get(chave_nome(p["nome"]), []):
            v = dict(projetos[k], det=det.get(k))
            s = _situacao(v, principal(v)) if v["det"] else {"status": "outra", "txt": "Situação não consultada nesta atualização", "en": "Status not checked in this update",
                                                                "data": None, "lei": None}
            prop = regional.proposta(f"alepe:{k}", f"{v['s']} {v['n']}/{v['a']}", v["t"], v["d"], v["e"],
                                     (v["det"] or {}).get("res"), f"https://proposicoes.alepe.pe.gov.br/proposicoes/detalhes?docid={k}&tipoprop=p",
                                     papel=papel, status=s["status"], data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Projetos de {p['nome']} na {legislatura_estadual(20)}ª legislatura (Portal de Dados Abertos)",
                        "https://proposicoes.alepe.pe.gov.br/")
        extras[pid] = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
                       "links": {"oficial": url, "email": None, "redes": []}, "fontes": [fonte_l, fonte_p]}
    log(f"  PE: situações {resumo_status(listas)}")
    notas = [("A lista de projetos vem do Portal de Dados Abertos da Alepe; a situação de cada um é relida aos poucos "
              "(os que ainda tramitam, a cada 21 dias).",
              "The list of bills comes from the Alepe Open Data Portal; the status of each one is re-read gradually "
              "(those still under discussion, every 21 days).")]
    g = None
    try:
        g = gastos_ceap(membros)
    except gv_carga.SemTempo:
        log("  PE CEAP: o tempo da rodada acabou; a leitura continua na próxima (ficam os gastos de antes)")
    except Exception as e:  # o serviço dos gastos fora do ar não derruba a Casa: ficam os blocos de antes
        log(f"  PE CEAP: ATENÇÃO: gastos não atualizados ({type(e).__name__}: {e}); ficam os de antes")
    com_gastos = VG.aplicar(extras, g, "gastos")
    if com_gastos:  # quem não está na lista de deputados da página tem o link para o serviço de dados (SERV)
        notas += nota_ceap([m["nome"] for m in membros
                            if (((extras.get(m["id"]) or {}).get("gastos") or {}).get("fonte") or {}).get("url", "").startswith(SERV)])
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": com_gastos}
    r = gravar("PE", {"casa": "Assembleia Legislativa do Estado de Pernambuco", "casa_en": "Legislative Assembly of the State of Pernambuco",
                      "sigla": "Alepe", "site": SITE}, membros, extras, cobertura, fonte_l, notas + [NOTA_VETOS, NOTA_VOTOS])
    try:
        _governo(rede, per, {k: dict(projetos[k], det=det.get(k)) for k in gov}, principal)
    except Exception as e:  # o perfil da governadora não derruba a lista da Assembleia: fica o arquivo da última vez
        log(f"  PE: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
    log(f"  PE: {rede.pedidos} pedidos ao site oficial")
    return r


NOTA_VOTOS = ("As votações não entram: a Alepe publica, para cada reunião plenária, o expediente, a ata e a frequência, mas não "
              "a lista com o voto de cada deputado; o Portal de Dados Abertos da Alepe não tem votações.",
              "Votes are not included: for each plenary meeting the Alepe publishes the agenda, the minutes and attendance, but "
              "not the list of each deputy's vote; the Alepe Open Data Portal has no votes.")
NOTA_VETOS = ("Os vetos do governo do estado não entram no perfil de quem governa: a Alepe não publica os vetos em dados "
              "abertos, e o resultado de cada projeto não separa o veto derrubado da sanção tácita (nos dois casos, quem "
              "promulga a lei é o presidente da Assembleia).",
              "The state government's vetoes are not shown on the governor's profile: the Alepe does not publish vetoes as "
              "open data, and the result of each bill does not tell an overridden veto from a tacit sanction (in both cases, "
              "the law is promulgated by the Assembly's president).")


# ---------------------------------------------------------------- gastos: CEAP (cota para o exercício da atividade parlamentar)
# Portal da Transparência da Alepe, página "Verbas Indenizatórias" (PAGINA_CEAP): escolhendo o deputado, o ano e o mês, a
# página mostra cada documento do mês ("PEDIDO" ou "COMPLEMENTO", com o número e o total) e, dentro dele, as notas
# (rubrica, data, CNPJ, empresa e valor). Ela lê os dados em JSON de www.alepe.pe.gov.br/servicos/transparencia/, os mesmos
# endereços usados aqui: adm/verbaindenizatoria.php?dep=&ano=&mes= (os documentos do mês; sem o deputado, vêm os de todos,
# com o nome de cada um), adm/verbaindenizatorianotas.php?docid= (as notas de um documento; só a rubrica e o valor de
# cada nota ficam no cache, sem CNPJ nem empresa), adm/verbaindenizatoria-rubricas.php?ano= (o nome de cada rubrica no
# ano; a página liga a nota à rubrica pelo número) e dep/deputados.php?leg=-16 (a lista de deputados da página). A CEAP
# substituiu a antiga verba indenizatória em 1º/9/2021 (Lei nº 17.368/2021, art. 3º); a página ainda usa o nome antigo. O
# mês é o de competência: os complementos de um mês chegam até o começo do ano seguinte (os de 2025 foram lançados até
# janeiro de 2026). Entram o pedido e os complementos (tipos "P" e "C"), como na página. O total do ano mostrado e os
# tipos de despesa vêm das notas (só as do ano mais recente de cada pessoa são lidas); o total desde fevereiro de 2023 soma
# o total de cada documento (que é a soma das notas dele). Conferido à mão em 26/10/2026, com os mesmos pedidos que a
# página faz para cada deputado: Álvaro Porto 06/2025 R$ 60.073,27 (pedido nº 447 + complementos nº 469 e 782) e 08/2026
# R$ 59.675,00; Dani Portela 06/2025 R$ 49.736,00 e 08/2026 R$ 59.670,00; os anos de 2026 inteiros (Álvaro Porto
# R$ 536.653,60 em 9 documentos; Dani Portela R$ 516.252,31 em 12) e o de 2025 de Álvaro Porto (R$ 720.879,24); o total
# de cada rubrica bate. A lista de deputados da página não traz Cayo Albino nem Junior Matuto (os gastos dos dois começam
# em 2024 e 2025): para eles, a fonte é o serviço de dados do mês. robots.txt de www.alepe.pe.gov.br: "Disallow:" vazio
# (tudo liberado), sem Crawl-delay.
SERV = "https://www.alepe.pe.gov.br/servicos/transparencia"
PAGINA_CEAP = "https://transparencia.alepe.pe.gov.br/financas/verbas-indenizatorias"
NOME_CEAP = ("Cota para o exercício da atividade parlamentar (CEAP)",
             "Office allowance (CEAP)")
CEAP_PASTA = "alepe-gastos"
CEAP_DIA_S = 120  # rodada diária com o cache cheio: cerca de 10 pedidos (os meses recentes e as notas dos documentos novos)
CEAP_MANUAL: dict[str, str] = {}  # {nome como a Alepe escreve nos documentos: id da pessoa ou "-"} (conferido à mão)


def _meses_ceap(ini: str) -> list[tuple[int, int]]:
    """(ano, mês) do começo da legislatura até o mês corrente."""
    h = hoje()
    a, m = int(ini[:4]), int(ini[5:7])
    out = []
    while (a, m) <= (int(h[:4]), int(h[5:7])):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _idade_mes(a: int, m: int) -> float:
    """Quantas horas a lista de documentos de um mês vale no cache: os 3 meses mais recentes são relidos a cada 20 h; os
    outros do ano corrente e do anterior (ainda podem ganhar complementos), a cada 7 a 9 dias; os mais antigos, a cada 30
    a 36 dias (o dia muda de mês para mês, para as releituras não caírem todas na mesma rodada)."""
    h = hoje()
    atras = int(h[:4]) * 12 + int(h[5:7]) - (a * 12 + m)
    return 20 if atras <= 2 else 24 * (7 + (a * 12 + m) % 3) if a >= int(h[:4]) - 1 else 24 * (30 + (a * 12 + m) % 7)


def _ceap_cache(rede: Rede, nome: str):
    """O JSON guardado em .cache/alepe-gastos/<nome> (None se não existe; se não for JSON, é apagado e baixado de novo)."""
    arq = rede.pasta / nome
    if not arq.exists():
        return None
    try:
        return json.loads(arq.read_text(encoding="utf-8-sig"))
    except Exception:
        arq.unlink(missing_ok=True)
        return None


def _ceap_fresco(rede: Rede, nome: str, horas: float) -> bool:
    arq = rede.pasta / nome
    return arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < horas


def _ceap_baixar(rede: Rede, est: dict, pedidos: list[tuple[str, str, bool]], fim: float) -> int:
    """Baixa [(url, arquivo do cache, pode vir vazio)] um por um até acabar, até `fim` (time.time()) ou até o fim da rodada
    (SemTempo). A resposta tem de ser uma lista JSON. Uma lista vazia onde devia haver dados não entra no cache e conta como
    erro (em 26/10/2026 o serviço respondeu [] para 106 pedidos seguidos, por cerca de 2 minutos, e depois voltou ao
    normal); ela só vale se vier vazia em 3 dias diferentes. Três erros seguidos param a leitura. Cada arquivo fica no
    cache assim que chega: a carga continua de onde parou na rodada seguinte."""
    feitos, seguidos, erros, h = 0, 0, [], hoje()
    vazias = est.setdefault("vazias", {})  # {arquivo: [dias diferentes em que veio vazio, último dia]}
    for url, nome, pode_vazia in pedidos:
        if time.time() >= fim:
            break
        try:
            b = rede.bruto(url, None, 0, headers={"Accept": "application/json"})
            x = json.loads(b.decode("utf-8-sig"))
            if not isinstance(x, list):
                raise ValueError("resposta fora do formato (não é uma lista)")
            if not x and not pode_vazia:
                n, dia = vazias.get(nome, [0, ""])
                vazias[nome] = [n + (dia != h), h]
                if vazias[nome][0] < 3:
                    raise ValueError("lista vazia onde devia haver dados")
        except gv_carga.SemTempo:
            break
        except Exception as e:
            seguidos += 1
            erros.append(f"{url.rsplit('/', 1)[-1]}: {type(e).__name__}: {e}")
            if seguidos >= 3:
                log("  PE CEAP: 3 erros seguidos; o resto fica para a próxima rodada")
                break
            continue
        if x:
            vazias.pop(nome, None)
        if nome.startswith("notas/"):  # das notas, só a rubrica e o valor ficam no cache (nada de CNPJ ou nome de empresa)
            b = json.dumps([{"rubrica": n.get("rubrica"), "valor": n.get("valor")} for n in x if isinstance(n, dict)],
                           ensure_ascii=False).encode("utf-8")
        arq = rede.pasta / nome
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_bytes(b)
        tmp.replace(arq)
        feitos, seguidos = feitos + 1, 0
    if erros:
        log(f"  PE CEAP: {len(erros)} pedidos sem resposta válida: {erros[:3]}{'...' if len(erros) > 3 else ''}")
    return feitos


def _tipo_ceap(nome: str) -> str:
    """'LOCAÇÃO DE VEÍCULOS' -> 'Locação de veículos' (as palavras da Alepe, sem as maiúsculas)."""
    t = re.sub(r"\s+", " ", nome or "").strip()
    return t[:1].upper() + t[1:].lower() if t and t == t.upper() else t


def _rubricas(lista) -> dict[int, str]:
    """{número da rubrica: nome} de um ano (a página liga cada nota à rubrica pelo número)."""
    out = {}
    for i, x in enumerate(lista if isinstance(lista, list) else []):
        n = str(x.get("numero_categoria") or "")
        out[int(n) if n.isdigit() else i + 1] = _tipo_ceap(x.get("nome_categoria"))
    return out


def _na_pagina(lista, membros: list[dict]) -> set[str] | None:
    """Ids de quem aparece na lista de deputados da página (o seletor "Deputado"); None se a lista não veio."""
    if not isinstance(lista, list) or not lista:
        return None
    exatos = {chave_nome(d.get("nome")) for d in lista}
    nomes = VG.Nomes([{"id": str(d.get("id")), "nome": d.get("nome")} for d in lista])
    return {m["id"] for m in membros if chave_nome(m["nome"]) in exatos or nomes.quem(m["nome"])}


def gastos_ceap(membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} desde o começo da legislatura ou desde que a pessoa assumiu. None enquanto a primeira
    carga (as listas de todos os meses e as notas do ano mais recente de cada pessoa) não termina: os perfis ficam com o
    bloco de antes. Depois dela, quem tem notas por ler (um documento novo) fica com o bloco de antes até a rodada seguinte.
    Quem não aparece na lista de deputados da página ganha, como fonte, os dados do mês no serviço que a página usa (SERV)."""
    t0 = time.time()
    rede = Rede(CEAP_PASTA, pausa=1.0, timeout=60)
    ini = regional.inicio_estadual("PE")
    est = rede.estado("estado.json", {}) or {}
    primeira = est.get("completa") != ini
    fim = t0 + gv_carga.limite_diario(CEAP_DIA_S, primeira)
    try:
        return _gastos_ceap(rede, est, membros, ini, primeira, fim, t0)
    finally:
        rede.guardar(est, "estado.json")


def _gastos_ceap(rede: Rede, est: dict, membros: list[dict], ini: str, primeira: bool, fim: float,
                 t0: float) -> dict[str, dict] | None:
    # 1. os documentos (pedidos e complementos) de cada mês, de todos os deputados: os mais recentes primeiro; só a lista do
    # mês corrente pode vir vazia
    meses = _meses_ceap(ini)
    pedidos = [(f"{SERV}/adm/verbaindenizatoria.php?dep=&ano={a}&mes={m}", f"docs/{a}-{m:02d}.json", (a, m) == meses[-1])
               for a, m in reversed(meses) if not _ceap_fresco(rede, f"docs/{a}-{m:02d}.json", _idade_mes(a, m))]
    pedidos.sort(key=lambda p: (rede.pasta / p[1]).exists())  # os que nunca foram lidos vêm antes
    _ceap_baixar(rede, est, pedidos, fim)
    docs, faltam = {}, []
    for a, m in meses:
        x = _ceap_cache(rede, f"docs/{a}-{m:02d}.json")
        if isinstance(x, list):
            docs[(a, m)] = [d for d in x if str(d.get("docid") or "").isdigit()]
        else:
            faltam.append(f"{m:02d}/{a}")
    if faltam:
        log(f"  PE CEAP: {len(faltam)} meses sem a lista de documentos ({', '.join(faltam[:4])}{'...' if len(faltam) > 4 else ''}); "
            f"os perfis ficam com os gastos de antes; {rede.pedidos} pedidos em {time.time() - t0:.0f} s")
        return None
    # 2. de quem é cada documento: o nome como a Alepe escreve -> a pessoa da lista de hoje
    quem = VG.Nomes(membros, CEAP_MANUAL)
    por: dict[str, list] = {}
    for (a, m), ds in docs.items():
        for d in ds:
            pid = quem.quem(d.get("deputado") or "")
            if pid:
                por.setdefault(pid, []).append((a, m, d))
    quem.avisar("PE", "CEAP")
    # 3. as notas dos documentos do ano mais recente de cada pessoa, as rubricas desse ano e a lista de deputados da página
    ultimo = {pid: max(a for a, _, d in ds if VG.valor_br(d.get("total"))) for pid, ds in por.items()
              if any(VG.valor_br(d.get("total")) for _, _, d in ds)}
    ano_atual = int(hoje()[:4])
    pedidos = [(f"{SERV}/adm/verbaindenizatoria-rubricas.php?ano={a}", f"rubricas-{a}.json", False) for a in sorted(set(ultimo.values()))
               if not _ceap_fresco(rede, f"rubricas-{a}.json", 24 * 7 if a >= ano_atual else 24 * 30)]
    if not _ceap_fresco(rede, "deputados-pagina.json", 24 * 7):
        pedidos.append((f"{SERV}/dep/deputados.php?leg=-16", "deputados-pagina.json", False))
    notas = []
    for pid, ds in por.items():
        for a, _, d in ds:
            if a != ultimo.get(pid) or not VG.valor_br(d.get("total")):
                continue
            nome = f"notas/{d['docid']}.json"
            ns = _ceap_cache(rede, nome)
            # documento novo, ou que mudou depois da leitura (a soma das notas não bate com o total): lê de novo
            if not isinstance(ns, list) or (abs(sum(VG.valor_br(n.get("valor")) for n in ns) - VG.valor_br(d.get("total"))) > 0.005
                                            and not _ceap_fresco(rede, nome, 20)):
                notas.append((int(d["docid"]), f"{SERV}/adm/verbaindenizatorianotas.php?docid={d['docid']}", nome))
    _ceap_baixar(rede, est, pedidos + [(u, n, False) for _, u, n in sorted(set(notas), reverse=True)], fim)
    # 4. os blocos
    rubricas = {a: _rubricas(_ceap_cache(rede, f"rubricas-{a}.json")) for a in set(ultimo.values())}
    na_pagina = _na_pagina(_ceap_cache(rede, "deputados-pagina.json"), membros)
    blocos, incompletos, avisos = {}, [], []
    for m in membros:
        pid = m["id"]
        if pid not in ultimo:
            continue
        ano, ds = ultimo[pid], sorted(por[pid], key=lambda x: (x[0], x[1], int(x[2]["docid"])))
        linhas, completo = [], bool(rubricas.get(ano))
        for a, mes, d in ds:
            total = VG.valor_br(d.get("total"))
            if a != ano or not total:  # anos anteriores: o total de cada documento (os tipos só valem no ano mostrado)
                linhas.append((f"{a}-{mes:02d}", "", total))
                continue
            ns = _ceap_cache(rede, f"notas/{d['docid']}.json")
            if not isinstance(ns, list) or not completo:
                completo = False
                break
            soma = sum(VG.valor_br(n.get("valor")) for n in ns)
            if ns and abs(soma - total) > 0.005:
                avisos.append(f"{m['nome']} {mes:02d}/{a} (documento {d['docid']}): notas R$ {soma:.2f}, total R$ {total:.2f}")
            if not ns:  # o serviço não traz nota deste documento (vazio em 3 dias diferentes): o total entra sem rubrica
                avisos.append(f"{m['nome']} {mes:02d}/{a} (documento {d['docid']}): sem notas; R$ {total:.2f} sem rubrica")
                linhas.append((f"{a}-{mes:02d}", "Sem rubrica informada", total))
            for n in ns:
                r = str(n.get("rubrica") or "")
                linhas.append((f"{a}-{mes:02d}", rubricas[ano].get(int(r)) if r.isdigit() and int(r) in rubricas[ano]
                               else f"Rubrica {r or 'não informada'}", VG.valor_br(n.get("valor"))))
        if not completo:
            incompletos.append(pid)
            continue
        if na_pagina is None or pid in na_pagina:
            f = fonte(VEICULO, f"Verbas indenizatórias (CEAP) de {m['nome']} no Portal da Transparência da Alepe "
                      "(escolha o deputado, o ano e o mês)", PAGINA_CEAP)
        else:  # a página não deixa escolher esta pessoa: os dados do mês mais recente, no serviço que a página usa
            ua, um = max((a, mes) for a, mes, d in ds if VG.valor_br(d.get("total")))
            f = fonte(VEICULO, f"Verbas indenizatórias (CEAP) de todos os deputados em {um:02d}/{ua}, com {m['nome']} (dados "
                      "do Portal da Transparência da Alepe; a lista de deputados da página não traz esse nome)",
                      f"{SERV}/adm/verbaindenizatoria.php?dep=&ano={ua}&mes={um}")
        b = VG.bloco_gastos(linhas, f, ini, NOME_CEAP)
        if b and b["ano"] == ano:
            blocos[pid] = b
        elif b:
            avisos.append(f"{m['nome']}: o ano dos gastos ({b['ano']}) não é o dos documentos ({ano}); fica sem bloco")
    if avisos:
        log(f"  PE CEAP: ATENÇÃO: {len(avisos)} avisos: {avisos[:3]}{'...' if len(avisos) > 3 else ''}")
    if incompletos and primeira:  # nada pela metade: a carga continua na próxima rodada, de onde parou
        log(f"  PE CEAP: primeira carga em andamento ({len(incompletos)} pessoas com notas por ler); os perfis ficam com os "
            f"gastos de antes; {rede.pedidos} pedidos em {time.time() - t0:.0f} s")
        return None
    for pid in incompletos:  # documento novo com as notas por ler: fica o bloco de antes, até a próxima rodada
        velho = VG.de_antes(pid, "gastos")
        if velho:
            blocos[pid] = velho
    if incompletos:
        log(f"  PE CEAP: {len(incompletos)} pessoas com notas por ler ficam com o bloco de antes")
    if primeira:
        est["completa"] = ini
    total = sum(b["mandatoTotal"] for b in blocos.values())
    log(f"  PE CEAP: {len(blocos)} de {len(membros)} perfis com gastos (R$ {total:,.2f} desde {ini[:7]}); "
        f"{rede.pedidos} pedidos em {time.time() - t0:.0f} s")
    return blocos


def nota_ceap(fora: list[str]) -> list[tuple[str, str]]:
    pt, en = mes_ano(regional.inicio_estadual("PE"))
    out = [(f"Gastos: cota para o exercício da atividade parlamentar (CEAP), que substituiu a antiga verba indenizatória e que "
            f"o Portal da Transparência da Alepe mostra na página \"Verbas Indenizatórias\", desde {pt}. Entram os pedidos de "
            f"reembolso e os complementos de cada mês; os tipos de despesa são as rubricas da Alepe, pelas notas de cada pedido.",
            f"Spending: the office allowance (CEAP), which replaced the old "
            f"expense allowance and which the Alepe transparency portal shows on its \"Verbas Indenizatórias\" page, since "
            f"{en}. Each month's reimbursement requests and supplements are included; expense types are the Alepe's "
            f"categories (\"rubricas\"), taken from the receipts in each request.")]
    if fora:
        um = len(fora) == 1
        npt = fora[0] if um else f"{', '.join(fora[:-1])} nem {fora[-1]}"
        nen = fora[0] if um else f"{', '.join(fora[:-1])} or {fora[-1]}"
        out.append((f"Gastos: a lista de deputados da página \"Verbas Indenizatórias\" não traz {npt}; o link dos gastos "
                    f"{'desse perfil' if um else 'desses perfis'} abre os dados do mês no serviço que a própria página usa.",
                    f"Spending: the list of deputies on the \"Verbas Indenizatórias\" page does not include {nen}; the spending "
                    f"link on {'that profile' if um else 'those profiles'} opens the month's data in the service the page itself "
                    f"uses."))
    return out


LEGIS = "https://legis.alepe.pe.gov.br"  # legislação estadual (Alepe)


def _leis_do_ano(rede: Rede, ano: int, atual: bool) -> list[dict]:
    """Leis ordinárias (tiponorma=1) e complementares (2) de um ano na Legislação Estadual da Alepe (só o resumo fica guardado)."""
    est = rede.estado("gov-leis-lista.json", {}) or {}
    x = est.get(str(ano))
    h = dt.date.fromisoformat(hoje())
    if x and (h - dt.date.fromisoformat(x["lido"])).days < (1 if atual else 30):
        return x["itens"]
    itens = []
    for tn in (1, 2):
        t = rede.texto(f"{LEGIS}/lista.aspx?tiponorma={tn}&ano={ano}")
        for m in re.finditer(r"href='texto\.aspx\?id=(\d+)&tipo='''>\s*Lei (Ordin[aá]ria|Complementar) n[°º]\s*([\d.]+)\s*</a>"
                             r"\s*</span>\s*<span class=\"publicacao\">\s*Publicada no DOE (\d{2}/\d{2}/\d{4})", t):
            itens.append({"id": m.group(1), "tl": "LC" if m.group(2).startswith("Compl") else "LO", "n": m.group(3).replace(".", ""),
                          "pub": data_iso(m.group(4))})
    est[str(ano)] = {"lido": hoje(), "itens": itens}
    rede.guardar(est, "gov-leis-lista.json")
    return itens


def _governo(rede: Rede, per: dict, projetos: dict, principal) -> dict:
    """dados/pessoas/gov-PE.json: os projetos do Executivo (autor: a governadora ou, no exercício do governo, a vice) e as
    leis sancionadas (pelo texto oficial de cada lei, na Legislação Estadual da Alepe)."""
    ini = per["inicio"]
    lista = []
    for k, v in projetos.items():
        if (v["d"] or "") < ini:
            continue
        s = _situacao(v, principal(v)) if v["det"] else {"status": "outra", "txt": "Situação não consultada nesta atualização",
                                                            "en": "Status not checked in this update", "data": None, "lei": None}
        prop = regional.proposta(f"alepe:{k}", f"{v['s']} {v['n']}/{v['a']}", v["t"], v["d"], v["e"], (v["det"] or {}).get("res"),
                                 f"https://proposicoes.alepe.pe.gov.br/proposicoes/detalhes?docid={k}&tipoprop=p", papel="autor",
                                 status=s["status"], data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
        lista.append(com_status_en(prop, s["en"]))
    fonte_prop = fonte(VEICULO, "Projetos do Poder Executivo na legislatura (Portal de Dados Abertos)", "https://proposicoes.alepe.pe.gov.br/")
    h = hoje()
    leis = {}
    for ano in range(int(ini[:4]), int(h[:4]) + 1):
        for i in _leis_do_ano(rede, ano, ano == int(h[:4])):
            if (i.get("pub") or "9999") >= ini:
                leis[f"{i['tl']}-{i['n']}"] = i
    quem, faltam = gv.classificar_leis(rede, {k: f"{LEGIS}/texto.aspx?id={i['id']}&tipo=" for k, i in leis.items()},
                                       lambda u: rede.texto(u, None, None), orcamento_s=150)
    fontes = [fonte(VEICULO, "Legislação Estadual: leis ordinárias e complementares", f"{LEGIS}/lista.aspx?tiponorma=1")]
    if faltam:  # sem a conta das leis, o perfil ficaria pela metade: fica o arquivo da última vez
        log(f"  PE: {faltam} leis ainda sem leitura do texto; o perfil da governadora fica como estava até todas serem lidas")
        return {}
    c = collections.Counter(quem.values())
    n_leis, prom = c[False], c[True]
    nota, nota_en = gv.nota_leis(per, len(leis), c[False], c[True], c[None], "na Legislação Estadual da Alepe (publicadas "
                                 "no Diário Oficial a partir dessa data)", "in the Alepe state legislation portal (published in "
                                 "the Official Gazette from that date on)")
    nota += " Vetos: a Alepe não publica os vetos em dados abertos."
    nota_en += " Vetoes: the Alepe does not publish vetoes as open data."
    ex = gv.bloco_executivo(per, n_leis, None, fontes, nota, nota_en, promulgadas_pela_casa=prom)
    esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature",
                            "projetos de lei (inclusive os do orçamento), de lei complementar e de emenda à Constituição do estado",
                            "bills (including budget bills), complementary bills and amendments to the state Constitution",
                            "Entram também os que a vice-governadora assinou quando estava no exercício do governo.",
                            "Also included are those signed by the vice governor while acting as governor.")
    return gv.gravar_gov("PE", per, lista, esc, esc_en, fonte_prop, ex, fontes)


TSE_MANUAL: dict[str, str] = {}
