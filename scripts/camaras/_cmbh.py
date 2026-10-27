"""Leitura das proposições da Câmara Municipal de Belo Horizonte (usado por c3106200.py; frente capitais-b-r6, 27/10/2026).

A pesquisa do portal (www.cmbh.mg.gov.br/atividade-legislativa/pesquisar-
proposicoes) é a única forma de ver as proposições: não há API nem arquivo de dados abertos. A página usa dois endereços do
próprio portal, que respondem ao formulário dela: pesquisar.php (a lista, 7 por página, com autoria, ementa, situação, fase
atual e a lei publicada) e proxy.php (a página de cada proposição, que o portal busca no Sistema de Informações Legislativas,
SIL: data de publicação, o endereço permanente e a tramitação, com a data de cada documento). Tipos que entram: Projeto de
Lei (inclui os de lei complementar: o portal não separa), Proposta de Emenda à Lei Orgânica, Projeto de Decreto Legislativo
e Projeto de Resolução. Autoria: "Ver.(a) A; Ver.(a) B" — o primeiro é o autor principal, os outros assinaram junto;
"Executivo: Mensagem nº ..." é a prefeitura; "Mesa - ..." (a Mesa Diretora) e comissões não entram no perfil de ninguém.

Rede: o robots.txt da Câmara pede 10 s entre pedidos (Crawl-delay). Primeira carga: ~140 páginas de lista + ~970 páginas de
proposição (~4 horas; no robô, umas 8 rodadas, sem publicar nada pela metade). Depois, por dia (~20 a 30 pedidos, 4 a 7
minutos): a 1ª página de cada tipo do ano corrente (o que é novo), um rodízio de 15 páginas da lista (cada proposição revista
em ~9 dias) e a página das proposições novas ou cuja situação mudou na lista (até 40 por dia).

Gastos: a Câmara extinguiu a verba indenizatória em 2015 (Resolução 2.076/2015; alguns itens foram indenizados até 2017, na
transição — a página "Verba Indenizatória" do portal vai até julho de 2017); o material e os serviços dos gabinetes são
contratados pela própria Câmara (pergunta frequente oficial "Na Câmara Municipal de BH existe verba indenizatória?",
conferida em 27/10/2026; nota da Câmara).
"""
from __future__ import annotations

import html
import re
import urllib.parse

from comum import log

from . import _base as B
from . import _paginas as P

IBGE, UF, SITE = "3106200", "MG", "https://www.cmbh.mg.gov.br"
CASA = {"casa": "Câmara Municipal de Belo Horizonte", "casa_en": "Belo Horizonte City Council", "sigla": "CMBH", "site": SITE,
        "sistema": "Portal oficial (HTML): lista de vereadores e pesquisa de proposições",
        # "Fale com a Câmara": o formulário oficial dos pedidos de informação (Lei de Acesso à Informação), conferido em 27/10
        "sic": f"{SITE}/participe/fale-com-a-camara"}
PESQUISA = f"{SITE}/atividade-legislativa/pesquisar-proposicoes"
LISTA_PHP = f"{SITE}/sites/all/modules/proposicoes/pesquisar.php"
DETALHE_PHP = f"{SITE}/sites/all/modules/proposicoes/proxy.php"
PAUSA = 10.0  # o robots.txt pede 10 s (Crawl-delay); a Rede usa o maior entre os dois
# tipo do portal -> (sigla oficial, tipo comum do site, trecho do endereço permanente)
TIPOS = {"2c907f7801d41f2001024943e5ec004a": ("PL", "PL", "projeto-de-lei"),
         "2c907f7801d41f2001024946b79b004f": ("PELO", "PELO", "proposta-de-emenda-a-lei-organica"),
         "2c907f78078f0f0001084488c4bf60c4": ("PDL", "PDL", "projeto-de-decreto-legislativo"),
         "2c907f7801d41f20010249450ee0004d": ("PR", "PRC", "projeto-de-resolucao")}
