# trading/trade_executor.py
from trading.alpaca_client import AlpacaClient

class TradeExecutor:
    def __init__(self):
        self.client = AlpacaClient()
        
    def place_trade(self, symbol, qty, side, take_profit=None, stop_loss=None):
        try:
            self.client.trading_client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type='market',
                time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': take_profit} if take_profit else None,
                stop_loss={'stop_price': stop_loss} if stop_loss else None
            )
            return True
        except Exception as e:
            print(f"Error placing trade: {e}")
            return False
