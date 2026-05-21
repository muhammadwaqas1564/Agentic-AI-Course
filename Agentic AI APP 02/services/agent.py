"""
The Career Mentor Agent — an agentic orchestrator that runs the full
analysis pipeline as a sequence of observed → decided → acted steps.

Step 1: Observe   — receive CV text
Step 2: Parse     — extract skills, education, experience
Step 3: Analyse   — career paths, gaps, confidence scores (LLM)
Step 4: Search    — fetch jobs from Adzuna
Step 5: Match     — rank jobs against profile
Step 6: Decide    — flag readiness, choose recommended path
Step 7: Persist   — save everything to DB
"""

import logging
from flask import current_app

from services.cv_parser import parse_cv
from services.ai_engine import analyze_career_paths
from services.job_api import fetch_jobs, match_jobs_to_profile

logger = logging.getLogger(__name__)


class CareerMentorAgent:
    """
    Stateless agent: each call to run() executes the full pipeline
    and returns a structured result dict. Persistence is handled
    by the caller (Flask route) to keep the agent framework-agnostic.
    """

    # ── Step decision thresholds ─────────────────────────────────────────────
    MIN_SKILLS_FOR_SENIOR = 12
    MIN_SKILLS_FOR_MID = 6
    MATCH_THRESHOLD_APPLY = 60  # Auto-apply only above this score

    def run(self, cv_text: str, location: str = "London") -> dict:
        """
        Execute the full agentic pipeline.
        Returns a dict consumed by Flask routes + Jinja templates.
        """
        self._log("OBSERVE", "CV received. Starting agentic pipeline.")

        # ── Step 2: Parse ────────────────────────────────────────────────────
        self._log("PARSE", "Extracting skills, education, experience.")
        parsed = parse_cv(cv_text)
        skills = parsed["skills"]
        education = parsed["education"]
        experience = parsed["experience"]

        self._log("PARSE", f"Extracted {len(skills)} skills, "
                           f"{len(education)} education entries, "
                           f"{len(experience)} experience entries.")

        # ── Step 3: Analyse ──────────────────────────────────────────────────
        self._log("ANALYSE", "Running LLM career analysis.")
        career_data = analyze_career_paths(skills, education, experience)

        career_paths = career_data.get("career_paths", [])
        skill_gaps = career_data.get("skill_gaps", {})
        confidence_scores = career_data.get("confidence_scores", {})
        readiness_note = career_data.get("readiness_note", "")

        # ── Step 4: Decide primary career path ──────────────────────────────
        primary_path = self._decide_primary_path(career_paths, confidence_scores)
        self._log("DECIDE", f"Primary recommended path: {primary_path}")

        # ── Step 5: Search jobs ──────────────────────────────────────────────
        self._log("SEARCH", f"Fetching jobs for skills: {skills[:5]}")
        raw_jobs = fetch_jobs(
            keywords=skills[:8] if skills else [primary_path],
            location=location,
            max_results=20,
        )
        self._log("SEARCH", f"Retrieved {len(raw_jobs)} raw job listings.")

        # ── Step 6: Match ────────────────────────────────────────────────────
        self._log("MATCH", "Scoring and ranking jobs against profile.")
        matched_jobs = match_jobs_to_profile(raw_jobs, skills)

        # ── Step 7: Agent Recommendations ───────────────────────────────────
        recommendations = self._build_recommendations(
            skills, career_paths, matched_jobs, primary_path
        )
        self._log("ACT", f"Generated {len(recommendations)} agent recommendations.")

        return {
            "parsed": parsed,
            "skills": skills,
            "education": education,
            "experience": experience,
            "career_paths": career_paths,
            "skill_gaps": skill_gaps,
            "confidence_scores": confidence_scores,
            "readiness_note": readiness_note,
            "primary_path": primary_path,
            "matched_jobs": matched_jobs,
            "recommendations": recommendations,
            "agent_log": self._agent_log,
        }

    # ── Internal decision logic ──────────────────────────────────────────────────
    def _decide_primary_path(self, career_paths: list, scores: dict) -> str:
        """
        Pick the most realistic career path.
        Prefer 'ready' > 'developing' > 'aspirational'.
        Break ties by confidence score.
        """
        priority = {"ready": 0, "developing": 1, "aspirational": 2}

        if not career_paths:
            return "Software Developer"

        sorted_paths = sorted(
            career_paths,
            key=lambda p: (
                priority.get(p.get("readiness", "aspirational"), 2),
                -scores.get(p.get("title", ""), 0),
            ),
        )
        return sorted_paths[0].get("title", "Software Developer")

    def _build_recommendations(
        self, skills: list, career_paths: list, jobs: list, primary_path: str
    ) -> list[dict]:
        """
        Produce a set of concrete agent recommendations:
        - Apply to high-match jobs
        - Learn specific skills
        - Take specific actions
        """
        recs = []
        skill_count = len(skills)

        # Seniority assessment
        if skill_count >= self.MIN_SKILLS_FOR_SENIOR:
            recs.append({
                "type": "insight",
                "icon": "🎯",
                "message": f"Strong profile with {skill_count} identified skills. You're ready for mid-to-senior level roles.",
            })
        elif skill_count >= self.MIN_SKILLS_FOR_MID:
            recs.append({
                "type": "insight",
                "icon": "📈",
                "message": f"Solid foundation with {skill_count} skills. Focus on depth over breadth before senior applications.",
            })
        else:
            recs.append({
                "type": "warning",
                "icon": "⚠️",
                "message": (
                    "Your profile shows a limited skill set. Prioritise building core "
                    f"competencies for {primary_path} before applying broadly."
                ),
            })

        # High-match job recommendations
        apply_jobs = [j for j in jobs if j["match_score"] >= self.MATCH_THRESHOLD_APPLY]
        if apply_jobs:
            top = apply_jobs[0]
            recs.append({
                "type": "action",
                "icon": "💼",
                "message": (
                    f"Strong match found: {top['title']} at {top['company']} "
                    f"({top['match_score']}% match). Apply now."
                ),
            })

        # Learning recommendation
        recs.append({
            "type": "learn",
            "icon": "📚",
            "message": f"Generate a personalised learning roadmap for {primary_path} to close skill gaps systematically.",
        })

        # Path-specific advice
        for path in career_paths[:2]:
            if path.get("readiness") == "aspirational":
                recs.append({
                    "type": "roadblock",
                    "icon": "🚧",
                    "message": (
                        f"You are not yet ready for {path['title']}. "
                        "Complete the roadmap and revisit in 3–6 months."
                    ),
                })

        return recs

    # ── Logging ──────────────────────────────────────────────────────────────────
    def __init__(self):
        self._agent_log = []

    def _log(self, step: str, message: str):
        entry = f"[{step}] {message}"
        self._agent_log.append(entry)
        logger.info("Agent %s", entry)