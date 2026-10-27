"""Câmara Municipal de Belo Horizonte (MG): a lista oficial de vereadores em exercício (www.cmbh.mg.gov.br/vereadores) e as
propostas de cada vereador e da prefeitura desde 1º/1/2025, lidas na pesquisa de proposições do portal da Câmara (leitura e
situação em scripts/camaras/_cmbh.py; frente capitais-b-r6, 27/10/2026).

O robots.txt da Câmara pede 10 s entre pedidos: a primeira carga das propostas leva umas 4 horas (no robô do GitHub,
umas 8 rodadas, sem publicar nada pela metade); depois, uns 20 a 30 pedidos por dia (4 a 7 minutos).
Gastos: a Câmara extinguiu a verba indenizatória em 2015 (Resolução 2.076/2015); o material e os serviços dos gabinetes são
contratados pela própria Câmara (nota da Câmara).
"""
import collections
import re
import time

import regional
from comum import fonte, hoje, log

from . import _base as B
from . import _cmbh as M
from . import _paginas as P

IBGE, UF, SITE = M.IBGE, M.UF, M.SITE
CASA = M.CASA
# conferidos à mão (nome no portal da Câmara = nome de urna no TSE, eleitos em 2024): "Trópia" = MARCELA TRÓPIA (NOVO);
# "Vile Santos" = VILE (Wili dos Santos, PL)
TSE_MANUAL = {"tr%C3%B3pia": "130001976053", "vile-santos": "130002172736"}
# nomes na autoria das proposições conferidos à mão (como o portal escreve -> chave oficial do vereador na lista)
AUTORES_MANUAL: dict[str, str | None] = {}
_ORGAO = re.compile(r"^(mesa|comiss|tribunal|bancada|lideranca|frente|procuradoria|defensoria|ministerio|cidadao|iniciativa)")
_EXECUTIVO = re.compile(r"^(executivo|prefeit|poder executivo)")

ESCOPO = (B.ESCOPO + ", segundo a pesquisa de proposições do portal da Câmara (a data é a da publicação da proposição).",
          B.ESCOPO_EN + ", according to the bills search on the City Council's portal (the date is when the bill was "
          "published).")
NOTA_PROPOSTAS = (
    "As propostas vêm da pesquisa de proposições do portal da Câmara (a lista e a página de cada proposição): o primeiro nome "
    "da autoria é o autor principal e os outros assinaram junto; a situação é a que a Câmara publica (\"Lei\", \"Primeiro "
    "turno\", \"Retirada\"...). Projetos da Mesa Diretora e das comissões não entram no perfil de nenhum vereador. O portal "
    "pede 10 segundos entre um pedido e outro; por isso, a situação de cada proposição é revista em até dez dias (as novas "
    "entram no mesmo dia).",
    "Bills come from the bills search on the City Council's portal (the list and each bill's page): the first name among the "
    "authors is the main author and the others co-signed; the status is the one the City Council publishes (\"Law\", \"First "
    "round\", \"Withdrawn\"...). Bills by the City Council's board or committees are not shown on any councilor's profile. "
    "The portal asks for 10 seconds between requests, so each bill's status is checked again within ten days (new bills "
    "are added on the same day).")


def autores(texto: str | None) -> list[str]:
    """'Ver.(a) A; Ver.(a) B' -> ['Ver.(a) A', 'Ver.(a) B']; 'Mesa - Ver.(a) ...' -> ['Mesa Diretora']."""
    t = (texto or "").strip()
    if re.match(r"(?i)mesa\b", t):
        return ["Mesa Diretora"]
    return [p.strip() for p in t.split(";") if p.strip()]


