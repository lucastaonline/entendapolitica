"""Junta as peças depois dos coletores:
- dados/tse/federais.json -> eleicao, eleicao2026 e bens nos perfis federais (dados/pessoas/*.json)
  e eleicao2026 nas listas (camara.json, senado.json, executivo.json);
- textos em inglês da eleição de 2026 (txt_en) também nos estados;
- explicações simples (dados/simples/*.json) -> campos "s" e "s_en" das propostas (perfis e páginas das votações);
- listas oficiais das Assembleias e Câmaras Municipais (dados/assembleias, dados/camaras) nas páginas do estado e da cidade;
- dados/cidades.json e sitemap.xml.

Rode por último: python scripts/montar.py
"""
from __future__ import annotations

from comum import *
from mandatos import vigente
import votacoes

CARGOS_EN = {
    "presidente": "president", "vice-presidente": "vice president", "senador": "senator", "senadora": "senator",
    "governador": "governor", "governadora": "governor", "vice-governador": "vice governor", "vice-governadora": "vice governor",
    "deputado federal": "federal deputy", "deputada federal": "federal deputy", "deputado estadual": "state deputy",
    "deputada estadual": "state deputy", "deputado distrital": "district deputy", "deputada distrital": "district deputy",
    "1º suplente de senador": "1st alternate senator", "2º suplente de senador": "2nd alternate senator",
    "1o suplente": "1st alternate senator", "2o suplente": "2nd alternate senator",
}


def cargo_en(cargo: str | None) -> str | None:
    if not cargo:
        return None
    c = re.sub(r"\s+", " ", sem_acento(cargo).lower()).strip()
    for pt, en in CARGOS_EN.items():
        if sem_acento(pt) == c:
            return en
    return None


def txt_en(e: dict | None) -> str | None:
    if not e or not e.get("situacao"):
        return None
    c = cargo_en(e.get("cargo"))
    s = e["situacao"]
    if s == "nao-concorreu":
        return "Did not run in 2026"
    t2 = e.get("turno") == 2  # resultado do 2º turno
    passou = s == "segundo-turno" and (e.get("txt") or "").startswith("Disputou")  # o 2º turno já foi, sem resultado
    if not c:
        return {"eleito": "Elected in the 2026 runoff" if t2 else "Elected in 2026",
                "reeleito": "Re-elected in the 2026 runoff" if t2 else "Re-elected in 2026",
                "segundo-turno": "Ran in the runoff on October 25, 2026" if passou else "In the runoff on October 25, 2026",
                "nao-eleito": "Ran in the 2026 runoff and was not elected" if t2 else "Not elected in 2026",
                "suplente": "Alternate in 2026", "candidato": "Candidate in 2026"}.get(s)
    return {"eleito": f"Elected {c} in the 2026 runoff" if t2 else f"Elected {c} in 2026",
            "reeleito": f"Re-elected {c} in the 2026 runoff" if t2 else f"Re-elected {c} in 2026",
            "segundo-turno": f"Ran in the runoff for {c} on October 25, 2026" if passou else f"In the runoff for {c} on October 25, 2026",
            "nao-eleito": f"Ran for {c} in the 2026 runoff and was not elected" if t2 else f"Ran for {c} in 2026 and was not elected",
            "suplente": f"Alternate for {c} in 2026", "candidato": f"Candidate for {c} in 2026"}.get(s)


def com_en(e: dict | None) -> dict | None:
    if not e:
        return e
    e = dict(e)
    t = txt_en(e)
    if t:
        e["txt_en"] = t
    return e


def resumo2026(e: dict | None) -> dict | None:
    """Versão curta para as listas (cartões)."""
    if not e or not e.get("situacao"):
        return None
    return {k: e[k] for k in ("situacao", "cargo", "txt", "txt_en") if e.get(k) is not None}


# mandatos anteriores: só os do mesmo cargo/Casa, para todo mundo (cada fonte oficial só conhece os seus)
MESMO_CARGO = {"dep": r"^deputad[oa] federal", "sen": r"^senador", "pres": r"^presidente", "vp": r"^vice-presidente"}