NOME_TIPO = {"projeto de lei": "PL", "proposta de emenda a lei organica": "PELO", "projeto de decreto legislativo": "PDL",
             "projeto de resolucao": "PR"}
CABECALHOS = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
              "Referer": PESQUISA, "Origin": SITE}
ROTACAO = 15          # páginas da lista relidas por dia (rodízio), depois da primeira carga (cada proposição em ~9 dias)
DETALHES_DIA = 40     # páginas de proposição por dia (as novas e as que mudaram), depois da primeira carga
TIPO_COMUM = {"PL": "PL", "PELO": "PELO", "PDL": "PDL", "PR": "PRC"}
_SLUG = {v[0]: v[2] for v in TIPOS.values()}
# tipo da norma no endereço do portal (/atividade-legislativa/pesquisar-legislacao/<tipo>/<número>/<ano>) -> nome
NORMAS = {"lei": "Lei", "lei-complementar": "Lei Complementar", "resolucao": "Resolução", "decreto-legislativo":
          "Decreto Legislativo", "emenda-a-lei-organica": "Emenda à Lei Orgânica", "emenda": "Emenda à Lei Orgânica"}
REDACAO_FINAL = ("Aprovada pela Câmara; falta a redação final",
                 "Approved by the City Council; the final wording is being prepared")


def sigla(x: dict) -> str:
    return f"{x['tipo']} {x['num']}/{x['ano']}"


def url_permanente(x: dict) -> str:
    return f"{PESQUISA}/{_SLUG[x['tipo']]}/{x['num']}/{x['ano']}"


def data_mensagem(autoria: str | None) -> str | None:
    """'Executivo: Mensagem nº 31, de 05/12/2025' -> '2025-12-05' (a data em que a prefeitura mandou o projeto)."""
    m = re.search(r"mensagem[^,]*,\s*de\s*(\d{2}/\d{2}/\d{4})", autoria or "", re.I)
    return P.data_br(m.group(1)) if m else None


