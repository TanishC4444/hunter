# Sophomore Job Hunter

Find broadly relevant tech internships, co-ops and student programs, rank them with explainable scores, and append only new opportunities to a Google Sheets recruiting tracker. Applications and outreach remain manual.

This implementation reconstructs the Sophomore Job Hunter design from the referenced conversation; the original downloadable archive was not available during repository setup.

## What runs

1. Read the structured [Pitt/Simplify internship feed](https://github.com/SimplifyJobs/Summer2027-Internships), currently the Summer 2027 repository's `dev/.github/scripts/listings.json`.
2. Read selected companies through the public [Lever Postings API](https://github.com/lever/postings-api) and [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html).
3. Normalize dates, descriptions and URLs; merge duplicate URLs across sources.
4. Keep plausible student opportunities across SWE, AI/ML, data, infrastructure/cloud, security, quant, product, hardware/embedded, QA/automation, and other technical programs.
5. Rank jobs, preserving ambiguous/low-scoring opportunities by default. Remove explicit senior roles, required advanced degrees without undergraduate alternatives, and substantial experience requirements.
6. Compare with the Applications sheet, including manually added job links, then append only unseen URLs. Existing statuses, notes, contacts and application history are never rewritten.
7. Optionally send a bounded Discord digest for new jobs above the configured threshold.

The Sheet is the database. No SQLite file or persistent GitHub runner storage is required.

## Quick start

Use Python 3.12 (the version used by GitHub Actions):

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python main.py --dry-run
python -m integrations.connections "NVIDIA"
```

`--dry-run` fetches public feeds and prints aggregate counts plus the top ten results. It does not read or write Google Sheets or send alerts. It uses only `config/companies.yaml` for direct company boards. Normal runs also read the Companies and Settings tabs.

## Activate Google Sheets sync

1. In your Google Cloud project, enable the **Google Sheets API**.
2. Create a service account and a JSON key. Share your existing recruiting spreadsheet with the key's `client_email` as **Editor**. Do not commit the key or paste it into an issue.
3. In this repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
| --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Entire service-account JSON key |
| `SPREADSHEET_ID` | ID between `/d/` and `/edit` in your tracker URL |
| `DISCORD_WEBHOOK_URL` | Optional Discord webhook for new-job digests |

4. Open **Actions → Find sophomore tech jobs → Run workflow**. Leave **dry_run** checked for a public-feed preview. Uncheck it to sync the tracker.

The two-hour schedule is already defined as `0 */2 * * *` in `.github/workflows/jobs.yml`, on the default branch. It runs at even UTC hours. Pushes and pull requests run tests only; scheduled and manual scans first require tests to pass. The schedule needs the two required secrets for successful Sheets sync. Missing credentials produce an explicit failed run, rather than pretending synchronization succeeded.

GitHub scheduling is best effort and may be delayed. GitHub may disable scheduled workflows in public repositories after 60 days without activity. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). The sheet's Poll Interval Hours entry is informational; changing it does not edit the workflow cron.

For a local live run, set the same environment variables and run `python main.py`. Avoid overlapping local runs with GitHub Actions; the workflow serializes its own runs, but Sheets does not provide a cross-client transaction lock.

## Existing tracker schema

The existing Applications / Connections / Companies / Settings structure is supported. No tabs are recreated. A schema mismatch stops writes. For a new tracker, create these tabs and copy the headers below into their first rows.

### Applications

```text
Company	Role	Location	Work Mode	Employment Type	Department	Status	Posting Date	Applied Date	Source / Job Link	Contact	Relationship	Referral / Direct Consideration	Last Contact	Next Action	Follow-up Date	Notes	Category	Score	Priority	First Seen	Match Reasons	Connection Search
```

Column order can change; the sync maps by header. Extra columns receive blank values on new rows. New jobs start with `Not Applied`; manual fields remain blank. Writes use RAW values so source text cannot become a spreadsheet formula. Unknown posting dates remain blank; First Seen records discovery time separately.

### Connections

Keep your existing columns for people, company, relationship, outreach dates, replies and referral status. The bot does not scrape LinkedIn, harvest profiles, send messages, or alter this tab. Each new job gets a UT Austin alumni search link. For additional links:

```sh
python -m integrations.connections "Example Company"
python -m integrations.connections "Example Company" --school "Another University"
```

This outputs search links for alumni, former interns, engineers and recruiters. Choose people manually and track outreach in Connections.

### Companies

```text
Company	Priority	ATS	ATS Identifier	Monitor Directly?	Careers URL	Notes
```

Set **ATS** to `Lever` or `Greenhouse`, **ATS Identifier** to the board slug from the company's careers URL, and **Monitor Directly?** to `TRUE`. For `jobs.lever.co/example`, use `example`; for `job-boards.greenhouse.io/example`, use `example`. Optional `Region` column: `eu` for Lever's EU instance, otherwise `global`. Priority/Careers URL/Notes are informational.

The initial Companies sheet contains a disabled placeholder and the local configuration contains no enabled boards. Pitt/Simplify works immediately; direct Lever/Greenhouse monitoring starts after you select companies. Do not enable the placeholder.

You can also configure local boards in `config/companies.yaml`:

```yaml
companies:
  - company: Example Company
    ats: lever
    identifier: replace-with-real-board-slug
    enabled: false
    region: global
```

The Sheet overrides matching local ATS+identifier entries, including disabling them. An enabled company with an invalid ATS or identifier fails visibly.

### Settings

Use columns `Setting`, `Value`, `Meaning`. The following keys match the existing tracker:

| Setting | Default |
| --- | --- |
| Minimum Alert Score | 10 |
| Poll Interval Hours | 2 (informational) |
| Include SWE / AI/ML / Data / Infra/Cloud / Security / Quant / PM/Product / Hardware/Embedded / QA/Automation / Technical/Other | TRUE for each separate `Include <category>` key |
| Include Co-ops | TRUE |
| Keep Low Scores | TRUE |
| Freshness Bonus <24h | 4 |
| Freshness Bonus <72h | 3 |
| Sophomore Bonus | 4 |
| Undergraduate Bonus | 3 |
| Junior Preferred Penalty | -2 |

Edit category terms and weights in `config/keywords.yaml`. Word boundaries prevent `AI` from matching unrelated words like `retail`. Multiple category matches use the highest category weight, not an inflated sum.

## Scoring and limits

- Role match: +5 SWE/AI, +4 data/infra/security/quant/hardware, +3 QA, +2 product/other.
- Internship/student signal: +5. Explicit sophomore/underclassman: +4. Undergraduate: +3.
- Posting freshness: +4 under 24 hours, +3 under 72 hours, +1 under 7 days. Future dates and unknown dates get no bonus. Greenhouse `updated_at` is never treated as a posting date.
- Junior/penultimate-year preference: -2. Master's preference: -2.
- Priorities: **15+ Apply ASAP**, **10–14 Good**, **6–9 Inspect**, **below 6 Low**.

Scores are review priorities, not eligibility guarantees. Graduation-year windows, sponsorship, citizenship, location, degree requirements and application questions need manual review. No fixed graduation year or work authorization is assumed. Job descriptions and structured feeds can be incomplete or stale; a job remaining active upstream may already have closed. Direct full-time listings without a student signal are excluded. Broad student programs can survive under Technical/Other even without a recognized technical title.

URL deduplication removes known tracking parameters and preserves job IDs in query strings. Different URLs for the same job can still create duplicates. Existing rows are not rescored, marked closed, or deleted. A deleted row can be discovered again on a future run.

## Reliability and troubleshooting

- Public feed reads retry transient failures and have timeouts. Lever is paginated.
- If one source fails, healthy sources still sync, but the run ends as failed so coverage loss is visible. If every source fails, no rows are written.
- Append requests are not blindly retried after an ambiguous timeout; the next run rereads the Sheet to avoid duplicate rows.
- Notification failures do not undo saved rows. Alerts are best effort and are not replayed on the next run; use the tracker as the source of truth. The first successful run can backfill many active postings; Discord sends a top-eight digest, not one message per job.
- A missing tab, renamed required header, invalid numeric setting, incorrect key, disabled Sheets API or missing Editor share can stop sync. Inspect Actions logs and recheck configuration; secrets and full error payloads are not printed.
- To switch seasons, set `PITT_LISTINGS_URL` locally or edit `sources/pitt.py`/the workflow environment after verifying the new structured-feed URL.

## Verification

`python -m pytest -q` covers all source normalizers, Lever pagination, freshness boundaries, broad categories, narrow exclusions, preferences, settings, cross-source deduplication, sheet column mapping, repeat-run idempotence, RAW writes, connection-search encoding, partial/all-source failures, and workflow schedule/permissions/secret isolation. These tests mock external writes and do not require credentials.

The workflow uses a read-only GitHub token. Only the sync step receives Google/Discord secrets. No application submission, LinkedIn scraping, or automatic outreach is included.
