import os
import asyncio
import logging
import json
import aiohttp
import hmac
import hashlib
import time
from urllib.parse import urlencode
from binance.client import Client
from binance.enums import *
from binance.helpers import round_step_size
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Binance API credentials from environment variables
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET').encode()

# Trading parameters
TRADE_SYMBOL = 'BONKUSDT'
ORDER_AMOUNT_USDT = 100  # Fixed amount to spend on each buy order
ORDER_BOOK_DEPTH = 20  # Top 20 levels of order book
MIN_PROFIT_MARGIN = 0.0044  # 0.44% to cover 0.11% buy fee, 0.11% sell fee, and 0.22% profit margin
DECIMAL_PRECISION = 2  # Decimal precision for order quantity
COOLDOWN_PERIOD = 60  # Cooldown period in seconds (1 minute)
SAFETY_PROFIT_THRESHOLD = 0.0044  # Safety profit threshold set to 0.44%
TRADE_FEE_PERCENT = 0.0011  # 0.11% trade fee per transaction

# Initialize Binance client
client = Client(API_KEY, API_SECRET.decode())

# Data structures
order_book = {
    'bids': [],
    'asks': []
}

position_open = False  # Track if there is an open position
order_id = None  # Track the current open order ID
last_sell_time = 0  # Track the time of the last sell order
historical_prices = []  # Track historical prices for moving average calculation
buy_price = 0  # Track the buy price for the current position
current_sell_price = 0  # Track the current sell price
ma_crossed = False  # Track if the MA has crossed up

async def get_server_time_diff(session):
    """Get the server time difference."""
    url = 'https://api.binance.com/api/v3/time'
    async with session.get(url) as response:
        server_time = await response.json()
        local_time = int(asyncio.get_event_loop().time() * 1000)
        return server_time['serverTime'] - local_time

