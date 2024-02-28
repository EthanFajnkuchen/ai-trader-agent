import telebot
import time
import os
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

# Set your tokens here
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
BASE_URL_API = os.getenv("BASE_URL_API")
list_traders = []   

class BotParameters:
    def __init__(self, chat_id, api_key, api_secret):
        self.chat_id = chat_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_alive = False
        self.end_time = None
        self.ticker = None
        self.amount_to_spend = None

    def send_message(self, message):
        bot.send_message(self.chat_id, message)


def ask_for_api_key(message):
    message_to_send = ("Hello there 👋\nI am your friendly AI Trader Agent.\nTo use me, you need to open an Alpaca account and provide me your credentials.\nPlease enter your API-Key:")
    msg = bot.reply_to(message, message_to_send)
    bot.register_next_step_handler(msg, process_api_key_step)

def process_api_key_step(message):
    chat_id = message.chat.id
    api_key = message.text
    msg = bot.send_message(chat_id, "Very good!\nNow, please enter your API-Secret:")
    bot.register_next_step_handler(msg, process_api_secret_step, api_key)

def verify_credentials(api_key, api_secret, chat_id):
    # Define the URL for your FastAPI endpoint

    # Make the POST request and capture the response
    response = requests.post(f"{BASE_URL_API}/verifyandstorecredentials/", json={"chat_id": str(chat_id), 'api_key': api_key, 'api_secret': api_secret})

    # Check if the request was successful
    if response.status_code == 200:
        response_body = response.json()
        # Check the 'status' field in the response
        return response_body.get('status') == 200

    # Handle failure cases
    return False


def process_api_secret_step(message, api_key):
    chat_id = message.chat.id
    api_secret = message.text
    bot.send_message(chat_id, "Thank you! Your API credentials have been received.")

    if verify_credentials(api_key, api_secret, chat_id):
        trader = BotParameters(chat_id, api_key, api_secret)
        list_traders.append(trader)
        bot.send_message(chat_id, "Credentials verified! To start your trading agent, please type /start 🚀")
    else:
        bot.send_message(chat_id, "Wrong credentials ❌\nPlease initiate the setup again with /init.")

def check_user_credentials(chat_id):
    # Construct the URL for the FastAPI endpoint
    url = f"{BASE_URL_API}/checkcredentials/{chat_id}"
    
    # Make the GET request and capture the response
    response = requests.get(url)
    response_body = response.json()
    print(response_body)
    
    # Check if the request was successful and the credentials exist
    if response_body['status'] == 200:
        print('go')

        return True  
    return False  # No credentials found or an error occurred

@bot.message_handler(commands=['init'])
def init(message):
    chat_id = message.chat.id
    if check_user_credentials(chat_id):
        bot.send_message(chat_id, "Your credentials are already stored 🗃️. To start your trading agent, please type /start 🚀")
    else:
        ask_for_api_key(message)

def ask_for_ticker(message,trader):
    msg = bot.reply_to(message, "Please enter a ticker symbol (e.g., AAPL, GOOG):")
    bot.register_next_step_handler(msg, process_ticker_step, trader)

def process_ticker_step(message, trader):
    chat_id = message.chat.id
    ticker = message.text.upper()  # Convert ticker to uppercase for consistency

    # Simple validation for ticker format (you can enhance this as needed)
    if not ticker.isalpha() or len(ticker) > 5:
        msg = bot.reply_to(message, "Invalid ticker symbol. Please enter a valid ticker (e.g., AAPL, GOOG):")
        bot.register_next_step_handler(msg, process_ticker_step,trader)
        return
    
    response = requests.post(f"{BASE_URL_API}/check_ticker/", json={"ticker": ticker})
    if response.status_code == 200:
        response_body = response.json()
        # Check if the status field in the response body indicates a failure
        if response_body.get('status') != 200:
            msg = bot.reply_to(message, "Ticker not found or is invalid. Please enter a valid ticker:")
            bot.register_next_step_handler(msg, process_ticker_step, trader)
            return
    else:
        # Handle unexpected status codes
        msg = bot.reply_to(message, "There was an error processing your request. Please try again.")
        bot.register_next_step_handler(msg, process_ticker_step, trader)
        return
    

    trader.ticker = ticker

    # If the ticker is valid, proceed to ask for the start time
    
    msg = bot.send_message(chat_id, "Please enter the end time of your session (HH:MM):")
    bot.register_next_step_handler(msg, validate_end_time, trader)



def validate_end_time(message, trader):
    chat_id = message.chat.id
    end_time_str = message.text
    try:
        # Combine current date with provided hour and minute for end time
        end_time = datetime.now().replace(hour=int(end_time_str.split(":")[0]), minute=int(end_time_str.split(":")[1]), second=0, microsecond=0)

        # Check if the end time is in the past or before the start time
        if end_time <= datetime.now():
            raise ValueError("End time must be in the future.")

        # End time is valid and in the future, ask for max amount
        trader.end_time = end_time
        msg = bot.send_message(chat_id, "Please enter the maximum amount of money to be spent:")
        bot.register_next_step_handler(msg, process_max_amount_step, trader)
    except ValueError as e:
        msg = bot.reply_to(message, str(e) + "\nPlease enter a valid end time in the future (HH:MM):")
        bot.register_next_step_handler(msg, validate_end_time, trader)

def process_max_amount_step(message, trader):
    chat_id = message.chat.id
    max_amount = message.text  # Add validation for max_amount if needed
    # Formatting start and end times for the summary message
    trader.amount_to_spend = max_amount
    trader.session_alive = True

    bot.send_message(chat_id, f"All set! Your trading agent is alive.")
    bot.send_message(chat_id, f"{trader.chat_id}\n{trader.session_alive}\n{trader.ticker}\n{trader.end_time}\n{trader.amount_to_spend}")

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    trader = next((t for t in list_traders if t.chat_id == chat_id), None)

    if trader:
        ask_for_ticker(message, trader)
    else:
        bot.reply_to(message, "Please initialize your credentials first with /init.")

@bot.message_handler(func=lambda message: True)
def redirect_to_init_or_start(message):
    chat_id = message.chat.id
    # Check if the user has already initialized their credentials
    trader = next((t for t in list_traders if t.chat_id == chat_id), None)
    if trader:
        # If credentials are initialized, prompt to use /start
        bot.send_message(chat_id, "You can start trading by using the /start command. 🚀")
    else:
        # If credentials are not initialized, prompt to use /init
        bot.send_message(chat_id, "Please initialize your credentials first with the /init command. 🔑")


def start_bot():
    bot.polling()

def run_other_task():
    while(True):
        if len(list_traders) > 0:
            for trader in list_traders:
                trader.send_message('Hello, I am a bot')
                time.sleep(10)



def main():
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    # agent_thread = threading.Thread(target=run_other_task)
    # agent_thread.start()

if __name__ == "__main__":
    start_bot()