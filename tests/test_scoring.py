from datetime import datetime, timedelta, timezone

import pytest

from models import Job
from processing.classify import classify, exclusion
from processing.scoring import rank

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def job(title="Software Engineering Intern", **kwargs):
    return Job("Example", title, "https://example.com/jobs/1", "test", **kwargs)


def test_strong_match_and_explanations(rules):
    result = rank(job(description="Sophomore undergraduate", posted_at=NOW - timedelta(hours=2)), rules, now=NOW)
    assert result.score == 21
    assert result.priority == "🔥 Apply ASAP"
    assert any("sophomore" in reason for reason in result.reasons)


@pytest.mark.parametrize("title,category", [
    ("Frontend Intern", "SWE"), ("Applied AI Intern", "AI/ML"), ("Data Science Intern", "Data"),
    ("DevOps Intern", "Infra/Cloud"), ("Cybersecurity Intern", "Security"),
    ("Quant Research Intern", "Quant"), ("Product Management Intern", "PM/Product"),
    ("Firmware Co-op", "Hardware/Embedded"), ("Test Automation Intern", "QA/Automation"),
    ("Technology Summer Analyst", "Technical/Other"), ("Exploratory Program", "Technical/Other")])
def test_broad_coverage(rules, title, category):
    result = rank(job(title), rules, now=NOW)
    assert result is not None and category in result.categories


@pytest.mark.parametrize("description", ["PhD required", "doctoral candidates only", "Must be enrolled in a PhD program", "5+ years experience required"])
def test_hard_requirements(description):
    assert exclusion(job(description=description))


@pytest.mark.parametrize("description", ["Bachelor's, Master's, or PhD students", "PhD preferred", "PhD not required", "Junior preferred", "Master's preferred", "5 years experience preferred"])
def test_preferences_and_alternatives_survive(description, rules):
    assert rank(job(description=description), rules, now=NOW) is not None


def test_senior_title_and_regular_fulltime_excluded(rules):
    assert rank(job("Staff Engineer"), rules) is None
    assert rank(job("Software Engineer"), rules) is None
    assert rank(job("Software Engineer", description="Mentor interns and undergraduate colleagues"), rules) is None


@pytest.mark.parametrize("title,description", [("PhD Research Intern", ""), ("Research Intern", "Ph.D. required")])
def test_doctoral_only_roles(rules, title, description):
    assert rank(job(title, description=description), rules) is None


def test_word_boundaries(rules):
    assert "AI/ML" not in classify(job("Retail Intern"), rules)


@pytest.mark.parametrize("hours,bonus", [(0, 4), (23, 4), (24, 3), (71, 3), (72, 1), (167, 1), (168, 0), (-2, 0)])
def test_freshness_boundaries(rules, hours, bonus):
    assert rank(job(posted_at=NOW - timedelta(hours=hours)), rules, now=NOW).score == 10 + bonus


def test_preferences_only_lower_score(rules):
    assert rank(job(description="Junior preferred. Master's preferred."), rules).score == 6


def test_sheet_settings(rules):
    assert rank(job("Firmware Co-op"), rules, {"Include Co-ops": "FALSE"}) is None
    assert rank(job("Software Intern"), rules, {"Include SWE": "FALSE"}) is None
    assert rank(job(description="sophomore"), rules, {"Sophomore Bonus": "8"}).score == 18


def test_low_scores_kept_by_default(rules):
    candidate = job("Technology Summer Analyst", description="Junior preferred. Master's preferred.")
    assert rank(candidate, rules).score == 3
    assert rank(candidate, rules, {"Keep Low Scores": "FALSE"}) is None
