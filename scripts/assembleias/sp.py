"""Assembleia Legislativa do Estado de São Paulo (Alesp): Dados Abertos da Alesp (www.al.sp.gov.br/dados-abertos) e a
API do portal do Processo Legislativo da Alesp (legis-api-portal-prd.al.sp.gov.br, a mesma que as páginas oficiais usam).

Lista: arquivo deputados.xml (deputados em exercício, com partido de hoje e e-mail); foto e mandatos vêm da ficha de
cada deputado na API do portal (/parlamentar-portal/detalhes/<matrícula>). Página oficial: /deputado/?matricula=<matrícula>.
Propostas: arquivos proposituras.zip (PL, PLC = PLP, PR = PRC, PDL e PEC publicados desde 15/3/2023, começo da
legislatura atual em São Paulo) e documento_autor.zip (todos os autores). O autor principal vem da pesquisa de
proposituras da API do portal (campo autorPrincipal): a ordem do arquivo de autores não diz quem é o principal.
Situação: as tramitações oficiais de cada proposta (documento_andamento.zip, baixado uma vez para começar, ~100 MB, e
depois documento_andamento_atual.zip, com os últimos 12 meses, todo dia). As regras de EVENTOS acham, na ordem do tempo,
os fatos que decidem a situação (lei publicada, veto total, retirada, rejeição, projeto prejudicado, aprovação,
arquivamento); sem nenhum deles, a proposta está em discussão.
Gastos: despesas de gabinete reembolsadas (despesas_gabinetes_<ano>.xml), somadas por ano e tipo, desde março de 2023.
Votações nominais: a Alesp lista as votações nominais na API do portal (/votacao/<ano>), mas o voto de cada deputado
só aparece em PDF (painel de votação), sem formato aberto. Por isso não entram.
"""
from __future__ import annotations

import html
import json
import re
import zipfile
import xml.etree.ElementTree as ET

import regional
from comum import PESSOAS, hoje, ler_json, log, sem_acento

from ._sse_comum import (Rede, bloco_gastos, casar_membros, com_status_en, desde, dia_rodizio, escopo, fonte, gravar,
                         legislatura, membro, nome_lei, partido_sigla, resumo_status, virou)

UF = "SP"
REPO = "https://www.al.sp.gov.br/repositorioDados"
API = "https://legis-api-portal-prd.al.sp.gov.br"
SITE = "https://www.al.sp.gov.br"
VEICULO = "Assembleia Legislativa do Estado de São Paulo (Alesp)"
CASA = {"casa": "Assembleia Legislativa do Estado de São Paulo", "casa_en": "Legislative Assembly of the State of São Paulo",
        "sigla": "Alesp", "site": SITE}
INICIO = legislatura(UF)["inicio"]  # 2023-03-15: começo da 20ª legislatura (Constituição de SP, ADCT art. 1º-A, EC nº 47/2019)
NATUREZAS = {"1": ("PL", "PL"), "2": ("PLC", "PLP"), "3": ("PR", "PRC"), "4": ("PDL", "PDL"), "5": ("PEC", "PEC")}
NOME_GASTOS = ("Verba de gabinete (despesas reembolsadas)", "Office allowance (reimbursed expenses)")

