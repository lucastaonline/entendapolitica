"""Leis e vetos nos títulos das matérias dos Diários Oficiais dos municípios (fase 4: o que cada prefeitura fez).

Funções puras (sem rede), usadas por scripts/municipios/diarios.py para todas as plataformas:

- `ler_titulo(titulo)`: o que um título diz — uma lei (ordinária ou complementar, com número, ano e data quando o título
  traz), uma prova de que uma lei existe (republicação, retificação, errata, anexo, termo de sanção), um veto ou nada.
- `contar_leis(...)`: junta as leis de uma cidade (cada número uma vez), separa as que a Câmara promulgou e confere a
  numeração (buracos, começo e fim do período): a contagem só vale quando a lista parece completa.
- `contar_vetos(...)`: só vale quando a prefeitura publica os vetos numerados, sem buracos.

Regras (conferidas à mão numa amostra de cidades de associações diferentes; ver notas/diarios-r3.md):
- Lei = título que começa com "Lei" (municipal, ordinária, complementar, orçamentária), seguido do número; ou um título
  com "Lei ... nº X, de <data>" depois de um texto que não é outro tipo de ato (ex.: "Reestruturação administrativa...
  Lei Complementar nº 215/2026, de 19 de março de 2026"). Ficam de fora: "Lei Orgânica" (é da Câmara), projetos de lei,
  autógrafos, decretos, portarias, avisos, extratos, atas e balanços que só citam uma lei (ex.: "Lei Federal 14.133/21").
- Republicação, retificação, errata, anexo e termo de sanção de uma lei contam como a mesma lei (o número só entra uma
  vez): mostram que a lei existe, mesmo quando a publicação original não aparece.
- Lei publicada pela Câmara Municipal (órgão "Câmara..." ou "Lei promulgada") não conta como sancionada pela prefeitura,
  mas o número dela vale para conferir a numeração (não é um buraco).
- Veto = "Veto", "Veto total/parcial/integral", "Mensagem de veto", "Razões do veto", "Justificativa de veto". Fora:
  decisões da Câmara sobre o veto (derrubada, manutenção, rejeição, acolhimento, decreto legislativo) e promulgações.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
         "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}
_MES = "|".join(MESES)

FALTANDO_MAX = 0.15     # no máximo 15% dos números de lei do período sem publicação (a mesma régua do SAPL)
BURACO_MAX = 5          # e nenhum buraco grande: no máximo 5 números seguidos faltando (ou 5% da faixa, se for maior)
BURACO_MAX_FRACAO = 0.05
SALTO_MAX = 50          # um salto maior que este entre números vizinhos é erro de digitação ou outra sequência
ATRASO_MAX_DIAS = 120   # a lei mais nova tem de ser recente; senão a prefeitura parou de publicar as leis ali
MIN_LEIS = 3            # com menos leis que isso no período, não dá para conferir a numeração


def norm(s: str | None) -> str:
    """Maiúsculas, sem acentos, com "nº/n°/n.º/№" virando " NO " e espaços simples."""
    t = (s or "").upper()
    for a, b in (("º", "O"), ("°", "O"), ("˚", "O"), ("ª", "A"), ("№", "NO "), ("–", "-"), ("—", "-"), ("‐", "-"),
                 ("“", '"'), ("”", '"'), ("’", "'"), ("´", "'"), ("\u00a0", " ")):
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\bN\s*\.?\s*O\s*\.?(?=[\s\d_:,.\-]|$)", " NO ", t)
    t = re.sub(r"\bNUMERO\b|\bNRO?\b\.?|\bNUM\b\.?", " NO ", t)
    t = re.sub(r"\bN\.(?=\s*\d)", " NO ", t)
    return re.sub(r"\s+", " ", t).strip()


# outros tipos de ato no começo do título (o título "fala de" uma lei, mas não é a lei)
_OUTRO_ATO = re.compile(
    r"\b(DECRETO|PORTARIA|RESOLUCAO|INSTRUCAO|ERRATA|RETIFICA\w*|REPUBLICA\w*|EXTRATO|ANEXO\w*|ATA|AVISO|EDITAL|TERMO|"
    r"PROJETO|MENSAGEM|VETO|AUTOGRAFO|SANCAO|PROMULGA\w*|ALTERA\w*|REGULAMENTA\w*|TERMOS|CONFORME|BASE|BALANCO|"
    r"DEMONSTRA\w*|RELATORIO|PARECER|CONVITE|CONVOCA\w*|AUDIENCIA|DISPENSA|INEXIGIBILIDADE|LICITA\w*|CONTRAT\w*|"
    r"CHAMAMENTO|OFICIO|CERTIDAO|NOTIFICA\w*|PUBLICACAO|ACORDO|CONVENIO|HOMOLOGA\w*|RATIFICA\w*|ADJUDICA\w*|PREGAO|"
    r"CONCURSO|PROCESSO|SELECAO|CREDENCIA\w*|LEILAO|SUMULA|JUSTIFICATIVA|RAZOES|ADITIVO|DESPACHO|COMUNICADO|"
    r"DA LEI|A LEI|NA LEI|DE LEI|PELA LEI|COM A LEI|DAS LEIS|DE ACORDO)\b")
# o que vem antes de "Lei nº X" e quer dizer "é outra publicação da mesma lei"
_PROVA = re.compile(r"^(REPUBLICA\w*|RETIFICA\w*|ERRATA|ANEXOS?|TERMO DE SANCAO|SANCAO)\b")
_REPUBLICACAO = re.compile(r"\bREPUBLICA\w*|\bPOR INCORRECAO\b|\bRETIFICA\w*|\bERRATA\b")
_QUALIF = r"(?:\s+(?:MUNICIPAL|MUNICIAL|MUNICIPAIS|MUN\.?|ORDINARIA|COMPLEMENTAR|ORCAMENTARIA|DE|DA|DO|ESPECIFICA))*"
_NUM = r"(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,6})"
_LEI_INICIO = re.compile(r"^\W*LEI(?P<qual>" + _QUALIF + r")[\s,.:\-_]*(?:NO\b\s*)*[\s,.:\-_]*" + _NUM + r"(?![\d])")
_LEI_MEIO = re.compile(r"\bLEI(?P<qual>" + _QUALIF + r")\s*(?:NO\b\s*)+[\s,.:\-_]*" + _NUM + r"(?![\d])")
_LEI_PROVA = re.compile(r"^(?:REPUBLICA\w*|RETIFICA\w*|ERRATA|ANEXOS?|TERMO DE SANCAO|SANCAO)\W+(?:(?:DA|DE|A|AO|NA)\s+)?"
                        r"LEI(?P<qual>" + _QUALIF + r")[\s,.:\-_]*(?:NO\b\s*)*[\s,.:\-_]*" + _NUM + r"(?![\d])")
_LEI_SEM_NUMERO = re.compile(r"^\W*LEI(?:\s+(?:MUNICIPAL|ORDINARIA|COMPLEMENTAR))+\W*$")
_ANO_BARRA = re.compile(r"^\s*[/\-]\s*(?:[A-Z]{1,12}\s*[/\-]\s*)*(?P<ano>(?:19|20)\d{2})\b")
_ANO_CURTO = re.compile(r"^\s*[/\-]\s*(?P<ano>\d{2})(?![\d])")
_ANO_DE = re.compile(r"^\s*,?\s*DE\s+(?P<ano>(?:19|20)\d{2})\b")
_DATA = re.compile(r"(?P<d>\d{1,2})\s*O?\s*(?:DE\s+)?(?P<m>" + _MES + r")\s*(?:DE\s+|,\s*)?(?P<a>(?:19|20)\d{2})")
_DATA_NUM = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<a>(?:19|20)\d{2})\b")
_CAMARA = re.compile(r"C[AÂ]MARA|LEGISLATIV|VEREADOR", re.I)
_CORTE_EMENTA = re.compile(r"\s[-=:]\s|\s[-=]\s*$|[\"(]|\b(?:DISPOE|ALTERA|AUTORIZA|INSTITUI|CRIA|DENOMINA|ESTIMA|ABRE|"
                           r"CONCEDE|DEFINE|REVOGA|FIXA|ACRESCENTA|REGULAMENTA|NOMEIA|INSERE|DECLARA|EMENTA|LEI)\b")

_VETO = re.compile(r"^\W*(?:(?:MENSAGEM|RAZOES|RAZAO|JUSTIFICATIVA|COMUNICACAO|OFICIO)(?:\s+\w+){0,3}?\s+(?:DE|DO|DOS|AO)\s+)?"
                   r"VETOS?\b(?P<resto>.*)$")
_NAO_VETO = re.compile(r"DERRUBAD|REJEI|MANUTEN|MANTEM|MANTIDO|ACOLH|APRECIA|PROMULGA|DECRETO LEGISLATIVO|SANCAO OU VETO|"
                       r"SANCAO TACITA|SILENCIO|PARECER|VOTACAO|SESSAO|PAUTA|ORDEM DO DIA|EDITAL|AVISO|ATA\b|LEILAO")


def _ano_curto(a: str, ref: int) -> int:
    n = int(a)
    return 2000 + n if 2000 + n <= ref + 1 else 1900 + n


def _data(t: str) -> str | None:
    m = _DATA.search(t)
    if m:
        try:
            return date(int(m["a"]), MESES[m["m"]], int(m["d"])).isoformat()
        except ValueError:
            return None
    m = _DATA_NUM.search(t)
    if m:
        try:
            return date(int(m["a"]), int(m["m"]), int(m["d"])).isoformat()
        except ValueError:
            return None
    return None


def _numero(s: str) -> int:
    return int(s.replace(".", ""))


def ler_titulo(titulo: str | None, ano_ref: int = 2026) -> dict | None:
    """{"tipo": "lei"|"veto", ...} ou None.
    Lei: {"tipo": "lei", "lc": bool, "num": int|None, "ano": int|None, "data": "AAAA-MM-DD"|None, "prova": bool,
          "promulgada": bool}. num None = título sem número ("Lei Municipal"): o número está no texto da matéria.
    Veto: {"tipo": "veto", "num": int|None, "ano": int|None, "parcial": bool|None, "projeto": "12/2025"|None}."""
    t = norm(titulo)
    if not t:
        return None
    mv = _VETO.match(t)
    if mv and not _NAO_VETO.search(t):
        resto = mv["resto"]
        parcial = True if re.search(r"\bPARCIA", t) else (False if re.search(r"\b(TOTAL|INTEGRAL)\b", t) else None)
        num = ano = None
        m = re.match(r"^\s*(?:(?:TOTAL|PARCIAL|INTEGRAL)\s+)?(?:NO\b)?[\s.:\-]*(?P<n>\d{1,4})(?P<r>.*)$", resto)
        if m and not re.match(r"^\s*(?:TOTAL|PARCIAL|INTEGRAL)?\s*(?:AO|A|DO|NO PROJETO)\b", resto):
            num = int(m["n"])
            r = m["r"]
            ma = _ANO_BARRA.match(r) or _ANO_DE.match(r)
            if ma:
                ano = int(ma["ano"])
            else:
                mc = _ANO_CURTO.match(r)
                ano = _ano_curto(mc["ano"], ano_ref) if mc else None
        mp = re.search(r"PROJETO DE LEI(?: COMPLEMENTAR)?(?: \w+)?\s*(?:NO\b)?[\s.:\-]*(\d{1,4})\s*[/\-]\s*((?:19|20)?\d{2})", t)
        projeto = None
        if mp:
            a = mp.group(2)
            projeto = f"{int(mp.group(1))}/{a if len(a) == 4 else _ano_curto(a, ano_ref)}"
        return {"tipo": "veto", "num": num, "ano": ano, "parcial": parcial, "projeto": projeto}
    prova = False
    m = _LEI_INICIO.match(t)
    if m:
        ini = 0
    elif _LEI_PROVA.match(t):
        m = _LEI_PROVA.match(t)
        prova = True
        ini = 0
    else:
        mp = _PROVA.match(t)
        m = _LEI_MEIO.search(t)
        if not m:
            if _LEI_SEM_NUMERO.match(t) and not _REPUBLICACAO.search(t):
                return {"tipo": "lei", "lc": "COMPLEMENTAR" in t, "num": None, "ano": None, "data": None, "prova": False,
                        "promulgada": "PROMULGAD" in t}
            return None
        antes = t[:m.start()]
        if mp:
            prova = True
        elif _OUTRO_ATO.search(antes):
            return None
        ini = m.start()
    qual = m["qual"] or ""
    if re.search(r"\bORGANICA\b", t[ini:m.end()]) or "FEDERAL" in qual or "ESTADUAL" in qual:
        return None
    if re.match(r"^\W*LEI\s+(?:FEDERAL|ESTADUAL|ORGANICA)\b", t[ini:]):
        return None
    num = _numero(m["num"])
    depois = t[m.end():]
    ano = None
    ma = _ANO_BARRA.match(depois) or _ANO_DE.match(depois)
    if ma:
        ano = int(ma["ano"])
    else:
        mc = _ANO_CURTO.match(depois)
        if mc:
            ano = _ano_curto(mc["ano"], ano_ref)
    # a data da lei vem logo depois do número; a ementa (depois de " - ", "Dispõe"...) pode citar outras leis e datas
    corte = _CORTE_EMENTA.search(depois)
    dt = _data((depois[:corte.start()] if corte else depois)[:90])
    if dt and ano and abs(int(dt[:4]) - ano) > 1:
        dt = None
    if dt and not ano:
        ano = int(dt[:4])
    if ano and (ano < 1950 or ano > ano_ref + 1):
        return None
    return {"tipo": "lei", "lc": "COMPLEMENTAR" in qual, "num": num, "ano": ano, "data": dt,
            "prova": prova or bool(_REPUBLICACAO.search(depois)), "promulgada": "PROMULGAD" in t}


def eh_camara(orgao: str | None, entidade: str | None = None) -> bool:
    """A publicação é da Câmara Municipal (órgão ou entidade)?"""
    return bool(_CAMARA.search(orgao or "")) or bool(re.match(r"(?i)\s*c[aâ]mara", entidade or ""))


_LEI_QUALQUER = re.compile(r"\bLEIS?(?P<qual>(?:[\s\-]+(?!NO\b)[A-Z]+\.?){0,3}?)[\s,.:\-_]*(?:NO\b[\s.\-]*)*[\s,.:\-_]*" + _NUM +
                           r"(?![\d])")
# nomes de arquivo: "LC 57-2026", "LO 3575", "LM 6662-2026", "L 985", "l5215", "l-1491-2026", "Compl. 130-26",
# "leicomplementar151_26", "leic150_26", "LEIS 02679 2026", "LEIS COMPLEMENTARES 00659 2026"
_PREFIXO = re.compile(r"^\W*(?P<p>LEIS COMPLEMENTARES|LEICOMPLEMENTAR|LEIC|LEIS|COMPL\w*\.?|LC|LO|LM|L)"
                      r"(?:\s*(?:NO\b[\s.\-]*)*)[\s.\-]*(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,5})(?![\d])(?P<resto>.*)$")
# só o número no começo ("3985", "4.377", "1609- LEI ...", "9152.lei"); não vale "15.07.2026", "49602026", "2.29526"
_NUMERO_INICIO = re.compile(r"^\W*(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,5})(?=$|[\s\-(,]|\.(?!\d))(?P<resto>.*)$")
# "19- 207-26 - LEI ...": um índice e depois o número e o ano
_INDICE_NUM_ANO = re.compile(r"^\W*\d{1,3}\s*-\s*(?P<num>\d{1,5})\s*-\s*(?P<ano>\d{2})\b(?P<resto>.*)$")
_ANEXO = re.compile(r"\b(ANEXOS?|DEMONSTRATIVOS?|MEMORIAL|CROQUI|MATRICULA|ESTATUTO|PROTOCOLO|PLANTA|MAPA|TABELA|QUADRO|"
                    r"RELATORIO|PARECER|OFICIO|AUDIENCIA|AUTOGRAFO|METAS|RISCOS|AMF|DESPESAS?|RECEITAS?|CONVOCACAO|"
                    r"CONVITE|NOTIFICACAO|JUSTIFICATIVA|MENSAGEM|PROJETO|PL|PLL|PLC|EMENDAS?|DECRETO|DEC|PORTARIA|PORTAIA|"
                    r"RESOLUCAO|EDITAL|EXTRATO|ATA|AVISO|CONTRATO|TERMO|VETO|ERRATA|RETIFICA\w*|REPUBLICA\w*)\b")


def _ano_resto(resto: str, ano_ref: int) -> int | None:
    m = re.match(r"^\s*[/\-_.\s]\s*(?P<ano>(?:19|20)\d{2})(?![\d])", resto) or re.match(r"^\s*,?\s*DE\s+(?P<ano>(?:19|20)\d{2})\b",
                                                                                         resto)
    if m:
        return int(m["ano"])
    m = re.match(r"^\s*[/\-_]\s*(?P<ano>\d{2})(?![\d])", resto)
    return _ano_curto(m["ano"], ano_ref) if m else None


def _lei_lista(num: str, lc: bool, resto: str, t: str, ano_ref: int) -> dict | None:
    n = _numero(num)
    ano = _ano_resto(resto, ano_ref)
    if ano and (ano < 1950 or ano > ano_ref + 1):
        ano = None
    corte = _CORTE_EMENTA.search(resto)
    dt = _data((resto[:corte.start()] if corte else resto)[:90])
    if dt and not ano:
        ano = int(dt[:4])
    return {"tipo": "lei", "lc": lc, "num": n, "ano": ano, "data": dt, "prova": bool(_REPUBLICACAO.search(t)),
            "promulgada": bool(re.search(r"PROMULGAD|SANCIONADA PELA CAMARA", t))}


_INICIO_OUTRO = re.compile(r"^\W*(?:" + _ANEXO.pattern[3:-3] + r")\b")
_VARIAS = re.compile(r"^\W*LEIS\s+(?:NOS?\b\s*)?(?P<a>\d{1,3}(?:\.\d{3})+|\d{1,5})\s*(?:(?P<ate>A|ATE|AO)\s+|(?P<lista>(?:\s*,\s*"
                     r"(?:\d{1,3}(?:\.\d{3})+|\d{1,5}))*\s*E\s+))(?P<b>\d{1,3}(?:\.\d{3})+|\d{1,5})(?![\d])")


def _colado(num: str, ano_ref: int) -> tuple[str, str] | None:
    """"30682026" -> ("3068", "2026"): número e ano grudados."""
    m = re.fullmatch(r"(\d{1,5})((?:19|20)\d{2})", num)
    if m and 1990 <= int(m.group(2)) <= ano_ref + 1 and int(m.group(1)) > 0:
        return m.group(1), m.group(2)
    return None


def ler_titulo_lista(titulo: str | None, ano_ref: int = 2026) -> dict | None:
    """Título de um item de uma lista que já é só de leis (a seção "Leis" de um Diário): o título muitas vezes é o nome do
    arquivo ("LEI 1767 PARA DOM", "Lei Odinária 4301-2026", "LC 57-2026", "l5215", "3985 - Dispõe..."). Anexos,
    demonstrativos, projetos e outros tipos de ato que caíram na lista não contam (None). Um título de lei sem número
    (nome de arquivo de scanner, "LEIS") devolve uma lei com num None: o item existe, mas não dá para saber qual lei é.
    "Leis 1754 até 1760" e "Leis 1348, 1349 e 1350" devolvem a primeira em "num" e as outras em "mais"."""
    x = ler_titulo(titulo, ano_ref)
    if x is not None:
        return x if x["tipo"] == "lei" else None
    t = norm(titulo).replace("_", " ")
    t = re.sub(r"\bN\s+(?=\d)", "NO ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if re.search(r"\bLEI ORGANICA\b|\bLOM\b", t):
        return None
    m = _VARIAS.match(t)
    if m:
        a, b = _numero(m["a"]), _numero(m["b"])
        if m["ate"] and 0 < b - a <= 30:
            mais = list(range(a + 1, b + 1))
        else:
            mais = [_numero(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})+|\d{1,5}", t[m.end("a"):m.end("b")])]
        y = _lei_lista(m["a"], False, t[m.end():], t, ano_ref)
        y["mais"] = [n for n in mais if n != a]
        return y
    m = re.search(r"(?<![A-Z])(?P<p>LC|LO|LM|LEI)\s+NO\s+(?P<num>\d{1,3}(?:\.\d{3})+|\d{1,5})(?![\d])(?P<resto>.*)$", t)
    if m:
        return _lei_lista(m["num"], m["p"] == "LC", m["resto"], t, ano_ref)
    m = _LEI_QUALQUER.search(t)
    if m and not re.search(r"\b(FEDERAL|ESTADUAL|ORGANICA)\b", m["qual"] or ""):
        qual = m["qual"] or ""
        n = _numero(m["num"])
        sem_no = not re.search(r"\bNO\b", t[m.start():m.start("num")])
        nome_estranho = qual.strip(" -") and not re.fullmatch(
            r"(?:[\s\-]*(?:COMPL\w*|ORD\w*|ODIN\w*|MUNIC\w*|NUMERO|N|PROMULGADA))+[\s\-]*", qual)
        # "Lei Refis 2025": o número é o ano, não o da lei
        if not (sem_no and nome_estranho and 1990 <= n <= ano_ref + 1):
            return _lei_lista(m["num"], bool(re.search(r"\bCOMPL", qual)), t[m.end():], t, ano_ref)
    m = re.match(r"^\W*LEI\s+(?:NO\b\s*)?(?P<num>\d{6,9})\b(?P<resto>.*)$", t)
    if m and _colado(m["num"], ano_ref):
        num, ano = _colado(m["num"], ano_ref)
        return _lei_lista(num, False, "/" + ano + m["resto"], t, ano_ref)
    for rx, lc_de in ((_INDICE_NUM_ANO, None), (_PREFIXO, "p"), (_NUMERO_INICIO, None)):
        m = rx.match(t)
        if not m:
            continue
        lc = bool(lc_de and re.match(r"LC|LEIC|LEICOMPL|COMPL|LEIS COMPL", m["p"]))
        resto = m["resto"]
        if rx is _INDICE_NUM_ANO:
            resto = "/" + m["ano"] + resto
        # o que vem logo depois do número não pode ser outro tipo de ato ("23 Convocação...", "03-Despesas por programa")
        if rx is _NUMERO_INICIO and _INICIO_OUTRO.match(resto):
            continue
        return _lei_lista(m["num"], lc, resto, t, ano_ref)
    m = re.match(r"^\W*(?P<num>\d{6,9})\b(?P<resto>.*)$", t)
    if m and _colado(m["num"], ano_ref) and not _INICIO_OUTRO.match(m["resto"]):
        num, ano = _colado(m["num"], ano_ref)
        return _lei_lista(num, False, "/" + ano + m["resto"], t, ano_ref)
    if _ANEXO.search(t):
        return None
    return {"tipo": "lei", "lc": bool(re.search(r"\bCOMPL", t)), "num": None, "ano": None, "data": None, "prova": False,
            "promulgada": bool(re.search(r"PROMULGAD|SANCIONADA PELA CAMARA", t))}

# ---------------------------------------------------------------------------------------------------- contagem
def _buracos(nums: list[int]) -> tuple[int, int, int]:
    """(faltando, faixa, maior buraco) numa lista ordenada de números de uma sequência."""
    falta = maior = 0
    for a, b in zip(nums, nums[1:]):
        if 1 < b - a <= SALTO_MAX:
            falta += b - a - 1
            maior = max(maior, b - a - 1)
    return falta, len(nums) + falta, maior


def _fora_da_sequencia(nums: set[int]) -> set[int]:
    """Números longe da sequência principal: erro de digitação ("Lei nº 001/2026" no meio das leis 620 a 635) ou outra
    numeração pequena ("Lei 83-2025" no meio das leis 5.046 a 5.414). Os números são separados em grupos (um salto de mais
    de SALTO_MAX começa outro grupo); os grupos pequenos (até 10% dos números) ficam fora. Só com 5 números ou mais."""
    s = sorted(nums)
    if len(s) < 5:
        return set()
    grupos, atual = [], [s[0]]
    for a, b in zip(s, s[1:]):
        if b - a > SALTO_MAX:
            grupos.append(atual)
            atual = [b]
        else:
            atual.append(b)
    grupos.append(atual)
    if len(grupos) == 1:
        return set()
    principal = max(grupos, key=len)
    return {n for g in grupos if g is not principal and len(g) <= max(1, len(s) // 10) for n in g}


def _sequencia(por_ano: dict[int, set[int]], antes: list[int]) -> dict:
    """Confere uma sequência de números (por ano). `antes` = números da mesma sequência de antes do período.
    Numeração contínua (não recomeça no ano novo) ou anual (recomeça em 1 a cada ano).
    "inicio": True = o começo do período foi conferido (a 1ª lei do período vem logo depois da última de antes, ou a
    numeração recomeça em 1 no ano)."""
    anos = sorted(por_ano)
    todos = sorted(set().union(*por_ano.values())) if por_ano else []
    if not todos:
        return {"falta": 0, "faixa": 0, "maior": 0, "modo": None, "inicio": False}
    continua_mesmo = all(min(por_ano[b]) > max(por_ano[a]) - 3 for a, b in zip(anos, anos[1:]))
    recomeca = all(min(por_ano[a]) - 1 <= SALTO_MAX for a in anos) and (
        len(anos) > 1 and not continua_mesmo or min(por_ano[anos[0]]) <= 3)
    if recomeca and not (continua_mesmo and len(anos) > 1):
        fa = fxa = mxa = 0
        for a in anos:
            s = sorted(por_ano[a])
            f1, fx1, mx1 = _buracos(s)
            fa, fxa, mxa = fa + f1 + s[0] - 1, fxa + fx1 + s[0] - 1, max(mxa, mx1, s[0] - 1)
        return {"falta": fa, "faixa": fxa, "maior": mxa, "modo": "anual", "inicio": True}
    f, fx, mx = _buracos(todos)
    perto = [n for n in antes if todos[0] - SALTO_MAX - 1 <= n < todos[0]]
    inicio = False
    if perto:
        g = todos[0] - max(perto) - 1
        f, fx, mx = f + g, fx + g, max(mx, g)
        inicio = True
    elif todos[0] <= 3:          # a numeração começa (de novo) no período: lei nº 1
        g = todos[0] - 1
        f, fx, mx = f + g, fx + g, max(mx, g)
        inicio = True
    return {"falta": f, "faixa": fx, "maior": mx, "modo": "continua", "inicio": inicio}


def contar_leis(itens: list[dict], inicio: str, hoje: str) -> dict:
    """Leis de UMA cidade. itens = [{"lei": ler_titulo(...), "circ": "AAAA-MM-DD", "camara": bool, "id": ...}], desde uns
    3 meses antes do começo do período (para saber o último número de antes). Devolve {"ok": bool, "motivo": código|None,
    "leis": n (sancionadas: publicadas pela prefeitura), "promulgadas": n (só pela Câmara), "ultima": data, "falta": n,
    "faixa": n, "maior": n, "fora_seq": n, "sem_numero": n, "sem_data": n, "inicio_conferido": bool, "numeros": [...]}.
    Motivos: "sem_numero" (títulos sem o número da lei), "nenhuma"/"poucas", "parou" (a lei mais nova é antiga),
    "buracos" (faltam mais de 15% dos números), "inicio" (não deu para conferir o começo da numeração)."""
    ano_ini = int(inicio[:4])
    sem_numero = 0
    antes: dict[bool, set[int]] = {False: set(), True: set()}
    brutos = []          # (complementar?, número, ano, ano dito no título?, data, ref, câmara?, id)
    for x in itens:
        lei = x.get("lei") or {}
        if lei.get("tipo") != "lei":
            continue
        circ = x.get("circ") or ""
        if lei.get("num") is None:
            if circ >= inicio:
                sem_numero += 1
            continue
        dt = lei.get("data")
        ano = lei.get("ano")
        # a data que vale: a da lei (no título); senão o ano do número; senão a da publicação
        if dt:
            no_periodo = dt >= inicio
        elif ano:
            no_periodo = ano > ano_ini or (ano == ano_ini and (inicio[5:] == "01-01" or circ >= inicio))
        else:
            no_periodo = circ >= inicio
        k = bool(lei.get("lc"))
        if not no_periodo:
            antes[k].add(lei["num"])
            antes[k].update(lei.get("mais") or [])
            continue
        camara = bool(x.get("camara")) or bool(lei.get("promulgada"))
        ref = dt or (f"{ano}-12-31" if ano and circ[:4].isdigit() and ano < int(circ[:4]) else circ)
        a_ref = ano or (int(dt[:4]) if dt else int(circ[:4] or 0))
        for num in [lei["num"]] + list(lei.get("mais") or []):
            brutos.append((k, num, a_ref, bool(ano or dt), dt, ref, camara, x.get("id")))
    # numeração que recomeça a cada ano (lei nº 1 de 2025, lei nº 1 de 2026...): o mesmo número em anos diferentes são
    # leis diferentes. Senão (a numeração continua), o mesmo número é a mesma lei (republicada em outro ano).
    recomeca = {}
    for k in (False, True):
        por_ano: dict[int, set[int]] = {}
        for b in brutos:
            if b[0] == k and b[3]:
                por_ano.setdefault(b[2], set()).add(b[1])
        anos = sorted(por_ano)
        # recomeça mesmo: o ano seguinte começa perto do 1 (um número errado repetido não é recomeço)
        recomeca[k] = any(len(por_ano[a]) >= 2 and len(por_ano[b]) >= 2 and min(por_ano[b]) <= 3 and
                          max(por_ano[a]) > min(por_ano[b]) + 3 for a, b in zip(anos, anos[1:]))
    registros: dict[tuple, dict] = {}   # (complementar?, número[, ano]) -> registro
    for k, num, a_ref, _, dt, ref, camara, ident in brutos:
        chave = (k, num, a_ref) if recomeca[k] else (k, num)
        r = registros.get(chave)
        if r is None:
            registros[chave] = {"lc": k, "num": num, "ano": a_ref, "data": dt, "ref": ref, "camara": camara,
                                "ids": [ident]}
        else:
            r["ids"].append(ident)
            if not camara:
                r["camara"] = False      # a prefeitura também publicou: é lei sancionada
            if dt and not r["data"]:
                r["data"], r["ref"] = dt, dt
    # números longe da sequência principal (erro de digitação ou outra numeração pequena) não entram; nem, quando a
    # numeração continua de um ano para o outro, números menores que o da última lei de antes do período (republicação
    # de uma lei antiga ou erro de digitação: não é lei nova)
    fora = set()
    for k in (False, True):
        nums = {c[1] for c in registros if c[0] == k}
        isolados = _fora_da_sequencia(nums)
        fora |= {c for c in registros if c[0] == k and c[1] in isolados}
        if not recomeca[k] and nums and antes[k]:
            nucleo = [n for n in nums if n not in isolados]
            perto = [a for a in antes[k] if nucleo and min(nucleo) - SALTO_MAX - 1 <= a < max(nucleo)]
            if perto:
                ultimo = max(perto)
                velhos = {n for n in nums if n <= ultimo}
                if len(velhos) <= max(1, len(nums) // 10):
                    fora |= {c for c in registros if c[0] == k and c[1] in velhos}
    regs = [r for c, r in registros.items() if c not in fora]
    sanc = [r for r in regs if not r["camara"]]
    prom = [r for r in regs if r["camara"]]
    out = {"ok": False, "motivo": None, "leis": len(sanc), "promulgadas": len(prom), "ultima": None, "falta": 0,
           "faixa": 0, "maior": 0, "fora_seq": len(fora), "sem_numero": sem_numero, "modo": None,
           "inicio_conferido": False, "sem_data": sum(1 for r in sanc if not r["data"]),
           "numeros": sorted(((("LC " if r["lc"] else "") + str(r["num"]), r["ref"], r["camara"]) for r in regs),
                             key=lambda z: (z[1], z[0]))}
    if sanc:
        out["ultima"] = max(r["ref"] for r in sanc)
        out["primeira"] = min(r["ref"] for r in sanc)
    # publicações de lei sem o número no título: até 5% das leis contadas (no mínimo 1, com 10 leis ou mais), elas não
    # entram na conta e a nota diz quantas são; mais que isso, não dá para saber se a lista está completa
    tolera = max(1, int(0.05 * len(sanc))) if len(sanc) >= 10 else 0
    if sem_numero > tolera:
        out["motivo"] = "sem_numero"
        return out
    if len(sanc) < MIN_LEIS:
        out["motivo"] = "poucas" if sanc else "nenhuma"
        return out

    def seq(filtro):
        por_ano: dict[int, set[int]] = {}
        for r in regs:
            if filtro(r):
                por_ano.setdefault(r["ano"], set()).add(r["num"])
        return por_ano

    # ordinárias e complementares em sequências separadas (o comum) ou na mesma: vale o jeito com menos buracos.
    # O começo do período é conferido na sequência das ordinárias (as complementares são poucas e antigas).
    sep = [_sequencia(seq(lambda r, k=k: r["lc"] == k), sorted(antes[k])) for k in (False, True)]
    jun = _sequencia(seq(lambda r: True), sorted(antes[False] | antes[True]))
    s_falta, s_faixa = sum(s["falta"] for s in sep), sum(s["faixa"] for s in sep)
    principal = sep[0] if sep[0]["faixa"] else sep[1]
    if jun["faixa"] and jun["falta"] < s_falta:
        esc = jun
        # ordinárias e complementares na mesma numeração: um número só conta uma vez (ex.: a mesma lei publicada uma vez
        # como "Lei nº 801" e outra como "Lei Complementar nº 801")
        unicos: dict = {}
        for r in regs:
            u = (r["num"], r["ano"]) if (recomeca[False] or recomeca[True]) else r["num"]
            unicos[u] = unicos.get(u, True) and r["camara"]
        out["leis"] = sum(1 for c in unicos.values() if not c)
        out["promulgadas"] = sum(1 for c in unicos.values() if c)
    else:
        esc = {"falta": s_falta, "faixa": s_faixa, "maior": max(s["maior"] for s in sep), "modo": principal["modo"],
               "inicio": principal["inicio"]}
    out.update({k: esc[k] for k in ("falta", "faixa", "maior", "modo")})
    out["inicio_conferido"] = bool(esc["inicio"])
    # o maior buraco (números seguidos que faltam) na sequência principal: um buraco grande é um lote de leis que não foi
    # publicado ali (as complementares, poucas e esparsas, não entram nesta conta)
    seq_p = esc if esc is jun else principal
    out["maior"] = seq_p["maior"]
    limite = (date.fromisoformat(hoje) - timedelta(days=ATRASO_MAX_DIAS)).isoformat()
    if out["ultima"] < limite:
        out["motivo"] = "parou"
    elif esc["faixa"] and esc["falta"] > FALTANDO_MAX * esc["faixa"]:
        out["motivo"] = "buracos"
    elif seq_p["maior"] > max(BURACO_MAX, BURACO_MAX_FRACAO * seq_p["faixa"]):
        out["motivo"] = "buraco_grande"
    elif not esc["inicio"]:
        out["motivo"] = "inicio"
    else:
        out["ok"] = True
    return out


def contar_vetos(itens: list[dict], inicio: str, hoje: str) -> dict:
    """Vetos de UMA cidade (itens com "veto" = ler_titulo(...)), desde uns 3 meses antes do período. Só vale quando a
    prefeitura publica os vetos numerados e a numeração do período não tem buracos: ou recomeça em 1 a cada ano, ou
    continua a de antes do período (o último veto de antes é conhecido). Nenhum veto publicado no período não quer dizer
    zero vetos: nesse caso o número fica fora."""
    ano_ini = int(inicio[:4])
    por_ano: dict[int, set[int]] = {}
    antes: set[int] = set()
    sem_num = 0
    parciais = totais = 0
    for x in itens:
        v = x.get("veto") or {}
        if v.get("tipo") != "veto":
            continue
        circ = x.get("circ") or ""
        ano = v.get("ano") or (int(circ[:4]) if circ[:4].isdigit() else None)
        if circ < inicio:
            if v.get("num") is not None:
                antes.add(v["num"])
            continue
        if v.get("num") is None:
            sem_num += 1
            continue
        if ano and ano < ano_ini:
            antes.add(v["num"])
            continue
        if v["num"] not in por_ano.get(ano, set()):
            if v.get("parcial") is True:
                parciais += 1
            elif v.get("parcial") is False:
                totais += 1
        por_ano.setdefault(ano, set()).add(v["num"])
    n = sum(len(s) for s in por_ano.values())
    out = {"ok": False, "vetos": n, "sem_numero": sem_num, "parciais": parciais, "totais": totais, "motivo": None,
           "modo": None}
    if sem_num:
        out["motivo"] = "sem_numero"
        return out
    if not n:
        out["motivo"] = "nenhum"
        return out
    anos = sorted(por_ano)
    # recomeça em 1 a cada ano (e há vetos no primeiro ano do período: um ano sem nenhum veto publicado não dá para conferir)
    if all(min(por_ano[a]) == 1 and max(por_ano[a]) == len(por_ano[a]) for a in anos) and (
            ano_ini in por_ano or ano_ini == int(hoje[:4])):
        out.update({"ok": True, "modo": "anual"})
        return out
    # continua a numeração de antes do período
    todos = sorted(set().union(*por_ano.values()))
    if len(todos) == n and todos[-1] - todos[0] + 1 == n:
        perto = [a for a in antes if 0 < todos[0] - a <= 3]
        if perto and todos[0] == max(perto) + 1:
            out.update({"ok": True, "modo": "continua"})
            return out
        out["motivo"] = "inicio"
        return out
    out["motivo"] = "buracos"
    return out

__all__ = ["norm", "ler_titulo", "ler_titulo_lista", "eh_camara", "contar_leis", "contar_vetos", "FALTANDO_MAX",
           "ATRASO_MAX_DIAS"]
