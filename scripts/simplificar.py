"""Gera explicações simples (português e inglês) para cada proposta, a partir da ementa oficial.

O texto oficial continua sempre ao lado no site; a explicação só traduz o "juridiquês".
As explicações ficam no repositório, em dados/simples/<00-99>.json (o robô faz commit de dados/): nunca dependem do
cache do Actions. São salvas a cada 10 pedidos e no fim (também quando o tempo acaba ou o passo é interrompido).

Provedor (SIMPLIFICAR_PROVEDOR; sem ele, a OpenAI se houver OPENAI_API_KEY):
  - openai:  API de chat da OpenAI (variável OPENAI_API_KEY; SIMPLIFICAR_URL troca o endereço por outro compatível)
  - copilot: GitHub Copilot CLI ("copilot -p", sem ferramentas). No Actions, usa o GITHUB_TOKEN com
             "permissions: copilot-requests: write"; o gasto sai dos créditos de IA do plano Copilot do dono do repositório.
  O GitHub Models (models.github.ai), usado antes, foi desligado pelo GitHub em 30/07/2026: o endereço responde
  "OK" em texto a qualquer pedido.
Variáveis opcionais:
  SIMPLIFICAR_MODELO  (padrão: gpt-4.1-mini na OpenAI; gpt-5.6-luna no Copilot)
  SIMPLIFICAR_ESFORCO quanto o modelo "pensa" antes de responder, no Copilot (padrão low: gasta menos)
  LIMITE              máximo de pedidos nesta execução (padrão 140)
  MINUTOS             tempo máximo desta execução, em minutos (padrão 0 = sem limite): o que faltar fica para a próxima
  LOTE                propostas por pedido (padrão 20)
  PAUSA               segundos entre pedidos (padrão 4)
Se o provedor recusar de vez (chave errada, sem permissão, endereço que não existe, cota esgotada, resposta que não é
da API de chat) ou falhar em 3 pedidos seguidos, a execução para na hora e o log mostra o status e o começo da resposta.

Uso: python scripts/simplificar.py [--teste 5] [--ids camara:123,senado:456]
Ordem (mesma régua para todos): rodízio por pessoa. A cada rodada, cada político ganha a explicação da sua proposta
mais nova que ainda não tem; assim todo mundo avança no mesmo ritmo (nada de prioridade para quem governa).
"""
from __future__ import annotations

import argparse
import datetime
import shutil
import signal
import subprocess

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
# termos técnicos com palavra da lista acima que não são opinião
TERMOS_TECNICOS = re.compile(r"\b(?:ensino|educação) fundamental\b|\b(?:direitos|garantias|liberdades|preceitos) fundamentais\b|"
                             r"\bpreceito fundamental\b", re.I)


def _opiniao(rx: re.Pattern, texto: str, ementa: str) -> str:
    """A primeira palavra de opinião do texto ("" = nenhuma). Não contam os termos técnicos (ensino fundamental, direitos
    fundamentais) nem os nomes próprios copiados da ementa (Boa Vista, Bom Jesus da Lapa, Escola Bom Pastor): palavra com
    maiúscula que aparece na ementa junto da mesma palavra vizinha."""
    texto = TERMOS_TECNICOS.sub(" ", texto)
    e = _norm(ementa)
    for m in rx.finditer(texto):
        w = m.group(0)
        if w[:1].isupper() and e:
            antes = re.search(r"([\w-]+)\W*$", texto[:m.start()])
            depois = re.match(r"\W*([\w-]+)", texto[m.end():])
            if any(p and _norm(p) in e for p in (antes and f"{antes.group(1)} {w}", depois and f"{w} {depois.group(1)}")):
                continue
        return w
    return ""


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


MODELS_DESLIGADO = ("o GitHub Models (models.github.ai), usado antes, foi desligado pelo GitHub em 30/07/2026 "
                    "(https://docs.github.com/en/github-models)")


