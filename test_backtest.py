"""
test_backtest.py - Test Script for QuantPulse Backtesting Engine

This script runs a complete backtest using the backtesting engine,
executes the mean reversion strategy, and prints the final Sharpe Ratio.

Usage:
    python test_backtest.py
"""

import numpy as np
from datetime import datetime, timedelta

from engine import BacktestEngine, Tick
from indicators import calculate_rsi, calculate_macd
from strategy import MeanReversionStrategy, get_strategy_config
from analytics import PerformanceAnalytics


def generate_test_data(count: int = 10000) -> list:
    """Generate synthetic market data for backtesting."""
    ticks = []
    base_price = 100.0
    current_time = datetime.now()

    for i in range(count):
        price = base_price + np.random.normal(0, 0.1)
        volume = np.random.uniform(100, 1000)
        bid = price - 0.01
        ask = price + 0.01
        bid_size = np.random.uniform(100, 1000)
        ask_size = np.random.uniform(100, 1000)

        tick = Tick(
            timestamp=current_time + timedelta(seconds=i * 0.001),
            symbol="TEST",
            price=price,
            volume=volume,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size
        )
        ticks.append(tick)

    return ticks


def run_backtest():
    """Run a complete backtest and print the final Sharpe Ratio."""
    print("=" * 60)
    print("QuantPulse Institutional Backtesting Engine")
    print("Mean Reversion Strategy - Backtest Report")
    print("=" * 60)
    print()

    # Generate test data
    print("Generating test data...")
    ticks = generate_test_data(1000)
    prices = np.array([tick.price for tick in ticks])
    print(f"Generated {len(ticks)} ticks")
    print()

    # Calculate indicators
    print("Calculating indicators...")
    rsi = calculate_rsi(prices, period=14)
    macd_line, signal_line, histogram = calculate_macd(prices, 12, 26, 9)
    print(f"RSI: {rsi[-1]:.2f}")
    print(f"MACD: {macd_line[-1]:.2f}, Signal: {signal_line[-1]:.2f}, Histogram: {histogram[-1]:.2f}")
    print()

    # Initialize strategy
    print("Initializing strategy...")
    config = get_strategy_config()
    strategy = MeanReversionStrategy(config)
    print(f"Strategy: {strategy.config['strategy']['name']}")
    print(f"RSI Period: {strategy.rsi_period}")
    print(f"RSI Oversold: {strategy.rsi_oversold}")
    print(f"RSI Overbought: {strategy.rsi_overbought}")
    print(f"Stop Loss: {strategy.stop_loss}")
    print(f"Take Profit: {strategy.take_profit}")
    print()

    # Generate signals
    print("Generating signals...")
    signals = strategy.calculate_signals(prices)
    print(f"Generated {len(signals)} signals")
    print()

    # Run backtest
    print("Running backtest...")
    engine = BacktestEngine()
    results = engine.run_backtest(ticks, signals)
    print(f"Backtest completed. Final capital: ${results['final_capital']:.2f}")
    print(f"Total Trades: {results['total_trades']}")
    print()

    # Generate performance report
    print("Generating performance report...")
    analytics = PerformanceAnalytics(engine.equity_curve)
    report = analytics.generate_performance_report(results['trades'])
    print()
    print("=" * 60)
    print("Backtest Results")
    print("=" * 60)
    print(f"Initial Capital: ${results['initial_capital']:,.2f}")
    print(f"Final Capital: ${results['final_capital']:,.2f}")
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2%}")
    print(f"Win Rate: {results['win_rate']:.2%}")
    print()
    print("=" * 60)
    print(f"Final Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_backtest()
