import os
import json
import telebot
from dotenv import load_dotenv
from pathlib import Path

# Імпортуємо твої функції
from analyze import analyze_with_llm, recompute_metrics # Є проблеми з цілим файлом??????
import generate  # Імпортуємо твій файл генерації

# Завантажуємо змінні середовища
current_dir = Path(__file__).parent.absolute()
load_dotenv(current_dir / '.env')

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Не знайдено TELEGRAM_TOKEN у файлі .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- СПІЛЬНА ФУНКЦІЯ АНАЛІЗУ ---
def process_dataset(chat_id, dataset, status_msg_id):
    """Спільна логіка: приймає датасет, аналізує, рахує штрафи і відправляє звіт"""
    try:
        # 1. Отримуємо аналіз від ШІ
        raw_results = analyze_with_llm(dataset)
        if not raw_results:
            bot.edit_message_text("❌ Сталася помилка під час аналізу LLM.", chat_id=chat_id, message_id=status_msg_id)
            return
        
        # 2. Розраховуємо метрики
        final_reports = []
        response_text = "📊 **Результати аналізу:**\n\n"
        
        for item in raw_results:
            final_data = recompute_metrics(item)
            final_reports.append(final_data)
            
            case_id = final_data.get('case_id', 'Невідомо')
            score = final_data.get('final_score', 'N/A')
            mistakes = final_data.get('mistakes', [])
            mistakes_str = ", ".join(mistakes) if mistakes else "✅ Немає"
            
            response_text += f"🔹 **Кейс:** `{case_id}`\n"
            response_text += f"⭐️ **Рейтинг:** {score}/5\n"
            response_text += f"⚠️ **Проблеми:** {mistakes_str}\n"
            response_text += "➖➖➖➖➖➖➖➖\n"

        # 3. Зберігаємо фінальний звіт і відправляємо
        output_filename = "analysis_result.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(final_reports, f, ensure_ascii=False, indent=4)

        if len(response_text) > 4000:
            bot.send_message(chat_id, "⚠️ Текстовий звіт великий. Деталі у файлі.")
        else:
            bot.send_message(chat_id, response_text, parse_mode="Markdown")

        with open(output_filename, "rb") as f:
            bot.send_document(chat_id, f, caption="📁 Детальний звіт аналізу (JSON)")
            
        os.remove(output_filename)
        bot.delete_message(chat_id=chat_id, message_id=status_msg_id)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Помилка під час обробки: {e}")


# --- ОБРОБНИКИ КОМАНД ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 Привіт! Я бот-QA. У мене є дві опції:\n\n"
        "1️⃣ **Відправ мені файл** `support_dataset.json`, і я його проаналізую.\n"
        "2️⃣ **Напиши команду** /generate — я сам згенерую нові діалоги (за твоїми сценаріями) і одразу проведу їхній аналіз."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['generate'])
def handle_generate(message):
    status_msg = bot.reply_to(message, "⏳ Починаю генерацію нових діалогів... Це може зайняти близько хвилини. Будь ласка, зачекай.")
    
    try:
        # Запускаємо твою функцію main() з generate.py
        generate.main()
        
        # main() зберігає файл 'support_dataset.json', зчитуємо його
        input_file = "support_dataset.json"
        if not os.path.exists(input_file):
            bot.edit_message_text("❌ Помилка: Файл не згенерувався.", chat_id=message.chat.id, message_id=status_msg.message_id)
            return

        # Відправляємо згенерований датасет користувачу, щоб він його теж мав
        with open(input_file, "rb") as f:
            bot.send_document(message.chat.id, f, caption="📝 Ось щойно згенерований датасет. Тепер починаю його аналіз...")

        # Зчитуємо дані для аналізу
        with open(input_file, 'r', encoding='utf-8') as f:
            dataset = json.load(f)

        bot.edit_message_text("🧠 Діалоги згенеровано! Тепер аналізую їх через Gemini...", chat_id=message.chat.id, message_id=status_msg.message_id)
        
        # Запускаємо спільну логіку аналізу
        process_dataset(message.chat.id, dataset, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Помилка під час генерації: {e}", chat_id=message.chat.id, message_id=status_msg.message_id)


@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        if not message.document.file_name.endswith('.json'):
            bot.reply_to(message, "❌ Будь ласка, відправте файл у форматі .json")
            return

        status_msg = bot.reply_to(message, "⏳ Файл отримано. Починаю аналіз через Gemini...")

        # Завантажуємо файл від користувача
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        dataset = json.loads(downloaded_file.decode('utf-8'))
        
        # Запускаємо спільну логіку аналізу
        process_dataset(message.chat.id, dataset, status_msg.message_id)

    except json.JSONDecodeError:
        bot.reply_to(message, "❌ Помилка: Невірний формат JSON-файлу.")
    except Exception as e:
        bot.reply_to(message, f"❌ Сталася неочікувана помилка: {e}")


if __name__ == "__main__":
    print("🤖 Бот запущено... Очікую на файли або команду /generate")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)