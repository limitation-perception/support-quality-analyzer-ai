import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from prompts import get_analyze_prompt

current_dir = Path(__file__).parent.absolute()
load_dotenv(current_dir / ".env")

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("Не знайдено API_KEY у файлі .env")

client = genai.Client(api_key=api_key)

rules = {
    "ignored_question": -2,
    "incorrect_info": -2,
    "rude_tone": -1,
    "no_resolution": -3,
    "unnecessary_escalation": -1,
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
    max_cases_per_chunk = 10

    count = 0
    for block in case_blocks:
        if not block.strip():
            continue

        formatted_block = "=== CASE_ID: " + block
        current_chunk += formatted_block
        count += 1

        if count >= max_cases_per_chunk:
            chunks.append(current_chunk)
            current_chunk = ""
            count = 0

    if current_chunk:
        chunks.append(current_chunk)

    combined_results = []

    def process_chunk(chunk):
        prompt = get_analyze_prompt(chunk)

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
            print(f"❌ Помилка API: {e}")
            return []

    chunk_results: list[list] = [[] for _ in chunks]
    with ThreadPoolExecutor(max_workers=min(len(chunks), 8)) as executor:
        future_to_index = {
            executor.submit(process_chunk, chunk): i for i, chunk in enumerate(chunks)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            result = future.result() or []
            chunk_results[index] = result
            print(
                f"✅ Chunk {index + 1}/{len(chunks)} завершено ({len(result)} кейсів)"
            )

    for result in chunk_results:
        if result:
            combined_results.extend(result)

    return combined_results


def recompute_metrics(case_data):
    actual_fields = {"id" if k == "case_id" else k for k in case_data.keys()}
    actual_fields.update(case_data.get("analysis", {}).keys())
    missing = needed_fields - actual_fields
    if missing:
        valid = "was fixed"
    else:
        valid = "ok"

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
        "evaluation_status": valid,
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


def main(input_filename="support_dataset.json", rotate=False):
    input_path = current_dir / input_filename
    output_dir = current_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"❌ Файл {input_filename} не знайдено!")
        return

    # identify filetype
    if input_path.suffix == ".json":
        with open(input_path, encoding="utf-8") as f:
            dataset = json.load(f)
    else:
        # for .txt files we create the structure for AI
        with open(input_path, encoding="utf-8") as f:
            content = f.read()
            dataset = [
                {
                    "metadata": {"case_id": "TXT_IMPORT_001"},
                    "chat_transcript": [{"role": "client", "text": content}],
                }
            ]

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
    main(input_filename="support_dataset.json", rotate=False)
