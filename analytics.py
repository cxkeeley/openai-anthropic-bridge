"""
analytics.py - Performance Analytics for QuantPulse Backtesting Engine

This module provides performance analytics including Sharpe Ratio, Maximum Drawdown,
and Win Rate calculations for backtesting results.

Analytics Implemented:
- Sharpe Ratio: Risk-adjusted return measure
- Maximum Drawdown: Largest peak-to-trough decline
- Win Rate: Percentage of profitable trades
- Additional metrics: Sortino Ratio, Calmar Ratio, Profit Factor
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime


class PerformanceAnalytics:
    """
    Performance Analytics for QuantPulse Backtesting Engine.

    This class provides comprehensive performance analytics including:
    - Sharpe Ratio: Risk-adjusted return measure
    - Maximum Drawdown: Largest peak-to-trough decline
    - Win Rate: Percentage of profitable trades
    - Additional metrics: Sortino Ratio, Calmar Ratio, Profit Factor

    All calculations use NumPy for vectorized operations for optimal performance.
    """

    def __init__(self, equity_curve: List[Tuple[datetime, float]],
                 risk_free_rate: float = 0.02):
        """
        Initialize the Performance Analytics.

        Args:
            equity_curve: List of (timestamp, equity) tuples
            risk_free_rate: Annual risk-free rate (default: 2%)
        """
        self.equity_curve = equity_curve
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = np.sqrt(252)  # Daily returns
        self.equity_values = np.array([equity for _, equity in equity_curve])
        self.returns = self._calculate_returns()

    def _calculate_returns(self) -> np.ndarray:
        """
        Calculate returns from equity curve.

        Returns:
            Array of returns
        """
        if len(self.equity_values) < 2:
            return np.array([0.0])
        returns = np.diff(self.equity_values) / self.equity_values[:-1]
        return returns

    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate the Sharpe Ratio.

        The Sharpe Ratio measures the risk-adjusted return of an investment.
        It is calculated as the excess return divided by the standard deviation
        of returns.

        Formula:
            Sharpe Ratio = (Mean Return - Risk-Free Rate) / Std Dev of Returns

        Returns:
            Sharpe Ratio (annualized)
        """
        if len(self.returns) < 2:
            return 0.0

        mean_return = np.mean(self.returns)
        std_return = np.std(self.returns)

        if std_return == 0:
            return 0.0

        sharpe_ratio = (mean_return / std_return) * self.annualization_factor

        return sharpe_ratio

    def calculate_sortino_ratio(self) -> float:
        """
        Calculate the Sortino Ratio.

        The Sortino Ratio is a variation of the Sharpe Ratio that only
        considers downside volatility (standard deviation of negative returns).

        Formula:
            Sortino Ratio = (Mean Return - Risk-Free Rate) / Downside Deviation

        Returns:
            Sortino Ratio (annualized)
        """
        if len(self.returns) < 2:
            return 0.0

        mean_return = np.mean(self.returns)
        downside_returns = self.returns[self.returns < 0]
        downside_deviation = np.std(downside_returns)

        if downside_deviation == 0:
            return 0.0

        sortino_ratio = (mean_return / downside_deviation) * self.annualization_factor

        return sortino_ratio

    def calculate_max_drawdown(self) -> float:
        """
        Calculate the Maximum Drawdown.

        Maximum Drawdown measures the largest peak-to-trough decline in
        the equity curve. It is expressed as a positive value.

        Returns:
            Maximum Drawdown (as a positive value)
        """
        if len(self.equity_values) < 2:
            return 0.0

        # Calculate running maximum
        running_max = np.maximum.accumulate(self.equity_values)
        # Calculate drawdown
        drawdown = (running_max - self.equity_values) / running_max
        # Return maximum drawdown
        return np.max(drawdown)

    def calculate_calmar_ratio(self) -> float:
        """
        Calculate the Calmar Ratio.

        The Calmar Ratio measures the return of an investment relative to
        its maximum drawdown. It is calculated as the annualized return
        divided by the maximum drawdown.

        Formula:
            Calmar Ratio = Annualized Return / Maximum Drawdown

        Returns:
            Calmar Ratio
        """
        if len(self.returns) < 2:
            return 0.0

        # Calculate annualized return
        total_return = self.equity_values[-1] / self.equity_values[0]
        annualized_return = total_return ** (252 / len(self.equity_values)) - 1

        # Calculate maximum drawdown
        max_drawdown = self.calculate_max_drawdown()

        if max_drawdown == 0:
            return 0.0

        calmar_ratio = annualized_return / max_drawdown

        return calmar_ratio

    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """
        Calculate the Win Rate.

        Win Rate measures the percentage of profitable trades.

        Args:
            trades: List of trade dictionaries with 'profit' key

        Returns:
            Win Rate (as a percentage)
        """
        if len(trades) == 0:
            return 0.0

        # Handle both Trade objects and dictionaries
        if len(trades) > 0 and isinstance(trades[0], dict):
            # Dictionaries
            profitable_trades = sum(1 for trade in trades if trade.get('profit', 0) > 0)
        else:
            # Trade objects
            profitable_trades = sum(1 for trade in trades if trade.profit > 0)
        win_rate = (profitable_trades / len(trades)) * 100

        return win_rate

    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """
        Calculate the Profit Factor.

        Profit Factor measures the gross profit divided by the gross loss.
        A value greater than 1 indicates a profitable strategy.

        Args:
            trades: List of trade dictionaries with 'profit' key

        Returns:
            Profit Factor
        """
        if len(trades) == 0:
            return 0.0

        # Handle both Trade objects and dictionaries
        if len(trades) > 0 and isinstance(trades[0], dict):
            # Dictionaries
            gross_profit = sum(trade.get('profit', 0) for trade in trades if trade.get('profit', 0) > 0)
            gross_loss = abs(sum(trade.get('profit', 0) for trade in trades if trade.get('profit', 0) < 0))
        else:
            # Trade objects
            gross_profit = sum(trade.profit for trade in trades if trade.profit > 0)
            gross_loss = abs(sum(trade.profit for trade in trades if trade.profit < 0))

        if gross_loss == 0:
            return float('inf')

        profit_factor = gross_profit / gross_loss

        return profit_factor

    def generate_performance_report(self, trades: List[Dict]) -> Dict:
        """
        Generate a comprehensive performance report.

        Args:
            trades: List of trade dictionaries with 'profit' key

        Returns:
            Dictionary with performance metrics
        """
        return {
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'sortino_ratio': self.calculate_sortino_ratio(),
            'max_drawdown': self.calculate_max_drawdown(),
            'calmar_ratio': self.calculate_calmar_ratio(),
            'win_rate': self.calculate_win_rate(trades),
            'profit_factor': self.calculate_profit_factor(trades),
            'total_trades': len(trades),
            'total_return': (self.equity_values[-1] / self.equity_values[0]) - 1 if len(self.equity_values) > 0 else 0.0,
            'annualized_return': ((self.equity_values[-1] / self.equity_values[0]) ** (252 / len(self.equity_values))) - 1 if len(self.equity_values) > 0 else 0.0
        }


