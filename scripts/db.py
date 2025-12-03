import sqlite3
import threading
from .config import DB_PATH

_db_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def init_db():
    """Создаём таблицы, если ещё нет. на всякий случай"""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_query (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                img_url TEXT,
                img_file_name TEXT,
                url_for_button TEXT,
                text_for_button TEXT,
                message_time TEXT,
                users_group INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                number_of_recepients INTEGER,
                url_follow_ammount INTEGER
            )
        """)
        _conn.commit()


def fetch_pending_messages():
    """Берём сообщения, которых ещё нет в feedback (то есть не разосланы)."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.*
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            WHERE mf.message_id IS NULL
        """)
        return cur.fetchall()


def insert_feedback(message_id: int, number_of_recipients: int, url_follow_amount: int = 0):
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            INSERT INTO message_feedback (message_id, number_of_recepients, url_follow_ammount)
            VALUES (?, ?, ?)
        """, (message_id, number_of_recipients, url_follow_amount))
        _conn.commit()


def insert_message_query(message: str, message_time: str, users_group: int = 1):
    """Вызывается из веба — создать новую рассылку."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            INSERT INTO message_query (message, message_time, users_group)
            VALUES (?, ?, ?)
        """, (message, message_time, users_group))
        _conn.commit()


def get_messages_with_stats():
    """Для странички /: список рассылок + сколько отправлено."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.id, mq.message, mq.message_time,
                   IFNULL(mf.number_of_recepients, 0) AS sent
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            ORDER BY mq.id DESC
        """)
        return cur.fetchall()


def get_message_stats(message_id: int):
    """Для API /api/stats/<id>."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.id, mq.message, mq.message_time,
                   IFNULL(mf.number_of_recepients, 0) AS sent,
                   IFNULL(mf.url_follow_ammount, 0) AS clicks
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            WHERE mq.id = ?
        """, (message_id,))
        return cur.fetchone()