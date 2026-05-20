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

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAEvMCnXthyxT-UMMvzwd1WRKAa3BMqdkQ0"
GROQ_API_KEY = "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"
OPENROUTER_API_KEY = "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"

PRIMARY_MODEL = "llama-3.3-70b-versatile"        
FALLBACK_MODEL = "google/gemini-2.5-flash:free"  

SYSTEM_PROMPT = (
    "Ты — 14-летний подросток по имени Тимур. Ты сидишь в локальном групповом чате с друзьями в Telegram. У тебя аутизм."
    "Общайся как реальный парень из интернета: иронично, очень коротко, немного дерзко и с юмором. "
    "Реагируй строго на контекст беседы, подкалывай участников чата. "
    "ПРАВИЛА СТИЛЯ: пиши только маленькими буквами, используй молодежный сленг, "
    "никогда не ставь точки в конце сообщений, запятые или знаки препинания."
)

CHANCE_TO_REPLY = 0.30  
# ================================================

st.title("🤖 Тимур Bot [V19 - Фикс Медиа Хэндлера]")

if "CHATS_ACTIVITY" not in globals():
    globals()["CHATS_ACTIVITY"] = {}
if "LAST_REPLY_TIME" not in globals():
    globals()["LAST_REPLY_TIME"] = {}
if "BOT_RUNNING_STATE" not in globals():
    globals()["BOT_RUNNING_STATE"] = False

# Проверяем реальное наличие живого потока
active_threads = [t.name for t in threading.enumerate()]
is_thread_alive = "TimurThread" in active_threads

# Синхронизируем состояние
if not is_thread_alive:
    globals()["BOT_RUNNING_STATE"] = False

st.write(f"Текущий статус процесса: {'🟢 **РАБОТАЕТ**' if globals()['BOT_RUNNING_STATE'] else '🔴 **ВЫКЛЮЧЕН**'}")

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

PHOTO_REPLIES = [
    "нахуй ты своего батю кидаешь выблядь",
    "нахуй ты мне это скинул даунище",
    "нахуй ты мне это скинула дура",
    "норм photoкарточка",
    "у меня глаза горят от этой поеботни",
    "удали не позорь ся"
]

GIF_REPLIES = [
    "гифки юзаешь уебанище",
    "хвапзхвапхаз че за гифка ублюдская",
    "заканчивай гифки кидать",
    "бля не грузит че то с впном походу"
]

STICKER_REPLIES = [
    "хватит стикеры кидать уебанище кринжовое",
    "че за стикер уебанский сын коровы",
    "ахуенный стикер",
    "нахуй ты мне это кидаешь"
]

def get_ai_joke(prompt: str) -> str:
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
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"--> [Groq Ошибка]: {e}")

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
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"--> [OpenRouter Ошибка]: {e}")

    return random.choice(LOCAL_REPLIES)

# Создаем объекты глобально, чтобы к ним был доступ из разных мест
if "bot_instance" not in globals():
    globals()["bot_instance"] = Bot(token=TELEGRAM_TOKEN)
if "dp_instance" not in globals():
    globals()["dp_instance"] = Dispatcher()

bot = globals()["bot_instance"]
dp = globals()["dp_instance"]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(F.any())
async def handle_chat(message: types.Message):
    if not globals().get("BOT_RUNNING_STATE", False):
        return

    if message.from_user and message.from_user.is_bot:
        return

    chat_id = message.chat.id
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

    if content_type == "text" and not message.text:
        return

    logging.info(f"!!! БОТ УВИДЕЛ СООБЩЕНИЕ ({content_type}): '{msg_log_text}' от {user_name}")

    activity = globals()["CHATS_ACTIVITY"]
    if chat_id not in activity:
        activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    activity[chat_id]["last_message_time"] = datetime.now()
    
    log_to_context = msg_log_text if content_type == "text" else f"отправил {content_type}"
    activity[chat_id]["context"].append(f"{user_name}: {log_to_context}")
    
    if len(activity[chat_id]["context"]) > 5:
        activity[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    text_lower = msg_log_text.lower()
    
    is_mentioned_via_dog = f"@{bot_info.username}".lower() in text_lower
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    is_name_called = "тимур" in text_lower
    random_strike = random.random() < CHANCE_TO_REPLY

    logging.info(f"Проверка триггеров: тег={is_mentioned_via_dog}, реплай={is_reply_to_bot}, имя={is_name_called}, рандом={random_strike}")

    if is_mentioned_via_dog or is_reply_to_bot or is_name_called or random_strike:
        current_time = time.time()
        last_time = globals()["LAST_REPLY_TIME"].get(chat_id, 0)
        
        if current_time - last_time < 2:
            logging.info("Отмена ответа: сработал антифлуд-таймер")
            return  

        globals()["LAST_REPLY_TIME"][chat_id] = current_time
        
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Для медиа мы скармливаем ИИ контекст и инструкцию, чтобы он генерировал УНИКАЛЬНЫЙ ответ
            if content_type != "text":
                chat_history = "\n".join(activity[chat_id]["context"])
                prompt = f"Контекст беседы:\n{chat_history}\n\nВажное условие: {user_name} {ai_media_context}\nОтветь от лица Тимура:"
                reply_text = get_ai_joke(prompt)
                delay = 2.0
            else:
                chat_history = "\n".join(activity[chat_id]["context"])
                prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь."
                reply_text = get_ai_joke(prompt)
                delay = max(1.5, min(4.0, len(reply_text) / 25))
                
            await asyncio.sleep(delay)
            
            if globals().get("BOT_RUNNING_STATE", False):
                await message.reply(reply_text)
                logging.info(f"🟢 Отвечено: {reply_text}")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}")

async def run_bot_polling():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("--> [Telegram API] Очередь очищена.")
        await dp.start_polling(bot, handle_signals=False, allowed_updates=["message"])
    except Exception as e:
        logging.error(f"Сбой поллинга: {e}")
    finally:
        globals()["BOT_RUNNING_STATE"] = False

def thread_target():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot_polling())
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()

# --- ИНТЕРФЕЙС УПРАВЛЕНИЯ STREAMLIT ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Включить бота", disabled=globals()["BOT_RUNNING_STATE"]):
        if not is_thread_alive:
            globals()["BOT_RUNNING_STATE"] = True
            # Свежая инициализация сессии бота при каждом старте
            globals()["bot_instance"] = Bot(token=TELEGRAM_TOKEN)
            bot = globals()["bot_instance"]
            
            t = threading.Thread(target=thread_target, name="TimurThread", daemon=True)
            t.start()
            st.success("Бот успешно запускается... Подожди пару секунд!")
            time.sleep(2.5)
            st.rerun()

with col2:
    if st.button("🛑 Выключить бота", disabled=not globals()["BOT_RUNNING_STATE"]):
        globals()["BOT_RUNNING_STATE"] = False
        
        # ГЛАВНЫЙ ФИКС: Принудительно закрываем поллинг через остановку диспетчера и закрытие сессии бота
        async def stop_all():
            try:
                await dp.stop_polling()
                await bot.session.close()
            except Exception as e:
                logging.error(f"Ошибка при мягкой остановке бота: {e}")

        # Запускаем быструю корутину закрытия прямо из Streamlit
        try:
            asyncio.run(stop_all())
        except Exception:
            pass
            
        st.warning("Поток бота принудительно остановлен.")
        time.sleep(1.5)
        st.rerun()
