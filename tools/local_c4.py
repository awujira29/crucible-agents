#!/usr/bin/env python3
"""Play local Connect Four matches through the same protocol as Crucible.

Our agent runs as a separate process (python3 src/agent.py), exactly like on
the platform: JSON lines in on stdin, JSON lines out on stdout.

Usage (from the project root):
    python3 tools/local_c4.py --vs random --games 4
    python3 tools/local_c4.py --vs rules --games 4
    python3 tools/local_c4.py --vs agent --games 2      # self-play, slower
Add --quiet to hide the move-by-move output.

Each agent's stderr log is saved to logs/<game>-<seat>.log.
"""
import argparse
import json
import random
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_COMMAND = [sys.executable, str(ROOT / "src" / "agent.py")]
LOG_DIR = ROOT / "logs"

ROWS, COLS = 6, 7
DEADLINE_MS = 65_000          # platform decision deadline
INIT_LIMIT = 15               # seconds allowed for init
MATCH_LIMIT = 300             # seconds for the whole match (5 minutes)
CENTER_FIRST = [3, 2, 4, 1, 5, 0, 6]


# ---------------------------------------------------------------- players

class AgentProcess:
    """Our agent, running as a real subprocess."""

    def __init__(self, seat, log_path):
        self.seat = seat
        self.name = "agent"
        self.log_file = open(log_path, "w")
        self.proc = subprocess.Popen(AGENT_COMMAND, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log_file,
                                     text=True, bufsize=1)

    def ask(self, message, timeout):
        """Send one JSON line; wait up to `timeout` seconds for one JSON line back."""
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        ready, _, _ = select.select([self.proc.stdout], [], [], timeout)
        if not ready:
            raise TimeoutError(f"no reply within {timeout:.0f}s")
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("process exited (crashed?)")
        return json.loads(line)

    def close(self):
        self.proc.kill()
        self.proc.wait()
        self.log_file.close()


def heights_from(history):
    heights = [0] * COLS
    for entry in history:
        if entry["event"]["type"] == "disc-dropped":
            heights[entry["event"]["column"]] += 1
    return heights


class RandomBot:
    """Plays a random legal column."""

    def __init__(self, seat):
        self.seat, self.name = seat, "random"

    def ask(self, message, timeout):
        if message["type"] == "init":
            return {}
        heights = heights_from(message["history"])
        return {"type": "disc-dropped",
                "column": random.choice([c for c in range(COLS) if heights[c] < ROWS])}

    def close(self):
        pass


class RulesBot:
    """Wins if it can, blocks if it must, otherwise plays center-first.

    Written independently of the agent's code, using a plain grid.
    """

    def __init__(self, seat):
        self.seat, self.name = seat, "rules"

    def ask(self, message, timeout):
        if message["type"] == "init":
            return {}
        history = message["history"]
        me = next(e["event"]["you"] for e in history if e["event"]["type"] == "game-started")
        board = [[0] * COLS for _ in range(ROWS)]
        for entry in history:
            ev = entry["event"]
            if ev["type"] == "disc-dropped":
                board[ev["row"]][ev["column"]] = ev["player"]
        legal = [c for c in CENTER_FIRST if board[0][c] == 0]
        for player in (me, 3 - me):                 # first look for our win, then their win
            for col in legal:
                row = max(r for r in range(ROWS) if board[r][col] == 0)
                board[row][col] = player
                won = winner(board) == player
                board[row][col] = 0
                if won:
                    return {"type": "disc-dropped", "column": col}
        return {"type": "disc-dropped", "column": legal[0]}

    def close(self):
        pass


# ---------------------------------------------------------------- referee

def winner(board):
    """1 or 2 if that player has four in a row, else 0."""
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if not p:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                if all(0 <= r + k * dr < ROWS and 0 <= c + k * dc < COLS
                       and board[r + k * dr][c + k * dc] == p for k in range(4)):
                    return p
    return 0


def show(board):
    for row in board:
        print("   " + " ".join(".XO"[v] for v in row))
    print("   0 1 2 3 4 5 6")


