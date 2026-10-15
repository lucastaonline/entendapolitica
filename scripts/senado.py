"""Senado Federal: os 81 senadores em exercício.

Gera dados/senado.json, dados/pessoas/sen-<código>.json e dados/votacoes/senado.json (contrato no README;
as votações ficam normalizadas: cada votação aparece uma vez em dados/votacoes/senado.json, com chave
"senado-vot:<codigoSessaoVotacao>", e o perfil guarda só "votos": [["senado-vot:7107", "Sim"], ...]).

Fontes oficiais (todas do Senado Federal):
- Ficha: Dados Abertos Legislativos /dadosabertos/senador/lista/atual, /senador/{código} (+ /mandatos,
  /comissoes, /profissao).
- Propostas: /dadosabertos/processo?codigoParlamentarAutor={código} (API nova de processos; a antiga
  /senador/{código}/autorias está DEPRECIADA desde 2025, com desativação marcada para 01/02/2026) e
  /dadosabertos/processo/{id} (autoria em ordem, assunto, apensamento, norma gerada, outros números).
  id das propostas = "senado:<codigoMateria>" (o "código da matéria", o mesmo da página
  https://www25.senado.leg.br/web/atividade/materias/-/materia/<codigoMateria>).
- Votações: /dadosabertos/votacao?dataInicio&dataFim (todas as votações do Plenário com o voto de cada um,
  em janelas de até 1 ano).
- Gastos (CEAPS): Dados Abertos Administrativos, adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/
  despesas_ceaps/{ano} (mesmos dados dos arquivos despesa_ceaps_{ano}.csv, mas com o código do senador).
- Situação na Câmara (só para propostas aprovadas no Senado cujo processo na Câmara já foi encerrado):
  API da Câmara dos Deputados.

Uso:  python scripts/senado.py [--ids 5672,825]

Cache em .cache/senado/. A 1ª execução baixa o detalhe de ~8 mil processos (demora ~40 min);
as seguintes só baixam o que mudou.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import os
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (CACHE, DADOS, PESSOAS, STATUS_TXT, TIPOS_PROPOSTA, aplicar_simples, baixar, carregar_simples,  # noqa: E402
                   chave_nome, classificar_situacao, data_iso, foto_local, fonte, hoje, ler_json, limpa, log,
                   ordenar_propostas, resumo_propostas, salvar_json, sem_acento, sem_mudar_data)

API = "https://legis.senado.leg.br/dadosabertos"
ADM = "https://adm.senado.gov.br/adm-dadosabertos/api/v1"
SITE = "https://www25.senado.leg.br/web"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
CS = CACHE / "senado"
DET = CS / "processo"
INICIO_LEG = "2023-02-01"          # início da legislatura atual (57ª): régua de votações e gastos
TIPOS = set(TIPOS_PROPOSTA) | {"PRN"}  # PRN = projeto de resolução do Congresso (equivalente ao PRS/PRC)
VEICULO = "Senado Federal"

for _p in (CS, DET):
    _p.mkdir(parents=True, exist_ok=True)

# Contorno: comum.baixar() não fecha a resposta quando a API devolve erro HTTP (HTTPError); no Python 3.14
# isso gera avisos "Exception ignored ... I/O operation on closed file" ao terminar. Só silencia esse aviso.
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
    se nada mais mudou, devolve o conteúdo antigo e salvar_json não reescreve o arquivo."""
    antigo = ler_json(caminho)
    if isinstance(antigo, dict) and _sem_datas(antigo) == _sem_datas(novo):
        return antigo
    return sem_mudar_data(novo, caminho)


# ---------------------------------------------------------------- rede (com freio: a API pede < 10 req/s)
_trava = threading.Lock()
_ultimo = [0.0]


def _respira(intervalo: float = 0.13):
    with _trava:
        espera = _ultimo[0] + intervalo - time.time()
        if espera > 0:
            time.sleep(espera)
        _ultimo[0] = time.time()


def _fresco(arq: Path, max_idade_h) -> bool:
    if not arq.exists() or arq.stat().st_size == 0:
        return False
    return max_idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < max_idade_h


def api(url: str, cache: str | None, max_idade_h=20, timeout: int = 300):
    """GET de JSON (Senado ou outra API) com cache em .cache/senado/<cache>."""
    if not url.startswith("http"):
        url = API + url
    destino = CS / cache if cache else None
    if destino is not None and _fresco(destino, max_idade_h):
        return json.loads(destino.read_bytes().decode("utf-8-sig"))
    _respira()
    b = baixar(url, destino, max_idade_h=0, headers={"Accept": "application/json"}, timeout=timeout)
    return json.loads(b.decode("utf-8-sig"))


def L(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def em_paralelo(funcao, itens, n: int = 4):
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(funcao, itens))


# ---------------------------------------------------------------- textos
def data_br(d: str | None) -> str | None:
    d = data_iso(d)
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if d else None


def url_materia(cod) -> str:
    return f"{SITE}/atividade/materias/-/materia/{cod}"


def url_senador(cod) -> str:
    return f"{SITE}/senadores/senador/-/perfil/{cod}"


def nome_norma(desc: str | None) -> tuple[str | None, str | None]:
    """'Lei nº 14.803 de 10/01/2024' -> ('Lei nº 14.803/2024', 'a'); devolve também o artigo (a/o)."""
    if not desc:
        return None, None
    m = re.match(r"\s*(.+?)\s+n[º°o]\.?\s*([\d\.]+)(?:[\-/][A-Z])?\s*(?:,?\s*de\s+\d{1,2}/\d{1,2}/(\d{4}))?", desc)
    if not m:
        return limpa(desc), "a"
    tipo, num, ano = m.groups()
    tipo = tipo.replace("Resolução do Senado Federal", "Resolução do Senado").replace(
        "Resolução do Congresso Nacional", "Resolução do Congresso")
    nome = f"{tipo} nº {num}" + (f"/{ano}" if ano else "")
    artigo = "o" if tipo.lower().startswith(("decreto", "ato")) else "a"
    return nome, artigo


# ---------------------------------------------------------------- senadores
def lista_atual() -> list[dict]:
    d = api("/senador/lista/atual.json", "lista_atual.json", 6)
    return L(d["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"])


def ficha(cod: str) -> dict:
    """Detalhe, mandatos, comissões e profissões de um senador."""
    det = api(f"/senador/{cod}.json", f"senador/{cod}.json", 20)["DetalheParlamentar"]["Parlamentar"]
    man = api(f"/senador/{cod}/mandatos.json", f"senador/{cod}_mandatos.json", 20)["MandatoParlamentar"]["Parlamentar"]
    com = api(f"/senador/{cod}/comissoes.json", f"senador/{cod}_comissoes.json", 20)["MembroComissaoParlamentar"]["Parlamentar"]
    pro = api(f"/senador/{cod}/profissao.json", f"senador/{cod}_profissao.json", 24 * 7)["HistoricoAcademicoParlamentar"]["Parlamentar"]
    return {"det": det, "mandatos": L((man.get("Mandatos") or {}).get("Mandato")),
            "comissoes": L((com.get("MembroComissoes") or {}).get("Comissao")),
            "profissoes": [limpa(p.get("NomeProfissao")) for p in L((pro.get("Profissoes") or {}).get("Profissao"))
                           if limpa(p.get("NomeProfissao"))]}


