#!/usr/bin/env python3
"""Crucible agent entrypoint.

The platform talks to this process through standard input and output:
  - It sends one JSON request per line on stdin.
  - We reply with one JSON object per line on stdout.
  - Logs must go to stderr, never stdout, or they corrupt the protocol.
The process stays alive for the whole match.
"""
import importlib
import json
import sys
import time
import traceback

# Which module plays which game. The key is the "game" value sent in "init".
# Python finds the "games" package because it lives next to this file in src/.
GAME_MODULES = {
    "connect-four": "games.connect_four",
    # "clue": "games.clue",
    # "secret-dictator": "games.secret_dictator",
}

# ---------------------------------------------------------------- logging
# The platform keeps at most 200 log lines of 4,000 characters per seat.
MAX_LOG_LINES = 190
MAX_LOG_CHARS = 3900
_log_count = 0


def log(*parts):
    """Write one line to stderr, respecting the platform's log limits."""
    global _log_count
    if _log_count >= MAX_LOG_LINES:
        return
    _log_count += 1
    text = " ".join(str(p) for p in parts).replace("\n", " | ")
    sys.stderr.write(text[:MAX_LOG_CHARS] + "\n")
    sys.stderr.flush()


# ---------------------------------------------------------------- output

def send(obj):
    """Write one JSON object as a single line and flush immediately."""
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------- handlers

def load_game(game):
    """Import the module for this game, or return None if unsupported."""
    name = GAME_MODULES.get(game)
    if name is None:
        log("unsupported game:", game)
        return None
    return importlib.import_module(name)


def handle_decision(module, request):
    """Get a move from the game module. Never let an exception escape.

    Order of attempts:
      1. module.decide(request)   - the real strategy
      2. module.fallback(request) - a simple, always-legal move
      3. {}                       - last resort (invalid, but keeps us alive)
    """
    start = time.monotonic()
    try:
        response = module.decide(request)
        log("decide ok in %.2fs: %s" % (time.monotonic() - start, json.dumps(response)))
        return response
    except Exception:
        log("decide crashed:", traceback.format_exc(limit=3))

    try:
        response = module.fallback(request)
        log("fallback used:", json.dumps(response))
        return response
    except Exception:
        log("fallback crashed:", traceback.format_exc(limit=3))

    return {}


# ---------------------------------------------------------------- main loop

def main():
    module = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            log("could not parse input:", line[:200])
            continue

        msg_type = msg.get("type")

        if msg_type == "init":
            # Load the game module, then always acknowledge with {}.
            try:
                module = load_game(msg.get("game"))
                if module is not None and hasattr(module, "init"):
                    module.init(msg)
            except Exception:
                log("init failed:", traceback.format_exc(limit=3))
            send({})

        elif msg_type == "decision":
            if module is None:
                log("decision received but no game module is loaded")
                send({})
            else:
                send(handle_decision(module, msg))

        else:
            log("ignoring unknown message type:", msg_type)


if __name__ == "__main__":
    main()