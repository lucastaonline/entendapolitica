"""O que o governo do estado fez, no perfil do governador: dados/pessoas/gov-<UF>.json (rodada "nenhum Em breve",
contrato, seção 2). Cada coletor de Assembleia do Nordeste junta isso na mesma leitura, todo dia:

- "propostas": os projetos que o Executivo mandou para a Assembleia (autor "Poder Executivo", "Governador", "Governo do
  Estado" ou o nome de quem governa), com a situação de cada um, calculada com as mesmas regras das propostas dos deputados;
- "executivo": as leis que o governador sancionou e os vetos (totais ou parciais) no período, com fonte e uma nota que diz
  como foi contado. O que não dá para contar com segurança fica fora (e a nota da Casa explica).

Período: desde o começo do mandato de quem está no cargo (o maior entre o início do mandato de governador em curso,
scripts/mandatos.py, e o "desde" da ficha em dados/estados/<UF>.json, para quem assumiu depois).
"""
from __future__ import annotations

import regional
from comum import DADOS, fonte, ler_json, log
from mandatos import vigente

MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
            "December"]


def periodo(uf: str) -> dict:
    """Começo do período, nome e gênero de quem governa (e do vice, que às vezes assina no lugar do titular)."""
    e = ler_json(DADOS / "estados" / f"{uf}.json") or {}
    g, v = e.get("governador") or {}, e.get("vice") or {}
    ini_mandato = vigente("governador", uf=uf)["inicio"]
    desde = (g.get("desde") or "")[:10] or None
    ini = max(ini_mandato, desde) if desde else ini_mandato
    return {"inicio": ini, "mandato": ini_mandato, "assumiu": ini != ini_mandato, "nome": g.get("nome"),
            "genero": g.get("genero"), "vice": v.get("nome") if isinstance(v, dict) else None}


def data_pt(iso: str) -> str:
    a, m, d = iso[:10].split("-")
    return f"{'1º' if d == '01' else int(d)}/{int(m)}/{a}"


def data_en(iso: str) -> str:
    a, m, d = iso[:10].split("-")
    return f"{MESES_EN[int(m) - 1]} {int(d)}, {a}"


def quando(per: dict) -> tuple[str, str]:
    """("desde 1º/1/2023 (começo do mandato)", "since January 1, 2023 (start of the term)")"""
    if per["assumiu"]:
        return (f"desde {data_pt(per['inicio'])}, quando {per['nome']} assumiu o governo",
                f"since {data_en(per['inicio'])}, when {per['nome']} took office as governor")
    return f"desde {data_pt(per['inicio'])} (começo do mandato)", f"since {data_en(per['inicio'])} (start of the term)"


def escopo(per: dict, casa: str, casa_en: str, tipos: str = "projetos de lei, de lei complementar e de emenda à Constituição do estado",
           tipos_en: str = "bills, complementary bills and amendments to the state Constitution", extra: str = "",
           extra_en: str = "") -> tuple[str, str]:
    q, q_en = quando(per)
    return (f"Projetos que o governo do estado mandou para a {casa} {q}: {tipos}. Mensagens, ofícios e vetos não entram."
            + (f" {extra}" if extra else ""),
            f"Bills the state government sent to the {casa_en} {q_en}: {tipos_en}. Messages, official letters and vetoes are "
            f"not included." + (f" {extra_en}" if extra_en else ""))


def bloco_executivo(per: dict, leis: int | None, vetos: int | None, fontes: list[dict], nota: str, nota_en: str,
                    vetos_totais: int | None = None, vetos_parciais: int | None = None,
                    promulgadas_pela_casa: int | None = None) -> dict | None:
    """O bloco "executivo" do contrato; None quando não há nem leis nem vetos contados com segurança."""
    if leis is None and vetos is None:
        return None
    x = {"periodo": {"inicio": per["inicio"], "fim": None}}
    if leis is not None:
        x["leisSancionadas"] = leis
        if promulgadas_pela_casa is not None:
            x["leisPromulgadasPelaCasa"] = promulgadas_pela_casa
    if vetos is not None:
        x["vetos"] = vetos
        if vetos_totais is not None and vetos_parciais is not None:
            x["vetosTotais"], x["vetosParciais"] = vetos_totais, vetos_parciais
    x.update({"fonte": fontes, "nota": nota, "nota_en": nota_en})
    return x


def gravar_gov(uf: str, per: dict, lista: list[dict], escopo_pt: str, escopo_en: str, fonte_prop: dict,
               executivo: dict | None, fontes: list[dict], nota_prop: tuple[str, str] | None = None,
               outros: dict | None = None) -> dict:
    lista = [p for p in lista if (p.get("data") or "9999") >= per["inicio"]]
    bloco = regional.bloco_propostas(lista, escopo_pt, escopo_en, fonte_prop, outros)
    if nota_prop:
        bloco["nota"], bloco["nota_en"] = nota_prop
    dados = {"propostas": bloco}
    if executivo:
        dados["executivo"] = executivo
    # as fontes ficam dentro de cada bloco (propostas.fonte, executivo.fonte); nada de "fontes" no topo: o perfil junta
    # este arquivo à ficha do governador (Object.assign) e "fontes" aqui cobriria as fontes da ficha (posse, eleição)
    regional.salvar_extras(f"gov-{uf}", dados)
    ex = executivo or {}
    r = {"desde": per["inicio"], "propostas": len(lista), "leis": ex.get("leisSancionadas"), "vetos": ex.get("vetos")}
    log(f"  {uf}: governo {r}")
    return r


