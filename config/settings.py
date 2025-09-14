# config/settings.py
class Config:
    CTRADING_CLIENT_ID = ""
    CTRADING_CLIENT_SECRET = ""
    CTRADING_ACCOUNT_ID = ""
    RISK_LEVEL = "medium"
    
    @classmethod
    def update_credentials(cls, client_id, client_secret, account_id):
        cls.CTRADING_CLIENT_ID = client_id
        cls.CTRADING_CLIENT_SECRET = client_secret
        cls.CTRADING_ACCOUNT_ID = account_id
