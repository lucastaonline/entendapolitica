"""Listas oficiais que dão pistas para o mapa das cidades (scripts/municipios/mapear.py).

1. Interlegis (programa do Senado Federal): "Órgãos legislativos atendidos" (SIGI), em CSV, com o domínio .leg.br de
   cada Câmara, o SAPL, o Portal Modelo e o e-mail cadastrado: https://sigi.interlegis.leg.br/servicos/casasatendidas/
2. Diários Oficiais das associações de municípios, que publicam os atos das prefeituras por lei:
   - SIGPub (www.diariomunicipal.com.br/<associação>/): a lista "Município (entidade)" da busca de cada associação;
   - Diário Oficial MS da Assomasul (www.diariooficialms.com.br/assomasul): a lista de municípios do filtro avançado.
   Outros (DOM/SC, DOM-ES da Amunes, Famem, Diário Oficial do Estado...) entram pelos links do site de cada prefeitura.

Cada lista é baixada uma vez a cada DIAS_LISTAS dias (cache em .cache/municipios/fontes/).
"""
from __future__ import annotations

import csv
import difflib
import html
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comum import CACHE, fonte, hoje, log  # noqa: E402

import _paginas as P  # noqa: E402

PASTA = CACHE / "municipios" / "fontes"
DIAS_LISTAS = 7
TEMPO_LISTAS = 180   # segundos: o Interlegis leva uns 25 s só para começar a mandar a lista (gerada na hora)
SO_CACHE = False   # True: não baixa nada (mapear.py --montar)

SIGI_URL = "https://sigi.interlegis.leg.br/servicos/casasatendidas/"
SIGI_CSV = SIGI_URL + "?format=csv"

# Associações no SIGPub (mapa da página inicial de www.diariomunicipal.com.br): endereço -> UF
SIGPUB = {
    "sergipe": "SE", "amupe": "PE", "aam": "AM", "famep": "PA", "amm-mt": "MT", "arom": "RO", "aemerj": "RJ",
    "famurs": "RS", "amp": "PR", "apm": "SP", "ms": "MS", "amm-mg": "MG", "appm": "PI", "aprece": "CE", "amr": "RR",
    "femurn": "RN", "famup": "PB", "agm": "GO", "fgm": "GO", "bahia": "BA", "amurc": "BA", "ama": "AL",
}
SIGPUB_BASE = "https://www.diariomunicipal.com.br/"
ASSOMASUL = "https://www.diariooficialms.com.br/assomasul"

GENERICOS_EMAIL = re.compile(r"(gmail|hotmail|outlook|yahoo|bol|uol|terra|live|ig|globo|msn|icloud|zipmail|r7|oi)\.")


def _baixar(rede, url: str, arquivo: Path, dias: float = DIAS_LISTAS, aceitar: str | None = None) -> bytes | None:
    if arquivo.exists() and arquivo.stat().st_size > 0 and (
            SO_CACHE or (time.time() - arquivo.stat().st_mtime) < dias * 86400):
        return arquivo.read_bytes()
    if SO_CACHE:
        return None
    kw = {"aceitar": aceitar} if aceitar else {}
    r = rede.pagina(url, max_bytes=20_000_000, tempo=TEMPO_LISTAS, **kw)
    if not r.ok or not r.corpo:
        log(f"  [fontes] falhou {url}: {r.erro or r.status}")
        return arquivo.read_bytes() if arquivo.exists() else None
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(r.corpo)
    return r.corpo


