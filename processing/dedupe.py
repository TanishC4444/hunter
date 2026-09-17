from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"source", "ref", "referrer", "gh_src", "lever-source", "lever-origin", "fbclid", "gclid", "mc_cid", "mc_eid"}


def canonical_url(url):
    parts = urlsplit(str(url).strip())
    if parts.scheme.lower() not in ("https", "http") or not parts.netloc:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    host = parts.netloc.lower()
    if host == "boards.greenhouse.io":
        host = "job-boards.greenhouse.io"
    path = parts.path.rstrip("/")
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and path.endswith("/apply"):
        path = path[:-6]
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def dedupe(jobs):
    unique = {}
    for job in jobs:
        key = canonical_url(job.url)
        if not key:
            continue
        if key not in unique:
            unique[key] = job
        else:
            old = unique[key]
            if len(job.description) > len(old.description):
                old.description = job.description
            old.student_feed = old.student_feed or job.student_feed
            old.posted_at = old.posted_at or job.posted_at
            for field in ("employment_type", "department", "work_mode", "location"):
                if not getattr(old, field):
                    setattr(old, field, getattr(job, field))
    return list(unique.values())
