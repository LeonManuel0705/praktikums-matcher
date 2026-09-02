import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlparse

ALLOWED_COMPENSATION = {"paid", "unpaid", "unknown"}
ALLOWED_CATEGORIES = {"ai_tech", "business"}
ALLOWED_TARGET_GROUPS = {"schuelerpraktikum", "pflichtpraktikum", "allgemeines_praktikum", "unklar"}
ALLOWED_ELIGIBILITY = {"offen", "qualifikation_noetig", "unklar"}


@dataclass
class SearchContext:
    profile: dict
    log: Callable[[str, str], None]
    publish: Callable[[list[dict], str], list[dict]]
    cancelled: Callable[[], bool]


class SearchProvider(Protocol):
    name: str
    label: str

    def available(self) -> bool: ...

    async def run(self, ctx: SearchContext) -> None: ...


def clean_text(value, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref", "source"}


def canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    query = "&".join(
        part for part in parsed.query.split("&")
        if part and part.split("=")[0].lower() not in TRACKING_PARAMS
    )
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{host}{path}" + (f"?{query}" if query else "")


def normalize_offer(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    title = clean_text(raw.get("title"), 200)
    company = clean_text(raw.get("company"), 120)
    url = clean_text(raw.get("url"), 500)
    if not title or not company or not valid_url(url):
        return None

    categories = [c for c in (raw.get("categories") or []) if c in ALLOWED_CATEGORIES]
    compensation_kind = str(raw.get("compensation_kind") or "unknown").lower()
    target_group = str(raw.get("target_group") or "unklar").lower()

    return {
        "title": title,
        "company": company,
        "city": clean_text(raw.get("city"), 120) or "unbekannt",
        "compensation_kind": compensation_kind if compensation_kind in ALLOWED_COMPENSATION else "unknown",
        "compensation_text": clean_text(raw.get("compensation_text"), 160),
        "description": clean_text(raw.get("description"), 800),
        "url": url,
        "source": clean_text(raw.get("source"), 120) or (urlparse(url).netloc or ""),
        "start_date_hint": clean_text(raw.get("start_date_hint"), 120),
        "end_date_hint": clean_text(raw.get("end_date_hint"), 120),
        "duration_hint": clean_text(raw.get("duration_hint"), 120),
        "categories": categories,
        "target_group": target_group if target_group in ALLOWED_TARGET_GROUPS else "unklar",
        "eligibility": (str(raw.get("eligibility") or "").lower()
                        if str(raw.get("eligibility") or "").lower() in ALLOWED_ELIGIBILITY else ""),
        "evidence": clean_text(raw.get("evidence"), 400),
    }


OFFER_LINE = re.compile(r"^\s*OFFER:\s*(\{.*\})\s*$", re.MULTILINE)


def parse_offer_lines(text: str) -> list[dict]:
    offers = []
    for match in OFFER_LINE.finditer(text or ""):
        try:
            parsed = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        normalized = normalize_offer(parsed)
        if normalized:
            offers.append(normalized)
    return offers


def extract_json_payload(text: str) -> list[dict]:
    if not text:
        return []

    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidates = [block.strip() for block in fenced]
    candidates.append(text.strip())

    for depth_open, depth_close in (("[", "]"), ("{", "}")):
        start = text.find(depth_open)
        end = text.rfind(depth_close)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            for key in ("offers", "results", "items", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if "title" in parsed:
                return [parsed]
    return []
