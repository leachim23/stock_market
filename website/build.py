# -*- coding: utf-8 -*-
"""Baut die statische Webseite aus portfolio/*.md nach docs/ (GitHub Pages).

Quelle der Wahrheit sind die Markdown-Dateien – nach Änderungen dort einfach
`python website/build.py` ausführen und docs/index.html im Browser öffnen.
Keine externen Abhängigkeiten.
"""
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "portfolio"
PUB = HERE.parent / "docs"  # GitHub Pages liefert /docs aus
PRICES = HERE / "data" / "prices.json"
DEPOTS = HERE / "data" / "depots"
DEPOT_NAV = []  # [(id, label)] – wird in build() gefüllt

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
    {"".join(f'<a href="{root}depot-{i}.html">Depot {l}</a>' for i, l in DEPOT_NAV)}
    <a href="{root}overview.html">Analyse &amp; Makro</a>
  </nav>
  <button class="theme-toggle" type="button" aria-label="Farbschema wechseln" onclick="toggleTheme()">◐</button>
</header>
<main>
{body}
</main>
<footer>Keine Anlageberatung · Daten aus Inputgeber-Reports KW38–42/2026 · generiert aus <code>portfolio/*.md</code></footer>
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
  <p class="cap">Tagesschlusskurse von Yahoo Finance mit 200-Tage-Linie – Inputgebers zentrale Marke für Ein- und Ausstiege.</p>
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


def votes_html(r):
    names = {"inputgeber": "Inputgeber", "analysten": "Analysten", "fundamental": "Fundamental", "momentum": "Momentum"}
    dots = "".join(f'<i class="vd v{v}" title="{names[k]}: {"positiv" if v > 0 else "negativ" if v < 0 else "neutral"}"></i>' for k, v in r["votes"].items())
    neg = f' · {r["votesNeg"]} negativ' if r["votesNeg"] else ""
    return f'<span class="votes">{dots}<b>{r["votesPos"]}/4 positiv</b>{neg}</span>'


def buy_page(b, wiki, dep):
    de = lambda d: f"{d[8:]}.{d[5:7]}.{d[:4]}"
    pct = lambda v: "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")
    num = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    dec = lambda v: str(v).replace(".", ",")
    esc = html.escape
    rows = {r["t"]: r for r in b["rows"]}
    link = lambda t: f"assets/{t}.html" if t in wiki else f"https://finance.yahoo.com/quote/{t}"
    sc = lambda i: f"c{i + 1}"
    stale_inputgeber = b["inputgeberAge"] > b["maxAge"]

    before = "".join(f'<span class="chip-s">{esc(k)} <small>{dec(v)} %</small></span>'
                     for k, v in sorted(dep["bucketWeights"].items(), key=lambda x: -x[1]))
    scen = b.get("scenarios") or [{"id": "A", "title": "Empfehlung", "allocKey": "alloc", "excludedKey": "excluded", "picks": b["picks"], "text": ""}]

    def cards_for(tickers, key):
      cards = ""
      for i, t in enumerate(tickers):
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
        tech = f'<p class="note">Sektor heute im Depot: {dec(r["bucketWeight"])} % · Familie {esc(r["family"])}: {dec(r["familyWeight"])} %</p>'
        inputgeber_age = f'{de(b["inputgeberDate"])} · {b["inputgeberAge"]} Tage' + (" – veraltet" if stale_inputgeber else "")
        s_ = r["score"]
        cards += f"""<article class="buy-card {sc(i % 5)}">
  <header>
    <div><span class="rank">{i + 1}</span><a class="tk" href="{link(t)}">{t}</a> <span class="nm">{esc(r['name'])}</span></div>
    <div class="buy-meta"><span class="badge-s">{esc(r['bucket'])}</span><span class="badge-s">{esc(r.get('slot', ''))}</span><b>{r.get(key, 0)} %</b></div>
  </header>
  <div class="trend">{num(r['price'])} {r['currency']} · <span class="{'pos' if (r['vsMa200'] or 0) > 0 else 'neg'}">{pct(r['vsMa200'])} vs. 200T</span> · <span data-spark="{json.dumps(r['spark'])}"></span></div>
  <div class="vs">
    <section class="op inputgeber">
      <h4>1 · Inputgeber</h4>
      <div class="op-head"><b>{esc(r['signalLabel'])}</b><span class="age {'stale' if stale_inputgeber else 'ok'}">{inputgeber_age}</span></div>
      <p>{esc(r['inputgeber'])}</p>
    </section>
    <section class="op second">
      <h4>2 · Analysten &amp; Web</h4>
      {second}
    </section>
    <section class="op">
      <h4>3 · Fundamental (Buffett-Kennzahlen)</h4>
      <div class="op-head"><b class="v{r['fund']['score']}">{esc(r['fund']['label'])}</b><span class="age ok">{de(r['fund']['date'])} · aktuell</span></div>
      <ul class="kz">{"".join(f"<li>{esc(x)}</li>" for x in r['fund']['details'])}</ul>
    </section>
    <section class="op">
      <h4>4 · Momentum (relative Stärke vs. S&amp;P 500)</h4>
      <div class="op-head"><b class="v{r['mom']['score']}">{esc(r['mom']['label'])}</b><span class="age ok">{de(r['mom']['date'])} · Schlusskurs</span></div>
      <ul class="kz">{"".join(f"<li>{esc(x)}</li>" for x in r['mom']['details'])}</ul>
    </section>
  </div>
  <footer>{votes_html(r)}<span class="agree {agree_cls}">Inputgeber vs. Analysten: {esc(r['agree'])}</span> <span class="muted">Wertung {dec(s_['total'])} = Inputgeber {dec(s_['inputgeber'])} · Analysten {dec(s_['analyst'])} · Web {dec(s_['web'])} · Trend {dec(s_['trend'])} · Fundamental {dec(round(s_['fundamental'], 2))} · Momentum {dec(round(s_['momentum'], 2))}</span>{tech}</footer>
</article>"""
      return cards

    blocks, tabs = "", ""
    for k, sv in enumerate(scen):
        key = sv["allocKey"]
        bar = "".join(f'<span class="{sc(i % 5)}" style="flex:{max(rows[t].get(key, 0), 0.5)}" title="{t} {rows[t].get(key, 0)} %"></span>'
                      for i, t in enumerate(sv["picks"]))
        leg = "".join(f'<span class="{sc(i % 5)}"><i></i><b>{t}</b> {rows[t].get(key, 0)} % · {esc(rows[t]["bucket"])}</span>'
                      for i, t in enumerate(sv["picks"]))
        after = "".join(f'<span class="chip-s new">{esc(rows[t]["bucket"])} <small>{t}</small></span>' for t in sv["picks"])
        tabs += f'<button type="button" class="chip{" active" if k == 0 else ""}" data-scen="{sv["id"]}">{esc(sv["title"])}</button>'
        blocks += f"""<div class="scen" data-scen="{sv['id']}"{'' if k == 0 else ' hidden'}>
<section class="card">
  <h2>{esc(sv['title'])}</h2>
  <p class="cap">{esc(sv['text'])}</p>
  <div class="cover"><div><small>Sektoren heute im Depot (Gewicht)</small><div>{before}</div></div><div><small>Neu durch dieses Szenario</small><div>{after}</div></div></div>
  <h3 class="mini">Aufteilung neuen Kapitals</h3>
  <div class="wbar">{bar}</div><div class="wlegend">{leg}</div>
</section>
<section class="buy-list">{cards_for(sv['picks'], key)}</section>
</div>"""

    excl = "".join(
        f'<tr><td><a class="tk" href="{link(r["t"])}">{r["t"]}</a><div class="sub">{esc(r["name"])}</div></td><td>{esc(r["bucket"])}</td>'
        f'<td>{esc(r["signalLabel"])}</td><td>{esc(r["score"]["analystLabel"])}</td><td class="v{r["fund"]["score"]}">{esc(r["fund"]["label"])}</td>'
        f'<td class="v{r["mom"]["score"]}">{esc(r["mom"]["label"])}</td><td class="num">{dec(r["score"]["total"])}<div class="sub">{r["votesPos"]}/4 positiv</div></td>'
        f'<td>{esc(r["excluded"] or "empfohlen")}</td><td>{esc(r.get("excludedB") or "empfohlen")}</td></tr>'
        for r in b["rows"] if r["excluded"] or r.get("excludedB"))
    market = "".join(f'<li><span class="age ok">{de(w["date"])}</span> {esc(w["text"])} '
                     f'<a href="{w["url"]}" target="_blank" rel="noopener">{esc(w["source"])}</a></li>' for w in b["market"])
    stale_web = "".join(f'<li><span class="age stale">{de(w["date"])}</span> {esc(w["source"])} – ignoriert (älter als {b["maxAge"]} Tage)</li>'
                        for w in b["staleWeb"])
    warn = ""
    if stale_inputgeber:
        warn = (f'<div class="banner warn">⚠️ <b>Inputgeber-Signale veraltet:</b> letzter Report vom {de(b["inputgeberDate"])} ({b["inputgeberAge"]} Tage). '
                'Sie zählen nur halb. Neue PDFs nach <code>pdf/</code> legen und <code>python website/serve.py</code> ausführen.</div>')

    bbi = dep.get("barbell", {}).get("ist", {})
    compare = compare_html(dep, wiki)
    return f"""
<div id="freshness" class="banner" hidden></div>
<section class="hero">
  <h1>Kaufempfehlung {esc(dep['label'])} vom {de(b['generated'])}</h1>
  <p class="tabs"><a href="depot-{dep['id']}.html">Depot {esc(dep['label'])}</a><b>Kaufempfehlung {de(b['generated'])}</b></p>
  <p>Erstellt am <b>{de(b['generated'])}</b>, gültig bis <b>{de(b['validUntil'])}</b> (max. {b['maxAge']} Tage). Vier Meinungen je Titel: Inputgeber, Analysten (Yahoo + datierte Webquellen), Fundamentaldaten nach Buffett-Kennzahlen und Momentum/relative Stärke – gefiltert auf Diversifikation zum Depot {esc(dep['label'])}. Keine Anlageberatung.</p>
</section>
{warn}
{compare}
<section class="card">
  <h2>Zwei Szenarien im Detail</h2>
  <p class="cap">Gleiche Kandidaten und Meinungen, unterschiedliche Aufteilung. A folgt der verbindlichen Barbell-Strategie, B verzichtet ganz auf den Barbell-Anker.</p>
  <div class="chips" role="group" aria-label="Szenario">{tabs}</div>
  <p class="cap" style="margin-top:12px">Barbell-Regeln (Szenario A): Neues Kapital zuerst in fehlende Anker-Bausteine (Geldmarkt, kurzlaufende AAA-Staatsanleihen, physisches Gold, höchstens ein Welt-ETF). Satelliten nur, solange der Satellit unter 15 % liegt – dann max. 2 Titel, ein Titel je Sektor/Familie, keine Sektoren ≥ 10 % bzw. Familien ≥ 25 %. Kandidaten der „ignorierten Mitte“ werden ausgeschlossen. Barbell heute: Anker {dec(round(bbi.get("Anker", 0)))} % · Satellit {dec(round(bbi.get("Satellit", 0)))} % · Mitte {dec(round(bbi.get("Mitte", 0)))} %.</p>
</section>
{blocks}
<section class="card">
  <h2>Nicht empfohlen</h2>
  <p class="cap">Alle geprüften Kandidaten aus Inputgebers Depots und Watchlists mit dem Grund für den Ausschluss.</p>
  <div class="table-wrap"><table><thead><tr><th>Titel</th><th>Sektor</th><th>Inputgeber</th><th>Analysten</th><th>Fundamental</th><th>Momentum</th><th class="num">Wertung</th><th>Grund Szenario A</th><th>Grund Szenario B</th></tr></thead><tbody>{excl}</tbody></table></div>
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
  document.querySelectorAll('button[data-scen]').forEach(btn => btn.addEventListener('click', () => {{
    document.querySelectorAll('button[data-scen]').forEach(x => x.classList.toggle('active', x === btn));
    document.querySelectorAll('div.scen').forEach(d => d.hidden = d.dataset.scen !== btn.dataset.scen);
  }}));
}})();
</script>"""


def compare_html(d, wiki):
    """Szenario A (mit Barbell) und B (ohne Barbell) eines Depots nebeneinander – Kopf des Untertabs Kaufempfehlung."""
    dec = lambda v: str(v).replace(".", ",")
    esc = html.escape
    link = lambda t: f"assets/{t}.html" if t in wiki else f"https://finance.yahoo.com/quote/{t}"
    rows = {r["t"]: r for r in d["buy"]["rows"]}
    short = {"A": "Neues Kapital zuerst in fehlende Anker-Bausteine (Geldmarkt, kurzlaufende AAA-Staatsanleihen, physisches Gold, ein Welt-ETF). "
                  "Satelliten nur, solange der Satellit unter 15 % liegt. Mitte ausgeschlossen.",
             "B": "Ohne Krisenpuffer: kein Geldmarkt, keine kurzen Anleihen, kein physisches Gold, kein Welt-ETF. Bis zu 3 Einzelaktien und "
                  "2 Kern-Bausteine (Gewicht 2:1), Mitte erlaubt – höheres Risiko."}

    def col(sv):
        key = sv["allocKey"]
        bar = "".join(f'<span class="c{i % 5 + 1}" style="flex:{max(rows[t].get(key, 0), 0.5)}" title="{t} {rows[t].get(key, 0)} %"></span>'
                      for i, t in enumerate(sv["picks"]))
        trs = "".join(
            f'<tr><td><a class="tk" href="{link(t)}">{t}</a><div class="sub">{esc(rows[t]["name"])}</div></td>'
            f'<td>{esc(rows[t]["bucket"])}<div class="sub"><span class="role role-{rows[t]["role"].lower()}">{esc(rows[t]["role"])}</span></div></td>'
            f'<td>{esc(rows[t]["signalLabel"])}</td><td>{votes_html(rows[t])}</td><td class="num"><b>{rows[t].get(key, 0)} %</b></td></tr>'
            for t in sv["picks"])
        return (f'<section class="op"><h4>{esc(sv["title"])}</h4><p class="cap">{esc(short[sv["id"]])}</p>'
                f'<div class="wbar">{bar}</div>'
                f'<div class="table-wrap"><table><thead><tr><th>Titel</th><th>Sektor · Rolle</th><th>Inputgeber</th><th>Meinungen</th><th class="num">Anteil</th></tr></thead>'
                f'<tbody>{trs or "<tr><td colspan=5 class=empty>Keine Empfehlung</td></tr>"}</tbody></table></div></section>')

    bb, acts = d["barbell"]["ist"], d.get("actions", {})
    first = " · ".join(f'{k}: {", ".join(acts[k])}' for k in ("Verkaufen", "Trimmen") if acts.get(k)) or "keine Verkäufe oder Trimmungen"
    summary = "".join(f"<li>{esc(x)}</li>" for x in d["buy"].get("summary", []))
    inputgeber = (f'<section class="card"><h2>Inputgeber – das Wichtigste aus den Reports</h2>'
              f'<p class="cap">Stand {esc(d["buy"].get("inputgeberStand", ""))}. Zusammenfassung der Einschätzung des Inputgebers – seine Meinung, keine geprüften Fakten.</p>'
              f'<ul class="ana">{summary}</ul></section>') if summary else ""
    return inputgeber + f"""<section class="card">
  <h2>Mit und ohne Barbell</h2>
  <p class="cap">Auf Basis des aktuellen Portfolios ({len(d['holdings'])} Positionen). Barbell heute: Anker {dec(round(bb.get('Anker', 0)))} % · Satellit {dec(round(bb.get('Satellit', 0)))} % · Mitte {dec(round(bb.get('Mitte', 0)))} % (Ziel 85 / 15 / 0).
  Inputgeber-Grundsatz: erst verkaufen und trimmen, dann gestaffelt kaufen – {esc(first)}.</p>
  <div class="vs">{"".join(col(sv) for sv in d["buy"]["scenarios"])}</div>
  <p class="note">Details zu jedem Titel (vier Meinungen, Wertung) und die Ausschlussgründe stehen weiter unten.</p>
</section>"""


def md_inline(x):
    return inline(x)


def dots(h):
    names = {"inputgeber": "Inputgeber", "analysten": "Analysten", "fundamental": "Fundamental", "momentum": "Momentum"}
    v = h.get("votes") or {}
    if not v:
        return "–"
    return ('<span class="votes">' + "".join(
        f'<i class="vd v{x}" title="{names[k]}: {"positiv" if x > 0 else "negativ" if x < 0 else "neutral"}"></i>' for k, x in v.items())
        + f'<b>{h.get("votesPos", 0)}/4</b></span>')


def depot_page(d, wiki):
    esc = html.escape
    pct = lambda v: "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")
    num = lambda v: "–" if v is None else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    dec = lambda v: str(v).replace(".", ",")
    link = lambda t, sym: f"assets/{t}.html" if t in wiki else f"https://finance.yahoo.com/quote/{sym or t}"
    hs = d["holdings"]
    has_buy = any(h.get("perf") is not None for h in hs)
    order = {"Verkaufen": 0, "Trimmen": 1, "Nachkaufen": 2, "Halten": 3}
    acts = d.get("actions", {})
    picks = d["buy"]["picks"]
    plan_cols = [("Verkaufen", "verkaufen", acts.get("Verkaufen", [])), ("Trimmen", "reduzieren", acts.get("Trimmen", [])),
                 ("Nachkaufen", "kaufen", acts.get("Nachkaufen", [])), ("Neu kaufen", "kaufen", picks),
                 ("Szenario B", "kaufen", (d["buy"].get("scenarios") or [{}, {"picks": []}])[1]["picks"]),
                 ("Halten", "halten", acts.get("Halten", []))]
    plan = "".join(
        f'<div class="pcol pc-{c}"><h3>{k} <small>{len(v)}</small></h3>'
        + ("".join(f'<span class="ptk">{esc(x)}</span>' for x in v) if v else '<span class="muted">–</span>')
        + (f'<a class="pmore" href="kaufempfehlung-{d["id"]}.html">Begründung →</a>' if k in ("Neu kaufen", "Szenario B") and v else "")
        + ('<div class="sub">ohne Barbell-Anker</div>' if k == "Szenario B" else "")
        + "</div>" for k, c, v in plan_cols)
    analysis = "".join(f"<li>{md_inline(x)}</li>" for x in d.get("analysis", []))
    bb = d.get("barbell") or {"ist": {}, "ziel": {}, "status": []}
    roles = [("Anker", "rb-anker"), ("Satellit", "rb-sat"), ("Mitte", "rb-mitte")]
    def bbar(vals):
        return "".join(f'<span class="{c}" style="flex:{max(vals.get(r, 0), 0.0001)}" title="{r} {dec(round(vals.get(r, 0), 1))} %"></span>' for r, c in roles)
    bb_html = (f'<div class="bbrow"><span class="bbl">Ist</span><div class="wbar">{bbar(bb["ist"])}</div></div>'
               f'<div class="bbrow"><span class="bbl">Ziel</span><div class="wbar">{bbar(bb["ziel"])}</div></div>'
               '<div class="wlegend">' + "".join(f'<span class="{c}"><i></i>{r} {dec(round(bb["ist"].get(r, 0)))} % '
                                                  f'<small>(Ziel {dec(round(bb["ziel"].get(r, 0)))} %)</small></span>' for r, c in roles) + '</div>'
               '<ul class="ana">' + "".join(f"<li>{esc(x)}</li>" for x in bb["status"]) + '</ul>')

    bars = ""
    mx = max(d["bucketWeights"].values() or [1])
    for k, v in sorted(d["bucketWeights"].items(), key=lambda x: -x[1]):
        over = v >= 10
        bars += (f'<div class="sbar{" over" if over else ""}"><span class="sl">{esc(k)}</span>'
                 f'<span class="st"><i style="width:{v / mx * 100:.1f}%"></i></span><span class="sv">{dec(v)} %{" · voll" if over else ""}</span></div>')

    rows = ""
    for h in sorted(hs, key=lambda h: (not h["resolved"], order.get(h.get("entscheidung"), 9), h["bucket"], h["t"])):
        if not h["resolved"]:
            rows += (f'<tr class="unres"><td><b>{esc(h["t"])}</b><div class="sub">{esc(h["raw"])}</div></td><td>–</td><td class="num">–</td>'
                     + (f'<td class="num">–</td>' if has_buy else "") +
                     f'<td class="num">–</td><td>–</td><td>–</td><td><span class="reco reco-halten">Daten nachtragen</span><div class="sub">{esc(h.get("hint", ""))}</div></td></tr>')
            continue
        v = h.get("vsMa200")
        perf_td = ""
        if has_buy:
            warn = f'<div class="sub neg">⚠️ unplausibel – bitte prüfen</div>' if h.get("buyWarn") else ""
            perf_td = (f'<td class="num {"pos" if (h.get("perf") or 0) > 0 else "neg"}" title="{esc(h.get("buyWarn", ""))}">{pct(h.get("perf"))}'
                       f'<div class="sub">Kauf {num(h.get("buy"))} €</div>{warn}</td>')
        price = f'{num(h.get("price"))} <small>{h.get("currency", "")}</small>' if h.get("price") is not None else "–"
        if h.get("currency") not in (None, "EUR") and h.get("priceEUR") is not None:
            price += f'<div class="sub">{num(h["priceEUR"])} €</div>'
        bk = h["inputgeber"]
        btxt = {"held": "Im Inputgeber-Depot", "sold": "Von Inputgeber verkauft", "watch": "Inputgeber-Watchlist", "none": "–"}[bk["kind"]]
        rows += (f'<tr><td><a class="tk" href="{link(h["t"], h.get("symbol"))}">{esc(h["t"])}</a><div class="sub">{esc(h["name"])}</div></td>'
                 f'<td>{esc(h["bucket"])}<div class="sub"><span class="role role-{(h.get("role") or "").lower()}">{esc(h.get("role") or "–")}</span> · {esc(h.get("style") or "")}</div></td>'
                 f'<td class="num">{price}</td>{perf_td}'
                 f'<td class="num {"pos" if (v or 0) > 0 else "neg"}"><span data-spark="{json.dumps(h.get("spark") or [])}"></span>{pct(v)}</td>'
                 f'<td><span class="bk bk-{bk["kind"]}" title="{esc(bk["text"])}">{btxt}</span></td>'
                 f'<td>{dots(h)}</td>'
                 f'<td><span class="reco reco-{h["ecls"]}">{esc(h["entscheidung"])}</span>'
                 + (f' <span class="prio prio-{h["prio"]}">Priorität {esc(h["prio"])}</span>' if h.get("prio") else "")
                 + f'<div class="sub why">{esc(h["egrund"])}</div>'
                 f'<details class="det"><summary>Alle Gründe</summary><ul>{"".join(f"<li>{esc(x)}</li>" for x in h.get("gruende", []))}</ul></details></td></tr>')

    ma_rows = [{"label": h["t"], "sub": h["name"], "value": h["vsMa200"], "href": link(h["t"], h.get("symbol"))}
               for h in hs if h.get("vsMa200") is not None]
    ma_rows.sort(key=lambda r: -r["value"])
    perf_rows = [{"label": h["t"], "sub": h["name"], "value": h["perf"], "href": link(h["t"], h.get("symbol"))}
                 for h in hs if h.get("perf") is not None]
    perf_rows.sort(key=lambda r: -r["value"])
    unres = ""
    warns = [h for h in hs if h.get("buyWarn")]
    if warns:
        unres += ('<div class="banner warn">⚠️ <b>Kaufkurs unplausibel:</b> '
                  + "; ".join(f'{esc(h["t"])} ({esc(h["name"])}): {esc(h["buyWarn"])}' for h in warns)
                  + '. Diese Positionen fließen nicht in die Performance ein – möglicherweise sind Zeilen in der Depot-Datei vertauscht.</div>')
    if d["unresolved"]:
        unres += (f'<div class="banner warn">⚠️ <b>{len(d["unresolved"])} Positionen nicht aufgelöst:</b> {esc(", ".join(d["unresolved"]))}. '
                 f'Bitte Name oder ISIN in <code>input/{esc(d["id"])}/</code> nachtragen – sie fehlen in Bewertung und Sektorgewichten.</div>')
    perf_card = ""
    if perf_rows:
        perf_card = f"""<section class="card">
  <h2>Performance seit Kauf</h2>
  <p class="cap">Kaufkurse aus der Depot-Datei (als EUR interpretiert), aktueller Kurs in EUR umgerechnet. Ø {pct(d['perf'])} über {d['perfCount']} Positionen (gleichgewichtet).</p>
  <div id="perfbars"></div>
</section>"""
    return f"""
<section class="hero">
  <h1>Depot {esc(d['label'])}</h1>
  <p class="tabs"><b>Depot {esc(d['label'])}</b><a href="kaufempfehlung-{d['id']}.html">Kaufempfehlung {d['buy']['generated'][8:]}.{d['buy']['generated'][5:7]}.{d['buy']['generated'][:4]}</a></p>
  <p>{len(hs)} Positionen aus <code>input/{esc(d['id'])}/</code> · Kurse Yahoo Finance vom {d['generated'][8:]}.{d['generated'][5:7]}.{d['generated'][:4]} · bewertet nach Inputgebers Regelwerk (Status, 200-Tage-Linie) und Analystenkonsens. Keine Anlageberatung.</p>
</section>
{unres}
<section class="card">
  <h2>Aktionsplan</h2>
  <p class="cap">Eine Entscheidung je Position aus Barbell-Rolle (Anker/Satellit/Mitte), Steuerung (prozyklisch mit Stop, antizyklisch mit Cost Average), Inputgeber-Status, vier Meinungen und 200-Tage-Linie. Reihenfolge: erst verkaufen, dann Mitte abbauen (Priorität „hoch“ zuerst), dann gestaffelt in den Anker. Keine Anlageberatung.</p>
  <div class="plan">{plan}</div>
</section>
<section class="card">
  <h2>Barbell: Ist gegen Ziel</h2>
  <p class="cap">Verbindliche Strategie: 85 % defensiver Anker (Geldmarkt, kurzlaufende AAA-Staatsanleihen, physisches Gold, höchstens ein Welt-ETF) · 15 % aggressiver Satellit · keine Mitte. Anteile nach Anzahl der Positionen (ohne Stückzahlen). Rebalancing quartalsweise.</p>
  {bb_html}
</section>
<section class="card">
  <h2>Gesamtanalyse</h2>
  <ul class="ana">{analysis}</ul>
</section>
<section class="card">
  <h2>Sektorgewichte</h2>
  <p class="cap">Ohne Stückzahlen zählt jede Position gleich. Ab 10 % gilt ein Sektor als ausreichend besetzt („voll“) und wird in der Kaufempfehlung nicht weiter aufgestockt.</p>
  <div class="sbars">{bars}</div>
</section>
{perf_card}
<section class="card">
  <h2>Abstand zur 200-Tage-Linie</h2>
  <p class="cap"><i class="sw sw-up"></i>darüber · <i class="sw sw-down"></i>darunter. Inputgebers zentrale Marke für Stopps.</p>
  <div id="ma200"></div>
</section>
<section class="table-wrap">
<table class="dep">
<thead><tr><th>Position</th><th>Sektor · Rolle</th><th class="num">Kurs</th>{'<th class="num">seit Kauf</th>' if has_buy else ''}<th class="num">vs. 200T</th><th>Inputgeber</th><th>4 Meinungen</th><th>Entscheidung</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</section>
<script>
document.querySelectorAll('[data-spark]').forEach(s => s.innerHTML = sparkline(JSON.parse(s.dataset.spark), 70, 20));
divergingBars(document.getElementById('ma200'), {json.dumps(ma_rows, ensure_ascii=False)}, {{label: 'Abstand zur 200-Tage-Linie'}});
{f"divergingBars(document.getElementById('perfbars'), {json.dumps(perf_rows, ensure_ascii=False)}, {{label: 'Performance seit Kauf'}});" if perf_rows else ''}
</script>"""


def build():
    if PUB.exists():
        shutil.rmtree(PUB)
    (PUB / "assets").mkdir(parents=True)
    (PUB / ".nojekyll").write_text("", encoding="utf-8")  # Pages: Dateien unverändert ausliefern
    shutil.copy(HERE / "style.css", PUB / "style.css")
    shutil.copy(HERE / "charts.js", PUB / "charts.js")
    prices = json.loads(PRICES.read_text(encoding="utf-8")) if PRICES.exists() else {"fetched": None, "prices": {}}
    P = prices["prices"]
    deps = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(DEPOTS.glob("*.json")) if f.stem != "index"]
    DEPOT_NAV[:] = [(d["id"], d["label"]) for d in deps]
    held_by = {}
    for d in deps:
        for h in d["holdings"]:
            held_by.setdefault(h["t"], []).append(d["id"])
            if h["t"] in ("2B70", "G2XJ", "SPYD"):
                held_by.setdefault({"2B70": "IBB", "G2XJ": "GDXJ", "SPYD": "NOBL"}[h["t"]], []).append(d["id"])

    assets = []
    for f in sorted((SRC / "assets").glob("*.md")):
        md = f.read_text(encoding="utf-8")
        meta = read_meta(md)
        inputgeber = section(md, "🗣️")
        meta["chance"] = inputgeber.get("Chance", "")
        meta["href"] = f"assets/{f.stem}.html"
        meta["mine"] = sorted(set(held_by.get(f.stem, [])))
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
    cash = {"beta": "21 %", "2030": "0 %", "alpha": "38 %"}
    roles = {"beta": "Beta-Core · Kapitalerhalt", "2030": "Langfrist-Core · Sparplan", "alpha": "Alpha-Satellit · Themenwetten"}
    cards = "".join(
        f'<button class="kpi depot-{k}" data-depot="{k}" type="button">'
        f'<span class="kpi-label">{DEPOT_LABEL[k]}</span>'
        f'<span class="kpi-value">{counts[k]}</span><span class="kpi-sub">Positionen · Cash {cash[k]}</span>'
        f'<span class="kpi-role">{roles[k]}</span></button>'
        for k in ("beta", "2030", "alpha"))
    own = ""
    for d in deps:
        perf = (f'{"+" if d["perf"] > 0 else "−"}{abs(d["perf"]):.1f} %'.replace(".", ",") + " Ø seit Kauf") if d.get("perf") is not None else "ohne Kaufkurse"
        own += (f'<a class="kpi kpi-mine" href="depot-{d["id"]}.html"><span class="kpi-label">Depot {html.escape(d["label"])}</span>'
                f'<span class="kpi-value">{len(d["holdings"])}</span><span class="kpi-sub">Positionen · {perf}</span>'
                f'<span class="kpi-role">Bewertung &amp; Kaufempfehlung →</span></a>')
    cards = own + cards
    dash = f"""
<section class="hero">
  <h1>Depot-Steckbriefe</h1>
  <p>{len(assets)} Steckbriefe aus Inputgebers drei Depots und den eigenen Depots, analysiert nach Buffett (Value) und Inputgeber (Makro &amp; Asymmetrie). Stand {html.escape(stand)}.</p>
</section>
<section class="kpis">{cards}</section>
<section class="toolbar">
  <input id="q" type="search" placeholder="Suche nach Name, Ticker, Thema …" aria-label="Suche">
  <div class="chips" role="group" aria-label="Depot-Filter">
    <button class="chip active" data-f="all" type="button">Alle</button>
    {"".join(f'<button class="chip" data-f="dep:{i}" type="button">{html.escape(l)}</button>' for i, l in DEPOT_NAV)}
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
  return DATA.filter(a=>(filter==='all'||a.depot===filter||(filter.startsWith('dep:')&&a.mine.includes(filter.slice(4)))) &&
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
      <td>${{a.name}}${{a.mine.map(m=>' <span class="badge depot-mein">'+m+'</span>').join('')}}<div class="sub">${{a.block}}</div></td>
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
    wiki = {a["ticker"] for a in assets}
    for d in deps:
        (PUB / f"depot-{d['id']}.html").write_text(page(f"Depot {d['label']}", depot_page(d, wiki)), encoding="utf-8")
        (PUB / f"kaufempfehlung-{d['id']}.html").write_text(
            page(f"Kaufempfehlung {d['label']}", buy_page(d["buy"], wiki, d)), encoding="utf-8")
    print(f"Webseite gebaut: {PUB / 'index.html'} ({len(assets)} Steckbriefe)")


if __name__ == "__main__":
    build()
