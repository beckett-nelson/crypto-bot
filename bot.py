import os
import time
import traceback
from datetime import datetime, timezone

import ccxt
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '15'))
MARKET_REFRESH_SECONDS = 6 * 60 * 60

exchange = ccxt.kraken({
    'apiKey': os.getenv('KRAKEN_API_KEY'),
    'secret': os.getenv('KRAKEN_SECRET'),
    'enableRateLimit': True,
})
sb = create_client(os.environ['https://xsuwbwisaobneimlogmw.supabase.co'], os.environ['eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhzdXdid2lzYW9ibmVpbWxvZ213Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTk1NTgyMCwiZXhwIjoyMTA1NTMxODIwfQ.YvxiaMM6ayJhNUJ4sIUijncv3lkSEwYiqFXnwa2uYj0'])


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {msg}", flush=True)


# ---------- Markets ----------

def sync_markets():
    """Write every active Kraken spot USD pair to Supabase so the dashboard can validate tickers."""
    markets = exchange.load_markets(reload=True)
    rows = []
    for m in markets.values():
        if m.get('spot') and m.get('quote') == 'USD' and m.get('active') is not False:
            limits = m.get('limits') or {}
            rows.append({
                'symbol': m['symbol'],
                'base': m['base'],
                'quote': m['quote'],
                'min_amount': (limits.get('amount') or {}).get('min'),
                'min_cost': (limits.get('cost') or {}).get('min'),
                'updated_at': now_iso(),
            })
    for i in range(0, len(rows), 500):
        sb.table('markets').upsert(rows[i:i + 500]).execute()
    log(f"Synced {len(rows)} Kraken USD markets")


def check_minimums(symbol, amount, price):
    limits = exchange.market(symbol).get('limits') or {}
    min_amount = (limits.get('amount') or {}).get('min')
    min_cost = (limits.get('cost') or {}).get('min')
    if amount <= 0 or (min_amount and amount < min_amount):
        raise ValueError(f"Order too small: {amount} is below Kraken's minimum of {min_amount} for {symbol}")
    if min_cost and amount * price < min_cost:
        raise ValueError(f"Order too small: ${amount * price:.2f} is below Kraken's minimum of ${min_cost} for {symbol}")


# ---------- Orders ----------

def execute(side, symbol, amount, price, paper):
    """Returns (fill_price, filled_amount). Paper mode simulates a fill at the current price."""
    amount = float(exchange.amount_to_precision(symbol, amount))
    check_minimums(symbol, amount, price)
    if paper:
        return price, amount

    if side == 'buy':
        order = exchange.create_market_buy_order(symbol, amount)
    else:
        order = exchange.create_market_sell_order(symbol, amount)
    try:
        order = exchange.fetch_order(order['id'], symbol)
    except Exception:
        pass
    fill_price = order.get('average') or order.get('price') or price
    filled = order.get('filled') or amount
    return float(fill_price), float(filled)


def open_position(asset, price, paper, reason):
    symbol = asset['symbol']
    fill_price, filled = execute('buy', symbol, float(asset['capital_usd']) / price, price, paper)
    cost = fill_price * filled

    sb.table('positions').insert({
        'asset_id': asset['id'],
        'symbol': symbol,
        'entry_price': fill_price,
        'amount': filled,
        'cost_usd': cost,
        'paper': paper,
    }).execute()
    sb.table('trades').insert({
        'asset_id': asset['id'],
        'symbol': symbol,
        'side': 'buy',
        'price': fill_price,
        'amount': filled,
        'usd_value': cost,
        'paper': paper,
        'reason': reason,
    }).execute()

    log(f"{'[PAPER] ' if paper else ''}BUY {filled:.6f} {symbol} at {fill_price:.4f} ({reason})")
    return {}


