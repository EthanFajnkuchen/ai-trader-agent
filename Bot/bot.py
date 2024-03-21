import telebot
import time
import os
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv("./../.env")

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))
BASE_URL_API = os.getenv("BASE_URL_API")
LIST_TRADERS = []   

class BotParameters:
    """
    Represents the parameters and state for each bot user.

    Attributes:
        chat_id (int): Telegram chat ID of the user.
        api_key (str): User's API key.
        api_secret (str): User's API secret.
        session_alive (bool): Indicates whether a trading session is active.
        end_time (datetime): Scheduled end time for the trading session.
        ticker (str): Ticker symbol for the trading session.
        amount_to_spend (float): Maximum amount of money to be spent.
    """
    def __init__(self, chat_id, api_key, api_secret,session_alive=False, end_time=None, ticker=None, amount_to_spend=None):
        self.chat_id = chat_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_alive = session_alive
        self.end_time = end_time
        self.ticker = ticker
        self.amount_to_spend = amount_to_spend

    def send_message(self, message):
        bot.send_message(self.chat_id, message)



######################################################################################################################
#                                                                                                                    #
#                                                                                                                    #
#                                         HELPER FUNCTIONS FOR BOT COMMANDS                                          #
#                                                                                                                    #
#                                                                                                                    #
######################################################################################################################



def ask_for_api_key(message):
    """
    Prompts the user to enter their API key by sending a message.

    Parameters:
        message (telebot.types.Message): The Telegram message object that triggered the bot command.
    """
    message_to_send = ("Hello there 👋\nI am your friendly AI Trader Agent.\nTo use me, you need to open an Alpaca account and provide me your credentials.\nPlease enter your API-Key:")
    msg = bot.reply_to(message, message_to_send)
    bot.register_next_step_handler(msg, process_api_key_step)

def process_api_key_step(message):
    """
    Processes the API key entered by the user and prompts the user to enter their API secret.

    Parameters:
        message (telebot.types.Message): The Telegram message object containing the user's API key.
    """
    chat_id = message.chat.id
    api_key = message.text
    msg = bot.send_message(chat_id, "Very good!\nNow, please enter your API-Secret:")
    bot.register_next_step_handler(msg, process_api_secret_step, api_key)



def process_api_secret_step(message, api_key):
    """
    Processes the API secret provided by the user and attempts to verify the API credentials.

    This function is called after a user has entered their API secret in response to a prompt. It extracts the chat ID and the API secret from the incoming message, and then attempts to verify the API credentials using the `verify_credentials` function. If the credentials are verified successfully, a new `BotParameters` instance is created for the user and added to the list of traders, and the user is notified that they can start their trading agent by typing `/start`. If the credentials are not verified, the user is informed that the credentials are incorrect and is prompted to initiate the setup process again with `/init`.

    Parameters:
        message (telebot.types.Message): The Telegram message object containing the user's API secret.
        api_key (str): The API key previously entered by the user.

    Returns:
        None
    """
    chat_id = message.chat.id
    api_secret = message.text
    bot.send_message(chat_id, "Thank you! Your API credentials have been received.")

    if verify_credentials(api_key, api_secret, chat_id):
        trader = BotParameters(chat_id, api_key, api_secret)
        LIST_TRADERS.append(trader)
        bot.send_message(chat_id, "Credentials verified! To start your trading agent, please type /start 🚀")
    else:
        bot.send_message(chat_id, "Wrong credentials ❌\nPlease initiate the setup again with /init.")
        
def verify_credentials(api_key, api_secret, chat_id):
    """
    Verifies the provided API credentials by making a POST request to a specified endpoint.

    This function sends the API key, API secret, and chat ID as a JSON payload to an endpoint that verifies these credentials. If the server responds with a status code of 200 and the response body also contains a status of 200, the credentials are considered verified.

    Parameters:
        api_key (str): The API key to be verified.
        api_secret (str): The API secret to be verified.
        chat_id (int): The Telegram chat ID associated with these credentials, used for identifying the user.

    Returns:
        bool: True if the credentials are successfully verified, False otherwise.
    """
    response = requests.post(f"{BASE_URL_API}/verifyandstorecredentials/", json={"chat_id": str(chat_id), 'api_key': api_key, 'api_secret': api_secret})
    if response.status_code == 200:
        response_body = response.json()
        return response_body.get('status') == 200
    return False

