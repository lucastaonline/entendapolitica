"""IBGE: estados, municípios (código de 7 dígitos), capitais e a correspondência TSE ↔ IBGE.

O TSE usa um código próprio de município (SG_UE, 5 dígitos). A correspondência com o código
do IBGE é feita por nome + UF normalizados (chave_nome). Os nomes que são escritos de jeito
diferente no TSE e no IBGE ficam no dicionário EXCECOES_TSE, conferido à mão.

Uso:
    python scripts/ibge.py          # baixa/atualiza o cache (.cache/ibge) e mostra um resumo

Outros scripts usam:
    import ibge
    ibge.municipios()               # {ibge: {"ibge","nome","uf"}} (só municípios de verdade)
    ibge.estados()                  # {uf: nome}
    ibge.capital(uf)                # {"ibge","nome"}
    ibge.casar_tse({sg_ue: (uf, nome_tse)})   # {sg_ue: ibge}, com conferência
"""
from __future__ import annotations

import functools
import sys

from comum import *

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
URL_ESTADOS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
PAGINA_CODIGOS = "https://www.ibge.gov.br/explica/codigos-dos-municipios.php"
IDADE_CACHE_H = 24 * 7

UF_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

# Código IBGE das capitais (conferido com o nome na API do IBGE em cada execução).
CAPITAIS = {
    "AC": ("1200401", "Rio Branco"), "AL": ("2704302", "Maceió"), "AM": ("1302603", "Manaus"),
    "AP": ("1600303", "Macapá"), "BA": ("2927408", "Salvador"), "CE": ("2304400", "Fortaleza"),
    "DF": ("5300108", "Brasília"), "ES": ("3205309", "Vitória"), "GO": ("5208707", "Goiânia"),
    "MA": ("2111300", "São Luís"), "MG": ("3106200", "Belo Horizonte"), "MS": ("5002704", "Campo Grande"),
    "MT": ("5103403", "Cuiabá"), "PA": ("1501402", "Belém"), "PB": ("2507507", "João Pessoa"),
    "PE": ("2611606", "Recife"), "PI": ("2211001", "Teresina"), "PR": ("4106902", "Curitiba"),
    "RJ": ("3304557", "Rio de Janeiro"), "RN": ("2408102", "Natal"), "RO": ("1100205", "Porto Velho"),
    "RR": ("1400100", "Boa Vista"), "RS": ("4314902", "Porto Alegre"), "SC": ("4205407", "Florianópolis"),
    "SE": ("2800308", "Aracaju"), "SP": ("3550308", "São Paulo"), "TO": ("1721000", "Palmas"),
}

# Localidades com código IBGE que NÃO são municípios (não têm prefeito nem vereadores).
NAO_MUNICIPIOS = {
    "5300108": "Brasília: o Distrito Federal não pode ser dividido em municípios (Constituição, art. 32)",
    "2605459": "Fernando de Noronha: distrito estadual de Pernambuco, sem prefeito nem vereadores",
}

# Município com nome diferente no TSE e no IBGE: código TSE (SG_UE) -> código IBGE.
EXCECOES_TSE = {
    "00256": "1100098",  # RO: ESPIGÃO DO OESTE (TSE) = Espigão D'Oeste (IBGE)
    "00337": "1100346",  # RO: ALVORADA DO OESTE = Alvorada D'Oeste
    "03158": "1400605",  # RR: SÃO LUIZ = São Luiz do Anauá
    "04120": "1502954",  # PA: ELDORADO DOS CARAJÁS = Eldorado do Carajás
    "05290": "1506500",  # PA: SANTA ISABEL DO PARÁ = Santa Izabel do Pará
    "17035": "2405306",  # RN: BOA SAÚDE = Januário Cicco
    "31011": "2800100",  # SE: AMPARO DE SÃO FRANCISCO = Amparo do São Francisco
    "34118": "2905602",  # BA: CAMACÃ = Camacan
    "41092": "3105509",  # MG: BARÃO DE MONTE ALTO = Barão do Monte Alto
    "44571": "3122900",  # MG: DONA EUSÉBIA = Dona Euzébia
    "53031": "3165206",  # MG: SÃO THOMÉ DAS LETRAS = São Tomé das Letras
    "71013": "3550001",  # SP: SÃO LUÍS DO PARAITINGA = São Luiz do Paraitinga
    "91553": "5107800",  # MT: SANTO ANTÔNIO DO LEVERGER = Santo Antônio de Leverger
}


