"""Assembleia Legislativa do Estado do Tocantins (Aleto): lista oficial no site da Casa + propostas no SAPL 3.

Lista oficial: https://www.al.to.leg.br/perfil (os 24 deputados em exercício, com partido, foto, e-mail e redes). O SAPL
da Aleto (https://sapl.al.to.leg.br/api/) não traz o partido e marca como ativo quem já saiu, por isso a lista vem do site;
cada pessoa do site é ligada à sua ficha no SAPL pelo nome. Propostas: matérias do SAPL desde 1º/2/2023 (os tipos "da
Casa": PL, PLP, PEC, PDL e PRC dos deputados); situação = a da última tramitação; "virou lei" = norma jurídica ligada à
proposta no SAPL. O SAPL do Tocantins não tem votações registradas.
Governador (gov-TO): projetos e vetos do governo no SAPL e as leis sancionadas, pela página "Legislação Estadual" do site
da Aleto (GOVERNO, abaixo), inclusive o que assinou quem estava no exercício do cargo (vice-governador ou presidente da
Assembleia; a nota diz quantos); as leis promulgadas pela própria Assembleia ficam de fora.
"""
from __future__ import annotations

import re

import regional
from comum import fonte, log, sem_acento

from . import _nco_gov as G
from ._nco_comum import https, texto_html
from ._nco_sapl import Sapl

SITE = "https://www.al.to.leg.br"


def lista_oficial(col: Sapl, parls: list[dict]) -> list[dict]:
    html = col.rede.texto(f"{SITE}/perfil", "site/perfil.html", 20)
    blocos = html.split('class="quadro-deputado-container"')[1:]
    if len(blocos) < 20:
        raise RuntimeError(f"TO: a página {SITE}/perfil mudou (só {len(blocos)} deputados)")
    sapl = [(p["id"], set(regional.palavras(p.get("nome_parlamentar")))) for p in parls]
    out, usados = [], set()
    for bl in blocos:
        nome = texto_html((re.search(r"<h3>(.*?)</h3>", bl, re.S) or [None, ""])[1])
        partido = texto_html((re.search(r"<h5>(.*?)</h5>", bl, re.S) or [None, ""])[1])
        url = (re.search(r'href="(/perfil/parlamentar/[^"]+)"', bl) or [None, None])[1]
        foto = (re.search(r'<img src="([^"]+)"', bl) or [None, None])[1]
        emails = [texto_html(x) for x in re.findall(r"<h6>(.*?)</h6>", bl, re.S) if "@" in x]
        redes = [u for u in re.findall(r'<a href="(https?://[^"]+)"', bl) if not u.startswith(SITE)]
        alvo = set(regional.palavras(nome))
        cands = [sid for sid, pal in sapl if pal and (pal == alvo or (len(alvo & pal) >= 2 and (alvo <= pal or pal <= alvo)))]
        cands = [c for c in cands if c not in usados]
        sid = cands[0] if len(cands) == 1 else None
        if sid is None:
            log(f"  TO: {nome} não foi ligado a uma ficha do SAPL ({cands})")
        else:
            usados.add(sid)
        out.append({"sapl": sid, "nome_site": nome, "partido_site": partido, "foto": https(foto),
                    "url": f"{SITE}{url}" if url else f"{SITE}/perfil", "email": emails[0] if emails else None, "redes": redes})
    return out


VETO_PENDENTE = ("Vetada pelo governador; a Assembleia ainda vai decidir sobre o veto",
                 "Vetoed by the governor; the state assembly has yet to decide on the veto")
