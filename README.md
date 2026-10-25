# Rittel 🃏

**A daily riddle game, like Wheel of Fortune meets Wordle.**

Each day brings one riddle. The answer starts as blank tiles on an old parchment scroll, and you have six lives to reveal it.

![Rittel mid-game](docs/play.png)

## How to play

- Guess a consonant. If it's in the answer, it's free. If not, you lose a life.
- Vowels always cost a life, like buying one on Wheel of Fortune, and you can't buy one on your last life.
- Hit **Solve** (or press Enter) whenever you think you know it. A wrong solve costs a life.
- Your score is the number of lives you used, so lower is better.
- Share your result as an emoji grid, Wordle-style:

```
Rittel #298 🧩 2/6
🟩🟩⬛🟨🟩⭐
```

🟩 letter found · 🟨 vowel bought · ⬛ miss · 🟥 wrong solve · ⭐ solved

## Features

- A new riddle every day from a bank of 70 originals
- Stats, streaks and a lives-used distribution saved in the browser
- Medieval scroll styling with blackletter type and a hand-drawn jester logo
- A candlelit dark mode and a mobile-friendly layout
- A single self-contained HTML file with no network calls, tracking or dependencies

| Win screen | Dark mode |
| --- | --- |
| ![Win screen](docs/win.png) | ![Dark mode on mobile](docs/mobile-dark.png) |

## Development

Open `index.html` in any browser to play locally.

- `?day=N` plays a specific day, with separate dev stats, and `&reset=1` clears them.
- `index.html` is generated, so don't edit it directly. Change game logic in `src/game.html`, styling in `src/style.css` and the logo in `src/jester.svg`, then rebuild with:

```sh
python3 src/build.py
```

- Tests use Playwright: `pip install playwright && playwright install chromium`, then run `python3 tests/test.py`. `python3 tests/shots.py` regenerates the screenshots in `docs/`.

Pushing to the `dev` branch deploys the test build to GitHub Pages.

## Credits

The game code is under the MIT License. The fonts are embedded under the SIL Open Font License (see `src/OFL.txt`): UnifrakturMaguntia, IM Fell English and EB Garamond.