class Nomes:
    """Liga um nome de cidade escrito por outro órgão ao código do IBGE (dentro do mesmo estado)."""

    APELIDOS = {  # grafias antigas ou diferentes das do IBGE que aparecem nas listas oficiais
        ("RN", "acu"): "assu", ("SE", "gracho cardoso"): "graccho cardoso", ("TO", "sao valerio da natividade"): "sao valerio",
        ("MG", "sao thome das letras"): "sao tome das letras", ("TO", "couto de magalhaes"): "couto magalhaes",
        ("PE", "belem de sao francisco"): "belem do sao francisco",
        ("PB", "sao domingos de pombal"): "sao domingos", ("MG", "brasopolis"): "brazopolis",
        ("SP", "embu"): "embu das artes", ("PA", "eldorado dos carajas"): "eldorado do carajas",
    }

    def __init__(self, cidades: list):
        self.por_uf: dict[str, dict[str, str]] = {}
        self.nome: dict[str, tuple[str, str]] = {}
        for ibge, nome, uf in cidades:
            self.por_uf.setdefault(uf, {})[P.norm(nome)] = ibge
            self.nome[ibge] = (nome, uf)

    def ibge(self, nome: str, uf: str, corte: float = 0.92) -> str | None:
        tab = self.por_uf.get(uf) or {}
        n = P.norm(nome)
        n = re.sub(r"\b(mg|sp|rj|pr|rs|sc|ba|go|pe|pb|rn|ce|pi|ma|pa|am|ro|rr|ap|to|ac|al|se|es|mt|ms|df)$", "", n).strip()
        n = self.APELIDOS.get((uf, n), n)
        if n in tab:
            return tab[n]
        comp = n.replace(" ", "")
        for k, v in tab.items():
            if k.replace(" ", "") == comp:
                return v
        perto = difflib.get_close_matches(n, list(tab), n=1, cutoff=corte)
        return tab[perto[0]] if perto else None


# ---------------------------------------------------------------------------------------------------- Interlegis (SIGI)
def sigi(rede, nomes: Nomes) -> tuple[dict, dict]:
    """{ibge: {"leg": [domínios .leg.br], "gov": [domínios .gov.br], "portal": url, "sapl": [urls], "email": domínio}},
    e a fonte."""
    corpo = _baixar(rede, SIGI_CSV, PASTA / "sigi-casasatendidas.csv", aceitar="text/csv,*/*;q=0.5")
    out: dict[str, dict] = {}
    if not corpo:
        return out, None
    leitor = csv.DictReader(io.StringIO(corpo.decode("utf-8-sig", "replace")))
    sem = set()
    for r in leitor:
        if (r.get("casa_legislativa__tipo__nome") or "") != "Câmara Municipal":
            continue
        uf = (r.get("casa_legislativa__municipio__uf__sigla") or "").upper()
        mun = r.get("casa_legislativa__municipio__nome") or ""
        ibge = nomes.ibge(mun, uf)
        if not ibge:
            sem.add(f"{mun}/{uf}")
            continue
        d = out.setdefault(ibge, {"leg": [], "gov": [], "portal": None, "sapl": [], "email": None})
        tipo = r.get("tipo_servico__nome") or ""
        url = (r.get("url") or "").strip()
        host = re.sub(r"^https?://", "", url).split("/")[0].lower().strip(".")
        if tipo.startswith("Dom") and ".LEG" in tipo.upper() and host and host not in d["leg"]:
            d["leg"].append(host)
        elif tipo.startswith("Dom") and ".GOV" in tipo.upper() and host and host not in d["gov"]:
            d["gov"].append(host)
        elif tipo == "Portal Modelo" and host:
            d["portal"] = d["portal"] or f"https://{host}/"
        elif tipo == "SAPL" and host:
            if not re.search(r"jovem|juvenil|mirim|senior", host) and host not in d["sapl"]:
                d["sapl"].append(host)
        email = (r.get("casa_legislativa__email") or "").strip().lower()
        if "@" in email and not d["email"]:
            dom = email.split("@")[-1].strip(" .;,")
            if (dom.endswith(".leg.br") or dom.endswith(".gov.br")) and not GENERICOS_EMAIL.search(dom):
                d["email"] = dom
    if sem:
        log(f"  [sigi] {len(sem)} Câmaras sem código do IBGE (nome diferente): {sorted(sem)[:12]}")
    f = fonte("Interlegis (Senado Federal)", "Órgãos legislativos atendidos pelo Interlegis (SIGI): domínio .leg.br, "
              "SAPL e Portal Modelo de cada Câmara", SIGI_URL)
    return out, f


# ---------------------------------------------------------------------------------------------------- SIGPub
_ENT = re.compile(r'<option value="(\d+)">([^<]*)</option>')


