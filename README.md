# Praktikums-Matcher

Prototyp einer Web-App für Oberstufenschüler, die ein Praktikum im Bereich KI/Tech oder Wirtschaft bei
Startups in Berlin und Potsdam suchen. Der Schüler legt ein Wunsch-Profil an, startet eine Suche, und ein
Agent recherchiert in dem Moment live im Netz. Jeder Treffer bekommt einen Prozentwert, der offenlegt,
wie er zustande kommt.

## Starten

```bash
./scripts/run.sh
```

Danach http://127.0.0.1:8000 öffnen. Das Skript baut das Frontend beim ersten Start selbst.

Für die Frontend-Entwicklung mit Hot Reload:

```bash
./.venv/bin/python -m uvicorn backend.app.main:app --port 8000   # Terminal 1
cd frontend && npm run dev                                       # Terminal 2, http://localhost:5173
```

## Wie die Live-Suche funktioniert

Beim Klick auf "Suche starten" passiert Folgendes:

1. Der geprüfte Grundstock wird sofort gegen das Profil bewertet, damit die Liste nicht leer bleibt.
2. Vier Suchwinkel starten parallel: Praktikumsbörsen, Karriereseiten von Startups, regionale und
   öffentliche Börsen, sowie explizit ausgeschriebene Schülerpraktika.
3. Jeder Winkel sucht und öffnet Seiten. Jede Suchanfrage und jeder Seitenabruf erscheint live im Protokoll.
4. Sobald ein Angebot belegt ist, meldet der Agent es sofort einzeln. Es wird direkt bewertet und erscheint
   in der Liste, noch während die Recherche weiterläuft.

Jedes Angebot muss ein wörtliches Zitat von der abgerufenen Seite mitbringen. Angebote ohne Beleg oder ohne
gültige URL werden verworfen. Das Zitat ist in der Oberfläche unter "Beleg" einsehbar.

## Suchprovider

Die App wählt automatisch den ersten verfügbaren Provider. `GET /api/providers` zeigt den Stand.

| Provider | Braucht | Status |
|---|---|---|
| `anthropic_api` | `ANTHROPIC_API_KEY` | Anthropic-Websuche über `web_search_20260209`, ungetestet mangels Key |
| `claude_cli` | Claude Code auf dem Rechner | Standard hier, nutzt die bestehende Anmeldung, kein Key nötig |
| `tavily` | `TAVILY_API_KEY` und `ANTHROPIC_API_KEY` | Tavily sucht, Claude extrahiert, ungetestet mangels Key |
| `corpus` | nichts | Offline-Rückfall auf den geprüften Grundstock |

Erzwingen lässt sich einer über `PM_PROVIDER=corpus ./scripts/run.sh` oder pro Suche über den Request-Body.

Weitere Umgebungsvariablen: `PM_CLAUDE_MODEL` (Standard `claude-sonnet-5`), `PM_CLAUDE_BINARY`,
`PM_SEARCH_TIMEOUT`, `PM_DB_PATH`.

### Aufwandsbudget

Ohne Begrenzung hat ein einzelner Suchwinkel bis zu 43 Suchanfragen und 41 Seitenabrufe verbraucht und
trotzdem nur ein bis zwei Angebote geliefert. Jeder Winkel bekommt deshalb ein Budget im Prompt, dazu eine
harte Obergrenze im Code, die den Prozess beendet, falls er sich nicht daran hält. Gemessen hat das die
Laufzeit einer Suche von über acht auf 2,7 Minuten gedrückt, bei gleicher Ausbeute.

| Variable | Standard | Bedeutung |
|---|---|---|
| `PM_BUDGET_SEARCHES` | 6 | Suchanfragen pro Winkel, dem Agenten im Prompt vorgegeben |
| `PM_BUDGET_FETCHES` | 10 | Seitenabrufe pro Winkel, dem Agenten im Prompt vorgegeben |
| `PM_CAP_SEARCHES` | 12 | harte Obergrenze, danach wird der Winkel beendet |
| `PM_CAP_FETCHES` | 18 | harte Obergrenze, danach wird der Winkel beendet |