def mesma_regua(p: dict, t: dict) -> None:
    """Mesma régua para todos os perfis federais: ocupação e escolaridade declaradas ao TSE na candidatura mais
    recente (as Casas e o Planalto descrevem isso de jeitos diferentes, ou não descrevem) e mandatos anteriores
    só no mesmo cargo."""
    ficha = t.get("ficha")
    p.pop("profissoes", None)
    p["ocupacao"] = ({"txt": ficha["ocupacao"], "ano": ficha["ano"], "fonte": ficha["fonte"]}
                     if ficha and ficha.get("ocupacao") else None)
    p["escolaridade"] = ficha.get("escolaridade") if ficha else None
    if ficha and ficha.get("escolaridade"):
        p["escolaridadeFonte"] = ficha["fonte"]
    else:
        p.pop("escolaridadeFonte", None)
    exp = MESMO_CARGO.get((p.get("id") or "").split("-")[0])
    if exp and p.get("mandatosAnteriores"):
        p["mandatosAnteriores"] = [m for m in p["mandatosAnteriores"]
                                   if re.search(exp, sem_acento((m.get("cargo") or "").lower()))]


SITE = "https://entendapolitica.vercel.app"  # endereço público (troque aqui e no robots.txt se mudar)
PAGINAS = ("", "entenda.html", "brasil.html", "estado.html", "cidade.html", "votacoes.html", "imparcialidade.html", "dados.html")


def indice_cidades() -> int:
    """dados/cidades.json: as 5.569 cidades numa lista só ([código IBGE, nome, UF]), para a busca de cidade do site."""
    l = []
    for arq in sorted((DADOS / "cidades").glob("*.json")):
        for c in ler_json(arq, []) or []:
            l.append([str(c["ibge"]), c["nome"], arq.stem])
    l.sort(key=lambda x: (sem_acento(x[1].lower()), x[2]))
    salvar_json(DADOS / "cidades.json", l)
    return len(l)


def sitemap() -> int:
    """sitemap.xml com as páginas, os 27 estados, os perfis, as votações do texto principal (as outras ficam a um
    clique, na lista e nos perfis) e os mandatos anteriores do Brasil e dos estados, em português e em inglês."""
    urls = [(p, None) for p in PAGINAS if p == "" or (RAIZ / p).exists()]
    for arq in sorted((DADOS / "estados").glob("*.json")):
        urls.append((f"estado.html?uf={arq.stem}", (ler_json(arq) or {}).get("atualizado")))
    for arq in sorted(PESSOAS.glob("*.json")):
        urls.append((f"pessoa.html?id={arq.stem}", (ler_json(arq) or {}).get("atualizado")))
    for arq in sorted(EXTRAS_CIDADES.glob("*.json")):  # vereadores e prefeitos com dados no arquivo da cidade
        b = ler_json(arq) or {}
        urls += [(f"pessoa.html?id={pid}", b.get("atualizado")) for pid in sorted(b.get("pessoas") or {})]
    for casa in ("camara", "senado"):
        cat = (ler_json(DADOS / "votacoes" / f"{casa}.json") or {}).get("votacoes") or {}
        for chave, v in sorted(cat.items()):
            if v.get("categoria") == "principal":
                urls.append((f"votacao.html?casa={casa}&id={chave.split(':')[-1]}", v.get("data")))
    # mandatos que já acabaram (o de hoje é a página sem ?mandato); as cidades dariam ~44 mil endereços e ficam de fora
    ind = ler_json(DADOS / "historico" / "indice.json") or {}
    ufs = sorted(a.stem for a in (DADOS / "estados").glob("*.json"))
    for nivel, bases in (("brasil", ["brasil.html?"]), ("estados", [f"estado.html?uf={uf}&" for uf in ufs])):
        for m in ind.get(nivel) or []:
            if m.get("fim") and m["fim"] <= hoje():
                urls += [(f"{b}mandato={m['id']}", ind.get("atualizado")) for b in bases]
    urls += _eleitos_sitemap()  # eleitos 2026 (até a posse): perfis e26-
    urls += _stf_sitemap()  # ministros do STF: perfis stf-

    def en(c: str) -> str:
        return c + ("&" if "?" in c else "?") + "lang=en"

    def esc(u: str) -> str:
        return u.replace("&", "&amp;")

    linhas = []
    for c, data in urls:
        pt, ing = f"{SITE}/{c}", f"{SITE}/{en(c)}"
        alt = (f'<xhtml:link rel="alternate" hreflang="pt-BR" href="{esc(pt)}"/>'
               f'<xhtml:link rel="alternate" hreflang="en" href="{esc(ing)}"/>'
               f'<xhtml:link rel="alternate" hreflang="x-default" href="{esc(pt)}"/>')
        lm = f"<lastmod>{data}</lastmod>" if data else ""
        for u in (pt, ing):
            linhas.append(f"<url><loc>{esc(u)}</loc>{lm}{alt}</url>")

    def grava(nome: str, txt: str) -> None:
        # fim de linha "\n" em qualquer sistema, comparando byte a byte (ver comum.salvar_json)
        arq, dado = RAIZ / nome, txt.encode("utf-8")
        if not arq.exists() or arq.read_bytes() != dado:
            arq.write_bytes(dado)

    cab = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n')
    # um arquivo aceita até 50 mil endereços: acima de 40 mil, sitemap.xml vira um índice de sitemap-1.xml, sitemap-2.xml...
    POR_ARQ = 40000
    partes = [linhas[i:i + POR_ARQ] for i in range(0, len(linhas), POR_ARQ)] or [[]]
    velhas = set(p.name for p in RAIZ.glob("sitemap-*.xml"))
    if len(partes) == 1:
        grava("sitemap.xml", cab + "\n".join(partes[0]) + "\n</urlset>\n")
    else:
        for k, parte in enumerate(partes, 1):
            grava(f"sitemap-{k}.xml", cab + "\n".join(parte) + "\n</urlset>\n")
            velhas.discard(f"sitemap-{k}.xml")
        grava("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
              "\n".join(f"<sitemap><loc>{SITE}/sitemap-{k}.xml</loc></sitemap>" for k in range(1, len(partes) + 1)) + "\n</sitemapindex>\n")
    for nome in velhas:
        (RAIZ / nome).unlink()
    return len(linhas)


