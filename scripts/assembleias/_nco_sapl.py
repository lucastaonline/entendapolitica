"""Coletor das Assembleias que usam o SAPL 3 do Interlegis (API pública em <endereço>/api/): AM, AC, RO, RR e TO.

O que ele pega (só da API oficial da Casa, e da página oficial quando a Casa mantém a lista lá):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido,
   foto) + /api/parlamentares/mandato/ (titular ou suplente, datas) + /api/parlamentares/parlamentar/<id>/ (nome completo,
   sexo, e-mail). Uma Casa pode trocar a lista (ex.: Tocantins, onde a lista oficial com partido está no site da Casa);
2. propostas desde 1º/2/2023 (PL, PLP, PEC, PDL, PRC): /api/materia/materialegislativa/ (com os autores),
   /api/materia/autoria/ (quem é o primeiro autor, só quando há mais de um), a situação de hoje (última tramitação:
   /api/materia/materiaemtramitacao/, conferida para todas as propostas a cada rodada) e a norma que a proposta virou
   (/api/norma/normajuridica/, campo "materia");
3. contagem do resto (requerimentos, indicações, moções, emendas...) de cada pessoa, para "outros";
4. votações nominais (/api/sessao/registrovotacao/ + /api/sessao/votoparlamentar/), só nas Casas em que o voto de cada
   deputado é registrado no SAPL de forma regular (ligado por Casa, depois de conferido).

Educado com o site: uma requisição por vez, pausa entre elas, páginas de 100, cache em .cache/<pasta>/ e atualização
incremental das listas grandes (filtro data_ultima_atualizacao__gte), com lista completa a cada 30 dias (pega o que foi
apagado).
"""
from __future__ import annotations

import datetime as dt
import re
import time

import regional
from comum import STATUS_TXT, chave_nome, data_iso, fonte, hoje, log, sem_acento

from ._nco_comum import (INICIO, OUTROS_TXT, Rede, casar_membros, classificar, com_status_en, gravar, limpa_civil,
                         limpa_nome, membro, nome_civil, nome_lei, nome_norma, artigo, partido_sigla, resumo_status)

LOTE = 100
LISTA_COMPLETA_DIAS = 30


def _agora_iso() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S")


def _menos_dias(iso: str, dias: int) -> str:
    return (dt.date.fromisoformat(iso[:10]) - dt.timedelta(days=dias)).isoformat()


