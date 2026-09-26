import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats

from riskmon.metrics import historical_var

# arch's optimiser is happier with returns in percent than in fractions
SCALE = 100


def normal_var(returns, confidence: float) -> float:
    """Next day VaR as mu + z * sigma under a normal distribution."""
    z = stats.norm.ppf(1 - confidence)
    return float(-(np.mean(returns) + z * np.std(returns, ddof=1)))


def _garch(returns):
    # student t innovations, because a normal garch still underfits the tails
    return arch_model(np.asarray(returns) * SCALE, mean="Constant", vol="GARCH",
                      p=1, q=1, dist="t")


def fit_garch(returns) -> pd.Series:
    """Maximum likelihood GARCH(1,1) parameters on the window."""
    return _garch(returns).fit(disp="off").params


def _filter(returns, params):
    # fixed parameters, so this only runs the variance recursion over the window
    fixed = _garch(returns).fix(params)
    sigma_next = np.sqrt(fixed.forecast(horizon=1, reindex=False).variance.iloc[-1, 0])
    return fixed, sigma_next


def garch_var(returns, confidence: float, params: pd.Series) -> float:
    """Next day VaR from the one step GARCH sigma forecast and a standardised t quantile."""
    _, sigma_next = _filter(returns, params)
    nu = params["nu"]
    # the t quantile has variance nu/(nu-2), rescale so sigma keeps meaning sigma
    q = stats.t.ppf(1 - confidence, nu) * np.sqrt((nu - 2) / nu)
    return float(-(params["mu"] + q * sigma_next) / SCALE)


def fhs_var(returns, confidence: float, params: pd.Series) -> float:
    """Filtered historical simulation, empirical quantile of GARCH standardised residuals rescaled by tomorrow's sigma."""
    fixed, sigma_next = _filter(returns, params)
    # residuals carry the shape of the tails, garch carries today's volatility level
    q = np.quantile(fixed.std_resid, 1 - confidence)
    return float(-(params["mu"] + q * sigma_next) / SCALE)
