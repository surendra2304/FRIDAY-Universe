#!/usr/bin/env python
"""Test Telegram bot polling"""
import os
from notifications.telegram_bot import TelegramBotClient
import time

token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    raise SystemExit('Set TELEGRAM_BOT_TOKEN before running this test script.')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

bot = TelegramBotClient(bot_token=token, chat_id=chat_id)
print('Starting polling...')
bot.start_polling_in_background()

# Send a test message
import requests
url = 'https://api.telegram.org/bot' + token + '/sendMessage'
requests.post(url, json={'chat_id': chat_id, 'text': '/balance'}, timeout=10)
print('Sent /balance command')

# Wait for processing
print('Waiting 8 seconds for bot to process...')
time.sleep(8)

bot.stop_polling()
print('Polling stopped')