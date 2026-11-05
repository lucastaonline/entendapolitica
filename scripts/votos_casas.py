"""As votações recentes de cada Assembleia Legislativa e de cada Câmara Municipal, com o voto de cada pessoa
(site-d-r16: a aba "Como votaram" das páginas do estado e da cidade).

Hoje o voto de cada pessoa só existe dentro do perfil dela (dados/pessoas/dest-<UF>-*.json, campo "votacoes") ou, nas
Câmaras Municipais, dentro do arquivo da cidade (dados/camaras/extras/<IBGE>.json, "pessoas"). Para mostrar "uma votação ->
o voto de cada pessoa" o navegador teria de baixar todos os perfis da Casa (2 a 6 MB). Este script junta, a partir do que
já está em dados/ (nenhum pedido aos sites oficiais), um arquivo pequeno por Casa com o voto de alguém guardado:

  dados/votacoes/assembleias/<UF>.json   (as Assembleias com votações nominais nos perfis dos deputados)
  dados/votacoes/camaras/<IBGE>.json     (as Câmaras Municipais com votações nominais no arquivo da cidade)

  { "uf", "ibge" (Câmara), "casa" (sigla), "nome", "nome_en", "site", "escopo", "escopo_en", "fontes",
    "total": quantas votações nominais o site tem da Casa, "recentes": quantas vêm no arquivo,
    "pessoas": [[id, nome, partido, foto, genero]]  (quem tem voto nas votações do arquivo, em ordem alfabética),
    "votacoes": [ { "id", "data", "proposta", "propostaId", "descricao", "resultado", "url",
                    "placar": o placar oficial (ou null, quando a Casa não publica o placar junto: AM, GO, PA, RO),
                    "ementa"?, "urlProposta"?, "s"?, "s_en"?: da proposta, quando ela está na lista "O que propôs" de algum
                                                              perfil da Casa (a explicação simples é feita por IA),
                    "votos": { "<voto oficial>": [índices em "pessoas"] } } ],   (da mais nova para a mais antiga)
    "atualizado" }

Só entra quem tem perfil no site (quem está na Casa hoje e tem o voto guardado): o placar oficial conta todos que votaram
na época, e a página diz isso quando as contas não batem. O CPF nunca entra (os arquivos de origem não têm).

Roda no fim do scripts/montar.py (montar.py chama gravar()); à mão: python scripts/votos_casas.py
"""
from __future__ import annotations


import sys
from collections import Counter

from comum import DADOS, PESSOAS, EXTRAS_CIDADES, chave_nome, hoje, ler_json, log, salvar_json, sem_mudar_data

RECENTES = 30
SAIDA_ALE = DADOS / "votacoes" / "assembleias"
SAIDA_CAM = DADOS / "votacoes" / "camaras"


def _mais_comum(valores):
    c = Counter(v for v in valores if v)
    return c.most_common(1)[0][0] if c else None


def _fontes(lista):
    vistas, out = set(), []
    for f in lista:
        if isinstance(f, dict) and f.get("url") and (f["url"], f.get("titulo")) not in vistas:
            vistas.add((f["url"], f.get("titulo")))
            out.append(f)
    return out


def _props(perfis) -> dict:
    """O que o site sabe de cada proposta (pelo id da proposta, o mesmo das votações): a ementa, a página oficial e a
    explicação simples (feita por IA a partir da ementa), lidos das listas "O que propôs" dos perfis."""
    out = {}
    for p in perfis:
        for y in ((p or {}).get("propostas") or {}).get("lista") or []:
            if y.get("id") and y["id"] not in out:
                out[y["id"]] = {c: y.get(c) for c in ("ementa", "url", "s", "s_en")}
    return out