def provedor() -> dict | None:
    escolha = (os.environ.get("SIMPLIFICAR_PROVEDOR") or "").strip().lower()
    modelo = (os.environ.get("SIMPLIFICAR_MODELO") or "").strip()
    if escolha in ("github", "models", "github-models"):
        aviso(f"SIMPLIFICAR_PROVEDOR={escolha}: {MODELS_DESLIGADO}. Use SIMPLIFICAR_PROVEDOR=copilot ou uma OPENAI_API_KEY.")
        return None
    if escolha == "copilot":
        return {"nome": "copilot", "modelo": modelo or "gpt-5.6-luna", "aiu": 0.0,
                "esforco": (os.environ.get("SIMPLIFICAR_ESFORCO") or "low").strip()}
    if escolha not in ("", "openai"):
        aviso(f"SIMPLIFICAR_PROVEDOR desconhecido: {escolha!r} (use openai ou copilot).")
        return None
    if not os.environ.get("OPENAI_API_KEY"):
        aviso(f"Nenhum provedor de IA: sem OPENAI_API_KEY e sem SIMPLIFICAR_PROVEDOR=copilot ({MODELS_DESLIGADO}). "
              "Nenhuma explicação nova hoje.")
        return None
    return {"nome": "openai", "modelo": modelo or "gpt-4.1-mini",
            "url": os.environ.get("SIMPLIFICAR_URL") or "https://api.openai.com/v1/chat/completions",
            "cab": {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}}


def aviso(msg: str) -> None:
    """No log e, no GitHub Actions, também como aviso no resumo da rodada (sem precisar abrir o log)."""
    log(msg)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::warning title=Explicações simples::" + msg.replace("%", "%25").replace("\n", " "), flush=True)


class Falha(Exception):
    """Um pedido que não deu certo. modo: "parar" (recusa que não muda tentando de novo: a execução para),
    "repetir" (rede, servidor fora do ar, limite por minuto: tenta de novo), "estranha" (resposta que não é da API
    de chat: tenta 1 vez mais e depois para), "pular" (este lote não vai dar certo: segue para o próximo)."""

    def __init__(self, msg: str, modo: str, espera: float = 0, limite: bool = False):
        super().__init__(msg)
        self.modo, self.espera, self.limite = modo, espera, limite  # limite: 429 (espera e tenta de novo)


def _trecho(b, n: int = 300) -> str:
    """O começo de uma resposta, numa linha só, para o log."""
    if isinstance(b, bytes):
        b = b.decode("utf-8", "replace")
    t = re.sub(r"\s+", " ", b or "").strip()
    return (t[:n] + "…" if len(t) > n else t) or "(corpo vazio)"


def _entrada(lote: list[dict]) -> str:
    return json.dumps([{"id": x["id"], "sigla": x["sigla"], "ementa": x["ementa"]} for x in lote], ensure_ascii=False)


def _openai(prov: dict, lote: list[dict]) -> str:
    """Um pedido à API de chat (formato da OpenAI). Devolve o texto escrito pelo modelo."""
    corpo = json.dumps({
        "model": prov["modelo"], "temperature": 0.2, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": _entrada(lote)}],
    }).encode("utf-8")
    h = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA}
    h.update(prov["cab"])
    req = urllib.request.Request(prov["url"], data=corpo, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            status, cab, bruto = r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        status, cab, bruto = e.code, e.headers, e.read()
    resumo = f"HTTP {status} ({cab.get('Content-Type') or 'sem Content-Type'}): {_trecho(bruto)}"
    if status == 429:
        try:
            espera = float(cab.get("Retry-After") or 0)
        except ValueError:
            espera = 0
        if b"insufficient_quota" in bruto or espera > 300:
            raise Falha(f"cota esgotada — {resumo}", "parar")
        raise Falha(f"limite de pedidos — {resumo}", "repetir", espera, limite=True)
    if status in (401, 403, 404, 405, 410):
        raise Falha(f"recusado (chave, permissão, endereço ou modelo) — {resumo}", "parar")
    if status in (400, 413, 422):
        raise Falha(f"pedido recusado — {resumo}", "pular")
    if status >= 300:
        raise Falha(resumo, "repetir")
    try:
        texto = json.loads(bruto)["choices"][0]["message"]["content"]
    except Exception:
        raise Falha(f"a resposta não é da API de chat — {resumo}", "estranha")
    if not isinstance(texto, str):
        raise Falha(f"a resposta não trouxe texto — {resumo}", "estranha")
    return texto


def _copilot(prov: dict, lote: list[dict]) -> str:
    """Um pedido pelo GitHub Copilot CLI, sem nenhuma ferramenta (só escreve texto). Autenticação: COPILOT_GITHUB_TOKEN,
    GH_TOKEN ou GITHUB_TOKEN (no Actions, com "permissions: copilot-requests: write")."""
    exe = shutil.which("copilot")
    if not exe:
        raise Falha("o GitHub Copilot CLI não está instalado (npm install -g @github/copilot)", "parar")
    pasta = CACHE / "simples-copilot"  # pasta vazia: o CLI não lê instruções nem configurações do repositório
    pasta.mkdir(parents=True, exist_ok=True)
    uso = pasta / "uso.json"
    uso.unlink(missing_ok=True)
    cmd = [exe, "-s", "--model", prov["modelo"], "--no-custom-instructions", "--disable-builtin-mcps", "--no-ask-user",
           "--no-auto-update", "--usage-output-file", str(uso)]
    if prov.get("esforco"):
        cmd += ["--reasoning-effort", prov["esforco"]]
    cmd.append("--available-tools")  # sem nome nenhum depois: nenhuma ferramenta
    prompt = SISTEMA + "\nPropostas (JSON):\n" + _entrada(lote)
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=300, cwd=pasta)
    except subprocess.TimeoutExpired:
        raise Falha("o Copilot CLI não respondeu em 5 minutos", "repetir")
    try:
        prov["aiu"] += (ler_json(uso, {}) or {}).get("totalNanoAiu", 0) / 1e9
    except Exception:
        pass
    if r.returncode != 0:
        msg = f"Copilot CLI saiu com código {r.returncode}: {_trecho((r.stderr or '') + ' ' + (r.stdout or ''))}"
        definitivo = re.search(r"not available|not found|auth|log ?in|token|permission|forbidden|denied|unauthori[sz]ed|"
                               r"quota|credit|budget|billing|policy|exceed|\b40[134]\b|\b429\b", msg, re.I)
        raise Falha(msg, "parar" if definitivo else "repetir")
    return r.stdout


