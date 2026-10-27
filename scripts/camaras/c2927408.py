"""Câmara Municipal de Salvador (BA): a lista oficial de vereadores da legislatura atual (www.cms.ba.gov.br/vereadores,
aba "Vereadores - 20ª Legislatura"; quem saiu ou está de licença fica em outra aba, que não entra) e as propostas dos
vereadores desde 1º/1/2025, lidas do sistema legislativo da Câmara ("Acompanhamento de proposição",
https://cmsalvador.sys.inf.br/cl/prop_interna/, um sistema ScriptCase com páginas HTML).

Propostas (propostas()): a grade oficial de proposições, filtrada por ano e por modalidade (Projeto de Lei, de Lei
Complementar, de Decreto Legislativo, de Emenda à Lei Orgânica e de Resolução; e os Vetos, só para saber que projeto foi
vetado), 50 linhas por página: sigla (PLE-574/2025), autor, ementa, data da última movimentação, localização e situação. A
janela de tramitação de cada proposição (as movimentações, da mais nova para a mais antiga) dá a situação (regras próprias da
Câmara: situacao_ssa), a data em que foi protocolada e o texto da proposição (o PDF anexado como "Íntegra"). O sistema não
tem um endereço fixo para a página de cada proposição (a janela de tramitação abre pela sessão de quem consulta): o link de
cada proposta leva a esse PDF, no servidor de documentos da Câmara, ou, sem ele, à consulta oficial, onde se busca pela sigla.
Educado: uma sessão como a de um navegador, um pedido por vez, 2 s entre pedidos (o robots.txt não pede intervalo), cache do
que já foi lido em .cache/camaras/2927408/propostas.json. A primeira carga (umas 1.300 janelas de tramitação) pode levar mais
de uma rodada; até terminar, ficam publicadas as propostas de antes (nada pela metade). Depois, cada rodada lê as listas (as
do ano todo dia; as do ano anterior uma vez por semana) e só a tramitação do que mudou desde a última leitura (no máximo 250
por rodada), mais um rodízio das que estão em tramitação (cada uma a cada 60 dias, no máximo 40 por rodada).

Gastos: a Verba Compensatória de Atividade Parlamentar aparece só como empenhos e pagamentos no "Registro de Despesa" do
portal da transparência, sem ligação segura com cada vereador e cada mês (nota da Câmara, com os números conferidos).
"""
import html
import re
import time

import regional
from comum import fonte, hoje, ler_json, log, salvar_json

from . import _base as B
from . import _capitais_c as C
from . import _scriptcase as S

IBGE, UF, SITE = "2927408", "BA", "https://www.cms.ba.gov.br"
CASA = {"casa": "Câmara Municipal de Salvador", "casa_en": "Salvador City Council", "sigla": "CMS", "site": SITE,
        "sistema": "Portal oficial (HTML) e sistema legislativo (ScriptCase)", "api": None}
SISTEMA = "https://cmsalvador.sys.inf.br/cl/prop_interna/"
TRAM = "https://cmsalvador.sys.inf.br/cl/prop_interna_tram/"
PREFIXO = f"cm{IBGE}"
ESTADO = B.PASTA_CACHE / IBGE / "propostas.json"
PAUSA = 2.0
# modalidade no sistema da Câmara -> tipo comum do site (None: lida só para saber dos vetos)
MODALIDADES = {"Projeto de Lei": "PL", "Projeto de Lei Complementar": "PLP", "Projeto de Decreto Legislativo": "PDL",
               "Projeto de Emenda a LOM": "PELO", "Projeto de Resolucao": "PRC", "Veto": None}
# a sigla de cada modalidade no sistema (PLE-574/2025): confere que a pesquisa filtrou mesmo a modalidade pedida
PREFIXO_MOD = {"Projeto de Lei": "PLE", "Projeto de Lei Complementar": "PLC", "Projeto de Decreto Legislativo": "PDL",
               "Projeto de Emenda a LOM": "PEL", "Projeto de Resolucao": "PRE", "Veto": "VTO"}
