#!/usr/bin/env python3
"""Chart MSTR's market cap against the dollar value of its Bitcoin holdings."""

from datetime import datetime
from pathlib import Path

import json

import requests

HERE = Path(__file__).resolve().parent
CHART = HERE / "mstr-btc.png"
INTERACTIVE = HERE / "mstr-btc.html"
LATEST_URL = "https://data.strategytracker.com/latest.json"
COMPANY_URL = "https://data.strategytracker.com/MSTR.v{version}.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://strategytracker.com/"}


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()


def build_rows() -> list[dict]:
    version = fetch_json(LATEST_URL)["version"]
    history = fetch_json(COMPANY_URL.format(version=version))["companies"]["MSTR"]["historicalData"]
    rows = []
    for day, price, shares, balance, btc_price in zip(
        history["dates"],
        history["stock_prices"],
        history["total_outstanding_shares"],
        history["btc_balance"],
        history["btc_prices"],
    ):
        date = datetime.fromisoformat(day).date()
        if date.weekday() >= 5:
            continue
        if price is None or shares is None or not balance or btc_price is None:
            continue
        rows.append(
            {
                "date": date,
                "market_cap": float(price) * float(shares),
                "btc_value": float(balance) * float(btc_price),
            }
        )
    if not rows:
        raise RuntimeError("No overlapping MSTR and Bitcoin history")
    return rows


def draw(rows: list[dict]) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    panel = "#0b0d10"
    plot = "#000000"
    grid = "#2a2e33"
    ink = "#d7dbe0"
    title = "#f4f6f8"
    muted = "#8b939c"
    blue = "#4da3ff"
    green = "#00d26a"

    dates = [row["date"] for row in rows]
    market_cap = [row["market_cap"] / 1e9 for row in rows]
    btc_value = [row["btc_value"] / 1e9 for row in rows]
    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=panel)
    ax.set_facecolor(plot)
    ax.fill_between(
        dates,
        market_cap,
        btc_value,
        where=[cap >= btc for cap, btc in zip(market_cap, btc_value)],
        interpolate=True,
        color="#ff4d5a",
        alpha=0.18,
        linewidth=0,
    )
    ax.fill_between(
        dates,
        market_cap,
        btc_value,
        where=[btc > cap for cap, btc in zip(market_cap, btc_value)],
        interpolate=True,
        color="#00d26a",
        alpha=0.16,
        linewidth=0,
    )
    ax.plot(dates, market_cap, color=blue, linewidth=2, label="MSTR market cap")
    ax.plot(dates, btc_value, color=green, linewidth=2, label="BTC holdings value")
    ax.set_title("MSTR market cap and Bitcoin holdings", color=title, pad=12)
    ax.set_ylabel("Billions of dollars", color=ink)
    ax.tick_params(colors=ink)
    ax.grid(True, axis="y", color=grid)
    for spine in ax.spines.values():
        spine.set_color(grid)
    legend = ax.legend(frameon=True, facecolor=panel, edgecolor=grid, labelcolor=ink)
    legend.get_frame().set_linewidth(0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()
    fig.text(
        0.01,
        0.01,
        "Bitcoin value uses the last reported balance until the next disclosure. Market cap is the close times basic shares outstanding.",
        fontsize=8,
        color=muted,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CHART, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)


def write_interactive(rows: list[dict]) -> None:
    payload = [
        [row["date"].isoformat(), row["market_cap"], row["btc_value"]]
        for row in rows
    ]
    data = json.dumps(payload).replace("<", "\\u003c")
    INTERACTIVE.write_text(HTML.replace("__DATA__", data), encoding="utf-8")


def main() -> int:
    rows = build_rows()
    draw(rows)
    write_interactive(rows)
    latest = rows[-1]
    print(f"Chart saved to {CHART}")
    print(f"Interactive chart saved to {INTERACTIVE}")
    print(
        f"{latest['date'].isoformat()}: market cap ${latest['market_cap'] / 1e9:.2f}B, "
        f"BTC holdings ${latest['btc_value'] / 1e9:.2f}B"
    )
    return 0


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MSTR market cap and Bitcoin holdings</title>
<style>
  html, body { margin: 0; background: #0b0d10; color: #d7dbe0; font-family: "Segoe UI", sans-serif; }
  body { min-height: 100vh; }
  #wrap { position: relative; width: min(1100px, 100vw); margin: 0 auto; }
  svg { display: block; width: 100%; height: auto; }
  #tip {
    position: absolute; z-index: 2; pointer-events: none; display: none;
    background: #0b0d10; border: 1px solid #2a2e33; border-radius: 6px;
    padding: 8px 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.45);
  }
  #tip .date { color: #f4f6f8; font-size: 13px; }
  #tip .cap { color: #4da3ff; font-size: 13px; margin-top: 3px; }
  #tip .hold { color: #00d26a; font-size: 13px; margin-top: 3px; }
