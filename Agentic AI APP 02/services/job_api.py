"""
job_api.py
Fetches jobs from Adzuna API and ranks them against a skill profile.
Falls back to realistic mock data when API credentials are absent.
"""

import logging
import math
import requests
from flask import current_app

logger = logging.getLogger(__name__)


# ── Adzuna API ──────────────────────────────────────────────────────────────────
def fetch_jobs(keywords: list[str], location: str = "London", max_results: int = 20) -> list[dict]:
    """
    Fetch jobs from Adzuna.  Returns a list of normalized job dicts.
    Falls back to mock data if credentials are missing or request fails.
    """
    app_id = current_app.config.get("ADZUNA_APP_ID", "")
    app_key = current_app.config.get("ADZUNA_APP_KEY", "")
    country = current_app.config.get("ADZUNA_COUNTRY", "gb")

    if not app_id or not app_key:
        logger.warning("Adzuna credentials missing — using mock job data.")
        return _mock_jobs(keywords, location)

    query = " ".join(keywords[:5])  # Adzuna works best with 3–5 keywords
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "where": location,
        "results_per_page": max_results,
        "content-type": "application/json",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        jobs = [_normalize_adzuna(job) for job in data.get("results", [])]
        logger.info("Fetched %d jobs from Adzuna.", len(jobs))
        return jobs
    except requests.RequestException as e:
        logger.error("Adzuna API error: %s — falling back to mock data.", e)
        return _mock_jobs(keywords, location)


def _normalize_adzuna(raw: dict) -> dict:
    """Map Adzuna response fields to our internal schema."""
    salary = raw.get("salary_min"), raw.get("salary_max")
    return {
        "job_id": raw.get("id", ""),
        "title": raw.get("title", "Unknown Role"),
        "company": raw.get("company", {}).get("display_name", "Unknown Company"),
        "location": raw.get("location", {}).get("display_name", "Remote"),
        "description": raw.get("description", "")[:600],
        "url": raw.get("redirect_url", "#"),
        "salary_min": float(salary[0]) if salary[0] else None,
        "salary_max": float(salary[1]) if salary[1] else None,
    }


# ── Job Matching ────────────────────────────────────────────────────────────────
def match_jobs_to_profile(jobs: list[dict], skills: list[str]) -> list[dict]:
    """
    Score each job 0–100 by how many profile skills appear in
    the job title + description.  Attach match_score and match_reasons.
    """
    skill_set = {s.lower() for s in skills}
    scored = []

    for job in jobs:
        haystack = (job["title"] + " " + job.get("description", "")).lower()
        matched = [s for s in skill_set if s in haystack]
        score = min(100, math.ceil(len(matched) / max(len(skill_set), 1) * 100))

        # Bonus for exact title keyword match
        title_lower = job["title"].lower()
        title_hits = [s for s in skill_set if s in title_lower]
        score = min(100, score + len(title_hits) * 5)

        reasons = []
        if matched:
            reasons.append(f"Matches your skills: {', '.join(matched[:5])}")
        if not matched:
            reasons.append("General match based on career path alignment")

        scored.append({
            **job,
            "match_score": score,
            "match_reasons": reasons,
        })

    # Sort by score descending
    scored.sort(key=lambda j: j["match_score"], reverse=True)
    return scored


# ── Mock Data (fallback) ────────────────────────────────────────────────────────
def _mock_jobs(keywords: list[str], location: str) -> list[dict]:
    """Realistic mock jobs for demo / no-credential mode."""
    keyword_str = " & ".join(k.title() for k in keywords[:2]) if keywords else "Tech"
    templates = [
        {
            "job_id": f"mock_{i}",
            "title": title,
            "company": company,
            "location": location,
            "description": desc,
            "url": "https://www.adzuna.com",
            "salary_min": salary[0],
            "salary_max": salary[1],
        }
        for i, (title, company, desc, salary) in enumerate([
            ("Junior Data Analyst", "TechCorp Ltd",
             f"Analyse data using {keyword_str}. Work with SQL, Python, and Tableau to deliver insights. "
             "Entry-level role with mentorship programme.", (28000, 38000)),
            ("Python Developer", "StartupXYZ",
             "Build scalable backend services using Python and Flask. Experience with REST APIs and Docker a plus.",
             (35000, 50000)),
            ("Machine Learning Engineer", "AI Innovations",
             "Design and deploy ML pipelines. Strong Python, PyTorch, and cloud (AWS/GCP) experience required.",
             (55000, 80000)),
            ("Data Scientist", "FinTech Global",
             "Use statistical modelling and machine learning to extract insights from financial data. SQL + Python essential.",
             (45000, 65000)),
            ("Software Engineer (Full Stack)", "CloudBase",
             "Build React frontends and Node.js backends. Experience with PostgreSQL, Docker, and CI/CD pipelines.",
             (40000, 60000)),
            ("Business Intelligence Developer", "RetailCo",
             "Create Power BI dashboards and ETL pipelines. SQL expertise and data storytelling skills required.",
             (32000, 45000)),
            ("DevOps Engineer", "NetOps",
             "Manage Kubernetes clusters, Terraform infrastructure, and CI/CD pipelines on AWS.",
             (50000, 70000)),
            ("NLP Research Engineer", "DeepMind-style Startup",
             "Work on cutting-edge NLP models using HuggingFace and PyTorch. PhD or strong research background preferred.",
             (60000, 90000)),
            ("Product Data Analyst", "GrowthLabs",
             "Analyse product metrics, A/B tests, and user funnels. Python, SQL, and Mixpanel experience ideal.",
             (30000, 42000)),
            ("Cloud Solutions Architect", "Enterprise Systems",
             "Design cloud-native architectures on Azure and AWS. Strong communication and client-facing skills.",
             (65000, 95000)),
        ])
    ]
    return templates