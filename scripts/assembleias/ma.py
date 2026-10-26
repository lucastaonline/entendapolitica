"""Assembleia Legislativa do Estado do Maranhão (Alema): sistema legislativo AlemaLegis, com API pública
(https://alemalegis.al.ma.leg.br/api/v1/public/, a mesma que alimenta https://alemalegis.al.ma.leg.br/; o endereço antigo
sapl.al.ma.leg.br leva para lá).

Lista: /parliamentary?activeInHouse=ACTIVE&legislature=<atual> (42 pessoas, com o partido de hoje). As fotos do sistema
são links temporários (expiram em uma hora), então ficam as fotos do TSE.
Propostas: /legislative-matter/filter/access?legislativeMatterTypeId=..&year=.. (projetos de lei ordinária, de lei
complementar, de emenda constitucional, de decreto legislativo e de resolução legislativa) desde 1º/2/2023, com os
autores, a situação ("situation") e a norma que a proposta virou ("legalNorms"). Vetos: tipos Veto Total e Veto Parcial.
Gastos (gastos()): a Cota para o Exercício da Atividade Parlamentar (CEAP), pelas páginas "Cotas para Exercício da
Atividade Parlamentar" do Portal da Transparência da Alema (https://sistemas.al.ma.leg.br/transparencia/, outro sistema),
desde fevereiro de 2023: o valor ressarcido de cada mês (o que a Alema pagou) e as despesas por tipo da própria página.
"""
from __future__ import annotations

import datetime as dt
import html
import http.cookiejar
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import regional
from comum import UA, chave_nome, fonte, hoje, log, sem_acento

from . import _carga
from . import _ne_gov as gv
from . import _votos_gastos as VG
from ._carga import SemTempo
from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, feito, gravar, legislatura_estadual,
                        membro, nome_lei, partido_sigla, resumo_status, vez)

API = "https://alemalegis.al.ma.leg.br/api/v1/public"
SITE = "https://alemalegis.al.ma.leg.br"
VEICULO = "Assembleia Legislativa do Maranhão (Alema)"
TIPOS = {10110: ("PL", "PLO"), 10114: ("PLP", "PLC"), 10123: ("PEC", "PEC"), 10115: ("PDL", "PDL"), 10111: ("PRC", "PRE")}
TIPOS_GOV = {10110: ("PL", "PLO"), 10114: ("PLP", "PLC"), 10123: ("PEC", "PEC"), 10115: ("PDL", "PDL"), 10118: ("MPV", "MPV")}
VETOS = {10120: True, 10124: False}
NORMA = [(r"lei complementar", "Lei Complementar"), (r"emenda", "Emenda Constitucional"), (r"decreto legislativo", "Decreto Legislativo"),
         (r"resolu", "Resolução"), (r"^lei", "Lei")]

# situação oficial (sem acento, minúsculas) -> status do site
REGRAS = [
    (r"transformad[ao] em (lei|norma)|lei sancionada|promulgad|sancionad", "lei", "Virou lei", None),
    (r"veto .*mantido|veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto .*rejeitado|veto .*derrubado", "aprovada", "Aprovada; o veto do governador foi derrubado e falta promulgar",
     "Approved; the governor's veto was overridden and it still has to be promulgated"),
    (r"retirad[ao] (pel[oa] autor|a pedido)", "retirada", None, None),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] ao autor", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"arquivad", "arquivada", "Arquivada", None),
    (r"anexad|apensad", "junta", None, None),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando sancao|autografo", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"parecer contrario", "andando", "Uma comissão deu parecer contra; falta a decisão final",
     "A committee recommended rejecting it; the final decision is pending"),
    (r"aprovad[ao] (em|no|pelo) plenario|aprovad[ao] em (discussao|votacao|turno unico|segundo turno|2)", "aprovada", None, None),
    (r"tramitacao inicial", "andando", "Apresentada; ainda vai começar a ser analisada", None),
    (r".", "andando", None, None),
]


def _norma(desc: str | None) -> str | None:
    d = sem_acento((desc or "").lower()).strip()
    for exp, nome in NORMA:
        if re.search(exp, d):
            return nome
    return None


def _legislatura(rede: Rede) -> dict:
    """A legislatura em curso pelo número (a Alema cadastra as legislaturas de 1º de janeiro a 31 de dezembro, mas a posse
    é em 1º de fevereiro: art. 29, § 3º, da Constituição do Maranhão)."""
    legs = rede.json(f"{API}/legislature", "legislaturas.json", 24 * 7)
    n = str(legislatura_estadual(20))
    for l in legs:
        if str(l.get("legislatureNumber")) == n:
            return l
    raise RuntimeError(f"Alema: legislatura {n} não encontrada")


