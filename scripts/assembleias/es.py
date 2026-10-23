"""Assembleia Legislativa do Estado do Espírito Santo (Ales): API pública do Sistema de Processo Legislativo (SPL),
documentada no Portal de Dados Abertos da Ales (www3.al.es.gov.br/dados-abertos.aspx).

Lista: GET /api/publico/parlamentar/?parlamentarSituacao=1 (deputados ativos): nome, partido, foto, e-mail e o código
de autor de cada deputado (30 cadeiras). Página oficial: www.al.es.gov.br/Deputado/<NomeSemEspaços>.
Propostas: GET /api/publico/proposicao/?sigla=<tipo>&ano=<ano> (PL, PLC = PLP, PEC, PDL e PR = PRC, de 2023 em diante),
com autor, coautores, situação e a tramitação completa. O autor (AutorRequerenteDados) é o autor principal; os
coautores, quando a Ales informa, entram como coautores. Os dados pessoais que a API traz junto (CPF, endereço) não são
guardados.
A API devolve cada proposição com toda a tramitação (respostas grandes e lentas): cada rodada lê, primeiro, a primeira
página de cada tipo no ano de hoje (as novas) e depois continua um rodízio pelas outras páginas, até ALES_SEGUNDOS
segundos (150). O que já foi lido fica no cache e é atualizado quando o rodízio passa de novo.
Situação: "Tramitando", "Apensado" ou "Arquivado", com a tramitação para separar (regras em _situacao): sanção do
governador, publicação da norma ou "Compilar Norma" = virou lei; "Publicar Ato Normativo" = decreto legislativo ou
resolução publicado (virou norma); "Posicionamento do Governador" sem decisão registrada = aprovado e enviado ao
governador.
Votações nominais: a Ales publica "Boletins de Votação Nominal" como documentos (PDF); não entram. Gastos: não há
publicação aberta da verba de cada gabinete na API.
"""
from __future__ import annotations

import os
import re
import time

import regional
from comum import data_iso, hoje, log, sem_acento

from ._sse_comum import (Rede, casar_membros, com_status_en, desde, escopo, fonte, gravar, legislatura, membro,
                         partido_sigla, resumo_status)

UF = "ES"
SITE = "https://www.al.es.gov.br"
API = "https://www3.al.es.gov.br/api/publico"
VEICULO = "Assembleia Legislativa do Estado do Espírito Santo (Ales)"
CASA = {"casa": "Assembleia Legislativa do Estado do Espírito Santo", "casa_en": "Legislative Assembly of the State of Espírito Santo",
        "sigla": "Ales", "site": SITE}
INICIO = legislatura(UF)["inicio"]
TIPOS = {"PL": "PL", "PLC": "PLP", "PEC": "PEC", "PDL": "PDL", "PR": "PRC"}
POR_PAGINA = 50

# ligações com o TSE conferidas à mão: {código do deputado na Ales: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
# (a biografia oficial de cada um, no próprio serviço de dados da Ales, dá o nome civil e a eleição de 2022)
MANUAL: dict[str, str] = {
    "466": "80001604502",  # Alcântaro Filho = "ALCÂNTARO" (Alcântaro Victor Lazzarini Campos, Republicanos)
    "48": "80001602765",   # Gandini = "FABRÍCIO GANDINI" (Fabricio Gandine Aquino, Cidadania em 2022, 16.948 votos)
}


def _slug(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", sem_acento(nome or ""))


def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], dict[str, str], list[str]]:
    d = rede.json(f"{API}/parlamentar/?pag=1&qtd=200&parlamentarSituacao=1", "parlamentares.json", 20, timeout=180)
    lista = [x for x in d.get("parlamentares") or [] if (x.get("parlamentarSituacao") or "").lower().startswith("ativ")]
    if not 25 <= len(lista) <= 35:
        raise RuntimeError(f"Ales: a lista oficial veio com {len(lista)} pessoas")
    pessoas = [{"chave": str(x["parlamentarID"]), "nome": (x.get("parlamentarRazaoSocial") or x.get("parlamentarNome") or "").strip(),
                "nomeCivil": None, "partido": partido_sigla(x.get("partidoSigla")), "foto": x.get("parlamentarFoto"),
                "email": x.get("parlamentarEmail"), "autor": str(x.get("autorID") or "")} for x in lista]
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids, autores = [], {}, {}
    for p in pessoas:
        cand = casados.get(p["chave"])
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[p["chave"]] = pid
        if p["autor"]:
            autores[p["autor"]] = p["chave"]
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"), p["foto"], f"{SITE}/Deputado/{_slug(p['nome'])}",
                   (cand or {}).get("sit") == "SUPLENTE")
        m["_email"] = p["email"]
        membros.append(m)
    return membros, ids, autores, avisos


