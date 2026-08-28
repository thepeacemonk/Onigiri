# Value store for the WebUI settings dialog.
#
# Onigiri keeps settings in three different places and the old PyQt dialog read
# them straight out of live Qt widgets at save time. This module makes that
# addressing explicit instead: every field in `schema.py` carries a `bind`
# descriptor, and this file is the only thing that knows how to read/write one.
#
#   {"kind": "config", "key": "maxHide"}                    -> addon config JSON
#   {"kind": "config", "path": ["colors", "light", "--fg"]}  -> nested config JSON
#   {"kind": "col",    "key": "modern_menu_statsTitle"}      -> mw.col.conf
#   {"kind": "col_path", "key": "onigiri_pomodoro_settings", "path": ["size"]}
#                                                               -> nested mw.col.conf
#   {"kind": "profile", "key": "onigiri_language"}           -> mw.pm.profile
#   {"kind": "game",   "key": "nook_name"}                   -> a gamification
#                                                               manager's own
#                                                               state, via
#                                                               games_state
#
# A `config`/`col` bind may also carry `"asset_dir": "user_files/..."`: the
# value on disk is then a path relative to the add-on root while the page only
# ever sees (and the gallery only ever writes) the bare filename. Onigimon's
# scene background and Mochi's messenger image are stored that way and are read
# back by code outside this dialog, so the stored shape cannot change.
#
# Edits are staged in memory and only land in `config.write_config()` /
# `mw.col.conf` when `commit()` runs, so Cancel is a true no-op and a failing
# page cannot half-write another page's keys.

import copy
import os

from aqt import mw

from .. import config


class MissingBinding(Exception):
    pass


def _col_get(col, key, default=None):
    """Read via the modern col.get_config, falling back to the deprecated
    col.conf dict. Mirrors onigiri_renderer._col_conf_get — the real UI reads
    collection config this way, so writes must go through the matching
    _col_set below or the WebUI and the real render disagree on the value."""
    try:
        value = col.get_config(key)
        return default if value is None else value
    except Exception:
        try:
            return col.conf.get(key, default)
        except Exception:
            return default


def _col_set(col, key, value):
    """Write via the modern col.set_config, falling back to col.conf. Mirrors
    onigiri_renderer._col_conf_set."""
    try:
        col.set_config(key, value)
        return
    except Exception:
        pass
    try:
        col.conf[key] = value
        col.setMod()
    except Exception:
        pass


