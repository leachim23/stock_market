# -*- coding: utf-8 -*-
"""Kaufempfehlung: Becker-Signale vs. Zweitmeinung (Yahoo-Analystenkonsens + datierte Webquellen),
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
import my_portfolio  # noqa: E402

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
    dict(t="GLD", name="SPDR Gold Shares", bucket="Gold & Edelmetalle", kind="ETF", signal="warten",
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


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    today = date.today()
    holdings = [r["ticker"] for r in my_portfolio.parse()]
    held_buckets = {HOLD_BUCKET.get(t, t) for t in holdings}

    def load(c):
        h = yahoo.fetch_history(c["t"])
        try:
            q = yahoo.fetch_consensus(c["t"])
        except Exception:  # noqa: BLE001
            q = None
        return c, h, q

    with ThreadPoolExecutor(8) as ex:
        loaded = list(ex.map(load, [c for c in CANDIDATES if c["t"] not in holdings]))

    rows = []
    for c, h, q in loaded:
        web = fresh_web(c["t"], today)
        sc = score(c, q, h, web, today)
        rows.append({**c, "price": h["price"], "currency": h["currency"], "vsMa200": h["vsMa200"], "chg1y": h["chg1y"],
                     "ma200": h["ma200"], "spark": h["close"][-252::3], "consensus": q, "web": web, "score": sc,
                     "agree": agreement(c, sc, q), "signalLabel": SIGNAL_LABEL[c["signal"]]})
    rows.sort(key=lambda r: -r["score"]["total"])

    # Diversifikation: max. 1 Titel je Bucket und je Familie, keine Buckets, die das Depot schon abdeckt,
    # keine 'nein'-Signale, kein Widerspruch zwischen Becker und Zweitmeinung, feste Plätze je Klasse.
    held_fam = {family(b) for b in held_buckets}
    picks, used, used_fam, filled = [], set(), set(), {k: 0 for k in SLOTS}
    for r in rows:
        r["slot"], r["family"] = slot(r), family(r["bucket"])
        why = None
        if r["signal"] == "nein":
            why = "Becker: nicht einsteigen"
        elif r["bucket"] in held_buckets:
            why = f"Sektor bereits im Depot ({r['bucket']})"
        elif r["bucket"] in used:
            why = f"Sektor schon belegt ({r['bucket']})"
        elif r["family"] in used_fam:
            why = f"Familie '{r['family']}' schon belegt – Klumpenrisiko vermeiden"
        elif r["agree"] == "Divergenz" and r["signal"] != "kaufen":
            why = "Becker und Zweitmeinung uneinig"
        elif r["score"]["total"] < 2:
            why = "Gesamtwertung zu niedrig"
        elif filled[r["slot"]] >= SLOTS[r["slot"]]:
            why = f"Plätze für {r['slot']} belegt (besser bewertete Alternativen)"
        r["excluded"] = why
        if not why:
            picks.append(r)
            used.add(r["bucket"])
            used_fam.add(r["family"])
            filled[r["slot"]] += 1
    r_tech_note = "Technologie" in held_fam
    for r in picks:
        r["techNote"] = r_tech_note and r["family"] == "Technologie"

    # Vorgeschlagene Aufteilung neuen Kapitals: ETFs/Kern doppelt gewichtet (Becker-Barbell)
    w = {r["t"]: (2 if r["slot"] == "Kern-Baustein" else 1) for r in picks}
    tw = sum(w.values()) or 1
    for r in picks:
        r["alloc"] = round(w[r["t"]] / tw * 100)

    payload = {
        "generated": today.isoformat(), "validUntil": (today + timedelta(days=MAX_AGE)).isoformat(), "maxAge": MAX_AGE,
        "beckerDate": BECKER_DATE, "beckerAge": age(BECKER_DATE, today),
        "holdings": [{"t": t, "bucket": HOLD_BUCKET.get(t, t)} for t in holdings],
        "picks": [r["t"] for r in picks], "rows": rows,
        "market": fresh_web("*", today),
        "staleWeb": [dict(date=d, text=x, source=s[0]) for d, x, _, s in WEB.get("*", []) if age(d, today) > MAX_AGE],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_md(payload)
    print(f"Kaufempfehlung {today}: {', '.join(f'{r['t']} ({r['alloc']} %)' for r in picks)}")
    return payload


def de(d):
    return f"{d[8:]}.{d[5:7]}.{d[:4]}"


def pct(v):
    return "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")


def write_md(p):
    rows = {r["t"]: r for r in p["rows"]}
    L = [
        "# 🛒 Kaufempfehlung – Becker vs. Zweitmeinung",
        "",
        f"**Erstellt:** {de(p['generated'])} · **Gültig bis:** {de(p['validUntil'])} (max. {p['maxAge']} Tage)",
        "",
    ]
    if p["beckerAge"] > p["maxAge"]:
        L += [f"> ⚠️ **Becker-Signale veraltet:** Der letzte Report ist vom {de(p['beckerDate'])} ({p['beckerAge']} Tage). "
              "Sie fließen nur halb gewichtet ein. Neue PDFs in `PDF_input/` legen und neu generieren.", ""]
    L += [
        "> Keine Anlageberatung. Ziel: Diversifikation zum bestehenden Depot ("
        + ", ".join(f"{h['t']} = {h['bucket']}" for h in p["holdings"]) + "). Regeln: max. ein Titel je Sektor und je Familie (z. B. nur ein Technologie-/Halbleiterwert), "
        "keine bereits abgedeckten Sektoren, 3 Einzelaktien + 2 Kern-Bausteine (ETFs/Anleihen) nach Beckers Barbell-Prinzip.",
        "",
        "## ✅ Empfehlungen",
        "",
        "| # | Titel | Sektor / Rolle | Anteil neues Kapital | Becker (Stand " + de(p["beckerDate"]) + ") | Zweitmeinung (" + de(p["generated"]) + ") | Bild |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, t in enumerate(p["picks"], 1):
        r = rows[t]
        q = r["consensus"] or {}
        sec = (f"{r['score']['analystLabel']} · {q.get('analysts')} Analysten · Ziel {pct(q.get('upside'))}"
               if q.get("mean") else r["score"]["analystLabel"])
        L.append(f"| {i} | **{r['name']} ({t})** | {r['bucket']} · {r['slot']} | {r['alloc']} % | {r['signalLabel']} | {sec} | {r['agree']} |")
    L.append("")
    for t in p["picks"]:
        r = rows[t]
        q = r["consensus"] or {}
        L += [f"### {r['name']} ({t})", "",
              f"- **Becker ({de(p['beckerDate'])}, {p['beckerAge']} Tage alt):** {r['becker']}"]
        if q.get("mean"):
            d = q["dist"]
            L.append(f"- **Analystenkonsens Yahoo Finance ({de(q['date'])}):** {r['score']['analystLabel']} (Note {q['mean']:.2f} von 1–5), "
                     f"{q['analysts']} Analysten – {d['strongBuy']}× Strong Buy, {d['buy']}× Buy, {d['hold']}× Hold, {d['sell'] + d['strongSell']}× Sell. "
                     f"Mittleres Kursziel {q['target']:.2f} {r['currency']} ({pct(q['upside'])}).")
        else:
            L.append("- **Analystenkonsens:** keiner (ETF) – Zweitmeinung aus Trend und Webquellen.")
        for w in r["web"]:
            L.append(f"- **Web ({de(w['date'])}, [{w['source']}]({w['url']})):** {w['text']}")
        if r.get("techNote"):
            L.append("- **Hinweis Diversifikation:** Mit CRWD hält das Depot bereits einen Technologiewert – dieser Titel ist der einzige zusätzliche Tech-/Halbleiterwert.")
        L.append(f"- **Trend:** Kurs {r['price']:.2f} {r['currency']}, {pct(r['vsMa200'])} zur 200-Tage-Linie, 1 Jahr {pct(r['chg1y'])}.")
        L.append("")
    L += ["## ❌ Nicht empfohlen (mit Grund)", "", "| Titel | Sektor | Becker | Zweitmeinung | Grund |", "|---|---|---|---|---|"]
    for r in p["rows"]:
        if r["excluded"]:
            L.append(f"| {r['name']} ({r['t']}) | {r['bucket']} | {r['signalLabel']} | {r['score']['analystLabel']} | {r['excluded']} |")
    L += ["", "## 🌐 Marktstimmung aus dem Web (≤ 4 Tage)", ""]
    L += [f"- **{de(w['date'])}** · [{w['source']}]({w['url']}): {w['text']}" for w in p["market"]]
    if p["staleWeb"]:
        L += ["", "*Wegen Alter ignoriert:* " + "; ".join(f"{w['source']} ({de(w['date'])})" for w in p["staleWeb"])]
    L += ["", "---", "[⬅️ Dashboard](index.md) | [👤 Mein Depot](mein_depot.md) | *Keine Anlageberatung.*", ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    run()
