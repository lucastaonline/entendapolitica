"""Assembleia Legislativa do Estado de Santa Catarina (Alesc): página oficial dos deputados, o e-Legis (Processo
Legislativo Eletrônico, portalelegis.alesc.sc.gov.br) e os dados abertos do Portal da Transparência.

Lista: página oficial "Deputados" (www.alesc.sc.gov.br/deputados/, legislatura atual): nome, partido, foto, e-mail e
página de cada deputado (40 cadeiras).
Propostas: a lista pública do e-Legis (/proposicoes/processo-legislativo), por tipo (Projeto de Lei, de Lei
Complementar, de Decreto Legislativo, de Resolução e Proposta de Emenda Constitucional), com data de abertura desde
1º/2/2023. Cada item traz número, ementa, data de entrada, autoria (o primeiro é o autor principal), setor e situação
atual. São páginas HTML de 10 itens (não há API aberta): a primeira página de cada tipo é lida todo dia e as outras em
rodízio, no máximo ALESC_PAGINAS páginas por rodada (80), até completar a volta; o que já foi lido fica no cache.
Situação: o texto oficial "Situação atual" com as regras REGRAS. "Arquivado" quase sempre vem depois de a proposta virar
lei; por isso as propostas que terminaram (arquivadas, "Transformado", "Veto Parcial", "Retirado") têm a página de
tramitação lida uma vez (no máximo ALESC_FICHAS por rodada, 100; relida só se a situação mudar): ela diz se virou norma
(com número e link da lei em leis.alesc.sc.gov.br), se foi retirada, vetada ou arquivada depois de parecer contrário.
Gastos: "Despesas dos gabinetes parlamentares" (CSV anual do Portal da Transparência), somadas por ano e tipo de verba.
Inclui diárias e passagens da equipe do gabinete, como a Alesc publica; elas aparecem separadas ("Diárias da equipe",
"Passagens da equipe") das do próprio deputado.
Votações nominais: a Alesc publica a "planilha de votação" de cada sessão em PDF; não entram.
"""
from __future__ import annotations

import csv
import io
import os
import re

import regional
from comum import chave_nome, data_iso, hoje, log, sem_acento

from ._sse_comum import (Rede, bloco_gastos, casar_membros, com_status_en, desde, escopo, fonte, gravar, https,
                         legislatura, membro, nome_lei, partido_sigla, resumo_status, sem_html, virou)

UF = "SC"
SITE = "https://www.alesc.sc.gov.br"
ELEGIS = "https://portalelegis.alesc.sc.gov.br"
TRANSP = "https://transparencia.alesc.sc.gov.br"
VEICULO = "Assembleia Legislativa do Estado de Santa Catarina (Alesc)"
CASA = {"casa": "Assembleia Legislativa do Estado de Santa Catarina", "casa_en": "Legislative Assembly of the State of Santa Catarina",
        "sigla": "Alesc", "site": SITE}
INICIO = legislatura(UF)["inicio"]
TIPOS = {1: ("PL", "PL"), 2: ("PLC", "PLP"), 6: ("PDL", "PDL"), 8: ("PRS", "PRC"), 7: ("PEC", "PEC")}
NOME_GASTOS = ("Despesas do gabinete (inclui diárias e passagens da equipe)", "Office expenses (including staff travel)")

# situação oficial (sem acento, minúsculas) -> status do site; o que não bate aqui segue a tabela comum (comum.py).
# Conferidas à mão no e-Legis (out/2026). "Arquivado" quase sempre vem DEPOIS de virar lei: por isso as propostas
# arquivadas (e as "Transformado", "Veto Parcial", "Retirado") têm a página de tramitação lida uma vez (FICHA).
REGRAS = [
    # "Transformado" = "Transformado em Mensagem de Veto" (veto total ou parcial): só a página de tramitação diz qual
    (r"^transformad[oa]$", "outra"),
    (r"^transformad|resultou (em|n[ao])|sancionad|promulgad|veto parcial", "lei"),
    (r"vetad[oa] total|veto total", "rejeitada"),
    (r"^retirad", "retirada"),
    (r"devolvid[oa] ao autor|prejudicad", "parada"),
    (r"rejeitad|nao aprovad", "rejeitada"),
    (r"arquivad|arquive-se|arquivamento", "arquivada"),
    # "Foi Apensado a este processo" e "Fez Juntada a este processo" = OUTRA proposta veio para esta, que segue andando
    (r"a este processo|documentos anexados|desapensad", "andando"),
    (r"^apensad|anexad[oa] ao processo|tramita(ndo)? em conjunto", "junta"),
    (r"aguardando sancao|enviad[oa] a sancao|remetid[oa] a sancao|autografo|redacao final - providencie|"
     r"publicacao da redacao final", "aprovada"),
    (r"aguardando|em tramitacao|tramitando|comissao|relator|parecer|pauta|leitura|publicacao|protocolad|distribu|diligencia|"
     r"expediente|recebid|em analise|ordem do dia|vista|oficio|encaminhad|devolucao|audiencia publica|deixou de ser apreciad", "andando"),
]
FICHA = re.compile(r"(?i)^\s*(arquivad|arquive-se|aguardando arquivamento|transformad|resultou|veto parcial|retirad)")
NORMA_EV = re.compile(r"(?i)transformad[oa] em|resultou|promulgad")

