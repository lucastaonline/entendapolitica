"""Assembleia Legislativa do Estado do Rio Grande do Sul (ALRS): o serviço de dados do portal da ALRS (o mesmo que a
página "Deputados" usa) e as páginas oficiais de proposições de cada deputado.

Lista: https://ww4.al.rs.gov.br:5000/listarDestaqueDeputados (JSON usado pela página oficial "Deputados"): nome,
partido de hoje, e-mail, foto e código de cada deputado em exercício (55 cadeiras).
Propostas: a página oficial "Proposições" de cada deputado (ww4.al.rs.gov.br/deputados/<código>/proposicoes) traz,
dentro dela, a lista do sistema de processo legislativo da ALRS (ePRO) em JSON: tipo, número, ano, proponente,
situação atual e histórico, ementa. Entram PL, PLC (= PLP), PEC, PDL e PR (= PRC) protocolados desde 1º/2/2023. O
proponente principal é o autor; quando a lista mostra "Deputado(a) X + N Deputado(s)", X é o autor principal.
As páginas são lentas (~8 s cada): cada deputado é conferido a cada 3 dias (um terço por dia, em rodízio).
Situação: o texto oficial ("descricao") com as regras REGRAS.
Votações nominais: a página de cada proposição mostra a "Planilha de Votação" (voto de cada deputado), mas só em HTML,
proposição por proposição; por isso não entram. Gastos: não há publicação aberta da verba de cada gabinete.
O governo do estado (perfil do governador, dados/pessoas/gov-RS.json), desde o começo do mandato: os projetos do
proponente "Poder Executivo" (PL, PLC e PEC), pela pesquisa de proposições do portal (ww4.al.rs.gov.br/legislativo/
pesquisa/dados, um ano por vez, ~25 s cada); as leis ordinárias e complementares pela pesquisa do Sistema LEGIS
(ww3.al.rs.gov.br/legis, por data; a busca abre uma sessão no servidor); e os vetos pelas proposições "VT" (veto
total) e "VP" (veto parcial) do Poder Executivo protocoladas no período (a lista de cada tipo vem inteira, ~1 min:
lida a cada 3 dias).
"""
from __future__ import annotations

import datetime as _dt
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

import regional
from comum import PESSOAS, UA, chave_nome, data_iso, hoje, ler_json, log

from ._sse_comum import (Rede, SemTempo, anterior_governo, bloco_executivo, casar_membros, com_status_en, desde, dia_rodizio,
                         escopo, escopo_governo, fonte, gravar, gravar_governo, legislatura, membro, partido_sigla,
                         periodo_governo, qtd, resumo_status)

UF = "RS"
SITE = "https://ww4.al.rs.gov.br"
VEICULO = "Assembleia Legislativa do Estado do Rio Grande do Sul (ALRS)"
CASA = {"casa": "Assembleia Legislativa do Estado do Rio Grande do Sul",
        "casa_en": "Legislative Assembly of the State of Rio Grande do Sul", "sigla": "ALRS", "site": SITE,
        "sic": "https://www.al.rs.gov.br/e-sic/site/primeiro_acesso.html"}  # pedido de informação (Lei de Acesso à Informação)
INICIO = legislatura(UF)["inicio"]  # 2023-01-31 (posse no RS: Constituição do RS, art. 49, § 3º)
TIPOS = {"PL": "PL", "PLC": "PLP", "PEC": "PEC", "PDL": "PDL", "PR": "PRC"}

