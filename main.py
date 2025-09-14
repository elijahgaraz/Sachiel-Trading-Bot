# main.py
import tkinter as tk
from tkinter import ttk
import sys
import os
import asyncio
import threading
from datetime import datetime
import traceback

from gui.trading import TradingTab
from gui.settings import SettingsTab
from gui.sachiel_ai import SachielAITab
from gui.performance import PerformanceTab
from gui.chart_tab import ChartTab
from trading.ctrader_client import CTraderClient

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Set up async event loop
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

        self.title("Sachiel Trading Bot")
        self.geometry("1200x800")
        
        # Initialize cTrader Client
        try:
            self.ctrader_client = CTraderClient()
            if self.ctrader_client.connect():
                print("Successfully connected to cTrader")
            else:
                print("Failed to connect to cTrader")
        except Exception as e:
            print(f"Error initializing cTrader client: {e}")
            traceback.print_exc()
            self.ctrader_client = None
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create tabs with shared cTrader client
        self.trading_tab = TradingTab(self.notebook)
        if hasattr(self.trading_tab, 'ctrader_client'):
            self.trading_tab.ctrader_client = self.ctrader_client
            
        self.settings_tab = SettingsTab(self.notebook)
        self.ai_tab = SachielAITab(self.notebook)
        self.performance_tab = PerformanceTab(self.notebook)
        self.chart_tab = ChartTab(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.trading_tab, text='Trading')
        self.notebook.add(self.performance_tab, text='Performance')
        self.notebook.add(self.chart_tab, text='Chart')
        self.notebook.add(self.ai_tab, text='Sachiel AI')
        self.notebook.add(self.settings_tab, text='Settings')
        
        # Set style
        self.style = ttk.Style()
        self.style.configure('TNotebook.Tab', padding=[12, 4])
        
        # Set up closing handler
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start periodic connection check
        self.check_connection()

    def _run_event_loop(self):
        """Run the event loop in the background thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def check_connection(self):
        """Periodically check cTrader connection"""
        try:
            if self.ctrader_client:
                is_connected = self.ctrader_client.check_connection()
                if not is_connected:
                    print("Lost connection to cTrader, attempting to reconnect...")
                    self.ctrader_client.connect()
            else:
                print("No cTrader client, attempting to initialize...")
                self.ctrader_client = CTraderClient()
                self.ctrader_client.connect()
                
                # Update trading tab's client reference
                if hasattr(self.trading_tab, 'ctrader_client'):
                    self.trading_tab.ctrader_client = self.ctrader_client
                    
        except Exception as e:
            print(f"Error in connection check: {e}")
            
        finally:
            # Schedule next check in 30 seconds
            self.after(30000, self.check_connection)

    def on_closing(self):
        """Clean up resources before closing"""
        try:
            print("Shutting down application...")
            
            # Stop the async event loop
            if hasattr(self, 'loop') and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Wait for the thread to finish
            if hasattr(self, 'thread'):
                self.thread.join(timeout=1.0)
            
            # Close cTrader client
            if self.ctrader_client:
                self.ctrader_client.close()
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            traceback.print_exc()
        finally:
            self.quit()

    def run(self):
        """Start the application"""
        try:
            self.mainloop()
        except KeyboardInterrupt:
            print("Application closed by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
            traceback.print_exc()
        finally:
            self.on_closing()

def main():
    try:
        # Add the project root directory to Python path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(project_root)
        
        # Create and run the application
        app = MainApp()
        app.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()