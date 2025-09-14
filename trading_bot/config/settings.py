# config/settings.py
class Config:
    API_KEY = ""
    API_SECRET = ""
    PAPER_TRADING = True
    RISK_LEVEL = "medium"
    
    @classmethod
    def update_credentials(cls, api_key, api_secret, paper_trading):
        cls.API_KEY = api_key
        cls.API_SECRET = api_secret
        cls.PAPER_TRADING = paper_trading
