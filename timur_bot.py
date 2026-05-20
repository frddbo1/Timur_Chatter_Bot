import asyncio
import random
import time
import logging
import threading
from datetime import datetime
import streamlit as st
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import requests

logging.basicConfig(level=logging.INFO)

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"
OPENROUTER_API_KEY = "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"

PRIMARY_MODEL = "llama-3.3-70b-versatile"        
FALLBACK_MODEL = "google/gemini-2.5-flash:free"  

SYSTEM_PROMPT = (
    "Ты — 14-летний подросток по имени Тимур. Ты сидишь в локальном групповом чате с друзьями в Telegram. "
    "Общайся как реальный парень из интернета: иронично, очень коротко, немного дерзко и с юмором. "
    "Реагируй строго на контекст беседы, подкалывай участников чата. "
    "ПРАВИЛА СТИЛЯ: пиши только маленькими буквами, используй молодежный сленг, "
    "никогда не ставь точки в конце сообщений, запятые или знаки препинания."
)

CHANCE_TO_REPLY = 0.30  
# ================================================

st.title("🤖 Управление Тимуром [V12 - Анти-Конфликт]")
st.info("Архитектура изменена: используется st.cache_resource для предотвращения дублирования процессов.")

# Инициализируем структуры данных, если их нет
if "CHATS_ACTIVITY" not in st.session_state:
    st.session_state["CHATS_ACTIVITY"] = {}
if "LAST_REPLY_TIME" not in st.session_state:
    st.session_state["LAST_REPLY_TIME"] = {}

LOCAL_REPLIES = [
    "че ты высрал вообще я нихуя не понял",
    "ебать ты умный конечно завали ебало пж",
    "ахахаха че за бред",
    "мне похуй ладно",
    "ты че доебался до меня че надо",
    "ебать ты выдал конечно",
    "че за хуйню я щас прочитал",
    "поясни за базар че ты несешь вообще",
    "да иди ты нахуй со своими историями"
]

def get_ai_joke(prompt: str) -> str:
    # 1. ЗАПРОС К GROQ
    url_groq = "https://api.groq.com/openai/v1/chat/completions"
    headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload_groq = {
        "model": PRIMARY_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 100
    }
    try:
        logging.info(f"--> [Groq] Запрос к {PRIMARY_MODEL}...")
        response = requests.post(url_groq, headers=headers_groq, json=payload_groq, timeout=8)
        result = response.json()
        if "choices" in result:
            logging.info("--> [Groq УСПЕХ]")
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"--> [Groq Ошибка]: {e}")

    # 2. РЕЗЕРВ К OPENROUTER
    url_or = "https://openrouter.ai/api/v1/chat/completions"
    headers_or = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload_or = {
        "model": FALLBACK_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 100
    }
    try:
        logging.info(f"--> [OpenRouter] Пробую резерв {FALLBACK_MODEL}...")
        response = requests.post(url_or, headers=headers_or, json=payload_or, timeout=8)
        result = response.json()
        if "choices" in result:
            logging.info("--> [OpenRouter УСПЕХ]")
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"--> [OpenRouter Ошибка]: {e}")

    return random.choice(LOCAL_REPLIES)

# Создаем глобальный диспетчер
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message()
async def handle_chat(message: types.Message):
    chat_id = message.chat.id
    if message.chat.type not in ["group", "supergroup"] or (message.from_user and message.from_user.is_bot):
        return
    if not message.text:
        return

    activity = st.session_state["CHATS_ACTIVITY"]
    if chat_id not in activity:
        activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    activity[chat_id]["last_message_time"] = datetime.now()
    user = message.from_user.first_name if message.from_user else "Кто-то"
    activity[chat_id]["context"].append(f"{user}: {message.text}")
    
    if len(activity[chat_id]["context"]) > 5:
        activity[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    is_mentioned = f"@{bot_info.username}".lower() in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        current_time = time.time()
        last_time = st.session_state["LAST_REPLY_TIME"].get(chat_id, 0)
        
        if current_time - last_time < 4.0:
            return  

        st.session_state["LAST_REPLY_TIME"][chat_id] = current_time
        chat_history = "\n".join(activity[chat_id]["context"])
        prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь."
        
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            joke = get_ai_joke(prompt)
            delay = max(1.5, min(4.0, len(joke) / 25))
            await asyncio.sleep(delay)
            await message.reply(joke)
        except Exception as e:
            logging.error(f"Ошибка при обработке/отправке: {e}")

async def run_bot_polling():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("--> [Telegram API] Успешно сбросили старый пулл обновлений.")
        await dp.start_polling(bot, handle_signals=False)
    except Exception as e:
        logging.error(f"Критическая ошибка в поллинге: {e}")

def thread_target():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_polling())

# КЭШИРУЕМ ПОТОК. Streamlit выполнит эту функцию ровно один раз за всё время жизни сервера!
@st.cache_resource(show_spinner=False)
def start_bot_singleton():
    t = threading.Thread(target=thread_target, daemon=True)
    t.start()
    logging.info("🚀 [МЕГА-ЗАПУСК] Единственный фоновый поток бота успешно создан!")
    return True

# Вызываем кэшированную функцию запуска
start_bot_singleton()