def situacao(x: dict) -> tuple[tuple, str | None, str | None, dict | None]:
    """((status, statusTxt, statusTxt_en), situação oficial, data, lei) pela "Situação" e pela "Fase Atual" que o portal
    publica para cada proposição (regras conferidas à mão; ver as notas da frente capitais-b-r6):
    - "Lei" (ou "Resolução", "Emenda à Lei Orgânica", "Decreto Legislativo"), com a norma publicada = virou norma (o nome e
      o link vêm da "Publicação"; a data é a do Diário Oficial do Município); veto na tramitação que não foi derrubado (o
      portal escreve só "Veto do prefeito"; com a lei publicada, ele só pode ter sido parcial) = "com partes vetadas";
    - "Proposição de Lei" (a proposição enviada ao prefeito, "Aguarda Sanção/Veto") = aprovada, esperando a sanção;
    - "Em redação final" = aprovada pela Câmara (no Plenário ou, nos projetos que a comissão decide sozinha, na comissão),
      falta a redação final;
    - "... - Veto Total" = vetada por inteiro, esperando a Câmara decidir o veto; "Veto mantido"/"Vetada" = rejeitada;
      "Rejeitada" depois de "Decisão e ocorrências: veto mantido" na tramitação = o prefeito vetou e a Câmara manteve o veto;
      veto rejeitado (derrubado) na tramitação, sem a lei publicada ainda = aprovada, falta promulgar;
    - "Retirada" = retirada; "Rejeitada" = rejeitada; "Arquivada" = arquivada; "Prejudicada" = parada; "Anexada" = junta;
    - "Primeiro turno", "Segundo turno", "Turno único" (e as fases) = ainda em discussão."""
    sit, fase = x.get("situacao") or "", x.get("fase") or ""
    s, f = B.norm(sit), B.norm(fase)
    passos = (x.get("det") or {}).get("passos") or []
    ult = max((p[0] for p in passos if p[0]), default=None)
    oficial = (sit + (f" ({fase})" if fase else "")) or None
    lei = x.get("lei") or {}
    comum = TIPO_COMUM[x["tipo"]]
    hist = " | ".join(B.norm(f"{p[1]} {p[2]}") for p in passos)
    # a decisão do Plenário sobre o veto ("Decisão e ocorrências: veto mantido"; "... veto rejeitado"); o parecer da comissão
    # ("pela manutenção do veto", "pela rejeição do veto") ainda não é a decisão
    veto_mantido = bool(re.search(r"veto mantido", hist))
    veto_derrubado = bool(re.search(r"veto (rejeitado|derrubado)", hist))
    # o portal escreve só "Veto do prefeito": com a lei publicada, um veto que não foi derrubado só pode ser parcial (a lei
    # saiu com as partes que não foram vetadas)
    veto_parcial = bool(re.search(r"veto parcial|vetad[oa] parcialmente", hist)) or (
        bool(lei.get("numero")) and "cadastro de veto" in hist and not veto_derrubado)
    if lei.get("numero") and lei.get("ano"):
        nome = B.nome_norma(NORMAS.get(lei.get("tipo") or "", "Lei"), lei["numero"], lei["ano"])
        st = ("lei", B.virou(nome, veto_parcial), None)
        if "emenda" in (lei.get("tipo") or ""):
            st = ("lei", st[1], "Became an amendment to the city's Organic Law" + (" (with some parts vetoed)" if veto_parcial else ""))
        return st, oficial, lei.get("dom") or ult, {"nome": nome, "url": lei.get("url")}
    if re.match(r"(lei|resolucao|decreto legislativo|emenda a lei organica)$", s):
        return ("lei", None, None), oficial, ult, None
    if "veto total" in s or "veto total" in f:
        if re.search(r"mantid", s) or veto_mantido:
            return ("rejeitada", *B.TXT["veto_mantido"]), oficial, ult, None
        if re.search(r"rejeitad|derrubad", s) or veto_derrubado:
            return ("aprovada", *B.TXT["veto_derrubado"]), oficial, ult, None
        return ("rejeitada", *B.TXT["veto_total_pendente"]), oficial, ult, None
    if re.search(r"vetad|veto mantido", s):
        return ("rejeitada", *B.TXT["veto_mantido"]), oficial, ult, None
    if s.startswith("proposicao de lei") or "sancao" in f:
        ch = "promulgar" if comum in ("PDL", "PRC", "PELO") else "sancao"
        return ("aprovada", *B.TXT[ch]), oficial, ult, None
    if s.startswith("em redacao final"):
        return ("aprovada", *REDACAO_FINAL), oficial, ult, None
    if "promulga" in s or "promulga" in f:
        return ("aprovada", *B.TXT["promulgar"]), oficial, ult, None
    if s.startswith("retirad"):
        return ("retirada", None, None), oficial, ult, None
    if s.startswith("rejeitad"):
        if veto_mantido:
            return ("rejeitada", *B.TXT["veto_mantido"]), oficial, ult, None
        return ("rejeitada", None, None), oficial, ult, None
    if s.startswith("arquivad"):
        return ("arquivada", None, None), oficial, ult, None
    if s.startswith("prejudicad"):
        return ("parada", None, None), oficial, ult, None
    if "anexad" in s or "apensad" in s:
        return ("junta", None, None), oficial, ult, None
    if veto_derrubado:
        return ("aprovada", *B.TXT["veto_derrubado"]), oficial, ult, None
    return ("andando", None, None), oficial, ult, None


# ---------------------------------------------------------------- lista oficial de vereadores
def vereadores() -> list[dict]:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    pessoas = []
    for bloco in t.split('<div class="vereador">')[1:]:
        foto = re.search(r'<img[^>]+src="([^"]+)"', bloco)
        sigla = re.search(r'views-field-field-sigla">\s*<div class="field-content">(.*?)</div>', bloco, re.S)
        nome = re.search(r'views-field-title">\s*<span class="field-content"><a href="([^"]+)">(.*?)</a>', bloco, re.S)
        if not nome:
            continue
        pessoas.append({"chave": nome.group(1).rsplit("/", 1)[-1], "nome": html.unescape(nome.group(2)).strip(),
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                        "foto": html.unescape(foto.group(1)) if foto else None, "url": SITE + nome.group(1)})
    return pessoas


