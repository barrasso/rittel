import asyncio
from playwright.async_api import async_playwright
import os, pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
URL=(ROOT/"index.html").as_uri()
errs=[]
async def setup(b,scheme,vp):
    ctx=await b.new_context(viewport=vp,device_scale_factor=2,color_scheme=scheme,has_touch=True)
    pg=await ctx.new_page(); pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m:errs.append(m.text) if m.type=="error" else None)
    return pg
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
        pg=await setup(b,"light",{"width":430,"height":900})
        await pg.goto(f"{URL}?day=25&reset=1"); await pg.wait_for_timeout(500)
        await pg.screenshot(path="_work/help.png")
        await pg.click("#helpModal .btn")
        for k in ["N","S","Q","E","L"]: await pg.keyboard.press(k); await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(900); await pg.screenshot(path="screenshot-play.png")
        await pg.click("#solveBtn"); await pg.fill("#solveInput","tennis"); await pg.wait_for_timeout(300); await pg.screenshot(path="_work/solve.png")
        await pg.fill("#solveInput","tennis ball"); await pg.press("#solveInput","Enter")
        await pg.wait_for_selector("#statsModal.open"); await pg.wait_for_timeout(1300)
        await pg.screenshot(path="screenshot-win.png")
        m=await setup(b,"dark",{"width":390,"height":844})
        await m.goto(f"{URL}?day=12&reset=1"); await m.wait_for_timeout(300); await m.click("#helpModal .btn")
        ans=await m.evaluate("__rittel.answer()")
        cons=[c for c in dict.fromkeys(ans) if c.isalpha() and c not in "AEIOU"][:2]
        wrong=[c for c in "ZQXJKVBPYGFWMHCDLNRST" if c not in ans][:2]
        vow=[c for c in "AEIOU" if c in ans][:1]
        for k in cons+wrong+vow: await m.keyboard.press(k); await m.wait_for_timeout(250)
        await m.wait_for_timeout(900); await m.screenshot(path="screenshot-mobile.png")
        await m.click("#solveBtn"); await m.fill("#solveInput",ans); await m.press("#solveInput","Enter")
        await m.wait_for_selector("#statsModal.open"); await m.wait_for_timeout(1300); await m.screenshot(path="_work/win-dark.png")
        d=await setup(b,"light",{"width":1280,"height":800}); await d.goto(f"{URL}?day=40&reset=1"); await d.click("#helpModal .btn")
        for k in "TRS": await d.keyboard.press(k)
        await d.wait_for_timeout(900); await d.screenshot(path="_work/desktop.png")
        await b.close()
    print("errors",errs, "mobile answer", ans)
asyncio.run(main())
