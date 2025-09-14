# trading/market_clock.py
from datetime import datetime
import pytz
from alpaca.trading.client import TradingClient
from config.settings import Config

class MarketClock:
    def __init__(self):
        self.trading_client = None
        self.clock = None
        self.last_update = None
        self.update_interval = 60  # Update every 60 seconds

    def connect(self):
        self.trading_client = TradingClient(
            Config.API_KEY,
            Config.API_SECRET,
            paper=Config.PAPER_TRADING
        )
        
    def get_clock(self, force_update=False):
        current_time = datetime.now(pytz.UTC)
        
        # Update clock if it's None or if last update was more than update_interval ago
        if (self.clock is None or force_update or 
            self.last_update is None or 
            (current_time - self.last_update).seconds > self.update_interval):
            
            self.clock = self.trading_client.get_clock()
            self.last_update = current_time
            
        return self.clock
        
    def is_market_open(self):
        try:
            clock = self.get_clock()
            return clock.is_open
        except Exception as e:
            print(f"Error checking market status: {e}")
            return False
            
    def get_next_market_open(self):
        try:
            clock = self.get_clock()
            return clock.next_open.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Exception as e:
            print(f"Error getting next market open: {e}")
            return None
            
    def get_next_market_close(self):
        try:
            clock = self.get_clock()
            return clock.next_close.strftime('%Y-%m-%d %H:%M:%S %Z')
        except Exception as e:
            print(f"Error getting next market close: {e}")
            return None
            
    def get_market_status_message(self):
        try:
            clock = self.get_clock()
            if clock.is_open:
                return f"Market is OPEN | Closes at: {self.get_next_market_close()}"
            else:
                return f"Market is CLOSED | Opens at: {self.get_next_market_open()}"
        except Exception as e:
            return f"Error getting market status: {e}"