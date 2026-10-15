"""Gera os ícones e a imagem de compartilhamento a partir de img/icone.svg e testes/og.html.
Precisa do servidor local rodando (python -m http.server 8770) e do Playwright com o Edge.
Uso: python testes/gerar_imagens.py"""
import asyncio
import io
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8770/"
SVG = (RAIZ / "img" / "icone.svg").read_text(encoding="utf-8")


async def icone(pagina, tam: int, fundo: str | None) -> Image.Image:
    estilo = f"background:{fundo}" if fundo else "background:transparent"
    await pagina.set_viewport_size({"width": tam, "height": tam})
    svg = SVG.replace("<svg ", f'<svg width="{tam}" height="{tam}" ', 1)
    if fundo:  # ícone da Apple: quadrado cheio (o iPhone arredonda sozinho)
        svg = svg.replace('rx="14" ', "", 1)
    await pagina.set_content(f'<html><body style="margin:0;{estilo}">{svg}</body></html>')
    png = await pagina.screenshot(omit_background=not fundo, clip={"x": 0, "y": 0, "width": tam, "height": tam})
    return Image.open(io.BytesIO(png)).convert("RGBA")


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch(channel="msedge")
        pagina = await nav.new_page(device_scale_factor=1)
        (await icone(pagina, 512, None)).save(RAIZ / "img" / "icone-512.png", optimize=True)
        (await icone(pagina, 192, None)).save(RAIZ / "img" / "icone-192.png", optimize=True)
        (await icone(pagina, 180, "#1f3a5f")).convert("RGB").save(RAIZ / "img" / "apple-touch-icon.png", optimize=True)
        grande = await icone(pagina, 256, None)
        grande.save(RAIZ / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

        await pagina.set_viewport_size({"width": 1200, "height": 630})
        await pagina.goto(BASE + "testes/og.html", wait_until="networkidle")
        await pagina.wait_for_timeout(800)
        png = await pagina.screenshot(clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        Image.open(io.BytesIO(png)).convert("RGB").save(RAIZ / "img" / "compartilhar.jpg", quality=88, optimize=True)
        await nav.close()
    for f in ("img/icone-512.png", "img/icone-192.png", "img/apple-touch-icon.png", "favicon.ico", "img/compartilhar.jpg"):
        print(f, (RAIZ / f).stat().st_size, "bytes")


asyncio.run(main())
