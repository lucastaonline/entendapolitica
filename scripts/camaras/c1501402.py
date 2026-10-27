"""Câmara Municipal de Belém (PA): a lista oficial de vereadores (www.cmb.pa.gov.br/vereadores) e as propostas dos
vereadores desde 1º/1/2025, lidas do site oficial da Câmara.

Propostas (propostas()): as listas oficiais de projetos de lei do Legislativo (PLL), de decreto legislativo (PDL), de lei
complementar, de resolução (PR) e de emenda à Lei Orgânica, pelos arquivos que o próprio site exporta (JSON) ou pela lista da
página, e a página de cada projeto (www.cmb.pa.gov.br/legislacao/norma/<id>), que diz os autores (o primeiro é o autor
principal) e o andamento. O andamento publicado é quase sempre só a data em que o projeto foi cadastrado no sistema
("Cadastrado no Sistema"), até nos projetos que viraram lei: aí a situação fica "não classificada" (nota da Câmara), e a data
é essa; quando a página mostra outro passo ("Protocolado", "Aprovado"), ele vai para a regra comum das Câmaras.
A primeira carga (umas 1.500 páginas, 5 s entre pedidos, como o robots.txt pede) leva várias rodadas; até terminar, ficam
publicadas as propostas de antes (nada pela metade). Depois, cada rodada lê as listas e só as páginas novas e um rodízio das
outras (cada página de novo a cada 90 dias; no máximo 30 páginas por rodada).

Prefeitura: as páginas "Projetos de Lei do Executivo" e "Projetos de Lei Complementar do Executivo" do site estão vazias, e
a lista de processos não tem nenhum do Executivo: os projetos do prefeito não entram (nota da Câmara). Se a Câmara publicar,
entram sozinhos.
"""
import html
import re
import time

import regional
from comum import fonte, hoje, ler_json, log, nome_proprio, salvar_json

from . import _base as B
from . import _capitais_c as C

IBGE, UF, SITE = "1501402", "PA", "https://www.cmb.pa.gov.br"
CASA = {"casa": "Câmara Municipal de Belém", "casa_en": "Belém City Council", "sigla": "CMB", "site": SITE,
        "sistema": "Portal oficial (HTML e arquivos exportados)"}
PREFIXO = f"cm{IBGE}"
ESTADO = B.PASTA_CACHE / IBGE / "propostas.json"
PAUSA = 5.0  # o robots.txt pede 5 s entre pedidos (Crawl-delay)
# página da lista -> (tipo comum do site, como ler a lista, é do Executivo?)
LISTAS = {
    "projetos-de-lei": ("PL", "json", False),
    "projetos-de-decreto-legislativo": ("PDL", "json", False),
    "projetos-de-lei-complementar": ("PLP", "json", False),
    "projetos-de-resolucao": ("PRC", "html", False),
    "projetos-de-emenda-a-lei-organica": ("PELO", "html", False),
    "projetos-de-lei-do-executivo": ("PL", "json", True),
    "projetos-de-lei-complementar-do-executivo": ("PLP", "json", True),
}
PAGINA = SITE + "/legislacao/norma/{id}?fonte=api&pagina={pagina}"
RELER_DIAS = 90
PAGINAS_DIA = 30  # páginas por rodada depois da primeira carga (as novas primeiro; depois, o rodízio)
FALHAS_SEGUIDAS = 5  # páginas seguidas com erro = o site está fora do ar: a rodada para (senão, pula só a página)
SEM_ANDAMENTO = ("A Câmara não publica o andamento desta proposta no site", "The City Council does not publish this bill's progress on its website")
# no bloco de propostas de cada vereador (aparece no topo da lista): os números de aprovadas e de leis ficam menores (ou em
# zero) porque a Câmara quase nunca publica a situação, e não porque nenhuma foi aprovada
NOTA_SITUACAO = ("A Câmara de Belém quase nunca publica no site o andamento dos projetos (em geral, só a data em que cada um "
                 "foi cadastrado), nem diz de qual projeto veio cada lei. Por isso, aqui a situação da maioria das propostas "
                 "aparece como não classificada, e os números de aprovadas e de leis não mostram tudo o que foi aprovado: um "
                 "zero não quer dizer que nenhuma foi aprovada.",
                 "The Belém City Council almost never publishes the progress of bills on its website (usually, only the date "
                 "each one was entered), nor which bill each law came from. So here the status of most bills shows as not "
                 "classified, and the numbers of approved bills and laws do not show everything that was approved: a zero "
                 "does not mean that none was approved.")


