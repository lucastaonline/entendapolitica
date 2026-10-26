"""Assembleia Legislativa do Estado da Bahia (Alba): portal legislativo (SPL) com API pública
(https://albalegis.nopapercloud.com.br/api/publico/, documentada em https://albalegis.nopapercloud.com.br/dados-abertos.aspx).
Desde 1º/8/2025 a Alba publica os dados dos deputados e das proposições nesse portal (aviso na página "Deputados" do site).

Lista: parlamentares da 20ª legislatura com situação "Ativo" (filtro da própria API: 63 pessoas, inclusive suplentes que
assumiram), conferida com a lista "Em exercício" do site da Alba. A API de parlamentares é muito lenta (cerca de 40 s por
página de 10), então ela fica guardada por até 3 dias; a lista do site, que é rápida, é lida todo dia e, se as duas não
baterem, a da API é baixada de novo.
Propostas: projetos de lei (PL), de lei complementar (PLC), de emenda constitucional (PEC), de decreto legislativo (PDL) e
de resolução (PRS) desde 1º/2/2023, com autor, coautores, situação e tramitações.
Gastos: verba indenizatória desde o começo da legislatura (fevereiro de 2023), pela lista de notas do Portal da
Transparência da Alba (a planilha Excel de cada ano), com o valor que a Alba aceitou em cada nota (sem a glosa) e as
categorias oficiais (ver "gastos: verba indenizatória" abaixo). O coletor NoPaper (comum a BA e SE) grava a Casa e os
perfis sem gastos; depois, Alba.coletar() põe o bloco "gastos" em cada perfil e a cobertura e a nota na Casa.
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

import regional
from comum import PESSOAS, UA, chave_nome, data_iso, fonte, hoje, ler_json, log, salvar_json, sem_acento, sem_mudar_data
from mandatos import mes_ano

from . import _ne_gov as gv
from ._ne_comum import Rede, com_status_en, feito, legislatura_estadual, nome_lei, vez
from ._ne_nopaper import NoPaper, consulta_csv, texto_tramitacoes, ultima
from ._votos_gastos import Nomes, bloco_gastos, valor_br, xlsx_linhas

SITE_LISTA = "https://www.al.ba.gov.br/deputados/deputados-estaduais"


def _nomes_site(col) -> set[str]:
    t = col.rede.texto(SITE_LISTA, "site-em-exercicio.html", 20)
    nomes = re.findall(r'<option value="/deputados/deputado-estadual/\d+">\s*<span>(.*?)</span>', t, re.S)
    return {chave_nome(html.unescape(n)) for n in nomes if n.strip()}


def em_exercicio(col, ps: list[dict]) -> list[dict]:
    ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
    try:
        site = _nomes_site(col)
    except Exception as e:  # o site fora do ar não impede a lista da API
        log(f"  BA: lista do site indisponível ({e})")
        return ativos
    api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
    if site and site != api:
        ps = col.parlamentares(max_idade_h=20)
        ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
        api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
        if site != api:
            log(f"  BA: lista da API e do site diferentes. Só na API: {sorted(api - site)}; só no site: {sorted(site - api)}")
    return ativos


# Na Alba a "situação" da API não acompanha o fim do processo (projeto que virou lei pode continuar "TRAMITANDO"), então a
# situação vem das tramitações (frases conferidas à mão numa amostra; ver as notas da frente ale-nordeste):
# "Promulgada/Publicada a Lei nº ..." e "Sancionada Lei nº ..." = virou lei (o número da lei vem junto); o mesmo para
# Resolução; "Expedido autógrafo ao Governador" = aprovada e enviada para sanção; "Devolvido sem sanção ou veto" = o
# governador não decidiu no prazo e falta promulgar; "Aprovado em 1ª/2ª discussão" ou "em discussão única" = aprovada no
# Plenário; "Retirado de tramitação a pedido do autor" = o autor desistiu.
_NORMA = re.compile(r"(?:promulgad|publicad|sancionad)[ao]?\s+(?:a\s+)?(lei complementar|lei|resolucao|emenda constitucional|"
                    r"decreto legislativo)\s+n[o°º]?\.?\s*([\d.,]+)")
NOMES = {"lei complementar": "Lei Complementar", "lei": "Lei", "resolucao": "Resolução",
         "emenda constitucional": "Emenda Constitucional", "decreto legislativo": "Decreto Legislativo"}
REGRAS = [
    (r"(?<!pedido de )retirad[ao] de tramitacao|retirad[ao] pel[oa] autor|(?<!pedido de retirada )a pedido do autor", "retirada", None, None),
    (r"veto total|veto integral|vetad[oa] (totalmente|integralmente)", "rejeitada", "Vetada por inteiro pelo governador",
     "Fully vetoed by the governor"),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] sem sancao ou veto", "aprovada", "Aprovada; o governador não sancionou nem vetou no prazo, e falta promulgar",
     "Approved; the governor did not sign or veto it in time, and it still has to be promulgated"),
    (r"expedido autografo|autografo expedido", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"aprovad[ao] em (\S+ )?(e \S+ )?discussao|aprovad[ao] em plenario", "aprovada",
     "Aprovada no Plenário", "Approved by the full Assembly"),
    (r"apensad", "junta", None, None),
]


def situacao(v: dict) -> dict:
    data = (ultima(v)[0] or "")[:10] or None
    for t in reversed(v.get("tr") or []):  # a norma que a proposição virou, com número e data
        m = _NORMA.search(sem_acento((t[3] or "").lower()))
        if m:
            nome = NOMES[m.group(1)]
            num = re.sub(r"\D", "", m.group(2))
            ano = (re.search(r"(?:de|em)\s+\d{1,2}[º°o]?/\d{2}/(\d{4})|de (\d{4})", sem_acento((t[3] or "").lower()[m.end():m.end() + 40])) or None)
            ano = next((g for g in ano.groups() if g), None) if ano else (t[0] or "")[:4] or None
            nl = nome_lei(nome, num, ano)
            return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None,
                    "data": (t[0] or "")[:10] or data, "lei": {"nome": nl, "url": None}}
    tx = texto_tramitacoes(v)
    for exp, st, pt, en in REGRAS:
        if re.search(exp, tx):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    sit = sem_acento((v.get("sit") or "").lower())
    if sit.startswith("arquivad"):
        return {"status": "arquivada", "txt": "Arquivada", "en": None, "data": data, "lei": None}
    if sit.startswith("tramitando") or v.get("tr"):
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


def coletar() -> dict:
    return Alba(
        uf="BA", base="https://albalegis.nopapercloud.com.br", casa="Assembleia Legislativa do Estado da Bahia",
        casa_en="Legislative Assembly of the State of Bahia", sigla="Alba", site="https://www.al.ba.gov.br",
        veiculo=VEICULO, prefixo="alba", pasta="alba",
        tipos={1: "PL", 6: "PLP", 10: "PEC", 2: "PDL", 13: "PRC"}, situacao=situacao, em_exercicio=em_exercicio,
        filtro_pessoas=f"&parlamentarLegislatura={legislatura_estadual(20)}&parlamentarSituacao=1", idade_pessoas_h=72, qtd_pessoas=10,
        notas=[NOTA_VOTOS],
    ).coletar()


NOTA_VOTOS = ("As votações não entram: no sistema legislativo da Alba (albalegis.nopapercloud.com.br), cada sessão traz só o "
              "áudio e o texto (PDF); a Alba não publica o voto de cada deputado em formato aberto.",
              "Votes are not included: in the Alba legislative system (albalegis.nopapercloud.com.br), each session only has "
              "the audio and the text (PDF); the Alba does not publish each deputy's vote in an open format.")


# ---------------------------------------------------------------- gastos: verba indenizatória
# Portal da Transparência da Alba, página "Verba Indenizatória" (VERBAS; o endereço oficial é escrito "idenizatorias"): a
# lista de notas (nº do processo, nº da nota, competência mês/ano, deputado, categoria e valor), com filtros por categoria,
# deputado, mês e ano. O botão "Excel" baixa a mesma lista de um ano inteiro (VERBAS-excel?categoria=&deputado=&mes=&ano=
# AAAA; 1 arquivo de ~220 KB por ano): a coluna DATA é o 1º dia do mês de competência e o nome de algumas categorias vem
# cortado (cerca de 80 letras); o nome completo vem do filtro "Categoria" da página. O valor é o que a Alba aceitou: o
# detalhe de cada nota (/transparencia/verbas-idenizatorias/<id>/) mostra o valor da nota e a "glosa" (a parte recusada);
# a nota recusada por inteiro aparece na lista e na planilha com R$ 0,00 (conferido em 26/10/2026). Duas linhas iguais
# (mesmo processo, nota, deputado e valor) são duas entradas da lista oficial, cada uma com o seu detalhe e o seu anexo:
# as duas contam, como na página. A lista da página às vezes mostra uma linha vazia no lugar de uma nota (ex.: as 4 notas
# de Hilton Coelho no processo nº 210487 de 2026, número que também foi usado em 2025): a planilha, que sai da mesma
# página, traz essas notas completas, e elas entram. Janeiro de 2023 ainda é da legislatura anterior e fica de fora.
# Conferido à mão em 26/10/2026 (lista da página filtrada por deputado e mês x planilha): Adolfo Menezes 06/2025
# R$ 47.000,00 e 03/2026 R$ 45.300,00 (e os anos inteiros: 2025, 35 notas, R$ 513.100,00; 2026, 27 notas, R$ 426.372,23),
# Hilton Coelho 04/2024 R$ 51.751,97 e 08/2026 R$ 20.100,00, Eduardo Alencar 11/2025 R$ 44.500,00 e 09/2026
# R$ 42.450,00, Zé Raimundo Fontes 12/2023 R$ 35.615,33; o total e cada categoria batem. robots.txt de www.al.ba.gov.br:
# não existe (404): sem regras nem Crawl-delay.
VEICULO = "Assembleia Legislativa da Bahia (Alba)"
VERBAS = "https://www.al.ba.gov.br/transparencia/verbas-idenizatorias"
NOME_VERBA = ("Verba indenizatória", "Expense allowance (verba indenizatória)")
VERBA_PASTA = "alba-gastos"
VERBA_MANUAL: dict[str, str] = {}  # {nome como a planilha escreve: id da pessoa ou "-"} (conferido à mão)


def _limpo(t: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip()


def _cache_ou_velho(rede: Rede, url: str, nome: str, idade_h: float) -> bytes:
    """O arquivo do cache se ainda vale; senão baixa de novo. Se o site não responder (ou a rodada acabar), vale a cópia
    da última leitura, se houver."""
    try:
        return rede.bruto(url, nome, idade_h)
    except Exception as e:
        arq = rede.pasta / nome
        if arq.exists() and arq.stat().st_size:
            log(f"  BA verba: {url} não foi relido ({type(e).__name__}); vale a cópia da última leitura")
            return arq.read_bytes()
        raise


def _filtros_verba(rede: Rede) -> tuple[list[str], dict[str, str]]:
    """(nomes completos das categorias, {id no filtro "Deputado": nome}) do formulário da página da verba."""
    t = _cache_ou_velho(rede, VERBAS, "pagina.html", 72).decode("utf-8", "replace")

    def opcoes(campo: str) -> list[tuple[str, str]]:
        s = re.search(rf'<select[^>]*\bname="{campo}"[^>]*>(.*?)</select>', t, re.S)
        return [(v.strip(), _limpo(re.sub(r"<[^>]+>", " ", n))) for v, n in
                re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', s.group(1), re.S) if v.strip()] if s else []

    cats = [n for _, n in opcoes("categoria")]
    if len(cats) < 5:
        raise RuntimeError(f"a página da verba indenizatória mudou ({len(cats)} categorias no filtro)")
    return cats, {v: re.sub(r"(?i)^dep(utad[oa])?\.?\s+", "", n) for v, n in opcoes("deputado")}


def _categoria(txt: str, cats: list[str]) -> str:
    """A categoria como a página escreve (a planilha corta os nomes longos: 'Aquisição ou locação de software; ...;
    assinaturas de' -> o nome completo do filtro, quando só uma categoria começa assim)."""
    t = _limpo(txt)
    k = chave_nome(t)
    for c in cats:
        if chave_nome(c) == k:
            return c
    cortado = [c for c in cats if chave_nome(c).startswith(k)]
    return cortado[0] if len(k) >= 40 and len(cortado) == 1 else (t or "Sem categoria informada")


def _mes_planilha(v: str) -> str | None:
    """DATA da planilha (número de série do Excel, '45597.0', ou '01/11/2024') -> '2024-11'."""
    v = (v or "").strip()
    if re.fullmatch(r"\d{4,6}(\.\d+)?", v):
        d = dt.date(1899, 12, 30) + dt.timedelta(days=int(float(v)))
        return f"{d.year}-{d.month:02d}"
    d = data_iso(v)
    return d[:7] if d else None


def _planilha(b: bytes, ano: int, cats: list[str]) -> list[tuple[str, str, str, float]]:
    """[(mês 'AAAA-MM', deputado como a planilha escreve, categoria, valor)] da planilha de um ano."""
    linhas = xlsx_linhas(b)
    for i, l in enumerate(linhas):
        col = {chave_nome(c).split(" ")[0]: k for k, c in enumerate(l) if c.strip()}
        if {"DATA", "DEPUTADO", "CATEGORIA", "VALOR"} <= set(col):
            break
    else:
        raise RuntimeError(f"a planilha da verba de {ano} mudou de formato (cabeçalho não encontrado)")
    out, fora = [], 0
    cat: dict[str, str] = {}
    for l in linhas[i + 1:]:
        if not any(c.strip() for c in l):
            continue
        cel = {k: (l[j] if j < len(l) else "") for k, j in col.items()}
        mes, nome = _mes_planilha(cel["DATA"]), _limpo(cel["DEPUTADO"])
        if not mes or not nome or mes[:4] != str(ano):
            fora += 1
            continue
        if cel["CATEGORIA"] not in cat:
            cat[cel["CATEGORIA"]] = _categoria(cel["CATEGORIA"], cats)
        out.append((mes, nome, cat[cel["CATEGORIA"]], valor_br(cel["VALOR"])))
    if fora:
        log(f"  BA verba: planilha de {ano}: {fora} linhas sem data do ano ou sem deputado; não entram")
    return out


def ler_verba() -> dict | None:
    """As planilhas da verba indenizatória (uma por ano, desde o começo da legislatura) e os filtros da página. Poucos
    pedidos: o ano corrente é relido a cada 20 h (e o anterior também, até março); o ano anterior, a cada 7 dias; os mais
    antigos, a cada 30 dias. None quando a planilha de algum ano nunca foi baixada e não veio nesta rodada (primeira carga:
    os perfis ficam com o bloco de antes)."""
    rede = Rede(VERBA_PASTA, pausa=1.5, timeout=180)
    ini, h = regional.inicio_estadual("BA"), hoje()
    atual = int(h[:4])
    try:
        cats, deps = _filtros_verba(rede)
        linhas = []
        for ano in range(int(ini[:4]), atual + 1):
            idade = 20 if ano == atual or (ano == atual - 1 and int(h[5:7]) <= 3) else 24 * 7 if ano == atual - 1 else 24 * 30
            nome = f"verba-{ano}.xlsx"
            b = _cache_ou_velho(rede, f"{VERBAS}-excel?categoria=&deputado=&mes=&ano={ano}", nome, idade)
            if b[:2] != b"PK":  # o site devolveu outra coisa (página de erro): o próximo pedido baixa de novo
                (rede.pasta / nome).unlink(missing_ok=True)
                raise RuntimeError(f"a planilha de {ano} não veio no formato Excel")
            linhas += _planilha(b, ano, cats)
    except Exception as e:  # inclui SemTempo (o fim da rodada)
        log(f"  BA verba: planilhas não lidas ({type(e).__name__}: {e}); os perfis ficam com os gastos de antes")
        return None
    log(f"  BA verba: {len(linhas)} linhas nas planilhas de {ini[:4]} a {atual}; {rede.pedidos} pedidos ao site")
    return {"linhas": linhas, "deputados": deps, "inicio": ini}


def blocos_verba(verba: dict, membros: list[dict]) -> dict[str, dict]:
    """{id da pessoa: bloco "gastos"} (desde o começo da legislatura ou desde que a pessoa assumiu)."""
    ini = verba["inicio"]
    nomes = Nomes(membros, VERBA_MANUAL)
    por: dict[str, list] = {}
    for mes, nome, tipo, valor in verba["linhas"]:
        if mes >= ini[:7]:
            pid = nomes.quem(nome)
            if pid:
                por.setdefault(pid, []).append((mes, tipo, valor))
    nomes.avisar("BA", "verba indenizatória")
    # o id de cada pessoa no filtro "Deputado" da página (para o link da fonte), pelo nome
    filtro = verba["deputados"]
    exatos = {chave_nome(n): v for v, n in filtro.items()}
    no_filtro = Nomes([{"id": v, "nome": n} for v, n in filtro.items()])
    out, sem_filtro = {}, []
    for m in membros:
        ls = [x for x in por.get(m["id"], []) if x[2]]
        if not ls:
            continue
        ano = max(x[0] for x in ls)[:4]
        sid = exatos.get(chave_nome(m["nome"])) or no_filtro.quem(m["nome"])
        if sid:
            f = fonte(VEICULO, f"Verba indenizatória de {m['nome']} em {ano} (Portal da Transparência da Alba)",
                      f"{VERBAS}?categoria=&deputado={sid}&mes=&ano={ano}")
        else:  # a pessoa não está no filtro "Deputado" da página: a lista do ano, com todos os deputados
            sem_filtro.append(m["nome"])
            f = fonte(VEICULO, f"Verba indenizatória da Alba em {ano}, com todos os deputados (o filtro da página não traz "
                      f"{m['nome']})", f"{VERBAS}?categoria=&deputado=&mes=&ano={ano}")
        b = bloco_gastos(ls, f, ini, NOME_VERBA)
        if b:
            out[m["id"]] = b
    if sem_filtro:
        log(f"  BA verba: fora do filtro \"Deputado\" da página (o link vai para a lista do ano): {sem_filtro}")
    total = sum(b["mandatoTotal"] for b in out.values())
    log(f"  BA verba: {len(out)} de {len(membros)} perfis com gastos; R$ {total:,.2f} desde {ini[:7]}")
    return out


def nota_verba() -> tuple[str, str]:
    pt, en = mes_ano(regional.inicio_estadual("BA"))
    return (f"Gastos: verba indenizatória, pela lista de notas do Portal da Transparência da Alba (a planilha de cada ano, "
            f"com o mês a que cada nota se refere), desde {pt}. Entra o valor que a Assembleia aceitou em cada nota: "
            f"quando ela recusa uma nota inteira (a \"glosa\"), a lista mostra R$ 0,00. Os tipos de despesa são as "
            f"categorias da própria Alba.",
            f"Spending: the expense allowance (verba indenizatória), from the list of receipts on the Alba transparency "
            f"portal (one spreadsheet per year, with the month each receipt refers to), since {en}. Each receipt counts "
            f"with the amount the Assembly accepted: when it rejects a whole receipt (a \"glosa\"), the list shows R$ 0.00. "
            f"Expense types are the Alba's own categories.")


def _de_antes() -> dict[str, dict | None]:
    """Os arquivos da Casa e dos perfis como estavam antes desta rodada (o coletor NoPaper regrava todos sem gastos)."""
    out: dict[str, dict | None] = {}
    for p in [*PESSOAS.glob("dest-BA-*.json"), regional.ASSEMBLEIAS / "BA.json"]:
        try:
            out[p.name] = ler_json(p)
        except Exception:  # arquivo ilegível: é regravado do zero
            out[p.name] = None
    return out


def _regravar(caminho: Path, novo: dict, antigo: dict | None) -> None:
    """Grava `novo` com a data de hoje. Se, em relação ao arquivo de antes desta rodada, só mudaram as datas de consulta,
    o arquivo de antes fica como estava (a regra de comum.sem_mudar_data, a mesma do NoPaper ao gravar)."""
    novo["atualizado"] = hoje()
    if antigo is not None:
        salvar_json(caminho, antigo)
    salvar_json(caminho, sem_mudar_data(novo, caminho))


def por_gastos(verba: dict | None, antes: dict[str, dict | None], resumo: dict) -> bool:
    """Depois que o coletor NoPaper gravou a Casa e os perfis (sem gastos), põe o bloco "gastos" em cada perfil e a
    cobertura e a nota na Casa. Sem as planilhas (verba None) ou com erro na conta, cada perfil fica com o bloco que tinha
    antes desta rodada (nada pela metade). Devolve se algum perfil ficou com o bloco."""
    casa_arq = regional.ASSEMBLEIAS / "BA.json"
    casa = ler_json(casa_arq)
    blocos = None
    if verba is not None:
        try:
            blocos = blocos_verba(verba, casa["membros"])
        except Exception as e:
            log(f"  BA verba: ATENÇÃO: gastos não calculados ({type(e).__name__}: {e}); ficam os de antes")
    algum = False
    for m in casa["membros"]:
        arq = PESSOAS / f"{m['id']}.json"
        try:
            x = ler_json(arq)
            if x is None:
                continue
            b = blocos.get(m["id"]) if blocos is not None else (antes.get(arq.name) or {}).get("gastos")
            x.pop("gastos", None)
            if b:
                x["gastos"] = b
                algum = True
                if b.get("fonte") and b["fonte"] not in (x.get("fontes") or []):
                    x.setdefault("fontes", []).append(b["fonte"])
            _regravar(arq, x, antes.get(arq.name))
        except Exception as e:  # um perfil com problema não impede os outros
            log(f"  BA verba: perfil {m['id']} não regravado ({type(e).__name__}: {e})")
    casa["cobertura"]["gastos"] = algum
    notas = [n for n in zip(casa.get("notas") or [], casa.get("notas_en") or []) if not n[0].startswith("Gastos:")]
    if algum:
        notas.append(nota_verba())
    casa["notas"], casa["notas_en"] = [n[0] for n in notas], [n[1] for n in notas]
    _regravar(casa_arq, casa, antes.get("BA.json"))
    resumo.setdefault("cobertura", {})["gastos"] = algum
    return algum


# ---------------------------------------------------------------- o que o governo do estado fez (gov-BA)
AUTOR_EXECUTIVO = 4105  # "PODER EXECUTIVO" no portal legislativo da Alba
LEGISLA = "https://www.legislabahia.ba.gov.br"  # Portal de Legislação do Estado da Bahia (Casa Civil)
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                     "outubro", "novembro", "dezembro"], 1)}
def _legisla(url: str, pausa: float = 1.0) -> str:
    """O Legisla Bahia só aceita conexões TLS antigas (o padrão do Python recusa): contexto próprio, um pedido por vez, com
    o robots.txt e o intervalo entre pedidos respeitados (vez/feito de _ne_comum)."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    erro = None
    for t in range(3):
        iv = vez(url, pausa)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            erro = e
            # as páginas da lista às vezes devolvem 404 por um instante (conferido em 26/10/2026): ganham nova chance
            if e.code in (400, 401, 403, 410) or (e.code == 404 and "/documentos?" not in url):
                break
        except Exception as e:
            erro = e
        finally:
            feito(url, max(iv, 3.0 * (t + 1)))
    raise RuntimeError(f"Legisla Bahia: {url}: {erro}")


def _titulo(t: str) -> tuple[str, str] | None:
    """'LEI Nº 15.201 DE 1º DE JULHO DE 2026' -> ('15201', '2026-07-01')"""
    m = re.search(r"n[º°o]\s*([\d.]+)\s*,?\s*de\s+(\d{1,2})[º°o]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", sem_acento(t.lower()).replace("º", "o"))
    if not m or m.group(3) not in MESES:
        return None
    return m.group(1).replace(".", ""), f"{m.group(4)}-{MESES[m.group(3)]:02d}-{int(m.group(2)):02d}"


class Alba(NoPaper):
    def coletar(self) -> dict:
        antes = _de_antes()  # o NoPaper regrava a Casa e os perfis sem gastos: o que estava antes fica guardado aqui
        verba = ler_verba()  # os pedidos à rede vêm antes de tudo, para os perfis ficarem sem gastos o menor tempo possível
        r = super().coletar()
        if r.get("pendente"):  # primeira carga das propostas em andamento: nada foi gravado (nem os gastos)
            return r
        try:
            por_gastos(verba, antes, r)
        except Exception as e:  # um erro nos gastos não derruba a Casa: os perfis ficam com o que o NoPaper gravou
            log(f"  BA: ATENÇÃO: gastos não gravados ({type(e).__name__}: {e})")
        try:
            self.governo()
        except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
            log(f"  BA: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
        return r

    def leis_legisla(self, ini: str) -> dict[str, dict]:
        """Leis ordinárias e complementares desde ini no Legisla Bahia, da mais nova para a mais antiga; depois da primeira
        leitura completa, só as páginas do começo (até achar uma página só com leis já conhecidas)."""
        est = self.rede.estado("gov-legisla.json", {}) or {}
        leis: dict = est.get("leis") or {}
        for cat, tl in ((7, "LO"), (5, "LC")):
            completo = est.get(f"completo-{cat}") == ini
            pag, ultima_pag = 0, None
            while True:
                t = _legisla(f"{LEGISLA}/documentos?categoria%5B0%5D={cat}&data%5Bmin%5D={ini}&sort_by=field_data_doc&sort=desc&page={pag}")
                novos, velhas, atuais = 0, 0, 0
                for href, tit in re.findall(r'href="(/documentos/lei[^"]+)"[^>]*>([^<]+)<', t):
                    x = _titulo(html.unescape(tit))
                    if not x:
                        continue
                    if x[1] < ini:  # a lista vem da mais nova para a mais antiga; o filtro de data do portal não vale
                        velhas += 1
                        continue
                    atuais += 1
                    k = f"{tl}-{x[0]}"
                    if k not in leis:
                        novos += 1
                    leis[k] = {"n": x[0], "d": x[1], "tl": tl, "url": LEGISLA + href, "t": html.unescape(tit).strip()}
                pags = [int(p) for p in re.findall(r"(?:[?&]|&amp;)page=(\d+)", t)]
                ultima_pag = max(pags) if pags else 0
                if pag >= ultima_pag or (velhas and not atuais) or (completo and not novos):
                    break
                pag += 1
            est[f"completo-{cat}"] = ini
        est["leis"] = leis
        self.rede.guardar(est, "gov-legisla.json")
        return {k: v for k, v in leis.items() if v["d"] >= ini}

    def vetos(self, ini: str) -> list[dict]:
        """Mensagens e ofícios do Poder Executivo que vetam projetos (exportação CSV da consulta por autor, ano a ano)."""
        est = self.rede.estado("gov-vetos.json", {}) or {}
        h = dt.date.fromisoformat(hoje())
        out = []
        for ano in range(int(ini[:4]), h.year + 1):
            x = est.get(str(ano))
            if not x or (h - dt.date.fromisoformat(x["lido"])).days >= (1 if ano == h.year else 30):
                linhas = consulta_csv(self.base, f"autor={AUTOR_EXECUTIVO}&ano={ano}")
                vs = []
                for r in linhas[1:]:
                    s = " | ".join(r)
                    if len(r) > 6 and re.search(r"(?i)^(mensagem|of[ií]cio)", r[3].strip()) and re.search(r"(?i)\bvet(a|o|ou)\b", r[6]):
                        d = r[9].strip() if len(r) > 9 and re.fullmatch(r"\d{2}/\d{2}/\d{4}", r[9].strip()) else None
                        d = d or (re.findall(r"\b\d{2}/\d{2}/\d{4}\b", s) or [None])[-1]
                        vs.append({"id": r[0], "tipo": r[3].strip(), "n": r[4].strip(), "e": r[6].strip()[:300], "d": data_iso(d) if d else None})
                x = est[str(ano)] = {"lido": hoje(), "vetos": vs}
                self.rede.guardar(est, "gov-vetos.json")
            out += [v for v in x["vetos"] if (v.get("d") or f"{ano}-12-31") >= ini]
        return out

    def governo(self) -> dict:
        per = gv.periodo("BA")
        ini = per["inicio"]
        props = (self.rede.estado("estado.json", {}) or {}).get("props") or {}
        lista = []
        for k, v in props.items():
            tipo = self.tipos.get(v["tid"])
            if not tipo or (v.get("d") or "") < ini or v.get("au") != AUTOR_EXECUTIVO:
                continue
            s = situacao(dict(v, _id=k))
            prop = regional.proposta(f"{self.prefixo}:{k}", f"{v['s']} {v['n']}/{v['a']}", tipo, v.get("d"), v.get("e"),
                                     v.get("sit"), f"{self.base}/spl/processo.aspx?id={k}", papel="autor", status=s["status"],
                                     data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        fonte_prop = fonte(self.veiculo, "Proposições do Poder Executivo (portal legislativo)",
                           f"{self.base}/spl/consulta-producao.aspx?autor={AUTOR_EXECUTIVO}")
        fontes = [fonte("Governo da Bahia (Casa Civil)", "Legisla Bahia: leis ordinárias e complementares",
                        f"{LEGISLA}/documentos?categoria%5B0%5D=7")]
        leis = self.leis_legisla(ini)
        quem, faltam = gv.classificar_leis(self.rede, {k: v["url"] for k, v in leis.items()}, _legisla, orcamento_s=150)
        if faltam:  # sem a conta das leis, o perfil ficaria pela metade: fica o arquivo da última vez
            log(f"  BA: {faltam} leis ainda sem leitura do texto; o perfil do governador fica como estava até todas serem lidas")
            return {}
        n_leis, nota, nota_en, prom = None, [], [], None
        c = collections.Counter(quem.values())
        n_leis, prom = c[False], c[True]
        pt, en = gv.nota_leis(per, len(leis), c[False], c[True], c[None], "no Legisla Bahia (o portal de legislação do "
                              "governo do estado)", "in Legisla Bahia (the state government's legislation portal)")
        nota.append(pt)
        nota_en.append(en)
        vts = self.vetos(ini)
        parciais = sum(1 for v in vts if re.search(r"(?i)parcial", v["e"]))
        nota.append(f"Vetos: as mensagens e os ofícios do Poder Executivo que vetam projetos, recebidos pela Assembleia desde "
                    f"{gv.data_pt(ini)} (a Alba registra os vetos como mensagens do governador).")
        nota_en.append(f"Vetoes: the executive branch's messages and official letters vetoing bills, received by the Assembly "
                       f"since {gv.data_en(ini)} (the Alba records vetoes as messages from the governor).")
        fontes.append(fonte(self.veiculo, "Mensagens e ofícios do Poder Executivo (portal legislativo)",
                            f"{self.base}/spl/consulta-producao.aspx?autor={AUTOR_EXECUTIVO}"))
        ex = gv.bloco_executivo(per, n_leis, len(vts), fontes, " ".join(nota), " ".join(nota_en), len(vts) - parciais, parciais, prom)
        esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature")
        return gv.gravar_gov("BA", per, lista, esc, esc_en, fonte_prop, ex, fontes)