def _junta_membros(oficiais: list[dict], do_tse: list[dict]) -> list[dict]:
    """Lista oficial da Casa por cima da lista do TSE. Quem é a mesma pessoa (mesmo id) mantém o que veio do TSE (votos,
    situação na eleição, eleição de 2026); nome, partido e foto passam a ser os da Casa, que são os de hoje. "extras": true
    marca quem tem dados/pessoas/<id>.json (propostas, votações, gastos), para a página do perfil buscar esse arquivo."""
    tse = {m["id"]: m for m in do_tse}
    out = []
    for m in oficiais:
        p = dict(tse.get(m["id"], {}))
        for k in ("id", "nome", "nomeCivil", "partido", "genero", "foto", "url", "exercicio", "exercicio_en"):
            if m.get(k) not in (None, ""):
                p[k] = m[k]
        if (PESSOAS / f"{m['id']}.json").exists():
            p["extras"] = True
        else:
            p.pop("extras", None)
        out.append(p)
    return sorted(out, key=lambda x: chave_nome(x.get("nome") or ""))


def _canais_lai() -> tuple[dict, dict]:
    """dados/manual/canais-lai.json: o canal oficial de pedido de informação (Lei de Acesso à Informação) de Casas que o
    coletor não traz, conferido à mão: {"assembleias": {"RJ": {"sic", "conferido"}}, "camaras": {"<IBGE>": {...}}}."""
    c = ler_json(DADOS / "manual" / "canais-lai.json") or {}
    return c.get("assembleias") or {}, c.get("camaras") or {}


def _info_casa(a: dict, canal: dict | None = None, conferido: str | None = None) -> dict:
    """O que a página do estado ou da cidade mostra sobre a Casa: o que o site já tem dela (cobertura), as notas (o que falta
    e por quê), o site oficial, o canal oficial de pedido de informação (Lei de Acesso à Informação), se houver, e a data da
    última leitura completa do site oficial ("conferido", do índice dados/legislativos.json; sem ele, a data do arquivo da
    Casa): o site mostra essa data, para ficar claro quando uma Casa não pôde ser lida há algum tempo."""
    d = {k: a[k] for k in ("casa", "casa_en", "sigla", "site", "sic", "cobertura", "notas", "notas_en") if a.get(k)}
    if not d.get("sic") and (canal or {}).get("sic"):
        d["sic"] = canal["sic"]
    datas = [x for x in (conferido, a.get("atualizado")) if isinstance(x, str) and re.match(r"\d{4}-\d{2}-\d{2}", x)]
    if datas:
        d["conferido"] = max(x[:10] for x in datas)
    return d


