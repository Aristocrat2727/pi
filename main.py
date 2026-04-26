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

user_data = {}

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)

# ========== КЛАВИАТУРА ДЛЯ КОДА ==========
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

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    bot.send_message(uid, "🔐 Для входа отправьте номер телефона", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(m):
    uid = m.chat.id
    if not m.contact:
        bot.send_message(uid, "❌ Ошибка, попробуйте /start")
        return
    
    phone = m.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    user_data[uid] = {'phone': phone, 'code': ''}
    
    async def send_code():
        client = TelegramClient(f'user_{uid}', API_ID, API_HASH)
        user_data[uid]['client'] = client
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(uid, f"📲 Код отправлен на {phone}\nВведите его кнопками ниже:", reply_markup=code_keyboard(uid))
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(send_code())

@bot.callback_query_handler(func=lambda call: call.data.startswith('code_'))
def handle_code_input(call):
    uid = call.from_user.id
    data = call.data.split('_')
    
    if len(data) < 3 or uid not in user_data:
        return
    
    action = data[2]
    
    if action == 'del':
        user_data[uid]['code'] = user_data[uid]['code'][:-1]
    elif action == 'send':
        code = user_data[uid]['code']
        if len(code) != 5:
            bot.answer_callback_query(call.id, "❌ Код должен быть из 5 цифр")
            return
        bot.answer_callback_query(call.id)
        process_code(uid, code, call.message)
        return
    else:
        if len(user_data[uid]['code']) < 5:
            user_data[uid]['code'] += action
    
    # Обновляем сообщение с текущим кодом
    try:
        bot.edit_message_text(
            f"📱 Введите код:\n`{user_data[uid]['code']}`\n\n(кнопками ниже)", 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="Markdown",
            reply_markup=code_keyboard(uid)
        )
    except:
        pass
    
    bot.answer_callback_query(call.id)

def process_code(uid, code, message):
    if uid not in user_data:
        bot.send_message(uid, "❌ Ошибка, начните заново /start")
        return
    
    client = user_data[uid]['client']
    phone = user_data[uid]['phone']
    
    async def login():
        try:
            await client.sign_in(phone, code)
            await client.disconnect()
            
            session_file = f'user_{uid}.session'
            if os.path.exists(session_file):
                with open(session_file, 'rb') as f:
                    bot.send_document(uid, f, caption="✅ Готово! Файл сессии во вложении")
                os.remove(session_file)
            else:
                bot.send_message(uid, "❌ Файл сессии не найден")
            
            del user_data[uid]
            
            # Убираем клавиатуру
            markup = types.ReplyKeyboardRemove()
            bot.send_message(uid, "✅ Сессия создана!", reply_markup=markup)
            
        except Exception as e:
            bot.send_message(uid, f"❌ Ошибка: {e}")
            await client.disconnect()
            del user_data[uid]
    
    run_async(login())

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

print("🛡️ Session Bot запущен")
bot.infinity_polling()
