#!/usr/bin/env python
"""Test Telegram bot functionality"""
import os
from notifications.telegram_bot import TelegramBotClient
import requests

token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    raise SystemExit('Set TELEGRAM_BOT_TOKEN before running this test script.')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

bot = TelegramBotClient(bot_token=token, chat_id=chat_id)
print('Configured:', bot.is_configured)
print('Chat ID match:', bot.chat_id == chat_id)

# Test handle_command directly
response = bot.handle_command('/status')
with open('response.txt', 'w', encoding='utf-8') as f:
    f.write(response)
print('Response written to response.txt (length:', len(response), ')')

# Test send_message
result = bot.send_message('Direct test message from test script')
print('Direct send result:', result)