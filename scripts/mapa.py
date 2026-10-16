"""Mapa do Brasil com o formato real de cada estado, para a página "A política do meu estado".

Fonte: malha territorial do IBGE (API de malhas v3, país dividido por UF, qualidade mínima).
Gera dados/mapa-brasil.json: o contorno de cada estado já desenhado (caminho SVG, numa folha de
LARGURA unidades de largura) e o lugar da sigla. A sigla fica dentro do estado quando cabe; nos
estados pequenos, fica fora, num "selo" ligado ao estado por uma linha (no mar, à direita, ou ao
lado do Distrito Federal).

Uso: python scripts/mapa.py   (o contorno dos estados quase nunca muda: não precisa rodar todo dia)
"""
from __future__ import annotations

import gzip
import heapq
import json
import math

from comum import CACHE, DADOS, baixar, fonte, hoje, log, salvar_json

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")
UF_IBGE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
LARGURA = 1000      # largura da folha do desenho (unidades do SVG)
MARGEM = 14
MAR = 120           # espaço à direita, no mar, para os selos dos estados pequenos
SIGLA = 28          # tamanho da letra da sigla (unidades do SVG)
SELO_ALT = 34       # altura do selo dos estados pequenos
TOLERANCIA = 0.35   # simplificação do contorno (unidades do SVG; invisível no tamanho da tela)


def _dist2_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx or dy:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        ax, ay = ax + t * dx, ay + t * dy
    return (px - ax) ** 2 + (py - ay) ** 2


def simplifica(pts, tol):
    """Douglas-Peucker (sem recursão)."""
    if len(pts) < 5:
        return pts
    manter = [False] * len(pts)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pts) - 1)]
    t2 = tol * tol
    while pilha:
        a, b = pilha.pop()
        dmax, idx = 0.0, None
        for i in range(a + 1, b):
            d = _dist2_seg(*pts[i], *pts[a], *pts[b])
            if d > dmax:
                dmax, idx = d, i
        if idx is not None and dmax > t2:
            manter[idx] = True
            pilha += [(a, idx), (idx, b)]
    return [p for p, m in zip(pts, manter) if m]


def _dist_poligono(x, y, aneis):
    """Distância até a borda: positiva dentro do polígono, negativa fora."""
    dentro, menor = False, math.inf
    for anel in aneis:
        for i in range(len(anel) - 1):
            (ax, ay), (bx, by) = anel[i], anel[i + 1]
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                dentro = not dentro
            menor = min(menor, _dist2_seg(x, y, ax, ay, bx, by))
    return (1 if dentro else -1) * math.sqrt(menor)


def polo(aneis, precisao=0.5):
    """Ponto mais "de dentro" do polígono (algoritmo polylabel): o melhor lugar para a sigla.
    Devolve (x, y, raio do maior círculo que cabe ali)."""
    xs = [p[0] for p in aneis[0]]
    ys = [p[1] for p in aneis[0]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    lado = min(x1 - x0, y1 - y0)
    if lado <= 0:
        return x0, y0, 0.0

    def celula(cx, cy, h):
        d = _dist_poligono(cx, cy, aneis)
        return (-(d + h * math.sqrt(2)), cx, cy, h, d)

    fila = []
    h = lado / 2
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            heapq.heappush(fila, celula(x + h, y + h, h))
            y += lado
        x += lado
    melhor = celula((x0 + x1) / 2, (y0 + y1) / 2, 0)
    while fila:
        c = heapq.heappop(fila)
        if c[4] > melhor[4]:
            melhor = c
        if -c[0] - melhor[4] <= precisao:
            continue
        h = c[3] / 2
        for dx in (-h, h):
            for dy in (-h, h):
                heapq.heappush(fila, celula(c[1] + dx, c[2] + dy, h))
    return melhor[1], melhor[2], melhor[4]


def area(anel):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(anel, anel[1:]))) / 2