# ligações com o TSE conferidas à mão: {endereço da página oficial (final): SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], list[str], dict]:
    t = rede.texto(f"{SITE}/deputados/", "deputados.html", 20)
    pessoas = []
    for art in re.findall(r'<article class="lab-card-team.*?</article>', t, flags=re.S):
        url = (re.search(r'href="(https://www\.alesc\.sc\.gov\.br/deputado/[^"]+)"', art) or [None, None])[1]
        nome = sem_html((re.search(r'<h3 class="lab-title-news">(.*?)</h3>', art, re.S) or [None, ""])[1])
        if not url or not nome:
            continue
        sigla = sem_html((re.search(r'<span class="lab-button[^"]*"[^>]*>(.*?)</span>', art, re.S) or [None, ""])[1])
        foto = (re.search(r'<img src="([^"]+)"', art) or [None, None])[1]
        email = (re.search(r"[\w.+-]+@[\w.-]+\.\w+", sem_html(art) or "") or [None])[0]
        pessoas.append({"chave": url.rstrip("/").rsplit("/", 1)[-1], "nome": nome, "nomeCivil": None,
                        "partido": partido_sigla(sigla), "url": url,
                        "foto": re.sub(r"-150x150(\.\w+)$", r"\1", foto) if foto else None, "email": email})
    if not 35 <= len(pessoas) <= 45:
        raise RuntimeError(f"Alesc: a lista oficial veio com {len(pessoas)} pessoas")
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"],
                   p["url"], (cand or {}).get("sit") == "SUPLENTE")
        m["_email"] = p["email"]
        membros.append(m)
    return membros, ids, avisos, casados


def _itens(t: str) -> list[dict]:
    out = []
    for card in re.findall(r'<div class="card card-alesc mb-3">(.*?)</div>\s*</div>\s*(?=<div class="card card-alesc|<div class="d-flex)', t, flags=re.S):
        a = re.search(r'<h4 class="card-title">\s*<a href="/proposicoes/([^"]+)">(.*?)</a>', card, re.S)
        if not a:
            continue
        campos = {sem_html(k): v for k, v in re.findall(r'fw-bold[^"]*">(.*?)</div>\s*<div class="col-lg-10">(.*?)</div>', card, re.S)}
        out.append({"id": a.group(1), "sigla": sem_html(a.group(2)),
                    "ementa": sem_html((re.search(r'<p class="mb-1 fst-italic"[^>]*>(.*?)</p>', card, re.S) or [None, ""])[1]),
                    "entrada": data_iso(sem_html(campos.get("Entrada"))),
                    "autores": [sem_html(x) for x in re.findall(r"<li>(.*?)</li>", campos.get("Autoria") or "", re.S)],
                    "setor": sem_html(campos.get("Setor atual")), "situacao": sem_html(campos.get("Situação atual"))})
    return out


def _proposicoes(rede: Rede) -> dict[str, dict]:
    """Junta, no cache (estado.json), o que já foi lido do e-Legis; lê a 1ª página de cada tipo e um rodízio das outras
    (o limite de páginas por rodada é dividido entre os tipos, na proporção do tamanho de cada um)."""
    est = rede.estado("estado.json", {}) or {}
    itens, cursor = est.get("itens", {}), est.get("cursor", {})
    limite = int(os.environ.get("ALESC_PAGINAS", "80"))
    bases, paginas = {}, {}
    for cod in TIPOS:
        bases[cod] = f"{ELEGIS}/proposicoes/processo-legislativo?tipoPropositura={cod}&inicio={INICIO}&arquivados=1"
        t = rede.texto(bases[cod], None)
        for x in _itens(t):
            itens[x["id"]] = dict(x, tipo=cod)
        paginas[cod] = max([int(p) for p in re.findall(r"page=(\d+)", t)] or [1])
    soma = sum(p - 1 for p in paginas.values()) or 1
    for cod, (sig, _) in TIPOS.items():
        if paginas[cod] < 2:
            continue
        cota = max(1, round((limite - len(TIPOS)) * (paginas[cod] - 1) / soma))
        pagina = int(cursor.get(str(cod), 2))
        for _ in range(min(cota, paginas[cod] - 1)):
            if pagina > paginas[cod]:
                pagina = 2
            for x in _itens(rede.texto(f"{bases[cod]}&page={pagina}", None)):
                itens[x["id"]] = dict(x, tipo=cod)
            pagina += 1
        cursor[str(cod)] = pagina if pagina <= paginas[cod] else 2
    rede.guardar({"itens": itens, "cursor": cursor}, "estado.json")
    return itens


