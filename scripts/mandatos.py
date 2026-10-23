"""Quando começa e quando acaba cada mandato: a regra fica num lugar só, e os coletores perguntam aqui quem está no cargo
numa data. Assim o site troca sozinho de mandato nas datas de posse, sem ninguém precisar mudar ano no código.

Regras (Constituição Federal):
- Presidente e vice: posse em 1º de janeiro do ano seguinte à eleição; a partir dos eleitos em 2026, em 5 de janeiro
  (art. 82, com a Emenda Constitucional 111/2021).
- Governador e vice: 1º de janeiro; a partir dos eleitos em 2026, em 6 de janeiro (art. 28, com a EC 111/2021).
- Deputados federais e senadores: a legislatura começa em 1º de fevereiro do ano seguinte à eleição (art. 57, § 4º, e
  art. 44, parágrafo único: legislatura de 4 anos). A 57ª legislatura começou em 1º/2/2023.
- Deputados estaduais e distritais: posse na data da Constituição de cada estado (quase sempre 1º de fevereiro;
  as exceções ficam em POSSE_ESTADUAL).
- Prefeito, vice e vereadores: 1º de janeiro do ano seguinte à eleição (art. 29, III).
Eleições gerais: 2022, 2026, 2030... Eleições municipais: 2024, 2028, 2032...

Uso: from mandatos import vigente; vigente("governador")  ->  {"eleicao": 2022, "inicio": "2023-01-01", "fim": "2027-01-06", ...}
"""
from __future__ import annotations

import datetime as _dt

CF = {"veiculo": "Planalto", "titulo": "Constituição Federal, arts. 28, 29, 44, 57 e 82",
      "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", "data": "1988-10-05"}
EC111 = {"veiculo": "Planalto", "titulo": "Emenda Constitucional nº 111/2021 (posse do presidente em 5 de janeiro e dos governadores em 6 de janeiro, a partir de 2027)",
         "url": "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm", "data": "2021-09-28"}

GERAIS = "presidente vice-presidente governador vice-governador senador deputado_federal deputado_estadual".split()
MUNICIPAIS = "prefeito vice-prefeito vereador".split()
# deputados estaduais: data de posse ("MM-DD") quando não é 1º de fevereiro (Constituição de cada estado)
POSSE_ESTADUAL: dict[str, str] = {}
SINONIMOS = {"pres": "presidente", "vp": "vice-presidente", "gov": "governador", "vgov": "vice-governador",
             "sen": "senador", "dep": "deputado_federal", "dest": "deputado_estadual", "deputado_distrital": "deputado_estadual",
             "pref": "prefeito", "vpref": "vice-prefeito", "ver": "vereador"}


def _cargo(c: str) -> str:
    c = SINONIMOS.get(c, c)
    if c not in GERAIS and c not in MUNICIPAIS:
        raise ValueError(f"cargo desconhecido: {c}")
    return c


def _hoje() -> str:
    return (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=3)).date().isoformat()  # horário de Brasília


def posse(cargo: str, eleicao: int, uf: str | None = None) -> str:
    """Data (AAAA-MM-DD) em que tomam posse os eleitos na eleição deste ano."""
    c, a = _cargo(cargo), eleicao + 1
    if c in ("presidente", "vice-presidente"):
        return f"{a}-01-05" if eleicao >= 2026 else f"{a}-01-01"
    if c in ("governador", "vice-governador"):
        return f"{a}-01-06" if eleicao >= 2026 else f"{a}-01-01"
    if c in ("senador", "deputado_federal"):
        return f"{a}-02-01"
    if c == "deputado_estadual":
        return f"{a}-{POSSE_ESTADUAL.get((uf or '').upper(), '02-01')}"
    return f"{a}-01-01"


def _ultima_eleicao(c: str, ano: int) -> int:
    base = 2022 if c in GERAIS else 2024
    return ano - ((ano - base) % 4)


def vigente(cargo: str, data: str | None = None, uf: str | None = None) -> dict:
    """Mandato em curso na data (hoje, se não disser): ano da eleição, início, fim (dia da posse dos próximos) e,
    no Congresso, o número da legislatura. Senadores têm mandato de 8 anos, mas a legislatura (e as listas) é de 4."""
    c, d = _cargo(cargo), data or _hoje()
    e = _ultima_eleicao(c, int(d[:4]))
    while posse(c, e, uf) > d:
        e -= 4
    r = {"cargo": c, "eleicao": e, "inicio": posse(c, e, uf), "fim": posse(c, e + 4, uf),
         "fontes": [CF, EC111] if c in ("presidente", "vice-presidente", "governador", "vice-governador") else [CF]}
    if c in ("senador", "deputado_federal"):
        r["legislatura"] = 57 + (int(r["inicio"][:4]) - 2023) // 4
    return r


def antes_da_posse(cargo: str, eleicao: int, data: str | None = None, uf: str | None = None) -> bool:
    """True enquanto os eleitos nesta eleição ainda não tomaram posse (ex.: o selo "Eleito em 2026" só faz sentido até lá)."""
    return (data or _hoje()) < posse(cargo, eleicao, uf)


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def data_br(iso: str) -> str:
    """'2027-01-05' -> '5/1/2027'; o dia 1 vira '1º' ('1º/2/2027'), como se escreve no Brasil."""
    d = int(iso[8:10])
    return f"{'1º' if d == 1 else d}/{int(iso[5:7])}/{iso[:4]}"


def extenso(iso: str) -> tuple[str, str]:
    """'2027-01-05' -> ('5 de janeiro de 2027', 'January 5, 2027')."""
    d, m = int(iso[8:10]), int(iso[5:7])
    return f"{'1º' if d == 1 else d} de {MESES[m - 1]} de {iso[:4]}", f"{MONTHS[m - 1]} {d}, {iso[:4]}"


def mes_ano(iso: str) -> tuple[str, str]:
    """'2023-02-01' -> ('fevereiro de 2023', 'February 2023') (ex.: "votações desde fevereiro de 2023")."""
    m = int(iso[5:7])
    return f"{MESES[m - 1]} de {iso[:4]}", f"{MONTHS[m - 1]} {iso[:4]}"


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for d in ("2026-10-23", "2027-01-04", "2027-01-05", "2027-01-06", "2027-01-31", "2027-02-01", "2028-12-31", "2029-01-01"):
        print(d, {c: vigente(c, d)["eleicao"] for c in ("presidente", "governador", "deputado_federal", "deputado_estadual", "prefeito")},
              "legislatura", vigente("deputado_federal", d)["legislatura"])
