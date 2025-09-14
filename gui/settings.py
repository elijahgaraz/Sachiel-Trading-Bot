# gui/settings.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config
from trading.ctrader_client import CTraderClient

class SettingsTab(ttk.Frame):
    def __init__(self, parent, ctrader_client):
        super().__init__(parent)
        self.ctrader_client = ctrader_client
        self.setup_ui()
        self.load_existing_settings()
        
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
        
        self.account_status = ttk.Label(self.account_frame, text="Status: N/A")
        self.account_status.pack(pady=2)
        
        self.account_frame.pack_forget()  # Hide initially

    def toggle_show(self, entry_widget):
        if entry_widget.cget('show') == '*':
            entry_widget.config(show='')
        else:
            entry_widget.config(show='*')

    def disconnect(self):
        try:
            # Clear API credentials from Config
            Config.CTRADING_CLIENT_ID = ""
            Config.CTRADING_CLIENT_SECRET = ""
            Config.CTRADING_ACCOUNT_ID = ""
            
            # Clear the entry fields
            self.client_id.delete(0, tk.END)
            self.client_secret.delete(0, tk.END)
            self.account_id.delete(0, tk.END)
            
            # Update connection status
            self.connection_status.config(text="Not Connected", foreground="red")
            self.status_label.config(text="Disconnected from cTrader", foreground="blue")
            
            # Update button states
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
            
            # Delete saved credentials
            self.delete_saved_credentials()
            
            # Hide account information
            self.account_frame.pack_forget()
            
            messagebox.showinfo("Success", "Successfully disconnected from cTrader")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error during disconnect: {str(e)}")

    def delete_saved_credentials(self):
        try:
            config_dir = os.path.expanduser('~/.sachiel_trading')
            config_file = os.path.join(config_dir, 'config.json')
            
            if os.path.exists(config_file):
                os.remove(config_file)
                
        except Exception as e:
            print(f"Error deleting credentials: {e}")

    def load_existing_settings(self):
        """Load previously saved settings if they exist"""
        try:
            config_dir = os.path.expanduser('~/.sachiel_trading')
            settings_file = os.path.join(config_dir, 'config.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    config_data = json.load(f)
                    
                self.client_id.insert(0, config_data.get('client_id', ''))
                self.client_secret.insert(0, config_data.get('client_secret', ''))
                self.account_id.insert(0, config_data.get('account_id', ''))
                
                # Update Config class
                Config.update_credentials(
                    config_data.get('client_id', ''),
                    config_data.get('client_secret', ''),
                    config_data.get('account_id', '')
                )
                    
        except Exception as e:
            print(f"Error loading settings: {e}")
            self.status_label.config(text=f"Error loading settings: {str(e)}", foreground="red")

    def save_to_file(self):
        """Save API credentials to file"""
        try:
            config_dir = os.path.expanduser('~/.sachiel_trading')
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            config_file = os.path.join(config_dir, 'config.json')
            config_data = {
                'client_id': self.client_id.get(),
                'client_secret': self.client_secret.get(),
                'account_id': self.account_id.get()
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.status_label.config(text=f"Error saving settings: {str(e)}", foreground="red")
            raise e

    def save_and_connect(self):
        if not self.client_id.get() or not self.client_secret.get() or not self.account_id.get():
            messagebox.showerror("Error", "Client ID, Client Secret, and Account ID cannot be empty!")
            return
            
        try:
            # Update config
            Config.update_credentials(
                self.client_id.get(),
                self.client_secret.get(),
                self.account_id.get()
            )
            
            # Save credentials to file
            self.save_to_file()

            self.status_label.config(text="Connecting to cTrader...", foreground="blue")

            # Use the shared client instance to connect
            if self.ctrader_client.connect():
                self.connection_status.config(text="Connecting...", foreground="orange")
                self.disconnect_button.config(state=tk.NORMAL)
                self.status_label.config(text="Connection process started. Please check your browser to authenticate.", foreground="blue")
                # The connection status will be updated by the check_connection loop in the main app
            else:
                error_msg = self.ctrader_client.get_connection_status()[1]
                self.connection_status.config(text="Not Connected", foreground="red")
                messagebox.showerror("Connection Error", f"Failed to initiate connection: {error_msg}")
                self.status_label.config(text=f"Error: {error_msg}", foreground="red")

        except Exception as e:
            self.connection_status.config(text="Not Connected", foreground="red")
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")

    def display_account_info(self, account):
        # Show the account frame
        self.account_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Update account information
        # This will be updated with cTrader account details
        # self.account_balance.config(text=f"Balance: ${float(account.equity):.2f}")
        # self.account_status.config(text=f"Status: {account.status}")