def coletar() -> dict:
    rede = Rede("alema", pausa=0.5, timeout=90)
    leg = _legislatura(rede)
    d = rede.json(f"{API}/parliamentary?page=0&size=100&sort=parliamentaryName,asc&activeInHouse=ACTIVE&legislature={leg['id']}",
                  f"parlamentares-{leg['id']}.json", 20)
    ativos = d.get("content") or []
    if not 35 <= len(ativos) <= 50:
        raise RuntimeError(f"Alema: {len(ativos)} deputados ativos (esperado: 42)")
    # propostas: por tipo e por ano
    mats: dict[str, dict] = {}
    anos = range(int(INICIO[:4]), int(hoje()[:4]) + 1)
    for tp in list(TIPOS) + [10118] + list(VETOS):
        for ano in anos:
            pag = 0
            while True:
                r = rede.json(f"{API}/legislative-matter/filter/access?page={pag}&size=200&sort=number,desc&legislativeMatterTypeId={tp}&year={ano}")
                for x in r.get("content") or []:
                    mats[str(x["id"])] = {"tp": tp, "n": x.get("number"), "a": x.get("year"), "d": x.get("presentationDate"),
                                          "e": (x.get("ement") or "").strip(), "au": (x.get("authorNames") or "").strip(),
                                          "sit": (x.get("situation") or "").strip() or None, "da": x.get("forwardingDate"),
                                          "leis": x.get("legalNorms") or []}
                if pag + 1 >= int(r.get("totalPages") or 0):
                    break
                pag += 1
    vetos = {}
    for k, v in mats.items():
        if v["tp"] not in VETOS:
            continue
        m = re.search(r"projeto de lei( complementar)?( ordinaria)?\D{0,10}([\d.]+)\s*/\s*(\d{4})", sem_acento(v["e"].lower()))
        if m:
            vetos[(10114 if m.group(1) else 10110, str(int(m.group(3).replace(".", ""))), m.group(4))] = {"total": VETOS[v["tp"]], "d": v["d"]}
    log(f"  MA: {sum(1 for v in mats.values() if v['tp'] in TIPOS)} propostas desde 2023 (todas as autorias); {len(vetos)} vetos ligados")
    # pessoas
    pessoas = [{"chave": str(p["id"]), "nome": re.sub(r"\s+", " ", (p.get("parliamentaryName") or "").strip()),
                "nomeCivil": re.sub(r"\s+", " ", (p.get("fullName") or "").strip()) or None,
                "partido": partido_sigla(((p.get("partyAffiliationId") or {}).get("partyAcronym"))), "id": p["id"]} for p in ativos]
    ligados, avisos = casar_membros("MA", pessoas, TSE_MANUAL)
    for a in avisos:
        log(f"  MA TSE: {a}")
    por_nome: dict[str, list[tuple[str, str]]] = {}
    for k, v in mats.items():
        if v["tp"] not in TIPOS or (v["d"] or "") < INICIO:
            continue
        nomes = [n.strip() for n in re.split(r",|;| e (?=[A-ZÁÉÍÓÚ])", v["au"]) if n.strip()]
        for i, n in enumerate(nomes):
            por_nome.setdefault(chave_nome(n), []).append((k, "autor" if i == 0 else "coautor"))
    membros, extras, listas = [], {}, []
    fonte_l = fonte(VEICULO, f"Parlamentares em atividade na {leg.get('legislatureNumber')}ª legislatura (AlemaLegis)",
                    f"{SITE}/sapl/protocol/parliamentary/research")
    from tse import url_foto  # as fotos do sistema da Alema expiram; a do TSE (pública) vale para eleitos e suplentes

    for p in pessoas:
        cand = ligados.get(p["chave"])
        pid = regional.id_pessoa("dest", "MA", cand, p["nome"])
        url = f"{SITE}/sapl/protocol/parliamentary/details/{p['id']}"
        membros.append(membro(pid, p["nome"], p["nomeCivil"] if p["nomeCivil"] != p["nome"] else None, p["partido"],
                              (cand or {}).get("genero"), url_foto(2022, cand["sq"], "MA") if cand else None, url))
        lista = []
        for k, papel in por_nome.get(chave_nome(p["nome"]), []):
            v = mats[k]
            tipo, sigla = TIPOS[v["tp"]]
            s = _situacao(v, vetos)
            prop = regional.proposta(f"alema:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], v["sit"],
                                     f"{SITE}/sapl/protocol/legislative-matter/view/{k}", papel=papel, status=s["status"],
                                     data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        listas.append(lista)
        fonte_p = fonte(VEICULO, f"Matérias legislativas de {p['nome']} (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")
        extras[pid] = {"propostas": regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_p),
                       "links": {"oficial": url, "email": None, "redes": []}, "fontes": [fonte_l, fonte_p]}
    log(f"  MA: situações {resumo_status(listas)}")
    notas = [("As fotos do sistema da Alema são links que expiram em uma hora; por isso aparecem as fotos do TSE.",
              "The photos in the Alema system are links that expire after one hour, so the photos from the TSE are shown."),
             NOTA_GASTOS,
             ("As votações não entram: a Alema publica cada votação nominal como um documento PDF na página \"Votações "
              "Nominais\" do seu Portal da Transparência; o AlemaLegis, que tem lugar para os votos, não traz votações desde "
              "2023.",
              "Votes are not included: the Alema publishes each roll-call vote as a PDF document on the roll-call votes "
              "page of its transparency portal; AlemaLegis, which has room for votes, has none since 2023.")]
    try:
        g = gastos(membros)
    except SemTempo:
        g = None
        log("  MA: gastos: o tempo da rodada acabou; a leitura continua na próxima")
    except Exception as e:  # o portal da transparência fora do ar não derruba a Casa: ficam os gastos de antes
        g = None
        log(f"  MA: ATENÇÃO: gastos não atualizados ({type(e).__name__}: {e}); ficam os de antes")
    com_gastos = VG.aplicar(extras, g, "gastos")
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": com_gastos}
    r = gravar("MA", {"casa": "Assembleia Legislativa do Estado do Maranhão", "casa_en": "Legislative Assembly of the State of Maranhão",
                      "sigla": "Alema", "site": "https://www.al.ma.leg.br"}, membros, extras, cobertura, fonte_l, notas)
    try:
        _governo(rede, mats, vetos)
    except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
        log(f"  MA: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
    log(f"  MA: {rede.pedidos} pedidos ao site oficial")
    return r


def _governo(rede: Rede, mats: dict, vetos: dict) -> dict:
    """dados/pessoas/gov-MA.json: matérias do "PODER EXECUTIVO" (projetos e medidas provisórias), as leis do período no
    AlemaLegis e os vetos (matérias Veto Total e Veto Parcial)."""
    per = gv.periodo("MA")
    ini = per["inicio"]
    lista = []
    for k, v in mats.items():
        if v["tp"] not in TIPOS_GOV or (v["d"] or "") < ini or not gv.autor_do_executivo(v["au"], per):
            continue
        tipo, sigla = TIPOS_GOV[v["tp"]]
        s = _situacao(v, vetos)
        prop = regional.proposta(f"alema:{k}", f"{sigla} {v['n']}/{v['a']}", tipo, v["d"], v["e"], v["sit"],
                                 f"{SITE}/sapl/protocol/legislative-matter/view/{k}", papel="autor", status=s["status"],
                                 data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
        lista.append(com_status_en(prop, s["en"]))
    fonte_prop = fonte(VEICULO, "Matérias de autoria do Poder Executivo (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")
    # vetos do governador recebidos no período
    vts = [v for v in mats.values() if v["tp"] in VETOS and (v["d"] or "") >= ini]
    totais = sum(1 for v in vts if VETOS[v["tp"]])
    # leis do período (o AlemaLegis não diz quem assinou cada uma: entram também as promulgadas pelo presidente da Assembleia)
    leis = 0
    for ano in range(int(ini[:4]), int(hoje()[:4]) + 1):
        pag = 0
        while True:
            d = rede.json(f"{API}/legal-norm/filter?page={pag}&size=100&year={ano}", f"gov-normas-{ano}-{pag}.json", 20)
            for x in d.get("content") or []:
                if ((x.get("legalNormType") or {}).get("description") in ("Lei", "Lei Ordinária", "Lei Complementar")
                        and (x.get("date") or "")[:10] >= ini):
                    leis += 1
            pag += 1
            if pag >= int(d.get("totalPages") or 0):
                break
    nota = (f"Leis: as {leis} leis ordinárias e complementares com data a partir de {gv.data_pt(ini)} registradas no AlemaLegis "
            f"(o sistema legislativo da Alema). O sistema não diz quem assinou cada lei, então entram também as promulgadas pelo "
            f"presidente da Assembleia (quando o governador não sanciona no prazo ou quando o veto é derrubado). Vetos: as matérias "
            f"\"Veto Total\" e \"Veto Parcial\" recebidas pela Assembleia desde {gv.data_pt(ini)}.")
    nota_en = (f"Laws: the {leis} ordinary and complementary laws dated from {gv.data_en(ini)} on in AlemaLegis (the Alema "
               f"legislative system). The system does not say who signed each law, so this also includes laws promulgated by the "
               f"Assembly's president (when the governor does not sign in time or a veto is overridden). Vetoes: the \"Veto Total\" "
               f"and \"Veto Parcial\" items received by the Assembly since {gv.data_en(ini)}.")
    fontes = [fonte(VEICULO, "Normas jurídicas (AlemaLegis)", f"{SITE}/sapl/protocol/legal-norm/research"),
              fonte(VEICULO, "Matérias Veto Total e Veto Parcial (AlemaLegis)", f"{SITE}/sapl/protocol/legislative-matter/research")]
    ex = gv.bloco_executivo(per, leis, len(vts), fontes, nota, nota_en, totais, len(vts) - totais)
    esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature",
                            "projetos de lei, de lei complementar e de emenda à Constituição do estado e medidas provisórias",
                            "bills, complementary bills, amendments to the state Constitution and provisional measures")
    nota_prop = ("Medidas provisórias (MP) valem como lei assim que o governador as publica, mas perdem a validade se a "
                 "Assembleia não as aprovar no prazo da Constituição do estado.",
                 "Provisional measures (MP) take effect as law as soon as the governor publishes them, but they expire if the "
                 "state legislature does not approve them within the deadline set by the state Constitution.")
    return gv.gravar_gov("MA", per, lista, esc, esc_en, fonte_prop, ex, fontes, nota_prop)


def _situacao(v: dict, vetos: dict) -> dict:
    for l in v.get("leis") or []:
        nome = _norma(l.get("description"))
        if nome and l.get("number"):
            nl = nome_lei(nome, l["number"], l.get("year"))
            return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None, "data": v.get("da"),
                    "lei": {"nome": nl, "url": None}}
    vt = vetos.get((v["tp"], str(v["n"]), str(v["a"])))
    if vt and vt["total"]:
        return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor",
                "data": vt["d"], "lei": None}
    t = sem_acento((v.get("sit") or "").lower())
    if not t:
        return {"status": "outra", "txt": None, "en": None, "data": v.get("da"), "lei": None}
    for exp, st, pt, en in REGRAS:
        if re.search(exp, t):
            return {"status": st, "txt": pt, "en": en, "data": v.get("da"), "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": v.get("da"), "lei": None}


