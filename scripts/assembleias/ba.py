"""Assembleia Legislativa do Estado da Bahia (Alba): portal legislativo (SPL) com API pública
(https://albalegis.nopapercloud.com.br/api/publico/, documentada em https://albalegis.nopapercloud.com.br/dados-abertos.aspx).
Desde 1º/8/2025 a Alba publica os dados dos deputados e das proposições nesse portal (aviso na página "Deputados" do site).

Lista: parlamentares da 20ª legislatura com situação "Ativo" (filtro da própria API: 63 pessoas, inclusive suplentes que
assumiram), conferida com a lista "Em exercício" do site da Alba. A API de parlamentares é muito lenta (cerca de 40 s por
página de 10), então ela fica guardada por até 3 dias; a lista do site, que é rápida, é lida todo dia e, se as duas não
baterem, a da API é baixada de novo.
Propostas: projetos de lei (PL), de lei complementar (PLC), de emenda constitucional (PEC), de decreto legislativo (PDL) e
de resolução (PRS) desde 1º/2/2023, com autor, coautores, situação e tramitações.
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import re
import ssl
import urllib.error
import urllib.request

import regional
from comum import UA, chave_nome, data_iso, fonte, hoje, log, sem_acento

from . import _ne_gov as gv
from ._ne_comum import com_status_en, feito, legislatura_estadual, nome_lei, vez
from ._ne_nopaper import NoPaper, consulta_csv, texto_tramitacoes, ultima

SITE_LISTA = "https://www.al.ba.gov.br/deputados/deputados-estaduais"


def _nomes_site(col) -> set[str]:
    t = col.rede.texto(SITE_LISTA, "site-em-exercicio.html", 20)
    nomes = re.findall(r'<option value="/deputados/deputado-estadual/\d+">\s*<span>(.*?)</span>', t, re.S)
    return {chave_nome(html.unescape(n)) for n in nomes if n.strip()}


def em_exercicio(col, ps: list[dict]) -> list[dict]:
    ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
    try:
        site = _nomes_site(col)
    except Exception as e:  # o site fora do ar não impede a lista da API
        log(f"  BA: lista do site indisponível ({e})")
        return ativos
    api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
    if site and site != api:
        ps = col.parlamentares(max_idade_h=20)
        ativos = [p for p in ps if (p.get("parlamentarSituacao") or "").lower() == "ativo"]
        api = {chave_nome(p.get("parlamentarNome")) for p in ativos}
        if site != api:
            log(f"  BA: lista da API e do site diferentes. Só na API: {sorted(api - site)}; só no site: {sorted(site - api)}")
    return ativos


# Na Alba a "situação" da API não acompanha o fim do processo (projeto que virou lei pode continuar "TRAMITANDO"), então a
# situação vem das tramitações (frases conferidas à mão numa amostra; ver as notas da frente ale-nordeste):
# "Promulgada/Publicada a Lei nº ..." e "Sancionada Lei nº ..." = virou lei (o número da lei vem junto); o mesmo para
# Resolução; "Expedido autógrafo ao Governador" = aprovada e enviada para sanção; "Devolvido sem sanção ou veto" = o
# governador não decidiu no prazo e falta promulgar; "Aprovado em 1ª/2ª discussão" ou "em discussão única" = aprovada no
# Plenário; "Retirado de tramitação a pedido do autor" = o autor desistiu.
_NORMA = re.compile(r"(?:promulgad|publicad|sancionad)[ao]?\s+(?:a\s+)?(lei complementar|lei|resolucao|emenda constitucional|"
                    r"decreto legislativo)\s+n[o°º]?\.?\s*([\d.,]+)")
NOMES = {"lei complementar": "Lei Complementar", "lei": "Lei", "resolucao": "Resolução",
         "emenda constitucional": "Emenda Constitucional", "decreto legislativo": "Decreto Legislativo"}
REGRAS = [
    (r"(?<!pedido de )retirad[ao] de tramitacao|retirad[ao] pel[oa] autor|(?<!pedido de retirada )a pedido do autor", "retirada", None, None),
    (r"veto total|veto integral|vetad[oa] (totalmente|integralmente)", "rejeitada", "Vetada por inteiro pelo governador",
     "Fully vetoed by the governor"),
    (r"rejeitad", "rejeitada", "Rejeitada", None),
    (r"prejudicad", "parada", "Ficou prejudicada", None),
    (r"devolvid[ao] sem sancao ou veto", "aprovada", "Aprovada; o governador não sancionou nem vetou no prazo, e falta promulgar",
     "Approved; the governor did not sign or veto it in time, and it still has to be promulgated"),
    (r"expedido autografo|autografo expedido", "aprovada", "Aprovada; enviada ao governador para sanção ou veto",
     "Approved; sent to the governor to sign or veto"),
    (r"aprovad[ao] em (\S+ )?(e \S+ )?discussao|aprovad[ao] em plenario", "aprovada",
     "Aprovada no Plenário", "Approved by the full Assembly"),
    (r"apensad", "junta", None, None),
]


def situacao(v: dict) -> dict:
    data = (ultima(v)[0] or "")[:10] or None
    for t in reversed(v.get("tr") or []):  # a norma que a proposição virou, com número e data
        m = _NORMA.search(sem_acento((t[3] or "").lower()))
        if m:
            nome = NOMES[m.group(1)]
            num = re.sub(r"\D", "", m.group(2))
            ano = (re.search(r"(?:de|em)\s+\d{1,2}[º°o]?/\d{2}/(\d{4})|de (\d{4})", sem_acento((t[3] or "").lower()[m.end():m.end() + 40])) or None)
            ano = next((g for g in ano.groups() if g), None) if ano else (t[0] or "")[:4] or None
            nl = nome_lei(nome, num, ano)
            return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}", "en": None,
                    "data": (t[0] or "")[:10] or data, "lei": {"nome": nl, "url": None}}
    tx = texto_tramitacoes(v)
    for exp, st, pt, en in REGRAS:
        if re.search(exp, tx):
            return {"status": st, "txt": pt, "en": en, "data": data, "lei": None}
    sit = sem_acento((v.get("sit") or "").lower())
    if sit.startswith("arquivad"):
        return {"status": "arquivada", "txt": "Arquivada", "en": None, "data": data, "lei": None}
    if sit.startswith("tramitando") or v.get("tr"):
        return {"status": "andando", "txt": None, "en": None, "data": data, "lei": None}
    return {"status": "outra", "txt": None, "en": None, "data": data, "lei": None}


def coletar() -> dict:
    return Alba(
        uf="BA", base="https://albalegis.nopapercloud.com.br", casa="Assembleia Legislativa do Estado da Bahia",
        casa_en="Legislative Assembly of the State of Bahia", sigla="Alba", site="https://www.al.ba.gov.br",
        veiculo="Assembleia Legislativa da Bahia (Alba)", prefixo="alba", pasta="alba",
        tipos={1: "PL", 6: "PLP", 10: "PEC", 2: "PDL", 13: "PRC"}, situacao=situacao, em_exercicio=em_exercicio,
        filtro_pessoas=f"&parlamentarLegislatura={legislatura_estadual(20)}&parlamentarSituacao=1", idade_pessoas_h=72, qtd_pessoas=10,
    ).coletar()


# ---------------------------------------------------------------- o que o governo do estado fez (gov-BA)
AUTOR_EXECUTIVO = 4105  # "PODER EXECUTIVO" no portal legislativo da Alba
LEGISLA = "https://www.legislabahia.ba.gov.br"  # Portal de Legislação do Estado da Bahia (Casa Civil)
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                     "outubro", "novembro", "dezembro"], 1)}
def _legisla(url: str, pausa: float = 1.0) -> str:
    """O Legisla Bahia só aceita conexões TLS antigas (o padrão do Python recusa): contexto próprio, um pedido por vez, com
    o robots.txt e o intervalo entre pedidos respeitados (vez/feito de _ne_comum)."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    erro = None
    for t in range(3):
        iv = vez(url, pausa)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            erro = e
            # as páginas da lista às vezes devolvem 404 por um instante (conferido em 26/10/2026): ganham nova chance
            if e.code in (400, 401, 403, 410) or (e.code == 404 and "/documentos?" not in url):
                break
        except Exception as e:
            erro = e
        finally:
            feito(url, max(iv, 3.0 * (t + 1)))
    raise RuntimeError(f"Legisla Bahia: {url}: {erro}")