def _itens(texto: str) -> list[dict]:
    """A lista "itens" do JSON escrito pelo modelo (aceita o JSON dentro de ```json ... ```)."""
    t = (texto or "").strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ValueError(f"o modelo não respondeu em JSON: {_trecho(t, 200)}")
    d = json.loads(t[i:j + 1])
    itens = d.get("itens") if isinstance(d, dict) else None
    if not isinstance(itens, list):
        raise ValueError(f"o JSON do modelo não tem a lista \"itens\": {_trecho(t, 200)}")
    return [x for x in itens if isinstance(x, dict)]


def pedir(prov: dict, lote: list[dict], tentativas: int = 4) -> list[dict] | None:
    """Os itens do modelo para um lote, ou None se o lote falhou. Levanta Falha("parar") quando não adianta continuar."""
    chamar = _copilot if prov["nome"] == "copilot" else _openai
    estranhas = 0
    for tentativa in range(tentativas):
        espera = 8 * (tentativa + 1)
        try:
            return _itens(chamar(prov, lote))
        except Falha as f:
            if f.modo == "parar":
                raise
            if f.modo == "estranha":
                estranhas += 1
                if estranhas >= 2:
                    raise Falha(str(f), "parar")
            log(f"  erro: {f}")
            if f.modo == "pular":
                return None
            if f.limite:
                if tentativa == tentativas - 1:
                    raise Falha(f"o limite de pedidos não passou depois de {tentativas} tentativas — {f}", "parar")
                espera = max(f.espera, 20 * (tentativa + 1))
        except ValueError as e:  # o modelo escreveu um JSON quebrado: tenta de novo
            log(f"  erro: {e}")
            espera = 2
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # rede
            log(f"  erro de rede: {e}")
        if tentativa < tentativas - 1:
            log(f"  tentando de novo em {espera:.0f} s")
            time.sleep(espera)
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


def recusa(x: dict, ementa: str = "") -> str:
    """Por que a conferência recusa a explicação ("" = aceita)."""
    pt, en = limpa(x.get("pt")), limpa(x.get("en"))
    if not pt or not en:
        return "sem o texto em português ou em inglês"
    if _norm(pt) == _norm(en) or (re.search(r"\b(the|and)\b", pt, re.I) and not re.search(r"\b(the|and)\b", ementa, re.I)):
        return "o texto em português está em inglês"
    if len(pt.split()) > LIMITE_PT:
        return f"português com {len(pt.split())} palavras (máximo {LIMITE_PT})"
    if len(en.split()) > LIMITE_EN:
        return f"inglês com {len(en.split())} palavras (máximo {LIMITE_EN})"
    m = _opiniao(PROIBIDAS_PT, pt, ementa) or _opiniao(PROIBIDAS_EN, en, ementa)
    if m:
        return f"palavra de opinião: {m!r}"
    if ementa:
        # números: cada número da explicação tem de vir de algum número da ementa (7,52 bilhões <- 7.520.000.000,00)
        nums_e = _digitos(ementa)
        for n in _digitos(pt) + _digitos(en):
            if not any(_bate(n, e) for e in nums_e):
                return f"número que não está na ementa: {n}"
        # trechos entre aspas (português) têm de estar na ementa
        for q in re.findall(r"[\"“]([^\"”]{2,})[\"”]", pt):
            if _norm(q) not in _norm(ementa):
                return f"trecho entre aspas que não está na ementa: {q!r}"
    return ""


