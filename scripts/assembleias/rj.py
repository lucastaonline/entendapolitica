"""Assembleia Legislativa do Estado do Rio de Janeiro (Alerj): página oficial "Quem são" (deputados em exercício).

Lista: www.alerj.rj.gov.br/Deputados/QuemSao: nome, partido, foto e página de cada deputado da legislatura atual
(70 cadeiras, inclusive suplentes que assumiram).
Propostas e votações dos deputados: não entram. A Alerj não tem API nem arquivo aberto do processo legislativo; o
sistema oficial de proposições (Lotus Notes, scpro2327.nsf) só pode ser lido página a página, pelo portal www3
(www3.alerj.rj.gov.br/lotus_notes/default.asp?id=..&url=<caminho em base64>), ~20 s por página, e a página de cada
projeto não tem um campo de situação (só a lista de despachos). Testado em 23/10/2026.
O governo do estado (perfil do governador, dados/pessoas/gov-RJ.json), desde o dia em que quem governa assumiu:
- projetos: a lista oficial de Mensagens do Poder Executivo (view MensInt, aberta com os passos de cada uma pelo portal
  www3, uma leitura por dia); entram os projetos de lei (código 03), de lei complementar (02) e de emenda à Constituição
  (01); a situação sai dos passos ("Resultado Final => Lei nº ..", ofício "Comunicar Sanção/Veto", autógrafo enviado
  ao Executivo, devolução);
- leis e vetos: o Diário Oficial do Estado em dados abertos (dadosabertos.rj.gov.br, Casa Civil/SECC: "Publicações por
  Tipo" I - Lei, I - Lei Complementar, I - Veto Parcial e I - Veto Total, um arquivo JSON por ano, achado na página de
  cada conjunto: a API do portal é fechada para robôs, e o robots.txt pede 10 s entre pedidos), contando tudo o que o
  governo assinou desde o começo do período (data da assinatura no texto), de quem estivesse no cargo; a nota diz
  quantas leis cada um assinou.
"""
from __future__ import annotations

import base64
import collections
import html as _html
import re
import urllib.parse

import regional
from comum import data_iso, hoje, log, nome_proprio, sem_acento

from ._sse_comum import (Rede, anterior_governo, bloco_executivo, casar_membros, com_status_en, desde, escopo_governo,
                         fonte, gravar, gravar_governo, membro, nome_lei, partido_sigla, periodo_governo, qtd, sem_html,
                         virou)

UF = "RJ"
SITE = "https://www.alerj.rj.gov.br"
VEICULO = "Assembleia Legislativa do Estado do Rio de Janeiro (Alerj)"
CASA = {"casa": "Assembleia Legislativa do Estado do Rio de Janeiro", "casa_en": "Legislative Assembly of the State of Rio de Janeiro",
        "sigla": "Alerj", "site": SITE,
        "sic": "https://www2.alerj.rj.gov.br/leideacesso/formulario-2016.asp"}  # pedido de informação (Lei de Acesso à Informação)

# ligações com o TSE conferidas à mão: {código do deputado na Alerj: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}

# ---------------------------------------------------------------- o governo (perfil do governador)
WWW3 = "https://www3.alerj.rj.gov.br/lotus_notes/default.asp"
MENSAGENS = "/scpro2327.nsf/Internet/MensInt?OpenForm&Start={start}&Count=1000&ExpandView"
PORTAL_RJ = "https://dadosabertos.rj.gov.br"
DOERJ = {"lei": "secc_doerj_i_lei", "lc": "secc_doerj_i_lei_complementar", "parcial": "secc_doerj_i_veto_parcial",
         "total": "secc_doerj_i_veto_total"}
TIPO_COD = {"03": ("PL", "PL"), "02": ("PLC", "PLP"), "01": ("PEC", "PEC")}  # 5º e 6º dígitos do código do projeto
MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]


def _www3(caminho: str, id_: int = 166) -> str:
    """Endereço público (portal www3) de uma página do sistema de proposições da Alerj."""
    return f"{WWW3}?id={id_}&url={urllib.parse.quote(base64.b64encode(caminho.encode('latin-1')).decode())}"


