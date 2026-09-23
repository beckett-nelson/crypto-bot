"""
kraken_client.py — shared plumbing for the Auto Trader.

Both bot.py (spot) and margin_bot.py (leverage) import from here so the
exchange connection, Supabase connection, logging, fee math and market
data live in exactly one place.

Nothing in this file places an order. It only reads.
"""

import os
import time
import traceback
from datetime import datetime, timezone

import ccxt
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


# ---------------------------------------------------------------- fees
# Kraken Pro fee schedule at the entry volume tier (<$10k 30-day volume).
# These are what paper mode charges so simulated P&L matches reality.
# Check https://www.kraken.com/features/fee-schedule if your volume grows.

TAKER_FEE = 0.0026          # 0.26% — market orders pay this
MAKER_FEE = 0.0016          # 0.16% — limit orders that rest on the book
MARGIN_OPEN_FEE = 0.0002    # 0.02% — charged once when a margin position opens
MARGIN_ROLLOVER_FEE = 0.0002  # 0.02% — charged every 4h a margin position stays open
ROLLOVER_SECONDS = 4 * 60 * 60

# Kraken liquidates a margin position when your equity falls to 40% of the
# initial margin requirement. So you lose 60% of your margin before liquidation.
MAINTENANCE_MARGIN_RATIO = 0.40
LIQUIDATION_LOSS_FRACTION = 1.0 - MAINTENANCE_MARGIN_RATIO  # 0.60


# ---------------------------------------------------------------- logging

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(msg, prefix=""):
    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
    tag = f"[{prefix}] " if prefix else ""
    print(f"{stamp} {tag}{msg}", flush=True)


def log_error(msg, exc=None, prefix=""):
    log(f"ERROR: {msg}", prefix)
    if exc is not None:
        traceback.print_exc()


# ---------------------------------------------------------------- clients

_exchange = None
_supabase = None


def get_exchange():
    """Single shared ccxt Kraken instance. Markets are loaded on first use."""
    global _exchange
    if _exchange is None:
        _exchange = ccxt.kraken({
            "apiKey": os.getenv("KRAKEN_API_KEY"),
            "secret": os.getenv("KRAKEN_SECRET"),
            "enableRateLimit": True,
            "options": {"adjustForTimeDifference": True},
        })
        _exchange.load_markets()
        log(f"Kraken client ready — {len(_exchange.markets)} markets loaded")
    return _exchange


def get_supabase():
    """Single shared Supabase client using the service key (bypasses RLS)."""
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------- prices

def fetch_price(symbol):
    """Last traded price for a symbol, or None if the call fails."""
    try:
        ticker = get_exchange().fetch_ticker(symbol)
        return ticker.get("last") or ticker.get("close")
    except Exception as e:
        log_error(f"price fetch failed for {symbol}: {e}")
        return None


def fetch_prices(symbols):
    """Prices for several symbols at once. Returns {symbol: price}, skipping failures."""
    out = {}
    ex = get_exchange()
    try:
        tickers = ex.fetch_tickers(list(symbols))
        for sym, t in tickers.items():
            price = t.get("last") or t.get("close")
            if price:
                out[sym] = price
    except Exception:
        # Kraken occasionally rejects bulk ticker calls; fall back one by one.
        for sym in symbols:
            price = fetch_price(sym)
            if price:
                out[sym] = price
            time.sleep(ex.rateLimit / 1000)
    return out


def moving_average(symbol, period=50, timeframe="5m"):
    """
    Simple moving average of closing prices — the trend filter.

    Returns None if there isn't enough history, which callers should treat
    as "no opinion" rather than "bad trend".
    """
    try:
        candles = get_exchange().fetch_ohlcv(symbol, timeframe=timeframe, limit=period + 1)
        if not candles or len(candles) < period:
            return None
        closes = [c[4] for c in candles[-period:]]
        return sum(closes) / len(closes)
    except Exception as e:
        log_error(f"OHLCV fetch failed for {symbol}: {e}")
        return None


def trend_is_up(symbol, period=50, timeframe="5m"):
    """
    True when price sits above its moving average (uptrend — favours longs),
    False when below (downtrend — favours shorts),
    None when we can't tell.
    """
    ma = moving_average(symbol, period, timeframe)
    price = fetch_price(symbol)
    if ma is None or price is None:
        return None
    return price > ma


# ---------------------------------------------------------------- markets

def market_info(symbol):
    """ccxt market dict for a symbol, or None if Kraken doesn't list it."""
    return get_exchange().markets.get(symbol)


def max_leverage(symbol, side="long"):
    """
    Highest leverage Kraken allows on this pair, per its own market data.
    Returns 1 when the pair has no margin support at all.
    """
    m = market_info(symbol)
    if not m:
        return 1
    info = m.get("info", {})
    key = "leverage_buy" if side == "long" else "leverage_sell"
    levels = info.get(key) or []
    try:
        numeric = [int(float(x)) for x in levels]
    except (TypeError, ValueError):
        return 1
    return max(numeric) if numeric else 1


