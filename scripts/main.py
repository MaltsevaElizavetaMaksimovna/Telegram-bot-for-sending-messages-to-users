import threading
import schedule
import time
import sqlite3
from datetime import datetime, timezone

from bot.bot import Bot
from bot.handler import MessageHandler

# ================== НАСТРОЙКИ ==================

TOKEN = "001.2190967850.0383199263:1011970881"  # TODO: вынести в ENV
DB_PATH = "databases/SQLite.db"  # или свой путь к БД

# ВРЕМЕННАЯ заглушка: сопоставление users_group -> список chat_id
# Потом заменишь на таблицу с группами / нормальный запрос в БД.
DEFAULT_CHAT_IDS = [
    "n.lyzunenko@test-123645965336.bizml.ru",
    "AoLJrsA6x1EdRf3xNm4",
]

def resolve_recipients(users_group: int) -> list[str]:
    """
    Заглушка. Сейчас просто возвращаем один и тот же список чатов
    для любых групп. Потом здесь можно сделать SELECT из таблицы
    users_groups / users / subscriptions и т.д.
    """
    return DEFAULT_CHAT_IDS

# ================== ИНИЦИАЛИЗАЦИЯ БОТА И БД ==================

bot = Bot(token=TOKEN, is_myteam=True)

db_lock = threading.Lock()
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row  # удобно обращаться по имени колонки

# ================== РАБОТА С ВРЕМЕНЕМ ==================

def should_send(message_time_str: str, now_utc: datetime) -> bool:
    """
    message_time:
      - 'now' -> отправляем сразу
      - 'YYYY-MM-DD HH:MM' (UTC) -> отправляем, если <= текущего времени (UTC)
    """
    if not message_time_str:
        return False

    mt = message_time_str.strip().lower()
    if mt == "now":
        return True

    try:
        # парсим как UTC
        dt = datetime.strptime(message_time_str, "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now_utc
    except ValueError:
        print(f"[WARN] Неверный формат message_time='{message_time_str}', пропускаю")
        return False

# ================== ЗАПРОСЫ К БД ==================

def fetch_pending_messages():
    """
    Берём все сообщения из message_query, по которым ещё нет записи
    в message_feedback (то есть рассылка ещё не делалась).
    """
    with db_lock:
        cur = conn.cursor()
        cur.execute("""
            SELECT mq.id,
                   mq.message,
                   mq.img_url,
                   mq.img_file_name,
                   mq.url_for_button,
                   mq.text_for_button,
                   mq.message_time,
                   mq.users_group
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            WHERE mf.message_id IS NULL
        """)
        rows = cur.fetchall()
    return rows

def insert_feedback(message_id: int, number_of_recipients: int, url_follow_amount: int = 0):
    """
    Пишем агрегированную статистику в message_feedback.
    Пока url_follow_ammount = 0 — позже добавим инкремент при клике.
    """
    with db_lock:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO message_feedback (message_id, number_of_recepients, url_follow_ammount)
            VALUES (?, ?, ?)
        """, (message_id, number_of_recipients, url_follow_amount))
        conn.commit()

# ================== ОТПРАВКА СООБЩЕНИЙ ==================

def build_keyboard(message_row) -> dict | None:
    """
    Пока просто заглушка под будущую кнопку.
    Сейчас:
      - если есть text_for_button и url_for_button, можно либо:
        а) сделать кнопку с ссылкой (без трекинга кликов на стороне бота),
        б) или сделать callback-кнопку и в ответ присылать ссылку (трекаем клики).
    Для начала можно вообще не отправлять кнопку и оставить место под реализацию.
    """
    text_for_button = message_row["text_for_button"]
    url_for_button = message_row["url_for_button"]

    if not text_for_button or not url_for_button:
        return None

    # Вариант А (простая кнопка-ссылка БЕЗ счётчика на стороне бота).
    # Если в твоей версии библиотеки структура другая — здесь поправишь.
    keyboard = {
        "inline_keyboard_markup": {
            "inline_keyboard": [[
                {
                    "text": text_for_button,
                    "url": url_for_button,
                }
            ]]
        }
    }
    return keyboard

def send_message_to_recipients(message_row) -> int:
    """
    Отправляем одну рассылку по всем получателям.
    Возвращаем количество чатов, куда сообщение реально ушло
    """
    msg_id = message_row["id"]
    text = message_row["message"] or ""
    img_url = message_row["img_url"]
    img_file_name = message_row["img_file_name"]
    users_group = message_row["users_group"]

    recipients = resolve_recipients(users_group)
    keyboard = build_keyboard(message_row)

    sent_count = 0

    for chat_id in recipients:
        try:
            if img_url:
                # картинка по URL
                if keyboard:
                    bot.send_file(chat_id=chat_id, file=img_url, text=text, **keyboard)
                else:
                    bot.send_file(chat_id=chat_id, file=img_url, text=text)

            elif img_file_name:
                # локальный файл (например, "images/cat.jpg")
                if keyboard:
                    bot.send_file(chat_id=chat_id, file=img_file_name, text=text, **keyboard)
                else:
                    bot.send_file(chat_id=chat_id, file=img_file_name, text=text)

            else:
                # только текст
                if keyboard:
                    bot.send_text(chat_id=chat_id, text=text, **keyboard)
                else:
                    bot.send_text(chat_id=chat_id, text=text)

            sent_count += 1
        except Exception as e:
            # просто логируем ошибку, без ретраев
            print(f"[ERROR] Ошибка отправки message_id={msg_id} в чат {chat_id}: {e}")

    print(f"[INFO] Рассылка message_id={msg_id}: отправлено {sent_count} из {len(recipients)}")

    return sent_count

# ================== ОСНОВНОЙ JOB ДЛЯ schedule ==================

def check_and_send_messages():
    """
    Периодически вызывается планировщиком:
    - берёт ещё не разосланные сообщения;
    - фильтрует по времени (now или <= текущее UTC);
    - отправляет и пишет feedback.
    """
    now_utc = datetime.now(timezone.utc)
    rows = fetch_pending_messages()

    if not rows:
        return

    print(f"[INFO] check_and_send_messages(): найдено {len(rows)} кандидатов")

    for row in rows:
        message_time_str = row["message_time"]
        if should_send(message_time_str, now_utc):
            sent_count = send_message_to_recipients(row)
            insert_feedback(message_id=row["id"],
                            number_of_recipients=sent_count,
                            url_follow_amount=0)  # пока 0, позже добавим клики
        else:
            # ещё не настало время
            pass

# ================== ОБРАБОТЧИКИ БОТА ==================

def on_message(bot_obj, event):
    """
    Пока только /ping, но сюда же можно будет добавить обработку
    callback-кнопок для счётчика url_follow_ammount.
    """
    text = (getattr(event, "text", "") or "").strip().lower()

    if text == "/ping":
        bot_obj.send_text(chat_id=event.from_chat, text="Бот активен!")

    # Здесь позже можно будет:
    # - проверять event.callbackData / event.queryData
    # - если это клик по нашей кнопке, инкрементировать url_follow_ammount
    #   для нужного message_id.

bot.dispatcher.add_handler(MessageHandler(callback=on_message))

# ================== ЦИКЛ ПЛАНИРОВЩИКА ==================

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(5)

# Вызываем check_and_send_messages раз в минуту
schedule.every(1).minutes.do(check_and_send_messages)

# ================== ЗАПУСК ==================

if __name__ == "__main__":
    threading.Thread(target=schedule_loop, daemon=True).start()

    bot.start_polling()
    bot.idle()