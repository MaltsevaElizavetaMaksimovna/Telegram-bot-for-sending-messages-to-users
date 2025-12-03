# main.py

import threading
from db import init_db
from webapp import create_app
from bot_logic import init_bot
from scheduler import setup_schedule, schedule_loop


def run_web():
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=False)


if __name__ == "__main__":
    # 1. Инициализируем БД (создаём таблицы)
    init_db()

    # 2. Инициализируем бота
    bot = init_bot()

    # 3. Настраиваем планировщик, привязывая к конкретному bot
    setup_schedule(bot)

    # 4. Запускаем веб и планировщик в фоновых потоках
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=schedule_loop, daemon=True).start()

    # 5. Основной поток - long polling VK Teams
    bot.start_polling()
    bot.idle()