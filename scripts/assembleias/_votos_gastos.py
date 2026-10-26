"""Votações nominais e gastos do mandato dos deputados estaduais, comum às três frentes das Assembleias (fase 6).

Mesmo formato e mesma régua dos perfis federais e das Casas que já tinham votações (AM, RO, GO, PA) e gastos (MG, SP, SC,
GO, MS); ver o README, "dados/pessoas/<id>.json".

- votacoes = {"escopo", "escopo_en", "resumo": {"total", "Sim", "Não", "Abstenção", "Obstrução", "Outro"}, "fonte", "lista"}.
  As Casas desta fase guardam as votações dentro do próprio perfil (campo "lista", que o js/pessoa.js já lê), sem catálogo
  em dados/votacoes/: nenhum arquivo novo fora de dados/assembleias/ e dados/pessoas/ (limite de arquivos da Vercel).
  Cada item (item_voto): {"id": "<sigla>-vot:<id oficial>", "voto", "data", "proposta", "propostaId", "descricao",
  "resultado", "placar", "url"}; "voto" = Sim | Não | Abstenção | Obstrução | um código de ausência que o D.voto do
  js/traducoes.js conhece (NR = não votou). Só entram votações com o voto de cada deputado (nominais), do Plenário, desde o
  começo da legislatura em curso; quem não registrou voto não ganha item (como na Câmara dos Deputados).
- gastos = bloco_gastos (de _sse_comum.py): {"nome", "nome_en", "ano", "total", "porTipo", "mandatoTotal", "desde",
  "meses", "fonte"}; "porTipo" usa os tipos de despesa da própria Casa (vazio quando a Casa não classifica).
- Primeira carga (cache vazio, como no robô do GitHub): enquanto as votações ou os gastos de uma Casa não foram lidos por
  inteiro, cada perfil fica com o bloco publicado antes (aplicar(..., None) / de_antes): nada pela metade no site.
"""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET

import regional
from comum import DADOS, chave_nome, ler_json, log, sem_acento
from mandatos import mes_ano

from ._sse_comum import bloco_gastos  # noqa: F401  (re-exportado: o mesmo formato para todas as Casas)

VOTOS_RESUMO = ("Sim", "Não", "Abstenção", "Obstrução")


