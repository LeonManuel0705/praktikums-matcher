# Taskplan Praktikums-Matcher

Stand: 2026-09-02

## Entscheidungen (bestätigt)
| Thema | Entscheidung |
|---|---|
| UI | FastAPI + eigenes Vite/React-Frontend, Liquid-Glass-Design |
| Datenquelle | Live-Recherche beim Klick auf "Suche starten" + verifizierter Grundstock in SQLite |
| Scoring | Deterministisch mit sichtbarer Aufschlüsselung, LLM-Re-Ranking zuschaltbar |
| Agent-Motor | Claude-Code-Binary headless, nutzt den bestehenden Login, kein API-Key nötig |

## Bausteine

### A. Fundament
- [x] A1 Projektgerüst, venv, FastAPI 0.141 auf Python 3.14 verifiziert
- [x] A2 SQLite-Schema: users, sessions, profiles, searches, search_events, offers, matches
- [x] A3 Auth: scrypt-Hashing, Session-Token als SHA-256, kein Klartext in der DB
- [x] A4 Geo: Gazetteer Berlin/Brandenburg + DE, Haversine, Fuzzy-Ortsauflösung
- [x] A5 Datumsparser für deutsche Zeitraumangaben inkl. Monatsbereiche und Saisons

### B. Matching
- [x] B1 Scorer: Interesse 40, Ort 25, Vergütung 15, Zeitraum 20, je mit Begründung
- [x] B2 Freitext-Keywords lokal auswerten
- [x] B3 Gewichte zur Laufzeit über die API veränderbar
- [x] B4 Unit-Tests für Scorer, Geo, Datumsparser

### C. Live-Agent
- [x] C1 Provider-Schnittstelle mit Fortschritts-Callback
- [x] C2 claude_cli-Provider: stream-json parsen, echte Suchschritte an die UI melden
- [x] C3 anthropic_api-Provider (greift bei gesetztem ANTHROPIC_API_KEY)
- [x] C4 tavily-Provider als dritte Option
- [x] C5 corpus-Provider als Offline-Fallback
- [x] C6 Registry: wählt automatisch den verfügbaren Provider
- [x] C7 Job-Runner: Suche asynchron, Ereignis-Log, Teilergebnisse sofort sichtbar
- [x] C8 Halluzinations-Bremse: Angebote ohne belegte Quelle werden markiert

### D. API
- [x] D1 Registrierung, Login, Logout, /api/me
- [x] D2 Profil lesen und speichern
- [x] D3 Suche starten, Status abfragen, Ergebnisse abrufen
- [x] D4 Grundstock-Suche ohne Live-Agent

### E. Frontend
- [x] E1 Design-System: Tokens, Glas-Flächen, runde Formen, Dark und Light
- [x] E2 Auth-Screen
- [x] E3 Profil-Formular in Schritten
- [x] E4 Live-Suchansicht mit mitlaufendem Agenten-Protokoll
- [x] E5 Ergebnisliste: Score-Ring, Kriterien-Balken, Link zur Quelle
- [x] E6 Animationen und Bewegungsreduktion respektieren

### F. Abschluss
- [x] F1 Grundstock aus der laufenden Recherche einspielen
- [x] F2 Ein Startbefehl für Backend und Frontend
- [x] F3 End-to-End im Browser durchklicken
- [x] F4 Adversarialer Code-Review und Design-Kritik
- [x] F5 README mit Kosten- und Grenzen-Hinweis

## Nach dem Review
- [x] G1 25 Befunde aus 5 Prüfdimensionen, 19 nach Gegenprüfung bestätigt, siehe [REVIEW.md](REVIEW.md)
- [x] G2 13 schwerwiegende und 9 mittlere Befunde behoben, 12 Regressionstests dazu
- [x] G3 LLM-Feinschliff für den Freitext nachgereicht, bewertet alle Treffer in parallelen Stapeln

## Kosten, auf Zuruf ergänzt
- [x] K1 Kosten je Suchwinkel gemessen statt geschätzt, Sonnet gegen Haiku verglichen
- [x] K2 Haiku als Standard, straffere Budgets, weniger Runden
- [x] K3 Suchwinkel laufen in Wellen mit Budgetprüfung vor dem Start
- [x] K4 Echte Kosten aus `total_cost_usd`, aufaddiert und in der Datenbank festgehalten
- [x] K5 Suchtiefe in der Oberfläche wählbar, Kosten laufen sichtbar mit
- [x] K6 Vertragstests für die beiden Provider ohne Schlüssel
- [x] K7 Von 1,54 USD auf 0,17 bis 0,33 USD je Suche

## Zugänglichkeit, auf Zuruf ergänzt
- [x] H1 Prüfung, wer sich bewerben darf: offen, nur_studierende, unklar
- [x] H2 Suchagenten melden Angebote mit Studienpflicht gar nicht erst
- [x] H3 Filter in der Ergebnisliste, Standard blendet Studienpflicht aus
- [x] H4 11 Tests für die Einstufung
- [x] H5 Zweite Recherche gezielt nach zugänglichen Angeboten

## Zusätzlich gebaut, nicht ursprünglich geplant
- [x] Grundstock als Vorwelle: 54 geprüfte Angebote sind sofort bewertet, die Liste ist nie leer
- [x] Sofort-Ausgabe je Treffer statt JSON erst am Schluss, überlebt auch ein Zeitlimit
- [x] Geo-Vorschau: Umkreis-Ringe mit echten Orten und Entfernungen aus dem Ortsverzeichnis
- [x] Herkunfts-Kennzeichnung je Karte: Grundstock oder gerade gefunden

## Erledigt im Hintergrund
- [x] Recherche-Fanout: 28 Agenten, 623 Werkzeugaufrufe, 57 belegte Angebote, 1 verworfen