def _prefeituras() -> tuple[dict, dict]:
    """dados/prefeituras/<UF>.json (scripts/municipios/diarios.py): as leis e os vetos de cada prefeitura contados no
    Diário Oficial ou nas páginas oficiais de legislação do município, só onde a contagem é segura ({IBGE: bloco
    "executivo"}), e, nas outras cidades lidas, o motivo e onde conferir ({IBGE: {tipo, nome, url, motivo, ...}})."""
    contadas, fora = {}, {}
    for arq in sorted((DADOS / "prefeituras").glob("*.json")):
        d = ler_json(arq) or {}
        for ibge, c in (d.get("cidades") or {}).items():
            ex = (c or {}).get("executivo")
            if isinstance(ex, dict) and (ex.get("leisSancionadas") is not None or ex.get("vetos") is not None):
                contadas[str(ibge)] = {k: v for k, v in ex.items() if k != "conferencia"}  # conferencia: só para quem confere
        for ibge, f in (d.get("fora") or {}).items():
            if isinstance(f, dict) and f.get("motivo"):
                fora[str(ibge)] = {k: f[k] for k in ("tipo", "nome", "nome_en", "url", "motivo", "motivo_en", "data") if f.get(k)}
    return contadas, fora


def _executivo_sapl(ibge: str) -> dict:
    """O bloco "executivo" do prefeito que o SAPL da Câmara já dá: no arquivo da cidade (dados/camaras/extras/<IBGE>.json)
    ou, nas capitais com arquivo próprio, em dados/pessoas/pref-<IBGE>.json."""
    pid = f"pref-{ibge}"
    x = (((ler_json(EXTRAS_CIDADES / f"{ibge}.json") or {}).get("pessoas")) or {}).get(pid) or ler_json(PESSOAS / f"{pid}.json") or {}
    return (x.get("executivo") if isinstance(x, dict) else None) or {}


def _executivo_prefeito(ibge: str, p, bloco: dict | None) -> dict | None:
    """O bloco "executivo" dos Diários Oficiais vai para a ficha do prefeito só se for de quem governa hoje, desde o
    começo do período contado: fica fora quem assumiu numa eleição suplementar sem a data da posse na ficha (a conta
    juntaria as leis de quem governava antes) e quem está "a confirmar". Onde o SAPL da Câmara já tem a contagem, vale a do
    SAPL (o perfil põe o arquivo extra por cima da ficha); se o SAPL tiver só os vetos (ou só as leis), o bloco dos Diários
    fica na ficha e o perfil junta os dois (js/pessoa.js, juntaExecutivo), cada número com a sua fonte e a sua nota, desde
    que os dois contem do mesmo dia."""
    if not bloco or not isinstance(p, dict) or not p.get("nome") or p.get("aConfirmar"):
        return None
    if "suplementar" in (p.get("situacao") or "") and not p.get("desde"):
        return None
    if ((bloco.get("periodo") or {}).get("inicio") or "") < (p.get("desde") or vigente("prefeito")["inicio"]):
        return None
    sapl = _executivo_sapl(ibge)
    if sapl:
        soma = ((sapl.get("leisSancionadas") is None and bloco.get("leisSancionadas") is not None) or
                (sapl.get("vetos") is None and bloco.get("vetos") is not None))
        ini = (sapl.get("periodo") or {}).get("inicio")
        if not soma or (ini and ini != (bloco.get("periodo") or {}).get("inicio")):
            return None
    return bloco


