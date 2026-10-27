"""Gastos do mandato dos vereadores de João Pessoa (PB): a verba indenizatória que a Câmara publica numa tabela do site
oficial (https://joaopessoa.pb.leg.br/transparencia/verbas-indenizatorias/: mês, vereador, serviço, valor, contratos e notas
fiscais em PDF). Um pedido por dia (a página guardada vale 20 h).

Cada linha é um mês de um vereador: um valor só, com os serviços descritos em texto livre ("ASSESSORIA JURÍDICA E
DIVULGAÇÃO DE ATIVIDADE PARLAMENTAR"). Por isso o perfil mostra os totais (do ano mais recente com dados e desde janeiro de
2025), sem a divisão por tipo de despesa. Ligação com a lista oficial pelo nome completo (como a tabela escreve) comparado ao
nome civil do vereador no SAPL e ao nome na candidatura de 2024 (TSE); na dúvida, não liga. Uma linha repetida igual (mesmo
mês, vereador, serviço, valor e documentos) conta uma vez.

Usado por c2507507.py depois do coletor do SAPL (aplicar): o SAPL grava a lista e as propostas; aqui entram os gastos no
arquivo da cidade e a cobertura/nota da Câmara. Se a leitura falhar, ficam os gastos publicados antes.
"""
from __future__ import annotations

import difflib
import html
import re

import regional
from comum import EXTRAS_CIDADES, fonte, hoje, ler_json, log
from regional import CAMARAS

from . import _base as B
from . import _capitais_c as C

IBGE, UF = "2507507", "PB"
URL = "https://joaopessoa.pb.leg.br/transparencia/verbas-indenizatorias/"
CASA = "Câmara Municipal de João Pessoa"
NOME = ("Verba indenizatória (prestação de contas na tabela do site da Câmara)",
        "Office allowance (as accounted for in the table on the City Council's website)")
NOTA_COM = ("Gastos do mandato: a verba indenizatória que a Câmara publica numa tabela do site (um valor por mês para cada "
            "vereador, com os serviços descritos em texto livre e os contratos e notas fiscais em PDF). Como cada mês tem um "
            "valor só, o perfil mostra os totais, sem a divisão por tipo de despesa. Uma linha repetida igual conta uma vez; os "
            "meses mais recentes aparecem quando a Câmara os publica.",
            "Office spending: the office allowance the City Council publishes in a table on its website (one amount per month "
            "for each councilor, with the services described in free text and the contracts and invoices as PDFs). Since "
            "each month has a single amount, the profile shows the totals, without a breakdown by type of expense. A repeated "
            "identical row counts once; the latest months appear when the City Council publishes them.")
NOTA_SEM = ("Os gastos do mandato de cada vereador não entram neste site: o SAPL da Câmara não tem esse dado, e o site da "
            "Câmara mostra a verba indenizatória numa tabela de página (um valor por mês, com os serviços descritos em texto "
            "livre), sem dados abertos.",
            "Each councilor's office spending is not included on this site: the City Council's SAPL system does not have it, "
            "and the City Council's website shows the office allowance in a table on a web page (one amount per month, with "
            "the services described in free text), with no open data.")


def _valor(s: str) -> float | None:
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})", s or "")
    return float(m.group(1).replace(".", "") + "." + m.group(2)) if m else None