def _lista(rede: C.Rede, pagina: str, modo: str) -> list[dict]:
    """[{id, numero, ano, ementa, proponente}] de uma lista oficial (arquivo JSON exportado pelo site, ou a lista que a página
    da lista traz para mostrar na tela)."""
    if modo == "json":
        d = rede.json(f"{SITE}/legislacao/{pagina}/exportar?situacao=todos&ordem=recent&per_page=10&formato=json")
        if isinstance(d, dict):
            d = next((v for v in d.values() if isinstance(v, list)), [])
        return [{"id": x.get("id"), "numero": x.get("numero"), "ano": x.get("ano"), "ementa": x.get("ementa"),
                 "proponente": x.get("proponente")} for x in d if x.get("id")]
    t = rede.pagina(f"{SITE}/legislacao/{pagina}?situacao=todos&ordem=recent&per_page=100&page=1")
    m = re.search(r"const legislacoesData = (\[.*?\]);", t, re.S)
    if not m:
        raise RuntimeError(f"a página {pagina} mudou (sem a lista)")
    import json
    out = []
    for x in json.loads(m.group(1)):
        num = re.match(r"\s*(\d+)\s*/\s*(\d{4})", x.get("number") or "")
        out.append({"id": x.get("id"), "numero": num.group(1) if num else None, "ano": x.get("year"), "ementa": x.get("ementa"),
                    "proponente": None})
    return [x for x in out if x["id"]]


