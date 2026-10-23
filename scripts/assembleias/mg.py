"""Assembleia Legislativa de Minas Gerais (ALMG): Dados Abertos da ALMG (https://dadosabertos.almg.gov.br).

Lista: arquivo "Deputados da atual legislatura" (nome, partido de hoje e página oficial), conferido com o serviço
"Deputados em exercício" da API; nome completo, gênero e tipo de mandato (efetivo ou suplente) vêm do registro de cada
deputado na API. Foto: a da página oficial (www.almg.gov.br/export/sites/portal/a-assembleia/deputados/fotos/<id>.jpg).
Propostas: arquivos anuais "Proposições" (CSV, de 2023 até o ano de hoje): PL, PLC (= PLP), PEC e PRE (= PRC)
publicados desde 1º/2/2023. Autor principal = o primeiro da lista de autores (o primeiro signatário); os outros são
coautores. Situação: o texto oficial ("Situacao") com as regras REGRAS; a norma (número da lei) vem da pesquisa da API
(situações "Transformado em norma jurídica" e "... com veto parcial").
Gastos: verba indenizatória pela API de prestação de contas (um pedido por deputado e mês, desde fevereiro de 2023),
somada por ano e tipo de despesa. O arquivo CSV "Verbas indenizatórias" da ALMG não serve: vem com os valores em branco.
Meses fechados há mais de 4 meses ficam no cache para sempre; cada rodada baixa no máximo ALMG_VERBAS_MAX meses (160),
os mais recentes primeiro. Enquanto faltam meses de alguém, fica o bloco de gastos da rodada anterior.
Votações nominais: a ALMG não publica o voto de cada deputado em formato aberto (só no texto das atas do Diário do
Legislativo); a API de reuniões de Plenário traz o resultado de cada votação, sem os votos. Por isso não entram.
A ALMG pede no máximo 2 pedidos ao mesmo tempo e 1 segundo entre um e outro: aqui é 1 por vez, com 1,1 s de pausa.
"""
from __future__ import annotations

import csv
import io
import json

import regional
from comum import PESSOAS, data_iso, hoje, ler_json, log, nome_proprio, sem_acento

from ._sse_comum import (Rede, bloco_gastos, casar_membros, com_status_en, desde, dia_rodizio, escopo, fonte, gravar,
                         legislatura, membro, nome_lei, partido_sigla, resumo_status, virou)

UF = "MG"
API = "https://dadosabertos.almg.gov.br/api/v2"
ARQ = "https://dadosabertos.almg.gov.br/arquivo"
SITE = "https://www.almg.gov.br"
VEICULO = "Assembleia Legislativa de Minas Gerais (ALMG)"
CASA = {"casa": "Assembleia Legislativa do Estado de Minas Gerais", "casa_en": "Legislative Assembly of the State of Minas Gerais",
        "sigla": "ALMG", "site": SITE}
INICIO = legislatura(UF)["inicio"]  # 2023-02-01 (troca sozinho na posse de 2027)
LEG = 20 + (int(INICIO[:4]) - 2023) // 4  # número da legislatura na ALMG (20ª: 2023–2027)
TIPOS = {"PL": "PL", "PLC": "PLP", "PEC": "PEC", "PRE": "PRC"}  # sigla da ALMG -> tipo do site

# situação oficial (sem acento, minúsculas) -> status do site; o que não bate aqui segue a tabela comum (comum.py)
REGRAS = [
    (r"desarquivad", "andando"),
    (r"proposicao nao recebida", "parada"),        # a Presidência não recebeu o projeto (devolvido)
    (r"retirad[oa] de tramitacao", "retirada"),    # retirado a pedido do autor
    (r"vetad[oa] totalmente", "rejeitada"),
    (r"^publicad|^recebid|encaminhad[oa] a mesa|cumprindo prazo|^aguardando publicacao$", "andando"),
]
FRASES = {  # situação oficial -> frase do site (português, inglês)
    "aguardando sancao": ("Aprovada; esperando a sanção ou o veto do governador", "Approved; waiting for the governor to sign or veto it"),
    "aguardando promulgacao": ("Aprovada; esperando ser promulgada", "Approved; waiting to be promulgated"),
    "projeto vetado totalmente": ("Aprovada pela Assembleia, mas vetada por inteiro pelo governador",
                                  "Approved by the Assembly, but fully vetoed by the governor"),
    "proposicao nao recebida": ("Não foi recebida pela Presidência da Assembleia (não pôde seguir)",
                                "Not accepted by the Assembly's presiding officer (could not go ahead)"),
}
NORMAS = {"LEI": "Lei", "LCP": "Lei Complementar", "EMC": "Emenda Constitucional", "RAL": "Resolução", "LDL": "Lei Delegada"}