REGRAS = [
    (r"lei promulgada|lei sancionada|promulgacao de decreto legislativo|veto total ou parcial promulgado", "lei", None, None),
    (r"cancelamento a pedido do autor|retirada pelo autor", "retirada", None, None),
    (r"veto sobre a proposicao rejeitado", "aprovada", "Aprovada; o veto do governador foi derrubado e falta promulgar",
     "Approved; the governor's veto was overridden and it still needs to be promulgated"),
    (r"mensagem de veto", "andando", *VETO_PENDENTE),
    (r"aguardando promulgacao", "aprovada", "Aprovada; esperando ser promulgada", None),
    (r"aguardando autografo|autografo de lei elaborado", "aprovada", "Aprovada; o texto final (autógrafo) vai ao governador",
     "Approved; the final text (autograph) goes to the governor"),
    (r"aprovada em 1.? turno", "andando", "Aprovada no 1º turno; falta o 2º turno", "Approved in the first round; the second round is still pending"),
    (r"aprovada em 2.? turno|^proposicao aprovada$", "aprovada", None, None),
    (r"apensado|anexada", "junta", None, None),
    (r"desarquivada", "andando", None, None),
    (r"encaminhamento ao arquivo|arquivada", "arquivada", None, None),
    (r"rejeitada", "rejeitada", None, None),
    (r"retirad[ao] da (pauta|ordem do dia)", "andando", None, None),
    (r"^requerimento", "andando", None, None),  # requerimento sobre a proposta (urgência, por exemplo): não muda a situação dela
    (r"aguardando|procuradoria|gerar proposicao|tramitacao normal|recurso|comissoes|distribuida", "andando", None, None),
]
AMBIGUOS = [r"^requerimento"]

# ------------------------------------------------------------ o que o governo do estado fez (perfil gov-TO)
LEIS_URL = f"{SITE}/legislacaoEstadual"
_MESES = {m: i + 1 for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
                                           "setembro", "outubro", "novembro", "dezembro"])}


def _quem_assinou(t: str) -> str:
    """Começo do texto da lei (sem acento, minúsculas) -> quem assinou: "governador" (o governador de hoje ou de antes,
    "o governador do estado ... eu sanciono"), "exercicio" (vice-governador ou presidente da Assembleia no exercício do
    cargo de governador; o texto oficial às vezes tem erro de digitação, como "GOVERNDOR"), "promulgada" (promulgada pela
    Assembleia, inclusive a conversão de medida provisória: "o governador ... adotou a medida provisória ... e eu,
    presidente da Assembleia, promulgo") ou "?"."""
    if re.search(r"no exercicio do cargo|no exercicio das atribuicoes|governador em exercicio|o vice-governador do estado", t):
        return "exercicio"
    if re.search(r"o governador do estado", t) and "sanciono" in t:
        return "governador"
    if re.search(r"promulg", t):
        return "promulgada"
    return "?"


# leis em que a página mostra só a ementa (longa) e não o começo do texto: quem assinou foi conferido à mão no PDF oficial
# (https://www.al.to.leg.br/arquivo/<id>) em 23/10/2026. Leis novas nessa situação ficam como "?" e a nota diz quantas.
QUEM_CONFERIDO = {
    **{f"LO-{n}": "promulgada" for n in (4143, 4232, 4295, 4377, 4505, 4620, 4718, 4816, 4955, 4987, 5030, 5031)},
    **{f"LO-{n}": "exercicio" for n in (4181, 4182, 4437, 4438, 4441, 4442, 4443, 4444)},
    **{f"LO-{n}": "governador" for n in (4219, 4990, 4995, 5001, 5003, 5004, 5026)},
}


