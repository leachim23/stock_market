---
name: multi-asset-investor-wiki
description: Liest Balthasar-Becker-Reports (PDF) und eigene Depots ein, pflegt ein Markdown-Wiki mit Steckbriefen (Buffett- und Becker-Check), bewertet jede Depotposition (Kaufen/Halten/Trimmen/Verkaufen) nach der verbindlichen Barbell-Strategie (85 % defensiver Anker / 15 % aggressiver Satellit, keine Mitte), erzeugt je Depot eine Kaufempfehlung mit vier datierten Meinungen und baut daraus eine statische Webseite mit Yahoo-Finance-Kursen und Charts (GitHub Pages).
version: 2.5.0
---

# Multi-Asset Investor Wiki (Buffett & Becker Framework)

Dieser Skill pflegt ein Portfolio-Wiki und eine Webseite auf Basis der wöchentlichen Pure-Alpha-Reports von Balthasar Becker und der eigenen Depots unter `input/`. Die Analyse folgt zwei Denkrichtungen: Value Investing (Buffett) und Makro-/Liquiditätszyklen (Becker). Ergänzt wird sie um Analystenkonsens, Fundamentaldaten und Momentum von Yahoo Finance.

Alle Ausgaben sind Bildungs- und Analysezwecke, **keine Anlageberatung**. Das steht auf jeder Seite.

## 0. Verbindliche Anlagestrategie: Barbell (Hantel-Modell)

**Vorrang:** Diese Strategie ist der Rahmen für alle Bewertungen und Empfehlungen zu den eigenen Depots. Becker, Analysten, Fundamental und Momentum bleiben die Signalgeber für die Auswahl **innerhalb** der beiden Enden. Beckers eigene Depotaufteilung (Beta/2030/Alpha) gilt nur als Quelle für Signale, nicht als Zielallokation.

### Kernphilosophie
Strikte Trennung von maximalem Kapitalschutz und aggressivem Alpha-Sizing. Das Mittelfeld (moderates Risiko, moderate Upside) wird bewusst eliminiert. Das Portfolio soll gegen „Schwarze Schwäne“ (Marktcrashs) widerstandsfähig sein und trotzdem die Chance auf exponentielle Gewinne behalten.

### Ziel-Allokation
| Ende | Anteil am Gesamtkapital | Fokus |
|---|---|---|
| **Defensiver Anker** | **85 %** | Absoluter Kapitalerhalt, hohe Liquidität, minimale Volatilität |
| **Aggressiver Satellit** | **15 %** | Asymmetrisches Chance-Risiko-Profil: Verlust auf max. 15 % des Gesamtdepots begrenzt, Upside unbegrenzt |

### Asset-Klassen-Matrix
**A. Ultradefensives Ende (85 %)**
- Tagesgeld / Geldmarkt-ETFs: unmittelbare Liquidität, Zinsmitnahme (z. B. XEON).
- Kurzlaufende Staatsanleihen mit AAA-Rating: maximaler Schutz vor Emittentenausfall (z. B. kurzlaufende Bund- oder US-Treasury-ETFs, Laufzeit bis ca. 3 Jahre).
- Physisches Gold: systemischer Anker gegen Inflation und Währungskrisen (physisch hinterlegte ETCs wie EWG2 oder Gold im Zollfreilager). **Goldminen zählen nicht dazu.**
- Optional **höchstens ein** breit gestreuter Welt-ETF (z. B. VWCE) mit niedriger Volatilität.

**B. Ultraaggressives Ende (15 %)**
- Kryptowährungen: Bitcoin/Ethereum sowie kleine, spekulative Altcoins (auch über Bitcoin-ETFs/ETPs oder Krypto-Treasury-Aktien).
- Wachstums- und Micro-Cap-Aktien: junge Unternehmen in disruptiven Sektoren (KI, Biotech, CleanTech, Quantencomputing, Robotik), oft vor der Profitabilitätsschwelle.
- Derivate/Optionen: gezielte Hebelinstrumente oder Long-Volatility-Optionen (vgl. Beckers Long Calls und weit aus dem Geld liegende SPX-Puts).

