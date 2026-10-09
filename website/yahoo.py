# -*- coding: utf-8 -*-
"""Lädt Kursdaten von Yahoo Finance (inoffizielle Chart-API, keine Abhängigkeiten).

    python website/yahoo.py          -> schreibt website/data/prices.json (2 Jahre, täglich)

Wird von build.py eingebettet und von serve.py für Live-Kurse genutzt.
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "prices.json"

# Ticker im Wiki -> Yahoo-Symbol (nur Abweichungen; sonst identisch)
YAHOO = {
    "3CP": "1810.HK",      # Xiaomi, Hongkong
    "DN3": "3350.T",       # Metaplanet, Tokio
    "EWG2": "EWG2.SG",     # EUWAX Gold II, Stuttgart
    "0D7Z": "AIGI.L",      # WisdomTree Industrial Metals, London
    "XEON": "XEON.DE",     # Xtrackers EUR Overnight, Xetra
    "EXVM": "EXVM.DE",     # iShares eb.rexx Government Germany 0-1yr (AAA, kurzlaufend)
    "4GLD": "4GLD.DE",     # Xetra-Gold (physisch hinterlegt)
    "VWCE": "VWCE.DE",     # Vanguard FTSE All-World
}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def symbol(ticker):
    return YAHOO.get(ticker, ticker)


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def sma(values, n):
    out, s = [], 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(round(s / n, 4) if i >= n - 1 else None)
    return out


def fetch_history(ticker, rng="2y"):
    sym = symbol(ticker)
    d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d")
    res = d["chart"]["result"][0]
    meta = res["meta"]
    ts = res.get("timestamp") or []
    closes = res["indicators"]["quote"][0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, closes) if c is not None]
    dates = [time.strftime("%Y-%m-%d", time.gmtime(t)) for t, _ in pts]
    close = [round(c, 4) for _, c in pts]
    ma200 = sma(close, 200)
    last = meta.get("regularMarketPrice") or (close[-1] if close else None)
    prev = close[-2] if len(close) > 1 else None
    one_year = close[-252:] if close else []
    return {
        "ticker": ticker, "symbol": sym, "currency": meta.get("currency"),
        "name": meta.get("longName") or meta.get("shortName"),
        "price": last, "prev": prev,
        "chg1d": round((last / prev - 1) * 100, 2) if last and prev else None,
        "chg1y": round((last / one_year[0] - 1) * 100, 2) if last and one_year else None,
        "hi52": max(one_year) if one_year else None, "lo52": min(one_year) if one_year else None,
        "ma200": ma200[-1] if ma200 else None,
        "vsMa200": round((last / ma200[-1] - 1) * 100, 2) if last and ma200 and ma200[-1] else None,
        "dates": dates, "close": close, "sma200": ma200,
        "asof": time.strftime("%Y-%m-%d %H:%M", time.localtime(meta.get("regularMarketTime", time.time()))),
    }


def fetch_quotes(tickers):
    """Leichter Live-Abruf: nur aktueller Kurs und Tagesveränderung."""
    def one(t):
        try:
            d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol(t)}?range=5d&interval=1d")
            r = d["chart"]["result"][0]
            m = r["meta"]
            closes = [c for c in (r["indicators"]["quote"][0].get("close") or []) if c is not None]
            p = m.get("regularMarketPrice")
            # Vortagesschluss = vorletzter Tagesschluss im 5-Tage-Fenster (chartPreviousClose läge 5 Tage zurück)
            pc = closes[-2] if len(closes) > 1 else m.get("chartPreviousClose")
            return t, {"price": p, "chg1d": round((p / pc - 1) * 100, 2) if p and pc else None,
                       "asof": time.strftime("%H:%M", time.localtime(m.get("regularMarketTime", time.time())))}
        except Exception as e:  # noqa: BLE001
            return t, {"error": str(e)}
    with ThreadPoolExecutor(8) as ex:
        return dict(ex.map(one, tickers))


def fetch_all(tickers):
    out, errors = {}, {}

    def one(t):
        try:
            return t, fetch_history(t), None
        except Exception as e:  # noqa: BLE001
            return t, None, str(e)

    with ThreadPoolExecutor(8) as ex:
        for t, data, err in ex.map(one, tickers):
            if data:
                out[t] = data
            else:
                errors[t] = err
    return out, errors


def update(tickers):
    data, errors = fetch_all(tickers)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fetched": time.strftime("%Y-%m-%d %H:%M"), "prices": data}
    DATA.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Yahoo: {len(data)} Kursreihen geladen -> {DATA}")
    for t, e in errors.items():
        print(f"  FEHLER {t} ({symbol(t)}): {e}")
    return payload


def wiki_tickers():
    return sorted(p.stem for p in (HERE.parent / "portfolio" / "assets").glob("*.md"))


if __name__ == "__main__":
    update(wiki_tickers())


# ---------------------------------------------------------------- Analysten-Konsens (Zweitmeinung)
_SESSION = {}


def _opener():
    """Yahoo verlangt für quoteSummary ein Cookie + Crumb."""
    if "op" not in _SESSION:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = list(UA.items())
        try:
            op.open("https://fc.yahoo.com", timeout=15)
        except Exception:  # noqa: BLE001 – liefert 404, setzt aber das Cookie
            pass
        _SESSION["crumb"] = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=15).read().decode()
        _SESSION["op"] = op
    return _SESSION["op"], _SESSION["crumb"]


def fetch_consensus(ticker):
    """Analystenkonsens von Yahoo Finance: Empfehlung, Durchschnittsnote (1 = Strong Buy … 5 = Sell),
    Anzahl Analysten, mittleres Kursziel und Verteilung des aktuellen Monats."""
    op, crumb = _opener()
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol(ticker)}"
           f"?modules=financialData,recommendationTrend,assetProfile&crumb={crumb}")
    with op.open(url, timeout=20) as r:
        res = json.load(r)["quoteSummary"]["result"][0]
    f = res.get("financialData", {}) or {}
    raw = lambda k: (f.get(k) or {}).get("raw")
    trend = (res.get("recommendationTrend", {}).get("trend") or [{}])[0]
    price, target = raw("currentPrice"), raw("targetMeanPrice")
    return {
        "rating": f.get("recommendationKey"), "mean": raw("recommendationMean"),
        "analysts": raw("numberOfAnalystOpinions"), "target": target, "targetHigh": raw("targetHighPrice"),
        "targetLow": raw("targetLowPrice"),
        "upside": round((target / price - 1) * 100, 1) if price and target else None,
        "dist": {k: trend.get(k, 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")},
        "sector": (res.get("assetProfile") or {}).get("sector"),
        "date": time.strftime("%Y-%m-%d"),
    }


def fetch_fundamentals(ticker):
    """Fundamentaldaten (3. Meinung): Bewertung, Qualität, Verschuldung, Cashflow, Rendite."""
    op, crumb = _opener()
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol(ticker)}"
           f"?modules=defaultKeyStatistics,summaryDetail,financialData&crumb={crumb}")
    with op.open(url, timeout=20) as r:
        res = json.load(r)["quoteSummary"]["result"][0]

    def g(mod, key):
        v = (res.get(mod) or {}).get(key)
        return v.get("raw") if isinstance(v, dict) else v

    return {
        "trailingPE": g("summaryDetail", "trailingPE"), "forwardPE": g("summaryDetail", "forwardPE"),
        "peg": g("defaultKeyStatistics", "pegRatio"), "roe": g("financialData", "returnOnEquity"),
        "margin": g("financialData", "profitMargins"), "debtEq": g("financialData", "debtToEquity"),
        "fcf": g("financialData", "freeCashflow"), "mcap": g("summaryDetail", "marketCap"),
        "growth": g("financialData", "revenueGrowth"),
        "beta": g("defaultKeyStatistics", "beta") or g("summaryDetail", "beta"),
        "yield": g("summaryDetail", "yield") or g("summaryDetail", "dividendYield"),
        "date": time.strftime("%Y-%m-%d"),
    }
