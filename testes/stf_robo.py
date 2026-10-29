"""O robô do STF sem rede (scripts/stf.py): o que acontece quando os sites caem e quando a composição muda.

Sem servidor e sem internet. Usa cópias em .cache/stf/teste/ (o dados/stf.json e as fotos de verdade não são tocados):
1. cache vazio e todos os sites fora do ar (como o robô do GitHub num dia ruim): o arquivo de antes fica igual, byte a byte;
2. o STF responde (cache) mas o Senado cai: cada ministro fica com o bloco do Senado de antes;
3. a página do STF volta com menos ministros do que o mínimo: a leitura é recusada e o arquivo de antes fica;
4. a composição muda (alguém sai, alguém entra, troca a presidência, muda a Turma, chega uma indicação): o log avisa;
5. o robô diário não lê de novo antes de uma semana (sai sem nenhum pedido).
Uso: python testes/stf_robo.py"""
import contextlib
import copy
import io
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import stf  # noqa: E402

RES = []
T = RAIZ / ".cache" / "stf" / "teste"


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def sem_rede(*a, **k):
    raise stf.Falha("sem rede (teste)")


def roda(*args):
    """Roda o main() do stf.py com os argumentos e devolve o que ele escreveu no log."""
    buf = io.StringIO()
    velho = sys.argv
    sys.argv = ["stf.py", *args]
    try:
        with contextlib.redirect_stdout(buf):
            stf.main()
    finally:
        sys.argv = velho
    return buf.getvalue()


def main():
    real = RAIZ / "dados" / "stf.json"
    if not real.exists():
        print("sem dados/stf.json: rode antes python scripts/stf.py --agora")
        sys.exit(1)
    shutil.rmtree(T, ignore_errors=True)
    (T / "fotos").mkdir(parents=True)
    for f in (RAIZ / "img" / "pessoas").glob("stf-*.jpg"):  # as fotos que já estão no repositório (como no robô)
        shutil.copy(f, T / "fotos" / f.name)
    arq = T / "stf.json"
    shutil.copy(real, arq)
    antes = arq.read_bytes()
    stf.ARQ, stf.FOTOS = arq, T / "fotos"
    stf.Rede._abre = sem_rede  # nenhum pedido sai daqui

    # 1. cache vazio, tudo fora do ar
    stf.CS = T / "cache-vazio"
    log = roda("--agora")
    ok("cache vazio e sites fora do ar: o arquivo fica igual", arq.read_bytes() == antes, log.strip().splitlines()[-1][:160])
    ok("cache vazio e sites fora do ar: o log diz que fica o de antes", "Fica o arquivo de antes" in log)

    # 2. o STF (cache) responde, o Senado não: fica o bloco do Senado de antes
    stf.CS = T / "cache-so-stf"
    shutil.copytree(RAIZ / ".cache" / "stf" / "stf", stf.CS / "stf")
    log = roda("--agora")
    novo = json.loads(arq.read_text(encoding="utf-8"))
    velho = json.loads(antes.decode("utf-8"))
    ok("Senado fora do ar: o arquivo continua com os 10 ministros", len(novo["ministros"]) == len(velho["ministros"]), log.strip().splitlines()[-1][:120])
    ok("Senado fora do ar: cada ministro fica com o placar de antes",
       [m["senado"]["plenario"] for m in novo["ministros"]] == [m["senado"]["plenario"] for m in velho["ministros"]])
    ok("Senado fora do ar: a cadeira vazia fica como estava", novo.get("vagas") == velho.get("vagas"))
    ok("Senado fora do ar: o log avisa", "fica o bloco do Senado de antes" in log)

    # 3. a página do STF volta quebrada (só 3 ministros): a leitura é recusada
    shutil.copy(real, arq)
    stf.CS = T / "cache-quebrado"
    shutil.copytree(RAIZ / ".cache" / "stf", stf.CS, ignore=shutil.ignore_patterns("teste", "explora"))
    h = (stf.CS / "stf" / "ostf.html").read_text(encoding="utf-8")
    partes = h.split('class="ministro-conteudo')
    (stf.CS / "stf" / "ostf.html").write_text('class="ministro-conteudo'.join(partes[:4]) + h[h.find("card-turmas-ostf") - 30:], encoding="utf-8")
    log = roda("--agora")
    ok("página do STF quebrada: a leitura é recusada e o arquivo fica igual", arq.read_bytes() == antes and "Fica o arquivo de antes" in log,
       log.strip().splitlines()[-1][:120])

    # 4. a composição muda: o log avisa (aposentadoria, posse, presidência, Turma, indicação nova)
    a = copy.deepcopy(velho)
    saiu = a["ministros"].pop()  # o mais novo "não estava" na leitura de antes
    falso = copy.deepcopy(a["ministros"][-1])
    falso.update({"id": "stf-fulano-de-tal", "idStf": 9999, "nome": "Fulano de Tal"})
    a["ministros"].append(falso)
    a["presidencia"]["presidente"] = a["presidencia"]["vice"]
    a["ministros"][2]["turma"] = 3 - (a["ministros"][2]["turma"] or 1)
    a["vagas"] = []
    avisos = stf.mudancas(a, velho)
    txt = " | ".join(avisos)
    ok("mudança: avisa quem entrou", f"entrou no STF: {saiu['nome']}" in txt, txt[:200])
    ok("mudança: avisa quem saiu", "saiu do STF: Fulano de Tal" in txt)
    ok("mudança: avisa a troca na presidência", "presidência:" in txt)
    ok("mudança: avisa a troca de Turma", any("Turma" in x for x in avisos))
    ok("mudança: avisa a indicação no Senado e as cadeiras vazias",
       (not velho.get("vagas")) or ("indicação no Senado" in txt and "cadeiras vazias: 0 → " in txt))
    ok("sem mudança: nenhum aviso", stf.mudancas(velho, velho) == [])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        stf.avisa("teste")
    ok("aviso vai para o log", "⚠️ STF: teste" in buf.getvalue())

    # 5. o robô diário: conferido há menos de 7 dias -> sai sem pedir nada
    shutil.copy(real, arq)
    stf.CS = T / "cache-vazio"
    log = roda()
    ok("robô diário: não lê de novo antes de uma semana", "próxima leitura" in log and arq.read_bytes() == antes, log.strip()[:140])

    shutil.rmtree(T, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passaram")
    sys.exit(0 if all(RES) else 1)


main()
