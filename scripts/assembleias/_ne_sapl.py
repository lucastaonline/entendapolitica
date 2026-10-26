"""Coletor das Assembleias que usam o SAPL 3 do Interlegis (API pública em <endereço>/api/): PB, PI e AL.

O que ele pega (só da API oficial da Casa):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido de hoje,
   foto) + /api/parlamentares/mandato/ (titular ou suplente, datas) + /api/parlamentares/parlamentar/<id>/ (nome completo,
   sexo, e-mail). Cada Casa pode trocar a regra de "quem está no cargo" (ex.: Alagoas usa a página oficial da legislatura);
2. propostas desde 1º/2/2023 (PL, PLP, PEC, PDL, PRC): /api/materia/materialegislativa/ (com os autores),
   /api/materia/autoria/ (quem é o primeiro autor), situação = a da última tramitação (/api/materia/materiaemtramitacao/),
   a norma que a proposta virou (/api/norma/normajuridica/, campo "materia") e os vetos do governador (matérias do tipo
   veto, ligadas ao projeto pelo campo "anexadas" ou pelo número citado na ementa);
3. contagem do resto (requerimentos, indicações, moções, emendas...) de cada pessoa, para "outros";
4. com gov={...}: o que o governo do estado fez (dados/pessoas/gov-<UF>.json, ver _ne_gov.py): as matérias de autoria do
   Executivo no período (situação como as dos deputados), as leis ordinárias e complementares com data no período (sem as
   que a própria Assembleia promulgou, quando a Casa registra isso) e as matérias do tipo veto recebidas no período.

Educado com o site (seção 6 do contrato): o robots.txt dos SAPL do Interlegis pede 60 s entre pedidos ("Crawl-delay"), e
a Rede de _ne_comum respeita isso (um pedido por minuto). Por isso cada rodada gasta poucos pedidos: páginas de 100 (o
máximo do SAPL), cache em .cache/<pasta>/ e só o que mudou desde a última rodada (filtros data_ultima_atualizacao__gte nas
matérias e normas e data_tramitacao__gte nas tramitações); a situação das outras propostas é conferida em rodízio (um lote
de 100 por rodada); as fichas dos deputados e as contagens de "outros" são relidas aos poucos; e uma página da lista
completa por rodada acha as matérias apagadas. Há um limite de tempo por rodada (ORCAMENTO_S): o que não couber fica para
a próxima, e o arquivo é gravado com o que já está no cache.
Primeira carga (cache vazio, como no robô do GitHub): matérias, normas e vetos página por página, depois a autoria e a
situação de cada matéria, as fichas e as contagens de "outros", usando o tempo todo da rodada (ver _carga.py) e
guardando o progresso a cada página; enquanto ela não termina, nada é gravado em dados/ (ficam os arquivos de antes) e o
coletor devolve "em andamento". Com 60 s entre pedidos, leva alguns dias (PB ~290 pedidos; AL e PI ~130).
"""
from __future__ import annotations

import collections
import datetime as dt
import re
import time

import regional
from comum import data_iso, fonte, hoje, log, nome_proprio, sem_acento

from . import _carga
from . import _ne_gov as gv
from ._carga import SemTempo
from ._ne_comum import (INICIO, Rede, casar_membros, com_status_en, gravar, membro, nome_lei, partido_sigla, posse_atual,
                        resumo_status)