def autor_do_executivo(nome: str | None, per: dict | None = None) -> bool:
    """O autor é o Poder Executivo? (nomes que as Casas usam; com per, também o nome de quem governa ou do vice)."""
    import re

    from comum import sem_acento
    n = sem_acento((nome or "").lower())
    if re.search(r"poder executivo|governo do estado|governador|governadora|gabinete do governador|chefe do executivo", n):
        return True
    if per:
        for quem in (per.get("nome"), per.get("vice")):
            p = set(regional.palavras(quem))
            if len(p) >= 2 and p <= set(regional.palavras(nome)):
                return True
    return False


def quem_assinou(texto: str) -> bool | None:
    """Pelo texto oficial da lei: False = o governador sancionou ("... e eu sanciono a seguinte Lei"); True = o presidente
    da Assembleia promulgou (sanção tácita ou veto derrubado: "... eu promulgo a seguinte Lei"); None = não deu para saber."""
    import re

    from comum import sem_acento
    t = re.sub(r"\s+", " ", sem_acento((texto or "").lower()))
    if re.search(r"\beu sanciono\b|\bsanciono a (seguinte|presente)\b", t):
        return False
    # "O PRESIDENTE DA ASSEMBLEIA", "O PRESIDENTE EM EXERCÍCIO DA ASSEMBLEIA", "O PRESIDENTE DAASSEMBLEIA" (erro de digitação)
    if re.search(r"\bpromulgo\b", t) and re.search(r"president[ea](?: em exercicio)? ?d[ao] ?(?:assembleia|mesa)|mesa diretora", t):
        return True
    return None


def classificar_leis(rede, leis: dict[str, str], ler, orcamento_s: float = 120, guardar_em: str = "gov-leis.json",
                     decidir=None) -> tuple[dict, int]:
    """Quem assinou cada lei, lendo o texto oficial de cada uma uma única vez (o resultado fica guardado em
    .cache/<casa>/<guardar_em>). leis = {chave: endereço do texto}; ler(endereço) -> texto; decidir(texto) -> True/False/None
    (padrão: quem_assinou). Lê até o limite de tempo por rodada (sem limite com NE_SEM_LIMITE=1); na primeira carga
    (muitos textos por ler, como no robô que começa com o cache vazio), até o fim da rodada (_carga.py). Um texto que não
    abre em 3 rodadas seguidas conta como "sem a informação" (None), para a conta não ficar parada. Devolve
    ({chave: True/False/None}, quantas ainda não foram lidas). Quem chama não grava a conta enquanto faltar alguma."""
    import time

    from . import _carga
    guardado: dict = rede.estado(guardar_em, {}) or {}
    falhas: dict = rede.estado(guardar_em.replace(".json", "-falhas.json"), {}) or {}
    pendentes = [k for k in leis if k not in guardado]
    limite = _carga.limite_diario(orcamento_s, primeira=len(pendentes) > 30)
    t0, lidas, seguidas = time.time(), 0, 0
    for k in pendentes:
        url = leis[k]
        if time.time() - t0 > limite or _carga.acabou() or seguidas >= 3:  # 3 falhas seguidas: o site deve estar fora
            break
        try:
            guardado[k] = (decidir or quem_assinou)(ler(url))
            falhas.pop(k, None)
            seguidas = 0
        except _carga.SemTempo:
            break
        except Exception as e:
            log(f"  lei {k}: texto não lido ({type(e).__name__}: {e})")
            falhas[k] = falhas.get(k, 0) + 1
            seguidas += 1
            if falhas[k] >= 3:
                guardado[k] = None
            continue
        lidas += 1
        if lidas % 50 == 0:
            rede.guardar(guardado, guardar_em)
    rede.guardar(guardado, guardar_em)
    rede.guardar(falhas, guardar_em.replace(".json", "-falhas.json"))
    return {k: guardado.get(k) for k in leis}, sum(1 for k in leis if k not in guardado)


def nota_leis(per: dict, total: int, sancionadas: int, promulgadas: int, sem: int, fonte_pt: str, fonte_en: str,
              criterio: tuple[str, str] | None = None) -> tuple[str, str]:
    """Texto padrão da nota das leis contadas pelo texto oficial de cada uma (mesma régua do perfil do presidente: conta
    tudo o que o governo sancionou no período, inclusive quando outra pessoa estava no exercício do cargo)."""
    crit, crit_en = criterio or ("em que o texto oficial diz \"eu sanciono\"", "whose official text says \"I sign\" (\"eu sanciono\")")
    pt = (f"Leis: das {total} leis ordinárias e complementares com data a partir de {data_pt(per['inicio'])} {fonte_pt}, "
          f"contam como sancionadas as {sancionadas} {crit} (assinadas pelo governador ou por quem estava no exercício do "
          f"cargo).")
    en = (f"Laws: of the {total} ordinary and complementary laws dated from {data_en(per['inicio'])} on {fonte_en}, the "
          f"{sancionadas} {crit_en} count as signed (by the governor or by whoever was acting as governor).")
    fora = ([f"{promulgadas} que o presidente da Assembleia promulgou (quando o governador não sanciona no prazo ou quando o "
             f"veto é derrubado)"] if promulgadas else []) + ([f"{sem} em que o texto não diz quem assinou"] if sem else [])
    fora_en = ([f"{promulgadas} promulgated by the Assembly's president (when the governor does not sign in time or a veto is "
                f"overridden)"] if promulgadas else []) + ([f"{sem} whose text does not say who signed"] if sem else [])
    if fora:
        pt += " Ficam de fora " + " e ".join(fora) + "."
        en += " Left out: " + " and ".join(fora_en) + "."
    return pt, en


__all__ = ["periodo", "data_pt", "data_en", "quando", "escopo", "bloco_executivo", "gravar_gov", "autor_do_executivo", "fonte",
           "quem_assinou", "classificar_leis", "nota_leis"]
