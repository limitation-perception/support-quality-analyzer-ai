import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. НАЛАШТУВАННЯ ТА ЗАВАНТАЖЕННЯ КЛЮЧІВ
current_dir = Path(__file__).parent.absolute()
load_dotenv(current_dir.parent / '.env')

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("Не знайдено API_KEY у файлі .env")

client = genai.Client(api_key=api_key)

# Правила для штрафів з твого test.py
RULES = {
    'ignored_question': -2,
    'incorrect_info': -2,
    'no_resolution': -2,
    'template_responses': -1,
    'failed_to_help': -1
}


# --- ЕТАП 1: АНАЛІЗ ЧЕРЕЗ LLM ---
def analyze_with_llm(dataset):
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
            Ти — суворий QA-інженер. Проаналізуй діалоги та поверни JSON-масив.

            ДІАЛОГИ: {full_text_to_analyze}

            ВАЖЛИВО: У полі 'agent_mistakes' використовуй ТІЛЬКИ ці назви (якщо помилка є):
            - "ignored_question"
            - "incorrect_info" 
            - "no_resolution"
            - "template_responses"
            - "failed_to_help"

            Особливо зверни увагу на CASE_ID: CS009 та CS004. 
            У CS009, якщо проблема з кнопкою не вирішена (агент просто дав відписку) — ОБОВ'ЯЗКОВО додай "no_resolution".
            У CS004, якщо агент був грубим або не допоміг — додай "failed_to_help".

            ФОРМАТ: [{{ "case_id": "...", "analysis": {{ "intent": "...", "satisfaction": "...", "quality_score": 5, "agent_mistakes": [] }} }}]
        """

    try:
        # ВИПРАВЛЕНО: Використовуємо існуючу модель 2.0-flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"❌ Помилка API: {e}")
        return []


# --- ЕТАП 2: ВАЛІДАЦІЯ ТА ШТРАФИ (Твій test.py) ---
def recompute_metrics(case_data):
    analysis = case_data.get("analysis", {})
    mistakes = analysis.get("agent_mistakes", [])

    # Розрахунок штрафу
    penalty = sum(RULES.get(m, 0) for m in mistakes)
    llm_score = analysis.get("quality_score", 3)

    # Фінальний скор (базові 5 мінус штрафи)
    final_score = max(1, min(5, 5 + penalty))

    # Корекція задоволеності
    final_sat = analysis.get("satisfaction", "neutral")
    if final_score <= 2:
        final_sat = "unsatisfied"
    elif final_score >= 4:
        final_sat = "satisfied"

    return {
        "case_id": case_data.get("case_id"),
        "intent": analysis.get("intent"),
        "llm_score": llm_score,
        "final_score": final_score,
        "final_satisfaction": final_sat,
        "mistakes": mistakes
    }


# --- ГОЛОВНИЙ ПРОЦЕС ---
def main(input_filename='support_dataset.json'):
    input_path = current_dir / input_filename
    output_dir = current_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # 1. Читаємо вхідні дані
    if not input_path.exists():
        print(f"❌ Файл {input_filename} не знайдено!")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    # 2. Отримуємо аналіз від ШІ
    print(f"🧠 Запуск аналізу через Gemini для {len(dataset)} кейсів...")
    raw_results = analyze_with_llm(dataset)

    if not raw_results:
        print("❌ Аналіз не вдався.")
        return

    # 3. Обробляємо кожен кейс правилами з test.py
    print("⚖️ Застосування бізнес-правил та розрахунок штрафів...")
    final_reports = []
    for item in raw_results:
        final_data = recompute_metrics(item)
        final_reports.append(final_data)

        # Зберігаємо індивідуальні JSON в output
        with open(output_dir / f"{final_data['case_id']}.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)

    # 4. Зберігаємо загальний звіт
    with open(current_dir / "final_results.json", "w", encoding="utf-8") as f:
        json.dump(final_reports, f, ensure_ascii=False, indent=4)

    print(f"✅ Готово! Результати збережено в 'output' та 'final_results.json'")


if __name__ == "__main__":
    main()