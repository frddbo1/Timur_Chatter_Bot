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

# Включаем детальные логи в консоль Streamlit, чтобы видеть каждое действие бота
logging.basicConfig(level=logging.INFO)

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"

# Две модели для автоматического переключения (Защита от Rate Limit)
PRIMARY_MODEL = "llama-3.1-70b-versatile" # Основная (умная)
FALLBACK_MODEL = "llama-3.1-8b-instant"     # Запасная (быстрая и безотказная)

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

# ГЛОБАЛЬНЫЕ СЛОВАРИ (Хранятся на уровне процесса, защищены от перезагрузок интерфейса Streamlit)
if "CHATS_ACTIVITY" not in globals():
    CHATS_ACTIVITY = {}
if "LAST_REPLY_TIME" not in globals():
    LAST_REPLY_TIME = {}

# Отрисовка веб-панели управления Streamlit
st.title("🤖 Панель управления Тимуром [70B + 8B Гибрид]")
st.subheader("Статус: Активен (Фоновый поток Python 3.14)")
st.write(f"Основная модель ИИ: **Meta Llama 3.1 70B**")
st.write(f"Резервная модель ИИ: **Meta Llama 3.1 8B**")
st.write("Если бот замолчал, попробуй тегнуть его напрямую: `@Timur_Chatter_bot`")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

def get_ai_joke(prompt: str) -> str:
    """Запрос к Groq API с автоматическим переключением на резервную модель"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. Попытка отправить запрос в умную Llama 3.1 70B
    payload_70b = {
        "model": PRIMARY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.2,
        "max_tokens": 150
    }
    
    try:
        logging.info("--> Отправка запроса к основной модели 70B...")
        response = requests.post(url, headers=headers, json=payload_70b, timeout=10)
        result = response.json()
        
        if "choices" in result:
            logging.info("--> [Успех] Ответ получен от модели 70B")
            return result["choices"][0]["message"]["content"].strip()
            
        logging.warning(f"--> [70B Ограничение] Превышен лимит или ошибка. Переключаюсь на 8B... Код ответа: {result}")
        
    except Exception as e:
        logging.error(f"--> [70B Ошибка сети]: {e}. Пробую резервный вариант...")

    # 2. РЕЗЕРВНЫЙ ВАРИАНТ: Быстрая отправка в безотказную Llama 3.1 8B
    payload_8b = {
        "model": FALLBACK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.2,
        "max_tokens": 150
    }
    
    try:
        logging.info("--> Отправка запроса к резервной модели 8B...")
        response = requests.post(url, headers=headers, json=payload_8b, timeout=10)
        result = response.json()
        
        if "choices" in result:
            logging.info("--> [Успех] Ответ получен от резервной модели 8B")
            return result["choices"][0]["message"]["content"].strip()
        
        logging.error(f"Отказывали обе модели Groq: {result}")
        return "ебать че то сервак лег окончательно походу я сломался"
    except Exception as e:
        logging.error(f"Критический сбой сети на обеих моделях: {e}")
        return "интернет пропал на сервере ахахах"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    global CHATS_ACTIVITY
    chat_id = message.chat.id
    if chat_id in CHATS_ACTIVITY:
        CHATS_ACTIVITY[chat_id]["context"] = []
    await message.reply("ебать вы мне стерли память нахуй пидарасы аыааааа я умираю ааа , . . . .     привет) ")

@dp.message()
async def handle_chat(message: types.Message):
    global CHATS_ACTIVITY, LAST_REPLY_TIME
    chat_id = message.chat.id
    
    # Игнорируем личные сообщения (работаем только в группах) и сообщения от других ботов
    if message.chat.type not in ["group", "supergroup"] or (message.from_user and message.from_user.is_bot):
        return
    if not message.text:
        return

    # Инициализация и сохранение контекста сообщений в чате
    if chat_id not in CHATS_ACTIVITY:
        CHATS_ACTIVITY[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    CHATS_ACTIVITY[chat_id]["last_message_time"] = datetime.now()
    
    user = message.from_user.first_name if message.from_user else "Кто-то"
    CHATS_ACTIVITY[chat_id]["context"].append(f"{user}: {message.text}")
    
    # Держим в памяти только последние 5 реплик, чтобы контекст не раздувался
    if len(CHATS_ACTIVITY[chat_id]["context"]) > 5:
        CHATS_ACTIVITY[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    bot_username = f"@{bot_info.username}"
    
    # Проверка условий для ответа
    is_mentioned = bot_username.lower() in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        current_time = time.time()
        last_time = LAST_REPLY_TIME.get(chat_id, 0)
        
        # Кулдаун 4 секунды между сообщениями в одном чате
        if current_time - last_time < 4.0:
            logging.info(f"--> Сработал кулдаун. Пропуск хода в чате {chat_id}")
            return  

        LAST_REPLY_TIME[chat_id] = current_time
        chat_history = "\n".join(CHATS_ACTIVITY[chat_id]["context"])
        prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь на последнее сообщение."
        
        logging.info(f"--> Инициация генерации ответа для чата {chat_id}")
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        joke = get_ai_joke(prompt)
        
        # Реалистичная задержка перед отправкой (имитация печатания текста)
        delay = max(1.5, min(4.0, len(joke) / 25))
        await asyncio.sleep(delay)
        
        try:
            await message.reply(joke)
            logging.info(f"--> Сообщение успешно отправлено в чат {chat_id}!")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")

async def silence_checker():
    """Фоновый таймер тишины"""
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
    """Инициализация изолированного Event Loop для асинхронного движка в потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(silence_checker())
    # Отключаем обработку сигналов ОС, чтобы не конфликтовать со Streamlit Cloud
    loop.run_until_complete(dp.start_polling(bot, handle_signals=False))

# Запуск фонового процесса строго один раз при первом запуске приложения
if "bot_thread" not in st.session_state:
    st.session_state.bot_thread = True
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()
    logging.info("Фоновый поток гибридного ИИ-бота успешно запущен.")
