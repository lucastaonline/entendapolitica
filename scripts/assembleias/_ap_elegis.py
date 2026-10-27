"""e-Legis da Assembleia Legislativa do Amapá (Alap): as propostas dos deputados estaduais e o que o governo do estado
mandou, sancionou e vetou (perfil do governador). Usado por scripts/assembleias/ap.py.

O e-Legis (https://elegis.al.ap.leg.br/portal) é o sistema do processo legislativo da Alap desde 2025-2026; ele trouxe do
sistema antigo (SILEGIS) as proposições dos anos anteriores ("Documento Importado do SILEGIS") e avisa que, durante a
mudança, as informações podem não aparecer em tempo real. O robots.txt dele libera tudo ("Disallow:" vazio, sem
Crawl-delay); mesmo assim, um pedido por vez, com PAUSA segundos entre dois pedidos, e cache em .cache/alap-elegis/.

O que é lido:
- Listas de proposições por tipo e ano (/portal/proposicoes?tipo_proposicao=<t>&ano=<a>, 50 por página, com a data de
  protocolo, o número oficial, a origem e a ementa). A lista conta também as proposições que não mostra (a busca diz "375
  encontradas" e mostra 372): essas não entram, e o número delas vai para o log.
- A página de cada proposição (/portal/proposicao/<id>): a norma que ela gerou (no título), a origem, a data de protocolo e
  a movimentação, da mais nova para a mais antiga. A situação de cada proposta sai daí (situacao()).
- O cadastro de legislação em CSV (/portal/legislacao-csv?tipo_proposicao_id=<1 lei ordinária | 2 complementar>&ano=<ano
  da proposição>): número, data e publicação de cada lei, e o projeto de onde ela veio.
- As mensagens de veto do governo (tipo "Veto", /portal/proposicoes?tipo_proposicao=6&ano=<a>): número da mensagem, data
  de protocolo e, na ementa, "Veto Total"/"Veto Parcial" e o projeto vetado.
- Duas situações oficiais da busca ("Devolvido ao Autor" e "Rejeitado pela CCJ", filtro status=<código>&ano=<a>), que às
  vezes não aparecem na movimentação dos projetos trazidos do sistema antigo (SITUACOES_OFICIAIS).

Rodada de todo dia (cache cheio, ~135 pedidos, ~4 min): as listas e o CSV de leis do ano (as do ano anterior a cada 3 dias,
o CSV todo dia; as mais antigas, uma vez por semana), as páginas das proposições novas e, por rodízio, as das que ainda
podem mudar (a cada 2 ou 6 dias) e as já terminadas (a cada ~2 meses), até LIMITE_S segundos.
Primeira carga (cache vazio, como no robô): ~2.450 pedidos (~78 min com a pausa); usa o resto da rodada (_carga.py) e
continua no dia seguinte; enquanto faltar alguma página, nada de propostas nem do governador é gravado (ficam os blocos
publicados antes). Internet fora (sem DNS, sem conexão) para a leitura sem contar como defeito da página.
"""
from __future__ import annotations

import csv
import datetime as dt
import html as _html
import io
import re
import time
import urllib.parse

import regional
from comum import STATUS_TXT, fonte, hoje, log, sem_acento

from . import _carga
from . import _nco_gov as G
from ._nco_comum import ESCOPO, ESCOPO_EN, Rede, SemTempo, com_status_en, resumo_status
from ._votos_gastos import Nomes

BASE = "https://elegis.al.ap.leg.br/portal"
VEICULO = "Assembleia Legislativa do Amapá (Alap)"
PREFIXO = "alap"  # id das propostas: "alap:<id da proposição no e-Legis>"
PAUSA = 1.5  # segundos entre dois pedidos ao e-Legis (o robots.txt não pede intervalo)
LIMITE_S = 300  # limite diário (segundos) das páginas de proposição; na primeira carga, o resto da rodada
FALHAS_MAX = 3  # uma página que não abre em 3 rodadas seguidas entra só com os dados da lista ("Situação não classificada")

# tipos do e-Legis -> (tipo comum do site, sigla da Alap, nome no e-Legis)
TIPOS = {1: ("PL", "PLO", "Projeto de Lei Ordinária"), 2: ("PLP", "PLC", "Projeto de Lei Complementar"),
         4: ("PEC", "PEC", "Proposta de Emenda Constitucional"), 10: ("PDL", "PDL", "Projeto de Decreto Legislativo"),
         9: ("PRC", "PR", "Projeto de Resolução")}
TIPO_VETO = 6
# cadastro de legislação (legislacao-csv?tipo_proposicao_id=): as leis que contam para o governador
NORMAS_LEI = {1: "LO", 2: "LC"}
NOME_TIPO_LEI = {"LO": "Lei", "LC": "Lei Complementar"}
# projetos que o governo do estado manda (tipos dos deputados que o Executivo também usa)
TIPOS_GOV = (1, 2, 4)
# nomes da origem que a regra comum (Nomes) não liga sozinha, conferidos à mão em 27/10/2026: {nome como o e-Legis
# escreve: id da pessoa ou "-"}. "Dr. Vitor" (PDL 0145/24-AL e outros, junto com Fabricio Furlan e R. Nelson Vieira) é o
# deputado Dr. Victor; "Edna Azuer" é a deputada Edna Auzier (a única Edna da Casa).
ELEGIS_MANUAL = {"Dr. Vitor": "dest-AP-30001604789", "Edna Azuer": "dest-AP-30001615060"}
# situações oficiais do e-Legis (filtro "Situação" da busca) que a movimentação da proposição às vezes não mostra (os
# documentos trazidos do sistema antigo vêm sem o parecer ou sem a devolução): {código: (status, frase, frase em inglês, texto
# oficial)}. Valem só para as proposições que, pela movimentação, ainda estariam andando ou sem resultado (conferido em
# 27/10/2026 com as listas oficiais dos projetos de lei de 2025: notas da frente amapa, §4).
SITUACOES_OFICIAIS = {23: ("parada", "Devolvida ao autor", "Returned to the author", "Devolvido ao Autor"),
                      26: ("rejeitada", "Rejeitada na Comissão de Constituição e Justiça",
                           "Rejected by the Constitution and Justice Committee", "Rejeitado pela CCJ")}

_EXECUTIVO = re.compile(r"poder executivo|governo do estado|governador|governadora|chefe do executivo", re.I)
_ORGAO = re.compile(r"poder executivo|governo do estado|governador|mesa diretora|comiss[aã]o|tribunal|procuradoria|procuraria|"
                    r"defensoria|poder judici|minist[eé]rio p|sindicato|departamento|assembleia|justi[cç]a", re.I)
_COLETIVO = re.compile(r"^(deputad[oa]s\s+diversos|deputadas\s+diversas|diversos\s+deputad|diversas\s+deputad|"
                       r"v[aá]rios\s+deputad|todos\s+os\s+deputad)", re.I)
_NUM = re.compile(r"n[º°o]\.?\s*([\d]+(?:-[A-Z])?)\s*/\s*(\d{2,4})(?:\s*-\s*([A-Za-zÀ-ú]+))?", re.I)