def _itens_leis(html: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<h4><a href="/arquivo/(\d+)">([^<]+)</a></h4>(.*?)(?=<h4><a href=|<nav aria-label|$)', html, re.S):
        titulo, bloco = texto_html(m.group(2)), texto_html(m.group(3))
        num = re.search(r"n\D{0,3}\s*([\d.]+)", titulo)
        if not num:
            continue
        t = sem_acento(bloco).lower()
        n = int(num.group(1).replace(".", ""))
        pub = re.search(r"data: (\d{2})/(\d{2})/(\d{4})", t)
        data = None
        # o cabeçalho da própria lei ("LEI Nº 4.223, DE 1º DE SETEMBRO DE 2023. Publicado no Diário Oficial..."): vale mais
        # que o título da página, que às vezes tem erro de digitação ("Lei nº 2023 de 2023")
        hdr = re.search(r"lei(?: complementar)? n[^\d]{0,5}([\d.]+),? de (\d{1,2})[oº°]? de ([a-z]+) de (\d{4})\.?\s*publicad", t)
        if hdr and _MESES.get(hdr.group(3)):
            n = int(hdr.group(1).replace(".", ""))
            data = f"{hdr.group(4)}-{_MESES[hdr.group(3)]:02d}-{int(hdr.group(2)):02d}"
        else:
            # sem o cabeçalho completo: a data da lei com o número do título (a ementa pode citar outras leis antes)
            n_exp = re.sub(r"(\d)(?=(\d{3})+$)", r"\1\\.?", str(n))
            d = re.search(rf"lei(?: complementar)? n[^\d]{{0,5}}{n_exp},? de (\d{{1,2}})[oº°]? de ([a-z]+) de (\d{{4}})", t)
            if d and _MESES.get(d.group(2)):
                data = f"{d.group(3)}-{_MESES[d.group(2)]:02d}-{int(d.group(1)):02d}"
            elif pub:
                data = f"{pub.group(3)}-{pub.group(2)}-{pub.group(1)}"
        tipo = "LC" if "complementar" in titulo.lower() else "LO"
        q = _quem_assinou(t)
        out.append({"id": m.group(1), "t": tipo, "n": n, "d": data,
                    "q": QUEM_CONFERIDO.get(f"{tipo}-{n}", q) if q == "?" else q})
    return out


def leis_to(col: Sapl, ini: str):
    """Leis do Tocantins publicadas desde 'ini', pela página "Legislação Estadual" do site da Aleto: cada lei vem com a
    data e o começo do texto, que diz quem assinou ("O GOVERNADOR DO ESTADO ... eu sanciono"; "O VICE-GOVERNADOR ..., no
    exercício do cargo de GOVERNADOR"; ou a promulgação pela Assembleia). O cadastro de normas do SAPL da Aleto tem números
    repetidos e muitas faltas, por isso não serve para contar. 20 leis por página, da mais nova para a mais antiga; a
    rodada lê só até achar leis já conhecidas (tudo de novo a cada 30 dias). Mesma régua do perfil do presidente: entram
    as sancionadas pelo governador e por quem estava no exercício do cargo (a nota diz quantas); as promulgadas pela
    própria Assembleia não entram. Se o tempo da rodada acabar, vale o que já está no cache."""
    import datetime as dt
    from comum import hoje
    from ._nco_comum import SemTempo
    st = col.rede.estado("leis-site.json", {}) or {}
    if st.get("inicio") != ini:
        st = {"inicio": ini}
    leis: dict[str, dict] = st.get("leis") or {}
    completo = st.get("completo") or ""
    cheio = not leis or not completo or (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(completo[:10])).days >= 30
    lidas: dict[str, dict] = {}
    p, total, terminou = 1, None, False
    try:
        while True:
            html = col.rede.texto(f"{LEIS_URL}?documento.dataInicio={ini}&pagPaginaAtual={p}")
            if total is None:
                total = int((re.search(r"Registros encontrados: <strong>(\d+)", html) or [0, "0"])[1])
            itens = _itens_leis(html)
            novos = [x for x in itens if x["id"] not in leis]
            lidas.update({x["id"]: x for x in itens})
            if not itens or p * 20 >= total or (not cheio and not novos):
                terminou = True
                break
            p += 1
    except SemTempo:
        log("  gov-TO: o tempo desta rodada acabou na página de leis; vale o que já estava no cache")
    if cheio and terminou:
        if len(lidas) < 0.95 * (total or 0):
            raise RuntimeError(f"TO: a página de leis mudou (li {len(lidas)} de {total})")
        leis = lidas
        completo = hoje()
    else:
        leis.update(lidas)
    if not leis:
        raise RuntimeError("TO: nenhuma lei lida da página da Aleto")
    col.rede.guardar({"inicio": ini, "leis": leis, "completo": completo}, "leis-site.json")
    no_periodo = [x for x in leis.values() if x.get("d") and x["d"] >= ini]
    quem = {k: sum(1 for x in no_periodo if x["q"] == k) for k in ("governador", "exercicio", "promulgada", "?")}
    log(f"  gov-TO: leis no site desde {ini}: {quem}")
    lista = [{"tipo": x["t"], "numero": x["n"], "data": x["d"]} for x in no_periodo if x["q"] in ("governador", "exercicio")]
    frases, frases_en = [], []
    if quem["exercicio"]:
        frases.append(f"Inclui {quem['exercicio']} leis assinadas por quem estava no exercício do cargo de governador (o "
                      "vice-governador ou o presidente da Assembleia).")
        frases_en.append(f"Includes {quem['exercicio']} laws signed by someone acting as governor (the vice governor or the "
                         "speaker of the state assembly).")
    fora, fora_en = [], []
    if quem["promulgada"]:
        fora.append(f"{quem['promulgada']} leis promulgadas pela própria Assembleia (inclusive a conversão de medidas provisórias)")
        fora_en.append(f"{quem['promulgada']} laws promulgated by the state assembly itself (including conversions of provisional measures)")
    if quem["?"]:
        fora.append(f"{quem['?']} em que o começo do texto não diz quem assinou")
        fora_en.append(f"{quem['?']} whose opening text does not say who signed them")
    if fora:
        frases.append(f"Não entram {G.lista_pt(fora)}.")
        frases_en.append(f"Not included: {G.lista_pt(fora_en, 'and')}.")
    prom = (" ".join(frases), " ".join(frases_en)) if frases else None
    existentes = {(x["t"], x["n"]) for x in leis.values()}
    return (lista, ("sancionadas no período, pela página \"Legislação Estadual\" da Aleto (o começo de cada lei diz quem a "
                    "assinou; a Aleto publica as leis nessa página algumas semanas depois)",
                    "signed in the period, from the Aleto's \"Legislação Estadual\" page (the opening of each law says who "
                    "signed it; the Aleto posts laws on that page a few weeks later)"),
            prom, [fonte("Assembleia Legislativa do Tocantins (Aleto)", "Legislação Estadual (leis ordinárias e complementares)",
                         f"{LEIS_URL}?documento.dataInicio={ini}")], existentes)


# projetos = os tipos "do Executivo" (PLG, PLCG, PEC-G) e as medidas provisórias (MP), de quem estava no cargo no período;
# vetos = "Mensagem de Veto" (13). O SAPL registra quem mandou cada um (o governador ou o vice no exercício do cargo):
# entram todos (mesma régua do presidente) e a nota diz quantos foram de quem estava no exercício.
GOVERNO = {
    "autores": None, "tipo_autor": r"^poder executivo estadual$",
    "tipos": {2: "PL", 3: "PLP", 5: "PEC", 14: "MPV"},
    "vetos": {"tipos": [13], "parcial": r"parcial", "total": r"integral|total",
              "de_onde": ("mensagens de veto que chegaram à Aleto no período, pela data em que foram lidas",
                          "veto messages received by the Aleto in the period, by the date they were read")},
    "leis": leis_to,
    "nota_propostas": ("Medidas provisórias (MPV) valem como lei assim que o governador as publica, mas perdem a validade se a "
                       "Assembleia não as aprovar no prazo da Constituição do Tocantins.",
                       "Provisional measures (MPV) take effect as law as soon as the governor publishes them, but they lose "
                       "effect if the state assembly does not approve them within the deadline set by the Tocantins "
                       "Constitution."),
    "nota": [("Conta o que o governo do estado assinou ou mandou no período, inclusive quando outra pessoa estava no "
              "exercício do cargo de governador (o vice-governador, por exemplo).",
              "Counts what the state government signed or sent in the period, including when someone else was acting as "
              "governor (the vice governor, for example).")],
}


def coletar() -> dict:
    return Sapl(
        "TO", "https://sapl.al.to.leg.br",
        "Assembleia Legislativa do Estado do Tocantins", "Legislative Assembly of the State of Tocantins",
        "Aleto", SITE, "Assembleia Legislativa do Tocantins (Aleto)", "aleto",
        {1: "PL", 26: "PLP", 4: "PEC", 36: "PEC", 37: "PDL", 15: "PRC"}, REGRAS, "aleto",
        lista_oficial=lista_oficial, ambiguos=AMBIGUOS, governo=GOVERNO, sic=f"{SITE}/loginExterno/sic",
        lista_url=f"{SITE}/perfil", lista_titulo="Perfil dos deputados em exercício (página oficial)",
        notas=[NOTA_VOTOS_GASTOS],
    ).coletar()


NOTA_VOTOS_GASTOS = (
    "As votações e os gastos não entram. Votações: o SAPL da Aleto não tem nenhuma votação registrada. Gastos: a Aleto "
    "publica a verba indenizatória (CODAP) de cada deputado num documento PDF por mês, no Portal da Transparência, sem o tipo "
    "de cada despesa e com um formato que muda de um ano para outro.",
    "Votes and spending are not included. Votes: the Aleto SAPL system has no votes recorded. Spending: the Aleto publishes "
    "each deputy's expense allowance (CODAP) as one PDF document per month on its transparency portal, without the type of "
    "each expense and in a layout that changes from year to year.")
