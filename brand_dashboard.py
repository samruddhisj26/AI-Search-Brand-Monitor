#!/usr/bin/env python3
"""
brand_dashboard.py — Web dashboard for the Brand Monitor.
Run:  python3 brand_dashboard.py
Then open: http://localhost:8766
"""

import http.server
import json
import os
import sys
import sqlite3
from datetime import datetime, timezone
from collections import Counter

PORT = 8766
DB_PATH = "/opt/data/brand-monitor/brand_monitor.db"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_analyses():
    """Get the most recent complete analysis cycle for each brand."""
    conn = get_conn()
    # Get the most recent query timestamp
    row = conn.execute("SELECT MAX(queried_at) as max_ts FROM query_log").fetchone()
    if not row or not row["max_ts"]:
        conn.close()
        return []

    max_ts = row["max_ts"]

    # Get all analyses from the most recent cycle (within 30 min of max timestamp)
    analyses = conn.execute("""
        SELECT a.*, q.platform, q.keyword, q.brand_name, q.queried_at
        FROM analysis a
        JOIN query_log q ON a.query_log_id = q.id
        WHERE q.queried_at >= datetime(?, '-30 minutes')
        ORDER BY q.brand_name, q.platform, q.keyword
    """, (max_ts,)).fetchall()

    conn.close()
    return [dict(a) for a in analyses]