def exercicios(mandato: dict) -> list[dict]:
    return sorted(L((mandato.get("Exercicios") or {}).get("Exercicio")), key=lambda e: e.get("DataInicio") or "")


def mandato_atual(p: dict, fic: dict, titulares: dict) -> tuple[dict, list[dict]]:
    """Monta 'mandato' e 'mandatosAnteriores' (só mandatos no Senado; os da Câmara não estão nesta API)."""
    m = p["Mandato"]
    cod_m = m.get("CodigoMandato")
    ini = (m.get("PrimeiraLegislaturaDoMandato") or {}).get("DataInicio")
    fim = (m.get("SegundaLegislaturaDoMandato") or {}).get("DataFim") or (m.get("PrimeiraLegislaturaDoMandato") or {}).get("DataFim")
    part = m.get("DescricaoParticipacao") or ""
    genero = "F" if p["IdentificacaoParlamentar"].get("SexoParlamentar") == "Feminino" else "M"
    obs = None
    cheio = next((x for x in fic["mandatos"] if x.get("CodigoMandato") == cod_m), m)
    exs = exercicios(cheio) or exercicios(m)
    if "suplente" in part.lower():
        tit = cheio.get("Titular") or m.get("Titular") or {}
        nome_t = tit.get("NomeParlamentar")
        exs_validos = [e for e in exs if e.get("DataInicio")]
        if exs_validos:
            ini = exs_validos[0]["DataInicio"]  # suplente: conta desde que assumiu neste mandato
        info_t = titulares.get(tit.get("CodigoParlamentar")) or {}
        sig, data = info_t.get("sigla"), info_t.get("data")
        motivo = ""
        if sig == "REN":
            motivo = f", que renunciou ao mandato em {data_br(data)}"
        elif sig == "FAL":
            motivo = f", que faleceu em {_ano(data)}"
        elif sig in ("LCS", "LS", "LP", "LSP", "LPA", "LAP", "LG", "LA", "LAF", "LN", "LEG"):
            motivo = ", que está de licença"
        elif sig == "AFO":
            motivo = f", que está afastad{'a' if info_t.get('genero') == 'F' else 'o'} do mandato"
        elif sig:
            motivo = f" (motivo registrado pelo Senado: {info_t.get('descricao')})"
        if nome_t:
            obs = f"Suplente em exercício no lugar de {nome_t}{motivo}."
            if exs_validos and exs_validos[-1]["DataInicio"] != ini:
                obs += f" Voltou a exercer o mandato em {data_br(exs_validos[-1]['DataInicio'])}."
        else:
            obs = f"{part} em exercício."
    anteriores = []
    for x in fic["mandatos"]:
        if x.get("CodigoMandato") == cod_m or not x.get("DescricaoParticipacao"):
            continue
        exs_x = [e for e in exercicios(x) if e.get("DataInicio")]
        if not exs_x:
            continue  # suplente que nunca assumiu
        cargo = "Senadora" if genero == "F" else "Senador"
        if "suplente" in (x.get("DescricaoParticipacao") or "").lower():
            cargo = f"{cargo} (suplente em exercício)"
        if "suplente" in (x.get("DescricaoParticipacao") or "").lower():
            i, f = exs_x[0]["DataInicio"], exs_x[-1].get("DataFim")
        else:
            i = (x.get("PrimeiraLegislaturaDoMandato") or {}).get("DataInicio")
            f = (x.get("SegundaLegislaturaDoMandato") or {}).get("DataFim") or (x.get("PrimeiraLegislaturaDoMandato") or {}).get("DataFim")
        anteriores.append({"cargo": cargo, "inicio": i, "fim": f})
    anteriores.sort(key=lambda a: a["inicio"] or "", reverse=True)
    mand = {"inicio": ini, "fim": fim, "situacao": "Em exercício", "obs": obs,
            "fonte": fonte(VEICULO, "Dados Abertos: mandatos do senador", f"{API}/senador/{p['IdentificacaoParlamentar']['CodigoParlamentar']}/mandatos.json")}
    return mand, anteriores


def info_titular(cod_t: str) -> dict:
    """Último afastamento do titular (renúncia, falecimento, licença...)."""
    try:
        d = api(f"/senador/{cod_t}/mandatos.json", f"senador/{cod_t}_mandatos.json", 20)["MandatoParlamentar"]["Parlamentar"]
        det = api(f"/senador/{cod_t}.json", f"senador/{cod_t}.json", 24 * 7)["DetalheParlamentar"]["Parlamentar"]
    except Exception as e:  # noqa: BLE001
        log(f"  titular {cod_t}: {e}")
        return {}
    exs = []
    for m in L((d.get("Mandatos") or {}).get("Mandato")):
        exs += exercicios(m)
    exs = [e for e in exs if e.get("DataFim")]
    if not exs:
        return {}
    e = max(exs, key=lambda e: e["DataFim"])
    sexo = (det.get("IdentificacaoParlamentar") or {}).get("SexoParlamentar")
    return {"sigla": (e.get("SiglaCausaAfastamento") or "").strip(), "descricao": e.get("DescricaoCausaAfastamento"),
            "data": e.get("DataFim"), "genero": "F" if sexo == "Feminino" else "M"}


def comissoes_atuais(fic: dict) -> list[dict]:
    out, vistos = [], set()
    for c in fic["comissoes"]:
        if c.get("DataFim") and c["DataFim"] < hoje():
            continue
        ic = c.get("IdentificacaoComissao") or {}
        nome = limpa(ic.get("NomeComissao")) or ""
        if re.match(r"(Grupo Parlamentar|Frente Parlamentar|Comenda|Conselho d[aoe] (Comenda|Diploma|Prêmio|Projeto Jovem))", nome):
            continue  # grupos de amizade, frentes e conselhos de prêmios/homenagens não são comissões
        k = (ic.get("SiglaComissao"), c.get("DescricaoParticipacao"))
        if k in vistos:
            continue
        vistos.add(k)
        out.append({"sigla": ic.get("SiglaComissao"), "nome": nome, "papel": c.get("DescricaoParticipacao")})
    return sorted(out, key=lambda c: (chave_nome(c["nome"]), c["papel"] or ""))


# ---------------------------------------------------------------- processos (propostas)
def processos_do_autor(cod: str) -> list[dict]:
    return L(api(f"/processo.json?codigoParlamentarAutor={cod}", f"processos/{cod}.json", 20, timeout=600))