def _arquivo(meta: dict, votos: dict[str, dict], membros: dict[str, dict], blocos: list[dict], ordem: dict[str, tuple], props: dict | None = None) -> dict | None:
    """meta: o que foi votado (chave -> {data, proposta, ...}); votos: chave -> {pessoaId: voto}; membros: id -> {nome, partido,
    foto, genero}; blocos: os blocos "votacoes" dos perfis (escopo e fonte); ordem: chave -> desempate (a mais nova primeiro);
    props: id da proposta -> {ementa, url, s, s_en} (o que entra em "Do que se trata")."""
    chaves = [k for k in meta if votos.get(k)]
    if not chaves:
        return None
    chaves.sort(key=lambda k: (meta[k].get("data") or "", ordem.get(k, (0,))), reverse=True)
    rec = chaves[:RECENTES]
    ids = sorted({p for k in rec for p in votos[k] if p in membros}, key=lambda p: (chave_nome(membros[p].get("nome") or ""), p))
    if not ids:
        return None
    idx = {p: i for i, p in enumerate(ids)}
    out = []
    for k in rec:
        m = meta[k]
        grupos: dict[str, list] = {}
        for p, v in votos[k].items():
            if p in idx:
                grupos.setdefault(v or "NR", []).append(idx[p])
        for g in grupos.values():
            g.sort()
        pl = m.get("placar")
        item = {"id": k, "data": m.get("data"), "proposta": m.get("proposta"), "propostaId": m.get("propostaId"),
                "descricao": m.get("descricao"), "resultado": m.get("resultado"), "url": m.get("url"),
                "placar": pl if isinstance(pl, dict) and pl.get("total") is not None else None, "votos": grupos}
        pr = (props or {}).get(m.get("propostaId")) or {}
        for c, nome in (("ementa", "ementa"), ("url", "urlProposta"), ("s", "s"), ("s_en", "s_en")):
            # a ementa só entra quando diz algo além da descrição da votação (em muitas Casas, as duas são o mesmo texto)
            if pr.get(c) and not (c == "ementa" and chave_nome(pr[c])[:120] in chave_nome(m.get("descricao") or "")):
                item[nome] = pr[c]
        out.append(item)
    return {
        "escopo": _mais_comum(b.get("escopo") for b in blocos), "escopo_en": _mais_comum(b.get("escopo_en") for b in blocos),
        "fontes": _fontes([b.get("fonte") for b in blocos]),
        "total": len(chaves), "recentes": len(rec),
        "pessoas": [[p, membros[p].get("nome"), membros[p].get("partido"), membros[p].get("foto"), membros[p].get("genero")] for p in ids],
        "votacoes": out,
    }


def assembleia(uf: str) -> dict | None:
    est = ler_json(DADOS / "estados" / f"{uf}.json") or {}
    membros = {m["id"]: m for m in ((est.get("deputadosEstaduais") or {}).get("membros") or []) if m.get("id")}
    ale = ler_json(DADOS / "assembleias" / f"{uf}.json") or {}
    meta, votos, ordem, blocos, catalogos, perfis = {}, {}, {}, [], {}, []
    for f in sorted(PESSOAS.glob(f"dest-{uf}-*.json")) + [PESSOAS / f"gov-{uf}.json"]:
        p = ler_json(f) or {}
        perfis.append(p)
        v = p.get("votacoes") or {}
        pid = p.get("id") or f.stem
        if not v or pid not in membros:
            continue
        blocos.append(v)
        # CE, PB, PI, RN, SC: o que foi votado vem dentro do perfil ("lista", da mais nova para a mais antiga)
        for pos, x in enumerate(v.get("lista") or []):
            k = x.get("id")
            if not k:
                continue
            if k not in meta:
                meta[k] = {c: x.get(c) for c in ("data", "proposta", "propostaId", "descricao", "resultado", "placar", "url")}
            ordem.setdefault(k, (-pos,))
            votos.setdefault(k, {})[pid] = x.get("voto")
        # AM, GO, PA, RO: catálogo da Casa (dados/votacoes/<sigla>.json) + [chave, voto] no perfil
        if v.get("votos") and v.get("arquivo"):
            arq = v["arquivo"]
            if arq not in catalogos:
                catalogos[arq] = ler_json(DADOS.parent / arq) or {}
            cat = (catalogos[arq].get("votacoes") or {})
            for x in v["votos"]:
                k, voto = x[0], (x[1] if len(x) > 1 else None)
                if k in cat:
                    if k not in meta:
                        meta[k] = dict(cat[k])
                    votos.setdefault(k, {})[pid] = voto
    for arq, c in catalogos.items():
        for pos, k in enumerate(c.get("votacoes") or {}):
            ordem[k] = (-pos,)
        if c.get("fonte"):
            blocos.append({"fonte": c["fonte"]})
    d = _arquivo(meta, votos, membros, blocos, ordem, _props(perfis))
    if not d:
        return None
    return dict({"uf": uf, "ibge": None, "casa": ale.get("sigla"), "nome": ale.get("casa"), "nome_en": ale.get("casa_en"),
                 "site": ale.get("site")}, **d, atualizado=hoje())


