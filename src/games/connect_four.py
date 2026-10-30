"""Connect Four player: bitboard foundation.

BOARD LAYOUT
Each column gets 7 bits: 6 real cells plus one always-empty spare on top.
    bit number = column * 7 + row_from_bottom

         col0 col1 col2 col3 col4 col5 col6
 spare     6   13   20   27   34   41   48
 row 5     5   12   19   26   33   40   47
 ...
 row 0     0    7   14   21   28   35   42   <- bottom

We store two integers:
    mask     = every occupied cell (both colors)
    position = cells owned by the player about to move
The opponent's discs are always mask ^ position.
"""
import json
import sys
import time
from pathlib import Path

WIDTH = 7
HEIGHT = 6
H1 = HEIGHT + 1                  # bits per column, including the spare

# One bit at the bottom of every column: 1 + 2^7 + 2^14 + ... + 2^42
BOTTOM_MASK = sum(1 << (col * H1) for col in range(WIDTH))
# All 42 real cells (spare bits excluded)
BOARD_MASK = BOTTOM_MASK * ((1 << HEIGHT) - 1)

CENTER_FIRST = [3, 2, 4, 1, 5, 0, 6]


# ---------------------------------------------------------------- single cells & columns

def bottom_bit(col):
    """The bit for the bottom cell of a column."""
    return 1 << (col * H1)


def top_bit(col):
    """The bit for the top real cell of a column (row 5)."""
    return 1 << (col * H1 + HEIGHT - 1)


def column_bits(col):
    """All 6 real cells of one column."""
    return ((1 << HEIGHT) - 1) << (col * H1)


# ---------------------------------------------------------------- moves

def can_play(mask, col):
    """A column is playable if its top real cell is empty."""
    return (mask & top_bit(col)) == 0


def landing_cells(mask):
    """One bit per non-full column: where a dropped disc would land.

    Adding the bottom bit of every column makes a carry ripple up each
    column to its first empty cell (the trick from our lessons).
    """
    return (mask + BOTTOM_MASK) & BOARD_MASK


def play(position, mask, col):
    """Drop a disc in `col` for the player to move.

    Returns the new (position, mask), where position now belongs to the
    OTHER player, since it's their turn next.
    """
    new_mask = mask | (mask + bottom_bit(col))
    # Before the move, the opponent's discs are mask ^ position.
    # After the move it's the opponent's turn, so they become `position`.
    new_position = position ^ mask
    return new_position, new_mask


# ---------------------------------------------------------------- wins & threats

# Shift amounts for the four directions (see the bit layout above):
#   1 = vertical, 7 = horizontal, 8 = diagonal /, 6 = diagonal \
DIRECTIONS = (1, H1, H1 + 1, H1 - 1)


def has_four(discs):
    """True if this set of discs contains four in a row anywhere."""
    for s in DIRECTIONS:
        pairs = discs & (discs >> s)           # a disc with a neighbor s away
        if pairs & (pairs >> (2 * s)):         # two such pairs, 2s apart
            return True
    return False


def threat_cells(discs, mask):
    """Empty cells that would complete four in a row for `discs`.

    For each direction we check the four ways an empty cell can be part of
    a line: as the end of three discs (on either side), or as a gap inside
    X X _ X / X _ X X patterns.
    """
    # Vertical: only possible with three discs directly below.
    r = (discs << 1) & (discs << 2) & (discs << 3)

    for s in (H1, H1 + 1, H1 - 1):
        pair_below = (discs << s) & (discs << (2 * s))   # discs at -s and -2s
        r |= pair_below & (discs << (3 * s))             # X X X _
        r |= pair_below & (discs >> s)                   # X X _ X
        pair_above = (discs >> s) & (discs >> (2 * s))   # discs at +s and +2s
        r |= pair_above & (discs << s)                   # X _ X X
        r |= pair_above & (discs >> (3 * s))             # _ X X X

    return r & (BOARD_MASK ^ mask)                       # keep only empty cells


