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
Ordem (mesma régua para todos): rodízio por pessoa. A cada rodada, cada político ganha a explicação da sua proposta
mais nova que ainda não tem; assim todo mundo avança no mesmo ritmo (nada de prioridade para quem governa).
"""
from __future__ import annotations

import argparse
import datetime

from comum import *

SISTEMA = """Você escreve explicações simples de propostas de lei do Brasil para um site educativo e imparcial.
Leitores: crianças de 10 anos (em português) e estrangeiros que não conhecem o Brasil (em inglês).
Para cada proposta você recebe id, sigla e a ementa oficial. Responda SOMENTE com JSON:
{"itens":[{"id":"...","pt":"...","en":"..."}]} — um item para cada proposta recebida, na mesma ordem, com o mesmo id.

Regras para "pt":
- 1 ou 2 frases curtas, no máximo 35 palavras no total.
- Comece com o verbo que corresponde ao da ementa: institui/cria → Cria; altera → Muda; veda/proíbe → Proíbe; revoga → Revoga;
  susta → Suspende; autoriza/permite → Permite; obriga → Obriga; dispõe sobre → Trata de; denomina → Dá o nome; inscreve/homenageia → Homenageia;
  abre crédito → Libera um gasto extra; aprova (acordo, contas) → Aprova; solicita → Pede.
  Só use "Garante" se a ementa disser "garante" ou "assegura". Só use "Tira", "Aumenta" ou "Diminui" se a ementa disser isso.
- Diga O QUE a proposta faz, nunca se é boa ou ruim. Sem opinião e sem adjetivos de valor (bom, ruim, importante, justo, polêmico, necessário, essencial, histórico).
- Use só o que está na ementa. Não invente detalhes, números, motivos nem consequências.
- Se a ementa disser a finalidade com palavras de valor (fortalecer, modernizar, aperfeiçoar, valorizar, combater, proteger, incentivar, promover), não repita a finalidade. Faça igual em todas.
- Não cite partidos, políticos ou governos, nem diga quem apresentou a proposta.
- Não use apelidos de propostas (ex.: "PL das Fake News", "PEC da Blindagem"). Se o apelido estiver na ementa, repita entre aspas.
- Se a ementa usar uma expressão com carga política ou de valor (ex.: "ideologia de gênero", "fake news", "privilégios"), repita a expressão entre aspas, como está no texto oficial; não troque por sinônimos nem comente.
- Não diga quem ganha ou quem perde com a proposta, nem para que ela "serve", se a ementa não disser.
- Troque palavras difíceis por simples ("dispõe sobre" -> "trata de"; "altera a Lei nº X" -> "muda a lei sobre ..." quando der para saber o assunto pela ementa).
- Se a ementa não disser qual é o assunto, escreva exatamente: "Muda uma lei. O texto oficial explica os detalhes."
- Pode manter siglas conhecidas (SUS, INSS) e nomes próprios.