# conferidos à mão (nome na Alema -> candidato do TSE de 2022): "Ariston" é ARISTON GONÇALO (Ariston Ribeiro de Sousa,
# eleito pelo PSB); "Dra Vivianne" é DRA VIVIANNE (Vivianne Martins Coelho e Silva, eleita pelo PDT; a Alema escreve o nome
# civil como "Dra. Viviane").
TSE_MANUAL: dict[str, str] = {"107": "100001607069", "129": "100001599580"}


# ---------------------------------------------------------------- gastos: CEAP (Portal da Transparência da Alema)
# A Alema não publica a CEAP em arquivo aberto (a página "API de Dados Abertos" do portal diz que o requisito de dados
# abertos "não é atendido") e os botões PDF/XLS/XML/CSV da página de cada parlamentar são postbacks do formulário (não há
# arquivo para baixar por endereço). O caminho é o da própria página, como no navegador:
# 1. lista da competência: GET lista-parlamentar.html (abre a sessão), POST do formulário com in_competencia_input=MM/AAAA
#    (o botão "Pesquisar") -> tabela "tabela" com 10 nomes por página; as páginas seguintes vêm por AJAX (paginação do
#    PrimeFaces, 10 por página, como na tela). Mês sem nada publicado: sem tabela ("Nenhum resultado encontrado.");
# 2. código de cada parlamentar: o clique no nome (AJAX) responde com o endereço da página dele no mês
#    (lista-sintetico.html?competencia=AAAA-MM-01&parlamentar=<código>). O código é o mesmo em todos os meses (conferido
#    na carga de 26/10/2026: nas 1.729 páginas de 02/2023 a 06/2026, o nome no título da página é o da lista), então só
#    os nomes novos são clicados;
# 3. página do parlamentar no mês (GET, também abre sem sessão): tabela Código | Descrição | Valor e a frase "O valor
#    ressarcido respeitando os limites regulamentares é R$ X - Total gasto no mês: R$ Y" (Y = a soma das linhas).
# Os ids j_idt... do formulário não são fixos no código: saem da própria página a cada sessão. robots.txt de
# sistemas.al.ma.leg.br: responde 403 (RFC 9309: sem regras); sem CAPTCHA nem login. 1,5 s entre pedidos (vez/feito).
TRANSP = "https://sistemas.al.ma.leg.br/transparencia"
NOME_GASTOS = ("Cota para o Exercício da Atividade Parlamentar (CEAP): valor ressarcido pela Alema (os tipos mostram o total "
               "gasto, que pode passar dos limites do mês)",
               "Office allowance (CEAP): amount reimbursed by the Alema "
               "(the types show the total spent, which can go over the month's limits)")