## Wer darf sich überhaupt bewerben

Die erste Fassung hat einen entscheidenden Punkt übersehen: sehr viele Praktikumsanzeigen verlangen eine
laufende Immatrikulation. Für einen Schüler sind die wertlos. Eine Prüfung des ersten Grundstocks hat es
deutlich gezeigt: von 57 recherchierten Angeboten waren nur 9 wirklich zugänglich, 23 verlangten
ausdrücklich ein Studium. Eine zweite Recherche, die von vornherein nur nach zugänglichen Stellen
gesucht hat, hat den Grundstock auf 67 Angebote gebracht, davon 21 ausdrücklich offen.

Jedes Angebot bekommt deshalb eine Einstufung:

| Einstufung | Bedeutung |
|---|---|
| `offen` | Schüler oder Abiturienten ohne Studium dürfen sich bewerben |
| `qualifikation_noetig` | Anzeige verlangt Immatrikulation, Studienbescheinigung, Bachelor, Master, eine abgeschlossene Ausbildung oder Berufserfahrung |
| `unklar` | Die Anzeige sagt nichts über die Voraussetzungen |

Die Einstufung entsteht auf zwei Wegen: der Suchagent liest sie aus dem Anforderungsteil der Anzeige, und
unabhängig davon prüft `eligibility.py` den Text auf Signalwörter, an Wortgrenzen statt als Teilstring.
Der Suchagent bekommt zusätzlich die Anweisung, Angebote mit Studienpflicht gar nicht erst zu melden.

Bei Berufserfahrung zählt der Zusammenhang: "du sammelst erste Berufserfahrung" ist ein Angebot und
bleibt drin, "Voraussetzung: mehrjährige Berufserfahrung" schließt aus.

In der Ergebnisliste steht der Schalter standardmäßig auf "Für dich möglich", `qualifikation_noetig` ist
also ausgeblendet. Wie viele das betrifft, steht daneben, und über "Alle" sind sie weiterhin einsehbar.

## Wie der Suchagent eingehegt ist

Der Agent öffnet fremde Webseiten. Eine manipulierte Anzeige könnte versuchen, ihm Anweisungen
unterzuschieben. Deshalb läuft der Prozess bewusst eingeschränkt:

- `--disallowedTools` sperrt Bash, Read, Write, Edit, Task und Konsorten
- `--setting-sources ""` verhindert, dass er die globale Allow-Liste des Rechners erbt
- `--strict-mcp-config` schneidet angebundene Dienste wie Gmail oder Drive ab
- eigenes leeres Arbeitsverzeichnis unter `TMPDIR` statt der Projektwurzel mit der Datenbank
- gefilterte Umgebung: sieben Variablen, keine API-Schlüssel
- der Freitext des Profils steht in einem markierten Block, nicht zwischen den Anweisungen

Gemessen: statt 77 Werkzeugen inklusive Bash und 49 MCP-Werkzeugen stehen dem Agenten noch 21 bis 24
zur Verfügung, keins davon mit Zugriff auf das Dateisystem oder die Shell.

## Der Matching-Score

Vier Kriterien, gewichtet wie im Konzept vorgegeben:

| Kriterium | Gewicht | Wie gerechnet wird |
|---|---|---|
| Interesse | 40 % | Bereichsabgleich plus Treffer deiner Freitext-Stichworte in Titel und Beschreibung, mit Synonymen |
| Ort | 25 % | Echte Luftlinie über Koordinaten. Innerhalb des Umkreises voll, darüber linear abfallend |
| Vergütung | 15 % | Abgleich mit deinem Wunsch. Fehlende Angabe zählt neutral, nicht negativ |
| Zeitraum | 20 % | Überlappung deines Wunschzeitraums mit dem Angebot, deutsche Datumsangaben werden geparst |