def check_user_credentials(chat_id):
    """
    Checks the stored credentials for a given user by making a GET request to a specific endpoint.

    This function constructs a URL using the provided chat ID and makes a GET request to check if the credentials associated with that chat ID are stored and valid. The response from the server is expected to contain a status code within the response body. If the status code is 200, it indicates that the credentials are found and presumably valid, and the function returns True along with the response body. If the status code is not 200, the function returns False along with the response body, indicating that the credentials are either not found or not valid.

    Parameters:
        chat_id (int): The Telegram chat ID of the user whose credentials are being checked.

    Returns:
        tuple: A tuple containing a boolean value and the response body. The boolean value is True if the credentials are found and valid, and False otherwise. The response body is a dictionary containing the server's response.
    """
    url = f"{BASE_URL_API}/checkcredentials/{chat_id}"
    
    response = requests.get(url)
    response_body = response.json()
    
    if response_body['status'] == 200:
        return True, response_body
    return False, response_body  


def ask_for_ticker(message,trader):
    """
    Prompts the user to enter a stock ticker symbol for initiating a trading session.

    This function is called when the user needs to provide a ticker symbol for the stock they wish to trade. It sends a message asking the user to enter a ticker symbol (e.g., AAPL, GOOG) and registers the `process_ticker_step` function as the next step to handle the user's response.

    Parameters:
        message (telebot.types.Message): The Telegram message object related to the current chat session.
        trader (BotParameters): The trader object associated with the current user, containing user and session details.

    Returns:
        None
    """
    msg = bot.reply_to(message, "Please enter a ticker symbol (e.g., AAPL, GOOG):")
    bot.register_next_step_handler(msg, process_ticker_step, trader)

def process_ticker_step(message, trader):
    """
    Processes the ticker symbol provided by the user, validating its format and existence.

    This function is triggered after a user responds with a ticker symbol. It validates the ticker by ensuring it is alphabetical and does not exceed five characters. If the ticker is invalid, the user is prompted to enter a valid ticker symbol again. If the ticker is valid, a request is made to an external API to further validate the ticker. If the ticker exists and is valid, the user is asked to enter the end time for the trading session. Otherwise, the user is informed of the error and asked to try again.

    Parameters:
        message (telebot.types.Message): The Telegram message object containing the user's ticker input.
        trader (BotParameters): The trader object associated with the current user, to be updated with the ticker information if valid.

    Returns:
        None
    """
    chat_id = message.chat.id
    ticker = message.text.upper()

    if not ticker.isalpha() or len(ticker) > 5:
        msg = bot.reply_to(message, "Invalid ticker symbol. Please enter a valid ticker (e.g., AAPL, GOOG):")
        bot.register_next_step_handler(msg, process_ticker_step,trader)
        return
    
    response = requests.post(f"{BASE_URL_API}/check_ticker/", json={"ticker": ticker})
    if response.status_code == 200:
        response_body = response.json()
        if response_body.get('status') != 200:
            msg = bot.reply_to(message, "Ticker not found or is invalid. Please enter a valid ticker:")
            bot.register_next_step_handler(msg, process_ticker_step, trader)
            return
    else:
        msg = bot.reply_to(message, "There was an error processing your request. Please try again.")
        bot.register_next_step_handler(msg, process_ticker_step, trader)
        return
    trader.ticker = ticker
    msg = bot.send_message(chat_id, "Please enter the end date of your session (YYY-MM-DD hh:mm):")
    bot.register_next_step_handler(msg, validate_end_time, trader)



def validate_end_time(message, trader):
    """
    Validates the end time for a trading session provided by the user.

    This function checks if the provided end time is in the correct format (HH:MM) and is in the future. 
    If the end time is valid, it is set for the trader's session, and the user is prompted to enter the maximum amount of money to be spent. 
    If the end time is not valid, the user is notified and asked to enter a valid end time.

    Parameters:
        message (telebot.types.Message): The Telegram message object containing the user's end time input.
        trader (BotParameters): The trader object associated with the current user, to be updated with the end time if valid.

    Returns:
        None
    """
    chat_id = message.chat.id
    end_time_str = message.text
    try:
        # Assuming end_time_str is the string provided by the user, e.g., "2024-03-21 15:30"
        end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
        if end_time <= datetime.now():
            raise ValueError("End time must be in the future.")
        trader.end_time = end_time
        msg = bot.send_message(chat_id, "Please enter the maximum amount of money to be spent:")
        bot.register_next_step_handler(msg, process_max_amount_step, trader)
    except ValueError as e:
        msg = bot.reply_to(message, str(e) + "\nPlease enter a valid end time in the future (HH:MM):")
        bot.register_next_step_handler(msg, validate_end_time, trader)