def margin_allowed(symbol, side="long"):
    return max_leverage(symbol, side) > 1


def round_amount(symbol, amount):
    """Round an order size to the pair's precision so Kraken doesn't reject it."""
    try:
        return float(get_exchange().amount_to_precision(symbol, amount))
    except Exception:
        return round(amount, 8)


def meets_minimums(symbol, amount, price):
    """
    Checks a prospective order against Kraken's minimum size and cost.
    Returns (ok: bool, reason: str).
    """
    m = market_info(symbol)
    if not m:
        return False, f"{symbol} is not a Kraken market"

    limits = m.get("limits", {})
    min_amount = (limits.get("amount") or {}).get("min")
    min_cost = (limits.get("cost") or {}).get("min")

    if min_amount and amount < min_amount:
        return False, f"size {amount:.8f} below Kraken minimum {min_amount}"
    if min_cost and amount * price < min_cost:
        return False, f"order value ${amount * price:.2f} below Kraken minimum ${min_cost}"
    return True, ""


def sync_margin_markets():
    """
    Write every Kraken USD pair that supports margin into the `markets` table,
    with its max long/short leverage, so the dashboard can offer a valid
    ticker list and cap the leverage dropdown per coin.
    """
    ex = get_exchange()
    sb = get_supabase()
    rows = []

    for symbol, m in ex.markets.items():
        if not m.get("active") or m.get("quote") != "USD" or m.get("type") != "spot":
            continue
        long_lev = max_leverage(symbol, "long")
        short_lev = max_leverage(symbol, "short")
        if long_lev <= 1 and short_lev <= 1:
            continue
        limits = m.get("limits", {})
        rows.append({
            "symbol": symbol,
            "base": m.get("base"),
            "quote": m.get("quote"),
            "max_leverage_long": long_lev,
            "max_leverage_short": short_lev,
            "min_amount": (limits.get("amount") or {}).get("min"),
            "min_cost": (limits.get("cost") or {}).get("min"),
            "updated_at": now_iso(),
        })

    if rows:
        sb.table("margin_markets").upsert(rows, on_conflict="symbol").execute()
    log(f"Synced {len(rows)} margin-enabled Kraken USD markets")
    return len(rows)


# ---------------------------------------------------------------- margin math

def liquidation_price(entry_price, leverage, side):
    """
    Estimated price at which Kraken liquidates the position.

    You lose 60% of your posted margin before liquidation, and your margin is
    1/leverage of the notional — so the move that kills you is
    0.60 / leverage away from entry.

    This is an estimate. Rollover fees and funding push the real level closer,
    which is exactly why the stop-loss needs a safety buffer inside it.
    """
    distance = LIQUIDATION_LOSS_FRACTION / leverage
    if side == "long":
        return entry_price * (1 - distance)
    return entry_price * (1 + distance)


def max_safe_stop_pct(leverage, buffer=0.7):
    """
    Widest stop-loss (in % of entry price) that still triggers comfortably
    before liquidation. `buffer` keeps the stop at 70% of the distance to
    liquidation by default, leaving room for fees and a gappy fill.

    At 20x: liquidation is ~3.0% away, so the widest safe stop is ~2.1%.
    At 5x:  liquidation is ~12.0% away, widest safe stop ~8.4%.
    """
    return (LIQUIDATION_LOSS_FRACTION / leverage) * buffer * 100


def unrealized_pnl(entry_price, current_price, amount, side):
    """P&L in USD on an open position, before fees."""
    if side == "long":
        return (current_price - entry_price) * amount
    return (entry_price - current_price) * amount


def pnl_pct_on_margin(entry_price, current_price, leverage, side):
    """
    P&L as a percent of *your own money*, not the notional.
    A 1% move against a 20x long is a 20% loss of your margin.
    """
    if side == "long":
        move = (current_price - entry_price) / entry_price
    else:
        move = (entry_price - current_price) / entry_price
    return move * leverage * 100


def rollover_fees_owed(notional_usd, opened_at_ts, now_ts=None):
    """Accumulated 4-hourly rollover fees on an open margin position."""
    now_ts = now_ts or time.time()
    periods = int((now_ts - opened_at_ts) // ROLLOVER_SECONDS)
    return notional_usd * MARGIN_ROLLOVER_FEE * max(periods, 0)


# ---------------------------------------------------------------- settings

def get_mode():
    """Global 'paper' or 'live' switch from the settings table. Defaults to paper."""
    try:
        res = get_supabase().table("settings").select("margin_mode").eq("id", 1).single().execute()
        return (res.data or {}).get("margin_mode") or "paper"
    except Exception as e:
        log_error(f"could not read mode, defaulting to paper: {e}")
        return "paper"


def heartbeat(field="margin_heartbeat"):
    """Stamp the settings row so the dashboard can show the bot is alive."""
    try:
        get_supabase().table("settings").update({field: now_iso()}).eq("id", 1).execute()
    except Exception as e:
        log_error(f"heartbeat failed: {e}")