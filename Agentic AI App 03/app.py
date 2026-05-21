import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("OPENROUTER_API_KEY")
DB = "chat.db"

# ✅ FIXED & VERIFIED WORKING MODELS
MODELS = {
    "llama": "meta-llama/llama-3.1-8b-instruct",
    "Future any model": ""
}

# ---------------- DATABASE ----------------
def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

init_db()

def get_history(session_id):
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()
    return [{"role": r, "content": c} for r, c in rows]

def save_message(session_id, role, content):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?,?,?)",
            (session_id, role, content)
        )

def get_sessions():
    with sqlite3.connect(DB) as con:
        rows = con.execute("""
            SELECT session_id, MAX(content), MAX(timestamp)
            FROM messages
            WHERE role='user'
            GROUP BY session_id
            ORDER BY MAX(timestamp) DESC
            LIMIT 20
        """).fetchall()

    return [
        {"id": r[0], "preview": (r[1] or "")[:40], "time": r[2]}
        for r in rows
    ]

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html", models=list(MODELS.keys()))

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json

    session_id = data.get("session_id") or str(uuid.uuid4())
    model_key = data.get("model", "llama")
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    if not API_KEY:
        return jsonify({"error": "Missing OPENROUTER_API_KEY"}), 500

    # ✅ safe model selection
    model = MODELS.get(model_key, MODELS["llama"])

    save_message(session_id, "user", user_msg)

    history = get_history(session_id)
    history.append({"role": "user", "content": user_msg})

    SYSTEM_PROMPT = """
        You are an expert teacher and mentor.

        Your role:
        - Guide students step by step
        - Do not just give direct answers immediately
        - Explain concepts in a simple and educational way
        - Ask guiding questions when needed
        - Help students understand, not just memorize answers
        - Be patient, friendly, and structured
    """

    try:
        # ✅ correct OpenRouter endpoint
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "FlaskChatApp"
            },
            # json={
            #     "model": model,
            #     "messages": history
            # },

            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history
                ],
                "temperature": 0.3
            },
            timeout=60
        )

        print(f"[OpenRouter] model={model} status={res.status_code}")

        if not res.ok:
            return jsonify({
                "error": f"OpenRouter {res.status_code}: {res.text}"
            }), 500

        data = res.json()
        reply = data["choices"][0]["message"]["content"]

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Connection error"}), 500
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    save_message(session_id, "assistant", reply)

    return jsonify({
        "reply": reply,
        "session_id": session_id
    })

@app.route("/sessions")
def sessions():
    return jsonify(get_sessions())

@app.route("/history/<session_id>")
def history(session_id):
    return jsonify(get_history(session_id))

@app.route("/new_session", methods=["POST"])
def new_session():
    return jsonify({"session_id": str(uuid.uuid4())})

@app.route("/debug")
def debug():
    return jsonify({
        "api_key": "SET" if API_KEY else "MISSING",
        "models": MODELS
    })

if __name__ == "__main__":
    app.run(debug=True)