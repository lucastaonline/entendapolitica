"""Assembleia Legislativa do Estado de Rondônia (Ale-RO): SAPL 3 (https://sapl.al.ro.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL (a mesma lista de https://www.al.ro.leg.br/deputados/perfil/).
Propostas: matérias do SAPL desde 1º/2/2023; situação = a da última tramitação (quando ela não diz nada sozinha, vale o
texto dela ou a tramitação de antes); "virou lei" = norma jurídica ligada à proposta no SAPL.
Votações nominais: voto de cada deputado registrado no SAPL. Em Rondônia, a maioria das votações é simbólica (sem o voto
de cada um); as nominais (vetos, por exemplo) têm o voto de cada deputado.
Gastos: verba indenizatória (só as "Verbas Gerais") do Portal da Transparência da Ale-RO, uma página por gabinete e por
mês (gastos(), abaixo).
Governador (gov-RO): projetos do Poder Executivo, leis e vetos desde 1º/1/2023 (GOVERNO, abaixo).
"""
from __future__ import annotations

import datetime as dt
import re
import time
import urllib.parse

import regional
from comum import fonte, log, sem_acento
from mandatos import mes_ano

from . import _carga
from . import _nco_gov as G
from . import _votos_gastos as VG
from ._nco_comum import Rede, SemTempo, texto_html
from ._nco_sapl import Sapl

VETO_PENDENTE = ("Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
                 "Vetoed by the governor; the state assembly has yet to decide on the veto")
REGRAS = [
    (r"transformada em lei|norma promulgada|lei promulgada|veto total ou parcial promulgado", "lei", None, None),
    (r"retirado pela secretaria legislativa", "parada", "Retirada pela Secretaria Legislativa (não pôde seguir)",
     "Withdrawn by the Legislative Secretariat (could not go ahead)"),
    (r"retirad[ao] pelo autor|projeto retirado pelo autor", "retirada", None, None),
    (r"aguardando promulgacao de lei com veto rejeitado|veto sobre a proposicao rejeitado", "aprovada",
     "Aprovada; o veto do governador foi derrubado e falta promulgar", "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"aguardando deliberacao do poder executivo", "aprovada", "Aprovada; esperando a decisão do governador",
     "Approved; waiting for the governor's decision"),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando assinatura do autografo", "aprovada", "Aprovada; esperando a assinatura do texto final (autógrafo)",
     "Approved; waiting for the final text (autograph) to be signed"),
    (r"redacao\s+final inclusa na ordem do dia|vai a redacao final|aprovada a redacao final", "aprovada",
     "Aprovada; falta votar a redação final", "Approved; the final wording still needs a vote"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"aprovada em 2.? turno|^proposicao aprovada\.?$", "aprovada", None, None),
    (r"projeto aprovado na comissao", "andando", "Aprovada numa comissão", "Approved by a committee"),
    (r"com veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto sobre a proposicao mantido", "rejeitada", "Vetada pelo governador; a Assembleia manteve o veto",
     "Vetoed by the governor; the state assembly upheld the veto"),
    (r"veto|mensagem sobre o veto", "andando", *VETO_PENDENTE),
    (r"retirada da ordem do dia|adiada|vista|anulacao de votacao", "andando", None, None),
    (r"desarquiv", "andando", None, None),
    (r"vai ao arquivo|ao arquivo|pelo arquivamento", "arquivada", "Arquivada", None),
    (r"anexada", "junta", None, None),
    (r"rejeitada pela comissao", "rejeitada", "Rejeitada por uma comissão", "Rejected by a committee"),
    (r"rejeitada pelo plenario", "rejeitada", "Rejeitada pelo Plenário", "Rejected by the full assembly"),
    (r"^parecer contrario", "andando", "Recebeu parecer contrário de uma comissão", "Received an unfavorable opinion from a committee"),
    (r"autuada e cumprindo prazo de pauta", "andando", "Apresentada; aberta para receber emendas", "Filed; open for amendments"),
    (r"autuada|avocada|prazo|sem parecer|recurso|redistribuicao|despachada|decurso", "andando", None, None),
    (r"ordem do dia|em pauta|comissao|comissoes|parecer", "andando", None, None),
]
AMBIGUOS = [r"para providencias", r"requerimento deferido", r"^parecer contrario"]