GASTOS_S = 150            # limite diário desta leitura (s); a primeira carga usa o resto da rodada (_carga.py)
ABERTOS = 6               # o mês corrente e os 5 anteriores: a Alema publica com alguns meses de atraso (em 26/10/2026, o
                          # último mês com dados era 06/2026, ainda incompleto), então a lista e as páginas deles são relidas
LISTA_H = 20              # lista de um mês aberto: relida a cada 20 h
DETALHE_DIAS, DETALHES_POR_RODADA = 10, 25  # página de um parlamentar num mês aberto: relida a cada 10 dias, até 25 por rodada
ERROS_SEGUIDOS = 6        # o portal parou de responder: o resto fica para a próxima rodada
FALHAS_MAX = 3            # lista ou página que falha em 3 rodadas (com o portal no ar): fica registrada como erro e avisada
# conferido à mão: {nome na lista da CEAP: id da pessoa ou "-"}, quando os nomes não bastam. "Andreia M. Rezende" é a
# deputada Andreia Martins Rezende (MDB; a regra comum não liga a abreviação "M.").
CEAP_MANUAL: dict[str, str] = {"Andreia M. Rezende": "dest-MA-100001607086"}
NOTA_GASTOS = (
    "Gastos: a Cota para o Exercício da Atividade Parlamentar (CEAP), pelas páginas de cada deputado no Portal da "
    "Transparência da Alema, desde fevereiro de 2023. O total é o \"valor ressarcido\" de cada mês (o que a Alema pagou, "
    "respeitando os limites); os tipos são as despesas da página, que somam o \"total gasto no mês\" e podem passar do "
    "valor ressarcido. Cada mês aparece no portal da Alema alguns meses depois.",
    "Spending: the office allowance (CEAP), from each deputy's pages on "
    "the Alema transparency portal, since February 2023. The total is each month's \"valor ressarcido\" (the amount the "
    "Alema paid, within the limits); the types are the expenses on the page, which add up to the \"total gasto no mês\" "
    "(total spent in the month) and can be more than the amount reimbursed. Each month shows up on the Alema portal a few "
    "months later.")
