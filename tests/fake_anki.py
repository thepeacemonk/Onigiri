"""Fakes modelling the slice of Anki's API the deck-browser render touches.

Kept intentionally minimal: enough for onigiri_renderer.render_onigiri_
deck_browser() to produce its full HTML headlessly, nothing more.
"""

from collections import namedtuple

from conftest import FakeDb, FakeMw  # reuse the sqlite-backed db facade

DeckInfo = namedtuple("DeckInfo", ["id", "name"])


class FakeDbWithStats(FakeDb):
    """FakeDb plus the revlog columns the dashboard widgets query."""

    def __init__(self):
        super().__init__()
        self.conn.execute("ALTER TABLE revlog ADD COLUMN ease INTEGER DEFAULT 1")
        self.conn.execute("ALTER TABLE revlog ADD COLUMN time INTEGER DEFAULT 5000")
        self.conn.commit()

    def first(self, query, *args):
        row = self.execute(query, args).fetchone()
        return tuple(row) if row else None


class DeckNode:
    """Minimal stand-in for anki.decks.DeckTreeNode."""

    def __init__(self, deck_id, name, **kwargs):
        self.deck_id = deck_id
        self.name = name
        self.level = 0
        self.collapsed = False
        self.filtered = False
        self.children = []
        self.new_count = 0
        self.learn_count = 0
        self.review_count = 0
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_child(self, node):
        node.level = self.level + 1
        self.children.append(node)
        return node


class FakeDecks:
    def __init__(self, decks=None):
        # decks: {deck_id: {"name": str, ...}}
        self._decks = decks or {}
        self.current_id = min(self._decks) if self._decks else 1

    def all_names_and_ids(self):
        return [DeckInfo(did, d["name"]) for did, d in sorted(self._decks.items())]

    def get(self, did, default=None):
        return self._decks.get(int(did), default)

    def get_current_id(self):
        return self.current_id

    def due_tree_from_decks(self):
        """Build a DeckNode tree honouring 'Parent::Child' names."""
        root = DeckNode(0, "root")
        branches = {}
        for did in sorted(self._decks):
            name = self._decks[did]["name"]
            parts = name.split("::")
            full = []
            parent = root
            for part in parts:
                full.append(part)
                key = "::".join(full)
                if key not in branches:
                    node = DeckNode(did if key == name else -did, part, new_count=7, learn_count=3, review_count=11)
                    branches[key] = parent.add_child(node)
                parent = branches[key]
        return root


class RecordingWeb:
    """Captures what the renderer would send to Anki's webview."""

    def __init__(self):
        self.calls = []

    def stdHtml(self, body, css=None, js=None, context=None, **kwargs):
        self.calls.append({"body": body, "css": css, "js": js, "context": context})

    @property
    def last_body(self):
        return self.calls[-1]["body"]


class FakeDeckBrowser:
    """Stand-in for aqt.deckbrowser.DeckBrowser as consumed by the renderer."""

    def __init__(self, mw, web=None):
        self.mw = mw
        self.web = web or RecordingWeb()


def make_render_mw(reviews_today=12, reviews_yesterday=8):
    """A FakeMw whose collection looks like a small real-life collection."""
    mw = FakeMw()
    mw.col.db = FakeDbWithStats()

    cutoff_ms = (mw.col.sched.day_cutoff - 86400) * 1000

    rows = []
    for i in range(reviews_today):
        rows.append((cutoff_ms + i * 60_000, 1, 1, 4, 5_000))
    for i in range(reviews_yesterday):
        rows.append((cutoff_ms - 86_400_000 + i * 60_000, 2, 1, 3, 6_000))
    mw.col.db.conn.executemany(
        "INSERT INTO revlog (id, cid, type, ease, time) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    mw.col.db.conn.commit()

    decks = FakeDecks(
        {
            1: {"name": "Default", "id": 1},
            2: {"name": "Japanese::Core 2000", "id": 2},
            3: {"name": "Law::Constitutional", "id": 3},
        }
    )
    mw.col.decks = decks
    mw.col.sched.deck_due_tree = decks.due_tree_from_decks
    return mw


def make_deck_browser(mw):
    shim = FakeDeckBrowser(mw)
    # Bind Onigiri's patched deck-node renderer (patcher.py monkey-patches
    # this onto the real DeckBrowser class; bind it onto our shim).
    from conftest import load_module

    patcher = load_module("patcher")
    shim._render_deck_node = patcher._onigiri_render_deck_node.__get__(shim)
    return shim
