# Portfolio-Wiki

Depot-Steckbriefe, eigene Depotbewertung und Kaufempfehlung auf Basis der wöchentlichen Pure-Alpha-Reports (Balthasar Becker), ergänzt um Kursdaten und Analystenkonsens von Yahoo Finance. Keine Anlageberatung.

## Webseite ansehen

`website/public/index.html` im Browser öffnen. Die Seite ist statisch und braucht keinen Server.

## Aktualisieren

```
python website/serve.py
```

Der Befehl lädt Kurse und Analystenkonsens neu, bewertet das eigene Depot und die Kaufempfehlung neu, baut die Seite und startet `http://localhost:8765` mit Live-Kursen.

| Pfad | Inhalt |
|---|---|
| `portfolio/` | Markdown-Wiki: Dashboard, Steckbriefe, `mein_depot.md`, `kaufempfehlung.md` |
| `website/` | Build (`build.py`), Charts, Yahoo-Anbindung (`yahoo.py`), Server (`serve.py`), fertige Seite in `public/` |
| `tools/` | Rohdaten aus den Reports (`assets_data.py`) und Generatoren |
| `input/michi_h/md_portolio.md` | Eigenes Depot (Format: `TICKER gekauft am TT.MM.JJJJ`) |

Die Quell-PDFs liegen nur lokal in `PDF_input/` und sind nicht Teil des Repositories.
