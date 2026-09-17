import pytest

from models import Job
from processing.eligibility import authorization, filter_jobs, screen, us_location
from sources.details import target


def job(location="Austin, TX", description="", **kwargs):
    return Job("Example", "Software Intern", "https://example.com/1", "test",
               location=location, description=description, **kwargs)


@pytest.mark.parametrize("location", ["Austin, TX", "NYC", "SF", "South SF", "LA", "United States", "Remote in USA", "Boston, Massachusetts", "Seattle, WA (Hybrid)", "North Wales, PA", "New Mexico", "California", "Mexico, MO"])
def test_us_locations(location):
    assert us_location(location)


@pytest.mark.parametrize("location", ["Toronto, ON, Canada", "London, UK", "Cambridge, UK", "Vancouver, WA, Canada", "Remote", "", "London", "Remote in Canada", "San Jose, Costa Rica", "California, Spain"])
def test_international_and_unknown_locations(location):
    assert not us_location(location)


def test_multi_location_keeps_only_us_options():
    candidate = job(locations=["Toronto, ON, Canada", "Austin, TX"])
    assert filter_jobs([candidate])[0].location == "Austin, TX"


@pytest.mark.parametrize("description", ["Must be a US citizen", "U.S. citizenship is required", "Must be a U.S. person under ITAR", "Permanent residents only", "No CPT or OPT", "CPT/OPT candidates are not eligible", "Cannot hire international students", "Must work without sponsorship now or in the future"])
def test_explicit_restrictions(description):
    assert not screen(job(description=description)).keep


def test_structured_citizenship_requirement():
    assert not screen(job(sponsorship="U.S. Citizenship is Required")).keep


@pytest.mark.parametrize("description", ["No sponsorship is available", "We comply with ITAR", "US citizenship is not required", "We do not need to be a US citizen"])
def test_ambiguous_statements_not_false_exclusions(description):
    assert screen(job(description=description)).keep


def test_no_sponsorship_is_not_cpt_rejection():
    candidate = job(sponsorship="Does Not Offer Sponsorship")
    assert screen(candidate).keep
    assert "unconfirmed" in screen(candidate).f1_review
    assert not screen(candidate, {"Require Explicit CPT/OPT": True}).keep


@pytest.mark.parametrize("description", ["We accept CPT students", "CPT/OPT candidates are eligible", "F-1 students are welcome"])
def test_explicit_acceptance(description):
    assert screen(job(description=description), {"Require Explicit CPT/OPT": True}).keep


def test_negated_acceptance():
    assert authorization(job(description="We do not accept CPT students"))[0] == "excluded"


def test_export_authorization_alternative_needs_review():
    text = "Applicant must be a U.S. citizen, permanent resident, or eligible to obtain the required authorizations from the U.S. Department of State."
    assert authorization(job(description=text))[0] == "unknown"
    assert screen(job(description=text)).keep


def test_supported_detail_urls_only():
    assert target("https://job-boards.greenhouse.io/example/jobs/123")[1].endswith("/example/jobs/123")
    assert target("https://boards.greenhouse.io/embed/job_app?for=example&token=123")[1].endswith("/example/jobs/123")
    assert target("https://jobs.lever.co/example/abc/apply")[1].endswith("/example/abc")
    assert target("https://evil.example/example/jobs/123") is None


@pytest.mark.parametrize("company", ["RTX", "Raytheon Technologies", "Lockheed Martin", "Northrop Grumman", "Pratt & Whitney", "Boeing", "General Dynamics Information Technology", "Space Dynamics Laboratory", "Lawrence Livermore National Laboratory (LLNL)"])
def test_defense_government_company_preference(company):
    candidate = job(description="We accept CPT students")
    candidate.company = company
    assert not screen(candidate).keep
    assert "defense/government" in screen(candidate).f1_review


@pytest.mark.parametrize("company", ["Sierra", "Huntington Bancshares", "Navy Federal", "BlueCross BlueShield of Nebraska", "University of Arkansas", "NVIDIA"])
def test_do_not_exclude_unrelated_name_fragments(company):
    candidate=job()
    candidate.company=company
    assert screen(candidate).keep