# o que o governo do estado fez (perfil gov-RO): autor 29 = "Poder Executivo"; vetos = matérias "Veto Total" (17) e
# "Veto Parcial" (18); leis = normas "Lei ordinária" e "Lei Complementar". Conferido à mão em 23/10/2026.
GOVERNO = {
    "autores": [29],
    "tipos": {1: "PL", 5: "PLP", 12: "PEC", 6: "PDL"},
    "vetos": {"tipos": [17, 18], "tipos_totais": [17], "tipos_parciais": [18],
              "de_onde": ("matérias \"Veto Total\" e \"Veto Parcial\" que chegaram à Ale-RO no período, pela data em que foram lidas",
                          "\"Veto Total\" and \"Veto Parcial\" items received by the Ale-RO in the period, by the date they were read")},
    "leis": {"tipos": {1: "LO", 2: "LC"},
             "de_onde": ("cadastradas no sistema da Ale-RO (SAPL) com data no período",
                         "recorded in the Ale-RO's system (SAPL) with a date in the period"),
             "promulgadas": G.PROMULGADAS_INCLUIDAS},
    "nota": [G.EM_EXERCICIO],
}


# ---------------------------------------------------------------- gastos: verba indenizatória (verbas gerais)
# Portal da Transparência da Ale-RO, página "Verba Indenizatória" (VI): uma página por gabinete e por mês
# (?categoria=&ano=AAAA&mes=M&gabinete=<número>; sem o gabinete, o servidor dá erro 500; sem o mês, a página vem sem
# dados). O <select name="gabinete"> da página dá o número do gabinete de cada deputado. Cada bloco começa com
# "<Deputado(a) nome> - Mes: M/AAAA - Lote: Principal|Complementar - Verbas Gerais|Verbas de Saúde - Total pago: R$ x";
# os itens das verbas gerais trazem a "Classe" (o tipo de despesa) e o "Valor"; os da saúde, só a data e o valor. Entram
# só as "Verbas Gerais" (despesas do gabinete, como a cota dos deputados federais e as verbas das outras Assembleias); as
# "Verbas de Saúde" (ressarcimento de despesas de saúde do próprio deputado, o "Auxílio Saúde" da legislação) não entram.
# O filtro "categoria" da página não separa as duas (conferido em 26/10/2026): a separação vem do título de cada bloco.
# Mês sem lançamento: a tabela vem vazia; lote de R$ 0,00 pode vir sem o título (os itens dele ficam fora). robots.txt de
# transparencia.al.ro.leg.br: só fecha /admin/ e /painel/; sem Crawl-delay. Conferido à mão em 26/10/2026.
VI = "https://transparencia.al.ro.leg.br/Deputados/VerbaIndenizatoria/"
VEICULO = "Assembleia Legislativa de Rondônia (Ale-RO)"
NOME_GASTOS = ("Verba indenizatória (verbas gerais)", "Expense allowance (verba indenizatória, general expenses)")
GERAIS, SAUDE = "verbas gerais", "verbas de saude"  # o título de cada bloco, sem acento e em minúsculas
# Em alguns lotes, o "Total pago" do título é maior que a soma dos itens que a página lista (21 dos 1.013 meses com
# gastos lidos em 26/10/2026, R$ 121.972,24 de R$ 89,8 milhões; nunca o contrário): o total do mês segue o "Total pago" e a
# diferença entra com este nome, para a soma dos tipos dar o total que a página mostra.
SEM_DETALHE = "Sem detalhamento na página"
GASTOS_MANUAL: dict[str, str] = {}  # {nome na lista de gabinetes: id da pessoa ou "-"} (conferido à mão)
GASTOS_PASTA, GASTOS_ARQ = "alero-gastos", "verba.json"
GASTOS_DIA_S = 6 * 60  # rodada diária com o cache cheio: ~50 pedidos (1 a 2 min); o limite dá folga para o site lento
FECHA = 3              # um mês M lido a partir do 1º dia de M + 3 meses fica no cache para sempre; antes disso...
RELER_H = 20           # ...é relido a cada 20 h (a Casa ainda paga lotes complementares): na prática, os 2 meses mais recentes
ERROS_MAX = 3          # um mês que falha em 3 rodadas (com o site no ar) só é tentado de novo a cada 7 dias
BR = dt.timezone(dt.timedelta(hours=-3))


