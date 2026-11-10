#!/usr/bin/env python
"""Test individual Telegram commands quickly with timeout"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import signal

class TimeoutError(Exception):
    pass

def handler(signum, frame):
    raise TimeoutError()

# Only test the fast ones - /start and /help don't hit external services
from notifications.telegram_bot import TelegramBotClient

token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    raise SystemExit('Set TELEGRAM_BOT_TOKEN before running this test script.')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
bot = TelegramBotClient(bot_token=token, chat_id=chat_id)

for cmd in ['/start', '/help']:
    print(f"\n=== {cmd} ===")
    try:
        resp = bot.handle_command(cmd)
        print(f"OK len={len(resp)}")
    except Exception as e:
        print(f"FAILED: {e}")