def _n(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def caminho(aneis):
    partes = []
    for anel in aneis:
        pts = anel[:-1] if anel[0] == anel[-1] else anel
        partes.append("M" + " ".join(_n(x) + " " + _n(y) for x, y in pts) + "Z")
    return "".join(partes)


def main():
    corpo = baixar(URL, CACHE / "ibge-malha-ufs.json", max_idade_h=24 * 30, headers={"Accept": "application/json"})
    if corpo[:2] == b"\x1f\x8b":  # o IBGE às vezes manda compactado sem avisar no cabeçalho
        corpo = gzip.decompress(corpo)
    geo = json.loads(corpo)
    estados = {}
    for f in geo["features"]:
        uf = UF_IBGE[str(f["properties"]["codarea"])]
        g = f["geometry"]
        estados[uf] = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    assert len(estados) == 27, sorted(estados)

    # projeção simples (equiretangular), com a largura corrigida pela latitude do meio do país
    lons = [c[0] for p in estados.values() for pol in p for anel in pol for c in anel]
    lats = [c[1] for p in estados.values() for pol in p for anel in pol for c in anel]
    k = math.cos(math.radians((min(lats) + max(lats)) / 2))
    esc = (LARGURA - 2 * MARGEM - MAR) / ((max(lons) - min(lons)) * k)
    lon0, lat0 = min(lons), max(lats)

    def proj(c):
        return (round(MARGEM + (c[0] - lon0) * k * esc, 2), round(MARGEM + (lat0 - c[1]) * esc, 2))

    altura = math.ceil(2 * MARGEM + (max(lats) - min(lats)) * esc)
    saida, pontos = {}, 0
    for uf, poligonos in estados.items():
        pols = []
        for pol in poligonos:
            aneis = [simplifica([proj(c) for c in anel], TOLERANCIA) for anel in pol]
            aneis = [a for a in aneis if len(a) >= 4]
            if aneis:
                pols.append(aneis)
        maior = max(pols, key=lambda p: area(p[0]))
        # ilhotas muito pequenas somem no tamanho da tela: ficam de fora
        pols = [p for p in pols if p is maior or area(p[0]) > 0.004 * area(maior[0])]
        x, y, raio = polo(maior)
        pontos += sum(len(a) for p in pols for a in p)
        saida[uf] = {"d": "".join(caminho(p) for p in pols), "x": round(x, 1), "y": round(y, 1), "raio": round(raio, 1)}

    # estados onde a sigla não cabe dentro: selo fora do estado, ligado por uma linha
    cabe = SIGLA * 0.78
    pequenos = sorted((u for u, v in saida.items() if v["raio"] < cabe), key=lambda u: saida[u]["y"])
    for u in pequenos:
        v = saida[u]
        if u == "DF":  # no meio do país: selo um pouco acima e à direita
            v["selo"] = {"x": round(v["x"] + 52, 1), "y": round(v["y"] - 40, 1)}
    no_mar = [u for u in pequenos if u != "DF"]
    if no_mar:
        # coluna no mar, à direita do ponto mais a leste do país, sem um selo encostar no outro
        x_mar = LARGURA - MARGEM - MAR / 2 + 6
        ultimo = -math.inf
        for u in no_mar:
            y = max(saida[u]["y"], ultimo + SELO_ALT + 8)
            saida[u]["selo"] = {"x": round(x_mar, 1), "y": round(y, 1)}
            ultimo = y
    for v in saida.values():
        del v["raio"]

    dados = {
        "fonte": fonte("IBGE", "Malha territorial do Brasil por estado (API de malhas do IBGE, versão 3, qualidade mínima)", URL),
        "largura": LARGURA, "altura": altura, "sigla": SIGLA, "seloAltura": SELO_ALT,
        "ufs": dict(sorted(saida.items())),
        "atualizado": hoje(),
    }
    mudou = salvar_json(DADOS / "mapa-brasil.json", dados)
    log(f"mapa: 27 estados, {pontos} pontos, folha {LARGURA}x{altura}, selos fora: {', '.join(pequenos)}"
        f"{'' if mudou else ' (sem mudança)'}")


if __name__ == "__main__":
    main()
