"""Leitura das páginas iniciais (HTML) e das pistas que elas dão: quem é o dono do site (Câmara ou prefeitura, de que
cidade), o sistema de propostas, o pedido de informação (e-SIC), o portal da transparência e o Diário Oficial.

Só biblioteca padrão (html.parser). Nada aqui faz pedidos de rede.
"""
from __future__ import annotations

import html
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser


# ---------------------------------------------------------------------------------------------------- texto
def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    """'Santa Bárbara d'Oeste' -> 'santa barbara d oeste' (sem acento, minúsculas, só letras e números)."""
    s = sem_acento(html.unescape(s or "")).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def compacto(s: str) -> str:
    return norm(s).replace(" ", "")


PREPOSICOES = {"de", "da", "do", "das", "dos", "d", "e"}


def slugs_cidade(nome: str) -> list[str]:
    """Formas do nome que as cidades usam nos endereços: 'Santa Bárbara d'Oeste' -> ['santabarbaradoeste',
    'santabarbaraoeste']; 'São João del-Rei' -> ['saojoaodelrei']."""
    n = norm(nome)
    out = [n.replace(" ", "")]
    sem_prep = "".join(p for p in n.split() if p not in PREPOSICOES)
    if sem_prep and sem_prep not in out and len(sem_prep) >= 4:
        out.append(sem_prep)
    return out


def nome_curto(nome: str) -> list[str]:
    """Nomes curtos que algumas cidades usam no endereço: 'São Luiz do Anauá' -> ['sao luiz'] (as palavras antes do
    primeiro 'do/da/de/dos/das/d''); 'Nossa Senhora do Socorro' -> ['socorro'] (o que vem depois de 'Nossa Senhora
    do'). Quem usa precisa conferir que nenhuma outra cidade do estado tem o mesmo nome curto."""
    palavras = norm(nome).split()
    out = []
    if len(palavras) >= 4 and palavras[0] == "nossa" and palavras[1] == "senhora" and palavras[2] in PREPOSICOES:
        resto = " ".join(palavras[3:])
        if len(resto.replace(" ", "")) >= 5:
            out.append(resto)
    for i, p in enumerate(palavras):
        if i >= 1 and p in ("do", "da", "de", "dos", "das", "d"):
            curto = " ".join(palavras[:i])
            if len(curto.replace(" ", "")) >= 5 and curto not in ("nossa senhora", "santa", "santo", "sao"):
                out.append(curto)
            break
    return out


def tem_cidade(texto_norm: str, nome: str) -> bool:
    """O texto (já normalizado) fala da cidade? Palavra inteira; nomes longos valem também sem espaços."""
    n = norm(nome)
    if not n:
        return False
    if re.search(r"(^| )" + re.escape(n) + r"( |$)", texto_norm):
        return True
    comp = n.replace(" ", "")
    return len(comp) >= 7 and comp in texto_norm.replace(" ", "")


# ---------------------------------------------------------------------------------------------------- HTML
class _Leitor(HTMLParser):
    IGNORAR = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titulo = []
        self.no_titulo = False
        self.metas: dict[str, str] = {}
        self.links: list[list] = []           # [href, texto, atributos]
        self._a: list | None = None
        self.textos: list[str] = []
        self.ignorando = 0
        self.scripts: list[str] = []
        self.frames: list[str] = []
        self.base: str | None = None
        self.h1: list[str] = []
        self._h = 0
        self.alts: list[str] = []
        self.tam = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.IGNORAR:
            self.ignorando += 1
            if tag == "script" and a.get("src"):
                self.scripts.append(a["src"])
            return
        if tag == "title":
            self.no_titulo = True
        elif tag == "meta":
            chave = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if chave and chave not in self.metas:
                self.metas[chave] = a.get("content", "")
        elif tag == "base" and a.get("href") and not self.base:
            self.base = a["href"]
        elif tag == "a":
            if self._a is not None:
                self.links.append(self._a)
            extra = " ".join(a.get(k, "") for k in ("title", "aria-label"))
            self._a = [a.get("href", ""), extra, ""]
        elif tag in ("frame", "iframe") and a.get("src"):
            self.frames.append(a["src"])
        elif tag == "img":
            alt = (a.get("alt") or a.get("title") or "").strip()
            if alt:
                if self._a is not None:
                    self._a[1] += " " + alt
                if len(self.alts) < 60:
                    self.alts.append(alt)
        elif tag == "h1":
            self._h += 1
        elif tag == "link" and "canonical" in a.get("rel", "").lower() and a.get("href"):
            self.metas.setdefault("canonical", a["href"])

    def handle_endtag(self, tag):
        if tag in self.IGNORAR:
            self.ignorando = max(0, self.ignorando - 1)
            return
        if tag == "title":
            self.no_titulo = False
        elif tag == "a" and self._a is not None:
            self.links.append(self._a)
            self._a = None
        elif tag == "h1":
            self._h = max(0, self._h - 1)

    def handle_data(self, data):
        if self.no_titulo:
            self.titulo.append(data)
            return
        if self.ignorando:
            return
        d = data.strip()
        if not d:
            return
        if self._a is not None:
            self._a[1] += " " + d
        if self._h and len(self.h1) < 10:
            self.h1.append(d)
        if self.tam < 400_000:
            self.textos.append(d)
            self.tam += len(d) + 1


