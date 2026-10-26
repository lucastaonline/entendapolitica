"""Coletor das Assembleias que usam o SAPL 3 do Interlegis (API pública em <endereço>/api/): AM, AC, RO, RR e TO.

O que ele pega (só da API oficial da Casa, e da página oficial quando a Casa mantém a lista lá):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido,
   foto) + /api/parlamentares/mandato/ (titular ou suplente, datas) + /api/parlamentares/parlamentar/<id>/ (nome completo,
   sexo, e-mail). Uma Casa pode trocar a lista (ex.: Tocantins, onde a lista oficial com partido está no site da Casa);
2. propostas desde 1º/2/2023 (PL, PLP, PEC, PDL, PRC): /api/materia/materialegislativa/ (com os autores),
   /api/materia/autoria/ (quem é o primeiro autor, só quando há mais de um), a situação de hoje (última tramitação:
   /api/materia/materiaemtramitacao/) e a norma que a proposta virou (/api/norma/normajuridica/, campo "materia");
3. contagem do resto (requerimentos, indicações, moções, emendas...) de cada pessoa, para "outros";
4. votações nominais (/api/sessao/registrovotacao/ + /api/sessao/votoparlamentar/), só nas Casas em que o voto de cada
   deputado é registrado no SAPL de forma regular (ligado por Casa, depois de conferido);
5. o que o governo do estado fez (perfil gov-<UF>): projetos do Poder Executivo, leis e vetos.

Educado com o site (contrato "nenhum Em breve", seção 6): o robots.txt dos SAPL do Interlegis pede 60 s entre pedidos
("Crawl-delay: 60") e a Rede (_nco_comum) respeita isso. Por isso cada rodada diária faz poucos pedidos (uns 6 a 12):
- listas incrementais: só o que mudou desde a rodada anterior (filtro data_ultima_atualizacao__gte), 100 por página; uma
  tramitação nova muda a data de atualização da matéria (conferido no cache: 99 a 100% das matérias);
- situação (última tramitação) só das propostas que mudaram e de uma fatia das outras (as que andam a cada 30 dias, as
  que chegaram ao fim a cada 120), 100 por pedido, num pedido só para as propostas dos deputados e as do governo;
- a cada 7 dias, uma contagem confere se o total de matérias do SAPL bate com o cache (se não bate, a lista é relida aos
  poucos); votações nominais uma vez por semana; "outros documentos" de cada pessoa uma vez por mês (2 por rodada);
- cadastros que quase não mudam (legislaturas, tipos, autores, ficha de cada deputado) ficam em cache por 7 a 30 dias.
Há um limite de tempo por rodada (NCO_MINUTOS, e o fim da rodada inteira: _carga.py): o que não der fica para a próxima,
e o cache guarda o progresso. A primeira carga de uma Casa (cache vazio, como no robô do GitHub) usa a rodada toda e leva
dias; enquanto ela não termina, nada é gravado em dados/ (ficam os arquivos de antes) e o coletor devolve "em andamento".
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

import regional
from comum import DADOS, STATUS_TXT, chave_nome, data_iso, fonte, hoje, ler_json, log, sem_acento

from . import _carga
from ._nco_comum import (INICIO, OUTROS_TXT, Rede, SemTempo, casar_membros, classificar, com_status_en, gravar, limpa_civil,
                         limpa_nome, membro, nome_civil, nome_lei, nome_norma, artigo, partido_sigla, resumo_status)

LOTE = 100                  # o maior page_size que a API do SAPL aceita
CONTAGEM_DIAS = 7           # a cada 7 dias: o total de matérias no SAPL bate com o cache?
ROTACAO_ANDAM = 30          # situação das propostas que ainda andam: conferida de novo a cada 30 dias (além das que mudaram)
ROTACAO_FIM = 120           # das que chegaram ao fim (lei, arquivada, rejeitada, retirada, parada): a cada 120 dias
VOTOS_DIAS = 7              # votações nominais: uma vez por semana
OUTROS_DIAS = 30            # "outros documentos" de cada deputado: uma vez por mês...
OUTROS_POR_RODADA = 2       # ...no máximo 2 por rodada
HISTORICO_POR_RODADA = 5    # histórico de tramitação (situações que não dizem nada sozinhas): até 5 novos por rodada
EMENTAS_POR_RODADA = 3      # ementas de matérias votadas que não estão no cache: até 3 por rodada
CADASTRO_H = 24 * 30        # tipos de matéria, de norma, de autor e de situação: 30 dias


def _agora_iso() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S")


def _menos_dias(iso: str, dias: int) -> str:
    return (dt.date.fromisoformat(iso[:10]) - dt.timedelta(days=dias)).isoformat()


def _dias(iso: str | None) -> int:
    """Dias desde a data (muitos, se não houver data)."""
    if not iso:
        return 10 ** 6
    return (dt.date.fromisoformat(hoje()) - dt.date.fromisoformat(iso[:10])).days


class Sapl:
    def __init__(self, uf: str, base: str, casa: str, casa_en: str, sigla: str, site: str, veiculo: str, prefixo: str,
                 tipos: dict[int, str], regras: list[tuple], pasta: str, *, lista_oficial=None, tse_manual: dict | None = None,
                 pausa: float = 1.0, notas: list | None = None, vagas: int = 24, votacoes: bool = False,
                 nomes: dict | None = None, posse: str = "02-01", ambiguos: list[str] | None = None,
                 lista_url: str | None = None, lista_titulo: str | None = None, governo: dict | None = None,
                 sic: str | None = None, gastos=None):
        """tipos = {id do tipo de matéria no SAPL: PL|PLP|PEC|PDL|PRC}; regras = [(expressão sem acento, status, frase pt ou
        None, frase en ou None)] para a situação da última tramitação; lista_oficial(coletor, parlamentares) -> lista de
        {"sapl": id SAPL ou None, "nome", "partido", "foto", "url", "email", "redes"} troca a regra padrão (ativos na
        legislatura atual); tse_manual = {nome ou id SAPL: SQ do TSE ou "-"} conferido à mão; nomes = {id SAPL: nome usado
        no cargo} quando o SAPL escreve diferente da Casa; governo = o que o governo do estado fez (ver governo_gravar);
        gastos(coletor, membros) -> {id da pessoa: bloco "gastos"} (fonte própria da Casa, fora do SAPL; ver
        _votos_gastos.py), ou None enquanto a primeira carga dos gastos não termina (os perfis ficam com o bloco de antes).
        Uma exceção em gastos() não derruba a Casa: os perfis ficam com o bloco de antes."""
        self.uf, self.base = uf, base.rstrip("/")
        self.info = {"casa": casa, "casa_en": casa_en, "sigla": sigla, "site": site, "sic": sic}
        self.veiculo, self.prefixo, self.tipos, self.regras = veiculo, prefixo, tipos, regras
        self.lista_oficial, self.tse_manual = lista_oficial, tse_manual or {}
        self.notas = list(notas or [])
        self.vagas, self.com_votacoes, self.nomes, self.posse = vagas, votacoes, nomes or {}, posse
        self.ambiguos = list(ambiguos or [])
        self.lista_url, self.lista_titulo = lista_url, lista_titulo
        self.gov = governo
        self.gastos = gastos
        self.rede = Rede(pasta, pausa=pausa)
        self.parcial = False          # primeira carga das propostas em andamento (não grava os perfis)
        self.votos_de_antes = False   # votações relidas desde o começo: os perfis ficam com as da última leitura completa
        self._normas_lidas: list[dict] = []
        self._contas = {"historico": 0, "outros": 0, "ementas": 0}

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

    def _paginas(self, consulta: str, rel: dict) -> tuple[list[dict], bool]:
        """Páginas de uma consulta a partir de rel["pag"] (rel guarda o progresso), até acabar (True) ou até o tempo da
        rodada acabar (False: a próxima rodada continua da página seguinte)."""
        itens: list[dict] = []
        pag = int(rel.get("pag") or 1)
        sep = "&" if "?" in consulta else "?"
        try:
            while True:
                d = self.api(f"{consulta}{sep}page={pag}&page_size={LOTE}")
                itens += d.get("results") or []
                if not (d.get("pagination") or {}).get("next_page"):
                    return itens, True
                pag += 1
                rel["pag"] = pag
        except SemTempo:
            return itens, False

    # ------------------------------------------------------------ pessoas
    def legislatura(self) -> dict:
        # a lista de legislaturas só muda na posse: cache de 7 dias, de 20 h nos 30 dias depois do dia da posse
        h = hoje()
        posse = f"{h[:4]}-{self.posse}"
        perto = posse <= h <= (dt.date.fromisoformat(posse) + dt.timedelta(days=30)).isoformat()
        legs = self.todos("/api/parlamentares/legislatura/", "legislaturas", 20 if perto else 24 * 7)
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
        # quem está na legislatura (ativo, partido, foto): todo dia, 1 pedido
        parls = self.todos(f"/api/parlamentares/legislatura/{leg['id']}/parlamentares/", "parlamentares", 20)
        marca = sorted([p["id"], bool(p.get("ativo"))] for p in parls)
        ep = self.rede.estado("pessoas.json", {}) or {}
        # mandatos (titular ou suplente): de novo só quando a lista muda, ou a cada 7 dias
        mandatos = self.todos(f"/api/parlamentares/mandato/?legislatura={leg['id']}", "mandatos",
                              20 if ep.get("marca") != marca else 24 * 7)
        self.rede.guardar({"marca": marca}, "pessoas.json")
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
            # ficha de cada um (nome completo, sexo, e-mail): pedida quando a pessoa aparece e depois a cada 30 a 59 dias
            # (o prazo varia com o id, para as fichas não vencerem todas no mesmo dia)
            det = self.api(f"/api/parlamentares/parlamentar/{sid}/", f"parlamentar/{sid}.json", 24 * (30 + int(sid) % 30)) if sid else {}
            ms = [m for m in mandatos if m.get("parlamentar") == sid]
            atuais = [m for m in ms if (m.get("data_inicio_mandato") or "") <= h <= (m.get("data_fim_mandato") or "9999")] or ms
            m = sorted(atuais, key=lambda m: m.get("data_inicio_mandato") or "")[-1] if atuais else {}
            p.update({"det": det or {}, "mandato": m, "titular_sapl": m.get("titular") if m else None})
            out.append(p)
        return out, leg

    def _autores_tipo(self, filtro, idade: float) -> list[dict]:
        """Autores dos tipos de autor cuja descrição (sem acento, minúsculas) passa no filtro."""
        out = []
        for t in self.todos("/api/base/tipoautor/", "tipoautor", CADASTRO_H):
            if filtro(sem_acento((t.get("descricao") or "").lower()).strip()):
                out += self.todos(f"/api/base/autor/?tipo={t['id']}", f"autores-{t['id']}", idade)
        return out

    def autores(self, precisa: set[int] | None = None) -> dict[int, int]:
        """{id do parlamentar no SAPL: id de autor}. O cadastro de autores é relido a cada 7 dias, ou antes se alguém da
        lista ainda não tem autor (uma pessoa nova)."""
        def ler(idade):
            out = {}
            for a in self._autores_tipo(lambda d: re.sub(r"\W", "", d) == "parlamentar", idade):
                pid = a.get("object_id") or ((a.get("autor_related") or {}).get("value"))
                if pid:
                    out[int(pid)] = a["id"]
            return out
        out = ler(24 * 7)
        if precisa and not precisa <= set(out):
            out = ler(20)
        return out

    def autores_do_tipo(self, tipo_desc: str) -> list[int]:
        """Todos os autores de um tipo (ex.: "Poder Executivo"), para as Casas que cadastram cada governador como um autor."""
        return sorted(a["id"] for a in self._autores_tipo(lambda d: re.search(tipo_desc, d), 24 * 7))

    def autores_executivo(self, tipo_desc: str, nomes: list[str]) -> list[int]:
        """Ids de autor do governador de hoje, nas Casas que cadastram cada governador como um autor do tipo "Poder
        Executivo": o nome do autor tem de bater com o nome civil ou o nome da ficha (as palavras de um dentro do outro)."""
        alvo = [set(regional.palavras(n)) for n in nomes if n]
        out = []
        for a in self._autores_tipo(lambda d: re.search(tipo_desc, d), 24 * 7):
            p = set(regional.palavras(a.get("nome")))
            if p and any(x and (p == x or (min(len(p), len(x)) >= 2 and (p <= x or x <= p))) for x in alvo):
                out.append(a["id"])
        return sorted(out)

    # ------------------------------------------------------------ matérias (incremental)
    @staticmethod
    def _curta(x: dict) -> dict:
        return {"t": x["tipo"], "n": x.get("numero"), "a": x.get("ano"), "d": x.get("data_apresentacao"),
                "e": (x.get("ementa") or "").strip(), "au": x.get("autores") or [], "u": x.get("data_ultima_atualizacao"),
                "an": x.get("anexadas") or []}

    def _sincronizar(self, mats: dict, consulta: str, st: dict, chave: str, desde: str | None) -> tuple[set[str], bool]:
        """Atualiza mats {id: forma curta} com uma consulta à API. Devolve (ids novos ou mudados, a parte incremental deu
        certo?).
        - Todo dia: só o que mudou desde 'desde' (filtro data_ultima_atualizacao__gte; em geral 1 pedido).
        - Releitura (st[chave] = {"pag", "vistos", "total" ou "primeira"}): todas as páginas, aos poucos, continuando de
          onde a rodada anterior parou. Acontece na primeira carga e quando a contagem semanal não bate. No fim, saem do
          cache as matérias que não apareceram, se a conta fechar com o total do SAPL (matérias apagadas).
        A situação, a autoria e as marcas guardadas continuam onde nada mudou."""
        lidos: dict[str, dict] = {}
        rel = st.get(chave)
        if rel is not None:
            itens, fim = self._paginas(consulta, rel)
            vistos = set(rel.get("vistos") or []) | {str(x["id"]) for x in itens}
            lidos.update({str(x["id"]): self._curta(x) for x in itens})
            if fim:
                st.pop(chave, None)
                sobra = [k for k in mats if k not in vistos]
                if sobra and rel.get("total") is not None and len(mats) - len(sobra) == rel["total"]:
                    for k in sobra:
                        mats.pop(k, None)
                    log(f"  {self.uf}: {len(sobra)} matérias saíram do SAPL e do cache ({chave})")
                elif sobra:
                    log(f"  {self.uf}: {len(sobra)} matérias do cache não apareceram na releitura ({chave}); ficam")
            else:
                rel["vistos"] = sorted(vistos)
        ok = False
        if desde and not (rel or {}).get("primeira"):
            try:
                sep = "&" if "?" in consulta else "?"
                lidos.update({str(x["id"]): self._curta(x)
                              for x in self.todos(f"{consulta}{sep}data_ultima_atualizacao__gte={desde}")})
                ok = True
            except SemTempo:
                pass
        mudaram = set()
        for k, v in lidos.items():
            a = mats.get(k) or {}
            if a.get("u") != v["u"] or a.get("au") != v["au"]:
                mudaram.add(k)
            elif a.get("aut") is not None:
                v["aut"] = a["aut"]
            for campo in ("st", "fim", "rever"):
                if a.get(campo) is not None:
                    v[campo] = a[campo]
            mats[k] = v
        return mudaram, ok

    def materias(self) -> dict:
        """Propostas dos deputados (cadastro principal) e normas jurídicas, incrementais. Devolve o estado (com
        "_mudaram"); quem chama confere as situações e grava (estado.json)."""
        est = self.rede.estado("estado.json", {}) or {}
        if est.get("tipos") != sorted(self.tipos):  # tipos mudaram: tudo de novo
            est = {"tipos": sorted(self.tipos)}
        mats: dict[str, dict] = est.setdefault("materias", {})
        normas: dict[str, dict] = est.setdefault("normas", {})
        agora = _agora_iso()
        tipos = ",".join(str(t) for t in sorted(self.tipos))
        consulta = f"/api/materia/materialegislativa/?tipo__in={tipos}&data_apresentacao__gte={INICIO}"
        consulta_n = f"/api/norma/normajuridica/?data__gte={INICIO[:4]}-01-01"
        if not mats and "rel_mat" not in est:  # primeira carga: aos poucos, alguns dias
            est["rel_mat"] = {"pag": 1, "primeira": 1}
            est.setdefault("ultimo", agora)
        if not est.get("normas_ok") and "rel_normas" not in est:
            if est.get("completo"):  # cache do formato anterior (lista completa a cada 30 dias): as normas já estão lá
                est["normas_ok"] = 1
            else:
                est["rel_normas"] = {"pag": 1, "primeira": 1}
        desde = _menos_dias(est["ultimo"], 3) if est.get("ultimo") else None
        # contagem semanal: o total do SAPL bate com o cache? Se não bate, relê a lista aos poucos
        if "rel_mat" not in est and _dias(est.get("contado")) >= CONTAGEM_DIAS:
            try:
                total = self.total(consulta)
                est["contado"] = hoje()
                if total != len(mats):
                    log(f"  {self.uf}: o SAPL tem {total} matérias e o cache {len(mats)}; a lista vai ser relida aos poucos")
                    est["rel_mat"] = {"pag": 1, "total": total}
            except SemTempo:
                pass
        mudaram, ok_m = self._sincronizar(mats, consulta, est, "rel_mat", desde)
        self.parcial = bool((est.get("rel_mat") or {}).get("primeira"))
        # autoria (quem é o autor principal): só quando há mais de um autor; com um só, ele é o autor principal
        pedir = sorted(k for k, v in mats.items() if len(v["au"]) > 1 and (k in mudaram or v.get("aut") is None))
        for i in range(0, len(pedir), LOTE):
            lote = pedir[i:i + LOTE]
            try:
                res = self.todos(f"/api/materia/autoria/?materia__in={','.join(lote)}")
            except SemTempo:
                break
            aut: dict[str, dict] = {k: {} for k in lote}
            for a in res:
                if str(a["materia"]) in aut:
                    aut[str(a["materia"])][str(a["autor"])] = [bool(a.get("primeiro_autor")), a["id"]]
            for k in lote:
                mats[k]["aut"] = aut[k]
        # normas (as ligadas a uma proposta dizem que ela virou lei; as leis também contam no perfil do governador)
        lidas: list[dict] = []
        rel_n = est.get("rel_normas")
        if rel_n is not None:
            itens, fim = self._paginas(consulta_n, rel_n)
            lidas += itens
            if fim:
                est.pop("rel_normas", None)
                est["normas_ok"] = 1
        ok_n = False
        if desde:
            try:
                lidas += self.todos(f"{consulta_n}&data_ultima_atualizacao__gte={desde}")
                ok_n = True
            except SemTempo:
                pass
        for n in lidas:
            if n.get("materia"):
                normas[str(n["id"])] = {"m": n["materia"], "t": n.get("tipo"), "n": n.get("numero"), "a": n.get("ano"),
                                        "d": n.get("data")}
            else:
                normas.pop(str(n["id"]), None)
        self._normas_lidas = lidas
        if ok_m and ok_n:
            est["ultimo"] = agora
        est.pop("completo", None)
        est["_mudaram"] = sorted(mudaram)
        log(f"  {self.uf}: {len(mats)} propostas no cache ({len(mudaram)} novas ou mudadas), {len(normas)} normas ligadas a "
            f"propostas" + (" — primeira carga em andamento" if self.parcial else ""))
        return est

    def situacoes(self, conjuntos: list[tuple[dict, set[str]]]) -> tuple[int, int]:
        """Situação de hoje (última tramitação) das propostas, 100 por pedido, num pedido só para todos os cadastros
        (propostas dos deputados e do governo): primeiro as novas, as mudadas e as sem situação; depois uma fatia das
        outras (as que andam a cada ROTACAO_ANDAM dias, as que chegaram ao fim a cada ROTACAO_FIM). As que não couberem
        no tempo da rodada ficam marcadas ("rever") para a próxima. Devolve (conferidas, pedidas)."""
        dia = dt.date.fromisoformat(hoje()).toordinal()
        urgentes: dict[str, list] = {}
        rotina: dict[str, list] = {}
        for mats, mud in conjuntos:
            for k, v in mats.items():
                if k in mud:
                    v["rever"] = 1
                if v.get("st") is None or v.get("rever"):
                    urgentes.setdefault(k, []).append(v)
                elif int(k) % (ROTACAO_FIM if v.get("fim") else ROTACAO_ANDAM) == dia % (ROTACAO_FIM if v.get("fim") else ROTACAO_ANDAM):
                    rotina.setdefault(k, []).append(v)
        ids = sorted(urgentes, key=int) + sorted((k for k in rotina if k not in urgentes), key=int)
        feitas = 0
        for i in range(0, len(ids), LOTE):
            lote = ids[i:i + LOTE]
            try:
                res = self.todos(f"/api/materia/materiaemtramitacao/?materia__in={','.join(lote)}")
            except SemTempo:
                break
            sits = {}
            for t in res:
                partes = (t.get("__str__") or "").rsplit(" | ", 2)
                if len(partes) == 3:
                    sits[str(t["materia"])] = [partes[1].strip() or None, data_iso(partes[2].strip()), t.get("tramitacao")]
            for k in lote:
                for v in urgentes.get(k, []) + rotina.get(k, []):
                    v["st"] = sits.get(k) or [None, None, None]
                    v.pop("rever", None)
            feitas += len(lote)
        return feitas, len(ids)

    def _marcar_fim(self, mats: dict, com_norma: set[str]) -> None:
        """Quem já chegou ao fim (lei, arquivada, rejeitada, retirada, parada) entra na rotação lenta (ROTACAO_FIM)."""
        for k, v in mats.items():
            txt = (v.get("st") or [None])[0]
            v["fim"] = 1 if (k in com_norma or (txt and not self.ambiguo(txt)
                                                and classificar(txt, self.regras)[0] in ("lei", "arquivada", "rejeitada", "retirada", "parada"))) else 0

    def tipos_norma(self) -> dict[int, str | None]:
        return {t["id"]: nome_norma(t.get("descricao")) for t in self.todos("/api/norma/tiponormajuridica/", "tiponorma", CADASTRO_H)}

    _siglas: dict | None = None

    def sigla_tipo(self, t: int) -> str:
        if self._siglas is None:
            self._siglas = {x["id"]: (x.get("sigla") or "").strip() for x in
                            self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", CADASTRO_H)}
        return self._siglas.get(t) or self.tipos.get(t) or "?"

    # ------------------------------------------------------------ situação
    MORTAS = ("arquivada", "rejeitada", "retirada", "parada")

    def ambiguo(self, texto: str | None) -> bool:
        t = sem_acento((texto or "").lower())
        return any(re.search(e, t) for e in self.ambiguos)

    def historico(self, k: str, ult) -> list[list]:
        """Tramitações da proposta, da mais nova para a mais antiga: [[data, situação oficial, texto]]. Guardado no cache
        até aparecer uma tramitação nova; até HISTORICO_POR_RODADA novos por rodada (os outros ficam com o de antes)."""
        arq = f"historico/{k}.json"
        h = self.rede.estado(arq)
        if h and h.get("ult") == ult:
            return h["h"]
        if self._contas["historico"] >= HISTORICO_POR_RODADA or not self.rede.tem_tempo(2, self.base):
            return h["h"] if h else []
        self._contas["historico"] += 1
        try:
            if not hasattr(self, "_status_tram"):
                self._status_tram = {s["id"]: (s.get("descricao") or "").strip()
                                     for s in self.todos("/api/materia/statustramitacao/", "statustramitacao", CADASTRO_H)}
            ts = self.todos(f"/api/materia/tramitacao/?materia={k}")
        except SemTempo:
            return h["h"] if h else []
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
        """Quantos documentos que não são projetos (requerimentos, indicações, moções, emendas...) a pessoa apresentou.
        Conta conferida a cada OUTROS_DIAS dias, no máximo OUTROS_POR_RODADA por rodada (as outras ficam com a de antes);
        a conta de quem ainda não tem nenhuma no cache (pessoa nova ou primeira carga) é lida logo, se houver tempo."""
        if not autor:
            return None
        cache = f"outros/{autor}.json"
        arq = self.rede.pasta / cache
        existe = arq.exists()
        fresco = existe and (time.time() - arq.stat().st_mtime) / 86400 < OUTROS_DIAS
        d = None
        if not fresco and (not existe or self._contas["outros"] < OUTROS_POR_RODADA) and self.rede.tem_tempo(2, self.base):
            if existe:
                self._contas["outros"] += 1
            try:
                if not hasattr(self, "_outros_tipos"):
                    todos = self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", CADASTRO_H)
                    self._outros_tipos = ",".join(str(x["id"]) for x in todos if x["id"] not in self.tipos)
                d = self.api(f"/api/materia/materialegislativa/?autores={autor}&tipo__in={self._outros_tipos}"
                             f"&data_apresentacao__gte={INICIO}&page_size=1", cache, 0)
            except SemTempo:
                d = None
        if d is None and arq.exists():
            d = json.loads(arq.read_text(encoding="utf-8"))
        if d is None:
            self._contas["sem_outros"] = self._contas.get("sem_outros", 0) + 1
        n = ((d or {}).get("pagination") or {}).get("total_entries") or 0
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

    def _primeira_carga(self) -> bool:
        """O cache ainda está na primeira carga (como no robô do GitHub, que começa com o cache vazio)?"""
        est = self.rede.estado("estado.json", {}) or {}
        mats = est.get("materias") or {}
        if not mats or any((est.get(k) or {}).get("primeira") for k in ("rel_mat", "rel_normas")):
            return True
        return sum(1 for v in mats.values() if v.get("st") is None) > 0.05 * len(mats)

    def coletar(self) -> dict:
        t0 = time.time()
        if self._primeira_carga():  # primeira carga: a rodada toda (cada Casa fala com o seu servidor; ver _carga.py)
            fim = _carga.fim_rodada()
            self.rede.prazo = max(self.rede.prazo, fim if fim is not None else t0 + 50 * 60)
        try:
            return self._coletar(t0)
        except SemTempo:  # o fim da rodada chegou no meio: o cache guarda o que foi lido; nada pela metade em dados/
            return self._pendente("o tempo da rodada acabou", t0)

    def _pendente(self, etapa: str, t0: float) -> dict:
        hosts = ", ".join(f"{h}: {n}" for h, n in sorted(self.rede.por_host.items()))
        log(f"  {self.uf}: em andamento ({etapa}); os arquivos publicados de antes continuam; {self.rede.pedidos} pedidos "
            f"aos sites oficiais ({hosts}) em {int(time.time() - t0)} s")
        return _carga.pendente(self.info["sigla"], etapa, self.rede.pedidos)

    def _coletar(self, t0: float) -> dict:
        pessoas, leg = self.pessoas()
        autores = self.autores({int(p["sapl"]) for p in pessoas if p.get("sapl")})
        est = self.materias()
        mud = set(est.pop("_mudaram", []))
        gv = None
        if self.gov:
            try:
                gv = self.governo_sincronizar()
            except SemTempo:
                raise
            except Exception as e:  # o perfil do governador fica como estava; o resto continua
                log(f"  {self.uf}: ATENÇÃO: as listas do governo não foram lidas ({type(e).__name__}: {e})")
        conj = [(est["materias"], mud)]
        if gv is not None:
            conj.append((gv["materias"], set(gv.pop("_mudaram", []))))
        feitas, pedidas = self.situacoes(conj)
        nomes_norma = self.tipos_norma()
        norma_de: dict[str, dict] = {}
        for nid, n in est["normas"].items():
            if nomes_norma.get(n["t"]):
                n = dict(n, id=nid)
                atual = norma_de.get(str(n["m"]))
                if not atual or (n.get("d") or "") < (atual.get("d") or ""):
                    norma_de[str(n["m"])] = n
        for mats, _ in conj:
            self._marcar_fim(mats, set(norma_de))
        self.rede.guardar(est, "estado.json")
        if gv is not None:
            self.rede.guardar(gv, "governo.json")
        log(f"  {self.uf}: situações conferidas nesta rodada: {feitas} de {pedidas}")
        if self.parcial:
            return self._pendente(f"primeira carga das propostas: {len(est['materias'])} lidas", t0)
        sem_st = sum(1 for v in est["materias"].values() if v.get("st") is None)
        if sem_st > 0.05 * len(est["materias"]):  # na primeira carga, "a Assembleia não informa" seria falso
            return self._pendente(f"primeira carga das situações: {sem_st} de {len(est['materias'])} propostas sem situação", t0)
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
            x = {"propostas": bloco,
                 "links": {"oficial": url, "email": (p.get("email") or det.get("email") or "").strip() or None,
                           "redes": p.get("redes") or []},
                 "fontes": [self.fonte_lista(leg), fonte_prop]}
            if p.get("sapl"):
                x["fontes"].append(fonte(self.veiculo, f"Ficha de {nome} no SAPL", f"{self.base}/parlamentar/{p['sapl']}"))
            if votos.get(p.get("sapl")):
                x["votacoes"] = votos[p["sapl"]]
            elif self.votos_de_antes:
                antes = (ler_json(DADOS / "pessoas" / f"{pid}.json", {}) or {}).get("votacoes")
                if antes:
                    x["votacoes"] = antes
            extras[pid] = x
        if self._contas.get("sem_outros", 0) > OUTROS_POR_RODADA:  # primeira carga: contas de "outros" por ler
            return self._pendente(f"contas de outros documentos: {self._contas['sem_outros']} por ler", t0)
        log(f"  {self.uf}: situações {resumo_status(listas)}")
        self.listas = listas
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
        cobertura = {"lista": True, "propostas": True, "votacoes": bool(votos) or self.votos_de_antes, "gastos": com_gastos}
        notas = list(self.notas)
        legis = {"numero": leg.get("numero"), "inicio": leg.get("data_inicio"), "fim": leg.get("data_fim")}
        if self.lista_oficial:  # lista do site da Casa: depois da posse, só vale se o site já trocou a lista
            from ._nco_comum import conferir_virada, legislatura_por_data
            conferir_virada(self.rede, self.uf, [c["nome"] for c in casar], legislatura_por_data(self.posse))
        r = gravar(self.uf, self.info, membros, extras, cobertura, self.fonte_lista(leg), notas, minimo=self.vagas - 4,
                   legislatura=legis)
        if len(membros) != self.vagas:
            log(f"  {self.uf}: ATENÇÃO: {len(membros)} pessoas na lista oficial (a Casa tem {self.vagas} vagas)")
        if self.gov:
            try:
                self.governo_gravar(est, gv, norma_de, nomes_norma)
            except SemTempo:  # sem tempo para a parte do governo: o arquivo do governador de antes continua
                log(f"  {self.uf}: o tempo da rodada acabou antes da parte do governo; o arquivo de antes continua")
            except Exception as e:  # o arquivo do governador de antes continua (se for do mesmo período)
                from . import _nco_gov as G
                log(f"  {self.uf}: ATENÇÃO: o que o governo fez não foi atualizado ({type(e).__name__}: {e})")
                G.descartar_se_velho(self.uf)
        hosts = ", ".join(f"{h}: {n}" for h, n in sorted(self.rede.por_host.items()))
        log(f"  {self.uf}: {self.rede.pedidos} pedidos aos sites oficiais ({hosts}) em {int(time.time() - t0)} s")
        return r

    def nome_de(self, p: dict) -> str:
        if p.get("sapl") in self.nomes:
            return self.nomes[p["sapl"]]
        return limpa_nome(p.get("nome_site") or p.get("nome_parlamentar") or (p.get("det") or {}).get("nome_parlamentar"))

    @staticmethod
    def escopo() -> tuple[str, str]:
        from ._nco_comum import ESCOPO, ESCOPO_EN
        return ESCOPO, ESCOPO_EN

    # ------------------------------------------------------------ o que o governo do estado fez
    def _autores_gov(self, cfg: dict) -> list[int]:
        a = cfg.get("autores")
        if a == "tipo":  # RR: cada governador é um autor do tipo "Poder Executivo"; entram todos (inclusive quem esteve no exercício)
            return self.autores_do_tipo(cfg["tipo_autor"])
        return sorted(a or [])

    @staticmethod
    def _guarda_lei(leis: dict, n: dict, tipos: dict, ini: str) -> None:
        sig = tipos.get(n.get("tipo"))
        num = re.sub(r"\D", "", str(n.get("numero") or ""))
        if sig and num and (n.get("data") or "") >= ini:
            leis[str(n["id"])] = {"t": sig, "n": int(num), "d": n["data"]}
        else:
            leis.pop(str(n["id"]), None)

    def governo_sincronizar(self) -> dict:
        """Listas do perfil do governador, incrementais (governo.json): os projetos do Executivo que não estão no cadastro
        principal (tipos só do Executivo, como em TO, ou o mês antes do começo da legislatura, como em RO), as matérias de
        veto e as leis do período. As leis do SAPL: primeira carga por tipo; depois, as novas chegam com as normas do
        cadastro principal (sem pedido a mais). Os projetos dos tipos dos deputados vêm do cadastro principal."""
        from . import _nco_gov as G
        cfg = self.gov
        g = G.governo_atual(self.uf)
        ini = g["inicio"]
        autores = self._autores_gov(cfg)
        tipos = sorted(cfg["tipos"])
        comuns = [t for t in tipos if t in self.tipos]
        extra = [t for t in tipos if t not in self.tipos]
        vc = cfg.get("vetos") or {}
        lc = cfg.get("leis") if isinstance(cfg.get("leis"), dict) else None
        chave = {"inicio": ini, "tipos": tipos, "autores": autores, "vetos": sorted(vc.get("tipos") or []),
                 "leis": sorted((lc or {}).get("tipos") or [])}
        gv = self.rede.estado("governo.json", {}) or {}
        if gv.get("chave") != chave:  # outro período ou outra configuração: começa de novo
            gv = {"chave": chave}
        for k in ("materias", "vetos", "leis"):
            gv.setdefault(k, {})
        feitas = set(gv.get("feitas") or [])
        agora = _agora_iso()
        desde = _menos_dias(gv["ultimo"], 3) if gv.get("ultimo") else None
        gv.setdefault("ultimo", agora)
        m = "/api/materia/materialegislativa/?tipo__in="
        consultas = []
        if extra:
            consultas.append(("extra", f"{m}{','.join(map(str, extra))}&data_apresentacao__gte={ini}", "materias"))
        if comuns and ini < INICIO:
            for a in autores or [None]:
                consultas.append((f"jan-{a}", f"{m}{','.join(map(str, comuns))}&data_apresentacao__gte={ini}"
                                  f"&data_apresentacao__lt={INICIO}" + (f"&autores={a}" if a else ""), "materias"))
        if vc.get("tipos"):
            consultas.append(("vetos", f"{m}{','.join(map(str, sorted(vc['tipos'])))}&data_apresentacao__gte={ini}", "vetos"))
        mudaram: set[str] = set()
        incremental_ok = True
        for nome, q, destino in consultas:
            rk = f"rel_{nome}"
            ja = nome in feitas
            if not ja and rk not in gv:
                gv[rk] = {"pag": 1, "primeira": 1}
            mud, ok = self._sincronizar(gv[destino], q, gv, rk, desde if ja else None)
            if ja and not ok:
                incremental_ok = False
            if not ja and rk not in gv:
                feitas.add(nome)
            if destino == "materias":
                mudaram |= mud
        if lc:
            for t in sorted(lc["tipos"]):
                nome = f"leis-{t}"
                if nome in feitas:
                    continue
                rk = f"rel_{nome}"
                rel = gv.setdefault(rk, {"pag": 1, "primeira": 1})
                itens, fim = self._paginas(f"/api/norma/normajuridica/?tipo={t}&data__gte={ini}", rel)
                for n in itens:
                    self._guarda_lei(gv["leis"], n, lc["tipos"], ini)
                if fim:
                    gv.pop(rk, None)
                    feitas.add(nome)
            for n in self._normas_lidas:  # leis novas ou mudadas, do incremental das normas do cadastro principal
                self._guarda_lei(gv["leis"], n, lc["tipos"], ini)
        if desde and incremental_ok:
            gv["ultimo"] = agora
        gv["feitas"] = sorted(feitas)
        gv["_mudaram"] = sorted(mudaram)
        return gv

    def governo_gravar(self, est: dict, gv: dict | None, norma_de: dict, nomes_norma: dict) -> None:
        """Perfil do governador (dados/pessoas/gov-<UF>.json): os projetos que o Poder Executivo mandou para a Assembleia
        desde o começo do mandato de quem governa hoje, com a situação de cada um (as mesmas regras das propostas dos
        deputados), e o bloco "executivo": leis e vetos do período. Mesma régua do perfil do presidente: entra o que o
        governo assinou ou mandou, inclusive quando outra pessoa estava no exercício do cargo (a nota diz quantos, quando
        o SAPL registra quem foi).

        self.gov = {"autores": [ids] | "tipo" | None, "tipo_autor": expressão do tipo de autor do Executivo (para saber
        quem é o governador de hoje, ou para "tipo"), "tipos": {id: PL|PLP|PEC|PDL|MPV}, "vetos": {"tipos": [ids],
        "filtro": expressão (só as mensagens de veto, quando o tipo mistura outras), "parcial", "total", "tipos_parciais",
        "tipos_totais", "de_onde": (pt, en)} ou None, "leis": {"tipos": {id: LO|LC}, "de_onde", "promulgadas"} ou uma
        função (coletor, início) -> (leis, de_onde, promulgadas, fontes, existentes) ou None, "nota": [(pt, en)],
        "nota_propostas": (pt, en), "diario": {"nome", "url"}}"""
        from . import _nco_gov as G
        cfg = self.gov
        g = G.governo_atual(self.uf)
        ini = g["inicio"]
        if gv is None:
            raise RuntimeError("as listas do governo não foram lidas nesta rodada")
        pend = sorted(k for k, v in gv.items() if k.startswith("rel_") and (v or {}).get("primeira"))
        if pend:
            log(f"  gov-{self.uf}: primeira carga em andamento ({', '.join(pend)}); o arquivo de antes continua")
            G.descartar_se_velho(self.uf)
            return
        autores = gv["chave"]["autores"]
        proprios = set(self.autores_executivo(cfg["tipo_autor"], [g["nomeCivil"], g["nome"]])) if cfg.get("tipo_autor") else set()
        # 1. projetos do Executivo: os dos tipos dos deputados vêm do cadastro principal; os outros, das listas do governo
        extra = {t for t in cfg["tipos"] if t not in self.tipos}
        escolhidos: dict[str, dict] = {}
        for k, v in est["materias"].items():
            if (v["t"] in cfg["tipos"] and v["t"] not in extra and (v.get("d") or "") >= ini
                    and (not autores or set(v["au"]) & set(autores))):
                escolhidos[k] = v
        for k, v in gv["materias"].items():
            if k in escolhidos or v["t"] not in cfg["tipos"] or (v.get("d") or "") < ini:
                continue
            if v["t"] in extra or not autores or set(v["au"]) & set(autores):
                escolhidos[k] = v
        sem_st = sum(1 for v in escolhidos.values() if v.get("st") is None)
        if sem_st > 0.05 * max(len(escolhidos), 1):
            log(f"  gov-{self.uf}: primeira carga das situações em andamento ({sem_st} de {len(escolhidos)}); o arquivo de antes continua")
            G.descartar_se_velho(self.uf)
            return
        lista, de_outro = [], 0
        for k, v in escolhidos.items():
            s = self.situacao(k, v, norma_de.get(k), nomes_norma)
            prop = regional.proposta(f"{self.prefixo}:{k}", f"{self.sigla_tipo(v['t'])} {v['n']}/{v['a']}", cfg["tipos"][v["t"]],
                                     v.get("d"), v.get("e"), s["oficial"], f"{self.base}/materia/{k}", papel="autor",
                                     status=s["status"], data_status=s["data"], status_txt=s["txt"], lei=s["lei"])
            lista.append(com_status_en(prop, s["en"]))
            if proprios and not set(v["au"]) & proprios:
                de_outro += 1
        log(f"  gov-{self.uf}: {len(lista)} projetos do Executivo desde {ini}; situações {resumo_status([lista])}")
        filtro = f"autoria__autor={autores[0]}" if len(autores) == 1 else f"tipo={sorted(cfg['tipos'])[0]}"
        fonte_prop = fonte(self.veiculo, "Projetos do Poder Executivo (SAPL, dados abertos)",
                           f"{self.base}/materia/pesquisar-materia?{filtro}")
        esc, esc_en = G.escopo(g, list(cfg["tipos"].values()))
        bloco = regional.bloco_propostas(lista, esc, esc_en, fonte_prop)
        notas_p = [cfg["nota_propostas"]] if cfg.get("nota_propostas") else []
        if de_outro:
            notas_p.append((f"Entram também {de_outro} projeto{'s' if de_outro > 1 else ''} mandado{'s' if de_outro > 1 else ''} "
                            "por quem estava no exercício do cargo de governador (o vice-governador, por exemplo).",
                            f"Also included: {de_outro} bill{'s' if de_outro > 1 else ''} sent by someone acting as governor "
                            "(the vice governor, for example)."))
        if notas_p:
            bloco["nota"] = " ".join(p for p, _ in notas_p)
            bloco["nota_en"] = " ".join(e for _, e in notas_p)
        # 2. leis sancionadas no período
        ex_fontes: list[dict] = []
        nota: list[str] = []
        nota_en: list[str] = []
        leis = None
        lc = cfg.get("leis")
        res = None
        if callable(lc):
            res = lc(self, ini)
        elif lc:
            lst = [{"tipo": x["t"], "numero": x["n"], "data": x["d"]} for x in gv["leis"].values()]
            res = (lst, lc["de_onde"], lc.get("promulgadas"),
                   [fonte(self.veiculo, "Normas jurídicas: leis ordinárias e complementares (SAPL, dados abertos)",
                          f"{self.base}/norma/pesquisar")])
        if res:
            lst, de_onde, prom, fls = res[:4]
            leis = G.contar_leis(lst, ini, hoje(), res[4] if len(res) > 4 else None)
            if leis["total"]:
                pt, en = G.texto_leis(leis, de_onde, prom)
                nota.append(pt)
                nota_en.append(en)
                ex_fontes += fls
            else:
                leis = None
        # 3. vetos que chegaram à Assembleia no período (de quem estava no cargo, inclusive no exercício)
        vetos = None
        vc = cfg.get("vetos")
        if vc:
            vs = [v for v in gv["vetos"].values() if (v.get("d") or "") >= ini
                  and (not vc.get("filtro") or re.search(vc["filtro"], sem_acento((v.get("e") or "").lower()).strip()))]
            parc = tot = outro_v = 0
            for v in vs:
                em = sem_acento((v.get("e") or "").lower()).strip()
                if v["t"] in (vc.get("tipos_parciais") or []) or (vc.get("parcial") and re.search(vc["parcial"], em)):
                    parc += 1
                elif v["t"] in (vc.get("tipos_totais") or []) or (vc.get("total") and re.search(vc["total"], em)):
                    tot += 1
                if proprios and not set(v["au"]) & proprios:
                    outro_v += 1
            vetos = {"total": len(vs), "ultimo": max((v.get("d") or "" for v in vs), default="") or None}
            if parc + tot == len(vs):  # só separa totais e parciais quando dá para classificar todos
                vetos.update({"totais": tot, "parciais": parc})
            pt, en = G.texto_vetos(vetos, vc["de_onde"])
            if outro_v:
                pt += (f" Inclui {outro_v} veto{'s' if outro_v > 1 else ''} de quem estava no exercício do cargo de governador "
                       "(o vice-governador, por exemplo).")
                en += f" Includes {outro_v} veto{'es' if outro_v > 1 else ''} by someone acting as governor (the vice governor, for example)."
            nota.append(pt)
            nota_en.append(en)
            ex_fontes.append(fonte(self.veiculo, "Vetos do governador (SAPL, dados abertos)",
                                   f"{self.base}/materia/pesquisar-materia?tipo={vc['tipos'][0]}"))
        for pt, en in cfg.get("nota") or []:
            nota.append(pt)
            nota_en.append(en)
        ex = G.bloco_executivo(g, leis, vetos, ex_fontes, nota, nota_en)
        G.gravar_gov(self.uf, bloco, ex, [fonte_prop] + ex_fontes, cfg.get("diario"), ini)

    # ------------------------------------------------------------ votações (só onde a Casa registra o voto de cada um)
    # voto como o SAPL escreve -> como o site guarda (js/traducoes.js, D.voto: Sim, Não, Abstenção e códigos de ausência)
    VOTO = {"sim": "Sim", "nao": "Não", "abstencao": "Abstenção", "nao votou": "NR", "obstrucao": "Obstrução",
            "presidente": "PS", "presidencia": "PS", "presidente da sessao": "PS", "ausente": "NCOM"}

    def votacoes(self, pessoas: list[dict], leg: dict, est: dict) -> dict:
        """{id SAPL do deputado: bloco "votacoes" do perfil}. Grava o catálogo dados/votacoes/<prefixo>.json (cada votação
        uma vez só, no formato do README). Só votações nominais (com o voto de cada um) desde o começo da legislatura.
        Lidas uma vez por semana (VOTOS_DIAS), da última leitura menos 2 dias até hoje, em janelas de um mês: o progresso
        fica gravado a cada janela e uma rodada que acabar no meio continua na seguinte. Nas outras rodadas, o catálogo e
        os perfis são montados com o que já está no cache."""
        from comum import DADOS, ler_json, salvar_json, sem_mudar_data
        from ._nco_comum import RobotsFechado
        inicio = max(leg.get("data_inicio") or INICIO, INICIO)
        vt = self.rede.estado("votos.json", {}) or {}
        primeira = not vt.get("regs") or vt.get("inicio") != inicio
        regs: dict = {} if primeira else vt["regs"]
        votos: dict = {} if primeira else vt["votos"]
        sess: dict = {} if primeira else vt.get("sess") or {}
        feito = vt.get("feito") if not primeira else None
        # o catálogo só é publicado depois da primeira leitura completa (na primeira carga, um perfil mostraria só uma
        # parte das votações); o cache do formato anterior (sem "completo"), em dia, já conta como completo
        if primeira:
            completo = False
        elif "completo" in vt:
            completo = bool(vt["completo"])
        else:
            completo = _dias(feito) <= 2 * VOTOS_DIAS
        lido = feito
        if primeira or vt.get("pendente") or _dias(feito) >= VOTOS_DIAS:
            desde = inicio if not feito else max(inicio, _menos_dias(feito, 2))
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
                    if regs_j:  # sem votação na janela, não há votos nem sessões para buscar
                        for v in self.todos(f"/api/sessao/votoparlamentar/?data_hora__gte={a}&data_hora__lt={b}"):
                            votos_j.setdefault(str(v["votacao"]), {})[str(v["parlamentar"])] = v.get("voto")
                        for o in self.todos(f"/api/sessao/ordemdia/?data_ordem__gte={a}&data_ordem__lt={b}&tipo_votacao=2"):
                            sess_j["o" + str(o["id"])] = o.get("sessao_plenaria")
                        for o in self.todos(f"/api/sessao/expedientemateria/?data_ordem__gte={a}&data_ordem__lt={b}&tipo_votacao=2"):
                            sess_j["e" + str(o["id"])] = o.get("sessao_plenaria")
                except (SemTempo, RobotsFechado):
                    raise
                except RuntimeError:
                    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
                    if (db - da).days <= 4:
                        raise
                    meio = (da + (db - da) / 2).isoformat()
                    log(f"  {self.uf}: o SAPL demorou com as votações de {a} a {b}; dividindo a janela")
                    janela(a, meio)
                    janela(meio, b)
                    return
                regs.update(regs_j)
                for k, v in votos_j.items():
                    votos.setdefault(k, {}).update(v)
                sess.update(sess_j)

            try:
                for a, b in janelas:
                    janela(a, b)
                    lido = min(b, hoje())
                    self.rede.guardar({"regs": regs, "votos": votos, "sess": sess, "inicio": inicio,
                                       "feito": lido, "pendente": 1, "completo": int(completo)}, "votos.json")
                completo = True
                self.rede.guardar({"regs": regs, "votos": votos, "sess": sess, "inicio": inicio, "feito": hoje(),
                                   "pendente": 0, "completo": 1}, "votos.json")
            except SemTempo:
                log(f"  {self.uf}: votações: o tempo desta rodada acabou; a leitura continua na próxima")
        arq_rel = f"dados/votacoes/{self.prefixo}.json"
        arq = DADOS / "votacoes" / f"{self.prefixo}.json"
        if not completo:
            # releitura desde o começo (cache perdido): se o catálogo publicado é desta legislatura, ele e os blocos dos
            # perfis ficam como estavam (coletar() copia o bloco de antes); se não, os perfis saem sem votações
            antes = (ler_json(arq, {}) or {}).get("votacoes") or {}
            self.votos_de_antes = any((v.get("data") or "") >= inicio for v in antes.values())
            log(f"  {self.uf}: primeira carga das votações em andamento (lidas até {lido or '—'}); "
                + ("os perfis ficam com as votações da última leitura completa" if self.votos_de_antes
                   else "os perfis saem sem votações até ela terminar"))
            return {}
        resultados =  {t["id"]: t.get("nome") for t in self.todos("/api/sessao/tiporesultadovotacao/", "tiporesultado", CADASTRO_H)}
        tipos_desc = {}
        for t in self.todos("/api/materia/tipomaterialegislativa/", "tipomateria", CADASTRO_H):
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
        fonte_v =  fonte(self.veiculo, "Votações nominais do Plenário (SAPL, dados abertos)", f"{self.base}/sessao/pesquisar-sessao")
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
        """Ementa de uma matéria votada que não está no cache das propostas (requerimentos, vetos, projetos de antes de
        2023). No máximo EMENTAS_POR_RODADA novas por rodada (as outras vêm nas próximas), para não pesar no site da Casa."""
        if not m:
            return None
        arq = self.rede.pasta / f"materia/{m}.json"
        if not arq.exists():
            if self._contas["ementas"] >= EMENTAS_POR_RODADA or not self.rede.tem_tempo(1, self.base):
                return None
            self._contas["ementas"] += 1
        try:
            d = self.api(f"/api/materia/materialegislativa/{m}/", f"materia/{m}.json", None)
        except Exception:
            return None
        return (d.get("ementa") or "").strip() or None
