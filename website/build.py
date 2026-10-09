# -*- coding: utf-8 -*-
"""Baut die statische Webseite aus portfolio/*.md nach website/public/.

Quelle der Wahrheit sind die Markdown-Dateien – nach Änderungen dort einfach
`python website/build.py` ausführen und website/public/index.html im Browser öffnen.
Keine externen Abhängigkeiten.
"""
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "portfolio"
PUB = HERE / "public"
PRICES = HERE / "data" / "prices.json"
MINE = HERE / "data" / "mine.json"
BUY = HERE / "data" / "buy.json"

DEPOT_LABEL = {"mein": "Mein Depot", "beta": "Beta-Depot", "2030": "2030-Depot", "alpha": "Alpha-Depot"}


# ---------------------------------------------------------------- Mini-Markdown
def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)

    def link(m):
        label, href = m.group(1), m.group(2)
        if href.endswith(".md"):
            href = href[:-3] + ".html"
        return f'<a href="{href}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)


def md_to_html(md):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or s.startswith("<!--"):
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            lvl = len(m.group(1))
            text = m.group(2)
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            out.append(f'<h{lvl} id="{slug}">{inline(text)}</h{lvl}>')
            i += 1
            continue
        if s == "---":
            out.append("<hr>")
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            t = ['<div class="table-wrap"><table><thead><tr>']
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in body:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
            continue
        if s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||>|- |---)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- Seiten
def page(title, body, root="", extra_head=""):
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{root}style.css">
<script src="{root}charts.js"></script>
{extra_head}
</head>
<body>
<header class="topbar">
  <a class="brand" href="{root}index.html">Portfolio-Wiki</a>
  <nav>
    <a href="{root}index.html">Dashboard</a>
    <a href="{root}mein-depot.html">Mein Depot</a>
    <a href="{root}kaufempfehlung.html">Kaufempfehlung</a>
    <a href="{root}overview.html">Analyse &amp; Makro</a>
  </nav>
  <button class="theme-toggle" type="button" aria-label="Farbschema wechseln" onclick="toggleTheme()">◐</button>