REGRAS = [
    (r"^(sancionad|promulgad)", "lei"),
    (r"^vetad|veto total", "rejeitada"),
    (r"^retirad", "retirada"),
    (r"^(prejudicad|devolvid)", "parada"),
    (r"^rejeitad", "rejeitada"),
    (r"^arquivad", "arquivada"),
    (r"^(apensad|anexad)", "junta"),
    (r"^aprovad|^aguardando sancao|^encaminhad[oa] a sancao|^redacao final aprovada", "aprovada"),
    # "Tramitação Concluída" e "Solucionado(a)" aparecem sem votação nem norma na página oficial: não dá para dizer
    # como acabou (conferido em PR 3/2023 e PL 293/2025)
    (r"^(tramitacao concluida|solucionad)", "outra"),
    (r"^(entrada|autuad|pauta|para parecer|ordem do dia|publicad|diligencia|comissao|em tramitacao|para redacao|"
     r"redacao final|leitura|recebid|distribu|aguardando|em discussao|em votacao|baixad|vista|com parecer|pedido de vista|"
     r"votacao conclusiva|tramitacao suspensa)", "andando"),
]

# ligações com o TSE conferidas à mão: {código do deputado na ALRS: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], list[str]]:
    d = rede.json(f"{SITE}:5000/listarDestaqueDeputados", "deputados.json", 20)
    lista = [x for x in d.get("lista") or [] if str(x.get("codStatus")) == "1"]
    if not 45 <= len(lista) <= 60:
        raise RuntimeError(f"ALRS: a lista oficial veio com {len(lista)} pessoas")
    pessoas = [{"chave": str(x["idDeputado"]), "nome": (x.get("nomeDeputado") or "").strip(), "nomeCivil": None,
                "partido": partido_sigla(x.get("siglaPartido")), "email": x.get("emailDeputado"),
                "foto": x.get("fotoGrandeDeputado")} for x in lista]
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], f"{SITE}/deputados/{p['chave']}",
                   (cand or {}).get("sit") == "SUPLENTE")
        m["_email"] = p["email"]
        membros.append(m)
    return membros, ids, avisos


def _lista(rede: Rede, cod: str) -> list[dict]:
    t = rede.texto(f"{SITE}/deputados/{cod}/proposicoes", f"proposicoes/{cod}.html", 20 if dia_rodizio(cod, 3) else 24 * 4,
                   timeout=180)
    m = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', t, re.S)
    if not m:
        raise RuntimeError(f"ALRS: página de proposições do deputado {cod} sem a lista")
    p = (json.loads(m.group(1)).get("alergs_deputados") or {}).get("proposicoes") or {}
    if str(p.get("statusCodeRequest")) != "200":
        raise RuntimeError(f"ALRS: o sistema de proposições respondeu {p.get('statusCodeRequest')} para o deputado {cod}")
    return (p.get("body") or {}).get("lista") or []


# ---------------------------------------------------------------- o governo (perfil do governador)
LEGIS = "https://ww3.al.rs.gov.br/legis/M010"
PESQUISA = f"{SITE}/legislativo/pesquisa/dados"


def _pesquisa(rede: Rede, cache: str, ttl: float, **filtro) -> list[dict]:
    """Pesquisa de proposições do portal (JSON com os mesmos campos da lista de cada deputado)."""
    campos = {"siglaTipoProposicao": "", "nroProposicao": "", "anoProposicao": "", "nomeProponente": "",
              "situacaoProposicao": "", "dataIni": "", "dataFim": "", "assunto1": "", "assunto2": "", "assunto3": ""}
    campos.update(filtro)
    d = rede.json(f"{PESQUISA}?{urllib.parse.urlencode(campos)}", cache, ttl, timeout=300)
    return d.get("lista") or []


