import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed

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
needed_fields = {"id", "intent", "satisfaction", "quality_score", "agent_mistakes"}


def analyze_with_llm(dataset):
    def cleanup(text: str):
        if not text:
            return None

        t = text.strip()
        if len(t) < 4:
            return None

        return t

    lines = []
    for entry in dataset:
        case_id = entry["metadata"]["case_id"]
        lines.append(f"=== CASE_ID: {case_id} ===")
        for msg in entry["chat_transcript"]:
            role = "Клієнт" if msg.get("role") == "client" else "Агент"
            cleaned = cleanup(msg.get("text"))
            if cleaned:
                lines.append(f"{role}: {cleaned}")
        lines.append("")

    full_text = "\n".join(lines)
    case_blocks = full_text.split("=== CASE_ID: ")

    chunks = []
    current_chunk = ""
    MAX_CASES_PER_CHUNK = 10

    count = 0
    for block in case_blocks:
        if not block.strip():
            continue

        formatted_block = "=== CASE_ID: " + block
        current_chunk += formatted_block
        count += 1

        if count >= MAX_CASES_PER_CHUNK:
            chunks.append(current_chunk)
            current_chunk = ""
            count = 0

    if current_chunk:
        chunks.append(current_chunk)

    combined_results = []

    def process_chunk(chunk):
        prompt = f"""
    You are a Merciless QA Auditor. Your goal is to expose failures. 
    Analyze the dialogues and return EXCLUSIVELY a JSON array.

    DIALOGUES FOR ANALYSIS:
    {chunk}

    1. DATA PRIVACY & ANONYMIZATION:
       - Mask real names, phones, emails using [NAME], [PHONE], [EMAIL].

    2. ABSOLUTE SATISFACTION BLOCKER (PRIORITY #0):
       - If the agent denies a request (e.g., "no pause", "no refund", "can't help") and the client explicitly mentions "inconvenience", "uncomfortable", "not good", or "unhappy" (like in Case 19: "Це не дуже зручно"):
       - You are STRICTLY FORBIDDEN from using "satisfied".
       - You MUST use "unsatisfied" (if they are annoyed) or "neutral" (if they are just informed).
       - Polite closing words like "Дякую за відповідь" DO NOT override this blocker.

    3. CRITICAL AUDIT PROTOCOL:
       - "intent": Map to: "payment_issues", "technical_errors", "access_to_account", "tariff_questions", "refunds", "other".
       - "satisfaction": Choose ONLY: "satisfied", "neutral", "unsatisfied".
       - THE "UNSATISFIED" TRIGGER: If "no_resolution", "incorrect_info", or "failed_to_help" is present, you MUST set "unsatisfied".
       - HIDDEN DISSATISFACTION: If the problem is not resolved but the client says "thanks", use "unsatisfied".

        A) DEFINE WHEN "no_resolution" IS ALLOWED
        - Use "no_resolution" ONLY for actionable requests (billing, tech, access) that were not solved.
        - For feature requests/roadmap: use [] for mistakes but "neutral" for satisfaction.

    4. SCORING & MISTAKES:
       - "quality_score": 1-5. If 'agent_mistakes' is NOT empty, score MUST be ≤ 3.
       - "agent_mistakes": ONLY: "ignored_question", "incorrect_info", "rude_tone", "no_resolution", "unnecessary_escalation".

    OVERRIDE #1 (HIGHEST): FORCED_SATISFIED
    ONLY if: (1) Full resolution confirmed by client AND (2) Explicit joy/gratitude for the RESULT.
    CRITICAL: Case 19 is NOT satisfied. The client is paying for nothing during vacation. That is a fail for satisfaction.

    VALIDATION:
    If Case includes "не зручно" or "доведеться платити заново" => satisfaction != satisfied.

    FORMAT: [
      {{
        "case_id": "...",
        "analysis": {{
          "intent": "...",
          "satisfaction": "...",
          "quality_score": 0,
          "agent_mistakes": [],
          "explanation": "..."
        }}
      }}
    ]
    """

        try:
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

    chunk_results: list[list] = [[] for _ in chunks]
    with ThreadPoolExecutor(max_workers=min(len(chunks), 8)) as executor:
        future_to_index = {executor.submit(process_chunk, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            result = future.result() or []
            chunk_results[index] = result
            print(f"✅ Chunk {index + 1}/{len(chunks)} завершено ({len(result)} кейсів)")

    for result in chunk_results:
        if result:
            combined_results.extend(result)

    return combined_results


def recompute_metrics(case_data):
    actual_fields = {"id" if k == "case_id" else k for k in case_data.keys()}
    actual_fields.update(case_data.get('analysis', {}).keys())
    missing = needed_fields - actual_fields
    if len(missing) == 0:
        valid = "ok"
    else:
        valid = "was fixed"

    analysis = case_data.get("analysis", {})
    mistakes = analysis.get("agent_mistakes", [])

    penalty = sum(rules.get(m, 0) for m in mistakes)
    llm_score = analysis.get("quality_score", 3)
    final_score = max(1, min(5, 5 + penalty))

    llm_sat = analysis.get("satisfaction", "neutral")

    if final_score <= 2:
        final_sat = "unsatisfied"
    elif llm_sat == "satisfied" and final_score < 4:
        final_sat = "neutral"
    else:
        final_sat = llm_sat

    return {
        "case_id": case_data.get("case_id"),
        "intent": analysis.get("intent"),
        "llm_score": llm_score,
        "final_score": final_score,
        "final_satisfaction": final_sat,
        "mistakes": mistakes,
        "evaluation_status": valid
    }


def rotate_existing_file(path: Path) -> None:
    if not path.exists():
        return
    parent, stem, suffix = path.parent, path.stem, path.suffix
    n = 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            path.rename(candidate)
            print(f"🗂️  Existing file rotated: {path.name} -> {candidate.name}")
            return
        n += 1


def main(input_filename='support_dataset.json', rotate=False):
    input_path = current_dir / input_filename
    output_dir = current_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"❌ Файл {input_filename} не знайдено!")
        return

    # identify filetype
    if input_path.suffix == '.json':
        with open(input_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    else:
        # for .txt files we create the structure for AI
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
            dataset = [{
                "metadata": {"case_id": "TXT_IMPORT_001"},
                "chat_transcript": [{"role": "client", "text": content}]
            }]

    print(f"🧠 Запуск аналізу через Gemini...")
    raw_results = analyze_with_llm(dataset)

    if not raw_results:
        print("❌ Аналіз не вдався.")
        return

    print("⚖️ Застосування бізнес-правил та розрахунок штрафів...")
    final_reports = []
    for item in raw_results:
        final_data = recompute_metrics(item)
        final_reports.append(final_data)

        case_path = output_dir / f"{final_data['case_id']}.json"
        if rotate:
            rotate_existing_file(case_path)
        with open(case_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)

    final_path = current_dir / "final_results.json"
    if rotate:
        rotate_existing_file(final_path)
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(final_reports, f, ensure_ascii=False, indent=4)

    print("✅ Готово! Результати збережено в 'output' та 'final_results.json'")


if __name__ == "__main__":
    # to test TXT, you can just change the name of the file
    main(input_filename='support_dataset.json', rotate=False)