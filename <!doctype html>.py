<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auto Trader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"></script>
<style>
:root {
  --bg: #E6EAEF; --panel: #F6F8FA; --ink: #17202C; --muted: #5A6777; --line: #C9D1DA;
  --accent: #2E3DB0; --accent-ink: #FFFFFF; --gain: #177A4B; --loss: #B0392D; --warn: #8E6300;
  --hatch: rgba(23, 32, 44, .16); --live: #B0392D;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0F141B; --panel: #171F29; --ink: #E5EAF0; --muted: #93A1B2; --line: #2A3542;
    --accent: #8E99FF; --accent-ink: #0E1230; --gain: #4DC48B; --loss: #F2796D; --warn: #E3B64B;
    --hatch: rgba(229, 234, 240, .2); --live: #F2796D;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--bg); color: var(--ink);
  font: 15px/1.5 "Schibsted Grotesk", system-ui, -apple-system, sans-serif;
  font-variant-numeric: tabular-nums;
}
button, input { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 24px 20px 64px; }
[hidden] { display: none !important; }

/* Header */
header { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
header h1 { font-size: 22px; font-weight: 700; letter-spacing: -.01em; margin: 0; margin-right: auto; }
.bot { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
.dot.on { background: var(--gain); }
.dot.off { background: var(--loss); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; padding: 2px; background: var(--panel); }
.seg button { border: 0; background: transparent; padding: 5px 12px; border-radius: 6px; font-size: 13px; font-weight: 500; color: var(--muted); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--bg); }
.seg.mode button.live[aria-pressed="true"] { background: var(--live); color: #fff; }
.link { background: none; border: 0; color: var(--muted); font-size: 13px; text-decoration: underline; padding: 0; }

/* Portfolio band */
.portfolio { margin-bottom: 32px; }
.stats { display: flex; gap: 40px; flex-wrap: wrap; margin-bottom: 14px; }
.stat .v { font-size: 30px; font-weight: 600; letter-spacing: -.02em; line-height: 1.1; }
.stat .k { font-size: 13px; color: var(--muted); }
.up { color: var(--gain); } .down { color: var(--loss); }
.band { display: flex; height: 44px; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); background: var(--panel); }
.band .s { min-width: 3px; border-right: 2px solid var(--bg); }
.band .s:last-child { border-right: 0; }
.band .s.cash { background-image: repeating-linear-gradient(135deg, var(--c) 0 3px, transparent 3px 9px); opacity: .85; }
.band .s.held { background: var(--c); }
.band-empty { display: flex; align-items: center; padding: 0 14px; color: var(--muted); font-size: 13px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 22px; margin-top: 10px; font-size: 13px; }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.legend i { width: 12px; height: 12px; border-radius: 3px; background: var(--c); display: inline-block; }
.legend i.cash { background: repeating-linear-gradient(135deg, var(--c) 0 2px, transparent 2px 5px); border: 1px solid var(--c); }
.legend em { font-style: normal; color: var(--muted); }

/* Panels */
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; }
h2 { font-size: 16px; font-weight: 600; margin: 0 0 12px; }

/* Add asset */
.add { margin-bottom: 28px; }
.add-grid { display: grid; grid-template-columns: 1.3fr 1fr .8fr .8fr; gap: 12px; }
label.f { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); }
input.in { background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px; font-size: 15px; width: 100%; min-width: 0; }
input.in:focus { border-color: var(--accent); outline: none; }
.row2 { display: flex; align-items: center; gap: 12px 20px; flex-wrap: wrap; margin-top: 14px; }
.presets { display: flex; gap: 6px; align-items: center; font-size: 13px; color: var(--muted); }
.chip { border: 1px solid var(--line); background: transparent; border-radius: 999px; padding: 3px 10px; font-size: 13px; }
.chip:hover { border-color: var(--ink); }
.choice { display: flex; gap: 8px; }
.choice button { border: 1px solid var(--line); background: var(--bg); border-radius: 8px; padding: 7px 12px; text-align: left; font-size: 13px; line-height: 1.3; }
.choice button b { display: block; font-weight: 600; font-size: 14px; }
.choice button[aria-pressed="true"] { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.primary { background: var(--accent); color: var(--accent-ink); border: 0; border-radius: 8px; padding: 11px 18px; font-weight: 600; margin-left: auto; }
.primary:disabled { opacity: .5; cursor: default; }
.form-msg { font-size: 13px; color: var(--loss); margin: 10px 0 0; min-height: 1em; }

/* Asset cards */
.assets { display: flex; flex-direction: column; gap: 14px; }
.asset { position: relative; border-left: 4px solid var(--c); border-radius: 0 12px 12px 0; }
.asset-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.asset-head h3 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -.01em; }
.asset-head h3 small { font-size: 14px; font-weight: 400; color: var(--muted); }
.state { font-size: 13px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }
.state.holding { color: var(--gain); border-color: var(--gain); }
.state.watching { color: var(--accent); border-color: var(--accent); }
.state.waiting { color: var(--warn); border-color: var(--warn); }
.asset-head .seg { margin-left: auto; }

