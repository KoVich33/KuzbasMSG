from flask import Flask, request, jsonify, session
from flask_cors import CORS
from database import db, User, Message
from datetime import datetime
import hashlib
import os

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=[
    "http://127.0.0.1:5500",
    "https://your-frontend-url.onrender.com"  # Замените на ваш URL
])

# Конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///messenger.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

db.init_app(app)

# Хэширование пароля
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# API роуты

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Пользователь уже существует'}), 400
        
        hashed_password = hash_password(password)
        new_user = User(username=username, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        
        return jsonify({
            'message': 'Регистрация успешна',
            'user': {'id': new_user.id, 'username': new_user.username}
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if not user or user.password != hash_password(password):
            return jsonify({'error': 'Неверное имя пользователя или пароль'}), 401
        
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'message': 'Вход выполнен успешно',
            'user': {'id': user.id, 'username': user.username}
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Выход выполнен успешно'}), 200

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'username': session['username']
            }
        }), 200
    return jsonify({'authenticated': False}), 200

@app.route('/api/users', methods=['GET'])
def get_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    current_user_id = session['user_id']
    users = User.query.filter(User.id != current_user_id).all()
    
    users_list = [{'id': user.id, 'username': user.username} for user in users]
    return jsonify(users_list), 200

@app.route('/api/messages/<int:receiver_id>', methods=['GET'])
def get_messages(receiver_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    sender_id = session['user_id']
    
    messages = Message.query.filter(
        ((Message.sender_id == sender_id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == sender_id))
    ).order_by(Message.timestamp.asc()).all()
    
    # Помечаем сообщения как прочитанные
    for message in messages:
        if message.receiver_id == sender_id and not message.is_read:
            message.is_read = True
    db.session.commit()
    
    messages_list = [{
        'id': msg.id,
        'content': msg.content,
        'sender_id': msg.sender_id,
        'receiver_id': msg.receiver_id,
        'timestamp': msg.timestamp.isoformat(),
        'is_read': msg.is_read,
        'is_mine': msg.sender_id == sender_id
    } for msg in messages]
    
    return jsonify(messages_list), 200

@app.route('/api/messages', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        data = request.json
        content = data.get('content')
        receiver_id = data.get('receiver_id')
        
        if not content or not receiver_id:
            return jsonify({'error': 'Контент и получатель обязательны'}), 400
        
        new_message = Message(
            content=content,
            sender_id=session['user_id'],
            receiver_id=receiver_id
        )
        
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({
            'message': 'Сообщение отправлено',
            'id': new_message.id,
            'timestamp': new_message.timestamp.isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/unread_count', methods=['GET'])
def get_unread_count():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    count = Message.query.filter_by(
        receiver_id=session['user_id'],
        is_read=False
    ).count()
    
    return jsonify({'count': count}), 200

# Создание таблиц
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)