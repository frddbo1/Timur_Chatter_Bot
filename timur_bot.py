import streamlit as st
import subprocess
import psutil
import time
import os
import sys

st.title("🤖 Тимур Bot [V21 - Управление Процессами]")

# Функция проверки: запущен ли наш бот-воркер как отдельный процесс ОС
def get_bot_process():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and "bot_worker.py" in "".join(cmd):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

bot_proc = get_bot_process()
is_running = bot_proc is not None

st.write(f"Текущий статус процесса: {'🟢 **РАБОТАЕТ как PID ' + str(bot_proc.pid) + '**' if is_running else '🔴 **ВЫКЛЮЧЕН**'}")

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Включить бота", disabled=is_running):
        # Запускаем bot_worker.py независимо от Streamlit
        # Используем тот же интерпретатор python, что запустил streamlit
        script_path = os.path.join(os.path.dirname(__file__), "bot_worker.py")
        
        subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True # Запуск в изолированной сессии ОС
        )
        st.success("Команда на запуск отправлена операционной системе!")
        time.sleep(2.0)
        st.rerun()

with col2:
    if st.button("🛑 Выключить бота", disabled=not is_running):
        if bot_proc:
            # Жесткое и гарантированное убийство процесса на уровне ОС
            bot_proc.terminate()
            bot_proc.wait() # Ждем завершения
        st.warning("Процесс бота уничтожен.")
        time.sleep(1.5)
        st.rerun()
