# BONK-USDT-ORDER-BOOK-TRADER

# Binance Trading Bot

This script is an automated trading bot for the Binance exchange. It uses a scalping strategy to maximize profits while minimizing risks by analyzing the order book and placing buy and sell orders accordingly.

## Features
- Places buy orders based on moving average crossover strategy
- Ensures minimum profit margin to cover trading fees and earn profit
- Places safety sell orders to avoid losses when prices drop
- Cooldown period between trades to avoid frequent trading

## Requirements
- Python 3.7 or higher
- aiohttp
- numpy
- binance

## Installation

1. Clone the repository or download the script.
2. Install the required Python packages:
    ```
    pip install aiohttp numpy python-binance
    ```

## Configuration

1. Set up your Binance API credentials in your environment variables:
    ```
    export BINANCE_API_KEY='your_api_key'
    export BINANCE_API_SECRET='your_api_secret'
    ```

## Usage

Run the script using Python:
```
python trading_bot.py
```

## Script Explanation

### Parameters

- `TRADE_SYMBOL`: The trading pair symbol (e.g., 'BONKUSDT').
- `ORDER_AMOUNT_USDT`: The fixed amount in USDT to spend on each buy order.
- `ORDER_BOOK_DEPTH`: The depth of the order book to consider.
- `MIN_PROFIT_MARGIN`: The minimum profit margin required to place a sell order, accounting for trading fees.
- `DECIMAL_PRECISION`: The decimal precision for order quantity.
- `COOLDOWN_PERIOD`: The cooldown period in seconds between trades.
- `SAFETY_PROFIT_THRESHOLD`: The threshold profit margin for placing safety sell orders.
- `TRADE_FEE_PERCENT`: The trading fee percentage per transaction.

### Functions

- `get_server_time_diff(session)`: Gets the time difference between the server and local machine.
- `create_signed_payload(params, recv_window=5000)`: Creates a signed payload for authenticated requests.
- `update_order_book(data)`: Updates the order book with the latest data.
- `get_account_balance(session, asset, time_diff)`: Gets the current account balance for the given asset.
- `get_exchange_info(session)`: Fetches exchange information for the trading pair.
- `get_historical_prices(session, symbol, interval, limit=100)`: Fetches historical price data.
- `calculate_moving_averages(prices, window)`: Calculates moving averages.
- `calculate_fees(amount, price)`: Calculates the trading fees.
- `calculate_min_sell_price(buy_price, amount)`: Calculates the minimum sell price to cover fees and profit margin.
- `place_buy_order(session, time_diff, min_lot_size, tick_size)`: Places a buy order.
- `place_sell_order(session, time_diff, min_lot_size, tick_size, sell_price=None)`: Places a sell order.
- `check_open_order(session, time_diff)`: Checks if there is an open order.
- `check_break_even_sell_order(session, time_diff, min_lot_size, tick_size)`: Checks for break-even sell orders.
- `scalping_strategy(session, time_diff, min_lot_size, tick_size)`: Executes the scalping strategy.
- `handle_socket_msg(session, msg, time_diff, min_lot_size, tick_size)`: Handles incoming websocket messages.
- `listen_to_depth_stream(session, time_diff, min_lot_size, tick_size)`: Listens to the depth stream websocket.

## Disclaimer

This script is for educational purposes only. Trading cryptocurrencies involves significant risk and can result in substantial financial losses. Use this script at your own risk.
