#!/usr/bin/env python
"""Test Telegram bot functionality"""
from notifications.telegram_bot import TelegramBotClient
import requests

token = '[REDACTED:telegram_bot_token]'
chat_id = '[REDACTED:telegram_chat_id]'

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