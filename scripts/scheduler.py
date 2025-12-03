# app/scheduler.py

import time
import schedule
from .bot_logic import check_and_send_messages
from bot.bot import Bot


def setup_schedule(bot: Bot):
    """Регистрируем job в schedule."""
    schedule.every(1).minutes.do(check_and_send_messages, bot=bot)


def schedule_loop():
    """Бесконечный цикл для фонового потока."""
    while True:
        schedule.run_pending()
        time.sleep(5)