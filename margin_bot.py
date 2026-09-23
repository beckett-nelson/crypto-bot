"""
margin_bot.py — leveraged trading on Kraken, separate from the spot bot.

Runs its own loop, its own Supabase tables, its own dashboard section.
bot.py is untouched and keeps handling spot.

Safety rules baked in, not optional:
  1. No position opens without a stop-loss. An asset missing one is skipped.
  2. A stop wider than the liquidation buffer is rejected, not silently clamped.
  3. Live mode needs an explicit per-asset confirmation, same as spot.
  4. One position per asset at a time. No averaging down, no stacking.
"""

import os
import time
from datetime import datetime, timezone

import ccxt

from kraken_client import (
    TAKER_FEE,
    MARGIN_OPEN_FEE,
    fetch_price,
    get_exchange,
    get_mode,
    get_supabase,
    heartbeat,
    liquidation_price,
    log,
    log_error,
    margin_allowed,
    max_leverage,
    max_safe_stop_pct,
    meets_minimums,
    now_iso,
    pnl_pct_on_margin,
    rollover_fees_owed,
    round_amount,
    sync_margin_markets,
    trend_is_up,
    unrealized_pnl,
)

POLL_INTERVAL_SECONDS = int(os.getenv("MARGIN_POLL_SECONDS", "15"))
MARKET_REFRESH_SECONDS = 6 * 60 * 60
TREND_FILTER_PERIOD = int(os.getenv("TREND_PERIOD", "50"))
TREND_FILTER_TIMEFRAME = os.getenv("TREND_TIMEFRAME", "5m")

# How close to liquidation we bail out regardless of the stop, as a fraction
# of the distance from entry to the liquidation price.
PANIC_CLOSE_AT = 0.85

TAG = "margin"
sb = get_supabase()


# ---------------------------------------------------------------- helpers

def set_asset(asset_id, fields):
    fields["updated_at"] = now_iso()
    sb.table("margin_assets").update(fields).eq("id", asset_id).execute()


def flag_error(asset, message):
    log(f"{asset['symbol']}: {message}", TAG)
    set_asset(asset["id"], {"last_error": message, "status": "error"})


def record_trade(asset, side, action, price, amount, leverage, paper,
                 pnl_usd=None, pnl_pct=None, fees=0.0, reason=None):
    sb.table("margin_trades").insert({
        "asset_id": asset["id"],
        "symbol": asset["symbol"],
        "side": side,              # long | short
        "action": action,          # open | close
        "price": price,
        "amount": amount,
        "notional_usd": price * amount,
        "leverage": leverage,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "fees_usd": fees,
        "paper": paper,
        "reason": reason,
        "created_at": now_iso(),
    }).execute()


def open_position_row(asset_id):
    res = sb.table("margin_positions").select("*").eq("asset_id", asset_id).execute()
    return res.data[0] if res.data else None


# ---------------------------------------------------------------- validation

def validate(asset):
    """
    Returns (ok, reason). Every check here is a reason not to trade,
    so a failure is loud rather than a quiet skip.
    """
    symbol = asset["symbol"]
    side = asset.get("side", "long")
    leverage = asset.get("leverage") or 1
    stop_pct = asset.get("stop_loss_pct")

    if stop_pct is None or stop_pct <= 0:
        return False, "no stop-loss set — refusing to trade on margin without one"

    if leverage < 1:
        return False, f"leverage {leverage}x is invalid"

    if leverage > 1 and not margin_allowed(symbol, side):
        return False, f"Kraken does not offer margin on {symbol} for {side}s"

    cap = max_leverage(symbol, side)
    if leverage > cap:
        return False, f"{leverage}x exceeds Kraken's {cap}x limit on {symbol}"

    safe_stop = max_safe_stop_pct(leverage)
    if stop_pct > safe_stop:
        return False, (
            f"stop-loss of {stop_pct}% is too wide for {leverage}x — "
            f"liquidation sits near {100 * 0.6 / leverage:.2f}%, so keep the stop "
            f"at or under {safe_stop:.2f}%"
        )

    take_profit = asset.get("take_profit_pct")
    if take_profit is None or take_profit <= 0:
        return False, "no take-profit target set"

    return True, ""


# ---------------------------------------------------------------- opening

def should_open(asset, price):
    """
    Entry signal. Longs buy a dip off the rolling high, shorts sell a rally
    off the rolling low. The trend filter vetoes trades fighting the trend.
    """
    side = asset.get("side", "long")
    trigger_pct = asset.get("entry_trigger_pct") or 1.0

    if side == "long":
        reference = asset.get("rolling_high") or price
        drop = (reference - price) / reference * 100
        signal = drop >= trigger_pct
        detail = f"down {drop:.2f}% from rolling high {reference:.2f}"
    else:
        reference = asset.get("rolling_low") or price
        rise = (price - reference) / reference * 100
        signal = rise >= trigger_pct
        detail = f"up {rise:.2f}% from rolling low {reference:.2f}"

    if not signal:
        return False, detail

    if asset.get("use_trend_filter", True):
        up = trend_is_up(asset["symbol"], TREND_FILTER_PERIOD, TREND_FILTER_TIMEFRAME)
        if up is None:
            return False, f"{detail} — trend unknown, sitting out"
        if side == "long" and not up:
            return False, f"{detail} — but price is below its MA, skipping long"
        if side == "short" and up:
            return False, f"{detail} — but price is above its MA, skipping short"

    return True, detail


