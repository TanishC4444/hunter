import requests


def notify(webhook_url, jobs, minimum_score=10):
    selected = [r for r in jobs if r.score >= minimum_score]
    if not webhook_url or not selected:
        return 0
    # A bounded digest prevents an initial backfill from flooding Discord.
    lines = [f"{len(selected)} new matching jobs. Top {min(8, len(selected))}:"]
    for ranked in selected[:8]:
        job = ranked.job
        lines.append(f"{ranked.score} | {job.company[:60]} — {job.title[:90]}\n{job.url[:250]}")
    response = requests.post(webhook_url, json={"content": "\n".join(lines)[:1950],
                             "allowed_mentions": {"parse": []}}, timeout=30)
    # Never include the webhook URL (a credential) in exception logs.
    if not response.ok:
        raise RuntimeError(f"Discord notification failed: HTTP {response.status_code}")
    return len(selected)