def close_position(asset, pos, price, reason):
    """Sells in the same mode the position was opened in, so paper holdings never trigger real sells."""
    symbol = asset['symbol']
    paper = pos['paper']
    fill_price, filled = execute('sell', symbol, float(pos['amount']), price, paper)
    proceeds = fill_price * filled
    cost = float(pos['cost_usd'])
    pnl = proceeds - cost
    pnl_pct = (pnl / cost * 100) if cost else 0

    sb.table('positions').delete().eq('asset_id', asset['id']).execute()
    sb.table('trades').insert({
        'asset_id': asset['id'],
        'symbol': symbol,
        'side': 'sell',
        'price': fill_price,
        'amount': filled,
        'usd_value': proceeds,
        'pnl_usd': pnl,
        'pnl_pct': pnl_pct,
        'paper': paper,
        'reason': reason,
    }).execute()

    log(f"{'[PAPER] ' if paper else ''}SELL {filled:.6f} {symbol} at {fill_price:.4f} "
        f"P&L ${pnl:.2f} ({pnl_pct:.2f}%) ({reason})")

    updates = {
        'realized_pnl': float(asset['realized_pnl'] or 0) + pnl,
        'rolling_high': fill_price,
    }
    if not asset['perpetual']:
        updates['status'] = 'inactive'  # one-time: sold, don't buy back
    return updates


# ---------- Per-asset logic ----------

def handle_asset(a, pos, tickers, mode):
    ticker = tickers.get(a['symbol'])
    if not ticker or not ticker.get('last'):
        raise ValueError(f"No price from Kraken for {a['symbol']}")
    price = float(ticker['last'])
    paper = mode == 'paper'
    upd = {'last_price': price, 'last_error': None, 'updated_at': now_iso()}

    def save():
        sb.table('assets').update(upd).eq('id', a['id']).execute()

    # Manual "sell now" works in any state
    if a['command'] == 'sell_now':
        upd['command'] = None
        if pos:
            upd.update(close_position(a, pos, price, 'manual'))
        return save()

    # Stopped: just keep the price fresh
    if a['status'] == 'inactive':
        return save()

    # Live mode: wait for the one-time confirmation from the dashboard
    if not paper and not a['live_confirmed']:
        return save()

    # New asset: initial buy right away
    if a['status'] == 'pending_start':
        if pos is None:
            upd.update(open_position(a, price, paper, 'initial'))
        upd['status'] = 'active'
        return save()

    # Active asset
    if pos:
        target = float(pos['entry_price']) * (1 + float(a['sell_gain_pct']) / 100)
        if price >= target:
            upd.update(close_position(a, pos, price, 'target'))
    elif not a['perpetual']:
        upd['status'] = 'inactive'  # one-time and nothing held: stop
    else:
        high = max(float(a['rolling_high'] or price), price)
        upd['rolling_high'] = high
        if price <= high * (1 - float(a['buy_dip_pct']) / 100):
            upd.update(open_position(a, price, paper, 'dip'))

    save()


def cycle(mode):
    assets = sb.table('assets').select('*').execute().data
    if not assets:
        return
    positions = {p['asset_id']: p for p in sb.table('positions').select('*').execute().data}
    tickers = exchange.fetch_tickers(sorted({a['symbol'] for a in assets}))

    for a in assets:
        try:
            handle_asset(a, positions.get(a['id']), tickers, mode)
        except Exception as e:
            log(f"{a['symbol']} error: {e}")
            sb.table('assets').update({'last_error': str(e)[:500]}).eq('id', a['id']).execute()


def main():
    log(f"Bot starting, polling every {POLL_INTERVAL_SECONDS}s")
    last_sync = 0
    while True:
        try:
            if time.time() - last_sync > MARKET_REFRESH_SECONDS:
                sync_markets()
                last_sync = time.time()
            settings = sb.table('settings').select('*').eq('id', 1).single().execute().data
            cycle(settings['mode'])
            sb.table('settings').update({'bot_heartbeat': now_iso()}).eq('id', 1).execute()
        except Exception as e:
            log(f"Cycle error: {e}")
            traceback.print_exc()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == '__main__':
    main()