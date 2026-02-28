import json


def get_generation_prompt(test_cases):
    return f"""
    You are an experienced screenwriter and an expert in creating realistic datasets for machine learning.
    Your task is to generate dialogues between a client and a support agent in Ukrainian for ALL provided scenarios at once.

    SCENARIO PARAMETERS (list of all cases):
    {json.dumps(test_cases, indent=2, ensure_ascii=False)}

    STRICT REQUIREMENTS:
    1. The dialogue must be as natural as possible. People in chats use short replicas, sometimes make typos, or use slang.
    2. Perfectly follow 'agent_specific_instructions' and 'client_specific_instructions' for the respective case.
    3. If "hidden dissatisfaction" is specified, the client must end the dialogue with a formal thank you, despite the fact that their problem is NOT resolved.
    4. The number of replicas in each dialogue should not exceed the 'max_turns' parameter of the specific case.
    5. For each case, the client's first replica should be based on 'initial_client_prompt'.

    OUTPUT FORMAT:
    Return EXCLUSIVELY a valid JSON in the following format (it must be an array of objects for each case, without markdown formatting):
    [
      {{
        "case_id": "CS001",
        "chat_transcript": [
          {{"role": "client", "text": "client's first replica"}},
          {{"role": "agent", "text": "agent's response"}},
          {{"role": "client", "text": "next replica"}}
        ]
      }},
      {{
        "case_id": "CS002",
        "chat_transcript": [ ... ]
      }}
      // ... and so on for each case_id from the input data
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
