"""Assembleia Legislativa do Estado do Amazonas (Aleam): SAPL 3 (https://sapl.al.am.leg.br/api/).

Lista oficial: deputados ativos na legislatura atual do SAPL (a mesma lista de https://www.aleam.gov.br/deputados/).
Propostas: matérias do SAPL desde 1º/2/2023; situação = a da última tramitação (quando ela não diz nada sozinha, como
"Para Providências", vale o texto dela ou a tramitação de antes); "virou lei" = norma jurídica ligada à proposta no SAPL.
Votações nominais: voto de cada deputado registrado no SAPL (painel do Plenário).
Gastos: cota parlamentar (CEAP) do Portal da Transparência da Aleam, um CSV por deputado e por mês (gastos(), abaixo).
Governador (gov-AM): projetos do Poder Executivo, leis e vetos desde a posse de quem governa hoje (GOVERNO, abaixo).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import time
import urllib.parse

import regional
from comum import fonte, log
from mandatos import mes_ano

from . import _carga
from . import _nco_gov as G
from . import _votos_gastos as VG
from ._nco_comum import Rede, SemTempo, texto_html
from ._nco_sapl import Sapl

# situação da última tramitação (texto oficial sem acento, minúsculas) -> status do site; a primeira que bater vale.
# Conferido à mão em outubro de 2026 (ex.: PL 521/2023 "Comenda Entregue pelo Plenário" depois de virar lei;
# PL 555/2024 "Veto sobre a proposição mantido" sem lei; PL 1170/2023 "Para Providências" com texto "Arquivado").
REGRAS = [
    (r"transformada em lei|norma promulgada|lei promulgada|veto total ou parcial promulgado|comenda entregue", "lei", None, None),
    (r"retirad[ao] de tramitacao pelo autor|retirad[ao] pelo autor|requerimento de retirada", "retirada", None, None),
    (r"aguardando promulgacao de lei com veto rejeitado|veto sobre a proposicao rejeitado", "aprovada",
     "Aprovada; o veto do governador foi derrubado e falta promulgar", "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"aguardando sancao|a sancao governamental", "aprovada", "Aprovada; esperando a sanção do governador",
     "Approved; waiting for the governor to sign it"),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando assinatura do autografo", "aprovada", "Aprovada; esperando a assinatura do texto final (autógrafo)",
     "Approved; waiting for the final text (autograph) to be signed"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"^proposicao aprovada\.?$", "aprovada", None, None),
    (r"com veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"veto sobre a proposicao mantido", "rejeitada", "Vetada pelo governador; a Assembleia manteve o veto",
     "Vetoed by the governor; the state assembly upheld the veto"),
    (r"veto sobre a proposicao aplicado|veto distribuido|veto\s+incluso|parecer pel[ao] (rejeicao|manutencao) do veto",
     "andando", "Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
     "Vetoed by the governor; the state assembly has yet to decide on the veto"),
    (r"retirada da ordem do dia|adiada", "andando", None, None),
    (r"desarquivada", "andando", None, None),
    (r"devolvida ao autor para correc", "parada", "Devolvida ao autor para correções", "Returned to the author for corrections"),
    (r"pelo arquivamento", "arquivada", "Arquivada (parecer de comissão pelo arquivamento)",
     "Shelved (a committee recommended shelving it)"),
    (r"rejeitada pela comissao", "rejeitada", "Rejeitada por uma comissão", "Rejected by a committee"),
    (r"rejeitada pelo plenario", "rejeitada", "Rejeitada pelo Plenário", "Rejected by the full assembly"),
    (r"^parecer contrario", "andando", "Recebeu parecer contrário de uma comissão", "Received an unfavorable opinion from a committee"),
    (r"autuada e cumprindo prazo de pauta", "andando", "Apresentada; aberta para receber emendas", "Filed; open for amendments"),
    (r"prejudicialidade|ordem do dia|em pauta|comissao", "andando", None, None),
]
# situações que não dizem nada sozinhas: vale o texto da tramitação ou a tramitação de antes
AMBIGUOS = [r"para providencias", r"requerimento deferido", r"deferido pela presidencia", r"^parecer contrario",
            r"assinatura do secretario geral"]

# o que o governo do estado fez (perfil gov-AM): autor 28 = "Poder Executivo" (tipo de autor "Externo"); vetos = matérias
# "Veto a Projeto de Lei" (a ementa começa com "VETO TOTAL" ou "VETO PARCIAL"); leis = normas "Lei Ordinária" e "Lei
# Complementar" (o tipo "Lei Promulgada" não tem nada desde 2018). Conferido à mão em 23/10/2026.
GOVERNO = {
    "autores": [28],
    "tipos": {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL"},
    "vetos": {"tipos": [9], "parcial": r"veto parcial", "total": r"veto total",
              "de_onde": ("mensagens \"Veto a Projeto de Lei\" que chegaram à Aleam no período, pela data em que foram lidas",
                          "\"Veto a Projeto de Lei\" messages received by the Aleam in the period, by the date they were read")},
    "leis": {"tipos": {1: "LO", 2: "LC"},
             "de_onde": ("cadastradas no sistema da Aleam (SAPL) com data no período",
                         "recorded in the Aleam's system (SAPL) with a date in the period"),
             "promulgadas": G.PROMULGADAS_INCLUIDAS},
    "nota": [G.EM_EXERCICIO],
}


# ---------------------------------------------------------------- gastos: cota parlamentar (CEAP)
# Portal da Transparência da Aleam, página "Controle de Cota Parlamentar" (CEAP_PAG): o formulário pede ano, mês e
# parlamentar (o <select name="dados"> dá o número de cada deputado; vale de fevereiro de 2023 em diante) e gera um CSV por
# deputado e por mês (CEAP_CSV): nome civil, competência, "Despesa Reembolsável" (o total do mês) e cada despesa, com
# "Verba/Descrição" (o tipo) e "Val Líquido" (o que foi reembolsado, depois da glosa). Mês sem lançamento: erro 400
# ("Nenhum dado encontrado para exportação."). A Aleam lança as despesas de um mês até o último dia útil do mês seguinte
# (aviso da página). robots.txt de www.aleam.gov.br: só fecha /cgi-bin/, /wp-login.php e /wp-admin/; sem Crawl-delay.
# Conferido à mão em 26/10/2026: a soma do "Val Líquido" é a "Despesa Reembolsável" que a página mostra (em 2 dos 979
# meses com despesas, o cabeçalho do CSV traz um número maior, que só aparece no saldo; a página mostra a soma das linhas).
CEAP_PAG = "https://www.aleam.gov.br/transparencia/controle-de-cota-parlamentar/"
CEAP_CSV = "https://www.aleam.gov.br/transparencia/wp-content/themes/transparencia/createCeap.php"
VEICULO = "Assembleia Legislativa do Amazonas (Aleam)"
NOME_GASTOS = ("Cota parlamentar (CEAP)", "Office allowance (CEAP, cota parlamentar)")
MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro",
         "Dezembro")  # como o formulário manda (o texto de cada mês)
GASTOS_MANUAL: dict[str, str] = {}  # {nome na lista da página da cota: id da pessoa ou "-"} (conferido à mão)
GASTOS_PASTA, GASTOS_ARQ = "aleam-gastos", "ceap.json"
GASTOS_DIA_S = 6 * 60  # rodada diária com o cache cheio: ~50 pedidos (1 a 2 min); o limite dá folga para o site lento
FECHA = 3              # um mês M lido a partir do 1º dia de M + 3 meses fica no cache para sempre; antes disso...
RELER_H = 20           # ...é relido a cada 20 h (a Casa ainda lança e corrige): na prática, os 2 meses mais recentes
ERROS_MAX = 3          # um mês que falha em 3 rodadas (com o site no ar) só é tentado de novo a cada 7 dias
BR = dt.timezone(dt.timedelta(hours=-3))


def nota_gastos() -> tuple[str, str]:
    pt, en = mes_ano(regional.inicio_estadual("AM"))
    return (f"Gastos: cota parlamentar (CEAP), do Portal da Transparência da Aleam (página \"Controle de Cota Parlamentar\", "
            f"um arquivo por deputado e por mês): soma do valor líquido de cada despesa (o que foi reembolsado), por tipo, "
            f"desde {pt}. A Aleam lança as despesas de cada mês até o último dia útil do mês seguinte.",
            f"Spending: the office allowance (cota parlamentar, CEAP), from the Aleam transparency portal (\"Controle de Cota "
            f"Parlamentar\" page, one file per deputy and month): the net amount of each expense (what was reimbursed), by "
            f"type, since {en}. The Aleam posts each month's expenses by the last working day of the following month.")


def _nota_sem_lista(nomes: list[str]) -> tuple[str, str]:
    um = len(nomes) == 1
    pt = nomes[0] if um else f"{', '.join(nomes[:-1])} nem {nomes[-1]}"
    en = nomes[0] if um else f"{', '.join(nomes[:-1])} or {nomes[-1]}"
    return (f"Gastos: a página \"Controle de Cota Parlamentar\" da Aleam não traz {pt} na lista de parlamentares; por isso, "
            f"{'esse perfil fica' if um else 'esses perfis ficam'} sem os gastos da cota.",
            f"Spending: the Aleam \"Controle de Cota Parlamentar\" page does not include {en} in its list of legislators, so "
            f"{'that profile has' if um else 'those profiles have'} no allowance spending.")


def _meses_gastos(inicio: str) -> list[str]:
    """'AAAA-MM' do começo da legislatura até o mês passado (as despesas de um mês só são lançadas no mês seguinte)."""
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
    """'COMBUSTIVEL / LUBRIFICANTE' -> 'Combustivel / lubrificante' (as palavras da Casa, sem as letras maiúsculas)."""
    t = re.sub(r"\s+", " ", txt or "").strip() or "Sem tipo informado"
    letras = [c for c in t if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) > 0.6 * len(letras):
        t = t[0].upper() + t[1:].lower()
    return t


def _mesma_pessoa(nome: str | None, m: dict) -> bool:
    """O nome escrito no CSV de um mês é o da pessoa ligada ao número? (2 palavras em comum com o nome civil ou com o
    nome usado no cargo, ou todas as do nome mais curto): conferência contra um número que mudou de dono."""
    a = set(regional.palavras(nome))
    for ref in (m.get("nomeCivil"), m.get("nome")):
        b = set(regional.palavras(ref))
        if a and b and len(a & b) >= min(2, len(a), len(b)):
            return True
    return False


def _lista_cota(rede: Rede) -> dict[str, str]:
    """{número do deputado no formulário da cota: nome} (o <select name="dados">). Se a página não responde, vale a última
    guardada no cache (os meses já lidos continuam valendo)."""
    try:
        h = rede.texto(CEAP_PAG, "pagina.html", RELER_H)
    except SemTempo:
        raise
    except Exception as e:
        arq = rede.pasta / "pagina.html"
        if not arq.exists():
            raise
        log(f"  AM gastos: a página da cota não respondeu ({type(e).__name__}); vale a lista guardada")
        h = arq.read_bytes().decode("utf-8", "replace")
    sel = re.search(r'<select[^>]*\bname="dados"[^>]*>(.*?)</select>', h, re.S)
    lista = {v: texto_html(n) for v, n in re.findall(r'<option value="(\d+)"[^>]*>(.*?)</option>', sel.group(1), re.S)} if sel else {}
    if len(lista) < 20:
        raise RuntimeError(f"a página da cota parlamentar mudou: {len(lista)} nomes na lista de parlamentares")
    return lista


def _csv_mes(rede: Rede, num: str, mes: str) -> dict:
    """Um mês da cota de um deputado: {"l": quando foi lido, "n": nome civil, "s": "Despesa Reembolsável", "t": {tipo:
    soma do "Val Líquido"}}; só {"l"} quando a Aleam não lançou nada no mês."""
    url = f"{CEAP_CSV}?" + urllib.parse.urlencode({"parlamentar": num, "parlamentarJaneiro": "", "mes": MESES[int(mes[5:7]) - 1],
                                                 "ano": mes[:4], "formato": "csv"})
    try:
        txt = rede.bruto(url).decode("utf-8-sig", "replace")
    except RuntimeError as e:
        if "HTTP Error 400" in str(e):  # "Nenhum dado encontrado para exportação."
            return {"l": int(time.time())}
        raise
    linhas = list(csv.reader(io.StringIO(txt), delimiter=";"))
    k = next((i for i, l in enumerate(linhas) if l and l[0].strip() == "Lote"), None)
    cab = {l[0].strip(): l[1].strip() for l in linhas[:k or 0] if len(l) >= 2}
    if k is None or VG.mes_br(cab.get("Competência")) != mes:
        raise RuntimeError(f"CSV da cota fora do formato esperado (número {num}, {mes})")
    col = [c.strip() for c in linhas[k]]
    ct, cv = col.index("Verba/Descrição"), col.index("Val Líquido")
    t: dict[str, float] = {}
    for l in linhas[k + 1:]:
        if len(l) > max(ct, cv) and l[cv].strip():
            tipo = _tipo(l[ct])
            t[tipo] = round(t.get(tipo, 0.0) + VG.valor_br(l[cv]), 2)
    s = VG.valor_br(cab.get("Despesa Reembolsável"))
    if abs(sum(t.values()) - s) > 0.015:  # visto em 2 meses (out/2026): a página mostra a soma das despesas listadas
        log(f"  AM gastos: número {num}, {mes}: a \"Despesa Reembolsável\" do CSV ({s:.2f}) é diferente da soma das despesas "
            f"listadas ({sum(t.values()):.2f}); vale a soma (a mesma que a página mostra)")
    return {"l": int(time.time()), "n": cab.get("Deputado(a)", ""), "s": s, "t": t}


def _ler_meses(rede: Rede, est: dict, pend: list[tuple[str, str]]) -> int:
    """Lê os meses pendentes [(número, 'AAAA-MM')] até acabar ou até o tempo da rodada acabar, guardando o progresso no
    cache. Três erros seguidos (site fora do ar): para e deixa o resto para a próxima rodada."""
    lidos, seguidos, erros = 0, [], []
    try:
        for num, mes in pend:
            try:
                novo = _csv_mes(rede, num, mes)
            except SemTempo:
                raise
            except Exception as e:
                seguidos.append((num, mes))
                erros.append(f"{num}/{mes}: {type(e).__name__}: {e}")
                if len(seguidos) >= 3:
                    log("  AM gastos: 3 erros seguidos; o resto fica para a próxima rodada")
                    break
                continue
            for n, m in seguidos:  # falhas com o site no ar: contam (depois de ERROS_MAX, o mês espera 7 dias)
                x = est["m"].setdefault(n, {}).setdefault(m, {})
                if "l" not in x:
                    x.update(e=x.get("e", 0) + 1, u=int(time.time()))
            seguidos = []
            velho = est["m"].setdefault(num, {}).get(mes) or {}
            if not novo.get("t") and velho.get("t"):  # tinha despesas e veio vazio: fica o de antes (relido depois)
                log(f"  AM gastos: número {num}, {mes} veio sem despesas (antes tinha); fica o que estava")
                continue
            est["m"][num][mes] = novo
            lidos += 1
            if lidos % 25 == 0:
                rede.guardar(est, GASTOS_ARQ)
    except SemTempo:
        log("  AM gastos: o tempo desta rodada acabou; a leitura continua na próxima")
    finally:
        rede.guardar(est, GASTOS_ARQ)
        if erros:
            log(f"  AM gastos: {len(erros)} erros: {erros[:3]}{'...' if len(erros) > 3 else ''}")
    return lidos


def gastos(coletor, membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} da cota parlamentar (CEAP) desde o começo da legislatura, ou None enquanto a primeira
    carga (todos os meses de todos os deputados) não termina. Depois dela, quem tem algum mês por ler (uma pessoa nova)
    fica com o bloco de antes; quem não está na lista da página da cota fica sem bloco (e ganha uma nota da Casa)."""
    t0 = time.time()
    inicio = regional.inicio_estadual("AM")
    rede = Rede(GASTOS_PASTA, pausa=1.0)
    est = rede.estado(GASTOS_ARQ, {}) or {}
    est.setdefault("m", {})
    rede.prazo = time.time() + _carga.limite_diario(GASTOS_DIA_S, not est.get("completo"))
    lista = _lista_cota(rede)
    nomes = VG.Nomes(membros, GASTOS_MANUAL)
    num: dict[str, str] = {}
    for n, nome in lista.items():
        pid = nomes.quem(nome)
        if pid and pid in num:
            raise RuntimeError(f"dois números da lista da cota para a mesma pessoa ({nome})")
        if pid:
            num[pid] = n
    nomes.avisar("AM", "gastos (lista da página da cota parlamentar)")
    sem_lista = [m["nome"] for m in membros if m["id"] not in num]
    if sem_lista:
        log(f"  AM gastos: fora da lista da página da cota (sem bloco): {sem_lista}")
    meses = _meses_gastos(inicio)
    todos = [(num[m["id"]], mes) for m in membros if m["id"] in num for mes in meses]
    lidos = _ler_meses(rede, est, [(n, mes) for n, mes in todos if _precisa(est["m"].get(n, {}).get(mes), mes)])
    faltam = sum(1 for n, mes in todos if not _feito(est["m"].get(n, {}).get(mes)))
    log(f"  AM gastos: {lidos} meses lidos nesta rodada ({rede.pedidos} pedidos ao Portal da Transparência em "
        f"{int(time.time() - t0)} s); {len(todos) - faltam} de {len(todos)} meses no cache")
    if not est.get("completo"):
        if faltam:
            log("  AM gastos: primeira carga em andamento; os perfis ficam com o bloco de antes")
            if sem_lista and coletor is not None and any(VG.de_antes(m["id"], "gastos") for m in membros):
                coletor.notas.append(_nota_sem_lista(sem_lista))
            return None
        est["completo"] = True
        rede.guardar(est, GASTOS_ARQ)
    out: dict[str, dict | None] = {}
    for m in membros:
        n = num.get(m["id"])
        if not n:
            continue
        itens = est["m"].get(n, {})
        if not all("l" in (itens.get(mes) or {}) for mes in meses):  # pessoa nova (ou mês com erro): fica o de antes
            out[m["id"]] = VG.de_antes(m["id"], "gastos")
            continue
        linhas, outro = [], []
        for mes in meses:
            it = itens[mes]
            if not it.get("t"):
                continue
            if not _mesma_pessoa(it.get("n"), m):
                outro.append(f"{mes} ({it.get('n')!r})")
                continue
            linhas += [(mes, t, v) for t, v in it["t"].items()]
        if outro:
            log(f"  AM gastos: CSV do número {n} ({m['nome']}) com outro nome, meses fora: {', '.join(outro)}")
        f = fonte(VEICULO, f"Cota parlamentar (CEAP) de {m['nome']}: Portal da Transparência da Aleam (escolha o ano, o mês "
                           f"e o parlamentar)", CEAP_PAG)
        out[m["id"]] = VG.bloco_gastos(linhas, f, inicio, NOME_GASTOS)
    if sem_lista and coletor is not None:
        coletor.notas.append(_nota_sem_lista(sem_lista))
    return out


def coletar() -> dict:
    return Sapl(
        "AM", "https://sapl.al.am.leg.br",
        "Assembleia Legislativa do Estado do Amazonas", "Legislative Assembly of the State of Amazonas",
        "Aleam", "https://www.aleam.gov.br", "Assembleia Legislativa do Amazonas (Aleam)", "aleam",
        {1: "PL", 5: "PLP", 10: "PEC", 6: "PDL", 2: "PRC"}, REGRAS, "aleam",
        ambiguos=AMBIGUOS, votacoes=True, governo=GOVERNO, sic="https://www.aleam.gov.br/transparencia/sic",
        notas=[nota_gastos()], gastos=gastos,
    ).coletar()
