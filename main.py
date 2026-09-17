from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import yaml

from integrations.notify import notify
from integrations.sheets import Sheets
from processing.dedupe import dedupe
from processing.scoring import enabled, rank
from sources import greenhouse, lever, pitt
from sources.common import session

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("hunter")


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def boards(local, sheet_rows):
    result = {}
    for item in local:
        item = dict(item)
        item["ats"] = item["ats"].lower()
        result[(item["ats"], item["identifier"])] = item
    for row in sheet_rows:
        ats = row.get("ATS", "").strip().lower()
        identifier = row.get("ATS Identifier", "").strip()
        if not identifier:
            if enabled(row, "Monitor Directly?", False):
                raise ValueError("Enabled company is missing ATS Identifier")
            continue
        result[(ats, identifier)] = {"ats": ats, "identifier": identifier,
                "company": row.get("Company") or identifier, "region": row.get("Region") or "global",
                "enabled": enabled(row, "Monitor Directly?", False)}
    active = [item for item in result.values() if enabled(item, "enabled")]
    for item in active:
        if item["ats"] not in ("greenhouse", "lever"):
            raise ValueError("Enabled company ATS must be Greenhouse or Lever")
    return active


def collect(client, company_boards, pitt_url):
    jobs, errors = [], []
    feeds = [("Pitt/Simplify", lambda: pitt.fetch(client, pitt_url))]
    for board in company_boards:
        def fetch_board(b=board):
            if b["ats"] == "lever":
                return lever.fetch(client, b["identifier"], b["company"], b.get("region", "global"))
            return greenhouse.fetch(client, b["identifier"], b["company"])
        feeds.append((board["ats"] + ":" + board["identifier"], fetch_board))
    for label, fetch in feeds:
        try:
            fetched = fetch()
            jobs.extend(fetched)
            LOG.info("%s: %d jobs", label, len(fetched))
        except Exception as error:
            # Public feed name and error class suffice; no credentials or full payloads in logs.
            errors.append(label)
            LOG.error("%s failed (%s)", label, type(error).__name__)
    if len(errors) == len(feeds):
        raise RuntimeError("All job feeds failed")
    return jobs, errors


def run(args):
    rules = read_yaml(ROOT / "config/keywords.yaml")
    local = read_yaml(args.companies).get("companies", [])
    settings, sheet_rows, sheets = {}, [], None
    if not args.dry_run:
        required = [name for name in ("SPREADSHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON") if not os.getenv(name)]
        if required:
            raise ValueError("Missing GitHub secrets/environment: " + ", ".join(required))
        sheets = Sheets(os.environ["SPREADSHEET_ID"], os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        settings, sheet_rows = sheets.settings(), sheets.companies()
    minimum_score = int(settings.get("Minimum Alert Score", 10))
    if int(settings.get("Poll Interval Hours", 2)) != 2:
        LOG.warning("Poll Interval Hours is informational; change the workflow cron to change cadence")
    jobs, errors = collect(session(), boards(local, sheet_rows), args.pitt_url)
    unique = dedupe(jobs)
    ranked = [result for job in unique if (result := rank(job, rules, settings)) is not None]
    ranked.sort(key=lambda result: result.score, reverse=True)
    LOG.info("Fetched=%d unique=%d eligible-for-review=%d", len(jobs), len(unique), len(ranked))
    if args.dry_run:
        print(json.dumps({"fetched": len(jobs), "unique": len(unique), "ranked": len(ranked),
                          "source_failures": errors, "preview": [
                              {"company": r.job.company, "role": r.job.title, "score": r.score,
                               "priority": r.priority, "reasons": r.reasons, "url": r.job.url}
                              for r in ranked[:10]]}, indent=2))
    else:
        added = sheets.append_new(ranked)
        LOG.info("Appended %d new jobs; existing application rows preserved", len(added))
        if os.getenv("DISCORD_WEBHOOK_URL"):
            try:
                notify(os.environ["DISCORD_WEBHOOK_URL"], added, minimum_score)
            except Exception as error:
                LOG.error("Notification failed (%s). Sheet rows are saved; alerts are not retried.", type(error).__name__)
                return 1
    # Healthy feeds can sync, but a partial source failure must remain visible in Actions.
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description="Discover sophomore-relevant tech opportunities")
    parser.add_argument("--dry-run", action="store_true", help="Public feeds only; no Sheets or alerts")
    parser.add_argument("--companies", default=str(ROOT / "config/companies.yaml"))
    parser.add_argument("--pitt-url", default=os.getenv("PITT_LISTINGS_URL", pitt.DEFAULT_URL))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return run(args)
    except Exception as error:
        LOG.error("Run failed (%s). Check configuration, credentials and source availability.", type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