def _onde_ver_cidades() -> tuple[int, int]:
    """dados/municipios/<UF>.json (scripts/municipios/mapear.py: site oficial da Câmara e da prefeitura, sistema de
    propostas, pedido de informação, Diário Oficial) e os canais conferidos à mão (dados/manual/canais-lai.json) -> campo
    "onde" de cada dados/cidades/<UF>/<IBGE>.json. É o que o perfil mostra quando a Câmara ou a prefeitura não publica um
    dado num formato que o site consiga ler: onde ver e como pedir, em vez de "Em breve".
    Também dados/prefeituras/<UF>.json: as leis e os vetos contados vão para prefeito.executivo (_executivo_prefeito), e o
    motivo das cidades em que a contagem não é segura vai para onde.prefeitura.leis, com o link para conferir.
    Devolve (cidades com "onde" atualizado, prefeitos com as leis e vetos atualizados)."""
    ondes: dict[str, dict] = {}
    for arq in sorted((DADOS / "municipios").glob("*.json")):
        for ibge, o in (((ler_json(arq) or {}).get("cidades")) or {}).items():
            if isinstance(o, dict):
                ondes[str(ibge)] = {k: dict(o[k]) for k in ("camara", "prefeitura") if isinstance(o.get(k), dict) and o[k]}
    for ibge, canal in _canais_lai()[1].items():
        cam = ondes.setdefault(str(ibge), {}).setdefault("camara", {})
        if canal.get("sic") and not cam.get("sic"):
            cam["sic"] = canal["sic"]
            cam.setdefault("conferido", canal.get("conferido"))
    # Câmaras com coletor próprio (dados/camaras/<IBGE>.json): o coletor leu o site oficial da Câmara (do Brasil, quando o
    # site recusa o robô do GitHub), e as notas dele dizem o que entra e o que não entra, e por quê. Ali, o palpite do mapa
    # (ex.: "não achamos as proposições a partir da página inicial") não vale: sai o motivo do mapa, as propostas contam
    # como publicadas quando o coletor as lê, e o site da Câmara vem do coletor quando o mapa não o achou.
    for k_arq in sorted((DADOS / "camaras").glob("*.json")):
        k = ler_json(k_arq) or {}
        cam = (ondes.get(str(k.get("ibge") or k_arq.stem)) or {}).get("camara")
        if not cam:
            continue
        if k.get("site") and not cam.get("site"):
            cam["site"] = k["site"]
        if cam.get("propostasOnline") is False or cam.get("motivo"):
            cam["propostasOnline"] = True if (k.get("cobertura") or {}).get("propostas") else None
            cam.pop("motivo", None)
            cam.pop("motivo_en", None)
    contadas, fora = _prefeituras()
    for ibge, f in fora.items():
        ondes.setdefault(ibge, {}).setdefault("prefeitura", {})["leis"] = f
    n = n_ex = 0
    for c_arq in sorted((DADOS / "cidades").glob("*/*.json")):
        c = ler_json(c_arq)
        if not isinstance(c, dict):
            continue
        mudou = False
        onde = ondes.get(c_arq.stem)
        if c.get("onde") != onde:
            if onde:
                c["onde"] = onde
            else:
                c.pop("onde", None)
            mudou = True
            n += 1
        p = c.get("prefeito")
        if isinstance(p, dict):
            ex = _executivo_prefeito(c_arq.stem, p, contadas.get(c_arq.stem))
            if p.get("executivo") != ex:
                if ex:
                    p["executivo"] = ex
                else:
                    p.pop("executivo")
                mudou = True
                n_ex += 1
        if mudou:
            salvar_json(c_arq, sem_mudar_data(c, c_arq))
    return n, n_ex


def _marcar_extras_cidades() -> int:
    """Marca "extras": "cidade" em quem tem dados no arquivo da cidade (dados/camaras/extras/<IBGE>.json): vereadores,
    prefeito e vice; e tira a marca de quem saiu do arquivo (o perfil não pede um arquivo à toa). Quem tem arquivo próprio
    (dados/pessoas/<id>.json) continua com "extras": true."""
    n = 0
    com_arquivo = {f.stem: f for f in EXTRAS_CIDADES.glob("*.json")}
    for c_arq in sorted((DADOS / "cidades").glob("*/*.json")):
        f = com_arquivo.get(c_arq.stem)
        c = ler_json(c_arq)
        if not isinstance(c, dict):
            continue
        ex_p = ((ler_json(f) or {}).get("pessoas") or {}) if f else {}
        ids = {i for i, x in ex_p.items() if not _extras_de_antes(c.get("prefeito"), i, x)}  # prefeitos 2026
        mudou = False
        for p in [c.get("prefeito"), c.get("vice")] + list((c.get("vereadores") or {}).get("membros") or []):
            if not isinstance(p, dict) or p.get("extras") is True:
                continue
            if p.get("id") in ids and p.get("extras") != "cidade":
                p["extras"] = "cidade"
                mudou = True
            elif p.get("extras") == "cidade" and p.get("id") not in ids:
                p.pop("extras")
                mudou = True
        if mudou:
            salvar_json(c_arq, sem_mudar_data(c, c_arq))
            n += 1
    return n


# prefeitos 2026 (frente prefeitos-r7): os dados a mais do prefeito (o que o SAPL da Câmara contou) começam numa data. Se a
# ficha da cidade mostra outra pessoa no cargo, assumida depois dessa data ("desde"), ou não mostra ninguém (quem governa
# hoje não foi conferido), esses dados são de quem governava antes: o perfil não os pede até o coletor da Câmara contar de
# novo, a partir do "desde" da ficha (scripts/camaras/_sapl.py, prefeito).
def _extras_de_antes(pref, pid: str, x) -> bool:
    if not isinstance(pref, dict) or pid != pref.get("id") or not str(pid).startswith("pref-") or not isinstance(x, dict):
        return False
    if not pref.get("nome"):
        return True
    desde = (pref.get("desde") or "")[:10]
    ini = ((x.get("executivo") or {}).get("periodo") or {}).get("inicio")
    if not ini:
        m = re.search(r"data_apresentacao_0=(\d{2})%2F(\d{2})%2F(\d{4})", ((x.get("propostas") or {}).get("fonte") or {}).get("url") or "")
        ini = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
    return bool(desde and ini and ini < desde)


