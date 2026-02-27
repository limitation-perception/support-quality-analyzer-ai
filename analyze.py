import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

current_dir = Path(__file__).parent.absolute()
load_dotenv(current_dir / '.env')

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("Не знайдено API_KEY у файлі .env")

client = genai.Client(api_key=api_key)

rules = {
    'ignored_question': -2,
    'incorrect_info': -2,
    'rude_tone': -1,
    'no_resolution': -3,
    'unnecessary_escalation': -1
}
needed_fields = {"id", "intent", "satisfaction",  "quality_score", "agent_mistakes"}


def analyze_with_llm(dataset):
    def cleanup(text: str):
        if not text:
            return None

        t = text.strip()
        if len(t) < 4:
            return None

        return t

    lines = []
    append = lines.append 

    for entry in dataset:
        case_id = entry["metadata"]["case_id"]
        append(f"=== CASE_ID: {case_id} ===")

        for msg in entry["chat_transcript"]:
            role = "Клієнт" if msg.get("role") == "client" else "Агент"

            cleaned = cleanup(msg.get("text"))
            if cleaned:
                append(f"{role}: {cleaned}")

        append("")

    full_text_to_analyze = "\n".join(lines)

    prompt = f"""
        You are a Merciless QA Auditor and Data Privacy Expert. 
        Your goal is to expose failures and ensure PII (Personally Identifiable Information) protection.
        Analyze the dialogues and return EXCLUSIVELY a JSON array.

        DIALOGUES FOR ANALYSIS:
        {full_text_to_analyze}

        1. DATA PRIVACY & ANONYMIZATION (CRITICAL):
           - If you detect real names, phone numbers, emails, or physical addresses in the chat, 
             you MUST mask them in the "intent" or "analysis" fields using tags like [NAME], [PHONE], [EMAIL].
           - Do not include raw private data in the final JSON output.

        2. CRITICAL AUDIT PROTOCOL:
           - "intent": Map to exactly one: "payment_issues", "technical_errors", "access_to_account", "tariff_questions", "refunds", "other".
           - "satisfaction": Choose ONLY: "satisfied", "neutral", "unsatisfied".
           - THE "UNSATISFIED" TRIGGER: If "no_resolution", "incorrect_info", or "failed_to_help" is present, you MUST set "unsatisfied".
           - HIDDEN DISSATISFACTION: If the problem is not resolved but the client says "thanks", use "unsatisfied".

        3. SCORING & MISTAKES:
           - "quality_score": 1-5. If 'agent_mistakes' is NOT empty, score MUST be ≤ 3.
           - "agent_mistakes": Use ONLY: "ignored_question", "incorrect_info", "rude_tone", "no_resolution", "unnecessary_escalation".

        OUTPUT FORMAT:
        - Return ONLY raw JSON code. No markdown, no preamble.
        - Be hyper-critical. If in doubt, choose the LOWER score.

        FORMAT: [
          {{
            "case_id": "...",
            "analysis": {{
              "intent": "...",
              "satisfaction": "...",
              "quality_score": 0,
              "agent_mistakes": []
            }}
          }}
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
        print(f"❌ Помилка API: {e}")
        return []


def recompute_metrics(case_data):
    actual_fields = {"id" if k == "case_id" else k for k in case_data.keys()}
    actual_fields.update(case_data.get('analysis', {}).keys())
    missing = needed_fields - actual_fields
    if len(missing) == 0:
        valid = "ok"
    else:
        valid =  "was fixed"

    analysis = case_data.get("analysis", {})
    mistakes = analysis.get("agent_mistakes", [])

    penalty = sum(rules.get(m, 0) for m in mistakes)
    llm_score = analysis.get("quality_score", 3)

    final_score = max(1, min(5, 5 + penalty))

    final_sat = analysis.get("satisfaction", "neutral")
    if final_score <= 2:
        final_sat = "unsatisfied"
    elif final_score >= 4:
        final_sat = "satisfied"
    elif final_score == 3:
        final_sat = "neutral"

    return {
        "case_id": case_data.get("case_id"),
        "intent": analysis.get("intent"),
        "llm_score": llm_score,
        "final_score": final_score,
        "final_satisfaction": final_sat,
        "mistakes": mistakes,
        "evaluation_status":  valid
    }


def main(input_filename='support_dataset.json'):
    input_path = current_dir / input_filename
    output_dir = current_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"❌ Файл {input_filename} не знайдено!")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print(f"🧠 Запуск аналізу через Gemini для {len(dataset)} кейсів...")
    raw_results = analyze_with_llm(dataset)

    if not raw_results:
        print("❌ Аналіз не вдався.")
        return

    print("⚖️ Застосування бізнес-правил та розрахунок штрафів...")

    final_reports = []
    append_result = final_reports.append

    for item in raw_results:
        final_data = recompute_metrics(item)
        append_result(final_data)

        # saving every file
        with open(output_dir / f"{final_data['case_id']}.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)     

    with open(current_dir / "final_results.json", "w", encoding="utf-8") as f:
        json.dump(final_reports, f, ensure_ascii=False, indent=4)             

    print(f"✅ Готово! Результати збережено в 'output' та 'final_results.json'")


if __name__ == "__main__":
    main()