FALHAS_SEGUIDAS = 5  # janelas seguidas com erro = o sistema está fora do ar: a rodada para (senão, pula só a proposição)
LIMITE_DIA = 250   # janelas de tramitação por rodada depois da primeira carga (as novas e as que mudaram)
RELER_DIAS = 60    # cada proposição em tramitação tem a janela lida de novo a cada 60 dias (o rodízio)...
RODIZIO_DIA = 40   # ...no máximo 40 por rodada
# autores conferidos à mão (nome como o sistema escreve -> chave do vereador na página oficial)
AUTOR_MANUAL: dict[str, str] = {}
GASTOS_NOTA = ("Os gastos do mandato não entram neste site: a Câmara publica a Verba Compensatória de Atividade Parlamentar só "
               "como empenhos e pagamentos no \"Registro de Despesa\" do portal da transparência, e essa tabela não permite "
               "ligar com segurança cada gasto a cada vereador e a cada mês. Em 2025 e 2026 (conferido em 27/10/2026), dos 848 "
               "empenhos da verba, 106 não têm pagamento ligado, 18 têm pagamentos de valor diferente do empenho (em alguns, "
               "igual ao empenho de outro vereador), 129 não dizem o mês ou o ano a que se referem, e há empenhos repetidos para "
               "o mesmo vereador e o mesmo mês.",
               "Office spending is not included on this site: the City Council publishes its Parliamentary Activity "
               "Compensation Allowance only as commitments and payments in the \"Expense Register\" of its transparency portal, "
               "and that table does not allow each expense to be safely matched to each councilor and each month. In 2025 and "
               "2026 (checked on October 27, 2026), of the 848 commitments of the allowance, 106 have no linked payment, 18 "
               "have payments with an amount different from the commitment (in some, equal to another councilor's "
               "commitment), 129 do not say which month or year they refer to, and there are repeated commitments for the same "
               "councilor and month.")


# ---------------------------------------------------------------- lista oficial
def pessoas_oficiais() -> list[dict]:
    t = B.baixar_pagina(f"{SITE}/vereadores", IBGE, "vereadores")
    i, j = t.find('id="vereadores"'), t.find('id="exvereadores_licenciados"')
    if i < 0 or j < i:
        raise RuntimeError("a página de vereadores mudou")
    secao = t[i:j]
    emails = {}
    for nome, email in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", secao, re.S):
        emails[re.sub(r"\W", "", html.unescape(nome).lower())] = html.unescape(email).strip() or None
    pessoas = []
    for href, foto, nome, sigla in re.findall(r"getUrl\('([^']+)'.*?background-image: url\('([^']+)'\).*?"
                                              r'<div class="name">\s*<p>(.*?)</p>.*?<div class="partido">\s*<p>(.*?)</p>', secao, re.S):
        nome = html.unescape(nome).strip()
        pessoas.append({"chave": href.rsplit("/", 1)[-1], "nome": nome, "partido": html.unescape(sigla).strip() or None,
                        "foto": SITE + foto if foto.startswith("/") else foto, "url": SITE + href,
                        "email": emails.get(re.sub(r"\W", "", nome.lower()))})
    return pessoas


# ---------------------------------------------------------------- propostas
def _linha_grade(r: str) -> dict:
    link = re.search(r"nm_gp_submit5\('/cl/prop_interna_tram/',\s*'[^']*',\s*'([^']+)'", r)
    return {"sigla": S.valor(r, "proposicao"), "autor": S.valor(r, "autorproposicao"), "ementa": S.valor(r, "pro_ementa"),
            "mov": C.data_iso(S.valor(r, "tra_dt_movimentacao")), "dest": S.valor(r, "destino"),
            "sit": S.valor(r, "sit_nome_futuro"), "parms": link.group(1) if link else None}