@dataclass
class Pagina:
    url: str
    titulo: str = ""
    gerador: str = ""
    nome_site: str = ""
    h1: str = ""
    alts: str = ""
    texto: str = ""                  # texto visível, normalizado (norm)
    cru: str = ""                    # texto visível sem acento e em minúsculas, com a pontuação ("12/2025")
    bruto: str = ""                  # HTML em minúsculas (para marcas de fornecedor)
    links: list = field(default_factory=list)   # [(url absoluta, texto normalizado, texto original)]
    scripts: list = field(default_factory=list)
    frames: list = field(default_factory=list)
    refresh: str | None = None
    js_redir: str | None = None
    rodape: str = ""

    def cabeca(self) -> str:
        """O que diz de quem é o site: título, nome do site, logotipo e o primeiro título da página."""
        return norm(" ".join([self.titulo, self.nome_site, self.h1, self.alts[:600]]))

    def so_navegador(self) -> bool:
        """Página montada por JavaScript no navegador (quase sem texto e sem links no HTML)."""
        return len(self.texto) < 800 and len(self.links) < 8 and (
            len(self.scripts) >= 2 or bool(re.search(r'id="(app|root|__next|__nuxt)"|ng-version|data-ww-app-mount|'
                                                     r'enable javascript|habilite o javascript|ative o javascript',
                                                     self.bruto[:300000])))


def decodificar(corpo: bytes, charset: str | None) -> str:
    cands = []
    if charset:
        cands.append(charset)
    m = re.search(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_\-]+)', corpo[:6000], re.I)
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    cands += ["utf-8", "cp1252"]
    for c in cands:
        try:
            return corpo.decode(c)
        except (LookupError, UnicodeDecodeError):
            continue
    return corpo.decode("utf-8", "replace")


_RODAPE = re.compile(r"(desenvolvid[oa] por|desenvolvimento:|powered by|produzid[oa] por|criad[oa] por)"
                     r"\s*[:\-–]?\s*(.{2,60})", re.I)


