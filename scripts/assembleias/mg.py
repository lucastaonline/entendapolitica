"""Assembleia Legislativa de Minas Gerais (ALMG): Dados Abertos da ALMG (https://dadosabertos.almg.gov.br).

Lista: serviço "Deputados em exercício" da API (/api/v2/deputados/em_exercicio); nome completo, gênero e tipo de mandato
(efetivo ou suplente) vêm do registro de cada deputado na API. Página oficial: www.almg.gov.br/deputados/<nome>/<id>.
Foto: a da página oficial (www.almg.gov.br/export/sites/portal/a-assembleia/deputados/fotos/<id>.jpg).
robots.txt: dadosabertos.almg.gov.br deixa robôs lerem só /documentacao/, /api/ajuda/ e /api/v2/, e na API não deixa
paginar nem ordenar a pesquisa (p=, tp=, ord=, ordenacao=). Por isso os arquivos anuais (/arquivo/) não são mais
baixados e a pesquisa é lida só na 1ª página (20 itens).
Propostas: PL, PLC (= PLP), PEC e PRE (= PRC) publicados desde 1º/2/2023, mais os vetos (VET), em proposicoes.json:
a 1ª carga veio dos arquivos anuais que já estavam no cache; a cada rodada entram as novas (1ª página da pesquisa de
cada tipo no ano de hoje e os números seguintes ao maior conhecido, pesquisa por número) e cada proposição conhecida é
conferida pelo detalhe da API (/api/v2/proposicoes/<tipo>/<número>/<ano>) quando vence o prazo (_vence: 2 semanas;
1 mês se parada há mais de 3 meses; 4 meses se terminou), até ALMG_SEGUNDOS segundos por rodada (420). Sem os arquivos
anuais (o robô do GitHub começa com o cache vazio), a primeira carga procura número por número e lê o detalhe de cada
proposição, usando a rodada toda (_carga.py; uns 12 mil pedidos, alguns dias): enquanto ela não termina, nada vai para
dados/ (ficam os arquivos de antes). Autor
principal = o primeiro da lista de autores; os outros são coautores. Situação: o texto oficial com as regras REGRAS; a
norma (número da lei) vem do detalhe ("linkLegislacao") ou, para as ainda não conferidas, da pesquisa antiga (cache).
Gastos: verba indenizatória pela API de prestação de contas (um pedido por deputado e mês, desde fevereiro de 2023),
somada por ano e tipo de despesa. O arquivo CSV "Verbas indenizatórias" da ALMG não serve: vem com os valores em branco.
Meses fechados há mais de 4 meses ficam no cache para sempre; cada rodada baixa no máximo ALMG_VERBAS_MAX meses (160;
800 na primeira carga), os mais recentes primeiro. Enquanto faltam meses de alguém, fica o bloco de gastos da rodada anterior.
Votações nominais: a ALMG não publica o voto de cada deputado em formato aberto (só no texto das atas do Diário do
Legislativo); a API de reuniões de Plenário traz o resultado de cada votação, sem os votos. Por isso não entram.
A ALMG pede no máximo 2 pedidos ao mesmo tempo e 1 segundo entre um e outro: aqui é 1 por vez, com 1,1 s de pausa.
O governo do estado (perfil do governador, dados/pessoas/gov-MG.json), desde o começo do mandato ou do dia em que
quem governa assumiu: os projetos de lei, de lei complementar e as PEC sem deputado autor cujo autor, no detalhe da API
(/proposicoes/<tipo>/<número>/<ano>), é o Governador; as leis e leis complementares pela pesquisa oficial da Legislação
Mineira (por data); e os vetos pelas proposições VET (mensagens de veto), com "total" ou "parcial" no resumo.
"""
from __future__ import annotations

import ast
import csv
import datetime as _dt
import io
import json
import os
import re
import time

import regional
from comum import CACHE, PESSOAS, data_iso, hoje, ler_json, log, nome_proprio, sem_acento, slug

