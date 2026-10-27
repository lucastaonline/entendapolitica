"""Câmara Municipal do Recife (PE): as propostas dos vereadores e da prefeitura e as votações nominais do Plenário, pela API
JSON pública do SAGL (https://publico.recife.pe.leg.br/@@materias, @@normas e @@sessoes).

A lista de quem está no cargo fica a dos eleitos em 2024 (TSE): a API lista os titulares e os suplentes que assumiram, mas não
diz quais titulares estão de licença (nota da Câmara). Propostas e votos entram no perfil de quem a página da cidade mostra
(eleitos em 2024), ligado pelo nome ao candidato do TSE; os de suplentes que assumiram ficam fora.

Propostas (propostas()): as listas de matérias por tipo e ano desde 2025 (autoria com o primeiro autor), a página JSON de cada
matéria de vereador ou da prefeitura (a tramitação: de onde sai a situação, com regras próprias da Câmara, em situacao_recife)
e as normas jurídicas desde 2025 (@@normas/<id> diz de qual matéria a norma veio: "virou lei"). A primeira carga (umas 1.300
páginas) pode levar mais de uma rodada; até terminar, ficam publicadas as propostas de antes (nada pela metade) e o resumo
marca a Câmara como em andamento. Depois, cada rodada lê as listas do ano e só as matérias que podem ter mudado (em
tramitação: a cada 3 dias se andou no último mês, senão a cada 14; encerradas: a cada 60 dias).

Gastos: a Câmara publica a verba indenizatória (CEAP) num sistema de consulta que pede o teste "não sou robô" (reCAPTCHA) a
cada pesquisa (ceap.recife.pe.leg.br): não entram (nota da Câmara).

Votações: as reuniões plenárias desde 1º/1/2025 (ordinárias e extraordinárias, uma lista por tipo e ano) e as votações de
cada uma ("@id_votacao": o que foi votado, o turno, a apuração e os vereadores de cada voto). Entram as nominais de projetos,
emendas, substitutivos e vetos que decidiram alguma coisa (aprovado, rejeitado, veto mantido ou derrubado); requerimentos,
indicações, moções e votações sem a lista de votos ficam fora. O que já foi lido fica em .cache/camaras/2611606/votos.json
(a primeira leitura, umas 200 reuniões, pode levar mais de uma rodada; até terminar, ficam publicadas as votações de antes,
nada pela metade); depois, só as reuniões novas e as dos últimos 7 dias.
"""
import datetime as dt
import json
import re
import time

import regional
from comum import baixar, fonte, hoje, ler_json, log, salvar_json

from . import _base as B
from . import _capitais_c as C
from ._sapl import data_en, data_pt

IBGE, UF = "2611606", "PE"
API = "https://publico.recife.pe.leg.br"
SITE = "https://www.recife.pe.leg.br"
CASA = {"casa": "Câmara Municipal do Recife", "casa_en": "Recife City Council", "sigla": "CMR", "site": SITE,
        "sistema": "SAGL (API JSON)", "api": f"{API}/@@sessoes"}
TIPOS_SESSAO = (1, 2, 9)  # Ordinária, Extraordinária, Convocação Extraordinária
ESTADO = B.PASTA_CACHE / IBGE / "votos.json"
PREFIXO = f"cm{IBGE}"  # ids das propostas no site: cm2611606:<código da matéria no SAGL>, como nas outras Câmaras
ESCOPO_VOTOS = ("Votações nominais (em que o voto de cada vereador fica registrado) de projetos, emendas, substitutivos e vetos "
                "no Plenário desde 1º/1/2025, segundo o sistema oficial da Câmara (SAGL). Votações de requerimentos, "
                "indicações e moções, e as que não têm a lista de votos, não entram.",
                "Roll-call votes (where each councilor's vote is recorded) on bills, amendments, substitute bills and vetoes in "
                "the full City Council since January 1, 2025, according to the City Council's official system (SAGL). Votes on "
                "requests, recommendations and motions, and votes without the list of how each member voted, are not included.")
_PROJ = re.compile(r"^(projeto|proposta de emenda|emenda|subemenda|substitutivo|veto|redacao final)")
_DECIDIU = re.compile(r"aprovad|rejeitad|veto mantido|veto derrubado|mantid|derrubad")
VOTOS = (("favoravel", "Sim"), ("contrario", "Não"), ("abstencao", "Abstenção"), ("ausente", "NCom"), ("presidencia", "PS"))
_n = 0


def _json(url: str, pausa: float = 1.0):
    global _n
    B.esperar_vez(url, pausa)
    try:
        b = baixar(url, tentativas=3, timeout=120, headers={"Accept": "application/json"})
    finally:
        B.pedido_feito(url)
    _n += 1
    return json.loads(b.decode("utf-8"))


def _menos(h: str, dias: int) -> str:
    return (dt.date.fromisoformat(h) - dt.timedelta(days=dias)).isoformat()


def _itens(d: dict) -> list[dict]:
    """As votações nominais de uma reunião que têm a lista de votos (as outras não servem para o perfil)."""
    out = []
    for it in d.get("items") or []:
        if B.norm(it.get("tipo_votacao")) != "nominal":
            continue
        for ap in it.get("apuracao") or []:
            grupos = (ap.get("votos") or [{}])[0] or {}
            votos = [[str(v.get("id")), v.get("title"), v.get("description"), ((v.get("partido") or [{}])[0] or {}).get("token"), codigo]
                     for campo, codigo in VOTOS for v in grupos.get(campo) or []]
            if votos:
                out.append({"materia": str(it.get("id")), "titulo": it.get("title"), "ementa": it.get("description"),
                            "turno": it.get("turno"), "resultado": ap.get("resultado"), "sim": ap.get("favoravel") or 0,
                            "nao": ap.get("contrario") or 0, "abst": ap.get("abstencao") or 0, "votos": votos})
    return out