def ler(corpo: bytes, charset: str | None, url: str) -> Pagina:
    texto_html = decodificar(corpo, charset)
    leitor = _Leitor()
    try:
        leitor.feed(texto_html)
        leitor.close()
    except Exception:
        pass
    if leitor._a is not None:
        leitor.links.append(leitor._a)
    base = urllib.parse.urljoin(url, leitor.base) if leitor.base else url
    links = []
    vistos = set()
    for href, txt, _ in leitor.links:
        href = html.unescape((href or "").strip())
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "whatsapp:", "data:")):
            continue
        try:
            absoluto = urllib.parse.urljoin(base, href)
        except ValueError:
            continue
        if not absoluto.startswith(("http://", "https://")):
            continue
        original = re.sub(r"\s+", " ", txt).strip()
        metade = original.split(" ")
        if len(metade) % 2 == 0 and metade[: len(metade) // 2] == metade[len(metade) // 2:]:
            original = " ".join(metade[: len(metade) // 2])   # "Legislação Legislação" (title + texto do link)
        chave = (absoluto, original)
        if chave in vistos:
            continue
        vistos.add(chave)
        links.append((absoluto, norm(original), original[:120]))
    p = Pagina(url=url)
    p.titulo = re.sub(r"\s+", " ", " ".join(leitor.titulo)).strip()[:300]
    p.gerador = (leitor.metas.get("generator") or "")[:120]
    p.nome_site = (leitor.metas.get("og:site_name") or leitor.metas.get("application-name") or "")[:200]
    p.h1 = " ".join(leitor.h1)[:300]
    p.alts = " ".join(leitor.alts)[:2000]
    textos = " ".join(leitor.textos)
    p.texto = norm(textos)
    p.cru = sem_acento(textos[:400_000]).lower()
    p.bruto = texto_html[:2_000_000].lower()
    p.links = links
    p.scripts = [urllib.parse.urljoin(base, s) for s in leitor.scripts[:80]]
    p.frames = [urllib.parse.urljoin(base, s) for s in leitor.frames[:10]]
    ref = leitor.metas.get("refresh") or ""
    m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", ref, re.I)
    if m:
        p.refresh = urllib.parse.urljoin(base, m.group(1).strip())
    if len(textos) < 600:
        m = re.search(r"(?:window\.|document\.|top\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]|"
                      r"location\.replace\(\s*['\"]([^'\"]+)['\"]", texto_html[:20000])
        if m:
            p.js_redir = urllib.parse.urljoin(base, m.group(1) or m.group(2))
    rod = [m.group(0) for m in _RODAPE.finditer(textos[-6000:])]
    p.rodape = re.sub(r"\s+", " ", rod[-1]).strip()[:90] if rod else ""
    return p


# ---------------------------------------------------------------------------------------------------- de quem é o site
ESTACIONADO = re.compile(
    r"index of |it works|apache2? (ubuntu|debian)? ?default page|welcome to nginx|test page for|iis windows server|"
    r"plesk|cpanel|default web site page|account suspended|conta suspensa|site suspenso|dominio (registrado|disponivel)|"
    r"this domain (is|may be) for sale|domain parked|hospedagem de sites|hostgator|locaweb|site em construcao|"
    r"em construcao|under construction|coming soon|pagina nao encontrada|page not found|404 not found|403 forbidden|"
    r"service unavailable|bad gateway|website is offline|wordpress  instalacao|error establishing")

CAMARA = re.compile(r"\bcamara\b|\blegislativ[oa]\b|\bvereador(es|a|as)?\b|\bparlamento\b")
PREFEITURA = re.compile(r"\bprefeitura\b|\bprefeito\b|\bmunicipio de\b|\bgoverno municipal\b|\bpoder executivo\b|"
                        r"\badministracao municipal\b|\bgoverno de\b")


def dono(p: Pagina, nome_cidade: str) -> dict:
    """Pontua se a página é de Câmara ou de prefeitura e se fala da cidade."""
    cab = p.cabeca()
    tit = norm(p.titulo + " " + p.nome_site)
    corpo = p.texto[:60000]
    camara = 0
    prefeitura = 0
    if CAMARA.search(tit):
        camara += 10
    if PREFEITURA.search(tit):
        prefeitura += 10
    if re.search(r"camara municipal|poder legislativo|legislativo municipal|camara de vereadores", cab):
        camara += 6
    if re.search(r"prefeitura municipal|prefeitura de|municipio de|governo municipal", cab):
        prefeitura += 6
    camara += min(5, len(re.findall(r"camara municipal|vereador", corpo)))
    prefeitura += min(5, len(re.findall(r"prefeitura municipal|prefeitura de|secretaria municipal", corpo)))
    vazia = len(corpo) < 200 and not p.links
    estacionada = bool(ESTACIONADO.search(norm(p.titulo) + " " + corpo[:3000])) and len(p.links) < 40
    return {
        "camara": camara, "prefeitura": prefeitura,
        "cidadeNoTopo": tem_cidade(cab, nome_cidade),
        "cidade": tem_cidade(cab + " " + corpo[:120000], nome_cidade),
        "vazia": vazia, "estacionada": estacionada, "spa": p.so_navegador(),
    }


# ---------------------------------------------------------------------------------------------------- links úteis
def _melhor(p: Pagina, regras: list[tuple[int, re.Pattern, re.Pattern | None]], excluir: re.Pattern | None = None):
    """Link com maior peso. regras = [(peso, regex no texto do link, regex no endereço ou None)]."""
    melhor, peso_m = None, 0
    for url, txt, orig in p.links:
        alvo = url.lower()
        if excluir is not None and excluir.search(alvo):
            continue
        for peso, rtxt, rurl in regras:
            ok = (rtxt is not None and rtxt.search(txt)) or (rurl is not None and rurl.search(alvo))
            if ok and peso > peso_m:
                melhor, peso_m = url, peso
                break
    return melhor


_SIC = [
    (10, re.compile(r"\be ?sic\b|servico de informac(ao|oes) ao cidadao|sistema eletronico do servico de informac"),
     re.compile(r"/e-?sic\b|[/.]esic[./]|esic\.|e-sic\.|/sic/|/sic\b|sic\.|falabr\.cgu")),
    (8, re.compile(r"pedido(s)? de (acesso a )?informac|solicitac(ao|oes) de informac|solicite (uma )?informac"), None),
    (6, re.compile(r"acesso a informac(ao|oes)|lei de acesso|\blai\b"),
     re.compile(r"acesso-a-informac|acessoainformac|/lai\b|lei-de-acesso")),
    (3, re.compile(r"\bsic\b"), None),
]
_SIC_FORA = re.compile(r"gov\.br/acessoainformacao|acessoainformacao\.gov\.br|\.leg\.br/(transparencia|institucional)/?$|"
                       r"transparencia\.gov\.br|cgu\.gov\.br/(?!.*falabr)|radardatransparencia|atricon|"
                       r"\.(ac|al|am|ap|ba|ce|df|es|go|ma|mg|ms|mt|pa|pb|pe|pi|pr|rj|rn|ro|rr|rs|sc|se|sp|to)\.gov\.br/?$"
                       r"(?<=//www\.(ac|al))")


def achar_sic(p: Pagina) -> str | None:
    return _melhor(p, _SIC)


_TRANSP = [
    (10, re.compile(r"portal (da|de) transparencia"), None),
    (7, re.compile(r"\btransparencia\b"), re.compile(r"transparen")),
]
# portais de outros governos (estado, União, Tribunais de Contas, radar da Atricon) não são o da cidade
_TRANSP_FORA = re.compile(r"portaltransparencia\.gov\.br|//(www\.)?transparencia\.gov\.br|radardatransparencia|atricon|"
                          r"transparencia\.(ac|al|am|ap|ba|ce|df|es|go|ma|mg|ms|mt|pa|pb|pe|pi|pr|rj|rn|ro|rr|rs|sc|se|sp|to)"
                          r"\.gov\.br|//(www\.)?tce|//(www\.)?tcm|tce\.[a-z]{2}\.gov\.br|tcm\.[a-z]{2}\.gov\.br|"
                          r"//(www\.)?(portal\.)?(sp|mg|rj|ba)\.gov\.br|cgu\.gov\.br|gov\.br/cgu")


def achar_transparencia(p: Pagina) -> str | None:
    return _melhor(p, _TRANSP, _TRANSP_FORA)


_DIARIO = [
    (10, re.compile(r"diario oficial|diario eletronico|jornal oficial|imprensa oficial|diario do municipio|"
                    r"diario municipal|publicac(ao|oes) oficia"),
     re.compile(r"diariomunicipal\.|diariooficial|diario-oficial|diario_oficial|imprensa-?oficial|jornal-?oficial|"
                r"doem\.org|/diario\b|/diarios?/|atende\.net/diariooficial|dom\.[a-z0-9\-]+\.|/dom/?$|/dom\b")),
    (6, re.compile(r"\bdom\b|\bdoe\b|\bdoem\b|\bdome\b|\bdiario\b"), None),
]
_DIARIO_FORA = re.compile(r"in\.gov\.br|imprensanacional|pesquisa\.in\.gov|dou\.gov|portal\.in\.gov|"
                          r"diariodasleis|leismunicipais|jusbrasil|camara\.leg\.br/|senado\.leg\.br|"
                          r"tce\.[a-z]{2}\.gov\.br|tcm\.[a-z]{2}\.gov\.br|tce[a-z]{2}\.|"
                          r"youtube|facebook|instagram|twitter|whatsapp")


def achar_diario(p: Pagina) -> tuple[str, str] | tuple[None, None]:
    melhor, peso_m, txt_m = None, 0, ""
    for url, txt, orig in p.links:
        alvo = url.lower()
        if _DIARIO_FORA.search(alvo):
            continue
        for peso, rtxt, rurl in _DIARIO:
            if (rtxt.search(txt)) or (rurl is not None and rurl.search(alvo)):
                if "camara" in txt or "legislativ" in txt:
                    peso -= 3           # "Diário do Legislativo" da Câmara não é o da prefeitura
                if peso > peso_m:
                    melhor, peso_m, txt_m = url, peso, orig
                break
    return (melhor, txt_m) if melhor else (None, None)


_LEGISLACAO = [
    (10, re.compile(r"leis municipais|legislacao municipal|leis e decretos|atos normativos|atos oficiais"), None),
    (7, re.compile(r"\blegislacao\b|\bleis\b"), re.compile(r"legislac|/leis\b|leis-|/leis/|atos-oficiais")),
]
_LEG_FORA = re.compile(r"planalto\.gov\.br|leismunicipais|jusbrasil|camara\.leg\.br/|senado\.leg\.br|in\.gov\.br|"
                       r"youtube|facebook|instagram")


def achar_legislacao(p: Pagina) -> str | None:
    return _melhor(p, _LEGISLACAO, _LEG_FORA)


# ---------------------------------------------------------------------------------------------------- sistema de propostas
_SISTEMA = [
    ("sapl", re.compile(r"//sapl[0-9]*\.|/sapl(/|$)|sapl\.[a-z0-9\-]+\.(leg|gov)\.br")),
    ("sagl", re.compile(r"//sagl\.|/sagl(/|$)|openlegis|@@materias|/consultas/materia|publico\.[a-z0-9\-]+\.leg\.br")),
    ("nopaper", re.compile(r"camarasempapel|/spl/|sempapel\.")),
]
_PROPOSTAS = [
    (10, re.compile(r"\bproposic(ao|oes)\b|projetos? de lei|materias? legislativ|pesquisa(r)? (de )?materias?|"
                    r"consulta(r)? (de )?materias?|proposituras?|producao legislativa|sistema de apoio ao processo legislativo"),
     re.compile(r"proposic|propositura|materias?-?legislativas?|producao-?legislativa|projetos?-de-lei|pesquisar-materia|"
                r"consulta-?materia|/spl/|//sapl|/sapl/|//sagl")),
    (7, re.compile(r"processo legislativo|atividade legislativa|atividades legislativas|tramitac(ao|oes)"),
     re.compile(r"atividade-?legislativa|tramitac")),
    # 3ª linha: "Legislação", "Legislações e Atos" (às vezes têm os projetos de lei numa categoria)
    (4, re.compile(r"^(todas as )?legislac(ao|oes)( e atos| municipal)?$|^leis e atos$|^atos legislativos$"), None),
]
_PROP_FORA = re.compile(r"camara\.leg\.br/|senado\.leg\.br|al[a-z]{0,2}\.[a-z]{2}\.gov\.br|youtube|facebook|instagram|"
                        r"leismunicipais|planalto\.gov\.br|/noticias?/|/noticia[-_]|/post/|/blog/|/artigos?/|/news/|"
                        r"\.pdf($|\?)|\.docx?($|\?)")


def achar_sistemas(p: Pagina) -> list[tuple[str, str]]:
    """[(sistema, url)] dos links para SAPL, SAGL ou o SPL da Ágape (Câmara sem Papel)."""
    out = []
    for url, txt, orig in p.links:
        alvo = url.lower()
        for nome, rx in _SISTEMA:
            if rx.search(alvo):
                if nome == "sapl" and re.search(r"sapl ?jovem|saplj|parlamento jovem|mirim|juvenil|senior", txt + " " + alvo):
                    continue
                out.append((nome, url))
                break
    return out


def parece_noticia(url: str) -> bool:
    """Link para uma notícia ou um item (e não para a lista de proposições): último trecho do endereço muito longo
    ("projeto-de-lei-que-oficializa-..."), ou com número de item."""
    caminho = urllib.parse.urlsplit(url).path.rstrip("/")
    ultimo = caminho.rsplit("/", 1)[-1]
    return len(ultimo) > 45 or bool(re.search(r"/\d{3,}(/|$|-)|view/\d+", caminho)) or bool(
        re.search(r"[?&](id|cod)\w*=\d+", url.lower()))


def achar_propostas(p: Pagina, quantos: int = 1, com_peso: bool = False):
    """Link (ou os `quantos` melhores links) para a área de proposições. Só valem links de texto curto (menu), não
    manchetes de notícia."""
    cands = []
    for url, txt, orig in p.links:
        alvo = url.lower()
        if _PROP_FORA.search(alvo):
            continue
        t = txt.strip()
        for peso, rtxt, rurl in _PROPOSTAS:
            por_texto = len(t) <= 50 and rtxt.search(t)
            por_link = rurl is not None and rurl.search(alvo)
            if por_link and not por_texto and parece_noticia(url):
                continue   # link para UMA proposição (notícia, item), não para a lista
            if por_texto or por_link:
                if url not in [c[1] for c in cands]:
                    cands.append((peso if por_texto else peso - 1, url))
                break
    cands.sort(key=lambda c: -c[0])
    if com_peso:
        return cands[:quantos]
    if quantos == 1:
        return cands[0][1] if cands else None
    return [c[1] for c in cands[:quantos]]


def evidencia_propostas(p: Pagina, estrito: bool = False) -> str:
    """'recentes' (há projetos numerados de 2025 ou 2026), 'antigas' (só até 2024), 'navegador' (a página só se monta
    num navegador, com JavaScript) ou 'nenhuma'. `estrito`: o número tem de vir logo depois de "projeto"/"proposição"
    (para páginas de legislação, que também listam leis)."""
    t = p.cru
    if p.so_navegador():
        return "navegador"
    if estrito:
        anos = [int(a) for a in re.findall(r"(?:projetos? de (?:lei|resolucao|decreto)|proposic\w*|propositura)[^\n]{0,50}?"
                                           r"\b\d{1,4}(?:\.\d{3})?\s*/\s*(20[0-3]\d)\b", t)]
        anos += [int(a) for a in re.findall(r"(?:projetos? de (?:lei|resolucao|decreto)|proposic\w*|propositura)[^\n]{0,40}?"
                                            r"\bde\s+(20[0-3]\d)\b", t)]
        if any(a >= 2025 for a in anos):
            return "recentes"
        return "antigas" if anos else "nenhuma"
    if not re.search(r"projeto|proposic|propositura|materia|\bpl\b|\bplo\b|\bplc\b|\bple\b|\bpdl\b|\bplcm?\b", t):
        return "nenhuma"
    anos = [int(a) for a in re.findall(r"(?<![\d/.])\d{1,4}(?:\.\d{3})?\s*/\s*(20[0-3]\d)\b(?!\s*/)", t)]   # "12/2025", não datas
    anos += [int(a) for a in re.findall(r"(?:projeto|proposic|propositura|materia|\bpl[a-z]{0,2}|lei)[^\n]{0,40}?"
                                        r"\b(?:de|ano|exercicio)\s+(20[0-3]\d)\b", t)]
    if any(a >= 2025 for a in anos):
        return "recentes"
    if anos:
        return "antigas"
    return "nenhuma"


# ---------------------------------------------------------------------------------------------------- fornecedores
GERADORES = [
    ("Interlegis (Portal Modelo)", re.compile(r"plone")),
    ("WordPress", re.compile(r"wordpress")),
    ("Joomla", re.compile(r"joomla")),
    ("Drupal", re.compile(r"drupal")),
    ("Wix", re.compile(r"wix\.com")),
]
_SEM_LINKS = re.compile(r"""href\s*=\s*["'][^"']*["']""")
_SEM_SCRIPTS = re.compile(r"(?s)<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>")

FORNECEDORES = [
    ("Interlegis (Portal Modelo)", re.compile(r"portal modelo|interlegis")),
    ("Ágape (Câmara sem Papel)", re.compile(r"camarasempapel|agape sistemas|agapesistemas|nopaper")),
    ("OpenLegis (SAGL)", re.compile(r"openlegis|\bsagl\b")),
    ("Instar", re.compile(r"instar\.com\.br|instar tecnologia|\binstar\b")),
    ("IPM Sistemas (Atende.net)", re.compile(r"atende\.net|ipm sistemas|ipmsistemas")),
    ("Portal Fácil", re.compile(r"portalfacil|portal f[aá]cil")),
    ("Betha", re.compile(r"betha\.cloud|betha sistemas|bethasistemas")),
    ("Elotech", re.compile(r"elotech")),
    ("Fiorilli", re.compile(r"fiorilli")),
    ("GOVBR (Smarapd)", re.compile(r"smarapd")),
    ("Ecrie", re.compile(r"ecrie\.com|\becrie\b")),
    ("Siscam", re.compile(r"siscam")),
    ("Assessor Público", re.compile(r"assessorpublico|assessor p[uú]blico")),
    ("Portal TP", re.compile(r"portaltp\.com\.br")),
    ("Publicsoft", re.compile(r"publicsoft")),
    ("Govtech/Sino", re.compile(r"sinosistemas|sino sistemas")),
    ("Prodata", re.compile(r"prodata")),
    ("Siganet", re.compile(r"siganet")),
    ("Município Online", re.compile(r"municipioonline")),
    ("WeWeb", re.compile(r"ww-build-asset-prefix|data-ww-app-mount")),
    ("WordPress", re.compile(r"wp-content|wordpress")),
]


def fornecedor(p: Pagina, extra: str = "") -> str | None:
    """Quem fez o site ou o sistema: pelas marcas no HTML (gerador, rodapé, scripts), sem contar os links para outros
    sites (um link para o portal da transparência da Betha não quer dizer que o site é da Betha)."""
    bruto = _SEM_LINKS.sub("", _SEM_SCRIPTS.sub(" ", p.bruto[:200000] + " " + p.bruto[-200000:]))
    bruto = bruto[:30000] + " " + bruto[-60000:]
    alvo = " ".join([p.gerador.lower(), p.rodape.lower(), extra.lower(), " ".join(p.scripts).lower(), bruto])
    for nome, rx in FORNECEDORES:
        if rx.search(alvo):
            return nome
    g = p.gerador.lower()
    for nome, rx in GERADORES:
        if rx.search(g):
            return nome
    return None


_CDN = re.compile(r"google|gstatic|facebook|fbcdn|instagram|youtube|youtu\.be|twitter|//x\.com|cloudflare|jsdelivr|"
                  r"bootstrapcdn|fonts\.|jquery|cdnjs|unpkg|vlibras|whatsapp|wa\.me|tiktok|linkedin|flickr|spotify|"
                  r"radardatransparencia|atricon|userway|hotjar|crisp\.chat|tawk|addthis|sharethis|recaptcha|gravatar|"
                  r"wp\.com|w\.org|fontawesome|cookiebot|onetrust|doubleclick|clarity\.ms|apple\.com|play\.google")
_MARCA_RODAPE = re.compile(r"(desenvolv\w* por|desenvovido por|powered by|produzid[oa] por|criad[oa] por|"
                           r"©|&copy;|copyright)\s*[:\-–]?\s*(.{2,60})", re.I)


def marcas(p: Pagina) -> dict:
    """Marcas do fornecedor: gerador, frases do rodapé ("Desenvolvido por...", "© 2026 ...") e os domínios de fora
    (sem redes sociais, CDNs e governo) de onde a página carrega scripts ou para onde aponta."""
    fim = p.cru[-8000:]
    rod = []
    for m in _MARCA_RODAPE.finditer(fim):
        s = re.sub(r"\s+", " ", m.group(0)).strip()[:80]
        if s not in rod:
            rod.append(s)
    hosts, links = [], []
    for lista, destino in ((p.scripts + p.frames, hosts), ([x[0] for x in p.links], links)):
        for u in lista:
            h = (urllib.parse.urlsplit(u).hostname or "").lower()
            if (not h or _CDN.search(h) or h.endswith((".gov.br", ".leg.br", ".jus.br", ".mp.br", ".def.br"))
                    or h in destino):
                continue
            destino.append(h)
    # "hosts" = de onde a página carrega scripts/frames (é do fornecedor do site); "links" = para onde aponta (outros
    # fornecedores, como o do portal da transparência: só informativo)
    return {"gerador": p.gerador[:60], "rodape": rod[-4:], "hosts": hosts[:8], "links": links[:8]}


MARCAS_FORNECEDOR = [   # (nome, expressão nas marcas: gerador + rodapé + domínios)
    ("Interlegis (Portal Modelo)", r"plone|interlegis|portal modelo"),
    ("TLX Soluções", r"tlx solu|tlxsolucoes"),
    ("Datalins Informática", r"datalins"),
    ("JA Gestão e Tecnologia (7Focus)", r"ja - gest|7focus"),
    ("3Tecnos", r"3tecnos"),
    ("J.C. Softwares", r"j\.? ?c\.? softwares|jcsoftwares"),
    ("Marka System", r"marka ?system"),
    ("CamaraTech", r"camaratech"),
    ("Megasoft", r"megasoft"),
    ("Publicsoft", r"publicsoft"),
    ("Instar", r"instar"),
    ("IPM Sistemas (Atende.net)", r"atende\.net|ipm sistemas"),
    ("Portal Fácil", r"portalfacil|portal f[aá]cil"),
    ("Ágape", r"agape|camarasempapel"),
    ("Betha", r"betha"),
    ("Elotech", r"elotech"),
    ("Fiorilli", r"fiorilli"),
    ("GOVBR (Smarapd)", r"smarapd"),
    ("Ecrie", r"ecrie"),
    ("Siscam", r"siscam"),
    ("Assessor Público", r"assessorpublico|assessor p[uú]blico"),
    ("Portal TP", r"portaltp"),
    ("Sino Sistemas", r"sinosistemas|sino sistemas"),
    ("Município Online", r"municipioonline"),
    ("CR2", r"portalcr2|\bcr2\b"),
    ("Softcam", r"softcam"),
    ("WeWeb", r"weweb"),
    ("WordPress", r"wordpress"),
    ("Joomla", r"joomla"),
    ("Drupal", r"drupal"),
    ("Wix", r"wix\.com"),
]


def fornecedor_marcas(m: dict | None) -> str | None:
    if not m:
        return None
    alvo = " ".join([m.get("gerador") or ""] + list(m.get("rodape") or []) + list(m.get("hosts") or [])).lower()
    for nome, rx in MARCAS_FORNECEDOR:
        if re.search(rx, alvo):
            return nome
    return None


# ---------------------------------------------------------------------------------------------------- Diário Oficial
DOE_ESTADO = {
    "AC": "Diário Oficial do Estado do Acre", "AL": "Diário Oficial do Estado de Alagoas",
    "AM": "Diário Oficial do Estado do Amazonas", "AP": "Diário Oficial do Estado do Amapá",
    "BA": "Diário Oficial do Estado da Bahia", "CE": "Diário Oficial do Estado do Ceará",
    "ES": "Diário Oficial do Estado do Espírito Santo", "GO": "Diário Oficial do Estado de Goiás",
    "MA": "Diário Oficial do Estado do Maranhão", "MG": "Diário Oficial do Estado de Minas Gerais",
    "MS": "Diário Oficial do Estado de Mato Grosso do Sul", "MT": "Diário Oficial do Estado de Mato Grosso",
    "PA": "Diário Oficial do Estado do Pará", "PB": "Diário Oficial do Estado da Paraíba",
    "PE": "Diário Oficial do Estado de Pernambuco", "PI": "Diário Oficial do Estado do Piauí",
    "PR": "Diário Oficial do Estado do Paraná", "RJ": "Diário Oficial do Estado do Rio de Janeiro",
    "RN": "Diário Oficial do Estado do Rio Grande do Norte", "RO": "Diário Oficial do Estado de Rondônia",
    "RR": "Diário Oficial do Estado de Roraima", "RS": "Diário Oficial do Estado do Rio Grande do Sul",
    "SC": "Diário Oficial do Estado de Santa Catarina", "SE": "Diário Oficial do Estado de Sergipe",
    "SP": "Diário Oficial do Estado de São Paulo", "TO": "Diário Oficial do Estado do Tocantins",
}

# (regex no endereço, id da plataforma, nome da plataforma)
PLATAFORMAS = [
    (re.compile(r"diariomunicipal\.com\.br/"), "sigpub", "SIGPub (diariomunicipal.com.br)"),
    (re.compile(r"amm\.diariomunicipal\.org|diariomunicipal\.org/mt/amm"), "dexatec", "DexaTec (Jornal Oficial AMM-MT)"),
    (re.compile(r"diariomunicipal\.sc\.gov\.br"), "dom-sc", "DOM/SC (Consórcio CIGA)"),
    (re.compile(r"dio\.es\.gov\.br"), "dio-es", "DIO-ES (Imprensa Oficial do Espírito Santo)"),
    (re.compile(r"diariooficialms\.com\.br"), "assomasul", "Diário Oficial MS (Assomasul)"),
    (re.compile(r"famem\.org\.br|siganet\.net\.br"), "siganet", "Siganet"),
    (re.compile(r"atende\.net"), "atende", "IPM Sistemas (Atende.net)"),
    (re.compile(r"doem\.org\.br"), "doem", "DOEM"),
    (re.compile(r"\.io\.org\.br|imap\.org\.br"), "diof", "DIOF / IMAP"),
    (re.compile(r"municipioonline\.com\.br"), "municipioonline", "Município Online"),
    (re.compile(r"dosp\.com\.br|imprensaoficialmunicipal\.com\.br"), "dosp", "DOSP (Imprensa Oficial Municipal)"),
    (re.compile(r"diariooficialbr\.com\.br"), "diariooficialbr", "Diário Oficial BR"),
    (re.compile(r"dioenet\.com\.br"), "dioenet", "Dioenet (Plenus)"),
    (re.compile(r"barcodigital\.com\.br"), "barcodigital", "Barco Digital"),
    (re.compile(r"administracaopublica\.com\.br|transparenciadministrativa"), "administracaopublica", "Administração Pública"),
    (re.compile(r"portaldatransparencia\.com\.br"), "ptio", "Portal da Transparência (PTIO)"),
    (re.compile(r"/diariooficial\.php|/jornal\.php"), "adiarios", "ADiários"),
    (re.compile(r"/portal/diario-oficial|/portal/diario_oficial"), "instar", "Instar"),
    (re.compile(r"/controllers/diario_oficial"), "portalgov", "PortalGov"),
    (re.compile(r"portalfacil"), "portalfacil", "Portal Fácil"),
    (re.compile(r"betha\.cloud"), "betha", "Betha"),
    (re.compile(r"agapesistemas\.com\.br|sitesagapesistemas"), "agape", "Ágape (AgDiário)"),
]


def plataforma_diario(url: str) -> tuple[str, str]:
    alvo = (url or "").lower()
    for rx, pid, nome in PLATAFORMAS:
        if rx.search(alvo):
            return pid, nome
    return "propria", "Própria (site oficial)"


def eh_doe_estado(url: str, uf: str) -> bool:
    """Diário Oficial do Estado (ex.: diario.ac.gov.br, diariooficial.to.gov.br): um nome só antes de <uf>.gov.br.
    'diariooficial.<cidade>.to.gov.br' é o diário da própria cidade."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return bool(re.fullmatch(r"(www\.)?(diario|doe|diariooficial|imprensaoficial|ioe|io|iomat|dioe|dioems|ioepa|diof|"
                             r"dom|doweb|diarioficial|publicacoes)\." + re.escape(uf.lower()) + r"\.gov\.br", host))
