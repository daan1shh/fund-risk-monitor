import json
from pathlib import Path

import pandas as pd
from scipy import stats
from scipy.special import xlogy

from riskmon.metrics import historical_var
from riskmon.models import normal_var

BACKTEST_FILE = Path(__file__).resolve().parent.parent / "reports" / "backtest.json"
MODELS = ["Historical simulation", "Parametric normal"]


def rolling_var(port: pd.Series, window: int, lookback: int, confidence: float) -> pd.DataFrame:
    """One day VaR from each model for each of the last window days, fitted on prior data only."""
    rows = []
    for i in range(len(port) - window, len(port)):
        history = port.iloc[i - lookback:i]
        rows.append({
            "date": port.index[i],
            "pnl": port.iloc[i],
            "Historical simulation": historical_var(history, confidence),
            "Parametric normal": normal_var(history, confidence),
        })
    return pd.DataFrame(rows).set_index("date")


def traffic_light(exceptions: int) -> str:
    """Basel zone for 250 days at 99 percent."""
    if exceptions <= 4:
        return "green"
    if exceptions <= 9:
        return "amber"
    return "red"


def kupiec(exceptions: int, n: int, p: float) -> float:
    """Kupiec proportion of failures likelihood ratio, chi squared with one degree of freedom."""
    x = exceptions
    # xlogy treats 0 * ln(0) as 0, which is the right limit when there are no exceptions
    restricted = xlogy(n - x, 1 - p) + xlogy(x, p)
    unrestricted = xlogy(n - x, 1 - x / n) + xlogy(x, x / n)
    return float(-2 * restricted + 2 * unrestricted)


def compare_models(var: pd.DataFrame, confidence: float) -> list[dict]:
    """Exception count, traffic light and Kupiec result per model."""
    n, p = len(var), 1 - confidence
    critical = stats.chi2.ppf(0.95, df=1)
    table = []
    for model in MODELS:
        exceptions = int((-var["pnl"] > var[model]).sum())
        lr = kupiec(exceptions, n, p)
        table.append({
            "model": model,
            "exceptions": exceptions,
            "expected": n * p,
            "zone": traffic_light(exceptions),
            "kupiec": lr,
            "passed": bool(lr < critical),
        })
    return table


def print_table(table: list[dict]):
    print(f"{'model':24}{'exceptions':>11}{'expected':>10}{'zone':>8}{'kupiec':>9}  result")
    for row in table:
        print(f"{row['model']:24}{row['exceptions']:>11}{row['expected']:>10.1f}{row['zone']:>8}"
              f"{row['kupiec']:>9.2f}  {'pass' if row['passed'] else 'fail'}")


def save(var: pd.DataFrame, table: list[dict], confidence: float):
    payload = {
        "confidence": confidence,
        "window": len(var),
        "models": table,
        "dates": [d.strftime("%Y-%m-%d") for d in var.index],
        "pnl": var["pnl"].round(6).tolist(),
        "var": {m: var[m].round(6).tolist() for m in MODELS},
    }
    BACKTEST_FILE.parent.mkdir(exist_ok=True)
    BACKTEST_FILE.write_text(json.dumps(payload, indent=1))


def load() -> dict:
    return json.loads(BACKTEST_FILE.read_text())
