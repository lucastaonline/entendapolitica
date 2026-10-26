"""Simulação do robô das cidades para as leis e os vetos das prefeituras (scripts/municipios/diarios.py), sem rede:
numa cópia separada (scripts/ e os dados que ele lê), com o cache VAZIO (como o robô do GitHub começa) e TODOS os pedidos
falhando (um proxy que não existe), a rodada tem de terminar sem mudar nenhum byte de dados/prefeituras/<UF>.json: cidade
que não deu para ler fica pendente, com o que já estava publicado (nunca some, nunca vira "fora", nunca fica com uma
contagem menor). As rotas de cada cidade ficam no próprio arquivo publicado ("rotas"), então o robô sabe onde ler mesmo
sem o cache e sem o link que o mapa das cidades acha no site da prefeitura.
Não precisa do servidor. Uso: python testes/diarios_robo.py [UF ...]   (sem UF: todos os estados com arquivo)"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def resumo(pasta: Path) -> dict:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(pasta.glob("*.json"))}


def main() -> int:
    ufs = [a.upper() for a in sys.argv[1:]] or [f.stem for f in sorted((RAIZ / "dados" / "prefeituras").glob("*.json"))]
    with tempfile.TemporaryDirectory(prefix="ep-robo-") as tmp:
        sim = Path(tmp)
        shutil.copytree(RAIZ / "scripts", sim / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for d in ("municipios", "prefeituras", "cidades", "manual"):
            shutil.copytree(RAIZ / "dados" / d, sim / "dados" / d)
        for f in (RAIZ / "dados").glob("*.json"):
            shutil.copy2(f, sim / "dados" / f.name)
        antes = resumo(sim / "dados" / "prefeituras")
        cache_vazio_no_comeco = not (sim / ".cache").exists()  # o robô na primeira vez
        env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="",
                   http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", no_proxy="", PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "scripts/municipios/diarios.py", *ufs, "--minutos", "3"], cwd=sim, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        depois = resumo(sim / "dados" / "prefeituras")
        mudou = [n for n in antes if antes[n] != depois.get(n)] + [n for n in depois if n not in antes]
        pedidos_ok = "Pronto" in r.stdout + r.stderr
        res = [
            ("a rodada termina sem erro", r.returncode == 0 and pedidos_ok, (r.stdout + r.stderr).strip().splitlines()[-1:] if r.returncode else ""),
            (f"cache vazio e rede toda falhando: {len(antes)} arquivos iguais byte a byte", cache_vazio_no_comeco and not mudou, ", ".join(mudou)),
        ]
    for nome, cond, extra in res:
        print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))
    print(f"\n{sum(1 for _, c, _ in res if c)}/{len(res)} ok")
    return 0 if all(c for _, c, _ in res) else 1


if __name__ == "__main__":
    sys.exit(main())
