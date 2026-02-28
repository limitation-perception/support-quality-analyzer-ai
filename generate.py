import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from prompts import get_generation_prompt

load_dotenv()

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError(
        "Не знайдено API_KEY. Будь ласка, створіть файл .env та додайте туди ключ."
    )

client = genai.Client(api_key=api_key)


def generate_all_chats(test_cases):
    """
    Відправляє промпт до LLM для генерації ВСІХ діалогів за один запит
    на основі масиву параметрів кейсів.
    """
    prompt = get_generation_prompt(test_cases)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Помилка масової генерації: {e}")
        return []


def main():
    # Завантаження кейсів із зовнішнього файлу
    scenarios_path = "scenarios.json"
    if not os.path.exists(scenarios_path):
        print(f"❌ Файл {scenarios_path} не знайдено!")
        return

    with open(scenarios_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Починаємо генерацію датасету. Кількість кейсів: {len(test_cases)}")
    print("Відправляємо єдиний запит до API... Це може зайняти кілька десятків секунд.")

    generated_responses = generate_all_chats(test_cases)

    final_dataset = []

    for case in test_cases:
        transcript = []
        for response_data in generated_responses:
            if response_data.get("case_id") == case["case_id"]:
                transcript = response_data.get("chat_transcript", [])
                break

        if not transcript:
            print(
                f"Попередження: Не вдалося знайти згенерований діалог для {case['case_id']}"
            )

        dataset_entry = {"metadata": case, "chat_transcript": transcript}
        final_dataset.append(dataset_entry)

    output_file = "support_dataset.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_dataset, f, ensure_ascii=False, indent=2)

    print(f"\nГотово! Згенерований датасет збережено у файл {output_file}")


if __name__ == "__main__":
    main()
