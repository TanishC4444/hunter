import html
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session():
    client = requests.Session()
    client.headers.update({"User-Agent": "SophomoreJobHunter/1.0", "Accept": "application/json"})
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    client.mount("https://", HTTPAdapter(max_retries=retry))
    return client


def get_json(client, url, **params):
    response = client.get(url, params=params, timeout=(10, 45))
    response.raise_for_status()
    return response.json()


def plain(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def slug(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("ATS Identifier must be a board slug, not a URL")
    return value