# fatos da tramitação (texto oficial sem acento, minúsculas) que decidem a situação; o primeiro que bater vale
EVENTOS = [
    ("lei", r"publicad[oa] (?:(?:a|o) )?(lei complementar|lei|decreto legislativo|resolucao|emenda constitucional) n"),
    ("veto_total", r"opondo veto total"),
    ("veto_parcial", r"opondo veto parcial"),
    ("veto_rejeitado", r"rejeitado o veto"),
    ("retirada", r"(deferid[oa]|defiro|aprovad[oa]|aprovacao d[oa]).{0,80}(pedido|requerimento) de retirada"
                 r"(?! de assinatura)(?! da emenda)(?! de pauta)(?! da pauta)(?! da ordem)"),
    ("rejeitada", r"rejeitad[oa] (o projeto|a propositura|conclusivamente a propositura)|rejeitado o pl\b"),
    ("prejudicada", r"aprovad[oa] o projeto (de lei )?n\D{0,3}\d.{0,200}prejudicad[oa] o (pl|projeto)"),  # aprovado OUTRO projeto
    ("aprovada", r"aprovad[oa] (o projeto|conclusivamente a propositura|o substitutivo|na forma do substitutivo)|"
                 r"publicado o autografo|encaminhando o incluso autografo|prazo para sancao ou veto"),
    ("prejudicada", r"prejudicad[oa] (o projeto|a propositura|o pl)\b|declara prejudicad"),
    ("junta", r"anexad[oa] ao projeto"),
    ("arquivo", r"arquivo - em processo de arquivamento|arquive-se|arquivem-se"),
]
ETAPAS_ATIVAS = {"Comissao", "Pauta", "Prontos para Ordem do Dia", "Ordem do Dia", "Distribuicao"}
# sinais de que a proposta ainda está antes da votação final (ex.: PL 143/2023 tem um "Publicado o Autógrafo" no meio do
# trabalho das comissões e depois segue na CCJR e na comissão de mérito)
REABRE = r"aprovado como parecer o voto|entrada na comissao de (?!constituicao, justica e redacao)|pauta de \d+. sessao"
TIPOS_NORMA = {"lei complementar": ("Lei Complementar", "lei.complementar"), "lei": ("Lei", "lei"),
               "decreto legislativo": ("Decreto Legislativo", "decreto.legislativo"),
               "resolucao": ("Resolução", "resolucao.alesp"), "emenda constitucional": ("Emenda Constitucional", "emenda.constitucional")}
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                     "outubro", "novembro", "dezembro"], 1)}

# ligações com o TSE conferidas à mão: {matrícula da Alesp: SQ_CANDIDATO de 2022 ou "-" (sem ligação)}
MANUAL: dict[str, str] = {
    "300669": "250001610130",  # Fabiana Bolsonaro = "FABIANA B." (Fabiana de Lima Barroso, PL); a biografia oficial confirma
    "300584": "250001611768",  # Teonilio Barba = "BARBA" (Teonílio Monteiro da Costa, PT)
}

_RE_ID = re.compile(rb"<IdDocumento>(\d+)</IdDocumento>")
_RE_CAMPO = re.compile(rb"<(\w+)>(.*?)</\1>", re.S)


def _registros(caminho, tag: bytes, docs: set[str] | None = None):
    """Lê um XML grande dentro do zip, registro por registro, sem parar em caractere inválido (o arquivo completo de
    tramitações da Alesp tem alguns). Só devolve os registros dos documentos pedidos."""
    fim = b"</" + tag + b">"
    want = {d.encode() for d in docs} if docs is not None else None
    with zipfile.ZipFile(caminho) as z, z.open(z.namelist()[0]) as f:
        resto = b""
        while True:
            bloco = f.read(16 << 20)
            if not bloco:
                break
            partes = (resto + bloco).split(fim)
            resto = partes.pop()
            for p in partes:
                if want is not None:
                    m = _RE_ID.search(p)
                    if not m or m.group(1) not in want:
                        continue
                ini = p.find(b"<" + tag + b">")
                yield {k.decode(): html.unescape(v.decode("utf-8", "replace")).strip() for k, v in _RE_CAMPO.findall(p[ini:])}