def nota_gastos() -> tuple[str, str]:
    pt, en = mes_ano(regional.inicio_estadual("RO"))
    return (f"Gastos: verba indenizatória, do Portal da Transparência da Ale-RO (uma página por gabinete e por mês): soma do "
            f"\"Total pago\" nas \"Verbas Gerais\" (despesas do gabinete, nos lotes principal e complementar), por classe de "
            f"despesa, desde {pt}. Em alguns lotes, o \"Total pago\" é maior que a soma dos itens que a página lista; a "
            f"diferença aparece como \"{SEM_DETALHE}\". As \"Verbas de Saúde\", publicadas na mesma página, não entram: são "
            f"o ressarcimento de despesas de saúde do próprio deputado, e não despesas do gabinete.",
            f"Spending: the expense allowance (verba indenizatória), from the Ale-RO transparency portal (one page per office "
            f"and month): the \"Total pago\" (amount paid) under \"Verbas Gerais\" (office expenses, in the main and "
            f"supplementary batches), by type of expense, since {en}. In some batches, the \"Total pago\" is larger than the "
            f"sum of the items the page lists; the difference appears as \"{SEM_DETALHE}\" (not itemized on the page). The "
            f"\"Verbas de Saúde\", published on the same page, are not included: they reimburse the deputy's own health "
            f"expenses and are not office expenses.")


def _nota_sem_lista(nomes: list[str]) -> tuple[str, str]:
    um = len(nomes) == 1
    pt = nomes[0] if um else f"{', '.join(nomes[:-1])} nem {nomes[-1]}"
    en = nomes[0] if um else f"{', '.join(nomes[:-1])} or {nomes[-1]}"
    return (f"Gastos: a página \"Verba Indenizatória\" da Ale-RO não traz {pt} na lista de gabinetes; por isso, "
            f"{'esse perfil fica' if um else 'esses perfis ficam'} sem os gastos da verba.",
            f"Spending: the Ale-RO \"Verba Indenizatória\" page does not include {en} in its list of offices, so "
            f"{'that profile has' if um else 'those profiles have'} no allowance spending.")