# ---------------------------------------------------------------- pesquisa de proposições
def _campos(**kw) -> bytes:
    """O formulário da página de pesquisa, como o navegador manda (os campos vazios vão com o texto de exemplo)."""
    c = {"metodo": "", "nomeProposicao": "", "paginaRequerida": "1", "urlProposicao": "", "idProposicao": "",
         "buscarEmendas_proposicoes": "", "idTipoEmenda": "", "idTipoSubemenda": "", "idTipoEmendaDeRedacao": "",
         "drupalUsername": "deslogado-anonimo", "drupalEmail": "", "buscaViaUrl": "", "stormCodex": _token(),
         "mobile": "0", "tipo": "", "numero": "[número]", "ano": "[ano]", "buscarPorProtocolo": "false",
         "autor": "[autor]", "assunto": "[assunto]", "assunto2": "[assunto2]", "fase": "[Selecione]", "tramitando": "Tanto faz",
         "buscarProposicoesOpinar": "false"}
    c.update({k: str(v) for k, v in kw.items()})
    return urllib.parse.urlencode(c).encode()


_TOKEN: dict = {}
_REDE: dict = {}


def _token() -> str:
    """O código que a página de pesquisa põe no formulário (lido uma vez por rodada; guardado 20 h)."""
    if "v" not in _TOKEN:
        t = _REDE["r"].guardado(PESQUISA, "pesquisar.html", 20).decode("utf-8", "replace")
        m = re.search(r'name="stormCodex"[^>]*value="([^"]+)"', t)
        if not m:
            raise RuntimeError("a página de pesquisa de proposições mudou (sem o código do formulário)")
        _TOKEN["v"] = m.group(1)
    return _TOKEN["v"]


