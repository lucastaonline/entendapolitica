"""Coletor do TSE para o Entenda Política.

Gera a ficha eleitoral de quem está no mandato nos estados e nas cidades, e os dados eleitorais
dos federais (o orquestrador junta estes nos perfis):

- dados/estados/<UF>.json ......... governador(a) e vice, ids dos senadores e deputados federais,
                                    deputados estaduais/distritais eleitos em 2022, capital, nº de municípios
- dados/cidades/<UF>.json .......... lista das cidades (para escolher) com o prefeito
- dados/cidades/<UF>/<IBGE>.json ... prefeito(a), vice e vereadores eleitos em 2024 (+ eleições suplementares)
- dados/busca.json ................. índice da busca (sem vereadores)
- dados/tse/federais.json .......... {id: {"eleicao", "eleicao2026", "bens"}} de deputados federais,
                                    senadores, presidente e vice

Fontes:
- TSE, Portal de Dados Abertos (https://dadosabertos.tse.jus.br/): consulta_cand (candidaturas e situação
  depois da totalização), consulta_cand_complementar (se a candidatura de 2026 foi para a urna),
  votacao_candidato_munzona (votos por município e zona, somados aqui) e bem_candidato (bens).
- TSE, DivulgaCandContas: foto (URL pública), página de cada candidatura, códigos das eleições
  suplementares e o resultado de 2024 das cidades que aparecem sem definição nos dados abertos.
- IBGE (scripts/ibge.py): código e nome oficial dos municípios.
- Câmara e Senado (Dados Abertos): quem está no mandato hoje e CPF/nome civil/nascimento (para casar com o TSE).
- dados/manual/governadores.json (pesquisa à mão): quem governa hoje, se já existir.
- dados/manual/prefeitos.json (opcional, mesmo formato, chave = código IBGE): quem é prefeito(a)/vice hoje
  quando não é quem o TSE mostra (ex.: morte, cassação sem eleição suplementar nos dados).

Casamento de pessoas entre eleições: CPF; se não houver CPF, nome civil + data de nascimento.
Nunca só pelo nome.

Uso:
    python scripts/tse.py              # tudo
    python scripts/tse.py --so-2026    # só atualiza "eleicao2026" (estados e dados/tse/federais.json)
    python scripts/tse.py --renovar    # baixa de novo todos os arquivos do TSE (ignora o cache)
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import *  # noqa: E402
import ibge  # noqa: E402
from mandatos import antes_da_posse, vigente  # noqa: E402

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
PORTAL = "https://dadosabertos.tse.jus.br/dataset/"
DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga"
CACHE_TSE = CACHE / "tse"
SAIDA_TSE = DADOS / "tse"
ESTADOS = DADOS / "estados"
CIDADES = DADOS / "cidades"
MANUAL_GOV = DADOS / "manual" / "governadores.json"
MANUAL_PREF = DADOS / "manual" / "prefeitos.json"

# Horas até baixar de novo. None = baixa uma vez só (eleição encerrada).
IDADE_H = {2018: None, 2022: None, 2024: None, 2026: 20}
IDADE_API_H = 20          # listas de Câmara/Senado e consultas ao DivulgaCandContas
IDADE_DETALHE_H = 24 * 7  # CPF/nome civil/nascimento (quase nunca muda)

# Código de cada eleição geral/municipal no DivulgaCandContas (fotos e páginas das candidaturas).
ID_DIVULGA = {2018: "2022802018", 2022: "2040602022", 2024: "2045202024", 2026: "20322002026"}
# CD_ELEICAO das eleições ordinárias (as outras são suplementares).
ORDINARIAS = {
    2018: {"295", "296", "297", "298"},
    2022: {"544", "545", "546", "547"},
    2024: {"619", "620"},
    2026: {"6257", "6258", "6259", "6260"},
}
REGIAO = {uf: reg for reg, ufs in {
    "NORTE": "AC AM AP PA RO RR TO", "NORDESTE": "AL BA CE MA PB PE PI RN SE",
    "CENTROOESTE": "DF GO MS MT", "SUDESTE": "ES MG RJ SP", "SUL": "PR RS SC"}.items() for uf in ufs.split()}
UFS = sorted(REGIAO)
# O servidor do DivulgaCandContas só responde a pedidos com os cabeçalhos que todo navegador manda e
# recusa (403) User-Agent com "https://" (o UA de comum.py tem); por isso o UA vai sem o "https://".
H_DIVULGA = {"Accept": "application/json", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
             "Sec-Fetch-Site": "same-origin",
             "User-Agent": "EntendaPolitica/1.0 (site educativo sem fins lucrativos; +entendapolitica.vercel.app)"}

CARGOS = {  # DS_CARGO do TSE -> (masculino, feminino)
    "PRESIDENTE": ("Presidente", "Presidente"),
    "VICE-PRESIDENTE": ("Vice-presidente", "Vice-presidente"),
    "GOVERNADOR": ("Governador", "Governadora"),
    "VICE-GOVERNADOR": ("Vice-governador", "Vice-governadora"),
    "SENADOR": ("Senador", "Senadora"),
    "1º SUPLENTE": ("1º suplente de senador", "1ª suplente de senador"),
    "2º SUPLENTE": ("2º suplente de senador", "2ª suplente de senador"),
    "DEPUTADO FEDERAL": ("Deputado federal", "Deputada federal"),
    "DEPUTADO ESTADUAL": ("Deputado estadual", "Deputada estadual"),
    "DEPUTADO DISTRITAL": ("Deputado distrital", "Deputada distrital"),
    "PREFEITO": ("Prefeito", "Prefeita"),
    "VICE-PREFEITO": ("Vice-prefeito", "Vice-prefeita"),
    "VEREADOR": ("Vereador", "Vereadora"),
}
SUPLENTES_SENADO = ("1º SUPLENTE", "2º SUPLENTE")
PRIORIDADE_SIT = {"ELEITO": 0, "ELEITO POR QP": 0, "ELEITO POR MÉDIA": 0, "2º TURNO": 1, "SUPLENTE": 2, "NÃO ELEITO": 3}

AVISO_DEST = ("Lista de quem foi eleito em {ano}, segundo o TSE. Alguns podem ter saído e suplentes podem ter "
              "assumido: quem está no cargo hoje aparece no site oficial da Assembleia.")
AVISO_DIST = ("Lista de quem foi eleito em {ano}, segundo o TSE. Alguns podem ter saído e suplentes podem ter "
              "assumido: quem está no cargo hoje aparece no site oficial da Câmara Legislativa.")
AVISO_PREF = ("Prefeito(a) e vice eleitos em 2024, segundo o TSE. Pode ter havido mudanças depois "
              "(cassação, renúncia, morte ou eleição suplementar).")
AVISO_VER = ("Lista de quem foi eleito em 2024, segundo o TSE. Alguns podem ter saído (cassação, renúncia, "
             "licença) e suplentes podem ter assumido.")
# os mesmos avisos em inglês (o site tem versão em inglês)
AVISO_DEST_EN = ("List of the people elected in {ano}, according to the TSE (Superior Electoral Court). Some may have "
                 "left and substitutes may have taken their seats: who is in office today is shown on the official "
                 "website of the Legislative Assembly (state parliament).")
AVISO_DIST_EN = ("List of the people elected in {ano}, according to the TSE (Superior Electoral Court). Some may have "
                 "left and substitutes may have taken their seats: who is in office today is shown on the official "
                 "website of the Legislative Chamber of the Federal District.")
AVISO_PREF_EN = ("Mayor and vice mayor elected in 2024, according to the TSE (Superior Electoral Court). There may "
                 "have been changes since then (removal from office, resignation, death or a special election).")
AVISO_VER_EN = ("List of the people elected in 2024, according to the TSE (Superior Electoral Court). Some may have "
                "left (removal from office, resignation, leave) and substitutes may have taken their seats.")


# ---------------------------------------------------------------- textos
_ABREV = {"DR", "DRS", "PR", "SGT", "SD", "CB", "CPT", "TC", "ST", "SR", "SRA", "JR"}
_ROMANOS = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}


def nome_tse(s: str | None) -> str | None:
    """Nome em maiúsculas do TSE -> 'Nome Próprio', mantendo siglas sem vogal (JHC) e números romanos."""
    s = limpa(re.sub(r"\.{2,}", ".", s or ""))
    if not s:
        return None
    out = []
    for tok in nome_proprio(s).split(" "):
        if tok == ".":
            continue
        base = sem_acento(tok).upper()
        if base in _ROMANOS:
            tok = tok.upper()
        elif len(base) >= 3 and base.isalpha() and base not in _ABREV and not re.search(r"[AEIOUY]", base):
            tok = tok.upper()
        tok = re.sub(r"([-'’])(\w)", lambda m: m.group(1) + m.group(2).upper(), tok)
        out.append(tok)
    return " ".join(out)


def genero(ds: str | None) -> str | None:
    ds = (ds or "").upper()
    return "F" if ds.startswith("FEM") else "M" if ds.startswith("MASC") else None


def cargo_txt(cargo: str, g: str | None) -> str:
    m, f = CARGOS.get(cargo, (nome_proprio(cargo.lower()), nome_proprio(cargo.lower())))
    return f if g == "F" else m


def minusc1(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[0].isdigit() else s


def eleito(sit: str | None) -> bool:
    return (sit or "").startswith("ELEITO")


def sit_txt(sit: str, g: str | None) -> str | None:
    a = "a" if g == "F" else "o"
    return {
        "ELEITO": f"Eleit{a}", "ELEITO POR QP": f"Eleit{a} por QP", "ELEITO POR MÉDIA": f"Eleit{a} por média",
        "SUPLENTE": "Suplente", "NÃO ELEITO": f"Não eleit{a}", "2º TURNO": "Foi ao 2º turno",
    }.get(sit)


def data_br(iso: str | None) -> str | None:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else None


MESES_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December")


def data_en(iso: str | None) -> str | None:
    return f"{MESES_EN[int(iso[5:7]) - 1]} {int(iso[8:10])}, {iso[:4]}" if iso else None


def cpf_valido(s: str | None) -> str | None:
    d = re.sub(r"\D", "", s or "")
    return d.zfill(11) if 0 < len(d) <= 11 and int(d) > 0 else None


def social(s: str | None) -> str | None:
    s = limpa(s)
    return None if not s or s.startswith("#") or "DIVULG" in sem_acento(s).upper() else s


def chave_ord(nome: str | None, extra: str = "") -> tuple:
    return (chave_nome(nome or ""), extra)


# ---------------------------------------------------------------- arquivos do TSE
def zip_tse(pasta: str, ano: int) -> Path:
    nome = f"{pasta}_{ano}.zip"
    idade = IDADE_H.get(ano, 20)
    if hoje() >= f"{ano + 1}-02-01":
        idade = None  # eleição encerrada há meses (os eleitos já tomaram posse): baixa uma vez só
    return baixar_arquivo(f"{CDN}{pasta}/{nome}", f"tse/{nome}", max_idade_h=idade)


def chave_cache() -> str:
    """Nome do cache de .cache/tse no GitHub Actions. Muda quando uma eleição fecha (1º de fevereiro do ano seguinte):
    aí os arquivos dela, que não mudam mais, entram no cache novo (o nome antigo não seria salvo de novo)."""
    h = hoje()
    fechadas = [a for a in range(2018, int(h[:4]) + 1, 2) if h >= f"{a + 1}-02-01"]
    return "tse-" + "-".join(map(str, fechadas[-2:]))


def membros_csv(z: zipfile.ZipFile) -> list[str]:
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    brasil = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
    return brasil or nomes


def ler_csv(caminho: Path):
    with zipfile.ZipFile(caminho) as z:
        for nome in membros_csv(z):
            with z.open(nome) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def cand(r: dict, ano: int) -> dict:
    """Linha do consulta_cand reduzida ao que usamos."""
    return {
        "ano": ano, "el": r["CD_ELEICAO"], "turno": int(r["NR_TURNO"]), "dt": data_iso(r["DT_ELEICAO"]),
        "uf": r["SG_UF"], "ue": r["SG_UE"], "nm_ue": r["NM_UE"], "cargo": r["DS_CARGO"].upper(),
        "sq": r["SQ_CANDIDATO"], "num": r["NR_CANDIDATO"], "nome": limpa(r["NM_CANDIDATO"]),
        "civil": social(r.get("NM_SOCIAL_CANDIDATO")) or limpa(r["NM_CANDIDATO"]),
        "urna": limpa(r["NM_URNA_CANDIDATO"]), "cpf": cpf_valido(r.get("NR_CPF_CANDIDATO")),
        "partido": limpa(r["SG_PARTIDO"]), "nasc": data_iso(r["DT_NASCIMENTO"]),
        "genero": genero(r["DS_GENERO"]), "sit": (r["DS_SIT_TOT_TURNO"] or "").upper(),
        "ocup": limpa(r.get("DS_OCUPACAO")), "instr": limpa(r.get("DS_GRAU_INSTRUCAO")),
    }


def _cache_derivado(nome: str, origem: Path, calcular):
    """Guarda em .cache/tse um resumo calculado de um arquivo grande (refaz se o arquivo mudar)."""
    destino = CACHE_TSE / nome
    if destino.exists() and destino.stat().st_mtime >= origem.stat().st_mtime:
        with open(destino, encoding="utf-8") as f:
            return json.load(f)
    valor = calcular()
    tmp = destino.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(valor, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, destino)
    return valor


def votos(ano: int) -> dict:
    """{"SQ|turno": votos nominais válidos}, somando a votação por município e zona."""
    z = zip_tse("votacao_candidato_munzona", ano)

    def calcular():
        t = time.time()
        soma = collections.Counter()
        data = None
        with zipfile.ZipFile(z) as zz:
            for nome in membros_csv(zz):
                with zz.open(nome) as f:
                    cab = f.readline().decode("latin-1").strip().replace('"', "").split(";")
                    i_t, i_sq = cab.index("NR_TURNO"), cab.index("SQ_CANDIDATO")
                    i_v = cab.index("QT_VOTOS_NOMINAIS_VALIDOS") if "QT_VOTOS_NOMINAIS_VALIDOS" in cab else cab.index("QT_VOTOS_NOMINAIS")
                    i_g = cab.index("DT_GERACAO")
                    for linha in f:
                        p = linha.split(b";")
                        if len(p) != len(cab):  # ";" dentro de algum texto: usa o leitor de CSV
                            p = [x.encode("latin-1") for x in next(csv.reader([linha.decode("latin-1")], delimiter=";"))]
                        if data is None:
                            data = data_iso(p[i_g].decode("latin-1").strip('"'))
                        sq, turno = p[i_sq].strip(b'"').decode(), p[i_t].strip(b'"').decode()
                        soma[sq + "|" + turno] += int(p[i_v].strip(b'"') or 0)
        log(f"  votos {ano}: {len(soma)} candidaturas somadas em {time.time() - t:.0f}s")
        return {"data": data, "votos": dict(soma)}

    return _cache_derivado(f"votos_{ano}.json", z, calcular)


def votos_ou_nada(ano: int) -> dict:
    """votos(ano), ou nenhum voto se o arquivo ainda não existir (eleição recém-terminada): a ficha sai sem o número."""
    try:
        return votos(ano)
    except Exception as e:  # noqa: BLE001
        log(f"  [aviso] votos de {ano} indisponíveis ({e}); as fichas saem sem o número de votos")
        return {"votos": {}, "data": None}


def bens(ano: int) -> dict:
    """{"data": geração, "bens": {SQ: total declarado}}."""
    z = zip_tse("bem_candidato", ano)

    def calcular():
        soma, data = collections.defaultdict(float), None
        for r in ler_csv(z):
            data = data or data_iso(r["DT_GERACAO"])
            try:
                soma[r["SQ_CANDIDATO"]] += float((r["VR_BEM_CANDIDATO"] or "0").replace(".", "").replace(",", "."))
            except ValueError:
                pass
        return {"data": data, "bens": {k: round(v, 2) for k, v in soma.items()}}

    return _cache_derivado(f"bens_{ano}.json", z, calcular)


class Base:
    """Candidaturas de uma eleição geral (2018, 2022), com índices para casar pessoas."""

    def __init__(self, ano: int):
        self.ano, self.data = ano, None
        self.rows, self.por_sq = [], collections.defaultdict(list)
        self.por_cpf, self.por_nn = collections.defaultdict(set), collections.defaultdict(set)
        for r in ler_csv(zip_tse("consulta_cand", ano)):
            self.data = self.data or data_iso(r["DT_GERACAO"])
            c = cand(r, ano)
            self.rows.append(c)
            self.por_sq[c["sq"]].append(c)
            if c["cpf"]:
                self.por_cpf[c["cpf"]].add(c["sq"])
            if c["nasc"]:
                self.por_nn[(chave_nome(c["nome"]), c["nasc"])].add(c["sq"])

    def achar(self, cpf=None, nome=None, nasc=None) -> list[str]:
        sqs = set()
        if cpf:
            sqs = set(self.por_cpf.get(cpf_valido(cpf) or "", ()))
        if not sqs and nome and nasc:
            sqs = set(self.por_nn.get((chave_nome(nome), nasc), ()))
        return sorted(sqs)

    def linha(self, sq: str, turno: int | None = None) -> dict | None:
        rs = self.por_sq.get(sq) or []
        if turno is not None:
            rs = [c for c in rs if c["turno"] == turno] or rs
        return rs[0] if rs else None


# ---------------------------------------------------------------- DivulgaCandContas
def url_foto(ano: int, sq: str, local: str, id_eleicao: str | None = None) -> str:
    """URL pública da foto da candidatura (2018/2022/2026: local = UF; 2024: local = código TSE do município)."""
    return f"{DIVULGA}/rest/arquivo/img/{id_eleicao or ID_DIVULGA[ano]}/{sq}/{local}"


def url_cand(ano: int, sq: str, uf: str, ue: str, id_eleicao: str | None = None) -> str:
    reg = "BR" if uf == "BR" else REGIAO[uf]
    return f"{DIVULGA}/#/candidato/{reg}/{uf}/{id_eleicao or ID_DIVULGA[ano]}/{sq}/{ano}/{ue}"


def fonte_cand(c: dict, data: str | None, id_eleicao: str | None = None, ano_divulga: int | None = None) -> dict:
    ano = ano_divulga or c["ano"]
    return fonte("TSE", f"DivulgaCandContas: candidatura de {nome_tse(c['urna'])} ({c['dt'][:4] if c.get('dt') else ano})",
                 url_cand(ano, c["sq"], c["uf"], c["ue"], id_eleicao), data)


def fonte_resultados(ano: int, data: str | None, titulo: str | None = None) -> dict:
    return fonte("TSE", titulo or f"Dados Abertos: resultados de {ano} (votação nominal por município e zona)",
                 f"{PORTAL}resultados-{ano}", data)


def fonte_candidatos(ano: int, data: str | None, titulo: str | None = None) -> dict:
    return fonte("TSE", titulo or f"Dados Abertos: candidaturas de {ano}", f"{PORTAL}candidatos-{ano}", data)


def divulga_json(caminho: str, cache: str):
    return baixar_json(f"{DIVULGA}/rest/v1/{caminho}", cache=f"tse/divulga/{cache}", max_idade_h=IDADE_API_H,
                       headers=H_DIVULGA, tentativas=3, timeout=60)


def divulga_totalizacao_2024(ue: str, cod_cargo: int) -> dict | None:
    """{SQ: situação (como no CSV: 'ELEITO', 'ELEITO POR QP'...)} do DivulgaCandContas, ou None se falhar."""
    try:
        d = divulga_json(f"candidatura/listar/2024/{ue}/{ID_DIVULGA[2024]}/{cod_cargo}/candidatos",
                         f"listar_2024_{ue}_{cod_cargo}.json")
    except Exception as e:
        log(f"  [aviso] DivulgaCandContas {ue}/{cod_cargo}: {e}")
        return None
    return {str(c["id"]): (c.get("descricaoTotalizacao") or "").upper() for c in d.get("candidatos") or []}


def ids_suplementares_2024(ufs) -> dict:
    """{(código TSE do município, 'AAAA-MM-DD'): id da eleição suplementar no DivulgaCandContas}."""
    out = {}
    for uf in sorted(ufs):
        try:
            for e in divulga_json(f"eleicao/suplementares/2024/{uf}", f"suplementares_2024_{uf}.json") or []:
                out[(str(e.get("siglaUF")), str(e.get("dataEleicao"))[:10])] = str(e["id"])
        except Exception as e:
            log(f"  [aviso] eleições suplementares de {uf} no DivulgaCandContas: {e}")
    return out


# ---------------------------------------------------------------- 2026
class Base2026:
    """Candidaturas de 2026 (situação depois da totalização) para o campo eleicao2026."""

    def __init__(self):
        comp = {}
        for r in ler_csv(zip_tse("consulta_cand_complementar", 2026)):
            comp[(r["SQ_CANDIDATO"], r["CD_ELEICAO"])] = (r["ST_CANDIDATO_INSERIDO_URNA"], r["DS_SITUACAO_JULGAMENTO"])
        self.data = None
        self.por_sq = collections.defaultdict(list)
        self.por_cpf, self.por_nn = collections.defaultdict(set), collections.defaultdict(set)
        for r in ler_csv(zip_tse("consulta_cand", 2026)):
            self.data = self.data or data_iso(r["DT_GERACAO"])
            c = cand(r, 2026)
            c["urna_sim"], c["julg"] = comp.get((c["sq"], c["el"]), (None, None))
            self.por_sq[c["sq"]].append(c)
            if c["cpf"]:
                self.por_cpf[c["cpf"]].add(c["sq"])
            if c["nasc"]:
                self.por_nn[(chave_nome(c["nome"]), c["nasc"])].add(c["sq"])

    def achar(self, cpf=None, nome=None, nasc=None) -> list[str]:
        sqs = set(self.por_cpf.get(cpf_valido(cpf) or "", ())) if cpf else set()
        if not sqs and nome and nasc:
            sqs = set(self.por_nn.get((chave_nome(nome), nasc), ()))
        return sorted(sqs)

    def melhor(self, sqs: list[str]) -> str:
        """Se a pessoa tem mais de um registro, vale o que foi para a urna e com resultado mais definido."""
        def chave(sq):
            rs = self.por_sq[sq]
            na_urna = any(c["urna_sim"] == "SIM" for c in rs)
            return (0 if na_urna else 1, min(PRIORIDADE_SIT.get(c["sit"], 9) for c in rs), sq)
        return min(sqs, key=chave)

    def fonte_lista(self) -> dict:
        return fonte_candidatos(2026, self.data, "Dados Abertos: candidaturas de 2026 (a pessoa não aparece na lista)")

    def situacao(self, cpf=None, nome=None, nasc=None, cargo_atual: str | None = None, g: str | None = None) -> dict:
        sqs = self.achar(cpf, nome, nasc)
        if not sqs:
            return {"cargo": None, "situacao": "nao-concorreu", "txt": "Não concorreu em 2026", "fonte": self.fonte_lista()}
        sq = self.melhor(sqs)
        rs = sorted(self.por_sq[sq], key=lambda c: c["turno"])
        t1 = rs[0]
        t2 = next((c for c in rs if c["turno"] == 2), None)
        g = t1["genero"] or g
        a = "a" if g == "F" else "o"
        cargo = cargo_txt(t1["cargo"], g)
        cl = minusc1(cargo)
        suplente_senado = t1["cargo"] in SUPLENTES_SENADO
        if t2 and eleito(t2["sit"]):
            sit = "reeleito" if t1["cargo"] == cargo_atual else "eleito"
            txt = f"{'Reeleit' if sit == 'reeleito' else 'Eleit'}{a} {cl} no 2º turno de 2026"
        elif t2 and t2["sit"] == "NÃO ELEITO":
            sit, txt = "nao-eleito", f"Disputou o 2º turno para {cl} em 2026 e não foi eleit{a}"
        elif t1["sit"] == "2º TURNO":
            sit, txt = "segundo-turno", f"Disputa o 2º turno para {cl} em {data_br(t2['dt']) if t2 else 'outubro de 2026'}"
        elif eleito(t1["sit"]):
            if suplente_senado:
                sit, txt = "suplente", f"Eleit{a} {cl} em 2026"
            elif t1["cargo"] == cargo_atual:
                sit, txt = "reeleito", f"Reeleit{a} {cl} em 2026"
            else:
                sit, txt = "eleito", f"Eleit{a} {cl} em 2026"
        elif t1["sit"] == "SUPLENTE":
            sit, txt = "suplente", f"Concorreu a {cl} em 2026 e ficou como suplente"
        elif t1["sit"] == "NÃO ELEITO":
            sit, txt = "nao-eleito", f"Concorreu a {cl} em 2026 e não foi eleit{a}"
        elif t1["urna_sim"] == "SIM":
            sit, txt = "candidato", f"Concorreu a {cl} em 2026; o TSE ainda não fechou o resultado"
        else:
            julg = sem_acento(t1["julg"] or "").upper()
            sit = "nao-concorreu"
            if "RENUNCIA" in julg:
                txt = f"Desistiu da candidatura a {cl} em 2026"
            elif "INDEFERIDO" in julg:
                txt = f"Teve a candidatura a {cl} negada pela Justiça Eleitoral em 2026"
            elif "CANCELADO" in julg:
                txt = f"Teve a candidatura a {cl} cancelada em 2026"
            elif "FALECIDO" in julg:
                txt = f"Era candidat{a} a {cl} em 2026"
            else:
                txt = f"Pediu registro de candidatura a {cl} em 2026, mas não foi para a urna"
        return {"cargo": cargo, "situacao": sit, "txt": txt, "fonte": fonte_cand(t1, self.data)}

    def foto(self, cpf=None, nome=None, nasc=None) -> str | None:
        sqs = self.achar(cpf, nome, nasc)
        if not sqs:
            return None
        c = self.por_sq[self.melhor(sqs)][0]
        return url_foto(2026, c["sq"], c["uf"])


# ---------------------------------------------------------------- federais (quem está no mandato hoje)
def _api(url: str, cache: str, idade):
    return baixar_json(url, cache=cache, max_idade_h=idade, tentativas=4, timeout=90)


def deputados_atuais() -> list[dict]:
    cam = ler_json(DADOS / "camara.json")
    lista = _api("https://dadosabertos.camara.leg.br/api/v2/deputados?itens=1000&ordem=ASC&ordenarPor=nome",
                 "tse/camara/lista.json", IDADE_API_H)["dados"]
    por_id = {str(d["id"]): d for d in lista}
    membros = {str(m["id"]).replace("dep-", ""): m for m in (cam or {}).get("membros") or []}
    ids = list(membros) if membros else list(por_id)

    def detalhe(i):
        return i, _api(f"https://dadosabertos.camara.leg.br/api/v2/deputados/{i}", f"tse/camara/{i}.json", IDADE_DETALHE_H)["dados"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        det = dict(ex.map(detalhe, ids))
    out = []
    for i in ids:
        d, m, l = det[i], membros.get(i) or {}, por_id.get(i) or {}
        us = d.get("ultimoStatus") or {}
        out.append({
            "id": f"dep-{i}", "tipo": "dep", "cargo": "DEPUTADO FEDERAL",
            "nome": m.get("nome") or l.get("nome") or us.get("nome"),
            "partido": m.get("partido") or l.get("siglaPartido") or us.get("siglaPartido"),
            "uf": m.get("uf") or l.get("siglaUf") or us.get("siglaUf"),
            "genero": m.get("genero") if "genero" in m else ({"M": "M", "F": "F"}.get(d.get("sexo"))),
            "cpf": cpf_valido(d.get("cpf")), "nomeCivil": limpa(d.get("nomeCivil")), "nasc": data_iso(d.get("dataNascimento")),
        })
    return out


def senadores_atuais() -> list[dict]:
    sen = ler_json(DADOS / "senado.json")
    lst = _api("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json", "tse/senado/lista.json", IDADE_API_H)
    ps = lst["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    por_cod = {p["IdentificacaoParlamentar"]["CodigoParlamentar"]: p for p in ps}
    membros = {str(m["id"]).replace("sen-", ""): m for m in (sen or {}).get("membros") or []}
    ids = list(membros) if membros else list(por_cod)

    def detalhe(cod):
        d = _api(f"https://legis.senado.leg.br/dadosabertos/senador/{cod}.json", f"tse/senado/{cod}.json", IDADE_DETALHE_H)
        return cod, d["DetalheParlamentar"]["Parlamentar"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        det = dict(ex.map(detalhe, ids))
    out = []
    for cod in ids:
        d, m, p = det[cod], membros.get(cod) or {}, por_cod.get(cod) or {}
        ident = d.get("IdentificacaoParlamentar") or p.get("IdentificacaoParlamentar") or {}
        mand = p.get("Mandato") or {}
        if isinstance(mand, list):
            mand = mand[0] if mand else {}
        sexo = (ident.get("SexoParlamentar") or "").upper()
        out.append({
            "id": f"sen-{cod}", "tipo": "sen", "cargo": "SENADOR",
            "nome": m.get("nome") or ident.get("NomeParlamentar"),
            "partido": m.get("partido") or ident.get("SiglaPartidoParlamentar"),
            "uf": m.get("uf") or ident.get("UfParlamentar") or mand.get("UfParlamentar"),
            "genero": m.get("genero") if "genero" in m else ("F" if sexo.startswith("F") else "M" if sexo.startswith("M") else None),
            "cpf": None, "nomeCivil": limpa(ident.get("NomeCompletoParlamentar")),
            "nasc": data_iso((d.get("DadosBasicosParlamentar") or {}).get("DataNascimento")),
            "participacao": mand.get("DescricaoParticipacao"),
            "legislatura": (mand.get("PrimeiraLegislaturaDoMandato") or {}).get("NumeroLegislatura"),
        })
    return out


_PALAVRAS_COMUNS = {"DA", "DE", "DO", "DAS", "DOS", "E", "FILHO", "JUNIOR", "NETO", "SOBRINHO", "SILVA", "SANTOS", "SOUZA"}


def _mesmo_nome(a: str, b: str) -> bool:
    ta = {t for t in chave_nome(a).split() if len(t) > 2 and t not in _PALAVRAS_COMUNS}
    tb = {t for t in chave_nome(b).split() if len(t) > 2 and t not in _PALAVRAS_COMUNS}
    return bool(ta & tb)


def executivo_atual(b22: Base) -> list[dict]:
    """Presidente e vice em exercício (dados/executivo.json) casados com a eleição do mandato em curso (b22.ano)."""
    ex = ler_json(DADOS / "executivo.json") or {}
    out = []
    ano = b22.ano
    for chave, cargo, tipo, padrao in (("presidente", "PRESIDENTE", "pres", "pres-lula"), ("vice", "VICE-PRESIDENTE", "vp", "vp-alckmin")):
        el = [c for c in b22.rows if c["cargo"] == cargo and c["el"] in ORDINARIAS[ano] and eleito(c["sit"])]
        el = [c for c in el if c["turno"] == max(x["turno"] for x in el)] if el else el
        if len(el) != 1:
            log(f"  [aviso] {cargo} eleito em {ano} não encontrado no TSE")
            continue
        c = el[0]
        p = ex.get(chave) or {}
        if p.get("nome") and not _mesmo_nome(p["nome"], f"{c['urna']} {c['nome']}"):
            log(f"  [aviso] {chave} em executivo.json ({p['nome']}) não é quem foi eleito em {ano} ({c['urna']}); sem dados do TSE")
            continue
        out.append({
            "id": p.get("id") or padrao, "tipo": tipo, "cargo": cargo, "nome": p.get("nome") or nome_tse(c["urna"]),
            "partido": p.get("partido") or c["partido"], "uf": "BR", "genero": p.get("genero") or c["genero"],
            "cpf": c["cpf"], "nomeCivil": c["civil"], "nasc": c["nasc"], "tseExec": c,
        })
    return out


def casar_federais(fed: list[dict], b18: Base, b22: Base) -> None:
    """Acha a candidatura que levou cada federal ao mandato atual (f['tse'])."""
    senado = [c for b in (b22, b18) for c in b.rows if c["cargo"] in ("SENADOR",) + SUPLENTES_SENADO and eleito(c["sit"])]
    for f in fed:
        f["tse"] = None
        if f["tipo"] in ("pres", "vp"):
            f["tse"] = f.pop("tseExec")
            continue
        if f["tipo"] == "dep":
            cands = [b22.linha(sq) for sq in b22.achar(f["cpf"], f["nomeCivil"], f["nasc"])]
            cands = [c for c in cands if c and c["cargo"] == "DEPUTADO FEDERAL" and c["el"] in ORDINARIAS[b22.ano]]
            if len(cands) == 1:
                f["tse"] = cands[0]
                f["cpf"] = f["cpf"] or cands[0]["cpf"]
            continue
        # senadores: titulares e suplentes eleitos em 2018 (ou em eleição suplementar) ou em 2022
        cands = [c for c in senado if c["uf"] == f["uf"]]
        exato = [c for c in cands if c["nasc"] == f["nasc"] and chave_nome(c["nome"]) == chave_nome(f["nomeCivil"])]
        mesma_data = [c for c in cands if c["nasc"] and c["nasc"] == f["nasc"]]
        if len(exato) > 1:
            # a mesma pessoa em duas chapas (ex.: suplente em 2018 e titular em 2022): vale a do mandato atual
            ano = {"56": 2018, "57": 2022, "58": 2026}.get(str(f.get("legislatura")))
            part = sem_acento(f.get("participacao") or "").upper()
            cargo = "SENADOR" if part.startswith("TITULAR") else "1º SUPLENTE" if part.startswith("1") else "2º SUPLENTE" if part.startswith("2") else None
            exato = [c for c in exato if (ano is None or c["ano"] == ano) and (cargo is None or c["cargo"] == cargo)] or exato
        if len(exato) == 1:
            f["tse"] = exato[0]
        elif not exato and len(mesma_data) == 1:
            f["tse"] = mesma_data[0]
            log(f"  {f['id']} ({f['nomeCivil']}) casado com o TSE pela data de nascimento + UF: {mesma_data[0]['nome']}")
        if f["tse"]:
            f["cpf"] = f["tse"]["cpf"]


def bloco_eleicao_federal(f: dict, bases: dict, vot: dict) -> dict | None:
    c = f["tse"]
    if not c:
        return None
    b = bases[c["ano"]]
    g = c["genero"] or f["genero"]
    a = "a" if g == "F" else "o"
    ano_el = int((c["dt"] or str(c["ano"]))[:4])
    if c["cargo"] in SUPLENTES_SENADO:
        tit = next((x for x in b.rows if x["uf"] == c["uf"] and x["el"] == c["el"] and x["cargo"] == "SENADOR"
                    and x["num"] == c["num"] and eleito(x["sit"])), None)
        situacao = f"Eleit{a} {minusc1(cargo_txt(c['cargo'], g))}" + (f" na chapa de {nome_tse(tit['urna'])}" if tit else "")
        n = None
    else:
        situacao = sit_txt(c["sit"], g)
        if c["cargo"] in ("PRESIDENTE", "VICE-PRESIDENTE"):
            situacao = f"Eleit{a} no {c['turno']}º turno"
        tit = c
        if c["cargo"] == "VICE-PRESIDENTE":
            tit = next((x for x in b.rows if x["cargo"] == "PRESIDENTE" and x["el"] == c["el"] and eleito(x["sit"])), None)
            situacao += " (votos da chapa)"
        n = vot[c["ano"]]["votos"].get(f"{tit['sq']}|{tit['turno']}") if tit else None
    return {"ano": ano_el, "cargo": cargo_txt(c["cargo"], g), "votos": n, "situacao": situacao,
            "fonte": fonte_resultados(c["ano"], vot[c["ano"]]["data"]) if n is not None else fonte_cand(c, b.data)}


def candidatura_recente(f: dict, b26: Base2026, b22: Base, b18: Base, fed24: dict):
    """(ano, linha da candidatura, data dos dados) da candidatura mais recente da pessoa (2026, 2024, 2022 ou 2018)."""
    nn = (chave_nome(f["nomeCivil"] or ""), f["nasc"])
    sqs = b26.achar(f["cpf"], f["nomeCivil"], f["nasc"])
    if sqs:
        return (2026, b26.por_sq[b26.melhor(sqs)][0], b26.data)
    if fed24.get(nn):
        rs = sorted(fed24[nn], key=lambda c: (PRIORIDADE_SIT.get(c["sit"], 9), c["el"] not in ORDINARIAS[2024]))
        return (2024, rs[0], None)
    for b in (b22, b18):
        sqs = b.achar(f["cpf"], f["nomeCivil"], f["nasc"])
        if sqs:
            rs = sorted((b.linha(sq) for sq in sqs), key=lambda c: (PRIORIDADE_SIT.get(c["sit"], 9), c["sq"]))
            return (b.ano, rs[0], b.data)
    return None


def bloco_bens(f: dict, b26: Base2026, b22: Base, b18: Base, fed24: dict, bens_ano) -> dict | None:
    """Bens da candidatura mais recente (2026, 2024, 2022 ou 2018)."""
    escolha = candidatura_recente(f, b26, b22, b18, fed24)
    if not escolha:
        return None
    ano, c, _ = escolha
    if c["el"] not in ORDINARIAS[ano]:
        return None  # eleição suplementar: sem página conhecida no DivulgaCandContas
    bb = bens_ano(ano)
    return {"ano": ano, "total": bb["bens"].get(c["sq"], 0.0),
            "fonte": fonte("TSE", f"DivulgaCandContas: bens declarados por {nome_tse(c['urna'])} ({ano})",
                           url_cand(ano, c["sq"], c["uf"], c["ue"]), bb["data"])}


_FEMININO = {  # o TSE escreve as ocupações no masculino; para mulheres, troca as palavras que mudam
    "DEPUTADO": "DEPUTADA", "SENADOR": "SENADORA", "VEREADOR": "VEREADORA", "PREFEITO": "PREFEITA", "GOVERNADOR": "GOVERNADORA",
    "ADVOGADO": "ADVOGADA", "MÉDICO": "MÉDICA", "EMPRESÁRIO": "EMPRESÁRIA", "PROFESSOR": "PROFESSORA", "ENGENHEIRO": "ENGENHEIRA",
    "SERVIDOR": "SERVIDORA", "PÚBLICO": "PÚBLICA", "ADMINISTRADOR": "ADMINISTRADORA", "DELEGADO": "DELEGADA", "AGRICULTOR": "AGRICULTORA",
    "PRODUTOR": "PRODUTORA", "ODONTÓLOGO": "ODONTÓLOGA", "PSICÓLOGO": "PSICÓLOGA", "CONTADOR": "CONTADORA", "TÉCNICO": "TÉCNICA",
    "SOCIÓLOGO": "SOCIÓLOGA", "BIÓLOGO": "BIÓLOGA", "FARMACÊUTICO": "FARMACÊUTICA", "ENFERMEIRO": "ENFERMEIRA", "APOSENTADO": "APOSENTADA",
    "VETERINÁRIO": "VETERINÁRIA", "PEDAGOGO": "PEDAGOGA", "LOCUTOR": "LOCUTORA", "COMUNICADOR": "COMUNICADORA", "APRESENTADOR": "APRESENTADORA",
    "CANTOR": "CANTORA", "ATOR": "ATRIZ", "ESCRITOR": "ESCRITORA", "PASTOR": "PASTORA", "BANCÁRIO": "BANCÁRIA", "SECRETÁRIO": "SECRETÁRIA",
    "DIRETOR": "DIRETORA", "COMERCIÁRIO": "COMERCIÁRIA", "SERVENTUÁRIO": "SERVENTUÁRIA", "PROPRIETÁRIO": "PROPRIETÁRIA", "SUPERVISOR": "SUPERVISORA",
    "VENDEDOR": "VENDEDORA", "AGROPECUÁRIO": "AGROPECUÁRIA", "ESTAGIÁRIO": "ESTAGIÁRIA", "BOLSISTA": "BOLSISTA", "TRABALHADOR": "TRABALHADORA", "ARQUITETO": "ARQUITETA", "GEÓGRAFO": "GEÓGRAFA", "HISTORIADOR": "HISTORIADORA",
    "METALÚRGICO": "METALÚRGICA", "MOTORISTA": "MOTORISTA", "OPERADOR": "OPERADORA", "AUXILIAR": "AUXILIAR", "EMPREGADO": "EMPREGADA",
}


def _feminino(txt: str) -> str:
    return " ".join(_FEMININO.get(w, w) for w in txt.split())


def _ficha_txt(v: str | None, g: str | None) -> str | None:
    v = (v or "").strip()
    if not v or v.upper() in ("OUTROS", "#NULO#", "#NE", "NÃO DIVULGÁVEL", "NAO DIVULGAVEL"):
        return None
    v = v.upper()
    if g == "F":
        v = _feminino(v)
    return v[:1] + v[1:].lower()


def bloco_ficha(f: dict, b26: Base2026, b22: Base, b18: Base, fed24: dict) -> dict | None:
    """Ocupação e escolaridade declaradas ao TSE na candidatura mais recente. É a mesma fonte para todo mundo:
    as Casas e o Planalto descrevem (ou não) profissões e escolaridade de jeitos diferentes."""
    escolha = candidatura_recente(f, b26, b22, b18, fed24)
    if not escolha:
        return None
    ano, c, data = escolha
    oc, ins = _ficha_txt(c.get("ocup"), f.get("genero") or c.get("genero")), _ficha_txt(c.get("instr"), None)
    if not oc and not ins:
        return None
    eh_supl = c["el"] not in ORDINARIAS[ano]
    fonte_c = (fonte_candidatos(ano, data, f"Dados Abertos: candidaturas de {ano}") if eh_supl or ano == 2024
               else fonte_cand(c, data))
    return {"ano": ano, "ocupacao": oc, "escolaridade": ins, "fonte": fonte_c}


# ---------------------------------------------------------------- estados
def eleito_exec(rows: list[dict], cargo: str, ordinarias: set) -> dict | None:
    el = [c for c in rows if c["cargo"] == cargo and c["el"] in ordinarias and eleito(c["sit"])]
    el.sort(key=lambda c: c["turno"], reverse=True)
    return el[0] if el else None


def bloco_eleito_exec(c: dict, titular: dict, vot: dict, data: str, ano: int, local: str, id_eleicao=None) -> dict:
    """Ficha de quem foi eleito governador/vice (ou prefeito/vice). Vice: votos da chapa."""
    g = c["genero"]
    a = "a" if g == "F" else "o"
    vice = c["cargo"].startswith("VICE")
    if c["el"] in ORDINARIAS[ano]:
        sit = f"Eleit{a} no {c['turno']}º turno"
    else:
        sit = f"Eleit{a} na eleição suplementar de {data_br(c['dt'])}"
    if vice and titular:
        sit += f", na chapa de {nome_tse(titular['urna'])}"
    n = vot["votos"].get(f"{titular['sq']}|{titular['turno']}") if titular else None
    b = {
        "nome": nome_tse(c["urna"]), "nomeCivil": nome_tse(c["civil"]), "partido": c["partido"], "genero": g,
        "foto": url_foto(ano, c["sq"], local, id_eleicao), "votos": n, "situacao": sit,
        "fontes": [fonte_cand(c, data, id_eleicao, ano), fonte_resultados(ano, vot["data"])],
    }
    if vice and n is not None:
        b["votosDaChapa"] = True
    return b


def limpar(d: dict, manter=()) -> dict:
    """Tira as chaves com None (menos as de `manter`, que ficam como null = sem informação)."""
    return {k: v for k, v in d.items() if v is not None or k in manter}


CAMPOS_PESSOA = ("nome", "nomeCivil", "partido", "genero", "foto")


def manual_governadores(ano: int) -> dict:
    """dados/manual/governadores.json: quem governa hoje, pesquisado à mão. "eleicao" diz de qual mandato é a pesquisa
    (2022 = mandato 2023-2026): depois da posse de quem foi eleito em outra eleição, o arquivo deixa de valer (o site
    mostra quem ganhou, com "aConfirmar") até a pesquisa ser refeita com o novo "eleicao"."""
    m = ler_json(MANUAL_GOV) or {}
    return (m.get("estados") or {}) if m.get("eleicao", 2022) == ano else {}


def manual_prefeitos(ano: int = 2024) -> dict:
    """dados/manual/prefeitos.json (opcional): {"eleicao": 2024, "cidades": {"<IBGE>": {"prefeito": {...}, "vice": {...}}}},
    no mesmo formato de governadores.json, para quem está no cargo hoje quando não é quem o TSE mostra."""
    m = ler_json(MANUAL_PREF) or {}
    return (m.get("cidades") or {}) if m.get("eleicao", 2024) == ano else {}


def _textos_manual(m: dict) -> dict:
    """Textos extras da pesquisa à mão (português e inglês) que vão junto para o site."""
    return {k: m.get(k) for k in ("comoAssumiu_en", "nota", "nota_en") if m.get(k)}


def _vago_manual(pid: str, m: dict, extra: dict, manter: tuple) -> dict:
    d = {"id": pid, "vago": True, "txt": m.get("txt") or m.get("nota") or m.get("comoAssumiu") or "Cargo vago",
         "txt_en": m.get("txt_en") or m.get("nota_en") or m.get("comoAssumiu_en") or "Vacant",
         "fontes": _fontes_manual(m)}
    d.update(extra)
    return limpar(d, manter=manter)


def aplicar_manual_cidade(pid: str, m, bloco: dict | None, candidatos: list) -> dict | None:
    """Troca a ficha do TSE pela pessoa do arquivo manual (a ficha do TSE fica em "eleito2024")."""
    if not isinstance(m, dict) or not m:
        return bloco
    eleito = {k: v for k, v in bloco.items() if k not in ("id", "aConfirmar")} if bloco else None
    if m.get("vago") or chave_nome(m.get("nome") or "") in ("VAGO", "CARGO VAGO") or not (m.get("nome") or m.get("nomeCivil")):
        return _vago_manual(pid, m, {"eleito2024": eleito}, ("eleito2024",))
    foto, g = None, None
    for c, b in candidatos:
        if c and b and _mesma_pessoa(m, c):
            foto, g = b.get("foto"), c["genero"]
            break
    d = {"id": pid, "nome": m.get("nome"), "nomeCivil": m.get("nomeCivil"), "partido": m.get("partido"),
         "genero": m.get("genero") or g, "foto": m.get("foto") or foto, "desde": m.get("desde"),
         "comoAssumiu": m.get("comoAssumiu")}
    d.update(_textos_manual(m))
    d.update({"fontes": _fontes_manual(m), "eleito2024": eleito})
    return limpar(d, manter=CAMPOS_PESSOA + ("desde", "comoAssumiu", "eleito2024"))


def pessoa_executivo_estadual(uf: str, papel: str, eleito22: dict | None, outro22: dict | None,
                              man: dict, bloco22: dict | None, bloco_outro22: dict | None, ano: int = 2022) -> dict:
    """Governador(a) ou vice hoje. papel = 'governador' | 'vice'. ano = eleição do mandato em curso (as chaves
    "eleito<ano>" e "sq<ano>" levam o ano: o site sabe de qual eleição é a ficha)."""
    pid = f"{'gov' if papel == 'governador' else 'vgov'}-{uf}"
    k_el, k_sq = f"eleito{ano}", f"sq{ano}"
    m = man.get(papel)
    if not isinstance(m, dict) or not m:
        # sem pesquisa à mão para este cargo: mostra quem foi eleito, com "aConfirmar"
        if not eleito22:
            return {"id": pid, "aConfirmar": True, k_el: None, "eleicao2026": None}
        b = bloco22
        out = {"id": pid}
        out.update({k: b[k] for k in CAMPOS_PESSOA})
        out.update({"aConfirmar": True, k_sq: eleito22["sq"], "fontes": b["fontes"], k_el: bloco22,
                    "eleicao2026": None})
        return out
    if m.get("vago") or chave_nome(m.get("nome") or "") in ("VAGO", "CARGO VAGO") or not (m.get("nome") or m.get("nomeCivil")):
        return _vago_manual(pid, m, {k_el: bloco22}, (k_el,))
    # quem está no cargo é o eleito de 2022 para este cargo, o eleito para o outro cargo (vice que assumiu) ou outra pessoa
    sq, foto, g = None, None, None
    for c, b in ((eleito22, bloco22), (outro22, bloco_outro22)):
        if c and _mesma_pessoa(m, c):
            sq, foto, g = c["sq"], b["foto"], c["genero"]
            break
    d = {"id": pid, "nome": m.get("nome"), "nomeCivil": m.get("nomeCivil"), "partido": m.get("partido"),
         "genero": m.get("genero") or g, "foto": m.get("foto") or foto, "desde": m.get("desde"),
         "comoAssumiu": m.get("comoAssumiu")}
    d.update(_textos_manual(m))
    d.update({"nascimento": m.get("nascimento"), k_sq: sq, "fontes": _fontes_manual(m), k_el: bloco22,
              "eleicao2026": None})
    return limpar(d, manter=CAMPOS_PESSOA + ("desde", "comoAssumiu", k_el, "eleicao2026"))


def _fontes_manual(m: dict | None) -> list | None:
    if not m:
        return None
    f = m.get("fontes") or m.get("fonte")
    return f if isinstance(f, list) else [f] if f else None


def _mesma_pessoa(m: dict, c: dict) -> bool:
    """A pessoa do arquivo manual é o eleito de 2022 `c`? (comparação só entre governador e vice do mesmo estado)"""
    nasc = (m.get("nascimento") or "")[:10]
    if nasc and c["nasc"] and nasc != c["nasc"]:
        return False
    civil = chave_nome(m.get("nomeCivil") or "")
    if civil and civil in (chave_nome(c["nome"]), chave_nome(c["civil"])):
        return True
    return bool(m.get("nome")) and chave_nome(m["nome"]) == chave_nome(c["urna"])


def chaves_executivo_estadual(p: dict, b22: Base) -> tuple:
    """(cpf, nome civil, nascimento) de quem está no cargo, para casar com 2026."""
    if p.get(f"sq{b22.ano}"):
        c = b22.linha(p[f"sq{b22.ano}"])
        if c:
            return c["cpf"], c["nome"], c["nasc"]
    if p.get("nomeCivil") and p.get("nascimento"):
        return None, p["nomeCivil"], p["nascimento"][:10]
    return None, None, None


def aplicar_2026_estado(est: dict, b22: Base, b26: Base2026) -> None:
    """Selos "Eleito/Reeleito em 2026": só até a posse de quem foi eleito em 2026 (governador: 6/1/2027; deputados: posse
    da Assembleia). Depois, quem aparece já é quem foi eleito, e o selo sai."""
    gov_antes = antes_da_posse("governador", 2026)
    dest_antes = antes_da_posse("deputado_estadual", 2026, uf=est["uf"])
    for papel, cargo in (("governador", "GOVERNADOR"), ("vice", "VICE-GOVERNADOR")):
        p = est.get(papel) or {}
        if not p or p.get("vago"):
            continue
        if not gov_antes:
            p["eleicao2026"] = None
            continue
        cpf, nome, nasc = chaves_executivo_estadual(p, b22)
        if cpf or (nome and nasc):
            p["eleicao2026"] = b26.situacao(cpf, nome, nasc, cargo, p.get("genero"))
            if not p.get("foto"):
                p["foto"] = b26.foto(cpf, nome, nasc)
        else:
            p["eleicao2026"] = None
    for m in est["deputadosEstaduais"]["membros"]:
        c = b22.linha(m["id"].rsplit("-", 1)[1]) if dest_antes else None
        m["eleicao2026"] = b26.situacao(c["cpf"], c["nome"], c["nasc"], c["cargo"], m.get("genero")) if c else None


def montar_estado(uf: str, b22: Base, vot22: dict, man: dict, fed: list[dict], n_mun: int,
                  bdest: Base | None = None, votdest: dict | None = None) -> dict:
    """b22/vot22: eleição do governador em exercício; bdest/votdest: eleição da legislatura estadual em curso (é a mesma,
    menos entre a posse do governador, em janeiro, e a da Assembleia, em fevereiro)."""
    bdest, votdest = bdest or b22, votdest or vot22
    ag, ad = b22.ano, bdest.ano
    rows = [c for c in b22.rows if c["uf"] == uf]
    gov22 = eleito_exec(rows, "GOVERNADOR", ORDINARIAS[ag])
    vice22 = eleito_exec(rows, "VICE-GOVERNADOR", ORDINARIAS[ag])
    if gov22 and vice22 and gov22["turno"] != vice22["turno"]:
        log(f"  [aviso] {uf}: governador e vice eleitos em turnos diferentes?")
    bg = bloco_eleito_exec(gov22, gov22, vot22, b22.data, ag, uf) if gov22 else None
    bv = bloco_eleito_exec(vice22, gov22, vot22, b22.data, ag, uf) if vice22 else None
    m = man.get(uf) or {}
    governador = pessoa_executivo_estadual(uf, "governador", gov22, vice22, m, bg, bv, ag)
    vice = pessoa_executivo_estadual(uf, "vice", vice22, gov22, m, bv, bg, ag)

    cargo_leg = "DEPUTADO DISTRITAL" if uf == "DF" else "DEPUTADO ESTADUAL"
    membros = []
    for c in (x for x in bdest.rows if x["uf"] == uf):
        if c["cargo"] != cargo_leg or c["el"] not in ORDINARIAS[ad] or not eleito(c["sit"]):
            continue
        membros.append({
            "id": f"dest-{uf}-{c['sq']}", "nome": nome_tse(c["urna"]), "nomeCivil": nome_tse(c["civil"]),
            "partido": c["partido"], "foto": url_foto(ad, c["sq"], uf), "genero": c["genero"],
            "votos": votdest["votos"].get(f"{c['sq']}|1"), f"situacao{ad}": sit_txt(c["sit"], c["genero"]), "eleicao2026": None,
        })
    membros.sort(key=lambda x: chave_ord(x["nome"], x["id"]))
    casa = "Câmara Legislativa do DF" if uf == "DF" else "Assembleia Legislativa"
    est = {
        "uf": uf, "nome": ibge.estados()[uf], "capital": ibge.capital(uf), "municipios": n_mun,
        "governador": governador, "vice": vice, "eleicaoGoverno": ag,
        "senadores": [f["id"] for f in sorted((f for f in fed if f["tipo"] == "sen" and f["uf"] == uf), key=lambda f: chave_ord(f["nome"], f["id"]))],
        "deputadosFederais": [f["id"] for f in sorted((f for f in fed if f["tipo"] == "dep" and f["uf"] == uf), key=lambda f: chave_ord(f["nome"], f["id"]))],
        "deputadosEstaduais": {
            "total": len(membros), "casa": casa, "eleicao": ad, "aviso": (AVISO_DIST if uf == "DF" else AVISO_DEST).format(ano=ad),
            "aviso_en": (AVISO_DIST_EN if uf == "DF" else AVISO_DEST_EN).format(ano=ad),
            "fonte": fonte_resultados(ad, votdest["data"], f"Dados Abertos: eleitos para {'deputado distrital' if uf == 'DF' else 'deputado estadual'} em {ad} ({uf}) e votos"),
            "membros": membros,
        },
        "fonteMunicipios": ibge.fonte_ibge(),
        "atualizado": hoje(),
    }
    if uf == "DF":
        est["aviso"] = ("O Distrito Federal não é dividido em municípios: não tem prefeito nem vereadores. "
                        "O governador e os 24 deputados distritais cuidam do DF todo.")
        est["aviso_en"] = ("The Federal District is not divided into municipalities: it has no mayor and no city "
                           "councilors. The governor and the 24 district deputies take care of the whole Federal District.")
    elif uf == "PE":
        est["aviso"] = "Fernando de Noronha é um distrito estadual de Pernambuco: não tem prefeito nem vereadores."
        est["aviso_en"] = ("Fernando de Noronha is a state district of Pernambuco: it has no mayor and no city "
                           "councilors.")
    return est


# ---------------------------------------------------------------- cidades (2024)
def ler_2024(chaves_fed: set) -> tuple:
    """Linhas de prefeito, vice e vereador de 2024 (inclui eleições suplementares de 2025/2026)."""
    rows, ues, fed24, data = [], {}, collections.defaultdict(list), None
    for r in ler_csv(zip_tse("consulta_cand", 2024)):
        data = data or data_iso(r["DT_GERACAO"])
        ues[r["SG_UE"]] = (r["SG_UF"], r["NM_UE"])
        cargo, sit, el = r["DS_CARGO"], r["DS_SIT_TOT_TURNO"], r["CD_ELEICAO"]
        if chaves_fed:
            nn = (chave_nome(r["NM_CANDIDATO"]), data_iso(r["DT_NASCIMENTO"]))
            if nn in chaves_fed:
                fed24[nn].append(cand(r, 2024))
        if cargo in ("PREFEITO", "VICE-PREFEITO") or (
                cargo == "VEREADOR" and (sit.startswith("ELEITO") or sit.startswith("#NULO") or el not in ORDINARIAS[2024])):
            rows.append(cand(r, 2024))
    return rows, ues, fed24, data


def _pessoa_cidade(c: dict, pid: str, titular: dict | None, vot24: dict, data: str, supl_ids: dict, aconf: bool,
                   sit_divulga: str | None = None) -> dict:
    id_el = None if c["el"] in ORDINARIAS[2024] else supl_ids.get((c["ue"], c["dt"]))
    b = bloco_eleito_exec(c, titular, vot24, data, 2024, c["ue"], id_el)
    if c["el"] not in ORDINARIAS[2024] and not id_el:
        b["foto"] = None  # sem o código da eleição suplementar não dá para montar a URL da foto
        b["fontes"] = [fonte_candidatos(2024, data, f"Dados Abertos: candidaturas de 2024 e eleições suplementares ({c['nm_ue']})"),
                       b["fontes"][1]]
    if sit_divulga:
        a = "a" if c["genero"] == "F" else "o"
        b["situacao"] = f"Eleit{a} em 2024 (segundo o DivulgaCandContas)"
    out = {"id": pid}
    out.update(b)
    if aconf:
        out["aConfirmar"] = True
    return out


def montar_cidade(ue: str, cod: str, nome: str, uf: str, rows: list[dict], vot24: dict, data: str, supl_ids: dict,
                  contagem: collections.Counter, manual: dict | None = None) -> dict:
    hoje_iso = hoje()
    ords = [c for c in rows if c["el"] in ORDINARIAS[2024]]
    supl = collections.defaultdict(list)
    for c in rows:
        if c["el"] not in ORDINARIAS[2024]:
            supl[c["el"]].append(c)
    avisos = [(AVISO_PREF, AVISO_PREF_EN)]  # (português, inglês)
    aconf = False
    # prefeito e vice: eleição de 2024 ou a eleição suplementar mais recente com resultado
    pref = eleito_exec(ords, "PREFEITO", ORDINARIAS[2024])
    vice = eleito_exec(ords, "VICE-PREFEITO", ORDINARIAS[2024])
    origem = f"2024-{pref['turno']}t" if pref else None
    aplicada = None
    for el, rs in sorted(supl.items(), key=lambda kv: kv[1][0]["dt"]):
        p = eleito_exec(rs, "PREFEITO", {el})
        if p:
            pref, vice, aplicada, origem = p, eleito_exec(rs, "VICE-PREFEITO", {el}), rs[0]["dt"], "suplementar"
    if aplicada:
        avisos.append((f"Prefeito(a) e vice escolhidos na eleição suplementar de {data_br(aplicada)}.",
                       f"Mayor and vice mayor chosen in the special election held on {data_en(aplicada)}."))
    # eleições suplementares para prefeito ainda sem resultado (marcadas para o futuro ou sem resultado publicado)
    pendentes = sorted(rs[0]["dt"] for el, rs in supl.items()
                       if any(c["cargo"] == "PREFEITO" for c in rs) and not eleito_exec(rs, "PREFEITO", {el})
                       and not (aplicada and rs[0]["dt"] <= aplicada))
    sit_div = None
    if not pref:
        # sem resultado nos dados abertos: confere no DivulgaCandContas (TSE), se não houver eleição suplementar
        ep, ev = [], []
        if not pendentes:
            tp = divulga_totalizacao_2024(ue, 11) or {}
            tv = divulga_totalizacao_2024(ue, 12) or {}
            ep = [c for c in ords if c["cargo"] == "PREFEITO" and tp.get(c["sq"], "").startswith("ELEITO")]
            ev = [c for c in ords if c["cargo"] == "VICE-PREFEITO" and tv.get(c["sq"], "").startswith("ELEITO")]
        if len(ep) == 1:
            pref, vice, origem, sit_div, aconf = ep[0], (ev[0] if len(ev) == 1 else None), "divulga", "ELEITO", True
            avisos.append(("Nos dados abertos do TSE, o resultado de 2024 desta cidade aparece sem definição "
                           "(pode estar sendo recalculado). O nome veio do DivulgaCandContas, do TSE.",
                           "In the TSE open data, this city's 2024 result shows as undefined (it may be being "
                           "recalculated). The name comes from DivulgaCandContas, the TSE candidate website."))
        else:
            avisos.append(("O TSE não mostra prefeito(a) eleito(a) em 2024 nesta cidade: a eleição pode ter sido "
                           "anulada ou ainda estar em julgamento na Justiça Eleitoral.",
                           "The TSE shows no mayor elected in 2024 in this city: the election may have been "
                           "annulled or may still be under review by the Electoral Courts."))
    for dt in pendentes:
        aconf = True
        if dt > hoje_iso:
            avisos.append((f"Está marcada uma eleição suplementar para prefeito em {data_br(dt)}. Até lá, "
                           + ("quem está no cargo pode ser outra pessoa." if pref else
                              "a cidade é governada de forma temporária (em geral, por quem preside a Câmara Municipal)."),
                           f"A special election for mayor is scheduled for {data_en(dt)}. Until then, "
                           + ("the person in office may be someone else." if pref else
                              "the city is governed temporarily (usually by the president of the City Council).")))
        else:
            avisos.append((f"Uma eleição suplementar para prefeito foi marcada para {data_br(dt)}, mas o resultado não "
                           "aparece nos dados abertos do TSE (ela pode ter sido suspensa ou adiada). "
                           + ("Quem está no cargo pode ser outra pessoa." if pref else ""),
                           f"A special election for mayor was scheduled for {data_en(dt)}, but the result does not "
                           "appear in the TSE open data (it may have been suspended or postponed). "
                           + ("The person in office may be someone else." if pref else "")))
    contagem[origem or "sem"] += 1

    prefeito = _pessoa_cidade(pref, f"pref-{cod}", pref, vot24, data, supl_ids, aconf, sit_div) if pref else None
    vice_o = _pessoa_cidade(vice, f"vpref-{cod}", pref, vot24, data, supl_ids, aconf, sit_div) if vice else None
    if manual:
        cands = [(pref, prefeito), (vice, vice_o)]
        prefeito, vice_o = (aplicar_manual_cidade(f"pref-{cod}", manual.get("prefeito"), prefeito, cands),
                            aplicar_manual_cidade(f"vpref-{cod}", manual.get("vice"), vice_o, cands[::-1]))
        avisos = [("Quem está no cargo hoje foi conferido à mão, com as fontes indicadas.",
                   "Who is in office today was checked by hand, using the sources shown.")]
        contagem["manual"] += 1

    # vereadores: 2024 + eleições suplementares de vereador
    ver = [c for c in ords if c["cargo"] == "VEREADOR" and eleito(c["sit"])]
    aviso_ver = [(AVISO_VER, AVISO_VER_EN)]
    for el, rs in sorted(supl.items(), key=lambda kv: kv[1][0]["dt"]):
        ev = [c for c in rs if c["cargo"] == "VEREADOR" and eleito(c["sit"])]
        if not ev:
            continue
        if not ver or len(ev) >= len(ver):
            ver = ev
            aviso_ver.append((f"Estes vereadores foram eleitos na eleição suplementar de {data_br(rs[0]['dt'])}.",
                              f"These councilors were elected in the special election held on {data_en(rs[0]['dt'])}."))
        else:
            ver = ver + ev
            nomes = ", ".join(f"{nome_tse(c['urna'])} ({c['partido']})" for c in ev)
            quem = f"foi eleit{'a' if ev[0]['genero'] == 'F' else 'o'}" if len(ev) == 1 else "foram eleitos"
            quem_en = "was elected" if len(ev) == 1 else "were elected"
            aviso_ver.append((f"Em {data_br(rs[0]['dt'])} houve eleição suplementar para vereador: {nomes} {quem}. "
                              "Quem saiu da Câmara não aparece nos dados do TSE, por isso a lista pode ter um nome a mais.",
                              f"On {data_en(rs[0]['dt'])} there was a special election for city councilor: {nomes} "
                              f"{quem_en}. People who left the City Council do not appear in the TSE data, so the "
                              "list may have one extra name."))
    origem_ver = "csv"
    if not ver:
        tv = divulga_totalizacao_2024(ue, 13) or {}
        ver = [dict(c, sit=tv[c["sq"]]) for c in ords if c["cargo"] == "VEREADOR" and tv.get(c["sq"], "").startswith("ELEITO")]
        origem_ver = "divulga" if ver else "sem"
        if ver:
            aviso_ver.append(("Nos dados abertos do TSE, o resultado de 2024 desta cidade aparece sem definição "
                              "(pode estar sendo recalculado). Os nomes vieram do DivulgaCandContas, do TSE.",
                              "In the TSE open data, this city's 2024 result shows as undefined (it may be being "
                              "recalculated). The names come from DivulgaCandContas, the TSE candidate website."))
        else:
            aviso_ver.append(("O TSE ainda não mostra os vereadores eleitos em 2024 nesta cidade.",
                              "The TSE does not yet show the city councilors elected in 2024 in this city."))
    contagem["ver-" + origem_ver] += 1
    membros = []
    for c in ver:
        id_el = None if c["el"] in ORDINARIAS[2024] else supl_ids.get((c["ue"], c["dt"]))
        tem_foto = c["el"] in ORDINARIAS[2024] or id_el
        sit = sit_txt(c["sit"], c["genero"])
        if c["el"] not in ORDINARIAS[2024]:
            sit += f" na eleição suplementar de {data_br(c['dt'])}"
        membros.append({
            "id": f"ver-{cod}-{c['sq']}", "nome": nome_tse(c["urna"]), "nomeCivil": nome_tse(c["civil"]),
            "partido": c["partido"], "foto": url_foto(2024, c["sq"], ue, id_el) if tem_foto else None,
            "genero": c["genero"], "votos": vot24["votos"].get(f"{c['sq']}|{c['turno']}"), "situacao": sit,
        })
    membros.sort(key=lambda x: chave_ord(x["nome"], x["id"]))
    fonte_ver = fonte_resultados(2024, vot24["data"], f"Dados Abertos: vereadores eleitos em 2024 em {nome} ({uf}) e votos")
    if origem_ver == "divulga":
        fonte_ver = fonte("TSE", f"DivulgaCandContas: candidaturas a vereador em {nome} ({uf}), 2024",
                          f"{DIVULGA}/#/candidato/{REGIAO[uf]}/{uf}/{ID_DIVULGA[2024]}", hoje())
    cid = {
        "ibge": cod, "nome": nome, "uf": uf, "prefeito": prefeito, "vice": vice_o,
        "aviso": " ".join(a[0].strip() for a in avisos if a[0].strip()),
        "aviso_en": " ".join(a[1].strip() for a in avisos if a[1].strip()),
        "vereadores": {"total": len(membros), "aviso": " ".join(a[0] for a in aviso_ver),
                       "aviso_en": " ".join(a[1] for a in aviso_ver), "fonte": fonte_ver, "membros": membros},
        "atualizado": hoje(),
    }
    return cid


# ---------------------------------------------------------------- busca
def item_busca(pid: str, nome: str, cargo: str, g, uf, partido, cidade=None) -> list:
    if partido and re.sub(r"\s+", "", partido.upper()) in ("S/PARTIDO", "SEMPARTIDO"):
        partido = "Sem partido"  # o mesmo texto das listas da Câmara e do Senado
    return [pid, nome, cargo_txt(cargo, g), uf, partido, cidade]


# ---------------------------------------------------------------- principal
def tamanho(caminhos) -> int:
    tot = 0
    for p in caminhos:
        p = Path(p)
        if p.is_file():
            tot += p.stat().st_size
        elif p.is_dir():
            tot += sum(f.stat().st_size for f in p.rglob("*.json"))
    return tot


def _sem_datas(o):
    """Tira "atualizado" e a "data" das fontes, para comparar só o conteúdo."""
    if isinstance(o, dict):
        return {k: _sem_datas(v) for k, v in o.items() if not (k == "atualizado" or (k == "data" and "veiculo" in o))}
    if isinstance(o, list):
        return [_sem_datas(x) for x in o]
    return o


def salvar(caminho: Path, obj) -> bool:
    """Só grava se algo além das datas mudou (os arquivos do TSE são gerados de novo todo dia)."""
    antigo = ler_json(caminho)
    if antigo is not None and _sem_datas(antigo) == _sem_datas(obj):
        return False
    return salvar_json(caminho, obj)


def carregar_federais(b18: Base, b22: Base, bpres: Base | None = None) -> list[dict]:
    log("Federais: quem está no mandato hoje (Câmara, Senado, executivo)...")
    fed = deputados_atuais() + senadores_atuais() + executivo_atual(bpres or b22)
    casar_federais(fed, b18, b22)
    sem = [f["id"] for f in fed if not f["tse"]]
    log(f"  {sum(f['tipo'] == 'dep' for f in fed)} deputados, {sum(f['tipo'] == 'sen' for f in fed)} senadores, "
        f"{sum(f['tipo'] in ('pres', 'vp') for f in fed)} presidente/vice; sem candidatura achada no TSE: {sem or 'nenhum'}")
    return fed


def so_2026(b22: Base, b26: Base2026, fed: list[dict]) -> None:
    caminho = SAIDA_TSE / "federais.json"
    fj = ler_json(caminho, {}) or {}
    for f in fed:
        d = fj.setdefault(f["id"], {"eleicao": None, "eleicao2026": None, "bens": None})
        d["eleicao2026"] = (b26.situacao(f["cpf"], f["nomeCivil"], f["nasc"], f["cargo"], f["genero"])
                            if antes_da_posse(f["tipo"], 2026) else None)
    salvar(caminho, dict(sorted(fj.items())))
    n = 0
    for uf in UFS:
        p = ESTADOS / f"{uf}.json"
        est = ler_json(p)
        if not est:
            log(f"  [aviso] {p} não existe: rode o modo completo")
            continue
        aplicar_2026_estado(est, b22, b26)
        n += salvar(p, est)
    log(f"eleicao2026 atualizado: federais.json + {n} estados mudaram")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--so-2026", action="store_true", help="só atualiza eleicao2026")
    ap.add_argument("--renovar", action="store_true", help="baixa de novo os arquivos do TSE")
    args = ap.parse_args()
    if args.renovar:
        for k in IDADE_H:
            IDADE_H[k] = 0
    t0 = time.time()
    for p in (CACHE_TSE, SAIDA_TSE, ESTADOS, CIDADES):
        p.mkdir(parents=True, exist_ok=True)

    # cada cargo usa a eleição do mandato em curso hoje (scripts/mandatos.py): até as posses de 2027, a de 2022
    a_cong = vigente("deputado_federal")["eleicao"]      # Câmara e Senado (posse em 1º/2)
    a_pres = vigente("presidente")["eleicao"]            # presidente e vice (posse em 5/1 a partir de 2027)
    a_gov = vigente("governador")["eleicao"]             # governador e vice (posse em 6/1 a partir de 2027)
    a_dest = {uf: vigente("deputado_estadual", uf=uf)["eleicao"] for uf in UFS}
    anos = sorted({a_cong - 4, a_cong, a_pres, a_gov} | set(a_dest.values()))
    log(f"TSE: candidaturas de {', '.join(map(str, anos))} e 2026...")
    bs = {a: Base(a) for a in anos}
    b22, b18, b26 = bs[a_cong], bs[a_cong - 4], Base2026()
    fed = carregar_federais(b18, b22, bs[a_pres])
    if args.so_2026:
        so_2026(b22, b26, fed)
        log(f"Pronto em {time.time() - t0:.0f}s")
        return

    log("TSE: candidaturas de 2024 (prefeitos, vices, vereadores e eleições suplementares)...")
    chaves_fed = {(chave_nome(f["nomeCivil"] or ""), f["nasc"]) for f in fed if f["nomeCivil"] and f["nasc"]}
    rows24, ues24, fed24, data24 = ler_2024(chaves_fed)
    log("TSE: votos (votação nominal por município e zona)...")
    vot = {ano: votos_ou_nada(ano) for ano in sorted(set(anos) | {2024})}
    bens_cache = {}

    def bens_ano(ano):
        if ano not in bens_cache:
            bens_cache[ano] = bens(ano)
        return bens_cache[ano]

    # ---- federais
    bases = bs
    federais = {}
    for f in fed:
        federais[f["id"]] = {
            "eleicao": bloco_eleicao_federal(f, bases, vot),
            # selo "Eleito/Reeleito em 2026": só até a posse de quem foi eleito em 2026 naquele cargo
            "eleicao2026": (b26.situacao(f["cpf"], f["nomeCivil"], f["nasc"], f["cargo"], f["genero"])
                            if antes_da_posse(f["tipo"], 2026) else None),
            "bens": bloco_bens(f, b26, b22, b18, fed24, bens_ano),
            "ficha": bloco_ficha(f, b26, b22, b18, fed24),
        }
    salvar(SAIDA_TSE / "federais.json", dict(sorted(federais.items())))
    log(f"dados/tse/federais.json: {len(federais)} pessoas")

    # ---- estados
    man = manual_governadores(a_gov)  # só vale se a pesquisa à mão for do mandato em curso
    log(f"Governadores (eleição de {a_gov}): {'dados/manual/governadores.json com ' + str(len(man)) + ' estados' if man else 'sem pesquisa à mão deste mandato (aConfirmar)'}")
    municipios = ibge.municipios()
    n_mun = collections.Counter(m["uf"] for m in municipios.values())
    estados = {}
    for uf in UFS:
        est = montar_estado(uf, bs[a_gov], vot[a_gov], man, fed, n_mun.get(uf, 0), bs[a_dest[uf]], vot[a_dest[uf]])
        aplicar_2026_estado(est, bs[a_gov], b26)
        estados[uf] = est
        salvar(ESTADOS / f"{uf}.json", est)
    total_dest = sum(e["deputadosEstaduais"]["total"] for e in estados.values())
    log(f"dados/estados: {len(estados)} estados, {total_dest} deputados estaduais/distritais")

    # ---- cidades
    log("Cidades: TSE x IBGE...")
    mapa = ibge.casar_tse(ues24)
    supl_ufs = {c["uf"] for c in rows24 if c["el"] not in ORDINARIAS[2024]}
    supl_ids = ids_suplementares_2024(supl_ufs)
    por_ue = collections.defaultdict(list)
    for c in rows24:
        por_ue[c["ue"]].append(c)
    contagem = collections.Counter()
    listas = collections.defaultdict(list)
    cidades = {}
    man_pref = manual_prefeitos()
    if man_pref:
        log(f"  dados/manual/prefeitos.json: {len(man_pref)} cidades")
    for ue, (uf, _) in sorted(ues24.items()):
        cod = mapa[ue]
        nome = municipios[cod]["nome"]
        cid = montar_cidade(ue, cod, nome, uf, por_ue.get(ue, []), vot[2024], data24, supl_ids, contagem, man_pref.get(cod))
        cidades[cod] = cid
        salvar(CIDADES / uf / f"{cod}.json", cid)
        p = cid["prefeito"]
        listas[uf].append({"ibge": cod, "nome": nome,
                           "prefeito": f"{p['nome']} ({p['partido']})" if p and p.get("nome") else None})
    for uf in UFS:
        salvar(CIDADES / f"{uf}.json", sorted(listas.get(uf, []), key=lambda x: chave_ord(x["nome"], x["ibge"])))
    # arquivos de cidades que não existem mais (ex.: código que mudou)
    for f in CIDADES.glob("*/*.json"):
        if f.stem not in cidades:
            f.unlink()
    n_pref = sum(1 for c in cidades.values() if c["prefeito"] and c["prefeito"].get("nome"))
    n_ver = sum(c["vereadores"]["total"] for c in cidades.values())
    log(f"dados/cidades: {len(cidades)} cidades, {n_pref} prefeitos, {n_ver} vereadores; origem: {dict(contagem)}")

    # ---- busca
    busca = []
    for f in fed:
        busca.append(item_busca(f["id"], f["nome"], f["cargo"], f["genero"], f["uf"], f["partido"]))
    for uf, est in estados.items():
        for papel, cargo in (("governador", "GOVERNADOR"), ("vice", "VICE-GOVERNADOR")):
            p = est[papel]
            if p.get("nome"):
                busca.append(item_busca(p["id"], p["nome"], cargo, p.get("genero"), uf, p.get("partido")))
        cargo_leg = "DEPUTADO DISTRITAL" if uf == "DF" else "DEPUTADO ESTADUAL"
        for m in est["deputadosEstaduais"]["membros"]:
            busca.append(item_busca(m["id"], m["nome"], cargo_leg, m["genero"], uf, m["partido"]))
    for cod, cid in cidades.items():
        for papel, cargo in (("prefeito", "PREFEITO"), ("vice", "VICE-PREFEITO")):
            p = cid[papel]
            if p and p.get("nome"):
                busca.append(item_busca(p["id"], p["nome"], cargo, p.get("genero"), cid["uf"], p.get("partido"), cid["nome"]))
    busca.sort(key=lambda x: (chave_nome(x[1] or ""), x[0]))
    salvar(DADOS / "busca.json", busca)
    log(f"dados/busca.json: {len(busca)} pessoas")

    # ---- resumo
    sit26 = collections.Counter(d["eleicao2026"]["situacao"] for d in federais.values() if d["eleicao2026"])
    log(f"eleicao2026 (federais): {dict(sit26)}")
    tam = {
        "estados": tamanho([ESTADOS]), "cidades": tamanho([CIDADES]), "busca": tamanho([DADOS / "busca.json"]),
        "tse": tamanho([SAIDA_TSE]),
    }
    log("Tamanho: " + ", ".join(f"{k} {v / 1e6:.1f} MB" for k, v in tam.items()) + f" (total {sum(tam.values()) / 1e6:.1f} MB)")
    log(f"Pronto em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
