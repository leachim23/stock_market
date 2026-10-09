# Portfolio-Wiki

Depot-Steckbriefe, eigene Depotbewertung und Kaufempfehlung auf Basis der wöchentlichen Pure-Alpha-Reports (Balthasar Becker), ergänzt um Kursdaten und Analystenkonsens von Yahoo Finance. Keine Anlageberatung.

## Webseite ansehen

- **Online:** https://leachim23.github.io/stock_market/ (GitHub Pages, Ordner `docs/`)
- **Lokal:** `docs/index.html` im Browser öffnen. Die Seite ist statisch und braucht keinen Server.

## Aktualisieren

```
python website/serve.py
```

Der Befehl lädt Kurse und Analystenkonsens neu, bewertet alle Depots unter `input/` samt Kaufempfehlung neu, baut die Seite und startet `http://localhost:8765` mit Live-Kursen.

| Pfad | Inhalt |
|---|---|
| `portfolio/` | Markdown-Wiki: Dashboard, Steckbriefe, `depots/<name>.md` und `depots/<name>_kaufempfehlung.md` |
| `docs/` | Fertige, generierte Webseite (wird von GitHub Pages ausgeliefert) |
| `website/` | Build (`build.py`), Charts, Yahoo-Anbindung (`yahoo.py`), Server (`serve.py`) |
| `tools/` | Rohdaten aus den Reports (`assets_data.py`) und Generatoren |
| `input/<name>/*.md` | Eigene Depots, ein Ordner je Person (Zeile = Name aus dem Depotauszug, optional Kaufkurs in EUR oder `gekauft am TT.MM.JJJJ`) |

Die Quell-PDFs liegen nur lokal in `PDF_input/` und sind nicht Teil des Repositories.
