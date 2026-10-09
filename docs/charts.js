/* Kleine SVG-Chart-Bibliothek ohne Abhängigkeiten.
   lineChart  – Kurs + 200-Tage-Linie mit Crosshair-Tooltip und Zeitraumwahl
   divergingBars – Abstand zur 200-Tage-Linie (blau = darüber, rot = darunter)
   sparkline – Mini-Verlauf für Tabellen */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };
  const fmt = (v, d = 2) => v == null ? "–" : v.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtPct = v => v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), 1) + " %";
  const fmtDate = s => { const [y, m, d] = s.split("-"); return `${d}.${m}.${y}`; };
  window.fmtPct = fmtPct; window.fmtNum = fmt;

  function niceTicks(min, max, n = 4) {
    const span = max - min || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || mag * 10;
    const out = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  function tooltip(host) {
    let t = host.querySelector(".viz-tip");
    if (!t) { t = document.createElement("div"); t.className = "viz-tip"; host.appendChild(t); }
    return t;
  }

  /* ---------------------------------------------------------- Linienchart */
  window.lineChart = function (host, series, opts = {}) {
    const ranges = [["1M", 21], ["3M", 63], ["6M", 126], ["1J", 252], ["2J", 10000]];
    let cur = opts.range || "1J";
    host.classList.add("viz-root");
    host.innerHTML = `
      <div class="viz-head">
        <div class="viz-legend">
          <span><i class="sw sw-line"></i>Kurs (${series.currency || ""})</span>
          <span><i class="sw sw-dash"></i>200-Tage-Linie</span>
        </div>
        <div class="seg" role="group" aria-label="Zeitraum">${ranges.map(([k]) => `<button type="button" data-r="${k}">${k}</button>`).join("")}</div>
      </div>
      <div class="viz-plot"></div>`;
    const plot = host.querySelector(".viz-plot");
    host.querySelectorAll(".seg button").forEach(b => b.addEventListener("click", () => { cur = b.dataset.r; draw(); }));

    function draw() {
      host.querySelectorAll(".seg button").forEach(b => b.classList.toggle("on", b.dataset.r === cur));
      const n = ranges.find(r => r[0] === cur)[1];
      const start = Math.max(0, series.close.length - n);
      const D = series.dates.slice(start), C = series.close.slice(start), S = series.sma200.slice(start);
      const W = plot.clientWidth || 640, H = opts.height || 300, m = { t: 12, r: 12, b: 26, l: 52 };
      const vals = C.concat(S.filter(v => v != null));
      let lo = Math.min(...vals), hi = Math.max(...vals);
      const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
      const x = i => m.l + (i / Math.max(1, C.length - 1)) * (W - m.l - m.r);
      const y = v => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
      plot.innerHTML = "";
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
        "aria-label": `Kursverlauf ${series.ticker}, ${cur}` }, plot);
      niceTicks(lo, hi).forEach(v => {
        el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "grid" }, svg);
        el("text", { x: m.l - 8, y: y(v) + 4, class: "tick", "text-anchor": "end" }, svg).textContent = fmt(v, v >= 100 ? 0 : 2);
      });
      const xt = Math.min(5, C.length);
      for (let k = 0; k < xt; k++) {
        const i = Math.round(k * (C.length - 1) / Math.max(1, xt - 1));
        el("text", { x: x(i), y: H - 6, class: "tick", "text-anchor": k === 0 ? "start" : k === xt - 1 ? "end" : "middle" }, svg)
          .textContent = fmtDate(D[i]).slice(0, cur === "2J" || cur === "1J" ? 10 : 5);
      }
      const path = arr => arr.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)
        .reduce((a, p) => p == null ? a + " " : a + (a.endsWith(" ") || !a ? "M" : "L") + p, "").trim();
      el("path", { d: path(S), class: "ma" }, svg);
      el("path", { d: path(C), class: "price" }, svg);
      // Endpunkt + Direktlabel
      const li = C.length - 1;
      el("circle", { cx: x(li), cy: y(C[li]), r: 4, class: "dot" }, svg);

      // Hover-Layer
      const cross = el("line", { y1: m.t, y2: H - m.b, class: "cross", visibility: "hidden" }, svg);
      const hd = el("circle", { r: 4.5, class: "dot", visibility: "hidden" }, svg);
      const hit = el("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" }, svg);
      const tip = tooltip(host);
      const move = ev => {
        const r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
        const i = Math.max(0, Math.min(C.length - 1, Math.round((px * W / r.width - m.l) / (W - m.l - m.r) * (C.length - 1))));
        cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
        hd.setAttribute("cx", x(i)); hd.setAttribute("cy", y(C[i])); hd.setAttribute("visibility", "visible");
        const dist = S[i] ? (C[i] / S[i] - 1) * 100 : null;
        tip.innerHTML = `<b>${fmtDate(D[i])}</b><div><i class="sw sw-line"></i>Kurs <span>${fmt(C[i])}</span></div>` +
          `<div><i class="sw sw-dash"></i>200T <span>${fmt(S[i])}</span></div>` +
          (dist != null ? `<div class="muted">Abstand <span>${fmtPct(dist)}</span></div>` : "");
        tip.style.display = "block";
        const tx = x(i) * r.width / W;
        tip.style.left = Math.min(r.width - tip.offsetWidth - 4, Math.max(4, tx + 12)) + "px";
        tip.style.top = "40px";
      };
      const leave = () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); hd.setAttribute("visibility", "hidden"); };
      hit.addEventListener("mousemove", move); hit.addEventListener("touchmove", move, { passive: true });
      hit.addEventListener("mouseleave", leave);
    }
    draw();
    let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(draw, 120); });
  };

  /* ---------------------------------------------------------- Diverging Bars */
  window.divergingBars = function (host, rows, opts = {}) {
    // rows: [{label, sub, value, href}]
    host.classList.add("viz-root");
    const tip = tooltip(host);
    const W = host.clientWidth || 640, rowH = 22, m = { t: 22, r: 56, b: 8, l: 64 };
    const H = m.t + m.b + rows.length * rowH;
    const ext = Math.max(10, ...rows.map(r => Math.abs(r.value)));
    const x = v => m.l + (v + ext) / (2 * ext) * (W - m.l - m.r);
    host.querySelectorAll("svg").forEach(s => s.remove());
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": opts.label || "" }, host);
    niceTicks(-ext, ext, 6).forEach(v => {
      el("line", { x1: x(v), x2: x(v), y1: m.t - 4, y2: H - m.b, class: v === 0 ? "base" : "grid" }, svg);
      el("text", { x: x(v), y: 12, class: "tick", "text-anchor": "middle" }, svg).textContent = (v > 0 ? "+" : "") + v + "%";
    });
    rows.forEach((r, k) => {
      const yy = m.t + k * rowH, h = rowH - 6, x0 = x(0), x1 = x(r.value);
      const g = el("g", { class: "bar-row" }, svg);
      el("text", { x: m.l - 8, y: yy + h / 2 + 4, class: "lbl", "text-anchor": "end" }, g).textContent = r.label;
      const w = Math.max(1, Math.abs(x1 - x0)), bx = Math.min(x0, x1), rad = Math.min(4, w / 2);
      // 4px abgerundetes Datenende, Basis an der Nulllinie
      const pos = r.value >= 0;
      const d = pos
        ? `M${bx},${yy} H${bx + w - rad} Q${bx + w},${yy} ${bx + w},${yy + rad} V${yy + h - rad} Q${bx + w},${yy + h} ${bx + w - rad},${yy + h} H${bx} Z`
        : `M${bx + w},${yy} H${bx + rad} Q${bx},${yy} ${bx},${yy + rad} V${yy + h - rad} Q${bx},${yy + h} ${bx + rad},${yy + h} H${bx + w} Z`;
      el("path", { d, class: pos ? "up" : "down" }, g);
      el("text", { x: pos ? bx + w + 6 : bx - 6, y: yy + h / 2 + 4, class: "val", "text-anchor": pos ? "start" : "end" }, g)
        .textContent = fmtPct(r.value);
      const hit = el("rect", { x: 0, y: yy - 3, width: W, height: rowH, fill: "transparent" }, g);
      hit.addEventListener("mousemove", ev => {
        const b = host.getBoundingClientRect();
        tip.innerHTML = `<b>${r.label}</b> ${r.sub || ""}<div>Abstand 200T <span>${fmtPct(r.value)}</span></div>` + (r.extra || "");
        tip.style.display = "block";
        tip.style.left = Math.min(b.width - tip.offsetWidth - 4, ev.clientX - b.left + 14) + "px";
        tip.style.top = (ev.clientY - b.top + 14) + "px";
      });
      hit.addEventListener("mouseleave", () => tip.style.display = "none");
      if (r.href) { hit.style.cursor = "pointer"; hit.addEventListener("click", () => location.href = r.href); }
    });
  };

  /* ---------------------------------------------------------- Sparkline */
  window.sparkline = function (values, w = 96, h = 28) {
    if (!values || values.length < 2) return "";
    const lo = Math.min(...values), hi = Math.max(...values);
    const pts = values.map((v, i) => `${(i / (values.length - 1) * (w - 4) + 2).toFixed(1)},${(2 + (1 - (v - lo) / (hi - lo || 1)) * (h - 4)).toFixed(1)}`);
    const up = values[values.length - 1] >= values[0];
    const last = pts[pts.length - 1].split(",");
    return `<svg class="spark ${up ? "up" : "down"}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">` +
      `<polyline points="${pts.join(" ")}"/><circle cx="${last[0]}" cy="${last[1]}" r="2.5"/></svg>`;
  };

  /* ---------------------------------------------------------- Live-Kurse (nur via serve.py) */
  window.liveQuotes = function (tickers, onData) {
    // nur mit lokalem Server (serve.py); auf file:// und GitHub Pages gibt es keine /api
    if (!["localhost", "127.0.0.1"].includes(location.hostname)) return;
    const pull = () => fetch("/api/quotes?t=" + encodeURIComponent(tickers.join(",")))
      .then(r => r.ok ? r.json() : null).then(d => d && onData(d)).catch(() => {});
    pull(); setInterval(pull, 60000);
  };
})();