_IDX_ARQ = CS / "processo_idx.json"
_idx = ler_json(_IDX_ARQ, {}) or {}
_idx_trava = threading.Lock()
_baixados = [0]


def impressao(x: dict) -> str:
    return "|".join(str(x.get(k) or "") for k in ("situacaoAtual", "dataSituacaoAtual", "tramitando", "normaGerada",
                                                   "siglaTipoDeliberacao", "dataUltimaAtualizacao"))


def detalhe(x: dict) -> dict | None:
    """Detalhe do processo (cache .cache/senado/processo/<id>.json.gz). Baixa de novo se a situação mudou
    ou se o processo ainda tramita e o cache tem mais de 15 dias."""
    pid = str(x["id"])
    arq = DET / f"{pid}.json.gz"
    imp = impressao(x)
    if arq.exists():
        with _idx_trava:
            velho = _idx.setdefault(pid, imp)
        idade_d = (time.time() - arq.stat().st_mtime) / 86400
        if velho == imp and not (x.get("tramitando") == "Sim" and idade_d > 15):
            try:
                return json.loads(gzip.decompress(arq.read_bytes()))
            except Exception:  # noqa: BLE001 - cache corrompido: baixa de novo
                pass
    _respira()
    try:
        b = baixar(f"{API}/processo/{pid}.json", None, headers={"Accept": "application/json"}, timeout=120)
        d = json.loads(b)
    except Exception as e:  # noqa: BLE001
        log(f"  processo {pid}: {e}")
        return json.loads(gzip.decompress(arq.read_bytes())) if arq.exists() else None
    tmp = arq.with_suffix(".part")
    tmp.write_bytes(gzip.compress(b))
    os.replace(tmp, arq)
    with _idx_trava:
        _idx[pid] = imp
        _baixados[0] += 1
        if _baixados[0] % 500 == 0:
            salvar_json(_IDX_ARQ, _idx)
            log(f"  ... {_baixados[0]} detalhes de processos baixados")
    return d


def sigla_de(x: dict) -> str:
    return (x.get("identificacao") or "").split()[0] if x.get("identificacao") else ""


def autores(det: dict) -> tuple[list[dict], list[dict], str]:
    doc = det.get("documento") or {}
    return L(doc.get("autoria")), L(det.get("autoriaIniciativa")), doc.get("resumoAutoria") or ""


def papel_no_processo(det: dict | None, x: dict, cod: int, nomes: set[str]) -> str | None:
    """'autor' (1º autor), 'coautor' (assinou junto) ou None (não entra: proposta da época de deputado/a
    ou da Câmara). Usa a autoria estruturada do processo (campo 'ordem'); se faltar, o texto 'autoria'."""
    if det:
        aut, ini, resumo = autores(det)
        meus = [a for a in aut + ini if a.get("codigoParlamentar") == cod]
        if meus:
            papeis = {(a.get("siglaTipo") or "").upper() for a in meus}
            if all("DEPUTADO" in p for p in papeis):
                return None  # assinou como deputado(a) federal
            base = ini or aut

            def pos(a):
                i = resumo.find(a.get("autor") or "\0") if a.get("autor") else -1
                return i if i >= 0 else 10 ** 6
            primeiro = min(base, key=lambda a: (a.get("ordem") or 999, pos(a)))
            return "autor" if primeiro.get("codigoParlamentar") == cod else "coautor"
    a = x.get("autoria") or ""
    if not a.startswith(("Senador", "Senadora", "Líder", "Presidente do Senado")):
        return None
    m = re.match(r"(?:Senadora?|Líder d[oa] [^ ]+(?: [^ ]+)?|Presidente do Senado Federal: Senadora?)\s+(.+?)\s+\(", a)
    return "autor" if m and chave_nome(m.group(1)) in nomes else "coautor"


def apensado_a(det: dict | None) -> dict | None:
    for a in L((det or {}).get("apensadoA")):
        if not a.get("dataDesapensamento"):
            return a
    return None


def numero_camara(det: dict | None) -> list[dict]:
    return [o for o in L((det or {}).get("outrosNumeros")) if o.get("casaIdentificadora") == "CD"]


_cam_cache: dict = {}
_cam_trava = threading.Lock()
SIT_FINAL_CAMARA = ("lei", "arquivada", "rejeitada", "retirada")


def _final_nas_tramitacoes(pid) -> dict | None:
    """Última tramitação 'final' (arquivada, prejudicada, norma jurídica...) de uma proposição da Câmara.
    Usada quando o status atual da Câmara é um passo administrativo depois do fim (ex.: 'Devolução à CCP')."""
    try:
        t = L(api(f"{CAMARA_API}/proposicoes/{pid}/tramitacoes", f"camara/{pid}_tramitacoes.json", 24 * 7).get("dados"))
    except Exception as e:  # noqa: BLE001
        log(f"  Câmara tramitações {pid}: {e}")
        return None
    t.sort(key=lambda x: (x.get("dataHora") or "", x.get("sequencia") or 0))
    for x in reversed(t):
        desp = x.get("despacho") or ""
        if re.search(r"declarad[oa] prejudicad", desp, re.I):
            return {"situacao": "Prejudicada", "data": data_iso(x.get("dataHora")), "despacho": desp}
        if classificar_situacao(x.get("descricaoSituacao")) in SIT_FINAL_CAMARA:
            return {"situacao": limpa(x.get("descricaoSituacao")), "data": data_iso(x.get("dataHora")), "despacho": desp}
    return None


def situacao_na_camara(o: dict) -> dict | None:
    """Situação de uma proposta na Câmara (API da Câmara), pelo número que o Senado informa
    ('outrosNumeros'). Só é chamada quando o Senado diz que o processo na Câmara já não tramita."""
    sig, num, ano = o.get("sigla"), str(int(o.get("numero") or 0)), o.get("ano")
    chave = f"{sig}-{num}-{ano}"
    with _cam_trava:
        if chave in _cam_cache:
            return _cam_cache[chave]
    r = None
    try:
        q = urllib.parse.urlencode({"siglaTipo": sig, "numero": num, "ano": ano})
        lst = api(f"{CAMARA_API}/proposicoes?{q}", f"camara/busca-{chave}.json", 24 * 7)
        dados = lst.get("dados") or []
        if dados:
            pid = dados[0]["id"]
            det = api(f"{CAMARA_API}/proposicoes/{pid}", f"camara/{pid}.json", 24 * 3)["dados"]
            st = det.get("statusProposicao") or {}
            r = {"id": pid, "situacao": limpa(st.get("descricaoSituacao")), "data": data_iso(st.get("dataHora")),
                 "despacho": limpa(st.get("despacho")), "sigla": f"{sig} {num}/{ano}"}
            if classificar_situacao(r["situacao"]) not in SIT_FINAL_CAMARA:
                fim_ = _final_nas_tramitacoes(pid)
                if fim_:
                    r.update(fim_)
    except Exception as e:  # noqa: BLE001
        log(f"  Câmara {chave}: {e}")
    with _cam_trava:
        _cam_cache[chave] = r
    return r


