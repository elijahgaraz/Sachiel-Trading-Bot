# gui/performance.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import traceback

class PerformanceTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.metrics = {}
        self.trades_cache = []
        self.last_update = None
        self.setup_ui()
        self.start_auto_update()

    def setup_ui(self):
        """Enhanced UI setup with more detailed metrics"""
        # Main container
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Summary metrics frame
        metrics_frame = ttk.LabelFrame(main_container, text="Performance Summary")
        metrics_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Create metrics display with scrollbar
        tree_frame = ttk.Frame(metrics_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.metrics_tree = ttk.Treeview(
            tree_frame,
            columns=("Metric", "Value", "Change"),
            show="headings",
            height=12
        )
        
        # Configure columns
        self.metrics_tree.heading("Metric", text="Metric")
        self.metrics_tree.heading("Value", text="Value")
        self.metrics_tree.heading("Change", text="24h Change")
        
        self.metrics_tree.column("Metric", width=200)
        self.metrics_tree.column("Value", width=150)
        self.metrics_tree.column("Change", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.metrics_tree.yview)
        self.metrics_tree.configure(yscrollcommand=scrollbar.set)
        
        self.metrics_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Controls frame
        controls_frame = ttk.Frame(metrics_frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Refresh button
        self.refresh_button = ttk.Button(
            controls_frame,
            text="Refresh Metrics",
            command=self.update_metrics
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Time range selector
        ttk.Label(controls_frame, text="Time Range:").pack(side=tk.LEFT, padx=(10, 5))
        self.time_range = ttk.Combobox(
            controls_frame,
            values=["Today", "24 Hours", "7 Days", "30 Days", "All Time"],
            state="readonly",
            width=10
        )
        self.time_range.set("24 Hours")
        self.time_range.pack(side=tk.LEFT, padx=5)
        self.time_range.bind('<<ComboboxSelected>>', lambda e: self.update_metrics())
        
        # Last update label
        self.last_update_label = ttk.Label(controls_frame, text="")
        self.last_update_label.pack(side=tk.RIGHT, padx=5)

    def get_trades(self):
        """Enhanced trade data collection"""
        try:
            trading_tab = None
            
            # Find trading tab
            notebook = self.parent
            for child in notebook.winfo_children():
                if child.winfo_name() == '!tradingtab':
                    trading_tab = child
                    break
                    
            if not trading_tab or not hasattr(trading_tab, 'trade_log'):
                print("Trading tab or trade log not found")
                return []

            trades = []
            for item in trading_tab.trade_log.get_children():
                values = trading_tab.trade_log.item(item)['values']
                if len(values) >= 8:  # Ensure we have all needed values
                    try:
                        trade_time = datetime.strptime(values[0], '%Y-%m-%d %H:%M:%S')
                        trades.append({
                            'time': trade_time,
                            'symbol': values[1],
                            'type': values[2],
                            'price': self.extract_price(values[3]),
                            'size': self.extract_size(values[4]),
                            'pl': self.extract_pl(values[5]),
                            'reason': values[6],
                            'confidence': values[7]
                        })
                    except Exception as e:
                        print(f"Error processing trade: {e}")
                        continue
            
            # Cache the trades
            self.trades_cache = trades
            return trades
            
        except Exception as e:
            print(f"Error getting trades: {e}")
            traceback.print_exc()
            return []

    def extract_size(self, size_str):
        """Extract numerical size from string"""
        try:
            if isinstance(size_str, (int, float)):
                return float(size_str)
            if size_str == '-':
                return 0.0
            return float(size_str.replace(',', ''))
        except:
            return 0.0

    def calculate_metrics(self, trades):
        """Enhanced metrics calculation"""
        try:
            # Get time range
            range_str = self.time_range.get()
            now = datetime.now()
            
            if range_str == "Today":
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif range_str == "24 Hours":
                start_time = now - timedelta(days=1)
            elif range_str == "7 Days":
                start_time = now - timedelta(days=7)
            elif range_str == "30 Days":
                start_time = now - timedelta(days=30)
            else:  # All Time
                start_time = datetime.min
                
            # Filter trades by time range
            filtered_trades = [t for t in trades if t['time'] >= start_time]
            closed_trades = [t for t in filtered_trades if t['type'] in ['SELL', 'STOP LOSS', 'TAKE PROFIT']]
            
            if not closed_trades:
                return self.get_default_metrics()

            # Calculate basic metrics
            pls = [t['pl'] for t in closed_trades]
            total_pl = sum(pls)
            winning_trades = [pl for pl in pls if pl > 0]
            losing_trades = [pl for pl in pls if pl < 0]
            
            # Calculate detailed metrics
            win_rate = len(winning_trades) / len(pls) if pls else 0
            avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0
            largest_win = max(winning_trades) if winning_trades else 0
            largest_loss = min(losing_trades) if losing_trades else 0
            
            # Calculate profit factor
            gross_profit = sum(winning_trades) if winning_trades else 0
            gross_loss = abs(sum(losing_trades)) if losing_trades else 0
            profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
            
            # Calculate risk metrics
            returns = pd.Series(pls)
            if len(returns) > 1:
                sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() != 0 else 0
                
                # Calculate Max Drawdown
                cumulative = returns.cumsum()
                running_max = cumulative.expanding().max()
                drawdowns = (cumulative - running_max) / running_max * 100
                max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0
            else:
                sharpe = 0
                max_drawdown = 0
                
            # Calculate 24h changes if we have previous metrics
            changes = self.calculate_changes(total_pl, win_rate, avg_win, avg_loss)

            return {
                "Total P/L": (f"£{total_pl:,.2f}", changes['pl']),
                "Win Rate": (f"{win_rate*100:.2f}%", changes['win_rate']),
                "Total Trades": (str(len(pls)), ""),
                "Winning Trades": (str(len(winning_trades)), ""),
                "Losing Trades": (str(len(losing_trades)), ""),
                "Average Win": (f"£{avg_win:,.2f}", changes['avg_win']),
                "Average Loss": (f"£{avg_loss:,.2f}", changes['avg_loss']),
                "Largest Win": (f"£{largest_win:,.2f}", ""),
                "Largest Loss": (f"£{largest_loss:,.2f}", ""),
                "Profit Factor": (f"{profit_factor:.2f}", ""),
                "Sharpe Ratio": (f"{sharpe:.2f}", ""),
                "Max Drawdown": (f"{max_drawdown:.2f}%", "")
            }
            
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            traceback.print_exc()
            return self.get_default_metrics()

    def get_default_metrics(self):
        """Return default metrics when no trades exist"""
        return {
            "Total P/L": ("£0.00", ""),
            "Win Rate": ("0.00%", ""),
            "Total Trades": ("0", ""),
            "Winning Trades": ("0", ""),
            "Losing Trades": ("0", ""),
            "Average Win": ("£0.00", ""),
            "Average Loss": ("£0.00", ""),
            "Largest Win": ("£0.00", ""),
            "Largest Loss": ("£0.00", ""),
            "Profit Factor": ("0.00", ""),
            "Sharpe Ratio": ("0.00", ""),
            "Max Drawdown": ("0.00%", "")
        }

    def calculate_changes(self, current_pl, current_win_rate, current_avg_win, current_avg_loss):
        """Calculate 24h changes in metrics"""
        try:
            # Get trades from 24-48 hours ago for comparison
            now = datetime.now()
            day_ago = now - timedelta(days=1)
            two_days_ago = now - timedelta(days=2)
            
            old_trades = [t for t in self.trades_cache 
                         if two_days_ago <= t['time'] <= day_ago and 
                         t['type'] in ['SELL', 'STOP LOSS', 'TAKE PROFIT']]
            
            if not old_trades:
                return {
                    'pl': "",
                    'win_rate': "",
                    'avg_win': "",
                    'avg_loss': ""
                }
                
            # Calculate old metrics
            old_pls = [t['pl'] for t in old_trades]
            old_pl = sum(old_pls)
            old_winning = [pl for pl in old_pls if pl > 0]
            old_losing = [pl for pl in old_pls if pl < 0]
            
            old_win_rate = len(old_winning) / len(old_pls) if old_pls else 0
            old_avg_win = sum(old_winning) / len(old_winning) if old_winning else 0
            old_avg_loss = sum(old_losing) / len(old_losing) if old_losing else 0
            
            # Calculate changes
            pl_change = ((current_pl - old_pl) / abs(old_pl) * 100) if old_pl != 0 else 0
            win_rate_change = (current_win_rate - old_win_rate) * 100
            avg_win_change = ((current_avg_win - old_avg_win) / old_avg_win * 100) if old_avg_win != 0 else 0
            avg_loss_change = ((current_avg_loss - old_avg_loss) / old_avg_loss * 100) if old_avg_loss != 0 else 0
            
            return {
                'pl': f"{'+' if pl_change >= 0 else ''}{pl_change:.1f}%",
                'win_rate': f"{'+' if win_rate_change >= 0 else ''}{win_rate_change:.1f}%",
                'avg_win': f"{'+' if avg_win_change >= 0 else ''}{avg_win_change:.1f}%",
                'avg_loss': f"{'+' if avg_loss_change >= 0 else ''}{avg_loss_change:.1f}%"
            }
            
        except Exception as e:
            print(f"Error calculating changes: {e}")
            return {'pl': "", 'win_rate': "", 'avg_win': "", 'avg_loss': ""}

    def update_metrics(self):
        """Update performance metrics display"""
        try:
            # Get trades
            trades = self.get_trades()
            
            # Calculate metrics
            metrics = self.calculate_metrics(trades)
            
            # Update display
            self.display_metrics(metrics)
            
            # Update last update time
            self.last_update = datetime.now()
            self.last_update_label.config(
                text=f"Last Update: {self.last_update.strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            print(f"Error updating metrics: {e}")
            traceback.print_exc()

    def display_metrics(self, metrics):
        """Display metrics with color coding"""
        try:
            # Clear current display
            for item in self.metrics_tree.get_children():
                self.metrics_tree.delete(item)
                
            # Add metrics with color coding
            for metric, (value, change) in metrics.items():
                # Determine color based on value type
                if 'P/L' in metric or 'Win' in metric or 'Loss' in metric:
                    if value.startswith('£'):
                        amount = float(value.replace('£', '').replace(',', ''))
                        tags = ('positive',) if amount > 0 else ('negative',) if amount < 0 else ()
                    elif value.endswith('%'):
                        amount = float(value.rstrip('%'))
                        tags = ('positive',) if amount > 50 else ('negative',) if amount < 50 else ()
                    else:
                        tags = ()
                else:
                    tags = ()
                
                self.metrics_tree.insert('', tk.END, values=(metric, value, change), tags=tags)
                
            # Configure tag colors
            self.metrics_tree.tag_configure('positive', foreground='green')
            self.metrics_tree.tag_configure('negative', foreground='red')
                
        except Exception as e:
            print(f"Error displaying metrics: {e}")
            traceback.print_exc()

    def start_auto_update(self):
            """Start automatic updates"""
            def update():
                if self.winfo_exists():
                    self.update_metrics()
                    # Schedule next update (every 30 seconds)
                    self.after(30000, update)
            
            # Start first update after 1 second
            self.after(1000, update)

    def extract_price(self, price_str):
        """Extract numerical price from string"""
        try:
            if isinstance(price_str, (int, float)):
                return float(price_str)
            if price_str == '-':
                return 0.0
            # Remove £ and , from string and convert to float
            return float(price_str.replace('£', '').replace(',', ''))
        except Exception as e:
            print(f"Error extracting price from {price_str}: {e}")
            return 0.0

    def extract_pl(self, pl_str):
        """Extract P/L value from string"""
        try:
            if isinstance(pl_str, (int, float)):
                return float(pl_str)
            if pl_str == '-':
                return 0.0
            # Handle different P/L string formats
            if '(' in pl_str:
                # Extract the pound amount before the parentheses
                pl_value = pl_str.split('(')[0].strip()
            else:
                pl_value = pl_str
            # Remove £ and , from string and convert to float
            return float(pl_value.replace('£', '').replace(',', ''))
        except Exception as e:
            print(f"Error extracting P/L from {pl_str}: {e}")
            return 0.0

    def format_change(self, old_value, new_value):
        """Format change percentage with color coding"""
        try:
            if old_value == 0:
                return "", None
            change = ((new_value - old_value) / abs(old_value)) * 100
            color = 'green' if change > 0 else 'red' if change < 0 else 'black'
            return f"{'+' if change > 0 else ''}{change:.1f}%", color
        except Exception as e:
            print(f"Error formatting change: {e}")
            return "", None

    def get_trading_tab(self):
        """Get reference to trading tab"""
        try:
            notebook = self.parent
            for child in notebook.winfo_children():
                if child.winfo_name() == '!tradingtab':
                    return child
            return None
        except Exception as e:
            print(f"Error getting trading tab: {e}")
            return None

    def format_metric(self, name, value, include_pound=True, include_percent=False):
        """Format metric value with appropriate symbols"""
        try:
            if value == 0:
                return "£0.00" if include_pound else "0.00%"
            if include_pound:
                return f"£{value:,.2f}"
            if include_percent:
                return f"{value:.2f}%"
            return f"{value:.2f}"
        except Exception as e:
            print(f"Error formatting metric {name}: {e}")
            return "0.00"

    def save_metrics(self):
        """Save current metrics for historical comparison"""
        try:
            self.previous_metrics = self.metrics.copy()
        except Exception as e:
            print(f"Error saving metrics: {e}")
            self.previous_metrics = {}