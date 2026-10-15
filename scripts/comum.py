"""Funções comuns dos coletores de dados do Entenda Política.

Só biblioteca padrão + Pillow (para as fotos). Todos os scripts importam daqui:

    from comum import *

Regras:
- Nunca invente dado. Sem informação = None.
- Todo bloco salvo leva uma fonte (use fonte()).
- salvar_json() só reescreve o arquivo se o conteúdo mudou (menos ruído no git).
"""
from __future__ import annotations

import datetime as _dt
import gzip
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
PESSOAS = DADOS / "pessoas"
SIMPLES = DADOS / "simples"
FOTOS = RAIZ / "img" / "pessoas"
CACHE = RAIZ / ".cache"
UA = "EntendaPolitica/1.0 (site educativo sem fins lucrativos; entendapolitica.vercel.app)"

for _p in (DADOS, PESSOAS, SIMPLES, FOTOS, CACHE):
    _p.mkdir(parents=True, exist_ok=True)

try:  # Windows: acentos no terminal
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- datas
def agora_br() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-3)))


def hoje() -> str:
    return agora_br().strftime("%Y-%m-%d")


def data_iso(v) -> str | None:
    """Converte '2023-03-01T10:00', '01/03/2023', '2023-03-01 10:00:00' em '2023-03-01'."""
    if not v:
        return None
    s = str(v).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "-".join(m.groups())
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{mth}-{d}"
    return None


def idade(nascimento: str | None, em: str | None = None) -> int | None:
    if not nascimento:
        return None
    n = _dt.date.fromisoformat(nascimento[:10])
    r = _dt.date.fromisoformat(em[:10]) if em else agora_br().date()
    return r.year - n.year - ((r.month, r.day) < (n.month, n.day))


# ---------------------------------------------------------------- texto
def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def chave_nome(s: str) -> str:
    """Para comparar nomes: maiúsculas, sem acento, sem pontuação, espaços simples."""
    s = sem_acento(s or "").upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slug(s: str) -> str:
    s = sem_acento(s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def limpa(s) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s or None


def nome_proprio(s: str | None) -> str | None:
    """'JOSÉ DA SILVA' -> 'José da Silva'; mantém siglas sem vogal ('JHC') e põe maiúscula depois de hífen/apóstrofo."""
    if not s:
        return None
    minusc = {"da", "de", "do", "das", "dos", "e", "di", "du", "del", "van", "von"}

    def palavra(p: str, primeira: bool) -> str:
        if not primeira and p in minusc:
            return p
        if re.fullmatch(r"[a-zç]{2,4}", p) and not re.search(r"[aeiouáéíóúâêôãõày]", p):
            return p.upper()  # sigla, ex.: JHC
        return re.sub(r"(^|[-'’])(\w)", lambda m: m.group(1) + m.group(2).upper(), p)

    return " ".join(palavra(p, i == 0) for i, p in enumerate(str(s).strip().lower().split()))


def fonte(veiculo: str, titulo: str, url: str, data: str | None = None) -> dict:
    return {"veiculo": veiculo, "titulo": titulo, "url": url, "data": data or hoje()}


# ---------------------------------------------------------------- rede
def baixar(url: str, destino: Path | str | None = None, max_idade_h: float | None = 20,
           tentativas: int = 5, timeout: int = 180, headers: dict | None = None,
           dados: bytes | None = None) -> bytes:
    """Baixa uma URL com novas tentativas. Se `destino` for dado, usa como cache em disco
    (reaproveita se tiver menos de `max_idade_h` horas; None = sempre reaproveita)."""
    if destino is not None:
        destino = Path(destino)
        if destino.exists() and destino.stat().st_size > 0:
            idade_h = (time.time() - destino.stat().st_mtime) / 3600
            if max_idade_h is None or idade_h < max_idade_h:
                return destino.read_bytes()
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    h.update(headers or {})
    erro = None
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=h, data=dados)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corpo = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    corpo = gzip.decompress(corpo)
            if destino is not None:
                destino.parent.mkdir(parents=True, exist_ok=True)
                tmp = destino.with_suffix(destino.suffix + ".part")
                tmp.write_bytes(corpo)
                os.replace(tmp, destino)
            return corpo
        except urllib.error.HTTPError as e:
            erro = e
            try:
                e.close()
            except Exception:
                pass
            if e.code in (400, 401, 403, 404, 410):
                break
        except Exception as e:  # rede instável
            erro = e
        time.sleep(min(60, 2 ** t * 2))
    raise RuntimeError(f"Falha ao baixar {url}: {erro}")


def baixar_json(url: str, cache: str | None = None, max_idade_h: float | None = 20, **kw):
    destino = CACHE / cache if cache else None
    h = {"Accept": "application/json"}
    h.update(kw.pop("headers", {}) or {})
    return json.loads(baixar(url, destino, max_idade_h=max_idade_h, headers=h, **kw).decode("utf-8-sig"))


