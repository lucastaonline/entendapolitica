"""Assembleia Legislativa do Estado do Rio Grande do Sul (ALRS): o serviço de dados do portal da ALRS (o mesmo que a
página "Deputados" usa), as páginas oficiais de proposições de cada deputado e as planilhas de votação do Plenário.

Lista: https://ww4.al.rs.gov.br:5000/listarDestaqueDeputados (JSON usado pela página oficial "Deputados"): nome,
partido de hoje, e-mail, foto e códigos de cada deputado em exercício (55 cadeiras).
Propostas: a página oficial "Proposições" de cada deputado (ww4.al.rs.gov.br/deputados/<código>/proposicoes) traz,
dentro dela, a lista do sistema de processo legislativo da ALRS (ePRO) em JSON: tipo, número, ano, proponente,
situação atual e histórico, ementa. Entram PL, PLC (= PLP), PEC, PDL e PR (= PRC) protocolados desde 1º/2/2023. O
proponente principal é o autor; quando a lista mostra "Deputado(a) X + N Deputado(s)", X é o autor principal.
As páginas são lentas (~8 s cada): cada deputado é conferido a cada 3 dias (um terço por dia, em rodízio).
Situação: o texto oficial ("descricao") com as regras REGRAS.
Votações nominais do Plenário (desde a posse, INICIO), pelo portal do Departamento de Assessoramento Legislativo (DAL,
ww2.al.rs.gov.br/dal; formulários ASP.NET). A planilha de cada votação (DetalheVotacao/.../idProjeto/<número>) traz o
projeto, a data, a ementa do que foi votado, os totais, o resultado e o voto, o partido e o código de cada deputado (o
"codigoPro" da lista oficial; quem não tem o código de alguém da lista de hoje é ligado pelo nome, com
_votos_gastos.Nomes, e quem saiu da Assembleia fica fora). Nenhuma lista do portal mostra todas as votações: a pesquisa
"Planilhas de Votação" (um ano por vez, 20 por página) não mostra os requerimentos votados durante a sessão ("PL 172/2026
- RCD", preferência de votação) nem as votações de emendas ("PL 133/2025 - Emenda"); a página "Votos por Deputados" de
cada deputado de hoje (25 por página, um ano por vez) mostra os requerimentos, mas não as emendas. Por isso, além das
duas listas, as planilhas são procuradas número por número nas lacunas entre os números já conhecidos (_varredura); a
conferência é o "Nº Votação" de cada planilha, que em cada sessão tem de ir de 1 ao último sem buraco (o log avisa). A
planilha lida fica no cache para sempre (não muda); a pesquisa do ano de hoje é relida todo dia (as dos anos anteriores a
cada ~30 dias), a página de cada deputado (só no ano de hoje) a cada 3 dias, até as votações já lidas, e cada número
novo uma vez. Votações sem o voto de cada deputado e as das comissões não entram. Gastos: não há publicação aberta da
verba de cada gabinete.
O governo do estado (perfil do governador, dados/pessoas/gov-RS.json), desde o começo do mandato: os projetos do
proponente "Poder Executivo" (PL, PLC e PEC), pela pesquisa de proposições do portal (ww4.al.rs.gov.br/legislativo/
pesquisa/dados, um ano por vez, ~25 s cada); as leis ordinárias e complementares pela pesquisa do Sistema LEGIS
(ww3.al.rs.gov.br/legis, por data; a busca abre uma sessão no servidor); e os vetos pelas proposições "VT" (veto
total) e "VP" (veto parcial) do Poder Executivo protocoladas no período (a lista de cada tipo vem inteira, ~1 min:
lida a cada 3 dias).
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request

import regional
from comum import PESSOAS, UA, chave_nome, data_iso, hoje, ler_json, log, sem_acento

from . import _carga
from . import _votos_gastos as VG
from ._sse_comum import (Rede, SemTempo, anterior_governo, bloco_executivo, casar_membros, com_status_en, desde, dia_rodizio,
                         escopo, escopo_governo, fonte, gravar, gravar_governo, legislatura, membro, partido_sigla,
                         periodo_governo, qtd, resumo_status, sem_html)

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


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], dict[str, str], list[str]]:
    """(membros, {código do deputado: id da pessoa}, {"codigoPro" do deputado: id da pessoa}, avisos). O "codigoPro" é o
    código de cada deputado nas planilhas de votação (VotosPorDeputado/.../idpro/<código>)."""
    d = rede.json(f"{SITE}:5000/listarDestaqueDeputados", "deputados.json", 20)
    lista = [x for x in d.get("lista") or [] if str(x.get("codStatus")) == "1"]
    if not 45 <= len(lista) <= 60:
        raise RuntimeError(f"ALRS: a lista oficial veio com {len(lista)} pessoas")
    pessoas = [{"chave": str(x["idDeputado"]), "nome": (x.get("nomeDeputado") or "").strip(), "nomeCivil": None,
                "partido": partido_sigla(x.get("siglaPartido")), "email": x.get("emailDeputado"),
                "foto": x.get("fotoGrandeDeputado"), "pro": str(x.get("codigoPro") or "").strip()} for x in lista]
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids, pros = [], {}, {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        if p["pro"]:
            pros[p["pro"]] = pid
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], f"{SITE}/deputados/{p['chave']}",
                   (cand or {}).get("sit") == "SUPLENTE")
        m["_email"] = p["email"]
        membros.append(m)
    return membros, ids, pros, avisos


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


# ---------------------------------------------------------------- votações nominais do Plenário (planilhas de votação)
DAL = "https://ww2.al.rs.gov.br/dal/Sess%C3%A3oPlen%C3%A1ria"  # portal do Departamento de Assessoramento Legislativo
DAL_LISTA = f"{DAL}/PlanilhadeVota%C3%A7%C3%A3o/tabid/5626/Default.aspx"
_PV = "dnn$ctr8548$ViewalrsPesquisaVotacao$"  # prefixo dos campos do formulário da pesquisa
VOTOS_S = 4 * 60  # limite diário (segundos) da leitura das votações; na primeira carga, o resto da rodada
EMENTA_DAL = 400  # a planilha guarda só os primeiros 400 caracteres da ementa
VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "obstrucao": "Obstrução"}
# nomes das planilhas sem o código de alguém da lista de hoje, conferidos à mão: {nome como a planilha escreve: id ou "-"}
MANUAL_VOTOS: dict[str, str] = {}
VETO_RS: tuple[str, str] | None = None  # o que quer dizer o "sim" nos vetos (_votacoes(); vai também para a nota da Casa)
_LINHA = re.compile(r'idProjeto/(\d+)/Default\.aspx">([^<]*)</a>\s*</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*'
                    r'<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', re.S)


def _planilha_url(idv: str) -> str:
    """A planilha de uma votação (o voto de cada deputado)."""
    return f"{DAL}/DetalheVotacao/tabid/5627/idProjeto/{idv}/Default.aspx"


def _deputado_url(cod: str) -> str:
    """"Votos por Deputados": as votações de um deputado ("codigoPro"), da mais nova para a mais antiga, um ano por vez."""
    return f"{DAL}/VotosPorDeputado/tabid/5628/idpro/{cod}/Default.aspx"


def _dal_campos(t: str, pesquisa: bool = True) -> dict[str, str]:
    """Os campos do formulário de uma página do DAL, como o navegador mandaria (ASP.NET: o __VIEWSTATE de cada página
    guarda o filtro e a página da lista em que se está)."""
    campos = {}
    for a in re.findall(r"<input\b([^>]*)>", t):
        n = re.search(r'\bname="([^"]+)"', a)
        tipo = (re.search(r'\btype="([^"]+)"', a) or [None, "text"])[1].lower()
        if not n or tipo in ("submit", "button", "image", "reset") or "disabled" in a or \
                (tipo in ("radio", "checkbox") and "checked" not in a):
            continue
        v = re.search(r'\bvalue="([^"]*)"', a)
        campos[_html.unescape(n.group(1))] = _html.unescape(v.group(1)) if v else ""
    for n, opcoes in re.findall(r'<select\b[^>]*\bname="([^"]+)"[^>]*>(.*?)</select>', t, re.S):
        v = re.search(r'<option selected="selected" value="([^"]*)"', opcoes) or re.search(r'<option value="([^"]*)"', opcoes)
        campos[_html.unescape(n)] = _html.unescape(v.group(1)) if v else ""
    if pesquisa:  # todos os proponentes
        campos[_PV + "cboProponente$TextBox"], campos[_PV + "cboProponente$HiddenField"] = "Todos", "0"
    return campos


def _dal_post(rede: Rede, campos: dict[str, str], url: str = DAL_LISTA,
              marca: str = r"\d+ registro\(s\) encontrado|(?i:nenhum (registro|resultado))") -> str:
    t = rede.bruto(url, None, headers={"Content-Type": "application/x-www-form-urlencoded"},
                   dados=urllib.parse.urlencode(campos).encode(), timeout=180).decode("utf-8", "replace")
    if not re.search(marca, t):
        raise RuntimeError("ALRS: o portal do DAL não devolveu a lista de votações")
    return t


def _dal_ano(rede: Rede, ano: int, ttl: float) -> list[dict]:
    """As votações nominais do Plenário de um ano pela pesquisa "Planilhas de Votação" (20 por página):
    [{"id", "proposta", "data", "resultado"}]. O ano só é guardado quando todas as páginas vieram."""
    nome = f"listas/{ano}.json"
    if rede.fresco(nome, ttl):
        return rede.estado(nome, [])
    t = ""
    for tentativa in (0, 1):  # o formulário guardado pode ter ficado velho (o servidor recusa o __VIEWSTATE): lê de novo
        form = rede.texto(DAL_LISTA, "pesquisa.html", 20 if tentativa == 0 else 0, timeout=120)
        if not re.search(rf'<option (?:selected="selected" )?value="{ano}">', form):
            log(f"  RS votações: a pesquisa das planilhas de votação não oferece o ano {ano} (sem votação nominal nele)")
            return []
        campos = _dal_campos(form)
        campos.update({_PV + "ddlAno": str(ano), _PV + "ddlMes": "0", _PV + "btnPesquisar": "Pesquisar"})
        try:
            t = _dal_post(rede, campos)
            break
        except SemTempo:
            raise
        except RuntimeError:
            if tentativa:
                raise
    linhas: dict[str, tuple] = {}
    pag = 1
    while True:
        m = re.search(r"(\d+) registro\(s\) encontrado", t)
        total = int(m.group(1)) if m else 0
        for x in _LINHA.findall(t):
            linhas[x[0]] = x
        if len(linhas) >= total or not re.search(rf"'Page\${pag + 1}'", t):
            break
        pag += 1
        campos = _dal_campos(t)
        campos.update({"__EVENTTARGET": _PV + "grdResultado", "__EVENTARGUMENT": f"Page${pag}"})
        t = _dal_post(rede, campos)
    if len(linhas) != total:
        raise RuntimeError(f"ALRS: a pesquisa das planilhas de votação de {ano} trouxe {len(linhas)} de {total} votações")
    lista = [{"id": i, "proposta": re.sub(r"\s+", " ", sem_html(p) or ""), "data": data_iso(sem_html(d)),
              "resultado": sem_html(r)} for i, p, _, d, _, r in linhas.values()]
    rede.guardar(lista, nome)
    return lista


_VD = "dnn$ctr8552$ViewalrsVotosDeputados$"  # prefixo dos campos da página "Votos por Deputados"
_LINHA_DEP = re.compile(r"<td>(\d\d/\d\d/\d{4})</td>(?:(?!</tr>).)*?idProjeto=(\d+)", re.S)
_TEM_DEP = r'_grdListaVotos"|(?i:nenhum (registro|resultado))'


def _deputado_ano(rede: Rede, cod: str, ano: int, aberta: str, corte: str | None) -> dict[str, str]:
    """{id da votação: data} de um deputado num ano, pela página "Votos por Deputados" (25 por página, da mais nova para a
    mais antiga; `aberta` = a página do deputado já aberta). corte: lê só até passar dessa data (o resto foi lido antes)."""
    sel = re.search(r'name="[^"]*ddlAnos"[^>]*>(.*?)</select>', aberta, re.S)
    if not sel or f'value="{ano}"' not in sel.group(1):
        return {}  # o ano não aparece para o deputado: nenhum voto nele
    url, t = _deputado_url(cod), aberta
    if not re.search(rf'<option selected="selected" value="{ano}"', sel.group(1)):
        campos = _dal_campos(aberta, pesquisa=False)
        campos.update({_VD + "ddlAnos": str(ano), "__EVENTTARGET": _VD + "ddlAnos", "__EVENTARGUMENT": ""})
        t = _dal_post(rede, campos, url, _TEM_DEP)
    ids: dict[str, str] = {}
    pag = 1
    while True:
        linhas = [(i, data_iso(d)) for d, i in _LINHA_DEP.findall(t)]
        if any(d[:4] != str(ano) for _, d in linhas):
            raise RuntimeError(f"ALRS: a página de votos do deputado {cod} não mostrou o ano {ano}")
        ids.update(linhas)
        if (corte and linhas and linhas[-1][1] < corte) or not re.search(rf"'Page\${pag + 1}'", t):
            return ids
        pag += 1
        campos = _dal_campos(t, pesquisa=False)
        campos.update({"__EVENTTARGET": _VD + "grdListaVotos", "__EVENTARGUMENT": f"Page${pag}"})
        t = _dal_post(rede, campos, url, _TEM_DEP)


def _modo_deputado(st: dict | None, hj: str, cod: str) -> str | None:
    """Como ler as votações de um deputado no ano: "tudo" (nunca lido inteiro), "novos" (só as recentes: a cada 3 dias,
    em rodízio) ou None (nada hoje)."""
    if not st or not st.get("completo"):
        return "tudo"
    dias = (_dt.date.fromisoformat(hj) - _dt.date.fromisoformat(st["lido"])).days
    return "novos" if dias >= 1 and (dia_rodizio(cod, 3) or dias >= 4) else None


def _planilha(rede: Rede, idv: str) -> dict | None:
    """A planilha de uma votação: projeto, data, ementa, sessão, totais e resultado, e o voto de cada deputado
    ([código, nome, partido, voto]). Planilha publicada não muda: fica no cache para sempre (em JSON, sem o HTML); a que
    veio sem votos ou com a soma diferente dos totais é relida no dia seguinte, até ficar completa. None se o número não
    tem planilha; {"semVotacao": True} se o projeto está registrado para votar, mas sem votação ainda."""
    nome = f"planilhas/{idv}.json"
    x = rede.estado(nome) if rede.fresco(nome, None) else None
    if x and not (x.get("conferir") and not rede.fresco(nome, 20)):
        return x
    t = rede.texto(_planilha_url(idv), None, timeout=120)
    cab = {k: sem_html(v) or "" for k, v in re.findall(r'_ViewalrsExibeVotacao_lbl(\w+)">(.*?)</span>', t, re.S)}
    if not cab.get("Projeto"):
        return None
    if not data_iso(cab.get("DataVotacao")):
        return {"semVotacao": True}  # registrada para votar, sem votação ainda
    tab = re.search(r'_grdVotosDeputados"[^>]*>(.*?)</table>', t, re.S)
    votos = []
    for partido, cel, voto in re.findall(r'<tr class="GridView\w*Style">\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*'
                                         r'<td[^>]*>(.*?)</td>\s*</tr>', tab.group(1) if tab else "", re.S):
        cod = re.search(r"/idpro/(\d+)/", cel)
        votos.append([cod.group(1) if cod else None, sem_html(cel) or "", sem_html(partido) or "", sem_html(voto) or ""])

    def num(k: str) -> int | None:
        return int(cab[k]) if (cab.get(k) or "").isdigit() else None

    x = {"proposta": re.sub(r"\s+", " ", cab["Projeto"]), "data": data_iso(cab["DataVotacao"]), "ementa": cab.get("Ementa") or None,
         "sessao": " ".join(s for s in (cab.get("TipoSessao"), cab.get("SessionNumber")) if s) or None,
         "ordem": cab.get("SequenceNumber") or None, "resultado": cab.get("ResultadoVotacao") or None,
         "sim": num("TotalSim"), "nao": num("TotalNao"), "total": num("TotalVotos"), "votos": votos}
    soma = [VOTO.get(sem_acento(v[3]).lower()) for v in votos]
    if not votos or (soma.count("Sim"), soma.count("Não"), len(soma)) != (x["sim"], x["nao"], x["total"]):
        x["conferir"] = True
    rede.guardar(x, nome)
    return x


def _so_letras(s: str) -> str:
    return re.sub(r"\W+", "", sem_acento(s or "").lower())


def _ementa(rede: Rede, idv: str, v: dict) -> str | None:
    """A ementa do que foi votado. Quando a da planilha veio cortada (400 caracteres), a inteira vem da página da
    proposição no portal (lida uma vez só), se começar igual; senão, fica a da planilha, com "…" no fim."""
    e = v.get("ementa")
    if not e or len(e) < EMENTA_DAL - 5:
        return e
    if "ementaInteira" not in v:
        # "PL 8/2023 (Substitutivo 1)" também serve; "PL 172/2026 - RCD" (requerimento) não: a ementa é a do pedido
        sig = re.match(r"([A-Z]+) (\d+)/(\d{4})(?!\s*-)", v["proposta"])
        inteira = ""
        if sig:
            try:
                t = rede.texto(f"{SITE}/proposicao/{sig.group(1)}/{sig.group(2)}/{sig.group(3)}", None, timeout=180)
                m = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', t, re.S)
                dados = ((json.loads(m.group(1)).get("#proposicao") or {}).get("dados") or {}) if m else {}
                cheia = re.sub(r"\s+", " ", dados.get("ementa") or "").strip()
                if _so_letras(cheia).startswith(_so_letras(e)):
                    inteira = cheia
            except SemTempo:
                raise
            except Exception as erro:  # o portal fora do ar: fica a ementa cortada nesta rodada
                log(f"  RS votações: ementa inteira de {v['proposta']}: {erro}")
                return e.rstrip() + "…"
        v["ementaInteira"] = inteira
        rede.guardar(v, f"planilhas/{idv}.json")
    return v["ementaInteira"] or e.rstrip() + "…"


LACUNA_MAX = 100  # lacuna maior entre dois números de planilha = as emendas do Orçamento, registradas uma a uma
BORDA = 30  # numa lacuna maior, procura só os primeiros e os últimos números dela


def _varredura(rede: Rede, conhecidos: set[str], hj: str, sem_tempo) -> tuple[dict[str, str], bool]:
    """As planilhas que nenhuma lista mostra (as votações de emendas, "PL 133/2025 - Emenda"), procuradas número por
    número nas lacunas entre os números das votações conhecidas (nas lacunas grandes, que são as emendas do Orçamento
    registradas uma a uma e votadas em bloco, só nas bordas). Cada número é visto uma vez; o projeto registrado para votar
    e ainda sem votação é visto de novo a cada 7 dias (por um ano). Devolve ({número: data} das achadas, se terminou)."""
    est = rede.estado("varredura.json", {}) or {}
    vazias = set(est.get("vazias") or [])
    achadas: dict[str, str] = dict(est.get("achadas") or {})
    pendentes: dict[str, list[str]] = dict(est.get("pendentes") or {})  # {número: [visto primeiro, visto por último]}

    def guardar() -> None:
        rede.guardar({"vazias": sorted(vazias), "achadas": achadas, "pendentes": pendentes}, "varredura.json")

    def dias(d: str) -> int:
        return (_dt.date.fromisoformat(hj) - _dt.date.fromisoformat(d)).days

    ns = sorted({int(i) for i in conhecidos} | {int(i) for i in achadas})
    alvo: list[int] = []
    for a, b in zip(ns, ns[1:]):
        alvo += range(a + 1, b) if b - a - 1 <= LACUNA_MAX else [*range(a + 1, a + 1 + BORDA), *range(b - BORDA, b)]
    terminou = True
    try:  # o que foi visto fica guardado mesmo se o tempo da rodada acabar no meio
        for n, i in enumerate(alvo):
            k = str(i)
            if i in vazias or k in achadas or k in conhecidos or (k in pendentes and (dias(pendentes[k][1]) < 7 or
                                                                                      dias(pendentes[k][0]) > 365)):
                continue
            if sem_tempo():
                terminou = False
                break
            try:
                p = _planilha(rede, k)
            except SemTempo:
                raise
            except Exception as erro:  # o portal fora do ar: a varredura continua na próxima rodada
                log(f"  RS votações: varredura das planilhas parou no número {k}: {erro}")
                terminou = False
                break
            if p is None:
                vazias.add(i)
            elif p.get("semVotacao"):
                pendentes[k] = [(pendentes.get(k) or [hj])[0], hj]
            else:
                achadas[k] = p["data"]
                pendentes.pop(k, None)
            if n % 50 == 49:
                guardar()
    finally:
        guardar()
    return achadas, terminou


def _votacoes(membros: list[dict], pros: dict[str, str], hj: str) -> dict[str, dict] | None:
    """{id da pessoa: bloco "votacoes"} com as votações nominais do Plenário desde a posse (INICIO), ou None enquanto a
    primeira carga não termina (os perfis ficam com o bloco publicado antes; o que já foi lido fica no cache).
    1) a pesquisa "Planilhas de Votação" (a lista oficial, um ano por vez); 2) a página "Votos por Deputados" de cada
    deputado de hoje, no ano de hoje, que mostra também os requerimentos votados durante a sessão (como os de preferência
    de votação); 3) a varredura dos números de planilha (as votações de emendas, que nenhuma lista mostra); 4) a planilha
    de cada votação."""
    rede = Rede("alrs-votos", pausa=1.0)
    est = rede.estado("estado.json", {}) or {}
    primeira = not est.get("completa")
    limite, t0 = _carga.limite_diario(VOTOS_S, primeira), time.time()

    def sem_tempo() -> bool:
        return time.time() - t0 > limite

    def andamento(o_que: str) -> None:
        log(f"  RS votações: carga em andamento ({o_que}; {rede.pedidos} pedidos); continua na próxima rodada")

    atual = int(hj[:4])
    anos = list(range(int(INICIO[:4]), atual + 1))
    datas: dict[str, str] = {}  # id da votação -> data
    da_pesquisa: set[str] = set()
    for ano in anos:
        # o ano de hoje (e o anterior, em janeiro) todo dia; os outros a cada ~30 dias (espalhados entre os anos)
        ttl = 20 if ano == atual or (ano == atual - 1 and hj[5:7] == "01") else 24 * (28 + ano % 5)
        if not rede.fresco(f"listas/{ano}.json", ttl) and sem_tempo() and primeira:
            andamento(f"lista de {ano}")
            return None
        try:
            do_ano = _dal_ano(rede, ano, ttl) if not sem_tempo() else rede.estado(f"listas/{ano}.json", [])
        except SemTempo:
            raise
        except Exception as erro:  # a pesquisa falhou: vale a lista lida antes desse ano (se houver)
            do_ano = rede.estado(f"listas/{ano}.json")
            if do_ano is None:
                raise
            log(f"  RS votações: {erro}; fica a lista de {ano} lida antes")
        for x in do_ano:
            if x["data"] and INICIO <= x["data"] <= hj:
                datas[x["id"]] = x["data"]
                da_pesquisa.add(x["id"])
    # a página "Votos por Deputados" só no ano de hoje (e no anterior, em janeiro): os requerimentos votados durante a
    # sessão aparecem nela em até 3 dias; os dos anos anteriores, a varredura (abaixo) acha entre os números conhecidos
    anos_dep = [a for a in anos if a == atual or (a == atual - 1 and hj[5:7] == "01")]
    incompletos: set[str] = set()  # deputados ainda sem as votações do ano lidas por inteiro
    for cod in sorted(pros, key=lambda c: (len(c), c)):
        nome_d = f"deputados/{cod}.json"
        dep = rede.estado(nome_d, {}) or {}
        aberta = None
        try:
            for ano in reversed(anos_dep):
                st = dep.get(str(ano))
                modo = _modo_deputado(st, hj, cod)
                if not modo or sem_tempo():
                    continue
                if aberta is None:
                    aberta = rede.texto(_deputado_url(cod), None, timeout=120)
                    if "ddlAnos" not in aberta:
                        raise RuntimeError(f"ALRS: a página de votos do deputado {cod} veio sem a lista")
                ate = (st or {}).get("ate")
                corte = (_dt.date.fromisoformat(ate) - _dt.timedelta(days=14)).isoformat() if modo == "novos" and ate else None
                ids = dict((st or {}).get("ids") or {}) if modo == "novos" else {}
                ids.update(_deputado_ano(rede, cod, ano, aberta, corte))
                dep[str(ano)] = {"ids": ids, "ate": max(ids.values(), default=None), "lido": hj, "completo": True}
                rede.guardar(dep, nome_d)
        except SemTempo:
            raise
        except Exception as erro:  # a página de um deputado fora do ar não segura as outras: fica o que já foi lido
            log(f"  RS votações: {erro}")
        if any(not (dep.get(str(a)) or {}).get("completo") for a in anos_dep):
            incompletos.add(cod)
        for st in dep.values():
            for i, d in (st.get("ids") or {}).items():
                if d and INICIO <= d <= hj:
                    datas.setdefault(i, d)
    if incompletos and primeira:
        andamento(f"votos por deputado: faltam {len(incompletos)} de {len(pros)} deputados")
        return None
    achadas, terminou = _varredura(rede, set(datas), hj, sem_tempo)
    for i, d in achadas.items():
        if d and INICIO <= d <= hj:
            datas.setdefault(i, d)
    if not terminou and primeira:
        andamento(f"varredura das planilhas: {len(achadas)} achadas até aqui")
        return None
    planilhas: dict[str, dict] = {}
    faltam = 0
    for idv in sorted(datas, key=int):
        if not rede.fresco(f"planilhas/{idv}.json", None) and sem_tempo():
            faltam += 1
            continue
        try:
            p = _planilha(rede, idv)
        except SemTempo:
            raise
        except Exception as erro:  # uma planilha fora do ar não segura as outras: tenta de novo na próxima rodada
            log(f"  RS votações: planilha {idv}: {erro}")
            p = None
        if p and not p.get("semVotacao"):
            planilhas[idv] = p
    if faltam and primeira:
        andamento(f"{len(planilhas)} de {len(datas)} planilhas lidas")
        return None
    if faltam:
        log(f"  RS votações: {faltam} planilhas novas ficam para a próxima rodada (tempo)")
    nomes = VG.Nomes(membros, MANUAL_VOTOS)
    por_pessoa: dict[str, dict[str, dict]] = {}
    pelo_nome: dict[str, str] = {}
    difs, vazias, outros = [], [], {}
    for idv, v in planilhas.items():
        votos = [(cod, nome, VOTO.get(sem_acento(voto).lower(), voto)) for cod, nome, _, voto in v["votos"] if voto]
        if not votos:
            vazias.append(idv)
            continue
        pl = VG.placar([vt for _, _, vt in votos])
        if (v.get("sim"), v.get("nao"), v.get("total")) != (pl["Sim"], pl["Não"], pl["total"]):
            difs.append(idv)  # vale a soma dos votos da planilha
        chave = f"alrs-vot:{idv}"
        # "PL 172/2026 - RCD": requerimento votado durante a sessão sobre o PL 172/2026 (a ementa diz o que se pediu); a
        # proposta é o PL, como na página "Votos por Deputados". "PL 8/2023 (Substitutivo 1)" fica como está.
        sig = re.match(r"([A-Z]+) (\d+)/(\d{4})", v["proposta"])
        proposta = re.sub(r"\s*-\s*RCD$", "", v["proposta"])
        ementa = _ementa(rede, idv, v)
        for cod, nome, vt in votos:
            if vt not in VG.VOTOS_RESUMO:
                outros[vt] = outros.get(vt, 0) + 1
            pid = pros.get(cod or "")
            if not pid:  # sem código da lista de hoje: quem saiu (fica fora) ou código diferente (liga pelo nome)
                pid = nomes.quem(nome)
                if pid:
                    pelo_nome[nome] = pid
            if pid:
                por_pessoa.setdefault(pid, {})[chave] = VG.item_voto(
                    chave, vt, v["data"], proposta, ementa, v.get("resultado"), pl, _planilha_url(idv),
                    f"alrs:{sig.group(1)}-{sig.group(2)}-{sig.group(3)}" if sig else None)
    # o que quer dizer o "sim" nos vetos (conferido em 26/10/2026: VT 599/2023 "Rejeitado" com 38 "não" de 55 deputados)
    global VETO_RS
    vetos = [(pv["Sim"], pv["Não"], v.get("resultado")) for v in planilhas.values() if re.match(r"VT\b", v.get("proposta") or "")
             and (pv := VG.placar([VOTO.get(sem_acento(vt).lower(), vt) for _, _, _, vt in v["votos"] if vt]))]
    VETO_RS = VG.sentido_veto(vetos, len(membros))
    esc_pt, esc_en = VG.escopo_votos("ALRS", *desde(INICIO), extra=VETO_RS)
    f_v = fonte(VEICULO, "Planilhas de Votação do Plenário (Departamento de Assessoramento Legislativo)", DAL_LISTA, hj)
    blocos = {pid: b for pid, d in por_pessoa.items() if (b := VG.bloco_votacoes(list(d.values()), esc_pt, esc_en, f_v))}
    for cod in incompletos:  # deputado novo na lista, com o ano ainda por ler: fica o bloco publicado antes
        blocos.pop(pros[cod], None)
        if VG.de_antes(pros[cod], "votacoes"):
            blocos[pros[cod]] = VG.de_antes(pros[cod], "votacoes")
    if not est.get("completa"):
        rede.guardar(dict(est, completa=True), "estado.json")
    dts = sorted(v["data"] for v in planilhas.values())
    so_dep = len(set(planilhas) - da_pesquisa - set(achadas))
    so_varr = len(set(planilhas) & set(achadas))
    log(f"  RS: {len(planilhas)} votações nominais do Plenário" + (f" ({dts[0]} a {dts[-1]})" if dts else "") +
        f": {len(set(planilhas) & da_pesquisa)} da pesquisa, {so_dep} só nas páginas \"Votos por Deputados\" e {so_varr} "
        f"achadas na varredura das planilhas; votos de {len(blocos)} deputados de hoje; {rede.pedidos} pedidos ao portal do DAL")
    if incompletos:
        log(f"  RS votações: deputados com votos por ler (fica o bloco de antes): {sorted(incompletos)}")
    sessoes: dict[tuple, set[int]] = {}
    for v in planilhas.values():
        if (v.get("ordem") or "").isdigit():
            sessoes.setdefault((v["data"], v.get("sessao")), set()).add(int(v["ordem"]))
    buracos = {f"{d} {s}": sorted(set(range(1, max(o) + 1)) - o) for (d, s), o in sessoes.items() if len(o) < max(o)}
    if buracos:
        log(f"  RS votações: sessões com \"Nº Votação\" sem planilha achada até aqui (conferir): "
            f"{dict(list(sorted(buracos.items()))[-8:])}")
    if difs:
        log(f"  RS votações: em {len(difs)} planilhas a soma dos votos não bate com o total publicado (vale a soma): {difs[:10]}")
    if vazias:
        log(f"  RS votações: {len(vazias)} planilhas sem o voto de cada deputado (ficam fora): {vazias[:10]}")
    if outros:
        log(f"  RS votações: votos fora de Sim/Não/Abstenção/Obstrução: {outros}")
    if pelo_nome:
        log(f"  RS votações: ligados pelo nome (o código da planilha não é o da lista de hoje; conferir): {pelo_nome}")
    nomes.avisar("RS", "votações")
    return blocos


def coletar() -> dict:
    rede = Rede("alrs", pausa=1.0)
    membros, ids, pros, avisos = _membros(rede)
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
    try:  # com limite de tempo próprio (VOTOS_S); na primeira carga, o resto da rodada
        blocos_v = _votacoes(membros, pros, hj)
    except Exception as e:  # inclui o fim da rodada (SemTempo): ficam as votações publicadas antes
        log(f"  RS votações: {type(e).__name__}: {e} (ficam as votações publicadas antes)")
        blocos_v = None
    com_votos = VG.aplicar(extras, blocos_v, "votacoes")
    d_pt, d_en = desde(INICIO)
    if com_votos:
        nota_v = (f"Votações: entram as votações do Plenário com o voto de cada deputado (nominais) desde {d_pt}, pelas "
                  "planilhas de votação do portal do Departamento de Assessoramento Legislativo da ALRS. Nenhuma lista do "
                  "portal mostra todas as votações: além da pesquisa \"Planilhas de Votação\" e da página \"Votos por "
                  "Deputados\" de cada deputado, o site procura as planilhas número por número (é assim que entram as "
                  "votações de emendas e de requerimentos feitos durante a sessão). Votações sem o voto de cada deputado e as "
                  "das comissões não entram.",
                  f"Votes: roll-call votes in the full Assembly (where each deputy's vote is recorded) since {d_en}, from the "
                  "voting sheets on the ALRS Legislative Advisory Department's website. No list on that website shows every "
                  "vote: besides the voting sheet search and each deputy's page of votes, this site looks for the sheets "
                  "number by number (that is how votes on amendments and on "
                  "procedural requests made during the session are included). Votes without each deputy's vote and committee "
                  "votes are not included.")
        if VETO_RS:
            nota_v = (f"{nota_v[0]} {VETO_RS[0]}.", f"{nota_v[1]} {VETO_RS[1]}.")
    else:
        nota_v = ("As votações do Plenário, com o voto de cada deputado, estão nas \"Planilhas de Votação\" do portal do "
                  "Departamento de Assessoramento Legislativo da ALRS (ww2.al.rs.gov.br/dal).",
                  "Votes in the full Assembly, with each deputy's vote, are in the voting sheets on "
                  "the ALRS Legislative Advisory Department's website (ww2.al.rs.gov.br/dal).")
    notas = [nota_v,
             ("A lista de propostas de cada deputado mostra quem apresentou; quem só assinou junto pode não aparecer.",
              "Each deputy's list shows the bills they filed; co-signers may not appear."),
             ("Os gastos não entram: a ALRS mostra os gastos de cada gabinete no seu Portal da Transparência "
              "(transparencia.al.rs.gov.br), que não respondeu quando foi conferido, em 26/10/2026; por isso não foi possível "
              "ver em que formato esses dados estão.",
              "Spending is not included: the ALRS shows each office's spending on its transparency portal "
              "(transparencia.al.rs.gov.br), which did not respond when checked, on October 26, 2026, so it was not possible "
              "to see what format that data is in.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": com_votos, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
