FROM python:3.11-slim

WORKDIR /app 
RUN pip install --no-cache-dir python-dotenv google-genai
COPY . . 
RUN mkdir -p /app/output 
CMD ["python", "run_all.py"]