def baixar_arquivo(url: str, nome_cache: str, max_idade_h: float | None = 20, **kw) -> Path:
    """Baixa um arquivo grande para .cache/ (por partes, sem guardar tudo na memória) e devolve o caminho."""
    destino = CACHE / nome_cache
    if destino.exists() and destino.stat().st_size > 0:
        idade_h = (time.time() - destino.stat().st_mtime) / 3600
        if max_idade_h is None or idade_h < max_idade_h:
            return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    erro = None
    for t in range(kw.get("tentativas", 5)):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            tmp = destino.with_suffix(destino.suffix + ".part")
            with urllib.request.urlopen(req, timeout=kw.get("timeout", 600)) as r, open(tmp, "wb") as f:
                esperado, n = r.headers.get("Content-Length"), 0
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
                    n += len(bloco)
            # lendo por partes, o Python não reclama se a conexão cair no meio: confere o tamanho
            if esperado and esperado.isdigit() and n != int(esperado):
                raise IOError(f"arquivo cortado ({n} de {esperado} bytes)")
            os.replace(tmp, destino)
            return destino
        except urllib.error.HTTPError as e:
            erro = e
            try:
                e.close()
            except Exception:
                pass
            if e.code in (400, 401, 403, 404, 410):
                break
        except Exception as e:
            erro = e
        time.sleep(min(60, 2 ** t * 2))
    raise RuntimeError(f"Falha ao baixar {url}: {erro}")