</style>
</head>
<body>
<div id="wrap">
  <svg id="chart" viewBox="0 0 1100 680" role="img" aria-label="MSTR market cap and Bitcoin holdings"></svg>
  <div id="tip"><div class="date"></div><div class="cap"></div><div class="hold"></div></div>
</div>
<script>
const rows = __DATA__.map(([d, cap, btc]) => ({d, cap, btc}));
const svg = document.getElementById("chart");
const tip = document.getElementById("tip");
const W = 1100, H = 680;
const margin = {l: 74, r: 28, t: 48, b: 86};
const plotW = W - margin.l - margin.r;
const plotH = H - margin.t - margin.b;
const times = rows.map(r => Date.parse(r.d + "T00:00:00Z"));
const caps = rows.map(r => r.cap / 1e9);
const btcs = rows.map(r => r.btc / 1e9);
const xMin = times[0];
const xMax = times[times.length - 1];
const yMax = Math.ceil(Math.max(...caps, ...btcs) / 20) * 20;
const xPix = t => margin.l + (t - xMin) / (xMax - xMin) * plotW;
const yPix = v => margin.t + (1 - v / yMax) * plotH;

const ns = "http://www.w3.org/2000/svg";
function el(name, attrs) {
  const node = document.createElementNS(ns, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  svg.appendChild(node);
  return node;
}

el("rect", {x: 0, y: 0, width: W, height: H, fill: "#0b0d10"});
el("rect", {x: margin.l, y: margin.t, width: plotW, height: plotH, fill: "#000"});
el("text", {x: W / 2, y: 28, fill: "#f4f6f8", "font-size": 16, "text-anchor": "middle"}).textContent = "MSTR market cap and Bitcoin holdings";
el("text", {x: 18, y: margin.t + plotH / 2, fill: "#d7dbe0", "font-size": 12, "text-anchor": "middle", transform: `rotate(-90 18 ${margin.t + plotH / 2})`}).textContent = "Billions of dollars";

for (let value = 0; value <= yMax; value += 20) {
  const y = yPix(value);
  el("line", {x1: margin.l, y1: y, x2: margin.l + plotW, y2: y, stroke: "#2a2e33"});
  el("text", {x: margin.l - 10, y: y + 4, fill: "#d7dbe0", "font-size": 11, "text-anchor": "end"}).textContent = String(value);
}

const startYear = new Date(xMin).getUTCFullYear();
const endYear = new Date(xMax).getUTCFullYear();
for (let year = startYear; year <= endYear; year++) {
  for (const month of [0, 6]) {
    const t = Date.UTC(year, month, 1);
    if (t < xMin || t > xMax) continue;
    const x = xPix(t);
    const label = new Date(t).toLocaleDateString("en-US", {month: "short", year: "numeric", timeZone: "UTC"});
    const text = el("text", {x, y: margin.t + plotH + 22, fill: "#d7dbe0", "font-size": 11, "text-anchor": "end", transform: `rotate(-35 ${x} ${margin.t + plotH + 22})`});
    text.textContent = label;
  }
}
el("rect", {x: margin.l, y: margin.t, width: plotW, height: plotH, fill: "none", stroke: "#2a2e33"});

function areaPaths() {
  const parts = {red: [], green: []};
  let run = [];
  let side = null;
  function flush() {
    if (run.length < 2) { run = []; return; }
    const forward = run.map(p => `${p.x.toFixed(1)},${yPix(p.hi).toFixed(1)}`);
    const back = run.map(p => `${p.x.toFixed(1)},${yPix(p.lo).toFixed(1)}`).reverse();
    parts[side].push(`M${forward[0]} L${forward.slice(1).join(" L")} L${back.join(" L")} Z`);
    run = [];
  }
  for (let i = 0; i < rows.length; i++) {
    const sideNow = caps[i] >= btcs[i] ? "red" : "green";
    if (i > 0 && sideNow !== side) {
      const gap = (caps[i - 1] - btcs[i - 1]) - (caps[i] - btcs[i]);
      const t = gap === 0 ? 0 : (caps[i - 1] - btcs[i - 1]) / gap;
      const x = xPix(times[i - 1] + (times[i] - times[i - 1]) * t);
      const y = caps[i - 1] + (caps[i] - caps[i - 1]) * t;
      run.push({x, hi: y, lo: y});
      flush();
      side = sideNow;
      run.push({x, hi: y, lo: y});
    } else if (side === null) {
      side = sideNow;
    }
    run.push({x: xPix(times[i]), hi: Math.max(caps[i], btcs[i]), lo: Math.min(caps[i], btcs[i])});
  }
  flush();
  return parts;
}
const areas = areaPaths();
for (const d of areas.red) el("path", {d, fill: "#ff4d5a", "fill-opacity": 0.18});
for (const d of areas.green) el("path", {d, fill: "#00d26a", "fill-opacity": 0.16});

function linePath(values) {
  return values.map((v, i) => `${i ? "L" : "M"}${xPix(times[i]).toFixed(1)},${yPix(v).toFixed(1)}`).join("");
}
el("path", {d: linePath(caps), fill: "none", stroke: "#4da3ff", "stroke-width": 2});
el("path", {d: linePath(btcs), fill: "none", stroke: "#00d26a", "stroke-width": 2});

const legend = el("g", {});
el("rect", {x: margin.l + plotW - 196, y: margin.t + 10, width: 184, height: 48, rx: 4, fill: "#0b0d10", stroke: "#2a2e33"});
legend.appendChild(svg.lastChild);
el("line", {x1: margin.l + plotW - 182, y1: margin.t + 26, x2: margin.l + plotW - 160, y2: margin.t + 26, stroke: "#4da3ff", "stroke-width": 2});
el("text", {x: margin.l + plotW - 152, y: margin.t + 30, fill: "#d7dbe0", "font-size": 12}).textContent = "MSTR market cap";
el("line", {x1: margin.l + plotW - 182, y1: margin.t + 44, x2: margin.l + plotW - 160, y2: margin.t + 44, stroke: "#00d26a", "stroke-width": 2});
el("text", {x: margin.l + plotW - 152, y: margin.t + 48, fill: "#d7dbe0", "font-size": 12}).textContent = "BTC holdings value";

el("text", {x: 12, y: H - 14, fill: "#8b939c", "font-size": 11}).textContent = "Bitcoin value uses the last reported balance until the next disclosure. Market cap is the close times basic shares outstanding.";

const guide = el("line", {x1: 0, y1: margin.t, x2: 0, y2: margin.t + plotH, stroke: "#8b939c", "stroke-width": 1, visibility: "hidden"});
const dot = el("circle", {r: 3.5, fill: "#4da3ff", stroke: "#0b0d10", "stroke-width": 1, visibility: "hidden"});
const holdDot = el("circle", {r: 3.5, fill: "#00d26a", stroke: "#0b0d10", "stroke-width": 1, visibility: "hidden"});
const hit = el("rect", {x: margin.l, y: margin.t, width: plotW, height: plotH, fill: "transparent", cursor: "crosshair"});

function nearest(x) {
  let lo = 0, hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xPix(times[mid]) < x) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(xPix(times[lo - 1]) - x) < Math.abs(xPix(times[lo]) - x)) return lo - 1;
  return lo;
}

