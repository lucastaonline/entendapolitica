#!/usr/bin/env python3
"""Votações nominais do Plenário (Câmara dos Deputados e Senado Federal): uma página por votação.

Os coletores (scripts/camara.py e scripts/senado.py) leem as votações e chamam estas funções para:
  - classificar cada votação pela descrição oficial (categoria, regras abaixo);
  - contar o placar (Sim, Não, Abstenção, Obstrução, Outro e total) a partir do voto de cada um;
  - ligar a orientação publicada por cada liderança (partido, federação ou bloco) aos partidos de quem votou;
  - dizer a regra para aprovar (quórum), só quando ela é clara;
  - gravar dados/votacoes/<casa>/<id>.json (uma votação por arquivo) e pôr "hora", "categoria" e "placar"
    em cada item do catálogo dados/votacoes/<casa>.json (o que a lista de votações precisa).

Categorias (a descrição oficial é comparada sem acentos; olha-se o que vem logo depois de "Aprovado(a)",
"Rejeitado(a)", "Mantido", "Votação nominal do(a)"...; a primeira regra que vale ganha):
  procedimento  pedidos sobre o andamento, e não sobre o texto: requerimentos de urgência, de adiamento, de
                retirada de pauta, de encerramento da discussão, de preferência, de quebra de interstício, de
                calendário especial, de inclusão na pauta, e recursos para levar ao Plenário um projeto que as
                comissões já tinham decidido (RICD arts. 117, 132 § 2º, 154 e 155; RISF arts. 279 e 336)
  outra         decisões que não são sobre o texto de uma proposta: o parecer sobre os pressupostos de uma medida
                provisória (relevância e urgência, CF art. 62 § 5º), casos sobre o mandato de um parlamentar
                (sustação de ação penal, medida cautelar, representação) e questões de ordem
  mudanca       mudança numa parte do texto: emendas, subemendas, destaques (parte votada em separado),
                "mantido/suprimido o texto", artigos, parágrafos e expressões (RICD arts. 118 e 161; RISF art. 312)
  principal     o texto inteiro: o projeto, a PEC (cada turno), a medida provisória, o projeto de lei de conversão,
                o substitutivo (texto novo que troca o original inteiro, RICD art. 118 § 4º) e a redação final
                (RICD art. 195 § 1º: a redação final faz parte do turno)
  O que não se encaixa fica em "outra". Para conferir: python scripts/votacoes.py --cache --revisar
  (grava .cache/votacoes/categorias.txt com cada descrição e a categoria dada).

Quórum (só quando a regra é clara; "quorum" no arquivo de detalhes):
  pec          texto principal de PEC: 3/5 dos membros, em dois turnos (CF art. 60 § 2º): 308 deputados, 49 senadores
  plp          texto principal de projeto de lei complementar: maioria absoluta (CF art. 69): 257 / 41
  urgencia155  Câmara, requerimento de urgência do art. 155 do Regimento: maioria absoluta (257)
  maioria      texto principal de projeto de lei, medida provisória ou lei de conversão: maioria dos votos, com a
               maioria absoluta presente (CF art. 47; RICD art. 183; RISF art. 288)

Orientação: o voto que o líder pede à sua bancada (RICD art. 10, IV). Para cada partido de quem votou, vale a
orientação publicada mais específica: a do próprio partido; senão a da federação de que ele faz parte (o nome da
federação traz os partidos: "Fdr PT-PCdoB-PV"); senão a do bloco, quando o partido aparece no nome abreviado do
bloco ("Bl UniPpPsd..." = União, PP, PSD e outros que o nome cortado não mostra). Governo, Maioria, Minoria,
Oposição e a Bancada Feminina aparecem na lista, mas não contam como orientação de partido.

Uso (refaz só a parte das votações, sem rodar os coletores inteiros):
  python scripts/votacoes.py                 Câmara e Senado (baixa de novo os arquivos com mais de 20 h)
  python scripts/votacoes.py --cache         usa os arquivos de .cache/ como estão (só baixa o que falta)
  python scripts/votacoes.py --camara        só a Câmara (ou --senado)
  python scripts/votacoes.py --revisar       grava também .cache/votacoes/categorias.txt (para conferir à mão)
Depois: python scripts/montar.py
"""
from __future__ import annotations

import argparse
import math
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (CACHE, DADOS, PESSOAS, carregar_simples, chave_nome, hoje, ler_json, limpa, log,  # noqa: E402
                   salvar_json, sem_acento, sem_mudar_data)

