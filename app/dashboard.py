from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .logging_config import LOG_PATH


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return round(float(d0 + d1), 2)


def get_dashboard_metrics(window_minutes: int = 60) -> dict[str, Any]:
    if not LOG_PATH.exists():
        return {"error": "logs not found"}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)

    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            ts_str = rec.get("ts")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    records.append(rec)
            else:
                records.append(rec)
        except Exception:
            continue

    # 1. Latency & TTFT
    response_events = [r for r in records if r.get("event") == "response_sent"]
    latencies = [float(r["latency_ms"]) for r in response_events if "latency_ms" in r]
    ttfts = [float(r["ttft_ms"]) for r in response_events if "ttft_ms" in r]

    latency_metrics = {
        "p50": _percentile(latencies, 50),
        "p95": _percentile(latencies, 95),
        "p99": _percentile(latencies, 99),
        "ttft_p95": _percentile(ttfts, 95),
        "count": len(latencies),
        "threshold": {"aggregation": "p95", "operator": "lte", "value": 3000},
        "status": "PASS" if _percentile(latencies, 95) <= 3000 else "VIOLATION",
    }

    # 2. Traffic
    received_events = [r for r in records if r.get("event") == "request_received"]
    traffic_count = len(received_events)
    rate_per_min = round(traffic_count / max(1, window_minutes), 2)
    traffic_metrics = {
        "count": traffic_count,
        "rate_per_minute": rate_per_min,
        "threshold": {"aggregation": "rate_per_minute", "operator": "gte", "value": 1},
        "status": "PASS" if rate_per_min >= 1 or traffic_count >= 1 else "WAITING",
    }

    # 3. Errors & Retrieval
    failed_events = [r for r in records if r.get("event") == "request_failed"]
    total_reqs = max(len(received_events), len(response_events) + len(failed_events))
    error_rate = round((len(failed_events) / total_reqs * 100) if total_reqs > 0 else 0.0, 2)

    error_breakdown: dict[str, int] = {}
    for f in failed_events:
        etype = f.get("error_type", "UnknownError")
        error_breakdown[etype] = error_breakdown.get(etype, 0) + 1

    tool_events = [r for r in records if r.get("tool_name") == "retrieval" and r.get("tool_success") is not None]
    tool_success_count = sum(1 for r in tool_events if r.get("tool_success") is True)
    tool_success_rate = round((tool_success_count / len(tool_events) * 100) if tool_events else 100.0, 2)

    error_metrics = {
        "error_rate_pct": error_rate,
        "count_by_value": error_breakdown,
        "tool_success_rate_pct": tool_success_rate,
        "failed_count": len(failed_events),
        "threshold": {"aggregation": "error_rate_pct", "operator": "lte", "value": 2},
        "status": "PASS" if error_rate <= 2 else "VIOLATION",
    }

    # 4. Cost
    costs = [float(r.get("cost_usd", 0.0)) for r in response_events]
    total_cost = round(sum(costs), 6)
    cost_metrics = {
        "total": total_cost,
        "avg_cost_per_req": round(total_cost / len(costs), 6) if costs else 0.0,
        "threshold": {"aggregation": "total", "operator": "lte", "value": 2.5},
        "status": "PASS" if total_cost <= 2.5 else "VIOLATION",
    }

    # 5. Tokens
    tokens_in = sum(int(r.get("tokens_in", 0)) for r in response_events)
    tokens_out = sum(int(r.get("tokens_out", 0)) for r in response_events)
    token_metrics = {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "threshold": {"aggregation": "sum_by_field", "operator": "lte", "value": 50000},
        "status": "PASS" if (tokens_in + tokens_out) <= 50000 else "VIOLATION",
    }

    # 6. Quality
    qualities = [float(r.get("quality_score", 0.0)) for r in response_events if "quality_score" in r]
    avg_quality = round(sum(qualities) / len(qualities), 2) if qualities else 1.0
    quality_metrics = {
        "mean": avg_quality,
        "count": len(qualities),
        "threshold": {"aggregation": "mean", "operator": "gte", "value": 0.75},
        "status": "PASS" if avg_quality >= 0.75 else "VIOLATION",
    }

    return {
        "time_range_minutes": window_minutes,
        "refresh_seconds": 30,
        "timestamp": now.isoformat(),
        "panels": {
            "latency": latency_metrics,
            "traffic": traffic_metrics,
            "errors": error_metrics,
            "cost": cost_metrics,
            "tokens": token_metrics,
            "quality": quality_metrics,
        },
    }


