import re
from dataclasses import dataclass, field
from datetime import date

from .config import WEIGHTS
from .dateparse import overlap_ratio, parse_window
from .geo import distance_between, geocode, is_remote, normalize

STOPWORDS = {
    "und", "oder", "der", "die", "das", "ein", "eine", "einen", "einem", "eines", "mit", "fuer", "von", "bei", "im",
    "in", "am", "an", "auf", "zu", "zur", "zum", "ich", "mir", "mich", "moechte", "will", "gerne", "gern", "etwas",
    "was", "machen", "arbeiten", "lernen", "wuerde", "haette", "sehr", "auch", "nicht", "kein", "keine", "aber",
    "dass", "man", "sich", "als", "aus", "ist", "sind", "sein", "haben", "hat", "wenn", "damit", "bereich", "thema",
    "praktikum", "praktikums", "stelle", "job", "the", "and", "for", "with", "would", "like", "want",
}

SYNONYMS = {
    "ki": ["ki", "ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural"],
    "ai": ["ki", "ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural"],
    "llm": ["llm", "large language model", "sprachmodell", "language model", "gpt", "transformer", "nlp", "genai", "generative ai"],
    "llms": ["llm", "large language model", "sprachmodell", "language model", "gpt", "transformer", "nlp", "genai", "generative ai"],
    "nlp": ["nlp", "sprachverarbeitung", "language model", "llm", "text"],
    "daten": ["daten", "data", "analytics", "analyse", "datenanalyse"],
    "data": ["data", "daten", "analytics", "analyse", "datenanalyse"],
    "robotik": ["robotik", "robotics", "roboter", "embedded", "hardware"],
    "webentwicklung": ["web", "frontend", "backend", "fullstack", "react", "webentwicklung"],
    "programmieren": ["software", "engineering", "entwicklung", "developer", "programmier", "coding", "code"],
    "software": ["software", "engineering", "entwicklung", "developer", "coding"],
    "marketing": ["marketing", "social media", "content", "kampagne", "growth", "brand"],
    "finanzen": ["finance", "finanzen", "controlling", "investment", "fundraising", "accounting"],
    "startup": ["startup", "gruendung", "venture", "scaleup", "founder"],
    "vertrieb": ["sales", "vertrieb", "business development", "kunden"],
    "produkt": ["produkt", "product", "product management", "ux"],
    "cyber": ["security", "cyber", "sicherheit", "infosec"],
    "medizin": ["health", "medizin", "medical", "clinical", "gesundheit"],
}

CATEGORY_KEYWORDS = {
    "ai_tech": [
        "ai", "ki", "machine learning", "ml", "llm", "data", "daten", "software", "engineer", "engineering",
        "developer", "entwickl", "python", "backend", "frontend", "fullstack", "devops", "cloud", "robot",
        "computer vision", "nlp", "informatik", "tech", "it ", "coding", "programmier", "deep learning",
    ],
    "business": [
        "marketing", "sales", "vertrieb", "business development", "bizdev", "finance", "finanzen", "controlling",
        "operations", "strategy", "strategie", "consulting", "product management", "produktmanagement",
        "human resources", "hr ", "personal", "recruiting", "venture", "investment", "wirtschaft", "growth",
        "communications", "kommunikation", "content", "brand",
    ],
}

CATEGORY_LABELS = {"ai_tech": "KI/Tech", "business": "Wirtschaft"}


@dataclass
class Criterion:
    key: str
    label: str
    weight: float
    score: float
    detail: str

    @property
    def contribution(self) -> float:
        return self.weight * self.score


@dataclass
class MatchResult:
    score: int
    criteria: list[Criterion] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "criteria": [
                {
                    "key": c.key,
                    "label": c.label,
                    "weight": round(c.weight, 4),
                    "score": round(c.score, 4),
                    "percent": round(c.score * 100),
                    "contribution": round(c.contribution * 100, 1),
                    "detail": c.detail,
                }
                for c in self.criteria
            ],
        }


def extract_keywords(free_text: str) -> list[str]:
    tokens = [t for t in re.split(r"[^a-zA-ZäöüßÄÖÜ0-9+#]+", (free_text or "").lower()) if t]
    keywords: list[str] = []
    for token in tokens:
        cleaned = normalize(token)
        if len(cleaned) < 3 or cleaned in STOPWORDS:
            continue
        if cleaned not in keywords:
            keywords.append(cleaned)
    return keywords[:20]


def expand_keyword(keyword: str) -> list[str]:
    return SYNONYMS.get(keyword, [keyword])


def infer_categories(offer: dict) -> list[str]:
    haystack = normalize(f"{offer.get('title', '')} {offer.get('description', '')}")
    found = [key for key, words in CATEGORY_KEYWORDS.items() if any(normalize(w) in haystack for w in words)]
    return found or ["ai_tech", "business"]


