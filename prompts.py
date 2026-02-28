import json

def get_generation_prompt(test_cases):
    return f"""
    Ти — досвідчений сценарист та експерт зі створення реалістичних датасетів для машинного навчання.
    Твоє завдання — згенерувати діалоги між клієнтом (client) та сапорт-агентом (agent) українською мовою для ВСІХ наданих сценаріїв за один раз.

    ПАРАМЕТРИ СЦЕНАРІЇВ (список усіх кейсів):
    {json.dumps(test_cases, indent=2, ensure_ascii=False)}

    ЖОРСТКІ ВИМОГИ:
    1. Діалог має бути максимально природним. Люди в чатах використовують короткі репліки, іноді роблять одруківки або використовують сленг.
    2. Ідеально виконуй 'agent_specific_instructions' та 'client_specific_instructions' для відповідного кейсу. 
    3. Якщо вказана "прихована незадоволеність", клієнт має завершити діалог формальною подякою, незважаючи на те, що його проблема НЕ вирішена.
    4. Кількість реплік у кожному діалозі не повинна перевищувати параметр 'max_turns' конкретного кейсу.
    5. Для кожного кейсу перша репліка клієнта має базуватися на 'initial_client_prompt'.
    
    ФОРМАТ ВИВОДУ:
    Поверни ВИКЛЮЧНО валідний JSON у такому форматі (це має бути масив об'єктів для кожного кейсу, без markdown-розмітки):
    [
      {{
        "case_id": "CS001",
        "chat_transcript": [
          {{"role": "client", "text": "перша репліка клієнта"}},
          {{"role": "agent", "text": "відповідь агента"}},
          {{"role": "client", "text": "наступна репліка"}}
        ]
      }},
      {{
        "case_id": "CS002",
        "chat_transcript": [ ... ]
      }}
      // ... і так для кожного case_id з вхідних даних
    ]
    """

def get_analyze_prompt(chunk):
    return f"""
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