_AJAX = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest"}


def _meses(ini: str, ate: str) -> list[str]:
    """['2023-02', '2023-03', ..., ate] (meses "AAAA-MM")."""
    a, m = int(ini[:4]), int(ini[5:7])
    out = []
    while f"{a}-{m:02d}" <= ate:
        out.append(f"{a}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _menos_meses(mes: str, n: int) -> str:
    a, m = int(mes[:4]), int(mes[5:7]) - n
    while m < 1:
        a, m = a - 1, m + 12
    return f"{a}-{m:02d}"


def _agora() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _idade_h(quando: str | None) -> float:
    if not quando:
        return float("inf")
    t = dt.datetime.strptime(quando, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def _url_ceap(mes: str, cod: str, janela: str | None = None) -> str:
    u = f"{TRANSP}/lista-sintetico.html?competencia={mes}-01&parlamentar={cod}"
    return f"{u}&dswid={janela}" if janela else u


class _Portal:
    """Uma sessão no Portal da Transparência da Alema (JSF/PrimeFaces, com cookie de sessão), um pedido por vez, com o
    robots.txt e o intervalo entre pedidos de _ne_comum (vez/feito)."""

    def __init__(self, pausa: float = 1.5, timeout: int = 90):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.pausa, self.timeout = pausa, timeout
        self.pedidos = 0
        self.campos: dict | None = None
        self.acao = self.botao = self.janela = self.comp = None
        self.form = ""

    def _abrir(self, url: str, dados: dict | None = None, ajax: bool = False) -> str:
        h = {"User-Agent": UA}
        if dados is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        if ajax:
            h.update(_AJAX)
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        erro = None
        for _ in range(2):
            iv = vez(url, self.pausa)
            try:
                with self.op.open(urllib.request.Request(url, data=corpo, headers=h), timeout=self.timeout) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                erro = e
                if e.code < 500:
                    break
            except Exception as e:  # rede instável: mais uma tentativa
                erro = e
            finally:
                feito(url, iv)
                self.pedidos += 1
        raise RuntimeError(f"{url}: {erro}")

    def _ler_form(self, h: str) -> None:
        f = next((m.group(0) for m in re.finditer(r"<form\b[^>]*>.*?</form>", h, re.S) if "in_competencia_input" in m.group(0)), None)
        b = re.search(r'<button[^>]*name="([^"]+)"[^>]*type="submit"[^>]*>\s*<span[^>]*>\s*Pesquisar', f or "")
        if not f or not b:
            raise RuntimeError("Alema CEAP: a página da lista mudou (sem o formulário de competência)")
        self.form, self.botao = f, b.group(1)
        self.acao = urllib.parse.urljoin(TRANSP + "/", html.unescape(re.search(r'action="([^"]+)"', f).group(1)))
        self.campos = {}
        for inp in re.findall(r"<input\b[^>]*>", f):
            n, v = re.search(r'name="([^"]+)"', inp), re.search(r'value="([^"]*)"', inp)
            if n and 'type="hidden"' in inp:
                self.campos[n.group(1)] = html.unescape(v.group(1)) if v else ""
        self.janela = self.campos.get("javax.faces.ClientWindow")

    def _dados(self, extra: dict) -> dict:
        d = dict(self.campos)
        d["in_competencia_input"] = self.comp
        d.update(extra)
        return d

    @staticmethod
    def _nomes(x: str) -> list[tuple[str, str]]:
        return [(src, re.sub(r"\s+", " ", html.unescape(n)).strip())
                for src, n in re.findall(r'<a id="(tabela:\d+:[^"]+)"[^>]*>([^<]*)</a>', x)]

    def competencia(self, mes: str, codigos: dict[str, str]) -> list[str]:
        """Os nomes da lista da competência `mes` ("AAAA-MM"), página por página. Os nomes ainda sem código ganham o código
        (clique no nome) em `codigos`."""
        if self.campos is None:
            self._ler_form(self._abrir(f"{TRANSP}/lista-parlamentar.html"))
        self.comp = f"{mes[5:7]}/{mes[:4]}"
        h = self._abrir(self.acao, self._dados({self.botao: ""}))
        self._ler_form(h)
        if 'id="tabela"' not in self.form:
            if "Nenhum resultado encontrado" in h:
                return []  # mês ainda sem nada publicado
            raise RuntimeError(f"Alema CEAP: a lista de {self.comp} veio sem a tabela de parlamentares")
        total = int((re.search(r"rowCount:(\d+)", self.form) or [0, 0])[1])
        por_pag = int((re.search(r"\brows:(\d+)", self.form) or [0, 10])[1])
        # a tabela volta na página em que estava na competência anterior (a mesma sessão): a 1ª página é pedida de novo
        pagina = self._nomes(self.form)
        nomes, first, linhas_vistas = [], 0, set()
        while True:
            if not pagina or not pagina[0][0].startswith(f"tabela:{first}:"):
                pagina = self._pagina(first, por_pag)
            if not pagina or not pagina[0][0].startswith(f"tabela:{first}:"):
                raise RuntimeError(f"Alema CEAP: a página {first // por_pag + 1} da lista de {self.comp} não veio")
            for src, nome in pagina:
                linhas_vistas.add(int(src.split(":")[1]))
                nomes.append(nome)
                if nome not in codigos:
                    cod = self.codigo(src, mes)
                    if cod:
                        codigos[nome] = cod
            first += por_pag
            if first >= total:
                break
            pagina = []
        if len(nomes) != total or linhas_vistas != set(range(total)):
            raise RuntimeError(f"Alema CEAP: {len(nomes)} nomes na lista de {self.comp}, que diz {total}")
        return nomes

    def _pagina(self, first: int, por_pag: int) -> list[tuple[str, str]]:
        """Uma página da tabela (paginação do PrimeFaces por AJAX, como na tela)."""
        x = self._abrir(self.acao, self._dados({
            "javax.faces.partial.ajax": "true", "javax.faces.source": "tabela", "javax.faces.partial.execute": "tabela",
            "javax.faces.partial.render": "tabela", "javax.faces.behavior.event": "page", "javax.faces.partial.event": "page",
            "tabela_pagination": "true", "tabela_first": str(first), "tabela_rows": str(por_pag),
            "tabela_skipChildren": "true", "tabela_encodeFeature": "true"}), ajax=True)
        vs = re.search(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[(.*?)\]\]>', x)
        if vs:
            self.campos["javax.faces.ViewState"] = vs.group(1)
        return self._nomes(x)

    def codigo(self, src: str, mes: str) -> str | None:
        x = self._abrir(self.acao, self._dados({"javax.faces.partial.ajax": "true", "javax.faces.source": src,
                                                "javax.faces.partial.execute": "@all", src: src}), ajax=True)
        m = re.search(r'<redirect url="([^"]+)"', x)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(m.group(1))).query) if m else {}
        if (q.get("competencia") or [""])[0][:7] != mes:
            return None
        return (q.get("parlamentar") or [None])[0]

    def detalhe(self, mes: str, cod: str) -> str:
        if self.campos is None:
            self._ler_form(self._abrir(f"{TRANSP}/lista-parlamentar.html"))
        return self._abrir(_url_ceap(mes, cod, self.janela))  # com a janela da sessão: sem redirecionamento


