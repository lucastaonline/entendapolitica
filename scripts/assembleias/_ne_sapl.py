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


def _mais_dias(iso: str, dias: int) -> str:
    return _menos_dias(iso, -dias)


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
                 gov: dict | None = None, gastos=None, votacoes: bool = False):
        """tipos = {id do tipo de matéria no SAPL: PL|PLP|PEC|PDL|PRC}; tipos_veto = {id do tipo: "total"|"parcial"|None
        (None: lê na ementa)}; regras = [(expressão sem acento, status, texto pt ou None, texto en ou None)] para a situação
        da última tramitação; em_exercicio(coletor, parlamentares_da_legislatura) -> {id SAPL: dados extras} troca a regra
        padrão (ativo na legislatura atual); tse_manual = {id SAPL: SQ do TSE ou "-"} conferido à mão; lista_oficial =
        (título, endereço) da fonte da lista quando ela não vem do SAPL; gov = o que entra no perfil do governador:
        {"autores": [ids de autor do Executivo], "tipos": {id do tipo: PL|PLP|PEC|PDL|PRC|MPV}, "tipos_lei": [ids dos tipos
        de norma lei ordinária e complementar] ou None (sem contagem de leis), "promulgada": função(norma) -> True (a
        Assembleia promulgou), False (o governador sancionou) ou None (sem a informação), "criterio_leis": (pt, en) que
        completa "contam como sancionadas as N ...", "autores_fora": [ids de autor cujos vetos não entram (governo
        anterior)], "nota_prop": (pt, en) ou None, "tipos_txt": (pt, en) ou None}; gastos(coletor, membros) -> {id da
        pessoa: bloco "gastos"} (fonte própria da Casa, fora do SAPL; ver _votos_gastos.py) ou None enquanto a primeira
        carga dos gastos não termina (os perfis ficam com o bloco de antes; uma exceção também mantém os de antes);
        votacoes = True: votações nominais do Plenário registradas no SAPL (ver votacoes())."""
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
        self.gastos = gastos
        self.com_votacoes = votacoes
        self.votos_info: dict | None = None
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
        pid_de_sapl: dict[int, str] = {}
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
            pid_de_sapl[int(p["id"])] = pid
        # fichas e contagens que ainda não estão no cache (primeira carga sem tempo para elas): nada é gravado ainda
        sem_outros = [a for a in cod if self._idade_h(f"outros/{a}.json") is None]
        if self.sem_ficha or len(sem_outros) > OUTROS_POR_RODADA:
            log(f"  {self.uf}: faltam {len(self.sem_ficha)} fichas de deputados e {len(sem_outros)} contagens de outros "
                "documentos; os arquivos de antes ficam até a próxima rodada")
            return self._pendente("fichas e contagens dos deputados")
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        com_gastos = False
        if self.gastos:
            from . import _votos_gastos as VG
            try:
                g = self.gastos(self, membros)
            except SemTempo:
                g = None
                log(f"  {self.uf}: gastos: o tempo da rodada acabou; a leitura continua na próxima")
            except Exception as e:  # o site dos gastos fora do ar não derruba a Casa: ficam os blocos de antes
                g = None
                log(f"  {self.uf}: ATENÇÃO: gastos não atualizados ({type(e).__name__}: {e}); ficam os de antes")
            com_gastos = VG.aplicar(extras, g, "gastos")
        com_votos = False
        notas = list(self.notas)
        if self.com_votacoes:
            from . import _votos_gastos as VG
            try:
                vb = self.votacoes(pid_de_sapl)
            except SemTempo:
                vb = None
            except Exception as e:  # o SAPL das votações com erro não derruba a Casa: ficam os blocos de antes
                vb = None
                log(f"  {self.uf}: ATENÇÃO: votações não atualizadas ({type(e).__name__}: {e}); ficam as de antes")
            com_votos = VG.aplicar(extras, vb, "votacoes")
            if com_votos:
                notas.append(self.nota_votacoes())
        cobertura = {"lista": True, "propostas": True, "votacoes": com_votos, "gastos": com_gastos}
        r = gravar(self.uf, self.info, membros, extras, cobertura, self.fonte_lista(leg), notas)
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

    # ------------------------------------------------------------ votações nominais (painel do Plenário registrado no SAPL)
    # voto como o SAPL escreve -> como o site guarda (js/traducoes.js, D.voto); o mesmo de _nco_sapl.Sapl.VOTO
    VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "nao votou": "NR", "obstrucao": "Obstrução",
            "presidente": "PS", "presidencia": "PS", "presidente da sessao": "PS", "ausente": "NCOM"}

    def votacoes(self, pid_de_sapl: dict[int, str]) -> dict | None:
        """{id da pessoa: bloco "votacoes"} (formato "lista" de _votos_gastos.py) ou None enquanto a primeira carga não
        termina (os perfis ficam com o bloco de antes). Lê os votos registrados no SAPL (/api/sessao/votoparlamentar/, pela
        data do registro: na primeira vez desde a posse; depois, desde a última leitura menos 2 dias), o registro de cada
        votação (placar, resultado, matéria: /api/sessao/registrovotacao/?id__in=), a ordem do dia ou o expediente de cada
        uma (a sessão e a data) e a ementa das matérias votadas que não estão no cache das propostas. Com 60 s entre pedidos
        (Interlegis), a primeira carga leva de 30 a 60 pedidos (uma a três rodadas, guardando o progresso em votos.json);
        depois, 1 a 3 pedidos por dia. O SAPL que ignora o filtro id__in (o da ALPB devolve a lista inteira) não é lido um
        registro por pedido: cada voto da lista já traz a ordem do dia (ou o expediente), a data e um texto com a sessão, o
        resultado e a matéria ("... Veto nº 366 de 2025 em 28ª Sessão Ordinária da 4ª Sessão Legislativa da 20ª Legislatura -
        Votação: Mantida - Matéria: Veto nº 366 de 2025 - ..."); a matéria é achada pelo tipo, número e ano no cache das
        propostas e dos vetos, e a sessão pela lista de sessões (/api/sessao/sessaoplenaria/, ligada pelo nome). Só o que não
        se acha assim vai ao registro, um por pedido. Na ALPB: ~52 pedidos na primeira carga (2 a 3 rodadas)."""
        from . import _votos_gastos as VG
        from mandatos import mes_ano
        vt = self.rede.estado("votos.json", {}) or {}
        if vt.get("inicio") != INICIO:
            vt = {"inicio": INICIO}
        votos: dict = vt.setdefault("votos", {})   # id da votação -> {id do parlamentar: voto}
        regs: dict = vt.setdefault("regs", {})     # id da votação -> registro resumido
        ords: dict = vt.setdefault("ords", {})     # "o<id>" (ordem do dia) / "e<id>" (expediente) -> {"s": sessão, "d": data}
        mats: dict = vt.setdefault("mats", {})     # matéria votada fora do cache das propostas -> {"t", "n", "a", "e"}
        vinfo: dict = vt.setdefault("vinfo", {})   # id da votação -> o que o voto traz: {"o", "x", "d", "s" (texto)}
        if vt.get("sem_in") and not vt.get("cursor") and any(k not in vinfo and k not in regs for k in votos):
            # cache de antes desta regra: relê a lista dos votos uma vez, para guardar a sessão e a matéria de cada votação
            vt["cursor"] = {"desde": INICIO, "pag": 1, "ate": hoje()}

        def guardar() -> None:
            self.rede.guardar(vt, "votos.json")

        def pedir() -> None:
            if not self.tem_tempo():
                raise SemTempo("votações: acabou o tempo desta rodada")

        try:
            cur = vt.get("cursor") or {"desde": _menos_dias(vt["feito"], 2) if vt.get("feito") else INICIO, "pag": 1, "ate": hoje()}
            vt["cursor"] = cur
            while True:
                pedir()
                d = self.api(f"/api/sessao/votoparlamentar/?data_hora__gte={cur['desde']}&o=data_hora&page={cur['pag']}"
                             f"&page_size={LOTE}", None, None)
                for v in d.get("results") or []:
                    if v.get("votacao") is not None and v.get("parlamentar") is not None:
                        vid = str(v["votacao"])
                        votos.setdefault(vid, {})[str(v["parlamentar"])] = v.get("voto")
                        if vid not in vinfo:
                            s = re.sub(r"\s+", " ", v.get("__str__") or "").strip()
                            vinfo[vid] = {"o": v.get("ordem"), "x": v.get("expediente"),
                                          "d": (v.get("data_hora") or "")[:10] or None,
                                          "s": re.sub(r" - Parlamentar: .*$", "", s)[:400]}
                if not (d.get("pagination") or {}).get("next_page"):
                    break
                cur["pag"] += 1
                guardar()
            vt["feito"] = cur["ate"]
            vt.pop("cursor", None)
            guardar()

            def por_ids(caminho: str, ids: list[str]) -> list[dict] | None:
                """Os registros de `ids` pelo filtro id__in, ou None se este SAPL ignora o filtro (o da ALPB devolve a lista
                inteira): aí vale um registro por pedido (vt["sem_in"])."""
                d = self.api(f"{caminho}?id__in={','.join(ids)}&page=1&page_size={LOTE}", None, None)
                res = d.get("results") or []
                total = (d.get("pagination") or {}).get("total_entries")
                if (total is not None and total > len(ids)) or any(str(x.get("id")) not in ids for x in res):
                    return None
                return res

            def um(caminho: str, i: str) -> dict | None:
                """Um registro pelo endereço dele (None se foi apagado: 404)."""
                try:
                    return self.api(f"{caminho}{i}/", None, None)
                except RuntimeError as e:
                    if re.search(r"HTTP Error 404\b", str(e)):
                        return None
                    raise

            def lido(r: dict) -> dict:
                s = re.sub(r"\s+", " ", r.get("__str__") or "")
                ses = re.search(r" em (\d+\S* .*?Legislatura)\b", s)
                return {"m": r.get("materia"), "o": r.get("ordem"), "x": r.get("expediente"),
                        "r": r.get("tipo_resultado_votacao"), "d": (r.get("data_hora") or "")[:10] or None,
                        "sim": r.get("numero_votos_sim"), "nao": r.get("numero_votos_nao"),
                        "abst": r.get("numero_abstencoes"), "s": s[:300],
                        "ses": ses.group(1) if ses else None,
                        "obs": (r.get("observacao") or "").strip()[:300] or None}

            indice_m: dict | None = None

            def pelo_texto(vid: str) -> dict | None:
                """O registro da votação montado com o que o voto traz (ver a docstring), ou None se a matéria ou a sessão
                não aparecem no texto ou se a matéria não está no cache (aí vale o registro, um pedido)."""
                nonlocal indice_m
                vi = vinfo.get(vid)
                if not vi or not (vi.get("o") or vi.get("x")):
                    return None
                s = vi.get("s") or ""
                ses = re.search(r" em (\d+\S* .*?Legislatura)\b", s)
                res = re.search(r" - Votação: (.*?)(?: - Matéria: |$)", s)
                mat = re.search(r" - Matéria: (.+?) nº ?(\d+) de (\d{4})", s)
                if not (ses and mat):
                    return None
                if indice_m is None:
                    por_desc = {}
                    for t in self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", 24 * 30):
                        por_desc.setdefault(sem_acento((t.get("descricao") or "").lower()).strip(), set()).add(t["id"])
                    indice_m = {"desc": por_desc, "m": {}}
                    for fonte_m in ((self.est or {}).get("materias") or {}, (self.est or {}).get("vetos") or {}, mats):
                        for mid, x in fonte_m.items():
                            if x and x.get("t") and x.get("n") and x.get("a"):
                                indice_m["m"].setdefault((int(x["t"]), int(x["n"]), int(x["a"])), set()).add(str(mid))
                tipos_m = indice_m["desc"].get(sem_acento(mat.group(1).lower()).strip()) or set()
                achou = set().union(*[indice_m["m"].get((t, int(mat.group(2)), int(mat.group(3))), set()) for t in tipos_m]) if tipos_m else set()
                if len(achou) != 1:
                    return None
                return {"m": int(next(iter(achou))), "o": vi.get("o"), "x": vi.get("x"), "r": None,
                        "rt": res.group(1).strip() if res else None, "d": vi.get("d"), "sim": None, "nao": None,
                        "abst": None, "s": s[:300], "ses": ses.group(1), "obs": None}

            faltam = sorted((k for k in votos if k not in regs), key=int)
            while faltam:
                if vt.get("sem_in"):
                    vid = faltam.pop(0)
                    r = pelo_texto(vid)
                    if r is None:
                        pedir()
                        rr = um("/api/sessao/registrovotacao/", vid)
                        r = lido(rr) if rr else {}
                    regs[vid] = r
                    if not faltam or len(regs) % 20 == 0:
                        guardar()
                    continue
                pedir()
                lote, faltam = faltam[:LOTE], faltam[LOTE:]
                rs = por_ids("/api/sessao/registrovotacao/", lote)
                if rs is None:
                    vt["sem_in"] = True
                    log(f"  {self.uf}: votações: o SAPL ignora o filtro id__in; a sessão e a matéria de cada votação vêm do "
                        "texto de cada voto (e, se faltar, do registro, um por pedido)")
                    faltam = lote + faltam
                else:
                    for r in rs:
                        regs[str(r["id"])] = lido(r)
                guardar()
            if vt.get("sem_in"):
                # sessão e data de cada votação pela lista de sessões (poucos pedidos), ligada pelo nome da sessão que o
                # registro da votação traz ("28ª Sessão Ordinária da 4ª Sessão Legislativa da 20ª Legislatura")
                sess: dict = vt.setdefault("sessoes", {})   # nome da sessão -> {"s": id, "d": data}
                sem_sessao = [r for r in regs.values() if r and (r.get("o") or r.get("x"))
                              and f"{'o' if r.get('o') else 'e'}{r.get('o') or r.get('x')}" not in ords]
                if sem_sessao and vt.get("sessoes_em") != hoje() and any(r.get("ses") and r["ses"] not in sess for r in sem_sessao):
                    pedir()
                    desde = _menos_dias(max((v.get("d") or INICIO for v in sess.values()), default=INICIO), 7) if sess else INICIO
                    for s in self.todos(f"/api/sessao/sessaoplenaria/?data_inicio__gte={desde}"):
                        sess[re.sub(r"\s+", " ", s.get("__str__") or "").strip()] = {"s": s.get("id"), "d": s.get("data_inicio")}
                    vt["sessoes_em"] = hoje()
                    guardar()
                for r in sem_sessao:
                    s = sess.get(r.get("ses"))
                    if s:
                        ords[f"{'o' if r.get('o') else 'e'}{r.get('o') or r.get('x')}"] = {"s": s["s"], "d": s["d"]}
                guardar()
            else:
                for pre, caminho in (("o", "/api/sessao/ordemdia/"), ("e", "/api/sessao/expedientemateria/")):
                    ids = sorted({str(r["o" if pre == "o" else "x"]) for r in regs.values() if r and r.get("o" if pre == "o" else "x")}
                                 - {k[1:] for k in ords if k[0] == pre}, key=int)
                    for i in range(0, len(ids), LOTE):
                        pedir()
                        for o in self.todos(f"{caminho}?id__in={','.join(ids[i:i + LOTE])}"):
                            ords[f"{pre}{o['id']}"] = {"s": o.get("sessao_plenaria"), "d": (o.get("data_ordem") or "")[:10] or None}
                        guardar()
            cache_m = (self.est or {}).get("materias") or {}
            vetos_c = (self.est or {}).get("vetos") or {}   # os vetos do governo também estão no cache (com tipo, número e ementa)
            sem_m = sorted({str(r["m"]) for r in regs.values() if r and r.get("m") and str(r["m"]) not in cache_m
                            and str(r["m"]) not in vetos_c and str(r["m"]) not in mats}, key=int)
            for i in range(0, len(sem_m), 1 if vt.get("sem_in") else LOTE):
                pedir()
                ms = ([x for x in [um("/api/materia/materialegislativa/", sem_m[i])] if x] if vt.get("sem_in")
                      else self.todos(f"/api/materia/materialegislativa/?id__in={','.join(sem_m[i:i + LOTE])}"))
                for m in ms:
                    mats[str(m["id"])] = {"t": m.get("tipo"), "n": m.get("numero"), "a": m.get("ano"),
                                          "e": re.sub(r"\s+", " ", m.get("ementa") or "").strip() or None}
                if vt.get("sem_in") and not ms:
                    mats[sem_m[i]] = {}
                guardar()
        except SemTempo:
            guardar()
            log(f"  {self.uf}: votações: primeira leitura em andamento ({len(votos)} votações com votos lidas até aqui); "
                "os perfis ficam com as votações de antes")
            return None
        resultados = {t["id"]: t.get("nome") for t in self.todos("/api/sessao/tiporesultadovotacao/", "tiporesultado", 24 * 30)}
        cache_m = (self.est or {}).get("materias") or {}
        vetos_c = (self.est or {}).get("vetos") or {}
        vetos_sim: list[tuple] = []   # (sim, não, resultado) de cada votação de veto
        por_pessoa: dict[str, list] = {}
        datas, divergentes, desconhecidos, sem_placar = [], 0, set(), 0
        for vid, vs in votos.items():
            r = regs.get(vid)
            if not r:
                continue
            o = ords.get(f"o{r['o']}") if r.get("o") else ords.get(f"e{r['x']}") if r.get("x") else None
            data = (o or {}).get("d") or r.get("d")
            if not data or data < INICIO:
                continue
            convertidos = {}
            for parl, voto in vs.items():
                v = self.VOTO.get(sem_acento((voto or "").lower()).strip())
                if v:
                    convertidos[int(parl)] = v
                else:
                    desconhecidos.add(voto)
            if not convertidos:
                continue
            pl = VG.placar(convertidos.values())
            if r.get("sim") is not None and (pl["Sim"], pl["Não"], pl["Abstenção"]) != (r.get("sim"), r.get("nao"), r.get("abst")):
                divergentes += 1
            sem_placar += r.get("sim") is None
            resultado = resultados.get(r.get("r")) or r.get("rt")
            datas.append(data)
            m = str(r.get("m") or "")
            info_m = cache_m.get(m) or vetos_c.get(m) or mats.get(m) or {}
            sigla = f"{self.sigla_tipo(info_m['t'])} {info_m['n']}/{info_m['a']}" if info_m.get("t") and info_m.get("n") else None
            if o and o.get("s") and r.get("o"):
                url = f"{self.base}/sessao/{o['s']}/votacao-nominal-transparencia/{r['o']}/{m}?&materia=ordem"
            elif o and o.get("s") and r.get("x"):
                url = f"{self.base}/sessao/{o['s']}/votacao-nominal-transparencia/{r['x']}/{m}?&materia=expediente"
            else:
                url = f"{self.base}/materia/{m}"
            desc = re.sub(r"\s+", " ", info_m.get("e") or "").strip() or r.get("obs") or None
            chave = f"{self.prefixo}-vot:{vid}"
            prop_id = f"{self.prefixo}:{m}" if m in cache_m else None
            if info_m.get("t") in (self.tipos_veto or {}):  # votação de veto: para dizer o que quer dizer o "sim"
                vetos_sim.append((pl["Sim"], pl["Não"], resultado))
            for parl, voto in convertidos.items():
                pid = pid_de_sapl.get(parl)
                if pid:
                    por_pessoa.setdefault(pid, []).append(VG.item_voto(chave, voto, data, sigla, desc, resultado,
                                                                       pl, url, prop_id))
        if desconhecidos:
            log(f"  {self.uf}: votações: votos com valor desconhecido (fora): {sorted(map(str, desconhecidos))}")
        sigla_casa = self.info["sigla"]
        extra = None
        if datas and min(datas) > _mais_dias(INICIO, 60):
            primeira = mes_ano(min(datas))
            extra = (f"O sistema da {sigla_casa} (SAPL) registra o voto de cada deputado a partir de {primeira[0]}; as votações "
                     "de antes não aparecem lá",
                     f"The {sigla_casa} system (SAPL) records each deputy's vote from {primeira[1]} on; earlier votes do not "
                     "appear there")
        if vetos_sim:
            # o que quer dizer cada voto nos vetos (como na RN e em SC), só quando o resultado registrado confirma
            v = VG.sentido_veto(vetos_sim, len(set(pid_de_sapl.values())))
            if v:
                extra = VG.junta(extra, v)
            else:
                log(f"  {self.uf}: votações: o resultado das {len(vetos_sim)} votações de veto não mostra sozinho o que quer "
                    "dizer o \"sim\" (sem a frase no escopo)")
        esc, esc_en = VG.escopo_votos(sigla_casa, extra=extra)
        fonte_v = fonte(self.veiculo, "Votações nominais do Plenário (SAPL, dados abertos)", f"{self.base}/sessao/pesquisar-sessao")
        blocos = {pid: VG.bloco_votacoes(l, esc, esc_en, fonte_v) for pid, l in por_pessoa.items()}
        n = len({x["id"] for l in por_pessoa.values() for x in l})
        self.votos_info = {"votacoes": n, "desde": min(datas) if datas else None, "divergentes": divergentes, "extra": extra}
        vt["info"] = self.votos_info
        guardar()
        log(f"  {self.uf}: votações: {n} votações nominais desde {INICIO} (a primeira em {min(datas) if datas else '—'}); votos de "
            f"{len(blocos)} deputados; {divergentes} com o placar do registro diferente da soma dos votos"
            + (f" ({sem_placar} montadas pelo texto dos votos, sem o placar do registro para conferir)" if sem_placar else ""))
        return blocos

    def nota_votacoes(self) -> tuple[str, str]:
        """Nota da Casa sobre as votações (o que entra e de onde; e, se for o caso, desde quando o SAPL registra os votos)."""
        s = self.info["sigla"]
        pt = (f"Votações: entram as votações nominais do Plenário (com o voto de cada deputado) desde 1º/2/2023, como estão "
              f"registradas no sistema da {s} (SAPL, dados abertos). As votações simbólicas não entram: nelas o voto de cada um "
              "não fica registrado.")
        en = (f"Votes: roll-call votes in the full Assembly (with each deputy's vote) since February 1, 2023 are included, as "
              f"recorded in the {s} system (SAPL, open data). Voice votes are not included: in them, each member's vote is not "
              "recorded.")
        info = self.votos_info or (self.rede.estado("votos.json", {}) or {}).get("info") or {}
        if info.get("extra"):
            pt, en = f"{pt} {info['extra'][0]}.", f"{en} {info['extra'][1]}."
        return pt, en

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