def _titulo(t: str) -> tuple[str, str] | None:
    """'LEI Nº 15.201 DE 1º DE JULHO DE 2026' -> ('15201', '2026-07-01')"""
    m = re.search(r"n[º°o]\s*([\d.]+)\s*,?\s*de\s+(\d{1,2})[º°o]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", sem_acento(t.lower()).replace("º", "o"))
    if not m or m.group(3) not in MESES:
        return None
    return m.group(1).replace(".", ""), f"{m.group(4)}-{MESES[m.group(3)]:02d}-{int(m.group(2)):02d}"


class Alba(NoPaper):
    def coletar(self) -> dict:
        r = super().coletar()
        if r.get("pendente"):  # primeira carga das propostas em andamento: o perfil do governador fica como estava
            return r
        try:
            self.governo()
        except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
            log(f"  BA: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
        return r

    def leis_legisla(self, ini: str) -> dict[str, dict]:
        """Leis ordinárias e complementares desde ini no Legisla Bahia, da mais nova para a mais antiga; depois da primeira
        leitura completa, só as páginas do começo (até achar uma página só com leis já conhecidas)."""
        est = self.rede.estado("gov-legisla.json", {}) or {}
        leis: dict = est.get("leis") or {}
        for cat, tl in ((7, "LO"), (5, "LC")):
            completo = est.get(f"completo-{cat}") == ini
            pag, ultima_pag = 0, None
            while True:
                t = _legisla(f"{LEGISLA}/documentos?categoria%5B0%5D={cat}&data%5Bmin%5D={ini}&sort_by=field_data_doc&sort=desc&page={pag}")
                novos, velhas, atuais = 0, 0, 0
                for href, tit in re.findall(r'href="(/documentos/lei[^"]+)"[^>]*>([^<]+)<', t):
                    x = _titulo(html.unescape(tit))
                    if not x:
                        continue
                    if x[1] < ini:  # a lista vem da mais nova para a mais antiga; o filtro de data do portal não vale
                        velhas += 1
                        continue
                    atuais += 1
                    k = f"{tl}-{x[0]}"
                    if k not in leis:
                        novos += 1
                    leis[k] = {"n": x[0], "d": x[1], "tl": tl, "url": LEGISLA + href, "t": html.unescape(tit).strip()}
                pags = [int(p) for p in re.findall(r"(?:[?&]|&amp;)page=(\d+)", t)]
                ultima_pag = max(pags) if pags else 0
                if pag >= ultima_pag or (velhas and not atuais) or (completo and not novos):
                    break
                pag += 1
            est[f"completo-{cat}"] = ini
        est["leis"] = leis
        self.rede.guardar(est, "gov-legisla.json")
        return {k: v for k, v in leis.items() if v["d"] >= ini}

    def vetos(self, ini: str) -> list[dict]:
        """Mensagens e ofícios do Poder Executivo que vetam projetos (exportação CSV da consulta por autor, ano a ano)."""
        est = self.rede.estado("gov-vetos.json", {}) or {}
        h = dt.date.fromisoformat(hoje())
        out = []
        for ano in range(int(ini[:4]), h.year + 1):
            x = est.get(str(ano))
            if not x or (h - dt.date.fromisoformat(x["lido"])).days >= (1 if ano == h.year else 30):
                linhas = consulta_csv(self.base, f"autor={AUTOR_EXECUTIVO}&ano={ano}")
                vs = []
                for r in linhas[1:]:
                    s = " | ".join(r)
                    if len(r) > 6 and re.search(r"(?i)^(mensagem|of[ií]cio)", r[3].strip()) and re.search(r"(?i)\bvet(a|o|ou)\b", r[6]):
                        d = r[9].strip() if len(r) > 9 and re.fullmatch(r"\d{2}/\d{2}/\d{4}", r[9].strip()) else None
                        d = d or (re.findall(r"\b\d{2}/\d{2}/\d{4}\b", s) or [None])[-1]
                        vs.append({"id": r[0], "tipo": r[3].strip(), "n": r[4].strip(), "e": r[6].strip()[:300], "d": data_iso(d) if d else None})
                x = est[str(ano)] = {"lido": hoje(), "vetos": vs}
                self.rede.guardar(est, "gov-vetos.json")
            out += [v for v in x["vetos"] if (v.get("d") or f"{ano}-12-31") >= ini]
        return out

    def governo(self) -> dict:
        per = gv.periodo("BA")
        ini = per["inicio"]
        props = (self.rede.estado("estado.json", {}) or {}).get("props") or {}
        lista = []
        for k, v in props.items():
            tipo = self.tipos.get(v["tid"])
            if not tipo or (v.get("d") or "") < ini or v.get("au") != AUTOR_EXECUTIVO:
                continue
            s = situacao(dict(v, _id=k))
            prop = regional.proposta(f"{self.prefixo}:{k}", f"{v['s']} {v['n']}/{v['a']}", tipo, v.get("d"), v.get("e"),
                                     v.get("sit"), f"{self.base}/spl/processo.aspx?id={k}", papel="autor", status=s["status"],
                                     data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        fonte_prop = fonte(self.veiculo, "Proposições do Poder Executivo (portal legislativo)",
                           f"{self.base}/spl/consulta-producao.aspx?autor={AUTOR_EXECUTIVO}")
        fontes = [fonte("Governo da Bahia (Casa Civil)", "Legisla Bahia: leis ordinárias e complementares",
                        f"{LEGISLA}/documentos?categoria%5B0%5D=7")]
        leis = self.leis_legisla(ini)
        quem, faltam = gv.classificar_leis(self.rede, {k: v["url"] for k, v in leis.items()}, _legisla, orcamento_s=150)
        if faltam:  # sem a conta das leis, o perfil ficaria pela metade: fica o arquivo da última vez
            log(f"  BA: {faltam} leis ainda sem leitura do texto; o perfil do governador fica como estava até todas serem lidas")
            return {}
        n_leis, nota, nota_en, prom = None, [], [], None
        c = collections.Counter(quem.values())
        n_leis, prom = c[False], c[True]
        pt, en = gv.nota_leis(per, len(leis), c[False], c[True], c[None], "no Legisla Bahia (o portal de legislação do "
                              "governo do estado)", "in Legisla Bahia (the state government's legislation portal)")
        nota.append(pt)
        nota_en.append(en)
        vts = self.vetos(ini)
        parciais = sum(1 for v in vts if re.search(r"(?i)parcial", v["e"]))
        nota.append(f"Vetos: as mensagens e os ofícios do Poder Executivo que vetam projetos, recebidos pela Assembleia desde "
                    f"{gv.data_pt(ini)} (a Alba registra os vetos como mensagens do governador).")
        nota_en.append(f"Vetoes: the executive branch's messages and official letters vetoing bills, received by the Assembly "
                       f"since {gv.data_en(ini)} (the Alba records vetoes as messages from the governor).")
        fontes.append(fonte(self.veiculo, "Mensagens e ofícios do Poder Executivo (portal legislativo)",
                            f"{self.base}/spl/consulta-producao.aspx?autor={AUTOR_EXECUTIVO}"))
        ex = gv.bloco_executivo(per, n_leis, len(vts), fontes, " ".join(nota), " ".join(nota_en), len(vts) - parciais, parciais, prom)
        esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature")
        return gv.gravar_gov("BA", per, lista, esc, esc_en, fonte_prop, ex, fontes)
