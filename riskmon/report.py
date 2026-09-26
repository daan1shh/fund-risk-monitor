from pathlib import Path

from riskmon.limits import check_limits, largest_moves, overnight_moves
from riskmon.metrics import LABELS, RATIOS, format_value

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"


def format_move(metric, change):
    if metric in RATIOS:
        return f"{change:+.3f}x"
    # fractions of nav move in basis points, a percent sign here would read as relative
    return f"{change * 1e4:+.1f}bp"


def write_morning_report(as_of, nav: float, today: dict, yesterday: dict,
                         limits: dict, verbose: bool = False) -> Path:
    """Write reports/YYYY-MM-DD.md showing only what needs attention, and print a short version."""
    rows = check_limits(today, limits)
    flagged = [r for r in rows if r["status"] != "ok"]
    moves = overnight_moves(today, yesterday)
    breaches = sum(r["status"] == "breach" for r in flagged)
    ambers = len(flagged) - breaches
    date = as_of.strftime("%Y-%m-%d")

    md = [f"# Morning risk report {date}", "",
          f"NAV EUR {nav:,.0f}  |  as of {date}  |  {breaches} breach, {ambers} amber", ""]
    console = [f"{date}  NAV EUR {nav:,.0f}  {breaches} breach, {ambers} amber"]

    if flagged:
        md += ["## Limits needing attention", "",
               "| Status | Metric | Value | Limit | Utilisation | Overnight |",
               "|---|---|--:|--:|--:|--:|"]
        for r in flagged:
            m = r["metric"]
            md.append(f"| {r['status'].upper()} | {LABELS[m]} | {format_value(m, r['value'])} | "
                      f"{format_value(m, r['hard'])} | {r['utilisation']:.0%} | {format_move(m, moves[m])} |")
            console.append(f"  {r['status'].upper():7}{LABELS[m]}  {format_value(m, r['value'])} "
                           f"vs {format_value(m, r['hard'])}  ({r['utilisation']:.0%} used, "
                           f"{format_move(m, moves[m])} overnight)")
        md.append("")
    else:
        md += ["All limits within thresholds, nothing to action.", ""]
        console.append("  all limits within thresholds, nothing to action")

    md += ["## Largest overnight moves", ""]
    console.append("  largest moves:")
    for m in largest_moves(today, yesterday):
        line = f"{LABELS[m]} {format_value(m, yesterday[m])} to {format_value(m, today[m])} ({format_move(m, moves[m])})"
        md.append(f"- {line}")
        console.append(f"    {line}")
    md.append("")

    if verbose:
        md += ["## All metrics", "", "| Metric | Value | Previous | Change |", "|---|--:|--:|--:|"]
        console.append("  all metrics:")
        for m, value in today.items():
            md.append(f"| {LABELS[m]} | {format_value(m, value)} | "
                      f"{format_value(m, yesterday[m])} | {format_move(m, moves[m])} |")
            console.append(f"    {LABELS[m]:28}{format_value(m, value):>9}{format_move(m, moves[m]):>9}")
        md.append("")

    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"{date}.md"
    path.write_text("\n".join(md))
    print("\n".join(console))
    print(f"written to {path.relative_to(REPORT_DIR.parent)}")
    return path