if __name__ == "__main__":
    # Test the analytics
    from datetime import datetime, timedelta
    import random

    # Generate sample equity curve
    equity_curve = []
    equity = 1000000
    current_time = datetime.now()
    for i in range(100):
        equity_curve.append((current_time + timedelta(days=i), equity))
        equity += random.uniform(-1000, 1000)

    # Generate sample trades
    trades = []
    for i in range(50):
        trades.append({
            'timestamp': (current_time + timedelta(days=i * 5)).isoformat(),
            'profit': random.uniform(-500, 1000)
        })

    # Calculate performance metrics
    analytics = PerformanceAnalytics(equity_curve)
    report = analytics.generate_performance_report(trades)

    print("Performance Report:")
    print(f"  Sharpe Ratio: {report['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {report['sortino_ratio']:.2f}")
    print(f"  Max Drawdown: {report['max_drawdown']:.2%}")
    print(f"  Calmar Ratio: {report['calmar_ratio']:.2f}")
    print(f"  Win Rate: {report['win_rate']:.2f}%")
    print(f"  Profit Factor: {report['profit_factor']:.2f}")
    print(f"  Total Trades: {report['total_trades']}")
    print(f"  Total Return: {report['total_return']:.2%}")
    print(f"  Annualized Return: {report['annualized_return']:.2%}")