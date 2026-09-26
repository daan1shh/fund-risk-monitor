import time
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
HISTORY = "10y"


def load_config() -> tuple[dict, dict]:
    portfolio = yaml.safe_load((ROOT / "config" / "portfolio.yaml").read_text())
    limits = yaml.safe_load((ROOT / "config" / "limits.yaml").read_text())
    return portfolio, limits


def universe(portfolio: dict) -> list[str]:
    return sorted(set(portfolio["holdings"]) | set(portfolio["reference"]))


def _download(ticker, start=None):
    # yahoo drops connections now and then, a couple of retries is enough
    for attempt in range(3):
        try:
            if start is None:
                hist = yf.Ticker(ticker).history(period=HISTORY, auto_adjust=True)
            else:
                hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
            break
        except Exception as err:
            if attempt == 2:
                raise
            print(f"  {ticker}: download failed ({err}), retrying")
            time.sleep(2)
    close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.rename(ticker)


def _cached_close(ticker, refresh):
    path = CACHE_DIR / f"{ticker}.parquet"
    if refresh or not path.exists():
        close = _download(ticker)
    else:
        cached = pd.read_parquet(path)[ticker]
        # re-pull the last few days too, yahoo revises the latest print after the close
        tail = _download(ticker, start=cached.index[-5])
        close = pd.concat([cached[cached.index < tail.index.min()], tail]) if len(tail) else cached
    if len(close):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        close.to_frame().to_parquet(path)
    return close


def load_prices(tickers: list[str], refresh: bool = False) -> pd.DataFrame:
    """Adjusted daily closes for every ticker, stopping if any ticker comes back empty."""
    series, missing = {}, []
    for ticker in tickers:
        close = _cached_close(ticker, refresh)
        if close.empty:
            missing.append(ticker)
            print(f"  {ticker}: no data returned")
        else:
            series[ticker] = close
    if missing:
        raise SystemExit(f"stopping, no price history for {', '.join(missing)}")
    return pd.DataFrame(series).sort_index()


def build_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns on dates where every constituent has a price."""
    aligned = prices.dropna()
    before_start = int((prices.index < aligned.index[0]).sum())
    gaps = len(prices) - len(aligned) - before_start
    print(f"history starts {aligned.index[0].date()} ({before_start} dates before the youngest "
          f"listing), {gaps} later dates dropped for a missing price")
    # simple not log returns, so position pnl adds up across holdings in money terms
    return aligned.pct_change().dropna()
