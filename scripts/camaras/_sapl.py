"""Coletor genérico das Câmaras Municipais que usam o SAPL 3.x do Interlegis (API REST pública em <endereço>/api/).

Duas formas de usar:
- capitais: um arquivo pequeno por cidade (scripts/camaras/c<IBGE>.py), com os ajustes conferidos à mão:

    from ._sapl import Sapl

    def coletar():
        return Sapl("2408102", "RN", "https://sapl.natal.rn.leg.br", casa="Câmara Municipal de Natal",
                    casa_en="Natal City Council", sigla="CMN", site="https://www.cmnat.rn.gov.br", prefixo="cmnatal").coletar()

- as outras cidades: uma entrada em scripts/camaras/sapl_cidades.json, sem arquivo .py (scripts/camaras/_lista.py;
  "python scripts/legislativos.py sapl"). O nome da Câmara, a sigla e o site vêm do próprio SAPL (/api/base/casalegislativa/).

O que ele pega (tudo da API oficial; nada de sites de terceiros):
1. quem está no cargo hoje: legislatura atual -> /api/parlamentares/legislatura/<id>/parlamentares/ (ativo, partido de hoje,
   foto, titular ou suplente) + /api/parlamentares/mandato/ + /api/parlamentares/parlamentar/ (nome completo, sexo, e-mail);
2. propostas desde 1º/1/2025 (projetos de lei, de lei complementar, de emenda à Lei Orgânica, de decreto legislativo e de
   resolução): /api/materia/materialegislativa/, autoria (/api/materia/autoria/: quem é o primeiro autor), situação = a da
   última tramitação (/api/materia/tramitacao/ + /api/materia/statustramitacao/) e a norma que a proposta virou
   (/api/norma/normajuridica/: "virou lei");
3. o prefeito (pref-<IBGE>): os projetos que a prefeitura mandou à Câmara (autor "Poder Executivo", "Prefeito", "Chefe do Poder
   Executivo"...) desde a posse (ou desde que assumiu, se era vice), e o quadro "Leis sancionadas e vetos": as leis ordinárias
   e complementares cadastradas no SAPL e os projetos que receberam veto (andamento no SAPL). Cada número só entra quando dá
   para contar com segurança (ver Sapl.executivo); senão fica fora e a nota da Câmara diz por quê;
4. votações nominais e gastos: o SAPL quase nunca tem (cobertura false).

Educado com o site (contrato, seção 6):
- o robots.txt de cada servidor é lido uma vez por rodada (RFC 9309: 4xx = pode ler; 5xx ou sem resposta = não lê nada
  nessa rodada); nenhum endereço proibido ("Disallow") é pedido;
- um pedido por vez por servidor, com o intervalo do robots.txt ("Crawl-delay": 60 s no SAPL do Interlegis) ou a pausa do
  coletor, o que for maior; uma nova tentativa também espera o intervalo; erro 429/503 = para a cidade nessa rodada;
- poucos pedidos: páginas de 100 (o máximo do SAPL), o que quase não muda fica guardado por dias (tipos, autores, situações),
  e as matérias, tramitações e normas vêm só "o que mudou desde a última vez" (filtros por data de edição), sobre o estado
  guardado em .cache/camaras/<IBGE>/estado.json;
- um orçamento de pedidos por cidade em cada rodada (ORCAMENTO, ou SAPL_PEDIDOS no ambiente; e o limite de tempo da rodada,
  LEGISLATIVOS_PRAZO): a primeira carga de uma cidade grande pode levar várias rodadas; o que foi lido fica guardado e a
  próxima rodada continua dali. Enquanto a carga não termina, os arquivos publicados da cidade ficam como estavam.

Conferência: o número de vereadores ativos no SAPL tem de ser igual ao de vagas (eleitos em 2024, pelo TSE). Nas capitais,
se não bater, o coletor para e fica o arquivo de antes (alguém confere à mão e anota incluir/excluir). Nas outras cidades
(sem_lista_se_falhar=True), a página da cidade fica com a lista do TSE e as propostas entram só para quem está nela e foi
ligado ao TSE pelo nome sem dúvida.

Grava um arquivo por cidade (limite de arquivos do site): dados/camaras/<IBGE>.json (lista oficial) e
dados/camaras/extras/<IBGE>.json (propostas de cada vereador e o que o prefeito fez). Fotos: só as capitais guardam a foto
oficial reduzida em img/pessoas/; nas outras vale a foto do TSE.
"""
from __future__ import annotations

import bisect
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.parse

import regional
from comum import EXTRAS_CIDADES, baixar, fonte, hoje, ler_json, log, nome_proprio, salvar_json, sem_acento
from regional import CAMARAS

from . import _base as B

LOTE = 100               # ids por requisição (materia__in=...) e tamanho da página (o SAPL não passa de 100)
ORCAMENTO = int(os.environ.get("SAPL_PEDIDOS") or 60)   # pedidos por cidade em cada rodada (com 60 s entre eles: 1 hora)
LOG_PEDIDOS = bool(os.environ.get("SAPL_LOG_PEDIDOS"))  # 1 = escreve no log cada pedido feito (para medir)
FOLGA_DIAS = 4           # "o que mudou desde a última vez" pede alguns dias a mais, para não perder nada
LISTA_COMPLETA_DIAS = 90 # de tempos em tempos, a lista inteira de matérias e normas (pega o que foi apagado)
REVISAR_DIAS = 60        # revisão do histórico de cada proposta (só com sobra de orçamento)
FIXO_H = 24 * 30         # horas de cache das listas que quase não mudam (tipos, autores, partidos, nome da Câmara)
SEMANA_H = 24 * 7
LEIS_ATRASO_DIAS = 120   # a lei mais nova cadastrada tem de ser recente; senão a Câmara parou de cadastrar as leis no SAPL
LEIS_FALTANDO = 0.15     # no máximo 15% dos números de lei do período sem cadastro no SAPL (contando o começo e o fim)
LEIS_BURACO, LEIS_BURACO_FRACAO = 5, 0.05  # e nenhum buraco maior que 5 números seguidos (ou 5% da faixa, se for maior)
LEIS_SALTO = 50          # um salto de mais de 50 números separa outra numeração (ou um erro de digitação): não é buraco
LEIS_RECESSO_DIAS = 45   # no começo do mandato (recesso de janeiro), dias sem lei que não contam como falta
LEIS_LAG_DIAS = 15       # no fim, o atraso normal entre a sanção e o cadastro da lei no SAPL (não conta como falta)
MAT, TRAM, NORMA = "/api/materia/materialegislativa/", "/api/materia/tramitacao/", "/api/norma/normajuridica/"
REG, VOTO = "/api/sessao/registrovotacao/", "/api/sessao/votoparlamentar/"
ORDEM, EXPEDIENTE, TIPO_RES = "/api/sessao/ordemdia/", "/api/sessao/expedientemateria/", "/api/sessao/tiporesultadovotacao/"
# texto do registro de votação: "Ordem: Ordem do Dia/Expediente: 1 - Projeto de Lei Ordinária nº 723 de 2016 em 10ª Ordinária ..."
_REGISTRO_TXT = re.compile(r"\d+\s*-\s*(.+?)\s+n[º°o]\.?\s*\d+\s*(?:de|/)\s*\d{4}")
ESCOPO_VOTOS = ("Votações nominais (em que o voto de cada vereador fica registrado) de projetos, emendas e vetos no Plenário "
                "desde 1º/1/2025, segundo o sistema oficial da Câmara (SAPL). Votações de requerimentos, indicações, moções e "
                "outros documentos, e as que não decidiram a proposta (adiamento, pedido de vista), não entram.",
                "Roll-call votes (where each councilor's vote is recorded) on bills, amendments and vetoes in the full City "
                "Council since January 1, 2025, according to the City Council's official system (SAPL). Votes on requests, "
                "recommendations, motions and other documents, and votes that did not decide on the proposal (postponing it, "
                "asking for more time to review it), are not included.")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]
# proposta sem nenhuma tramitação cadastrada e que o SAPL diz que não está mais em tramitação: não dá para saber o que houve
SEM_ANDAMENTO = ("A Câmara não registrou o andamento desta proposta no SAPL",
                 "The City Council did not record this bill's progress in SAPL")

# autor que é a prefeitura (tipo de autor, nome ou cargo, sem acento e em minúsculas)
_EXECUTIVO = re.compile(r"\bexecutivo\b|\bprefeit[oa]s?\b|\bprefeitura\b")
_NAO_EXECUTIVO = re.compile(r"vice[- ]?prefeit|ex[- ]?prefeit|assessor|secretari|\bcamara\b|legislativ|vereador|parlamentar|comiss|"
                            r"\bmesa\b|bancada|\bbloco\b|\bfrente\b|\bcidada[os]?\b|cidadania|popular|sindicat|associa|tribunal|"
                            r"ministerio|defensoria|estadual|federal|governador|governo do estado")


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


def tipo_de_veto(descricao: str | None) -> bool:
    """Tipo de matéria que é a mensagem de veto do prefeito ("Veto", "Razões do Veto", "Veto Total ou Parcial"...)."""
    d = B.norm(descricao)
    return bool(re.match(r"((razoes|mensagem|oficio) d[eo] )?vetos?\b|veto (total|parcial)", d)) and "parecer" not in d


def status_de_veto(descricao: str | None) -> bool:
    """Situação de tramitação que só aparece quando houve veto ("Proposição com veto total", "Veto lido em sessão",
    "Transformada em lei com veto parcial"...). Fora: "Aguardando sanção ou veto", "prazo para sanção/veto", "sem veto"."""
    t = B.norm(descricao)
    if not re.search(r"\bvet", t):
        return False
    return not re.search(r"sancao\s*(ou|/|e|,)\s*(o |a )?vet|prazo\s*(de|para)\s*(a |o )?(sancao|vet)|sem vet|nao (foi )?vetad|"
                         r"nao houve vet|aguardando (a )?(sancao|prazo)", t)


def voto_normal(voto: str | None) -> str:
    """O voto como o perfil entende (os mesmos códigos do Congresso): Sim, Não, Abstenção, NR (não votou), NCom (ausente),
    PS (presidia). Outro texto fica como a Câmara escreveu."""
    t = B.norm(voto)
    if t in ("sim", "favoravel", "a favor"):
        return "Sim"
    if t in ("nao", "contrario", "contra"):
        return "Não"
    if t.startswith("absten"):
        return "Abstenção"
    if t.startswith("nao vot") or t in ("nao registrou voto", "nr"):
        return "NR"
    if t.startswith("ausen"):
        return "NCom"
    if t.startswith("presid"):
        return "PS"
    return (voto or "").strip() or "NR"


def eh_lei(t: dict) -> bool:
    """Tipo de norma jurídica que é lei ordinária ou complementar (pelo código LexML do tipo ou pela descrição)."""
    d = B.norm(t.get("descricao"))
    lex = (t.get("equivalente_lexml") or "").strip().lower()
    if re.search(r"organica|regimento|decreto|resolu|emenda|portaria|ato\b|veto", d):
        return False
    if lex in ("lei", "lei.complementar"):
        return "lei" in d
    return bool(re.fullmatch(r"leis?( (ordinarias?|complementar(es)?|municipa(l|is)|promulgadas?))*", d))


def data_pt(d: str) -> str:
    a = dt.date.fromisoformat(d[:10])
    return f"{'1º' if a.day == 1 else a.day}/{a.month}/{a.year}"


def data_en(d: str) -> str:
    a = dt.date.fromisoformat(d[:10])
    return f"{MONTHS[a.month - 1]} {a.day}, {a.year}"


def _numero(n) -> int | None:
    s = str(n or "").strip()
    if not re.fullmatch(r"\d{1,3}(\.\d{3})*|\d+", s):
        return None
    return int(s.replace(".", ""))


def _email_oficial(e: str | None) -> str | None:
    """Só e-mails da própria Câmara ou do governo (.leg.br, .gov.br): nada de endereço pessoal no site."""
    e = (e or "").strip().lower()
    return e if re.fullmatch(r"[\w.+-]+@[\w.-]+\.(leg|gov)\.br", e) else None


def _prazo() -> float | None:
    """Fim do tempo desta rodada (scripts/legislativos.py --minutos), em segundos desde 1970."""
    try:
        return float(os.environ.get("LEGISLATIVOS_PRAZO") or 0) or None
    except ValueError:
        return None


# erro de conexão (o nome do servidor não foi achado, a rede caiu, o servidor recusou a conexão): não é culpa de um lote
_SEM_CONEXAO = re.compile(r"getaddrinfo|name or service not known|temporary failure in name resolution|connection refused|"
                          r"network is unreachable|no route to host|\[(WinError|Errno) (10051|10061|10065|11001|11002|11004|"
                          r"-2|-3|-5|101|111|113)\]", re.I)


def sem_conexao(erro: BaseException | str) -> bool:
    return bool(_SEM_CONEXAO.search(str(erro)))


def _compacta_materia(m: dict) -> dict:
    return {k: m.get(k) for k in ("tipo", "numero", "ano", "data_apresentacao", "ementa", "em_tramitacao", "autores")}


def _compacta_norma(n: dict) -> dict:
    return {k: n.get(k) for k in ("tipo", "numero", "ano", "data", "materia", "esfera_federacao")}


class FiltroIgnorado(RuntimeError):
    """O SAPL (versão antiga) ignorou um filtro da API e devolveria a lista inteira."""


class MuitasPaginas(FiltroIgnorado):
    """A lista tem mais páginas do que o esperado (um filtro ignorado ou uma lista grande demais para pedir de uma vez)."""


class SemOrcamento(Exception):
    """Acabou o orçamento de pedidos (ou o tempo) desta cidade nesta rodada: o resto fica para a próxima."""


