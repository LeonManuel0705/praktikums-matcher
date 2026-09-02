# Ergebnis des Code-Reviews

Ein Fanout aus 25 Agenten hat den Prototyp entlang von fünf Dimensionen geprüft: Nebenläufigkeit,
Datenintegrität, Bewertungslogik, Sicherheit und Frontend. Jeder Befund ging danach an einen
Gegenprüfer, dessen Standardannahme war, dass die Behauptung falsch ist.

25 Rohbefunde, 19 haben die Gegenprüfung überstanden. Die folgenden habe ich selbst am Code
nachvollzogen und behoben.

## Schwerwiegend

| Befund | Was passiert wäre | Behoben durch |
|---|---|---|
| `PUT /api/weights` ohne Anmeldung | Jeder ohne Konto konnte die Bewertungsgewichte aller Nutzer verstellen | Endpunkt hängt an `current_user` |
| Gewichte wurden vor der Prüfung geschrieben | Eine abgelehnte Anfrage hinterließ trotzdem kaputte Gewichte | Erst auf einer Kopie prüfen, dann übernehmen |
| Ort-Score sprang an der Umkreisgrenze nach oben | Adlershof mit 33 km bekam 94 %, Berlin-Mitte mit 27 km nur 86 % | Stetige, monoton fallende Kurve, per Test über alle Orte abgesichert |
| Bereichserkennung traf Wortfragmente | „Detailhandel" galt als KI/Tech, weil „ai" in „detail" steckt | Vergleich nur noch an Wortgrenzen |
| Monatsbereiche über den Jahreswechsel | „Dezember bis Februar 2027" wurde zu Februar bis Dezember 2027 | Jahr der früheren Monate wird zurückgerollt |
| Freitext ungetrennt im Agenten-Prompt | Ein Schüler hätte dem Suchagenten Anweisungen unterschieben können | Freitext steht in einem markierten Block, Trennmarken werden entfernt, Länge begrenzt |
| **Agentenprozess lief ohne jede Eindämmung** | siehe eigenen Abschnitt unten | Sandkasten-Verzeichnis, minimale Umgebung, gesperrte Werkzeuge, keine geerbten Einstellungen, kein MCP |
| stderr des Agenten wurde nie geleert | Ab 64 KiB blockiert das Kind, der Suchwinkel läuft ins Zeitlimit | stderr wird nebenher in einer eigenen Aufgabe geleert |
| stdout-Zeilen über 64 KiB | Eine große Werkzeugausgabe beendete den Suchwinkel mit einem Fehler | Puffergrenze auf 16 MiB, überlange Zeilen werden übersprungen |
| Fehler in einem Suchwinkel | Die drei anderen liefen weiter und schrieben in eine bereits beendete Suche | Geschwister werden abgebrochen und abgewartet |
| `process.kill()` traf nur das direkte Kind | Enkelprozesse blieben als Waisen zurück | Eigene Prozessgruppe, Abbruch per `killpg` |
| Neuer Nutzer kam nicht an den Speichern-Knopf | Ohne Profil war Speichern gesperrt und die Suche antwortete mit 400 | Ohne gespeichertes Profil gilt das Formular als ungespeichert |
| `ProfileForm` übernahm das geladene Profil nicht | Nach dem Anmelden standen Standardwerte statt der eigenen Angaben im Formular | Formular gleicht sich mit dem Prop ab |
| Ein fehlgeschlagener Poll beendete die Abfrage | Die laufende Suche wirkte eingefroren | Bis zu vier Wiederholungen mit wachsendem Abstand |

## Mittel

| Befund | Behoben durch |
|---|---|
| Zeitraum wurde aus der Fließtext-Beschreibung gelesen | Nur noch die Zeitraum-Felder zählen |
| Monatsgenaues Angebot wurde auf 180 Tage gedehnt | Dehnung entfernt, ein Monat bleibt ein Monat |
| Mehrdeutige Ortspräfixe hingen an der Einfügereihenfolge | Längster Treffer gewinnt, deterministisch |
| `rescore` rechnete alte Suchen gegen das neue Profil | Nutzt den Profil-Schnappschuss der Suche, `?use_current_profile=true` erzwingt das alte Verhalten |
| Entdopplung übersah URL-Varianten | Vergleich über eine kanonische URL ohne Tracking-Parameter und `www` |
| Registrierung prüfte die E-Mail außerhalb einer Transaktion | `IntegrityError` wird abgefangen und als 409 beantwortet |
| Suchen blieben nach einem Serverneustart ewig auf „läuft" | Beim Start werden sie abgeschlossen und protokolliert |
| Umkreis-Karte zeigte Anker des alten Ortes | Karte leert sich, wenn das Ortsfeld leer ist |
| Zustand blieb nach dem Abmelden stehen | Fehler, Hinweise und Suchbezug werden zurückgesetzt |

## Der schwerste Befund im Detail

Der Gegenprüfer hat nicht nur gelesen, sondern die Binary mit genau den Flags gestartet, die im Code
standen. Ergebnis: `--allowedTools` schränkt den Werkzeugsatz **nicht** ein, es erweitert nur Freigaben.
Der Agentenprozess bekam damit:

| | vorher | nachher |
|---|---|---|
| Werkzeuge insgesamt | 77 | 21 bis 24 |
| davon Bash, Read, Write, Edit, Task | alle vorhanden | keins |
| MCP-Werkzeuge (Gmail, Drive, Kalender) | 49 | 0 |
| Arbeitsverzeichnis | Projektwurzel mit `app.db` samt Passwort-Hashes | eigenes leeres Verzeichnis unter `TMPDIR` |
| Umgebung | vollständig geerbt, inklusive API-Schlüssel | sieben Variablen, keine Schlüssel |
| Einstellungen | globale Allow-Liste mit Shell-Freigaben und Lesezugriff auf das Home-Verzeichnis | keine geerbten Einstellungen |

Der gefährliche Weg war nicht der eigene Freitext, sondern die Anzeigen selbst: der Agent soll ja fremde
Seiten öffnen. Wer eine Jobbörse oder eine dort verlinkte Anzeige kontrolliert, hätte Anweisungen in den
Seitentext schreiben können, die in einem Kontext mit vollen lokalen Rechten landen.

Behoben durch `--disallowedTools`, `--setting-sources ""`, `--strict-mcp-config`, ein eigenes
Arbeitsverzeichnis und eine gefilterte Umgebung. Nachgemessen: der Agent findet weiterhin echte Angebote,
sieht aber kein einziges gefährliches Werkzeug mehr. Fünf Tests halten das fest.

## Nicht übernommen

- **Herkunft eines Angebots komme vom Modell.** Stimmt nicht: `origin` wird im Backend aus dem
  Suchwinkel gesetzt, das Modell hat darauf keinen Einfluss.
- **Der UNIQUE-Index auf `offers` greife nie.** Er ist als Rückfall gedacht, weil vorher schon in
  Python entdoppelt wird. Der zweite Teil des Befunds, URL-Varianten, ist oben behoben.
- Fehlendes Rate-Limiting, HTTPS, CSRF-Tokens: bewusste Grenzen eines lokalen Prototyps, im README
  als solche dokumentiert.
