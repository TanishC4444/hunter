"""Read individual public ATS descriptions to improve authorization screening."""
from concurrent.futures import ThreadPoolExecutor
import logging
import re
from urllib.parse import parse_qs, urlsplit

from sources import greenhouse, lever
from sources.common import get_json, session

LOG = logging.getLogger("hunter")


def target(url):
    parts = urlsplit(url)
    path = parts.path.strip("/").split("/")
    if parts.hostname in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        if len(path) >= 3 and path[1] == "jobs":
            board, job_id = path[0], path[2]
        elif path[:1] == ["embed"]:
            query = parse_qs(parts.query)
            board, job_id = query.get("for", [""])[0], query.get("token", [""])[0]
        else:
            return None
        if re.fullmatch(r"[\w-]+", board) and job_id.isdigit():
            return "greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    if parts.hostname in ("jobs.lever.co", "jobs.eu.lever.co") and len(path) >= 2:
        board, job_id = path[:2]
        if re.fullmatch(r"[\w-]+", board) and re.fullmatch(r"[\w-]+", job_id):
            host = "api.eu.lever.co" if parts.hostname == "jobs.eu.lever.co" else "api.lever.co"
            return "lever", f"https://{host}/v0/postings/{board}/{job_id}"
    return None


def enrich_one(job):
    endpoint = target(job.url)
    if not endpoint:
        return job, False
    kind, url = endpoint
    try:
        with session() as client:
            payload = get_json(client, url, **({"mode": "json"} if kind == "lever" else {}))
        records = lever.normalize([payload], job.company) if kind == "lever" else greenhouse.normalize({"jobs": [payload]}, job.company)
        if records and records[0].description:
            job.description += "\n" + records[0].description
        return job, False
    except Exception:
        # Missing descriptions remain UNKNOWN; they must never become affirmative eligibility.
        return job, True


def enrich(jobs):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(enrich_one, jobs))
    failures = sum(failed for _, failed in results)
    LOG.info("ATS description checks: %d attempted, %d unavailable (marked for review)",
             sum(target(job.url) is not None for job in jobs), failures)
    return [job for job, _ in results]