# ligações com o TSE conferidas à mão: {id da ALMG: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {}


def _csv(b: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))


def _membros(rede: Rede) -> tuple[list[dict], dict, list[str]]:
    linhas = _csv(rede.bruto(f"{ARQ}/deputados-legislatura/download", "deputados.csv", 20))
    em = {str(x["id"]): x for x in rede.json(f"{API}/deputados/em_exercicio?formato=json", "em_exercicio.json", 20)["list"]}
    if len(em) < 60:
        raise RuntimeError(f"ALMG: só {len(em)} deputados em exercício na API")
    pagina = {str(l["Codigo"]): l for l in linhas}
    pessoas, fichas = [], {}
    for i, e in sorted(em.items()):
        ficha = rede.json(f"{API}/deputados/{i}?formato=json", f"deputados/{i}.json", 20 if dia_rodizio(i) else 24 * 8)["deputado"]
        fichas[i] = ficha
        pessoas.append({"chave": i, "nome": e["nome"], "nomeCivil": nome_proprio(ficha.get("nomeServidor")),
                        "partido": partido_sigla(ficha.get("partidoEleicao") or e.get("partido"))})
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        i, ficha, linha = p["chave"], fichas[p["chave"]], pagina.get(p["chave"]) or {}
        cand = casados.get(i)
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[i] = pid
        url = linha.get("PaginaAlmg") or f"{SITE}/deputados/{i}"
        suplente = (ficha.get("tipoMandato") or "").lower().startswith("suplente")
        if not suplente and (cand or {}).get("sit") == "SUPLENTE":
            suplente = "vaga"  # suplente na eleição de 2022 que ficou com a vaga (a ALMG diz "Efetivo")
        membros.append(membro(pid, p["nome"], p["nomeCivil"], partido_sigla(linha.get("Partido") or em[i].get("partido")),
                              ficha.get("sexo") or (cand or {}).get("genero"),
                              f"{SITE}/export/sites/portal/a-assembleia/deputados/fotos/{i}.jpg", url, suplente))
        m = membros[-1]
        m["_email"] = next((x["endereco"] if "@" in x["endereco"] else x["endereco"] + "@almg.gov.br"
                            for x in ficha.get("emails") or [] if x.get("endereco")), None)
    return membros, ids, avisos


def _proposicoes(rede: Rede) -> list[dict]:
    """Linhas dos arquivos anuais de proposições (só os tipos do site, desde 1º/2/2023). O ano de hoje é baixado todo
    dia; dos anos anteriores, no máximo um por dia (o mais velho), para não pesar no site oficial."""
    atual = int(hoje()[:4])
    anos = list(range(int(INICIO[:4]), atual + 1))
    velhos = sorted((a for a in anos[:-1] if not rede.fresco(f"proposicoes-{a}.csv", 70)),
                    key=lambda a: rede.idade_h(f"proposicoes-{a}.csv") or 1e9, reverse=True)
    renovar = set(velhos[:1]) | {a for a in anos if rede.idade_h(f"proposicoes-{a}.csv") is None}
    out = []
    for a in anos:
        ttl = 20 if a == atual or a in renovar else None
        b = rede.bruto(f"{ARQ}/proposicoes/download?ano={a}&tipo=CSV", f"proposicoes-{a}.csv", ttl, timeout=300)
        for l in _csv(b):
            sig = (l.get("SiglaTipoProposicao") or "").strip()
            if sig in TIPOS and (data_iso(l.get("DataPublicacao")) or "") >= INICIO:
                out.append(l)
    return out


