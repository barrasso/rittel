"""Build the single self-contained, offline index.html from src/.

  src/game.html   page template with {{FAVICON}} {{FONTS}} {{CSS}} {{LOGO}} {{RIDDLES}} {{GAME}} slots
  src/skins.css   skin variables (Parchment light/dark, Royal Court, Forest Ranger, Dragon's Hoard)
  src/style.css   base styles
  src/game.js     game logic
  src/riddles.txt riddle bank: tier|ANSWER|riddle   (validated here; the build fails on bad data)
  src/jester.svg  logo + favicon
  src/fonts/      OFL font subsets (woff2), embedded as base64
"""
import base64, collections, json, os, re, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
rd = lambda *p: open(os.path.join(SRC, *p), encoding="utf-8").read()
b64 = lambda f: base64.b64encode(open(os.path.join(SRC, "fonts", f), "rb").read()).decode()

def load_riddles():
    rows, errors = [], []
    for n, line in enumerate(rd("riddles.txt").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 3:
            errors.append(f"line {n}: expected tier|ANSWER|riddle"); continue
        tier, ans, q = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if tier not in ("1", "2", "3"): errors.append(f"line {n}: bad tier {tier!r}")
        if not re.fullmatch(r"[A-Z]+( [A-Z]+)*", ans): errors.append(f"line {n}: answer must be A-Z and single spaces: {ans!r}")
        if len(q) < 12: errors.append(f"line {n}: riddle too short")
        rows.append([int(tier) if tier.isdigit() else 0, ans, q])
    dup = [a for a, c in collections.Counter(r[1].replace(" ", "") for r in rows).items() if c > 1]
    if dup: errors.append("duplicate answers: " + ", ".join(dup))
    if len(rows) < 250: errors.append(f"only {len(rows)} riddles (need >= 250)")
    if errors:
        sys.exit("riddles.txt invalid:\n  " + "\n  ".join(errors))
    return rows

def build():
    riddles = load_riddles()
    fonts = ('<style id="fonts">/* Embedded subsets: UnifrakturMaguntia (c) j. \'mach\' wust, IM FELL English (c) Igino Marini, '
             'EB Garamond digits (c) Georg Duffner & Octavio Pardo. SIL Open Font License 1.1 (see src/OFL.txt) */\n'
             f'@font-face{{font-family:"Rittel Fraktur";src:url(data:font/woff2;base64,{b64("frak.woff2")}) format("woff2");font-display:swap}}\n'
             f'@font-face{{font-family:"Rittel Fell";src:url(data:font/woff2;base64,{b64("fell-r.woff2")}) format("woff2");font-display:swap}}\n'
             f'@font-face{{font-family:"Rittel Fell";font-style:italic;src:url(data:font/woff2;base64,{b64("fell-i.woff2")}) format("woff2");font-display:swap}}\n'
             f'@font-face{{font-family:"Rittel Fell";src:url(data:font/woff2;base64,{b64("digits.woff2")}) format("woff2");unicode-range:U+0023,U+0025,U+0030-0039;font-display:swap}}\n'
             f'@font-face{{font-family:"Rittel Fell";font-style:italic;src:url(data:font/woff2;base64,{b64("digits.woff2")}) format("woff2");unicode-range:U+0023,U+0025,U+0030-0039;font-display:swap}}\n</style>')
    svg = rd("jester.svg").strip()
    fav = "data:image/svg+xml," + urllib.parse.quote(svg.replace("\n", ""), safe=" =:/'\".,-").replace('"', "'")
    logo = svg.replace('<svg xmlns="http://www.w3.org/2000/svg"', '<svg class="logo" aria-hidden="true"')
    out = rd("game.html")
    parts = {
        "{{FAVICON}}": fav, "{{FONTS}}": fonts, "{{CSS}}": rd("skins.css") + rd("style.css"), "{{LOGO}}": logo,
        "{{RIDDLES}}": "const RIDDLES = " + json.dumps(riddles, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";",
        "{{GAME}}": rd("game.js").replace("</script", "<\\/script"),
    }
    for k, v in parts.items():
        if k not in out: sys.exit(f"template slot {k} missing")
        out = out.replace(k, v)
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(out)
    tiers = collections.Counter(r[0] for r in riddles)
    print(f"index.html: {len(out.encode()):,} bytes · riddles {len(riddles)} (Squire {tiers[1]}, Knight {tiers[2]}, Sage {tiers[3]})")

if __name__ == "__main__":
    build()
