#!/usr/bin/env python3
"""Checks for the negamax alpha-beta search. Run from the project root:
    python3 tools/test_search.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.connect_four import rebuild, best_move, WIN

failures = 0


def history_from(columns):
    hist, heights = [], [0] * 7
    for i, col in enumerate(columns):
        hist.append({"seq": i + 1, "event": {
            "type": "disc-dropped", "column": col,
            "row": 5 - heights[col], "player": 1 + i % 2}})
        heights[col] += 1
    return hist


def search(columns, depth, prune=True, use_table=True):
    position, mask, moves = rebuild(history_from(columns))
    start = time.monotonic()
    col, score, srch = best_move(position, mask, moves, depth, prune, use_table)
    nodes = srch.nodes
    return col, score, nodes, time.monotonic() - start


def check(name, condition, detail=""):
    global failures
    print(("PASS  " if condition else "FAIL  ") + name + (f"   ({detail})" if detail else ""))
    if not condition:
        failures += 1


print("Tactics")
col, score, _, _ = search([0, 1, 0, 1, 0, 2], 6)
check("takes an immediate win", col == 0, f"col {col}")

col, score, _, _ = search([3, 3, 2, 4, 1], 6)
check("blocks the opponent's threat", col == 0, f"col {col}")

# Red: bottom row cols 2 and 3. Playing 1 or 4 makes an open three: _ X X X _
col, score, _, _ = search([3, 3, 2, 2], 6)
check("finds a double threat (win in 2 moves)", col in (1, 4) and score == WIN - 7,
      f"col {col}, score {score}")

print("\nAlpha-beta vs. plain minimax, no table (same depth, same answer?)")
for depth in (4, 5, 6):
    col_ab, score_ab, nodes_ab, t_ab = search([3, 3], depth, prune=True, use_table=False)
    col_mm, score_mm, nodes_mm, t_mm = search([3, 3], depth, prune=False, use_table=False)
    check(f"depth {depth}: same score", score_ab == score_mm,
          f"minimax {nodes_mm:,} nodes {t_mm:.2f}s | alpha-beta {nodes_ab:,} nodes {t_ab:.2f}s")

print("\nSpeed of a depth-8 search from the opening")
col, score, nodes, t = search([], 8)
print(f"      empty board: col {col}, score {score}, {nodes:,} nodes in {t:.2f}s")

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")