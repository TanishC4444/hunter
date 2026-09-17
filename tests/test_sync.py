from copy import deepcopy
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from integrations.connections import searches
from integrations.sheets import HEADERS, Sheets, prepare_append
from main import boards, collect
from models import Job, RankedJob
from processing.dedupe import canonical_url, dedupe


def ranked(url="https://example.com/jobs?id=2", title="Intern"):
    return RankedJob(Job("Example", title, url, "test"), ["SWE"], 10, "🟢 Good", ["+5 SWE"])


def test_dedupe_retains_job_ids_and_removes_tracking():
    assert canonical_url("https://EXAMPLE.com/jobs/?id=1&utm_source=x#apply") == "https://example.com/jobs?id=1"
    assert canonical_url("https://example.com/jobs?id=1") != canonical_url("https://example.com/jobs?id=2")
    assert canonical_url("https://jobs.lever.co/a/b/apply") == canonical_url("https://jobs.lever.co/a/b")
    assert canonical_url("https://boards.greenhouse.io/a/jobs/1") == canonical_url("https://job-boards.greenhouse.io/a/jobs/1")
    assert canonical_url("javascript:alert(1)") == ""


def test_duplicate_enrichment():
    a = ranked().job
    a.student_feed = True
    b = ranked().job
    b.description = "Undergraduate"
    result = dedupe([a, b])
    assert len(result) == 1 and result[0].description == "Undergraduate" and result[0].student_feed


def test_sync_maps_reordered_columns_and_preserves_manual_fields():
    headers = list(reversed(HEADERS))
    manual = [""] * len(headers)
    manual[headers.index("Source / Job Link")] = "https://example.com/jobs?id=1&utm_source=test"
    manual[headers.index("Status")] = "Interview"
    manual[headers.index("Notes")] = "My private notes"
    existing = [headers, manual]
    original = deepcopy(existing)
    rows, added = prepare_append(existing, [ranked("https://example.com/jobs?id=1"), ranked(), ranked()])
    assert existing == original
    assert len(rows) == len(added) == 1
    assert rows[0][headers.index("Role")] == "Intern"
    assert rows[0][headers.index("Contact")] == ""
    assert prepare_append(existing + rows, [ranked()]) == ([], [])


def test_bad_sheet_schema_stops_writes():
    with pytest.raises(ValueError):
        prepare_append([["Company", "Role"]], [ranked()])


def test_append_uses_raw_values_not_formulas():
    sheet = Sheets.__new__(Sheets)
    sheet.base = "https://sheets.googleapis.com/v4/spreadsheets/example"
    sheet.read = Mock(return_value=[HEADERS])
    sheet.client = Mock()
    sheet.append_new([ranked(title='=IMPORTXML("https://example.com","//x")')])
    call = sheet.client.post.call_args
    assert call.kwargs["params"]["valueInputOption"] == "RAW"
    assert call.kwargs["json"]["values"][0][1].startswith("=IMPORTXML")
    assert sheet.client.post.call_count == 1


def test_sheet_can_disable_local_board():
    local = [{"ats": "Lever", "identifier": "example", "company": "Example"}]
    rows = [{"ATS": "Lever", "ATS Identifier": "example", "Monitor Directly?": "FALSE"}]
    assert boards(local, rows) == []
    assert boards(local, [])[0]["ats"] == "lever"


def test_partial_source_failure_is_visible(monkeypatch):
    monkeypatch.setattr("main.pitt.fetch", Mock(return_value=[ranked().job]))
    monkeypatch.setattr("main.lever.fetch", Mock(side_effect=RuntimeError("offline")))
    jobs, errors = collect(None, [{"ats": "lever", "identifier": "example", "company": "Example"}], "unused")
    assert len(jobs) == 1 and errors == ["lever:example"]


def test_all_sources_failed(monkeypatch):
    monkeypatch.setattr("main.pitt.fetch", Mock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError, match="All job feeds"):
        collect(None, [], "unused")


def test_connection_searches():
    result = searches("Example & Co")
    query = parse_qs(urlsplit(result["alumni"]).query)["q"][0]
    assert '"Example & Co"' in query and '"University of Texas at Austin"' in query
    assert set(result) == {"alumni", "former_interns", "engineers", "recruiters"}
