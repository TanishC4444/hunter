from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from integrations.connections import searches
from processing.dedupe import canonical_url

HEADERS = ["Company", "Role", "Location", "Work Mode", "Employment Type", "Department", "Status",
           "Posting Date", "Applied Date", "Source / Job Link", "Contact", "Relationship",
           "Referral / Direct Consideration", "Last Contact", "Next Action", "Follow-up Date", "Notes",
           "Category", "Score", "Priority", "First Seen", "Match Reasons", "Connection Search",
           "Location Check", "F-1 Review", "Show Job"]
REQUIRED = {"Company", "Role", "Source / Job Link", "Category", "Score", "Priority", "First Seen", "Match Reasons", "Connection Search"}


def column_name(number):
    result = ""
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result


def record(ranked, now=None):
    job = ranked.job
    return {"Company": job.company, "Role": job.title, "Location": job.location,
            "Work Mode": job.work_mode, "Employment Type": job.employment_type,
            "Department": job.department, "Status": "Not Applied",
            "Posting Date": job.posted_at.date().isoformat() if job.posted_at else "",
            "Source / Job Link": job.url, "Notes": "Source: " + job.source,
            "Category": ", ".join(ranked.categories), "Score": ranked.score,
            "Priority": ranked.priority, "First Seen": (now or datetime.now(timezone.utc)).isoformat(),
            "Match Reasons": "; ".join(ranked.reasons), "Connection Search": searches(job.company)["alumni"],
            "Location Check": job.location_check, "F-1 Review": job.f1_review, "Show Job": "Show"}


def prepare_append(existing, ranked_jobs):
    if not existing:
        raise ValueError("Applications needs a header row; see README")
    headers = existing[0]
    if len(headers) != len(set(headers)) or not REQUIRED <= set(headers):
        raise ValueError("Applications has missing or duplicate required columns; refusing to write")
    url_col = headers.index("Source / Job Link")
    seen = {canonical_url(row[url_col]) for row in existing[1:] if len(row) > url_col}
    rows, added = [], []
    for ranked in ranked_jobs:
        key = canonical_url(ranked.job.url)
        if not key or key in seen:
            continue
        values = record(ranked)
        rows.append([values.get(header, "") for header in headers])
        added.append(ranked)
        seen.add(key)
    return rows, added


class Sheets:
    def __init__(self, spreadsheet_id, credentials_json):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials
        if not re.fullmatch(r"[A-Za-z0-9_-]+", spreadsheet_id):
            raise ValueError("Invalid SPREADSHEET_ID")
        credentials = Credentials.from_service_account_info(json.loads(credentials_json),
                      scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.client = AuthorizedSession(credentials)
        self.base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"

    def read(self, range_name):
        response = self.client.get(self.base + "/values/" + quote(range_name, safe=""), timeout=45)
        response.raise_for_status()
        return response.json().get("values", [])

    def settings(self):
        rows = self.read("'Settings'!A1:C200")
        if not rows or rows[0][:2] != ["Setting", "Value"]:
            raise ValueError("Settings headers must begin Setting, Value")
        return {row[0]: row[1] for row in rows[1:] if len(row) >= 2}

    def companies(self):
        rows = self.read("'Companies'!A1:J10000")
        if not rows or not {"Company", "ATS", "ATS Identifier", "Monitor Directly?"} <= set(rows[0]):
            raise ValueError("Companies headers do not match the README schema")
        if len(rows) == 10000:
            raise ValueError("Companies range is full; raise the configured read limit")
        return [dict(zip(rows[0], row)) for row in rows[1:]]

    def known_urls(self):
        rows = self.read("'Applications'!A:AZ")
        if not rows or "Source / Job Link" not in rows[0]:
            raise ValueError("Applications is missing Source / Job Link")
        index = rows[0].index("Source / Job Link")
        return {canonical_url(row[index]) for row in rows[1:] if len(row) > index}

    def append_new(self, ranked_jobs):
        # Read only current job-link values (default FORMATTED_VALUE), including manual additions.
        existing = self.read("'Applications'!A:AZ")
        rows, added = prepare_append(existing, ranked_jobs)
        if not rows:
            return []
        last = column_name(len(existing[0]))
        url = self.base + "/values/" + quote(f"'Applications'!A:{last}", safe="") + ":append"
        # Do not retry an append: a timeout may mean it already committed. Next run deduplicates.
        response = self.client.post(url, params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                                    json={"majorDimension": "ROWS", "values": rows}, timeout=60)
        response.raise_for_status()
        return added