# ---------------------------------------------------------------- arquivos
def ler_json(caminho, padrao=None):
    caminho = Path(caminho)
    if not caminho.exists():
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def salvar_json(caminho, obj, indentado: bool = False) -> bool:
    """Salva em UTF-8 compacto. Só reescreve se mudou. Devolve True se escreveu."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if indentado:
        txt = json.dumps(obj, ensure_ascii=False, indent=1)
    else:
        txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    txt += "\n"
    if caminho.exists() and caminho.read_text(encoding="utf-8") == txt:
        return False
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(txt, encoding="utf-8")
    os.replace(tmp, caminho)
    return True


def _sem_datas(v):
    """Cópia sem as datas que mudam a cada execução ("atualizado" e a "data" de consulta das fontes)."""
    if isinstance(v, dict):
        eh_fonte = "url" in v and ("veiculo" in v or "titulo" in v)
        return {k: _sem_datas(x) for k, x in v.items() if k != "atualizado" and not (eh_fonte and k == "data")}
    if isinstance(v, list):
        return [_sem_datas(x) for x in v]
    return v


def sem_mudar_data(novo, caminho):
    """Se só mudaram datas de consulta (campo 'atualizado' e a data das fontes), devolve o conteúdo antigo,
    para o arquivo não ser regravado todo dia sem mudança de verdade."""
    antigo = ler_json(caminho)
    if antigo is not None and _sem_datas(antigo) == _sem_datas(novo):
        return antigo
    return novo


# ---------------------------------------------------------------- propostas
# Tipos que contam como "proposta" (vão para a lista). O resto vira contagem em "outros".
TIPOS_PROPOSTA = {
    "PL", "PLP", "PEC", "PDL", "PRC", "MPV", "PLV", "PLN",          # atuais
    "PDC", "PLS", "PLC", "PDS", "PRS", "PRN", "MSC",                # antigos / Senado / Congresso
}
NOME_TIPO = {
    "PL": "Projeto de lei", "PLP": "Projeto de lei complementar", "PEC": "Proposta de emenda à Constituição",
    "PDL": "Projeto de decreto legislativo", "PDC": "Projeto de decreto legislativo", "PRC": "Projeto de resolução",
    "PRS": "Projeto de resolução do Senado", "MPV": "Medida provisória", "PLV": "Projeto de lei de conversão",
    "PLN": "Projeto de lei do Congresso (orçamento)", "PLS": "Projeto de lei do Senado", "PLC": "Projeto de lei da Câmara",
    "PDS": "Projeto de decreto legislativo do Senado",
}
STATUS = ("lei", "aprovada", "andando", "junta", "arquivada", "rejeitada", "parada", "retirada", "outra")

# "rejeitada" = rejeitada numa votação ou vetada por inteiro. "parada" = parou sem ser rejeitada: perdeu a validade
# (medida provisória não votada a tempo), ficou prejudicada, foi devolvida ao autor ou impugnada. A Constituição
# (art. 62, §§ 3º e 11) trata "rejeição" e "perda de eficácia" como coisas diferentes, e o site também.
_REGRAS_STATUS = [  # (expressão, status) na ordem: a primeira que bater vale
    (r"transformad[oa] em (norma|lei)|norma jur[ií]dica|transformad[oa] na lei|promulgad|sancionad|convertid[oa] na lei", "lei"),
    (r"retirad[oa]s? pel|retirad[oa] de tramita|retirad[oa] a pedido", "retirada"),
    (r"perdeu a efic|perda de efic|sem efic[aá]cia|n[aã]o convertid|prejudicad|declarad[oa] prejudicad|"
     r"devolvid[oa] ao\s*(\([aà]\)\s*)?autor|impugnad", "parada"),
    (r"vetad[oa] totalmente|veto total|rejeitad|n[aã]o aprovad|inadmitid", "rejeitada"),
    (r"arquivad|arquivo", "arquivada"),
    (r"tramitando em conjunto|apensad|anexad[oa]", "junta"),
    (r"aguardando (aprecia[cç][aã]o|delibera[cç][aã]o) pelo senado|remetid[oa] ao senado|enviad[oa] ao senado|"
     r"remetid[oa] [àa] c[aâ]mara|enviad[oa] [àa] c[aâ]mara|aguardando (aprecia[cç][aã]o|delibera[cç][aã]o) pela c[aâ]mara|"
     r"aguardando san[cç][aã]o|remetid[oa] [àa] san[cç][aã]o|enviad[oa] [àa] san[cç][aã]o|aguardando promulga|"
     r"remetid[oa] ao presidente da rep|aprovad[oa]", "aprovada"),
    (r"aguardando|pronta para pauta|em tramita|tramitando|em an[aá]lise|em vota|tramita[cç][aã]o|"
     r"aguarda|comiss[aã]o|relator|parecer|plen[aá]rio|em pauta|leitura|recebid|apresentad|devolvid", "andando"),
]


def classificar_situacao(texto: str | None) -> str:
    """Traduz o texto oficial da situação para um dos STATUS. Regras específicas de cada Casa
    podem ser aplicadas antes de chamar esta função (ela é o padrão comum)."""
    t = sem_acento((texto or "").lower())
    if not t.strip():
        return "outra"
    for exp, st in _REGRAS_STATUS:
        if re.search(sem_acento(exp), t):
            return st
    return "outra"


STATUS_TXT = {
    "lei": "Virou lei",
    "aprovada": "Aprovada, mas ainda não virou lei",
    "andando": "Ainda em discussão",
    "junta": "Andando junto com outra proposta parecida",
    "arquivada": "Arquivada",
    "rejeitada": "Rejeitada em votação ou vetada por inteiro",
    "parada": "Parou (perdeu a validade, ficou prejudicada ou foi devolvida)",
    "retirada": "O autor desistiu",
    "outra": "Situação não classificada",
}


def resumo_propostas(lista: list[dict]) -> dict:
    r = {"total": len(lista), "autor": 0, "coautor": 0}
    r.update({s: 0 for s in STATUS})
    for p in lista:
        r[p.get("papel") or "coautor"] = r.get(p.get("papel") or "coautor", 0) + 1
        r[p.get("status") or "outra"] += 1
    return r


def ordenar_propostas(lista: list[dict]) -> list[dict]:
    return sorted(lista, key=lambda p: (p.get("data") or "", p.get("id") or ""), reverse=True)


# ---------------------------------------------------------------- explicações simples
def arquivo_simples(pid: str) -> Path:
    num = re.sub(r"\D", "", pid.split(":")[-1]) or "0"
    return SIMPLES / f"{int(num) % 100:02d}.json"


def carregar_simples() -> dict:
    tudo = {}
    for f in SIMPLES.glob("*.json"):
        tudo.update(ler_json(f, {}) or {})
    return tudo


def aplicar_simples(lista: list[dict], cache: dict | None = None) -> list[dict]:
    """Preenche "s" (português) e "s_en" (inglês) a partir do cache dados/simples/*.json.
    O cache guarda {"id": {"pt": "...", "en": "..."}} (ou só o texto em português, formato antigo)."""
    cache = carregar_simples() if cache is None else cache
    for p in lista:
        v = cache.get(p.get("id"))
        if not v:
            # o cache manda: explicação apagada ou recusada no cache some também do perfil
            p.pop("s", None)
            p.pop("s_en", None)
            continue
        if isinstance(v, str):
            p["s"] = p.get("s") or v
        else:
            if v.get("pt"):
                p["s"] = v["pt"]
            if v.get("en"):
                p["s_en"] = v["en"]
    return lista


# ---------------------------------------------------------------- fotos
def foto_local(url: str | None, pid: str, largura: int = 240, max_idade_dias: float = 30) -> str | None:
    """Baixa a foto oficial, reduz para `largura` px e salva em img/pessoas/<pid>.jpg.
    Devolve o caminho relativo ao site (ou None se falhar)."""
    if not url:
        return None
    destino = FOTOS / f"{pid}.jpg"
    rel = f"img/pessoas/{pid}.jpg"
    if destino.exists() and (time.time() - destino.stat().st_mtime) < max_idade_dias * 86400:
        return rel
    try:
        from PIL import Image  # Pillow
        bruto = baixar(url, tentativas=3, timeout=60, max_idade_h=None)
        im = Image.open(io.BytesIO(bruto))
        im = im.convert("RGB")
        if im.width > largura:
            im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
        im.save(destino, "JPEG", quality=82, optimize=True, progressive=True)
        return rel
    except Exception as e:
        print(f"  [foto] {pid}: {e}", file=sys.stderr)
        return rel if destino.exists() else None


def log(*a):
    print(agora_br().strftime("%H:%M:%S"), *a, flush=True)