def _detalhe(h: str) -> dict:
    """Página de um parlamentar num mês -> {"nome", "mes", "l": [[código, descrição, valor]], "r" (valor ressarcido),
    "t" (total gasto no mês)}."""
    t = re.search(r'<h2 class="titulo-pagina">(.*?)</h2>', h, re.S)
    if not t or "CEAP" not in t.group(1):
        raise RuntimeError("Alema CEAP: a página do parlamentar mudou (sem o título da CEAP)")
    nome = re.sub(r"\s+", " ", html.unescape(t.group(1))).strip().split(" - CEAP - ", 1)[-1].strip()
    comp = re.search(r"Compet\w+:\s*(\d{4}-\d{2})", h)
    linhas = []
    for tr in re.findall(r'<tr data-ri="\d+"[^>]*>(.*?)</tr>', h, re.S):
        cel = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cel) >= 3:
            linhas.append([cel[0], cel[1], VG.valor_br(cel[2])])
    pe = re.search(r"<tfoot[^>]*>(.*?)</tfoot>", h, re.S)
    txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pe.group(1)))) if pe else ""
    r = re.search(r"ressarcido.*?R\$\s*([\d.,]+)", txt)
    g = re.search(r"Total gasto no m\w+:\s*R\$\s*([\d.,]+)", txt)
    if linhas and not g:
        raise RuntimeError("Alema CEAP: a página do parlamentar veio sem o total gasto no mês")
    return {"nome": nome, "mes": comp.group(1) if comp else None, "l": linhas,
            "r": VG.valor_br(r.group(1)) if r else None, "t": VG.valor_br(g.group(1)) if g else None}