def _leis(rede: Rede, tipo: int, ini: str) -> list[tuple[str, str, str]]:
    """[(id da norma, número, data)] das normas do tipo (20 = lei ordinária, 2 = lei complementar) de ini até hoje, pela
    pesquisa do Sistema LEGIS. A busca guarda o resultado numa sessão do servidor e redireciona para a lista: precisa do
    cookie da sessão."""
    nome = f"leis/{tipo}-{ini}.html"
    if not rede.fresco(nome, 20):
        br = lambda d: f"{d[8:10]}/{d[5:7]}/{d[:4]}"  # noqa: E731
        q = urllib.parse.urlencode({"txthNRO_PROPOSICAO": "", "txthAdin": "", "txthQualquerPalavra": "", "cboTipoNorma": tipo,
                                    "TxtNumero_Norma": "", "TxtAno": "", "txtData": "", "txtDataInicial": br(ini),
                                    "txtDataFinal": br(hoje()), "txtPalavraChave": "", "TxtQualquerPalavra": "",
                                    "CmbPROPOSICAO": "", "txtProcAdin": "", "cmbNumero_Docs": 1000, "txtOrdenacao": "data",
                                    "txtOperacaoFormulario": "Pesquisar"})
        abre = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        url = f"{LEGIS}/M0100008.asp?{q}"
        rede.esperar(url)  # robots.txt e pausa do servidor
        try:
            with abre.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
                corpo = r.read()
        finally:
            rede.marcar(url)
        arq = rede.caminho(nome)
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(corpo)
    t = rede.caminho(nome).read_bytes().decode("iso-8859-1")
    linhas = re.findall(r'Hid_NumeroNorma\d+" value="(\d+)".*?Hid_IdNorma\d+" value="(\d+)".*?'
                        r'class="TextoMenor2">\s*(\d{2}/\d{2}/\d{4})', t, re.S)
    total = re.search(r"mero de Documentos:\s*\d+\s*-\s*\d+\s*de\s*(\d+)", t)
    if not total and not linhas and re.search(r"(?i)nenhum|n.o (foi|foram) encontrad", t):
        return []
    if not total or int(total.group(1)) != len(linhas):
        rede.caminho(nome).unlink(missing_ok=True)
        raise RuntimeError(f"ALRS: a pesquisa do LEGIS (tipo {tipo}) veio com {len(linhas)} linhas de "
                           f"{total.group(1) if total else '?'}")
    return [(i, n, data_iso(d)) for n, i, d in linhas]


def _dias_atras(n: int) -> str:
    return (_dt.date.fromisoformat(hoje()) - _dt.timedelta(days=n)).isoformat()


def _data(x: dict) -> str | None:
    return data_iso(x.get("dthProtocolo")) or data_iso((x.get("situacoesPorPeriodo") or [{}])[-1].get("data"))


def _proposta(x: dict, papel: str) -> dict:
    sig = (x.get("siglaTipoProposicao") or "").strip().upper()
    num, ano = x.get("nroProposicao"), x.get("anoProposicao")
    p = regional.proposta(f"alrs:{sig}-{num}-{ano}", f"{sig} {num}/{ano}", TIPOS[sig], _data(x), x.get("ementa"),
                          (x.get("descricao") or "").strip() or None, f"{SITE}/proposicao/{sig}/{num}/{ano}",
                          papel=papel, data_status=data_iso(x.get("dthSituacaoProposicao")), regras=REGRAS)
    if p["status"] == "aprovada" and (p.get("dataStatus") or "9") < _dias_atras(60):
        # aprovada há mais de 60 dias (o prazo de sanção é de 15 dias úteis) e a página oficial não diz o que veio depois
        com_status_en(p, "Aprovada pela Assembleia (a página oficial não registra a sanção ou o veto)",
                      "Approved by the Assembly (the official page does not record whether it was signed or vetoed)")
    elif p["status"] == "aprovada":
        com_status_en(p, "Aprovada pela Assembleia; segue para a sanção ou o veto do governador",
                      "Approved by the Assembly; it goes to the governor to sign or veto")
    elif p["status"] == "rejeitada" and re.match(r"(?i)vetad", p["situacao"] or ""):
        com_status_en(p, "Aprovada pela Assembleia, mas vetada pelo governador", "Approved by the Assembly, but vetoed by the governor")
    elif re.match(r"(?i)tramita[cç][aã]o suspensa", p["situacao"] or ""):
        com_status_en(p, "Ainda em discussão, mas com a tramitação suspensa", "Still under discussion, but its processing is on hold")
    elif re.match(r"(?i)devolu[cç][aã]o", p["situacao"] or ""):
        com_status_en(p, "Devolvida ao autor", "Returned to its author")
    return p