def _normas(rede: Rede) -> dict[str, dict]:
    """{"PL 123/2023": {"nome": "Lei nº 24.567/2023", "url": ...}} pela pesquisa da API (renovada a cada 3 dias)."""
    est = rede.estado("normas.json")
    if est and rede.fresco("normas.json", 70):
        return est
    out = {}
    for sig in TIPOS:
        for sit in ("TNJUR", "TNJVP"):
            p = 1
            while True:
                d = rede.json(f"{API}/proposicoes/pesquisa/direcionada?tipo={sig}&ini={INICIO.replace('-', '')}&sit={sit}"
                              f"&tp=100&p={p}&ord=0&formato=json")["resultado"]
                for x in d.get("listaItem") or []:
                    ln = x.get("linkLegislacao") or {}
                    if not ln.get("tipo"):
                        continue
                    tipo = NORMAS.get(ln["tipo"]) or (x.get("norma") or "").split(" - ")[-1].strip() or "Norma"
                    out[f"{x['siglaTipoProjeto']} {x['numero']}/{x['ano']}"] = {
                        "nome": nome_lei(tipo, ln.get("numero"), ln.get("ano")),
                        "url": f"{SITE}/legislacao-mineira/{ln['tipo']}/{ln['numero']}/{ln['ano']}/"}
                if p * 100 >= int(d.get("noOcorrencias") or 0) or not d.get("listaItem"):
                    break
                p += 1
    rede.guardar(out, "normas.json")
    return out


def _autores(txt: str | None) -> list[str]:
    try:
        return [str(a["id"]) for a in json.loads(txt or "[]") if a.get("id")]
    except ValueError:
        return []


def _proposta(l: dict, papel: str, normas: dict) -> dict:
    sig = l["SiglaTipoProposicao"].strip()
    num, ano = l["Numero"].strip(), l["Ano"].strip()
    situacao = (l.get("Situacao") or "").strip() or None
    p = regional.proposta(
        f"almg:{sig}-{num}-{ano}", f"{sig} {num}/{ano}", TIPOS[sig], data_iso(l.get("DataPublicacao")), l.get("Ementa"),
        situacao, f"{SITE}/projetos-de-lei/{sig}/{num}/{ano}", papel=papel, data_status=data_iso(l.get("DataUltimaAcao")),
        regras=REGRAS)
    chave = sem_acento((situacao or "").lower())
    if p["status"] == "lei":
        n = normas.get(f"{sig} {num}/{ano}")
        parcial = "veto parcial" in chave
        if n:
            virou(p, n["nome"], n["url"])
            if parcial:
                p["statusTxt"] += " (com partes vetadas)"
        elif parcial:
            com_status_en(p, "Virou lei, com partes vetadas", "Became law, with some parts vetoed")
    else:
        for k, (pt, en) in FRASES.items():
            if chave.startswith(k):
                com_status_en(p, pt, en)
                break
    return p


def _gastos(rede: Rede, ids: dict[str, str]) -> tuple[dict[str, list], set[str]]:
    """({id ALMG: [(mês, tipo, valor)]}, ids com todos os meses já baixados) pela API de prestação de contas: um pedido
    por deputado e mês (o arquivo CSV "Verbas indenizatórias" da ALMG vem com os valores em branco). Meses com mais de
    4 meses não mudam mais (ficam no cache para sempre); os recentes são conferidos uma vez por semana. Cada rodada faz
    no máximo VERBAS_MAX pedidos de meses (os mais recentes primeiro): no começo, a coleta completa leva alguns dias."""
    import os
    limite = int(os.environ.get("ALMG_VERBAS_MAX", "160"))
    hj = hoje()
    ano, mes = int(hj[:4]), int(hj[5:7]) - 4
    if mes <= 0:
        ano, mes = ano - 1, mes + 12
    corte = f"{ano}-{mes:02d}"  # meses antes deste já estão fechados e não mudam mais
    pedidos, faltas = [], {}
    meses_dep: dict[str, list[str]] = {}
    for i in ids:
        d = rede.json(f"{API}/prestacao_contas/verbas_indenizatorias/deputados/{i}/datas?formato=json",
                      f"verbas/{i}/datas.json", 20 if dia_rodizio(i) else 24 * 8)
        meses = sorted({(x.get("dataReferencia") or "")[:7] for x in d.get("listaFechamentoVerba") or []
                        if (x.get("dataReferencia") or "")[:7] >= INICIO[:7]})
        meses_dep[i] = meses
        for m in meses:
            cache = f"verbas/{i}/{m}.json"
            ttl = None if m < corte else (20 if dia_rodizio(i + m) else 24 * 8)
            if not rede.fresco(cache, ttl):
                pedidos.append((m, i, cache, ttl))
    pedidos.sort(reverse=True)  # os meses mais recentes primeiro
    feitos = set()
    for m, i, cache, ttl in pedidos[:limite]:
        try:
            rede.json(f"{API}/prestacao_contas/verbas_indenizatorias/deputados/{i}/{int(m[:4])}/{int(m[5:])}?formato=json",
                      cache, ttl)
            feitos.add(cache)
        except Exception as e:  # um mês fora do ar não derruba a coleta
            log(f"  MG: verba {i} {m}: {e}")
    for m, i, cache, ttl in pedidos:
        if cache not in feitos and not rede.caminho(cache).exists():
            faltas[i] = faltas.get(i, 0) + 1
    if len(pedidos) > limite:
        log(f"  MG: verba indenizatória: {len(pedidos) - limite} meses ficam para as próximas rodadas")
    out: dict[str, list] = {}
    for i, meses in meses_dep.items():
        for m in meses:
            arq = rede.caminho(f"verbas/{i}/{m}.json")
            if not arq.exists():
                continue
            for x in json.loads(arq.read_text(encoding="utf-8")).get("list") or []:
                v = x.get("valor")
                if v:
                    out.setdefault(i, []).append((m, (x.get("descTipoDespesa") or "Outros").strip(), float(v)))
    completos = {i for i in ids if not faltas.get(i)}
    return out, completos