def linhas(t: str) -> list[dict]:
    """As linhas da tabela: {mes: "AAAA-MM", nome, servico, valor, docs}."""
    tabs = re.findall(r"<table.*?</table>", t, re.S)
    if not tabs:
        raise RuntimeError("a página das verbas indenizatórias mudou (sem tabela)")
    tb = max(tabs, key=len)
    cab = [C.texto(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", tb, re.S)]
    if [B.norm(c) for c in cab[:4]] != ["mes/ano", "parlamentar", "servico", "valor"]:
        raise RuntimeError(f"a tabela das verbas indenizatórias mudou ({cab})")
    out = []
    for r in re.findall(r"<tr.*?</tr>", tb, re.S):
        cel = dict(re.findall(r'<td class="column-(\d)">(.*?)(?=<td class="column-|</tr>|$)', r, re.S))
        if not cel:
            continue
        m = re.search(r"(\d{1,2})/(\d{4})", C.texto(cel.get("1")))
        valor = _valor(html.unescape(re.sub(r"<[^>]+>", " ", cel.get("4") or "")))
        nome = C.texto(cel.get("2"))
        if not m or not nome or valor is None:
            raise RuntimeError(f"linha da tabela fora do formato: {C.texto(r)[:120]}")
        docs = tuple(re.findall(r'href="([^"]+)"', (cel.get("5") or "") + (cel.get("6") or "")))
        out.append({"mes": f"{m.group(2)}-{int(m.group(1)):02d}", "nome": nome, "servico": C.texto(cel.get("3")),
                    "valor": valor, "docs": docs})
    if len(out) < 100:
        raise RuntimeError(f"a tabela das verbas indenizatórias veio com {len(out)} linhas")
    return out


def _chave(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", B.sem_acento((s or "").lower())).strip()


def ligar(nome: str, nomes_por_id: dict[str, list[str]]) -> str | None:
    """id da lista oficial cujo nome completo é este (igual; ou quase igual, parecença de 0,92 ou mais sem empate; ou com
    todas as palavras de um dentro do outro, pelo menos 3, sem empate)."""
    alvo = _chave(nome)
    iguais = {pid for pid, ns in nomes_por_id.items() if alvo in {_chave(n) for n in ns}}
    if len(iguais) == 1:
        return iguais.pop()
    if iguais:
        return None
    notas = sorted(((max(difflib.SequenceMatcher(None, alvo, _chave(n)).ratio() for n in ns), pid)
                    for pid, ns in nomes_por_id.items() if ns), reverse=True)
    if notas and notas[0][0] >= 0.92 and (len(notas) == 1 or notas[1][0] < notas[0][0] - 0.05):
        return notas[0][1]
    pa = set(alvo.split()) - {"da", "de", "do", "das", "dos", "e"}
    sub = {pid for pid, ns in nomes_por_id.items() for n in ns
           if len(pa) >= 3 and (lambda pb: len(pb) >= 3 and (pa <= pb or pb <= pa))(set(_chave(n).split()) - {"da", "de", "do", "das", "dos", "e"})}
    return sub.pop() if len(sub) == 1 else None


def gastos(membros: list[dict], h: str, rede: C.Rede | None = None, t: str | None = None) -> tuple[dict, dict, dict]:
    """({id: bloco "gastos"}, {nome sem ligação: linhas}, {"linhas", "repetidas", "meses"}) desde janeiro de 2025."""
    if t is None:
        rede = rede or C.Rede(IBGE, 1.0)
        t = rede.pagina(URL, "verbas-indenizatorias.html", 20)
    tse = B.Tse(IBGE, UF)
    nomes_por_id: dict[str, list[str]] = {}
    for m in membros:
        ns = [m.get("nome"), m.get("nomeCivil")]
        sq = m["id"].rsplit("-", 1)[-1]
        cand = tse.por_sq.get(sq)
        if cand:
            ns += [cand.get("nome"), cand.get("urna")]
        nomes_por_id[m["id"]] = [n for n in ns if n]
    vistos, repetidas = set(), 0
    por: dict[str, dict[str, float]] = {}
    sem: dict[str, int] = {}
    ligados: dict[str, str | None] = {}
    for x in linhas(t):
        if x["mes"] < B.INICIO[:7]:
            continue
        k = (x["mes"], _chave(x["nome"]), x["servico"], x["valor"], x["docs"])
        if k in vistos:
            repetidas += 1
            continue
        vistos.add(k)
        if x["nome"] not in ligados:
            ligados[x["nome"]] = ligar(x["nome"], nomes_por_id)
        pid = ligados[x["nome"]]
        if not pid:
            sem[x["nome"]] = sem.get(x["nome"], 0) + 1
            continue
        por.setdefault(pid, {})[x["mes"]] = round(por.get(pid, {}).get(x["mes"], 0.0) + x["valor"], 2)
    meses_todos = sorted({k[0] for k in vistos})
    f = fonte(CASA, "Transparência: verbas indenizatórias (tabela do site oficial, com contratos e notas fiscais)", URL, h)
    out = {}
    for pid, pm in por.items():
        meses = sorted(pm)
        if not meses or round(sum(pm.values()), 2) <= 0:
            continue
        ano = meses[-1][:4]
        do_ano = [k for k in meses if k[:4] == ano]
        out[pid] = {"ano": int(ano), "total": round(sum(pm[k] for k in do_ano), 2), "porTipo": [],
                    "mandatoTotal": round(sum(pm.values()), 2), "desde": meses[0], "meses": [do_ano[0], do_ano[-1]],
                    "nome": NOME[0], "nome_en": NOME[1], "fonte": f}
    return out, sem, {"repetidas": repetidas, "meses": [meses_todos[0], meses_todos[-1]] if meses_todos else None}


def aplicar(r: dict, antes: dict[str, dict], rede: C.Rede | None = None) -> dict:
    """Depois do coletor do SAPL (que regravou os arquivos da cidade): põe os gastos no arquivo da cidade
    (dados/camaras/extras/<IBGE>.json), a cobertura e a nota da Câmara (dados/camaras/<IBGE>.json) e o número no resumo.
    antes = {id: bloco "gastos"} publicado antes da rodada: fica se a leitura de hoje falhar ou se o SAPL não terminou a
    rodada (primeira carga em andamento: aí a tabela não é lida de novo)."""
    casa = ler_json(CAMARAS / f"{IBGE}.json", {}) or {}
    cidade = ler_json(EXTRAS_CIDADES / f"{IBGE}.json", {}) or {}
    membros = casa.get("membros") or []
    pessoas = cidade.get("pessoas") or {}
    if not membros or not pessoas:
        return r
    h = hoje()
    if r.get("pendente") or not r.get("ok", True):
        novos = {pid: g for pid, g in antes.items() if pid in pessoas}
        rede = None
    else:
        try:
            novos, sem, info = gastos(membros, h, rede)
            if sem:
                log("  CMJP: verbas de quem não está na lista oficial de hoje (ficam fora): "
                    + ", ".join(f"{n} ({q} meses)" for n, q in sorted(sem.items())))
            if info["repetidas"]:
                log(f"  CMJP: {info['repetidas']} linha(s) repetida(s) igual(is) na tabela de verbas (contam uma vez)")
        except Exception as erro:  # os gastos são um extra: um erro aqui não derruba a cidade; ficam os de antes
            log(f"  CMJP: verbas indenizatórias: {type(erro).__name__}: {str(erro)[:200]}; ficam as publicadas antes")
            novos = {pid: g for pid, g in antes.items() if pid in pessoas}
    for pid, x in pessoas.items():
        x.pop("id", None)
        g = novos.get(pid)
        x.pop("gastos", None)
        x["fontes"] = [f for f in x.get("fontes") or [] if not (isinstance(f, dict) and f.get("url") == URL)]
        if g:
            x["gastos"] = g
            x["fontes"].append(g["fonte"])
    B.salvar_extras_cidade(IBGE, pessoas, fontes=cidade.get("fontes"), votacoes=cidade.get("votacoes"))
    com = bool(novos)
    notas, notas_en = list(casa.get("notas") or []), list(casa.get("notas_en") or [])
    novo_pt, novo_en = NOTA_COM if com else NOTA_SEM
    for i, n in enumerate(notas):
        if n in (NOTA_COM[0], NOTA_SEM[0]):
            notas[i] = novo_pt
            if i < len(notas_en):
                notas_en[i] = novo_en
            break
    else:
        notas.append(novo_pt)
        notas_en.append(novo_en)
    casa["notas"], casa["notas_en"] = notas, notas_en
    casa.setdefault("cobertura", {})["gastos"] = com
    regional.salvar_casa("camara", IBGE, casa)
    if isinstance(r.get("cobertura"), dict):  # numa rodada pela metade (pendente), o resumo de antes fica como estava
        r["cobertura"]["gastos"] = com
    if com:
        r["vereadoresComGastos"] = sum(1 for pid in novos if pid in pessoas)
    else:
        r.pop("vereadoresComGastos", None)
    if rede is not None:
        r["requisicoes"] = (r.get("requisicoes") or 0) + rede.n
    return r