### Risikomanagement & Rebalancing
- **Hard Stop:** Fällt der aggressive Teil durch Kursverluste unter **10 %** des Gesamtdepots, wird er **nicht** blind nachgekauft. Erst die Investment-Thesen je Position neu bewerten.
- **Take-Profit:** Steigt der aggressive Teil durch eine Rallye über **25 %** des Gesamtdepots, wird konsequent rebalanciert: Gewinne abschöpfen und in den defensiven Anker umschichten.
- **Intervall:** Überprüfung und Rebalancing **quartalsweise**, um Handelskosten zu sparen und Gewinnern Raum zu lassen. Wöchentliche Becker-Updates lösen nur Einzelentscheidungen aus (Verkauf bei Thesenbruch oder Stop), kein Rebalancing.

### Ausschlusskriterien (die ignorierte Mitte)
- Keine mittelprächtigen Dividendenaktien mit hohem zyklischem Risiko.
- Keine Unternehmensanleihen mit mittlerem Rating (BBB oder schlechter).
- Keine aktiven Mischfonds mit moderater Rendite bei moderatem Risiko.

### Anwendung im Projekt
Jede Position bekommt zusätzlich eine **Barbell-Rolle**: `Anker`, `Satellit` oder `Mitte`.

| Rolle | Typische Positionen | Hinweis |
|---|---|---|
| Anker | Geldmarkt (XEON), kurzlaufende AAA-Staatsanleihen, physisches Gold (EWG2, GLD), **ein** Welt-ETF (VWCE) | Ein zweiter oder weiterer breiter Aktien-ETF (z. B. IS3S, RSP, XDEM) ist **nicht** Anker, sondern Mitte. |
| Satellit | Krypto (IBIT, Metaplanet, SharpLink), Wachstums- und Micro-Caps (z. B. CRDO, OUST, IONQ, INFQ, ENRD, POET), Optionen | Auch Tech-Einzelwerte mit hohem Beta. |
| Mitte | Etablierte Large Caps und Konglomerate (META, GOOGL, AMZN, MCD, BRK-B, MKL), Dividenden-ETFs (NOBL, SPYD), Sektor- und Themen-ETFs (Tech, Healthcare, Wasser, Halbleiter), Goldminen (GDXJ/G2XJ), langlaufende Anleihen (TLT), Rohstoff-ETCs | Ob eine Large-Cap Satellit oder Mitte ist, im Zweifel anhand von Volatilität/Beta und Becker-Einordnung begründen und den Nutzer fragen. |

Auswertung je Depot:
1. **Ist-Verteilung** Anker / Satellit / Mitte (ohne Stückzahlen gleichgewichtet, mit Hinweis) gegen die Zielwerte 85 / 15 / 0 stellen.
2. **Rebalancing-Status:** Satellit < 10 % → Hard Stop (Thesen prüfen, nicht nachkaufen). Satellit > 25 % → Take-Profit (Gewinne in den Anker). Mitte > 0 % → schrittweiser Abbau in Erholungen hinein.
3. **Entscheidungen** (Abschnitt 4) um die Rolle ergänzen: Positionen der Mitte bekommen standardmäßig „Trimmen“ bzw. „Abbauen in Erholung“, sofern nicht „Verkaufen“ greift. Nachkaufen nur bei Anker- oder Satellit-Positionen und nur, wenn deren Ende unter dem Ziel liegt.
4. **Kaufempfehlung** (Abschnitt 5): Kern-Bausteine nur aus dem Anker-Universum (Geldmarkt, kurzlaufende AAA-Staatsanleihen, physisches Gold, höchstens ein Welt-ETF). Einzelaktien-Plätze nur für echte Satelliten. Kandidaten der Mitte (z. B. RSP, NOBL, BRK-B, TLT) mit Grund „Barbell: ignorierte Mitte“ ausschließen.

**Umsetzung im Code:** `tools/decision.py` (`role_of`, `style_of`, `barbell`, `decide`, `synthesis`, Ziele in `TARGET`, Schwellen `SAT_HARD_STOP`/`SAT_TAKE_PROFIT`, Makro-Stand in `MAKRO`), Auswahl in `tools/portfolios.py` (`buy_for`), Anker-Kandidaten in `tools/buy_reco.py` (XEON = Geldmarkt, EXVM = eb.rexx Germany 0-1yr als kurzlaufende AAA-Bundesanleihen – US-Treasuries sind nicht mehr AAA, 4GLD = Xetra-Gold, VWCE = Welt-ETF). Rollenregel für Aktien: Satellit bei Becker-Alpha, Wachstumsbranche (Quanten, Robotik, Krypto, Kernenergie), Beta ≥ 1,6 oder Börsenwert < 50 Mrd. bei Beta ≥ 1,0; sonst Mitte. Explizite Zuordnungen in `ROLE_OVERRIDE`. Große Einzelaktien (GOOGL, AMZN, META) zählen derzeit zur Mitte – Änderung nur nach Rücksprache.

