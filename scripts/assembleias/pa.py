"""Assembleia Legislativa do Estado do Pará (Alepa).

Lista oficial: https://www.alepa.pa.gov.br/Home/Page/Deputados. A página monta a lista com um componente DevExpress; a
resposta de /Institucional/CardViewDeputados (pedida com o cookie da página e o Referer) traz os códigos dos 41 deputados
em exercício, e a página de cada um (/Institucional/Deputado/<código>) traz nome, nome completo, partido, e-mail e foto.
Propostas: NÃO entram por enquanto. A busca de proposições (/Home/Page/Proposicoes) só devolve 10 resultados por vez e
muda de página por um protocolo próprio do componente (sem endereço de página ou arquivo aberto).
Votações nominais: lista oficial de cada mês (/Legislativo/CallbackPanelVotacoesNominais?ano=&mes=, a mesma que a página
/Home/Page/VotacoesNominais mostra; até 12 por mês numa página) e o detalhe de cada votação
(/Legislativo/DetalhesVotacaoNominal?IdProposicao=&IdVotacao=), com o voto de cada deputado.
"""
from __future__ import annotations

import html as _html
import re
import urllib.parse

import regional
from comum import fonte, log

from ._nco_comum import (Rede, casar_membros, conferir_virada, gravar, legislatura_por_data, limpa_civil, limpa_nome, membro,
                         nome_civil, partido_sigla, sigla_votacao, texto_html)

SITE = "https://www.alepa.pa.gov.br"
VEICULO = "Assembleia Legislativa do Pará (Alepa)"
VAGAS = 41
TSE_MANUAL: dict[str, str] = {}


class Sessao(Rede):
    """Rede com cookie de sessão (o componente da Alepa só responde dentro da sessão aberta pela página)."""

    def __init__(self, pasta: str, **kw):
        import http.cookiejar
        import urllib.request
        super().__init__(pasta, **kw)
        self._cj = http.cookiejar.CookieJar()
        self._op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cj))

    def pagina(self, url: str, referer: str | None = None) -> str:
        import gzip
        import time
        import urllib.request
        from comum import UA
        espera = self.pausa - (time.time() - self._ult)
        if espera > 0:
            time.sleep(espera)
        h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
        if referer:
            h["Referer"] = referer
        try:
            for t in range(3):
                try:
                    with self._op.open(urllib.request.Request(url, headers=h), timeout=90) as r:
                        b = r.read()
                        if r.headers.get("Content-Encoding") == "gzip":
                            b = gzip.decompress(b)
                        return b.decode("utf-8", "replace")
                except Exception:
                    if t == 2:
                        raise
                    time.sleep(5 * (t + 1))
        finally:
            self._ult = time.time()
            self.pedidos += 1
        return ""


def _foto(html: str) -> str | None:
    m = re.search(r'card-politico-img-wrapper">\s*<img src="([^"]+)"', html)
    if not m:
        return None
    u = _html.unescape(m.group(1)).replace("\\", "/").split("?")[0]
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path)), "", ""))


def lista_oficial(rede: Sessao) -> list[dict]:
    pag = f"{SITE}/Home/Page/Deputados"
    rede.pagina(pag)
    cv = rede.pagina(f"{SITE}/Institucional/CardViewDeputados", referer=pag)
    m = re.search(r"'keys':\[([^\]]*)\]", cv)
    ids = re.findall(r"'(\d+)'", m.group(1)) if m else []
    if len(ids) < VAGAS - 5:
        raise RuntimeError(f"PA: a lista de deputados mudou (só {len(ids)} códigos)")
    out = []
    for i in ids:
        h = rede.texto(f"{SITE}/Institucional/Deputado/{i}", f"perfil/{i}.html", 24 * 7)
        tit = texto_html((re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1])
        txt = texto_html(re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S))
        nome = re.sub(r"^Deputad[oa]\s+", "", tit.split(" - ")[0]).strip()
        civil = re.search(r"Nome completo:\s*(.+?)\s+(?:Nascimento|Profissão|Partido Político):", txt)
        partido = re.search(r"Partido Político:\s*(\S+)", txt)
        email = re.search(r"([\w.\-]+@alepa\.pa\.gov\.br)", txt)
        out.append({"id": i, "nome": nome, "civil": civil.group(1).strip() if civil else None,
                    "partido": partido.group(1) if partido else (tit.split(" - ")[1] if " - " in tit else None),
                    "email": email.group(1) if email else None, "foto": _foto(h),
                    "genero": "F" if re.match(r"(?i)deputada", tit) else "M" if re.match(r"(?i)deputado", tit) else None})
    return out


