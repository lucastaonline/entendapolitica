"""Gera explicações simples (português e inglês) para cada proposta, a partir da ementa oficial.

O texto oficial continua sempre ao lado no site; a explicação só traduz o "juridiquês".
Provedor (o primeiro disponível):
  - GitHub Models (no GitHub Actions, com "permissions: models: read"): variável GITHUB_TOKEN
  - OpenAI: variável OPENAI_API_KEY
Variáveis opcionais:
  SIMPLIFICAR_MODELO  (padrão: openai/gpt-4.1-mini no GitHub Models; gpt-4.1-mini na OpenAI)
  LIMITE              máximo de pedidos nesta execução (padrão 140, a cota diária grátis do GitHub Models)
  LOTE                propostas por pedido (padrão 20)
  PAUSA               segundos entre pedidos (padrão 4)

Uso: python scripts/simplificar.py [--teste 5] [--ids camara:123,senado:456]
Prioridade: o que virou lei e o que foi aprovado primeiro; depois das mais novas para as mais antigas.
"""
from __future__ import annotations

import argparse

from comum import *

SISTEMA = """Você escreve explicações simples de propostas de lei do Brasil para um site educativo e imparcial.
Leitores: crianças de 10 anos (em português) e estrangeiros que não conhecem o Brasil (em inglês).
Para cada proposta você recebe id, sigla e a ementa oficial. Responda SOMENTE com JSON:
{"itens":[{"id":"...","pt":"...","en":"..."}]} — um item para cada proposta recebida, na mesma ordem, com o mesmo id.

Regras para "pt":
- 1 ou 2 frases curtas, no máximo 35 palavras no total.
- Comece com um verbo no presente que diga o que a proposta faz: Cria, Muda, Proíbe, Obriga, Permite, Garante, Tira, Aumenta, Diminui, Homenageia, Susta, Aprova, Pede.
- Diga O QUE a proposta faz, nunca se é boa ou ruim. Sem opinião e sem adjetivos de valor (bom, ruim, importante, justo, polêmico, necessário).
- Use só o que está na ementa. Não invente detalhes, números, motivos nem consequências.
- Troque palavras difíceis por simples ("dispõe sobre" -> "trata de"; "altera a Lei nº X" -> "muda a lei sobre ..." quando der para saber o assunto pela ementa).
- Se a ementa não disser qual é o assunto, escreva exatamente: "Muda uma lei. O texto oficial explica os detalhes."
- Pode manter siglas conhecidas (SUS, INSS) e nomes próprios.

Regras para "en": a mesma explicação em inglês simples, para estrangeiros, com as mesmas regras e o mesmo limite.
Explique siglas brasileiras em poucas palavras (ex.: "SUS, Brazil's public health system"; "INSS, the national pension agency").
Se a ementa não disser o assunto, escreva exatamente: "Changes a law. The official text has the details."
"""

PROIBIDAS_PT = re.compile(r"\b(bom|boa|bons|boas|ruim|ruins|ótim[oa]s?|péssim[oa]s?|excelente|absurd[oa]s?|polêmic[oa]s?|importante|justo|injust[oa]|incrível|maravilhos[oa])\b", re.I)
PROIBIDAS_EN = re.compile(r"\b(good|bad|great|terrible|excellent|absurd|controversial|important|unfair|amazing|wonderful)\b", re.I)


def coletar() -> dict:
    """Todas as propostas dos perfis, sem repetir: id -> {sigla, ementa, prioridade, data}."""
    props = {}
    pri = {"lei": 0, "aprovada": 1}
    for f in sorted(PESSOAS.glob("*.json")):
        p = ler_json(f) or {}
        for x in (p.get("propostas") or {}).get("lista") or []:
            pid, ementa = x.get("id"), limpa(x.get("ementa"))
            if not pid or not ementa:
                continue
            atual = props.get(pid)
            item = {"id": pid, "sigla": x.get("sigla") or "", "ementa": ementa, "prioridade": pri.get(x.get("status"), 2), "data": x.get("data") or ""}
            if not atual or item["prioridade"] < atual["prioridade"]:
                props[pid] = item
    return props


