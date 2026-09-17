from models import Job, parse_date
from sources.common import get_json

DEFAULT_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"


def normalize(records):
    if not isinstance(records, list):
        raise ValueError("Pitt feed must be a JSON list")
    jobs = []
    for row in records:
        if row.get("active") is False or row.get("is_visible") is False:
            continue
        if not all(row.get(key) for key in ("company_name", "title", "url")):
            continue
        degrees = row.get("degrees") or []
        degree_text = " ".join(degrees)
        if degrees and all(value.lower().replace(".", "") in ("phd", "doctoral") for value in degrees):
            degree_text += " required"
        jobs.append(Job(company=row["company_name"], title=row["title"], url=row["url"],
                        source="Pitt/Simplify", location=", ".join(row.get("locations") or []),
                        posted_at=parse_date(row.get("date_posted")),
                        description=" ".join([row.get("description") or "", degree_text]), employment_type="Internship",
                        student_feed=True, locations=row.get("locations") or [],
                        sponsorship=row.get("sponsorship") or ""))
    return jobs


def fetch(client, url=DEFAULT_URL):
    return normalize(get_json(client, url))
