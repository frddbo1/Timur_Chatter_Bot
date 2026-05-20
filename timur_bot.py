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

# СЮДА ВСТАВЬ СВОЙ РАБОЧИЙ КЛЮЧ OPENROUTER
OPENROUTER_API_KEY = "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"

PRIMARY_MODEL = "llama-3.1-70b-versatile" 
FALLBACK_MODEL = "meta-llama/llama-3.1-8b-instruct:free" 

# Новый уникальный маркер для блокировки старых потоков
CURRENT_VERSION = "v8_logging_stable"

SYSTEM_PROMPT = (
    "Ты — 14-летний парень по имени Тимур, сидишь в lokalnom групповом чате в Telegram. "
    "Твоя цель — общаться как реальный подросток в интернете: иронично, дерзко, местами toxic, но смешно. "
    "Не неси однообразный несвязный бред. Реагируй именно на то, что пишут люди, подкалывай их по контексту. "
    "Если тебя троллят или оскорбляют — жестко отвечай взаимностью, используй маты и интернет-сленг. "
    "ПРАВИЛА ОФОРМЛЕНИЯ: пиши исключительно маленькими буквами, коротко (до 20 слов), "
    "никогда не ставь точки в конце сообщений, запятые, знаки восклицания или вопроса. "
    "Никакого вежливого тона нейросети, ты обычный чел из чата."
)

CHANCE_TO_REPLY = 0.30  
SILENCE_TIMEOUT = 3000
# ================================================

if "CHATS_ACTIVITY" not in globals():
    CHATS_ACTIVITY = {}
if "LAST_REPLY_TIME" not in globals():
    LAST_REPLY_TIME = {}
globals()["GLOBAL_VERSION"] = CURRENT_VERSION

st.title("🤖 Панель управления Тимуром [V8 Stable]")
st.subheader("Статус: Мониторинг сети активен")
st.write(f"Текущая активная версия в памяти: **{globals()['GLOBAL_VERSION']}**")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ИСКЛЮЧИТЕЛЬНО ЖИВЫЕ ОДНОСТРОЧНИКИ ДЛЯ МАСКИРОВКИ
LOCAL_REPLIES = [
    "че ты высрал вообще я нихуя не понял",
    "ебать ты умный конечно завали ебало пж",
    "ахахаха че за бред",
    "мне похуй ладно",
    "ты че доебался до меня че надо",
    "ясно автор дебил",
    "ебать ты выдал конечно",
    "че за хуйню я щас прочитал",
    "ладно забей",
    "поясни за базар че ты несешь вообще",
    "да иди ты нахуй со своими историями",
    "ммм понятно",
    "че за кринж нахуй"
]

def get_ai_joke(prompt: str) -> str:
    """Запрос к ИИ с подробным логированием ошибок в консоль Streamlit"""
    
    # 1. ПРОБУЕМ GROQ
    url_groq = "https://api.groq.com/openai/v1/chat/completions"
    headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload_groq = {
        "model": PRIMARY_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 150
    }
    try:
        logging.info("--> [Groq] Пробую достучаться...")
        response = requests.post(url_groq, headers=headers_groq, json=payload_groq, timeout=8)
        result = response.json()
        if "choices" in result:
            logging.info("--> [Groq УСПЕХ] Ответила Llama 70B")
            return result["choices"][0]["message"]["content"].strip()
        else:
            logging.warning(f"--> [Groq ОТКАЗ] Код: {response.status_code}, Ответ: {result}")
    except Exception as e:
        logging.error(f"--> [Groq ОШИБКА СЕТИ]: {e}")

    # 2. ЕСЛИ GROQ СДОХ — ИДЕМ В OPENROUTER
    url_or = "https://openrouter.ai/api/v1/chat/completions"
    headers_or = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload_or = {
        "model": FALLBACK_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 150
    }
    try:
        logging.info("--> [OpenRouter] Groq недоступен, пробую резерв...")
        response = requests.post(url_or, headers=headers_or, json=payload_or, timeout=8)
        result = response.json()
        if "choices" in result:
            logging.info("--> [OpenRouter УСПЕХ] Ответил резерв через OpenRouter")
            return result["choices"][0]["message"]["content"].strip()
        else:
            logging.warning(f"--> [OpenRouter ОТКАЗ] Код: {response.status_code}, Ответ: {result}")
    except Exception as e:
        logging.error(f"--> [OpenRouter ОШИБКА СЕТИ]: {e}")

    # 3. ЕСЛИ ВСЁ ПЛОХО — ВЫДАЕМ МАСКИРОВКУ
    logging.error("🚨 [ТОТАЛЬНЫЙ КРАХ] Все нейросети лежат! Выдаю фразу из списка LOCAL_REPLIES.")
    return random.choice(LOCAL_REPLIES)

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
    
    # СТОП-КРАН ДЛЯ СТАРЫХ ПОТОКОВ
    if globals().get("GLOBAL_VERSION") != CURRENT_VERSION:
        return

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
    while globals().get("GLOBAL_VERSION") == CURRENT_VERSION:
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

globals()["GLOBAL_VERSION"] = CURRENT_VERSION

if "bot_thread_v8" not in st.session_state:
    st.session_state.bot_thread_v8 = True
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()
    logging.info(f"--> [Запуск] Поток {CURRENT_VERSION} успешно поднят.")
