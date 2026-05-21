"""
cv_parser.py
Extracts skills, education, and experience from CV text using
regex heuristics + spaCy NER. Falls back gracefully if spaCy
model is unavailable.
"""

import re
import io
import logging

logger = logging.getLogger(__name__)

# ── PDF extraction ─────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_storage) -> str:
    """Extract plain text from an uploaded PDF FileStorage object."""
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        file_bytes = file_storage.read()
        text = pdfminer_extract(io.BytesIO(file_bytes))
        if text and text.strip():
            return text.strip()
    except Exception as e:
        logger.warning("pdfminer failed: %s", e)

    # Fallback to PyPDF2
    try:
        import PyPDF2
        file_storage.seek(0)
        reader = PyPDF2.PdfReader(file_storage)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        logger.error("PyPDF2 also failed: %s", e)
        return ""


# ── Skill vocabulary ────────────────────────────────────────────────────────────
TECH_SKILLS = {
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "kotlin", "swift", "r", "matlab", "php", "ruby", "scala", "dart",
    # Web
    "react", "vue", "angular", "next.js", "nuxt", "html", "css", "tailwind",
    "bootstrap", "node.js", "express", "django", "flask", "fastapi", "spring",
    # Data / ML
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "matplotlib", "seaborn", "hugging face", "langchain", "openai",
    # Data Engineering
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "spark", "hadoop", "kafka", "airflow", "dbt", "snowflake", "bigquery",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "jenkins", "github actions", "linux", "bash", "git",
    # Other
    "excel", "power bi", "tableau", "figma", "photoshop", "agile", "scrum",
    "rest api", "graphql", "microservices", "blockchain", "cybersecurity",
}

SOFT_SKILLS = {
    "leadership", "communication", "teamwork", "problem solving",
    "critical thinking", "time management", "project management",
    "collaboration", "adaptability", "creativity", "presentation",
    "negotiation", "mentoring",
}

ALL_SKILLS = TECH_SKILLS | SOFT_SKILLS

# ── Section header patterns ─────────────────────────────────────────────────────
SECTION_PATTERNS = {
    "skills": re.compile(
        r"(skills|technical skills|core competencies|technologies|tools)", re.I
    ),
    "education": re.compile(
        r"(education|academic|qualification|degree|university|college)", re.I
    ),
    "experience": re.compile(
        r"(experience|employment|work history|professional background|career)", re.I
    ),
    "projects": re.compile(r"(projects|portfolio|achievements)", re.I),
}

DEGREE_KEYWORDS = re.compile(
    r"\b(bachelor|master|phd|doctorate|b\.?sc|m\.?sc|b\.?eng|m\.?eng"
    r"|b\.?tech|m\.?tech|mba|associate|diploma|certificate)\b",
    re.I,
)

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


# ── Main parser ─────────────────────────────────────────────────────────────────
def parse_cv(text: str) -> dict:
    """
    Parse CV text and return structured dict with:
      skills, education, experience, summary
    """
    skills = extract_skills(text)
    education = extract_education(text)
    experience = extract_experience(text)
    summary = extract_summary(text)

    return {
        "skills": list(skills),
        "education": education,
        "experience": experience,
        "summary": summary,
    }


def extract_skills(text: str) -> set:
    """Match known skill keywords in the full CV text."""
    text_lower = text.lower()
    found = set()

    for skill in ALL_SKILLS:
        # Word-boundary aware matching (handles multi-word skills too)
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill.title() if len(skill) > 3 else skill.upper())

    # Also try spaCy NER for additional tech entities
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text[:5000])  # limit for speed
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PRODUCT") and len(ent.text) > 2:
                candidate = ent.text.strip().lower()
                if candidate in ALL_SKILLS:
                    found.add(ent.text.strip())
    except Exception:
        pass  # spaCy unavailable — regex results are still good

    return found


def extract_education(text: str) -> list:
    """Extract education blocks — degree + institution + year."""
    lines = text.split("\n")
    education = []
    in_edu_section = False

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Detect section start
        if SECTION_PATTERNS["education"].search(line) and len(line) < 60:
            in_edu_section = True
            continue

        # Detect next section
        if in_edu_section:
            for key, pat in SECTION_PATTERNS.items():
                if key != "education" and pat.search(line) and len(line) < 60:
                    in_edu_section = False
                    break

        if in_edu_section or DEGREE_KEYWORDS.search(line):
            # Grab a 2-line window as context
            context = " ".join(lines[max(0, i-1):i+2])
            years = YEAR_PATTERN.findall(context)
            entry = {
                "text": line,
                "years": years,
                "has_degree": bool(DEGREE_KEYWORDS.search(line)),
            }
            # Avoid duplicates
            if not any(e["text"] == line for e in education):
                education.append(entry)

    return education[:8]  # cap at 8 entries


def extract_experience(text: str) -> list:
    """Extract work experience blocks."""
    lines = text.split("\n")
    experience = []
    in_exp_section = False
    current_block = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_block and in_exp_section:
                experience.append(" ".join(current_block))
                current_block = []
            continue

        if SECTION_PATTERNS["experience"].search(stripped) and len(stripped) < 60:
            in_exp_section = True
            continue

        if in_exp_section:
            for key, pat in SECTION_PATTERNS.items():
                if key != "experience" and pat.search(stripped) and len(stripped) < 60:
                    in_exp_section = False
                    break

        if in_exp_section:
            current_block.append(stripped)

    if current_block:
        experience.append(" ".join(current_block))

    # Format as dicts with year detection
    result = []
    for block in experience[:6]:
        years = YEAR_PATTERN.findall(block)
        result.append({
            "text": block[:300],  # truncate long blocks
            "years": years,
        })

    return result


def extract_summary(text: str) -> str:
    """Return first 400 chars as a rough summary / objective."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    summary_lines = []
    for line in lines[:10]:
        if len(line) > 30:  # Skip short header-like lines
            summary_lines.append(line)
        if len(" ".join(summary_lines)) > 400:
            break
    return " ".join(summary_lines)[:400]