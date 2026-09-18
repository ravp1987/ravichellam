"""Render the analysis results (see analyze.py) as a single self-contained HTML report."""
from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analyze import run_all

OUT_PATH = Path(__file__).parent / "report.html"

COLORS = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#84CC16"]


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _bar_chart(df: pd.DataFrame, x: str, y: str, title: str, top_n: int = 12) -> str:
    d = df.head(top_n)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(d))))
    ax.barh(d[x][::-1], d[y][::-1], color=COLORS[0])
    ax.set_title(title)
    ax.set_xlabel(y)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _pie_chart(df: pd.DataFrame, labels: str, values: str, title: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(df[values], labels=df[labels], autopct="%1.0f%%", colors=COLORS)
    ax.set_title(title)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _df_to_html_table(df: pd.DataFrame, columns: list[str] | None = None, fmt: dict | None = None) -> str:
    if df.empty:
        return "<p class='muted'>No data available.</p>"
    d = df[columns] if columns else df
    if fmt:
        d = d.copy()
        for col, f in fmt.items():
            if col in d.columns:
                d[col] = d[col].map(f)
    return d.to_html(index=False, classes="table", border=0)


def build_report() -> Path:
    results = run_all()
    apps_df = results["apps_df"]
    spend = results["spend"]
    utilization = results["utilization"]
    shadow = results["shadow_it"]
    inventory = results["inventory"]

    money = lambda v: f"${v:,.0f}"

    sections = []

    sections.append(
        f"""
        <div class="kpis">
          <div class="kpi"><div class="kpi-value">{inventory['total_apps']}</div><div class="kpi-label">Apps discovered</div></div>
          <div class="kpi"><div class="kpi-value">{money(spend['total_spend'])}</div><div class="kpi-label">Total annual SaaS spend</div></div>
          <div class="kpi"><div class="kpi-value">{len(shadow)}</div><div class="kpi-label">Unmanaged / shadow IT apps</div></div>
          <div class="kpi"><div class="kpi-value">{money(utilization['wasted_spend'].sum()) if not utilization.empty else '$0'}</div><div class="kpi-label">Wasted spend (unused licenses)</div></div>
        </div>
        """
    )

    if not spend["by_app"].empty:
        img = _bar_chart(spend["by_app"], "name", "spend", "Top apps by annual spend")
        sections.append(f"<h2>Spend by app</h2><img src='data:image/png;base64,{img}'/>")
        sections.append(_df_to_html_table(spend["by_app"], fmt={"spend": money}))

    if not spend["by_category"].empty:
        img = _pie_chart(spend["by_category"].head(8), "category", "spend", "Spend by category")
        sections.append(f"<h2>Spend by category</h2><img src='data:image/png;base64,{img}'/>")

    if not utilization.empty:
        img = _bar_chart(
            utilization.sort_values("wasted_spend", ascending=False), "name", "wasted_spend",
            "Wasted spend from unused licenses (top offenders)",
        )
        sections.append(f"<h2>License utilization</h2><img src='data:image/png;base64,{img}'/>")
        sections.append(
            _df_to_html_table(
                utilization,
                columns=["name", "licenses_total", "licenses_active", "unused_licenses", "utilization_pct", "wasted_spend"],
                fmt={"wasted_spend": money, "utilization_pct": lambda v: f"{v}%"},
            )
        )

    if not shadow.empty:
        sections.append("<h2>Shadow IT / unmanaged apps</h2>")
        sections.append(_df_to_html_table(shadow, columns=["name", "category", "state", "spend"], fmt={"spend": money}))

    if not inventory["by_category"].empty:
        img = _bar_chart(inventory["by_category"].rename(columns={"size": "count"}), "category", "count", "App inventory by category")
        sections.append(f"<h2>App inventory</h2><img src='data:image/png;base64,{img}'/>")

    body = "\n".join(sections)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Torii SaaS Analysis</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; max-width: 960px; margin: 40px auto; color: #1f2937; }}
  h1 {{ margin-bottom: 0; }}
  .subtitle {{ color: #6b7280; margin-top: 4px; }}
  h2 {{ margin-top: 40px; border-top: 1px solid #e5e7eb; padding-top: 24px; }}
  img {{ max-width: 100%; }}
  .kpis {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 24px 0; }}
  .kpi {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 20px; flex: 1; min-width: 180px; }}
  .kpi-value {{ font-size: 28px; font-weight: 700; }}
  .kpi-label {{ color: #6b7280; font-size: 13px; margin-top: 4px; }}
  table.table {{ border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 14px; }}
  table.table th, table.table td {{ padding: 6px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
  .muted {{ color: #6b7280; }}
</style></head>
<body>
  <h1>Torii SaaS Analysis</h1>
  <div class="subtitle">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
  {body}
</body></html>"""

    OUT_PATH.write_text(html)
    return OUT_PATH


if __name__ == "__main__":
    path = build_report()
    print(f"Report written to {path}")