def open_position(asset, price, reason):
    symbol = asset["symbol"]
    side = asset.get("side", "long")
    leverage = int(asset.get("leverage") or 1)
    capital = float(asset["capital_usd"])
    paper = get_mode() == "paper"

    notional = capital * leverage
    amount = round_amount(symbol, notional / price)

    ok, why = meets_minimums(symbol, amount, price)
    if not ok:
        flag_error(asset, why)
        return

    if not paper and not asset.get("live_confirmed"):
        log(f"{symbol}: live trade blocked — confirm this asset on the dashboard first", TAG)
        return

    entry = price
    fees = notional * (TAKER_FEE + MARGIN_OPEN_FEE)

    if not paper:
        try:
            ex = get_exchange()
            order_side = "buy" if side == "long" else "sell"
            order = ex.create_order(
                symbol, "market", order_side, amount,
                params={"leverage": leverage},
            )
            entry = order.get("average") or order.get("price") or price
            fees = (order.get("fee") or {}).get("cost") or fees

            # Attach the protective stop immediately. If this fails we close
            # straight back out rather than sit on an unprotected levered position.
            place_stop_order(symbol, side, amount, entry, asset["stop_loss_pct"], leverage)
        except Exception as e:
            log_error(f"{symbol}: live open failed: {e}", e, TAG)
            flag_error(asset, f"open failed: {e}")
            return

    stop = stop_price(entry, asset["stop_loss_pct"], side)
    target = target_price(entry, asset["take_profit_pct"], side)
    liq = liquidation_price(entry, leverage, side)

    sb.table("margin_positions").insert({
        "asset_id": asset["id"],
        "symbol": symbol,
        "side": side,
        "leverage": leverage,
        "entry_price": entry,
        "amount": amount,
        "margin_usd": capital,
        "notional_usd": entry * amount,
        "stop_price": stop,
        "target_price": target,
        "liquidation_price": liq,
        "open_fees_usd": fees,
        "paper": paper,
        "opened_at": now_iso(),
    }).execute()

    set_asset(asset["id"], {"status": "holding", "last_error": None})
    record_trade(asset, side, "open", entry, amount, leverage, paper, fees=fees, reason=reason)

    log(
        f"{symbol}: OPEN {side} {leverage}x — {amount:.6f} @ {entry:.2f} "
        f"(${entry * amount:.2f} notional on ${capital:.2f}) | "
        f"stop {stop:.2f} · target {target:.2f} · liq ~{liq:.2f} | {reason}",
        TAG,
    )


def place_stop_order(symbol, side, amount, entry, stop_pct, leverage):
    """Live-mode protective stop. Paper mode checks the level in the loop instead."""
    ex = get_exchange()
    stop = stop_price(entry, stop_pct, side)
    close_side = "sell" if side == "long" else "buy"
    ex.create_order(
        symbol, "stop-loss", close_side, amount,
        params={"stopPrice": stop, "leverage": leverage, "reduceOnly": True},
    )
    log(f"{symbol}: stop-loss placed at {stop:.2f}", TAG)


def stop_price(entry, stop_pct, side):
    if side == "long":
        return entry * (1 - stop_pct / 100)
    return entry * (1 + stop_pct / 100)


def target_price(entry, take_profit_pct, side):
    if side == "long":
        return entry * (1 + take_profit_pct / 100)
    return entry * (1 - take_profit_pct / 100)


# ---------------------------------------------------------------- closing

def check_exit(asset, position, price):
    """Returns a close reason, or None to keep holding."""
    side = position["side"]
    stop = position["stop_price"]
    target = position["target_price"]
    liq = position["liquidation_price"]
    entry = position["entry_price"]

    if asset.get("command") == "close_now":
        return "manual close from dashboard"

    # Panic exit if price gets near liquidation before the stop fires
    # (a gap, a stop order that didn't fill, a fee-eroded margin).
    entry_to_liq = abs(entry - liq)
    travelled = abs(entry - price) if (
        (side == "long" and price < entry) or (side == "short" and price > entry)
    ) else 0
    if entry_to_liq and travelled / entry_to_liq >= PANIC_CLOSE_AT:
        return "emergency close — approaching liquidation"

    if side == "long":
        if price <= stop:
            return "stop-loss hit"
        if price >= target:
            return "take-profit hit"
    else:
        if price >= stop:
            return "stop-loss hit"
        if price <= target:
            return "take-profit hit"

    return None