def _meses_gastos(inicio: str) -> list[str]:
    """'AAAA-MM' do começo da legislatura até o mês passado (a verba de um mês só é paga no mês seguinte)."""
    h = dt.datetime.now(BR).date()
    a, m = int(inicio[:4]), int(inicio[5:7])
    out = []
    while (a, m) < (h.year, h.month):
        out.append(f"{a}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _feito(item: dict | None) -> bool:
    return bool(item) and ("l" in item or item.get("e", 0) >= ERROS_MAX)


def _precisa(item: dict | None, mes: str) -> bool:
    """O mês precisa ser lido (de novo) nesta rodada? item = {"l": quando foi lido (segundos), ...} ou {"e": falhas,
    "u": última falha}."""
    agora = time.time()
    if not item or "l" not in item:
        return (item or {}).get("e", 0) < ERROS_MAX or agora - (item or {}).get("u", 0) >= 7 * 86400
    a, m = int(mes[:4]), int(mes[5:7]) + FECHA
    fecha = f"{a + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}-01"
    return dt.datetime.fromtimestamp(item["l"], BR).date().isoformat() < fecha and agora - item["l"] >= RELER_H * 3600


def _tipo(txt: str) -> str:
    """'DESPESAS DO ESCRITÓRIO DE APOIO' -> 'Despesas do escritório de apoio' (as palavras da Casa, sem as maiúsculas)."""
    t = re.sub(r"\s+", " ", txt or "").strip() or "Sem classe informada"
    letras = [c for c in t if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) > 0.6 * len(letras):
        t = t[0].upper() + t[1:].lower()
    return t


def _mesma_pessoa(nome: str | None, m: dict) -> bool:
    """O nome no título dos blocos de um mês é o da pessoa ligada ao gabinete? (2 palavras em comum com o nome usado no
    cargo ou com o nome civil, ou todas as do nome mais curto): conferência contra um gabinete que mudou de dono."""
    a = set(regional.palavras(nome))
    for ref in (m.get("nome"), m.get("nomeCivil")):
        b = set(regional.palavras(ref))
        if a and b and len(a & b) >= min(2, len(a), len(b)):
            return True
    return False


def _lista_gabinetes(rede: Rede) -> dict[str, str]:
    """{número do gabinete: nome} (o <select name="gabinete"> da página da verba). Se a página não responde, vale a última
    guardada no cache (os meses já lidos continuam valendo)."""
    try:
        h = rede.texto(VI, "pagina.html", RELER_H)
    except SemTempo:
        raise
    except Exception as e:
        arq = rede.pasta / "pagina.html"
        if not arq.exists():
            raise
        log(f"  RO gastos: a página da verba não respondeu ({type(e).__name__}); vale a lista guardada")
        h = arq.read_bytes().decode("utf-8", "replace")
    sel = re.search(r'<select[^>]*\bname="gabinete"[^>]*>(.*?)</select>', h, re.S)
    lista = {v: texto_html(n) for v, n in re.findall(r'<option value="(\d+)"[^>]*>(.*?)</option>', sel.group(1), re.S)} if sel else {}
    if len(lista) < 20:
        raise RuntimeError(f"a página da verba indenizatória mudou: {len(lista)} gabinetes na lista")
    return lista


def _pagina_mes(rede: Rede, gab: str, mes: str) -> dict:
    """Um mês da verba de um gabinete: {"l": quando foi lido, "n": nome no título dos blocos, "s": soma do "Total pago" das
    verbas gerais, "t": {classe: soma dos valores das verbas gerais}, "o": soma do "Total pago" das verbas de saúde}; só
    {"l"} quando a página vem sem lançamento."""
    url = f"{VI}?" + urllib.parse.urlencode({"categoria": "", "ano": mes[:4], "mes": int(mes[5:7]), "gabinete": gab})
    corpo = re.search(r'<table id="tabela".*?<tbody>(.*?)</tbody>', rede.texto(url), re.S)
    if not corpo:
        raise RuntimeError(f"página da verba fora do formato esperado (gabinete {gab}, {mes})")
    blocos: list[dict] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", corpo.group(1), re.S):
        txt = texto_html(tr)
        if "<h4" in tr:
            b = re.fullmatch(r"(.+?) - Mes: (\d{1,2})/(\d{4}) - Lote: (.+?) - (.+?) - Total pago: R\$\s*(-?[\d.,]+)", txt)
            if not b or f"{b.group(3)}-{int(b.group(2)):02d}" != mes:
                raise RuntimeError(f"título de bloco fora do esperado (gabinete {gab}, {mes}): {txt[:120]!r}")
            blocos.append({"n": b.group(1), "cat": sem_acento(b.group(5)).lower().strip(), "total": VG.valor_br(b.group(6)),
                           "itens": []})
            continue
        if not txt:  # linha de título sem o título (visto em lotes de R$ 0,00): os itens até o próximo título ficam fora
            blocos.append({"n": None, "cat": None, "total": 0.0, "itens": []})
            continue
        v = re.search(r"Valor:\s*R\$\s*(-?[\d.,]+)", txt)
        if not blocos or not v:
            raise RuntimeError(f"item fora do esperado (gabinete {gab}, {mes}): {txt[:80]!r}")
        c = re.search(r"Classe:\s*(.*?)\s*(?:\||$)", txt)
        blocos[-1]["itens"].append((c.group(1) if c else "", VG.valor_br(v.group(1))))
    blocos = [b for b in blocos if b["cat"] or b["itens"]]
    if not blocos:
        return {"l": int(time.time())}
    novas = {b["cat"] for b in blocos if b["cat"]} - {GERAIS, SAUDE}
    if novas:
        log(f"  RO gastos: gabinete {gab}, {mes}: categoria nova de verba ({sorted(novas)}); não entra")
    sem_titulo = sum(v for b in blocos if not b["cat"] for _, v in b["itens"])
    if sem_titulo:
        log(f"  RO gastos: gabinete {gab}, {mes}: itens sem título de bloco somam {sem_titulo:.2f}; não entram")
    t: dict[str, float] = {}
    for b in blocos:
        if b["cat"] != GERAIS:
            continue
        for c, v in b["itens"]:
            tipo = _tipo(c)
            t[tipo] = round(t.get(tipo, 0.0) + v, 2)
        if abs(sum(v for _, v in b["itens"]) - b["total"]) > 0.015:
            log(f"  RO gastos: gabinete {gab}, {mes}: o \"Total pago\" do bloco ({b['total']:.2f}) é diferente da soma dos itens "
                f"listados ({sum(v for _, v in b['itens']):.2f})")
    return {"l": int(time.time()), "n": next((b["n"] for b in blocos if b["n"]), ""),
            "s": round(sum(b["total"] for b in blocos if b["cat"] == GERAIS), 2),
            "t": {k: v for k, v in t.items() if v}, "o": round(sum(b["total"] for b in blocos if b["cat"] == SAUDE), 2)}


def _ler_meses(rede: Rede, est: dict, pend: list[tuple[str, str]]) -> int:
    """Lê os meses pendentes [(gabinete, 'AAAA-MM')] até acabar ou até o tempo da rodada acabar, guardando o progresso no
    cache. Três erros seguidos (site fora do ar): para e deixa o resto para a próxima rodada."""
    lidos, seguidos, erros = 0, [], []
    try:
        for gab, mes in pend:
            try:
                novo = _pagina_mes(rede, gab, mes)
            except SemTempo:
                raise
            except Exception as e:
                seguidos.append((gab, mes))
                erros.append(f"{gab}/{mes}: {type(e).__name__}: {e}")
                if len(seguidos) >= 3:
                    log("  RO gastos: 3 erros seguidos; o resto fica para a próxima rodada")
                    break
                continue
            for g, m in seguidos:  # falhas com o site no ar: contam (depois de ERROS_MAX, o mês espera 7 dias)
                x = est["m"].setdefault(g, {}).setdefault(m, {})
                if "l" not in x:
                    x.update(e=x.get("e", 0) + 1, u=int(time.time()))
            seguidos = []
            velho = est["m"].setdefault(gab, {}).get(mes) or {}
            if not (novo.get("t") or novo.get("s")) and (velho.get("t") or velho.get("s")):  # tinha e veio vazio: fica o de antes
                log(f"  RO gastos: gabinete {gab}, {mes} veio sem despesas (antes tinha); fica o que estava")
                continue
            est["m"][gab][mes] = novo
            lidos += 1
            if lidos % 25 == 0:
                rede.guardar(est, GASTOS_ARQ)
    except SemTempo:
        log("  RO gastos: o tempo desta rodada acabou; a leitura continua na próxima")
    finally:
        rede.guardar(est, GASTOS_ARQ)
        if erros:
            log(f"  RO gastos: {len(erros)} erros: {erros[:3]}{'...' if len(erros) > 3 else ''}")
    return lidos


def gastos(coletor, membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} da verba indenizatória (verbas gerais) desde o começo da legislatura, ou None
    enquanto a primeira carga (todos os meses de todos os gabinetes) não termina. Depois dela, quem tem algum mês por ler
    (uma pessoa nova) fica com o bloco de antes; quem não está na lista de gabinetes fica sem bloco (e ganha uma nota)."""
    t0 = time.time()
    inicio = regional.inicio_estadual("RO")
    rede = Rede(GASTOS_PASTA, pausa=1.0)
    est = rede.estado(GASTOS_ARQ, {}) or {}
    est.setdefault("m", {})
    rede.prazo = time.time() + _carga.limite_diario(GASTOS_DIA_S, not est.get("completo"))
    lista = _lista_gabinetes(rede)
    nomes = VG.Nomes(membros, GASTOS_MANUAL)
    gab: dict[str, str] = {}
    for g, nome in lista.items():
        pid = nomes.quem(nome)
        if pid and pid in gab:
            raise RuntimeError(f"dois gabinetes para a mesma pessoa ({nome})")
        if pid:
            gab[pid] = g
    nomes.avisar("RO", "gastos (lista de gabinetes da página da verba indenizatória)")
    sem_lista = [m["nome"] for m in membros if m["id"] not in gab]
    if sem_lista:
        log(f"  RO gastos: fora da lista de gabinetes da página da verba (sem bloco): {sem_lista}")
    meses = _meses_gastos(inicio)
    todos = [(gab[m["id"]], mes) for m in membros if m["id"] in gab for mes in meses]
    lidos = _ler_meses(rede, est, [(g, mes) for g, mes in todos if _precisa(est["m"].get(g, {}).get(mes), mes)])
    faltam = sum(1 for g, mes in todos if not _feito(est["m"].get(g, {}).get(mes)))
    log(f"  RO gastos: {lidos} meses lidos nesta rodada ({rede.pedidos} pedidos ao Portal da Transparência em "
        f"{int(time.time() - t0)} s); {len(todos) - faltam} de {len(todos)} meses no cache")
    if not est.get("completo"):
        if faltam:
            log("  RO gastos: primeira carga em andamento; os perfis ficam com o bloco de antes")
            if sem_lista and coletor is not None and any(VG.de_antes(m["id"], "gastos") for m in membros):
                coletor.notas.append(_nota_sem_lista(sem_lista))
            return None
        est["completo"] = True
        rede.guardar(est, GASTOS_ARQ)
    out: dict[str, dict | None] = {}
    for m in membros:
        g = gab.get(m["id"])
        if not g:
            continue
        itens = est["m"].get(g, {})
        if not all("l" in (itens.get(mes) or {}) for mes in meses):  # pessoa nova (ou mês com erro): fica o de antes
            out[m["id"]] = VG.de_antes(m["id"], "gastos")
            continue
        linhas, outro = [], []
        for mes in meses:
            it = itens[mes]
            if not it.get("t") and not it.get("s"):
                continue
            if not _mesma_pessoa(it.get("n"), m):
                outro.append(f"{mes} ({it.get('n')!r})")
                continue
            linhas += [(mes, t, v) for t, v in it["t"].items()]
            resto = round(it.get("s", 0.0) - sum(it["t"].values()), 2)
            if resto > 0.015:  # "Total pago" maior que os itens listados: a diferença, com nome próprio
                linhas.append((mes, SEM_DETALHE, resto))
            elif resto < -0.015:
                log(f"  RO gastos: gabinete {g}, {mes}: os itens listados passam do \"Total pago\" em {-resto:.2f}; valem os itens")
        if outro:
            log(f"  RO gastos: gabinete {g} ({m['nome']}) com outro nome no título, meses fora: {', '.join(outro)}")
        ult = max((mes for mes, _, _ in linhas), default=meses[-1] if meses else inicio[:7])
        f = fonte(VEICULO, f"Verba indenizatória de {m['nome']}: Portal da Transparência da Ale-RO (um mês por página; "
                           f"entram as \"Verbas Gerais\")",
                  f"{VI}?" + urllib.parse.urlencode({"categoria": "", "ano": ult[:4], "mes": int(ult[5:7]), "gabinete": g}))
        out[m["id"]] = VG.bloco_gastos(linhas, f, inicio, NOME_GASTOS)
    if sem_lista and coletor is not None:
        coletor.notas.append(_nota_sem_lista(sem_lista))
    return out


def coletar() -> dict:
    return Sapl(
        "RO", "https://sapl.al.ro.leg.br",
        "Assembleia Legislativa do Estado de Rondônia", "Legislative Assembly of the State of Rondônia",
        "Ale-RO", "https://www.al.ro.leg.br", "Assembleia Legislativa de Rondônia (Ale-RO)", "alero",
        {1: "PL", 5: "PLP", 12: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "alero",
        ambiguos=AMBIGUOS, votacoes=True, governo=GOVERNO, sic="https://transparencia.al.ro.leg.br/AcessoInformacao/",
        notas=[nota_gastos()], gastos=gastos,
    ).coletar()
