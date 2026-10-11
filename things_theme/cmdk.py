"""Anki Design — Command-K palette search backend.

Drives the floating palette injected by web/cmdk.js. The JS sends two pycmds:

  ba:cmdk-search:<seq>:<urlEncodedQuery>
      → build a result payload (decks, cards, tags, actions) and push it
        back via web.eval("window.__baCmdkResults(<json>);").

  ba:cmdk-do:<action-spec>
      → execute the chosen item. Action specs are simple URL-encoded
        strings of the form "<kind>:<arg>" — e.g. "action:add",
        "deck:1745201234", "card:1745201234", "search:tag%3Aleech".

Everything here runs on Qt's main thread (the webview message hook does).
Card searches are bounded to a small N — the goal is "show me what I want
in <100ms", not "exhaustive results". The Browser embed is the natural
follow-up surface when the user wants the long list."""

from __future__ import annotations

import html
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote

from aqt import mw


# Max items per section in the result payload. Cards and tags are
# expensive; decks/actions are cheap so we let them list a bit more.
MAX_ACTIONS = 8
MAX_DECKS = 8
MAX_CARDS = 8
MAX_TAGS = 6


# --------------------------------------------------------------------------- #
# ACTION CATALOG — the static commands surfaced in the palette.
# Each: (key, title, sub, icon, do, contexts?, keywords?)
#   key:       stable id used in `do` ("action:<key>")
#   title:     primary label
#   sub:       small line below (optional)
#   icon:      cmdk.js icon name
#   contexts:  optional set; if present, action is only listed when the
#              current mw.state is in the set (or "any" sentinel).
#   keywords:  extra strings to match against (aliases, synonyms).
# --------------------------------------------------------------------------- #
_ACTIONS: List[Dict[str, Any]] = [
    {
        "key": "decks",
        "title": "Go to Decks",
        "sub": "Return to the deck homepage",
        "icon": "home",
        "keywords": ["home", "deck list", "back"],
    },
    {
        "key": "add",
        "title": "Add Card",
        "sub": "Create a new note",
        "icon": "add",
        "keywords": ["new card", "new note", "create"],
    },
    {
        "key": "browse",
        "title": "Open Browser",
        "sub": "Browse and search all cards",
        "icon": "browse",
        "keywords": ["find", "cards", "search"],
    },
    {
        "key": "stats",
        "title": "Open Stats",
        "sub": "Review history and forecasts",
        "icon": "stats",
        "keywords": ["statistics", "analytics", "graphs"],
    },
    {
        "key": "sync",
        "title": "Sync now",
        "sub": "Push and pull from AnkiWeb",
        "icon": "sync",
        "keywords": ["upload", "download", "ankiweb"],
    },
    {
        "key": "settings",
        "title": "Anki Design Settings",
        "sub": "Theme, accent, density, fonts",
        "icon": "settings",
        "keywords": ["preferences", "options", "config", "theme"],
    },
    {
        "key": "prefs-native",
        "title": "Anki Preferences",
        "sub": "Anki's native preferences dialog",
        "icon": "settings",
        "keywords": ["preferences", "options"],
    },
    {
        "key": "import",
        "title": "Import File",
        "sub": "Import .apkg / .colpkg / .txt",
        "icon": "import",
        "keywords": ["upload", "open", "apkg"],
    },
    {
        "key": "undo",
        "title": "Undo last action",
        "icon": "undo",
        "keywords": ["revert"],
    },
    {
        "key": "create",
        "title": "New deck…",
        "sub": "Create a fresh deck",
        "icon": "add",
        "keywords": ["new deck", "make deck"],
    },
    # Reviewer-only commands.
    {
        "key": "show",
        "title": "Show Answer",
        "sub": "Flip the current card",
        "icon": "eye",
        "contexts": {"review"},
        "keywords": ["flip", "reveal", "space"],
    },
    {
        "key": "again",
        "title": "Answer: Again",
        "icon": "play",
        "contexts": {"review"},
        "keywords": ["1", "rate"],
    },
    {
        "key": "hard",
        "title": "Answer: Hard",
        "icon": "play",
        "contexts": {"review"},
        "keywords": ["2", "rate"],
    },
    {
        "key": "good",
        "title": "Answer: Good",
        "icon": "play",
        "contexts": {"review"},
        "keywords": ["3", "rate"],
    },
    {
        "key": "easy",
        "title": "Answer: Easy",
        "icon": "play",
        "contexts": {"review"},
        "keywords": ["4", "rate"],
    },
    {
        "key": "flag-cycle",
        "title": "Cycle flag color",
        "icon": "flag",
        "contexts": {"review"},
        "keywords": ["mark", "color"],
    },
    # Theme switching — drives the addon's data-rf-theme override.
    {
        "key": "theme:dark",
        "title": "Theme: Dark",
        "icon": "theme",
        "keywords": ["night", "appearance"],
    },
    {
        "key": "theme:light",
        "title": "Theme: Light",
        "icon": "theme",
        "keywords": ["day", "appearance"],
    },
    {
        "key": "theme:system",
        "title": "Theme: Match system",
        "icon": "theme",
        "keywords": ["auto", "appearance"],
    },
]