def _ler_pagina(t: str) -> dict:
    """Sigla, espécie, ementa, autores ([nome, partido]) e andamento ([data, texto], do mais novo para o mais antigo) da
    página de um projeto."""
    i, j = t.find("<main"), t.find("</main>")
    s = t[i:j] if i >= 0 and j > i else t
    sigla = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    especie = re.search(r"</h1>\s*<p[^>]*>(.*?)</p>", s, re.S)
    if not sigla:
        raise RuntimeError("a página do projeto mudou (sem a sigla)")
    autores = []
    k = s.find("Autor(es)")
    if k >= 0:
        bloco = s[k:s.find("Tramitação", k) if s.find("Tramitação", k) > 0 else len(s)]
        for nome, resto in re.findall(r'<p class="font-bold[^"]*">(.*?)</p>(.*?)</div>', bloco, re.S):
            part = re.search(r'<p class="text-xs[^"]*">(.*?)</p>', resto, re.S)
            autores.append([C.texto(nome), C.texto(part.group(1)) if part else None])
    tram = []
    for card in re.findall(r'<div class="tram-card.*?(?=<div class="tram-card|<!-- Observações|</main>|$)', s, re.S):
        ps = [C.texto(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", card, re.S)]
        data = next((C.data_iso(p) for p in ps if re.fullmatch(r"\d{2}/\d{2}/\d{4}", p)), None)
        txts = [p for p in ps if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", p) and p]
        tram.append([data, " ".join(txts)[:400]])
    tram.sort(key=lambda x: x[0] or "", reverse=True)
    return {"sigla": C.texto(sigla.group(1)), "especie": C.texto(especie.group(1)) if especie else None, "autores": autores,
            "tram": tram}


def propostas(rede: C.Rede, h: str) -> dict:
    """Lê (ou continua lendo) as listas e as páginas dos projetos desde 2025. Devolve o estado ({"itens": ...}), com
    "_completo" (a primeira carga terminou) e a contagem do que falta. Uma página que dá erro fica marcada ("erro": data) e
    é tentada de novo na rodada seguinte, sem travar as outras; 5 erros seguidos (o site fora do ar) param a rodada."""
    est = ler_json(ESTADO, {}) or {}
    listas, itens = est.setdefault("listas", {}), est.setdefault("itens", {})
    primeira = not est.get("completo_em")
    n0, falhas = rede.n, 0
    try:
        for pagina, (comum, modo, executivo) in LISTAS.items():
            if listas.get(pagina) == h:
                continue
            if C.sem_tempo():
                raise TimeoutError("fim do tempo da rodada")
            novos = {}
            for x in _lista(rede, pagina, modo):
                try:
                    ano = int(str(x.get("ano") or "0")[:4])
                except ValueError:
                    ano = 0
                if ano < int(B.INICIO[:4]):
                    continue
                novos[str(x["id"])] = {"pag": pagina, "comum": comum, "exec": executivo, "numero": x.get("numero"), "ano": ano,
                                       "ementa": re.sub(r"\s+", " ", x.get("ementa") or "").strip() or None,
                                       "prop": (x.get("proponente") or "").strip() or None}
            guardados = sum(1 for it in itens.values() if it.get("pag") == pagina)
            if guardados >= 10 and len(novos) < guardados / 2:  # resposta de erro ou site fora do ar: não apaga o que foi lido
                raise RuntimeError(f"a lista {pagina} veio com {len(novos)} projetos (antes: {guardados})")
            for k, nv in novos.items():
                itens.setdefault(k, {}).update(nv)
            for k in [k for k, it in itens.items() if it.get("pag") == pagina and k not in novos]:
                itens.pop(k)  # saiu da lista oficial
            listas[pagina] = h
            salvar_json(ESTADO, est)
        faltam = sorted((k for k, it in itens.items() if (not it.get("lido") or it["lido"] < C.menos(h, RELER_DIAS))
                         and it.get("erro") != h),
                        key=lambda k: (bool(itens[k].get("lido")), itens[k].get("lido") or "", -int(k)))
        for n, k in enumerate(faltam):
            if C.sem_tempo() or (not primeira and n >= PAGINAS_DIA):
                break
            it = itens[k]
            try:
                d = _ler_pagina(rede.pagina(PAGINA.format(id=k, pagina=it["pag"])))
            except (RuntimeError, ValueError, OSError) as erro:  # a página saiu do ar ou mudou: fica como estava (sem ser
                it["erro"] = h                                      # lida, não entra) e é tentada na próxima rodada
                falhas += 1
                log(f"  CMB: projeto {k}: {type(erro).__name__}: {str(erro)[:120]} (tenta de novo na próxima rodada)")
                if falhas >= FALHAS_SEGUIDAS:
                    raise
                continue
            falhas = 0
            it.update(d)
            it["lido"] = h
            it.pop("erro", None)
            if n % 20 == 19:
                salvar_json(ESTADO, est)
    except (TimeoutError, RuntimeError, OSError, ValueError) as erro:
        log(f"  CMB: propostas: {type(erro).__name__}: {str(erro)[:150]} ({rede.n - n0} pedidos); continua na próxima rodada")
    sem = sum(1 for it in itens.values() if not it.get("lido") and not it.get("erro"))
    completo = all(listas.get(p) for p in LISTAS) and not sem
    if completo and primeira:
        est["completo_em"] = h
    salvar_json(ESTADO, est)
    est["_completo"] = completo or not primeira
    est["_faltam"], est["_total"], est["_pedidos"] = sem, len(itens), rede.n - n0
    return est


def situacao(it: dict) -> tuple:
    """(status, statusTxt, statusTxt_en, situação oficial, dataStatus). O site mostra, no andamento de quase todos os
    projetos, só "Cadastrado no Sistema" (com a data; às vezes também "Documento Importado Digitalmente", que também não diz
    nada da situação): sem outra informação, a situação fica "não classificada", com o motivo. Quando a página mostra outro
    passo ("Protocolado", "Aprovado"), o texto oficial do passo mais novo vai para a regra comum das Câmaras."""
    tram = [t for t in it.get("tram") or [] if t[1]]
    outros = [t for t in tram if not re.match(r"(cadastrad[oa] no sistema|documento importado)", B.norm(t[1]))]
    if not outros:
        return "outra", SEM_ANDAMENTO[0], SEM_ANDAMENTO[1], tram[0][1] if tram else None, None
    data, txt = outros[0]
    st, s_txt, s_en = B.situacao(txt, None, None, None, it.get("comum"))
    if st == "aprovada" and not s_txt:  # o site quase nunca mostra os passos seguintes (sanção, promulgação, lei)
        s_txt, s_en = ("Aprovada pela Câmara (o site não mostra o que aconteceu depois)",
                       "Approved by the City Council (the website does not show what happened next)")
    if st == "outra" and not s_txt:
        s_txt = f"Situação na Câmara: {txt}"
    return st, s_txt, s_en, txt, data


def _autores(it: dict) -> list[str]:
    """Os nomes dos autores, na ordem da página (ou do "proponente" da lista, se a página não trouxer)."""
    nomes = [a[0] for a in it.get("autores") or [] if a and a[0]]
    if not nomes and it.get("prop"):
        nomes = [p.strip() for p in re.split(r"(?<=\))\s*,\s*|(?<=\))\s+e\s+", it["prop"]) if p.strip()]
    return nomes


def coletar() -> dict:
    t0 = time.time()
    h = hoje()
    rede = C.Rede(IBGE, PAUSA)
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    pessoas = []
    for href, dnome, dpart, corpo in re.findall(r'<a href="([^"]+/vereador/[^"]+)"\s+class="vereador-card[^"]*"\s+data-name="([^"]*)"\s+data-partido="([^"]*)">(.*?)</a>', t, re.S):
        foto = re.search(r'<img[^>]+src="([^"]+)"', corpo)
        nome = re.search(r"<h3[^>]*>(.*?)</h3>", corpo, re.S)
        sigla = re.search(r"</h3>\s*<span[^>]*>(.*?)</span>", corpo, re.S)
        nome = html.unescape(nome.group(1)).strip() if nome else None
        if not nome:
            continue
        dnome = html.unescape(dnome).strip()
        civil = dnome[len(nome):].strip() if dnome.lower().startswith(nome.lower()) else None
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": nome, "nomeCivil": nome_proprio(civil) if civil else None,
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else dpart.upper(),
                        "foto": foto.group(1) if foto else None, "url": href})
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores (portal oficial)", f"{SITE}/vereadores", h)
    membros, extras, tse = C.lista_oficial(IBGE, UF, CASA, pessoas, 35)
    for m in membros:
        m.pop("_chave", None)
        m.pop("_cand", None)

    est = propostas(rede, h)
    notas = []
    escopo = (B.ESCOPO + ", segundo o site oficial da Câmara.", B.ESCOPO_EN + ", according to the City Council's official website.")
    com_prop = False
    if est["_completo"]:
        por: dict[str, list] = {m["id"]: [] for m in membros}
        sem_ligacao: dict[str, int] = {}
        for k, it in (est.get("itens") or {}).items():
            if not it.get("lido") or it.get("exec"):
                continue
            st, txt, txt_en, situ, data_st = situacao(it)
            datas = [x[0] for x in it.get("tram") or [] if x[0]]
            data = min(datas) if datas else None
            sigla = it.get("sigla") or f"{it.get('numero')}/{it.get('ano')}"
            for i, nome in enumerate(_autores(it)):
                pid = C.ligar_nome(nome, membros, tse)
                if not pid:
                    sem_ligacao[nome] = sem_ligacao.get(nome, 0) + 1
                    continue
                p = regional.proposta(f"{PREFIXO}:{k}", sigla, it["comum"], data, it.get("ementa"), situ,
                                      PAGINA.format(id=k, pagina=it["pag"]), "autor" if i == 0 else "coautor", status=st,
                                      data_status=data_st, status_txt=txt)
                if txt_en:
                    p["statusTxt_en"] = txt_en
                if not any(q["id"] == p["id"] for q in por[pid]):
                    por[pid].append(p)
        if sem_ligacao:
            log("  CMB: autores fora da lista oficial de hoje (ficam fora): "
                + ", ".join(f"{n} ({q})" for n, q in sorted(sem_ligacao.items(), key=lambda kv: -kv[1])))
        for m in membros:
            f_prop = fonte(CASA["casa"], f"Projetos de {m['nome']} (site oficial: listas de projetos e a página de cada um)",
                           f"{SITE}/legislacao/projetos-de-lei", h)
            b = regional.bloco_propostas(por[m["id"]], escopo[0], escopo[1], f_prop)
            if any(p.get("statusTxt") == SEM_ANDAMENTO[0] for p in por[m["id"]]):
                b["nota"], b["nota_en"] = NOTA_SITUACAO
            extras[m["id"]]["propostas"] = b
            extras[m["id"]]["fontes"].append(f_prop)
        com_prop = True
    else:  # primeira carga em andamento: ficam as propostas já publicadas (as de antes, ou nenhuma)
        for pid, b in C.publicados(IBGE).items():
            if pid in extras:
                extras[pid]["propostas"] = b
                if b.get("fonte"):
                    extras[pid]["fontes"].append(b["fonte"])
                com_prop = True
    if com_prop:
        notas.append(("As propostas vêm das listas de projetos do site da Câmara e da página de cada projeto, que diz os autores "
                      "(o primeiro é o autor principal). A situação de quase todas as propostas fica sem classificar: no "
                      "andamento de quase todos os projetos, o site mostra só a data em que ele foi cadastrado no sistema, até "
                      "nos que viraram lei (quando a página mostra outro passo, como \"Aprovado\", ele entra). Os projetos de "
                      "quem não está na lista oficial de hoje não aparecem em nenhum perfil.",
                      "Bills come from the lists of bills on the City Council's website and from each bill's page, which names "
                      "the authors (the first one is the main author). The status of almost all bills is left unclassified: on "
                      "the progress of almost every bill, the website shows only the date it was entered into the system, even "
                      "for bills that became law (when the page shows another step, such as approval, it is used). Bills by "
                      "people who are not on today's official list do not appear on any profile."))
    else:
        notas.append(("As propostas dos vereadores não entram neste site: a Câmara lista os projetos só em páginas do site, sem o "
                      "autor de forma organizada e sem dados abertos.",
                      "Councilors' bills are not included on this site: the City Council lists bills only as web pages, without "
                      "structured author information or open data."))
    executivo = [it for it in (est.get("itens") or {}).values() if it.get("exec")]
    if not executivo:
        notas.append(("Os projetos que a prefeitura mandou à Câmara não entram: as páginas \"Projetos de Lei do Executivo\" e "
                      "\"Projetos de Lei Complementar do Executivo\" do site da Câmara estão vazias, e a lista de processos não tem "
                      "nenhum projeto do Executivo.",
                      "The bills the mayor's office sent to the City Council are not included: the \"Executive Bills\" and "
                      "\"Executive Complementary Bills\" pages on the City Council's website are empty, and its list of "
                      "proceedings has no bill from the Executive."))
    prefeito = None
    pref = B.cidade(IBGE, UF).get("prefeito") or {}
    if executivo and est["_completo"] and pref.get("id"):
        inicio = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
        lst = []
        for k, it in (est.get("itens") or {}).items():
            datas = [x[0] for x in it.get("tram") or [] if x[0]]
            data = min(datas) if datas else None
            if not it.get("exec") or not it.get("lido") or (data or "") < inicio:
                continue
            st, txt, txt_en, situ, data_st = situacao(it)
            p = regional.proposta(f"{PREFIXO}:{k}", it.get("sigla") or f"{it.get('numero')}/{it.get('ano')}", it["comum"], data,
                                  it.get("ementa"), situ, PAGINA.format(id=k, pagina=it["pag"]), "autor", status=st,
                                  data_status=data_st, status_txt=txt)
            if txt_en:
                p["statusTxt_en"] = txt_en
            lst.append(p)
        if lst:
            f_pref = fonte(CASA["casa"], "Projetos de Lei do Executivo (site oficial)", f"{SITE}/legislacao/projetos-de-lei-do-executivo", h)
            prefeito = (pref["id"], {"propostas": regional.bloco_propostas(
                lst, "Projetos que a prefeitura mandou à Câmara Municipal desde 1º/1/2025, segundo o site oficial da Câmara",
                "Bills the mayor's office sent to the City Council since January 1, 2025, according to the City Council's "
                "official website", f_pref), "fontes": [f_pref]})
    elif not est["_completo"] and pref.get("id"):  # primeira carga em andamento: fica o que foi publicado antes
        antes = C.publicados(IBGE).get(pref["id"])
        if antes:
            prefeito = (pref["id"], {"propostas": antes, "fontes": [antes["fonte"]] if antes.get("fonte") else []})
    notas += B.NOTAS_VOTOS_GASTOS.get(IBGE, [])
    cobertura = {"lista": True, "propostas": com_prop, "votacoes": False, "gastos": False}
    r = B.salvar(IBGE, UF, CASA, membros, extras, cobertura, notas, escopo if com_prop else None, prefeito=prefeito)
    r["semTse"] = len(tse.sem_ligacao)
    r["requisicoes"] = rede.n
    if not est["_completo"]:
        r["pendente"] = True
        r["etapa"] = (f"propostas ({est['_total'] - est['_faltam']} de {est['_total']} páginas lidas)" if est["_total"]
                      else "propostas (lendo as listas)")
    log(f"  CMB: {len(membros)} no cargo, {r['propostas']} propostas"
        f"{' (primeira carga em andamento)' if not est['_completo'] else ''}, {rede.n} pedidos, {time.time() - t0:.0f} s")
    return r
