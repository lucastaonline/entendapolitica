"""Coletor genérico das Câmaras Municipais que usam o SAPL 3.x do Interlegis (API REST pública em <endereço>/api/).

Uma cidade com SAPL só precisa de um arquivo pequeno (scripts/camaras/c<IBGE>.py):

    from ._sapl import Sapl

    def coletar():
        return Sapl("2408102", "RN", "https://sapl.natal.rn.leg.br", casa="Câmara Municipal de Natal",
                    casa_en="Natal City Council", sigla="CMN", site="https://www.cmnat.rn.gov.br", prefixo="cmnatal").coletar()

O que ele pega (tudo da API oficial; nada de sites de terceiros):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido de hoje,
   foto, titular ou suplente) + /api/parlamentares/mandato/ + /api/parlamentares/parlamentar/<id>/ (nome completo, sexo, e-mail);
2. propostas desde 1º/1/2025 (projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de
   resolução): /api/materia/materialegislativa/, autoria (/api/materia/autoria/: quem é o primeiro autor), situação = a da
   última tramitação (/api/materia/tramitacao/ + /api/materia/statustramitacao/), e a norma que a proposta virou
   (/api/norma/normajuridica/?materia=...: "virou lei");
3. votações nominais e gastos: o SAPL quase nunca tem (cobertura false).

Educado com o site: uma requisição por vez, pausa entre elas, páginas de 100, cache em .cache/camaras/<IBGE>/ e atualização
incremental das tramitações (só as que mudaram desde a última vez: filtro ultima_edicao__gte), com uma revisão completa
aos poucos (algumas centenas de propostas por dia) para pegar tramitações apagadas.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

import regional
from comum import CACHE, baixar, fonte, hoje, ler_json, log, salvar_json, sem_acento

from . import _base as B

LOTE = 100           # ids por requisição (materia__in=...) e tamanho da página (o SAPL não passa de 100)
REVISAR_DIAS = 30    # revisão completa de cada proposta a cada tantos dias...
REVISAR_LOTES = 3    # ...mas no máximo estes lotes de 100 por dia


def tipo_por_descricao(sigla: str | None, descricao: str | None) -> str | None:
    """Tipo de matéria do SAPL (cada Câmara cria os seus) -> tipo comum do site, pela descrição. None = não é proposta."""
    d = sem_acento((descricao or "").lower()).strip()
    if re.search(r"(projeto|proposta) de emenda (a |ao |a\b)?\s*(lei organica|loman|lom\b)|emenda (a|ao) lei organica", d):
        return "PELO"
    if re.search(r"substitutiv|anteprojeto|^emenda|veto|parecer|indicac|requerimento|mocao|oficio|mensagem|recurso|^processo|"
                 r"protocolo|relatorio|^ata|prestacao|consulta|^ato |^item|^resolucao$|^decreto|^lei", d):
        return None
    if re.search(r"projeto de lei complementar", d):
        return "PLP"
    if re.search(r"projeto de decreto legislativo", d):
        return "PDL"
    if re.search(r"projeto de resolucao", d):
        return "PRC"
    if re.search(r"^(projeto|proposta) de lei\b", d):
        return "PL"
    return None


class Sapl:
    def __init__(self, ibge: str, uf: str, base: str, casa: str, casa_en: str, sigla: str, site: str, prefixo: str,
                 tipos: dict[str, str | None] | None = None, regras: list | None = None, tse_manual: dict | None = None,
                 incluir: set | None = None, excluir: set | None = None, pausa: float = 0.5, notas: list | None = None,
                 primeiro_por_ordem: bool = True):
        """tipos = {sigla oficial do tipo: tipo comum ou None} para corrigir a escolha automática pela descrição;
        regras = [(expressão, status, chave de _base.TXT ou None)] próprias da Câmara (vêm antes das comuns);
        tse_manual = {id do parlamentar no SAPL: SQ do TSE ou "-"} conferidos à mão;
        incluir = ids do SAPL que estão no cargo mesmo sem "ativo"; excluir = {id: até quando (AAAA-MM-DD) ou None} para quem
        o SAPL marca como ativo mas está afastado (anote a fonte no arquivo da cidade);
        primeiro_por_ordem: quando a Câmara não marca o primeiro autor e há vários, vale o primeiro cadastrado."""
        self.ibge, self.uf, self.base = ibge, uf, base.rstrip("/")
        self.casa, self.casa_en, self.sigla, self.site, self.prefixo = casa, casa_en, sigla, site, prefixo
        self.tipos_fixos = tipos or {}
        self.regras = regras or []
        self.tse_manual = tse_manual or {}
        self.incluir = set(incluir or ())
        # excluir: {id: até quando (AAAA-MM-DD) ou None}; um conjunto vale "para sempre"
        self.excluir = dict(excluir) if isinstance(excluir, dict) else {i: None for i in (excluir or ())}
        self.pausa = pausa
        self.notas_casa = list(notas or [])
        self.primeiro_por_ordem = primeiro_por_ordem
        self.pasta = CACHE / "camaras" / ibge
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.n_req = 0

    # ------------------------------------------------------------ rede (uma por vez, com pausa e cache)
    def url(self, caminho: str, params: dict | None = None) -> str:
        q = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None}, safe=",")
        return f"{self.base}{caminho}" + (f"?{q}" if q else "")

    def get(self, caminho: str, params: dict | None = None, cache: str | None = None, idade_h: float | None = 20):
        arq = self.pasta / "http" / f"{cache}.json" if cache else None
        if arq and arq.exists() and (idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < idade_h):
            return json.loads(arq.read_text(encoding="utf-8"))
        bruto = baixar(self.url(caminho, params), tentativas=3, timeout=120, headers={"Accept": "application/json"})
        self.n_req += 1
        time.sleep(self.pausa)
        d = json.loads(bruto.decode("utf-8"))
        if arq:
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d

    def todos(self, caminho: str, params: dict | None = None, cache: str | None = None, idade_h: float | None = 20) -> list:
        """Todas as páginas de uma lista da API (100 por página)."""
        out, pagina = [], 1
        while True:
            p = dict(params or {}, page=pagina, page_size=LOTE)
            d = self.get(caminho, p, cache=f"{cache}-p{pagina}" if cache else None, idade_h=idade_h)
            if isinstance(d, list):  # algumas ações antigas não paginam
                return d
            out += d.get("results") or []
            pag = d.get("pagination") or {}
            if pagina >= (pag.get("total_pages") or 1):
                return out
            pagina += 1

    def total(self, caminho: str, params: dict | None = None) -> int:
        d = self.get(caminho, dict(params or {}, page_size=1))
        return ((d.get("pagination") or {}).get("total_entries")) or 0

    def por_lotes(self, caminho: str, campo: str, ids: list[int], extra: dict | None = None) -> list:
        """Busca por lotes de ids (campo__in=1,2,3). Se um id sumiu do SAPL (o servidor responde erro 500), divide o lote."""
        out = []
        for i in range(0, len(ids), LOTE):
            out += self._lote(caminho, campo, ids[i:i + LOTE], extra)
        return out

    def _lote(self, caminho, campo, lote, extra):
        try:
            return self.todos(caminho, dict(extra or {}, **{f"{campo}__in": ",".join(map(str, lote))}))
        except RuntimeError:
            if len(lote) == 1:
                log(f"  {self.sigla}: {campo}={lote[0]} não respondeu; fica sem")
                return []
            meio = len(lote) // 2
            return self._lote(caminho, campo, lote[:meio], extra) + self._lote(caminho, campo, lote[meio:], extra)

    # ------------------------------------------------------------ quem está no cargo
    def legislatura_atual(self) -> dict:
        legs = self.todos("/api/parlamentares/legislatura/", cache="legislaturas")
        h = hoje()
        atuais = [l for l in legs if (l.get("data_inicio") or "") <= h <= (l.get("data_fim") or "")]
        if not atuais:
            raise RuntimeError("o SAPL não tem a legislatura atual cadastrada")
        return max(atuais, key=lambda l: l["data_inicio"])

    def parlamentar(self, pid: int) -> dict:
        if not hasattr(self, "_ativos"):  # quase todos estão aqui (uma ou duas páginas); os outros vêm um por um
            self._ativos = {p["id"]: p for p in self.todos("/api/parlamentares/parlamentar/", {"ativo": "True"},
                                                           cache="parlamentares-ativos")}
        return self._ativos.get(pid) or self.get(f"/api/parlamentares/parlamentar/{pid}/", cache=f"parlamentar-{pid}")

    def membros(self) -> tuple[list[dict], dict, dict]:
        """(pessoas no cargo hoje, legislatura, {id SAPL: dados do SAPL})."""
        leg = self.legislatura_atual()
        L = leg["id"]
        try:
            vinc = self.todos(f"/api/parlamentares/legislatura/{L}/parlamentares/", cache=f"leg{L}-parlamentares", idade_h=6)
        except RuntimeError:
            vinc = []
        mandatos = self.todos("/api/parlamentares/mandato/", {"legislatura": L}, cache=f"leg{L}-mandatos", idade_h=6)
        por_id = {v["id"]: dict(v) for v in vinc}
        for m in mandatos:
            por_id.setdefault(m["parlamentar"], {"id": m["parlamentar"]})
        h = hoje()
        for pid, v in por_id.items():
            v["mandatos"] = [m for m in mandatos if m["parlamentar"] == pid]
            if "ativo" not in v or "partido" not in v:  # SAPL antigo, sem a ação .../parlamentares/
                d = self.parlamentar(pid)
                v.setdefault("ativo", d.get("ativo"))
                v.setdefault("fotografia", d.get("fotografia"))
                v.setdefault("nome_parlamentar", d.get("nome_parlamentar"))
                fil = self.todos("/api/parlamentares/filiacao/", {"parlamentar": pid}, cache=f"filiacao-{pid}")
                fil = [f for f in fil if not f.get("data_desfiliacao") or f["data_desfiliacao"] >= h]
                if fil:
                    ult = max(fil, key=lambda f: f.get("data") or "")
                    v["partido"] = self.partidos().get(ult.get("partido"))
            v["titular"] = any(m.get("titular") for m in v["mandatos"]) if v["mandatos"] else v.get("titular") in (True, "Sim")
        no_cargo = []
        for pid, v in por_id.items():
            cobre = [m for m in v["mandatos"] if (m.get("data_inicio_mandato") or "") <= h
                     and (not m.get("data_fim_mandato") or m["data_fim_mandato"] >= h)]
            ok = bool(v.get("ativo")) and (bool(cobre) or not v["mandatos"])
            fora = pid in self.excluir and (self.excluir[pid] is None or h <= self.excluir[pid])
            if (ok or pid in self.incluir) and not fora:
                v["mandato_hoje"] = max(cobre, key=lambda m: m.get("data_inicio_mandato") or "") if cobre else None
                no_cargo.append(v)
        return no_cargo, leg, por_id

    def partidos(self) -> dict:
        if not hasattr(self, "_partidos"):
            self._partidos = {p["id"]: p.get("sigla") for p in self.todos("/api/parlamentares/partido/", cache="partidos")}
        return self._partidos

    # ------------------------------------------------------------ propostas
    def tipos(self) -> dict[int, tuple[str, str, str]]:
        """{id do tipo: (tipo comum, sigla oficial, descrição)} só dos tipos que são propostas."""
        out = {}
        for t in self.todos("/api/materia/tipomaterialegislativa/", cache="tipos"):
            sig = (t.get("sigla") or "").strip()
            comum = self.tipos_fixos[sig] if sig in self.tipos_fixos else tipo_por_descricao(sig, t.get("descricao"))
            if comum:
                out[t["id"]] = (comum, sig, t.get("descricao") or "")
        return out

    def estado(self) -> dict:
        e = ler_json(self.pasta / "estado.json", {}) or {}
        e.setdefault("ultima", {})
        e.setdefault("autoria", {})
        e.setdefault("verif", {})
        return e

    def guardar_estado(self, e: dict) -> None:
        salvar_json(self.pasta / "estado.json", e)

    @staticmethod
    def _chave_tram(t: dict) -> tuple:
        return (t.get("data_tramitacao") or "", t.get("timestamp") or t.get("ultima_edicao") or "", t.get("id") or 0)

    def _aplicar_tramitacoes(self, e: dict, trams: list[dict], status_txt: dict, completo: set[str]) -> None:
        """Atualiza a última tramitação de cada proposta. completo = ids cujo histórico inteiro veio agora (recalcula do zero)."""
        por_mat: dict[str, list] = {}
        for t in trams:
            por_mat.setdefault(str(t["materia"]), []).append(t)
        for mid, lista in por_mat.items():
            if mid in completo:
                atual, vetos = None, set()
            else:
                atual = e["ultima"].get(mid)
                vetos = set((atual or {}).get("v") or [])
            for t in sorted(lista, key=self._chave_tram):
                vetos |= B.flags_veto(status_txt.get(t.get("status")))
                ch = list(self._chave_tram(t))
                if atual is None or t["id"] == atual.get("t") or ch >= (atual.get("k") or []):
                    atual = {"t": t["id"], "k": ch, "d": t.get("data_tramitacao"), "s": t.get("status")}
            if atual:
                atual["v"] = sorted(vetos)
                e["ultima"][mid] = atual
        for mid in completo - set(por_mat):
            e["ultima"][mid] = None  # nenhuma tramitação cadastrada

    def tramitacoes(self, e: dict, mats: dict[str, dict], status_txt: dict) -> None:
        h = hoje()
        novos = [int(m) for m in mats if m not in e["ultima"]]
        # revisão completa aos poucos (pega tramitação apagada ou corrigida sem mudar a data de edição)
        vencidos = sorted((m for m in mats if m in e["ultima"] and (e["verif"].get(m) or "") < _menos_dias(h, REVISAR_DIAS)),
                          key=lambda m: e["verif"].get(m) or "")
        revisar = [int(m) for m in vencidos[:REVISAR_LOTES * LOTE]]
        desde = e.get("desde")
        if desde:  # incremental: tudo o que foi criado ou editado desde a última vez (com 2 dias de folga)
            campo = e.get("campo_incremental") or self._campo_incremental()
            e["campo_incremental"] = campo
            trams = self.todos("/api/materia/tramitacao/", {f"{campo}__gte": _menos_dias(desde, 2)})
            self._aplicar_tramitacoes(e, [t for t in trams if str(t["materia"]) in mats], status_txt, set())
        lote = novos + [m for m in revisar if m not in novos]
        if lote:
            log(f"  {self.sigla}: histórico completo de {len(lote)} propostas ({len(novos)} novas)")
            trams = self.por_lotes("/api/materia/tramitacao/", "materia", lote)
            self._aplicar_tramitacoes(e, trams, status_txt, {str(m) for m in lote})
            for m in lote:
                e["verif"][str(m)] = h
        e["desde"] = h

    def _campo_incremental(self) -> str:
        """ultima_edicao (criação e edição) quando o SAPL filtra por ela; senão data_tramitacao (versões antigas)."""
        tudo = self.total("/api/materia/tramitacao/")
        for campo in ("ultima_edicao", "timestamp"):
            n = self.total("/api/materia/tramitacao/", {f"{campo}__gte": _menos_dias(hoje(), 7)})
            if 0 < n < tudo:
                return campo
        return "data_tramitacao"

    def autorias(self, e: dict, mats: dict[str, dict]) -> None:
        faltam = [int(mid) for mid, m in mats.items()
                  if (e["autoria"].get(mid) or {}).get("a") != sorted(m.get("autores") or [])]
        if faltam:
            log(f"  {self.sigla}: autoria de {len(faltam)} propostas")
            rows = self.por_lotes("/api/materia/autoria/", "materia", faltam)
            por: dict[str, list] = {str(m): [] for m in faltam}
            for r in rows:
                por.setdefault(str(r["materia"]), []).append([r["autor"], bool(r.get("primeiro_autor")), r["id"]])
            for mid, lst in por.items():
                if mid in mats:
                    e["autoria"][mid] = {"a": sorted(mats[mid].get("autores") or []), "r": sorted(lst, key=lambda x: x[2])}

    def normas(self) -> dict[str, dict]:
        """{id da matéria: norma} das normas de 2025 em diante ligadas a uma matéria."""
        tipos = {t["id"]: t.get("descricao") or t.get("sigla") for t in self.todos("/api/norma/tiponormajuridica/", cache="tipos-norma")}
        out = {}
        for n in self.todos("/api/norma/normajuridica/", {"ano__gte": INICIO_ANO, "materia__isnull": "false"}):
            if n.get("materia"):
                out[str(n["materia"])] = {"id": n["id"], "nome": B.nome_norma(tipos.get(n.get("tipo")), n.get("numero"), n.get("ano")),
                                          "data": n.get("data"), "tipo": tipos.get(n.get("tipo")) or ""}
        return out

    def autores_parlamentares(self) -> dict[int, int]:
        """{id do autor: id do parlamentar} (autores cujo "tipo de conteúdo" é o cadastro de parlamentares)."""
        cts = set()
        try:
            cts = {c["id"] for c in self.todos("/api/contenttypes/contenttype/", {"app_label": "parlamentares", "model": "parlamentar"},
                                               cache="ct-parlamentar", idade_h=None) if c.get("model") == "parlamentar"}
        except RuntimeError:
            pass
        ta = self.todos("/api/base/tipoautor/", cache="tipos-autor")
        if not cts:
            cts = {t.get("content_type") for t in ta if t.get("content_type")
                   and re.fullmatch(r"(parlamentar(es)?|vereador(a|es)?|vereador\(a\))", sem_acento((t.get("descricao") or "").lower().strip()))}
        out = {}
        for tid in [t["id"] for t in ta if t.get("content_type") in cts]:
            for a in self.todos("/api/base/autor/", {"tipo": tid}, cache=f"autores-{tid}"):
                if a.get("object_id") and a.get("content_type") in cts:
                    out[a["id"]] = a["object_id"]
        if not out:
            raise RuntimeError("não achei os autores que são vereadores")
        return out

    # ------------------------------------------------------------ tudo
    def coletar(self) -> dict:
        t0 = time.time()
        h = hoje()
        presentes, leg, todos_leg = self.membros()
        tse = B.Tse(self.ibge, self.uf, self.tse_manual)
        fonte_lista = fonte(self.casa, f"SAPL: vereadores em exercício na legislatura {leg['data_inicio'][:4]}–{leg['data_fim'][:4]} (dados abertos)",
                            f"{self.base}/parlamentar/", h)
        membros, por_pid = [], {}
        for v in presentes:
            d = self.parlamentar(v["id"])
            nome = B.nome_limpo(v.get("nome_parlamentar") or d.get("nome_parlamentar"))
            civil = B.nome_limpo(d.get("nome_completo")) if d.get("nome_completo") else None
            sigla_p = B.partido(v.get("partido"))
            pid, cand = tse.casar(v["id"], [nome, civil], sigla_p)
            foto = (v.get("fotografia") or d.get("fotografia") or None)
            if foto and self.base.startswith("https://"):
                foto = re.sub(r"^http://", "https://", foto)
            # suplente = não foi eleito(a) titular em 2024 (TSE), mesmo que tenha assumido a vaga de vez; sem o TSE, vale o SAPL
            supl = (cand or {}).get("sit") == "SUPLENTE" if cand else not v.get("titular")
            m = {"id": pid, "nome": nome, "nomeCivil": civil if civil and sem_acento(civil).lower() != sem_acento(nome or "").lower() else None,
                 "partido": sigla_p, "genero": (d.get("sexo") or "")[:1].upper() or (cand or {}).get("genero"),
                 "foto": B.foto(foto, pid, self.ibge), "url": f"{self.base}/parlamentar/{v['id']}",
                 "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None}
            if m["genero"] not in ("F", "M"):
                m["genero"] = None
            membros.append(m)
            por_pid[v["id"]] = (m, d, v)
        ids_dup = [m["id"] for m in membros]
        if len(set(ids_dup)) != len(ids_dup):
            raise RuntimeError(f"duas pessoas com o mesmo id: {sorted(i for i in ids_dup if ids_dup.count(i) > 1)}")
        # conferência: o número de pessoas no cargo tem de bater com o de vagas (eleitos em 2024, pelo TSE); se não bater,
        # o cadastro do SAPL está desatualizado e alguém precisa conferir à mão (o arquivo de antes fica como estava)
        vagas = sum(1 for c in tse.cands if c.get("sit", "").startswith("ELEITO"))
        if vagas and not (0.8 * vagas <= len(membros) <= vagas + 1):
            raise RuntimeError(f"o SAPL tem {len(membros)} vereadores ativos para {vagas} vagas: conferir à mão (incluir/excluir)")

        # propostas
        tipos = self.tipos()
        mats_l = self.todos("/api/materia/materialegislativa/", {"tipo__in": ",".join(map(str, sorted(tipos))),
                                                                  "data_apresentacao__gte": B.INICIO})
        mats = {str(m["id"]): m for m in mats_l}
        status_txt = {s["id"]: s.get("descricao") for s in self.todos("/api/materia/statustramitacao/", cache="status")}
        e = self.estado()
        self.autorias(e, mats)
        self.tramitacoes(e, mats, status_txt)
        normas = self.normas()
        autores = self.autores_parlamentares()
        for k in ("ultima", "autoria", "verif"):  # esquece propostas que não estão mais na lista
            e[k] = {mid: x for mid, x in e[k].items() if mid in mats}
        self.guardar_estado(e)

        por_parl: dict[int, list] = {pid: [] for pid in por_pid}
        heuristica = 0
        for mid, m in mats.items():
            comum, sig_tipo, _ = tipos[m["tipo"]]
            rows = (e["autoria"].get(mid) or {}).get("r") or []
            rows = [r for r in rows if r[0] in autores]
            if not rows:
                continue
            marcados = [r for r in (e["autoria"].get(mid) or {}).get("r") or [] if r[1]]
            for autor_id, primeiro, aid in rows:
                parl = autores[autor_id]
                if parl not in por_parl:
                    continue
                if marcados:
                    papel = "autor" if primeiro else "coautor"
                elif len((e["autoria"].get(mid) or {}).get("r") or []) == 1:
                    papel = "autor"
                elif self.primeiro_por_ordem:
                    heuristica += 1
                    papel = "autor" if aid == min(r[2] for r in (e["autoria"].get(mid) or {}).get("r")) else "coautor"
                else:
                    papel = "coautor"
                por_parl[parl].append(self.proposta(mid, m, comum, sig_tipo, papel, e["ultima"].get(mid), status_txt, normas))
        if heuristica:
            log(f"  {self.sigla}: {heuristica} autorias sem 'primeiro autor' marcado (vale o primeiro cadastrado)")

        escopo = (B.ESCOPO + ", segundo o sistema oficial da Câmara (SAPL).",
                  B.ESCOPO_EN + ", according to the City Council's official system (SAPL).")
        extras = {}
        for parl, (m, d, v) in por_pid.items():
            f_prop = fonte(self.casa, f"SAPL: matérias de {m['nome']}", f"{self.base}/parlamentar/{parl}/materias", h)
            x = {"propostas": regional.bloco_propostas(por_parl[parl], escopo[0], escopo[1], f_prop),
                 "links": {"oficial": m["url"], "email": (d.get("email") or "").strip() or None, "redes": []},
                 "fontes": [fonte_lista, f_prop]}
            if m.get("foto"):
                x["fotoCredito"] = self.casa
            mh = v.get("mandato_hoje")
            if mh and mh.get("data_inicio_mandato"):
                x["mandato"] = {"inicio": mh["data_inicio_mandato"], "fim": mh.get("data_fim_mandato") or leg["data_fim"],
                                "situacao": "Em exercício", "obs": None, "fonte": fonte_lista}
                if mh["data_inicio_mandato"] > leg["data_inicio"]:
                    x["desde"] = mh["data_inicio_mandato"]
            extras[m["id"]] = x

        notas = list(self.notas_casa) + [
            ("Votações com o voto de cada vereador e gastos do mandato não estão no sistema de dados abertos da Câmara (SAPL).",
             "Roll-call votes and office spending are not in the City Council's open data system (SAPL).")]
        if tse.sem_ligacao:
            log(f"  {self.sigla}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
        cobertura = {"lista": True, "propostas": True, "votacoes": False, "gastos": False}
        casa = {"casa": self.casa, "casa_en": self.casa_en, "sigla": self.sigla, "site": self.site, "fonte": fonte_lista,
                "sistema": "SAPL", "api": f"{self.base}/api/"}
        r = B.salvar(self.ibge, self.uf, casa, membros, extras, cobertura, notas, escopo)
        r["requisicoes"] = self.n_req
        r["semTse"] = len(tse.sem_ligacao)
        log(f"  {self.sigla}: {len(membros)} no cargo, {r['propostas']} propostas, {self.n_req} requisições, {time.time() - t0:.0f} s")
        return r

    def proposta(self, mid: str, m: dict, comum: str, sig_tipo: str, papel: str, ult: dict | None, status_txt: dict,
                 normas: dict) -> dict:
        desc = status_txt.get((ult or {}).get("s")) if ult else None
        vetos = set((ult or {}).get("v") or [])
        sigla = f"{sig_tipo} {m.get('numero')}/{m.get('ano')}"
        url = f"{self.base}/materia/{mid}"
        norma = normas.get(mid)
        if norma:
            parcial = "vp" in vetos
            p = regional.proposta(f"{self.prefixo}:{mid}", sigla, comum, m.get("data_apresentacao"), m.get("ementa"),
                                  desc, url, papel, status="lei", data_status=norma.get("data") or (ult or {}).get("d"),
                                  status_txt=B.virou(norma["nome"], parcial),
                                  lei={"nome": norma["nome"], "url": f"{self.base}/norma/{norma['id']}"})
            if re.search(r"emenda", sem_acento(norma.get("tipo", "").lower())):
                p["statusTxt_en"] = "Became an amendment to the city's Organic Law" + (" (with some parts vetoed)" if parcial else "")
            return p
        st, txt, txt_en = B.situacao(desc, self.regras, vetos, m.get("em_tramitacao"), comum)
        if st == "outra" and not txt and desc:
            txt = f"Situação na Câmara: {desc}"  # mostra o texto oficial quando não dá para classificar com segurança
        p = regional.proposta(f"{self.prefixo}:{mid}", sigla, comum, m.get("data_apresentacao"), m.get("ementa"), desc, url,
                              papel, status=st, data_status=(ult or {}).get("d"), status_txt=txt)
        if txt_en:
            p["statusTxt_en"] = txt_en
        return p


INICIO_ANO = int(B.INICIO[:4])


def _menos_dias(data: str, n: int) -> str:
    import datetime as dt
    return (dt.date.fromisoformat(data[:10]) - dt.timedelta(days=n)).isoformat()


__all__ = ["Sapl", "tipo_por_descricao"]