def sigpub(rede, nomes: Nomes, ufs: set[str] | None = None) -> tuple[dict, list]:
    """{ibge: [{"assoc", "nome", "url", "entidade", "camara": entidade da Câmara ou None}]} e as fontes."""
    out: dict[str, list] = {}
    fontes = []
    for slug, uf in SIGPUB.items():
        if ufs and uf not in ufs:
            continue
        url = f"{SIGPUB_BASE}{slug}/pesquisar"
        corpo = _baixar(rede, url, PASTA / f"sigpub-{slug}.html")
        if not corpo:
            continue
        t = P.decodificar(corpo, "utf-8")
        alt = re.search(r'<img[^>]+alt="([^"]+)"[^>]*class="[^"]*logo|<img[^>]+class="[^"]*logo[^"]*"[^>]+alt="([^"]+)"', t)
        if alt:
            assoc = html.unescape(alt.group(1) or alt.group(2)).strip()
        else:
            alts = [html.unescape(a) for a in re.findall(r'<img[^>]+alt="([^"]+)"', t)]
            assoc = next((a for a in alts if re.search(r"(?i)associa|federa|munic|uni[aã]o", a)), slug.upper())
        nome_diario = f"Diário Oficial dos Municípios ({assoc})"
        i = t.find('id="busca_avancada_entidade"')
        j = t.find("</select>", i)
        ents = _ENT.findall(t[i:j]) if i >= 0 else []
        pref: dict[str, str] = {}
        cam: dict[str, str] = {}
        for eid, enome in ents:
            en = html.unescape(enome).strip()
            m = re.match(r"(?i)^(prefeitura|munic[ií]pio)( municipal)?( de| do| da| dos| das)?\s+(.+)$", en)
            if m:
                ibge = nomes.ibge(m.group(4), uf)
                if ibge and ibge not in pref:
                    pref[ibge] = eid
                continue
            m = re.match(r"(?i)^c[aã]mara( municipal)?( de vereadores)?( de| do| da| dos| das)?\s+(.+)$", en)
            if m:
                ibge = nomes.ibge(m.group(4), uf)
                if ibge and ibge not in cam:
                    cam[ibge] = eid
        for ibge, eid in pref.items():
            out.setdefault(ibge, []).append({"assoc": slug, "nome": nome_diario, "url": f"{SIGPUB_BASE}{slug}/",
                                             "entidade": eid, "camara": cam.get(ibge)})
        fontes.append(fonte(assoc, f"{nome_diario}: lista de municípios (entidades) que publicam", url))
        log(f"  [sigpub] {slug} ({uf}): {len(pref)} prefeituras e {len(cam)} Câmaras na lista de entidades")
    return out, fontes


# ---------------------------------------------------------------------------------------------------- Assomasul (MS)
def assomasul(rede, nomes: Nomes) -> tuple[dict, list]:
    url = f"{ASSOMASUL}?pagina=filtro-avancado"
    corpo = _baixar(rede, url, PASTA / "assomasul-filtro.html")
    out: dict[str, list] = {}
    if not corpo:
        return out, []
    t = P.decodificar(corpo, "utf-8")
    i = t.find('filtro[municipio_id]')
    j = t.find("</select>", i)
    for mid, mnome in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)', t[i:j] if i >= 0 else ""):
        ibge = nomes.ibge(html.unescape(mnome), "MS")
        if ibge:
            out.setdefault(ibge, []).append({"assoc": "assomasul", "nome": "Diário Oficial MS (Assomasul)",
                                             "url": ASSOMASUL, "entidade": mid, "camara": None})
    log(f"  [assomasul] {len(out)} municípios na lista do filtro avançado")
    return out, [fonte("Associação dos Municípios de Mato Grosso do Sul (Assomasul)",
                       "Diário Oficial MS: lista de municípios do filtro avançado", url)]


# ---------------------------------------------------------------------------------------------------- atividade
# As listas de entidades guardam também quem parou de publicar (numa amostra de 30 cidades do SIGPub, 8 não tinham
# nada publicado entre junho e outubro de 2026). Por isso cada cidade é conferida: publicou algo nos últimos 6 meses?
# E quantas matérias com "lei" no título desde 1º/1/2025 (ajuda a fase 4)? Até 2 pedidos por cidade, a cada 30 dias.
PASTA_DIARIOS = CACHE / "municipios" / "diarios"
DIAS_ATIVIDADE = 30
JANELA_DIAS = 183
INICIO_LEIS = "2025-01-01"