def _tramitacao(h: str) -> list[list]:
    """[[data, situação, observação, link do documento], ...] da janela de tramitação, na ordem da página (da mais nova para
    a mais antiga). O link é o do documento anexado ao passo (PDF no servidor de documentos da Câmara), quando há."""
    out = []
    for r in S.linhas(h):
        sit = re.search(r'css_situacao_grid_line[^>]*>(.*?)</TD>', r, re.S)
        doc = re.search(r"(https?://[^'\" ]+?\.pdf)", r, re.I)
        out.append([C.data_iso(S.valor(r, "tra_dt_movimentacao")), C.texto(sit.group(1)) if sit else "",
                    S.valor(r, "tra_observacao")[:300], doc.group(1) if doc else None])
    return out


def _ler_tram(s: "S.Sessao", parms: str) -> tuple[list, int]:
    t = s.pedir(TRAM + "?&nmgp_outra_jan=true&nmgp_url_saida=modal&SC_lig_apl_orig=prop_interna&nmgp_opcao=grid&nmgp_parms="
                + parms)
    tot = S.total(t)
    trams = _tramitacao(t)
    if tot and tot[2] > len(trams):  # mais de 20 movimentações: a mesma janela com 50 por página
        m = re.search(r'name="script_case_init" value="(\d+)"', t)
        if m:
            import json
            d = json.loads(s.pedir(TRAM + "index.php", "nmgp_opcao=ajax_navigate&script_case_init=" + m.group(1)
                                   + "&opc=muda_qt_linhas&parm=50").strip())
            trams = _tramitacao(S.campo_html(d, "sc_grid_body"))
    return trams, (tot[2] if tot else len(trams))


def _precisa(it: dict, h: str) -> str | None:
    """Por que ler a tramitação de novo: "nova" (nunca lida, ou lida no formato antigo, sem o link do documento), "mudou"
    (a grade mostra outra data ou situação desde a última leitura), "velha" (em tramitação e lida há mais de RELER_DIAS
    dias: o rodízio) ou None."""
    if not it.get("lido") or (it.get("tram") and len(it["tram"][0]) < 4):
        return "nova"
    if (it.get("mov_lido"), it.get("sit_lido")) != (it.get("mov"), it.get("sit")):
        return "mudou"
    if it["lido"] < C.menos(h, RELER_DIAS) and it.get("st") not in ("lei", "arquivada", "retirada", "rejeitada"):
        return "velha"
    return None