@functools.lru_cache(maxsize=1)
def _localidades():
    mun = baixar_json(URL_MUNICIPIOS, cache="ibge/municipios.json", max_idade_h=IDADE_CACHE_H)
    est = baixar_json(URL_ESTADOS, cache="ibge/estados.json", max_idade_h=IDADE_CACHE_H)
    return mun, est


def estados() -> dict:
    """{uf: nome do estado}"""
    _, est = _localidades()
    return {e["sigla"]: e["nome"] for e in est}


def todas_localidades() -> dict:
    """{ibge: {"ibge","nome","uf"}} com tudo o que o IBGE lista (inclui Brasília e Fernando de Noronha)."""
    mun, _ = _localidades()
    out = {}
    for m in mun:
        cod = str(m["id"])
        out[cod] = {"ibge": cod, "nome": m["nome"], "uf": UF_CODIGO[cod[:2]]}
    return out


def municipios() -> dict:
    """{ibge: {"ibge","nome","uf"}} só com municípios (sem Brasília e Fernando de Noronha)."""
    return {k: v for k, v in todas_localidades().items() if k not in NAO_MUNICIPIOS}


def capital(uf: str) -> dict:
    cod, nome = CAPITAIS[uf]
    loc = todas_localidades().get(cod)
    if not loc or chave_nome(loc["nome"]) != chave_nome(nome):
        raise RuntimeError(f"Capital de {uf} não confere com o IBGE: {cod} {nome} x {loc}")
    return {"ibge": cod, "nome": loc["nome"]}


def fonte_ibge() -> dict:
    return fonte("IBGE", "Códigos e nomes dos municípios (API de localidades)", PAGINA_CODIGOS)


def casar_tse(tse: dict) -> dict:
    """tse = {sg_ue: (uf, nome no TSE)} -> {sg_ue: código IBGE}.
    Levanta erro se algum município do TSE não casar ou se dois casarem com o mesmo IBGE."""
    locs = municipios()
    por_nome = {}
    for cod, m in locs.items():
        por_nome.setdefault((m["uf"], chave_nome(m["nome"])), cod)
    out, faltam = {}, []
    for ue, (uf, nome) in tse.items():
        cod = EXCECOES_TSE.get(ue) or por_nome.get((uf, chave_nome(nome)))
        if not cod or locs.get(cod, {}).get("uf") != uf:
            faltam.append(f"{ue} {nome} ({uf})")
            continue
        out[ue] = cod
    vistos, repetidos = set(), []
    for c in out.values():
        if c in vistos:
            repetidos.append(c)
        vistos.add(c)
    if faltam or repetidos:
        raise RuntimeError(f"TSE x IBGE: sem par: {faltam}; IBGE repetido: {repetidos}")
    return out


def main():
    est = estados()
    locs = todas_localidades()
    mun = municipios()
    log(f"IBGE: {len(est)} estados, {len(locs)} localidades, {len(mun)} municípios (sem Brasília e Fernando de Noronha)")
    for uf in sorted(CAPITAIS):
        capital(uf)
    log("Capitais conferidas com a API do IBGE.")
    porUF = {}
    for m in mun.values():
        porUF[m["uf"]] = porUF.get(m["uf"], 0) + 1
    log("Municípios por UF:", ", ".join(f"{uf} {n}" for uf, n in sorted(porUF.items())))


if __name__ == "__main__":
    main()
