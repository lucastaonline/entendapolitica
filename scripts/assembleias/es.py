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
segundos (150). O que já foi lido fica no cache e é atualizado quando o rodízio passa de novo. Enquanto o rodízio não
deu a primeira volta inteira (cache vazio, como no robô do GitHub), ele usa a rodada toda (_carga.py) e nada é gravado
em dados/ (ficam os arquivos de antes; "em andamento").
Situação: "Tramitando", "Apensado" ou "Arquivado", com a tramitação para separar (regras em _situacao): sanção do
governador, publicação da norma ou "Compilar Norma" = virou lei; "Publicar Ato Normativo" = decreto legislativo ou
resolução publicado (virou norma); "Posicionamento do Governador" sem decisão registrada = aprovado e enviado ao
governador.
Votações nominais: a Ales publica "Boletins de Votação Nominal" como documentos (PDF); não entram.
Gastos: a cota parlamentar de cada gabinete (Ato da Mesa nº 6.226/2025), pela tabela "Cotas Parlamentares" do Portal da
Transparência (www.al.es.gov.br/Transparencia/CotasParlamentares): o "Valor Solicitado" de cada tipo de despesa (diárias
e passagens aéreas do deputado e da equipe do gabinete e, desde 2024, o reembolso de despesas como aluguel, divulgação e
consultorias; em 2023 e 2024 também telefone, material, cópias, periódicos e postagens, e em 2023, combustível), de um
gabinete num período de meses de um ano (página HTML; sem nenhum registro, "Nenhuma despesa encontrada"):
GET /Transparencia/Api/CotasParlamentaresNovoTable/<mês inicial>/<mês final>/<ano>/<gabinete>/false.
Os gabinetes de hoje ("Gab. Dep. <nome>") vêm de /Transparencia/SetoresAtivosDiv, a lista que a página usa, e são
ligados aos deputados da lista oficial pelo nome (_votos_gastos.Nomes). Desde 1º/2/2023 (o mês 1 de 2023 é da
legislatura anterior e não entra), com poucos pedidos: cada ano fechado num pedido só; o ano mostrado (o mais recente com
gasto, quase sempre o ano corrente) mês a mês, para saber os meses; e, no primeiro ano com gasto, os meses do começo até
o primeiro com gasto (o "desde"). O sufixo "solicitadas pelo Gabinete" do nome do tipo sai (a tabela toda é do valor
solicitado); "Devolução de diária" entra com valor negativo. A Ales publica cada mês até o fim do mês seguinte (art. 20
do Ato) e pode acertar o que já publicou (art. 21): o mês passado é relido todo dia, o corrente e os três antes do
passado uma vez por semana, os outros a cada três meses (rodízio). Primeira carga (cache vazio, como no robô do
GitHub): ~450 pedidos (~12 min), no resto da rodada (_carga.py); enquanto falta alguma tabela, os perfis ficam com o
bloco de gastos de antes (nada pela metade).
O governo do estado (perfil do governador, dados/pessoas/gov-ES.json), desde o começo do mandato ou do dia em que quem
governa assumiu: os projetos do autor "GOVERNADOR DO ESTADO" (código 972 no SPL; GET /proposicao/?autorID=972&tipoID=..);
as leis ordinárias e complementares do cadastro de legislação (GET /legislacao?tipo=3|4&ano=..), cada uma com o detalhe
(GET /legislacao/<id>: sancionada ou promulgada e o projeto de origem, que também marca "virou lei" nas propostas); e os
vetos, pelas mensagens de veto (MV, GET /proposicao/?tipoID=2), com "VETO TOTAL" ou "VETO PARCIAL" no resumo.
"""
from __future__ import annotations

import os
import re
import time

import regional
from comum import data_iso, hoje, log, sem_acento

from ._sse_comum import (Rede, SemTempo, bloco_executivo, bloco_gastos, casar_membros, com_status_en, desde, dia_rodizio,
                         escopo, escopo_governo, fonte, gravar, gravar_governo, legislatura, membro, nome_lei, partido_sigla,
                         periodo_governo, qtd, resumo_status, sem_html, virou)
from ._votos_gastos import Nomes, aplicar, de_antes, valor_br
from . import _carga

UF = "ES"
SITE = "https://www.al.es.gov.br"
API = "https://www3.al.es.gov.br/api/publico"
TRANSP = f"{SITE}/Transparencia"
COTAS = f"{TRANSP}/CotasParlamentares"  # a página das cotas (escolha o gabinete e os meses)
VEICULO = "Assembleia Legislativa do Estado do Espírito Santo (Ales)"
CASA = {"casa": "Assembleia Legislativa do Estado do Espírito Santo", "casa_en": "Legislative Assembly of the State of Espírito Santo",
        "sigla": "Ales", "site": SITE,
        "sic": "https://esic.al.es.gov.br/sistema/site/index.html"}  # pedido de informação (Lei de Acesso à Informação)
INICIO = legislatura(UF)["inicio"]
TIPOS = {"PL": "PL", "PLC": "PLP", "PEC": "PEC", "PDL": "PDL", "PR": "PRC"}
POR_PAGINA = 50
GOVERNADOR = "972"  # autor "GOVERNADOR DO ESTADO" no SPL
TIPO_ID = {"PL": 5, "PLC": 4, "PEC": 3}  # tipoID da API para os projetos do governador
LEI_TIPO = {3: "Lei", 4: "Lei Complementar"}  # tipo da API de legislação
# mensagens de veto cujo resumo não diz se o veto é total ou parcial, conferidas no documento oficial (PDF)
VETO_MANUAL = {"495545": "total"}  # MV 22/2026 (Mensagem 181/2026): "VETO TOTAL ao Autógrafo de Lei nº 198/2026"
NOME_GASTOS = ("Cota parlamentar do gabinete (valor solicitado)", "Office allowance (cota parlamentar; amount requested by the office)")
GASTOS_S = 240  # limite diário (s) da leitura das cotas (ALES_GASTOS_SEGUNDOS); a primeira carga usa o resto da rodada
# gabinetes da lista das cotas cujo nome não bate sozinho com a lista oficial: {nome como a Ales escreve: id ou "-"}
# (conferido à mão; em 26/10/2026 os 30 gabinetes ligaram sozinhos, ex.: "Gab. Dep. Fabrício Gandini" = Gandini)
GABINETES_MANUAL: dict[str, str] = {}

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


def _proposicoes(rede: Rede) -> tuple[dict, bool]:
    """(itens, completo): o que já foi lido das proposições e se o cache já tem todas as janelas (tipo e ano) completas:
    o número de proposições guardadas bate com o total que a API dá para a janela (98%), ou a janela foi lida inteira
    desde a última mudança do total. Enquanto falta alguma (cache vazio, como no robô do GitHub, ou páginas que deram
    erro), as janelas incompletas são lidas inteiras, usando a rodada toda (_carga.py); depois, o rodízio de sempre."""
    est = rede.estado("estado.json", {}) or {}
    itens, cursor = est.get("itens", {}), est.get("cursor", 0)
    lidas: dict = est.get("lidas", {})  # janela -> total da API quando ela foi lida inteira
    atual = int(hoje()[:4])
    total = est.get("total", {})
    t0 = time.time()

    def guarda(dados: list) -> None:
        for x in dados:
            r = _resumo(x)
            if r["id"]:
                itens[str(r["id"])] = r

    def ler(sig, ano, pag):
        k = f"{sig}-{ano}"
        dados, t = _lote(rede, f"{API}/proposicao/?sigla={sig}&ano={ano}", pag, POR_PAGINA, int(total.get(k) or 0))
        if t:  # total 0 ("Nenhum Registro encontrado" num dia ruim) não apaga o total conhecido
            total[k] = t
        guarda(dados)

    def incompletas() -> list[tuple[str, int]]:
        c: dict[str, int] = {}
        for x in itens.values():
            k = f"{(x.get('sigla') or '').strip().upper()}-{x.get('ano')}"
            c[k] = c.get(k, 0) + 1
        return [(sig, ano) for sig in TIPOS for ano in range(int(INICIO[:4]), atual + 1)
                if (t := int(total.get(f"{sig}-{ano}") or 0)) and c.get(f"{sig}-{ano}", 0) < 0.98 * t
                and lidas.get(f"{sig}-{ano}") != t]

    def salvar():
        rede.guardar({"itens": itens, "cursor": cursor, "total": total, "lidas": lidas}, "estado.json")

    try:
        for sig in TIPOS:  # as novas (primeira página de cada tipo no ano de hoje) e os anos ainda sem total conhecido
            for ano in range(int(INICIO[:4]), atual + 1):
                if ano == atual or not total.get(f"{sig}-{ano}"):  # total 0 = resposta vazia de um dia ruim: lê de novo
                    ler(sig, ano, 1)
        faltam = incompletas()
        if faltam:  # primeira carga (ou janelas com páginas que falharam): as janelas incompletas, inteiras
            limite = _carga.limite_diario(0, True)
            for sig, ano in faltam:
                paginas = max(1, -(-int(total.get(f"{sig}-{ano}") or 0) // POR_PAGINA))
                erros = 0
                for pag in range(1, paginas + 1):
                    if time.time() - t0 > limite:
                        break
                    try:
                        ler(sig, ano, pag)
                    except SemTempo:
                        raise
                    except Exception as e:
                        erros += 1
                        log(f"  ES: {sig} {ano} página {pag}: {e}")
                else:
                    if not erros:
                        lidas[f"{sig}-{ano}"] = int(total.get(f"{sig}-{ano}") or 0)
                salvar()
        else:  # todo dia: o rodízio por todas as páginas, até ALES_SEGUNDOS
            limite = float(os.environ.get("ALES_SEGUNDOS", "150"))
            blocos = []  # (tipo, ano, página) de todo o período, para o rodízio
            for sig in TIPOS:
                for ano in range(int(INICIO[:4]), atual + 1):
                    paginas = max(1, -(-int(total.get(f"{sig}-{ano}") or 0) // POR_PAGINA))
                    blocos += [(sig, ano, p) for p in range(1, paginas + 1)]
            while blocos and time.time() - t0 < limite:
                sig, ano, pag = blocos[cursor % len(blocos)]
                try:
                    ler(sig, ano, pag)
                except SemTempo:
                    raise
                except Exception as e:
                    log(f"  ES: {sig} {ano} página {pag}: {e}")
                cursor = (cursor + 1) % len(blocos)
                if cursor == 0:
                    break
    except SemTempo:  # o fim da rodada chegou: o que foi lido fica guardado
        pass
    salvar()
    faltam = incompletas()
    if faltam:
        log(f"  ES: janelas (tipo-ano) ainda incompletas: {', '.join(f'{s}-{a}' for s, a in faltam)}")
    return itens, not faltam


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


def _lote(rede: Rede, url: str, pag: int, qtd: int, total: int = 0) -> tuple[list[dict], int]:
    """(itens, total) de uma página de uma lista da API. Quando uma proposição da página tem defeito, a API devolve
    {"erro": true, "mensagem": "Nullable object must have a value."} no lugar da página inteira, sem o total (conferido
    em 26/10/2026: páginas 2, 7, 8, 9 e 14 dos PL de 2023): aí a página é relida em pedaços de 10 e cada pedaço ainda
    quebrado, um por um (só o item com defeito fica fora). total: o da lista, se já se sabe (para não pedir além do fim).
    Lista vazia não é erro: a API responde "Nenhum Registro encontrado", com total 0."""
    d = rede.json(f"{url}&pag={pag}&qtd={qtd}", None, timeout=300) or {}
    if not d.get("erro"):
        return d.get("Data") or [], int(d.get("total") or 0)
    out, quebrados, q = [], [], 10
    primeiro = (pag - 1) * qtd  # posição (a partir de 0) do primeiro item da página
    for sub in range(primeiro // q + 1, (primeiro + qtd) // q + 1):
        if total and (sub - 1) * q >= total:
            break
        ds = rede.json(f"{url}&pag={sub}&qtd={q}", None, timeout=300) or {}
        if ds.get("erro"):
            quebrados.append(sub)  # lido depois, um por um (até lá, outro pedaço pode dar o total)
            continue
        total = int(ds.get("total") or total)
        out += ds.get("Data") or []
    for sub in quebrados:
        for um in range((sub - 1) * q + 1, sub * q + 1):
            if total and um > total:
                break
            d1 = rede.json(f"{url}&pag={um}&qtd=1", None, timeout=300) or {}
            if d1.get("erro"):
                continue  # o item com defeito
            if not d1.get("Data"):
                break  # passou do fim
            total = int(d1.get("total") or total)
            out += d1["Data"]
    return out, total


def _ate(rede: Rede, url: str, ini: str, qtd: int = 40) -> list[dict]:
    """Lista de proposições da mais nova para a mais antiga, página a página, até passar de ini."""
    out, pag = [], 1
    while True:
        lote, total = _lote(rede, url, pag, qtd)  # páginas grandes às vezes dão erro na Ales
        out += lote
        if not lote or (total and pag * qtd >= total) or min(data_iso(x.get("data")) or "" for x in lote) < ini:
            return out
        pag += 1


def _governo(rede: Rede, ini: str) -> list[dict]:
    """Projetos do governador (autor 972) apresentados de ini em diante, por tipo e ano. Como em _proposicoes, só o
    resumo de cada um fica guardado (uma leitura por dia)."""
    est = rede.estado("governo.json", {}) or {}
    if est.get("dia") == hoje() and est.get("desde") == ini:
        return est.get("itens") or []
    itens = {}
    for tid in TIPO_ID.values():
        for ano in range(int(ini[:4]), int(hoje()[:4]) + 1):
            for x in _ate(rede, f"{API}/proposicao/?autorID={GOVERNADOR}&tipoID={tid}&ano={ano}", ini):
                r = _resumo(x)
                if r["id"] and (r["data"] or "") >= ini:
                    itens[str(r["id"])] = r
    lista = sorted(itens.values(), key=lambda x: x["data"])
    rede.guardar({"dia": hoje(), "desde": ini, "itens": lista}, "governo.json")
    return lista


def _leis(rede: Rede, ini: str) -> tuple[list[dict], int]:
    """Leis ordinárias e complementares de ini até hoje no cadastro de legislação da Ales, cada uma com o detalhe
    (sancionada ou promulgada e o projeto de origem), guardado de vez. Um registro com número menor que o de uma lei do
    mesmo tipo de antes de ini é erro de cadastro (conferido: "10.906" de 06/07/2026 é a Lei 12.906, que também está lá;
    a LC 1.145 "de 04/04/2026" é de 4 de março) e fica fora. Devolve (leis, registros fora)."""
    atual, hj = int(hoje()[:4]), hoje()
    out, fora = [], 0
    for tid, nome in LEI_TIPO.items():
        regs = []
        for ano in range(int(ini[:4]), atual + 1):
            pag = 1
            while True:
                d = rede.json(f"{API}/legislacao?pag={pag}&qtd=500&tipo={tid}&ano={ano}", f"leis/{tid}-{ano}-{pag}.json",
                              20 if ano == atual else 24 * 7, timeout=300)
                regs += d.get("Data") or []
                if pag * 500 >= int(d.get("total") or 0):
                    break
                pag += 1
        antes = max((int(x["numero"]) for x in regs if str(x.get("numero") or "").isdigit()
                     and (data_iso(x.get("data")) or "") < ini), default=0)
        vistos = set()
        for x in sorted(regs, key=lambda x: data_iso(x.get("data")) or ""):
            dt, n = data_iso(x.get("data")) or "", str(x.get("numero") or "")
            if not (ini <= dt <= hj) or not n.isdigit():
                continue
            if int(n) < antes or n in vistos:
                fora += 1
                continue
            vistos.add(n)
            modo, prop = None, None
            try:
                det = rede.json(f"{API}/legislacao/{x['id']}", f"legislacao/{x['id']}.json", None, timeout=120)
                det = det.get("Data") if isinstance(det, dict) and "Data" in det else det
                if isinstance(det, list):
                    det = det[0] if det else {}
                modo = (det.get("modoValor") or "").strip() or None
                prop = str((det.get("ProposicaoOriginal") or {}).get("proposicaoId") or "") or None
            except SemTempo:  # o fim da rodada chegou: nada pela metade (o perfil do governador fica como estava)
                raise
            except Exception as e:
                log(f"  ES: detalhe da {nome} {n}: {e}")
            prom = (modo or "").lower().startswith("promulg") if modo else bool(
                re.search(r"promulgad[ao]\.?\s*$", (x.get("ementa") or "").strip(), re.I))
            out.append({"tipo": nome, "numero": n, "ano": dt[:4], "data": dt, "promulgada": prom, "proposicao": prop,
                        "url": x.get("arquivoHtml") or None})
    return out, fora


def _vetos(rede: Rede, ini: str) -> list[dict]:
    """Mensagens de veto (MV) do governador que chegaram à Assembleia de ini em diante (só o resumo fica guardado)."""
    est = rede.estado("vetos.json", {}) or {}
    if est.get("dia") == hoje() and est.get("desde") == ini:
        return est.get("itens") or []
    lista = []
    for x in _ate(rede, f"{API}/proposicao/?tipoID=2", ini):
        dt = data_iso(x.get("data")) or ""
        if dt < ini or str((x.get("AutorRequerenteDados") or {}).get("autorId") or "") != GOVERNADOR:
            continue
        txt = sem_acento((x.get("assunto") or "").upper())
        tipo = ("total" if re.search(r"VETO\s+TOTAL", txt) else "parcial" if re.search(r"VETO\s+PARCIAL", txt)
                else VETO_MANUAL.get(str(x.get("id"))))
        if not tipo:
            log(f"  ES: veto MV {x.get('numero')} ({dt}) sem 'total' ou 'parcial' no resumo; confira o PDF e ponha em VETO_MANUAL")
        lista.append({"id": str(x.get("id")), "numero": x.get("numero"), "data": dt, "tipo": tipo})
    lista.sort(key=lambda v: v["data"])
    rede.guardar({"dia": hoje(), "desde": ini, "itens": lista}, "vetos.json")
    return lista


# ---------------------------------------------------------------- gastos: a cota parlamentar de cada gabinete
def _validade(chave: str, idade: int) -> float:
    """Horas de validade de uma tabela guardada, pela idade (em meses) do último mês que ela cobre. A Ales publica cada mês
    até o fim do mês seguinte (Ato da Mesa nº 6.226/2025, art. 20) e pode acertar o que já publicou (art. 21): o mês
    passado é relido todo dia; o mês corrente e os três antes do passado, uma vez por semana; os outros, a cada três
    meses (cada tabela no seu dia, para espalhar os pedidos)."""
    if idade == 1:
        return 20
    if idade <= 4:
        return 20 if dia_rodizio(chave, 7) else 24 * 8
    return 20 if dia_rodizio(chave, 91) else 24 * 100


def _tipo_gasto(txt: str) -> str:
    """'Diárias solicitadas pelo Gabinete' -> 'Diárias' (a tabela toda é do valor solicitado pelo gabinete)."""
    t = re.sub(r"\s+", " ", txt or "").strip()
    return re.sub(r"(?i)\s+solicitad[ao]s pelo gabinete$", "", t) or "Outros"


def _tabela_cotas(t: str) -> dict:
    """A tabela "Cotas Parlamentares" (#table-grid) de um gabinete num período: {"linhas": [[tipo, valor]], "total"}, só
    as linhas com valor. Linhas: Produto, Quantidade, Valor Solicitado; "Reembolso das Despesas" é um título de seção, e
    "Total:" fecha a tabela. Sem nenhum registro no período, a Ales responde "Nenhuma despesa encontrada"."""
    if "Nenhuma despesa encontrada" in t:
        return {"linhas": [], "total": 0.0}
    tab = re.search(r'<table id="table-grid".*?</table>', t, re.S)
    if not tab:
        raise RuntimeError("a resposta não tem a tabela das cotas (#table-grid)")
    linhas, total = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab.group(0), re.S):
        tds = [sem_html(x) or "" for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) == 2 and tds[0].startswith("Total"):
            total = valor_br(tds[1])
        elif len(tds) == 3 and tds[0]:
            tipo, v = _tipo_gasto(tds[0]), valor_br(tds[2])
            if re.match(r"(?i)devolu", tipo):  # devolução de diária: diminui o gasto (a Ales mostra o valor negativo)
                v = -abs(v)
            if v:
                linhas.append([tipo, round(v, 2)])
    if total is None:
        raise RuntimeError("a tabela das cotas veio sem a linha do total")
    return {"linhas": linhas, "total": total}


def _gabinetes(rede: Rede) -> list[list[str]]:
    """[[código, nome]] dos gabinetes dos deputados de hoje ("Gab. Dep. Adilson Espindula"), a lista da página das cotas
    (sem "Todos os Deputados"); guardada por 20 h (se a Ales não responder, vale a última que veio)."""
    if rede.fresco("gabinetes.json", 20):
        return rede.estado("gabinetes.json")
    try:
        t = rede.texto(f"{TRANSP}/SetoresAtivosDiv", None)
        gabs = [[c, sem_html(n) or ""] for c, n in re.findall(r'<option value="(\d+)"[^>]*>(.*?)</option>', t, re.S) if c != "0"]
        if not 25 <= len(gabs) <= 35:
            raise RuntimeError(f"a lista de gabinetes veio com {len(gabs)} itens")
    except SemTempo:
        raise
    except Exception as e:
        antes = rede.estado("gabinetes.json")
        if not antes:
            raise
        log(f"  ES: cotas: lista de gabinetes sem resposta ({e}); vale a da última vez")
        return antes
    rede.guardar(gabs, "gabinetes.json")
    return gabs


def _gastos(membros: list[dict]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} pela tabela "Cotas Parlamentares" de cada gabinete (ver o começo do arquivo), ou None
    enquanto a primeira carga não terminou (os perfis ficam com o bloco de antes). Cada tabela lida fica no cache
    (.cache/ales-gastos/<gabinete>/<ano>-<mês>[-<mês final>].json, só os totais por tipo), e a carga continua de onde
    parou na rodada seguinte."""
    rede = Rede("ales-gastos", pausa=1.0, timeout=60)
    t0, hj = time.time(), hoje()
    atual, mes = int(hj[:4]), int(hj[5:7])
    a0 = int(INICIO[:4])

    def ini(ano: int) -> int:  # o primeiro mês de um ano que conta (em 2023, fevereiro: janeiro é da legislatura anterior)
        return int(INICIO[5:7]) if ano == a0 else 1

    def arq(cod: str, ano: int, a: int, b: int) -> str:
        return f"{cod}/{ano}-{a:02d}" + ("" if a == b else f"-{b:02d}") + ".json"

    def url(cod: str, ano: int, a: int, b: int) -> str:
        return f"{TRANSP}/Api/CotasParlamentaresNovoTable/{a}/{b}/{ano}/{cod}/false"

    nomes = Nomes(membros, GABINETES_MANUAL, prefixo=r"^\s*gab(inete)?\.?\s*(d[oa]\s+)?dep(utad[oa])?\.?\s+")
    por_pid: dict[str, list[str]] = {}
    for cod, nome in _gabinetes(rede):
        pid = nomes.quem(nome)
        if pid:
            por_pid.setdefault(pid, []).append(cod)
    nomes.avisar(UF, "cotas parlamentares (gabinetes)")
    for pid, cods in por_pid.items():
        if len(cods) > 1:
            log(f"  ES: cotas: os gabinetes {cods} caíram na mesma pessoa ({pid}); sem ligação")
    liga = {cods[0]: pid for pid, cods in por_pid.items() if len(cods) == 1}
    sem = [m["nome"] for m in membros if m["id"] not in liga.values()]
    if sem:
        log(f"  ES: cotas: deputados sem gabinete ligado (fica o bloco de antes, se houver): {sem}")

    est = rede.estado("estado.json", {}) or {}
    completa = bool(est.get("completa")) and est.get("inicio") == INICIO
    fixos = [arq(c, y, ini(y), 12) for c in liga for y in range(a0, atual)] + \
            [arq(c, atual, k, k) for c in liga for k in range(ini(atual), mes + 1)]
    primeira = not completa or any(not rede.caminho(n).exists() for n in fixos)
    limite = _carga.limite_diario(float(os.environ.get("ALES_GASTOS_SEGUNDOS", GASTOS_S)), primeira)
    ctl = {"parar": False, "erros": 0, "faltam": 0}

    def tabela(cod: str, ano: int, a: int, b: int) -> dict | None:
        """A tabela de um gabinete de a/ano a b/ano: do cache, se ainda vale; senão, da Ales (se ainda há tempo nesta
        rodada); se não deu, a guardada antes (mesmo velha). None = nunca lida (falta)."""
        nome = arq(cod, ano, a, b)
        idade = (atual - ano) * 12 + mes - b
        if rede.fresco(nome, _validade(nome, idade if a == b else max(idade, 2))):
            return rede.estado(nome)
        if not ctl["parar"] and time.time() - t0 < limite:
            try:
                d = _tabela_cotas(rede.texto(url(cod, ano, a, b), None))
                soma = round(sum(v for _, v in d["linhas"]), 2)
                if abs(soma - d["total"]) > 0.01:
                    log(f"  ES: cotas do gabinete {cod} ({a}/{ano} a {b}/{ano}): a soma das linhas ({soma}) não bate com o "
                        f"total da página ({d['total']}); confira")
                rede.guardar(d, nome)
                ctl["erros"] = 0
                return d
            except SemTempo:
                ctl["parar"] = True
            except Exception as e:
                ctl["erros"] += 1
                log(f"  ES: cotas do gabinete {cod} ({a}/{ano} a {b}/{ano}): {e}")
                if ctl["erros"] >= 3:
                    ctl["parar"] = True
                    log("  ES: cotas: três erros seguidos; o resto fica para a próxima rodada")
        d = rede.estado(nome)
        if d is None:
            ctl["faltam"] += 1
        return d

    def gasto(d: dict | None) -> float:
        return sum(v for _, v in (d or {}).get("linhas") or [] if v > 0)

    blocos: dict[str, dict] = {}
    incompletos: list[str] = []
    for cod, pid in liga.items():
        antes = ctl["faltam"]
        anos = {y: tabela(cod, y, ini(y), 12) for y in range(a0, atual)}  # anos fechados: um pedido por ano
        meses = {(atual, k): tabela(cod, atual, k, k) for k in range(ini(atual), mes + 1)}  # o ano corrente, mês a mês
        if ctl["faltam"] > antes:
            incompletos.append(pid)
            continue
        # o ano mostrado: o mais recente com gasto (quase sempre o corrente); se for um ano fechado, ele também mês a mês
        ys = atual if any(gasto(d) for d in meses.values()) else max((y for y, d in anos.items() if gasto(d)), default=None)
        if ys is None:
            continue  # nenhum gasto desde o começo da legislatura: sem bloco
        if ys != atual:
            meses.update({(ys, k): tabela(cod, ys, k, k) for k in range(ini(ys), 13)})
        # o primeiro ano com gasto: se for outro, os meses dele do começo até o primeiro com gasto (o "desde")
        y0 = min([y for y, d in anos.items() if gasto(d)] + [ys])
        prim = None
        if y0 != ys:
            for k in range(ini(y0), 13):
                d = tabela(cod, y0, k, k)
                if d is None or gasto(d):
                    prim = f"{y0}-{k:02d}" if d else None
                    break
        if ctl["faltam"] > antes:
            incompletos.append(pid)
            continue
        if y0 != ys and not prim:
            log(f"  ES: cotas do gabinete {cod}: {y0} tem gasto no ano, mas em nenhum mês; o \"desde\" fica no começo do ano")
            prim = f"{y0}-{ini(y0):02d}"
        linhas = [(f"{y}-{k:02d}", t, v) for (y, k), d in meses.items() if y == ys for t, v in d["linhas"]]
        for y, d in anos.items():
            if y < ys:  # depois do ano mostrado não há gasto (no máximo uma devolução, que não muda o ano mostrado)
                linhas += [(prim if y == y0 else f"{y}-{ini(y):02d}", t, v) for t, v in d["linhas"]]
        nome = next(m["nome"] for m in membros if m["id"] == pid)
        b = bloco_gastos(linhas, fonte(VEICULO, f"Cotas Parlamentares do gabinete de {nome} em {ys} (Portal da Transparência)",
                                       url(cod, ys, ini(ys), 12), hj), INICIO, NOME_GASTOS)
        if b:
            blocos[pid] = b
    s = time.time() - t0
    if incompletos:
        if not completa:  # primeira carga: nada pela metade (os perfis ficam com o bloco de antes)
            log(f"  ES: primeira carga das cotas parlamentares em andamento: faltam {ctl['faltam']}+ tabelas de "
                f"{len(incompletos)} dos {len(liga)} gabinetes; a carga continua na próxima rodada; {rede.pedidos} pedidos em {s:.0f} s")
            return None
        log(f"  ES: cotas: {len(incompletos)} gabinetes com tabelas por ler (fica o bloco de antes deles)")
    elif not completa:
        rede.guardar({"completa": True, "inicio": INICIO}, "estado.json")
    for m in membros:  # sem gabinete ligado ou com tabelas por ler: fica o bloco de antes, se houver
        if m["id"] in incompletos or m["id"] not in liga.values():
            b = de_antes(m["id"], "gastos")
            if b and (b.get("desde") or "") >= INICIO[:7]:
                blocos[m["id"]] = b
    log(f"  ES: cotas parlamentares: {len(blocos)} perfis com gastos ({len(liga)} gabinetes ligados); "
        f"{rede.pedidos} pedidos à rede em {s:.0f} s")
    return blocos


def coletar() -> dict:
    rede = Rede("ales", pausa=1.0)
    membros, ids, autores, avisos = _membros(rede)
    for a in avisos:
        log(f"  ES: {a}")
    itens, completo = _proposicoes(rede)
    if not completo:  # primeira carga em andamento: nada pela metade no site (ficam os arquivos de antes)
        log(f"  ES: primeira carga das proposições em andamento ({len(itens)} lidas); os arquivos de antes continuam; "
            f"{rede.pedidos} pedidos à rede")
        return _carga.pendente(CASA["sigla"], f"primeira carga: {len(itens)} proposições lidas", rede.pedidos)
    hj = hoje()
    per = periodo_governo(UF)
    try:
        leis, fora = _leis(rede, per["inicio"])
    except Exception as e:  # o cadastro de legislação fora do ar: as propostas seguem, sem o "virou lei" que vem dele
        log(f"  ES: cadastro de legislação: {e}")
        leis, fora = None, 0
    lei_de = {l["proposicao"]: l for l in leis or [] if l["proposicao"]}  # projeto de origem -> lei (detalhe de cada lei)

    def proposta(x: dict, papel: str) -> dict:
        sig = (x.get("sigla") or "").strip().upper()
        st, extra = _situacao(x)
        lei = lei_de.get(str(x["id"]))
        if lei:
            st, extra = "lei", None
        p = regional.proposta(f"ales:{x['id']}", f"{sig} {x.get('numero')}/{x.get('ano')}", TIPOS[sig], x.get("data"),
                              x.get("ementa"), (x.get("situacao") or "").strip() or None,
                              x.get("arquivo") or "https://www3.al.es.gov.br/spl/", papel=papel, status=st)
        if lei:
            virou(p, nome_lei(lei["tipo"], lei["numero"], lei["ano"]), lei["url"])
        elif st == "lei" and extra == "parcial":
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
        return p

    por_dep: dict[str, list] = {}
    for x in itens.values():
        sig = (x.get("sigla") or "").strip().upper()
        if sig not in TIPOS or (x.get("data") or "") < INICIO:
            continue
        quem = [autores[a] for a in dict.fromkeys([x.get("autor")] + (x.get("coautores") or [])) if a in autores]
        for k in quem:
            por_dep.setdefault(k, []).append(proposta(x, "autor" if autores.get(x.get("autor")) == k else "coautor"))
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
    try:
        # o governo do estado: projetos do governador, leis sancionadas (cadastro de legislação) e mensagens de veto
        if leis is None:
            raise RuntimeError("cadastro de legislação sem resposta")
        governo = [proposta(x, "autor") for x in _governo(rede, per["inicio"]) if (x.get("sigla") or "").upper() in TIPOS]
        vetos = _vetos(rede, per["inicio"])
        sanc = sorted((l for l in leis if not l["promulgada"]), key=lambda l: l["data"])
        n_ord, n_prom = sum(1 for l in sanc if l["tipo"] == "Lei"), sum(1 for l in leis if l["promulgada"])
        tot, par = sum(1 for v in vetos if v["tipo"] == "total"), sum(1 for v in vetos if v["tipo"] == "parcial")
        sem = len(vetos) - tot - par
        v_pt = f"{qtd(tot, 'total', 'totais')} e {qtd(par, 'parcial', 'parciais')}" + (f"; {sem} sem a indicação no resumo" if sem else "")
        v_en = f"{tot} full and {par} partial" + (f"; {sem} without that information in the summary" if sem else "")
        d_pt, d_en = desde(per["inicio"])
        esc_g = escopo_governo(UF, per, "Assembleia Legislativa", "Legislative Assembly", ("PL", "PLP", "PEC"),
                               "Na Ales, o autor desses projetos aparece como \"Governador do Estado\". O link de cada um abre "
                               "o documento oficial (PDF).",
                               "At the Ales, the author of these bills is listed as the state governor. "
                               "Each link opens the official document (PDF).")
        f_gov = [fonte(VEICULO, "Dados Abertos: API pública de proposições (autor: Governador do Estado)",
                       "https://www3.al.es.gov.br/dados-abertos.aspx", hj),
                 fonte(VEICULO, "Consulta de proposições no Sistema de Processo Legislativo (SPL)", "https://www3.al.es.gov.br/spl/", hj)]
        prom_pt = ("as promulgadas pela própria Assembleia ficam de fora (" + qtd(n_prom, "lei", "leis") + ")") if n_prom else \
            "nenhuma foi promulgada pela própria Assembleia"
        prom_en = (f"the laws promulgated by the Assembly itself are left out ({qtd(n_prom, 'law', 'laws')})") if n_prom else \
            "none was promulgated by the Assembly itself"
        fora_pt = (f"; {'um registro' if fora == 1 else str(fora) + ' registros'} com número ou data errados no cadastro "
                   f"({'fica' if fora == 1 else 'ficam'} fora)") if fora else ""
        fora_en = (f"; {'one record' if fora == 1 else str(fora) + ' records'} with a wrong number or date in the register "
                   f"{'is' if fora == 1 else 'are'} left out") if fora else ""
        executivo = bloco_executivo(
            per, [fonte(VEICULO, "Dados Abertos: API pública de legislação estadual (leis e o detalhe de cada uma)",
                        "https://www3.al.es.gov.br/dados-abertos.aspx", hj),
                  fonte(VEICULO, "Legislação estadual no portal da Ales", "https://www3.al.es.gov.br/legislacao/", hj),
                  fonte(VEICULO, "Dados Abertos: API pública de proposições (mensagens de veto do governador)",
                        "https://www3.al.es.gov.br/dados-abertos.aspx", hj)],
            f"Leis: {qtd(n_ord, 'lei ordinária', 'leis ordinárias')} e {qtd(len(sanc) - n_ord, 'lei complementar', 'leis complementares')} "
            f"sancionadas desde {d_pt}, pelo cadastro de legislação da Ales (data da lei); {prom_pt}{fora_pt}. Vetos: as "
            f"mensagens de veto que o governo mandou à Assembleia no período, pela data de entrada ({v_pt}).",
            f"Laws: {qtd(n_ord, 'ordinary law', 'ordinary laws')} and {qtd(len(sanc) - n_ord, 'complementary law', 'complementary laws')} "
            f"signed since {d_en}, from the Ales register of laws (by the law's date); {prom_en}{fora_en}. Vetoes: the veto "
            f"messages the government sent to the Assembly in the period, by the date they arrived ({v_en}).",
            leis=len(sanc), vetos=len(vetos), vetos_totais=None if sem else tot, vetos_parciais=None if sem else par,
            ultima_lei=sanc[-1]["data"] if sanc else None, ultimo_veto=vetos[-1]["data"] if vetos else None)
        gravar_governo(UF, per, governo, *esc_g, f_gov, executivo)
    except Exception as e:  # uma fonte do governo fora do ar não derruba a coleta: fica o perfil da rodada anterior
        log(f"  ES: governo: {e}")
    # gastos: depois do resto, para a primeira carga deles (que pode usar o resto da rodada) não atrasar o governo
    try:
        blocos = _gastos(membros)
    except SemTempo:
        blocos = None
        log("  ES: cotas parlamentares: acabou o tempo da rodada; a leitura continua na próxima (ficam os blocos de antes)")
    except Exception as e:  # o portal da transparência fora do ar não derruba a Casa: ficam os blocos de antes
        blocos = None
        log(f"  ES: ATENÇÃO: cotas parlamentares não atualizadas ({type(e).__name__}: {e}); ficam os blocos de antes")
    com_gastos = aplicar(extras, blocos, "gastos")
    f_cotas = fonte(VEICULO, "Portal da Transparência: Cotas Parlamentares (escolha o gabinete e os meses)", COTAS, hj)
    for x in extras.values():
        if x.get("gastos") and f_cotas not in x["fontes"]:
            x["fontes"].append(f_cotas)
    notas = [("A Ales publica os boletins de votação nominal só como documentos (PDF); as votações não entram.",
              "The Ales only publishes roll-call vote reports as documents (PDF); votes are not included.")]
    if com_gastos:
        d_pt, d_en = desde(INICIO)
        notas.append((
            f"Gastos: o \"Valor Solicitado\" de cada gabinete na cota parlamentar, mês a mês desde {d_pt}, como a Ales publica "
            "no Portal da Transparência (\"Cotas Parlamentares\"): diárias e passagens aéreas (do deputado e da equipe do "
            "gabinete) e, desde 2024, reembolso de despesas, como aluguel de escritório, divulgação e consultorias. Em 2023 e "
            "2024 entravam também telefone, material, cópias, periódicos e postagens, e em 2023, combustível. A Ales publica "
            "cada mês até o fim do mês seguinte (Ato da Mesa nº 6.226/2025).",
            f"Spending: each office's \"Valor Solicitado\" (amount requested) from its allowance (\"cota parlamentar\"), month "
            f"by month since {d_en}, as the Ales publishes it on its transparency portal (\"Cotas Parlamentares\"): per diems "
            "and air tickets (for the deputy and the office staff) and, since 2024, reimbursed expenses such as office rent, "
            "publicity and consulting. In 2023 and 2024 it also covered phone, supplies, copies, periodicals and postage, and "
            "in 2023, fuel. The Ales publishes each month by the end of the following month (\"Ato da Mesa\" No. 6,226/2025)."))
    return gravar(UF, CASA, membros, extras, {"lista": True, "propostas": True, "votacoes": False, "gastos": com_gastos},
                  f_lista, esc_pt, esc_en, notas)