from . import _carga
from ._sse_comum import (Rede, SemTempo, bloco_executivo, bloco_gastos, casar_membros, com_status_en, desde, dia_rodizio,
                         escopo, escopo_governo, fonte, gravar, gravar_governo, legislatura, membro, nome_lei, partido_sigla,
                         periodo_governo, qtd, resumo_status, sem_html, virou)

UF = "MG"
API = "https://dadosabertos.almg.gov.br/api/v2"
CACHE_ALMG = CACHE / "almg"
SITE = "https://www.almg.gov.br"
VEICULO = "Assembleia Legislativa de Minas Gerais (ALMG)"
CASA = {"casa": "Assembleia Legislativa do Estado de Minas Gerais", "casa_en": "Legislative Assembly of the State of Minas Gerais",
        "sigla": "ALMG", "site": SITE,
        "sic": "https://www.almg.gov.br/apps/fale-com/assembleia"}  # pedido de informação (Lei de Acesso à Informação)
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
    em = {str(x["id"]): x for x in rede.json(f"{API}/deputados/em_exercicio?formato=json", "em_exercicio.json", 20)["list"]}
    if len(em) < 60:
        raise RuntimeError(f"ALMG: só {len(em)} deputados em exercício na API")
    pessoas, fichas = [], {}
    for i, e in sorted(em.items()):
        ficha = rede.json(f"{API}/deputados/{i}?formato=json", f"deputados/{i}.json", 20 if dia_rodizio(i) else 24 * 8)["deputado"]
        fichas[i] = ficha
        pessoas.append({"chave": i, "nome": e["nome"], "nomeCivil": nome_proprio(ficha.get("nomeServidor")),
                        "partido": partido_sigla(ficha.get("partidoEleicao") or e.get("partido"))})
    casados, avisos = casar_membros(UF, pessoas, MANUAL)
    membros, ids = [], {}
    for p in pessoas:
        i, ficha = p["chave"], fichas[p["chave"]]
        cand = casados.get(i)
        pid = regional.id_pessoa("dest", UF, cand, p["nome"])
        ids[i] = pid
        url = f"{SITE}/deputados/{slug(p['nome'])}/{i}"  # o mesmo endereço do arquivo "Deputados da atual legislatura"
        suplente = (ficha.get("tipoMandato") or "").lower().startswith("suplente")
        if not suplente and (cand or {}).get("sit") == "SUPLENTE":
            suplente = "vaga"  # suplente na eleição de 2022 que ficou com a vaga (a ALMG diz "Efetivo")
        membros.append(membro(pid, p["nome"], p["nomeCivil"], partido_sigla(em[i].get("partido")),
                              ficha.get("sexo") or (cand or {}).get("genero"),
                              f"{SITE}/export/sites/portal/a-assembleia/deputados/fotos/{i}.jpg", url, suplente))
        m = membros[-1]
        m["_email"] = next((x["endereco"] if "@" in x["endereco"] else x["endereco"] + "@almg.gov.br"
                            for x in ficha.get("emails") or [] if x.get("endereco")), None)
    return membros, ids, avisos


def _lista_api(v):
    """A pesquisa devolve listas e dicionários como texto ("[{'id': 28874, ...}]"); o detalhe, como JSON."""
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return None
    return v


