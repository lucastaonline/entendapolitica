"""Câmara Municipal do Rio de Janeiro (RJ): a lista oficial de vereadores atuais (www.camara.rio/vereadores/quem-sao, que mostra
a tabela www.camara.rio/includes_php/vereadores_atuais.php) e as propostas de cada vereador e da prefeitura desde 1º/1/2025.

A foto vem embutida na própria tabela; o partido vem do logotipo de cada linha. O portal usa uma cadeia de certificados
incompleta (o navegador completa sozinho; o Python não): por isso a lista é lida sem conferir o certificado; o resultado é
conferido pelo número de vagas (51) e pelos nomes do TSE.

Propostas (frente capitais-b-r6, 27/10/2026): o sistema de proposições da Câmara (Lotus Notes, aplicnt.camara.rj.gov.br, o
mesmo das páginas de "Processo Legislativo" do portal) entrega as listas e a tramitação em JSON; a leitura e as regras da
situação estão em scripts/camaras/_cmrj.py. Primeira carga: ~60 pedidos (~55 MB, 2 minutos); depois, por dia, ~30 pedidos
(o primeiro pedido de cada lista, a tramitação do ano corrente e, a cada 3 dias, a dos anos anteriores).
Gastos: a cota de gabinete fica em partes separadas no portal da transparência (nota da Câmara).
"""
import collections
import html
import re
import time

import regional
from comum import fonte, hoje, log

from . import _base as B
from . import _cmrj as M
from . import _paginas as P

IBGE, UF, SITE = "3304557", "RJ", "https://www.camara.rio"
PAGINA = f"{SITE}/includes_php/vereadores_atuais.php?imprimir=N"
CASA = {"casa": "Câmara Municipal do Rio de Janeiro", "casa_en": "Rio de Janeiro City Council", "sigla": "CMRJ", "site": SITE,
        "sistema": "Portal oficial (HTML) e sistema de proposições (Lotus Notes, JSON)",
        "api": "https://aplicnt.camara.rj.gov.br/APL/Legislativos/scpro.nsf",
        "sic": "https://transparencia.camara.rj.gov.br/acesso-a-informacao/solicitacao-de-informacao"}
PAG_PROJETOS = f"{SITE}/atividade-parlamentar/processo-legislativo/pl"
# autores que não são vereadores (não entram no perfil de ninguém) e a prefeitura
_ORGAO = re.compile(r"^(mesa|comiss|tribunal|bancada|lideranca|frente|procuradoria|defensoria|ministerio)")
_EXECUTIVO = re.compile(r"^(poder executivo|prefeit)")
# nomes no sistema de proposições conferidos à mão (chave = como o sistema escreve; valor = chave oficial na lista)
AUTORES_MANUAL: dict[str, str | None] = {}


def autores(lista: list[str]) -> list[str]:
    """Os autores na ordem do cadastro. Alguns registros juntam dois nomes ("VEREADOR A E VEREADOR B"); os assinados em nome
    da Mesa Diretora ("VEREADOR A - MESA DIRETORA") são da Mesa."""
    out = []
    for a in lista:
        a = re.sub(r"[.\s]+$", "", a.strip())
        if re.search(r"mesa diretora", B.norm(a)):
            out.append("MESA DIRETORA")
            continue
        out += [p.strip() for p in re.split(r"\s+E\s+(?=VEREADOR)", a, flags=re.I) if p.strip()]
    return out


def vereadores(ctx) -> list[dict]:
    t = B.baixar_pagina(PAGINA, IBGE, "vereadores", contexto=ctx)
    pessoas = []
    for linha in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", t):
        cvd = re.search(r"vereador\.php\?cvd=(\d+)'[^>]*>\s*([^<]+?)\s*</a>", linha)
        foto = re.search(r'<img src="(data:image/[^"]+)"', linha)
        sigla = re.search(r'partido_politico/[^"]+"\s+alt="([^"]*)"', linha)
        email = re.search(r'href="mailto:([^"]+)"', linha)
        if not cvd:
            continue
        pessoas.append({"chave": cvd.group(1), "nome": html.unescape(cvd.group(2)).strip(),
                        "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                        "foto": foto.group(1) if foto else None,
                        "url": f"{SITE}/includes_php/vereador.php?cvd={cvd.group(1)}",
                        "email": html.unescape(email.group(1)).strip() if email else None})
    return pessoas


ESCOPO = (B.ESCOPO + ", segundo o sistema de proposições da Câmara (a data é a da publicação do projeto no Diário da Câmara).",
          B.ESCOPO_EN + ", according to the City Council's bills system (the date is when the bill was published in the City "
          "Council's official gazette).")
NOTA_PROPOSTAS = (
    "As propostas vêm do sistema de proposições da Câmara (o mesmo das páginas de \"Processo Legislativo\" do portal): o "
    "primeiro nome da lista de autores é o autor principal e os outros assinaram junto; a situação é a do documento mais novo "
    "da tramitação que decide o andamento (lei, veto, retirada, anexação a outro projeto, arquivo, rejeição ou aprovação). "
    "Projetos da Mesa Diretora e das comissões não entram no perfil de nenhum vereador.",
    "Bills come from the City Council's bills system (the same one shown on the portal's \"Legislative Process\" pages): the "
    "first name on the list of authors is the main author and the others co-signed; the status is the one in the newest "
    "document of the bill's history that decides where it stands (law, veto, withdrawal, attachment to another bill, archive, "
    "rejection or approval). Bills by the City Council's board or committees are not shown on any councilor's profile.")
