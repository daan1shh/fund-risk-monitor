import numpy as np
import pandas as pd

TRADING_DAYS = 252

LABELS = {
    "absolute_var": "Absolute VaR 20d 99%",
    "relative_var": "Relative VaR",
    "commitment_leverage": "Commitment leverage",
    "ref_var": "Reference VaR 20d 99%",
    "var_1d": "VaR 1d 99%",
    "es_20d": "Expected shortfall 20d 99%",
    "volatility": "Volatility, annualised",
    "tracking_error": "Tracking error",
    "max_drawdown": "Max drawdown, lookback",
}
RATIOS = {"relative_var", "commitment_leverage"}


def portfolio_returns(returns: pd.DataFrame, weights: dict) -> pd.Series:
    """Daily portfolio return as the weighted sum of constituent returns."""
    w = pd.Series(weights, dtype=float)
    # fixed weights means the fund is treated as rebalanced to target every day
    return returns[w.index] @ w


def historical_var(returns, confidence: float) -> float:
    """One day VaR as a positive fraction of NAV, the empirical loss quantile."""
    return float(-np.quantile(returns, 1 - confidence))


def scale_var(var_1d: float, holding_period: int) -> float:
    """Square root of time scaling from one day to the holding period."""
    # assumes iid returns, which they are not because volatility clusters
    return var_1d * np.sqrt(holding_period)


def expected_shortfall(returns, confidence: float) -> float:
    """One day ES as a positive fraction of NAV, the mean loss beyond the VaR quantile."""
    returns = np.asarray(returns)
    cutoff = np.quantile(returns, 1 - confidence)
    return float(-returns[returns <= cutoff].mean())


def annualised_vol(returns) -> float:
    return float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS))


def tracking_error(port: pd.Series, ref: pd.Series) -> float:
    """Annualised standard deviation of the active return."""
    return annualised_vol(port - ref)


def commitment_leverage(holdings: dict, overlay: list | None = None) -> float:
    """Gross notional of holdings plus derivative overlay, over NAV."""
    # weights are already fractions of nav, so dividing by nav is implicit
    gross = sum(abs(w) for w in holdings.values())
    gross += sum(abs(leg["notional_pct"]) for leg in overlay or [])
    return float(gross)


def max_drawdown(returns) -> float:
    """Largest peak to trough fall in cumulative value, as a positive fraction."""
    value = np.cumprod(1 + np.asarray(returns))
    peak = np.maximum.accumulate(value)
    return float(-(value / peak - 1).min())


def snapshot(returns: pd.DataFrame, portfolio: dict, limits: dict, as_of) -> dict:
    """Every monitored metric using only data up to and including as_of."""
    window = returns.loc[:as_of].tail(limits["var_lookback_days"])
    conf, horizon = limits["var_confidence"], limits["holding_period_days"]
    port = portfolio_returns(window, portfolio["holdings"])
    ref = portfolio_returns(window, portfolio["reference"])

    var_1d = historical_var(port, conf)
    abs_var = scale_var(var_1d, horizon)
    ref_var = scale_var(historical_var(ref, conf), horizon)
    return {
        "absolute_var": abs_var,
        "relative_var": abs_var / ref_var,
        "commitment_leverage": commitment_leverage(portfolio["holdings"], portfolio.get("overlay")),
        "ref_var": ref_var,
        "var_1d": var_1d,
        "es_20d": scale_var(expected_shortfall(port, conf), horizon),
        "volatility": annualised_vol(port),
        "tracking_error": tracking_error(port, ref),
        "max_drawdown": max_drawdown(port),
    }


def format_value(metric: str, value: float) -> str:
    return f"{value:.4f}x" if metric in RATIOS else f"{value:.2%}"
