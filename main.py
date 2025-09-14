# main.py
"""
Sachiel Trading Bot - Tkinter + Twisted (asyncio reactor) bootstrap

Key changes:
- Install Twisted's asyncio reactor BEFORE importing any module that might touch `twisted.internet.reactor`.
- Create one global asyncio event loop and reuse it everywhere.
- Remove duplicate reactor installation from MainApp; just reuse the global loop.
"""

# --- Absolutely first: set up asyncio + Twisted reactor -----------------------------------------
import sys
import os
import asyncio

# Create a single global event loop for the entire app
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)

# Install Twisted's asyncio reactor BEFORE any other imports that might pull in `reactor`
from twisted.internet import asyncioreactor

if "twisted.internet.reactor" not in sys.modules:
    asyncioreactor.install(eventloop=LOOP)
else:
    # If some import already installed a reactor, make sure it's the asyncio one
    from twisted.internet import reactor as _reactor  # noqa: E402
    if _reactor.__class__.__name__ != "AsyncioSelectorReactor":
        raise SystemExit(
            "A non-asyncio Twisted reactor was already installed before main.py ran. "
            "Ensure main.py is your entry point and reactor is installed first."
        )

# --- Standard/library & UI imports (safe after reactor install) ---------------------------------
import threading
import traceback
import tkinter as tk
from tkinter import ttk

# --- Project imports (safe after reactor install) -----------------------------------------------
# If running this file directly, ensure project root is on sys.path so the `gui/` and `trading/` packages resolve
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT_ROOT = os.path.dirname(PROJECT_ROOT)
if PARENT_ROOT not in sys.path:
    sys.path.append(PARENT_ROOT)

from gui.trading import TradingTab
from gui.settings import SettingsTab
from gui.sachiel_ai import SachielAITab
from gui.performance import PerformanceTab
from gui.chart_tab import ChartTab
from trading.ctrader_client import CTraderClient


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Reuse the already-created global asyncio loop
        self.loop = LOOP

        # Run the asyncio loop in a background thread so Tk can own the main thread
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

        # --- Window basics ---
        self.title("Sachiel Trading Bot")
        self.geometry("1200x800")

        # --- cTrader client (not connected yet) ---
        self.ctrader_client = CTraderClient(
            on_account_update=self.update_account_info_ui,
            on_status_update=self.update_connection_status_ui,
        )

        # --- Tabs ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=5, pady=5)

        # Create tabs
        self.trading_tab = TradingTab(self.notebook)
        # Set the cTrader client for the trading tab
        self.trading_tab.set_ctrader_client(self.ctrader_client)

        self.settings_tab = SettingsTab(self.notebook, self.ctrader_client)
        self.ai_tab = SachielAITab(self.notebook)
        self.performance_tab = PerformanceTab(self.notebook)
        self.chart_tab = ChartTab(self.notebook)

        # Add tabs to the notebook
        self.notebook.add(self.trading_tab, text="Trading")
        self.notebook.add(self.performance_tab, text="Performance")
        self.notebook.add(self.chart_tab, text="Chart")
        self.notebook.add(self.ai_tab, text="Sachiel AI")
        self.notebook.add(self.settings_tab, text="Settings")

        # Styling
        self.style = ttk.Style()
        self.style.configure("TNotebook.Tab", padding=[12, 4])

        # Window close handler
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- UI callback helpers (scheduled onto Tk thread with after) -------------------------------
    def update_account_info_ui(self, summary: dict):
        """Callback to update the UI with account information."""
        def do_update():
            if hasattr(self, "settings_tab") and self.settings_tab.winfo_exists():
                balance = summary.get("balance")
                if balance is not None:
                    self.settings_tab.account_frame.pack(fill=tk.X, padx=5, pady=5)
                    self.settings_tab.account_balance.config(text=f"Balance: £{balance:,.2f}")
                else:
                    self.settings_tab.account_frame.pack_forget()

        self.after(0, do_update)

    def update_connection_status_ui(self, status: str, color: str):
        """
        Callback to update the UI with connection status.
        Called from network thread; schedule onto Tk main thread.
        """
        def do_update():
            if hasattr(self, "settings_tab") and self.settings_tab.winfo_exists():
                self.settings_tab.connection_status.config(text=status, foreground=color)
                self.settings_tab.status_label.config(text=f"Status: {status}", foreground=color)
                if status == "Connected":
                    self.settings_tab.disconnect_button.config(state=tk.NORMAL)
                    self.trading_tab.load_symbols_if_connected()
                else:
                    self.settings_tab.disconnect_button.config(state=tk.DISABLED)

        self.after(0, do_update)

    # --- Async loop thread runner ----------------------------------------------------------------
    def _run_event_loop(self):
        """Run the asyncio event loop in a background thread."""
        try:
            asyncio.set_event_loop(self.loop)
            if not self.loop.is_running():
                self.loop.run_forever()
        except Exception as e:
            print(f"Async loop error: {e}")
            traceback.print_exc()

    # --- Shutdown / cleanup ----------------------------------------------------------------------
    def on_closing(self):
        """Clean up resources before closing."""
        try:
            print("Shutting down application...")

            # Close cTrader client first to stop network activity
            try:
                if getattr(self, "ctrader_client", None):
                    self.ctrader_client.close()
            except Exception as e:
                print(f"Error closing cTrader client: {e}")

            # Stop the asyncio loop
            if hasattr(self, "loop") and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)

            # Wait briefly for the loop thread
            if hasattr(self, "thread") and self.thread.is_alive():
                self.thread.join(timeout=1.0)

        except Exception as e:
            print(f"Error during cleanup: {e}")
            traceback.print_exc()
        finally:
            try:
                # Destroy Tk window
                self.destroy()
            except Exception:
                pass

    # --- Tk mainloop wrapper ---------------------------------------------------------------------
    def run(self):
        try:
            self.mainloop()
        except KeyboardInterrupt:
            print("Application closed by user.")
        except Exception as e:
            print(f"Error in main loop: {e}")
            traceback.print_exc()
        finally:
            # Ensure cleanup runs even if mainloop bails
            self.on_closing()


# --- Entrypoint ---------------------------------------------------------------------------------
def main():
    try:
        app = MainApp()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