def _ler_ceap(portal: _Portal, rede: Rede, est: dict, limite: float) -> None:
    """Lê o que falta (e o que vence) nesta rodada, até `limite` segundos; o progresso fica em `est`."""
    t0, erros, certos = time.time(), [0], [0]
    falhas: dict[str, int] = est.setdefault("falhas", {})
    falhou: set[str] = set()
    atual = hoje()[:7]
    abertos = _menos_meses(atual, ABERTOS - 1)

    def tem_tempo() -> bool:
        return time.time() - t0 < limite and not _carga.acabou() and erros[0] < ERROS_SEGUIDOS

    def deu_certo(chave: str) -> None:
        erros[0] = 0
        certos[0] += 1
        falhas.pop(chave, None)

    def deu_errado(chave: str, msg: str) -> None:
        erros[0] += 1
        falhou.add(chave)
        log(f"  MA CEAP: {msg}")

    try:
        # 1. lista de cada competência (a dos meses abertos é relida a cada LISTA_H horas)
        for mes in _meses(INICIO[:7], atual):
            m = est["meses"].get(mes)
            if m and (mes < abertos or _idade_h(m.get("lido")) < LISTA_H):
                continue
            if not tem_tempo():
                return
            chave = f"lista/{mes}"
            try:
                nomes = portal.competencia(mes, est["codigos"])
            except SemTempo:
                raise
            except Exception as e:
                portal.campos = None  # a próxima competência abre uma sessão nova
                deu_errado(chave, f"lista de {mes}: {type(e).__name__}: {e}")
                if m is None and falhas.get(chave, 0) >= FALHAS_MAX:  # desiste (avisado no log); a carga não trava
                    est["meses"][mes] = {"lido": _agora(), "nomes": [], "erro": True}
                continue
            sem_codigo = [n for n in nomes if n not in est["codigos"]]
            if not sem_codigo:
                deu_certo(chave)
                est["meses"][mes] = {"lido": _agora(), "nomes": nomes}
            else:
                deu_errado(chave, f"lista de {mes}: sem o código de {sem_codigo}")
                if m is None and falhas.get(chave, 0) >= FALHAS_MAX:
                    est["meses"][mes] = {"lido": _agora(), "nomes": [n for n in nomes if n in est["codigos"]],
                                         "erro": True}
            rede.guardar(est)
        # 2. página de cada parlamentar em cada mês (as que faltam; das abertas, as mais antigas)
        cod = est["codigos"]
        nos_meses = {f"{mes}/{cod[n]}" for mes, m in est["meses"].items() if mes >= INICIO[:7] for n in m["nomes"] if n in cod}
        faltam = sorted(k for k in nos_meses if k not in est["det"])
        vencidas = sorted((d["lido"], k) for k, d in est["det"].items()
                          if k in nos_meses and k[:7] >= abertos and _idade_h(d["lido"]) > DETALHE_DIAS * 24)
        for n, k in enumerate(faltam + [k for _, k in vencidas[:DETALHES_POR_RODADA]]):
            if not tem_tempo():
                return
            mes, c = k.split("/")
            if k not in est["det"] and falhas.get(k, 0) >= FALHAS_MAX:  # desiste (avisado no log); a carga não trava
                est["det"][k] = {"nome": None, "mes": mes, "l": [], "r": None, "t": None, "erro": True, "lido": _agora()}
                continue
            try:
                d = _detalhe(portal.detalhe(mes, c))
            except SemTempo:
                raise
            except Exception as e:
                deu_errado(k, f"{_url_ceap(mes, c)}: {type(e).__name__}: {e}")
                continue
            if d["mes"] != mes:
                deu_errado(k, f"{_url_ceap(mes, c)}: a página mostrou a competência {d['mes']}")
                continue
            deu_certo(k)
            d["lido"] = _agora()
            est["det"][k] = d
            if n % 25 == 24:
                rede.guardar(est)
    finally:
        if certos[0]:  # o portal respondeu nesta rodada: o que falhou conta como falha daquele endereço
            for k in falhou:
                falhas[k] = falhas.get(k, 0) + 1


def _pendencias_ceap(est: dict) -> int:
    n = sum(1 for mes in _meses(INICIO[:7], hoje()[:7]) if mes not in est["meses"])
    for mes, m in est["meses"].items():
        if mes >= INICIO[:7]:
            n += sum(1 for nome in m["nomes"] if nome in est["codigos"] and f"{mes}/{est['codigos'][nome]}" not in est["det"])
    return n


