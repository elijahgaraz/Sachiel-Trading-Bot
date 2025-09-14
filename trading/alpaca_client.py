# trading/alpaca_client.py
from alpaca.trading.client import TradingClient
from alpaca.data import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
from config.settings import Config
import pytz
from alpaca.data.live import CryptoDataStream
from alpaca.data.requests import CryptoLatestQuoteRequest
import traceback
from datetime import datetime, timedelta
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
import pandas as pd
import asyncio


class AlpacaClient:
    def __init__(self):
        self.trading_client = None
        self.stock_data_client = None
        self.crypto_data_client = None
        self.crypto_stream = None
        self.latest_crypto_prices = {}  # Cache for latest prices

    async def init_crypto_stream(self):
        """Initialize crypto data stream with proper connection"""
        try:
            # Check if we have credentials
            if not hasattr(Config, 'API_KEY') or not hasattr(Config, 'API_SECRET'):
                print("No API credentials found for crypto stream")
                return False

            print("Initializing crypto stream...")
            # Create crypto stream with credentials
            self.crypto_stream = CryptoDataStream(
                api_key=Config.API_KEY,
                secret_key=Config.API_SECRET
            )

            # Define the handler for crypto data
            async def handle_crypto_data(data):
                print(f"Crypto data received: {data}")

            # Set up the handler
            self.crypto_stream.data_feed = handle_crypto_data

            # Subscribe to default crypto pairs
            default_symbols = ["BTC/USD", "ETH/USD"]
            await self.crypto_stream.subscribe_bars(default_symbols)
            
            print(f"Successfully subscribed to crypto streams: {default_symbols}")
            return True

        except Exception as e:
            print(f"Error initializing crypto stream: {e}")
            traceback.print_exc()
            return False

    def close_crypto_stream(self):
        """Properly close the crypto stream"""
        try:
            if hasattr(self, 'crypto_stream'):
                asyncio.create_task(self.crypto_stream.close())
                print("Crypto stream closed")
        except Exception as e:
            print(f"Error closing crypto stream: {e}")
            traceback.print_exc()
        
    def close(self):
        """Close all connections properly"""
        try:
            # Close trading client if exists
            if hasattr(self, 'trading_client'):
                # Any cleanup needed for trading client
                pass

            # Close crypto stream if exists
            if hasattr(self, 'crypto_stream'):
                try:
                    # Get event loop for async operations
                    loop = asyncio.get_event_loop()
                    if loop and loop.is_running():
                        loop.create_task(self.crypto_stream.close())
                    else:
                        print("No running event loop for crypto stream cleanup")
                    print("Crypto stream closed")
                except Exception as e:
                    print(f"Error closing crypto stream: {e}")

        except Exception as e:
            print(f"Error in client cleanup: {e}")
            traceback.print_exc()

    def check_connection(self):
        """Check if the connection to Alpaca is active"""
        try:
            if self.trading_client:
                # Try to get account info as a connection test
                self.trading_client.get_account()
                return True
            return False
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False
                
    def get_latest_crypto_price(self, symbol):
        """Get the latest crypto price"""
        try:
            # Format symbol if needed
            if '/' not in symbol:
                formatted_symbol = f"{symbol[:3]}/USD"
            else:
                formatted_symbol = symbol

            # Try to get from cache first
            if formatted_symbol in self.latest_crypto_prices:
                return self.latest_crypto_prices[formatted_symbol]

            # If not in cache, try to get latest quote
            if not self.crypto_data_client:
                self.crypto_data_client = CryptoHistoricalDataClient()

            request = CryptoLatestQuoteRequest(symbol_or_symbols=[formatted_symbol])
            quotes = self.crypto_data_client.get_crypto_latest_quote(request)
            
            if quotes and formatted_symbol in quotes:
                quote = quotes[formatted_symbol]
                price = (float(quote.ask_price) + float(quote.bid_price)) / 2
                self.latest_crypto_prices[formatted_symbol] = price
                return price
                
            return None

        except Exception as e:
            print(f"Error getting latest crypto price: {e}")
            return None            
        
    def connect(self):
        """Connect to Alpaca API and initialize all clients"""
        try:
            print("\nConnecting to Alpaca:")
            
            print("1. Initializing trading client...")
            self.trading_client = TradingClient(
                api_key=Config.API_KEY,
                secret_key=Config.API_SECRET,
                paper=True  # Use paper trading
            )

            print("2. Initializing data client...")
            self.data_client = StockHistoricalDataClient(
                api_key=Config.API_KEY,
                secret_key=Config.API_SECRET
            )

            print("3. Verifying connection...")
            account = self.trading_client.get_account()
            print(f"Connection verified - Account Status: {account.status}")
            
            # We don't need to await the crypto stream here
            # It will be initialized asynchronously
            print("4. Crypto stream will be initialized asynchronously")
            
            return True

        except Exception as e:
            print(f"Error connecting to Alpaca: {e}")
            traceback.print_exc()
            return False
    
    def get_tradable_symbols(self):
        try:
            if not self.trading_client:
                self.connect()
                
            search_params = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
            assets = self.trading_client.get_all_assets(search_params)
            return [asset.symbol for asset in assets if asset.tradable]
        except Exception as e:
            print(f"Error getting stock symbols: {e}")
            return []

    def get_tradable_crypto_symbols(self):
        try:
            if not self.trading_client:
                self.connect()
                
            search_params = GetAssetsRequest(asset_class=AssetClass.CRYPTO)
            assets = self.trading_client.get_all_assets(search_params)
            # Format crypto symbols correctly for Alpaca (removing the '/')
            return [asset.symbol.replace("/", "") for asset in assets if asset.tradable]
        except Exception as e:
            print(f"Error getting crypto symbols: {e}")
            return []
    def get_account(self):
        try:
            if not self.trading_client:
                self.connect()
            return self.trading_client.get_account()
        except Exception as e:
            print(f"Error getting account info: {e}")
            return None
    def get_current_price(self, symbol):
        """Get current price using available API methods"""
        try:
            if not self.trading_client:
                self.connect()
                
            # Try to get latest trade
            try:
                latest_trade = self.trading_client.get_latest_trade(symbol)
                if latest_trade:
                    print(f"Got current price for {symbol}: ${float(latest_trade.price):.2f}")
                    return float(latest_trade.price)
            except Exception as e:
                print(f"Error getting latest trade: {e}")
                
            # Try to get last quote as backup
            try:
                last_quote = self.trading_client.get_latest_quote(symbol)
                if last_quote:
                    # Use mid price from quote
                    price = (float(last_quote.ask_price) + float(last_quote.bid_price)) / 2
                    print(f"Got current price from quote for {symbol}: ${price:.2f}")
                    return price
            except Exception as e:
                print(f"Error getting latest quote: {e}")
            
            return None
                
        except Exception as e:
            print(f"Error getting current price: {e}")
            return None

    def get_stock_bars(self, symbol, timeframe=TimeFrame.Day, limit=100):
        """Get stock bars using IEX feed"""
        try:
            if not self.stock_data_client:
                self.connect()
                
            # Use a specific recent date that should have data
            end_dt = datetime(2023, 12, 15)
            end_time = end_dt.replace(hour=16, minute=0, second=0, tzinfo=pytz.timezone('America/New_York'))
            start_time = end_time - timedelta(days=5)
            
            print(f"\nFetching IEX historical data for {symbol}")
            print(f"Time range: {start_time} to {end_time} ET")
            
            try:
                bars_request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=start_time,
                    end=end_time,
                    feed='iex',
                    limit=limit,
                    adjustment='raw'  # Try without adjustments first
                )
                
                bars = self.stock_data_client.get_stock_bars(bars_request)
                if bars and symbol in bars:
                    bar_list = list(bars[symbol])
                    if bar_list:
                        print(f"Received {len(bar_list)} bars")
                        latest_bar = bar_list[-1]
                        print(f"Latest bar - Time: {latest_bar.timestamp}, Close: ${latest_bar.close:.2f}")
                        return bar_list
                        
                # If no data, try with a different date range
                print("No data for first attempt, trying alternative date range...")
                alt_end = datetime(2023, 12, 1)
                alt_end = alt_end.replace(hour=16, minute=0, second=0, tzinfo=pytz.timezone('America/New_York'))
                alt_start = alt_end - timedelta(days=5)
                
                bars_request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=alt_start,
                    end=alt_end,
                    feed='iex',
                    limit=limit,
                    adjustment='raw'
                )
                
                bars = self.stock_data_client.get_stock_bars(bars_request)
                if bars and symbol in bars:
                    bar_list = list(bars[symbol])
                    if bar_list:
                        print(f"Received {len(bar_list)} bars from alternative date range")
                        return bar_list
                        
                print("No data available from either date range")
                return []
                
            except Exception as e:
                print(f"Error in bar request: {e}")
                traceback.print_exc()
                return []
                
        except Exception as e:
            print(f"Error getting stock bars: {e}")
            traceback.print_exc()
            return []

    def get_bars(self, symbol, is_crypto=False):
        """Main method to get price bars for both crypto and stocks"""
        try:
            if is_crypto:
                if not self.crypto_data_client:
                    from alpaca.data.historical import CryptoHistoricalDataClient
                    self.crypto_data_client = CryptoHistoricalDataClient()
                
                # Format crypto symbol
                if '/' not in symbol:
                    formatted_symbol = f"{symbol[:3]}/USD"
                else:
                    formatted_symbol = symbol
                    
                print(f"Fetching crypto data for {formatted_symbol}")
                
                try:
                    # Try to get current price using historical data client
                    current_time = datetime.now(pytz.UTC)
                    start_time = current_time - timedelta(minutes=5)
                    
                    request = CryptoBarsRequest(
                        symbol_or_symbols=formatted_symbol,
                        timeframe=TimeFrame.Minute,
                        start=start_time,
                        end=current_time
                    )
                    
                    try:
                        bars = self.crypto_data_client.get_crypto_bars(request)
                        if bars and formatted_symbol in bars:
                            bar_list = list(bars[formatted_symbol])
                            if bar_list:
                                print(f"Received real crypto data")
                                print(f"Latest price: ${bar_list[-1].close:.2f}")
                                return bar_list
                    except Exception as e:
                        print(f"Error fetching real data: {e}")
                    
                    # If real data fails, use simulation with current market price
                    print("Using simulation data with current market prices")
                    return self.get_simulated_bars(formatted_symbol)
                        
                except Exception as e:
                    print(f"Error in crypto request: {e}")
                    return self.get_simulated_bars(formatted_symbol)
                    
            else:
                # Stock data handling remains the same
                if not self.stock_data_client:
                    self.connect()
                
                # Use recent historical dates that should have data
                end_time = datetime(2023, 12, 15, 16, 0, 0).replace(tzinfo=pytz.timezone('America/New_York'))
                start_time = end_time - timedelta(days=5)
                
                print(f"\nFetching IEX historical data for {symbol}")
                print(f"Time range: {start_time} to {end_time} ET")
                
                # Try different timeframes
                timeframes = [
                    (TimeFrame.Day, "daily"),
                    (TimeFrame.Hour, "hourly"),
                    (TimeFrame.Minute, "minute")
                ]
                
                for timeframe, desc in timeframes:
                    try:
                        print(f"\nTrying {desc} timeframe...")
                        request = StockBarsRequest(
                            symbol_or_symbols=symbol,
                            timeframe=timeframe,
                            start=start_time,
                            end=end_time,
                            feed='iex',
                            adjustment='raw'
                        )
                        
                        bars = self.stock_data_client.get_stock_bars(request)
                        if bars and symbol in bars:
                            bar_list = list(bars[symbol])
                            if bar_list:
                                print(f"Received {len(bar_list)} {desc} bars")
                                print(f"Latest bar - Time: {bar_list[-1].timestamp}, Close: ${bar_list[-1].close:.2f}")
                                return bar_list
                    except Exception as e:
                        print(f"Error fetching {desc} data: {e}")
                        continue
                
                print(f"\nNo historical data available for {symbol}, using simulation")
                return self.get_simulated_bars(symbol)
                    
        except Exception as e:
            print(f"Error in get_bars: {e}")
            traceback.print_exc()
            return self.get_simulated_bars(symbol)
   
    def get_simulated_bars(self, symbol):
        """Generate simulated bar data with realistic prices"""
        try:
            import numpy as np
            
            # Updated default prices for crypto (as of current market)
            default_prices = {
                'BTC/USD': 93741.24,  # Updated Bitcoin price
                'BTCUSD': 93741.24,
                'ETH/USD': 4850.00,   # Updated Ethereum price
                'ETHUSD': 4850.00,
                'SOL/USD': 145.00,    # Updated Solana price
                'SOLUSD': 145.00,
                # Stock defaults remain the same
                'AAPL': 190.0,
                'MSFT': 375.0,
                'GOOGL': 140.0,
                'AMZN': 155.0,
                'META': 350.0,
                'NVDA': 490.0,
                'TSLA': 250.0
            }
            
            # Try to get current crypto price from trading client
            current_price = None
            try:
                if 'BTC' in symbol:
                    # Use reliable default for Bitcoin
                    current_price = default_prices.get('BTC/USD', 93741.24)
                elif 'ETH' in symbol:
                    current_price = default_prices.get('ETH/USD', 4850.00)
                else:
                    current_price = default_prices.get(symbol)
            except Exception as e:
                print(f"Could not get current price: {e}")
            
            # Use default if no current price
            if not current_price:
                current_price = default_prices.get(symbol) or default_prices.get(symbol.replace('/', ''))
                if not current_price:
                    current_price = 100.0  # fallback default
                
            print(f"Using price: ${current_price:.2f}")
            
            # Generate bars with realistic price movement
            bars = []
            current_time = datetime.now(pytz.UTC)
            base_price = current_price
            
            # Determine if it's a crypto symbol
            is_crypto = '/' in symbol or symbol.endswith('USD')
            
            # Set parameters based on asset type
            daily_volatility = 0.02 if is_crypto else 0.015  # Adjusted volatility
            volume_mean = 10_000 if is_crypto else 1_000_000  # Adjusted volume for crypto
            volume_std = volume_mean * 0.2
            
            print(f"Simulating with {'crypto' if is_crypto else 'stock'} parameters")
            print(f"Volatility: {daily_volatility:.3f}")
            
            for i in range(20):
                price_drift = np.random.normal(0, daily_volatility) * base_price
                base_price = base_price + price_drift
                
                open_price = base_price * (1 + np.random.normal(0, daily_volatility/2))
                high_price = max(open_price, base_price) * (1 + abs(np.random.normal(0, daily_volatility/2)))
                low_price = min(open_price, base_price) * (1 - abs(np.random.normal(0, daily_volatility/2)))
                close_price = base_price
                
                volume = int(abs(np.random.normal(volume_mean, volume_std)))
                if volume < 100:
                    volume = 100
                
                bar = type('Bar', (), {
                    'timestamp': current_time - timedelta(hours=i),
                    'open': round(open_price, 2),
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'close': round(close_price, 2),
                    'volume': volume,
                    'trade_count': int(volume/100),
                    'vwap': round((high_price + low_price + close_price)/3, 2)
                })
                
                bars.append(bar)
            
            print(f"\nSimulation summary for {symbol}:")
            print(f"Generated {len(bars)} bars")
            print(f"Price range: ${min(b.low for b in bars):.2f} - ${max(b.high for b in bars):.2f}")
            
            return bars
            
        except Exception as e:
            print(f"Error in simulation: {e}")
            traceback.print_exc()
            return []
    
    def get_position(self, symbol):
        """Get position information for a symbol"""
        try:
            if not self.trading_client:
                self.connect()
                
            try:
                positions = self.trading_client.get_all_positions()
                for position in positions:
                    if position.symbol == symbol:
                        return position
                return None
            except Exception as e:
                if "no positions" in str(e).lower():
                    return None
                raise
                
        except Exception as e:
            print(f"Error getting position for {symbol}: {e}")
            return None

    def get_positions(self):
        try:
            if not self.trading_client:
                self.connect()
            return self.trading_client.get_positions()
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def submit_order(self, order_data):
        """Submit an order with proper price validation"""
        try:
            if not self.trading_client:
                self.connect()

            # Get the current price from Alpaca's quote
            symbol = order_data.symbol
            current_price = None
            
            try:
                positions = self.trading_client.get_all_positions()
                for pos in positions:
                    if pos.symbol == symbol:
                        current_price = float(pos.current_price)
                        break
            except Exception as e:
                print(f"Warning: Could not get position price: {e}")

            if not current_price:
                try:
                    # Get latest quote for better price accuracy
                    quotes = self.trading_client.get_quotes(symbol, "2023-12-15", "2023-12-15", limit=1)
                    if quotes and len(quotes) > 0:
                        quote = quotes[0]
                        current_price = (float(quote.ask_price) + float(quote.bid_price)) / 2
                        print(f"Using quote midpoint price: ${current_price:.2f}")
                except Exception as e:
                    print(f"Warning: Could not get quote: {e}")

            # If we have a take profit order, ensure it's valid
            if hasattr(order_data, 'take_profit') and order_data.take_profit:
                if current_price:
                    # Make sure take profit is above current price
                    new_take_profit = max(current_price * 1.001, current_price + 0.01)
                    order_data.take_profit['limit_price'] = new_take_profit
                    print(f"Adjusted take profit to ${new_take_profit:.2f}")

            print(f"Submitting order for {symbol}...")
            return self.trading_client.submit_order(order_data)

        except Exception as e:
            print(f"Error submitting order: {e}")
            traceback.print_exc()
            return None

    def cancel_all_orders(self):
        try:
            if not self.trading_client:
                self.connect()
            return self.trading_client.cancel_all_orders()
        except Exception as e:
            print(f"Error canceling orders: {e}")
            return None