.rail { margin: 4px 0 16px; }
.track { position: relative; height: 6px; border-radius: 3px; background: var(--line); margin: 10px 7px; }
.track .fill { position: absolute; top: 0; bottom: 0; left: 0; border-radius: 3px; background: var(--hatch); }
.track .tick { position: absolute; top: -4px; width: 2px; height: 14px; background: var(--muted); transform: translateX(-1px); }
.track .mark { position: absolute; top: 50%; width: 14px; height: 14px; border-radius: 50%; background: var(--panel); border: 3px solid var(--ink); transform: translate(-50%, -50%); transition: left .6s ease; }
.track .mark.up { border-color: var(--gain); }
.track .mark.down { border-color: var(--loss); }
.rail-labels { display: flex; justify-content: space-between; font-size: 13px; color: var(--muted); }
.rail-note { font-size: 13px; margin: 2px 0 0; }
@media (prefers-reduced-motion: reduce) { .track .mark { transition: none; } }

.facts { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px 16px; margin: 0 0 16px; }
.facts div { min-width: 0; }
.facts dt { font-size: 12px; color: var(--muted); }
.facts dd { margin: 0; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.controls { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px; padding-top: 14px; border-top: 1px solid var(--line); }
.controls label.f { width: 110px; }
.controls label.f.cap { width: 130px; }
.controls input.in { padding: 6px 9px; font-size: 14px; }
.btn { border: 1px solid var(--line); background: transparent; border-radius: 8px; padding: 6px 12px; font-size: 13px; font-weight: 500; }
.btn:hover { border-color: var(--ink); }
.btn.danger { color: var(--loss); }
.btn.danger:hover { border-color: var(--loss); }
.btn.go { background: var(--live); color: #fff; border-color: var(--live); }
.btn.save { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.spacer { flex: 1; }
.err { margin: 12px 0 0; font-size: 13px; color: var(--loss); }

details { margin-top: 12px; }
summary { font-size: 13px; color: var(--muted); cursor: pointer; }
.hist { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
.hist-wrap { overflow-x: auto; }
.hist th { text-align: left; font-weight: 500; color: var(--muted); padding: 4px 10px 4px 0; border-bottom: 1px solid var(--line); }
.hist td { padding: 5px 10px 5px 0; border-bottom: 1px solid var(--line); white-space: nowrap; }
.tag { font-size: 11px; border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; color: var(--muted); }
.tag.live { color: var(--live); border-color: var(--live); }

.empty { text-align: center; color: var(--muted); padding: 36px 20px; border: 1px dashed var(--line); border-radius: 12px; }

/* Login + setup */
.gate { max-width: 360px; margin: 12vh auto 0; }
.gate h1 { font-size: 24px; margin: 0 0 4px; }
.gate p { color: var(--muted); margin: 0 0 18px; font-size: 14px; }
.gate form { display: flex; flex-direction: column; gap: 12px; }
.gate .primary { margin-left: 0; }

.toast { position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); background: var(--ink); color: var(--bg); padding: 10px 16px; border-radius: 8px; font-size: 14px; max-width: 90vw; }
.toast.bad { background: var(--loss); color: #fff; }

@media (max-width: 760px) {
  .add-grid { grid-template-columns: 1fr 1fr; }
  .facts { grid-template-columns: repeat(3, 1fr); }
  .stats { gap: 24px; }
  .stat .v { font-size: 24px; }
  .asset-head .seg { margin-left: 0; }
  .primary { margin-left: 0; width: 100%; }
}
</style>
</head>
<body>

<div id="setup" class="wrap gate" hidden>
  <h1>Add your Supabase details</h1>
  <p>Open this file, find SUPABASE_URL and SUPABASE_ANON_KEY near the top of the script, and paste in the values from Supabase, Project Settings, API.</p>
</div>

<div id="login" class="wrap gate" hidden>
  <h1>Auto Trader</h1>
  <p>Sign in with the user you created in Supabase.</p>
  <form id="loginForm">
    <label class="f">Email<input class="in" type="email" id="email" autocomplete="username" required></label>
    <label class="f">Password<input class="in" type="password" id="password" autocomplete="current-password" required></label>
    <button class="primary" type="submit">Sign in</button>
    <p class="form-msg" id="loginMsg" aria-live="polite"></p>
  </form>
</div>

<div id="app" class="wrap" hidden>
  <header>
    <h1>Auto Trader</h1>
    <div class="bot" id="botStatus"><span class="dot"></span><span>Checking bot</span></div>
    <div class="seg mode" role="group" aria-label="Trading mode">
      <button type="button" data-mode="paper">Paper</button>
      <button type="button" data-mode="live" class="live">Live</button>
    </div>
    <button class="link" type="button" id="signOut">Sign out</button>
  </header>

  <section class="portfolio" aria-label="Portfolio">
    <div class="stats" id="stats"></div>
    <div class="band" id="band"></div>
    <div class="legend" id="legend"></div>
  </section>

  <section class="panel add">
    <h2>Add a coin</h2>
    <form id="addForm" novalidate>
      <div class="add-grid">
        <label class="f">Coin
          <input class="in" id="ticker" list="marketList" placeholder="ETH, SOL, HYPE…" autocomplete="off" spellcheck="false">
          <datalist id="marketList"></datalist>
        </label>
        <label class="f">Capital for this coin (USD)
          <input class="in" id="capital" type="number" min="1" step="1" placeholder="100">
        </label>
        <label class="f">Buy after a dip of (%)
          <input class="in" id="dip" type="number" min="0.1" step="0.1" value="1.5">
        </label>
        <label class="f">Sell at a gain of (%)
          <input class="in" id="gain" type="number" min="0.1" step="0.1" value="1.5">
        </label>
      </div>
      <div class="row2">
        <div class="presets">Presets
          <button type="button" class="chip" data-preset="1,1">1 / 1</button>
          <button type="button" class="chip" data-preset="1.5,1.5">1.5 / 1.5</button>
          <button type="button" class="chip" data-preset="2,2.5">2 / 2.5</button>
          <button type="button" class="chip" data-preset="3,3">3 / 3</button>
        </div>
        <div class="choice" role="group" aria-label="Trading duration">
          <button type="button" data-perp="true"><b>Perpetual</b>Buys back after every sell</button>
          <button type="button" data-perp="false"><b>One-time</b>Buys once, sells at target, stops</button>
        </div>
        <button class="primary" type="submit" id="addBtn">Buy &amp; start trading</button>
      </div>
      <p class="form-msg" id="addMsg" aria-live="polite"></p>
    </form>
  </section>

  <section aria-label="Coins">
    <div class="assets" id="assets"></div>
  </section>
</div>

<div class="toast" id="toast" role="status" aria-live="polite" hidden></div>

<script>
// ===== CONFIG: paste from Supabase > Project Settings > API =====
const SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co';
const SUPABASE_ANON_KEY = 'YOUR-ANON-KEY';
// Never put the service_role key here. That one only goes in Railway.
// =================================================================

const POLL_MS = 5000;
const BOT_POLL_SECONDS = 15;
const COLORS = ['#2E3DB0', '#138A86', '#C06A1B', '#7B3FA6', '#3E812A', '#B0345F', '#5A6B7F', '#9A7B12'];

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = v => (v === null || v === undefined || v === '') ? null : Number(v);
const clamp = x => Math.max(0, Math.min(1, x));
const usd = n => (n < 0 ? '-$' : '$') + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signedUsd = n => (n > 0 ? '+' : '') + usd(n);
const pct = n => (n > 0 ? '+' : '') + n.toFixed(2) + '%';
const tone = n => n > 0 ? 'up' : n < 0 ? 'down' : '';
function price(p) {
  if (p === null || p === undefined) return '—';
  const a = Math.abs(p), d = a >= 100 ? 2 : a >= 1 ? 4 : 6;
  return '$' + p.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function ago(iso) {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return s + ' sec ago';
  if (s < 5400) return Math.round(s / 60) + ' min ago';
  return Math.round(s / 3600) + ' h ago';
}
let toastTimer;
function toast(msg, bad) {
  const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (bad ? ' bad' : ''); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 4500);
}

const S = {
  settings: null, markets: [], assets: [], positions: {}, trades: [],
  realized: { paper: 0, live: 0 }, drafts: {}, openHistory: new Set(), addPerpetual: null, timer: null,
};

// ---------- Boot ----------
if (SUPABASE_URL.includes('YOUR-PROJECT') || SUPABASE_ANON_KEY.includes('YOUR-ANON')) {
  $('#setup').hidden = false;
  throw new Error('Supabase config missing');
}
const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

sb.auth.onAuthStateChange((_event, session) => route(session));
sb.auth.getSession().then(({ data }) => route(data.session));

let routedIn = false;
function route(session) {
  const inApp = !!session;
  $('#login').hidden = inApp; $('#app').hidden = !inApp;
  if (inApp && !routedIn) {
    routedIn = true;
    loadMarkets();
    refresh();
    S.timer = setInterval(refresh, POLL_MS);
  } else if (!inApp) {
    routedIn = false;
    clearInterval(S.timer);
  }
}

$('#loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('#loginMsg').textContent = '';
  const { error } = await sb.auth.signInWithPassword({ email: $('#email').value.trim(), password: $('#password').value });
  if (error) $('#loginMsg').textContent = error.message;
});
$('#signOut').addEventListener('click', () => sb.auth.signOut());

// ---------- Data ----------
async function loadMarkets() {
  const all = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await sb.from('markets').select('symbol,base,min_cost').order('base').range(from, from + 999);
    if (error) { toast('Could not load Kraken coin list: ' + error.message, true); return; }
    all.push(...data);
    if (data.length < 1000) break;
  }
  S.markets = all;
  $('#marketList').innerHTML = all.map(m => `<option value="${esc(m.base)}">${esc(m.symbol)}</option>`).join('');
  if (!all.length) $('#addMsg').textContent = 'The coin list is empty. It fills in once the bot is running with the new code.';
}

async function refresh() {
  try {
    const [st, as, ps, tr, rz] = await Promise.all([
      sb.from('settings').select('*').eq('id', 1).single(),
      sb.from('assets').select('*').order('created_at'),
      sb.from('positions').select('*'),
      sb.from('trades').select('*').order('created_at', { ascending: false }).limit(400),
      sb.from('trades').select('pnl_usd,paper').eq('side', 'sell'),
    ]);
    for (const r of [st, as, ps, tr, rz]) if (r.error) throw r.error;
    S.settings = st.data;
    S.assets = as.data;
    S.positions = Object.fromEntries(ps.data.map(p => [p.asset_id, p]));
    S.trades = tr.data;
    S.realized = { paper: 0, live: 0 };
    for (const t of rz.data) S.realized[t.paper ? 'paper' : 'live'] += num(t.pnl_usd) || 0;
    render();
  } catch (err) {
    toast('Could not reach Supabase: ' + (err.message || err), true);
  }
}

// ---------- Render ----------
function colorMap() {
  const m = {}; S.assets.forEach((a, i) => { m[a.id] = COLORS[i % COLORS.length]; }); return m;
}

function render() {
  renderHeader();
  renderPortfolio();
  const active = document.activeElement;
  if (!(active && active.closest('#assets') && active.tagName === 'INPUT')) renderAssets();
}

function renderHeader() {
  const mode = S.settings?.mode || 'paper';
  document.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  const hb = S.settings?.bot_heartbeat;
  const fresh = hb && (Date.now() - new Date(hb).getTime()) < BOT_POLL_SECONDS * 4 * 1000;
  $('#botStatus').innerHTML = hb
    ? `<span class="dot ${fresh ? 'on' : 'off'}"></span><span>${fresh ? 'Bot running' : 'Bot offline, last seen ' + ago(hb)}</span>`
    : `<span class="dot off"></span><span>Bot hasn't checked in yet</span>`;
}

function renderPortfolio() {
  const colors = colorMap();
  const mode = S.settings?.mode || 'paper';
  let unrealized = 0;
  const rows = S.assets.map(a => {
    const p = S.positions[a.id], last = num(a.last_price);
    let value = 0, kind = null;
    if (p) {
      value = last ? num(p.amount) * last : num(p.cost_usd);
      unrealized += value - num(p.cost_usd);
      kind = 'held';
    } else if (a.status !== 'inactive') {
      value = num(a.capital_usd); kind = 'cash';
    }
    return { a, value, kind, c: colors[a.id] };
  }).filter(r => r.value > 0);
  const total = rows.reduce((s, r) => s + r.value, 0);
  const realized = S.realized[mode];

  $('#stats').innerHTML = `
    <div class="stat"><div class="v">${usd(total)}</div><div class="k">Portfolio value</div></div>
    <div class="stat"><div class="v ${tone(unrealized)}">${signedUsd(unrealized)}</div><div class="k">Unrealized</div></div>
    <div class="stat"><div class="v ${tone(realized)}">${signedUsd(realized)}</div><div class="k">Realized gains, ${mode} trades</div></div>`;

  $('#band').innerHTML = total > 0
    ? rows.map(r => `<div class="s ${r.kind}" style="--c:${r.c};width:${(r.value / total * 100).toFixed(3)}%" title="${esc(r.a.symbol)} ${usd(r.value)}"></div>`).join('')
    : `<div class="band-empty">Add a coin below to start building your portfolio.</div>`;

  $('#legend').innerHTML = rows.length ? rows.map(r => `
    <span><i class="${r.kind}" style="--c:${r.c}"></i>${esc(r.a.symbol.split('/')[0])}
    ${usd(r.value)} <em>${(r.value / total * 100).toFixed(1)}%, ${r.kind === 'held' ? 'held' : 'cash waiting for a dip'}</em></span>`).join('') : '';
}

function stateOf(a, p) {
  const mode = S.settings?.mode || 'paper';
  if (a.status !== 'inactive' && mode === 'live' && !a.live_confirmed) return ['waiting', 'Waiting for live confirmation'];
  if (a.status === 'pending_start') return ['watching', 'Starting, buying on next check'];
  if (a.status === 'inactive') return ['', p ? 'Stopped, still holding' : 'Stopped'];
  if (p) return ['holding', 'Holding'];
  return a.perpetual ? ['watching', 'Watching for a dip'] : ['', 'Finishing'];
}

function railHtml(a, p) {
  const last = num(a.last_price);
  if (last === null) return `<p class="rail-note" style="color:var(--muted)">Waiting for the first price from the bot.</p>`;
  if (p) {
    const entry = num(p.entry_price), target = entry * (1 + num(a.sell_gain_pct) / 100), lo = entry - (target - entry);
    const pos = clamp((last - lo) / (target - lo)), change = (last / entry - 1) * 100, toGo = (target / last - 1) * 100;
    return `<div class="rail">
      <div class="track"><span class="tick" style="left:50%"></span><span class="mark ${tone(change)}" style="left:${pos * 100}%"></span></div>
      <div class="rail-labels"><span>Entry ${price(entry)}</span><span>Sells at ${price(target)}</span></div>
      <p class="rail-note"><span class="${tone(change)}">${pct(change)}</span> since entry, ${toGo > 0 ? toGo.toFixed(2) + '% to go' : 'target reached, selling on next check'}</p>
    </div>`;
  }
  if (a.status === 'inactive') return '';
  const high = num(a.rolling_high) ?? last, buyAt = high * (1 - num(a.buy_dip_pct) / 100);
  const pos = clamp((last - buyAt) / (high - buyAt || 1)), away = (last / buyAt - 1) * 100;
  return `<div class="rail">
    <div class="track"><span class="fill" style="width:${pos * 100}%"></span><span class="mark" style="left:${pos * 100}%"></span></div>
    <div class="rail-labels"><span>Buys at ${price(buyAt)}</span><span>Recent high ${price(high)}</span></div>
    <p class="rail-note">${away > 0 ? away.toFixed(2) + '% above the buy point' : 'At the buy point, buying on next check'}</p>
  </div>`;
}

function historyHtml(a) {
  const rows = S.trades.filter(t => t.asset_id === a.id).slice(0, 25);
  if (!rows.length) return `<p class="rail-note" style="color:var(--muted)">No trades yet.</p>`;
  return `<div class="hist-wrap"><table class="hist">
    <thead><tr><th>When</th><th>Side</th><th>Price</th><th>Amount</th><th>Value</th><th>P&amp;L</th><th></th></tr></thead>
    <tbody>${rows.map(t => {
      const pnl = num(t.pnl_usd);
      return `<tr>
        <td>${new Date(t.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
        <td>${t.side === 'buy' ? 'Buy' : 'Sell'}${t.reason === 'manual' ? ' (manual)' : ''}</td>
        <td>${price(num(t.price))}</td>
        <td>${Number(t.amount).toPrecision(6)}</td>
        <td>${usd(num(t.usd_value))}</td>
        <td class="${pnl === null ? '' : tone(pnl)}">${pnl === null ? '' : signedUsd(pnl) + ' (' + pct(num(t.pnl_pct)) + ')'}</td>
        <td><span class="tag ${t.paper ? '' : 'live'}">${t.paper ? 'paper' : 'live'}</span></td>
      </tr>`;
    }).join('')}</tbody></table></div>`;
}

function renderAssets() {
  const colors = colorMap();
  const mode = S.settings?.mode || 'paper';
  if (!S.assets.length) {
    $('#assets').innerHTML = `<div class="empty">No coins yet. Add one above and the bot picks it up within ${BOT_POLL_SECONDS} seconds.</div>`;
    return;
  }
  $('#assets').innerHTML = S.assets.map(a => {
    const p = S.positions[a.id], last = num(a.last_price), d = S.drafts[a.id] || {};
    const [stClass, stText] = stateOf(a, p);
    const value = p && last ? num(p.amount) * last : null;
    const unreal = value !== null ? value - num(p.cost_usd) : null;
    const base = a.symbol.split('/')[0];
    const needsConfirm = mode === 'live' && !a.live_confirmed && a.status !== 'inactive';
    const resumeLabel = (!p && !a.perpetual) ? 'Buy &amp; start again' : 'Resume';

    return `<article class="panel asset" style="--c:${colors[a.id]}" data-id="${a.id}">
      <div class="asset-head">
        <h3>${esc(base)} <small>/USD</small></h3>
        <span class="state ${stClass}">${stText}</span>
        <div class="seg" role="group" aria-label="Duration for ${esc(base)}">
          <button type="button" data-act="perpetual" aria-pressed="${a.perpetual}">Perpetual</button>
          <button type="button" data-act="onetime" aria-pressed="${!a.perpetual}">One-time</button>
        </div>
      </div>
      ${railHtml(a, p)}
      <dl class="facts">
        <div><dt>Price</dt><dd>${price(last)}</dd></div>
        <div><dt>Entry</dt><dd>${p ? price(num(p.entry_price)) : '—'}</dd></div>
        <div><dt>Unrealized</dt><dd class="${unreal === null ? '' : tone(unreal)}">${unreal === null ? '—' : signedUsd(unreal)}</dd></div>
        <div><dt>Allocated</dt><dd>${usd(num(a.capital_usd))}</dd></div>
        <div><dt>Deployed</dt><dd>${p ? usd(num(p.cost_usd)) : '$0.00'}</dd></div>
        <div><dt>Realized</dt><dd class="${tone(num(a.realized_pnl))}">${signedUsd(num(a.realized_pnl))}</dd></div>
      </dl>
      <div class="controls">
        <label class="f cap">Capital (USD)<input class="in" type="number" min="1" step="1" data-field="capital" value="${esc(d.capital ?? a.capital_usd)}"></label>
        <label class="f">Dip to buy (%)<input class="in" type="number" min="0.1" step="0.1" data-field="dip" value="${esc(d.dip ?? a.buy_dip_pct)}"></label>
        <label class="f">Gain to sell (%)<input class="in" type="number" min="0.1" step="0.1" data-field="gain" value="${esc(d.gain ?? a.sell_gain_pct)}"></label>
        <button type="button" class="btn save" data-act="save"${S.drafts[a.id] ? '' : ' hidden'}>Save changes</button>
        <span class="spacer"></span>
        ${needsConfirm ? `<button type="button" class="btn go" data-act="confirmlive">Confirm live trading</button>` : ''}
        ${p ? `<button type="button" class="btn" data-act="sell"${a.command === 'sell_now' ? ' disabled' : ''}>${a.command === 'sell_now' ? 'Selling…' : 'Sell now'}</button>` : ''}
        ${a.status === 'inactive'
          ? `<button type="button" class="btn" data-act="resume">${resumeLabel}</button>`
          : `<button type="button" class="btn" data-act="deactivate">Stop</button>`}
        ${!p ? `<button type="button" class="btn danger" data-act="remove">Remove</button>` : ''}
      </div>
      ${a.last_error ? `<p class="err">${esc(a.last_error)}</p>` : ''}
      <details data-hist="${a.id}"${S.openHistory.has(a.id) ? ' open' : ''}><summary>Trade history</summary>${historyHtml(a)}</details>
    </article>`;
  }).join('');
}

// ---------- Actions ----------
async function updateAsset(id, fields, doneMsg) {
  const { error } = await sb.from('assets').update({ ...fields, updated_at: new Date().toISOString() }).eq('id', id);
  if (error) { toast(error.message, true); return false; }
  if (doneMsg) toast(doneMsg);
  await refresh();
  return true;
}

$('#assets').addEventListener('input', e => {
  const f = e.target.dataset.field; if (!f) return;
  const id = e.target.closest('[data-id]').dataset.id;
  S.drafts[id] = { ...(S.drafts[id] || {}), [f]: e.target.value };
  e.target.closest('.asset').querySelector('[data-act="save"]').hidden = false;
});
$('#assets').addEventListener('toggle', e => {
  const id = e.target.dataset?.hist; if (!id) return;
  e.target.open ? S.openHistory.add(id) : S.openHistory.delete(id);
}, true);

$('#assets').addEventListener('click', async e => {
  const btn = e.target.closest('[data-act]'); if (!btn) return;
  const id = btn.closest('[data-id]').dataset.id;
  const a = S.assets.find(x => x.id === id); if (!a) return;
  const p = S.positions[id], base = a.symbol.split('/')[0];
  const live = (S.settings?.mode || 'paper') === 'live';

  switch (btn.dataset.act) {
    case 'perpetual': {
      if (a.perpetual) return;
      const f = { perpetual: true };
      if (a.status === 'inactive') { f.status = 'active'; if (!p) f.rolling_high = null; }
      return updateAsset(id, f, `${base} is perpetual now`);
    }
    case 'onetime':
      if (!a.perpetual) return;
      return updateAsset(id, { perpetual: false },
        p ? `${base} will sell at its target, then stop` : `${base} will stop and not buy again`);
    case 'save': {
      const d = S.drafts[id] || {};
      const capital = Number(d.capital ?? a.capital_usd), dip = Number(d.dip ?? a.buy_dip_pct), gain = Number(d.gain ?? a.sell_gain_pct);
      if (!(capital > 0) || !(dip > 0) || !(gain > 0)) return toast('Capital, dip and gain all need to be above 0.', true);
      const f = { capital_usd: capital, buy_dip_pct: dip, sell_gain_pct: gain };
      if (capital !== num(a.capital_usd)) f.live_confirmed = false;
      delete S.drafts[id];
      return updateAsset(id, f, `Saved ${base}` + (f.live_confirmed === false && live ? '. Confirm live trading again to continue.' : ''));
    }
    case 'sell':
      if (!confirm(`Sell all ${base} now at market price?` + (!p.paper ? ' This is a real sell on Kraken.' : ''))) return;
      return updateAsset(id, { command: 'sell_now' }, `Selling ${base} on the next check`);
    case 'deactivate':
      if (!confirm(`Stop trading ${base}?` + (p ? ' It keeps what it holds. Use Sell now if you want out.' : ''))) return;
      return updateAsset(id, { status: 'inactive', live_confirmed: false }, `Stopped ${base}`);
    case 'resume': {
      const f = (!p && !a.perpetual) ? { status: 'pending_start' } : { status: 'active', ...(p ? {} : { rolling_high: null }) };
      return updateAsset(id, f, live ? `${base} resumed. Confirm live trading to let it trade.` : `Resumed ${base}`);
    }
    case 'confirmlive':
      if (!confirm(`Start live trading ${base} with ${usd(num(a.capital_usd))} of real money? Trades for ${base} run automatically after this.`)) return;
      return updateAsset(id, { live_confirmed: true }, `${base} is trading live`);
    case 'remove': {
      if (!confirm(`Remove ${base} from your list? Its trade history stays in Supabase.`)) return;
      const { error } = await sb.from('assets').delete().eq('id', id);
      if (error) return toast(error.message, true);
      toast(`Removed ${base}`); return refresh();
    }
  }
});

// Mode switch
document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', async () => {
  const mode = b.dataset.mode;
  if (mode === S.settings?.mode) return;
  if (mode === 'live' && !confirm('Switch to live trading? New buys use real money. Each coin needs a one-time confirmation before its first live trade. Paper holdings still close as paper.')) return;
  const { error } = await sb.from('settings').update({ mode, updated_at: new Date().toISOString() }).eq('id', 1);
  if (error) return toast(error.message, true);
  toast(mode === 'live' ? 'Live mode on' : 'Paper mode on');
  refresh();
}));

// ---------- Add a coin ----------
document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => {
  const [dip, gain] = b.dataset.preset.split(',');
  $('#dip').value = dip; $('#gain').value = gain;
}));
document.querySelectorAll('[data-perp]').forEach(b => b.addEventListener('click', () => {
  S.addPerpetual = b.dataset.perp === 'true';
  document.querySelectorAll('[data-perp]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  $('#addMsg').textContent = '';
}));
['#ticker', '#capital', '#dip', '#gain'].forEach(s => $(s).addEventListener('input', () => { $('#addMsg').textContent = ''; }));

function resolveMarket(raw) {
  let q = raw.trim().toUpperCase();
  if (!q) return null;
  if (q === 'XBT') q = 'BTC';
  return S.markets.find(m => m.symbol === q || m.symbol === q + '/USD' || m.base === q) || null;
}

$('#addForm').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = $('#addMsg');
  const m = resolveMarket($('#ticker').value);
  const capital = Number($('#capital').value), dip = Number($('#dip').value), gain = Number($('#gain').value);

  if (!$('#ticker').value.trim()) return msg.textContent = 'Enter a coin, for example ETH.';
  if (!m) return msg.textContent = `Kraken doesn't have a USD pair for "${$('#ticker').value.trim()}". Pick one from the list.`;
  if (S.assets.some(a => a.symbol === m.symbol)) return msg.textContent = `${m.base} is already in your list. Change it in its card below.`;
  if (!(capital > 0)) return msg.textContent = 'Enter how much capital to put into this coin.';
  if (m.min_cost && capital < num(m.min_cost)) return msg.textContent = `Kraken's minimum order for ${m.base} is $${m.min_cost}.`;
  if (!(dip > 0) || !(gain > 0)) return msg.textContent = 'Dip and gain need to be above 0.';
  if (S.addPerpetual === null) return msg.textContent = 'Choose Perpetual or One-time.';

  const live = (S.settings?.mode || 'paper') === 'live';
  if (live && !confirm(`This buys ${usd(capital)} of ${m.base} on Kraken with real money. Trades for ${m.base} run automatically after this.`)) return;

  $('#addBtn').disabled = true;
  const { error } = await sb.from('assets').insert({
    symbol: m.symbol, capital_usd: capital, buy_dip_pct: dip, sell_gain_pct: gain,
    perpetual: S.addPerpetual, status: 'pending_start', live_confirmed: live,
  });
  $('#addBtn').disabled = false;
  if (error) return msg.textContent = error.message;

  toast(`${m.base} added. The bot buys on its next check.`);
  $('#ticker').value = ''; $('#capital').value = '';
  S.addPerpetual = null;
  document.querySelectorAll('[data-perp]').forEach(x => x.setAttribute('aria-pressed', 'false'));
  refresh();
});
</script>
</body>
</html>