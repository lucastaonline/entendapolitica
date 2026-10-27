"""Assembleia Legislativa do Estado do Amapá (Alap).

Lista oficial: a página da legislatura atual no site da Alap (pagina.php?pg=exibir_legislatura&idlegislatura=<id>: "IX
Legislatura (2023 / 2027) [Atual]", "Membros"), que traz só quem está no cargo (inclusive os suplentes que assumiram), com
nome, nome completo, partido e foto, e a página de cada deputado (pagina.php?pg=exibir_parlamentar&iddeputado=<id>: nome
civil, e-mail, legislaturas e "Situação: Ativo"/"Inativo"). Quem saiu continua na lista "Filtrar" da página de cada
deputado, com "Situação: Inativo". A legislatura marcada como atual tem de ser a do calendário e cada pessoa da lista tem
de estar "Ativo" na própria página; senão nada é gravado (fica o arquivo de antes). A página "Parlamentares" do menu, sem
o número da legislatura, saiu vazia em outubro de 2026.
Gastos: CEAP (Cota para o Exercício da Atividade Parlamentar), no Portal da Transparência da Alap
(https://www.al.ap.leg.br/transparencia/pagina.php?pg=ceap). Para um gabinete e um mês, a página mostra o valor de cada tipo
de despesa (o nome vem com o código contábil, que sai) e o TOTAL do mês, e também o valor de cada mês do ano daquele
gabinete (pagamentos complementares, "(compl.)", aparecem à parte; a tabela do mês já os soma). Lemos a lista de meses de
cada ano e a de gabinetes de cada mês (cada gabinete é "NOME - PARTIDO", ligado pelo nome à pessoa da lista de hoje); uma
página por gabinete e ano, que dá o valor de cada mês; e, no ano mais recente de cada pessoa, a página de cada mês, que dá
os tipos de despesa. Período: desde fevereiro de 2023 (começo da legislatura).
Propostas dos deputados e perfil do governador (projetos do Executivo, leis sancionadas e vetos): e-Legis da Alap
(https://elegis.al.ap.leg.br/portal), lido por _ap_elegis.py (listas por tipo e ano, a página de cada proposição, o
cadastro de legislação em CSV e as mensagens de veto). Primeira carga longa (~2.450 pedidos, ~78 min): continua nos dias
seguintes; enquanto não termina, cada perfil fica com o bloco de antes e o arquivo do governador não muda.
Votações: NÃO entram (motivo em NOTAS).
"""
from __future__ import annotations

import datetime as dt
import html as _html
import re
import time
import urllib.parse

import regional
from comum import fonte, hoje, log, sem_acento

from . import _ap_elegis as EL
from . import _carga
from . import _nco_comum as _N
from . import _nco_gov as G
from ._nco_comum import (Rede, SemTempo, casar_membros, conferir_virada, gravar, legislatura_por_data, limpa_civil, limpa_nome,
                         membro, nome_civil, partido_sigla, texto_html)
from ._votos_gastos import Nomes, aplicar, bloco_gastos, de_antes, mes_br, valor_br

SITE = "https://www.al.ap.leg.br"
TRANSP = f"{SITE}/transparencia"
CEAP = f"{TRANSP}/pagina.php?pg=ceap"
VEICULO = "Assembleia Legislativa do Amapá (Alap)"
VAGAS = 24
PAUSA = 1.5  # segundos entre dois pedidos ao site da Alap (o robots.txt responde 403: sem regras, RFC 9309)
CASA = {"casa": "Assembleia Legislativa do Estado do Amapá", "casa_en": "Legislative Assembly of the State of Amapá",
        "sigla": "Alap", "site": SITE,
        # e-SIC da Alap (Lei de Acesso à Informação): o formulário do Portal da Transparência (pg=esic explica o canal)
        "sic": f"{TRANSP}/pagina.php?pg=form_esic"}
# conferido à mão (26/10/2026): os 24 da lista oficial casam sozinhos com o TSE de 2022 (Pedro Filé e Rodolfo Vale são
# suplentes: SQ 30001604019, PDT, e 30001607455, PCdoB em 2022). {nome na lista oficial: SQ do TSE de 2022 ou "-"}
TSE_MANUAL: dict[str, str] = {}
# nomes da CEAP que a regra comum (Nomes) não liga sozinha: {nome como a CEAP escreve: id da pessoa ou "-"}
CEAP_MANUAL: dict[str, str] = {}
NOME_CEAP = ("Cota para o Exercício da Atividade Parlamentar (CEAP)",
             "Office allowance (CEAP)")
ORCAMENTO_S = 240  # limite diário (segundos) da leitura da CEAP; na primeira carga, a rodada toda (_carga.limite_diario)
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]
ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50}

NOTA_LISTA = ("Quem está no cargo: a lista de membros da legislatura atual no site da Alap, conferida com a situação de cada "
              "deputado (\"Ativo\") na página dele. Suplentes que assumiram aparecem marcados.",
              "Who is in office: the member list of the current term on the Alap website, checked against each deputy's "
              "status (\"Ativo\", active) on their own page. Substitutes who took a seat are marked.")
