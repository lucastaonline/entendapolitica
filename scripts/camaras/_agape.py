"""Câmaras que usam o "Processo Legislativo Eletrônico" da Ágape ("Câmara sem Papel"; páginas /spl/ em ASP.NET): Vitória,
Teresina e Cuiabá. Tudo vem do próprio sistema da Câmara, como uma pessoa usa no navegador:

1. quem está no cargo: /spl/parlamentares.aspx mostra os vereadores da legislatura atual em dois grupos, "Ativo" (no cargo,
   inclusive suplentes que assumiram) e "Suplente"/"Inativo" (quem já exerceu e saiu). Entra só o grupo "Ativo";
2. as proposições (projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de resolução)
   desde 1º/1/2025: a lista de cada tipo e ano (/spl/consulta-producao.aspx?tipo=<tipo>&ano_proposicao=<ano>, os links
   da "Consulta por Tipo") e o botão DOWNLOAD → XLS da própria lista (um arquivo XLSX com número, ementa, autores na ordem
   do cadastro — o primeiro é quem apresentou —, data, fase atual e situação). Dois pedidos por tipo e ano;
3. a página de cada proposição (/spl/processo.aspx?id=<ID>): autoria (com o código de cada vereador), situação, "Norma
   resultante" e o histórico da tramitação (fase, ação e complemento de cada passo), de onde sai a situação mostrada no site
   (regras de cada Câmara: eventos_vitoria, eventos_teresina, eventos_cuiaba, conferidas à mão). É lida uma vez e de novo só
   quando a lista mostra que a fase, o setor ou a situação mudou (e, de tempos em tempos, as que ainda andam);
4. em Cuiabá, a página de cada proposição é pesada (de 2 a 6 MB, uns 0,5 MB comprimidos, porque repete o desenho do fluxo
   do processo em cada passo): a situação vem da fase atual da lista oficial e das normas do módulo de Legislação
   (/legislacao/consulta-legislacao.aspx, que liga cada norma à proposição de origem), e a página só é lida quando isso não
   basta (arquivadas sem norma, por exemplo), até o fim da tabela da tramitação e com um limite de bytes por rodada.

Educado (contrato, seção 6): robots.txt de cada servidor (Disallow e Crawl-delay; um redirecionamento só é seguido se o
robots.txt do destino deixar), um pedido por vez, pelo menos 1,5 s entre pedidos ao mesmo servidor, o User-Agent do projeto
no formato dos robôs de busca (_base.UA_COMPAT), cache em .cache/camaras/<IBGE>/agape/ e o fim da rodada
(LEGISLATIVOS_PRAZO). A primeira carga pode levar várias rodadas: o que foi lido fica guardado e, enquanto falta a página de
alguma proposição, nada é publicado (ficam os arquivos de antes; o resumo marca a Câmara como "em andamento").
"""
from __future__ import annotations

import datetime as dt
import html
import io
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import NamedTuple

import regional
from comum import fonte, hoje, ler_json, log, salvar_json, sem_acento

from . import _base as B
from . import _capitais as C
from ._capitais import Rede, SemTempo

ANOS_DESDE = int(B.INICIO[:4])
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_FIM_TRAMITACAO = (b"ContentPlaceHolder1_tb_tramitacao", b"</tbody>")  # a página só interessa até o fim da tramitação