def _governo(rede: Rede, hj: str) -> None:
    """Projetos do Poder Executivo, leis do período (LEGIS) e vetos (VT e VP) -> dados/pessoas/gov-RS.json."""
    per = periodo_governo(UF)
    ini, atual = per["inicio"], int(hj[:4])
    gov: dict[str, dict] = {}
    for ano in range(int(ini[:4]), atual + 1):  # o ano de hoje todo dia; os anteriores a cada 3 dias (em rodízio)
        ttl = 20 if ano == atual or dia_rodizio(f"executivo-{ano}", 3) else 24 * 4
        for x in _pesquisa(rede, f"governo/projetos-{ano}.json", ttl, anoProposicao=ano, nomeProponente="Poder Executivo"):
            sig = (x.get("siglaTipoProposicao") or "").strip().upper()
            if sig in ("PL", "PLC", "PEC") and (_data(x) or "") >= ini and \
                    re.match(r"(?i)\s*poder executivo", x.get("nomeProponente") or ""):
                gov[f"{sig}-{x.get('nroProposicao')}-{x.get('anoProposicao')}"] = _proposta(x, "autor")
    vetos = []
    for sig in ("VT", "VP"):  # a lista de cada tipo vem inteira (de 1964 para cá): lida a cada 3 dias
        ttl = 20 if dia_rodizio(f"vetos-{sig}", 3) else 24 * 4
        for x in _pesquisa(rede, f"governo/{sig}.json", ttl, siglaTipoProposicao=sig):
            dt = data_iso(x.get("dthProtocolo")) or ""
            if ini <= dt <= hj and re.match(r"(?i)\s*poder executivo", x.get("nomeProponente") or ""):
                vetos.append((dt, sig))
    vetos.sort()
    leis: list[tuple[str, str]] | None = []
    try:
        for tipo, nome in ((20, "Lei"), (2, "Lei Complementar")):
            leis += [(d, nome) for _, _, d in _leis(rede, tipo, ini) if ini <= (d or "") <= hj]
        leis.sort()
    except SemTempo:  # o fim da rodada chegou: o perfil do governador fica como estava
        raise
    except Exception as e:  # o LEGIS fora do ar: fica a conta das leis da rodada anterior
        log(f"  RS: {e}")
        leis = None
    tot, par = sum(1 for v in vetos if v[1] == "VT"), sum(1 for v in vetos if v[1] == "VP")
    d_pt, d_en = desde(ini)
    esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                           "Na ALRS, o autor desses projetos aparece como \"Poder Executivo\".",
                           "At the ALRS, the author of these bills is listed as the executive branch.")
    f_gov = fonte(VEICULO, "Pesquisa de proposições do portal da ALRS (proponente: Poder Executivo)",
                  f"{SITE}/legislativo/pesquisa", hj)
    if leis is None:
        n_ord = n_lc = 0
        l_pt, l_en = ("As leis não entram nesta atualização: a pesquisa do Sistema LEGIS não respondeu.",
                      "Laws are not included in this update: the LEGIS search did not respond.")
    else:
        n_ord = sum(1 for _, n in leis if n == "Lei")
        n_lc = len(leis) - n_ord
        l_pt = (f"Leis: {qtd(n_ord, 'lei ordinária', 'leis ordinárias')} e {qtd(n_lc, 'lei complementar', 'leis complementares')} "
                f"desde {d_pt}, pela pesquisa do Sistema LEGIS da ALRS "
                "(data da lei). A pesquisa não separa as poucas leis promulgadas pela própria Assembleia (quando ela derruba "
                "um veto ou o governador não responde no prazo): elas estão na conta.")
        l_en = (f"Laws: {qtd(n_ord, 'ordinary law', 'ordinary laws')} and {qtd(n_lc, 'complementary law', 'complementary laws')} "
                f"since {d_en}, from the ALRS LEGIS search (by the law's "
                "date). The search does not single out the few laws promulgated by the Assembly itself (when it overrides a "
                "veto or the governor does not answer in time): they are included.")
    executivo = bloco_executivo(
        per, [fonte(VEICULO, "Sistema LEGIS: pesquisa de leis ordinárias e complementares por data", "https://ww3.al.rs.gov.br/legis/", hj),
              fonte(VEICULO, "Pesquisa de proposições do portal da ALRS: vetos total (VT) e parcial (VP)",
                    f"{SITE}/legislativo/pesquisa", hj)],
        f"{l_pt} Vetos: as proposições de veto total (VT) e parcial (VP) que o Poder Executivo mandou à Assembleia no período, "
        f"pela data de protocolo ({tot} {'total' if tot == 1 else 'totais'} e {par} {'parcial' if par == 1 else 'parciais'}).",
        f"{l_en} Vetoes: the full and partial veto messages the executive branch sent to the Assembly in the period, "
        f"by their filing date ({tot} full and {par} partial).",
        leis=len(leis) if leis is not None else None, vetos=len(vetos), vetos_totais=tot, vetos_parciais=par,
        ultima_lei=leis[-1][0] if leis else None, ultimo_veto=vetos[-1][0] if vetos else None)
    if leis is None and anterior_governo(UF, "executivo"):  # o LEGIS não respondeu: fica a conta da rodada anterior
        executivo = anterior_governo(UF, "executivo")
    gravar_governo(UF, per, sorted(gov.values(), key=lambda p: p["data"] or ""), *esc_g, f_gov, executivo)


