# -*- coding: utf-8 -*-
"""Gesamturteil je Depotposition: Nachkaufen · Halten · Trimmen · Verkaufen.

Rahmen (SKILL.md Abschnitt 0 und 0b):
  - Barbell: 85 % Anker / 15 % Satellit / 0 % Mitte. Die Mitte wird abgebaut.
  - Inputgeber-Makro: prozyklische Positionen über den Stop steuern, antizyklische über
    Cost Average und Positionsgröße (kein harter Stop). 8 % Geldentwertung als Hürde.
Darin verknüpft: Inputgebers Status, vier Meinungen (Inputgeber, Analysten, Fundamental, Momentum),
200-Tage-Linie, Sektor-/Familiengewichte.
"""
FAMILY_MAX = 25.0      # % – ab hier kein Nachkauf in derselben Familie
FAMILY_TRIM = 40.0     # % – ab hier Gewinner der Familie trimmen (Klumpenrisiko)
BUCKET_FULL = 10.0     # % – Sektor gilt als voll, kein Nachkauf (wie in der Kaufempfehlung)

# Barbell-Ziele (Anteil an den Positionen, ohne Stückzahlen gleichgewichtet)
TARGET = {"Anker": 85.0, "Satellit": 15.0, "Mitte": 0.0}
SAT_HARD_STOP = 10.0   # % – darunter: nicht blind nachkaufen, Thesen prüfen
SAT_TAKE_PROFIT = 25.0  # % – darüber: Gewinne in den Anker umschichten

# Makro-Stand laut Inputgeber (Weekly Recap KW42 / Makro-Crashkurs Session 02)
MAKRO = {
    "date": "2026-10-16",
    "debasement": 8.0,          # % Geldentwertung p. a. (Crashkurs; KW41: 8–10 %)
    "debtLiqRatio": 1.8,        # Verhältnis Schulden- zu Liquiditätswachstum, kritisch ab 2,2 (letzter genannter Wert: KW41)
    "debtLiqCritical": 2.2,
    "liqGrowth": "erstmals leicht gefallen, aber noch ausreichend (KW42)",
    "sentiment": "Fear & Greed 25, 42 % Bären unter Kleinanlegern, kein Panik-VIX – historisch ein Kontraindikator",
    "rates": "Höhepunkt laut Inputgeber gesehen – 2- und 10-jährige fallen, Dollar schwächer; kritisch ab ~6 % Zehnjahresrendite",
    "scenario": "Rotation aus KI in defensive Werte, Jahresendrallye bleibt möglich",
}

# --------------------------------------------------------------------------- Rollen
ANCHOR_BUCKETS = {"Geldmarkt", "Kurzlaufende Staatsanleihen (AAA)", "Gold physisch"}
SAT_BUCKETS = {"Quantencomputing", "Robotik & Automatisierung", "Krypto & Rechenzentren", "Krypto", "Kernenergie & Uran"}
ROLE_OVERRIDE = {
    # Anker
    "XEON": "Anker", "EXVM": "Anker", "4GLD": "Anker", "EWG2": "Anker", "GLD": "Anker", "VWCE": "Anker",
    # Mitte: Sektor-/Themen-/Faktor-ETFs, Dividenden, Langläufer, Goldminen, Rohstoff-ETCs, weitere Welt-ETFs
    "TLT": "Mitte", "TIP": "Mitte", "NOBL": "Mitte", "SPYD": "Mitte", "RSP": "Mitte", "IS3S": "Mitte", "XDEM": "Mitte",
    "QDVE": "Mitte", "LYPG": "Mitte", "XDWT": "Mitte", "XNAS": "Mitte", "QDVG": "Mitte", "2B70": "Mitte", "IBB": "Mitte",
    "HLT": "Mitte", "IQQQ": "Mitte", "CHIP": "Mitte", "G2XJ": "Mitte", "GDXJ": "Mitte", "GSG": "Mitte", "0D7Z": "Mitte",
    "SLV": "Mitte", "GDX": "Mitte",
    # Satellit
    "IBIT": "Satellit",
}
LABEL_ROLE = {"Anker": "Anker (defensiv)", "Satellit": "Satellit (aggressiv)", "Mitte": "Mitte (abbauen)"}


