import re,base64,urllib.parse
import os; ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); W=os.path.join(ROOT,'src')+'/'; F=os.path.join(ROOT,'src','fonts')+'/'
s=open(W+'game.html').read()
b64=lambda f:base64.b64encode(open(F+f,'rb').read()).decode()
fonts=('<style id="fonts">/* Embedded subsets: UnifrakturMaguntia (c) j. \'mach\' wust, IM FELL English (c) Igino Marini, EB Garamond digits (c) Georg Duffner & Octavio Pardo — both SIL Open Font License 1.1 */\n'
 f'@font-face{{font-family:"Rittel Fraktur";src:url(data:font/woff2;base64,{b64("frak.woff2")}) format("woff2");font-display:swap}}\n'
 f'@font-face{{font-family:"Rittel Fell";src:url(data:font/woff2;base64,{b64("fell-r.woff2")}) format("woff2");font-display:swap}}\n'
 f'@font-face{{font-family:"Rittel Fell";font-style:italic;src:url(data:font/woff2;base64,{b64("fell-i.woff2")}) format("woff2");font-display:swap}}\n'
 f'@font-face{{font-family:"Rittel Fell";src:url(data:font/woff2;base64,{b64("digits.woff2")}) format("woff2");unicode-range:U+0023,U+0025,U+0030-0039;font-display:swap}}\n'
 f'@font-face{{font-family:"Rittel Fell";font-style:italic;src:url(data:font/woff2;base64,{b64("digits.woff2")}) format("woff2");unicode-range:U+0023,U+0025,U+0030-0039;font-display:swap}}\n</style>\n')
css=open(W+'style.css').read()
s=re.sub(r'<style>.*?</style>\n', lambda m: fonts+'<style>\n'+css+'</style>\n', s, flags=re.S)
svg=open(W+'jester.svg').read().strip()
fav=urllib.parse.quote(svg.replace('\n',''),safe=" =:/'\".,-")
s=re.sub(r'<link rel="icon".*\n', '<link rel="icon" href="data:image/svg+xml,'+fav.replace('"',"'")+'">\n', s)
s=s.replace('<meta name="theme-color" content="#101116">','<meta name="theme-color" content="#e8d4a6" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#20150d" media="(prefers-color-scheme: dark)">')
logo=svg.replace('<svg xmlns="http://www.w3.org/2000/svg"','<svg class="logo" aria-hidden="true"')
s=s.replace('<h1><span class="dot"></span>Rittel</h1>','<div class="brand">'+logo+'<h1><span>R</span>ittel</h1></div>')
# help copy
old=s[s.index('<h2 id="helpTitle">'):s.index('<div class="ex" id="exTiles">')]
new='''<h2 id="helpTitle">Hear ye, hear ye</h2>
    <p>Each day the court jester poses one riddle. Reveal its answer letter by letter, then solve it before your lives run out.</p>
    <ul>
      <li>You have <b>6 lives</b>.</li>
      <li><b>Consonants</b> are free if they're in the answer. A wrong consonant costs <b>1 life</b>.</li>
      <li><b>Vowels</b> (A E I O U) always cost <b>1 life</b>, right or wrong. You buy them. You can't buy a vowel with your last life.</li>
      <li>Press <b>Solve</b> at any time to guess the whole answer. A wrong solve costs <b>1 life</b>.</li>
      <li>Fill every tile or solve it to win. Your score is the number of lives you used, so <b>lower is better</b>.</li>
    </ul>
    '''
s=s.replace(old,new)
s=s.replace('Green = consonant hit · Gold = bought vowel. Your physical keyboard works too: type letters, press Enter to solve.','Green = consonant found · Gold = vowel bought. Your keyboard works too: type letters, press Enter to solve.')
s=s.replace('<button class="btn" data-close>Let\'s play</button>','<button class="btn seal" data-close>Begin</button>')
s=s.replace('<button class="btn" type="submit">Submit guess</button>','<button class="btn seal" type="submit">Submit answer</button>')
s=s.replace('<button class="btn" id="shareBtn" style="flex:1">Share 🧩</button>','<button class="btn seal" id="shareBtn" style="flex:1">Share</button>')
s=s.replace('<h2>Solve the riddle</h2>','<h2>Speak thy answer</h2>')
s=s.replace('<title>Rittel — the daily riddle</title>','<title>Rittel · the daily riddle</title>')
# light flavor in JS strings (rules unchanged)
s=s.replace('["Genius!","Brilliant!","Sharp!","Nice!","Solid!","Phew!"]','["Huzzah! A flawless solve.","Most clever!","Well riddled!","Nicely done!","Solved, and none too soon.","Phew! By a whisker."]')
s=s.replace("(won?\"Solved! 🎉\":\"So close 😵\")","(won?\"Huzzah!\":\"Alas!\")")
s=s.replace("'<h2>Your stats</h2>","'<h2>Thy record</h2>")
s=s.replace('Out of lives. The answer was "+ANSWER+".','Alas, out of lives. The answer was "+ANSWER+".')
s=s.replace('"Solved! Come back tomorrow for a new riddle."','"Solved! Return on the morrow for a new riddle."')
s=s.replace("'Consonants free if right · <b>vowels cost 1 life</b> · wrong = 1 life'","'Right consonants are free · <b>vowels cost 1 life</b> · any miss costs 1 life'")
s=s.replace('s.textContent="SOLVE"','s.textContent="Solve"')
s=s.replace('state.status==="playing"?"SOLVE":(state.status==="won"?"SOLVED ✓":"OUT OF LIVES")','state.status==="playing"?"Solve":(state.status==="won"?"Solved":"Out of lives")')
open(os.path.join(ROOT,'index.html'),'w').write(s)
print(len(s))