def build_dashboard_data():
    """Build all dashboard data from the database."""
    analyses = get_latest_analyses()
    if not analyses:
        return None

    # Group by brand
    brands = {}
    for a in analyses:
        name = a.get("brand_name", "Unknown")
        if name not in brands:
            brands[name] = []
        brands[name].append(a)

    # Build leaderboard
    leaderboard = []
    for brand_name, brand_analyses in brands.items():
        total = len(brand_analyses)
        mentioned = [a for a in brand_analyses if a.get("brand_mentioned")]
        scores = [a.get("visibility_score", 0) for a in brand_analyses]
        avg_score = sum(scores) / total if total else 0
        mention_rate = len(mentioned) / total * 100 if total else 0

        sentiments = [a["sentiment"] for a in mentioned if a.get("sentiment")]
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")

        # Competitors
        comps = []
        for a in brand_analyses:
            comps.extend(json.loads(a.get("competitors", "[]")) if isinstance(a.get("competitors"), str) else a.get("competitors", []))
        top_comps = Counter(comps).most_common(5)

        # Platform breakdown
        platforms = {}
        for a in brand_analyses:
            plat = a.get("platform", "unknown")
            if plat not in platforms:
                platforms[plat] = {"mentioned": 0, "total": 0, "scores": []}
            platforms[plat]["total"] += 1
            platforms[plat]["scores"].append(a.get("visibility_score", 0))
            if a.get("brand_mentioned"):
                platforms[plat]["mentioned"] += 1

        leaderboard.append({
            "name": brand_name,
            "avg_score": round(avg_score, 1),
            "mention_rate": round(mention_rate, 1),
            "positive": pos,
            "negative": neg,
            "total_mentioned": len(mentioned),
            "total_queries": total,
            "competitors": [{"name": c, "count": n} for c, n in top_comps],
            "platforms": {p: {"mentioned": d["mentioned"], "total": d["total"], "avg_score": round(sum(d["scores"])/len(d["scores"]), 1)} for p, d in platforms.items()},
        })

    leaderboard.sort(key=lambda x: x["avg_score"], reverse=True)

    # Historical data (previous cycles for trend)
    conn = get_conn()
    # Get all unique cycle timestamps (by query time)
    cycles = conn.execute("""
        SELECT DISTINCT date(queried_at) as day
        FROM query_log
        ORDER BY day DESC
        LIMIT 10
    """).fetchall()
    conn.close()

    history = [c["day"] for c in cycles]

    return {
        "leaderboard": leaderboard,
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_brands": len(brands),
        "total_queries": len(analyses),
        "history": history,
    }


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Brand Monitor Dashboard</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 { text-align: center; font-size: 26px; color: #58a6ff; margin-bottom: 4px; }
  .subtitle { text-align: center; color: #8b949e; font-size: 13px; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h3 { font-size: 14px; color: #8b949e; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  .full-width { grid-column: 1 / -1; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 12px; color: #8b949e; padding: 6px 8px; border-bottom: 1px solid #21262d; }
  td { padding: 8px; font-size: 13px; border-bottom: 1px solid #21262d; }
  .rank { color: #8b949e; font-size: 12px; width: 24px; }
  .bar { height: 18px; border-radius: 3px; min-width: 4px; transition: width 0.5s; }
  .bar-green { background: #3fb950; }
  .bar-yellow { background: #d29922; }
  .bar-red { background: #f85149; }
  .score-cell { display: flex; align-items: center; gap: 8px; }
  .score-num { font-weight: 600; min-width: 36px; }
  .tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }
  .tag-green { background: #3fb95020; color: #3fb950; border: 1px solid #3fb95040; }
  .tag-red { background: #f8514920; color: #f85149; border: 1px solid #f8514940; }
  .tag-yellow { background: #d2992220; color: #d29922; border: 1px solid #d2992240; }
  .platform-grid { display: flex; gap: 12px; flex-wrap: wrap; }
  .platform-badge { background: #21262d; border-radius: 4px; padding: 6px 10px; font-size: 12px; }
  .platform-badge strong { color: #e6edf3; }
  .comp-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
  .comp-chip { background: #21262d; border-radius: 3px; padding: 2px 6px; font-size: 11px; color: #8b949e; }
  .comp-chip .count { color: #58a6ff; font-weight: 600; }
  .brand-header { display: flex; align-items: center; gap: 8px; }
  .brand-header .name { font-weight: 600; }
  .brand-header .cat { font-size: 11px; color: #8b949e; }
  .collapse { cursor: pointer; user-select: none; }
  .collapse:hover { color: #58a6ff; }
  .details { display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid #21262d; }
  .details.open { display: block; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .status-dot.green { background: #3fb950; }
  .status-dot.yellow { background: #d29922; }
  .status-dot.red { background: #f85149; }
  @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container" id="app">
  <h1>📊 AI Search Brand Monitor</h1>
  <p class="subtitle" v-if="data">Scan {{ data.updated }} · {{ data.total_brands }} brands · {{ data.total_queries }} queries</p>
  <p class="subtitle" v-else>Loading...</p>

  <div class="grid" v-if="data">
    <!-- Leaderboard -->
    <div class="card full-width">
      <h3>🏆 Visibility Leaderboard</h3>
      <table>
        <tr>
          <th></th><th>Brand</th><th>Score</th><th>Mention Rate</th><th>Sentiment</th><th>Platforms</th>
        </tr>
        <tr v-for="(b, i) in data.leaderboard" :key="b.name">
          <td class="rank">{{ i + 1 }}</td>
          <td>
            <span class="brand-header">
              <span :class="'status-dot ' + (b.avg_score >= 40 ? 'green' : b.avg_score >= 15 ? 'yellow' : 'red')"></span>
              <span class="name">{{ b.name }}</span>
            </span>
          </td>
          <td>
            <div class="score-cell">
              <span class="score-num" :style="{color: b.avg_score >= 40 ? '#3fb950' : b.avg_score >= 15 ? '#d29922' : '#f85149'}">{{ b.avg_score }}</span>
              <div class="bar" :class="b.avg_score >= 40 ? 'bar-green' : b.avg_score >= 15 ? 'bar-yellow' : 'bar-red'"
                   :style="{width: Math.max(4, b.avg_score * 1.5) + 'px'}"></div>
            </div>
          </td>
          <td>{{ b.mention_rate }}%</td>
          <td>
            <span class="tag tag-green" v-if="b.positive > 0">+{{ b.positive }}</span>
            <span class="tag tag-red" v-if="b.negative > 0">-{{ b.negative }}</span>
          </td>
          <td>
            <div class="platform-grid">
              <div class="platform-badge" v-for="(p, plat) in b.platforms" :key="plat">
                <strong>{{ plat.slice(0,4) }}</strong> {{ p.avg_score }}
              </div>
            </div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Share of Voice -->
    <div class="card">
      <h3>📊 Share of Voice</h3>
      <div v-for="b in data.leaderboard" :key="b.name + 'sov'" style="margin-bottom: 6px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px;">
          <span>{{ b.name }}</span>
          <span>{{ b.total_mentioned }}/{{ b.total_queries }}</span>
        </div>
        <div style="background:#21262d;border-radius:3px;height:10px;overflow:hidden;">
          <div :style="{width: (b.mention_rate)+'%', height:'100%', background: b.avg_score >= 40 ? '#3fb950' : '#d29922', borderRadius:'3px', transition:'width 0.5s'}"></div>
        </div>
      </div>
    </div>

    <!-- Competitive Landscape -->
    <div class="card">
      <h3>🎯 Top Competitors</h3>
      <div v-for="b in data.leaderboard.slice(0, 5)" :key="b.name + 'comp'" style="margin-bottom: 10px;">
        <div style="font-size:13px;font-weight:600;margin-bottom:4px;">{{ b.name }}</div>
        <div class="comp-list">
          <span class="comp-chip" v-for="c in b.competitors" :key="c.name">
            {{ c.name }} <span class="count">({{ c.count }})</span>
          </span>
          <span style="font-size:11px;color:#484f58;" v-if="b.competitors.length === 0">No competitors detected</span>
        </div>
      </div>
    </div>

    <!-- Brand Detail Cards -->
    <div class="card full-width">
      <h3>🔍 Brand Details</h3>
      <table>
        <tr>
          <th></th><th>Brand</th><th>Score</th><th>Top Competitor</th><th>Gap</th><th>Priority</th>
        </tr>
        <tr v-for="(b, i) in data.leaderboard" :key="b.name + 'detail'">
          <td class="rank">{{ i + 1 }}</td>
          <td>
            <span class="collapse" @click="toggle(b.name)">
              <span>{{ b.name }}</span>
              <span style="font-size:10px;color:#484f58;">{{ expanded[b.name] ? '▲' : '▼' }}</span>
            </span>
          </td>
          <td :style="{color: b.avg_score >= 40 ? '#3fb950' : b.avg_score >= 15 ? '#d29922' : '#f85149'}">{{ b.avg_score }}</td>
          <td>{{ b.competitors[0]?.name || '—' }}</td>
          <td>{{ b.competitors[0]?.count || 0 }}x mentions</td>
          <td>
            <span class="tag" :class="b.avg_score < 15 ? 'tag-red' : b.avg_score < 40 ? 'tag-yellow' : 'tag-green'">
              {{ b.avg_score < 15 ? 'HIGH' : b.avg_score < 40 ? 'MEDIUM' : 'LOW' }}
            </span>
          </td>
        </tr>
      </table>
      <div v-for="b in data.leaderboard" :key="b.name + 'expand'" :class="'details ' + (expanded[b.name] ? 'open' : '')">
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:12px;">
          <div v-for="(p, plat) in b.platforms" :key="plat" class="platform-badge">
            <strong>{{ plat }}</strong><br>
            Score: {{ p.avg_score }} · {{ p.mentioned }}/{{ p.total }} queries
          </div>
        </div>
        <div class="comp-list" style="margin-top:8px;">
          <span class="comp-chip" v-for="c in b.competitors" :key="c.name">
            {{ c.name }} <span class="count">({{ c.count }})</span>
          </span>
        </div>
      </div>
    </div>
  </div>

  <div style="text-align:center;color:#484f58;font-size:12px;padding:20px;">
    Need a fresh scan? Run: <code style="background:#21262d;padding:2px 6px;border-radius:3px;">python3 runner.py</code>
    · <a href="/api/data" style="color:#58a6ff;">API data</a>
  </div>
</div>

<script>
const { createApp, ref, onMounted } = Vue;
createApp({
  setup() {
    const data = ref(null);
    const expanded = ref({});
    async function load() {
      const r = await fetch('/api/data');
      data.value = await r.json();
    }
    function toggle(name) {
      expanded.value[name] = !expanded.value[name];
    }
    onMounted(load);
    return { data, expanded, toggle };
  }
}).mount('#app');
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        elif self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            dash_data = build_dashboard_data()
            if dash_data:
                self.wfile.write(json.dumps(dash_data).encode())
            else:
                self.wfile.write(json.dumps({"error": "No data found. Run the scanner first: python3 runner.py"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"⚠ Database not found at {DB_PATH}")
        print(f"  Run the scanner first: cd /opt/data/brand-monitor && python3 runner.py")
        sys.exit(1)

    print(f"📊 Brand Monitor Dashboard")
    print(f"   Open: http://localhost:{PORT}")
    print(f"   Data: {DB_PATH}")
    print(f"   Press Ctrl+C to stop")
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()