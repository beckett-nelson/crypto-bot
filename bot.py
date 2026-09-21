import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.kraken({
    'apiKey': os.getenv('KRAKEN_API_KEY'),
    'secret': os.getenv('KRAKEN_SECRET'),
})

# ---- CONFIG ----
DRY_RUN = True  # True = simulate only, no real orders
POLL_INTERVAL_SECONDS = 30

SYMBOLS = {
    'ETH/USD': {'buy_dip_pct': 1.0, 'sell_gain_pct': 1.0, 'trade_amount_usd': 25},
    'SOL/USD': {'buy_dip_pct': 1.5, 'sell_gain_pct': 1.5, 'trade_amount_usd': 25},
}
# ----------------

state = {}
for symbol in SYMBOLS:
    state[symbol] = {
        'rolling_high': None,     # highest price seen since last position closed
        'position': None,         # None = no holding, else {'entry_price', 'amount'}
    }

def get_price(symbol):
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']

def place_buy(symbol, price, amount_usd):
    amount = amount_usd / price
    if DRY_RUN:
        print(f"[DRY RUN] Would BUY {amount:.6f} {symbol} at {price:.2f}")
    else:
        exchange.create_market_buy_order(symbol, amount)
        print(f"BOUGHT {amount:.6f} {symbol} at {price:.2f}")
    return amount

def place_sell(symbol, price, amount):
    if DRY_RUN:
        print(f"[DRY RUN] Would SELL {amount:.6f} {symbol} at {price:.2f}")
    else:
        exchange.create_market_sell_order(symbol, amount)
        print(f"SOLD {amount:.6f} {symbol} at {price:.2f}")

def run():
    print(f"Starting bot | DRY_RUN={DRY_RUN}")

    for symbol in SYMBOLS:
        state[symbol]['rolling_high'] = get_price(symbol)
        print(f"{symbol} initial rolling high: {state[symbol]['rolling_high']:.2f}")

    while True:
        for symbol, cfg in SYMBOLS.items():
            try:
                price = get_price(symbol)
                s = state[symbol]

                if s['position'] is None:
                    # update rolling high whenever we see a new peak
                    if price > s['rolling_high']:
                        s['rolling_high'] = price

                    dip_target = s['rolling_high'] * (1 - cfg['buy_dip_pct'] / 100)
                    if price <= dip_target:
                        amount = place_buy(symbol, price, cfg['trade_amount_usd'])
                        s['position'] = {'entry_price': price, 'amount': amount}
                    else:
                        print(f"{symbol}: {price:.2f} | high {s['rolling_high']:.2f} | dip target {dip_target:.2f}")

                else:
                    entry = s['position']['entry_price']
                    gain_target = entry * (1 + cfg['sell_gain_pct'] / 100)
                    if price >= gain_target:
                        place_sell(symbol, price, s['position']['amount'])
                        s['position'] = None
                        s['rolling_high'] = price  # start tracking fresh from here
                    else:
                        print(f"{symbol}: holding, entry {entry:.2f} | target {gain_target:.2f} | now {price:.2f}")

            except Exception as e:
                print(f"Error on {symbol}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == '__main__':
    run()