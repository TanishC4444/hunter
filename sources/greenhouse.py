from models import Job, parse_date
from sources.common import get_json, plain, slug


def normalize(payload, company):
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Greenhouse feed must contain a jobs list")
    return [Job(company=company, title=row["title"], url=row["absolute_url"], source="Greenhouse",
                location=(row.get("location") or {}).get("name", ""),
                description=plain(row.get("content", "")),
                # updated_at is an edit time, not a posting date. Never award freshness for it.
                posted_at=parse_date(row.get("first_published")),
                department=", ".join(x["name"] for x in row.get("departments", [])))
            for row in payload["jobs"] if row.get("title") and row.get("absolute_url")]


def fetch(client, identifier, company):
    return normalize(get_json(client, f"https://boards-api.greenhouse.io/v1/boards/{slug(identifier)}/jobs", content="true"), company)
