import math

import numpy as np
import pytest

from riskmon.limits import classify
from riskmon.metrics import commitment_leverage, historical_var, scale_var

RETURNS = np.array([0.02, -0.05, 0.01, -0.01, 0.04, -0.03, 0.0, 0.05, -0.02, 0.03])


def test_historical_var_matches_hand_quantile():
    # sorted: -0.05, -0.03, ... the 10% quantile sits 0.9 of the way from the
    # 1st to the 2nd order statistic under linear interpolation
    expected = -(-0.05 + 0.9 * (-0.03 - -0.05))
    assert historical_var(RETURNS, 0.90) == pytest.approx(expected)
    assert historical_var(RETURNS, 0.90) == pytest.approx(0.032)


def test_square_root_of_time_scaling():
    assert scale_var(0.01, 20) == pytest.approx(0.01 * math.sqrt(20))
    assert scale_var(0.01, 1) == pytest.approx(0.01)


@pytest.mark.parametrize("value, status", [
    (0.20, "amber"),
    (0.2000001, "breach"),
    (0.16, "ok"),
    (0.1600001, "amber"),
])
def test_classification_on_the_threshold_is_within(value, status):
    assert classify(value, hard=0.20, amber=0.16) == status


def test_commitment_leverage_without_overlay_is_gross_weight():
    holdings = {"A": 0.6, "B": 0.4}
    assert commitment_leverage(holdings) == pytest.approx(1.0)
    assert commitment_leverage(holdings, []) == pytest.approx(1.0)


def test_commitment_leverage_adds_overlay_notional_either_direction():
    holdings = {"A": 0.6, "B": 0.4}
    overlay = [
        {"instrument": "long future", "notional_pct": 0.20, "direction": "long"},
        {"instrument": "short future", "notional_pct": 0.10, "direction": "short"},
    ]
    assert commitment_leverage(holdings, overlay) == pytest.approx(1.30)
