# Original / Middle → Current upgrade audit

Audited on 2026-10-11 against the attached `Onigiri(Original)` and
`Onigiri(Middle)` directories. Changes are implemented in Current.

## Verified data contracts

| Saved data | Upgrade treatment |
| --- | --- |
| `settings_<profile>.json` | Same root `user_files` location; saved values and unknown keys retained; new defaults fill missing settings. Explicit empty settings do not import stale shared settings. |
| Shared Anki add-on config | Used only when no valid profile save exists. Included in the immutable backup before migration. |
| `gamification_<profile>.json` | XP, level, coins, owned items, equipped restaurant, achievements, daily specials, and nested metadata survive load/save/reload. A stale checksum no longer resets coins. |
| Legacy `gamification.json` | Copied into the active profile when needed; the source file remains intact. Existing profile balances, including zero, take precedence. |
| Onigimon / Hexagon Land | Companions, inventory, currencies, island tiles/materials, and unfamiliar fields survive. In-memory state follows the correct profile. |
| Mochi history | Legacy in-settings history remains available; the new history cache follows the correct profile. |
| Hashi Notes / Prep Station / Pomodoro | Existing collection keys are unchanged: notes, plans, sessions, and preferences remain in the collection. Hashi normalization now retains unfamiliar note fields. |
| Colors and layout | Saved palettes remain authoritative even when equal to an old default. Sparse widget grids and actions stored in More are preserved. |
| Uploaded files | Avatars, backgrounds, icons, fonts, audio, database files, and nested theme assets remain under `user_files`; the external recovery mirror now includes them. |
| Bundled assets / purchases | Restored 117 missing legacy asset paths/lookup entries. All bundled asset paths and catalog IDs from both snapshots resolve in Current. Original's five retired evolution IDs remain available to existing owners. |
| Middle sync | Existing opt-in full sync includes layouts. Unresolved archives cannot be overwritten on first startup. Imported game files invalidate/reload existing caches before a later save. |

The existing retired slideshow migrations still render a single image. The
Overview migration now selects the first saved slide when no image was selected;
the complete image list, interval, and uploaded files remain saved. This audit
protects data; it does not reinstate retired interfaces or animations.

## Backup and recovery

Before migrations or file repairs, Onigiri creates:

- `<Anki base>/onigiri_backups/before_progress_upgrade_v2.zip`, containing the
  original `user_files` tree, shared add-on configuration, and any surviving
  legacy root sync/layout files. It is never refreshed by subsequent saves.
- `before_progress_upgrade_v2_<profile hash>.json` in the same directory, holding
  each profile's original collection configuration and profile name.

Older v1 archives remain untouched. Normal writes are atomic, with backups,
dated snapshots, and an external mirror. Recovery selects the newest valid copy;
valid empty containers are respected as intentional clears. Failed queued writes
remain pending for retry, and an older queued write cannot overwrite a newer
immediate save. Snapshot paths include the parent directory.

Profile-rename recovery only adopts a coherent, single orphaned settings owner
when one active Anki profile makes the association unambiguous. Default startup
files and unrelated orphaned game files are not guessed into another profile.

## Release packaging

Build with:

```sh
python3 tools/build_addon.py /absolute/path/Onigiri.ankiaddon
```

The builder keeps package identity `1011095603`, ships empty default add-on
configuration, and includes only a generic README under `user_files`. It excludes
personal saves, `meta.json`, the developer's root layout, caches, tests, tools,
and both attached historical versions.

Install updates over the same add-on through Anki's add-on installer. Anki's
[documented user-files contract](https://addon-docs.ankiweb.net/addon-config.html#user-files)
preserves `user_files` and removes other old add-on files. Uninstalling the old
add-on or replacing its entire data folder before installing is a different
operation and is not the tested upgrade path. An old version cannot create the
new external backup before its files have reached Current.

## Verification

- The initial audit passed **43 upgrade tests**, including real Original/Middle settings and game
  writers, both complete simulated installations, repeated saves/reloads,
  multiple profiles, stale checksums, unknown fields, imported artwork/fonts,
  backup recovery, write failures, and legacy sync archives.
- Both install simulations preserve every pre-existing user file byte-for-byte
  through code replacement. Subsequent Current saves preserve the tested values
  and keep an exact copy of the original files in the immutable archive.
- The initial audit ran **273 tests overall: 263 pass, 10 fail.** The same ten UI-contract failures
  were present before these changes. Two additional baseline scan errors were
  caused by treating the attached historical code fragments as Current; the
  production scans now exclude those reference directories.
- All 132 Current Python files parse successfully after the backup warning fix.
- The nine existing files in this installation's `user_files` directory were
  checked by SHA-256 and remain unchanged. Test persistence writes use temporary
  directories only.

The remaining baseline failures cover two Bento/Byte contracts, three font/settings
contracts, the developer Nook catalog artwork contract, two settings-startup
contracts, the Shima header contract, and the Kome customizer contract.

This verification does **not** claim a live Anki updater run, a real AnkiWeb
round trip, or hardware/platform validation. Anki was not opened or restarted,
and no real collection or account was modified during the audit.

## Collection backup warning fix and dialog branding

The reported `bad argument type for built-in operation` came from converting
Anki's `ConfigManager` with `dict(collection.conf)`. Its legacy dictionary-like
interface is not iterable: Python requests integer index 0, which Anki's backend
rejects because configuration keys must be strings. This failed while reading
configuration, before writing the collection backup; it did not delete settings.
The initial test fixtures used plain dictionaries and missed this incompatibility.

Backup and sync now share `collection_config_snapshot()`, using the installed
Anki public `Collection.all_config()` method. A real dictionary fallback supports
older hosts. The snapshot is detached from live settings; export failures never
become empty sync payloads or replace an existing sync archive.

Storage notices and generic font, icon, Kome, shortcut, and recent-menu warnings
now use the central native Onigiri dialog. It shows the supplied Onigiri logo,
visible app name, and theme palette. Native fallback/confirmation boxes and the
sync conflict dialog are branded too. Warning dialogs remain persistent even
when game notifications are muted. Long messages scroll; keyboard/OK dismissal
remains available. The collection backup notice and warning headings cover all
eight supported languages.

Post-fix verification:

- **47 upgrade tests: 39 pass, 8 skipped.** The Original/Middle attachment
  directories are no longer present in the workspace, so tests requiring those
  exact historical fixtures are explicitly skipped. Their initial audit result
  above remains the recorded evidence; it was not rerun against substitutes.
- **277 total tests: 259 pass, 10 pre-existing failures, 8 fixture skips**, with
  no errors or additional failures.
- `tools/verify_anki_upgrade.py`, run with the installed Anki Python environment,
  reproduces the exact exception on a temporary real Anki collection. The fixed
  backup then matches every collection configuration key and value, with live
  settings unchanged; a real sync archive retains the Onigiri notes/title keys.
- The same tool renders Qt dialogs offscreen in light/dark mode and checks logo,
  visible source name, OK dismissal, scrolling, silent-mode independence, and
  the branded fallback. No live Anki window or user collection is used.
- Nine original user files still match their original SHA-256 checksums.

Restart Anki to load the corrected installed code. The release package has been
rebuilt with this fix; it still excludes personal data and historical fixtures.
