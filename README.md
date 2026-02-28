# Support-quality-analyzer-ai
## Project Overview:
#### This project demonstrates an end-to-end pipeline that uses an LLM (gemini-2.5-flash-lite) to:
+ Generate synthetic customer–support conversations (generate.py)
+ Analyze conversation quality using a hybrid approach (analyze.py):
1. LLM reasoning
2. Rule-based scoring 
#### The system produces structured evaluation results in JSON format for each dialogue and an aggregated report for the entire dataset.
#### The pipeline can be executed:
+ manually (step-by-step),
+ automatically via run_all.py,
+ inside Docker,
+ using Telegram-bot.
## Architecture:
+ generate.py        → generates support_dataset.json
+ analyze.py         → evaluates conversations via Gemini
+ run_all.py         → runs full pipeline locally
+ bot.py             → Telegram interface
+ output/            → per-case analysis results
+ final_results.json → aggregated report
+ prompts.py         → Centralized prompt templates for generation and analysis
+ scenarios.json     → Definitions of all test scenarios used for dataset creation
## Requirements:
+ Python 3.10+
+ Dependencies from requirements.txt
+ Google Gemini API Key
+ Telegram Bot Token (optional, only for bot mode)
+ Docker (optional)
## Environment Setup
#### Create a .env file in the project root:
+ API_KEY=your_gemini_api_key
+ TELEGRAM_TOKEN=your_telegram_token (optional)
## Installation
#### Clone repository and install dependencies:
+ python -m venv .venv
+ .\.venv\Scripts\activate        # Windows
+ pip install -r requirements.txt
## Running the Project
### Option 1 — Manual Execution
#### Generate dataset:
+ python generate.py
#### This creates:
+ support_dataset.json
#### Run analysis:
+ python analyze.py
#### Results:
+ output/CS001.json
+ output/CS002.json
+ ...
+ final_results.json
### Option 2 — Automatic Pipeline (Recommended)
+ python run_all.py
#### This script:
+ Generates dataset
+ Waits 30 seconds to avoid API rate-limits
+ Runs analysis automatically
### Option 3 — Docker Execution
#### Build container:
+ docker build -t support-qa .
#### Run container:
+ docker run --env-file .env support-qa
## Option 4 — Telegram Bot Mode
#### Run the bot locally:
+ python bot.py
#### Open thge bot in Telegram:
+ https://t.me/ChatAnalyticBot
#### Start interaction:
+ /start
#### The bot allows you to:
+ Upload your own dataset (.json) for analysis
+ Generate new conversations using /generate
+ Receive QA evaluation results directly in Telegram
+ Download the detailed JSON report
## Output Description
+ output/{case_id}.json
#### Contains analysis for each individual case:
{
  "case_id": "CS001",
  "intent": "...",
  "llm_score": 4,
  "final_score": 3,
  "final_satisfaction": "neutral",
  "mistakes": [...]
}
+ final_results.json
#### Aggregated report across all generated conversations.
#### Useful for analytics, dashboards, or QA reporting.
## Use Cases
#### This project can be used for:
+ Support agent QA automation
+ Synthetic dataset generation for ML training
+ LLM evaluation experiments
+ Prompt-driven simulation testing
+ Customer service analytics prototyping