def valido(x: dict, ementa: str = "") -> bool:
    return not recusa(x, ementa)


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
    ap.add_argument("--sem-salvar", action="store_true", help="só mostra: não grava dados/simples nem as recusadas")
    a = ap.parse_args()
    prov = provedor()
    if not prov:
        return
    cache = carregar_simples()
    props, filas = coletar()
    recusadas = ler_json(RECUSADAS, {}) or {}
    explicadas = {pid for pid, v in cache.items() if isinstance(v, dict) and v.get("pt") and v.get("en")}
    pular = explicadas | {pid for pid, n in recusadas.items() if n >= 2}
    lote_n = int(os.environ.get("LOTE", "20"))
    limite = int(os.environ.get("LIMITE", "140"))
    pausa = float(os.environ.get("PAUSA", "4"))
    prazo = float(os.environ.get("MINUTOS", "0")) * 60
    t0 = time.monotonic()
    if a.ids:
        ordem = [i for i in a.ids.split(",") if i in props]
    else:
        ordem = rodizio(filas, pular, lote_n * limite)
    if a.teste:
        ordem = ordem[: a.teste]
    faltam = [props[i] for i in ordem]
    log(f"propostas: {len(props)} | já explicadas: {len(explicadas & set(props))} | pessoas: {len(filas)} | "
        f"nesta execução: até {len(faltam)} (rodízio por pessoa) | provedor: {prov['nome']} | modelo: {prov['modelo']}")
    novos, pedidos, falhas_seguidas, recusas = {}, 0, 0, []

    def gravar() -> None:
        if a.sem_salvar:
            return
        salvar(novos)
        for pid in novos:
            recusadas.pop(pid, None)
        salvar_json(RECUSADAS, dict(sorted(recusadas.items())))

    # o passo do Actions pode ser interrompido (tempo esgotado, rodada cancelada): o que já foi gerado é gravado antes de sair
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        for i in range(0, len(faltam), lote_n):
            if pedidos >= limite:
                log("limite de pedidos desta execução atingido")
                break
            if prazo and time.monotonic() - t0 > prazo:
                log("limite de tempo desta execução atingido: o resto fica para a próxima")
                break
            lote = faltam[i: i + lote_n]
            pedidos += 1
            itens = pedir(prov, lote)
            if itens is None:  # falha do provedor: não conta como recusa
                falhas_seguidas += 1
                log(f"pedido {pedidos}: falhou")
                if falhas_seguidas >= 3:
                    raise Falha("3 pedidos seguidos falharam", "parar")
                continue
            falhas_seguidas = 0
            ids = {x["id"] for x in lote}
            aceitas = set()
            for x in itens:
                pid = x.get("id")
                if pid not in ids or pid in aceitas:
                    continue
                motivo = recusa(x, props[pid]["ementa"])
                if motivo:
                    recusas.append((pid, motivo, x))
                else:
                    novos[pid] = {"pt": limpa(x["pt"]), "en": limpa(x["en"])}
                    aceitas.add(pid)
            devolvidas = {x.get("id") for x in itens}
            for pid in ids - aceitas:
                recusadas[pid] = recusadas.get(pid, 0) + 1
                if pid not in devolvidas:
                    recusas.append((pid, "o modelo não devolveu esta proposta", {}))
            log(f"pedido {pedidos}: {len(aceitas)}/{len(lote)} aceitas")
            if pedidos % 10 == 0:
                gravar()
            time.sleep(pausa)
    except Falha as e:
        aviso(f"parando: {e}")
    finally:
        gravar()
    gasto = f" | créditos de IA do Copilot usados: {prov['aiu']:.1f}" if prov["nome"] == "copilot" else ""
    log(f"novas explicações: {len(novos)} | recusadas pela conferência: {len(recusas)} | pedidos: {pedidos}{gasto}")
    if a.teste or a.ids:
        for pid, v in novos.items():
            print(f"\n{pid}: {props[pid]['ementa']}\n  PT: {v['pt']}\n  EN: {v['en']}")
        for pid, motivo, x in recusas:
            print(f"\nRECUSADA {pid} ({motivo}): {props[pid]['ementa']}\n  PT: {limpa(x.get('pt'))}\n  EN: {limpa(x.get('en'))}")


if __name__ == "__main__":
    main()
