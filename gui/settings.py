# gui/settings.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings
from trading.ctrader_client import CTraderClient

class SettingsTab(ttk.Frame):
    def __init__(self, parent, settings: Settings, ctrader_client: CTraderClient):
        super().__init__(parent)
        self.settings = settings
        self.ctrader_client = ctrader_client
        self.setup_ui()
        self.load_settings_into_ui()
        
    def setup_ui(self):
        settings_frame = ttk.LabelFrame(self, text="cTrader API Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Client ID
        ttk.Label(settings_frame, text="Client ID:").grid(row=0, column=0, padx=5, pady=5)
        self.client_id = ttk.Entry(settings_frame, width=50, show="*")
        self.client_id.grid(row=0, column=1, padx=5, pady=5)
        
        # Show/Hide Client ID
        self.show_client_id = ttk.Button(settings_frame, text="Show", width=8, command=lambda: self.toggle_show(self.client_id))
        self.show_client_id.grid(row=0, column=2, padx=5, pady=5)
        
        # Client Secret
        ttk.Label(settings_frame, text="Client Secret:").grid(row=1, column=0, padx=5, pady=5)
        self.client_secret = ttk.Entry(settings_frame, width=50, show="*")
        self.client_secret.grid(row=1, column=1, padx=5, pady=5)
        
        # Show/Hide Client Secret
        self.show_client_secret = ttk.Button(settings_frame, text="Show", width=8, command=lambda: self.toggle_show(self.client_secret))
        self.show_client_secret.grid(row=1, column=2, padx=5, pady=5)
        
        # Account ID
        ttk.Label(settings_frame, text="Account ID:").grid(row=2, column=0, padx=5, pady=5)
        self.account_id = ttk.Entry(settings_frame, width=50)
        self.account_id.grid(row=2, column=1, padx=5, pady=5)
        
        # Buttons Frame
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Connect Button
        self.connect_button = ttk.Button(
            button_frame,
            text="Connect",
            command=self.save_and_connect,
            width=20
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        # Disconnect Button
        self.disconnect_button = ttk.Button(
            button_frame,
            text="Disconnect",
            command=self.disconnect,
            width=20,
            state=tk.DISABLED
        )
        self.disconnect_button.pack(side=tk.LEFT, padx=5)
        
        # Status Label
        self.status_label = ttk.Label(settings_frame, text="")
        self.status_label.grid(row=4, column=0, columnspan=3, pady=5)
        
        # Connection Status
        self.connection_status = ttk.Label(settings_frame, text="Not Connected", foreground="red")
        self.connection_status.grid(row=5, column=0, columnspan=3, pady=5)

        # Account Information Frame
        self.account_frame = ttk.LabelFrame(self, text="Account Information")
        self.account_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.account_balance = ttk.Label(self.account_frame, text="Balance: N/A")
        self.account_balance.pack(pady=2)
        
        self.account_frame.pack_forget()  # Hide initially

    def toggle_show(self, entry_widget):
        if entry_widget.cget('show') == '*':
            entry_widget.config(show='')
        else:
            entry_widget.config(show='*')

    def disconnect(self):
        try:
            self.ctrader_client.disconnect()
            self.client_id.delete(0, tk.END)
            self.client_secret.delete(0, tk.END)
            self.account_id.delete(0, tk.END)
            self.status_label.config(text="Disconnected.", foreground="blue")
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
            self.account_frame.pack_forget()
            messagebox.showinfo("Success", "Successfully disconnected from cTrader.")
        except Exception as e:
            messagebox.showerror("Error", f"Error during disconnect: {e}")

    def load_settings_into_ui(self):
        """Populate UI fields from the loaded settings object."""
        self.client_id.delete(0, tk.END)
        self.client_secret.delete(0, tk.END)
        self.account_id.delete(0, tk.END)

        if self.settings.openapi.client_id:
            self.client_id.insert(0, self.settings.openapi.client_id)
        if self.settings.openapi.client_secret:
            self.client_secret.insert(0, self.settings.openapi.client_secret)
        if self.settings.openapi.default_ctid_trader_account_id:
            self.account_id.insert(0, str(self.settings.openapi.default_ctid_trader_account_id))

    def save_and_connect(self):
        if not self.client_id.get() or not self.client_secret.get() or not self.account_id.get():
            messagebox.showerror("Error", "Client ID, Client Secret, and Account ID cannot be empty!")
            return
            
        try:
            # Update the settings object from the UI
            self.settings.openapi.client_id = self.client_id.get()
            self.settings.openapi.client_secret = self.client_secret.get()
            try:
                self.settings.openapi.default_ctid_trader_account_id = int(self.account_id.get())
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Account ID must be a valid integer.")
                return

            # Save the updated settings to config.json
            self.settings.save()

            self.status_label.config(text="Connecting to cTrader... Please check your browser to authenticate.", foreground="blue")
            self.connect_button.config(state=tk.DISABLED)

            def connect_thread_target():
                if not self.ctrader_client.connect():
                    error_msg = self.ctrader_client.get_connection_status()[1]
                    self.after(0, self.handle_connection_error, error_msg)

            thread = threading.Thread(target=connect_thread_target, daemon=True)
            thread.start()

        except Exception as e:
            self.handle_connection_error(f"Failed to start connection thread: {e}")

    def handle_connection_error(self, error_msg):
        self.connection_status.config(text="Not Connected", foreground="red")
        messagebox.showerror("Connection Error", f"Failed to connect: {error_msg}")
        self.status_label.config(text=f"Error: {error_msg}", foreground="red")
        self.connect_button.config(state=tk.NORMAL)

    def display_account_info(self, account):
        # Show the account frame
        self.account_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Update account information
        # This will be updated with cTrader account details
        # self.account_balance.config(text=f"Balance: ${float(account.equity):.2f}")
        # self.account_status.config(text=f"Status: {account.status}")