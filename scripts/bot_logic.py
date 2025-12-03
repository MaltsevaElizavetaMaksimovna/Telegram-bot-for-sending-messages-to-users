from datetime import datetime, timezone
from bot.bot import Bot
from bot.handler import MessageHandler

from .config import TOKEN, DEFAULT_CHAT_IDS
from .db import fetch_pending_messages, insert_feedback


def resolve_recipients(users_group: int) -> list[str]:
    """Пока просто хардкодим список чатов."""
    return DEFAULT_CHAT_IDS


def should_send(message_time_str: str, now_utc: datetime) -> bool:
    """Логика 'now' или время <= текущего UTC."""
    if not message_time_str:
        return False

    mt = message_time_str.strip().lower()
    if mt == "now":
        return True

    try:
        dt = datetime.strptime(message_time_str, "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now_utc
    except ValueError:
        print(f"[WARN] bad message_time='{message_time_str}'")
        return False


def send_message_to_recipients(bot: Bot, row) -> int:
    """Отправляем одно сообщение всем получателям, возвращаем количество успешных отправок."""
    msg_id = row["id"]
    text = row["message"] or ""
    users_group = row["users_group"] or 1

    recipients = resolve_recipients(users_group)
    sent_count = 0

    for chat_id in recipients:
        try:
            bot.send_text(chat_id=chat_id, text=text)
            sent_count += 1
        except Exception as e:
            print(f"[ERROR] send msg_id={msg_id} to {chat_id}: {e}")

    print(f"[INFO] msg_id={msg_id}: sent {sent_count}/{len(recipients)}")
    return sent_count


def check_and_send_messages(bot: Bot):
    """Вызывается планировщиком: проверить БД и разослать готовые сообщения."""
    now_utc = datetime.now(timezone.utc)
    rows = fetch_pending_messages()
    if not rows:
        return

    print(f"[INFO] check_and_send_messages: {len(rows)} candidate(s)")
    for row in rows:
        if should_send(row["message_time"], now_utc):
            sent_count = send_message_to_recipients(bot, row)
            insert_feedback(row["id"], sent_count, 0)


# ========== инициализация бота и handler'ов ==========

def on_message(bot_obj: Bot, event):
    """Простой обработчик /ping."""
    text = (getattr(event, "text", "") or "").strip().lower()
    if text == "/ping":
        bot_obj.send_text(chat_id=event.from_chat, text="Бот активен!")


def init_bot() -> Bot:
    """Создаём Bot, регистрируем handler и возвращаем готовый объект."""
    bot = Bot(token=TOKEN, is_myteam=True)

    bot.dispatcher.add_handler(MessageHandler(callback=on_message))
    return bot