# ---------------------------------------------------------------- rebuilding from history

def rebuild(history):
    """Replay every disc-dropped event to get (position, mask, moves_played)."""
    drops = sorted(
        (h for h in history if h.get("event", {}).get("type") == "disc-dropped"),
        key=lambda h: h.get("seq", 0),
    )
    position, mask = 0, 0
    for entry in drops:
        col = entry["event"]["column"]
        position, mask = play(position, mask, col)
    return position, mask, len(drops)


def legal_columns(mask):
    return [c for c in CENTER_FIRST if can_play(mask, c)]


def column_of(bit):
    """Which column a single-bit value belongs to."""
    return (bit.bit_length() - 1) // H1


# ---------------------------------------------------------------- opening book
# Precomputed best moves for early positions, generated offline by
# tools/build_book.py and stored next to this file. If the file is missing
# or broken, the book is simply empty and the search plays every move.

BOOK_PATH = Path(__file__).with_name("c4_book.json")


def mirror_key(key):
    """The key of the left-right mirror image of a position.

    Each column's part of the key fits in its own 7 bits, so mirroring
    just moves column c's 7 bits to column 6 - c.
    """
    result = 0
    for col in range(WIDTH):
        bits = (key >> (col * H1)) & ((1 << H1) - 1)
        result |= bits << ((WIDTH - 1 - col) * H1)
    return result


def load_book(path=BOOK_PATH):
    """Read the book file into {position_key: column}. Never raises."""
    try:
        with open(path) as f:
            data = json.load(f)
        return {int(key): col for key, col in data["moves"].items()}
    except Exception:
        return {}


BOOK = load_book()


def book_move(position, mask, book=None):
    """The book's column for this position (or its mirror image), or None."""
    if book is None:
        book = BOOK
    key = position + mask
    col = book.get(key)
    if col is None:
        mirrored = book.get(mirror_key(key))
        if mirrored is not None:
            col = WIDTH - 1 - mirrored
    if col is not None and 0 <= col < WIDTH and can_play(mask, col):
        return col
    return None


# ---------------------------------------------------------------- search settings

CELLS = WIDTH * HEIGHT     # 42: the board is full after this many moves
WIN = 1_000_000            # base score for a win; far above any evaluation
INF = 10 * WIN             # bigger than any possible score
PROVEN = WIN - CELLS       # any score at least this big is a proven win or loss

TIME_BUDGET = 3.0          # seconds per move; the whole match is capped at 5 minutes
CLOCK_CHECK = 1023         # check the clock every 1,024 positions

# Transposition table flags: what a stored score means.
EXACT = 0                  # the true score
LOWER = 1                  # the true score is at least this (search was cut off high)
UPPER = 2                  # the true score is at most this (no move beat alpha)
MAX_TABLE_ENTRIES = 500_000   # roughly 100 MB; we have 512 MiB per seat

# Rows for threat parity, counted 1 to 6 from the bottom.
# Red (moves first) benefits from threats on odd rows, Yellow on even rows.
ODD_ROWS = BOTTOM_MASK * 0b010101    # rows 1, 3, 5 (bits 0, 2, 4 of each column)
EVEN_ROWS = BOTTOM_MASK * 0b101010   # rows 2, 4, 6 (bits 1, 3, 5 of each column)
CENTER_COLUMN = column_bits(3)

# Evaluation weights (starting values; tune them by testing).
THREAT_WEIGHT = 4
PARITY_WEIGHT = 3
CENTER_WEIGHT = 2


class TimeUp(Exception):
    """Raised inside the search when the time budget runs out."""


# ---------------------------------------------------------------- move helpers

def non_losing_moves(position, mask):
    """Landing cells that don't let the opponent win on their next move."""
    possible = landing_cells(mask)
    opponent_threats = threat_cells(position ^ mask, mask)
    forced = possible & opponent_threats
    if forced:
        if forced & (forced - 1):
            return 0                 # two immediate threats: can't block both
        possible = forced            # exactly one: we must block it
    return possible & ~(opponent_threats >> 1)


