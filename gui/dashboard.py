# gui/dashboard.py
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DashboardTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.figure = plt.Figure(figsize=(10, 6))
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.controls_frame = ttk.Frame(self)
        self.controls_frame.pack(fill=tk.X)
        
        ttk.Label(self.controls_frame, text="Symbol:").pack(side=tk.LEFT)
        self.symbol_var = tk.StringVar(value="AAPL")
        self.symbol_entry = ttk.Entry(self.controls_frame, textvariable=self.symbol_var)
        self.symbol_entry.pack(side=tk.LEFT)
        
        ttk.Label(self.controls_frame, text="Timeframe:").pack(side=tk.LEFT)
        self.timeframe_var = tk.StringVar(value="1D")
        self.timeframe_combo = ttk.Combobox(
            self.controls_frame,
            textvariable=self.timeframe_var,
            values=["1m", "5m", "15m", "1H", "1D"]
        )
        self.timeframe_combo.pack(side=tk.LEFT)