def votacoes(tse: "B.Tse", h: str):
    """(catálogo, {id no site: [[chave, voto], ...]}, escopo, fonte) ou None se a leitura não terminou nesta rodada."""
    from ._sapl import _prazo
    est = ler_json(ESTADO, {}) or {}
    ses, det, listas = est.setdefault("sessoes", {}), est.setdefault("det", {}), est.setdefault("listas", {})
    prazo = _prazo()
    ano_h = int(h[:4])
    try:
        for ano in range(int(B.INICIO[:4]), ano_h + 1):
            for t in TIPOS_SESSAO:
                k = f"{t}-{ano}"
                if ano < ano_h and (listas.get(k) or "") >= _menos(h, 30):
                    continue  # ano passado: a lista é lida de novo uma vez por mês
                for s in _json(f"{API}/@@sessoes/tipo/{t}/ano/{ano}").get("items") or []:
                    if B.INICIO <= (s.get("date") or "") <= h:
                        ses[str(s["id"])] = [s["date"], s.get("title")]
                listas[k] = h
        recentes = _menos(h, 7)  # as reuniões dos últimos dias podem ganhar votações depois
        faltam = sorted((i for i, (d, _) in ses.items() if i not in det or d >= recentes), key=int)
        for k, i in enumerate(faltam):
            if prazo and time.time() > prazo - 120:
                raise TimeoutError("fim do tempo da rodada")
            det[i] = _itens(_json(f"{API}/@@sessoes/id/{i}/votacao"))
            if k % 20 == 19:
                salvar_json(ESTADO, est)
    except (TimeoutError, RuntimeError, OSError, ValueError) as erro:
        salvar_json(ESTADO, est)
        log(f"  CMR: votações pela metade ({type(erro).__name__}: {str(erro)[:120]}; {_n} pedidos): continuam na próxima rodada")
        return None
    salvar_json(ESTADO, est)
    validos = tse.ids_eleitos()
    pessoa: dict[str, str | None] = {}
    cat, por = {}, {}
    for sid, itens in det.items():
        data = (ses.get(sid) or [None])[0]
        if not data or data < B.INICIO:
            continue
        vistos: dict[str, int] = {}
        for it in itens:
            if not _PROJ.match(B.norm(it.get("titulo"))) or not _DECIDIU.search(B.norm(it.get("resultado"))):
                continue
            n = vistos[it["materia"]] = vistos.get(it["materia"], 0) + 1
            chave = f"cmr-vot:{sid}-{it['materia']}" + (f"-{n}" if n > 1 else "")
            oficial = {"Sim": it["sim"], "Não": it["nao"], "Abstenção": it["abst"]}
            brutos = []
            for vid, titulo, descr, partido, voto in it["votos"]:
                if vid not in pessoa:
                    pid, cand = tse.casar(f"sagl-{vid}", [titulo, descr], B.partido(partido))
                    pessoa[vid] = pid if cand and pid in validos else None
                brutos.append((pessoa[vid] or f"?{vid}", voto))
            votos = B.votos_unicos(brutos, oficial)
            contado = {k: sum(1 for v in votos.values() if v == k) for k in oficial}
            ementa = re.sub(r"\s+", " ", it.get("ementa") or "").strip()
            desc = f"{ementa} (Turno: {it['turno']})" if ementa and it.get("turno") else ementa or None
            x = {"data": data, "proposta": re.sub(r"\s+", " ", it.get("titulo") or "").strip() or None,
                 "propostaId": f"{PREFIXO}:{it['materia']}", "descricao": desc, "resultado": it.get("resultado"),
                 "placar": dict(oficial, total=sum(oficial.values())),
                 "url": f"{API}/consultas/materia/materia_mostrar_proc?cod_materia={it['materia']}"}
            if contado != oficial:
                x["aviso"] = {"oficial": oficial, "contado": contado}
            cat[chave] = x
            for pid, vt in votos.items():
                if not str(pid).startswith("?"):
                    por.setdefault(pid, []).append([chave, vt])
    for lst in por.values():
        lst.sort(key=lambda kv: (cat[kv[0]]["data"], kv[0]), reverse=True)
    f = fonte(CASA["casa"], "SAGL: reuniões plenárias e votações nominais (API pública)", f"{API}/@@sessoes", h)
    return cat, por, ESCOPO_VOTOS, f


# ---------------------------------------------------------------- propostas (SAGL: @@materias e @@normas)
ESTADO_PROP = B.PASTA_CACHE / IBGE / "propostas.json"
# tipo de matéria no SAGL -> (sigla oficial, tipo comum do site). Siglas como as páginas oficiais das normas mostram a
# "Matéria Originária" (PLO 7/2025, PLE 47/2025, PDL 30/2025, PRES 16/2025); sem sigla conferida, vale o nome oficial
# ("Projeto de Emenda à Lei Orgânica nº 3/2025"). Requerimentos, vetos, emendas e pareceres não entram.
TIPOS_MAT = {10: ("PLO", "PL"), 11: ("PLE", "PL"), 28: (None, "PLP"), 14: (None, "PELO"), 23: (None, "PELO"),
             6: ("PDL", "PDL"), 2: ("PRES", "PRC")}