def _gastos(rede: Rede, quem) -> dict[str, list]:
    """{chave do deputado: [(mês, verba, valor)]} pelos CSV anuais de despesas dos gabinetes. A coluna "Conta" traz o
    nome do deputado, às vezes o civil sem uma parte ("Ana Caroline Campagnolo") ou com o apelido entre parênteses
    ("Ana Paula da Silva (Paulinha)"): quem(nome) resolve (só quando há um único deputado possível)."""
    out: dict[str, list] = {}
    atual = int(hoje()[:4])
    achados: dict[str, str | None] = {}
    for ano in range(int(INICIO[:4]), atual + 1):
        b = rede.bruto(f"{TRANSP}/gabinetes-parlamentares/csv/{ano}", f"gabinetes-{ano}.csv", 70 if ano == atual else 24 * 7)
        for r in csv.DictReader(io.StringIO(b.decode("utf-8-sig", "replace")), delimiter=";"):
            conta = (r.get("Conta") or "").strip()
            if conta not in achados:
                apelido = re.search(r"\(([^)]+)\)", conta)
                achados[conta] = (quem(apelido.group(1)) if apelido else None) or quem(re.sub(r"\s*\(.*?\)\s*", " ", conta))
            k = achados[conta]
            if not k:
                continue
            try:
                v = float((r.get("Valor") or "0").replace(".", "").replace(",", "."))
            except ValueError:
                continue
            mes = (data_iso(r.get("Data de Referência")) or "")[:7]
            verba = (r.get("Verba") or "Outros").strip()
            verba = verba[:1] + verba[1:].lower()
            if re.search(r"(?i)funcion", r.get("Descrição") or ""):  # diárias e passagens da equipe, separadas das do deputado
                verba += " da equipe"
            if mes and v:
                out.setdefault(k, []).append((mes, verba, v))
    return out


def _ficha(rede: Rede, pid: str, situacao: str | None) -> dict:
    """Página de tramitação de uma proposta: o campo "Informações" e os eventos que contam o fim da história
    (virou norma, veto, retirada, rejeição). Guarda só o resumo, não a página."""
    t = rede.texto(f"{ELEGIS}/proposicoes/{pid}", None)
    if "timeline-item" not in t:
        raise RuntimeError(f"Alesc: página de tramitação sem eventos ({pid})")
    ev = []
    for li in re.findall(r'<li class="timeline-item[^"]*">(.*?)</li>', t, re.S):
        sit = sem_html((re.search(r'<p class="mb-1 fw-bold">(.*?)</p>', li, re.S) or [None, ""])[1])
        if not sit:
            continue
        info = sem_html((re.search(r'<p class="mb-1 text-primary fst-italic">(.*?)</p>', li, re.S) or [None, ""])[1])
        url = next((u for u, n in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
                    if re.search(r"(?i)^\s*(lei|resolu|emenda|decreto)", sem_html(n) or "")), None)
        ev.append({"s": sit, "d": data_iso(sem_html((re.search(r'<p class="mb-1 text-muted">(.*?)</p>', li, re.S) or [None, ""])[1])),
                   "i": info, "u": url})
    importantes = [e for e in ev if NORMA_EV.search(e["s"]) or re.search(r"(?i)veto|retirad|rejeitad|prejudicad|devolvid|"
                                                                          r"arquiv|parecer contr", e["s"] + " " + (e["i"] or ""))]
    return {"sit": situacao, "info": sem_html((re.search(r"<th>Informações</th>\s*<td>(.*?)</td>", t, re.S) or [None, ""])[1]),
            "ev": importantes[-12:]}