class Sapl:
    def __init__(self, ibge: str, uf: str, base: str, casa: str | None = None, casa_en: str | None = None,
                 sigla: str | None = None, site: str | None = None, prefixo: str | None = None,
                 tipos: dict[str, str | None] | None = None, regras: list | None = None, tse_manual: dict | None = None,
                 incluir: set | None = None, excluir: set | dict | None = None, pausa: float = 0.5, notas: list | None = None,
                 primeiro_por_ordem: bool = True, fotos_locais: bool | None = None, sem_lista_se_falhar: bool = False,
                 vagas: tuple[int, int] | None = None, prefeito: bool = True, orcamento: int | None = None,
                 nota_gastos: tuple[str, str] | None = None):
        """tipos = {sigla oficial do tipo: tipo comum ou None} para corrigir a escolha automática pela descrição;
        regras = [(expressão, status, chave de _base.TXT ou None)] próprias da Câmara (vêm antes das comuns);
        tse_manual = {id do parlamentar no SAPL: SQ do TSE ou "-"} conferidos à mão;
        incluir = ids do SAPL que estão no cargo mesmo sem "ativo"; excluir = {id: até quando (AAAA-MM-DD) ou None} para quem
        o SAPL marca como ativo mas está afastado (anote a fonte no arquivo da cidade);
        primeiro_por_ordem: quando a Câmara não marca o primeiro autor e há vários, vale o primeiro cadastrado;
        casa, casa_en, sigla, site, prefixo: None = tirados do próprio SAPL e do nome da cidade;
        pausa: intervalo mínimo entre pedidos (o do robots.txt vale quando é maior);
        fotos_locais: guarda a foto reduzida em img/pessoas/ (None = só nas capitais);
        sem_lista_se_falhar: se a conferência de vagas falhar, segue sem a lista oficial (senão, para com erro);
        vagas = (mínimo, máximo) aceitos na conferência, quando conferido à mão (padrão: exatamente as vagas; capitais
        sem_lista_se_falhar=False: de 80% das vagas até as vagas + 1, como na primeira rodada);
        prefeito: junta os projetos da prefeitura e as leis e vetos do mandato (pref-<IBGE>);
        orcamento: pedidos nesta rodada (padrão ORCAMENTO);
        nota_gastos: (pt, en) no lugar da nota padrão sobre os gastos do mandato (o SAPL não tem), quando a Câmara os publica
        em outro lugar."""
        self.ibge, self.uf, self.base = ibge, uf, base.rstrip("/")
        self.nota_gastos = tuple(nota_gastos) if nota_gastos else None
        self.casa, self.casa_en, self.sigla, self.site = casa, casa_en, sigla, site
        self.prefixo = prefixo or f"cm{ibge}"
        self.tipos_fixos = tipos or {}
        self.regras = [tuple(r) for r in (regras or [])]
        self.tse_manual = tse_manual or {}
        self.incluir = set(incluir or ())
        # excluir: {id: até quando (AAAA-MM-DD) ou None}; um conjunto vale "para sempre"
        self.excluir = dict(excluir) if isinstance(excluir, dict) else {i: None for i in (excluir or ())}
        self.pausa = pausa
        self.notas_casa = [tuple(n) for n in (notas or [])]
        self.primeiro_por_ordem = primeiro_por_ordem
        self.fotos_locais = (ibge in B.CAPITAIS) if fotos_locais is None else fotos_locais
        self.sem_lista_se_falhar = sem_lista_se_falhar
        self.faixa_vagas = tuple(vagas) if vagas else None
        self.com_prefeito = prefeito
        self.orcamento = orcamento or ORCAMENTO
        self.pasta = B.PASTA_CACHE / ibge
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.n_req = 0
        self.filtro_exato = False  # o SAPL desta Câmara ignora os filtros "__in"/"__gte" das matérias (versão antiga)

    # ------------------------------------------------------------ rede: robots.txt, intervalo, orçamento, cache
    def url(self, caminho: str, params: dict | None = None) -> str:
        q = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None}, safe=",")
        return f"{self.base}{caminho}" + (f"?{q}" if q else "")

    def _pode_pedir(self, intervalo: float) -> None:
        """SemOrcamento se acabou o orçamento de pedidos desta cidade ou se o próximo pedido passaria do fim da rodada."""
        if self.n_req >= self.orcamento:
            raise SemOrcamento(f"{self.n_req} pedidos")
        prazo = _prazo()
        if prazo and time.time() + intervalo + 60 > prazo:
            raise SemOrcamento("fim do tempo da rodada")

    def _conta_foto(self) -> None:
        """Uma foto nova a baixar (capitais) também é um pedido ao servidor: conta no orçamento e respeita o prazo."""
        self._pode_pedir(max(self.pausa, B.robots(self.base).atraso))
        self.n_req += 1

    def get(self, caminho: str, params: dict | None = None, cache: str | None = None, idade_h: float | None = 20):
        arq = self.pasta / "http" / f"{cache}.json" if cache else None
        if arq and arq.exists() and (idade_h is None or (time.time() - arq.stat().st_mtime) / 3600 < idade_h):
            return json.loads(arq.read_text(encoding="utf-8"))
        url = self.url(caminho, params)
        self._pode_pedir(self.pausa)  # antes até do robots.txt: sem orçamento ou sem tempo, nada é pedido
        regras = B.robots(self.base)  # uma vez por rodada; 5xx ou sem resposta = RuntimeError (nada é lido)
        intervalo = max(self.pausa, regras.atraso)
        erro = None
        for tentativa in range(2):
            self._pode_pedir(intervalo)
            B.esperar_vez(url, self.pausa)  # confere o Disallow e espera o intervalo do servidor
            try:
                bruto = baixar(url, tentativas=1, timeout=120, headers={"Accept": "application/json"})
                erro = None
                break
            except RuntimeError as e:
                erro = e
                codigo = re.search(r"HTTP Error (\d{3})", str(e))
                if codigo and codigo.group(1) in ("429", "503"):
                    raise RuntimeError(f"o servidor pediu para esperar (HTTP {codigo.group(1)}); fica para a próxima rodada")
                if codigo and codigo.group(1).startswith("4"):
                    break  # 4xx: não adianta tentar de novo
            finally:
                self.n_req += 1
                B.pedido_feito(url)
                if LOG_PEDIDOS:  # para medir quais etapas gastam pedidos
                    p = {k: (v if len(str(v)) <= 24 else f"{str(v)[:20]}…") for k, v in (params or {}).items() if k != "page_size"}
                    log(f"    {self.ibge} pedido {self.n_req}: {caminho} {p} {cache or ''}")
        if erro:
            raise erro
        d = json.loads(bruto.decode("utf-8"))
        if arq:
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d

    def todos(self, caminho: str, params: dict | None = None, cache: str | None = None, idade_h: float | None = 20,
              max_paginas: int | None = None, checar=None) -> list:
        """Todas as páginas de uma lista da API (100 por página). max_paginas e checar (função aplicada aos itens da
        primeira página) protegem contra um SAPL antigo que ignora um filtro e devolveria a lista inteira."""
        out, pagina = [], 1
        while True:
            p = dict(params or {}, page=pagina, page_size=LOTE)
            d = self.get(caminho, p, cache=f"{cache}-p{pagina}" if cache else None, idade_h=idade_h)
            if isinstance(d, list):  # algumas ações antigas não paginam
                return d
            res = d.get("results") or []
            pag = d.get("pagination") or {}
            if pagina == 1:  # primeiro o filtro (SAPL antigo que ignora o filtro), depois o tamanho da lista
                if checar and not all(checar(x) for x in res):
                    raise FiltroIgnorado(f"{caminho}: o SAPL ignorou o filtro {params}")
                if max_paginas and (pag.get("total_pages") or 1) > max_paginas:
                    raise MuitasPaginas(f"{caminho} {params}: {pag.get('total_pages')} páginas (filtro ignorado?)")
            out += res
            if pagina >= (pag.get("total_pages") or 1):
                return out
            pagina += 1

    def por_lotes(self, caminho: str, campo: str, ids: list[int], extra: dict | None = None, cache: str | None = None) -> list:
        """Busca por lotes de ids (campo__in=1,2,3). Se um id sumiu do SAPL (o servidor responde erro 500), divide o lote.
        Erro de conexão (sem_conexao: a rede caiu, o servidor não foi achado) não divide o lote: a cidade fica para a
        próxima rodada (dividir só gastaria pedidos e deixaria propostas sem andamento, marcadas como conferidas).
        SAPL antigo que ignora "__in" (ex.: 3.1.162): um id por vez (campo=id). cache: as páginas de cada lote ficam
        guardadas por 2 dias (uma rodada que parou no meio continua sem pedir de novo)."""
        out = []
        for i in range(0, len(ids), LOTE):
            try:
                out += self._lote(caminho, campo, ids[i:i + LOTE], extra, cache)
            except FiltroIgnorado:
                log(f"  {self.sigla} {self.ibge}: o SAPL não filtra {campo}__in em {caminho}: um por vez ({len(ids) - i} pedidos)")
                for x in ids[i:]:
                    out += self.todos(caminho, dict(extra or {}, **{campo: x}), max_paginas=30,
                                      cache=f"{cache}-{campo}{x}" if cache else None, idade_h=48,
                                      checar=lambda r, x=x: r.get(campo) == x)
                break
        return out

    def _lote(self, caminho, campo, lote, extra, cache=None):
        pedidos = set(lote)
        nome = f"{cache}-{hashlib.sha1(','.join(map(str, lote)).encode()).hexdigest()[:12]}" if cache else None
        try:
            return self.todos(caminho, dict(extra or {}, **{f"{campo}__in": ",".join(map(str, lote))}), cache=nome, idade_h=48,
                              checar=lambda x: x.get(campo) in pedidos)
        except FiltroIgnorado:
            raise
        except RuntimeError as erro:
            if sem_conexao(erro):
                raise
            if len(lote) == 1:
                log(f"  {self.sigla}: {campo}={lote[0]} não respondeu; fica sem")
                return []
            meio = len(lote) // 2
            return self._lote(caminho, campo, lote[:meio], extra, cache) + self._lote(caminho, campo, lote[meio:], extra, cache)

    # ------------------------------------------------------------ a Câmara (nome, sigla, site)
    def identificar(self) -> None:
        """Completa nome, sigla e site da Câmara com o cadastro do próprio SAPL (/api/base/casalegislativa/) e o nome da
        cidade (dados/cidades/<UF>/<IBGE>.json)."""
        if self.casa and self.casa_en and self.sigla and self.site:
            return
        nome_cidade = B.cidade(self.ibge, self.uf).get("nome") or ""
        try:
            c = (self.todos("/api/base/casalegislativa/", cache="casa", idade_h=FIXO_H) or [{}])[0]
        except FiltroIgnorado:
            c = {}
        except RuntimeError as erro:
            if "HTTP Error 404" not in str(erro):
                raise
            c = {}
        if not self.casa:
            n = re.sub(r"\s+", " ", (c.get("nome") or "").strip())
            if n.isupper():
                n = nome_proprio(n)
                n = re.sub(r"\b(De|Do|Da|Dos|Das|E)\b", lambda m: m.group(1).lower(), n)
            n = re.sub(r"^c[aâ]mara\b", "Câmara", n, flags=re.I)  # "Camara Municipal de ..." sem o acento
            ok = re.match(r"c[aâ]mara (municipal|de vereadores)\b", n, re.I) and B.norm(n).endswith(B.norm(nome_cidade))
            if ok and nome_cidade:
                n = n[:len(n) - len(nome_cidade)] + nome_cidade  # o nome da cidade com os acentos certos
            self.casa = n if ok else f"Câmara Municipal de {nome_cidade}"
        if not self.casa_en:
            self.casa_en = f"{nome_cidade} City Council"
        if not self.sigla:
            s = re.sub(r"[^A-Za-z]", "", c.get("sigla") or "")
            self.sigla = s.upper() if 2 <= len(s) <= 8 else "CM"
        if not self.site:
            w = (c.get("endereco_web") or "").strip()
            if w and not w.startswith("http"):
                w = "https://" + w
            host = urllib.parse.urlparse(w).hostname or ""
            self.site = re.sub(r"^http://", "https://", w.rstrip("/")) if re.search(r"\.(leg|gov)\.br$", host) else self.base

    # ------------------------------------------------------------ quem está no cargo
    def legislatura_atual(self) -> dict:
        legs = self.todos("/api/parlamentares/legislatura/", cache="legislaturas", idade_h=SEMANA_H)
        h = hoje()
        atuais = [l for l in legs if (l.get("data_inicio") or "") <= h <= (l.get("data_fim") or "")]
        if not atuais:
            legs = self.todos("/api/parlamentares/legislatura/", cache="legislaturas", idade_h=0)  # começou uma nova?
            atuais = [l for l in legs if (l.get("data_inicio") or "") <= h <= (l.get("data_fim") or "")]
        if not atuais:
            raise RuntimeError("o SAPL não tem a legislatura atual cadastrada")
        return max(atuais, key=lambda l: l["data_inicio"])

    def parlamentar(self, pid: int) -> dict:
        if not hasattr(self, "_ativos"):  # quase todos estão aqui (uma ou duas páginas); os outros vêm um por um
            self._ativos = {p["id"]: p for p in self.todos("/api/parlamentares/parlamentar/", {"ativo": "True"},
                                                           cache="parlamentares-ativos", idade_h=FIXO_H)}
        return self._ativos.get(pid) or self.get(f"/api/parlamentares/parlamentar/{pid}/", cache=f"parlamentar-{pid}",
                                                 idade_h=FIXO_H)

    def membros(self, e: dict) -> tuple[list[dict], dict, dict]:
        """(pessoas no cargo hoje, legislatura, {id SAPL: dados do SAPL} de todos com mandato nesta legislatura).
        Os mandatos só são pedidos de novo quando muda quem está ativo (ou depois de 30 dias)."""
        leg = self.legislatura_atual()
        L = leg["id"]
        try:
            vinc = self.todos(f"/api/parlamentares/legislatura/{L}/parlamentares/", cache=f"leg{L}-parlamentares", idade_h=12)
        except FiltroIgnorado:
            vinc = []
        except RuntimeError as erro:
            if "HTTP Error 404" not in str(erro):
                raise
            vinc = []  # SAPL antigo, sem a ação .../parlamentares/
        ativos = sorted(v["id"] for v in vinc if v.get("ativo"))
        mudou = ativos != e.get("ativos")
        mandatos = self.todos("/api/parlamentares/mandato/", {"legislatura": L}, cache=f"leg{L}-mandatos",
                              idade_h=0 if mudou else FIXO_H)
        e["ativos"] = ativos
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
                fil = self.todos("/api/parlamentares/filiacao/", {"parlamentar": pid}, cache=f"filiacao-{pid}", idade_h=SEMANA_H)
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
            v["mandato_hoje"] = max(cobre, key=lambda m: m.get("data_inicio_mandato") or "") if cobre else None
            if (ok or pid in self.incluir) and not fora:
                no_cargo.append(v)
        return no_cargo, leg, por_id

    def partidos(self) -> dict:
        if not hasattr(self, "_partidos"):
            self._partidos = {p["id"]: p.get("sigla") for p in self.todos("/api/parlamentares/partido/", cache="partidos",
                                                                          idade_h=FIXO_H)}
        return self._partidos

    def fichas(self, pessoas: list[dict], tse: B.Tse) -> tuple[list[dict], dict]:
        """Ficha de cada pessoa (contrato da lista oficial) + {id SAPL: (ficha, cadastro, vínculo)}."""
        modelo = None if self.fotos_locais else B.modelo_foto_tse(self.ibge, self.uf)
        membros, por_pid = [], {}
        for v in pessoas:
            d = self.parlamentar(v["id"])
            nome = B.nome_limpo(v.get("nome_parlamentar") or d.get("nome_parlamentar"))
            if not nome:
                continue
            civil = B.nome_limpo(d.get("nome_completo")) if d.get("nome_completo") else None
            sigla_p = B.partido(v.get("partido"))
            pid, cand = tse.casar(v["id"], [nome, civil], sigla_p)
            foto = (v.get("fotografia") or d.get("fotografia") or None)
            if foto and self.base.startswith("https://"):
                foto = re.sub(r"^http://", "https://", foto)
            if self.fotos_locais:
                foto = B.foto(foto, pid, self.ibge, antes_de_baixar=self._conta_foto)
            elif cand and cand.get("sit", "").startswith("ELEITO"):
                foto = None  # a lista do TSE da cidade já tem a foto desta pessoa
            elif cand and modelo:
                foto = modelo.format(sq=cand["sq"])  # suplente: a foto da candidatura no TSE
            else:
                foto = None  # sem ligação com o TSE: sem foto (a do SAPL seria mais um pedido e pode ter vários MB)
            # suplente = não foi eleito(a) titular em 2024 (TSE), mesmo que tenha assumido a vaga de vez; sem o TSE, vale o SAPL
            supl = (cand or {}).get("sit") == "SUPLENTE" if cand else not v.get("titular")
            m = {"id": pid, "nome": nome, "nomeCivil": civil if civil and sem_acento(civil).lower() != sem_acento(nome).lower() else None,
                 "partido": sigla_p, "genero": (d.get("sexo") or "")[:1].upper() or (cand or {}).get("genero"),
                 "foto": foto, "url": f"{self.base}/parlamentar/{v['id']}",
                 "exercicio": "Suplente em exercício" if supl else None, "exercicio_en": "Substitute in office" if supl else None}
            if m["genero"] not in ("F", "M"):
                m["genero"] = None
            m["_cand"] = cand
            membros.append(m)
            por_pid[v["id"]] = (m, d, v)
        return membros, por_pid

    def conferir(self, membros: list[dict], tse: B.Tse) -> str | None:
        """None se a lista oficial bate com as vagas; senão, o motivo."""
        vagas = tse.vagas
        if not vagas:
            return "não achei as vagas da cidade no TSE"
        if self.faixa_vagas:
            lo, hi = self.faixa_vagas
        elif self.sem_lista_se_falhar:
            lo = hi = vagas
        else:
            lo, hi = 0.8 * vagas, vagas + 1
        if not (lo <= len(membros) <= hi):
            return f"o SAPL tem {len(membros)} vereadores ativos para {vagas} vagas"
        ligados = sum(1 for m in membros if m.get("_cand"))
        if self.sem_lista_se_falhar and ligados < 0.7 * len(membros):
            return f"só {ligados} dos {len(membros)} vereadores ativos no SAPL foram achados entre os candidatos de 2024 (TSE)"
        ids = [m["id"] for m in membros]
        if len(set(ids)) != len(ids):
            return f"duas pessoas com o mesmo id: {sorted(i for i in ids if ids.count(i) > 1)}"
        return None

    # ------------------------------------------------------------ tipos e situações (quase não mudam)
    def tipos_materia(self) -> list[dict]:
        return self.todos("/api/materia/tipomaterialegislativa/", cache="tipos", idade_h=FIXO_H)

    def tipos(self) -> dict[int, tuple[str, str, str]]:
        """{id do tipo: (tipo comum, sigla oficial, descrição)} só dos tipos que são propostas."""
        out = {}
        for t in self.tipos_materia():
            sig = (t.get("sigla") or "").strip()
            comum = self.tipos_fixos[sig] if sig in self.tipos_fixos else tipo_por_descricao(sig, t.get("descricao"))
            if comum:
                out[t["id"]] = (comum, sig, t.get("descricao") or "")
        return out

    def tipos_veto(self) -> set[int]:
        return {t["id"] for t in self.tipos_materia() if tipo_de_veto(t.get("descricao"))}

    def status_tramitacao(self, novo: bool = False) -> dict[int, str]:
        return {s["id"]: s.get("descricao") for s in self.todos("/api/materia/statustramitacao/", cache="status",
                                                                 idade_h=0 if novo else SEMANA_H)}

    def tipos_norma(self) -> dict[int, dict]:
        return {t["id"]: t for t in self.todos("/api/norma/tiponormajuridica/", cache="tipos-norma", idade_h=FIXO_H)}

    def tipos_autor(self) -> list[dict]:
        return self.todos("/api/base/tipoautor/", cache="tipos-autor", idade_h=FIXO_H)

    # ------------------------------------------------------------ estado guardado (o que já foi lido)
    def estado(self) -> dict:
        e = ler_json(self.pasta / "estado.json", {}) or {}
        for k in ("ultima", "autoria", "verif", "mats", "normas", "vetos"):
            e.setdefault(k, {})
        return e

    def guardar_estado(self, e: dict) -> None:
        salvar_json(self.pasta / "estado.json", e)

    # ------------------------------------------------------------ matérias (a lista inteira uma vez; depois, o que mudou)
    def materias(self, tipos: set[int], inicio: str, max_paginas: int = 150, cache: str | None = None,
                 idade_h: float = 48, exato: bool = False) -> list[dict]:
        """Matérias destes tipos apresentadas desde `inicio`. Algumas versões do SAPL (ex.: 3.1.165-RC2) ignoram tipo__in e
        data_apresentacao__gte nesta lista, mas filtram por tipo e ano exatos: aí vai um tipo e um ano por vez (exato=True:
        direto assim, quando já se sabe que o SAPL desta Câmara é desses; self.filtro_exato fica True quando foi preciso)."""
        if not tipos:
            return []
        h = hoje()
        try:
            if exato:
                raise FiltroIgnorado("filtros exatos")
            return self.todos(MAT, {"tipo__in": ",".join(map(str, sorted(tipos))), "data_apresentacao__gte": inicio},
                              max_paginas=max_paginas, cache=cache, idade_h=idade_h,
                              checar=lambda m: m.get("tipo") in tipos and (m.get("data_apresentacao") or "") >= inicio)
        except FiltroIgnorado as erro:
            if not isinstance(erro, MuitasPaginas):
                self.filtro_exato = True
            out = []
            for t in sorted(tipos):
                for ano in range(int(inicio[:4]), int(h[:4]) + 1):
                    out += self.todos(MAT, {"tipo": t, "ano": ano}, max_paginas=max_paginas,
                                      cache=f"{cache}-t{t}-a{ano}" if cache else None, idade_h=idade_h,
                                      checar=lambda m, t=t, ano=ano: m.get("tipo") == t and m.get("ano") == ano)
            return [m for m in out if (m.get("data_apresentacao") or "") >= inicio]

    def atualizar_materias(self, e: dict, tipos: set[int]) -> dict[str, dict]:
        """e["mats"] = {id: matéria (campos que o site usa)} dos tipos pedidos, desde 1º/1/2025. A primeira vez (e a cada
        LISTA_COMPLETA_DIAS), a lista inteira: numa cidade grande ela leva mais de uma rodada (as páginas lidas ficam
        guardadas por uma semana e a rodada seguinte continua dali). Nas outras rodadas, só as matérias alteradas desde a
        última vez (data_ultima_atualizacao__gte); SAPL antigo, sem esse filtro: só as matérias do ano, por tipo e ano."""
        h = hoje()
        desde = e.get("desde_mat")
        velha = (e.get("mats_lista_em") or "") < _menos_dias(h, LISTA_COMPLETA_DIAS)
        if not e["mats"] or not desde or velha or sorted(tipos) != e.get("mats_tipos"):
            ini = e.setdefault("mats_lista_ini", h)  # "o que mudou" vai contar a partir do dia em que a lista começou
            self.filtro_exato = False
            lista = self.materias(tipos, B.INICIO, cache="mats-lista", idade_h=SEMANA_H, exato=bool(e.get("mats_exato")))
            e["mats"] = {str(m["id"]): _compacta_materia(m) for m in lista}
            e.pop("mats_lista_ini", None)
            e.update(desde_mat=min(ini, h), mats_lista_em=h, mats_tipos=sorted(tipos), mats_exato=self.filtro_exato)
            return e["mats"]
        ini = _menos_dias(desde, FOLGA_DIAS)
        try:
            if e.get("mats_exato"):
                raise FiltroIgnorado("filtros exatos")
            novos = self.todos(MAT, {"tipo__in": ",".join(map(str, sorted(tipos))), "data_ultima_atualizacao__gte": ini},
                               max_paginas=60, checar=lambda m: m.get("tipo") in tipos
                               and str(m.get("data_ultima_atualizacao") or "")[:10] >= ini)
        except MuitasPaginas:  # mudou muita coisa de uma vez (ex.: a Câmara recadastrou as matérias): a lista inteira de novo
            e["mats_lista_em"] = ""
            return self.atualizar_materias(e, tipos)
        except FiltroIgnorado:
            # SAPL antigo: as matérias apresentadas desde o começo do ano de `ini` (por tipo e ano exatos: poucas páginas);
            # as dos anos anteriores quase não mudam (a situação vem das tramitações) e voltam com a lista inteira, que é
            # pedida de novo a cada LISTA_COMPLETA_DIAS
            e["mats_exato"] = True
            novos = self.materias(tipos, max(B.INICIO, f"{ini[:4]}-01-01"), cache="mats-ano", idade_h=20, exato=True)
        for m in novos:
            if (m.get("data_apresentacao") or "") >= B.INICIO:
                e["mats"][str(m["id"])] = _compacta_materia(m)
        e["desde_mat"] = h
        return e["mats"]

    # ------------------------------------------------------------ autoria e tramitações
    def autorias(self, e: dict, mats: dict[str, dict]) -> None:
        faltam = [int(mid) for mid, m in mats.items()
                  if (e["autoria"].get(mid) or {}).get("a") != sorted(m.get("autores") or [])]
        if not faltam:
            return
        log(f"  {self.sigla} {self.ibge}: autoria de {len(faltam)} propostas")
        for i in range(0, len(faltam), LOTE):
            lote = faltam[i:i + LOTE]
            rows = self.por_lotes("/api/materia/autoria/", "materia", lote, cache="aut")
            por: dict[str, list] = {str(m): [] for m in lote}
            for r in rows:
                por.setdefault(str(r["materia"]), []).append([r["autor"], bool(r.get("primeiro_autor")), r["id"]])
            for mid, lst in por.items():
                if mid in mats:
                    e["autoria"][mid] = {"a": sorted(mats[mid].get("autores") or []), "r": sorted(lst, key=lambda x: x[2])}
            self.guardar_estado(e)

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

    @staticmethod
    def _vetos_do_fluxo(e: dict, trams: list[dict], st_veto: set) -> None:
        """e["vetos"] = {id da matéria: data da primeira situação de veto vista} (qualquer matéria)."""
        for t in trams:
            d = (t.get("data_tramitacao") or "")[:10]
            if t.get("status") in st_veto and d and t.get("materia"):
                k = str(t["materia"])
                e["vetos"][k] = min(e["vetos"].get(k, d), d)

    def tramitacoes(self, e: dict, mats: dict[str, dict], status_txt: dict, st_veto: set) -> None:
        """1) o que mudou desde a última rodada (todas as matérias: também serve para os vetos); 2) o histórico inteiro das
        propostas novas, em lotes de 100 (cada lote fica guardado: se o orçamento acabar, a próxima rodada continua);
        3) com sobra de orçamento, a revisão de um lote antigo (pega tramitação apagada ou corrigida)."""
        h = hoje()
        if not e.get("desde"):
            e["desde"] = h  # as mudanças a partir de hoje vêm pelo filtro de edição nas próximas rodadas
        elif e["desde"] < h:
            ini = _menos_dias(e["desde"], FOLGA_DIAS)
            trams = None
            campos = [e["campo_incremental"]] if e.get("campo_incremental") else ["ultima_edicao", "timestamp", "data_tramitacao"]
            for campo in campos:
                try:
                    trams = self.todos(TRAM, {f"{campo}__gte": ini}, max_paginas=80,
                                       checar=lambda t, c=campo: str(t.get(c) or "")[:10] >= ini)
                    e["campo_incremental"] = campo
                    break
                except FiltroIgnorado:
                    continue
            if trams is None:
                log(f"  {self.sigla} {self.ibge}: o SAPL não filtra as tramitações por data de edição; só a revisão completa")
                e.pop("campo_incremental", None)
            else:
                if any(t.get("status") not in status_txt for t in trams):
                    status_txt.update(self.status_tramitacao(novo=True))
                    st_veto |= {k for k, d in status_txt.items() if status_de_veto(d)}
                self._aplicar_tramitacoes(e, [t for t in trams if str(t["materia"]) in mats], status_txt, set())
                self._vetos_do_fluxo(e, trams, st_veto)
            e["desde"] = h
            self.guardar_estado(e)
        novos = [int(m) for m in mats if m not in e["ultima"]]
        if novos:
            log(f"  {self.sigla} {self.ibge}: histórico completo de {len(novos)} propostas")
        lotes = [novos[i:i + LOTE] for i in range(0, len(novos), LOTE)]
        if self.orcamento - self.n_req >= 20 or not e.get("campo_incremental"):
            vencidos = sorted((m for m in mats if m in e["ultima"] and (e["verif"].get(m) or "") < _menos_dias(h, REVISAR_DIAS)),
                              key=lambda m: e["verif"].get(m) or "")
            if vencidos:
                lotes.append([int(m) for m in vencidos[:LOTE]])
        for lote in lotes:
            trams = self.por_lotes(TRAM, "materia", lote, cache="hist")
            self._aplicar_tramitacoes(e, trams, status_txt, {str(m) for m in lote})
            self._vetos_do_fluxo(e, trams, st_veto)
            for m in lote:
                e["verif"][str(m)] = h
            self.guardar_estado(e)

    # ------------------------------------------------------------ normas (a lista inteira uma vez; depois, o que mudou)
    def normas_de(self, params_in: dict, tipos: set[int] | None, desde_ano: int, checar_extra=None, max_paginas: int = 60,
                  cache: str | None = None, idade_h: float = 48) -> list:
        """Normas jurídicas com filtros "__in"/"__gte"; se o SAPL ignorar, um tipo e um ano exatos por vez."""
        def ok(n):
            return (tipos is None or n.get("tipo") in tipos) and (n.get("ano") or 0) >= desde_ano and (checar_extra is None or checar_extra(n))
        try:
            return self.todos(NORMA, params_in, max_paginas=max_paginas, checar=ok, cache=cache, idade_h=idade_h)
        except FiltroIgnorado:
            out = []
            for t in (sorted(tipos) if tipos is not None else [None]):
                for ano in range(desde_ano, int(hoje()[:4]) + 1):
                    p = {"ano": ano} if t is None else {"tipo": t, "ano": ano}
                    out += self.todos(NORMA, p, max_paginas=max_paginas, cache=f"{cache}-t{t}-a{ano}" if cache else None,
                                      idade_h=idade_h, checar=lambda n, t=t, ano=ano: n.get("ano") == ano and (t is None or n.get("tipo") == t))
            return [n for n in out if ok(n)]

    def atualizar_normas(self, e: dict) -> dict[str, dict]:
        """e["normas"] = {id: norma} de 2025 em diante (todas: servem para "virou lei" e para contar as leis do mandato).
        A primeira vez (e a cada LISTA_COMPLETA_DIAS), a lista inteira (as páginas ficam guardadas por uma semana, para uma
        carga de várias rodadas continuar dali); depois, só o que mudou (o campo de data de edição que o SAPL aceitar fica
        guardado em e["campo_norma"]); SAPL antigo, sem esse filtro: só as normas do ano. As normas vêm desde o ano anterior
        ao mandato (NORMAS_DESDE_ANO): a última lei de antes diz onde a numeração do período tem de começar."""
        h = hoje()
        desde = e.get("desde_norma")
        velha = (e.get("normas_lista_em") or "") < _menos_dias(h, LISTA_COMPLETA_DIAS)
        if not desde or velha or e.get("normas_ano") != NORMAS_DESDE_ANO:
            ini = e.setdefault("normas_lista_ini", h)
            lista = self.normas_de({"ano__gte": NORMAS_DESDE_ANO}, None, NORMAS_DESDE_ANO, max_paginas=200,
                                   cache=f"normas-lista-{NORMAS_DESDE_ANO}", idade_h=SEMANA_H)
            e["normas"] = {str(n["id"]): _compacta_norma(n) for n in lista}
            e.pop("normas_lista_ini", None)
            e.update(desde_norma=min(ini, h), normas_lista_em=h, normas_ano=NORMAS_DESDE_ANO)
            return e["normas"]
        ini = _menos_dias(desde, FOLGA_DIAS)
        novos = None
        campos = [e["campo_norma"]] if e.get("campo_norma") else ([] if "campo_norma" in e else
                                                                  ["data_ultima_atualizacao", "ultima_edicao", "timestamp"])
        for campo in campos:
            try:
                novos = self.todos(NORMA, {f"{campo}__gte": ini}, max_paginas=30,
                                   checar=lambda n, c=campo: str(n.get(c) or "")[:10] >= ini)
                e["campo_norma"] = campo
                break
            except MuitasPaginas:  # mudou muita coisa de uma vez: a lista inteira de novo
                e["normas_lista_em"] = ""
                return self.atualizar_normas(e)
            except FiltroIgnorado:
                continue
        if novos is None:  # SAPL antigo: as normas do ano de `ini` em diante (por ano exato: poucas páginas)
            e["campo_norma"] = ""
            ano = max(NORMAS_DESDE_ANO, int(ini[:4]))
            novos = self.normas_de({"ano__gte": ano}, None, ano, max_paginas=60, cache="normas-ano", idade_h=20)
        for n in novos:
            if (n.get("ano") or 0) >= NORMAS_DESDE_ANO:
                e["normas"][str(n["id"])] = _compacta_norma(n)
        e["desde_norma"] = h
        return e["normas"]

    def normas(self, e: dict) -> dict[str, dict]:
        """{id da matéria: norma} das normas de 2025 em diante ligadas a uma matéria."""
        tipos = {k: t.get("descricao") or t.get("sigla") for k, t in self.tipos_norma().items()}
        out = {}
        for nid, n in e["normas"].items():
            if n.get("materia"):
                out[str(n["materia"])] = {"id": int(nid), "nome": B.nome_norma(tipos.get(n.get("tipo")), n.get("numero"), n.get("ano")),
                                          "data": n.get("data"), "tipo": tipos.get(n.get("tipo")) or ""}
        return out

    def vetos_iniciais(self, e: dict, st_veto: set) -> None:
        """Uma vez: as tramitações com situação de veto desde um ano antes do mandato (para saber a primeira vez que cada
        projeto foi vetado). Depois, os vetos novos vêm junto com as tramitações alteradas (tramitacoes())."""
        if e.get("vetos_ini") or not st_veto:
            return
        desde_v = _menos_dias(B.INICIO, 365)
        sv = set(st_veto)
        try:
            trams = self.todos(TRAM, {"status__in": ",".join(map(str, sorted(sv))), "data_tramitacao__gte": desde_v},
                               max_paginas=40, checar=lambda t: t.get("status") in sv, cache="vetos-ini", idade_h=48)
        except FiltroIgnorado:
            trams = []
            try:  # SAPL que não filtra por "__in": uma situação por vez
                for s in sorted(sv):
                    trams += self.todos(TRAM, {"status": s, "data_tramitacao__gte": desde_v}, max_paginas=40,
                                        cache=f"vetos-ini-s{s}", idade_h=48, checar=lambda t, s=s: t.get("status") == s)
            except FiltroIgnorado as erro:
                log(f"  {self.sigla} {self.ibge}: vetos pelo andamento: {erro}")
                e["vetos_ini"] = "sem filtro"
                return
        self._vetos_do_fluxo(e, trams, sv)
        e["vetos_ini"] = hoje()
        self.guardar_estado(e)

    # ------------------------------------------------------------ autores
    def _cts_parlamentar(self, ta: list[dict]) -> set:
        cts = set()
        try:
            cts = {c["id"] for c in self.todos("/api/contenttypes/contenttype/", {"app_label": "parlamentares", "model": "parlamentar"},
                                               cache="ct-parlamentar", idade_h=None) if c.get("model") == "parlamentar"}
        except FiltroIgnorado:
            pass
        except RuntimeError as erro:
            if "HTTP Error 404" not in str(erro):
                raise
        if not cts:
            cts = {t.get("content_type") for t in ta if t.get("content_type")
                   and re.fullmatch(r"(parlamentar(es)?|vereador(a|es)?|vereador\(a\))", sem_acento((t.get("descricao") or "").lower().strip()))}
        return cts

    def autores_por_tipo(self, novo: bool = False) -> dict[int, list[dict]]:
        """{id do tipo de autor: [autores]}: a lista inteira de autores (1 a 5 páginas na maioria das Câmaras, em vez de um
        pedido por tipo), guardada por 30 dias; novo=True pede de novo."""
        por: dict[int, list] = {}
        for a in self.todos("/api/base/autor/", cache="autores-todos", idade_h=0 if novo else FIXO_H, max_paginas=80):
            por.setdefault(a.get("tipo"), []).append(a)
        return por

    def autores(self, e: dict, mats: dict[str, dict]) -> tuple[dict[int, int], dict[int, str]]:
        """({id do autor: id do parlamentar} dos vereadores, {id do autor: nome} da prefeitura). Se alguma proposta tem um
        autor que não está na lista guardada (vereador ou suplente novo), a lista é pedida de novo (uma vez por rodada)."""
        ta = self.tipos_autor()
        cts = self._cts_parlamentar(ta)
        por_tipo = self.autores_por_tipo()
        conhecidos = {a["id"] for lst in por_tipo.values() for a in lst}
        usados = {r[0] for mid in mats for r in ((e["autoria"].get(mid) or {}).get("r") or [])}
        faltam = usados - conhecidos - set(e.get("autores_sumidos") or [])
        if faltam:  # vereador ou suplente novo: pede a lista de novo; quem continuar sumido não faz pedir de novo depois
            por_tipo = self.autores_por_tipo(novo=True)
            conhecidos = {a["id"] for lst in por_tipo.values() for a in lst}
            e["autores_sumidos"] = sorted(set(e.get("autores_sumidos") or []) | (faltam - conhecidos))
        parl, execu = {}, {}
        desc = {t["id"]: t for t in ta}
        for tid, lst in por_tipo.items():
            t = desc.get(tid) or {}
            if t.get("content_type") in cts and t.get("content_type"):
                for a in lst:
                    if a.get("object_id") and a.get("content_type") in cts:
                        parl[a["id"]] = a["object_id"]
                continue
            dt_ = B.norm(t.get("descricao"))
            if re.search(r"comiss|bancada|bloco|frente|parlamentar", dt_):
                continue  # grupos de vereadores
            tipo_exec = bool(_EXECUTIVO.search(dt_)) and not _NAO_EXECUTIVO.search(dt_)
            for a in lst:
                txt = B.norm(f"{a.get('nome') or ''} {a.get('cargo') or ''}")
                if _NAO_EXECUTIVO.search(txt):
                    continue
                if tipo_exec or _EXECUTIVO.search(txt):
                    execu[a["id"]] = re.sub(r"\s+", " ", a.get("nome") or a.get("__str__") or "").strip()
        return parl, execu

    def tipos_de(self, ids: list[int], parar: bool = False) -> dict[int, int]:
        """{id da matéria: id do tipo}, guardado para sempre em .cache/camaras/<IBGE>/tipos-materias.json (o tipo de uma
        matéria não muda). Pede 100 por vez (id__in); SAPL antigo que ignora o filtro: não pede uma por uma (custaria um
        minuto cada) e devolve só o que já sabe. Sem orçamento: guarda o que veio e para (parar=True: a cidade fica para a
        próxima rodada) ou devolve o que deu."""
        arq = self.pasta / "tipos-materias.json"
        mapa = ler_json(arq, {}) or {}
        faltam = [i for i in ids if str(i) not in mapa]
        sem_orcamento = None
        try:
            for i in range(0, len(faltam), LOTE):
                lote = faltam[i:i + LOTE]
                pedidos = set(lote)
                rows = self.todos(MAT, {"id__in": ",".join(map(str, lote))}, checar=lambda x: x.get("id") in pedidos)
                for r in rows:
                    mapa[str(r["id"])] = r.get("tipo")
        except FiltroIgnorado:
            for x in faltam:  # o que já veio, de rodadas antigas, um por um
                velho = self.pasta / "http" / f"materia-{x}.json"
                if velho.exists() and str(x) not in mapa:
                    mapa[str(x)] = json.loads(velho.read_text(encoding="utf-8")).get("tipo")
        except SemOrcamento as erro:
            sem_orcamento = erro
        if faltam:
            salvar_json(arq, mapa)
        if sem_orcamento and parar:
            raise sem_orcamento
        pedidos_todos = set(ids)
        return {int(k): v for k, v in mapa.items() if int(k) in pedidos_todos}

    def vetadas_fora(self, e: dict, todas: dict[str, dict]) -> list[int]:
        """Matérias com veto no andamento desde o começo da legislatura que não estão na lista guardada (projetos de antes
        de 2025 vetados no mandato, por exemplo): o tipo delas é pedido antes de publicar (Sapl.executivo)."""
        h = hoje()
        return sorted(int(m) for m, d in e["vetos"].items() if B.INICIO <= d <= h and m not in todas)

    # ------------------------------------------------------------ votações nominais (o voto de cada vereador)
    def tipos_votacao(self, tipos: dict, tipos_v: set[int]) -> set[int]:
        """Tipos de matéria cujas votações nominais entram: os projetos (tipos), os vetos e as emendas, substitutivos e
        redações finais (o texto dos projetos). Requerimentos, indicações, moções e outros documentos ficam fora: em muitas
        Câmaras quase tudo é votado no painel, e eles seriam a maior parte da lista."""
        extra = {t["id"] for t in self.tipos_materia() if re.search(r"\bemenda|substitutiv|redacao final", B.norm(t.get("descricao")))}
        return set(tipos) | set(tipos_v) | extra

    def tipos_resultado(self) -> dict[int, tuple[str, str | None]]:
        """{id: (nome, natureza)} dos tipos de resultado de votação ("A" = aprovado, "R" = rejeitado, "" = nenhum, como
        adiamento e pedido de vista; None = versão do SAPL sem esse campo)."""
        return {t["id"]: ((t.get("nome") or "").strip(), t.get("natureza")) for t in
                self.todos(TIPO_RES, cache="tipos-resultado", idade_h=FIXO_H)}

    @staticmethod
    def resultado_votacao(nome: str, natureza: str | None) -> str | None:
        """O resultado para o site, ou None se a votação não decidiu a matéria (adiamento, pedido de vista, resultado
        desconhecido). Vale o nome oficial ("Aprovado em 2ª votação", "Veto mantido"), sem a caixa alta; nome sem
        "aprovado"/"rejeitado" (como "Acatado"): o da natureza."""
        nome = re.sub(r"\s+", " ", nome or "").strip().rstrip(".").strip()
        if sum(c.isupper() for c in nome) > sum(c.islower() for c in nome):  # quase tudo em caixa alta
            nome = nome.lower()
        nome = nome[:1].upper() + nome[1:]
        n = B.norm(nome)
        sim, nao = r"aprovad|mantid|acatad|acolhid", r"rejeitad|reprovad|derrubad"
        if natureza is None:  # SAPL antigo: só pelo nome
            natureza = "A" if re.search(sim, n) and not re.search(nao, n) else "R" if re.search(nao, n) else ""
        if natureza not in ("A", "R"):
            return None
        if not re.search(sim if natureza == "A" else nao, n):
            return "Aprovado" if natureza == "A" else "Rejeitado"
        if re.fullmatch(r"(aprovad|rejeitad|reprovad)[oa]", n):
            return "Aprovado" if natureza == "A" else "Rejeitado"
        return nome

    def _tipo_do_registro(self, r: dict, por_texto: dict[str, int], todas: dict, mats: dict) -> int | None:
        """O tipo da matéria votada: da lista guardada, do cadastro pedido antes ou do texto do registro ("... 1 - Projeto de
        Lei Ordinária nº 723 de 2016 em ..."); None = é preciso pedir a matéria."""
        mid = str(r.get("materia"))
        if mid in todas:
            return todas[mid].get("tipo")
        if mid in mats:
            return mats[mid][0]
        m = _REGISTRO_TXT.search(r.get("__str__") or "")
        return por_texto.get(B.norm(m.group(1))) if m else None

    def _guardar_registros(self, v: dict, regs: list[dict], todas: dict, tipos_ok: set[int]) -> list[str]:
        """Guarda os registros de votação desde 2025 das matérias de tipos_ok (pede o cadastro das matérias de tipo
        desconhecido, 100 por vez). Devolve os ids guardados."""
        por_texto = {B.norm(t.get("descricao")): t["id"] for t in self.tipos_materia() if t.get("descricao")}
        regs = [r for r in regs if str(r.get("data_hora") or "")[:10] >= B.INICIO and r.get("materia")]
        faltam = sorted({int(r["materia"]) for r in regs if self._tipo_do_registro(r, por_texto, todas, v["mat"]) is None})
        self.materias_votadas(v, faltam)
        out = []
        for r in regs:
            if self._tipo_do_registro(r, por_texto, todas, v["mat"]) not in tipos_ok:
                continue
            rid = str(r["id"])
            obs = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", r.get("observacao") or "")).strip()
            v["reg"][rid] = [r["materia"], r.get("ordem"), r.get("expediente"), r.get("tipo_resultado_votacao"),
                             r.get("numero_votos_sim"), r.get("numero_votos_nao"), r.get("numero_abstencoes"),
                             str(r.get("data_hora") or "")[:10], obs[:300]]
            out.append(rid)
        # o número, o ano e a ementa das matérias votadas que não estão na lista guardada (projetos de antes de 2025, vetos)
        self.materias_votadas(v, sorted({int(v["reg"][r][0]) for r in out if str(v["reg"][r][0]) not in todas}))
        return out

    def materias_votadas(self, v: dict, ids: list[int]) -> None:
        """Cadastro (tipo, número, ano e ementa) das matérias votadas que não estão na lista guardada (projetos de antes de
        2025, vetos, emendas), 100 por pedido. SAPL que ignora id__in: o tipo fica desconhecido e a votação não entra."""
        faltam = [i for i in ids if str(i) not in v["mat"]]
        for i in range(0, len(faltam), LOTE):
            lote = faltam[i:i + LOTE]
            pedidos = set(lote)
            try:
                rows = self.todos(MAT, {"id__in": ",".join(map(str, lote))}, checar=lambda x: x.get("id") in pedidos)
            except FiltroIgnorado:
                return
            for x in rows:
                v["mat"][str(x["id"])] = [x.get("tipo"), x.get("numero"), x.get("ano"), (x.get("ementa") or "").strip()[:600]]

    def _votos_de(self, v: dict, rids: list[str]) -> None:
        """O voto de cada vereador (votoparlamentar) dos registros que ainda não têm, 100 registros por vez (votacao__in)."""
        faltam = [int(r) for r in rids if r not in v["votos"]]
        for i in range(0, len(faltam), LOTE):
            lote = faltam[i:i + LOTE]
            rows = self.por_lotes(VOTO, "votacao", lote, cache="votos-lote")
            por: dict[str, list] = {str(r): [] for r in lote}
            for x in rows:
                por.setdefault(str(x.get("votacao")), []).append([x.get("parlamentar"), x.get("voto")])
            v["votos"].update(por)

    def _itens_de(self, v: dict) -> None:
        """A sessão e a data de cada item votado (ordem do dia ou expediente), 100 por pedido, para o endereço da votação na
        página da Câmara. SAPL que ignora id__in: vale a data do registro e a página da matéria."""
        if v.get("sem_itens"):
            return
        for chave, caminho, campo in (("o", ORDEM, 1), ("x", EXPEDIENTE, 2)):
            ids = sorted({int(r[campo]) for rid, r in v["reg"].items() if r[campo] and v["votos"].get(rid)
                          and f"{chave}{r[campo]}" not in v["itens"]})
            for i in range(0, len(ids), LOTE):
                lote = ids[i:i + LOTE]
                pedidos = set(lote)
                try:
                    rows = self.todos(caminho, {"id__in": ",".join(map(str, lote))}, checar=lambda x: x.get("id") in pedidos)
                except FiltroIgnorado:
                    v["sem_itens"] = True
                    return
                for x in rows:
                    v["itens"][f"{chave}{x['id']}"] = [x.get("sessao_plenaria"), str(x.get("data_ordem") or "")[:10]]

    def votacoes(self, e: dict, todas: dict[str, dict], tipos_ok: set[int]) -> None:
        """e["votacoes"]: as votações nominais desde 1º/1/2025 das matérias de tipos_ok (Sapl.tipos_votacao), com o voto de
        cada vereador. A primeira vez (e a cada LISTA_COMPLETA_DIAS), a lista inteira desde 2025, por um de dois caminhos,
        o que gastar menos pedidos: pelos registros de votação (registrovotacao; depois os votos de cada um) ou pelos votos
        (votoparlamentar; depois o registro de cada votação), conforme o tamanho das duas listas. A lista inteira é montada
        à parte (e["votacoes"]["nova"], guardada no estado a cada lote: uma leitura de várias rodadas continua de onde
        parou) e só substitui a de antes quando termina. Depois, só o que foi registrado desde a última rodada."""
        v = e.setdefault("votacoes", {})
        for k in ("reg", "votos", "itens", "mat"):
            v.setdefault(k, {})
        if v.get("sem_filtro"):
            return
        h = hoje()
        chk = lambda d: (lambda x: str(x.get("data_hora") or "")[:10] >= d)  # noqa: E731
        try:
            velha = (v.get("lista_em") or "") < _menos_dias(h, LISTA_COMPLETA_DIAS)
            if velha or v.get("nova"):
                w = v.setdefault("nova", {"ini": h, "reg": {}, "votos": {}, "fora": []})
                p_reg = self.get(REG, {"data_hora__gte": B.INICIO, "page": 1, "page_size": LOTE}, cache="reg-lista-p1", idade_h=SEMANA_H)
                p_vot = self.get(VOTO, {"data_hora__gte": B.INICIO, "page": 1, "page_size": LOTE}, cache="votos-lista-p1", idade_h=SEMANA_H)
                if not all(chk(B.INICIO)(x) for x in (p_reg.get("results") or []) + (p_vot.get("results") or [])):
                    raise FiltroIgnorado("data_hora__gte")
                n_reg = (p_reg.get("pagination") or {}).get("total_entries") or 0
                n_vot = (p_vot.get("pagination") or {}).get("total_entries") or 0
                # a lista à parte usa o cadastro das matérias e os itens da pauta já guardados (valem para as duas)
                tmp = {"reg": w["reg"], "votos": w["votos"], "mat": v["mat"], "itens": v["itens"], "sem_itens": v.get("sem_itens")}
                if n_vot:
                    modo = w.setdefault("modo", "votos" if n_vot < 1.4 * n_reg else "reg")
                    if modo == "reg":
                        regs = self.todos(REG, {"data_hora__gte": B.INICIO}, cache="reg-lista", idade_h=SEMANA_H, max_paginas=400,
                                          checar=chk(B.INICIO))
                        self.guardar_estado(e)
                        self._votos_de(tmp, self._guardar_registros(tmp, regs, todas, tipos_ok))
                    else:
                        votos = self.todos(VOTO, {"data_hora__gte": B.INICIO}, cache="votos-lista", idade_h=SEMANA_H, max_paginas=400,
                                           checar=chk(B.INICIO))
                        self._votos_pelos_votos(tmp, votos, todas, tipos_ok, fora=w["fora"])
                else:
                    w["modo"] = "votos"  # nenhum voto nominal desde 2025: nas próximas rodadas, só os votos novos (1 pedido)
                self._itens_de(tmp)
                v.update(reg=w["reg"], votos=w["votos"], modo=w["modo"], n_reg=n_reg, n_votos=n_vot, lista_em=h,
                         desde=min(w["ini"], h), sem_itens=tmp.get("sem_itens"))
                v.pop("nova", None)
            elif (v.get("desde") or "") < h:
                ini = _menos_dias(v["desde"], FOLGA_DIAS)
                if v.get("modo") == "reg":
                    regs = self.todos(REG, {"data_hora__gte": ini}, max_paginas=60, checar=chk(ini))
                    novos = self._guardar_registros(v, regs, todas, tipos_ok)
                    for rid in novos:  # registro corrigido ou novo: os votos de novo
                        v["votos"].pop(rid, None)
                    self._votos_de(v, novos)
                else:
                    votos = self.todos(VOTO, {"data_hora__gte": ini}, max_paginas=60, checar=chk(ini))
                    self._votos_pelos_votos(v, votos, todas, tipos_ok)
                self._itens_de(v)
                v["desde"] = h
            if any(v["votos"].values()):
                self.tipos_resultado()  # (guardado por 30 dias) o catálogo usa
        except MuitasPaginas:
            v.pop("nova", None)
            v.update(sem_filtro=True, motivo="muitas")
        except FiltroIgnorado:
            v.pop("nova", None)
            v["sem_filtro"] = True

    def _votos_pelos_votos(self, v: dict, votos: list[dict], todas: dict, tipos_ok: set[int], fora: list | None = None) -> None:
        """Caminho pelos votos: agrupa os votos por registro, pede os registros (100 por vez) e guarda os de tipos_ok, lote a
        lote (uma leitura pela metade continua dali). fora = os registros já vistos que não entram (requerimentos etc.),
        para não pedir de novo na rodada seguinte."""
        por: dict[str, list] = {}
        for x in votos:
            por.setdefault(str(x.get("votacao")), []).append([x.get("parlamentar"), x.get("voto")])
        fora = fora if fora is not None else []
        ja = set(v["reg"]) | {str(r) for r in fora}
        rids = sorted(int(r) for r in por if r != "None" and r not in ja)
        for i in range(0, len(rids), LOTE):
            lote = rids[i:i + LOTE]
            pedidos = set(lote)
            nome = f"reg-id-{hashlib.sha1(','.join(map(str, lote)).encode()).hexdigest()[:12]}"
            regs = self.todos(REG, {"id__in": ",".join(map(str, lote))}, cache=nome, idade_h=48,
                              checar=lambda x: x.get("id") in pedidos)
            guardados = set(self._guardar_registros(v, regs, todas, tipos_ok))
            fora.extend(r for r in lote if str(r) not in guardados)
        for rid, lst in por.items():
            if rid in v["reg"]:
                antes = {p for p, _ in v["votos"].get(rid) or []}
                v["votos"][rid] = (v["votos"].get(rid) or []) + [x for x in lst if x[0] not in antes]

    def catalogo_votacoes(self, e: dict, todas: dict[str, dict], tipos: dict) -> tuple[dict | None, dict[int, list]]:
        """({chave: votação} para o arquivo da cidade, {id do parlamentar no SAPL: [[chave, voto], ...]}): só as votações
        nominais (com voto de cada vereador) desde 1º/1/2025. Placar = o publicado pela Câmara no registro; se a soma dos
        votos for diferente, vai junto o "aviso" (como no Congresso). None no lugar do catálogo quando a rodada acabou antes
        de ler os tipos de resultado e não há a lista guardada (no robô, que começa com o cache vazio): sem eles, não dá
        para saber quais votações decidiram a matéria, e o catálogo não é montado nesta rodada."""
        v = e.get("votacoes") or {}
        if not v.get("reg"):
            return {}, {}
        try:
            res = self.tipos_resultado()
        except SemOrcamento:  # a rodada acabou: vale a lista guardada, de qualquer idade
            arq = self.pasta / "http" / "tipos-resultado-p1.json"
            guardada = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
            res = {t["id"]: ((t.get("nome") or "").strip(), t.get("natureza")) for t in
                   (guardada.get("results") if isinstance(guardada, dict) else guardada) or []}
            if not res:
                return None, {}
        siglas = {t["id"]: (t.get("sigla") or "").strip() for t in self.tipos_materia()}
        cat, por_parl = {}, {}
        for rid, r in v["reg"].items():
            vs = v["votos"].get(rid) or []
            if not vs:
                continue  # votação simbólica: só o resultado
            mid, oid, xid, tres, s, n, a, dh, obs = r
            resultado = self.resultado_votacao(*res.get(tres, ("", "")))
            if not resultado:
                continue  # adiamento, pedido de vista: a votação não decidiu a matéria
            item = v["itens"].get(f"o{oid}" if oid else f"x{xid}") or [None, None]
            data = item[1] or dh
            if not data or data < B.INICIO:
                continue
            m = todas.get(str(mid)) or {}
            if m:
                tipo, num, ano, ementa = m.get("tipo"), m.get("numero"), m.get("ano"), m.get("ementa")
            else:
                tipo, num, ano, ementa = (v["mat"].get(str(mid)) or [None, None, None, None])
            sig = siglas.get(tipo) or ((tipos.get(tipo) or ("", "", ""))[1])
            if item[0]:
                url = f"{self.base}/sessao/{item[0]}/votacao-nominal-transparencia/{oid or xid}/{mid}?materia={'ordem' if oid else 'expediente'}"
            else:
                url = f"{self.base}/materia/{mid}"
            chave = f"{self.prefixo}-vot:{rid}"
            oficial = {"Sim": s or 0, "Não": n or 0, "Abstenção": a or 0}
            # a mesma pessoa duas vezes na mesma votação: vale o voto que bate com o placar (B.votos_unicos)
            votos = B.votos_unicos(((pid, voto_normal(voto)) for pid, voto in vs if pid is not None), oficial)
            contado = {k: sum(1 for x in votos.values() if x == k) for k in oficial}
            for pid, vn in votos.items():
                por_parl.setdefault(pid, []).append([chave, vn])
            ementa = re.sub(r"\s+", " ", ementa or "").strip()
            desc = f"{ementa} (Observação do registro da votação: {obs})" if ementa and obs else ementa or obs or None
            x = {"data": data, "proposta": f"{sig} {num}/{ano}".strip() if num and ano else (sig or None),
                 "propostaId": f"{self.prefixo}:{mid}", "descricao": desc,
                 "resultado": resultado, "placar": dict(oficial, total=sum(oficial.values())), "url": url}
            if contado != oficial:
                x["aviso"] = {"oficial": oficial, "contado": contado}
            cat[chave] = x
        for lst in por_parl.values():
            lst.sort(key=lambda kv: (cat[kv[0]]["data"], kv[0]), reverse=True)
        return dict(sorted(cat.items(), key=lambda kv: (kv[1]["data"], kv[0]), reverse=True)), por_parl

    def notas_votos_publicadas(self) -> list[tuple[str, str]]:
        """As notas sobre as votações do arquivo da Câmara já publicado (o que não entra e por quê, de uma leitura completa).
        Só as do formato de hoje ("As votações de cada vereador não entram neste site: ..."): a nota antiga, que juntava
        votações e gastos, fica fora."""
        d = ler_json(CAMARAS / f"{self.ibge}.json", {}) or {}
        pt, en = d.get("notas") or [], d.get("notas_en") or []
        return [(n, en[i] if len(en) == len(pt) else n) for i, n in enumerate(pt)
                if isinstance(n, str) and n.startswith("As votações de cada vereador não entram neste site:")]

    def notas_votacoes(self, e: dict, publicou: bool, sem_catalogo: bool = False) -> list[tuple[str, str]]:
        """As notas da Câmara sobre as votações (o que não entra e por quê) e sobre os gastos (o SAPL não tem).
        sem_catalogo: nesta rodada não deu para montar o catálogo (faltaram os tipos de resultado). Enquanto a leitura das
        votações não termina (ou sem o catálogo), fica a nota publicada antes, de uma leitura completa; sem ela, nada a
        dizer sobre as votações (uma nota de "não entram" seria um palpite)."""
        v = e.get("votacoes") or {}
        gastos = self.nota_gastos or (
            "Os gastos do mandato de cada vereador não entram neste site: o sistema de dados abertos da Câmara (SAPL) "
            "não tem esse dado.",
            "Each councilor's office spending is not included on this site: the City Council's open data system (SAPL) "
            "does not have it.")
        if publicou:
            return [gastos]
        if sem_catalogo or (not v.get("lista_em") and not v.get("sem_filtro")):
            return self.notas_votos_publicadas() + [gastos]
        if v.get("motivo") == "muitas":
            p = ("As votações de cada vereador não entram neste site: o SAPL desta Câmara tem mais votações desde 1º/1/2025 do que "
                 "dá para ler respeitando o intervalo entre pedidos que o próprio sistema pede.",
                 "Each councilor's votes are not included on this site: this City Council's SAPL system has more votes since "
                 "January 1, 2025 than can be read while respecting the interval between requests the system itself asks for.")
        elif v.get("sem_filtro"):
            p = ("As votações de cada vereador não entram neste site: o SAPL desta Câmara não deixa pesquisar as votações por data.",
                 "Each councilor's votes are not included on this site: this City Council's SAPL system does not allow searching "
                 "the votes by date.")
        elif not v.get("n_reg"):
            p = ("As votações de cada vereador não entram neste site: o SAPL desta Câmara não tem as votações do Plenário desde "
                 "1º/1/2025.",
                 "Each councilor's votes are not included on this site: this City Council's SAPL system has no record of the "
                 "full Council's votes since January 1, 2025.")
        elif not v.get("n_votos"):
            p = ("As votações de cada vereador não entram neste site: desde 1º/1/2025, o SAPL desta Câmara registra o resultado "
                 "de cada votação, mas não o voto de cada vereador.",
                 "Each councilor's votes are not included on this site: since January 1, 2025, this City Council's SAPL system "
                 "has recorded the result of each vote, but not how each councilor voted.")
        else:
            p = ("As votações de cada vereador não entram neste site: desde 1º/1/2025, o SAPL desta Câmara tem o voto de cada "
                 "vereador só em votações que ficam fora (de requerimentos, indicações, moções e outros documentos, ou que não "
                 "decidiram a proposta, como o adiamento).",
                 "Each councilor's votes are not included on this site: since January 1, 2025, this City Council's SAPL system "
                 "has each councilor's vote only in votes that are left out (on requests, recommendations, motions and other "
                 "documents, or votes that did not decide on the proposal, such as postponing it).")
        return [p, gastos]

    # ------------------------------------------------------------ o prefeito
    def executivo(self, inicio: str, tipos_prop: dict, todas: dict[str, dict], tipos_v: set[int], e: dict) -> tuple[dict | None, list]:
        """("executivo" do contrato ou None, notas da Câmara sobre o que ficou fora). inicio = começo do mandato de quem está
        no cargo. Leis: normas jurídicas de tipo lei ordinária/complementar, municipais, com data no período, cada lei uma
        vez. Só conta se a numeração parece completa (_conferir_leis: começo, fim, buracos, a lei mais nova da numeração
        principal com até 120 dias). Vetos: projetos cuja primeira situação de veto no andamento é do período; se o andamento
        não tiver nenhum, as matérias do tipo "Veto" do período."""
        h = hoje()
        notas: list[tuple[str, str]] = []
        ex: dict = {"periodo": {"inicio": inicio, "fim": None}}
        # (pt, en) de cada número: como foi contado ou, se ficou fora, por quê (também vai para as notas da Câmara)
        parte_leis: tuple[str, str] = ("", "")
        parte_vetos: tuple[str, str] = ("", "")
        dpt, den = data_pt(inicio), data_en(inicio)
        fontes = []
        # ---- leis
        tn = self.tipos_norma()
        leis = {k: t for k, t in tn.items() if eh_lei(t)}
        promulgadas = {k for k, t in leis.items() if "promulg" in B.norm(t.get("descricao"))}
        comp = {k for k, t in leis.items() if "complementar" in B.norm(t.get("descricao"))
                or (t.get("equivalente_lexml") or "").lower() == "lei.complementar"}
        municipais = [n for n in e["normas"].values() if n.get("tipo") in leis and (n.get("esfera_federacao") or "M") == "M"
                      and "1900" < (n.get("data") or "")[:10] <= h]
        lista = [n for n in municipais if n["data"][:10] >= inicio]
        antes = [n for n in municipais if n["data"][:10] < inicio]  # para saber o número da última lei de antes do período
        sanc = [n for n in lista if n["tipo"] not in promulgadas]
        conf = _conferir_leis(lista, antes, comp, inicio, h) if sanc else None
        n_sanc = conf["conta"](sanc) if conf else 0  # a mesma lei cadastrada duas vezes conta uma
        if not sanc:
            parte_leis = ("O SAPL desta Câmara não tem as leis municipais do mandato atual cadastradas: por isso o perfil do "
                          "prefeito não mostra quantas leis foram sancionadas.",
                          "This City Council's SAPL system does not list the city's laws for the current term, so the "
                          "mayor's profile does not show how many laws were signed.")
        else:
            ultima, falta, faixa, buraco = conf["ultima"], conf["faltam"], conf["faixa"], conf["buraco"]
            ult_p = conf["ultima_principal"] or ultima
            cerca, cerca_en = ("cerca de ", "about ") if conf["estimadas"] else ("", "")
            depois = (f", contando as que deveriam vir depois da última cadastrada, de {data_pt(ult_p)}" if conf["fim"] else "")
            depois_en = (f", counting those that should have come after the last one recorded, from {data_en(ult_p)}"
                         if conf["fim"] else "")
            if conf["distintas"] < 3:
                parte_leis = (f"O SAPL desta Câmara tem só {conf['distintas']} lei(s) cadastrada(s) desde {dpt}: é pouco para "
                              "saber se o cadastro está completo, e o número de leis sancionadas fica fora do perfil do prefeito.",
                              f"This City Council's SAPL system has only {conf['distintas']} law(s) recorded since {den}: too "
                              "few to tell whether the records are complete, so the number of laws signed is left out of the "
                              "mayor's profile.")
            elif ult_p < _menos_dias(h, LEIS_ATRASO_DIAS):
                parte_leis = (f"As leis no SAPL desta Câmara vão só até {data_pt(ult_p)}: o número de leis sancionadas fica "
                              "fora do perfil do prefeito até a Câmara atualizar o cadastro.",
                              f"The laws in this City Council's SAPL system only go up to {data_en(ult_p)}, so the number of "
                              "laws signed is left out of the mayor's profile until the Council updates it.")
            elif buraco and buraco[1] - buraco[0] + 1 > max(LEIS_BURACO, LEIS_BURACO_FRACAO * faixa):
                a, b = buraco
                parte_leis = (f"Faltam leis no SAPL desta Câmara (os números {a} a {b} não estão cadastrados): o número de leis "
                              "sancionadas fica fora do perfil do prefeito.",
                              f"Some laws are missing from this City Council's SAPL system (numbers {a} to {b} are not there), "
                              "so the number of laws signed is left out of the mayor's profile.")
            elif faixa and falta > LEIS_FALTANDO * faixa:
                parte_leis = (f"Faltam leis no SAPL desta Câmara ({cerca}{falta} dos {faixa} números de lei desde {dpt} não estão "
                              f"cadastrados{depois}): o número de leis sancionadas fica fora do perfil do prefeito.",
                              f"Some laws are missing from this City Council's SAPL system ({cerca_en}{falta} of the {faixa} law "
                              f"numbers since {den} are not there{depois_en}), so the number of laws signed is left out of the "
                              "mayor's profile.")
            else:
                ex["leisSancionadas"] = n_sanc
                ex["periodo"]["ultimaLei"] = ultima  # mesmo lugar do presidente e dos governadores (o perfil mostra a data)
                lo = min(leis, key=lambda k: (not re.fullmatch(r"leis?( ordinarias?)?", B.norm(leis[k].get("descricao"))), k))
                fontes.append(fonte(self.casa, f"SAPL: leis com data a partir de {dpt}",
                                    f"{self.base}/norma/pesquisar?tipo={lo}&data_0={_data_br(inicio)}&data_1=", h))
                t_pt = (f"Leis: as {n_sanc} leis ordinárias e complementares com data a partir de {dpt} cadastradas no SAPL "
                        "da Câmara, venham de quem vierem (a prefeitura sanciona quase todas).")
                t_en = (f"Laws: the {n_sanc} ordinary and complementary laws dated from {den} on in the City Council's SAPL "
                        "system, whoever proposed them (the mayor's office signs almost all of them).")
                if promulgadas:
                    t_pt += " As leis que a própria Câmara promulgou (tipo “Lei Promulgada” no SAPL) ficam fora."
                    t_en += " Laws promulgated by the Council itself (type “Lei Promulgada” in SAPL) are left out."
                else:
                    t_pt += (" O SAPL não separa as poucas leis que a própria Câmara promulga (quando derruba um veto ou quando "
                             "o prefeito não assina no prazo), então elas também entram.")
                    t_en += (" SAPL does not separate the few laws the Council promulgates itself (when it overrides a veto or "
                             "when the mayor does not sign in time), so they are included too.")
                if falta:
                    t_pt += f" Faltam no SAPL {cerca}{falta} dos {faixa} números de lei do período{depois}."
                    t_en += f" {cerca_en.capitalize()}{falta} of the {faixa} law numbers in the period are missing from SAPL{depois_en}."
                parte_leis = (t_pt, t_en)
        if "leisSancionadas" not in ex:
            notas.append(parte_leis)
        # ---- vetos
        cand = sorted(int(m) for m, d in e["vetos"].items() if inicio <= d <= h)
        tipo_mat = {int(k): v.get("tipo") for k, v in todas.items()}
        tipo_mat.update(self.tipos_de([m for m in cand if m not in tipo_mat]))  # projetos de antes de 2025 vetados no período
        desconhecidos = [m for m in cand if m not in tipo_mat]
        vetados = [m for m in cand if tipo_mat.get(m) in tipos_prop]
        if desconhecidos:
            parte_vetos = (f"O número de vetos fica fora do perfil do prefeito: o SAPL desta Câmara não deixa conferir, numa "
                           f"pesquisa só, de que tipo são {len(desconhecidos)} matérias com veto no andamento desde {dpt} "
                           "(projeto ou outro documento).",
                           f"The number of vetoes is left out of the mayor's profile: this City Council's SAPL system does not "
                           f"let us check, in a single search, what kind of item {len(desconhecidos)} records with a veto in "
                           f"their progress since {den} are (a bill or another document).")
        elif vetados:
            ex["vetos"] = len(vetados)
            st = self.status_tramitacao()
            sid = max((k for k, d in st.items() if status_de_veto(d)), default=None,
                      key=lambda k: B.norm(st[k]).startswith("proposicao com veto"))
            fontes.append(fonte(self.casa, "SAPL: matérias com veto no andamento",
                                f"{self.base}/materia/pesquisar-materia" + (f"?tramitacao__status={sid}" if sid else ""), h))
            parte_vetos = (f"Vetos: os projetos que, pelo andamento registrado no SAPL, receberam veto total ou parcial a "
                           f"partir de {dpt}.",
                           f"Vetoes: the bills that, according to the progress recorded in SAPL, were vetoed in whole or in "
                           f"part from {den} on.")
        else:
            n = sum(1 for m in todas.values() if m.get("tipo") in tipos_v and inicio <= (m.get("data_apresentacao") or "")[:10] <= h)
            if n:
                ex["vetos"] = n
                fontes.append(fonte(self.casa, "SAPL: mensagens de veto",
                                    f"{self.base}/materia/pesquisar-materia?tipo={min(tipos_v)}", h))
                parte_vetos = (f"Vetos: as mensagens de veto (total ou parcial) que a prefeitura mandou à Câmara a partir de "
                               f"{dpt}, cadastradas no SAPL.",
                               f"Vetoes: the veto messages (full or partial) the mayor's office sent to the City Council from "
                               f"{den} on, as recorded in SAPL.")
            else:
                parte_vetos = (f"O SAPL desta Câmara não registra nenhum veto desde {dpt}: como não dá para saber se não houve "
                               "veto ou se ele não foi cadastrado, o perfil do prefeito não mostra o número de vetos.",
                               f"This City Council's SAPL system records no veto since {den}. Since there is no way to tell "
                               "whether there was no veto or it was not recorded, the mayor's profile does not show the number "
                               "of vetoes.")
        if "vetos" not in ex:
            notas.append(parte_vetos)
        if "leisSancionadas" not in ex and "vetos" not in ex:
            return None, notas
        ex["fonte"] = fontes[0]
        if len(fontes) > 1:
            ex["fontes"] = fontes
        # "Como contamos": como cada número foi contado e, se um deles ficou fora, por quê (o perfil mostra o quadro só com o
        # número que entrou, e o quadro "Onde ver mais" não aparece). Também separadas (notaLeis, notaVetos): quando outra
        # fonte oficial conta o número que ficou fora (ex.: as leis pelo Diário Oficial), o perfil junta cada número com a
        # explicação da fonte de onde ele veio. nota = notaLeis + " " + notaVetos
        ex["nota"] = f"{parte_leis[0]} {parte_vetos[0]}"
        ex["nota_en"] = f"{parte_leis[1]} {parte_vetos[1]}"
        ex["notaLeis"], ex["notaLeis_en"] = parte_leis
        ex["notaVetos"], ex["notaVetos_en"] = parte_vetos
        return ex, notas

    def prefeito(self, mats: dict[str, dict], todas: dict[str, dict], tipos: dict, tipos_v: set[int], e: dict,
                 status_txt: dict, normas: dict, exec_aut: dict[int, str]) -> tuple[tuple | None, list]:
        """(("pref-<IBGE>", dados) ou None, notas da Câmara)."""
        c = B.cidade(self.ibge, self.uf)
        pref = c.get("prefeito") or {}
        pid = pref.get("id")
        if not pid:
            return None, []
        h = hoje()
        inicio = max(B.INICIO, (pref.get("desde") or "")[:10] or B.INICIO)
        notas: list[tuple[str, str]] = []
        dados: dict = {}
        lista = []
        for mid, m in mats.items():
            if (m.get("data_apresentacao") or "")[:10] < inicio:
                continue
            rows = (e["autoria"].get(mid) or {}).get("r") or []
            if any(r[0] in exec_aut for r in rows) or (not rows and set(m.get("autores") or []) & set(exec_aut)):
                comum, sig_tipo, _ = tipos[m["tipo"]]
                lista.append(self.proposta(mid, m, comum, sig_tipo, "autor", e["ultima"].get(mid), status_txt, normas))
        desde_txt = (f"desde {data_pt(inicio)}, quando assumiu a prefeitura" if inicio > B.INICIO
                     else f"desde {data_pt(inicio)}, começo do mandato")
        desde_en = (f"since {data_en(inicio)}, when the current mayor took office" if inicio > B.INICIO
                    else f"since {data_en(inicio)}, start of the term")
        if lista:
            principal = max(exec_aut, key=lambda a: sum(1 for x in mats.values() if a in (x.get("autores") or [])))
            quem = B.nome_limpo(exec_aut[principal]) or "Poder Executivo"
            f_prop = fonte(self.casa, f"SAPL: matérias de autoria de {quem}",
                           f"{self.base}/materia/pesquisar-materia?autoria__autor={principal}&data_apresentacao_0={_data_br(inicio)}"
                           "&data_apresentacao_1=", h)
            dados["propostas"] = regional.bloco_propostas(
                lista, f"Projetos que a prefeitura mandou à Câmara Municipal {desde_txt} (projetos de lei, de lei complementar e "
                       "de emenda à Lei Orgânica), segundo o sistema oficial da Câmara (SAPL)",
                f"Bills the mayor's office sent to the City Council {desde_en} (ordinary and complementary bills and amendments "
                "to the city's Organic Law), according to the City Council's official system (SAPL)", f_prop)
            dados["fontes"] = [f_prop]
        else:
            notas.append((f"Não achamos no SAPL desta Câmara projetos mandados pela prefeitura desde {data_pt(inicio)} (o autor "
                          "\"Poder Executivo\" ou \"Prefeito\" não aparece): o perfil do prefeito não mostra os projetos dele.",
                          f"We found no bills sent by the mayor's office since {data_en(inicio)} in this City Council's SAPL "
                          "system (no \"Executive\" or \"Mayor\" author), so the mayor's profile does not list them."))
        ex, n_ex = self.executivo(inicio, tipos, todas, tipos_v, e)
        notas += n_ex
        if ex:
            dados["executivo"] = ex
            dados.setdefault("fontes", []).extend(f for f in (ex.get("fontes") or [ex["fonte"]]) if f not in dados.get("fontes", []))
        return ((pid, dados) if dados else None), notas

    # ------------------------------------------------------------ tudo
    def prefeito_de_antes(self) -> tuple[tuple | None, list]:
        """Se a parte do prefeito falhar numa rodada: fica o que foi publicado antes (arquivo da cidade e as notas da Câmara
        sobre o prefeito), desde que seja de quem está no cargo hoje."""
        pid = (B.cidade(self.ibge, self.uf).get("prefeito") or {}).get("id")
        antes = ((ler_json(EXTRAS_CIDADES / f"{self.ibge}.json") or {}).get("pessoas") or {}).get(pid) if pid else None
        if not antes:
            return None, []
        casa = ler_json(CAMARAS / f"{self.ibge}.json") or {}
        notas = [(pt, en) for pt, en in zip(casa.get("notas") or [], casa.get("notas_en") or []) if re.search(r"prefeit", pt)]
        dados = {k: v for k, v in antes.items() if k != "id"}
        return (pid, dados), notas

    def limpar_paginas(self, votos: bool = True) -> None:
        """Depois de uma carga completa: apaga as páginas guardadas só para uma carga pela metade continuar (listas inteiras
        e lotes de autoria e de tramitação), para o cache do robô ficar pequeno. Ficam as listas de referência (tipos,
        situações, autores, legislaturas...), que valem por dias. votos=False: a leitura das votações continua na próxima
        rodada, e as páginas dela ficam."""
        apagar = r"mats-lista|mats-ano|normas-lista|normas-ano|aut|hist|vetos-ini" + (r"|reg-lista|votos-lista|votos-lote|reg-id" if votos else "")
        for arq in (self.pasta / "http").glob("*.json"):
            if re.match(rf"({apagar})-", arq.name):
                arq.unlink(missing_ok=True)

    def limpar_paginas_votos(self) -> None:
        """Apaga as páginas guardadas da leitura das votações (a lista inteira recomeça do zero)."""
        for arq in (self.pasta / "http").glob("*.json"):
            if re.match(r"(reg-lista|votos-lista|votos-lote|reg-id)-", arq.name):
                arq.unlink(missing_ok=True)

    def coletar(self) -> dict:
        t0 = time.time()
        h = hoje()
        e = self.estado()
        etapa = "lista"
        try:
            self.identificar()
            presentes, leg, todos_leg = self.membros(e)
            tse = B.Tse(self.ibge, self.uf, self.tse_manual)
            membros, por_pid = self.fichas(presentes, tse)
            problema = self.conferir(membros, tse)
            oficial, validos = True, None
            if problema:
                if not self.sem_lista_se_falhar:
                    raise RuntimeError(f"{problema}: conferir à mão (incluir/excluir)")
                # sem a lista oficial: a página da cidade fica com a lista do TSE; as propostas vão para quem está nela e foi
                # ligado ao TSE pelo nome sem dúvida (casar_tse só liga quando não há empate)
                oficial = False
                validos = tse.ids_eleitos()
                tse = B.Tse(self.ibge, self.uf, self.tse_manual)
                todos, por_pid_t = self.fichas(list(todos_leg.values()), tse)
                contagem: dict[str, int] = {}
                for m in todos:
                    contagem[m["id"]] = contagem.get(m["id"], 0) + 1
                por_pid = {k: v for k, v in por_pid_t.items() if v[0]["id"] in validos and v[0].get("_cand")
                           and contagem[v[0]["id"]] == 1}
                membros = []
            for m in membros:
                m.pop("_cand", None)
            etapa = "tipos"
            tipos = self.tipos()
            tipos_v = self.tipos_veto()
            status_txt = self.status_tramitacao()
            st_veto = {k for k, d in status_txt.items() if status_de_veto(d)}
            etapa = "matérias"
            todas = self.atualizar_materias(e, set(tipos) | tipos_v)
            self.guardar_estado(e)
            mats = {k: v for k, v in todas.items() if v.get("tipo") in tipos}
            etapa = "autoria"
            self.autorias(e, mats)
            etapa = "tramitações"
            self.tramitacoes(e, mats, status_txt, st_veto)
            etapa = "normas"
            self.atualizar_normas(e)
            self.guardar_estado(e)
            etapa = "vetos"
            self.vetos_iniciais(e, st_veto)
            etapa = "autores"
            autores, exec_aut = self.autores(e, mats)
            normas = self.normas(e)
            if self.com_prefeito:
                etapa = "vetos do prefeito"
                self.tipos_de(self.vetadas_fora(e, todas), parar=True)  # o tipo de cada matéria vetada (pedido uma vez só)
            etapa = "votações"
            votos_pela_metade = False
            try:
                self.votacoes(e, todas, self.tipos_votacao(tipos, tipos_v))
            except SemOrcamento as motivo:
                # a leitura da lista inteira das votações continua na próxima rodada (de onde parou); a cidade é publicada
                # com as votações completas de antes (na primeira leitura, sem votações) e fica na fila diária
                votos_pela_metade = True
                self.guardar_estado(e)
                log(f"  {self.sigla} {self.ibge}: votações nominais pela metade ({motivo}; {self.n_req} pedidos): continuam "
                    "na próxima rodada; publica o resto")
            except Exception as erro:  # as votações são um extra: um erro aqui não derruba o resto da cidade
                # (ex.: a lista mudou de tamanho entre um dia e outro e uma página guardada aponta para uma que não existe
                # mais, HTTP 404): a leitura da lista inteira recomeça do zero na próxima vez
                (e.get("votacoes") or {}).pop("nova", None)
                self.limpar_paginas_votos()
                self.guardar_estado(e)
                log(f"  {self.sigla} {self.ibge}: votações: {type(erro).__name__}: {str(erro)[:200]}; recomeçam na próxima "
                    "rodada; publica o resto")
        except SemOrcamento as motivo:
            if self.n_req == 0 and e.get("completo") is True:
                # a rodada acabou antes do primeiro pedido desta cidade (começou no último minuto): nada mudou, e ela
                # continua completa (não entra na fila diária de primeira carga por isso)
                log(f"  {self.sigla} {self.ibge}: sem tempo para começar ({motivo}); fica para a próxima rodada")
                return {"ok": True, "pendente": True, "etapa": etapa, "requisicoes": 0}
            e["completo"] = False
            e["parou_em"] = {"data": h, "etapa": etapa, "pedidos": self.n_req}
            self.guardar_estado(e)
            log(f"  {self.sigla} {self.ibge}: parou em \"{etapa}\" ({motivo}; {self.n_req} pedidos, {time.time() - t0:.0f} s); "
                "continua na próxima rodada")
            return {"ok": True, "pendente": True, "etapa": etapa, "requisicoes": self.n_req}
        for k in ("ultima", "autoria", "verif"):  # esquece propostas que não estão mais na lista
            e[k] = {mid: x for mid, x in e[k].items() if mid in mats}
        e["conferencia"] = {"data": h, "problema": problema}

        notas_extra: list[tuple[str, str]] = []
        sem_and = sum(1 for mid in mats if not e["ultima"].get(mid))
        if len(mats) >= 10 and sem_and >= 0.5 * len(mats):
            notas_extra.append((f"A Câmara não registra no SAPL o andamento da maior parte das propostas ({sem_and} de {len(mats)} "
                                "apresentadas desde 1º/1/2025): a situação delas aparece como não registrada.",
                                f"The City Council does not record in SAPL the progress of most bills ({sem_and} of {len(mats)} "
                                "filed since January 1, 2025), so their status shows as not recorded."))
        fonte_lista = fonte(self.casa, f"SAPL: vereadores em exercício na legislatura {leg['data_inicio'][:4]}–{leg['data_fim'][:4]} (dados abertos)",
                            f"{self.base}/parlamentar/", h)

        por_parl: dict[int, list] = {pid: [] for pid in por_pid}
        heuristica = 0
        for mid, m in mats.items():
            comum, sig_tipo, _ = tipos[m["tipo"]]
            todas_aut = (e["autoria"].get(mid) or {}).get("r") or []
            rows = [r for r in todas_aut if r[0] in autores]
            if not rows:
                continue
            marcados = [r for r in todas_aut if r[1]]
            for autor_id, primeiro, aid in rows:
                parl = autores[autor_id]
                if parl not in por_parl:
                    continue
                if marcados:
                    papel = "autor" if primeiro else "coautor"
                elif len(todas_aut) == 1:
                    papel = "autor"
                elif self.primeiro_por_ordem:
                    heuristica += 1
                    papel = "autor" if aid == min(r[2] for r in todas_aut) else "coautor"
                else:
                    papel = "coautor"
                por_parl[parl].append(self.proposta(mid, m, comum, sig_tipo, papel, e["ultima"].get(mid), status_txt, normas))
        if heuristica:
            log(f"  {self.sigla} {self.ibge}: {heuristica} autorias sem 'primeiro autor' marcado (vale o primeiro cadastrado)")

        escopo = (B.ESCOPO + ", segundo o sistema oficial da Câmara (SAPL).",
                  B.ESCOPO_EN + ", according to the City Council's official system (SAPL).")
        if not autores:
            notas_extra.append(("As propostas de cada vereador não entram neste site: o SAPL desta Câmara não registra os "
                                "vereadores como autores das proposições. Dá para ver as proposições no sistema da Câmara.",
                                "Each councilor's bills are not included on this site: this City Council's SAPL system does not "
                                "record councilors as the authors of bills. The bills can be seen in the Council's system."))
        extras = {}
        for parl, (m, d, v) in por_pid.items():
            f_prop = fonte(self.casa, f"SAPL: matérias de {m['nome']}", f"{self.base}/parlamentar/{parl}/materias", h)
            x = {"links": {"oficial": m["url"], "email": _email_oficial(d.get("email")), "redes": []},
                 "fontes": [fonte_lista, f_prop] if autores else [fonte_lista]}
            if autores:
                x["propostas"] = regional.bloco_propostas(por_parl[parl], escopo[0], escopo[1], f_prop)
            if (m.get("foto") or "").startswith("img/pessoas/"):
                x["fotoCredito"] = self.casa
            mh = v.get("mandato_hoje")
            if oficial and mh and mh.get("data_inicio_mandato"):
                x["mandato"] = {"inicio": mh["data_inicio_mandato"], "fim": mh.get("data_fim_mandato") or leg["data_fim"],
                                "situacao": "Em exercício", "obs": None, "fonte": fonte_lista}
                if mh["data_inicio_mandato"] > leg["data_inicio"]:
                    x["desde"] = mh["data_inicio_mandato"]
            extras[m["id"]] = x

        # votações nominais: o voto de cada vereador (no perfil) e o que foi votado (catálogo no arquivo da cidade)
        cat_vot, votos_parl = self.catalogo_votacoes(e, todas, tipos)
        sem_catalogo = cat_vot is None
        cat_vot = cat_vot or {}
        v_est = e.get("votacoes") or {}
        usadas: set[str] = set()
        if cat_vot:
            fonte_vot = fonte(self.casa, "SAPL: votações nominais das sessões plenárias", f"{self.base}/sessao/pesquisar-sessao", h)
            for parl, (m, d, v) in por_pid.items():
                lst = votos_parl.get(parl) or []
                if not lst or m["id"] not in extras:
                    continue
                resumo = {"total": len(lst)}
                for k in ("Sim", "Não", "Abstenção"):
                    resumo[k] = sum(1 for _, vt in lst if vt == k)
                resumo["Outro"] = resumo["total"] - resumo["Sim"] - resumo["Não"] - resumo["Abstenção"]
                extras[m["id"]]["votacoes"] = {"escopo": ESCOPO_VOTOS[0], "escopo_en": ESCOPO_VOTOS[1], "resumo": resumo,
                                               "fonte": fonte_vot, "arquivo": f"dados/camaras/extras/{self.ibge}.json", "votos": lst}
                extras[m["id"]]["fontes"].append(fonte_vot)
                usadas.update(k for k, _ in lst)
        elif sem_catalogo or v_est.get("nova") or not v_est.get("lista_em"):
            # a leitura das votações não terminou (no robô, que começa com o cache vazio, por exemplo: a lista inteira pela
            # metade, uma leitura que nunca terminou ou que nem começou, ou a rodada acabou antes dos tipos de resultado,
            # que o catálogo usa): fica publicado o que já estava, para quem continua no cargo
            cat_vot, blocos = B.votos_publicados(self.ibge)
            for x_id, x in extras.items():
                if x_id in blocos:
                    x["votacoes"] = blocos[x_id]
                    x["fontes"].append(blocos[x_id].get("fonte"))
                    usadas.update(k for k, _ in blocos[x_id]["votos"])
        cat_vot = {k: x for k, x in cat_vot.items() if k in usadas}

        pref, notas_pref = None, []
        if self.com_prefeito:
            try:
                pref, notas_pref = self.prefeito(mats, todas, tipos, tipos_v, e, status_txt, normas, exec_aut)
            except Exception as erro:  # o que o prefeito fez é um extra: um erro aqui não derruba as propostas dos vereadores
                log(f"  {self.sigla} {self.ibge}: prefeito: {type(erro).__name__}: {str(erro)[:200]}")
                pref, notas_pref = self.prefeito_de_antes()
        notas = list(self.notas_casa) + notas_extra + self.notas_votacoes(e, bool(cat_vot), sem_catalogo) + notas_pref
        if tse.sem_ligacao:
            log(f"  {self.sigla} {self.ibge}: sem ligação com o TSE: {', '.join(tse.sem_ligacao)}")
        if problema:
            log(f"  {self.sigla} {self.ibge}: sem lista oficial ({problema}); propostas ligadas à lista do TSE")
        cobertura = {"lista": oficial, "propostas": bool(autores), "votacoes": bool(cat_vot), "gastos": False}
        casa = {"casa": self.casa, "casa_en": self.casa_en, "sigla": self.sigla, "site": self.site, "fonte": fonte_lista,
                "sistema": "SAPL", "api": f"{self.base}/api/"}
        r = B.salvar(self.ibge, self.uf, casa, membros, extras, cobertura, notas, escopo, prefeito=pref, oficial=oficial,
                     ids_validos=validos, votacoes=cat_vot)
        # só agora (a cidade foi publicada inteira) a carga conta como completa; um erro antes deixa a cidade na fila. Com
        # as votações nominais pela metade, a cidade volta amanhã (_lista.pendentes) e as páginas delas ficam guardadas.
        e["completo"] = not votos_pela_metade
        e.pop("parou_em", None)
        self.guardar_estado(e)
        self.limpar_paginas(votos=not votos_pela_metade)
        r["requisicoes"] = self.n_req
        r["semTse"] = len(tse.sem_ligacao)
        if problema:
            r["conferencia"] = problema
            r["vereadoresComPropostas"] = len(extras)
        log(f"  {self.sigla} {self.ibge}: {len(membros)} no cargo{'' if oficial else ' (sem lista oficial)'}, {r['propostas']} propostas, "
            f"prefeito {r.get('prefeito')}, {self.n_req} pedidos, {time.time() - t0:.0f} s")
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
        elif st == "outra" and not txt and not ult:
            txt, txt_en = SEM_ANDAMENTO
        p = regional.proposta(f"{self.prefixo}:{mid}", sigla, comum, m.get("data_apresentacao"), m.get("ementa"), desc, url,
                              papel, status=st, data_status=(ult or {}).get("d"), status_txt=txt)
        if txt_en:
            p["statusTxt_en"] = txt_en
        return p