def coletar() -> dict:
    rede = Rede("almg", pausa=1.1)
    membros, ids, avisos = _membros(rede)
    for a in avisos:
        log(f"  MG: {a}")
    linhas = _proposicoes(rede)
    normas = _normas(rede)
    gastos, completos = _gastos(rede, ids)
    hj = hoje()
    f_lista = fonte(VEICULO, "Dados Abertos: deputados da atual legislatura e deputados em exercício",
                    "https://dadosabertos.almg.gov.br/documentacao/arquivos/deputados-da-atual-legislatura", hj)
    f_prop = fonte(VEICULO, "Dados Abertos: proposições (arquivos anuais) e pesquisa de proposições transformadas em norma",
                   "https://dadosabertos.almg.gov.br/documentacao/arquivos/proposicoes", hj)
    por_dep: dict[str, list] = {}
    for l in linhas:
        aut = _autores(l.get("Autores"))
        for k, a in enumerate(dict.fromkeys(aut)):
            if a in ids:
                p = _proposta(l, "autor" if k == 0 else "coautor", normas)
                if p:
                    por_dep.setdefault(a, []).append(p)
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PRC"))
    extras = {}
    for m in membros:
        i = next(k for k, v in ids.items() if v == m["id"])
        email = m.pop("_email", None)
        x: dict = {"links": {"oficial": m["url"], "email": email, "redes": []}}
        lista = por_dep.get(i) or []
        f_pessoa = fonte(VEICULO, f"Proposições de {m['nome']} no portal da ALMG",
                         f"{SITE}/atividade-parlamentar/projetos-de-lei/?pesquisou=true&idDeputado={i}&dataInicio=&dataFim=&ordem=0", hj)
        x["propostas"] = regional.bloco_propostas(lista, esc_pt, esc_en, [f_pessoa, f_prop])
        g = bloco_gastos(gastos.get(i) or [], [
            fonte(VEICULO, f"Verba indenizatória de {m['nome']} (prestação de contas no portal da ALMG)",
                  f"{SITE}/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/detalhe.html?id={i}&leg={LEG}", hj),
            fonte(VEICULO, "Dados Abertos: lista mensal de itens de verba indenizatória de um deputado",
                  "https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest#/", hj)], inicio=INICIO)
        if i not in completos:  # ainda faltam meses no cache: fica o bloco da rodada anterior, se houver
            g = (ler_json(PESSOAS / f"{m['id']}.json", {}) or {}).get("gastos")
        if g:
            x["gastos"] = g
        x["fontes"] = [fonte(VEICULO, f"Página de {m['nome']} no portal da ALMG", m["url"], hj),
                       fonte(VEICULO, f"Dados Abertos: registro do deputado {i}", f"{API}/deputados/{i}?formato=json", hj)]
        extras[m["id"]] = x
    log(f"  MG: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    notas = [("A ALMG não publica o voto de cada deputado em formato aberto (só no texto das atas, no Diário do Legislativo).",
              "The ALMG does not publish each deputy's vote in an open format (only in the text of the minutes, in its official gazette).")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": True},
                  f_lista, esc_pt, esc_en, notas)