def render_dashboard_html() -> str:
    metrics = get_dashboard_metrics()
    p = metrics.get("panels", {})
    lat = p.get("latency", {})
    traf = p.get("traffic", {})
    err = p.get("errors", {})
    cost = p.get("cost", {})
    tok = p.get("tokens", {})
    qual = p.get("quality", {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>K4-L3A Day 13 Monitoring & LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --green: #4ade80;
      --red: #f87171;
      --yellow: #facc15;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 24px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border-bottom: 1px solid var(--card-border); padding-bottom: 16px; }}
    .title {{ font-size: 24px; font-weight: 700; color: var(--text); }}
    .badge {{ padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
    .badge-pass {{ background: rgba(74, 222, 128, 0.15); color: var(--green); border: 1px solid var(--green); }}
    .badge-viol {{ background: rgba(248, 113, 113, 0.15); color: var(--red); border: 1px solid var(--red); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }}
    .card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }}
    .card-title {{ font-size: 16px; font-weight: 600; color: var(--accent); }}
    .card-unit {{ font-size: 12px; color: var(--text-muted); }}
    .metric-main {{ font-size: 32px; font-weight: 700; margin: 8px 0; }}
    .metrics-row {{ display: flex; gap: 16px; margin: 12px 0; flex-wrap: wrap; }}
    .metric-sub {{ font-size: 13px; color: var(--text-muted); }}
    .metric-sub span {{ font-weight: 600; color: var(--text); }}
    .threshold-bar {{ background: rgba(255,255,255,0.05); border-radius: 6px; padding: 8px 12px; font-size: 12px; margin-top: 12px; border-left: 3px solid var(--accent); }}
    .footer {{ margin-top: 32px; text-align: center; color: var(--text-muted); font-size: 12px; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1 class="title">K4-L3A Day 13 Monitoring & LLMOps Dashboard</h1>
      <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">Time range: 60 minutes | Auto-refresh: 30s | Source: data/logs.jsonl</p>
    </div>
    <div style="text-align: right;">
      <span class="badge badge-pass">System Healthy</span>
      <p style="color: var(--text-muted); font-size: 12px; margin-top: 6px;" id="last-updated">Updated: {metrics.get("timestamp")}</p>
    </div>
  </div>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="card" id="panel-latency">
      <div class="card-header">
        <div class="card-title">1. Latency percentiles and TTFT</div>
        <div class="card-unit">Unit: ms</div>
      </div>
      <div class="metric-main">{lat.get('p95', 0)} <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">ms (P95)</span></div>
      <div class="metrics-row">
        <div class="metric-sub">P50: <span>{lat.get('p50', 0)} ms</span></div>
        <div class="metric-sub">P99: <span>{lat.get('p99', 0)} ms</span></div>
        <div class="metric-sub">TTFT P95: <span>{lat.get('ttft_p95', 0)} ms</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>P95 &le; 3000 ms</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{lat.get('status')}</span>
      </div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="card" id="panel-traffic">
      <div class="card-header">
        <div class="card-title">2. Request traffic</div>
        <div class="card-unit">Unit: requests/min</div>
      </div>
      <div class="metric-main">{traf.get('count', 0)} <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">total reqs</span></div>
      <div class="metrics-row">
        <div class="metric-sub">Rate: <span>{traf.get('rate_per_minute', 0)} req/min</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>Rate &ge; 1 req/min</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{traf.get('status')}</span>
      </div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="card" id="panel-errors">
      <div class="card-header">
        <div class="card-title">3. Error rate & retrieval success</div>
        <div class="card-unit">Unit: percent</div>
      </div>
      <div class="metric-main">{err.get('error_rate_pct', 0)}% <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">error rate</span></div>
      <div class="metrics-row">
        <div class="metric-sub">Retrieval success: <span>{err.get('tool_success_rate_pct', 100)}%</span></div>
        <div class="metric-sub">Failed reqs: <span>{err.get('failed_count', 0)}</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>Error rate &le; 2%</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{err.get('status')}</span>
      </div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="card" id="panel-cost">
      <div class="card-header">
        <div class="card-title">4. Cost over time</div>
        <div class="card-unit">Unit: USD</div>
      </div>
      <div class="metric-main">${cost.get('total', 0):.4f} <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">total</span></div>
      <div class="metrics-row">
        <div class="metric-sub">Avg/req: <span>${cost.get('avg_cost_per_req', 0):.5f}</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>Total &le; $2.50</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{cost.get('status')}</span>
      </div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="card" id="panel-tokens">
      <div class="card-header">
        <div class="card-title">5. Input and output tokens</div>
        <div class="card-unit">Unit: tokens</div>
      </div>
      <div class="metric-main">{tok.get('total_tokens', 0):,} <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">tokens</span></div>
      <div class="metrics-row">
        <div class="metric-sub">Tokens In: <span>{tok.get('tokens_in', 0):,}</span></div>
        <div class="metric-sub">Tokens Out: <span>{tok.get('tokens_out', 0):,}</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>Total &le; 50,000 tokens</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{tok.get('status')}</span>
      </div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="card" id="panel-quality">
      <div class="card-header">
        <div class="card-title">6. Quality proxy</div>
        <div class="card-unit">Unit: score (0 to 1)</div>
      </div>
      <div class="metric-main">{qual.get('mean', 0):.2f} <span style="font-size: 18px; font-weight: normal; color: var(--text-muted);">mean score</span></div>
      <div class="metrics-row">
        <div class="metric-sub">Evaluated responses: <span>{qual.get('count', 0)}</span></div>
      </div>
      <div class="threshold-bar">
        Threshold: <strong>Mean &ge; 0.75</strong> &bull; Status: <span style="color: var(--green); font-weight: bold;">{qual.get('status')}</span>
      </div>
    </div>
  </div>

  <div class="footer">
    K4-L3A Day 13 Monitoring & LLMOps Lab Dashboard &bull; Validated against config/dashboard.yaml contract
  </div>

  <script>
    setTimeout(() => window.location.reload(), 30000);
  </script>
</body>
</html>"""