/* ---------------------------------------------------------- Indexierte Performance (mehrere Serien, Start = 100) */
window.indexChart = function (host, series) {
  // series: [{label, dates[], close[], cls}]
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; };
  host.classList.add("viz-root");
  const dates = [...new Set(series.flatMap(s => s.dates))].sort();
  const S = series.map(s => { const m = {}; s.dates.forEach((d, i) => m[d] = s.close[i] / s.close[0] * 100); return { ...s, v: dates.map(d => m[d] ?? null) }; });
  host.innerHTML = `<div class="viz-head"><div class="viz-legend">${S.map(s => `<span class="${s.cls}"><i class="sw"></i>${s.label}</span>`).join("")}</div></div><div class="viz-plot"></div>`;
  const plot = host.querySelector(".viz-plot");
  function draw() {
    const W = plot.clientWidth || 640, H = 280, m = { t: 12, r: 64, b: 26, l: 44 };
    const all = S.flatMap(s => s.v.filter(v => v != null)).concat([100]);
    let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * .08 || 5; lo -= pad; hi += pad;
    const x = i => m.l + i / Math.max(1, dates.length - 1) * (W - m.l - m.r);
    const y = v => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
    plot.innerHTML = "";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Performance seit Kauf, indexiert auf 100" }, plot);
    const step = (hi - lo) > 60 ? 20 : 10;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: v === 100 ? "base" : "grid" }, svg);
      el("text", { x: m.l - 8, y: y(v) + 4, class: "tick", "text-anchor": "end" }, svg).textContent = v;
    }
    [0, Math.floor((dates.length - 1) / 2), dates.length - 1].forEach((i, k) => {
      const [yy, mm, dd] = dates[i].split("-");
      el("text", { x: x(i), y: H - 6, class: "tick", "text-anchor": ["start", "middle", "end"][k] }, svg).textContent = `${dd}.${mm}.`;
    });
    S.forEach(s => {
      let d = "", pen = false;
      s.v.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1); pen = true; });
      el("path", { d, class: "line " + s.cls }, svg);
      const li = s.v.length - 1, lv = s.v[li];
      el("circle", { cx: x(li), cy: y(lv), r: 4, class: "end " + s.cls }, svg);
      el("text", { x: x(li) + 8, y: y(lv) + 4, class: "lbl" }, svg).textContent = s.label;
    });
    // Kollisionsschutz für Direktlabels
    const labels = [...svg.querySelectorAll("text.lbl")].sort((a, b) => a.getAttribute("y") - b.getAttribute("y"));
    for (let k = 1; k < labels.length; k++) {
      const prev = +labels[k - 1].getAttribute("y"), cur = +labels[k].getAttribute("y");
      if (cur - prev < 14) labels[k].setAttribute("y", prev + 14);
    }
    const cross = el("line", { y1: m.t, y2: H - m.b, class: "cross", visibility: "hidden" }, svg);
    const hit = el("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" }, svg);
    let tip = host.querySelector(".viz-tip"); if (!tip) { tip = document.createElement("div"); tip.className = "viz-tip"; host.appendChild(tip); }
    hit.addEventListener("mousemove", ev => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(dates.length - 1, Math.round(((ev.clientX - r.left) * W / r.width - m.l) / (W - m.l - m.r) * (dates.length - 1))));
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
      const [yy, mm, dd] = dates[i].split("-");
      tip.innerHTML = `<b>${dd}.${mm}.${yy}</b>` + S.map(s => `<div class="${s.cls}"><i class="sw"></i>${s.label}<span>${s.v[i] == null ? "–" : fmtPct(s.v[i] - 100)}</span></div>`).join("");
      tip.style.display = "block";
      tip.style.left = Math.min(r.width - tip.offsetWidth - 4, x(i) * r.width / W + 12) + "px"; tip.style.top = "36px";
    });
    hit.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); });
  }
  draw();
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(draw, 120); });
};
