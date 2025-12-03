# app/webapp.py

from flask import Flask, request, redirect, url_for, render_template_string, jsonify
from .db import get_messages_with_stats, insert_message_query, get_message_stats

INDEX_HTML = """
<!doctype html>
<title>Broadcast demo</title>
<h1>Создать рассылку</h1>
<form method="post" action="{{ url_for('create_message') }}">
  <label>Текст сообщения:</label><br>
  <textarea name="message" rows="4" cols="40"></textarea><br><br>

  <label>Время отправки (UTC):</label><br>
  <input name="message_time" placeholder="now или 2025-11-25 15:30"><br><br>

  <button type="submit">Создать</button>
</form>

<hr>

<h2>Список рассылок</h2>
<table border="1" cellpadding="4" cellspacing="0">
  <tr>
    <th>ID</th>
    <th>Текст</th>
    <th>Время</th>
    <th>Отправлено (чатов)</th>
  </tr>
  {% for row in rows %}
  <tr>
    <td>{{ row['id'] }}</td>
    <td>{{ row['message'][:40] }}</td>
    <td>{{ row['message_time'] }}</td>
    <td>{{ row['sent'] }}</td>
  </tr>
  {% endfor %}
</table>
"""


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index():
        rows = get_messages_with_stats()
        return render_template_string(INDEX_HTML, rows=rows)

    @app.route("/create", methods=["POST"])
    def create_message():
        message = request.form.get("message", "").strip()
        message_time = request.form.get("message_time", "").strip() or "now"
        users_group = 1  # пока хардкод

        insert_message_query(message, message_time, users_group)
        return redirect(url_for("index"))

    @app.route("/api/stats/<int:message_id>", methods=["GET"])
    def api_stats(message_id):
        row = get_message_stats(message_id)
        if row is None:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "id": row["id"],
            "message": row["message"],
            "message_time": row["message_time"],
            "sent": row["sent"],
            "clicks": row["clicks"],
        })

    return app