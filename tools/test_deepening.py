#!/usr/bin/env python3
"""Checks for iterative deepening and the time budget.
Run from the project root:
    python3 tools/test_deepening.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.connect_four import (play, think, non_losing_moves, threat_cells, landing_cells,
                                column_bits, CENTER_FIRST, TIME_BUDGET)

failures = 0
SLACK = 0.3   # allowed overshoot past the budget, in seconds


def check(name, condition, detail=""):
    global failures
    print(("PASS  " if condition else "FAIL  ") + name + (f"\n      {detail}" if detail else ""))
    if not condition:
        failures += 1


def random_position(n_moves, seed):
    """Play n_moves random 'sensible' moves (no immediate wins, no blunders)."""
    rng = random.Random(seed)
    position = mask = 0
    for _ in range(n_moves):
        if threat_cells(position, mask) & landing_cells(mask):
            return None
        safe = non_losing_moves(position, mask)
        cols = [c for c in CENTER_FIRST if safe & column_bits(c)]
        if not cols:
            return None
        position, mask = play(position, mask, rng.choice(cols))
    return position, mask


def run(label, position, mask, moves, budget=TIME_BUDGET):
    start = time.monotonic()
    col, score, depth, search, reason = think(position, mask, moves, budget)
    took = time.monotonic() - start
    detail = (f"col {col}, score {score}, depth {depth}, {search.nodes:,} nodes, "
              f"{took:.2f}s, {reason}")
    return col, score, depth, took, reason, detail


print(f"How deep does the search get in {TIME_BUDGET:.0f} seconds?")
# (moves played, seed): positions chosen so the result isn't already decided
for moves, seed in ((0, None), (8, 1), (16, 7), (22, 20)):
    position, mask = (0, 0) if seed is None else random_position(moves, seed)
    col, score, depth, took, reason, detail = run("", position, mask, moves)
    check(f"after {moves:2d} moves: stays within budget", took <= TIME_BUDGET + SLACK, detail)

print("\nStopping early")
position, mask = random_position(22, 37)           # a proven loss for the mover (from test_table)
col, score, depth, took, reason, detail = run("", position, mask, 22)
check("stops as soon as the result is proven", "proven" in reason and took < TIME_BUDGET, detail)

hist = [0, 1, 0, 1, 0, 2]                          # Red can win in column 0
position = mask = 0
for c in hist:
    position, mask = play(position, mask, c)
col, score, depth, took, reason, detail = run("", position, mask, len(hist))
check("immediate win is played without searching", col == 0 and took < 0.05, detail)

print("\nTiny budget (a slow machine or a short deadline)")
col, score, depth, took, reason, detail = run("", 0, 0, 0, budget=0.2)
check("still returns a legal move on time", col in range(7) and took <= 0.2 + SLACK, detail)

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")