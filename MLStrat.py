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
from lumibot.entities import Asset
from lumibot.traders import Trader
from datetime import datetime 
from alpaca_trade_api import REST 
from timedelta import Timedelta 
from Models.sentiment_analysis import estimate_sentiment
from alpha_vantage.timeseries import TimeSeries
import numpy as np
import pandas as pd


load_dotenv()

BASE_URL_ALPACA = os.getenv("BASE_URL_ALPACA")

API_KEY="PKOTMBK8PUMPIO9Z6IAK"
API_SECRET="WbmmtdLcvvhSaPj7eVm5XwLrvnzcator5gRPwzkF"

ALPACA_CREDS = {
    "API_KEY":API_KEY,
    "API_SECRET": API_SECRET, 
    "PAPER": True
}


class MyStrategy(Strategy):
    def initialize(self, symbol:str="PAYC", cash_at_risk:float=.5, macd_short_window=12, macd_long_window=26, macd_signal=9, rsi_period=14, rsi_overbought=60, rsi_oversold=40): 
        self.symbol = symbol
        self.sleeptime = "24H" 
        self.last_trade = None 
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=BASE_URL_ALPACA, key_id=API_KEY, secret_key=API_SECRET)
        self.macd_short_window = macd_short_window
        self.macd_long_window = macd_long_window
        self.macd_signal = macd_signal
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def calculate_macd(self, prices):
        short_ema = prices.ewm(span=12, adjust=False).mean()
        long_ema = prices.ewm(span=26, adjust=False).mean()
        macd = short_ema - long_ema
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def calculate_rsi(self, prices):
        delta = prices.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def position_sizing(self): 
        cash = self.get_cash() 
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0) * self.cash_at_risk
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
        print(news)
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment 

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing() 
        probability, sentiment = self.get_sentiment()
        
        # Fetch historical prices
        end_date, start_date = self.get_dates()
        historical_data = self.get_historical_prices(self.symbol, 40, "day")  # Fetch more data for calculation
        historical_data = historical_data.df
        prices = [day for day in historical_data["close"]]
        prices = pd.DataFrame(prices, columns=["close"])
        
        

        # Calculate indicators
        macd, macd_signal = self.calculate_macd(prices)
        rsi = self.calculate_rsi(prices)
        print(macd.iloc[-1,0],macd_signal.iloc[-1,0],rsi.iloc[-1,0],sentiment,probability)
        if cash > last_price: 
            if ((macd.iloc[-1,0] > macd_signal.iloc[-1,0]) or (rsi.iloc[-1,0] < self.rsi_oversold)) or sentiment == "positive" and probability > .9:  
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
            elif ((macd.iloc[-1,0] < macd_signal.iloc[-1,0]) or (rsi.iloc[-1,0] > self.rsi_overbought) ) or sentiment == "negative" and probability > .9:
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


start_date = datetime(2020,1,1)
end_date = datetime(2023,12,31) 
broker = Alpaca(ALPACA_CREDS) 
strategy = MyStrategy(name='mlstrat', broker=broker, 
                    parameters={"symbol":"PAYC", 
                                "cash_at_risk":.5})
strategy.backtest(
    YahooDataBacktesting, 
    start_date, 
    end_date, 
    benchmark_asset="PAYC",
    parameters={"symbol":"PAYC", "cash_at_risk":.5}
)


# historical_data = strategy.get_historical_prices("AMZN", 40, "day")  # Fetch more data for calculation
# historical_data = historical_data.df
# prices = [day for day in historical_data["close"]]
# prices = pd.DataFrame(prices, columns=["close"])