def role_of(t, kind, bucket, inputgeber_depot=None, fund=None):
    """Barbell-Rolle. Aktien: Satellit bei Inputgeber-Alpha, Wachstumsbranche, Beta ≥ 1,6 oder Börsenwert < 50 Mrd. bei Beta ≥ 1,0 – sonst Mitte."""
    if t in ROLE_OVERRIDE:
        return ROLE_OVERRIDE[t]
    if bucket in ANCHOR_BUCKETS:
        return "Anker"
    if kind == "ETF":
        return "Satellit" if bucket in SAT_BUCKETS else "Mitte"
    if inputgeber_depot == "Alpha" or bucket in SAT_BUCKETS:
        return "Satellit"
    f = fund or {}
    mcap, beta = f.get("mcap"), f.get("beta")
    if beta and beta >= 1.6:
        return "Satellit"
    # kleinerer Börsenwert nur dann aggressiv, wenn die Aktie auch schwankungsfreudig ist (sonst z. B. defensive Versicherer)
    if mcap and mcap < 50e9 and (beta is None or beta >= 1.0):
        return "Satellit"
    return "Mitte"


def style_of(h, role):
    """antizyklisch (Cost Average statt Stop) oder prozyklisch (Stop an der 200-Tage-Linie)."""
    b = h.get("inputgeber", {})
    if role == "Anker":
        return "antizyklisch"
    if b.get("kind") == "held" and (b.get("depot") == "Beta" or str(b.get("block", "")).startswith("C")):
        return "antizyklisch"
    return "prozyklisch"


def barbell(holdings):
    res = [h for h in holdings if h.get("resolved") and h.get("role")]
    n = len(res) or 1
    ist = {r: round(sum(h["role"] == r for h in res) / n * 100, 1) for r in TARGET}
    status = []
    if ist["Satellit"] > SAT_TAKE_PROFIT:
        status.append(f"Take-Profit: Satellit {ist['Satellit']:.0f} % > {SAT_TAKE_PROFIT:.0f} % – Gewinne abschöpfen und in den Anker umschichten")
    elif ist["Satellit"] < SAT_HARD_STOP:
        status.append(f"Hard Stop: Satellit {ist['Satellit']:.0f} % < {SAT_HARD_STOP:.0f} % – nicht blind nachkaufen, Thesen prüfen")
    if ist["Mitte"] > 0:
        status.append(f"Mitte {ist['Mitte']:.0f} % – schrittweise in Erholungen abbauen")
    if ist["Anker"] < TARGET["Anker"]:
        status.append(f"Anker {ist['Anker']:.0f} % von {TARGET['Anker']:.0f} % – neues Kapital und Erlöse in den Anker")
    return {"ist": ist, "ziel": TARGET, "status": status, "n": len(res)}


# --------------------------------------------------------------------------- Entscheidung
ORDER = {"Verkaufen": 0, "Trimmen": 1, "Nachkaufen": 2, "Halten": 3, "Daten nachtragen": 4}
CLS = {"Verkaufen": "verkaufen", "Trimmen": "reduzieren", "Nachkaufen": "kaufen", "Halten": "halten", "Daten nachtragen": "halten"}


def pct(v):
    return "–" if v is None else f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} %".replace(".", ",")


def inputgeber_vote(b):
    if b["kind"] == "sold":
        return -1
    if b["kind"] == "held":
        st = b.get("status", "")
        if st == "REDUZIEREN":
            return -1
        if st == "AUFBAUEN" or (b.get("depot") == "Alpha" and st.startswith(("EINSTEIGEN", "NEU"))):
            return 1
        return 0
    if b["kind"] == "watch":
        return {"kaufen": 1, "pruefen": 1, "halten": 0, "warten": 0, "nein": -1}.get(b.get("signal"), 0)
    return 0


def analyst_vote(q):
    if not q or not q.get("mean"):
        return 0
    return 1 if q["mean"] <= 2.2 else -1 if q["mean"] >= 3 else 0