TIPOS_NORMA = {1: "Lei Ordinária", 2: "Lei Complementar", 3: "Resolução", 4: "Decreto Legislativo"}
PAG_MATERIA = API + "/consultas/materia/materia_mostrar_proc?cod_materia={}"
PAG_NORMA = API + "/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma={}"
PAG_PARL = API + "/consultas/parlamentar/parlamentar_mostrar_proc?cod_parlamentar={}"
PAUSA_PROP = 2.0  # entre pedidos das propostas (o servidor respondeu 503 depois de ~700 pedidos com 1 s)
LIMITE_DIA = 150  # páginas de matéria por rodada depois da primeira carga (a primeira vai até o fim do tempo da rodada)
_NUM = re.compile(r"n[º°o]\.?\s*(\d+)\s*/\s*(\d{4})", re.I)
# a lei citada no andamento: "LEI Nº 19.471/2025, PROMULGADA EM ...", "DECRETO LEGISLATIVO Nº 1.205/2025"
_LEI_TXT = re.compile(r"\b(lei complementar|lei|decreto legislativo|resolucao)\s+(?:municipal\s+)?n[ºo°]?\.?\s*([\d.]+)\s*/\s*(\d{4})")
_ESPECIE = {"lei": ("Lei", 1), "lei complementar": ("Lei Complementar", 2), "resolucao": ("Resolução", 3),
            "decreto legislativo": ("Decreto Legislativo", 4)}
# passos do andamento que não dizem nada sobre o resultado (mudança de lugar, documento anexado...): pulados na leitura
_NEUTRO = re.compile(r"^(documento anexado|enviado (por solicitacao|ao protocolo|ao gabinete|ao arquivo)|distribuido internamente|"
                     r"pendencia resolvida|arquivo geral|aguardando endereco eletronico|resposta de requerimento)")
# situações oficiais de quem ainda está em discussão (recebida, prazo de emendas, parecer, pauta, Ordem do Dia, vistas...)
_ANDANDO = re.compile(r"^(recebimento no protocolo|apresentado em plenario|distribuido para as comissoes|aguardando|"
                      r"parecer de comissao|incluido n|adiada discussao|pedido de vistas|emenda apresentada|substitutivo apresentado|"
                      r"dispensado prazo|em fase de votacao|extra pauta|reuniao extraordinaria|convocacao extraordinaria|"
                      r"prolongamento da ordem do dia)")


def _classe(titulo: str | None, desc: str | None, tipo: str) -> tuple[str, str | None]:
    """(status, chave de _base.TXT ou None) de um passo do andamento, pelas situações oficiais do SAGL da Câmara (lista
    "Status" da pesquisa de matérias: "Promulgado / Arquivado", "Aceito veto total do Prefeito", "Proposição aprovada"...).
    "neutro" = passo que não diz nada sobre o resultado."""
    t, d = B.norm(titulo), B.norm(desc)
    sancao = "sancao" if tipo in ("PL", "PLP") else "promulgar"
    if _NEUTRO.match(t):
        return "neutro", None
    if re.match(r"(promulgad|sancionad)", t):
        return "lei", "veto_parcial" if "parcial" in t else None
    if re.search(r"aceito veto parcial|^veto parcial", t):
        return "lei", "veto_parcial"
    if re.search(r"aceito veto total", t):
        return "rejeitada", "veto_mantido"
    if re.match(r"veto total", t):
        return "rejeitada", "veto_total_pendente"
    if re.search(r"rejeitad|aprovado pela rejeicao", t):
        return "rejeitada", None
    if re.search(r"retirado pelo autor", t):
        return "retirada", None
    if re.match(r"arquivad", t):
        return "arquivada", None
    if re.search(r"aguardando publicacao|enviado ao executivo|^redacao final", t):
        return "aprovada", sancao
    if re.match(r"proposicao aprovada", t):
        if re.search(r"\bparecer(es)?\b.{0,90}\bpela rejeicao", d):
            return "rejeitada", None  # aprovado o parecer pela rejeição: a matéria foi rejeitada
        if re.search(r"\b(1a|primeira) discussao|\b1o turno|\bprimeiro turno", d):
            return "andando", None  # aprovada só em 1ª discussão: ainda falta a 2ª
        return "aprovada", sancao
    if _ANDANDO.match(t):
        return "andando", None
    st, txt, _ = B.situacao(titulo, None, None, None, tipo)
    return st, None


def _lei_no_texto(trams: list) -> tuple[str, str, str] | None:
    """(espécie, número, ano) da norma citada no andamento de quem virou norma (o passo mais novo que cita uma)."""
    for _, titulo, desc in trams:
        if re.match(r"(promulgad|sancionad|aceito veto parcial|veto parcial)", B.norm(titulo)):
            m = _LEI_TXT.search(B.norm(desc))
            if m:
                return m.group(1), m.group(2).replace(".", ""), m.group(3)
    return None


