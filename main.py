import os
import telebot
from telebot import types
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import asyncio
import threading

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)

user_data = {}

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
    bot.send_message(uid, "🔐 Нажмите кнопку, чтобы войти", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if not m.contact:
        bot.send_message(uid, "❌ Ошибка, попробуйте /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    user_data[uid] = {'phone': phone, 'step': 'code'}
    
    async def send_code():
        client = TelegramClient(f'session_{uid}', API_ID, API_HASH)
        user_data[uid]['client'] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, f"📲 На номер {phone} отправлен код.\nВведите его цифрами:")
            bot.register_next_step_handler(m, get_code)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(send_code())

def get_code(m):
    uid = m.chat.id
    code = m.text.strip()
    
    if uid not in user_data or 'client' not in user_data[uid]:
        bot.send_message(uid, "❌ Ошибка, начните заново /start")
        return
    
    user_data[uid]['code'] = code
    client = user_data[uid]['client']
    phone = user_data[uid]['phone']
    
    async def login():
        try:
            await client.sign_in(phone, code)
            await finish_session(uid, client)
        except SessionPasswordNeededError:
            bot.send_message(uid, "🔐 Введите пароль от аккаунта (2FA):")
            bot.register_next_step_handler(m, get_password)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(login())

def get_password(m):
    uid = m.chat.id
    password = m.text.strip()
    
    if uid not in user_data or 'client' not in user_data[uid]:
        bot.send_message(uid, "❌ Ошибка, начните заново /start")
        return
    
    client = user_data[uid]['client']
    
    async def login_with_password():
        try:
            await client.sign_in(password=password)
            await finish_session(uid, client)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(login_with_password())

async def finish_session(uid, client):
    await client.disconnect()
    
    session_file = f'session_{uid}.session'
    if os.path.exists(session_file):
        with open(session_file, 'rb') as f:
            bot.send_document(uid, f, caption="✅ Готово! Файл сессии во вложении")
        os.remove(session_file)
    else:
        bot.send_message(uid, "❌ Файл не найден")
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "✅ Вход выполнен", reply_markup=markup)
    
    if uid in user_data:
        del user_data[uid]

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

print("🚀 Бот запущен (поддержка 2FA)")
bot.infinity_polling()
