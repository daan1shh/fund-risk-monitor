import numpy as np
from scipy import stats


def normal_var(returns, confidence: float) -> float:
    """Next day VaR as mu + z * sigma under a normal distribution."""
    z = stats.norm.ppf(1 - confidence)
    return float(-(np.mean(returns) + z * np.std(returns, ddof=1)))
