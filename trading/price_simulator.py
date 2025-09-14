# trading/price_simulator.py
import random
import numpy as np

class PriceSimulator:
    def __init__(self, base_price=100.0, volatility=0.002):
        self.base_price = base_price
        self.current_price = base_price
        self.volatility = volatility
        self.trend = 0  # -1 for downtrend, 0 for sideways, 1 for uptrend
        self.trend_duration = 0
        self.max_trend_duration = 100
        
    def get_next_price(self):
        # Randomly change trend
        if self.trend_duration >= self.max_trend_duration or random.random() < 0.02:
            self.trend = random.choice([-1, 0, 1])
            self.trend_duration = 0
            
        # Calculate price movement
        trend_component = self.trend * self.volatility * self.base_price
        random_component = np.random.normal(0, self.volatility * self.base_price)
        
        # Update price
        self.current_price += trend_component + random_component
        self.trend_duration += 1
        
        # Ensure price doesn't go negative
        self.current_price = max(self.current_price, 0.01)
        
        return self.current_price
        
    def reset(self, new_base_price=None):
        if new_base_price is not None:
            self.base_price = new_base_price
        self.current_price = self.base_price
        self.trend = 0
        self.trend_duration = 0