# ------------------------------------------------------------------------------------------------ páginas
def texto(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def campos_form(t: str) -> dict:
    """Os campos de um formulário ASP.NET (ocultos, textos, caixas marcadas e listas), como o navegador manda."""
    out = {}
    for m in re.finditer(r"<input\b([^>]*)>", t, re.I):
        a = m.group(1)
        nm = re.search(r'\bname="([^"]+)"', a)
        if not nm:
            continue
        tp = (re.search(r'\btype="([^"]+)"', a) or [None, "text"])[1].lower()
        if tp in ("submit", "button", "image", "file") or (tp in ("checkbox", "radio") and "checked" not in a):
            continue
        v = re.search(r'\bvalue="([^"]*)"', a)
        out[html.unescape(nm.group(1))] = html.unescape(v.group(1)) if v else ""
    for m in re.finditer(r'<select\b[^>]*name="([^"]+)"[^>]*>(.*?)</select>', t, re.I | re.S):
        sel = re.search(r'<option[^>]*selected[^>]*value="([^"]*)"', m.group(2)) or \
            re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', m.group(2))
        out[html.unescape(m.group(1))] = html.unescape(sel.group(1)) if sel else ""
    return out


def xlsx_linhas(b: bytes) -> list[list[str]]:
    """As linhas da primeira planilha de um arquivo XLSX (só a biblioteca padrão)."""
    z = zipfile.ZipFile(io.BytesIO(b))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{_NS}si"):
            ss.append("".join(x.text or "" for x in si.iter(f"{_NS}t")))
    out = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(f"{_NS}row"):
        vals = []
        for c in row.findall(f"{_NS}c"):
            t, v = c.get("t"), c.find(f"{_NS}v")
            if t == "s":
                vals.append(ss[int(v.text)])
            elif t == "inlineStr":
                vals.append("".join(x.text or "" for x in c.find(f"{_NS}is").iter(f"{_NS}t")))
            else:
                vals.append(v.text if v is not None else "")
        out.append(vals)
    return out


def data_iso(s: str | None) -> str | None:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def chave_nome(s: str | None) -> str:
    """Nome sem acento, sem pontuação e sem os rótulos do sistema ("(Câmara Digital)", "Vereador")."""
    n = B.nome_limpo(s or "") or ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", sem_acento(n).lower())).strip()


def ler_processo(t: str) -> dict:
    """O que interessa na página de uma proposição (processo.aspx?id=...), sem o HTML: data, autoria (com o código de
    parlamentar), situação, origem, normas resultantes, processos acessórios e a tramitação, do passo mais novo ao mais
    antigo: [recebimento, fase, setor, envio, ação, complemento, [[documento, endereço], ...]]."""
    def span(ident):
        m = re.search(rf'id="ContentPlaceHolder1_{ident}"[^>]*>(.*?)</(?:span|p|div)>', t, re.S)
        return texto(m.group(1)) if m else None
    if 'id="ContentPlaceHolder1_sp_id"' not in t or "ContentPlaceHolder1_tb_tramitacao" not in t:
        raise RuntimeError("a página da proposição veio sem os dados (formato mudou ou erro do servidor)")
    out = {"data": data_iso(span("sp_data_apresentacao")), "situacao": span("p_situacao")}
    autores = []
    m = re.search(r'id="ContentPlaceHolder1_p_autoria"[^>]*>(.*?)</p>', t, re.S)
    if m:
        for href, nome in re.findall(r"<a[^>]*href='([^']*)'[^>]*>(.*?)</a>", m.group(1), re.S):
            pid = re.search(r"parlamentar\.aspx\?id=(\d+)", href)
            autores.append([texto(nome), pid.group(1) if pid else None])
        resto = texto(re.sub(r"<a[^>]*>.*?</a>", "", m.group(1), flags=re.S))
        autores += [[n.strip(), None] for n in resto.split(";") if n.strip()]
    out["autores"] = autores
    m = re.search(r'id="ContentPlaceHolder1_a_origem"[^>]*>(.*?)</p>', t, re.S)
    out["origem"] = texto(m.group(1)) if m else None
    m = re.search(r'id="ContentPlaceHolder1_span_norma_resultante"[^>]*>(.*?)</span>\s*</div>', t, re.S)
    out["normas"] = [[texto(n), h] for h, n in re.findall(r"<a[^>]*href='([^']*)'[^>]*>(.*?)</a>", m.group(1), re.S)] if m else []
    m = re.search(r'id="div_processo_acessorios"[^>]*>(.*?)</div>', t, re.S)
    out["acessorios"] = [[texto(n), i] for i, n in re.findall(r"<a href='processo\.aspx\?id=(\d+)'[^>]*>(.*?)</a>",
                                                               m.group(1), re.S)] if m else []
    tram = []
    m = re.search(r'<tbody id="ContentPlaceHolder1_tb_tramitacao">(.*?)</tbody>', t, re.S)
    if m:
        for bloco in re.split(r"<tr>\s*<td>\s*<table>", m.group(1))[1:]:
            def campo(rotulo):
                x = re.search(rf"<strong>{rotulo}:?\s*</strong>(.*?)</td>", bloco, re.S)
                return texto(x.group(1)) if x else None
            docs = [[texto(n)[:160], h] for h, n in re.findall(r"<a[^>]*href='([^']*)'[^>]*>(.*?)</a>", bloco, re.S) if texto(n)]
            compl = campo("Complemento da Ação")
            tram.append([campo("Recebimento"), campo("Fase"), campo("Setor"), campo("Envio"), campo("Ação"),
                         compl[:900] if compl else None, docs])
    out["tramitacao"] = tram
    return out


def ler_normas_lista(t: str) -> list[dict]:
    """Itens de uma página de resultado do módulo de Legislação: a norma, a data, o link e a proposição de origem."""
    out = []
    for bloco in t.split('<div class="kt-widget5__item')[1:]:
        tit = re.search(r'class="kt-widget5__title"[^>]*>(.*?)</a>', bloco, re.S)
        det = re.search(r"href=['\"]([^'\"]*norma\.aspx\?id=(\d+)[^'\"]*)['\"]", bloco)
        orig = re.search(r"href=['\"][^'\"]*processo\.aspx\?id=(\d+)['\"][^>]*>(.*?)</a>", bloco, re.S)
        data = re.search(r"Data:\s*</span>\s*<span[^>]*>(.*?)</span>", bloco, re.S)
        if tit and det:
            out.append({"nome": texto(tit.group(1)), "norma": det.group(2), "data": data_iso(texto(data.group(1))) if data else None,
                        "processo": orig.group(1) if orig else None, "origem": texto(orig.group(2)) if orig else None})
    return out


# ------------------------------------------------------------------------------------------------ situação
class Ev(NamedTuple):
    """Um acontecimento da tramitação que decide (ou ajuda a decidir) a situação."""
    data: str | None
    tipo: str          # lei | aprovada | sancao | veto_total | veto_parcial | veto_mantido | veto_derrubado | rejeitada |
    #                    inconst | inconst_revista | retirada | parada | arquivada | desarquivada
    info: dict


# frases das situações próprias destas Câmaras (as outras vêm de _base.TXT e de comum.STATUS_TXT)
TXT = {
    "inconst": ("A Comissão de Justiça considerou a proposta inconstitucional, e ela foi arquivada",
                "The Justice Committee found the bill unconstitutional, and it was shelved"),
    "inconst_pendente": ("A Comissão de Justiça considerou a proposta inconstitucional",
                         "The Justice Committee found the bill unconstitutional"),
    "ccj_unanime": ("A Comissão de Legislação considerou a proposta inconstitucional, por unanimidade, e ela foi arquivada",
                    "The Legislation Committee unanimously found the bill unconstitutional, and it was shelved"),
    "parecer_rejeicao": ("Rejeitada: o Plenário aprovou o parecer da comissão contra a proposta",
                         "Rejected: the full City Council approved the committee's opinion against the bill"),
    "plenario": ("Rejeitada em votação no Plenário", "Rejected in a vote of the full City Council"),
    "prejudicada": ("Ficou prejudicada (as regras da Câmara não deixam seguir)",
                    "Set aside (the City Council's rules do not let it go ahead)"),
    "prejudicada_lei": ("Ficou prejudicada: já existe uma lei sobre o mesmo assunto",
                        "Set aside: there is already a law on the same subject"),
    "prejudicada_aprovada": ("Ficou prejudicada: a Câmara já tinha aprovado outra proposta sobre o mesmo assunto",
                             "Set aside: the City Council had already approved another bill on the same subject"),
    "prejudicada_saida": ("Ficou prejudicada: o vereador que apresentou a proposta saiu da Câmara",
                          "Set aside: the councilor who filed the bill left the City Council"),
    "prejudicada_semelhante": ("Ficou prejudicada: já havia outra proposta sobre o mesmo assunto",
                               "Set aside: there was already another bill on the same subject"),
    "prejudicada_ausencia": ("Ficou prejudicada: quem apresentou não estava na sessão em que ela seria votada",
                             "Set aside: the person who filed it was absent from the session where it was to be voted on"),
    "prejudicada_homenagem": ("Ficou prejudicada: a pessoa já tinha recebido essa homenagem da Câmara",
                              "Set aside: the person had already received this honor from the City Council"),
    "maioria": ("Não teve os votos necessários (maioria absoluta) e ficou prejudicada",
                "It did not get the votes it needed (an absolute majority) and was set aside"),
    "lei_semelhante": ("O autor desistiu: já existe uma lei sobre o mesmo assunto",
                       "Withdrawn by the author: there is already a law on the same subject"),
    "promulgada": ("Virou norma: promulgada pela Câmara", "Became law: promulgated by the City Council"),
    "sancionada_sem_numero": ("Virou lei (sancionada pelo prefeito)", "Became law (signed by the mayor)"),
    "sancao_tacita": ("Virou lei sem a assinatura do prefeito (sanção tácita)", "Became law without the mayor's signature (tacit approval)"),
    "na_prefeitura": ("Aprovada pela Câmara; esperando a decisão do prefeito", "Approved by the City Council; waiting for the mayor's decision"),
    "redacao_final": ("Aprovada pela Câmara; falta votar o texto final (redação final)",
                      "Approved by the City Council; the final text still has to be voted on"),
    "aprovada_arquivada": ("Aprovada pela Câmara e arquivada, sem a norma registrada no sistema",
                           "Approved by the City Council and shelved, with no law recorded in the system"),
}
_NORMA = re.compile(r"\b(lei ordinaria|lei complementar|lei municipal|lei|decreto legislativo|resolucao|emenda a lei organica)"
                    r"\s*(?:n[ºo°.]*\s*)?(\d{1,2}\.?\d{3}|\d{1,4})\s*(?:/|,? de [^/]*?|de )?\s*(\d{4})?", re.I)


def nome_lei(texto_: str | None, ano_padrao: str | None = None) -> tuple[str, str, str] | None:
    """('Lei Ordinária', '10386', '2026') de um texto como "Lei Ordinária 10386/2026 - Publicação DO PMV",
    "Sancionada a Lei nº 6.187, de 20 de março de 2025" ou "LEI Nº 7.437 DE 29 DE DEZEMBRO DE 2025"."""
    t = B.norm(texto_)
    m = re.search(r"\b(lei ordinaria|lei complementar|lei municipal|decreto legislativo|resolucao|emenda a lei organica|lei)\s*"
                  r"(?:n[o°.]*\s*)?(\d{1,2}\.\d{3}|\d{1,5})\b(?:\s*/\s*(\d{4})|[^/]{0,40}?\bde (?:\d{1,2} de )?[a-z]+ de (\d{4}))?", t)
    if not m:
        return None
    tipo = {"lei ordinaria": "Lei Ordinária", "lei complementar": "Lei Complementar", "lei municipal": "Lei",
            "decreto legislativo": "Decreto Legislativo", "resolucao": "Resolução", "emenda a lei organica": "Emenda à Lei Orgânica",
            "lei": "Lei"}[m.group(1)]
    return tipo, m.group(2).replace(".", ""), m.group(3) or m.group(4) or ano_padrao


_MESES = {m: i for i, m in enumerate(("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                      "outubro", "novembro", "dezembro"), 1)}


def data_lei(texto_: str | None) -> str | None:
    """A data da norma escrita no complemento ("Sancionada a Lei nº 6.179, de 19 de fevereiro de 2025", "LEI Nº 7.437 DE 29
    DE DEZEMBRO DE 2025", "Lei nº 10.238, de 13/10/2025"), em AAAA-MM-DD."""
    t = B.norm(texto_)
    m = re.search(r"\blei\b[^/]{0,40}?\bde (\d{1,2})o? de ([a-z]+) de (\d{4})", t)
    if m and m.group(2) in _MESES:
        try:
            return dt.date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"\blei\b[^/]{0,40}?\bde (\d{2})/(\d{2})/(\d{4})", t)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _passos(p: dict):
    """Os passos da tramitação do mais antigo ao mais novo: (data, fase, ação, complemento, documentos, passo)."""
    for t in reversed(p.get("tramitacao") or []):
        data = data_iso(t[3]) or data_iso(t[0])
        yield data, B.norm(t[1]), B.norm(t[4]), B.norm(t[5]), t[6] or [], t


def _doc_lei(docs: list, ano: str | None = None):
    """(nome, número, ano, endereço) do documento da lei na tramitação ("Lei Ordinária 10386/2026 - Publicação DO PMV",
    "Lei Municipal 6187/2025 - lei")."""
    for nome, href in docs:
        n = nome_lei(nome.split(" - ")[0], ano)
        if n:
            return n, href
    return None


def _ev_lei(data: str | None, docs: list | None, c: str, como: str) -> Ev:
    """O passo em que a proposição virou norma: o documento da norma (se houver), o nome e a data escritos no complemento."""
    return Ev(data, "lei", {"doc": _doc_lei(docs) if docs is not None else None, "como": como,
                            "texto": nome_lei(c, (data or "")[:4] or None), "dt": data_lei(c)})


_NORMA_CAMARA = re.compile(r"^(resolucao|decreto legislativo|decreto) n[o°.]*\s*(\d{1,2}\.\d{3}|\d{1,5})\s*/\s*(\d{4})")


def eventos_vitoria(p: dict) -> list[Ev]:
    """Vitória (conferido à mão: ver as notas da frente). A ação de cada passo ("Sancionado", "Veto Total", "Mantido o veto
    total", "Rejeitado o veto total", "Aprovado", "Publicado em DO"...) e o complemento, quando a decisão está escrita nele
    ("Parecer do Relator pela Inconstitucionalidade e Ilegalidade APROVADO na ... Comissão de Constituição, Justiça...",
    "Publicação da Inconstitucionalidade no Diário Oficial", "Vencido o prazo recursal ... sem apresentação de recurso",
    "Requerimento de Arquivamento ... apresentado pelo Vereador autor", "versa sobre a mesma matéria de Projeto de Lei já
    aprovado"). Depois de aprovada com emendas, a proposição volta ao Plenário para a votação da redação final."""
    ev = []
    aprovada, norma_camara, motivo_arquivo = False, None, None
    for data, f, a, c, docs, _ in _passos(p):
        cr = re.sub(r"retirad[oa]s? de pauta", "", c)  # "retirado de pauta a pedido do autor" não é desistir da proposta
        m = _NORMA_CAMARA.match(c)
        if m:  # "Resolução nº 2.087/2025." no passo da aprovação (resoluções e decretos legislativos da Câmara)
            norma_camara = ("Resolução" if m.group(1) == "resolucao" else "Decreto Legislativo", m.group(2).replace(".", ""), m.group(3))
        if a.startswith("sancionad"):
            e = _ev_lei(data, docs, c, "sancionada")
            ev.append(e._replace(info=dict(e.info, parcial="veto parcial" in a)))
        elif a in ("promulgada", "promulgacao", "promulgado") or a.startswith("projeto promulgad"):
            ev.append(_ev_lei(data, docs, c, "promulgada"))
        elif a == "publicado em do" and f.startswith("aguardando a publicacao"):  # norma da Câmara publicada no Diário Oficial
            e = _ev_lei(data, docs, c, "promulgada")
            ev.append(e._replace(info=dict(e.info, texto=e.info["texto"] or norma_camara)))
        elif a == "perdeu prazo":  # o prefeito não decidiu no prazo: a lei vai para a promulgação
            ev.append(_ev_lei(data, docs, c, "tacita"))
        elif a in ("veto total", "comunica veto total"):
            ev.append(Ev(data, "veto_total", {}))
        elif a in ("veto parcial", "sancionado com veto parcial"):
            ev.append(Ev(data, "veto_parcial", {}))
        elif a in ("mantido o veto total",) or (re.search(r"\bveto (total )?mantido\b", c) and "veto" in f and "parecer" not in c[:20]):
            ev.append(Ev(data, "veto_mantido", {}))
        elif a in ("rejeitado o veto total", "rejeitado o veto") or (re.search(r"\bveto (total )?rejeitado\b", c) and "veto" in f
                                                                     and "parecer" not in c[:20]):
            ev.append(Ev(data, "veto_derrubado", {}))
        elif a in ("arquivado a pedido do autor", "retirado a pedido do autor", "retirada a pedido do autor") or re.search(
                r"(a pedido|conforme solicitado pelo|requerimento (formulado|apresentado) pelo|solicitacao) d?[oa]? ?(vereador )?"
                r"(autor|proponente)[^.]{0,60}(arquiv|retir)|(arquiv|retir)[^.]{0,80}(a pedido|solicitado pelo|por solicitacao) d?[oa]? ?"
                r"(vereador )?(autor|proponente)|solicito a retirada da proposicao|(vereador|vereadora|autor|autora|gabinete)[^.]{0,40}"
                r"(requer|solicit)\w*[^.]{0,20} o arquivamento|requerimento de arquivamento de proposic|requerido o arquivamento|"
                r"solicitacao do gabinete|requerimento de arquivamento[^.]{0,40}apresentad[oa] pel[oa] (vereador|vereadora)[^.]{0,10}"
                r"autor", cr):
            ev.append(Ev(data, "retirada", {}))
        elif a in ("prejudicado", "prejudicada"):  # nos complementos, "prejudicada" é quase sempre a votação de um parecer
            ev.append(Ev(data, "parada", {"txt": "prejudicada"}))
        elif re.search(r"pela inconstitucionalidade[^.]{0,120}\baprovad|reconhecida a inconstitucionalidade|publicacao da "
                       r"inconstitucionalidade|inconstitucionalidade publicada|pela constitucionalidade[^.]{0,80}\b(reprovad|rejeitad)",
                       c) or a == "mantido a inconstitucionalidade":
            ev.append(Ev(data, "inconst", {}))
        elif re.search(r"pela inconstitucionalidade[^.]{0,120}\b(rejeitad|reprovad)", c):
            ev.append(Ev(data, "inconst_revista", {}))
        elif re.search(r"(vencido|esgotado|aguardado|encerrado|transcorrido) o prazo (recursal|regimental)|nao apresentado recurso|"
                       r"sem (a )?apresentacao de recurso", c):
            ev.append(Ev(data, "recurso_vencido", {}))
        elif re.search(r"mesma materia de (projeto de lei|lei) ja aprovad", c):  # art. 201, V, do Regimento Interno: vale
            motivo_arquivo = "prejudicada_aprovada"                             # quando a proposição é arquivada por isso
        elif (f.startswith("ordem do dia") or f.startswith("discussao unica")) and "veto" not in f:
            if a.startswith("aprovad") or re.search(r"\b(projeto|materia|proposicao)[^.]{0,30}\baprovad", c):
                ev.append(Ev(data, "aprovada", {}))
                aprovada = True
            elif a.startswith("rejeitad") or re.search(r"\b(projeto|materia|proposicao)[^.]{0,30}\brejeitad", c):
                ev.append(Ev(data, "rejeitada", {"txt": "plenario"}))
        elif f in ("autografo de lei", "avaliacao na pmv", "autografo"):
            ev.append(Ev(data, "sancao", {}))
            aprovada = False
        elif "desarquiv" in c or a.startswith("desarquiv"):
            ev.append(Ev(data, "desarquivada", {}))
        elif aprovada and ("redacao final" in f or "redacao final" in a or "emenda" in f):
            ev.append(Ev(data, "aprovada", {"txt": "redacao_final"}))
            aprovada = False
        if re.match(r"(arquive-se|arquivar|arquivado|para arquivamento)$", a) or f.startswith("arquivo"):
            if motivo_arquivo:
                ev.append(Ev(data, "parada", {"txt": motivo_arquivo}))
                motivo_arquivo = None
            ev.append(Ev(data, "arquivada", {}))
    return ev


def eventos_teresina(p: dict) -> list[Ev]:
    """Teresina (conferido à mão): ações padronizadas do sistema ("Sancionada", "Sanção Tácita", "Promulgado", "Veto
    Total/Parcial", "Resultado do Veto (Mantido)", "Parecer Inconstitucional “Unânime”", "Triagem - Retirada pelo Autor",
    "Solicitado Retirada pelo Autor", "Proposição Rejeitada", "Proposição Aprovada")."""
    ev = []
    for data, f, a, c, docs, _ in _passos(p):
        if a == "sancionada":
            ev.append(_ev_lei(data, docs, c, "sancionada"))
        elif a == "sancao tacita":
            ev.append(_ev_lei(data, docs, c, "tacita"))
        elif a == "promulgado":
            ev.append(_ev_lei(data, docs, c, "promulgada"))
        elif a == "veto total/parcial":
            ev.append(Ev(data, "veto_parcial" if "parcial" in c else "veto_total" if "total" in c else "veto", {}))
        elif a.startswith("resultado do veto"):
            ev.append(Ev(data, "veto_derrubado" if re.search(r"rejeitad|derrubad", a) else "veto_mantido", {}))
        elif a.startswith("parecer inconstitucional"):
            ev.append(Ev(data, "inconst", {"txt": "ccj_unanime"}))
        elif a in ("triagem - retirada pelo autor", "solicitado retirada pelo autor"):
            ev.append(Ev(data, "retirada", {"txt": "lei_semelhante" if "lei semelhante" in c else None}))
        elif a == "proposicao rejeitada":
            ev.append(Ev(data, "rejeitada", {"txt": "plenario"}))
        elif a.startswith("proposicao aprovada") or a == "proposicao lida e aprovada com urgencia":
            final = f in ("votacao turno unico", "para votacao em 2o turno", "leitura plenaria") or "urgencia" in a
            ev.append(Ev(data, "aprovada" if final else "aprovada_1turno", {}))
        elif f in ("elaborar autografo", "aguardando sancao"):
            ev.append(Ev(data, "sancao", {}))
        if f.startswith("para arquivamento"):
            ev.append(Ev(data, "arquivada", {}))
    return ev


def _motivo_prejudicada(c: str) -> str:
    """Cuiabá: o motivo escrito no passo "Prejudicado" (conferido à mão nos complementos de 2025 e 2026)."""
    if re.search(r"existencia d[ae] lei|lei analoga|lei que trata", c):
        return "prejudicada_lei"
    if re.search(r"materia analoga|processo (mais antigo|analogo|analago)|existencia d[oe] (processo|projeto)|propositura identica", c):
        return "prejudicada_semelhante"
    if re.search(r"saida do vereador|deixado a vereanca", c):
        return "prejudicada_saida"
    if re.search(r"ausencia d[oa] autor|auencia d[oa] autor|autor ausente", c):
        return "prejudicada_ausencia"
    if re.search(r"ja (possui|foi agraciad|agraciad|recebeu)", c):
        return "prejudicada_homenagem"
    return "prejudicada"


def eventos_cuiaba(p: dict) -> list[Ev]:
    """Cuiabá (conferido à mão; só para as proposições cuja página é lida): "Sancionado"/"Processo Sancionado",
    "Decreto Promulgado", vetos, "Prejudicado", a votação do "Parecer pela Rejeição" aprovada, "Retirado de Tramitação a
    Pedido do Autor"."""
    ev = []
    for data, f, a, c, docs, _ in _passos(p):
        txt = a + " " + c
        if a in ("sancionado", "processo sancionado") or "sancionad" in a:
            ev.append(_ev_lei(data, docs, c, "sancionada"))
        elif "lei" in f and f.startswith(("8. anexar", "9. anexar", "anexar")) and nome_lei(c):
            ev.append(_ev_lei(data, None, c, "sancionada"))
        elif a in ("decreto promulgado", "resolucao promulgada", "promulgado", "promulgada", "lei promulgada"):
            ev.append(_ev_lei(data, docs, c, "promulgada"))
        elif (a.startswith("mantido") and "veto" in a) or c.startswith("mantido o veto"):
            # "Mantido o Veto" (o veto do prefeito foi votado e mantido; sem "parcial", é o veto total)
            if "parcial" in txt[:120]:
                ev.append(Ev(data, "veto_parcial", {}))
            else:
                ev += [Ev(data, "veto_total", {}), Ev(data, "veto_mantido", {})]
        elif re.search(r"manutencao do veto|veto (foi )?mantido|mantido o veto", txt) and "parecer" not in c[:15]:
            pass  # o aviso à prefeitura de que o veto foi mantido: não muda a situação
        elif (a in ("rejeitado o veto", "veto rejeitado", "veto derrubado") or
              re.search(r"veto (foi )?(rejeitado|derrubado)|derrubada do veto", c)) and "mantido" not in c[:40] and "parecer" not in c[:15]:
            ev.append(Ev(data, "veto_derrubado", {}))
        elif re.search(r"veto total|vetado totalmente|vetad[oa] integralmente", txt) and "parecer" not in c[:15]:
            ev.append(Ev(data, "veto_total", {}))
        elif re.search(r"veto parcial|vetado parcialmente", txt) and "parecer" not in c[:15]:
            ev.append(Ev(data, "veto_parcial", {}))
        elif a.startswith("prejudicad") or a == "propositura identica":
            ev.append(Ev(data, "parada", {"txt": _motivo_prejudicada(txt)}))
        elif "votacao do parecer pela rejeicao" in f and a.startswith("aprovad"):
            ev.append(Ev(data, "rejeitada", {"txt": "parecer_rejeicao"}))
        elif ("de pauta" not in a and re.search(r"a pedido d[oa] autor", a)) or a.startswith("retirado de tramitacao") or \
                re.search(r"retirad[oa] de tramitacao a pedido d[oa] autor|pedido de retirada de tramitacao", c):
            ev.append(Ev(data, "retirada", {}))  # "retirar de pauta" (tirar da sessão do dia) não é desistir
        elif re.search(r"(1a|2a|unica) (discussao|votacao)", f) and a.startswith("rejeitad"):
            ev.append(Ev(data, "rejeitada", {"txt": "plenario"}))
        elif re.search(r"(2a|unica) discussao", f) and a.startswith("aprovad"):
            ev.append(Ev(data, "aprovada", {}))
        elif "autografo" in f or "tomar conhecimento" in f:
            ev.append(Ev(data, "sancao", {}))
        if "arquivar processo" in f or "arquivado" in f:
            ev.append(Ev(data, "arquivada", {}))
    return ev


EVENTOS = {"vitoria": eventos_vitoria, "teresina": eventos_teresina, "cuiaba": eventos_cuiaba}


def resolver(eventos: list[Ev], situacao: str | None, tipo: str, norma: dict | None = None, desde: str | None = None) -> dict:
    """A situação de uma proposição a partir dos acontecimentos da tramitação (do mais antigo ao mais novo; o último que
    decide vale), da situação oficial ("Tramitando", "Arquivado", "Apensado"...) e da norma ligada a ela (se houver).
    desde: a data em que a proposição foi apresentada (a data de uma norma escrita no complemento só vale se vier depois
    dela). Devolve {status, statusTxt, statusTxt_en, dataStatus, lei}."""
    sit = B.norm(situacao)
    estado, chave, data = None, None, None
    veto, lei_ev, inconst, arquivo = None, None, None, None
    ultima = max((e.data for e in eventos if e.data), default=None)
    for e in eventos:
        t = e.tipo
        if t == "lei":
            lei_ev = e
        elif t == "veto_total" or (t == "veto" and veto is None):
            veto = "vt"
            estado, chave, data = "rejeitada", "veto_total_pendente", e.data or data
            if lei_ev and not norma:
                # o sistema marca "Sancionado" quando o processo volta da prefeitura, mesmo com veto total: não virou lei
                lei_ev = None
        elif t == "veto_parcial":
            veto = "vp"
        elif t == "veto_mantido" and veto == "vt":
            estado, chave, data = "rejeitada", "veto_mantido", e.data or data
        elif t == "veto_derrubado":
            estado, chave, data = "aprovada", "veto_derrubado", e.data or data
        elif t == "inconst":
            inconst = e
            estado, chave, data = "rejeitada", e.info.get("txt") or "inconst_pendente", e.data or data
        elif t == "inconst_revista":
            inconst = None
            if estado == "rejeitada" and chave in ("inconst", "inconst_pendente"):
                estado, chave, data = "andando", None, e.data or data
        elif t == "recurso_vencido" and inconst:
            estado, chave, data = "rejeitada", "inconst", e.data or data
        elif t in ("rejeitada", "retirada", "parada"):
            estado, chave, data = t, e.info.get("txt"), e.data or data
        elif t == "aprovada":
            if e.info.get("txt") == "redacao_final":
                if estado == "aprovada":
                    chave = "redacao_final"  # vale a data da aprovação
            else:
                estado, chave, data = "aprovada", "sancao" if tipo in ("PL", "PLP") else "promulgar", e.data or data
        elif t == "aprovada_1turno" and estado in (None, "andando"):
            estado, chave, data = "andando", None, e.data or data
        elif t == "sancao" and estado in (None, "andando", "aprovada") and veto is None:
            ja = estado == "aprovada" and chave in ("na_prefeitura", "promulgar")  # vale a data em que foi mandada
            estado, chave, data = "aprovada", "na_prefeitura" if tipo in ("PL", "PLP") else "promulgar", \
                (data if ja else None) or e.data or data
        elif t == "desarquivada":
            arquivo = None
            if estado in ("retirada", "rejeitada", "parada"):
                estado, chave = "andando", None
        if t == "arquivada":
            arquivo = e.data or ultima
    # virou norma (a norma ligada na página ou no módulo de Legislação; senão, a lei dita na tramitação)
    nome, url, data_lei = None, None, None
    if norma:
        nome, url, data_lei = norma.get("nome"), norma.get("url"), norma.get("data")
    elif lei_ev:
        doc, txt = lei_ev.info.get("doc"), lei_ev.info.get("texto")
        # o número do documento da norma vale mais que o do complemento (conferido à mão nos PDFs das leis de Teresina:
        # quando os dois discordam, o complemento repete o texto de outra lei)
        n = (doc[0] if doc else None) or txt
        if n and n[2]:
            especie = "Lei Complementar" if tipo == "PLP" and n[0] == "Lei" else n[0]
            nome = B.nome_norma(especie, n[1], n[2])
            url = doc[1] if doc else None
        data_lei = lei_ev.data
        quando = lei_ev.info.get("dt")
        if quando and txt and (not doc or doc[0][1] == txt[1]) and (not desde or quando >= desde) and \
                (not lei_ev.data or quando <= lei_ev.data):
            data_lei = quando  # a data da própria norma (o passo às vezes é registrado meses depois)
    if norma or lei_ev:
        if nome:
            return {"status": "lei", "statusTxt": B.virou(nome, veto == "vp"), "statusTxt_en": None,
                    "dataStatus": data_lei or (lei_ev.data if lei_ev else None), "lei": {"nome": nome, "url": url}}
        como = (lei_ev.info.get("como") if lei_ev else None) or "promulgada"
        k = {"sancionada": "sancionada_sem_numero", "tacita": "sancao_tacita"}.get(como, "promulgada")
        return {"status": "lei", "statusTxt": TXT[k][0], "statusTxt_en": TXT[k][1], "dataStatus": lei_ev.data if lei_ev else None,
                "lei": None}
    if estado is None or estado == "andando":
        if sit.startswith(("apensad", "anexad")):
            estado, chave = "junta", None
        elif sit.startswith("arquiv") or arquivo:
            estado, chave, data = "arquivada", None, arquivo or data or ultima
        elif estado is None:
            estado, data = "andando", ultima
    if estado == "rejeitada" and chave == "inconst_pendente" and (sit.startswith("arquiv") or arquivo):
        chave = "inconst"
    if estado == "aprovada" and (sit.startswith("arquiv") or arquivo) and chave in ("sancao", "na_prefeitura", "promulgar",
                                                                                     "redacao_final"):
        # aprovada e arquivada sem a norma registrada no sistema: não dá para dizer que virou lei
        chave, data = "aprovada_arquivada", arquivo or data
    txt, txt_en = None, None
    if chave in TXT:
        txt, txt_en = TXT[chave]
    elif chave in B.TXT:
        txt, txt_en = B.TXT[chave]
    return {"status": estado, "statusTxt": txt, "statusTxt_en": txt_en, "dataStatus": data or ultima, "lei": None}


# ------------------------------------------------------------------------------------------------ a Câmara
class Agape:
    """Uma Câmara com o Processo Legislativo Eletrônico da Ágape.
    host: https://<servidor> (o sistema fica em <host>/spl e a legislação em <host>/legislacao);
    tipos: {código do tipo de proposição no sistema: (tipo comum, sigla oficial)} (PL, PLP, PELO, PDL, PRC);
    perfil: "vitoria" | "teresina" | "cuiaba" (as regras da situação: EVENTOS);
    paginas: "todas" (lê a página de cada proposição) ou "duvida" (só quando a fase atual e as normas não bastam: Cuiabá);
    normas: {código da espécie no módulo de Legislação: nome} (liga norma → proposição pela lista de normas: Cuiabá);
    autores_manual: {nome como a planilha escreve: código do parlamentar} para nomes que a planilha escreve diferente;
    executivo: expressão do autor que é a prefeitura na planilha;
    max_mb_paginas: limite de MB (comprimidos) de páginas de proposição por rodada."""

    def __init__(self, ibge: str, uf: str, host: str, casa: dict, vagas: int, tipos: dict[str, tuple[str, str]], perfil: str,
                 tse_manual: dict | None = None, autores_manual: dict | None = None, paginas: str = "todas",
                 normas: dict | None = None, executivo: str = r"^prefeit|^executivo|^poder executivo",
                 max_mb_paginas: float | None = None, refazer_dias: int = 30, pausa_paginas: float | None = None,
                 notas: list | None = None, nota_fase: dict | None = None, gastos=None):
        self.ibge, self.uf, self.host = ibge, uf, host.rstrip("/")
        self.spl = self.host + "/spl"
        self.casa, self.vagas, self.tipos, self.perfil = casa, vagas, tipos, perfil
        self.gastos = gastos  # função(por_chave, prazo) -> ({id: bloco "gastos"}, notas): os gastos do mandato (Teresina)
        self.tse_manual = tse_manual or {}
        self.autores_manual = {chave_nome(k): str(v) for k, v in (autores_manual or {}).items()}
        self.paginas, self.normas_tipos = paginas, normas or {}
        self.executivo = re.compile(executivo, re.I)
        self.max_mb_paginas, self.refazer_dias, self.pausa_paginas = max_mb_paginas, refazer_dias, pausa_paginas
        self.notas_casa = list(notas or [])
        self.nota_fase = nota_fase or {}
        self.pasta = B.PASTA_CACHE / ibge / "agape"
        self.rede = Rede()
        self.h = hoje()
        self.anos = list(range(ANOS_DESDE, int(self.h[:4]) + 1))

    # -------------------------------------------------------------- cache
    def _arq(self, nome: str):
        return self.pasta / nome

    def _fresco(self, nome: str, horas: float):
        arq = self._arq(nome)
        if arq.exists() and (time.time() - arq.stat().st_mtime) / 3600 < horas:
            return ler_json(arq)
        return None

    def _guardar(self, nome: str, dados) -> None:
        salvar_json(self._arq(nome), dados)

    # -------------------------------------------------------------- vereadores
    def vereadores(self) -> tuple[list[dict], dict[str, dict], str | None]:
        """(pessoas do grupo "Ativo", {chave do nome: {id do parlamentar, grupo}} de todos os cartões, legislatura)."""
        pagina = f"{self.spl}/parlamentares.aspx"
        t = B.baixar_pagina(pagina, self.ibge, "parlamentares", ua_navegador=True)
        leg = re.search(r'id="ContentPlaceHolder1_legislatura_data"[^>]*>([^<]+)<', t)
        partes = re.split(r"<div class='custom-legend[^']*'>\s*", t)
        ativos, cartoes = None, {}
        for p in partes[1:]:
            grupo = (texto(p[:60]).split(" ") or [""])[0].lower()
            pessoas = []
            for bloco in p.split("custom-user-profile'>")[1:]:
                pid = re.search(r"href='parlamentar\.aspx\?id=(\d+)'", bloco)
                nome = re.search(r"class='kt-widget__username pb-1'>\s*(.*?)\s*</a>", bloco, re.S)
                sigla = re.search(r"<small>\((.*?)\)</small>", bloco)
                foto = re.search(r"<img class='kt-widget__img' src='([^']+)'", bloco)
                if not (pid and nome):
                    continue
                n = html.unescape(nome.group(1)).strip()
                f = html.unescape(foto.group(1)) if foto else None
                if f and re.search(r"sem[-_]?foto|avatar|default", f, re.I):
                    f = None
                pessoas.append({"chave": pid.group(1), "nome": n, "partido": html.unescape(sigla.group(1)).strip() if sigla else None,
                                "foto": f, "url": f"{self.spl}/parlamentar.aspx?id={pid.group(1)}"})
                cartoes.setdefault(chave_nome(n), {"id": pid.group(1), "grupo": grupo})
            if grupo.startswith("ativo") and ativos is None:
                ativos = pessoas
        if ativos is None:
            raise RuntimeError("o sistema não mostrou o grupo de vereadores ativos")
        return ativos, cartoes, leg.group(1).strip() if leg else None

    # -------------------------------------------------------------- listas de proposições (XLSX)
    def _pagina(self, url: str, dados: dict | None = None) -> str:
        b, ct = self.rede.pedir(url, dados)
        if "html" not in ct:
            raise RuntimeError(f"{url}: veio {ct or 'sem tipo'} em vez de uma página")
        return b.decode("utf-8", "replace")

    def lista(self, tipo: str, ano: int) -> list[dict]:
        """As proposições de um tipo e ano (planilha do botão DOWNLOAD → XLS da própria lista). Guardada por 20 horas (anos
        de antes do anterior: 7 dias)."""
        nome = f"lista-{tipo}-{ano}.json"
        horas = 20 if ano >= int(self.h[:4]) - 1 else 24 * 7
        x = self._fresco(nome, horas)
        if x is not None:
            return x
        url = f"{self.spl}/consulta-producao.aspx?tipo={tipo}&ano_proposicao={ano}"
        t = self._pagina(url)
        m = re.search(r"Localizada\(s\)\s*<strong>(\d+)</strong>", t)
        if not m:
            raise RuntimeError(f"a lista {url} veio sem a contagem")
        n = int(m.group(1))
        linhas = []
        if n:
            d = campos_form(t)
            d["ctl00$ContentPlaceHolder1$btn_export_excel"] = "XLS"
            b, ct = self.rede.pedir(url, d)
            if b[:2] != b"PK":
                raise RuntimeError(f"a planilha de {url} não veio ({ct})")
            brutas = xlsx_linhas(b)
            cab = [c.strip() for c in brutas[0]]
            if cab[:6] != ["ID", "Processo", "Ano", "Tipo", "Nº", "Ano"] or "Autor" not in cab or "Fase" not in cab:
                raise RuntimeError(f"a planilha de {url} mudou de formato: {cab}")
            cab[5] = "AnoProposicao"
            for r in brutas[1:]:
                x = dict(zip(cab, r))
                autores = [a.strip() for a in re.split(r",\s*(?:<br\s*/?>)?", x.get("Autor") or "") if a.strip()]
                linhas.append({"id": x["ID"].strip(), "numero": (x.get("Nº") or "").strip(), "ano": int(x.get("AnoProposicao") or ano),
                               "tipo_nome": (x.get("Tipo") or "").strip(), "ementa": re.sub(r"_x000D_|\s+", " ", x.get("Ementa") or "").strip(),
                               "autores": autores, "data": data_iso(x.get("Data")), "fase": (x.get("Fase") or "").strip(),
                               "setor": (x.get("Setor") or "").strip(), "situacao": (x.get("Situação") or "").strip()})
            if len(linhas) != n:
                raise RuntimeError(f"a planilha de {url} tem {len(linhas)} linhas e a lista diz {n}")
        self._guardar(nome, linhas)
        return linhas

    def todas_listas(self) -> dict[str, dict]:
        out = {}
        for tipo in self.tipos:
            for ano in self.anos:
                for r in self.lista(tipo, ano):
                    out[r["id"]] = dict(r, _tipo=tipo)
        return out

    # -------------------------------------------------------------- normas (módulo de Legislação)
    def normas(self) -> dict[str, dict]:
        """{ID da proposição de origem: norma} pelas listas do módulo de Legislação (só quando configurado)."""
        out = {}
        for tipo in self.normas_tipos:
            for ano in self.anos:
                for x in self._normas_tipo_ano(tipo, ano):
                    if x.get("processo"):
                        out.setdefault(x["processo"], x)
        return out

    def _normas_tipo_ano(self, tipo: str, ano: int) -> list[dict]:
        nome = f"normas-{tipo}-{ano}.json"
        horas = 20 if ano >= int(self.h[:4]) else 24 * 7
        x = self._fresco(nome, horas)
        if x is not None:
            return x
        url = f"{self.host}/legislacao/consulta-legislacao.aspx?tipo={tipo}&ano={ano}"
        t = self._pagina(url)
        m = re.search(r"Localizada\(s\)\s*<strong>(\d+)</strong>", t)
        n = int(m.group(1)) if m else 0
        itens = ler_normas_lista(t)
        if n > len(itens):
            d = campos_form(t)
            d["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddl_ItensExibidos"
            d["ctl00$ContentPlaceHolder1$ddl_ItensExibidos"] = "100"
            t = self._pagina(url, d)
            itens = ler_normas_lista(t)
            while len(itens) < n:
                if "ctl00$ContentPlaceHolder1$lbNext" not in t:
                    break
                d = campos_form(t)
                d["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$lbNext"
                t = self._pagina(url, d)
                vistos = {j["norma"] for j in itens}
                novos = [i for i in ler_normas_lista(t) if i["norma"] not in vistos]
                if not novos:
                    break
                itens += novos
        if len(itens) != n:
            raise RuntimeError(f"a lista de normas {url} tem {len(itens)} itens e diz {n}")
        for i in itens:
            i["url"] = f"{self.host}/legislacao/norma.aspx?id={i['norma']}"
        self._guardar(nome, itens)
        return itens

    # -------------------------------------------------------------- páginas das proposições
    def _estado_paginas(self) -> dict:
        if not hasattr(self, "_paginas_cache"):
            self._paginas_cache = ler_json(self._arq("processos.json"), {}) or {}
            for x in self._paginas_cache.values():  # páginas guardadas por uma versão antiga: data "dd/mm/aaaa hh:mm:ss"
                p = x.get("p") or {}
                if p.get("data") and not re.match(r"\d{4}-\d{2}-\d{2}$", p["data"]):
                    p["data"] = data_iso(p["data"])
        return self._paginas_cache

    def guardar_paginas(self) -> None:
        if hasattr(self, "_paginas_cache"):
            self._guardar("processos.json", self._paginas_cache)

    @staticmethod
    def assinatura(r: dict) -> str:
        return "|".join([r.get("fase") or "", r.get("setor") or "", r.get("situacao") or ""])

    def pagina(self, pid: str) -> tuple[dict, int]:
        """(página lida, bytes que vieram pela rede). Lê só até o fim da tabela da tramitação (o resto da página é o desenho
        do fluxo do processo, que não interessa)."""
        antes = self.rede.fio
        b, ct = self.rede.pedir(f"{self.spl}/processo.aspx?id={pid}", parar_em=_FIM_TRAMITACAO)
        return ler_processo(b.decode("utf-8", "replace")), self.rede.fio - antes

    def ler_paginas(self, alvo: dict[str, dict]) -> tuple[int, int, int]:
        """Lê (ou lê de novo) a página de cada proposição de `alvo` ({ID: linha da lista}) que precisa: nova, com a fase, o setor
        ou a situação mudada na lista, ou velha demais (as em andamento a cada refazer_dias, as arquivadas a cada 4 vezes
        isso). Devolve (lidas agora, sem página nenhuma ainda, bytes). Guarda a cada 20 páginas."""
        e = self._estado_paginas()
        fila = []
        hoje_ = dt.date.fromisoformat(self.h)
        for pid, r in alvo.items():
            x = e.get(pid)
            if x is None:
                fila.append((0, int(pid), pid))
                continue
            idade = (hoje_ - dt.date.fromisoformat(x["lido"])).days
            terminado = B.norm(r.get("situacao")).startswith("arquiv")
            if x.get("sig") != self.assinatura(r):
                fila.append((1, int(pid), pid))
            elif idade >= (self.refazer_dias * 4 if terminado else self.refazer_dias) + int(pid) % 7:
                fila.append((2, int(pid), pid))
        fila.sort()
        lidas, fio = 0, 0
        pausa_antes = self.rede.pausa
        if self.pausa_paginas:
            self.rede.pausa = max(self.rede.pausa, self.pausa_paginas)
        try:
            for prio, _, pid in fila:
                if self.max_mb_paginas and fio >= self.max_mb_paginas * 1e6:
                    raise SemTempo(f"limite de {self.max_mb_paginas:.0f} MB de páginas nesta rodada")
                p, n = self.pagina(pid)
                fio += n
                e[pid] = {"sig": self.assinatura(alvo[pid]), "lido": self.h, "p": p}
                lidas += 1
                if lidas % 20 == 0:
                    self.guardar_paginas()
        except SemTempo:
            pass
        finally:
            self.rede.pausa = pausa_antes
            self.guardar_paginas()
        return lidas, sum(1 for pid in alvo if pid not in e), fio

    # -------------------------------------------------------------- autores
    def autor_id(self, nome: str, cartoes: dict, pagina: dict | None) -> str | None:
        """O código de parlamentar de um autor da planilha: pela autoria da página da proposição (que tem o link), pelos
        cartões de vereadores do sistema ou pela lista conferida à mão."""
        k = chave_nome(nome)
        if not k:
            return None
        if k in self.autores_manual:
            return self.autores_manual[k]
        if pagina:
            for n, pid in pagina.get("autores") or []:
                if pid and chave_nome(n) == k:
                    return pid
        c = cartoes.get(k)
        if c:
            return c["id"]
        if pagina:  # nome escrito de outro jeito na planilha: todas as palavras de um dentro do outro, e só um serve
            ks = set(k.split())
            cands = {pid for n, pid in pagina.get("autores") or [] if pid and (ks <= set(chave_nome(n).split()) or
                                                                             set(chave_nome(n).split()) <= ks)}
            if len(cands) == 1:
                return cands.pop()
        return None

    # -------------------------------------------------------------- situação de uma proposição
    def situacao(self, r: dict, pagina: dict | None, norma: dict | None) -> dict:
        tipo = self.tipos[r["_tipo"]][0]
        sit = r.get("situacao")
        if pagina is not None:
            ev = EVENTOS[self.perfil](pagina)
            n = norma
            if not n and pagina.get("normas"):
                nome, href = pagina["normas"][0]
                nl = nome_lei(nome)
                n = {"nome": B.nome_norma(*nl) if nl and nl[2] else nome, "url": self.host + href if href.startswith("/") else href,
                     "data": None}
            s = resolver(ev, pagina.get("situacao") or sit, tipo, n, desde=r.get("data") or pagina.get("data"))
            if s["status"] == "lei" and not s["dataStatus"]:
                s["dataStatus"] = next((e.data for e in reversed(ev) if e.tipo == "lei"), None)
            if s.get("lei") and (s["lei"].get("url") or "").startswith("/"):
                s["lei"]["url"] = self.host + s["lei"]["url"]
            return s
        # sem a página (Cuiabá): a norma ligada, ou a fase atual da lista oficial
        if norma:
            nl = nome_lei(norma["nome"])
            nome = B.nome_norma(*nl) if nl and nl[2] else norma["nome"]
            return {"status": "lei", "statusTxt": B.virou(nome), "statusTxt_en": None, "dataStatus": norma.get("data"),
                    "lei": {"nome": nome, "url": norma.get("url")}}
        f = B.norm(r.get("fase"))
        for exp, (st, chave) in self.nota_fase.items():
            if re.search(exp, f):
                if chave in ("sancao", "na_prefeitura") and tipo not in ("PL", "PLP"):
                    chave = "promulgar"
                txt = TXT.get(chave) or B.TXT.get(chave) or (None, None)
                return {"status": st, "statusTxt": txt[0], "statusTxt_en": txt[1], "dataStatus": None, "lei": None}
        if B.norm(sit).startswith(("apensad", "anexad")):
            return {"status": "junta", "statusTxt": None, "statusTxt_en": None, "dataStatus": None, "lei": None}
        if B.norm(sit).startswith("arquiv"):
            return {"status": "arquivada", "statusTxt": None, "statusTxt_en": None, "dataStatus": None, "lei": None}
        return {"status": "andando", "statusTxt": None, "statusTxt_en": None, "dataStatus": None, "lei": None}

    def precisa_pagina(self, r: dict, norma: dict | None) -> bool:
        """Cuiabá: a página só é lida quando a lista e as normas não bastam (arquivada sem norma, "expedição de certificado"
        sem norma, ou uma fase que a lista não explica)."""
        if self.paginas == "todas":
            return True
        sit, f = B.norm(r.get("situacao")), B.norm(r.get("fase"))
        if norma:
            return "a pedido do autor" in f
        if "a pedido do autor" in f:
            return False
        if sit.startswith("arquiv") or "arquivar" in f or "certificado" in f or "receber processo" in f:
            return True
        return False

    # -------------------------------------------------------------- tudo
    def coletar(self) -> dict:
        t0 = time.time()
        h = self.h
        pessoas, cartoes, leg = self.vereadores()
        casa = dict(self.casa, sistema="Processo Legislativo Eletrônico (Ágape)",
                    fonte=fonte(self.casa["casa"], "Vereadores ativos na legislatura atual" + (f" ({leg})" if leg else ""),
                                f"{self.spl}/parlamentares.aspx", h))
        membros, por_chave, tse = C.membros(self.ibge, self.uf, casa, pessoas, self.vagas, self.tse_manual)
        etapa = "listas"
        try:
            linhas = self.todas_listas()
            etapa = "normas"
            normas = self.normas() if self.normas_tipos else {}
            etapa = "páginas das proposições"
            alvo = {i: r for i, r in linhas.items() if self.precisa_pagina(r, normas.get(i))}
            lidas, falta, fio = self.ler_paginas(alvo)
        except SemTempo as motivo:
            log(f"  {casa['sigla']}: parou em \"{etapa}\" ({motivo}; {self.rede.n} pedidos); continua na próxima rodada")
            return {"ok": True, "pendente": True, "etapa": etapa, "requisicoes": self.rede.n}
        if falta:
            log(f"  {casa['sigla']}: primeira carga das páginas das proposições em andamento ({len(alvo) - falta} de {len(alvo)}; "
                f"{lidas} lidas agora, {fio / 1e6:.0f} MB, {self.rede.n} pedidos, {time.time() - t0:.0f} s); nada publicado")
            return {"ok": True, "pendente": True, "etapa": f"páginas das proposições ({len(alvo) - falta} de {len(alvo)})",
                    "requisicoes": self.rede.n}
        paginas = self._estado_paginas()
        gastos, notas_gastos = None, []
        if self.gastos:
            try:
                gastos, notas_gastos = self.gastos(por_chave, self.rede.prazo)
            except Exception as erro:  # os gastos são um extra (o fim da rodada também cai aqui): fica o que estava publicado
                log(f"  {casa['sigla']}: gastos: {type(erro).__name__}: {str(erro)[:200]}; ficam os gastos publicados antes")
                gastos = C.publicados(self.ibge, "gastos")
                notas_gastos = [n for n in self._notas_publicadas() if re.match(r"(Os )?[Gg]astos do mandato", n[0])]
        r = self.montar(casa, membros, por_chave, cartoes, linhas, normas, paginas, gastos, notas_gastos)
        r["requisicoes"] = self.rede.n
        r["semTse"] = len(tse.sem_ligacao)
        log(f"  {casa['sigla']}: {len(membros)} no cargo, {r['propostas']} propostas, prefeito {r.get('prefeito')}, "
            f"{lidas} páginas lidas ({fio / 1e6:.1f} MB), {self.rede.n} pedidos ({self.rede.fio / 1e6:.1f} MB), {time.time() - t0:.0f} s")
        return r

    def montar(self, casa: dict, membros: list, por_chave: dict, cartoes: dict, linhas: dict, normas: dict, paginas: dict,
               gastos: dict | None = None, notas_extra: list | None = None) -> dict:
        h = self.h
        por_parl: dict[str, list] = {k: [] for k in por_chave}
        pref = B.cidade(self.ibge, self.uf).get("prefeito") or {}
        inicio_pref = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
        do_pref, sem_autor = [], 0
        for pid_, r in sorted(linhas.items()):
            if self.tipos[r["_tipo"]][0] not in regional.TIPOS_REGIONAIS:
                continue
            pag = (paginas.get(pid_) or {}).get("p")
            s = self.situacao(r, pag, normas.get(pid_))
            comum, sig = self.tipos[r["_tipo"]]
            url = f"{self.spl}/processo.aspx?id={pid_}"
            situ = r.get("situacao") + (f": {r['fase']}" if r.get("fase") else "")

            def item(papel):
                x = regional.proposta(f"cm{self.ibge}:{pid_}", f"{sig} {r['numero']}/{r['ano']}", comum, r.get("data") or (pag or {}).get("data"),
                                      r.get("ementa"), situ, url, papel, status=s["status"], data_status=s["dataStatus"],
                                      status_txt=s["statusTxt"], lei=s["lei"])
                if s.get("statusTxt_en"):
                    x["statusTxt_en"] = s["statusTxt_en"]
                return x
            autores = r.get("autores") or []
            if autores and self.executivo.search(autores[0]) and (r.get("data") or "") >= inicio_pref:
                do_pref.append(item("autor"))
            ligados = False
            for i, nome in enumerate(autores):
                aid = self.autor_id(nome, cartoes, pag)
                if aid in por_parl:
                    por_parl[aid].append(item("autor" if i == 0 else "coautor"))
                    ligados = True
            if not ligados and not (autores and self.executivo.search(autores[0])):
                sem_autor += 1
        f_sis = f"{self.spl}/consulta-tipo.aspx"
        escopo = (B.ESCOPO + ", segundo o Processo Legislativo Eletrônico, o sistema oficial da Câmara.",
                  B.ESCOPO_EN + ", according to the City Council's official legislative system (Processo Legislativo Eletrônico).")
        extras = {}
        for chave, m in por_chave.items():
            x = C.extras_base(m, casa)
            f_prop = fonte(casa["casa"], f"Processo Legislativo Eletrônico: proposições de {m['nome']}",
                           f"{self.spl}/consulta-producao.aspx?autor=" + (self._autor_de(chave) or ""), h) \
                if self._autor_de(chave) else fonte(casa["casa"], "Processo Legislativo Eletrônico: consulta por tipo", f_sis, h)
            x["propostas"] = regional.bloco_propostas(por_parl[chave], escopo[0], escopo[1], f_prop)
            x["fontes"].append(f_prop)
            if gastos and gastos.get(m["id"]):
                x["gastos"] = gastos[m["id"]]
                x["fontes"].append(gastos[m["id"]]["fonte"])
            extras[m["id"]] = x
        prefeito = None
        notas = list(self.notas_casa) + list(notas_extra or [])
        if pref.get("id"):
            desde_pt = ("desde 1º/1/2025, começo do mandato" if inicio_pref == B.INICIO
                        else f"desde {_data_pt(inicio_pref)}, quando assumiu a prefeitura")
            desde_en = ("since January 1, 2025 (start of the term)" if inicio_pref == B.INICIO
                        else f"since {_data_en(inicio_pref)}, when the current mayor took office")
            if do_pref:
                f_pref = fonte(casa["casa"], "Processo Legislativo Eletrônico: proposições do Poder Executivo", f_sis, h)
                prefeito = (pref["id"], {"propostas": regional.bloco_propostas(
                    do_pref, f"Projetos que a prefeitura mandou à Câmara Municipal {desde_pt} (projetos de lei, de lei complementar "
                             "e de emenda à Lei Orgânica), segundo o Processo Legislativo Eletrônico, o sistema oficial da Câmara",
                    f"Bills the mayor's office sent to the City Council {desde_en} (ordinary and complementary bills and amendments "
                    "to the city's Organic Law), according to the City Council's official legislative system", f_pref),
                    "fontes": [f_pref]})
        cobertura = {"lista": True, "propostas": True, "votacoes": False,
                     "gastos": any(x.get("gastos") for x in extras.values())}
        r = B.salvar(self.ibge, self.uf, casa, membros, extras, cobertura, notas, escopo, prefeito=prefeito)
        r["semAutorNoCargo"] = sem_autor
        return r

    def _notas_publicadas(self) -> list[tuple[str, str]]:
        casa = ler_json(regional.CAMARAS / f"{self.ibge}.json") or {}
        return list(zip(casa.get("notas") or [], casa.get("notas_en") or []))

    def _autor_de(self, chave: str) -> str | None:
        """O código de autor (consulta-producao.aspx?autor=...) de um parlamentar, pelo cartão dele na página de vereadores."""
        if not hasattr(self, "_autores_cartoes"):
            t = B.baixar_pagina(f"{self.spl}/parlamentares.aspx", self.ibge, "parlamentares", ua_navegador=True)
            self._autores_cartoes = {}
            for bloco in t.split("custom-user-profile'>")[1:]:
                pid = re.search(r"href='parlamentar\.aspx\?id=(\d+)'", bloco)
                aut = re.search(r"consulta-producao\.aspx\?autor=(\d+)", bloco)
                if pid and aut:
                    self._autores_cartoes[pid.group(1)] = aut.group(1)
        return self._autores_cartoes.get(str(chave))


def _data_pt(d: str) -> str:
    a = dt.date.fromisoformat(d[:10])
    return f"{'1º' if a.day == 1 else a.day}/{a.month}/{a.year}"


def _data_en(d: str) -> str:
    meses = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
             "December"]
    a = dt.date.fromisoformat(d[:10])
    return f"{meses[a.month - 1]} {a.day}, {a.year}"


__all__ = ["Agape", "Ev", "EVENTOS", "TXT", "resolver", "eventos_vitoria", "eventos_teresina", "eventos_cuiaba", "nome_lei",
           "ler_processo", "ler_normas_lista", "xlsx_linhas", "campos_form", "chave_nome", "texto", "SemTempo", "Rede"]