## Aktivierungs-Auslöser
- „Lies die neuen PDFs ein / Update aus `PDF_input/<ordner>`“
- „Erstelle / aktualisiere Steckbriefe“, „Portfolio-Wiki nach Buffett und Becker“
- „Bewerte mein Depot“, „Kaufempfehlung“, „kaufen, verkaufen, halten oder trimmen?“
- Neue oder geänderte Depot-Datei unter `input/<name>/`
- „Webseite updaten / pushen“
- Neue Unterlagen zum Makro-Crashkurs in `PDF_input/markro_crash_kurs/`

## Projektstruktur

| Pfad | Inhalt |
|---|---|
| `PDF_input/` und Unterordner (z. B. `PDF_input/09102026/`) | Becker-Reports: `2030_Depot_KWxx`, `Alpha_Depot_KWxx`, `Beta_Depot_KWxx`, `Pure_Alpha_Weekly_Recap_KWxx`. **Nie committen.** |
| `PDF_input/markro_crash_kurs/` | Folien des Becker-Makro-Crashkurses (10 Sessions, 06.10.–05.11.2026). **Nie committen.** |
| `.claude/skills/portfolio-analyzer/makro_crashkurs.md` | Zusammenfassung des Crashkurses je Einheit (Referenz für Abschnitt 0b) |
| `input/<name>/*.md` | Eigene Depots, ein Ordner je Person (z. B. `michi_h`, `michi_g`). Wird automatisch erkannt. |
| `tools/assets_data.py` | Strukturierte Becker-Daten: `STAND`, `DEPOTS`, `ASSETS` (je Position), `SOLD`, `WATCH`, `MAKRO` |
| `tools/generate_wiki.py` | Erzeugt `portfolio/index.md` und `portfolio/assets/[TICKER].md` aus `assets_data.py` |
| `tools/buy_reco.py` | Bausteine der Kaufempfehlung: `CANDIDATES` (Becker-Universum), `WEB` (datierte Webquellen), Wertung, Fundamental-/Momentum-Meinung |
| `tools/decision.py` | Gesamturteil je Depotposition und Gesamtanalyse je Depot |
| `tools/portfolios.py` | Liest alle `input/<name>/`, bewertet, erzeugt Kaufempfehlung, schreibt `portfolio/depots/` und `website/data/depots/` |
| `website/yahoo.py` | Yahoo-Finance-Anbindung: Kurse (2 Jahre), Analystenkonsens, Fundamentaldaten, Live-Kurse |
| `website/build.py`, `charts.js`, `style.css` | Baut die statische Seite nach `docs/` (GitHub Pages) |
| `website/serve.py` | Lokaler Server: Refresh der gesamten Pipeline + Live-Kurse auf `http://localhost:8765` |

## 0b. Becker-Makro-Framework (aus dem Makro-Crashkurs)

Details und Belege stehen in [makro_crashkurs.md](makro_crashkurs.md). Diese Datei vor jeder Gesamtanalyse lesen. Kommen neue Kurs-PDFs hinzu, die Datei je Einheit ergänzen (Tabelle „Stand“ fortschreiben) und neue, analyserelevante Regeln hier nachtragen.

**Die These in einem Satz:** Schulden wachsen schneller als die Wirtschaft, also muss dauerhaft Geld gedruckt werden (etwa 8 % Geldentwertung pro Jahr). Gleichzeitig bündelt KI die Produktivitätsgewinne bei wenigen Unternehmen. Gewinner sind die Besitzer von Aktien (vor allem der wenigen Plattform-Gewinner), Gold und Krypto. Verlierer sind Arbeitseinkommen und Sparguthaben.