def situacao_recife(tipo: str, det: dict, normas_mat: list, por_numero: dict) -> tuple:
    """(status, statusTxt, statusTxt_en, situação oficial, dataStatus, lei) de uma matéria, a partir do andamento (do mais
    novo para o mais antigo) e das normas ligadas a ela. Regras próprias da Câmara do Recife (conferidas à mão):
    - norma ligada à matéria (@@normas/<id> -> materia) ou andamento "Promulgado"/"Sancionado"/"Veto parcial" = virou norma
      (com partes vetadas, se houve veto parcial); o nome vem da norma ou do texto do andamento ("LEI Nº 19.471/2025");
    - "Aceito veto total do Prefeito" = o prefeito vetou e a Câmara manteve o veto (rejeitada); "Veto total da proposição"
      sem decisão da Câmara depois = rejeitada, esperando a Câmara decidir sobre o veto;
    - "Proposição rejeitada / arquivada", "Aprovado pela rejeição / arquivado" e "Proposição aprovada" quando o aprovado foi o
      parecer pela rejeição ("APROVADO PARECER ... PELA REJEIÇÃO") = rejeitada; "Retirado pelo autor" = retirada;
    - "Aguardando publicação" (redação final enviada ao prefeito), "Redação Final" e "Proposição aprovada" (menos em 1ª
      discussão) = aprovada, esperando a sanção (ou a promulgação, nos decretos legislativos, resoluções e emendas à Lei Orgânica);
    - "Arquivado" = arquivada, a não ser que antes disso a matéria tenha virado norma, sido rejeitada ou retirada;
    - passos que só mudam a matéria de lugar ou anexam documentos são pulados; o resto (prazo de emendas, pareceres, pauta,
      vistas, adiamento) = ainda em discussão."""
    trams = det.get("tr") or []
    oficial = trams[0][1] if trams else None
    parcial = any(re.search(r"veto parcial|sancionado parcialmente", B.norm(t)) for _, t, _ in trams)
    if normas_mat:
        # a mesma lei cadastrada duas vezes (como ordinária e como complementar, ou com outro número): vale a que o andamento
        # cita; senão, a da espécie do projeto e, entre elas, a de número maior (a numeração das leis do Recife é uma só)
        citada = _lei_no_texto(trams)
        cands = [n for n in normas_mat if citada and n["n"] == citada[1] and n["a"] == citada[2]] or normas_mat
        pref = {"PL": 1, "PLP": 2, "PRC": 3, "PDL": 4}.get(tipo)
        n = sorted(cands, key=lambda x: (x["t"] != pref, -int(x["n"] or 0) if str(x["n"] or "").isdigit() else 0))[0]
        nome = B.nome_norma(TIPOS_NORMA[n["t"]], n["n"], n["a"])
        return ("lei", B.virou(nome, parcial), None, oficial, n["data"] or (trams[0][0][:10] if trams else None),
                {"nome": nome, "url": PAG_NORMA.format(n["id"])})
    passos = [(d, t, x, *_classe(t, x, tipo)) for d, t, x in trams]
    lei = next((p for p in passos if p[3] == "lei"), None)
    if lei:
        citada = _lei_no_texto(trams)
        nome, url = None, None
        if citada:
            esp, num, ano = citada
            nome_esp, t_norma = _ESPECIE[esp]
            achada = por_numero.get((t_norma, num, ano)) or (por_numero.get((2, num, ano)) if t_norma == 1 else None)
            nome = B.nome_norma(TIPOS_NORMA[achada["t"]] if achada else nome_esp, num, ano)
            url = PAG_NORMA.format(achada["id"]) if achada else None
        txt = B.virou(nome, parcial) if nome else (B.TXT["veto_parcial"][0] if parcial else None)
        txt_en = None if nome else (B.TXT["veto_parcial"][1] if parcial else None)
        return "lei", txt, txt_en, oficial, lei[0][:10], ({"nome": nome, "url": url} if nome else None)
    aceito = next((p for p in passos if p[4] == "veto_mantido"), None)
    if aceito:
        return "rejeitada", *B.TXT["veto_mantido"], oficial, aceito[0][:10], None
    vt = next((p for p in passos if p[4] == "veto_total_pendente"), None)
    if vt:
        return "rejeitada", *B.TXT["veto_total_pendente"], oficial, vt[0][:10], None
    escolhido = None
    for p in passos:
        if p[3] == "neutro":
            continue
        if escolhido is None:
            escolhido = p
            if p[3] != "arquivada":
                break
            continue
        if p[3] in ("rejeitada", "retirada"):  # arquivada depois de rejeitada ou retirada: vale o que aconteceu
            escolhido = p
        if p[3] != "arquivada":
            break
    if escolhido is None:  # sem andamento, ou só passos que não dizem nada
        if not trams:
            return "andando", *B.TXT["sem_tramitacao"], None, None, None
        escolhido = (*passos[0][:3], "andando", None)
    st, chave = escolhido[3], escolhido[4]
    txt, txt_en = (B.TXT[chave][0], B.TXT[chave][1]) if chave else (None, None)
    if st == "outra" and not txt:
        txt = f"Situação na Câmara: {escolhido[1]}"
    return st, txt, txt_en, oficial, escolhido[0][:10] or None, None


def _compacta(d: dict) -> dict:
    """O que se guarda da página JSON de uma matéria: se ainda tramita e o andamento (data, situação, texto), do mais novo
    para o mais antigo."""
    trams = [[(p.get("date") or "")[:19], re.sub(r"\s+", " ", p.get("title") or "").strip(), C.texto(p.get("description"))[:400]]
             for p in d.get("processing") or []]
    trams.sort(key=lambda x: x[0], reverse=True)
    return {"em": d.get("inProgress"), "tr": trams}


