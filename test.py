import json
import random

def generate(i):
    result = {}
    result['id'] = i
    intents = ['проблеми з оплатою', 'технічні помилки', 'доступ до акаунту', 'питання по тарифу', 'повернення коштів', 'other']
    satisfactions = ['satisfied', 'neutral', 'unsatisfied']
    agent_mistakes = ['ignored_question', 'incorrect_info', 'rude_tone', 'no_resolution', 'unnecessary_escalation']
    result['intent'] = random.choice(intents)
    result['satisfaction'] = random.choice(satisfactions)
    result['quality_score'] = random.randint(1,5)
    k = random.randint(0, 3)
    result['agent_mistakes'] = [random.choice(agent_mistakes) for n in range(k)]
    print(result)
    file_name = f"{i}.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)  

needed_fields = {"id", "intent", "satisfaction",  "quality_score", "agent_mistakes"}
rules = {'ignored_question': -2, 'incorrect_info': -2, 'no_resolution': -2,'rude_tone': -1, 'unnecessary_escalation': -1}


def validate_schema(data):
    missing = needed_fields - data.keys()
    if len(missing) == 0:
        return "ok"
    else:
        return "was fixed"

def sanitize(data, i):
    if "quality_score"  not in data:
        data["quality_score"] = 3  
    if "intent" not in data:
        data["intent"] = "other"
    if "id" not in data:
        data["id"] = i
    if "satisfaction" not in data:
        data["satisfaction"] = "neutral"
    if "agent_mistakes" not in data:
        data["agent_mistakes"] = []
    return data

def calculate_penalty(mistakes):
    return sum(rules.get(m, 0) for m in mistakes)

def recompute_score(penalty):
    score = 5 + penalty
    return max(1, min(5, score))

def normalize_satisfaction(score,satified):
    if score == 1 :
        return   "unsatisfied"
    elif score == 2 and satified == "satisfied":
        return "unsatisfied"
    elif score == 3 and satified != "neutral":
        return "neutral"
    elif score == 4 and satified == "unsatisfied":
        return  "satisfied"
    else:
        return  "satisfied"
       
def build_output(data, valid, score, satisfaction):
    return {
        "id": data["id"],
        "intent": data["intent"],
        "llm_quality_score": data.get("quality_score"),
        "quality_score": score,
        "satisfaction": satisfaction,
        "agent_mistakes": data["agent_mistakes"],
        "evaluation_status":  valid 
    }

def evaluate_record(data, i):
    valid = validate_schema(data)
    data = sanitize(data, i)
    penalty = calculate_penalty(data["agent_mistakes"])
    score = recompute_score(penalty)
    satisfaction = normalize_satisfaction(score, data["satisfaction"])
    return build_output(data, valid, score, satisfaction)

def result_check(i):
    with open(f'{i}.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    resul = evaluate_record(data, i)
    file_name = f"{i}.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(resul, f, indent=4)  

n = 4
for i in range(1,n+1):
    generate(i,"message")
    result_check(i)


