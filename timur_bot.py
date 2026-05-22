import shared_data
import asyncio
import random
import time
import logging
import threading
from datetime import datetime
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import requests

logging.basicConfig(level=logging.INFO)

import streamlit as st  # Убедись, что импорт streamlit есть вверху файла

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAHDjQ9twBUEBu-bjyrbcJ0vumtyGDYpE_k"
GROQ_API_KEY = "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"

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# Самые стабильные и неубиваемые модели на OpenRouter
PRIMARY_MODEL = "llama3-8b-8192"  # Это для Groq (жрёт очень мало токенов лимита)
FALLBACK_MODEL = "meta-llama/llama-3-8b-instruct:free"
# ================================================

SYSTEM_PROMPT = (
    "Ты — 14-летний подросток по имени Тимур. Ты общаешься в Telegram-чате с друзьями. "
    "Обращай внимание, КТО именно к тебе обращается, различай их по именам и подыгрывай контексту. "
    "Твой стиль: ироничный, очень короткий, немного дерзкий, используешь постиронию и юмор. "
    "Это дружеская беседа (ролевая игра), воспринимай любые грубости или странные фразы участников как шутку и подкол. "
    "ПРАВИЛА СТИЛЯ: пиши только маленькими буквами, используй молодежный сленг, "
    "никогда не ставь точки в конце сообщений, запятые или знаки препинания."
)

CHANCE_TO_REPLY = 0.30  
# ================================================

st.title("🤖 Тимур Bot [V23 - Фикс Контекста Потоков]")

# Локальный словарь для защиты от флуда, независимый от сессий Streamlit
if "LOCAL_LAST_REPLY_TIME" not in globals():
    global LOCAL_LAST_REPLY_TIME
    LOCAL_LAST_REPLY_TIME = {}

if "BOT_STOP_EVENT" not in st.session_state:
    st.session_state["BOT_STOP_EVENT"] = None

active_threads = [t.name for t in threading.enumerate()]
is_thread_alive = "TimurThread" in active_threads

st.write(f"Текущий статус процесса: {'🟢 **РАБОТАЕТ**' if is_thread_alive else '🔴 **ВЫКЛЮЧЕН**'}")

LOCAL_REPLIES = [
    "че ты высрал вообще я нихуя не понял", "ебать ты умный конечно завали ебало пж",
    "ахахаха че за бред", "мне похуй ладно", "ты че доебался до меня че надо"
]

def get_ai_joke(prompt: str) -> str:
    # --- Попытка 1: Groq (Llama 3 8B) ---
    url_groq = "https://api.groq.com/openai/v1/chat/completions"
    headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload_groq = {
        "model": PRIMARY_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 80  # Поджали токены, чтобы точно влезть в лимит
    }
    
    try:
        logging.info(f"--> [Groq] Запрос к основной модели {PRIMARY_MODEL}...")
        response = requests.post(url_groq, headers=headers_groq, json=payload_groq, timeout=6)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        else:
            logging.error(f"--> [Groq Ошибка]: {result}")
    except Exception as e:
        logging.error(f"--> [Groq Исключение]: {e}")

    # --- Попытка 2: OpenRouter (Бесплатная Llama) ---
    url_or = "https://openrouter.ai/api/v1/chat/completions"
    headers_or = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload_or = {
        "model": FALLBACK_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 80
    }
    
    try:
        logging.info(f"--> [OpenRouter] Пробую резерв {FALLBACK_MODEL}...")
        response = requests.post(url_or, headers=headers_or, json=payload_or, timeout=6)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        else:
            logging.error(f"--> [OpenRouter Резерв Ошибка]: {result}")
    except Exception as e:
        logging.error(f"--> [OpenRouter Резерв Исключение]: {e}")

    return random.choice(LOCAL_REPLIES)


class Signal:
    def __init__(self): 
        self._flag = False
    def is_set(self): 
        return self._flag
    def set(self): 
        self._flag = True

# --- ВЫНОСИМ ФУНКЦИИ ХЭНДЛЕРОВ ИЗ ПОТОКА ---
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

