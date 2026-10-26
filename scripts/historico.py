"""Mandatos anteriores: quem foi eleito para cada mandato desde 1994, segundo os dados abertos do TSE.

O site mostra, por padrão, quem está no cargo hoje. Nas páginas do Brasil, do estado e da cidade, o campo
"Ver outro mandato" mostra quem foi ELEITO para cada mandato anterior. Este script gera esses dados:

- dados/historico/indice.json ............... os mandatos de cada nível (brasil, estados, cidades): datas, rótulos, fontes
- dados/historico/brasil/<ano>.json ........ presidente e vice, os 81 senadores e os 513 deputados federais do mandato
                                              que começou em <ano> (1995, 1999, ..., 2023)
- dados/historico/estados/<UF>.json ........ governador(a), vice e deputados estaduais/distritais de cada mandato
- dados/historico/cidades/<UF>/<ano>.json .. prefeito(a), vice e vereadores de cada cidade do estado no mandato que
                                              começou em <ano> (1997, 2001, ..., 2025)
- dados/historico/ministros/<ano>.json ..... os ministros de cada governo do mandato federal que começou em <ano>
                                              (1995 a 2019), a partir de dados/manual/ministros-anteriores.json

A mesma régua para todos os anos e cargos:
- Eleito = situação do TSE depois da totalização começando com "ELEITO" ("MÉDIA", em 1998, é o nome antigo de
  "ELEITO POR MÉDIA"). Quem aparece como eleito mas tem a candidatura marcada como renúncia, falecimento ou registro
  negado fica de fora, e a lista avisa (acontece nos arquivos de 1998 e de 2000, quando um candidato foi trocado por
  outro com o mesmo número e os dois ficaram marcados como eleitos).
- Cargos de um só eleito (presidente, governador, prefeito): quem venceu o último turno da eleição ordinária.
- Vice: o da mesma chapa, ligado pelo próprio TSE (mesmo número, na mesma eleição e no mesmo lugar). Em 1994, 1996 e
  1998 o TSE não liga o vice à chapa (ou não publica o nome): o vice fica sem nome, com aviso.
- Partido: o da eleição (partido que mudou de nome depois aparece com o nome da época).
- Eleições suplementares (quando uma eleição é anulada e se vota de novo) não entram. Não há votos (só quem foi eleito).
- Senado: em cada legislatura, os eleitos nas duas eleições que a formam (ex.: 2019 a 2022 = eleitos em 2018 + 2014).
  Os eleitos em 1990 (parte do Senado de 1995 a 1998) vêm do arquivo de resultados de 1990 do TSE
  (votacao_candidato_uf_1990); no Amapá e em Roraima, que elegeram 3 senadores em 1990, a lista da 50ª legislatura dos
  dados abertos do Senado mostra qual deles continuou no Senado depois de 1995.
- Presidente e vice: o que o TSE não tem (o vice de 1994 e de 1998 e o 2º turno de 2006) e o que mudou durante o
  mandato (2016) vêm de dados/manual/presidentes.json, sempre com fonte oficial.
- Ministros (não são eleitos, então não vêm do TSE): dados/manual/ministros-anteriores.json, transcrito uma vez das
  listas "Ministérios" e "Órgãos da Presidência" da Biblioteca da Presidência da República (FHC, Lula e Dilma) e dos
  decretos de nomeação e exoneração do Diário Oficial da União (órgãos da Presidência no governo Dilma, o que falta nas
  listas, Temer e Bolsonaro), cada pessoa com a sua fonte. Em 2015 a 2018 há duas partes: Dilma Rousseff (até
  12/5/2016) e Michel Temer (desde 12/5/2016). O cartão avisa quando a fonte não traz ninguém por mais de 15 dias.
  Nomeação tornada sem efeito por outro decreto ("semEfeito") não conta como período de ninguém: fica na pasta, com a
  data dos dois decretos e as duas fontes.
- Municípios: o código do TSE (SG_UE) é ligado ao código do IBGE pelo mesmo casamento de scripts/ibge.py
  (casar_tse e EXCECOES_TSE). Cidade que ainda não existia numa eleição aparece em "depois" (ano da 1ª eleição dela).

Fontes: TSE, Portal de Dados Abertos (consulta_cand_<ano>.zip e votacao_candidato_uf_1990.zip); Senado Federal,
Dados Abertos (senadores da 50ª legislatura); IBGE (códigos dos municípios); dados/manual/presidentes.json.

Uso (à mão: o passado não muda, então não precisa rodar todo dia):
    python scripts/historico.py              # gera tudo (baixa o que faltar para .cache/tse/)
    python scripts/historico.py --so 2018    # só uma eleição (para conferir)
    python scripts/historico.py --ministros  # só os ministros (lê o arquivo manual; não baixa nada)
Depois do resultado final de 2026 (sem 2º turno pendente), rode de novo: o mandato que começa em 2027 entra sozinho.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import *  # noqa: E402
import ibge  # noqa: E402
import mandatos  # noqa: E402  (datas de posse: a regra fica num lugar só)
from tse import cpf_valido, data_br, data_en, genero, ler_csv, nome_tse, resultado_2turno  # noqa: E402

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
PORTAL = "https://dadosabertos.tse.jus.br/dataset/"
SENADO_API = "https://legis.senado.leg.br/dadosabertos/"
HIST = DADOS / "historico"
CACHE_TSE = CACHE / "tse"
MANUAL_PRES = DADOS / "manual" / "presidentes.json"
MANUAL_MIN = DADOS / "manual" / "ministros-anteriores.json"

GERAIS = [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]
MUNICIPAIS = [1996, 2000, 2004, 2008, 2012, 2016, 2020, 2024]
IDADE_H = {2026: 20}  # horas até baixar de novo; os outros anos já fecharam (baixa uma vez só)
VERSAO_CACHE = 3       # muda quando o resumo guardado em .cache/tse/historico_<ano>.json muda de formato
# Na eleição de 1994 o TSE ainda não ligava o vice à chapa (o número do vice é outro e não há coligação), em 1996
# o arquivo de vice-prefeitos tem poucas linhas e números próprios, e em 1998 o nome dos vices não foi publicado
# (em 2000 também não: as linhas de vice vêm sem nome e ficam de fora sozinhas).
SEM_VICE_LIGADO = {1994, 1996, 1998}
NOMES_CORTADOS = {1990, 1994, 1996}  # anos em que o nome na urna é o nome completo cortado em 30 letras

CARGOS_GERAIS = {"PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL",
                 "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}
CARGOS_MUNICIPAIS = {"PREFEITO", "VICE-PREFEITO", "VEREADOR"}
EXECUTIVOS = {"PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "PREFEITO", "VICE-PREFEITO"}
UFS = sorted(ibge.UF_CODIGO.values())
F_CF = fonte("Planalto", "Constituição Federal, arts. 27, 28, 29, 44, 45, 46 e 82 (mandatos e posse)",
             "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", "1988-10-05")
F_EC111 = fonte("Planalto", "Emenda Constitucional nº 111/2021 (posse do presidente em 5 de janeiro e dos governadores "
                "em 6 de janeiro, a partir de 2027)", "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm",
                "2021-09-28")


# ---------------------------------------------------------------- datas dos mandatos (Constituição; scripts/mandatos.py)
def posse_presidente(eleicao: int) -> str:
    return mandatos.posse("presidente", eleicao)  # 1º de janeiro; 5 de janeiro a partir dos eleitos em 2026 (EC 111/2021)


def posse_governador(eleicao: int) -> str:
    return mandatos.posse("governador", eleicao)  # 1º de janeiro; 6 de janeiro a partir dos eleitos em 2026 (EC 111/2021)


def legislatura(eleicao: int) -> int:
    return 50 + (eleicao - 1994) // 4


def rotulos(inicio: int) -> tuple[str, str]:
    return f"{inicio} a {inicio + 3}", f"{inicio}–{inicio + 3}"


# nos arquivos mais antigos do TSE os nomes vêm sem acento e cortados em 30 letras
AVISO_NOMES = {
    1994: ("Nos arquivos mais antigos do TSE (1990 e 1994), muitos nomes aparecem sem acento, e os mais longos foram "
           "cortados (marcados com “…”).",
           "In the oldest TSE files (1990 and 1994), many names appear without accents, and the longest ones were cut "
           "short (marked with “…”)."),
    1996: ("Nos arquivos do TSE de 1996, os nomes aparecem sem acento, e os mais longos foram cortados (marcados com “…”).",
           "In the TSE files from 1996, names appear without accents, and the longest ones were cut short (marked with “…”)."),
}


# ---------------------------------------------------------------- textos e fontes
def fonte_candidatos(ano: int, data: str | None) -> dict:
    return fonte("TSE", f"Dados Abertos: candidaturas de {ano} (situação depois da totalização)",
                 f"{PORTAL}candidatos-{ano}", data)


def eleito(sit: str | None) -> bool:
    s = (sit or "").upper()
    return s.startswith("ELEITO") or s == "MÉDIA"


def nome_exibido(s: str | None, cortado_em_30: bool = False) -> str | None:
    """Nome do TSE em letra normal. Nos arquivos de 1990, 1994 e 1996 o campo do nome na urna traz o nome completo cortado
    em 30 letras: aí o nome com 30 letras ganha "…" (nos outros anos, 30 letras é o limite do nome na urna, não um corte)."""
    s = limpa(s)
    if not s or s.startswith("#"):
        return None
    n = nome_tse(s)
    return n + "…" if cortado_em_30 and len(s) == 30 and n else n


def turno_txt(turno: int, g: str | None) -> tuple[str, str]:
    a = "a" if g == "F" else "o"
    return (f"Eleit{a} no {turno}º turno", "Elected in the first round" if turno == 1 else "Elected in the runoff")


# ---------------------------------------------------------------- leitura (com resumo guardado em .cache/tse)
def zip_cand(ano: int) -> Path:
    nome = f"consulta_cand_{ano}.zip"
    return baixar_arquivo(f"{CDN}consulta_cand/{nome}", f"tse/{nome}", max_idade_h=IDADE_H.get(ano))


def linhas(ano: int) -> dict:
    """{"data": geração do arquivo, "linhas": [...]} só com o que interessa: todas as candidaturas de cargos executivos
    (para achar o vice da chapa) e as candidaturas eleitas dos outros cargos. Cada linha leva o ano ("ano")."""
    d = _linhas(ano)
    for c in d["linhas"]:
        c["ano"] = ano
    if ano >= 2026:
        completar_2turno(d["linhas"], ano)
    return d


def completar_2turno(rows: list[dict], ano: int) -> None:
    """Os dados abertos de candidaturas levam alguns dias para trazer a situação depois do 2º turno (até lá, "#NULO"):
    usa a totalização final do sistema de resultados do TSE, como o scripts/tse.py, e guarda a fonte na linha
    ("fonte2t"), para ela aparecer junto na ficha de quem venceu."""
    disputas = collections.defaultdict(list)
    for c in rows:
        if (c["turno"] == 2 and c["ord"] and c["sit"] not in ("ELEITO", "NÃO ELEITO") and c["dt"] and c["dt"] <= hoje()
                and c["cargo"] in EXECUTIVOS):
            disputas[(c["el"], c["uf"], c["cargo"].replace("VICE-", ""))].append(c)
    for (el, uf, cargo), cs in sorted(disputas.items()):
        r = resultado_2turno(ano, el, uf, cargo)
        if not r:
            continue
        sit, f = r
        for c in cs:
            if sit.get(c["sq"]):
                c["sit"], c["fonte2t"] = sit[c["sq"]], f


def fontes_com_2turno(fts: list, *cs) -> list:
    """As fontes da ficha mais o resultado do 2º turno do sistema de resultados do TSE, se veio de lá."""
    return fts + [c["fonte2t"] for c in cs if c and c.get("fonte2t")]


def _linhas(ano: int) -> dict:
    z = zip_cand(ano)
    destino = CACHE_TSE / f"historico_{ano}.json"
    if destino.exists() and destino.stat().st_mtime >= z.stat().st_mtime:
        with open(destino, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("versao") == VERSAO_CACHE:
            return d
    t = time.time()
    cargos = CARGOS_MUNICIPAIS if ano in MUNICIPAIS else CARGOS_GERAIS
    out, data = [], None
    for r in ler_csv(z):
        cargo = (r["DS_CARGO"] or "").upper().strip()
        if cargo not in cargos:
            continue
        sit = (r["DS_SIT_TOT_TURNO"] or "").upper().strip()
        if cargo not in EXECUTIVOS and not eleito(sit):
            continue
        data = data or data_iso(r["DT_GERACAO"])
        out.append({
            "el": r["CD_ELEICAO"], "ord": "ORDIN" in sem_acento(r["NM_TIPO_ELEICAO"] or "").upper(),
            "turno": int(r["NR_TURNO"] or 1), "dt": data_iso(r["DT_ELEICAO"]), "uf": r["SG_UF"], "ue": r["SG_UE"],
            "nm_ue": limpa(r["NM_UE"]), "cargo": cargo, "sq": r["SQ_CANDIDATO"], "num": r["NR_CANDIDATO"],
            "nome": limpa(r["NM_CANDIDATO"]), "urna": limpa(r["NM_URNA_CANDIDATO"]), "partido": limpa(r["SG_PARTIDO"]),
            "g": genero(r.get("DS_GENERO")), "sit": sit, "sitc": (r.get("DS_SITUACAO_CANDIDATURA") or "").upper().strip(),
            "cpf": cpf_valido(r.get("NR_CPF_CANDIDATO")), "nasc": data_iso(r.get("DT_NASCIMENTO")),
        })
    d = {"versao": VERSAO_CACHE, "ano": ano, "data": data, "linhas": out}
    tmp = destino.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, destino)
    log(f"  {ano}: {len(out)} linhas guardadas em {destino.name} ({time.time() - t:.0f}s)")
    return d


# ---------------------------------------------------------------- quem foi eleito
def candidatura_caiu(sitc: str | None) -> bool:
    """A candidatura não valeu na eleição (renúncia, morte, registro negado ou cancelado). Nos arquivos de 1998 e 2000,
    quando um candidato foi trocado por outro com o mesmo número, os dois aparecem como eleitos: vale o que ficou."""
    s = sem_acento(sitc or "").upper()
    return any(x in s for x in ("RENUNCIA", "FALECID", "INDEFERID", "CANCELA", "CASSA", "NAO CONHECIMENTO"))


def eleitos(rows: list[dict], cargos: set, excluidos: list | None = None) -> list[dict]:
    """Eleitos da eleição ordinária para estes cargos (sem repetir a pessoa). Quem tem a candidatura marcada como
    renúncia, falecimento ou registro negado (ou está sem nome) vai para `excluidos`."""
    vistos, out = set(), []
    for c in sorted(rows, key=lambda c: (c["turno"], c["sq"])):
        chave = (c["ue"], c["cargo"], c["sq"])  # nos arquivos antigos o SQ_CANDIDATO só é único dentro do estado
        if c["cargo"] not in cargos or not c["ord"] or not eleito(c["sit"]) or chave in vistos:
            continue
        vistos.add(chave)
        if candidatura_caiu(c["sitc"]) or not nome_exibido(c["urna"] or c["nome"]):
            if excluidos is not None:
                excluidos.append(c)
            continue
        out.append(c)
    return out


def vencedor(rows: list[dict], cargo: str) -> dict | None:
    """Quem venceu o último turno da eleição ordinária (presidente, governador, prefeito)."""
    el = eleitos(rows, {cargo})
    if not el:
        return None
    t = max(c["turno"] for c in el)
    ult = [c for c in el if c["turno"] == t]
    if len({c["sq"] for c in ult}) > 1:
        log(f"  [aviso] mais de um eleito para {cargo} em {ult[0]['nm_ue']} ({ult[0]['uf']}), {ult[0]['dt']}: ninguém escolhido")
        return None
    return ult[0]


def vice_da_chapa(rows: list[dict], cargo_vice: str, tit: dict, ano: int) -> dict | None:
    """O vice que o TSE liga à chapa vencedora: mesmo número, na mesma eleição e no mesmo lugar."""
    if ano in SEM_VICE_LIGADO:
        return None
    for mesmo_turno in (True, False):
        cs = [c for c in rows if c["cargo"] == cargo_vice and c["ue"] == tit["ue"] and c["num"] == tit["num"] and c["ord"]
              and ((c["el"] == tit["el"]) if mesmo_turno else c["turno"] == 1)]
        cs = [c for c in cs if nome_exibido(c["urna"] or c["nome"])]
        if not cs:
            continue
        por_sq = {c["sq"]: c for c in cs}
        if len(por_sq) == 1:
            return cs[0]
        # chapa com vice trocado: vale o que o TSE marca como eleito; senão, o que continuou com o registro válido
        for filtro in (lambda c: eleito(c["sit"]), lambda c: c["sitc"] in ("APTO", "DEFERIDO", "DEFERIDO COM RECURSO")):
            f = {c["sq"]: c for c in por_sq.values() if filtro(c)}
            if len(f) == 1:
                return next(iter(f.values()))
        log(f"  [aviso] vice de {tit['nm_ue']} ({tit['uf']}) {ano}: {len(por_sq)} possíveis, nenhum escolhido")
        return None
    return None


def pessoa(c: dict, extra: dict | None = None) -> dict:
    corte = c.get("ano") in NOMES_CORTADOS
    d = {"nome": nome_exibido(c["urna"], corte) or nome_exibido(c["nome"], corte), "nomeCivil": nome_exibido(c["nome"], corte),
         "partido": c["partido"], "genero": c["g"]}
    # nome na urna cortado em 30 letras ("…"), mas o nome completo começa igual e não foi cortado: vale o completo
    if d["nome"] and d["nome"].endswith("…") and d["nomeCivil"] and not d["nomeCivil"].endswith("…") \
            and chave_nome(d["nomeCivil"]).startswith(chave_nome(d["nome"][:-1])):
        d["nome"] = d["nomeCivil"]
    if d["nomeCivil"] == d["nome"]:
        d.pop("nomeCivil")
    if extra:
        d.update(extra)
    return {k: v for k, v in d.items() if v is not None or k in ("partido", "genero")}


def executivo(c: dict | None, vice: bool = False, titular: dict | None = None) -> dict | None:
    if not c:
        return None
    if vice:
        g = c["g"]
        a = "a" if g == "F" else "o"
        nt = pessoa(titular)["nome"] if titular else None
        sit = (f"Eleit{a} na chapa de {nt}" if nt else f"Eleit{a} na mesma chapa",
               f"Elected on {nt}'s ticket" if nt else "Elected on the same ticket")
    else:
        sit = turno_txt(c["turno"], c["g"])
    return pessoa(c, {"situacao": sit[0], "situacao_en": sit[1]})


def membro(c: dict, **extra) -> dict:
    return pessoa(c, extra or None)


def ordem(lista: list[dict]) -> list[dict]:
    return sorted(lista, key=lambda m: (chave_nome(m.get("nome") or ""), m.get("uf") or "", m.get("partido") or ""))


def aviso_excluidos(n: int) -> tuple[str, str] | None:
    if not n:
        return None
    if n == 1:
        return ("Nos dados do TSE, 1 pessoa aparece como eleita, mas com a candidatura marcada como renúncia, falecimento "
                "ou registro negado (ou sem nome): ela não entra na lista.",
                "In the TSE data, 1 person appears as elected, but with the candidacy marked as withdrawn, deceased or "
                "rejected (or with no name): this person is not on the list.")
    return (f"Nos dados do TSE, {n} pessoas aparecem como eleitas, mas com a candidatura marcada como renúncia, "
            "falecimento ou registro negado (ou sem nome): elas não entram na lista.",
            f"In the TSE data, {n} people appear as elected, but with the candidacy marked as withdrawn, deceased or "
            "rejected (or with no name): they are not on the list.")


def junta_avisos(*avisos) -> dict:
    """[(pt, en), None, ...] -> {"aviso": "...", "aviso_en": "..."}"""
    a = [x for x in avisos if x]
    return {"aviso": " ".join(x[0] for x in a), "aviso_en": " ".join(x[1] for x in a)} if a else {}


def aviso_lista(ano: int, quem: str, quem_en: str) -> tuple[str, str]:
    return (f"Lista de quem foi eleito em {ano} ({quem}), segundo o TSE, com o partido da eleição. Durante o mandato, "
            "algumas pessoas podem ter saído (renúncia, cassação, licença, morte) e suplentes podem ter assumido; "
            "outras podem ter trocado de partido.",
            f"List of the people elected in {ano} ({quem_en}), according to the TSE (Superior Electoral Court), with the "
            "party they had in the election. During the term, some may have left (resignation, removal from office, "
            "leave, death) and alternates may have taken their seats; others may have changed parties.")


def aviso_cadeiras(n: int, cadeiras: int | None) -> tuple[str, str] | None:
    if not cadeiras or n >= cadeiras:
        return None
    return (f"O TSE lista {n} eleitos, mas a Casa tinha {cadeiras} cadeiras: faltam nomes nos dados abertos.",
            f"The TSE lists {n} elected people, but the house had {cadeiras} seats: some names are missing from the open data.")


AVISO_SUPLEMENTAR = ("Eleições suplementares (quando uma eleição é anulada e se vota de novo) não entram aqui.",
                     "Special elections (held when an election is annulled and people vote again) are not included here.")


def suplementares(rows: list[dict], cargos: set, ue: str | None = None) -> list[str]:
    """Datas (1º turno) das eleições suplementares para estes cargos que aparecem nos dados do TSE."""
    return sorted({c["dt"] for c in rows if not c["ord"] and c["cargo"] in cargos and c["dt"] and c["turno"] == 1
                   and (ue is None or c["ue"] == ue)})


# ---------------------------------------------------------------- presidente e vice: o que o TSE não tem
def manual_presidentes() -> dict:
    return (ler_json(MANUAL_PRES) or {}).get("mandatos") or {}


def chapa_manual(rows: list[dict], m: dict) -> tuple[dict | None, int | None]:
    """Quando o TSE não marca o vencedor (2º turno de 2006), o arquivo manual diz o número da chapa vencedora."""
    v = m.get("vencedor") or {}
    if not v.get("numero"):
        return None, None
    cs = [c for c in rows if c["cargo"] == "PRESIDENTE" and c["ord"] and c["num"] == str(v["numero"])]
    cs.sort(key=lambda c: -c["turno"])
    return (cs[0] if cs else None), v.get("turno")


def executivo_federal(ano: int, rows: list[dict], data: str, m: dict) -> dict:
    fts = [fonte_candidatos(ano, data)]
    pres = vencedor(rows, "PRESIDENTE")
    turno_manual = None
    if not pres:
        pres, turno_manual = chapa_manual(rows, m)
    if pres is None and not (m.get("presidente") or {}).get("nome"):
        raise RuntimeError(f"{ano}: presidente eleito não encontrado no TSE nem em {MANUAL_PRES.name}")
    out = {}
    if pres:
        p = executivo(pres)
        if turno_manual:
            p["situacao"], p["situacao_en"] = turno_txt(turno_manual, pres["g"])
        p["fontes"] = fontes_com_2turno(fts, pres) + (m.get("fontes") or [] if turno_manual else [])
        out["presidente"] = p
    vice = vice_da_chapa(rows, "VICE-PRESIDENTE", pres, ano) if pres else None
    if vice:
        out["vice"] = dict(executivo(vice, True, pres), fontes=fontes_com_2turno(fts, vice))
    for papel in ("presidente", "vice"):
        mp = m.get(papel)
        if mp and mp.get("nome"):
            # pesquisa à mão (com fonte oficial) para o que o TSE não liga ou não publica
            out[papel] = {k: mp.get(k) for k in ("nome", "nomeCivil", "partido", "genero", "situacao", "situacao_en", "fontes")
                          if mp.get(k) is not None}
    for k in ("mudancas", "nota", "nota_en"):
        if m.get(k):
            out[k] = m[k]
    return out


# ---------------------------------------------------------------- senadores eleitos em 1990 (parte do Senado de 1995 a 1998)
def senadores_1990() -> tuple[list[dict], list[dict]]:
    """Os 27 senadores eleitos em 1990 que ainda estavam no mandato em 1995-1998 + as fontes."""
    url = f"{CDN}votacao_candidato_uf/votacao_candidato_uf_1990.zip"
    z = baixar_arquivo(url, "tse/votacao_candidato_uf_1990.zip", max_idade_h=None)
    rows, data = [], None
    with zipfile.ZipFile(z) as zz:
        for n in zz.namelist():
            if not n.lower().endswith(".txt"):
                continue
            with zz.open(n) as f:
                for p in csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                    # leiaute antigo, sem cabeçalho: 5 UF, 8 número, 10 nome, 11 nome na urna, 12 cargo, 18 situação, 20 partido, 25 votos
                    if len(p) < 26 or p[12].strip().upper() != "SENADOR" or not eleito(p[18]):
                        continue
                    if not data:
                        d, mth, y = (p[0].split("/") + ["", "", ""])[:3]
                        data = f"{y}-{int(mth):02d}-{int(d):02d}" if y and mth and d else None
                    rows.append({"uf": p[5], "nome": limpa(p[10]), "urna": limpa(p[11]), "partido": limpa(p[20]),
                                 "votos": int(p[25] or 0)})
    # quem dos eleitos de 1990 ficou no Senado depois de 1º/2/1995 (Amapá e Roraima elegeram 3 em 1990)
    leg = baixar_json(f"{SENADO_API}senador/lista/legislatura/50.json", cache="senado/historico/legislatura-50.json",
                      max_idade_h=None)
    ps = leg["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
    nomes, sexo, continuou = {}, {}, set()
    for p in ps:
        ident = p["IdentificacaoParlamentar"]
        sexo[ident["CodigoParlamentar"]] = genero(ident.get("SexoParlamentar"))
        ms = p["Mandatos"]["Mandato"]
        for mand in ms if isinstance(ms, list) else [ms]:
            if mand["PrimeiraLegislaturaDoMandato"]["NumeroLegislatura"] != "49":
                continue
            if mand.get("DescricaoParticipacao") == "Titular":
                nomes[ident["CodigoParlamentar"]] = (mand["UfParlamentar"], ident.get("NomeCompletoParlamentar") or ident.get("NomeParlamentar"))
            tit = ident["CodigoParlamentar"] if mand.get("DescricaoParticipacao") == "Titular" else (mand.get("Titular") or {}).get("CodigoParlamentar")
            ex = (mand.get("Exercicios") or {}).get("Exercicio") or []
            ex = ex if isinstance(ex, list) else [ex]
            if tit and any((e.get("DataFim") or "9999") > "1995-02-01" for e in ex):
                continuou.add(tit)

    def tokens(s):
        return {t for t in chave_nome(s).split() if t not in ("DE", "DA", "DO", "DAS", "DOS", "E")}

    def codigo(r):
        """Senador titular de 1991 da mesma UF com o mesmo nome (sem contar "de", "da"...; um nome pode ter uma palavra a mais)."""
        alvo = tokens(r["nome"])
        achou = [cod for cod, (uf, nome) in nomes.items() if uf == r["uf"] and len(alvo & tokens(nome)) >= 2
                 and (alvo <= tokens(nome) or tokens(nome) <= alvo)]
        return achou[0] if len(achou) == 1 else None

    por_uf = collections.defaultdict(list)
    for r in rows:
        r["cod"] = codigo(r)
        por_uf[r["uf"]].append(r)
    out = []
    for uf, rs in sorted(por_uf.items()):
        if len(rs) > 1:
            fic = [r for r in rs if r["cod"] in continuou]
            if len(fic) != 1:
                fic = sorted(rs, key=lambda r: -r["votos"])[:1]
                log(f"  [aviso] senadores de 1990 em {uf}: o Senado não mostra quem continuou; fica o mais votado ({fic[0]['nome']})")
            rs = fic
        r = rs[0]
        out.append({"nome": nome_exibido(r["urna"], True) or nome_exibido(r["nome"], True), "partido": r["partido"], "uf": uf,
                    "genero": sexo.get(r["cod"]), "eleito": 1990})
        if not r["cod"]:
            log(f"  [aviso] senador de 1990 sem par no Senado (sem gênero): {r['nome']} ({uf})")
    if len(out) != 27:
        log(f"  [aviso] senadores de 1990: {len(out)} (esperado 27)")
    fts = [fonte("TSE", "Dados Abertos: resultados de 1990 (votação por candidato e estado)", f"{PORTAL}resultados-1990", data),
           fonte("Senado Federal", "Dados Abertos: senadores da 50ª legislatura (1995 a 1999)",
                 f"{SENADO_API}senador/lista/legislatura/50", hoje())]
    return out, fts


# ---------------------------------------------------------------- eleições gerais: Brasil e estados
def cadeiras_estaduais(fed: int, uf: str) -> int:
    """Constituição, art. 27 (e art. 32, § 3º, para o DF): o triplo dos deputados federais até 36; depois, +1 por deputado acima de 12."""
    if uf == "DF":
        return 24
    return 3 * fed if fed <= 12 else 36 + fed - 12


def resultado_final(rows: list[dict]) -> bool:
    """A eleição geral já tem o resultado fechado (presidente, 27 governadores e deputados de todos os estados)?"""
    if not vencedor(rows, "PRESIDENTE"):
        return False
    ufs_gov = {c["uf"] for c in eleitos(rows, {"GOVERNADOR"})}
    ufs_dep = {c["uf"] for c in eleitos(rows, {"DEPUTADO FEDERAL"})}
    pend = [c for c in rows if c["ord"] and c["sit"] == "2º TURNO"]
    pend = [c for c in pend if not any(x["ue"] == c["ue"] and x["cargo"] == c["cargo"] and x["turno"] == 2 and eleito(x["sit"])
                                       for x in rows)]
    return len(ufs_gov) == 27 and len(ufs_dep) == 27 and not pend


def gerar_geral(ano: int, base: dict, ant: dict | None, man: dict) -> tuple[dict, dict]:
    """(arquivo do Brasil, {UF: mandato do estado}) do mandato que começa em ano + 1."""
    rows, data = base["linhas"], base["data"]
    inicio = ano + 1
    m = man.get(str(inicio)) or {}
    fts = [fonte_candidatos(ano, data)]
    # Câmara
    exc = []
    deps = eleitos(rows, {"DEPUTADO FEDERAL"}, exc)
    por_uf_dep = collections.Counter(c["uf"] for c in deps)
    camara = {"total": len(deps), "membros": ordem([membro(c, uf=c["uf"]) for c in deps]), "fonte": fts[0]}
    camara.update(junta_avisos(aviso_lista(ano, "deputados federais", "federal deputies"), aviso_excluidos(len(exc)),
                               aviso_cadeiras(len(deps), 513)))
    # Senado: eleitos nesta eleição + na anterior
    sen = [membro(c, uf=c["uf"], eleito=ano) for c in eleitos(rows, {"SENADOR"})]
    if ant is not None:
        sen_ant = [membro(c, uf=c["uf"], eleito=ano - 4) for c in eleitos(ant["linhas"], {"SENADOR"})]
        fts_sen = fts + [fonte_candidatos(ano - 4, ant["data"])]
    else:
        sen_ant, f90 = senadores_1990()
        fts_sen = fts + f90
    senado = {"total": len(sen) + len(sen_ant), "membros": ordem(sen + sen_ant), "fontes": fts_sen}
    # vaga decidida numa eleição suplementar (ex.: Mato Grosso, 2020): diz onde e quando, em vez de "faltam nomes"
    sup = sorted({(c["uf"], c["dt"]) for b in (rows, ant["linhas"] if ant else []) for c in b
                  if not c["ord"] and c["cargo"] == "SENADOR" and eleito(c["sit"])})
    if sup:
        nomes_uf = ibge.estados()
        senado["suplementar"] = [{"uf": u, "data": d,
                                  "txt": f"Em {nomes_uf[u]} ({u}), uma vaga foi decidida numa eleição suplementar em {data_br(d)}, que não entra aqui.",
                                  "txt_en": f"In {nomes_uf[u]} ({u}), one seat was decided in a special election on {data_en(d)}, which is not included here."}
                                 for u, d in sup]
    senado.update(junta_avisos(
        (f"Senadores eleitos em {ano} e em {ano - 4}, segundo o TSE, com o partido da eleição. O mandato de senador dura "
         "8 anos, por isso o Senado de cada legislatura junta eleitos de duas eleições. Durante o mandato, alguns podem "
         "ter saído e suplentes podem ter assumido.",
         f"Senators elected in {ano} and in {ano - 4}, according to the TSE (Superior Electoral Court), with the party "
         "they had in the election. A senator's term lasts 8 years, so the Senate of each legislature brings together "
         "people elected in two elections. During the term, some may have left and alternates may have taken their seats."),
        None if sup else aviso_cadeiras(len(sen) + len(sen_ant), 81)))
    brasil = {"id": str(inicio), "eleicao": ano, "inicio": posse_presidente(ano), "fim": posse_presidente(ano + 4),
              "legislatura": legislatura(ano)}
    brasil.update(executivo_federal(ano, rows, data, m))
    brasil.update({"senado": senado, "camara": camara})
    # estados
    estados = {}
    for uf in UFS:
        rs = [c for c in rows if c["uf"] == uf]
        gov = vencedor(rs, "GOVERNADOR")
        vice = vice_da_chapa(rs, "VICE-GOVERNADOR", gov, ano) if gov else None
        exc = []
        dest = eleitos(rs, {"DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}, exc)
        cad = cadeiras_estaduais(por_uf_dep.get(uf, 0), uf)
        quem = ("deputados distritais", "district deputies") if uf == "DF" else ("deputados estaduais", "state deputies")
        e = {"eleicao": ano,
             "governador": dict(executivo(gov), fontes=fontes_com_2turno(fts, gov)) if gov else None,
             "vice": dict(executivo(vice, True, gov), fontes=fontes_com_2turno(fts, vice)) if vice else None,
             "deputados": dict({"total": len(dest), "cadeiras": cad, "membros": ordem([membro(c) for c in dest]), "fonte": fts[0]},
                               **junta_avisos(aviso_lista(ano, *quem), aviso_excluidos(len(exc)), aviso_cadeiras(len(dest), cad)))}
        if gov and not vice:
            e.update({"avisoVice": AVISO_VICE[ano][0] if ano in AVISO_VICE else "Nos dados do TSE, o vice desta chapa não aparece.",
                      "avisoVice_en": AVISO_VICE[ano][1] if ano in AVISO_VICE else "In the TSE data, the vice of this ticket does not appear."})
        sup = suplementares(rs, {"GOVERNADOR"})
        if sup:
            e["suplementar"] = sup
        if not gov:
            log(f"  [aviso] {ano} {uf}: sem governador eleito no TSE")
        estados[uf] = e
    return brasil, estados


AVISO_VICE = {
    1994: ("Nos dados de 1994, o TSE não liga o vice à chapa de quem foi eleito, por isso o vice não aparece aqui.",
           "In the 1994 data, the TSE does not link the vice to the elected ticket, so the vice is not shown here."),
    1996: ("Nos dados de 1996, o TSE não liga o vice à chapa de quem foi eleito, por isso o vice não aparece aqui.",
           "In the 1996 data, the TSE does not link the vice to the elected ticket, so the vice is not shown here."),
    1998: ("Nos dados de 1998, o TSE não publica o nome dos vices, por isso o vice não aparece aqui.",
           "In the 1998 data, the TSE does not publish the names of the vices, so the vice is not shown here."),
    2000: ("Nos dados de 2000, o TSE não publica o nome dos vices, por isso o vice não aparece aqui.",
           "In the 2000 data, the TSE does not publish the names of the vices, so the vice is not shown here."),
}
# Nos dados de 2012, o vice-prefeito aparece com o partido do prefeito (o da chapa), mesmo quando era de outro partido
# (ex.: Rio de Janeiro, Belo Horizonte, Curitiba, São Paulo, Salvador). Nos outros anos, cada vice tem o próprio partido.
VICE_COM_PARTIDO_DA_CHAPA = {2012}
AVISO_PARTIDO_VICE = ("Nos dados de 2012, o TSE registra o vice com o mesmo partido do prefeito (o partido da chapa), mesmo "
                      "quando o vice era de outro partido. Por isso o partido do vice não aparece aqui.",
                      "In the 2012 data, the TSE records the vice mayor with the mayor's party (the ticket's party), even "
                      "when the vice mayor belonged to another party. That is why the vice mayor's party is not shown here.")


# ---------------------------------------------------------------- eleições municipais: cidades
def vagas_municipais(ano: int) -> dict:
    """{(SG_UE, cargo): cadeiras} da eleição ordinária (TSE, consulta_vagas)."""
    z = baixar_arquivo(f"{CDN}consulta_vagas/consulta_vagas_{ano}.zip", f"tse/consulta_vagas_{ano}.zip", max_idade_h=IDADE_H.get(ano))
    v = collections.Counter()
    for r in ler_csv(z):
        if "ORDIN" in sem_acento(r.get("NM_TIPO_ELEICAO") or "").upper():
            v[(r["SG_UE"], (r["DS_CARGO"] or "").upper())] += int(r.get("QT_VAGA") or r.get("QT_VAGAS") or 0)
    return v


def mapa_municipios(ues_por_ano: dict) -> dict:
    """{SG_UE: código IBGE} para todos os anos. Base: o casamento de 2024 (scripts/ibge.py); para cidades que não
    estão em 2024, o mesmo casamento por nome + UF (e EXCECOES_TSE)."""
    ultimo = max(ues_por_ano)
    out = dict(ibge.casar_tse(ues_por_ano[ultimo]))
    locs = ibge.municipios()
    por_nome = {}
    for cod, mm in locs.items():
        por_nome.setdefault((mm["uf"], chave_nome(mm["nome"])), cod)
    usados = set(out.values())
    faltam = []
    for ano in sorted(ues_por_ano):
        for ue, (uf, nome) in sorted(ues_por_ano[ano].items()):
            if ue in out:
                continue
            cod = ibge.EXCECOES_TSE.get(ue) or por_nome.get((uf, chave_nome(nome)))
            if cod and locs.get(cod, {}).get("uf") == uf and cod not in usados:
                out[ue] = cod
                usados.add(cod)
            else:
                faltam.append(f"{ano} {ue} {nome} ({uf})")
    if faltam:
        log(f"  [aviso] {len(faltam)} códigos do TSE sem município do IBGE hoje (ficam de fora): {faltam[:12]}")
    return out


def cidade(rs: list[dict], ano: int, vagas: dict, nome_ibge: str) -> dict:
    exc = []
    pref = vencedor(rs, "PREFEITO")
    vice = vice_da_chapa(rs, "VICE-PREFEITO", pref, ano) if pref else None
    ver = eleitos(rs, {"VEREADOR"}, exc)
    eleitos(rs, {"PREFEITO"}, exc)
    ver.sort(key=lambda c: (chave_nome(nome_exibido(c["urna"]) or nome_exibido(c["nome"]) or ""), c["sq"]))
    d = {}
    if pref:
        p = pessoa(pref)
        d["p"] = [p["nome"], p.get("nomeCivil"), p["partido"], p["genero"], pref["turno"]]
    if vice:
        v = pessoa(vice)
        # nos dados de 2012 o TSE registra o vice com o partido do prefeito (o da chapa): o partido do vice fica sem informação
        d["v"] = [v["nome"], v.get("nomeCivil"), None if ano in VICE_COM_PARTIDO_DA_CHAPA else v["partido"], v["genero"]]
    d["ver"] = []
    for c in ver:
        v = pessoa(c)
        d["ver"].append([v["nome"], v["partido"], v["genero"]])  # sem o nome civil: o arquivo das cidades de MG passaria de 600 KB
    cad = vagas.get((rs[0]["ue"], "VEREADOR"))
    if cad and len(ver) < cad:
        d["vagas"] = cad
    n_exc = len({c["sq"] for c in exc})
    if n_exc:
        d["exc"] = n_exc
    for chave, cargos in (("supP", {"PREFEITO", "VICE-PREFEITO"}), ("supV", {"VEREADOR"})):
        sup = suplementares(rs, cargos)
        if sup:
            d[chave] = sup
    nm = nome_tse(next((c["nm_ue"] for c in rs if c["ord"]), rs[0]["nm_ue"]))
    if nm and chave_nome(nm) != chave_nome(nome_ibge):
        d["nm"] = nm
    return d


def gerar_municipal(ano: int, base: dict, mapa: dict, primeira: dict) -> dict:
    """{UF: arquivo} do mandato municipal que começa em ano + 1."""
    rows, data = base["linhas"], base["data"]
    vagas = vagas_municipais(ano)
    locs = ibge.municipios()
    por_ue = collections.defaultdict(list)
    for c in rows:
        por_ue[c["ue"]].append(c)
    inicio = ano + 1
    out = {}
    for uf in UFS:
        if uf == "DF":
            continue
        out[uf] = {"uf": uf, "id": str(inicio), "eleicao": ano, "inicio": mandatos.posse("prefeito", ano),
                   "fim": mandatos.posse("prefeito", ano + 4), "fonte": fonte_candidatos(ano, data)}
        out[uf].update(junta_avisos(
            (f"Quem foi eleito em {ano}, segundo o TSE, com o partido da eleição. Durante o mandato, algumas pessoas "
             "podem ter saído (renúncia, cassação, licença, morte) e o vice ou suplentes podem ter assumido.",
             f"The people elected in {ano}, according to the TSE (Superior Electoral Court), with the party they had in "
             "the election. During the term, some may have left (resignation, removal from office, leave, death) and the "
             "vice mayor or alternates may have taken over."), AVISO_SUPLEMENTAR))
        if ano in AVISO_VICE:
            out[uf]["avisoVice"], out[uf]["avisoVice_en"] = AVISO_VICE[ano]
        if ano in VICE_COM_PARTIDO_DA_CHAPA:
            out[uf]["avisoPartidoVice"], out[uf]["avisoPartidoVice_en"] = AVISO_PARTIDO_VICE
        out[uf]["cidades"] = {}
    for ue, rs in por_ue.items():
        cod = mapa.get(ue)
        if not cod or cod not in locs:
            continue
        uf = locs[cod]["uf"]
        out[uf]["cidades"][cod] = cidade(rs, ano, vagas, locs[cod]["nome"])
    for uf, f in out.items():
        f["cidades"] = dict(sorted(f["cidades"].items()))
        depois = {cod: primeira[cod] for cod, mm in locs.items() if mm["uf"] == uf and cod not in f["cidades"]
                  and primeira.get(cod, 0) > ano}
        if depois:
            f["depois"] = dict(sorted(depois.items()))
    return out


# ---------------------------------------------------------------- ministros dos governos anteriores
# dados/manual/ministros-anteriores.json (transcrito uma vez das listas da Biblioteca da Presidência e dos decretos do
# Diário Oficial, cada pessoa com a sua fonte) -> dados/historico/ministros/<mandato>.json, só com o que cabe no mandato
LACUNA_DIAS = 15  # intervalo sem ninguém na fonte que vale um aviso no cartão


def conta_no_periodo(ini: str | None, fim: str | None, j_ini: str, j_fim: str) -> bool:
    """O período [ini, fim] (fim incluído; None = sem data de saída na fonte) conta para a janela [j_ini, j_fim)?
    Quem sai no dia da posse do governo seguinte (ex.: "a 1º/1/1999") não entra no mandato que começa nesse dia."""
    if ini is None:
        return fim is not None and j_ini < fim <= j_fim
    if ini >= j_fim:
        return False
    if fim is None:
        return True
    if ini == fim:
        return ini >= j_ini
    return fim > j_ini


def lacunas(pessoas: list[dict], j_ini: str, j_fim: str) -> list[list[str]]:
    """Intervalos de mais de LACUNA_DIAS dias, dentro da janela, entre um titular/interino e o seguinte."""
    per = sorted((max(a, j_ini), min(b or j_fim, j_fim)) for p in pessoas if p["tipo"] != "substituto"
                 for a, b in p["periodos"] if a and conta_no_periodo(a, b, j_ini, j_fim))
    out, ate = [], None
    for a, b in per:
        if ate and a > ate:
            d = (datetime.date.fromisoformat(a) - datetime.date.fromisoformat(ate)).days
            if d > LACUNA_DIAS:
                out.append([ate, a])
        ate = max(ate or b, b)
    return out


def ministros_anteriores(brasil: list[dict]) -> list[Path]:
    mestre = ler_json(MANUAL_MIN) or {}
    govs = mestre.get("governos") or []
    escritos = []
    for m in brasil:
        t_ini, t_fim = m["inicio"], m["fim"]
        partes = []
        for g in govs:
            j_ini, j_fim = max(t_ini, g["inicio"]), min(t_fim, g["fim"])
            if j_ini >= j_fim:
                continue
            usadas, fontes, pastas = {}, [], []

            def ref(i):
                if i not in usadas:
                    usadas[i] = len(fontes)
                    fontes.append(g["fontes"][i])
                return usadas[i]
            for pa in g["pastas"]:
                pessoas = []
                for p in pa["pessoas"]:
                    per = [x for x in p["periodos"] if conta_no_periodo(x[0], x[1], j_ini, j_fim)]
                    if not per:
                        continue
                    pessoas.append(dict(p, periodos=per, f=[ref(i) for i in p["f"]]))
                # nomeação tornada sem efeito: não é período de ninguém; entra no mandato da data do decreto de nomeação
                anuladas = [dict(s, f=[ref(i) for i in s["f"]]) for s in pa.get("semEfeito") or [] if j_ini <= s["nomeacao"] < j_fim]
                if not any(p["tipo"] != "substituto" for p in pessoas) and not anuladas:
                    continue
                x = {k: pa[k] for k in ("nome", "nome_en", "grupo")}
                x["pessoas"] = pessoas
                if anuladas:
                    x["semEfeito"] = anuladas
                buracos = lacunas(pessoas, j_ini, j_fim)
                if buracos:
                    so_dou = all(fontes[i]["veiculo"].startswith("Diário Oficial") for p in pessoas for i in p["f"])
                    x["lacunas"] = buracos
                    x["lacunaFonte"] = "dou" if so_dou else "lista"
                pastas.append(x)
            if pastas:
                partes.append({"presidente": g["presidente"], "inicio": j_ini, "fim": j_fim, "inicioGoverno": g["inicio"],
                               "fimGoverno": g["fim"], "nota": g["nota"], "nota_en": g["nota_en"], "pastas": pastas, "fontes": fontes})
        if not partes:
            continue
        cam = HIST / "ministros" / f"{m['id']}.json"
        gravar(cam, {"id": m["id"], "inicio": t_ini, "fim": t_fim, "governos": partes, "atualizado": hoje()})
        escritos.append(cam)
        log(f"  ministros {m['id']}: " + "; ".join(f"{p['presidente']} {len(p['pastas'])} pastas, "
                                                    f"{sum(len(x['pessoas']) for x in p['pastas'])} pessoas" for p in partes))
    return escritos


def marca_ministros(indice: dict, feitos: list[Path]) -> None:
    """No índice, "ministros": true nos mandatos federais que têm a lista (a página só busca o arquivo quando ele existe)."""
    ids = {f.stem for f in feitos}
    for m in indice.get("brasil") or []:
        if m["id"] in ids:
            m["ministros"] = True
        else:
            m.pop("ministros", None)


AVISO_INDICE = ("Para os mandatos anteriores, o site mostra quem foi eleito, segundo o TSE, com o partido da eleição. "
                "Durante um mandato, pessoas podem ter saído e vices ou suplentes podem ter assumido. Eleições "
                "suplementares não entram. Os ministros de cada governo vêm das listas da Biblioteca da Presidência e do "
                "Diário Oficial da União.")
AVISO_INDICE_EN = ("For earlier terms, the site shows who was elected, according to the TSE (Superior Electoral Court), with "
                   "the party they had in the election. During a term, people may have left and vices or alternates may "
                   "have taken over. Special elections are not included. The ministers of each government come from the "
                   "Presidency Library lists and from the Official Gazette (Diário Oficial da União).")


# ---------------------------------------------------------------- gravar
def gravar(caminho: Path, obj) -> bool:
    obj = sem_mudar_data(obj, caminho)
    return salvar_json(caminho, obj)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--so", type=int, nargs="*", help="só estas eleições (ex.: --so 2018 2020); não apaga nada")
    ap.add_argument("--ministros", action="store_true",
                    help="só os ministros dos governos anteriores (de dados/manual/ministros-anteriores.json); não baixa nada")
    args = ap.parse_args()
    t0 = time.time()
    if args.ministros:
        indice = ler_json(HIST / "indice.json") or {}
        (HIST / "ministros").mkdir(parents=True, exist_ok=True)
        log("Ministros dos governos anteriores...")
        feitos = ministros_anteriores(indice.get("brasil") or [])
        for f in (HIST / "ministros").glob("*.json"):
            if f not in feitos:
                log(f"  apagando {f.relative_to(RAIZ)} (não foi gerado nesta rodada)")
                f.unlink()
        if indice:
            antes = json.dumps(indice, sort_keys=True, ensure_ascii=False)
            marca_ministros(indice, feitos)
            indice.update({"aviso": AVISO_INDICE, "aviso_en": AVISO_INDICE_EN})
            if json.dumps(indice, sort_keys=True, ensure_ascii=False) != antes:
                gravar(HIST / "indice.json", indice)
        log(f"Pronto em {time.time() - t0:.0f}s")
        return
    so = set(args.so or [])
    for p in (HIST / "brasil", HIST / "estados", HIST / "cidades", HIST / "ministros"):
        p.mkdir(parents=True, exist_ok=True)
    escritos = set()
    indice_ant = ler_json(HIST / "indice.json") or {}
    indice = {"brasil": [], "estados": [], "cidades": []}

    # ---- eleições gerais
    log("Eleições gerais (Brasil e estados)...")
    man = manual_presidentes()
    bases = {}
    estados = collections.defaultdict(dict)
    for ano in GERAIS:
        if so and ano not in so and ano + 4 not in so:
            continue
        bases[ano] = linhas(ano)
    for ano in GERAIS:
        if so and ano not in so:
            continue
        base = bases[ano]
        if ano >= 2026 and not resultado_final(base["linhas"]):
            log(f"  {ano}: o resultado ainda não está fechado no TSE (2º turno ou estados pendentes): o mandato de {ano + 1} fica para depois")
            continue
        ant = bases.get(ano - 4) or (linhas(ano - 4) if ano - 4 in GERAIS else None)
        brasil, est = gerar_geral(ano, base, ant, man)
        inicio = ano + 1
        cam = HIST / "brasil" / f"{inicio}.json"
        brasil["atualizado"] = hoje()
        gravar(cam, brasil)
        escritos.add(cam)
        for uf, e in est.items():
            estados[uf][str(inicio)] = e
        r, r_en = rotulos(inicio)
        nomes_av = dict(zip(("aviso", "aviso_en"), AVISO_NOMES[ano])) if ano in AVISO_NOMES else {}
        indice["brasil"].append(dict({"id": str(inicio), "eleicao": ano, "inicio": posse_presidente(ano), "fim": posse_presidente(ano + 4),
                                      "congresso": {"legislatura": legislatura(ano), "inicio": mandatos.posse("deputado_federal", ano),
                                                    "fim": f"{inicio + 4}-01-31"},
                                      "rotulo": r, "rotulo_en": r_en}, **nomes_av))
        indice["estados"].append(dict({"id": str(inicio), "eleicao": ano, "inicio": posse_governador(ano), "fim": posse_governador(ano + 4),
                                       "rotulo": r, "rotulo_en": r_en}, **nomes_av))
        log(f"  mandato {inicio}: presidente {brasil.get('presidente', {}).get('nome')}, vice {brasil.get('vice', {}).get('nome')}, "
            f"{brasil['senado']['total']} senadores, {brasil['camara']['total']} deputados federais, "
            f"{sum(e['deputados']['total'] for e in est.values())} deputados estaduais/distritais, "
            f"{sum(1 for e in est.values() if e['governador'])} governadores, {sum(1 for e in est.values() if e['vice'])} vices")
    for uf in UFS:
        cam = HIST / "estados" / f"{uf}.json"
        mand = dict(estados.get(uf) or {})
        if so:  # rodada parcial: junta com o que já existia
            mand = dict(((ler_json(cam) or {}).get("mandatos") or {}), **mand)
        if not mand:
            continue
        gravar(cam, {"uf": uf, "mandatos": dict(sorted(mand.items())), "atualizado": hoje()})
        escritos.add(cam)

    # ---- eleições municipais
    log("Eleições municipais (cidades)...")
    mun = {ano: linhas(ano) for ano in MUNICIPAIS}
    ues = {ano: {c["ue"]: (c["uf"], c["nm_ue"]) for c in b["linhas"] if c["ord"]} for ano, b in mun.items()}
    mapa = mapa_municipios(ues)
    primeira = {}  # código IBGE -> ano da 1ª eleição municipal em que a cidade aparece no TSE
    for ano in sorted(ues):
        for cod in {mapa[ue] for ue in ues[ano] if ue in mapa}:
            primeira.setdefault(cod, ano)
    for ano in MUNICIPAIS:
        if so and ano not in so:
            continue
        inicio = ano + 1
        por_uf = gerar_municipal(ano, mun[ano], mapa, primeira)
        for uf, f in por_uf.items():
            f["atualizado"] = hoje()
            cam = HIST / "cidades" / uf / f"{inicio}.json"
            gravar(cam, f)
            escritos.add(cam)
        r, r_en = rotulos(inicio)
        nomes_av = dict(zip(("aviso", "aviso_en"), AVISO_NOMES[ano])) if ano in AVISO_NOMES else {}
        indice["cidades"].append(dict({"id": str(inicio), "eleicao": ano, "inicio": mandatos.posse("prefeito", ano),
                                       "fim": mandatos.posse("prefeito", ano + 4), "rotulo": r, "rotulo_en": r_en}, **nomes_av))
        n_cid = sum(len(f["cidades"]) for f in por_uf.values())
        n_pref = sum(1 for f in por_uf.values() for c in f["cidades"].values() if c.get("p"))
        n_vice = sum(1 for f in por_uf.values() for c in f["cidades"].values() if c.get("v"))
        n_ver = sum(len(c["ver"]) for f in por_uf.values() for c in f["cidades"].values())
        log(f"  mandato {inicio}: {n_cid} cidades, {n_pref} prefeitos, {n_vice} vices, {n_ver} vereadores")

    # ---- índice
    if so:  # rodada parcial: mantém os mandatos que já estavam no índice
        for nivel in indice:
            ids = {x["id"] for x in indice[nivel]}
            indice[nivel] += [x for x in indice_ant.get(nivel) or [] if x["id"] not in ids]
    for nivel in indice:
        indice[nivel].sort(key=lambda x: x["id"], reverse=True)
    # ---- ministros dos governos anteriores (arquivo manual; não baixa nada); o índice marca os mandatos que têm a lista
    log("Ministros dos governos anteriores...")
    feitos = ministros_anteriores(indice["brasil"])
    escritos.update(feitos)
    marca_ministros(indice, feitos)
    indice.update({
        "fontes": [fonte("TSE", "Portal de Dados Abertos: candidaturas de cada eleição desde 1994", f"{PORTAL}?q=candidatos", hoje()),
                   F_CF, F_EC111],
        "aviso": AVISO_INDICE,
        "aviso_en": AVISO_INDICE_EN,
        "atualizado": hoje(),
    })
    cam = HIST / "indice.json"
    gravar(cam, indice)
    escritos.add(cam)

    # ---- arquivos que sobraram de rodadas antigas
    if not so:
        for f in HIST.rglob("*.json"):
            if f not in escritos:
                log(f"  apagando {f.relative_to(RAIZ)} (não foi gerado nesta rodada)")
                f.unlink()
    arqs = list(HIST.rglob("*.json"))
    tam = sum(f.stat().st_size for f in arqs)
    maior = max(arqs, key=lambda f: f.stat().st_size)
    log(f"dados/historico: {len(arqs)} arquivos, {tam / 1e6:.1f} MB; maior: {maior.relative_to(RAIZ)} ({maior.stat().st_size / 1e3:.0f} KB)")
    grandes = [f for f in arqs if f.stat().st_size > 600_000]
    if grandes or tam > 40e6 or len(arqs) > 400:
        log(f"  [aviso] passou do limite combinado (40 MB, 400 arquivos, 600 KB por arquivo): {[str(f.name) for f in grandes]}")
    log(f"Pronto em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