Der Ring auf jeder Karte zeigt nicht nur den Gesamtwert: er besteht aus vier Bögen, deren Länge das Gewicht
abbildet und deren Füllung den Teilscore. Man sieht also sofort, welches Kriterium einen Treffer runterzieht.

### Freitext-Feinschliff

Der deterministische Teil trifft den Freitext nur über Stichworte und Synonyme. Wer einen Wunsch
formuliert hat, kann nach der Suche auf "Freitext-Feinschliff" drücken: dann liest ein Modell alle
Treffer und bewertet, wie gut sie zum Wunsch passen, unabhängig von Wortgleichheit. Das Urteil geht zur
Hälfte in das Kriterium Interesse ein und ersetzt dessen Begründung durch die des Modells.

Es werden immer alle Treffer bewertet, nie nur die vordersten. Sonst würden unbewertete Angebote mit
zu hohem Wert die tatsächlich passenden überholen.

Gewichte lassen sich zur Laufzeit ändern:

```bash
curl -X PUT localhost:8000/api/weights -H 'Content-Type: application/json' \
     -d '{"interest":0.5,"location":0.3,"compensation":0.05,"timeframe":0.15}'
curl -X POST localhost:8000/api/searches/1/rescore -b cookies.txt
```

## Geprüft

- 77 Unit-Tests für Geo, Datumsparsen, Bewertung, Normalisierung und die Regressionen aus dem Review
- Ein Playwright-Klickpfad durch den ganzen Ablauf, von der Registrierung bis zum Abmelden
- Ein Fanout aus 25 Review-Agenten über fünf Dimensionen, jeder Befund gegengeprüft. Ergebnis und
  Behebung in [docs/REVIEW.md](docs/REVIEW.md)
- Die Links im Grundstock wurden abgerufen: 56 von 57 antworten mit 200, einer wehrt Abrufe ab

## Aufbau

```
backend/app/
  main.py         API und Auslieferung des Frontends
  db.py           SQLite-Schema
  auth.py         scrypt-Passwörter, Sessions als SHA-256-Token
  geo.py          Ortsverzeichnis, Haversine, unscharfe Ortsauflösung
  dateparse.py    deutsche Zeitraumangaben
  scoring.py      Score mit Begründung je Kriterium
  jobs.py         asynchrone Suchläufe mit Ereignisprotokoll
  search/         Provider, Prompts, Normalisierung
  rerank.py       optionaler Feinschliff des Freitexts durch ein Modell
frontend/src/     React, eigenes Design-System, keine UI-Bibliothek
tests/            77 Tests für Geo, Datum, Scoring, Normalisierung, Regressionen
```

## Tests

```bash
./.venv/bin/python -m pytest tests -q
```

## Grenzen dieses Prototyps

- Der Grundstock in `backend/data/seed_offers.json` ist eine Momentaufnahme vom 2. September 2026 mit
  67 Angeboten aus zwei Recherchen.
  Praktikumsanzeigen laufen ab, die Links können ins Leere führen.
- Eine Live-Suche startet vier Agentenprozesse mit echter Websuche. Sie dauert rund drei Minuten und kostet
  Guthaben auf dem Konto, mit dem Claude Code angemeldet ist.
- Je voller der Grundstock, desto häufiger findet die Live-Suche etwas, das schon drinsteht. Das Protokoll
  weist das als "waren schon bekannt" aus, statt es als neuen Treffer zu zählen.
- Sessions liegen unverschlüsselt in SQLite, das Cookie ist nicht auf `secure` gesetzt. Für lokalen Betrieb
  gedacht, nicht für ein öffentliches Deployment.
- Die Gewichte gelten prozessweit, nicht pro Benutzer.
- Das Ortsverzeichnis ist eine feste Liste. Orte, die darin fehlen, bekommen beim Ort-Kriterium einen
  neutralen Wert statt einer echten Entfernung.
- Kein Bewerbungs-Flow, keine Unternehmensseite, keine Zahlungslogik. Das war so vorgegeben.
