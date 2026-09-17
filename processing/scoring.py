from datetime import datetime, timezone

from models import RankedJob
from processing.classify import classify, exclusion, is_student_role, matches


def enabled(settings, key, default=True):
    value = settings.get(key, default)
    return str(value).lower() in ("true", "yes", "1")


def rank(job, rules, settings=None, now=None):
    settings = settings or {}
    now = now or datetime.now(timezone.utc)
    if exclusion(job):
        return None
    categories = classify(job, rules)
    student = is_student_role(job, rules)
    # Keep ambiguous student programs; a direct feed's ordinary full-time job is not an internship.
    if not student:
        return None
    categories = categories or ["Technical/Other"]
    categories = [c for c in categories if enabled(settings, "Include " + c)]
    if not categories:
        return None
    text = " ".join((job.title, job.description, job.employment_type))
    if matches(text, ["co-op", "coop", "co op"]) and not enabled(settings, "Include Co-ops"):
        return None
    reasons, score = [], 0

    def add(points, reason):
        nonlocal score
        score += points
        reasons.append(f"{points:+d} {reason}")

    role_points = max(rules["categories"][c]["weight"] for c in categories)
    add(role_points, "/".join(categories))
    add(5, "internship/student role")
    if matches(text, ["sophomore", "second-year", "second year", "underclassman", "underclassmen"]):
        add(int(settings.get("Sophomore Bonus", 4)), "sophomore/underclassman signal")
    if matches(text, ["undergraduate", "bachelor", "bachelor's", "bachelors"]):
        add(int(settings.get("Undergraduate Bonus", 3)), "undergraduate signal")
    if matches(text, ["junior preferred", "juniors preferred", "penultimate year"]):
        add(int(settings.get("Junior Preferred Penalty", -2)), "check class-year requirement")
    if matches(text, ["master's preferred", "masters preferred", "master’s preferred"]):
        add(-2, "master's preferred")
    if job.posted_at:
        hours = (now - job.posted_at).total_seconds() / 3600
        if 0 <= hours < 24:
            add(int(settings.get("Freshness Bonus <24h", 4)), "posted within 24h")
        elif 24 <= hours < 72:
            add(int(settings.get("Freshness Bonus <72h", 3)), "posted within 72h")
        elif 72 <= hours < 168:
            add(1, "posted within 7 days")
    if score < 6 and not enabled(settings, "Keep Low Scores"):
        return None
    priority = "🔥 Apply ASAP" if score >= 15 else "🟢 Good" if score >= 10 else "🟡 Inspect" if score >= 6 else "Low"
    return RankedJob(job, categories, score, priority, reasons)
