import math

import pytest

from riskmon.backtest import kupiec, traffic_light


def test_kupiec_against_hand_calculation():
    n, x, p = 250, 5, 0.01
    restricted = (n - x) * math.log(1 - p) + x * math.log(p)
    unrestricted = (n - x) * math.log(1 - x / n) + x * math.log(x / n)
    assert kupiec(x, n, p) == pytest.approx(-2 * restricted + 2 * unrestricted)
    # 245 ln 0.99 + 5 ln 0.01 = -25.4882, 245 ln 0.98 + 5 ln 0.02 = -24.5098
    assert kupiec(x, n, p) == pytest.approx(1.957, abs=1e-3)


def test_kupiec_with_no_exceptions_rejects_an_overcautious_model():
    # only the restricted term survives, -2 * 250 * ln 0.99
    assert kupiec(0, 250, 0.01) == pytest.approx(5.025, abs=1e-3)
    assert kupiec(0, 250, 0.01) > 3.841


def test_kupiec_is_zero_when_exceptions_match_expectation():
    assert kupiec(5, 500, 0.01) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("exceptions, zone", [(0, "green"), (4, "green"), (5, "amber"),
                                              (9, "amber"), (10, "red")])
def test_traffic_light_boundaries(exceptions, zone):
    assert traffic_light(exceptions) == zone
