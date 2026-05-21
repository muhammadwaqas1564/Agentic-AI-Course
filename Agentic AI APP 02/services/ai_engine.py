"""
ai_engine.py
All LLM calls go through here.  Uses OpenRouter API with Mistral / LLaMA.
Falls back to rule-based responses when the API key is missing.
"""

import json
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


# ── Core LLM caller ─────────────────────────────────────────────────────────────
def call_llm(prompt: str, system: str = "", max_tokens: int = 1200) -> str:
    """
    Send a prompt to OpenRouter and return the response text.
    Raises RuntimeError if the call fails so callers can catch and fallback.
    """
    api_key = current_app.config.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-career-mentor.app",
        "X-Title": "AI Career Mentor",
    }

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": current_app.config.get("LLM_MODEL", "mistralai/mistral-7b-instruct:free"),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    resp = requests.post(
        current_app.config["OPENROUTER_BASE_URL"],
        headers=headers,
        json=payload,
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# ── Career Analysis ─────────────────────────────────────────────────────────────
def analyze_career_paths(skills: list, education: list, experience: list) -> dict:
    """
    Use LLM to suggest career paths, skill gaps, and confidence scores.
    Returns dict: {career_paths, skill_gaps, confidence_scores, readiness_note}
    """
    system = (
        "You are an expert career counsellor and AI recruiter. "
        "Respond ONLY with valid JSON, no markdown fences, no preamble."
    )
    prompt = f"""
Given this candidate profile:
Skills: {json.dumps(skills[:30])}
Education: {json.dumps([e.get('text','') for e in education[:5]])}
Experience: {json.dumps([e.get('text','') for e in experience[:4]])}

Return a JSON object with exactly these keys:
{{
  "career_paths": [
    {{"title": "...", "description": "...", "readiness": "ready|developing|aspirational"}}
  ],
  "skill_gaps": {{
    "CareerTitle": ["missing_skill1", "missing_skill2"]
  }},
  "confidence_scores": {{
    "CareerTitle": 72
  }},
  "readiness_note": "One paragraph honest assessment of where this candidate is right now and what they should prioritise."
}}

Suggest 3–4 career paths. Be honest — if someone is not ready for ML Engineer, say so and suggest Data Analyst first.
"""
    try:
        raw = call_llm(prompt, system=system, max_tokens=1000)
        # Strip any accidental markdown fences
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("LLM career analysis failed: %s — using fallback.", e)
        return _fallback_career_analysis(skills)


def _fallback_career_analysis(skills: list) -> dict:
    """Rule-based career analysis when LLM is unavailable."""
    tech_skills = {s.lower() for s in skills}
    paths = []
    gaps = {}
    scores = {}

    ml_skills = {"python", "machine learning", "tensorflow", "pytorch", "numpy", "pandas"}
    data_skills = {"sql", "python", "excel", "tableau", "power bi"}
    dev_skills = {"python", "javascript", "react", "node.js", "git", "docker"}

    ml_overlap = tech_skills & {s.lower() for s in ml_skills}
    data_overlap = tech_skills & {s.lower() for s in data_skills}
    dev_overlap = tech_skills & {s.lower() for s in dev_skills}

    if len(data_overlap) >= 2:
        paths.append({"title": "Data Analyst", "description": "Analyse business data to deliver actionable insights.", "readiness": "ready"})
        scores["Data Analyst"] = min(90, 50 + len(data_overlap) * 8)
        gaps["Data Analyst"] = list(data_skills - tech_skills)[:3]

    if len(dev_overlap) >= 2:
        paths.append({"title": "Software Developer", "description": "Build web or backend applications.", "readiness": "developing" if len(dev_overlap) < 4 else "ready"})
        scores["Software Developer"] = min(90, 45 + len(dev_overlap) * 7)
        gaps["Software Developer"] = list(dev_skills - tech_skills)[:3]

    if len(ml_overlap) >= 2:
        paths.append({"title": "ML Engineer", "description": "Design and deploy machine learning models.", "readiness": "aspirational" if len(ml_overlap) < 4 else "developing"})
        scores["ML Engineer"] = min(85, 30 + len(ml_overlap) * 10)
        gaps["ML Engineer"] = list(ml_skills - tech_skills)[:4]

    if not paths:
        paths = [{"title": "Junior Developer", "description": "Start with foundational coding roles.", "readiness": "developing"}]
        scores["Junior Developer"] = 40
        gaps["Junior Developer"] = ["Python", "Git", "SQL", "HTML/CSS"]

    return {
        "career_paths": paths,
        "skill_gaps": gaps,
        "confidence_scores": scores,
        "readiness_note": (
            "Based on your current skills, you have a solid foundation to build from. "
            "Focus on the skill gaps listed for your target role, and consider taking "
            "structured online courses (Coursera, fast.ai, FreeCodeCamp) before applying."
        ),
    }