INICIO_ANO = int(B.INICIO[:4])
NORMAS_DESDE_ANO = INICIO_ANO - 1  # as normas guardadas começam no ano anterior ao mandato (a última lei de antes)


def _menos_dias(data: str, n: int) -> str:
    return (dt.date.fromisoformat(data[:10]) - dt.timedelta(days=n)).isoformat()


def _data_br(d: str) -> str:
    """AAAA-MM-DD -> DD%2FMM%2FAAAA (formato dos formulários de pesquisa do SAPL, já pronto para a URL)."""
    return urllib.parse.quote(f"{d[8:10]}/{d[5:7]}/{d[:4]}", safe="")


def _vazios(lo: int, hi: int, presentes) -> list[tuple[int, int]]:
    """Os pedaços seguidos de números entre lo e hi (inclusive) que não estão em `presentes`."""
    out, x = [], lo
    while x <= hi:
        if x in presentes:
            x += 1
            continue
        y = x
        while y + 1 <= hi and y + 1 not in presentes:
            y += 1
        out.append((x, y))
        x = y + 1
    return out


def _conferir_leis(lista: list[dict], antes: list[dict], comp: set, inicio: str, h: str) -> dict:
    """Confere se as leis do período cadastradas no SAPL parecem completas, olhando a numeração principal inteira (a mesma
    régua da contagem pelos Diários Oficiais). Até 26/10/2026 só se contavam os buracos entre números vizinhos de cada ano e
    a "lei mais nova" podia ser uma lei solta: passavam cadastros que pararam no meio do mandato (Alpinópolis/MG, Rodolfo
    Fernandes/RN) ou que começaram tarde (Coronel Ezequiel/RN), e a mesma lei cadastrada duas vezes contava duas.
    - a mesma lei cadastrada duas vezes ("2551" e "2.551", ou como ordinária e como complementar) conta uma vez;
    - ordinárias e complementares formam uma numeração só quando os números se misturam; senão, duas. A **numeração
      principal** é a que tem mais leis (quase sempre a das ordinárias); as outras só entram na contagem;
    - a numeração principal segue de um ano para o outro, ou recomeça a cada ano (só quando há evidência: os dois anos com
      3 leis ou mais, e o ano seguinte começando num número até 10, menor que o último do ano anterior);
    - um salto de mais de LEIS_SALTO números separa outra numeração ou um erro de digitação (ex.: uma "Lei 1/2026" no meio
      das leis 985 a 1004): vale a sequência principal, e um número solto assim não conta;
    - uma lei do período com número abaixo de 3 ou mais leis de antes está fora da sequência (data ou número digitado
      errado, ou uma lei de antes publicada já no período): conta, mas não marca onde a numeração do período começa; e um
      número que é de uma lei de antes não "falta" no período;
    - o começo: a 1ª lei do período tem de vir logo depois da última de antes (o estado guarda as normas desde o ano anterior
      ao mandato); numeração que recomeça a cada ano começa em 1; sem saber a de antes, estima-se pelo ritmo de leis quantas
      faltariam entre o começo do período (descontado o recesso, LEIS_RECESSO_DIAS) e a 1ª cadastrada;
    - o fim: pelo ritmo de leis da numeração principal, quantas deveriam ter vindo depois da última cadastrada até hoje,
      descontado o atraso normal de cadastro (LEIS_LAG_DIAS) (e, quando a numeração recomeça a cada ano, depois da última de
      cada ano até 31 de dezembro).
    Devolve {"conta": normas -> quantas leis diferentes (sem as repetidas nem os números soltos), "distintas", "faltam" e
    "faixa" (na numeração principal, com as estimadas), "estimadas", "fim" (as estimadas no fim), "buraco" ((de, até) do
    maior pedaço seguido que falta na numeração principal, ou None), "ultima" (a lei mais nova que conta),
    "ultima_principal" (a mais nova da numeração principal)}."""
    def num(n):
        return _numero(n.get("numero"))

    def data(n):
        return (n.get("data") or "")[:10]

    def corridas(nums: list[int]) -> list[list[int]]:
        out = [[nums[0]]]
        for a, b in zip(nums, nums[1:]):
            if b - a > LEIS_SALTO:
                out.append([b])
            else:
                out[-1].append(b)
        return out

    def principal(nums) -> list[int]:
        return max(corridas(sorted(set(nums))), key=len)

    todas = [n for n in lista + antes if num(n) is not None]
    lo = [n for n in todas if n.get("tipo") not in comp]
    lc = [n for n in todas if n.get("tipo") in comp]
    juntas = False
    if lo and lc:
        pl = principal([num(n) for n in lo])
        juntas = sum(1 for n in lc if pl[0] <= num(n) <= pl[-1]) >= 0.5 * len(lc)

    def seq(n):
        return "L" if juntas or n.get("tipo") not in comp else "C"

    no_periodo = {}
    for n in lista:
        if num(n) is not None:
            no_periodo[seq(n)] = no_periodo.get(seq(n), 0) + 1
    s0 = max(no_periodo, key=no_periodo.get) if no_periodo else None  # a numeração principal
    recomeca = {}
    for s in {seq(n) for n in todas}:
        por_ano: dict[int, list] = {}
        for n in todas:
            if seq(n) == s and n.get("ano"):
                por_ano.setdefault(int(n["ano"]), []).append(num(n))
        pr = {y: principal(v) for y, v in por_ano.items()}
        anos = sorted(pr)
        if s == s0:
            recomeca[s] = any(len(pr[y1]) >= 3 and len(pr[y2]) >= 3 and pr[y2][0] <= 10 and pr[y2][0] < pr[y1][-1]
                              for y1, y2 in zip(anos, anos[1:]))
        else:
            recomeca[s] = True  # nas outras numerações, o mesmo número em anos diferentes são leis diferentes

    def chave(n):
        x = num(n)
        if x is None:
            return ("?", n.get("tipo"), n.get("numero"), n.get("ano"), data(n))
        s = seq(n)
        return (s, int(n.get("ano") or 0) if recomeca[s] else None, x)

    grupos: dict[tuple, dict[int, str]] = {}  # (numeração, ano se recomeça) -> {número: data mais antiga}
    for n in todas:
        k = chave(n)
        g = grupos.setdefault(k[:2], {})
        g[k[2]] = min(g.get(k[2], data(n)), data(n))
    validos: dict[tuple, set] = {}
    pedacos = []
    maior = None
    for g, datas in grupos.items():
        s, ano = g
        if s != s0:  # as outras numerações (em geral, as complementares): só a contagem
            validos[g] = {x for x, d in datas.items() if d >= inicio}
            continue
        cs = [c for c in corridas(sorted(datas)) if any(datas[x] >= inicio for x in c)]
        if not cs:
            continue
        run = max(cs, key=lambda c: sum(1 for x in c if datas[x] >= inicio))
        P = [x for x in run if datas[x] >= inicio]
        validos[g] = set(P) | {x for c in cs if c is not run and sum(1 for y in c if datas[y] >= inicio) >= 3
                               for x in c if datas[x] >= inicio}
        # uma lei do período com número abaixo de 3 ou mais leis de antes está fora da sequência (data ou número digitado
        # errado, ou uma lei de antes publicada já no período: Boa Vista/RR, a 2814 "de 23/4/2026" no meio das leis de
        # março): conta, mas não marca onde a numeração do período começa (senão as leis de antes no meio dela "faltariam")
        antes_run = [x for x in run if datas[x] < inicio]
        Ps = [x for x in P if len(antes_run) - bisect.bisect_right(antes_run, x) < 3] or P
        A = [x for x in antes_run if x < Ps[0]]
        if A:
            comeco = (A[-1] + 1, Ps[0] - 1)
        elif recomeca[s] and ano and inicio <= f"{ano}-01-01":
            comeco = (1, Ps[0] - 1)
        else:
            comeco = None  # não dá para saber onde a numeração do período começa: estimado pelo ritmo
        # faltam os números que nenhuma lei tem (um número que é de uma lei de antes não falta)
        faltando = [v for a, b in zip(Ps, Ps[1:]) for v in _vazios(a + 1, b - 1, datas)]
        if comeco:
            faltando += _vazios(comeco[0], comeco[1], datas)
        for a, b in faltando:
            if maior is None or b - a > maior[1] - maior[0]:
                maior = (a, b)
        pedacos.append({"ano": ano, "p": Ps[0], "u": Ps[-1], "comeco": comeco is not None,
                        "dp": min(datas[x] for x in Ps), "du": max(datas[x] for x in Ps),
                        "faltam": sum(b - a + 1 for a, b in faltando),
                        "faixa": Ps[-1] - Ps[0] + 1 + (max(0, comeco[1] - comeco[0] + 1) if comeco else 0)})

    def conta(ns) -> int:
        ks = set()
        for n in ns:
            k = chave(n)
            if k[0] == "?" or k[2] in validos.get(k[:2], ()):
                ks.add(k)
        return len(ks)

    contam = [n for n in lista if num(n) is None or num(n) in validos.get(chave(n)[:2], ())]
    res = {"conta": conta, "distintas": conta(lista), "faltam": 0, "faixa": 0, "estimadas": 0, "fim": 0, "buraco": maior,
           "ultima": max((data(n) for n in contam), default=""), "ultima_principal": ""}
    if not pedacos:
        return res
    ps = sorted(pedacos, key=lambda p: p["dp"])
    dias = (dt.date.fromisoformat(max(p["du"] for p in ps)) - dt.date.fromisoformat(ps[0]["dp"])).days
    ritmo = sum(p["u"] - p["p"] + 1 for p in ps) / max(30, dias)  # leis por dia na numeração principal
    est = 0.0
    if not ps[0]["comeco"]:
        est += ritmo * max(0, (dt.date.fromisoformat(ps[0]["dp"]) - dt.date.fromisoformat(inicio)).days - LEIS_RECESSO_DIAS)
    if recomeca[s0]:
        for p in ps[:-1]:
            est += ritmo * max(0, (dt.date(p["ano"], 12, 31) - dt.date.fromisoformat(p["du"])).days)
    fim = ritmo * max(0, (dt.date.fromisoformat(h) - dt.date.fromisoformat(ps[-1]["du"])).days - LEIS_LAG_DIAS)
    res["fim"] = round(fim)
    res["estimadas"] = round(est + fim)
    res["faltam"] = sum(p["faltam"] for p in ps) + res["estimadas"]
    res["faixa"] = sum(p["faixa"] for p in ps) + res["estimadas"]
    res["ultima_principal"] = max(p["du"] for p in ps)
    return res


__all__ = ["Sapl", "SemOrcamento", "FiltroIgnorado", "ORCAMENTO", "tipo_por_descricao", "tipo_de_veto", "status_de_veto", "eh_lei"]