class Store:
    """Reads current values, stages edits, writes them all at once."""

    def __init__(self):
        # config.get_config() returns the fully-built config (defaults merged in).
        # We hold one instance for the dialog's lifetime, exactly like the legacy
        # dialog's self.current_config, and write it back on commit.
        self.config = config.get_config()
        self._staged = {}          # field id -> value
        self._bindings = {}        # field id -> bind descriptor
        self._defaults = {}        # field id -> default value

    # ─── registration ──────────────────────────────────────────────────────────

    def register(self, field_id, bind, default=None):
        # The default is recorded even for unbound fields (notes, and anything
        # whose value is display-only), so read() still answers with something
        # sensible instead of None.
        self._defaults[field_id] = default
        if bind:
            self._bindings[field_id] = bind

    # ─── reading ───────────────────────────────────────────────────────────────

    def read(self, field_id):
        """Current value: staged edit if there is one, else what is persisted."""
        if field_id in self._staged:
            return self._staged[field_id]
        bind = self._bindings.get(field_id)
        if bind is None:
            return self._defaults.get(field_id)
        return self._read_bound(bind, self._defaults.get(field_id))

    def _read_bound(self, bind, default):
        value = self._read_raw(bind, default)
        asset_dir = bind.get("asset_dir")
        if asset_dir and isinstance(value, str) and value:
            return os.path.basename(value)
        return value

    def _read_raw(self, bind, default):
        kind = bind.get("kind", "config")
        try:
            if kind == "config":
                return self._read_config(bind, default)
            if kind == "game":
                from . import games_state

                return games_state.read(bind["key"], default)
            if kind == "col":
                if mw is None or mw.col is None:
                    return default
                value = _col_get(mw.col, bind["key"], default)
                return default if value is None else value
            if kind == "col_path":
                if mw is None or mw.col is None:
                    return default
                node = _col_get(mw.col, bind["key"], {})
                for part in bind.get("path", []):
                    if not isinstance(node, dict) or part not in node:
                        return default
                    node = node[part]
                return default if node is None else node
            if kind == "profile":
                if mw is None or mw.pm is None:
                    return default
                return mw.pm.profile.get(bind["key"], default)
        except Exception:
            return default
        return default

    def _read_config(self, bind, default):
        if "key" in bind:
            value = self.config.get(bind["key"], default)
            return default if value is None else value
        node = self.config
        for part in bind.get("path", []):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return default if node is None else node

    # ─── staging ───────────────────────────────────────────────────────────────

    def stage(self, field_id, value):
        """Record an edit without persisting it."""
        self._staged[field_id] = value

    def stage_many(self, values):
        for field_id, value in (values or {}).items():
            self.stage(field_id, value)

    def discard(self):
        self._staged.clear()

    @property
    def dirty(self):
        return bool(self._staged)

    def staged_ids(self):
        return set(self._staged)

    # ─── committing ────────────────────────────────────────────────────────────

    def apply_staged(self):
        """Fold every staged edit into self.config / mw.col.conf in memory.

        Returns the list of (field_id, error) pairs that failed, so one bad
        binding can never abort the rest of the save (the legacy dialog learned
        this the hard way — see the `_safe` wrapper in _dialog_core.save_settings).
        """
        failures = []
        for field_id, value in self._staged.items():
            bind = self._bindings.get(field_id)
            if bind is None:
                failures.append((field_id, "no binding registered"))
                continue
            try:
                self._write_bound(bind, value)
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                failures.append((field_id, repr(exc)))
        return failures

    def _write_bound(self, bind, value):
        kind = bind.get("kind", "config")
        asset_dir = bind.get("asset_dir")
        if asset_dir and isinstance(value, str):
            name = os.path.basename(value)
            value = f"{asset_dir.rstrip('/')}/{name}" if name else ""
        if kind == "game":
            from . import games_state

            games_state.write(bind["key"], value)
        elif kind == "config":
            self._write_config(bind, value)
        elif kind == "col":
            _col_set(mw.col, bind["key"], value)
        elif kind == "col_path":
            node = copy.deepcopy(_col_get(mw.col, bind["key"], {}))
            if not isinstance(node, dict):
                node = {}
            path = list(bind.get("path", []))
            if not path:
                raise MissingBinding("col_path bind needs a path")
            target = node
            for part in path[:-1]:
                child = target.get(part)
                if not isinstance(child, dict):
                    child = {}
                    target[part] = child
                target = child
            target[path[-1]] = value
            _col_set(mw.col, bind["key"], node)
        elif kind == "profile":
            mw.pm.profile[bind["key"]] = value
        else:
            raise MissingBinding(f"unknown bind kind {kind!r}")

    def _write_config(self, bind, value):
        if "key" in bind:
            self.config[bind["key"]] = value
            return
        path = list(bind.get("path", []))
        if not path:
            raise MissingBinding("config bind needs 'key' or 'path'")
        node = self.config
        for part in path[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[path[-1]] = value

    def apply_now(self, values):
        """Stage a patch, fold it in and persist it in one go.

        This is the auto-save path: the page sends small patches as the user
        edits, so there is no "pending until Save" window to lose. Returns
        (touched_field_ids, failures)."""
        self.stage_many(values)
        touched = set(values or {})
        failures = self.apply_staged()
        # Everything in this patch is now persisted, so it is no longer pending.
        for field_id in touched:
            self._staged.pop(field_id, None)
        self.write_config()
        return touched, failures

    def write_config(self):
        config.write_config(self.config)

    # ─── helpers used by side effects ──────────────────────────────────────────

    def effective(self, field_id):
        """Value a post-save hook should act on (staged or persisted)."""
        return self.read(field_id)

    def snapshot(self):
        return copy.deepcopy(self.config)