def lei_da_norma(texto: str | None, det: dict | None) -> dict | None:
    ng = (det or {}).get("normaGerada") or {}
    nome, _ = nome_norma(ng.get("descricao") or texto)
    if not nome:
        return None
    url = f"https://legis.senado.leg.br/norma/{ng['codigo']}" if ng.get("codigo") else None
    return {"nome": nome, "url": url}


DELIB_NEG = {  # deliberações que encerram a proposta sem virar lei
    "PREJUDICADO": ("rejeitada", "Ficou prejudicada (não vai mais ser votada)"),
    "RETIRADO_PELO_AUTOR": ("retirada", "O autor desistiu e retirou a proposta"),
    "REJEITADO_PLENARIO": ("rejeitada", "Rejeitada pelo Plenário do Senado"),
    "REJEITADO_COMISSAO_TERM": ("rejeitada", "Rejeitada por uma comissão do Senado"),
    "REJEITADO_COMISSAO_NAO_TERM": ("rejeitada", "Rejeitada por uma comissão do Senado"),
    "REJEITADO_INCONSTICIONALIDADE_CCJ": ("rejeitada", "Rejeitada na CCJ do Senado por ir contra a Constituição"),
    "REJEITADO_PLENARIO_CD": ("rejeitada", "Rejeitada pelo Plenário da Câmara"),
    "SEM_EFICACIA": ("rejeitada", "Perdeu o efeito (ficou sem eficácia)"),
    "IMPUGNADO_PRESIDENCIA": ("rejeitada", "Devolvida pela Presidência do Senado (não pôde seguir)"),
    "RETIRADA_DE_ASSINATURA": ("rejeitada", "Não pôde seguir: assinaturas foram retiradas"),
    "PERDA_EFICACIA": ("rejeitada", "Perdeu a validade (o Congresso não votou a tempo)"),
    "INADIMITIDA_URGENCIA": ("rejeitada", "Não foi aceita pelo Congresso"),
    "TRANSF_PROJ_LEI_SEN": ("outra", "Foi transformada em outro projeto (projeto de lei do Senado)"),
    "TRANSF_PROJ_RES_SEN": ("outra", "Foi transformada em outro projeto (projeto de resolução do Senado)"),
    "TRANSF_IND": ("outra", "Foi transformada em indicação (sugestão ao governo)"),
    "REAUTUADO": ("outra", "Foi transformada em outro processo"),
    "REVOGADO": ("retirada", "Foi revogada (cancelada)"),
    "DEVOLVIDO_CD_ACAO_JUD": ("outra", "Devolvida à Câmara por decisão judicial"),
}



def _ano(d: str | None) -> str:
    return (d or "")[:4]