Regras para "en": a mesma explicação em inglês simples, para estrangeiros, com as mesmas regras; no máximo 45 palavras
(o limite é maior só para caber a explicação de siglas e termos brasileiros, ex.: "SUS, Brazil's public health system"; "INSS, the national pension agency").
Expressões com carga política ficam entre aspas, traduzidas ao pé da letra.
Se a ementa não disser o assunto, escreva exatamente: "Changes a law. The official text has the details."
"""

PROIBIDAS_PT = re.compile(
    r"\b(bom|boa|bons|boas|ruins?|ótim[oa]s?|péssim[oa]s?|excelentes?|absurd[oa]s?|polêmic[oa]s?|importantes?|"
    r"just[oa]s?(?! causa)|injust[oa]s?|incríve(?:l|is)|maravilhos[oa]s?|necessári[oa]s?|essenciais|essencial|"
    r"fundamenta(?:l|is)|avanços?|retrocessos?|conquistas?|vergonhos[oa]s?|corajos[oa]s?|benéfic[oa]s?)\b", re.I)
PROIBIDAS_EN = re.compile(
    r"\b(good|bad|great|terrible|excellent|absurd|controversial|important|unfair|amazing|wonderful|necessary|essential|"
    r"crucial|landmark|fair|progress|setback|beneficial|shameful|brave)\b", re.I)
LIMITE_PT, LIMITE_EN = 35, 45


def coletar() -> tuple[dict, dict]:
    """Todas as propostas dos perfis, sem repetir (id -> {sigla, ementa, data}), e a fila de cada pessoa
    (id da pessoa -> ids das propostas dela, da mais nova para a mais antiga). Inclui as pessoas dos arquivos por
    cidade (dados/camaras/extras/<IBGE>.json)."""
    props, filas = {}, {}
    for pessoa, p in perfis_com_extras():
        fila = []
        for x in (p.get("propostas") or {}).get("lista") or []:
            pid, ementa = x.get("id"), limpa(x.get("ementa"))
            if not pid or not ementa:
                continue
            props.setdefault(pid, {"id": pid, "sigla": x.get("sigla") or "", "ementa": ementa, "data": x.get("data") or ""})
            fila.append(pid)
        if fila:
            fila.sort(key=lambda i: props[i]["data"], reverse=True)
            filas[pessoa] = fila
    return props, filas


def rodizio(filas: dict, feitas, maximo: int) -> list[str]:
    """Uma proposta de cada pessoa por vez (a mais nova que falta), até `maximo`. O ponto de partida muda a cada dia,
    para ninguém ficar sempre no começo da fila."""
    pessoas = sorted(filas)
    if not pessoas:
        return []
    ini = datetime.date.today().toordinal() % len(pessoas)
    pessoas = pessoas[ini:] + pessoas[:ini]
    pos = {pid: 0 for pid in pessoas}
    escolhidas, vistas = [], set(feitas)
    while len(escolhidas) < maximo:
        andou = False
        for pid in pessoas:
            fila = filas[pid]
            while pos[pid] < len(fila) and fila[pos[pid]] in vistas:
                pos[pid] += 1
            if pos[pid] < len(fila):
                x = fila[pos[pid]]
                escolhidas.append(x)
                vistas.add(x)
                andou = True
                if len(escolhidas) >= maximo:
                    break
        if not andou:
            break
    return escolhidas


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


def _digitos(s: str) -> list[str]:
    return [re.sub(r"\D", "", n) for n in re.findall(r"\d[\d.,]*", s or "") if re.sub(r"\D", "", n)]


def _bate(n: str, e: str) -> bool:
    """O número n (só dígitos) é o começo do número e da ementa, ou e arredondado (64,3 milhões <- 64.289.400,00)."""
    if e.startswith(n):
        return True
    k = len(n)
    if len(e) <= k or k < 2:
        return False
    r = str(round(int(e[:k + 1]) / 10))
    return r == n


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", sem_acento((s or "").lower())).strip()


def valido(x: dict, ementa: str = "") -> bool:
    pt, en = limpa(x.get("pt")), limpa(x.get("en"))
    if not pt or not en:
        return False
    if len(pt.split()) > LIMITE_PT or len(en.split()) > LIMITE_EN:
        return False
    if PROIBIDAS_PT.search(pt) or PROIBIDAS_EN.search(en):
        return False
    if ementa:
        # números: cada número da explicação tem de vir de algum número da ementa (7,52 bilhões <- 7.520.000.000,00)
        nums_e = _digitos(ementa)
        for n in _digitos(pt) + _digitos(en):
            if not any(_bate(n, e) for e in nums_e):
                return False
        # trechos entre aspas (português) têm de estar na ementa
        for q in re.findall(r"[\"“]([^\"”]{2,})[\"”]", pt):
            if _norm(q) not in _norm(ementa):
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


RECUSADAS = DADOS / "simples-recusadas.json"  # {id: tentativas recusadas}; depois de 2, a proposta sai do rodízio


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
    props, filas = coletar()
    recusadas = ler_json(RECUSADAS, {}) or {}
    explicadas = {pid for pid, v in cache.items() if isinstance(v, dict) and v.get("pt") and v.get("en")}
    pular = explicadas | {pid for pid, n in recusadas.items() if n >= 2}
    lote_n = int(os.environ.get("LOTE", "20"))
    limite = int(os.environ.get("LIMITE", "140"))
    pausa = float(os.environ.get("PAUSA", "4"))
    if a.ids:
        ordem = [i for i in a.ids.split(",") if i in props]
    else:
        ordem = rodizio(filas, pular, lote_n * limite)
    if a.teste:
        ordem = ordem[: a.teste]
    faltam = [props[i] for i in ordem]
    log(f"propostas: {len(props)} | já explicadas: {len(explicadas & set(props))} | pessoas: {len(filas)} | "
        f"nesta execução: até {len(faltam)} (rodízio por pessoa) | modelo: {modelo}")
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
                continue  # falha de rede/modelo: não conta como recusa
            ids = {x["id"] for x in lote}
            aceitas = set()
            for x in itens:
                pid = x.get("id")
                if pid in ids and valido(x, props[pid]["ementa"]):
                    novos[pid] = {"pt": limpa(x["pt"]), "en": limpa(x["en"])}
                    aceitas.add(pid)
            for pid in ids - aceitas:
                recusadas[pid] = recusadas.get(pid, 0) + 1
            log(f"pedido {pedidos}: {len(aceitas)}/{len(lote)} aceitas")
            if pedidos % 10 == 0:
                salvar(novos)
                salvar_json(RECUSADAS, dict(sorted(recusadas.items())))
            time.sleep(pausa)
    except RuntimeError as e:
        log(f"parando: {e}")
    salvar(novos)
    for pid in novos:
        recusadas.pop(pid, None)
    salvar_json(RECUSADAS, dict(sorted(recusadas.items())))
    log(f"novas explicações: {len(novos)}")
    if a.teste:
        for pid, v in list(novos.items())[: a.teste]:
            print(f"\n{pid}: {props[pid]['ementa']}\n  PT: {v['pt']}\n  EN: {v['en']}")


if __name__ == "__main__":
    main()
