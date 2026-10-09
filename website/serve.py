# -*- coding: utf-8 -*-
"""Lokaler Server mit Yahoo-Finance-Anbindung.

    python website/serve.py            -> lädt Kursverläufe neu, bewertet alle Depots unter input/, baut die Seite, öffnet http://localhost:8765
    python website/serve.py --no-fetch -> ohne Neuladen der Historie (schneller Start)

Endpunkte:
    /api/quotes?t=MCD,MU   aktuelle Kurse (Seite fragt alle 60 s nach)
    /api/refresh           Kursverläufe neu laden + Seite neu bauen
"""
import json
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import build  # noqa: E402
import portfolios  # noqa: E402
import yahoo  # noqa: E402

PORT = 8765
LOCK = threading.Lock()


def refresh():
    with LOCK:
        yahoo.update(yahoo.wiki_tickers())
        portfolios.run()
        build.build()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(build.PUB), **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/quotes":
            tickers = [t for t in parse_qs(u.query).get("t", [""])[0].split(",") if t][:100]
            return self._json(yahoo.fetch_quotes(tickers))
        if u.path == "/api/refresh":
            refresh()
            return self._json({"ok": True})
        return super().do_GET()

    def log_message(self, fmt, *args):
        if "/api/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


def main():
    if "--no-fetch" in sys.argv:
        build.build()
    else:
        refresh()
    url = f"http://localhost:{PORT}/"
    print(f"Server läuft: {url}  (Strg+C beendet)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