function show(index, clientX, clientY) {
  const row = rows[index];
  const x = xPix(times[index]);
  guide.setAttribute("x1", x);
  guide.setAttribute("x2", x);
  guide.setAttribute("visibility", "visible");
  dot.setAttribute("cx", x);
  dot.setAttribute("cy", yPix(caps[index]));
  dot.setAttribute("visibility", "visible");
  holdDot.setAttribute("cx", x);
  holdDot.setAttribute("cy", yPix(btcs[index]));
  holdDot.setAttribute("visibility", "visible");
  const when = new Date(row.d + "T00:00:00Z").toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"});
  tip.querySelector(".date").textContent = when;
  tip.querySelector(".cap").textContent = "Market cap $" + caps[index].toFixed(2) + "B";
  tip.querySelector(".hold").textContent = "BTC holdings $" + btcs[index].toFixed(2) + "B";
  tip.style.display = "block";
  const wrap = document.getElementById("wrap").getBoundingClientRect();
  let left = clientX - wrap.left + 14;
  let top = clientY - wrap.top + 14;
  if (left + tip.offsetWidth > wrap.width - 8) left = clientX - wrap.left - tip.offsetWidth - 14;
  if (top + tip.offsetHeight > wrap.height - 8) top = clientY - wrap.top - tip.offsetHeight - 14;
  tip.style.left = left + "px";
  tip.style.top = top + "px";
}

function hide() {
  guide.setAttribute("visibility", "hidden");
  dot.setAttribute("visibility", "hidden");
  holdDot.setAttribute("visibility", "hidden");
  tip.style.display = "none";
}

hit.addEventListener("mousemove", event => {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const local = point.matrixTransform(svg.getScreenCTM().inverse());
  if (local.x < margin.l || local.x > margin.l + plotW) { hide(); return; }
  show(nearest(local.x), event.clientX, event.clientY);
});
hit.addEventListener("mouseleave", hide);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