# ---------------------------------------------------------------- lista
def _membros(rede: Rede) -> tuple[list[dict], dict[str, str], dict[str, str], list[str]]:
    raiz = ET.fromstring(rede.bruto(f"{REPO}/deputados/deputados.xml", "deputados.xml", 20))
    deps = [{c.tag: (c.text or "").strip() for c in d} for d in raiz]
    deps = [d for d in deps if d.get("Situacao") == "EXE" and d.get("Matricula")]
    if len(deps) < 80:
        raise RuntimeError(f"Alesp: só {len(deps)} deputados em exercício no deputados.xml")
    pessoas, fichas = [], {}
    for d in deps:
        mat = d["Matricula"]
        try:
            fichas[mat] = rede.json(f"{API}/parlamentar-portal/detalhes/{mat}", f"deputados/{mat}.json",
                                    20 if dia_rodizio(mat) else 24 * 8)
        except Exception as e:  # sem a ficha, fica sem foto
            log(f"  SP: ficha {mat}: {e}")
            fichas[mat] = {}
        pessoas.append({"chave": mat, "nome": d["NomeParlamentar"], "nomeCivil": None, "partido": partido_sigla(d.get("Partido"))})
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids, spl = [], {}, {}
    for d, p in zip(deps, pessoas):
        mat, ficha = p["chave"], fichas.get(p["chave"]) or {}
        cand = casados.get(mat)
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[mat] = pid
        spl[d.get("IdSPL") or str(ficha.get("idAutor") or "")] = mat
        foto = (ficha.get("biografia") or {}).get("txFotoGrande")
        # a Alesp não diz se o suplente está no lugar de alguém afastado ou se ficou com a vaga de vez
        suplente = (cand or {}).get("sit") == "SUPLENTE"
        m = membro(pid, p["nome"], None, p["partido"], (cand or {}).get("genero"),
                   f"https://www3.al.sp.gov.br/legis/{foto.lstrip('/')}" if foto else None,
                   f"{SITE}/deputado/?matricula={mat}", suplente)
        m["_email"] = d.get("Email") or (ficha.get("biografia") or {}).get("txEmail")
        membros.append(m)
    return membros, ids, spl, avisos


# ---------------------------------------------------------------- propostas
def _proposituras(rede: Rede) -> dict[str, dict]:
    arq = rede.arquivo(f"{REPO}/processo_legislativo/proposituras.zip", "proposituras.zip", 20)
    out = {}
    for r in _registros(arq, b"propositura"):
        nat, dt = r.get("IdNatureza"), (r.get("DtPublicacao") or "")[:10]
        if nat in NATUREZAS and dt >= INICIO:
            out[r["IdDocumento"]] = {"nat": nat, "num": r.get("NroLegislativo"), "ano": r.get("AnoLegislativo"), "data": dt,
                                     "ementa": re.sub(r"\s+", " ", r.get("Ementa") or "").strip() or None}
    if len(out) < 1000:
        raise RuntimeError(f"Alesp: só {len(out)} proposituras no arquivo")
    return out


def _autores(rede: Rede, docs: dict) -> dict[str, list[str]]:
    arq = rede.arquivo(f"{REPO}/processo_legislativo/documento_autor.zip", "documento_autor.zip", 20)
    out: dict[str, list[str]] = {}
    for r in _registros(arq, b"DocumentoAutor", set(docs)):
        out.setdefault(r["IdDocumento"], []).append(r.get("IdAutor"))
    return out


def _principais(rede: Rede, docs: dict) -> dict[str, str]:
    """{IdDocumento: matrícula do autor principal} pela pesquisa de proposituras da API do portal (500 por página, das
    mais novas para as mais antigas; para quando uma página inteira já é conhecida)."""
    est = rede.estado("principais.json", {}) or {}
    tipos = "".join(f"&listaIdTipoProcesso={n}" for n in NATUREZAS)
    falta = [d for d in docs if d not in est]
    pagina = 0
    while falta:
        r = rede.json(f"{API}/processo?flPropositura=true&page={pagina}&size=500&sort=desc&dtInicio={INICIO}{tipos}")
        novos = 0
        for x in r.get("content") or []:
            k = str(x.get("idProcesso"))
            if k not in est:
                novos += 1
            est[k] = str(x.get("numeroAutorPrincipal") or "") if x.get("tipoAutorPrincipal") == "Parlamentar" else "-"
        pagina += 1
        if r.get("last", True) or not r.get("content") or (novos == 0 and pagina > 1):
            break
        falta = [d for d in docs if d not in est]
    rede.guardar(est, "principais.json")
    return est


