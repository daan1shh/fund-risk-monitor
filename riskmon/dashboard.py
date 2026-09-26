from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from riskmon.limits import TRACKED, check_limits, largest_moves, worst_status
from riskmon.metrics import LABELS, format_value, snapshot
from riskmon.report import format_move

DASHBOARD_FILE = Path(__file__).resolve().parent.parent / "docs" / "index.html"
HISTORY_DAYS = 252

STATUS_WORDS = {"ok": "within limits", "amber": "amber, approaching a limit", "breach": "breach"}
# series colours only, so green, amber and red stay reserved for status
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED, GRID = "#0b0b0b", "#6b6a65", "#e1e0d9"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

CSS = """
:root { --ink: #0b0b0b; --muted: #6b6a65; --line: #e1e0d9; --bg: #ffffff; --accent: #2a78d6;
  --ok: #0ca30c; --amber: #fab219; --breach: #d03b3b;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 20px 40px; }
section { margin-top: 36px; }
h2 { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  color: var(--muted); margin: 0 0 10px; }
.status { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 24px;
  padding: 14px 18px; border: 1px solid var(--line); border-left-width: 8px; }
.status.ok { border-left-color: var(--ok); }
.status.amber { border-left-color: var(--amber); }
.status.breach { border-left-color: var(--breach); }
.status .fund { font-size: 16px; font-weight: 600; }
.status .meta { color: var(--muted); }
.state { margin-left: auto; font-size: 18px; font-weight: 700; padding: 4px 12px; }
.state.ok { background: var(--ok); color: #000; }
.state.amber { background: var(--amber); color: #000; }
.state.breach { background: var(--breach); color: #fff; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.tile { border: 1px solid var(--line); padding: 14px 16px; }
.tile .name { color: var(--muted); }
.tile .value { font-size: 26px; font-weight: 600; margin: 4px 0 2px; }
.tile .sub { display: flex; justify-content: space-between; color: var(--muted);
  font-family: var(--mono); font-size: 12px; }
.tile .word { font-family: inherit; font-weight: 600; color: var(--ink); }
.bar { position: relative; height: 10px; background: #f0efec; margin: 10px 0 6px; }
.bar .fill { position: absolute; left: 0; top: 0; bottom: 0; }
.fill.ok { background: var(--ok); } .fill.amber { background: var(--amber); }
.fill.breach { background: var(--breach); }
.bar .tick { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--ink); }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 4px 10px; border-bottom: 1px solid var(--line); text-align: left; }
th { font-weight: 600; color: var(--muted); font-size: 12px; }
td.num, th.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }
.table-wrap { overflow-x: auto; }
.movers li { margin: 2px 0; }
.movers { padding-left: 18px; margin: 0; }
.mono { font-family: var(--mono); }
.note { color: var(--muted); margin: 6px 0 0; }
footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 12px; }
"""


def limit_history(returns: pd.DataFrame, portfolio: dict, limits: dict) -> pd.DataFrame:
    """Utilisation and status of every tracked limit on each of the last HISTORY_DAYS dates."""
    rows = []
    for as_of in returns.index[-HISTORY_DAYS:]:
        for row in check_limits(snapshot(returns, portfolio, limits, as_of), limits):
            rows.append({"date": as_of, **row})
    return pd.DataFrame(rows)