def classificar(x: dict, det: dict | None, cont: dict | None, det_cont: dict | None) -> dict:
    """Status, statusTxt, situação oficial, data e lei de uma proposta do Senado.
    Regras do Senado antes da regra comum (classificar_situacao):
    1) norma gerada => lei;  2) vetada => rejeitada;  3) aprovada no Senado => aprovada (vê a Câmara);
    4) processo encerrado => vale a deliberação;  5) tramitando => andando/junta;  6) regra comum."""
    S = limpa(x.get("situacaoAtual")) or ""
    Su = S.upper()
    D = x.get("siglaTipoDeliberacao") or ""
    T = x.get("tramitando")
    data_s = x.get("dataSituacaoAtual") or x.get("dataDeliberacao")
    r = {"status": None, "statusTxt": None, "situacao": S or None, "dataStatus": data_iso(data_s), "lei": None,
         "regra": None}

    def fim(status, txt, regra, **kw):
        r.update(status=status, statusTxt=txt, regra=regra, **kw)
        return r

    # 1) virou norma (lei, emenda constitucional, resolução, decreto legislativo)
    for proc, dproc in ((x, det), (cont, det_cont)):
        if proc and (proc.get("normaGerada") or ((dproc or {}).get("normaGerada") or {}).get("descricao")):
            lei = lei_da_norma(proc.get("normaGerada"), dproc)
            nome, artigo = nome_norma(((dproc or {}).get("normaGerada") or {}).get("descricao") or proc.get("normaGerada"))
            veto = " (com partes vetadas)" if "VETO PARCIAL" in (limpa(proc.get("situacaoAtual")) or "").upper() else ""
            ng = (dproc or {}).get("normaGerada") or {}
            dstat = data_iso(ng.get("dataAssinatura")) or data_iso(proc.get("dataSituacaoAtual")) or r["dataStatus"]
            sit = limpa(proc.get("situacaoAtual")) or r["situacao"]
            return fim("lei", f"Virou {artigo} {nome}{veto}", "norma gerada", lei=lei, dataStatus=dstat, situacao=sit)

    # continuação na Câmara (substitutivo/emendas da Câmara voltaram ao Senado)
    if cont is not None:
        Sc = (limpa(cont.get("situacaoAtual")) or "").upper()
        if Sc == "VETADA":
            return fim("rejeitada", "Aprovada pelo Congresso, mas vetada por inteiro pelo presidente", "continuação vetada",
                       situacao=limpa(cont.get("situacaoAtual")), dataStatus=data_iso(cont.get("dataSituacaoAtual")))
        if Sc.startswith("REMETIDA À SANÇÃO"):
            return fim("aprovada", "Aprovada pelo Congresso; esperando a sanção do presidente", "continuação na sanção",
                       situacao=limpa(cont.get("situacaoAtual")), dataStatus=data_iso(cont.get("dataSituacaoAtual")))
        if cont.get("tramitando") == "Sim":
            return fim("aprovada", "Aprovada no Senado e na Câmara (com mudanças); o Senado analisa as mudanças",
                       "continuação tramitando", situacao=limpa(cont.get("situacaoAtual")),
                       dataStatus=data_iso(cont.get("dataSituacaoAtual")))

    # 2) vetada por inteiro
    if Su == "VETADA":
        return fim("rejeitada", "Aprovada pelo Congresso, mas vetada por inteiro pelo presidente", "vetada")
    if Su.startswith("REMETIDA À SANÇÃO"):
        return fim("aprovada", "Aprovada pelo Congresso; esperando a sanção do presidente", "sanção")
    if Su.startswith("REMETIDA À PROMULGAÇÃO"):
        return fim("aprovada", "Aprovada; esperando ser promulgada", "promulgação")
    if Su == "ARQUIVADO NA CÂMARA DOS DEPUTADOS":
        return fim("arquivada", "Aprovada no Senado, mas arquivada na Câmara", "arquivada na Câmara")

    # 3) aprovada no Senado e enviada à Câmara
    aprovada_sf = Su in ("REMETIDA À CÂMARA DOS DEPUTADOS", "AGUARDANDO DECISÃO DA CÂMARA DOS DEPUTADOS") or (
        T == "Não" and D.startswith("APROVAD") and Su in ("APROVADA", "APROVADO O SUBSTITUTIVO", "APROVADA A MATÉRIA (DECISÃO TERMINATIVA)",
                                                         "APRECIADA EM DECISÃO TERMINATIVA PELAS COMISSÕES", "TRAMITAÇÃO ENCERRADA", ""))
    if aprovada_sf:
        if (D in DELIB_NEG or D == "ARQUIVADO_FIM_LEGISLATURA") and (x.get("dataDeliberacao") or "") > (x.get("dataSituacaoAtual") or ""):
            if D == "ARQUIVADO_FIM_LEGISLATURA":
                return fim("arquivada", f"Arquivada ao fim da legislatura em {_ano(x.get('dataDeliberacao'))}",
                           "deliberação mais nova que a situação", dataStatus=data_iso(x.get("dataDeliberacao")))
            st, txt = DELIB_NEG[D]
            return fim(st, txt, "deliberação mais nova que a situação", dataStatus=data_iso(x.get("dataDeliberacao")))
        cds = numero_camara(det)
        if any(o.get("tramitando") == "Sim" for o in cds):
            return fim("aprovada", "Aprovada no Senado; agora está na Câmara", "aprovada SF, tramita na CD")
        if cds:
            cam = situacao_na_camara(cds[0])
            if cam and cam.get("situacao"):
                stc = classificar_situacao(cam["situacao"])
                sit_c = f"Na Câmara: {cam['situacao']}"
                d_c = cam.get("data") or r["dataStatus"]
                if stc == "lei":
                    m = re.search(r"(Lei(?: Ordinária| Complementar)?|Emenda Constitucional)\s*(?:n[º°o]\.?\s*)?([\d\.]+)\s*/\s*(\d{4})",
                                  cam.get("despacho") or "")
                    lei, txt = None, "Aprovada no Senado e na Câmara; virou lei"
                    if m:
                        nome = f"{m.group(1).replace('Lei Ordinária', 'Lei')} nº {m.group(2)}/{m.group(3)}"
                        lei, txt = {"nome": nome, "url": None}, f"Virou a {nome}"
                    return fim("lei", txt, "Câmara: norma jurídica", lei=lei, dataStatus=d_c, situacao=sit_c)
                if stc == "rejeitada":
                    s_low = sem_acento(cam["situacao"].lower())
                    if "vetad" in s_low:
                        txt = "Aprovada pelo Congresso, mas vetada por inteiro pelo presidente"
                    elif "prejudicad" in s_low:
                        txt = "Aprovada no Senado, mas ficou prejudicada na Câmara"
                    else:
                        txt = "Aprovada no Senado, mas rejeitada na Câmara"
                    return fim("rejeitada", txt, "Câmara: rejeitada", dataStatus=d_c, situacao=sit_c)
                txts = {"arquivada": ("arquivada", "Aprovada no Senado, mas arquivada na Câmara"),
                        "retirada": ("retirada", "Aprovada no Senado, mas retirada na Câmara"),
                        "junta": ("aprovada", "Aprovada no Senado; na Câmara, anda junto com outra proposta"),
                        "andando": ("aprovada", "Aprovada no Senado; agora está na Câmara"),
                        "aprovada": ("aprovada", "Aprovada no Senado e na Câmara; ainda não virou lei")}
                if stc in txts:
                    return fim(txts[stc][0], txts[stc][1], "Câmara: " + stc, dataStatus=d_c, situacao=sit_c)
        quando = _ano(x.get("dataSituacaoAtual") or x.get("dataDeliberacao"))
        return fim("aprovada", f"Aprovada no Senado e enviada à Câmara em {quando}" if quando else
                   "Aprovada no Senado e enviada à Câmara", "aprovada SF sem dados da CD")

    # 4) processo encerrado: vale a deliberação (a data é a da situação atual, como na página do Senado)
    if T == "Não":
        if D == "ARQUIVADO_FIM_LEGISLATURA":
            return fim("arquivada", f"Arquivada ao fim da legislatura em {_ano(data_s)}",
                       "deliberação: fim da legislatura", situacao=S or "ARQUIVADA AO FINAL DA LEGISLATURA")
        if D in DELIB_NEG:
            st, txt = DELIB_NEG[D]
            return fim(st, txt, "deliberação", situacao=S or None)
        if "ARQUIVADA AO FINAL DA LEGISLATURA" in Su or "PREJUDICADA AO FINAL DA LEGISLATURA" in Su:
            return fim("arquivada", f"Arquivada ao fim da legislatura em {_ano(data_s)}", "situação: fim da legislatura")
        if Su in ("ARQUIVADA", "AO ARQUIVO"):
            return fim("arquivada", "Arquivada", "situação: arquivada")

    # 5) ainda tramitando no Senado
    if T == "Sim":
        ap = apensado_a(det)
        if ap:
            return fim("junta", f"Andando junto com outra proposta parecida ({ap.get('identificacao')})", "apensada",
                       situacao=S or "ANEXADA", dataStatus=data_iso(ap.get("dataApensamento")) or r["dataStatus"])
        return fim("andando", "Ainda em discussão no Senado", "tramitando")

    # 6) regra comum
    st = classificar_situacao(S or None)
    txt = {"rejeitada": "Rejeitada ou parada de vez", "arquivada": "Arquivada", "retirada": "O autor desistiu e retirou a proposta",
           "andando": "Ainda em discussão no Senado", "lei": NORMA_GENERICA.get(sigla_de(x), "Virou lei")}.get(st) or STATUS_TXT.get(st)
    if Su == "PREJUDICADA":
        txt = "Ficou prejudicada (não vai mais ser votada)"
    elif Su.startswith("REJEITADA"):
        txt = "Rejeitada no Senado"
    elif Su == "SEM EFICÁCIA":
        txt = "Perdeu o efeito (ficou sem eficácia)"
    return fim(st, txt, "regra comum")


# quando a situação diz que virou norma, mas a API não informa qual
NORMA_GENERICA = {"PEC": "Virou emenda à Constituição", "PRS": "Virou resolução do Senado", "PRN": "Virou resolução do Congresso",
                  "PDL": "Virou decreto legislativo", "PDS": "Virou decreto legislativo"}


def base_ident(ident: str) -> str:
    return re.sub(r"\s*\((Substitutivo|Emenda)s?-CD\)\s*$", "", ident or "").strip()


