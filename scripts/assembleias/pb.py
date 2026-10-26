"""Assembleia Legislativa da Paraíba (ALPB): SAPL 3 (https://sapl.al.pb.leg.br/api/).

Lista: deputados com "ativo" na legislatura atual do SAPL (é a mesma lista da página inicial da ALPB, com 36 pessoas,
inclusive os suplentes que assumiram). Propostas: projetos de lei ordinária (PLO), de lei complementar (PLC), de emenda
constitucional (PEC), de decreto legislativo (PDL) e de resolução (PRE) desde 1º/2/2023. Situação: a da última tramitação;
"virou lei" pela norma jurídica ligada ao projeto; "vetada por inteiro" pelas matérias do tipo Veto (ligadas ao projeto).
Gastos (gastos()): a Verba Indenizatória de Apoio Parlamentar (VIAP), pelas planilhas mensais de prestação de contas de cada
gabinete no Portal da Transparência da ALPB (https://www.al.pb.leg.br/transparencia/deputados/viap-v2; outro servidor, fora
do SAPL), desde fevereiro de 2023: o "Reembolso" de cada mês (o que a ALPB pagou) e as despesas por subitem.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import re
import time
import urllib.parse
import zipfile

import regional
from comum import fonte, hoje, log, sem_acento

from . import _carga
from . import _ne_gov as gv
from ._carga import SemTempo
from ._ne_comum import INICIO, Rede
from ._ne_sapl import SaplAssembleia
from ._votos_gastos import Nomes, bloco_gastos, mes_br, ods_linhas, valor_br, xlsx_linhas

# situação da última tramitação na ALPB (texto oficial sem acento, minúsculas) -> status do site. Conferido à mão numa
# amostra (ver as notas da frente ale-nordeste): na ALPB, "Aprovado" sozinho quase sempre é o parecer de uma comissão
# aprovado (quando o Plenário aprova, a tramitação seguinte, "Sanção e ou Veto", vem em um ou dois dias).
REGRAS = [
    (r"sancao e ou veto|redacao final e autografo|redacao final aprovad", "aprovada",
     "Aprovada; enviada ao governador para sanção ou veto", "Approved; sent to the governor to sign or veto"),
    (r"mantido o veto", "rejeitada", "Vetada pelo governador; o veto foi mantido", "Vetoed by the governor; the veto was upheld"),
    (r"retirado a pedido do autor", "retirada", None, None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"igual teor", "parada", "Saiu da pauta porque já existe outro projeto igual",
     "Taken off the agenda because an identical bill already exists"),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"arquivad", "arquivada", "Arquivada", None),
    (r"pela reprovacao", "andando", "Uma comissão deu parecer contra; falta a decisão final",
     "A committee recommended rejecting it; the final decision is pending"),
    (r"^aprovado$", "andando", "Aprovada numa etapa (comissão ou Plenário); faltam as outras etapas antes de ir ao governador",
     "Approved at one stage (committee or full Assembly); other stages remain before it goes to the governor"),
    (r"despachad|aguardando|incluir|constou|costou|indicacao de relator|recebido em plenario|protocolad|destacad|adiad|"
     r"retirado pauta|retirado de pauta|retirado por ausencia|aprovado a urgencia|materia regimental", "andando", None, None),
    (r".", "outra", None, None),
]


def _classificar(col, normas: list[dict]) -> list[bool | None]:
    """Quem assinou cada lei na Paraíba (True = o presidente da Assembleia promulgou; False = o governador sancionou).
    O SAPL da ALPB não tem esse campo, e o texto da lei só existe em PDF. Regra, conferida com o texto (PDF) de 28 leis de
    2026: (1) a tramitação do projeto anota onde a lei saiu; quando cita o Diário do Poder Legislativo ("DPL"), quem
    promulgou foi o presidente da Assembleia (sanção tácita ou veto derrubado); (2) as leis que vêm de medidas provisórias
    são, quase sempre, promulgadas pelo presidente da Assembleia (13 de 14 na conferência) e ficam de fora da conta das
    sancionadas; (3) as outras foram sancionadas pelo governador. As anotações com "DPL" do período vêm numa consulta só
    (filtro de texto e data da API de tramitações: uma ou duas páginas por rodada)."""
    ini = gv.periodo("PB")["inicio"]
    mats = (getattr(col, "est", None) or {}).get("materias") or {}
    mps = {int(k) for k, v in mats.items() if v["t"] == 15}  # medidas provisórias (só o governador as edita)
    marcadas = set()
    for t in col.todos(f"/api/materia/tramitacao/?texto__icontains=DPL&data_tramitacao__gte={ini}", "gov-dpl", 20):
        x = t.get("texto") or ""
        if re.search(r"\bDPL\b", x) and re.search(r"(?i)\blei\b.{0,30}n", x):
            marcadas.add(t.get("materia"))
    return [n.get("materia") in mps or n.get("materia") in marcadas for n in normas]


GOV = {
    "autores": [74],  # "Governador do Estado da Paraíba"
    "tipos": {1: "PL", 6: "PLP", 2: "PEC", 15: "MPV"},
    "tipos_lei": [2, 1],  # Lei Ordinária, Lei Complementar
    "classificar": _classificar,
    "criterio_leis": ("que não saíram no Diário do Poder Legislativo e não vêm de medidas provisórias (regra conferida com o "
                      "texto de 28 leis)", "that did not appear in the Legislative Gazette and do not come from provisional "
                      "measures (rule checked against the text of 28 laws)"),
    "tipos_txt": ("projetos de lei, de lei complementar e de emenda à Constituição do estado e medidas provisórias",
                  "bills, complementary bills, amendments to the state Constitution and provisional measures"),
    "nota_prop": ("Medidas provisórias (MP) valem como lei assim que o governador as publica, mas perdem a validade se a "
                  "Assembleia não as aprovar no prazo da Constituição do estado.",
                  "Provisional measures (MP) take effect as law as soon as the governor publishes them, but they expire if "
                  "the state legislature does not approve them within the deadline set by the state Constitution."),
}


def coletar() -> dict:
    return SaplAssembleia(
        uf="PB", base="https://sapl.al.pb.leg.br", casa="Assembleia Legislativa do Estado da Paraíba",
        casa_en="Legislative Assembly of the State of Paraíba", sigla="ALPB", site="https://www.al.pb.leg.br",
        veiculo="Assembleia Legislativa da Paraíba (ALPB)", prefixo="alpb", pasta="alpb",
        tipos={1: "PL", 6: "PLP", 2: "PEC", 7: "PDL", 3: "PRC"}, tipos_veto={13: None}, regras=REGRAS, gov=GOV,
        gastos=gastos, notas=[NOTA_GASTOS], votacoes=True,
    ).coletar()


# ---------------------------------------------------------------- gastos: VIAP (Portal da Transparência da ALPB)
# Fluxo (só GET, páginas abertas): lista do mês (?tipo_viap=deputados&ano_viap=AAAA&mes_viap=M: o campo "deputado" traz
# os gabinetes com prestação de contas naquele mês, cada um com um código) -> página do gabinete no mês (&deputado=<código>:
# o link da planilha, aberta pelo visualizador do Office) -> a planilha (.ods até 09/2025, .xlsx desde 10/2025), com uma
# linha por despesa (ITEM, SUB_ITEM, fornecedor, documento, Valor) e as linhas de conta ("Total de Despesas",
# "Reembolso"; nas .ods também "Saldo Anterior", "Crédito" e "Saldo P/Mês"). O robots.txt de www.al.pb.leg.br só fecha
# /wp-admin/ (e barra robôs por nome; o nosso não está na lista) e não pede intervalo: 1,5 s entre pedidos.
VIAP = "https://www.al.pb.leg.br/transparencia/deputados/viap-v2"
VEICULO = "Assembleia Legislativa da Paraíba (ALPB)"
NOME_GASTOS = ("Verba Indenizatória de Apoio Parlamentar (VIAP): valor reembolsado pela ALPB (os tipos mostram as despesas "
               "declaradas, que podem passar do crédito do mês)",
               "Expense allowance (\"Verba Indenizatória de Apoio Parlamentar\", VIAP): amount reimbursed by the ALPB (the "
               "types show the declared expenses, which can go over the month's credit)")
GASTOS_S = 150            # limite diário desta leitura (s); a primeira carga usa o resto da rodada (_carga.py)
ABERTOS = 4               # o mês corrente e os 3 anteriores: a lista e as páginas deles ainda são conferidas de novo
LISTA_H = 20              # lista de um mês aberto: relida a cada 20 h
PAGINA_DIAS, PAGINAS_POR_RODADA = 10, 20  # página de um gabinete num mês aberto: relida a cada 10 dias, até 20 por rodada
ERROS_SEGUIDOS = 6        # o site parou de responder: o resto fica para a próxima rodada
FALHAS_MAX = 3            # endereço que falha em 3 rodadas (com o site no ar): fica registrado como erro e avisado no log
# conferido à mão: {código do gabinete na página da VIAP: id da pessoa ou "-"}, quando os nomes não bastam
VIAP_MANUAL: dict[str, str] = {}
NOTA_GASTOS = (
    "Gastos: a Verba Indenizatória de Apoio Parlamentar (VIAP), pelas planilhas mensais de prestação de contas de cada "
    "gabinete no Portal da Transparência da ALPB, desde fevereiro de 2023. O total é o \"Reembolso\" de cada mês (o que a "
    "ALPB pagou); os tipos são os subitens das despesas da planilha, que somam o \"Total de Despesas\". Quando as despesas "
    "de um mês passam do crédito disponível, o reembolso fica menor que a soma dos tipos.",
    "Spending: the expense allowance (\"Verba Indenizatória de Apoio Parlamentar\", VIAP), from each office's monthly "
    "spreadsheets on the ALPB transparency portal, since February 2023. The total is each month's \"Reembolso\" (what the "
    "ALPB paid); the types are the expense sub-items in the spreadsheet, which add up to the \"Total de Despesas\" (total "
    "expenses). When a month's expenses go over the available credit, the reimbursement is smaller than the sum of the "
    "types.")


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


def _url_viap(mes: str, dep: str | None = None) -> str:
    u = f"{VIAP}?tipo_viap=deputados&ano_viap={mes[:4]}&mes_viap={int(mes[5:7])}"
    return f"{u}&deputado={dep}" if dep else u


def _agora() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _idade_h(quando: str | None) -> float:
    if not quando:
        return float("inf")
    t = dt.datetime.strptime(quando, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def _gabinetes(h: str) -> dict[str, str]:
    """{código do gabinete: nome} do campo "deputado" da página (vazio quando o mês não foi publicado)."""
    i = h.find('name="deputado"')
    if i < 0 or 'name="mes_viap"' not in h:
        raise RuntimeError("PB VIAP: a página mudou (sem o campo de escolha do gabinete)")
    trecho = h[i:h.find("</select>", i)]
    return {v: re.sub(r"\s+", " ", html.unescape(t)).strip()
            for v, t in re.findall(r"<option[^>]*?value=['\"]?(\d+)['\"]?[^>]*>([^<]*)<", trecho) if v != "0"}


def _arquivos(h: str) -> list[str]:
    """Os links das planilhas na página de um gabinete num mês (o visualizador do Office recebe o arquivo em "src")."""
    i = h.find("Exibindo as Verbas")
    if i < 0:
        return []
    trecho = h[i:h.find("viap-update", i)]
    out = []
    for href in re.findall(r"href=['\"]([^'\"]+)['\"]", trecho):
        href = html.unescape(href)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        u = q["src"][0] if "src" in q else href
        if "/wp-content/uploads/" in u and u not in out:
            out.append(u)
    return out


def _chave(s) -> str:
    return re.sub(r"[^a-z]", "", sem_acento(str(s or "")).lower())


def _num(s) -> float:
    try:
        return float(str(s).strip())
    except ValueError:
        return valor_br(s)


def _planilha(b: bytes) -> dict:
    """Uma planilha de prestação de contas da VIAP (.ods ou .xlsx) -> {"mes", "nomes", "t": {subitem: valor},
    "total" ("Total de Despesas"), "reembolso", "soma" (das linhas de despesa)}."""
    z = zipfile.ZipFile(io.BytesIO(b))
    linhas = ods_linhas(b) if "content.xml" in z.namelist() else xlsx_linhas(b)
    cab = next((k for k, l in enumerate(linhas) if {"item", "subitem", "valor"} <= {_chave(c) for c in l}), None)
    if cab is None:
        raise RuntimeError("planilha sem o cabeçalho ITEM / SUB_ITEM / Valor")
    col = {}
    for k, c in enumerate(linhas[cab]):
        col.setdefault(_chave(c), k)
    ci, cs, cv, cc = col["item"], col["subitem"], col["valor"], col.get("competencia")
    cn = [col[k] for k in ("deputado", "nomecompleto", "nome") if k in col]
    out = {"mes": None, "nomes": [], "t": {}, "total": None, "reembolso": None, "soma": 0.0}
    for l in linhas[cab + 1:]:
        l = list(l) + [""] * (len(linhas[cab]) - len(l))
        rotulo = " ".join(_chave(c) for c in l[:cv])
        if "totaldedespesas" in rotulo:
            out["total"] = _num(l[cv])
            continue
        if "reembolso" in rotulo:
            out["reembolso"] = _num(l[cv])
            continue
        if cc is not None and not out["mes"]:
            out["mes"] = mes_br(l[cc])
        for k in cn:
            n = re.sub(r"\s+", " ", str(l[k] or "")).strip()
            if n and n not in out["nomes"]:
                out["nomes"].append(n)
        item, sub = str(l[ci] or "").strip(), str(l[cs] or "").strip()
        if not (item or sub) or str(l[cv]).strip() == "":
            continue  # "Saldo Anterior", "Crédito", "Saldo P/Mês" e linhas vazias
        tipo = re.sub(r"\s+", " ", sub or item).strip(" :")
        v = _num(l[cv])
        out["t"][tipo] = round(out["t"].get(tipo, 0.0) + v, 2)
        out["soma"] = round(out["soma"] + v, 2)
    if out["total"] is None:
        raise RuntimeError("planilha sem a linha \"Total de Despesas\"")
    return out


def _ler_viap(rede: Rede, est: dict, limite: float) -> None:
    """Lê o que falta (e o que vence) nesta rodada, até `limite` segundos; o progresso fica em `est`."""
    t0, erros, certos = time.time(), [0], [0]
    meses_est, pags, arqs = est["meses"], est["pags"], est["arqs"]
    falhas: dict[str, int] = est.setdefault("falhas", {})
    falhou: set[str] = set()
    atual = hoje()[:7]
    abertos = _menos_meses(atual, ABERTOS - 1)

    def tem_tempo() -> bool:
        return time.time() - t0 < limite and not _carga.acabou() and erros[0] < ERROS_SEGUIDOS

    def pedir(url: str, texto: bool = True, primeira_vez: bool = True):
        """O conteúdo; None se falhou nesta rodada; False se a primeira leitura já falhou em FALHAS_MAX rodadas com o site
        no ar (desiste, para a carga não travar; fica avisado no log)."""
        if primeira_vez and falhas.get(url, 0) >= FALHAS_MAX:
            return False
        try:
            b = rede.bruto(url, None)
        except SemTempo:
            raise
        except Exception as e:
            erros[0] += 1
            falhou.add(url)
            log(f"  PB VIAP: {url}: {type(e).__name__}: {e}")
            return None
        erros[0] = 0
        certos[0] += 1
        falhas.pop(url, None)
        return b.decode("utf-8", "replace") if texto else b

    try:
        # 1. lista de gabinetes de cada mês (a dos meses abertos é relida a cada LISTA_H horas)
        for mes in _meses(INICIO[:7], atual):
            m = meses_est.get(mes)
            if m and (mes < abertos or _idade_h(m.get("lido")) < LISTA_H):
                continue
            if not tem_tempo():
                return
            h = pedir(_url_viap(mes), primeira_vez=m is None)
            if h is False:
                meses_est[mes] = {"lido": _agora(), "deps": {}, "erro": True}
            elif h is not None:
                meses_est[mes] = {"lido": _agora(), "deps": _gabinetes(h)}
        # 2. página de cada gabinete em cada mês (as que faltam; das abertas, as mais antigas) e as planilhas novas
        faltam = [(mes, d) for mes in sorted(meses_est) if mes >= INICIO[:7] for d in meses_est[mes]["deps"]
                  if f"{mes}/{d}" not in pags]
        vencidas = sorted((pags[f"{mes}/{d}"]["lido"], mes, d) for mes in sorted(meses_est) if mes >= abertos
                          for d in meses_est[mes]["deps"] if f"{mes}/{d}" in pags
                          and _idade_h(pags[f"{mes}/{d}"]["lido"]) > PAGINA_DIAS * 24)
        tarefas = faltam + [(mes, d) for _, mes, d in vencidas[:PAGINAS_POR_RODADA]]
        for k, (mes, d) in enumerate(tarefas):
            if not tem_tempo():
                return
            chave = f"{mes}/{d}"
            h = pedir(_url_viap(mes, d), primeira_vez=chave not in pags)
            if h is False:
                pags[chave] = {"lido": _agora(), "arqs": [], "erro": True}
                continue
            if h is None:
                continue
            links = _arquivos(h)
            completa = True
            for u in links:
                if u in arqs:
                    continue
                if not tem_tempo():
                    return
                b = pedir(u, texto=False)
                if b is False:
                    arqs[u] = {"erro": f"a planilha não baixou em {FALHAS_MAX} rodadas"}
                    continue
                if b is None:  # a planilha não veio: a página fica para a próxima rodada
                    completa = False
                    break
                try:
                    arqs[u] = _planilha(b)
                except Exception as e:  # formato que não dá para ler: fica registrado (e avisado) para não pedir de novo
                    arqs[u] = {"erro": f"{type(e).__name__}: {e}"}
            if completa:
                pags[chave] = {"lido": _agora(), "arqs": links}
            if k % 25 == 24:
                rede.guardar(est)
    finally:
        if certos[0]:  # o site respondeu nesta rodada: o que falhou conta como falha daquele endereço
            for u in falhou:
                falhas[u] = falhas.get(u, 0) + 1


def _pendencias(est: dict) -> int:
    """Quantas páginas de gabinete (ou listas de meses) faltam ler."""
    meses_est, pags, arqs = est["meses"], est["pags"], est["arqs"]
    n = sum(1 for mes in _meses(INICIO[:7], hoje()[:7]) if mes not in meses_est)
    for mes, m in meses_est.items():
        if mes >= INICIO[:7]:
            for d in m["deps"]:
                p = pags.get(f"{mes}/{d}")
                n += 1 if p is None or any(u not in arqs for u in p["arqs"]) else 0
    return n


def gastos(col, membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} da VIAP desde o começo da legislatura (INICIO), ou None enquanto a primeira carga
    (todas as planilhas desde fevereiro de 2023, ~3.200 pedidos) não termina: os perfis ficam com o bloco de antes e a
    leitura continua na rodada seguinte, de onde parou (.cache/alpb-gastos/estado.json)."""
    rede = Rede("alpb-gastos", pausa=1.5)
    est = rede.estado("estado.json", {}) or {}
    if est.get("inicio") != INICIO:  # legislatura nova: a carga recomeça (as planilhas já lidas continuam no cache)
        est = {"inicio": INICIO, "completo": False, "meses": {}, "pags": {}, "arqs": est.get("arqs") or {}}
    primeira = not est.get("completo")
    t0 = time.time()
    try:
        _ler_viap(rede, est, _carga.limite_diario(GASTOS_S, primeira))
    except SemTempo:
        log("  PB VIAP: o tempo da rodada acabou; o resto fica para a próxima")
    finally:
        falta = _pendencias(est)
        if primeira and not falta:
            est["completo"] = True
        if est.get("completo"):  # planilhas trocadas pela ALPB (link novo na página): a antiga sai do cache
            usadas = {u for p in est["pags"].values() for u in p["arqs"]}
            est["arqs"] = {u: a for u, a in est["arqs"].items() if u in usadas}
        rede.guardar(est)
    log(f"  PB VIAP: {rede.pedidos} pedidos a www.al.pb.leg.br em {time.time() - t0:.0f} s; "
        f"{len(est['pags'])} páginas de gabinete e {len(est['arqs'])} planilhas no cache; faltam {falta}")
    if not est.get("completo"):
        log("  PB VIAP: primeira carga em andamento; os perfis ficam com os gastos de antes")
        return None
    return _blocos(est, membros)