NOTA_GASTOS = (
    "Os gastos do mandato de cada vereador não entram neste site: a Câmara publica a cota de gabinete em partes separadas no "
    "portal da transparência — uma planilha anual de combustível e manutenção de veículos (a de 2026 traz só de janeiro a "
    "março), uma lista anual do auxílio-alimentação de cada vereador e uma consulta dos pagamentos do aluguel de carros "
    "blindados, ano a ano —, sem um arquivo com todos os gastos de cada vereador mês a mês.",
    "Each councilor's office spending is not included on this site: the City Council publishes its office allowance in "
    "separate parts on its transparency portal — a yearly spreadsheet of fuel and vehicle upkeep (the 2026 one only covers "
    "January to March), a yearly list of each councilor's meal allowance and a search of payments for armored car rentals, "
    "year by year — with no file of all of each councilor's spending month by month.")


def coletar() -> dict:
    t0 = time.time()
    h = hoje()
    ctx = M.contexto()
    pessoas = vereadores(ctx)
    CASA["fonte"] = fonte(CASA["casa"], "Vereadores atuais (portal oficial)", f"{SITE}/vereadores/quem-sao", h)
    membros, extras, _, tse = P.lista(IBGE, UF, CASA, pessoas, 51)

    # ------------------------------------------------ propostas (sistema de proposições)
    rede = P.Rede(IBGE, M.PAUSA, contexto=ctx)
    e = P.ler_estado(IBGE)
    try:
        M.ler_propostas(rede, e, h)
    except P.SemTempo as motivo:
        P.guardar_estado(IBGE, e)
        log(f"  CMRJ: propostas pela metade ({motivo}; {rede.resumo(t0)}): continuam na próxima rodada; nada foi gravado")
        return {"ok": True, "pendente": True, "etapa": "propostas", "requisicoes": rede.n}
    except Exception:
        P.guardar_estado(IBGE, e)  # site fora do ar no meio: o que já foi lido fica para a próxima rodada
        raise
    itens, normas = e.get("itens") or {}, e.get("normas") or {}
    nomes = P.Nomes(membros, AUTORES_MANUAL)
    P.limpar_membros(membros)
    pref_id, pref_ini = P.inicio_prefeito(IBGE, UF)
    por_id: dict[str, list] = {m["id"]: [] for m in membros}
    do_pref, orgaos, fora = [], collections.Counter(), collections.Counter()
    for c, x in sorted(itens.items()):
        st, situ, d_st, lei = M.situacao(x, normas)
        comum = M.TIPOS[x["tipo"]][1]
        vistos = set()
        for i, a in enumerate(autores(x.get("autores") or [])):
            k = B.norm(a)
            k = re.sub(r"^vereador(a)?\s+", "", k)
            if _EXECUTIVO.match(k):
                if i == 0 and comum in ("PL", "PLP", "PELO") and (x.get("data") or "") >= pref_ini and pref_id:
                    do_pref.append(P.proposta(f"cm{IBGE}:{c}", M.sigla(x), comum, x.get("data"), x.get("ementa"), situ,
                                              M.url_projeto(x), "autor", st, d_st, lei))
                continue
            if _ORGAO.match(k):
                orgaos[a] += 1
                continue
            pid = nomes.id(a)
            if not pid:
                fora[a] += 1
                continue
            if pid in vistos or pid not in por_id:
                continue
            vistos.add(pid)
            por_id[pid].append(P.proposta(f"cm{IBGE}:{c}", M.sigla(x), comum, x.get("data"), x.get("ementa"), situ,
                                          M.url_projeto(x), "autor" if i == 0 else "coautor", st, d_st, lei))
    if fora:
        log(f"  CMRJ: autores fora da lista oficial de hoje ({len(fora)} nomes): "
            + ", ".join(f"{n} ({q})" for n, q in fora.most_common(12)))
    for m in membros:
        f_prop = fonte(CASA["casa"], f"Sistema de proposições da Câmara: projetos de {m['nome']}", PAG_PROJETOS, h)
        x = extras[m["id"]]
        x["propostas"] = regional.bloco_propostas(por_id[m["id"]], ESCOPO[0], ESCOPO[1], f_prop)
        x["fontes"].append(f_prop)
    prefeito = None
    if pref_id:
        esc = P.escopo_prefeito(pref_ini, "o sistema de proposições da Câmara", "the City Council's bills system",
                                "projetos de lei, de lei complementar e de emenda à Lei Orgânica",
                                "ordinary and complementary bills and amendments to the city's Organic Law")
        f_pref = fonte(CASA["casa"], "Sistema de proposições da Câmara: projetos do Poder Executivo",
                       f"{SITE}/atividade-parlamentar/processo-legislativo/msgexec", h)
        prefeito = (pref_id, {"propostas": regional.bloco_propostas(do_pref, esc[0], esc[1], f_pref), "fontes": [f_pref]})

    notas = [NOTA_PROPOSTAS] + [n for n in B.NOTAS_VOTOS_GASTOS.get(IBGE, []) if "votações" in n[0]] + [NOTA_GASTOS]
    cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
    r = B.salvar(IBGE, UF, CASA, membros, extras, cobertura, notas, ESCOPO, prefeito=prefeito)
    r["requisicoes"] = rede.n
    r["semTse"] = len(tse.sem_ligacao)
    log(f"  CMRJ: {len(membros)} no cargo, {r['propostas']} propostas de {sum(1 for v in por_id.values() if v)} vereadores, "
        f"prefeito {len(do_pref)} projetos; {rede.resumo(t0)}")
    return r
