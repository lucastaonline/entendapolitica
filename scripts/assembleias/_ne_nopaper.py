"""Coletor das Assembleias que usam o SPL da NoPaper/Ágape (API pública em <endereço>/api/publico/): BA e SE.

O que ele pega (só da API oficial da Casa, documentada na página "Dados Abertos" do portal legislativo):
1. quem está no cargo hoje: /api/publico/parlamentar/ (situação "Ativo" na legislatura atual), com partido, foto, e-mail,
   nome completo e o código de autor de cada pessoa;
2. propostas desde 1º/2/2023 (PL, PLP, PEC, PDL, PRC): /api/publico/proposicao/?tipoID=..&ano=.. (cada proposição já vem
   com o autor, os coautores, a situação e todas as tramitações). O filtro por data da API não é confiável na Alba (devolve
   proposições de outros anos), por isso o corte é por ano e, depois, pela data de apresentação;
3. contagem do resto (requerimentos, indicações, moções...) de cada pessoa, para "outros".

A API é lenta (cada proposição traz todas as tramitações): todo dia ela lê a 1ª página de cada tipo no ano atual (o que
acabou de chegar) e, até um limite de tempo, um "cursor" que passa por todas as páginas de todos os anos e recomeça quando
chega ao fim (cada proposição é relida a cada poucos dias). Cache em .cache/<pasta>/ (só o resumo de cada proposição).
"""
from __future__ import annotations

import os
import re
import time

import regional
from comum import chave_nome, data_iso, fonte, hoje, log, nome_proprio, sem_acento

from ._ne_comum import (ESCOPO, ESCOPO_EN, INICIO, Rede, casar_membros, com_status_en, gravar, legislatura_estadual, membro,
                        partido_sigla, resumo_status)


def _dh(v: str | None) -> str | None:
    """'11/06/2026 13:56:02' -> '2026-06-11T13:56:02' (para ordenar)."""
    if not v:
        return None
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}:\d{2}:\d{2}))?", v.strip())
    if not m:
        return None
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4) or '00:00:00'}"


