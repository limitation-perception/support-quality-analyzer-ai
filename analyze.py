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

    # --------------------------
    # 🔥 ADD BATCHING HERE (ONLY CHANGE)
    # --------------------------
    BATCH_SIZE = 18000  # safe token-friendly chunk size

    def split_text(text, size):
        return [text[i:i + size] for i in range(0, len(text), size)]

    chunks = split_text(full_text_to_analyze, BATCH_SIZE)

    combined_results = []

    def process_chunk(chunk):
        prompt = f"""
            You are a Merciless QA Auditor and Data Privacy Expert. 
            Your goal is to expose failures and ensure PII (Personally Identifiable Information) protection.
            Analyze the dialogues and return EXCLUSIVELY a JSON array.

            DIALOGUES FOR ANALYSIS:
            {chunk}

            1. DATA PRIVACY & ANONYMIZATION (CRITICAL):
               - If you detect real names, phone numbers, emails, or physical addresses in the chat, 
                 you MUST mask them in the "intent" or "analysis" fields using tags like [NAME], [PHONE], [EMAIL].
               - Do not include raw private data in the final JSON output.

            2. CRITICAL AUDIT PROTOCOL:
               - "intent": Map to exactly one: "payment_issues", "technical_errors", "access_to_account", "tariff_questions", "refunds", "other".
               - "satisfaction": Choose ONLY: "satisfied", "neutral", "unsatisfied".
               - THE "UNSATISFIED" TRIGGER: If "no_resolution", "incorrect_info", or "failed_to_help" is present, you MUST set "unsatisfied".
               - HIDDEN DISSATISFACTION: If the problem is not resolved but the client says "thanks", use "unsatisfied".

                A) DEFINE WHEN "no_resolution" IS ALLOWED
                - You may set agent_mistakes "no_resolution" ONLY if the user's request is ACTIONABLE within support scope AND should reasonably be solvable or progressed with concrete next steps in-chat.
                - ACTIONABLE includes: account access recovery steps, payment/refund handling, technical troubleshooting with diagnostics/workaround, tariff changes, order/shipping/delivery issues.
                - NON-ACTIONABLE includes: feature requests, product roadmap questions, requests for future ETAs/launch dates, general product suggestions, "will you add X?" questions.

                B) SPECIAL RULE: FEATURE REQUEST / ROADMAP / ETA QUESTIONS
                If the user asks about future functionality or "when will X be added":
                - Consider the request "resolved" if the agent:
                  1) acknowledges the request,
                  2) confirms it will be recorded/forwarded (or explains how feedback is tracked),
                  3) sets expectation boundaries (e.g., cannot share timelines / no ETA).
                - In this scenario:
                  - agent_mistakes MUST be [] (unless the agent is rude, ignores the question, or gives incorrect/conflicting info),
                  - satisfaction MUST be "neutral" (NOT "unsatisfied"),
                  - quality_score should be 3-5 depending on clarity and helpfulness.

                C) WHEN FEATURE/ROADMAP BECOMES "unsatisfied"
                For feature/roadmap/ETA cases, set satisfaction = "unsatisfied" ONLY if at least one of these is true:
                - agent_mistakes includes "ignored_question" OR "rude_tone" OR "incorrect_info".
                - The agent refuses to help AND provides no alternative (e.g., where to track updates / release notes / feedback channel).
                IMPORTANT: DO NOT use "no_resolution" for feature/roadmap/ETA by itself.

                D) GOLDEN EXAMPLE (MUST MATCH)
                User: "Чи планується додати функцію групових чатів? Якщо так, то коли?"
                Agent: "Дякуємо за пропозицію, передали команді розробки. Точні терміни не розголошуємо."
                => intent: "other"
                => agent_mistakes: []
                => satisfaction: "neutral"
                => quality_score: 4

            3. SCORING & MISTAKES:
               - "quality_score": 1-5. If 'agent_mistakes' is NOT empty, score MUST be ≤ 3.
               - "agent_mistakes": Use ONLY: "ignored_question", "incorrect_info", "rude_tone", "no_resolution", 
               "unnecessary_escalation".
            HIGHEST PRIORITY RULE (INVARIANT): If agent_mistakes contains no_resolution OR incorrect_info OR failed_to_help, then satisfaction MUST be unsatisfied (always, regardless of client gratitude/tone).
            PROCESS: First decide agent_mistakes, then set satisfaction using the invariant; only if invariant doesn't trigger, choose neutral/satisfied.
            VALIDATION: Before output, assert: if no_resolution or incorrect_info present => satisfaction == unsatisfied. If not, fix.

            OUTPUT FORMAT:
            - Return ONLY raw JSON code. No markdown, no preamble.
            - Be hyper-critical. If in doubt, choose the LOWER score.
            - explain for every case why you evaluated all the cases this way
            ABSOLUTE PRIORITY RULESET (ORDERED OVERRIDES):

            OVERRIDE #1 (HIGHEST): FORCED_SATISFIED
            Set satisfaction = "satisfied" even if agent_mistakes is non-empty ONLY IF the dialogue contains a clear, final confirmation of full resolution AND explicit satisfaction.
            Allowed evidence must include BOTH:
              (1) Resolution-confirmation: client explicitly confirms the issue is resolved (e.g., "все працює", "проблему вирішено", "гроші повернули", "швидкість відновилась", "доступ відновлено", "заміну оформили і мене влаштовує").
              (2) Satisfaction-confirmation: client explicitly expresses satisfaction with the outcome (strong positive, not just politeness).
            Reject as insufficient: generic "дякую", "ок", "зрозуміло", "гарного дня", "сподіваюсь" without explicit resolution.

            OVERRIDE #2: UNSATISFIED_TRIGGER
            If OVERRIDE #1 did NOT trigger AND agent_mistakes contains ANY of ["no_resolution","incorrect_info","failed_to_help"],
            THEN satisfaction MUST be "unsatisfied" (regardless of thanks/tone).

            Otherwise:
            - If resolved but satisfaction is not explicit => "neutral"
            - If unresolved => "unsatisfied"

            PROCESS (MANDATORY ORDER):
            1) Determine agent_mistakes (allowed list only).
            2) Determine satisfaction using OVERRIDE #1 then OVERRIDE #2.
            3) quality_score rule stays: if agent_mistakes non-empty => quality_score ≤ 3.

            VALIDATION (MUST RUN):
            For every case:
            - If OVERRIDE #1 triggered => satisfaction must be "satisfied".
            - Else if mistakes contain unsatisfied triggers => satisfaction must be "unsatisfied".
            - Fix and re-validate before output.

            FORMAT: [
              {{
                "case_id": "...",
                "analysis": {{
                  "intent": "...",
                  "satisfaction": "...",
                  "quality_score": 0,
                  "agent_mistakes": []
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

    # Run all chunks in parallel
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
    # --------------------------
    # END OF BATCHING CHANGE
    # --------------------------


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
        "evaluation_status": valid
    }


def rotate_existing_file(path: Path) -> None:
    if not path.exists():
        return

    parent = path.parent
    stem = path.stem
    suffix = path.suffix

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
    main(rotate=False)