LOTE = 100                 # o maior page_size que o SAPL aceita
ORCAMENTO_S = 30 * 60      # tempo por rodada (com 60 s entre pedidos, uns 30 pedidos); o essencial vem primeiro
ORCAMENTO_CARGA_S = 50 * 60  # primeira carga rodando sozinha (sem legislativos.py --minutos); com --minutos, a rodada toda
GIRO_LOTES = 1             # lotes de 100 propostas cuja situação é conferida de novo por rodada, em rodízio
FICHA_DIAS, FICHAS_POR_RODADA = 30, 2      # ficha de cada deputado (nome completo, sexo, e-mail): relida a cada 30 dias
OUTROS_DIAS, OUTROS_POR_RODADA = 7, 2      # contagem de "outros documentos" de cada deputado
CONFERIR_POR_RODADA = 5    # matérias que sumiram da lista completa, conferidas uma a uma (apagadas de verdade?)


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
                 pagina_pessoa: str | None = None, foto_pessoa=None, lista_oficial: tuple[str, str] | None = None,
                 gov: dict | None = None):
        """tipos = {id do tipo de matéria no SAPL: PL|PLP|PEC|PDL|PRC}; tipos_veto = {id do tipo: "total"|"parcial"|None
        (None: lê na ementa)}; regras = [(expressão sem acento, status, texto pt ou None, texto en ou None)] para a situação
        da última tramitação; em_exercicio(coletor, parlamentares_da_legislatura) -> {id SAPL: dados extras} troca a regra
        padrão (ativo na legislatura atual); tse_manual = {id SAPL: SQ do TSE ou "-"} conferido à mão; lista_oficial =
        (título, endereço) da fonte da lista quando ela não vem do SAPL; gov = o que entra no perfil do governador:
        {"autores": [ids de autor do Executivo], "tipos": {id do tipo: PL|PLP|PEC|PDL|PRC|MPV}, "tipos_lei": [ids dos tipos
        de norma lei ordinária e complementar] ou None (sem contagem de leis), "promulgada": função(norma) -> True (a
        Assembleia promulgou), False (o governador sancionou) ou None (sem a informação), "criterio_leis": (pt, en) que
        completa "contam como sancionadas as N ...", "autores_fora": [ids de autor cujos vetos não entram (governo
        anterior)], "nota_prop": (pt, en) ou None, "tipos_txt": (pt, en) ou None}."""
        self.uf, self.base = uf, base.rstrip("/")
        self.info = {"casa": casa, "casa_en": casa_en, "sigla": sigla, "site": site}
        self.veiculo, self.prefixo = veiculo, prefixo
        self.tipos, self.tipos_veto, self.regras = tipos, tipos_veto, regras
        self.em_exercicio, self.tse_manual = em_exercicio, tse_manual or {}
        self.notas = list(notas or [])
        self.pagina_pessoa = pagina_pessoa or (self.base + "/parlamentar/{id}")
        self.foto_pessoa = foto_pessoa
        self.lista_oficial = lista_oficial
        self.gov = gov
        self.rede = Rede(pasta, pausa=pausa)
        self.t0 = time.time()
        self.orcamento = ORCAMENTO_S
        self.carga = False               # primeira carga em andamento (nada é gravado em dados/)
        self.sem_ficha: set = set()      # deputados sem a ficha no cache (lida quando houver tempo)

    # ------------------------------------------------------------ tempo da rodada
    def tem_tempo(self, pedidos: int = 1) -> bool:
        """Cabem mais `pedidos` nesta rodada? (cada pedido custa o intervalo do site: 60 s nos SAPL do Interlegis). Vale o
        menor entre o limite desta Casa (ORCAMENTO_S; na primeira carga, a rodada toda) e o fim da rodada inteira
        (legislativos.py --minutos, menos a folga de _carga.py)."""
        limite = self.t0 + self.orcamento
        fim = _carga.fim_rodada()
        if fim is not None:
            limite = min(limite, fim)
        return time.time() + pedidos * self.rede.atraso(self.base + "/api/") <= limite

    def _idade_h(self, cache: str) -> float | None:
        p = self.rede.pasta / cache
        return (time.time() - p.stat().st_mtime) / 3600 if p.exists() and p.stat().st_size else None

    def _desde(self) -> str:
        """Primeiro dia das matérias guardadas: o começo da legislatura (deputados) ou o do mandato de quem governa, o que
        vier antes (as do governo de janeiro de 2023 também entram no perfil do governador)."""
        return min(INICIO, gv.periodo(self.uf)["inicio"]) if self.gov else INICIO

    def _tipos_lista(self) -> dict[int, str]:
        return {**self.tipos, **((self.gov or {}).get("tipos") or {})}

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
        # fichas: as que faltam são lidas já; das guardadas, as mais antigas (mais de FICHA_DIAS) aos poucos
        idades = {pid: self._idade_h(f"parlamentar/{pid}.json") for pid in escolhidos}
        velhas = sorted((i, pid) for pid, i in idades.items() if i is not None and i > FICHA_DIAS * 24)
        reler = {pid for _, pid in velhas[-FICHAS_POR_RODADA:]}
        h = hoje()
        out = []
        for pid, extra in escolhidos.items():
            p = dict(por_id.get(pid) or {"id": pid})
            nova = idades[pid] is None or (pid in reler and self.tem_tempo(15))
            if idades[pid] is None and not self.tem_tempo(1):  # sem tempo para a ficha nova: fica para a próxima rodada
                det = {}
                self.sem_ficha.add(pid)
            else:
                det = self.api(f"/api/parlamentares/parlamentar/{pid}/", f"parlamentar/{pid}.json", 0 if nova else None)
            ms = [m for m in mandatos if m.get("parlamentar") == pid]
            atuais = [m for m in ms if (m.get("data_inicio_mandato") or "") <= h <= (m.get("data_fim_mandato") or "9999")] or ms
            m = sorted(atuais, key=lambda m: m.get("data_inicio_mandato") or "")[-1] if atuais else {}
            titular = any(x.get("titular") for x in ms)
            p.update({"det": det, "mandato": m, "suplente": not titular if ms else False})
            p.update(extra)
            out.append(p)
        return out, leg

    def autores(self, faltam: set[int] | None = None) -> dict[int, int]:
        """{id do parlamentar no SAPL: id de autor} (lista guardada por 30 dias; relida antes se alguém de hoje não tem
        código de autor nela)."""
        tipos = self.todos("/api/base/tipoautor/", "tipoautor", 24 * 30)
        tparl = [t["id"] for t in tipos if sem_acento((t.get("descricao") or "").lower()).strip() == "parlamentar"]

        def ler(idade):
            out = {}
            for t in tparl:
                for a in self.todos(f"/api/base/autor/?tipo={t}", f"autores-{t}", idade):
                    pid = a.get("object_id") or ((a.get("autor_related") or {}).get("value"))
                    if pid:
                        out[int(pid)] = a["id"]
            return out

        out = ler(24 * 30)
        if faltam and not set(faltam) <= set(out) and all((self._idade_h(f"autores-{t}-1.json") or 0) > 20 for t in tparl):
            out = ler(0)
        return out

    # ------------------------------------------------------------ matérias (incremental)
    def _materia_curta(self, x: dict) -> dict:
        return {"t": x["tipo"], "n": x.get("numero"), "a": x.get("ano"), "d": x.get("data_apresentacao"),
                "e": (x.get("ementa") or "").strip(), "au": x.get("autores") or [], "u": x.get("data_ultima_atualizacao"),
                "tr": x.get("em_tramitacao"), "an": x.get("anexadas") or []}

    @staticmethod
    def _situacao_tram(t: dict) -> list:
        """[situação, data, id da tramitação] de um registro de /api/materia/materiaemtramitacao/."""
        partes = (t.get("__str__") or "").rsplit(" | ", 2)
        st = partes[1].strip() if len(partes) == 3 else None
        return [None if st in (None, "", "None") else st, data_iso(partes[2].strip()) if len(partes) == 3 else None,
                t.get("tramitacao")]

    def _norma_curta(self, n: dict, normas: dict, normas_gov: dict, tipos_lei: set, ini_g: str | None) -> None:
        if n.get("materia"):
            normas[str(n["id"])] = {"m": n["materia"], "t": n.get("tipo"), "n": n.get("numero"), "a": n.get("ano"),
                                    "d": n.get("data"), "s": n.get("__str__")}
        if n.get("tipo") in tipos_lei and (n.get("data") or "") >= ini_g:
            normas_gov[str(n["id"])] = {c: n.get(c) for c in ("id", "materia", "tipo", "numero", "ano", "data",
                                                               "veiculo_publicacao", "observacao")}

    @staticmethod
    def _veto_curto(x: dict) -> dict:
        return {"t": x["tipo"], "e": (x.get("ementa") or "").strip(), "an": x.get("anexadas") or [],
                "d": x.get("data_apresentacao"), "n": x.get("numero"), "a": x.get("ano"), "au": x.get("autores") or []}

    def _primeira_carga(self, est: dict) -> dict:
        """Primeira carga (cache vazio), aos poucos e sem pressa: matérias, normas e vetos página por página (o progresso
        fica em est["carga"] e no estado.json a cada página), depois a autoria e a situação de cada matéria, em lotes de
        100. Quando tudo foi lido, "ultimo" vira o começo da carga: a rodada seguinte pega, pelo caminho de todo dia, o
        que mudou enquanto a carga andava."""
        self.carga = True
        desde, tipos = self._desde(), sorted(self._tipos_lista())
        base_m = "/api/materia/materialegislativa/"
        c = est.get("carga")
        if not c:
            c = {"inicio": _agora_iso(), "fase": "materias", "pag": 1}
            est.clear()
            est.update({"carga": c, "materias": {}, "normas": {}, "normas_gov": {}, "vetos": {},
                        "cfg": {"desde": desde, "tipos": tipos}})
        mats, normas, normas_gov, vetos = est["materias"], est["normas"], est["normas_gov"], est["vetos"]
        g = self.gov or {}
        ini_g = gv.periodo(self.uf)["inicio"] if self.gov else None
        tipos_lei = set(g.get("tipos_lei") or [])
        cfg = est["cfg"]
        fases = [("materias", f"{base_m}?tipo__in={','.join(str(t) for t in cfg['tipos'])}&data_apresentacao__gte={cfg['desde']}",
                  lambda x: mats.__setitem__(str(x["id"]), self._materia_curta(x))),
                 ("normas", f"/api/norma/normajuridica/?data__gte={INICIO[:4]}-01-01",
                  lambda n: self._norma_curta(n, normas, normas_gov, tipos_lei, ini_g))]
        if self.tipos_veto:
            fases.append(("vetos", f"{base_m}?tipo__in={','.join(str(t) for t in self.tipos_veto)}"
                                   f"&data_apresentacao__gte={INICIO[:4]}-01-01",
                          lambda x: vetos.__setitem__(str(x["id"]), self._veto_curto(x))))
        nomes = [f[0] for f in fases]
        try:
            while c["fase"] in nomes and self.tem_tempo(1):
                nome, consulta, guarda = fases[nomes.index(c["fase"])]
                d = self.api(f"{consulta}&page={c['pag']}&page_size={LOTE}")
                for x in d.get("results") or []:
                    guarda(x)
                if (d.get("pagination") or {}).get("next_page"):
                    c["pag"] += 1
                else:
                    i = nomes.index(nome) + 1
                    c["fase"], c["pag"] = (nomes[i] if i < len(nomes) else "situacoes"), 1
                self.rede.guardar(est, "estado.json")
            if c["fase"] == "situacoes":
                # autoria (quem é o autor principal), só quando há mais de um autor
                faltam = sorted((k for k, v in mats.items() if len(v["au"]) > 1 and v.get("aut") is None), key=int)
                for i in range(0, len(faltam), LOTE):
                    if not self.tem_tempo(2):
                        break
                    lote = faltam[i:i + LOTE]
                    aut: dict[str, dict] = {k: {} for k in lote}
                    for a in self.todos(f"/api/materia/autoria/?materia__in={','.join(lote)}"):
                        if str(a["materia"]) in aut:
                            aut[str(a["materia"])][str(a["autor"])] = [bool(a.get("primeiro_autor")), a["id"]]
                    for k in lote:
                        mats[k]["aut"] = aut[k]
                    self.rede.guardar(est, "estado.json")
                # situação de hoje (a última tramitação), 100 por pedido
                faltam = sorted((k for k, v in mats.items() if v.get("st") is None), key=int)
                for i in range(0, len(faltam), LOTE):
                    if not self.tem_tempo(1):
                        break
                    lote = faltam[i:i + LOTE]
                    sits = {str(t["materia"]): self._situacao_tram(t)
                            for t in self.todos(f"/api/materia/materiaemtramitacao/?materia__in={','.join(lote)}")}
                    for k in lote:
                        mats[k]["st"] = sits.get(k) or [None, None, None]
                    self.rede.guardar(est, "estado.json")
                if all(v.get("st") is not None for v in mats.values()) and \
                        not any(len(v["au"]) > 1 and v.get("aut") is None for v in mats.values()):
                    est["ultimo"] = c["inicio"]
                    est["cfg_gov"] = {"desde": ini_g, "tipos": sorted(tipos_lei)} if tipos_lei else None
                    est.pop("carga", None)
                    self.carga = False
        except SemTempo:
            pass
        self.rede.guardar(est, "estado.json")
        sem_st = sum(1 for v in mats.values() if v.get("st") is None)
        log(f"  {self.uf}: primeira carga " + ("concluída" if not self.carga else f"em andamento (etapa \"{c['fase']}\", "
            f"página {c['pag']})") + f": {len(mats)} propostas ({sem_st} sem situação), {len(normas)} normas, {len(vetos)} vetos")
        return est

    def materias(self) -> dict:
        """As matérias (propostas dos deputados e do governo), as normas e os vetos, guardados em estado.json e atualizados
        com poucos pedidos: o que mudou (data_ultima_atualizacao), o que tramitou (data_tramitacao), um lote em rodízio
        e uma página da lista completa por rodada. Com o cache vazio, a primeira carga (_primeira_carga)."""
        est = self.rede.estado("estado.json", {}) or {}
        if est.get("carga") or not est.get("materias") or not est.get("ultimo"):
            return self._primeira_carga(est)
        mats: dict[str, dict] = est.get("materias") or {}
        normas: dict[str, dict] = est.get("normas") or {}
        vetos: dict[str, dict] = est.get("vetos") or {}
        agora = _agora_iso()
        ultimo = est.get("ultimo")
        desde = self._desde()
        tipos = sorted(self._tipos_lista())
        lista_t = ",".join(str(t) for t in tipos)
        base_m = "/api/materia/materialegislativa/"
        mudaram: set[str] = set()

        def guardar_mat(x: dict) -> None:
            k = str(x["id"])
            v = self._materia_curta(x)
            antigo = mats.get(k)
            if not antigo or antigo.get("u") != v["u"]:
                mudaram.add(k)
            else:
                v["aut"], v["st"] = antigo.get("aut"), antigo.get("st")
            mats[k] = v

        # complementos (uma vez): tipos novos (ex.: medidas provisórias do governo) ou um começo mais cedo
        cfg = est.get("cfg") or {"desde": INICIO, "tipos": sorted(self.tipos)}
        novos_t = [t for t in tipos if t not in cfg["tipos"]]
        if novos_t:
            for x in self.todos(f"{base_m}?tipo__in={','.join(str(t) for t in novos_t)}&data_apresentacao__gte={desde}"):
                guardar_mat(x)
        velhos_t = [t for t in tipos if t in cfg["tipos"]]
        if desde < cfg["desde"] and velhos_t:
            for x in self.todos(f"{base_m}?tipo__in={','.join(str(t) for t in velhos_t)}&data_apresentacao__gte={desde}"
                                f"&data_apresentacao__lt={cfg['desde']}"):
                guardar_mat(x)
        for x in self.todos(f"{base_m}?tipo__in={lista_t}&data_apresentacao__gte={desde}"
                            f"&data_ultima_atualizacao__gte={_menos_dias(ultimo, 2)}"):
            guardar_mat(x)
        est["cfg"] = {"desde": desde, "tipos": tipos}
        # o que tramitou desde a última rodada (a tramitação nova nem sempre muda a data de atualização da matéria)
        tramitaram: set[str] = set()
        for t in self.todos(f"/api/materia/tramitacao/?data_tramitacao__gte={_menos_dias(ultimo, 2)}"):
            if str(t.get("materia")) in mats:
                tramitaram.add(str(t["materia"]))
        # e um lote em rodízio (a situação de todas é conferida de novo de tempos em tempos)
        chaves = sorted(mats, key=int)
        giro = int(est.get("giro") or 0) % max(1, len(chaves))
        rodizio = set(chaves[giro:giro + GIRO_LOTES * LOTE]) if self.tem_tempo(12) else set()
        est["giro"] = (giro + len(rodizio)) % max(1, len(chaves)) if rodizio else giro
        rever = {k for k, v in mats.items() if k in mudaram or k in tramitaram or k in rodizio or v.get("st") is None}
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
            v["st"] = self._situacao_tram(t)
        for k in rever:  # sem tramitação nenhuma
            if mats[k].get("st") is None:
                mats[k]["st"] = [None, None, None]
        # normas: uma consulta (o que mudou) serve às propostas ("virou lei") e à conta de leis do governador
        g = self.gov or {}
        ini_g = gv.periodo(self.uf)["inicio"] if self.gov else None
        tipos_lei = set(g.get("tipos_lei") or [])
        normas_gov: dict[str, dict] = est.get("normas_gov") or {}
        cfg_g = {"desde": ini_g, "tipos": sorted(tipos_lei)}

        def guardar_norma(n: dict) -> None:
            self._norma_curta(n, normas, normas_gov, tipos_lei, ini_g)

        if tipos_lei and est.get("cfg_gov") != cfg_g:  # a conta do governador começou (ou mudou): leis do período, uma vez
            normas_gov = {}
            for n in self.todos(f"/api/norma/normajuridica/?tipo__in={','.join(str(t) for t in sorted(tipos_lei))}"
                                f"&data__gte={ini_g}"):
                guardar_norma(n)
        for n in self.todos(f"/api/norma/normajuridica/?data__gte={INICIO[:4]}-01-01"
                            f"&data_ultima_atualizacao__gte={_menos_dias(ultimo, 2)}"):
            guardar_norma(n)
        est["cfg_gov"] = cfg_g if tipos_lei else None
        # vetos do governador (matérias do tipo veto), com os autores (o governo anterior fica de fora na conta)
        if self.tipos_veto:
            tv = ",".join(str(t) for t in self.tipos_veto)
            sem_autores = any("au" not in v for v in vetos.values())
            filtro_v = "" if sem_autores or not vetos else f"&data_ultima_atualizacao__gte={_menos_dias(ultimo, 2)}"
            for x in self.todos(f"{base_m}?tipo__in={tv}&data_apresentacao__gte={INICIO[:4]}-01-01{filtro_v}"):
                vetos[str(x["id"])] = self._veto_curto(x)
        est.update({"materias": mats, "normas": normas, "normas_gov": normas_gov, "vetos": vetos, "ultimo": agora})
        self.rede.guardar(est, "estado.json")
        # uma página da lista completa por rodada: no fim da volta, o que não apareceu é conferido uma a uma (apagada?)
        self._varrer(est, mats, lista_t, desde, guardar_mat)
        self.rede.guardar(est, "estado.json")
        log(f"  {self.uf}: {len(mats)} propostas no cache ({len(mudaram)} mudaram, {len(tramitaram)} tramitaram, "
            f"{len(rever)} conferidas), {len(normas)} normas, {len(normas_gov)} leis do governo, {len(vetos)} vetos")
        return est

    def _varrer(self, est: dict, mats: dict, lista_t: str, desde: str, guardar_mat) -> None:
        v = est.get("varredura") or {"pag": 1, "vistos": [], "inicio": hoje()}
        conferir = [k for k in est.get("conferir") or [] if k in mats]
        while conferir and self.tem_tempo(2):
            k = conferir.pop(0)
            try:
                guardar_mat(self.api(f"/api/materia/materialegislativa/{k}/"))
            except RuntimeError as e:
                if re.search(r"HTTP Error (404|410)\b", str(e)):
                    mats.pop(k, None)
                    log(f"  {self.uf}: a matéria {k} foi apagada no SAPL e saiu do cache")
                else:
                    conferir.append(k)
                    break
        if not conferir and self.tem_tempo(3):
            d = self.api(f"/api/materia/materialegislativa/?tipo__in={lista_t}&data_apresentacao__gte={desde}"
                         f"&page={v['pag']}&page_size={LOTE}")
            vistos = set(v["vistos"])
            for x in d.get("results") or []:
                guardar_mat(x)
                vistos.add(str(x["id"]))
            if (d.get("pagination") or {}).get("next_page"):
                v = {"pag": v["pag"] + 1, "vistos": sorted(vistos, key=int), "inicio": v["inicio"]}
            else:
                # fim da volta: as que não apareceram (e não mudaram desde o começo dela) são conferidas uma a uma
                conferir = [k for k, m in mats.items() if k not in vistos and (m.get("d") or "9999") >= desde
                            and (m.get("u") or "")[:10] < v["inicio"]]
                v = {"pag": 1, "vistos": [], "inicio": hoje()}
        est["varredura"], est["conferir"] = v, conferir

    def tipos_norma(self) -> dict[int, str | None]:
        return {t["id"]: nome_norma(t.get("descricao")) for t in self.todos("/api/norma/tiponormajuridica/", "tiponorma", 24 * 30)}

    # ------------------------------------------------------------ situação
    def ligar_vetos(self, est: dict, tipos: dict[int, str] | None = None) -> dict[str, dict]:
        """{id da proposta: {"total": bool, "d": data}} a partir das matérias do tipo veto."""
        mats = est["materias"]
        tipos = tipos or self.tipos
        indice = {}
        for k, v in mats.items():
            indice.setdefault((tipos.get(v["t"]), str(v["n"]), str(v["a"])), k)
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
    def _pendente(self, etapa: str) -> dict:
        log(f"  {self.uf}: {self.rede.pedidos} pedidos ao site oficial em {time.time() - self.t0:.0f} s; em andamento "
            f"({etapa}); os arquivos publicados de antes continuam")
        return _carga.pendente(self.info["sigla"], etapa, self.rede.pedidos)

    def coletar(self) -> dict:
        self.t0 = time.time()
        est0 = self.rede.estado("estado.json", {}) or {}
        if est0.get("carga") or not est0.get("materias") or not est0.get("ultimo"):
            self.orcamento = max(ORCAMENTO_S, _carga.segundos(ORCAMENTO_CARGA_S))  # primeira carga: a rodada toda
        try:
            return self._coletar()
        except SemTempo:  # o fim da rodada chegou no meio: o cache guarda o que foi lido; nada pela metade em dados/
            return self._pendente("o tempo da rodada acabou")

    def _coletar(self) -> dict:
        pessoas, leg = self.pessoas()
        est = self.est = self.materias()
        if self.carga:
            c = est.get("carga") or {}
            return self._pendente(f"primeira carga: {c.get('fase')}, página {c.get('pag')}")
        autores = self.autores({int(p["id"]) for p in pessoas})
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
        # "outros documentos": as contagens que faltam e, das guardadas, as mais antigas, aos poucos
        cod = [autores.get(int(p["id"])) for p in pessoas if autores.get(int(p["id"]))]
        idades = {a: self._idade_h(f"outros/{a}.json") for a in cod}
        velhas = sorted((i, a) for a, i in idades.items() if i is not None and i > OUTROS_DIAS * 24)
        self._outros_reler = {a for a, i in idades.items() if i is None} | {a for _, a in velhas[-OUTROS_POR_RODADA:]}
        membros, extras, listas = [], {}, []
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
                if not tipo or (v.get("d") or "9999") < INICIO:  # só desde o começo da legislatura (o cache vai mais longe)
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
                prop = regional.proposta(f"{self.prefixo}:{k}", sigla, tipo, v.get("d"), re.sub(r"\s+", " ", v.get("e") or ""), (v.get("st") or [None])[0],
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
        # fichas e contagens que ainda não estão no cache (primeira carga sem tempo para elas): nada é gravado ainda
        sem_outros = [a for a in cod if self._idade_h(f"outros/{a}.json") is None]
        if self.sem_ficha or len(sem_outros) > OUTROS_POR_RODADA:
            log(f"  {self.uf}: faltam {len(self.sem_ficha)} fichas de deputados e {len(sem_outros)} contagens de outros "
                "documentos; os arquivos de antes ficam até a próxima rodada")
            return self._pendente("fichas e contagens dos deputados")
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
        r = gravar(self.uf, self.info, membros, extras, cobertura, self.fonte_lista(leg), self.notas)
        if self.gov:
            try:
                self.governo(est, norma_de, nomes_norma)
            except Exception as e:  # o perfil do governador não derruba a lista da Assembleia: fica o arquivo da última vez
                log(f"  {self.uf}: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
        log(f"  {self.uf}: {self.rede.pedidos} pedidos ao site oficial em {time.time() - self.t0:.0f} s "
            f"(intervalo entre pedidos: {self.rede.atraso(self.base + '/api/'):.0f} s)")
        return r

    # ------------------------------------------------------------ governo do estado (dados/pessoas/gov-<UF>.json)
    def governo(self, est: dict, norma_de: dict, nomes_norma: dict) -> dict:
        g, per = self.gov, gv.periodo(self.uf)
        ini = per["inicio"]
        # 1. projetos do Executivo no período: já estão nas matérias guardadas (sem pedido a mais)
        autores_g = set(g["autores"])
        mats = {k: v for k, v in est["materias"].items()
                if v["t"] in g["tipos"] and set(v["au"]) & autores_g and (v.get("d") or "") >= ini}
        vetos_de = self.ligar_vetos({"materias": mats, "vetos": est["vetos"]}, {**self.tipos, **g["tipos"]})
        lista = []
        for k, v in mats.items():
            v = dict(v, st=v.get("st") or [None, None, None])
            s = self.situacao(k, v, norma_de.get(k), vetos_de.get(k), nomes_norma)
            prop = regional.proposta(f"{self.prefixo}:{k}", f"{self.sigla_tipo(v['t'])} {v['n']}/{v['a']}", g["tipos"][v["t"]],
                                     v.get("d"), re.sub(r"\s+", " ", v.get("e") or ""), (v.get("st") or [None])[0], f"{self.base}/materia/{k}", papel="autor",
                                     status=s["status"], data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
        autor = g["autores"][0]
        fonte_prop = fonte(self.veiculo, "Matérias de autoria do Poder Executivo (SAPL)",
                           f"{self.base}/materia/pesquisar-materia?autoria__autor={autor}")
        # 2. leis ordinárias e complementares com data no período (guardadas em materias(), normas_gov)
        fontes, nota, nota_en = [], [], []
        n_leis = promulgadas = None
        if g.get("tipos_lei"):
            normas = [n for n in (est.get("normas_gov") or {}).values() if n.get("tipo") in g["tipos_lei"] and (n.get("data") or "") >= ini]
            classif = g["classificar"](self, normas) if g.get("classificar") else [g["promulgada"](n) for n in normas]
            quem = collections.Counter(classif)
            n_leis, promulgadas = quem[False], quem[True]
            crit, crit_en = g["criterio_leis"]
            pt = (f"Leis: das {len(normas)} leis ordinárias e complementares com data a partir de {gv.data_pt(ini)} registradas no "
                  f"SAPL da {self.info['sigla']}, contam como sancionadas (pelo governador ou por quem estava no exercício do "
                  f"cargo) as {n_leis} {crit}.")
            en = (f"Laws: of the {len(normas)} ordinary and complementary laws dated from {gv.data_en(ini)} on in the "
                  f"{self.info['sigla']} SAPL system, the {n_leis} {crit_en} count as signed (by the governor or by whoever was "
                  f"acting as governor).")
            fora = ([f"{quem[True]} promulgadas pelo presidente da Assembleia (quando o governador não sanciona no prazo ou "
                     f"quando o veto é derrubado)"] if quem[True] else []) + ([f"{quem[None]} sem essa informação no SAPL"] if quem[None] else [])
            fora_en = ([f"{quem[True]} promulgated by the Assembly's president (when the governor does not sign in time or a "
                        f"veto is overridden)"] if quem[True] else []) + ([f"{quem[None]} without that information in SAPL"] if quem[None] else [])
            if fora:
                pt += " Ficam de fora " + " e ".join(fora) + "."
                en += " Left out: " + " and ".join(fora_en) + "."
            nota.append(pt)
            nota_en.append(en)
            fontes.append(fonte(self.veiculo, "Normas jurídicas: leis ordinárias e complementares (SAPL)", f"{self.base}/norma/pesquisar"))
        # 3. vetos: matérias do tipo veto recebidas no período (só o governador veta)
        n_vetos = totais = parciais = None
        if self.tipos_veto:
            fora_g = set(g.get("autores_fora") or [])
            vts = [x for x in est["vetos"].values() if (x.get("d") or "") >= ini and not set(x.get("au") or []) & fora_g]
            tipo_de = []
            for x in vts:
                t = self.tipos_veto.get(x["t"])
                if t is None:
                    e = sem_acento((x.get("e") or "").lower())
                    t = "total" if re.search(r"veto total|totalmente|integral", e) else "parcial" if re.search(r"parcial", e) else None
                tipo_de.append(t)
            n_vetos, totais, parciais = len(vts), tipo_de.count("total"), tipo_de.count("parcial")
            if totais + parciais != n_vetos:
                totais = parciais = None
            nota.append(f"Vetos: as mensagens de veto do governador (totais e parciais) recebidas pela Assembleia desde "
                        f"{gv.data_pt(ini)}, registradas no SAPL como matérias do tipo veto.")
            nota_en.append(f"Vetoes: the governor's veto messages (full and partial) received by the Assembly since "
                           f"{gv.data_en(ini)}, recorded in SAPL as veto items.")
            fontes.append(fonte(self.veiculo, "Matérias do tipo veto (SAPL)",
                                f"{self.base}/materia/pesquisar-materia?tipo={next(iter(self.tipos_veto))}"))
        ex = gv.bloco_executivo(per, n_leis, n_vetos, fontes, " ".join(nota), " ".join(nota_en), totais, parciais, promulgadas)
        tipos_txt = g.get("tipos_txt") or (None, None)
        esc, esc_en = gv.escopo(per, "Assembleia Legislativa", "state legislature", *([tipos_txt[0], tipos_txt[1]] if tipos_txt[0] else []))
        return gv.gravar_gov(self.uf, per, lista, esc, esc_en, fonte_prop, ex, fontes, g.get("nota_prop"))

    def fonte_lista(self, leg: dict) -> dict:
        if self.lista_oficial:
            titulo, url = self.lista_oficial
            return fonte(self.veiculo, titulo, url)
        return fonte(self.veiculo, f"Deputados em exercício na {leg.get('numero')}ª legislatura (SAPL, dados abertos)",
                     f"{self.base}/parlamentar/")

    _siglas: dict | None = None

    def sigla_tipo(self, t: int) -> str:
        if self._siglas is None:
            self._siglas = {x["id"]: x["sigla"].strip() for x in self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 30)}
        return self._siglas.get(t) or self.tipos.get(t) or "?"

    def outros(self, autor: int | None, nome: str) -> dict | None:
        """Quantos documentos que não são projetos (requerimentos, indicações, moções, emendas...) a pessoa apresentou."""
        if not autor:
            return None
        if not hasattr(self, "_outros_tipos"):
            todos = self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 30)
            veto = set(self.tipos_veto)
            self._outros_tipos = ",".join(str(x["id"]) for x in todos if x["id"] not in self.tipos and x["id"] not in veto)
        cache = f"outros/{autor}.json"
        reler = autor in getattr(self, "_outros_reler", set())
        if reler and not self.tem_tempo(3):
            if self._idade_h(cache) is None:
                return None
            reler = False
        d = self.api(f"/api/materia/materialegislativa/?autores={autor}&tipo__in={self._outros_tipos}&data_apresentacao__gte={INICIO}&page_size=1",
                     cache, 0 if reler else None)
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
