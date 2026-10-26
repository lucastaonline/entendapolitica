"""Atualiza, de um computador no Brasil, o que o robô do GitHub não consegue ler.

Os robôs (.github/workflows/atualizar.yml e cidades.yml) rodam no GitHub, fora do Brasil, e alguns sites oficiais de
Assembleias e Câmaras Municipais não aceitam esse acesso: recusam, não respondem ou mandam ao robô regras que proíbem a
leitura. Essas Casas ficam com os dados da última leitura completa, e o site mostra essa data ("Última atualização dos
dados"; infoCasa.conferido, vindo de dados/legislativos.json). Este programa é rodado à mão, num computador no Brasil (não
há rotina automática): lê de novo só as Casas atrasadas, junta tudo (montar.py) e, com --publicar, faz o commit só dos
dados e envia ao GitHub; a Vercel publica sozinha. A skill "entendapolitica-atualizar" do Copilot roda este programa.

Uso (na raiz do repositório):
  python scripts/atualizar_do_brasil.py --so-ver      mostra o que está atrasado e por quê, sem ler nada
  python scripts/atualizar_do_brasil.py               lê as Casas atrasadas e junta tudo, sem publicar
  python scripts/atualizar_do_brasil.py --publicar    ... e publica (commit e push só de dados/, img/pessoas e sitemap)
Opções: --todas (todas as Assembleias e capitais, não só as atrasadas), --casas BA RN 2111300 (só estas), --minutos 50
(limite de tempo da leitura das Casas), --paralelo 27, --mapa (também o mapa das Câmaras e prefeituras: umas 2 horas),
--diarios (também as leis e os vetos das prefeituras pelos Diários Oficiais: 1 a 2 horas), --forcar (roda mesmo com um robô
do GitHub rodando).

Atrasada: a última tentativa falhou, ou a última leitura completa é de mais de 1 dia (Assembleias e capitais, que o robô
diário lê todo dia) ou de mais de 8 dias (as outras Câmaras com SAPL, que o robô das cidades lê uma vez por semana).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / "dados" / "legislativos.json"
DIAS_DIARIO = 1     # Assembleias e capitais: o robô diário lê todo dia
DIAS_SEMANA = 8     # Câmaras com SAPL: o robô das cidades lê cada uma uma vez por semana
PUBLICAVEIS = ("dados/", "img/pessoas/", "sitemap")  # o que este programa pode publicar (nunca código)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S} {msg}", flush=True)


def ler(arq: Path) -> dict:
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def proprias() -> tuple[set[str], set[str]]:
    """Casas com coletor próprio: as Assembleias (scripts/assembleias/<uf>.py) e as capitais (scripts/camaras/c<IBGE>.py)."""
    ale = {a.stem.upper() for a in (RAIZ / "scripts" / "assembleias").glob("*.py") if not a.stem.startswith("_")}
    cap = {a.stem[1:] for a in (RAIZ / "scripts" / "camaras").glob("c*.py")}
    return ale, cap


def ultima_leitura(grupo: str, chave: str, e: dict) -> str | None:
    """A data da última leitura completa: a do índice ("conferido") ou, sem ela, a do arquivo da Casa."""
    arq = RAIZ / "dados" / ("assembleias" if grupo == "assembleias" else "camaras") / f"{chave}.json"
    datas = [x[:10] for x in (e.get("conferido"), ler(arq).get("atualizado")) if isinstance(x, str) and len(x) >= 10]
    return max(datas) if datas else None


def situacao(todas: bool, so: set[str]) -> list[dict]:
    """Cada Casa conhecida, com a última leitura, o limite de dias e se está atrasada (e por quê)."""
    idx = ler(INDICE)
    ale, cap = proprias()
    cidades = {str(c[0]): f"Câmara de {c[1]}/{c[2]}" for c in (json.loads((RAIZ / "dados" / "cidades.json").read_text(encoding="utf-8"))
                                                         if (RAIZ / "dados" / "cidades.json").exists() else []) if len(c) >= 3}
    hoje = dt.date.today()
    out = []
    for grupo, chaves in (("assembleias", sorted(ale)), ("camaras", sorted(cap | set((idx.get("camaras") or {}))))):
        for chave in chaves:
            e = (idx.get(grupo) or {}).get(chave) or {}
            limite = DIAS_DIARIO if grupo == "assembleias" or chave in cap else DIAS_SEMANA
            ult = ultima_leitura(grupo, chave, e)
            dias = (hoje - dt.date.fromisoformat(ult)).days if ult else None
            motivos = []
            if e.get("ok") is False:
                motivos.append("falhou: " + str(e.get("erro") or "?")[:110])
            if dias is None or dias > limite:
                motivos.append("nunca lida por completo" if dias is None else f"última leitura há {dias} dias")
            nome = (e.get("casa") if grupo == "assembleias" else e.get("nome")) or cidades.get(chave) or e.get("casa") or chave
            # a primeira leitura no robô (que começa sem cache) não deixa o dado publicado velho: quem decide é a data
            rodar = (chave in so) if so else ((todas and (grupo == "assembleias" or chave in cap)) or bool(motivos))
            out.append({"grupo": grupo, "chave": chave, "nome": nome, "ultima": ult, "dias": dias, "atrasada": bool(motivos),
                        "motivos": motivos + (["primeira leitura em andamento no robô"] if e.get("pendente") else []), "rodar": rodar})
    return out


def robo_rodando() -> list[str]:
    """Rodadas dos robôs do GitHub em andamento (pelo gh, se ele estiver instalado e com login)."""
    if not shutil.which("gh"):
        return []
    r = subprocess.run(["gh", "run", "list", "--status", "in_progress", "--limit", "5", "--json", "workflowName,createdAt"],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    try:
        return [f"{x['workflowName']} (desde {x['createdAt'][11:16]} UTC)" for x in json.loads(r.stdout or "[]")]
    except ValueError:
        return []


def git(*args: str, ok: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode and not ok:
        raise SystemExit(f"git {' '.join(args)} falhou:\n{r.stdout}{r.stderr}")
    return r


def mudancas_fora_dos_dados() -> list[str]:
    linhas = git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    return [l for l in linhas if not l[3:].strip('"').split(" -> ")[-1].startswith(PUBLICAVEIS)]


def rodar(cmd: list[str]) -> int:
    log("▶ " + " ".join(cmd))
    return subprocess.run([sys.executable, *cmd], cwd=RAIZ).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--so-ver", action="store_true")
    ap.add_argument("--publicar", action="store_true")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--casas", nargs="+", default=[])
    ap.add_argument("--minutos", type=float, default=50)
    ap.add_argument("--paralelo", type=int, default=27)
    ap.add_argument("--mapa", action="store_true")
    ap.add_argument("--diarios", action="store_true")
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    if not (RAIZ / "scripts" / "legislativos.py").exists():
        raise SystemExit("Rode na raiz do repositório entendapolitica.")
    so = {c.upper() for c in a.casas}

    if a.publicar:
        fora = mudancas_fora_dos_dados()
        if fora:
            raise SystemExit("Há mudanças fora de dados/ nesta pasta (este programa só publica dados):\n" + "\n".join(fora[:20]))
        rodando = robo_rodando()
        if rodando and not a.forcar:
            raise SystemExit("Um robô do GitHub está rodando agora: " + "; ".join(rodando) + ". Espere ele terminar (aba Actions) "
                             "e rode de novo; ou use --forcar.")
        log("Atualizando a pasta com o GitHub (git pull)…")
        git("pull", "--rebase", "--autostash", "-q", "origin", "main")

    casas = situacao(a.todas, so)
    atrasadas = [c for c in casas if c["atrasada"]]
    log(f"{len(casas)} Casas conhecidas; {len(atrasadas)} atrasadas:")
    for c in atrasadas:
        print(f"   {'▶' if c['rodar'] else ' '} {c['grupo'][:-1]:<10} {c['chave']:<8} {str(c['nome'])[:48]:<48} "
              f"{c['ultima'] or '—':<10}  {'; '.join(c['motivos'])}", flush=True)
    alvo = [c["chave"] for c in casas if c["rodar"]]
    if a.so_ver:
        log(f"Para ler de novo: {len(alvo)} Casas" + (f" ({', '.join(alvo[:30])}{'…' if len(alvo) > 30 else ''})" if alvo else ""))
        return 0

    if alvo:
        rodar(["scripts/legislativos.py", *alvo, "--paralelo", str(a.paralelo), "--minutos", str(a.minutos)])
    else:
        log("Nenhuma Casa atrasada.")
    if a.mapa:
        rodar(["scripts/municipios/mapear.py"])
    if a.diarios:
        rodar(["scripts/municipios/diarios.py", "--minutos", "120"])
    if not (alvo or a.mapa or a.diarios):
        return 0
    rodar(["scripts/montar.py"])

    # o que esta rodada conseguiu
    depois = {(c["grupo"], c["chave"]): c for c in situacao(False, set())}
    hoje = dt.date.today().isoformat()
    lidas = [k for k in alvo if any(d["chave"] == k and d["ultima"] == hoje for d in depois.values())]
    faltam = [d for d in depois.values() if d["chave"] in alvo and d["ultima"] != hoje]
    log(f"RESUMO: {len(lidas)} de {len(alvo)} Casas lidas por completo hoje" + (f": {', '.join(lidas)}" if lidas else ""))
    for d in faltam:
        log(f"   ainda atrasada: {d['chave']} {str(d['nome'])[:48]} ({'; '.join(d['motivos']) or 'leitura incompleta'})")

    if not a.publicar:
        log("Sem publicar (use --publicar para enviar ao GitHub).")
        return 0
    # "sitemap*.xml" vai para o git como padrão (pega também um sitemap-N.xml que deixou de existir)
    git("add", "-A", "--", "dados", "img/pessoas", "sitemap*.xml")
    if not git("diff", "--cached", "--quiet", ok=True).returncode:
        log("RESULTADO: nada mudou nos dados; nada a publicar.")
        return 0
    msg = (f"Dados atualizados do Brasil em {hoje}\n\nLidas de novo, de um computador no Brasil (scripts/atualizar_do_brasil.py): "
           f"{', '.join(lidas) or 'nenhuma Casa por completo'}.\n\n"
           "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>\n")
    git("commit", "-q", "-m", msg)
    for tentativa in range(3):
        if not git("pull", "--rebase", "-X", "theirs", "-q", "origin", "main", ok=True).returncode and \
                not git("push", "-q", "origin", "HEAD:main", ok=True).returncode:
            log(f"RESULTADO: publicado ({git('rev-parse', '--short', 'HEAD').stdout.strip()}); a Vercel atualiza o site em uns 2 minutos.")
            return 0
        git("rebase", "--abort", ok=True)
    raise SystemExit("Não consegui enviar ao GitHub: o commit ficou nesta pasta. Rode de novo daqui a pouco (ou git push).")


if __name__ == "__main__":
    sys.exit(main())
