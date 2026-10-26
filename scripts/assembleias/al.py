"""Assembleia Legislativa do Estado de Alagoas (ALE-AL): SAPL 3 (https://sapl.al.al.leg.br/api/) + página oficial da
legislatura.

Lista: a página oficial "20ª Legislatura" do site da ALE-AL (https://www.al.al.leg.br/processo-legislativo/20-a-legislatura),
só a parte de quem está exercendo o mandato (a parte "Parlamentares eleitos mas que não estão exercendo o mandato" fica de
fora). O SAPL da ALE-AL não marca o fim dos mandatos (mais de 27 pessoas aparecem como ativas), por isso ele não serve
para dizer quem está no cargo hoje; serve para o resto: nome completo, sexo, titular ou suplente e as propostas.
Propostas: projetos de lei ordinária (PLO), de lei complementar (PLC), de emenda à Constituição (PEC), de decreto
legislativo (PDL) e de resolução (PRE) desde 1º/2/2023. Situação: a da última tramitação; "virou lei" pela norma
jurídica ligada ao projeto; "vetada por inteiro" pelas matérias do tipo VETO TOTAL (ligadas pelo número do projeto citado
na ementa).
"""
from __future__ import annotations

import html
import re

from comum import sem_acento

from ._ne_comum import legislatura_estadual
from ._ne_sapl import SaplAssembleia

PAGINA = "https://www.al.al.leg.br/processo-legislativo/{n}-a-legislatura"
REDES = re.compile(r"https?://(www\.)?(instagram\.com|twitter\.com|x\.com|facebook\.com|youtube\.com|tiktok\.com)/[^\s\"'<>]+", re.I)


def em_exercicio(col, parls) -> dict:
    """Quem está exercendo o mandato segundo a página oficial da legislatura em curso (id do SAPL -> foto, partido e redes).
    No dia da posse da legislatura seguinte (1º/2/2027) o endereço passa a ser o da 21ª; se a página ainda não existir, o
    coletor falha e o legislativos.py mantém a lista anterior."""
    n = legislatura_estadual(20)
    t = col.rede.texto(PAGINA.format(n=n), f"legislatura-{n}.html", 20)
    corte = re.search(r"PARLAMENTARES ELEITOS MAS QUE N(?:Ã|&Atilde;|&#195;)O EST(?:Ã|&Atilde;|&#195;)O EXERCENDO", t)
    inicio = re.search(rf"{n}(?:ª|&ordf;|&#170;) LEGISLATURA", t)
    if not inicio:
        raise RuntimeError("ALE-AL: a página da legislatura mudou de formato")
    parte = t[inicio.end():corte.start() if corte else len(t)]
    out = {}
    for linha in re.findall(r"<tr.*?</tr>", parte, re.S):
        m = re.search(r'href="https?://sapl\.al\.al\.leg\.br/parlamentar/(\d+)"', linha)
        if not m:
            continue
        txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", linha))).strip()
        img = re.search(r'<img[^>]+src="([^"]+)"', linha)
        partido = re.search(r"Partido:\s*(.+?)\s+E-mail", txt)
        redes = []
        for r in REDES.finditer(linha):
            u = r.group(0).rstrip("/")
            if u not in redes:
                redes.append(u)
        out[int(m.group(1))] = {"foto": img.group(1) if img else None, "partido_site": partido.group(1) if partido else None,
                                "redes": redes}
    if not 20 <= len(out) <= 30:
        raise RuntimeError(f"ALE-AL: a página da legislatura trouxe {len(out)} pessoas (esperado: 27)")
    return out


