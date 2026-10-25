/* Rittel v2: game logic. RIDDLES ([tier, ANSWER, riddle] rows) is injected by build.py from riddles.txt. */
(() => {
"use strict";

// ───────────────────────── config ─────────────────────────
// Advertising is OFF. Nothing is loaded and the slot renders nothing until ADS_ENABLED is true.
// See README, "Turning on ads".
const CONFIG = {
  ADS_ENABLED: false,
  AD_CLIENT: "ca-pub-XXXXXXXXXXXXXXXX", // AdSense publisher id placeholder
  AD_SLOT: "0000000000",                // AdSense ad unit id placeholder
};
const RULES = {
  DAILY_LIVES: 6,
  RUN_LIVES: 6,
  MAX_LIVES: 9,
  MISS_COST: 1,
  VOWEL_COST: 1,
  WRONG_SOLVE_COST: 2,
  YIELD_COST: 1,
  SOLVE_HEAL: 1,
  FLAWLESS_HEAL: 2,
};
const TIERS = {1:{name:"Squire",base:100}, 2:{name:"Knight",base:200}, 3:{name:"Sage",base:300}};
const HIDDEN_BONUS = 2;      // +200% of base when every tile is still hidden
const LIFE_BONUS = 10;       // per life left after the solve
const STREAK_STEP = 0.25, STREAK_CAP = 3;  // ×1, ×1.25 … ×3

const SKINS = [
  {id:"parchment", name:"Parchment", desc:"The scribe's own. Follows thy device: daylight parchment, or candlelit leather by night.", price:0, sw:["#e8d4a6","#2f5a36","#8e1b1b","#20150d"]},
  {id:"royal", name:"Royal Court", desc:"Purple velvet and gold leaf, fit for the throne room.", price:2500, sw:["#2b1442","#e0b84f","#7d3cb0","#f1e2bf"]},
  {id:"forest", name:"Forest Ranger", desc:"Oak, moss and lantern light from deep in the greenwood.", price:4000, sw:["#16281b","#5c8f3b","#c8782a","#e8dcbc"]},
  {id:"dragon", name:"Dragon's Hoard", desc:"Obsidian scales, ember glow and a mountain of gold.", price:8000, sw:["#120806","#e9b949","#c2361b","#2e7d5b"]},
];
const ITEMS = [{id:"noads", name:"Banish the Ads", desc:"A royal decree: no banner shall ever darken thy scroll.", price:6000}];

// ───────────────────────── riddle bank ─────────────────────────
const BANK = RIDDLES.map(([tier, a, q]) => ({id:a, tier, a, q}));
const BY_ID = new Map(BANK.map(r => [r.id, r]));
const VOWELS = new Set("AEIOU");
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function seededShuffle(arr, seed){const r=mulberry32(seed),a=arr.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
const DAILY_ORDER = {1:[],2:[],3:[]};
for (const t of [1,2,3]) DAILY_ORDER[t] = seededShuffle(BANK.filter(r=>r.tier===t).map(r=>r.id), 0x52495454 + t);

// Day 1 = 1 Jan 2026 (local). Mon = Squire, Tue–Thu = Knight, Fri–Sun = Sage.
const dayNumberFor = d => Math.floor((Date.UTC(d.getFullYear(),d.getMonth(),d.getDate())-Date.UTC(2026,0,1))/86400000)+1;
const dailyTier = n => { const wd = new Date(2026,0,n).getDay(); return wd===1 ? 1 : (wd>=2 && wd<=4) ? 2 : 3; };
function dailyRiddleId(n){
  const t = dailyTier(n); let count = 0;
  const end = Math.max(1, n);
  for (let d = 1; d <= end; d++) if (dailyTier(d) === t) count++;
  const order = DAILY_ORDER[t];
  return order[(count - 1 + order.length * 1000) % order.length];
}

// ───────────────────────── environment / storage ─────────────────────────
const params = new URLSearchParams(location.search);
const devDay = parseInt(params.get("day"), 10);
const DEV = Number.isFinite(devDay) || params.has("dev");
const TODAY = dayNumberFor(new Date());
const DAY = Number.isFinite(devDay) ? devDay : TODAY;
const NS = DEV ? "rittel-dev:" : "rittel:";
if (DEV && params.has("reset")) {
  Object.keys(localStorage).filter(k => k.startsWith(NS)).forEach(k => localStorage.removeItem(k));
  params.delete("reset");
  try { history.replaceState(null, "", "?" + params.toString()); } catch (e) {}
}
const store = {
  get(k, d){ try { const v = localStorage.getItem(NS + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v){ try { localStorage.setItem(NS + k, JSON.stringify(v)); } catch (e) {} },
  del(k){ try { localStorage.removeItem(NS + k); } catch (e) {} },
};

// v1 → v2 migration: keep daily stats and streaks; give veterans a purse; never double-count today.
(function migrate(){
  if (store.get("schema", 1) >= 2) return;
  const old = store.get("stats", null);
  const wallet = store.get("wallet", {gold:0, lifetime:0});
  if (old) {
    old.dist = old.dist || [0,0,0,0,0,0];
    old.losses = old.losses || 0;
    old.bestScore = old.bestScore || 0;
    store.set("stats", old);
    const bonus = 150 * (old.wins || 0);
    wallet.gold += bonus; wallet.lifetime += bonus;
    if (bonus) store.set("veteranBonus", bonus);
  }
  const st = store.get("state", null);   // v1 in-progress / finished daily
  if (st && st.day === TODAY && st.status && st.status !== "playing") store.set("legacyDay", TODAY);
  store.del("state");
  if (store.get("seen", null) !== null) { store.del("seen"); }  // v1 "help seen" flag; v2 shows the new rules once
  store.set("wallet", wallet);
  store.set("schema", 2);
})();

let stats = store.get("stats", {played:0,wins:0,streak:0,maxStreak:0,lastWon:null,dist:[0,0,0,0,0,0],losses:0,bestScore:0});
if (stats.lastWon !== null && stats.lastWon < DAY - 1 && stats.streak > 0 && !DEV) { stats.streak = 0; store.set("stats", stats); }
let wallet = store.get("wallet", {gold:0, lifetime:0});
let owned = new Set(store.get("owned", []));
let records = store.get("records", {solved:0, runs:0, bestRun:0, bestStreak:0, sages:0});
let prefs = store.get("prefs", {mode:"daily", skin:"parchment", name:""});

// ───────────────────────── leaderboard adapter ─────────────────────────
// Any backend must implement: submitScore(board, entry) -> Promise<{rank}>, getTop(board, limit) -> Promise<entry[]>.
// board is "gauntlet" or "daily"; entry = {name, score, ...meta, at}. Swap `Leaderboard` for a remote adapter
// (Supabase, Firebase …) later; the UI only talks to this interface.
const LocalLeaderboard = {
  id: "local",
  _key: b => "lb:" + b,
  async submitScore(board, entry){
    const list = store.get(this._key(board), []);
    const e = Object.assign({at: Date.now()}, entry);
    list.push(e);
    list.sort((a, b) => b.score - a.score || a.at - b.at);
    store.set(this._key(board), list.slice(0, 50));
    return {rank: list.indexOf(e) + 1};
  },
  async getTop(board, limit = 10){ return store.get(this._key(board), []).slice(0, limit); },
};
const Leaderboard = LocalLeaderboard;

// ───────────────────────── ads (isolated, off by default) ─────────────────────────
const Ads = {
  shouldShow(){ return CONFIG.ADS_ENABLED && !owned.has("noads"); },
  init(){
    const slot = $("adSlot"); const show = this.shouldShow();
    slot.hidden = !show; document.body.classList.toggle("has-ad", show);
    if (show && !slot.dataset.loaded) { slot.dataset.loaded = "1"; this.load(slot); }
  },
  // Intentionally empty. To go live, inject the AdSense loader here using CONFIG.AD_CLIENT and render an
  // <ins class="adsbygoogle"> unit with CONFIG.AD_SLOT inside `slot`. The slot height is reserved by CSS so nothing shifts.
  load(slot){},
};

// ───────────────────────── state ─────────────────────────
const newRound = id => ({id, guessed:[], history:[], status:"playing", lost:0, points:0, hidden:0, breakdown:null});
let daily = store.get("daily", null);
if (!daily || daily.day !== DAY || !BY_ID.has(daily.round.id)) daily = {day:DAY, round:newRound(dailyRiddleId(DAY)), recorded:false};
let run = store.get("run", null);
if (run && run.round && !BY_ID.has(run.round.id)) run = null;
let mode = prefs.mode === "gauntlet" ? "gauntlet" : "daily";
const save = () => { store.set("daily", daily); store.set("run", run); store.set("prefs", prefs); store.set("wallet", wallet); store.set("records", records); store.set("stats", stats); store.set("owned", [...owned]); };

const R = () => mode === "daily" ? daily.round : (run ? run.round : null);
const riddle = () => { const r = R(); return r ? BY_ID.get(r.id) : null; };
const lettersOf = a => new Set(a.replace(/[^A-Z]/g, ""));
const norm = s => s.toUpperCase().replace(/[^A-Z]/g, "");
function lives(){ return mode === "daily" ? RULES.DAILY_LIVES - daily.round.lost : (run ? run.lives : 0); }
function maxLives(){ return mode === "daily" ? RULES.DAILY_LIVES : RULES.MAX_LIVES; }
function spend(n){
  const r = R(); r.lost += n;
  if (mode === "gauntlet") run.lives = Math.max(0, run.lives - n);
}
const runActive = () => !!(run && !run.over);
const playing = () => { const r = R(); return !!r && r.status === "playing" && (mode === "daily" || runActive()); };

// ───────────────────────── scoring ─────────────────────────
function streakMult(streak){ return Math.min(STREAK_CAP, 1 + STREAK_STEP * Math.max(0, streak - 1)); }
function scoreSolve({tier, hiddenFrac, livesLeft, streak}){
  const base = TIERS[tier].base;
  const hidden = Math.round(base * HIDDEN_BONUS * hiddenFrac / 5) * 5;
  const life = LIFE_BONUS * livesLeft;
  const mult = streakMult(streak);
  const total = Math.round((base + hidden + life) * mult / 5) * 5;
  return {base, hidden, life, mult, total};
}

// ───────────────────────── seen-tracking & gauntlet picking ─────────────────────────
function runTierWeights(n){
  if (n <= 2) return [70, 30, 0];
  if (n <= 5) return [25, 55, 20];
  if (n <= 8) return [10, 50, 40];
  return [5, 35, 60];
}
function pickRunRiddle(n){
  const exclude = dailyRiddleId(DAY);
  let seen = new Set(store.get("seenRiddles", []));
  let pool = BANK.filter(r => !seen.has(r.id) && r.id !== exclude);
  if (!pool.length) { seen = new Set(); store.set("seenRiddles", []); pool = BANK.filter(r => r.id !== exclude); }
  const w = runTierWeights(n);
  const byTier = [1,2,3].map(t => pool.filter(r => r.tier === t));
  let total = 0; const ww = w.map((x, i) => byTier[i].length ? x : 0); ww.forEach(x => total += x);
  let tierIdx;
  if (!total) tierIdx = byTier.findIndex(l => l.length);
  else { let r = Math.random() * total; tierIdx = 0; while (r >= ww[tierIdx]) { r -= ww[tierIdx]; tierIdx++; } }
  const list = byTier[tierIdx];
  const pick = list[Math.floor(Math.random() * list.length)];
  seen.add(pick.id); store.set("seenRiddles", [...seen]);
  return pick.id;
}

// ───────────────────────── DOM helpers ─────────────────────────
function $(id){ return document.getElementById(id); }
const board = $("board"), kb = $("kb"), msg = $("msg"), livesEl = $("lives");
let tiles = [], builtFor = null;
const fmt = n => Math.round(n).toLocaleString("en-US");
function el(tag, cls, text){ const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function setMsg(t){ msg.textContent = t || ""; }
function toast(t, ms = 1800){ const e = $("toast"); e.textContent = t; e.classList.add("on"); clearTimeout(toast._t); toast._t = setTimeout(() => e.classList.remove("on"), ms); }
function shake(){ board.classList.remove("shake"); void board.offsetWidth; board.classList.add("shake"); }

function buildBoard(){
  const rd = riddle(); board.innerHTML = ""; tiles = []; builtFor = rd ? rd.id + "|" + mode : null;
  if (!rd) return;
  rd.a.split(" ").forEach(w => {
    const wd = el("div", "word");
    for (const ch of w) {
      const t = el("div", "tile" + (VOWELS.has(ch) ? " v" : ""));
      t.innerHTML = '<div class="in"><div class="face front"></div><div class="face back"></div></div>';
      t.querySelector(".back").textContent = ch;
      t.setAttribute("aria-label", "blank"); wd.appendChild(t); tiles.push({el:t, ch});
    }
    board.appendChild(wd);
  });
  sizeTiles();
  revealTiles(false);
}
function sizeTiles(){
  const rd = riddle(); if (!rd) return;
  const words = rd.a.split(" "), longest = Math.max(...words.map(w => w.length));
  const W = Math.min(board.clientWidth || window.innerWidth - 32, 560);
  const fit = (n, g) => Math.floor((W - g * (n - 1)) / n);
  let ts = fit(rd.a.length + (words.length - 1) * 2, 5);
  if (ts < 34) ts = fit(longest, 5);
  ts = Math.max(18, Math.min(50, ts));
  board.style.setProperty("--ts", ts + "px");
  board.style.setProperty("--tg", (ts < 28 ? 3 : 5) + "px");
}
window.addEventListener("resize", sizeTiles);

function revealTiles(animate, onlyCh){
  const r = R(); if (!r) return 0; let n = 0;
  const done = r.status !== "playing";
  tiles.forEach(t => {
    if (onlyCh && t.ch !== onlyCh) return;
    const show = done || r.guessed.includes(t.ch);
    if (show && !t.el.classList.contains("rev")) {
      if (done && r.status !== "won" && !r.guessed.includes(t.ch)) t.el.classList.add("missed");
      const inn = t.el.querySelector(".in");
      if (!animate) inn.style.transition = "none";
      const d = animate ? n++ * 80 : 0;
      setTimeout(() => { t.el.classList.add("rev"); t.el.setAttribute("aria-label", t.ch); }, d);
      if (!animate) requestAnimationFrame(() => requestAnimationFrame(() => { inn.style.transition = ""; }));
    }
  });
  return n * 80;
}

// ───────────────────────── keyboard ─────────────────────────
const ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"];
const keyEls = {};
function buildKeyboard(){
  ROWS.forEach(r => {
    const row = el("div", "row");
    for (const ch of r) {
      const b = el("button", "key" + (VOWELS.has(ch) ? " vowel" : ""), ch); b.dataset.k = ch;
      b.setAttribute("aria-label", ch + (VOWELS.has(ch) ? " (vowel, costs 1 life)" : ""));
      b.addEventListener("click", () => guess(ch)); row.appendChild(b); keyEls[ch] = b;
    }
    kb.appendChild(row);
  });
  const row = el("div", "row actions");
  const y = el("button", "key wide ghostkey", "Yield"); y.id = "yieldBtn"; y.title = "Skip this riddle for 1 life";
  y.addEventListener("click", yieldRound);
  const s = el("button", "key wide", "Solve"); s.id = "solveBtn"; s.addEventListener("click", primaryAction);
  row.append(y, s); kb.appendChild(row);
  kb.appendChild(Object.assign(el("div", "legend"), {innerHTML: 'Right consonants are free · <b>vowels cost 1</b> · misses cost 1 · <b>wrong solve costs 2</b>'}));
}

// ───────────────────────── rendering ─────────────────────────
function render(){
  document.documentElement.dataset.mode = mode;
  $("tabDaily").classList.toggle("on", mode === "daily"); $("tabDaily").setAttribute("aria-selected", mode === "daily");
  $("tabGauntlet").classList.toggle("on", mode === "gauntlet"); $("tabGauntlet").setAttribute("aria-selected", mode === "gauntlet");
  if (!$("gold").dataset.counting) $("gold").textContent = fmt(wallet.gold);
  const showStart = mode === "gauntlet" && !run;
  $("startPanel").hidden = !showStart;
  document.body.classList.toggle("starting", showStart);
  $("runbar").hidden = mode !== "gauntlet" || !run;
  if (showStart) {
    $("bestRun").textContent = records.bestRun ? "Thy best run: " + fmt(records.bestRun) + " points" : "No run recorded yet. Be the first in the Hall.";
    Leaderboard.getTop("gauntlet", 3).then(top => {
      const ol = $("startTop"); ol.innerHTML = "";
      top.forEach((e, i) => { const li = el("li", "top" + (i + 1)); li.append(el("span", "rk", i + 1), el("span", "nm", e.name), el("b", "sc", fmt(e.score))); ol.appendChild(li); });
      ol.hidden = !top.length;
    });
  }
  const rd = riddle();
  if (rd) {
    $("riddle").textContent = rd.q;
    $("tier").textContent = TIERS[rd.tier].name; $("tier").dataset.t = rd.tier;
    $("dayLabel").innerHTML = "";
    $("dayLabel").append(mode === "daily" ? "Riddle #" + DAY : "Riddle " + run.n);
    if (DEV) $("dayLabel").appendChild(el("span", "dev", "DEV"));
    if ((rd.id + "|" + mode) !== builtFor) buildBoard();
  } else { $("riddle").textContent = ""; board.innerHTML = ""; builtFor = null; $("tier").textContent = ""; $("dayLabel").textContent = ""; }
  if (run) { if (!$("runScore").dataset.counting) $("runScore").textContent = fmt(run.score); $("runStreak").textContent = "×" + streakMult(run.streak + 1).toFixed(2).replace(/\.?0+$/, ""); $("runSolved").textContent = run.solved; }
  renderLives(); renderKeys();
}
function renderLives(){
  livesEl.innerHTML = "";
  if (mode === "gauntlet" && !run) return;
  const L = lives(), M = Math.max(maxLives(), L);
  const shown = mode === "daily" ? M : Math.max(RULES.RUN_LIVES, L);
  for (let i = 0; i < shown; i++) livesEl.appendChild(el("div", "pip" + (i >= L ? " lost" : "")));
  livesEl.classList.toggle("danger", L <= 1);
  livesEl.setAttribute("aria-label", L + " lives left");
}
function renderKeys(){
  const r = R(), rd = riddle(); const letters = rd ? lettersOf(rd.a) : new Set();
  const live = playing(), last = lives() <= 1;
  for (const ch in keyEls) {
    const b = keyEls[ch], g = !!r && r.guessed.includes(ch);
    b.classList.remove("hit", "vhit", "miss", "locked");
    if (g) b.classList.add(letters.has(ch) ? (VOWELS.has(ch) ? "vhit" : "hit") : "miss");
    if (!g && VOWELS.has(ch) && last && live) b.classList.add("locked");
    b.disabled = g || !live;
  }
  const s = $("solveBtn"), y = $("yieldBtn");
  y.hidden = !(mode === "gauntlet" && live);
  s.classList.toggle("next", !live);
  if (live) s.textContent = "Solve";
  else if (mode === "daily") s.textContent = "Onward to the Gauntlet";
  else if (!run) s.textContent = "Enter the Gauntlet";
  else if (run.over) s.textContent = "Begin a new run";
  else s.textContent = "Next riddle";
}

// ───────────────────────── actions ─────────────────────────
function primaryAction(){
  if (playing()) return openSolve();
  if (mode === "daily") return setMode("gauntlet");
  if (!run || run.over) return startRun();
  nextRiddle();
}
function guess(ch){
  if (!playing()) return;
  const r = R(), rd = riddle(); if (r.guessed.includes(ch)) return;
  const isV = VOWELS.has(ch), hit = lettersOf(rd.a).has(ch);
  if (isV && lives() <= 1) { toast("Last life: thou canst not buy a vowel now"); shake(); return; }
  r.guessed.push(ch);
  if (isV) { spend(RULES.VOWEL_COST); r.history.push(hit ? "V" : "X"); }
  else if (!hit) { spend(RULES.MISS_COST); r.history.push("X"); }
  else r.history.push("H");
  const count = tiles.filter(t => t.ch === ch).length;
  if (hit) setMsg(count + " × " + ch + (isV ? " (bought, −1 life)" : ""));
  else { setMsg("No " + ch + " (−1 life)"); shake(); }
  const delay = hit ? revealTiles(true, ch) : 0;
  afterMove(delay);
}
function hiddenFraction(){
  const r = R(); const hidden = tiles.filter(t => !r.guessed.includes(t.ch)).length;
  return tiles.length ? hidden / tiles.length : 0;
}
function solve(text){
  if (!playing()) return false;
  const g = norm(text); if (!g) return false;
  const r = R(), rd = riddle();
  if (g === norm(rd.a)) { r.history.push("S"); win(hiddenFraction()); return true; }
  spend(RULES.WRONG_SOLVE_COST); r.history.push("W");
  setMsg("“" + text.trim().toUpperCase().slice(0, 30) + "” is not it (−" + RULES.WRONG_SOLVE_COST + " lives)"); shake();
  afterMove(0); return false;
}
function afterMove(delay){
  const r = R(), rd = riddle();
  if ([...lettersOf(rd.a)].every(c => r.guessed.includes(c))) return win(0, delay);
  if (lives() <= 0) return lose(delay);
  save(); render();
}
function win(hiddenFrac, delay = 0){
  const r = R(), rd = riddle();
  r.status = "won"; r.hidden = hiddenFrac;
  let streak;
  if (mode === "daily") {
    const legacy = store.get("legacyDay", null) === DAY;
    if (!daily.recorded && !legacy) {
      stats.played++; stats.wins++; stats.dist[Math.min(r.lost, 5)]++;
      stats.streak = (stats.lastWon === DAY - 1) ? stats.streak + 1 : 1;
      stats.lastWon = DAY; stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
    }
    streak = Math.max(1, stats.streak);
  } else {
    run.streak++; streak = run.streak;
  }
  const sc = scoreSolve({tier: rd.tier, hiddenFrac, livesLeft: lives(), streak});
  r.points = sc.total; r.breakdown = sc;
  wallet.gold += sc.total; wallet.lifetime += sc.total; records.solved++; if (rd.tier === 3) records.sages++;
  if (mode === "daily") {
    if (!daily.recorded) {
      daily.recorded = true; stats.bestScore = Math.max(stats.bestScore || 0, sc.total);
      Leaderboard.submitScore("daily", {name: prefs.name || "Wanderer", score: sc.total, day: DAY, used: r.lost});
    }
  } else {
    const before = run.score;
    run.score += sc.total; run.solved++; run.bestStreak = Math.max(run.bestStreak, run.streak);
    const heal = r.lost === 0 ? RULES.FLAWLESS_HEAL : RULES.SOLVE_HEAL;
    const healed = Math.min(RULES.MAX_LIVES, run.lives + heal) - run.lives; run.lives += healed; r.healed = healed;
    countUp($("runScore"), before, run.score, 900);
  }
  save();
  setTimeout(() => {
    const d = revealTiles(true);
    render();
    setTimeout(() => tiles.forEach((t, i) => { t.el.style.setProperty("--d", (i * 50) + "ms"); t.el.classList.add("win"); }), d + 450);
    popPoints(sc, rd, d + 250);
    const flair = ["Huzzah!", "Most clever!", "Well riddled!", "Nicely done!", "Solved, and none too soon.", "Phew! By a whisker."][Math.min(r.lost, 5)];
    setMsg(flair + (mode === "gauntlet" && r.healed ? "  +" + r.healed + (r.healed > 1 ? " lives" : " life") + (r.lost === 0 ? " for a flawless solve" : "") : ""));
    if (mode === "daily") setTimeout(openStats, d + 2300);
  }, delay + 200);
}
function lose(delay = 0){
  const r = R(), rd = riddle();
  r.status = "lost";
  if (mode === "daily") {
    if (!daily.recorded && store.get("legacyDay", null) !== DAY) { stats.played++; stats.losses = (stats.losses || 0) + 1; stats.streak = 0; }
    daily.recorded = true;
  } else endRun();
  save();
  setTimeout(() => {
    const d = revealTiles(true); render();
    setMsg("Alas, out of lives. The answer was " + rd.a + ".");
    setTimeout(mode === "daily" ? openStats : openRunEnd, d + 1200);
  }, delay + 200);
}
function yieldRound(){
  if (mode !== "gauntlet" || !playing()) return;
  const r = R(), rd = riddle();
  spend(RULES.YIELD_COST); r.status = "yielded"; r.history.push("Y"); run.streak = 0;
  if (run.lives <= 0) { r.status = "lost"; endRun(); }
  save();
  const d = revealTiles(true); render();
  setMsg("Thou yieldest. It was " + rd.a + ". Streak reset.");
  if (run.over) setTimeout(openRunEnd, d + 1100);
}
function endRun(){
  run.over = true; run.endedAt = Date.now();
  records.runs++; records.bestRun = Math.max(records.bestRun, run.score); records.bestStreak = Math.max(records.bestStreak, run.bestStreak);
  run.pendingSubmit = run.score > 0;
}
function startRun(){
  run = {lives: RULES.RUN_LIVES, score: 0, streak: 0, bestStreak: 0, solved: 0, n: 1, over: false, startedAt: Date.now()};
  run.round = newRound(pickRunRiddle(1));
  closeAll(); setMsg("The Gauntlet begins. Fortune favour thee."); save(); render();
}
function nextRiddle(){
  if (!run || run.over) return;
  run.n++; run.round = newRound(pickRunRiddle(run.n));
  setMsg(""); save(); render();
}
function setMode(m){
  if (m === mode) return;
  mode = m; prefs.mode = m; save(); closeAll(); setMsg(""); render();
  if (m === "gauntlet" && run && run.over) setTimeout(openRunEnd, 50);
}

// ───────────────────────── points animation ─────────────────────────
function popPoints(sc, rd, delay){
  const p = $("pop"); p.innerHTML = "";
  p.appendChild(el("div", "pts", "+" + fmt(sc.total)));
  const lines = el("div", "lines");
  lines.appendChild(el("span", "", TIERS[rd.tier].name + " " + sc.base));
  if (sc.hidden) lines.appendChild(el("span", "", "Hidden tiles +" + sc.hidden));
  if (sc.life) lines.appendChild(el("span", "", "Lives +" + sc.life));
  if (sc.mult > 1) lines.appendChild(el("span", "mult", "Streak ×" + sc.mult.toFixed(2).replace(/\.?0+$/, "")));
  p.appendChild(lines);
  setTimeout(() => {
    p.classList.remove("on"); void p.offsetWidth; p.classList.add("on");
    const g = $("purse"); g.classList.remove("bump"); void g.offsetWidth; g.classList.add("bump");
    countUp($("gold"), wallet.gold - sc.total, wallet.gold, 1000);
    for (let i = 0; i < 10; i++) {
      const c = el("i", "spark"); c.style.setProperty("--x", (Math.random() * 220 - 110) + "px"); c.style.setProperty("--y", (-60 - Math.random() * 90) + "px");
      c.style.animationDelay = (Math.random() * 180) + "ms"; p.appendChild(c);
    }
  }, delay);
  clearTimeout(popPoints._t); popPoints._t = setTimeout(() => p.classList.remove("on"), delay + 2600);
}
function countUp(node, from, to, ms){
  const t0 = performance.now(); node.dataset.counting = "1";
  const step = now => { const k = Math.min(1, (now - t0) / ms); node.textContent = fmt(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step); else delete node.dataset.counting; };
  requestAnimationFrame(step);
}

// ───────────────────────── modals ─────────────────────────
function open(id){ $(id).classList.add("open"); }
function close(id){
  $(id).classList.remove("open");
  if (id === "helpModal") store.set("helpV2", true);
  if (id === "runModal" && run && run.pendingSubmit) submitRun(prefs.name || "Wanderer");
}
function closeAll(){ document.querySelectorAll(".overlay.open").forEach(o => close(o.id)); }
document.querySelectorAll(".overlay").forEach(o => o.addEventListener("click", e => { if (e.target === o || e.target.closest("[data-close]")) close(o.id); }));
const anyOpen = () => document.querySelector(".overlay.open");
$("helpBtn").onclick = () => open("helpModal");
$("statsBtn").onclick = openStats;
$("hallBtn").onclick = () => openHall("gauntlet");
$("shopBtn").onclick = openShop; $("purse").onclick = openShop;
$("tabDaily").onclick = () => setMode("daily");
$("tabGauntlet").onclick = () => setMode("gauntlet");
$("startRun").onclick = startRun;
$("runAgain").onclick = () => { if (run && run.pendingSubmit) submitRun(prefs.name || "Wanderer"); startRun(); };
$("toGauntlet").onclick = () => setMode("gauntlet");

function openSolve(){
  if (!playing()) return;
  const rd = riddle(), r = R(); const words = rd.a.split(" ").map(w => w.length);
  $("solveHint").textContent = (words.length > 1 ? words.length + " words (" + words.join(", ") + " letters)" : words[0] + " letters") +
    " · a wrong guess costs " + RULES.WRONG_SOLVE_COST + " lives · " + lives() + " left";
  const inp = $("solveInput"); inp.value = "";
  inp.placeholder = rd.a.split(" ").map(w => [...w].map(c => r.guessed.includes(c) ? c : "_").join("")).join(" ");
  open("solveModal"); setTimeout(() => inp.focus(), 50);
}
$("solveForm").addEventListener("submit", e => {
  e.preventDefault(); const v = $("solveInput").value; if (!norm(v)) { $("solveInput").focus(); return; }
  close("solveModal"); solve(v);
});

const EMO = {H:"🟩", V:"🟨", X:"⬛", S:"⭐", W:"🟥", Y:"🏳️"};
const emojiRow = r => r.history.map(h => EMO[h]).join("");
function dailyShareText(){
  const r = daily.round; const won = r.status === "won";
  return "Rittel #" + DAY + " 🧩 " + (won ? r.lost : "X") + "/" + RULES.DAILY_LIVES + "\n" + emojiRow(r) + (won ? "\n⚜ " + fmt(r.points) + " points" : "");
}
function runShareText(){
  return "Rittel · The Gauntlet ⚔\n⚜ " + fmt(run.score) + " points · " + run.solved + " riddle" + (run.solved === 1 ? "" : "s") + " solved · best streak " + run.bestStreak;
}
async function copy(txt){
  try { await navigator.clipboard.writeText(txt); toast("Copied to clipboard"); }
  catch (e) {
    const ta = el("textarea"); ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch (_) {}
    ta.remove(); toast(ok ? "Copied to clipboard" : txt, ok ? 1600 : 4000);
  }
}
$("shareBtn").onclick = () => copy(dailyShareText());
$("runShare").onclick = () => run && copy(runShareText());

function openStats(){
  const res = $("result"); res.innerHTML = ""; const r = daily.round, rd = BY_ID.get(r.id);
  if (r.status === "playing") {
    res.append(el("h2", "", "Thy record"), el("p", "hintline", "Today's riddle is still unsolved."));
    $("foot").style.display = "none";
  } else {
    const won = r.status === "won";
    res.append(el("h2", "", won ? "Huzzah!" : "Alas!"),
      el("div", "hintline", won ? "Solved with " + r.lost + " of " + RULES.DAILY_LIVES + " lives spent" : "Thou ran out of lives"),
      el("div", "ans", rd.a));
    if (won) res.appendChild(el("div", "earned", "+" + fmt(r.points) + " gold"));
    res.append(el("div", "emo", emojiRow(r)), el("p", "hintline", "“" + rd.q + "”"));
    $("foot").style.display = "";
  }
  const pct = stats.played ? Math.round(stats.wins / stats.played * 100) : 0;
  const S = $("stats"); S.innerHTML = "";
  [[stats.played, "Played"], [pct, "Win %"], [stats.streak, "Streak"], [stats.maxStreak, "Max streak"]].forEach(([v, l]) => { const d = el("div"); d.append(el("b", "", v), el("span", "", l)); S.appendChild(d); });
  const mx = Math.max(1, ...stats.dist, stats.losses || 0);
  const D = $("dist"); D.innerHTML = "";
  stats.dist.map((v, i) => [String(i), v, r.status === "won" && r.lost === i]).concat([["X", stats.losses || 0, r.status === "lost"]]).forEach(([l, v, me]) => {
    const row = el("div", "bar" + (me ? " me" : "")); const f = el("span", "fill", v); f.style.width = Math.max(7, Math.round(v / mx * 100)) + "%";
    row.append(el("span", "lbl", l), f); D.appendChild(row);
  });
  $("toGauntlet").hidden = r.status === "playing";
  open("statsModal");
}

async function openRunEnd(){
  if (!run || !run.over) return;
  const rd = BY_ID.get(run.round.id);
  $("runAnswer").textContent = "The last riddle's answer: " + rd.a;
  $("runFinal").textContent = fmt(run.score);
  $("runSummary").textContent = run.solved + " riddle" + (run.solved === 1 ? "" : "s") + " solved · best streak " + run.bestStreak + " · gold earned " + fmt(run.score);
  const top = await Leaderboard.getTop("gauntlet", 10);
  const wouldRank = run.score > 0 ? top.filter(e => e.score >= run.score).length + 1 : null;
  $("runRank").textContent = run.pendingSubmit
    ? (wouldRank <= 10 ? "A place in the Hall of Fame awaits: rank " + wouldRank + "!" : "Not quite enough for the Hall this time.")
    : (run.rank ? "Inscribed in the Hall at rank " + run.rank + "." : "");
  $("nameForm").hidden = !run.pendingSubmit;
  $("nameInput").value = prefs.name || "";
  $("runTitle").textContent = run.score >= records.bestRun && run.score > 0 ? "A new personal best!" : "Thy run is ended";
  open("runModal");
  if (run.pendingSubmit) setTimeout(() => $("nameInput").focus(), 60);
}
$("nameForm").addEventListener("submit", async e => {
  e.preventDefault();
  const name = $("nameInput").value.replace(/[\u0000-\u001f<>]/g, "").trim().slice(0, 14) || "Wanderer";
  prefs.name = name; await submitRun(name); openRunEnd();
});
async function submitRun(name){
  if (!run || !run.pendingSubmit) return;
  run.pendingSubmit = false; save();
  const {rank} = await Leaderboard.submitScore("gauntlet", {name, score: run.score, solved: run.solved, streak: run.bestStreak});
  run.rank = rank; save();
}

async function openHall(tab){
  document.querySelectorAll(".subtab").forEach(b => b.classList.toggle("on", b.dataset.hall === tab));
  const body = $("hallBody"); body.innerHTML = "";
  if (tab === "records") {
    const pct = stats.played ? Math.round(stats.wins / stats.played * 100) : 0;
    const rows = [["Lifetime points", fmt(wallet.lifetime)], ["Gold in purse", fmt(wallet.gold)], ["Riddles solved", records.solved], ["Sage riddles solved", records.sages],
      ["Gauntlet runs", records.runs], ["Best run", fmt(records.bestRun)], ["Best run streak", records.bestStreak],
      ["Daily played", stats.played], ["Daily win %", pct], ["Best daily score", fmt(stats.bestScore || 0)], ["Daily max streak", stats.maxStreak]];
    const t = el("div", "records"); rows.forEach(([k, v]) => { const r = el("div", "rec"); r.append(el("span", "", k), el("b", "", v)); t.appendChild(r); });
    body.appendChild(t);
  } else {
    const list = await Leaderboard.getTop(tab, 10);
    if (!list.length) body.appendChild(el("p", "empty", tab === "gauntlet" ? "No runs yet. Enter the Gauntlet and claim the first place." : "Solve a daily riddle to be recorded here."));
    const ol = el("ol", "lb");
    list.forEach((e, i) => {
      const li = el("li", i < 3 ? "top" + (i + 1) : "");
      li.append(el("span", "rk", i + 1), el("span", "nm", e.name),
        el("span", "dt", tab === "gauntlet" ? e.solved + " solved" : "#" + e.day), el("b", "sc", fmt(e.score)));
      ol.appendChild(li);
    });
    body.appendChild(ol);
  }
  open("hallModal");
}
document.querySelectorAll(".subtab").forEach(b => b.onclick = () => openHall(b.dataset.hall));

function applySkin(){
  const s = SKINS.find(k => k.id === prefs.skin && (k.price === 0 || owned.has(k.id))) || SKINS[0];
  document.documentElement.dataset.skin = s.id;
  const tc = s.id === "parchment" ? null : s.sw[0];
  document.querySelectorAll('meta[name="theme-color"]').forEach(m => { if (tc) m.setAttribute("content", tc); });
}
function openShop(){
  document.querySelectorAll(".shopGold").forEach(n => n.textContent = fmt(wallet.gold));
  const L = $("shopList"); L.innerHTML = "";
  const card = (it, isSkin) => {
    const c = el("div", "item" + (isSkin && prefs.skin === it.id ? " equipped" : "")); c.dataset.item = it.id;
    const sw = el("div", "swatch");
    if (isSkin) it.sw.forEach(col => { const s = el("i"); s.style.background = col; sw.appendChild(s); });
    else sw.classList.add("noads");
    const info = el("div", "info"); info.append(el("b", "", it.name), el("span", "", it.desc));
    const has = it.price === 0 || owned.has(it.id);
    let label, act, dis = false;
    if (isSkin && has) { label = prefs.skin === it.id ? "Worn" : "Wear"; dis = prefs.skin === it.id; act = () => { prefs.skin = it.id; save(); applySkin(); openShop(); toast(it.name + " donned"); }; }
    else if (has) { label = "Owned"; dis = true; }
    else { label = fmt(it.price); act = () => buy(it, isSkin); }
    const b = el("button", "btn buy" + (has ? "" : " price") + (!has && wallet.gold < it.price ? " short" : ""), label);
    b.disabled = dis; if (act) b.onclick = act;
    c.append(sw, info, b); L.appendChild(c);
  };
  SKINS.forEach(s => card(s, true)); ITEMS.forEach(i => card(i, false));
  open("shopModal");
}
function buy(it, isSkin){
  if (owned.has(it.id)) return;
  if (wallet.gold < it.price) { toast("Thou needest " + fmt(it.price - wallet.gold) + " more gold"); return; }
  wallet.gold -= it.price; owned.add(it.id);
  if (isSkin) prefs.skin = it.id;
  save(); applySkin(); Ads.init(); render(); openShop();
  toast(isSkin ? it.name + " is thine!" : "So decreed: " + it.name);
}

// countdown
function tick(){
  const now = new Date(), t = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const s = Math.max(0, Math.floor((t - now) / 1000)), p = n => String(n).padStart(2, "0");
  $("countdown").textContent = p(Math.floor(s / 3600)) + ":" + p(Math.floor(s % 3600 / 60)) + ":" + p(s % 60);
}
setInterval(tick, 1000); tick();

// physical keyboard
document.addEventListener("keydown", e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const o = anyOpen();
  if (e.key === "Escape" && o) { close(o.id); return; }
  if (o) return;
  if (/^[a-zA-Z]$/.test(e.key)) { e.preventDefault(); guess(e.key.toUpperCase()); }
  else if (e.key === "Enter") { e.preventDefault(); primaryAction(); }
});

// ───────────────────────── init ─────────────────────────
applySkin(); buildKeyboard(); render(); Ads.init();
if (mode === "daily" && daily.round.status !== "playing") setTimeout(openStats, 400);
if (mode === "gauntlet" && run && run.over) setTimeout(openRunEnd, 400);
else if (mode === "gauntlet" && run && run.round.status !== "playing") setMsg("Press Next riddle to continue thy run.");
else if (R() && R().history.length && playing()) setMsg("Welcome back. " + lives() + " lives left.");
const vb = store.get("veteranBonus", 0);
if (vb) { store.del("veteranBonus"); setTimeout(() => toast("Welcome back, veteran: " + fmt(vb) + " gold for thy past solves", 3500), 600); }
if (!store.get("helpV2", false)) open("helpModal");

if (DEV) window.__rittel = {
  day: DAY, bankSize: BANK.length, bank: BANK, mode: () => mode, answer: () => riddle() && riddle().a, tier: () => riddle() && riddle().tier,
  round: () => JSON.parse(JSON.stringify(R())), run: () => JSON.parse(JSON.stringify(run)), daily: () => JSON.parse(JSON.stringify(daily)),
  lives, wallet: () => ({...wallet}), owned: () => [...owned], scoreSolve, dailyRiddleId, rules: RULES, config: CONFIG,
  grant(n){ wallet.gold += n; save(); render(); },
};
})();
