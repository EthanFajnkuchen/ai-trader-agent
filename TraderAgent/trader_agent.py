from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import redis
import json
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
import asyncio
import math
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch


device = "cuda:0" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained("mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis")
model = AutoModelForSequenceClassification.from_pretrained("mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis").to(device)
labels = ["negative", "neutral", "positive"]

def estimate_sentiment(news):
    if news:
        tokens = tokenizer(news, return_tensors="pt", padding=True).to(device)

        result = model(tokens["input_ids"], attention_mask=tokens["attention_mask"])[
            "logits"
        ]
        result = torch.nn.functional.softmax(torch.sum(result, 0), dim=-1)
        probability = result[torch.argmax(result)]
        sentiment = labels[torch.argmax(result)]
        return probability, sentiment
    else:
        return 0, labels[-1]

load_dotenv('./../')

r = redis.StrictRedis(host="redis", port=6379, charset="utf-8", decode_responses=True) #Change to redis for docker


BASE_URL_ALPACA = os.getenv("BASE_URL_ALPACA")
CHAT_ID = ""
TRADE_COUNTER = 0
ONGOING_SESSION = {}

ALPACA_CREDS = {
    "API_KEY":None, 
    "API_SECRET": None, 
    "PAPER": True
}

app = FastAPI()

class Credentials(BaseModel):
    chat_id: str
    api_key: str
    api_secret: str

class Ticker(BaseModel):
    ticker: str
    
class Session(BaseModel):
    chat_id: str
    session_alive: bool
    ticker: str
    end_time: str
    amount_to_spend: str


class MLStrategy(Strategy):
    def initialize(self, symbol, amount_to_spend): 
        self.symbol = symbol
        self.sleeptime = "24H"
        self.last_trade = None 
        self.amount_to_spend = float(amount_to_spend)
        self.api = REST(base_url=BASE_URL_ALPACA, key_id=ALPACA_CREDS["API_KEY"], secret_key=ALPACA_CREDS["API_SECRET"])

    def position_sizing(self): 
        last_price = self.get_last_price(self.symbol)
        quantity = math.floor(self.amount_to_spend / last_price)
        return self.amount_to_spend, last_price, quantity

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
        global TRADE_COUNTER
        amount_to_spend, last_price, quantity = self.position_sizing() 
        probability, sentiment = self.get_sentiment()
        print(probability, sentiment)
        cash = self.get_cash()

        if amount_to_spend > last_price and amount_to_spend < cash: 
            print(f"Amount to spend: {amount_to_spend}, last price: {last_price}, quantity: {quantity}, cash: {cash}")

            if sentiment == "positive" and probability > .9: 
                if self.last_trade == "sell": 
                    self.sell_all() 
                    TRADE_COUNTER += 1
                    trade_info = f'SELL all shares of {self.symbol} at {last_price}$ 💰# {CHAT_ID}'
                    r.publish('trade_channel',trade_info)
                order = self.create_order(
                    asset=self.symbol, 
                    quantity=quantity, 
                    side="buy",
                    take_profit_price=round(last_price*1.20, 2), 
                    stop_loss_price=round(last_price*.95, 2),
                )
                self.submit_order(order) 
                TRADE_COUNTER += 1
                trade_info = f'BUY {quantity} shares of {self.symbol} at {last_price}$ 💸# {CHAT_ID}'
                r.publish('trade_channel',trade_info)
                print(f"Order submitted: {order}")
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > .9: 
                if self.last_trade == "buy": 
                    self.sell_all() 
                    TRADE_COUNTER += 1
                    trade_info = f'SELL all shares of {self.symbol} at {last_price}$ 💰# {CHAT_ID}'
                    r.publish('trade_channel',trade_info)
                order = self.create_order(
                    self.symbol, 
                    quantity, 
                    "sell", 
                    type="bracket", 
                    take_profit_price=last_price*.8, 
                    stop_loss_price=last_price*1.05
                )
                self.submit_order(order) 
                TRADE_COUNTER += 1
                trade_info = f'SELL {quantity} shares of {self.symbol} at {last_price}$ 💰# {CHAT_ID}'
                r.publish('trade_channel',trade_info)
                self.last_trade = "sell"
            

trader = Trader()

@app.get("/checkcredentials/{chat_id}")
async def check_credentials(chat_id: str):
    try:
        data_from_redis = r.hgetall(chat_id)
        if data_from_redis == {}:
            return {"message": "No credentials found", "status": 404}
        data = {key: value.strip('"') for key, value in data_from_redis.items()}
        data['status'] = 200
        return data
    except Exception as e:
        print('error')
        return {"message": "Error retrieving credentials", "status": 500}
    