# ---------------------------------------------------------------- votações
def placar(votos) -> dict:
    """Contagem dos votos de uma votação (lista de "Sim", "Não"...), no formato do README."""
    p = {"Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
    for v in votos:
        p[v if v in VOTOS_RESUMO else "Outro"] += 1
    p["total"] = sum(p.values())
    return p


def item_voto(chave: str, voto: str, data: str | None, proposta: str | None, descricao: str | None, resultado: str | None,
              placar_: dict | None, url: str | None, proposta_id: str | None = None) -> dict:
    x = {"id": chave, "voto": voto, "data": data, "proposta": proposta, "propostaId": proposta_id,
         "descricao": re.sub(r"\s+", " ", descricao).strip() if descricao else None, "resultado": resultado,
         "placar": placar_, "url": url}
    return {k: v for k, v in x.items() if v is not None}


def bloco_votacoes(itens: list[dict], escopo: str, escopo_en: str, fonte_v: dict) -> dict | None:
    """O bloco "votacoes" de uma pessoa, com a lista da mais nova para a mais antiga."""
    if not itens:
        return None
    lista = sorted(itens, key=lambda x: (x.get("data") or "", x["id"]), reverse=True)
    resumo = {"total": len(lista), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
    for x in lista:
        resumo[x["voto"] if x["voto"] in resumo else "Outro"] += 1
    return {"escopo": escopo, "escopo_en": escopo_en, "resumo": resumo, "fonte": fonte_v, "lista": lista}


def escopo_votos(sigla: str, desde_pt: str = "1º/2/2023", desde_en: str = "February 1, 2023", extra: tuple[str, str] | None = None,
                 artigo: str = "da") -> tuple[str, str]:
    pt = f"Votações nominais (com o voto de cada deputado) no Plenário {artigo} {sigla} desde {desde_pt}"
    en = f"Roll-call votes (where each member's vote is recorded) in the full {sigla} since {desde_en}"
    if extra:
        pt, en = f"{pt}. {extra[0].rstrip('.')}.", f"{en}. {extra[1].rstrip('.')}."
    return pt, en


VETO_SIM_MANTEM = ("Nas votações de vetos do governador, quem vota “sim” mantém o veto e quem vota “não” vota para derrubá-lo",
                   "In votes on the governor's vetoes, a “yes” vote keeps the veto and a “no” vote is a vote to overturn it")
VETO_SIM_DERRUBA = ("Nas votações de vetos do governador, quem vota “sim” vota para derrubar o veto e quem vota “não”, para "
                    "mantê-lo (o veto só cai com os votos da maioria absoluta dos deputados)",
                    "In votes on the governor's vetoes, a “yes” vote is a vote to overturn the veto and a “no” vote is a vote to "
                    "keep it (a veto is only overturned with the votes of an absolute majority of the members)")


def sentido_veto(votacoes: list[tuple[int, int, str | None]], cadeiras: int) -> tuple[str, str] | None:
    """O que quer dizer o "sim" nas votações de veto da Casa (cada Casa pergunta de um jeito: na ALRN e na Alesc, "sim"
    mantém; na ALPB, "sim" derruba). votacoes = [(votos sim, votos não, resultado oficial)] das votações de veto. Só diz
    quando o resultado de todas confirma um dos dois jeitos e descarta o outro: (a) "sim" mantém = veto derrubado sempre com
    mais "não" e veto mantido nunca com "não" da maioria absoluta; (b) "sim" derruba = veto derrubado sempre com mais "sim" e
    veto mantido nunca com "sim" da maioria absoluta. Só contam os resultados claros ("Mantido", "Rejeitado", "Derrubado");
    "Aprovado" num veto pode querer dizer as duas coisas e não conta. None se não há votação de veto ou se o resultado não
    decide."""
    maioria = cadeiras // 2 + 1
    vs = []
    for s, n, res in votacoes:
        t = sem_acento((res or "").lower())
        vs.append((s, n, "mantido" if re.match(r"mantid", t) else "caiu" if re.match(r"(rejeitad|derrubad)", t) else None))
    if not any(t for _, _, t in vs):
        return None
    a = all(not (t == "caiu" and not n > s) and not (t == "mantido" and n >= maioria) for s, n, t in vs)
    b = all(not (t == "caiu" and not s > n) and not (t == "mantido" and s >= maioria) for s, n, t in vs)
    return VETO_SIM_MANTEM if a and not b else VETO_SIM_DERRUBA if b and not a else None


def junta(extra: tuple[str, str] | None, mais: tuple[str, str] | None) -> tuple[str, str] | None:
    """Junta duas frases (pt, en) do escopo."""
    if not (extra and mais):
        return extra or mais
    return f"{extra[0].rstrip('.')}. {mais[0]}", f"{extra[1].rstrip('.')}. {mais[1]}"


def periodo_meses(datas: list[str]) -> tuple[str, str] | None:
    """['2023-02-09', '2024-11-27'] -> ('de fevereiro de 2023 a novembro de 2024', 'from February 2023 to November 2024')."""
    ds = sorted(d for d in datas if d)
    if not ds:
        return None
    a, b = mes_ano(ds[0]), mes_ano(ds[-1])
    if a == b:
        return f"em {a[0]}", f"in {a[1]}"
    return f"de {a[0]} a {b[0]}", f"from {a[1]} to {b[1]}"


# ---------------------------------------------------------------- perfis: o bloco de antes durante a primeira carga
def de_antes(pid: str, campo: str):
    return (ler_json(DADOS / "pessoas" / f"{pid}.json", {}) or {}).get(campo)


def aplicar(extras: dict[str, dict], blocos: dict[str, dict] | None, campo: str) -> bool:
    """Põe o bloco `campo` ("votacoes" ou "gastos") em cada perfil. blocos=None: a primeira carga não terminou; cada perfil
    fica com o bloco publicado antes (se houver). Devolve se algum perfil ficou com o bloco (para a cobertura da Casa)."""
    algum = False
    for pid, x in extras.items():
        b = blocos.get(pid) if blocos is not None else de_antes(pid, campo)
        if not b:
            x.pop(campo, None)
            continue
        x[campo] = b
        algum = True
        f = b.get("fonte")
        if f and f not in (x.get("fontes") or []):
            x.setdefault("fontes", []).append(f)
    return algum


# ---------------------------------------------------------------- nomes (quando a Casa não dá o id de cada deputado)
class Nomes:
    """Liga o nome escrito na planilha ou na página de votação (ex.: "AP. LUIZ HENRIQUE", "DEP AGENOR NETO") à pessoa da
    lista oficial de hoje. Mesma regra de GO e PA: as palavras do nome (sem títulos, acentos e "de/da/do") têm de bater
    (iguais, ou uma contida na outra com 2 palavras em comum, ou um nome de uma palavra só com 4+ letras), e só vale quando
    uma pessoa só bate. manual = {nome como a Casa escreve (qualquer caixa/acento): id da pessoa ou "-"} (conferido à
    mão). Quem não bate (quem saiu da Casa, por exemplo) fica em `sem`, para o log."""

    def __init__(self, membros: list[dict], manual: dict[str, str] | None = None, prefixo: str = r"^\s*dep(utad[oa])?\.?\s+",
                 aproximado: bool = False):
        """aproximado=True: quando nenhuma regra bate, aceita um erro de digitação ("CALUDIO PINHO" = "Cláudio Pinho"):
        nome inteiro com semelhança de 90% ou mais com uma só pessoa (e 5 pontos acima da segunda). Cada ligação assim
        vai para o log (`aproximados`), para conferir."""
        self.prefixo = re.compile(prefixo, re.I) if prefixo else None
        self.indice = [(m["id"], set(regional.palavras(m.get("nome"))), set(regional.palavras(m.get("nomeCivil")))) for m in membros]
        self.nomes_chave = [(m["id"], chave_nome(m.get("nome") or "")) for m in membros if m.get("nome")]
        self.manual = {chave_nome(k): v for k, v in (manual or {}).items()}
        self.aproximado = aproximado
        self.cache: dict[str, str | None] = {}
        self.sem: dict[str, int] = {}
        self.aproximados: dict[str, str] = {}

    def limpa(self, nome: str) -> str:
        n = re.sub(r"\s+", " ", nome or "").strip()
        return self.prefixo.sub("", n) if self.prefixo else n

    def quem(self, nome: str) -> str | None:
        k = chave_nome(self.limpa(nome))
        if k in self.manual:
            v = self.manual[k]
            return None if v == "-" else v
        if k not in self.cache:
            alvo = set(regional.palavras(self.limpa(nome).replace("ª", "a").replace("º", "o")))
            ach = set()
            for pid, p, c in self.indice:
                if not alvo:
                    break
                if p and (p == alvo or ((p <= alvo or alvo <= p) and len(p & alvo) >= 2)
                          or (len(p & alvo) == 1 and min(len(p), len(alvo)) == 1 and len(next(iter(p & alvo))) >= 4)):
                    ach.add(pid)
                elif c and alvo <= c and len(alvo) >= 2:
                    ach.add(pid)
            if not ach and self.aproximado and k:
                import difflib
                melhor: dict[str, float] = {}
                for pid, ch in self.nomes_chave:
                    melhor[pid] = max(melhor.get(pid, 0.0), difflib.SequenceMatcher(None, k, ch).ratio())
                notas = sorted(((s, pid) for pid, s in melhor.items()), reverse=True)
                if notas and notas[0][0] >= 0.9 and (len(notas) == 1 or notas[0][0] - notas[1][0] >= 0.05):
                    ach.add(notas[0][1])
                    self.aproximados[nome] = notas[0][1]
            self.cache[k] = ach.pop() if len(ach) == 1 else None
        if self.cache[k] is None:
            self.sem[nome] = self.sem.get(nome, 0) + 1
        return self.cache[k]

    def avisar(self, uf: str, o_que: str) -> None:
        if self.aproximados:
            log(f"  {uf} {o_que}: ligados por semelhança (erro de digitação na fonte): "
                f"{sorted(self.aproximados.items())[:15]}")
        if self.sem:
            nomes = sorted(self.sem)
            log(f"  {uf} {o_que}: nomes sem pessoa na lista de hoje (quem saiu ou grafia diferente): "
                f"{nomes[:15]}{'...' if len(nomes) > 15 else ''}")


# ---------------------------------------------------------------- números e planilhas (biblioteca padrão)
def valor_br(s) -> float:
    """'1.234,56' / 'R$ 1.234,56' / '1234.56' / 1234.56 -> 1234.56 (0.0 se vazio)."""
    if isinstance(s, (int, float)):
        return float(s)
    t = re.sub(r"[^\d,.\-]", "", str(s or ""))
    if not t:
        return 0.0
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return 0.0


_NS_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_linhas(b: bytes, aba: int = 0) -> list[list[str]]:
    """Linhas de uma planilha .xlsx (texto de cada célula; células vazias = ""), na posição certa de cada coluna."""
    z = zipfile.ZipFile(io.BytesIO(b))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_NS_X}si"):
            ss.append("".join(t.text or "" for t in si.iter(f"{_NS_X}t")))
    abas = sorted((n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
                  key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
    out = []
    for row in ET.fromstring(z.read(abas[aba])).iter(f"{_NS_X}row"):
        cel: dict[int, str] = {}
        for c in row.findall(f"{_NS_X}c"):
            v, t = c.find(f"{_NS_X}v"), c.get("t")
            if t == "s" and v is not None:
                txt = ss[int(v.text)]
            elif t == "inlineStr":
                txt = "".join(x.text or "" for x in c.iter(f"{_NS_X}t"))
            else:
                txt = v.text if v is not None and v.text is not None else ""
            cel[_col(c.get("r"))] = txt
        out.append([cel.get(k, "") for k in range(max(cel) + 1)] if cel else [])
    return out


_NS_T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_NS_O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_NS_TX = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def ods_linhas(b: bytes, aba: int = 0) -> list[list[str]]:
    """Linhas de uma planilha .ods (OpenDocument); números vêm do valor da célula (office:value), texto do parágrafo."""
    z = zipfile.ZipFile(io.BytesIO(b))
    tabelas = list(ET.fromstring(z.read("content.xml")).iter(f"{_NS_T}table"))
    out = []
    for row in tabelas[aba].iter(f"{_NS_T}table-row"):
        rep_l = min(int(row.get(f"{_NS_T}number-rows-repeated", "1")), 50)
        linha: list[str] = []
        for c in row:
            if c.tag not in (f"{_NS_T}table-cell", f"{_NS_T}covered-table-cell"):
                continue
            rep = min(int(c.get(f"{_NS_T}number-columns-repeated", "1")), 200)
            val = c.get(f"{_NS_O}value")
            txt = val if val is not None else "\n".join("".join(p.itertext()) for p in c.iter(f"{_NS_TX}p"))
            linha += [txt] * rep
        while linha and not linha[-1]:
            linha.pop()
        out += [linha] * rep_l if linha else [[]]
    while out and not out[-1]:
        out.pop()
    return out


def mes_br(txt: str | None) -> str | None:
    """'09/2026', 'SETEMBRO/2026', '2026-09-01' -> '2026-09'."""
    t = sem_acento(txt or "").lower().strip()
    m = re.match(r"(\d{4})-(\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"(\d{1,2})\s*/\s*(\d{4})$", t)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    nomes = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    m = re.match(r"([a-z]+)\s*(?:/|de)?\s*(\d{4})$", t)
    if m and m.group(1) in nomes:
        return f"{m.group(2)}-{nomes.index(m.group(1)) + 1:02d}"
    return None


__all__ = ["VOTOS_RESUMO", "placar", "item_voto", "bloco_votacoes", "escopo_votos", "periodo_meses", "de_antes", "aplicar",
           "Nomes", "valor_br", "xlsx_linhas", "ods_linhas", "mes_br", "bloco_gastos"]