def _layout(fig, height, yaxis_title):
    fig.update_layout(
        height=height, margin=dict(l=56, r=190, t=10, b=36), font=dict(family=FONT, size=12, color=INK),
        paper_bgcolor="white", plot_bgcolor="white", hovermode="x unified",
        legend=dict(orientation="h", y=-0.14, x=0), yaxis_title=yaxis_title,
    )
    fig.update_xaxes(showgrid=False, linecolor="#c3c2b7", tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def _end_label(fig, y, text, color=INK, yanchor="middle"):
    fig.add_annotation(x=1, xref="paper", y=y, text=text, showarrow=False, xanchor="left", xshift=6,
                       yanchor=yanchor, font=dict(color=color, size=11))


def utilisation_chart(history: pd.DataFrame, limits: dict) -> go.Figure:
    fig = go.Figure()
    for metric, color in zip(TRACKED, SERIES):
        series = history[history["metric"] == metric]
        fig.add_trace(go.Scatter(x=series["date"], y=series["utilisation"] * 100, name=LABELS[metric],
                                 line=dict(color=color, width=2),
                                 hovertemplate="%{y:.1f}%<extra>" + LABELS[metric] + "</extra>"))
        _end_label(fig, series["utilisation"].iloc[-1] * 100, LABELS[metric])
    fig.add_hline(y=100, line=dict(color=INK, width=1.5))
    _end_label(fig, 100, "hard limit 100%")
    # amber sits at a different share of the hard limit for each limit, so draw each distinct level
    ambers = {}
    for metric in TRACKED:
        ambers.setdefault(round(limits[metric]["amber"] / limits[metric]["hard"] * 100), []).append(metric)
    for i, (level, metrics) in enumerate(sorted(ambers.items())):
        fig.add_hline(y=level, line=dict(color=INK, width=1, dash="dash"))
        names = "leverage" if metrics == ["commitment_leverage"] else "VaR limits"
        # alternate above and below the line so neighbouring amber levels do not collide
        _end_label(fig, level, f"amber {level}%, {names}", MUTED, "top" if i % 2 == 0 else "bottom")
    fig.update_xaxes(range=[history["date"].min(), history["date"].max()])
    fig.update_yaxes(range=[0, max(110, history["utilisation"].max() * 105)], ticksuffix="%")
    return _layout(fig, 340, "utilisation of hard limit")


def backtest_chart(bt: dict) -> go.Figure:
    dates = pd.to_datetime(bt["dates"])
    pnl = pd.Series(bt["pnl"], index=dates) * 100
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=pnl, name="realised daily P&L", marker_color="#c3c2b7",
                         hovertemplate="%{y:.2f}%<extra>P&L</extra>"))
    broken = pd.Series("", index=dates)
    for (model, var), color in zip(bt["var"].items(), SERIES):
        var = pd.Series(var, index=dates) * 100
        # plotted as a loss threshold, so an exception is a bar reaching below its line
        fig.add_trace(go.Scatter(x=dates, y=-var, name=model, line=dict(color=color, width=2),
                                 hovertemplate="%{y:.2f}%<extra>" + model + "</extra>"))
        broken[pnl < -var] += model + "<br>"
    hits = broken[broken != ""]
    fig.add_trace(go.Scatter(x=hits.index, y=pnl[hits.index], mode="markers", name="exception",
                             marker=dict(symbol="x", size=10, color=INK, line=dict(width=1)),
                             customdata=hits.values,
                             hovertemplate="exception against<br>%{customdata}<extra></extra>"))
    fig.update_yaxes(ticksuffix="%")
    return _layout(fig, 360, "daily return, % of NAV")


def _status_bar(name, nav, as_of, state):
    return (f'<div class="status {state}"><span class="fund">{escape(name)}</span>'
            f'<span class="meta">NAV EUR {nav:,.0f}</span><span class="meta">as of {as_of}</span>'
            f'<span class="state {state}">{STATUS_WORDS[state]}</span></div>')


def _tile(row):
    m = row["metric"]
    fill = min(row["utilisation"], 1) * 100
    tick = row["amber"] / row["hard"] * 100
    return (f'<div class="tile"><div class="name">{LABELS[m]}</div>'
            f'<div class="value">{format_value(m, row["value"])}</div>'
            f'<div class="bar"><div class="fill {row["status"]}" style="width:{fill:.1f}%"></div>'
            f'<div class="tick" style="left:{tick:.1f}%" title="amber threshold"></div></div>'
            f'<div class="sub"><span>{row["utilisation"]:.0%} of limit {format_value(m, row["hard"])}</span>'
            f'<span class="word">{STATUS_WORDS[row["status"]]}</span></div></div>')


def _movers(today, yesterday):
    items = []
    for m in largest_moves(today, yesterday):
        direction = "up" if today[m] > yesterday[m] else "down"
        items.append(f"<li>{LABELS[m]} {direction} <span class='mono'>{format_move(m, today[m] - yesterday[m])}</span>, "
                     f"<span class='mono'>{format_value(m, yesterday[m])}</span> to "
                     f"<span class='mono'>{format_value(m, today[m])}</span></li>")
    return f'<ul class="movers">{"".join(items)}</ul>'


def _holdings_table(portfolio):
    names, ref = portfolio.get("names", {}), portfolio["reference"]
    rows = "".join(
        f"<tr><td class='mono'>{t}</td><td>{escape(names.get(t, ''))}</td><td class='num'>{w:.0%}</td>"
        f"<td class='num'>{ref.get(t, 0):.0%}</td><td class='num'>{w - ref.get(t, 0):+.0%}</td></tr>"
        for t, w in portfolio["holdings"].items())
    # the overlay is notional exposure on top of fully invested holdings, so it has no reference weight
    rows += "".join(
        f"<tr><td></td><td>{escape(leg['instrument'])}, synthetic {leg['direction']} overlay</td>"
        f"<td class='num'>{leg['notional_pct']:.0%}</td><td class='num'></td><td class='num'></td></tr>"
        for leg in portfolio.get("overlay") or [])
    return ("<div class='table-wrap'><table><tr><th>Ticker</th><th>Holding</th><th class='num'>Fund</th>"
            f"<th class='num'>Reference</th><th class='num'>Active</th></tr>{rows}</table></div>")