def process_max_amount_step(message, trader):
    """
    Validates the end time for a trading session provided by the user.

    This function checks if the provided end time is in the correct format (HH:MM) and is in the future. If the end time is valid, it is set for the trader's session, and the user is prompted to enter the maximum amount of money to be spent. If the end time is not valid, the user is notified and asked to enter a valid end time.

    Parameters:
        message (telebot.types.Message): The Telegram message object containing the user's end time input.
        trader (BotParameters): The trader object associated with the current user, to be updated with the end time if valid.

    Returns:
        None
    """
    chat_id = message.chat.id
    max_amount = message.text 
    trader.amount_to_spend = max_amount
    trader.session_alive = True
    response = requests.post(f"{BASE_URL_API}/store_and_start_new_session/", json={"chat_id": str(trader.chat_id), 'session_alive': trader.session_alive, 'ticker': trader.ticker, 'end_time': str(trader.end_time), 'amount_to_spend': trader.amount_to_spend})
    response_body = response.json()
    print(response_body )
    if response_body["status"] == 500:
        bot.send_message(chat_id, f"An error occurred while starting your session. Please try again later.")
    elif response_body["status"] == 403:
        bot.send_message(chat_id, f"Insufficient funds")
    else:
        bot.send_message(chat_id, f"All set! Your trading agent is alive.")



def retreive_trader(chat_id):
    """
    Retrieves the trader object associated with a given chat ID from the list of traders.

    This function first checks the user's credentials to see if they exist.
    If a trader object with the given chat ID exists in the list of traders and the user's credentials are valid, the function updates the trader object with the latest session details from the response body.
    If a trader object does not exist but the user's credentials are valid, a new trader object is created and added to the list of traders. The trader object is then retrieved from the list of traders and returned.

    Parameters:
        chat_id (int): The Telegram chat ID of the user whose trader object is being retrieved.

    Returns:
        BotParameters: The trader object associated with the given chat ID.
    """
    already_exists, response_body = check_user_credentials(chat_id)
    trader = next((t for t in LIST_TRADERS if t.chat_id == chat_id), None)
    if trader and already_exists:
        trader.session_alive = True if response_body["session_alive"] == "true" else False
        trader.end_time = response_body["end_time"]
        trader.ticker = response_body["ticker"]
        trader.amount_to_spend = response_body["amount_to_spend"]
    if not trader and already_exists:
        trader = BotParameters(chat_id, response_body['api_key'], response_body['api_secret'], True if response_body["session_alive"] == "true" else False, response_body['end_time'], response_body['ticker'], response_body['amount_to_spend'])
        LIST_TRADERS.append(trader)
    
    trader = next((t for t in LIST_TRADERS if t.chat_id == chat_id), None)
    return trader
  
  
  
######################################################################################################################
#                                                                                                                    #
#                                                                                                                    #
#                                             BOT COMMANDS HANDLERS                                                  #
#                                                                                                                    #
#                                                                                                                    #
######################################################################################################################

      
@bot.message_handler(commands=['init'])
def init(message):
    """
    Handles the `/init` command from a user, initiating the process of setting up API credentials.

    This function is triggered when a user sends the `/init` command to the Telegram bot. It checks if the user's credentials are already stored by calling the `check_user_credentials` function with the user's chat ID. If the credentials exist, the user is informed that their credentials are stored and they can start their trading agent using the `/start` command. If the credentials are not found, the user is prompted to enter their API key by calling the `ask_for_api_key` function.

    Parameters:
        message (telebot.types.Message): The Telegram message object that triggered the `/init` command.

    Returns:
        None
    """
    chat_id = message.chat.id
    already_exists, response_body = check_user_credentials(chat_id)
    if already_exists:
        bot.send_message(chat_id, "Your credentials are already stored 🗃️. To start your trading agent, please type /start 🚀")
    else:
        ask_for_api_key(message)
        

  