def evaluate(position, mask, moves):
    """Estimated score of an unfinished position, from the mover's view."""
    opponent = position ^ mask
    my_threats = threat_cells(position, mask)
    their_threats = threat_cells(opponent, mask)

    # 1. More threats is better.
    score = THREAT_WEIGHT * (my_threats.bit_count() - their_threats.bit_count())

    # 2. Threats on a player's "good" rows count extra.
    if moves % 2 == 0:               # even number of discs played: Red to move
        my_rows, their_rows = ODD_ROWS, EVEN_ROWS
    else:
        my_rows, their_rows = EVEN_ROWS, ODD_ROWS
    score += PARITY_WEIGHT * ((my_threats & my_rows).bit_count()
                              - (their_threats & their_rows).bit_count())

    # 3. Discs in the center column are part of the most possible lines.
    score += CENTER_WEIGHT * ((position & CENTER_COLUMN).bit_count()
                              - (opponent & CENTER_COLUMN).bit_count())
    return score


def ordered_moves(position, mask, candidates, first_col=None):
    """Candidate moves as (score, column, move_bit), most promising first.

    `first_col`, if given, is the best move remembered from an earlier
    search of this position; it always goes to the front.
    """
    moves = []
    for col in CENTER_FIRST:
        move = candidates & column_bits(col)
        if move:
            score = threat_cells(position | move, mask | move).bit_count()
            if col == first_col:
                score += 100
            moves.append((score, col, move))
    moves.sort(key=lambda m: m[0], reverse=True)
    return moves


# ---------------------------------------------------------------- search

class Search:
    """State shared by one move's search: counters, table, and deadline."""

    def __init__(self, prune=True, use_table=True, deadline=None):
        self.nodes = 0
        self.table_hits = 0
        self.prune = prune
        self.use_table = use_table
        self.deadline = deadline   # time.monotonic() value, or None for no limit
        self.table = {}            # key -> (depth, flag, score, best_col)

    def negamax(self, position, mask, moves, depth, alpha, beta):
        """Score of this position for the player to move.

        A win scores WIN minus the number of discs on the board when the
        game ends, so faster wins (and slower losses) score higher.
        """
        self.nodes += 1
        if (self.deadline is not None and (self.nodes & CLOCK_CHECK) == 0
                and time.monotonic() > self.deadline):
            raise TimeUp

        if moves == CELLS:
            return 0                                   # full board: draw

        if threat_cells(position, mask) & landing_cells(mask):
            return WIN - (moves + 1)                   # we win with our next disc

        candidates = non_losing_moves(position, mask)
        if candidates == 0:
            return -(WIN - (moves + 2))                # opponent wins next turn

        if depth == 0:
            return evaluate(position, mask, moves)

        # ---- transposition table lookup
        alpha_original = alpha
        key = position + mask
        remembered_col = None
        entry = self.table.get(key) if self.use_table else None
        if entry is not None:
            stored_depth, flag, stored_score, remembered_col = entry
            if stored_depth >= depth:
                self.table_hits += 1
                if flag == EXACT:
                    return stored_score
                if flag == LOWER:
                    alpha = max(alpha, stored_score)
                elif flag == UPPER:
                    beta = min(beta, stored_score)
                if alpha >= beta:
                    return stored_score

        # ---- search the moves
        best, best_col = -INF, None
        for _, col, move in ordered_moves(position, mask, candidates, remembered_col):
            score = -self.negamax(position ^ mask, mask | move, moves + 1,
                                  depth - 1, -beta, -alpha)
            if score > best:
                best, best_col = score, col
            if score > alpha:
                alpha = score
            if self.prune and alpha >= beta:
                break

        # ---- transposition table store
        if self.use_table:
            if best <= alpha_original:
                flag = UPPER
            elif best >= beta:
                flag = LOWER
            else:
                flag = EXACT
            if len(self.table) >= MAX_TABLE_ENTRIES:
                self.table.clear()
            self.table[key] = (depth, flag, best, best_col)

        return best

    def root(self, position, mask, moves, depth):
        """Search every move from the current position to `depth`.

        Returns (best_column, best_score). Assumes there is no immediate
        win (the caller checks that first).
        """
        candidates = non_losing_moves(position, mask) or landing_cells(mask)
        remembered = self.table.get(position + mask)
        first_col = remembered[3] if remembered else None

        best_col, best_score = None, -INF
        alpha, beta = -INF, INF
        for _, col, move in ordered_moves(position, mask, candidates, first_col):
            score = -self.negamax(position ^ mask, mask | move, moves + 1,
                                  depth - 1, -beta, -alpha)
            if score > best_score:
                best_col, best_score = col, score
            alpha = max(alpha, score)

        if self.use_table:
            self.table[position + mask] = (depth, EXACT, best_score, best_col)
        return best_col, best_score