def propostas(s: "S.Sessao", h: str) -> dict:
    """Lê (ou continua lendo) as listas e a tramitação das proposições desde 2025. Devolve o estado, com "_completo"."""
    est = ler_json(ESTADO, {}) or {}
    listas, itens = est.setdefault("listas", {}), est.setdefault("itens", {})
    primeira = not est.get("completo_em")
    ano_h = int(h[:4])
    n0, lidas, rodizio, falhas = s.n, 0, 0, 0
    for it in itens.values():  # a situação de cada uma (para o rodízio não reler as que já terminaram)
        if it.get("lido") and "st" not in it and MODALIDADES.get(it.get("mod")):
            it["st"] = situacao_ssa(it, {})[0]
    try:
        s.abrir()
        qt = False
        for ano in range(int(B.INICIO[:4]), ano_h + 1):
            pendentes = [m for m in MODALIDADES if not (listas.get(f"{ano}-{m}") == h or
                                                         (ano < ano_h and (listas.get(f"{ano}-{m}") or "") >= C.menos(h, 7)))]
            if not pendentes:
                continue
            d = s.nav("interativ_search", f"pro_ano__DL__Ano__DL__tx__DL__{ano}##@@{ano}__DL__S__DL__N")
            for mod in pendentes:
                if C.sem_tempo():
                    raise TimeoutError("fim do tempo da rodada")
                d = s.nav("interativ_search", f"mod_nome__DL__Modalidade__DL__tx__DL__{mod}##@@{mod}__DL__S__DL__N")
                if not qt:
                    d = s.nav("muda_qt_linhas", "50")
                    qt = True
                tot = S.total(d)
                vistos, ini = set(), 1
                while True:
                    linhas = S.linhas(S.campo_html(d, "sc_grid_body"))
                    if not tot and len(linhas) >= 50:  # página cheia sem o total no rodapé: não dá para saber se leu tudo
                        raise RuntimeError(f"{ano} {mod}: a grade não mostrou o total de linhas")
                    for r in linhas:
                        x = _linha_grade(r)
                        if not x["sigla"] or not re.search(rf"/{ano}$", x["sigla"]) \
                                or not x["sigla"].startswith(PREFIXO_MOD[mod] + "-"):
                            continue  # outro ano ou outra modalidade (a pesquisa não filtrou: a conta abaixo para a rodada)
                        it = itens.setdefault(x["sigla"], {})
                        it.update({k: x[k] for k in ("autor", "ementa", "mov", "dest", "sit")}, mod=mod, ano=ano)
                        vistos.add(x["sigla"])
                        por_que = _precisa(it, h) if MODALIDADES[mod] and x["parms"] else None
                        if not por_que or not (primeira or (lidas < LIMITE_DIA and
                                                            (por_que != "velha" or rodizio < RODIZIO_DIA))):
                            continue
                        if C.sem_tempo():  # a lista não fica marcada como lida: a próxima rodada continua daqui
                            raise TimeoutError("fim do tempo da rodada")
                        try:
                            it["tram"], it["n_tram"] = _ler_tram(s, x["parms"])
                        except (RuntimeError, ValueError, OSError) as erro:
                            it["erro"] = h
                            falhas += 1
                            log(f"  CMS: tramitação de {x['sigla']}: {type(erro).__name__}: {str(erro)[:120]} "
                                "(tenta de novo na próxima rodada)")
                            if falhas >= FALHAS_SEGUIDAS:
                                raise
                            continue
                        falhas = 0
                        it.pop("erro", None)
                        it.update(lido=h, mov_lido=it["mov"], sit_lido=it["sit"])
                        it["st"] = situacao_ssa(it, {})[0]
                        lidas += 1
                        rodizio += por_que == "velha"
                        if lidas % 25 == 0:
                            salvar_json(ESTADO, est)
                    if not tot or tot[1] >= tot[2]:
                        break
                    ini = tot[1] + 1
                    if C.sem_tempo():
                        raise TimeoutError("fim do tempo da rodada")
                    d = s.nav("rec", str(ini))
                    tot = S.total(d)
                if tot and len(vistos) < tot[2] - 2:  # a lista não veio inteira (o sistema mudou?): não esquece ninguém
                    raise RuntimeError(f"{ano} {mod}: {len(vistos)} de {tot[2]} linhas lidas")
                guardados = sum(1 for it in itens.values() if it.get("ano") == ano and it.get("mod") == mod)
                if guardados >= 10 and len(vistos) < guardados / 2:  # resposta de erro ou sistema fora do ar: não apaga
                    raise RuntimeError(f"{ano} {mod}: a lista veio com {len(vistos)} linhas (antes: {guardados})")
                for k in [k for k, it in itens.items() if it.get("ano") == ano and it.get("mod") == mod and k not in vistos]:
                    itens.pop(k)  # saiu da lista oficial
                listas[f"{ano}-{mod}"] = h
                salvar_json(ESTADO, est)
    except (TimeoutError, RuntimeError, OSError, ValueError) as erro:
        log(f"  CMS: propostas: {type(erro).__name__}: {str(erro)[:150]} ({s.n - n0} pedidos); continua na próxima rodada")
    # uma janela que dá erro não segura a primeira carga (a proposição fica fora do perfil até ser lida)
    sem = sum(1 for it in itens.values() if MODALIDADES.get(it.get("mod")) and not it.get("erro")
              and (not it.get("lido") or (it.get("tram") and len(it["tram"][0]) < 4)))
    completo = all(listas.get(f"{a}-{m}") for a in range(int(B.INICIO[:4]), ano_h + 1) for m in MODALIDADES) and not sem
    if completo and primeira:
        est["completo_em"] = h
    salvar_json(ESTADO, est)
    est["_completo"] = completo or not primeira
    est["_faltam"] = sem
    est["_total"] = sum(1 for it in itens.values() if MODALIDADES.get(it.get("mod")))
    est["_pedidos"] = s.n - n0
    return est


