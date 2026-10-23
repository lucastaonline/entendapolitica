"""Ajudas comuns dos coletores das Assembleias do Sudeste e do Sul (SP, MG, RJ, ES, PR, SC, RS) e da Câmara Legislativa
do Distrito Federal (DF).

- Rede: um pedido por vez ao site oficial, com pausa entre eles, e cache em .cache/<pasta>/ (para não pesar no site
  oficial e para a coleta de todo dia ser rápida).
- partido_sigla: o partido como cada Casa escreve -> a sigla usada no resto do site (a mesma da lista da Câmara).
- casar_membros: liga cada pessoa da lista oficial ao candidato do TSE da eleição da legislatura em curso (2022; 2026
  depois da posse de 2027): é ele que dá o id do site. Na dúvida,
  não liga (ligar errado é pior do que não ligar); os casos conferidos à mão ficam no próprio coletor (MANUAL).
- bloco_gastos: verba indenizatória no mesmo formato dos gastos dos deputados federais.
- gravar: grava dados/assembleias/<UF>.json e dados/pessoas/dest-<UF>-*.json com as ajudas de scripts/regional.py.
"""
from __future__ import annotations

import html as _html
import json
import re
import time
from pathlib import Path

import regional
from comum import CACHE, STATUS_TXT, baixar, chave_nome, fonte, hoje, log, sem_acento
from mandatos import data_br, extenso, vigente

SUPLENTE = ("Suplente em exercício", "Substitute in office")
SUPLENTE_VAGA = ("Suplente que assumiu a vaga", "Substitute who took over the seat")
# posse da legislatura 2023–2027 onde não foi em 1º de fevereiro de 2023: SP (Constituição de SP, ADCT art. 1º-A, EC 47/2019),
# DF (Lei Orgânica do DF, art. 66, antes da Emenda 131/2024) e RS (Constituição do RS, art. 49, § 3º). Da legislatura
# seguinte em diante vale a data de scripts/mandatos.py (POSSE_ESTADUAL).
POSSE_2023 = {"SP": "2023-03-15", "DF": "2023-01-01", "RS": "2023-01-31"}


def legislatura(uf: str) -> dict:
    """A legislatura estadual em curso: {"eleicao": 2022, "inicio": "2023-02-01", "fim": "2027-02-01"}. Na posse da
    próxima (scripts/mandatos.py), tudo troca sozinho: os candidatos do TSE (2026), o começo das propostas e os textos."""
    v = vigente("deputado_estadual", uf=uf)
    ini = POSSE_2023.get(uf, v["inicio"]) if v["eleicao"] == 2022 else v["inicio"]
    return {"eleicao": v["eleicao"], "inicio": ini, "fim": v["fim"]}


def desde(iso: str) -> tuple[str, str]:
    """'2023-02-01' -> ('1º/2/2023', 'February 1, 2023'), para o texto do escopo."""
    return data_br(iso), extenso(iso)[1]
_TIPOS_PT = {"PL": "projetos de lei", "PLP": "projetos de lei complementar", "PEC": "propostas de emenda à Constituição do estado",
             "PELO": "propostas de emenda à Lei Orgânica do Distrito Federal",
             "PDL": "projetos de decreto legislativo", "PRC": "projetos de resolução"}
_TIPOS_EN = {"PL": "bills", "PLP": "complementary bills", "PEC": "amendments to the state Constitution",
             "PELO": "amendments to the Organic Law of the Federal District (its constitution)",
             "PDL": "legislative decrees", "PRC": "resolutions"}


def _junta(itens: list[str], e: str) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + f" {e} " + itens[-1]


def escopo(desde_txt: str, desde_en: str, tipos=("PL", "PLP", "PEC", "PDL", "PRC"), extra: str = "",
           extra_en: str = "") -> tuple[str, str]:
    """Texto do escopo das propostas (português, inglês), só com os tipos que a Casa tem."""
    pt = (f"Propostas apresentadas desde {desde_txt}, quando começou o mandato atual: "
          f"{_junta([_TIPOS_PT[t] for t in tipos], 'e')}. Pedidos de informação, sugestões ao governo (indicações) "
          "e moções não entram." + (" " + extra if extra else ""))
    en = (f"Proposals filed since {desde_en}, when the current term began: {_junta([_TIPOS_EN[t] for t in tipos], 'and')}. "
          "Requests for information, suggestions to the government and motions are not included." + (" " + extra_en if extra_en else ""))
    return pt, en