def play_game(red, yellow, verbose):
    """Run one game. Returns (result, reason, stats).

    result: 1 = red won, 2 = yellow won, 0 = draw
    """
    players = {1: red, 2: yellow}
    seats = {1: "seat-1", 2: "seat-2"}
    think_time = {1: 0.0, 2: 0.0}
    slowest = {1: 0.0, 2: 0.0}
    game_start = time.monotonic()

    def stats():
        return {"total": time.monotonic() - game_start,
                "think": think_time, "slowest": slowest}

    # Initialization
    for p in (1, 2):
        try:
            reply = players[p].ask({"type": "init", "game": "connect-four", "seat": seats[p]},
                                   INIT_LIMIT)
            if reply != {}:
                return 3 - p, f"player {p} sent {reply} to init instead of {{}}", stats()
        except Exception as error:
            return 3 - p, f"player {p} failed init: {error}", stats()

    histories = {p: [{"seq": 0, "atMs": 0, "event": {
        "type": "game-started", "red": seats[1], "yellow": seats[2],
        "you": p, "columns": COLS, "rows": ROWS}}] for p in (1, 2)}
    board = [[0] * COLS for _ in range(ROWS)]
    seq, turn, p = 1, 0, 1

    while True:
        turn += 1
        request = {"type": "decision",
                   "decision": {"requestId": f"turn:{turn}", "seat": seats[p],
                                "kind": "disc-dropped"},
                   "history": histories[p], "deadlineMs": DEADLINE_MS}
        start = time.monotonic()
        try:
            reply = players[p].ask(request, DEADLINE_MS / 1000)
        except Exception as error:
            return 3 - p, f"player {p} ({players[p].name}) forfeits: {error}", stats()
        took = time.monotonic() - start
        think_time[p] += took
        slowest[p] = max(slowest[p], took)

        col = reply.get("column")
        if (reply.get("type") != "disc-dropped" or not isinstance(col, int)
                or not 0 <= col < COLS or board[0][col] != 0 or len(reply) != 2):
            return 3 - p, f"player {p} ({players[p].name}) forfeits: illegal reply {reply}", stats()

        row = max(r for r in range(ROWS) if board[r][col] == 0)
        board[row][col] = p
        event = {"seq": seq, "atMs": int((time.monotonic() - game_start) * 1000), "event": {
            "type": "disc-dropped", "seat": seats[p], "column": col, "row": row, "player": p}}
        seq += 1
        for q in (1, 2):
            histories[q].append(event)
        if verbose:
            print(f"   turn {turn:2d}: {'XO'[p - 1]} ({players[p].name:6s}) -> column {col}   {took:5.2f}s")

        if time.monotonic() - game_start > MATCH_LIMIT:
            return 0, "match time limit exceeded (no result)", stats()
        w = winner(board)
        if w or all(board[0]):
            if verbose:
                show(board)
            return w, "four in a row" if w else "board full", stats()
        p = 3 - p


# ---------------------------------------------------------------- main

def make_opponent(kind, seat, game_number):
    if kind == "random":
        return RandomBot(seat)
    if kind == "rules":
        return RulesBot(seat)
    return AgentProcess(seat, LOG_DIR / f"game{game_number}-{seat}-opponent.log")


def main():
    parser = argparse.ArgumentParser(description="Local Connect Four matches")
    parser.add_argument("--vs", choices=["random", "rules", "agent"], default="random")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    LOG_DIR.mkdir(exist_ok=True)

    tally = {"won": 0, "lost": 0, "draw": 0}
    for g in range(1, args.games + 1):
        agent_color = 1 if g % 2 == 1 else 2          # alternate red and yellow
        agent_seat = "seat-1" if agent_color == 1 else "seat-2"
        other_seat = "seat-2" if agent_color == 1 else "seat-1"
        agent = AgentProcess(agent_seat, LOG_DIR / f"game{g}-{agent_seat}.log")
        opponent = make_opponent(args.vs, other_seat, g)
        red, yellow = (agent, opponent) if agent_color == 1 else (opponent, agent)

        print(f"\nGame {g}: agent is {'Red (X)' if agent_color == 1 else 'Yellow (O)'} "
              f"vs {args.vs}")
        try:
            result, reason, st = play_game(red, yellow, verbose=not args.quiet)
        finally:
            agent.close()
            opponent.close()

        if result == 0:
            outcome = "draw"
        elif args.vs == "agent":
            outcome = "won" if result == 1 else "lost"   # self-play: report from Red's side
        else:
            outcome = "won" if result == agent_color else "lost"
        tally[outcome] += 1
        print(f"   result: {outcome.upper()} ({reason})")
        print(f"   game time {st['total']:.1f}s of {MATCH_LIMIT}s | agent thinking "
              f"{st['think'][agent_color]:.1f}s, slowest move {st['slowest'][agent_color]:.2f}s")

    print(f"\nSummary vs {args.vs}: {tally['won']} won, {tally['lost']} lost, "
          f"{tally['draw']} drawn" + ("  (self-play: counted from Red's side)"
                                      if args.vs == "agent" else ""))


if __name__ == "__main__":
    main()