# ---------------------------------------------------------------- textos
def _limpa(s: str | None) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", sem_acento(s or "").lower()).strip()


def _data_br(s: str | None) -> str | None:
    """'20/12/2023' -> '2023-12-20' (None se não for uma data)."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def numero_oficial(txt: str | None) -> tuple[str, str, str] | None:
    """'Projeto de Lei Ordinária nº 0335/23-AL' -> ('0335', '23', 'AL'); 'nº 0002/23' -> ('0002', '23', ''); sem número
    (rascunho, "Documento duplicado") -> None."""
    m = _NUM.search(txt or "")
    if not m:
        return None
    ano = m.group(2)[-2:]
    return m.group(1).upper(), ano, (m.group(3) or "").upper()


def sigla_de(tipo: int, num: tuple[str, str, str]) -> str:
    """(1, ('0335', '23', 'AL')) -> 'PLO 0335/23-AL' (como a Alap escreve; a origem no fim separa as numerações)."""
    n, a, s = num
    return f"{TIPOS[tipo][1] if tipo in TIPOS else 'Veto'} {n}/{a}" + (f"-{s}" if s else "")


def chave_num(tipo: int, num: tuple[str, str, str]) -> tuple:
    n, a, s = num
    return tipo, re.sub(r"^0+(?=\d)", "", n), a, s


# ---------------------------------------------------------------- páginas
def ler_pagina_lista(h: str) -> tuple[int | None, list[dict], str | None, list[str]]:
    """Uma página da lista de proposições -> (total que a busca diz, linhas, endereço da próxima página, nomes do seletor
    "Deputado"). Levanta erro se a tabela mudou."""
    t = re.search(r"<strong>\s*(\d+)\s*</strong>\s*proposi", h)
    cab = [_limpa(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", h[h.find("<thead>"):h.find("</thead>")], re.S)]
    if cab[:4] != ["Data", "Número", "Origem", "Ementa"]:
        raise RuntimeError(f"AP e-Legis: a tabela de proposições mudou (colunas {cab})")
    tb = h[h.find("<tbody>"):h.find("</tbody>")]
    linhas = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        link = re.search(r'href="[^"]*/portal/proposicao/(\d+)"', tr)
        if len(tds) < 4 or not link:
            raise RuntimeError("AP e-Legis: uma linha da lista de proposições mudou (sem o link da proposição)")
        linhas.append({"id": link.group(1), "data": _data_br(_limpa(tds[0])), "numero": _limpa(tds[1]),
                       "origem": _limpa(tds[2]), "ementa": _limpa(tds[3])})
    prox = re.search(r'<a href="([^"]+)"[^>]*>\s*Próximo', h)
    sel = re.search(r'<select name="origem_select"[^>]*>(.*?)</select>', h, re.S)
    nomes = [_limpa(v) for v in re.findall(r'<option value="([^"]+)"', sel.group(1))] if sel else []
    return (int(t.group(1)) if t else None), linhas, (_html.unescape(prox.group(1)) if prox else None), nomes


def ler_pagina_proposicao(h: str, pid: str) -> dict:
    """A página de uma proposição -> {"titulo", "norma", "origem", "ementa", "protocolo", "obs", "movs": [[data, texto]]
    (da mais nova para a mais antiga), "votacao", "texto"}."""
    i = h.find('<section class="app">')
    s = h[i:h.find("</section>", i)] if i >= 0 else ""
    t = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    if not t or not re.search(r"(?i)projeto|proposta|veto", _limpa(t.group(1))):
        raise RuntimeError(f"AP e-Legis: a página da proposição {pid} mudou (sem o título)")
    d = {"titulo": _limpa(t.group(1))}
    n = re.search(r"</h1>\s*<h2[^>]*>(.*?)</h2>", s, re.S)
    d["norma"] = _limpa(n.group(1)) if n else ""
    for chave, rot in (("origem", "Origem"), ("ementa", "Ementa"), ("protocolo", "Data de Protocolo"), ("obs", "Observações")):
        m = re.search(r"<strong>\s*" + rot + r":\s*</strong>(.*?)</p>", s, re.S)
        d[chave] = _limpa(m.group(1)) if m else ""
    d["protocolo"] = _data_br(d["protocolo"])
    k = s.find("Movimentação da proposição")
    movs = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s[k:] if k >= 0 else "", re.S):
        tds = [_limpa(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) >= 2 and _data_br(tds[0]):
            movs.append([_data_br(tds[0]), tds[1][:400]])
    d["movs"] = movs
    d["votacao"] = f"/proposicao/{pid}/votacao" in s
    d["texto"] = f"/proposicao/{pid}/texto-integral" in s
    return d


def ler_csv_normas(b: bytes) -> list[dict]:
    """legislacao-csv -> [{"txt", "numero", "data", "publicacao", "doe", "origem" (o número do projeto, como a Alap escreve),
    "ementa"}]."""
    txt = b.decode("utf-8-sig", "replace")
    linhas = list(csv.reader(io.StringIO(txt)))
    if not linhas or [c.strip() for c in linhas[0][:5]] != ["Tipo - número", "Ementa", "DOE nº", "Publicado em", "Nº proposição"]:
        raise RuntimeError(f"AP e-Legis: o CSV de legislação mudou (colunas {linhas[0][:5] if linhas else None})")
    out = []
    for r in linhas[1:]:
        if len(r) < 5 or not r[0].strip():
            continue
        t = r[0].strip()
        m = re.search(r"n[º°o]\.?\s*(?:n[º°o]\.?\s*)?([\d.]+)", t)
        out.append({"txt": t, "numero": int(m.group(1).replace(".", "")) if m else None, "data": _data_tolerante(t[m.end():] if m else t),
                    "publicacao": _data_tolerante(r[3]), "doe": r[2].strip(), "origem": r[4].strip(), "ementa": r[1].strip()})
    return out


def _data_tolerante(s: str | None) -> str | None:
    """Datas como a Alap às vezes escreve: '20/12/2023', '08/012026', '08/05/22', '11/12/20257', '14/12/2023'."""
    m = re.search(r"(\d{1,2})\s*[/.;]\s*(\d{1,2})\s*[/.;]?\s*(\d{2,5})", s or "")
    if not m:
        return None
    a = m.group(3)
    a = a[:4] if len(a) >= 4 else (("19" if int(a) >= 50 else "20") + a)
    try:
        return dt.date(int(a), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- situação (regras da Alap, conferidas à mão: notas)
_LEI_NOMES = [(r"^lei complementar", "Lei Complementar"), (r"^lei", "Lei"), (r"^emenda constitucional", "Emenda Constitucional"),
              (r"^decreto legislativo", "Decreto Legislativo"), (r"^resolu", "Resolução")]


def norma_de(txt: str | None) -> tuple[str, str | None] | None:
    """'Lei Ordinária nº 3436, de 14/01/2026' -> ('Lei nº 3.436/2026', '2026-01-14'); 'Decreto Legislativo nº 1332, de
    22/10/2024' -> ('Decreto Legislativo nº 1.332/2024', ...)."""
    t = _norm(txt)
    nome = next((n for exp, n in _LEI_NOMES if re.search(exp, t)), None)
    m = re.search(r"n[º°o]\.?\s*(?:n[º°o]\.?\s*)?([\d.]+)", txt or "")
    if not nome or not m:
        return None
    num = int(m.group(1).replace(".", ""))
    data = _data_tolerante((txt or "")[m.end():])
    ano = (data or "")[:4]
    n = f"{num:,}".replace(",", ".") if num >= 1000 else str(num)
    return (f"{nome} nº {n}/{ano}" if ano else f"{nome} nº {n}"), data


