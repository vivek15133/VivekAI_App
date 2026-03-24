"""
VivekAI_App - Resume Parser v1.0
Parses uploaded resume (PDF / DOCX / TXT) and extracts:
  - Candidate name, skills, experience, education
  - Builds a rich system-prompt context automatically
"""

import os
import re


# ── Plain-text extraction ─────────────────────────────────────────────────────

def extract_text_from_file(filepath: str) -> str:
    """Return raw text from PDF, DOCX, or TXT file."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext == ".pdf":
            return _extract_pdf(filepath)
        elif ext in (".docx", ".doc"):
            return _extract_docx(filepath)
        else:
            # Fallback: try reading as text
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        return f"[Resume read error: {e}]"


def _extract_pdf(filepath: str) -> str:
    # Try pdfminer first, then pypdf2, then pytesseract on images
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        text = extract_text(filepath)
        if text and text.strip():
            return text
    except Exception:
        pass

    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(filepath)
        pages  = [page.extract_text() or "" for page in reader.pages]
        text   = "\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass

    try:
        import PyPDF2  # type: ignore
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages  = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages)
    except Exception as e:
        return f"[PDF extraction failed: {e}]"


def _extract_docx(filepath: str) -> str:
    try:
        import docx  # type: ignore  (python-docx)
        doc   = docx.Document(filepath)
        paras = [p.text for p in doc.paragraphs]
        return "\n".join(paras)
    except Exception:
        pass

    # Fallback: mammoth
    try:
        import mammoth  # type: ignore
        with open(filepath, "rb") as f:
            result = mammoth.extract_raw_text(f)
        return result.value
    except Exception as e:
        return f"[DOCX extraction failed: {e}]"


# ── Structured parsing ────────────────────────────────────────────────────────

def parse_resume(text: str) -> dict:
    """
    Extract structured fields from raw resume text.
    Returns a dict with: name, email, phone, skills, experience, education, summary
    """
    lines  = [l.strip() for l in text.split("\n") if l.strip()]
    result = {
        "name":       _extract_name(lines),
        "email":      _extract_email(text),
        "phone":      _extract_phone(text),
        "skills":     _extract_skills(text),
        "experience": _extract_experience(text, lines),
        "education":  _extract_education(text, lines),
        "raw":        text[:3000],          # keep first 3000 chars for AI context
    }
    return result


def _extract_name(lines: list) -> str:
    # Usually the first non-trivial line is the name
    for line in lines[:5]:
        # Skip lines that look like headers / URLs / emails
        if "@" in line or "http" in line.lower() or len(line) > 60:
            continue
        if re.match(r"^[A-Z][a-z]+(\s[A-Z][a-z]+)+$", line):
            return line
        # Allow all-caps names
        if re.match(r"^[A-Z\s]{4,40}$", line):
            return line.title()
    return lines[0] if lines else "Candidate"


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"[\+\(]?[\d][\d\s\-\(\)]{7,15}[\d]", text)
    return match.group(0).strip() if match else ""


def _extract_skills(text: str) -> list:
    """Extract a list of skill tokens from common resume patterns."""
    skills = []

    # Look for a Skills section
    skill_section_match = re.search(
        r"(?:skills?|technical skills?|core competencies)[:\s]*\n?(.*?)(?:\n\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL
    )
    if skill_section_match:
        raw = skill_section_match.group(1)
        # Split by common delimiters
        tokens = re.split(r"[,•|\n/]", raw)
        skills = [t.strip() for t in tokens if 2 < len(t.strip()) < 40]

    # Also scan for common tech keywords anywhere in the doc
    tech_keywords = [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
        "React", "Angular", "Vue", "Node.js", "Django", "Flask", "FastAPI",
        "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
        "Machine Learning", "Deep Learning", "NLP", "TensorFlow", "PyTorch",
        "Git", "Linux", "REST", "GraphQL", "Agile", "Scrum",
        "Excel", "Power BI", "Tableau", "Salesforce", "SAP",
    ]
    for kw in tech_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE) and kw not in skills:
            skills.append(kw)

    return skills[:30]   # cap at 30 items


def _extract_experience(text: str, lines: list) -> str:
    """Return the Experience section as a compact string."""
    return _extract_section(text, [
        "experience", "work experience", "employment", "professional experience",
        "work history", "career history"
    ])


def _extract_education(text: str, lines: list) -> str:
    return _extract_section(text, ["education", "academic", "qualifications"])


def _extract_section(text: str, headings: list) -> str:
    pattern = "(?:" + "|".join(re.escape(h) for h in headings) + ")"
    match = re.search(
        rf"(?i){pattern}[:\s]*\n(.*?)(?:\n(?=[A-Z][A-Z\s]{{3,}}:)|\Z)",
        text,
        re.DOTALL
    )
    if match:
        return match.group(1).strip()[:800]
    return ""


# ── System-prompt builder ─────────────────────────────────────────────────────

def build_resume_context(parsed: dict) -> str:
    """
    Convert parsed resume dict into a system-prompt preamble that the AI
    will use to give personalised, context-aware answers.
    """
    name       = parsed.get("name", "the candidate")
    skills     = parsed.get("skills", [])
    experience = parsed.get("experience", "")
    education  = parsed.get("education", "")
    raw        = parsed.get("raw", "")

    skills_str = ", ".join(skills[:20]) if skills else "not specified"

    context = f"""
=== CANDIDATE RESUME CONTEXT ===
Name       : {name}
Key Skills : {skills_str}

Experience Summary:
{experience[:600] if experience else "(see raw below)"}

Education:
{education[:300] if education else "(see raw below)"}

Full Resume Excerpt (first 2000 chars):
{raw[:2000]}
=================================

Use this context to:
1. Tailor every answer to {name}'s specific background.
2. Reference their actual skills when answering technical questions.
3. Frame behavioral answers using their real experience.
4. Highlight strengths relevant to the question being asked.
"""
    return context.strip()


def get_resume_enhanced_prompt(base_prompt: str, resume_context: str) -> str:
    """Prepend resume context to any base system prompt."""
    if not resume_context:
        return base_prompt
    return f"{resume_context}\n\n{base_prompt}"