def coletar() -> dict:
    t0 = time.time()
    h = hoje()
    pessoas = M.vereadores()
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores em exercício (portal oficial)", f"{SITE}/vereadores", h)
    membros, extras, _, tse = P.lista(IBGE, UF, CASA, pessoas, 41, TSE_MANUAL)

    rede = P.Rede(IBGE, M.PAUSA)
    e = P.ler_estado(IBGE)
    try:
        M.ler_propostas(rede, e, h)
    except P.SemTempo as motivo:
        P.guardar_estado(IBGE, e)
        itens = e.get("itens") or {}
        log(f"  CMBH: propostas pela metade ({motivo}; {len(itens)} na lista, "
            f"{sum(1 for x in itens.values() if x.get('det'))} com a página lida; {rede.resumo(t0)}): continuam na próxima "
            "rodada; nada foi gravado")
        return {"ok": True, "pendente": True, "etapa": "propostas", "requisicoes": rede.n}
    except Exception:
        P.guardar_estado(IBGE, e)  # site fora do ar no meio: o que já foi lido fica para a próxima rodada
        raise
    itens = e.get("itens") or {}
    nomes = P.Nomes(membros, AUTORES_MANUAL)
    P.limpar_membros(membros)
    pref_id, pref_ini = P.inicio_prefeito(IBGE, UF)
    por_id: dict[str, list] = {m["id"]: [] for m in membros}
    do_pref, orgaos, fora = [], collections.Counter(), collections.Counter()
    for k, x in sorted(itens.items()):
        st, situ, d_st, lei = M.situacao(x)
        comum = M.TIPO_COMUM[x["tipo"]]
        data = (x.get("det") or {}).get("data")
        url = (x.get("det") or {}).get("url") or M.url_permanente(x)
        pid_prop = f"cm{IBGE}:{x['id']}"
        vistos = set()
        for i, a in enumerate(autores(x.get("autoria"))):
            n = B.norm(a)
            if _EXECUTIVO.match(n):
                ini = M.data_mensagem(a) or data or ""
                if i == 0 and comum in ("PL", "PLP", "PELO") and ini >= pref_ini and pref_id:
                    do_pref.append(P.proposta(pid_prop, M.sigla(x), comum, data, x.get("ementa"), situ, url, "autor", st,
                                              d_st, lei))
                continue
            if _ORGAO.match(n):
                orgaos[a] += 1
                continue
            pid = nomes.id(a)
            if not pid:
                fora[a] += 1
                continue
            if pid in vistos or pid not in por_id:
                continue
            vistos.add(pid)
            por_id[pid].append(P.proposta(pid_prop, M.sigla(x), comum, data, x.get("ementa"), situ, url,
                                          "autor" if i == 0 else "coautor", st, d_st, lei))
    if fora:
        log(f"  CMBH: autores fora da lista oficial de hoje ({len(fora)} nomes): "
            + ", ".join(f"{n} ({q})" for n, q in fora.most_common(12)))
    for m in membros:
        f_prop = fonte(CASA["casa"], f"Pesquisa de proposições do portal: projetos de {m['nome']}", m["url"] + "/projetos", h)
        x = extras[m["id"]]
        x["propostas"] = regional.bloco_propostas(por_id[m["id"]], ESCOPO[0], ESCOPO[1], f_prop)
        x["fontes"].append(f_prop)
    prefeito = None
    if pref_id:
        esc = P.escopo_prefeito(pref_ini, "a pesquisa de proposições do portal da Câmara", "the bills search on the City "
                                "Council's portal", "projetos de lei e de emenda à Lei Orgânica",
                                "bills and amendments to the city's Organic Law")
        f_pref = fonte(CASA["casa"], "Pesquisa de proposições do portal: projetos do Executivo", M.PESQUISA, h)
        prefeito = (pref_id, {"propostas": regional.bloco_propostas(do_pref, esc[0], esc[1], f_pref), "fontes": [f_pref]})

    notas = [NOTA_PROPOSTAS] + list(B.NOTAS_VOTOS_GASTOS.get(IBGE, []))
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = B.salvar(IBGE, UF, CASA, membros, extras, cobertura, notas, ESCOPO, prefeito=prefeito)
    r["requisicoes"] = rede.n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMBH: {len(membros)} no cargo, {r['propostas']} propostas de {sum(1 for v in por_id.values() if v)} vereadores, "
        f"prefeito {len(do_pref)} projetos; {rede.resumo(t0)}")
    return r
