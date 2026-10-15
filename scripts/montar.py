"""Junta as peças depois dos coletores:
- dados/tse/federais.json -> eleicao, eleicao2026 e bens nos perfis federais (dados/pessoas/*.json)
  e eleicao2026 nas listas (camara.json, senado.json, executivo.json);
- textos em inglês da eleição de 2026 (txt_en) também nos estados;
- explicações simples (dados/simples/*.json) -> campos "s" e "s_en" das propostas.

Rode por último: python scripts/montar.py
"""
from __future__ import annotations

from comum import *

CARGOS_EN = {
    "presidente": "president", "vice-presidente": "vice president", "senador": "senator", "senadora": "senator",
    "governador": "governor", "governadora": "governor", "vice-governador": "vice governor", "vice-governadora": "vice governor",
    "deputado federal": "federal deputy", "deputada federal": "federal deputy", "deputado estadual": "state deputy",
    "deputada estadual": "state deputy", "deputado distrital": "district deputy", "deputada distrital": "district deputy",
    "1º suplente de senador": "1st alternate senator", "2º suplente de senador": "2nd alternate senator",
    "1o suplente": "1st alternate senator", "2o suplente": "2nd alternate senator",
}


def cargo_en(cargo: str | None) -> str | None:
    if not cargo:
        return None
    c = re.sub(r"\s+", " ", sem_acento(cargo).lower()).strip()
    for pt, en in CARGOS_EN.items():
        if sem_acento(pt) == c:
            return en
    return None


def txt_en(e: dict | None) -> str | None:
    if not e or not e.get("situacao"):
        return None
    c = cargo_en(e.get("cargo"))
    s = e["situacao"]
    if s == "nao-concorreu":
        return "Did not run in 2026"
    if not c:
        return {"eleito": "Elected in 2026", "reeleito": "Re-elected in 2026", "segundo-turno": "In the runoff on 25 Oct 2026",
                "nao-eleito": "Not elected in 2026", "suplente": "Alternate in 2026", "candidato": "Candidate in 2026"}.get(s)
    return {"eleito": f"Elected {c} in 2026", "reeleito": f"Re-elected {c} in 2026",
            "segundo-turno": f"In the runoff for {c} on 25 Oct 2026", "nao-eleito": f"Ran for {c} in 2026 and was not elected",
            "suplente": f"Alternate for {c} in 2026", "candidato": f"Candidate for {c} in 2026"}.get(s)


def com_en(e: dict | None) -> dict | None:
    if not e:
        return e
    e = dict(e)
    t = txt_en(e)
    if t:
        e["txt_en"] = t
    return e


def resumo2026(e: dict | None) -> dict | None:
    """Versão curta para as listas (cartões)."""
    if not e or not e.get("situacao"):
        return None
    return {k: e[k] for k in ("situacao", "cargo", "txt", "txt_en") if e.get(k) is not None}


def main() -> None:
    fed = ler_json(DADOS / "tse" / "federais.json", {}) or {}
    cache = carregar_simples()
    log(f"TSE federais: {len(fed)} | explicações simples no cache: {len(cache)}")

    # ---------- perfis federais
    escritos = 0
    for f in sorted(PESSOAS.glob("*.json")):
        p = ler_json(f)
        if not isinstance(p, dict):
            continue
        t = fed.get(p.get("id")) or {}
        for campo in ("eleicao", "bens"):
            if t.get(campo) is not None:
                p[campo] = t[campo]
        if t.get("eleicao2026") is not None:
            p["eleicao2026"] = com_en(t["eleicao2026"])
        lista = (p.get("propostas") or {}).get("lista") or []
        aplicar_simples(lista, cache)
        if salvar_json(f, sem_mudar_data(p, f)):
            escritos += 1
    log(f"perfis reescritos: {escritos}")

    # ---------- listas da Câmara e do Senado
    for nome in ("camara.json", "senado.json"):
        cam = DADOS / nome
        d = ler_json(cam)
        if not d:
            continue
        for m in d.get("membros", []):
            e = (fed.get(m["id"]) or {}).get("eleicao2026")
            m["eleicao2026"] = resumo2026(com_en(e)) if e else m.get("eleicao2026")
        salvar_json(cam, sem_mudar_data(d, cam))

    # ---------- presidente e vice
    ex_arq = DADOS / "executivo.json"
    ex = ler_json(ex_arq)
    if ex:
        for k in ("presidente", "vice"):
            if ex.get(k):
                e = (fed.get(ex[k]["id"]) or {}).get("eleicao2026")
                if e:
                    ex[k]["eleicao2026"] = resumo2026(com_en(e))
        salvar_json(ex_arq, sem_mudar_data(ex, ex_arq))

    # ---------- estados: txt_en na eleição de 2026
    for arq in sorted((DADOS / "estados").glob("*.json")):
        e = ler_json(arq)
        if not e:
            continue
        for k in ("governador", "vice"):
            if isinstance(e.get(k), dict) and e[k].get("eleicao2026"):
                e[k]["eleicao2026"] = com_en(e[k]["eleicao2026"])
        for m in (e.get("deputadosEstaduais") or {}).get("membros", []):
            if m.get("eleicao2026"):
                m["eleicao2026"] = com_en(m["eleicao2026"])
        salvar_json(arq, sem_mudar_data(e, arq))
    log("pronto")


if __name__ == "__main__":
    main()
