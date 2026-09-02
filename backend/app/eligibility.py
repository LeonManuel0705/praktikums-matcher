import re

from .geo import normalize

OPEN = "offen"
STUDENTS_ONLY = "nur_studierende"
UNCLEAR = "unklar"

SCHOOL_SIGNALS = [
    "schuelerpraktikum", "schuelerpraktika", "schulpraktikum", "schuelerinnen und schueler",
    "fuer schueler", "praktikum fuer schuelerinnen", "orientierungspraktikum", "berufsorientierung",
    "betriebspraktikum", "praxislernen", "oberstufe", "sekundarstufe", "ab 15 jahren", "ab 16 jahren",
    "schuelerin", "schueler", "gymnasium", "abiturient", "abiturienten", "vor dem studium",
    "schnupperpraktikum", "ferienpraktikum",
]

STUDENT_SIGNALS = [
    "immatrikuliert", "immatrikulation", "eingeschrieben", "einschreibung", "laufendes studium",
    "waehrend deines studiums", "waehrend des studiums", "studierende", "studierender", "studentin",
    "student", "studiengang", "bachelorstudium", "masterstudium", "im studium", "hochschule",
    "universitaet", "fachhochschule", "pflichtpraktikum im rahmen des studiums", "studienbescheinigung",
    "enrolled", "university", "bachelor", "master", "undergraduate", "graduate", "phd", "diplom",
]

NEGATED_STUDENT = [
    "kein studium noetig", "ohne studium", "auch ohne studium", "kein abgeschlossenes studium",
    "schueler und studierende", "schuelerinnen und studierende",
]


def _has(haystack: str, term: str) -> bool:
    cleaned = normalize(term)
    if not cleaned:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", haystack) is not None


def classify(offer: dict) -> tuple[str, str]:
    declared = str(offer.get("eligibility") or "").strip().lower()
    if declared in {OPEN, STUDENTS_ONLY, UNCLEAR}:
        return declared, "Angabe aus der Anzeige"

    if str(offer.get("target_group") or "") == "schuelerpraktikum":
        return OPEN, "als Schülerpraktikum ausgeschrieben"

    haystack = normalize(" ".join(str(offer.get(field, "")) for field in
                                 ("title", "description", "evidence", "target_group", "duration_hint")))

    school_hits = [term for term in SCHOOL_SIGNALS if _has(haystack, term)]
    student_hits = [term for term in STUDENT_SIGNALS if _has(haystack, term)]
    negations = [term for term in NEGATED_STUDENT if normalize(term) in haystack]

    if negations:
        return OPEN, "Anzeige nennt ausdrücklich keinen Studienzwang"
    if school_hits and not student_hits:
        return OPEN, f"Anzeige spricht Schüler an ({school_hits[0]})"
    if student_hits and not school_hits:
        return STUDENTS_ONLY, f"Anzeige setzt ein Studium voraus ({student_hits[0]})"
    if student_hits and school_hits:
        return UNCLEAR, f"Anzeige nennt beides ({school_hits[0]} und {student_hits[0]})"
    return UNCLEAR, "Anzeige sagt nichts über die Voraussetzungen"
