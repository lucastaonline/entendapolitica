"""Leitura das proposições e dos gastos dos gabinetes da Câmara Municipal de Porto Alegre (usado por c4314902.py; frente
capitais-b-r6, 27/10/2026).

Propostas: a consulta de projetos do site da Câmara (www.camarapoa.rs.gov.br/processos) é a fonte oficial. Ela tem:
- a exportação em CSV da busca (botão "Exportar... CSV", até 2.000 linhas por tipo, das mais novas para as mais antigas):
  número e ano do processo, tipo e número do projeto, ementa, data e setor da última tramitação, autores, situação;
- a lista da busca (20 por página), de onde vem o número interno de cada processo (o endereço /processos/<número>);
- a página de cada processo: data de abertura, autores, situação, situação plenária, os documentos (o texto da lei, quando o
  projeto vira lei: "Lei nº 14.407/25"), as votações e as tramitações (setor, chegada, saída, situação).
Tipos que entram: PLL e PLE (projetos de lei do Legislativo e do Executivo), PLCL e PLCE (de lei complementar), PELO, PDL e PR.
A página de cada processo é lida na primeira carga (~1.650 páginas, 1 s entre elas: ~1 hora) e depois de novo pela idade da
leitura: as novas e as que mudaram no CSV logo; as aprovadas que esperam a lei a cada 3 dias; as em discussão a cada 7 dias
(14, se a última tramitação tem mais de um mês); as que já terminaram (lei, arquivada, rejeitada, retirada) a cada 60 dias
(cada processo com o seu prazo, de metade a uma vez e meia esse tempo, para as releituras não se juntarem no mesmo dia).
O CSV da busca nem sempre acompanha a página do processo (a situação e a "última tramitação" dele às vezes ficam para trás, e
as colunas "Veto" e "Lei" vêm quase sempre vazias): a situação publicada é sempre a da página do processo.

Gastos: o Portal Transparência da Câmara (transparencia.camarapoa.rs.gov.br/gastos/vereadores) mostra os lançamentos da
cota de cada gabinete (Quota Básica Mensal, QBM) por mês, lidos da API pública do próprio portal
(portal-api.camarapoa.rs.gov.br/v1/lancamentos.json?mes=MM/AAAA: um pedido traz os lançamentos de todos os gabinetes do
mês). Créditos (a cota do mês) não são gastos; os débitos (valores negativos) são.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse

from comum import hoje, log

from . import _base as B
from . import _paginas as P

IBGE = "4314902"
SITE = "https://www.camarapoa.rs.gov.br"
API = "https://portal-api.camarapoa.rs.gov.br/v1"
TRANSPARENCIA = "https://transparencia.camarapoa.rs.gov.br"
PAUSA = 1.0
# tipo do sistema -> tipo comum do site
TIPOS = {"PLL": "PL", "PLE": "PL", "PLCL": "PLP", "PLCE": "PLP", "PELO": "PELO", "PDL": "PDL", "PR": "PRC"}
XHR = {"Accept": "text/javascript, application/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
JSON_H = {"Accept": "application/json, text/javascript, */*; q=0.01", "Origin": TRANSPARENCIA,
          "Referer": f"{TRANSPARENCIA}/gastos/vereadores"}
REVER_APROVADAS_DIAS = 3   # aprovadas que esperam a lei
REVER_ABERTAS_DIAS = 7     # em discussão, com tramitação no último mês
REVER_PARADAS_DIAS = 14    # em discussão, sem tramitação há mais de um mês
REVER_FINAIS_DIAS = 60     # lei, arquivada, rejeitada, retirada, prejudicada
PAGINAS_POR_RODADA = 400   # páginas de processo por rodada depois da primeira carga (~30 minutos)


def _busca(tipo: str, pagina: int | None = None, formato: str = "") -> str:
    q = {"andamento": "todos", "aprovados_em": "", "autor": "", "busca": "", "tipo": tipo, "utf8": "✓"}
    if pagina:
        q["page"] = str(pagina)
    return f"{SITE}/projetos{formato}?" + urllib.parse.urlencode(q)


def _txt(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def ler_csv(rede: P.Rede, tipo: str, desde_ano: int) -> list[dict]:
    """As linhas do CSV da busca de um tipo, com ano do processo >= desde_ano."""
    b = rede.pedir(_busca(tipo, formato=".csv"), timeout=180)
    t = b.decode("utf-8-sig", "replace")
    linhas = list(csv.DictReader(io.StringIO(t)))
    if linhas and not {"Número", "Ano", "Tipo", "Matéria", "Autores", "Situação"} <= set(linhas[0]):
        raise RuntimeError(f"o CSV de {tipo} mudou de colunas: {list(linhas[0])}")
    out = []
    for r in linhas:
        try:
            ano = int(r.get("Ano") or 0)
        except ValueError:
            continue
        if ano >= desde_ano:
            out.append({k: (v or "").strip() for k, v in r.items() if k})
    if len(linhas) >= 2000 and out and len(out) == len(linhas):
        raise RuntimeError(f"o CSV de {tipo} veio cortado (2.000 linhas) antes de chegar a {desde_ano}")
    return out


def ler_ids(rede: P.Rede, tipo: str, faltam: set[str], desde_ano: int) -> dict[str, str]:
    """{matéria ("474/26"): número interno do processo} pela lista da busca (20 por página), até achar as que faltam."""
    achados: dict[str, str] = {}
    pagina, velhas = 1, 0
    while faltam - set(achados):
        t = rede.pedir(_busca(tipo, pagina), cabecalhos=XHR).decode("utf-8", "replace")
        js = t.replace('\\"', '"').replace("\\/", "/").replace("\\n", "\n")
        itens = re.findall(r'<h2 class="header"><a target="_blank" href="/processos/(\d+)">\s*PROC\.\s*\d+/(\d{2})\s*-\s*'
                           r'([A-Z]+)\s*(\d+/\d{2})\s*</a>', js)
        if not itens:
            break
        for pid, ano_proc, tp, materia in itens:
            if tp == tipo:
                achados[materia] = pid
        # a lista não é estritamente por ano: só para depois de 3 páginas seguidas só com processos mais antigos
        velhas = velhas + 1 if all(2000 + int(a) < desde_ano and 2000 + int(m.split("/")[1]) < desde_ano
                                   for _, a, _, m in itens) else 0
        if velhas >= 3 or pagina > 300:
            break
        pagina += 1
    return achados


def ler_processo(rede: P.Rede, pid: str) -> dict:
    """A página do processo: dados, documentos, votações e tramitações."""
    t = rede.pedir(f"{SITE}/processos/{pid}").decode("utf-8", "replace")
    dados = {}
    for dt_, dd in re.findall(r"(?s)<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", t):
        dados[B.norm(_txt(dt_)).rstrip(":").replace("\ufffd", "")] = _txt(dd)
    if not dados:
        raise RuntimeError(f"a página do processo {pid} mudou de formato")
    docs = [[_txt(nome), url] for url, nome in re.findall(
        r'<a target="_blank" href="(https?://[^"]*/draco/processos/[^"]+)"><i[^>]*></i><span>(.*?)</span></a>', t, re.S)]
    vot = []
    tab = t.split('data-tab="votacoes"><table', 1)[1].split("</table>", 1)[0] if 'data-tab="votacoes"><table' in t else ""
    for r in re.findall(r'(?s)<tr class="votacao">(.*?)</tr>', tab):
        c = [_txt(x) for x in re.findall(r"(?s)<td>(.*?)</td>", r)]
        if len(c) >= 6:
            vot.append([P.data_br(c[0]), c[1], c[2], c[3], c[4], c[5]])
    tram = []
    tab = t.split('summary="Tramita', 1)[1].split("</table>", 1)[0] if 'summary="Tramita' in t else ""
    for r in re.findall(r"(?s)<tr>(.*?)</tr>", tab):
        c = [_txt(x) for x in re.findall(r"(?s)<td>(.*?)</td>", r)]
        if len(c) >= 4:
            tram.append([c[0], P.data_br(c[1]), P.data_br(c[2]), c[3]])

    def campo(*nomes):
        for n in nomes:
            for k, v in dados.items():
                if k.startswith(n):
                    return v
        return None
    return {"abertura": P.data_br(campo("data da abertura")), "autores": campo("autores"), "situacao": campo("situa"),
            "plenaria": next((v for k, v in dados.items() if "plenaria" in k or "plen" in k), None),
            "ultima": P.data_br(campo("ultima", "ltima")), "docs": docs, "votacoes": vot, "tram": tram}


def ler_propostas(rede: P.Rede, e: dict, h: str) -> bool:
    desde = int(B.INICIO[:4])
    itens = e.setdefault("itens", {})
    if e.get("csv") != h or not e.get("completo"):
        vistos = set()
        for tipo in TIPOS:
            for r in ler_csv(rede, tipo, desde):
                k = f"{tipo} {r['Matéria']}"
                vistos.add(k)
                x = itens.setdefault(k, {})
                if x.get("ult") != r.get("Dt. Tramitação"):
                    x["pendente"] = True
                x.update({"tipo": tipo, "materia": r["Matéria"], "proc": f"{r['Número']}/{r['Ano']}", "ano": int(r["Ano"]),
                          "ementa": r.get("Ementa"), "autores_csv": r.get("Autores"), "sit_csv": r.get("Situação"),
                          "veto": r.get("Veto") or None, "lei_csv": r.get("Lei") or None, "ult": r.get("Dt. Tramitação")})
            P.guardar_estado(IBGE, e)
        for k in [k for k in itens if k not in vistos]:
            itens.pop(k)
        e["csv"] = h
        P.guardar_estado(IBGE, e)
    # o número interno de cada processo (para o endereço da página); o que não foi achado é procurado de novo em 7 dias
    for tipo in TIPOS:
        faltam = {x["materia"] for x in itens.values() if x["tipo"] == tipo and not x.get("pid")
                  and P.dias_desde(x.get("pid_procurado"), h) >= 7}
        if faltam:
            ids = ler_ids(rede, tipo, faltam, desde)
            for x in itens.values():
                if x["tipo"] == tipo and x["materia"] in ids:
                    x["pid"] = ids[x["materia"]]
                elif x["tipo"] == tipo and x["materia"] in faltam:
                    x["pid_procurado"] = h
            P.guardar_estado(IBGE, e)
    # a página de cada processo: na primeira carga, todas; depois, as novas, as que mudaram no CSV e um rodízio pela idade da
    # leitura (o CSV da busca nem sempre acompanha a página do processo: a "última tramitação" dele às vezes fica para trás)
    n = 0
    completo = bool(e.get("completo"))

    def vencida(x) -> bool:
        pag = x.get("pag")
        if pag is None or x.get("pendente"):
            return True
        st = situacao(x)[0][0]
        idade = P.dias_desde(pag.get("lida"), h)
        # o prazo de cada processo varia de 0,5 a 1,5 vez o do grupo (pelo número do processo): depois da primeira carga,
        # as releituras não caem todas no mesmo dia
        fator = 0.5 + (int(x["pid"]) % 97) / 96
        if st in ("lei", "arquivada", "rejeitada", "retirada", "parada"):
            return idade >= REVER_FINAIS_DIAS * fator
        if st == "aprovada":
            return idade >= REVER_APROVADAS_DIAS * fator
        return idade >= (REVER_ABERTAS_DIAS if P.dias_desde(pag.get("ultima"), h) <= 30 else REVER_PARADAS_DIAS) * fator

    fila = sorted((kv for kv in itens.items() if kv[1].get("pid") and vencida(kv[1])),
                  key=lambda kv: (kv[1].get("pag") is not None, not kv[1].get("pendente"), (kv[1].get("pag") or {}).get("lida") or ""))
    try:
        for k, x in fila:
            if completo and n >= PAGINAS_POR_RODADA:
                break
            x["pag"] = ler_processo(rede, x["pid"])
            x["pag"]["lida"] = h
            x["pendente"] = False
            n += 1
            if n % 25 == 0:
                P.guardar_estado(IBGE, e)
    except P.SemTempo:
        P.guardar_estado(IBGE, e)
        if not completo:
            raise  # primeira carga: nada é publicado pela metade
        log(f"  CMPA: fim do tempo da rodada depois de {n} páginas de processos; o resto fica para a próxima (publica o que "
            "já foi lido, cada processo com a sua última leitura completa)")
    sem_pid = [k for k, x in itens.items() if not x.get("pid")]
    if sem_pid:
        log(f"  CMPA: {len(sem_pid)} projetos sem o número interno do processo (ficam fora): {sem_pid[:8]}")
    e["completo"] = True
    P.guardar_estado(IBGE, e)
    return True


# ---------------------------------------------------------------- situação
_LEI = re.compile(r"^(lei complementar|lei|resolucao|decreto legislativo|emenda a lei organica)\s*(?:n[o.º°]*\s*)?"
                  r"([\d.]+)\s*/\s*(\d{2,4})")


def _tem_lei(pag: dict, desde_ano: int | None = None) -> tuple | None:
    """(tipo, número, ano, link, data) do documento da norma no processo ("Lei nº 14.407/25", "Lei Complementar 1.036/25").
    O número do nome do arquivo ("Lei_14539.pdf") vale quando o nome escrito no documento diverge dele (erro de digitação:
    "Lei nº 13.539/26"); a data vem do nome do arquivo quando ele a traz ("Resolução_nº_3.003__de_24-06-26.pdf"). Uma norma
    de antes do ano do processo é outra (uma lei citada), não a que o projeto virou."""
    for nome, url in pag.get("docs") or []:
        m = _LEI.match(B.norm(nome))
        if m:
            ano = int(m.group(3))
            ano = ano + 2000 if ano < 100 else ano
            if desde_ano and ano < desde_ano:
                continue
            num = int(m.group(2).replace(".", ""))
            arq = re.search(r"/(?:lei|lc|lei_complementar|resolucao)_?(\d{3,6})(?:_-_[a-z_]+)?\.pdf$", url, re.I)
            if arq and int(arq.group(1)) != num:
                num = int(arq.group(1))
            d = re.search(r"_de_(\d{2})-(\d{2})-(\d{2})\.pdf$", urllib.parse.unquote(url))
            data = f"20{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None
            return m.group(1), num, ano, url, data
    return None


def _veto(x: dict, pag: dict) -> tuple[str, str | None] | None:
    """("total"|"parcial", "mantido"|"derrubado"|"parte"|None) pela página do processo: o documento "Veto Total"/"Veto
    Parcial", a tramitação mais nova sobre o veto ("VETO MANTIDO", "VETO REJEITADO", "VETO-PARCIALMENTE MANTIDO", "VETO EM
    APRECIACAO") e a votação do veto ("Projeto rejeitado/Veto mantido"; no veto parcial, "Rejeitado" = a parte vetada caiu,
    o veto ficou; "Aprovado" = a Câmara derrubou o veto). A coluna "Veto" do CSV só vale quando a página não diz nada."""
    docs = [B.norm(d[0]) for d in pag.get("docs") or []]
    csv_v = B.norm(x.get("veto"))
    sit = B.norm(pag.get("situacao"))
    total = any(d.startswith("veto total") for d in docs)
    parcial = not total and any(d.startswith("veto parcial") for d in docs)
    if not (total or parcial) and csv_v:
        total, parcial = "total" in csv_v, "parcial" in csv_v
    if not (total or parcial) and sit.startswith("veto"):
        total, parcial = "parcial" not in sit, "parcial" in sit
    if not (total or parcial):
        return None
    decisao = None
    for t in pag.get("tram") or []:  # da mais nova para a mais antiga, como na página
        s = B.norm(t[3])
        if "veto" not in s:
            continue
        if "parcialmente mantido" in s:
            decisao = "parte"
        elif "mantid" in s:
            decisao = "mantido"
        elif "rejeitad" in s or "derrubad" in s:
            decisao = "derrubado"
        break
    if decisao is None:
        vv = sorted((v for v in pag.get("votacoes") or [] if re.search(r"- veto (total|parcial)$", B.norm(v[1]))),
                    key=lambda v: v[0] or "")
        if vv:
            r = B.norm(vv[-1][5])
            decisao = ("mantido" if "veto mantido" in r or r.startswith("rejeitad") else
                       "derrubado" if "veto rejeitado" in r or r.startswith("aprovad") else None)
    if decisao is None and csv_v:
        decisao = ("parte" if "parte mantido" in csv_v else "mantido" if "mantido" in csv_v else
                   "derrubado" if "rejeitado" in csv_v else None)
    return ("total" if total else "parcial"), decisao


NOME_NORMA = {"lei": "Lei", "lei complementar": "Lei Complementar", "resolucao": "Resolução", "decreto legislativo":
              "Decreto Legislativo", "emenda a lei organica": "Emenda à Lei Orgânica"}


def situacao(x: dict) -> tuple[tuple, str | None, str | None, dict | None]:
    """((status, statusTxt, statusTxt_en), situação oficial, data, lei) de um processo (regras conferidas à mão; ver as notas
    da frente capitais-b-r6):
    - documento "Lei nº ..."/"Lei Complementar ..."/"Resolução nº ..." no processo = virou norma (o link é o do texto); com
      veto parcial que não foi todo derrubado = "com partes vetadas";
    - veto total (documento "Veto Total", tramitação e votação do veto): mantido = rejeitada; derrubado = aprovada, falta
      promulgar; sem decisão = vetada, esperando a Câmara decidir; veto parcial sem o documento da lei = virou lei, com
      partes vetadas;
    - situação plenária "APROVADO" sem a lei: processo ainda aberto = aprovada, esperando a sanção (ou a promulgação);
      processo já arquivado = aprovada (a página não traz o documento da lei);
    - situação plenária "REJEITADO" = rejeitada; "RETIRADO" = retirada; "PREJUDICADO" = parada;
    - situação do processo "ARQUIVADO" (sem aprovação) = arquivada; "ANEXADO A OUTRO PROCESSO" = andando junto;
    - o resto = ainda em discussão."""
    pag = x.get("pag") or {}
    plen = B.norm(pag.get("plenaria"))
    sit = B.norm(pag.get("situacao") or x.get("sit_csv"))
    comum = TIPOS[x["tipo"]]
    hj = hoje()
    datas = [d for d in (pag.get("ultima"), *(t[1] for t in pag.get("tram") or [])) if d and d <= hj]
    ult = max(datas) if datas else (P.data_br(x.get("ult")) if x.get("ult") else None)
    oficial = " / ".join(v for v in (pag.get("situacao") or x.get("sit_csv"), f"Situação plenária: {pag.get('plenaria')}"
                                     if pag.get("plenaria") else None) if v)
    lei = _tem_lei(pag, x.get("ano"))
    veto = _veto(x, pag)
    if lei:
        tipo_n, num, ano, url, data_lei = lei
        nome = B.nome_norma(NOME_NORMA[tipo_n], num, ano)
        parcial = bool(veto) and veto[0] == "parcial" and veto[1] != "derrubado"
        st = ("lei", B.virou(nome, parcial), None)
        if tipo_n == "emenda a lei organica":
            st = ("lei", st[1], "Became an amendment to the city's Organic Law" + (" (with some parts vetoed)" if parcial else ""))
        return st, f"{nome} (documento do processo)", data_lei, {"nome": nome, "url": url}
    if veto and veto[0] == "total":
        if veto[1] == "mantido":
            return ("rejeitada", *B.TXT["veto_mantido"]), oficial, ult, None
        if veto[1] == "derrubado":
            return ("aprovada", *B.TXT["veto_derrubado"]), oficial, ult, None
        return ("rejeitada", *B.TXT["veto_total_pendente"]), oficial, ult, None
    if veto:
        return ("lei", *B.TXT["veto_parcial"]), oficial, ult, None
    if plen.startswith("aprovad"):
        if sit.startswith("arquivad"):
            return ("aprovada", *SEM_LEI), oficial, ult, None
        ch = "promulgar" if comum in ("PDL", "PRC", "PELO") else "sancao"
        return ("aprovada", *B.TXT[ch]), oficial, ult, None
    if plen.startswith("rejeitad"):
        return ("rejeitada", None, None), oficial, ult, None
    if plen.startswith("retirad") or "retirad" in sit:
        return ("retirada", None, None), oficial, ult, None
    if plen.startswith("prejudicad") or "prejudicad" in sit:
        return ("parada", None, None), oficial, ult, None
    if sit.startswith("arquivad"):
        return ("arquivada", None, None), oficial, ult, None
    if "anexado" in sit:
        return ("junta", None, None), oficial, ult, None
    return ("andando", None, None), oficial, ult, None


SEM_LEI = ("Aprovada pela Câmara; a página do processo não traz o documento da lei",
           "Approved by the City Council; the bill's page does not include the law document")


def sigla(x: dict) -> str:
    n, a = x["materia"].split("/")
    return f"{x['tipo']} {int(n)}/{2000 + int(a) if len(a) == 2 else a}"


def ementa(x: dict) -> str | None:
    """A ementa do CSV sem o número do processo eletrônico que vem no começo ("210.00405/2026-47 - DISPÕE...")."""
    t = re.sub(r"^\s*\d{3}\.\d{5}/\d{4}-\d{2}\s*[-–]?\s*", "", x.get("ementa") or "").strip()
    return t or None


def url_processo(x: dict) -> str:
    return f"{SITE}/processos/{x['pid']}"


# ---------------------------------------------------------------- autores
def autores(texto: str | None, protegidos: list[str]) -> tuple[list[str], bool]:
    """(nomes na ordem, "e outros"?) de "Ver. A e Ver.ª B", "Verª A, Ver. B e Ver. C", "A e outros". Nomes de mandatos que
    têm " e " no meio ("Giovani Culau e Coletivo") são protegidos antes de separar."""
    t = re.sub(r"\s+", " ", (texto or "").strip()).rstrip(" .")
    outros = bool(re.search(r"\be (outros|outras|demais)\b", t, re.I))
    t = re.sub(r"\s+e\s+(outros|outras|demais.*)$", "", t, flags=re.I)
    marcas = {}
    for i, p in enumerate(sorted(protegidos, key=len, reverse=True)):
        if " e " in p.lower():
            pad = re.compile(re.escape(p), re.I)
            if pad.search(t):
                marcas[f"§{i}§"] = p
                t = pad.sub(f"§{i}§", t)
    partes = [x.strip() for x in re.split(r"\s*,\s*|\s+e\s+(?=(?:ver\b|ver\.|verª|vers|vereador|§))|\s+e\s+", t, flags=re.I) if x.strip()]
    out = []
    for p in partes:
        for k, v in marcas.items():
            p = p.replace(k, v)
        out.append(p)
    return out, outros


NOME_GASTOS = ("Cota mensal do gabinete (QBM), segundo o Portal Transparência da Câmara",
               "Monthly office allowance (QBM), according to the City Council's Transparency Portal")
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
            "dezembro"]


def gastos_por_gabinete(meses: dict) -> dict[str, dict[str, dict[str, float]]]:
    """{nome do gabinete ("Gab. Ver(a). Fulano"): {"AAAA-MM": {tipo: valor}}}. A conta é a do próprio portal ("Valores
    utilizados"), conferida centavo a centavo com o total de cada mês: entram os débitos (valores negativos) de todas as
    categorias menos "Créditos QBM" (a cota do mês e as transferências de saldo), descontados os estornos que o portal
    lança numa categoria de gasto; estornos sem categoria não descontam (como no portal)."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    for k, m in meses.items():
        for l in m.get("lancamentos") or []:
            cat, setor = l.get("categoria"), re.sub(r"\s+", " ", (l.get("setor") or "")).strip()
            try:
                v = float(l.get("valor") or 0)
            except ValueError:
                continue
            if cat == "Créditos QBM" or not setor or (v > 0 and cat is None):
                continue
            tipos = out.setdefault(setor, {}).setdefault(k, {})
            t = cat or "Outros"
            tipos[t] = tipos.get(t, 0.0) - v
    return out


def bloco_gastos(por_mes: dict[str, dict[str, float]], fonte_g: dict) -> dict | None:
    """O bloco "gastos" do perfil (o mesmo formato de São Paulo e das Assembleias): o ano mais recente com gastos, por tipo,
    e o total desde o primeiro mês."""
    meses = sorted(k for k, t in por_mes.items() if round(sum(t.values()), 2))
    if not meses:
        return None
    ano = meses[-1][:4]
    do_ano = [k for k in sorted(por_mes) if k[:4] == ano]
    por_tipo: dict[str, float] = {}
    for k in do_ano:
        for t, v in por_mes[k].items():
            por_tipo[t] = por_tipo.get(t, 0.0) + v
    total_mandato = round(sum(sum(t.values()) for t in por_mes.values()), 2)
    return {"ano": int(ano), "total": round(sum(por_tipo.values()), 2),
            "porTipo": [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(por_tipo.items(), key=lambda kv: (-kv[1], kv[0]))
                        if round(v, 2)],
            "mandatoTotal": total_mandato, "desde": meses[0], "meses": [do_ano[0], do_ano[-1]],
            "nome": NOME_GASTOS[0], "nome_en": NOME_GASTOS[1], "fonte": fonte_g}


# ---------------------------------------------------------------- gastos (QBM)
def ler_gastos(rede: P.Rede, e: dict, h: str) -> dict:
    """{"AAAA-MM": [lançamentos do mês]} desde janeiro de 2025 (os meses passados ficam guardados; os 3 mais novos são
    relidos todo dia, porque ainda podem mudar)."""
    meses = e.setdefault("meses", {})
    ano_h, mes_h = int(h[:4]), int(h[5:7])
    for ano in range(int(B.INICIO[:4]), ano_h + 1):
        for mes in range(1, 13):
            if (ano, mes) > (ano_h, mes_h):
                break
            k = f"{ano}-{mes:02d}"
            recente = (ano * 12 + mes) >= (ano_h * 12 + mes_h - 2)
            if k in meses and not (recente and meses[k].get("lido") != h):
                continue
            url = f"{API}/lancamentos.json?" + urllib.parse.urlencode({"mes": f"{mes}/{ano}", "agregadores": "true"})
            d = json.loads(rede.pedir(url, cabecalhos=JSON_H).decode("utf-8"))
            if not isinstance(d.get("lancamentos"), list):
                raise RuntimeError("a API de gastos dos gabinetes mudou de formato")
            meses[k] = {"lido": h, "gastos": d.get("gastos"), "lancamentos": [
                {"setor": (l.get("setor") or {}).get("nome"), "setor_id": (l.get("setor") or {}).get("id"),
                 "valor": l.get("valor"), "categoria": (l.get("categoria_raiz") or {}).get("nome"),
                 "subcategoria": (l.get("categoria") or {}).get("nome"), "descricao": l.get("descricao")}
                for l in d["lancamentos"]]}
            P.guardar_estado(IBGE, e, "gastos")
    return meses
