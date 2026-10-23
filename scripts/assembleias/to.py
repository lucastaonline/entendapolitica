"""Assembleia Legislativa do Estado do Tocantins (Aleto): lista oficial no site da Casa + propostas no SAPL 3.

Lista oficial: https://www.al.to.leg.br/perfil (os 24 deputados em exercício, com partido, foto, e-mail e redes). O SAPL
da Aleto (https://sapl.al.to.leg.br/api/) não traz o partido e marca como ativo quem já saiu, por isso a lista vem do site;
cada pessoa do site é ligada à sua ficha no SAPL pelo nome. Propostas: matérias do SAPL desde 1º/2/2023 (os tipos "da
Casa": PL, PLP, PEC, PDL e PRC dos deputados); situação = a da última tramitação; "virou lei" = norma jurídica ligada à
proposta no SAPL. O SAPL do Tocantins não tem votações registradas.
"""
from __future__ import annotations

import re

import regional
from comum import log

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


def coletar() -> dict:
    return Sapl(
        "TO", "https://sapl.al.to.leg.br",
        "Assembleia Legislativa do Estado do Tocantins", "Legislative Assembly of the State of Tocantins",
        "Aleto", SITE, "Assembleia Legislativa do Tocantins (Aleto)", "aleto",
        {1: "PL", 26: "PLP", 4: "PEC", 36: "PEC", 37: "PDL", 15: "PRC"}, REGRAS, "aleto",
        lista_oficial=lista_oficial, ambiguos=AMBIGUOS,
        lista_url=f"{SITE}/perfil", lista_titulo="Perfil dos deputados em exercício (página oficial)",
    ).coletar()