NOTA_GASTOS = ("Gastos: CEAP (Cota para o Exercício da Atividade Parlamentar), do Portal da Transparência da Alap, desde "
               "fevereiro de 2023: o valor de cada mês, com os pagamentos complementares, e, no ano mais recente, o total de "
               "cada tipo de despesa.",
               "Spending: the office allowance (CEAP), from the Alap transparency portal, since February 2023: the amount "
               "for each month, including supplementary payments, and, for the latest year, the total for each type of "
               "expense.")
NOTA_PROPOSTAS = ("Propostas: as do e-Legis, o sistema do processo legislativo da Alap (elegis.al.ap.leg.br), desde 1º/2/2023. "
                  "A situação de cada uma sai da página dela no e-Legis: a norma que ela gerou ou a movimentação mais recente "
                  "que decide (sanção, veto, arquivamento, rejeição na Comissão de Constituição e Justiça...). O próprio "
                  "e-Legis avisa que o processo legislativo mudou para esse sistema e que, durante a mudança, as informações "
                  "podem não aparecer em tempo real.",
                  "Bills: those in e-Legis, the Alap's legislative process system (elegis.al.ap.leg.br), since February 1, "
                  "2023. The status of each one comes from its page in e-Legis: the law or decree it became, or the latest "
                  "decisive step (signature, veto, shelving, rejection by the Constitution and Justice Committee...). e-Legis "
                  "itself warns that the legislative process moved to this system and that, during the move, the information "
                  "may not appear in real time.")
NOTA_SEM_PROPOSTAS = ("As propostas de cada deputado não entram aqui: elas estão no e-Legis da Alap (elegis.al.ap.leg.br), "
                      "que não respondeu por inteiro na última leitura deste site.",
                      "Each deputy's bills are not included here: they are in the Alap's e-Legis system "
                      "(elegis.al.ap.leg.br), which did not respond in full the last time this site read it.")
NOTA_VOTACOES = ("As votações de cada deputado não entram: o e-Legis mostra, na página de cada proposição votada, uma lista de "
                 "votos da sessão, mas não diz se a votação foi nominal (cada deputado vota no painel) ou simbólica; numa "
                 "amostra de 40 dessas listas, de 2023 a 2026, todos os votos são \"favorável\" ou \"sem voto\".",
                 "Each deputy's votes are not included: e-Legis shows, on the page of each bill that was voted on, a list of "
                 "votes from that session, but it does not say whether the vote was a roll call (each member votes on the "
                 "panel) or a symbolic one; in a sample of 40 of these lists, from 2023 to 2026, every vote is \"in favor\" "
                 "or \"no vote\".")


def notas_casa(com_propostas: bool, el: dict | None) -> list[tuple[str, str]]:
    """As notas da Casa: lista, gastos, propostas (com as contas da última leitura do e-Legis, quando houver) e votações."""
    notas = [NOTA_LISTA, NOTA_GASTOS]
    if not com_propostas:
        return notas + [NOTA_SEM_PROPOSTAS, NOTA_VOTACOES]
    notas.append(NOTA_PROPOSTAS)
    n = (el or {}).get("coletivos")
    pt = ("Autoria: quando a origem de um projeto tem mais de um nome, o primeiro é o autor principal e os outros "
          "assinaram junto. Os projetos de \"Deputados Diversos\"" + (f" ({n})" if n else "") + " não entram no perfil de "
          "ninguém, porque o e-Legis não diz quais deputados assinaram.")
    en = ("Authorship: when a bill's origin lists more than one name, the first one is the main author and the others "
          "co-signed. The bills whose origin is listed only as \"several deputies\"" + (f" ({n})" if n else "") + " are not "
          "in anyone's profile, because e-Legis does not say which deputies signed them.")
    notas.append((pt, en))
    k = (el or {}).get("ocultas")
    if k:
        notas.append((f"A busca de proposições do e-Legis conta {k} projeto{'s' if k > 1 else ''} do período que a lista não "
                      f"mostra (o número entra na contagem, mas não há página para abrir): {'eles não entram' if k > 1 else 'ele não entra'}.",
                      f"The e-Legis bill search counts {k} bill{'s' if k > 1 else ''} from the period that its list does not "
                      f"show (included in the count, but with no page to open), so {'they are' if k > 1 else 'it is'} not "
                      "included."))
    return notas + [NOTA_VOTACOES]


# ---------------------------------------------------------------- ajudas
def _partido(txt: str | None) -> str | None:
    """'REDE SUSTENTABILIDADE - REDE', 'PARTIDO VERDE - PV', 'PV (PARTIDO VERDE)', 'UNIÃO BRASIL (UNIÃO)', 'REPUBLICANO'
    -> a sigla do resto do site."""
    t = re.sub(r"\s+", " ", txt or "").strip()
    if not t:
        return None
    conhecidas = {s for _, s in getattr(_N, "_PARTIDOS", [])}
    for p in [t] + [x.strip() for x in re.split(r"\s+-\s+|[()]", t) if x.strip()]:
        s = partido_sigla(re.sub(r"(?i)^republicano$", "REPUBLICANOS", p))
        if s in conhecidas:
            return s
    return partido_sigla(t)


def _romano(s: str) -> int | None:
    n, ant = 0, 0
    for ch in reversed((s or "").upper()):
        v = ROMANOS.get(ch)
        if not v:
            return None
        n, ant = (n - v, ant) if v < ant else (n + v, v)
    return n or None


