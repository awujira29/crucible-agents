#!/usr/bin/env python3
"""Compare search with and without the transposition table.
Run from the project root:
    python3 tools/test_table.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.connect_four import (play, best_move, non_losing_moves, threat_cells,
                                landing_cells, column_of, CENTER_FIRST, column_bits, CELLS)

failures = 0


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
            return None                      # someone could win: skip this seed
        safe = non_losing_moves(position, mask)
        cols = [c for c in CENTER_FIRST if safe & column_bits(c)]
        if not cols:
            return None
        position, mask = play(position, mask, rng.choice(cols))
    return position, mask


def compare(label, position, mask, moves, depth):
    t0 = time.monotonic()
    col_a, score_a, without = best_move(position, mask, moves, depth, use_table=False)
    t1 = time.monotonic()
    col_b, score_b, with_ = best_move(position, mask, moves, depth, use_table=True)
    t2 = time.monotonic()
    detail = (f"without table: {without.nodes:>9,} nodes {t1 - t0:6.2f}s   "
              f"with table: {with_.nodes:>9,} nodes {t2 - t1:6.2f}s   "
              f"(table hits {with_.table_hits:,})")
    return score_a, score_b, detail


print("Opening (the search stops early, so these scores are estimates)")
for depth in (8, 10):
    a, b, detail = compare("opening", 0, 0, 0, depth)
    print(f"      depth {depth}: score without {a}, with {b}\n      {detail}")

print("\nExact endgame solves (search to the end: scores MUST match)")
# Positions after 22 sensible random moves, chosen because they take real work.
for number, seed in enumerate((20, 37, 5), start=1):
    position, mask = random_position(22, seed)
    remaining = CELLS - 22
    a, b, detail = compare("endgame", position, mask, 22, remaining)
    check(f"position {number}, {remaining} moves to the end: score {a} vs {b}", a == b, detail)

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")