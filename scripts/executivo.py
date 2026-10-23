"""Presidente e vice-presidente da República.

Gera dados/pessoas/pres-<slug>.json, dados/pessoas/vp-<slug>.json e dados/executivo.json (contrato no README).
Quem está no cargo depende da data (scripts/mandatos.py): até 4/1/2027, a chapa eleita em 2022 (fichas pesquisadas à mão,
abaixo); a partir de 5/1/2027, a chapa eleita em 2026, montada sozinha com os dados do TSE (mesmo id se for a mesma pessoa).

Fontes:
- Propostas do presidente = proposições de autoria do Poder Executivo (tipo de autor 30000, "Órgão do Poder
  Executivo") apresentadas desde o começo do mandato atual: MPV, PL, PLP, PLN e PEC. Arquivos em lote da Câmara dos Deputados
  (proposicoes-{ano}, proposicoesAutores-{ano}, proposicoesTemas-{ano}). id = "camara:{id}" (o mesmo da Câmara).
- Situação: PL, PLP e PEC = situação na Câmara (ultimoStatus). MPV e PLN são decididas pelo Congresso
  Nacional; a situação na Câmara delas é incompleta, então usamos a do Congresso (Dados Abertos do Senado,
  /dadosabertos/processo?sigla=MPV|PLN&ano=), que também diz qual lei foi gerada. Para PL/PLP/PEC que viraram
  lei ou estão no Senado, o número da lei vem do Senado (/dadosabertos/processo?sigla&numero&ano).
- Leis sancionadas: normas federais (Lei e Lei Complementar) por ano no Senado (/dadosabertos/legislacao/lista),
  menos as leis promulgadas depois de o Congresso derrubar um veto total (/dadosabertos/materia/vetos/{ano}).
- Vetos: /dadosabertos/materia/vetos/{ano} (vetos totais e parciais publicados desde o começo do mandato atual).
- Fichas: biografias oficiais (Presidência/Vice-Presidência), Câmara dos Deputados (mandatos de deputado),
  fotos do Palácio do Planalto e da Vice-Presidência no Wikimedia Commons (licença CC BY 2.0); a partir de 2027,
  candidatura no TSE (DivulgaCandContas: nome, partido, nascimento, foto).

Uso:  python scripts/executivo.py
"""
from __future__ import annotations

import collections
import csv
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (CACHE, DADOS, PESSOAS, STATUS_TXT, aplicar_simples, baixar_arquivo, baixar_json,  # noqa: E402
                   carregar_simples, chave_nome, classificar_situacao, data_iso, foto_local, fonte, hoje, ler_json, limpa,
                   log, ordenar_propostas, resumo_propostas, salvar_json, sem_acento, sem_mudar_data, slug)
from mandatos import CF, EC111, data_br as data_br_curta, extenso, vigente  # noqa: E402

CE = CACHE / "executivo"
CE.mkdir(parents=True, exist_ok=True)
SENADO = "https://legis.senado.leg.br/dadosabertos"
CAMARA_ARQ = "https://dadosabertos.camara.leg.br/arquivos"
VIG = vigente("presidente")  # mandato em curso hoje (eleição, início, fim)
INICIO = VIG["inicio"]
TIPOS_EXEC = ("MPV", "PL", "PLP", "PLN", "PEC")
csv.field_size_limit(10 ** 9)

# Contorno: comum.baixar() não fecha a resposta de erro HTTP; no Python 3.14 isso gera avisos
# "Exception ignored ... I/O operation on closed file" ao terminar. Só silencia esse aviso.
_hook_original = sys.unraisablehook


def _hook_silencioso(u):
    if isinstance(u.exc_value, ValueError) and "closed file" in str(u.exc_value):
        return
    _hook_original(u)


sys.unraisablehook = _hook_silencioso


def _sem_datas(o):
    """Cópia sem 'atualizado' e sem a data de consulta das fontes (dicionários com veiculo/titulo/url)."""
    if isinstance(o, dict):
        fonte_ = {"veiculo", "titulo", "url"} <= set(o)
        return {k: _sem_datas(v) for k, v in o.items() if k != "atualizado" and not (fonte_ and k == "data")}
    if isinstance(o, list):
        return [_sem_datas(v) for v in o]
    return o


def sem_mudar_datas(novo: dict, caminho) -> dict:
    """Como comum.sem_mudar_data, mas também ignora a data de consulta das fontes (fonte() usa a data de hoje):
    se nada mais mudou, devolve o conteúdo antigo (salvar_json não reescreve)."""
    antigo = ler_json(caminho)
    if isinstance(antigo, dict) and _sem_datas(antigo) == _sem_datas(novo):
        return antigo
    return sem_mudar_data(novo, caminho)