def _foto(src: str | None) -> str | None:
    """'fotodeputado/230828122115Aldilene Souza.jpg' -> endereço completo em https (os endereços antigos do mesmo servidor,
    como http://www.al.ap.gov.br/fotodeputado/..., vão para o domínio do site, que responde em https)."""
    if not src:
        return None
    p = urllib.parse.urlsplit(urllib.parse.urljoin(SITE + "/", _html.unescape(src.strip())))
    host = "www.al.ap.leg.br" if re.search(r"(^|\.)al\.ap\.(leg|gov)\.br$", p.netloc.lower()) else p.netloc
    return urllib.parse.urlunsplit(("https", host, urllib.parse.quote(urllib.parse.unquote(p.path)), p.query, ""))


def _dia_da_semana(chave: str) -> bool:
    """Rodízio: cada página de deputado é lida de novo uma vez por semana, no "seu" dia."""
    return dt.date.fromisoformat(hoje()).toordinal() % 7 == int(re.sub(r"\D", "", chave) or 0) % 7


def _conserta(s: str) -> str:
    """Nomes gravados duas vezes em UTF-8 na lista de gabinetes da CEAP: 'SERRÃ\\x83O' -> 'SERRÃO'."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


# ---------------------------------------------------------------- quem está no cargo
def _legislatura(rede: Rede, leg: dict) -> tuple[str, str, str]:
    """(id, título, html) da legislatura que o site marca como "[Atual]"; tem de ser a do calendário (posse de 1º/2)."""
    est = rede.estado("legislatura.json", {}) or {}
    lid = str(est.get("id") or "9")
    for _ in range(3):
        url = f"{SITE}/pagina.php?pg=exibir_legislatura&idlegislatura={lid}"
        html = rede.texto(url, f"legislatura-{lid}.html", 20)
        atual = re.search(r'<option value="pagina\.php\?pg=exibir_legislatura&idlegislatura=(\d+)"[^>]*>\s*([^<]*?)\s*'
                          r'\[Atual\]\s*</option>', html)
        if not atual:
            raise RuntimeError("AP: a página de legislaturas do site mudou (nenhuma marcada como [Atual])")
        if atual.group(1) == lid:
            break
        lid = atual.group(1)
    else:
        raise RuntimeError("AP: a legislatura marcada como [Atual] muda a cada página")
    titulo = re.sub(r"\s+", " ", _html.unescape(atual.group(2))).strip()
    anos = re.search(r"\((\d{4})\s*/\s*(\d{4})\)", titulo)
    if not anos or anos.group(1) != leg["inicio"][:4]:
        raise RuntimeError(f"AP: o site marca como atual a \"{titulo}\", mas a legislatura de hoje começou em {leg['inicio']}")
    if est.get("id") != lid:
        rede.guardar({"id": lid}, "legislatura.json")
    return lid, titulo, html


def _membros_pagina(html: str) -> list[dict]:
    """Os membros da página da legislatura: id, nome, gênero ("Deputada"/"Deputado"), nome completo, partido e foto."""
    out = []
    for did, miolo, titulo, nome in re.findall(
            r'<div class="box-foto-deputados">\s*<a href="pagina\.php\?pg=exibir_parlamentar&(?:amp;)?iddeputado=(\d+)"'
            r'((?:(?!</a>).)*)</a>\s*</div>\s*<p class="ls-title-5">\s*(Deputad[oa])\s+(.*?)\s*</p>', html, re.S):
        tip = re.search(r"Tip\('(.*?)'\s*,\s*WIDTH", miolo, re.S)
        tip = tip.group(1) if tip else ""
        civil = re.search(r"Nome Completo:</b>\s*(.*?)\s*<br>", tip)
        partido = re.search(r"Partido:</b>\s*(.*?)\s*<br>", tip)
        foto = re.search(r'<img class="foto-deputado" src="([^"]+)"', miolo)
        out.append({"id": did, "nome": texto_html(nome), "genero": "F" if titulo.endswith("a") else "M",
                    "civil": texto_html(civil.group(1)) if civil else None,
                    "partido": texto_html(partido.group(1)) if partido else None,
                    "foto": foto.group(1) if foto else None})
    return out


def _perfil(html: str) -> dict:
    """Os campos da página de um deputado ("Nome Civil", "E-mail", "Partido", "Legislatura(s)", "Situação"...), com as
    chaves sem acento e em minúsculas; mais a lista "Filtrar" (todos os deputados da legislatura)."""
    i = html.find('<h5 class="ls-title-5">Perfil:')
    seg = html[i:html.find("box-proposicoes", i)] if i >= 0 else ""
    campos = {sem_acento(r).strip().lower(): texto_html(v) for r, v in re.findall(
        r"<b>\s*([^<:]+?)\s*:\s*</b>\s*</p>\s*</div>\s*<div[^>]*>(.*?)</div>", seg, re.S)}
    campos["_filtrar"] = [(d, texto_html(n)) for d, n in re.findall(
        r'<option value="pagina\.php\?pg=exibir_parlamentar&(?:amp;)?iddeputado=(\d+)"[^>]*>(.*?)</option>', html, re.S)]
    return campos


def lista_oficial(rede: Rede, leg: dict) -> tuple[list[dict], dict, list[str]]:
    """([pessoas da lista oficial, com os campos da página de cada uma], {"id", "titulo", "numero", "url"} da legislatura,
    [nomes de quem foi deputado nesta legislatura e saiu (lista "Filtrar" menos a lista de hoje)])."""
    lid, titulo, html = _legislatura(rede, leg)
    lista = _membros_pagina(html)
    if len(lista) < VAGAS - 4:
        raise RuntimeError(f"AP: a página da legislatura mudou (só {len(lista)} membros)")
    if len(lista) > VAGAS:  # mais gente do que vagas: a lista não diz quem está no cargo hoje
        raise RuntimeError(f"AP: a página da legislatura traz {len(lista)} membros para {VAGAS} vagas; nada gravado")
    if len({l["id"] for l in lista}) != len(lista):
        raise RuntimeError("AP: a página da legislatura repete deputados")
    est = rede.estado("membros.json", {}) or {}
    ids = sorted(l["id"] for l in lista)
    mudou = est.get("ids") != ids  # a lista mudou: lê de novo a página de todo mundo
    todos: dict[str, str] = {}
    for l in lista:
        url = f"{SITE}/pagina.php?pg=exibir_parlamentar&iddeputado={l['id']}"
        ttl = 0 if mudou else (20 if _dia_da_semana(l["id"]) else 24 * 8)
        p = _perfil(rede.texto(url, f"deputado/{l['id']}.html", ttl))
        if sem_acento(p.get("situacao") or "").lower() != "ativo" and ttl:  # página guardada antiga: confere de novo
            p = _perfil(rede.texto(url, f"deputado/{l['id']}.html", 0))
        if sem_acento(p.get("situacao") or "").lower() != "ativo":
            raise RuntimeError(f"AP: {l['nome']} está na lista da legislatura, mas a página dele diz "
                               f"\"Situação: {p.get('situacao') or '?'}\"; nada gravado")
        if not p.get("legislatura(s)") or titulo.split("(")[-1].rstrip(")").strip() not in p["legislatura(s)"]:
            log(f"  AP: ATENÇÃO: a página de {l['nome']} não cita a legislatura {titulo}")
        l["perfil"] = p
        todos.update({d: n for d, n in p.get("_filtrar") or []})
    if mudou:
        rede.guardar({"ids": ids}, "membros.json")
    if len(lista) < VAGAS:
        log(f"  AP: ATENÇÃO: {len(lista)} pessoas na lista oficial (a Casa tem {VAGAS} vagas)")
    num = _romano(titulo.split()[0]) if titulo else None
    info = {"id": lid, "titulo": titulo, "numero": num,
            "url": f"{SITE}/pagina.php?pg=exibir_legislatura&idlegislatura={lid}"}
    sairam = [re.split(r"\s+-\s+", n, maxsplit=1)[0].strip() for d, n in todos.items() if d not in set(ids)]
    return lista, info, sairam


# ---------------------------------------------------------------- CEAP (cota parlamentar)
def _url_tabela(ano: int, mes: int, gab: str) -> str:
    return f"{CEAP}&acao=buscar&ano_verbaB={ano}&mes_verbaB={mes:02d}&idgabineteB={gab}"


def _post(**campos) -> bytes:
    return urllib.parse.urlencode(campos).encode()


def _meses(rg: Rede, ano: int, ano_hoje: int) -> list[int]:
    """Os meses com a CEAP publicada num ano (o seletor do site). Ano passado com os 12 meses: fica no cache para sempre."""
    url, nome = f"{TRANSP}/mes_ceap_json.php", f"meses/{ano}.html"
    ler = lambda ttl: sorted({int(m) for m in re.findall(r'<option value="(\d{1,2})"',
                                                          rg.texto(url, nome, ttl, dados=_post(ano_verbaB=ano)))})
    ms = ler(None if ano < ano_hoje else 20)
    if ano < ano_hoje and len(ms) < 12:
        ms = ler(20)
    return [m for m in ms if 1 <= m <= 12]


def _gabinetes(rg: Rede, ano: int, mes: int, ttl: float | None) -> dict[str, str]:
    """{id do gabinete: "NOME - PARTIDO"} dos gabinetes com CEAP num mês."""
    h = rg.texto(f"{TRANSP}/gabinete_ceap_json.php", f"gabinetes/{ano}-{mes:02d}.html", ttl,
                 dados=_post(ano_verbaB=ano, mes_verbaB=f"{mes:02d}"))
    return {g: re.sub(r"\s+", " ", _conserta(_html.unescape(n))).strip()
            for g, n in re.findall(r'<option value="(\d+)"[^>]*>(.*?)</option>', h, re.S)}


def _nome_gabinete(rotulo: str) -> str:
    """'ROBERTO GOES -UNIÃO' / 'OLIVEIRA SANTOS  -  REPUBLICANOS' -> o nome (o partido vem depois do primeiro hífen com
    espaço de um dos lados)."""
    return re.split(r"\s+-\s*|\s*-\s+", rotulo, maxsplit=1)[0].strip()


def _rotulo_mes(txt: str) -> tuple[str, bool] | None:
    """'Março/2026 (compl.)' -> ('2026-03', True)."""
    t = re.sub(r"\s+", " ", _html.unescape(txt or "")).strip()
    m = mes_br(re.sub(r"\s*\(.*?\)\s*", "", t))
    return (m, bool(re.search(r"(?i)\(\s*compl", t))) if m else None


def _caixas_grafico(h: str) -> list[list]:
    """O valor de cada mês do ano no gráfico da página (categorias e valores do Highcharts): está também nas páginas sem
    resultado ("Nenhum resultado foi encontrado"), que não têm os quadros com os meses."""
    cat = re.search(r"categories:\s*\[(.*?)\]", h, re.S)
    dados = re.search(r"series:\s*\[\s*\{.*?data:\s*\[(.*?)\]", h, re.S)
    if not cat or not dados:
        return []
    rotulos = re.findall(r'"([^"]*)"', cat.group(1))
    valores = [x.strip() for x in dados.group(1).split(",") if x.strip()]
    if len(rotulos) != len(valores):
        raise RuntimeError("AP CEAP: o gráfico do ano mudou (meses e valores com tamanhos diferentes)")
    out = []
    for rot, v in zip(rotulos, valores):
        r = _rotulo_mes(rot)
        if r:
            out.append([r[0], r[1], round(float(v), 2)])
    return out


def _tabela(h: str, ano: int, mes: int) -> dict:
    """A página de um gabinete num mês -> {"ref", "linhas": [[tipo, valor]], "total", "caixas": [["AAAA-MM", compl., valor]]}.
    Confere: o mês da página é o pedido, a soma dos tipos é o TOTAL e os quadros dos meses batem com o gráfico do ano.
    Mês sem despesa ("Nenhum resultado foi encontrado"): sem linhas, total 0; os meses do ano vêm do gráfico."""
    grafico = _caixas_grafico(h)
    ref = re.search(r"Ref\.:\s*<h5>(.*?)</h5>\s*\(([^)]*)\)", h, re.S)
    if not ref:
        sel = {}
        for campo, opcoes in re.findall(r'<select id="(ano_verbaB|mes_verbaB)"[^>]*>((?:(?!</select>).)*)</select>', h, re.S):
            s = re.search(r'<option value="(\d+)"\s*selected', opcoes)
            sel[campo] = s.group(1) if s else None
        if re.search(r"Nenhum:?\s*(</strong>)?\s*resultado foi encontrado", h) and \
                sel.get("ano_verbaB") == str(ano) and sel.get("mes_verbaB") == f"{mes:02d}":
            return {"ref": None, "linhas": [], "total": 0.0, "caixas": grafico}
        raise RuntimeError(f"AP CEAP: a página de {mes:02d}/{ano} mudou (sem o resultado da consulta)")
    rm = _rotulo_mes(ref.group(2))
    if not rm or rm[0] != f"{ano}-{mes:02d}":
        raise RuntimeError(f"AP CEAP: pedi {mes:02d}/{ano} e a página respondeu \"{texto_html(ref.group(2))}\"")
    linhas = []
    for desc, val in re.findall(r'<tr>\s*<td>\s*<strong>\s*<a[^>]*>(.*?)</a>\s*</strong>\s*</td>\s*'
                                r'<td class="ls-txt-right">\s*<strong>\s*(-?[\d.,]+)\s*</strong>', h, re.S):
        tipo = re.sub(r"^\s*[\d.]+\s*-\s*", "", texto_html(desc)).strip() or "Outros"
        linhas.append([tipo, valor_br(val)])
    tot = re.search(r"<h5>\s*TOTAL\s*</h5>\s*</td>\s*<td[^>]*>\s*<h5>\s*(-?[\d.,]+)\s*</h5>", h)
    total = valor_br(tot.group(1)) if tot else 0.0
    if abs(sum(v for _, v in linhas) - total) > 0.011:
        raise RuntimeError(f"AP CEAP: {texto_html(ref.group(1))} {mes:02d}/{ano}: a soma dos tipos "
                           f"({sum(v for _, v in linhas):.2f}) não bate com o TOTAL ({total:.2f})")
    caixas = []
    k = h.find('id="sending-stats"')
    for bloco in (re.split(r'<div class="ls-box-head">', h[k:])[1:] if k >= 0 else []):
        rot = re.search(r"<h6[^>]*>(.*?)</h6>", bloco, re.S)
        val = re.search(r"<h1>\s*(-?[\d.,]+)\s*</h1>", bloco)
        r = _rotulo_mes(texto_html(rot.group(1))) if rot else None
        if r and val:
            caixas.append([r[0], r[1], valor_br(val.group(1))])
    if grafico and caixas and ([(c[0], c[1]) for c in caixas] != [(c[0], c[1]) for c in grafico]
                               or any(abs(a[2] - b[2]) > 0.011 for a, b in zip(caixas, grafico))):
        log(f"  AP CEAP: ATENÇÃO: {texto_html(ref.group(1))} {mes:02d}/{ano}: os quadros dos meses não batem com o gráfico "
            f"do ano; valem os quadros")
    caixas = caixas or grafico
    if total and round(sum(c[2] for c in caixas if c[0] == f"{ano}-{mes:02d}"), 2) == 0:
        raise RuntimeError(f"AP CEAP: {texto_html(ref.group(1))} {mes:02d}/{ano}: sem o valor de cada mês do ano")
    return {"ref": texto_html(ref.group(1)), "linhas": linhas, "total": round(total, 2), "caixas": caixas}


def gastos(rg: Rede, membros: list[dict], sairam: list[str]) -> dict[str, dict] | None:
    """{id da pessoa: bloco "gastos"} da CEAP desde o começo da legislatura; None enquanto a primeira carga não terminou
    (cada perfil fica com o bloco de antes: aplicar). sairam = quem foi deputado nesta legislatura e saiu (para conferir
    que só eles ficam sem ligação)."""
    ini = regional.inicio_estadual("AP")
    a0, m0 = int(ini[:4]), int(ini[5:7])
    hj = hoje()
    ah, mh = int(hj[:4]), int(hj[5:7])
    recente = lambda a, m: (ah * 12 + mh) - (a * 12 + m) <= 3
    # 1) os meses publicados de cada ano e os gabinetes de cada mês (pequenos; os antigos ficam no cache para sempre)
    gabs: dict[tuple[int, int], dict[str, str]] = {}
    for ano in range(a0, ah + 1):
        for mes in _meses(rg, ano, ah):
            if (ano, mes) >= (a0, m0):
                gabs[(ano, mes)] = _gabinetes(rg, ano, mes, 20 if recente(ano, mes) else None)
    if not gabs:
        raise RuntimeError("AP CEAP: nenhum mês publicado desde o começo da legislatura")
    # 2) cada gabinete, mês a mês, ligado pelo nome a uma pessoa da lista de hoje
    nomes = Nomes(membros, CEAP_MANUAL)
    dono: dict[tuple[int, int, str], str] = {}
    for (ano, mes), gs in gabs.items():
        for g, rot in gs.items():
            pid = nomes.quem(_nome_gabinete(rot))
            if pid:
                dono[(ano, mes, g)] = pid
    ex = Nomes([{"id": n, "nome": n} for n in sairam])
    estranhos = sorted(n for n in nomes.sem if not ex.quem(n))
    if nomes.sem:
        log(f"  AP CEAP: nomes sem pessoa na lista de hoje (quem saiu): {sorted(nomes.sem)}")
    if estranhos:
        log(f"  AP CEAP: ATENÇÃO: nomes sem ligação que também não são de quem saiu (grafia diferente?): {estranhos}")
    por_ga: dict[tuple[str, int], dict[int, str]] = {}  # (gabinete, ano) -> {mês: pessoa}
    for (ano, mes, g), pid in dono.items():
        por_ga.setdefault((g, ano), {})[mes] = pid
    # 3) as páginas a ler: uma por gabinete e ano (o último mês: dá o valor de cada mês do ano) e, no ano mais recente de
    # cada pessoa, todas (os tipos de despesa). O último mês publicado é relido a cada 20 h; os outros ficam no cache e só
    # são relidos quando o valor do mês mostrado numa página mais nova muda (pagamento complementar lançado depois).
    ano_de: dict[str, int] = {}
    for (g, ano), ms in por_ga.items():
        for pid in ms.values():
            ano_de[pid] = max(ano_de.get(pid, 0), ano)
    tabs: dict[tuple[int, int, str], dict] = {}

    def nome_cache(a, m, g):
        return f"tabelas/{a}-{m:02d}-{g}.json"

    def idade_h(nome):
        arq = rg.pasta / nome
        return (time.time() - arq.stat().st_mtime) / 3600 if arq.exists() else None

    def precisa(a, m, g, ttl) -> bool:
        i = idade_h(nome_cache(a, m, g))
        return i is None or (ttl is not None and i >= ttl)

    def tabela(a, m, g) -> dict | None:
        if (a, m, g) not in tabs:
            tabs[(a, m, g)] = rg.estado(nome_cache(a, m, g))
        return tabs[(a, m, g)]

    def mes_caixas(g, ano) -> int:
        """O mês cuja página dá os valores do ano do gabinete: o último listado (se a página dele vier sem os valores do
        ano, o anterior)."""
        ms = sorted(por_ga[(g, ano)], reverse=True)
        for m in ms:
            if idade_h(nome_cache(ano, m, g)) is None or (tabela(ano, m, g) or {}).get("caixas"):
                return m
        return ms[0]

    def caixas(g, ano) -> dict[int, float]:
        """{mês: valor do mês (com os complementos)} de um gabinete num ano."""
        t = tabela(ano, mes_caixas(g, ano), g) or {}
        out: dict[int, float] = {}
        for mm, _, v in t.get("caixas") or []:
            if mm.startswith(f"{ano}-"):
                out[int(mm[5:])] = round(out.get(int(mm[5:]), 0) + v, 2)
        return out

    def pedidas(anos_de: dict[str, int]) -> dict[tuple[int, int, str], float | None]:
        out: dict[tuple[int, int, str], float | None] = {}
        for (g, ano), ms in por_ga.items():
            u = mes_caixas(g, ano)
            out[(ano, u, g)] = 20 if recente(ano, max(ms)) else None
            for mes, pid in ms.items():
                if ano == anos_de.get(pid):
                    out.setdefault((ano, mes, g), None)
        return out

    def ler(anos_de: dict[str, int], t0: float, limite: float) -> bool:
        """Lê as páginas que faltam (as mais recentes primeiro) até o limite de tempo; True se leu todas. Repete enquanto a
        página escolhida para os valores do ano muda (página de um mês sem os valores do ano)."""
        for _ in range(13):
            fila = [(k, ttl) for k, ttl in sorted(pedidas(anos_de).items(), reverse=True) if precisa(*k, ttl)]
            if not fila:
                return True
            for (a, m, g), _ttl in fila:
                if time.time() - t0 >= limite or _carga.acabou():
                    return False
                try:
                    h = rg.texto(_url_tabela(a, m, g), None, 0)
                except SemTempo:  # o fim da rodada chegou durante a espera entre pedidos
                    return False
                c = _tabela(h, a, m)
                rg.guardar(c, nome_cache(a, m, g))
                tabs[(a, m, g)] = c
        return True

    faltam = sum(1 for (a, m, g) in pedidas(ano_de) if idade_h(nome_cache(a, m, g)) is None)
    primeira = faltam > 40
    t0, limite = time.time(), _carga.limite_diario(ORCAMENTO_S, primeira)
    completo = ler(ano_de, t0, limite)

    # o ano mostrado de cada pessoa é o mais recente com valor (um mês listado pode vir zerado)
    if completo:
        ano_val: dict[str, int] = {}
        for (g, ano), ms in por_ga.items():
            cx = caixas(g, ano)
            for mes, pid in ms.items():
                if cx.get(mes):
                    ano_val[pid] = max(ano_val.get(pid, 0), ano)
        if ano_val != {p: a for p, a in ano_de.items() if p in ano_val}:
            completo = ler(ano_val, t0, limite)
        ano_de = ano_val
    # pagamento complementar lançado depois: o valor do mês na página mais nova do ano não bate com o TOTAL guardado do mês
    # (só relê quando a página do mês é mais velha que a dos valores do ano: se as duas são novas, é diferença do site)
    relidos = 0
    if completo:
        for (g, ano), ms in por_ga.items():
            cx = caixas(g, ano)
            mc = mes_caixas(g, ano)
            i_cx = idade_h(nome_cache(ano, mc, g)) or 0
            for mes, pid in ms.items():
                if ano != ano_de.get(pid) or mes == mc:
                    continue
                t = tabela(ano, mes, g)
                if t and abs(t["total"] - cx.get(mes, 0)) > 0.011 and (idade_h(nome_cache(ano, mes, g)) or 0) > i_cx + 0.1:
                    if time.time() - t0 >= limite or _carga.acabou():
                        completo = False
                        break
                    tabs[(ano, mes, g)] = _tabela(rg.texto(_url_tabela(ano, mes, g), None, 0), ano, mes)
                    rg.guardar(tabs[(ano, mes, g)], nome_cache(ano, mes, g))
                    relidos += 1
    pedidas_total = len(pedidas(ano_de))
    lidas = sum(1 for (a, m, g) in pedidas(ano_de) if idade_h(nome_cache(a, m, g)) is not None)
    if not completo:
        log(f"  AP CEAP: {'primeira carga' if primeira else 'leitura'} em andamento: {lidas} de {pedidas_total} páginas de "
            f"gabinete lidas; continua na próxima rodada (os perfis ficam com o bloco de antes)")
        return None
    # 4) os blocos: no ano mostrado, os tipos de cada mês; nos outros anos, o valor de cada mês
    linhas: dict[str, list[tuple[str, str, float]]] = {}
    ultimo: dict[str, tuple[int, int, str]] = {}
    avisos = []
    for (g, ano), ms in sorted(por_ga.items(), key=lambda x: (x[0][1], x[0][0])):
        cx = caixas(g, ano)
        fora = [m for m, v in cx.items() if v and m not in ms and (ano, m) >= (a0, m0)]
        if fora:
            avisos.append(f"gabinete {g} {ano}: valor nos meses {fora}, sem o gabinete na lista desses meses (não entram)")
        for mes, pid in sorted(ms.items()):
            if ano == ano_de.get(pid):
                t = tabela(ano, mes, g)
                if t is None:
                    raise RuntimeError(f"AP CEAP: falta a página do gabinete {g} em {mes:02d}/{ano}")
                if abs(t["total"] - cx.get(mes, 0)) > 0.011:
                    avisos.append(f"gabinete {g} {mes:02d}/{ano}: TOTAL {t['total']:.2f}, valor do mês {cx.get(mes, 0):.2f}")
                linhas.setdefault(pid, []).extend((f"{ano}-{mes:02d}", tipo, v) for tipo, v in t["linhas"])
                if t["total"] and (ano, mes, g) > ultimo.get(pid, (0, 0, "")):
                    ultimo[pid] = (ano, mes, g)
            elif cx.get(mes):
                linhas.setdefault(pid, []).append((f"{ano}-{mes:02d}", "-", cx[mes]))
    if avisos:
        log(f"  AP CEAP: ATENÇÃO: {len(avisos)} diferenças entre as tabelas e os valores do mês: {avisos[:5]}")
    nome_de = {m["id"]: m["nome"] for m in membros}
    out = {}
    for pid, ls in linhas.items():
        if pid not in ultimo:
            continue
        a, m, g = ultimo[pid]
        f = fonte(VEICULO, f"CEAP de {nome_de[pid]}: {MESES[m - 1]} de {a}, com o valor de cada mês do ano (Portal da "
                           f"Transparência da Alap)", _url_tabela(a, m, g))
        b = bloco_gastos(ls, f, ini, NOME_CEAP)
        if not b:
            continue
        if b["ano"] != a or any(x["tipo"] == "-" for x in b["porTipo"]):  # não deveria acontecer: fica o bloco de antes
            log(f"  AP CEAP: ATENÇÃO: {nome_de[pid]}: o ano mostrado ({b['ano']}) não é o das páginas lidas ({a}); fica o "
                f"bloco de antes")
            b = de_antes(pid, "gastos")
        if b:
            out[pid] = b
    log(f"  AP CEAP: {len(out)} pessoas com gastos; {lidas} páginas de gabinete no cache ({relidos} relidas por mudança "
        f"no valor do mês); {len(gabs)} meses desde {MESES[m0 - 1]} de {a0}")
    return out


# ---------------------------------------------------------------- tudo
def coletar() -> dict:
    t0 = time.time()
    rede = Rede("alap", pausa=PAUSA)
    leg = legislatura_por_data("02-01")
    lista, info, sairam = lista_oficial(rede, leg)
    casar = [{"chave": l["id"], "nome": limpa_nome(l["nome"]),
              "nomeCivil": limpa_civil(l["perfil"].get("nome civil") or l.get("civil")),
              "partido": _partido(l.get("partido") or l["perfil"].get("partido"))} for l in lista]
    ligados, avisos = casar_membros("AP", casar, TSE_MANUAL)
    for a in avisos:
        log(f"  AP TSE: {a}")
    fonte_lista = fonte(VEICULO, f"{info['titulo']}: membros (página oficial)", info["url"])
    membros, extras = [], {}
    for l, c in zip(lista, casar):
        cand = ligados.get(c["chave"])
        pid = regional.id_pessoa("dest", "AP", cand, c["nome"])
        url = f"{SITE}/pagina.php?pg=exibir_parlamentar&iddeputado={l['id']}"
        membros.append(membro(pid, c["nome"], nome_civil(c["nomeCivil"], c["nome"], cand), c["partido"],
                              l.get("genero") or (cand or {}).get("genero"), _foto(l.get("foto")), url,
                              bool(cand and cand["sit"] == "SUPLENTE")))
        email = (l["perfil"].get("e-mail") or "").strip()
        extras[pid] = {"links": {"oficial": url, "email": email if re.fullmatch(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", email, re.A)
                                 else None, "redes": []},
                       "fontes": [fonte_lista, fonte(VEICULO, f"Página oficial de {c['nome']}", url)]}
    # gastos: o mesmo servidor; as duas Redes dividem o robots.txt lido e a hora do último pedido (um pedido por vez)
    rg = Rede("alap-gastos", pausa=PAUSA)
    rg._robots, rg._ult = rede._robots, rede._ult
    try:
        g = gastos(rg, membros, sairam)
    except SemTempo:
        g = None
        log("  AP: gastos: o tempo da rodada acabou; a leitura continua na próxima (os perfis ficam com o bloco de antes)")
    except Exception as e:  # o site da CEAP fora do ar não derruba a Casa: ficam os blocos de antes
        g = None
        log(f"  AP: ATENÇÃO: gastos não atualizados ({type(e).__name__}: {e}); ficam os de antes")
    com_gastos = aplicar(extras, g, "gastos")
    conferir_virada(rede, "AP", [l["id"] for l in lista], leg)
    # propostas dos deputados e o perfil do governador: e-Legis (outro servidor). Enquanto a primeira carga não termina ou
    # se o e-Legis falhar, cada perfil fica com o bloco de antes e o arquivo do governador não muda
    gov = G.governo_atual("AP")
    try:
        el = EL.coletar_elegis(membros, regional.inicio_estadual("AP"), gov)
    except SemTempo:
        el = None
        log("  AP: e-Legis: o tempo da rodada acabou; a leitura continua na próxima (ficam os blocos de antes)")
    except Exception as e:  # o e-Legis fora do ar não derruba a Casa
        el = None
        log(f"  AP: ATENÇÃO: e-Legis não lido ({type(e).__name__}: {e}); ficam os blocos de antes")
    com_propostas = aplicar(extras, (el or {}).get("propostas"), "propostas")
    cobertura = {"lista": True, "propostas": com_propostas, "votacoes": False, "gastos": com_gastos}
    legislatura = {"numero": info.get("numero"), "inicio": leg["inicio"], "fim": leg["fim"]}
    notas = notas_casa(com_propostas, el)
    gv = (el or {}).get("governo")
    if gv and not gv.get("executivo"):  # leis e vetos sem conta segura: o motivo vai nas notas da Casa
        notas += gv.get("notas") or []
    r = gravar("AP", CASA, membros, extras, cobertura, fonte_lista, notas, minimo=VAGAS - 4, legislatura=legislatura)
    if gv:
        G.gravar_gov("AP", propostas=gv["propostas"], executivo=gv.get("executivo"), inicio=gov["inicio"])
    else:
        G.descartar_se_velho("AP")
    sup = sum(1 for m in membros if m.get("exercicio"))
    hosts = {h: rede.por_host.get(h, 0) + rg.por_host.get(h, 0) for h in set(rede.por_host) | set(rg.por_host)}
    log(f"  AP: {len(membros)} pessoas ({sup} suplentes), {sum(1 for x in extras.values() if x.get('gastos'))} com gastos, "
        f"{sum(1 for x in extras.values() if (x.get('propostas') or {}).get('lista'))} com propostas; "
        f"{rede.pedidos + rg.pedidos} pedidos ({', '.join(f'{h}: {n}' for h, n in sorted(hosts.items()))}) + "
        f"{(el or {}).get('pedidos', 0)} no e-Legis em {int(time.time() - t0)} s"
        + (f"; e-Legis: {el['pendente']}" if el and el.get("pendente") else ""))
    return r
