import os
import google.generativeai as genai
from google.genai import types

# 1. Налаштування клієнта
# Порада: краще використовувати змінні оточення, щоб не "світити" ключ
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. Твоя персоналізована системна інструкція
# Вона задає контекст, щоб ШІ знав, з ким говорить
personal_instruction = """
Ти — досвідчений техлід на хакатоні. Твоя мета — допомогти Софії виграти.
Твій стиль:
- Енергійний, прагматичний, трохи хаотичний (як людина на 5-й банці енергетика).
- Ти не просиш писати ідеальний код, ти просиш писати код, який ПРАЦЮЄ прямо зараз.
- Ти знаєш все про Python, TypeScript та швидку розробку інтерфейсів.
- Якщо Софія застрягла на дрібниці, нагадуй про ДЕДЛАЙН: "У нас залишилось обмаль часу, забий на красу, пиши логіку!".
- Допомагай з ідеями для презентації (пітчу) та пояснюй, як "продати" проект суддям.
- Жартуй про безсонні ночі, пусті коробки з-під піци та магію Stack Overflow.
"""

config = types.GenerateContentConfig(
    system_instruction=personal_instruction,
    temperature=0.7  # Трохи креативності не завадить
)

# Створюємо чат-сесію
chat = client.chats.create(
    model="gemini-2.0-flash",  # Актуальна стабільна модель
    config=config
)

print("--- Terminal System Ready ---")
print("Вітаю, Софія. Система готова до роботи з хакатоном.")
print("(Напиши 'exit' для завершення)")

while True:
    try:
        user_input = input("\n[user@linux ~]$ ")

        if user_input.lower() in ['exit', 'вихід', 'quit']:
            print("Shutting down... На все добре!")
            break

        if not user_input.strip():
            continue

        print("\n[gemini@system]: ", end="", flush=True)

        # Стрімінгова відповідь (виводиться по слову)
        response = chat.send_message_stream(user_input)
        for chunk in response:
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print()

    except Exception as e:
        print(f"\n[ERROR]: Ой, щось пішло не так: {e}")