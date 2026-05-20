# shared_data.py

# Сюда бот будет записывать данные, а Streamlit — читать их.
# Структура может быть любой, например: { chat_id: "Последнее сообщение" }
CHATS_ACTIVITY = {}

def update_activity(chat_id, status_text):
    """Функция для удобного обновления активности из бота"""
    CHATS_ACTIVITY[chat_id] = status_text


def get_activity():
    """Функция для получения актуальной активности в Streamlit"""
    return CHATS_ACTIVITY