# Temas: classificação oficial do Senado ("classificacoes", em níveis: "Política Social / Saúde / Saúde Pública").
# Usamos o 2º nível ("Saúde"); nos 3 grupos muito largos abaixo, o 3º nível ("Mulheres", "Processo Penal",
# "Segurança Pública"). Processos antigos sem essa classificação usam o "assunto específico".
TEMA_DESCE = {"Proteção Social", "Processo", "Defesa do Estado e das Instituições Democráticas"}


def temas_do_processo(det: dict | None) -> list[str]:
    temas = []
    for cl in L((det or {}).get("classificacoes")):
        h = [limpa(x) for x in (cl.get("descricaoHierarquia") or cl.get("descricao") or "").split("/") if limpa(x)]
        if not h:
            continue
        t = h[1] if len(h) > 1 else h[0]
        if t in TEMA_DESCE and len(h) > 2:
            t = h[2]
        if t not in temas:
            temas.append(t)
    if not temas:
        c = (det or {}).get("conteudo") or {}
        t = limpa(c.get("assuntoEspecifico")) or limpa(c.get("assuntoGeral"))
        if t:
            temas.append(t[:1].upper() + t[1:])
    return sorted(temas, key=chave_nome)


def montar_propostas(cod: str, nome: str, nomes: set[str], genero: str, procs: list[dict], dets: dict,
                     simples: dict, registro: collections.Counter) -> dict:
    icod = int(cod)
    continuacoes = {}
    for x in procs:
        if re.search(r"\((Substitutivo|Emenda)s?-CD\)", x.get("identificacao") or ""):
            continuacoes.setdefault(base_ident(x["identificacao"]), []).append(x)
    lista, outros, vistos = [], collections.Counter(), set()
    for x in procs:
        sig = sigla_de(x)
        ident = x.get("identificacao") or ""
        if sig not in TIPOS:
            a = x.get("autoria") or ""
            if a.startswith(("Câmara dos Deputados", "Presidência da República", "Presidente da República")):
                continue
            if any(chave_nome(n) in nomes for n in re.findall(r"Deputad[oa] Federal\s+(.+?)\s*\(", a)):
                continue  # assinou como deputado(a) federal
            outros[sig] += 1
            continue
        if "(Substitutivo" in ident or "(Emenda" in ident or (x.get("autoria") or "").startswith("Câmara dos Deputados"):
            continue  # texto que veio da Câmara (não é proposta apresentada pelo/a senador/a)
        det = dets.get(x["id"])
        papel = papel_no_processo(det, x, icod, nomes)
        if papel is None:
            continue
        cm = x.get("codigoMateria")
        pid = f"senado:{cm or x['id']}"
        if pid in vistos:
            continue
        vistos.add(pid)
        conts = continuacoes.get(base_ident(ident)) or []
        cont = max(conts, key=lambda c: c.get("dataApresentacao") or "") if conts else None
        c = classificar(x, det, cont, dets.get(cont["id"]) if cont else None)
        registro[(c["situacao"] or "(sem situação)", x.get("siglaTipoDeliberacao") or "-", c["status"], c["regra"])] += 1
        lista.append({
            "id": pid,
            "sigla": ident,
            "tipo": sig,
            "data": data_iso(x.get("dataApresentacao")),
            "ementa": limpa(x.get("ementa")),
            "s": None,
            "status": c["status"],
            "statusTxt": c["statusTxt"],
            "situacao": c["situacao"],
            "dataStatus": c["dataStatus"],
            "papel": papel,
            "temas": temas_do_processo(det),
            "url": url_materia(cm) if cm else None,
            "lei": c["lei"],
        })
    aplicar_simples(lista, simples)
    lista = ordenar_propostas(lista)
    por_tema = collections.Counter(t for p in lista for t in p["temas"])
    a = "a" if genero == "F" else ""
    return {
        "escopo": f"Propostas apresentadas como senador{a}",
        "resumo": resumo_propostas(lista),
        "porTipo": dict(sorted(collections.Counter(p["tipo"] for p in lista).items())),
        "porTema": [{"tema": t, "n": n} for t, n in sorted(por_tema.items(), key=lambda kv: chave_nome(kv[0]))],
        "outros": {"total": sum(outros.values()), "porTipo": dict(sorted(outros.items())),
                   "url": f"{SITE}/atividade/materias/-/materia/autor/{cod}/p/1",
                   "txt": "Requerimentos, indicações, ofícios e outros pedidos (não são projetos de lei)"},
        "fonte": fonte(VEICULO, f"Matérias de autoria de {nome} (Dados Abertos: processos legislativos)",
                       f"{SITE}/atividade/materias/-/materia/autor/{cod}/p/1"),
        "lista": lista,
    }


# ---------------------------------------------------------------- votações
RESULTADO = {"A": "Aprovado", "R": "Rejeitado"}


def janelas_votacao() -> list[tuple[str, str, bool]]:
    ini = dt.date.fromisoformat(INICIO_LEG)
    hj = dt.date.fromisoformat(hoje())
    out = []
    while ini <= hj:
        fim_ = dt.date(ini.year + 1, ini.month, ini.day) - dt.timedelta(days=1)
        atual = fim_ >= hj
        out.append((ini.isoformat(), min(fim_, hj).isoformat(), atual))
        ini = fim_ + dt.timedelta(days=1)
    return out


def votacoes_plenario() -> tuple[dict, dict]:
    """Votações abertas do Plenário do Senado desde 01/02/2023.
    Devolve ({"senado-vot:<codigoSessaoVotacao>": detalhes}, {codigoParlamentar: [(idVotacao, voto)]})."""
    detalhes, por_sen = {}, collections.defaultdict(dict)
    for a, b, atual in janelas_votacao():
        cache = f"votacoes/{a}_atual.json" if atual else f"votacoes/{a}_{b}.json"
        d = L(api(f"/votacao.json?dataInicio={a}&dataFim={b}", cache, 20 if atual else 24 * 30, timeout=900))
        for v in d:
            if v.get("casaSessao") != "SF" or v.get("votacaoSecreta") != "N":
                continue  # só o Plenário do Senado e só votações abertas (nas secretas o voto não é divulgado)
            vid = f"senado-vot:{v.get('codigoSessaoVotacao')}"
            cm = v.get("codigoMateria")
            detalhes[vid] = {
                "data": data_iso(v.get("dataSessao")),
                "propostaId": f"senado:{cm}" if cm else None,
                "proposta": limpa(v.get("identificacao")),
                "descricao": limpa(v.get("descricaoVotacao")),
                "resultado": RESULTADO.get(v.get("resultadoVotacao")),
                "url": f"{url_materia(cm)}/votacoes" if cm else f"{SITE}/atividade/votacoes-nominais",
            }
            for voto in L(v.get("votos")):
                por_sen[voto.get("codigoParlamentar")].setdefault(vid, limpa(voto.get("siglaVotoParlamentar")))
    return detalhes, por_sen


def _chave_vot(vid: str, detalhes: dict):
    return (detalhes[vid]["data"] or "", int(re.sub(r"\D", "", vid) or 0))