CASAS = {"camara": 513, "senado": 81}
CATEGORIAS = ("principal", "mudanca", "procedimento", "outra")
CATS_VOTO = ("Sim", "Não", "Abstenção", "Obstrução", "Outro")
OBSTRUCAO = {"Obstrução", "P-OD", "OB"}   # Senado: "P-OD" = presente, em obstrução declarada


# ---------------------------------------------------------------- texto
def _n(s) -> str:
    """Sem acento, minúsculas, espaços simples ("1º" -> "1o")."""
    s = sem_acento(str(s or "")).lower().replace("º", "o").replace("ª", "a").replace("°", "o")
    return re.sub(r"\s+", " ", s).strip()


def id_arquivo(chave: str) -> str:
    """Chave do catálogo -> nome do arquivo de detalhes ("senado-vot:7107" -> "7107"; "2236186-60" fica igual)."""
    return str(chave).split(":")[-1]


# ---------------------------------------------------------------- categoria
# o que vem antes do objeto da votação: "Votação nominal do(a)", "Aprovado(a), em 1º turno, o(a)", "Mantido o"...
_PREFIXO = re.compile(
    r"^\(?\s*(?:"
    r"votacao(?: nominal)?(?:,? (?:em|do|no) \S+ turno,?)?(?: nominal)? d[aoe]s? "
    r"|(?:aprovad|rejeitad|mantid|suprimid)[oa]s?(?:,? (?:em apreciacao preliminar|em \S+ turno|por unanimidade),?)* (?:[ao]s? )?"
    r")?")
_R_PROCEDIMENTO = re.compile(
    r"^(?:requerimentos?\b|rqs\b|solicita\b|preferencia\b|recursos?\b|inclusao\b|quebra de intersticio|adiamento\b"
    r"|retirada de pauta|encerramento d[ae] discussao)")
_R_OUTRA = re.compile(r"^(?:parecer\b|decisao d[ao] presidencia)|questao de ordem|sustacao de andamento|medida cautelar")
_R_DESTACADO = re.compile(r"\bdestacad[oa]s?\b")
_R_TEXTO_INTEIRO = re.compile(
    r"^(?:emenda (?:no?\.? ?)?\S+ ?\(substitutiv|emenda aglutinativa substitutiva|subemenda substitutiva|substitutiv)")
_R_PARTE = re.compile(
    r"^(?:emendas?\b|subemendas?\b|destaques?\b|texto\b|art\b|art\.|artigos?\b|§|paragrafos?\b|dispositivos?\b"
    r"|express(?:ao|oes)\b|capitulos?\b|parte\b|incisos?\b|alineas?\b)")
_R_PRINCIPAL = re.compile(
    r"^(?:projetos?\b|propostas? de emenda|pec\b|plp\b|pl\b|plv\b|pdl\b|prc\b|pls\b|plc\b|pds\b|prs\b|mpv\b"
    r"|medida provisoria|redacao final)")


def objeto(descricao: str | None) -> str:
    d = re.sub(r"\s*sim:\s*\d.*$", "", _n(descricao))   # a Câmara põe o placar no fim ("Sim: 252; Não: 176...")
    return _PREFIXO.sub("", d, count=1).strip()


def categoria(descricao: str | None) -> str:
    """principal | mudanca | procedimento | outra (regras no começo do arquivo)."""
    o = objeto(descricao)
    if _R_PROCEDIMENTO.match(o):
        return "procedimento"
    if _R_OUTRA.search(o):
        return "outra"
    if _R_DESTACADO.search(o):
        return "mudanca"
    if _R_TEXTO_INTEIRO.match(o):
        return "principal"
    if _R_PARTE.match(o):
        return "mudanca"
    if _R_PRINCIPAL.match(o):
        return "principal"
    return "outra"


# ---------------------------------------------------------------- quórum (só quando a regra é clara)
def maioria_absoluta(casa: str) -> int:
    return CASAS[casa] // 2 + 1                     # 257 deputados, 41 senadores


def tres_quintos(casa: str) -> int:
    return math.ceil(CASAS[casa] * 3 / 5)           # 308 deputados, 49 senadores