</header>
<main>
{body}
</main>
<footer>Keine Anlageberatung · Daten aus Balthasar-Becker-Reports KW38–40/2026 · generiert aus <code>portfolio/*.md</code></footer>
<script>
function toggleTheme(){{
  var r=document.documentElement, cur=r.getAttribute('data-theme');
  var dark = cur ? cur==='dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  r.setAttribute('data-theme', dark?'light':'dark');
  try{{localStorage.setItem('theme', dark?'light':'dark')}}catch(e){{}}
}}
try{{var t=localStorage.getItem('theme'); if(t) document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}
</script>
</body>
</html>
"""


def read_meta(md):
    m = re.search(r"<!-- meta: (\{.*?\}) -->", md)
    return json.loads(m.group(1)) if m else {}


def section(md, heading_prefix):
    """Gibt die Listenpunkte eines ##-Abschnitts als {label: text} zurück."""
    m = re.search(rf"^## {re.escape(heading_prefix)}.*?$(.*?)(?=^## |^---)", md, re.S | re.M)
    res = {}
    if m:
        for li in re.findall(r"^- (.+)$", m.group(1), re.M):
            k = re.match(r"\*{1,2}([^*]+?):\*{1,2}\s*(.*)", li)
            if k:
                res[k.group(1).strip()] = k.group(2).strip()
    return res


def price_card(ticker, q, fetched, depot):
    if not q:
        return '<section class="card"><p class="cap">Keine Kursdaten von Yahoo Finance verfügbar.</p></section>'
    cur = q["currency"] or ""
    pct = lambda v: "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")
    num = lambda v: "–" if v is None else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    stats = [
        ("Kurs", f'<span data-live="price">{num(q["price"])}</span> {cur}', f'Yahoo: {q["symbol"]}'),
        ("1 Tag", f'<span data-live="chg1d">{pct(q["chg1d"])}</span>', "Veränderung"),
        ("1 Jahr", pct(q["chg1y"]), "Veränderung"),
        ("200-Tage-Linie", num(q["ma200"]), f'Abstand {pct(q["vsMa200"])}'),
        ("52W Hoch / Tief", f'{num(q["hi52"])}', f'Tief {num(q["lo52"])}'),
    ]
    tiles = "".join(f'<div class="stat"><small>{a}</small><b>{b}</b><small>{c}</small></div>' for a, b, c in stats)
    series = {k: q[k] for k in ("ticker", "currency", "dates", "close", "sma200")}
    return f"""<section class="card depot-{depot}">
  <h2>Kursverlauf <span class="live" id="live">Stand {html.escape(fetched or '')}</span></h2>
  <p class="cap">Tagesschlusskurse von Yahoo Finance mit 200-Tage-Linie – Beckers zentrale Marke für Ein- und Ausstiege.</p>
  <div class="stats">{tiles}</div>
  <div id="chart"></div>
</section>
<script>
lineChart(document.getElementById('chart'), {json.dumps(series, separators=(",", ":"))});
liveQuotes([{json.dumps(ticker)}], d => {{
  const q = d[{json.dumps(ticker)}]; if (!q || q.error) return;
  document.querySelector('[data-live=price]').textContent = fmtNum(q.price);
  document.querySelector('[data-live=chg1d]').textContent = fmtPct(q.chg1d);
  const l = document.getElementById('live'); l.textContent = 'Live ' + q.asof; l.classList.add('on');
}});
</script>"""


def buy_page(b, wiki):
    de = lambda d: f"{d[8:]}.{d[5:7]}.{d[:4]}"
    pct = lambda v: "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")
    num = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    dec = lambda v: str(v).replace(".", ",")
    esc = html.escape
    rows = {r["t"]: r for r in b["rows"]}
    link = lambda t: f"assets/{t}.html" if t in wiki else f"https://finance.yahoo.com/quote/{t}"
    sc = lambda i: f"c{i + 1}"
    stale_becker = b["beckerAge"] > b["maxAge"]

    alloc_bar = "".join(f'<span class="{sc(i)}" style="flex:{rows[t]["alloc"]}" title="{t} {rows[t]["alloc"]} %"></span>'
                        for i, t in enumerate(b["picks"]))
    alloc_leg = "".join(f'<span class="{sc(i)}"><i></i><b>{t}</b> {rows[t]["alloc"]} % · {esc(rows[t]["bucket"])}</span>'
                        for i, t in enumerate(b["picks"]))
    before = "".join(f'<span class="chip-s">{esc(h["bucket"])} <small>{h["t"]}</small></span>' for h in b["holdings"])
    after = "".join(f'<span class="chip-s new">{esc(rows[t]["bucket"])} <small>{t}</small></span>' for t in b["picks"])

    cards = ""
    for i, t in enumerate(b["picks"]):
        r = rows[t]
        q = r["consensus"] or {}
        if q.get("mean"):
            d = q["dist"]
            segs = "".join(f'<span class="r-{k}" style="flex:{v}" title="{lbl}: {v}"></span>'
                           for k, v, lbl in [("sb", d["strongBuy"], "Strong Buy"), ("b", d["buy"], "Buy"), ("h", d["hold"], "Hold"),
                                             ("s", d["sell"], "Sell"), ("ss", d["strongSell"], "Strong Sell")] if v)
            second = (f'<div class="op-head"><b>{esc(r["score"]["analystLabel"])}</b><span class="age ok">{de(q["date"])} · aktuell</span></div>'
                      f'<p>Yahoo-Analystenkonsens: Note <b>{dec(round(q["mean"], 2))}</b> (1 = Strong Buy … 5 = Sell), {q["analysts"]} Analysten.</p>'
                      f'<div class="ratings">{segs}</div><div class="r-leg">{d["strongBuy"]}× Strong Buy · {d["buy"]}× Buy · '
                      f'{d["hold"]}× Hold · {d["sell"] + d["strongSell"]}× Sell</div>'
                      f'<p>Ø Kursziel <b>{num(q["target"])} {r["currency"]}</b> ({pct(q["upside"])}), Spanne {num(q["targetLow"])}–{num(q["targetHigh"])}.</p>')
        else:
            second = (f'<div class="op-head"><b>Kein Analystenkonsens (ETF)</b><span class="age ok">{de(b["generated"])} · aktuell</span></div>'
                      f'<p>Zweitmeinung aus Trend und Webquellen: {pct(r["vsMa200"])} zur 200-Tage-Linie, 1 Jahr {pct(r["chg1y"])}.</p>')
        for w in r["web"]:
            tone = {"+": "pos", "−": "neg", "0": ""}[w["tone"]]
            second += (f'<p class="web {tone}"><span class="age ok">{de(w["date"])}</span> {esc(w["text"])} '
                       f'<a href="{w["url"]}" target="_blank" rel="noopener">{esc(w["source"])}</a></p>')
        agree_cls = {"Übereinstimmung": "pos", "Divergenz": "neg"}.get(r["agree"], "")
        tech = '<p class="note">Einziger zusätzlicher Technologie-/Halbleiterwert – CRWD ist bereits Tech.</p>' if r.get("techNote") else ""
        becker_age = f'{de(b["beckerDate"])} · {b["beckerAge"]} Tage' + (" – veraltet" if stale_becker else "")
        s_ = r["score"]
        cards += f"""<article class="buy-card {sc(i)}">
  <header>
    <div><span class="rank">{i + 1}</span><a class="tk" href="{link(t)}">{t}</a> <span class="nm">{esc(r['name'])}</span></div>
    <div class="buy-meta"><span class="badge-s">{esc(r['bucket'])}</span><span class="badge-s">{r['slot']}</span><b>{r['alloc']} %</b></div>
  </header>
  <div class="trend">{num(r['price'])} {r['currency']} · <span class="{'pos' if (r['vsMa200'] or 0) > 0 else 'neg'}">{pct(r['vsMa200'])} vs. 200T</span> · <span data-spark="{json.dumps(r['spark'])}"></span></div>
  <div class="vs">
    <section class="op becker">
      <h4>Becker</h4>
      <div class="op-head"><b>{esc(r['signalLabel'])}</b><span class="age {'stale' if stale_becker else 'ok'}">{becker_age}</span></div>
      <p>{esc(r['becker'])}</p>
    </section>
    <section class="op second">
      <h4>Zweitmeinung</h4>
      {second}
    </section>
  </div>
  <footer><span class="agree {agree_cls}">{esc(r['agree'])}</span> <span class="muted">Wertung {dec(s_['total'])} = Becker {dec(s_['becker'])} · Analysten {dec(s_['analyst'])} · Web {dec(s_['web'])} · Trend {dec(s_['trend'])}</span>{tech}</footer>
</article>"""

    excl = "".join(
        f'<tr><td><a class="tk" href="{link(r["t"])}">{r["t"]}</a><div class="sub">{esc(r["name"])}</div></td><td>{esc(r["bucket"])}</td>'
        f'<td>{esc(r["signalLabel"])}</td><td>{esc(r["score"]["analystLabel"])}</td><td class="num">{dec(r["score"]["total"])}</td>'
        f'<td>{esc(r["excluded"])}</td></tr>' for r in b["rows"] if r["excluded"])
    market = "".join(f'<li><span class="age ok">{de(w["date"])}</span> {esc(w["text"])} '
                     f'<a href="{w["url"]}" target="_blank" rel="noopener">{esc(w["source"])}</a></li>' for w in b["market"])
    stale_web = "".join(f'<li><span class="age stale">{de(w["date"])}</span> {esc(w["source"])} – ignoriert (älter als {b["maxAge"]} Tage)</li>'
                        for w in b["staleWeb"])
    warn = ""
    if stale_becker:
        warn = (f'<div class="banner warn">⚠️ <b>Becker-Signale veraltet:</b> letzter Report vom {de(b["beckerDate"])} ({b["beckerAge"]} Tage). '
                'Sie zählen nur halb. Neue PDFs nach <code>PDF_input/</code> legen und <code>python website/serve.py</code> ausführen.</div>')

    return f"""
<div id="freshness" class="banner" hidden></div>
<section class="hero">
  <h1>Kaufempfehlung</h1>
  <p>Erstellt am <b>{de(b['generated'])}</b>, gültig bis <b>{de(b['validUntil'])}</b> (max. {b['maxAge']} Tage). Becker-Signale gegenübergestellt mit einer Zweitmeinung aus Yahoo-Analystenkonsens und datierten Webquellen – gefiltert auf Diversifikation zu deinem Depot. Keine Anlageberatung.</p>
</section>
{warn}
<section class="card">
  <h2>Diversifikation</h2>
  <p class="cap">Regeln: max. ein Titel je Sektor und je Familie (nur ein Technologie-/Halbleiterwert), keine Sektoren, die das Depot schon abdeckt, 3 Einzelaktien + 2 Kern-Bausteine (doppelt gewichtet, Becker-Barbell).</p>
  <div class="cover"><div><small>Heute im Depot</small><div>{before}</div></div><div><small>Neu durch die Empfehlung</small><div>{after}</div></div></div>
  <h3 class="mini">Aufteilung neuen Kapitals</h3>
  <div class="wbar">{alloc_bar}</div><div class="wlegend">{alloc_leg}</div>
</section>
<section class="buy-list">{cards}</section>
<section class="card">
  <h2>Nicht empfohlen</h2>
  <p class="cap">Alle geprüften Kandidaten aus Beckers Depots und Watchlists mit dem Grund für den Ausschluss.</p>
  <div class="table-wrap"><table><thead><tr><th>Titel</th><th>Sektor</th><th>Becker</th><th>Zweitmeinung</th><th class="num">Wertung</th><th>Grund</th></tr></thead><tbody>{excl}</tbody></table></div>
</section>
<section class="card">
  <h2>Marktstimmung aus dem Web</h2>
  <p class="cap">Nur Quellen, die höchstens {b['maxAge']} Tage alt sind.</p>
  <ul class="plain">{market}{stale_web}</ul>
</section>
<script>
(function(){{
  const valid = new Date('{b['validUntil']}T23:59:59'), gen = new Date('{b['generated']}T00:00:00');
  const days = Math.floor((Date.now() - gen) / 864e5), el = document.getElementById('freshness');
  if (Date.now() > valid) {{
    el.hidden = false; el.className = 'banner stale';
    el.innerHTML = '⛔ <b>Diese Kaufempfehlung ist ' + days + ' Tage alt und damit abgelaufen.</b> Bitte neu erzeugen: <code>python website/serve.py</code>';
  }}
  document.querySelectorAll('[data-spark]').forEach(s => s.innerHTML = sparkline(JSON.parse(s.dataset.spark), 80, 22));
}})();
</script>"""


def mine_page(mine):
    items = mine["items"]
    pct = lambda v: f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")
    num = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sc = lambda i: f"s{i % 4 + 1}"
    cards = ""
    for i, a in enumerate(items):
        r = a["reco"]
        cls = "pos" if a["perf"] > 0 else "neg"
        cards += f"""<div class="reco-card {sc(i)}">
  <h3><a href="assets/{a['ticker']}.html">{a['ticker']}</a><span class="reco reco-{r['cls']}">{html.escape(r['aktion'])}</span></h3>
  <div class="nm">{html.escape(a['name'])}</div>
  <div class="kv">
    <div><small>Kauf {a['buyDate'][8:]}.{a['buyDate'][5:7]}.</small><b>{num(a['buy'])}{'*' if a['buyAssumed'] else ''}</b></div>
    <div><small>Kurs ({a['currency']})</small><b data-live-p="{a['ticker']}">{num(a['price'])}</b></div>
    <div><small>seit Kauf</small><b class="{cls}">{pct(a['perf'])}</b></div>
    <div><small>vs. 200-Tage-Linie</small><b class="{'pos' if a['vsMa200'] > 0 else 'neg'}">{pct(a['vsMa200'])}</b></div>
  </div>
  <p><strong>{html.escape(r['kurz'])}</strong></p>
</div>"""
    wbar = "".join(f'<span class="{sc(i)}" style="flex:{a["weight"]}" title="{a["ticker"]} {a["weight"]} %"></span>' for i, a in enumerate(items))
    wleg = "".join(f'<span class="{sc(i)}"><i></i>{a["ticker"]} {str(a["weight"]).replace(".", ",")} %</span>' for i, a in enumerate(items))
    series = [{"label": a["ticker"], "dates": a["dates"], "close": a["close"], "cls": sc(i)} for i, a in enumerate(items)]
    md = (SRC / "mein_depot.md").read_text(encoding="utf-8") if (SRC / "mein_depot.md").exists() else ""
    md = re.sub(r"^## 📊 Überblick.*?(?=^## )", "", md, flags=re.S | re.M)  # Tabelle steht schon als Karten oben
    md = md.replace("](assets/", "](assets/").replace("](index.md)", "](index.md)")
    return f"""
<section class="hero">
  <h1>Mein Depot</h1>
  <p>Performance seit Kauf <strong class="{'pos' if mine['total'] > 0 else 'neg'}">{pct(mine['total'])}</strong> · {len(items)} Positionen · Kurse Yahoo Finance · Empfehlungen nach Beckers Regelwerk und Buffett-Check. Keine Anlageberatung.</p>
</section>
<section class="reco-grid">{cards}</section>
<section class="card">
  <h2>Performance seit Kauf</h2>
  <p class="cap">Jede Position indexiert auf 100 am Kauftag. Linie über 100 = im Gewinn.</p>
  <div id="perf"></div>
</section>
<section class="card">
  <h2>Gewichtung</h2>
  <p class="cap">{html.escape(mine['note'])} * Kaufkurs = Yahoo-Schlusskurs am Kauftag.</p>
  <div class="wbar">{wbar}</div><div class="wlegend">{wleg}</div>
</section>
<article class="prose wide">{md_to_html(md)}</article>
<script>
indexChart(document.getElementById('perf'), {json.dumps(series, separators=(",", ":"))});
liveQuotes({json.dumps([a["ticker"] for a in items])}, d => {{
  for (const t in d) {{ const el = document.querySelector('[data-live-p="'+t+'"]'); if (el && d[t].price) el.textContent = fmtNum(d[t].price); }}
}});
</script>"""


def build():
    if PUB.exists():
        shutil.rmtree(PUB)
    (PUB / "assets").mkdir(parents=True)
    shutil.copy(HERE / "style.css", PUB / "style.css")
    shutil.copy(HERE / "charts.js", PUB / "charts.js")
    prices = json.loads(PRICES.read_text(encoding="utf-8")) if PRICES.exists() else {"fetched": None, "prices": {}}
    P = prices["prices"]
    mine = json.loads(MINE.read_text(encoding="utf-8")) if MINE.exists() else {"items": []}
    mine_t = {i["ticker"] for i in mine["items"]}

    assets = []
    for f in sorted((SRC / "assets").glob("*.md")):
        md = f.read_text(encoding="utf-8")
        meta = read_meta(md)
        becker = section(md, "🗣️")
        meta["chance"] = becker.get("Chance", "")
        meta["href"] = f"assets/{f.stem}.html"
        meta["mine"] = f.stem in mine_t
        q = P.get(f.stem)
        if q:
            meta.update({k: q[k] for k in ("symbol", "currency", "price", "chg1d", "chg1y", "vsMa200")})
            meta["spark"] = q["close"][-252::3]
        assets.append(meta)

        body = md_to_html(md)
        side = "".join(
            f'<a class="{"active" if a == f.stem else ""}" href="{a}.html">{a}</a>'
            for a in sorted(p.stem for p in (SRC / "assets").glob("*.md"))
        )
        content = (f'<div class="asset-layout"><aside class="side">{side}</aside><div>'
                   f'{price_card(f.stem, q, prices["fetched"], meta.get("depot", ""))}'
                   f'<article class="prose depot-{meta.get("depot","")}">{body}</article></div></div>')
        (PUB / "assets" / f"{f.stem}.html").write_text(
            page(f"{meta.get('name', f.stem)} ({f.stem})", content, root="../"), encoding="utf-8")

    # Analyse-/Makro-Seite = gerendertes index.md
    idx_md = (SRC / "index.md").read_text(encoding="utf-8")
    (PUB / "overview.html").write_text(
        page("Analyse & Makro", f'<article class="prose wide">{md_to_html(idx_md)}</article>'), encoding="utf-8")

    # Dashboard
    stand = re.search(r"\*\*Stichtag:\*\*\s*([^·]+)", idx_md)
    stand = stand.group(1).strip() if stand else ""
    counts = {k: sum(1 for a in assets if a.get("depot") == k) for k in DEPOT_LABEL}
    cash = {"beta": "20 %", "2030": "0 %", "alpha": "11 %"}
    counts["mein"] = len(mine_t)
    roles = {"beta": "Beta-Core · Kapitalerhalt", "2030": "Langfrist-Core · Sparplan", "alpha": "Alpha-Satellit · Themenwetten"}
    cards = "".join(
        f'<button class="kpi depot-{k}" data-depot="{k}" type="button">'
        f'<span class="kpi-label">{DEPOT_LABEL[k]}</span>'
        f'<span class="kpi-value">{counts[k]}</span><span class="kpi-sub">Positionen · Cash {cash[k]}</span>'
        f'<span class="kpi-role">{roles[k]}</span></button>'
        for k in ("beta", "2030", "alpha"))
    if mine["items"]:
        cards = (f'<a class="kpi kpi-mine" href="mein-depot.html"><span class="kpi-label">Mein Depot</span>'
                 f'<span class="kpi-value">{"+" if mine["total"] > 0 else "−"}{abs(mine["total"]):.1f} %</span>'.replace(".", ",")
                 + f'<span class="kpi-sub">{len(mine_t)} Positionen · seit Kauf</span><span class="kpi-role">Handlungsempfehlung →</span></a>') + cards
    dash = f"""
<section class="hero">
  <h1>Depot-Steckbriefe</h1>
  <p>{len(assets)} Positionen aus Beckers drei Depots und deinem eigenen Depot, analysiert nach Buffett (Value) und Becker (Makro &amp; Asymmetrie). Stand {html.escape(stand)}.</p>
</section>
<section class="kpis">{cards}</section>
<section class="toolbar">
  <input id="q" type="search" placeholder="Suche nach Name, Ticker, Thema …" aria-label="Suche">
  <div class="chips" role="group" aria-label="Depot-Filter">
    <button class="chip active" data-f="all" type="button">Alle</button>
    <button class="chip" data-f="mein" type="button">Mein Depot</button>
    <button class="chip" data-f="beta" type="button">Beta</button>
    <button class="chip" data-f="2030" type="button">2030</button>
    <button class="chip" data-f="alpha" type="button">Alpha</button>
  </div>
  <span class="live" id="live">Kurse: Yahoo Finance, Stand {html.escape(prices["fetched"] or "–")}</span>
</section>
<section class="card">
  <h2>Abstand zur 200-Tage-Linie</h2>
  <p class="cap">Wo steht jede Position relativ zu ihrem 200-Tage-Durchschnitt? <i class="sw sw-up"></i>darüber (Trend intakt / Übertreibung) · <i class="sw sw-down"></i>darunter (abgestraft / antizyklische Zone). Klick öffnet den Steckbrief.</p>
  <div id="ma200"></div>
</section>
<section class="table-wrap">
<table id="t">
<thead><tr>
  <th data-k="ticker">Ticker</th><th data-k="name">Name</th><th data-k="depot">Depot</th>
  <th data-k="alloc" class="num">Anteil</th><th data-k="price" class="num">Kurs</th>
  <th data-k="chg1d" class="num">1 Tag</th><th data-k="vsMa200" class="num">vs. 200T</th>
  <th data-k="chg1y" class="num">1 Jahr</th><th data-k="moat">Moat</th>
</tr></thead>
<tbody></tbody>
</table>
</section>
<p class="note">Anteil = Gewicht innerhalb des jeweiligen Depots laut PDF; grau = letzter bekannter Wert. Kurse in Handelswährung (Yahoo Finance). Mit <code>python website/serve.py</code> werden die Kurse live alle 60 s aktualisiert.</p>
<script>
const DATA = {json.dumps(assets, ensure_ascii=False)};
const LABEL = {json.dumps(DEPOT_LABEL, ensure_ascii=False)};
let filter='all', sortK='alloc', sortDir=-1;
const num = v => {{ const m=String(v??'').replace('−','-').match(/-?\\d+(?:[.,]\\d+)?/); return m?parseFloat(m[0].replace(',','.')):-999; }};
const cls = v => v==null?'':v>0?'pos':v<0?'neg':'';
function visible(){{
  const q=document.getElementById('q').value.toLowerCase();
  return DATA.filter(a=>(filter==='all'||a.depot===filter||(filter==='mein'&&a.mine)) &&
    (a.ticker+' '+a.name+' '+a.block+' '+a.chance).toLowerCase().includes(q));
}}
function render(){{
  const rows=visible();
  rows.sort((a,b)=>{{
    let x,y;
    if(sortK==='alloc'){{x=a.alloc??num(a.last)-0.5;y=b.alloc??num(b.last)-0.5;}}
    else if(['price','chg1d','vsMa200','chg1y'].includes(sortK)){{x=a[sortK]??-1e9;y=b[sortK]??-1e9;}}
    else {{x=String(a[sortK]).toLowerCase();y=String(b[sortK]).toLowerCase();}}
    return (x>y?1:x<y?-1:0)*sortDir;
  }});
  document.querySelector('#t tbody').innerHTML = rows.map(a=>{{
    const val = a.alloc!=null ? a.alloc : num(a.last), stale = a.alloc==null;
    const w = Math.max(2, Math.min(100, (val>0?val:0)/30*100));
    return `<tr data-href="${{a.href}}">
      <td><a class="tk" href="${{a.href}}">${{a.ticker}}</a></td>
      <td>${{a.name}}${{a.mine?' <span class="badge depot-mein">Mein Depot</span>':''}}<div class="sub">${{a.block}}</div></td>
      <td><span class="badge depot-${{a.depot}}">${{LABEL[a.depot]}}</span></td>
      <td class="num"><div class="bar ${{stale?'stale':''}} depot-${{a.depot}}"><span style="width:${{w}}%"></span></div>${{stale?(a.last||'–'):a.alloc+' %'}}</td>
      <td class="num" data-p="${{a.ticker}}">${{a.price!=null?fmtNum(a.price)+' <small>'+a.currency+'</small>':'–'}}</td>
      <td class="num ${{cls(a.chg1d)}}" data-c="${{a.ticker}}">${{fmtPct(a.chg1d)}}</td>
      <td class="num ${{cls(a.vsMa200)}}">${{fmtPct(a.vsMa200)}}</td>
      <td class="num ${{cls(a.chg1y)}}">${{sparkline(a.spark)}}${{fmtPct(a.chg1y)}}</td>
      <td><span class="moat moat-${{a.moat.toLowerCase().replace('/','')}}">${{a.moat}}</span></td></tr>`;
  }}).join('') || '<tr><td colspan="9" class="empty">Keine Treffer</td></tr>';
  const bars = visible().filter(a=>a.vsMa200!=null).sort((a,b)=>b.vsMa200-a.vsMa200)
    .map(a=>({{label:a.ticker, sub:a.name, value:a.vsMa200, href:a.href,
      extra:`<div class="muted">${{LABEL[a.depot]}} <span>${{a.alloc!=null?a.alloc+' %':a.last}}</span></div>`}}));
  divergingBars(document.getElementById('ma200'), bars, {{label:'Abstand zur 200-Tage-Linie je Position'}});
}}
document.getElementById('q').addEventListener('input',render);
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>setFilter(c.dataset.f)));
document.querySelectorAll('.kpi').forEach(c=>c.addEventListener('click',()=>setFilter(c.dataset.depot)));
function setFilter(f){{filter=f;document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('active',x.dataset.f===f));render();}}
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{{
  const k=th.dataset.k; sortDir = sortK===k ? -sortDir : (['ticker','name','depot','moat'].includes(k)?1:-1); sortK=k; render();
}}));
document.querySelector('#t tbody').addEventListener('click',e=>{{
  const tr=e.target.closest('tr[data-href]'); if(tr && !e.target.closest('a')) location.href=tr.dataset.href;
}});
let rt; window.addEventListener('resize',()=>{{clearTimeout(rt);rt=setTimeout(render,150);}});
render();
liveQuotes(DATA.map(a=>a.ticker), d=>{{
  DATA.forEach(a=>{{ const q=d[a.ticker]; if(q&&!q.error){{a.price=q.price;a.chg1d=q.chg1d;}} }});
  render();
  const l=document.getElementById('live'); l.textContent='Live · Yahoo Finance '+(Object.values(d).find(q=>q.asof)||{{}}).asof; l.classList.add('on');
}});
</script>
"""
    (PUB / "index.html").write_text(page("Portfolio-Wiki", dash), encoding="utf-8")
    if BUY.exists():
        (PUB / "kaufempfehlung.html").write_text(
            page("Kaufempfehlung", buy_page(json.loads(BUY.read_text(encoding="utf-8")), {a["ticker"] for a in assets})),
            encoding="utf-8")
    if mine["items"]:
        (PUB / "mein-depot.html").write_text(page("Mein Depot", mine_page(mine)), encoding="utf-8")
    print(f"Webseite gebaut: {PUB / 'index.html'} ({len(assets)} Steckbriefe)")


if __name__ == "__main__":
    build()