# situação da última tramitação na ALE-AL (texto oficial sem acento, minúsculas) -> status do site. Conferido à mão numa
# amostra: "MATÉRIA ENVIADA GABINETE DEPUTADO" e "GABINETE DO PARLAMENTAR" = o projeto foi para o gabinete do relator;
# "PARECER APROVADO, PL AGUARDANDO INCLUSÃO NA ORDEM DO DIA" = a comissão aprovou e falta o Plenário.
REGRAS = [
    (r"identica com lei", "parada", "Parou: já existe uma lei igual", "Stopped: an identical law already exists"),
    (r"mantido veto parcial|sancionada com veto parcial|lei com veto parcial|norma c/ veto parcial promulgada", "lei",
     "Virou lei (com partes vetadas)", "Became law (with some parts vetoed)"),
    (r"veto total promulgada", "lei", "Virou lei (o veto do governador foi derrubado)", "Became law (the governor's veto was overridden)"),
    (r"transformada em lei|sancionada como lei|lei publicada|lei republicada|transformada em emenda constitucional|"
     r"sancionada como emenda|transformada em resolucao|transforma em resolucao|transformada em decreto legislativo|"
     r"sancao tacita|prazo expirado p/ sancao e promulgada|promulgada pel[oa]", "lei", "Virou lei", None),
    (r"veto total|recebeu veto total", "rejeitada", "Vetada por inteiro pelo governador", "Fully vetoed by the governor"),
    (r"aguardando promulgacao|aguardando a promulgacao|aguardando o autografo|autografo da mesa|aguarda autografo|"
     r"aguardando assinatura do autografo|sancao|aprovada promulgacao", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"retirada, pleito identico|retirad[ao] (pelo|a pedido)", "retirada", None, None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvida ao gabinete", "parada", "Devolvida ao autor", "Returned to the author"),
    (r"arquiv", "arquivada", "Arquivada", None),
    (r"identica (do mesmo autor )?tramitando|materia identica", "junta", None, None),
    (r"parecer contrario|parecer pela rejeicao", "andando", "Uma comissão deu parecer contra; falta a decisão final",
     "A committee recommended rejecting it; the final decision is pending"),
    (r"parecer aprovado|parecer deliberado", "andando", "Aprovada numa comissão; falta a votação em Plenário",
     "Approved by a committee; the vote in the full Assembly is still pending"),
    (r"aprovada 1. turno|1. turno", "andando", None, None),
    (r"(materia|mat\.?) (discutida,? )?(e )?(votada e )?aprovada|aprovada em (1. ?e 2. discussao|discussao unica|redacao)|"
     r"aprovada na ordem do dia|aprovada, aguardando tramitacao final|discutida e aprovada|votada e provada", "aprovada", None, None),
    (r"gabinete|relator|parecer|aguardando|tramitando|distribui|lida no expediente|ordem do dia|pauta|discussao|leitura|"
     r"comiss|retificacao|recebimento de emendas|encaminha|despach|protocol|plenario|expediente", "andando", None, None),
    (r".", "outra", None, None),
]


def _promulgada(n: dict) -> bool | None:
    """Na ALE-AL, o SAPL anota onde cada lei saiu e, quase sempre, quem a assinou: as sancionadas pelo governador saem no
    Diário Oficial do Estado; as que o presidente da Assembleia promulga (sanção tácita ou veto derrubado) saem no Diário
    Oficial da Assembleia (e a observação diz "promulgada pelo presidente da Assembleia")."""
    v = sem_acento((n.get("veiculo_publicacao") or "").lower())
    o = sem_acento((n.get("observacao") or "").lower())
    if re.search(r"assembleia|legislativo|\bale\b", v) or re.search(r"presidente da assembleia|sancao tacita|poder legislativo", o):
        return True
    if re.search(r"diario oficial do estado|\bd\.?o\.?e|doeal", v) or re.search(r"sancionad|governador", o):
        return False
    return None


GOV = {
    "autores": [40],  # "PODER EXECUTIVO ESTADUAL"
    "tipos": {1: "PL", 5: "PLP", 9: "PEC", 6: "PDL"},
    "tipos_lei": [1, 2],  # LEI ORDINARIA, LEI COMPLEMENTAR
    "promulgada": _promulgada,
    "criterio_leis": ("publicadas no Diário Oficial do Estado ou anotadas como sancionadas pelo governador",
                      "published in the State Official Gazette or recorded as signed by the governor"),
}


def coletar() -> dict:
    n = legislatura_estadual(20)
    return SaplAssembleia(
        uf="AL", base="https://sapl.al.al.leg.br", casa="Assembleia Legislativa do Estado de Alagoas",
        casa_en="Legislative Assembly of the State of Alagoas", sigla="ALE-AL", site="https://www.al.al.leg.br",
        veiculo="Assembleia Legislativa de Alagoas (ALE-AL)", prefixo="aleal", pasta="aleal",
        tipos={1: "PL", 5: "PLP", 9: "PEC", 6: "PDL", 2: "PRC"}, tipos_veto={23: "total", 24: "parcial"}, regras=REGRAS,
        em_exercicio=em_exercicio, gov=GOV,
        lista_oficial=(f"Parlamentares no exercício do mandato ({n}ª Legislatura, página oficial)", PAGINA.format(n=n)),
        notas=[(f"A lista de quem está no cargo vem da página oficial da {n}ª Legislatura no site da ALE-AL. Substituições "
                "temporárias (licenças) podem demorar a aparecer nessa página.",
                f"The list of who is in office comes from the official page of the {n}th Legislature on the ALE-AL website. Temporary "
                "substitutions (leaves of absence) may take a while to show up on that page."), NOTA_VOTOS_GASTOS],
    ).coletar()


NOTA_VOTOS_GASTOS = (
    "As votações e os gastos não entram. Votações: o SAPL da ALE-AL (sapl.al.al.leg.br) não tem nenhuma sessão nem votação "
    "registrada desde 1º/2/2023. Gastos: a ALE-AL publica a verba indenizatória (VIAP) de cada deputado só como documento "
    "digitalizado (uma imagem em PDF por mês), na página \"VIAP\" do seu Portal da Transparência.",
    "Votes and spending are not included. Votes: the ALE-AL SAPL system (sapl.al.al.leg.br) has no sessions or votes "
    "recorded since February 1, 2023. Spending: the ALE-AL publishes each deputy's expense allowance (VIAP) only as a "
    "scanned document (one PDF image per month), on the \"VIAP\" page of its transparency portal.")
