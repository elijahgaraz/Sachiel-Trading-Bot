# gui/chart_tab.py
import tkinter as tk
from tkinter import ttk
import mplfinance as mpf
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mpdates
from datetime import datetime, timedelta
import pytz
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest
import threading
import ta
import traceback

class ChartTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_symbol = None
        self.data = None
        self.setup_ui()
        self.updating = False
        self.setup_auto_update()

    def setup_ui(self):
        # Create main container that will expand
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Control Frame at the top
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Symbol selection
        ttk.Label(control_frame, text="Symbol:").pack(side=tk.LEFT, padx=5)
        self.symbol_var = tk.StringVar()
        self.symbol_entry = ttk.Entry(control_frame, textvariable=self.symbol_var, width=10)
        self.symbol_entry.pack(side=tk.LEFT, padx=5)
        
        # Timeframe selection
        ttk.Label(control_frame, text="Timeframe:").pack(side=tk.LEFT, padx=5)
        self.timeframe_var = tk.StringVar(value="1D")
        timeframe_combo = ttk.Combobox(
            control_frame,
            textvariable=self.timeframe_var,
            values=["1m", "5m", "15m", "1H", "1D"],
            width=5,
            state="readonly"
        )
        timeframe_combo.pack(side=tk.LEFT, padx=5)

        # Indicators Frame
        indicators_frame = ttk.LabelFrame(control_frame, text="Indicators")
        indicators_frame.pack(side=tk.LEFT, padx=20)

        # Checkboxes for indicators
        self.show_ma = tk.BooleanVar(value=True)
        ttk.Checkbutton(indicators_frame, text="Moving Averages", variable=self.show_ma, 
                    command=self.update_chart).pack(side=tk.LEFT, padx=5)

        self.show_bb = tk.BooleanVar(value=True)
        ttk.Checkbutton(indicators_frame, text="Bollinger Bands", variable=self.show_bb, 
                    command=self.update_chart).pack(side=tk.LEFT, padx=5)

        self.show_rsi = tk.BooleanVar(value=True)
        ttk.Checkbutton(indicators_frame, text="RSI", variable=self.show_rsi, 
                    command=self.update_chart).pack(side=tk.LEFT, padx=5)

        # Update button
        self.update_button = ttk.Button(control_frame, text="Update", command=self.update_data)
        self.update_button.pack(side=tk.RIGHT, padx=5)

        # Create chart frame that will expand
        self.chart_frame = ttk.Frame(main_container)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create initial blank figure with tight layout
        self.fig = Figure(figsize=(10, 8), tight_layout=True)
        self.fig.add_subplot(111).grid(True)
        
        # Create canvas that will expand
        self.canvas = FigureCanvasTkAgg(self.fig, self.chart_frame)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Add toolbar at the bottom
        toolbar_frame = ttk.Frame(main_container)
        toolbar_frame.pack(fill=tk.X, padx=5)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        
        # Bind events
        self.symbol_entry.bind('<Return>', lambda e: self.update_data())
        timeframe_combo.bind('<<ComboboxSelected>>', lambda e: self.update_data())
        
        # Bind resize event
        self.bind('<Configure>', self.on_resize)

    def on_resize(self, event):
        # Only handle resizes of the main window
        if event.widget == self:
            # Wait a bit before updating to avoid too many updates
            if hasattr(self, '_resize_job'):
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(100, self.update_chart_size)

    def update_chart_size(self):
        try:
            if hasattr(self, 'fig') and hasattr(self, 'canvas'):
                # Get the current size of the chart frame
                width = self.chart_frame.winfo_width()
                height = self.chart_frame.winfo_height()
                
                # Update figure size (in inches)
                dpi = self.fig.get_dpi()
                self.fig.set_size_inches(width/dpi, height/dpi)
                
                # Update layout
                self.fig.tight_layout()
                
                # Redraw canvas
                self.canvas.draw()
        except Exception as e:
            print(f"Error updating chart size: {e}")
            traceback.print_exc()
    
    def setup_auto_update(self):
        def auto_update():
            if self.winfo_exists() and not self.updating:
                self.update_data()
            if self.winfo_exists():
                self.after(30000, auto_update)  # Update every 30 seconds
        
        self.after(1000, auto_update)

    def update_data(self):
        if self.updating:
            return
                
        self.updating = True
        self.update_button.config(state='disabled')
        
        def fetch_data():
            try:
                symbol = self.symbol_var.get().upper()
                if not symbol:
                    return

                # Get market data
                from trading.alpaca_client import AlpacaClient
                client = AlpacaClient()
                client.connect()

                # Use known good historical date range
                end = datetime(2023, 12, 15, 16, 0, 0).replace(tzinfo=pytz.timezone('America/New_York'))
                start = end - timedelta(days=30)  # Get 30 days of data

                print(f"Fetching data for {symbol} from {start} to {end}")

                # Get bars directly from AlpacaClient
                bars = client.get_bars(symbol, is_crypto=('BTC' in symbol or 'ETH' in symbol))
                
                if bars and len(bars) > 0:
                    # Convert bars to DataFrame
                    df = pd.DataFrame([{
                        'open': float(b.open),
                        'high': float(b.high),
                        'low': float(b.low),
                        'close': float(b.close),
                        'volume': float(b.volume),
                        'timestamp': pd.to_datetime(b.timestamp)
                    } for b in bars])
                    
                    # Set timestamp as index
                    df.set_index('timestamp', inplace=True)
                    df.sort_index(inplace=True)
                    
                    # Convert any infinite values to NaN and drop them
                    df.replace([np.inf, -np.inf], np.nan, inplace=True)
                    df.dropna(inplace=True)
                    
                    print(f"Received {len(df)} bars")
                    print(f"Data range: {df.index.min()} to {df.index.max()}")
                    print("Sample data:")
                    print(df.head())
                    
                    if len(df) >= 2:  # Need at least 2 bars for plotting
                        self.data = df
                        self.current_symbol = symbol
                        self.after(0, self.update_chart)
                        print("Chart update scheduled")
                    else:
                        print("Not enough data points for plotting")
                else:
                    print("No bars received")

            except Exception as e:
                print(f"Error fetching data: {e}")
                traceback.print_exc()
            finally:
                self.updating = False
                if self.winfo_exists():
                    self.after(0, lambda: self.update_button.config(state='normal'))

        threading.Thread(target=fetch_data, daemon=True).start()

    def update_chart(self):
        try:
            if self.data is None or len(self.data) < 2:
                print("No data or insufficient data to plot")
                return

            print("Updating chart...")
            print(f"Data shape: {self.data.shape}")
            print("Data types:", self.data.dtypes)
            print("Data sample:", self.data.head())
            
            # Calculate technical indicators
            addplot = []  # List to store additional plots
            
            if self.show_ma.get():
                self.data['MA20'] = ta.trend.sma_indicator(self.data['close'], window=min(20, len(self.data)-1))
                self.data['MA50'] = ta.trend.sma_indicator(self.data['close'], window=min(50, len(self.data)-1))
                if not self.data['MA20'].isna().all():
                    addplot.append(mpf.make_addplot(self.data['MA20'], color='blue', label='MA20'))
                if not self.data['MA50'].isna().all():
                    addplot.append(mpf.make_addplot(self.data['MA50'], color='red', label='MA50'))

            if self.show_bb.get() and len(self.data) > 2:
                bb = ta.volatility.BollingerBands(self.data['close'], window=min(20, len(self.data)-1))
                self.data['BB_upper'] = bb.bollinger_hband()
                self.data['BB_lower'] = bb.bollinger_lband()
                if not self.data['BB_upper'].isna().all():
                    addplot.append(mpf.make_addplot(self.data['BB_upper'], color='gray', linestyle='--'))
                if not self.data['BB_lower'].isna().all():
                    addplot.append(mpf.make_addplot(self.data['BB_lower'], color='gray', linestyle='--'))

            if self.show_rsi.get() and len(self.data) > 2:
                self.data['RSI'] = ta.momentum.rsi(self.data['close'], window=min(14, len(self.data)-1))
                if not self.data['RSI'].isna().all():
                    addplot.append(mpf.make_addplot(self.data['RSI'], panel=2, color='purple', ylabel='RSI'))

            # Set up the style
            s = mpf.make_mpf_style(base_mpf_style='charles', gridstyle=':', gridaxis='both')
            
            # Create the plot
            kwargs = dict(
                type='candle',
                style=s,
                volume=True,
                addplot=addplot if addplot else None,
                returnfig=True,
                title=f'\n{self.current_symbol} - {self.timeframe_var.get()} Timeframe\n',
                tight_layout=True,
                figsize=(self.chart_frame.winfo_width()/100, self.chart_frame.winfo_height()/100)
             )
    
            if self.show_rsi.get() and not self.data['RSI'].isna().all():
                kwargs['panel_ratios'] = (6, 2, 2)  # Adjusted ratios for better visibility
            else:
                kwargs['panel_ratios'] = (6, 2)  # Adjusted ratios for better visibility
                    
            # Create the plot
            fig, axes = mpf.plot(
                self.data,
                **kwargs
            )

            # If RSI is shown, add horizontal lines at 30 and 70
            if self.show_rsi.get() and len(axes) > 2:
                rsi_ax = axes[2]
                rsi_ax.axhline(y=70, color='r', linestyle='--', alpha=0.5)
                rsi_ax.axhline(y=30, color='g', linestyle='--', alpha=0.5)
                rsi_ax.set_ylim(0, 100)

            # Update the canvas with the new figure
            self.canvas.figure = fig
            self.canvas.draw()
            
            print("Chart updated successfully")
            
        except Exception as e:
            print(f"Error updating chart: {e}")
            traceback.print_exc()