from datetime import datetime
from app_init import db
import json


class CVProfile(db.Model):
    """Stores parsed CV data for a session."""
    __tablename__ = "cv_profiles"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    filename = db.Column(db.String(255))
    raw_text = db.Column(db.Text)
    skills = db.Column(db.Text)          # JSON list
    education = db.Column(db.Text)       # JSON list
    experience = db.Column(db.Text)      # JSON list
    career_paths = db.Column(db.Text)    # JSON list
    skill_gaps = db.Column(db.Text)      # JSON dict
    confidence_scores = db.Column(db.Text)  # JSON dict
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    job_matches = db.relationship("JobMatch", backref="profile", lazy=True)
    cover_letters = db.relationship("CoverLetter", backref="profile", lazy=True)
    applications = db.relationship("Application", backref="profile", lazy=True)

    def set_skills(self, skills_list):
        self.skills = json.dumps(skills_list)

    def get_skills(self):
        return json.loads(self.skills) if self.skills else []

    def set_education(self, edu_list):
        self.education = json.dumps(edu_list)

    def get_education(self):
        return json.loads(self.education) if self.education else []

    def set_experience(self, exp_list):
        self.experience = json.dumps(exp_list)

    def get_experience(self):
        return json.loads(self.experience) if self.experience else []

    def set_career_paths(self, paths):
        self.career_paths = json.dumps(paths)

    def get_career_paths(self):
        return json.loads(self.career_paths) if self.career_paths else []

    def set_skill_gaps(self, gaps):
        self.skill_gaps = json.dumps(gaps)

    def get_skill_gaps(self):
        return json.loads(self.skill_gaps) if self.skill_gaps else {}

    def set_confidence_scores(self, scores):
        self.confidence_scores = json.dumps(scores)

    def get_confidence_scores(self):
        return json.loads(self.confidence_scores) if self.confidence_scores else {}

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "filename": self.filename,
            "skills": self.get_skills(),
            "education": self.get_education(),
            "experience": self.get_experience(),
            "career_paths": self.get_career_paths(),
            "skill_gaps": self.get_skill_gaps(),
            "confidence_scores": self.get_confidence_scores(),
            "created_at": self.created_at.isoformat(),
        }


class JobMatch(db.Model):
    """Jobs fetched and matched against the user profile."""
    __tablename__ = "job_matches"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("cv_profiles.id"), nullable=False)
    job_id = db.Column(db.String(128))      # External job ID from Adzuna
    title = db.Column(db.String(255))
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    url = db.Column(db.String(512))
    salary_min = db.Column(db.Float)
    salary_max = db.Column(db.Float)
    match_score = db.Column(db.Float, default=0.0)  # 0–100
    match_reasons = db.Column(db.Text)               # JSON list of reasons
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_match_reasons(self, reasons):
        self.match_reasons = json.dumps(reasons)

    def get_match_reasons(self):
        return json.loads(self.match_reasons) if self.match_reasons else []

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "match_score": self.match_score,
            "match_reasons": self.get_match_reasons(),
        }


class CoverLetter(db.Model):
    """AI-generated cover letters for specific jobs."""
    __tablename__ = "cover_letters"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("cv_profiles.id"), nullable=False)
    job_title = db.Column(db.String(255))
    company = db.Column(db.String(255))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "job_title": self.job_title,
            "company": self.company,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


class Application(db.Model):
    """Simulated job applications log."""
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("cv_profiles.id"), nullable=False)
    job_title = db.Column(db.String(255))
    company = db.Column(db.String(255))
    job_url = db.Column(db.String(512))
    cover_letter_id = db.Column(db.Integer, db.ForeignKey("cover_letters.id"))
    status = db.Column(db.String(64), default="applied")  # applied, pending, rejected, interview
    application_email = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "job_title": self.job_title,
            "company": self.company,
            "job_url": self.job_url,
            "status": self.status,
            "application_email": self.application_email,
            "applied_at": self.applied_at.isoformat(),
        }


class Roadmap(db.Model):
    """AI-generated learning roadmap for a profile."""
    __tablename__ = "roadmaps"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("cv_profiles.id"), nullable=False)
    target_career = db.Column(db.String(255))
    content = db.Column(db.Text)   # JSON structured roadmap
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_content(self, data):
        self.content = json.dumps(data)

    def get_content(self):
        return json.loads(self.content) if self.content else {}

    def to_dict(self):
        return {
            "id": self.id,
            "target_career": self.target_career,
            "content": self.get_content(),
            "created_at": self.created_at.isoformat(),
        }