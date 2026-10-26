"""Rede educada para o mapa das cidades (scripts/municipios/mapear.py).

- Um User-Agent que diz quem somos (comum.UA).
- robots.txt de cada site, lido uma vez por rodada (RFC 9309: 4xx = pode ler; 5xx ou sem resposta = não lê nada).
  "Crawl-delay" é respeitado.
- Pausa entre dois pedidos ao mesmo site (PAUSA, ou o crawl-delay) e no máximo POR_IP pedidos ao mesmo tempo para o mesmo
  servidor (muitos sites de Câmaras e prefeituras ficam no mesmo servidor de um fornecedor).
- Tempo limite curto, no máximo MAX_BYTES por página, redirecionamentos seguidos à mão (o robots.txt do site de destino
  também vale).
- Muitos sites de prefeituras têm certificado vencido ou incompleto, ou só falam TLS antigo: nesses casos a página pública
  é lida sem conferir o certificado (nada é enviado; só se lê a página) e isso fica anotado (Resposta.tls = False).
"""
from __future__ import annotations

import gzip
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comum import UA  # noqa: E402

PAUSA = 1.0          # segundos entre dois pedidos ao mesmo site
POR_IP = 2           # pedidos ao mesmo tempo para o mesmo servidor (IP)
INTERVALO_IP = 0.5   # segundos entre dois pedidos ao mesmo servidor (vários sites de um fornecedor no mesmo IP)
FALHAS_SEGUIDAS = 6  # recusas/silêncios seguidos de um servidor antes de deixá-lo em paz pelo resto da rodada
TIMEOUT = 12         # segundos por operação de rede
TOTAL = 25           # segundos no máximo para baixar uma página
MAX_BYTES = 3_000_000
MAX_REDIRECIONAMENTOS = 6
MAX_ATRASO = 120     # "Crawl-delay" maior que isso: o site não é lido
TOKEN_ROBOTS = "EntendaPolitica"


def _ctx_seguro() -> ssl.SSLContext:
    return ssl.create_default_context()


def _ctx_antigo() -> ssl.SSLContext:
    """Sem conferir o certificado e aceitando TLS antigo (só para ler páginas públicas)."""
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    try:
        c.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    try:
        c.minimum_version = ssl.TLSVersion.TLSv1
    except (ValueError, AttributeError):
        pass
    c.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return c


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENERS = {
    "seguro": urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ctx_seguro()), _SemRedirecionar),
    "antigo": urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ctx_antigo()), _SemRedirecionar),
}


@dataclass
class Resposta:
    url: str                      # endereço pedido
    final: str                    # endereço depois dos redirecionamentos
    status: int | None = None
    tipo: str = ""
    corpo: bytes = b""
    charset: str | None = None
    erro: str | None = None       # "dns", "robots", "timeout", "tls", "conexao", "http 403"...
    tls: bool = True              # False = certificado não conferido
    cortado: bool = False
    caminho: list = field(default_factory=list)   # redirecionamentos

    @property
    def ok(self) -> bool:
        return self.erro is None and self.status is not None and 200 <= self.status < 300