@app.post("/verifyandstorecredentials/")
async def verify_and_store_credentials(request_body: Credentials):
    try:
        api = tradeapi.REST(request_body.api_key, request_body.api_secret, base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        print(account)

        data = {
            'api_key': request_body.api_key,
            'api_secret': request_body.api_secret
        }

        try:
            for key, value in data.items():
                r.hset(request_body.chat_id, key, value)
            for key in ['session_alive','ticker','end_time','amount_to_spend']:
                r.hset(request_body.chat_id, key, json.dumps(None))
        except Exception as e:
            return {"message": "Error storing credentials"}
        
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


@app.post("/store_and_start_new_session/")
async def store_and_start_new_session(request_body: Session):
    global CHAT_ID
    try:
        global trader

        data_from_redis = r.hgetall(request_body.chat_id)
        print(data_from_redis)
        if data_from_redis == {}:
            return {"message": "No credentials found", "status": 404}
        
        print(data_from_redis['api_key'], data_from_redis['api_secret'])

        api = tradeapi.REST(data_from_redis['api_key'], data_from_redis['api_secret'], base_url="https://paper-api.alpaca.markets")
        total_cash = api.get_account().cash
        if float(request_body.amount_to_spend) > float(total_cash):
            return {"status": 403, "message": "Insufficient funds"}
        
        ALPACA_CREDS["API_KEY"] = data_from_redis['api_key']
        ALPACA_CREDS["API_SECRET"] = data_from_redis['api_secret']

        broker = Alpaca(ALPACA_CREDS)
        strategy = MLStrategy(name='mlstrat', broker=broker, 
                    parameters={"symbol":request_body.ticker, 
                                "amount_to_spend": request_body.amount_to_spend})        

        trader.add_strategy(strategy)
        trader.run_all_async()

        data = {
            'session_alive': request_body.session_alive,
            'ticker': request_body.ticker,
            'end_time': request_body.end_time,
            'amount_to_spend': request_body.amount_to_spend
        }
        
        for key, value in data.items():
            if type(value) == str:
                r.hset(request_body.chat_id, key, value)
            else:
                r.hset(request_body.chat_id, key, json.dumps(value))     #Maybe need to change to value only and json.dumps because it add "" to the value
                
        # Convert end_time to a datetime object
        end_time_dt = datetime.strptime(request_body.end_time, "%Y-%m-%d %H:%M:%S")
        end_time_dt = end_time_dt - Timedelta(hours=2)
        now = datetime.now()
        time_remaining = end_time_dt - now
        print(time_remaining)

        task = asyncio.create_task(check_and_stop_session(request_body.chat_id, end_time_dt))
        ONGOING_SESSION[request_body.chat_id] = task

        # # Start the asynchronous loop in the background
        # asyncio.create_task(check_and_stop_session(request_body.chat_id, end_time_dt))
    
        CHAT_ID = request_body.chat_id
        print("status: 200", "message: Session saved and started succesfully")
        return {"status": 200, "message": "Session saved and started succesfully"}    

    except Exception as e:
        print("status :500, message :Internal server error")
        return{"status": 500, "message": "Internal server error"}
        print(e)        

@app.post("/stop_session/")
async def stop_session(request_body: Session):
    response = stop_session_for_chat_id(request_body.chat_id)
    return response


async def check_and_stop_session(chat_id: str, end_time: datetime):
    try:
        while True:
            await asyncio.sleep(60)
            now = datetime.now()
            time_remaining = end_time - now
            print(f"Time remaining till end_time: {time_remaining}")
            if now >= end_time:
                response = stop_session_for_chat_id(chat_id)
                trade_counter = response.get('counter')
                cash_value = response.get('cash_value')
                portfolio_value = response.get('portfolio_value')
                trade_info = f"📊📊 RECAP 📊📊\nTotal trades made: {trade_counter}\nCash Value: {cash_value}$\nPortfolio Value: {portfolio_value}$# {CHAT_ID}"
                r.publish('trade_channel',trade_info)
                break
    except asyncio.CancelledError:
        print(f"Session check task for chat ID {chat_id} was cancelled.")        

def stop_session_for_chat_id(chat_id: str):

    try:
        global trader
        global ONGOING_SESSION
        global TRADE_COUNTER

        data_from_redis = r.hgetall(chat_id)
        if data_from_redis == {}:
            return {"message": "No credentials found", "status": 404}

        data = {
            'session_alive': False,
            'ticker': None,
            'end_time': None,
            'amount_to_spend': None
        }

        for key, value in data.items():
            r.hset(chat_id, key, json.dumps(value))

        task = ONGOING_SESSION.get(chat_id)
        if task:
            task.cancel()
            print(f"Task for chat ID {chat_id} cancelled.")
            del ONGOING_SESSION[chat_id]  # Clean up the reference

        trader.stop_all()
        trader = Trader()

        api = tradeapi.REST(ALPACA_CREDS["API_KEY"], ALPACA_CREDS["API_SECRET"], base_url="https://paper-api.alpaca.markets")
        account = api.get_account()
        portfolio_value = account.portfolio_value
        cash_value = account.cash
        counter = TRADE_COUNTER

        TRADE_COUNTER = 0
        
        return {"status": 200, "message": "Session stopped succesfully", "counter": counter ,"cash_value": cash_value, "portfolio_value": portfolio_value}

    except Exception as e:
        return {"status": 500, "message": "Internal server error"}