def _mensagens(rede: Rede, ini: str) -> list[dict]:
    """Mensagens do Poder Executivo publicadas de ini em diante, cada uma com os passos (view MensInt aberta, da mais
    nova para a mais antiga; a página seguinte só é lida se a primeira não chegar até ini)."""
    regs: list[dict] = []
    start = 1
    for pagina in range(1, 6):
        t = rede.texto(_www3(MENSAGENS.format(start=start)), f"governo/mensagens-{pagina}.html", 20, timeout=180)
        seg = t[t.find('id="divConteudo"'):]
        atual, lidos = None, 0
        for tr in re.findall(r"<tr\b.*?</tr>", seg, re.S | re.I):
            cels = [_html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
                    for c in re.findall(r"<td\b.*?>(.*?)</td>", tr, re.S | re.I)]
            docs = [_html.unescape(d) for d in re.findall(r'data-role="([^"]*OpenDocument[^"]*)"', tr)]
            if len(cels) >= 5 and re.match(r"\d+/\d{4}$", cels[0]):
                m = re.search(r"=>\s*(\d{11})\s*$", cels[2])
                atual = {"num": cels[0], "ementa": re.sub(r"\s*=>\s*\d+\s*$", "", cels[2]).strip(),
                         "cod": m.group(1) if m else None, "data": data_iso(cels[3]), "autor": cels[4],
                         "doc": docs[-1] if docs else None, "passos": []}
                lidos += 1
                if not regs or regs[-1]["num"] != atual["num"] or regs[-1]["data"] != atual["data"]:
                    regs.append(atual)
                else:  # a mensagem que fechou a página anterior volta inteira no começo desta
                    regs[-1] = atual
            elif atual is not None and any(cels):
                atual["passos"].append(" | ".join(c for c in cels if c))
        if not lidos:
            raise RuntimeError("Alerj: a lista de Mensagens do Executivo veio vazia")
        if min((r["data"] or "9") for r in regs) < ini or lidos < 2:
            break
        start += lidos - 1
    return [r for r in regs if (r["data"] or "") >= ini]