def _cache_atividade(assoc: str, entidade: str) -> tuple[Path, dict | None]:
    import json
    arq = PASTA_DIARIOS / assoc / f"{entidade}.json"
    if arq.exists():
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            d = None
        if d and (SO_CACHE or (time.time() - arq.stat().st_mtime) < DIAS_ATIVIDADE * 86400):
            return arq, d
    return arq, None


def _contar_sigpub(rede, url: str) -> int | None:
    r = rede.pagina(url)
    if not r.ok or not r.corpo:
        return None
    p = P.ler(r.corpo, r.charset, r.final)
    m = re.search(r"mostrando \d+ a \d+ de ([\d ]+) materias", p.texto)
    if m:
        return int(m.group(1).replace(" ", ""))
    if "nenhuma materia encontrada" in p.texto:
        return 0
    return None


def _contar_assomasul(rede, entidade: str, inicio: str, fim: str, titulo: str = "") -> int | None:
    import json
    from urllib.parse import urlencode

    def br(d):
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    q = {"draw": 1, "start": 0, "length": 1, "filtro[municipio_id]": entidade, "filtro[titulo]": titulo,
         "filtro[data_de_inicio]": br(inicio), "filtro[data_de_fim]": br(fim)}
    # o filtro avançado do site pede a lista assim (é o mesmo pedido que a página faz no navegador)
    r = rede.pagina("https://www.diariooficialms.com.br/filtro?" + urlencode(q), aceitar="application/json",
                    extra={"X-Requested-With": "XMLHttpRequest"})
    if not r.ok:
        return None
    try:
        return int(json.loads(r.corpo.decode("utf-8")).get("recordsFiltered"))
    except Exception:
        return None


def atividade(rede, assoc: str, entidade: str) -> dict | None:
    """{"materias6m": n, "leis2025": n, "data"} da entidade no Diário Oficial da associação (cache de 30 dias)."""
    import json
    from datetime import date, timedelta
    arq, d = _cache_atividade(assoc, entidade)
    if d is not None or SO_CACHE:
        return d
    fim = hoje()
    ini = (date.fromisoformat(fim) - timedelta(days=JANELA_DIAS)).isoformat()
    if assoc == "amm-mt-jornal":
        # a plataforma nova só tem publicações recentes (a AMM-MT mudou para ela em 2026): uma busca pela entidade basta
        r = rede.pagina(f"{AMM_MT}/publicacoes/?e={entidade}")
        mat = len(set(re.findall(r"/publicacao/(\d+)/", r.corpo.decode("utf-8", "replace")))) if r.ok else None
        leis = None
    elif assoc == "assomasul":
        mat = _contar_assomasul(rede, entidade, ini, fim)
        leis = _contar_assomasul(rede, entidade, INICIO_LEIS, fim, "lei") if mat else None
    else:
        base = f"{SIGPUB_BASE}{assoc}/pesquisar?busca_avancada%5Bentidade%5D={entidade}"
        mat = _contar_sigpub(rede, base + f"&busca_avancada%5BdataInicio%5D={ini}&busca_avancada%5BdataFim%5D={fim}"
                                          f"&busca_avancada%5Bpagina%5D=1")
        leis = None
        if mat:
            leis = _contar_sigpub(rede, base + f"&busca_avancada%5Btitulo%5D=lei&busca_avancada%5BdataInicio%5D="
                                               f"{INICIO_LEIS}&busca_avancada%5BdataFim%5D={fim}&busca_avancada%5Bpagina%5D=1")
    d = {"assoc": assoc, "entidade": entidade, "data": fim, "desde": ini, "materias6m": mat, "leis2025": leis}
    if mat is not None:
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def ativo(rede, x: dict) -> bool | None:
    """A entidade publicou alguma coisa nos últimos 6 meses? None = não deu para saber."""
    d = atividade(rede, x["assoc"], x["entidade"])
    if not d or d.get("materias6m") is None:
        return None
    return d["materias6m"] > 0