def _lista_velha(a: dict, inicio: str) -> bool:
    """A lista oficial é de uma legislatura que já acabou? Acontece logo depois de uma posse, se o coletor falhou ou se a
    Casa ainda não trocou a lista: aí fica a lista do TSE, que já é a de quem foi eleito para o mandato em curso.
    "atualizado" só muda quando o conteúdo muda (comum.sem_mudar_data)."""
    leg = a.get("legislatura") or {}
    if leg.get("fim") and leg["fim"] < hoje():
        return True
    return (a.get("atualizado") or "") < inicio


# eleitos 2026 (até a posse): frente "quem assume" (dados/eleitos/, feitos por scripts/eleitos.py)
def _eleitos_2026() -> str:
    """Quem foi eleito em 2026 e ainda não tomou posse entra na busca (os perfis e26- e os vereadores eleitos) e ganha o
    selo "eleito em 2026" nas fichas das cidades. O trabalho fica em scripts/eleitos.py (busca_e_selos)."""
    if not any((DADOS / "eleitos").glob("*.json")):
        return "sem dados/eleitos"
    import eleitos
    return eleitos.busca_e_selos()


# eleitos 2026 (até a posse): os perfis e26- no sitemap.xml
def _eleitos_sitemap() -> list:
    if not any((DADOS / "eleitos").glob("*.json")):
        return []
    import eleitos
    return eleitos.urls_sitemap()


# ministros do STF (dados/stf.json, feito por scripts/stf.py): busca e sitemap
def _stf_busca() -> str:
    """Os ministros do STF entram na busca (dados/busca.json) como "Ministro(a) do Supremo Tribunal Federal", sem estado,
    partido nem cidade. Quem saiu do tribunal sai da busca na mesma rodada."""
    d = ler_json(DADOS / "stf.json") or {}
    b_arq = DADOS / "busca.json"
    busca = [x for x in (ler_json(b_arq, []) or []) if not str(x[0]).startswith("stf-")]
    novos = [[m["id"], m["nome"], ("Ministra" if m.get("genero") == "F" else "Ministro") + " do Supremo Tribunal Federal", None, None, None]
             for m in d.get("ministros") or [] if m.get("id") and m.get("nome")]
    busca += novos
    busca.sort(key=lambda x: (chave_nome(x[1] or ""), x[0]))
    salvar_json(b_arq, busca)
    return f"{len(novos)} ministros" if novos else "sem dados/stf.json"


def _stf_sitemap() -> list:
    d = ler_json(DADOS / "stf.json") or {}
    return [(f"pessoa.html?id={m['id']}", d.get("atualizado")) for m in d.get("ministros") or [] if m.get("id")]


