import subprocess
import sys
import time
from pathlib import Path

# Визначаємо шлях до папки, де лежить цей скрипт
current_dir = Path(__file__).parent.absolute()


def run_script(script_name):
    # Формуємо повний шлях до скрипта
    script_path = current_dir / script_name
    print(f"\n--- Запуск {script_name} ---")

    try:
        # Запускаємо скрипт і чекаємо на його завершення
        subprocess.run([sys.executable, str(script_path)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка при виконанні {script_name}: {e}")
        return False


def main():
    # 1. Генерація датасету (створює support_dataset.json)
    if not run_script("generate.py"):
        print("🛑 Зупинка: Помилка на етапі генерації.")
        return

    # 2. Пауза для запису файлу та відновлення квот API
    # Оскільки ліміти RPD у тебе критичні (24/20), 45 секунд — безпечніший варіант
    print("⏳ Очікування 45 секунд для стабілізації лімітів API...")
    time.sleep(45)

    # 3. Аналіз та Тестування (Об'єднаний скрипт)
    # Тепер він сам робить і запит до Gemini, і розрахунок штрафів
    if not run_script("analyze.py"):
        print("🛑 Зупинка: Помилка на етапі аналізу та валідації.")
        return

    print("\n✅ УСІ ЕТАПИ ЗАВЕРШЕНО УСПІШНО!")
    print(f"📁 Результати перевірено та збережено в папці: {current_dir / 'output'}")


if __name__ == "__main__":
    main()