def _andamentos(rede: Rede, docs: dict) -> dict[str, list]:
    """{IdDocumento: [[data, etapa, descrição], ...]} na ordem do tempo. Começa pelo arquivo completo (uma vez) e depois
    junta, todo dia, o arquivo dos últimos 12 meses: tudo o que é mais novo que o começo desse arquivo é trocado por ele."""
    est = rede.estado("andamentos.json") or {}
    if not est.get("docs"):
        log("  SP: baixando o arquivo completo de tramitações da Alesp (uma vez, ~100 MB)…")
        arq = rede.arquivo(f"{REPO}/processo_legislativo/documento_andamento.zip", "documento_andamento.zip", None, timeout=3600)
        base: dict[str, list] = {}
        for r in _registros(arq, b"DocumentoAndamento", set(docs)):
            base.setdefault(r["IdDocumento"], []).append([(r.get("Data") or "")[:10], r.get("NmEtapa") or "", r.get("Descricao") or ""])
        est = {"docs": base}
        arq.unlink(missing_ok=True)  # o arquivo é grande; o que importa já está em andamentos.json
    base = est["docs"]
    arq = rede.arquivo(f"{REPO}/processo_legislativo/documento_andamento_atual.zip", "documento_andamento_atual.zip", 20)
    novos: dict[str, list] = {}
    inicio = None
    for r in _registros(arq, b"DocumentoAndamento"):
        dt = (r.get("Data") or "")[:10]
        if dt and (inicio is None or dt < inicio):
            inicio = dt
        if r.get("IdDocumento") in docs:
            novos.setdefault(r["IdDocumento"], []).append([dt, r.get("NmEtapa") or "", r.get("Descricao") or ""])
    for d, l in novos.items():
        base[d] = [a for a in base.get(d, []) if inicio and a[0] < inicio] + l
    for d in base:
        base[d].sort(key=lambda a: a[0])  # sort estável: no mesmo dia, fica a ordem dos arquivos oficiais
    rede.guardar(est, "andamentos.json")
    return base


def _lei(desc: str) -> tuple[str | None, str | None]:
    t = re.sub(r"\s+", " ", sem_acento(desc.lower()))
    m = re.search(r"publicad[oa] (?:(?:a|o) )?(lei complementar|lei|decreto legislativo|resolucao|emenda constitucional) n\D{0,3}"
                  r"([\d.]+)\s*,?\s*de\s+(\d{1,2})\D{0,3}de\s+(\w+)\s*,?\s*de\s+(\d{4})", t)
    if not m:
        return None, None
    tipo, url_tipo = TIPOS_NORMA[m.group(1)]
    num = m.group(2).replace(".", "").strip(".")
    mes = MESES.get(m.group(4))
    nome = nome_lei(tipo, num, m.group(5))
    url = (f"{SITE}/repositorio/legislacao/{url_tipo}/{m.group(5)}/{url_tipo}-{num}-{int(m.group(3)):02d}.{mes:02d}.{m.group(5)}.html"
           if mes else None)
    return nome, url


