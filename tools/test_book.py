#!/usr/bin/env python3
"""Checks for the opening book. Run from the project root:
    python3 tools/test_book.py
The coverage checks run only if src/games/c4_book.json exists (build it first
with tools/build_book.py).
"""
import json
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games import connect_four as c4

failures = 0


def check(name, condition, detail=""):
    global failures
    print(("PASS  " if condition else "FAIL  ") + name + (f"   ({detail})" if detail else ""))
    if not condition:
        failures += 1


def position_after(columns):
    position = mask = 0
    for col in columns:
        position, mask = c4.play(position, mask, col)
    return position, mask


def key_after(columns):
    position, mask = position_after(columns)
    return position + mask


print("Mirror images")
check("column 0 mirrors to column 6", c4.mirror_key(key_after([0])) == key_after([6]))
check("a longer game mirrors correctly",
      c4.mirror_key(key_after([3, 2, 2, 1, 5])) == key_after([3, 4, 4, 5, 1]))
rng = random.Random(1)
ok = True
for _ in range(200):
    cols = []
    position = mask = 0
    for _ in range(rng.randint(0, 20)):
        legal = c4.legal_columns(mask)
        col = rng.choice(legal)
        cols.append(col)
        position, mask = c4.play(position, mask, col)
    key = position + mask
    if c4.mirror_key(c4.mirror_key(key)) != key or c4.mirror_key(key) != key_after([6 - c for c in cols]):
        ok = False
check("200 random positions: mirroring twice gives back the original", ok)

print("\nLookups")
fake_book = {key_after([0]): 2}           # after Red plays column 0, the book says column 2
check("direct lookup", c4.book_move(*position_after([0]), book=fake_book) == 2)
check("mirrored lookup flips the column", c4.book_move(*position_after([6]), book=fake_book) == 4)
check("unknown position gives None", c4.book_move(*position_after([3]), book=fake_book) is None)
full = position_after([3] * 6)
check("a book move into a full column is ignored",
      c4.book_move(*full, book={full[0] + full[1]: 3}) is None)

with tempfile.TemporaryDirectory() as folder:
    broken = Path(folder) / "broken.json"
    broken.write_text("{ this is not json")
    check("a broken book file loads as an empty book", c4.load_book(broken) == {})
    check("a missing book file loads as an empty book", c4.load_book(Path(folder) / "nope.json") == {})

print("\nThe real book")
if not c4.BOOK_PATH.exists():
    print(f"      (no {c4.BOOK_PATH.name} yet: build it with tools/build_book.py, then rerun)")
else:
    info = json.loads(c4.BOOK_PATH.read_text())
    plies = info["plies"]
    print(f"      {len(c4.BOOK)} positions, built with --plies {plies} --seconds {info['seconds']}")
    check("first move as Red is the center column", c4.book_move(0, 0) == 3)

    missing = []

    def walk(position, mask, moves, our_parity):
        if moves >= plies:
            return
        if moves % 2 == our_parity:
            col = c4.book_move(position, mask)
            if col is None:
                missing.append(moves)
                return
            walk(*c4.play(position, mask, col), moves + 1, our_parity)
        else:
            for col in c4.legal_columns(mask):
                walk(*c4.play(position, mask, col), moves + 1, our_parity)

    walk(0, 0, 0, 0)
    walk(0, 0, 0, 1)
    check("every early position we can reach has a legal book move",
          not missing, f"{len(missing)} missing" if missing else "")

    start = time.monotonic()
    col, score, depth, search, reason = c4.think(0, 0, 0, 3.0)
    took = time.monotonic() - start
    check("think() plays the book move instantly", reason == "opening book" and took < 0.05,
          f"{reason}, {took * 1000:.1f} ms")

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")