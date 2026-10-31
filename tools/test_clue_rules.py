#!/usr/bin/env python3
"""Tests for Tasks 2-4: own hand, groups, the exactly-N helper, and Rules 1-3.
Run from the project root:
    python3 tools/test_clue_rules.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from games.clue.deduction import Notebook, Contradiction, ENVELOPE, CATEGORIES

failures = 0


def check(name, condition, detail=""):
    global failures
    print(("PASS  " if condition else "FAIL  ") + name + (f"   ({detail})" if detail else ""))
    if not condition:
        failures += 1


def raises(error_type, function, *args):
    """True if calling function(*args) raises error_type."""
    try:
        function(*args)
    except error_type:
        return True
    except Exception:
        return False
    return False


# A real 21-card deck and a 3-player game where everyone holds 6 cards.
SUSPECTS = ["scarlet", "mustard", "plum", "green", "white", "peacock"]
WEAPONS = ["rope", "lead-pipe", "knife", "wrench", "candlestick", "pistol"]
ROOMS = ["kitchen", "ballroom", "conservatory", "dining-room", "billiard-room",
         "library", "lounge", "hall", "study"]
CARDS = ([f"suspect:{s}" for s in SUSPECTS] + [f"weapon:{w}" for w in WEAPONS]
         + [f"room:{r}" for r in ROOMS])
SEATS = ["seat-1", "seat-2", "seat-3"]
SIZES = {"seat-1": 6, "seat-2": 6, "seat-3": 6}
MY_HAND = ["suspect:mustard", "suspect:white", "weapon:rope",
           "weapon:knife", "room:study", "room:hall"]


def new_notebook(sizes=SIZES):
    return Notebook(CARDS, SEATS, sizes)


def column_values(nb, seat):
    return [nb.get(card, seat) for card in CARDS]


def run_rules_until_done(nb):
    """Repeat apply_rules until it finds nothing new. Returns how many passes it took."""
    passes = 0
    while nb.apply_rules():
        passes += 1
        if passes > 100:
            raise RuntimeError("apply_rules never stopped returning True")
    return passes


# ---------------------------------------------------------------- setup
print("Setup")
nb = new_notebook()
check("seats are stored separately from places", nb.seats == SEATS)
check("places are the seats plus the envelope", nb.places == SEATS + [ENVELOPE])
check("hand sizes are stored", nb.hand_sizes == SIZES)
check("hand sizes are a copy, not the caller's dictionary", nb.hand_sizes is not SIZES)
check("hand sizes default to an empty dictionary", Notebook(CARDS, SEATS).hand_sizes == {})
check("CATEGORIES covers every card",
      all(any(card.startswith(p) for p in CATEGORIES) for card in CARDS))

# ---------------------------------------------------------------- groups
print("\nGroups")
nb = new_notebook()
check("row has one cell per place, envelope last",
      nb.row("suspect:plum") == [("suspect:plum", p) for p in SEATS + [ENVELOPE]])
check("column has one cell per card",
      nb.column("seat-2") == [(card, "seat-2") for card in CARDS])
suspects = nb.envelope_category("suspect:")
check("envelope_category('suspect:') has the 6 suspects, all in the envelope",
      len(suspects) == 6 and all(place == ENVELOPE and card.startswith("suspect:")
                                 for card, place in suspects))
check("envelope_category('room:') has the 9 rooms", len(nb.envelope_category("room:")) == 9)
check("building groups doesn't change any cell",
      all(value is None for value in nb.cells.values()))

# ---------------------------------------------------------------- own hand
print("\nYour own hand")
nb = new_notebook()
nb.record_own_hand("seat-1", MY_HAND)
mine = column_values(nb, "seat-1")
check("your column has 6 ✓ and 15 ✗", mine.count(True) == 6 and mine.count(False) == 15,
      f"{mine.count(True)} ✓, {mine.count(False)} ✗")
check("each card in your hand is ✓", all(nb.get(c, "seat-1") is True for c in MY_HAND))
check("other columns are untouched",
      all(nb.get(c, p) is None for c in CARDS for p in ["seat-2", "seat-3", ENVELOPE]))

try:
    nb.record_own_hand("seat-1", MY_HAND)
    check("recording the same hand twice is harmless", True)
except Exception as error:
    check("recording the same hand twice is harmless", False, repr(error))

other_hand = ["suspect:plum"] + MY_HAND[1:]
check("recording a different hand raises Contradiction",
      raises(Contradiction, nb.record_own_hand, "seat-1", other_hand))

fresh = new_notebook()
check("a card that isn't in the deck raises ValueError",
      raises(ValueError, fresh.record_own_hand, "seat-1", ["weapon:Rope"]))
check("...and nothing was written before the error",
      all(value is None for value in fresh.cells.values()))
check("an unknown seat raises an error",
      raises(KeyError, new_notebook().record_own_hand, "seat-9", MY_HAND))

# ---------------------------------------------------------------- apply_exactly
print("\nThe exactly-N helper (Plum's row, n = 1)")
PLUM = "suspect:plum"


def plum_row(values):
    """A notebook where Plum's row holds `values` for seat-1, seat-2, seat-3, envelope."""
    nb = new_notebook()
    for place, value in zip(SEATS + [ENVELOPE], values):
        if value is not None:
            nb.set(PLUM, place, value)
    return nb


