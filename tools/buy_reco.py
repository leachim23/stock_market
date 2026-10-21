# -*- coding: utf-8 -*-
"""Bausteine der Kaufempfehlung (genutzt von tools/portfolios.py): Inputgeber-Signale vs. Zweitmeinung (Yahoo-Analystenkonsens + datierte Webquellen),
gefiltert auf Diversifikation gegenüber dem eigenen Depot.

    python tools/buy_reco.py   -> portfolio/kaufempfehlung.md + website/data/buy.json

Frische-Regel: Eine Quelle zählt nur voll, wenn sie höchstens MAX_AGE Tage alt ist.
Ältere Inputgeber-Signale werden halb gewichtet und markiert; ältere Webquellen werden ignoriert.
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
SLOTS = {"Einzelaktie": 3, "Kern-Baustein": 2}   # Inputgeber-Barbell: Satelliten + stabiler Kern
# Übergeordnete Familien: höchstens ein Titel je Familie (verhindert z. B. mehrere Halbleiter-nahe Werte)
FAMILY = {"Halbleiter": "Technologie", "Robotik & Automatisierung": "Technologie", "Messtechnik & Photonics": "Technologie",
          "Software & Cybersecurity": "Technologie", "Breiter Markt (gleichgewichtet)": "US-Aktien breit",
          "Dividenden-Qualität": "US-Aktien breit"}
OUT_MD = ROOT / "portfolio" / "kaufempfehlung.md"
OUT_JSON = ROOT / "website" / "data" / "buy.json"
INPUTGEBER_DATE = "2026-10-16"   # letzter Inputgeber-Report: pdf/ (KW42)

# Diversifikations-Buckets für die eigenen Positionen
HOLD_BUCKET = {"LULU": "Konsum zyklisch", "CRWD": "Software & Cybersecurity", "IBB": "Gesundheit / Biotech"}


def family(bucket):
    return FAMILY.get(bucket, bucket)


def slot(c):
    return "Kern-Baustein" if c["kind"] == "ETF" or c["t"] == "BRK-B" else "Einzelaktie"

# --------------------------------------------------------------------------- Inputgeber-Universum
# signal: kaufen (aktiver Nachkauf/Ausbau) · pruefen (Watchlist/Prüfung) · warten (nur bei Rücksetzer) · nein
CANDIDATES = [
    # --- Anker-Bausteine (Barbell, SKILL.md Abschnitt 0)
    dict(t="XEON", name="Xtrackers EUR Overnight Rate Swap (Geldmarkt)", bucket="Geldmarkt", kind="ETF", signal="kaufen",
         inputgeber="Beta-Depot 9 %, Status EINSTEIGEN: Liquidität (21 %) ist die strategische Reserve für den Moment, in dem die Notenbank eingreifen muss."),
    dict(t="EXVM", name="iShares eb.rexx Government Germany 0-1yr", bucket="Kurzlaufende Staatsanleihen (AAA)", kind="ETF", signal="pruefen",
         inputgeber="Nicht in Inputgebers Depots (er schichtet Euro-Liquidität in US-Anleihen, 'eventuell auch kürzere Laufzeiten'). Im Barbell-Anker gefordert: kurzlaufende AAA-Staatsanleihen – Bund statt Treasury (USA nicht mehr AAA)."),
    dict(t="4GLD", name="Xetra-Gold (physisch hinterlegt)", bucket="Gold physisch", kind="ETF", signal="kaufen",
         inputgeber="Beta-Depot: Gold 18 % auf Zielallokation, langfristig 'wieder sehr attraktiv'. Xetra-Gold kam aus der Gruppe als Ersatz für EWG2 – Inputgeber: 'das kann sein'."),
    dict(t="VWCE", name="Vanguard FTSE All-World", bucket="Breiter Markt (Welt)", kind="ETF", signal="pruefen",
         inputgeber="Nicht in Inputgebers Beta-Depot (er meidet marktgewichtete Indizes wegen des KI-Klumpens). Im Barbell-Anker optional: höchstens ein Welt-ETF."),
    # --- 2030-Depot
    dict(t="GOOGL", name="Alphabet", bucket="Kommunikation & Internet", kind="Aktie", signal="kaufen",
         inputgeber="2030-Depot 10 %, Status AUFBAUEN: mit Amazon der interessanteste Wert – sollte sich auch in einem größeren Abverkauf sehr gut halten."),
    dict(t="AMZN", name="Amazon", bucket="Konsum zyklisch", kind="Aktie", signal="kaufen",
         inputgeber="2030-Depot 7 %, Status AUFBAUEN: 'außergewöhnlich gut aufgestellt'. Kappen die Hyperscaler ihre KI-Investitionen, sollten ihre eigenen Aktien steigen."),
    dict(t="ASML", name="ASML Holding", bucket="Halbleiter", kind="Aktie", signal="kaufen",
         inputgeber="2030-Depot 3 %, Status AUFBAUEN: erholt sich nach dem Abverkauf; Pick-and-Shovel unabhängig davon, welcher Chiphersteller gewinnt."),
    dict(t="RKLB", name="Rocket Lab", bucket="Raumfahrt", kind="Aktie", signal="pruefen",
         inputgeber="2030: 'interessantester Neueinstiegskandidat' nach dem brutalen Abverkauf – Inputgeber schreibt Puts (Strike 66, effektiv ~60), um die Aktie eingebucht zu bekommen. Es kann weiter nach unten gehen."),
    dict(t="RGLD", name="Royal Gold", bucket="Gold & Edelmetalle", kind="Aktie", signal="pruefen",
         inputgeber="2030: mögliche Neuaufnahme – lief an einem schwachen Tag deutlich im Plus."),
    dict(t="CRDO", name="Credo Technology", bucket="Halbleiter", kind="Aktie", signal="kaufen",
         inputgeber="Alpha 4 % (+28 %), Status EINSTEIGEN – stärkster Wert im Depot; zusätzlich Neuaufnahme-Kandidat im 2030-Depot."),
    # --- Beta-Depot
    dict(t="MKL", name="Markel Group", bucket="Finanzen & Zahlungsverkehr", kind="Aktie", signal="kaufen",
         inputgeber="Beta-Depot 14 %, Status EINSTEIGEN: an den roten Tagen der Woche im Plus – 'bei Markel würde er einsteigen'."),
    dict(t="BRK-B", name="Berkshire Hathaway B", bucket="Finanzen & Zahlungsverkehr", kind="Aktie", signal="warten",
         inputgeber="Beta-Depot 18 %, Status EINSTEIGEN – nach dem starken Anstieg würde Inputgeber für einen Einstieg aber den nächsten Rücksetzer abwarten."),
    dict(t="RSP", name="Invesco S&P 500 Equal Weight ETF", bucket="Breiter Markt (gleichgewichtet)", kind="ETF", signal="warten",
         inputgeber="Beta 8 %, Status LAUFEN LASSEN: gut gelaufen, Chance-Risiko schlechter – nächsten Rücksetzer abwarten. UCITS: SP2Q (IE00BNGJJT35)."),
    dict(t="NOBL", name="ProShares S&P 500 Dividend Aristocrats", bucket="Dividenden-Qualität", kind="ETF", signal="warten",
         inputgeber="Beta 5 %, Status LAUFEN LASSEN: antizyklischer Kauf aufgegangen – nächsten Rücksetzer abwarten. UCITS-Näherung: SPYD (IE00B6YX5D40)."),
    dict(t="TLT", name="iShares 20+ Year Treasury Bond ETF", bucket="Anleihen", kind="ETF", signal="kaufen",
         inputgeber="Beta 6 %, Status EINSTEIGEN: Fluchthafen der Woche; Euro-Liquidität soll schrittweise in TLT/TIP fließen. Zinsgipfel laut Inputgeber gesehen. UCITS: DTLA (IE00BFM6TC58)."),
    dict(t="GLD", name="SPDR Gold Shares", bucket="Gold physisch", kind="ETF", signal="warten",
         inputgeber="Beta 14 %, auf Zielallokation; wegen hoher Gebühren will Inputgeber in ein günstigeres Produkt tauschen. UCITS: EWG2 / Xetra-Gold."),
    dict(t="IBIT", name="iShares Bitcoin Trust", bucket="Krypto", kind="ETF", signal="warten",
         inputgeber="Beta 10 %, auf Zielallokation – nicht mehr aggressiv nachkaufen, Einsteiger nur in Tranchen. Struktur beendet unter 75.000 USD. UCITS-ETP: IB1T."),
    # --- Alpha-Depot und Watchlists
    dict(t="XPEV", name="XPeng", bucket="China & Schwellenländer", kind="Aktie", signal="kaufen",
         inputgeber="Alpha 4 % (−17 %), Status EINSTEIGEN: China hielt im Abverkauf – Inputgeber hält XPeng 'für Einsteiger ausdrücklich für kaufbar'."),
    dict(t="KEYS", name="Keysight Technologies", bucket="Messtechnik & Photonics", kind="Aktie", signal="pruefen",
         inputgeber="Alpha 5 % (−10 %): reiner Chart-Trade – wird der Ausbruch negiert, geht Inputgeber raus."),
    dict(t="BE", name="Bloom Energy", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="pruefen",
         inputgeber="Alpha 6 % (+8 %), Status EINSTEIGEN: Strom- und Netzanschlüsse als möglicher nächster KI-Engpass; Ausstieg bei nachhaltigem Bruch der 200-Tage-Linie."),
    dict(t="GDX", name="VanEck Gold Miners ETF", bucket="Gold & Edelmetalle", kind="ETF", signal="pruefen",
         inputgeber="Alpha-Watchlist KW42: neben GDXJ jetzt auch der großkapitalisierte GDX – Minen verdienen beim aktuellen Goldpreis 'einen Haufen Geld'."),
    dict(t="DHI", name="D.R. Horton", bucket="Immobilien & Hausbau", kind="Aktie", signal="pruefen",
         inputgeber="Alpha-Watchlist KW42: steht mit Lennar 'ganz oben' bei den Profiteuren fallender Zinsen – Absicht, kein Kauf."),
    dict(t="LEN", name="Lennar", bucket="Immobilien & Hausbau", kind="Aktie", signal="pruefen",
         inputgeber="Alpha-Watchlist KW42: wie D.R. Horton – Rotation in alles, was von fallenden Zinsen profitiert."),
    dict(t="GEV", name="GE Vernova", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="pruefen",
         inputgeber="Alpha-Watchlist Versorger & Netze: Strom- und Netzanschlüsse könnten der nächste Engpass im KI-Thema werden."),
    dict(t="ETN", name="Eaton", bucket="Strom & Netzinfrastruktur", kind="Aktie", signal="pruefen",
         inputgeber="Alpha-Watchlist Versorger & Netze: Elektrifizierung und Rechenzentrums-Stromversorgung."),
    dict(t="NVO", name="Novo Nordisk", bucket="Gesundheit / Biotech", kind="Aktie", signal="pruefen",
         inputgeber="Healthcare: deutliche Zuflüsse – Inputgeber prüft, ob er den Sektor über einen Healthcare- oder Biotech-ETF spielt (Einzelwerte-Watchlist KW41: NVO, VRTX)."),
    dict(t="TER", name="Teradyne", bucket="Robotik & Automatisierung", kind="Aktie", signal="warten",
         inputgeber="Alpha (KW41): geplante dritte Robotics-Position – Inputgeber wartet auf einen günstigeren Einstieg. Robotics will er in die Schwäche hinein ausbauen."),
    dict(t="V", name="Visa", bucket="Finanzen & Zahlungsverkehr", kind="Aktie", signal="pruefen",
         inputgeber="2030-Watchlist (KW41, antizyklisch beobachtet) – Käufe erst nach dem McDonald's-Abbau."),
    dict(t="PLTR", name="Palantir", bucket="Software & Cybersecurity", kind="Aktie", signal="pruefen",
         inputgeber="KW41: 'eine der führenden Aktien des Marktes' (Leading Stock) – auf der Watchlist, nicht gekauft."),
    dict(t="MU", name="Micron Technology", bucket="Halbleiter", kind="Aktie", signal="nein",
         inputgeber="Alpha: am 13.10. über die Stop-Marke verkauft (zuvor 17 %, größte Position) – Thema Speicher fällt weg."),
    dict(t="LITE", name="Lumentum", bucket="Halbleiter", kind="Aktie", signal="nein",
         inputgeber="Alpha: am 14.10. verkauft, acht Tage nach dem Kauf – Ausbruch auf neue Hochs negiert."),
    dict(t="XOM", name="Exxon Mobil", bucket="Energie & Öl", kind="Aktie", signal="nein",
         inputgeber="Ölaktien meidet Inputgeber bewusst – der Ölpreis ist ihm 'deutlich zu hoch' und hängt an einem möglichen Ukraine-Deal."),
]

# Kurzfassung der Inputgeber-Reports für die datierte Kaufempfehlung (Paraphrase, Inputgebers Meinung)
INPUTGEBER_SUMMARY = [
    "Rotation aus KI in defensive Werte: Gleichgewichteter S&P, Dividenden-ETF, lange Anleihen und McDonald's steigen, gehypte KI-Aktien werden abgestraft.",
    "Alpha-Depot: Micron und Corning (13.10.) sowie Lumentum (14.10.) über Stop-Marken verkauft – Cash springt von 11 auf 38 %. Keine Neukäufe, bis sich eine Gelegenheit konkretisiert.",
    "Beta- und 2030-Depot ohne Transaktion: Beta im Plus (Berkshire, Markel, NOBL, RSP, TLT), 2030 stabil über McDonald's (32 %), das jetzt in die Stärke hinein abgebaut wird.",
    "Zinsen: Höhepunkt laut Inputgeber gesehen, Dollar schwächer. Liquidität erstmals leicht gefallen, aber noch ausreichend. Viel Angst (Fear & Greed 25) stützt die Jahresendrallye.",
    "Nächste Richtungen: Halbleiter-Gegenbewegung und Zinssenkungs-Profiteure (Lennar, D.R. Horton, Versorger, Healthcare); im 2030-Depot Rocket Lab, Royal Gold, Credo.",
    "Wichtigster Termin: Capex-Aussagen der Hyperscaler in der Berichtssaison. Dazu Bitcoin-Zone 80.000 USD, Stichwahl Brasilien 25.10., US-Midterms 03.11.",
]

# --------------------------------------------------------------------------- Zweitmeinung aus dem Web (datiert)
GLOBE19 = ("The Globe and Mail – US Analyst Updates 19.10.", "https://www.theglobeandmail.com/investing/markets/stocks/FCX/pressreleases/8206287/us-analyst-updates-october-19th-2026/")
GLOBE20 = ("The Globe and Mail – US Analyst Updates 20.10.", "https://www.theglobeandmail.com/investing/markets/stocks/MSFT/pressreleases/8245510/us-analyst-updates-october-20th-2026/")
INVESTRADE = ("Investrade – Market Review 20.10.2026", "https://investrade.com/market-review-october-20-2026/")
AOL = ("AOL – Chips Bounced, Builders Sank", "https://www.aol.com/articles/chips-bounced-builders-sank-crude-135400000.html")
MARKETBEAT = ("MarketBeat – Rocket Lab nach Analysten-Abstufung", "https://www.marketbeat.com/instant-alerts/price-rocket-lab-nasdaq-rklb-stock-price-down-8-after-analyst-downgrade-2026-10-16/")
CHIPS = ("2026-10-20", "Halbleiter beenden eine 9-tägige Verlustserie – Speicher- und KI-Infrastrukturwerte erholen sich.", "+", AOL)
BUILDERS = ("2026-10-20", "Hausbauer fallen, nachdem die Bauherren-Stimmung auf ein 14-Jahres-Tief gesunken ist.", "−", AOL)
WEB = {
    "GOOGL": [("2026-10-19", "KeyCorp: Overweight bestätigt, Kursziel auf 410 USD gesenkt.", "0", GLOBE19)],
    "ASML": [CHIPS],
    "CRDO": [CHIPS],
    "KEYS": [CHIPS],
    "DHI": [BUILDERS],
    "LEN": [BUILDERS],
    "NVO": [("2026-10-20", "Gesundheit (XLV) auf Allzeithoch – defensive Rotation hält an.", "+", INVESTRADE)],
    "GEV": [("2026-10-20", "BTIG stuft den Versorger American Electric Power auf Buy hoch (Ziel 147 USD) – Versorger gefragt.", "+", GLOBE20)],
    "ETN": [("2026-10-20", "BTIG stuft den Versorger American Electric Power auf Buy hoch (Ziel 147 USD) – Versorger gefragt.", "+", GLOBE20)],
    "RKLB": [("2026-10-16", "Kursziel-Senkungen nach Neutron-Verzögerung (Citizens JMP 130 → 90, KeyBanc 135 → 100 USD).", "−", MARKETBEAT)],
    "*":    [("2026-10-20", "107 Kursziel-Senkungen gegenüber 51 Anhebungen – Analysten werden vorsichtiger.", "−", GLOBE20),
             ("2026-10-20", "Defensive Rotation: Gesundheit auf Allzeithoch, Versorger, Basiskonsum und REITs stark; Halbleiter erholen sich nur leicht.", "0", INVESTRADE),
             ("2026-10-20", "Chips erholen sich, Hausbauer fallen nach Bauherren-Stimmung auf 14-Jahres-Tief, Ölpreis uneinheitlich.", "0", AOL),
             ("2026-10-16", "Rocket Lab: Kursziel-Senkungen nach Neutron-Verzögerung.", "−", MARKETBEAT)],
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
    inputgeber_age = age(INPUTGEBER_DATE, today)
    f_inputgeber = 1.0 if inputgeber_age <= MAX_AGE else 0.5
    sb = SIGNAL_SCORE[c["signal"]] * f_inputgeber
    sa, alabel = analyst_view(c, q, h)
    sw = sum({"+": 0.4, "−": -0.4, "0": 0}[w["tone"]] for w in web)
    v = h.get("vsMa200")
    # Inputgebers Trendfilter: Kauf nahe/über der 200T-Linie, keine überdehnten Werte jagen
    st = 0 if v is None else 0.8 if -8 <= v <= 20 else -1.0 if v > 40 else -0.6 if v < -20 else 0.2
    return {"total": round(sb + sa + sw + st, 2), "inputgeber": round(sb, 2), "analyst": round(sa, 2),
            "web": round(sw, 2), "trend": st, "analystLabel": alabel, "inputgeberAge": inputgeber_age,
            "inputgeberFresh": inputgeber_age <= MAX_AGE}


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
    """+1/0/-1 je Meinung: Inputgeber, Analysten, Fundamental, Momentum."""
    b = {"kaufen": 1, "pruefen": 1, "halten": 0, "warten": 0, "nein": -1}[c["signal"]]
    if q and q.get("mean"):
        a = 1 if q["mean"] <= 2.2 else -1 if q["mean"] >= 3 else 0
    else:
        a = 1 if sc["analyst"] >= 1 else 0
    return {"inputgeber": b, "analysten": a, "fundamental": fs, "momentum": ms}