def _fichas(rede: Rede, itens: dict[str, dict], precisa: list[str]) -> dict[str, dict]:
    """Lê (uma vez) a tramitação das propostas que já terminaram; relê só se a situação mudar. No máximo ALESC_FICHAS
    páginas por rodada (100): o resto fica para as próximas."""
    fichas = rede.estado("fichas.json", {}) or {}
    falta = [i for i in precisa if (fichas.get(i) or {}).get("sit") != itens[i].get("situacao")]
    limite = int(os.environ.get("ALESC_FICHAS", "100"))
    lidas = 0
    for i in falta[:limite]:
        try:
            fichas[i] = _ficha(rede, i, itens[i].get("situacao"))
            lidas += 1
        except Exception as e:  # noqa: BLE001 - uma página com problema não derruba a coleta
            log(f"  SC: tramitação de {i} não veio ({e})")
        if lidas and lidas % 50 == 0:
            rede.guardar(fichas, "fichas.json")
    rede.guardar(fichas, "fichas.json")
    if len(falta) > limite:
        log(f"  SC: {len(falta) - limite} páginas de tramitação ficam para as próximas rodadas")
    return fichas


def _desfecho(f: dict) -> tuple[str | None, dict | None, str | None, str | None]:
    """(status, norma {nome, url}, data, motivo) a partir da ficha; status None se ela não disser nada além da lista.
    motivo "veto" = vetada por inteiro; "parecer" = arquivada depois de parecer contrário de comissão comunicado na
    Ordem do Dia."""
    ev = f.get("ev") or []
    for e in ev:
        norma_ev = bool(NORMA_EV.search(e["s"]))
        # "Transformado" sozinho = "Transformado em Mensagem de Veto"; às vezes a mesma linha traz a lei (veto parcial)
        if not norma_ev and not (re.match(r"(?i)transformad", e["s"]) and re.search(r"(?i)\blei\b", e.get("i") or "")):
            continue
        m = re.search(r"(?i)\b(lei complementar|lei|resolu[cç][aã]o|emenda constitucional|decreto legislativo)\s+"
                      r"(?:n[º°o.]\s*)?([\d.]+)\s*,?\s*(?:de\s+)?\d{1,2}º?/\d{1,2}/(\d{4}|\d{2})\b", e.get("i") or "")
        if m:
            tipo, ano = m.group(1).strip(), m.group(3)
            ano = ano if len(ano) == 4 else "20" + ano
            return "lei", {"nome": nome_lei(tipo[:1].upper() + tipo[1:], int(m.group(2).replace(".", "")), ano),
                           "url": https(e.get("u")),
                           "parcial": bool(re.search(r"(?i)mensagem de veto", e.get("i") or ""))}, e.get("d"), None
        if norma_ev:
            return "lei", None, e.get("d"), None
    ult = " | ".join(sem_acento((e["s"] + " " + (e["i"] or "")).lower()) for e in ev[-4:])
    if re.search(r"(?:^|\| )retirad[oa]\b(?! de pauta| da pauta| da ordem)|retirad[oa] de tramitacao|retirad[oa] pelo autor|"
                 r"retirad[oa] a pedido|a pedido do autor", ult):
        return "retirada", None, None, None
    if re.search(r"mantid[oa] o veto|veto mantido|veto total", ult) and not re.search(r"veto (rejeitado|derrubado)|rejeitado o veto", ult):
        return "rejeitada", None, None, "veto"
    if re.search(r"rejeitad", re.sub(r"parecer contrario rejeitad[oa]", "", ult)):  # parecer contrário rejeitado = bom para ela
        return "rejeitada", None, None, None
    if re.search(r"comunicad[oa] .{0,25}parecer contrario", ult) and not re.search(r"desarquivad", ult):
        return "rejeitada", None, None, "parecer"
    if re.search(r"prejudicad|devolvid[oa] ao autor", ult):
        return "parada", None, None, None
    return None, None, None, None


