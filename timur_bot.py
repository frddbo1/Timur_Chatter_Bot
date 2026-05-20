import asyncio
import random
import time
import logging
import threading
from datetime import datetime, timedelta
import streamlit as st
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import requests

# Логирование
logging.basicConfig(level=logging.INFO)

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"

# СЮДА ВСТАВЬ СВОЙ КЛЮЧ ОТ OPENROUTER (создай бесплатно на openrouter.ai)
OPENROUTER_API_KEY = "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"

PRIMARY_MODEL = "llama-3.1-70b-versatile" # Умная модель на Groq
FALLBACK_MODEL = "meta-llama/llama-3.1-8b-instruct:free" # Бесплатная Llama 3.1 на OpenRouter

SYSTEM_PROMPT = (
    "Ты — 14-летний парень по имени Тимур, сидишь в локальном групповом чате в Telegram. "
    "Твоя цель — общаться как реальный подросток в интернете: иронично, дерзко, местами токсично, но смешно. "
    "Не неси однообразный несвязный бред. Реагируй именно на то, что пишут люди, подкалывай их по контексту. "
    "Если тебя троллят или оскорбляют — жестко и токсично отвечай взаимностью, используй маты и интернет-сленг. "
    "ПРАВИЛА ОФОРМЛЕНИЯ: пиши исключительно маленькими буквами, коротко (до 20 слов), "
    "никогда не ставь точки в конце сообщений, запятые, знаки восклицания или вопроса. "
    "Никакого вежливого тона нейросети, ты обычный чел из чата."
)

CHANCE_TO_REPLY = 0.30  # Шанс авто-ответа 30%
SILENCE_TIMEOUT = 3000
# ================================================

if "CHATS_ACTIVITY" not in globals():
    CHATS_ACTIVITY = {}
if "LAST_REPLY_TIME" not in globals():
    LAST_REPLY_TIME = {}

st.title("🤖 Панель управления Тимуром [Безотказный Гибрид]")
st.subheader("Статус: Активен (Фоновый поток Python 3.14)")
st.write(f"Основной движок: **Groq (Llama 70B)**")
st.write(f"Резервный движок: **OpenRouter (Llama 8B Free)**")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

def get_ai_joke(prompt: str) -> str:
    """Запрос с обходом лимитов через два разных провайдера"""
    
    # 1. СТУЧИМСЯ В GROQ К УМНОЙ 70B
    url_groq = "https://api.groq.com/openai/v1/chat/completions"
    headers_groq = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload_groq = {
        "model": PRIMARY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.2,
        "max_tokens": 150
    }
    
    try:
        logging.info("--> [Groq] Запрос к умной модели 70B...")
        response = requests.post(url_groq, headers=headers_groq, json=payload_groq, timeout=8)
        result = response.json()
        
        if "choices" in result:
            logging.info("--> [Groq Успех] Ответила 70B")
            return result["choices"][0]["message"]["content"].strip()
            
        logging.warning("--> [Groq Лимит] Запрос заблокирован. Переключаюсь на OpenRouter...")
    except Exception as e:
        logging.error(f"--> [Groq Ошибка сети]: {e}. Переключаюсь на OpenRouter...")

    # 2. ЕСЛИ GROQ СДОХ — МГНОВЕННО ИДЕМ В OPENROUTER (Изолированный лимит)
    url_or = "https://openrouter.ai/api/v1/chat/completions"
    headers_or = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload_or = {
        "model": FALLBACK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.2,
        "max_tokens": 150
    }
    
    try:
        logging.info("--> [OpenRouter] Запрос к резервной бесплатной Llama 3.1 8B...")
        response = requests.post(url_or, headers=headers_or, json=payload_or, timeout=8)
        result = response.json()
        
        if "choices" in result:
            logging.info("--> [OpenRouter Успех] Ответила резервная модель")
            return result["choices"][0]["message"]["content"].strip()
        
        logging.error(f"Оба провайдера отказали: {result}")
        return "ебать че то все серваки упали я спать"
    except Exception as e:
        logging.error(f"Критическая ошибка сетей: {e}")
        return "интернет лег походу пацаны"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    global CHATS_ACTIVITY
    chat_id = message.chat.id
    if chat_id in CHATS_ACTIVITY:
        CHATS_ACTIVITY[chat_id]["context"] = []
    await message.reply("память чиста")

@dp.message()
async def handle_chat(message: types.Message):
    global CHATS_ACTIVITY, LAST_REPLY_TIME
    chat_id = message.chat.id
    
    if message.chat.type not in ["group", "supergroup"] or (message.from_user and message.from_user.is_bot):
        return
    if not message.text:
        return

    if chat_id not in CHATS_ACTIVITY:
        CHATS_ACTIVITY[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    CHATS_ACTIVITY[chat_id]["last_message_time"] = datetime.now()
    
    user = message.from_user.first_name if message.from_user else "Кто-то"
    CHATS_ACTIVITY[chat_id]["context"].append(f"{user}: {message.text}")
    
    if len(CHATS_ACTIVITY[chat_id]["context"]) > 5:
        CHATS_ACTIVITY[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    bot_username = f"@{bot_info.username}"
    
    is_mentioned = bot_username.lower() in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        current_time = time.time()
        last_time = LAST_REPLY_TIME.get(chat_id, 0)
        
        if current_time - last_time < 4.0:
            return  

        LAST_REPLY_TIME[chat_id] = current_time
        chat_history = "\n".join(CHATS_ACTIVITY[chat_id]["context"])
        prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь на последнее сообщение."
        
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        joke = get_ai_joke(prompt)
        
        delay = max(1.5, min(4.0, len(joke) / 25))
        await asyncio.sleep(delay)
        
        try:
            await message.reply(joke)
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

async def silence_checker():
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        for chat_id, data in list(CHATS_ACTIVITY.items()):
            if now - data["last_message_time"] > timedelta(seconds=SILENCE_TIMEOUT):
                chat_history = "\n".join(data["context"])
                prompt = f"В чате тишина. Последнее обсуждение:\n{chat_history}\n\nНапиши один короткий провокационный вброс."
                joke = get_ai_joke(prompt)
                try:
                    await bot.send_message(chat_id, joke)
                    CHATS_ACTIVITY[chat_id]["last_message_time"] = datetime.now()
                except Exception as e:
                    logging.error(f"Ошибка чекера тишины: {e}")

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(silence_checker())
    loop.run_until_complete(dp.start_polling(bot, handle_signals=False))

if "bot_thread" not in st.session_state:
    st.session_state.bot_thread = True
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()
    logging.info("Фоновый поток гибридного ИИ-бота успешно запущен.")