def camara(ibge: str) -> dict | None:
    ex = ler_json(EXTRAS_CIDADES / f"{ibge}.json") or {}
    k = ler_json(DADOS / "camaras" / f"{ibge}.json") or {}
    achou = sorted((DADOS / "cidades").glob(f"*/{ibge}.json"))
    uf = k.get("uf") or (achou[0].parent.name if achou else None)
    cid = (ler_json(achou[0]) if achou else None) or {}
    cid = cid if isinstance(cid, dict) else {}
    membros = {m["id"]: m for m in (k.get("membros") or []) if m.get("id")}
    for m in ((cid.get("vereadores") or {}).get("membros") or []):
        if m.get("id"):
            membros[m["id"]] = dict(membros.get(m["id"]) or {}, **{c: v for c, v in m.items() if v is not None})
    cat = ex.get("votacoes") or {}
    ordem = {c: (-pos,) for pos, c in enumerate(cat)}
    meta = {c: dict(v) for c, v in cat.items()}
    votos, blocos = {}, []
    for pid, p in (ex.get("pessoas") or {}).items():
        v = p.get("votacoes") or {}
        if not v.get("votos") or not pid.startswith("ver-"):
            continue
        blocos.append(v)
        for x in v["votos"]:
            if x and x[0] in meta:
                votos.setdefault(x[0], {})[pid] = x[1] if len(x) > 1 else None
    d = _arquivo(meta, votos, membros, blocos, ordem, _props((ex.get("pessoas") or {}).values()))
    if not d:
        return None
    return dict({"uf": uf, "ibge": str(ibge), "casa": k.get("sigla"), "nome": k.get("casa"), "nome_en": k.get("casa_en"),
                 "site": k.get("site")}, **d, atualizado=hoje())


def gravar() -> str:
    """Grava um arquivo por Casa com votações nominais e apaga o de quem deixou de ter (o arquivo não fica velho). Vale o que
    está nos dados de hoje: toda Assembleia e toda Câmara Municipal com o voto de alguém guardado (os perfis e os arquivos das
    cidades), mesmo se a última leitura da Casa falhou (aí ficam os dados da última que deu certo, como na página)."""
    idx = ler_json(DADOS / "legislativos.json", {}) or {}
    ufs = sorted(set(idx.get("assembleias") or {}) | {f.stem.split("-")[1] for f in PESSOAS.glob("dest-*.json")})
    cams = sorted(set(idx.get("camaras") or {}) | {f.stem for f in EXTRAS_CIDADES.glob("*.json")})
    feitos = {"ale": set(), "cam": set()}
    for grupo, saida, fn, casas in (("assembleias", SAIDA_ALE, assembleia, ufs), ("camaras", SAIDA_CAM, camara, cams)):
        chave = "ale" if grupo == "assembleias" else "cam"
        for casa in casas:
            try:
                d = fn(casa)
            except Exception as e:  # um arquivo de origem quebrado não pode parar o resto
                log(f"  votos_casas: {grupo}/{casa}: {e}")
                continue
            if not d:
                continue
            arq = saida / f"{casa}.json"
            salvar_json(arq, sem_mudar_data(d, arq))
            feitos[chave].add(casa)
    for chave, saida in (("ale", SAIDA_ALE), ("cam", SAIDA_CAM)):
        if saida.exists():
            for f in saida.glob("*.json"):
                if f.stem not in feitos[chave]:
                    f.unlink()
    return f"{len(feitos['ale'])} Assembleias e {len(feitos['cam'])} Câmaras Municipais"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    log(f"votações recentes por Casa: {gravar()}")
