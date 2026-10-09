---
name: multi-asset-investor-wiki
description: Transformiert Depot-Rohdaten in ein strukturiertes Markdown-Wiki. Analysiert die Assets fundamental nach Warren Buffett und makroökonomisch nach Balthasar Becker.
version: 1.2.0
---

# Multi-Asset Investor Wiki (Buffett & Becker Framework)

Dieser Skill weist Claude an, ein Aktiendepot einzulesen, Risiken zu bewerten und ein lokales, cross-verlinktes Markdown-Wiki (Index + Einzelseiten) zu erstellen. Die Analyse erfolgt strikt aus der Sicht zweier Denkrichtungen: Value Investing und Makro-/Liquiditäts-Zyklen.

## Aktivierungs-Auslöser
Wird automatisch getriggert bei:
- "Erstelle mir ein Portfolio-Wiki nach Buffett und Becker Regeln."
- "Analysiere mein Depot auf Zentralbank-Liquidität und Moat."
- Bereitstellung von Depot-Listen mit der Bitte um Erstellung von Markdown-Dateien.

## Anweisungen für Claude

### 1. Verzeichnisstruktur
Erstelle im Projektordner die Struktur:
- `portfolio/index.md` (Zentrales Dashboard)
- `portfolio/assets/[TICKER].md` (Detailseite je Wertpapier)

### 2. Dashboard-Generierung (`portfolio/index.md`)
Die Index-Seite muss das Depot aggregieren und strategisch einordnen:
- **Gesamtwert & Stichtag**
- **Die Core-Satellite-Architektur (Becker Barbell):** Zeige die Aufteilung in:
  - *Beta-Portfolio (ca. 90%):* Breite ETFs, Anleihen, defensive Basiswerte zur Kapitalsicherung.
  - *Alpha-Portfolio (ca. 10%):* High-Risk-Einzelaktien, Krypto, asymmetrische Wetten.
- **Zentrale Asset-Tabelle:** Name, Ticker, Depot-Anteil (%), Performance, Link zu `assets/[TICKER].md`.
- **Makro- & Sentiment-Check:** Kurzer Kommentar, wie das Depot bei steigender/fallender Zentralbank-Liquidität performt.

### 3. Einzelblatt-Generierung (`portfolio/assets/[TICKER].md`)
Erstelle für jedes Asset ein standardisiertes Markdown-File:

```markdown
# [Asset Name] ([Ticker])

## 📊 Depot-Kennzahlen
- **Depot-Anteil:** [X]% (Klassifizierung: [Beta-Core / Alpha-Satellit])
- **Positionswert:** [X] € (Anzahl: [X] * Kurs: [X] €)
- **Kaufpreis / Performance:** [X] € / [+/- X]%

## 🏛️ Das Warren Buffett Fundament (Value Check)
- **Burggraben (Economic Moat):** Hat das Unternehmen eine monopolartige Preissetzungsmacht oder hohe Wechselkosten? (Bewertung: Stark / Schwach / Keiner)
- **Circle of Competence:** Ist das Geschäftsmodell so simpel, dass man es in 3 Sätzen erklären kann? [Erklärung einfügen]
- **Management & Verschuldung:** Agiert das Management im Sinne der Aktionäre? Ist die Nettoverschuldung/EBITDA gesund (< 3)?

## 🌊 Der Balthasar Becker Zyklus-Check (Makro & Asymmetrie)
- **Korrelation mit Globaler Liquidität:** Profitiert das Asset überproportional von Gelddrucken/Zinssenkungen (z. B. Tech, Krypto, Broker)?
- **Asymmetrisches Risikoprofil:** Handelt es sich um eine "kleine Bombe" mit begrenztem Downside, aber 5x–10x Upside-Potenzial?
- **Antizyklischer Status:** Befindet sich der Wert im Allzeithoch (Vorsicht vor Sentiment-Übertreibung) oder wurde er in einer Krise unberechtigt abgestraft?

## 📌 Eigene Notizen & Kauf-/Verkaufslimits
- *Mein Fairer Wert (Intrinsic Value):* [X] €
- *Nachkaufmarke bei Liquiditäts-Dip:* [X] €

---
[⬅️ Dashboard](../index.md) | *Keine Anlageberatung. Stand: [DATUM]*
```

### 4. Code- & Link-Disziplin
- Dateinamen immer in UPPERCASE Ticker (z.B. `AAPL.md`, `BTC.md`).
- Alle Links müssen als relative Pfade fehlerfrei funktionieren.
