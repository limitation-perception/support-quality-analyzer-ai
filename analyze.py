import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("Не знайдено API_KEY. Будь ласка, створіть файл .env у корені проєкту.")

client = genai.Client(api_key=api_key)


def generate_all_results(dataset):
    """
    Аналізує всі кейси за один запит до LLM.
    """
    full_text_to_analyze = ""
    for entry in dataset:
        case_id = entry["metadata"]["case_id"]
        chat = entry["chat_transcript"]
        full_text_to_analyze += f"=== CASE_ID: {case_id} ===\n"
        for msg in chat:
            role = "Клієнт" if msg.get("role") == "client" else "Агент"
            full_text_to_analyze += f"{role}: {msg.get('text')}\n"
        full_text_to_analyze += "\n"

    prompt = f"""
        Ти — суворий QA-інженер служби підтримки. Проаналізуй наступні діалоги та поверни JSON-масив.

        ДІАЛОГИ ДЛЯ АНАЛІЗУ:
        {full_text_to_analyze}

        КРИТЕРІЇ ОЦІНКИ (СУВОРО):
        1. intent: "проблеми з оплатою", "технічні помилки", "доступ до акаунту", "питання по тарифу", "повернення коштів" або "other".
        2. satisfaction: 
           - "satisfied": проблема вирішена повністю.
           - "neutral": інформацію надано, але активних дій не було.
           - "unsatisfied": ПРОБЛЕМА НЕ ВИРІШЕНА. 
           ВАЖЛИВО: Якщо агент просто "передав запит" без термінів або дав шаблонну пораду, яка не допомогла — це "unsatisfied", навіть якщо клієнт ввічливо каже "дякую". Ввічливість клієнта не означає задоволеність результатом.
        3. quality_score: Оцінюй від 1 до 5. Якщо проблему не вирішено через лінь або шаблонність агента — не став більше 2.
        4. agent_mistakes: ["no_resolution", "template_responses", "failed_to_help", "ignored_issue"].

        ФОРМАТ ВИВОДУ:
        Поверни ВИКЛЮЧНО валідний JSON-масив об'єктів:

    [
      {{
        "case_id": "ідентифікатор кейсу",
        "analysis": {{
          "intent": "...",
          "satisfaction": "...",
          "quality_score": 5,
          "agent_mistakes": []
        }}
      }},
      ...
    ]
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Помилка під час масового аналізу: {e}")
        return []


def reader(file, output_file='analyzed_results.json'):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"Помилка: Файл {file} не знайдено!")
        return

    print(f"Починаю аналіз усіх кейсів ({len(dataset)}) одним запитом...")

    start_time = time.time()
    analyzed_data = generate_all_results(dataset)
    end_time = time.time()

    if analyzed_data:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analyzed_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Успішно! Аналіз завершено за {round(end_time - start_time, 2)} сек.")
        print(f"Результати збережено у {output_file}")
    else:
        print("❌ Не вдалося отримати результати аналізу.")


if __name__ == "__main__":
    reader('support_dataset.json')