def _situacao(ands: list) -> dict:
    """status, texto oficial, data e lei a partir das tramitações (na ordem do tempo)."""
    if not ands:
        return {"status": "outra", "situacao": None, "data": None}
    ev: dict[str, list] = {}
    for a in ands:
        t = re.sub(r"\s+", " ", sem_acento((a[2] or "").lower()))
        for k, exp in EVENTOS:
            if re.search(exp, t):
                ev[k] = a
                break
    ult = ands[-1]
    ativo_depois = lambda e: ult[1] in ETAPAS_ATIVAS and ult[0] > e[0]  # voltou a andar depois (recurso, desarquivamento)
    if "lei" in ev:
        nome, url = _lei(ev["lei"][2])
        return {"status": "lei", "situacao": ev["lei"][2], "data": ev["lei"][0], "lei": (nome, url),
                "parcial": "veto_parcial" in ev and ev["veto_parcial"][0] <= ev["lei"][0]}
    if "veto_total" in ev and not ("veto_rejeitado" in ev and ev["veto_rejeitado"][0] >= ev["veto_total"][0]):
        return {"status": "rejeitada", "situacao": ev["veto_total"][2], "data": ev["veto_total"][0], "veto": True}
    for k, st in (("retirada", "retirada"), ("rejeitada", "rejeitada"), ("prejudicada", "parada")):
        if k in ev and (k == "retirada" or not ativo_depois(ev[k])):
            return {"status": st, "situacao": ev[k][2], "data": ev[k][0]}
    if "aprovada" in ev and any(a[0] > ev["aprovada"][0] and re.search(REABRE, re.sub(r"\s+", " ", sem_acento((a[2] or "").lower())))
                                for a in ands):
        del ev["aprovada"]  # depois do "aprovado" a proposta voltou às comissões de mérito: o registro não era o final
    if "aprovada" in ev:
        return {"status": "aprovada", "situacao": ev["aprovada"][2], "data": ev["aprovada"][0]}
    if "junta" in ev and not ativo_depois(ev["junta"]):
        return {"status": "junta", "situacao": ev["junta"][2], "data": ev["junta"][0]}
    if ult[1] == "Arquivo" or ("arquivo" in ev and not ativo_depois(ev["arquivo"])):
        a = ev.get("arquivo") or ult
        return {"status": "arquivada", "situacao": a[2], "data": a[0]}
    return {"status": "andando", "situacao": ult[2], "data": ult[0]}


def _proposta(doc: str, info: dict, papel: str, sit: dict) -> dict:
    sig, tipo = NATUREZAS[info["nat"]]
    texto = re.sub(r"\s+", " ", sit.get("situacao") or "").strip() or None
    if texto and len(texto) > 300:
        texto = texto[:297].rstrip() + "…"
    p = regional.proposta(f"alesp:{doc}", f"{sig} {info['num']}/{info['ano']}", tipo, info["data"], info["ementa"], texto,
                          f"{SITE}/propositura/?id={doc}", papel=papel, status=sit["status"], data_status=sit.get("data"))
    if sit["status"] == "lei":
        nome, url = sit.get("lei") or (None, None)
        if nome:
            virou(p, nome, url)
            if sit.get("parcial"):
                p["statusTxt"] += " (com partes vetadas)"
    elif sit.get("veto"):
        com_status_en(p, "Aprovada pela Assembleia, mas vetada por inteiro pelo governador",
                      "Approved by the Assembly, but fully vetoed by the governor")
    elif sit["status"] == "aprovada":
        com_status_en(p, "Aprovada pela Assembleia; segue para a sanção ou o veto do governador",
                      "Approved by the Assembly; it goes to the governor to sign or veto")
    return p


# ---------------------------------------------------------------- gastos
def _gastos(rede: Rede, mats: set[str]) -> dict[str, list]:
    atual = int(hoje()[:4])
    out: dict[str, list] = {}
    for ano in range(int(INICIO[:4]), atual + 1):
        # o arquivo do ano de hoje muda todo mês; os anteriores quase nunca (conferidos uma vez por semana)
        b = rede.bruto(f"{REPO}/deputados/despesas_gabinetes_{ano}.xml", f"despesas_{ano}.xml", 70 if ano == atual else 24 * 7,
                       timeout=600)
        for d in ET.fromstring(b):
            mat = (d.findtext("Matricula") or "").strip()
            if mat not in mats:
                continue
            try:
                v, mes = float(d.findtext("Valor") or 0), int(d.findtext("Mes") or 0)
            except ValueError:
                continue
            tipo = re.sub(r"^[A-Z]\s*-\s*", "", (d.findtext("Tipo") or "Outros").strip())
            tipo = tipo[:1] + tipo[1:].lower() if tipo.isupper() else tipo
            if v and mes:
                out.setdefault(mat, []).append((f"{ano}-{mes:02d}", tipo, v))
    return out