# ---------------------------------------------------------------- rede
class Rede:
    """Pede uma coisa por vez ao site oficial, com pausa entre os pedidos, e guarda tudo em .cache/<pasta>/."""

    def __init__(self, pasta: str, pausa: float = 1.0, timeout: int = 90, tentativas: int = 3):
        self.pasta = CACHE / pasta
        self.pausa, self.timeout, self.tentativas = pausa, timeout, tentativas
        self._ult = 0.0
        self.pedidos = 0  # quantos foram à rede nesta execução

    def caminho(self, cache: str) -> Path:
        return self.pasta / cache

    def fresco(self, cache: str | None, max_idade_h: float | None) -> bool:
        destino = self.pasta / cache if cache else None
        if destino is None or not destino.exists() or destino.stat().st_size == 0:
            return False
        return max_idade_h is None or (time.time() - destino.stat().st_mtime) / 3600 < max_idade_h

    def idade_h(self, cache: str) -> float | None:
        d = self.pasta / cache
        return (time.time() - d.stat().st_mtime) / 3600 if d.exists() else None

    def _espera(self) -> None:
        espera = self.pausa - (time.time() - self._ult)
        if espera > 0:
            time.sleep(espera)

    def bruto(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, headers: dict | None = None,
              dados: bytes | None = None, timeout: int | None = None) -> bytes:
        destino = self.pasta / cache if cache else None
        if cache and self.fresco(cache, max_idade_h):
            return destino.read_bytes()
        self._espera()
        try:
            return baixar(url, destino, max_idade_h=0, tentativas=self.tentativas, timeout=timeout or self.timeout,
                          headers=headers, dados=dados)
        finally:
            self._ult = time.time()
            self.pedidos += 1

    def json(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, **kw):
        h = {"Accept": "application/json"}
        h.update(kw.pop("headers", None) or {})
        return json.loads(self.bruto(url, cache, max_idade_h, headers=h, **kw).decode("utf-8-sig"))

    def texto(self, url: str, cache: str | None = None, max_idade_h: float | None = 20, codificacao: str = "utf-8", **kw) -> str:
        return self.bruto(url, cache, max_idade_h, **kw).decode(codificacao, "replace")

    def arquivo(self, url: str, cache: str, max_idade_h: float | None = 20, timeout: int = 600) -> Path:
        """Arquivo grande (zip, csv): baixa por partes direto para o disco."""
        from comum import baixar_arquivo
        if self.fresco(cache, max_idade_h):
            return self.pasta / cache
        self._espera()
        try:
            rel = (self.pasta / cache).relative_to(CACHE)
            return baixar_arquivo(url, str(rel).replace("\\", "/"), max_idade_h=0, timeout=timeout, tentativas=self.tentativas)
        finally:
            self._ult = time.time()
            self.pedidos += 1

    def estado(self, nome: str = "estado.json", padrao=None):
        arq = self.pasta / nome
        if arq.exists():
            try:
                return json.loads(arq.read_text(encoding="utf-8"))
            except Exception:
                pass
        return padrao

    def guardar(self, obj, nome: str = "estado.json") -> None:
        arq = self.pasta / nome
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(arq)


def https(url: str | None) -> str | None:
    """Fotos e páginas oficiais em https (o site é https; endereço http seria bloqueado pelo navegador)."""
    if not url:
        return None
    return re.sub(r"^http://", "https://", url.strip())


