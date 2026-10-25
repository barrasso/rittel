"""Rittel end-to-end tests (Playwright + local Chrome/Chromium).

Run:  python3 tests/test.py      (rebuilds index.html first)
Checks: riddle bank, scoring maths, daily win/loss, Gauntlet runs (life carry-over, heals, yield, run end,
Hall of Fame), seen-riddle pool, shop + skins, ad slot, v1 migration, layout, no console errors, no network.
"""
import asyncio, collections, math, os, pathlib, re, shutil, subprocess, sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(ROOT / "src" / "build.py")], check=True)
URL = (ROOT / "index.html").as_uri()
CHROME = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")

errors, network, passed = [], [], []
def ok(name): passed.append(name); print("  ✓", name)

# ---------- riddle bank (static) ----------
def check_bank():
    rows = []
    for line in (ROOT / "src" / "riddles.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            t, a, q = line.split("|"); rows.append((int(t), a, q))
    assert len(rows) >= 250, len(rows)
    assert all(re.fullmatch(r"[A-Z]+( [A-Z]+)*", a) for _, a, _ in rows), "charset"
    keys = [a.replace(" ", "") for _, a, _ in rows]
    assert len(set(keys)) == len(keys), [k for k, c in collections.Counter(keys).items() if c > 1]
    tiers = collections.Counter(t for t, _, _ in rows)
    assert set(tiers) == {1, 2, 3} and min(tiers.values()) >= 60, tiers
    for t, a, q in rows:  # no answer word longer than 3 letters may appear verbatim in its own riddle
        for w in a.split():
            assert not (len(w) > 3 and re.search(r"\b" + w + r"\b", q.upper())), (a, q)
    ok(f"riddle bank: {len(rows)} riddles, tiers {dict(sorted(tiers.items()))}, unique, A-Z only, no self-leaks")
    return rows

def expected_points(tier, hidden_frac, lives_left, streak):
    base = {1: 100, 2: 200, 3: 300}[tier]
    mult = min(3, 1 + 0.25 * max(0, streak - 1))
    raw = (base + math.floor(base * 2 * hidden_frac / 5 + 0.5) * 5 + 10 * lives_left) * mult
    return math.floor(raw / 5 + 0.5) * 5

def hook(page):
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: network.append(r.url) if not r.url.startswith(("file:", "data:", "about:", "blob:")) else None)

async def close_help(pg):
    if await pg.is_visible("#helpModal.open"): await pg.click("#helpModal .btn.seal")

async def solve(pg, text):
    await pg.click("#solveBtn"); await pg.wait_for_selector("#solveModal.open")
    await pg.fill("#solveInput", text); await pg.press("#solveInput", "Enter"); await pg.wait_for_timeout(250)

async def hidden_frac(pg):
    return await pg.evaluate("""() => { const a=__rittel.answer().replace(/ /g,''), g=__rittel.round().guessed;
        return [...a].filter(c=>!g.includes(c)).length / a.length; }""")

def consonants(ans): return [c for c in dict.fromkeys(ans) if c.isalpha() and c not in "AEIOU"]
def wrong_consonants(ans): return [c for c in "ZQXJKVWYFBGHPMCDLNRST" if c not in ans]