**Was das für die Analyse heißt:**
1. **Hürde von 8 % pro Jahr:** Jede Anlage muss zuerst die Geldentwertung schlagen. In der Gesamtanalyse je Depot angeben, welcher Anteil in Anlagen steckt, die nominal unter dieser Hürde liegen (Geldmarkt, kurzlaufende Anleihen), und was das real kostet.
   - **Spannung zur Barbell-Strategie (Abschnitt 0):** Der 85-%-Anker (Geldmarkt, kurzlaufende Anleihen) verliert nach Beckers Rechnung real Kaufkraft. Die Barbell-Strategie hat trotzdem Vorrang, weil sie auf Kapitalerhalt und Überleben im Crash zielt. Innerhalb des Ankers deshalb **physisches Gold** als Schutz gegen Geldentwertung gezielt einplanen und den Zielkonflikt offen ausweisen.
2. **Liquidität vor Wirtschaft:** Erst steigt die Liquidität und Aktien reagieren, dann zieht die Wirtschaft an, dann entsteht Inflation, dann wird die Liquidität verknappt. Den Makro-Check je Depot daran ausrichten: Liquiditätswachstum, Verhältnis von Schulden zu Liquidität (kritisch ab etwa 2,2), Zinsstrukturkurve, Dollar.
3. **Schwache Wirtschaft, starke Börse:** Eine Konjunkturschwäche allein ist kein Verkaufssignal. Entscheidend ist, ob die Liquidität nachzieht.
4. **Konzentration der Gewinner (Bessembinder):** Wenige Aktien erzeugen fast die gesamte Wertschöpfung, die mittlere Aktie verliert. Im Satellit Positionen ohne klare Gewinner-These kritisch prüfen; bei breiten ETFs bedenken, dass ihre Rendite von wenigen Titeln abhängt.
5. **Marktpsychologie:** Euphorie ist das größte Risiko, Kapitulation die größte Chance. Sentiment (Angst-und-Gier-Index, Konsumentenvertrauen) in den Makro-Check aufnehmen; Kaufempfehlungen in Euphorie-Phasen vorsichtiger formulieren.
6. **Drei Preistreiber:** Geldentwertung (nominal), Produktivität (real), Emotion (nur die Welle). Begründungen danach trennen: Steigt eine Aktie nur nominal oder wächst der Gewinn real?
7. **Zwei Alpha-Quellen (Session 08):**
   - **Prozyklisch** (Trendfolge, z. B. Alpha-Depot, Ausbruchskäufe): Einstieg über klare Filter, Risiko über den **Stop** begrenzen (200-Tage-Linie bzw. Beckers Stop-Marken).
   - **Antizyklisch** (in die Übertreibung kaufen, z. B. 2030-Block C, MCD, SOFI, TLT, NOBL): Risiko über **Cost Average und Positionsgröße** steuern, **nicht** über einen harten Stop.
   - Die Entscheidungsregeln (Abschnitt 4) müssen zwischen beiden unterscheiden. Bei antizyklischen Positionen keine automatische Verkaufsempfehlung nur wegen eines Abstands unter der 200-Tage-Linie; stattdessen prüfen, ob die These noch trägt, und die Positionsgröße begrenzen.
8. **Positionsgröße vor Titelauswahl:** Asymmetrische Wetten klein halten, sodass ein Totalverlust verkraftbar ist. Das passt zur Grenze von 15 % für den Satelliten.
9. **Rücksetzer sind normal:** Der S&P 500 fällt fast jedes Jahr zweistellig. Rücksetzer im Anker und im Kern sind kein Verkaufsgrund, sondern eine Gelegenheit für das Rebalancing.
10. **Nie aus dem Spiel fallen:** Risikomanagement hat Vorrang vor Rendite. Ziel ist ein positiver Erwartungswert über viele Entscheidungen, nicht der einzelne Treffer. Regeln vorher festlegen statt im Moment entscheiden.
11. **Steuern:** Der Zinseszins nach Steuern bestimmt das Endvermögen. Bei Trimm- und Verkaufsempfehlungen auf mögliche Steuerfolgen (realisierte Gewinne) hinweisen. Keine Steuerberatung.

**Umsetzung im Code:** Punkt 7 in `decision.style_of`/`decide` (antizyklisch = Anker, Becker-Beta-Depot, 2030-Block C; dort kein Stop-Verkauf, sondern Cost Average bzw. Abbau in Erholungen), Punkte 1, 2, 5, 11 in `decision.synthesis` und den Begründungen (8-%-Hürde, Makro-Stand aus `MAKRO`, Sentiment, Steuerhinweis bei Trimmen/Verkaufen). `MAKRO` bei jedem neuen Becker-Report aktualisieren.

## Standard-Workflow