# situação de um passo da tramitação (texto oficial, sem acento e em minúsculas) -> status; "neutro" = não diz nada
_REGRAS_SSA = [
    (r"^(armazenad|encaminhad|anexad|expedid|publicad|redistribuid|recebid|aguardando assinatura|aguardando publicacao|\.$)", "neutro"),
    (r"^(sancionad|promulgad)", "lei"),
    (r"retirad[oa] pel[oa] autor", "retirada"),
    (r"rejeitad", "rejeitada"),
    (r"^arquivad", "arquivada"),
    (r"^aguardando sancao|^aguardando redacao final|^aprovad", "aprovada"),
]


def _classe(sit: str) -> str:
    t = B.norm(sit)
    for exp, st in _REGRAS_SSA:
        if re.search(exp, t):
            return st
    return "andando"


# o sistema diz "Sancionado"/"Promulgado", sem o número da norma: o texto diz que tipo de norma a proposta virou
VIROU = {"PLP": ("Virou lei complementar", "Became a complementary law"),
         "PDL": ("Virou decreto legislativo", "Became a legislative decree"),
         "PRC": ("Virou resolução", "Became a resolution"),
         "PELO": ("Virou emenda à Lei Orgânica", "Became an amendment to the Organic Law")}


def situacao_ssa(it: dict, vetos: dict) -> tuple:
    """(status, statusTxt, statusTxt_en, situação oficial, dataStatus). Regras próprias da Câmara de Salvador (conferidas à
    mão), lendo a tramitação da mais nova para a mais antiga e pulando os passos que só mudam a proposição de lugar ou anexam
    documentos ("Armazenado", "Encaminhado...", "Anexado...", "Expedido", "Publicado"):
    - "Sancionado"/"Promulgado" = virou norma (o sistema não diz o número da lei; com veto parcial, "com partes vetadas");
    - veto total do prefeito (uma proposição "Veto" que cita o projeto) sem sanção = rejeitada ("O prefeito vetou a proposta
      inteira");
    - "Aprovado", "Aguardando Redação Final", "Aguardando Sanção/Promulgação" = aprovada, esperando a sanção (ou a
      promulgação, nos decretos legislativos, resoluções e emendas à Lei Orgânica);
    - "Arquivado" (por exemplo, pelo art. 191 do Regimento, depois do parecer contrário da CCJ) = arquivada, a não ser que
      logo antes a proposição tenha sido retirada pelo autor ou rejeitada; "Retirado pelo Autor" = retirada;
      "Desarquivado" volta para em discussão;
    - o resto (protocolado, relator designado, parecer, pauta, Ordem do Dia, diligência, adiado) = ainda em discussão."""
    trams = [t for t in it.get("tram") or [] if t[1]]
    oficial = it.get("sit") or (trams[0][1] if trams else None)
    comum = MODALIDADES.get(it.get("mod"))
    veto = vetos.get(it.get("chave_veto"))
    passos = [(t[0], t[1], _classe(t[1])) for t in trams]

    def sit(p):  # a "Situação" da grade, ou, se ela só diz onde a proposição está ("Armazenado"), o passo que decidiu
        return p[1] if p and (not oficial or _classe(oficial) == "neutro") else oficial

    lei = next((p for p in passos if p[2] == "lei"), None)
    if lei:
        if veto == "parcial":
            return "lei", *B.TXT["veto_parcial"], sit(lei), lei[0]
        return "lei", *VIROU.get(comum, (None, None)), sit(lei), lei[0]
    decisivos = [p for p in passos if p[2] != "neutro"]
    if veto == "total":
        return "rejeitada", *B.TXT["veto_total"], sit(decisivos[0] if decisivos else None), None
    escolhido = decisivos[0] if decisivos else None
    if escolhido and escolhido[2] == "arquivada":
        # arquivada depois de retirada pelo autor ou de rejeitada: vale o que aconteceu antes do arquivamento
        antes = next((p for p in decisivos[1:] if p[2] != "arquivada"), None)
        if antes and antes[2] in ("retirada", "rejeitada"):
            escolhido = antes
    if escolhido is None:
        if not trams:
            return "andando", *B.TXT["sem_tramitacao"], oficial, None
        return "andando", None, None, oficial, trams[0][0]
    st = escolhido[2]
    if st == "aprovada":
        chave = "sancao" if comum in ("PL", "PLP") else "promulgar"
        return "aprovada", *B.TXT[chave], sit(escolhido), escolhido[0]
    return st, None, None, sit(escolhido), escolhido[0]


