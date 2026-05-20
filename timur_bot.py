import asyncio
import random
import time
import logging
from datetime import datetime, timedelta
import streamlit as st
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import requests

# Настройка логирования для консоли Streamlit
logging.basicConfig(level=logging.INFO)

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"

SYSTEM_PROMPT = (
    "Ты — участник локального чата в Telegram группе. Твоя цель - нести максимальный не связанный бред и смешить людей "
    "иметь свой характер, влиться в общество, твое имя - Тимур, ты парень 14 летний в интернете "
    "пиши коротко, как обычный человек в мессенджере "
    "не пиши никогда не в коем случае запятые и точки, знаки восклицания и знаки вопроса "
    "Не будь вежливым помощником. Если тебя троллят — тролль в ответ еще жестче, с матами, очень токсично"
)

CHANCE_TO_REPLY = 0.20  # Шанс ответа 20%
SILENCE_TIMEOUT = 3000
# ================================================

# Инициализация интерфейса Streamlit (чтобы сервер видел активность)
st.title("🤖 Панель управления ботом Тимур")
st.subheader("Статус: Работает на серверах Streamlit Cloud")
st.text("Бот запущен асинхронно в фоновом режиме.")

# Инициализируем объекты aiogram
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Глобальные структуры данных храним на уровне модуля
if not hasattr(st, "_bot_chats_activity"):
    st._bot_chats_activity = {}
if not hasattr(st, "_bot_last_reply_time"):
    st._bot_last_reply_time = {}

def get_ai_joke(prompt: str) -> str:
    """Запрос к Groq API (Llama 3)"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.5, # Чуть снизил с 2.0 до 1.5, чтобы выдавал бред, но не превращался в кашу из символов
        "max_tokens": 150
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        else:
            print(f"Ошибка Groq API: {result}")
            return "ебать че то я тупой не понимаю нихуя я сломался"
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        return "сервер лег ебать ахахахпвщпаъх"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    chat_id = message.chat.id
    if chat_id in st._bot_chats_activity:
        st._bot_chats_activity[chat_id]["context"] = []
    await message.reply("ебать вы мне стерли память нахуй пидарасы аыааааа я умираю ааа , . . . .     привет)")

@dp.message()
async def handle_chat(message: types.Message):
    chat_id = message.chat.id
    
    # 1. Защита от лички и ботов
    if message.chat.type not in ["group", "supergroup"] or (message.from_user and message.from_user.is_bot):
        return

    # Проверка на пустой текст (стикеры, гифки)
    if not message.text:
        return

    # 2. Логика истории контекста
    if chat_id not in st._bot_chats_activity:
        st._bot_chats_activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    st._bot_chats_activity[chat_id]["last_message_time"] = datetime.now()
    
    user = message.from_user.first_name if message.from_user else "Кто-то"
    st._bot_chats_activity[chat_id]["context"].append(f"{user}: {message.text}")
    if len(st._bot_chats_activity[chat_id]["context"]) > 5:
        st._bot_chats_activity[chat_id]["context"].pop(0)

    # 3. Проверка триггеров на ответ
    bot_info = await bot.get_me()
    bot_username = f"@{bot_info.username}"
    
    is_mentioned = bot_username.lower() in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        current_time = time.time()
        last_time = st._bot_last_reply_time.get(chat_id, 0)
        
        # Кулдаун: исправил обратно на логичные 5-7 секунд (в твоем коде стояло 0.2 сек)
        if current_time - last_time < 5.0:
            return  

        st._bot_last_reply_time[chat_id] = current_time

        chat_history = "\n".join(st._bot_chats_activity[chat_id]["context"])
        prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь на последнее сообщение."
        
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        joke = get_ai_joke(prompt)
        
        delay = max(2.0, min(5.0, len(joke) / 25))
        await asyncio.sleep(delay)
        
        try:
            await message.reply(joke)
        except Exception as e:
            print(f"Ошибка при отправке реплая: {e}")

async def silence_checker():
    """Фоновый чекер тишины, адаптированный под Streamlit"""
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        
        for chat_id, data in list(st._bot_chats_activity.items()):
            if now - data["last_message_time"] > timedelta(seconds=SILENCE_TIMEOUT):
                chat_history = "\n".join(data["context"])
                prompt = f"В чате тишина. Последнее обсуждение:\n{chat_history}\n\nНапиши один короткий провокационный вброс."
                
                joke = get_ai_joke(prompt)
                try:
                    await bot.send_message(chat_id, joke)
                    st._bot_chats_activity[chat_id]["last_message_time"] = datetime.now()
                except Exception as e:
                    print(f"Ошибка отправки триггера тишины: {e}")

async def main():
    # Запускаем чекер тишины внутри текущего event loop
    asyncio.create_task(silence_checker())
    print("Тимур успешно запущен в Streamlit Cloud!")
    # handle_signals=False — критически важно для работы в Streamlit!
    await dp.start_polling(bot, handle_signals=False)

# Предотвращаем повторный запуск циклов при перезагрузке страницы интерфейса
if "bot_running" not in st.session_state:
    st.session_state.bot_running = True
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.create_task(main())