def _situacao_msg(passos: list[str], devolvida: bool) -> tuple[str, tuple | None, str | None, str | None]:
    """(status, (tipo, número, ano) da norma, detalhe, data da última etapa) pelos passos da mensagem."""
    txt = " | ".join(passos)
    datas = [data_iso(d) for d in re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", txt)]
    ult = max((d for d in datas if d), default=None)
    m = re.search(r"Resultado Final => \d+ => (Lei Complementar|Lei|Emenda Constitucional)\s*(?:n[º°o.]*\s*)?([\d.]+)/(\d{4})", txt)
    parcial = "parcial" if re.search(r"(?i)comunicar veto parcial", txt) else None
    if m:
        return "lei", (m.group(1), m.group(2).replace(".", ""), m.group(3)), parcial, ult
    if re.search(r"(?i)comunicar veto total", txt):
        return "rejeitada", None, "veto", ult
    if parcial:  # sancionada com partes vetadas; o número da lei aparece depois, no "Resultado Final"
        return "lei", None, "parcial", ult
    if re.search(r"(?i)comunicar san[cç][aã]o", txt):
        return "lei", None, None, ult
    if devolvida or re.search(r"(?i)proceda-se [àa] devolu[cç][aã]o", txt):
        return "retirada", None, None, ult
    if re.search(r"(?i)envio ao poder executivo", txt):
        return "aprovada", None, None, ult
    if re.search(r"Votação => \d+ => (?!Requerimento|Parecer|Emenda)[^|]*=> Rejeitad", txt):
        return "rejeitada", None, None, ult
    if any(p.startswith("Arquivo") for p in passos):
        return "arquivada", None, None, ult
    return "andando", None, None, ult


def _governo_projetos(rede: Rede, ini: str) -> list[dict]:
    regs = _mensagens(rede, ini)
    devolvidas = set()  # "RETIRADA E DEVOLUÇÃO DA(S) MENSAGEM(NS) Nº 08/2026 E 10/2026"
    for r in regs:
        if re.search(r"(?i)retirada|devolu", r["ementa"]) and not (r["cod"] or "")[4:6] in TIPO_COD:
            devolvidas.update(re.findall(r"\b(\d{1,3}/\d{4})\b", r["ementa"]))
    out = []
    for r in regs:
        cod = r["cod"] or ""
        if not re.match(r"(?i)poder executivo", r["autor"] or "") or cod[4:6] not in TIPO_COD:
            continue
        sig, tipo = TIPO_COD[cod[4:6]]
        st, norma, extra, ult = _situacao_msg(r["passos"], r["num"] in devolvidas)
        # situação: o "Resultado Final" ou, sem ele, o passo mais recente
        datados = sorted(r["passos"], key=lambda p: data_iso((re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", p) or ["01/01/1900"])[-1]) or "")
        base = next((x for x in r["passos"] if x.startswith("Resultado Final")), datados[-1] if datados else None)
        sit = re.sub(r"\s*=>\s*", " – ", re.sub(r"\s*=>\s*\d{11}\s*(=>)?\s*", ": ", base.split(" | ")[0])).strip(" –:") \
            if base else "Mensagem publicada"
        p = regional.proposta(f"alerj:{cod}", f"{sig} {int(cod[6:])}/{cod[:4]}", tipo, r["data"], r["ementa"] or None,
                              sit[:160] or None, _www3(r["doc"]) if r["doc"] else _www3(MENSAGENS.format(start=1)),
                              papel="autor", status=st, data_status=ult)
        if norma:
            nome = nome_lei(*norma)
            virou(p, nome + (" (com partes vetadas)" if extra == "parcial" else ""), None)
            p["lei"]["nome"] = nome
        elif st == "lei" and extra == "parcial":
            com_status_en(p, "Virou lei, com partes vetadas (a página oficial não mostra o número)",
                          "Became law, with some parts vetoed (the official page does not show the number)")
        elif st == "lei":
            com_status_en(p, "Virou lei (a página oficial não mostra o número)", "Became law (the official page does not show the number)")
        elif extra == "veto":
            com_status_en(p, "Aprovada pela Assembleia, mas vetada por inteiro", "Approved by the Assembly, but fully vetoed")
        elif st == "aprovada":
            com_status_en(p, "Aprovada pela Assembleia e enviada ao governo para sanção ou veto",
                          "Approved by the Assembly and sent to the governor to sign or veto")
        elif st == "retirada":
            com_status_en(p, "O governo retirou o projeto", "The government withdrew the bill")
        out.append(p)
    return out


def _doerj(rede: Rede, chave: str, ini: str) -> list[tuple[str, str, str]]:
    """[(id, data de publicação, texto)] das publicações do tipo no Diário Oficial (dados abertos da SECC) desde ini. A
    página de cada conjunto lista os arquivos (um por ano: "i_lei_2026_parte_1.json"); a API do portal (/api/) é fechada
    para robôs no robots.txt, que também pede 10 s entre pedidos (a Rede respeita)."""
    pag = rede.texto(f"{PORTAL_RJ}/dataset/{DOERJ[chave]}", f"doerj/{chave}.html", 24 * 3, timeout=120)
    arquivos = dict.fromkeys(re.findall(r'href="(https://dadosabertos\.rj\.gov\.br/dataset/[^"]+/download/[^"/]+?_(\d{4})'
                                        r'_parte_(\d+)\.json)"', pag))
    if not arquivos:
        raise RuntimeError(f"Diário Oficial do RJ: a página do conjunto {DOERJ[chave]} veio sem os arquivos")
    out = []
    for url, ano, parte in arquivos:
        if ano < ini[:4]:
            continue
        d = rede.json(url, f"doerj/{chave}-{ano}-{parte}.json", 20 if ano == hoje()[:4] else 24 * 7, timeout=300)
        for sec in (d or {}).values():
            for k, v in (sec or {}).items():
                if isinstance(v, list) and len(v) >= 2 and (v[0] or "")[:10] >= ini:
                    out.append((str(k), v[0][:10], v[1] or ""))
    return out


def _signatarios(txt: str) -> list[str]:
    """Nomes que assinam o texto: a linha em maiúsculas logo antes de "Governador" / "Governador em exercício" (às
    vezes o texto do Diário vem com a linha cortada, só "xercício")."""
    linhas = [l.strip() for l in (txt or "").replace("\r", "").split("\n") if l.strip()]
    out = []
    for a, b in zip(linhas, linhas[1:]):
        if re.match(r"(?i)(governador|e?x?erc[íi]cio\b)", b) and len(a.split()) >= 2 and len(a) <= 60 and \
                re.fullmatch(r"[A-ZÀ-Ý][A-ZÀ-Ý .'-]+", a) and not re.search(r"\b(ESTADO|GOVERNADOR|LEI)\b", a):
            out.append(a)
    return out


def _projeto(txt: str) -> str | None:
    m = re.search(r"(?i)projeto de lei( complementar)?\s*n[º°o.]*\s*([\d.]+)(?:-[A-Z])?\s*/\s*(\d{4})", txt)
    return f"{'PLC' if m.group(1) else 'PL'} {m.group(2).replace('.', '')}/{m.group(3)}" if m else None


def _assinada(txt: str) -> str | None:
    """Data da assinatura ("Rio de Janeiro, 15 de outubro de 2026")."""
    m = re.search(r"Rio de Janeiro,?\s*(\d{1,2})[º°]?\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{4})", txt)
    if not m or sem_acento(m.group(2)).lower() not in MESES:
        return None
    return f"{m.group(3)}-{MESES.index(sem_acento(m.group(2)).lower()) + 1:02d}-{int(m.group(1)):02d}"


def _executivo(rede: Rede, per: dict, hj: str) -> dict | None:
    """Leis e vetos que o governo assinou de per["inicio"] até hoje (data da assinatura no texto; sem ela, a da
    publicação), de quem estivesse no cargo, pelo Diário Oficial em dados abertos."""
    ini = per["inicio"]
    leis: dict[str, tuple[str, str, str | None]] = {}  # projeto -> (data, tipo, quem assinou)
    totais: dict[str, tuple[str, str | None]] = {}
    parciais: dict[str, tuple[str, str | None]] = {}
    for chave in ("lei", "lc", "parcial", "total"):
        for k, dt, txt in _doerj(rede, chave, ini):
            quando = _assinada(txt) or dt
            if not ini <= quando <= hj:
                continue
            quem = next(iter(_signatarios(txt)), None)
            proj = _projeto(txt)
            if chave in ("lei", "lc", "parcial"):  # "Veto Parcial" é a lei publicada com as partes vetadas
                leis.setdefault(f"{chave == 'lc'}-{proj or k}", (quando, chave, quem))
            if chave == "parcial":
                parciais.setdefault(proj or k, (quando, quem))
            elif chave == "total":
                ofi = re.search(r"(?i)of[íi]cio n[º°o.]*\s*(\d+)\s*-\s*M", txt)
                totais.setdefault(ofi.group(1) if ofi else (proj or k), (quando, quem))
    n_lc = sum(1 for _, c, _q in leis.values() if c == "lc")
    d_pt, d_en = desde(ini)
    # quem assinou (o texto do Diário traz o nome): diz quantas foram de cada um quando há mais de um
    por = collections.Counter(nome_proprio(q) if q else None for _, _, q in leis.values())
    if len(por) > 1:
        partes = [f"{n} " + (f"por {q}" if q else "sem o nome no texto do Diário") for q, n in por.most_common()]
        partes_en = [f"{n} " + (f"by {q}" if q else "with no name in the gazette text") for q, n in por.most_common()]
        quem_pt, quem_en = f": {', '.join(partes[:-1])} e {partes[-1]}", f": {', '.join(partes_en[:-1])} and {partes_en[-1]}"
    else:
        q = next(iter(por), None)
        quem_pt, quem_en = (f", todas por {q}", f", all by {q}") if q else ("", "")
    nt, np_ = len(totais), len(parciais)
    return bloco_executivo(
        per, [fonte("Governo do Estado do Rio de Janeiro (Casa Civil)", f"Diário Oficial do Estado em dados abertos: "
                    f"publicações do tipo \"{tit}\"", f"{PORTAL_RJ}/dataset/{DOERJ[k]}", hj)
              for k, tit in (("lei", "I - Lei"), ("lc", "I - Lei Complementar"), ("parcial", "I - Veto Parcial"),
                             ("total", "I - Veto Total"))],
        f"Leis: {qtd(len(leis) - n_lc, 'lei', 'leis')} e {qtd(n_lc, 'lei complementar', 'leis complementares')} assinadas "
        f"pelo governo desde {d_pt}, pela data da assinatura{quem_pt}. Contadas no Diário Oficial do Estado em dados "
        "abertos (publicações do tipo \"Lei\", \"Lei Complementar\" e \"Veto Parcial\", que é a lei publicada com as partes "
        f"vetadas). Vetos: {qtd(nt, 'total', 'totais')} e {qtd(np_, 'parcial', 'parciais')} no mesmo período. Cada lei conta "
        "uma vez (publicações repetidas do mesmo projeto ficam de fora).",
        f"Laws: {qtd(len(leis) - n_lc, 'law', 'laws')} and {qtd(n_lc, 'complementary law', 'complementary laws')} signed by "
        f"the government since {d_en}, by signing date{quem_en}. Counted in the State Official Gazette open data "
        "(publications of the types law, complementary law and partial veto, the latter being a law published with its "
        f"vetoed parts). Vetoes: {nt} full and {np_} partial in the same period. Each law counts once (repeated "
        "publications of the same bill are left out).",
        leis=len(leis), vetos=nt + np_, vetos_totais=nt, vetos_parciais=np_,
        ultima_lei=max((q for q, _, _x in leis.values()), default=None),
        ultimo_veto=max([q for q, _ in totais.values()] + [q for q, _ in parciais.values()], default=None))


def _governo(rede: Rede, hj: str) -> None:
    per = periodo_governo(UF)
    ini = per["inicio"]
    try:
        projetos = _governo_projetos(rede, ini)
    except Exception as e:  # o portal www3 fora do ar: fica a lista da rodada anterior
        log(f"  RJ: mensagens do Executivo: {e}")
        projetos = (anterior_governo(UF, "propostas") or {}).get("lista")
    try:
        executivo = _executivo(rede, per, hj)
    except Exception as e:  # o portal de dados abertos fora do ar: ficam as contas da rodada anterior
        log(f"  RJ: Diário Oficial em dados abertos: {e}")
        executivo = anterior_governo(UF, "executivo")
    esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                           "Lista oficial de Mensagens do Poder Executivo na Alerj; indicações de nomes para cargos e "
                           "pedidos de retirada não entram.",
                           "Official list of the executive branch's messages at the Alerj; nominations for public posts "
                           "and withdrawal requests are not included.")
    gravar_governo(UF, per, projetos, *esc_g,
                   fonte(VEICULO, "Mensagens do Poder Executivo (sistema de proposições da Alerj)",
                         _www3(MENSAGENS.format(start=1).replace("&ExpandView", "")), hj), executivo)


def coletar() -> dict:
    rede = Rede("alerj", pausa=1.5, timeout=120)
    t = rede.texto(f"{SITE}/Deputados/QuemSao", "quemsao.html", 20)
    pessoas = []
    for bloco in re.findall(r'<div class="controle_deputado[^"]*">(.*?)<span></span>', t, flags=re.S):
        m = re.search(r'href="/Deputados/PerfilDeputado/(\d+)\?Legislatura=(\d+)"', bloco)
        nome = sem_html((re.search(r'<div class="nome">(.*?)</div>', bloco, re.S) or [None, ""])[1])
        if not m or not nome:
            continue
        foto = (re.search(r'<img src="([^"]+)"', bloco) or [None, None])[1]
        pessoas.append({"chave": m.group(1), "nome": nome_proprio(nome), "nomeCivil": None,
                        "partido": partido_sigla(sem_html((re.search(r'<div class="partido">(.*?)</div>', bloco, re.S) or [None, ""])[1])),
                        "url": f"{SITE}/Deputados/PerfilDeputado/{m.group(1)}?Legislatura={m.group(2)}",
                        "foto": (SITE + foto) if foto and foto.startswith("/") else foto})
    if not 60 <= len(pessoas) <= 75:
        raise RuntimeError(f"Alerj: a lista oficial veio com {len(pessoas)} pessoas")
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    for a in avisos:
        log(f"  RJ: {a}")
    membros = []
    for p in pessoas:
        cand = casados.get(p["chave"])
        membros.append(membro(regional.id_pessoa("dest", UF, cand, p["nome"]), p["nome"], None, p["partido"],
                              (cand or {}).get("genero"), p["foto"], p["url"], (cand or {}).get("sit") == "SUPLENTE"))
    hj = hoje()
    f_lista = fonte(VEICULO, "Deputados da legislatura atual (página oficial \"Quem são\")", f"{SITE}/Deputados/QuemSao", hj)
    # o perfil ganha só o link da página oficial de cada um (e a fonte), para quem quiser ver o resto no site da Alerj
    extras = {m["id"]: {"links": {"oficial": m["url"], "email": None, "redes": []},
                        "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da Alerj", m["url"], hj)]} for m in membros}
    try:
        _governo(rede, hj)
    except Exception as e:  # o perfil do governador fica como estava; a lista dos deputados é gravada
        log(f"  RJ: governo: {e}")
    log(f"  RJ: {rede.pedidos} pedidos à rede")
    notas = [("As propostas e as votações dos deputados não entram: a Alerj não publica o processo legislativo em formato "
              "aberto (não há API nem arquivo para baixar), e a página de cada projeto não tem um campo de situação. Cada "
              "projeto pode ser consultado no site da Alerj (Processo Legislativo).",
              "The deputies' bills and votes are not included: the Alerj does not publish its legislative process in an open "
              "format (there is no API or downloadable file), and each bill's page has no status field. Each bill can be "
              "looked up on the Alerj website (legislative process section)."),
             ("Os deputados estaduais do Rio não recebem verba indenizatória (Portal da Transparência da Alerj, perguntas "
              "frequentes): por isso não há gastos dessa verba para mostrar.",
              "Rio de Janeiro's state deputies do not receive an expense allowance (Alerj transparency portal, FAQ), so there is "
              "no allowance spending to show.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": False, "votacoes": False, "gastos": False},
                  f_lista, None, None, notas)
