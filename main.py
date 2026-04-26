import asyncio
import os
import zipfile
import telebot
from telethon import TelegramClient

# ========== ТВОИ ДАННЫЕ ==========
TOKEN = os.getenv('TOKEN')          # токен бота (добавишь в переменные Railway)
API_ID = 28537210
API_HASH = "5388b7e4bc869cce695b682f2644a160"
# =================================

bot = telebot.TeleBot(TOKEN)

SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

user_sessions = {}

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, 
        "🔑 *Session Creator Bot*\n\n"
        "/new — создать сессию\n"
        "/cancel — отменить",
        parse_mode="Markdown")

@bot.message_handler(commands=['new'])
def new_session(msg):
    uid = msg.chat.id
    bot.send_message(uid, "📱 Введите номер телефона:\n`+71234567890`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_phone)

def process_phone(msg):
    uid = msg.chat.id
    phone = msg.text.strip()
    
    if not phone.startswith('+'):
        bot.send_message(uid, "❌ Номер должен начинаться с +\nПопробуйте ещё раз:")
        bot.register_next_step_handler(msg, process_phone)
        return
    
    session_name = f"{SESSION_DIR}/user_{uid}"
    client = TelegramClient(session_name, API_ID, API_HASH)
    user_sessions[uid] = {"client": client, "phone": phone}
    
    async def send_code():
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, "✅ Код отправлен!\nВведите код (только цифры):")
            bot.register_next_step_handler(msg, process_code, client, phone)
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_sessions[uid]
    
    asyncio.run(send_code())

def process_code(msg, client, phone):
    uid = msg.chat.id
    code = msg.text.strip()
    
    async def sign_in():
        try:
            await client.connect()
            await client.sign_in(phone, code)
            await client.disconnect()
            
            session_file = f"{SESSION_DIR}/user_{uid}.session"
            
            if os.path.exists(session_file):
                zip_name = f"/tmp/session_{uid}.zip"
                with zipfile.ZipFile(zip_name, 'w') as zf:
                    zf.write(session_file, arcname=f"user_{uid}.session")
                
                with open(zip_name, 'rb') as f:
                    bot.send_document(uid, f, caption=f"✅ Сессия создана!\nНомер: `{phone}`", parse_mode="Markdown")
                
                os.remove(zip_name)
            else:
                bot.send_message(uid, "❌ Файл сессии не найден")
            
            del user_sessions[uid]
            
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_sessions[uid]
    
    asyncio.run(sign_in())

@bot.message_handler(commands=['cancel'])
def cancel(msg):
    uid = msg.chat.id
    if uid in user_sessions:
        async def close():
            await user_sessions[uid]["client"].disconnect()
        asyncio.run(close())
        del user_sessions[uid]
    bot.send_message(uid, "❌ Отменено")

print("🚀 Session Bot запущен")
bot.polling(none_stop=True)
