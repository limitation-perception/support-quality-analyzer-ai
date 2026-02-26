FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir python-dotenv google-genai

COPY . .

# створюємо output директорію всередині контейнера
RUN mkdir -p /app/output

# запуск пайплайна
CMD ["sh", "-c", "python generate.py && python analyze.py"]
