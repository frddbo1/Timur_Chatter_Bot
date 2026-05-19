import asyncio
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from google import genai
from google.genai import types as ai_types

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = "8455818639:AAHFlCH-KKecRl2XMx2s_tovmg4D9NmPUMY"
GEMINI_API_KEY = "AIzaSyBa1nih3FeaTjDiPKc7ES5KvuKhKC519AU"

# Системная роль для ИИ — здесь настраивается его характер
SYSTEM_PROMPT = (
    "Ты — участник локального дружеского чата в Telegram, мастер постиронии, сарказма и рофлов. "
    "Твоя цель — высмеивать глупость, подкалывать участников чата, использовать современный сленг "
    "(кринж, база, чилл, рофл, скуф, альтушка и т.д.). Пиши коротко, как обычный человек в мессенджере "
    "со смартфона — без заглавных букв (почти всегда), без занудства, смайликами не злоупотребляй. "
    "Не будь вежливым помощником. Если тебя троллят — тролль в ответ еще жестче."
)

CHANCE_TO_REPLY = 0.70  # Шанс ответа на обычное сообщение (15%)
SILENCE_TIMEOUT = 5000  # Время в секундах (3 часа), после которого бот пишет сам
# ================================================

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Хранилище для отслеживания активности в чатах
# { chat_id: {"last_message_time": datetime, "context": [строки сообщений]} }
chats_activity = {}

def get_ai_joke(prompt: str) -> str:
    """Запрос к Gemini для генерации рофла"""
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash', # Быстрая и отлично подходящая для текста модель
            contents=prompt,
            config=ai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=1.0, # Выше температура — безумнее и смешнее ответы
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "у меня чет мозг поплыл, подожди"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("салам. добавь меня в группу, выруби privacy mode в BotFather и я устрою там суету.")

@dp.message()
async def handle_chat(message: types.Message):
    global chats_activity
    chat_id = message.chat.id
    
    # Игнорируем личные сообщения, работаем только в группах
    if message.chat.type not in ["group", "supergroup"]:
        return

    # Обновляем время последнего сообщения в этом чате
    if chat_id not in chats_activity:
        chats_activity[chat_id] = {"last_message_time": datetime.now(), "context": []}
    
    chats_activity[chat_id]["last_message_time"] = datetime.now()
    
    # Сохраняем историю (последние 5 сообщений для контекста)
    user = message.from_user.first_name if message.from_user else "Кто-то"
    chats_activity[chat_id]["context"].append(f"{user}: {message.text}")
    if len(chats_activity[chat_id]["context"]) > 5:
        chats_activity[chat_id]["context"].pop(0)

    bot_info = await bot.get_me()
    bot_username = f"@{bot_info.username}"
    
    # Проверяем условия для ответа
    is_mentioned = bot_username in (message.text or "")
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    random_strike = random.random() < CHANCE_TO_REPLY

    if is_mentioned or is_reply_to_bot or random_strike:
        # Собираем контекст для ИИ
        chat_history = "\n".join(chats_activity[chat_id]["context"])
        prompt = f"Вот последние сообщения в чате:\n{chat_history}\n\nОтветь на последнее сообщение или прокомментируй ситуацию смешным рофлом."
        
        # Показываем, что бот «печатает» для реализма
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(random.uniform(1, 3)) # Небольшая пауза для вида
        
        joke = get_ai_joke(prompt)
        await message.reply(joke)

async def silence_checker():
    """Фоновая задача: проверяет, не приуныл ли чат"""
    while True:
        await asyncio.sleep(60) # Проверка каждую минуту
        now = datetime.now()
        
        for chat_id, data in list(chats_activity.items()):
            # Если в чате тишина дольше заданного лимита
            if now - data["last_message_time"] > timedelta(seconds=SILENCE_TIMEOUT):
                chat_history = "\n".join(data["context"])
                prompt = (
                    f"В чате уже долго никто ничего не писал. Последнее, о чем говорили:\n{chat_history}\n\n"
                    "Напиши вброс, дерзкую мысль или смешной вопрос, чтобы спровоцировать людей возобновить общение."
                )
                
                joke = get_ai_joke(prompt)
                try:
                    await bot.send_message(chat_id, joke)
                    # Обнуляем таймер, чтобы он не спамил каждую минуту
                    chats_activity[chat_id]["last_message_time"] = datetime.now()
                except Exception as e:
                    print(f"Не удалось отправить сообщение в чат {chat_id}: {e}")

async def main():
    # Запускаем проверку тишины в фоновом режиме
    asyncio.create_task(silence_checker())
    # Запускаем чтение сообщений Telegram
    await dp.start_polling(bot)

if __name__ == '__main__':
    print("Бот успешно запущен и ищет рофлы...")
    asyncio.run(main())