def url_de(it: dict) -> str:
    """O texto da proposição (o PDF anexado como "Íntegra" na tramitação, no servidor de documentos da Câmara) ou, sem ele,
    a consulta oficial (o sistema não tem um endereço fixo para a página de cada proposição). Com mais de uma "Íntegra", vale
    a mais nova anexada pelo próprio autor (um texto "em substituição" ao anterior), sem os anexos; senão, a mais antiga
    (substitutivos e requerimentos de urgência também aparecem como "Íntegra", anexados por outros setores)."""
    ints = [t for t in it.get("tram") or [] if len(t) > 3 and t[3] and B.norm(t[1]).startswith("anexado integra")]
    if not ints:
        return SISTEMA
    autor = B.norm(it.get("autor"))
    sem_anexo = [t for t in ints if not B.norm(t[2]).startswith("anexo")]
    proprios = [t for t in sem_anexo if autor and B.norm(t[1]).endswith(autor)]
    return proprios[0][3] if proprios else (sem_anexo or ints)[-1][3]


def _chave_projeto(sigla: str | None) -> str | None:
    """'PLE-574/2025' -> 'ple 574 2025' (para casar com o projeto citado na ementa de um veto)."""
    m = re.match(r"\s*([A-Za-z]+)\s*-?\s*(\d+)\s*/\s*(\d{4})", sigla or "")
    return f"{m.group(1).lower()} {int(m.group(2))} {m.group(3)}" if m else None


def vetos_por_projeto(itens: dict) -> dict:
    """{chave do projeto: "total"|"parcial"}, pelas proposições "Veto" (a ementa cita o projeto vetado: "Veto Total ao Projeto
    de Lei nº 123/2025")."""
    out = {}
    for sigla, it in itens.items():
        if it.get("mod") != "Veto":
            continue
        e = B.norm(it.get("ementa"))
        m = re.search(r"projeto de (lei complementar|lei|resolucao|decreto legislativo)\D{0,20}?(\d+)\s*/\s*(\d{4})", e)
        if not m:
            continue
        sig = {"lei": "ple", "lei complementar": "plc", "resolucao": "pre", "decreto legislativo": "pdl"}[m.group(1)]
        tipo = "parcial" if "parcial" in e else "total" if "total" in e else None
        if tipo:
            out[f"{sig} {int(m.group(2))} {m.group(3)}"] = tipo
    return out


