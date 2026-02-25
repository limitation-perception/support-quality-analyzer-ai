FROM python:3.11-slim

WORKDIR /app

COPY . .

# створюємо output директорію всередині контейнера
RUN mkdir -p /app/output

# запуск пайплайна
CMD ["sh", "-c", "python generate.py && python test.py"]