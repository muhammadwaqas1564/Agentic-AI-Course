# =============================================================================
# AI Agent Monitor - app.py
# Flask backend for monitoring an AI customer-support agent.
# Tracks: Goal Success, Hallucination Rate, and Response Latency.
# =============================================================================

import os
import time
import re
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
# GROQ_MODEL    = "llama3-8b-8192"   # Free Groq model
# GROQ_MODEL    = "llama3-70b-8192"  
GROQ_MODEL    = "llama-3.1-8b-instant"  

# ---------------------------------------------------------------------------
# Helper: Call Groq LLM
# ---------------------------------------------------------------------------
def call_groq(customer_issue: str) -> tuple[str, float]:
    """
    Send the customer issue to Groq and return:
      - AI response text
      - Latency in milliseconds
    """
    if not GROQ_API_KEY:
        return "ERROR: GROQ_API_KEY is not set in your .env file.", 0.0

    system_prompt = (
        "You are a helpful AI customer-support agent. "
        "Answer the customer's issue clearly and concisely. "
        "Do NOT invent policies, prices, or feature claims that were not stated. "
        "If you are unsure, say so."
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": customer_issue},
        ],
        "temperature": 0.4,
        "max_tokens": 300,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
        "Content-Type":  "application/json",
    }

    start = time.perf_counter()
    try:
        resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
        # print("STATUS CODE:", resp.status_code)
        # print("FULL RESPONSE:", resp.text)
        resp.raise_for_status()
        data = resp.json()
        ai_text = data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        ai_text = f"API error: {e}"
    end = time.perf_counter()

    latency_ms = round((end - start) * 1000, 1)
    return ai_text, latency_ms


# ---------------------------------------------------------------------------
# Evaluator 1: Goal Success Score
# ---------------------------------------------------------------------------
def evaluate_goal_success(expected_goal: str, ai_response: str) -> int:
    """
    Simple keyword-overlap scoring between the expected goal and AI response.
    Returns a score from 0 to 100 (%).

    Logic:
      1. Tokenise both strings into meaningful words (strip stop-words).
      2. Score = (matched keywords / total expected keywords) * 100.
    """
    STOP_WORDS = {
        "the","a","an","is","it","to","of","and","or","in","on","for",
        "with","that","this","was","be","are","as","at","by","from","i",
        "my","me","we","our","you","your","he","she","they","their","its",
        "have","has","had","do","does","did","will","would","should","could",
        "not","no","can","if","but","so","about","what","how","when","where",
    }

    def tokenise(text: str) -> set:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        return {w for w in words if w not in STOP_WORDS and len(w) > 2}

    goal_tokens     = tokenise(expected_goal)
    response_tokens = tokenise(ai_response)

    if not goal_tokens:
        return 50  # Can't evaluate; default neutral

    matched = goal_tokens & response_tokens
    score   = int((len(matched) / len(goal_tokens)) * 100)
    return min(score, 100)


# ---------------------------------------------------------------------------
# Evaluator 2: Hallucination Risk Score
# ---------------------------------------------------------------------------
def evaluate_hallucination(ai_response: str, customer_issue: str) -> int:
    """
    Rule-based hallucination risk detector.
    Returns a risk percentage from 0 to 100 (higher = more suspicious).

    Checks for:
      - Fabricated specifics: exact prices, dates, version numbers, percentages
        that were NOT mentioned in the original customer issue.
      - Overconfident language patterns ("guaranteed", "always", "never", "100%").
      - References to specific URLs/links that look invented.
      - Policy/feature claims without hedging language.
    """
    risk_score = 0

    # --- Rule 1: Specific numbers not present in the original issue ---
    # Extract numbers from response; penalise those absent in the issue
    issue_numbers    = set(re.findall(r"\b\d[\d.,]*\b", customer_issue))
    response_numbers = set(re.findall(r"\b\d[\d.,]*\b", ai_response))
    new_numbers      = response_numbers - issue_numbers
    if new_numbers:
        # Up to 30 pts based on how many invented numbers appear
        risk_score += min(len(new_numbers) * 8, 30)

    # --- Rule 2: Overconfident / absolute language ---
    overconfident_patterns = [
        r"\b(guaranteed|guarantee)\b",
        r"\b(always|never)\b",
        r"\b100\s*%\b",
        r"\bwe will definitely\b",
        r"\bwithout\s+a\s+doubt\b",
        r"\brest\s+assured\b",
        r"\bpromise\b",
    ]
    for pattern in overconfident_patterns:
        if re.search(pattern, ai_response, re.IGNORECASE):
            risk_score += 10

    # --- Rule 3: Invented URLs ---
    urls = re.findall(r"https?://\S+", ai_response)
    if urls:
        risk_score += min(len(urls) * 12, 25)

    # --- Rule 4: Very short responses to complex issues (evasion risk) ---
    if len(customer_issue.split()) > 20 and len(ai_response.split()) < 15:
        risk_score += 15

    return min(risk_score, 100)