def juntar_legislativos() -> tuple[int, int]:
    """dados/assembleias/<UF>.json e dados/camaras/<IBGE>.json (scripts/legislativos.py) -> listas das páginas do estado e
    da cidade, no lugar da lista de eleitos do TSE. A busca (dados/busca.json) passa a ter quem está na lista oficial
    (inclusive suplentes que assumiram); vereadores não entram na busca (aparecem na página da cidade)."""
    na = nc = 0
    busca_uf: dict[str, list] = {}
    canais_ale, canais_cam = _canais_lai()
    # a data da última leitura completa de cada Casa (scripts/legislativos.py)
    idx = ler_json(DADOS / "legislativos.json", {}) or {}
    conf_ale = {k: (v or {}).get("conferido") for k, v in (idx.get("assembleias") or {}).items()}
    conf_cam = {k: (v or {}).get("conferido") for k, v in (idx.get("camaras") or {}).items()}
    for arq in sorted((DADOS / "assembleias").glob("*.json")):
        a = ler_json(arq) or {}
        e_arq = DADOS / "estados" / f"{a.get('uf') or arq.stem}.json"
        e = ler_json(e_arq)
        if not e or not a.get("membros"):
            continue
        if _lista_velha(a, vigente("deputado_estadual", uf=e["uf"])["inicio"]):
            log(f"  {arq.name}: lista de uma legislatura que já acabou; fica a lista do TSE")
            continue
        de = e.get("deputadosEstaduais") or {}
        de["membros"] = _junta_membros(a["membros"], de.get("membros") or [])
        busca_uf[e["uf"]] = [[m["id"], m.get("nome"), ("Deputada" if m.get("genero") == "F" else "Deputado") +
                              (" distrital" if e["uf"] == "DF" else " estadual"), e["uf"], m.get("partido"), None]
                             for m in de["membros"]]
        de["total"] = len(de["membros"])
        de["oficial"] = True
        de["aviso"] = f"Lista oficial da {a.get('casa') or 'Assembleia Legislativa'}: quem está no cargo hoje, inclusive suplentes que assumiram."
        de["aviso_en"] = (f"Official list from the {a.get('casa_en') or 'Legislative Assembly'}: who is in office today, "
                          "including substitutes who took a seat.")
        de["fonte"] = a.get("fonte") or de.get("fonte")
        de["infoCasa"] = _info_casa(a, canais_ale.get(e["uf"]), conf_ale.get(e["uf"]))
        e["deputadosEstaduais"] = de
        salvar_json(e_arq, sem_mudar_data(e, e_arq))
        na += 1
    for arq in sorted((DADOS / "camaras").glob("*.json")):
        k = ler_json(arq) or {}
        ibge = str(k.get("ibge") or arq.stem)
        c_arq = DADOS / "cidades" / (k.get("uf") or "") / f"{ibge}.json"
        c = ler_json(c_arq)
        if not c:
            continue
        if not k.get("membros"):
            # a Câmara tem dados abertos, mas a lista oficial não passou na conferência de vagas: fica a lista do TSE, e a
            # página da cidade e o quadro "Onde ver mais" ganham as notas e o site da Câmara
            v = c.get("vereadores") or {}
            info = _info_casa(k, canais_cam.get(ibge), conf_cam.get(ibge))
            if info.get("cobertura") and v.get("infoCasa") != info:
                v["infoCasa"] = info
                c["vereadores"] = v
                salvar_json(c_arq, sem_mudar_data(c, c_arq))
            continue
        if _lista_velha(k, vigente("vereador")["inicio"]):
            log(f"  camaras/{arq.name}: lista de uma legislatura que já acabou; fica a lista do TSE")
            continue
        v = c.get("vereadores") or {}
        v["membros"] = _junta_membros(k["membros"], v.get("membros") or [])
        v["total"] = len(v["membros"])
        v["oficial"] = True
        v["aviso"] = f"Lista oficial da {k.get('casa') or 'Câmara Municipal'}: quem está no cargo hoje, inclusive suplentes que assumiram."
        v["aviso_en"] = (f"Official list from the {k.get('casa_en') or 'City Council'}: who is in office today, "
                         "including substitutes who took a seat.")
        v["fonte"] = k.get("fonte") or v.get("fonte")
        v["infoCasa"] = _info_casa(k, canais_cam.get(ibge), conf_cam.get(ibge))
        c["vereadores"] = v
        salvar_json(c_arq, sem_mudar_data(c, c_arq))
        nc += 1
    if busca_uf:
        b_arq = DADOS / "busca.json"
        busca = [x for x in (ler_json(b_arq, []) or [])
                 if not any(x[0].startswith(f"dest-{uf}-") for uf in busca_uf)]
        for itens in busca_uf.values():
            busca += itens
        busca.sort(key=lambda x: (chave_nome(x[1] or ""), x[0]))
        salvar_json(b_arq, busca)
    return na, nc