def coletar() -> dict:
    t0 = time.time()
    h = hoje()
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores - 20ª Legislatura (portal oficial)", f"{SITE}/vereadores", h)
    # conferidos à mão (mesmo partido; nome de urna no TSE): "Omarzinho Gordilho" = OMARZINHO (Omar Antonio Gordilho de Britto,
    # PDT); "Téo Senna" = THEO SENNA (Theofilo Virgilio de Senna, PSDB), eleitos em 2024
    membros, extras, tse = C.lista_oficial(IBGE, UF, CASA, pessoas_oficiais(), 43,
                                           tse_manual={"omarzinho-gordilho": "50001921919", "teo-senna": "50001884200"})
    por_chave = {m["_chave"]: m["id"] for m in membros}
    for m in membros:
        m.pop("_chave", None)
        m.pop("_cand", None)
    s = S.Sessao(SISTEMA, PAUSA)
    est = propostas(s, h)
    escopo = (B.ESCOPO + ", segundo o sistema legislativo da Câmara (Acompanhamento de proposição).",
              B.ESCOPO_EN + ", according to the City Council's legislative system (bill tracking).")
    notas = []
    com_prop = False
    manual = {k: por_chave[v] for k, v in AUTOR_MANUAL.items() if v in por_chave}
    if est["_completo"]:
        itens = est.get("itens") or {}
        vetos = vetos_por_projeto(itens)
        por: dict[str, list] = {m["id"]: [] for m in membros}
        sem_ligacao: dict[str, int] = {}
        for sigla, it in itens.items():
            comum = MODALIDADES.get(it.get("mod"))
            if not comum or not it.get("lido") or re.match(r"documento de teste", B.norm(it.get("ementa"))):
                continue
            it["chave_veto"] = _chave_projeto(sigla)
            st, txt, txt_en, situ, data_st = situacao_ssa(it, vetos)
            datas = [t[0] for t in it.get("tram") or [] if t[0]]
            prot = [t[0] for t in it.get("tram") or [] if t[0] and B.norm(t[1]).startswith("protocolad")]
            data = min(prot) if prot else (min(datas) if datas and it.get("n_tram", 0) <= len(it.get("tram") or []) else None)
            pid = C.ligar_nome(it.get("autor") or "", membros, tse, manual)
            if not pid:
                sem_ligacao[it.get("autor") or "?"] = sem_ligacao.get(it.get("autor") or "?", 0) + 1
                continue
            p = regional.proposta(f"{PREFIXO}:{sigla.replace('/', '-')}", sigla, comum, data, it.get("ementa"), situ, url_de(it),
                                  "autor", status=st, data_status=data_st, status_txt=txt)
            if txt_en:
                p["statusTxt_en"] = txt_en
            por[pid].append(p)
        if sem_ligacao:
            log("  CMS: autores fora da lista oficial de hoje (ficam fora): "
                + ", ".join(f"{n} ({q})" for n, q in sorted(sem_ligacao.items(), key=lambda kv: -kv[1])))
        for m in membros:
            f_prop = fonte(CASA["casa"], f"Sistema legislativo: proposições de {m['nome']} (Acompanhamento de proposição)", SISTEMA, h)
            extras[m["id"]]["propostas"] = regional.bloco_propostas(por[m["id"]], escopo[0], escopo[1], f_prop)
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
        notas.append(("As propostas vêm do sistema legislativo da Câmara (Acompanhamento de proposição): a lista de cada ano e "
                      "modalidade e a tramitação de cada proposição, de onde sai a situação. O sistema mostra um autor por "
                      "proposição; as da Mesa Executiva não aparecem em nenhum perfil, nem as de quem não está na lista oficial "
                      "de hoje. Ele também não tem um endereço fixo para a página de cada "
                      "proposição: o link leva ao texto da proposição (o PDF anexado como \"Íntegra\") ou à consulta oficial, onde "
                      "dá para buscar pela sigla (por exemplo, PLE-574/2025). A tramitação diz quando um projeto foi sancionado "
                      "ou promulgado, mas não o número da lei.",
                      "Bills come from the City Council's legislative system (bill tracking): the list for each year and type and "
                      "each bill's progress, from which the status is taken. The system shows one author per bill; bills by the "
                      "Council's board do not appear on any profile, nor do those by people who are not on today's official "
                      "list. It also has no fixed address for each bill's page: the link "
                      "goes to the bill's text (the PDF attached as its full text) or to the official search, where you can look "
                      "up the bill's code (for example, PLE-574/2025). The progress record says when a bill was signed or "
                      "promulgated, but not the law's number."))
    else:
        notas.append(("As propostas dos vereadores não entram neste site: a Câmara publica as proposições só no sistema "
                      "legislativo dela, em páginas HTML, sem dados abertos.",
                      "Councilors' bills are not included on this site: the City Council publishes its bills only in its "
                      "legislative system, as web pages, without open data."))
    # prefeito: os projetos do Executivo (autor "Executivo Municipal")
    prefeito = None
    pref = B.cidade(IBGE, UF).get("prefeito") or {}
    if est["_completo"] and pref.get("id"):
        inicio = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
        vetos = vetos_por_projeto(est.get("itens") or {})
        lst = []
        for sigla, it in (est.get("itens") or {}).items():
            comum = MODALIDADES.get(it.get("mod"))
            if comum not in ("PL", "PLP", "PELO") or not it.get("lido") or B.norm(it.get("autor")) != "executivo municipal":
                continue
            it["chave_veto"] = _chave_projeto(sigla)
            st, txt, txt_en, situ, data_st = situacao_ssa(it, vetos)
            prot = [t[0] for t in it.get("tram") or [] if t[0] and B.norm(t[1]).startswith("protocolad")]
            data = min(prot) if prot else None
            if (data or f"{it.get('ano')}-12-31") < inicio:
                continue
            p = regional.proposta(f"{PREFIXO}:{sigla.replace('/', '-')}", sigla, comum, data, it.get("ementa"), situ, url_de(it),
                                  "autor", status=st, data_status=data_st, status_txt=txt)
            if txt_en:
                p["statusTxt_en"] = txt_en
            lst.append(p)
        if lst:
            f_pref = fonte(CASA["casa"], "Sistema legislativo: proposições do Executivo Municipal (Acompanhamento de proposição)", SISTEMA, h)
            prefeito = (pref["id"], {"propostas": regional.bloco_propostas(
                lst, "Projetos que a prefeitura mandou à Câmara Municipal desde 1º/1/2025 (projetos de lei, de lei complementar "
                     "e de emenda à Lei Orgânica), segundo o sistema legislativo da Câmara",
                "Bills the mayor's office sent to the City Council since January 1, 2025 (ordinary and complementary bills and "
                "amendments to the city's Organic Law), according to the City Council's legislative system", f_pref),
                "fontes": [f_pref]})
        else:
            notas.append(("Não achamos no sistema legislativo da Câmara projetos do \"Executivo Municipal\" desde 1º/1/2025: o "
                          "perfil do prefeito não mostra os projetos dele.",
                          "We found no bills by the \"Municipal Executive\" since January 1, 2025 in the City Council's "
                          "legislative system, so the mayor's profile does not list them."))
    elif not est["_completo"] and pref.get("id"):
        antes = C.publicados(IBGE).get(pref["id"])
        if antes:
            prefeito = (pref["id"], {"propostas": antes, "fontes": [antes["fonte"]] if antes.get("fonte") else []})
    votos = [n for n in B.NOTAS_VOTOS_GASTOS.get(IBGE, []) if "votações" in n[0]]
    notas += votos + [GASTOS_NOTA]
    cobertura = {"lista": True, "propostas": com_prop, "votacoes": False, "gastos": False}
    r = B.salvar(IBGE, UF, CASA, membros, extras, cobertura, notas, escopo if com_prop else None, prefeito=prefeito)
    r["semTse"] = len(tse.sem_ligacao)
    r["requisicoes"] = s.n + 1
    if not est["_completo"]:
        r["pendente"] = True
        r["etapa"] = (f"propostas ({est['_total'] - est['_faltam']} de {est['_total']} tramitações lidas)" if est["_total"]
                      else "propostas (lendo as listas)")
    log(f"  CMS: {len(membros)} no cargo, {r['propostas']} propostas"
        f"{' (primeira carga em andamento)' if not est['_completo'] else ''}, {s.n} pedidos, {time.time() - t0:.0f} s")
    return r
