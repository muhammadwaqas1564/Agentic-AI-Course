# AI Agent Monitor

A lightweight Flask dashboard that monitors and evaluates an AI customer-support agent in real time.

Tracks three key metrics:
- **Goal Success** — did the agent actually address the customer's issue?
- **Hallucination Risk** — did the agent fabricate facts, numbers, or claims?
- **Response Latency** — how fast did the agent respond?

Powered by the **Groq API** (free tier, `llama3-8b-8192`).

---

## Quick Start

### 1. Clone / download the project

```bash
git clone https://github.com/your-username/ai-agent-monitor
cd ai-agent-monitor
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your Groq API key

```bash
cp .env.example .env
# Open .env and paste your key from https://console.groq.com
```

### 5. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## Project Structure

```
ai-agent-monitor/
├── app.py                  # Flask backend — routes + evaluation logic
├── templates/
│   └── index.html          # Dashboard UI (Bootstrap 5 + custom CSS)
├── static/                 # Reserved for future static assets
├── requirements.txt
├── .env.example
└── README.md
```

---

## How Each Metric Works

| Metric | Method | Green | Yellow | Red |
|---|---|---|---|---|
| Goal Success | Keyword overlap between expected goal & AI response | ≥ 70% | 40–69% | < 40% |
| Hallucination Risk | Rule-based: fabricated numbers, absolute language, invented URLs | < 30% risk | 30–60% | > 60% |
| Latency | `time.perf_counter()` around Groq API call | < 1500 ms | 1500–3000 ms | > 3000 ms |

**Overall Health** = 50% Goal Success + 30% Safety Score + 20% Latency Score

---

## Using OpenRouter Instead of Groq

Replace the constants at the top of `app.py`:

```python
GROQ_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_MODEL   = "mistralai/mistral-7b-instruct:free"
# Also update the Authorization header to use your OpenRouter key
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Free key from console.groq.com |

---

## Requirements

- Python 3.10+
- Flask 3.x
- An internet connection (Groq API calls)