def coletar() -> dict:
    rede = Rede("alrs", pausa=1.0)
    membros, ids, avisos = _membros(rede)
    for a in avisos:
        log(f"  RS: {a}")
    hj = hoje()
    nomes = {chave_nome(m["nome"]): k for k, pid in ids.items() for m in membros if m["id"] == pid}
    por_dep: dict[str, list] = {}
    falhas = 0
    for k in ids:
        try:
            lista = _lista(rede, k)
        except SemTempo:  # o fim da rodada chegou: nada pela metade (ficam os arquivos de antes)
            raise
        except Exception as e:  # um deputado fora do ar não derruba os outros: fica a lista da rodada anterior
            falhas += 1
            log(f"  RS: {e}")
            antes = ((ler_json(PESSOAS / f"{ids[k]}.json", {}) or {}).get("propostas") or {}).get("lista")
            if antes:
                por_dep[k] = antes
            continue
        for x in lista:
            sig = (x.get("siglaTipoProposicao") or "").strip().upper()
            if sig not in TIPOS or (_data(x) or "") < INICIO:
                continue
            prop = re.sub(r"(?i)^deputad[oa]\(a\)\s*|\s*\+\s*\d+\s*deputad.*$", "", x.get("nomeProponente") or "").strip()
            por_dep.setdefault(k, []).append(_proposta(x, "autor" if nomes.get(chave_nome(prop)) == k else "coautor"))
    if falhas > len(ids) // 3:
        raise RuntimeError(f"ALRS: {falhas} páginas de proposições falharam")
    f_lista = fonte(VEICULO, "Deputados em exercício (serviço de dados da página oficial \"Deputados\")", f"{SITE}/deputados", hj)
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"))
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        f_prop = fonte(VEICULO, f"Proposições de {m['nome']} (página oficial)", f"{SITE}/deputados/{k}/proposicoes", hj)
        extras[m["id"]] = {"links": {"oficial": m["url"], "email": m.pop("_email", None), "redes": []},
                           "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                           "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da ALRS", m["url"], hj)]}
    log(f"  RS: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    try:
        _governo(rede, hj)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  RS: governo: {e}")
    notas = [("As votações não entram: a ALRS mostra o voto de cada deputado só na página de cada proposição, uma por uma.",
              "Votes are not included: the ALRS shows each deputy's vote only on each bill's own page, one by one."),
             ("A lista de propostas de cada deputado mostra quem apresentou; quem só assinou junto pode não aparecer.",
              "Each deputy's list shows the bills they filed; co-signers may not appear.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
