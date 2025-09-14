# gui/app.py
import tkinter as tk
from tkinter import ttk
import platform
from gui.dashboard import DashboardTab
from gui.trading import TradingTab
from gui.chart_tab import ChartTab
from gui.performance import PerformanceTab
from gui.settings import SettingsTab
from gui.sachiel_ai import SachielAITab

class TradingApp:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_style()
        self.create_notebook()

    def setup_window(self):
        # Set window size and position
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = int(screen_width * 0.8)
        height = int(screen_height * 0.8)
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        self.root.minsize(800, 600)  # Set minimum window size
        
        # Set window title
        self.root.title("Sachiel Trading Bot")

    def setup_style(self):
        style = ttk.Style()
        if platform.system() == 'Darwin':  # macOS specific
            style.theme_use('aqua')
            
            # Configure styles
            style.configure('TNotebook', tabmargins=[2, 5, 2, 0])
            style.configure('TNotebook.Tab', padding=[15, 5])
            style.configure('TFrame', background='systemWindowBackgroundColor')
            style.configure('TLabel', padding=[5, 5])
            style.configure('TButton', padding=[10, 5])
            style.configure('TEntry', padding=[5, 2])

    def create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        
        # Create tabs
        self.dashboard_tab = DashboardTab(self.notebook)
        self.trading_tab = TradingTab(self.notebook)
        self.chart_tab = ChartTab(self.notebook)
        self.performance_tab = PerformanceTab(self.notebook)
        self.settings_tab = SettingsTab(self.notebook)
        self.sachiel_tab = SachielAITab(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.trading_tab, text="Trading")
        self.notebook.add(self.chart_tab, text="Charts")
        self.notebook.add(self.performance_tab, text="Performance")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.sachiel_tab, text="Sachiel AI")
        
        self.notebook.pack(expand=True, fill="both")

"""if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()"""