def sem_html(s: str | None) -> str | None:
    """Tira as marcas de HTML e junta os espaços."""
    if s is None:
        return None
    t = _html.unescape(re.sub(r"<[^>]+>", " ", s))
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def dia_rodizio(chave, dias: int = 7) -> bool:
    """Para espalhar pedidos pela semana: True no dia da semana desta chave (1/7 das pessoas por dia)."""
    n = sum(ord(c) for c in str(chave))
    return n % dias == int(time.strftime("%j")) % dias


# ---------------------------------------------------------------- partidos
_PARTIDOS = [
    (r"UNIAO( BRASIL)?|UB|UNIAO BRASIL", "UNIÃO"), (r"REP|REPUBLICA|REPUBLICANOS|PRB", "REPUBLICANOS"),
    (r"PC ?DO ?B|PARTIDO COMUNISTA DO BRASIL", "PCdoB"), (r"SD|SDD|SOLIDARIEDADE", "SOLIDARIEDADE"),
    (r"PODE|PODEMOS", "PODE"), (r"PP|PROGRESSISTAS?|PARTIDO PROGRESSISTA", "PP"), (r"PL|PARTIDO LIBERAL", "PL"),
    (r"PT|PARTIDO DOS TRABALHADORES", "PT"), (r"P?MDB|(PARTIDO DO )?MOVIMENTO DEMOCRATICO BRASILEIRO", "MDB"),
    (r"PSB|PARTIDO SOCIALISTA BRASILEIRO", "PSB"), (r"PSD|PARTIDO SOCIAL DEMOCRATICO", "PSD"),
    (r"PSDB|PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA", "PSDB"), (r"PDT|PARTIDO DEMOCRATICO TRABALHISTA", "PDT"),
    (r"PV|PARTIDO VERDE", "PV"), (r"PSOL|PARTIDO SOCIALISMO E LIBERDADE", "PSOL"), (r"AVANTE", "AVANTE"),
    (r"CIDADANIA", "CIDADANIA"), (r"REDE( SUSTENTABILIDADE)?", "REDE"), (r"PRD|PARTIDO RENOVACAO DEMOCRATICA", "PRD"),
    (r"AGIR", "AGIR"), (r"NOVO|PARTIDO NOVO", "NOVO"), (r"MOBILIZA", "MOBILIZA"), (r"DC|DEMOCRACIA CRISTA", "DC"),
    (r"PMB|PARTIDO DA MULHER BRASILEIRA", "PMB"), (r"MISSAO|PARTIDO MISSAO", "MISSÃO"), (r"PRTB", "PRTB"),
    (r"PSDB ?CIDADANIA|FEDERACAO PSDB CIDADANIA", "PSDB"),
    (r"S/? ?PARTIDO|SEM PARTIDO|SEM FILIACAO|S\.? ?PART\.?", "Sem partido"),
]


def partido_sigla(txt: str | None) -> str | None:
    """'União Brasil', 'UNIAO', 'Progressistas', 'PC do B'... -> a sigla do resto do site ('UNIÃO', 'PP', 'PCdoB')."""
    t = re.sub(r"\s+", " ", sem_acento(txt or "").upper()).strip(" -")
    if not t:
        return None
    for exp, sigla in _PARTIDOS:
        if re.fullmatch(exp, t):
            return sigla
    return (txt or "").strip().upper()


# ---------------------------------------------------------------- TSE
def cargo_tse(uf: str) -> str:
    return "DEPUTADO DISTRITAL" if uf == "DF" else "DEPUTADO ESTADUAL"


def candidatos(uf: str) -> list[dict]:
    """Candidatos a deputado estadual (distrital, no DF) da eleição da legislatura em curso que foram eleitos ou ficaram
    como suplentes (quem está no cargo hoje só pode ter vindo daí)."""
    return [c for c in regional.candidatos_tse(legislatura(uf)["eleicao"], {cargo_tse(uf)}, uf)
            if c["sit"].startswith("ELEITO") or c["sit"] == "SUPLENTE"]


def _parecido(a: str | None, b: str | None) -> bool:
    pa, pb = set(regional.palavras(a)), set(regional.palavras(b))
    return bool(pa and pb) and (len(pa & pb) >= min(2, len(pa), len(pb)))


