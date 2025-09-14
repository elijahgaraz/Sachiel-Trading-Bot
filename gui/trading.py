# gui/trading.py

import tkinter as tk
from tkinter import ttk, messagebox
from ctrader_open_api import Protobuf
from trading.ctrader_client import CTraderClient
from trading.market_clock import MarketClock
from config.settings import Config
import threading
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
import traceback
import pandas as pd
from trading.price_simulator import PriceSimulator
from collections import defaultdict

class TradingTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.ctrader_client = None
        self.market_clock = None  # Initialize as None
        self.is_trading = False
        self.simulation_mode = False
        self.active_positions = defaultdict(dict)
        self.highest_prices = {}
        self.partial_exits = set()
        self.setup_ui()
        self.start_market_status_updates()

    def verify_connection(self):
            """Verify connection to cTrader is still active"""
            try:
                if self.ctrader_client and self.ctrader_client.client:
                    # This will be implemented later
                    return True
                return False
            except Exception as e:
                print(f"Connection verification failed: {e}")
                return False

    def setup_ui(self):
        """Setup the complete trading interface"""
        
        # Main Status Frame
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.market_status_label = ttk.Label(
            status_frame, 
            text="Checking market status...",
            font=('SF Pro', 12, 'bold')
        )
        self.market_status_label.pack(side=tk.LEFT, padx=5)

        # Mode Controls
        self.simulation_var = tk.BooleanVar(value=False)
        self.aggressive_var = tk.BooleanVar(value=False)
        
        mode_frame = ttk.Frame(status_frame)
        mode_frame.pack(side=tk.RIGHT, padx=5)
        
        self.simulation_check = ttk.Checkbutton(
            mode_frame,
            text="Simulation Mode",
            variable=self.simulation_var,
            command=self.toggle_simulation_mode
        )
        self.simulation_check.pack(side=tk.RIGHT, padx=5)
        
        self.aggressive_check = ttk.Checkbutton(
            mode_frame,
            text="Aggressive Mode",
            variable=self.aggressive_var
        )
        self.aggressive_check.pack(side=tk.RIGHT, padx=5)

        # Trading Controls Frame
        controls_frame = ttk.LabelFrame(self, text="Trading Controls")
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Symbol Selection
        symbol_frame = ttk.Frame(controls_frame)
        symbol_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(symbol_frame, text="Symbol:").pack(side=tk.LEFT, padx=5)
        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(
            symbol_frame,
            textvariable=self.symbol_var,
            state="readonly",
            width=20
        )
        self.symbol_combo.pack(side=tk.LEFT, padx=5)
        self.symbol_combo.bind('<<ComboboxSelected>>', self.symbol_selection_changed)
        
        self.loading_label = ttk.Label(symbol_frame, text="")
        self.loading_label.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(
            symbol_frame,
            text="↻",
            width=3,
            command=self.load_symbols
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)

        # Position Management Frame
        position_frame = ttk.LabelFrame(controls_frame, text="Position Management")
        position_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Base Position Size
        ttk.Label(position_frame, text="Position Size:").grid(row=0, column=0, padx=5, pady=5)
        self.position_size = ttk.Entry(position_frame, width=15)
        self.position_size.insert(0, "100")
        self.position_size.grid(row=0, column=1, padx=5, pady=5)
        
        # Position Type
        ttk.Label(position_frame, text="Position Type:").grid(row=0, column=2, padx=5, pady=5)
        self.position_type = ttk.Combobox(
            position_frame,
            values=["Fixed Size", "Dollar Amount", "Portfolio %"],
            state="readonly",
            width=15
        )
        self.position_type.set("Fixed Size")
        self.position_type.grid(row=0, column=3, padx=5, pady=5)

        # Risk Management Frame
        risk_frame = ttk.LabelFrame(controls_frame, text="Risk Management")
        risk_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Stop Loss Settings
        ttk.Label(risk_frame, text="Stop Loss %:").grid(row=0, column=0, padx=5, pady=5)
        self.stop_loss = ttk.Entry(risk_frame, width=10)
        self.stop_loss.insert(0, "2")
        self.stop_loss.grid(row=0, column=1, padx=5, pady=5)
        
        # Take Profit Settings
        ttk.Label(risk_frame, text="Take Profit %:").grid(row=0, column=2, padx=5, pady=5)
        self.take_profit = ttk.Entry(risk_frame, width=10)
        self.take_profit.insert(0, "4")
        self.take_profit.grid(row=0, column=3, padx=5, pady=5)
        
        # Trailing Stop Settings
        ttk.Label(risk_frame, text="Trailing Stop %:").grid(row=1, column=0, padx=5, pady=5)
        self.trailing_stop = ttk.Entry(risk_frame, width=10)
        self.trailing_stop.insert(0, "1.5")
        self.trailing_stop.grid(row=1, column=1, padx=5, pady=5)
        
        # Max Position Time
        ttk.Label(risk_frame, text="Max Hold Time (days):").grid(row=1, column=2, padx=5, pady=5)
        self.max_hold_time = ttk.Entry(risk_frame, width=10)
        self.max_hold_time.insert(0, "5")
        self.max_hold_time.grid(row=1, column=3, padx=5, pady=5)

        # Advanced Settings Frame
        advanced_frame = ttk.LabelFrame(controls_frame, text="Advanced Settings")
        advanced_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Partial Exit Settings
        ttk.Label(advanced_frame, text="Partial Exit at % of Target:").grid(row=0, column=0, padx=5, pady=5)
        self.partial_exit = ttk.Entry(advanced_frame, width=10)
        self.partial_exit.insert(0, "75")
        self.partial_exit.grid(row=0, column=1, padx=5, pady=5)
        
        # Trading Mode Settings
        ttk.Label(advanced_frame, text="Trading Mode:").grid(row=0, column=2, padx=5, pady=5)
        self.trading_mode = ttk.Combobox(
            advanced_frame,
            values=["Conservative", "Moderate", "Aggressive"],
            state="readonly",
            width=15
        )
        self.trading_mode.set("Moderate")
        self.trading_mode.grid(row=0, column=3, padx=5, pady=5)

        # Control Buttons Frame
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(pady=10)
        
        self.start_button = ttk.Button(
            button_frame,
            text="Start Trading",
            command=self.start_trading,
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Trading",
            command=self.stop_trading,
            width=15,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Trade Log Frame
        log_frame = ttk.LabelFrame(self, text="Trade Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create Treeview with scrollbar
        tree_frame = ttk.Frame(log_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.trade_log = ttk.Treeview(
            tree_frame,
            columns=("Time", "Symbol", "Type", "Price", "Size", "P/L", "Exit Reason", "Confidence"),
            show="headings",
            height=10
        )
        
        # Configure columns
        column_widths = {
            "Time": 150,
            "Symbol": 100,
            "Type": 100,
            "Price": 100,
            "Size": 100,
            "P/L": 100,
            "Exit Reason": 150,
            "Confidence": 100
        }
        
        for col, width in column_widths.items():
            self.trade_log.heading(col, text=col)
            self.trade_log.column(col, width=width)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.trade_log.yview)
        x_scrollbar = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.trade_log.xview)
        
        self.trade_log.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        self.trade_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        x_scrollbar.pack(fill=tk.X)
        
        # self.start_auto_updates() # This was causing errors
     
    def toggle_simulation_mode(self):
        """Updated simulation mode toggle with crypto support"""
        self.simulation_mode = self.simulation_var.get()
        
        # Get current symbol
        current_symbol = self.symbol_var.get() if hasattr(self, 'symbol_var') else ""
        is_crypto = 'BTC' in current_symbol or 'ETH' in current_symbol
        
        if self.simulation_mode:
            self.start_button.config(state=tk.NORMAL)
            self.market_status_label.config(
                text="SIMULATION MODE ACTIVE",
                foreground='blue'
            )
        else:
            try:
                if self.market_clock:
                    is_open = self.market_clock.get_clock().is_open
                    
                    # Enable button if it's crypto or market is open
                    if is_crypto or is_open:
                        self.start_button.config(state=tk.NORMAL)
                    else:
                        self.start_button.config(state=tk.DISABLED)
                        
                    # Update status message
                    if is_crypto:
                        self.market_status_label.config(
                            text="CRYPTO MARKET (24/7 Trading Available)",
                            foreground='green'
                        )
                    else:
                        self.market_status_label.config(
                            text=f"Stock Market is {'OPEN' if is_open else 'CLOSED'}",
                            foreground='green' if is_open else 'red'
                        )
            except Exception as e:
                print(f"Error checking market status: {e}")
                self.start_button.config(state=tk.DISABLED)
    
    def load_symbols(self):
        def fetch_symbols():
            try:
                self.loading_label.config(text="Loading symbols...")
                self.refresh_button.config(state=tk.DISABLED)
                self.symbol_combo.set("")
                self.symbol_combo.config(values=[])
            
                if self.ctrader_client is None:
                    self.initialize_clients()

            # Get both stocks and crypto symbols
                # This will be implemented later
                all_symbols = ["EURUSD", "USDJPY", "BTCUSD"]
                
                self.symbol_combo.config(values=all_symbols)
                self.loading_label.config(text=f"{len(all_symbols)} symbols loaded")
                self.refresh_button.config(state=tk.NORMAL)
            
                if all_symbols:
                    self.symbol_combo.set(all_symbols[0])
                
            except Exception as e:
                self.loading_label.config(text="Error loading symbols")
                self.refresh_button.config(state=tk.NORMAL)
                messagebox.showerror("Error", f"Failed to load symbols: {str(e)}")

        thread = threading.Thread(target=fetch_symbols)
        thread.daemon = True
        thread.start() 
    
    def load_symbols_if_connected(self):
        if Config.CTRADING_CLIENT_ID and Config.CTRADING_CLIENT_SECRET:
            self.load_symbols()

    def start_market_status_updates(self):
        """Start market status update thread with proper error handling"""
        def update_market_status():
            while True:
                try:
                    # Check if we have credentials
                    if not Config.CTRADING_CLIENT_ID or not Config.CTRADING_CLIENT_SECRET:
                        if self.winfo_exists():
                            self.after(0, lambda: self.market_status_label.config(
                                text="API credentials not set",
                                foreground='red'
                            ))
                        time.sleep(60)
                        continue

                    # Check if we need to initialize clients
                    if self.ctrader_client is None:
                        print("No cTrader client, attempting to initialize...")
                        if not self.initialize_clients():
                            time.sleep(60)
                            continue

                    # Get current symbol and check if it's crypto
                    current_symbol = self.symbol_var.get() if hasattr(self, 'symbol_var') else ""
                    is_crypto = 'BTC' in current_symbol or 'ETH' in current_symbol

                    if is_crypto:
                        # Crypto markets are always open
                        message = "CRYPTO MARKET (24/7 Trading Available)"
                        color = 'green'
                        can_trade = True
                    else:
                        # cTrader is mainly for forex, which is also 24/5
                        message = "FOREX MARKET (24/5 Trading Available)"
                        color = 'green'
                        can_trade = True


                    def update_ui():
                        if not self.winfo_exists():
                            return
                        
                        self.market_status_label.config(text=message, foreground=color)
                        
                        # Update trading button state
                        if not self.simulation_mode:
                            if is_crypto or can_trade:
                                self.start_button.config(state=tk.NORMAL)
                            else:
                                self.start_button.config(state=tk.DISABLED)

                    if self.winfo_exists():
                        self.after(0, update_ui)

                except Exception as e:
                    print(f"Error in market status update: {e}")
                    traceback.print_exc()
                    
                time.sleep(60)  # Update every minute

        # Start the update thread
        status_thread = threading.Thread(target=update_market_status, daemon=True)
        status_thread.start()

    def symbol_selection_changed(self, event=None):
        """New method to handle symbol changes"""
        if hasattr(self, 'symbol_var'):
            current_symbol = self.symbol_var.get()
            is_crypto = 'BTC' in current_symbol or 'ETH' in current_symbol
            
            if not self.simulation_mode:
                try:
                    if self.market_clock:
                        is_open = self.market_clock.get_clock().is_open
                        
                        # Enable button if it's crypto or market is open
                        if is_crypto or is_open:
                            self.start_button.config(state=tk.NORMAL)
                        else:
                            self.start_button.config(state=tk.DISABLED)
                except Exception as e:
                    print(f"Error checking market status: {e}")
                    self.start_button.config(state=tk.DISABLED)
    
    def execute_live_trade(self):
        """Initiates the process of fetching bars and executing a trade."""
        try:
            symbol = self.symbol_var.get()
            if not symbol:
                return
                
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            print(f"Attempting to trade {symbol}, is_crypto: {is_crypto}")
            
            deferred = self.ctrader_client.get_bars(symbol, is_crypto)
            if deferred:
                deferred.addCallback(self._on_bars_received, symbol=symbol, is_crypto=is_crypto)
                deferred.addErrback(self._on_bars_error)

        except Exception as e:
            print(f"Error initiating live trade execution: {e}")
            traceback.print_exc()

    def _on_bars_received(self, bars_response, symbol, is_crypto):
        """Callback executed when historical bar data is successfully received."""
        try:
            bars = bars_response.trendbar
            if not bars:
                print(f"No price data available for {symbol}")
                return

            symbol_id = self.ctrader_client.symbols_map.get(symbol)
            if not symbol_id:
                print(f"Symbol ID not found for {symbol}")
                return
            symbol_details = self.ctrader_client.symbol_details_map.get(symbol_id)
            if not symbol_details:
                print(f"Could not get symbol details for {symbol} to scale price.")
                return

            price_scale = 10**symbol_details.digits
            last_bar = bars[-1]
            current_price = (last_bar.low + last_bar.deltaClose) / price_scale

            print(f"Current price for {symbol}: {current_price}")

            positions_deferred = self.ctrader_client.get_positions()
            if positions_deferred:
                positions_deferred.addCallback(self._on_positions_received, symbol=symbol, current_price=current_price, bars=bars)
                positions_deferred.addErrback(self._on_positions_error)

        except Exception as e:
            print(f"Error processing bars: {e}")
            traceback.print_exc()

    def _on_bars_error(self, failure):
        """Callback for handling errors from the get_bars Deferred."""
        print(f"Error fetching bars: {failure.getErrorMessage()}")

    def _on_positions_received(self, positions_response, symbol, current_price, bars):
        """Callback executed when the list of positions is received."""
        try:
            position = None
            for p in positions_response.position:
                symbol_id = self.ctrader_client.symbols_map.get(symbol)
                if p.tradeData.symbolId == symbol_id:
                    position = p
                    break

            if position is None:
                if self.check_entry_conditions(symbol, current_price, bars):
                    self.enter_live_trade(symbol, current_price)
            else:
                self.check_live_exit(symbol, position, current_price)

        except Exception as e:
            print(f"Error processing positions: {e}")
            traceback.print_exc()

    def _on_positions_error(self, failure):
        """Callback for handling errors from the get_positions Deferred."""
        print(f"Error fetching positions: {failure.getErrorMessage()}")

    def start_trading(self):
        """Start trading with improved stock handling"""
        try:
            if not self.validate_inputs():
                return
                
            # Initialize clients if not already done
            if self.ctrader_client is None:
                print("\nInitializing new cTrader client...")
                if not self.initialize_clients():
                    raise Exception("Failed to initialize trading clients")
            
            # Get symbol and check if it's crypto
            symbol = self.symbol_var.get()
            if not symbol:
                raise ValueError("No symbol selected")
                
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            print(f"\nStarting trade for {symbol} (is_crypto: {is_crypto})")
            
            # cTrader is 24/5 for forex and 24/7 for crypto, so no need for market open checks
                    
            # Proceed with trading
            self.is_trading = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            # Start trading thread
            trading_thread = threading.Thread(target=self.trading_loop)
            trading_thread.daemon = True
            trading_thread.start()
            
            # Log trading start
            self.add_to_log(
                datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                symbol,
                "START",
                "-",
                self.position_size.get(),
                "-",
                "Trading Started",
                "-"
            )
            
        except Exception as e:
            print(f"Error starting trade: {str(e)}")
            traceback.print_exc()
            messagebox.showerror(
                "Error",
                f"Unable to start trading: {str(e)}\nPlease check connection and settings."
            )
            self.stop_trading()

    def stop_trading(self):
        """Stop all trading operations"""
        try:
            self.is_trading = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
            # Get current symbol
            symbol = self.symbol_var.get()
            
            # Log the stop event
            self.add_to_log(
                datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                symbol,
                "STOP",
                "-",
                "-",
                "-",
                "Trading Stopped",
                "-"
            )
            
            # Clean up any tracking variables
            if symbol in self.highest_prices:
                del self.highest_prices[symbol]
            if symbol in self.partial_exits:
                self.partial_exits.remove(symbol)
                
            # Show confirmation
            messagebox.showinfo("Trading Stopped", "Trading operations have been stopped.")
            
        except Exception as e:
            print(f"Error stopping trading: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", f"Error stopping trading: {str(e)}")

    def trading_loop(self):
        """Main trading loop with proper clock access"""
        while self.is_trading:
            try:
                symbol = self.symbol_var.get()
                is_crypto = 'BTC' in symbol or 'ETH' in symbol
                
                if self.simulation_mode:
                    self.execute_simulation_trade()
                else:
                    self.execute_live_trade()
                            
                time.sleep(1)  # Check every second
                    
            except Exception as e:
                print(f"Error in trading loop: {e}")
                traceback.print_exc()
                time.sleep(5)  # Wait longer on error

            # Add periodic connection check
            if not self.simulation_mode:
                try:
                    if not self.verify_connection():
                        print("Lost connection to cTrader, attempting to reconnect...")
                        if not self.initialize_clients():
                            print("Failed to reconnect, stopping trading")
                            self.stop_trading()
                            break
                except Exception as e:
                    print(f"Error in connection check: {e}")

        def verify_connection(self):
            """Verify connection to cTrader is still active"""
            try:
                if self.ctrader_client and self.ctrader_client.client:
                    # This will be implemented later
                    return True
                return False
            except Exception as e:
                print(f"Connection verification failed: {e}")
                return False
            
    def monitor_trade_execution(self):
        """Monitor pending trades and update status"""
        try:
            if not self.ctrader_client:
                return
                
            # This will be implemented later
                    
        except Exception as e:
            print(f"Error monitoring trades: {e}")
            traceback.print_exc()

    def execute_simulation_trade(self):
        """Execute a simulated trade"""
        try:
            if self.check_ai_signals():
                symbol = self.symbol_var.get()
                
                # Get latest simulated price
                if not hasattr(self, 'price_simulator'):
                    self.price_simulator = PriceSimulator()
                    
                current_price = self.price_simulator.get_next_price()
                
                if self.current_position is None:
                    # Check if we should enter a trade
                    if self.should_enter_trade(current_price):
                        self.enter_simulation_trade(current_price)
                else:
                    # Check if we should exit existing trade
                    self.check_simulation_exit(current_price)
                    
        except Exception as e:
            print(f"Error in simulation trade: {e}")
            traceback.print_exc()
    
    def enter_live_trade(self, symbol, price):
        try:
            position_size = float(self.position_size.get())
            
            order_data = {
                "symbol": symbol,
                "qty": position_size,
                "side": "BUY",
            }
            
            order = self.ctrader_client.submit_order(order_data)
            
            if order:
                self.add_to_log(
                    datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                    symbol,
                    "BUY",
                    f"${price:.2f}",
                    position_size,
                    "-"
                )
            
            return order
            
        except Exception as e:
            print(f"Error entering live trade: {e}")
            traceback.print_exc()
            return None
    
    def enter_live_crypto_trade(self, symbol, price):
        """Enhanced crypto trade entry with proper time-in-force setting"""
        try:
            position_size = float(self.position_size.get())
            
            order_data = {
                "symbol": symbol,
                "qty": position_size,
                "side": "BUY",
            }
            
            order = self.ctrader_client.submit_order(order_data)
            
            if order:
                print("Order submitted successfully!")
                self.add_to_log(
                    datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                    symbol,
                    "BUY CRYPTO",
                    f"${price:.2f}",
                    position_size,
                    "-",
                    "Entry",
                    "High Confidence"
                )
                return True
            else:
                print("Order submission failed!")
                return False
                
        except Exception as e:
            print(f"Error entering crypto trade: {e}")
            traceback.print_exc()
            return False
    
    def enter_simulation_trade(self, price):
        """Enter a simulated trade"""
        try:
            position_size = float(self.position_size.get())
            self.current_position = {
                'symbol': self.symbol_var.get(),
                'size': position_size,
                'entry_price': price,
                'stop_loss': price * (1 - float(self.stop_loss.get()) / 100),
                'take_profit': price * (1 + float(self.take_profit.get()) / 100),
                'entry_time': datetime.now(pytz.UTC)
            }
            
            self.add_to_log(
                datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                self.symbol_var.get(),
                "BUY (SIM)",
                f"${price:.2f}",
                position_size,
                "-"
            )
            
            print(f"Entered simulation trade:")
            print(f"Symbol: {self.current_position['symbol']}")
            print(f"Entry Price: ${self.current_position['entry_price']:.2f}")
            print(f"Stop Loss: ${self.current_position['stop_loss']:.2f}")
            print(f"Take Profit: ${self.current_position['take_profit']:.2f}")
            
        except Exception as e:
            print(f"Error entering simulation trade: {e}")
            traceback.print_exc()
            
    def check_entry_conditions(self, symbol, current_price, bars):
        """Enhanced entry condition checking with debug logging"""
        try:
            # Create DataFrame for technical analysis
            df = pd.DataFrame([{
                'close': bar.close,
                'high': bar.high,
                'low': bar.low,
                'volume': bar.volume,
                'timestamp': bar.timestamp
            } for bar in bars])
            
            if len(df) < 20:
                print(f"Insufficient data points: {len(df)}")
                return False
            
            # Calculate technical indicators
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['rsi'] = self.calculate_rsi(df['close'])
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            
            # Get latest values
            latest = df.iloc[-1]
            
            # Check conditions with detailed logging
            price_above_sma = current_price > latest['sma_20']
            volume_increase = latest['volume'] > latest['volume_ma'] * 1.2
            rsi_favorable = 30 < latest['rsi'] < 70
            uptrend = latest['sma_20'] > latest['sma_50'] if len(df) >= 50 else True

            print("\nEntry Conditions Check:")
            print(f"Price (${current_price:.2f}) above SMA20 (${latest['sma_20']:.2f}): {price_above_sma}")
            print(f"Volume ({latest['volume']:.0f}) above MA ({latest['volume_ma']:.0f}): {volume_increase}")
            print(f"RSI ({latest['rsi']:.2f}) between 30-70: {rsi_favorable}")
            print(f"Uptrend (SMA20 > SMA50): {uptrend}")
            
            # More lenient conditions for crypto
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            
            if is_crypto:
                # For crypto, require only 2 out of 4 conditions
                conditions_met = sum([price_above_sma, volume_increase, rsi_favorable, uptrend])
                should_enter = conditions_met >= 2
                print(f"Crypto conditions met: {conditions_met}/4")
            else:
                # For stocks, use more conservative approach
                should_enter = price_above_sma and (volume_increase or rsi_favorable) and uptrend
                print(f"Stock conditions all met: {should_enter}")

            return should_enter

        except Exception as e:
            print(f"Error checking entry conditions: {e}")
            traceback.print_exc()
            return False

    def check_ai_signals(self):
        try:
            notebook = self.master
            while not isinstance(notebook, ttk.Notebook):
                notebook = notebook.master
                if notebook is None:
                    print("Could not find notebook")
                    return False

            sachiel_tab = None
            for child in notebook.winfo_children():
                if child.winfo_name() == '!sachielaitab':
                    sachiel_tab = child
                    break

            if sachiel_tab is None:
                print("AI tab not found - widget names:", [child.winfo_name() for child in notebook.winfo_children()])
                return False

            symbol = self.symbol_var.get()
            signals = sachiel_tab.get_ai_signals(symbol)
            
            if not signals:
                print("No signals available")
                return False
                
            if signals['signals']['should_trade']:
                def update_gui():
                    try:
                        if not self.winfo_exists():
                            return
                            
                        self.position_size.delete(0, tk.END)
                        self.position_size.insert(0, str(signals['signals']['position_size']))
                        
                        self.stop_loss.delete(0, tk.END)
                        self.stop_loss.insert(0, str(signals['signals']['stop_loss'] * 100))
                        
                        self.take_profit.delete(0, tk.END)
                        self.take_profit.insert(0, str(signals['signals']['take_profit'] * 100))
                    except Exception as e:
                        print(f"Error updating GUI: {e}")

                if self.winfo_exists():
                    self.after(0, update_gui)
                
                return True
                
            return False
            
        except Exception as e:
            print(f"Error checking AI signals: {str(e)}")
            traceback.print_exc()
            return False
            
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum()/period
        down = -seed[seed < 0].sum()/period
        rs = up/down
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100./(1. + rs)
        
        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
                
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)
            
        return rsi
    
    def check_live_exit(self, symbol, position, current_price):
        """Check and execute exit conditions for live trades"""
        try:
            # This will be implemented later
            pass
            
        except Exception as e:
            print(f"Error in exit check: {e}")
            traceback.print_exc()
            return False
    
    def check_simulation_exit(self, current_price):
        """Check if we should exit the simulated trade"""
        try:
            if self.current_position is None:
                return
                
            # Calculate P&L
            entry_price = self.current_position['entry_price']
            position_size = self.current_position['size']
            pl_amount = (current_price - entry_price) * position_size
            pl_percentage = ((current_price / entry_price) - 1) * 100
            
            # Check stop loss and take profit
            stop_hit = current_price <= self.current_position['stop_loss']
            profit_hit = current_price >= self.current_position['take_profit']
            
            if stop_hit or profit_hit:
                exit_type = "STOP (SIM)" if stop_hit else "PROFIT (SIM)"
                
                self.add_to_log(
                    datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                    self.current_position['symbol'],
                    exit_type,
                    f"${current_price:.2f}",
                    position_size,
                    f"${pl_amount:.2f} ({pl_percentage:.2f}%)"
                )
                
                print(f"Exited simulation trade:")
                print(f"Exit Type: {exit_type}")
                print(f"Exit Price: ${current_price:.2f}")
                print(f"P&L: ${pl_amount:.2f} ({pl_percentage:.2f}%)")
                
                self.current_position = None
                
        except Exception as e:
            print(f"Error checking simulation exit: {e}")
            traceback.print_exc()
            
    def should_enter_trade(self, current_price):
        """Determine if we should enter a trade based on price history"""
        try:
            # Initialize price history if needed
            if not hasattr(self, 'price_history'):
                self.price_history = []
                
            self.price_history.append(current_price)
            self.price_history = self.price_history[-10:]  # Keep last 10 prices
            
            if len(self.price_history) < 4:
                return False
                
            # Simple trend following strategy
            return (self.price_history[-1] > self.price_history[-2] and
                    self.price_history[-2] > self.price_history[-3] and
                    self.price_history[-3] > self.price_history[-4])
                    
        except Exception as e:
            print(f"Error in trade decision: {e}")
            traceback.print_exc()
            return False
        
    def validate_inputs(self):
        if not self.symbol_var.get():
            messagebox.showerror("Error", "Please select a symbol")
            return False
            
        position_size = self.position_size.get().strip() or "100"
        stop_loss = self.stop_loss.get().strip() or "2"
        take_profit = self.take_profit.get().strip() or "4"
        
        try:
            position_size_val = float(position_size)
            stop_loss_val = float(stop_loss)
            take_profit_val = float(take_profit)
            
            if position_size_val <= 0:
                raise ValueError("Position size must be greater than 0")
                
            if stop_loss_val <= 0 or stop_loss_val >= 100:
                raise ValueError("Stop loss must be between 0 and 100")
                
            if take_profit_val <= 0 or take_profit_val >= 100:
                raise ValueError("Take profit must be between 0 and 100")
                
            if take_profit_val <= stop_loss_val:
                raise ValueError("Take profit must be greater than stop loss")
            
            if not self.position_size.get().strip():
                self.position_size.delete(0, tk.END)
                self.position_size.insert(0, str(position_size_val))
                
            if not self.stop_loss.get().strip():
                self.stop_loss.delete(0, tk.END)
                self.stop_loss.insert(0, str(stop_loss_val))
                
            if not self.take_profit.get().strip():
                self.take_profit.delete(0, tk.END)
                self.take_profit.insert(0, str(take_profit_val))
                
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input values: {str(e)}")
            return False
            
        return True
    
    def add_to_log(self, time_str, symbol, type_, price, size, pl, exit_reason="", confidence=""):
        """Add entry to trade log with all parameters"""
        try:
            self.trade_log.insert('', 0, values=(
                time_str,
                symbol,
                type_,
                price,
                size,
                pl,
                exit_reason,
                confidence
            ))
            
            # Scroll to top to show latest entry
            self.trade_log.yview_moveto(0)
            
            # Limit log size to prevent memory issues
            if self.trade_log.get_children().__len__() > 1000:
                last_item = self.trade_log.get_children()[-1]
                self.trade_log.delete(last_item)
                
        except Exception as e:
            print(f"Error adding to trade log: {e}")
            traceback.print_exc()