def arquivo_votacoes(detalhes: dict, por_sen: dict) -> dict:
    """dados/votacoes/senado.json: cada votação uma vez só (os perfis guardam só [idVotacao, voto])."""
    ids = sorted(detalhes, key=lambda vid: _chave_vot(vid, detalhes), reverse=True)
    oficiais = {}
    try:
        tc = api("/plenario/lista/tiposComparecimento.json", "tipos_comparecimento.json", 24 * 30)
        for t in L(((tc.get("ListaTiposComparecimento") or {}).get("TiposComparecimento") or {}).get("TipoComparecimento")):
            oficiais[t.get("Sigla")] = limpa(t.get("Descricao"))
    except Exception as e:  # noqa: BLE001
        log(f"  tipos de comparecimento: {e}")
    usados = {voto for vs in por_sen.values() for voto in vs.values()} - {"Sim", "Não", "Abstenção", None}
    legenda = {}
    for cod in sorted(usados, key=chave_nome):
        if cod in oficiais:
            legenda[cod] = oficiais[cod]
        elif cod.startswith("Presidente"):
            legenda[cod] = "Presidia a sessão (art. 51 do Regimento Interno do Senado)"
    return {
        "atualizado": hoje(),
        "fonte": fonte(VEICULO, "Votações nominais do Plenário do Senado (Dados Abertos: /dadosabertos/votacao)",
                       f"{SITE}/atividade/votacoes-nominais"),
        "legenda": legenda,
        "votacoes": {vid: detalhes[vid] for vid in ids},
    }


