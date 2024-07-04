This script is an automated trading bot designed to trade the BONKUSDT pair on the Binance exchange. It uses a scalping strategy based on moving average (MA) crossovers to identify buy opportunities and employs a sell strategy that aims to maximize profit while also having safety measures to minimize losses.

Key Components
Libraries and Setup:

The script uses various libraries including os, asyncio, logging, json, aiohttp, hmac, hashlib, time, and numpy.
Binance API client is initialized using the binance.client.Client.
Logging is configured to output information and error messages.
Global Variables:

API Credentials: Loaded from environment variables.
Trading Parameters: Define trading behaviors such as TRADE_SYMBOL, ORDER_AMOUNT_USDT, MIN_PROFIT_MARGIN, COOLDOWN_PERIOD, SAFETY_PROFIT_THRESHOLD, and TRADE_FEE_PERCENT.
Data Structures: Hold the order book data and track the current trading position and historical prices.
Helper Functions:

get_server_time_diff: Calculates the time difference between the local machine and Binance server.
create_signed_payload: Generates a signed payload for secure API requests.
update_order_book: Updates the global order book with the latest data.
get_account_balance: Retrieves the account balance for a specified asset.
get_exchange_info: Fetches the exchange information to determine minimum lot size and tick size for orders.
get_historical_prices: Fetches historical closing prices for the specified trading pair.
calculate_moving_averages: Calculates moving averages for a given list of prices.
calculate_fees: Calculates trading fees based on the trade amount and price.
calculate_min_sell_price: Determines the minimum sell price required to cover fees and achieve the desired profit margin.
round_quantity: Rounds the order quantity to the nearest valid increment.
Trading Logic:

place_buy_order: Places a buy order if conditions are met:
No existing open position.
Cooldown period has passed.
MA3 has crossed above MA6.
Potential profit meets or exceeds the minimum profit margin.
place_sell_order: Places a sell order for the current position:
Attempts to sell at the best available bid price.
Ensures the sell price covers fees and meets the minimum profit margin.
Resets flags and updates position status after selling.
check_open_order: Checks if there is an existing open order and updates the position status.
check_break_even_sell_order: Places a sell order at break-even price if the potential profit drops below the safety threshold.
WebSocket and Main Execution Loop:

handle_socket_msg: Handles incoming WebSocket messages to update the order book and execute the trading strategy.
listen_to_depth_stream: Listens to the order book depth stream and processes incoming data.
main: The main function that initializes the session, retrieves initial data, and starts the WebSocket listener.
How It Works
Initialization:

The script initializes global variables and sets up logging.
It connects to the Binance API using the provided API key and secret.
Fetching Initial Data:

The script retrieves the server time difference, exchange information, and historical prices for the specified trading pair (BONKUSDT).
Listening to WebSocket:

The script listens to the order book depth stream for the specified trading pair.
It continuously updates the order book and processes new data to decide on trading actions.
Trading Strategy:

When MA3 crosses above MA6 and the potential profit meets the minimum profit margin, the script places a buy order.
It monitors the position and places a sell order either at the desired profit target or at break-even if the profit potential diminishes.
Ensures only one buy order per MA crossover and manages cooldown periods between trades.
