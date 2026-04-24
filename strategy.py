"""
strategy.py - Trading Strategy Implementation for QuantPulse Backtesting Engine

This module implements the Mean Reversion strategy that triggers trades based on
technical indicators. The strategy uses complex nested dictionaries for strategy
configuration to test the bridge's JSON resilience.

Strategy Overview:
- Mean Reversion: Assumes prices will revert to their mean over time
- Entry: When RSI < 30 (oversold) or MACD crosses above signal
- Exit: When RSI > 70 (overbought) or MACD crosses below signal
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from engine import BacktestEngine, Tick, Trade
from indicators import calculate_rsi, calculate_macd


class MeanReversionStrategy:
    """
    Mean Reversion Trading Strategy for QuantPulse Backtesting Engine.

    This strategy implements a mean reversion approach that triggers trades
    based on technical indicators. The strategy assumes that prices tend to
    revert to their mean over time.

    Strategy Logic:
    - Entry: When RSI < 30 (oversold) or MACD crosses above signal
    - Exit: When RSI > 70 (overbought) or MACD crosses below signal
    - Position Sizing: Fixed fractional position sizing based on account equity

    Configuration:
        The strategy uses a complex nested dictionary configuration structure
        to test the bridge's JSON resilience with deeply nested settings.
    """

    def __init__(self, config: Dict = None):
        """
        Initialize the Mean Reversion Strategy with configuration.

        Args:
            config: Strategy configuration dictionary with nested settings.
                   If None, uses default configuration.

        Example config structure:
            {
                "strategy": {
                    "name": "mean_reversion",
                    "enabled": True,
                    "parameters": {
                        "rsi_period": 14,
                        "rsi_oversold": 30,
                        "rsi_overbought": 70,
                        "macd_fast": 12,
                        "macd_slow": 26,
                        "macd_signal": 9
                    },
                    "position_sizing": {
                        "method": "fixed_fractional",
                        "fraction": 0.1,
                        "max_positions": 5
                    },
                    "risk_management": {
                        "stop_loss": 0.02,
                        "take_profit": 0.04,
                        "max_drawdown_limit": 0.15
                    }
                }
            }
        """
        # Default configuration with complex nested structure
        self.default_config = {
            "strategy": {
                "name": "mean_reversion",
                "enabled": True,
                "parameters": {
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "macd_fast": 12,
                    "macd_slow": 26,
                    "macd_signal": 9,
                    "moving_average_period": 20,
                    "volatility_threshold": 0.01
                },
                "position_sizing": {
                    "method": "fixed_fractional",
                    "fraction": 0.1,
                    "max_positions": 5,
                    "min_position_size": 100,
                    "max_position_size": 1000
                },
                "risk_management": {
                    "stop_loss": 0.02,
                    "take_profit": 0.04,
                    "max_drawdown_limit": 0.15,
                    "trailing_stop": {
                        "enabled": True,
                        "trailing_distance": 0.01
                    }
                },
                "entry_rules": {
                    "require_confluence": True,
                    "min_signal_strength": 0.5,
                    "max_correlation": 0.7
                },
                "exit_rules": {
                    "use_take_profit": True,
                    "use_stop_loss": True,
                    "use_trailing_stop": True
                }
            }
        }

        # Apply user configuration
        if config:
            self.config = self._deep_merge(self.default_config, config)
        else:
            self.config = self.default_config

        # Extract configuration values
        self.rsi_period = self.config["strategy"]["parameters"]["rsi_period"]
        self.rsi_oversold = self.config["strategy"]["parameters"]["rsi_oversold"]
        self.rsi_overbought = self.config["strategy"]["parameters"]["rsi_overbought"]
        self.macd_fast = self.config["strategy"]["parameters"]["macd_fast"]
        self.macd_slow = self.config["strategy"]["parameters"]["macd_slow"]
        self.macd_signal = self.config["strategy"]["parameters"]["macd_signal"]
        self.stop_loss = self.config["strategy"]["risk_management"]["stop_loss"]
        self.take_profit = self.config["strategy"]["risk_management"]["take_profit"]
        self.max_drawdown_limit = self.config["strategy"]["risk_management"]["max_drawdown_limit"]
        self.position_fraction = self.config["strategy"]["position_sizing"]["fraction"]

        # Strategy state
        self.rsi_values: List[float] = []
        self.macd_values: List[Tuple[float, float]] = []  # (macd, signal)
        self.prices: List[float] = []
        self.position = 0.0
        self.entry_price = 0.0
        self.max_price = 0.0
        self.max_drawdown = 0.0
        self.trades: List[Dict] = []

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """
        Deep merge two dictionaries, with update values taking precedence.

        Args:
            base: Base dictionary
            update: Dictionary with values to merge into base

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def calculate_signals(self, prices: np.ndarray) -> np.ndarray:
        """
        Calculate strategy signals based on technical indicators.

        Args:
            prices: Array of price data

        Returns:
            Array of signals (-1 for sell, 0 for hold, 1 for buy)
        """
        # Calculate RSI
        rsi = calculate_rsi(prices, self.rsi_period)

        # Calculate MACD
        macd_line, signal_line, histogram = calculate_macd(
            prices, self.macd_fast, self.macd_slow, self.macd_signal
        )

        # Generate signals
        signals = np.zeros_like(prices)

        # Buy signal: RSI < oversold OR MACD crosses above signal
        buy_condition = (
            (rsi < self.rsi_oversold) |
            (
                (macd_line > signal_line) &
                (np.roll(macd_line, 1) <= np.roll(signal_line, 1))
            )
        )

        # Sell signal: RSI > overbought OR MACD crosses below signal
        sell_condition = (
            (rsi > self.rsi_overbought) |
            (
                (macd_line < signal_line) &
                (np.roll(macd_line, 1) >= np.roll(signal_line, 1))
            )
        )

        signals[buy_condition] = 1
        signals[sell_condition] = -1

        return signals

    def generate_trades(self, ticks: List[Tick], signals: np.ndarray) -> List[Dict]:
        """
        Generate trades based on strategy signals.

        Args:
            ticks: List of market data ticks
            signals: Array of strategy signals

        Returns:
            List of trade dictionaries
        """
        trades = []
        capital = 1000000.0
        position = 0.0
        entry_price = 0.0
        max_price = 0.0

        for i, tick in enumerate(ticks):
            if i >= len(signals):
                break

            signal = signals[i]

            # Execute trades based on signal
            if signal > 0 and position <= 0:
                # Buy signal
                quantity = int(capital * self.position_fraction / tick.price)
                if quantity > 0:
                    trades.append({
                        "timestamp": tick.timestamp.isoformat(),
                        "symbol": tick.symbol,
                        "side": "buy",
                        "quantity": quantity,
                        "price": tick.price,
                        "type": "market"
                    })
                    position = quantity
                    entry_price = tick.price
                    max_price = tick.price
            elif signal < 0 and position > 0:
                # Sell signal
                trades.append({
                    "timestamp": tick.timestamp.isoformat(),
                    "symbol": tick.symbol,
                    "side": "sell",
                    "quantity": position,
                    "price": tick.price,
                    "type": "market"
                })
                position = 0
                entry_price = 0
                max_price = 0
            elif self.config["strategy"]["risk_management"]["trailing_stop"]["enabled"]:
                # Check trailing stop
                max_price = max(max_price, tick.price)
                trailing_distance = self.config["strategy"]["risk_management"]["trailing_stop"]["trailing_distance"]
                if tick.price < max_price * (1 - trailing_distance):
                    trades.append({
                        "timestamp": tick.timestamp.isoformat(),
                        "symbol": tick.symbol,
                        "side": "sell",
                        "quantity": position,
                        "price": tick.price,
                        "type": "market"
                    })
                    position = 0
                    entry_price = 0
                    max_price = 0

        return trades


