import argparse

from riskmon import backtest as bt
from riskmon.dashboard import build_dashboard
from riskmon.data import build_returns, load_config, load_prices, universe
from riskmon.metrics import portfolio_returns, snapshot
from riskmon.report import write_morning_report


def monitor(verbose: bool):
    portfolio, limits = load_config()
    returns = build_returns(load_prices(universe(portfolio)))
    as_of, previous = returns.index[-1], returns.index[-2]
    today = snapshot(returns, portfolio, limits, as_of)
    yesterday = snapshot(returns, portfolio, limits, previous)
    write_morning_report(as_of, portfolio["nav"], today, yesterday, limits, verbose)


def backtest():
    portfolio, limits = load_config()
    returns = build_returns(load_prices(universe(portfolio)))
    port = portfolio_returns(returns, portfolio["holdings"])
    conf = limits["var_confidence"]
    print(f"backtesting {limits['backtest_window']} days, garch refit every {bt.REFIT_EVERY}")
    var = bt.rolling_var(port, limits["backtest_window"], limits["var_lookback_days"], conf)
    table = bt.compare_models(var, conf)
    bt.print_table(table)
    bt.save(var, table, conf)
    print(f"written to {bt.BACKTEST_FILE.relative_to(bt.BACKTEST_FILE.parent.parent)}")


def dashboard():
    portfolio, limits = load_config()
    if not bt.BACKTEST_FILE.exists():
        raise SystemExit("no backtest results yet, run backtest first")
    returns = build_returns(load_prices(universe(portfolio)))
    path = build_dashboard(returns, portfolio, limits, bt.load())
    print(f"written to {path.relative_to(path.parent.parent)}")


def refresh():
    portfolio, _ = load_config()
    prices = load_prices(universe(portfolio), refresh=True)
    print(f"redownloaded {len(prices.columns)} tickers, {len(prices)} dates")


def main():
    parser = argparse.ArgumentParser(prog="riskmon")
    commands = parser.add_subparsers(dest="command", required=True)
    mon = commands.add_parser("monitor", help="morning report for the latest date")
    mon.add_argument("--verbose", action="store_true", help="include the full metrics table")
    commands.add_parser("backtest", help="model comparison table, writes backtest.json")
    commands.add_parser("dashboard", help="rebuild docs/index.html")
    commands.add_parser("refresh", help="force a full price redownload")
    args = parser.parse_args()

    if args.command == "monitor":
        monitor(args.verbose)
    elif args.command == "backtest":
        backtest()
    elif args.command == "dashboard":
        dashboard()
    elif args.command == "refresh":
        refresh()


if __name__ == "__main__":
    main()
