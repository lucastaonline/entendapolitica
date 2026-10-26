"""Assembleia Legislativa do Estado de Santa Catarina (Alesc): página oficial dos deputados, o e-Legis (Processo
Legislativo Eletrônico, portalelegis.alesc.sc.gov.br) e os dados abertos do Portal da Transparência.

Lista: página oficial "Deputados" (www.alesc.sc.gov.br/deputados/, legislatura atual): nome, partido, foto, e-mail e
página de cada deputado (40 cadeiras).
Propostas: a lista pública do e-Legis (/proposicoes/processo-legislativo), por tipo (Projeto de Lei, de Lei
Complementar, de Decreto Legislativo, de Resolução e Proposta de Emenda Constitucional), com data de abertura desde
1º/2/2023. Cada item traz número, ementa, data de entrada, autoria (o primeiro é o autor principal), setor e situação
atual. São páginas HTML de 10 itens (não há API aberta): a primeira página de cada tipo é lida todo dia e as outras em
rodízio, no máximo ALESC_PAGINAS páginas por rodada (80), até completar a volta; o que já foi lido fica no cache.
Primeira carga (cache vazio, como no robô do GitHub): as listas e as páginas de tramitação usam a rodada toda
(_carga.py) e, enquanto não terminam, nada é gravado em dados/ (ficam os arquivos de antes; "em andamento").
Situação: o texto oficial "Situação atual" com as regras REGRAS. "Arquivado" quase sempre vem depois de a proposta virar
lei; por isso as propostas que terminaram (arquivadas, "Transformado", "Veto Parcial", "Retirado") têm a página de
tramitação lida uma vez (no máximo ALESC_FICHAS por rodada, 100; relida só se a situação mudar): ela diz se virou norma
(com número e link da lei em leis.alesc.sc.gov.br), se foi retirada, vetada ou arquivada depois de parecer contrário.
Gastos: "Despesas dos gabinetes parlamentares" (CSV anual do Portal da Transparência), somadas por ano e tipo de verba.
Inclui diárias e passagens da equipe do gabinete, como a Alesc publica; elas aparecem separadas ("Diárias da equipe",
"Passagens da equipe") das do próprio deputado.
Votações nominais do Plenário, desde o começo da legislatura (_votacoes): no e-Legis, a lista de sessões plenárias
(/sessoes-plenarias, ordinárias e extraordinárias, 10 por página), a Ordem do Dia de cada sessão
(/sessoes-plenarias/<id>/ordem-do-dia: cada proposição votada, o selo do resultado e, nas votações nominais, o botão
"Extrato de votação") e o extrato (/extrato-votacao/<id>, um pedaço de página que a Ordem do Dia busca com o cabeçalho
X-Requested-With, como o htmx da própria página faz): o nome e o voto (Sim, Não, Abstenção) de cada deputado que votou,
sem partido nem totais; o placar é a soma (conferido com as atas das sessões, em PDF, que trazem a chamada nominal). O
extrato também diz a fase (turno, redação final, votação em separado, parecer de comissão), que entra na descrição. Os
nomes são ligados aos deputados de hoje (_votos_gastos.Nomes; quem saiu da Casa fica fora). Primeira carga (63
páginas, ~630 Ordens do Dia e os extratos, ~920 pedidos): o tempo que sobrar na rodada, com o progresso em
.cache/alesc-votos/; até terminar, os perfis ficam com o bloco de antes. Depois (no máximo ALESC_VOTOS_SEGUNDOS por
rodada, 300): a 1ª página da lista, a Ordem do Dia das sessões dos últimos RELER_DIAS dias (o resultado pode ser
lançado depois) e os extratos novos.
O governo do estado (perfil do governador, dados/pessoas/gov-SC.json), desde o começo do mandato: os projetos de
iniciativa do Governador no e-Legis (PL, PLC e PEC; as medidas provisórias não entram, porque viram projetos de
conversão com outro número); as leis pela pesquisa da Legislação SC (leis.alesc.sc.gov.br, total por tipo e data); e
os vetos pelas mensagens de veto (MSV, tipoPropositura=10), com "Veto Total" ou "Veto Parcial" na ementa.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import time
import urllib.parse

import mandatos
import regional
from comum import chave_nome, data_iso, hoje, log, sem_acento

from . import _carga
from ._sse_comum import (Rede, SemTempo, bloco_executivo, bloco_gastos, casar_membros, com_status_en, desde, escopo,
                         escopo_governo, fonte, gravar, gravar_governo, https, legislatura, membro, nome_lei, partido_sigla,
                         periodo_governo, qtd, resumo_status, sem_html, virou)
from ._votos_gastos import Nomes, aplicar, bloco_votacoes, escopo_votos, item_voto, placar

UF = "SC"
SITE = "https://www.alesc.sc.gov.br"
ELEGIS = "https://portalelegis.alesc.sc.gov.br"
TRANSP = "https://transparencia.alesc.sc.gov.br"
VEICULO = "Assembleia Legislativa do Estado de Santa Catarina (Alesc)"
CASA = {"casa": "Assembleia Legislativa do Estado de Santa Catarina", "casa_en": "Legislative Assembly of the State of Santa Catarina",
        "sigla": "Alesc", "site": SITE,
        "sic": "https://www.alesc.sc.gov.br/sic/"}  # pedido de informação (Lei de Acesso à Informação)
INICIO = legislatura(UF)["inicio"]
TIPOS = {1: ("PL", "PL"), 2: ("PLC", "PLP"), 6: ("PDL", "PDL"), 8: ("PRS", "PRC"), 7: ("PEC", "PEC")}
LEIS = "https://leis.alesc.sc.gov.br"  # Legislação SC, mantida pela Alesc
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

# votações nominais (e-Legis: sessões plenárias)
VOTOS_CACHE = "alesc-votos"  # pasta própria em .cache/
VOTOS_SEGUNDOS = float(os.environ.get("ALESC_VOTOS_SEGUNDOS", "300"))  # limite de cada rodada depois da primeira carga
RELER_DIAS = 15  # a Ordem do Dia das sessões dos últimos 15 dias é relida (o resultado pode ser lançado depois)
VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "obstrucao": "Obstrução"}
# o extrato é um pedaço de página que a própria Ordem do Dia busca com este cabeçalho (htmx, extensão "ajax-header");
# sem ele, o e-Legis responde 405
AJAX = {"X-Requested-With": "XMLHttpRequest"}
# nome como o extrato de votação escreve -> id da pessoa (ou "-": sem ligação), conferido à mão. Em out/2026 os 39
# deputados de hoje com voto em extrato batem sozinhos (mesmo nome da página "Deputados"); os 18 nomes sem ligação são de
# quem saiu da Casa ou se licenciou (Marquito, Emerson Stein, Massocco, Delegado Egidio, Soratto, ...).
VOTOS_MANUAL: dict[str, str] = {}


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


def _proposicoes(rede: Rede) -> tuple[dict[str, dict], bool]:
    """Junta, no cache (estado.json), o que já foi lido do e-Legis; lê a 1ª página de cada tipo e um rodízio das outras
    (o limite de páginas por rodada é dividido entre os tipos, na proporção do tamanho de cada um). Devolve (itens,
    completo): completo quando todas as páginas de cada tipo já foram lidas pelo menos uma vez. Na primeira carga (cache
    vazio, como no robô do GitHub), o rodízio usa a rodada toda (_carga.py) em vez do limite de páginas."""
    est = rede.estado("estado.json", {}) or {}
    itens, cursor = est.get("itens", {}), est.get("cursor", {})
    volta = set(est.get("volta") or [])  # tipos com todas as páginas já lidas
    limite = int(os.environ.get("ALESC_PAGINAS", "80"))
    bases, paginas = {}, {}
    t0 = time.time()
    try:
        for cod in TIPOS:
            bases[cod] = f"{ELEGIS}/proposicoes/processo-legislativo?tipoPropositura={cod}&inicio={INICIO}&arquivados=1"
            t = rede.texto(bases[cod], None)
            for x in _itens(t):
                itens[x["id"]] = dict(x, tipo=cod)
            paginas[cod] = max([int(p) for p in re.findall(r"page=(\d+)", t)] or [1])
            n = sum(1 for x in itens.values() if int(x["tipo"]) == cod)
            if paginas[cod] < 2 or n >= (paginas[cod] - 1) * 10:  # cache de antes desta regra: já tem (quase) tudo
                volta.add(cod)
        primeira = any(cod not in volta for cod in TIPOS)
        prazo = _carga.limite_diario(0, primeira)  # na primeira carga, a rodada toda; senão, o limite de páginas
        soma = sum(p - 1 for p in paginas.values()) or 1
        for cod, (sig, _) in TIPOS.items():
            if paginas[cod] < 2:
                continue
            cota = max(1, round((limite - len(TIPOS)) * (paginas[cod] - 1) / soma))
            if primeira:
                cota = paginas[cod] - 1 if cod not in volta else min(cota, paginas[cod] - 1)
            pagina = int(cursor.get(str(cod), 2))
            ja_completo = cod in volta
            for _ in range(min(cota, paginas[cod] - 1)):
                if primeira and time.time() - t0 > prazo:
                    break
                if pagina > paginas[cod]:
                    pagina = 2
                for x in _itens(rede.texto(f"{bases[cod]}&page={pagina}", None)):
                    itens[x["id"]] = dict(x, tipo=cod)
                pagina += 1
                if pagina > paginas[cod]:
                    volta.add(cod)
                    if not ja_completo:  # primeira volta completa deste tipo: as páginas do começo já foram lidas antes
                        break
                if primeira and pagina % 20 == 0:
                    rede.guardar({"itens": itens, "cursor": dict(cursor, **{str(cod): pagina}), "volta": sorted(volta)}, "estado.json")
            cursor[str(cod)] = pagina if pagina <= paginas[cod] else 2
    except SemTempo:  # o fim da rodada chegou: o cursor guarda onde parou
        pass
    rede.guardar({"itens": itens, "cursor": cursor, "volta": sorted(volta)}, "estado.json")
    return itens, all(cod in volta for cod in TIPOS)


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


def _fichas(rede: Rede, itens: dict[str, dict], precisa: list[str]) -> tuple[dict[str, dict], int]:
    """Lê (uma vez) a tramitação das propostas que já terminaram; relê só se a situação mudar. No máximo ALESC_FICHAS
    páginas por rodada (100): o resto fica para as próximas. Na primeira carga (mais do que isso por ler, como no robô
    que começa com o cache vazio), até o fim da rodada (_carga.py). Devolve (fichas, quantas faltam)."""
    fichas = rede.estado("fichas.json", {}) or {}
    falta = [i for i in precisa if (fichas.get(i) or {}).get("sit") != itens[i].get("situacao")]
    limite = int(os.environ.get("ALESC_FICHAS", "100"))
    primeira = len(falta) > limite
    prazo, t0 = _carga.limite_diario(0, primeira), time.time()
    lidas = 0
    for i in (falta if primeira else falta[:limite]):
        if primeira and time.time() - t0 > prazo:
            break
        try:
            fichas[i] = _ficha(rede, i, itens[i].get("situacao"))
            lidas += 1
        except SemTempo:
            break
        except Exception as e:  # noqa: BLE001 - uma página com problema não derruba a coleta
            log(f"  SC: tramitação de {i} não veio ({e})")
        if lidas and lidas % 50 == 0:
            rede.guardar(fichas, "fichas.json")
    rede.guardar(fichas, "fichas.json")
    resto = sum(1 for i in precisa if (fichas.get(i) or {}).get("sit") != itens[i].get("situacao"))
    if resto:
        log(f"  SC: {resto} páginas de tramitação ficam para as próximas rodadas")
    return fichas, resto


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


def _vetos(rede: Rede, ini: str) -> list[dict]:
    """Mensagens de veto do governador (MSV) no e-Legis, todas as páginas: a primeira todo dia; as outras, a cada semana
    ou quando a primeira muda (uma mensagem nova empurra as outras uma posição para trás, de página em página)."""
    base = f"{ELEGIS}/proposicoes/processo-legislativo?tipoPropositura=10&inicio={ini}&arquivados=1"
    t = rede.texto(base, "vetos-1.html", 20)
    out = {x["id"]: x for x in _itens(t)}
    est = rede.estado("vetos.json", {}) or {}
    mudou = est.get("p1") != list(out)
    paginas = max([int(p) for p in re.findall(r"page=(\d+)", t)] or [1])
    for pg in range(2, paginas + 1):
        for x in _itens(rede.texto(f"{base}&page={pg}", f"vetos-{pg}.html", 0 if mudou else 24 * 7)):
            out.setdefault(x["id"], x)
    rede.guardar({"p1": [x["id"] for x in _itens(t)]}, "vetos.json")
    return list(out.values())


def _leis(rede: Rede, ini: str) -> tuple[dict[str, int], str | None]:
    """Leis ordinárias e complementares assinadas de ini até hoje, pela pesquisa oficial da Legislação SC
    (leis.alesc.sc.gov.br: "Foram encontrados N resultados"), e a data da mais recente."""
    total, ultima = {}, None
    for tipo in ("Lei Ordinária", "Lei Complementar"):
        t = rede.texto(f"{LEIS}/legislativo?tipo_ato_normativo={urllib.parse.quote(tipo)}&data_inicial={ini}"
                       f"&data_final={hoje()}&sort=data_desc", f"leis-{tipo[4:7].lower()}.html", 20)
        m = re.search(r'totalItems\\?":(\d+)', t)
        if not m:
            raise RuntimeError(f"Alesc: a pesquisa de leis ({tipo}) não trouxe o total")
        total[tipo] = int(m.group(1))
        datas = re.findall(r'data-ato-normativo\\?":\\?"(\d{4}-\d{2}-\d{2})', t)
        if datas:
            ultima = max([ultima or ""] + datas)
    return total, ultima


# ---------------------------------------------------------------- votações nominais (e-Legis: sessões plenárias)
def _lista_sessoes(t: str) -> tuple[list[dict], int | None, int]:
    """Uma página da lista de sessões plenárias do e-Legis (10 por página, da mais nova para a mais antiga):
    ([{"id", "t" (nome), "d" (data), "s" (situação)}], total de sessões que a lista mostra, última página)."""
    out = []
    for card in t.split('<div class="card card-alesc mb-4">')[1:]:
        sid = re.search(r'href="/sessoes-plenarias/([A-Za-z0-9]+)/', card)
        dia = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", card)
        if sid and dia:
            out.append({"id": sid.group(1), "t": sem_html((re.search(r"<h4[^>]*>(.*?)</h4>", card, re.S) or [None, ""])[1]),
                        "d": data_iso(dia.group(1)),
                        "s": sem_html((re.search(r'<span class="badge[^"]*">(.*?)</span>', card, re.S) or [None, ""])[1])})
    total = re.search(r"Exibindo\s+[\d.]+\s*-\s*[\d.]+\s+de\s+([\d.]+)", t)
    ultima = max([int(p) for p in re.findall(r"page=(\d+)", t)] or [1])
    return out, (int(total.group(1).replace(".", "")) if total else None), ultima


def _ordem_do_dia(t: str) -> dict:
    """A Ordem do Dia de uma sessão: data e situação (cabeçalho) e as proposições com "Extrato de votação" (as votações
    nominais): {"x": [extratos], "pid": id da proposição, "p": rótulo ("MSV/1424/2022"), "r": selo do resultado
    ("Aprovado"), "n": selo "Votação nominal", "e": ementa}."""
    cab = {sem_html(k): sem_html(v) for k, v in re.findall(r"<th>(.*?)</th>\s*<td>(.*?)</td>", t, re.S)}
    if not cab.get("Início"):
        raise RuntimeError("Alesc: a Ordem do Dia veio sem o cabeçalho da sessão")
    itens = []
    for bloco in t.split("<footer", 1)[0].split('<div class="border-bottom mb-3">')[1:]:
        ext = list(dict.fromkeys(re.findall(r'hx-get="/extrato-votacao/([A-Za-z0-9]+)"', bloco)))
        if not ext:
            continue
        a = re.search(r'<a href="/proposicoes/([A-Za-z0-9]+)">(.*?)</a>', bloco, re.S)
        selos = [sem_html(x) or "" for x in re.findall(r'<span class="badge[^"]*">(.*?)</span>', bloco, re.S)]
        itens.append({"x": ext, "pid": a.group(1) if a else None, "p": sem_html(a.group(2)) if a else None,
                      "r": next((s for s in selos if s and not re.match(r"(?i)vota", s)), None),
                      "n": any(re.search(r"(?i)nominal", s) for s in selos),
                      "e": sem_html((re.search(r'<p class="fst-italic[^"]*">(.*?)</p>', bloco, re.S) or [None, ""])[1])})
    return {"d": data_iso(cab.get("Início")), "s": cab.get("Situação"), "v": itens}


def _extrato(t: str) -> dict:
    """O extrato de uma votação nominal: rótulo da proposição ("c"), fase ("f") e [nome, voto] de cada deputado que
    votou ("v"; só quem votou aparece, sem partido nem totais: o placar é a soma)."""
    if re.search(r"(?i)<html|<!doctype", t[:3000]):
        raise RuntimeError("Alesc: o extrato de votação veio como página inteira (formato diferente)")
    votos = [[sem_html(n) or "", sem_html(v) or ""] for n, v in re.findall(
        r'<div class="d-flex justify-content-between[^"]*">\s*<div>(.*?)</div>\s*<div>\s*<span class="badge[^"]*">(.*?)</span>',
        t, re.S)]
    if len(votos) != t.count('class="border rounded'):
        raise RuntimeError("Alesc: o extrato de votação veio num formato diferente")
    return {"c": sem_html((re.search(r"<h4[^>]*>(.*?)</h4>", t, re.S) or [None, ""])[1]),
            "f": sem_html((re.search(r"<h5[^>]*>(.*?)</h5>", t, re.S) or [None, ""])[1]), "v": votos}


def _voto(txt: str) -> str:
    t = (txt or "").strip()
    return VOTO.get(sem_acento(t).lower(), t or "NR")


def _rotulo(r: str | None) -> str | None:
    """'MSV/1424/2022' -> 'MSV 1424/2022'; 'PL./0096/2023' -> 'PL 96/2023' (como na lista de propostas)."""
    m = re.match(r"\s*([A-Za-z]+)\W*?0*(\d+)\s*/\s*(\d{4})\s*$", r or "")
    return f"{m.group(1).upper()} {int(m.group(2))}/{m.group(3)}" if m else r


def _fase(f: str | None) -> str:
    """Fase do extrato ("Aguardando Discussão e Votação em 2º Turno") -> "discussao e votacao em 2º turno"."""
    return re.sub(r"^aguardando\s+", "", sem_acento(f or "").lower().strip())


def _descricao(ementa: str | None, proposta: str | None, fase: str, resultado: str | None, turno: bool,
               sessao: str | None = None) -> str | None:
    """A ementa oficial e, quando o extrato diz, a fase que foi votada, entre parênteses e com as palavras do extrato: o
    turno (se não houver dúvida: turno=False quando a mesma proposição tem outra votação com a mesma fase; aí entra o nome
    da sessão, para separar as duas), a redação final, a votação em separado ou o parecer de comissão. O que quer dizer cada
    voto nos vetos e nos pareceres (como a Presidência anuncia na sessão, nas atas) fica no escopo do bloco, em português e
    em inglês (VOTOS_EXPLICA)."""
    e = (ementa or "").strip()
    partes = [e if not e or re.search(r"[.!?;:]$", e) else e + "."]
    m = re.search(r"\b([12])º turno\b", fase)
    if "votacao do parecer" in fase:
        partes.append("(Votação do parecer de comissão.)")
    elif "redacao final" in fase:
        partes.append("(Redação final.)")
    elif "em separado" in fase:
        if not re.search(r"(?i)em separado", e):
            partes.append("(Votação em separado.)")
    elif m and turno:
        partes.append(f"({m.group(1)}º turno.)")
    elif m and sessao:
        partes.append(f"({sessao}.)")
    return " ".join(p for p in partes if p) or None


# o que quer dizer cada voto nas votações de veto (MSV) e de parecer de comissão, como a Presidência anuncia (atas)
VOTOS_EXPLICA = ("Nas votações de veto, quem vota “sim” mantém o veto e quem vota “não” o derruba; nas votações do parecer de "
                 "uma comissão, “sim” aprova o parecer e “não” o rejeita",
                 "In votes on a veto, a “yes” vote keeps the veto and a “no” vote overturns it; in votes on a committee's "
                 "opinion, “yes” approves the opinion and “no” rejects it")


def _votacoes(rede: Rede, membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "votacoes"} com as votações nominais do Plenário desde o começo da legislatura, pelo e-Legis:
    a lista de sessões plenárias (/sessoes-plenarias?page=N, ordinárias e extraordinárias), a Ordem do Dia de cada
    sessão (/sessoes-plenarias/<id>/ordem-do-dia: cada proposição, o selo do resultado e o botão "Extrato de votação" nas
    nominais) e o extrato de cada votação (/extrato-votacao/<id>: nome e voto de cada deputado que votou). Primeira carga
    (cache vazio): todas as páginas da lista, todas as Ordens do Dia e todos os extratos, com o tempo que sobrar na rodada
    (_carga.py); até terminar, devolve None e cada perfil fica com o bloco de antes (nada pela metade). Depois: a 1ª
    página da lista (e as seguintes enquanto aparecer sessão nova), a Ordem do Dia das sessões dos últimos RELER_DIAS dias
    (o resultado pode ser lançado depois) e os extratos novos."""
    rv = Rede(VOTOS_CACHE, pausa=1.0)
    rv._ult, rv._robots = rede._ult, rede._robots  # o mesmo servidor das propostas: a mesma pausa e o robots.txt lido uma vez
    est = rv.estado("estado.json", {}) or {}
    sessoes, odias, extratos = est.get("sessoes") or {}, est.get("odia") or {}, est.get("extratos") or {}
    volta, cursor, completa = bool(est.get("volta")), int(est.get("cursor") or 1), bool(est.get("completa"))
    hj = hoje()
    recente = (dt.date.fromisoformat(hj) - dt.timedelta(days=RELER_DIAS)).isoformat()
    prazo, t0 = _carga.limite_diario(VOTOS_SEGUNDOS, not completa), time.time()
    novos = [0]

    def guardar() -> None:
        rv.guardar({"sessoes": sessoes, "odia": odias, "extratos": extratos, "volta": volta, "cursor": cursor,
                    "completa": completa}, "estado.json")

    def antes_de_pedir() -> None:
        if time.time() - t0 >= prazo:
            raise SemTempo("acabou o limite de tempo das votações nesta rodada")
        novos[0] += 1
        if novos[0] % 25 == 0:
            guardar()

    def pagina(n: int) -> tuple[int, int | None, int]:
        antes_de_pedir()
        lst, total, ultima = _lista_sessoes(rv.texto(f"{ELEGIS}/sessoes-plenarias?page={n}", None))
        if not lst and n <= ultima:
            raise RuntimeError(f"Alesc: a página {n} da lista de sessões plenárias veio sem sessões")
        novas = sum(1 for s in lst if s["id"] not in sessoes)
        for s in lst:
            sessoes[s["id"]] = {"t": s["t"], "d": s["d"], "s": s["s"]}
        return novas, total, ultima

    def reler(lido_em: float, data: str) -> bool:
        return data >= recente and time.time() - lido_em >= 20 * 3600

    rotulos: dict[str, int] = {}
    try:
        lidas = set()
        while not volta:  # primeira volta: todas as páginas da lista, de onde parou
            _, _, ultima = pagina(cursor)
            lidas.add(cursor)
            cursor += 1
            if cursor > ultima:
                volta, cursor = True, 1
        if 1 not in lidas:  # depois: a 1ª página e as seguintes enquanto aparecer sessão nova (ou faltar sessão)
            n = 1
            while True:
                novas, total, ultima = pagina(n)
                n += 1
                if n > ultima or (not novas and (total is None or len(sessoes) >= total)):
                    break
        for sid in sorted(sessoes, key=lambda k: (sessoes[k].get("d") or "", k), reverse=True):
            s = sessoes[sid]
            if not s.get("d") or not INICIO <= s["d"] <= hj:
                continue
            o = odias.get(sid)
            if o is None or reler(o.get("em", 0), s["d"]):
                antes_de_pedir()
                try:
                    o = dict(_ordem_do_dia(rv.texto(f"{ELEGIS}/sessoes-plenarias/{sid}/ordem-do-dia", None)), em=int(time.time()))
                except SemTempo:
                    raise
                except Exception as e:  # noqa: BLE001 - uma sessão com problema não derruba as outras
                    if "HTTP Error 404" not in str(e):
                        log(f"  SC votações: Ordem do Dia de {s.get('t')} ({s['d']}) não veio ({e})")
                        continue
                    o = {"d": s["d"], "s": None, "v": [], "em": int(time.time())}
                odias[sid] = o
            for it in o["v"]:
                for x in it["x"]:
                    e = extratos.get(x)
                    # extrato lido no próprio dia da sessão: a votação podia estar aberta; é relido no dia seguinte
                    if e is None or (e.get("lido", "") <= s["d"] and reler(e.get("em", 0), s["d"])):
                        antes_de_pedir()
                        try:
                            e = dict(_extrato(rv.texto(f"{ELEGIS}/extrato-votacao/{x}", None, headers=AJAX)),
                                     em=int(time.time()), lido=hj)
                        except SemTempo:
                            raise
                        except Exception as erro:  # noqa: BLE001
                            if "HTTP Error 404" not in str(erro):
                                log(f"  SC votações: extrato {x} ({it.get('p')}, {s['d']}) não veio ({erro})")
                                continue
                            e = {"v": [], "em": int(time.time()), "lido": hj}
                        extratos[x] = e
    except SemTempo:
        pass
    finally:
        guardar()
    falta_o = [k for k, s in sessoes.items() if s.get("d") and INICIO <= s["d"] <= hj and k not in odias]
    falta_x = {x for o in odias.values() for it in o["v"] for x in it["x"] if x not in extratos}
    if not completa:
        if not volta or falta_o or falta_x:
            log(f"  SC votações: primeira carga em andamento ({len(sessoes)} sessões na lista"
                f"{'' if volta else (f', lista lida até a página {cursor - 1}' if cursor > 1 else ', lista por ler')}; "
                f"{len(falta_o)} Ordens do Dia e {len(falta_x)} extratos por ler; {rv.pedidos} pedidos nesta rodada); "
                "os perfis ficam com o bloco de antes")
            return None
        completa = True
        guardar()
    elif falta_o or falta_x:
        log(f"  SC votações: {len(falta_o)} Ordens do Dia e {len(falta_x)} extratos ficam para a próxima rodada")
    nomes = Nomes(membros, VOTOS_MANUAL)
    por_pessoa: dict[str, dict[str, dict]] = {}
    votacoes = []  # (sessão, data, item da Ordem do Dia, extrato, [(nome, voto)])
    for sid, o in odias.items():
        data = (sessoes.get(sid) or {}).get("d") or o.get("d")
        if not data or data < INICIO:
            continue
        for it in o["v"]:
            for x in it["x"]:
                votos = [(n_, _voto(v)) for n_, v in (extratos.get(x) or {}).get("v") or [] if n_]
                if votos:
                    votacoes.append((sid, data, it, x, votos))
    # a fase do extrato é a situação da proposição quando ela entrou na pauta: nos dois turnos no mesmo dia (sessão
    # ordinária e, logo depois, extraordinária), a segunda votação às vezes ainda diz "1º Turno". Quando a mesma
    # proposição tem duas votações com a mesma fase, o turno fica de fora (o que não se sabe fica de fora).
    fases: dict[tuple, int] = {}
    for _, _, it, x, _ in votacoes:
        k = (it.get("pid") or it.get("p"), _fase(extratos[x].get("f")))
        fases[k] = fases.get(k, 0) + 1
    for sid, data, it, x, votos in votacoes:
        for _, v in votos:
            if v not in VOTO.values():
                rotulos[v] = rotulos.get(v, 0) + 1
        chave = f"alesc-vot:{x}"
        proposta = _rotulo(it.get("p") or extratos[x].get("c"))
        fase = _fase(extratos[x].get("f"))
        desc = _descricao(it.get("e"), proposta, fase, it.get("r"), fases[(it.get("pid") or it.get("p"), fase)] == 1,
                          (sessoes.get(sid) or {}).get("t"))
        pl = placar(v for _, v in votos)
        url = f"{ELEGIS}/sessoes-plenarias/{sid}/ordem-do-dia"
        for nome, v in votos:
            pid = nomes.quem(nome)
            if pid and chave not in por_pessoa.setdefault(pid, {}):
                por_pessoa[pid][chave] = item_voto(chave, v, data, proposta, desc, it.get("r"), pl, url,
                                                   f"alesc:{it['pid']}" if it.get("pid") else None)
    nomes.avisar(UF, "votações")
    if rotulos:
        log(f"  SC votações: votos com outro nome no extrato (ficam como a Alesc escreve): {rotulos}")
    esc_pt, esc_en = escopo_votos(CASA["sigla"], *desde(INICIO), extra=VOTOS_EXPLICA)
    f_vot = fonte(VEICULO, "e-Legis: sessões plenárias (Ordem do Dia e extrato de votação de cada sessão)",
                  f"{ELEGIS}/sessoes-plenarias", hj)
    blocos = {pid: bloco_votacoes(list(d.values()), esc_pt, esc_en, f_vot) for pid, d in por_pessoa.items() if d}
    log(f"  SC: {len(votacoes)} votações nominais em {len({v[0] for v in votacoes})} sessões (de {len(odias)} lidas); "
        f"votos de {len(blocos)} deputados; {rv.pedidos} pedidos (votações)")
    return blocos


