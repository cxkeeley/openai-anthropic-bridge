"""
indicators.py - Technical Indicators for QuantPulse Backtesting Engine

This module provides vectorized implementations of common technical indicators
using NumPy for high-performance calculation on large datasets.

Indicators implemented:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)

All calculations use NumPy's vectorized operations for optimal performance.
"""

import numpy as np
from typing import Tuple, Optional


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Calculate the Relative Strength Index (RSI) using vectorized NumPy operations.

    RSI is a momentum oscillator that measures the speed and change of price movements.
    It ranges from 0 to 100, with overbought (>70) and oversold (<30) levels.

    Args:
        prices: Array of price data (1D numpy array)
        period: RSI period (default: 14 periods)

    Returns:
        Array of RSI values (same length as input, with initial NaN values

    Example:
        >>> prices = np.array([100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110])
        >>> rsi = calculate_rsi(prices, period=14)
        >>> print(f"RSI: {rsi[-1]:.2f}")
    """
    if len(prices) < period + 1:
        return np.full_like(prices, np.nan)

    # Calculate price changes
    delta = np.diff(prices)

    # Separate gains and losses
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    # Calculate rolling means using vectorized operations
    window = period
    roll_gain = np.zeros_like(prices)
    roll_loss = np.zeros_like(prices)

    # Use convolution for rolling mean (vectorized)
    kernel = np.ones(window) / window
    roll_gain[window] = np.sum(gain[:window])
    roll_loss[window] = np.sum(loss[:window])

    # Calculate RSI
    rsi = np.zeros_like(prices)
    rsi[window] = 100 - (100 / (1 + (roll_gain[window] / roll_loss[window])))

    # Fill remaining values
    for i in range(window + 1, len(prices)):
        roll_gain[i] = ((roll_gain[i - 1] * (window - 1)) + gain[i - 1]) / window
        roll_loss[i] = ((roll_loss[i - 1] * (window - 1)) + loss[i - 1]) / window
        if roll_loss[i] == 0:
            rsi[i] = 100
        else:
            rsi[i] = 100 - (100 / (1 + (roll_gain[i] / roll_loss[i])))

    return rsi


def calculate_macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate MACD (Moving Average Convergence Divergence) using vectorized NumPy operations.

    MACD is a trend-following momentum indicator that shows the relationship between
    two moving averages of a security's price.

    Args:
        prices: Array of price data (1D numpy array)
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)

    Returns:
        Tuple of (MACD line, Signal line, Histogram)

    Example:
        >>> prices = np.random.randn(100) + 100
        >>> macd_line, signal_line, histogram = calculate_macd(prices, 12, 26, 9)
        >>> print(f"MACD: {macd_line[-1]:.2f}, Signal: {signal_line[-1]:.2f}, Histogram: {histogram[-1]:.2f}
    """
    if len(prices) < slow + signal:
        return (np.full_like(prices, np.nan), np.full_like(prices, np.nan), np.full_like(prices, np.nan))

    # Calculate EMA using vectorized operations
    def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA using vectorized operations"""
        ema = np.zeros_like(data)
        ema[period - 1] = np.mean(data[:period])
        multiplier = 2 / (period + 1)

        for i in range(period, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)

    # Calculate MACD line
    macd_line = fast_ema - slow_ema

    # Calculate signal line
    signal_line = calculate_ema(macd_line, signal)

    # Calculate histogram
    histogram = macd_line - signal_line

    return (macd_line, signal_line, histogram)


def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, num_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands using vectorized NumPy operations.

    Bollinger Bands are a type of statistical chart characterizing the prices and
    volatility of a financial instrument.

    Args:
        prices: Array of price data (1D numpy array)
        period: Period for moving average (default: 20)
        num_std: Number of standard deviations (default: 2.0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band)

    Example:
        >>> prices = np.random.randn(100) + 100
        >>> upper, middle, lower = calculate_bollinger_bands(prices, 20, 2.0)
        >>> print(f"Upper: {upper[-1]:.2f}, Middle: {middle[-1]:.2f}, Lower: {lower[-1]:.2f})
    """
    if len(prices) < period:
        return (np.full_like(prices, np.nan), np.full_like(prices, np.nan), np.full_like(prices, np.nan))

    # Calculate rolling mean and std using vectorized operations
    kernel = np.ones(period) / period
    middle_band = np.convolve(prices, kernel, mode='valid')
    std = np.zeros_like(prices)
    std[period - 1] = np.std(prices[:period])

    for i in range(period, len(prices)):
        std[i] = np.std(prices[i - period:i])

    upper_band = middle_band + (std[period - 1:] * num_std)
    lower_band = middle_band - (std[period - 1:] * num_std)

    return (upper_band, middle_band, lower_band)


if __name__ == "__main__":
    # Test the indicators
    np.random.seed(42)
    prices = np.random.randn(100) + 100

    print("Testing RSI:")
    rsi = calculate_rsi(prices, period=14)
    print(f"RSI: {rsi[-1]:.2f}")

    print("\nTesting MACD:")
    macd_line, signal_line, histogram = calculate_macd(prices, 12, 26, 9)
    print(f"MACD: {macd_line[-1]:.2f}, Signal: {signal_line[-1]:.2f}, Histogram: {histogram[-1]:.2f}")

    print("\nTesting Bollinger Bands:")
    upper, middle, lower = calculate_bollinger_bands(prices, 20, 2.0)
    print(f"Upper: {upper[-1]:.2f}, Middle: {middle[-1]:.2f}, Lower: {lower[-1]:.2f}")
