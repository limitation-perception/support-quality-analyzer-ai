import subprocess
import sys
import time


def run_script(script_name):
    print(f"\n--- Запуск {script_name} ---")
    try:
        # Запускаємо скрипт і чекаємо на його завершення
        result = subprocess.run([sys.executable, script_name], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка при виконанні {script_name}: {e}")
        return False


def main():
    # 1. Генерація датасету
    if not run_script("generate.py"):
        return

    # 2. Аналіз через ШІ (тут ми робимо паузу, щоб не зловити ліміти)
    print("⏳ Очікування 30 секунд для відновлення лімітів API...")
    time.sleep(30)

    if not run_script("analyze.py"):
        return

    # 3. Валідація та фінальна оцінка (твій новий test.py)
    if not run_script("test.py"):
        return

    print("\n✅ УСІ ЕТАПИ ЗАВЕРШЕНО УСПІШНО!")
    print("Результати в папці 'output' та файл 'analyzed_results.json' готові.")


if __name__ == "__main__":
    main()