def L(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def senado(caminho: str, cache: str, max_idade_h=20):
    time.sleep(0.12)  # a API do Senado pede menos de 10 requisições por segundo
    return baixar_json(SENADO + caminho, cache=f"executivo/{cache}", max_idade_h=max_idade_h)


def nome_norma(desc: str | None) -> tuple[str | None, str]:
    """'Lei nº 14.600 de 19/06/2023' -> ('Lei nº 14.600/2023', 'a')."""
    if not desc:
        return None, "a"
    m = re.match(r"\s*(.+?)\s+n[º°o]\.?\s*([\d\.]+)\s*(?:,?\s*de\s+\d{1,2}/\d{1,2}/(\d{4}))?", desc)
    if not m:
        return limpa(desc), "a"
    tipo, num, ano = m.groups()
    tipo = tipo.replace("Resolução do Congresso Nacional", "Resolução do Congresso")
    return f"{tipo} nº {num}" + (f"/{ano}" if ano else ""), ("o" if tipo.lower().startswith("decreto") else "a")


# ---------------------------------------------------------------- arquivos da Câmara
def ler_csv(nome: str, ano: int):
    arq = baixar_arquivo(f"{CAMARA_ARQ}/{nome}/csv/{nome}-{ano}.csv", f"executivo/{nome}-{ano}.csv", max_idade_h=20)
    with open(arq, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def propostas_do_executivo() -> tuple[dict, collections.Counter, dict]:
    anos = range(int(INICIO[:4]), int(hoje()[:4]) + 1)
    autores = set()
    for ano in anos:
        for r in ler_csv("proposicoesAutores", ano):
            if r.get("codTipoAutor") == "30000":  # Órgão do Poder Executivo (Poder Executivo / Presidência da República)
                autores.add(r["idProposicao"])
    props, outros = {}, collections.Counter()
    for ano in anos:
        for r in ler_csv("proposicoes", ano):
            if r["id"] not in autores or (r.get("dataApresentacao") or "") < INICIO:
                continue
            if r["siglaTipo"] in TIPOS_EXEC:
                props[r["id"]] = r
            else:
                outros[r["siglaTipo"]] += 1
    temas = collections.defaultdict(list)
    for ano in anos:
        for r in ler_csv("proposicoesTemas", ano):
            pid = (r.get("uriProposicao") or "").rstrip("/").split("/")[-1]
            if pid in props and limpa(r.get("tema")) and limpa(r["tema"]) not in temas[pid]:
                temas[pid].append(limpa(r["tema"]))
    return props, outros, temas


# ---------------------------------------------------------------- situação no Congresso / Senado
def congresso(sigla: str) -> dict:
    """{(sigla, numero, ano): processo} das MPV/PLN no Congresso Nacional (Dados Abertos do Senado)."""
    out = {}
    for ano in range(int(INICIO[:4]), int(hoje()[:4]) + 1):
        atual = ano >= int(hoje()[:4]) - 1
        for x in L(senado(f"/processo.json?sigla={sigla}&ano={ano}", f"cn_{sigla}_{ano}.json", 20 if atual else 24 * 7)):
            m = re.match(r"([A-Z]+)\s+(\d+)/(\d{4})$", x.get("identificacao") or "")
            if m:
                out[(m.group(1), int(m.group(2)), int(m.group(3)))] = x
    return out


def no_senado(sigla: str, numero: int, ano: int) -> dict | None:
    """Processo de mesmo número no Senado (desde 2019 a numeração é única nas duas Casas)."""
    try:
        q = urllib.parse.urlencode({"sigla": sigla, "numero": numero, "ano": ano})
        lst = L(senado(f"/processo.json?{q}", f"sf_{sigla}_{numero}_{ano}.json", 20))
    except Exception as e:  # noqa: BLE001
        log(f"  Senado {sigla} {numero}/{ano}: {e}")
        return None
    lst = [x for x in lst if (x.get("identificacao") or "") == f"{sigla} {numero}/{ano}"]
    return lst[0] if lst else None


def status_congresso(x: dict, sigla: str) -> dict:
    """Status de MPV/PLN pela situação no Congresso Nacional."""
    S = limpa(x.get("situacaoAtual")) or ""
    Su = S.upper()
    D = x.get("siglaTipoDeliberacao") or ""
    data = data_iso(x.get("dataSituacaoAtual") or x.get("dataDeliberacao"))
    r = {"situacao": S or None, "dataStatus": data, "lei": None}
    if x.get("normaGerada"):
        nome, art = nome_norma(x["normaGerada"])
        veto = " (com partes vetadas)" if "VETO PARCIAL" in Su else ""
        return {**r, "status": "lei", "statusTxt": f"Virou {art} {nome}{veto}", "lei": {"nome": nome, "url": None}}
    if D == "PERDA_EFICACIA":
        return {**r, "status": "parada", "statusTxt": "Perdeu a validade (o Congresso não votou a tempo)",
                "situacao": S or "PERDA DE EFICÁCIA"}
    if "EFICÁCIA" in Su:
        return {**r, "status": "parada", "statusTxt": "Perdeu a validade (ficou sem eficácia)"}
    if D == "PREJUDICADO" or Su.startswith("PREJUDICAD"):
        return {**r, "status": "parada", "statusTxt": "Ficou prejudicada (não vai mais ser votada)",
                "situacao": S or "PREJUDICADA"}
    if D == "REVOGADO" or Su.startswith("REVOGAD"):
        return {**r, "status": "retirada", "statusTxt": "Foi revogada (cancelada)"}
    if D == "INADIMITIDA_URGENCIA":
        return {**r, "status": "rejeitada", "statusTxt": "Rejeitada pelo Congresso (sem os requisitos de urgência)"}
    if D.startswith("REJEITADO") or Su.startswith("REJEITAD"):
        return {**r, "status": "rejeitada", "statusTxt": "Rejeitada pelo Congresso"}
    if D == "RETIRADO_PELO_AUTOR" or "RETIRAD" in Su:
        return {**r, "status": "retirada", "statusTxt": "O governo retirou a proposta", "situacao": S or "RETIRADA PELO AUTOR"}
    if Su.startswith("REMETIDA À SANÇÃO") or "SANÇÃO" in Su:
        return {**r, "status": "aprovada", "statusTxt": "Aprovada pelo Congresso; esperando a sanção do presidente"}
    if x.get("tramitando") == "Sim":
        if sigla == "MPV":
            return {**r, "status": "andando", "statusTxt": "Já está valendo, mas o Congresso ainda precisa votar"}
        return {**r, "status": "andando", "statusTxt": "Ainda em análise no Congresso"}
    st = classificar_situacao(S or None)
    return {**r, "status": st, "statusTxt": STATUS_TXT[st]}


TXT_CAMARA = {
    "aprovada": "Aprovada na Câmara; agora está no Senado",
    "andando": "Ainda em discussão na Câmara",
    "junta": "Andando junto com outra proposta parecida",
    "arquivada": "Arquivada",
    "rejeitada": "Rejeitada",
    "parada": "Parou (não vai mais ser votada)",
    "retirada": "O governo retirou a proposta",
    "outra": STATUS_TXT["outra"],
}


def situacao_api_camara(pid: str) -> tuple[str, str | None]:
    """Situação de uma proposição pela API da Câmara: status atual ou, se vier vazio, a última tramitação com situação."""
    api = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    try:
        st = baixar_json(f"{api}/{pid}", cache=f"executivo/camara_{pid}.json", max_idade_h=20)["dados"].get("statusProposicao") or {}
        if limpa(st.get("descricaoSituacao")):
            return limpa(st["descricaoSituacao"]), data_iso(st.get("dataHora"))
        tram = L(baixar_json(f"{api}/{pid}/tramitacoes", cache=f"executivo/camara_{pid}_tram.json", max_idade_h=20).get("dados"))
        tram.sort(key=lambda x: (x.get("dataHora") or "", x.get("sequencia") or 0))
        for x in reversed(tram):
            if limpa(x.get("descricaoSituacao")):
                return limpa(x["descricaoSituacao"]), data_iso(x.get("dataHora"))
    except Exception as e:  # noqa: BLE001
        log(f"  Câmara {pid}: {e}")
    return "", None


def status_camara(p: dict) -> dict:
    """Status de PL/PLP/PEC pela situação na Câmara (casa onde começam as propostas do presidente)."""
    S = limpa(p.get("ultimoStatus_descricaoSituacao")) or ""
    desp = p.get("ultimoStatus_despacho") or ""
    data = data_iso(p.get("ultimoStatus_dataHora"))
    if not S:  # o arquivo em lote veio sem situação: pergunta à API da Câmara (status atual ou última tramitação com situação)
        S, data_api = situacao_api_camara(p["id"])
        data = data_api or data
    st = classificar_situacao(S or None)
    s_low = sem_acento(S.lower())
    if "aguardando envio ao senado" in s_low or "aguardando autografos" in s_low:
        st = "aprovada"
    txt = TXT_CAMARA.get(st)
    if "sancao" in s_low:
        txt = "Aprovada pelo Congresso; esperando a sanção do presidente"
    elif "vetado totalmente" in s_low:
        txt = "Aprovada pelo Congresso, mas vetada por inteiro"
    elif st == "parada" and "prejudicad" in s_low:
        txt = "Ficou prejudicada (não vai mais ser votada)"
    elif st == "aprovada" and "aguardando envio ao senado" in s_low:
        txt = "Aprovada na Câmara; vai para o Senado"
    r = {"status": st, "statusTxt": txt, "situacao": S or None, "dataStatus": data, "lei": None}
    if st == "lei":
        m = re.search(r"(Lei(?: Ordinária| Complementar)?|Emenda Constitucional)\s*(?:n[º°o]\.?\s*)?([\d\.]+)\s*/\s*(\d{4})", desp)
        if m:
            nome = f"{m.group(1).replace('Lei Ordinária', 'Lei')} nº {m.group(2)}/{m.group(3)}"
            r.update(statusTxt=f"Virou a {nome}", lei={"nome": nome, "url": None})
        else:
            r.update(statusTxt="Virou lei")
    return r


# ---------------------------------------------------------------- leis e vetos (contagem)
def leis_e_vetos() -> dict:
    ano_atual = int(hoje()[:4])
    leis = collections.Counter()
    ult = {"lei": "", "veto": ""}  # data da lei e do veto mais recentes contados (o "até quando" da contagem)
    for tipo in ("LEI", "LCP"):
        for ano in range(int(INICIO[:4]), ano_atual + 1):
            d = senado(f"/legislacao/lista.json?tipo={tipo}&ano={ano}", f"leis_{tipo}_{ano}.json", 20 if ano == ano_atual else 24 * 30)
            for x in L(((d.get("ListaDocumento") or {}).get("documentos") or {}).get("documento")):
                da = data_iso(x.get("dataassinatura")) or ""
                if da >= INICIO:
                    leis[tipo] += 1
                    ult["lei"] = max(ult["lei"], da)
    vetos = collections.Counter()
    promulgadas = []  # leis que nasceram da derrubada de um veto total (promulgadas, não sancionadas)
    for ano in range(int(INICIO[:4]) - 4, ano_atual + 1):
        d = senado(f"/materia/vetos/{ano}.json", f"vetos_{ano}.json", 20 if ano >= ano_atual - 1 else 24 * 30)
        for v in L(((d.get("ListaVetosAnoCN") or {}).get("Vetos") or {}).get("Veto")):
            dp = data_iso(v.get("DataPublicacao")) or ""
            if dp >= INICIO:
                vetos["total" if v.get("Total") == "Sim" else "parcial"] += 1
                ult["veto"] = max(ult["veto"], dp)
            ng = (v.get("MateriaVetada") or {}).get("NormaGerada") or {}
            if v.get("Total") == "Sim" and ng and (data_iso(ng.get("DataAssinatura")) or "") >= INICIO and \
                    ng.get("SiglaTipoNorma") in ("LEI-n", "LCP"):
                promulgadas.append(ng.get("NomeNorma"))
    n_leis = leis["LEI"] + leis["LCP"]
    promulgadas = sorted(set(promulgadas))
    return {
        "leisSancionadas": n_leis - len(promulgadas),
        "vetos": vetos["total"] + vetos["parcial"],
        "vetosTotais": vetos["total"],
        "vetosParciais": vetos["parcial"],
        "periodo": {"inicio": INICIO, "ultimaLei": ult["lei"] or None, "ultimoVeto": ult["veto"] or None},
        "obs": (f"Leis ordinárias e complementares assinadas pela Presidência da República desde {data_br_curta(INICIO)} "
                f"({leis['LEI']} ordinárias + {leis['LCP']} complementares = {n_leis}), sem contar as "
                f"{len(promulgadas)} leis promulgadas depois de o Congresso derrubar um veto total. Inclui as poucas "
                "leis e vetos assinados pelo vice-presidente quando estava no exercício da Presidência. "
                "Veto parcial = só uma parte da lei foi barrada; veto total = a lei inteira foi barrada."),
        "leisPromulgadasAposVetoTotal": promulgadas,
        "fonte": [
            fonte("Senado Federal", "Dados Abertos: legislação federal por ano (leis ordinárias)",
                  f"{SENADO}/legislacao/lista.json?tipo=LEI&ano={ano_atual}"),
            fonte("Senado Federal", "Dados Abertos: legislação federal por ano (leis complementares)",
                  f"{SENADO}/legislacao/lista.json?tipo=LCP&ano={ano_atual}"),
            fonte("Congresso Nacional", "Dados Abertos: vetos presidenciais por ano", f"{SENADO}/materia/vetos/{ano_atual}.json"),
            fonte("Congresso Nacional", "Vetos presidenciais (página do Congresso)", "https://www.congressonacional.leg.br/materias/vetos"),
            fonte("Palácio do Planalto", "Legislação: leis ordinárias", "https://www4.planalto.gov.br/legislacao/portal-legis/legislacao-1/leis-ordinarias"),
        ],
    }


# ---------------------------------------------------------------- fotos (Wikimedia Commons)
FOTOS = {
    "pres-lula": ("File:Foto oficial de Luiz Inácio Lula da Silva (2023–2027).jpg", "Ricardo Stuckert/PR (Palácio do Planalto)"),
    "vp-alckmin": ("File:Vice Presidente da República do Brasil, Geraldo Alckmin em 2023.jpg", "Cadu Gomes/VPR (Vice-Presidência da República)"),
}


def foto_commons(pid: str) -> tuple[str | None, str | None, dict | None]:
    titulo, autor = FOTOS[pid]
    try:
        q = urllib.parse.urlencode({"action": "query", "titles": titulo, "prop": "imageinfo", "iiprop": "url|extmetadata",
                                    "iiurlwidth": 480, "format": "json"})
        d = baixar_json(f"https://commons.wikimedia.org/w/api.php?{q}", cache=f"executivo/commons_{pid}.json", max_idade_h=24 * 7)
        ii = next(iter(d["query"]["pages"].values()))["imageinfo"][0]
        lic = re.sub(r"<[^>]+>", "", (ii["extmetadata"].get("LicenseShortName") or {}).get("value", ""))
    except Exception as e:  # noqa: BLE001
        log(f"  foto {pid}: {e}")
        return None, None, None
    if not lic.upper().startswith(("CC BY", "CC0", "PUBLIC DOMAIN")):
        log(f"  foto {pid}: licença {lic!r} não é livre; sem foto")
        return None, None, None
    foto = foto_local(ii.get("thumburl") or ii["url"], pid)
    credito = f"{autor}, licença {lic}, via Wikimedia Commons" if foto else None
    return foto, credito, fonte("Wikimedia Commons", f"Foto: {titulo[5:]} ({lic})", ii["descriptionurl"])


# ---------------------------------------------------------------- principal
def montar_lista(props, temas, simples):
    mpv, pln = congresso("MPV"), congresso("PLN")
    lista, regs = [], collections.Counter()
    for pid, p in props.items():
        sig, num, ano = p["siglaTipo"], int(p["numero"]), int(p["ano"])
        fonte_status = "Câmara"
        if sig in ("MPV", "PLN") and (sig, num, ano) in (mpv if sig == "MPV" else pln):
            c = status_congresso((mpv if sig == "MPV" else pln)[(sig, num, ano)], sig)
            fonte_status = "Congresso"
        else:
            c = status_camara(p)
            if c["status"] in ("lei", "aprovada") or (sig == "PEC" and c["status"] == "andando"):
                x = no_senado(sig, num, ano)
                if x and (x.get("normaGerada") or (c["status"] == "aprovada" and x.get("situacaoAtual"))):
                    if x.get("normaGerada"):
                        nome, art = nome_norma(x["normaGerada"])
                        veto = " (com partes vetadas)" if "VETO PARCIAL" in (x.get("situacaoAtual") or "").upper() else ""
                        c = {"status": "lei", "statusTxt": f"Virou {art} {nome}{veto}", "lei": {"nome": nome, "url": None},
                             "situacao": limpa(x.get("situacaoAtual")) or c["situacao"],
                             "dataStatus": data_iso(x.get("dataSituacaoAtual")) or c["dataStatus"]}
                        fonte_status = "Senado"
                    elif x.get("tramitando") == "Sim" and c["status"] == "aprovada":
                        c["statusTxt"] = "Aprovada na Câmara; agora está no Senado"
                    elif (x.get("situacaoAtual") or "").upper() == "VETADA":
                        c = {"status": "rejeitada", "statusTxt": "Aprovada pelo Congresso, mas vetada por inteiro",
                             "lei": None, "situacao": limpa(x.get("situacaoAtual")), "dataStatus": data_iso(x.get("dataSituacaoAtual"))}
                        fonte_status = "Senado"
        regs[(fonte_status, sig, c["situacao"] or "(sem situação)", c["status"])] += 1
        lista.append({
            "id": f"camara:{pid}",
            "sigla": f"{sig} {num}/{ano}",
            "tipo": sig,
            "data": data_iso(p.get("dataApresentacao")),
            "ementa": limpa(p.get("ementa")),
            "s": None,
            "status": c["status"],
            "statusTxt": c["statusTxt"],
            "situacao": c["situacao"],
            "dataStatus": c["dataStatus"],
            "papel": "autor",
            "temas": sorted(temas.get(pid, []), key=chave_nome),
            "url": f"https://www.camara.leg.br/propostas-legislativas/{pid}",
            "lei": c["lei"],
        })
    aplicar_simples(lista, simples)
    return ordenar_propostas(lista), regs


# presidentes desde 1995 (Biblioteca da Presidência: galeria dos ex-presidentes): mandatos no mesmo cargo, para quem
# voltar ao cargo. Dilma Rousseff foi afastada em 12/5/2016 e teve o mandato encerrado pelo Senado em 31/8/2016 (impeachment);
# Michel Temer, vice, assumiu a Presidência nessa data.
GALERIA = {"veiculo": "Presidência da República", "titulo": "Galeria dos ex-presidentes (Biblioteca da Presidência)",
           "url": "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/biblioteca-da-pr/galeria-dos-ex-presidentes",
           "data": "2026-10-23"}
MANDATOS_PRESIDENTE = {
    "LUIZ INACIO LULA DA SILVA": [("2023-01-01", "2027-01-05"), ("2007-01-01", "2010-12-31"), ("2003-01-01", "2006-12-31")],
    "JAIR MESSIAS BOLSONARO": [("2019-01-01", "2022-12-31")],
    "MICHEL MIGUEL ELIAS TEMER LULIA": [("2016-08-31", "2018-12-31")],
    "DILMA VANA ROUSSEFF": [("2015-01-01", "2016-08-31"), ("2011-01-01", "2014-12-31")],
    "FERNANDO HENRIQUE CARDOSO": [("1999-01-01", "2002-12-31"), ("1995-01-01", "1998-12-31")],
}
MANDATOS_VICE = {
    "GERALDO JOSE RODRIGUES ALCKMIN FILHO": [("2023-01-01", "2027-01-05")],
    "ANTONIO HAMILTON MARTINS MOURAO": [("2019-01-01", "2022-12-31")],
    "MICHEL MIGUEL ELIAS TEMER LULIA": [("2015-01-01", "2016-08-31"), ("2011-01-01", "2014-12-31")],
}


def chapa_eleita(ano: int, propostas: dict, exe: dict, fonte_cam: dict) -> tuple[dict, dict, list]:
    """Chapa eleita no ano (a partir de 2026), com os dados do TSE. Se for a mesma pessoa da chapa anterior, mantém o id
    (os links continuam funcionando) e a ficha pesquisada à mão (nascimento, naturalidade, foto)."""
    import tse  # noqa: PLC0415 (só aqui: leitura grande)
    rows = [tse.cand(r, ano) for r in tse.ler_csv(tse.zip_tse("consulta_cand", ano))
            if r["DS_CARGO"].upper() in ("PRESIDENTE", "VICE-PRESIDENTE") and r["CD_ELEICAO"] in tse.ORDINARIAS[ano]]
    eleitos = [c for c in rows if c["cargo"] == "PRESIDENTE" and tse.eleito(c["sit"])]
    if not eleitos:
        raise RuntimeError(f"o TSE ainda não mostra a chapa eleita em {ano}: as fichas de ontem ficam como estão")
    pc = max(eleitos, key=lambda c: c["turno"])
    vices = [c for c in rows if c["cargo"] == "VICE-PRESIDENTE" and c["num"] == pc["num"] and c["turno"] == pc["turno"]]
    vc = vices[0] if vices else None
    pres_ant, vice_ant, _ = chapa_2022(propostas, exe, fonte_cam)
    ini_pt, ini_en = extenso(VIG["inicio"])
    fim_pt, fim_en = extenso(VIG["fim"])
    turno = f"{pc['turno']}º turno" if pc["turno"] == 2 else "1º turno"

    def ficha(c: dict, tipo: str, anterior: dict, mandatos_conhecidos: dict) -> dict:
        g = c["genero"]
        a = "a" if g == "F" else "o"
        civil = tse.nome_tse(c["civil"]) or tse.nome_tse(c["nome"])
        mesma = chave_nome(anterior.get("nomeCivil") or "") == chave_nome(civil or "")
        fc = tse.fonte_cand(c, None)
        cargo = "Presidente da República" if tipo == "pres" else "Vice-presidente da República"
        if mesma:
            ant = [{"cargo": cargo, "inicio": anterior["mandato"]["inicio"], "fim": anterior["mandato"]["fim"]}] + anterior.get("mandatosAnteriores", [])
        else:
            ant = [{"cargo": cargo, "inicio": i, "fim": f} for i, f in mandatos_conhecidos.get(chave_nome(civil or ""), [])]
        quem = "presidente" if tipo == "pres" else "vice-presidente"
        return {
            "id": anterior["id"] if mesma else f"{tipo}-{slug(tse.nome_tse(c['urna']) or civil)}",
            "tipo": tipo, "nome": tse.nome_tse(c["urna"]), "nomeCivil": civil, "cargo": cargo, "genero": g,
            "uf": None, "municipio": None, "partido": c["partido"],
            "foto": anterior.get("foto") if mesma else tse.url_foto(ano, c["sq"], "BR"),
            "fotoCredito": anterior.get("fotoCredito") if mesma else "Foto da candidatura no TSE (DivulgaCandContas)",
            "nascimento": (anterior.get("nascimento") or c["nasc"]) if mesma else c["nasc"],
            "naturalidade": anterior.get("naturalidade") if mesma else None,
            "mandato": {"inicio": VIG["inicio"], "fim": VIG["fim"], "situacao": "Em exercício",
                        "obs": f"Eleit{a} em {ano}, no {turno}. O mandato começou em {ini_pt} e vai até a posse da próxima chapa eleita, em {fim_pt}.",
                        "obs_en": f"Elected in {ano} ({'runoff' if pc['turno'] == 2 else 'first round'}). The term began on {ini_en} and lasts until the next elected ticket takes office, on {fim_en}.",
                        "fonte": [fc, EC111]},
            "mandatosAnteriores": ant,
            "eleicao": {"ano": ano, "cargo": cargo, "votos": None, "situacao": f"Eleit{a} no {turno}", "fonte": fc},
            "eleicao2026": None, "bens": None,
            "links": {"oficial": "https://www.gov.br/planalto/pt-br" if tipo == "pres" else "https://www.gov.br/planalto/pt-br/vice-presidencia",
                      "email": None, "redes": []},
            "comissoes": [], "gastos": None, "votacoes": None,
            "fontes": [fc, EC111, CF] + ([GALERIA] if ant and not mesma else []),
            "atualizado": hoje(),
            "_quem": quem,
        }

    pres = ficha(pc, "pres", pres_ant, MANDATOS_PRESIDENTE)
    pres.update({"propostas": propostas, "executivo": exe})
    pres["fontes"].append(fonte_cam)
    vice = ficha(vc, "vp", vice_ant, MANDATOS_VICE) if vc else {"id": "vp-vago", "tipo": "vp", "vago": True}
    if vc:
        vice["propostas"] = vice_ant["propostas"]  # o vice não apresenta projetos (mesmo texto e fonte para qualquer vice)
        vice["executivo"] = None
    for p in (pres, vice):
        p.pop("_quem", None)
    return pres, vice, [EC111, CF]


def chapa_2022(propostas: dict, exe: dict, fonte_cam: dict) -> tuple[dict, dict, list]:
    """Chapa eleita em 2022 (mandato de 1º/1/2023 a 5/1/2027): fichas pesquisadas à mão, com fonte."""
    # ----- presidente
    foto_p, cred_p, fonte_foto_p = foto_commons("pres-lula")
    bio_p = fonte("Presidência da República", "Biografia de Luiz Inácio Lula da Silva (Biblioteca da Presidência)",
                  "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/biblioteca-da-pr/galeria-dos-ex-presidentes/luiz-inacio-lula-da-silva/biografia-completa")
    ec111 = fonte("Palácio do Planalto", "Emenda Constitucional nº 111/2021 (posse em 5 de janeiro a partir de 2027)",
                  "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm", "2021-09-28")
    dep_lula = fonte("Câmara dos Deputados", "Dados Abertos: deputado Luiz Inácio Lula da Silva (1987-1991)",
                     "https://dadosabertos.camara.leg.br/api/v2/deputados/139289")
    mand_p = {"inicio": "2023-01-01", "fim": "2027-01-05", "situacao": "Em exercício",
              "obs": "O mandato vai até a posse do próximo presidente, em 5 de janeiro de 2027 (regra da Emenda Constitucional 111, de 2021).",
              "fonte": ec111}
    pres = {
        "id": "pres-lula", "tipo": "pres", "nome": "Lula", "nomeCivil": "Luiz Inácio Lula da Silva",
        "cargo": "Presidente da República", "genero": "M", "uf": None, "municipio": None, "partido": "PT",
        "foto": foto_p, "fotoCredito": cred_p,
        "nascimento": "1945-10-27", "naturalidade": "Garanhuns (PE)",
        "mandato": mand_p,
        "mandatosAnteriores": [
            {"cargo": "Presidente da República", "inicio": "2007-01-01", "fim": "2010-12-31"},
            {"cargo": "Presidente da República", "inicio": "2003-01-01", "fim": "2006-12-31"},
        ],  # só mandatos no mesmo cargo, como para todo mundo (ver scripts/montar.py)
        "eleicao": None, "eleicao2026": None, "bens": None,
        "links": {"oficial": "https://www.gov.br/planalto/pt-br", "email": None, "redes": []},
        "comissoes": [],
        "propostas": propostas,
        "executivo": exe,
        "gastos": None,
        "votacoes": None,
        "fontes": [bio_p, ec111, fonte_cam,
                   fonte("Congresso Nacional", "Dados Abertos: medidas provisórias e PLN por ano", f"{SENADO}/processo.json?sigla=MPV&ano={hoje()[:4]}")]
                  + ([fonte_foto_p] if fonte_foto_p else []),
        "atualizado": hoje(),
    }

    # ----- vice
    foto_v, cred_v, fonte_foto_v = foto_commons("vp-alckmin")
    bio_v = fonte("Vice-Presidência da República", "Biografia do Vice-Presidente da República",
                  "https://www.gov.br/planalto/pt-br/vice-presidencia/acesso-a-informacao/institucional/biografia-do-vice-presidente-da-republica-1")
    dep_alck = fonte("Câmara dos Deputados", "Dados Abertos: deputado Geraldo Alckmin (1987-1995)",
                     "https://dadosabertos.camara.leg.br/api/v2/deputados/65480")
    # saída do MDIC: fontes oficiais primeiro (quem ocupa o ministério desde 03/04/2026), imprensa só como apoio
    saida_mdic = [fonte("Controladoria-Geral da União (e-Agendas)", "e-Agendas: autoridades em exercício no MDIC, com cargo e data de início",
                        "https://eagendas.cgu.gov.br/pesquisa/agentes-publicos-obrigados-por-orgao/orgao/1399/ativo/true", hoje()),
                  fonte("Presidência da República (Planalto)", "Ministros e Ministras (lista oficial do 1º escalão)",
                        "https://www.gov.br/planalto/pt-br/conheca-a-presidencia/ministros-e-ministras", "2026-05-05"),
                  fonte("Valor Econômico", "Exoneração de Alckmin e Gleisi é publicada no DOU",
                        "https://valor.globo.com/politica/noticia/2026/04/03/exonerao-de-alckmin-e-gleisi-publicada-no-dou.ghtml", "2026-04-03")]
    cf61 = fonte("Palácio do Planalto", "Constituição Federal, arts. 61, 62, 79 e 84 (quem pode propor leis; funções do vice)",
                 "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", "1988-10-05")
    zero = resumo_propostas([])
    vice = {
        "id": "vp-alckmin", "tipo": "vp", "nome": "Geraldo Alckmin", "nomeCivil": "Geraldo José Rodrigues Alckmin Filho",
        "cargo": "Vice-presidente da República", "genero": "M", "uf": None, "municipio": None, "partido": "PSB",
        "foto": foto_v, "fotoCredito": cred_v,
        "nascimento": "1952-11-07", "naturalidade": "Pindamonhangaba (SP)",
        "mandato": {"inicio": "2023-01-01", "fim": "2027-01-05", "situacao": "Em exercício",
                    "obs": ("Também foi ministro do Desenvolvimento, Indústria, Comércio e Serviços de janeiro de 2023 até "
                            "3 de abril de 2026; hoje exerce só a Vice-Presidência. O mandato vai até a posse da próxima "
                            "chapa eleita, em 5 de janeiro de 2027."),
                    "fonte": saida_mdic},
        "mandatosAnteriores": [],  # nenhum mandato anterior como vice-presidente (só o mesmo cargo, como para todo mundo)
        "eleicao": None, "eleicao2026": None, "bens": None,
        "links": {"oficial": "https://www.gov.br/planalto/pt-br/vice-presidencia", "email": None, "redes": []},
        "comissoes": [],
        "propostas": {
            "escopo": ("O vice-presidente não apresenta projetos de lei: quem envia propostas ao Congresso em nome do "
                       "Poder Executivo é o presidente. Quando o vice substitui o presidente (em viagens, por exemplo), "
                       "o que ele assina conta como ato da Presidência."),
            "resumo": zero, "porTipo": {}, "porTema": [], "outros": None, "fonte": cf61, "lista": [],
        },
        "gastos": None,
        "votacoes": None,
        "fontes": [bio_v, cf61, ec111] + saida_mdic + ([fonte_foto_v] if fonte_foto_v else []),
        "atualizado": hoje(),
    }
    return pres, vice, [bio_p, bio_v, ec111]


def main():
    t0 = time.time()
    log("Executivo: propostas do Poder Executivo (arquivos da Câmara)")
    props, outros, temas = propostas_do_executivo()
    log(f"  {len(props)} propostas (MPV/PL/PLP/PLN/PEC) desde {INICIO}; outros documentos: {sum(outros.values())}")
    lista, regs = montar_lista(props, temas, carregar_simples())
    linhas = ["fonte da situação | tipo | situação oficial | quantidade | status"]
    linhas += [f"{f} | {t} | {s} | {n} | {st}" for (f, t, s, st), n in sorted(regs.items(), key=lambda kv: (-kv[1], kv[0]))]
    (CE / "situacoes.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    log(f"Leis sancionadas e vetos desde {data_br_curta(INICIO)}")
    exe = leis_e_vetos()
    log(f"  leis sancionadas: {exe['leisSancionadas']}; vetos: {exe['vetos']} ({exe['vetosTotais']} totais, {exe['vetosParciais']} parciais)")

    por_tema = collections.Counter(t for p in lista for t in p["temas"])
    fonte_cam = fonte("Câmara dos Deputados", "Dados Abertos: proposições e autores (arquivos por ano)",
                      "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile")
    propostas = {
        "escopo": f"Propostas enviadas pelo presidente ao Congresso no mandato atual (desde {extenso(INICIO)[0]})",
        "escopo_en": f"Proposals sent by the President to Congress in the current term (since {extenso(INICIO)[1]})",
        "resumo": resumo_propostas(lista),
        "porTipo": dict(sorted(collections.Counter(p["tipo"] for p in lista).items())),
        "porTema": [{"tema": t, "n": n} for t, n in sorted(por_tema.items(), key=lambda kv: chave_nome(kv[0]))],
        "outros": {"total": sum(outros.values()), "porTipo": dict(sorted(outros.items())),
                   "url": "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile",
                   "txt": "Mensagens (como indicações de autoridades e acordos com outros países), renovações de "
                          "rádio e TV e outros documentos enviados ao Congresso"},
        "nota": ("Medidas provisórias (MPV) já valem como lei assim que o presidente as publica, mas perdem a validade se o "
                 "Congresso não as aprovar em até 120 dias. A situação das MPV e dos PLN (orçamento) é a do Congresso Nacional; "
                 "a das demais propostas é a da Câmara, onde elas começam."),
        "fonte": fonte_cam,
        "lista": lista,
    }

    if VIG["eleicao"] == 2022:
        pres, vice, fontes_chapa = chapa_2022(propostas, exe, fonte_cam)
    else:
        pres, vice, fontes_chapa = chapa_eleita(VIG["eleicao"], propostas, exe, fonte_cam)
    # fichas de quem saiu do cargo (outra pessoa assumiu): o site não mostra mais
    for arq in list(PESSOAS.glob("pres-*.json")) + list(PESSOAS.glob("vp-*.json")):
        if arq.stem not in (pres["id"], vice["id"]):
            arq.unlink()

    for pessoa in (pres, vice):
        arq = PESSOAS / f"{pessoa['id']}.json"
        salvar_json(arq, sem_mudar_datas(pessoa, arq))

    def resumo(x):
        return {k: x[k] for k in ("id", "nome", "cargo", "partido", "foto", "genero", "mandato", "eleicao2026")}
    geral = {
        "presidente": resumo(pres),
        "vice": resumo(vice),
        "fontes": fontes_chapa + [fonte_cam] + exe["fonte"][:3],
        "atualizado": hoje(),
    }
    arq = DADOS / "executivo.json"
    salvar_json(arq, sem_mudar_datas(geral, arq))
    r = propostas["resumo"]
    log(f"Pronto em {time.time() - t0:.0f}s: presidente com {r['total']} propostas ({r['lei']} viraram lei, "
        f"{r['rejeitada']} rejeitadas/perderam a validade, {r['andando']} em discussão). Situações em {CE / 'situacoes.txt'}")


if __name__ == "__main__":
    main()
