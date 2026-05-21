"""
Medical AI Diagnosis Assistant - Flask Application
Uses Ollama (mistral:7b-instruct) + FAISS + RAG for local, free AI inference.
"""

import os
import re
import json
import sqlite3
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

import requests
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "medical_ai_secret_2024"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
# OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
# OLLAMA_MODEL = "mistral:7b-instruct"
OLLAMA_MODEL = "tinyllama:latest"
# OLLAMA_MODEL = "llama3:8b"
DB_PATH = "medical_records.db"
KB_PATH = "medical_knowledge_base.txt"
EMBED_MODEL = "all-MiniLM-L6-v2"   # ~80 MB, CPU-friendly

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            age         INTEGER,
            gender      TEXT,
            symptoms    TEXT,
            history     TEXT,
            medications TEXT,
            lab_report  TEXT,
            radiology   TEXT,
            ai_result   TEXT,
            created_at  TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_patient(data: dict, ai_result: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO patients
            (name, age, gender, symptoms, history, medications,
             lab_report, radiology, ai_result, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        data["name"], data["age"], data["gender"],
        data["symptoms"], data["history"], data["medications"],
        data["lab_report"], data["radiology"],
        ai_result, datetime.now().isoformat()
    ))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_patient(pid: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id=?", (pid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# ─────────────────────────────────────────────
# Knowledge Base + FAISS
# ─────────────────────────────────────────────
embedder = None
faiss_index = None
kb_chunks: list[str] = []

def load_knowledge_base():
    global embedder, faiss_index, kb_chunks

    logger.info("Loading embedding model …")
    embedder = SentenceTransformer(EMBED_MODEL)

    if not os.path.exists(KB_PATH):
        logger.warning("Knowledge base file not found – RAG disabled.")
        return
    with open(KB_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    # split by disease headings
    sections = re.split(r"\n(?=[A-Z][A-Za-z0-9\s\(\)\/\-]+?\nSymptoms:)", text)

    kb_chunks.clear()

    for sec in sections:
        sec = sec.strip()

        if len(sec) > 100:
            kb_chunks.append(sec)

def retrieve_context(query: str, top_k: int = 5) -> str:
    if faiss_index is None or not kb_chunks:
        return "No knowledge base available."
    q_vec = embedder.encode([query], show_progress_bar=False)
    q_vec = np.array(q_vec, dtype="float32")
    _, indices = faiss_index.search(q_vec, top_k)
    snippets = [kb_chunks[i] for i in indices[0] if i < len(kb_chunks)]
    return "\n---\n".join(snippets)

# ─────────────────────────────────────────────
# Input Validation
# ─────────────────────────────────────────────
def validate_patient_input(data: dict) -> list[str]:
    errors = []
    if not data.get("name", "").strip():
        errors.append("Patient name is required.")
    age = data.get("age", "")
    try:
        age_int = int(age)
        if not (0 < age_int < 130):
            errors.append("Age must be between 1 and 129.")
    except (ValueError, TypeError):
        errors.append("Age must be a valid number.")
    if not data.get("symptoms", "").strip():
        errors.append("Symptoms are required.")
    return errors

def sanitize(text: str, max_len: int = 2000) -> str:
    text = re.sub(r"[<>]", "", text or "")
    return text[:max_len].strip()

# ─────────────────────────────────────────────
# LLM Call (Ollama)
# ─────────────────────────────────────────────
def call_ollama(prompt: str, timeout: int = 120) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            # LOWER temperature = stable JSON
            "temperature": 0.1,
            # better focus
            "top_p": 0.8,
            "num_predict": 700,
            # prevents repetition
            "repeat_penalty": 1.15,
            # more deterministic
            "top_k": 20,
            # stable sampling
            "seed": 42
        }
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    
    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama is not running. Please start Ollama with: ollama serve"
    
    except requests.exceptions.Timeout:
        return "ERROR: LLM timed out. Try a shorter input."
    
    except Exception as e:
        logger.error("Ollama error: %s", e)
        return f"ERROR: {str(e)}"

# ─────────────────────────────────────────────
# AI Pipeline
# ─────────────────────────────────────────────
# def build_prompt(patient: dict, context: str) -> str:
#     return f"""
#         You are a clinical AI system inside a hospital decision support tool.

#         🚨 STRICT RULES (MUST FOLLOW):
#         - Output ONLY valid JSON
#         - Do NOT add explanations
#         - Do NOT use markdown
#         - Do NOT include text before or after JSON
#         - Do NOT use [INST], tags, or commentary

#         === MEDICAL KNOWLEDGE (REFERENCE ONLY) ===
#         {context}

#         === PATIENT DATA ===
#         Name: {patient['name']}
#         Age: {patient['age']}
#         Gender: {patient['gender']}
#         Symptoms: {patient['symptoms']}
#         Medical History: {patient['history'] or 'None'}
#         Medications: {patient['medications'] or 'None'}
#         Lab Reports: {patient['lab_report'] or 'None'}
#         Radiology: {patient['radiology'] or 'None'}

#         === OUTPUT FORMAT (MANDATORY JSON SCHEMA) ===
#         Return EXACTLY this structure:

#         {{
#         "possible_diseases": [
#             {{
#             "name": "disease name",
#             "confidence": "High | Medium | Low",
#             "reason": "clinical reasoning"
#             }}
#         ],
#         "risk_factors": ["factor1", "factor2"],
#         "recommended_tests": ["test1", "test2"],
#         "patient_summary": "short clinical summary",
#         "priority_level": "Critical | High | Medium | Low",
#         "explainability": "why this prediction was made based on symptoms and history"
#         }}

#         If uncertain, still return valid JSON.
#         """


# def build_prompt(patient: dict, context: str) -> str:
#     return f"""
#         You are a medical assistant.

#         Use the context below.

#         Return ONLY JSON.

#         Context:
#         {context}

#         Patient:
#         {patient['symptoms']} {patient['history']} {patient['lab_report']}

#         Output format:
#         {{
#         "diseases": ["..."],
#         "risk": ["..."],
#         "tests": ["..."],
#         "summary": "...",
#         "priority": "High/Medium/Low"
#         }}
#         """


# def build_prompt(patient: dict, context: str) -> str:
#     return f"""
#         You are a clinical decision support AI.

#         TASK:
#         Analyze patient data and return ONLY valid JSON.

#         RULES:
#         - Output ONLY JSON
#         - No explanations
#         - No markdown
#         - No extra text
#         - If unsure, still return best possible JSON

#         MEDICAL CONTEXT:
#         {context}

#         PATIENT DATA:
#         Symptoms: {patient['symptoms']}
#         History: {patient['history']}
#         Medications: {patient['medications']}
#         Lab: {patient['lab_report']}
#         Radiology: {patient['radiology']}

#         OUTPUT FORMAT:
#         {{
#         "possible_diseases": [
#             {{
#             "name": "",
#             "confidence": "High/Medium/Low",
#             "reason": ""
#             }}
#         ],
#         "risk_factors": [],
#         "recommended_tests": [],
#         "patient_summary": "",
#         "priority_level": "Critical/High/Medium/Low",
#         "explainability": ""
#         }}
#         """
def build_prompt(patient: dict, context: str) -> str:

    return f"""
You are an expert clinical AI assistant.

Analyze the patient data carefully.

Use the medical context only as reference.

Return ONLY valid JSON.

DO NOT:
- explain outside JSON
- use markdown
- add comments
- add extra text

MEDICAL CONTEXT:
{context}

PATIENT:
Age: {patient['age']}
Gender: {patient['gender']}

Symptoms:
{patient['symptoms']}

History:
{patient['history']}

Medications:
{patient['medications']}

Lab Reports:
{patient['lab_report']}

Radiology:
{patient['radiology']}

IMPORTANT:
- Predict maximum 3 diseases
- Use concise medical reasoning
- Recommended tests must be medically relevant
- Priority must be:
  Critical / High / Medium / Low

RETURN THIS EXACT JSON STRUCTURE:

{{
  "possible_diseases": [
    {{
      "name": "",
      "confidence": "High",
      "reason": ""
    }}
  ],
  "risk_factors": [],
  "recommended_tests": [],
  "patient_summary": "",
  "priority_level": "",
  "explainability": ""
}}
"""

def run_ai_pipeline(patient: dict) -> dict:

    # =========================
    # STEP 1: SMART QUERY BUILD
    # =========================
    query_parts = [
        patient.get("symptoms", ""),
        patient.get("history", ""),
        patient.get("medications", ""),
        patient.get("lab_report", ""),
        patient.get("radiology", "")
    ]

    query = " ".join([q for q in query_parts if q])

    # =========================
    # STEP 2: RAG RETRIEVAL (LIMITED)
    # =========================
    context = retrieve_context(query, top_k=2)
    context = context[:1500]
    # IMPORTANT FIX:
    # Keep only top relevant chunks (avoid LLM overload)
    # context = context[:2000]  # limit tokens roughly
    context = "\n".join(context.split("\n")[:25])
    
    # =========================
    # STEP 3: BUILD PROMPT
    # =========================
    prompt = build_prompt(patient, context)

    # =========================
    # STEP 4: LLM CALL
    # =========================
    raw = call_ollama(prompt)

    if not raw or raw.startswith("ERROR"):
        return {"error": raw}

    # =========================
    # STEP 5: STRONG JSON CLEANING
    # =========================
    def extract_json(text):
        try:
            return json.loads(text)
        except:
            pass

        text = re.sub(r"```json", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            return None

        json_text = text[start:end+1]

        try:
            return json.loads(json_text)
        except Exception as e:
            print("JSON PARSE ERROR:", e)
            print(json_text)
            return None
    # def extract_json(text):

    #     # remove markdown blocks
    #     text = re.sub(r"```json", "", text)
    #     text = re.sub(r"```", "", text)
    #     text = text.strip()

    #     # find json object
    #     start = text.find("{")
    #     end = text.rfind("}")

    #     if start == -1 or end == -1:
    #         return None

    #     json_str = text[start:end + 1]

    #     # fix common issues
    #     json_str = json_str.replace("\n", " ")
    #     json_str = json_str.replace("\t", " ")

    #     try:
    #         return json.loads(json_str)
    #     except Exception as e:
    #         print("JSON ERROR:", e)
    #         print(json_str)
    #         return None


    # # IMPORTANT:
    # # create result variable
    # result = extract_json(raw)
    
    
    # def extract_json(text):
    #     text = text.strip()

    #     try:
    #         return json.loads(text)
    #     except:
    #         pass

    #     match = re.search(r'\{.*\}', text, re.DOTALL)

    #     if match:
    #         try:
    #             return json.loads(match.group())
    #         except:
    #             return None

    #     return None
    
    # def extract_json(text):
    #     # remove markdown
    #     text = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    #     # text = re.sub(r"```json|```", "", text).strip()

    #     # find FIRST valid JSON object safely
    #     start = text.find("{")
    #     end = text.rfind("}")

    #     if start == -1 or end == -1:
    #         return None

    #     json_str = text[start:end+1]
    #     # repair common model mistakes
    #     json_str = json_str.replace("'", '"')

    #     try:
    #         return json.loads(json_str)
    #     except:
    #         return None

    # result = extract_json(raw)



    # def post_process(result):
    #     if not result:
    #         return result

    #     # enforce minimum structure
    #     result.setdefault("possible_diseases", [])
    #     result.setdefault("risk_factors", [])
    #     result.setdefault("recommended_tests", [])
    #     result.setdefault("patient_summary", "")
    #     result.setdefault("priority_level", "Medium")
    #     result.setdefault("explainability", "")

    #     # limit diseases (avoid hallucination explosion)
    #     result["possible_diseases"] = result["possible_diseases"][:3]

    #     return result
    # # =========================
    # # STEP 6: SAFE FALLBACK
    # # =========================
    # if result:
    #     return post_process(result)

    # return {
    #     "possible_diseases": [],
    #     "risk_factors": [],
    #     "recommended_tests": [],
    #     "patient_summary": raw,
    #     "priority_level": "Unknown",
    #     "explainability": "Model output could not be parsed into JSON."
    # }


    def post_process(result):

        if not result:
            return None

        result.setdefault("possible_diseases", [])
        result.setdefault("risk_factors", [])
        result.setdefault("recommended_tests", [])
        result.setdefault("patient_summary", "")
        result.setdefault("priority_level", "Medium")
        result.setdefault("explainability", "")

        # limit disease count
        result["possible_diseases"] = result["possible_diseases"][:3]

        return result


    # SUCCESS
    if result:
        return post_process(result)

    # FALLBACK
    return {
        "possible_diseases": [
            {
                "name": "Unable to determine",
                "confidence": "Low",
                "reason": "Model failed to generate structured medical response"
            }
        ],
        "risk_factors": [],
        "recommended_tests": [],
        "patient_summary": raw[:500],
        "priority_level": "Medium",
        "explainability": "JSON parsing failed."
    }
# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    raw_data = {
        "name":        sanitize(request.form.get("name", "")),
        "age":         request.form.get("age", "").strip(),
        "gender":      sanitize(request.form.get("gender", "Not specified")),
        "symptoms":    sanitize(request.form.get("symptoms", "")),
        "history":     sanitize(request.form.get("history", "")),
        "medications": sanitize(request.form.get("medications", "")),
        "lab_report":  sanitize(request.form.get("lab_report", "")),
        "radiology":   sanitize(request.form.get("radiology", "")),
    }

    errors = validate_patient_input(raw_data)
    if errors:
        return render_template("index.html", errors=errors, form_data=raw_data)

    raw_data["age"] = int(raw_data["age"])

    # Run AI
    ai_result = run_ai_pipeline(raw_data)

    # Save to DB
    pid = save_patient(raw_data, json.dumps(ai_result))

    return render_template("result.html",
                           patient=raw_data,
                           result=ai_result,
                           patient_id=pid)

@app.route("/patient/<int:pid>")
def view_patient(pid):
    p = get_patient(pid)
    if not p:
        return "Patient not found", 404
    result = json.loads(p["ai_result"]) if p["ai_result"] else {}
    return render_template("result.html", patient=p, result=result, patient_id=pid)

@app.route("/health")
def health():
    """Quick endpoint to check if Ollama is reachable."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"status": "ok", "ollama": True, "models": models})
    except Exception:
        return jsonify({"status": "ok", "ollama": False, "models": []}), 200

# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    load_knowledge_base()
    app.run(debug=True, host="0.0.0.0", port=5000)
