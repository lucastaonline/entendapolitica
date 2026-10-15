"""Capturas de tela e erros do console (Playwright + Edge instalado no Windows).

Uso: python testes/captura.py index.html "entenda.html#3" --mobile --espera 2500
Salva em testes/capturas/<nome>-desk.png e <nome>-cel.png e lista erros do console.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8770/"
SAIDA = Path(__file__).resolve().parent / "capturas"
SAIDA.mkdir(exist_ok=True)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def nome_arquivo(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-") or "inicio"


async def captura(pagina, url, sufixo, espera, cheia, acoes):
    erros = []
    pagina.on("console", lambda m: erros.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pagina.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    pagina.on("requestfailed", lambda r: erros.append(f"falhou: {r.url}"))
    await pagina.goto(BASE + url, wait_until="networkidle")
    await pagina.wait_for_timeout(espera)
    for a in acoes:
        if a.startswith("click:"):
            await pagina.click(a[6:])
        elif a.startswith("jsclick:"):
            await pagina.eval_on_selector(a[8:], "el => el.click()")
        elif a.startswith("type:"):
            sel, txt = a[5:].split("=", 1)
            await pagina.fill(sel, txt)
        elif a.startswith("wait:"):
            await pagina.wait_for_timeout(int(a[5:]))
        elif a.startswith("press:"):
            await pagina.keyboard.press(a[6:])
        elif a.startswith("scroll:"):
            await pagina.evaluate(f"window.scrollTo(0,{a[7:]})")
    await pagina.wait_for_timeout(600)
    arq = SAIDA / f"{nome_arquivo(url)}-{sufixo}.png"
    await pagina.screenshot(path=str(arq), full_page=cheia)
    larg = await pagina.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    vaza = larg[0] > larg[1] + 1
    return arq, erros, vaza, larg


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--mobile", action="store_true", help="também no celular (390x844)")
    ap.add_argument("--so-mobile", action="store_true")
    ap.add_argument("--espera", type=int, default=2000)
    ap.add_argument("--cheia", action="store_true", help="página inteira")
    ap.add_argument("--acao", action="append", default=[], help="click:SEL | type:SEL=texto | wait:ms | press:Tecla | scroll:y")
    a = ap.parse_args()
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        for url in a.urls:
            modos = []
            if not a.so_mobile:
                modos.append(("desk", dict(viewport={"width": 1280, "height": 860})))
            if a.mobile or a.so_mobile:
                modos.append(("cel", dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)))
            for suf, opts in modos:
                ctx = await nav.new_context(**opts)
                pg = await ctx.new_page()
                arq, erros, vaza, larg = await captura(pg, url, suf, a.espera, a.cheia, a.acao)
                print(f"{url} [{suf}] -> {arq.name}" + (f"  ⚠️ VAZA {larg}" if vaza else ""))
                for e in erros:
                    print("   ", e)
                await ctx.close()
        await nav.close()


asyncio.run(main())