def regra_quorum(casa: str, cat: str, descricao: str | None, sigla: str | None) -> dict | None:
    d, s = _n(descricao), (sigla or "").upper()
    if casa == "camara" and cat == "procedimento" and re.search(r"urgencia \(art\.? ?155\b", d):
        return {"regra": "urgencia155", "minimoSim": maioria_absoluta(casa)}
    if cat != "principal" or "redacao final" in d:
        return None
    if re.search(r"proposta de emenda a constituicao|emenda constitucional|\bpec\b", d) or s.startswith("PEC "):
        return {"regra": "pec", "minimoSim": tres_quintos(casa)}
    if re.search(r"lei complementar|\bplp\b|- complementar", d) or s.startswith("PLP "):
        return {"regra": "plp", "minimoSim": maioria_absoluta(casa)}
    if re.search(r"medida provisoria|lei de conversao|\bplv\b|\bmpv\b|projeto de lei\b|\bpl\b|\bpls\b|\bplc\b", d):
        return {"regra": "maioria", "presentes": maioria_absoluta(casa)}
    return None


# ---------------------------------------------------------------- placar
def cat_voto(v: str | None) -> str:
    if v in ("Sim", "Não", "Abstenção"):
        return v
    return "Obstrução" if v in OBSTRUCAO else "Outro"


def placar(votos: list) -> dict:
    """votos = [(pessoaId, nome, partido, uf, voto)] -> {"Sim", "Não", "Abstenção", "Obstrução", "Outro", "total"}."""
    p = dict.fromkeys(CATS_VOTO, 0)
    for x in votos:
        p[cat_voto(x[4])] += 1
    p["total"] = len(votos)
    return p


def placar_da_descricao(descricao: str | None) -> dict | None:
    """O placar que a Câmara escreve no fim da descrição ("Sim: 252; Não: 176; Total: 428")."""
    m = re.search(r"sim:\s*(\d+)\s*;\s*n[aã]o:\s*(\d+)", descricao or "", re.I)
    return {"Sim": int(m.group(1)), "Não": int(m.group(2))} if m else None


# ---------------------------------------------------------------- orientações
_GERAIS = {"governo": "governo", "maioria": "maioria", "minoria": "minoria", "oposicao": "oposicao"}
_PRIORIDADE = {"partido": 0, "federacao": 1, "bloco": 2}
_COD = {"partido": "p", "federacao": "f", "bloco": "b"}
_VALORES = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "obstrucao": "Obstrução", "liberado": "Liberado",
            "livre": "Liberado"}
_ALIAS = {"PROGRESSISTAS": "PP", "PODEMOS": "PODE", "SPART": "SEMPARTIDO", "SPARTIDO": "SEMPARTIDO"}


def nome_partido(s: str | None) -> str | None:
    """Sigla como aparece nos votos; "sem partido" fica igual nas duas Casas ("S.PART.", "S/Partido")."""
    s = limpa(s)
    return "Sem partido" if s and chave_partido(s) == "SEMPARTIDO" else s


def chave_partido(s: str | None) -> str:
    k = re.sub(r"[^A-Z0-9]", "", sem_acento(str(s or "")).upper())
    return _ALIAS.get(k, k)


def tipo_lideranca(nome: str | None) -> str:
    """partido | federacao | bloco | governo | maioria | minoria | oposicao | bancada (Bancada Feminina do Senado)."""
    n = _n(nome)
    if n in _GERAIS:
        return _GERAIS[n]
    if n.startswith(("fdr ", "federacao")):
        return "federacao"
    if n.startswith(("bl ", "bloco")):
        return "bloco"
    if n.startswith(("banc", "b.fem", "b. fem")):
        return "bancada"
    return "partido"


def valor_orientacao(v: str | None) -> str | None:
    """"Sim", "Não", "Abstenção", "Obstrução" ou "Liberado" (o Senado escreve "LIVRE"); vazio = não orientou."""
    n = _n(v)
    return _VALORES.get(n, limpa(v)) if n else None


def _mesmo(a: str, b: str) -> bool:
    """Nome de liderança (às vezes cortado: "Solidaried", "Republica") x sigla do partido (chaves sem acento)."""
    return a == b or (len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)))


def _federacao(nome: str) -> list[str]:
    miolo = re.sub(r"^(?:fdr|federa[cç][aã]o)\s+", "", nome or "", flags=re.I)
    return [chave_partido(x) for x in re.split(r"[-/,\s]+", miolo) if chave_partido(x)]


def _token(t: str, k: str, conhecidos: set) -> bool:
    """Pedaço do nome do bloco ("Uni", "Pp", "Psd") x chave de partido. Uma sigla inteira só vale igual
    ("Psd" não é "PSDB"); um pedaço que não é sigla vale como começo ("Uni" = UNIÃO, "Rep" = REPUBLICANOS)."""
    t = chave_partido(t)
    return t == k or (len(t) >= 3 and t not in conhecidos and k.startswith(t))