def _blocos(est: dict, membros: list[dict]) -> dict[str, dict]:
    meses_est, pags, arqs = est["meses"], est["pags"], est["arqs"]
    # nomes de cada gabinete (o da lista do mês e os das planilhas: nome civil e, nas .xlsx, o nome parlamentar)
    nomes: dict[str, list[str]] = {}
    for mes in sorted(meses_est, reverse=True):
        if mes < INICIO[:7]:
            continue
        for d, n in meses_est[mes]["deps"].items():
            ns = nomes.setdefault(d, [])
            p = pags.get(f"{mes}/{d}") or {}
            for u in p.get("arqs") or []:
                for x in (arqs.get(u) or {}).get("nomes") or []:
                    if x not in ns:
                        ns.append(x)
            if n not in ns:
                ns.append(n)
    nm = Nomes(membros)
    # nome civil completo igual ao da lista de hoje (todas as palavras) vale antes da regra comum: "EDUARDO CARNEIRO DE
    # BRITO" é o deputado Eduardo Brito, e não Eduardo Carneiro (Eduardo Jorge Soares Carneiro), que a regra comum
    # também acharia
    civis: dict[frozenset, set] = {}
    for m in membros:
        k = frozenset(regional.palavras(m.get("nomeCivil")))
        if len(k) >= 3:
            civis.setdefault(k, set()).add(m["id"])

    def quem_e(n: str) -> str | None:
        ids = civis.get(frozenset(regional.palavras(n))) or set()
        return next(iter(ids)) if len(ids) == 1 else nm.quem(n)

    quem: dict[str, str] = {}
    sem, conflito = [], []
    for d, ns in nomes.items():
        if d in VIAP_MANUAL:
            if VIAP_MANUAL[d] != "-":
                quem[d] = VIAP_MANUAL[d]
            continue
        achados = {quem_e(n) for n in ns} - {None}
        if len(achados) == 1:
            quem[d] = achados.pop()
        elif achados:
            conflito.append(f"{d} {ns}")
        else:
            sem.append(ns[-1])
    if sem:
        log(f"  PB VIAP: gabinetes sem pessoa na lista de hoje (quem saiu): {sorted(sem)}")
    if conflito:
        log(f"  PB VIAP: ATENÇÃO: nomes que batem com mais de uma pessoa (conferir à mão; ficam de fora): {conflito}")
    ligados = set(quem.values())
    sem_gasto = [m["nome"] for m in membros if m["id"] not in ligados]
    if sem_gasto:
        log(f"  PB VIAP: pessoas da lista de hoje sem planilha da VIAP: {sem_gasto}")
    linhas: dict[str, list] = {}
    pagos: dict[str, dict[str, float]] = {}
    ultimo: dict[str, tuple[str, str]] = {}
    erros, outro_mes, sem_reembolso = [], [], []
    erros += [f"lista de {mes}" for mes, m in meses_est.items() if m.get("erro") and mes >= INICIO[:7]]
    for chave, p in pags.items():
        mes, d = chave.split("/")
        if mes < INICIO[:7] or d not in quem or d not in meses_est.get(mes, {}).get("deps", {}):
            continue
        pid = quem[d]
        if p.get("erro"):
            erros.append(f"{mes} {d}: a página do gabinete não abriu em {FALHAS_MAX} rodadas")
        for u in p["arqs"]:
            a = arqs.get(u) or {}
            if "erro" in a:
                erros.append(f"{mes} {d}: {a['erro']}")
                continue
            if abs(a["soma"] - a["total"]) > 0.005:
                log(f"  PB VIAP: ATENÇÃO: {u}: a soma das despesas ({a['soma']:.2f}) não bate com o Total de Despesas "
                    f"({a['total']:.2f})")
            if a.get("mes") and a["mes"] != mes:
                outro_mes.append(f"{mes} {d}: a planilha diz {a['mes']}")
            for tipo, v in a["t"].items():
                linhas.setdefault(pid, []).append((mes, tipo, v))
            if a.get("reembolso") is None:
                sem_reembolso.append(u)
            pg = pagos.setdefault(pid, {})
            pg[mes] = round(pg.get(mes, 0.0) + (a["reembolso"] if a.get("reembolso") is not None else a["total"]), 2)
            if mes >= ultimo.get(pid, ("", ""))[0]:
                ultimo[pid] = (mes, d)
    if erros:
        log(f"  PB VIAP: ATENÇÃO: o que não deu para ler (fica de fora): {erros[:10]}{'...' if len(erros) > 10 else ''}")
    if outro_mes:
        log(f"  PB VIAP: planilhas com competência diferente do mês da página (vale o mês da página): {outro_mes[:10]}")
    if sem_reembolso:
        log(f"  PB VIAP: planilhas sem a linha \"Reembolso\" (vale o Total de Despesas): {sem_reembolso[:5]}")
    nome_de = {m["id"]: m["nome"] for m in membros}
    out = {}
    for pid, ls in linhas.items():
        mes, d = ultimo[pid]
        f = fonte(VEICULO, f"VIAP de {nome_de.get(pid, pid)}: planilhas mensais de prestação de contas (Portal da Transparência)",
                  _url_viap(mes, d))
        b = bloco_gastos(_tipos_unicos(ls), f, INICIO, NOME_GASTOS)
        if b:  # o total (do ano e do mandato) é o que a ALPB reembolsou; os tipos são as despesas declaradas
            ano = str(b["ano"])
            b["total"] = round(sum(v for m, v in pagos[pid].items() if m.startswith(ano)), 2)
            b["mandatoTotal"] = round(sum(pagos[pid].values()), 2)
            out[pid] = b
    log(f"  PB VIAP: gastos de {len(out)} de {len(membros)} pessoas da lista de hoje; reembolsado no mandato: "
        f"{sum(b['mandatoTotal'] for b in out.values()):.2f}; despesas declaradas: "
        f"{sum(v for ls in linhas.values() for _, _, v in ls):.2f}")
    return out


def _tipos_unicos(linhas: list[tuple[str, str, float]]) -> list[tuple[str, str, float]]:
    """O mesmo subitem escrito de jeitos diferentes (caixa, acento, espaços) fica com o nome do mês mais recente."""
    nome: dict[str, tuple[str, str]] = {}
    for mes, t, _ in linhas:
        k = re.sub(r"[^a-z0-9]", "", sem_acento(t).lower())
        if mes >= nome.get(k, ("", ""))[0]:
            nome[k] = (mes, t)
    return [(mes, nome[re.sub(r"[^a-z0-9]", "", sem_acento(t).lower())][1], v) for mes, t, v in linhas]

