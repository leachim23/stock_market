# -*- coding: utf-8 -*-
"""Bausteine der Kaufempfehlung (genutzt von tools/portfolios.py): Becker-Signale vs. Zweitmeinung (Yahoo-Analystenkonsens + datierte Webquellen),
gefiltert auf Diversifikation gegenüber dem eigenen Depot.

    python tools/buy_reco.py   -> portfolio/kaufempfehlung.md + website/data/buy.json

Frische-Regel: Eine Quelle zählt nur voll, wenn sie höchstens MAX_AGE Tage alt ist.
Ältere Becker-Signale werden halb gewichtet und markiert; ältere Webquellen werden ignoriert.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "website"))
sys.path.insert(0, str(ROOT / "tools"))
import yahoo  # noqa: E402

MAX_AGE = 4          # Tage
SLOTS = {"Einzelaktie": 3, "Kern-Baustein": 2}   # Becker-Barbell: Satelliten + stabiler Kern
# Übergeordnete Familien: höchstens ein Titel je Familie (verhindert z. B. mehrere Halbleiter-nahe Werte)
FAMILY = {"Halbleiter": "Technologie", "Robotik & Automatisierung": "Technologie", "Messtechnik & Photonics": "Technologie",
          "Software & Cybersecurity": "Technologie", "Breiter Markt (gleichgewichtet)": "US-Aktien breit",
          "Dividenden-Qualität": "US-Aktien breit"}
OUT_MD = ROOT / "portfolio" / "kaufempfehlung.md"
OUT_JSON = ROOT / "website" / "data" / "buy.json"
BECKER_DATE = "2026-10-09"   # letzter Becker-Report: PDF_input/09102026 (KW41)

# Diversifikations-Buckets für die eigenen Positionen
HOLD_BUCKET = {"LULU": "Konsum zyklisch", "CRWD": "Software & Cybersecurity", "IBB": "Gesundheit / Biotech"}


def family(bucket):
    return FAMILY.get(bucket, bucket)


def slot(c):
    return "Kern-Baustein" if c["kind"] == "ETF" or c["t"] == "BRK-B" else "Einzelaktie"

# --------------------------------------------------------------------------- Becker-Universum
# signal: kaufen (aktiver Nachkauf/Ausbau) · pruefen (Watchlist/Prüfung) · warten (nur bei Rücksetzer) · nein
CANDIDATES = [
    # --- Anker-Bausteine (Barbell, SKILL.md Abschnitt 0)
    dict(t="XEON", name="Xtrackers EUR Overnight Rate Swap (Geldmarkt)", bucket="Geldmarkt", kind="ETF", signal="kaufen",
         becker="Beta-Depot: Liquidität ist eine strategische Position (Ziel ~20 %) – Munition für den Crash; Becker hält 8 % im XEON."),
    dict(t="EXVM", name="iShares eb.rexx Government Germany 0-1yr", bucket="Kurzlaufende Staatsanleihen (AAA)", kind="ETF", signal="pruefen",
         becker="Nicht in Beckers Depots (er bevorzugt taktisch lange US-Anleihen). Im Barbell-Anker gefordert: kurzlaufende AAA-Staatsanleihen – Bund statt Treasury (USA nicht mehr AAA)."),
    dict(t="4GLD", name="Xetra-Gold (physisch hinterlegt)", bucket="Gold physisch", kind="ETF", signal="kaufen",
         becker="Beta-Depot: Gold ~19 % als monetäres Fundament gegen Geldentwertung (Debasement Trade); Becker will auf günstigere Gold-Produkte wechseln – Xetra-Gold ist physisch hinterlegt."),
    dict(t="VWCE", name="Vanguard FTSE All-World", bucket="Breiter Markt (Welt)", kind="ETF", signal="pruefen",
         becker="Nicht in Beckers Beta-Depot (er meidet marktgewichtete Indizes wegen des KI-Klumpens). Im Barbell-Anker optional: höchstens ein Welt-ETF."),
    dict(t="GOOGL", name="Alphabet", bucket="Kommunikation & Internet", kind="Aktie", signal="kaufen",
         becker="2030-Depot, Status AUFBAUEN: gefällt Becker derzeit am besten – er ist 'ausdrücklich bullisch' auf die Aktie."),
    dict(t="AMZN", name="Amazon", bucket="Konsum zyklisch", kind="Aktie", signal="kaufen",
         becker="2030-Depot, Status AUFBAUEN: 'sehr interessant'; Becker erwägt, Apple zugunsten Amazon aufzulösen."),
    dict(t="ASML", name="ASML Holding", bucket="Halbleiter", kind="Aktie", signal="kaufen",
         becker="2030-Depot, Status AUFBAUEN: sollte weiter von KI profitieren."),
    dict(t="RSP", name="Invesco S&P 500 Equal Weight ETF", bucket="Breiter Markt (gleichgewichtet)", kind="ETF", signal="kaufen",
         becker="Beta-Depot: am 09.10. von 5 auf 8 % aufgestockt – 'kein Trade, sondern ein Investment'; weiterer Ausbaukandidat. UCITS: SP2Q (IE00BNGJJT35)."),
    dict(t="NOBL", name="ProShares S&P 500 Dividend Aristocrats", bucket="Dividenden-Qualität", kind="ETF", signal="kaufen",
         becker="Beta-Depot: ausdrücklicher Ausbaukandidat (Catch-up der Marktbreite bei fallenden Zinsen). UCITS-Näherung: USDV (IE00B6YX5D40)."),
    dict(t="TLT", name="iShares 20+ Year Treasury Bond ETF", bucket="Anleihen", kind="ETF", signal="kaufen",
         becker="Beta-Depot: 'der nächste Nachkauf' – XEON soll schrittweise in TLT fließen; Anleihen bei ~5 % taktisch interessant, im Crash Fluchtort. UCITS: DTLA (IE00BFM6TC58)."),
    dict(t="BRK-B", name="Berkshire Hathaway B", bucket="Finanzen & Zahlungsverkehr", kind="Aktie", signal="halten",
         becker="Beta-Depot: Kern des Aktienteils (18 %), unverändert – kein aktiver Ausbau genannt."),
    dict(t="RGLD", name="Royal Gold", bucket="Gold & Edelmetalle", kind="Aktie", signal="pruefen",
         becker="2030-Watchlist: steht oben auf der Liste möglicher Neuaufnahmen – langfristig von steigenden Goldpreisen profitieren."),
    dict(t="GLD", name="SPDR Gold Shares", bucket="Gold physisch", kind="ETF", signal="warten",
         becker="Beta-Depot: Nachkauf nur bei deutlicher Schwäche; Wechsel auf gebührengünstigeres Produkt geplant. UCITS: EWG2."),
    dict(t="V", name="Visa", bucket="Finanzen & Zahlungsverkehr", kind="Aktie", signal="pruefen",
         becker="2030-Watchlist (antizyklisch beobachtet) – KI- und Stablecoin-Profiteur; Käufe erst nach McDonald's-Abbau."),
    dict(t="DHI", name="D.R. Horton", bucket="Immobilien & Hausbau", kind="Aktie", signal="pruefen",
         becker="Alpha-Watchlist: Hausbauer sind für Becker 'die beste Möglichkeit, fallende Zinsen zu spielen'; Buffett hat stark gekauft. Trigger: fallende Zweijahreszinsen."),
    dict(t="LEN", name="Lennar", bucket="Immobilien & Hausbau", kind="Aktie", signal="pruefen",
         becker="Alpha-Watchlist: wie D.R. Horton – antizyklische Zinswette, Aufnahme bei fallenden Zweijahreszinsen erwogen."),
    dict(t="GEV", name="GE Vernova", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="pruefen",
         becker="Alpha-Watchlist Stromversorger (GEV, ETN, PWR): nach dem KI-Trade der Bereich mit dem zweitmeisten Momentum."),
    dict(t="ETN", name="Eaton", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="pruefen",
         becker="Alpha-Watchlist Stromversorger: Elektrifizierung und Rechenzentrums-Stromversorgung."),
    dict(t="CRDO", name="Credo Technology", bucket="Halbleiter", kind="Aktie", signal="kaufen",
         becker="Alpha +57 %, 'läuft weiterhin sehr stark'; zusätzlich auf der 2030-Watchlist Block B."),
    dict(t="LITE", name="Lumentum", bucket="Halbleiter", kind="Aktie", signal="kaufen",
         becker="Alpha-Neukauf 06.10.: Photonik ist für Becker 'der nächste Trend im Chipbereich' – Ausbruchskauf mit engem Stop."),
    dict(t="KEYS", name="Keysight Technologies", bucket="Messtechnik & Photonics", kind="Aktie", signal="kaufen",
         becker="Alpha-Neukauf 06.10. (5 %) als Ausbruchskauf mit engem Ausstieg."),
    dict(t="MU", name="Micron Technology", bucket="Halbleiter", kind="Aktie", signal="warten",
         becker="Alpha 17 %: hat auf starke Zahlen kaum reagiert – Warnsignal. Für Neueinsteiger nur mit Stopp (960 oder 891 USD)."),
    dict(t="TER", name="Teradyne", bucket="Robotik & Automatisierung", kind="Aktie", signal="warten",
         becker="Alpha: geplante dritte Robotics-Position – Becker wartet auf einen günstigeren Einstieg."),
    dict(t="BE", name="Bloom Energy", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="halten",
         becker="Alpha 7 %: laufen lassen bis zum Bruch der 200-Tage-Linie."),
    dict(t="NVO", name="Novo Nordisk", bucket="Gesundheit / Biotech", kind="Aktie", signal="pruefen",
         becker="Alpha-/2030-Watchlist Healthcare (NVO, VRTX, NTRA, BNTX) – stark gefallene Qualität."),
    dict(t="XOM", name="Exxon Mobil", bucket="Energie & Öl", kind="Aktie", signal="nein",
         becker="KW41: Ölaktien meidet Becker bewusst – der Ölpreis hängt an politischen Entscheidungen, 'ein Münzwurf'."),
    dict(t="IBIT", name="iShares Bitcoin Trust", bucket="Krypto", kind="ETF", signal="warten",
         becker="Beta: über Zielquote, laufen lassen; ohne Liquidität erwartet Becker einen kräftigen Rücksetzer. UCITS-ETP: IB1T."),
    dict(t="PLTR", name="Palantir", bucket="Software & Cybersecurity", kind="Aktie", signal="pruefen",
         becker="KW41: 'eine der führenden Aktien des Marktes' (Leading Stock) – auf der Watchlist, nicht gekauft."),
]

# --------------------------------------------------------------------------- Zweitmeinung aus dem Web (datiert)
GLOBE = ("The Globe and Mail – U.S. Analyst Updates", "https://www.theglobeandmail.com/investing/markets/stocks/NOW/pressreleases/4992898/us-analyst-updates-october-6th-2026/")
STRONG = ("StrongBuy Analytics – Stock Market Outlook", "https://strongbuyanalytics.com/stock-market-outlook")
MARKETBEAT = ("MarketBeat – Homebuilders Are Down for the Year", "https://www.marketbeat.com/articles/homebuilders-are-down-for-the-year-is-wall-street-in-denial/")
GOOGLEFIN = ("Google Finance – GEV Analysten", "https://www.google.com/finance/labs/quote/GEV:NYSE")
SCHWAB = ("Schwab – Monthly Stock Sector Outlook", "https://www.schwab.com/learn/story/stock-sector-outlook")
WEB = {
    "GOOGL": [("2026-10-06", "Wells Fargo: Overweight bestätigt, Kursziel 411 → 417 USD.", "+", GLOBE),
              ("2026-10-09", "Kommunikationssektor (XLC −1,51 %) schwächster Sektor des Tages.", "−", STRONG)],
    "AMZN": [("2026-10-06", "Tigress Financial: Buy bestätigt, Kursziel 315 → 385 USD.", "+", GLOBE),
             ("2026-10-09", "Zyklischer Konsum (XLY +1,02 %) mit stärkster relativer Stärke.", "+", STRONG)],
    "KEYS": [("2026-10-06", "Goldman Sachs: Buy bestätigt, Kursziel 452 → 487 USD.", "+", GLOBE)],
    "CRDO": [("2026-10-09", "Halbleiter (SMH −0,65 %) unter den Nachzüglern des Tages.", "−", STRONG)],
    "MU":   [("2026-10-09", "Halbleiter (SMH −0,65 %) unter den Nachzüglern des Tages.", "−", STRONG)],
    "ASML": [("2026-10-06", "Gemischtes Bild bei Ausrüstern: KLA-Kursziel bei Morgan Stanley 253 → 227 gesenkt, TSMC 650 → 665 angehoben (Barclays).", "0", GLOBE)],
    "BRK-B": [("2026-10-06", "Versicherer mit überwiegend gesenkten Kurszielen (Chubb, AIG, Allstate bei Morgan Stanley).", "−", GLOBE)],
    "V":    [("2026-10-06", "Finanzwerte gemischt: Konsumkreditgeber und Broker mit gesenkten Zielen.", "0", GLOBE)],
    "XOM":  [("2026-10-06", "Raffinerien/Energie mit selektiver Unterstützung (Valero 323 → 441, PBF 74 → 91).", "+", GLOBE)],
    "DHI":  [("2026-10-06", "Barclays: Equal Weight, Kursziel 141 → 130 USD; Hausbauer insgesamt mit gesenkten Zielen (Pulte, Toll).", "−", GLOBE),
             ("2026-10-06", "Aktie bei 136,64 USD nahe 52-Wochen-Tief; Hypothekenzinsen ~7 % und 10-jährige zeitweise 5 % belasten.", "−", MARKETBEAT)],
    "LEN":  [("2026-10-06", "Wohnungsbau-Sektor mit Vorsicht: mehrere Kursziel-Senkungen bei Hausbauern.", "−", GLOBE)],
    "GEV":  [("2026-10-05", "20 Analysten: 16× Buy, 3× Hold, 1× Sell; Ø Kursziel ~1.232 USD.", "+", GOOGLEFIN)],
    "NVO":  [("2026-10-09", "Gesundheit (XLV +1,58 %) stärkster Sektor des Tages.", "+", STRONG)],
    "LITE": [("2026-10-09", "Halbleiter (SMH −0,65 %) unter den Nachzüglern des Tages.", "−", STRONG)],
    "RSP":  [("2026-10-09", "Breiter Markt: Bias bullish, Small Caps (IWM) und Futures höher, VIX tiefer.", "+", STRONG)],
    "TLT":  [("2026-10-09", "Am 12.10. (Columbus Day) Anleihemarkt geschlossen – geringe Liquidität.", "0", STRONG)],
    "*":    [("2026-10-06", "Analysten bevorzugen selektive Wachstumsstorys (Halbleiter, KI-Infrastruktur, Software), Gesundheit/Verteidigung/Kupfer mit Unterstützung; Wohnungsbau, Autohandel, Transport vorsichtig.", "0", GLOBE),
             ("2026-10-09", "Marktausblick für 12.10.: 'Bullish, with holiday-liquidity caveats' – Gesundheit (XLV +1,58 %) und Konsum zyklisch führen, Kommunikation/Halbleiter/Regionalbanken hinken.", "0", STRONG),
             ("2026-10-06", "Berenberg stuft Nike von Hold auf Sell ab (Ziel 27,50 USD) – negatives Signal für Sportartikel/LULU.", "−", GLOBE),
             ("2026-10-02", "Sektor-Ausblick: Industrie und Rohstoffe (Kupfer) favorisiert.", "+", SCHWAB)],
}

SIGNAL_SCORE = {"kaufen": 3.0, "pruefen": 1.5, "halten": 0.8, "warten": 0.5, "nein": -2.0}
SIGNAL_LABEL = {"kaufen": "Kaufen / Aufbauen", "pruefen": "Prüfen / Watchlist", "halten": "Halten (kein Ausbau)", "warten": "Nur bei Rücksetzer", "nein": "Nicht einsteigen"}


def age(d, today):
    return (today - date.fromisoformat(d)).days


def fresh_web(t, today):
    return [dict(date=d, text=x, tone=tone, source=s[0], url=s[1], age=age(d, today))
            for d, x, tone, s in WEB.get(t, []) if age(d, today) <= MAX_AGE]


def analyst_view(c, q, h):
    """Zweitmeinung als Wertung: Analystenkonsens (Aktien) bzw. Trend + Web (ETFs)."""
    if q and q.get("mean"):
        s = (3 - q["mean"]) * 1.5 + (q["upside"] or 0) / 15
        label = {"strong_buy": "Starker Kauf", "buy": "Kaufen", "hold": "Halten", "underperform": "Untergewichten", "sell": "Verkaufen"}.get(q["rating"], q["rating"] or "–")
        return s, label
    v = h.get("vsMa200") or 0
    s = 1.0 if -10 <= v <= 15 else 0.3 if v > 15 else 0.0
    return s, "kein Konsens (ETF) – Trend/Web"


def score(c, q, h, web, today):
    becker_age = age(BECKER_DATE, today)
    f_becker = 1.0 if becker_age <= MAX_AGE else 0.5
    sb = SIGNAL_SCORE[c["signal"]] * f_becker
    sa, alabel = analyst_view(c, q, h)
    sw = sum({"+": 0.4, "−": -0.4, "0": 0}[w["tone"]] for w in web)
    v = h.get("vsMa200")
    # Beckers Trendfilter: Kauf nahe/über der 200T-Linie, keine überdehnten Werte jagen
    st = 0 if v is None else 0.8 if -8 <= v <= 20 else -1.0 if v > 40 else -0.6 if v < -20 else 0.2
    return {"total": round(sb + sa + sw + st, 2), "becker": round(sb, 2), "analyst": round(sa, 2),
            "web": round(sw, 2), "trend": st, "analystLabel": alabel, "beckerAge": becker_age,
            "beckerFresh": becker_age <= MAX_AGE}


def agreement(c, sc, q):
    b_pos = c["signal"] in ("kaufen", "pruefen")
    a_pos = (q and q.get("mean") and q["mean"] <= 2.2) or (not (q and q.get("mean")) and sc["analyst"] >= 1)
    if b_pos and a_pos:
        return "Übereinstimmung"
    if not b_pos and not a_pos:
        return "Beide zurückhaltend"
    return "Divergenz"


if __name__ == "__main__":
    raise SystemExit("Kaufempfehlungen je Depot erzeugt jetzt: python tools/portfolios.py")


# --------------------------------------------------------------------------- 3. Meinung: Fundamentaldaten (Buffett)
def _pc(v):
    return f"{v * 100:.0f} %".replace(".", ",")


def fundamental_view(c, f):
    """Liefert (Wertung -1/0/+1, Label, Detailzeilen). Aktien: Qualität + Bewertung; ETFs: KGV bzw. Rendite."""
    if not f:
        return 0, "Keine Daten", []
    if c["bucket"] == "Anleihen":
        y = f.get("yield")
        if y is None:
            return 0, "Keine Daten", []
        return (1 if y >= 0.04 else 0), ("Attraktive Rendite" if y >= 0.04 else "Neutral"), [f"Ausschüttungsrendite {_pc(y)} (≥ 4 % = attraktiv)"]
    if c["bucket"] in ("Gold & Edelmetalle", "Krypto") and c["kind"] == "ETF":
        return 0, "Nicht anwendbar", ["Rohstoff/Krypto – keine Unternehmenskennzahlen"]
    if c["kind"] == "ETF":
        pe = f.get("trailingPE")
        if not pe:
            return 0, "Keine Daten", []
        det = [f"KGV des Korbs {pe:.1f}".replace(".", ",")] + ([f"Rendite {_pc(f['yield'])}"] if f.get("yield") else [])
        return (1, "Fair bewertet", det) if pe < 18 else (-1, "Teuer", det) if pe > 25 else (0, "Neutral", det)
    q, v, det = 0, 0, []
    roe, mg, de, fcf, mcap, fpe, peg = (f.get(k) for k in ("roe", "margin", "debtEq", "fcf", "mcap", "forwardPE", "peg"))
    if roe is not None:
        q += roe >= 0.15
        det.append(f"Eigenkapitalrendite {_pc(roe)}")
    if mg is not None:
        q += mg >= 0.15
        det.append(f"Nettomarge {_pc(mg)}")
    if de is not None:
        q += de <= 100
        det.append(f"Verschuldung/EK {de / 100:.1f}".replace(".", ","))
    if fcf is not None:
        q += fcf > 0
    if fpe and fpe > 0:
        v += 2 if fpe < 15 else 1 if fpe < 25 else -1 if fpe > 40 else 0
        det.append(f"KGV (erwartet) {fpe:.1f}".replace(".", ","))
    if peg:
        v += 1 if peg < 1.5 else -1 if peg > 3 else 0
        det.append(f"PEG {peg:.2f}".replace(".", ","))
    if fcf and mcap:
        fy = fcf / mcap
        v += fy >= 0.04
        det.append(f"FCF-Rendite {fy * 100:.1f} %".replace(".", ","))
    det.insert(0, f"Qualität {q}/4")
    total = q + v
    if total >= 5:
        return 1, "Positiv – Qualität zu fairem Preis", det
    if total <= 2:
        return -1, "Kritisch – teuer oder schwache Qualität", det
    return 0, "Neutral", det


# --------------------------------------------------------------------------- 4. Meinung: Momentum / relative Stärke
def momentum_view(h, spy):
    """Relative Stärke vs. S&P 500 (SPY) über 3/6/12 Monate + Trendstatus (Kurs > 50T > 200T)."""
    c, s = h.get("close") or [], spy.get("close") or []
    if len(c) < 64 or len(s) < 64:
        return 0, "Zu kurze Historie", [], {}
    ret = lambda a, n: (a[-1] / a[-n - 1] - 1) * 100 if len(a) > n else None
    rows, out = {}, 0
    for lbl, n in (("3M", 63), ("6M", 126), ("12M", 252)):
        a, b = ret(c, n), ret(s, n)
        if a is None or b is None:
            continue
        rows[lbl] = (round(a, 1), round(b, 1))
        out += a > b
    ma50 = sum(c[-50:]) / 50
    ma200 = sum(c[-200:]) / 200 if len(c) >= 200 else None
    trend = 0
    if ma200:
        trend = 1 if c[-1] > ma50 > ma200 else -1 if c[-1] < ma50 < ma200 else 0
    tlabel = {1: "Aufwärtstrend (Kurs > 50T > 200T)", -1: "Abwärtstrend (Kurs < 50T < 200T)", 0: "Trend uneinheitlich"}[trend]
    det = [f"{k}: {a:+.1f} % vs. S&P {b:+.1f} %".replace(".", ",") for k, (a, b) in rows.items()] + [tlabel]
    pts = out + trend
    if pts >= 3:
        return 1, "Stark – schlägt den Markt", det, rows
    if pts <= 0:
        return -1, "Schwach – hinkt dem Markt hinterher", det, rows
    return 0, "Neutral", det, rows


def opinion_votes(c, q, sc, fs, ms):
    """+1/0/-1 je Meinung: Becker, Analysten, Fundamental, Momentum."""
    b = {"kaufen": 1, "pruefen": 1, "halten": 0, "warten": 0, "nein": -1}[c["signal"]]
    if q and q.get("mean"):
        a = 1 if q["mean"] <= 2.2 else -1 if q["mean"] >= 3 else 0
    else:
        a = 1 if sc["analyst"] >= 1 else 0
    return {"becker": b, "analysten": a, "fundamental": fs, "momentum": ms}