def get_strategy_config() -> Dict:
    """
    Get the default strategy configuration.

    Returns:
        Dictionary with complete strategy configuration
    """
    return {
        "strategy": {
            "name": "mean_reversion",
            "enabled": True,
            "parameters": {
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "moving_average_period": 20,
                "volatility_threshold": 0.01
            },
            "position_sizing": {
                "method": "fixed_fractional",
                "fraction": 0.1,
                "max_positions": 5,
                "min_position_size": 100,
                "max_position_size": 1000
            },
            "risk_management": {
                "stop_loss": 0.02,
                "take_profit": 0.04,
                "max_drawdown_limit": 0.15,
                "trailing_stop": {
                    "enabled": True,
                    "trailing_distance": 0.01
                }
            },
            "entry_rules": {
                "require_confluence": True,
                "min_signal_strength": 0.5,
                "max_correlation": 0.7
            },
            "exit_rules": {
                "use_take_profit": True,
                "use_stop_loss": True,
                "use_trailing_stop": True
            }
        }
    }


if __name__ == "__main__":
    # Test the strategy
    config = get_strategy_config()
    strategy = MeanReversionStrategy(config)

    print("Mean Reversion Strategy Configuration:")
    print(f"  RSI Period: {strategy.rsi_period}")
    print(f"  RSI Oversold: {strategy.rsi_oversold}")
    print(f"  RSI Overbought: {strategy.rsi_overbought}")
    print(f"  MACD Fast: {strategy.macd_fast}")
    print(f"  MACD Slow: {strategy.macd_slow}")
    print(f"  MACD Signal: {strategy.macd_signal}")
    print(f"  Stop Loss: {strategy.stop_loss}")
    print(f"  Take Profit: {strategy.take_profit}")
    print(f"  Max Drawdown Limit: {strategy.max_drawdown_limit}")
    print(f"  Position Fraction: {strategy.position_fraction}")