1. **PDFs einlesen** (siehe unten), `tools/assets_data.py` aktualisieren.
2. `python tools/generate_wiki.py` – Wiki und Steckbriefe.
3. `python website/yahoo.py` – Kursreihen für alle Steckbriefe.
4. `python tools/portfolios.py` – Depots bewerten, Kaufempfehlungen erzeugen.
5. `python website/build.py` – Seite nach `docs/` bauen.
   (Die Schritte 3 bis 5 erledigt auch `python website/serve.py`.)
6. **Visuell prüfen:** Headless-Screenshot mit Edge, dann ansehen:
   `"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --disable-gpu --window-size=1300,2000 --screenshot=<scratchpad>/x.png "file:///D:/dev/protfolio/docs/<seite>.html"`
7. Nur auf Nachfrage committen und pushen (siehe „Veröffentlichung“).

## 1. PDFs einlesen

- Extraktion: `pdftotext -enc UTF-8 -layout <pdf> <scratchpad>/<name>.txt`. **Immer `-enc UTF-8`**, sonst gehen die Umlaute kaputt.
- Doppelte PDFs per `md5sum` erkennen (z. B. `(1)`/`(2)`-Kopien) und nur einmal lesen.
- Zuerst den **Weekly Recap** lesen (Abschnitt 2 „Änderungen im Balthasar-Portfolio“), dann die Depot-PDFs: Übersichtstabelle, `ALLOC`-Zeilen und die Seite „Trigger & Watchlist“.
- Daraus in `tools/assets_data.py` aktualisieren:
  - `STAND` (Datum und KW) und `DEPOTS[...]` (Cash, Blöcke, Beschreibung).
  - Je Position: `hist` um die neue KW verlängern (Tupel KW38, KW39, …), `alloc`, `status` (2030 seit KW41: HALTEN/AUFBAUEN/REDUZIEREN; Alpha: EINSTEIGEN/LAUFEN LASSEN), `woche`. Für Alpha zusätzlich `entry`/`now`/`pl`.
  - Neue Positionen als neues `dict(...)` mit allen Feldern (siehe Steckbrief), verkaufte Positionen nach `SOLD`.
  - `WATCH` und `MAKRO` aus Recap und Watchlist-Seiten.
- Bei neuen KW-Spalten auch die Tabellenüberschrift in `generate_wiki.py` erweitern.
- In `tools/buy_reco.py` `BECKER_DATE` auf das Report-Datum setzen und die `signal`-Werte der `CANDIDATES` anpassen (`kaufen`, `pruefen`, `halten`, `warten`, `nein`).
- Becker-Aussagen als Paraphrase oder kurzes Zitat übernehmen und als seine Meinung kennzeichnen. Nichts erfinden: Wo das PDF keine Werte hat, „n/a“ oder den letzten bekannten Wert mit Hinweis eintragen.

## 2. Wiki und Steckbriefe

- `portfolio/index.md`: Stichtag, Quellen, Barbell-Architektur (Beta-Core / 2030 Langfrist-Core / Alpha-Satellit), Asset-Tabellen je Depot, Makro- und Sentiment-Check, Watchlist, verkaufte Positionen, Links zu den eigenen Depots.
- `portfolio/assets/[TICKER].md` (Dateiname = Ticker in GROSSBUCHSTABEN, `BRK.B` → `BRK-B.md`). Erste Zeile `<!-- meta: {...} -->` für die Webseite. Abschnitte:
  - 📊 Depot-Kennzahlen (Anteil, Klassifizierung, Einstieg → Kurs, WKN/ISIN, Gewichtungsverlauf je KW)
  - 🗣️ Einschätzung Balthasar Becker (Chance, Risiko, Wochenstatus, Quelle PDF)
  - 🏛️ Buffett-Check: Burggraben (Stark/Mittel/Schwach/Keiner), Circle of Competence in 3 Sätzen, Management & Verschuldung (Nettoverschuldung/EBITDA < 3). Bei ETFs Hinweis „bewertet den Korb“.
  - 🌊 Becker-Zyklus-Check: Liquiditätskorrelation, Asymmetrie, antizyklischer Status
  - 📌 Eigene Notizen: fairer Wert `[eigene Eingabe]`, Nachkaufmarke nur mit konkretem Becker-Trigger (z. B. Stop-Marken)
  - Fußzeile: `[⬅️ Dashboard](../index.md) | *Keine Anlageberatung. Stand: …*`
