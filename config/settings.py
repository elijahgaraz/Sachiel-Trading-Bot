# config/settings.py
class Config:
    CTRADING_CLIENT_ID = ""
    CTRADING_CLIENT_SECRET = ""
    CTRADING_ACCOUNT_ID = ""
    RISK_LEVEL = "medium"
    
    # cTrader API settings
    CTRADER_HOST_TYPE = "live"  # "live" or "demo"
    CTRADER_SPOTWARE_AUTH_URL = "https://connect.spotware.com/oauth/v2/auth"
    CTRADER_SPOTWARE_TOKEN_URL = "https://connect.spotware.com/oauth/v2/token"
    CTRADER_REDIRECT_URI = "http://localhost:5000/callback"

    @classmethod
    def update_credentials(cls, client_id, client_secret, account_id):
        cls.CTRADING_CLIENT_ID = client_id
        cls.CTRADING_CLIENT_SECRET = client_secret
        cls.CTRADING_ACCOUNT_ID = account_id
