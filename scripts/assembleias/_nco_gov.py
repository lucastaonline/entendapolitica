"""O que o governo do estado fez, para o perfil do governador (dados/pessoas/gov-<UF>.json), nos estados do Norte e do
Centro-Oeste: os projetos que o Poder Executivo mandou para a Assembleia (com a situação, como as propostas dos deputados)
e o bloco "executivo" (leis sancionadas e vetos no período), no mesmo formato do presidente.

Período: desde o começo do mandato de quem governa hoje, isto é, a posse do mandato (mandatos.vigente("governador"):
1º/1/2023; 6/1/2027 no próximo) ou, se outra pessoa assumiu depois (vice, presidente da Assembleia, eleição indireta), o
"desde" da ficha do governador em dados/estados/<UF>.json. Cada coletor de Assembleia chama isto no fim da rodada. O que
não dá para contar com segurança fica fora (o campo não vai para o arquivo) e o motivo vai nas notas da Casa.
"""
from __future__ import annotations

import datetime as dt

import regional
from comum import DADOS, PESSOAS, fonte, ler_json, log
from mandatos import vigente

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]
MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
            "December"]

# tipos das propostas do governo (os mesmos códigos das outras propostas; MPV = medida provisória, como no presidente)
TIPOS_TXT = {"PL": ("projetos de lei (PL)", "bills (PL)"), "PLP": ("de lei complementar (PLP)", "complementary bills (PLP)"),
             "PEC": ("de emenda à Constituição do estado (PEC)", "amendments to the state Constitution (PEC)"),
             "PDL": ("de decreto legislativo (PDL)", "legislative decrees (PDL)"),
             "MPV": ("medidas provisórias (MPV)", "provisional measures (MPV)")}
ORDEM = ["PL", "PLP", "PEC", "PDL", "MPV"]

# frases comuns das notas
PROMULGADAS_INCLUIDAS = ("O cadastro não separa as leis promulgadas pela própria Assembleia (quando ela derruba um veto, por "
                         "exemplo); se houver, estão na conta.",
                         "The records do not separate laws promulgated by the state assembly itself (when it overrides a "
                         "veto, for example); any such laws are included in the count.")
EM_EXERCICIO = ("Conta o que o governo do estado assinou no período, inclusive quando outra pessoa estava no exercício do "
                "cargo (numa viagem do governador, por exemplo).",
                "Counts what the state government signed in the period, including when someone else was acting as "
                "governor (during a trip by the governor, for example).")


def governo_atual(uf: str) -> dict:
    """Quem governa hoje e desde quando o que ele fez conta: {"nome", "genero", "inicio", "assumiu"}."""
    e = ler_json(DADOS / "estados" / f"{uf}.json") or {}
    g = e.get("governador") or {}
    mandato = vigente("governador", uf=uf)["inicio"]
    desde = str(g.get("desde") or "")[:10]
    inicio = desde if desde > mandato else mandato
    return {"nome": (g.get("nome") or "").strip(), "nomeCivil": (g.get("nomeCivil") or "").strip(), "genero": g.get("genero"),
            "inicio": inicio, "assumiu": inicio != mandato}