- Positionswert und Stückzahl bleiben „n/a“: Die PDFs enthalten nur Gewichtungen.

## 3. Eigene Depots (`input/<name>/`)

Erkannte Zeilenformate (Aufzählungszeichen werden ignoriert):
- Name aus dem Depotauszug: `• ALPHABET INC.CL.A DL-,001`. Nennwerte wie `DL-,001` oder `EO -,09` sind **kein** Kaufkurs; als Kaufkurs zählt nur eine reine Zahl am Zeilenende.
- Name plus Kaufkurs in EUR: `BMW kauf 100,16`
- Ticker plus Datum: `LULU gekauft am 01.09.2026` (Kaufkurs = Yahoo-Schluss am Kauftag)
- WKN-Zeile, dann Name mit ISIN und Preis: `A1103G` / `Xtrackers MSCI World Momentum … (ISIN: IE00BL25JP72)64,4`

Auflösung über `RESOLVE` in `tools/portfolios.py`: Regex (oder ISIN) → Ticker, Yahoo-Symbol, Name, Sektor, Art. ISIN-Einträge stehen vorn, damit Namensmuster sie nicht falsch treffen.
- UCITS-ETFs mit Euro-Notiz bevorzugen: Xetra `.DE`, sonst Paris `.PA`. Prüfen, ob eine Kurshistorie vorhanden ist (`.SG` hat oft keine).
- Neue Namen über die Yahoo-Suche finden: `https://query2.finance.yahoo.com/v1/finance/search?q=<Name oder ISIN>`.
- Reine WKNs findet die Yahoo-Suche nicht, und finanzen.net blockiert Abfragen (403). Dann als „nicht aufgelöst“ markieren und den Nutzer um Name oder ISIN bitten.
- Kurse in EUR umrechnen (`EURUSD=X` usw.). Kaufkurse in der Depot-Datei gelten als EUR.
- **Plausibilitätsprüfung:** Ist der Kaufkurs mehr als 8-mal höher oder niedriger als der aktuelle Kurs, wird er markiert und nicht in die Performance gerechnet (z. B. vertauschte Zeilen). Echte Kursstürze bis −90 % bleiben drin.
- **Die Depot-Dateien des Nutzers nie selbst ändern.** Auffälligkeiten melden und nachfragen.
- Ohne Stückzahlen: gleiche Gewichtung je Position, auch bei den Sektorgewichten. Nicht aufgelöste Positionen zählen nicht mit.

## 4. Entscheidung je Depotposition (`tools/decision.py`)

Vier Meinungen, jeweils +1/0/−1:
1. **Becker:** AUFBAUEN oder Alpha EINSTEIGEN = +1; REDUZIEREN oder von Becker verkauft = −1; HALTEN oder LAUFEN LASSEN = 0; Watchlist je nach Signal. UCITS-Pendants über `EQUIV` zuordnen (2B70 → IBB, G2XJ → GDXJ, SPYD → NOBL).
2. **Analysten:** Yahoo-Konsensnote ≤ 2,2 = +1, ≥ 3 = −1.
3. **Fundamental (Buffett-Kennzahlen):** Qualität (Eigenkapitalrendite ≥ 15 %, Marge ≥ 15 %, Verschuldung/Eigenkapital ≤ 1, freier Cashflow > 0) plus Bewertung (erwartetes KGV, PEG, Cashflow-Rendite). ETFs nach KGV des Korbs, Anleihe-ETFs nach Rendite (≥ 4 % = attraktiv), Gold- und Krypto-ETFs „nicht anwendbar“.
4. **Momentum:** Rendite über 3, 6 und 12 Monate gegen SPY plus Trend (Kurs > 50-Tage-Linie > 200-Tage-Linie).

Entscheidungsregel, in dieser Reihenfolge:
- **Verkaufen:** Becker hat verkauft · LULU/NKE (Sportartikel-Turnaround ohne Bestätigung) · mehr als 20 % unter der 200-Tage-Linie, Momentum ≤ 0 und keine Becker-Unterstützung · mindestens 3 negative Meinungen (hält Becker die Position noch: nur Trimmen).
- **Trimmen:** Becker REDUZIEREN · mehr als 100 % Gewinn seit Kauf · Familie ≥ 40 % des Depots und die Position mehr als 10 % über der 200-Tage-Linie · mehr als 60 % über der 200-Tage-Linie ohne Becker-Unterstützung.
- **Nachkaufen:** Becker +1, mindestens 3 positive Meinungen, zwischen −10 % und +25 % zur 200-Tage-Linie, Sektor < 10 %, Familie < 25 %.
- **Halten:** alles andere. Unter der 200-Tage-Linie mit Stop; junge Aktien ohne 200-Tage-Linie mit Stop unter dem Tief.

