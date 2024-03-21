import redis
import telebot
import os

from dotenv import load_dotenv

load_dotenv("./../.env")

# Configuration de la connexion Redis
redis_client = redis.Redis(host='redis', port=6379, db=0)
pubsub = redis_client.pubsub()

# Souscrire au canal Redis
pubsub.subscribe('trade_channel')

# Initialiser TeleBot avec votre token
bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"))

# Fonction pour écouter les messages Redis et agir
def listen_for_trades():
    for message in pubsub.listen():
        if message['type'] == 'message':
            # Extraire les informations de trade du message
            trade_info = message['data']
            trade_info = message['data'].decode('utf-8')  # Decode from bytes to string
            print(trade_info)
            print(type(trade_info))
            
            parts = trade_info.split(': ')
            chat_id = parts[1]
            message_info = parts[0] + ' 💸'

            # Envoyer une notification via Telegram
            bot.send_message(chat_id=chat_id, text=message_info)

# Lancer l'écoute dans un thread ou un processus séparé si nécessaire
listen_for_trades()
