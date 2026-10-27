"""Câmara Municipal de Teresina (PI): o Processo Legislativo Eletrônico da Ágape (https://teresina.camarasempapel.com.br/spl):
a lista oficial de vereadores, as propostas de cada um desde 1º/1/2025 e os projetos que a prefeitura mandou à Câmara
(scripts/camaras/_agape.py; situação pelas regras de eventos_teresina, conferidas à mão). E os gastos do mandato: a
consulta "Despesas com Atividade Parlamentar" do Portal da Transparência da Câmara
(transparencia.teresina.pi.leg.br/project6-war/ext/consultarDespesaAtividade.jsf), lida como a página lê: o formulário com
o nome em branco e o ano (todos os vereadores de uma vez; a tabela de 30 em 30 linhas, a maior opção da própria tabela) dá
os nomes, e o mesmo formulário com cada nome dá os pagamentos de cada um (ver ler_ano).
Cada linha é um pagamento: nome do vereador (o nome civil, às vezes abreviado), empenho, liquidação, data do pagamento e
valor. A consulta não separa os gastos por tipo (as notas de cada pagamento ficam no botão "Detalhar", uma página por
pagamento), então o perfil mostra os totais.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time

from comum import fonte, hoje, ler_json, log, salvar_json, sem_acento

from . import _base as B
from . import _capitais as C
from ._agape import Agape

IBGE, UF, HOST = "2211001", "PI", "https://teresina.camarasempapel.com.br"
CASA = {"casa": "Câmara Municipal de Teresina", "casa_en": "Teresina City Council", "sigla": "CMT", "site": "https://www.teresina.pi.leg.br"}
# tipo no sistema → (tipo comum, sigla oficial: a das pastas de documentos do sistema). Fora: Emenda (139), Indicação (1),
# Requerimento (9), Veto (142). Projeto de Resolução Administrativa (140): nenhum desde 2025
TIPOS = {"4": ("PL", "PLO"), "141": ("PLP", "PLC"), "143": ("PELO", "PEL"), "3": ("PDL", "PDL"), "2": ("PRC", "PR")}
# nomes que a planilha escreve diferente do cartão do vereador (conferidos à mão em 27/10/2026, pela autoria com link na
# página de cada proposição): "James Guerra Junior" = cartão "Del. James Guerra" (parlamentar.aspx?id=55)
AUTORES = {"James Guerra Junior": "55"}
TRANSP = "https://transparencia.teresina.pi.leg.br/project6-war/ext/consultarDespesaAtividade.jsf"
# nome da consulta de despesas → nome do cartão do vereador, quando o nome civil do TSE é escrito de outro jeito (conferido
# à mão em 27/10/2026: a consulta escreve "M ALVERNE" e o TSE "Mont Alverde"; é o único Luis André de Arruda da Câmara)
NOMES_GASTOS = {"LUIS ANDRE DE ARRUDA M ALVERNE": "Luis André"}
POR_PAGINA = 30
NOME_GASTOS = ("Verba de atividade parlamentar (ressarcimento mensal das despesas do mandato, Lei 4.086/2011), pela data do pagamento",
               "Parliamentary activity allowance (monthly reimbursement of office expenses, Law 4,086/2011), by payment date")
CACHE_GASTOS = B.PASTA_CACHE / IBGE / "verba.json"

NOTAS = [
    ("As propostas vêm do Processo Legislativo Eletrônico, o sistema oficial da Câmara: a lista de cada tipo de proposição "
     "(planilha da própria consulta) e a página de cada uma, com o histórico da tramitação, de onde sai a situação (sanção, "
     "promulgação, veto, parecer da Comissão de Legislação, retirada pelo autor). Entram projetos de lei ordinária, de lei "
     "complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução apresentados desde 1º/1/2025; emendas, "
     "requerimentos, indicações e vetos não entram. O primeiro nome da lista de autores de cada proposição aparece como autor "
     "principal, e os outros como quem assinou junto. Quando a Câmara promulga uma norma (decretos legislativos, por exemplo), "
     "o sistema não registra o número dela: o perfil diz só que virou norma. O número de cada lei vem do arquivo da lei "
     "anexado ao processo. A situação é a que o sistema mostra: algumas propostas estão há meses na fase \"Aguardando "
     "Sanção\", e o perfil as mostra como \"esperando a decisão do prefeito\".",
     "Bills come from the Processo Legislativo Eletrônico, the City Council's official system: the list of each type of bill "
     "(the search's own spreadsheet) and each bill's page, with the history of its progress, which gives its status (signed, "
     "promulgated, vetoed, Legislation Committee opinion, withdrawn by the author). Included: bills for ordinary and "
     "complementary laws, amendments to the city's Organic Law, legislative decrees and resolutions filed since January 1, "
     "2025; amendments, requests, recommendations and vetoes are not included. The first name on each bill's list of authors "
     "is shown as its main author, and the others as co-signers. When the City Council promulgates a law itself (legislative "
     "decrees, for example), the system does not record its number: the profile only says it became law. Each law's number "
     "comes from the law's file attached to the bill. The status is what the system shows: some bills have been at the "
     "\"Aguardando Sanção\" (awaiting signature) stage for months, and the profile shows them as \"waiting for the mayor's "
     "decision\"."),
    ("As votações de cada vereador não entram neste site: o site e o portal da transparência da Câmara não têm uma "
     "consulta das votações nominais (o voto de cada vereador).",
     "Each councilor's votes are not included on this site: the City Council's website and transparency portal have no "
     "search for roll-call votes (how each councilor voted)."),
]
NOTA_GASTOS = (
    "Gastos do mandato: a verba de atividade parlamentar paga a cada vereador (o ressarcimento das despesas do mês, no valor "
    "recomendado pela Controladoria, pela Lei 4.086/2011), mês a mês, pela data do pagamento, segundo a consulta \"Despesas "
    "com Atividade Parlamentar\" do Portal da Transparência da Câmara. A consulta não separa os gastos por tipo (as notas de "
    "cada pagamento ficam no botão \"Detalhar\"). Quando a consulta mostra o mesmo pagamento duas vezes (mesmas notas de "
    "empenho e de liquidação, mesma data e mesmo valor), ele conta uma vez. Entram só os vereadores em exercício hoje.",
    "Office spending: the parliamentary activity allowance paid to each councilor (the reimbursement of the month's expenses, "
    "in the amount recommended by the City Council's internal audit office, under Law 4,086/2011), month by month, by payment "
    "date, according to the parliamentary activity expenses search on the City Council's Transparency Portal. The search "
    "does not split spending by type (the receipts for each payment are behind the \"Detalhar\" button). When the search "
    "shows the same payment twice (same commitment and settlement notes, same date and same amount), it is counted once. "
    "Only councilors in office today are included.")


# ------------------------------------------------------------------------------------------------ gastos
def _vs(t: str) -> str:
    m = re.search(r'javax\.faces\.ViewState[^>]*><!\[CDATA\[(.*?)\]\]>', t) or \
        re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', t)
    if not m:
        raise RuntimeError("a consulta de despesas veio sem o estado do formulário (javax.faces.ViewState)")
    return m.group(1)


def _linhas(t: str) -> list[list[str]]:
    out = []
    for tr in re.findall(r'(?s)<tr data-ri="\d+"[^>]*>(.*?)</tr>', t):
        tds = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", x)).strip() for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        if len(tds) >= 7:
            out.append(tds[1:7])  # nome, empenho, liquidação, data do pagamento, valor, exercício
    return out


AJAX = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest", "Referer": TRANSP}


def _pesquisa(rede: C.Rede, ex: str, nome: str, vs: str) -> tuple[int, list[list[str]], str]:
    """O botão "Consultar" (nome e ano): (total de linhas, primeira página da tabela, novo estado do formulário)."""
    d = {"formConsulta": "formConsulta", "nome": nome, "exercicio_focus": "", "exercicio_input": ex,
         "javax.faces.partial.ajax": "true", "javax.faces.source": "btConsultar", "javax.faces.partial.execute": "formConsulta",
         "javax.faces.partial.render": "formConsulta", "btConsultar": "btConsultar", "javax.faces.ViewState": vs}
    r = rede.pedir(TRANSP, d, headers=AJAX)[0].decode("utf-8", "replace")
    m = re.search(r"rowCount:(\d+)", r)
    if not m:
        raise RuntimeError("a consulta de despesas não disse quantas linhas tem")
    return int(m.group(1)), _linhas(r), _vs(r)


def _tudo(rede: C.Rede, ex: str, nome: str, vs: str) -> tuple[int, list[list[str]], str]:
    """Todas as linhas de uma consulta: a primeira página basta quando cabe tudo nela; senão, a tabela de 30 em 30."""
    total, linhas, vs = _pesquisa(rede, ex, nome, vs)
    if total > len(linhas):
        linhas = []
        for inicio in range(0, total, POR_PAGINA):
            d = {"formConsulta": "formConsulta", "nome": nome, "exercicio_focus": "", "exercicio_input": ex,
                 "javax.faces.partial.ajax": "true", "javax.faces.source": "dataTable",
                 "javax.faces.partial.execute": "dataTable", "javax.faces.partial.render": "dataTable",
                 "javax.faces.behavior.event": "page", "javax.faces.partial.event": "page", "dataTable_pagination": "true",
                 "dataTable_first": str(inicio), "dataTable_rows": str(POR_PAGINA), "dataTable_skipChildren": "true",
                 "dataTable_encodeFeature": "true", "dataTable_rppDD": str(POR_PAGINA), "javax.faces.ViewState": vs}
            r = rede.pedir(TRANSP, d, headers=AJAX)[0].decode("utf-8", "replace")
            pag = _linhas(r)
            if not pag:
                raise RuntimeError(f"a página {inicio // POR_PAGINA + 1} da consulta de despesas veio vazia")
            linhas += pag
            try:
                vs = _vs(r)
            except RuntimeError:
                pass
    if len(linhas) != total:
        raise RuntimeError(f"a consulta de despesas ({nome or 'todos'}) diz {total} linhas e vieram {len(linhas)}")
    return total, linhas, vs


def ler_ano(rede: C.Rede, ano: int) -> tuple[list[dict], int]:
    """Os pagamentos de um ano, como a página mostra: a consulta de todos (o nome em branco) dá os nomes e o total de linhas;
    depois, a consulta de cada nome (uma página só) dá os pagamentos de cada um, e a soma tem de bater com o total (assim, a
    ordem da tabela entre uma página e outra não muda o resultado). A consulta às vezes mostra o mesmo pagamento duas vezes
    (mesmas notas de empenho e de liquidação, mesma data e mesmo valor: ao abrir "Detalhar", as duas linhas são o mesmo
    ressarcimento): ele conta uma vez. Devolve (pagamentos, linhas repetidas)."""
    t = rede.pedir(TRANSP)[0].decode("utf-8", "replace")
    m = re.search(r'(?s)<select id="exercicio_input"[^>]*>(.*?)</select>', t)
    opc = {html.unescape(n).strip(): v for v, n in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', m.group(1) if m else "")}
    if str(ano) not in opc:
        raise RuntimeError(f"a consulta de despesas não tem o ano {ano}")
    ex = opc[str(ano)]
    total, todas, vs = _tudo(rede, ex, "", _vs(t))
    out, soma, repetidas = [], 0, 0
    for nome in sorted({l[0] for l in todas}):
        _, linhas, vs = _tudo(rede, ex, nome, vs)
        linhas = [l for l in linhas if l[0] == nome]
        soma += len(linhas)
        vistos = set()
        for _, emp, liq, data, valor, exerc in linhas:
            if (emp, liq, data, valor) in vistos:
                repetidas += 1
                continue
            vistos.add((emp, liq, data, valor))
            out.append({"nome": nome, "empenho": emp, "liquidacao": liq, "data": _iso(data), "valor": C.brl(valor),
                        "exercicio": exerc})
    if soma != total:
        raise RuntimeError(f"a consulta de despesas de {ano} tem {total} linhas e as consultas por nome somam {soma}")
    return out, repetidas


def _iso(d: str) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _palavras(s: str | None) -> list[str]:
    return [p for p in re.sub(r"[^a-z ]", " ", sem_acento(s or "").lower()).split() if p not in ("da", "de", "do", "das", "dos", "e")]


def _casa_nome(curto: list[str], longo: list[str]) -> bool:
    """O nome da consulta (às vezes abreviado: "FERNANDO EDUARDO S DE L SANTOS") cabe no nome civil, na mesma ordem, com o
    primeiro e o último nomes iguais e as letras soltas valendo como iniciais."""
    if not curto or not longo or curto[0] != longo[0] or curto[-1] != longo[-1]:
        return False
    i = 0
    for p in curto:
        while i < len(longo) and not (longo[i] == p or (len(p) == 1 and longo[i].startswith(p))):
            i += 1
        if i == len(longo):
            return False
        i += 1
    return True


def ligar(nomes: set[str], por_chave: dict[str, dict]) -> tuple[dict[str, str], set]:
    civis, por_nome = {}, {}
    for m in por_chave.values():
        por_nome[m.get("nome")] = m["id"]
        cand = m.get("_cand") or {}
        for n in (cand.get("nome"), m.get("nomeCivil")):
            if n:
                civis.setdefault(m["id"], []).append(_palavras(n))
    out, fora = {}, set()
    for nome in nomes:
        if NOMES_GASTOS.get(nome) in por_nome:
            out[nome] = por_nome[NOMES_GASTOS[nome]]
            continue
        p = _palavras(nome)
        ids = [pid for pid, ns in civis.items() if any(_casa_nome(p, n) for n in ns)]
        if len(ids) == 1:
            out[nome] = ids[0]
        else:
            fora.add(nome)
    return out, fora


def gastos(por_chave: dict[str, dict], prazo: float | None) -> tuple[dict, list]:
    """({id: bloco "gastos"}, [nota]) da verba de atividade parlamentar. Cada ano é lido de novo depois de 20 horas (anos
    passados: 7 dias); o que foi lido fica em .cache/camaras/2211001/verba.json."""
    h = hoje()
    rede = C.Rede(prazo)
    e = ler_json(CACHE_GASTOS, {}) or {}
    anos = list(range(int(B.INICIO[:4]), int(h[:4]) + 1))
    for ano in anos:
        x = e.get(str(ano)) or {}
        idade_h = (time.time() - x.get("ts", 0)) / 3600
        if idade_h >= (20 if ano >= int(h[:4]) else 24 * 7):
            linhas, repetidas = ler_ano(rede, ano)
            e[str(ano)] = {"ts": time.time(), "lido": h, "linhas": linhas, "repetidas": repetidas}
            salvar_json(CACHE_GASTOS, e)
    linhas = [l for ano in anos for l in (e.get(str(ano)) or {}).get("linhas") or []]
    rep = sum((e.get(str(ano)) or {}).get("repetidas") or 0 for ano in anos)
    ligacao, fora = ligar({l["nome"] for l in linhas}, por_chave)
    if fora:
        log(f"  CMT: verba de quem não está no cargo hoje (fica fora): {', '.join(sorted(fora))}")
    por: dict[str, dict] = {}
    for l in linhas:
        pid = ligacao.get(l["nome"])
        if not pid or not l["data"] or l["valor"] is None:
            continue
        k = (int(l["data"][:4]), int(l["data"][5:7]))
        mes = por.setdefault(pid, {}).setdefault(k, {})
        mes[""] = mes.get("", 0.0) + l["valor"]
    ultimo = max((l["data"] for l in linhas if l["data"]), default=None)
    f = fonte(CASA["casa"], "Portal da Transparência: Despesas com Atividade Parlamentar, pagamentos de janeiro de 2025 a "
              + (f"{C.nome_mes(int(ultimo[5:7]))} de {ultimo[:4]}" if ultimo else "hoje"), TRANSP, h)
    out = {pid: b for pid, por_mes in por.items() if (b := C.bloco_gastos(por_mes, NOME_GASTOS, f))}
    log(f"  CMT: verba de atividade parlamentar: {len(linhas)} pagamentos ({rep} linhas repetidas contadas uma vez), "
        f"{len(out)} vereadores, {rede.n} pedidos")
    return out, [NOTA_GASTOS]


def coletar() -> dict:
    return Agape(IBGE, UF, HOST, CASA, 29, TIPOS, "teresina", autores_manual=AUTORES, notas=NOTAS,
                 executivo=r"^prefeit|^poder executivo|^executivo", gastos=gastos).coletar()