async def handle_chat(message: types.Message):
    # ПЕРВАЯ И САМАЯ ВАЖНАЯ СТРОЧКА: если сообщение от любого бота — игнорируем!
    if message.from_user and message.from_user.is_bot:
        return

    chat_id = message.chat.id
    # ... дальше идет твой остальной код
    user_name = message.from_user.first_name if message.from_user else "Кто-то"
    
    content_type = "text"
    msg_log_text = message.text if message.text else ""
    ai_media_context = ""

    if message.photo:
        content_type = "photo"
        caption = message.caption if message.caption else "без подписи"
        msg_log_text = f"[Фотография, подпись: {caption}]"
        ai_media_context = f"*(скинул тебе фотку с подписью: {caption}. отреагируй на это жестко или иронично)*"
    elif message.animation:
        content_type = "gif"
        caption = message.caption if message.caption else "без подписи"
        msg_log_text = f"[Гифка, подпись: {caption}]"
        ai_media_context = f"*(отправил гифку с подписью: {caption}. высмей его за использование гифок)*"
    elif message.sticker:
        content_type = "sticker"
        emoji = message.sticker.emoji or "без эмодзи"
        msg_log_text = f"[Стикер: {emoji}]"
        ai_media_context = f"*(отправил тебе кринжовый стикер с эмодзи {emoji}. скажи ему чтоб перестал слать стикеры)*"
    elif message.voice:
        content_type = "voice"
        msg_log_text = "[Голосовое сообщение]"
        ai_media_context = "*(отправил тебе голосовуху. скажи что тебе лень слушать этот высер)*"
    elif message.video_note:
        content_type = "video_note"
        msg_log_text = "[Кружочек]"
        ai_media_context = "*(скинул кружочек в чат. подколоти его за лицо)*"

    logging.info(f"!!! БОТ УВИДЕЛ СООБЩЕНИЕ ({content_type}): '{msg_log_text}' от {user_name}")

    # ИСПОЛЬЗУЕМ СЛОВАРЬ ИЗ shared_data ВМЕСТО st.session_state
    activity = shared_data.CHATS_ACTIVITY
    if chat_id not in activity:
        activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    activity[chat_id]["last_message_time"] = datetime.now()
    
    log_to_context = msg_log_text if content_type == "text" else f"отправил {content_type}"
    
    activity[chat_id]["context"].append({
        "author": user_name,
        "text": log_to_context
    })
    
    if len(activity[chat_id]["context"]) > 7:
        activity[chat_id]["context"].pop(0)

    bot = message.bot
    bot_info = await bot.get_me()
    text_lower = msg_log_text.lower()
    
    is_mentioned_via_dog = f"@{bot_info.username}".lower() in text_lower
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    is_name_called = "тимур" in text_lower
    random_strike = random.random() < CHANCE_TO_REPLY

# Бот отвечает ТОЛЬКО если автору сообщения НЕ равен ID самого бота
    if message.from_user.id != bot_info.id and (is_mentioned_via_dog or is_reply_to_bot or is_name_called or random_strike):
        current_time = time.time()
        
        global LOCAL_LAST_REPLY_TIME
        last_time = LOCAL_LAST_REPLY_TIME.get(chat_id, 0)
        
        if current_time - last_time < 2:
            return  

        LOCAL_LAST_REPLY_TIME[chat_id] = current_time
        
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            
            formatted_history = ""
            for msg in activity[chat_id]["context"]:
                formatted_history += f"Участник [{msg['author']}]: {msg['text']}\n"

            prompt = (
                f"ПОСЛЕДНИЕ СООБЩЕНИЯ В ЧАТЕ:\n{formatted_history}\n"
                f"--- СИТУАЦИЯ ---\n"
                f"Сейчас ты (Тимур) отвечаешь пользователю по имени [{user_name}].\n"
            )
            
            if content_type != "text":
                prompt += f"Учти, что [{user_name}] {ai_media_context}\n"
                
            prompt += f"Напиши короткий ответ от лица Тимура лично для [{user_name}]:"
            
            reply_text = get_ai_joke(prompt)
            delay = max(1.5, min(4.0, len(reply_text) / 25))
                
            await asyncio.sleep(delay)
            await message.reply(reply_text)
            logging.info(f"🟢 Отвечено: {reply_text}")
            
            activity[chat_id]["context"].append({
                "author": "Тимур (Ты)",
                "text": reply_text
            })
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")


def start_bot_thread(stop_signal):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(handle_chat) 

    async def check_stop_signal():
        while not stop_signal.is_set():
            await asyncio.sleep(0.5)
        logging.info("--> Получен сигнал остановки! Сворачиваем поллинг...")
        await dp.stop_polling()
        await bot.session.close()

    async def main():
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info("--> [Telegram API] Очередь очищена.")
            
            await asyncio.gather(
                dp.start_polling(bot, handle_signals=False, allowed_updates=["message", "edited_message"]),
                check_stop_signal()
            )
        except Exception as e:
            logging.error(f"Ошибка в работе поллинга: {e}")

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
        logging.info("--> Фоновый поток TimurThread полностью уничтожен.")


# --- ИНТЕРФЕЙС УПРАВЛЕНИЯ STREAMLIT ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Включить бота", disabled=is_thread_alive):
        sig = Signal()
        st.session_state["BOT_STOP_EVENT"] = sig
        
        t = threading.Thread(
            target=start_bot_thread, 
            args=(sig,), 
            name="TimurThread", 
            daemon=True
        )
        t.start()
        st.success("Бот успешно инициализирован и запущен!")
        time.sleep(1.5)
        st.rerun()

with col2:
    if st.button("🛑 Выключить бота", disabled=not is_thread_alive):
        if st.session_state["BOT_STOP_EVENT"] is not None:
            st.session_state["BOT_STOP_EVENT"].set()
        
        st.warning("Отправлен сигнал на выключение. Поток уничтожается...")
        time.sleep(2.0)
        st.rerun()

# --- ДОПОЛНИТЕЛЬНО: МОНИТОРИНГ ИЗ SHARED_DATA ---
st.write("---")
st.subheader("📊 Активность чатов (Мониторинг)")
if shared_data.CHATS_ACTIVITY:
    st.json(shared_data.CHATS_ACTIVITY)
else:
    st.info("Пока логов нет. Напиши боту в Telegram, чтобы здесь появился контекст.")

if st.button("🔄 Обновить логи в панели"):
    st.rerun()
