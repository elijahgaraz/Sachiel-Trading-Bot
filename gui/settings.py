# gui/settings.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config
from trading.alpaca_client import AlpacaClient

class SettingsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()
        self.load_existing_settings()
        
    def setup_ui(self):
        settings_frame = ttk.LabelFrame(self, text="API Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # API Key
        ttk.Label(settings_frame, text="API Key:").grid(row=0, column=0, padx=5, pady=5)
        self.api_key = ttk.Entry(settings_frame, width=50, show="*")
        self.api_key.grid(row=0, column=1, padx=5, pady=5)
        
        # Show/Hide API Key
        self.show_api_key = ttk.Button(settings_frame, text="Show", width=8, command=lambda: self.toggle_show(self.api_key))
        self.show_api_key.grid(row=0, column=2, padx=5, pady=5)
        
        # Secret Key
        ttk.Label(settings_frame, text="Secret Key:").grid(row=1, column=0, padx=5, pady=5)
        self.secret_key = ttk.Entry(settings_frame, width=50, show="*")
        self.secret_key.grid(row=1, column=1, padx=5, pady=5)
        
        # Show/Hide Secret Key
        self.show_secret_key = ttk.Button(settings_frame, text="Show", width=8, command=lambda: self.toggle_show(self.secret_key))
        self.show_secret_key.grid(row=1, column=2, padx=5, pady=5)
        
        # Trading Mode
        ttk.Label(settings_frame, text="Trading Mode:").grid(row=2, column=0, padx=5, pady=5)
        self.trading_mode = ttk.Combobox(
            settings_frame,
            values=["Paper", "Live"],
            state="readonly",
            width=47
        )
        self.trading_mode.set("Paper")
        self.trading_mode.grid(row=2, column=1, padx=5, pady=5)
        
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
            Config.API_KEY = ""
            Config.API_SECRET = ""
            
            # Clear the entry fields
            self.api_key.delete(0, tk.END)
            self.secret_key.delete(0, tk.END)
            
            # Update connection status
            self.connection_status.config(text="Not Connected", foreground="red")
            self.status_label.config(text="Disconnected from Alpaca", foreground="blue")
            
            # Update button states
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
            
            # Delete saved credentials
            self.delete_saved_credentials()
            
            # Hide account information
            self.account_frame.pack_forget()
            
            messagebox.showinfo("Success", "Successfully disconnected from Alpaca")
            
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
                    
                self.api_key.insert(0, config_data.get('api_key', ''))
                self.secret_key.insert(0, config_data.get('secret_key', ''))
                self.trading_mode.set("Paper" if config_data.get('paper_trading', True) else "Live")
                
                # Update Config class
                Config.update_credentials(
                    config_data.get('api_key', ''),
                    config_data.get('secret_key', ''),
                    config_data.get('paper_trading', True)
                )

                # If we have credentials, try to connect automatically
                if config_data.get('api_key') and config_data.get('secret_key'):
                    self.save_and_connect()
                    
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
                'api_key': self.api_key.get(),
                'secret_key': self.secret_key.get(),
                'paper_trading': self.trading_mode.get() == "Paper"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.status_label.config(text=f"Error saving settings: {str(e)}", foreground="red")
            raise e

    def save_and_connect(self):
        if not self.api_key.get() or not self.secret_key.get():
            messagebox.showerror("Error", "API Key and Secret Key cannot be empty!")
            return
            
        try:
            # Update config
            Config.update_credentials(
                self.api_key.get(),
                self.secret_key.get(),
                self.trading_mode.get() == "Paper"
            )
            
            # Test connection
            client = AlpacaClient()
            client.connect()
            account = client.get_account()
            
            if account:
                # Save to file if connection successful
                self.save_to_file()
                self.connection_status.config(text="Connected", foreground="green")
                self.disconnect_button.config(state=tk.NORMAL)  # Enable disconnect button
                messagebox.showinfo("Success", "Successfully connected to Alpaca!")
                self.status_label.config(text="Connected to Alpaca", foreground="green")
                self.display_account_info(account)  # Display account information
            else:
                raise Exception("Could not verify account connection")
                
        except Exception as e:
            self.connection_status.config(text="Not Connected", foreground="red")
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")

    def display_account_info(self, account):
        # Show the account frame
        self.account_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Update account information
        self.account_balance.config(text=f"Balance: ${float(account.equity):.2f}")
        self.account_status.config(text=f"Status: {account.status}")