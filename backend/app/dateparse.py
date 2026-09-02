import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {
    "januar": 1, "jan": 1, "february": 2, "februar": 2, "feb": 2, "maerz": 3, "marz": 3, "mrz": 3, "march": 3,
    "april": 4, "apr": 4, "mai": 5, "may": 5, "juni": 6, "jun": 6, "june": 6, "juli": 7, "jul": 7, "july": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "dezember": 12, "dez": 12, "december": 12, "dec": 12, "january": 1,
}
SEASONS = {
    "fruehjahr": (3, 3), "fruehling": (3, 3), "spring": (3, 3),
    "sommer": (6, 3), "summer": (6, 3),
    "herbst": (9, 3), "autumn": (9, 3), "fall": (9, 3),
    "winter": (12, 3),
}
ROLLING_HINTS = ("ab sofort", "jederzeit", "laufend", "ganzjaehrig", "fortlaufend", "durchgehend", "flexibel", "nach absprache", "asap", "immer")

ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DOTTED_RE = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b")
WORD_RE = re.compile(r"\b([a-z]{3,10})\b")
YEAR_RE = re.compile(r"\b(20\d{2})\b")
DURATION_RE = re.compile(r"\b(\d{1,2})\s*(?:bis|-|–)?\s*(\d{1,2})?\s*(woche|wochen|monat|monate|monaten|tage|tag)\b")


@dataclass
class Window:
    start: date | None = None
    end: date | None = None
    rolling: bool = False
    duration_days: int | None = None
    month_granular: bool = False

    @property
    def known(self) -> bool:
        return self.rolling or self.start is not None or self.end is not None


def _normalize(value: str) -> str:
    text = (value or "").lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        text = text.replace(a, b)
    return text


def _end_of_month(value: date) -> date:
    year = value.year + 1 if value.month == 12 else value.year
    month = 1 if value.month == 12 else value.month + 1
    return date(year, month, 1) - timedelta(days=1)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_window(*hints: str) -> Window:
    text = " ".join(_normalize(h) for h in hints if h).strip()
    if not text:
        return Window()

    window = Window()
    if any(hint in text for hint in ROLLING_HINTS):
        window.rolling = True

    explicit: list[date] = []
    for match in ISO_RE.finditer(text):
        found = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if found:
            explicit.append(found)
    for match in DOTTED_RE.finditer(text):
        found = _safe_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if found:
            explicit.append(found)

    month_granular = False
    month_tokens: list[date] = []
    if not explicit:
        years = [(m.start(), int(m.group(1))) for m in YEAR_RE.finditer(text)]
        for match in WORD_RE.finditer(text):
            word = match.group(1)
            month = MONTHS.get(word)
            season = SEASONS.get(word)
            if not month and not season:
                continue
            later = [y for pos, y in years if pos >= match.start()]
            year = later[0] if later else (years[0][1] if years else None)
            if year is None:
                continue
            if season:
                month, span = season
                found = _safe_date(year, month, 1)
                if found:
                    explicit.append(found)
                    tail_year = year + 1 if month + span > 12 else year
                    tail_month = (month + span - 1) % 12 + 1
                    tail = _safe_date(tail_year, tail_month, 1)
                    if tail:
                        explicit.append(tail - timedelta(days=1))
            else:
                found = _safe_date(year, month, 1)
                if found:
                    month_tokens.append(found)
                    month_granular = True

    for index in range(len(month_tokens) - 2, -1, -1):
        while month_tokens[index] >= month_tokens[index + 1]:
            month_tokens[index] = month_tokens[index].replace(year=month_tokens[index].year - 1)
    explicit.extend(month_tokens)

    duration = DURATION_RE.search(text)
    if duration:
        amount = int(duration.group(2) or duration.group(1))
        unit = duration.group(3)
        if unit.startswith("woche"):
            window.duration_days = amount * 7
        elif unit.startswith("tag"):
            window.duration_days = amount
        else:
            window.duration_days = amount * 30

    explicit.sort()
    if explicit:
        window.start = explicit[0]
        if len(explicit) > 1:
            window.end = _end_of_month(explicit[-1]) if month_granular else explicit[-1]
        elif window.duration_days:
            window.end = window.start + timedelta(days=window.duration_days)
        elif month_granular:
            window.end = _end_of_month(window.start)
            window.month_granular = True
    return window


def overlap_ratio(desired_start: date, desired_end: date, window: Window, horizon_days: int = 180) -> tuple[float, str]:
    if desired_end < desired_start:
        desired_start, desired_end = desired_end, desired_start
    desired_days = max((desired_end - desired_start).days + 1, 1)

    if not window.known:
        return 0.5, "Zeitraum nicht angegeben"

    if window.rolling and window.start is None:
        return 0.85, "laufend zu besetzen, kein fester Zeitraum genannt"

    start = window.start or desired_start
    end = window.end or (start + timedelta(days=window.duration_days or horizon_days))
    if end < start:
        start, end = end, start

    overlap_days = (min(desired_end, end) - max(desired_start, start)).days + 1
    if overlap_days <= 0:
        gap = abs((start - desired_end).days if start > desired_end else (desired_start - end).days)
        if window.rolling:
            return 0.6, "laufend, aber angegebener Start passt nicht"
        return 0.0, f"kein Überlappen, {gap} Tage daneben"

    ratio = min(1.0, overlap_days / desired_days)
    if ratio >= 0.99:
        return 1.0, "deckt deinen Zeitraum ab"
    return ratio, f"{overlap_days} von {desired_days} Tagen überlappen"