def _resumo(x: dict) -> dict:
    """Só o que o site usa (a API traz também CPF e endereço de quem assina, que não são guardados)."""
    autor = x.get("AutorRequerenteDados") or {}
    co = [str(c.get("autorId") or c.get("autorID") or "") for c in (x.get("CoAutores") or []) if isinstance(c, dict)]
    fases = [" / ".join(s for s in ((t.get("fase") or "").strip(), (t.get("acao") or "").strip()) if s)
             for t in x.get("Tramitacoes") or []]
    return {"id": x.get("id"), "sigla": x.get("sigla"), "numero": x.get("numero"), "ano": x.get("ano"),
            "ementa": (x.get("assunto") or "").strip() or None, "data": data_iso(x.get("data")), "situacao": x.get("situacao"),
            "autor": str(autor.get("autorId") or ""), "coautores": [c for c in co if c], "fases": fases[:40],
            "arquivo": x.get("arquivo")}


def _proposicoes(rede: Rede) -> dict:
    est = rede.estado("estado.json", {}) or {}
    itens, cursor = est.get("itens", {}), est.get("cursor", 0)
    limite = float(os.environ.get("ALES_SEGUNDOS", "150"))
    t0 = time.time()
    atual = int(hoje()[:4])
    total = est.get("total", {})

    def ler(sig, ano, pag):
        d = rede.json(f"{API}/proposicao/?pag={pag}&qtd={POR_PAGINA}&sigla={sig}&ano={ano}", None, timeout=300)
        total[f"{sig}-{ano}"] = d.get("total") or 0
        for x in d.get("Data") or []:
            r = _resumo(x)
            if r["id"]:
                itens[str(r["id"])] = r

    for sig in TIPOS:  # as novas (primeira página de cada tipo no ano de hoje) e os anos ainda sem total conhecido
        for ano in range(int(INICIO[:4]), atual + 1):
            if ano == atual or f"{sig}-{ano}" not in total:
                ler(sig, ano, 1)
    blocos = []  # (tipo, ano, página) de todo o período, para o rodízio
    for sig in TIPOS:
        for ano in range(int(INICIO[:4]), atual + 1):
            paginas = max(1, -(-int(total.get(f"{sig}-{ano}") or 0) // POR_PAGINA))
            blocos += [(sig, ano, p) for p in range(1, paginas + 1)]
    while blocos and time.time() - t0 < limite:
        sig, ano, pag = blocos[cursor % len(blocos)]
        try:
            ler(sig, ano, pag)
        except Exception as e:
            log(f"  ES: {sig} {ano} página {pag}: {e}")
        cursor = (cursor + 1) % len(blocos)
        if cursor == 0:
            break
    rede.guardar({"itens": itens, "cursor": cursor, "total": total}, "estado.json")
    return itens


def _situacao(x: dict) -> tuple[str, str | None]:
    """(status, detalhe). As fases vêm da mais nova para a mais antiga, como "fase / ação". Conferido à mão
    (out/2026): "Posicionamento do Governador / Norma Sancionada", "Resgistro da Publicação da Norma Sancionada" e
    "Compilar Norma" = virou lei; "Publicar Ato Normativo" = decreto legislativo ou resolução publicado; "Posicionamento
    do Governador" sem ação = enviado ao governador, ainda sem registro da decisão."""
    sit = (x.get("situacao") or "").strip()
    fases = sem_acento(" | ".join(x.get("fases") or []).lower())
    s = sem_acento(sit.lower())
    if re.search(r"compilar norma|norma compilada|norma sancionada|publicar ato normativo|ato normativo com veto parcial|"
                 r"governador[^|]*/ veto parcial", fases):
        return "lei", ("parcial" if re.search(r"veto parcial", fases) else None)
    if s.startswith(("apensad", "anexad")):  # "Anexado" = anexada a outra proposição (art. 178 do Regimento Interno)
        return "junta", None
    if re.search(r"governador[^|]*/ veto total|publicacao do veto total", fases):
        return "rejeitada", "veto"
    if s.startswith("arquivad"):
        if re.search(r"retirad[oa] pelo autor|retirada da proposicao|requerimento de retirada|a pedido do\(?s?\)? autor", fases):
            return "retirada", None
        if re.search(r"rejeitad|nao aprovad|rejeicao da proposicao principal", fases):
            return "rejeitada", None
        # a Mesa devolveu ao autor (proposta fora das regras) e ninguém recorreu, ou o recurso manteve a devolução
        if re.search(r"devolucao da proposicao ao autor|manutencao do despacho da mesa|devolver para o autor", fases):
            return "parada", None
        # aprovada em Plenário e arquivada na hora do autógrafo (ex.: PL 12, 48, 81 e 89/2023, do mesmo assunto): a Ales
        # não registra norma própria para ela
        if re.search(r"extracao de autografos / arquivo", fases) and re.search(r"aprovacao da proposicao principal", fases):
            return "arquivada", "aprovada"
        return "arquivada", None
    if re.search(r"posicionamento do governador|aguardando sancao", fases[:400]):
        return "aprovada", None
    if re.search(r"elaborar ato normativo", fases[:300]):
        return "aprovada", "promulgar"
    return "andando", None


def coletar() -> dict:
    rede = Rede("ales", pausa=1.0)
    membros, ids, autores, avisos = _membros(rede)
    for a in avisos:
        log(f"  ES: {a}")
    itens = _proposicoes(rede)
    hj = hoje()
    por_dep: dict[str, list] = {}
    for x in itens.values():
        sig = (x.get("sigla") or "").strip().upper()
        if sig not in TIPOS or (x.get("data") or "") < INICIO:
            continue
        quem = [autores[a] for a in dict.fromkeys([x.get("autor")] + (x.get("coautores") or [])) if a in autores]
        if not quem:
            continue
        st, extra = _situacao(x)
        for k in quem:
            p = regional.proposta(f"ales:{x['id']}", f"{sig} {x.get('numero')}/{x.get('ano')}", TIPOS[sig], x.get("data"),
                                  x.get("ementa"), (x.get("situacao") or "").strip() or None,
                                  x.get("arquivo") or "https://www3.al.es.gov.br/spl/", papel="autor" if autores.get(x.get("autor")) == k else "coautor",
                                  status=st)
            if st == "lei" and extra == "parcial":
                com_status_en(p, "Virou lei (com partes vetadas)", "Became law (with some parts vetoed)")
            elif st == "aprovada" and extra == "promulgar":
                com_status_en(p, "Aprovada; esperando ser promulgada", "Approved; waiting to be promulgated")
            elif st == "aprovada":
                com_status_en(p, "Aprovada pela Assembleia e enviada ao governador (sanção ou veto)",
                              "Approved by the Assembly and sent to the governor (to sign or veto)")
            elif st == "arquivada" and extra == "aprovada":
                com_status_en(p, "Aprovada pela Assembleia e depois arquivada (a Ales não registra lei própria para ela)",
                              "Approved by the Assembly and then archived (the Assembly records no law of its own for it)")
            elif extra == "veto":
                com_status_en(p, "Aprovada pela Assembleia, mas vetada por inteiro pelo governador",
                              "Approved by the Assembly, but fully vetoed by the governor")
            por_dep.setdefault(k, []).append(p)
    f_lista = fonte(VEICULO, "Dados Abertos: API pública de parlamentares (deputados ativos)", "https://www3.al.es.gov.br/dados-abertos.aspx", hj)
    f_prop = [fonte(VEICULO, "Dados Abertos: API pública de proposições (com a tramitação)", "https://www3.al.es.gov.br/dados-abertos.aspx", hj),
              fonte(VEICULO, "Consulta de proposições no Sistema de Processo Legislativo (SPL)", "https://www3.al.es.gov.br/spl/", hj)]
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"),
                            "O link de cada proposta abre o documento oficial (PDF).", "Each proposal's link opens the official document (PDF).")
    extras = {}
    for m in membros:
        k = next(n for n, v in ids.items() if v == m["id"])
        extras[m["id"]] = {"links": {"oficial": m["url"], "email": m.pop("_email", None), "redes": []},
                           "propostas": regional.bloco_propostas(por_dep.get(k) or [], esc_pt, esc_en, f_prop),
                           "fontes": [fonte(VEICULO, f"Página de {m['nome']} no portal da Ales", m["url"], hj)]}
    log(f"  ES: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    notas = [("A Ales publica os boletins de votação nominal só como documentos (PDF); as votações não entram.",
              "The Ales only publishes roll-call vote reports as documents (PDF); votes are not included.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": False},
                  f_lista, esc_pt, esc_en, notas)