def coletar() -> dict:
    rede = Rede("alesc", pausa=1.0)
    membros, ids, avisos, casados = _membros(rede)
    for a in avisos:
        log(f"  SC: {a}")
    itens = _proposicoes(rede)
    hj = hoje()
    por_nome: dict[str, str] = {}
    for k, pid in ids.items():
        m = next(x for x in membros if x["id"] == pid)
        por_nome[chave_nome(m["nome"])] = k
        c = casados.get(k)
        if c:
            por_nome.setdefault(chave_nome(c["nome"]), k)
            por_nome.setdefault(chave_nome(c["urna"]), k)

    def quem(nome: str) -> str | None:
        n = re.sub(r"(?i)^\s*deputad[oa]\s+", "", nome or "")
        n = re.sub(r"\s*\(.*?\)\s*", " ", n).strip()
        k = por_nome.get(chave_nome(n))
        if k:
            return k
        pa = set(regional.palavras(n))
        achados = {c for nn, c in por_nome.items() if pa and len(pa) >= 2 and (pa <= set(regional.palavras(nn)))}
        return achados.pop() if len(achados) == 1 else None

    por_dep: dict[str, list] = {}
    ligados: dict[str, list[str]] = {}
    for x in itens.values():
        if (x.get("entrada") or "") < INICIO:
            continue
        autores = [k for k in dict.fromkeys(quem(a) for a in x.get("autores") or []) if k]
        if autores:
            ligados[x["id"]] = autores
    fichas = _fichas(rede, itens, sorted((i for i in ligados if FICHA.search(itens[i].get("situacao") or "")),
                                         key=lambda i: itens[i].get("entrada") or "", reverse=True))
    for i, autores in ligados.items():
        x = itens[i]
        principal = quem((x.get("autores") or [""])[0])
        sig, tipo = TIPOS[int(x["tipo"])]
        m = re.search(r"(\d+)/(\d{4})", x.get("sigla") or "")
        sigla = f"{sig} {int(m.group(1))}/{m.group(2)}" if m else (x.get("sigla") or sig)
        f = fichas.get(i) if FICHA.search(x.get("situacao") or "") else None
        st, norma, dst, motivo = _desfecho(f) if f and f.get("sit") == x.get("situacao") else (None, None, None, None)
        for k in autores:
            p = regional.proposta(f"alesc:{x['id']}", sigla, tipo, x.get("entrada"), x.get("ementa"), x.get("situacao"),
                                  f"{ELEGIS}/proposicoes/{x['id']}", papel="autor" if k == principal else "coautor", regras=REGRAS,
                                  status=st, data_status=dst)
            if norma:
                parcial = norma.get("parcial") or re.search(r"(?i)veto parcial", x.get("situacao") or "") or any(
                    re.search(r"(?i)veto parcial", e["s"]) for e in (f or {}).get("ev") or [])
                virou(p, norma["nome"] + (" (com partes vetadas)" if parcial else ""), norma["url"])
                p["lei"]["nome"] = norma["nome"]
            elif p["status"] == "lei":
                com_status_en(p, "Virou lei (a página oficial ainda não mostra o número)",
                              "Became law (the official page does not show the number yet)")
            elif motivo == "veto" or (p["status"] == "rejeitada" and re.match(r"(?i)veto total", x.get("situacao") or "")):
                com_status_en(p, "Aprovada pela Assembleia, mas vetada por inteiro pelo governador",
                              "Approved by the Assembly, but fully vetoed by the governor")
            elif motivo == "parecer":
                com_status_en(p, "Rejeitada numa comissão (parecer contrário) e arquivada",
                              "Rejected in a committee (unfavorable opinion) and archived")
            elif p["status"] == "aprovada":
                com_status_en(p, "Aprovada pela Assembleia; segue para a sanção ou o veto do governador",
                              "Approved by the Assembly; it goes to the governor to sign or veto")
            por_dep.setdefault(k, []).append(p)
    gastos = _gastos(rede, quem)
    f_lista = fonte(VEICULO, "Deputados da legislatura atual (página oficial)", f"{SITE}/deputados/", hj)
    f_prop = fonte(VEICULO, "e-Legis: processo legislativo eletrônico (lista de proposições)", f"{ELEGIS}/proposicoes/processo-legislativo", hj)
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"))
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        x: dict = {"links": {"oficial": m["url"], "email": m.pop("_email", None), "redes": []},
                   "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                   "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da Alesc", m["url"], hj)]}
        g = bloco_gastos(gastos.get(k) or [], [
            fonte(VEICULO, "Portal da Transparência: despesas dos gabinetes parlamentares", f"{TRANSP}/gabinetes-parlamentares", hj),
            fonte(VEICULO, "Dados abertos: despesas dos gabinetes parlamentares (CSV anual)",
                  f"{TRANSP}/gabinetes-parlamentares/dados-abertos", hj)], inicio=INICIO, nome=NOME_GASTOS)
        if g:
            x["gastos"] = g
        extras[m["id"]] = x
    log(f"  SC: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    notas = [("A Alesc publica o voto de cada deputado só em planilhas PDF de cada sessão; as votações não entram.",
              "The Alesc only publishes each deputy's vote in PDF spreadsheets for each session; votes are not included."),
             ("Os gastos são as despesas de cada gabinete que a Alesc publica (diárias, passagens, telefone, veículos, aluguel e "
              "outras), inclusive as diárias e passagens da equipe, que aparecem separadas.",
              "Spending is each office's expenses as published by the Alesc (per diems, tickets, phone, vehicles, rent and "
              "others), including staff per diems and tickets, which are shown separately.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": True},
                  f_lista, esc_pt, esc_en, notas)
