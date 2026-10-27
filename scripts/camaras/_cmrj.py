"""Leitura das proposições da Câmara Municipal do Rio de Janeiro (usado por c3304557.py; frente capitais-b-r6, 27/10/2026).

O sistema de proposições da Câmara é um banco Lotus Notes/Domino (aplicnt.camara.rj.gov.br/APL/Legislativos/scpro.nsf), o
mesmo que as páginas de "Processo Legislativo" do portal www.camara.rio mostram. O Domino entrega as visões (listas) em JSON
(?ReadViewEntries&OutputFormat=JSON, até 1.000 linhas por pedido):
- as listas de cada tipo (Projeto de Lei, de Lei Complementar, de Emenda à Lei Orgânica, de Decreto Legislativo e de
  Resolução), da mais nova para a mais antiga: número, data de publicação, ementa (com o código do projeto) e autores (na
  ordem do cadastro; o primeiro é o autor principal);
- a visão da tramitação, organizada pelo código de cada projeto ("20250300002" = ano + tipo + número): a mesma lista de
  documentos que aparece no fim da página do projeto ("Votação => ... => Aprovado", "Ofício ... Comunicar Veto Total",
  "Resultado Final => ... => Lei 9012", "Anexado => PL Nº ...", "Arquivo"), com a data de cada um. Como os códigos de um tipo
  e ano ficam juntos, cada pedido traz a tramitação de ~60 projetos (StartKey = o primeiro código).
- as leis, decretos legislativos, resoluções e emendas à Lei Orgânica (contlei.nsf), para o link do texto da norma.
O robots.txt do servidor não existe (404 = pode ler); o certificado do servidor tem a cadeia incompleta (como o do portal),
por isso a leitura não confere o certificado, e o resultado é conferido pelo formato (JSON do Domino) e pelos números.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.parse

from . import _base as B
from . import _paginas as P

IBGE = "3304557"
SERVIDOR = "https://aplicnt.camara.rj.gov.br"
SCPRO = f"{SERVIDOR}/APL/Legislativos/scpro.nsf"
CONTLEI = f"{SERVIDOR}/APL/Legislativos/contlei.nsf"
TRAMITACAO = "ab87ae0e15e7dddd0325863200569395"  # visão da tramitação, por código do projeto
PAUSA = 1.5
# código do tipo no código do projeto -> (sigla oficial, tipo comum, visão da lista, formulário do portal)
TIPOS = {
    "01": ("PELOM", "PELO", "82669b1a0909c0c1032586320056934c", "EmendaInt"),
    "02": ("PLC", "PLP", "d305f3c25ec55a360325863200569353", "LeiCompInt"),
    "03": ("PL", "PL", "8446f2be3d9bb8730325863200569352", "LeiInt"),
    "04": ("PDL", "PDL", "7937e6fecbc74139032586320056934f", "DecretoInt"),
    "05": ("PR", "PRC", "c484633c3967be020325863200569358", "ResolucaoInt"),
}
# normas (contlei.nsf): tipo -> visão da lista (a das leis ordinárias é a completa, por número; a do portal mostra só parte)
NORMAS = {"lei": "50ad008247b8f030032579ea0073d588", "lei complementar": "a99e317a9cfec383032568620071f5d2",
          "decreto legislativo": "1103082e25d77b2203256500004ddfd5", "emenda": "c1eb7d14b66cd425032565000049f541",
          "resolucao": "803720d56d09c0e70325663200757b59"}
POR_PEDIDO = 1000
RODIZIO_DIAS = 3  # a tramitação dos anos anteriores é relida a cada 3 dias (a do ano corrente, todo dia)


def contexto():
    """O servidor manda a cadeia de certificados incompleta (o navegador completa sozinho; o Python não)."""
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _json(b: bytes) -> dict:
    t = b.decode("utf-8", "replace")
    try:
        return json.loads(t)
    except ValueError:
        # o Domino às vezes deixa caracteres de controle dentro dos textos
        return json.loads(re.sub(r"[\x00-\x1f]", " ", t))


def _valores(e: dict) -> dict:
    out = {}
    for c in e.get("entrydata") or []:
        nome = c.get("@name") or f"c{c.get('@columnnumber')}"
        for k in ("text", "number", "datetime", "textlist", "numberlist", "datetimelist"):
            if k in c:
                v = c[k]
                if isinstance(v, dict) and "0" in v:
                    v = v["0"]
                elif isinstance(v, dict) and isinstance(v.get("text") or v.get("number") or v.get("datetime"), list):
                    v = [x.get("0") for x in (v.get("text") or v.get("number") or v.get("datetime"))]
                out[nome] = v
                if c.get("@category") == "true":
                    out["_categoria"] = (c.get("@columnnumber"), v)
    return out


def _data(v) -> str | None:
    if isinstance(v, list):
        v = next((x for x in v if x), None)
    s = str(v or "")
    m = re.match(r"(\d{4})(\d{2})(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _texto(v) -> str:
    """Texto de uma coluna (as de vários valores viram uma linha só, separada por "; ")."""
    if isinstance(v, list):
        v = "; ".join(str(x).strip() for x in v if x and str(x).strip())
    return re.sub(r"\s+", " ", str(v or "")).strip()


def visao(rede: P.Rede, vid: str, inicio: int = 1, nome_db: str = SCPRO, **extra) -> dict:
    q = {"ReadViewEntries": "", "OutputFormat": "JSON", "Start": str(inicio), "Count": str(POR_PEDIDO)}
    q.update(extra)
    url = f"{nome_db}/{vid}?" + "&".join(k if v == "" else f"{k}={urllib.parse.quote(str(v))}" for k, v in q.items())
    return _json(rede.pedir(url, timeout=180))


# ---------------------------------------------------------------- listas de cada tipo
def ler_lista(rede: P.Rede, tt: str, desde_ano: int, so_primeira: bool = False) -> dict[str, dict]:
    """{código do projeto: {tipo, num, ano, data, ementa, autores, unid}} dos projetos com ano >= desde_ano (so_primeira:
    só o primeiro pedido, os 1.000 mais novos — onde aparecem os projetos novos)."""
    sig, comum, vid, _ = TIPOS[tt]
    out = {}
    inicio = 1
    while True:
        d = visao(rede, vid, inicio)
        ents = d.get("viewentry") or []
        if not ents:
            break
        velho = False
        for e in ents:
            v = _valores(e)
            num = next((x for x in v.values() if isinstance(x, str) and re.fullmatch(r"\d{1,5}/\d{4}", x)), None)
            if not num:
                continue
            n, ano = (int(x) for x in num.split("/"))
            if ano < desde_ano:
                velho = True
                continue
            em = next((x for x in v.values() if isinstance(x, str) and "=>" in x), "") or ""
            mc = re.search(r"=>\s*(\d{9,12})\b", em)
            codigo = mc.group(1) if mc else f"{ano}{tt}{n:05d}"
            ementa = re.split(r"\s*=>", em, 1)[0].strip()
            data = next((_data(x) for k, x in v.items() if isinstance(x, str) and re.fullmatch(r"\d{8}(T.*)?", x)), None)
            aut = v.get("prop_autor")
            autores = [a for a in (aut if isinstance(aut, list) else [aut]) if a and a.strip()]
            out[codigo] = {"tipo": tt, "num": n, "ano": ano, "data": data, "ementa": ementa or None,
                           "autores": [re.sub(r"\s+", " ", a).strip() for a in autores], "unid": e.get("@unid")}
        if velho or len(ents) < POR_PEDIDO or so_primeira:
            break
        inicio += len(ents)
    return out


# ---------------------------------------------------------------- tramitação (por faixas de código)
def ler_tramitacao(rede: P.Rede, ano: int, tt: str, ultimo: int) -> dict[str, list]:
    """{código: [[data, texto, autor], ...]} da tramitação dos projetos do tipo tt e ano (códigos ano+tt+00001 ...)."""
    prefixo = f"{ano}{tt}"
    out: dict[str, list] = {}
    chave = f"{prefixo}00000"
    voltas = 0
    while True:
        voltas += 1
        if voltas > 400:
            raise RuntimeError("tramitação: voltas demais (a visão deve ter mudado)")
        d = visao(rede, TRAMITACAO, 1, StartKey=chave)
        ents = d.get("viewentry") or []
        if not ents:
            break
        topo_cod: dict[str, str] = {}
        linhas: list[tuple[str, str, dict]] = []
        for e in ents:
            pos = e.get("@position") or ""
            topo = pos.split(".")[0]
            v = _valores(e)
            cat = v.get("_categoria")
            if cat and cat[0] in ("0", "2") and re.fullmatch(r"\d{9,16}", str(cat[1] or "")):
                topo_cod[topo] = str(cat[1])
                continue
            if e.get("@unid"):
                linhas.append((topo, pos, v))
        cods = [c for c in dict.fromkeys(topo_cod[t] for t, _, _ in linhas if t in topo_cod)]
        fora = [c for c in cods if not c.startswith(prefixo)]
        dentro = [c for c in cods if c.startswith(prefixo)]
        completa = len(ents) < POR_PEDIDO or bool(fora)
        if not completa and dentro:
            dentro = dentro[:-1]  # o último projeto da página pode ter vindo cortado: volta nele no próximo pedido
        for t, pos, v in linhas:
            c = topo_cod.get(t)
            if c not in dentro:
                continue
            out.setdefault(c, []).append([_data(v.get("$33")), _texto(v.get("$32")), _texto(v.get("$25")) or None,
                                          pos.count(".")])
        if completa or not dentro:
            if not completa and not dentro:
                raise RuntimeError(f"tramitação: um projeto com mais de {POR_PEDIDO} linhas ({cods[:1]})")
            break
        prox = cods[len(dentro)]  # o primeiro projeto que ficou para o próximo pedido
        if prox == chave:
            raise RuntimeError("tramitação: a página não avançou")
        chave = prox
    return out


# ---------------------------------------------------------------- normas (para o link do texto)
def ler_normas(rede: P.Rede, desde_ano: int) -> dict[str, dict[int, dict]]:
    """{tipo: {número: {ano, unid, url}}} das normas com ano >= desde_ano - 1 (o primeiro pedido de cada visão basta)."""
    out = {}
    for tipo, vid in NORMAS.items():
        d = visao(rede, vid, 1, nome_db=CONTLEI)
        m = {}
        for e in d.get("viewentry") or []:
            v = _valores(e)
            num = v.get("$8") or v.get("$12")
            ano = v.get("ComplL")
            try:
                num, ano = int(float(num)), int(float(ano))
            except (TypeError, ValueError):
                continue
            if ano >= desde_ano - 1 and num not in m:
                m[num] = {"ano": ano, "unid": e.get("@unid"), "url": f"{CONTLEI}/{vid}/{e.get('@unid')}?OpenDocument"}
        out[tipo] = m
    return out


# ---------------------------------------------------------------- tudo
def ler_propostas(rede: P.Rede, e: dict, h: str) -> bool:
    """Lê as listas, a tramitação e as normas; guarda no estado (e). True = tudo lido nesta rodada (a primeira carga e as
    rodadas seguintes cabem numa rodada só; se o tempo acabar no meio, o estado guarda o que já foi lido)."""
    desde = int(B.INICIO[:4])
    anos = list(range(desde, int(h[:4]) + 1))
    itens = e.setdefault("itens", {})
    # as listas inteiras na primeira carga e depois uma vez por semana (numa primeira carga que continua de onde parou, as
    # listas lidas na rodada anterior valem)
    completas = P.dias_desde(e.get("listas_completas"), h) >= 7
    if completas or e.get("listas") != h:
        # as listas inteiras na primeira carga e uma vez por semana (quem saiu da lista sai daqui); nos outros dias, só o
        # primeiro pedido de cada tipo, onde aparecem os projetos novos
        novos = {}
        for tt in TIPOS:
            novos.update(ler_lista(rede, tt, desde, so_primeira=not completas))
        for c, x in novos.items():
            antes = itens.get(c) or {}
            x["tram"] = antes.get("tram")
            x["tram_lida"] = antes.get("tram_lida")
            itens[c] = x
        if completas:
            for c in [c for c in itens if c not in novos]:  # saiu da lista oficial
                itens.pop(c)
            e["listas_completas"] = h
        e["listas"] = h
        P.guardar_estado(IBGE, e)
    faixas = e.setdefault("faixas", {})
    for ano in anos:
        for tt in TIPOS:
            k = f"{ano}{tt}"
            cods = [c for c, x in itens.items() if x["ano"] == ano and x["tipo"] == tt]
            if not cods:
                continue
            ult = faixas.get(k)
            precisa = (not e.get("completo") and ult is None) or (e.get("completo") and (
                ano == int(h[:4]) or P.dias_desde(ult, h) >= RODIZIO_DIAS or any(not itens[c].get("tram_lida") for c in cods)))
            if not precisa:
                continue
            tram = ler_tramitacao(rede, ano, tt, max(itens[c]["num"] for c in cods))
            for c in cods:
                itens[c]["tram"] = tram.get(c) or []
                itens[c]["tram_lida"] = h
            faixas[k] = h
            P.guardar_estado(IBGE, e)
    # as normas (para o link do texto): uma vez por semana, ou quando falta o número de uma norma citada na tramitação
    falta_norma = any(numero_norma(x.get("tram") or [], x["tipo"]) and str(numero_norma(x["tram"], x["tipo"])[1]) not in
                      ((e.get("normas") or {}).get(numero_norma(x["tram"], x["tipo"])[0]) or {}) for x in itens.values())
    if e.get("normas_lidas") != h and (falta_norma or P.dias_desde(e.get("normas_lidas"), h) >= 7):
        e["normas"] = {t: {str(n): x for n, x in m.items()} for t, m in ler_normas(rede, desde).items()}
        e["normas_lidas"] = h
    e["completo"] = True
    P.guardar_estado(IBGE, e)
    return True


NOME_NORMA = {"lei": "Lei", "lei complementar": "Lei Complementar", "decreto legislativo": "Decreto Legislativo",
              "resolucao": "Resolução", "emenda": "Emenda à Lei Orgânica"}
_VOTO_PROJETO = r"votacao\s*=>\s*(?:proposicao|projeto|substitutivo|redacao final)[^=]*=>\s*"


def situacao(x: dict, normas: dict) -> tuple[tuple, str | None, str | None, dict | None]:
    """((status, statusTxt, statusTxt_en), situação oficial, data, lei) de um projeto, pela tramitação (regras conferidas
    à mão nos projetos de 2025 e 2026; ver as notas da frente capitais-b-r6). A regra é a do documento decisivo mais novo:
    - "Resultado Final"/"Resultado Parcial => ... => Lei 9012" = virou norma (com o nome e o link do texto);
    - veto total do prefeito ("Comunicar Veto Total"): depois, "Rejeitado o Veto" = a Câmara derrubou o veto (falta
      promulgar); "Mantido o Veto" = rejeitada; sem decisão = vetada, esperando a Câmara decidir;
    - "Requerimento de retirada definitiva ... deferido/aprovado" ou ofício do autor pedindo a retirada = retirada;
    - "Anexado => PL Nº ..." = andando junto com outro projeto (até uma "desanexação");
    - "Arquivo" (sem lei, retirada, rejeição ou prejuízo antes) = arquivada (até um "desarquivamento");
    - "Votação => Proposição ... => Rejeitado" = rejeitada; "=> Prejudicado" = parada;
    - "Tramitação de Autógrafo; Envio ao Poder Executivo" ou a votação que aprova o projeto na 2ª discussão (ou na
      discussão única, ou a redação final) = aprovada pela Câmara, esperando a sanção (decretos legislativos, resoluções e
      emendas à Lei Orgânica: esperando ser promulgada);
    - o resto = ainda em discussão."""
    tram = [r for r in (x.get("tram") or []) if r[3] != 3]
    tipo_comum = TIPOS[x["tipo"]][1]
    ev: dict[str, tuple] = {}
    veto, veto_res, ultima_disc = None, None, None
    ordem = 0
    ultimo_datado = None
    for d, txt, _, _ in tram:
        ordem += 1
        t = B.norm(txt)
        k = (d or "", ordem, txt, d)
        if d and (ultimo_datado is None or (d, ordem) >= (ultimo_datado[0], ultimo_datado[1])):
            ultimo_datado = k
        if re.search(r"resultado (final|parcial)\s*=>", t):
            ev["lei"] = k
        elif re.search(r"comunicar veto total", t):
            veto, veto_res = "total", None
            ev["veto"] = k
        elif re.search(r"comunicar veto parcial", t):
            veto, veto_res = "parcial", None
            ev["veto"] = k
        elif re.search(r"votacao\s*=>\s*veto[^=]*=>\s*rejeitado o veto|comunicar rejeicao do veto", t):
            veto_res = "rejeitado"
            ev["veto_res"] = k
        elif re.search(r"votacao\s*=>\s*veto[^=]*=>\s*mantido o veto|comunicar manutencao do veto", t):
            veto_res = "mantido"
            ev["veto_res"] = k
        elif re.search(r"comunicar sancao", t):
            ev["sancao"] = k
        elif re.search(r"requerimento de retirada definitiva\s*=>.*=>\s*(deferid|aprovad)|solicita retirada|retirada de proposicao\s*=>", t):
            ev["retirada"] = k
        elif re.search(r"^anexado\s*=>|ato do presidente\s*=>.*=>\s*anexacao$", t):
            ev["anexado"] = k
        elif re.search(r"desanexa|desapense", t) and not re.search(r"arquiv", t):
            ev["desanexado"] = k
        elif re.search(r"desarquiv", t):
            ev["desarquivado"] = k
        elif re.search(r"^arquivo$|ao arquivo nos termos|remet\w* ao arquivo|remeta-se ao arquivo|arquivamento de projeto|"
                       r"desanexacao( de projeto)? e arquivamento|^despacho\s*=>.*=>\s*ao arquivo", t) and not t.startswith("emenda"):
            ev["arquivo"] = k
        elif re.search(_VOTO_PROJETO + r"rejeitad", t):
            ev["rejeitada"] = k
        elif re.search(_VOTO_PROJETO + r"prejudicad", t):
            ev["prejudicada"] = k
        elif re.search(r"tramitacao de autografo|encaminhamento para publicacao de promulgacao", t):
            ev["autografo"] = k
        elif re.search(r"^discussao (primeira|segunda|unica)", t) and "veto" not in t:
            ultima_disc = re.search(r"^discussao (primeira|segunda|unica)", t).group(1)
        if re.search(_VOTO_PROJETO + r"aprovad", t):
            if "redacao final" in t or ultima_disc in ("segunda", "unica"):
                ev["aprovada"] = k
    nn = numero_norma(x.get("tram") or [], x["tipo"])

    def saida(st, chave_txt=None, k=None, lei=None, txt=None):
        tt = (B.TXT[chave_txt][0], B.TXT[chave_txt][1]) if chave_txt else (txt, None)
        if chave_txt == "sancao" and tipo_comum in ("PDL", "PRC", "PELO"):
            tt = B.TXT["promulgar"]
        return (st, tt[0], tt[1]), (k[2] if k else None), (k[3] if k else None), lei

    if "lei" in ev and nn:
        tipo_n, num, _ = nn
        m = (normas.get(tipo_n) or {}).get(str(num)) or {}
        ano = m.get("ano") or int((ev["lei"][3] or x.get("data") or "0000")[:4])
        nome = B.nome_norma(NOME_NORMA[tipo_n], num, ano)
        parcial = veto == "parcial" and veto_res != "rejeitado"
        lei = {"nome": nome, "url": m.get("url")}
        st = ("lei", B.virou(nome, parcial), None)
        if tipo_n == "emenda":
            st = ("lei", st[1], "Became an amendment to the city's Organic Law" + (" (with some parts vetoed)" if parcial else ""))
        return st, ev["lei"][2], ev["lei"][3], lei
    if veto == "total":
        if veto_res == "rejeitado":
            return saida("aprovada", "veto_derrubado", ev.get("veto_res"))
        if veto_res == "mantido":
            return saida("rejeitada", "veto_mantido", ev.get("veto_res"))
        return saida("rejeitada", "veto_total_pendente", ev.get("veto"))
    if "sancao" in ev:
        return saida("lei", None, ev["sancao"], None, None)
    # o documento decisivo mais novo; um "Arquivo" logo depois de uma retirada, rejeição ou prejuízo é só a consequência
    cand = {k: v for k, v in ev.items() if k in ("retirada", "anexado", "arquivo", "rejeitada", "prejudicada", "autografo", "aprovada")}
    if "desanexado" in ev and "anexado" in cand and ev["desanexado"][:2] > cand["anexado"][:2]:
        cand.pop("anexado")
    if "desarquivado" in ev:
        for k in ("arquivo", "rejeitada", "prejudicada"):
            if k in cand and ev["desarquivado"][:2] > cand[k][:2]:
                cand.pop(k)
    if not cand:
        if veto == "parcial":
            return saida("lei", "veto_parcial", ev.get("veto"))
        k = ultimo_datado
        return saida("andando", None, k, None, None)
    ult = max(cand, key=lambda c: cand[c][:2])
    if ult == "arquivo":
        antes = [c for c in ("retirada", "rejeitada", "prejudicada") if c in cand]
        if antes:
            ult = max(antes, key=lambda c: cand[c][:2])
    k = cand[ult]
    if ult == "retirada":
        return saida("retirada", None, k, None, None)
    if ult == "anexado":
        return saida("junta", None, k, None, None)
    if ult == "arquivo":
        return saida("arquivada", None, k, None, None)
    if ult == "rejeitada":
        return saida("rejeitada", None, k, None, None)
    if ult == "prejudicada":
        return saida("parada", None, k, None, None)
    return saida("aprovada", "sancao", k)


def url_projeto(x: dict) -> str:
    return f"{SCPRO}/{TIPOS[x['tipo']][2]}/{x['unid']}?OpenDocument"


def sigla(x: dict) -> str:
    return f"{TIPOS[x['tipo']][0]} {x['num']}/{x['ano']}"


def numero_norma(tram: list, tt: str | None = None) -> tuple[str, int, str | None] | None:
    """("lei" | "lei complementar" | "decreto legislativo" | "resolucao" | "emenda", número, data) do "Resultado Final"
    (ou "Resultado Parcial", quando houve veto parcial) da tramitação ("Resultado Final => 20250300002 => Lei 9012",
    "... => Lei Complementar 286/2025"), ou None. O tipo da norma segue o tipo do projeto (tt), porque o texto às vezes vem
    abreviado ("Lei 281/2025" num projeto de lei complementar); erros de digitação no número ("1+879") são limpos."""
    for d, txt, _, _ in reversed(tram):
        m = re.search(r"resultado (?:final|parcial)\s*=>\s*\d*\s*=>\s*(.+?)\s*(?:n[º°o]\.?\s*)?(\d[\d.+]*)(?:\s*/\s*\d{4})?\s*$",
                      B.norm(txt))
        if m:
            t = m.group(1).strip()
            tipo = {"01": "emenda", "02": "lei complementar", "03": "lei", "04": "decreto legislativo", "05": "resolucao"}.get(tt or "")
            if not tipo:
                tipo = ("lei complementar" if "complementar" in t else "decreto legislativo" if "decreto" in t else
                        "resolucao" if "resolu" in t else "emenda" if "emenda" in t else "lei" if t.startswith("lei") else None)
            if tipo:
                return tipo, int(re.sub(r"\D", "", m.group(2))), d
    return None
