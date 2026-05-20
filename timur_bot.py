import streamlit as st
import subprocess
import time
import os
import sys

st.title("🤖 Тимур Bot [V24 - Исправление Синтаксиса]")

PID_FILE = os.path.join(os.path.dirname(__file__), "bot.pid")
LOG_FILE = os.path.join(os.path.dirname(__file__), "bot_output.log")

def is_bot_running():
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0) 
        return True
    except (OSError, ValueError):
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return False

is_running = is_bot_running()

st.write(f"Текущий статус процесса: {'🟢 **РАБОТАЕТ**' if is_running else '🔴 **ВЫКЛЮЧЕН**'}")

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Включить бота", disabled=is_running):
        script_path = os.path.join(os.path.dirname(__file__), "bot_worker.py")
        
        # Очищаем старый лог перед запуском
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            
        # Запускаем и пишем ВСЕ ошибки и выводы в файл bot_output.log
        with open(LOG_FILE, "w") as log_out:
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=log_out,
                stderr=log_out,
                start_new_session=True
            )
        
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
            
        st.success("Отправлен запрос на запуск...")
        time.sleep(2.5)
        st.rerun()

with col2:
    if st.button("🛑 Выключить бота", disabled=not is_running):
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 9)
            except Exception:
                pass
            finally:
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
                    
        st.warning("Процесс остановлен.")
        time.sleep(1.5)
        st.rerun()

# --- ОКНО ЛОГОВ ДЛЯ ТЕБЯ ---
st.subheader("📋 Логи работы бота (Что происходит внутри):")

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        log_content = f.read()
    
    if log_content.strip():
        st.code(log_content, language="text")
    else:
        st.info("Файл логов пустой. Бот запущен, но ничего не напечатал.")
else:
    st.info("Логов пока нет. Включи бота, чтобы они появились.")

# Кнопка для ручного обновления логов на экране
if st.button("🔄 Обновить логи"):
    st.rerun()
