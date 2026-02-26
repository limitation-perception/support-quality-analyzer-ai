import subprocess
import sys
import time
from pathlib import Path

current_dir = Path(__file__).parent.absolute()


def run_script(script_name):
    script_path = current_dir / script_name
    print(f"\n--- Запуск {script_name} ---")

    try:

        subprocess.run([sys.executable, str(script_path)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка при виконанні {script_name}: {e}")
        return False


def main():
    if not run_script("generate.py"):
        print("🛑 Зупинка: Помилка на етапі генерації.")
        return

    print("⏳ Очікування 30 секунд для стабілізації лімітів API...")
    time.sleep(30)

    if not run_script("analyze.py"):
        print("🛑 Зупинка: Помилка на етапі аналізу та валідації.")
        return

    print("\n✅ УСІ ЕТАПИ ЗАВЕРШЕНО УСПІШНО!")
    print(f"📁 Результати перевірено та збережено в папці: {current_dir / 'output'}")


if __name__ == "__main__":
    main()