def main() -> None:
    fed = ler_json(DADOS / "tse" / "federais.json", {}) or {}
    cache = carregar_simples()
    log(f"TSE federais: {len(fed)} | explicações simples no cache: {len(cache)}")

    # ---------- perfis federais (e as propostas das Assembleias e Câmaras, que também ganham explicação simples)
    escritos = 0
    for f in sorted(PESSOAS.glob("*.json")):
        p = ler_json(f)
        if not isinstance(p, dict):
            continue
        lista = (p.get("propostas") or {}).get("lista") or []
        for x in lista:
            if x.get("ementa"):
                x["ementa"] = sem_documentos(x["ementa"])
        if re.match(r"(dep|sen|pres|vp)-", p.get("id") or f.stem):
            t = fed.get(p.get("id")) or {}
            for campo in ("eleicao", "bens"):
                if t.get(campo) is not None:
                    p[campo] = t[campo]
            if t.get("eleicao2026") is not None:
                p["eleicao2026"] = com_en(t["eleicao2026"])
            mesma_regua(p, t)
        aplicar_simples(lista, cache)
        if salvar_json(f, sem_mudar_data(p, f)):
            escritos += 1
    # as pessoas dos arquivos por cidade (Câmaras Municipais e prefeituras): o mesmo cuidado com as propostas
    for f in sorted(EXTRAS_CIDADES.glob("*.json")):
        b = ler_json(f)
        if not isinstance(b, dict):
            continue
        for p in (b.get("pessoas") or {}).values():
            lista = (p.get("propostas") or {}).get("lista") or []
            for x in lista:
                if x.get("ementa"):
                    x["ementa"] = sem_documentos(x["ementa"])
            aplicar_simples(lista, cache)
        if salvar_json(f, sem_mudar_data(b, f)):
            escritos += 1
    log(f"perfis reescritos: {escritos}")
    log(f"votações com a explicação simples atualizada: {votacoes.atualizar_simples(cache)}")

    # ---------- listas da Câmara e do Senado
    for nome in ("camara.json", "senado.json"):
        cam = DADOS / nome
        d = ler_json(cam)
        if not d:
            continue
        for m in d.get("membros", []):
            e = (fed.get(m["id"]) or {}).get("eleicao2026")
            m["eleicao2026"] = resumo2026(com_en(e)) if e else m.get("eleicao2026")
        salvar_json(cam, sem_mudar_data(d, cam))

    # ---------- presidente e vice
    ex_arq = DADOS / "executivo.json"
    ex = ler_json(ex_arq)
    if ex:
        for k in ("presidente", "vice"):
            if ex.get(k):
                e = (fed.get(ex[k]["id"]) or {}).get("eleicao2026")
                if e:
                    ex[k]["eleicao2026"] = resumo2026(com_en(e))
        salvar_json(ex_arq, sem_mudar_data(ex, ex_arq))

    # ---------- estados: txt_en na eleição de 2026
    diarios = ((ler_json(DADOS / "manual" / "diarios-oficiais.json") or {}).get("estados")) or {}
    for arq in sorted((DADOS / "estados").glob("*.json")):
        e = ler_json(arq)
        if not e:
            continue
        for k in ("governador", "vice"):
            if isinstance(e.get(k), dict) and e[k].get("eleicao2026"):
                e[k]["eleicao2026"] = com_en(e[k]["eleicao2026"])
        # o que o governo do estado fez (projetos enviados à Assembleia, leis e vetos) fica em dados/pessoas/gov-<UF>.json
        for k, pre in (("governador", "gov"), ("vice", "vgov")):
            p = e.get(k)
            if isinstance(p, dict):
                if (PESSOAS / f"{pre}-{e.get('uf') or arq.stem}.json").exists():
                    p["extras"] = True
                else:
                    p.pop("extras", None)
        # Diário Oficial do estado (dados/manual/diarios-oficiais.json): o quadro "Onde ver mais" do perfil do governador
        g, dio = e.get("governador"), diarios.get(e.get("uf") or arq.stem)
        if isinstance(g, dict):
            if dio and dio.get("url"):
                g["diarioOficial"] = {k: dio[k] for k in ("nome", "url") if dio.get(k)}
            else:
                g.pop("diarioOficial", None)
        for m in (e.get("deputadosEstaduais") or {}).get("membros", []):
            if m.get("eleicao2026"):
                m["eleicao2026"] = com_en(m["eleicao2026"])
        salvar_json(arq, sem_mudar_data(e, arq))
    a, c = juntar_legislativos()
    log(f"listas oficiais: {a} Assembleias e {c} Câmaras Municipais")
    log(f"cidades com dados a mais num arquivo por cidade: {_marcar_extras_cidades()} atualizadas")
    n_onde, n_ex = _onde_ver_cidades()
    log(f"cidades com \"onde ver\" (site oficial, pedido de informação, Diário Oficial) atualizado: {n_onde}")
    log(f"prefeitos com as leis e os vetos dos Diários Oficiais atualizados: {n_ex}")
    log(f"eleitos em 2026 (até a posse): {_eleitos_2026()}")
    log(f"ministros do STF na busca: {_stf_busca()}")  # ministros do STF
    log(f"dados/cidades.json: {indice_cidades()} cidades")
    log(f"sitemap.xml: {sitemap()} endereços")
    log("pronto")


if __name__ == "__main__":
    main()