def _backtest_table(bt):
    rows = "".join(
        f"<tr><td>{r['model']}</td><td class='num'>{r['exceptions']}</td><td class='num'>{r['expected']:.1f}</td>"
        f"<td>{r['zone']}</td><td class='num'>{r['kupiec']:.2f}</td><td>{'pass' if r['passed'] else 'fail'}</td></tr>"
        for r in bt["models"])
    return ("<div class='table-wrap'><table><tr><th>Model</th><th class='num'>Exceptions</th>"
            "<th class='num'>Expected</th><th>Traffic light</th><th class='num'>Kupiec LR</th>"
            f"<th>Kupiec at 95%</th></tr>{rows}</table></div>")


def _exception_log(history):
    flagged = history[history["status"] != "ok"].sort_values("date", ascending=False)
    if flagged.empty:
        return f"<p>No amber or breach on any tracked limit in the last {HISTORY_DAYS} business days.</p>"
    rows = "".join(
        f"<tr><td class='num'>{r.date:%Y-%m-%d}</td><td>{LABELS[r.metric]}</td><td>{r.status}</td>"
        f"<td class='num'>{format_value(r.metric, r.value)}</td><td class='num'>{format_value(r.metric, r.hard)}</td></tr>"
        for r in flagged.itertuples())
    return ("<div class='table-wrap'><table><tr><th class='num'>Date</th><th>Metric</th><th>Status</th>"
            f"<th class='num'>Value</th><th class='num'>Limit</th></tr>{rows}</table></div>")


def build_dashboard(returns: pd.DataFrame, portfolio: dict, limits: dict, bt: dict) -> Path:
    """Write docs/index.html as one file with plotly inlined, readable offline."""
    as_of, previous = returns.index[-1], returns.index[-2]
    today = snapshot(returns, portfolio, limits, as_of)
    yesterday = snapshot(returns, portfolio, limits, previous)
    rows = check_limits(today, limits)
    history = limit_history(returns, portfolio, limits)

    chart_config = {"displayModeBar": False, "responsive": True}
    util_html = utilisation_chart(history, limits).to_html(
        full_html=False, include_plotlyjs=True, config=chart_config)
    bt_html = backtest_chart(bt).to_html(full_html=False, include_plotlyjs=False, config=chart_config)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Risk monitor {as_of:%Y-%m-%d}</title>
<style>{CSS}</style></head><body><main>
{_status_bar(portfolio["name"], portfolio["nav"], f"{as_of:%Y-%m-%d}", worst_status(rows))}
<section><h2>Limits</h2><div class="tiles">{"".join(_tile(r) for r in rows)}</div>
<p class="note">Bar shows utilisation of the hard limit, the black tick marks the amber threshold.</p></section>
<section><h2>Largest overnight moves, since {previous:%Y-%m-%d}</h2>{_movers(today, yesterday)}</section>
<section><h2>Holdings, weight of NAV</h2>{_holdings_table(portfolio)}
<p class="note">Reference portfolio for relative VaR is 60% MSCI World and 40% Eurozone government bonds. Prices are daily Xetra closes. The overlay counts toward commitment leverage only, VaR is computed on the five ETFs.</p></section>
<section><h2>Limit utilisation, last {HISTORY_DAYS} business days</h2>{util_html}</section>
<section><h2>VaR model backtest, 1 day {bt["confidence"]:.0%}, last {bt["window"]} days</h2>
{_backtest_table(bt)}
<p class="note">Expected exceptions at {bt["confidence"]:.0%} over {bt["window"]} days is {bt["window"] * (1 - bt["confidence"]):.1f}.
Kupiec fails either way, too many exceptions or too few. GARCH refitted every {bt["refit_every"]} days.</p>
{bt_html}</section>
<section><h2>Exception log</h2>{_exception_log(history)}</section>
<footer>Generated {stamp} from public market data (Yahoo Finance ETF prices) for a personal learning project.</footer>
</main></body></html>
"""
    DASHBOARD_FILE.parent.mkdir(exist_ok=True)
    DASHBOARD_FILE.write_text(html)
    return DASHBOARD_FILE