def _linha(x: dict, hj: str) -> dict:
    """Item da API (pesquisa ou detalhe) -> linha com os nomes de campo do arquivo anual (os que o resto usa)."""
    aut = [a for a in _lista_api(x.get("autoresEstruturados")) or [] if isinstance(a, dict)]
    ln = _lista_api(x.get("linkLegislacao"))
    origem = next((m.group(0) for o in _lista_api(x.get("linksOrigem")) or [] if isinstance(o, dict)
                   for m in [re.match(r"\s*MSG\s+\d+\s+\d{4}", o.get("descricao") or "")] if m), None)
    return {"SiglaTipoProposicao": str(x.get("siglaTipoProjeto") or "").strip(), "Numero": str(x.get("numero") or "").strip(),
            "Ano": str(x.get("ano") or "").strip(), "DataPublicacao": x.get("dataPublicacao"),
            "DataUltimaAcao": x.get("dataUltimaAcao"), "Situacao": (x.get("situacao") or "").strip(),
            "Ementa": x.get("ementa"), "Resumo": x.get("resumo"),
            "Autores": json.dumps([{"id": a.get("id"), "nome": a.get("nome")} for a in aut], ensure_ascii=False),
            "AutorTexto": re.sub(r"\s+", " ", x.get("autor") or "").strip(), "Origem": origem.strip() if origem else None,
            "Norma": {k: ln.get(k) for k in ("tipo", "numero", "ano")} if isinstance(ln, dict) and ln.get("tipo") else None,
            "visto": hj}


def _semente() -> dict[str, dict]:
    """Primeira carga: os arquivos anuais de proposições que já estavam no cache (baixados antes de a regra do
    robots.txt valer aqui); daí em diante cada item é conferido pela API, um a um."""
    out = {}
    for arq in sorted(CACHE_ALMG.glob("proposicoes-*.csv")):
        visto = time.strftime("%Y-%m-%d", time.localtime(arq.stat().st_mtime))
        for l in _csv(arq.read_bytes()):
            sig = (l.get("SiglaTipoProposicao") or "").strip()
            if (sig in TIPOS or sig == "VET") and (data_iso(l.get("DataPublicacao")) or "") >= INICIO:
                out[f"{sig}-{l['Numero'].strip()}-{l['Ano'].strip()}"] = dict(l, visto=visto)
    return out


def _vence(l: dict) -> str:
    """Quando conferir de novo: as que terminaram, a cada 4 meses; as paradas há mais de 3 meses, a cada mês; as outras,
    a cada 2 semanas."""
    st = regional.proposta("x", "x", "PL", None, None, l.get("Situacao") or None, "", regras=REGRAS)["status"]
    ult = data_iso(l.get("DataUltimaAcao")) or data_iso(l.get("DataPublicacao")) or "2000-01-01"
    dias = 120 if st in ("lei", "rejeitada", "retirada", "arquivada", "junta") else 30 if ult < _dias_atras(90) else 14
    return (_dt.date.fromisoformat(l.get("visto") or "2000-01-01") + _dt.timedelta(days=dias)).isoformat()


def _dias_atras(n: int) -> str:
    return (_dt.date.fromisoformat(hoje()) - _dt.timedelta(days=n)).isoformat()


