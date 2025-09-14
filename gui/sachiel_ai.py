# gui/sachiel_ai.py
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time
from datetime import datetime, timedelta
import pytz
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.historical import StockHistoricalDataClient
import queue
import traceback
from trading.alpaca_client import AlpacaClient
import pandas as pd
import numpy as np

class SachielAITab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.ai_core = None
        self.training_thread = None
        self.should_stop_training = False
        self.message_queue = queue.Queue()
        self.params = {
            'confidence_threshold': 0.6,
            'stop_loss': 0.02,
            'take_profit': 0.04,
            'position_size': 100,
            'volatility_threshold': 0.02,
            'volume_threshold': 1.2,
            'stop_loss_multiplier': 1.0,
            'position_size_multiplier': 1.0
        }
        self.setup_ui()
        self.setup_live_ai_analysis()
        self.load_existing_settings()
        self.message_queue = queue.Queue()
        self.start_message_checking()

    def setup_ui(self):
        """Setup enhanced UI for Sachiel AI"""
        # Create main container with scrollbar
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Add canvas for scrolling
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack the scroll components
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Main Controls Section
        main_controls = ttk.LabelFrame(scrollable_frame, text="AI Configuration")
        main_controls.pack(fill=tk.X, padx=10, pady=5)

        # Create grid layout for controls
        grid_frame = ttk.Frame(main_controls)
        grid_frame.pack(fill=tk.X, padx=10, pady=5)

        # Risk Level Selection with better layout
        ttk.Label(grid_frame, text="Risk Level:", font=('SF Pro', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.risk_level = ttk.Combobox(
            grid_frame,
            values=["safe", "medium", "aggressive"],
            state="readonly",
            width=20
        )
        self.risk_level.set("medium")
        self.risk_level.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        # Training Period with explanation
        ttk.Label(grid_frame, text="Training Period (days):", font=('SF Pro', 10, 'bold')).grid(row=1, column=0, padx=5, pady=5, sticky='e')
        period_frame = ttk.Frame(grid_frame)
        period_frame.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        self.training_period = ttk.Entry(period_frame, width=10)
        self.training_period.pack(side=tk.LEFT)
        self.training_period.insert(0, "30")
        
        ttk.Label(period_frame, text="(Recommended: 30-90 days)", font=('SF Pro', 9)).pack(side=tk.LEFT, padx=5)

        # Training Control Buttons with better spacing
        button_frame = ttk.Frame(main_controls)
        button_frame.pack(pady=10)

        self.train_button = ttk.Button(
            button_frame,
            text="Train AI Model",
            command=self.start_training,
            width=20,
            style='Accent.TButton'
        )
        self.train_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Training",
            command=self.stop_training,
            width=15,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Training Status Section
        status_frame = ttk.LabelFrame(scrollable_frame, text="Training Status")
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="Not initialized", font=('SF Pro', 10))
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

        progress_frame = ttk.Frame(status_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            length=300
        )
        self.progress_bar.pack(fill=tk.X)

        # Analysis Controls Section
        analysis_frame = ttk.LabelFrame(scrollable_frame, text="Market Analysis")
        analysis_frame.pack(fill=tk.X, padx=10, pady=5)

        # Symbol Selection with better layout
        symbol_frame = ttk.Frame(analysis_frame)
        symbol_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(symbol_frame, text="Symbol:", font=('SF Pro', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.symbol_var = tk.StringVar()
        self.symbol_entry = ttk.Entry(symbol_frame, textvariable=self.symbol_var, width=15)
        self.symbol_entry.pack(side=tk.LEFT, padx=5)

        self.analyze_button = ttk.Button(
            symbol_frame,
            text="Analyze Symbol",
            command=self.analyze_symbol,
            width=15
        )
        self.analyze_button.pack(side=tk.LEFT, padx=5)

        # Results Section with Tabs
        results_notebook = ttk.Notebook(scrollable_frame)
        results_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Basic Analysis Tab
        basic_frame = ttk.Frame(results_notebook)
        results_notebook.add(basic_frame, text="Basic Analysis")

        self.feedback_tree = ttk.Treeview(basic_frame, columns=("Parameter", "Value"), show="headings", height=6)
        self.feedback_tree.heading("Parameter", text="Parameter")
        self.feedback_tree.heading("Value", text="Value")
        self.feedback_tree.column("Parameter", width=150)
        self.feedback_tree.column("Value", width=150)
        
        feedback_scrollbar = ttk.Scrollbar(basic_frame, orient=tk.VERTICAL, command=self.feedback_tree.yview)
        self.feedback_tree.configure(yscrollcommand=feedback_scrollbar.set)
        
        self.feedback_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        feedback_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Detailed Analysis Tab
        detailed_frame = ttk.Frame(results_notebook)
        results_notebook.add(detailed_frame, text="Detailed Analysis")

        self.live_analysis_tree = ttk.Treeview(detailed_frame, columns=("Metric", "Value"), show="headings", height=8)
        self.live_analysis_tree.heading("Metric", text="Metric")
        self.live_analysis_tree.heading("Value", text="Value")
        self.live_analysis_tree.column("Metric", width=150)
        self.live_analysis_tree.column("Value", width=150)
        
        detailed_scrollbar = ttk.Scrollbar(detailed_frame, orient=tk.VERTICAL, command=self.live_analysis_tree.yview)
        self.live_analysis_tree.configure(yscrollcommand=detailed_scrollbar.set)
        
        self.live_analysis_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detailed_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Bind arrow keys for scrolling
        self.bind_all("<Up>", lambda e: canvas.yview_scroll(-1, "units"))
        self.bind_all("<Down>", lambda e: canvas.yview_scroll(1, "units"))

        # Make the canvas expand with the window
        self.pack_propagate(False)
        canvas.pack(expand=True, fill=tk.BOTH)

        # Start auto-updates
        self.start_auto_updates()

    def setup_live_ai_analysis(self):
        """Create a section for Live AI Analysis"""
        live_analysis_frame = ttk.LabelFrame(self, text="Live AI Analysis")
        live_analysis_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.live_analysis_tree = ttk.Treeview(live_analysis_frame, columns=("Metric", "Value"), show="headings")
        self.live_analysis_tree.heading("Metric", text="Metric")
        self.live_analysis_tree.heading("Value", text="Value")
        self.live_analysis_tree.column("Metric", width=150)
        self.live_analysis_tree.column("Value", width=150)
        self.live_analysis_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for the treeview
        scrollbar = ttk.Scrollbar(live_analysis_frame, orient=tk.VERTICAL, command=self.live_analysis_tree.yview)
        self.live_analysis_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def load_existing_settings(self):
        """Load existing AI settings from a file"""
        try:
            config_dir = os.path.expanduser('~/.sachiel_trading')
            config_file = os.path.join(config_dir, 'ai_settings.json')
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    settings = json.load(f)
                
                # Apply loaded settings to UI elements
                if 'risk_level' in settings:
                    self.risk_level.set(settings['risk_level'])
                    
                if 'training_period' in settings:
                    # For Entry widgets, use delete and insert
                    self.training_period.delete(0, tk.END)
                    self.training_period.insert(0, str(settings['training_period']))
                
                print("AI settings loaded successfully")
            else:
                print("No existing AI settings found")
        
        except Exception as e:
            print(f"Error loading AI settings: {e}")
    
    def analyze_symbol(self):
        symbol = self.symbol_var.get().upper()
        if not symbol:
            messagebox.showwarning("Warning", "Please enter a symbol")
            return

        # Clear existing trees
        for item in self.feedback_tree.get_children():
            self.feedback_tree.delete(item)
        for item in self.live_analysis_tree.get_children():
            self.live_analysis_tree.delete(item)

        # Get AI signals
        result = self.get_ai_signals(symbol)
        if result and 'signals' in result:
            signals = result['signals']
            
            # Basic feedback display
            self.feedback_tree.insert("", "end", values=("Symbol", symbol))
            self.feedback_tree.insert("", "end", values=("Should Trade", "Yes" if signals['should_trade'] else "No"))
            self.feedback_tree.insert("", "end", values=("Confidence", f"{signals['confidence']:.2%}"))
            self.feedback_tree.insert("", "end", values=("Stop Loss", f"{signals['stop_loss']:.2%}"))
            self.feedback_tree.insert("", "end", values=("Take Profit", f"{signals['take_profit']:.2%}"))
            self.feedback_tree.insert("", "end", values=("Position Size", signals['position_size']))

            # Detailed live analysis display
            self.live_analysis_tree.insert("", "end", values=("Decision", "TRADE NOW" if signals['should_trade'] else "DO NOT TRADE"))
            self.live_analysis_tree.insert("", "end", values=("Overall Confidence", f"{signals['confidence']:.2%}"))
            
            if hasattr(self, 'latest_price'):
                self.live_analysis_tree.insert("", "end", values=("Current Price", f"${self.latest_price:.2f}"))
                self.live_analysis_tree.insert("", "end", values=("Stop Loss Level", f"${self.latest_price * (1-signals['stop_loss']):.2f} ({signals['stop_loss']:.2%})"))
                self.live_analysis_tree.insert("", "end", values=("Take Profit Level", f"${self.latest_price * (1+signals['take_profit']):.2f} ({signals['take_profit']:.2%})"))
            
            self.live_analysis_tree.insert("", "end", values=("Recommended Position", signals['position_size']))
            
            # Parse and display the reason components
            reason_parts = signals['reason'].split()
            self.live_analysis_tree.insert("", "end", values=("", ""))  # Spacer
            self.live_analysis_tree.insert("", "end", values=("Analysis Components", "Score"))
            
            for part in reason_parts:
                if ':' in part:
                    metric, value = part.split(':')
                    try:
                        score = float(value)
                        self.live_analysis_tree.insert("", "end", values=(metric, f"{score:.2%}"))
                    except ValueError:
                        continue
            
            # Market conditions if available
            if hasattr(self, 'market_analysis') and self.market_analysis:
                self.live_analysis_tree.insert("", "end", values=("", ""))  # Spacer
                self.live_analysis_tree.insert("", "end", values=("Market Conditions", "Status"))
                self.live_analysis_tree.insert("", "end", values=("Market Type", self.market_analysis.get('market_type', 'N/A')))
                self.live_analysis_tree.insert("", "end", values=("Trend Strength", self.market_analysis.get('trend_strength', 'N/A')))
                self.live_analysis_tree.insert("", "end", values=("Volume Profile", self.market_analysis.get('volume_profile', 'N/A')))
                
        else:
            self.feedback_tree.insert("", "end", values=("Error", "Could not analyze symbol"))
            self.live_analysis_tree.insert("", "end", values=("Error", "Could not analyze symbol"))   
    def get_ai_signals(self, symbol):
        if not self.ai_core:
            print("AI not trained - using advanced signal generation")
        
        try:
            # Identify crypto and format symbol
            is_crypto = 'BTC' in symbol or 'ETH' in symbol
            formatted_symbol = 'BTC/USD' if 'BTC' in symbol else symbol
            print(f"Getting signals for {formatted_symbol} (is_crypto: {is_crypto})")

            client = AlpacaClient()
            if not client.connect():
                print("Failed to connect to Alpaca")
                return None

            if is_crypto:
                print(f"Generating crypto signals for {formatted_symbol}")
                # Get data for analysis
                data = client.get_bars(symbol, is_crypto=True)
            else:
                print(f"Fetching data for {symbol}")
                data = client.get_bars(symbol, is_crypto=False)
            
            if not data:
                print(f"No data received for {symbol}")
                return self._get_default_signals(symbol)

            print(f"Creating DataFrame from {len(data)} bars")
            df = pd.DataFrame([{
                'close': bar.close,
                'high': bar.high,
                'low': bar.low,
                'open': bar.open,
                'volume': bar.volume,
                'timestamp': bar.timestamp
            } for bar in data])
            
            if len(df) < 2:
                print(f"Insufficient data points: {len(df)}")
                return self._get_default_signals(symbol)

            # Calculate technical indicators
            df = self.calculate_technical_indicators(df)
            
            # Analyze market conditions
            market_analysis = self.analyze_market_conditions(df, symbol)
            
            # Adjust parameters based on market conditions
            adjusted_params = self.adjust_parameters(market_analysis)
            if adjusted_params:
                self.params.update(adjusted_params)

            # Get trading signals
            signals = self.get_trading_signals(df)
            
            if signals:
                print("\nSignal Analysis Summary:")
                print(f"Should Trade: {signals['should_trade']}")
                print(f"Confidence: {signals['confidence']:.2f}")
                print(f"Stop Loss: {signals['stop_loss']:.2%}")
                print(f"Take Profit: {signals['take_profit']:.2%}")
                print(f"Position Size: {signals['position_size']}")
                print(f"Reason: {signals['reason']}")
                
                return {'signals': signals}
            
            return self._get_default_signals(symbol)
        
            # Store market analysis and latest price for use in analyze_symbol
            self.market_analysis = market_analysis
            if len(df) > 0:
                self.latest_price = df['close'].iloc[-1]

            return {'signals': signals}

        except Exception as e:
            print(f"Error getting AI signals: {str(e)}")
            traceback.print_exc()
            return self._get_default_signals(symbol)

    def calculate_technical_indicators(self, df):
        """Calculate comprehensive technical indicators"""
        try:
            # Moving Averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (std * 2)
            df['bb_lower'] = df['bb_middle'] - (std * 2)
            
            # Average True Range (ATR)
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()
            
            # Volume Analysis
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            return df
            
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            traceback.print_exc()
            return df

    def analyze_market_conditions(self, df, symbol):
        """Analyze overall market conditions"""
        try:
            # Volatility Analysis
            daily_returns = df['close'].pct_change()
            volatility = daily_returns.std()
            
            # Volume Analysis
            avg_volume = df['volume'].mean()
            recent_volume = df['volume'].iloc[-5:].mean()
            volume_trend = recent_volume / avg_volume
            
            # Trend Strength
            price_trend = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
            
            # Market Type Classification
            market_conditions = {
                'high_volatility': volatility > 0.02,
                'increasing_volume': volume_trend > 1.2,
                'strong_trend': abs(price_trend) > 0.05,
                'breakout_potential': df['close'].iloc[-1] > df['bb_upper'].iloc[-1],
                'support_level': df['close'].iloc[-1] < df['bb_lower'].iloc[-1]
            }
            
            # Adjust strategy based on market conditions
            if market_conditions['high_volatility']:
                self.params['stop_loss_multiplier'] = 1.5
                self.params['position_size_multiplier'] = 0.8
            else:
                self.params['stop_loss_multiplier'] = 1.0
                self.params['position_size_multiplier'] = 1.0
                
            # Market specific adjustments
            if 'BTC' in symbol or 'ETH' in symbol:
                self.params['volatility_threshold'] = 0.03
                self.params['volume_threshold'] = 1.5
            else:
                self.params['volatility_threshold'] = 0.02
                self.params['volume_threshold'] = 1.2
                
            return {
                'market_type': 'volatile' if market_conditions['high_volatility'] else 'normal',
                'trend_strength': 'strong' if market_conditions['strong_trend'] else 'weak',
                'volume_profile': 'increasing' if market_conditions['increasing_volume'] else 'normal',
                'volatility': volatility,
                'volume_trend': volume_trend,
                'price_trend': price_trend
            }
            
        except Exception as e:
            print(f"Error analyzing market conditions: {e}")
            traceback.print_exc()
            return None

    def adjust_parameters(self, market_analysis):
        """Adjust trading parameters based on market conditions"""
        try:
            if market_analysis:
                # Base parameters
                params = {
                    'confidence_threshold': 0.6,
                    'stop_loss': 0.02,
                    'take_profit': 0.04,
                    'position_size': 100
                }
                
                # Adjust based on market type
                if market_analysis['market_type'] == 'volatile':
                    params['confidence_threshold'] *= 1.2
                    params['stop_loss'] *= 1.5
                    params['take_profit'] *= 1.5
                    params['position_size'] *= 0.8
                    
                # Adjust based on trend strength
                if market_analysis['trend_strength'] == 'strong':
                    params['take_profit'] *= 1.2
                    params['position_size'] *= 1.2
                    
                # Adjust based on volume
                if market_analysis['volume_profile'] == 'increasing':
                    params['confidence_threshold'] *= 0.9
                    
                return params
                
            return None
            
        except Exception as e:
            print(f"Error adjusting parameters: {e}")
            traceback.print_exc()
            return None

    def get_trading_signals(self, df):
        """Generate trading signals based on multiple indicators"""
        try:
            latest = df.iloc[-1]
            
            # Trend Signals
            trend_signals = {
                'above_sma20': latest['close'] > latest['sma_20'],
                'above_sma50': latest['close'] > latest['sma_50'],
                'golden_cross': latest['sma_20'] > latest['sma_50'],
                'macd_positive': latest['macd_hist'] > 0,
                'bb_position': (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
            }
            
            # Momentum Signals
            momentum_signals = {
                'rsi_bullish': 30 < latest['rsi'] < 70,
                'volume_confirming': latest['volume_ratio'] > 1.0,
                'macd_trending': latest['macd'] > latest['macd_signal']
            }
            
            # Risk Metrics
            volatility = latest['atr'] / latest['close']
            risk_signals = {
                'volatility_acceptable': volatility < 0.02,
                'bb_not_extreme': 0.1 < trend_signals['bb_position'] < 0.9
            }
            
            # Calculate overall confidence
            trend_score = sum(trend_signals.values()) / len(trend_signals)
            momentum_score = sum(momentum_signals.values()) / len(momentum_signals)
            risk_score = sum(risk_signals.values()) / len(risk_signals)
            
            # Weight the scores
            confidence = (trend_score * 0.4 + momentum_score * 0.4 + risk_score * 0.2)
            
            # Decision making
            should_trade = (
                confidence > 0.6 and
                trend_signals['above_sma20'] and
                momentum_signals['rsi_bullish'] and
                risk_signals['volatility_acceptable']
            )
            
            return {
                'should_trade': should_trade,
                'confidence': confidence,
                'stop_loss': max(volatility * 2, 0.02),
                'take_profit': max(volatility * 4, 0.04),
                'position_size': int(100 * confidence) if should_trade else 0,
                'reason': f"Trend:{trend_score:.2f} Momentum:{momentum_score:.2f} Risk:{risk_score:.2f}"
            }
            
        except Exception as e:
            print(f"Error generating signals: {e}")
            traceback.print_exc()
            return None

    def _get_default_signals(self, symbol):
        """Get default signals when analysis fails"""
        print(f"Using default signals for {symbol}")
        is_crypto = 'BTC' in symbol or 'ETH' in symbol
        
        if is_crypto:
            return {
                'signals': {
                    'should_trade': False,
                    'confidence': 0.0,
                    'stop_loss': 0.03,  # Higher stop loss for crypto
                    'take_profit': 0.06,
                    'position_size': 0,
                    'reason': "Using default crypto signals"
                }
            }
        else:
            return {
                'signals': {
                    'should_trade': False,
                    'confidence': 0.0,
                    'stop_loss': 0.02,
                    'take_profit': 0.04,
                    'position_size': 0,
                    'reason': "Using default stock signals"
                }
            }

    def start_auto_updates(self):
        """Start automatic updates for the current symbol"""
        if hasattr(self, 'update_job'):
            self.after_cancel(self.update_job)
        
        def update():
            if self.symbol_var.get():  # Only update if we have a symbol
                self.analyze_symbol()
            self.update_job = self.after(30000, update)  # Update every 30 seconds
        
        self.update_job = self.after(0, update)

    def stop_auto_updates(self):
        """Stop automatic updates"""
        if hasattr(self, 'update_job'):
            self.after_cancel(self.update_job)
            del self.update_job
    def start_message_checking(self):
        """Start checking for queued messages"""
        def check_messages():
            try:
                while True:
                    try:
                        msg_type, msg = self.message_queue.get_nowait()
                        if msg_type == 'status':
                            self.status_label.config(text=msg)
                        elif msg_type == 'progress':
                            self.progress_var.set(msg)
                        elif msg_type == 'error':
                            messagebox.showerror("Error", msg)
                    except queue.Empty:
                        break
            finally:
                if self.winfo_exists():
                    self.after(100, check_messages)

        self.after(100, check_messages)

    def queue_message(self, msg_type, msg):
        """Queue a message to be processed in the main thread"""
        self.message_queue.put((msg_type, msg))

    def start_training(self):
        try:
            training_days = int(self.training_period.get())
            if training_days <= 0:
                raise ValueError("Training period must be positive")

            self.train_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            # Initialize new AI core with selected risk level
            self.ai_core = True  # Placeholder for actual AI core
            
            # Start training in separate thread
            self.should_stop_training = False
            self.training_thread = threading.Thread(target=self.train_ai_thread)
            self.training_thread.daemon = True
            self.training_thread.start()

        except ValueError as e:
            messagebox.showerror("Error", str(e))
            self.train_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def stop_training(self):
        self.should_stop_training = True
        self.stop_button.config(state=tk.DISABLED)
        self.queue_message('status', "Stopping training...")

    def train_ai_thread(self):
        """Training thread that avoids direct GUI updates"""
        try:
            client = AlpacaClient()
            
            self.queue_message('status', "Connecting to Alpaca...")
            self.queue_message('progress', 10)
            
            client.connect()
            
            if self.should_stop_training:
                raise InterruptedError("Training cancelled")
                
            self.queue_message('status', "Fetching market data...")
            self.queue_message('progress', 30)
            
            clock = client.trading_client.get_clock()
            end = clock.timestamp
            start = end - timedelta(days=int(self.training_period.get()))
            
            # Simulate training progress
            self.queue_message('status', "Training model...")
            for i in range(30, 100, 10):
                if self.should_stop_training:
                    raise InterruptedError("Training cancelled")
                self.queue_message('progress', i)
                time.sleep(0.5)  # Simulate work
            
            self.queue_message('status', "Training complete!")
            self.queue_message('progress', 100)
            
            # Save settings
            self.save_settings()
            
        except Exception as e:
            self.queue_message('error', f"Training error: {str(e)}")
            self.ai_core = None
        finally:
            if self.winfo_exists():
                self.after(0, self.reset_ui_after_training)

    def reset_ui_after_training(self):
        """Reset UI elements after training"""
        self.train_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def save_settings(self):
        """Save AI settings and parameters"""
        try:
            settings = {
                'risk_level': self.risk_level.get(),
                'training_period': self.training_period.get(),
                'last_training': datetime.now(pytz.UTC).isoformat(),
                'status': 'trained' if self.ai_core else 'untrained'
            }
            
            config_dir = os.path.expanduser('~/.sachiel_trading')
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            with open(os.path.join(config_dir, 'ai_settings.json'), 'w') as f:
                json.dump(settings, f)
                
            print("AI settings saved successfully")
            return True
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            traceback.print_exc()
            return False

    def load_settings(self):
        """Load saved AI settings"""
        try:
            settings_file = os.path.expanduser('~/.sachiel_trading/ai_settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    
                self.risk_level.set(settings.get('risk_level', 'medium'))
                
                # For Entry widgets, use delete and insert
                self.training_period.delete(0, tk.END)
                self.training_period.insert(0, settings.get('training_period', '30'))
                
        except Exception as e:
            print(f"Error loading settings: {e}")
            traceback.print_exc()