def casar_membros(uf: str, pessoas: list[dict], manual: dict | None = None) -> tuple[dict, list[str]]:
    """pessoas = [{"chave", "nome", "nomeCivil", "partido"}] da lista oficial; manual = {chave: SQ do TSE ou "-"}
    (conferido à mão). Devolve ({chave: candidato do TSE ou None}, avisos para conferir)."""
    cands = candidatos(uf)
    ano = legislatura(uf)["eleicao"]
    por_sq = {c["sq"]: c for c in regional.candidatos_tse(ano, {cargo_tse(uf)}, uf)}
    manual = {str(k): v for k, v in (manual or {}).items()}
    out, avisos, usados = {}, [], {}
    for p in pessoas:
        k = str(p["chave"])
        if k in manual:
            sq = manual[k]
            out[k] = por_sq.get(sq) if sq and sq != "-" else None
            if sq and sq != "-" and not out[k]:
                avisos.append(f"{p['nome']}: SQ manual {sq} não está no TSE de {ano} ({uf})")
            if out[k]:
                usados[out[k]["sq"]] = p["nome"]
            continue
        c = regional.casar_tse([p.get("nome"), p.get("nomeCivil")], cands, partido=p.get("partido"))
        # conferência: se a Casa dá o nome completo, ele tem de bater com o nome do candidato no TSE
        if c and p.get("nomeCivil") and not _parecido(p["nomeCivil"], c["nome"]) and not _parecido(p["nomeCivil"], c["urna"]):
            avisos.append(f"{p['nome']} ({p.get('nomeCivil')}): o nome civil não bate com o TSE ({c['nome']}); sem ligação")
            c = None
        if c and c["sq"] in usados:
            avisos.append(f"{p['nome']} e {usados[c['sq']]} caíram no mesmo candidato do TSE ({c['urna']}); sem ligação")
            c = None
        if c:
            usados[c["sq"]] = p["nome"]
        else:
            avisos.append(f"{p['nome']} ({p.get('nomeCivil') or '-'}): sem candidato do TSE de {ano} ligado")
        out[k] = c
    return out, avisos


# ---------------------------------------------------------------- propostas
def nome_lei(tipo: str, numero, ano=None) -> str:
    """('Lei', '24567', 2023) -> 'Lei nº 24.567/2023'."""
    n = str(numero or "").strip()
    if n.isdigit() and len(n) > 3:
        n = f"{int(n):,}".replace(",", ".")
    return f"{tipo} nº {n}/{ano}" if ano else f"{tipo} nº {n}"


def virou(p: dict, lei_nome: str | None, lei_url: str | None) -> dict:
    """Marca "virou lei" com o nome da norma (o site traduz "Virou a Lei nº ..." para o inglês sozinho)."""
    if lei_nome:
        p["lei"] = {"nome": lei_nome, "url": lei_url}
        artigo = "o" if re.match(r"(?i)decreto", lei_nome) else "a"
        p["statusTxt"] = f"Virou {artigo} {lei_nome}"
    return p


def com_status_en(p: dict, pt: str | None, en: str | None) -> dict:
    """Frase própria para a situação (português e inglês)."""
    if pt:
        p["statusTxt"] = pt
    if en:
        p["statusTxt_en"] = en
    return p


def resumo_status(listas) -> dict:
    """Contagem de status de todas as propostas (para conferir as regras de cada Casa)."""
    c: dict[str, int] = {}
    for l in listas:
        for p in l:
            c[p["status"]] = c.get(p["status"], 0) + 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------- gastos
NOME_GASTOS = ("Verba indenizatória", "Expense allowance (verba indenizatória)")


