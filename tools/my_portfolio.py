# -*- coding: utf-8 -*-
"""Liest das eigene Depot aus input/michi_h/md_portolio.md, bewertet es mit Yahoo-Kursen
und Beckers letzten Einschätzungen und schreibt:

    portfolio/mein_depot.md        Handlungsempfehlung (Markdown)
    website/data/mine.json         Daten für die Webseite (Charts)

Zeilenformat in der Depot-Datei (Stück und Kaufkurs optional):
    LULU gekauft am 01.09.2026
    CRWD gekauft am 02.09.2026 10 Stück zu 203,42
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "website"))
sys.path.insert(0, str(ROOT / "tools"))
import yahoo  # noqa: E402
from assets_data import ASSETS, STAND  # noqa: E402

SRC = ROOT / "input" / "michi_h" / "md_portolio.md"
OUT_MD = ROOT / "portfolio" / "mein_depot.md"
OUT_JSON = ROOT / "website" / "data" / "mine.json"

LINE = re.compile(
    r"^\s*[-*]?\s*([A-Z0-9][A-Z0-9.\-]{0,9})\s+gekauft\s+am\s+(\d{1,2})\.(\d{1,2})\.(\d{4})"
    r"(?:.*?(\d+(?:[.,]\d+)?)\s*(?:Stück|Stk|x))?(?:.*?zu\s+(\d+(?:[.,]\d+)?))?", re.I)


def parse():
    rows = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        m = LINE.match(line)
        if m:
            t, d, mo, y, qty, px = m.groups()
            rows.append({"ticker": t.upper(), "date": f"{y}-{int(mo):02d}-{int(d):02d}",
                         "qty": float(qty.replace(",", ".")) if qty else None,
                         "buy": float(px.replace(",", ".")) if px else None})
    return rows


def pct(v):
    return "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")


def num(v):
    return "–" if v is None else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None


def analyse(pos, h):
    i = next((k for k, d in enumerate(h["dates"]) if d >= pos["date"]), len(h["dates"]) - 1)
    buy = pos["buy"] or h["close"][i]
    price = h["price"]
    since = h["close"][i:]
    return {
        **pos,
        "name": next((x["name"] for x in ASSETS if x["t"] == pos["ticker"]), h["name"]), "currency": h["currency"], "symbol": h["symbol"],
        "buy": round(buy, 2), "buyAssumed": pos["buy"] is None, "buyDate": h["dates"][i],
        "price": price, "perf": round((price / buy - 1) * 100, 2),
        "maxSince": max(since), "minSince": min(since),
        "ma200": h["ma200"], "vsMa200": h["vsMa200"], "ma50": round(sma(h["close"], 50), 2),
        "hi52": h["hi52"], "lo52": h["lo52"], "chg1y": h["chg1y"],
        "dates": h["dates"][i:], "close": since,
    }


# --------------------------------------------------------------- Empfehlungslogik
def recommend(a, becker):
    """Regelwerk nach Beckers Prozess: 'Würde ich die Position heute neu kaufen?'
    Ja → Halten · Ja, aber zu groß/zu weit gelaufen → Trimmen · Nein, These intakt → Halten mit Stop ·
    Nein, These kaputt → Verkaufen. Ergänzt um die 200-Tage-Linie als Trendfilter."""
    t, v200, perf = a["ticker"], a["vsMa200"] or 0, a["perf"]
    if t == "CRWD":
        stop = round(max(a["ma50"], a["price"] * 0.88), 2)
        return {
            "aktion": "Teilgewinn sichern", "cls": "reduzieren",
            "kurz": f"Etwa ein Drittel verkaufen, Rest mit Stop bei ~{num(stop)} USD laufen lassen.",
            "warum": [
                f"{pct(perf)} seit Kauf in rund fünf Wochen und {pct(v200)} über der 200-Tage-Linie – eine Übertreibung, wie Becker sie bei Meta über Covered Calls zu Geld gemacht hat (ein Drittel ausgebucht, Rest laufen lassen).",
                "Neu in KW41: Becker führt CRWD wieder auf der 2030-Watchlist (Block B, 'möglicher neuer Top-Performer') – in KW39 hieß es noch 'zu stark gelaufen, nicht mehr einsteigen'. Gekauft hat er sie nicht; die These bleibt bei ihm also positiv, der Einstiegskurs ist ihm zu hoch. Deshalb: Kern halten, Übertreibung teilweise verkaufen, kein Nachkauf.",
                "Das Geschäftsmodell ist intakt (starker Burggraben) – deshalb kein Komplettverkauf, sondern Gewinnmitnahme plus nachgezogener Stop.",
                f"Stop-Vorschlag: das höhere von 50-Tage-Linie ({num(a['ma50'])}) und −12 % vom aktuellen Kurs ({num(a['price'] * 0.88)}). Wer Optionen handelt: Covered Call auf ein Drittel wie Becker bei Meta.",
            ],
        }
    if t == "IBB":
        return {
            "aktion": "Halten", "cls": "halten",
            "kurz": f"Laufen lassen wie Becker; Nachkauf erst nahe der 200-Tage-Linie (~{num(a['ma200'])} USD).",
            "warum": [
                f"Deckungsgleich mit Becker: IBB liegt mit 4 % im 2030-Depot (Block B), Status im KW41-Sheet ausdrücklich 'HALTEN' – er erwartet durch KI 'viele positive Entwicklungen' in der Wirkstoffforschung.",
                f"Seit Kauf {pct(perf)} – normales Rauschen bei einem Sektor-ETF. Der Trend ist intakt ({pct(v200)} über der 200-Tage-Linie, {pct(a['chg1y'])} auf Jahressicht).",
                "Als breiter ETF diversifiziert die Position die beiden Einzelaktien. Biotech profitiert zusätzlich von fallenden Zinsen – Beckers Kernszenario für Q4.",
                "UCITS-Alternative für EU-Anleger: iShares Nasdaq US Biotechnology (2B70, IE00BYXG2H39).",
            ],
        }
    if t == "LULU":
        stop = round(a["lo52"] * 0.97, 2)
        return {
            "aktion": "Stop setzen / nicht nachkaufen", "cls": "reduzieren",
            "kurz": f"Nicht verbilligen. Harte Verkaufsmarke knapp unter dem 52-Wochen-Tief (~{num(stop)} USD); bei Erholung über ~{num(a['ma50'])} USD (50-Tage-Linie) neu bewerten.",
            "warum": [
                f"{pct(perf)} seit Kauf, {pct(v200)} unter der 200-Tage-Linie und nahe dem 52-Wochen-Tief ({num(a['lo52'])}). Es gibt noch keine Bodenbildung.",
                "Becker verkauft konsequent, wenn eine Aktie unter der 200-Tage-Linie bleibt und kein Momentum zeigt (Vista Energy, Cameco, MP Materials). Sein Learning aus KW41 (zu Micron): 'Eine Aktie, die auf starke Zahlen nicht reagiert, warnt dich.' Und: 'Ob du im Plus oder im Minus bist, ist keine Information.'",
                "Die direkte Analogie Nike spielt Becker bewusst nur über kleine Call-Optionen (Risiko auf die Prämie begrenzt) – und die liegen in KW41 bei −44 %; er räumt ein, 'zu früh dran' gewesen zu sein. Zusätzlich hat Berenberg Nike am 06.10. auf Sell abgestuft. Sportartikel-Turnarounds sind derzeit nicht gefragt.",
                "Der Burggraben (Marke, Netto-Cash) ist nicht kaputt – deshalb 'halten mit Stop' statt sofort verkaufen. Wer die These nicht mehr klar in 30 Sekunden erklären kann, sollte die Position nach Beckers Regel ganz schließen.",
            ],
        }
    # generische Regel für weitere Positionen
    if v200 > 40:
        return {"aktion": "Teilgewinn sichern", "cls": "reduzieren", "kurz": "Weit über der 200-Tage-Linie – Gewinne teilweise mitnehmen.", "warum": []}
    if v200 < -15:
        return {"aktion": "Stop setzen", "cls": "reduzieren", "kurz": "Deutlich unter der 200-Tage-Linie – Ausstieg definieren.", "warum": []}
    return {"aktion": "Halten", "cls": "halten", "kurz": "Trend intakt.", "warum": []}


def write_md(items, total_perf, weights_note):
    becker_map = {a["t"]: a for a in ASSETS}
    lines = [
        "# 👤 Mein Depot – Handlungsempfehlung",
        "",
        f"**Datenbasis:** `input/michi_h/md_portolio.md` · Kurse Yahoo Finance vom {items[0]['asof']} · Becker-Reports {STAND}",
        "",
        "> Keine Anlageberatung. Die Empfehlungen wenden Balthasar Beckers Regelwerk (200-Tage-Linie, 'Würde ich heute neu kaufen?', Gewinne laufen lassen, Verlierer begrenzen) und den Buffett-Check auf deine Positionen an.",
        "",
        "## 📊 Überblick",
        "",
        "| Position | Kauf am | Kaufkurs | Kurs | seit Kauf | vs. 200T | Empfehlung | Steckbrief |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for a in items:
        lines.append(f"| {a['name']} ({a['ticker']}) | {a['buyDate'][8:]}.{a['buyDate'][5:7]}.{a['buyDate'][:4]} | "
                     f"{num(a['buy'])}{'*' if a['buyAssumed'] else ''} {a['currency']} | {num(a['price'])} {a['currency']} | "
                     f"{pct(a['perf'])} | {pct(a['vsMa200'])} | **{a['reco']['aktion']}** | [{a['ticker']}](assets/{a['ticker']}.md) |")
    lines += [
        "",
        f"\\* Kaufkurs = Yahoo-Schlusskurs am Kauftag (in der Depot-Datei nicht angegeben). {weights_note}",
        "",
        f"**Depot-Performance seit Kauf:** {pct(total_perf)}",
        "",
    ]
    for a in items:
        r = a["reco"]
        b = becker_map.get(a["ticker"], {})
        lines += [f"## {a['ticker']} – {r['aktion']}", "", f"**{r['kurz']}**", ""]
        lines += [f"- {w}" for w in r["warum"]]
        if b:
            lines += ["", f"*Buffett-Check:* Burggraben **{b.get('moat', ('n/a',))[0]}** · *Becker-Status:* {b.get('woche', '–')}"]
        lines.append("")
    lines += [
        "## 🏋️ Depotstruktur nach Becker-Barbell",
        "",
        "- **Es fehlt der Beta-Kern.** Alle drei Positionen sind Wachstums- bzw. Satellitenwerte. Becker hält den Großteil des Vermögens im Beta-Depot (Ziel: max. ~20 % Drawdown) und nur einen kleineren Teil in solchen Wetten.",
        "- **Bausteine aus Beckers Beta-Depot als Orientierung:** Qualität ohne KI-Klumpen (BRK-B, RSP gleichgewichteter S&P 500, NOBL Dividenden-Aristokraten), Gold ~20 % (GLD/EWG2), Bitcoin 5-10 % (IBIT), Liquidität ~20 % (XEON, TLT).",
        "- **Gewinne umschichten:** Ein Teilverkauf bei CRWD wäre genau Beckers Regel 'Gewinne aus Alpha regelmäßig ins Beta umschichten'.",
        "- **Mehr Daten = bessere Empfehlung:** Mit Stückzahl und Kaufkurs je Zeile (z. B. `CRWD gekauft am 02.09.2026 10 Stück zu 203,42`) rechnet die Seite echte Gewichte und Euro-Werte.",
        "",
        "## 🌐 Makro-Kontext (Becker, KW41 – 09.10.2026)",
        "",
        "- Becker rechnet 60 : 40 – 60 % Jahresendrallye, 40 % baldiger Crash. Er stellt sich auf beides ein: Gewinner mit engen Stopps laufen lassen, Reserve für den Crash halten.",
        "- Seine klarste Wenn-dann-Regel: Steigen 2- und 10-jährige Renditen (aktuell ~4,8 % / ~5,3 %) weiter, ist der Bullenmarkt vorbei. Ein weiter steigender Dollar wäre das Bärenmarkt-Signal.",
        "- Gewinnwachstum im S&P kommt fast nur aus Tech und Energie, die Breite läuft nicht – das trifft Konsumwerte wie LULU und begünstigt Tech-Gewinner wie CRWD. Für die Breite (RSP, NOBL) erwartet Becker einen Catch-up bei fallenden Zinsen.",
        "",
        "---",
        "[⬅️ Dashboard](index.md) | *Keine Anlageberatung.*",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = parse()
    if not rows:
        raise SystemExit(f"Keine Positionen in {SRC} gefunden (Format: 'TICKER gekauft am TT.MM.JJJJ').")
    items = []
    for r in rows:
        h = yahoo.fetch_history(r["ticker"])
        a = analyse(r, h)
        a["asof"] = h["asof"][:10]
        a["reco"] = recommend(a, None)
        items.append(a)

    have_qty = all(a["qty"] for a in items)
    if have_qty:
        invested = sum(a["qty"] * a["buy"] for a in items)
        value = sum(a["qty"] * a["price"] for a in items)
        for a in items:
            a["weight"] = round(a["qty"] * a["price"] / value * 100, 1)
        note = "Gewichte aus Stückzahl × Kurs."
    else:
        invested, value = len(items), sum(a["price"] / a["buy"] for a in items)
        for a in items:
            a["weight"] = round((a["price"] / a["buy"]) / value * 100, 1)
        note = "Ohne Stückzahlen wird ein gleicher Kaufbetrag je Position angenommen."
    total = round((value / invested - 1) * 100, 2)

    write_md(items, total, note)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"total": total, "note": note, "generated": date.today().isoformat(), "items": items},
                                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Mein Depot: {len(items)} Positionen, Performance {pct(total)} -> {OUT_MD}")
    for a in items:
        print(f"  {a['ticker']:5} {pct(a['perf']):>9}  {a['reco']['aktion']}")


if __name__ == "__main__":
    main()