def membros(nome: str, tipo: str, partidos: list[str], conhecidos: set, federacoes: list[list[str]]) -> list[str]:
    """Quais partidos desta votação a liderança representa (só o que dá para saber pelo nome publicado)."""
    ks = {chave_partido(p): p for p in partidos}
    if tipo == "partido":
        c = chave_partido(nome)
        return [p for k, p in ks.items() if _mesmo(c, k)]
    if tipo == "federacao":
        fed = _federacao(nome)
        return [p for k, p in ks.items() if any(_mesmo(f, k) for f in fed)]
    if tipo != "bloco":
        return []
    miolo = re.sub(r"^(?:bl|bloco)\b\.?\s*", "", nome or "", flags=re.I).rstrip(". …")
    if not miolo or " " in miolo:   # nome por extenso ("Bloco Parlamentar"): não dá para saber quem está nele
        return []
    toks = re.findall(r"[A-Z][a-z]+|[A-Z]+(?![a-z])", miolo)
    alvo = set()
    i = 0
    while i < len(toks):
        if toks[i] == "Fdr" and i + 1 < len(toks):   # "FdrPsdbCid": a federação inteira está no bloco
            for fed in federacoes:
                if any(_token(toks[i + 1], f, conhecidos) for f in fed):
                    alvo |= set(fed)
        elif toks[i] != "Fdr":
            alvo |= {k for k in ks if _token(toks[i], k, conhecidos)}
        i += 1
    return [p for k, p in ks.items() if k in alvo]


def preparar(casa: str, itens: dict) -> None:
    """Completa cada votação (no lugar): categoria, placar, quórum, orientações ligadas aos partidos e aviso.

    Cada item vem do coletor com os campos do catálogo (data, hora, propostaId, proposta, descricao, resultado,
    url) e mais: _votos [(pessoaId, nome, partido, uf, voto)], _orient [(liderança, orientação)], _ementa,
    _propUrl (página da proposta), _portal (página oficial da votação), _fontes, _oficial (placar publicado,
    para conferir), _presidente e _legenda (Senado)."""
    conhecidos = {chave_partido(x[2]) for it in itens.values() for x in it.get("_votos", []) if x[2]}
    federacoes = []
    for it in itens.values():
        for nome, _ in it.get("_orient", []):
            if tipo_lideranca(nome) == "federacao":
                f = _federacao(nome)
                if f and f not in federacoes:
                    federacoes.append(f)
    for it in itens.values():
        votos = sorted((x for x in it.get("_votos", []) if x[4]), key=lambda x: (chave_nome(x[1] or ""), x[0]))
        it["_votos"] = votos
        it["placar"] = placar(votos)
        it["categoria"] = categoria(it.get("descricao"))
        it["_quorum"] = regra_quorum(casa, it["categoria"], it.get("descricao"), it.get("proposta"))
        partidos = sorted({x[2] for x in votos if x[2]}, key=chave_nome)
        ori, vistos = [], set()
        for nome, valor in it.get("_orient", []):
            nome = limpa(nome)
            if not nome or nome in vistos:
                continue
            vistos.add(nome)
            t = tipo_lideranca(nome)
            e = {"lideranca": nome, "orientacao": valor_orientacao(valor), "tipo": t}
            if t in _PRIORIDADE:
                e["partidos"] = membros(nome, t, partidos, conhecidos, federacoes)
            ori.append(e)
        ori.sort(key=lambda e: chave_nome(e["lideranca"]))
        por = {}
        for p in partidos:
            cands = [e for e in ori if e["orientacao"] and p in e.get("partidos", [])]
            if cands:
                e = min(cands, key=lambda e: _PRIORIDADE[e["tipo"]])
                por[p] = {"orientacao": e["orientacao"], "lideranca": e["lideranca"], "tipo": e["tipo"]}
        it["_orientacoes"], it["_porPartido"] = ori, por
        it["_partidoDe"] = {x[0]: x[2] for x in votos}
        of = it.get("_oficial")
        dif = {k: v for k, v in (of or {}).items() if v is not None and it["placar"].get(k) != v}
        it["_aviso"] = ({"oficial": {k: v for k, v in of.items() if v is not None},
                         "contado": {k: it["placar"][k] for k in of if of[k] is not None}} if dif else None)