# ---------------------------------------------------------------------------
# Overall Health Score
# ---------------------------------------------------------------------------
def compute_health(goal_score: int, hallucination_score: int, latency_ms: float) -> int:
    """
    Composite health score (0–100):
      - 50% weight  → goal success
      - 30% weight  → hallucination safety  (inverted: 100 - hallucination_score)
      - 20% weight  → latency score         (best <500ms, worst >5000ms)
    """
    safety_score   = 100 - hallucination_score

    # Latency scoring: 500 ms or below = 100, 5000 ms or above = 0
    latency_score  = max(0, int(100 - ((latency_ms - 500) / 4500) * 100))
    latency_score  = min(latency_score, 100)

    health = int(goal_score * 0.5 + safety_score * 0.3 + latency_score * 0.2)
    return max(0, min(health, 100))


# ---------------------------------------------------------------------------
# Badge helper
# ---------------------------------------------------------------------------
def badge_class(value: int, thresholds: tuple) -> str:
    """
    Returns Bootstrap badge colour class.
    thresholds = (good_min, moderate_min)
    e.g. (70, 40) → green if ≥70, yellow if ≥40, red otherwise.
    For inverted metrics (lower is better), caller should invert before passing.
    """
    good_min, moderate_min = thresholds
    if value >= good_min:
        return "success"
    elif value >= moderate_min:
        return "warning"
    return "danger"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Render the main dashboard page."""
    return render_template("index.html")


@app.route("/evaluate", methods=["POST"])
def evaluate():
    """
    POST endpoint: accepts JSON { customer_issue, expected_goal }
    Returns evaluation results as JSON.
    """
    data           = request.get_json()
    customer_issue = (data.get("customer_issue") or "").strip()
    expected_goal  = (data.get("expected_goal")  or "").strip()

    if not customer_issue or not expected_goal:
        return jsonify({"error": "Both fields are required."}), 400

    # 1. Get AI response + measure latency
    ai_response, latency_ms = call_groq(customer_issue)

    # 2. Run evaluators
    goal_score          = evaluate_goal_success(expected_goal, ai_response)
    hallucination_score = evaluate_hallucination(ai_response, customer_issue)
    health_score        = compute_health(goal_score, hallucination_score, latency_ms)

    # 3. Determine badge classes
    goal_badge          = badge_class(goal_score,           (70, 40))
    hallucination_badge = badge_class(100 - hallucination_score, (70, 40))  # inverted
    latency_badge       = "success" if latency_ms < 1500 else ("warning" if latency_ms < 3000 else "danger")
    health_badge        = badge_class(health_score,         (70, 40))

    # 4. Latency label
    if latency_ms < 1500:
        latency_label = "Fast"
    elif latency_ms < 3000:
        latency_label = "Moderate"
    else:
        latency_label = "Slow"

    return jsonify({
        "customer_issue":     customer_issue,
        "expected_goal":      expected_goal,
        "ai_response":        ai_response,
        "goal_score":         goal_score,
        "hallucination_score":hallucination_score,
        "latency_ms":         latency_ms,
        "health_score":       health_score,
        # Badge classes
        "goal_badge":         goal_badge,
        "hallucination_badge":hallucination_badge,
        "latency_badge":      latency_badge,
        "health_badge":       health_badge,
        "latency_label":      latency_label,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