def gastos(membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} da CEAP desde o começo da legislatura (INICIO), ou None enquanto a primeira carga
    (todas as competências desde fevereiro de 2023, ~1.900 pedidos) não termina: os perfis ficam com o bloco de antes e a
    leitura continua na rodada seguinte, de onde parou (.cache/alema-gastos/estado.json)."""
    rede = Rede("alema-gastos", pausa=1.5)  # só a pasta do estado; os pedidos vão pela sessão do _Portal
    est = rede.estado("estado.json", {}) or {}
    if est.get("inicio") != INICIO:  # legislatura nova: a carga recomeça (os códigos dos parlamentares continuam)
        est = {"inicio": INICIO, "completo": False, "codigos": est.get("codigos") or {}, "meses": {}, "det": {}}
    primeira = not est.get("completo")
    portal, t0 = _Portal(pausa=1.5), time.time()
    try:
        _ler_ceap(portal, rede, est, _carga.limite_diario(GASTOS_S, primeira))
    except SemTempo:
        log("  MA CEAP: o tempo da rodada acabou; o resto fica para a próxima")
    finally:
        falta = _pendencias_ceap(est)
        if primeira and not falta:
            est["completo"] = True
        rede.guardar(est)
    log(f"  MA CEAP: {portal.pedidos} pedidos a sistemas.al.ma.leg.br em {time.time() - t0:.0f} s; {len(est['det'])} páginas "
        f"de parlamentar no cache; faltam {falta}")
    if not est.get("completo"):
        log("  MA CEAP: primeira carga em andamento; os perfis ficam com os gastos de antes")
        return None
    return _blocos_ceap(est, membros)


def _blocos_ceap(est: dict, membros: list[dict]) -> dict[str, dict]:
    nomes_cod: dict[str, list[str]] = {}
    for nome, c in est["codigos"].items():
        nomes_cod.setdefault(c, []).append(nome)
    outro_nome = sorted({f"{k}: {d['nome']}" for k, d in est["det"].items()
                         if d.get("nome") and d["nome"] not in nomes_cod.get(k.split("/")[1], [])})
    if outro_nome:  # o código veio do clique no nome da lista; a página do parlamentar tem de mostrar o mesmo nome
        log(f"  MA CEAP: ATENÇÃO: páginas com nome diferente do da lista (conferir): {outro_nome[:10]}")
    for k, d in sorted(est["det"].items(), reverse=True):
        ns = nomes_cod.setdefault(k.split("/")[1], [])
        if d.get("nome") and d["nome"] not in ns:
            ns.append(d["nome"])
    nm = VG.Nomes(membros, CEAP_MANUAL)
    quem: dict[str, str] = {}
    sem, conflito = [], []
    for c, ns in nomes_cod.items():
        achados = {nm.quem(n) for n in ns} - {None}
        if len(achados) == 1:
            quem[c] = achados.pop()
        elif achados:
            conflito.append(f"{c} {ns}")
        elif not any(chave_nome(n) in nm.manual for n in ns):
            sem.append(ns[0])
    if sem:
        log(f"  MA CEAP: parlamentares sem pessoa na lista de hoje (quem saiu): {sorted(sem)}")
    if conflito:
        log(f"  MA CEAP: ATENÇÃO: nomes que batem com mais de uma pessoa (conferir à mão; ficam de fora): {conflito}")
    sem_gasto = [m["nome"] for m in membros if m["id"] not in set(quem.values())]
    if sem_gasto:
        log(f"  MA CEAP: pessoas da lista de hoje sem página da CEAP: {sem_gasto}")
    nos_meses = {f"{mes}/{est['codigos'][n]}" for mes, m in est["meses"].items() if mes >= INICIO[:7] for n in m["nomes"]
                 if n in est["codigos"]}
    linhas: dict[str, list] = {}
    pagos: dict[str, dict[str, float]] = {}
    ultimo: dict[str, str] = {}
    difere, sem_ressarcido = [], []
    erros = [f"lista de {mes}" for mes, m in est["meses"].items() if m.get("erro") and mes >= INICIO[:7]]
    for k, d in est["det"].items():
        mes, c = k.split("/")
        if k not in nos_meses or c not in quem:
            continue
        pid = quem[c]
        if d.get("erro"):
            erros.append(f"{k}: a página não abriu em {FALHAS_MAX} rodadas")
            continue
        soma = round(sum(v for _, _, v in d["l"]), 2)
        if d["l"] and abs(soma - (d["t"] or 0)) > 0.005:
            difere.append(f"{k}: soma {soma:.2f}, total gasto {d['t']}")
        for _, desc, v in d["l"]:
            linhas.setdefault(pid, []).append((mes, desc, v))
        if d["l"] and d["r"] is None:
            sem_ressarcido.append(k)
        pg = pagos.setdefault(pid, {})
        pg[mes] = round(pg.get(mes, 0.0) + (d["r"] if d["r"] is not None else soma), 2)
        if d["l"] and k > ultimo.get(pid, ""):
            ultimo[pid] = k
    if erros:
        log(f"  MA CEAP: ATENÇÃO: o que não deu para ler (fica de fora): {erros[:10]}{'...' if len(erros) > 10 else ''}")
    if difere:
        log(f"  MA CEAP: ATENÇÃO: páginas em que a soma das linhas não bate com o total gasto no mês: {difere[:10]}")
    if sem_ressarcido:
        log(f"  MA CEAP: páginas sem o valor ressarcido (vale a soma das linhas): {sem_ressarcido[:10]}")
    nome_de = {m["id"]: m["nome"] for m in membros}
    out = {}
    for pid, ls in linhas.items():
        mes, c = ultimo[pid].split("/")
        f = fonte(VEICULO, f"CEAP de {nome_de.get(pid, pid)} em {mes[5:7]}/{mes[:4]} (Portal da Transparência da Alema)",
                  _url_ceap(mes, c))
        b = VG.bloco_gastos(_tipos_unicos(ls), f, INICIO, NOME_GASTOS)
        if b:  # o total (do ano e do mandato) é o que a Alema ressarciu; os tipos são o que foi gasto
            ano = str(b["ano"])
            b["total"] = round(sum(v for m, v in pagos[pid].items() if m.startswith(ano)), 2)
            b["mandatoTotal"] = round(sum(pagos[pid].values()), 2)
            out[pid] = b
    log(f"  MA CEAP: gastos de {len(out)} de {len(membros)} pessoas da lista de hoje; ressarcido no mandato: "
        f"{sum(b['mandatoTotal'] for b in out.values()):.2f}; total gasto: {sum(v for ls in linhas.values() for _, _, v in ls):.2f}")
    return out


def _tipos_unicos(linhas: list[tuple[str, str, float]]) -> list[tuple[str, str, float]]:
    """O mesmo tipo escrito de jeitos diferentes (caixa, acento, espaços) fica com o nome do mês mais recente."""
    nome: dict[str, tuple[str, str]] = {}
    for mes, t, _ in linhas:
        k = re.sub(r"[^a-z0-9]", "", sem_acento(t).lower())
        if mes >= nome.get(k, ("", ""))[0]:
            nome[k] = (mes, t)
    return [(mes, nome[re.sub(r"[^a-z0-9]", "", sem_acento(t).lower())][1], v) for mes, t, v in linhas]