class NoPaper:
    def __init__(self, uf: str, base: str, casa: str, casa_en: str, sigla: str, site: str, veiculo: str, prefixo: str,
                 pasta: str, tipos: dict[int, str], situacao, em_exercicio=None, tse_manual: dict | None = None,
                 pausa: float = 0.6, notas: list | None = None, orcamento_s: float = 150,
                 qtd_pessoas: int = 10, qtd: int = 25, filtro_pessoas: str = "", idade_pessoas_h: float = 20):
        """tipos = {tipoID da Casa: PL|PLP|PEC|PDL|PRC}; situacao(registro) -> {"status", "txt", "en", "data", "lei"}
        (regras próprias da Casa, lendo a situação e as tramitações); em_exercicio(coletor, parlamentares) -> lista
        filtrada (troca a regra padrão: situação "Ativo" na legislatura mais recente)."""
        self.uf, self.base = uf, base.rstrip("/")
        self.info = {"casa": casa, "casa_en": casa_en, "sigla": sigla, "site": site}
        self.veiculo, self.prefixo = veiculo, prefixo
        self.tipos, self.situacao = tipos, situacao
        self.em_exercicio, self.tse_manual = em_exercicio, tse_manual or {}
        self.notas = list(notas or [])
        self.orcamento_s = orcamento_s
        self.qtd_pessoas, self.qtd = qtd_pessoas, qtd
        self.filtro_pessoas, self.idade_pessoas_h = filtro_pessoas, idade_pessoas_h
        self.rede = Rede(pasta, pausa=pausa, timeout=180)

    def api(self, caminho: str, cache: str | None = None, max_idade_h: float | None = 20):
        return self.rede.json(self.base + caminho, cache, max_idade_h)

    # ------------------------------------------------------------ pessoas
    def parlamentares(self, max_idade_h: float | None = None) -> list[dict]:
        out, pag = [], 1
        idade = self.idade_pessoas_h if max_idade_h is None else max_idade_h
        while True:
            d = self.api(f"/api/publico/parlamentar/?pag={pag}&qtd={self.qtd_pessoas}{self.filtro_pessoas}", f"parlamentares-{pag}.json", idade)
            lote = d.get("parlamentares") or []
            out += lote
            if not lote or len(out) >= int(d.get("total") or 0):
                return out
            pag += 1

    def pessoas(self) -> list[dict]:
        ps = self.parlamentares()
        if self.em_exercicio:
            return self.em_exercicio(self, ps)
        atual = str(legislatura_estadual(20))  # a numeração da Alba e da Alese: 20ª legislatura = 2023-2027
        return [p for p in ps if str(p.get("parlamentarLegislatura")) == atual and (p.get("parlamentarSituacao") or "").lower() == "ativo"]

    # ------------------------------------------------------------ propostas (por janelas de um mês)
    def _resumo(self, x: dict) -> dict:
        trs = []
        for t in x.get("Tramitacoes") or []:
            quando = _dh(t.get("dataAcaoSaida")) or _dh(t.get("dataAssinatura")) or _dh(t.get("dataRecebimento")) or _dh(t.get("data"))
            trs.append([quando, (t.get("fase") or "").strip(), (t.get("acao") or "").strip(),
                        re.sub(r"\s+", " ", (t.get("complemento") or "")).strip()[:500], (t.get("setor") or "").strip(), t.get("id") or 0])
        trs.sort(key=lambda t: (t[0] or "", t[5]))
        anexos = [re.sub(r"\s+", " ", (a.get("descricao") or "")).strip()[:200] for a in x.get("TramitacaoAnexo") or [] if a.get("descricao")]
        co = []
        for c in x.get("CoAutores") or []:
            a = c.get("autorId") or c.get("autorID") or c.get("id")
            if a:
                co.append(int(a))
        return {"tid": int(x.get("tipoId") or 0), "s": (x.get("sigla") or "").strip(), "n": x.get("numero"), "a": x.get("ano"),
                "d": data_iso(x.get("data")), "e": re.sub(r"\s+", " ", (x.get("assunto") or "")).strip(),
                "au": int((x.get("AutorRequerenteDados") or {}).get("autorId") or 0) or None,
                "aun": ((x.get("AutorRequerenteDados") or {}).get("nomeRazao") or "").strip() or None, "co": co,
                "sit": (x.get("situacao") or "").strip() or None, "tr": trs[-8:], "nt": len(trs), "anx": anexos[-5:],
                "pr": (x.get("ProcessoPrincipal") or {}).get("id") or None}

    def _pagina(self, tipo: int, ano: int, pag: int, props: dict) -> int:
        """Uma página (qtd proposições) de um tipo num ano; devolve quantas páginas a janela tem."""
        d = self.api(f"/api/publico/proposicao/?pag={pag}&qtd={self.qtd}&tipoID={tipo}&ano={ano}")
        for x in d.get("Data") or []:
            props[str(x["id"])] = self._resumo(x)
        return max(1, int((d.get("Paginacao") or {}).get("quantidade") or 1))

    def propostas(self) -> dict:
        """A API é lenta (cada proposição vem com todas as tramitações). Todo dia: a 1ª página de cada tipo no ano atual
        (o que acabou de chegar) e, até o limite de tempo, um "cursor" que anda por todas as páginas de todos os anos
        (do mais novo para o mais antigo) e recomeça quando chega ao fim. Assim cada proposição é relida a cada poucos dias."""
        est = self.rede.estado("estado.json", {}) or {}
        props: dict[str, dict] = {k: v for k, v in (est.get("props") or {}).items() if (v.get("d") or "9999") >= f"{INICIO[:4]}-01-01"}
        feitas_em: dict[str, str] = est.get("janelas") or {}
        w, p = est.get("cursor") or [0, 1]
        h = hoje()
        anos = list(range(int(h[:4]), int(INICIO[:4]) - 1, -1))
        janelas = [(t, a) for a in anos for t in self.tipos]
        sem_limite = os.environ.get("NE_SEM_LIMITE") == "1"
        t0, pags = time.time(), 0
        for t in self.tipos:
            self._pagina(t, anos[0], 1, props)
            pags += 1
        if w >= len(janelas):
            w, p = 0, 1
        inicio_volta = (w, p)
        while sem_limite or time.time() - t0 < self.orcamento_s:
            if w >= len(janelas):
                w, p = 0, 1
            t, a = janelas[w]
            n = self._pagina(t, a, p, props)
            pags += 1
            if p >= n:
                feitas_em[f"{t}-{a}"] = h
                w, p = w + 1, 1
            else:
                p += 1
            if pags % 10 == 0:
                self.rede.guardar({"props": props, "janelas": feitas_em, "cursor": [w, p]}, "estado.json")
            if (w % len(janelas), p) == inicio_volta and pags > len(self.tipos):  # deu a volta completa
                break
        self.rede.guardar({"props": props, "janelas": feitas_em, "cursor": [w, p]}, "estado.json")
        faltam = [f"{t}-{a}" for t, a in janelas if not feitas_em.get(f"{t}-{a}")]
        log(f"  {self.uf}: {len(props)} propostas no cache; {pags} páginas lidas hoje"
            + (f"; {len(faltam)} janelas (tipo e ano) ainda sem a primeira leitura completa" if faltam else ""))
        return {"props": props, "faltam": faltam, "janelas": janelas}

    # ------------------------------------------------------------ tudo
    def outros(self, autor: int | None, n_propostas: int) -> dict | None:
        if not autor:
            return None
        d = self.api(f"/api/publico/proposicao/?pag=1&qtd=1&autorID={autor}&dataInicio={INICIO}", f"outros/{autor}.json", 24 * 7)
        n = int(d.get("total") or 0) - n_propostas
        if n <= 0:
            return None
        return {"total": n, "url": f"{self.base}/spl/parlamentar.aspx",
                "txt": "Requerimentos, indicações, moções e outros documentos (não são projetos)",
                "txt_en": "requests, suggestions to the government, motions and other documents (these are not bills)"}

    def coletar(self) -> dict:
        pessoas = self.pessoas()
        est = self.propostas()
        if est["faltam"] and len(est["faltam"]) > len(est["janelas"]) // 2:
            raise RuntimeError(f"{self.uf}: menos da metade das propostas baixadas; rode de novo (cache em andamento)")
        casar = [{"chave": p["parlamentarID"], "nome": p.get("parlamentarNome"), "nomeCivil": _civil(p.get("parlamentarRazaoSocial")),
                  "partido": partido_sigla(p.get("partidoSigla"))} for p in pessoas]
        ligados, avisos = casar_membros(self.uf, casar, self.tse_manual)
        for a in avisos:
            log(f"  {self.uf} TSE: {a}")
        por_autor: dict[int, list[tuple[str, str]]] = {}
        for k, v in est["props"].items():
            if v.get("au"):
                por_autor.setdefault(v["au"], []).append((k, "autor"))
            for c in v.get("co") or []:
                if c != v.get("au"):
                    por_autor.setdefault(c, []).append((k, "coautor"))
        membros, extras, listas = [], {}, []
        fonte_l = self.fonte_lista()
        for p in pessoas:
            nome = re.sub(r"\s+", " ", (p.get("parlamentarNome") or "").strip())
            if nome == nome.upper():
                nome = nome_proprio(nome)
            cand = ligados.get(str(p["parlamentarID"]))
            pid = regional.id_pessoa("dest", self.uf, cand, nome)
            url = f"{self.base}/spl/parlamentar.aspx?id={p['parlamentarID']}"
            civil = _civil(p.get("parlamentarRazaoSocial"))
            membros.append(membro(pid, nome, civil, partido_sigla(p.get("partidoSigla")), (cand or {}).get("genero"),
                                  p.get("parlamentarFoto"), url, p.get("_suplente", False)))
            autor = int(p.get("autorID") or 0) or None
            if not autor and civil:
                # a API não traz o código de autor de algumas pessoas: ele é achado pelo nome completo do autor das proposições
                alvo = chave_nome(civil)
                achados = {v["au"] for v in est["props"].values() if v.get("au") and chave_nome(v.get("aun")) == alvo}
                if len(achados) == 1:
                    autor = achados.pop()
            lista = []
            for k, papel in por_autor.get(autor, []) if autor else []:
                v = est["props"][k]
                tipo = self.tipos.get(v["tid"])
                if not tipo or (v.get("d") or "") < INICIO:
                    continue
                s = self.situacao(dict(v, _id=k))
                prop = regional.proposta(f"{self.prefixo}:{k}", f"{v['s'] or tipo} {v['n']}/{v['a']}", tipo, v.get("d"), v.get("e"),
                                         v.get("sit"), f"{self.base}/spl/processo.aspx?id={k}", papel=papel, status=s["status"],
                                         data_status=s.get("data"), status_txt=s.get("txt"), lei=s.get("lei"))
                lista.append(com_status_en(prop, s.get("en")))
            listas.append(lista)
            fonte_prop = fonte(self.veiculo, f"Proposições de {nome} (portal legislativo, dados abertos)", url)
            n_autor = sum(1 for x in lista if x["papel"] == "autor")
            bloco = regional.bloco_propostas(lista, ESCOPO, ESCOPO_EN, fonte_prop, self.outros(autor, n_autor))
            if bloco.get("outros"):
                bloco["outros"]["url"] = url
            extras[pid] = {"propostas": bloco,
                           "links": {"oficial": url, "email": (p.get("parlamentarEmail") or "").strip() or None, "redes": []},
                           "fontes": [fonte_l, fonte_prop]}
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        notas = list(self.notas)
        if est["faltam"]:
            notas.append((f"Ainda faltam propostas de {len(est['faltam'])} combinações de tipo e ano (a API é lenta; o coletor completa aos poucos).",
                          f"Bills from {len(est['faltam'])} type-and-year combinations are still missing (the API is slow; the collector fills them in gradually)."))
        cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
        r = gravar(self.uf, self.info, membros, extras, cobertura, fonte_l, notas)
        log(f"  {self.uf}: {self.rede.pedidos} pedidos ao site oficial")
        return r

    def fonte_lista(self) -> dict:
        return fonte(self.veiculo, "Deputados em exercício (portal legislativo, dados abertos)", f"{self.base}/spl/parlamentares.aspx")


def _civil(v: str | None) -> str | None:
    c = re.sub(r"\s+", " ", (v or "").strip())
    if not c:
        return None
    return nome_proprio(c) if c == c.upper() else c


def ultima(v: dict) -> list:
    return (v.get("tr") or [[None, "", "", "", "", 0]])[-1]


def texto_tramitacoes(v: dict, n: int = 8) -> str:
    """Situação + últimas tramitações + anexos, sem acento e em minúsculas (para as regras de cada Casa)."""
    partes = [v.get("sit") or ""] + [" ".join(str(x) for x in t[1:5]) for t in (v.get("tr") or [])[-n:]] + (v.get("anx") or [])
    return sem_acento(" | ".join(partes).lower())
