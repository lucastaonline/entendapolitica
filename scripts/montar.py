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
        return {"eleito": "Elected in 2026", "reeleito": "Re-elected in 2026", "segundo-turno": "In the runoff on October 25, 2026",
                "nao-eleito": "Not elected in 2026", "suplente": "Alternate in 2026", "candidato": "Candidate in 2026"}.get(s)
    return {"eleito": f"Elected {c} in 2026", "reeleito": f"Re-elected {c} in 2026",
            "segundo-turno": f"In the runoff for {c} on October 25, 2026", "nao-eleito": f"Ran for {c} in 2026 and was not elected",
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


# mandatos anteriores: só os do mesmo cargo/Casa, para todo mundo (cada fonte oficial só conhece os seus)
MESMO_CARGO = {"dep": r"^deputad[oa] federal", "sen": r"^senador", "pres": r"^presidente", "vp": r"^vice-presidente"}


def mesma_regua(p: dict, t: dict) -> None:
    """Mesma régua para todos os perfis federais: ocupação e escolaridade declaradas ao TSE na candidatura mais
    recente (as Casas e o Planalto descrevem isso de jeitos diferentes, ou não descrevem) e mandatos anteriores
    só no mesmo cargo."""
    ficha = t.get("ficha")
    p.pop("profissoes", None)
    p["ocupacao"] = ({"txt": ficha["ocupacao"], "ano": ficha["ano"], "fonte": ficha["fonte"]}
                     if ficha and ficha.get("ocupacao") else None)
    p["escolaridade"] = ficha.get("escolaridade") if ficha else None
    if ficha and ficha.get("escolaridade"):
        p["escolaridadeFonte"] = ficha["fonte"]
    else:
        p.pop("escolaridadeFonte", None)
    exp = MESMO_CARGO.get((p.get("id") or "").split("-")[0])
    if exp and p.get("mandatosAnteriores"):
        p["mandatosAnteriores"] = [m for m in p["mandatosAnteriores"]
                                   if re.search(exp, sem_acento((m.get("cargo") or "").lower()))]


SITE = "https://entendapolitica.vercel.app"  # endereço público (troque aqui e no robots.txt se mudar)
PAGINAS = ("", "entenda.html", "brasil.html", "estado.html", "imparcialidade.html", "dados.html")


def sitemap() -> int:
    """sitemap.xml com as páginas, os 27 estados e todos os perfis federais, em português e em inglês (?lang=en)."""
    urls = [(p, None) for p in PAGINAS if p == "" or (RAIZ / p).exists()]
    for arq in sorted((DADOS / "estados").glob("*.json")):
        urls.append((f"estado.html?uf={arq.stem}", (ler_json(arq) or {}).get("atualizado")))
    for arq in sorted(PESSOAS.glob("*.json")):
        urls.append((f"pessoa.html?id={arq.stem}", (ler_json(arq) or {}).get("atualizado")))

    def en(c: str) -> str:
        return c + ("&" if "?" in c else "?") + "lang=en"

    def esc(u: str) -> str:
        return u.replace("&", "&amp;")

    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for c, data in urls:
        pt, ing = f"{SITE}/{c}", f"{SITE}/{en(c)}"
        alt = (f'<xhtml:link rel="alternate" hreflang="pt-BR" href="{esc(pt)}"/>'
               f'<xhtml:link rel="alternate" hreflang="en" href="{esc(ing)}"/>'
               f'<xhtml:link rel="alternate" hreflang="x-default" href="{esc(pt)}"/>')
        lm = f"<lastmod>{data}</lastmod>" if data else ""
        for u in (pt, ing):
            linhas.append(f"<url><loc>{esc(u)}</loc>{lm}{alt}</url>")
    linhas.append("</urlset>")
    txt = "\n".join(linhas) + "\n"
    arq = RAIZ / "sitemap.xml"
    if not arq.exists() or arq.read_text(encoding="utf-8") != txt:
        arq.write_text(txt, encoding="utf-8")
    return len(urls) * 2


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
        mesma_regua(p, t)
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
    log(f"sitemap.xml: {sitemap()} endereços")
    log("pronto")


if __name__ == "__main__":
    main()