@bot.message_handler(commands=['start'])
def start(message):
    """
    Handles the '/start' command from a user, initiating or resuming a trading session.

    This function is triggered when a user sends the '/start' command to the Telegram bot. It checks if the user has an existing trader object and whether there is an active session. If there is no active session, the user is prompted to enter a ticker symbol. If there is an active session, the user is informed that they must wait for it to end before starting a new one. If the trader object does not exist, the user is asked to initialize their credentials with '/init'.

    Parameters:
        message (telebot.types.Message): The Telegram message object that triggered the '/start' command.

    Returns:
        None
    """
    chat_id = message.chat.id
    trader = retreive_trader(chat_id)

    if trader and (not trader.session_alive):
        ask_for_ticker(message, trader)
    elif trader and trader.session_alive:
        bot.reply_to(message, "You already have an active session. Please wait for it to end before starting a new one. If you wish to stop the current session, use /stop.")
    else:

        bot.reply_to(message, "Please initialize your credentials first with /init.")
        
      
@bot.message_handler(commands=['stop'])
def stop(message):
    """
    Handles the '/stop' command from a user, terminating their active trading session.

    This function is triggered when a user sends the '/stop' command to the Telegram bot. 
    It retrieves the trader object associated with the user's chat ID. If there is an active trading session, 
    the function terminates it by updating the session status and notifying the user. 
    If there is no active session or the trader object does not exist, the user is informed accordingly.

    Parameters:
        message (telebot.types.Message): The Telegram message object that triggered the '/stop' command.

    Returns:
        None
    """
    chat_id = message.chat.id
    trader = retreive_trader(chat_id)

    if trader and (not trader.session_alive):
        bot.reply_to(message, "You don't have an active session to stop. Use /start to begin a new session. 🚀")
        
    elif trader and trader.session_alive:
        trader.session_alive = False
        response = requests.post(f"{BASE_URL_API}/stop_session/", json={"chat_id": str(trader.chat_id), 'session_alive': trader.session_alive, 'ticker': "null", 'end_time': "null", 'amount_to_spend': "null"})
        response_body = response.json()
        trade_counter = response_body.get('counter')
        cash_value = response_body.get('cash_value')
        portfolio_value = response_body.get('portfolio_value')
        trade_info = f"📊📊 RECAP 📊📊\nTotal trades made: {trade_counter}\nCash Value: {cash_value}$\nPortfolio Value:{portfolio_value}"
        bot.send_message(chat_id, "Your trading agent has been stopped. 🛑")
        bot.send_message(chat_id, trade_info)
    
    if not trader:
        bot.reply_to(message, "Please initialize your credentials first with /init. 🔑")

@bot.message_handler(func=lambda message: True)
def redirect_to_init_or_start(message):
    """
    Redirects any non-command messages based on the user's current session state.

    This function serves as a catch-all for messages that do not match other specific commands. It first retrieves the trader object associated with the user's chat ID. If a trader object exists and there is an active session, the user is informed that they must wait for the current session to end before starting a new one, with a suggestion to use '/stop' if they wish to terminate the current session. If a trader object exists but there is no active session, the user is prompted to start trading with the '/start' command. If no trader object is found, the user is advised to initialize their credentials with the '/init' command.

    Parameters:
        message (telebot.types.Message): The Telegram message object.

    Returns:
        None
    """
    chat_id = message.chat.id
    trader = retreive_trader(chat_id)
    if trader and trader.session_alive:
        bot.send_message(chat_id, "You already have an active session. Please wait for it to end before starting a new one. If you wish to stop the current session, use /stop. 🛑")
    elif trader and not trader.session_alive:
        bot.send_message(chat_id, "You can start trading by using the /start command. 🚀")
    else:
        bot.send_message(chat_id, "Please initialize your credentials first with the /init command. 🔑")



  
######################################################################################################################
#                                                                                                                    #
#                                                                                                                    #
#                                                      MAIN                                                          #
#                                                                                                                    #
#                                                                                                                    #
######################################################################################################################

def start_bot():
    bot.polling()

def run_other_task():
    while(True):
        if len(LIST_TRADERS) > 0:
            for trader in LIST_TRADERS:
                trader.send_message('Hello, I am a bot')
                time.sleep(10)



def main():
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    # agent_thread = threading.Thread(target=run_other_task)
    # agent_thread.start()

if __name__ == "__main__":
    start_bot()