# tipos de movimentação, na ordem em que são testados (texto sem acento, em minúsculas)
_MOV = [
    ("lei", r"proposicao sancionada|sancionad[ao] parcialmente|proposicao promulgada|\bpromulgad[ao] em\b"),
    ("veto_total", r"vetad[ao] totalmente|\bveto total\b"),
    ("veto_mantido", r"veto mantido|mantido o veto"),
    ("arquivamento_ccj", r"pelo arquivamento na ccj"),
    ("arquivada", r"^arquivad|\barquivad[ao] (em|por|pel[ao]|nos termos|de acordo)|\barquivamento (da|do|de) (proposi|projeto|materia)"),
    ("retirada", r"\bretirad[ao] (pel[ao]|a pedido|de tramita)|\bretirada de tramita|pedido de retirada (deferid|aprovad)"),
    ("devolvida", r"devolvid[ao] ao autor|devolucao ao autor"),
    ("prejudicada", r"\bprejudicad"),
    ("rejeitada_plenario", r"resultado:\s*rejeitad|rejeitad[ao] (em|no|pelo) plenario|rejeitad[ao] em sessao"),
    ("rejeitada_ccj", r"rejeita o projeto na ccj|rejeitad[ao] (pela|na) ccj"),
    ("aprovada", r"enviad[ao] para sancao|protocolado no gea|aguardando sancao|aguardando promulgacao|redacao final finalizada|"
                 r"resultado:\s*aprovad"),
    ("neutra", r"documento importado|certidao|encerramento do processo|retornado a depleg|votado na comissao|"
               r"parecer importado|^emissao de"),
]
_TXT = {
    "veto_total": ("Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    "veto_mantido": ("Vetada pelo governador; a Assembleia manteve o veto", "Vetoed by the governor; the state legislature upheld the veto"),
    "arquivada": ("Arquivada", None),
    "retirada": (None, None),
    "devolvida": ("Devolvida ao autor", "Returned to the author"),
    "prejudicada": ("Ficou prejudicada", None),
    "rejeitada_plenario": ("Rejeitada no Plenário da Assembleia", "Rejected by the full state legislature"),
    "rejeitada_ccj": ("Rejeitada na Comissão de Constituição e Justiça", "Rejected by the Constitution and Justice Committee"),
    "arquivamento_ccj": ("Rejeitada na Comissão de Constituição e Justiça (parecer pelo arquivamento)",
                         "Rejected by the Constitution and Justice Committee (it recommended shelving the bill)"),
    "aprovada_sancao": ("Aprovada; esperando a decisão do governador", "Approved; waiting for the governor's decision"),
    "aprovada_promulgacao": ("Aprovada; esperando ser promulgada", None),
    "encerrada": ("Processo encerrado na Assembleia, sem o resultado no e-Legis", "Proceedings closed at the state legislature; "
                  "e-Legis does not give the outcome"),
}
_STATUS = {"veto_total": "rejeitada", "veto_mantido": "rejeitada", "arquivada": "arquivada", "retirada": "retirada",
           "devolvida": "parada", "prejudicada": "parada", "rejeitada_plenario": "rejeitada", "rejeitada_ccj": "rejeitada",
           "arquivamento_ccj": "rejeitada", "aprovada": "aprovada"}


def tipo_mov(texto: str) -> str:
    t = _norm(texto)
    for nome, exp in _MOV:
        if re.search(exp, t):
            return nome
    return "andando"


def quem_assinou(d: dict | None) -> str | None:
    """Pela movimentação: "governo" (sancionou, inclusive com veto parcial), "casa" (a Assembleia promulgou) ou None."""
    if not d:
        return None
    t = " | ".join(_norm(x) for _, x in d.get("movs") or [])
    if re.search(r"proposicao sancionada|sancionad[ao] parcialmente", t):
        return "governo"
    if re.search(r"proposicao promulgada|\bpromulgad[ao] em\b", t):
        return "casa"
    return None


def situacao(d: dict, tipo: int, autor_gov: bool = False) -> dict:
    """Situação de uma proposição pela página dela no e-Legis: {"status", "txt", "en", "data", "lei", "oficial"}.
    1) Gerou norma (o título da página traz "Lei Ordinária nº ...", "Decreto Legislativo nº ..."): virou lei (com partes
       vetadas, se houve veto parcial). 2) Senão, a movimentação mais nova que decide: veto total, veto mantido, arquivada,
       retirada, devolvida, prejudicada, rejeitada (Plenário ou CCJ), aprovada (enviada à sanção, redação final...); as
       movimentações que não dizem nada (documento importado do sistema antigo, certidão, retorno ao departamento...) são
       puladas; as outras (leitura, comissões, pareceres a favor) = ainda em discussão. 3) "Encerramento do processo
       legislativo" sem nenhuma dessas: o e-Legis não diz o resultado ("outra")."""
    movs = d.get("movs") or []
    nt = norma_de(d.get("norma"))
    if nt:
        nome, data = nt
        parcial = any(re.search(r"vetad[ao] parcialmente|sancionad[ao] parcialmente", _norm(x)) for _, x in movs)
        artigo = "o" if nome.startswith("Decreto") else "a"
        dec = next((x for x in movs if tipo_mov(x[1]) == "lei"), None)
        if "/" not in nome and dec and dec[0]:  # norma sem data no título ("Lei Complementar nº 0185"): o ano da sanção
            nome = f"{nome}/{dec[0][:4]}"
        return {"status": "lei", "txt": f"Virou {artigo} {nome}" + (" (com partes vetadas)" if parcial else ""), "en": None,
                "data": data or (dec[0] if dec else None),
                "lei": {"nome": nome, "url": f"{BASE}/proposicao/{d['_id']}/texto-integral"} if d.get("texto") else {"nome": nome},
                "oficial": (dec[1] if dec else d.get("norma"))[:300]}
    encerrada = None
    andando = None
    # veto total (ou veto mantido) sem lei depois: vale o veto, mesmo que a movimentação siga (a leitura e a votação do
    # veto na Assembleia aparecem como "Incluído para votação", sem o resultado)
    for data, texto in movs:
        k = tipo_mov(texto)
        if k == "lei":
            break
        if k in ("veto_total", "veto_mantido"):
            pt, en = _TXT[k]
            return {"status": "rejeitada", "txt": pt, "en": en, "data": data, "lei": None, "oficial": texto[:300]}
    for data, texto in movs:
        k = tipo_mov(texto)
        if k == "neutra":
            if encerrada is None and re.search(r"encerramento do processo", _norm(texto)):
                encerrada = (data, texto)
            continue
        if k == "andando":
            andando = andando or (data, texto)
            if encerrada:  # depois do encerramento só vale um resultado: leitura e comissões não decidem
                continue
            return {"status": "andando", "txt": STATUS_TXT["andando"], "en": None, "data": data, "lei": None,
                    "oficial": texto[:300]}
        if k == "lei":  # sem a norma no título (cadastro incompleto): a movimentação diz que virou lei
            m = re.search(r"((?:lei|decreto legislativo|resolu[cç][aã]o|emenda constitucional)[^-|]*?n[º°o]\.?\s*[\d.]+[^-|]*)",
                          texto, re.I)
            nt2 = norma_de(m.group(1)) if m else None
            if nt2:
                artigo = "o" if nt2[0].startswith("Decreto") else "a"
                return {"status": "lei", "txt": f"Virou {artigo} {nt2[0]}", "en": None, "data": nt2[1] or data,
                        "lei": {"nome": nt2[0]}, "oficial": texto[:300]}
            return {"status": "lei", "txt": STATUS_TXT["lei"], "en": None, "data": data, "lei": None, "oficial": texto[:300]}
        if k == "aprovada":
            chave = "aprovada_promulgacao" if tipo in (4, 9, 10) else "aprovada_sancao"
            pt, en = _TXT[chave]
            return {"status": "aprovada", "txt": pt, "en": en, "data": data, "lei": None, "oficial": texto[:300]}
        if k == "retirada":
            pt = "O governo retirou a proposta" if autor_gov else STATUS_TXT["retirada"]
            return {"status": "retirada", "txt": pt, "en": None, "data": data, "lei": None, "oficial": texto[:300]}
        pt, en = _TXT[k]
        return {"status": _STATUS[k], "txt": pt, "en": en, "data": data, "lei": None, "oficial": texto[:300]}
    if encerrada:
        pt, en = _TXT["encerrada"]
        return {"status": "outra", "txt": pt, "en": en, "data": encerrada[0], "lei": None, "oficial": encerrada[1][:300]}
    if andando:
        return {"status": "andando", "txt": STATUS_TXT["andando"], "en": None, "data": andando[0], "lei": None,
                "oficial": andando[1][:300]}
    return {"status": "andando", "txt": STATUS_TXT["andando"], "en": None, "data": d.get("protocolo"), "lei": None,
            "oficial": None}


# ---------------------------------------------------------------- autoria
def autores(origem: str | None) -> tuple[list[str], str]:
    """A origem como o e-Legis escreve -> ([nomes, o autor principal primeiro], tipo): "pessoas", "coletivo" ("Deputados
    Diversos": o e-Legis não diz quem) ou "orgao" (Poder Executivo, Mesa Diretora, comissões, tribunais...)."""
    o = re.sub(r"\s+", " ", origem or "").strip(" .")
    if not o:
        return [], "orgao"
    if _COLETIVO.search(o):
        return [], "coletivo"
    tem_dep = re.search(r"(?i)\bdep(utad[oa]s?)?\b\.?", o)
    if not tem_dep and _ORGAO.search(o):
        return [], "orgao"
    s = re.sub(r"(?i)^\s*deputad[oa]s\s*:?\s*", "", o)
    partes = re.split(r"\s*,\s*|\s+e\s+", s)
    nomes = []
    for p in partes:
        p = re.sub(r"(?i)^\s*(deputad[oa]s?|dep)\.?\s*:?\s*", "", p).strip(" .:")
        if not p or re.match(r"(?i)^(demais|outr[oa]s|tod[oa]s)\b", p):
            continue
        nomes.append(p)
    return nomes, "pessoas"


def eh_executivo(origem: str | None, num: tuple[str, str, str] | None) -> bool:
    return bool(_EXECUTIVO.search(origem or "")) or bool(num and num[2] == "GEA")


# ---------------------------------------------------------------- leitura
class Elegis:
    def __init__(self, rede: Rede | None = None):
        # o limite de tempo de rede é o da rodada inteira (legislativos.py --minutos) e o diário de cada parte (LIMITE_S),
        # não os 25 min padrão das Casas do Norte: a primeira carga precisa da rodada toda
        self.rede = rede or Rede("alap-elegis", pausa=PAUSA, minutos=24 * 60 if _carga.sem_limite() else 60)
        self.nomes_select: list[str] = []
        self.ocultas: dict[str, int] = {}
        self.lidas = 0
        self.falhas_rodada = 0

    # listas -------------------------------------------------------
    def lista(self, tipo: int, ano: int, ttl_h: float | None) -> dict:
        """Todas as páginas da lista de um tipo e ano, lidas na mesma rodada (os itens novos entram no topo e empurram os
        outros de página): {"lido", "total", "linhas", "nomes"}."""
        nome = f"listas/{tipo}-{ano}.json"
        est = self.rede.estado(nome)
        if est and ttl_h is not None and time.time() - est.get("lido", 0) < ttl_h * 3600:
            self._conta_ocultas(tipo, ano, est)
            return est
        if est and ttl_h is None:
            self._conta_ocultas(tipo, ano, est)
            return est
        url = f"{BASE}/proposicoes?tipo_proposicao={tipo}&ano={ano}"
        linhas, total, nomes, vistas = [], None, [], set()
        for _ in range(80):
            h = self.rede.texto(url, None, 0)
            t, ls, prox, ns = ler_pagina_lista(h)
            total = t if total is None else total
            nomes = nomes or ns
            for l in ls:
                if l["id"] not in vistas:
                    vistas.add(l["id"])
                    linhas.append(l)
            if not prox or not ls:
                break
            url = prox
        if total is None:
            raise RuntimeError(f"AP e-Legis: a lista {tipo}/{ano} veio sem o total")
        if len(linhas) > total or (total and len(linhas) < total - max(10, total // 20)):
            raise RuntimeError(f"AP e-Legis: a lista {tipo}/{ano} diz {total} e mostrou {len(linhas)}; nada gravado")
        est = {"lido": time.time(), "total": total, "linhas": linhas, "nomes": nomes}
        self.rede.guardar(est, nome)
        self._conta_ocultas(tipo, ano, est)
        return est

    def _conta_ocultas(self, tipo: int, ano: int, est: dict) -> None:
        self.ocultas[f"{tipo}-{ano}"] = max(0, est["total"] - len(est["linhas"]))
        if est.get("nomes") and not self.nomes_select:
            self.nomes_select = est["nomes"]

    def com_situacao(self, status: int, ano: int, ttl_h: float | None) -> set[str]:
        """Os ids das proposições de um ano com uma situação oficial do e-Legis (filtro "Situação" da busca), para as
        situações que a movimentação não mostra (ex.: "Devolvido ao Autor")."""
        nome = f"situacoes/{status}-{ano}.json"
        est = self.rede.estado(nome)
        if est and (ttl_h is None or time.time() - est.get("lido", 0) < ttl_h * 3600):
            return set(est["ids"])
        url, ids = f"{BASE}/proposicoes?status={status}&ano={ano}", []
        for _ in range(40):
            _, ls, prox, _ = ler_pagina_lista(self.rede.texto(url, None, 0))
            ids += [l["id"] for l in ls]
            if not prox or not ls:
                break
            url = prox
        self.rede.guardar({"lido": time.time(), "ids": sorted(set(ids))}, nome)
        return set(ids)

    # proposições ---------------------------------------------------
    def detalhe(self, pid: str) -> dict | None:
        return self.rede.estado(f"proposicoes/{pid}.json")

    def ler_detalhe(self, pid: str) -> dict:
        h = self.rede.texto(f"{BASE}/proposicao/{pid}", None, 0)
        d = ler_pagina_proposicao(h, pid)
        d["_id"] = pid
        d["_lido"] = time.time()
        self.rede.guardar(d, f"proposicoes/{pid}.json")
        self.lidas += 1
        return d

    # legislação ----------------------------------------------------
    def normas(self, tipo: int, ano: int, ttl_h: float | None) -> list[dict]:
        nome = f"legislacao/{tipo}-{ano}.json"
        est = self.rede.estado(nome)
        if est and (ttl_h is None or time.time() - est.get("lido", 0) < ttl_h * 3600):
            return est["linhas"]
        b = self.rede.bruto(f"{BASE}/legislacao-csv?tipo_proposicao_id={tipo}&ano={ano}", None, 0)
        linhas = ler_csv_normas(b)
        self.rede.guardar({"lido": time.time(), "linhas": linhas}, nome)
        return linhas


def ttl_lista_h(ano: int) -> float:
    """Lista do ano: todo dia; do ano anterior: a cada 3 dias (ainda chega coisa atrasada da mudança de sistema); as mais
    antigas, uma vez por semana."""
    a = int(hoje()[:4])
    return 20 if ano >= a else 70 if ano == a - 1 else 24 * 7


def _idade_dias(d: dict) -> float:
    return (time.time() - d.get("_lido", 0)) / 86400


def _vence(pid: str, d: dict, tipo: int) -> float:
    """Quantos dias a página de uma proposição vale no cache: terminada (lei, rejeitada, arquivada...) ~60 dias; ainda
    andando: 2 dias se mexeu no último mês, senão 6. O id entra no prazo para espalhar as releituras pelos dias."""
    s = situacao(d, tipo)
    if s["status"] in ("lei", "rejeitada", "arquivada", "retirada", "parada"):
        return 55 + int(re.sub(r"\D", "", pid) or 0) % 10
    ult = (d.get("movs") or [[None]])[0][0] or d.get("protocolo") or "2000-01-01"
    recente = (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(ult)).days <= 30
    return 2 if recente else 6


# ---------------------------------------------------------------- tudo
def anos_desde(inicio: str) -> list[int]:
    return list(range(int(inicio[:4]), int(hoje()[:4]) + 1))


def coletar_elegis(membros: list[dict], ini_dep: str, gov: dict) -> dict:
    """Lê o e-Legis e devolve {"propostas": {id da pessoa: bloco} ou None (primeira carga em andamento), "governo":
    {"propostas", "executivo"} ou None, "notas": [(pt, en)], "pedidos", "segundos", "pendente": texto ou None}."""
    t0 = time.time()
    el = Elegis()
    ini_gov = gov["inicio"]
    anos = anos_desde(min(ini_dep, ini_gov))
    # 1) listas: os 5 tipos de projeto e os vetos, desde o começo do período
    listas: dict[tuple[int, int], dict] = {}
    for ano in anos:
        for tipo in list(TIPOS) + [TIPO_VETO]:
            listas[(tipo, ano)] = el.lista(tipo, ano, ttl_lista_h(ano))
    # 2) leis (cadastro de legislação), pelo ano da proposição: a lei mais antiga do período veio de um projeto de até 1 ano
    # antes do começo do período
    anos_leis = list(range(int(ini_gov[:4]) - 1, int(hoje()[:4]) + 1))
    leis_csv: dict[str, list[dict]] = {}
    for tipo, sig in NORMAS_LEI.items():
        leis_csv[sig] = []
        for ano in anos_leis:  # as leis novas vêm de projetos do ano e do ano anterior: esses dois, todo dia
            leis_csv[sig] += el.normas(tipo, ano, 20 if ano >= int(hoje()[:4]) - 1 else 24 * 7)
    # projetos de antes do período que viraram lei no período: as listas desses anos (para achar a página de cada um)
    anos_origem = set()
    for sig, ls in leis_csv.items():
        for l in ls:
            if (l.get("data") or "") >= ini_gov or (l.get("publicacao") or "") >= ini_gov:
                num = numero_oficial(l["origem"])
                if num:
                    anos_origem.add(2000 + int(num[1]))
    for ano in sorted(a for a in anos_origem if a < anos[0]):
        for tipo in TIPOS_GOV:
            listas[(tipo, ano)] = el.lista(tipo, ano, 24 * 7)
    # 3) o inventário: proposições com número, por id
    inv: dict[str, dict] = {}
    por_num: dict[tuple, str] = {}
    sem_numero = 0
    for (tipo, ano), est in listas.items():
        if tipo == TIPO_VETO:
            continue
        for l in est["linhas"]:
            num = numero_oficial(l["numero"])
            if not num:
                sem_numero += 1
                continue
            inv[l["id"]] = {"t": tipo, "num": num, "data": l["data"], "origem": l["origem"], "ementa": l["ementa"],
                            "sigla": sigla_de(tipo, num), "anoLista": ano}
            por_num.setdefault(chave_num(tipo, num), l["id"])
    # quais páginas são necessárias: as do período (deputados e governo) e as dos projetos de onde vieram as leis do período
    origem_lei: dict[tuple[str, int], str | None] = {}
    tipo_csv = {"LO": 1, "LC": 2}
    for sig, ls in leis_csv.items():
        for l in ls:
            num = numero_oficial(l["origem"])
            origem_lei[(sig, l["numero"])] = por_num.get(chave_num(tipo_csv[sig], num)) if num else None
            if num and not origem_lei[(sig, l["numero"])]:  # lei complementar que veio de projeto de lei ordinária, etc.
                for t in TIPOS_GOV:
                    if por_num.get(chave_num(t, num)):
                        origem_lei[(sig, l["numero"])] = por_num[chave_num(t, num)]
                        break
    precisa = set()
    nomes = Nomes(membros, ELEGIS_MANUAL, aproximado=True)
    donos: dict[str, list[tuple[str, str]]] = {}
    coletivos, sem_ligacao = 0, {}
    for pid, x in inv.items():
        if x["t"] in TIPOS_GOV and (x["data"] or "") >= ini_gov and eh_executivo(x["origem"], x["num"]):
            precisa.add(pid)
        if (x["data"] or "") < ini_dep:
            continue
        ns, tipo_o = autores(x["origem"])
        if tipo_o == "coletivo":
            coletivos += 1
            continue
        ligados: list[tuple[str, str]] = []
        for i, n in enumerate(ns):
            quem = nomes.quem(n)
            if quem and quem not in [q for q, _ in ligados]:
                ligados.append((quem, "autor" if i == 0 else "coautor"))
            elif not quem:
                sem_ligacao[n] = sem_ligacao.get(n, 0) + 1
        if ligados:
            donos[pid] = ligados
            precisa.add(pid)
    leis_periodo = _leis_do_periodo(leis_csv, ini_gov)
    precisa |= {origem_lei.get((l["sig"], l["numero"])) for l in leis_periodo} - {None}
    # 4) as páginas das proposições: primeiro as que faltam, depois as vencidas (as mais atrasadas primeiro)
    falhas = el.rede.estado("falhas.json", {}) or {}
    dets: dict[str, dict] = {}
    faltam, vencidas = [], []
    for pid in sorted(precisa, key=lambda x: -int(x)):
        d = el.detalhe(pid)
        if d is None:
            if falhas.get(pid, 0) < FALHAS_MAX:
                faltam.append(pid)
            continue
        dets[pid] = d
        atraso = _idade_dias(d) - _vence(pid, d, inv[pid]["t"])
        if atraso >= 0:
            vencidas.append((atraso, pid))
    primeira = len(faltam) > 100
    limite = _carga.limite_diario(LIMITE_S, primeira)
    t1 = time.time()
    fila = faltam + [pid for _, pid in sorted(vencidas, reverse=True)]
    seguidas = 0
    for pid in fila:
        if time.time() - t1 >= limite or _carga.acabou() or seguidas >= 3:
            break
        try:
            dets[pid] = el.ler_detalhe(pid)
            falhas.pop(pid, None)
            seguidas = 0
        except SemTempo:
            break
        except Exception as e:  # página com erro: tenta de novo nas próximas rodadas
            log(f"  AP e-Legis: proposição {pid} não lida ({type(e).__name__}: {e})")
            seguidas += 1
            # internet fora (sem DNS, sem conexão, tempo esgotado) não é defeito da página: não conta para as 3 rodadas
            if not re.search(r"urlopen error|getaddrinfo|timed out|tempo limite|Connection|RemoteDisconnected", str(e), re.I):
                falhas[pid] = falhas.get(pid, 0) + 1
    el.rede.guardar(falhas, "falhas.json")
    faltando = [pid for pid in precisa if pid not in dets and falhas.get(pid, 0) < FALHAS_MAX]
    ocultas = sum(el.ocultas.get(f"{t}-{a}", 0) for t in TIPOS for a in anos)
    r = {"pedidos": el.rede.pedidos, "segundos": round(time.time() - t0), "lidas": el.lidas, "faltam": len(faltando),
         "propostas": None, "governo": None, "notas": [], "pendente": None, "ocultas": ocultas, "semNumero": sem_numero,
         "coletivos": coletivos}
    if faltando:
        r["pendente"] = (f"{'primeira carga' if primeira else 'leitura'} do e-Legis: {len(precisa) - len(faltando)} de "
                         f"{len(precisa)} páginas de proposição lidas")
        log(f"  AP e-Legis: {r['pendente']}; continua na próxima rodada (ficam os blocos de antes)")
        return r
    # situações oficiais que a movimentação não mostra (ex.: "Devolvido ao Autor"): valem só para quem ainda está andando
    oficiais: dict[str, tuple] = {}
    for st, x in SITUACOES_OFICIAIS.items():
        for ano in anos:
            for pid in el.com_situacao(st, ano, ttl_lista_h(ano)):
                oficiais[pid] = x
    # 5) as propostas de cada deputado
    sit: dict[str, dict] = {}

    def s_de(pid: str) -> dict:
        if pid not in sit:
            x = inv[pid]
            d = dets.get(pid)
            sit[pid] = situacao(d, x["t"], eh_executivo(x["origem"], x["num"])) if d else {
                "status": "outra", "txt": STATUS_TXT["outra"], "en": None, "data": None, "lei": None, "oficial": None}
            if pid in oficiais and sit[pid]["status"] in ("andando", "outra"):
                st, pt, en, of = oficiais[pid]
                sit[pid] = {"status": st, "txt": pt, "en": en, "data": None, "lei": None, "oficial": of}
        return sit[pid]

    nomes.avisar("AP", "e-Legis (origem das propostas)")
    por_pessoa: dict[str, list[dict]] = {m["id"]: [] for m in membros}
    for pid, ligados in donos.items():
        x = inv[pid]
        s = s_de(pid)
        for quem, papel in ligados:
            p = regional.proposta(f"{PREFIXO}:{pid}", x["sigla"], TIPOS[x["t"]][0], x["data"], x["ementa"], s["oficial"],
                                  f"{BASE}/proposicao/{pid}", papel=papel, status=s["status"], data_status=s["data"],
                                  status_txt=s["txt"], lei=s["lei"])
            por_pessoa[quem].append(com_status_en(p, s["en"]))
    blocos = {}
    sel_de: dict[str, str] = {}
    for n in el.nomes_select:  # o nome de cada pessoa no seletor "Deputado" do e-Legis (link da fonte)
        q = nomes.quem(n)
        if q:
            sel_de.setdefault(q, n)
    for m in membros:
        lista = por_pessoa[m["id"]]
        nome_sel = sel_de.get(m["id"])
        url = (f"{BASE}/proposicoes?origem_select={urllib.parse.quote(nome_sel)}" if nome_sel else f"{BASE}/proposicoes")
        f = fonte(VEICULO, f"Proposições de {m['nome']} (e-Legis da Alap)", url)
        blocos[m["id"]] = regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, f)
    log(f"  AP e-Legis: {sum(len(v) for v in por_pessoa.values())} propostas nos perfis "
        f"({sum(1 for v in por_pessoa.values() if v)} pessoas); situações {resumo_status(list(por_pessoa.values()))}; "
        f"{coletivos} de \"Deputados Diversos\"; {ocultas} contadas pela busca e não mostradas; {sem_numero} sem número")
    r["propostas"] = blocos
    r["coletivos"] = coletivos
    # 6) o governador
    try:
        r["governo"] = _governo(el, gov, inv, dets, listas, leis_periodo, origem_lei, s_de)
    except SemTempo:
        raise
    except Exception as e:  # a parte do governo não derruba as propostas dos deputados
        log(f"  AP: ATENÇÃO: governador não atualizado ({type(e).__name__}: {e})")
        r["governo"] = None
    r["pedidos"] = el.rede.pedidos
    r["segundos"] = round(time.time() - t0)
    return r


def _leis_do_periodo(leis_csv: dict[str, list[dict]], inicio: str) -> list[dict]:
    """As leis ordinárias e complementares com data a partir do começo do período. A data é a do título da lei; quando ela
    não bate com a da publicação (mais de 60 dias: erro de digitação, como "Lei nº 2835, de 08/05/22", publicada em
    8/5/2023, ou a Lei nº 3237, de 4/6/2025, com publicação "15/10/2024"), vale a que combina com as leis de número vizinho."""
    def dias(a: str, b: str) -> int:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)

    out = []
    for sig, ls in leis_csv.items():
        por_num: dict[int, dict] = {}
        for l in ls:
            if l.get("numero") and l["numero"] not in por_num:
                por_num[l["numero"]] = l
        nums = sorted(por_num)
        base = {n: por_num[n].get("data") or por_num[n].get("publicacao") for n in nums}
        for i, n in enumerate(nums):
            l = por_num[n]
            d, p = l.get("data"), l.get("publicacao")
            if d and p and dias(d, p) > 60:
                viz = sorted(base[m] for m in nums[max(0, i - 3):i] + nums[i + 1:i + 4] if base[m])
                meio = viz[len(viz) // 2] if viz else d
                d = min((d, p), key=lambda x: dias(x, meio))
            d = d or p
            if d and d >= inicio:
                out.append(dict(l, sig=sig, dataLei=d))
    return out


def _vetos(listas: dict, dets: dict, inv: dict, inicio: str) -> tuple[dict, list[str]]:
    """As mensagens de veto do governo (tipo "Veto") que chegaram à Alap a partir do começo do período, uma por número
    (a mesma mensagem cadastrada duas vezes conta uma vez), e a conferência com a movimentação dos projetos ("Proposição
    Vetada Totalmente: Veto nº 0042/26-GEA"). Devolve ({número: {"data", "tipo": "total"|"parcial"|None, "projeto"}},
    avisos)."""
    vetos: dict[str, dict] = {}
    for (tipo, ano), est in listas.items():
        if tipo != TIPO_VETO:
            continue
        for l in est["linhas"]:
            num = numero_oficial(l["numero"])
            if not num or not l["data"] or l["data"] < inicio:
                continue
            if not _EXECUTIVO.search(l["origem"] or "") and num[2] != "GEA":
                continue
            k = f"{num[0]}/{num[1]}-{num[2]}"
            e = _norm(l["ementa"])
            tp = "total" if re.search(r"\bveto\s+total", e) else "parcial" if re.search(r"\bveto\s+parcial", e) else None
            if k in vetos:
                vetos[k]["data"] = min(vetos[k]["data"], l["data"])
                vetos[k]["tipo"] = vetos[k]["tipo"] or tp
                continue
            vetos[k] = {"data": l["data"], "tipo": tp, "url": f"{BASE}/proposicao/{l['id']}", "ementa": l["ementa"][:160]}
    avisos = []
    # conferência: os vetos que a movimentação dos projetos cita
    citados: dict[str, tuple[str, str]] = {}
    for pid, d in dets.items():
        for data, texto in d.get("movs") or []:
            m = re.search(r"vetad[ao] (totalmente|parcialmente)\s*:?\s*veto n[o.]*\s*(\d+)\s*/\s*(\d{2,4})\s*-\s*([a-z]+)",
                          _norm(texto))
            if m and data and data >= inicio:
                k = f"{int(m.group(2)):04d}/{m.group(3)[-2:]}-{m.group(4).upper()}"
                citados[k] = (data, "total" if m.group(1).startswith("total") else "parcial")
    so_mov = sorted(set(citados) - set(vetos))
    if so_mov:
        avisos.append(f"{len(so_mov)} vetos citados na movimentação dos projetos sem a mensagem na lista de vetos: {so_mov[:10]}")
    return vetos, avisos


def _governo(el: Elegis, g: dict, inv: dict, dets: dict, listas: dict, leis: list[dict], origem_lei: dict, s_de) -> dict:
    """Os projetos que o Executivo mandou (bloco "propostas") e o bloco "executivo" (leis sancionadas e vetos)."""
    ini = g["inicio"]
    # projetos do Executivo
    lista = []
    for pid, x in inv.items():
        if x["t"] not in TIPOS_GOV or (x["data"] or "") < ini or not eh_executivo(x["origem"], x["num"]):
            continue
        s = s_de(pid)
        p = regional.proposta(f"{PREFIXO}:{pid}", x["sigla"], TIPOS[x["t"]][0], x["data"], x["ementa"], s["oficial"],
                              f"{BASE}/proposicao/{pid}", papel="autor", status=s["status"], data_status=s["data"],
                              status_txt=s["txt"], lei=s["lei"])
        lista.append(com_status_en(p, s["en"]))
    tipos = sorted({TIPOS[inv[p["id"].split(":")[1]]["t"]][0] for p in lista}, key=["PL", "PLP", "PEC"].index)
    esc, esc_en = G.escopo(g, tipos or ["PL"])
    f_prop = fonte(VEICULO, "Projetos do Poder Executivo (e-Legis da Alap)",
                   f"{BASE}/proposicoes?origem={urllib.parse.quote('Poder Executivo')}")
    bloco = regional.bloco_propostas(lista, esc, esc_en, f_prop)
    log(f"  gov-AP: {len(lista)} projetos do Executivo desde {ini}; situações {resumo_status([lista])}")
    # leis: numeração completa? quem assinou?
    por_tipo = {"LO": [], "LC": []}
    quem = {"governo": 0, "casa": 0, None: 0}
    sem_info = []
    for l in leis:
        q = quem_assinou(dets.get(origem_lei.get((l["sig"], l["numero"])) or ""))
        quem[q] += 1
        if q is None:
            sem_info.append(f"{l['sig']} {l['numero']}")
        por_tipo[l["sig"]].append({"tipo": l["sig"], "numero": l["numero"], "data": l["dataLei"], "promulgada": q == "casa",
                                   "quem": q})
    todas = por_tipo["LO"] + por_tipo["LC"]
    c = G.contar_leis(todas, ini)
    faixa = sum(x["ate"] - x["de"] + 1 for x in c["tipos"].values())
    falta = sum(len(x["faltam"]) for x in c["tipos"].values())
    dpt, den = G.data_pt(ini), G.data_en(ini)
    fontes = [fonte(VEICULO, "Legislação estadual: leis ordinárias e complementares (e-Legis da Alap)",
                    f"{BASE}/legislacao?tipo_proposicao_id=1"),
              fonte(VEICULO, "Mensagens de veto do Poder Executivo (e-Legis da Alap)", f"{BASE}/proposicoes?tipo_proposicao=6")]
    ex = {"periodo": {"inicio": ini, "fim": None}}
    sanc = [x for x in todas if x["quem"] == "governo"]
    if not todas:
        leis_pt = (f"O cadastro de legislação do e-Legis não tem nenhuma lei com data a partir de {dpt}: o número de leis "
                   "sancionadas fica fora do perfil.",
                   f"The e-Legis legislation records have no law dated from {den} on, so the number of laws signed is left "
                   "out of the profile.")
    elif faixa and falta > 0.02 * faixa:
        leis_pt = (f"Faltam leis no cadastro de legislação do e-Legis ({falta} dos {faixa} números de lei desde {dpt} não "
                   "aparecem): o número de leis sancionadas fica fora do perfil.",
                   f"Some laws are missing from the e-Legis legislation records ({falta} of the {faixa} law numbers since "
                   f"{den} are not there), so the number of laws signed is left out of the profile.")
    else:
        ex["leisSancionadas"] = len(sanc)
        if quem["casa"]:
            ex["leisPromulgadasPelaCasa"] = quem["casa"]
        ex["periodo"]["ultimaLei"] = max(x["data"] for x in sanc) if sanc else None
        partes, partes_en = [], []
        for t, nome, nome_en in (("LO", "ordinárias", "ordinary"), ("LC", "complementares", "complementary")):
            x = c["tipos"].get(t)
            if x:
                partes.append(f"{x['n']} {nome if x['n'] != 1 else nome[:-2] if nome.endswith('es') else nome[:-1]} "
                              f"(nº {G.numero(x['de'])} a {G.numero(x['ate'])})")
                partes_en.append(f"{x['n']} {nome_en} (No. {G.numero(x['de'], True)} to {G.numero(x['ate'], True)})")
        falt = [(t, n) for t, x in c["tipos"].items() for n in x["faltam"]]
        if falt:
            nums = G.lista_pt([f"{NOME_TIPO_LEI[t]} {G.numero(n)}" for t, n in falt[:6]]) + (" e outros" if len(falt) > 6 else "")
            nums_en = G.lista_pt([f"{'Complementary Law' if t == 'LC' else 'Law'} {G.numero(n, True)}" for t, n in falt[:6]],
                                 "and") + (" and others" if len(falt) > 6 else "")
            sem_falta = (f"; {len(falt)} número{'s' if len(falt) > 1 else ''} do período ({nums}) não aparece"
                         f"{'m' if len(falt) > 1 else ''} no cadastro e não entra{'m' if len(falt) > 1 else ''} na conta",
                         f"; {len(falt)} number{'s' if len(falt) > 1 else ''} in the period ({nums_en}) "
                         f"{'are' if len(falt) > 1 else 'is'} missing from the records and not counted")
        else:
            sem_falta = (", sem número faltando", ", with no number missing")
        pt = (f"Leis: {G.lista_pt(partes)} com data a partir de {dpt} no cadastro de legislação do e-Legis da Alap"
              f"{sem_falta[0]}; a mais recente é de {G.data_pt(c['ultima'])}. Contam como sancionadas as {len(sanc)} em "
              "que a movimentação do projeto diz que o governo sancionou (\"Proposição Sancionada\", inclusive com veto "
              "parcial).")
        en = (f"Laws: {G.lista_pt(partes_en, 'and')} dated from {den} on in the e-Legis legislation records of the Alap"
              f"{sem_falta[1]}; the most recent one is from {G.data_en(c['ultima'])}. The {len(sanc)} whose bill history "
              "says the government signed them (\"Proposição Sancionada\", including with a partial veto) count as signed.")
        fora, fora_en = [], []
        if quem["casa"]:
            fora.append(f"{quem['casa']} que a própria Assembleia promulgou (quando derruba um veto ou quando o governador "
                        "não sanciona nem veta no prazo)")
            fora_en.append(f"{quem['casa']} promulgated by the state legislature itself (when it overrides a veto or when "
                           "the governor neither signs nor vetoes in time)")
        if quem[None]:
            fora.append(f"{quem[None]} sem esse registro no e-Legis (a página do projeto não diz quem assinou, ou o projeto "
                        "não aparece na lista de proposições)")
            fora_en.append(f"{quem[None]} without that record in e-Legis (the bill's page does not say who signed it, or the "
                           "bill is not in the list of bills)")
        if fora:
            pt += " Ficam de fora " + " e ".join(fora) + "."
            en += " Left out: " + " and ".join(fora_en) + "."
        if not quem["casa"]:
            pt += " Nenhuma aparece como promulgada pela própria Assembleia."
            en += " None appears as promulgated by the state legislature itself."
        leis_pt = (pt, en)
        if sem_info:
            log(f"  gov-AP: leis sem a informação de quem assinou: {sem_info[:12]}")
    # vetos
    vetos, avisos = _vetos(listas, dets, inv, ini)
    for a in avisos:
        log(f"  gov-AP: ATENÇÃO: {a}")
    if vetos:
        tot = sum(1 for v in vetos.values() if v["tipo"] == "total")
        par = sum(1 for v in vetos.values() if v["tipo"] == "parcial")
        ex["vetos"] = len(vetos)
        if tot + par == len(vetos):
            ex["vetosTotais"], ex["vetosParciais"] = tot, par
        ex["periodo"]["ultimoVeto"] = max(v["data"] for v in vetos.values())
        det = f" ({tot} totais e {par} parciais)" if tot + par == len(vetos) else ""
        det_en = f" ({tot} full and {par} partial)" if tot + par == len(vetos) else ""
        vetos_pt = (f"Vetos: {len(vetos)}{det}, as mensagens de veto do governo (tipo \"Veto\" no e-Legis) que chegaram à "
                    f"Alap a partir de {dpt}, pela data de protocolo; a mesma mensagem cadastrada duas vezes conta uma vez.",
                    f"Vetoes: {len(vetos)}{det_en}, the government's veto messages (type \"Veto\" in e-Legis) received by "
                    f"the Alap from {den} on, by filing date; a message recorded twice counts once.")
    else:
        vetos_pt = (f"O e-Legis não registra nenhuma mensagem de veto desde {dpt}: como não dá para saber se não houve veto ou "
                    "se ele não foi cadastrado, o perfil não mostra o número de vetos.",
                    f"e-Legis records no veto message since {den}. Since there is no way to tell whether there was no veto "
                    "or it was not recorded, the profile does not show the number of vetoes.")
    vetos_pt = (vetos_pt[0] + " " + G.EM_EXERCICIO[0], vetos_pt[1] + " " + G.EM_EXERCICIO[1])
    if "leisSancionadas" not in ex and "vetos" not in ex:
        return {"propostas": bloco, "executivo": None, "notas": [leis_pt, vetos_pt]}
    ex["fonte"] = fontes
    ex["nota"] = f"{leis_pt[0]} {vetos_pt[0]}"
    ex["nota_en"] = f"{leis_pt[1]} {vetos_pt[1]}"
    ex["notaLeis"], ex["notaLeis_en"] = leis_pt
    ex["notaVetos"], ex["notaVetos_en"] = vetos_pt
    log(f"  gov-AP: {len(sanc)} leis sancionadas ({quem['casa']} promulgadas pela Assembleia, {quem[None]} sem a "
        f"informação; numeração {faixa - falta} de {faixa}), {len(vetos)} vetos")
    return {"propostas": bloco, "executivo": ex, "notas": []}


__all__ = ["BASE", "Elegis", "coletar_elegis", "situacao", "autores", "quem_assinou", "norma_de", "numero_oficial",
           "ler_pagina_lista", "ler_pagina_proposicao", "ler_csv_normas", "TIPOS"]