def immediate_win(position, mask):
    """Column that wins right now, or None."""
    wins = threat_cells(position, mask) & landing_cells(mask)
    return column_of(wins & -wins) if wins else None


def best_move(position, mask, moves, depth, prune=True, use_table=True):
    """Fixed-depth search. Returns (column, score, search). Used by the tests."""
    search = Search(prune, use_table)
    col = immediate_win(position, mask)
    if col is not None:
        return col, WIN - (moves + 1), search
    col, score = search.root(position, mask, moves, depth)
    return col, score, search


def think(position, mask, moves, budget, use_book=True):
    """Iterative deepening within `budget` seconds.

    Returns (column, score, depth_completed, search, reason).
    `use_book=False` is for the book builder, which must not read its own output.
    """
    search = Search(deadline=time.monotonic() + budget)

    col = immediate_win(position, mask)
    if col is not None:
        return col, WIN - (moves + 1), 0, search, "immediate win"

    if use_book:
        col = book_move(position, mask)
        if col is not None:
            return col, 0, 0, search, "opening book"

    legal = legal_columns(mask)
    if len(legal) == 1:
        return legal[0], 0, 0, search, "only legal move"

    # A safe default in case even depth 1 runs out of time.
    candidates = non_losing_moves(position, mask) or landing_cells(mask)
    best_col = ordered_moves(position, mask, candidates)[0][1]
    best_score, completed, reason = 0, 0, "default move"

    remaining = CELLS - moves
    for depth in range(1, remaining + 1):
        try:
            col, score = search.root(position, mask, moves, depth)
        except TimeUp:
            reason = "time up during depth %d" % depth
            break
        best_col, best_score, completed = col, score, depth
        if abs(score) >= PROVEN:
            reason = "proven win" if score > 0 else "proven loss"
            break
        if depth == remaining:
            reason = "searched to the end of the game"
    return best_col, best_score, completed, search, reason


# ---------------------------------------------------------------- protocol entry points

def time_budget(request):
    """Seconds to spend on this move: our budget, but never a big share of the deadline."""
    deadline_seconds = request.get("deadlineMs", 15000) / 1000
    return max(0.2, min(TIME_BUDGET, deadline_seconds * 0.25))


def decide(request):
    position, mask, moves = rebuild(request.get("history", []))
    col, score, depth, search, reason = think(position, mask, moves, time_budget(request))
    sys.stderr.write("c4 move %d: col %d score %d depth %d nodes %d (%s)\n"
                     % (moves, col, score, depth, search.nodes, reason))
    sys.stderr.flush()
    return {"type": "disc-dropped", "column": col}


def fallback(request):
    """Any legal column, center first, using only simple counting."""
    heights = [0] * WIDTH
    for entry in request.get("history", []):
        event = entry.get("event", {})
        if event.get("type") == "disc-dropped":
            heights[event["column"]] += 1
    for col in CENTER_FIRST:
        if heights[col] < HEIGHT:
            return {"type": "disc-dropped", "column": col}
    return {"type": "disc-dropped", "column": 3}