def _vencida(m: dict, h: str) -> bool:
    d = m.get("det") or {}
    if not d.get("lido"):
        return True
    if d.get("em") is False:
        return d["lido"] < C.menos(h, 60)
    ult = ((d.get("tr") or [[""]])[0][0] or "")[:10]
    return d["lido"] < C.menos(h, 3 if ult >= C.menos(h, 30) else 14)


def _interessa(m: dict) -> bool:
    """Matéria que vai para algum perfil: de vereador ou da prefeitura (as da Comissão Executiva e das comissões, não)."""
    return any(a[2] in ("Parlamentar", "Poder Executivo") for a in m.get("aut") or [])


def _lista_inteira(nome: str, novos: int, guardados: int) -> None:
    """Uma lista oficial que volta vazia ou com bem menos itens do que a última leitura (resposta de erro, sistema fora do
    ar) não apaga o que foi lido: a rodada para e tenta de novo na próxima."""
    if guardados >= 10 and novos < guardados / 2:
        raise RuntimeError(f"a lista {nome} veio com {novos} itens (antes: {guardados})")


FALHAS_SEGUIDAS = 5  # páginas seguidas com erro = o servidor está fora do ar: a rodada para (senão, pula só a página)


def propostas(h: str) -> dict:
    """Lê (ou continua lendo) as matérias e as normas desde 2025 e devolve o estado: {"mats": {...}, "normas": {...},
    "completo": bool, "faltam": n}. A primeira carga pode levar mais de uma rodada (o que foi lido fica guardado).
    Uma página que dá erro fica marcada ("erro": data) e é tentada de novo na rodada seguinte, sem travar as outras."""
    est = ler_json(ESTADO_PROP, {}) or {}
    listas, mats = est.setdefault("listas", {}), est.setdefault("mats", {})
    normas, nlistas = est.setdefault("normas", {}), est.setdefault("nlistas", {})
    ano_h = int(h[:4])
    primeira = not est.get("completo_em")
    n0 = _n
    try:
        # 1. listas de matérias por tipo e ano (a do ano todo dia; as dos anos passados uma vez por semana)
        for ano in range(int(B.INICIO[:4]), ano_h + 1):
            for t in TIPOS_MAT:
                k = f"{t}-{ano}"
                if ano < ano_h and (listas.get(k) or "") >= C.menos(h, 7):
                    continue
                if listas.get(k) == h:
                    continue
                if C.sem_tempo():
                    raise TimeoutError("fim do tempo da rodada")
                ids = set()
                for x in _json(f"{API}/@@materias?ano={ano}&tipo={t}", PAUSA_PROP).get("items") or []:
                    mid = str(x.get("id"))
                    num = _NUM.search(x.get("title") or "")
                    novo = {"t": t, "lk": k, "titulo": re.sub(r"\s+", " ", x.get("title") or "").strip(),
                            "data": (x.get("date") or "")[:10] or None,
                            "ementa": re.sub(r"\s+", " ", x.get("description") or "").strip() or None,
                            "n": num.group(1) if num else None, "a": num.group(2) if num else str(ano),
                            "aut": [[re.sub(r"\s+", " ", a.get("title") or "").strip(), bool(a.get("firstAuthor")),
                                     (a.get("description") or "").strip()] for a in x.get("authorship") or []]}
                    if mid in mats:
                        mats[mid].update(novo)
                    else:
                        mats[mid] = novo
                    ids.add(mid)
                _lista_inteira(f"de matérias {k}", len(ids), sum(1 for m in mats.values() if m.get("lk") == k))
                for mid in [i for i, m in mats.items() if m.get("lk") == k and i not in ids]:
                    mats.pop(mid)  # saiu da lista oficial (apagada ou mudou de tipo)
                listas[k] = h
        # 2. normas desde 2025 (a lista do ano todo dia; a página de cada norma nova uma vez, e de novo a cada 90 dias)
        for ano in range(int(B.INICIO[:4]), ano_h + 1):
            for t in TIPOS_NORMA:
                k = f"{t}-{ano}"
                if (ano < ano_h and (nlistas.get(k) or "") >= C.menos(h, 7)) or nlistas.get(k) == h:
                    continue
                if C.sem_tempo():
                    raise TimeoutError("fim do tempo da rodada")
                ids = set()
                novas = {}
                for x in _json(f"{API}/@@normas?ano={ano}&tipo={t}", PAUSA_PROP).get("items") or []:
                    num = _NUM.search(x.get("title") or "")
                    novas[str(x.get("id"))] = {"t": t, "lk": k, "n": num.group(1) if num else None,
                                               "a": num.group(2) if num else str(ano), "titulo": x.get("title")}
                _lista_inteira(f"de normas {k}", len(novas), sum(1 for x in normas.values() if x.get("lk") == k))
                for nid, nv in novas.items():
                    normas.setdefault(nid, {}).update(nv)
                    ids.add(nid)
                for nid in [i for i, x in normas.items() if x.get("lk") == k and i not in ids]:
                    normas.pop(nid)
                nlistas[k] = h
        falhas = 0
        for nid, x in sorted(normas.items(), key=lambda kv: int(kv[0])):
            if (x.get("lido") and x["lido"] >= C.menos(h, 90)) or x.get("erro") == h:
                continue
            if C.sem_tempo():
                raise TimeoutError("fim do tempo da rodada")
            try:
                d = _json(f"{API}/@@normas/{nid}", PAUSA_PROP)
            except (RuntimeError, ValueError, OSError) as erro:
                x["erro"] = h
                falhas += 1
                log(f"  CMR: norma {nid}: {type(erro).__name__}: {str(erro)[:120]} (tenta de novo na próxima rodada)")
                if falhas >= FALHAS_SEGUIDAS:
                    raise
                continue
            falhas = 0
            x.update({"data": C.data_iso(d.get("data_norma")), "pub": C.data_iso(d.get("data_publicacao")),
                      "mats": [str(m.get("id")) for m in d.get("materia") or [] if m.get("id")], "lido": h})
            x.pop("erro", None)
            if (_n - n0) % 25 == 0:
                salvar_json(ESTADO_PROP, est)
        # 3. a página JSON de cada matéria que vai para algum perfil e pode ter mudado
        faltam = sorted((mid for mid, m in mats.items() if _interessa(m) and _vencida(m, h) and m.get("erro") != h),
                        key=lambda mid: (bool((mats[mid].get("det") or {}).get("lido")), (mats[mid].get("det") or {}).get("lido") or "", int(mid)))
        feitas = 0
        for mid in faltam:
            if C.sem_tempo() or (not primeira and feitas >= LIMITE_DIA):
                break
            try:
                d = _json(f"{API}/@@materias/{mid}", PAUSA_PROP)
            except (RuntimeError, ValueError, OSError) as erro:
                mats[mid]["erro"] = h
                falhas += 1
                log(f"  CMR: matéria {mid}: {type(erro).__name__}: {str(erro)[:120]} (tenta de novo na próxima rodada)")
                if falhas >= FALHAS_SEGUIDAS:
                    raise
                continue
            falhas = 0
            mats[mid]["det"] = dict(_compacta(d), lido=h)
            mats[mid].pop("erro", None)
            feitas += 1
            if feitas % 25 == 0:
                salvar_json(ESTADO_PROP, est)
    except (TimeoutError, RuntimeError, OSError, ValueError) as erro:
        log(f"  CMR: propostas: {type(erro).__name__}: {str(erro)[:150]} ({_n - n0} pedidos); continua na próxima rodada")
    # uma página que dá erro não segura a primeira carga (fica fora do perfil até ser lida)
    sem_det = sum(1 for m in mats.values() if _interessa(m) and not (m.get("det") or {}).get("lido") and not m.get("erro"))
    sem_norma = sum(1 for x in normas.values() if not x.get("lido") and not x.get("erro"))
    listas_ok = all(listas.get(f"{t}-{a}") for a in range(int(B.INICIO[:4]), ano_h + 1) for t in TIPOS_MAT)
    nlistas_ok = all(nlistas.get(f"{t}-{a}") for a in range(int(B.INICIO[:4]), ano_h + 1) for t in TIPOS_NORMA)
    completo = listas_ok and nlistas_ok and not sem_det and not sem_norma
    if completo and primeira:
        est["completo_em"] = h
    salvar_json(ESTADO_PROP, est)
    est["_completo"] = completo or not primeira  # depois da primeira carga, o que já foi lido vale (a rodada só atualiza)
    est["_faltam"] = sem_det + sem_norma
    est["_total"] = sum(1 for m in mats.values() if _interessa(m)) + len(normas)
    est["_pedidos"] = _n - n0
    return est