# --------------------------------------------------------------------------- #
# FUZZY SCORING
# --------------------------------------------------------------------------- #
def _score(text: str, q: str) -> int:
    """Lightweight scoring: substring + word-start bonuses. Returns a
    larger number for better matches; 0 = no match.

    Bonuses:
      • exact equal:         1000
      • prefix:              700
      • word-start hit:      500 (per token, decaying)
      • substring hit:       200 (per token, decaying)
      • short text bonus:    +10 per missing char (prefer concise hits)
    """
    if not q:
        return 1  # everything matches an empty query (caller decides count)
    t = text.lower()
    qs = q.lower().strip()
    if not qs:
        return 1
    if t == qs:
        return 1000
    if t.startswith(qs):
        return 700 + max(0, 40 - len(t))

    tokens = [tok for tok in re.split(r"\s+", qs) if tok]
    if not tokens:
        return 0
    score = 0
    matched = 0
    for i, tok in enumerate(tokens):
        decay = max(50, 200 - 30 * i)
        pos = t.find(tok)
        if pos == -1:
            return 0  # every token must appear somewhere
        matched += 1
        # Word-start bonus if the token starts at the beginning of a word.
        is_word_start = (
            pos == 0
            or not t[pos - 1].isalnum()
        )
        score += decay
        if is_word_start:
            score += 300 - 20 * i
        # Earlier positions score slightly higher.
        score += max(0, 40 - pos)
    if matched == 0:
        return 0
    # Bonus for tight matches against short labels.
    score += max(0, 30 - len(t) // 4)
    return score


# --------------------------------------------------------------------------- #
# RESULT BUILDERS
# --------------------------------------------------------------------------- #
def _action_items(q: str, state: str) -> List[Dict[str, Any]]:
    out: List[Tuple[int, Dict[str, Any]]] = []
    for a in _ACTIONS:
        contexts = a.get("contexts")
        if contexts and state not in contexts:
            continue
        hay = a["title"]
        if a.get("sub"):
            hay += " " + a["sub"]
        for kw in a.get("keywords", []):
            hay += " " + kw
        s = _score(hay, q)
        if not q:
            # No query: keep them in declared order, score them so we don't
            # bury the most common ones below decks/cards.
            s = 200 - _ACTIONS.index(a)
        if s <= 0:
            continue
        out.append((s, {
            "do": "action:" + a["key"],
            "title": a["title"],
            "sub": a.get("sub", ""),
            "icon": a.get("icon", "search"),
            "chip": "Action",
        }))
    out.sort(key=lambda x: -x[0])
    return [it for _, it in out[:MAX_ACTIONS]]


def _deck_items(q: str) -> List[Dict[str, Any]]:
    try:
        items = mw.col.decks.all_names_and_ids()
    except Exception:
        return []
    scored: List[Tuple[int, Dict[str, Any]]] = []
    # Precompute due tree so we can show due/new counts per top-level deck.
    counts_by_id: Dict[int, Tuple[int, int, int]] = {}
    try:
        tree = mw.col.sched.deck_due_tree()
        stack = [tree]
        while stack:
            node = stack.pop()
            for child in getattr(node, "children", []) or []:
                stack.append(child)
                did = int(getattr(child, "deck_id", 0) or 0)
                if did:
                    counts_by_id[did] = (
                        int(getattr(child, "review_count", 0) or 0),
                        int(getattr(child, "new_count", 0) or 0),
                        int(getattr(child, "learn_count", 0) or 0),
                    )
    except Exception:
        pass

    for d in items:
        name = getattr(d, "name", "") or ""
        if not name:
            continue
        # Drop filtered/internal decks from the palette (Anki may surface
        # things like "Custom Study Session" temporarily).
        if name == "Default" and len(items) > 1:
            # Still allow but at low priority — Default is rarely meaningful
            # when the user has real decks.
            base_score = 1
        else:
            base_score = 0
        s = _score(name, q)
        if not q:
            s = 100  # listed but quietly
        if s <= 0:
            continue
        did = int(getattr(d, "id", 0) or 0)
        if not did:
            continue
        # Use the leaf for the title, parents as the sub so "Spanish" with a
        # query of "vocab" can show "Vocab" with sub "Spanish ▸ Vocab".
        parts = name.split("::")
        leaf = parts[-1]
        parent_path = " ▸ ".join(parts[:-1]) if len(parts) > 1 else ""
        rev, new, lrn = counts_by_id.get(did, (0, 0, 0))
        total = rev + new + lrn
        meta = (str(total) + " due") if total else ""
        scored.append((s + base_score, {
            "do": "deck:" + str(did),
            "title": leaf,
            "sub": parent_path,
            "icon": "deck",
            "chip": "Deck",
            "meta": meta,
        }))
    scored.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
    return [it for _, it in scored[:MAX_DECKS]]


def _tag_items(q: str) -> List[Dict[str, Any]]:
    if not q:
        return []
    try:
        all_tags = mw.col.tags.all() or []
    except Exception:
        return []
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for t in all_tags:
        s = _score(t, q)
        if s <= 0:
            continue
        scored.append((s, {
            "do": "tag:" + t,
            "title": t,
            "sub": "",
            "icon": "tag",
            "chip": "Tag",
        }))
    scored.sort(key=lambda x: -x[0])
    return [it for _, it in scored[:MAX_TAGS]]


def _strip_field(s: str) -> str:
    """Lightweight HTML stripper for note field previews."""
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _card_items(q: str) -> List[Dict[str, Any]]:
    if not q or len(q.strip()) < 2:
        return []
    # If the query already looks like an Anki search expression (contains
    # `:` or quotes or boolean ops), pass it through verbatim. Otherwise
    # wrap each token so we match anywhere in any field.
    qs = q.strip()
    looks_like_query = (
        ":" in qs or '"' in qs
        or re.search(r"\b(AND|OR|NOT|is|deck|tag|prop)\b", qs)
    )
    if looks_like_query:
        search = qs
    else:
        # Use Anki's `*tok*` field-wildcard form so we get fuzzy substring
        # matches without forcing exact word order.
        toks = [tok for tok in re.split(r"\s+", qs) if tok]
        if not toks:
            return []
        # Escape characters with special meaning in Anki search.
        esc_toks = []
        for tok in toks:
            esc = tok.replace('"', '\\"').replace("*", "\\*")
            esc_toks.append('"*' + esc + '*"')
        search = " ".join(esc_toks)

    try:
        cids = list(mw.col.find_cards(search))[: MAX_CARDS]
    except Exception:
        return []
    if not cids:
        return []

    out: List[Dict[str, Any]] = []
    try:
        for cid in cids:
            try:
                card = mw.col.get_card(cid)
                note = card.note()
                fields = list(note.fields)
                # Use the first non-empty field as the title, the second as
                # the sub. Many note types put the question first.
                title = ""
                sub = ""
                for f in fields:
                    txt = _strip_field(f)
                    if not txt:
                        continue
                    if not title:
                        title = txt
                    elif not sub:
                        sub = txt
                        break
                if not title:
                    title = "(empty note)"
                # Trim aggressively — palette rows show one line.
                if len(title) > 90:
                    title = title[:88] + "…"
                if len(sub) > 90:
                    sub = sub[:88] + "…"
                deck_name = ""
                try:
                    deck_name = mw.col.decks.name(card.did)
                except Exception:
                    pass
                meta_bits = []
                if deck_name:
                    meta_bits.append(deck_name.split("::")[-1])
                out.append({
                    "do": "card:" + str(cid),
                    "title": title,
                    "sub": sub,
                    "icon": "card",
                    "chip": "Card",
                    "meta": " · ".join(meta_bits),
                })
            except Exception:
                continue
    except Exception:
        pass
    return out


def _fallback_search_item(q: str) -> Optional[Dict[str, Any]]:
    """When the user has typed a query we couldn't strongly match, offer to
    run it through the embedded Browser instead. Always at the bottom."""
    qs = (q or "").strip()
    if not qs:
        return None
    return {
        "do": "search:" + qs,
        "title": 'Search browser for "' + qs + '"',
        "sub": "Open Browser with this exact query",
        "icon": "search",
        "chip": "Search",
    }


# --------------------------------------------------------------------------- #
# PUBLIC: search + dispatch
# --------------------------------------------------------------------------- #
def search(query: str, seq: int) -> Dict[str, Any]:
    """Build the result payload for the given query.
    Returned shape matches what cmdk.js expects in __baCmdkResults."""
    q = (query or "").strip()
    state = getattr(mw, "state", "") or ""

    sections: List[Dict[str, Any]] = []

    actions = _action_items(q, state)
    if actions:
        sections.append({"title": "Actions", "items": actions})

    decks = _deck_items(q)
    if decks:
        sections.append({"title": "Decks", "items": decks})

    cards = _card_items(q)
    if cards:
        sections.append({"title": "Cards", "items": cards})

    tags = _tag_items(q)
    if tags:
        sections.append({"title": "Tags", "items": tags})

    # Fallback: explicit "Search browser for X" row at the bottom.
    fb = _fallback_search_item(q)
    if fb:
        sections.append({"title": "Other", "items": [fb]})

    return {"seq": seq, "q": q, "sections": sections}


def _push_results(payload: Dict[str, Any]) -> None:
    """Eval the result payload into whichever webview currently holds the
    palette. We try the active reviewer webview first (palette can open
    during review), then mw.web, then the cmdk overlay webview (used when
    an embed obscures mw.web). Each webview gets its own copy — cheap,
    and harmless when only one of them actually has the palette open."""
    try:
        data = json.dumps(payload)
    except Exception:
        return
    js = "window.__baCmdkResults && window.__baCmdkResults(" + data + ");"
    targets = []
    rv = getattr(mw, "reviewer", None)
    if rv is not None:
        w = getattr(rv, "web", None)
        if w is not None:
            targets.append(w)
    w = getattr(mw, "web", None)
    if w is not None and w not in targets:
        targets.append(w)
    try:
        from . import cmdk_overlay
        ow = cmdk_overlay.webview()
        if ow is not None and ow not in targets:
            targets.append(ow)
    except Exception:
        pass
    for t in targets:
        try:
            t.eval(js)
        except Exception:
            pass


def handle_search(raw: str) -> None:
    """Parse "<seq>:<urlEncodedQuery>" and emit a result payload."""
    try:
        sep = raw.find(":")
        if sep < 0:
            seq = 0
            q = raw
        else:
            try:
                seq = int(raw[:sep])
            except Exception:
                seq = 0
            q = raw[sep + 1:]
        try:
            q = unquote(q or "")
        except Exception:
            pass
        payload = search(q, seq)
    except Exception:
        payload = {"seq": 0, "q": "", "sections": []}
    _push_results(payload)


# --------------------------------------------------------------------------- #
# DISPATCH — execute the chosen item.
# --------------------------------------------------------------------------- #
def _close_all_embeds() -> None:
    """Close any inline embed (Add/Browse/Stats/Settings) so the palette's
    action lands on a clean deck-browser surface."""
    for mod_name in ("addcard_embed", "browse_embed", "stats_embed", "settings_embed"):
        try:
            from importlib import import_module
            import_module("." + mod_name, __package__).close_inline()
        except Exception:
            pass


def _open_browser_with_query(query: str) -> None:
    """Open the Browser (inline embed or Anki's window, per Settings) and
    run a search."""
    try:
        mw.onBrowse()
    except Exception:
        return
    # Push the query after the Browser has settled. find_widget lazily —
    # the embed's `_state["browser"]` is set once construction completes.
    def _apply():
        try:
            from . import browse_embed as _be
            br = _be._state.get("browser") if hasattr(_be, "_state") else None
            if br is None:
                # As a last resort, search Anki's native browser dialog.
                try:
                    from aqt import dialogs
                    nb = dialogs._dialogs.get("Browser", [None, None])[1]
                    br = nb
                except Exception:
                    br = None
            if br is None:
                return
            try:
                br.form.searchEdit.lineEdit().setText(query)
                br.onSearchActivated()
            except Exception:
                pass
        except Exception:
            pass
    try:
        from aqt.qt import QTimer
        QTimer.singleShot(60, _apply)
    except Exception:
        _apply()


def _apply_theme(theme: str) -> None:
    """Persist the user's theme choice and re-render so the change takes
    effect immediately."""
    if theme not in ("light", "dark", "system"):
        return
    try:
        # __package__ is the addon folder name (e.g. "anki-design" or the
        # numeric AnkiWeb ID). getConfig/writeConfig key off that.
        cfg = mw.addonManager.getConfig(__package__) or {}
        cfg["theme"] = theme
        mw.addonManager.writeConfig(__package__, cfg)
    except Exception:
        pass
    # Re-render the current state so the new <head> goes out.
    try:
        st = getattr(mw, "state", "")
        if st in ("deckBrowser", "overview", "review"):
            mw.moveToState(st)
    except Exception:
        pass


def _reviewer_eval(js: str) -> None:
    rv = getattr(mw, "reviewer", None)
    if rv is None:
        return
    w = getattr(rv, "web", None)
    if w is not None:
        try:
            w.eval(js)
        except Exception:
            pass


def _answer_card(ease: int) -> None:
    rv = getattr(mw, "reviewer", None)
    if rv is None:
        return
    if getattr(rv, "card", None) is None:
        return
    state = getattr(rv, "state", "")
    if state == "question":
        # Auto-flip first.
        try:
            rv._showAnswer()
        except Exception:
            pass
    try:
        rv._answerCard(ease)
    except Exception:
        pass


def _start_studying(did: int) -> None:
    """Mirror __init__._start_studying without the dev logging."""
    try:
        mw.col.decks.select(did)
        try:
            mw.col.startTimebox()
        except Exception:
            pass
        cur_state = getattr(mw, "state", "")
        rv = getattr(mw, "reviewer", None)
        if cur_state == "review" and rv is not None:
            try:
                rv._showQuestion()
                return
            except Exception:
                pass
        mw.moveToState("review")
    except Exception:
        try:
            mw.moveToState("overview")
        except Exception:
            pass


def handle_do(raw: str) -> None:
    """Execute the chosen palette item. Action spec format:
        action:<key>      | deck:<did> | card:<cid> |
        tag:<name>        | search:<query>
    """
    try:
        spec = unquote(raw or "")
    except Exception:
        spec = raw or ""
    if not spec:
        return
    kind, _, arg = spec.partition(":")
    kind = kind.strip()
    arg = arg.strip()

    if kind == "action":
        _do_action(arg)
        return
    if kind == "deck" and arg.isdigit():
        _close_all_embeds()
        _start_studying(int(arg))
        return
    if kind == "card" and arg.isdigit():
        _open_browser_with_query("cid:" + arg)
        return
    if kind == "tag":
        # Anki's search wants the bare tag name; quote if spaces.
        if " " in arg:
            _open_browser_with_query('tag:"' + arg + '"')
        else:
            _open_browser_with_query("tag:" + arg)
        return
    if kind == "search":
        _open_browser_with_query(arg)
        return


def _do_action(key: str) -> None:
    """Run a built-in action."""
    if not key:
        return
    # Theme switches.
    if key.startswith("theme:"):
        _apply_theme(key.split(":", 1)[1])
        return

    # Reviewer-only commands.
    if key == "show":
        rv = getattr(mw, "reviewer", None)
        if rv and getattr(rv, "state", "") == "question":
            try:
                rv._showAnswer()
            except Exception:
                _reviewer_eval("pycmd('ans')")
        return
    if key == "again":
        _answer_card(1); return
    if key == "hard":
        _answer_card(2); return
    if key == "good":
        _answer_card(3); return
    if key == "easy":
        _answer_card(4); return
    if key == "flag-cycle":
        try:
            rv = getattr(mw, "reviewer", None)
            if rv is None or getattr(rv, "card", None) is None:
                return
            card = rv.card
            cur = int(card.user_flag())
            card.set_user_flag((cur + 1) % 5)
            try:
                mw.col.update_card(card)
            except Exception:
                pass
        except Exception:
            pass
        return

    # Top-level navigation maps to the existing ba:* handlers.
    if key in ("decks", "add", "browse", "stats", "sync", "settings",
              "import", "undo", "create"):
        try:
            w = getattr(mw, "web", None)
            if w is not None:
                # Re-use the existing JS message routing so all the
                # embed-teardown / state-fixup logic stays in one place.
                w.eval("pycmd('ba:" + key + "');")
            else:
                _dispatch_top_level(key)
        except Exception:
            _dispatch_top_level(key)
        return
    if key == "prefs-native":
        try:
            from aqt import dialogs
            dialogs.open("Preferences", mw)
        except Exception:
            try:
                # mw.onPrefs was patched by the addon to open our settings;
                # call the underlying dialog via the Anki API instead.
                from aqt.preferences import Preferences
                Preferences(mw)
            except Exception:
                pass
        return


def _dispatch_top_level(key: str) -> None:
    """Fallback for top-level actions when mw.web isn't available
    (e.g. between renders)."""
    try:
        if key == "decks":
            mw.moveToState("deckBrowser")
        elif key == "add":
            # mw.onAddCard/onBrowse/onStats/onPrefs are patched by
            # __init__.py to honour the inline-window toggles.
            mw.onAddCard()
        elif key == "browse":
            mw.onBrowse()
        elif key == "stats":
            mw.onStats()
        elif key == "sync":
            mw.on_sync_button_clicked()
        elif key == "settings":
            mw.onPrefs()
        elif key == "import":
            mw.onImport()
        elif key == "undo":
            mw.undo()
        elif key == "create":
            try:
                from aqt.operations.deck import add_deck_dialog
                add_deck_dialog(parent=mw)
            except Exception:
                pass
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Open the palette from outside the webview (Qt shortcut → JS toggle).
# --------------------------------------------------------------------------- #
def _any_embed_open() -> bool:
    """True if any inline embed (Add/Browse/Stats/Settings) is currently
    overlaid on mw.web. The embeds expose a module-level `_state` dict; an
    "overlay" key set to a non-None QFrame means the embed is showing."""
    for mod_name in (
        "addcard_embed", "browse_embed", "stats_embed", "settings_embed",
    ):
        try:
            from importlib import import_module
            mod = import_module("." + mod_name, __package__)
            st = getattr(mod, "_state", None)
            if isinstance(st, dict) and st.get("overlay") is not None:
                return True
        except Exception:
            continue
    return False


def open_from_outside(initial: str = "") -> None:
    """Open the palette over the currently-visible surface.

    Routing:
      - In review state, the reviewer's webview gets the palette (mw.web
        is hidden during review, and no embeds can be open).
      - If an embed (Add/Browse/Stats/Settings) is up, render in the
        dedicated `cmdk_overlay` so the palette floats above the embed.
        (Embeds are Qt frames on top of mw.web; a palette in mw.web would
        be invisible behind them.)
      - Otherwise, the palette goes into mw.web as usual.
    """
    state = getattr(mw, "state", "") or ""

    if state == "review":
        rv = getattr(mw, "reviewer", None)
        target = getattr(rv, "web", None) if rv is not None else None
        if target is None:
            return
        try:
            js = (
                "if (window.__baCmdkOpen) window.__baCmdkOpen("
                + json.dumps(initial or "") + ");"
            )
            target.eval(js)
        except Exception:
            pass
        return

    if _any_embed_open():
        # The overlay is a transparent webview parented to centralwidget;
        # it raises itself above any embed so the palette is visible while
        # the embed (Browse/Add/etc.) stays in place underneath.
        try:
            from . import cmdk_overlay
            cmdk_overlay.open(initial)
        except Exception:
            pass
        return

    target = getattr(mw, "web", None)
    if target is None:
        return
    try:
        js = (
            "if (window.__baCmdkOpen) window.__baCmdkOpen("
            + json.dumps(initial or "") + ");"
        )
        target.eval(js)
    except Exception:
        pass
