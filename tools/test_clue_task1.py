#!/usr/bin/env python3
"""Tests for Task 1: the notebook. Run from the project root:
    python3 tools/test_clue_task1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.clue.deduction import Notebook, Contradiction, ENVELOPE
failures = 0


def check(name, condition):
    global failures
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures += 1


CARDS = ["suspect:plum", "suspect:green", "weapon:rope"]
SEATS = ["seat-1", "seat-2"]

nb = Notebook(CARDS, SEATS)

check("places are the seats plus the envelope",
      nb.places == ["seat-1", "seat-2", ENVELOPE])
check("there is one cell per (card, place) pair",
      len(nb.cells) == len(CARDS) * 3)
check("every cell starts unknown",
      all(nb.get(card, place) is None for card in CARDS for place in nb.places))

check("setting an unknown cell returns True",
      nb.set("suspect:plum", "seat-2", True) is True)
check("the value is stored",
      nb.get("suspect:plum", "seat-2") is True)
check("setting the same value again returns False",
      nb.set("suspect:plum", "seat-2", True) is False)
check("other cells are unaffected",
      nb.get("suspect:plum", "seat-1") is None)

check("setting False works too",
      nb.set("weapon:rope", ENVELOPE, False) is True and nb.get("weapon:rope", ENVELOPE) is False)

try:
    nb.set("suspect:plum", "seat-2", False)
    check("setting the opposite value raises Contradiction", False)
except Contradiction as error:
    check("setting the opposite value raises Contradiction", True)
    print("      message was:", error)

check("a contradiction doesn't change the stored value",
      nb.get("suspect:plum", "seat-2") is True)

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")