def orientacao_da_pessoa(it: dict, pessoa: str) -> list | None:
    """[orientação, "p"|"f"|"b"] do partido da pessoa NA ÉPOCA da votação (p = do partido, f = da federação,
    b = do bloco), ou None. Vai no perfil, como 3º e 4º elementos de cada par de "votos"."""
    o = it.get("_porPartido", {}).get(it.get("_partidoDe", {}).get(pessoa))
    return [o["orientacao"], _COD[o["tipo"]]] if o else None


# ---------------------------------------------------------------- arquivos
def detalhe(casa: str, chave: str, it: dict, simples: dict | None = None) -> dict:
    """O arquivo dados/votacoes/<casa>/<id>.json (contrato no README)."""
    pid = it.get("propostaId")
    prop = {"sigla": it.get("proposta"), "propostaId": pid, "url": it.get("_propUrl"), "ementa": it.get("_ementa")}
    s = (simples or {}).get(pid) if pid else None
    if isinstance(s, dict):
        if s.get("pt"):
            prop["s"] = s["pt"]
        if s.get("en"):
            prop["s_en"] = s["en"]
    elif isinstance(s, str) and s:
        prop["s"] = s
    usados = {x[4] for x in it["_votos"]}
    legenda = {k: v for k, v in (it.get("_legenda") or {}).items() if k in usados}
    return {
        "id": id_arquivo(chave), "chave": chave, "casa": casa,
        "data": it.get("data"), "hora": it.get("hora"),
        "proposta": prop,
        "descricao": it.get("descricao"), "resultado": it.get("resultado"),
        "categoria": it["categoria"], "placar": it["placar"], "quorum": it.get("_quorum"),
        "orientacoes": it["_orientacoes"], "orientacaoPartidos": it["_porPartido"],
        "votos": [list(x) for x in it["_votos"]],
        "legenda": legenda or None,
        "presidente": it.get("_presidente"),
        "aviso": it.get("_aviso"),
        "url": it.get("_portal") or it.get("url"),
        "fontes": it.get("_fontes") or [],
        "atualizado": hoje(),
    }


def salvar_detalhes(casa: str, itens: dict, simples: dict | None = None) -> tuple[int, int]:
    """Grava um arquivo por votação (só os que mudaram de verdade) e apaga os que não existem mais.
    Devolve (gravados, apagados)."""
    pasta = DADOS / "votacoes" / casa
    pasta.mkdir(parents=True, exist_ok=True)
    simples = carregar_simples() if simples is None else simples
    nomes, gravados = set(), 0
    for chave, it in itens.items():
        d = detalhe(casa, chave, it, simples)
        arq = pasta / f"{d['id']}.json"
        nomes.add(arq.name)
        if salvar_json(arq, sem_mudar_data(d, arq)):
            gravados += 1
    apagados = 0
    for arq in pasta.glob("*.json"):
        if arq.name not in nomes:
            arq.unlink()
            apagados += 1
    return gravados, apagados


def atualizar_simples(simples: dict | None = None) -> int:
    """Põe (ou tira) a explicação simples da proposta (proposta.s / proposta.s_en) nos arquivos de detalhes, a partir
    do cache dados/simples/ (como scripts/montar.py faz nos perfis). Devolve quantos arquivos mudaram."""
    simples = carregar_simples() if simples is None else simples
    n = 0
    for arq in sorted((DADOS / "votacoes").glob("*/*.json")):
        d = ler_json(arq)
        if not isinstance(d, dict) or not isinstance(d.get("proposta"), dict):
            continue
        prop, s = d["proposta"], simples.get(d["proposta"].get("propostaId") or "")
        prop.pop("s", None)
        prop.pop("s_en", None)
        if isinstance(s, dict):
            if s.get("pt"):
                prop["s"] = s["pt"]
            if s.get("en"):
                prop["s_en"] = s["en"]
        elif isinstance(s, str) and s:
            prop["s"] = s
        if salvar_json(arq, sem_mudar_data(d, arq)):
            n += 1
    return n


def revisar(casa: str, itens: dict, linhas: list[str], amostra: list[str]) -> None:
    """Para conferir a classificação: todas as descrições (com a categoria) e uma amostra sorteada."""
    c = Counter(it["categoria"] for it in itens.values())
    linhas.append(f"# {casa}: {len(itens)} votações | " + ", ".join(f"{k}: {c.get(k, 0)}" for k in CATEGORIAS))
    for chave, it in sorted(itens.items(), key=lambda kv: (kv[1]["categoria"], _n(kv[1].get("descricao")))):
        linhas.append(f"{it['categoria']:12s} | {chave} | {it.get('proposta') or '-'} | {it.get('descricao')}")
    rnd = random.Random(f"votacoes-{casa}")
    for chave in rnd.sample(sorted(itens), min(30, len(itens))):
        it = itens[chave]
        amostra.append(f"{it['categoria']:12s} | {casa} | {chave} | {it.get('proposta') or '-'} | {it.get('descricao')}")


