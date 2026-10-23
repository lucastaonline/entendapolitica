"""Coletor das Assembleias que usam o SAPL 3 do Interlegis (API pública em <endereço>/api/): PB, PI e AL.

O que ele pega (só da API oficial da Casa):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido de hoje,
   foto) + /api/parlamentares/mandato/ (titular ou suplente, datas) + /api/parlamentares/parlamentar/<id>/ (nome completo,
   sexo, e-mail). Cada Casa pode trocar a regra de "quem está no cargo" (ex.: Alagoas usa a página oficial da legislatura);
2. propostas desde 1º/2/2023 (PL, PLP, PEC, PDL, PRC): /api/materia/materialegislativa/ (com os autores),
   /api/materia/autoria/ (quem é o primeiro autor), situação = a da última tramitação (/api/materia/materiaemtramitacao/),
   a norma que a proposta virou (/api/norma/normajuridica/, campo "materia") e os vetos do governador (matérias do tipo
   veto, ligadas ao projeto pelo campo "anexadas" ou pelo número citado na ementa);
3. contagem do resto (requerimentos, indicações, moções, emendas...) de cada pessoa, para "outros".

Educado com o site: uma requisição por vez, pausa entre elas, páginas de 100, cache em .cache/<pasta>/ e atualização
incremental (só o que mudou desde a última vez: filtro data_ultima_atualizacao__gte), com uma revisão aos poucos das
situações (1/14 das propostas por dia) e uma lista completa a cada 30 dias (pega o que foi apagado).
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse

import regional
from comum import STATUS_TXT, data_iso, fonte, hoje, log, nome_proprio, sem_acento

from ._ne_comum import (INICIO, Rede, casar_membros, com_status_en, gravar, membro, nome_lei, partido_sigla, posse_atual,
                        resumo_status)

LOTE = 100
REVER_PARTES = 14      # a situação de cada proposta é conferida de novo pelo menos a cada 14 dias
LISTA_COMPLETA_DIAS = 30


def _agora_iso() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S")


def _menos_dias(iso: str, dias: int) -> str:
    d = dt.date.fromisoformat(iso[:10]) - dt.timedelta(days=dias)
    return d.isoformat()


# nome comum de cada tipo de norma (descrição oficial sem acento, minúsculas) -> nome usado no site
_NORMAS = [
    (r"lei complementar", "Lei Complementar"), (r"^lei( ordinaria)?( promulgada)?$", "Lei"),
    (r"emenda (a )?constitucional|emenda a constituicao", "Emenda Constitucional"),
    (r"decreto legislativo", "Decreto Legislativo"), (r"^resolucao", "Resolução"),
]


def nome_norma(descricao: str | None) -> str | None:
    d = sem_acento((descricao or "").lower()).strip()
    for exp, nome in _NORMAS:
        if re.search(exp, d):
            return nome
    return None  # autógrafo, decreto do governo, portaria, regimento...: não conta como "virou lei"


class SaplAssembleia:
    def __init__(self, uf: str, base: str, casa: str, casa_en: str, sigla: str, site: str, veiculo: str, prefixo: str,
                 tipos: dict[int, str], tipos_veto: dict[int, str | None], regras: list[tuple], pasta: str,
                 em_exercicio=None, tse_manual: dict | None = None, pausa: float = 0.6, notas: list | None = None,
                 pagina_pessoa: str | None = None, foto_pessoa=None, lista_oficial: tuple[str, str] | None = None):
        """tipos = {id do tipo de matéria no SAPL: PL|PLP|PEC|PDL|PRC}; tipos_veto = {id do tipo: "total"|"parcial"|None
        (None: lê na ementa)}; regras = [(expressão sem acento, status, texto pt ou None, texto en ou None)] para a situação
        da última tramitação; em_exercicio(coletor, parlamentares_da_legislatura) -> {id SAPL: dados extras} troca a regra
        padrão (ativo na legislatura atual); tse_manual = {id SAPL: SQ do TSE ou "-"} conferido à mão; lista_oficial =
        (título, endereço) da fonte da lista quando ela não vem do SAPL."""
        self.uf, self.base = uf, base.rstrip("/")
        self.info = {"casa": casa, "casa_en": casa_en, "sigla": sigla, "site": site}
        self.veiculo, self.prefixo = veiculo, prefixo
        self.tipos, self.tipos_veto, self.regras = tipos, tipos_veto, regras
        self.em_exercicio, self.tse_manual = em_exercicio, tse_manual or {}
        self.notas = list(notas or [])
        self.pagina_pessoa = pagina_pessoa or (self.base + "/parlamentar/{id}")
        self.foto_pessoa = foto_pessoa
        self.lista_oficial = lista_oficial
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

    def em_lotes(self, caminho: str, ids: list, campo: str = "materia__in") -> list[dict]:
        out = []
        ids = sorted({int(i) for i in ids})
        for k in range(0, len(ids), LOTE):
            parte = ",".join(str(i) for i in ids[k:k + LOTE])
            out += self.todos(f"{caminho}?{campo}={parte}")
        return out

    # ------------------------------------------------------------ pessoas
    def legislatura(self) -> dict:
        """A legislatura em curso: a mais recente que começou até a data da posse em curso (1º/2/2023, 1º/2/2027...).
        Assim a lista só troca no dia da posse, mesmo que a Casa cadastre a legislatura nova antes (ou com outra data)."""
        legs = self.todos("/api/parlamentares/legislatura/", "legislaturas", 24 * 7)
        limite = posse_atual()[:4]
        validas = [l for l in legs if (l.get("data_inicio") or "9999")[:4] <= limite]
        return sorted(validas or legs, key=lambda l: l.get("data_inicio") or "")[-1]

    def pessoas(self) -> tuple[list[dict], dict]:
        leg = self.legislatura()
        parls = self.todos(f"/api/parlamentares/legislatura/{leg['id']}/parlamentares/", f"leg{leg['id']}-parlamentares")
        mandatos = self.todos(f"/api/parlamentares/mandato/?legislatura={leg['id']}", f"leg{leg['id']}-mandatos")
        if self.em_exercicio:
            escolhidos = self.em_exercicio(self, parls)
        else:
            escolhidos = {p["id"]: {} for p in parls if p.get("ativo")}
        por_id = {p["id"]: p for p in parls}
        h = hoje()
        out = []
        for pid, extra in escolhidos.items():
            p = dict(por_id.get(pid) or {"id": pid})
            det = self.api(f"/api/parlamentares/parlamentar/{pid}/", f"parlamentar/{pid}.json", 24 * 7)
            ms = [m for m in mandatos if m.get("parlamentar") == pid]
            atuais = [m for m in ms if (m.get("data_inicio_mandato") or "") <= h <= (m.get("data_fim_mandato") or "9999")] or ms
            m = sorted(atuais, key=lambda m: m.get("data_inicio_mandato") or "")[-1] if atuais else {}
            titular = any(x.get("titular") for x in ms)
            p.update({"det": det, "mandato": m, "suplente": not titular if ms else False})
            p.update(extra)
            out.append(p)
        return out, leg

    def autores(self) -> dict[int, int]:
        """{id do parlamentar no SAPL: id de autor}"""
        tipos = self.todos("/api/base/tipoautor/", "tipoautor", 24 * 7)
        tparl = [t["id"] for t in tipos if sem_acento((t.get("descricao") or "").lower()).strip() == "parlamentar"]
        out = {}
        for t in tparl:
            for a in self.todos(f"/api/base/autor/?tipo={t}", f"autores-{t}", 24 * 7):
                pid = a.get("object_id") or ((a.get("autor_related") or {}).get("value"))
                if pid:
                    out[int(pid)] = a["id"]
        return out

    # ------------------------------------------------------------ matérias (incremental)
    def _materia_curta(self, x: dict) -> dict:
        return {"t": x["tipo"], "n": x.get("numero"), "a": x.get("ano"), "d": x.get("data_apresentacao"),
                "e": (x.get("ementa") or "").strip(), "au": x.get("autores") or [], "u": x.get("data_ultima_atualizacao"),
                "tr": x.get("em_tramitacao"), "an": x.get("anexadas") or []}

    def materias(self) -> dict:
        est = self.rede.estado("estado.json", {}) or {}
        mats: dict[str, dict] = est.get("materias") or {}
        normas: dict[str, dict] = est.get("normas") or {}
        vetos: dict[str, dict] = est.get("vetos") or {}
        agora = _agora_iso()
        completo = est.get("completo") or ""
        cheio = not mats or not completo or (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(completo[:10])).days >= LISTA_COMPLETA_DIAS
        tipos = ",".join(str(t) for t in self.tipos)
        filtro = "" if cheio else f"&data_ultima_atualizacao__gte={_menos_dias(est.get('ultimo') or agora, 3)}"
        lidas = self.todos(f"/api/materia/materialegislativa/?tipo__in={tipos}&data_apresentacao__gte={INICIO}{filtro}")
        mudaram = set()
        if cheio:
            novos = {str(x["id"]): self._materia_curta(x) for x in lidas}
            for k, v in novos.items():
                antigo = mats.get(k) or {}
                if antigo.get("u") != v["u"]:
                    mudaram.add(k)
                else:
                    v["aut"], v["st"] = antigo.get("aut"), antigo.get("st")
            mats = novos
        else:
            for x in lidas:
                k = str(x["id"])
                v = self._materia_curta(x)
                antigo = mats.get(k) or {}
                if antigo.get("u") != v["u"]:
                    mudaram.add(k)
                else:
                    v["aut"], v["st"] = antigo.get("aut"), antigo.get("st")
                mats[k] = v
        # a situação de quem não mudou é conferida de novo aos poucos (1/14 por dia), e quem nunca teve situação também
        parte = dt.date.fromisoformat(hoje()).toordinal() % REVER_PARTES
        rever = {k for k, v in mats.items() if k in mudaram or v.get("st") is None or int(k) % REVER_PARTES == parte}
        # autoria: só quando há mais de um autor (com um só, ele é o autor principal)
        pedir_aut = {k for k in rever if len(mats[k]["au"]) > 1 and (k in mudaram or mats[k].get("aut") is None)}
        for k in pedir_aut:
            mats[k]["aut"] = {}
        for a in self.em_lotes("/api/materia/autoria/", list(pedir_aut)):
            k = str(a["materia"])
            if k in pedir_aut:
                mats[k]["aut"][str(a["autor"])] = [bool(a.get("primeiro_autor")), a["id"]]
        for t in self.em_lotes("/api/materia/materiaemtramitacao/", list(rever)):
            v = mats.get(str(t["materia"]))
            if v is None:
                continue
            partes = (t.get("__str__") or "").rsplit(" | ", 2)
            st = partes[1].strip() if len(partes) == 3 else None
            v["st"] = [None if st in (None, "", "None") else st, data_iso(partes[2].strip()) if len(partes) == 3 else None,
                       t.get("tramitacao")]
        for k in rever:  # sem tramitação nenhuma
            if mats[k].get("st") is None:
                mats[k]["st"] = [None, None, None]
        # normas que vieram de uma proposta ("virou lei") e vetos do governador
        filtro_n = "" if cheio or not normas else f"&data_ultima_atualizacao__gte={_menos_dias(est.get('ultimo') or agora, 3)}"
        if cheio:
            normas = {}
        for n in self.todos(f"/api/norma/normajuridica/?data__gte={INICIO[:4]}-01-01{filtro_n}"):
            if n.get("materia"):
                normas[str(n["id"])] = {"m": n["materia"], "t": n.get("tipo"), "n": n.get("numero"), "a": n.get("ano"),
                                        "d": n.get("data"), "s": n.get("__str__")}
        if self.tipos_veto:
            tv = ",".join(str(t) for t in self.tipos_veto)
            filtro_v = "" if cheio or not vetos else f"&data_ultima_atualizacao__gte={_menos_dias(est.get('ultimo') or agora, 3)}"
            if cheio:
                vetos = {}
            for x in self.todos(f"/api/materia/materialegislativa/?tipo__in={tv}&data_apresentacao__gte={INICIO[:4]}-01-01{filtro_v}"):
                vetos[str(x["id"])] = {"t": x["tipo"], "e": (x.get("ementa") or "").strip(), "an": x.get("anexadas") or [],
                                       "d": x.get("data_apresentacao"), "n": x.get("numero"), "a": x.get("ano")}
        est = {"materias": mats, "normas": normas, "vetos": vetos, "ultimo": agora,
               "completo": agora if cheio else completo}
        self.rede.guardar(est, "estado.json")
        log(f"  {self.uf}: {len(mats)} propostas no cache ({len(mudaram)} mudaram, {len(rever)} conferidas), "
            f"{len(normas)} normas, {len(vetos)} vetos")
        return est

    def tipos_norma(self) -> dict[int, str | None]:
        return {t["id"]: nome_norma(t.get("descricao")) for t in self.todos("/api/norma/tiponormajuridica/", "tiponorma", 24 * 7)}

    # ------------------------------------------------------------ situação
    def ligar_vetos(self, est: dict) -> dict[str, dict]:
        """{id da proposta: {"total": bool, "d": data}} a partir das matérias do tipo veto."""
        mats = est["materias"]
        indice = {}
        for k, v in mats.items():
            indice.setdefault((self.tipos.get(v["t"]), str(v["n"]), str(v["a"])), k)
        out = {}
        for vid, v in est["vetos"].items():
            e = sem_acento(v["e"].lower())
            tot = self.tipos_veto.get(v["t"])
            if tot is None:
                tot = "total" if re.search(r"veto total|vetar totalmente|totalmente", e) else "parcial" if re.search(r"veto parcial|parcialmente", e) else None
            alvos = [str(a) for a in v["an"] if str(a) in mats]
            if not alvos:
                m = re.search(r"projeto de lei( complementar)?( ordinaria)?\s*n?[^\d]{0,6}([\d.]+)\s*/\s*(\d{4})", e)
                if m:
                    tipo = "PLP" if m.group(1) else "PL"
                    k = indice.get((tipo, str(int(m.group(3).replace(".", ""))), m.group(4)))
                    if k:
                        alvos = [k]
            for k in alvos:
                atual = out.get(k)
                if not atual or (v["d"] or "") > (atual["d"] or ""):
                    out[k] = {"total": tot == "total", "parcial": tot == "parcial", "d": v["d"]}
        return out

    def situacao(self, k: str, v: dict, norma: dict | None, veto: dict | None, nomes_norma: dict) -> dict:
        texto, data_st = (v.get("st") or [None, None])[:2]
        if norma:
            nome = nomes_norma.get(norma["t"])
            if nome:
                nl = nome_lei(nome, norma["n"], norma["a"])
                parcial = bool(veto and veto.get("parcial"))
                return {"status": "lei", "txt": f"Virou {'o' if nome.startswith('Decreto') else 'a'} {nl}" + (" (com partes vetadas)" if parcial else ""),
                        "en": None, "data": norma.get("d") or data_st, "lei": {"nome": nl, "url": f"{self.base}/norma/{norma['id']}"}}
        if veto and veto.get("total"):
            return {"status": "rejeitada", "txt": "Vetada por inteiro pelo governador", "en": "Fully vetoed by the governor",
                    "data": veto.get("d") or data_st, "lei": None}
        if not texto and not data_st:  # nenhuma tramitação ainda
            return {"status": "andando", "txt": "Apresentada; ainda vai começar a ser analisada", "en": None, "data": None, "lei": None}
        t = sem_acento((texto or "").lower())
        for exp, st, pt, en in self.regras:
            if re.search(exp, t):
                return {"status": st, "txt": pt, "en": en, "data": data_st, "lei": None}
        st = regional.situacao_para_status(texto)
        return {"status": st, "txt": None, "en": None, "data": data_st, "lei": None}

    # ------------------------------------------------------------ tudo
    def coletar(self) -> dict:
        pessoas, leg = self.pessoas()
        autores = self.autores()
        est = self.materias()
        nomes_norma = self.tipos_norma()
        norma_de = {}
        for nid, n in est["normas"].items():
            if nomes_norma.get(n["t"]):
                n = dict(n, id=nid)
                atual = norma_de.get(str(n["m"]))
                if not atual or (n.get("d") or "") < (atual.get("d") or ""):
                    norma_de[str(n["m"])] = n
        vetos = self.ligar_vetos(est)
        # TSE
        casar = [{"chave": p["id"], "nome": p.get("nome_parlamentar") or p["det"].get("nome_parlamentar"),
                  "nomeCivil": p["det"].get("nome_completo"), "partido": partido_sigla(p.get("partido"))} for p in pessoas]
        ligados, avisos = casar_membros(self.uf, casar, self.tse_manual)
        for a in avisos:
            log(f"  {self.uf} TSE: {a}")
        # propostas de cada pessoa
        por_autor: dict[int, list[str]] = {}
        for k, v in est["materias"].items():
            for a in v["au"]:
                por_autor.setdefault(int(a), []).append(k)
        membros, extras, listas = [], {}, []
        hoje_ = hoje()
        for p in pessoas:
            det = p["det"]
            nome = _limpa_nome(p.get("nome_parlamentar") or det.get("nome_parlamentar"))
            cand = ligados.get(str(p["id"]))
            pid = regional.id_pessoa("dest", self.uf, cand, nome)
            genero = det.get("sexo") if det.get("sexo") in ("F", "M") else (cand or {}).get("genero")
            foto = p.get("foto") or (self.foto_pessoa(p) if self.foto_pessoa else None) or det.get("fotografia") or p.get("fotografia")
            url = p.get("url") or self.pagina_pessoa.format(id=p["id"])
            partido = partido_sigla(p.get("partido_site") or p.get("partido"))
            membros.append(membro(pid, nome, _civil(det.get("nome_completo"), nome), partido, genero, foto, url, p.get("suplente")))
            autor = autores.get(int(p["id"]))
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
                s = self.situacao(k, v, norma_de.get(k), vetos.get(k), nomes_norma)
                sigla = f"{self.sigla_tipo(v['t'])} {v['n']}/{v['a']}"
                prop = regional.proposta(f"{self.prefixo}:{k}", sigla, tipo, v.get("d"), v.get("e"), (v.get("st") or [None])[0],
                                         f"{self.base}/materia/{k}", papel=papel, status=s["status"], data_status=s["data"],
                                         status_txt=s["txt"], lei=s["lei"])
                lista.append(com_status_en(prop, s["en"]))
            listas.append(lista)
            fonte_prop = fonte(self.veiculo, f"Matérias legislativas de {nome} (SAPL)",
                               f"{self.base}/materia/pesquisar-materia?autoria__autor={autor}" if autor else f"{self.base}/materia/pesquisar-materia")
            bloco = regional.bloco_propostas(lista, *_escopo(), fonte_prop, self.outros(autor, nome))
            m = p.get("mandato") or {}
            x = {"propostas": bloco,
                 "mandato": {"inicio": m.get("data_inicio_mandato"), "fim": m.get("data_fim_mandato"),
                             "situacao": "Suplente em exercício" if p.get("suplente") else "Em exercício", "obs": None,
                             "fonte": fonte(self.veiculo, f"Mandato de {nome} (SAPL)", url)} if m.get("data_inicio_mandato") else None,
                 "links": {"oficial": url, "email": (det.get("email") or "").strip() or None, "redes": p.get("redes") or []},
                 "fontes": [self.fonte_lista(leg), fonte_prop]}
            if not x["mandato"]:
                x.pop("mandato")
            extras[pid] = x
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
        r = gravar(self.uf, self.info, membros, extras, cobertura, self.fonte_lista(leg), self.notas)
        log(f"  {self.uf}: {self.rede.pedidos} pedidos ao site oficial")
        return r

    def fonte_lista(self, leg: dict) -> dict:
        if self.lista_oficial:
            titulo, url = self.lista_oficial
            return fonte(self.veiculo, titulo, url)
        return fonte(self.veiculo, f"Deputados em exercício na {leg.get('numero')}ª legislatura (SAPL, dados abertos)",
                     f"{self.base}/parlamentar/")

    _siglas: dict | None = None

    def sigla_tipo(self, t: int) -> str:
        if self._siglas is None:
            self._siglas = {x["id"]: x["sigla"].strip() for x in self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 7)}
        return self._siglas.get(t) or self.tipos.get(t) or "?"

    def outros(self, autor: int | None, nome: str) -> dict | None:
        """Quantos documentos que não são projetos (requerimentos, indicações, moções, emendas...) a pessoa apresentou."""
        if not autor:
            return None
        if not hasattr(self, "_outros_tipos"):
            todos = self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 7)
            veto = set(self.tipos_veto)
            self._outros_tipos = ",".join(str(x["id"]) for x in todos if x["id"] not in self.tipos and x["id"] not in veto)
        d = self.api(f"/api/materia/materialegislativa/?autores={autor}&tipo__in={self._outros_tipos}&data_apresentacao__gte={INICIO}&page_size=1",
                     f"outros/{autor}.json", 24 * 7)
        n = (d.get("pagination") or {}).get("total_entries") or 0
        if not n:
            return None
        return {"total": n, "url": f"{self.base}/materia/pesquisar-materia?autoria__autor={autor}",
                "txt": "Requerimentos, indicações, moções, emendas e outros documentos (não são projetos)",
                "txt_en": "requests, suggestions to the government, motions, amendments and other documents (these are not bills)"}


def _escopo():
    from ._ne_comum import ESCOPO, ESCOPO_EN
    return ESCOPO, ESCOPO_EN


def _limpa_nome(nome: str | None) -> str:
    """'DEPUTADA ÂNGELA GARROTE' -> 'Ângela Garrote' (o título "Deputado(a)" já aparece no cargo)."""
    n = re.sub(r"^\s*deputad[oa]\s+", "", (nome or "").strip(), flags=re.I)
    if n and n == n.upper():
        n = nome_proprio(n)
    return re.sub(r"\s+", " ", n).strip()


def _civil(civil: str | None, nome: str) -> str | None:
    c = re.sub(r"\s+", " ", (civil or "").strip())
    if not c:
        return None
    if c == c.upper():
        c = nome_proprio(c)
    return c
