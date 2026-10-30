"""Clue deduction: the notebook of what we know about every card.

Each cell of the notebook is one (card, place) pair:
    True  = the card is definitely in that place   (✓)
    False = the card is definitely not there        (✗)
    None  = not known yet                           (?)

Places are the player seats plus the envelope.
"""

ENVELOPE = "envelope"


class Contradiction(Exception):
    """Raised when the facts can't all be true (a bug, or history read wrongly)."""

class Notebook:
    def __init__(self, cards, seats):
        """Create a notebook where every cell is unknown.

        cards: list of card IDs, like ["suspect:plum", "weapon:rope", ...]
        seats: list of player seat IDs, like ["seat-1", "seat-2", "seat-3"]
        """
        self.cards = list(cards)
        self.places = list(seats) + [ENVELOPE]

        # TODO: create self.cells: a dictionary with one key for every
        # (card, place) pair, where every value starts as None.
        self.cells = {}

        for card in self.cards:
            for place in self.places:
                self.cells[(card, place)] = None
        
    def get(self, card, place):
        """Return True (✓), False (✗), or None (?) for this cell."""
        # TODO
        return self.cells[(card,place)]
            

    def set(self, card, place, value):
        """Record that `card` is (value=True) or is not (value=False) in `place`.

        Returns True if this is new information, False if it was already known.
        Raises Contradiction if the cell already holds the opposite value.
        """
        # TODO
        
        if not isinstance(value, bool):
            raise ValueError(f"set() needs True or False, got {value!r}")
        cur_val = self.cells[(card, place)]

        if cur_val is None:
            self.cells[(card, place)] = value
            return True
        if cur_val == value:
            return False
        raise Contradiction(
    f"{card} in {place}: already {cur_val}, but told {value}"
)       
                  