def atividade_cache(assoc: str, entidade: str) -> dict | None:
    """O que já foi conferido (qualquer idade), sem rede."""
    import json
    arq = PASTA_DIARIOS / assoc / f"{entidade}.json"
    if not arq.exists():
        return None
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------------- AMM-MT (DexaTec)
# A AMM-MT trocou o SIGPub (www.diariomunicipal.com.br/amm-mt, sem edições desde 2026) pelo "Jornal Oficial AMM-MT"
# em amm.diariomunicipal.org (plataforma DexaTec). A busca de publicações tem a lista "Entidades" (Pref. X / Cam. X).
AMM_MT = "https://amm.diariomunicipal.org"


def amm_mt(rede, nomes: Nomes) -> tuple[dict, list]:
    url = f"{AMM_MT}/publicacoes/"
    corpo = _baixar(rede, url, PASTA / "amm-mt-publicacoes.html")
    out: dict[str, list] = {}
    if not corpo:
        return out, []
    t = P.decodificar(corpo, "utf-8")
    m = re.search(r'(?is)<select[^>]+name="e"[^>]*>(.*?)</select>', t)
    for eid, enome in re.findall(r'(?is)<option[^>]*value="(\d+)"[^>]*>([^<]*)', m.group(1) if m else ""):
        en = re.sub(r"\s+", " ", html.unescape(enome)).strip()
        mm = re.match(r"(?i)^pref(?:eitura)?\.?\s+(?:municipal\s+)?(?:de\s+)?(.+)$", en)
        if mm:
            ibge = nomes.ibge(mm.group(1), "MT")
            if ibge and ibge not in out:
                out[ibge] = [{"assoc": "amm-mt-jornal", "nome": "Jornal Oficial AMM-MT (Associação Mato-grossense dos Municípios)",
                              "url": f"{AMM_MT}/", "entidade": eid, "camara": None}]
    log(f"  [amm-mt] {len(out)} prefeituras na lista de entidades do Jornal Oficial AMM-MT")
    return out, [fonte("Associação Mato-grossense dos Municípios (AMM-MT)",
                       "Jornal Oficial AMM-MT: lista de entidades da busca de publicações", url)]


# ---------------------------------------------------------------------------------------------------- CIGA (SC)
# O Consórcio de Inovação na Gestão Pública (Ciga, consorciociga.gov.br) mantém o DOM/SC. O site do Ciga publica os
# municípios consorciados e o link do site de 113 Câmaras (API pública do próprio site). O DOM/SC pede no robots.txt
# que robôs não o leiam: por isso, em SC, a ligação cidade -> DOM/SC vem do link no site da prefeitura (confirmada) ou
# da adesão ao Ciga (não confirmada cidade por cidade; o Ciga diz que 291 municípios usam o DOM/SC).
CIGA = "https://consorciociga.gov.br"


def ciga(rede, nomes: Nomes) -> tuple[set, dict, list]:
    """(IBGE dos municípios de SC consorciados ao Ciga, {IBGE: site da Câmara}, fontes)."""
    import json
    por6 = {ibge[:6]: ibge for ibge in nomes.nome}
    consorciados, camaras = set(), {}
    corpo = _baixar(rede, f"{CIGA}/api/municipios-consorciados", PASTA / "ciga-municipios.json",
                    aceitar="application/json")
    if corpo:
        try:
            for x in json.loads(corpo.decode("utf-8")).get("data") or []:
                ibge = por6.get(str(x.get("codigoIBGE") or "")[:6])
                if ibge and x.get("uf") == "SC":
                    consorciados.add(ibge)
        except Exception:
            pass
    corpo = _baixar(rede, f"{CIGA}/api/camara-municipios", PASTA / "ciga-camaras.json", aceitar="application/json")
    if corpo:
        try:
            for x in json.loads(corpo.decode("utf-8")).get("data") or []:
                ibge = por6.get(str((x.get("municipio") or {}).get("codigoIBGE") or "")[:6])
                link = x.get("link") or ""
                if ibge and link:
                    camaras[ibge] = link
        except Exception:
            pass
    log(f"  [ciga] {len(consorciados)} municípios de SC consorciados; {len(camaras)} sites de Câmaras")
    fontes = [fonte("Consórcio de Inovação na Gestão Pública (Ciga)", "Municípios consorciados e sites das Câmaras "
                    "(o Ciga mantém o DOM/SC)", f"{CIGA}/municipios-consorciados")]
    return consorciados, camaras, fontes


