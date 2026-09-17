from models import Job, parse_date
from sources.common import get_json, plain, slug


def normalize(records, company):
    jobs = []
    for row in records:
        if not row.get("text") or not row.get("hostedUrl"):
            continue
        categories = row.get("categories") or {}
        description = " ".join([row.get("descriptionPlain") or row.get("description") or "",
                                row.get("additionalPlain") or row.get("additional") or ""] +
                               [str(x.get("text", "")) + " " + str(x.get("content", "")) for x in row.get("lists", [])])
        jobs.append(Job(company=company, title=row["text"], url=row["hostedUrl"], source="Lever",
                        location=categories.get("location", ""), description=plain(description),
                        posted_at=parse_date(row.get("createdAt")),
                        employment_type=categories.get("commitment", ""),
                        department=categories.get("team", ""), work_mode=row.get("workplaceType", "")))
    return jobs


def fetch(client, identifier, company, region="global"):
    if region not in ("global", "eu"):
        raise ValueError("Lever region must be global or eu")
    host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
    url = f"https://{host}/v0/postings/{slug(identifier)}"
    result, seen = [], set()
    for skip in range(0, 100000, 100):
        page = get_json(client, url, mode="json", limit=100, skip=skip)
        if not isinstance(page, list):
            raise ValueError("Lever feed must be a JSON list")
        ids = {row.get("id") or row.get("hostedUrl") for row in page}
        if page and ids <= seen:
            raise ValueError("Lever repeated a page; refusing truncated scan")
        seen.update(ids)
        result.extend(normalize(page, company))
        if len(page) < 100:
            return result
    raise ValueError("Lever pagination limit exceeded")