def decide(h, bw, fw, family, bb):
    """Setzt h['entscheidung'], h['egrund'], h['prio'], h['gruende'], h['votes']; nutzt h['role'], h['style'] und den Barbell-Status bb."""
    if not h.get("resolved") or "price" not in h:
        h.update(entscheidung="Daten nachtragen", ecls="halten", egrund=h.get("hint") or h.get("error", "keine Kursdaten"),
                 gruende=[], votes={}, prio="")
        return h["entscheidung"]
    t, b, v, perf = h["t"], h["inputgeber"], h.get("vsMa200"), h.get("perf")
    role, style = h["role"], h["style"]
    sat = bb["ist"]["Satellit"]
    fam = family(h["bucket"])
    famw, bucketw = fw.get(fam, 0.0), bw.get(h["bucket"], 0.0)
    votes = {"inputgeber": inputgeber_vote(b), "analysten": analyst_vote(h.get("consensus")),
             "fundamental": (h.get("fund") or {}).get("score", 0), "momentum": (h.get("mom") or {}).get("score", 0)}
    pos, neg = sum(x > 0 for x in votes.values()), sum(x < 0 for x in votes.values())
    m = votes["momentum"]
    g = [f"Barbell-Rolle: {LABEL_ROLE[role]} · Steuerung {style} ({'Stop an der 200-Tage-Linie' if style == 'prozyklisch' else 'Cost Average und Positionsgröße statt Stop'})",
         f"Inputgeber: {b['text']}",
         f"Analysten: {(h.get('consensus') or {}).get('rating') or 'kein Konsens'}"
         + (f" (Note {h['consensus']['mean']:.2f})".replace(".", ",") if (h.get('consensus') or {}).get('mean') else ""),
         f"Fundamental: {(h.get('fund') or {}).get('label', '–')}",
         f"Momentum: {(h.get('mom') or {}).get('label', '–')}",
         f"Trend: {pct(v)} zur 200-Tage-Linie" + (f" · seit Kauf {pct(perf)}" if perf is not None else ""),
         f"Gewicht im Depot: Sektor {h['bucket']} {str(bucketw).replace('.', ',')} %, Familie {fam} {str(famw).replace('.', ',')} %"]
    tax = " Steuerfolgen realisierter Gewinne beachten." if (perf or 0) > 0 or (v or 0) > 20 else ""

    def out(e, why, prio=""):
        h.update(entscheidung=e, ecls=CLS[e], egrund=why + (tax if e in ("Trimmen", "Verkaufen") else ""), prio=prio,
                 gruende=g, votes=votes, votesPos=pos, votesNeg=neg)
        return e

    weak = (v is not None and v < 0) or neg >= 2

    # ---------------- Verkaufen (These gebrochen)
    if b["kind"] == "sold":
        return out("Verkaufen", f"Inputgeber hat die Position verkauft ({b['text'].split(': ', 1)[-1]}). Ohne Inputgeber-These fehlt der Grund zum Halten.", "hoch")
    if t in ("LULU", "NKE"):
        return out("Verkaufen", "Sportartikel-Turnaround ohne Bestätigung: deutlich unter der 200-Tage-Linie. Inputgebers Nike-Calls haben sich "
                                "in KW42 zwar erholt (−44 → −22 %), er spielt die Branche aber nur über kleine Optionen, nicht über die Aktie. "
                                "Berenberg stuft Nike auf Sell. Zudem Barbell-Mitte.", "hoch")
    if style == "prozyklisch" and v is not None and v < -20 and m <= 0 and votes["inputgeber"] <= 0:
        extra = " Fundamental günstig – Wiedereinstieg erst, wenn die Aktie die 200-Tage-Linie zurückerobert." if votes["fundamental"] > 0 else ""
        return out("Verkaufen", f"Prozyklische Position mit gebrochenem Trend: {pct(v)} unter der 200-Tage-Linie, kein positives Momentum, "
                                f"keine Inputgeber-Unterstützung – der Stop greift.{extra}", "hoch")
    if neg >= 3 and b["kind"] != "held":
        return out("Verkaufen", f"{neg} von 4 Meinungen negativ, kein Inputgeber-Rückhalt.", "hoch")

    # ---------------- Antizyklisch tief im Minus: kein Stop, Cost Average / Positionsgröße
    if style == "antizyklisch" and v is not None and v < -20:
        if role == "Mitte":
            return out("Trimmen", f"Antizyklische Position ({pct(v)} unter der 200-Tage-Linie): kein Stop-Verkauf in die Schwäche – "
                                  "aber Barbell-Mitte, deshalb in der nächsten Erholung abbauen.", "mittel")
        return out("Halten", f"Antizyklisch ({pct(v)} unter der 200-Tage-Linie): Cost Average statt Stop – These prüfen, Positionsgröße begrenzen.")

    # ---------------- Trimmen
    if b.get("status") == "REDUZIEREN":
        return out("Trimmen", "Inputgeber-Status REDUZIEREN – in Erholungen hinein abbauen, nicht in die Schwäche.", "hoch")
    if neg >= 3:
        return out("Trimmen", f"{neg} von 4 Meinungen negativ, Inputgeber hält die Position aber noch – reduzieren statt komplett verkaufen.", "hoch")
    if perf is not None and perf > 100:
        return out("Trimmen", f"{pct(perf)} seit Kauf – Gewinne in den Anker umschichten (Inputgeber: Alpha-Gewinne ins Beta). "
                              "Etwa ein Drittel verkaufen, Rest mit Stop an der 200-Tage-Linie.", "hoch")
    if role == "Satellit" and sat > SAT_TAKE_PROFIT and ((v or 0) > 10 or (perf or 0) > 30):
        return out("Trimmen", f"Take-Profit-Regel: Satellit macht {sat:.0f} % des Depots aus (Grenze {SAT_TAKE_PROFIT:.0f} %). "
                              f"Diese Position liegt {pct(v)} über der 200-Tage-Linie – Gewinne in den Anker umschichten.", "hoch")
    if famw >= FAMILY_TRIM and v is not None and v > 10:
        return out("Trimmen", f"Klumpenrisiko: Familie {fam} macht {str(famw).replace('.', ',')} % des Depots aus. "
                              f"Position {pct(v)} über der 200-Tage-Linie – Gewinne teilweise in den Anker umschichten.", "hoch")
    if role == "Mitte":
        prio = "hoch" if weak else "niedrig"
        inputgeber_note = " Inputgeber baut die Aktie zwar auf – im Barbell-Modell gehört sie aber weder in den Anker noch in den Satellit." if votes["inputgeber"] > 0 else ""
        return out("Trimmen", f"Barbell: ignorierte Mitte – schrittweise in Erholungen abbauen und in den Anker umschichten "
                              f"({'zuerst' if prio == 'hoch' else 'zuletzt'} abbauen: {pos}/4 Meinungen positiv, Trend {pct(v)}).{inputgeber_note}", prio)
    if v is not None and v > 60 and votes["inputgeber"] <= 0:
        return out("Trimmen", f"Starke Übertreibung ({pct(v)} über der 200-Tage-Linie) ohne aktive Inputgeber-Unterstützung – Teilgewinne sichern.", "mittel")

    # ---------------- Nachkaufen (nur Anker oder Satellit, Ende unter Ziel)
    healthy = v is not None and -10 <= v <= 25
    if role == "Anker" and bb["ist"]["Anker"] < TARGET["Anker"]:
        return out("Nachkaufen", f"Anker-Baustein, Anker erst {bb['ist']['Anker']:.0f} % von {TARGET['Anker']:.0f} % – "
                                 "neues Kapital und Erlöse aus der Mitte hierhin (antizyklisch, gestaffelt).")
    if role == "Satellit" and votes["inputgeber"] > 0 and pos >= 3 and healthy and bucketw < BUCKET_FULL and famw < FAMILY_MAX:
        if sat < SAT_HARD_STOP:
            return out("Halten", f"Gute Satellit-Position ({pos}/4 positiv), aber Hard-Stop-Regel: Satellit unter {SAT_HARD_STOP:.0f} % – "
                                 "erst Thesen prüfen, nicht blind nachkaufen.")
        if sat < TARGET["Satellit"]:
            return out("Nachkaufen", f"{pos} von 4 Meinungen positiv, Inputgeber positiv, Trend gesund ({pct(v)}) und Satellit unter 15 %.")
        return out("Halten", f"Starke Satellit-Position ({pos}/4 positiv) – Satellit aber schon {sat:.0f} % (Ziel 15 %), kein Nachkauf.")

    # ---------------- Halten
    if v is None:
        why = "Junge Aktie ohne 200-Tage-Linie – halten mit Stop unter dem bisherigen Tief."
    elif v < 0 and style == "prozyklisch":
        why = f"Halten mit Stop: {pct(v)} unter der 200-Tage-Linie – Ausstiegsmarke festlegen."
    elif v < 0:
        why = f"Antizyklisch ({pct(v)}): Cost Average statt Stop, Positionsgröße im Blick."
    else:
        why = f"These intakt, Trend {pct(v)} – laufen lassen."
    if role == "Satellit" and sat >= TARGET["Satellit"]:
        why += f" Satellit bereits {sat:.0f} % – kein Nachkauf."
    return out("Halten", why)