class Sapl:
    def __init__(self, uf: str, base: str, casa: str, casa_en: str, sigla: str, site: str, veiculo: str, prefixo: str,
                 tipos: dict[int, str], regras: list[tuple], pasta: str, *, lista_oficial=None, tse_manual: dict | None = None,
                 pausa: float = 0.6, notas: list | None = None, vagas: int = 24, votacoes: bool = False,
                 nomes: dict | None = None, posse: str = "02-01", ambiguos: list[str] | None = None,
                 lista_url: str | None = None, lista_titulo: str | None = None):
        """tipos = {id do tipo de matéria no SAPL: PL|PLP|PEC|PDL|PRC}; regras = [(expressão sem acento, status, frase pt ou
        None, frase en ou None)] para a situação da última tramitação; lista_oficial(coletor, parlamentares) -> lista de
        {"sapl": id SAPL ou None, "nome", "partido", "foto", "url", "email", "redes"} troca a regra padrão (ativos na
        legislatura atual); tse_manual = {nome ou id SAPL: SQ do TSE ou "-"} conferido à mão; nomes = {id SAPL: nome usado
        no cargo} quando o SAPL escreve diferente da Casa."""
        self.uf, self.base = uf, base.rstrip("/")
        self.info = {"casa": casa, "casa_en": casa_en, "sigla": sigla, "site": site}
        self.veiculo, self.prefixo, self.tipos, self.regras = veiculo, prefixo, tipos, regras
        self.lista_oficial, self.tse_manual = lista_oficial, tse_manual or {}
        self.notas = list(notas or [])
        self.vagas, self.com_votacoes, self.nomes, self.posse = vagas, votacoes, nomes or {}, posse
        self.ambiguos = list(ambiguos or [])
        self.lista_url, self.lista_titulo = lista_url, lista_titulo
        self.rede = Rede(pasta, pausa=pausa)

    # ------------------------------------------------------------ API
    def api(self, caminho: str, cache: str | None = None, max_idade_h: float | None = 20):
        return self.rede.json(self.base + caminho, cache, max_idade_h)

    def todos(self, caminho: str, cache: str | None = None, max_idade_h: float | None = 20) -> list[dict]:
        out, pag = [], 1
        while True:
            sep = "&" if "?" in caminho else "?"
            d = self.api(f"{caminho}{sep}page={pag}&page_size={LOTE}", f"{cache}-{pag}.json" if cache else None, max_idade_h)
            out += d.get("results") or []
            if not (d.get("pagination") or {}).get("next_page"):
                return out
            pag += 1

    def total(self, caminho: str) -> int:
        sep = "&" if "?" in caminho else "?"
        return int((self.api(f"{caminho}{sep}page_size=1").get("pagination") or {}).get("total_entries") or 0)

    def em_lotes(self, caminho: str, ids, campo: str = "materia__in") -> list[dict]:
        out = []
        ids = sorted({int(i) for i in ids})
        for k in range(0, len(ids), LOTE):
            parte = ",".join(str(i) for i in ids[k:k + LOTE])
            out += self.todos(f"{caminho}?{campo}={parte}")
        return out

    # ------------------------------------------------------------ pessoas
    def legislatura(self) -> dict:
        legs = self.todos("/api/parlamentares/legislatura/", "legislaturas", 20)
        h = hoje()
        atuais = [l for l in legs if (l.get("data_inicio") or "") <= h <= (l.get("data_fim") or "9999")]
        if not atuais:  # entre o fim de uma e o começo da outra (ex.: SAPL de Roraima termina em 31/12): a mais recente
            atuais = sorted([l for l in legs if (l.get("data_inicio") or "") <= h], key=lambda l: l.get("data_inicio") or "")[-1:]
        leg = sorted(atuais, key=lambda l: l.get("data_inicio") or "")[-1]
        fim = leg.get("data_fim") or "9999-12-31"
        if fim < h:
            # a legislatura seguinte toma posse no 1º de fevereiro depois do fim desta (Roraima cadastra o fim em 31/12)
            ano = int(fim[:4])
            posse = f"{ano}-{self.posse}" if fim <= f"{ano}-{self.posse}" else f"{ano + 1}-{self.posse}"
            if h >= posse:  # passou da posse e a Casa ainda não cadastrou a legislatura nova: melhor não mostrar a lista velha
                raise RuntimeError(f"{self.uf}: a legislatura nova ainda não está no SAPL (a última terminou em {fim})")
        return leg

    def pessoas(self) -> tuple[list[dict], dict]:
        leg = self.legislatura()
        parls = self.todos(f"/api/parlamentares/legislatura/{leg['id']}/parlamentares/")
        mandatos = self.todos(f"/api/parlamentares/mandato/?legislatura={leg['id']}")
        por_id = {p["id"]: p for p in parls}
        if self.lista_oficial:
            escolhidos = self.lista_oficial(self, parls)
        else:
            escolhidos = [{"sapl": p["id"]} for p in parls if p.get("ativo")]
        h = hoje()
        out = []
        for e in escolhidos:
            sid = e.get("sapl")
            p = dict(por_id.get(sid) or {})
            p.update({k: v for k, v in e.items() if v is not None})
            det = self.api(f"/api/parlamentares/parlamentar/{sid}/", f"parlamentar/{sid}.json", 24 * 7) if sid else {}
            ms = [m for m in mandatos if m.get("parlamentar") == sid]
            atuais = [m for m in ms if (m.get("data_inicio_mandato") or "") <= h <= (m.get("data_fim_mandato") or "9999")] or ms
            m = sorted(atuais, key=lambda m: m.get("data_inicio_mandato") or "")[-1] if atuais else {}
            p.update({"det": det or {}, "mandato": m, "titular_sapl": m.get("titular") if m else None})
            out.append(p)
        return out, leg

    def autores(self) -> dict[int, int]:
        """{id do parlamentar no SAPL: id de autor}"""
        tipos = self.todos("/api/base/tipoautor/", "tipoautor", 24 * 7)
        tparl = [t["id"] for t in tipos if re.sub(r"\W", "", (t.get("descricao") or "").lower()) == "parlamentar"]
        out = {}
        for t in tparl:
            for a in self.todos(f"/api/base/autor/?tipo={t}", f"autores-{t}", 20):
                pid = a.get("object_id") or ((a.get("autor_related") or {}).get("value"))
                if pid:
                    out[int(pid)] = a["id"]
        return out

    # ------------------------------------------------------------ matérias (incremental)
    @staticmethod
    def _curta(x: dict) -> dict:
        return {"t": x["tipo"], "n": x.get("numero"), "a": x.get("ano"), "d": x.get("data_apresentacao"),
                "e": (x.get("ementa") or "").strip(), "au": x.get("autores") or [], "u": x.get("data_ultima_atualizacao"),
                "an": x.get("anexadas") or []}

    def materias(self) -> dict:
        est = self.rede.estado("estado.json", {}) or {}
        mats: dict[str, dict] = est.get("materias") or {}
        normas: dict[str, dict] = est.get("normas") or {}
        agora = _agora_iso()
        completo = est.get("completo") or ""
        cheio = (not mats or not completo or est.get("tipos") != sorted(self.tipos)
                 or (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(completo[:10])).days >= LISTA_COMPLETA_DIAS)
        desde = _menos_dias(est.get("ultimo") or agora, 3)
        tipos = ",".join(str(t) for t in sorted(self.tipos))
        filtro = "" if cheio else f"&data_ultima_atualizacao__gte={desde}"
        lidas = self.todos(f"/api/materia/materialegislativa/?tipo__in={tipos}&data_apresentacao__gte={INICIO}{filtro}")
        novos = {str(x["id"]): self._curta(x) for x in lidas}
        if cheio:
            antigos, mats = mats, {}
        else:
            antigos = mats
        mudaram = set()
        for k, v in novos.items():
            a = antigos.get(k) or {}
            if a.get("u") != v["u"] or a.get("au") != v["au"]:
                mudaram.add(k)
            elif a.get("aut") is not None:
                v["aut"] = a["aut"]
            for campo in ("st", "fim"):  # situação de antes (é conferida de novo logo abaixo, quando preciso)
                if a.get(campo) is not None:
                    v[campo] = a[campo]
            mats[k] = v
        # autoria (quem é o autor principal): só quando há mais de um autor; com um só, ele é o autor principal
        pedir = {k for k, v in mats.items() if len(v["au"]) > 1 and (k in mudaram or v.get("aut") is None)}
        for k in pedir:
            mats[k]["aut"] = {}
        for a in self.em_lotes("/api/materia/autoria/", pedir):
            k = str(a["materia"])
            if k in pedir:
                mats[k]["aut"][str(a["autor"])] = [bool(a.get("primeiro_autor")), a["id"]]
        # situação de hoje (última tramitação), 100 propostas por pedido: todas as que ainda andam, as novas ou mudadas e,
        # das que já chegaram ao fim (lei, arquivada, rejeitada, retirada, parada), 1/7 por dia (todas numa semana)
        parte = dt.date.fromisoformat(hoje()).toordinal() % 7
        rever = [k for k, v in mats.items() if not v.get("fim") or k in mudaram or v.get("st") is None or int(k) % 7 == parte]
        sits = {}
        for t in self.em_lotes("/api/materia/materiaemtramitacao/", rever):
            partes = (t.get("__str__") or "").rsplit(" | ", 2)
            if len(partes) == 3:
                sits[str(t["materia"])] = [partes[1].strip() or None, data_iso(partes[2].strip()), t.get("tramitacao")]
        for k in rever:
            mats[k]["st"] = sits.get(k) or [None, None, None]
        # normas que vieram de uma proposta ("virou lei")
        filtro_n = "" if cheio or not normas else f"&data_ultima_atualizacao__gte={desde}"
        if cheio:
            normas = {}
        for n in self.todos(f"/api/norma/normajuridica/?data__gte={INICIO[:4]}-01-01{filtro_n}"):
            if n.get("materia"):
                normas[str(n["id"])] = {"m": n["materia"], "t": n.get("tipo"), "n": n.get("numero"), "a": n.get("ano"),
                                        "d": n.get("data")}
            else:
                normas.pop(str(n["id"]), None)
        # quem já chegou ao fim só é conferido de novo 1 vez por semana (ver acima)
        com_norma = {str(n["m"]) for n in normas.values()}
        for k, v in mats.items():
            txt = (v.get("st") or [None])[0]
            v["fim"] = 1 if (k in com_norma or (txt and not self.ambiguo(txt)
                                                and classificar(txt, self.regras)[0] in ("lei", "arquivada", "rejeitada", "retirada", "parada"))) else 0
        est = {"materias": mats, "normas": normas, "ultimo": agora, "completo": agora if cheio else completo,
               "tipos": sorted(self.tipos)}
        self.rede.guardar(est, "estado.json")
        log(f"  {self.uf}: {len(mats)} propostas no cache ({len(mudaram)} novas ou mudadas, {len(rever)} situações conferidas), "
            f"{len(normas)} normas ligadas a propostas")
        return est

    def tipos_norma(self) -> dict[int, str | None]:
        return {t["id"]: nome_norma(t.get("descricao")) for t in self.todos("/api/norma/tiponormajuridica/", "tiponorma", 24 * 7)}

    _siglas: dict | None = None

    def sigla_tipo(self, t: int) -> str:
        if self._siglas is None:
            self._siglas = {x["id"]: (x.get("sigla") or "").strip() for x in
                            self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 7)}
        return self._siglas.get(t) or self.tipos.get(t) or "?"

    # ------------------------------------------------------------ situação
    MORTAS = ("arquivada", "rejeitada", "retirada", "parada")

    def ambiguo(self, texto: str | None) -> bool:
        t = sem_acento((texto or "").lower())
        return any(re.search(e, t) for e in self.ambiguos)

    def historico(self, k: str, ult) -> list[list]:
        """Tramitações da proposta, da mais nova para a mais antiga: [[data, situação oficial, texto]]. Guardado no cache
        até aparecer uma tramitação nova."""
        arq = f"historico/{k}.json"
        h = self.rede.estado(arq)
        if h and h.get("ult") == ult:
            return h["h"]
        if not hasattr(self, "_status_tram"):
            self._status_tram = {s["id"]: (s.get("descricao") or "").strip()
                                 for s in self.todos("/api/materia/statustramitacao/", "statustramitacao", 24 * 7)}
        ts = self.todos(f"/api/materia/tramitacao/?materia={k}")
        ts.sort(key=lambda t: (t.get("data_tramitacao") or "", t.get("id") or 0), reverse=True)
        out = [[t.get("data_tramitacao"), self._status_tram.get(t.get("status"), ""), re.sub(r"\s+", " ", t.get("texto") or "").strip()]
               for t in ts]
        self.rede.guardar({"ult": ult, "h": out}, arq)
        return out

    def decide_historico(self, k: str, v: dict):
        """Para situações que não dizem nada sozinhas ("Para providências", "Requerimento deferido"...): o texto da
        tramitação ou, se ele não decide, a tramitação de antes. Devolve (status, frase pt, frase en, data, texto) ou None."""
        for d, s, tx in self.historico(k, v["st"][2]):
            if self.ambiguo(s):
                if tx:
                    st, pt, en = classificar(tx, self.regras)
                    if st not in ("outra", "andando"):
                        return st, pt, en, d, f"{s}: {tx}"[:300]
                continue
            st, pt, en = classificar(s, self.regras)
            return st, pt, en, d, s
        return None

    def situacao(self, k: str, v: dict, norma: dict | None, nomes_norma: dict) -> dict:
        texto, data_st = (v.get("st") or [None, None])[:2]
        st, pt, en = classificar(texto, self.regras) if texto else ("outra", None, None)
        oficial = texto
        if texto and self.ambiguo(texto):
            r = self.decide_historico(k, v)
            # o histórico só vale se disser algo mais do que a própria situação ("andando" não ganha de "andando")
            if r and (r[0] not in ("andando", "outra") or st == "outra"):
                st, pt, en, data_st, oficial = r
        if norma:
            nome = nomes_norma.get(norma["t"])
            # norma ligada a uma proposta retirada pelo autor, rejeitada numa votação, ou arquivada antes de a norma existir
            # é erro de cadastro (ex.: a lei veio de outro projeto parecido): vale a tramitação. Veto mantido com norma é
            # veto parcial (a lei existe, sem as partes vetadas).
            t_of = sem_acento((oficial or "").lower())
            depois = bool(data_st and norma.get("d") and norma["d"] > data_st)
            confiavel = not (st == "retirada" or (st == "rejeitada" and "veto" not in t_of)
                             or (st in ("arquivada", "parada", "rejeitada") and depois))
            if nome and confiavel:
                nl = nome_lei(nome, norma["n"], norma["a"])
                return {"status": "lei", "txt": f"Virou {artigo(nome)} {nl}", "en": None, "data": norma.get("d") or data_st,
                        "lei": {"nome": nl, "url": f"{self.base}/norma/{norma['id']}"}, "oficial": oficial}
        if not texto:
            return {"status": "outra", "txt": "A Assembleia não informa a situação", "en": "The state assembly does not report its status",
                    "data": None, "lei": None, "oficial": None}
        return {"status": st, "txt": pt, "en": en, "data": data_st, "lei": None, "oficial": oficial}

    # ------------------------------------------------------------ outros documentos
    def outros(self, autor: int | None) -> dict | None:
        """Quantos documentos que não são projetos (requerimentos, indicações, moções, emendas...) a pessoa apresentou."""
        if not autor:
            return None
        if not hasattr(self, "_outros_tipos"):
            todos = self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 7)
            self._outros_tipos = ",".join(str(x["id"]) for x in todos if x["id"] not in self.tipos)
        d = self.api(f"/api/materia/materialegislativa/?autores={autor}&tipo__in={self._outros_tipos}"
                     f"&data_apresentacao__gte={INICIO}&page_size=1", f"outros/{autor}.json", 24 * 7)
        n = (d.get("pagination") or {}).get("total_entries") or 0
        if not n:
            return None
        return {"total": n, "url": f"{self.base}/materia/pesquisar-materia?autoria__autor={autor}",
                "txt": OUTROS_TXT[0], "txt_en": OUTROS_TXT[1]}

    # ------------------------------------------------------------ tudo
    def fonte_lista(self, leg: dict) -> dict:
        if self.lista_url:
            return fonte(self.veiculo, self.lista_titulo or "Deputados em exercício (página oficial)", self.lista_url)
        return fonte(self.veiculo, f"Deputados em exercício na {leg.get('numero')}ª legislatura (SAPL, dados abertos)",
                     f"{self.base}/parlamentar/")

    def coletar(self) -> dict:
        pessoas, leg = self.pessoas()
        autores = self.autores()
        est = self.materias()
        nomes_norma = self.tipos_norma()
        norma_de: dict[str, dict] = {}
        for nid, n in est["normas"].items():
            if nomes_norma.get(n["t"]):
                n = dict(n, id=nid)
                atual = norma_de.get(str(n["m"]))
                if not atual or (n.get("d") or "") < (atual.get("d") or ""):
                    norma_de[str(n["m"])] = n
        # TSE
        casar = [{"chave": str(p.get("sapl") or p.get("nome")), "nome": self.nome_de(p),
                  "nomeCivil": limpa_civil((p.get("det") or {}).get("nome_completo")),
                  "partido": partido_sigla(p.get("partido_site") or p.get("partido"))} for p in pessoas]
        ligados, avisos = casar_membros(self.uf, casar, self.tse_manual, self.posse)
        for a in avisos:
            log(f"  {self.uf} TSE: {a}")
        self.avisos_tse = avisos
        por_autor: dict[int, list[str]] = {}
        for k, v in est["materias"].items():
            for a in v["au"]:
                por_autor.setdefault(int(a), []).append(k)
        votos = self.votacoes(pessoas, leg, est) if self.com_votacoes else {}
        membros, extras, listas = [], {}, []
        sit_de: dict[str, dict] = {}
        for p, c in zip(pessoas, casar):
            det = p.get("det") or {}
            nome = c["nome"]
            cand = ligados.get(c["chave"])
            pid = regional.id_pessoa("dest", self.uf, cand, nome)
            genero = det.get("sexo") if det.get("sexo") in ("F", "M") else (cand or {}).get("genero")
            foto = p.get("foto") or det.get("fotografia") or p.get("fotografia")
            url = p.get("url") or f"{self.base}/parlamentar/{p['sapl']}"
            suplente = bool((cand and cand["sit"] == "SUPLENTE") or p.get("titular_sapl") is False)
            civil = nome_civil(c["nomeCivil"], nome, cand)
            membros.append(membro(pid, nome, civil, c["partido"], genero, foto, url, suplente))
            autor = autores.get(int(p["sapl"])) if p.get("sapl") else None
            lista = []
            for k in por_autor.get(autor, []) if autor else []:
                v = est["materias"][k]
                tipo = self.tipos.get(v["t"])
                if not tipo:
                    continue
                aut = v.get("aut") or {}
                if len(v["au"]) <= 1:
                    papel = "autor"
                elif aut:
                    primeiros = [int(a) for a, (pr, _) in aut.items() if pr]
                    if not primeiros:  # a Casa não marcou o primeiro autor: vale o primeiro cadastrado
                        primeiros = [int(min(aut.items(), key=lambda x: x[1][1])[0])]
                    papel = "autor" if autor in primeiros else "coautor"
                else:
                    papel = "autor" if v["au"][0] == autor else "coautor"
                if k not in sit_de:
                    sit_de[k] = self.situacao(k, v, norma_de.get(k), nomes_norma)
                s = sit_de[k]
                sigla = f"{self.sigla_tipo(v['t'])} {v['n']}/{v['a']}"
                prop = regional.proposta(f"{self.prefixo}:{k}", sigla, tipo, v.get("d"), v.get("e"), s["oficial"],
                                         f"{self.base}/materia/{k}", papel=papel, status=s["status"], data_status=s["data"],
                                         status_txt=s["txt"], lei=s["lei"])
                lista.append(com_status_en(prop, s["en"]))
            listas.append(lista)
            fonte_prop = fonte(self.veiculo, f"Matérias legislativas de {nome} (SAPL, dados abertos)",
                               f"{self.base}/materia/pesquisar-materia?autoria__autor={autor}" if autor else f"{self.base}/materia/pesquisar-materia")
            bloco = regional.bloco_propostas(lista, *self.escopo(), fonte_prop, self.outros(autor))
            m = p.get("mandato") or {}
            x = {"propostas": bloco,
                 "links": {"oficial": url, "email": (p.get("email") or det.get("email") or "").strip() or None,
                           "redes": p.get("redes") or []},
                 "fontes": [self.fonte_lista(leg), fonte_prop]}
            if p.get("sapl"):
                x["fontes"].append(fonte(self.veiculo, f"Ficha de {nome} no SAPL", f"{self.base}/parlamentar/{p['sapl']}"))
            if votos.get(p.get("sapl")):
                x["votacoes"] = votos[p["sapl"]]
            extras[pid] = x
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        self.listas = listas
        cobertura = {"lista": True, "propostas": True, "votacoes": bool(votos), "gastos": False}
        notas = list(self.notas)
        legis = {"numero": leg.get("numero"), "inicio": leg.get("data_inicio"), "fim": leg.get("data_fim")}
        if self.lista_oficial:  # lista do site da Casa: depois da posse, só vale se o site já trocou a lista
            from ._nco_comum import conferir_virada, legislatura_por_data
            conferir_virada(self.rede, self.uf, [c["nome"] for c in casar], legislatura_por_data(self.posse))
        r = gravar(self.uf, self.info, membros, extras, cobertura, self.fonte_lista(leg), notas, minimo=self.vagas - 4,
                   legislatura=legis)
        if len(membros) != self.vagas:
            log(f"  {self.uf}: ATENÇÃO: {len(membros)} pessoas na lista oficial (a Casa tem {self.vagas} vagas)")
        log(f"  {self.uf}: {self.rede.pedidos} pedidos ao site oficial")
        return r

    def nome_de(self, p: dict) -> str:
        if p.get("sapl") in self.nomes:
            return self.nomes[p["sapl"]]
        return limpa_nome(p.get("nome_site") or p.get("nome_parlamentar") or (p.get("det") or {}).get("nome_parlamentar"))

    @staticmethod
    def escopo() -> tuple[str, str]:
        from ._nco_comum import ESCOPO, ESCOPO_EN
        return ESCOPO, ESCOPO_EN

    # ------------------------------------------------------------ votações (só onde a Casa registra o voto de cada um)
    # voto como o SAPL escreve -> como o site guarda (js/traducoes.js, D.voto: Sim, Não, Abstenção e códigos de ausência)
    VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "nao votou": "NR", "obstrucao": "Obstrução",
            "presidente": "PS", "presidencia": "PS", "presidente da sessao": "PS", "ausente": "NCOM"}

    def votacoes(self, pessoas: list[dict], leg: dict, est: dict) -> dict:
        """{id SAPL do deputado: bloco "votacoes" do perfil}. Grava o catálogo dados/votacoes/<prefixo>.json (cada votação
        uma vez só, no formato do README). Só votações nominais (com o voto de cada um) desde o começo da legislatura."""
        from comum import DADOS, salvar_json, sem_mudar_data
        inicio = max(leg.get("data_inicio") or INICIO, INICIO)
        vt = self.rede.estado("votos.json", {}) or {}
        primeira = not vt.get("regs") or vt.get("inicio") != inicio
        regs: dict = {} if primeira else vt["regs"]
        votos: dict = {} if primeira else vt["votos"]
        sess: dict = {} if primeira else vt.get("sess") or {}
        # janelas de um mês: na primeira vez são muitas páginas (o voto de cada um desde 2023); o progresso fica gravado a
        # cada mês, e uma rodada que cair no meio continua de onde parou. Depois, só os últimos 7 dias de novo.
        feito = vt.get("feito") if not primeira else None
        desde = inicio if not feito else max(inicio, _menos_dias(feito, 7))
        amanha = (dt.date.fromisoformat(hoje()) + dt.timedelta(days=1)).isoformat()
        janelas, a = [], desde
        while a < amanha:
            b = min(amanha, (dt.date.fromisoformat(a[:8] + "01") + dt.timedelta(days=32)).replace(day=1).isoformat())
            janelas.append((a, b))
            a = b
        def janela(a: str, b: str) -> None:
            """Uma janela de datas; se o SAPL demorar demais (504), divide em duas e tenta de novo."""
            try:
                regs_j, votos_j, sess_j = {}, {}, {}
                for r in self.todos(f"/api/sessao/registrovotacao/?data_hora__gte={a}&data_hora__lt={b}"):
                    regs_j[str(r["id"])] = {"d": (r.get("data_hora") or "")[:10], "m": r.get("materia"), "o": r.get("ordem"),
                                            "x": r.get("expediente"), "r": r.get("tipo_resultado_votacao"),
                                            "s": r.get("__str__") or "", "obs": (r.get("observacao") or "").strip()}
                for v in self.todos(f"/api/sessao/votoparlamentar/?data_hora__gte={a}&data_hora__lt={b}"):
                    votos_j.setdefault(str(v["votacao"]), {})[str(v["parlamentar"])] = v.get("voto")
                for o in self.todos(f"/api/sessao/ordemdia/?data_ordem__gte={a}&data_ordem__lt={b}&tipo_votacao=2"):
                    sess_j["o" + str(o["id"])] = o.get("sessao_plenaria")
                for o in self.todos(f"/api/sessao/expedientemateria/?data_ordem__gte={a}&data_ordem__lt={b}&tipo_votacao=2"):
                    sess_j["e" + str(o["id"])] = o.get("sessao_plenaria")
            except RuntimeError:
                da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
                if (db - da).days <= 4:
                    raise
                meio = (da + (db - da) / 2).isoformat()
                log(f"  {self.uf}: o SAPL demorou com as votações de {a} a {b}; dividindo a janela")
                time.sleep(20)
                janela(a, meio)
                janela(meio, b)
                return
            regs.update(regs_j)
            for k, v in votos_j.items():
                votos.setdefault(k, {}).update(v)
            sess.update(sess_j)

        for a, b in janelas:
            janela(a, b)
            self.rede.guardar({"regs": regs, "votos": votos, "sess": sess, "inicio": inicio,
                               "feito": min(b, hoje())}, "votos.json")
        resultados = {t["id"]: t.get("nome") for t in self.todos("/api/sessao/tiporesultadovotacao/", "tiporesultado", 24 * 7)}
        tipos_desc = {}
        for t in self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 7):
            tipos_desc[sem_acento((t.get("descricao") or "").lower()).strip()] = (t.get("sigla") or "").strip()
        mats = est["materias"]
        catalogo, por_parl = {}, {}
        for rid, r in regs.items():
            vs = votos.get(rid)
            if not vs:
                continue  # votação simbólica: sem o voto de cada um
            chave = f"{self.prefixo}-vot:{rid}"
            m = str(r.get("m") or "")
            nome_m = self._nome_materia(r["s"], tipos_desc)
            ementa = (mats.get(m) or {}).get("e") or self._ementa(m)
            if r.get("o") and sess.get(f"o{r['o']}"):
                url = f"{self.base}/sessao/{sess['o' + str(r['o'])]}/votacao-nominal-transparencia/{r['o']}/{m}?&materia=ordem"
            elif r.get("x") and sess.get(f"e{r['x']}"):
                url = f"{self.base}/sessao/{sess['e' + str(r['x'])]}/votacao-nominal-transparencia/{r['x']}/{m}?&materia=expediente"
            else:
                url = f"{self.base}/materia/{m}"
            catalogo[chave] = {"data": r["d"] or None, "propostaId": f"{self.prefixo}:{m}" if m in mats else None,
                               "proposta": nome_m, "descricao": ementa or r.get("obs") or None,
                               "resultado": resultados.get(r.get("r")), "url": url}
            for parl, voto in vs.items():
                v = self.VOTO.get(sem_acento((voto or "").lower()).strip(), voto or "NR")
                por_parl.setdefault(int(parl), []).append([chave, v, r["d"] or ""])
        arq_rel = f"dados/votacoes/{self.prefixo}.json"
        arq = DADOS / "votacoes" / f"{self.prefixo}.json"
        fonte_v = fonte(self.veiculo, "Votações nominais do Plenário (SAPL, dados abertos)", f"{self.base}/sessao/pesquisar-sessao")
        if catalogo:
            dados = {"votacoes": dict(sorted(catalogo.items(), key=lambda kv: (kv[1]["data"] or "", kv[0]), reverse=True)),
                     "fonte": fonte_v, "atualizado": hoje()}
            salvar_json(arq, sem_mudar_data(dados, arq))
        out = {}
        nome_casa = self.info["sigla"]
        for parl, lista in por_parl.items():
            lista.sort(key=lambda x: (x[2], x[0]), reverse=True)
            resumo = {"total": len(lista), "Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
            for _, v, _ in lista:
                resumo[v if v in resumo else "Outro"] += 1
            out[parl] = {"escopo": f"Votações nominais (com o voto de cada deputado) no Plenário da {nome_casa} desde 1º/2/2023",
                         "escopo_en": f"Roll-call votes (where each member's vote is recorded) in the full {nome_casa} since February 1, 2023",
                         "resumo": resumo, "fonte": fonte_v, "arquivo": arq_rel, "votos": [[c, v] for c, v, _ in lista]}
        log(f"  {self.uf}: {len(catalogo)} votações nominais desde {inicio}; votos de {len(out)} deputados")
        return out

    @staticmethod
    def _nome_materia(s: str, tipos_desc: dict) -> str | None:
        """'Ordem: Ordem do Dia/Expediente: 1 - Projeto de Lei Ordinária nº 44 de 2026 em 49ª Ordinária ...' -> 'PL 44/2026'."""
        m = re.search(r"Expediente:\s*\d+\s*-\s*(.+?)\s+n[ºo°]\s*(\d+)\s+de\s+(\d{4})", s or "")
        if not m:
            return None
        sigla = tipos_desc.get(sem_acento(m.group(1).lower()).strip())
        if not sigla:
            return None  # sem sigla conhecida: o texto oficial fica só na descrição (a página em inglês mostra este campo)
        return f"{sigla} {m.group(2)}/{m.group(3)}"

    def _ementa(self, m: str) -> str | None:
        """Ementa de uma matéria que não está no cache das propostas (requerimentos, vetos, projetos de antes de 2023).
        No máximo 300 novas por rodada (as outras vêm nas próximas), para não pesar no site da Casa."""
        if not m:
            return None
        arq = self.rede.pasta / f"materia/{m}.json"
        if not arq.exists():
            self._novas_ementas = getattr(self, "_novas_ementas", 0) + 1
            if self._novas_ementas > 300:
                return None
        try:
            d = self.api(f"/api/materia/materialegislativa/{m}/", f"materia/{m}.json", None)
        except Exception:
            return None
        return (d.get("ementa") or "").strip() or None