def data_pt(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{'1º' if d.day == 1 else d.day} de {MESES[d.month - 1]} de {d.year}"


def data_en(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{MESES_EN[d.month - 1]} {d.day}, {d.year}"


def numero(n: int, en: bool = False) -> str:
    """8562 -> '8.562' (como as leis são citadas); em inglês, '8,562'."""
    return f"{int(n):,}" if en else f"{int(n):,}".replace(",", ".")


def lista_pt(itens: list[str], e: str = "e") -> str:
    itens = [i for i in itens if i]
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + f" {e} " + itens[-1] if itens else ""


def periodo(g: dict) -> tuple[str, str]:
    if g["assumiu"]:
        # em inglês sem o nome: sobrenomes como "Cidade" parecem português para o teste de texto (verifica_texto)
        return (f"desde {data_pt(g['inicio'])}, quando {g['nome']} assumiu o governo",
                f"since {data_en(g['inicio'])}, when the current governor took office")
    return f"desde {data_pt(g['inicio'])}, começo do mandato atual", f"since {data_en(g['inicio'])}, the start of the current term"


def escopo(g: dict, tipos: list[str]) -> tuple[str, str]:
    """Texto que diz o que entra em "O que ele propôs"."""
    ts = [t for t in ORDEM if t in set(tipos)]
    pt = [TIPOS_TXT[t][0] for t in ts]
    if pt and not pt[0].startswith(("projetos", "medidas")):
        pt[0] = "projetos " + pt[0]
    en = [TIPOS_TXT[t][1] for t in ts]
    per, per_en = periodo(g)
    return (f"Projetos que o governo do estado mandou para a Assembleia Legislativa {per}: {lista_pt(pt)}. "
            "Vetos e mensagens não entram aqui.",
            f"Bills the state government sent to the state legislature {per_en}: {lista_pt(en, 'and')}. "
            "Vetoes and messages are not included here.")


def contar_leis(leis: list[dict], inicio: str, fim: str | None = None, existentes: set | None = None) -> dict:
    """leis = [{"tipo": "LO"|"LC", "numero": int, "data": "AAAA-MM-DD", "promulgada": bool|None}] (repetidas contam uma
    vez). Devolve os totais do período, a primeira e a última de cada tipo e os números que faltam no meio (existentes =
    {(tipo, número)} de todas as leis lidas, inclusive as que não entram na conta: essas não são falta)."""
    vistos, r = set(), {"LO": [], "LC": []}
    for x in leis:
        d = x.get("data") or ""
        if not d or d < inicio or (fim and d > fim) or x["tipo"] not in r:
            continue
        chave = (x["tipo"], int(x["numero"]))
        if chave in vistos:
            continue
        vistos.add(chave)
        r[x["tipo"]].append(x)
    out = {"total": 0, "promulgadas": 0, "ultima": None, "tipos": {}}
    for t, xs in r.items():
        if not xs:
            continue
        nums = sorted(int(x["numero"]) for x in xs)
        tem = set(nums) | {n for (tt, n) in (existentes or set()) if tt == t}
        faltam = [n for n in range(nums[0], nums[-1] + 1) if n not in tem]
        prom = sum(1 for x in xs if x.get("promulgada"))
        out["tipos"][t] = {"n": len(xs), "de": nums[0], "ate": nums[-1], "faltam": faltam, "promulgadas": prom,
                           "ultimaData": max(x["data"] for x in xs)}
        out["total"] += len(xs)
        out["promulgadas"] += prom
        out["ultima"] = max(out["ultima"] or "", max(x["data"] for x in xs))
    return out


def texto_leis(c: dict, de_onde: tuple[str, str], promulgadas: tuple[str, str] | None = None) -> tuple[str, str]:
    """Frase da nota sobre como as leis foram contadas. de_onde = ("no cadastro de normas da Assembleia (SAPL)", "in the
    ...") ; promulgadas = frase sobre as leis promulgadas pela Assembleia (separadas ou incluídas)."""
    partes, partes_en = [], []
    for t, nome, nome_en in (("LO", "ordinárias", "ordinary"), ("LC", "complementares", "complementary")):
        x = c["tipos"].get(t)
        if not x:
            continue
        faixa = f"nº {numero(x['de'])} a {numero(x['ate'])}" if x["de"] != x["ate"] else f"nº {numero(x['de'])}"
        faixa_en = (f"No. {numero(x['de'], True)} to {numero(x['ate'], True)}" if x["de"] != x["ate"]
                    else f"No. {numero(x['de'], True)}")
        partes.append(f"{x['n']} {nome if x['n'] != 1 else nome[:-2] if nome.endswith('es') else nome[:-1]} ({faixa})")
        partes_en.append(f"{x['n']} {nome_en} ({faixa_en})")
    pt = f"Leis: {lista_pt(partes)}, {de_onde[0]}"
    en = f"Laws: {lista_pt(partes_en, 'and')}, {de_onde[1]}"
    if c.get("ultima"):
        pt += f"; a mais recente é de {data_pt(c['ultima'])}"
        en += f"; the most recent one is from {data_en(c['ultima'])}"
    pt, en = pt + ".", en + "."
    falt = [(t, n) for t, x in c["tipos"].items() for n in x["faltam"]]
    if falt:
        nums = lista_pt([numero(n) for _, n in falt[:6]]) + (" e outros" if len(falt) > 6 else "")
        nums_en = lista_pt([numero(n, True) for _, n in falt[:6]], "and") + (" and others" if len(falt) > 6 else "")
        pt += (f" {len(falt)} número{'s' if len(falt) > 1 else ''} do período ({nums}) não aparece{'m' if len(falt) > 1 else ''} "
               "no cadastro e não entra" + ("m" if len(falt) > 1 else "") + " na conta.")
        en += (f" {len(falt)} number{'s' if len(falt) > 1 else ''} in the period ({nums_en}) "
               f"{'are' if len(falt) > 1 else 'is'} missing from the records and not counted.")
    if promulgadas:
        pt += " " + promulgadas[0]
        en += " " + promulgadas[1]
    return pt, en


def texto_vetos(v: dict, de_onde: tuple[str, str]) -> tuple[str, str]:
    """v = {"total", "totais", "parciais"}."""
    det = ""
    det_en = ""
    if v.get("totais") is not None and v.get("parciais") is not None:
        det = f" ({v['totais']} totais e {v['parciais']} parciais)"
        det_en = f" ({v['totais']} full and {v['parciais']} partial)"
    return (f"Vetos: {v['total']}{det}, {de_onde[0]}.", f"Vetoes: {v['total']}{det_en}, {de_onde[1]}.")


def bloco_executivo(g: dict, leis: dict | None, vetos: dict | None, fontes: list[dict], nota: list[str],
                    nota_en: list[str]) -> dict | None:
    """O bloco "executivo" do perfil. leis = contar_leis(...) ou None; vetos = {"total", "totais", "parciais", "ultimo"} ou
    None. O que é None fica fora do arquivo (a página mostra só o que existe)."""
    if not leis and not vetos:
        return None
    e = {"periodo": {"inicio": g["inicio"], "fim": None}}
    if leis:
        e["leisSancionadas"] = leis["total"]
        if leis.get("ultima"):
            e["periodo"]["ultimaLei"] = leis["ultima"]
    if vetos:
        e["vetos"] = vetos["total"]
        for k, campo in (("totais", "vetosTotais"), ("parciais", "vetosParciais")):
            if vetos.get(k) is not None:
                e[campo] = vetos[k]
        if vetos.get("ultimo"):
            e["periodo"]["ultimoVeto"] = vetos["ultimo"]
    e["fonte"] = fontes
    e["nota"] = " ".join(n for n in nota if n)
    e["nota_en"] = " ".join(n for n in nota_en if n)
    return e


def gravar_gov(uf: str, propostas: dict | None = None, executivo: dict | None = None, fontes: list[dict] | None = None,
               diario: dict | None = None, inicio: str | None = None) -> None:
    """dados/pessoas/gov-<UF>.json. diario = {"nome", "url"} do Diário Oficial do estado (o quadro "Onde ver mais" mostra o
    link quando as leis e os vetos não estão no site); inicio = começo do período (fica em "governoDesde": se a pessoa no
    governo mudar e a rodada falhar, descartar_se_velho apaga o arquivo da pessoa anterior). fontes: não vai mais para o
    arquivo (cada bloco já traz a sua; o parâmetro fica para os coletores que o passam)."""
    d: dict = {"governoDesde": inicio or governo_atual(uf)["inicio"]}
    if propostas is not None:
        d["propostas"] = propostas
    if executivo:
        d["executivo"] = executivo
    if diario:
        d["diarioOficial"] = diario
    if len(d) == 1:
        log(f"  gov-{uf}: nada para gravar")
        return
    # as fontes ficam dentro de cada bloco (propostas.fonte, executivo.fonte); nada de "fontes" no topo: o perfil junta
    # este arquivo à ficha do governador (Object.assign) e "fontes" aqui cobriria as fontes da ficha (posse, eleição)
    regional.salvar_extras(f"gov-{uf}", d)
    n = len((propostas or {}).get("lista") or [])
    ex = executivo or {}
    log(f"  gov-{uf}: {n} projetos do Executivo, {ex.get('leisSancionadas', '—')} leis, {ex.get('vetos', '—')} vetos")


def existe(uf: str) -> bool:
    return (PESSOAS / f"gov-{uf}.json").exists()


def descartar_se_velho(uf: str) -> None:
    """Depois de uma falha: se o arquivo gov-<UF> é de outro período (outra pessoa no governo, por exemplo na posse de
    2027), apaga, para o perfil de quem governa hoje não mostrar o que outra pessoa fez."""
    arq = PESSOAS / f"gov-{uf}.json"
    d = ler_json(arq) if arq.exists() else None
    if d is not None and d.get("governoDesde") != governo_atual(uf)["inicio"]:
        arq.unlink()
        log(f"  gov-{uf}: o arquivo era de outro período e foi apagado")


__all__ = ["governo_atual", "data_pt", "data_en", "numero", "lista_pt", "periodo", "escopo", "contar_leis", "texto_leis",
           "texto_vetos", "bloco_executivo", "gravar_gov", "existe", "descartar_se_velho", "fonte", "TIPOS_TXT",
           "PROMULGADAS_INCLUIDAS", "EM_EXERCICIO"]