def host_de(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


class Rede:
    def __init__(self, pausa: float = PAUSA, por_ip: int = POR_IP):
        self.pausa = pausa
        self._lock = threading.Lock()
        self._dns: dict[str, str | None] = {}
        self._proximo: dict[str, float] = {}
        self._sem_ip: dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(por_ip))
        self._ip_prox: dict[str, float] = {}         # intervalo mínimo entre pedidos ao mesmo servidor
        self._ip_falhas: dict[str, int] = defaultdict(int)
        self.suspensos: dict[str, str] = {}          # servidor (IP) -> por quê (parou de responder ou recusou)
        self._robots: dict[str, tuple] = {}          # "https://host" -> (parser | "tudo" | "nada", atraso)
        self._robots_lock: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.robots_txt: dict[str, str] = {}         # "https://host" -> começo do robots.txt (para agrupar fornecedores)
        self.pedidos = 0

    # ------------------------------------------------------------------ disjuntor por servidor
    # Um servidor que hospeda muitos sites (de um fornecedor) e começa a recusar (403/429) ou a não responder é deixado
    # em paz pelo resto da rodada: os sites dele ficam como "não respondeu" e são conferidos na próxima rodada.
    def _anotar(self, ip: str, r: "Resposta"):
        ruim = r.erro in ("timeout", "conexao") or r.status in (403, 429, 503)
        with self._lock:
            if ruim:
                self._ip_falhas[ip] += 1
                if self._ip_falhas[ip] >= FALHAS_SEGUIDAS and ip not in self.suspensos:
                    self.suspensos[ip] = r.erro or f"http {r.status}"
            else:
                self._ip_falhas[ip] = 0

    def _esperar_ip(self, ip: str):
        while True:
            with self._lock:
                agora = time.time()
                prox = self._ip_prox.get(ip, 0)
                if agora >= prox:
                    self._ip_prox[ip] = agora + INTERVALO_IP
                    return
                falta = prox - agora
            time.sleep(min(falta, 2))

    # ------------------------------------------------------------------ DNS
    def ip(self, host: str) -> str | None:
        host = (host or "").lower().strip(".")
        if not host:
            return None
        with self._lock:
            if host in self._dns:
                return self._dns[host]
        try:
            info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            r = info[0][4][0] if info else None
        except (OSError, UnicodeError, ValueError):
            r = None
        with self._lock:
            self._dns[host] = r
        return r

    # ------------------------------------------------------------------ ritmo
    def _esperar_vez(self, host: str, atraso: float):
        while True:
            with self._lock:
                agora = time.time()
                prox = self._proximo.get(host, 0)
                if agora >= prox:
                    self._proximo[host] = agora + max(self.pausa, atraso)
                    return
                falta = prox - agora
            time.sleep(min(falta, 5))

    # ------------------------------------------------------------------ um pedido (sem seguir redirecionamento)
    def _um(self, url: str, ua: str, aceitar: str, max_bytes: int, extra: dict | None = None,
            conta: bool = True) -> Resposta:
        host = host_de(url)
        ip = self.ip(host)
        if ip and ip in self.suspensos:
            return Resposta(url=url, final=url, erro="suspenso")
        if ip:
            self._esperar_ip(ip)
        r = self._um_cru(url, ua, aceitar, max_bytes, extra)
        if ip and (conta or r.erro in ("timeout", "conexao")):
            self._anotar(ip, r)
        return r

    def _um_cru(self, url: str, ua: str, aceitar: str, max_bytes: int, extra: dict | None = None) -> Resposta:
        r = Resposta(url=url, final=url)
        host = host_de(url)
        ip = self.ip(host)
        if not ip:
            r.erro = "dns"
            return r
        hdr = {"User-Agent": ua, "Accept": aceitar, "Accept-Encoding": "gzip, deflate",
               "Accept-Language": "pt-BR,pt;q=0.9"}
        hdr.update(extra or {})
        tentativas = ["seguro", "antigo"] if url.startswith("https:") else ["seguro"]
        for modo in tentativas:
            with self._sem_ip[ip]:
                with self._lock:
                    self.pedidos += 1
                inicio = time.time()
                try:
                    req = urllib.request.Request(url, headers=hdr)
                    with _OPENERS[modo].open(req, timeout=TIMEOUT) as resp:
                        r.status = resp.status
                        r.tipo = resp.headers.get("Content-Type") or ""
                        r.charset = resp.headers.get_content_charset()
                        partes, n = [], 0
                        while True:
                            bloco = resp.read(65536)
                            if not bloco:
                                break
                            partes.append(bloco)
                            n += len(bloco)
                            if n >= max_bytes or time.time() - inicio > TOTAL:
                                r.cortado = True
                                break
                        corpo = b"".join(partes)
                        enc = (resp.headers.get("Content-Encoding") or "").lower()
                    r.corpo = _descomprimir(corpo, enc)
                    r.tls = modo == "seguro"
                    r.erro = None
                    return r
                except urllib.error.HTTPError as e:
                    r.status = e.code
                    r.tipo = (e.headers.get("Content-Type") or "") if e.headers else ""
                    if 300 <= e.code < 400:
                        loc = (e.headers.get("Location") or "") if e.headers else ""
                        r.final = urllib.parse.urljoin(url, loc.strip()) if loc else url
                        r.erro = "redir"
                    else:
                        r.erro = f"http {e.code}"
                        try:
                            enc = ((e.headers.get("Content-Encoding") or "") if e.headers else "").lower()
                            r.corpo = _descomprimir(e.read(200_000), enc)
                        except Exception:
                            pass
                    try:
                        e.close()
                    except Exception:
                        pass
                    r.tls = modo == "seguro"
                    return r
                except (ssl.SSLError, ssl.CertificateError):
                    r.erro = "tls"
                    r.status = None
                    continue
                except urllib.error.URLError as e:
                    motivo = e.reason
                    if isinstance(motivo, (ssl.SSLError, ssl.CertificateError)):
                        r.erro = "tls"
                        continue
                    if isinstance(motivo, (socket.timeout, TimeoutError)):
                        r.erro = "timeout"
                    elif isinstance(motivo, socket.gaierror):
                        r.erro = "dns"
                    else:
                        r.erro = "conexao"
                    return r
                except (socket.timeout, TimeoutError):
                    r.erro = "timeout"
                    return r
                except Exception:  # conexão cortada, resposta inválida...
                    r.erro = "conexao"
                    return r
        return r

    # ------------------------------------------------------------------ robots.txt
    def robots(self, url: str, ua: str = UA) -> tuple[bool, float]:
        """(pode ler, atraso em segundos) para este endereço, segundo o robots.txt do site."""
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}".lower()
        with self._robots_lock[base]:
            if base not in self._robots:
                self._robots[base] = self._ler_robots(base, ua)
        regra, atraso = self._robots[base]
        if regra == "tudo":
            return True, atraso
        if regra == "nada":
            return False, atraso
        try:
            return regra.can_fetch(TOKEN_ROBOTS, url), atraso
        except Exception:
            return True, atraso

    def robots_estado(self, url: str) -> str:
        """'tudo', 'nada' (sem resposta) ou 'regras' — para explicar por que um site não foi lido."""
        p = urllib.parse.urlsplit(url)
        regra = self._robots.get(f"{p.scheme}://{p.netloc}".lower(), ("?", 0))[0]
        return regra if isinstance(regra, str) else "regras"

    def robots_marca(self, url: str) -> str | None:
        """Os caminhos fechados do robots.txt (agrupa sites do mesmo fornecedor que fecham para robôs)."""
        p = urllib.parse.urlsplit(url)
        txt = self.robots_txt.get(f"{p.scheme}://{p.netloc}".lower())
        if not txt:
            return None
        caminhos = sorted({m.strip() for m in re.findall(r"(?im)^\s*disallow:\s*(\S+)", txt)})
        return " ".join(caminhos)[:160] or None

    def _ler_robots(self, base: str, ua: str):
        host = host_de(base)
        if not self.ip(host):
            return ("nada", 0.0)
        self._esperar_vez(host, 0)
        atual = base + "/robots.txt"
        r = None
        for _ in range(4):
            r = self._um(atual, ua, "text/plain,*/*;q=0.5", 300_000, conta=False)
            if r.erro == "redir" and r.final and r.final != atual:
                atual = r.final
                if host_de(atual) != host:
                    self._esperar_vez(host_de(atual), 0)
                continue
            break
        if r is None or r.erro in ("dns", "timeout", "conexao", "tls", "suspenso"):
            return ("nada", 0.0)      # RFC 9309: sem resposta = não lê
        if r.status is not None and r.status >= 500:
            return ("nada", 0.0)
        if r.status is None or r.status >= 400 or r.erro == "redir":
            return ("tudo", 0.0)      # RFC 9309: 4xx = pode ler tudo
        texto = r.corpo.decode("utf-8", "replace")
        if "<html" in texto[:3000].lower() or "<!doctype" in texto[:300].lower():
            return ("tudo", 0.0)      # o site devolve uma página no lugar do robots.txt: não há regras
        with self._lock:
            self.robots_txt[base] = texto[:2000]
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(texto.splitlines())
        try:
            atraso = float(rp.crawl_delay(TOKEN_ROBOTS) or 0)
        except Exception:
            atraso = 0.0
        if atraso > MAX_ATRASO:
            return ("nada", atraso)   # pede mais de MAX_ATRASO segundos entre pedidos: não lemos o site
        with self._lock:              # o intervalo pedido vale também depois de ler o próprio robots.txt
            self._proximo[host] = max(self._proximo.get(host, 0), time.time() + atraso)
            # www.x -> x: o robots.txt lido vale também para o endereço final (economiza um pedido)
            p = urllib.parse.urlsplit(atual)
            outra = f"{p.scheme}://{p.netloc}".lower()
            if outra != base and outra not in self._robots:
                self._robots[outra] = (rp, atraso)
        return (rp, atraso)

    # ------------------------------------------------------------------ uma página, com redirecionamentos e robots
    def pagina(self, url: str, ua: str = UA, aceitar: str = "text/html,application/xhtml+xml,*/*;q=0.8",
               max_bytes: int = MAX_BYTES, respeitar_robots: bool = True, extra: dict | None = None) -> Resposta:
        atual = url
        caminho = []
        for _ in range(MAX_REDIRECIONAMENTOS):
            atraso = 0.0
            if respeitar_robots:
                pode, atraso = self.robots(atual, ua)
                if not pode:
                    return Resposta(url=url, final=atual, erro="robots", caminho=caminho)
            host = host_de(atual)
            if not self.ip(host):
                return Resposta(url=url, final=atual, erro="dns", caminho=caminho)
            self._esperar_vez(host, atraso)
            r = self._um(atual, ua, aceitar, max_bytes, extra)
            if r.erro == "redir" and r.final and r.final != atual:
                caminho.append(r.final)
                atual = r.final
                continue
            r.url, r.final, r.caminho = url, atual, caminho
            return r
        return Resposta(url=url, final=atual, erro="redirecionamentos", caminho=caminho)


def _descomprimir(corpo: bytes, enc: str) -> bytes:
    if not corpo:
        return corpo
    try:
        if "gzip" in enc or corpo[:2] == b"\x1f\x8b":
            try:
                return gzip.decompress(corpo)
            except Exception:
                return zlib.decompressobj(47).decompress(corpo)   # gzip cortado: o que der
        if "deflate" in enc:
            try:
                return zlib.decompress(corpo)
            except zlib.error:
                return zlib.decompress(corpo, -15)
    except Exception:
        return corpo
    return corpo
