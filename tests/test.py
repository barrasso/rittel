import asyncio, re
from playwright.async_api import async_playwright
import os, pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
URL=(ROOT/"index.html").as_uri()
errors=[]
def hook(page):
    page.on("console", lambda m: errors.append(m.text) if m.type=="error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
        ctx=await b.new_context(viewport={"width":430,"height":900},device_scale_factor=2,has_touch=True)
        await ctx.grant_permissions(["clipboard-read","clipboard-write"])
        page=await ctx.new_page(); hook(page)
        # today
        await page.goto(URL); await page.wait_for_timeout(300)
        assert await page.is_visible("#helpModal.open"), "help not shown on first visit"
        print("today:", await page.evaluate("__rittel.day"), await page.evaluate("__rittel.answer()"), "bank", await page.evaluate("__rittel.bankSize"))
        await page.click("#helpModal .btn"); 
        await page.reload(); await page.wait_for_timeout(300)
        assert not await page.is_visible("#helpModal.open"), "help shown again"
        # all days load
        seen=set()
        for d in range(1,71):
            await page.goto(f"{URL}?day={d}&reset=1"); seen.add(await page.evaluate("__rittel.answer()"))
        print("distinct answers over 70 days:", len(seen))
        # WIN on day 5
        await page.goto(f"{URL}?day=5&reset=1"); await page.wait_for_timeout(200)
        if await page.is_visible("#helpModal.open"): await page.click("#helpModal .btn")
        ans=await page.evaluate("__rittel.answer()"); print("day5 answer", ans)
        letters=[c for c in dict.fromkeys(ans) if c.isalpha() and c not in "AEIOU"]
        wrong=[c for c in "ZQXJKVBPYGFWMHCDLNRST" if c not in ans]
        await page.keyboard.press(wrong[0]); await page.wait_for_timeout(300)  # 1 strike
        vow=[c for c in "AEIOU" if c in ans]
        if vow: await page.click(f'.key[data-k="{vow[0]}"]'); await page.wait_for_timeout(300)  # 1 strike
        await page.click(f'.key[data-k="{letters[0]}"]'); await page.wait_for_timeout(900)
        st=await page.evaluate("__rittel.state()"); print("mid state", st)
        await page.screenshot(path="screenshot-play.png")
        # persistence
        await page.reload(); await page.wait_for_timeout(400)
        st2=await page.evaluate("__rittel.state()"); assert st2["guessed"]==st["guessed"] and st2["strikes"]==st["strikes"], "persist fail"
        revs=await page.locator("#board .tile.rev").count(); assert revs==ans.count(letters[0]) + (ans.count(vow[0]) if vow else 0), f"revealed {revs}"
        # wrong solve then right solve
        await page.click("#solveBtn"); await page.fill("#solveInput","nope wrong"); await page.press("#solveInput","Enter"); await page.wait_for_timeout(300)
        assert (await page.evaluate("__rittel.state()"))["strikes"]==st["strikes"]+1
        await page.keyboard.press("Enter"); await page.wait_for_timeout(100)
        await page.fill("#solveInput",ans.lower()); await page.click("#solveForm button"); 
        await page.wait_for_selector("#statsModal.open",timeout=6000); await page.wait_for_timeout(1200)
        st=await page.evaluate("__rittel.state()"); assert st["status"]=="won", st
        await page.screenshot(path="screenshot-win.png")
        await page.click("#shareBtn"); await page.wait_for_timeout(200)
        clip=await page.evaluate("navigator.clipboard.readText()"); print("share:\n"+clip)
        assert re.match(r"Rittel #5 🧩 \d/6\n", clip)
        # one game per day: reload, still won, keys disabled
        await page.reload(); await page.wait_for_timeout(500)
        assert (await page.evaluate("__rittel.state()"))["status"]=="won"
        assert await page.is_disabled("#solveBtn")
        # LOSS on day 6
        await page.goto(f"{URL}?day=6"); await page.wait_for_timeout(200)
        ans=await page.evaluate("__rittel.answer()"); print("day6 answer", ans)
        wrong=[c for c in "ZQXJKVBPYGFWMHCDLNRST" if c not in ans]
        for c in wrong[:6]:
            await page.keyboard.press(c); await page.wait_for_timeout(120)
        await page.wait_for_selector("#statsModal.open",timeout=6000); await page.wait_for_timeout(800)
        st=await page.evaluate("__rittel.state()"); assert st["status"]=="lost", st
        txt=await page.inner_text("#statsModal"); print("stats modal:", txt.replace("\n"," | "))
        await page.screenshot(path="/tmp/rittel_loss.png")
        # vowel lock on last life (day 7)
        await page.goto(f"{URL}?day=7"); ans=await page.evaluate("__rittel.answer()")
        wrong=[c for c in "ZQXJKVBPYGFWMHCDLNRST" if c not in ans]
        for c in wrong[:5]: await page.keyboard.press(c)
        await page.keyboard.press("A"); st=await page.evaluate("__rittel.state()")
        assert "A" not in st["guessed"] and st["strikes"]==5 and st["status"]=="playing", st
        # desktop sanity
        dp=await b.new_page(viewport={"width":1280,"height":800}); hook(dp)
        await dp.goto(f"{URL}?day=40"); await dp.wait_for_timeout(300); await dp.screenshot(path="/tmp/rittel_desktop.png")
        await b.close()
    print("console errors:", errors)
    assert not errors
    print("ALL TESTS PASSED")
asyncio.run(main())