def _proposicoes(rede: Rede) -> list[dict]:
    """Proposições da legislatura (PL, PLC, PEC, PRE e os vetos, VET) pela API de Dados Abertos. O robots.txt da ALMG
    deixa robôs lerem a API, mas não paginar a pesquisa (p=, tp=, ord=) nem baixar os arquivos (/arquivo/): então, a
    cada rodada, (1) a 1ª página da pesquisa de cada tipo no ano de hoje (as 20 mais novas) e os números seguintes ao
    maior conhecido (pesquisa por número), e (2) o detalhe de cada proposição já conhecida, quando vence o prazo de
    conferir de novo (_vence), até ALMG_SEGUNDOS segundos (420). O resumo de cada uma fica em proposicoes.json."""
    hj, atual = hoje(), hoje()[:4]
    est = rede.estado("proposicoes.json", {}) or {}
    if est.get("inicio") != INICIO:  # legislatura nova: a numeração recomeça; o que é da anterior sai
        est = {"itens": {k: l for k, l in (est.get("itens") or {}).items()
                         if (data_iso(l.get("DataPublicacao")) or "") >= INICIO}, "sem": {}, "desce": {}}
    itens: dict[str, dict] = est.get("itens") or {}
    desce: dict[str, int] = est.get("desce") or {}  # próximo número a procurar, de cima para baixo, até o 1
    if not itens:
        itens = _semente()
        desce = {s: 0 for s in list(TIPOS) + ["VET"]} if itens else {}  # com os arquivos, não falta nenhum número
    sem: dict[str, str] = est.get("sem") or {}  # detalhe que voltou 404 (número que não existe naquele ano)
    # primeira carga (como no robô, que começa sem os arquivos anuais no cache): números por achar ou muitas proposições
    # ainda sem o detalhe. Aí o limite é a rodada toda (_carga.py) e nada vai para dados/ enquanto ela não termina.
    primeira = any(n > 0 for n in desce.values()) or not itens or \
        sum(1 for l in itens.values() if (l.get("visto") or "2000-01-01") <= "2000-01-01") > 0.01 * len(itens)
    t0 = time.time()
    limite = _carga.limite_diario(float(os.environ.get("ALMG_SEGUNDOS", "420")), primeira)

    def guarda(x: dict, detalhe: bool) -> None:
        l = _linha(x, hj)
        if not (l["SiglaTipoProposicao"] and l["Numero"] and l["Ano"] and (data_iso(l["DataPublicacao"]) or "") >= INICIO):
            return
        k = f"{l['SiglaTipoProposicao']}-{l['Numero']}-{l['Ano']}"
        if not detalhe:  # a pesquisa não traz resumo, norma nem origem: fica o que já se sabia, e o detalhe vem logo
            antes = itens.get(k) or {}
            for c in ("Resumo", "Norma", "Origem"):
                l[c] = antes.get(c)
            l["visto"] = antes.get("visto") or "2000-01-01"
        itens[k] = l

    def pesquisa(q: str, cache: str | None = None) -> list[dict]:
        d = rede.json(f"{API}/proposicoes/pesquisa/direcionada?{q}&formato=json", cache, 20)
        return (d.get("resultado") or {}).get("listaItem") or []

    vencidos, lidos = [], 0
    try:
        for sig in list(TIPOS) + ["VET"]:  # (1) as novas
            try:
                for x in pesquisa(f"tipo={sig}&ano={atual}", f"pesquisa/{sig}-{atual}.json"):
                    guarda(x, False)
                maior = max((int(k.split("-")[1]) for k, l in itens.items() if k.startswith(f"{sig}-") and k.split("-")[1].isdigit()
                             and (data_iso(l.get("DataPublicacao")) or "") >= INICIO), default=0)
                vazios, n = 0, maior + 1
                while vazios < 3 and time.time() - t0 < limite:  # mais de 20 num dia: segue pelo número
                    achou = [x for x in pesquisa(f"tipo={sig}&num={n}") if str(x.get("ano")) >= INICIO[:4]]
                    for x in achou:
                        guarda(x, False)
                    vazios = 0 if achou else vazios + 1
                    n += 1
                if sig not in desce:  # sem os arquivos: os números de baixo vêm aos poucos, um pedido por número
                    desce[sig] = min((int(k.split("-")[1]) for k in itens if k.startswith(f"{sig}-")), default=n) - 1
            except SemTempo:
                raise
            except Exception as e:  # um tipo fora do ar não derruba a coleta
                log(f"  MG: pesquisa de {sig}: {e}")
        vencidos = sorted((_vence(l), k) for k, l in itens.items() if _vence(l) <= hj)
        for _, k in vencidos:  # (2) a conferência dos já conhecidos, os mais atrasados primeiro
            if time.time() - t0 >= limite:
                break
            sig, num, ano = k.split("-")
            try:
                d = rede.json(f"{API}/proposicoes/{sig}/{num}/{ano}?formato=json", None)
                for x in (d.get("resultado") or {}).get("listaItem") or []:
                    guarda(x, True)
                lidos += 1
            except SemTempo:
                raise
            except Exception as e:
                if "404" in str(e):
                    sem[k] = hj
                    itens[k]["visto"] = hj
                else:
                    log(f"  MG: {sig} {num}/{ano}: {e}")
            if primeira and lidos % 200 == 0:  # primeira carga: o progresso fica guardado de tempos em tempos
                rede.guardar({"inicio": INICIO, "itens": itens, "sem": sem, "desce": desce}, "proposicoes.json")
        for sig in list(desce):  # (3) os números que faltam, de cima para baixo (só sem os arquivos da 1ª carga)
            while desce[sig] >= 1 and time.time() - t0 < limite:
                try:
                    for x in pesquisa(f"tipo={sig}&num={desce[sig]}"):
                        if str(x.get("ano")) >= INICIO[:4]:
                            guarda(x, False)
                except SemTempo:
                    raise
                except Exception as e:
                    log(f"  MG: pesquisa de {sig} {desce[sig]}: {e}")
                    break
                desce[sig] -= 1
                if desce[sig] % 200 == 0:
                    rede.guardar({"inicio": INICIO, "itens": itens, "sem": sem, "desce": desce}, "proposicoes.json")
    except SemTempo:  # o fim da rodada chegou: o que foi lido fica guardado
        pass
    if len(vencidos) > lidos:
        log(f"  MG: {len(vencidos) - lidos} proposições ficam para as próximas rodadas (conferência pela API)")
    faltam = sum(max(0, n) for n in desce.values())
    if faltam:
        log(f"  MG: {faltam} números de proposição ficam para as próximas rodadas (pesquisa por número)")
    rede.guardar({"inicio": INICIO, "itens": itens, "sem": sem, "desce": desce}, "proposicoes.json")
    sem_detalhe = sum(1 for l in itens.values() if (l.get("visto") or "2000-01-01") <= "2000-01-01")
    completo = not faltam and bool(itens) and sem_detalhe <= 0.01 * len(itens)
    return [l for k, l in itens.items() if k not in sem and (data_iso(l.get("DataPublicacao")) or "") >= INICIO], completo


