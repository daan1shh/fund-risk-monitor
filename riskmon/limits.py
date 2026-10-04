TRACKED = ["absolute_var", "relative_var", "es_20d", "commitment_leverage"]
SEVERITY = {"ok": 0, "amber": 1, "breach": 2}


def classify(value: float, hard: float, amber: float) -> str:
    """ok, amber or breach against one limit."""
    # sitting exactly on a limit is still within it, ucits wording is must not exceed
    if value > hard:
        return "breach"
    if value > amber:
        return "amber"
    return "ok"


def check_limits(today: dict, limits: dict) -> list[dict]:
    """Status and utilisation of every tracked limit."""
    rows = []
    for metric in TRACKED:
        hard, amber = limits[metric]["hard"], limits[metric]["amber"]
        value = today[metric]
        rows.append({
            "metric": metric,
            "value": value,
            "hard": hard,
            "amber": amber,
            "utilisation": value / hard,
            "status": classify(value, hard, amber),
        })
    return rows


def overnight_moves(today: dict, yesterday: dict) -> dict:
    return {m: today[m] - yesterday[m] for m in today}


def largest_moves(today: dict, yesterday: dict, n: int = 3) -> list[str]:
    # ranked by relative change, since the metrics mix fractions of nav and ratios
    relative = {m: abs(today[m] / yesterday[m] - 1) for m in today if yesterday[m]}
    return sorted(relative, key=relative.get, reverse=True)[:n]


def worst_status(rows: list[dict]) -> str:
    return max((r["status"] for r in rows), key=SEVERITY.get, default="ok")