def coletar() -> dict:
    rede = Rede("alesc", pausa=1.0)
    membros, ids, avisos, casados = _membros(rede)
    for a in avisos:
        log(f"  SC: {a}")
    itens, completo = _proposicoes(rede)
    if not completo:  # primeira carga em andamento: nada pela metade no site (ficam os arquivos de antes)
        log(f"  SC: primeira carga das listas em andamento ({len(itens)} proposições lidas); os arquivos de antes "
            f"continuam; {rede.pedidos} pedidos à rede")
        return _carga.pendente(CASA["sigla"], f"primeira carga: {len(itens)} proposições lidas", rede.pedidos)
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
    per = periodo_governo(UF)
    do_governo: list[str] = []
    for x in itens.values():
        if any(re.search(r"(?i)governador|governo do estado|poder executivo", a or "") for a in x.get("autores") or []) and \
                (x.get("entrada") or "") >= per["inicio"]:
            do_governo.append(x["id"])
        if (x.get("entrada") or "") < INICIO:
            continue
        autores = [k for k in dict.fromkeys(quem(a) for a in x.get("autores") or []) if k]
        if autores:
            ligados[x["id"]] = autores
    precisa = sorted((i for i in set(ligados) | set(do_governo) if FICHA.search(itens[i].get("situacao") or "")),
                     key=lambda i: itens[i].get("entrada") or "", reverse=True)
    fichas, sem_ficha = _fichas(rede, itens, precisa)
    if sem_ficha > max(5, 0.01 * len(precisa)):  # primeira carga das tramitações: sem elas, a situação sai errada
        log(f"  SC: primeira carga das páginas de tramitação em andamento; os arquivos de antes continuam; "
            f"{rede.pedidos} pedidos à rede")
        return _carga.pendente(CASA["sigla"], f"primeira carga: {sem_ficha} páginas de tramitação por ler", rede.pedidos)

    def proposta(x: dict, papel: str) -> dict:
        sig, tipo = TIPOS[int(x["tipo"])]
        m = re.search(r"(\d+)/(\d{4})", x.get("sigla") or "")
        sigla = f"{sig} {int(m.group(1))}/{m.group(2)}" if m else (x.get("sigla") or sig)
        f = fichas.get(x["id"]) if FICHA.search(x.get("situacao") or "") else None
        st, norma, dst, motivo = _desfecho(f) if f and f.get("sit") == x.get("situacao") else (None, None, None, None)
        p = regional.proposta(f"alesc:{x['id']}", sigla, tipo, x.get("entrada"), x.get("ementa"), x.get("situacao"),
                              f"{ELEGIS}/proposicoes/{x['id']}", papel=papel, regras=REGRAS, status=st, data_status=dst)
        if norma:
            parcial = norma.get("parcial") or re.search(r"(?i)veto parcial", x.get("situacao") or "") or any(
                re.search(r"(?i)veto parcial", e["s"]) for e in (f or {}).get("ev") or [])
            virou(p, norma["nome"] + (" (com partes vetadas)" if parcial else ""), norma["url"])
            p["lei"]["nome"] = norma["nome"]
        elif p["status"] == "lei":
            com_status_en(p, "Virou lei (a página oficial não mostra o número)",
                          "Became law (the official page does not show the number)")
        elif motivo == "veto" or (p["status"] == "rejeitada" and re.match(r"(?i)veto total", x.get("situacao") or "")):
            com_status_en(p, "Aprovada pela Assembleia, mas vetada por inteiro pelo governador",
                          "Approved by the Assembly, but fully vetoed by the governor")
        elif motivo == "parecer":
            com_status_en(p, "Rejeitada numa comissão (parecer contrário) e arquivada",
                          "Rejected in a committee (unfavorable opinion) and archived")
        elif p["status"] == "aprovada":
            com_status_en(p, "Aprovada pela Assembleia; segue para a sanção ou o veto do governador",
                          "Approved by the Assembly; it goes to the governor to sign or veto")
        return p

    for i, autores in ligados.items():
        principal = quem((itens[i].get("autores") or [""])[0])
        for k in autores:
            por_dep.setdefault(k, []).append(proposta(itens[i], "autor" if k == principal else "coautor"))
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
    try:
        # o governo: projetos do Governador, leis do período e mensagens de veto
        governo = [proposta(itens[i], "autor") for i in do_governo if int(itens[i]["tipo"]) in TIPOS]
        tot_leis, ultima_lei = _leis(rede, per["inicio"])
        vetos = sorted((v for v in _vetos(rede, per["inicio"]) if (v.get("entrada") or "") >= per["inicio"]),
                       key=lambda v: v.get("entrada") or "")
        totais = sum(1 for v in vetos if re.match(r"(?i)\s*veto total", v.get("ementa") or ""))
        parciais = sum(1 for v in vetos if re.match(r"(?i)\s*veto parcial", v.get("ementa") or ""))
        d_pt, d_en = desde(per["inicio"])
        primeiro_veto = mandatos.data_br(vetos[0]["entrada"]) if vetos else "-"
        n_ord, n_lc, sem = tot_leis["Lei Ordinária"], tot_leis["Lei Complementar"], len(vetos) - totais - parciais
        v_pt = f"{qtd(totais, 'total', 'totais')} e {qtd(parciais, 'parcial', 'parciais')}" + (
            f"; {sem} sem a indicação na ementa" if sem else "")
        v_en = f"{totais} full and {parciais} partial" + (f"; {sem} without that information in the summary" if sem else "")
        esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                               "As medidas provisórias também não entram: na Alesc, cada uma vira um projeto de conversão em "
                               "lei, com outro número. Lista do e-Legis, o sistema da Alesc, que começa com a legislatura "
                               "(fevereiro de 2023).",
                               "Provisional measures are not included either: at the Alesc, each one becomes a conversion bill, "
                               "with another number. List from e-Legis, the Alesc system, which starts with the current "
                               "legislature (February 2023).")
        executivo = bloco_executivo(
            per, [fonte(VEICULO, "Legislação SC: pesquisa de leis ordinárias e complementares por data",
                        f"{LEIS}/legislativo?tipo_ato_normativo={urllib.parse.quote('Lei Ordinária')}&data_inicial={per['inicio']}", hj),
                  fonte(VEICULO, "e-Legis: mensagens de veto do governador",
                        f"{ELEGIS}/proposicoes/processo-legislativo?tipoPropositura=10&arquivados=1", hj)],
            f"Leis: {qtd(n_ord, 'lei ordinária', 'leis ordinárias')} e {qtd(n_lc, 'lei complementar', 'leis complementares')} "
            f"assinadas desde {d_pt}, pela pesquisa oficial da Legislação SC (mantida pela Alesc). A pesquisa não separa as "
            "poucas leis promulgadas pela própria Assembleia (quando ela derruba um veto ou o governador não responde no prazo): "
            f"elas estão na conta. Vetos: as mensagens de veto que chegaram à Assembleia (no e-Legis, desde {primeiro_veto}), "
            f"{v_pt}.",
            f"Laws: {qtd(n_ord, 'ordinary law', 'ordinary laws')} and {qtd(n_lc, 'complementary law', 'complementary laws')} "
            f"signed since {d_en}, from the official search of Santa Catarina's legislation (kept by the Alesc). The search "
            "does not single out the few laws promulgated by the Assembly itself (when it overrides a veto or the governor does "
            "not answer in time): they are included. Vetoes: the veto messages that reached the Assembly (in e-Legis, since "
            f"{mandatos.extenso(vetos[0]['entrada'])[1] if vetos else '-'}), {v_en}.",
            leis=sum(tot_leis.values()), vetos=len(vetos), vetos_totais=None if sem else totais,
            vetos_parciais=None if sem else parciais,
            ultima_lei=ultima_lei, ultimo_veto=vetos[-1]["entrada"] if vetos else None)
        gravar_governo(UF, per, governo, *esc_g, f_prop, executivo)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  SC: governo: {e}")
    try:  # por último: na primeira carga, as votações usam o tempo que sobrar na rodada
        vot = _votacoes(rede, membros)
    except Exception as e:  # noqa: BLE001 - o e-Legis fora do ar não derruba a coleta: fica o bloco de antes
        log(f"  SC: votações: {e}")
        vot = None
    com_votos = aplicar(extras, vot, "votacoes")
    v_pt, v_en = desde(INICIO)
    nota_votos = ((f"Votações: entram as nominais do Plenário (sessões ordinárias e extraordinárias) desde {v_pt}, com o voto "
                   "de cada deputado, do “Extrato de votação” de cada sessão no e-Legis (Sessões Plenárias > Ordem do Dia). O "
                   "extrato mostra só quem votou; o placar é a soma dele. As votações simbólicas não registram o voto de cada um "
                   "e não entram. Nas votações de veto, quem vota “sim” mantém o veto e quem vota “não” derruba o veto.",
                   f"Votes: roll-call votes in the full Assembly (regular and extraordinary sessions) since {v_en} are included, "
                   "with each deputy's vote, from the vote record of each session in e-Legis, the Alesc system (plenary "
                   "sessions > order of business > vote record). The record lists only those who voted; the tally is its sum. "
                   "Voice votes do not record each member's vote and are not included. In votes on a veto, a “yes” vote keeps "
                   "the veto and a “no” vote overturns it.") if com_votos else
                  ("O voto de cada deputado nas votações nominais está no e-Legis, no “Extrato de votação” de cada sessão "
                   "(Sessões Plenárias > Ordem do Dia).",
                   "Each deputy's vote in roll-call votes is in e-Legis, the Alesc system, in the vote record of each session "
                   "(plenary sessions > order of business > vote record)."))
    notas = [nota_votos,
             ("Os gastos são as despesas de cada gabinete que a Alesc publica (diárias, passagens, telefone, veículos, aluguel e "
              "outras), inclusive as diárias e passagens da equipe, que aparecem separadas.",
              "Spending is each office's expenses as published by the Alesc (per diems, tickets, phone, vehicles, rent and "
              "others), including staff per diems and tickets, which are shown separately.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": com_votos, "gastos": True},
                  f_lista, esc_pt, esc_en, notas)