def _legislatura(h: str) -> list[dict]:
    """Vereadores da legislatura atual no SAGL (titulares e suplentes que assumiram): id, nome, nome completo e partido,
    guardados por 7 dias. Liga o nome do autor de cada matéria ao vereador (o mesmo id dos votos)."""
    arq = B.PASTA_CACHE / IBGE / "http" / "legislatura.json"
    if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < 24 * 7:
        return json.loads(arq.read_text(encoding="utf-8"))
    try:
        leg = None
        try:
            for x in _json(f"{API}/@@legislaturas").get("items") or []:
                if (x.get("start") or "") <= h <= (x.get("end") or "9999"):
                    leg = str(x.get("id"))
        except (RuntimeError, ValueError, OSError):
            leg = None
        d = _json(f"{API}/@@legislaturas/{leg or 19}")
        itens = [{"id": str(x.get("id")), "nome": (x.get("title") or "").strip(), "civil": (x.get("description") or "").strip(),
                  "partido": ((x.get("partido") or [{}])[0] or {}).get("token")} for x in d.get("items") or []]
        if len(itens) < 30:
            raise RuntimeError(f"a legislatura do SAGL veio com {len(itens)} vereadores")
    except (RuntimeError, ValueError, OSError) as erro:
        if arq.exists():  # vale a lista guardada da semana passada (a legislatura muda pouco)
            log(f"  CMR: legislatura: {type(erro).__name__}: {str(erro)[:120]}; vale a lista guardada")
            return json.loads(arq.read_text(encoding="utf-8"))
        raise
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    return itens