# ---------------------------------------------------------------------------------------------------- SAPL
_TIPOS_PROJETO = re.compile(r"projeto de (lei|decreto legislativo|resolucao|emenda)|proposta de emenda|emenda a lei organica")
SAPL_DESCOBERTA = CACHE / "camaras" / "descoberta"
SAPL_PASTA = CACHE / "municipios" / "sapl"
DIAS_SAPL = 30


def sapl_descoberta(ibge: str, host: str) -> dict | None:
    """Resultado de scripts/descobrir_sapl.py para esta cidade, se for o mesmo endereço e tiver menos de DIAS_SAPL dias."""
    import json
    arq = SAPL_DESCOBERTA / f"{ibge}.json"
    if not arq.exists() or (time.time() - arq.stat().st_mtime) > DIAS_SAPL * 86400:
        return None
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return None
    if (d.get("host") or "").lower() != host.lower():
        return None
    if not d.get("dns"):
        return {"host": host, "data": d.get("data"), "dns": False, "api": False, "origem": "descoberta"}
    return {"host": host, "data": d.get("data"), "dns": True, "api": bool(d.get("api")),
            "legislaturaAtual": bool(d.get("legislaturaAtual")),
            "projetos2025": d.get("projetos2025"), "erro": d.get("erro"), "origem": "descoberta"}


def sapl_cache(host: str) -> dict | None:
    import json
    arq = SAPL_PASTA / f"{host}.json"
    if not arq.exists() or (time.time() - arq.stat().st_mtime) > DIAS_SAPL * 86400:
        return None
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return None


def sapl_testar(rede, host: str) -> dict:
    """A API pública do SAPL 3 responde? Tem a legislatura de hoje? Quantos projetos desde 1º/1/2025?
    Até 3 pedidos (o SAPL pede 60 s entre pedidos no robots.txt; a Rede respeita)."""
    import json
    from datetime import date
    base = f"https://{host}"
    r = {"host": host, "data": hoje(), "dns": True, "api": False, "legislaturaAtual": False, "projetos2025": None,
         "erro": None, "origem": "mapa"}
    if not rede.ip(host):
        r.update(dns=False, erro="dns")
        SAPL_PASTA.mkdir(parents=True, exist_ok=True)
        (SAPL_PASTA / f"{host}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        return r

    def pedir(caminho):
        resp = rede.pagina(base + caminho, aceitar="application/json", max_bytes=3_000_000)
        if resp.erro == "robots":
            raise RuntimeError("robots")
        if not resp.ok:
            raise RuntimeError(resp.erro or f"http {resp.status}")
        if "json" not in (resp.tipo or "").lower():
            raise RuntimeError("não é JSON")
        return json.loads(resp.corpo.decode("utf-8", "replace"))

    try:
        legs = pedir("/api/parlamentares/legislatura/?page_size=100")
        r["api"] = isinstance(legs, dict) and "results" in legs
        d = date.today().isoformat()
        r["legislaturaAtual"] = any((l.get("data_inicio") or "") <= d <= (l.get("data_fim") or "")
                                    for l in legs.get("results") or [])
        tipos = pedir("/api/materia/tipomaterialegislativa/?page_size=100")
        ids = [t["id"] for t in tipos.get("results") or []
               if _TIPOS_PROJETO.search(P.norm(t.get("descricao") or ""))]
        if ids:
            m = pedir("/api/materia/materialegislativa/?page_size=1&data_apresentacao__gte=2025-01-01&tipo__in="
                      + ",".join(map(str, ids)))
            r["projetos2025"] = (m.get("pagination") or {}).get("total_entries")
        else:
            r["projetos2025"] = 0
    except Exception as e:
        r["erro"] = str(e)[:80]
    SAPL_PASTA.mkdir(parents=True, exist_ok=True)
    (SAPL_PASTA / f"{host}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return r
