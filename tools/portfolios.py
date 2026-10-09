# -*- coding: utf-8 -*-
"""Mehrere eigene Depots: input/<name>/*.md einlesen, bewerten und je Depot eine Kaufempfehlung erzeugen.

    python tools/portfolios.py

Ausgaben je Depot <id>:
    portfolio/depots/<id>.md               Bewertung der Positionen
    portfolio/depots/<id>_kaufempfehlung.md
    website/data/depots/<id>.json          Daten für die Webseite

Zeilenformate in der Depot-Datei (alles optional außer dem Namen):
    • ALPHABET INC.CL.A DL-,001            (Name aus dem Depotauszug)
    BMW kauf 100,16                        (Name + Kaufkurs in EUR)
    LULU gekauft am 01.09.2026             (Ticker + Kaufdatum)
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "website"))
sys.path.insert(0, str(ROOT / "tools"))
import yahoo  # noqa: E402
import buy_reco as br  # noqa: E402
import decision  # noqa: E402
from assets_data import ASSETS, SOLD, STAND  # noqa: E402

INPUT = ROOT / "input"
OUT_MD = ROOT / "portfolio" / "depots"
OUT_JSON = ROOT / "website" / "data" / "depots"

BUCKET_MAX = 10.0   # % – ab hier gilt ein Sektor im Depot als ausreichend besetzt
FAMILY_MAX = 25.0   # % – ab hier keine weiteren Titel derselben Familie

# --------------------------------------------------------------------------- Auflösung Name → Wertpapier
# (Regex auf den Großbuchstaben-Namen, Ticker, Yahoo-Symbol, Anzeigename, Sektor, Art)
RESOLVE = [
    (r"XETRA.?GOLD|^4GLD\b|DE000A0S9GB0", "4GLD", "4GLD.DE", "Xetra-Gold", "Gold physisch", "ETF"),
    (r"EUWAX GOLD|^EWG2\b|DE000EWG2LD7", "EWG2", "EWG2.SG", "EUWAX Gold II", "Gold physisch", "ETF"),
    (r"OVERNIGHT|^XEON\b|LU0290358497", "XEON", "XEON.DE", "Xtrackers EUR Overnight Rate Swap", "Geldmarkt", "ETF"),
    (r"EB\.?REXX.*0-1|^EXVM\b|DE000A0Q4RZ9", "EXVM", "EXVM.DE", "iShares eb.rexx Government Germany 0-1yr", "Kurzlaufende Staatsanleihen (AAA)", "ETF"),
    (r"IE00BL25JP72", "XDEM", "XDEM.DE", "Xtrackers MSCI World Momentum", "Breiter Markt (Welt)", "ETF"),
    (r"IE00B3WJKG14", "QDVE", "QDVE.DE", "iShares S&P 500 Information Technology Sector", "Tech-ETF", "ETF"),
    (r"IE00B1TXK627", "IQQQ", "IQQQ.DE", "iShares Global Water", "Wasser & Infrastruktur", "ETF"),
    (r"LU1900066033", "CHIP", "CHIP.PA", "Amundi MSCI Semiconductors ESG Screened", "Halbleiter", "ETF"),
    (r"LU1834986900", "HLT", "HLT.PA", "Amundi STOXX Europe 600 Healthcare", "Gesundheit / Biotech", "ETF"),
    (r"LU0533033667", "LYPG", "LYPG.DE", "Amundi MSCI World Information Technology", "Tech-ETF", "ETF"),
    (r"BERKSH", "BRK-B", "BRK-B", "Berkshire Hathaway B", "Finanzen & Zahlungsverkehr", "Aktie"),
    (r"MARKEL", "MKL", "MKL", "Markel Group", "Finanzen & Zahlungsverkehr", "Aktie"),
    (r"A\.G\.HLD|ALIBABA", "BABA", "BABA", "Alibaba", "China & Schwellenländer", "Aktie"),
    (r"ALPHABET", "GOOGL", "GOOGL", "Alphabet", "Kommunikation & Internet", "Aktie"),
    (r"AMAZON", "AMZN", "AMZN", "Amazon", "Konsum zyklisch", "Aktie"),
    (r"ASML", "ASML", "ASML", "ASML Holding", "Halbleiter", "Aktie"),
    (r"ATLASSIAN", "TEAM", "TEAM", "Atlassian", "Software & Cybersecurity", "Aktie"),
    (r"LULULEMON|^LULU\b", "LULU", "LULU", "Lululemon Athletica", "Konsum zyklisch", "Aktie"),
    (r"MCDONALD", "MCD", "MCD", "McDonald's", "Konsum zyklisch", "Aktie"),
    (r"META PLATF", "META", "META", "Meta Platforms", "Kommunikation & Internet", "Aktie"),
    (r"NIKE", "NKE", "NKE", "Nike", "Konsum zyklisch", "Aktie"),
    (r"ROBINH", "HOOD", "HOOD", "Robinhood", "Finanzen & Zahlungsverkehr", "Aktie"),
    (r"SALESFORCE", "CRM", "CRM", "Salesforce", "Software & Cybersecurity", "Aktie"),
    (r"SOFI", "SOFI", "SOFI", "SoFi Technologies", "Finanzen & Zahlungsverkehr", "Aktie"),
    (r"ALCOA", "AA", "AA", "Alcoa", "Rohstoffe & Metalle", "Aktie"),
    (r"ALMONTY", "ALM", "ALM", "Almonty Industries", "Rohstoffe & Metalle", "Aktie"),
    (r"CELESTICA", "CLS", "CLS", "Celestica", "KI-Hardware & Netzwerk", "Aktie"),
    (r"CIPHER", "CIFR", "CIFR", "Cipher Digital", "Krypto & Rechenzentren", "Aktie"),
    (r"CIRCLE INT", "CRCL", "CRCL", "Circle Internet Group", "Krypto & Rechenzentren", "Aktie"),
    (r"CORNING", "GLW", "GLW", "Corning", "KI-Hardware & Netzwerk", "Aktie"),
    (r"CREDO", "CRDO", "CRDO", "Credo Technology", "Halbleiter", "Aktie"),
    (r"CRITICAL METALS", "CRML", "CRML", "Critical Metals", "Rohstoffe & Metalle", "Aktie"),
    (r"ENERGY FUELS", "UUUU", "UUUU", "Energy Fuels", "Kernenergie & Uran", "Aktie"),
    (r"FREEPORT", "FCX", "FCX", "Freeport-McMoRan", "Rohstoffe & Metalle", "Aktie"),
    (r"HIMS", "HIMS", "HIMS", "Hims & Hers Health", "Gesundheit / Biotech", "Aktie"),
    (r"IREN", "IREN", "IREN", "IREN", "Krypto & Rechenzentren", "Aktie"),
    (r"MARVELL", "MRVL", "MRVL", "Marvell Technology", "Halbleiter", "Aktie"),
    (r"MICRON", "MU", "MU", "Micron Technology", "Halbleiter", "Aktie"),
    (r"MP MATERIALS", "MP", "MP", "MP Materials", "Rohstoffe & Metalle", "Aktie"),
    (r"NEXTPOWER", "NXT", "NXT", "Nextpower", "Strom & Netzinfrastruktur", "Aktie"),
    (r"OUSTER", "OUST", "OUST", "Ouster", "Robotik & Automatisierung", "Aktie"),
    (r"POET", "POET", "POET", "POET Technologies", "Halbleiter", "Aktie"),
    (r"ROYAL GOLD", "RGLD", "RGLD", "Royal Gold", "Gold & Edelmetalle", "Aktie"),
    (r"SERVICENOW", "NOW", "NOW", "ServiceNow", "Software & Cybersecurity", "Aktie"),
    (r"VISHAY PREC", "VPG", "VPG", "Vishay Precision Group", "Robotik & Automatisierung", "Aktie"),
    (r"XIAOMI", "3CP", "1810.HK", "Xiaomi", "China & Schwellenländer", "Aktie"),
    (r"CROWDSTRIKE|^CRWD\b", "CRWD", "CRWD", "CrowdStrike", "Software & Cybersecurity", "Aktie"),
    (r"^IBB\b", "IBB", "IBB", "iShares Biotechnology ETF", "Gesundheit / Biotech", "ETF"),
    # UCITS-ETFs (Xetra, EUR)
    (r"MSCI W\.VAL", "IS3S", "IS3S.DE", "iShares Edge MSCI World Value Factor", "Breiter Markt (Welt)", "ETF"),
    (r"S\+P500H\.CA|HEALTH CARE", "QDVG", "QDVG.DE", "iShares S&P 500 Health Care Sector", "Gesundheit / Biotech", "ETF"),
    (r"D\.AR\.|DIV.*ARIST", "SPYD", "SPYD.DE", "SPDR S&P US Dividend Aristocrats", "Dividenden-Qualität", "ETF"),
    (r"FTSE A\.W|ALL.WORLD", "VWCE", "VWCE.DE", "Vanguard FTSE All-World", "Breiter Markt (Welt)", "ETF"),
    (r"WO\.IN\.TE|WORLD INFO", "XDWT", "XDWT.DE", "Xtrackers MSCI World Information Technology", "Tech-ETF", "ETF"),
    (r"N\.100|NASDAQ.?100", "XNAS", "XNAS.DE", "Xtrackers Nasdaq 100", "Tech-ETF", "ETF"),
    (r"NASDAQ US BIOTE", "2B70", "2B70.DE", "iShares Nasdaq US Biotechnology", "Gesundheit / Biotech", "ETF"),
    (r"J\. ?GOLD MIN|JUNIOR GOLD", "G2XJ", "G2XJ.DE", "VanEck Junior Gold Miners UCITS", "Gold & Edelmetalle", "ETF"),
    # michi_g
    (r"^BMW\b", "BMW", "BMW.DE", "BMW", "Auto & E-Mobilität", "Aktie"),
    (r"^BYD\b", "BYD", "1211.HK", "BYD", "Auto & E-Mobilität", "Aktie"),
    (r"EINRIDE", "ENRD", "ENRD", "Einride", "Robotik & Automatisierung", "Aktie"),
    (r"INFLEQTION", "INFQ", "INFQ", "Infleqtion", "Quantencomputing", "Aktie"),
    (r"IONQ", "IONQ", "IONQ", "IonQ", "Quantencomputing", "Aktie"),
    (r"TERRESTRIAL|TERRESTIAL", "IMSR", "IMSR", "Terrestrial Energy", "Kernenergie & Uran", "Aktie"),
]
# UCITS-Pendants zu Becker-Positionen (für Becker-Bezug und Doppelungs-Check)
EQUIV = {"2B70": "IBB", "G2XJ": "GDXJ", "SPYD": "NOBL", "IBB": "IBB"}
FAMILY_EXTRA = {"KI-Hardware & Netzwerk": "Technologie", "Quantencomputing": "Technologie", "Tech-ETF": "Technologie", "Halbleiter": "Technologie",
                "Breiter Markt (Welt)": "US-Aktien breit", "Krypto & Rechenzentren": "Krypto"}

WKN = re.compile(r"^[A-Z0-9]{6}$")
NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*$")
DATE = re.compile(r"gekauft\s+am\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.I)
ISIN = re.compile(r"\(?\s*ISIN:?\s*([A-Z]{2}[A-Z0-9]{9}\d)\s*\)?\s*(\d+(?:[.,]\d+)?)?", re.I)


def family(bucket):
    return FAMILY_EXTRA.get(bucket, br.family(bucket))


def parse(path):
    """Liefert Positionen; nicht auflösbare Zeilen werden mit resolved=False zurückgegeben."""
    out = []
    lines = [r.strip().lstrip("•*-– ").strip() for r in path.read_text(encoding="utf-8").splitlines()]
    raws = [r.strip() for r in path.read_text(encoding="utf-8").splitlines()]
    wkn = None
    for i, (raw, line) in enumerate(zip(raws, lines)):
        if not line or line.upper() in ("ETFS", "ETF") or line.lower().startswith(("hier ist", "es soll")):
            continue
        nxt = next((l for l in lines[i + 1:] if l), "")
        if WKN.match(line.upper()) and ISIN.search(nxt):
            wkn = line.upper()          # WKN-Zeile gehört zur folgenden Zeile mit Name + ISIN
            continue
        buy, d = None, None
        m = ISIN.search(line)
        if m:
            if m.group(2):
                buy = float(m.group(2).replace(",", "."))
            line = (line[:m.start()].strip() + " " + m.group(1)).strip()
        m = DATE.search(line)
        if m:
            d = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
            line = line[:m.start()].strip()
        # Kaufkurs nur, wenn das letzte Wort eine reine Zahl ist (nicht Nennwerte wie "DL-,001" oder "EO -,09")
        last = line.split()[-1] if line.split() else ""
        if not d and buy is None and len(line.split()) > 1 and NUM.fullmatch(last):
            buy = float(last.replace(",", "."))
            line = line[: line.rfind(last)].strip()
        line = re.sub(r"\s+kauf$", "", line, flags=re.I).strip()
        up = line.upper()
        hit = next((r for r in RESOLVE if re.search(r[0], up)), None)
        if hit:
            _, t, sym, name, bucket, kind = hit
            out.append(dict(raw=raw.strip(), t=t, symbol=sym, name=name, bucket=bucket, kind=kind, buy=buy, date=d, resolved=True, wkn=wkn))
        else:
            hint = "WKN – bitte Name oder ISIN nachtragen" if WKN.match(up) else "unbekannt – bitte Name oder ISIN nachtragen"
            out.append(dict(raw=raw.strip(), t=up, symbol=None, name=line, bucket="Nicht aufgelöst", kind="?", buy=buy, date=d,
                            resolved=False, hint=hint, wkn=wkn))
        wkn = None
    return out


# --------------------------------------------------------------------------- Becker-Bezug
BECKER = {a["t"]: a for a in ASSETS if a["depot"] != "mein"}
SOLD_MAP = {t: (n, d, w, g) for t, n, d, w, g in SOLD}
SOLD_MAP.update({"ALM": ("Almonty Industries", "Alpha", "KW39", "Momentum fehlte – Kapital ging in Marvell."),
                 "MP": ("MP Materials", "Alpha", "KW39", "lief monatelang seitwärts – Kapital ging in Corning.")})
CAND = {c["t"]: c for c in br.CANDIDATES}
BECKER_DEPOT = {a["t"]: {"beta": "Beta", "2030": "2030", "alpha": "Alpha"}[a["depot"]] for a in ASSETS if a["depot"] != "mein"}


def becker_info(t):
    key = EQUIV.get(t, t)
    if key in SOLD_MAP:
        n, dep, w, g = SOLD_MAP[key]
        return {"kind": "sold", "text": f"Von Becker im {dep}-Depot in {w} verkauft: {g}"}
    if key in BECKER:
        a = BECKER[key]
        dep = {"beta": "Beta", "2030": "2030", "alpha": "Alpha"}[a["depot"]]
        alloc = f"{a['alloc']} %" if a.get("alloc") is not None else "–"
        return {"kind": "held", "status": a.get("status") or "", "depot": dep, "alloc": alloc, "block": a.get("block", ""),
                "text": f"{dep}-Depot {alloc}" + (f", Status {a['status']}" if a.get("status") else "") + f". {a['woche']}"}
    if key in CAND:
        c = CAND[key]
        return {"kind": "watch", "signal": c["signal"], "text": c["becker"]}
    return {"kind": "none", "text": "Kein Bezug in Beckers Reports."}


# --------------------------------------------------------------------------- Bewertung je Position
def pct(v):
    return "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")


def hold_reco(h):
    b, v, perf, q = h["becker"], h.get("vsMa200"), h.get("perf"), h.get("consensus") or {}
    t = h["t"]
    if t == "LULU":
        return ("Stop setzen", "reduzieren", "Deutlich unter der 200-Tage-Linie, kein Becker-Bezug; Beckers Analogie Nike-Calls liegt bei −44 %, Berenberg stuft Nike auf Sell. Nicht verbilligen, Stop knapp unter dem 52-Wochen-Tief.")
    if t == "NKE":
        return ("Stop setzen", "reduzieren", "Becker spielt Nike nur über kleine Calls (−44 %, 'zu früh dran'); Berenberg am 06.10. Abstufung auf Sell (Ziel 27,50 USD). Nicht nachkaufen.")
    if b["kind"] == "sold":
        return ("Verkauf prüfen", "reduzieren", b["text"] + " Wer Beckers Regelwerk folgt, löst die Position ebenfalls auf oder setzt einen engen Stop.")
    if perf is not None and perf > 100:
        return ("Teilgewinn sichern", "reduzieren", f"{pct(perf)} seit Kauf – Beckers Regel: Gewinne aus spekulativen Positionen regelmäßig in den stabilen Teil umschichten. Etwa ein Drittel verkaufen, Rest mit Stop an der 200-Tage-Linie.")
    st = b.get("status", "")
    if b["kind"] == "held" and st == "REDUZIEREN":
        return ("Reduzieren (in Erholung)", "reduzieren", f"Becker: Status REDUZIEREN – in die Erholung hinein abbauen, nicht in die Schwäche. {pct(v)} zur 200-Tage-Linie.")
    if b["kind"] == "held" and st == "AUFBAUEN":
        return ("Halten / Aufbauen", "kaufen", f"Becker: Status AUFBAUEN. {pct(v)} zur 200-Tage-Linie.")
    if b["kind"] == "held" and b["depot"] == "Alpha":
        if v is not None and v < 0:
            return ("Stop prüfen", "reduzieren", f"Becker hält die Position im Alpha-Depot mit engen Stopps; aktuell {pct(v)} unter der 200-Tage-Linie – Ausstieg definieren.")
        return ("Halten mit Stop", "halten", f"Becker-Alpha-Position, Stop an der 200-Tage-Linie ({pct(v)} Abstand).")
    if b["kind"] == "held":
        return ("Halten", "halten", f"Becker: {b['depot']}-Depot, {('Status ' + st) if st else 'unverändert'}. {pct(v)} zur 200-Tage-Linie.")
    if h["kind"] == "ETF":
        if v is not None and v < -10:
            return ("Halten, beobachten", "halten", f"Basisbaustein, aber {pct(v)} unter der 200-Tage-Linie.")
        return ("Halten", "halten", f"Basisbaustein, Trend intakt ({pct(v)} zur 200-Tage-Linie).")
    if v is not None and v > 60:
        return ("Teilgewinn sichern", "reduzieren", f"{pct(v)} über der 200-Tage-Linie – starke Übertreibung; Gewinne teilweise sichern.")
    if v is None:
        return ("Halten mit Stop", "halten", "Junge Aktie ohne 200-Tage-Linie (zu kurze Kurshistorie) – Stop unter dem bisherigen Tief setzen.")
    if v < -25:
        return ("Stop setzen", "reduzieren", f"{pct(v)} unter der 200-Tage-Linie ohne Becker-Unterstützung – Ausstieg definieren. (Becker: 'Ob du im Plus oder Minus bist, ist keine Information' – entscheidend ist der Trend.)")
    if v < -15:
        return ("Stop prüfen", "reduzieren", f"{pct(v)} unter der 200-Tage-Linie – Trend negativ, Ausstiegsmarke festlegen.")
    if q.get("mean") and q["mean"] >= 3:
        return ("Reduzieren prüfen", "reduzieren", f"Analysten zurückhaltend (Note {q['mean']:.1f}).")
    return ("Halten", "halten", f"Kein Becker-Bezug; Trend {pct(v)} zur 200-Tage-Linie" + (f", Analysten: {br.analyst_view({}, q, {})[1]}" if q.get("mean") else "") + ".")


def fx_rates():
    rates = {"EUR": 1.0}
    for c in ("USD", "HKD", "JPY", "GBP", "CAD"):
        try:
            h = yahoo._get(f"https://query1.finance.yahoo.com/v8/finance/chart/EUR{c}=X?range=5d&interval=1d")
            rates[c] = h["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except Exception:  # noqa: BLE001
            pass
    return rates


def analyse(holdings, fx, spy):
    def one(h):
        if not h["resolved"]:
            return h
        yahoo.YAHOO.setdefault(h["t"], h["symbol"])
        try:
            p = yahoo.fetch_history(h["t"])
        except Exception as e:  # noqa: BLE001
            h["error"] = str(e)
            return h
        q = None
        if h["kind"] == "Aktie":
            try:
                q = yahoo.fetch_consensus(h["t"])
            except Exception:  # noqa: BLE001
                q = None
        fund = None
        try:
            fund = yahoo.fetch_fundamentals(h["t"])
        except Exception:  # noqa: BLE001
            pass
        c = {"bucket": h["bucket"], "kind": h["kind"]}
        fs, flabel, fdet = br.fundamental_view(c, fund)
        ms, mlabel, mdet, _ = br.momentum_view(p, spy)
        h["fund"] = {"score": fs, "label": flabel, "details": fdet}
        h["fundRaw"] = {k: (fund or {}).get(k) for k in ("mcap", "beta")}
        h["mom"] = {"score": ms, "label": mlabel, "details": mdet}
        rate = fx.get(p["currency"]) or None
        h.update(price=p["price"], currency=p["currency"], vsMa200=p["vsMa200"], chg1y=p["chg1y"], chg1d=p["chg1d"],
                 priceEUR=round(p["price"] / rate, 2) if rate else None, spark=p["close"][-252::3], consensus=q,
                 dates=p["dates"][-252:], close=p["close"][-252:])
        if h.get("buy") and h.get("priceEUR"):
            ratio = h["priceEUR"] / h["buy"]
            if ratio > 8 or ratio < 0.1:   # >8x Gewinn oder >90 % Verlust: eher Eingabefehler als Kursbewegung
                # z. B. vertauschte Zeilen in der Depot-Datei – nicht in die Performance rechnen
                h["buyWarn"] = (f"Kaufkurs {h['buy']:.2f} € weicht stark vom aktuellen Kurs {h['priceEUR']:.2f} € ab "
                                f"(Faktor {ratio:.2f}) – bitte in input/ prüfen").replace(".", ",")
            else:
                h["perf"] = round((ratio - 1) * 100, 1)
        elif h.get("date"):
            i = next((k for k, d in enumerate(p["dates"]) if d >= h["date"]), None)
            if i is not None:
                h["buy"] = round(p["close"][i] / rate, 2) if rate else p["close"][i]
                h["perf"] = round((p["price"] / p["close"][i] - 1) * 100, 1)
        return h

    with ThreadPoolExecutor(8) as ex:
        holdings = list(ex.map(one, holdings))
    for h in holdings:
        h["becker"] = becker_info(h["t"]) if h["resolved"] else {"kind": "none", "text": "–"}
        if h["resolved"] and "price" in h:
            h["aktion"], h["cls"], h["warum"] = hold_reco(h)
        else:
            h["aktion"], h["cls"], h["warum"] = ("Daten nachtragen", "halten", h.get("hint") or h.get("error", ""))
    return holdings


def weights(holdings):
    """Gleichgewichtung (keine Stückzahlen bekannt) – Anteil je Sektor und je Familie in %, nur aufgelöste Positionen."""
    res = [h for h in holdings if h["resolved"]]
    n = len(res) or 1
    bw, fw = {}, {}
    for h in res:
        bw[h["bucket"]] = bw.get(h["bucket"], 0) + 100 / n
        f = family(h["bucket"])
        fw[f] = fw.get(f, 0) + 100 / n
    return {k: round(v, 1) for k, v in bw.items()}, {k: round(v, 1) for k, v in fw.items()}


# --------------------------------------------------------------------------- Kaufempfehlung je Depot
def buy_for(holdings, bw, fw, today, loaded, spy, bb):
    held = {h["t"] for h in holdings} | {EQUIV.get(h["t"], h["t"]) for h in holdings}
    rows = []
    for c, hist, q, fund in loaded:
        if c["t"] in held:
            continue
        web = br.fresh_web(c["t"], today)
        sc = br.score(c, q, hist, web, today)
        wt = bw.get(c["bucket"], 0.0)
        sc["depot"] = round(-wt / 5, 2)          # leichte Abwertung je nach vorhandenem Sektorgewicht
        fs, flabel, fdet = br.fundamental_view(c, fund)
        ms, mlabel, mdet, mrows = br.momentum_view(hist, spy)
        sc["fundamental"], sc["momentum"] = 0.8 * fs, 0.8 * ms
        sc["total"] = round(sc["total"] + sc["depot"] + sc["fundamental"] + sc["momentum"], 2)
        votes = br.opinion_votes(c, q, sc, fs, ms)
        rows.append({**c, "price": hist["price"], "currency": hist["currency"], "vsMa200": hist["vsMa200"], "chg1y": hist["chg1y"],
                     "ma200": hist["ma200"], "spark": hist["close"][-252::3], "consensus": q, "web": web, "score": sc,
                     "agree": br.agreement(c, sc, q), "signalLabel": br.SIGNAL_LABEL[c["signal"]],
                     "slot": br.slot(c), "family": family(c["bucket"]), "bucketWeight": wt, "familyWeight": fw.get(family(c["bucket"]), 0.0),
                     "fund": {"score": fs, "label": flabel, "details": fdet, "date": (fund or {}).get("date", today.isoformat())},
                     "mom": {"score": ms, "label": mlabel, "details": mdet, "date": hist["dates"][-1] if hist.get("dates") else today.isoformat()},
                     "votes": votes, "votesPos": sum(v > 0 for v in votes.values()), "votesNeg": sum(v < 0 for v in votes.values()),
                     "role": decision.role_of(c["t"], c["kind"], c["bucket"], BECKER_DEPOT.get(c["t"]), fund)})
    rows.sort(key=lambda r: -r["score"]["total"])
    # ---- Barbell-Auswahl (SKILL.md Abschnitt 0)
    # 1. Anker: je fehlendem Baustein der bestbewertete Kandidat
    # 2. Satellit: nur wenn der Satellit unter 15 % liegt, max. 2 Titel mit den bisherigen Diversifikationsregeln
    # 3. Mitte: ausgeschlossen
    anchor_parts = ["Geldmarkt", "Kurzlaufende Staatsanleihen (AAA)", "Gold physisch", "Breiter Markt (Welt)"]
    held_parts = {h["bucket"] for h in holdings if h.get("role") == "Anker"}
    sat_ist = bb["ist"]["Satellit"]
    sat_open = sat_ist < decision.TARGET["Satellit"]
    picks, used, used_fam, n_sat = [], set(), set(), 0
    for r in rows:
        why = None
        if r["role"] == "Mitte":
            why = "Barbell: ignorierte Mitte – weder Anker noch Satellit"
        elif r["role"] == "Anker":
            part = r["bucket"]
            if part in held_parts:
                why = f"Anker-Baustein „{part}“ ist im Depot schon vorhanden"
            elif part in used:
                why = f"Anker-Baustein „{part}“ schon mit einem besser bewerteten Titel belegt"
        else:  # Satellit
            if r["signal"] == "nein":
                why = "Becker: nicht einsteigen"
            elif not sat_open:
                why = f"Satellit im Depot schon {sat_ist:.0f} % (Ziel 15 %) – neues Kapital nur in den Anker"
            elif r["bucketWeight"] >= BUCKET_MAX:
                why = f"Sektor im Depot schon {pct(r['bucketWeight']).lstrip('+')} ({r['bucket']})"
            elif r["familyWeight"] >= FAMILY_MAX:
                why = f"Familie '{r['family']}' im Depot schon {pct(r['familyWeight']).lstrip('+')} – Klumpenrisiko"
            elif r["bucket"] in used or r["family"] in used_fam:
                why = "Sektor/Familie in der Empfehlung schon belegt"
            elif r["agree"] == "Divergenz" and r["signal"] != "kaufen":
                why = "Becker und Zweitmeinung uneinig"
            elif r["score"]["total"] < 2:
                why = "Gesamtwertung zu niedrig"
            elif n_sat >= 2:
                why = "Plätze für Satelliten belegt (besser bewertete Alternativen)"
        r["excluded"] = why
        r["slot"] = decision.LABEL_ROLE[r["role"]]
        if not why:
            picks.append(r)
            used.add(r["bucket"])
            used_fam.add(r["family"])
            n_sat += r["role"] == "Satellit"
    # Aufteilung neuen Kapitals: Anker 85 % (bzw. 100 %, wenn kein Satellit empfohlen), innerhalb nach Baustein-Gewicht
    part_w = {"Geldmarkt": 30, "Kurzlaufende Staatsanleihen (AAA)": 30, "Gold physisch": 20, "Breiter Markt (Welt)": 20}
    anchors = [r for r in picks if r["role"] == "Anker"]
    sats = [r for r in picks if r["role"] == "Satellit"]
    a_share = decision.TARGET["Anker"] if sats else 100.0
    tw = sum(part_w.get(r["bucket"], 20) for r in anchors) or 1
    for r in anchors:
        r["alloc"] = round(a_share * part_w.get(r["bucket"], 20) / tw)
    for r in sats:
        r["alloc"] = round((100 - a_share) / len(sats))
    picks.sort(key=lambda r: (r["role"] != "Anker", -r["alloc"]))
    return rows, picks




def select_offensive(rows, holdings):
    """Szenario B: ohne Barbell-Anker. 100 % in die diversifizierte Auswahl mit vier Meinungen
    (3 Einzelaktien + 2 Kern-Bausteine, Sektor-/Familiengrenzen, ohne Ausschluss der Mitte)."""
    picks, used, used_fam, filled = [], set(), set(), {"Einzelaktie": 0, "Kern-Baustein": 0}
    slots = {"Einzelaktie": 3, "Kern-Baustein": 2}
    for r in rows:
        why = None
        if r["role"] == "Anker":
            r["excludedB"] = "Szenario B ohne Barbell-Anker"
            continue
        sl = br.slot(r)
        if r["signal"] == "nein":
            why = "Becker: nicht einsteigen"
        elif r["bucketWeight"] >= BUCKET_MAX:
            why = f"Sektor im Depot schon {pct(r['bucketWeight']).lstrip('+')} ({r['bucket']})"
        elif r["familyWeight"] >= FAMILY_MAX:
            why = f"Familie '{r['family']}' im Depot schon {pct(r['familyWeight']).lstrip('+')} – Klumpenrisiko"
        elif r["bucket"] in used or r["family"] in used_fam:
            why = "Sektor/Familie in der Empfehlung schon belegt"
        elif r["agree"] == "Divergenz" and r["signal"] != "kaufen":
            why = "Becker und Zweitmeinung uneinig"
        elif r["score"]["total"] < 2:
            why = "Gesamtwertung zu niedrig"
        elif filled[sl] >= slots[sl]:
            why = f"Plätze für {sl} belegt (besser bewertete Alternativen)"
        r["excludedB"] = why
        if not why:
            r["slotB"] = sl
            picks.append(r)
            used.add(r["bucket"])
            used_fam.add(r["family"])
            filled[sl] += 1
    w = {r["t"]: (2 if r["slotB"] == "Kern-Baustein" else 1) for r in picks}
    tw = sum(w.values()) or 1
    for r in picks:
        r["allocB"] = round(100 * w[r["t"]] / tw)
    if picks:  # Rundungsdifferenz der größten Position zuschlagen, damit die Summe 100 % ergibt
        max(picks, key=lambda r: r["allocB"])["allocB"] += 100 - sum(r["allocB"] for r in picks)
    picks.sort(key=lambda r: -r["allocB"])
    return picks


def de(d):
    return f"{d[8:]}.{d[5:7]}.{d[:4]}"


def write_md(pid, label, holdings, bw, buy, analysis):
    OUT_MD.mkdir(parents=True, exist_ok=True)
    L = [f"# 👤 Depot {label} – Bewertung", "",
         f"**Quelle:** `input/{pid}/` · **Kurse:** Yahoo Finance {de(buy['generated'])} · **Becker:** {STAND}", "",
         "> Keine Anlageberatung. Ohne Stückzahlen wird jede Position gleich gewichtet. Kaufkurse in der Depot-Datei werden als EUR interpretiert.", "",
         "## 🧭 Gesamtanalyse", ""] + [f"- {x}" for x in analysis] + ["",
         "## 📋 Entscheidung je Position", "",
         "| Position | Rolle | Sektor | Kurs | seit Kauf | vs. 200T | Meinungen (+/−) | Entscheidung | Priorität | Grund |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for h in holdings:
        price = f"{h['price']:.2f} {h['currency']}".replace(".", ",") if h.get("price") is not None else "–"
        L.append(f"| {h['name']} ({h['t']}) | {h.get('role', '–')} / {h.get('style', '–')} | {h['bucket']} | {price} | {pct(h.get('perf'))} | "
                 f"{pct(h.get('vsMa200'))} | {h.get('votesPos', 0)}/{h.get('votesNeg', 0)} | **{h['entscheidung']}** | {h.get('prio') or '–'} | {h['egrund']} |")
    L += ["", "## Sektorgewichte", ""] + [f"- {k}: {str(v).replace('.', ',')} %" for k, v in sorted(bw.items(), key=lambda x: -x[1])]
    L += ["", "## Details je Position", ""]
    for h in holdings:
        L += [f"### {h['t']} – {h['entscheidung']}", "", f"{h['egrund']}", ""] + [f"- {x}" for x in h.get("gruende", [])] + [""]
    L += ["", "---", f"[🛒 Kaufempfehlung]({pid}_kaufempfehlung.md) | [⬅️ Dashboard](../index.md)", ""]
    (OUT_MD / f"{pid}.md").write_text("\n".join(L), encoding="utf-8")

    rows = {r["t"]: r for r in buy["rows"]}
    K = [f"# 🛒 Kaufempfehlung {label}", "", f"**Erstellt:** {de(buy['generated'])} · **Gültig bis:** {de(buy['validUntil'])} · "
         f"**Becker-Stand:** {de(buy['beckerDate'])} ({buy['beckerAge']} Tage)", "",
         "> Barbell-Regeln: Neues Kapital zuerst in fehlende Anker-Bausteine (Geldmarkt, kurzlaufende AAA-Staatsanleihen, physisches Gold, "
         "höchstens ein Welt-ETF). Satelliten nur, solange der Satellit unter 15 % liegt. Kandidaten der Mitte werden ausgeschlossen. Keine Anlageberatung.", "",
         "| # | Titel | Barbell-Rolle | Sektor (Gewicht heute) | Anteil | 1 Becker | 2 Analysten | 3 Fundamental | 4 Momentum | Meinungsbild |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(buy["picks"], 1):
        r = rows[t]
        K.append(f"| {i} | **{r['name']} ({t})** | {r['role']} | {r['bucket']} ({str(r['bucketWeight']).replace('.', ',')} %) | {r['alloc']} % | "
                 f"{r['signalLabel']} | {r['score']['analystLabel']} | {r['fund']['label']} | {r['mom']['label']} | {r['votesPos']}/4 positiv |")
    sb = buy["scenarios"][1]
    K += ["", f"## {sb['title']}", "", sb["text"], "", "| # | Titel | Rolle | Sektor | Anteil | Meinungsbild |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(sb["picks"], 1):
        r = rows[t]
        K.append(f"| {i} | **{r['name']} ({t})** | {r['role']} | {r['bucket']} | {r['allocB']} % | {r['votesPos']}/4 positiv |")
    K += ["", "## Die vier Meinungen im Detail", ""]
    for t in dict.fromkeys(buy["picks"] + sb["picks"]):
        r = rows[t]
        K += [f"### {r['name']} ({t})", "",
              f"1. **Becker ({de(buy['beckerDate'])}):** {r['signalLabel']} – {r['becker']}",
              f"2. **Analysten (Yahoo, {de(buy['generated'])}):** {r['score']['analystLabel']}",
              f"3. **Fundamental ({de(r['fund']['date'])}):** {r['fund']['label']} – " + "; ".join(r["fund"]["details"]),
              f"4. **Momentum ({de(r['mom']['date'])}):** {r['mom']['label']} – " + "; ".join(r["mom"]["details"]), ""]
    K += ["## Nicht empfohlen", "", "| Titel | Meinungsbild | Grund Szenario A | Grund Szenario B |", "|---|---|---|---|"]
    K += [f"| {r['name']} ({r['t']}) | {r['votesPos']}/4 positiv | {r['excluded'] or 'empfohlen'} | {r.get('excludedB') or 'empfohlen'} |"
          for r in buy["rows"] if r["excluded"] or r.get("excludedB")]
    K += ["", "---", f"[👤 Depot {label}]({pid}.md) | [⬅️ Dashboard](../index.md)", ""]
    (OUT_MD / f"{pid}_kaufempfehlung.md").write_text("\n".join(K), encoding="utf-8")


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    today = date.today()
    fx = fx_rates()

    def load(c):
        hist = yahoo.fetch_history(c["t"])
        try:
            q = yahoo.fetch_consensus(c["t"])
        except Exception:  # noqa: BLE001
            q = None
        try:
            fund = yahoo.fetch_fundamentals(c["t"])
        except Exception:  # noqa: BLE001
            fund = None
        return c, hist, q, fund

    with ThreadPoolExecutor(8) as ex:
        loaded = list(ex.map(load, br.CANDIDATES))
    spy = yahoo.fetch_history("SPY")   # Vergleichsmaßstab für die relative Stärke

    OUT_JSON.mkdir(parents=True, exist_ok=True)
    index = []
    for folder in sorted(p for p in INPUT.iterdir() if p.is_dir()):
        files = sorted(folder.glob("*.md"))
        if not files:
            continue
        pid, label = folder.name, folder.name
        holdings = analyse(parse(files[0]), fx, spy)
        bw, fw = weights(holdings)
        for h in holdings:
            if h["resolved"]:
                h["role"] = decision.role_of(h["t"], h["kind"], h["bucket"], h["becker"].get("depot"), h.get("fundRaw"))
                h["style"] = decision.style_of(h, h["role"])
        bb = decision.barbell(holdings)
        for h in holdings:
            decision.decide(h, bw, fw, family, bb)
        prio = {"hoch": 0, "mittel": 1, "niedrig": 2, "": 3}
        holdings.sort(key=lambda h: (decision.ORDER.get(h["entscheidung"], 9), prio.get(h.get("prio", ""), 3), h["bucket"], h["t"]))
        rows, picks = buy_for(holdings, bw, fw, today, loaded, spy, bb)
        picks_b = select_offensive(rows, holdings)
        analysis, acts = decision.synthesis(label, holdings, bw, fw, [r["t"] for r in picks], family, bb)
        analysis.insert(-1, "**Szenario B (offensiv, ohne Barbell-Anker):** " + ", ".join(f"{r['t']} {r['allocB']} %" for r in picks_b)
                        + " – Alternative zur strikten Barbell-Aufteilung mit höherem Risiko.")
        perfs = [h["perf"] for h in holdings if h.get("perf") is not None]
        buy = {"generated": today.isoformat(), "validUntil": (today + timedelta(days=br.MAX_AGE)).isoformat(), "maxAge": br.MAX_AGE,
               "beckerDate": br.BECKER_DATE, "beckerAge": br.age(br.BECKER_DATE, today), "picks": [r["t"] for r in picks], "rows": rows,
               "scenarios": [
                   {"id": "A", "title": "Szenario A · Barbell strikt", "allocKey": "alloc", "excludedKey": "excluded",
                    "picks": [r["t"] for r in picks],
                    "text": "Verbindliche Barbell-Strategie: neues Kapital zuerst in fehlende Anker-Bausteine (85 %, bzw. 100 %, solange der "
                            "Satellit über 15 % liegt). Kandidaten der Mitte sind ausgeschlossen."},
                   {"id": "B", "title": "Szenario B · Offensiv (ohne Barbell-Anker)",
                    "allocKey": "allocB", "excludedKey": "excludedB", "picks": [r["t"] for r in picks_b],
                    "text": "Kein Barbell-Anteil: Geldmarkt, kurzlaufende Staatsanleihen, physisches Gold und Welt-ETF sind ausgeschlossen. "
                            "100 % des neuen Kapitals in die diversifizierte Auswahl mit vier Meinungen: bis zu 3 Einzelaktien und 2 Kern-Bausteine "
                            "(Gewicht 2:1), max. ein Titel je Sektor/Familie, keine Sektoren ≥ 10 % bzw. Familien ≥ 25 %, Mitte erlaubt. "
                            "Weicht bewusst von der verbindlichen Barbell-Strategie ab – kein Krisenpuffer, höheres Risiko, höhere Renditechance."}],
               "market": br.fresh_web("*", today),
               "staleWeb": [dict(date=d, text=x, source=s[0]) for d, x, _, s in br.WEB.get("*", []) if br.age(d, today) > br.MAX_AGE]}
        data = {"id": pid, "label": label, "generated": today.isoformat(), "holdings": holdings, "bucketWeights": bw, "familyWeights": fw,
                "perf": round(sum(perfs) / len(perfs), 1) if perfs else None, "perfCount": len(perfs), "buy": buy,
                "unresolved": [h["raw"] for h in holdings if not h["resolved"]], "analysis": analysis, "actions": acts, "barbell": bb}
        (OUT_JSON / f"{pid}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        write_md(pid, label, holdings, bw, buy, analysis)
        index.append({"id": pid, "label": label, "n": len(holdings), "perf": data["perf"], "picks": buy["picks"]})
        print(f"{pid}: {len(holdings)} Positionen ({len(data['unresolved'])} nicht aufgelöst) · Kaufempfehlung: {', '.join(buy['picks'])}")
        print(f"   Szenario B: {', '.join(f'{r['t']} {r['allocB']} %' for r in picks_b)}")
        print(f"   Barbell Ist: {bb['ist']} · {' | '.join(bb['status'])}")
        for k in ("Verkaufen", "Trimmen", "Nachkaufen", "Halten"):
            print(f"   {k:10} {', '.join(acts.get(k, []))}")
    (OUT_JSON / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


if __name__ == "__main__":
    run()