def _txt(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _decodifica(b: bytes) -> str:
    # as páginas misturam texto em UTF-8 (os dados do SIL) com rótulos em Latin-1 (o próprio portal)
    return b.decode("utf-8", "replace")


def ler_pagina_lista(rede: P.Rede, tipo_id: str, ano: int, pagina: int) -> tuple[int, list[dict]]:
    """(total da busca, itens da página)."""
    b = rede.pedir(LISTA_PHP, dados=_campos(tipo=tipo_id, ano=ano, paginaRequerida=pagina), cabecalhos=CABECALHOS)
    t = _decodifica(b)
    if "fonte n" in t and "autorizada" in t:
        raise RuntimeError("a pesquisa de proposições recusou o pedido (\"fonte não autorizada\")")
    m = re.search(r"de um total de (\d+) itens", t)
    total = int(m.group(1)) if m else 0
    if not m and "Nenhum resultado" not in t:
        raise RuntimeError("a lista de proposições mudou de formato")
    itens = []
    for li in re.findall(r"(?s)<li><h3>(.*?)</li>(?=<li><h3>|</ul>)", t):
        cam = re.search(r"data-caminho='([^']+)'", li)
        tit = re.search(r"class='left detalhar[^>]*>([^<]+)</span>", li)
        if not (cam and tit):
            continue
        sil = re.search(r"[?&]id=([0-9a-f]{32})", cam.group(1))
        mt = re.match(r"\s*(.+?)\s*-\s*(\d+)\s*/\s*(\d{4})\s*$", html.unescape(tit.group(1)))
        if not (sil and mt):
            continue
        campos = {}
        for rot, val in re.findall(r"(?s)<p><strong>([^<]*?):\s*</strong>(.*?)</p>", li):
            campos[B.norm(rot).replace("\ufffd", "")] = val
        sit = next((_txt(v) for k, v in campos.items() if k.startswith("situa")), None)
        fase = next((_txt(v) for k, v in campos.items() if k.startswith("fase")), None)
        pub = next((v for k, v in campos.items() if k.startswith("publica")), None)
        lei = None
        if pub:
            ml = re.search(r"href='([^']+)'>(.*?)</a>", pub)
            md = re.search(r"DOM:\s*(\d{2}/\d{2}/\d{4})", pub)
            # o tipo e o número vêm do endereço da norma (/atividade-legislativa/pesquisar-legislacao/lei/12033/2026)
            mu = re.search(r"pesquisar-legislacao/([^/]+)/(\d+)/(\d{4})", ml.group(1)) if ml else None
            lei = {"texto": _txt(ml.group(2)) if ml else _txt(pub), "url": (SITE + ml.group(1)) if ml else None,
                   "tipo": mu.group(1) if mu else None, "numero": int(mu.group(2)) if mu else None,
                   "ano": int(mu.group(3)) if mu else None, "dom": P.data_br(md.group(1)) if md else None}
        itens.append({"id": sil.group(1), "tipo": TIPOS[tipo_id][0], "num": int(mt.group(2)), "ano": int(mt.group(3)),
                      "autoria": _txt(campos.get("autoria")), "ementa": _txt(campos.get("ementa")),
                      "situacao": sit, "fase": fase, "lei": lei, "caminho": cam.group(1)})
    return total, itens


def ler_detalhe(rede: P.Rede, caminho: str) -> dict:
    """A página da proposição (data de publicação, endereço permanente e a tramitação, documento por documento)."""
    t = _decodifica(rede.pedir(DETALHE_PHP, dados=_campos(urlProposicao=caminho), cabecalhos=CABECALHOS))
    if "proposicoes-interna" not in t:
        raise RuntimeError("a página da proposição mudou de formato")
    pub = re.search(r"publicado em (\d{2}/\d{2}/\d{4})", t)
    url = re.search(r"id='novaUrl'[^>]*>([^<]+)<", t)
    passos, fase = [], None
    tram = t.split("id='tramitacao'", 1)[1] if "id='tramitacao'" in t else ""
    for m in re.finditer(r"(?s)<h4>(.*?)</h4>|<div class='doc-item[^']*'>(.*?)<span class='publicado'>[^<]*?(\d{2}/\d{2}/\d{4})", tram):
        if m.group(1) is not None:
            fase = _txt(m.group(1))
        else:
            passos.append([P.data_br(m.group(3)), fase, _txt(m.group(2))])
    return {"data": P.data_br(pub.group(1)) if pub else None, "url": url.group(1).strip() if url else None, "passos": passos}


def _mudou(velho: dict | None, novo: dict) -> bool:
    if not velho:
        return True
    return any(velho.get(k) != novo.get(k) for k in ("situacao", "fase", "lei", "autoria", "ementa"))


def ler_propostas(rede: P.Rede, e: dict, h: str) -> bool:
    """Lê o que falta e guarda no estado (e). Devolve True quando tudo está lido (primeira carga completa)."""
    _REDE["r"] = rede
    itens = e.setdefault("itens", {})
    pags = e.setdefault("paginas", {})
    anos = list(range(int(B.INICIO[:4]), int(h[:4]) + 1))
    combos = [(tid, ano) for tid in TIPOS for ano in anos]

    def guardar_itens(lst):
        for x in lst:
            antes = itens.get(x["id"])
            if _mudou(antes, x):
                x["det_pendente"] = True
            else:
                x["det_pendente"] = bool((antes or {}).get("det_pendente"))
            x["det"] = (antes or {}).get("det")
            x["visto"] = h
            itens[x["id"]] = x

    if not e.get("completo"):
        # primeira carga: todas as páginas de cada tipo e ano (guardando a cada página)
        for tid, ano in combos:
            k = f"{TIPOS[tid][0]}-{ano}"
            st = pags.setdefault(k, {"lidas": []})
            total = st.get("total")
            p = 1
            while total is None or p <= max(1, -(-total // 7)):
                if p not in st["lidas"]:
                    total, lst = ler_pagina_lista(rede, tid, ano, p)
                    st["total"] = total
                    guardar_itens(lst)
                    st["lidas"].append(p)
                    P.guardar_estado(IBGE, e)
                p += 1
                if total == 0:
                    break
        for k in list(itens):
            x = itens[k]
            if x.get("det") is None or x.get("det_pendente"):
                x["det"] = ler_detalhe(rede, x["caminho"])
                x["det"]["lido"] = h
                x["det_pendente"] = False
                if rede.n % 10 == 0:
                    P.guardar_estado(IBGE, e)
        e["completo"] = True
        e["carga_completa"] = h
        P.guardar_estado(IBGE, e)
        return True

    # rodada diária (depois da primeira carga): se o tempo da rodada acabar no meio, publica o que já foi lido (cada
    # proposição com a sua última leitura completa) e o resto fica para a próxima
    try:
        _rodada_diaria(rede, e, h, combos, itens, pags, guardar_itens)
    except P.SemTempo as motivo:
        log(f"  CMBH: {motivo} no meio da rodada diária ({rede.n} pedidos): o resto fica para a próxima; publica o que já foi lido")
    P.guardar_estado(IBGE, e)
    return True


def _rodada_diaria(rede, e, h, combos, itens, pags, guardar_itens) -> None:
    # o que é novo (1ª página de cada tipo do ano corrente — e do ano anterior até março —, e as seguintes enquanto houver
    # novidade)
    if e.get("dia") != h:
        e["dia"], e["dia_feito"] = h, []
    feitos = set(e.get("dia_feito") or [])
    for tid, ano in combos:
        if ano < int(h[:4]) - 1 or (ano < int(h[:4]) and int(h[5:7]) > 3):
            continue
        k = f"novos-{TIPOS[tid][0]}-{ano}"
        if k in feitos:
            continue
        p = 1
        while True:
            total, lst = ler_pagina_lista(rede, tid, ano, p)
            pags.setdefault(f"{TIPOS[tid][0]}-{ano}", {})["total"] = total
            novos = [x for x in lst if x["id"] not in itens]
            guardar_itens(lst)
            if not novos or p * 7 >= total:
                break
            p += 1
        feitos.add(k)
        e["dia_feito"] = sorted(feitos)
        P.guardar_estado(IBGE, e)
    # rodízio: ROTACAO páginas por dia, de todas as listas (cada proposição é revista em uns 9 dias)
    if "rodizio" not in feitos:
        ordem = [(tid, ano, p) for tid, ano in combos
                 for p in range(1, max(1, -(-(pags.get(f"{TIPOS[tid][0]}-{ano}", {}).get("total") or 0) // 7)) + 1)]
        cur = int(e.get("cursor") or 0)
        for i in range(min(ROTACAO, len(ordem))):
            tid, ano, p = ordem[(cur + i) % len(ordem)]
            total, lst = ler_pagina_lista(rede, tid, ano, p)
            guardar_itens(lst)
            e["cursor"] = (cur + i + 1) % len(ordem)
            P.guardar_estado(IBGE, e)
        feitos.add("rodizio")
        e["dia_feito"] = sorted(feitos)
    # a página das proposições novas ou que mudaram na lista (até DETALHES_DIA por dia; o resto fica para amanhã)
    feitos_det = 0
    for k, x in sorted(itens.items(), key=lambda kv: (kv[1].get("det") is not None, kv[1]["ano"], kv[1]["num"])):
        if x.get("det") is not None and not x.get("det_pendente"):
            continue
        if feitos_det >= DETALHES_DIA:
            break
        x["det"] = ler_detalhe(rede, x["caminho"])
        x["det"]["lido"] = h
        x["det_pendente"] = False
        feitos_det += 1
        if feitos_det % 10 == 0:
            P.guardar_estado(IBGE, e)
