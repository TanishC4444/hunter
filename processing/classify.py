import re


def matches(text, terms):
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) for term in terms)


def classify(job, rules):
    text = " ".join((job.title, job.department, job.description))
    return [name for name, config in rules["categories"].items() if matches(text, config["terms"])]


def exclusion(job):
    title = job.title.lower()
    if re.search(r"\b(staff|principal|sr\.?|senior)\s+(software\s+|data\s+|security\s+)?(engineer|developer|scientist)\b|\b(engineering manager|director|vice president|head of engineering)\b", title):
        return "senior-level role"
    text = (job.title + ". " + job.description).lower().replace("’", "'")
    text = re.sub(r"ph\.?\s*d\.?", "phd", text)
    if re.search(r"\b(ph\.?\s*d\.?|doctoral)\b", title):
        return "advanced degree in role title"
    # Check individual clauses; preferred/negated requirements and degree alternatives stay visible.
    for clause in re.split(r"[;\n.!?]", text):
        if re.search(r"\b(preferred|not required|no requirement)\b", clause):
            continue
        if not re.search(r"\b(bachelor|undergraduate|bs|bsc)\b", clause):
            if re.search(r"\b(phd|doctoral|mba|jd)\b.{0,25}\b(required|only)\b|\bmust\b.{0,50}\b(phd|doctoral|mba|jd)\b", clause):
                return "advanced degree required"
        if re.search(r"\b(?:[5-9]|[1-9][0-9])\+?\s+years?(?:\s+of)?\s+(?:professional\s+|industry\s+|work\s+)?experience", clause):
            return "5+ years experience"
    return None


def is_student_role(job, rules):
    if job.student_feed or matches(" ".join((job.title, job.employment_type)), rules["student_terms"]):
        return True
    # Generic mentions of interns (e.g. mentoring them) should not turn full-time roles into student jobs.
    return bool(re.search(r"\b(currently enrolled|currently pursuing|returning to school|pursuing (?:a |an )?(?:bachelor|undergraduate)|this internship)\b", job.description, re.I))
