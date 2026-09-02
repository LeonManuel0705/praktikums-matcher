import re

from .geo import normalize

OPEN = "offen"
BLOCKED = "qualifikation_noetig"
UNCLEAR = "unklar"

LEGACY_VALUES = {"nur_studierende": BLOCKED}

SCHOOL_SIGNALS = [
    "schuelerpraktikum", "schuelerpraktika", "schulpraktikum", "schuelerinnen und schueler",
    "fuer schueler", "praktikum fuer schuelerinnen", "orientierungspraktikum", "berufsorientierung",
    "betriebspraktikum", "praxislernen", "oberstufe", "sekundarstufe", "ab 15 jahren", "ab 16 jahren",
    "schuelerin", "schueler", "gymnasium", "abiturient", "abiturienten", "vor dem studium",
    "schnupperpraktikum", "ferienpraktikum",
]

STUDY_SIGNALS = [
    "immatrikuliert", "immatrikulation", "eingeschrieben", "einschreibung", "laufendes studium",
    "waehrend deines studiums", "waehrend des studiums", "studierende", "studierender", "studentin",
    "student", "studiengang", "bachelorstudium", "masterstudium", "im studium", "studienbescheinigung",
    "pflichtpraktikum im rahmen des studiums", "enrolled", "bachelor", "master", "undergraduate",
    "graduate", "phd", "diplom", "abgeschlossenes studium",
]

CREDENTIAL_SIGNALS = [
    "abgeschlossene ausbildung", "abgeschlossene berufsausbildung", "ausbildungsabschluss",
    "abgeschlossene kaufmaennische ausbildung", "abgeschlossene technische ausbildung",
    "facharbeiter", "facharbeiterbrief", "geselle", "gesellenbrief", "meisterbrief", "meistertitel",
    "staatlich gepruefter", "staatlich gepruefte", "examiniert", "approbation", "berufsabschluss",
    "vocational training completed", "completed apprenticeship",
]

EXPERIENCE_SIGNALS = [
    "berufserfahrung", "mehrjaehrige erfahrung", "einschlaegige berufserfahrung",
    "years of experience", "professional experience", "praxiserfahrung",
]

REQUIREMENT_CUES = [
    "voraussetzung", "voraussetzungen", "erforderlich", "erforderliche", "notwendig", "benoetigt",
    "du bringst mit", "sie bringen mit", "dein profil", "ihr profil", "anforderungen", "wir erwarten",
    "mindestens", "setzt voraus", "required", "requirements", "must have", "you have", "you bring",
    "qualifikation", "qualifikationen",
]

OFFERING_CUES = [
    "sammelst", "sammeln", "sammle", "erste einblicke", "gewinnst", "erwirbst", "wir bieten",
    "du erhaeltst", "lernst", "erste erfahrungen", "you will gain", "you gain",
]

NEGATED = [
    "kein studium noetig", "ohne studium", "auch ohne studium", "kein abgeschlossenes studium",
    "schueler und studierende", "schuelerinnen und studierende", "ohne vorkenntnisse",
    "keine vorkenntnisse noetig", "keine berufserfahrung noetig",
]

CONTEXT_WINDOW = 90


def _find(haystack: str, term: str) -> int:
    cleaned = normalize(term)
    if not cleaned:
        return -1
    match = re.search(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", haystack)
    return match.start() if match else -1


def _has(haystack: str, term: str) -> bool:
    return _find(haystack, term) >= 0


def _is_requirement(haystack: str, position: int) -> bool:
    window = haystack[max(0, position - CONTEXT_WINDOW) : position + CONTEXT_WINDOW]
    if any(normalize(cue) in window for cue in OFFERING_CUES):
        return False
    return any(normalize(cue) in window for cue in REQUIREMENT_CUES)


def classify(offer: dict) -> tuple[str, str]:
    declared = str(offer.get("eligibility") or "").strip().lower()
    declared = LEGACY_VALUES.get(declared, declared)
    if declared in {OPEN, BLOCKED, UNCLEAR}:
        return declared, "Angabe aus der Anzeige"

    if str(offer.get("target_group") or "") == "schuelerpraktikum":
        return OPEN, "als Schülerpraktikum ausgeschrieben"

    haystack = normalize(" ".join(str(offer.get(field, "")) for field in
                                 ("title", "description", "evidence", "eligibility_evidence",
                                  "target_group", "duration_hint")))

    if any(normalize(term) in haystack for term in NEGATED):
        return OPEN, "Anzeige nennt ausdrücklich keine solche Voraussetzung"

    school_hits = [term for term in SCHOOL_SIGNALS if _has(haystack, term)]
    study_hits = [term for term in STUDY_SIGNALS if _has(haystack, term)]
    credential_hits = [term for term in CREDENTIAL_SIGNALS if _has(haystack, term)]
    experience_hits = [
        term for term in EXPERIENCE_SIGNALS
        if (position := _find(haystack, term)) >= 0 and _is_requirement(haystack, position)
    ]

    blocking = study_hits + credential_hits + experience_hits
    if blocking and not school_hits:
        if credential_hits:
            return BLOCKED, f"Anzeige verlangt eine abgeschlossene Ausbildung ({credential_hits[0]})"
        if experience_hits:
            return BLOCKED, f"Anzeige verlangt Berufserfahrung ({experience_hits[0]})"
        return BLOCKED, f"Anzeige setzt ein Studium voraus ({study_hits[0]})"
    if school_hits and not blocking:
        return OPEN, f"Anzeige spricht Schüler an ({school_hits[0]})"
    if school_hits and blocking:
        return UNCLEAR, f"Anzeige nennt beides ({school_hits[0]} und {blocking[0]})"
    return UNCLEAR, "Anzeige sagt nichts über die Voraussetzungen"
