"""Conservative location screening and evidence-based F-1 review labels.

These are posting-level filters, not a determination of an individual's CPT/OPT eligibility.
Unknown authorization is labeled for review; only explicit employer restrictions exclude it.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import urlsplit

import yaml

from processing.scoring import enabled

STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
STATE_NAMES = "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia"
US_ALIASES = {"nyc", "sf", "south sf", "la", "new york city", "san francisco", "los angeles", "washington dc", "washington d.c."}
FOREIGN = re.compile(r"\b(?:Canada|United Kingdom|UK|England|Scotland|Wales|Ireland|India|China|Singapore|Australia|Germany|France|Netherlands|Switzerland|Spain|Poland|Sweden|Denmark|Norway|Finland|Japan|Korea|Taiwan|Hong Kong|Israel|Brazil|Mexico|New Zealand|Portugal|Italy|Belgium|Austria|Romania|Hungary|Czechia|Czech Republic|Malaysia|Philippines|Indonesia|Vietnam|Thailand|UAE|United Arab Emirates|Saudi Arabia|Turkey|Türkiye|South Africa|Argentina|Chile|Colombia|Costa Rica|Luxembourg|Pakistan|Bangladesh|Egypt|Kenya|Nigeria|Europe|EMEA|APAC|LATAM)\b", re.I)


@lru_cache(maxsize=1)
def excluded_names():
    return yaml.safe_load((Path(__file__).parents[1] / "config/excluded_employers.yaml").read_text())["names"]


def defense_government(job):
    company = " " + re.sub(r"[^a-z0-9]+", " ", job.company.lower()).strip() + " "
    for name in excluded_names():
        if " " + name.lower() + " " in company:
            return "Excluded: defense/government employer preference (" + name + ")"
    if re.search(r"\b(defense|defence|national laborator(?:y|ies)|department of (?:the )?(?:army|navy|air force))\b", company):
        return "Excluded: defense/government employer preference"
    host = urlsplit(job.url).hostname or ""
    if host.endswith((".gov", ".mil")):
        return "Excluded: government job site"
    if re.search(r"\b(defense|defence|military|federal government|government affairs)\b", job.title, re.I):
        return "Excluded: defense/government role preference"
    return None


def us_location(value):
    value = str(value).strip()
    if not value:
        return False
    if value.lower() in US_ALIASES:
        return True
    # Require a location-shaped state code rather than matching words such as 'in' or 'or'.
    # A terminal US state also disambiguates cities such as North Wales, PA and Mexico, MO.
    if re.search(r"(?:,\s*|\s+-\s+)(?:" + "|".join(sorted(STATES)) + r")(?:\s+\d{5}(?:-\d{4})?)?(?:\s*\([^)]*\))?$", value):
        return True
    if value.lower() in {name.lower() for name in STATE_NAMES.split("|")} - {"georgia"}:
        return True
    if FOREIGN.search(value):
        return False
    if re.search(r"\b(?:United States(?: of America)?|USA|U\.S\.A\.?|US|U\.S\.)\b", value, re.I):
        return True
    # Named states are accepted when disambiguated by a city or remote prefix.
    return bool(re.search(r"(?:,\s*|remote(?: in)?\s+)(?:" + STATE_NAMES + r")$", value, re.I))


def authorization(job):
    source = job.sponsorship.strip().lower()
    if source == "u.s. citizenship is required":
        return "excluded", "Excluded: source requires U.S. citizenship"
    text = (job.title + ". " + job.description).lower().replace("’", "'")
    text = re.sub(r"\bu\.?s\.?(?!\w)", "us", text)
    restricted = [
        r"\b(?:must|shall|need to)\s+(?:be|hold)\s+(?:an?\s+)?(?:us|united states)\s+(?:citizen|person)",
        r"\b(?:us|united states)\s+(?:citizenship|person status)\s+(?:is\s+)?required",
        r"\b(?:us|united states)\s+citizens?\s+only\b",
        r"\b(?:citizens?|permanent residents?)\s+only\b",
        r"\bmust\s+be\s+(?:an?\s+)?(?:lawful\s+)?permanent resident\b",
        r"\b(?:no|not eligible for|cannot (?:accept|hire)|do not (?:accept|hire))\s+(?:students (?:on|using)\s+)?(?:f-?1|cpt|opt|international students)\b",
        r"\b(?:f-?1|cpt|opt|international students)(?:\s*(?:/|or|and)\s*(?:cpt|opt))?(?:\s+(?:students|candidates|applicants))?\s+(?:are\s+|is\s+)?(?:not (?:accepted|eligible|supported)|ineligible)\b",
        r"\b(?:without|not (?:require|requiring|need))\b[^.;]{0,80}\bsponsorship\b[^.;]{0,50}\b(?:now or in the future|now or in future|now or at any time in the future|currently or in the future)\b",
    ]
    for clause in re.split(r"[;\n]", text):
        if re.search(r"citizenship (?:is )?not required|do not need to be (?:a )?us citizen", clause):
            continue
        for pattern in restricted:
            match = re.search(pattern, clause)
            if match:
                following = clause[match.start():match.end()+500]
                if re.search(r"\bor\s+(?:be\s+)?eligible to obtain\s+(?:the\s+)?(?:required|necessary)\s+(?:export\s+)?authorizations?", following):
                    # Some export-control clauses explicitly allow a license/authorization alternative.
                    return "unknown", "Review: export authorization alternative; confirm F-1/CPT acceptance"
                return "excluded", "Excluded: " + match.group(0)
    positive = [
        r"\b(?:accept|accepts|welcome|welcomes|support|supports)\s+(?:students (?:on|using)\s+)?(?:f-?1|cpt|opt|international students)\b",
        r"\b(?:f-?1|cpt|opt)(?:\s*(?:/|or|and)\s*(?:cpt|opt))?(?:\s+(?:students|candidates|applicants))?\s+(?:are\s+|is\s+)?(?:eligible|accepted|welcome|supported)\b",
    ]
    for pattern in positive:
        match = re.search(pattern, text)
        if match and not re.search(r"\b(?:not|cannot|don't|doesn't|do not|does not)\s*$", text[max(0, match.start()-15):match.start()]):
            return "explicit", "Explicit student-work authorization signal; confirm your CPT/OPT with employer and DSO"
    if source == "does not offer sponsorship" or re.search(r"\b(?:no|without|not offer|not provide)\b[^.;]{0,25}\bsponsorship\b", text):
        return "unknown", "Review: no sponsorship stated; CPT/OPT acceptance unconfirmed"
    if source == "offers sponsorship":
        return "unknown", "Review: sponsorship offered; CPT/OPT acceptance unconfirmed"
    return "unknown", "Review: CPT/OPT acceptance not stated"


@dataclass
class Screening:
    keep: bool
    us_locations: list[str]
    location_check: str
    f1_review: str


def screen(job, settings=None):
    settings = settings or {}
    places = job.locations or [job.location]
    us_places = [place for place in places if us_location(place)]
    location_ok = bool(us_places)
    kind, review = authorization(job)
    employer_reason = defense_government(job) if enabled(settings, "Exclude Defense/Government") else None
    if employer_reason:
        kind, review = "excluded", employer_reason
    strict = enabled(settings, "Require Explicit CPT/OPT", False)
    allowed = kind != "excluded" and (not strict or kind == "explicit")
    if strict and kind == "unknown":
        review = "Excluded from strict view: " + review
    location_check = "U.S. location available" if location_ok else "Excluded: no confirmed U.S. location"
    keep = not employer_reason and (location_ok or not enabled(settings, "U.S. Locations Only")) and (allowed or not enabled(settings, "F-1 Screening"))
    return Screening(keep, us_places, location_check, review)


def filter_jobs(jobs, settings=None):
    result = []
    for job in jobs:
        check = screen(job, settings)
        if not check.keep:
            continue
        job.location_check, job.f1_review = check.location_check, check.f1_review
        if enabled(settings or {}, "U.S. Locations Only"):
            job.locations = check.us_locations
            job.location = ", ".join(check.us_locations)
        result.append(job)
    return result
