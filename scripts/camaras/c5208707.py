"""Câmara Municipal de Goiânia (GO): a lista oficial de vereadores em exercício e os gastos da cota parlamentar (CEAP).

- Quem está no cargo: www.goiania.go.leg.br/institucional/parlamentares, seção "20ª Legislatura" (quem está de licença fica
  na seção "Parlamentares fora de exercício", que não entra).
- Gastos do mandato: a página "Cotas e Gastos Parlamentares" do Portal da Transparência da Câmara (NúcleoGov,
  camaragoiania.nucleogov.com.br/cidadao/informacao/mp/id=20): uma linha por vereador e mês de referência, com o nome do
  vereador, a descrição das despesas ("CONSULTORIA JURÍDICA - R$ 8.000,00", "COMBUSTÍVEL - R$ 604,58"...) e o valor pago no
  mês. Lida como a própria página lê, pelo filtro "Favorecido": a lista de nomes do filtro (POST em
  /api/modulos_personalizados, "get_valores_relacao") e, para cada vereador em exercício, as linhas dele (POST em /api,
  "modulos_personalizados/listarLinhasModulo" com o filtro), uns 40 pedidos a cada 6 dias. O portal pede o cabeçalho
  "X-NucleoGov-Services: true" para acesso automatizado (página "Acesso Automatizado aos Dados Abertos"). A lista inteira de
  uma vez não serve: o botão EXPORTAR monta a planilha na hora e passa de 60 s (o servidor devolve erro 504), e a lista
  paginada sem filtro repete e pula linhas entre as páginas (muitas têm a mesma data). O CPF que vem junto em cada linha é
  jogado fora na hora (não fica nem no cache).
  A CEAP foi criada pela Lei 11.308/2024 (a lista começa em janeiro de 2025).
- Propostas: não entram. A consulta das proposições é o SUAP (suap.camaragyn.go.gov.br/camara/consulta_publica/), cujo
  robots.txt pede que nenhum robô leia nada além da página de entrada ("Disallow: /"); as páginas de projetos do Portal da
  Transparência só levam para lá (o coletor não segue esse redirecionamento), e os relatórios mensais "Atuação e Frequência
  Parlamentar" são PDFs de imagem escaneada.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time

from comum import fonte, hoje, ler_json, log, salvar_json, sem_acento

from . import _base as B
from . import _capitais as C

IBGE, UF, SITE = "5208707", "GO", "https://www.goiania.go.leg.br"
PAGINA = f"{SITE}/institucional/parlamentares"
NG = "https://camaragoiania.nucleogov.com.br"
PAG_CEAP = f"{NG}/cidadao/informacao/mp/id=20"
POR_PAGINA = 100  # linhas por pedido (cada vereador tem uma linha por mês: cabe numa página só)
SUAP = "https://suap.camaragyn.go.gov.br/camara/consulta_publica/"
CASA = {"casa": "Câmara Municipal de Goiânia", "casa_en": "Goiânia City Council", "sigla": "CMG", "site": SITE,
        "sistema": "Portal oficial (HTML) e Portal da Transparência (NúcleoGov)"}
NOME_GASTOS = ("Cota para o Exercício da Atividade Parlamentar (CEAP, Lei 11.308/2024): valor pago a cada vereador no mês",
               "Office allowance (CEAP, Law 11,308/2024): amount paid to each councilor each month")
CACHE_CEAP = B.PASTA_CACHE / IBGE / "ceap.json"
TOLERANCIA = 0.05  # R$: a descrição do mês "fecha" com o valor pago

# a descrição de cada despesa é texto livre (com erros de digitação): cada item vai para um destes grupos, pela primeira
# expressão que bater (sem acento, minúsculas). Conferido em todos os 1.700 itens de jan/2025 a set/2026.
GRUPOS = [
    (r"divulga|parl[a]?mentar$", "Divulgação da atividade parlamentar"),
    (r"co[mp]*b[uú]?s?t", "Combustível"),
    (r"jur", "Consultoria jurídica"),
    (r"cont[aá]?bil", "Consultoria contábil"),
    (r"comunica|marketing|midia|monitoramento", "Consultoria de comunicação e marketing"),
    (r"manuten|esr?critorio|escristorio", "Manutenção de escritório"),
    (r"veiculo", "Locação de veículo"),
    (r"loca\w* de imovel", "Locação de imóvel"),
    (r"gener\w* alim", "Gêneros alimentícios"),
    (r"passage|hospeda|estadia em estac|estacionamento|locomo|pedagio|viage|aliment", "Viagens, estacionamento e pedágio"),
    (r"seguran", "Serviços de segurança"),
    (r"curso|palestra|inscri|evento", "Cursos, palestras e eventos"),
    (r"libras|interprete", "Intérprete de Libras"),
    (r"posta", "Serviços postais"),
    (r"consult|assessoria", "Outras consultorias e assessorias"),
]
SEM_TIPO = "Sem a divisão por tipo (a descrição do mês não soma o valor pago)"
GRUPOS_EN = {  # para pedir no js/traducoes.js (GASTOS)
    "Divulgação da atividade parlamentar": "Publicizing the councilor's work",
    "Combustível": "Fuel", "Consultoria jurídica": "Legal consulting", "Consultoria contábil": "Accounting consulting",
    "Consultoria de comunicação e marketing": "Communication and marketing consulting",
    "Manutenção de escritório": "Office upkeep", "Locação de veículo": "Vehicle rental", "Locação de imóvel": "Property rental",
    "Gêneros alimentícios": "Food supplies", "Viagens, estacionamento e pedágio": "Travel, parking and tolls",
    "Serviços de segurança": "Security services", "Cursos, palestras e eventos": "Courses, talks and events",
    "Intérprete de Libras": "Sign language (Libras) interpreter", "Serviços postais": "Postal services",
    "Outras consultorias e assessorias": "Other consulting and advisory services", "Outras despesas": "Other expenses",
    SEM_TIPO: "Not split by type (the month's description does not add up to the amount paid)",
}

NOTAS = [
    ("As propostas dos vereadores não entram neste site: a Câmara publica as proposições no sistema SUAP, e o arquivo de regras "
     "para robôs desse sistema (robots.txt) pede que nenhum robô leia as páginas dele; os relatórios mensais de projetos e "
     "frequência do site da Câmara são PDFs de imagem escaneada. Dá para procurar cada proposição na consulta pública do SUAP.",
     "Councilors' bills are not included on this site: the City Council publishes its bills in the SUAP system, and that "
     "system's rules file for robots (robots.txt) asks robots not to read its pages; the monthly reports on bills and attendance "
     "on the City Council's website are scanned image PDFs. You can look up each bill in SUAP's public search."),
    ("Os projetos que a prefeitura mandou à Câmara não entram neste site, pelo mesmo motivo: eles também ficam só no SUAP.",
     "The bills the mayor's office sent to the City Council are not included on this site for the same reason: they are also "
     "only in SUAP."),
    ("As votações de cada vereador não entram neste site: a consulta de votações do portal da transparência da Câmara "
     "está vazia, e as atas das sessões (PDF) não trazem o voto de cada vereador.",
     "Each councilor's votes are not included on this site: the votes search on the City Council's transparency portal "
     "is empty, and the session minutes (PDF) do not list each councilor's vote."),
]
NOTA_GASTOS = (
    "Gastos do mandato: os valores da Cota para o Exercício da Atividade Parlamentar (CEAP) pagos a cada vereador, mês a mês, "
    "segundo a página \"Cotas e Gastos Parlamentares\" do Portal da Transparência da Câmara (pelo mês a que a despesa se refere). "
    "Os tipos de despesa vêm da descrição de cada mês, escrita à mão pela Câmara; quando a descrição não soma o valor pago, o "
    "mês aparece como \"sem a divisão por tipo\". Entram só os vereadores em exercício hoje.",
    "Office spending: the amounts of the office allowance (CEAP) paid to each councilor, month by month, according to the "
    "\"Cotas e Gastos Parlamentares\" page of the City Council's Transparency Portal (by the month the expense refers to). The "
    "types of expense come from each month's description, typed by the City Council; when the description does not add up to "
    "the amount paid, that month shows as \"not split by type\". Only councilors in office today are included.")
NOTA_SEM_GASTOS = (
    "Os gastos do mandato não entram nesta leitura: a página \"Cotas e Gastos Parlamentares\" do Portal da Transparência da "
    "Câmara, onde eles ficam, não respondeu. Dá para ver os gastos de cada vereador lá.",
    "Office spending is not included in this reading: the \"Cotas e Gastos Parlamentares\" page of the City Council's "
    "Transparency Portal, where it is published, did not respond. Each councilor's spending can be seen there.")


def pessoas() -> list[dict]:
    t = B.baixar_pagina(PAGINA, IBGE, "parlamentares")
    ini = re.search(r"<h3>\s*\d+ª Legislatura:[^<]*</h3>", t)
    fim = t.find("Parlamentares fora de exerc")
    if not ini or fim < 0:
        raise RuntimeError("a página de parlamentares mudou")
    secao = t[ini.end():fim]
    out = []
    for href, foto, nome, resto in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>\s*<strong>(.*?)</strong>(.*?)</a>', secao, re.S):
        nome = html.unescape(re.sub(r"<[^>]+>", " ", nome)).strip()
        sigla = html.unescape(re.sub(r"<[^>]+>", " ", resto)).strip(" ,\n")
        out.append({"chave": href.rstrip("/").rsplit("/", 1)[-1], "nome": nome, "partido": sigla or None, "foto": foto, "url": href})
    return out


# ------------------------------------------------------------------------------------------------ CEAP
MESES = {sem_acento(m): i + 1 for i, m in enumerate(C.MESES)}


def _mes_ref(mes_txt: str, ano_txt: str | None, processo: str, recebido: str | None) -> tuple[int, int] | None:
    """(ano, mês) de referência. "Setembro/2026" (o ano vem no texto; se faltar, da coluna Ano ou do número do processo,
    "526.2025-56"). Um mês de referência depois do mês em que a Câmara recebeu a prestação de contas é erro de digitação do
    ano (ex.: "Dezembro/2026" recebido em 16/01/2026 = dezembro de 2025)."""
    m = re.match(r"\s*([^\W\d_]+)\s*(?:/\s*(\d{4}))?", sem_acento(mes_txt or "").lower())
    if not m or m.group(1) not in MESES:
        return None
    mes = MESES[m.group(1)]
    ano = m.group(2) or (ano_txt if (ano_txt or "").isdigit() else None)
    if not ano:
        p = re.search(r"\.(\d{4})-", processo or "")
        ano = p.group(1) if p else None
    if not ano:
        return None
    ano = int(ano)
    r = re.match(r"(\d{2})/(\d{2})/(\d{4})", recebido or "")
    if r and (ano, mes) > (int(r.group(3)), int(r.group(2))):
        ano -= 1
    return ano, mes


def _itens(desc: str) -> list[tuple[str, float]]:
    t = html.unescape(re.sub(r"(?i)<br\s*/?>|</p>", "\n", desc or ""))
    t = re.sub(r"<[^>]+>", " ", t).replace("\xa0", " ")
    out = []
    for nome, valor in re.findall(r"([^\n]+?)\s*[-–]\s*(?:R\s*[$4]?\s*)?(\d[\d.]*,\d{1,2}|\d{1,3}(?:\.\d{3})*\.\d{2})(?!\d)", t):
        out.append((re.sub(r"\s+", " ", nome).strip(" :-"), C.brl(valor)))
    return out


def grupo(nome: str) -> str:
    n = sem_acento(nome).lower()
    for exp, g in GRUPOS:
        if re.search(exp, n):
            return g
    return "Outras despesas"


def _linha_api(x: dict) -> dict:
    """Uma linha da lista da página (API da própria página), sem o CPF/CNPJ (jogado fora aqui)."""
    fav = (x.get("favorecido_multidata") or [None])[0] or ""
    mes = html.unescape(x.get("mes_de_referencia") or "")
    ref = _mes_ref(mes, str(x.get("ano") or ""), x.get("numero_do_processo") or "", x.get("data_de_recebimento"))
    return {"id": str(x.get("id")), "processo": (x.get("numero_do_processo") or "").strip(), "ref": list(ref) if ref else None,
            "mesTexto": mes.strip(), "favorecido": html.unescape(fav).strip(), "itens": _itens(x.get("descrio") or ""),
            "recebido": (x.get("data_de_recebimento") or "").strip(), "pago": C.brl(x.get("valor_pago"))}


def _pedir_api(rede: C.Rede, dados: dict, multi: bool = False):
    h = {"X-NucleoGov-Services": "true", "X-Requested-With": "XMLHttpRequest", "Referer": PAG_CEAP}
    b, ct = rede.pedir(f"{NG}/api" if multi else f"{NG}/api/modulos_personalizados", dados, headers=h)
    return json.loads(b.decode("utf-8-sig"))


def _linhas_de(rede: C.Rede, nome: str) -> list[dict]:
    """As linhas de um vereador (o filtro "Favorecido" da página: um pedido, com todas as linhas dele numa página só, para a
    ordem das páginas não importar)."""
    params = {"r1": {"filtros_selects": {"favorecido": nome}, "modulo": "20", "limit": f"0, {POR_PAGINA}",
                     "acao": "modulos_personalizados/listarLinhasModulo"}}
    d = _pedir_api(rede, {"multi_request": "true", "params": json.dumps(params)}, multi=True)["r1"]
    linhas = [_linha_api(x) for x in d.get("dados") or []]
    if int(d.get("total") or 0) != len(linhas):
        raise RuntimeError(f"CEAP de {nome}: a página diz {d.get('total')} linhas e vieram {len(linhas)}")
    if any(chave_fav(l["favorecido"]) != chave_fav(nome) for l in linhas):
        raise RuntimeError(f"CEAP de {nome}: o filtro devolveu linhas de outra pessoa")
    return linhas


def chave_fav(s: str | None) -> str:
    return " ".join(_palavras(s or ""))


def ler_ceap(rede: C.Rede, por_chave: dict[str, dict]) -> tuple[list[dict], dict[str, str], set]:
    """(linhas, {nome do favorecido: id da pessoa}, favorecidos que não são de quem está no cargo) da "Cotas e Gastos
    Parlamentares", lidas como a página lê: a lista de nomes do filtro "Favorecido" e, para cada vereador em exercício, as
    linhas dele (o filtro da página). Lida de novo a cada 6 dias (a Câmara publica um mês por vez); o que foi lido fica em
    .cache/camaras/5208707/ceap.json (sem o CPF)."""
    e = ler_json(CACHE_CEAP, {}) or {}
    h = hoje()
    if e.get("lido") and (dt.date.fromisoformat(h) - dt.date.fromisoformat(e["lido"])).days < 6 and e.get("ligacao"):
        validos = {m["id"] for m in por_chave.values()}
        if set(e["ligacao"].values()) <= validos:
            return e["linhas"], e["ligacao"], set(e.get("fora") or [])
    rede.pedir(PAG_CEAP)  # abre a página, como o navegador (cookies)
    nomes = [x["valor"].strip() for x in _pedir_api(rede, {"acao": "get_valores_relacao", "table": "vereadores", "column": "nome",
                                                           "condicao": "desativado <> 1"}) if (x.get("valor") or "").strip()]
    if len(nomes) < 30:
        raise RuntimeError(f"a lista de favorecidos da CEAP veio com {len(nomes)} nomes")
    ligacao, fora = ligar_favorecidos(nomes, por_chave)
    linhas = []
    for nome in sorted(ligacao):
        linhas += _linhas_de(rede, nome)
    salvar_json(CACHE_CEAP, {"lido": h, "ligacao": ligacao, "fora": sorted(fora), "linhas": linhas})
    return linhas, ligacao, fora


def _palavras(s: str) -> list[str]:
    return [p for p in re.sub(r"[^a-z ]", " ", sem_acento(s or "").lower()).split() if p not in ("da", "de", "do", "das", "dos", "e")]


def ligar_favorecidos(nomes: list[str], por_chave: dict[str, dict]) -> tuple[dict[str, str], set]:
    """{nome do favorecido: id da pessoa} pelo nome civil do TSE de quem está no cargo: igual, ou com todas as palavras do
    nome da CEAP dentro do nome civil (só quando uma pessoa só serve). Os outros (quem saiu do cargo) ficam fora."""
    civis = {}
    for m in por_chave.values():
        cand = m.get("_cand") or {}
        for n in (cand.get("nome"), m.get("nomeCivil")):
            if n:
                civis.setdefault(m["id"], set()).add(" ".join(_palavras(n)))
    out, fora = {}, set()
    for fav in set(nomes):
        k = " ".join(_palavras(fav))
        iguais = [pid for pid, ns in civis.items() if k in ns]
        if not iguais:
            ks = set(k.split())
            iguais = [pid for pid, ns in civis.items() if any(ks <= set(n.split()) for n in ns)] if len(ks) >= 2 else []
        if len(iguais) == 1:
            out[fav] = iguais[0]
        else:
            fora.add(fav)
    return out, fora


def gastos(linhas: list[dict], ligacao: dict[str, str], h: str) -> dict[str, dict]:
    por: dict[str, dict[tuple, dict[str, float]]] = {}
    for l in linhas:
        pid = ligacao.get(l["favorecido"])
        if not pid or not l["ref"] or l["pago"] is None:
            continue
        mes = por.setdefault(pid, {}).setdefault(tuple(l["ref"]), {})
        itens = l["itens"]
        if itens and all(v is not None for _, v in itens) and abs(sum(v for _, v in itens) - l["pago"]) <= TOLERANCIA:
            for nome, v in itens:
                g = grupo(nome)
                mes[g] = mes.get(g, 0.0) + v
        else:
            mes[SEM_TIPO] = mes.get(SEM_TIPO, 0.0) + l["pago"]
    ultimo = max((tuple(l["ref"]) for l in linhas if l["ref"]), default=None)
    f = fonte(CASA["casa"], "Portal da Transparência: Cotas e Gastos Parlamentares (CEAP), de janeiro de 2025 a "
              + (f"{C.nome_mes(ultimo[1])} de {ultimo[0]}" if ultimo else "hoje"), PAG_CEAP, h)
    out = {}
    for pid, por_mes in por.items():
        b = C.bloco_gastos(por_mes, NOME_GASTOS, f)
        if b:
            out[pid] = b
    return out


def coletar() -> dict:
    t0 = time.time()
    h = hoje()
    rede = C.Rede()
    casa = dict(CASA, fonte=fonte(CASA["casa"], "Parlamentares da 20ª Legislatura em exercício (portal oficial)", PAGINA, h))
    membros, por_chave, tse = C.membros(IBGE, UF, casa, pessoas(), 37)
    extras = {m["id"]: C.extras_base(m, casa) for m in por_chave.values()}
    try:
        linhas, ligacao, fora = ler_ceap(rede, por_chave)
        blocos = gastos(linhas, ligacao, h)
        if fora:
            log(f"  CMG: CEAP de quem não está no cargo hoje (fica fora): {', '.join(sorted(fora))}")
    except Exception as erro:  # os gastos são um extra (e o fim da rodada também cai aqui): fica o que já estava publicado
        log(f"  CMG: CEAP: {type(erro).__name__}: {str(erro)[:200]}; ficam os gastos publicados antes")
        blocos = C.publicados(IBGE, "gastos")
    for pid, b in blocos.items():
        if pid in extras:
            extras[pid]["gastos"] = b
            extras[pid]["fontes"].append(b["fonte"])
    cobertura = {"lista": True, "propostas": False, "votacoes": False, "gastos": any(x.get("gastos") for x in extras.values())}
    notas = NOTAS + [NOTA_GASTOS if cobertura["gastos"] else NOTA_SEM_GASTOS]
    r = B.salvar(IBGE, UF, casa, membros, extras, cobertura, notas)
    r["requisicoes"] = rede.n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMG: {len(membros)} no cargo, {r.get('vereadoresComGastos', 0)} com gastos (CEAP), {rede.n} pedidos, "
        f"{rede.bytes / 1e6:.1f} MB, {time.time() - t0:.0f} s")
    return r
