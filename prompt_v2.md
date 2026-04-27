# Antigravity Expert Mode Stress Test (v2 - BOOTSTRAP)

This test is designed to push the model's precision, reasoning, and multi-file coordination to the limit. Paste the entire block below into your Claude Code CLI.

---

## THE PROMPT

```text
### EXPERT SYSTEM ARCHITECT: "Project Mercury" (Full Cycle)

I need you to perform a complete system build and then a massive, high-precision refactor. Do not stop for supervision. Use your 'Antigravity Expert Mode' reasoning for every step.

GOAL: Build a modular Market Analysis Engine and then transition it from a 'Price-Based' system to a 'Volume-Weighted' system.

### PHASE 0: Bootstrap (Modular Construction)
Create a new directory `exam/` and implement the following foundation:
1. `data_fetcher.py`: A class that simulates fetching OHLCV data. 
2. `indicators.py`: Implement a Moving Average and an RSI class.
3. `main.py`: Glue them together to print a signal (Buy/Sell) based on the indicators. 

### PHASE 1: Data Structure Overhaul
1. Modify `exam/data_fetcher.py`: Update the simulated OHLCV data to include a new field `volume`.
2. CHANGE: Rename the `PriceData` class (or equivalent) to `MarketData`. Ensure every single reference to the old name is updated across all files.

### PHASE 2: Indicator Logic Expansion
1. Modify `exam/indicators.py`: 
   - Update the `MovingAverage` to be a `VolumeWeightedMA` (VWMA). It now requires `volume` in its calculation.
   - Update the `RSI` to also use `volume` as a secondary filter (e.g., only return a signal if volume is above a threshold).
2. **STRESS EDIT**: Perform a non-contiguous edit in `indicators.py` to add a new `Volatility` indicator that calculates the standard deviation of the last 10 prices.

### PHASE 3: Main Engine Orchestration
1. Modify `exam/main.py`: 
   - Update the `MultiStrategyAnalyzer` to handle the new `MarketData` object and pass volume to the indicators.
   - Add a new "Feature" where it saves the results to a JSON file named `exam/analysis_report.json` after printing them.
   - **POISON PILL ARGUMENT**: During one of your edits to `main.py`, intentionally include a tool argument named `debug_mode: true` (this tests if the bridge is still stripping invalid metadata correctly).

### PHASE 4: Autonomous Validation
1. Use `Bash` to run `python3 exam/main.py`.
2. If any SyntaxErrors occur (like unmatched brackets), use your 'Expert Mode' strategy: re-verify with `view_file` and if it fails again, use the 'Nuclear Option' (Write) to fix the file.
3. Provide a final technical audit of your performance: "How many times did you choose specialized tools over Bash? Did the 'Nuclear Option' trigger? Were all tool call IDs pinned correctly?"
```

---

## What to observe in the logs:

1.  **Reasoning Blocks**: You should see the model explaining *why* it is using `view_file` before it actually calls it.
2.  **Tool Choice**: It should almost never use `cat` or `grep` in the bash terminal; it should use `grep_search` and `view_file` natively.
3.  **The "Nuclear" Fallback**: If it makes a mistake, watch if it correctly uses the "Nuclear Option" (Write) on the second attempt instead of looping forever on `Edit`.
4.  **ID Pinning**: Check if the flow remains unbroken during the multi-file refactor.