nb = plum_row([False, True, None, None])
changed = nb.apply_exactly(nb.row(PLUM), 1)
check("one ✓ already: the ? cells become ✗",
      changed is True and nb.get(PLUM, "seat-3") is False and nb.get(PLUM, ENVELOPE) is False)

nb = plum_row([False, False, None, False])
changed = nb.apply_exactly(nb.row(PLUM), 1)
check("only one possibility left: it becomes ✓", changed is True and nb.get(PLUM, "seat-3") is True)

nb = plum_row([False, None, None, None])
changed = nb.apply_exactly(nb.row(PLUM), 1)
check("several possibilities: nothing changes",
      changed is False and nb.get(PLUM, "seat-2") is None)

nb = plum_row([False, True, False, False])
check("already complete: returns False", nb.apply_exactly(nb.row(PLUM), 1) is False)

nb = plum_row([False, True, True, None])
check("two ✓ in one row raises Contradiction", raises(Contradiction, nb.apply_exactly, nb.row(PLUM), 1))

nb = plum_row([False, False, False, False])
check("no possible place raises Contradiction", raises(Contradiction, nb.apply_exactly, nb.row(PLUM), 1))

# ---------------------------------------------------------------- the rules
print("\nRule 1: each card is in exactly one place")
nb = new_notebook()
nb.record_own_hand("seat-1", MY_HAND)
check("apply_rules reports a change", nb.apply_rules() is True)
check("your cards are ✗ for the other players and the envelope",
      all(nb.get(c, p) is False for c in MY_HAND for p in ["seat-2", "seat-3", ENVELOPE]))
check("cards you don't hold are still unknown elsewhere",
      nb.get("suspect:plum", "seat-2") is None and nb.get("suspect:plum", ENVELOPE) is None)
check("a second pass finds nothing new", nb.apply_rules() is False)

print("\nRule 2: the envelope holds one card of each category")
nb = new_notebook({})                       # no hand sizes, so only Rules 1 and 2 apply
for suspect in ["scarlet", "mustard", "plum", "green", "white"]:
    nb.set(f"suspect:{suspect}", ENVELOPE, False)
nb.apply_rules()
check("five suspects ruled out: the sixth is in the envelope",
      nb.get("suspect:peacock", ENVELOPE) is True)
run_rules_until_done(nb)
check("...and then Rule 1 rules Peacock out for every player",
      all(nb.get("suspect:peacock", seat) is False for seat in SEATS))

nb = new_notebook({})
nb.set("weapon:pistol", ENVELOPE, True)
nb.apply_rules()
check("a weapon known to be in the envelope rules out the other weapons there",
      all(nb.get(f"weapon:{w}", ENVELOPE) is False for w in WEAPONS if w != "pistol"))

print("\nRule 3: each player holds exactly their hand size")
nb = new_notebook({"seat-1": 6, "seat-2": 3, "seat-3": 9})
for card in ["suspect:plum", "weapon:wrench", "room:kitchen"]:
    nb.set(card, "seat-2", True)
nb.apply_rules()
check("a full hand: the rest of that column becomes ✗",
      column_values(nb, "seat-2").count(True) == 3 and column_values(nb, "seat-2").count(False) == 18)

nb = new_notebook({"seat-1": 6, "seat-2": 3, "seat-3": 9})
nb.set("suspect:plum", "seat-2", True)
for card in CARDS:
    if card not in ("suspect:plum", "weapon:wrench", "room:kitchen"):
        nb.set(card, "seat-2", False)
nb.apply_rules()
check("just enough possibilities: they all become ✓",
      nb.get("weapon:wrench", "seat-2") is True and nb.get("room:kitchen", "seat-2") is True)

nb = new_notebook({})
nb.set("suspect:plum", "seat-2", True)
try:
    nb.apply_rules()
    check("no hand sizes: Rule 3 is skipped without errors", True)
except Exception as error:
    check("no hand sizes: Rule 3 is skipped without errors", False, repr(error))

nb = new_notebook({"seat-1": 6, "seat-2": 2, "seat-3": 10})
for card in ["suspect:plum", "weapon:wrench", "room:kitchen"]:
    nb.set(card, "seat-2", True)
check("more ✓ than the hand size raises Contradiction", raises(Contradiction, nb.apply_rules))

print("\nAll three rules together")
# seat-1 is us. seat-2 is fully known by elimination; Rules 1-3 must work together.
nb = new_notebook()
nb.record_own_hand("seat-1", MY_HAND)
seat2 = ["suspect:scarlet", "suspect:green", "weapon:wrench", "weapon:pistol",
         "room:kitchen", "room:ballroom"]
for card in seat2:
    nb.set(card, "seat-2", True)
passes = run_rules_until_done(nb)
# Rule 3 fills the rest of seat-2 with ✗. Rule 1 then rules seat-2's cards out of
# seat-3 and the envelope. Suspects left for the envelope or seat-3: plum, peacock.
check("rules repeat until nothing changes, then stop", passes >= 1, f"{passes} pass(es)")
check("seat-2's other cards are all ✗", column_values(nb, "seat-2").count(False) == 15)
check("cards held by seat-1 or seat-2 are ✗ in the envelope",
      all(nb.get(c, ENVELOPE) is False for c in MY_HAND + seat2))
check("open cards are still unknown (not guessed)",
      nb.get("suspect:plum", ENVELOPE) is None and nb.get("suspect:plum", "seat-3") is None)

print("\nAll tests passed." if failures == 0 else f"\n{failures} test(s) failed.")