"""Remove fontes de imprensa que não são necessárias quando já existe fonte oficial no mesmo slide.
Uso: python testes/limpa_fontes.py  (aplica em conteudo/entenda/ e conteudo/entenda/en/)"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
TIRAR = {"parte-4.json": {"g1-teto-2026"}, "parte-6.json": {"agbrasil-pec-49"}}

for pasta in (RAIZ / "conteudo" / "entenda", RAIZ / "conteudo" / "entenda" / "en"):
    for nome, ids in TIRAR.items():
        f = pasta / nome
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        antes = len(d["fontes"])
        d["fontes"] = [x for x in d["fontes"] if x["id"] not in ids]
        for s in d["slides"]:
            if "fontes" in s:
                s["fontes"] = [x for x in s["fontes"] if x not in ids]
                if not s["fontes"] and s.get("tipo") != "abertura":
                    print("ATENÇÃO: slide ficou sem fonte:", f, s.get("titulo") or s.get("pergunta"))
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{f.relative_to(RAIZ)}: {antes} -> {len(d['fontes'])} fontes")