Becker-Makro (Abschnitt 0b, Punkt 7): Bei antizyklischen Positionen ersetzt Cost Average den harten Stop. Die Verkaufsregel „mehr als 20 % unter der 200-Tage-Linie“ gilt nur für prozyklische Positionen.

Barbell-Vorrang (Abschnitt 0): Diese Regeln gelten innerhalb der Barbell-Rollen. Positionen der „ignorierten Mitte“ werden abgebaut, Nachkäufe gibt es nur für Anker- oder Satellit-Positionen, deren Ende unter dem Ziel liegt.

Becker-Grundsätze, die zu beachten sind: „Ob du im Plus oder Minus bist, ist keine Information“, also entscheidet der Trend und nicht der Einstand. Reduzieren in Erholungen, nicht in die Schwäche. Erst verkaufen und trimmen, dann gestaffelt kaufen.

Gesamtanalyse je Depot (`synthesis`): Becker-Makro, Struktur (größte Familie, Anteil unter der 200-Tage-Linie), Abgleich mit Becker, fehlender Krisenpuffer (Anleihen/Gold), Klumpenrisiko, Aktionsplan.

## 5. Kaufempfehlung je Depot

- **Universum:** `CANDIDATES` aus Beckers Depots und Watchlists. Bereits gehaltene Titel und deren UCITS-Pendants sind ausgeschlossen.
- **Vier datierte Meinungen** je Kandidat: Becker (Report-Datum) · Analysten (Yahoo-Konsens plus Webquellen aus `WEB`) · Fundamental · Momentum.
- **Frische-Regel (max. 4 Tage):**
  - Becker-Signale, die älter als 4 Tage sind, zählen nur halb und werden rot markiert. Neue PDFs anfordern.
  - Webquellen, die älter als 4 Tage sind, werden ignoriert und als „wegen Alter ignoriert“ ausgewiesen.
  - Die Seite zeigt im Browser ein Ablauf-Banner, sobald „gültig bis“ überschritten ist.
- **Webquellen recherchieren:** WebSearch (z. B. Analysten-Updates, Sektor-Ausblicke), dann jeden Eintrag mit Datum, Aussage, Tendenz (+/−/0) und Quelle in `WEB` eintragen. Zweitmeinungen, die Becker widersprechen, bewusst aufnehmen (z. B. Kursziel-Senkungen bei Hausbauern). Quellen in der Antwort verlinken.
- **Wertung:** Becker-Signal × Frische + Analysten + Web + Trend (Nähe zur 200-Tage-Linie, keine überdehnten Werte) + 0,8 × Fundamental + 0,8 × Momentum − Sektorgewicht/5.
- **Diversifikation:**
  - Sektor mit ≥ 10 % oder Familie (z. B. Technologie: Halbleiter, Software, KI-Hardware, Robotik, Quantencomputing, Tech-ETFs) mit ≥ 25 % Depotgewicht: kein Kauf.
  - Höchstens ein Titel je Sektor und Familie, insgesamt 3 Einzelaktien + 2 Kern-Bausteine (ETFs/Anleihen/BRK-B, doppelt gewichtet).
  - Ausschluss bei Becker „nein“ oder wenn Becker und Analysten sich widersprechen (außer bei Becker „kaufen“).
