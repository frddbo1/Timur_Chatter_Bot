# Файл: bot_worker.py
import asyncio
import random
import time
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import requests

logging.basicConfig(level=logging.INFO)

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
CHATS_ACTIVITY = {}
LAST_REPLY_TIME = {}

LOCAL_REPLIES = ["че ты высрал вообще я нихуя не понял", "ебать ты умный конечно завали ебало пж", "ахахаха че за бред"]

def get_ai_joke(prompt: str) -> str:
    url_groq = "https://api.groq.com/openai/v1/chat/completions"
    headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload_groq = {
        "model": PRIMARY_MODEL, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 100
    }
    try:
        response = requests.post(url_groq, headers=headers_groq, json=payload_groq, timeout=8)
        result = response.json()
        if "choices" in result: return result["choices"][0]["message"]["content"].strip()
    except Exception: pass

    url_or = "https://openrouter.ai/api/v1/chat/completions"
    headers_or = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload_or = {
        "model": FALLBACK_MODEL, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 1.2, "max_tokens": 100
    }
    try:
        response = requests.post(url_or, headers=headers_or, json=payload_or, timeout=8)
        result = response.json()
        if "choices" in result: return result["choices"][0]["message"]["content"].strip()
    except Exception: pass
    return random.choice(LOCAL_REPLIES)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("ебать короче я роботаю")

@dp.message(F.any())
async def handle_chat(message: types.Message):
    if message.from_user and message.from_user.is_bot: return
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

    if content_type == "text" and not message.text: return

    if chat_id not in CHATS_ACTIVITY:
        CHATS_ACTIVITY[chat_id] = {"context": []}
    
    log_to_context = msg_log_text if content_type == "text" else f"отправил {content_type}"
    CHATS_ACTIVITY[chat_id]["context"].append(f"{user_name}: {log_to_context}")
    if len(CHATS_ACTIVITY[chat_id]["context"]) > 5: CHATS_ACTIVITY[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    text_lower = msg_log_text.lower()
    
    is_mentioned = f"@{bot_info.username}".lower() in text_lower
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    is_name = "тимур" in text_lower
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply or is_name or random_strike:
        current_time = time.time()
        if current_time - LAST_REPLY_TIME.get(chat_id, 0) < 2: return
        LAST_REPLY_TIME[chat_id] = current_time
        
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            chat_history = "\n".join(CHATS_ACTIVITY[chat_id]["context"])
            if content_type != "text":
                prompt = f"Контекст беседы:\n{chat_history}\n\nВажное условие: {user_name} {ai_media_context}\nОтветь от лица Тимура:"
            else:
                prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь."
            
            reply_text = get_ai_joke(prompt)
            await asyncio.sleep(max(1.5, min(4.0, len(reply_text) / 25)))
            await message.reply(reply_text)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

async def main():
    # drop_pending_updates=True — это самое важное! 
    # Он принудительно закроет все старые сессии в Telegram
    await bot.delete_webhook(drop_pending_updates=True) 
    print("--> Поллинг запущен успешно!")
    await dp.start_polling(bot, allowed_updates=["message"], drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