def create_signed_payload(params, recv_window=5000):
    """Create a signed payload for the API request."""
    params['recvWindow'] = recv_window
    query_string = urlencode(params)
    signature = hmac.new(API_SECRET, query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature
    return params

def update_order_book(data):
    """Update the order book with the latest data."""
    global order_book
    order_book['bids'] = sorted([(float(price), float(quantity)) for price, quantity in data['bids']], key=lambda x: -x[0])
    order_book['asks'] = sorted([(float(price), float(quantity)) for price, quantity in data['asks']], key=lambda x: x[0])
    logger.info("Order book updated")

async def get_account_balance(session, asset, time_diff, retries=3):
    """Get the current account balance for the given asset."""
    url = 'https://api.binance.com/api/v3/account'
    headers = {'X-MBX-APIKEY': API_KEY}
    params = {'timestamp': int(asyncio.get_event_loop().time() * 1000) + time_diff}
    signed_params = create_signed_payload(params)
    for attempt in range(retries):
        async with session.get(url, headers=headers, params=signed_params) as response:
            account_info = await response.json()
            if 'balances' in account_info:
                for balance in account_info['balances']:
                    if balance['asset'] == asset:
                        return float(balance['free'])
            logger.error(f"Error fetching account balance: {account_info}")
            if 'code' in account_info and account_info['code'] == -1021:
                time_diff = await get_server_time_diff(session)
    return 0.0

async def get_exchange_info(session):
    """Fetch exchange information for the trading pair."""
    url = 'https://api.binance.com/api/v3/exchangeInfo'
    async with session.get(url) as response:
        exchange_info = await response.json()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == TRADE_SYMBOL:
                min_lot_size, tick_size = None, None
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        min_lot_size = float(filter_info['minQty'])
                    if filter_info['filterType'] == 'PRICE_FILTER':
                        tick_size = float(filter_info['tickSize'])
                return min_lot_size, tick_size
    return None, None

async def get_historical_prices(session, symbol, interval, limit=100):
    """Fetch historical price data."""
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
    async with session.get(url) as response:
        klines = await response.json()
        closing_prices = [float(kline[4]) for kline in klines]
        logger.info(f"Fetched {len(closing_prices)} historical prices")
        return closing_prices

def calculate_moving_averages(prices, window):
    """Calculate moving averages."""
    return np.convolve(prices, np.ones(window), 'valid') / window

def calculate_fees(amount, price):
    """Calculate trading fees."""
    fee = amount * price * TRADE_FEE_PERCENT
    return fee

def calculate_min_sell_price(buy_price, amount):
    """Calculate the minimum sell price to cover fees and profit margin."""
    buy_fee = calculate_fees(amount, buy_price)
    sell_fee = calculate_fees(amount, buy_price * (1 + MIN_PROFIT_MARGIN))
    min_sell_price = buy_price + buy_fee / amount + sell_fee / amount + buy_price * MIN_PROFIT_MARGIN
    return min_sell_price

def round_quantity(quantity, step_size):
    """Round the quantity according to the step size."""
    return round_step_size(quantity, step_size)

async def place_buy_order(session, time_diff, min_lot_size, tick_size):
    """Place a buy order with a fixed USDT amount."""
    global position_open, order_id, last_sell_time, historical_prices, buy_price, current_sell_price, ma_crossed
    current_time = time.time()
    if position_open or (current_time - last_sell_time < COOLDOWN_PERIOD) or ma_crossed:
        logger.info("Skipping buy order due to open position, cooldown period, or MA cross")
        return

    if len(historical_prices) < 30:
        logger.info("Not enough data to calculate moving averages")
        return
    ma3 = calculate_moving_averages(historical_prices[-30:], 3)
    ma6 = calculate_moving_averages(historical_prices[-30:], 6)
    logger.info(f"MA3: {ma3[-1]}, MA6: {ma6[-1]}")
    if ma3[-1] <= ma6[-1]:
        logger.info("MA3 has not crossed above MA6, skipping buy order")
        return

    if not order_book['bids'] or not order_book['asks']:
        return
    best_bid = order_book['bids'][0][0]

    buy_price = best_bid
    min_sell_price = calculate_min_sell_price(buy_price, ORDER_AMOUNT_USDT / buy_price)
    potential_profit = ((min_sell_price - buy_price) / buy_price) * 100

    if potential_profit < (MIN_PROFIT_MARGIN * 100):
        logger.info("Potential profit is less than the minimum profit margin, skipping buy order")
        return

    quantity = ORDER_AMOUNT_USDT / buy_price
    quantity = round_quantity(quantity, tick_size)
    quantity = "{:.8f}".format(quantity).rstrip('0').rstrip('.')  # Ensure quantity has correct precision
    if float(quantity) < min_lot_size:
        logger.error(f"Calculated quantity {quantity} is less than minimum lot size {min_lot_size}")
        return
    url = 'https://api.binance.com/api/v3/order'
    params = {
        'symbol': TRADE_SYMBOL,
        'side': SIDE_BUY,
        'type': ORDER_TYPE_LIMIT,
        'timeInForce': TIME_IN_FORCE_GTC,
        'quantity': quantity,
        'price': f"{buy_price:.8f}".rstrip('0').rstrip('.'),  # Ensure price has correct precision
        'timestamp': int(asyncio.get_event_loop().time() * 1000) + time_diff
    }
    signed_params = create_signed_payload(params)
    headers = {'X-MBX-APIKEY': API_KEY}
    async with session.post(url, headers=headers, params=signed_params) as response:
        order = await response.json()
        if 'code' in order:
            logger.error(f"Error placing buy order: {order}")
        else:
            logger.info(f"Buy order placed: {order}")
            position_open = True  # Update the position status
            order_id = order['orderId']  # Store the order ID
            current_sell_price = order_book['asks'][0][0]  # Initial sell price based on best ask
            ma_crossed = True  # Set the MA cross flag
        return order

async def place_sell_order(session, time_diff, min_lot_size, tick_size, sell_price=None):
    """Place a sell order for all available quantity."""
    global position_open, order_id, last_sell_time, buy_price, ma_crossed
    asset = TRADE_SYMBOL.replace('USDT', '')
    quantity = await get_account_balance(session, asset, time_diff)
    if quantity <= 0:
        return
    quantity = round_quantity(quantity, tick_size)
    quantity = "{:.8f}".format(quantity).rstrip('0').rstrip('.')  # Ensure quantity has correct precision
    if float(quantity) < min_lot_size:
        logger.error(f"Calculated quantity {quantity} is less than minimum lot size {min_lot_size}")
        return
    if not order_book['bids']:
        logger.error("Order book is empty, cannot place sell order")
        return

    best_bid = order_book['bids'][0][0]
    min_sell_price = calculate_min_sell_price(buy_price, float(quantity))
    if sell_price is None:
        if best_bid > min_sell_price:
            sell_price = best_bid
        else:
            sell_price = min_sell_price
        sell_price = round_quantity(sell_price, tick_size)
    elif sell_price < min_sell_price:
        sell_price = min_sell_price

    url = 'https://api.binance.com/api/v3/order'
    params = {
        'symbol': TRADE_SYMBOL,
        'side': SIDE_SELL,
        'type': ORDER_TYPE_LIMIT,
        'timeInForce': TIME_IN_FORCE_GTC,
        'quantity': quantity,
        'price': f"{sell_price:.8f}".rstrip('0').rstrip('.'),  # Ensure price has correct precision
        'timestamp': int(asyncio.get_event_loop().time() * 1000) + time_diff
    }
    signed_params = create_signed_payload(params)
    headers = {'X-MBX-APIKEY': API_KEY}
    async with session.post(url, headers=headers, params=signed_params) as response:
        order = await response.json()
        if 'code' in order:
            logger.error(f"Error placing sell order: {order}")
        else:
            logger.info(f"Sell order placed: {order}")
            position_open = False  # Update the position status
            order_id = None  # Reset the order ID
            last_sell_time = time.time()  # Update the last sell time
            ma_crossed = False  # Reset the MA cross flag after a sell order is executed
        return order

async def check_open_order(session, time_diff):
    """Check if there is an open order."""
    global order_id, position_open
    if not order_id:
        return
    url = 'https://api.binance.com/api/v3/order'
    params = {
        'symbol': TRADE_SYMBOL,
        'orderId': order_id,
        'timestamp': int(asyncio.get_event_loop().time() * 1000) + time_diff
    }
    signed_params = create_signed_payload(params)
    headers = {'X-MBX-APIKEY': API_KEY}
    async with session.get(url, headers=headers, params=signed_params) as response:
        order = await response.json()
        if 'status' in order and order['status'] in ['FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']:
            position_open = False
            order_id = None
        else:
            position_open = True

async def check_break_even_sell_order(session, time_diff, min_lot_size, tick_size):
    """Check for break-even sell order."""
    global position_open, buy_price
    if not position_open or buy_price == 0:
        return
    if not order_book['bids']:
        logger.error("Order book is empty, cannot check break-even sell order")
        return

    best_bid = order_book['bids'][0][0]
    current_profit = ((best_bid - buy_price) / buy_price) * 100

    min_sell_price = calculate_min_sell_price(buy_price, await get_account_balance(session, TRADE_SYMBOL.replace('USDT', ''), time_diff))
    if current_profit <= SAFETY_PROFIT_THRESHOLD:
        logger.info("Potential profit is diminishing, placing a sell order at 0.44% profit")
        await place_sell_order(session, time_diff, min_lot_size, tick_size, sell_price=min_sell_price)

async def scalping_strategy(session, time_diff, min_lot_size, tick_size):
    """Scalping strategy main logic."""
    await check_open_order(session, time_diff)
    await check_break_even_sell_order(session, time_diff, min_lot_size, tick_size)
    await place_sell_order(session, time_diff, min_lot_size, tick_size)
    await place_buy_order(session, time_diff, min_lot_size, tick_size)

async def handle_socket_msg(session, msg, time_diff, min_lot_size, tick_size):
    """Handle incoming websocket messages."""
    if msg['e'] == 'depthUpdate':
        update_order_book({
            'bids': msg['b'],
            'asks': msg['a']
        })
        await scalping_strategy(session, time_diff, min_lot_size, tick_size)

async def listen_to_depth_stream(session, time_diff, min_lot_size, tick_size):
    """Websocket listener for order book depth stream."""
    url = f'wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@depth'
    async with session.ws_connect(url) as ws:
        async for msg in ws:
            msg_data = json.loads(msg.data)
            await handle_socket_msg(session, msg_data, time_diff, min_lot_size, tick_size)

async def main():
    """Main execution loop."""
    async with aiohttp.ClientSession() as session:
        time_diff = await get_server_time_diff(session)
        min_lot_size, tick_size = await get_exchange_info(session)
        historical_prices.extend(await get_historical_prices(session, TRADE_SYMBOL, '3m'))
        await listen_to_depth_stream(session, time_diff, min_lot_size, tick_size)

if __name__ == '__main__':
    asyncio.run(main())
