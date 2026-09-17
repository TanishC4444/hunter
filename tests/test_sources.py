from datetime import timezone
from unittest.mock import Mock

from models import parse_date
from sources import greenhouse, lever, pitt


def test_pitt_closed_hidden_and_degree_fields():
    base = {"company_name": "Example", "title": "Intern", "url": "https://example.com/job/1", "date_posted": 1700000000,
            "locations": ["Austin", "Remote"], "degrees": ["Bachelor's"]}
    result = pitt.normalize([base, {**base, "active": False}, {**base, "is_visible": False}, {}])
    assert len(result) == 1
    assert result[0].posted_at.tzinfo == timezone.utc
    assert result[0].location == "Austin, Remote"
    assert "Bachelor" in result[0].description


def test_lever_normalizes_html_lists_and_milliseconds():
    result = lever.normalize([{"text": "ML Intern", "hostedUrl": "https://jobs.lever.co/example/1",
        "createdAt": 1700000000000, "categories": {"commitment": "Intern", "location": "Austin"},
        "lists": [{"text": "Requirements", "content": "<li>Undergraduate &amp; sophomore</li>"}]}], "Example")[0]
    assert "Undergraduate & sophomore" in result.description
    assert "<li>" not in result.description
    assert result.posted_at == parse_date(1700000000)


def test_greenhouse_does_not_use_update_time_as_posting_date():
    job = greenhouse.normalize({"jobs": [{"title": "Intern", "absolute_url": "https://example.com/job/1",
        "content": "&lt;p&gt;Bachelor's&lt;/p&gt;", "updated_at": "2026-09-17T00:00:00Z"}]}, "Example")[0]
    assert job.posted_at is None
    assert job.description == "Bachelor's"


def test_lever_pagination(monkeypatch):
    page = [{"id": str(i), "text": "Intern", "hostedUrl": f"https://jobs.lever.co/example/{i}"} for i in range(100)]
    fake = Mock(side_effect=[page, []])
    monkeypatch.setattr(lever, "get_json", fake)
    assert len(lever.fetch(None, "example", "Example")) == 100
    assert fake.call_args_list[1].kwargs["skip"] == 100


def test_bad_dates_are_unknown():
    assert parse_date("bad") is None
    assert parse_date(None) is None