def score_interest(profile: dict, offer: dict) -> tuple[Criterion, list[str]]:
    wanted = set(profile.get("interests") or [])
    categories = set(offer.get("categories") or []) or set(infer_categories(offer))

    if not wanted or wanted == {"ai_tech", "business"}:
        base, reason = (1.0, "beide Bereiche gewünscht") if categories else (0.6, "Bereich unklar")
    elif wanted & categories:
        base = 1.0
        reason = "Bereich " + " und ".join(CATEGORY_LABELS.get(c, c) for c in sorted(wanted & categories)) + " passt"
    else:
        base = 0.15
        reason = "anderer Bereich: " + ", ".join(CATEGORY_LABELS.get(c, c) for c in sorted(categories))

    haystack = normalize(f"{offer.get('title', '')} {offer.get('description', '')} {offer.get('company', '')}")
    keywords = extract_keywords(profile.get("free_text", ""))
    matched = [kw for kw in keywords if any(normalize(v) in haystack for v in expand_keyword(kw))]

    bonus = 0.0
    if keywords:
        hit_ratio = len(matched) / len(keywords)
        bonus = min(0.3, hit_ratio * 0.45)
        if matched:
            reason += f", Stichworte {', '.join(matched[:4])} kommen vor"
        elif base >= 0.9:
            base -= 0.12
            reason += ", deine Stichworte tauchen aber nicht auf"

    return Criterion("interest", "Interesse", WEIGHTS["interest"], min(1.0, base + bonus), reason), matched


def score_location(profile: dict, offer: dict) -> Criterion:
    weight = WEIGHTS["location"]
    origin = profile.get("location") or ""
    city = offer.get("city") or ""
    radius = max(int(profile.get("radius_km") or 30), 1)

    if is_remote(city):
        return Criterion("location", "Ort", weight, 0.9, "remote möglich")
    if not geocode(city):
        return Criterion("location", "Ort", weight, 0.4, f"Ort „{city or 'unbekannt'}“ nicht einzuordnen")

    distance = distance_between(origin, city)
    if distance is None:
        return Criterion("location", "Ort", weight, 0.4, "dein Wunschort ist nicht einzuordnen")

    rounded = round(distance)
    if distance <= radius:
        score = 1.0 if radius <= 1 else max(0.85, 1.0 - 0.15 * (distance / radius))
        return Criterion("location", "Ort", weight, score, f"{rounded} km, liegt in deinem Umkreis")

    overshoot = (distance - radius) / (radius * 1.5)
    score = max(0.0, 1.0 - overshoot)
    return Criterion("location", "Ort", weight, score, f"{rounded} km, {round(distance - radius)} km über deinem Umkreis")


def score_compensation(profile: dict, offer: dict) -> Criterion:
    weight = WEIGHTS["compensation"]
    wish = (profile.get("compensation") or "any").lower()
    kind = (offer.get("compensation_kind") or "unknown").lower()
    text = offer.get("compensation_text") or ""

    if wish == "any":
        return Criterion("compensation", "Vergütung", weight, 1.0, "Vergütung ist dir egal")
    if wish == "paid":
        if kind == "paid":
            return Criterion("compensation", "Vergütung", weight, 1.0, text or "bezahlt")
        if kind == "unpaid":
            return Criterion("compensation", "Vergütung", weight, 0.0, "unbezahlt")
        return Criterion("compensation", "Vergütung", weight, 0.5, "keine Angabe zur Vergütung")
    if kind == "paid":
        return Criterion("compensation", "Vergütung", weight, 1.0, text or "bezahlt, besser als gefordert")
    if kind == "unpaid":
        return Criterion("compensation", "Vergütung", weight, 1.0, "unbezahlt, für dich in Ordnung")
    return Criterion("compensation", "Vergütung", weight, 0.8, "keine Angabe zur Vergütung")


def score_timeframe(profile: dict, offer: dict) -> Criterion:
    weight = WEIGHTS["timeframe"]
    start, end = profile.get("start_date"), profile.get("end_date")
    if not start or not end:
        return Criterion("timeframe", "Zeitraum", weight, 0.5, "du hast keinen Zeitraum angegeben")

    window = parse_window(
        offer.get("start_date_hint", ""),
        offer.get("end_date_hint", ""),
        offer.get("duration_hint", ""),
        offer.get("description", ""),
    )
    ratio, reason = overlap_ratio(date.fromisoformat(start), date.fromisoformat(end), window)
    return Criterion("timeframe", "Zeitraum", weight, ratio, reason)


def score_offer(profile: dict, offer: dict) -> MatchResult:
    interest, matched = score_interest(profile, offer)
    criteria = [interest, score_location(profile, offer), score_compensation(profile, offer), score_timeframe(profile, offer)]
    total_weight = sum(c.weight for c in criteria) or 1.0
    total = sum(c.contribution for c in criteria) / total_weight
    return MatchResult(score=round(total * 100), criteria=criteria, matched_keywords=matched)
