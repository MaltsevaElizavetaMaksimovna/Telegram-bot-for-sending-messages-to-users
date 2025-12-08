# app.py
import os
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify, redirect, session
from flask_sqlalchemy import SQLAlchemy
from time import time
import jwt
from jwt.exceptions import InvalidTokenError

# Загружаем переменные до создания app
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

VK_CLIENT_ID = os.getenv('VK_CLIENT_ID')
VK_CLIENT_SECRET = os.getenv('VK_CLIENT_SECRET')
REDIRECT_URI = 'https://localhost/auth'

# Читаем публичный ключ
with open('vk_public_key.pem', 'r') as f:
    PUBLIC_KEY_PEM = f.read()

basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "users.db")}'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vk_id = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    patronymic = db.Column(db.String(100))
    birthdate = db.Column(db.String(10))
    email = db.Column(db.String(255))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.Integer)

def validate_id_token(id_token: str) -> dict:
    try:
        claims = jwt.decode(
            id_token,
            PUBLIC_KEY_PEM,
            algorithms=["RS256"],
            #audience=VK_CLIENT_ID,
            options={
                "verify_signature": True,
                "require": ["exp", "iat", "sub"] 
            }
        )
        return claims
    except InvalidTokenError as e:
        raise Exception(f"Invalid id_token: {str(e)}")

@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.filter_by(vk_id=user_id).first()
        if user:
            return f"<h1>Привет, {user.first_name or 'друг'}!</h1><a href='/logout'>Выйти</a>"
    return open('index.html', encoding='utf-8').read()

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/set_verifier', methods=['POST'])
def set_verifier():
    data = request.get_json()
    session['vk_code_verifier'] = data['code_verifier']
    session['vk_state'] = data['state']
    return jsonify({"ok": True})

@app.route('/auth')
def vk_auth():
    code = request.args.get('code')
    device_id = request.args.get('device_id')
    received_state = request.args.get('state')

    if not code or not device_id or not received_state:
        return "Ошибка: не хватает параметров от VK", 400

    expected_state = session.get('vk_state')
    if received_state != expected_state:
        return "Ошибка: invalid_state", 400

    code_verifier = session.get('vk_code_verifier')
    if not code_verifier:
        return "Ошибка: code_verifier утерян", 400

    # ИСПРАВЛЕНО: убраны пробелы в URL
    resp = requests.post('https://id.vk.ru/oauth2/auth', data={
        'grant_type': 'authorization_code',
        'client_id': VK_CLIENT_ID,
        'client_secret': VK_CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code,
        'code_verifier': code_verifier,
        'device_id': device_id
    })

    if resp.status_code != 200:
        print("VK Auth Error:", resp.text)
        return "Ошибка авторизации в VK", 400

    tokens = resp.json()
    id_token = tokens.get('id_token')
    if not id_token:
        return "Ошибка: id_token отсутствует", 400

    try:
        claims = validate_id_token(id_token)
    except Exception as e:
        print("JWT Error:", e)
        return "Ошибка валидации токена", 400
    
    # После получения tokens и id_token (но даже если id_token не содержит данных)
    access_token = tokens['access_token']

    # Запрос к VK API для получения профиля
    user_info_resp = requests.get(
        'https://api.vk.com/method/users.get',
        params={
            'access_token': access_token,
            'v': '5.241',
            'fields': 'first_name,last_name,bdate,email'
        }
    )

    if user_info_resp.status_code != 200:
        print("VK API Error:", user_info_resp.text)
        return "Ошибка получения данных пользователя", 500

    user_info = user_info_resp.json()
    if 'error' in user_info:
        print("VK API Error:", user_info['error'])
        return "Ошибка VK API", 500

    vk_user = user_info['response'][0]

    user_data = {
        'vk_id': str(vk_user['id']),
        'first_name': vk_user.get('first_name'),
        'last_name': vk_user.get('last_name'),
        'patronymic': None,  # VK не предоставляет отчество
        'email': claims.get('email'),  # email может быть только в id_token!
        'birthdate': vk_user.get('bdate'),  # формат: D.M.YYYY или D.M (если год скрыт)
        'access_token': access_token,
        'refresh_token': tokens.get('refresh_token'),
        'token_expires_at': int(time()) + tokens['expires_in']
    }
    
    '''user_data = {
        'vk_id': str(claims['sub']),
        'first_name': claims.get('given_name'),
        'last_name': claims.get('family_name'),
        'patronymic': claims.get('patronymic'),
        'email': claims.get('email'),
        'birthdate': claims.get('birthdate'),
        'access_token': tokens['access_token'],
        'refresh_token': tokens.get('refresh_token'),
        'token_expires_at': int(time()) + tokens['expires_in']
    }'''

    print(user_data)

    user = User.query.filter_by(vk_id=user_data['vk_id']).first()
    if not user:
        user = User(**user_data)
        db.session.add(user)
    else:
        for k, v in user_data.items():
            setattr(user, k, v)
    db.session.commit()

    session['user_id'] = user.vk_id
    return redirect('/')

@app.route('/refresh', methods=['POST'])
def refresh_token():
    data = request.get_json()
    user_id = data.get('user_id')
    user = User.query.filter_by(vk_id=user_id).first()
    if not user or not user.refresh_token:
        return jsonify({"error": "No refresh token"}), 404

    resp = requests.post('https://id.vk.ru/oauth2/auth', data={
        'grant_type': 'refresh_token',
        'client_id': VK_CLIENT_ID,
        'client_secret': VK_CLIENT_SECRET,
        'refresh_token': user.refresh_token
    })

    if resp.status_code != 200:
        return jsonify({"error": "Token refresh failed"}), 401

    new_tokens = resp.json()
    user.access_token = new_tokens['access_token']
    user.refresh_token = new_tokens.get('refresh_token', user.refresh_token)
    user.token_expires_at = int(time()) + new_tokens['expires_in']
    db.session.commit()

    return jsonify({"access_token": user.access_token})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=True)