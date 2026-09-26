# UCITS Risk Monitor

A small daily risk monitor for a UCITS style fund, and a validation of the VaR model behind it.

The latest dashboard is at [daan1shh.github.io/ucits-risk-monitor](https://daan1shh.github.io/ucits-risk-monitor/) and opens in any browser.

The monitored fund holds five Xtrackers ETFs, 45% MSCI World, 15% MSCI Emerging Markets, 25% Eurozone government bonds, 10% EUR high yield and 5% in an overnight rate ETF as cash, plus a synthetic 20% EURO STOXX 50 futures overlay. The monitor computes the fund's 20 day 99% VaR, relative VaR against a 60/40 reference portfolio and commitment leverage, and checks each one against the UCITS hard limits and an internal amber threshold below them. Every morning it writes a short report that lists only what needs attention, meaning anything amber or in breach plus the three metrics that moved most overnight. The full metrics table is there if you ask for it, but the point of the report is that it fits on one screen.

The second half asks whether the VaR number can be trusted. It backtests four one day VaR estimators over the last 250 days (historical simulation, parametric normal, GARCH(1,1) with Student t innovations, and filtered historical simulation), counts the days where the realised loss beat the forecast, and scores each model with the Basel traffic light and the Kupiec proportion of failures test.

I built it to understand the daily cycle of a liquid investment risk team before starting a risk management internship. It uses only public market data and is not modelled on any firm's internal tooling.

## Running it

```
pip install -r requirements.txt
python -m riskmon.cli monitor              # morning report for the latest date
python -m riskmon.cli monitor --verbose    # plus the full metrics table
python -m riskmon.cli backtest             # model comparison, writes reports/backtest.json
python -m riskmon.cli dashboard            # rebuilds docs/index.html
python -m riskmon.cli refresh              # force a full price redownload
python -m pytest
```

The first run downloads about nine years of daily prices from Yahoo Finance and caches them as parquet in `data/cache/`. Later runs only fetch the last few days. Portfolio weights and NAV live in `config/portfolio.yaml` and every limit lives in `config/limits.yaml`, so nothing in the risk code is hardcoded.

`docs/index.html` is a single self contained page with the charting library inlined, so it opens offline on a double click. It shows the overall limit status first, then limit utilisation, the utilisation history over the last year, the backtest and a log of every amber or breach.

## What the backtest shows

Over the most recent 250 days markets were calm and the four models are hard to tell apart. Parametric normal, GARCH and filtered HS each have two exceptions against 2.5 expected, and historical simulation has none, which Kupiec rejects as too conservative. The differences show up once the window includes stress. Across 1,800 days from August 2019, parametric normal has 38 exceptions against 18 expected and fails Kupiec, while filtered HS has 25 and passes. In 2020 alone the normal model had 14 exceptions, deep in the red zone, against 4 for filtered HS. The normal model misses because it has no fat tails and its volatility estimate reacts slowly. Filtered HS takes the current volatility level from GARCH and the shape of the tails from its own standardised residuals, so it adapts when a shock arrives without assuming normality.

## Limitations

The 20 day VaR is the one day VaR scaled by the square root of 20, which assumes daily returns are independent and identically distributed. They are not, because volatility clusters, so the 20 day figure understates risk going into a stressed period and overstates it coming out. The holdings are ETFs standing in for the underlying securities a real fund would hold, so the VaR reflects ETF pricing, including stale prices on thinly traded days, rather than a look-through to bonds and equities. Commitment leverage is simplified. It adds the gross notional of every holding, cash included, to the notional of a single synthetic futures overlay, where the CESR methodology converts each derivative to the market value of its underlying and allows netting and hedging arrangements. The futures overlay exists only to give commitment leverage something to measure and has no price series, so it is left out of the VaR, which a real fund could not do. Weights are held fixed, which treats the fund as rebalanced to target every day.
