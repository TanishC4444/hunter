from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def parse_date(value):
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc)
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


@dataclass
class Job:
    company: str
    title: str
    url: str
    source: str
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    employment_type: str = ""
    department: str = ""
    work_mode: str = ""
    student_feed: bool = False
    locations: list[str] = field(default_factory=list)
    sponsorship: str = ""
    location_check: str = ""
    f1_review: str = ""


@dataclass
class RankedJob:
    job: Job
    categories: list[str]
    score: int
    priority: str
    reasons: list[str]
