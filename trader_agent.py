from fastapi import FastAPI
from pydantic import BaseModel
import alpaca_trade_api as tradeapi

app = FastAPI()

class Credentials(BaseModel):
    api_key: str
    api_secret: str

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/verifycredentials/")
async def verify_credentials(credentials: Credentials):
    api = tradeapi.REST(credentials.api_key, credentials.api_secret, base_url="https://paper-api.alpaca.markets")
    try:
        account = api.get_account()
        if account.trading_blocked:
            raise HTTPException(status_code=403, detail="Account is currently restricted from trading.")
        return {"message": "Credentials verified, account is active and not restricted from trading."}
    except Exception as e:
        raise HTTPException(status_code=403, detail="Failed to verify credentials or account status.")