def _leis(rede: Rede, ini: str) -> tuple[dict[str, int], str | None]:
    """Leis (grupo 9) e leis complementares (grupo 10) de ini até hoje, pela pesquisa oficial da Legislação Mineira
    ("N artigos encontrados"), e a data da mais recente (a pesquisa vem em ordem de data decrescente)."""
    total, ultima = {}, None
    for grupo, nome in (("9", "Lei"), ("10", "Lei Complementar")):
        t = rede.texto(f"{SITE}/atividade-parlamentar/leis/legislacao-mineira/?pesquisou=true&grupo={grupo}"
                       f"&dataInicio={ini}&dataFim={hoje()}&ordem=0", f"leis-{grupo}.html", 20)
        txt = sem_html(t) or ""
        m = re.search(r"([\d.]+)\s+artigos?\s+encontrad", txt)
        if not m and "Nenhum" not in txt:
            raise RuntimeError(f"ALMG: a pesquisa de legislação ({nome}) não trouxe o total")
        total[nome] = int(m.group(1).replace(".", "")) if m else 0
        d = re.search(r"\b(?:Lei|Lei Complementar) nº [\d.]+, de (\d{2})/(\d{2})/(\d{4})", txt)
        if d:
            ultima = max(ultima or "", f"{d.group(3)}-{d.group(2)}-{d.group(1)}")
    return total, ultima


def _autor_api(rede: Rede, l: dict) -> tuple[str, str | None]:
    """(autor, ano da mensagem de origem) de uma proposição sem deputado na lista de autores (Governador, Tribunal de
    Justiça...), pelo registro da API (lido uma vez: não muda). A origem é a mensagem que trouxe o projeto ("MSG 260
    2026")."""
    autor = l.get("AutorTexto")
    if autor and (l.get("Origem") or not re.search(r"(?i)governador", autor)):
        m = re.match(r"\s*MSG\s+\d+\s+(\d{4})", l.get("Origem") or "")
        return autor, m.group(1) if m else None
    sig, num, ano = l["SiglaTipoProposicao"].strip(), l["Numero"].strip(), l["Ano"].strip()
    try:
        d = rede.json(f"{API}/proposicoes/{sig}/{num}/{ano}?formato=json", f"proposicoes/detalhe/{sig}-{num}-{ano}.json", None)
    except SemTempo:  # o fim da rodada chegou: o perfil do governador fica como estava
        raise
    except Exception as e:  # uma proposição fora do ar não derruba a coleta (fica de fora nesta rodada)
        log(f"  MG: {sig} {num}/{ano}: {e}")
        return "", None
    item = ((d.get("resultado") or {}).get("listaItem") or [{}])[0]
    origem = next((m.group(1) for o in item.get("linksOrigem") or []
                   for m in [re.match(r"\s*MSG\s+\d+\s+(\d{4})", o.get("descricao") or "")] if m), None)
    return (item.get("autor") or "").strip(), origem