def _meses() -> list[tuple[int, int]]:
    import datetime as dt
    from comum import hoje
    a, m = 2023, 2
    h = dt.date.fromisoformat(hoje())
    out = []
    while (a, m) <= (h.year, h.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _palavras_voto(n: str) -> set[str]:
    return set(regional.palavras(n))


VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "nao votaram": "NR", "nao votou": "NR", "obstrucao": "Obstrução"}


def votacoes(rede: Sessao, membros: list[dict]) -> dict[str, dict]:
    """Votações nominais do Plenário: lista oficial de cada mês (/Home/Page/VotacoesNominais, até 12 por mês numa página) e
    o detalhe de cada votação (/Legislativo/DetalhesVotacaoNominal), com o voto de cada deputado."""
    import datetime as dt
    import time as _t
    from comum import DADOS, chave_nome, data_iso, hoje, salvar_json, sem_acento, sem_mudar_data
    pag = f"{SITE}/Home/Page/VotacoesNominais"
    aberta = False
    h = dt.date.fromisoformat(hoje())
    catalogo, por_pessoa, sem_nome, cheios = {}, {}, {}, []
    indice = [(m["id"], set(regional.palavras(m["nome"])), set(regional.palavras(m.get("nomeCivil")))) for m in membros]
    liga: dict[str, str | None] = {}

    def quem(nome: str) -> str | None:
        k = chave_nome(nome)
        if k not in liga:
            alvo = _palavras_voto(nome)
            ach = {pid for pid, p, c in indice if alvo and ((p and (p == alvo or ((p <= alvo or alvo <= p) and len(p & alvo) >= 2)
                                                                    or (len(p & alvo) == 1 and min(len(p), len(alvo)) == 1 and len(next(iter(p & alvo))) >= 4)))
                                                           or (c and alvo <= c and len(alvo) >= 2))}
            liga[k] = ach.pop() if len(ach) == 1 else None
        return liga[k]

    for a, m in _meses():
        nome_cache = f"votos/lista-{a}-{m:02d}.html"
        arq = rede.pasta / nome_cache
        recente = (h.year * 12 + h.month) - (a * 12 + m) < 3
        if arq.exists() and (_t.time() - arq.stat().st_mtime) / 3600 < (20 if recente else 24 * 30):
            lista = arq.read_text(encoding="utf-8")
        else:
            if not aberta:
                rede.pagina(pag)
                aberta = True
            lista = rede.pagina(f"{SITE}/Legislativo/CallbackPanelVotacoesNominais?ano={a}&mes={m}", referer=pag)
            if "pageRowCount" not in lista:
                raise RuntimeError(f"PA: a lista de votações nominais de {m}/{a} veio num formato diferente")
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(lista, encoding="utf-8")
        pc = re.search(r"'pageCount':(\d+)", lista)
        if pc and int(pc.group(1)) > 1:
            cheios.append(f"{m:02d}/{a}")
        for idp, idv, titulo in re.findall(r"href='/Legislativo/DetalhesVotacaoNominal\?IdProposicao=(\d+)&IdVotacao=(\d+)'>([^<]+)</a>", lista):
            url = f"{SITE}/Legislativo/DetalhesVotacaoNominal?IdProposicao={idp}&IdVotacao={idv}"
            det = rede.texto(url, f"votos/detalhe-{idv}.html", 24 * 30)
            corpo = det[det.find('class="pauta-container"'):]
            cab = {k: texto_html(v) for k, v in re.findall(r"<strong>([^<:]+):</strong>(.*?)</td>", corpo, re.S)}
            chave = f"alepa-vot:{idv}"
            projeto = cab.get("Projeto") or texto_html(titulo).split(" - ", 1)[-1]
            turno = cab.get("Turno")
            catalogo[chave] = {"data": data_iso(cab.get("Data")) or data_iso(titulo), "propostaId": None,
                               "proposta": sigla_votacao(projeto),
                               "descricao": ", ".join(x for x in [projeto, turno, f"autoria: {cab['Autor']}" if cab.get("Autor") else None] if x),
                               "resultado": (cab.get("Resultado") or "").capitalize() or None, "url": url}
            for secao, itens in re.findall(r'<div class="section-title">(.*?)</div>\s*<div class="votos-lista">(.*?)</div>\s*<p class="quantidade"',
                                            corpo, re.S):
                voto = VOTO.get(sem_acento(texto_html(secao).lower()), texto_html(secao).capitalize())
                cel = [texto_html(x) for x in re.findall(r'<div class="voto-item">(.*?)</div>', itens, re.S)]
                for nome in cel[0::2]:
                    pid = quem(nome)
                    if not pid:
                        sem_nome[nome] = sem_nome.get(nome, 0) + 1
                        continue
                    por_pessoa.setdefault(pid, {})[chave] = [chave, voto, catalogo[chave]["data"] or ""]
    if cheios:
        log(f"  PA votações: meses com mais de 12 votações nominais (só a 1ª página entrou): {cheios}")
    if sem_nome:
        log(f"  PA votações: nomes sem pessoa na lista de hoje: {sorted(sem_nome)[:15]}")
    fonte_v = fonte(VEICULO, "Votações nominais do Plenário (página oficial)", pag)
    arq_v = DADOS / "votacoes" / "alepa.json"
    if catalogo:
        dados = {"votacoes": dict(sorted(catalogo.items(), key=lambda kv: (kv[1]["data"] or "", kv[0]), reverse=True)),
                 "fonte": fonte_v, "atualizado": hoje()}
        salvar_json(arq_v, sem_mudar_data(dados, arq_v))
    out = {}
    for pid, d in por_pessoa.items():
        lista_v = sorted(d.values(), key=lambda x: (x[2], x[0]), reverse=True)
        resumo = {"total": len(lista_v), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
        for _, v, _ in lista_v:
            resumo[v if v in resumo else "Outro"] += 1
        out[pid] = {"escopo": "Votações nominais (com o voto de cada deputado) no Plenário da Alepa desde fevereiro de 2023",
                    "escopo_en": "Roll-call votes (where each member's vote is recorded) in the full Alepa since February 2023",
                    "resumo": resumo, "fonte": fonte_v, "arquivo": "dados/votacoes/alepa.json", "votos": [[c, v] for c, v, _ in lista_v]}
    log(f"  PA: {len(catalogo)} votações nominais; votos de {len(out)} deputados")
    return out, cheios


def coletar() -> dict:
    rede = Sessao("alepa", pausa=1.5)
    lista = lista_oficial(rede)
    casar = [{"chave": d["id"], "nome": limpa_nome(d["nome"]), "nomeCivil": limpa_civil(d["civil"]),
              "partido": partido_sigla(d["partido"])} for d in lista]
    ligados, avisos = casar_membros("PA", casar, TSE_MANUAL)
    for a in avisos:
        log(f"  PA TSE: {a}")
    fonte_lista = fonte(VEICULO, "Deputados em exercício (página oficial)", f"{SITE}/Home/Page/Deputados")
    membros, extras = [], {}
    for d, c in zip(lista, casar):
        cand = ligados.get(c["chave"])
        pid = regional.id_pessoa("dest", "PA", cand, c["nome"])
        url = f"{SITE}/Institucional/Deputado/{d['id']}"
        membros.append(membro(pid, c["nome"], nome_civil(c["nomeCivil"], c["nome"], cand), c["partido"],
                              d["genero"] or (cand or {}).get("genero"), d["foto"], url, bool(cand and cand["sit"] == "SUPLENTE")))
        extras[pid] = {"links": {"oficial": url, "email": d.get("email"), "redes": []},
                       "fontes": [fonte_lista, fonte(VEICULO, f"Perfil de {c['nome']} (página oficial)", url)]}
    leg = legislatura_por_data("02-01")
    conferir_virada(rede, "PA", [d["id"] for d in lista], leg)
    vot, cheios = votacoes(rede, membros)
    for pid, x in extras.items():
        if pid in vot:
            x["votacoes"] = vot[pid]
            x["fontes"].append(vot[pid]["fonte"])
    cobertura = {"lista": True, "propostas": False, "votacoes": bool(vot), "gastos": False}
    notas = [
        ("As propostas de cada deputado ainda não entram: a busca de proposições do site da Alepa mostra 10 resultados por vez "
         "e não tem arquivo aberto nem endereço para cada página de resultados.",
         "Each deputy's bills are not included yet: the Alepa website's bill search shows 10 results at a time and has no "
         "open data file or address for each page of results."),
    ]
    if cheios:
        notas.append((f"Votações: nos meses {', '.join(cheios)} a lista oficial tinha mais de 12 votações nominais e só a primeira "
                      "página entrou.", "Votes: in some months the official list had more than 12 roll-call votes and only the "
                      "first page was included."))
    r = gravar("PA", {"casa": "Assembleia Legislativa do Estado do Pará", "casa_en": "Legislative Assembly of the State of Pará",
                      "sigla": "Alepa", "site": SITE}, membros, extras, cobertura, fonte_lista, notas, minimo=VAGAS - 5,
               legislatura=leg)
    if len(membros) != VAGAS:
        log(f"  PA: ATENÇÃO: {len(membros)} pessoas na lista oficial (a Casa tem {VAGAS} vagas)")
    log(f"  PA: {rede.pedidos} pedidos ao site oficial")
    return r
