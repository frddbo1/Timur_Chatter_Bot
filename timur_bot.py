import asyncio
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import requests

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAHFlCH-KKecRl2XMx2s_tovmg4D9NmPUMY"
HF_API_KEY = "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" # Пример: hf_...

SYSTEM_PROMPT = (
    "Ты — участник локального дружеского чата в Telegram, мастер постиронии, сарказма и рофлов. "
    "Твоя цель — высмеивать глупость, подкалывать участников чата, использовать современный сленг "
    "(кринж, база, чилл, рофл, скуф, альтушка и т.д.). Пиши коротко, как обычный человек в мессенджере "
    "со смартфона — без заглавных букв (почти всегда), без занудства, смайликами не злоупотребляй. "
    "Не будь вежливым помощником. Если тебя троллят — тролль в ответ еще жестче."
)

CHANCE_TO_REPLY = 0.15
SILENCE_TIMEOUT = 10800
# ================================================

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
chats_activity = {}

def get_ai_joke(prompt: str) -> str:
    """Запрос к бесплатным моделям Hugging Face (Llama 3)"""
    # Используем мощную открытую модель Llama-3-8B-Instruct
    API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    
    # Формируем правильный запрос для текстовой модели
    full_prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{prompt}\n<|assistant|>\n"
    
    payload = {
        "inputs": full_prompt,
        "parameters": {
            "max_new_tokens": 100,
            "temperature": 0.9,
            "return_full_text": False
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
        result = response.json()
        
        # Если модель отвечает списком
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', '').strip()
        # Если модель выдает ошибку, что она загружается (такое бывает при первом запросе)
        elif isinstance(result, dict) and "estimated_time" in result:
            return "ща, погоди, мысль формулирую..."
        else:
            print(f"Неожиданный ответ API: {result}")
            return "не понял че ты высрал, давай заново"
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "у меня чето сервак поплыл, помянем"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("салам. добавь меня в группу, выруби privacy mode в BotFather и я устрою там суету.")

@dp.message()
async def handle_chat(message: types.Message):
    global chats_activity
    chat_id = message.chat.id
    
    if message.chat.type not in ["group", "supergroup"]:
        return

    if chat_id not in chats_activity:
        chats_activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    chats_activity[chat_id]["last_message_time"] = datetime.now()
    
    user = message.from_user.first_name if message.from_user else "Кто-то"
    chats_activity[chat_id]["context"].append(f"{user}: {message.text}")
    if len(chats_activity[chat_id]["context"]) > 5:
        chats_activity[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    bot_username = f"@{bot_info.username}"
    
    is_mentioned = bot_username in (message.text or "")
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        chat_history = "\n".join(chats_activity[chat_id]["context"])
        prompt = f"Контекст беседы:\n{chat_history}\n\nОтветь на последнее сообщение коротким рофлом."
        
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(random.uniform(1, 2))
        
        joke = get_ai_joke(prompt)
        await message.reply(joke)

async def silence_checker():
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        
        for chat_id, data in list(chats_activity.items()):
            if now - data["last_message_time"] > timedelta(seconds=SILENCE_TIMEOUT):
                chat_history = "\n".join(data["context"])
                prompt = f"В чате тишина. Последнее обсуждение:\n{chat_history}\n\nНапиши один короткий провокационный вброс."
                
                joke = get_ai_joke(prompt)
                try:
                    await bot.send_message(chat_id, joke)
                    chats_activity[chat_id]["last_message_time"] = datetime.now()
                except Exception as e:
                    print(f"Ошибка отправки: {e}")

async def main():
    asyncio.create_task(silence_checker())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
