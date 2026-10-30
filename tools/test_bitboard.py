#!/usr/bin/env python3
"""Checks for the bitboard foundation. Run from the project root:
    python3 tools/test_bitboard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.connect_four import (play, rebuild, has_four, threat_cells, landing_cells,
                                decide, H1, HEIGHT, WIDTH)


def history_from(columns):
    """Turn a list of columns into platform-style history entries."""
    hist, heights = [], [0] * WIDTH
    for i, col in enumerate(columns):
        hist.append({"seq": i + 1, "event": {
            "type": "disc-dropped", "column": col,
            "row": HEIGHT - 1 - heights[col], "player": 1 + i % 2}})
        heights[col] += 1
    return hist


def draw(position, mask, moves):
    """Print the board. X = Red, O = Yellow."""
    red = position if moves % 2 == 0 else position ^ mask
    for row in range(HEIGHT - 1, -1, -1):
        line = ""
        for col in range(WIDTH):
            bit = 1 << (col * H1 + row)
            line += ("X " if red & bit else "O ") if mask & bit else ". "
        print("   " + line)
    print("   0 1 2 3 4 5 6")


def bits(n):
    return sorted(i for i in range(49) if n >> i & 1)


def check(name, condition):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        global failures
        failures += 1


failures = 0

# The example from our lessons: Red 3, Yellow 3, Red 2, Yellow 4, Red 1
pos, mask, n = rebuild(history_from([3, 3, 2, 4, 1]))
print("Board after Red 3, Yellow 3, Red 2, Yellow 4, Red 1:")
draw(pos, mask, n)
print("   mask bits:", bits(mask), " value:", mask)
print("   position (Yellow to move):", bits(pos))
print("   Red = mask ^ position:", bits(pos ^ mask))
print()
check("mask is cells 7, 14, 21, 22, 28", bits(mask) == [7, 14, 21, 22, 28])
check("position is Yellow's cells 22, 28", bits(pos) == [22, 28])
check("Red's cells are 7, 14, 21", bits(pos ^ mask) == [7, 14, 21])
check("Red has a threat at cell 0", bits(threat_cells(pos ^ mask, mask)) == [0])
check("Yellow has no threats", threat_cells(pos, mask) == 0)
check("nobody has won yet", not has_four(pos) and not has_four(pos ^ mask))
check("bot blocks in column 0",
      decide({"history": history_from([3, 3, 2, 4, 1])})["column"] == 0)

# Wins in every direction
check("horizontal win detected", has_four(sum(1 << (c * H1) for c in range(4))))
check("vertical win detected", has_four(0b1111))
check("diagonal / win detected", has_four(sum(1 << (c * H1 + c) for c in range(4))))
check("diagonal \\ win detected", has_four(sum(1 << (c * H1 + 3 - c) for c in range(4))))
check("no fake vertical win across columns",
      not has_four((1 << 4) | (1 << 5) | (1 << 7) | (1 << 8)))

# Rule bot takes an immediate win
check("bot wins vertically in column 0",
      decide({"history": history_from([0, 1, 0, 1, 0, 2])})["column"] == 0)

# Full column is not offered
pos, mask, _ = rebuild(history_from([3] * 6))
check("full column 3 has no landing cell", landing_cells(mask) & (0b111111 << 21) == 0)

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")