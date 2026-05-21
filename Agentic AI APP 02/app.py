"""
app.py  —  AI Career Mentor Agent
Main Flask application: routes, session management, and API endpoints.
"""

import os
import uuid
import logging
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash
)
from werkzeug.utils import secure_filename

from app_init import db
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "txt"}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    # Import models here (after db is bound) to avoid circular imports
    with app.app_context():
        from models.user import CVProfile, JobMatch, CoverLetter, Application, Roadmap
        db.create_all()

    # ── Helpers ──────────────────────────────────────────────────────────────────
    def allowed_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def get_or_create_session():
        if "user_session" not in session:
            session["user_session"] = str(uuid.uuid4())
        return session["user_session"]

    def get_active_profile(session_id):
        from models.user import CVProfile
        return (
            CVProfile.query
            .filter_by(session_id=session_id)
            .order_by(CVProfile.created_at.desc())
            .first()
        )

    # ── Pages ─────────────────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        return render_template("index.html", profile=profile)

    @app.route("/upload")
    def upload():
        get_or_create_session()
        return render_template("upload.html")

    @app.route("/dashboard")
    def dashboard():
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("upload"))
        return render_template("dashboard.html", profile=profile)

    @app.route("/jobs")
    def jobs():
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("upload"))
        from models.user import JobMatch
        job_matches = (
            JobMatch.query
            .filter_by(profile_id=profile.id)
            .order_by(JobMatch.match_score.desc())
            .all()
        )
        return render_template("jobs.html", profile=profile, job_matches=job_matches)

    @app.route("/roadmap")
    def roadmap():
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("upload"))
        from models.user import Roadmap
        roadmaps = Roadmap.query.filter_by(profile_id=profile.id).order_by(Roadmap.created_at.desc()).all()
        return render_template("roadmap.html", profile=profile, roadmaps=roadmaps)

    @app.route("/applications")
    def applications():
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            flash("Please upload your CV first.", "warning")
            return redirect(url_for("upload"))
        from models.user import Application, CoverLetter
        apps = Application.query.filter_by(profile_id=profile.id).order_by(Application.applied_at.desc()).all()
        letters = CoverLetter.query.filter_by(profile_id=profile.id).order_by(CoverLetter.created_at.desc()).all()
        return render_template("applications.html", profile=profile, applications=apps, cover_letters=letters)

    # ── API Endpoints ─────────────────────────────────────────────────────────────
    @app.route("/api/upload-cv", methods=["POST"])
    def api_upload_cv():
        """Handle CV upload: parse → analyse → store → return results."""
        from models.user import CVProfile, JobMatch
        from services.cv_parser import extract_text_from_pdf
        from services.agent import CareerMentorAgent

        sid = get_or_create_session()
        location = request.form.get("location", "London")

        # ── Get text ──────────────────────────────────────────────────────────
        cv_text = ""
        filename = "manual_entry.txt"

        if "cv_file" in request.files:
            file = request.files["cv_file"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                if filename.endswith(".pdf"):
                    cv_text = extract_text_from_pdf(file)
                else:
                    cv_text = file.read().decode("utf-8", errors="ignore")
            elif file and file.filename:
                return jsonify({"error": "Only PDF and TXT files are supported."}), 400

        if not cv_text:
            cv_text = request.form.get("cv_text", "").strip()

        if not cv_text or len(cv_text) < 50:
            return jsonify({"error": "CV content too short. Please upload a valid CV."}), 400

        # ── Run agent ─────────────────────────────────────────────────────────
        try:
            agent = CareerMentorAgent()
            result = agent.run(cv_text, location=location)
        except Exception as e:
            logger.error("Agent error: %s", e)
            return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

        # ── Persist profile ────────────────────────────────────────────────────
        profile = CVProfile(session_id=sid, filename=filename, raw_text=cv_text[:8000])
        profile.set_skills(result["skills"])
        profile.set_education(result["education"])
        profile.set_experience(result["experience"])
        profile.set_career_paths(result["career_paths"])
        profile.set_skill_gaps(result["skill_gaps"])
        profile.set_confidence_scores(result["confidence_scores"])
        db.session.add(profile)
        db.session.flush()  # Get profile.id before committing

        # ── Persist job matches ────────────────────────────────────────────────
        for job in result["matched_jobs"][:15]:
            jm = JobMatch(
                profile_id=profile.id,
                job_id=job.get("job_id", ""),
                title=job.get("title", ""),
                company=job.get("company", ""),
                location=job.get("location", ""),
                description=job.get("description", ""),
                url=job.get("url", "#"),
                salary_min=job.get("salary_min"),
                salary_max=job.get("salary_max"),
                match_score=job.get("match_score", 0),
            )
            jm.set_match_reasons(job.get("match_reasons", []))
            db.session.add(jm)

        db.session.commit()

        return jsonify({
            "success": True,
            "profile_id": profile.id,
            "skills": result["skills"],
            "career_paths": result["career_paths"],
            "primary_path": result["primary_path"],
            "recommendations": result["recommendations"],
            "readiness_note": result["readiness_note"],
            "job_count": len(result["matched_jobs"]),
        })

    @app.route("/api/generate-cover-letter", methods=["POST"])
    def api_generate_cover_letter():
        """Generate a personalised cover letter for a specific job."""
        from models.user import CoverLetter
        from services.ai_engine import generate_cover_letter

        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            return jsonify({"error": "No CV profile found."}), 400

        data = request.get_json()
        job_title = data.get("job_title", "")
        company = data.get("company", "")
        job_description = data.get("job_description", "")

        if not job_title or not company:
            return jsonify({"error": "Job title and company are required."}), 400

        letter_text = generate_cover_letter(
            job_title=job_title,
            company=company,
            job_description=job_description,
            skills=profile.get_skills(),
            experience=profile.get_experience(),
        )

        # Persist
        cl = CoverLetter(
            profile_id=profile.id,
            job_title=job_title,
            company=company,
            content=letter_text,
        )
        db.session.add(cl)
        db.session.commit()

        return jsonify({"success": True, "cover_letter": letter_text, "id": cl.id})

    @app.route("/api/generate-roadmap", methods=["POST"])
    def api_generate_roadmap():
        """Generate a learning roadmap for a target career."""
        from models.user import Roadmap
        from services.ai_engine import generate_roadmap

        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            return jsonify({"error": "No CV profile found."}), 400

        data = request.get_json()
        target_career = data.get("target_career", profile.get_career_paths()[0].get("title", "Software Developer") if profile.get_career_paths() else "Software Developer")

        skill_gaps = profile.get_skill_gaps().get(target_career, [])
        roadmap_data = generate_roadmap(
            target_career=target_career,
            skill_gaps=skill_gaps,
            current_skills=profile.get_skills(),
        )

        rm = Roadmap(profile_id=profile.id, target_career=target_career)
        rm.set_content(roadmap_data)
        db.session.add(rm)
        db.session.commit()

        return jsonify({"success": True, "roadmap": roadmap_data, "id": rm.id})

    @app.route("/api/auto-apply", methods=["POST"])
    def api_auto_apply():
        """Simulate auto-apply: generate email + log application."""
        from models.user import Application, CoverLetter
        from services.ai_engine import generate_application_email

        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            return jsonify({"error": "No CV profile found."}), 400

        data = request.get_json()
        job_title = data.get("job_title", "")
        company = data.get("company", "")
        job_url = data.get("job_url", "#")
        cover_letter_id = data.get("cover_letter_id")

        # Fetch cover letter text if ID provided
        cover_letter_text = ""
        if cover_letter_id:
            cl = CoverLetter.query.get(cover_letter_id)
            if cl:
                cover_letter_text = cl.content

        email_body = generate_application_email(job_title, company, cover_letter_text)

        app_record = Application(
            profile_id=profile.id,
            job_title=job_title,
            company=company,
            job_url=job_url,
            cover_letter_id=cover_letter_id,
            status="applied",
            application_email=email_body,
        )
        db.session.add(app_record)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Application simulated for {job_title} at {company}.",
            "application_email": email_body,
            "application_id": app_record.id,
        })

    @app.route("/api/profile", methods=["GET"])
    def api_profile():
        """Return the active profile as JSON."""
        sid = get_or_create_session()
        profile = get_active_profile(sid)
        if not profile:
            return jsonify({"error": "No profile found."}), 404
        return jsonify(profile.to_dict())

    @app.route("/api/clear-session", methods=["POST"])
    def api_clear_session():
        """Start fresh (new upload)."""
        session.pop("user_session", None)
        return jsonify({"success": True})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)