import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.kraken({
    'apiKey': os.getenv('KRAKEN_API_KEY'),
    'secret': os.getenv('KRAKEN_SECRET'),
})

balance = exchange.fetch_balance()
print(balance['total'])