- Jeder Ausschluss bekommt einen Grund und das Meinungsbild („x/4 positiv“).
- **Barbell-Vorrang (Abschnitt 0):** Kern-Bausteine nur aus dem Anker-Universum, Einzelaktien nur als echte Satelliten, Kandidaten der Mitte ausschließen. Die neuen Mittel so verteilen, dass sich das Depot dem Ziel 85/15 nähert. Liegt der Satellit bereits über 15 %, fließt neues Kapital vollständig in den Anker.
- **Zwei Szenarien je Depot** (gleiche Kandidaten und Meinungen, unterschiedliche Aufteilung; auf der Seite per Umschalter):
  - **Szenario A · Barbell strikt:** wie oben – fehlende Anker-Bausteine zuerst (85 % bzw. 100 %), Satelliten nur unter 15 %, Mitte ausgeschlossen.
  - **Szenario B · Offensiv (ohne Barbell-Anker):** kein Anker-Anteil – Geldmarkt, kurzlaufende Staatsanleihen, physisches Gold und Welt-ETF sind ausgeschlossen. 100 % in die diversifizierte Auswahl mit vier Meinungen: bis zu 3 Einzelaktien + 2 Kern-Bausteine (Gewicht 2:1), max. ein Titel je Sektor/Familie, keine Sektoren ≥ 10 % bzw. Familien ≥ 25 %, **Mitte erlaubt**. Weicht bewusst von der verbindlichen Barbell-Strategie ab (kein Krisenpuffer) und ist immer als Alternative mit höherem Risiko zu kennzeichnen. Umsetzung: `select_offensive` in `tools/portfolios.py`, Ausschlussgründe in `excludedB`, Anteile in `allocB`.
- **Offene Grundsatzfrage:** Amazon steht derzeit im Sektor „Konsum zyklisch“, wirtschaftlich ist es eher Cloud (AWS). Vor einer Umklassifizierung den Nutzer fragen.

## 6. Webseite

- Seiten: Dashboard (Kacheln je Becker-Depot und eigenem Depot, Filter, Diagramm zur 200-Tage-Linie, Tabelle mit Sparklines), `assets/[TICKER].html` (Kurschart mit 200-Tage-Linie, Zeitraumwahl, Kennzahlen), `depot-<id>.html` (Aktionsplan, Gesamtanalyse, Sektorgewichte, Performance seit Kauf, Entscheidungstabelle mit vier Meinungen), `kaufempfehlung-<id>.html` (Diversifikation, Karten mit vier Meinungen, Nicht empfohlen, Marktstimmung), `overview.html`.
- **Charts:** eigenes SVG ohne Abhängigkeiten (`charts.js`: `lineChart`, `divergingBars`, `sparkline`, `indexChart`). Vor Änderungen an Charts den Skill `dataviz` laden. Farben aus der validierten Referenzpalette: Beta = Aqua, 2030 = Blau, Alpha = Orange; Diverging Blau/Rot. Hell- und Dunkelmodus.
- **Live-Kurse** nur, wenn die Seite über `serve.py` auf localhost läuft. Auf `file://` und GitHub Pages zeigt sie den gespeicherten Stand.
- Ausgabe nach `docs/` inklusive `.nojekyll`.

## 7. Veröffentlichung (GitHub)

- Repo: `https://github.com/leachim23/stock_market.git`, Branch `main`, Pages aus `/docs`, Adresse `https://leachim23.github.io/stock_market/`.
- **Nur auf ausdrückliche Bitte pushen.** `.gitignore` schließt `PDF_input/` und `*.pdf` aus. Vor jedem Push prüfen: `git ls-files | grep -ci '\.pdf$'` muss 0 ergeben.
- Hinweis an den Nutzer: Das Repo ist öffentlich und enthält Zusammenfassungen von Beckers kostenpflichtigen Reports sowie die eigenen Depots. Vor der ersten Veröffentlichung nachfragen.
- Commit-Nachrichten enden mit der Co-Authored-By-Zeile aus der System-Erinnerung.

## Technische Fallstricke (Windows / Git Bash)

- Längere Python-Patches mit Anführungszeichen **nicht als Heredoc** in Bash übergeben (bricht bei `'`). Stattdessen das Skript per Write-Tool ins Scratchpad legen und mit `python <datei>` ausführen.
- Konsolenausgabe mit Sonderzeichen (z. B. `−`): `sys.stdout.reconfigure(encoding="utf-8")` oder `python -X utf8`.
- Vor großen Patches eine Sicherungskopie ins Scratchpad legen. Patches mit `assert s.count(alt) == 1` absichern.
- `rm` mit Shell-Variablen wird blockiert: neue Ordner anlegen statt löschen, oder `"${VAR:?}"` verwenden.
- Yahoo `quoteSummary` braucht Cookie + Crumb (`yahoo._opener()`). Der Vortagesschluss für Live-Kurse ist der vorletzte Tagesschluss, nicht `chartPreviousClose` aus dem 5-Tage-Fenster.
- Yahoo liefert für ETFs keinen Analystenkonsens. Dort stützen Trend, Fundamental (KGV/Rendite) und Webquellen die Meinung.