# ── Cover Letter Generation ─────────────────────────────────────────────────────
def generate_cover_letter(job_title: str, company: str, job_description: str,
                           skills: list, experience: list) -> str:
    """Generate a personalised cover letter using LLM."""
    exp_text = " | ".join([e.get("text", "")[:120] for e in experience[:3]])

    prompt = f"""
Write a professional, compelling cover letter for this job application.

Job Title: {job_title}
Company: {company}
Job Description: {job_description[:500]}

Candidate Skills: {', '.join(skills[:15])}
Candidate Experience: {exp_text}

Requirements:
- 3–4 paragraphs, professional tone
- Open with genuine enthusiasm (not "I am writing to apply for...")
- Highlight 2–3 specific skills that match the role
- Close with a clear call to action
- Do NOT use placeholder text like [Your Name]
- Write as if from the candidate directly
"""
    try:
        return call_llm(prompt, max_tokens=700)
    except Exception as e:
        logger.warning("Cover letter LLM failed: %s", e)
        return _fallback_cover_letter(job_title, company, skills)


def _fallback_cover_letter(job_title: str, company: str, skills: list) -> str:
    skill_str = ", ".join(skills[:5]) if skills else "relevant technical skills"
    return f"""Dear Hiring Manager at {company},

Having followed {company}'s work with great interest, I was excited to discover the {job_title} opening. My background in {skill_str} aligns closely with what your team is building, and I am eager to contribute from day one.

Throughout my career, I have developed strong proficiency in {skill_str}. I thrive in collaborative environments where I can combine technical depth with clear communication to solve real problems — which is exactly the culture I see reflected in {company}'s approach.

I would welcome the opportunity to discuss how my skills and experience can help {company} achieve its goals. Thank you for your time and consideration.

Best regards"""


# ── Roadmap Generation ──────────────────────────────────────────────────────────
def generate_roadmap(target_career: str, skill_gaps: list, current_skills: list) -> dict:
    """Generate a structured weekly learning roadmap."""
    system = (
        "You are a learning coach and curriculum designer. "
        "Respond ONLY with valid JSON, no markdown fences."
    )
    prompt = f"""
Create a practical 12-week learning roadmap for this candidate.

Target Career: {target_career}
Current Skills: {json.dumps(current_skills[:15])}
Skills to Learn: {json.dumps(skill_gaps[:8])}

Return JSON with this structure:
{{
  "target": "{target_career}",
  "duration_weeks": 12,
  "phases": [
    {{
      "phase": 1,
      "title": "Foundation",
      "weeks": "1–4",
      "goals": ["goal1", "goal2"],
      "resources": [
        {{"name": "Course/Resource Name", "url": "https://...", "type": "course|book|practice|project"}}
      ]
    }}
  ],
  "milestones": ["Milestone at week 4", "Milestone at week 8", "Milestone at week 12"],
  "daily_commitment_hours": 2
}}
"""
    try:
        raw = call_llm(prompt, system=system, max_tokens=1200)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("Roadmap LLM failed: %s", e)
        return _fallback_roadmap(target_career, skill_gaps)


def _fallback_roadmap(target_career: str, skill_gaps: list) -> dict:
    gaps = skill_gaps[:6] if skill_gaps else ["Python", "SQL", "Communication"]
    return {
        "target": target_career,
        "duration_weeks": 12,
        "phases": [
            {
                "phase": 1,
                "title": "Foundation",
                "weeks": "1–4",
                "goals": [f"Learn fundamentals of {gaps[0]}" if gaps else "Core concepts", "Set up development environment"],
                "resources": [
                    {"name": "freeCodeCamp", "url": "https://www.freecodecamp.org", "type": "course"},
                    {"name": "Coursera", "url": "https://www.coursera.org", "type": "course"},
                ],
            },
            {
                "phase": 2,
                "title": "Skill Building",
                "weeks": "5–8",
                "goals": ["Build 2 portfolio projects", f"Deep dive into {gaps[1] if len(gaps) > 1 else 'core tools'}"],
                "resources": [
                    {"name": "Kaggle (practice datasets)", "url": "https://www.kaggle.com", "type": "practice"},
                    {"name": "GitHub (open source contribution)", "url": "https://github.com", "type": "project"},
                ],
            },
            {
                "phase": 3,
                "title": "Job Ready",
                "weeks": "9–12",
                "goals": ["Polish portfolio", "Apply to 10+ jobs", "Interview preparation"],
                "resources": [
                    {"name": "LeetCode", "url": "https://leetcode.com", "type": "practice"},
                    {"name": "LinkedIn Learning", "url": "https://www.linkedin.com/learning", "type": "course"},
                ],
            },
        ],
        "milestones": [
            "Week 4: Complete foundation course + first mini-project",
            "Week 8: Two portfolio projects live on GitHub",
            "Week 12: Active job applications with strong portfolio",
        ],
        "daily_commitment_hours": 2,
    }


# ── Application Email ───────────────────────────────────────────────────────────
def generate_application_email(job_title: str, company: str, cover_letter: str) -> str:
    """Generate a professional application email body."""
    prompt = f"""
Write a short professional email to submit a job application.

Job: {job_title} at {company}
The email should:
- Have a clear subject line (prefix with "Subject: ")
- Be 3–4 sentences in the body
- Reference that the cover letter and CV are attached
- Be warm but concise

After the subject line, write the email body.
"""
    try:
        return call_llm(prompt, max_tokens=300)
    except Exception:
        return f"""Subject: Application for {job_title} – AI Career Mentor

Dear Hiring Team at {company},

Please find attached my CV and cover letter for the {job_title} position. I am excited about the opportunity to contribute to your team and believe my background aligns well with your requirements.

I would welcome the chance to discuss my application further. Thank you for your consideration.

Best regards"""