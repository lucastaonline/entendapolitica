"""Testes de interação das votações nominais e dos gastos das Assembleias que entraram na fase 6 ("votações e gastos onde
existirem"): os números da página batem com os arquivos de dados, a lista de votações carrega (formato "lista", dentro do
perfil), "Mostrar mais votações" leva o foco, os links oficiais, o inglês, 320 px sem rolar para os lados e axe-core depois
de rolar e clicar.
Precisa do servidor em 8770 e dos dados gerados por scripts/legislativos.py + scripts/montar.py.
Uso: python testes/interacao_assembleias_votos.py   (outro servidor: EP_BASE=http://127.0.0.1:8771/)"""
import asyncio
import json
import math
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = __import__("os").environ.get("EP_BASE", "http://127.0.0.1:8770/")
RAIZ = Path(__file__).resolve().parents[1]
AXE = RAIZ.parent / "ferramentas" / "node_modules" / "axe-core" / "axe.min.js"
sys.stdout.reconfigure(encoding="utf-8")
RES = []
# Casas com votações no formato "lista" (dentro do perfil) e com gastos novos nesta fase
VOTOS = ["RN", "CE", "SC", "RS", "PI", "PB"]
GASTOS = ["CE", "AM", "RO", "ES", "BA", "PE", "PB", "MA", "AP"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
VOTO_CURTO = {"Sim": "Sim", "Não": "Não", "Abstenção": "Abstenção", "Obstrução": "Obstrução", "NR": "Não votou", "PS": "Presidia"}


def ok(nome, cond, extra=""):
    RES.append(bool(cond))
    print(("✅ " if cond else "❌ ") + nome + (f"  ({extra})" if extra else ""))


def ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def casa(uf):
    return ler(RAIZ / "dados" / "assembleias" / f"{uf}.json")


def perfis(uf):
    """[(membro, perfil)] da lista oficial de hoje."""
    out = []
    for m in casa(uf)["membros"]:
        arq = RAIZ / "dados" / "pessoas" / f"{m['id']}.json"
        if arq.exists():
            out.append((m, ler(arq)))
    return out


def num_pt(v, dec=0):
    s = f"{abs(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + s


def dinheiro_pt(v):
    return "R$ " + num_pt(v, 2)


def dinheiro_curto_pt(v):
    """O mesmo que EP.dinheiroCurto em português (js/comum.js)."""
    a = abs(v)
    if a >= 1e9:
        return "R$ " + num_pt(v / 1e9, 1) + (" bilhão" if a < 2e9 else " bilhões")
    if a >= 1e6:
        return "R$ " + num_pt(v / 1e6, 1) + (" milhão" if a < 2e6 else " milhões")
    if a >= 1e4:
        return "R$ " + num_pt(math.floor(v / 1e3 + 0.5)) + " mil"
    return dinheiro_pt(v)


def limpo(t):
    return re.sub(r"\s+", " ", (t or "").replace("\u00a0", " ")).strip()


async def ir(pg, url):
    try:
        await pg.goto(BASE + url, wait_until="networkidle", timeout=30000)
    except Exception:
        await pg.wait_for_timeout(1500)


async def axe(pg, nome):
    await pg.add_script_tag(path=str(AXE))
    v = await pg.evaluate("""async () => {
      const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
                                          resultTypes: ['violations'] });
      return r.violations.map(v => v.id + ' (' + v.nodes.length + ')');
    }""")
    ok(f"axe sem problemas: {nome}", not v, "; ".join(v)[:300])


def conferir_dados(uf):
    """Dados: cada votação tem o mesmo placar em todos os perfis; os votos dos deputados de hoje cabem no placar; o resumo
    de cada perfil é a contagem da lista; a lista vem da mais nova para a mais antiga."""
    vistos, contas, erros = {}, {}, []
    for m, p in perfis(uf):
        v = p.get("votacoes")
        if not v:
            continue
        lista = v.get("lista") or []
        r = {"Sim": 0, "Não": 0, "Abstenção": 0, "Obstrução": 0, "Outro": 0}
        for x in lista:
            r[x["voto"] if x["voto"] in r else "Outro"] += 1
            pl = x.get("placar")
            if pl:
                if x["id"] in vistos and vistos[x["id"]] != pl:
                    erros.append(f"placar diferente em {x['id']}")
                vistos[x["id"]] = pl
                c = contas.setdefault(x["id"], {})
                c[x["voto"]] = c.get(x["voto"], 0) + 1
        if any(v["resumo"].get(k) != n for k, n in r.items()) or v["resumo"]["total"] != len(lista):
            erros.append(f"resumo de {m['nome']}")
        datas = [x.get("data") or "" for x in lista]
        if datas != sorted(datas, reverse=True):
            erros.append(f"ordem da lista de {m['nome']}")
    for vid, c in contas.items():
        pl = vistos[vid]
        if any(n > pl.get(k if k in pl else "Outro", 0) for k, n in c.items()) or pl["total"] != sum(pl[k] for k in ("Sim", "Não", "Abstenção", "Obstrução", "Outro")):
            erros.append(f"votos de {vid} não cabem no placar {pl}")
    ok(f"{uf}: dados das votações coerentes (placar, resumo, ordem)", not erros and vistos, f"{len(vistos)} votações; " + "; ".join(erros[:3]))
    return len(vistos)


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        ctx = await nav.new_context(viewport={"width": 1280, "height": 860})
        pg = await ctx.new_page()
        erros_js = []
        pg.on("pageerror", lambda e: erros_js.append(f"{pg.url}: {e}"))

        # 1. página do estado: o quadro da Assembleia marca votações e gastos e mostra as notas da Casa
        for uf in sorted(set(VOTOS) | set(GASTOS)):
            c = casa(uf)
            await ir(pg, f"estado.html?uf={uf}&lang=pt")
            await pg.wait_for_timeout(1500)
            itens = pg.locator(".cobertura-casa li")
            textos = [limpo(t) for t in await itens.all_inner_texts()]
            classes = [await itens.nth(k).get_attribute("class") for k in range(await itens.count())]
            marca = {t.split(": ", 1)[-1]: cl for t, cl in zip(textos, classes)}
            v_ok = (marca.get("Como cada um votou") == "tem") == bool(c["cobertura"].get("votacoes"))
            g_ok = (marca.get("Gastos com a verba do mandato") == "tem") == bool(c["cobertura"].get("gastos"))
            n_notas = await pg.locator(".info-casa .notas-casa li").count()
            ok(f"{uf}: quadro da Assembleia com votações/gastos e as {len(c['notas'])} notas", v_ok and g_ok and n_notas == len(c["notas"]),
               f"votações {c['cobertura'].get('votacoes')}, gastos {c['cobertura'].get('gastos')}, {n_notas} notas na página")

        # 2. votações: dados coerentes; o perfil mostra o resumo, a lista, "Mostrar mais" com o foco e o link oficial
        for uf in VOTOS:
            if not casa(uf)["cobertura"].get("votacoes"):
                ok(f"{uf}: Casa com votações", False, "cobertura.votacoes = false")
                continue
            conferir_dados(uf)
            m, pf = max(((m, p) for m, p in perfis(uf) if p.get("votacoes")), key=lambda mp: mp[1]["votacoes"]["resumo"]["total"])
            v = pf["votacoes"]
            await ir(pg, f"pessoa.html?id={m['id']}&lang=pt")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            sec = limpo(await pg.locator("#votacoes").inner_text())
            r = v["resumo"]
            leg_ok = f"Total: {num_pt(r['total'])}" in sec and all(f"{k}: {num_pt(r[k])}" in sec for k in ("Sim", "Não", "Abstenção", "Obstrução", "Outro") if r.get(k))
            ok(f"{uf}: resumo do perfil igual ao arquivo ({m['nome']})", leg_ok and limpo(v["escopo"]) in sec,
               f"{r['total']} votações: {r['Sim']} Sim, {r['Não']} Não")
            itens = pg.locator("#lista-votos > li")
            n0 = await itens.count()
            cont = limpo(await pg.locator("#contagem-votos").inner_text())
            ok(f"{uf}: lista carregada ({min(15, r['total'])} de {r['total']})", n0 == min(15, r["total"]) and
               f"de {num_pt(r['total'])} " in cont, cont)
            x = v["lista"][0]
            primeiro = limpo(await itens.first.inner_text())
            chip = limpo(await itens.first.locator(".voto-chip").inner_text())
            link = await itens.first.locator('a[href^="http"]').first.get_attribute("href") if x.get("url") else None
            ok(f"{uf}: 1ª votação igual ao arquivo (voto, o que foi votado, link oficial)",
               chip.endswith(VOTO_CURTO.get(x["voto"], x["voto"])) and (not x.get("proposta") or x["proposta"] in primeiro)
               and link == x.get("url"), f"{x.get('proposta')} · {x['voto']} · {x.get('data')}")
            if r["total"] > 15:
                await pg.click("#ver-mais-votos")
                await pg.wait_for_timeout(500)
                n1 = await itens.count()
                foco = await pg.evaluate("() => { const a = document.activeElement; return !!a && a.parentElement && a.parentElement.id === 'lista-votos'; }")
                ok(f"{uf}: 'Mostrar mais votações' mostra mais e leva o foco", n1 == min(30, r["total"]) and foco, f"{n0} -> {n1}")
            if uf in ("RN", "CE"):
                await axe(pg, f"perfil {uf} com as votações abertas e 'Mostrar mais'")
            # em inglês: escopo traduzido, nenhum "undefined"
            await ir(pg, f"pessoa.html?id={m['id']}&lang=en")
            await pg.locator("#votacoes").scroll_into_view_if_needed()
            await pg.wait_for_timeout(1500)
            sec_en = limpo(await pg.locator("#votacoes").inner_text())
            ok(f"{uf} em inglês: escopo em inglês e a lista carregada", limpo(v["escopo_en"]) in sec_en and "How " in sec_en
               and "undefined" not in sec_en and await pg.locator("#lista-votos > li .voto-chip").count() > 0)

        # 3. gastos: o nome da verba, o total do ano, o total desde o começo e os tipos batem com o arquivo
        for uf in GASTOS:
            com = [(m, p) for m, p in perfis(uf) if p.get("gastos")]
            ok(f"{uf}: perfis com gastos", com and casa(uf)["cobertura"].get("gastos"), f"{len(com)} de {len(casa(uf)['membros'])}")
            if not com:
                continue
            m, pf = max(com, key=lambda mp: len(mp[1]["gastos"].get("porTipo") or []))
            g = pf["gastos"]
            await ir(pg, f"pessoa.html?id={m['id']}&lang=pt")
            await pg.locator("#gastos").scroll_into_view_if_needed()
            await pg.wait_for_timeout(600)
            sec = limpo(await pg.locator("#gastos").inner_text())
            mi, mf = int(g["meses"][0][5:7]), int(g["meses"][1][5:7])
            rot = (f"gastos em {MESES[mi - 1]} de {g['ano']}" if mi == mf else f"gastos de {MESES[mi - 1]} a {MESES[mf - 1]} de {g['ano']}")
            desde = f"desde {MESES[int(g['desde'][5:7]) - 1]} de {g['desde'][:4]}"
            ok(f"{uf}: total do ano e desde o começo iguais ao arquivo ({m['nome']})",
               dinheiro_curto_pt(g["total"]) + " " + rot in sec and dinheiro_curto_pt(g["mandatoTotal"]) + " " + desde in sec
               and limpo(g["nome"]) in sec, f"{dinheiro_curto_pt(g['total'])} {rot}; {dinheiro_curto_pt(g['mandatoTotal'])} {desde}")
            tipos = pg.locator("#gastos .gasto")
            n = await tipos.count()
            pt = g.get("porTipo") or []
            if pt:
                t0 = limpo(await tipos.first.inner_text())
                ok(f"{uf}: tipos de despesa ({min(8, len(pt))}), o maior com o valor do arquivo", n == min(8, len(pt)) and
                   dinheiro_pt(pt[0]["valor"]) in t0 and limpo(pt[0]["tipo"]) in t0, f"{pt[0]['tipo']}: {dinheiro_pt(pt[0]['valor'])}")
            else:
                ok(f"{uf}: sem tipos de despesa (a Casa não classifica), só os totais", n == 0)
            link = await pg.locator("#gastos a[href^='http']").count() + await pg.locator("#gastos button").count()
            ok(f"{uf}: gastos com o botão da fonte", link > 0)

        # 4. inglês dos gastos e celular de 320 px (perfil com votações e gastos)
        m, pf = next((m, p) for m, p in perfis("CE") if p.get("gastos") and p.get("votacoes"))
        await ir(pg, f"pessoa.html?id={m['id']}&lang=en")
        await pg.locator("#gastos").scroll_into_view_if_needed()
        await pg.wait_for_timeout(600)
        sec = limpo(await pg.locator("#gastos").inner_text())
        ok("CE em inglês: nome da verba em inglês nos gastos", limpo(pf["gastos"]["nome_en"]) in sec and "Office spending" in sec)
        await axe(pg, "perfil CE em inglês com os gastos")
        ctx2 = await nav.new_context(viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True)
        pg2 = await ctx2.new_page()
        for uf in ["RN", "CE", "RS", "AP"]:
            com = [(m, p) for m, p in perfis(uf) if p.get("votacoes") or p.get("gastos")]
            if not com:
                continue
            m, pf = com[0]
            for lang in ("", "&lang=en"):
                try:
                    await pg2.goto(BASE + f"pessoa.html?id={m['id']}{lang or '&lang=pt'}", wait_until="networkidle", timeout=30000)
                except Exception:
                    await pg2.wait_for_timeout(1500)
                for sec_id in ("votacoes", "gastos"):
                    if await pg2.locator(f"#{sec_id}").count():
                        await pg2.locator(f"#{sec_id}").scroll_into_view_if_needed()
                        await pg2.wait_for_timeout(900)
                if await pg2.locator("#ver-mais-votos").count():
                    await pg2.click("#ver-mais-votos")
                    await pg2.wait_for_timeout(400)
                larg = await pg2.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
                ok(f"320 px sem rolar para os lados: {uf} {'en' if lang else 'pt'}", larg[0] <= larg[1] + 1, str(larg))
        await ctx2.close()

        ok("sem erros de JavaScript", not erros_js, "; ".join(erros_js[:3]))
        await nav.close()
    print(f"\n{sum(RES)}/{len(RES)} ok")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
