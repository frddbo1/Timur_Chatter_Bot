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

# Включаем детальные логи в консоль Streamlit
logging.basicConfig(level=logging.INFO)

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"

# ПЕРЕКЛЮЧИЛИ НА СТАРШУЮ МОДЕЛЬ 70B INSTRUCT
LLAMA_MODEL = "llama-3.1-70b-versatile"

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

st.title("🤖 Панель управления Тимуром [70B Умный режим]")
st.subheader("Статус: Активен (Фоновый поток Python 3.14)")
st.write(f"Модель ИИ: **Meta Llama 3.1 70B Instruct** (via Groq)")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

def get_ai_joke(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": LLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.2,  # Снизил с 1.5 до 1.2, чтобы шутки были более логичными и точечными, без каши
        "max_tokens": 150
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        logging.error(f"Ошибка Groq API: {result}")
        return "ебать че то я тупой не понимаю нихуя"
    except Exception as e:
        logging.error(f"Критическая ошибка сети: {e}")
        return "сервер лег ебать ахахах"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
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
        
        logging.info(f"--> Тимур 70B генерирует ответ для чата {chat_id}")
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        joke = get_ai_joke(prompt)
        
        delay = max(1.5, min(4.0, len(joke) / 25))
        await asyncio.sleep(delay)
        
        try:
            await message.reply(joke)
            logging.info(f"--> Ответ успешно отправлен!")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")

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
    logging.info("Фоновый поток Llama 3.1 70B бота успешно запущен.")
