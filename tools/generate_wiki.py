# -*- coding: utf-8 -*-
"""Erzeugt portfolio/index.md und portfolio/assets/[TICKER].md aus tools/assets_data.py.

Achtung: Überschreibt bestehende Steckbriefe. Eigene Notizen daher erst nach der
Generierung direkt in den MD-Dateien pflegen (oder in assets_data.py eintragen).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assets_data import ASSETS, DEPOTS, ETF_BUFFETT, MAKRO, SOLD, STAND, WATCH  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "portfolio"
ASSET_DIR = OUT / "assets"

DEPOT_ORDER = ["mein", "beta", "2030", "alpha"]


def alloc_str(a):
    return f"{a['alloc']} %" if a.get("alloc") is not None else f"n/a (zuletzt {last_known(a)})"


def last_known(a):
    for v in reversed(a["hist"]):
        if v not in ("–", "neu"):
            return v
    return "–"


def asset_md(a):
    d = DEPOTS[a["depot"]]
    is_fund = a["typ"] in ("ETF", "ETC")
    moat_rating, moat_text = a.get("moat", ETF_BUFFETT["moat"])
    mgmt = a.get("mgmt", ETF_BUFFETT["mgmt"])
    meta = {
        "ticker": a["t"], "name": a["name"], "depot": a["depot"], "block": a["block"],
        "alloc": a.get("alloc"), "last": last_known(a), "typ": a["typ"],
        "pl": a.get("pl", ""), "moat": moat_rating, "status": a.get("status", ""),
    }
    perf = a.get("pl") or "n/a (PDF ohne Einstandskurs)"
    kauf = f"{a['entry']} → {a['now']}" if a.get("entry") else "n/a"

    lines = [
        f"<!-- meta: {json.dumps(meta, ensure_ascii=False)} -->",
        f"# {a['name']} ({a['t']})",
        "",
        f"> **{d['name']}** · {a['block']} · {a['typ']}"
        + (f" · Status: `{a['status']}`" if a.get("status") else ""),
        "",
        "## 📊 Depot-Kennzahlen",
        f"- **Depot-Anteil:** {alloc_str(a)} im {d['name']} (Klassifizierung: {d['klasse']})",
        "- **Positionswert:** n/a (Anzahl: n/a × Kurs: n/a) – die PDFs enthalten nur Gewichtungen",
        f"- **Einstieg → Kurs (laut PDF) / Performance:** {kauf} / {perf}",
        f"- **WKN / ISIN:** {a['wkn']} / {a['isin']}",
        "",
        "**Gewichtungsverlauf**",
        "",
        "| KW 38 | KW 39 | KW 40 | KW 41 |",
        "|---|---|---|---|",
        "| " + " | ".join(a["hist"]) + " |",
        "",
        "## 🗣️ Einschätzung Balthasar Becker (Quelle: PDF)",
        f"- **Chance:** {a['chance']}",
        f"- **Risiko:** {a['risiko']}",
        f"- **Wochenstatus:** {a['woche']}",
        "",
        "## 🏛️ Das Warren Buffett Fundament (Value Check)",
        f"- **Burggraben (Economic Moat):** {moat_text} (Bewertung: **{moat_rating}**)",
        f"- **Circle of Competence:** {a['circle']}",
        f"- **Management & Verschuldung:** {mgmt}",
        "",
        "## 🌊 Der Balthasar Becker Zyklus-Check (Makro & Asymmetrie)",
        f"- **Korrelation mit Globaler Liquidität:** {a['liq']}",
        f"- **Asymmetrisches Risikoprofil:** {a['asym']}",
        f"- **Antizyklischer Status:** {a['anti']}",
        "",
        "## 📌 Eigene Notizen & Kauf-/Verkaufslimits",
        f"- *Mein Fairer Wert (Intrinsic Value):* {a['fair']}",
        f"- *Nachkaufmarke bei Liquiditäts-Dip:* {a['dip']}",
        "",
        "---",
        f"[⬅️ Dashboard](../index.md) | *Keine Anlageberatung. Stand: {STAND}*",
        "",
    ]
    if is_fund:
        lines.insert(lines.index("## 🏛️ Das Warren Buffett Fundament (Value Check)") + 1,
                     "> Fonds/ETC: Der Buffett-Check bewertet hier den Korb bzw. das Underlying, nicht ein Einzelunternehmen.\n")
    return "\n".join(lines)


def index_md():
    out = [
        "# 📈 Portfolio-Wiki – Balthasar Becker Depots",
        "",
        f"**Stichtag:** {STAND} · **Quellen:** 14 PDFs in `PDF_input/` und `PDF_input/09102026/` (Depot-Reports KW38-41, Weekly Recaps KW38-41)",
        "",
        "**Gesamtwert:** n/a – die Reports weisen ausschließlich prozentuale Gewichtungen je Depot aus, keine Stückzahlen oder Euro-Beträge.",
        "",
        "> 👤 **Mein Depot:** Handlungsempfehlung für die eigenen Positionen → [mein_depot.md](mein_depot.md)",
        "> 🛒 **Kaufempfehlung:** Becker vs. Zweitmeinung, diversifiziert → [kaufempfehlung.md](kaufempfehlung.md)",
        "",
        "## 🏋️ Core-Satellite-Architektur (Becker Barbell)",
        "",
        "| Depot | Rolle | Cash | Struktur |",
        "|---|---|---|---|",
    ]
    for k in DEPOT_ORDER[1:]:
        d = DEPOTS[k]
        out.append(f"| **{d['name']}** | {d['klasse']} | {d['cash']} | {d['bloecke']} |")
    out += [
        "",
        "- *Beta-Portfolio (Großteil, Ziel ~90 %):* Beta-Depot – Qualitätsaktien ohne KI-Klumpen, Gold, Bitcoin, Anleihen, Geldmarkt.",
        "- *Langfrist-Core:* 2030-Depot – Plattform-Compounder, Aufsteiger und antizyklische Qualität per Sparplan.",
        "- *Alpha-Portfolio (kleiner Teil, ~10 %):* Alpha-Depot – Themenwetten, Krypto-Hebel und Optionen. 50 % Drawdown einkalkuliert.",
        "",
        "> Gewinne aus Alpha und 2030 werden regelmäßig ins Beta-Depot umgeschichtet.",
        "",
        "## 📋 Zentrale Asset-Tabelle",
    ]
    for k in DEPOT_ORDER:
        d = DEPOTS[k]
        out += ["", f"### {d['name']} ({d['klasse']})", "",
                "| Name | Ticker | Block / Thema | Anteil | Performance | Moat | Steckbrief |",
                "|---|---|---|---|---|---|---|"]
        rows = [a for a in ASSETS if a["depot"] == k]
        rows.sort(key=lambda a: -(a["alloc"] if a.get("alloc") is not None else -1))
        for a in rows:
            moat = a.get("moat", ETF_BUFFETT["moat"])[0]
            out.append(f"| {a['name']} | {a['t']} | {a['block']} | {alloc_str(a)} | {a.get('pl') or '–'} | {moat} | [{a['t']}](assets/{a['t']}.md) |")
    out += [
        "",
        "> Alle Anteile und Alpha-Performance (Einstieg → Kurs) laut Depot-Reports KW41 vom 09.10.2026. Neu im 2030-Depot: Status je Position (Halten / Aufbauen / Reduzieren).",
        "",
        "## 🌐 Makro- & Sentiment-Check",
        "",
        f"**Regime:** {MAKRO['regime']}",
        "",
    ]
    out += [f"- {p}" for p in MAKRO["punkte"]]
    out += [
        "",
        "**Steigende Zentralbank-Liquidität (Zinssenkungen, steile Kurve):** Stärkster Hebel im Alpha-Depot (Metaplanet, SharpLink, GDXJ, Robotics-Small-Caps, China) und im 2030-Depot (SoFi, Robinhood, Alibaba). Im Beta profitieren IBIT, TLT, RSP und NOBL. Die Barbell ist hier klar offensiv.",
        "",
        "**Fallende Liquidität / Zinsschock:** Alpha und 2030 tragen das Risiko (KI-Block im Alpha ~51 %: MU/CRDO/MRVL/GLW/LITE/KEYS/BE; SoFi). Puffer: Beta-Liquidität 20 %, Berkshire (Netto-Cash), Gold und McDonald's als defensive Cashflow-Titel. Becker würde einen Panik-Rücksetzer mit der Beta-Reserve kaufen.",
        "",
        "**Klumpenrisiken:** McDonald's 31 % im 2030-Depot (Cash 0 %) · Micron 17 % im Alpha · KI-Block ~51 % des Alpha-Depots · Krypto-Hebel hängen an der Bitcoin-200-Tage-Linie (~70-71 Tsd. USD).",
        "",
        "## 🔭 Watchlist",
        "",
    ]
    out += [f"- **{d}:** {t}" for d, t in WATCH]
    out += [
        "",
        "## 🗃️ Verkaufte Positionen (KW38-41)",
        "",
        "| Ticker | Name | Depot | Woche | Grund |",
        "|---|---|---|---|---|",
    ]
    out += [f"| {t} | {n} | {d} | {w} | {g} |" for t, n, d, w, g in SOLD]
    out += ["", "---", f"*Keine Anlageberatung. Alle Einschätzungen in den Abschnitten 'Einschätzung Balthasar Becker' geben dessen Meinung aus den PDFs wieder; Buffett-/Becker-Checks sind eigene Einordnungen. Stand: {STAND}*", ""]
    return "\n".join(out)


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for a in ASSETS:
        (ASSET_DIR / f"{a['t']}.md").write_text(asset_md(a), encoding="utf-8")
    (OUT / "index.md").write_text(index_md(), encoding="utf-8")
    print(f"{len(ASSETS)} Steckbriefe + index.md -> {OUT}")


if __name__ == "__main__":
    main()