def provedor():
    modelo = os.environ.get("SIMPLIFICAR_MODELO")
    if os.environ.get("OPENAI_API_KEY"):
        return ("https://api.openai.com/v1/chat/completions", {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, modelo or "gpt-4.1-mini")
    if os.environ.get("GITHUB_TOKEN"):
        return ("https://models.github.ai/inference/chat/completions",
                {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                modelo or "openai/gpt-4.1-mini")
    return None


def pedir(url: str, cab: dict, modelo: str, lote: list[dict]) -> list[dict] | None:
    corpo = json.dumps({
        "model": modelo, "temperature": 0.2, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SISTEMA},
                     {"role": "user", "content": json.dumps([{"id": x["id"], "sigla": x["sigla"], "ementa": x["ementa"]} for x in lote], ensure_ascii=False)}],
    }).encode("utf-8")
    h = {"Content-Type": "application/json", "User-Agent": UA}
    h.update(cab)
    for tentativa in range(4):
        try:
            req = urllib.request.Request(url, data=corpo, headers=h)
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read().decode("utf-8"))
            texto = resp["choices"][0]["message"]["content"]
            return json.loads(texto).get("itens") or []
        except urllib.error.HTTPError as e:
            if e.code == 429:
                espera = int(e.headers.get("Retry-After") or 0)
                if espera > 300 or tentativa == 3:
                    raise RuntimeError(f"cota esgotada (429, Retry-After={espera})")
                time.sleep(max(espera, 20 * (tentativa + 1)))
                continue
            if e.code in (401, 403):
                raise RuntimeError(f"sem permissão ({e.code}): confira a chave/permissões")
            log(f"  erro HTTP {e.code}; tentando de novo")
        except Exception as e:  # rede, JSON quebrado
            log(f"  erro: {e}; tentando de novo")
        time.sleep(8 * (tentativa + 1))
    return None


def valido(x: dict) -> bool:
    pt, en = limpa(x.get("pt")), limpa(x.get("en"))
    if not pt or not en:
        return False
    if len(pt.split()) > 48 or len(en.split()) > 48:
        return False
    if PROIBIDAS_PT.search(pt) or PROIBIDAS_EN.search(en):
        return False
    return True


def salvar(novos: dict) -> None:
    por_arquivo: dict[Path, dict] = {}
    for pid, v in novos.items():
        por_arquivo.setdefault(arquivo_simples(pid), {})[pid] = v
    for arq, itens in por_arquivo.items():
        atual = ler_json(arq, {}) or {}
        atual.update(itens)
        salvar_json(arq, dict(sorted(atual.items())))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teste", type=int, default=0, help="só N propostas (para conferir o resultado)")
    ap.add_argument("--ids", default="", help="ids separados por vírgula")
    a = ap.parse_args()
    prov = provedor()
    if not prov:
        log("Sem GITHUB_TOKEN nem OPENAI_API_KEY: nada a fazer.")
        return
    url, cab, modelo = prov
    cache = carregar_simples()
    props = coletar()
    faltam = [x for pid, x in props.items() if not (isinstance(cache.get(pid), dict) and cache[pid].get("pt") and cache[pid].get("en"))]
    if a.ids:
        quero = set(a.ids.split(","))
        faltam = [x for x in props.values() if x["id"] in quero]
    faltam.sort(key=lambda x: (x["prioridade"], "".join(chr(255 - ord(c)) for c in x["data"])))
    if a.teste:
        faltam = faltam[: a.teste]
    lote_n = int(os.environ.get("LOTE", "20"))
    limite = int(os.environ.get("LIMITE", "140"))
    pausa = float(os.environ.get("PAUSA", "4"))
    log(f"propostas: {len(props)} | já explicadas: {len(props) - len(faltam)} | faltam: {len(faltam)} | modelo: {modelo}")
    novos, pedidos = {}, 0
    try:
        for i in range(0, len(faltam), lote_n):
            if pedidos >= limite:
                log("limite de pedidos desta execução atingido")
                break
            lote = faltam[i: i + lote_n]
            itens = pedir(url, cab, modelo, lote)
            pedidos += 1
            if not itens:
                continue
            ids = {x["id"] for x in lote}
            ok = 0
            for x in itens:
                if x.get("id") in ids and valido(x):
                    novos[x["id"]] = {"pt": limpa(x["pt"]), "en": limpa(x["en"])}
                    ok += 1
            log(f"pedido {pedidos}: {ok}/{len(lote)} aceitas")
            if pedidos % 10 == 0:
                salvar(novos)
            time.sleep(pausa)
    except RuntimeError as e:
        log(f"parando: {e}")
    salvar(novos)
    log(f"novas explicações: {len(novos)}")
    if a.teste:
        for pid, v in list(novos.items())[: a.teste]:
            print(f"\n{pid}: {props[pid]['ementa']}\n  PT: {v['pt']}\n  EN: {v['en']}")


if __name__ == "__main__":
    main()
