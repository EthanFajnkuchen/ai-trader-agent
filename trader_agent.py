from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import alpaca_trade_api as tradeapi
import yfinance as yf
from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from datetime import datetime 
from alpaca_trade_api import REST 
from timedelta import Timedelta 
# from finbert_utils import estimate_sentiment

app = FastAPI()

load_dotenv()
BASE_URL = os.getenv("BASE_URL")

ALPACA_CREDS = {
    "API_KEY":None, 
    "API_SECRET": None, 
    "PAPER": True
}

class Credentials(BaseModel):
    api_key: str
    api_secret: str

class Ticker(BaseModel):
    ticker: str


class MLStrategy(Strategy):
    def initialize(self, symbol:str="SPY", cash_at_risk:float=.5): 
        self.symbol = symbol
        self.sleeptime = "24H" 
        self.last_trade = None 
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)

    def position_sizing(self): 
        cash = self.get_cash() 
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0)
        return cash, last_price, quantity

    def get_dates(self): 
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')

    def get_sentiment(self): 
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, 
                                 start=three_days_prior, 
                                 end=today) 
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment 

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing() 
        probability, sentiment = self.get_sentiment()

        if cash > last_price: 
            if sentiment == "positive" and probability > .999: 
                if self.last_trade == "sell": 
                    self.sell_all() 
                order = self.create_order(
                    self.symbol, 
                    quantity, 
                    "buy", 
                    type="bracket", 
                    take_profit_price=last_price*1.20, 
                    stop_loss_price=last_price*.95
                )
                self.submit_order(order) 
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > .999: 
                if self.last_trade == "buy": 
                    self.sell_all() 
                order = self.create_order(
                    self.symbol, 
                    quantity, 
                    "sell", 
                    type="bracket", 
                    take_profit_price=last_price*.8, 
                    stop_loss_price=last_price*1.05
                )
                self.submit_order(order) 
                self.last_trade = "sell"


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/verifycredentials/")
async def verify_credentials(request_body: Credentials):
    try:
        api = tradeapi.REST(request_body.api_key, request_body.api_secret, base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        ALPACA_CREDS["API_KEY"] = request_body.api_key
        ALPACA_CREDS["API_SECRET"] = request_body.api_secret
        # If the account information is successfully retrieved, return a success message
        return {"message": "Credentials verified, account is active and not restricted from trading.",
                "status": 200}
    except Exception as e:
        return {"message": "Invalid credentials or access forbidden.", 
                "status": 404}
    

@app.post("/check_ticker/")
async def check_ticker(request_body: Ticker):
    try:
        existingTicker = yf.Ticker(request_body.ticker)
        hist = existingTicker.history(period="1d")
        if hist.empty: 
            return {"status": 404, "message": "Ticker not found"}
        return {"status": 200, "message": "Ticker exists"}
    except Exception as e:
        return {"status": 500, "message": "Internal server error"}
