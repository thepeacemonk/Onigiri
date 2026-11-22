# Open Bento issue fixes — 2026-10-13

Implemented locally in the installed Onigiri add-on. The open issue list contained nine issues without the `pre-bento` label; #346 and #353 describe the same missing AI button. Issues #338, #336, #333, #328, #281 and #280 were excluded by that label.

| Issue | Change | Validation boundary |
| --- | --- | --- |
| [#354](https://github.com/thepeacemonk/Onigiri/issues/354) — lost levels and negative coins | Store the XP curve multiplier and convert XP when the curve changes, preserving earned levels. Positive XP can no longer trigger an undo deduction. Recover the exact erroneous first-review deduction only when a backup from the same profile proves the previous XP, level, purchases and balance. | Migration, level-up/undo, recovery, ambiguous-history rejection and persistence tests pass. The reporter's profile was unavailable. Recovery cannot infer a trustworthy balance after additional reviews or purchases. |
| [#353](https://github.com/thepeacemonk/Onigiri/issues/353) — missing AI button in Focus | Mirror captured native add-on toolbar actions into the reviewer header, including icons, accessible labels and their original command handlers. Refresh after late toolbar rebuilds. | Headless reviewer button rendering, icon decoding and command dispatch pass. The reporter's installed Anki Terminator version needs live verification. |
| [#352](https://github.com/thepeacemonk/Onigiri/issues/352) — missing Delay Overdue action | Add **Add-on actions…** to both deck context menus. This opens Anki's native deck menu for the selected deck and runs its add-on menu hooks, exposing actions such as Delay Overdue when their add-on is installed. | Selected-deck dispatch and installed Anki menu source verified. Requires live testing with the reporter's FSRS Helper version. |
| [#351](https://github.com/thepeacemonk/Onigiri/issues/351) — missing sidebar background images | Restore independent **Custom** backgrounds with **Image** and **Image + Color** choices, light/dark assets, opacity and blur. Keep image selection while matching widget effects. Preserve the meanings of existing Match Widgets and Match Main Menu stored selections. | Runtime image generation, shared-image fallback and eight light/dark preview combinations pass. |
| [#350](https://github.com/thepeacemonk/Onigiri/issues/350) — reviewer header font differs | Read typography through the supported configuration accessor, retain Poppins fallback faces and register selected font faces in the document head so the shadow header can load them. Keep typography selectors inside the shadow header. | Shipped selected font actually loads in four headless reviewer layouts; header and gauge match while card-template typography remains intact. Native macOS Anki still needs a visual check. |
| [#349](https://github.com/thepeacemonk/Onigiri/issues/349) — deck icon cannot save | Remove the branch-local `config` import that shadowed the module import throughout the command handler and raised `UnboundLocalError` on save/reset. | Icon save/reset and tag names containing colons pass; other deck icons and separate light/dark colors are preserved. |
| [#348](https://github.com/thepeacemonk/Onigiri/issues/348) — unclickable Windows dashboard | Count only visible card editors, discard hidden/deleted tracked editors and remove the dashboard-wide pointer block associated with editor dimming. | Hidden/deleted editor regressions and headless dashboard hit testing pass. This is a candidate fix for the reported Windows symptom; the affected Windows setup was unavailable. |
| [#346](https://github.com/thepeacemonk/Onigiri/issues/346) — missing Anki Terminator button | Same toolbar-to-reviewer bridge as #353. | The available [Anki Terminator fork source](https://api.github.com/repos/ataha24/anki-terminator-oe/contents/update_top_toolbar.py) registers toolbar commands using the mechanism handled by this bridge. The exact installed version was not exercised. |
| [#345](https://github.com/thepeacemonk/Onigiri/issues/345) — Chinese Kome sidebar shows undefined/— | Keep internal `new`, `learn` and `due` identifiers untranslated; translate only their visible labels. | All eight supported languages, five hero selections each and subsequent zero-count updates pass in the full sidebar/localization scripts. |

## Where restored controls appear

- Sidebar images: **Settings → Sidebar → Background Source → Custom → Background Mode → Image / Image + Color**.
- External deck actions: right-click the deck, then choose **Add-on actions…**. The corresponding third-party add-on must be installed and enabled.
- AI toolbar actions: the reviewer header mirrors third-party actions captured from Anki's top toolbar, including in Focus mode.

## Checks completed

- 13 new Python behavioral regression tests pass.
- Headless Chromium passes 40 locale/selection cases, eight sidebar image cases, dashboard click testing and four reviewer font/button layouts at 360/1440 pixels in light/dark mode. Tests use generated Onigiri UI and shipped fonts, without loading an Anki profile.
- Existing background-matching and font-color JavaScript checks pass; changed Python and JavaScript syntax checks pass.
- Full Python suite: 324 tests, 305 passed, eight skipped and 11 failures. The same 11 failures were present before these changes in the 311-test baseline; no new failing test names were introduced.
- Six of the seven original files under `user_files` retain their SHA-256 hashes. At final inspection, the gamification file had initialized `xp_multiplier: 1` and updated its timestamp; XP, level, coins, purchases and every other field were unchanged. Its new `.bak` file matches the original SHA-256 hash exactly. This initialization was preserved. The automated checks use isolated fixtures and did not open Anki or load the live collection.
- The frontend detector reported four existing CSS width-transition warnings, all confirmed in the original source.

## Remaining live validation

Restart Anki to load the modified Python code. Verify the reported Windows dashboard setup, the selected font in native macOS Anki and the relevant third-party add-on versions. For #354, automatic recovery is intentionally limited to an exact proven backup match; ambiguous affected profiles require inspection of their backups before restoring a balance.

No GitHub issue was closed or commented on, and no release was published. The add-on directory is not a Git checkout. Original source copies are in `/tmp/onigiri-issues-2026-10-13-baseline`; baseline and final suite logs are alongside that directory.
