# gui/trading.py

import tkinter as tk
from tkinter import ttk, messagebox
from trading.alpaca_client import AlpacaClient
from trading.market_clock import MarketClock
from config.settings import Config
import threading
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import traceback
import pandas as pd
from trading.price_simulator import PriceSimulator
from collections import defaultdict

class TradingTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.alpaca_client = None
        self.market_clock = None  # Initialize as None
        self.is_trading = False
        self.simulation_mode = False
        self.active_positions = defaultdict(dict)
        self.highest_prices = {}
        self.partial_exits = set()
        self.setup_ui()
        self.initialize_clients()
        self.start_market_status_updates()

    def verify_connection(self):
            """Verify connection to Alpaca is still active"""
            try:
                if self.alpaca_client and self.alpaca_client.trading_client:
                    # Try to get account info as a connection test
                    self.alpaca_client.trading_client.get_account()
                    return True
                return False
            except Exception as e:
                print(f"Connection verification failed: {e}")
                return False

    def start_auto_updates(self):
        """Start automatic updates for the current symbol and market data"""
        def update():
            try:
                # Update market data if we have a symbol selected and are trading
                if hasattr(self, 'symbol_var') and self.symbol_var.get() and self.is_trading:
                    symbol = self.symbol_var.get()
                    is_crypto = 'BTC' in symbol or 'ETH' in symbol
                    
                    # Get latest market data
                    if self.alpaca_client:
                        bars = self.alpaca_client.get_bars(symbol, is_crypto)
                        if bars:
                            current_price = bars[-1].close
                            
                            # Update trading view if needed
                            try:
                                position = self.alpaca_client.get_position(symbol.replace('/', ''))
                                if position:
                                    pl_pct = ((current_price - float(position.avg_entry_price)) / 
                                            float(position.avg_entry_price) * 100)
                                    
                                    # Add current status to log if significant change
                                    if abs(pl_pct) >= 1.0:  # Log every 1% change
                                        self.add_to_log(
                                            datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                                            symbol,
                                            "UPDATE",
                                            f"${current_price:.2f}",
                                            position.qty,
                                            f"${float(position.unrealized_pl):.2f} ({pl_pct:.2f}%)",
                                            "Position Update",
                                            "-"
                                        )
                            except Exception as e:
                                # No position exists, this is normal
                                pass
                
            except Exception as e:
                print(f"Error in auto update: {e}")
                traceback.print_exc()
            
            finally:
                # Schedule next update if widget still exists
                if self.winfo_exists():
                    self.after(30000, update)  # Update every 30 seconds
        
        # Start the first update
        if self.winfo_exists():
            self.after(1000, update)  # Start first update after 1 second

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
        
        # Start auto-updates
        self.start_auto_updates()
     
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
    
    def initialize_clients(self):
        """Initialize trading clients with focus on stock trading"""
        try:
            print("\nInitializing Trading Clients:")
            
            # Check API credentials
            if not hasattr(Config, 'API_KEY') or not Config.API_KEY or not hasattr(Config, 'API_SECRET') or not Config.API_SECRET:
                print("Error: Missing API credentials")
                if hasattr(self, 'market_status_label'):
                    self.market_status_label.config(
                        text="Please set up API credentials in Settings",
                        foreground='red'
                    )
                return False

            print("1. Creating Alpaca client...")
            self.alpaca_client = AlpacaClient()
            
            print("2. Connecting Alpaca client...")
            if not self.alpaca_client.connect():
                print("Failed to connect Alpaca client")
                return False
                
            print("3. Verifying trading client...")
            if not hasattr(self.alpaca_client, 'trading_client'):
                print("Error: No trading client available after connection")
                return False
                
            print("4. Testing account access...")
            try:
                account = self.alpaca_client.trading_client.get_account()
                print(f"Account verified - Status: {account.status}")
                
                # Update market status label
                if hasattr(self, 'market_status_label'):
                    self.market_status_label.config(
                        text=f"Connected to Alpaca - Account Active",
                        foreground='green'
                    )
                return True
                
            except Exception as e:
                print(f"Error verifying account: {e}")
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"Error in initialize_clients: {str(e)}")
            traceback.print_exc()
            if hasattr(self, 'market_status_label'):
                self.market_status_label.config(
                    text=f"Error connecting to Alpaca: {str(e)}",
                    foreground='red'
                )
            return False
         
    def load_symbols(self):
        def fetch_symbols():
            try:
                self.loading_label.config(text="Loading symbols...")
                self.refresh_button.config(state=tk.DISABLED)
                self.symbol_combo.set("")
                self.symbol_combo.config(values=[])
            
                if self.alpaca_client is None:
                    self.initialize_clients()

            # Get both stocks and crypto symbols
                stock_symbols = self.alpaca_client.get_tradable_symbols()
                crypto_symbols = self.alpaca_client.get_tradable_crypto_symbols()  # Add this method to AlpacaClient
                
                all_symbols = sorted(stock_symbols + crypto_symbols)
                self.symbol_pairs = {symbol: 'crypto' if symbol in crypto_symbols else 'stock' for symbol in all_symbols}
                
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
        if Config.API_KEY and Config.API_SECRET:
            self.load_symbols()

    def start_market_status_updates(self):
        """Start market status update thread with proper error handling"""
        def update_market_status():
            while True:
                try:
                    # Check if we have credentials
                    if not Config.API_KEY or not Config.API_SECRET:
                        if self.winfo_exists():
                            self.after(0, lambda: self.market_status_label.config(
                                text="API credentials not set",
                                foreground='red'
                            ))
                        time.sleep(60)
                        continue

                    # Check if we need to initialize clients
                    if self.alpaca_client is None:
                        print("No Alpaca client, attempting to initialize...")
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
                        # Check stock market status
                        try:
                            if self.market_clock:
                                clock = self.market_clock.get_clock()
                                is_open = clock.is_open
                                message = f"Market is {'OPEN' if is_open else 'CLOSED'}"
                                color = 'green' if is_open else 'red'
                                can_trade = is_open
                            else:
                                message = "Market clock not initialized"
                                color = 'red'
                                can_trade = False
                        except Exception as e:
                            print(f"Error checking market clock: {e}")
                            message = "Error checking market status"
                            color = 'red'
                            can_trade = False

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
        """Execute live trading operation with combo box"""
        try:
            # Get symbol from combo box
            symbol = self.symbol_var.get()
            if not symbol:
                return
                
            # Format symbol for crypto
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            formatted_symbol = f"{symbol[:3]}/USD" if is_crypto and '/' not in symbol else symbol
            
            print(f"Attempting to trade {formatted_symbol}, is_crypto: {is_crypto}")
            
            # Get current market data
            bars = self.alpaca_client.get_bars(formatted_symbol, is_crypto)
            if not bars:
                print(f"No price data available for {formatted_symbol}")
                return
                
            current_price = bars[-1].close
            print(f"Current price for {formatted_symbol}: {current_price}")
            
            # Check existing position
            try:
                check_symbol = formatted_symbol.replace('/', '') if is_crypto else formatted_symbol
                position = self.alpaca_client.get_position(check_symbol)
            except Exception:
                position = None
            
            if position is None:
                # Check entry conditions
                if self.check_entry_conditions(formatted_symbol, current_price, bars):
                    if is_crypto:
                        self.enter_live_crypto_trade(formatted_symbol, current_price)
                    else:
                        self.enter_live_trade(formatted_symbol, current_price)
            else:
                # Check exit conditions
                self.check_live_exit(formatted_symbol, position, current_price)
            
        except Exception as e:
            print(f"Error in live trade execution: {e}")
            traceback.print_exc()
                
    def start_trading(self):
        """Start trading with improved stock handling"""
        try:
            if not self.validate_inputs():
                return
                
            # Initialize clients if not already done
            if self.alpaca_client is None:
                print("\nInitializing new Alpaca client...")
                if not self.initialize_clients():
                    raise Exception("Failed to initialize trading clients")
            
            # Get symbol and check if it's crypto
            symbol = self.symbol_var.get()
            if not symbol:
                raise ValueError("No symbol selected")
                
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            print(f"\nStarting trade for {symbol} (is_crypto: {is_crypto})")
            
            # Stock-specific checks
            if not self.simulation_mode and not is_crypto:
                try:
                    if not self.alpaca_client:
                        raise Exception("No Alpaca client available")
                        
                    if not self.alpaca_client.trading_client:
                        raise Exception("No trading client available")
                        
                    print("Checking market status...")
                    clock = self.alpaca_client.trading_client.get_clock()
                    print(f"Market is {'OPEN' if clock.is_open else 'CLOSED'}")
                    
                    if not clock.is_open:
                        messagebox.showerror(
                            "Error",
                            "Stock market is closed. Enable simulation mode to test trading."
                        )
                        return
                        
                except Exception as e:
                    print(f"Stock market check error: {e}")
                    traceback.print_exc()
                    raise Exception(f"Unable to verify stock market status: {str(e)}")
                    
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
                    # For crypto, trade 24/7
                    if is_crypto:
                        self.execute_live_trade()
                    # For stocks, check market hours
                    else:
                        try:
                            # Access clock through alpaca_client
                            if self.alpaca_client and self.alpaca_client.trading_client:
                                clock = self.alpaca_client.trading_client.get_clock()
                                if clock.is_open:
                                    self.execute_live_trade()
                                else:
                                    print("Stock market is closed, stopping live trading")
                                    self.stop_trading()
                                    break
                            else:
                                print("Trading client not available, stopping trading")
                                self.stop_trading()
                                break
                        except Exception as e:
                            print(f"Error checking market status: {e}")
                            traceback.print_exc()
                            self.stop_trading()
                            break
                            
                time.sleep(1)  # Check every second
                    
            except Exception as e:
                print(f"Error in trading loop: {e}")
                traceback.print_exc()
                time.sleep(5)  # Wait longer on error

            # Add periodic connection check
            if not self.simulation_mode and not is_crypto:
                try:
                    if not self.verify_connection():
                        print("Lost connection to Alpaca, attempting to reconnect...")
                        if not self.initialize_clients():
                            print("Failed to reconnect, stopping trading")
                            self.stop_trading()
                            break
                except Exception as e:
                    print(f"Error in connection check: {e}")

        def verify_connection(self):
            """Verify connection to Alpaca is still active"""
            try:
                if self.alpaca_client and self.alpaca_client.trading_client:
                    # Try to get account info as a connection test
                    self.alpaca_client.trading_client.get_account()
                    return True
                return False
            except Exception as e:
                print(f"Connection verification failed: {e}")
                return False
            
    def monitor_trade_execution(self):
        """Monitor pending trades and update status"""
        try:
            if not self.alpaca_client:
                return
                
            # Get pending orders
            orders = self.alpaca_client.trading_client.get_orders()
            
            for order in orders:
                print(f"\nOrder Status Check:")
                print(f"Symbol: {order.symbol}")
                print(f"Status: {order.status}")
                print(f"Filled Qty: {order.filled_qty}")
                print(f"Filled Avg Price: ${float(order.filled_avg_price) if order.filled_avg_price else 0:.2f}")
                
                if order.status == 'filled':
                    print("Order filled successfully!")
                    self.add_to_log(
                        datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                        order.symbol,
                        "FILLED",
                        f"${float(order.filled_avg_price):.2f}",
                        order.filled_qty,
                        "-",
                        "Order Filled",
                        "-"
                    )
                elif order.status == 'rejected':
                    print(f"Order rejected: {order.rejected_reason}")
                    self.add_to_log(
                        datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                        order.symbol,
                        "REJECTED",
                        "-",
                        "-",
                        "-",
                        order.rejected_reason,
                        "-"
                    )
                    
        except Exception as e:
            print(f"Error monitoring trades: {e}")
            traceback.print_exc()
    def execute_live_trade(self):
        """Execute live trading operation with combo box"""
        try:
            # Get symbol from combo box
            symbol = self.symbol_var.get()
            if not symbol:
                return
                
            # Format symbol for crypto
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            formatted_symbol = f"{symbol[:3]}/USD" if is_crypto and '/' not in symbol else symbol
            
            print(f"Attempting to trade {formatted_symbol}, is_crypto: {is_crypto}")
            
            # Get current market data
            bars = self.alpaca_client.get_bars(formatted_symbol, is_crypto)
            if not bars:
                print(f"No price data available for {formatted_symbol}")
                return
                
            current_price = bars[-1].close
            print(f"Current price for {formatted_symbol}: {current_price}")
            
            # Check existing position
            try:
                check_symbol = formatted_symbol.replace('/', '') if is_crypto else formatted_symbol
                position = self.alpaca_client.get_position(check_symbol)
            except Exception:
                position = None
            
            if position is None:
                # Check entry conditions
                if self.check_entry_conditions(formatted_symbol, current_price, bars):
                    if is_crypto:
                        self.enter_live_crypto_trade(formatted_symbol, current_price)
                    else:
                        self.enter_live_trade(formatted_symbol, current_price)
            else:
                # Check exit conditions
                self.check_live_exit(formatted_symbol, position, current_price)
            
        except Exception as e:
            print(f"Error in live trade execution: {e}")
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
            stop_loss_pct = float(self.stop_loss.get()) / 100
            take_profit_pct = float(self.take_profit.get()) / 100
            
            # Ensure minimum price differences
            stop_loss = price * (1 - stop_loss_pct)
            take_profit = max(price * (1 + take_profit_pct), price + 0.01)
            
            print(f"Preparing order for {symbol}")
            print(f"Entry Price: ${price:.2f}")
            print(f"Stop Loss: ${stop_loss:.2f}")
            print(f"Take Profit: ${take_profit:.2f}")
            
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=position_size,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class='bracket',
                take_profit={'limit_price': take_profit},
                stop_loss={'stop_price': stop_loss, 'limit_price': stop_loss * 0.99}
            )
            
            order = self.alpaca_client.submit_order(order_data)
            
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
            print(f"\nAttempting to enter crypto trade for {symbol} at ${price:.2f}")
            
            # For Bitcoin, use a smaller default position size due to high price
            default_size = 0.01 if 'BTC' in symbol else 0.1  # 0.01 BTC or 0.1 ETH
            requested_size = float(self.position_size.get())
            
            # If requested size seems too large for BTC, assume it's meant to be a fraction
            if 'BTC' in symbol and requested_size > 1:
                requested_size = requested_size / 10000  # Convert to fractional BTC
                print(f"Adjusted position size to {requested_size:.4f} BTC")
                
            stop_loss_pct = float(self.stop_loss.get()) / 100
            take_profit_pct = float(self.take_profit.get()) / 100
            
            # Format symbol for order submission
            order_symbol = symbol.replace('/', '')
            
            print(f"\nOrder Details:")
            print(f"Symbol: {order_symbol}")
            print(f"Entry Price: ${price:.2f}")
            print(f"Position Size: {requested_size:.4f}")
            print(f"Stop Loss: ${price * (1 - stop_loss_pct):.2f} ({stop_loss_pct*100}%)")
            print(f"Take Profit: ${price * (1 + take_profit_pct):.2f} ({take_profit_pct*100}%)")
            
            # Calculate notional value and check limits
            notional_value = requested_size * price
            max_notional = 200000  # $200,000 limit
            
            if notional_value > max_notional:
                adjusted_size = (max_notional / price) * 0.95  # Use 95% of max to be safe
                print(f"Adjusting position size from {requested_size:.4f} to {adjusted_size:.4f} due to notional limit")
                position_size = adjusted_size
            else:
                position_size = requested_size
            
            # Create and submit the order - use IOC for crypto
            order_data = MarketOrderRequest(
                symbol=order_symbol,
                qty=position_size,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.IOC  # Changed from GTC to IOC for crypto
            )
            
            print("\nSubmitting order...")
            order = self.alpaca_client.submit_order(order_data)
            
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
            # Extract position details
            entry_price = float(position.avg_entry_price)
            position_size = float(position.qty)
            current_pl_pct = (current_price - entry_price) / entry_price
            unrealized_pl = float(position.unrealized_pl)
            
            print(f"\nChecking exit conditions for {symbol}:")
            print(f"Entry Price: ${entry_price:.2f}")
            print(f"Current Price: ${current_price:.2f}")
            print(f"Current P/L: {current_pl_pct:.2%} (${unrealized_pl:.2f})")
            
            # Get configured exit levels
            stop_loss_pct = float(self.stop_loss.get()) / 100
            take_profit_pct = float(self.take_profit.get()) / 100
            trailing_stop_pct = float(self.trailing_stop.get()) / 100
            
            # Initialize exit flags
            exit_triggered = False
            exit_type = None
            
            # 1. Stop Loss Check
            if current_pl_pct <= -stop_loss_pct:
                exit_triggered = True
                exit_type = "STOP LOSS"
                print(f"Stop loss triggered at {current_pl_pct:.2%}")
            
            # 2. Take Profit Check
            elif current_pl_pct >= take_profit_pct:
                exit_triggered = True
                exit_type = "TAKE PROFIT"
                print(f"Take profit triggered at {current_pl_pct:.2%}")
            
            # 3. Trailing Stop Check
            if symbol in self.highest_prices:
                highest_price = self.highest_prices[symbol]
                if current_price > highest_price:
                    self.highest_prices[symbol] = current_price
                    print(f"New highest price: ${current_price:.2f}")
                elif current_price < (highest_price * (1 - trailing_stop_pct)):
                    exit_triggered = True
                    exit_type = "TRAILING STOP"
                    print(f"Trailing stop triggered. Highest: ${highest_price:.2f}, Current: ${current_price:.2f}")
            else:
                self.highest_prices[symbol] = current_price
                print(f"Initial highest price set: ${current_price:.2f}")
            
            # 4. Time-Based Exit
            max_hold_days = float(self.max_hold_time.get())
            try:
                # Try different possible timestamp attributes
                if hasattr(position, 'created_at'):
                    entry_time = datetime.strptime(position.created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                elif hasattr(position, 'timestamp'):
                    entry_time = datetime.strptime(position.timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
                else:
                    entry_time = None
                    print("No entry timestamp found")
                    
                if entry_time:
                    entry_time = entry_time.replace(tzinfo=pytz.UTC)
                    hold_time = datetime.now(pytz.UTC) - entry_time
                    print(f"Current hold time: {hold_time.days} days, {hold_time.seconds//3600} hours")
                    
                    if hold_time > timedelta(days=max_hold_days):
                        exit_triggered = True
                        exit_type = "TIME EXIT"
                        print(f"Time exit triggered after {hold_time.days} days")
                    
            except Exception as e:
                print(f"Error checking time-based exit: {e}")
            
            # 5. Partial Exit Check
            partial_exit_threshold = float(self.partial_exit.get()) / 100
            if (current_pl_pct >= take_profit_pct * partial_exit_threshold and 
                position_size >= 2 and 
                symbol not in self.partial_exits):
                
                try:
                    print(f"Executing partial exit at {current_pl_pct:.2%} profit")
                    # Sell half position
                    partial_size = position_size / 2
                    
                    # Check if it's a crypto symbol
                    is_crypto = 'BTC' in symbol or 'ETH' in symbol
                    
                    order_data = MarketOrderRequest(
                        symbol=symbol.replace('/', ''),
                        qty=partial_size,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.IOC if is_crypto else TimeInForce.DAY
                    )
                    
                    partial_order = self.alpaca_client.submit_order(order_data)
                    
                    if partial_order:
                        self.partial_exits.add(symbol)
                        print(f"Partial exit executed for {symbol}")
                        self.add_to_log(
                            datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                            symbol,
                            "PARTIAL EXIT",
                            f"${current_price:.2f}",
                            partial_size,
                            f"${(unrealized_pl/2):.2f}",
                            "Partial Profit",
                            f"{current_pl_pct:.2%}"
                        )
                    
                except Exception as e:
                    print(f"Error executing partial exit: {e}")
                    traceback.print_exc()
            
            # Execute full exit if triggered
            if exit_triggered:
                try:
                    print(f"\nExecuting {exit_type} for {symbol}")
                    print(f"Position Size: {position_size}")
                    print(f"Exit Price: ${current_price:.2f}")
                    
                    # Check if it's a crypto symbol
                    is_crypto = 'BTC' in symbol or 'ETH' in symbol
                    
                    order_data = MarketOrderRequest(
                        symbol=symbol.replace('/', ''),
                        qty=position_size,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.IOC if is_crypto else TimeInForce.DAY
                    )
                    
                    exit_order = self.alpaca_client.submit_order(order_data)
                    
                    if exit_order:
                        self.add_to_log(
                            datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                            symbol,
                            exit_type,
                            f"${current_price:.2f}",
                            position_size,
                            f"${unrealized_pl:.2f}",
                            exit_type,
                            f"{current_pl_pct:.2%}"
                        )
                        
                        # Clean up tracking variables
                        if symbol in self.highest_prices:
                            del self.highest_prices[symbol]
                        if symbol in self.partial_exits:
                            self.partial_exits.remove(symbol)
                        
                        print("Exit order submitted successfully")
                        print(f"Final P&L: ${unrealized_pl:.2f} ({current_pl_pct:.2%})")
                        
                        return True
                    else:
                        print("Exit order submission failed")
                        
                except Exception as e:
                    print(f"Error executing exit: {e}")
                    traceback.print_exc()
                    
            return False
            
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