# ---------------------------------------------------------------- coletar
def coletar() -> dict:
    rede = Rede("alesp", pausa=1.0)
    membros, ids, spl, avisos = _membros(rede)
    for a in avisos:
        log(f"  SP: {a}")
    docs = _proposituras(rede)
    autores = _autores(rede, docs)
    principais = _principais(rede, docs)
    ands = _andamentos(rede, docs)
    gastos = _gastos(rede, set(ids))
    hj = hoje()
    por_dep: dict[str, list] = {}
    sem_principal = 0
    for doc, info in docs.items():
        mats = [spl[a] for a in dict.fromkeys(autores.get(doc) or []) if a in spl]
        principal = principais.get(doc)
        if principal is None:
            sem_principal += 1
            continue
        if principal in ids and principal not in mats:
            mats.insert(0, principal)
        if not mats:
            continue
        sit = _situacao(ands.get(doc) or [])
        for mat in mats:
            por_dep.setdefault(mat, []).append(_proposta(doc, info, "autor" if mat == principal else "coautor", sit))
    if sem_principal:
        log(f"  SP: {sem_principal} proposituras ainda sem autor principal na API do portal (ficam para a próxima rodada)")
    f_lista = fonte(VEICULO, "Dados Abertos: deputados em exercício (deputados.xml)",
                    "https://www.al.sp.gov.br/dados-abertos/dataset/41", hj)
    f_prop = [fonte(VEICULO, "Dados Abertos: proposituras, autores e tramitações (arquivos diários)",
                    "https://www.al.sp.gov.br/dados-abertos/grupo/1", hj),
              fonte(VEICULO, "Pesquisa de proposituras no portal do Processo Legislativo (autor principal)",
                    f"{SITE}/propositura/pesquisa", hj)]
    esc_pt, esc_en = escopo(*desde(INICIO), ("PL", "PLP", "PEC", "PDL", "PRC"),
                            "Em São Paulo, a legislatura atual começou em 15 de março de 2023.",
                            "In São Paulo, the current term began on March 15, 2023.")
    extras = {}
    for m in membros:
        mat = next(k for k, v in ids.items() if v == m["id"])
        x: dict = {"links": {"oficial": m["url"], "email": m.pop("_email", None), "redes": []}}
        x["propostas"] = regional.bloco_propostas(por_dep.get(mat) or [], esc_pt, esc_en, f_prop)
        g = bloco_gastos(gastos.get(mat) or [], [
            fonte(VEICULO, f"Prestação de contas do gabinete de {m['nome']} no portal da Alesp",
                  f"{SITE}/deputado/contas/?matricula={mat}", hj),
            fonte(VEICULO, "Dados Abertos: despesas de gabinete (arquivos anuais)", "https://www.al.sp.gov.br/dados-abertos/dataset/5", hj)],
            inicio=INICIO, nome=NOME_GASTOS)
        if g:
            x["gastos"] = g
        x["fontes"] = [fonte(VEICULO, f"Página de {m['nome']} no portal da Alesp", m["url"], hj)]
        extras[m["id"]] = x
    log(f"  SP: situações {resumo_status([x['propostas']['lista'] for x in extras.values()])}; {rede.pedidos} pedidos à rede")
    notas = [("A Alesp lista as votações nominais, mas o voto de cada deputado só aparece em PDF, sem formato aberto.",
              "The Alesp lists its roll-call votes, but each deputy's vote is only published in PDF files, not in an open format.")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": True},
                  f_lista, esc_pt, esc_en, notas)
