#!/usr/bin/env python
"""Diagnose Telegram bot commands - find which ones fail"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from notifications.telegram_bot import TelegramBotClient

token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    raise SystemExit('Set TELEGRAM_BOT_TOKEN before running this test script.')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
bot = TelegramBotClient(bot_token=token, chat_id=chat_id)

commands = [
    '/start', '/help', '/status', '/balance', '/positions', '/pnl',
    '/history', '/scan', '/balance binance', '/positions icmarkets',
    '/pnl combined',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"TESTING: {cmd}")
    print('='*60)
    try:
        resp = bot.handle_command(cmd)
        print(f"OK (len={len(resp)})")
        print(resp[:300])
    except Exception as e:
        import traceback
        print(f"FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()