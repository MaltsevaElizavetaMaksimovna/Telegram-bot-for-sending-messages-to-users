import threading
import schedule
import time
from datetime import datetime
from bot.bot import Bot
from bot.handler import MessageHandler

# === Настройки ===
TOKEN = "001.2190967850.0383199263:1011970881"
CHAT_IDS = ["n.lyzunenko@test-123645965336.bizml.ru", "AoLJrsA6x1EdRf3xNm4"]

bot = Bot(token=TOKEN, is_myteam=True)

# === Функция для отправки сообщений ===
def send_day_of_week():
    day = datetime.now().strftime("%A")  # например, "Monday"
    text = f"Сегодня {day}"
    for chat_id in CHAT_IDS:
        bot.send_text(chat_id=chat_id, text=text)
    print(f"[{datetime.now()}] Сообщения отправлены")

# === Планировщик ===
schedule.every().day.at("09:00").do(send_day_of_week)

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(30)

# === Обработчик /ping ===
def on_message(bot, event):
    text = event.text.lower().strip()
    if text == "/ping":
        bot.send_text(chat_id=event.from_chat, text="Бот активен!")

# Регистрируем обработчик сообщений
bot.dispatcher.add_handler(MessageHandler(callback=on_message))

# Запускаем планировщик в отдельном потоке
threading.Thread(target=schedule_loop, daemon=True).start()

# === Основной цикл бота ===
bot.start_polling()
bot.idle()