def bloco_votacoes(votos: dict, detalhes: dict, nome_civil: str) -> dict:
    ids = sorted(votos, key=lambda vid: _chave_vot(vid, detalhes), reverse=True)
    resumo = {"total": len(ids), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
    for vid in ids:
        v = votos[vid]
        k = v if v in ("Sim", "Não", "Abstenção") else ("Obstrução" if v in ("P-OD", "OB", "Obstrução") else "Outro")
        resumo[k] += 1
    return {
        "escopo": "Votações abertas (com o voto de cada um) no Plenário do Senado desde fevereiro de 2023. "
                  "As votações secretas, como a escolha de autoridades, não entram: nelas o voto de cada um não é divulgado.",
        "resumo": resumo,
        "fonte": fonte(VEICULO, f"Votações nominais de {nome_civil}",
                       f"{SITE}/atividade/votacoes-nominais/-/v/parlamentar/{urllib.parse.quote(nome_civil)}"),
        "arquivo": "dados/votacoes/senado.json",
        "votos": [[vid, votos[vid]] for vid in ids],
    }


# ---------------------------------------------------------------- gastos (CEAPS)
def ceaps() -> tuple[dict, dict]:
    ano_atual = int(hoje()[:4])
    por = collections.defaultdict(lambda: {"ano": 0.0, "tipos": collections.defaultdict(float), "mandato": 0.0})
    meta = {"ano": ano_atual, "ultimoMes": None}
    for ano in range(int(INICIO_LEG[:4]), ano_atual + 1):
        d = L(api(f"{ADM}/senadores/despesas_ceaps/{ano}", f"ceaps/{ano}.json", 20 if ano == ano_atual else 24 * 30, timeout=900))
        for r in d:
            cod = str(r.get("codSenador") or "")
            try:
                valor = float(r.get("valorReembolsado") or 0)
                a, m = int(r.get("ano") or ano), int(r.get("mes") or 0)
            except (TypeError, ValueError):
                continue
            if not cod:
                continue
            if (a, m) >= (int(INICIO_LEG[:4]), int(INICIO_LEG[5:7])):
                por[cod]["mandato"] += valor
            if a == ano_atual:
                por[cod]["ano"] += valor
                tipo = limpa(r.get("tipoDespesa")) or "Outros"
                por[cod]["tipos"][tipo.rstrip(".")] += valor
                meta["ultimoMes"] = max(meta["ultimoMes"] or 0, m)
    return por, meta


MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def bloco_gastos(cod: str, nome: str, por: dict, meta: dict) -> dict:
    g = por.get(cod) or {"ano": 0.0, "tipos": {}, "mandato": 0.0}
    ano = meta["ano"]
    um = meta.get("ultimoMes")
    return {
        "ano": ano,
        "total": round(g["ano"], 2),
        "porTipo": [{"tipo": t, "valor": round(v, 2)} for t, v in sorted(g["tipos"].items(), key=lambda kv: chave_nome(kv[0]))],
        "mandatoTotal": round(g["mandato"], 2),
        "obs": (f"Cota para o exercício da atividade parlamentar (CEAPS): dinheiro devolvido ao senador por gastos do "
                f"mandato. {ano}: de janeiro a {MESES[um]} (último mês publicado). "
                f"\"mandatoTotal\": tudo desde fevereiro de {INICIO_LEG[:4]}, para todos do mesmo jeito.") if um else None,
        "fonte": fonte(VEICULO, f"Transparência: recursos utilizados por {nome} (CEAPS)",
                       f"https://www6g.senado.leg.br/transparencia/sen/{cod}/?ano={ano}"),
    }


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="só estes códigos de senador (separados por vírgula)")
    args = ap.parse_args()
    t0 = time.time()
    so = {s.strip() for s in (args.ids or "").split(",") if s.strip()}

    log("Senado: lista dos senadores em exercício")
    ps = lista_atual()
    log(f"  {len(ps)} senadores em exercício")
    alvo = [p for p in ps if not so or p["IdentificacaoParlamentar"]["CodigoParlamentar"] in so]

    log("Fichas, mandatos e comissões")
    fichas = dict(zip([p["IdentificacaoParlamentar"]["CodigoParlamentar"] for p in alvo],
                      em_paralelo(lambda p: ficha(p["IdentificacaoParlamentar"]["CodigoParlamentar"]), alvo)))
    cods_tit = sorted({(p["Mandato"].get("Titular") or {}).get("CodigoParlamentar") for p in alvo} - {None})
    titulares = dict(zip(cods_tit, em_paralelo(info_titular, cods_tit)))

    log("Propostas (processos legislativos de autoria de cada senador)")
    procs = dict(zip([p["IdentificacaoParlamentar"]["CodigoParlamentar"] for p in alvo],
                     em_paralelo(lambda p: processos_do_autor(p["IdentificacaoParlamentar"]["CodigoParlamentar"]), alvo)))
    precisa = {}
    for lst in procs.values():
        for x in lst:
            if sigla_de(x) in TIPOS and not (x.get("autoria") or "").startswith("Câmara dos Deputados") or \
                    re.search(r"\((Substitutivo|Emenda)s?-CD\)", x.get("identificacao") or ""):
                precisa[x["id"]] = x
    log(f"  {sum(len(v) for v in procs.values())} processos; {len(precisa)} propostas para detalhar")
    ids = sorted(precisa)
    dets = dict(zip(ids, em_paralelo(lambda i: detalhe(precisa[i]), ids, 5)))
    salvar_json(_IDX_ARQ, _idx)
    log(f"  detalhes prontos ({_baixados[0]} baixados agora)")

    log("Votações do Plenário (desde 01/02/2023)")
    det_vot, votos = votacoes_plenario()
    arq_vot = DADOS / "votacoes" / "senado.json"
    salvar_json(arq_vot, sem_mudar_datas(arquivo_votacoes(det_vot, votos), arq_vot))
    log(f"  {len(det_vot)} votações abertas -> {arq_vot.relative_to(DADOS.parent)}")

    log("Gastos (CEAPS)")
    gastos, meta_g = ceaps()
    log(f"  CEAPS {meta_g['ano']} até o mês {meta_g['ultimoMes']}")

    simples = carregar_simples()
    registro = collections.Counter()
    membros = []
    for p in alvo:
        ip, m = p["IdentificacaoParlamentar"], p["Mandato"]
        cod = ip["CodigoParlamentar"]
        fic = fichas[cod]
        det = fic["det"]
        nome = limpa(ip.get("NomeParlamentar"))
        nome_civil = limpa(ip.get("NomeCompletoParlamentar"))
        genero = "F" if ip.get("SexoParlamentar") == "Feminino" else "M" if ip.get("SexoParlamentar") == "Masculino" else None
        partido = limpa(ip.get("SiglaPartidoParlamentar"))
        if partido and partido.upper() in ("S/PARTIDO", "S/ PARTIDO", "SEM PARTIDO"):
            partido = "Sem partido"
        uf = ip.get("UfParlamentar")
        foto_url = (ip.get("UrlFotoParlamentar") or "").replace("http://", "https://") or None
        foto = foto_local(foto_url, f"sen-{cod}")
        mand, anteriores = mandato_atual(p, fic, titulares)
        nomes = {chave_nome(nome), chave_nome(nome_civil)}
        propostas = montar_propostas(cod, nome, nomes, genero, procs[cod], dets, simples, registro)
        dados_b = det.get("DadosBasicosParlamentar") or {}
        nat = limpa(dados_b.get("Naturalidade"))
        uf_nat = limpa(dados_b.get("UfNaturalidade"))
        id_ = f"sen-{cod}"
        site_p = (det.get("IdentificacaoParlamentar") or {}).get("UrlPaginaParticular")
        pessoa = {
            "id": id_,
            "tipo": "sen",
            "nome": nome,
            "nomeCivil": nome_civil,
            "cargo": "Senadora" if genero == "F" else "Senador",
            "genero": genero,
            "uf": uf,
            "municipio": None,
            "partido": partido,
            "foto": foto,
            "fotoCredito": "Senado Federal" if foto else None,
            "nascimento": data_iso(dados_b.get("DataNascimento")),
            "naturalidade": (f"{nat} ({uf_nat})" if nat and uf_nat else nat) or None,
            "escolaridade": None,
            "profissoes": fic["profissoes"],
            "mandato": mand,
            "mandatosAnteriores": anteriores,
            "eleicao": None,
            "eleicao2026": None,
            "bens": None,
            "links": {"oficial": url_senador(cod), "email": limpa(ip.get("EmailParlamentar")),
                      "redes": [site_p] if site_p else []},
            "comissoes": comissoes_atuais(fic),
            "propostas": propostas,
            "gastos": bloco_gastos(cod, nome, gastos, meta_g),
            "votacoes": bloco_votacoes(votos.get(int(cod), {}), det_vot, nome_civil or nome),
            "fontes": [
                fonte(VEICULO, f"Página oficial de {nome}", url_senador(cod)),
                fonte(VEICULO, "Dados Abertos Legislativos: senador", f"{API}/senador/{cod}.json"),
                fonte(VEICULO, "Dados Abertos Legislativos: processos de autoria",
                      f"{API}/processo.json?codigoParlamentarAutor={cod}"),
                fonte(VEICULO, "Dados Abertos Legislativos: votações do Plenário",
                      f"{API}/votacao.json?codigoParlamentar={cod}&dataInicio={INICIO_LEG}"),
                fonte(VEICULO, "Dados Abertos Administrativos: CEAPS",
                      f"{ADM}/senadores/despesas_ceaps/{meta_g['ano']}"),
            ],
            "atualizado": hoje(),
        }
        if any(str(p_.get("situacao") or "").startswith("Na Câmara:") for p_ in propostas["lista"]):
            pessoa["fontes"].append(fonte("Câmara dos Deputados", "Dados Abertos: situação na Câmara de propostas aprovadas no Senado",
                                          "https://dadosabertos.camara.leg.br/swagger/api.html"))
        arq = PESSOAS / f"{id_}.json"
        salvar_json(arq, sem_mudar_datas(pessoa, arq))
        membros.append({"id": id_, "nome": nome, "partido": partido, "uf": uf, "foto": foto, "genero": genero,
                        "fimMandato": mand["fim"], "eleicao2026": None})
        r = propostas["resumo"]
        log(f"  {id_} {nome}: {r['total']} propostas ({r['autor']} autor, {r['lei']} lei), "
            f"{len(pessoa['votacoes']['votos'])} votações, gastos {pessoa['gastos']['total']}")

    # relatório das situações (para conferir a classificação)
    linhas = ["situação oficial | deliberação | quantidade | status | regra"]
    for (sit, dl, st, rg), n in sorted(registro.items(), key=lambda kv: -kv[1]):
        linhas.append(f"{sit} | {dl} | {n} | {st} | {rg}")
    por_status = collections.Counter()
    for (sit, dl, st, rg), n in registro.items():
        por_status[st] += n
    linhas.append("")
    linhas.append("total por status: " + ", ".join(f"{k}={v}" for k, v in sorted(por_status.items())))
    (CS / "situacoes.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    if not so:
        membros.sort(key=lambda x: (chave_nome(x["nome"]), x["id"]))
        por_partido = collections.Counter(x["partido"] for x in membros)
        geral = {
            "total": len(membros),
            "porPartido": [{"partido": k, "n": v} for k, v in sorted(por_partido.items(), key=lambda kv: chave_nome(kv[0]))],
            "membros": membros,
            "fonte": fonte(VEICULO, "Dados Abertos: senadores em exercício", f"{API}/senador/lista/atual.json"),
            "atualizado": hoje(),
        }
        arq = DADOS / "senado.json"
        salvar_json(arq, sem_mudar_datas(geral, arq))
    log(f"Pronto: {len(membros)} senadores em {time.time() - t0:.0f}s. Situações em {CS / 'situacoes.txt'}")
    log("  status: " + ", ".join(f"{k}={v}" for k, v in sorted(por_status.items())))


if __name__ == "__main__":
    main()