async def main():
    rows = check_bank()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True)
        await ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        pg = await ctx.new_page(); hook(pg)

        # ---- first visit / help ----
        await pg.goto(f"{URL}?day=300&reset=1"); await pg.wait_for_timeout(300)
        assert await pg.is_visible("#helpModal.open"), "help on first visit"
        await close_help(pg); await pg.reload(); await pg.wait_for_timeout(300)
        assert not await pg.is_visible("#helpModal.open"), "help shown twice"
        assert await pg.evaluate("__rittel.bankSize") == len(rows)
        ok("how-to-play shown once; page bank matches riddles.txt")

        # ---- scoring maths ----
        for tier, h, lives, streak in [(1, 1, 6, 1), (3, .5, 2, 3), (2, 0, 1, 1), (2, .25, 9, 20), (3, 1, 9, 9)]:
            got = await pg.evaluate(f"__rittel.scoreSolve({{tier:{tier},hiddenFrac:{h},livesLeft:{lives},streak:{streak}}}).total")
            assert got == expected_points(tier, h, lives, streak), (tier, h, lives, streak, got)
        assert await pg.evaluate("__rittel.scoreSolve({tier:1,hiddenFrac:0,livesLeft:0,streak:50}).mult") == 3
        ok("scoring: base by tier + hidden-tile bonus + lives bonus, streak multiplier capped at ×3")

        # ---- daily: win ----
        ans = await pg.evaluate("__rittel.answer()"); tier = await pg.evaluate("__rittel.tier()")
        assert ans == await pg.evaluate("__rittel.dailyRiddleId(300)")
        await pg.keyboard.press(consonants(ans)[0]); await pg.wait_for_timeout(200)
        await pg.keyboard.press(wrong_consonants(ans)[0]); await pg.wait_for_timeout(200)
        assert await pg.evaluate("__rittel.lives()") == 5
        await pg.reload(); await pg.wait_for_timeout(300)
        assert await pg.evaluate("__rittel.lives()") == 5 and len(await pg.evaluate("__rittel.round().guessed")) == 2, "daily persisted"
        hf = await hidden_frac(pg)
        await solve(pg, ans.lower())
        await pg.wait_for_selector("#statsModal.open", timeout=8000)
        r = await pg.evaluate("__rittel.round()")
        assert r["status"] == "won" and r["points"] == expected_points(tier, hf, 5, 1), (r, hf)
        assert (await pg.evaluate("__rittel.wallet()"))["gold"] == r["points"]
        await pg.click("#shareBtn"); await pg.wait_for_timeout(150)
        clip = await pg.evaluate("navigator.clipboard.readText()")
        assert re.fullmatch(r"Rittel #300 🧩 1/6\n🟩⬛⭐\n⚜ [\d,]+ points", clip), clip
        await pg.reload(); await pg.wait_for_timeout(500)
        assert (await pg.evaluate("__rittel.round()"))["status"] == "won" and "Gauntlet" in await pg.inner_text("#solveBtn")
        ok(f"daily win ({ans}, {r['points']} pts), state survives refresh, share text, one game per day")

        # ---- daily: loss + wrong solve costs 2 + vowel lock ----
        await pg.goto(f"{URL}?day=301"); await pg.wait_for_timeout(300); await close_help(pg)
        ans = await pg.evaluate("__rittel.answer()")
        await solve(pg, "definitely wrong"); assert await pg.evaluate("__rittel.lives()") == 4, "wrong solve = -2"
        w = wrong_consonants(ans)
        for c in w[:3]: await pg.keyboard.press(c); await pg.wait_for_timeout(120)
        assert await pg.evaluate("__rittel.lives()") == 1
        await pg.keyboard.press("A"); await pg.wait_for_timeout(100)
        assert "A" not in (await pg.evaluate("__rittel.round()"))["guessed"], "vowel blocked on last life"
        await pg.keyboard.press(w[3]); await pg.wait_for_selector("#statsModal.open", timeout=8000)
        assert (await pg.evaluate("__rittel.round()"))["status"] == "lost"
        st = await pg.evaluate("JSON.parse(localStorage.getItem('rittel-dev:stats'))")
        assert st["played"] == 2 and st["wins"] == 1 and st["losses"] == 1 and st["streak"] == 0, st
        ok("daily loss: wrong solve costs 2, misses cost 1, no vowel on last life, stats updated")

        # ---- gauntlet run ----
        await pg.click("#statsModal .close"); await pg.click("#tabGauntlet"); await pg.wait_for_timeout(200)
        assert await pg.is_visible("#startPanel") and not await pg.is_visible("#kb"), "start panel"
        daily_id = await pg.evaluate("__rittel.dailyRiddleId(301)")
        await pg.click("#startRun"); await pg.wait_for_timeout(200)
        run = await pg.evaluate("__rittel.run()"); assert run["lives"] == 6 and run["n"] == 1
        seen_ids = []
        # riddle 1: instant flawless solve → +2 lives
        a1 = await pg.evaluate("__rittel.answer()"); t1 = await pg.evaluate("__rittel.tier()"); seen_ids.append(a1)
        await solve(pg, a1); await pg.wait_for_timeout(600)
        run = await pg.evaluate("__rittel.run()")
        assert run["lives"] == 8 and run["streak"] == 1 and run["score"] == expected_points(t1, 1, 6, 1), run
        assert "Next" in await pg.inner_text("#solveBtn")
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(300)
        # riddle 2: one miss, refresh mid-riddle, then solve → +1 life, streak ×1.25
        a2 = await pg.evaluate("__rittel.answer()"); t2 = await pg.evaluate("__rittel.tier()"); seen_ids.append(a2)
        await pg.keyboard.press(wrong_consonants(a2)[0]); await pg.wait_for_timeout(200)
        await pg.reload(); await pg.wait_for_timeout(400)
        assert await pg.evaluate("__rittel.answer()") == a2 and await pg.evaluate("__rittel.lives()") == 7, "run persisted"
        before = (await pg.evaluate("__rittel.run()"))["score"]
        await solve(pg, a2); await pg.wait_for_timeout(600)
        run = await pg.evaluate("__rittel.run()")
        assert run["lives"] == 8 and run["streak"] == 2 and run["score"] - before == expected_points(t2, 1, 7, 2), run
        await pg.click("#solveBtn"); await pg.wait_for_timeout(300)
        # riddle 3: yield → −1 life, streak reset
        a3 = await pg.evaluate("__rittel.answer()"); seen_ids.append(a3)
        await pg.click("#yieldBtn"); await pg.wait_for_timeout(300)
        run = await pg.evaluate("__rittel.run()"); assert run["lives"] == 7 and run["streak"] == 0 and run["round"]["status"] == "yielded"
        await pg.click("#solveBtn"); await pg.wait_for_timeout(300)
        # riddle 4: four wrong solves (7→5→3→1→0) ends the run
        a4 = await pg.evaluate("__rittel.answer()"); seen_ids.append(a4)
        for _ in range(4): await solve(pg, "zzzz wrong")
        await pg.wait_for_selector("#runModal.open", timeout=8000)
        run = await pg.evaluate("__rittel.run()"); assert run["over"] and run["lives"] == 0 and run["solved"] == 2
        assert len(set(seen_ids)) == 4 and daily_id not in seen_ids, seen_ids
        seen = await pg.evaluate("JSON.parse(localStorage.getItem('rittel-dev:seenRiddles'))")
        assert set(seen_ids) <= set(seen)
        await pg.fill("#nameInput", "Mark"); await pg.click("#nameSubmit"); await pg.wait_for_timeout(300)
        lb = await pg.evaluate("JSON.parse(localStorage.getItem('rittel-dev:lb:gauntlet'))")
        assert lb[0]["name"] == "Mark" and lb[0]["score"] == run["score"] and lb[0]["solved"] == 2, lb
        assert "rank 1" in await pg.inner_text("#runRank")
        await pg.click("#runModal .close"); await pg.click("#hallBtn"); await pg.wait_for_selector("#hallModal.open")
        assert "Mark" in await pg.inner_text("#hallBody")
        await pg.click('.subtab[data-hall="daily"]'); assert "#300" in await pg.inner_text("#hallBody")
        await pg.click('.subtab[data-hall="records"]'); assert "Best run" in await pg.inner_text("#hallBody")
        await pg.click("#hallModal .close")
        ok(f"gauntlet: 4 riddles, lives carried (6→8→7→8→7→0), heals, yield, run score {run['score']} saved to Hall of Fame")

        # ---- seen pool: exhaustion + daily exclusion ----
        all_ids = await pg.evaluate("__rittel.bank.map(r=>r.id)")
        last = next(i for i in all_ids if i != daily_id)
        await pg.evaluate(f"localStorage.setItem('rittel-dev:seenRiddles', JSON.stringify({[i for i in all_ids if i != last]!r}))")
        await pg.reload(); await pg.wait_for_timeout(300)
        if await pg.is_visible("#runModal.open"): await pg.click("#runAgain")
        else: await pg.click("#solveBtn")
        await pg.wait_for_timeout(300)
        assert await pg.evaluate("__rittel.answer()") == last, "only unseen riddle picked"
        await pg.click("#yieldBtn"); await pg.wait_for_timeout(200); await pg.click("#solveBtn"); await pg.wait_for_timeout(200)
        nxt = await pg.evaluate("__rittel.answer()")
        assert nxt != daily_id and len(await pg.evaluate("JSON.parse(localStorage.getItem('rittel-dev:seenRiddles'))")) == 1, "pool reset after exhaustion"
        ok("no repeats until the bank is exhausted, then the pool resets; today's daily never appears in the Gauntlet")

        # ---- shop + skins + ads ----
        assert await pg.evaluate("document.getElementById('adSlot').hidden && document.getElementById('adSlot').offsetHeight===0")
        assert not await pg.evaluate("__rittel.config.ADS_ENABLED")
        assert await pg.evaluate("document.querySelectorAll('script[src],iframe,ins').length") == 0
        gold = (await pg.evaluate("__rittel.wallet()"))["gold"]
        if gold < 2500: await pg.evaluate(f"__rittel.grant({2500 - gold})")
        gold = (await pg.evaluate("__rittel.wallet()"))["gold"]
        await pg.click("#purse"); await pg.wait_for_selector("#shopModal.open")
        await pg.click('.item[data-item="royal"] .btn'); await pg.wait_for_timeout(200)
        assert await pg.evaluate("document.documentElement.dataset.skin") == "royal"
        assert (await pg.evaluate("__rittel.wallet()"))["gold"] == gold - 2500 and "royal" in await pg.evaluate("__rittel.owned()")
        bg = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--modalBg').trim()")
        assert bg == "#2a1442", bg
        await pg.click('.item[data-item="dragon"] .btn'); await pg.wait_for_timeout(100)
        assert "dragon" not in await pg.evaluate("__rittel.owned()"), "can't buy without gold"
        await pg.reload(); await pg.wait_for_timeout(300)
        assert await pg.evaluate("document.documentElement.dataset.skin") == "royal", "skin persisted"
        await pg.evaluate("__rittel.grant(6000)"); await pg.click("#shopBtn"); await pg.wait_for_selector("#shopModal.open")
        await pg.click('.item[data-item="noads"] .btn'); await pg.wait_for_timeout(150)
        assert "noads" in await pg.evaluate("__rittel.owned()") and await pg.evaluate("document.getElementById('adSlot').hidden")
        await pg.click('.item[data-item="parchment"] .btn'); await pg.wait_for_timeout(100)
        assert await pg.evaluate("document.documentElement.dataset.skin") == "parchment"
        await pg.click("#shopModal .close")
        ok("armory: buy Royal Court (−2500 gold), skin applied + persisted, insufficient gold refused, Banish the Ads owned, ad slot hidden, no ad scripts")

        # ---- layout: longest answer fits at 390px ----
        long_day = await pg.evaluate("""() => { let best=[0,1]; for (let d=1; d<=900; d++){ const l=__rittel.dailyRiddleId(d).length; if(l>best[0]) best=[l,d]; } return best[1]; }""")
        await pg.goto(f"{URL}?day={long_day}"); await pg.wait_for_timeout(400); await close_help(pg)
        await pg.click("#tabDaily"); await pg.wait_for_timeout(300)
        assert await pg.evaluate("__rittel.mode()") == "daily"
        assert len(await pg.evaluate("__rittel.answer()")) >= 20, "expected a long multi-word answer"
        sw = await pg.evaluate("[document.documentElement.scrollWidth, Math.max(...[...document.querySelectorAll('#board .tile')].map(t=>t.getBoundingClientRect().right))]")
        assert sw[0] <= 390 and sw[1] <= 390, sw
        ok(f"layout: longest daily answer ({await pg.evaluate('__rittel.answer()')}) fits a 390px screen")

        # ---- v1 → v2 migration ----
        m = await ctx.new_page(); hook(m)
        await m.goto(f"{URL}?dev=1"); await m.evaluate("localStorage.clear()")
        today = await m.evaluate("__rittel.day")
        await m.evaluate(f"""() => {{ localStorage.setItem('rittel-dev:stats', JSON.stringify({{played:9,wins:7,streak:3,maxStreak:5,lastWon:{today},dist:[1,2,2,1,1,0],losses:2}}));
            localStorage.setItem('rittel-dev:state', JSON.stringify({{day:{today},guessed:['T'],strikes:2,history:['H'],status:'won',recorded:true}}));
            localStorage.setItem('rittel-dev:seen', 'true'); }}""")
        await m.reload(); await m.wait_for_timeout(400)
        st = await m.evaluate("JSON.parse(localStorage.getItem('rittel-dev:stats'))")
        assert st["played"] == 9 and st["wins"] == 7 and st["maxStreak"] == 5 and st["streak"] == 3, st
        assert (await m.evaluate("__rittel.wallet()"))["gold"] == 7 * 150
        assert await m.evaluate("localStorage.getItem('rittel-dev:state')") is None
        assert await m.is_visible("#helpModal.open"), "v2 rules shown to returning players"
        await close_help(m); a = await m.evaluate("__rittel.answer()"); await solve(m, a)
        await m.wait_for_selector("#statsModal.open", timeout=8000)
        st = await m.evaluate("JSON.parse(localStorage.getItem('rittel-dev:stats'))")
        assert st["played"] == 9 and st["wins"] == 7, "v1-finished day not double counted"
        ok("migration: v1 stats/streaks kept, veteran gold granted, today's finished v1 game not double-counted")
        await m.close()

        # ---- production URL (no dev hook) + desktop ----
        d = await b.new_page(viewport={"width": 1280, "height": 800}); hook(d)
        await d.goto(URL); await d.wait_for_timeout(500)
        assert await d.evaluate("typeof window.__rittel") == "undefined", "test hook hidden in production"
        await close_help(d); await d.click("#tabGauntlet"); await d.click("#startRun"); await d.wait_for_timeout(200)
        await d.keyboard.press("T"); await d.wait_for_timeout(200)
        ok("production build loads on desktop (no dev hook exposed)")
        await b.close()

    assert not errors, errors
    ok("no console errors")
    assert not network, network
    ok("no network requests")
    print(f"\nALL {len(passed)} CHECKS PASSED")

asyncio.run(main())