def blocos_propostas(est: dict, tse: "B.Tse", h: str, pref: dict) -> tuple[dict, list | None, dict, dict]:
    """({id do vereador: [propostas]}, [propostas da prefeitura] ou None, {id do vereador: id no SAGL}, {nome de vereador que
    não está entre os eleitos em 2024 (suplente que assumiu): quantas matérias})."""
    mats, normas = est.get("mats") or {}, est.get("normas") or {}
    por_mat: dict[str, list] = {}
    por_numero: dict[tuple, dict] = {}
    for nid, x in normas.items():
        item = {"id": nid, "t": x["t"], "n": x.get("n"), "a": x.get("a"), "data": x.get("data")}
        for mid in x.get("mats") or []:
            por_mat.setdefault(mid, []).append(item)
        if x.get("n"):
            por_numero[(x["t"], x["n"], x.get("a"))] = item
    leg = _legislatura(h)
    por_nome = {B.norm(v["nome"]): v for v in leg}
    por_nome.update({B.norm(v["civil"]): v for v in leg if v.get("civil") and B.norm(v["civil"]) not in por_nome})
    validos = tse.ids_eleitos()
    quem: dict[str, tuple[str | None, str | None]] = {}

    def pessoa(nome: str) -> tuple[str | None, str | None]:
        if nome not in quem:
            v = por_nome.get(B.norm(nome))
            if v:
                pid, cand = tse.casar(f"sagl-{v['id']}", [v["nome"], v.get("civil")], B.partido(v.get("partido")))
            else:
                pid, cand = tse.casar(f"autor-{B.slug(nome)}", [nome])
            quem[nome] = (pid if cand and pid in validos else None, v["id"] if v else None)
        return quem[nome]

    inicio_pref = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
    por: dict[str, list] = {pid: [] for pid in validos}
    do_pref: list = []
    sagl: dict[str, str] = {}
    fora: dict[str, int] = {}
    for mid, m in mats.items():
        if not _interessa(m) or not (m.get("det") or {}).get("lido"):
            continue
        sig, comum = TIPOS_MAT[m["t"]]
        sigla = f"{sig} {m['n']}/{m['a']}" if sig and m.get("n") else m["titulo"]
        st, txt, txt_en, situ, data_st, lei = situacao_recife(comum, m["det"], por_mat.get(mid) or [], por_numero)

        def item(papel: str) -> dict:
            p = regional.proposta(f"{PREFIXO}:{mid}", sigla, comum, m.get("data"), m.get("ementa"), situ,
                                  PAG_MATERIA.format(mid), papel, status=st, data_status=data_st, status_txt=txt, lei=lei)
            if txt_en:
                p["statusTxt_en"] = txt_en
            return p
        for nome, primeiro, desc in m.get("aut") or []:
            if desc == "Parlamentar":
                pid, vid = pessoa(nome)
                if pid:
                    por.setdefault(pid, []).append(item("autor" if primeiro else "coautor"))
                    if vid:
                        sagl[pid] = vid
                else:
                    fora[nome] = fora.get(nome, 0) + 1
            elif desc == "Poder Executivo" and comum in ("PL", "PLP", "PELO") and (m.get("data") or "") >= inicio_pref:
                do_pref.append(item("autor"))
    return por, do_pref, sagl, fora