def _normas(rede: Rede, linhas: list[dict]) -> dict[str, dict]:
    """{"PL 123/2023": {"nome": "Lei nº 24.567/2023", "url": ...}}: a norma que o detalhe da API dá para cada proposição;
    para as que ainda não foram conferidas por ele, a pesquisa de proposições transformadas em norma da rodada anterior
    (normas.json, no cache; a pesquisa paginada não é mais feita: o robots.txt fecha a paginação para robôs)."""
    out = dict(rede.estado("normas.json") or {})
    for l in linhas:
        n = l.get("Norma")
        if n and n.get("tipo") and n.get("numero"):
            tipo = NORMAS.get(n["tipo"]) or "Norma"
            out[f"{l['SiglaTipoProposicao']} {l['Numero']}/{l['Ano']}"] = {
                "nome": nome_lei(tipo, n.get("numero"), n.get("ano")),
                "url": f"{SITE}/legislacao-mineira/{n['tipo']}/{n['numero']}/{n['ano']}/"}
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
    try:
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
    except SemTempo:  # sem tempo nesta rodada: os blocos de gastos de antes continuam
        return {}, set()
    if len(pedidos) > 3 * limite:  # primeira carga (cache vazio): mais meses por rodada (~15 min, 1,1 s entre pedidos)
        limite = max(limite, 800)
    pedidos.sort(reverse=True)  # os meses mais recentes primeiro
    feitos = set()
    for m, i, cache, ttl in pedidos[:limite]:
        try:
            rede.json(f"{API}/prestacao_contas/verbas_indenizatorias/deputados/{i}/{int(m[:4])}/{int(m[5:])}?formato=json",
                      cache, ttl)
            feitos.add(cache)
        except SemTempo:
            break
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
    gastos, completos = _gastos(rede, ids)  # antes das propostas: na primeira carga, as duas andam a cada rodada
    linhas, completo = _proposicoes(rede)
    if not completo:  # primeira carga em andamento: nada pela metade no site (ficam os arquivos de antes)
        log(f"  MG: primeira carga das proposições em andamento ({len(linhas)} lidas); os arquivos de antes continuam; "
            f"{rede.pedidos} pedidos à rede")
        return _carga.pendente(CASA["sigla"], f"primeira carga: {len(linhas)} proposições lidas", rede.pedidos)
    normas = _normas(rede, linhas)
    hj = hoje()
    f_lista = fonte(VEICULO, "Dados Abertos: API de deputados (deputados em exercício e o registro de cada um)",
                    f"{API}/deputados/em_exercicio?formato=json", hj)
    f_prop = fonte(VEICULO, "Dados Abertos: API de proposições (pesquisa e detalhe de cada proposição)",
                   "https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest#/", hj)
    por_dep: dict[str, list] = {}
    for l in linhas:
        if l["SiglaTipoProposicao"].strip() not in TIPOS:
            continue
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
    try:
        # o governo: projetos do Governador do Estado, leis do período (pesquisa da Legislação Mineira) e vetos (VET)
        per = periodo_governo(UF)
        governo = []
        for l in linhas:
            if l["SiglaTipoProposicao"].strip() in TIPOS and not _autores(l.get("Autores")) and \
                    (data_iso(l.get("DataPublicacao")) or "") >= per["inicio"]:
                autor, origem = _autor_api(rede, l)
                # mensagem de um ano anterior ao começo do período (ex.: PL 3.334/2025, da MSG 187/2025, lida só em maio
                # de 2026) é do governo anterior
                if re.search(r"(?i)governador", autor) and (origem or "9999") >= per["inicio"][:4]:
                    governo.append(_proposta(l, "autor", normas))
        vetos = sorted((l for l in linhas if l["SiglaTipoProposicao"].strip() == "VET"
                        and (data_iso(l.get("DataPublicacao")) or "") >= per["inicio"]), key=lambda l: data_iso(l.get("DataPublicacao")))
        totais = sum(1 for l in vetos if re.match(r"(?i)\s*veto total", l.get("Resumo") or ""))
        parciais = sum(1 for l in vetos if re.match(r"(?i)\s*veto parcial", l.get("Resumo") or ""))
        tot_leis, ultima_lei = _leis(rede, per["inicio"])
        d_pt, d_en = desde(per["inicio"])
        n_l, n_lc, sem = tot_leis["Lei"], tot_leis["Lei Complementar"], len(vetos) - totais - parciais
        v_pt = f"{qtd(totais, 'total', 'totais')} e {qtd(parciais, 'parcial', 'parciais')}" + (
            f"; {sem} sem a indicação no resumo" if sem else "")
        v_en = f"{totais} full and {parciais} partial" + (f"; {sem} without that information in the summary" if sem else "")
        esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                               "Na ALMG, o autor desses projetos aparece como \"Governador do Estado\"; a data é a da publicação. "
                               "Projetos de mensagens de anos anteriores, lidos só agora, ficam de fora.",
                               "At the ALMG, the author of these bills is listed as the state governor; the date is the "
                               "publication date. Bills from messages of earlier years, read only now, are left out.")
        executivo = bloco_executivo(
            per, [fonte(VEICULO, "Legislação Mineira: pesquisa de leis e leis complementares por data",
                        f"{SITE}/atividade-parlamentar/leis/legislacao-mineira/?pesquisou=true&grupo=9&dataInicio={per['inicio']}"
                        f"&dataFim={hj}&ordem=0", hj),
                  fonte(VEICULO, "Dados Abertos: API de proposições (mensagens de veto do governo, tipo VET)",
                        "https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest#/", hj)],
            f"Leis: {qtd(n_l, 'lei', 'leis')} e {qtd(n_lc, 'lei complementar', 'leis complementares')} desde {d_pt}, pela "
            "pesquisa oficial da Legislação Mineira (data da lei). A pesquisa não separa as poucas leis promulgadas pela própria "
            "Assembleia (quando ela derruba um veto ou o governador não responde no prazo): elas estão na conta. Vetos: as "
            f"mensagens de veto publicadas pela ALMG no período (proposições do tipo VET), {v_pt}.",
            f"Laws: {qtd(n_l, 'law', 'laws')} and {qtd(n_lc, 'complementary law', 'complementary laws')} since {d_en}, from the "
            "official search of Minas Gerais legislation (by the law's date). The search does not single out the few laws "
            "promulgated by the Assembly itself (when it overrides a veto or the governor does not answer in time): they are "
            f"included. Vetoes: the veto messages published by the ALMG in the period, {v_en}.",
            leis=sum(tot_leis.values()), vetos=len(vetos), vetos_totais=None if sem else totais,
            vetos_parciais=None if sem else parciais, ultima_lei=ultima_lei,
            ultimo_veto=data_iso(vetos[-1].get("DataPublicacao")) if vetos else None)
        gravar_governo(UF, per, governo, *esc_g, f_prop, executivo)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  MG: governo: {e}")
    notas = [("A ALMG não publica o voto de cada deputado em formato aberto (só no texto das atas, no Diário do Legislativo).",
              "The ALMG does not publish each deputy's vote in an open format (only in the text of the minutes, in its official gazette).")]
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": True},
                  f_lista, esc_pt, esc_en, notas)
