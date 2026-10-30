#!/usr/bin/env python3
"""Build the Connect Four opening book (run offline, on your own machine).

For every early position our bot can reach, as Red and as Yellow, this runs
a long search and saves the best move to src/games/c4_book.json.

Only our own turns branch on one move (our book choice); the opponent's turns
branch on every legal reply. Mirror-image positions are searched only once.

Progress is saved after every position, so you can stop with Ctrl+C and run
the same command again later to continue where it left off.

Usage (from the project root):
    python3 tools/build_book.py                       # defaults: --plies 6 --seconds 10
    python3 tools/build_book.py --plies 6 --seconds 20
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.connect_four import (BOOK_PATH, play, think, legal_columns, has_four,
                                mirror_key, WIDTH)


def load_existing(path):
    """Resume from an existing book, but only if it was built with the same settings."""
    try:
        data = json.loads(path.read_text())
        return data
    except (FileNotFoundError, ValueError):
        return None


def save(path, plies, seconds, moves):
    data = {"version": 1, "plies": plies, "seconds": seconds,
            "positions": len(moves), "moves": {str(k): c for k, c in moves.items()}}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=0, sort_keys=True))
    temporary.replace(path)      # replace in one step, so a crash never leaves half a file


def count_our_turns(plies):
    """How many of our-turn positions the walk will visit (before mirror savings)."""
    red = sum(7 ** (k // 2) for k in range(0, plies, 2))
    yellow = sum(7 ** ((k + 1) // 2) for k in range(1, plies, 2))
    return red, yellow


def main():
    parser = argparse.ArgumentParser(description="Build the Connect Four opening book")
    parser.add_argument("--plies", type=int, default=6,
                        help="book covers positions with fewer than this many discs (default 6)")
    parser.add_argument("--seconds", type=float, default=10,
                        help="search time per position (default 10)")
    parser.add_argument("--out", type=Path, default=BOOK_PATH)
    args = parser.parse_args()

    moves = {}
    existing = load_existing(args.out)
    if existing and existing.get("plies") == args.plies and existing.get("seconds") == args.seconds:
        moves = {int(k): c for k, c in existing["moves"].items()}
        print(f"Resuming: {len(moves)} positions already in {args.out}")
    elif existing:
        print(f"Existing book used different settings; starting a new one.")

    red, yellow = count_our_turns(args.plies)
    print(f"Book covers positions with fewer than {args.plies} discs.")
    print(f"Our-turn positions to cover: {red} as Red + {yellow} as Yellow "
          f"(mirror images are searched once, so roughly half need a search).")
    print(f"At {args.seconds:g}s per search, the worst case is about "
          f"{(red + yellow) * args.seconds / 60:.0f} minutes.\n")

    stats = {"searched": 0, "reused": 0}
    start = time.monotonic()

    def explore(position, mask, moves_played, our_parity):
        if moves_played >= args.plies:
            return
        if has_four(position ^ mask):            # the previous mover already won
            return
        if moves_played % 2 == our_parity:       # our turn: one branch, the book move
            key = position + mask
            if key in moves:
                col = moves[key]
                stats["reused"] += 1
            elif mirror_key(key) in moves:
                col = WIDTH - 1 - moves[mirror_key(key)]
                stats["reused"] += 1
            else:
                col, score, depth, search, reason = think(
                    position, mask, moves_played, args.seconds, use_book=False)
                moves[key] = col
                save(args.out, args.plies, args.seconds, moves)
                stats["searched"] += 1
                elapsed = time.monotonic() - start
                print(f"  #{stats['searched']:4d}  discs {moves_played}  -> column {col}  "
                      f"score {score:>8}  depth {depth:2d}  ({reason})  [{elapsed / 60:.1f} min]")
            explore(*play(position, mask, col), moves_played + 1, our_parity)
        else:                                     # opponent's turn: every legal reply
            for col in legal_columns(mask):
                explore(*play(position, mask, col), moves_played + 1, our_parity)

    try:
        print("As Red:")
        explore(0, 0, 0, our_parity=0)
        print("As Yellow:")
        explore(0, 0, 0, our_parity=1)
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved; run the same command again to continue.")
        return

    save(args.out, args.plies, args.seconds, moves)
    print(f"\nDone: {len(moves)} positions in {args.out} "
          f"({stats['searched']} searched now, {stats['reused']} reused or mirrored), "
          f"{(time.monotonic() - start) / 60:.1f} minutes.")


if __name__ == "__main__":
    main()