def bloco_gastos(linhas: list[tuple[str, str, float]], fonte_gastos: dict, inicio: str = regional.INICIO_ESTADUAL,
                 nome: tuple[str, str] = NOME_GASTOS) -> dict | None:
    """linhas = [(mês "AAAA-MM", tipo de despesa, valor reembolsado)] de uma pessoa. Mesmo formato dos gastos federais:
    {ano, total, porTipo, mandatoTotal, fonte}; ano = o mais recente com gastos; mandatoTotal = desde o começo da
    legislatura (ou desde o primeiro mês com gastos, em "desde", como no README)."""
    linhas = [(m, t, v) for m, t, v in linhas if m and m >= inicio[:7] and v]
    if not linhas:
        return None
    ano = max(m for m, _, _ in linhas)[:4]
    por_tipo: dict[str, float] = {}
    for m, t, v in linhas:
        if m.startswith(ano):
            por_tipo[t] = por_tipo.get(t, 0.0) + v
    meses = sorted({m for m, _, _ in linhas if m.startswith(ano)})
    return {
        "nome": nome[0], "nome_en": nome[1],
        "ano": int(ano), "total": round(sum(por_tipo.values()), 2),
        "porTipo": [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(por_tipo.items(), key=lambda x: (-x[1], x[0]))],
        "mandatoTotal": round(sum(v for _, _, v in linhas), 2), "desde": min(m for m, _, _ in linhas),
        "meses": [meses[0], meses[-1]], "fonte": fonte_gastos,
    }


# ---------------------------------------------------------------- gravar
def membro(pid: str, nome: str, nome_civil: str | None, partido: str | None, genero: str | None, foto: str | None,
           url: str | None, suplente: bool | str = False) -> dict:
    """suplente: False (titular eleito), True (suplente em exercício: o titular está afastado) ou "vaga" (suplente que
    ficou com a vaga de vez, porque o titular saiu)."""
    ex = SUPLENTE_VAGA if suplente == "vaga" else SUPLENTE if suplente else (None, None)
    return {"id": pid, "nome": nome, "nomeCivil": nome_civil or None, "partido": partido,
            "genero": genero if genero in ("F", "M") else None, "foto": https(foto), "url": url,
            "exercicio": ex[0], "exercicio_en": ex[1]}


def gravar(uf: str, casa: dict, membros: list[dict], extras: dict[str, dict], cobertura: dict, fonte_lista: dict,
           escopo_pt: str, escopo_en: str, notas: list[tuple[str, str]] | None = None) -> dict:
    """casa = {"casa", "casa_en", "sigla", "site"}; membros no formato do contrato; extras = {id: dados do perfil};
    notas = [(português, inglês)]. Devolve o resumo que vai para dados/legislativos.json."""
    membros = sorted(membros, key=lambda m: chave_nome(m.get("nome") or ""))
    ids = [m["id"] for m in membros]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{uf}: ids repetidos na lista oficial")
    if not membros:
        raise RuntimeError(f"{uf}: a lista oficial veio vazia")
    notas = notas or []
    dados = {
        "uf": uf, "ibge": None, "casa": casa["casa"], "casa_en": casa["casa_en"], "sigla": casa["sigla"], "site": casa["site"],
        "fonte": fonte_lista, "cobertura": cobertura, "escopoPropostas": escopo_pt, "escopoPropostas_en": escopo_en,
        "membros": membros, "notas": [n[0] for n in notas], "notas_en": [n[1] for n in notas],
    }
    regional.salvar_casa("assembleia", uf, dados)
    for pid, x in extras.items():
        regional.salvar_extras(pid, x)
    apagados = regional.limpar_extras(f"dest-{uf}-", set(extras))
    total = sum(len(((x.get("propostas") or {}).get("lista") or [])) for x in extras.values())
    if apagados:
        log(f"  {uf}: {apagados} perfis antigos apagados (saíram da lista)")
    return {"casa": casa["sigla"], "membros": len(membros), "propostas": total, "cobertura": cobertura, "fonte": fonte_lista}


__all__ = ["Rede", "https", "sem_html", "dia_rodizio", "partido_sigla", "cargo_tse", "candidatos", "casar_membros",
           "nome_lei", "virou", "com_status_en", "resumo_status", "bloco_gastos", "membro", "gravar", "escopo",
           "legislatura", "desde", "POSSE_2023",
           "SUPLENTE", "SUPLENTE_VAGA", "NOME_GASTOS", "STATUS_TXT", "fonte", "hoje", "log"]
