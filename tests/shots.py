"""Regenerate the README screenshots in docs/.  python3 tests/shots.py"""
import asyncio, os, pathlib, shutil, subprocess, sys, json
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(ROOT / "src" / "build.py")], check=True)
URL = (ROOT / "index.html").as_uri()
DOCS = ROOT / "docs"; DOCS.mkdir(exist_ok=True)
CHROME = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
errs = []
HALL = [{"name":"Lady Rowena","score":6840,"solved":9,"streak":6},{"name":"Mark","score":5215,"solved":8,"streak":5},
        {"name":"Sir Galahad","score":3960,"solved":6,"streak":4},{"name":"Wanderer","score":2410,"solved":4,"streak":3},
        {"name":"Brother Cadfael","score":1785,"solved":3,"streak":3},{"name":"Merry","score":905,"solved":2,"streak":2}]

async def page(b, scheme="light", vp=(390, 844)):
    ctx = await b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2, color_scheme=scheme, has_touch=vp[0] < 800)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    return pg

async def fresh(pg, q="day=300"):
    await pg.goto(f"{URL}?{q}&reset=1"); await pg.wait_for_timeout(300)
    await pg.evaluate(f"localStorage.setItem('rittel-dev:lb:gauntlet', JSON.stringify({json.dumps(HALL)}.map((e,i)=>({{...e,at:i}}))))")
    await pg.evaluate("localStorage.setItem('rittel-dev:helpV2','true')")
    await pg.reload(); await pg.wait_for_timeout(300)

async def solve(pg, text):
    await pg.click("#solveBtn"); await pg.wait_for_selector("#kb.scribe"); await pg.fill("#solveInput", text); await pg.press("#solveInput", "Enter")

def cons(a): return [c for c in dict.fromkeys(a) if c.isalpha() and c not in "AEIOU"]
def wrong(a): return [c for c in "ZQXJKVWYFBGHPMCDLNRST" if c not in a]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        # how to play
        pg = await page(b); await pg.goto(f"{URL}?day=300&reset=1"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(DOCS / "help.png"))
        # daily mid-game + win
        pg = await page(b); await fresh(pg, "day=303")
        a = await pg.evaluate("__rittel.answer()")
        for k in cons(a)[:2] + wrong(a)[:1] : await pg.keyboard.press(k); await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(900); await pg.screenshot(path=str(DOCS / "play.png"))
        await solve(pg, a); await pg.wait_for_selector("#statsModal.open", timeout=9000); await pg.wait_for_timeout(900)
        await pg.screenshot(path=str(DOCS / "win.png"))
        # gauntlet: points pop, then run end
        pg = await page(b); await fresh(pg, "day=303")
        await pg.click("#tabGauntlet"); await pg.wait_for_timeout(300); await pg.screenshot(path=str(DOCS / "gauntlet-start.png"))
        await pg.click("#startRun"); await pg.wait_for_timeout(300)
        a = await pg.evaluate("__rittel.answer()"); await pg.keyboard.press(cons(a)[0]); await pg.wait_for_timeout(500)
        await solve(pg, a); await pg.wait_for_timeout(500)
        await pg.click("#solveBtn"); await pg.wait_for_timeout(300)
        a = await pg.evaluate("__rittel.answer()")
        for k in cons(a)[:1] + wrong(a)[:1]: await pg.keyboard.press(k); await pg.wait_for_timeout(300)
        await solve(pg, a); await pg.wait_for_timeout(1150)
        await pg.screenshot(path=str(DOCS / "gauntlet.png"))
        await pg.wait_for_timeout(2500); await pg.click("#solveBtn"); await pg.wait_for_timeout(300)
        for _ in range(4): await solve(pg, "not it"); await pg.wait_for_timeout(250)
        await pg.wait_for_selector("#runModal.open", timeout=9000); await pg.fill("#nameInput", "Rock"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(DOCS / "run-end.png"))
        await pg.click("#nameSubmit"); await pg.wait_for_timeout(300); await pg.click("#runModal .close")
        await pg.click("#hallBtn"); await pg.wait_for_timeout(400); await pg.screenshot(path=str(DOCS / "hall.png"))
        await pg.click("#hallModal .close"); await pg.evaluate("__rittel.grant(3100)")
        await pg.click("#shopBtn"); await pg.wait_for_timeout(400); await pg.screenshot(path=str(DOCS / "shop.png"))
        # skins + dark mode
        for skin, scheme in [("royal", "light"), ("forest", "light"), ("dragon", "light"), ("parchment", "dark")]:
            pg = await page(b, scheme); await fresh(pg, "day=305")
            await pg.evaluate(f"""() => {{ const o=JSON.parse(localStorage.getItem('rittel-dev:owned')||'[]'); o.push('{skin}'); localStorage.setItem('rittel-dev:owned', JSON.stringify(o));
                localStorage.setItem('rittel-dev:prefs', JSON.stringify({{mode:'gauntlet',skin:'{skin}',name:''}})); }}""")
            await pg.reload(); await pg.wait_for_timeout(300); await pg.click("#startRun"); await pg.wait_for_timeout(300)
            a = await pg.evaluate("__rittel.answer()")
            for k in cons(a)[:2] + wrong(a)[:1]: await pg.keyboard.press(k); await pg.wait_for_timeout(250)
            await pg.wait_for_timeout(900)
            await pg.screenshot(path=str(DOCS / ("mobile-dark.png" if scheme == "dark" else f"skin-{skin}.png")))
        # desktop
        pg = await page(b, "light", (1280, 800)); await fresh(pg, "day=306")
        a = await pg.evaluate("__rittel.answer()")
        for k in cons(a)[:2] + wrong(a)[:1]: await pg.keyboard.press(k); await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(900); await pg.screenshot(path=str(DOCS / "desktop.png"))
        await b.close()
    print("errors:", errs)
    print("wrote", sorted(f.name for f in DOCS.glob("*.png")))

asyncio.run(main())