# ---------------------------------------------------------------- refazer só as votações (a partir do cache)
def refazer_camara(idade, simples, linhas, amostra) -> None:
    import camara as C
    lista = ler_json(DADOS / "camara.json", {}) or {}
    ids = {m["id"][4:] for m in lista.get("membros", []) if str(m.get("id", "")).startswith("dep-")}
    if not ids:
        raise RuntimeError("dados/camara.json sem membros: rode antes python scripts/camara.py")
    t0 = time.time()
    itens, vv = C.ler_votacoes(ids, idade)
    log(f"Câmara: {len(itens)} votações nominais ({time.time() - t0:.0f}s)")
    if len(itens) < 100:
        raise RuntimeError(f"poucas votações ({len(itens)}): nada foi gravado")
    preparar("camara", itens)
    C.salvar_sem_ruido(DADOS.parent / C.ARQ_VOTACOES, C.catalogo_votacoes(itens))
    g, a = salvar_detalhes("camara", itens, simples)
    log(f"  dados/votacoes/camara/: {len(itens)} arquivos ({g} gravados, {a} apagados)")
    n = 0
    for dep in sorted(ids):
        arq = PESSOAS / f"dep-{dep}.json"
        p = ler_json(arq)
        if isinstance(p, dict):
            p["votacoes"] = C.bloco_votacoes(dep, itens, vv["votos"])
            n += salvar_json(arq, sem_mudar_data(p, arq))
    log(f"  perfis: {n} com a parte das votações reescrita")
    if linhas is not None:
        revisar("camara", itens, linhas, amostra)


def refazer_senado(idade, simples, linhas, amostra) -> None:
    import senado as S
    t0 = time.time()
    det, votos = S.votacoes_plenario(idade)
    log(f"Senado: {len(det)} votações abertas ({time.time() - t0:.0f}s)")
    if len(det) < 50:
        raise RuntimeError(f"poucas votações ({len(det)}): nada foi gravado")
    preparar("senado", det)
    arq_vot = DADOS / "votacoes" / "senado.json"
    salvar_json(arq_vot, S.sem_mudar_datas(S.arquivo_votacoes(det, votos), arq_vot))
    g, a = salvar_detalhes("senado", det, simples)
    log(f"  dados/votacoes/senado/: {len(det)} arquivos ({g} gravados, {a} apagados)")
    n = 0
    for arq in sorted(PESSOAS.glob("sen-*.json")):
        p = ler_json(arq)
        if isinstance(p, dict) and p.get("votacoes") is not None:
            cod = arq.stem[4:]
            p["votacoes"] = S.bloco_votacoes(votos.get(int(cod), {}), det, p.get("nomeCivil") or p.get("nome"), cod)
            n += salvar_json(arq, sem_mudar_data(p, arq))
    log(f"  perfis: {n} com a parte das votações reescrita")
    if linhas is not None:
        revisar("senado", det, linhas, amostra)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camara", action="store_true", help="só a Câmara")
    ap.add_argument("--senado", action="store_true", help="só o Senado")
    ap.add_argument("--cache", action="store_true", help="usa os arquivos de .cache/ como estão (só baixa o que falta)")
    ap.add_argument("--revisar", action="store_true", help="grava .cache/votacoes/categorias.txt para conferir")
    a = ap.parse_args()
    idade = None if a.cache else 20
    simples = carregar_simples()
    linhas, amostra = ([], []) if a.revisar else (None, None)
    if a.camara or not a.senado:
        refazer_camara(idade, simples, linhas, amostra)
    if a.senado or not a.camara:
        refazer_senado(idade, simples, linhas, amostra)
    if a.revisar:
        arq = CACHE / "votacoes" / "categorias.txt"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text("\n".join(linhas + ["", "# amostra sorteada para conferir à mão (30 por Casa)"] + amostra) + "\n",
                       encoding="utf-8")
        log(f"  {arq.relative_to(DADOS.parent)}: categorias para conferir")
    log("Pronto. Agora: python scripts/montar.py")


if __name__ == "__main__":
    main()
