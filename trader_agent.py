from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

app = FastAPI()

class Credentials(BaseModel):
    api_key: str
    api_secret: str

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/verifycredentials/")
async def verify_credentials(request_body: Credentials):
    try:
        api = tradeapi.REST(request_body.api_key, request_body.api_secret, base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        # If the account information is successfully retrieved, return a success message
        return {"message": "Credentials verified, account is active and not restricted from trading.",
                "status": 200}
    except Exception as e:
        return {"message": "Invalid credentials or access forbidden.", 
                "status": 404}
    