def coletar() -> dict:
    global _n
    _n = 0
    t0 = time.time()
    h = hoje()
    CASA["fonte"] = fonte(CASA["casa"], "SAGL: matérias e reuniões plenárias (API pública)", f"{API}/@@materias", h)
    tse = B.Tse(IBGE, UF)
    vot = votacoes(tse, h)
    est = propostas(h)
    pref = B.cidade(IBGE, UF).get("prefeito") or {}
    notas = [("A lista de vereadores desta página é a dos eleitos em 2024 (TSE): o sistema da Câmara (SAGL) lista os titulares "
              "e os suplentes que assumiram, mas não diz quais titulares estão de licença. Por isso, as propostas e os votos "
              "dos suplentes que assumiram não aparecem aqui.",
              "The list of councilors on this page is the one of those elected in 2024 (TSE): the City Council's system (SAGL) "
              "lists the full members and the substitutes who took office, but does not say which full members are on leave. "
              "So the bills and votes of substitutes who took office do not appear here."),
             ("Os gastos do mandato de cada vereador não entram neste site: a Câmara publica a verba indenizatória (CEAP) num "
              "sistema de consulta (ceap.recife.pe.leg.br) que pede o teste \"não sou robô\" (reCAPTCHA) a cada pesquisa, e "
              "este site não contorna esse teste.",
              "Each councilor's office spending is not included on this site: the City Council publishes its office allowance "
              "(CEAP) in a search system (ceap.recife.pe.leg.br) that asks for a \"not a robot\" test (reCAPTCHA) for every "
              "search, and this site does not get around that test.")]
    extras: dict[str, dict] = {}
    if vot:
        cat, por_v, escopo_v, f_vot = vot
        for pid, lst in por_v.items():
            extras[pid] = {"fontes": [f_vot], "votacoes": B.bloco_votacoes(lst, escopo_v, f_vot, IBGE)}
    else:  # a leitura não terminou nesta rodada: ficam as votações já publicadas
        cat, blocos = B.votos_publicados(IBGE)
        extras = {pid: {"fontes": [b.get("fonte")], "votacoes": b} for pid, b in blocos.items()}
    escopo = (B.ESCOPO + ", segundo o SAGL, o sistema oficial da Câmara.",
              B.ESCOPO_EN + ", according to SAGL, the City Council's official system.")
    prefeito = None
    pendente = not est["_completo"]
    fora: dict[str, int] = {}
    if not pendente:
        por_p, do_pref, sagl, fora = blocos_propostas(est, tse, h, pref)
        for pid, lst in por_p.items():
            vid = sagl.get(pid)
            f_prop = fonte(CASA["casa"], "SAGL: matérias do vereador", PAG_PARL.format(vid) if vid else f"{API}/@@materias", h)
            x = extras.setdefault(pid, {"fontes": []})
            x["propostas"] = regional.bloco_propostas(lst, escopo[0], escopo[1], f_prop)
            x["fontes"].insert(0, f_prop)
        inicio = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
        desde_pt = (f"desde {data_pt(inicio)}, quando assumiu a prefeitura" if inicio > B.INICIO
                    else f"desde {data_pt(inicio)}, começo do mandato")
        desde_en = (f"since {data_en(inicio)}, when the current mayor took office" if inicio > B.INICIO
                    else f"since {data_en(inicio)}, start of the term")
        if pref.get("id"):
            f_pref = fonte(CASA["casa"], "SAGL: projetos de lei do Executivo (autoria: Prefeito do Recife)",
                           f"{API}/@@materias?ano={h[:4]}&tipo=11", h)
            if do_pref:
                prefeito = (pref["id"], {"propostas": regional.bloco_propostas(
                    do_pref, f"Projetos que a prefeitura mandou à Câmara Municipal {desde_pt} (projetos de lei, de lei "
                             "complementar e de emenda à Lei Orgânica), segundo o SAGL, o sistema oficial da Câmara",
                    f"Bills the mayor's office sent to the City Council {desde_en} (ordinary and complementary bills and "
                    "amendments to the city's Organic Law), according to SAGL, the City Council's official system", f_pref),
                    "fontes": [f_pref]})
            else:
                notas.append((f"Não achamos no SAGL desta Câmara projetos mandados pela prefeitura {desde_pt}: o perfil do "
                              "prefeito não mostra os projetos dele.",
                              f"We found no bills sent by the mayor's office {desde_en} in this City Council's SAGL system, so "
                              "the mayor's profile does not list them."))
    else:  # primeira carga em andamento: ficam as propostas já publicadas (as de antes, ou nenhuma)
        antes = C.publicados(IBGE)
        for pid, b in antes.items():
            if pid.startswith("ver-"):
                x = extras.setdefault(pid, {"fontes": []})
                x["propostas"] = b
                if b.get("fonte"):
                    x["fontes"].insert(0, b["fonte"])
            elif pid == pref.get("id"):
                prefeito = (pid, {"propostas": b, "fontes": [b["fonte"]] if b.get("fonte") else []})
    com_prop = any(x.get("propostas") for pid, x in extras.items() if pid.startswith("ver-"))
    if com_prop and pendente:  # primeira carga em andamento: fica a nota publicada antes (com a conta das matérias de suplentes)
        casa_antes = ler_json(regional.CAMARAS / f"{IBGE}.json", {}) or {}
        antes = next(((pt, en) for pt, en in zip(casa_antes.get("notas") or [], casa_antes.get("notas_en") or [])
                      if pt.startswith("As propostas entram")), None)
        if antes:
            notas.insert(1, antes)
    elif com_prop:
        nomes_f = sorted(fora, key=lambda n: (-fora[n], n))

        def junta(lst: list, e: str) -> str:
            return lst[0] if len(lst) == 1 else ", ".join(lst[:-1]) + f" {e} " + lst[-1]
        quem, quem_en = (junta(nomes_f, "e"), junta(nomes_f, "and")) if nomes_f else ("", "")
        n_fora = sum(fora.values())
        notas.insert(1, ("As propostas entram no perfil dos vereadores eleitos em 2024 que as assinaram (autor principal ou "
                         "coautor), ligados pelo nome; os projetos da Comissão Executiva (a Mesa) e das comissões não aparecem "
                         "em nenhum perfil" + (f", nem as {n_fora} matérias de suplentes que assumiram ({quem})" if fora else "")
                         + ".",
                         "Bills appear on the profile of the councilors elected in 2024 who signed them (main author or "
                         "co-author), matched by name; bills by the Executive Committee (the Council's board) and by "
                         "committees do not appear on any profile" + (f", nor do the {n_fora} bills by substitutes who took "
                                                                      f"office ({quem_en})" if fora else "") + "."))
    cobertura = {"lista": False, "propostas": com_prop, "votacoes": any(x.get("votacoes") for x in extras.values()), "gastos": False}
    r = B.salvar(IBGE, UF, CASA, [], extras, cobertura, notas, escopo if com_prop else None, prefeito=prefeito,
                 oficial=False, ids_validos=tse.ids_eleitos(), votacoes=cat if cobertura["votacoes"] else None)
    r["requisicoes"] = _n
    if pendente:
        r["pendente"] = True
        r["etapa"] = (f"propostas ({est['_total'] - est['_faltam']} de {est['_total']} páginas lidas)" if est["_total"]
                      else "propostas (lendo as listas)")
    if tse.sem_ligacao:
        log(f"  CMR: sem ligação com os eleitos de 2024 (suplentes que assumiram e outros, ficam fora): {len(tse.sem_ligacao)}")
    log(f"  CMR: {r.get('propostas', 0)} propostas{' (primeira carga em andamento)' if pendente else ''}, "
        f"{sum(1 for x in extras.values() if x.get('votacoes'))} eleitos de 2024 com votações nominais, {r.get('votacoes', 0)} votações, "
        f"{_n} pedidos, {time.time() - t0:.0f} s")
    return r
