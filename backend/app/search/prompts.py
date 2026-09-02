from datetime import date

CATEGORY_LABELS = {"ai_tech": "KI/Tech", "business": "Wirtschaft"}
COMPENSATION_LABELS = {"paid": "bezahlt", "unpaid": "unbezahlt ist auch in Ordnung", "any": "egal"}

FIELD_SPEC = """Jedes Angebot ist ein Objekt mit genau diesen Feldern:
"title", "company", "city", "compensation_kind" (paid|unpaid|unknown), "compensation_text",
"description" (1-3 Saetze deutsch, sachlich), "url" (direkter Link zur Anzeige),
"source" (Domain), "start_date_hint", "end_date_hint", "duration_hint",
"categories" (Teilmenge von ["ai_tech","business"]), "target_group"
(schuelerpraktikum|pflichtpraktikum|allgemeines_praktikum|unklar), "evidence" (woertliches Zitat von der Seite)."""

RULES = """HARTE REGELN:
1. Erfinde nichts. Jedes Angebot muss von einer Seite stammen, die du mit WebFetch tatsaechlich geoeffnet hast.
2. "evidence" ist ein woertliches Zitat aus dem abgerufenen Seiteninhalt. Ohne Zitat gehoert das Angebot nicht in die Liste.
3. "url" zeigt auf die konkrete Anzeige oder die Karriereseite, auf der die Stelle wirklich steht.
4. Keine Werkstudenten-, Vollzeit- oder Abschlussarbeitsstellen.
5. Wenn du nichts Belegtes findest, ist das ein gueltiges Ergebnis. Sag es einfach.

SO GIBST DU ERGEBNISSE AUS, DAS IST WICHTIG:
Sobald du EIN Angebot belegt hast, gib es SOFORT aus, bevor du weitersuchst. Schreibe dafuer eine einzelne Zeile,
die genau so beginnt:

OFFER: {"title": ..., "company": ..., ...}

Das JSON steht komplett auf dieser einen Zeile, ohne Zeilenumbruch, ohne Markdown-Fence. Danach suchst du weiter
und gibst das naechste gefundene Angebot wieder als eigene OFFER-Zeile aus. Sammle die Angebote NICHT bis zum
Schluss, sondern melde jedes einzeln, sobald es belegt ist. Wenn du fertig bist, schreibe als letzte Zeile FERTIG."""

ANGLES = [
    ("boersen", "Praktikumsboersen und Aggregatoren: deutsche-startups.de/jobs, startupsucht.com, jobmensa.de, praktikum.de, absolventa.de. Suche dort nach passenden Praktika und oeffne die Trefferseiten."),
    ("startups", "Karriereseiten konkreter Startups in der Zielregion. Finde erst passende Firmen, dann pruefe deren Jobseiten, haeufig gehostet auf join.com, greenhouse.io, ashbyhq.com, jobs.lever.co oder personio."),
    ("regional", "Regionale und oeffentliche Boersen: IHK-Praktikumsboersen, Praktikumsboersen der Staedte, die Jobboerse der Bundesagentur fuer Arbeit, Hochschul-Transferstellen und Gruenderzentren der Region."),
    ("schueler", "Explizit als Schuelerpraktikum ausgeschriebene Plaetze. Suche nach Formulierungen wie \\\"Schuelerpraktikum\\\" kombiniert mit der Region und dem Interessensbereich. Hier duerfen es auch groessere Arbeitgeber sein, solange der Platz wirklich fuer Schueler ist."),
]


def describe_profile(profile: dict) -> str:
    interests = profile.get("interests") or []
    interest_text = " und ".join(CATEGORY_LABELS.get(i, i) for i in interests) or "KI/Tech und Wirtschaft"
    grade = profile.get("grade_level") or "Oberstufe"
    lines = [
        f"Interessensbereich: {interest_text}",
        f"Wunschort: {profile.get('location') or 'Berlin'}, akzeptierter Umkreis: {profile.get('radius_km') or 30} km",
        f"Klassenstufe: {grade}",
        f"Verguetung: {COMPENSATION_LABELS.get(profile.get('compensation') or 'any', 'egal')}",
    ]
    if profile.get("start_date") and profile.get("end_date"):
        lines.append(f"Wunschzeitraum: {profile['start_date']} bis {profile['end_date']}")
    if profile.get("free_text"):
        lines.append(f"Zusaetzlicher Wunsch in eigenen Worten: {profile['free_text']}")
    return "\n".join(f"- {line}" for line in lines)


def build_prompt(profile: dict, angle_key: str, angle_text: str, today: date, limit: int = 6,
                 budget_searches: int = 6, budget_fetches: int = 10) -> str:
    return f"""Du recherchierst Praktikumsplaetze fuer einen Schueler. Heute ist der {today.isoformat()}.

Profil des Schuelers:
{describe_profile(profile)}

Dein Suchwinkel fuer diesen Durchlauf ({angle_key}):
{angle_text}

Nutze WebSearch fuer die Suche und WebFetch, um die Seiten wirklich zu oeffnen und die Angaben abzulesen.
Suche in der Region um den Wunschort, der Umkreis darf grosszuegig ausgelegt werden, aber bleib im erreichbaren Bereich.

{FIELD_SPEC}

{RULES}

DEIN AUFWANDSBUDGET, HALTE DICH DARAN:
Hoechstens {budget_searches} Suchanfragen und {budget_fetches} Seitenabrufe fuer diesen ganzen Durchlauf.
Waehle die Abrufe also gezielt: erst suchen, dann nur die Seiten oeffnen, die wirklich nach einer Anzeige
aussehen. Wenn das Budget aufgebraucht ist, hoerst du auf und meldest, was du bis dahin belegt hast.
Ein Durchlauf mit zwei belegten Angeboten im Budget ist besser als sechs Angebote weit darueber.

Gib hoechstens {limit} Angebote zurueck. Lieber wenige belegte als viele vage."""