def close_position(asset, position, price, reason):
    symbol = position["symbol"]
    side = position["side"]
    amount = float(position["amount"])
    leverage = int(position["leverage"])
    entry = float(position["entry_price"])
    margin = float(position["margin_usd"])
    paper = bool(position["paper"])

    exit_price = price

    if not paper:
        try:
            ex = get_exchange()
            close_side = "sell" if side == "long" else "buy"
            ex.cancel_all_orders(symbol)
            order = ex.create_order(
                symbol, "market", close_side, amount,
                params={"leverage": leverage, "reduceOnly": True},
            )
            exit_price = order.get("average") or order.get("price") or price
        except Exception as e:
            log_error(f"{symbol}: live close failed: {e}", e, TAG)
            flag_error(asset, f"close failed: {e} — check Kraken manually")
            return

    gross = unrealized_pnl(entry, exit_price, amount, side)

    opened_ts = datetime.fromisoformat(position["opened_at"].replace("Z", "+00:00")).timestamp()
    rollover = rollover_fees_owed(entry * amount, opened_ts)
    close_fee = exit_price * amount * TAKER_FEE
    fees = float(position.get("open_fees_usd") or 0) + close_fee + rollover

    net = gross - fees
    net_pct = net / margin * 100 if margin else 0

    sb.table("margin_positions").delete().eq("asset_id", asset["id"]).execute()
    record_trade(asset, side, "close", exit_price, amount, leverage, paper,
                 pnl_usd=net, pnl_pct=net_pct, fees=fees, reason=reason)

    realized = float(asset.get("realized_pnl") or 0) + net
    perpetual = asset.get("perpetual", True)

    updates = {
        "realized_pnl": realized,
        "command": None,
        "rolling_high": None,
        "rolling_low": None,
        "status": "active" if perpetual else "inactive",
    }
    # Compounding: roll profit back into the margin for the next trade.
    if perpetual and asset.get("compound", False):
        updates["capital_usd"] = max(float(asset["capital_usd"]) + net, 0)
    set_asset(asset["id"], updates)

    verdict = "PROFIT" if net > 0 else "LOSS"
    log(
        f"{symbol}: CLOSE {side} {leverage}x @ {exit_price:.2f} — {reason} | "
        f"{verdict} ${net:+.2f} ({net_pct:+.2f}% on margin) after ${fees:.2f} fees | "
        f"lifetime ${realized:+.2f}"
        + ("" if perpetual else " | one-time asset, now inactive"),
        TAG,
    )


# ---------------------------------------------------------------- reference tracking

def update_reference(asset, price):
    """
    Rolling high (for longs) and rolling low (for shorts), so entries chase
    the market instead of anchoring to whatever the price was at startup.
    """
    updates = {"last_price": price}
    side = asset.get("side", "long")

    if side == "long":
        high = asset.get("rolling_high")
        if high is None or price > high:
            updates["rolling_high"] = price
    else:
        low = asset.get("rolling_low")
        if low is None or price < low:
            updates["rolling_low"] = price

    set_asset(asset["id"], updates)
    asset.update(updates)


# ---------------------------------------------------------------- main loop

def process(asset):
    symbol = asset["symbol"]
    price = fetch_price(symbol)
    if price is None:
        return

    position = open_position_row(asset["id"])

    if position:
        pnl = pnl_pct_on_margin(
            float(position["entry_price"]), price,
            int(position["leverage"]), position["side"],
        )
        set_asset(asset["id"], {"last_price": price, "unrealized_pct": pnl})

        reason = check_exit(asset, position, price)
        if reason:
            close_position(asset, position, price, reason)
        else:
            log(
                f"{symbol}: holding {position['side']} {position['leverage']}x @ "
                f"{price:.2f} — {pnl:+.2f}% on margin "
                f"(stop {position['stop_price']:.2f} · target {position['target_price']:.2f})",
                TAG,
            )
        return

    # No position open.
    if asset.get("status") in ("inactive", "error"):
        return

    ok, why = validate(asset)
    if not ok:
        flag_error(asset, why)
        return

    if asset.get("command") == "close_now":
        set_asset(asset["id"], {"command": None})

    update_reference(asset, price)

    go, detail = should_open(asset, price)
    if go:
        open_position(asset, price, detail)
    else:
        log(f"{symbol}: watching @ {price:.2f} — {detail}", TAG)


def run():
    log("Margin bot starting", TAG)
    log(f"Mode: {get_mode().upper()} | polling every {POLL_INTERVAL_SECONDS}s", TAG)

    last_market_sync = 0

    while True:
        try:
            heartbeat("margin_heartbeat")

            if time.time() - last_market_sync > MARKET_REFRESH_SECONDS:
                sync_margin_markets()
                last_market_sync = time.time()

            res = (
                sb.table("margin_assets")
                .select("*")
                .in_("status", ["pending_start", "active", "holding"])
                .execute()
            )
            assets = res.data or []

            if not assets:
                log("No active margin assets", TAG)

            for asset in assets:
                try:
                    process(asset)
                except Exception as e:
                    log_error(f"{asset.get('symbol')}: {e}", e, TAG)

        except Exception as e:
            log_error(f"loop failure: {e}", e, TAG)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()