# --------------------------------------------------------------------------- Gesamtanalyse
def synthesis(label, holdings, bw, fw, picks, family, bb):
    """Gesamtanalyse: Barbell × Inputgeber-Makro (Crashkurs + KW41) × Depotstruktur × Aktionen."""
    res = [h for h in holdings if h.get("resolved") and "price" in h]
    n = len(res) or 1
    below = [h for h in res if (h.get("vsMa200") or 0) < 0]
    sold = [h["t"] for h in res if h["inputgeber"]["kind"] == "sold"]
    overlap = [h for h in res if h["inputgeber"]["kind"] in ("held", "watch")]
    anti = [h["t"] for h in res if h.get("style") == "antizyklisch"]
    acts = {}
    for h in holdings:
        acts.setdefault(h.get("entscheidung", "Halten"), []).append(h["t"])
    topfam = max(fw.items(), key=lambda x: x[1]) if fw else ("–", 0)
    ist = bb["ist"]
    dec = lambda x: f"{x:.0f}"
    L = [
        f"**Barbell (Ziel 85 / 15 / 0):** Anker {dec(ist['Anker'])} % · Satellit {dec(ist['Satellit'])} % · Mitte {dec(ist['Mitte'])} %. "
        + " · ".join(bb["status"]) + ".",
        f"**Inputgeber-Makro ({MAKRO['date'][8:]}.{MAKRO['date'][5:7]}.):** Szenario {MAKRO['scenario']}. Verhältnis Schulden- zu Liquiditätswachstum "
        f"{str(MAKRO['debtLiqRatio']).replace('.', ',')} (kritisch ab {str(MAKRO['debtLiqCritical']).replace('.', ',')}), Liquidität {MAKRO['liqGrowth']}, "
        f"Zinsen {MAKRO['rates']}. Sentiment: {MAKRO['sentiment']}. Bullenmarkt-Ende laut Inputgeber, wenn 2- und 10-jährige Renditen weiter steigen oder der Dollar ausbricht.",
        f"**8-%-Hürde:** Inputgeber rechnet mit rund {dec(MAKRO['debasement'])} % Geldentwertung pro Jahr. Geldmarkt und kurzlaufende Bundesanleihen im Anker "
        "bringen nominal nur rund 2–3 % und verlieren daran gemessen real Kaufkraft – der Preis für Kapitalerhalt im Crash. "
        "Physisches Gold im Anker ist deshalb kein Beiwerk, sondern der Schutz gegen Geldentwertung.",
        f"**Struktur:** {len(res)} bewertete Positionen, größte Familie {topfam[0]} mit {str(topfam[1]).replace('.', ',')} %. "
        f"{len(below)} Positionen ({round(len(below) / n * 100)} %) unter der 200-Tage-Linie. "
        f"{len(anti)} antizyklisch gesteuert (Cost Average statt Stop), {len(res) - len(anti)} prozyklisch (Stop an der 200-Tage-Linie).",
        f"**Inputgeber-Abgleich:** {len(overlap)} Positionen in Inputgebers Depots oder auf seiner Watchlist"
        + (f"; {len(sold)} hat er verkauft ({', '.join(sold)})." if sold else "."),
    ]
    if topfam[1] >= FAMILY_TRIM:
        L.append(f"**Klumpenrisiko {topfam[0]}:** {str(topfam[1]).replace('.', ',')} % des Depots. Inputgeber spielt den KI-Boom nur im Alpha- und "
                 "2030-Depot und hält seinen stabilen Teil bewusst frei davon.")
    plan = [f"{k}: {', '.join(acts[k])}" for k in ("Verkaufen", "Trimmen", "Nachkaufen") if acts.get(k)]
    if picks:
        plan.append(f"Neu kaufen: {', '.join(picks)}")
    L.append("**Aktionsplan:** " + " · ".join(plan) + f" · Halten: {len(acts.get('Halten', []))} Positionen.")
    L.append("**Reihenfolge (Inputgeber, Barbell):** 1. Verkäufe mit gebrochener These. 2. Mitte und REDUZIEREN-Positionen in Erholungen abbauen – "
             "Priorität „hoch“ zuerst. 3. Erlöse und neues Kapital gestaffelt in den Anker. Rebalancing quartalsweise; Rücksetzer im Anker sind "
             "Kaufgelegenheiten, kein Verkaufsgrund.")
    return L, acts
