# Declarative description of the Onigiri settings dialog.
#
# This is the whole point of the WebUI migration: pages are data, not 2,000-line
# Qt builder methods. `web/settings.js` renders whatever this file describes and
# `store.py` knows how to persist each field's `bind`, so a new setting is one
# dict entry rather than a widget + a save line + a stylesheet rule.
#
# Field types the renderer understands:
#   toggle      bool switch
#   mode_card   bool switch presented as a big card (icon, title, desc, notes)
#   choice      grid of selectable cards      (options: [{value,label,sub,emoji}])
#   select      dropdown                      (options: [{value,label}])
#   number      numeric input                 (min/max/step/suffix/default_hint)
#   text        single-line text
#   color       colour chip -> native picker  (bind per light/dark handled by
#                                              two separate fields)
#   font        font chip -> native picker
#   note        static explanatory block, no binding
#   game_choice picture cards, one per option    (Games pages' difficulty picker)
#   message_list  reorderable list of one-line strings
#   notif_position  the six reviewer-notification anchors, with a live preview
#
# The Games pages (the former standalone "Gamification Settings" window) live in
# games.py and are appended by build_pages() below.
#
# A page with "legacy_page" set has not been ported yet: it renders an explainer
# plus a button that opens the classic PyQt dialog on the matching page. Removing
# that key (and adding sections) is what "porting a page" means.

from aqt import mw

from ..translations import LANGUAGES, tr
from . import games

# ── constants mirrored from the legacy pages ───────────────────────────────────
# Duplicated on purpose: importing settings/_page_languages.py would drag the
# entire 41k-line PyQt tree in, which is exactly what this package replaces.

LANGUAGE_FLAGS = {
    "English (Default)": "🇺🇸",
    "Português (Brasil)": "🇧🇷",
    "Español (España)": "🇪🇸",
    "简体中文": "🇨🇳",
    "日本語": "🇯🇵",
    "Français": "🇫🇷",
    "한국어": "🇰🇷",
    "Deutsch": "🇩🇪",
}

LANGUAGE_ORDER = [
    "English (Default)",
    "Français",
    "Español (España)",
    "Português (Brasil)",
    "Deutsch",
    "简体中文",
    "日本語",
    "한국어",
]

# A greeting in each language's own script. The Languages page leads with this
# rather than the language's name, so every card looks like the thing it selects
# instead of a column of the same Latin typeface.
LANGUAGE_GREETINGS = {
    "en": "Hello",
    "pt-BR": "Olá",
    "es-ES": "¡Hola!",
    "zh-CN": "你好",
    "ja-JP": "こんにちは",
    "fr-FR": "Bonjour",
    "ko-KR": "안녕하세요",
    "de-DE": "Hallo",
}

# Four strings the user will recognise from the UI, shown as English -> target
# pairs so a language can be judged before it is applied.
LANGUAGE_PREVIEW_KEYS = ("save", "search", "modes", "themes")

FONT_ROLES = (
    # (config_key, label_key, label_fallback, default_size, colour token)
    ("main", "text", "Text", 14, "--fg"),
    ("subtle", "titles", "Titles", 20, "--fg-subtle"),
    ("small_title", "small_titles", "Small titles", 15, "--font-small-title-color"),
)


# ── availability probes ────────────────────────────────────────────────────────

def _mac_titlebar_supported():
    try:
        from .. import mac_titlebar

        return bool(mac_titlebar.is_supported())
    except Exception:
        return False


def _synapsepro_present():
    try:
        from .. import patcher

        return bool(patcher.is_synapsepro_identified())
    except Exception:
        return False


# ── field helpers ──────────────────────────────────────────────────────────────

def _language_parts(lang_name):
    """Splits 'Português (Brasil)' into a clean title and a code-led caption."""
    title, note = lang_name, ""
    if " (" in lang_name and lang_name.endswith(")"):
        title, note = lang_name[:-1].split(" (", 1)
    code = LANGUAGES.get(lang_name, "en").upper()
    subtitle = f"{code} · {note.upper()}" if note else code
    return title, subtitle


def _language_coverage(code):
    """How much of the add-on is actually translated into `code`.

    Only keys that exist in English count, so a stale key left behind in a
    translation cannot push a language over 100%."""
    from ..translations import TRANSLATIONS

    english = set(TRANSLATIONS.get("en", {}))
    total = len(english)
    if not total:
        return {"translated": 0, "total": 0, "pct": 100, "complete": True}
    translated = len(english & set(TRANSLATIONS.get(code, {})))
    complete = translated >= total
    # Floor, and cap an incomplete language at 99: a language one string short
    # would otherwise round to 100% and claim "fully translated" while that
    # string is still English. `complete` is the only thing allowed to say that.
    pct = 100 if complete else min(99, int(100.0 * translated / total))
    return {
        "translated": translated,
        "total": total,
        "pct": pct,
        "complete": complete,
    }


def _language_preview(code):
    """English -> target pairs for a handful of familiar UI strings."""
    from ..translations import TRANSLATIONS

    english = TRANSLATIONS.get("en", {})
    target = TRANSLATIONS.get(code, {})
    pairs = []
    for key in LANGUAGE_PREVIEW_KEYS:
        source = english.get(key)
        if not source:
            continue
        pairs.append({
            "from": source,
            "to": target.get(key, source),
            "missing": key not in target,
        })
    return pairs


def _language_options():
    ordered = [name for name in LANGUAGE_ORDER if name in LANGUAGES]
    ordered += [name for name in LANGUAGES if name not in LANGUAGE_ORDER]
    options = []
    for name in ordered:
        code = LANGUAGES.get(name, "en")
        title, subtitle = _language_parts(name)
        options.append({
            "value": name,
            "label": title,
            "sub": subtitle,
            "code": code,
            "emoji": LANGUAGE_FLAGS.get(name, "🌐"),
            "greeting": LANGUAGE_GREETINGS.get(code, title),
            "coverage": _language_coverage(code),
            "preview": _language_preview(code),
        })
    return options


def _font_options():
    """Every registered font key, ordered with the default first."""
    try:
        from ..fonts import get_all_fonts

        fonts = get_all_fonts(_addon_root())
    except Exception:
        fonts = {}
    options = []
    for key, info in fonts.items():
        label = str((info or {}).get("name") or (info or {}).get("family") or key)
        options.append({"value": key, "label": label, "family": str((info or {}).get("family", "") or "")})
    options.sort(key=lambda o: (o["value"] != "system", o["label"].lower()))
    return options


def _addon_root():
    import os

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fonts_sections():
    sections = []
    for key, label_key, fallback, default_size, colour_token in FONT_ROLES:
        sections.append({
            "id": f"font_{key}",
            "title": tr(label_key, fallback),
            "layout": "font_role",
            "role_key": key,
            "fields": [
                {
                    "id": f"onigiri_font_{key}",
                    "type": "font",
                    "label": tr("font", "Font"),
                    "bind": {"kind": "col", "key": f"onigiri_font_{key}"},
                    "default": "system",
                    "options": _font_options(),
                },
                {
                    "id": f"onigiri_font_size_{key}",
                    "type": "number",
                    "label": tr("font_size", "Size"),
                    "bind": {"kind": "col", "key": f"onigiri_font_size_{key}"},
                    "default": default_size,
                    "min": 8,
                    "max": 72,
                    "step": 1,
                    "suffix": "px",
                    "reset_to": default_size,
                },
                _color_pair_field(
                    f"font_color_{key}",
                    tr("color", "Color"),
                    f"font_color_light_{key}",
                    f"font_color_dark_{key}",
                    None,
                ),
                {
                    "id": f"font_color_light_{key}",
                    "type": "hidden",
                    "label": "",
                    "bind": {"kind": "config", "path": ["colors", "light", colour_token]},
                    "default": "#1f2933",
                },
                {
                    "id": f"font_color_dark_{key}",
                    "type": "hidden",
                    "label": "",
                    "bind": {"kind": "config", "path": ["colors", "dark", colour_token]},
                    "default": "#f4f4f5",
                },
                _hidden_field(f"font_color_{key}_theme_mode"),
            ],
        })
    return sections


# ── pages ──────────────────────────────────────────────────────────────────────

def _modes_page():
    # Focus / Flow / Zen are a ladder, not three independent switches: each one
    # contains the previous (see the `cascade` rules, which mirror the old
    # dialog's _on_*_toggled handlers). `level` tells the renderer where each
    # sits, so the nesting is visible instead of implied.
    immersion = [
        {
            "id": "hideNativeHeaderAndBottomBar",
            "type": "mode_card",
            "level": 1,
            "label": tr("mode_focus", "Focus"),
            "desc": tr("hide_anki_bars", "Hide Anki's bars"),
            "notes": [tr("replaces_top_bar", ""), tr("best_onigiri_experience", "The best Onigiri experience")],
            "icon": "mode-focus-eye.svg",
            "bind": {"kind": "config", "key": "hideNativeHeaderAndBottomBar"},
            "default": True,
            # Focus is the base level: switching it off collapses Flow and Zen too.
            "cascade": {"off": {"flowMode": False, "maxHide": False}},
        },
        {
            "id": "flowMode",
            "type": "mode_card",
            "level": 2,
            "label": tr("mode_flow", "Flow"),
            "desc": tr("everything_in_focus", ""),
            "notes": [tr("hides_onigiri_top_bar", ""), tr("restart_anki_note", "")],
            "icon": "mode-flow-wind.svg",
            "bind": {"kind": "config", "key": "flowMode"},
            "default": False,
            "cascade": {
                "on": {"hideNativeHeaderAndBottomBar": True},
                "off": {"maxHide": False},
            },
        },
        {
            "id": "maxHide",
            "type": "mode_card",
            "level": 3,
            "label": tr("mode_zen", "Zen"),
            "desc": tr("everything_in_flow", ""),
            "notes": [
                tr("hides_reviewer_bottom_bar", ""),
                tr("button_only_navigation", ""),
                tr("restart_anki_note", ""),
            ],
            "icon": "mode-zen-moon-regular.svg",
            "bind": {"kind": "config", "key": "maxHide"},
            "default": False,
            "cascade": {"on": {"flowMode": True, "hideNativeHeaderAndBottomBar": True}},
        },
    ]

    # These hide things too, but they stack with any immersion level rather than
    # being part of the ladder, so they get their own plain section.
    extras = [
        {
            "id": "fullHideMode",
            "type": "mode_card",
            "label": tr("mode_full", "Full"),
            "desc": tr("hide_top_menu_bar", ""),
            "notes": [
                tr("menu_bar_items_example", ""),
                tr("windows_linux_only", ""),
                tr("restart_anki_note", ""),
            ],
            "icon": "mode-full-window-maximize-regular.svg",
            "bind": {"kind": "config", "key": "fullHideMode"},
            "default": False,
            "toast_on": tr("full_hide_restart_toast", "Restart Anki for Full Hide Mode to take effect"),
        },
    ]

    if _mac_titlebar_supported():
        extras.append({
            "id": "hideMacTitleBar",
            "type": "mode_card",
            "label": tr("mode_seamless", "Seamless"),
            "desc": tr("hide_mac_title_bar", ""),
            "notes": [tr("mac_title_bar_keeps_buttons", ""), tr("macos_only", "")],
            "icon": "top_bar.svg",
            "bind": {"kind": "config", "key": "hideMacTitleBar"},
            "default": False,
        })

    if _synapsepro_present():
        extras.append({
            "id": "hideSynapseProSidebar",
            "type": "mode_card",
            "label": tr("synapsepro_sidebar", "SynapsePro sidebar"),
            "desc": tr("hide_synapsepro_sidebar", ""),
            "notes": [tr("synapsepro_sidebar_desc", "")],
            "icon": "sidebar_left_hidden.svg",
            "bind": {"kind": "config", "key": "hideSynapseProSidebar"},
            "default": False,
        })

    return {
        "id": "modes",
        "legacy_name": "Modes",
        "title": tr("modes", "Modes"),
        "icon": "modes.svg",
        "group": "general",
        "description": tr("modes_description", ""),
        "sections": [
            {
                "id": "immersion",
                "title": "",
                "layout": "ladder",
                "fields": immersion,
            },
            {
                "id": "modes_extras",
                "title": tr("settings_web_modes_extras", "Independent"),
                "fields": extras,
            },
        ],
        "post_save": ["modes"],
    }


def _languages_page():
    return {
        "id": "languages",
        "legacy_name": "Languages",
        "title": tr("languages", "Languages"),
        "icon": "languages.svg",
        "group": "general",
        "description": tr("language_description", ""),
        "sections": [{
            "id": "language",
            "title": "",
            "fields": [{
                "id": "language",
                "type": "language",
                "label": "",
                "bind": {"kind": "config", "key": "language"},
                "default": "English (Default)",
                "options": _language_options(),
            }],
        }],
        "post_save": ["language"],
    }


def _fonts_page():
    return {
        "id": "fonts",
        "legacy_name": "Fonts",
        "title": tr("fonts", "Fonts"),
        "icon": "text.svg",
        "group": "general",
        "description": "",
        "sections": _fonts_sections(),
    }


def _sync_page():
    made_by = tr("sync_made_by", "Made by h0tp")
    return {
        "id": "sync",
        "legacy_name": "Sync",
        "title": tr("sync_button", "Sync"),
        "icon": "sync.svg",
        "group": "general",
        "description": "",
        "sections": [{
            "id": "sync",
            "title": "",
            "fields": [
                {
                    "id": "ankiweb_sync_enabled",
                    "type": "toggle",
                    "hero": True,
                    "icon": "sync.svg",
                    "label": tr("sync_title", "AnkiWeb sync"),
                    "desc": made_by,
                    "desc_link": {"text": "h0tp", "href": "https://github.com/h0tp-ftw"},
                    "bind": {"kind": "config", "key": "ankiweb_sync_enabled"},
                    "default": True,
                },
                {
                    "id": "sync_state_note",
                    "type": "note",
                    "label": tr("sync_bullet_1", ""),
                    "desc": tr("sync_bullet_4", ""),
                },
                {
                    "id": "sync_notes",
                    "type": "note",
                    "layout": "grid",
                    "items": [tr("sync_bullet_2", ""), tr("sync_bullet_3", "")],
                },
            ],
        }],
    }


def _image_field(field_id, folder, label, **extra):
    """A picture slot backed by the gallery popover.

    `light_field` / `dark_field` name the two keys used while Dynamic mode is
    on; without them (or with it off) the field stores one filename in its own
    key. Those companion keys are declared as `hidden` fields so the store
    still persists them — the popover writes them, nothing renders them."""
    field = {
        "id": field_id,
        "type": "image",
        "label": label,
        "folder": folder,
        "bind": {"kind": "col", "key": field_id},
        "default": "",
    }
    field.update(extra)
    if field.get("light_field"):
        field.setdefault("theme_mode_field", field_id + "_theme_mode")
    return field


def _designer_preview_section(
    section_id, preview_kind, fields, title="", icon="", dynamic_keys=None,
    sync_toggle_id=None, sync_hidden_fields=None, stage_side=False,
    icon_colors_inline=False, head_to_deck=False, subsections=None,
    hide_deck_when=None,
):
    """One of Main menu's self-contained "designer" cards: a live preview stage
    (painted client-side by PREVIEW_PAINTERS[preview_kind] in settings.js) plus
    its own controls, all in one section — unlike Profile's preview, which pulls
    fields from sibling sections into embedded tabs, Main menu's designers are
    single stacked cards, so the fields simply live on this same section.

    `dynamic_keys`, when given, is a list of "single"/"separate" theme-mode
    field ids that a single header switch (mirroring Profile's grouped Dynamic
    mode toggle — see PROFILE_DYNAMIC_KEYS in settings.js) sets together,
    matching how the legacy dialog's one Dynamic-mode toggle drove several
    theme-mode keys at once (e.g. Main Background's color AND image).

    `sync_toggle_id` + `sync_hidden_fields`: Stats Widgets and Deck Stats each
    have a "Sync with Widget Color and Effect" toggle that, when on, takes its
    blur/opacity/radius/stroke/box-colour values from Widget Color and Effect —
    so those rows collapse away entirely rather than sitting there greyed out,
    the same way a setting the current design cannot use disappears."""
    return {
        "id": section_id,
        "title": title,
        # Sub-menu tab glyph, used when the labels no longer fit beside the
        # page title (settings.js measures and swaps the strip to icons).
        "icon": icon,
        "layout": "designer_preview",
        "preview_kind": preview_kind,
        # Stage beside the controls instead of above them, and one column of
        # controls in schema order. For a preview whose subject is tall and
        # narrow — the sidebar — a full-width stage above a two-column deck
        # wastes the height that is the whole point of the picture.
        "stage_side": bool(stage_side),
        # Some previews have many option controls. Keep their configuration
        # rows in the deck below the stage while reserving the header for the
        # preview-only state selector and the shared utility controls.
        "head_to_deck": bool(head_to_deck),
        # Show an icon field's companion colour under its tile, not only inside
        # its popover (settings.js renderIconTileColors).
        "icon_colors_inline": bool(icon_colors_inline),
        # Some background modes inherit every value from another surface. In
        # that state their local controls are not applicable and the whole
        # settings deck should be removed, not left as an empty panel.
        "hide_deck_when": hide_deck_when or {},
        # Optional labelled groups inside the controls deck. Each entry is
        # {"id": ..., "title": ..., "fields": [...]} and keeps grouping
        # declarative without changing the field bindings.
        "subsections": subsections or [],
        "dynamic_keys": dynamic_keys or [],
        "sync_toggle_id": sync_toggle_id or "",
        "sync_hidden_fields": sync_hidden_fields or [],
        "fields": fields,
    }


def _image_list_field(field_id, folder, label, **extra):
    """A reorderable list of pictures backed by the same gallery popover as
    `_image_field`, for a setting that holds several images at once (Main
    Background's slideshow) instead of exactly one."""
    field = {
        "id": field_id,
        "type": "image_list",
        "label": label,
        "folder": folder,
        "bind": {"kind": "col", "key": field_id},
        "default": [],
    }
    field.update(extra)
    return field


def _hidden_field(field_id, default=""):
    return {
        "id": field_id,
        "type": "hidden",
        "label": "",
        "bind": {"kind": "col", "key": field_id},
        "default": default,
    }


def _hidden_config_field(field_id, path, default=""):
    """Like `_hidden_field`, but for a value that lives in the addon config
    (`conf.get(...)`) instead of `mw.col.conf`."""
    return {
        "id": field_id,
        "type": "hidden",
        "label": "",
        "bind": {"kind": "config", "path": path},
        "default": default,
    }


def _color_pair_field(field_id, label, light_field, dark_field, dynamic_field, **extra):
    """The light/dark colour pair, rendered as one control.

    Two independent colour rows made the light/dark relationship something the
    user had to infer from the labels, and gave nowhere to hang "use the same
    colour for both". This is the colour twin of `_image_field`: one row, one or
    two swatches, one link switch. The two real keys stay as `hidden` fields so
    every existing reader keeps finding them where it always did."""
    field = {
        "id": field_id,
        "type": "color_pair",
        "label": label,
        "light_field": light_field,
        "dark_field": dark_field,
        "dynamic_field": dynamic_field,
        # Remembers an explicit "same for both" across sessions. Left unset it
        # is inferred from the values themselves, so nothing has to be migrated
        # and a profile saved before this existed opens exactly as it was.
        "theme_mode_field": field_id + "_theme_mode",
    }
    field.update(extra)
    return field


def _profile_page():
    return {
        "id": "profile",
        "legacy_name": "Profile",
        "title": tr("profile", "Profile"),
        "icon": "person.svg",
        "group": "general",
        "description": tr("profile_description", "Manage your profile information, layout styles, pictures, and panel modules."),
        "sections": [
            {
                "id": "profile_preview_section",
                "title": "",
                "layout": "profile_preview",
                "fields": [],
            },
            {
                "id": "profile_info",
                "title": tr("profile_information", "Profile Information"),
                "fields": [
                    {
                        "id": "userName",
                        "type": "text",
                        "label": tr("user_name", "User Name"),
                        "bind": {"kind": "config", "key": "userName"},
                        "default": "USER",
                    },
                    {
                        "id": "userBirthday",
                        "type": "text",
                        "label": tr("birthday", "Birthday"),
                        "bind": {"kind": "config", "key": "userBirthday"},
                        "default": "",
                        "placeholder": "YYYY-MM-DD",
                    },
                    {
                        "id": "profile_status",
                        "type": "text",
                        "label": tr("profile_status", "Status"),
                        "bind": {"kind": "config", "path": ["onigiriProfile", "status"]},
                        "default": "",
                    },
                    {
                        "id": "profile_bio",
                        "type": "text",
                        "label": tr("profile_bio", "Bio"),
                        "multiline": True,
                        "bind": {"kind": "config", "path": ["onigiriProfile", "bio"]},
                        "default": "",
                    },
                    {
                        "id": "profile_music",
                        "type": "text",
                        "label": tr("profile_music", "Music Link"),
                        "placeholder": "https://open.spotify.com/... | https://music.apple.com/...",
                        "bind": {"kind": "config", "path": ["onigiriProfile", "spotifyLink"]},
                        "default": "",
                    },
                ],
            },
            {
                "id": "profile_panel_toggles",
                "title": tr("profile_panel_toggles_header", "Show in Profile Panel"),
                "fields": [
                    {
                        "id": "profile_panel_weekly_chart",
                        "type": "toggle",
                        "label": tr("profile_panel_weekly_chart", "Weekly Study Chart"),
                        "bind": {"kind": "config", "path": ["onigiriProfilePanel", "show_weekly_chart"]},
                        "default": True,
                    },
                    {
                        "id": "profile_panel_nook_level",
                        "type": "toggle",
                        "label": tr("profile_panel_nook_level", "Nook Level Progress"),
                        "bind": {"kind": "config", "path": ["restaurant_level", "show_profile_page_progress"]},
                        "default": True,
                    },
                    {
                        "id": "profile_panel_hexagon_land",
                        "type": "toggle",
                        "label": tr("profile_panel_hexagon_land", "Hexagon Land Count"),
                        "bind": {"kind": "config", "path": ["onigiriProfilePanel", "show_hexagon_land"]},
                        "default": True,
                    },
                    {
                        "id": "profile_panel_onigimon_hp",
                        "type": "toggle",
                        "label": tr("profile_panel_onigimon_hp", "Onigimon HP"),
                        "bind": {"kind": "config", "path": ["onigiriProfilePanel", "show_onigimon_hp"]},
                        "default": True,
                    },
                    {
                        "id": "profile_panel_mantras",
                        "type": "toggle",
                        "label": tr("profile_panel_mantras", "My Mantras"),
                        "bind": {"kind": "config", "path": ["onigiriProfilePanel", "show_mantras"]},
                        "default": True,
                    },
                ],
            },
            {
                # The Gamification profile *page*'s own backdrop, not the
                # profile bar's — patcher.generate_profile_page_background_css
                # paints `body` from these six keys, either a flat colour or a
                # 135° two-stop gradient (settings/_page_profile.py:1089-1102).
                # Mounted inside the Profile Sidebar tab by settings.js.
                "id": "profile_page_background",
                "title": tr("profile_page_background", "Profile Page Background"),
                "fields": [
                    {
                        "id": "onigiri_profile_page_bg_mode",
                        "type": "choice",
                        "label": tr("bg_mode", "Background Mode"),
                        "bind": {"kind": "col", "key": "onigiri_profile_page_bg_mode"},
                        "default": "color",
                        "options": [
                            {"value": "color", "label": tr("color_only", "Color only")},
                            {"value": "gradient", "label": tr("gradient", "Gradient")},
                        ],
                    },
                    {
                        "id": "onigiri_profile_page_bg_dynamic_mode",
                        "type": "toggle",
                        "label": tr("dynamic_mode", "Dynamic mode"),
                        "bind": {"kind": "col", "key": "onigiri_profile_page_bg_dynamic_mode"},
                        "default": True,
                    },
                    _color_pair_field(
                        "onigiri_profile_page_bg_color1",
                        tr("color", "Color"),
                        "onigiri_profile_page_bg_light_color1",
                        "onigiri_profile_page_bg_dark_color1",
                        "onigiri_profile_page_bg_dynamic_mode",
                    ),
                    _hidden_field("onigiri_profile_page_bg_light_color1", "#F5F5F5"),
                    _hidden_field("onigiri_profile_page_bg_dark_color1", "#2C2C2C"),
                    _hidden_field("onigiri_profile_page_bg_color1_theme_mode"),
                    _color_pair_field(
                        "onigiri_profile_page_bg_color2",
                        tr("gradient_second_color", "Second Color"),
                        "onigiri_profile_page_bg_light_color2",
                        "onigiri_profile_page_bg_dark_color2",
                        "onigiri_profile_page_bg_dynamic_mode",
                        show_when={"field": "onigiri_profile_page_bg_mode", "values": ["gradient"]},
                    ),
                    _hidden_field("onigiri_profile_page_bg_light_color2", "#E0E0E0"),
                    _hidden_field("onigiri_profile_page_bg_dark_color2", "#1A1A1A"),
                    _hidden_field("onigiri_profile_page_bg_color2_theme_mode"),
                ],
            },
            {
                "id": "profile_type_section",
                "title": tr("profile_layout_type", "Profile Layout"),
                "fields": [
                    {
                        "id": "modern_menu_profile_type",
                        "type": "choice",
                        "label": tr("profile_type", "Profile Type"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_type"},
                        "default": "bar",
                        "options": [
                            {"value": "bar", "label": tr("profile_type_bar", "Bar")},
                            {"value": "ring", "label": tr("profile_type_ring", "Ring")},
                            {"value": "minimal", "label": tr("profile_type_minimal", "Minimal")},
                        ],
                    },
                ],
            },
            {
                "id": "profile_name_appearance",
                "title": tr("profile_name_appearance", "Profile Name Appearance"),
                "fields": [
                    {
                        "id": "modern_menu_profile_name_font",
                        "type": "font",
                        "label": tr("profile_name_font", "Name Font"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_name_font"},
                        "default": "system",
                        "options": _font_options(),
                    },
                    # One of the four legacy per-asset Dynamic mode flags. The
                    # WebUI shows a single Dynamic mode switch in the profile
                    # preview header that writes all four; they stay registered
                    # here because that is what binds them to the collection.
                    # Renderers still read each key individually.
                    {
                        "id": "modern_menu_profile_name_dynamic_mode",
                        "type": "toggle",
                        "label": tr("dynamic_mode", "Dynamic mode"),
                        "desc": tr("profile_name_dynamic_desc", "Use separate colors for light and dark themes"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_name_dynamic_mode"},
                        "default": True,
                    },
                    _color_pair_field(
                        "modern_menu_profile_name_color",
                        tr("color", "Color"),
                        "modern_menu_profile_name_color_light",
                        "modern_menu_profile_name_color_dark",
                        "modern_menu_profile_name_dynamic_mode",
                    ),
                    _hidden_field("modern_menu_profile_name_color_light", "#111827"),
                    _hidden_field("modern_menu_profile_name_color_dark", "#f9fafb"),
                    _hidden_field("modern_menu_profile_name_color_theme_mode"),
                ],
            },
            {
                "id": "profile_fill_appearance",
                "title": tr("profile_ring_color", "Ring Color"),
                "fields": [
                    # Read-only: whether the classic dialog's Nook Level minigame
                    # is on. This section only makes sense (and is only shown —
                    # see updateProfileVisibility in settings.js) when it's off
                    # and Ring is the selected Profile Type, so JS needs the
                    # current value even though nothing here edits it.
                    _hidden_config_field("restaurant_level_nook_enabled_ro", ["restaurant_level", "enabled"], False),
                    # Written by the shared Dynamic mode switch — see the note on
                    # modern_menu_profile_name_dynamic_mode above.
                    {
                        "id": "modern_menu_profile_fill_dynamic_mode",
                        "type": "toggle",
                        "label": tr("dynamic_mode", "Dynamic mode"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_fill_dynamic_mode"},
                        "default": True,
                    },
                    _color_pair_field(
                        "modern_menu_profile_fill_color",
                        tr("color", "Color"),
                        "modern_menu_profile_fill_color_light",
                        "modern_menu_profile_fill_color_dark",
                        "modern_menu_profile_fill_dynamic_mode",
                    ),
                    _hidden_field("modern_menu_profile_fill_color_light", "#4f7cff"),
                    _hidden_field("modern_menu_profile_fill_color_dark", "#4f7cff"),
                    _hidden_field("modern_menu_profile_fill_color_theme_mode"),
                ],
            },
            {
                "id": "profile_picture_appearance",
                "title": tr("profile_picture", "Profile Picture"),
                "fields": [
                    {
                        "id": "modern_menu_profile_picture_mode",
                        "type": "choice",
                        "label": tr("picture_mode", "Picture Mode"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_picture_mode"},
                        "default": "image",
                        "options": [
                            {"value": "image", "label": tr("image", "Image")},
                            {"value": "custom", "label": tr("color_only", "Color only")},
                            {"value": "accent", "label": tr("accent_color", "Accent color")},
                        ],
                    },
                    # Written by the shared Dynamic mode switch — see the note on
                    # modern_menu_profile_name_dynamic_mode above.
                    {
                        "id": "modern_menu_profile_picture_dynamic_mode",
                        "type": "toggle",
                        "label": tr("dynamic_mode", "Dynamic mode"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_picture_dynamic_mode"},
                        "default": True,
                    },
                    _image_field(
                        "modern_menu_profile_picture",
                        "profile",
                        tr("profile_picture", "Profile Picture"),
                        dynamic_field="modern_menu_profile_picture_dynamic_mode",
                        light_field="modern_menu_profile_picture_light",
                        dark_field="modern_menu_profile_picture_dark",
                        empty_label=tr("none_default", "Default"),
                    ),
                    _hidden_field("modern_menu_profile_picture_light"),
                    _hidden_field("modern_menu_profile_picture_dark"),
                    _hidden_field("modern_menu_profile_picture_theme_mode"),
                    _color_pair_field(
                        "modern_menu_profile_picture_color",
                        tr("color", "Color"),
                        "modern_menu_profile_picture_color_light",
                        "modern_menu_profile_picture_color_dark",
                        "modern_menu_profile_picture_dynamic_mode",
                    ),
                    _hidden_field("modern_menu_profile_picture_color_light", "#8CACB4"),
                    _hidden_field("modern_menu_profile_picture_color_dark", "#B8BDC3"),
                    _hidden_field("modern_menu_profile_picture_color_theme_mode"),
                    {
                        # The renderer blurs the picture from this key
                        # (onigiri_renderer.py:351, patcher.py:917). The legacy
                        # page had no control for it and hard-wrote 0 on every
                        # save, next to an opacity slider that nothing outside
                        # the dialog's own preview ever read — so the setting
                        # that actually reaches the screen is the one exposed
                        # here, and the one that never did is left alone.
                        "id": "modern_menu_profile_picture_blur",
                        "type": "slider",
                        "label": tr("blur_intensity", "Blur Intensity"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_picture_blur"},
                        "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
                    },
                ],
            },
            {
                "id": "profile_bg_appearance",
                "title": tr("profile_bar_bg", "Profile Bar Background"),
                "fields": [
                    {
                        "id": "modern_menu_profile_bg_mode",
                        "type": "choice",
                        "label": tr("bg_mode", "Background Mode"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_bg_mode"},
                        "default": "image",
                        "options": [
                            {"value": "image", "label": tr("image", "Image")},
                            {"value": "custom", "label": tr("color_only", "Color only")},
                            {"value": "accent", "label": tr("accent_color", "Accent color")},
                        ],
                    },
                    # Written by the shared Dynamic mode switch — see the note on
                    # modern_menu_profile_name_dynamic_mode above.
                    {
                        "id": "modern_menu_profile_bg_dynamic_mode",
                        "type": "toggle",
                        "label": tr("dynamic_mode", "Dynamic mode"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_bg_dynamic_mode"},
                        "default": True,
                    },
                    _image_field(
                        "modern_menu_profile_bg_image",
                        "profile_bg",
                        tr("select_bg_image", "Background Image"),
                        dynamic_field="modern_menu_profile_bg_dynamic_mode",
                        light_field="modern_menu_profile_bg_image_light",
                        dark_field="modern_menu_profile_bg_image_dark",
                        empty_label=tr("none_default", "Default"),
                    ),
                    _hidden_field("modern_menu_profile_bg_image_light"),
                    _hidden_field("modern_menu_profile_bg_image_dark"),
                    _hidden_field("modern_menu_profile_bg_image_theme_mode"),
                    # Shown in Image mode too, not only in Color-only: it fills
                    # the bar *behind* the picture, so it is what the user sees
                    # blending through as the opacity slider comes down. Having
                    # to leave Image mode to set it was the reason a low opacity
                    # looked like it faded to nothing in particular.
                    _color_pair_field(
                        "modern_menu_profile_bg_color",
                        tr("color", "Color"),
                        "modern_menu_profile_bg_color_light",
                        "modern_menu_profile_bg_color_dark",
                        "modern_menu_profile_bg_dynamic_mode",
                        desc_alt=tr(
                            "settings_web_bg_color_behind_image",
                            "Sits behind the image — it blends through as opacity drops.",
                        ),
                    ),
                    _hidden_field("modern_menu_profile_bg_color_light", "#EEEEEE"),
                    _hidden_field("modern_menu_profile_bg_color_dark", "#3C3C3C"),
                    _hidden_field("modern_menu_profile_bg_color_theme_mode"),
                    {
                        "id": "modern_menu_profile_bg_blur",
                        "type": "slider",
                        "label": tr("blur", "Blur"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_bg_blur"},
                        "default": 0,
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "suffix": "%",
                        "min_label": "0%",
                        "max_label": "100%",
                    },
                    {
                        "id": "modern_menu_profile_bg_opacity",
                        "type": "slider",
                        "label": tr("opacity", "Opacity"),
                        "bind": {"kind": "col", "key": "modern_menu_profile_bg_opacity"},
                        "default": 50,
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "suffix": "%",
                        "min_label": "0%",
                        "max_label": "100%",
                    },
                ],
            },
        ],
        "post_save": ["profile"],
    }


def _themes_page():
    return {
        "id": "themes",
        "legacy_name": "Themes",
        "title": tr("themes", "Themes"),
        "icon": "themes.svg",
        "group": "general",
        "description": tr(
            "themes_description",
            "Apply a full color palette, save your own, or import one someone shared.",
        ),
        "sections": [{
            "id": "theme_gallery",
            "title": "",
            "layout": "themes",
            "fields": [],
        }],
    }


def _legacy_page(page_id, legacy_name, title, icon, group):
    """A page still served by the classic PyQt dialog."""
    return {
        "id": page_id,
        "legacy_name": legacy_name,
        "title": title,
        "icon": icon,
        "group": group,
        "legacy_page": legacy_name,
        "sections": [],
    }


# ── Study Tools ───────────────────────────────────────────────────────────────
#
# These pages deliberately bind to the same collection/config locations as the
# former Qt pages.  The WebUI is therefore the sole editable surface; no
# conversion or duplicated preference document is involved.

def _col_path(key, *path):
    return {"kind": "col_path", "key": key, "path": list(path)}


def _tool_action(field_id, label, button_label, action, desc=""):
    return {
        "id": field_id,
        "type": "action",
        "label": label,
        "desc": desc,
        "button_label": button_label,
        "action": action,
    }


def _prep_station_page():
    col = lambda key, _default: {"kind": "col", "key": key}
    return {
        "id": "prepstation",
        "legacy_name": "Prep Station",
        "title": tr("prep_station_title", "Prep Station"),
        "icon": "stats.svg",
        "group": "tools",
        "description": tr("prep_station_intro", "Plan your exam preparation and tune the Study Plans widget."),
        "sections": [
            {
                "id": "prep_open", "title": "", "fields": [
                    _tool_action("prep_open_action", "", tr("prep_station_open", "Open Prep Station"), "open_prep_station"),
                ],
            },
            {
                "id": "prep_pace", "title": tr("prep_pace_section_title", "Pace & Statistics"),
                "fields": [
                    {
                        "id": "prep_include_suspended", "type": "toggle",
                        "label": tr("prep_suspended_label", "Count suspended cards"),
                        "desc": tr("prep_suspended_setting_desc", "When on, suspended cards count toward each plan's pace calculation and statistics."),
                        "bind": col("onigiri_prep_station_include_suspended", False), "default": False,
                    },
                    {
                        "id": "prep_week_start", "type": "choice",
                        "label": tr("week_start_label", "Week Starts On"),
                        "desc": tr("prep_week_start_desc", "Sets the first day shown in Prep Station's weekly charts."),
                        "bind": col("onigiri_prep_station_week_start", "monday"), "default": "monday",
                        "options": [
                            {"value": "monday", "label": tr("week_start_monday", "Monday")},
                            {"value": "sunday", "label": tr("week_start_sunday", "Sunday")},
                        ],
                    },
                ],
            },
            {
                "id": "prep_widget", "title": tr("prep_widget_section_title", "Study Plans Widget"),
                "fields": [{
                    "id": "prep_widget_font_scale", "type": "slider",
                    "label": tr("prep_widget_font_label", "Font Size"),
                    "desc": tr("prep_widget_font_desc", "Font size of the Study Plans preview shown on the deck browser widget."),
                    "bind": col("onigiri_prep_station_widget_font_scale", 100), "default": 100,
                    "min": 60, "max": 160, "step": 1, "suffix": "%",
                }],
            },
        ],
    }


def _hashi_note_options():
    options = [{"value": "", "label": tr("hashi_widget_newest_note", "Most recent note")}]
    try:
        from .. import hashi_notes
        for note in hashi_notes.load_notes():
            note_id = str(note.get("id") or "")
            if note_id:
                options.append({"value": note_id, "label": str(note.get("title") or tr("hashi_untitled", "Untitled"))})
    except Exception:
        pass
    return options


def _hashi_notes_page():
    path = lambda *parts: {"kind": "config", "path": ["hashi_widget_style", *parts]}
    def color(key, label, light, dark):
        return [
            _color_pair_field("hashi_widget_color_" + key, label, "hashi_widget_color_" + key + "_light", "hashi_widget_color_" + key + "_dark", "hashi_widget_dynamic"),
            {"id": "hashi_widget_color_" + key + "_light", "type": "hidden", "label": "", "bind": path("colors", "light", key), "default": light},
            {"id": "hashi_widget_color_" + key + "_dark", "type": "hidden", "label": "", "bind": path("colors", "dark", key), "default": dark},
        ]
    widget_fields = [
        {"id": "hashi_widget_mode", "type": "choice", "label": tr("hashi_widget_mode", "Layout"), "bind": path("mode"), "default": "gallery", "options": [{"value": "gallery", "label": tr("hashi_widget_mode_gallery", "Gallery")}, {"value": "single", "label": tr("hashi_widget_mode_single", "Single note")}]},
        {"id": "hashi_widget_note_id", "type": "select", "label": tr("hashi_widget_pinned_note", "Pinned note"), "bind": path("note_id"), "default": "", "options": _hashi_note_options(), "show_when": {"field": "hashi_widget_mode", "values": ["single"]}},
        {"id": "hashi_widget_limit", "type": "slider", "label": tr("hashi_widget_limit", "Notes shown"), "bind": path("limit"), "default": 4, "min": 1, "max": 4, "suffix": ""},
        {"id": "hashi_widget_sync", "type": "toggle", "label": tr("sync_with_box_effect", "Sync with Widget Color and Effect"), "bind": path("sync_box_effect"), "default": True},
        {"id": "hashi_widget_dynamic", "type": "toggle", "label": tr("dynamic_mode", "Dynamic mode"), "bind": path("dynamic"), "default": True},
        {"id": "hashi_widget_show_icon", "type": "toggle", "label": tr("hashi_widget_show_icon", "Show note icons"), "bind": path("show_icon"), "default": True},
        {"id": "hashi_widget_show_excerpt", "type": "toggle", "label": tr("hashi_widget_show_excerpt", "Show excerpt"), "bind": path("show_excerpt"), "default": True},
        {"id": "hashi_widget_show_date", "type": "toggle", "label": tr("hashi_widget_show_date", "Show date"), "bind": path("show_date"), "default": True},
        {"id": "hashi_widget_blur", "type": "slider", "label": tr("blur", "Blur"), "bind": path("blur"), "default": 0, "min": 0, "max": 100, "suffix": "%"},
        {"id": "hashi_widget_opacity", "type": "slider", "label": tr("opacity", "Opacity"), "bind": path("opacity"), "default": 100, "min": 0, "max": 100, "suffix": "%"},
        {"id": "hashi_widget_radius", "type": "slider", "label": tr("border_radius", "Border Radius"), "bind": path("radius"), "default": 20, "min": 0, "max": 60, "suffix": "px"},
        {"id": "hashi_widget_stroke", "type": "slider", "label": tr("border_width", "Border Width"), "bind": path("stroke"), "default": 1, "min": 0, "max": 10, "suffix": "px"},
    ]
    widget_fields += color("box_bg", tr("box_background", "Box Background"), "#ffffff", "#2c2c2c")
    widget_fields += color("box_border", tr("border_color", "Border Color"), "#e0e0e0", "#424242")
    widget_fields += color("card_bg", tr("hashi_widget_card_color", "Note Card Color"), "#f5f5f5", "#363636")
    widget_fields += color("accent", tr("hashi_widget_accent_color", "Accent"), "#0077C8", "#4da3e8")
    widget_fields += color("title", tr("hashi_widget_title_color", "Title Color"), "#212121", "#f0f0f0")
    widget_fields += color("excerpt", tr("hashi_widget_excerpt_color", "Excerpt Color"), "#757575", "#9c9c9c")
    return {
        "id": "hashinotes", "legacy_name": "Hashi Notes", "title": tr("hashi_notes_title", "Hashi Notes"), "icon": "hashi_notes.svg", "group": "tools",
        "description": tr("hashi_settings_intro", "Hashi Notes are quick, temporary study notes."),
        "sections": [
            {"id": "hashi_open", "title": "", "fields": [_tool_action("hashi_open_action", "", tr("hashi_open_button", "Open Hashi Notes"), "open_hashi_notes")]},
            {"id": "hashi_options", "title": tr("hashi_options", "Options"), "fields": [
                {"id": "hashi_retention", "type": "choice", "label": tr("hashi_default_retention", "Default retention"), "bind": {"kind": "config", "path": ["hashi_notes", "retention_default"]}, "default": 0, "options": [{"value": 7, "label": tr("hashi_7_days", "7 days")}, {"value": 30, "label": tr("hashi_30_days", "30 days")}, {"value": 0, "label": tr("hashi_never", "Never")}]},
                {"id": "hashi_sort", "type": "choice", "label": tr("hashi_default_sort", "Default sort"), "bind": {"kind": "config", "path": ["hashi_notes", "default_sort"]}, "default": "age", "options": [{"value": "age", "label": tr("hashi_sort_age", "Age")}, {"value": "tags", "label": tr("hashi_sort_tags", "Tags")}, {"value": "priority", "label": tr("hashi_sort_priority", "Priority")}, {"value": "title", "label": tr("hashi_sort_title", "Title")}]},
                {"id": "hashi_show_header", "type": "toggle", "label": tr("hashi_show_in_header", "Show in Reviewer header"), "bind": {"kind": "config", "path": ["hashi_notes", "show_in_reviewer_header"]}, "default": True},
                {"id": "hashi_custom_css", "type": "text", "multiline": True, "label": tr("hashi_custom_css", "Custom CSS"), "desc": tr("hashi_custom_css_desc", "Fine-tune the Hashi Notes gallery and editor. Changes apply the next time the window opens."), "bind": {"kind": "config", "path": ["hashi_notes", "custom_css"]}, "default": "", "placeholder": ":root {\n  --accent: #00A982;\n}"},
            ]},
            {"id": "hashi_widget", "title": tr("hashi_widget_section", "Dashboard Widget"), "fields": widget_fields},
        ],
    }


def _pomodoro_page():
    path = lambda *parts: _col_path("onigiri_pomodoro_settings", *parts)
    def color(key, label, light, dark):
        return [
            _color_pair_field("pomodoro_color_" + key, label, "pomodoro_color_" + key + "_light", "pomodoro_color_" + key + "_dark", "pomodoro_dynamic"),
            {"id": "pomodoro_color_" + key + "_light", "type": "hidden", "label": "", "bind": path("colors", "light", key), "default": light},
            {"id": "pomodoro_color_" + key + "_dark", "type": "hidden", "label": "", "bind": path("colors", "dark", key), "default": dark},
        ]
    appearance = [
        {"id": "pomodoro_icon", "type": "icon", "label": tr("pomodoro_icon", "Timer Icon"), "bind": path("icon"), "default": "system:pomodoro.svg"},
        {"id": "pomodoro_font", "type": "font", "label": tr("pomodoro_font", "Timer Font"), "bind": path("font_key"), "default": "system", "options": _font_options()},
        {"id": "pomodoro_size", "type": "choice", "label": tr("pomodoro_size", "Timer Size"), "bind": path("size"), "default": "small", "options": [{"value": "small", "label": tr("pomodoro_size_small", "Small")}, {"value": "medium", "label": tr("pomodoro_size_medium", "Medium")}, {"value": "big", "label": tr("pomodoro_size_big", "Big")}]},
        {"id": "pomodoro_dynamic", "type": "toggle", "label": tr("pomodoro_dynamic_mode", "Dynamic Mode"), "bind": path("dynamic_mode"), "default": True},
        {"id": "pomodoro_opacity", "type": "slider", "label": tr("pomodoro_opacity", "Opacity"), "bind": path("shell_opacity"), "default": 100, "min": 0, "max": 100, "suffix": "%"},
        {"id": "pomodoro_blur", "type": "slider", "label": tr("pomodoro_blur", "Blur"), "bind": path("shell_blur"), "default": 0, "min": 0, "max": 100, "suffix": "%"},
    ]
    appearance += color("shell", tr("pomodoro_color_shell", "Background"), "", "")
    appearance += color("accent", tr("pomodoro_color_accent", "Accent"), "", "")
    appearance += color("digits", tr("pomodoro_color_digits", "Timer Numbers"), "", "")
    appearance += color("icon", tr("pomodoro_color_icon", "Icon & Text"), "", "")
    return {
        "id": "pomodoro", "legacy_name": "Pomodoro", "title": tr("pomodoro_title", "Pomodoro"), "icon": "pomodoro.svg", "group": "tools",
        "description": tr("pomodoro_page_intro", "A minimal focus timer. Open the floating island with Shift+P, the Reviewer header button, or the Study Tools menu."),
        "post_save": ["pomodoro"],
        "sections": [
            {"id": "pomodoro_open", "title": "", "fields": [_tool_action("pomodoro_open_action", "", tr("pomodoro_open_button", "Open Pomodoro"), "open_pomodoro")]},
            {"id": "pomodoro_durations", "title": tr("pomodoro_durations", "Durations"), "fields": [
                {"id": "pomodoro_focus", "type": "number", "label": tr("pomodoro_focus", "Focus"), "bind": path("focus_minutes"), "default": 25, "min": 1, "max": 180, "suffix": tr("pomodoro_unit_min", "min")},
                {"id": "pomodoro_short_break", "type": "number", "label": tr("pomodoro_short_break", "Short Break"), "bind": path("short_break_minutes"), "default": 5, "min": 1, "max": 60, "suffix": tr("pomodoro_unit_min", "min")},
                {"id": "pomodoro_long_break", "type": "number", "label": tr("pomodoro_long_break", "Long Break"), "bind": path("long_break_minutes"), "default": 15, "min": 1, "max": 90, "suffix": tr("pomodoro_unit_min", "min")},
                {"id": "pomodoro_cycle", "type": "number", "label": tr("pomodoro_sessions_until_long", "Sessions until Long Break"), "bind": path("sessions_until_long_break"), "default": 4, "min": 1, "max": 12, "suffix": tr("pomodoro_unit_sessions", "sessions")},
            ]},
            {"id": "pomodoro_options", "title": tr("pomodoro_options", "Options"), "fields": [
                {"id": "pomodoro_show_header", "type": "toggle", "label": tr("pomodoro_show_in_header", "Show in Reviewer header"), "bind": {"kind": "config", "key": "onigiri_pomodoro_show_in_reviewer_header"}, "default": True},
                {"id": "pomodoro_auto_start", "type": "toggle", "label": tr("pomodoro_auto_start", "Auto-start next timer"), "bind": path("auto_start_next_phase"), "default": True},
            ]},
            {"id": "pomodoro_appearance", "title": tr("pomodoro_appearance", "Appearance"), "fields": appearance},
            {"id": "pomodoro_sound", "title": tr("pomodoro_sound", "Sound"), "fields": [
                {"id": "pomodoro_sound_enabled", "type": "toggle", "label": tr("pomodoro_sound_enabled", "Play Sound"), "bind": path("sound_enabled"), "default": True},
                {"id": "pomodoro_sound_file", "type": "text", "label": tr("pomodoro_choose_sound", "Choose Sound File…"), "bind": path("sound_file"), "default": "", "placeholder": tr("pomodoro_reset_sound", "Default chime")},
                _tool_action("pomodoro_choose_sound_action", "", tr("pomodoro_choose_sound", "Choose Sound File…"), "pomodoro_choose_sound"),
                _tool_action("pomodoro_test_sound_action", "", tr("pomodoro_test_sound", "Test Sound"), "pomodoro_test_sound"),
            ]},
        ],
    }


def _mainmenu_background_section():
    """Main Background designer. Config keys match the legacy page exactly
    (settings/_page_backgrounds.py, settings/_page_mainmenu.py:2201-2241) with
    one deliberate simplification: the legacy "Color only" / "Slideshow"
    toggle pair (which only ever produced one of three `modern_menu_background_mode`
    values) becomes a single 3-way choice writing that same key directly.

    `modern_menu_bg_image_theme_mode` is the canonical dynamic-mode key (what
    every OTHER reader already prefers — see `_page_backgrounds.py:2050`'s
    fallback chain); `modern_menu_background_image_mode` is kept as a hidden
    mirror purely for old readers that only know that key, exactly as legacy's
    own save path writes both (`_page_mainmenu.py:2213-2214`)."""
    return _designer_preview_section(
        "mainmenu_background",
        "background",
        title=tr("main_background_section", "Main Background"),
        icon="paintbrush.svg",
        dynamic_keys=[
            "modern_menu_bg_color_theme_mode",
            "modern_menu_bg_image_theme_mode",
            "modern_menu_background_image_mode",
        ],
        fields=[
            {
                "id": "modern_menu_background_mode",
                "type": "choice",
                # Sits in the card header as a segmented control, not as a row
                # below the stage — it is what the whole card is *about*.
                "head": True,
                "head_label": tr("style", "Style"),
                "label": tr("bg_mode", "Background Mode"),
                "bind": {"kind": "col", "key": "modern_menu_background_mode"},
                "default": "image_color",
                "options": [
                    {"value": "image_color", "label": tr("image", "Image")},
                    {"value": "color", "label": tr("color_only", "Color only")},
                    {"value": "slideshow", "label": tr("slideshow", "Slideshow")},
                ],
            },
            _color_pair_field(
                "modern_menu_bg_color",
                tr("color", "Color"),
                "modern_menu_bg_color_light",
                "modern_menu_bg_color_dark",
                None,
                show_when={"field": "modern_menu_background_mode", "values": ["color", "image_color"]},
            ),
            _hidden_field("modern_menu_bg_color_light", "#EEEEEE"),
            _hidden_field("modern_menu_bg_color_dark", "#3C3C3C"),
            _hidden_field("modern_menu_bg_color_theme_mode", "separate"),
            _image_field(
                "modern_menu_background_image",
                "main_bg",
                tr("select_bg_image", "Background Image"),
                light_field="modern_menu_background_image_light",
                dark_field="modern_menu_background_image_dark",
                theme_mode_field="modern_menu_bg_image_theme_mode",
                empty_label=tr("none_default", "Default"),
                show_when={"field": "modern_menu_background_mode", "values": ["image_color"]},
            ),
            _hidden_field("modern_menu_background_image_light"),
            _hidden_field("modern_menu_background_image_dark"),
            _hidden_field("modern_menu_bg_image_theme_mode", "separate"),
            _hidden_field("modern_menu_background_image_mode", "separate"),
            _image_list_field(
                "modern_menu_slideshow_images",
                "main_bg",
                tr("slideshow_images", "Slideshow Images"),
                show_when={"field": "modern_menu_background_mode", "values": ["slideshow"]},
            ),
            {
                # Stored in seconds, edited as amount + unit (seconds/minutes/
                # hours) — the renderer derives the unit from the value, so the
                # stored key stays exactly what every reader expects.
                "id": "modern_menu_slideshow_interval",
                "type": "duration",
                "label": tr("slideshow_interval", "Slide Interval"),
                "bind": {"kind": "col", "key": "modern_menu_slideshow_interval"},
                "default": 5,
                "show_when": {"field": "modern_menu_background_mode", "values": ["slideshow"]},
            },
            {
                "id": "modern_menu_background_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                "bind": {"kind": "col", "key": "modern_menu_background_blur"},
                "default": 0,
                "min": 0,
                "max": 100,
                "step": 1,
                "suffix": "%",
            },
            {
                "id": "modern_menu_background_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "col", "key": "modern_menu_background_opacity"},
                "default": 100,
                "min": 0,
                "max": 100,
                "step": 1,
                "suffix": "%",
            },
        ],
    )


def _overview_background_section():
    """Overviewer Background designer (settings/_page_overviews.py:15-44, built
    from the same generic modern-background designer as Main Background —
    settings/_page_backgrounds.py — but with `prefix="overview"` and, unlike
    every other user of that designer, `storage="config"`: these keys live in
    the addon config, not `mw.col.conf`.

    Four modes, matching the legacy designer's `allow_main_sync=True` spec
    (settings/_page_overviews.py:25-37): Image, Color only, Slideshow, and
    "Match Main Menu", which borrows Main Background's own colour/image but
    keeps its *own* blur/opacity pair (`main_sync_blur_key` /
    `main_sync_opacity_key` — patcher.py:3421-3430 reads those two keys and no
    others while the mode is "main")."""
    return _designer_preview_section(
        "overview_background",
        "overview_background",
        title=tr("overviewer_background_section", "Overviewer Background"),
        icon="paintbrush.svg",
        dynamic_keys=[
            "overview_bg_color_theme_mode",
            "overview_bg_image_theme_mode",
        ],
        fields=[
            {
                "id": "overview_background_mode",
                "type": "choice",
                "head": True,
                "head_label": tr("style", "Style"),
                "label": tr("bg_mode", "Background Mode"),
                "bind": {"kind": "config", "key": "onigiri_overview_bg_mode"},
                "default": "color",
                "options": [
                    {"value": "image_color", "label": tr("image", "Image")},
                    {"value": "color", "label": tr("color_only", "Color only")},
                    {"value": "slideshow", "label": tr("slideshow", "Slideshow")},
                    {"value": "main", "label": tr("match_main_menu", "Match Main Menu")},
                ],
            },
            _color_pair_field(
                "overview_bg_color",
                tr("color", "Color"),
                "overview_bg_color_light",
                "overview_bg_color_dark",
                None,
                show_when={"field": "overview_background_mode", "values": ["color", "image_color"]},
            ),
            _hidden_config_field("overview_bg_color_light", ["onigiri_overview_bg_light_color"], "#f2f2f2"),
            _hidden_config_field("overview_bg_color_dark", ["onigiri_overview_bg_dark_color"], "#2C2C2C"),
            _hidden_config_field("overview_bg_color_theme_mode", ["onigiri_overview_bg_color_theme_mode"], "separate"),
            _image_field(
                "overview_background_image",
                # Same on-disk folder as Main Background (GALLERY_ASSET_FOLDERS
                # groups both under "Main Menu & Overviewer") — one shared pool
                # of pictures, not a separate "overview_bg" folder.
                "main_bg",
                tr("select_bg_image", "Background Image"),
                light_field="overview_background_image_light",
                dark_field="overview_background_image_dark",
                theme_mode_field="overview_bg_image_theme_mode",
                empty_label=tr("none_default", "Default"),
                show_when={"field": "overview_background_mode", "values": ["image_color"]},
                bind={"kind": "config", "key": "onigiri_overview_bg_image"},
            ),
            _hidden_config_field("overview_background_image_light", ["onigiri_overview_bg_image_light"]),
            _hidden_config_field("overview_background_image_dark", ["onigiri_overview_bg_image_dark"]),
            _hidden_config_field("overview_bg_image_theme_mode", ["onigiri_overview_bg_image_theme_mode"], "separate"),
            _hidden_config_field("overview_background_image_mode", ["onigiri_overview_bg_image_mode"], "separate"),
            _image_list_field(
                "overview_slideshow_images",
                "main_bg",
                tr("slideshow_images", "Slideshow Images"),
                show_when={"field": "overview_background_mode", "values": ["slideshow"]},
                bind={"kind": "config", "key": "onigiri_overview_slideshow_images"},
            ),
            {
                "id": "overview_slideshow_interval",
                "type": "duration",
                "label": tr("slideshow_interval", "Slide Interval"),
                "bind": {"kind": "config", "key": "onigiri_overview_slideshow_interval"},
                "default": 5,
                "show_when": {"field": "overview_background_mode", "values": ["slideshow"]},
            },
            {
                "id": "overview_background_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                "bind": {"kind": "config", "key": "onigiri_overview_bg_blur"},
                "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"not": {"field": "overview_background_mode", "values": ["main"]}},
            },
            {
                "id": "overview_background_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "config", "key": "onigiri_overview_bg_opacity"},
                "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"not": {"field": "overview_background_mode", "values": ["main"]}},
            },
            # Match Main Menu keeps its own blur/opacity so the same picture can
            # sit quiet behind the overview and loud behind the deck browser.
            {
                "id": "overview_background_main_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                "bind": {"kind": "config", "key": "onigiri_overview_bg_main_blur"},
                "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"field": "overview_background_mode", "values": ["main"]},
            },
            {
                "id": "overview_background_main_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "config", "key": "onigiri_overview_bg_main_opacity"},
                "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"field": "overview_background_mode", "values": ["main"]},
            },
        ],
        hide_deck_when={"field": "overview_background_mode", "values": ["main"]},
    )


def _overview_style_section():
    """Overview Style designer (settings/_page_overviews.py:587-1525): the
    Overviewer/Congrats card's box, Study Now button and card-count colours,
    ported onto the shared designer_preview + sync-with-widgets shape (see
    _mainmenu_deck_stats_section). `dynamic` stays fixed True as in legacy —
    Overview Style always keeps separate light/dark colours, so unlike Stats
    Widgets/Deck Stats there is no user-facing Dynamic mode toggle here."""
    path = lambda *parts: {"kind": "config", "path": ["overview_style", *parts]}

    def color(key, label, default_light, default_dark, show_when=None, always_split=False):
        pair_extra = {"always_split": True} if always_split else {}
        return [
            _color_pair_field(
                f"ovstyle_color_{key}", label,
                f"ovstyle_color_{key}_light", f"ovstyle_color_{key}_dark", None,
                **pair_extra,
                **({"show_when": show_when} if show_when else {}),
            ),
            {"id": f"ovstyle_color_{key}_light", "type": "hidden", "label": "",
             "bind": path("colors", "light", key), "default": default_light},
            {"id": f"ovstyle_color_{key}_dark", "type": "hidden", "label": "",
             "bind": path("colors", "dark", key), "default": default_dark},
            # The shared Dynamic mode switch below writes each colour pair's
            # state independently.  Keep that presentation state separate
            # from the legacy light/dark colour values, which remain the only
            # values the overview renderer consumes.
            {"id": f"ovstyle_color_{key}_theme_mode", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"onigiri_web_ovstyle_color_{key}_theme_mode"},
             "default": "separate"},
        ]

    fields = [
        {
            "id": "ovstyle_design", "type": "choice", "label": tr("design", "Design"),
            # Rendered in the settings deck; the preview header is reserved
            # for its local Overview/Congrats selector and utility controls.
            "head": False,
            "bind": {"kind": "col", "key": "onigiri_overview_style"}, "default": "pro",
            "options": [
                {"value": "pro", "label": tr("overview_style_pro", "Pro")},
                {"value": "mini", "label": tr("overview_style_mini", "Mini")},
            ],
        },
        {
            "id": "ovstyle_sync_box_effect", "type": "toggle",
            # Rendered below the preview alongside the other style controls.
            "head": False,
            "label": tr("sync_with_box_effect", "Sync with Widget Color and Effect"),
            "bind": path("sync_box_effect"), "default": False,
        },
        {
            "id": "ovstyle_blur", "type": "slider", "label": tr("blur", "Blur"),
            "bind": path("blur"), "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "ovstyle_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
            "bind": path("opacity"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "ovstyle_radius", "type": "slider", "label": tr("border_radius", "Border Radius"),
            "bind": path("radius"), "default": 20, "min": 0, "max": 60, "step": 1, "suffix": "px",
        },
        {
            "id": "ovstyle_stroke", "type": "slider", "label": tr("border_width", "Border Width"),
            "bind": path("stroke"), "default": 1, "min": 0, "max": 10, "step": 1, "suffix": "px",
        },
        {
            "id": "ovstyle_study_button_opacity", "type": "slider",
            "label": tr("study_button_opacity", "Study Button Opacity"),
            "bind": path("study_button_opacity"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "ovstyle_study_button_radius", "type": "slider",
            "label": tr("study_button_radius", "Study Button Radius"),
            "bind": path("study_button_radius"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "ovstyle_study_button_stroke", "type": "slider",
            "label": tr("study_button_stroke", "Study Button Stroke"),
            "bind": path("study_button_stroke"), "default": 0, "min": 0, "max": 10, "step": 1, "suffix": "px",
        },
        # As soon as the button has a visible stroke, expose its own colour
        # pair so both themes can be tuned independently.
        _color_pair_field(
            "ovstyle_color_study_button_stroke",
            tr("study_button_stroke_color", "Study Button Stroke Color"),
            "ovstyle_color_study_button_stroke_light",
            "ovstyle_color_study_button_stroke_dark",
            None,
            show_when={"field": "ovstyle_study_button_stroke", "greater_than": 0},
        ),
        {"id": "ovstyle_color_study_button_stroke_light", "type": "hidden", "label": "",
         "bind": path("colors", "light", "study_button_stroke"), "default": "#e0e0e0"},
        {"id": "ovstyle_color_study_button_stroke_dark", "type": "hidden", "label": "",
         "bind": path("colors", "dark", "study_button_stroke"), "default": "#565656"},
        {
            "id": "ovstyle_study_button_dashed", "type": "toggle",
            "label": tr("dashed_stroke", "Dashed stroke"),
            "bind": path("study_button_dashed"), "default": False,
        },
        {
            "id": "ovstyle_study_button_animated", "type": "toggle",
            "label": tr("animated_hover_effect", "Animated (hover effect)"),
            "bind": path("study_button_animated"), "default": True,
        },
        {
            "id": "show_congrats_due_later_notice", "type": "toggle",
            "label": tr("show_congrats_due_later_notice", "Show next learning card notice on Congrats"),
            "desc": tr(
                "show_overview_due_later_notice_desc",
                "Show when the next learning card is ready, how many are due later today, and an expandable upcoming-card list.",
            ),
            "bind": {"kind": "config", "key": "showNextLearningCardNoticeOnCongrats"}, "default": True,
        },
        {
            "id": "show_overview_due_later_notice", "type": "toggle",
            "label": tr("show_overview_due_later_notice", "Show next learning card notice on Overview"),
            "desc": tr(
                "show_overview_due_later_notice_desc",
                "Show when the next learning card is ready, how many are due later today, and an expandable upcoming-card list.",
            ),
            "bind": {"kind": "config", "key": "showNextLearningCardNoticeOnOverview"}, "default": True,
        },
        {
            "id": "overview_study_now_text", "type": "text",
            "label": tr("custom_stats_title_study_now", "Custom Stats Title (Study Now)"),
            "bind": {"kind": "col", "key": "modern_menu_studyNowText"}, "default": "Study Now",
        },
        {
            "id": "overview_congrats_message", "type": "text",
            "label": tr("congrats_message", "Congrats Message"),
            "multiline": True,
            "bind": {"kind": "config", "key": "congratsMessage"},
            "default": "Congratulations! You have finished this deck for now.",
        },
    ]
    fields += color("box_bg", tr("box_background", "Box Background"), "#f3f3f3", "#2c2c2c")
    fields += color("box_border", tr("border_color", "Border Color"), "#e0e0e0", "#565656")
    # Unlike the other colours, the Study Now button should always expose its
    # light and dark values.  Its defaults intentionally match, but hiding the
    # second swatch made it impossible to discover that each theme is editable.
    fields += color(
        "study_button", tr("study_button_color", "Study Button Color"),
        "#0077C8", "#0077C8", always_split=True,
    )
    fields += color(
        "options_button", tr("options_button_color", "Options Button Color"),
        "#f5f5f5", "#2a2a2a", always_split=True,
    )
    fields += color(
        "custom_study_button", tr("custom_study_button_color", "Custom Study Button Color"),
        "#f5f5f5", "#2a2a2a", always_split=True,
    )
    fields += color(
        "description_button", tr("description_button_color", "Description Button Color"),
        "#f5f5f5", "#2a2a2a", always_split=True,
    )
    fields += color(
        "reveal_button", tr("reveal_button_color", "Reveal Button Color"),
        "#0077C8", "#0a84ff", always_split=True,
    )
    fields += color("new_bubble", tr("new_count_label", "New Count"), "#1e8cff", "#0077C8")
    fields += color("new_text", tr("new_count_fg_label", "New Count Text"), "#ffffff", "#f7fbff")
    fields += color("learn_bubble", tr("learn_count_label", "Learning Count"), "#ff5757", "#ff453a")
    fields += color("learn_text", tr("learn_count_fg_label", "Learning Count Text"), "#ffffff", "#fff5f5")
    fields += color("review_bubble", tr("review_count_label", "Review Count"), "#19c96b", "#12b765")
    fields += color("review_text", tr("review_count_fg_label", "Review Count Text"), "#ffffff", "#f4fff8")

    return _designer_preview_section(
        "overview_style",
        "overview_style",
        title=tr("overview_style_section", "Overview Style"),
        icon="stats.svg",
        dynamic_keys=[
            "ovstyle_color_box_bg_theme_mode", "ovstyle_color_box_border_theme_mode",
            "ovstyle_color_study_button_theme_mode", "ovstyle_color_new_bubble_theme_mode",
            "ovstyle_color_new_text_theme_mode", "ovstyle_color_learn_bubble_theme_mode",
            "ovstyle_color_learn_text_theme_mode", "ovstyle_color_review_bubble_theme_mode",
            "ovstyle_color_review_text_theme_mode",
        ],
        head_to_deck=True,
        sync_toggle_id="ovstyle_sync_box_effect",
        sync_hidden_fields=[
            "ovstyle_blur", "ovstyle_opacity", "ovstyle_radius", "ovstyle_stroke",
            "ovstyle_color_box_bg", "ovstyle_color_box_border",
        ],
        subsections=[
            {
                "id": "overview_layout",
                "title": tr("overview_layout", "Overview Layout"),
                "fields": ["ovstyle_design", "ovstyle_sync_box_effect"],
            },
            {
                "id": "box_appearance",
                "title": tr("box_appearance", "Box Appearance"),
                "fields": ["ovstyle_blur", "ovstyle_opacity", "ovstyle_radius", "ovstyle_stroke"],
            },
            {
                "id": "study_button",
                "title": tr("study_button", "Study Button"),
                "fields": [
                    "ovstyle_study_button_opacity", "ovstyle_study_button_radius",
                    "ovstyle_study_button_stroke", "ovstyle_color_study_button_stroke",
                    "ovstyle_study_button_dashed", "ovstyle_study_button_animated",
                ],
            },
            {
                "id": "notifications",
                "title": tr("notifications", "Notifications"),
                "fields": ["show_congrats_due_later_notice", "show_overview_due_later_notice"],
            },
            {
                "id": "text",
                "title": tr("text", "Text"),
                "fields": ["overview_study_now_text", "overview_congrats_message"],
            },
            {
                "id": "colors",
                "title": tr("colors", "Colors"),
                "fields": [
                    "ovstyle_color_box_bg", "ovstyle_color_box_border",
                    "ovstyle_color_study_button", "ovstyle_color_options_button",
                    "ovstyle_color_custom_study_button", "ovstyle_color_description_button",
                    "ovstyle_color_reveal_button", "ovstyle_color_new_bubble",
                    "ovstyle_color_new_text", "ovstyle_color_learn_bubble",
                    "ovstyle_color_learn_text", "ovstyle_color_review_bubble",
                    "ovstyle_color_review_text",
                ],
            },
        ],
        fields=fields,
    )


def _reviewer_background_section():
    """Reviewer Background designer (settings/_page_reviewer.py:2059-2088),
    built from the same generic modern-background designer as Main/Overviewer
    Background but with `prefix="reviewer"` and `storage="config"`. Like
    Overviewer Background it carries a fourth "Match Main Menu" mode with its
    own blur/opacity pair (`onigiri_reviewer_bg_main_blur` / `_main_opacity`,
    the only two keys patcher.py:3264-3272 reads in that mode)."""
    return _designer_preview_section(
        "reviewer_background",
        "reviewer_background",
        title=tr("reviewer_bg", "Reviewer Background"),
        icon="paintbrush.svg",
        dynamic_keys=[
            "reviewer_bg_color_theme_mode",
            "reviewer_bg_image_theme_mode",
        ],
        fields=[
            {
                "id": "reviewer_background_mode",
                "type": "choice",
                "head": True,
                "head_label": tr("style", "Style"),
                "label": tr("bg_mode", "Background Mode"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_bg_mode"},
                "default": "color",
                "options": [
                    {"value": "image_color", "label": tr("image", "Image")},
                    {"value": "color", "label": tr("color_only", "Color only")},
                    {"value": "slideshow", "label": tr("slideshow", "Slideshow")},
                    {"value": "main", "label": tr("match_main_menu", "Match Main Menu")},
                ],
            },
            _color_pair_field(
                "reviewer_bg_color",
                tr("color", "Color"),
                "reviewer_bg_color_light",
                "reviewer_bg_color_dark",
                None,
                show_when={"field": "reviewer_background_mode", "values": ["color", "image_color"]},
            ),
            _hidden_config_field("reviewer_bg_color_light", ["onigiri_reviewer_bg_light_color"], "#f2f2f2"),
            _hidden_config_field("reviewer_bg_color_dark", ["onigiri_reviewer_bg_dark_color"], "#2C2C2C"),
            _hidden_config_field("reviewer_bg_color_theme_mode", ["onigiri_reviewer_bg_color_theme_mode"], "separate"),
            _image_field(
                "reviewer_background_image",
                "reviewer_bg",
                tr("select_bg_image", "Background Image"),
                light_field="reviewer_background_image_light",
                dark_field="reviewer_background_image_dark",
                theme_mode_field="reviewer_bg_image_theme_mode",
                empty_label=tr("none_default", "Default"),
                show_when={"field": "reviewer_background_mode", "values": ["image_color"]},
                bind={"kind": "config", "key": "onigiri_reviewer_bg_image"},
            ),
            _hidden_config_field("reviewer_background_image_light", ["onigiri_reviewer_bg_image_light"]),
            _hidden_config_field("reviewer_background_image_dark", ["onigiri_reviewer_bg_image_dark"]),
            _hidden_config_field("reviewer_bg_image_theme_mode", ["onigiri_reviewer_bg_image_theme_mode"], "separate"),
            _hidden_config_field("reviewer_background_image_mode", ["onigiri_reviewer_bg_image_mode"], "separate"),
            _image_list_field(
                "reviewer_slideshow_images",
                "reviewer_bg",
                tr("slideshow_images", "Slideshow Images"),
                show_when={"field": "reviewer_background_mode", "values": ["slideshow"]},
                bind={"kind": "config", "key": "onigiri_reviewer_slideshow_images"},
            ),
            {
                "id": "reviewer_slideshow_interval",
                "type": "duration",
                "label": tr("slideshow_interval", "Slide Interval"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_slideshow_interval"},
                "default": 5,
                "show_when": {"field": "reviewer_background_mode", "values": ["slideshow"]},
            },
            {
                "id": "reviewer_background_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_bg_blur"},
                "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"not": {"field": "reviewer_background_mode", "values": ["main"]}},
            },
            {
                "id": "reviewer_background_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_bg_opacity"},
                "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"not": {"field": "reviewer_background_mode", "values": ["main"]}},
            },
            {
                "id": "reviewer_background_main_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_bg_main_blur"},
                "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"field": "reviewer_background_mode", "values": ["main"]},
            },
            {
                "id": "reviewer_background_main_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "config", "key": "onigiri_reviewer_bg_main_opacity"},
                "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"field": "reviewer_background_mode", "values": ["main"]},
            },
        ],
        hide_deck_when={"field": "reviewer_background_mode", "values": ["main"]},
    )


def _reviewer_bottom_bar_section():
    """Bottom Bar Background and Buttons (settings/_page_reviewer.py:676-1652,
    2504-2641 for the save contract). Ported against what patcher.py's
    generate_reviewer_bottom_bar_background_css *actually reads*
    (patcher.py:4186-4359), not against every control the legacy Qt page
    happens to draw:

    - "Match Main Menu" is the only match-mode with its own independent
      blur/opacity (onigiri_reviewer_bottom_bar_match_main_blur/opacity —
      patcher.py:4325-4326).
    - "Match Overviewer"/"Match Reviewer Background" always inherit that
      source's OWN blur/opacity (patcher.py:4332, 4339); the legacy dialog
      draws an editable "Match Overview" slider pair that patcher.py never
      reads (`onigiri_reviewer_bottom_bar_match_overview_bg_blur/opacity` is
      written but silently ignored) — a latent dead control, not reproduced
      here. Lighter and correct beats pixel-identical-but-broken.

    Pre-Answer Count Colors edit the exact same `overview_style.colors` path
    the Overview Style section (_overview_style_section) already owns — bound
    directly to that config path rather than mirrored through a Qt-only
    "_bottom_bar_pre_count_colors_dirty" style dirty-flag, since the web
    store's single `values` namespace makes two surfaces editing one path
    safe without any sync plumbing."""
    path = lambda *parts: {"kind": "config", "path": list(parts)}

    def color(suffix, config_key, label, default_light, default_dark, show_when=None):
        return [
            _color_pair_field(
                f"bbar_{suffix}", label, f"bbar_{suffix}_light", f"bbar_{suffix}_dark", None,
                **({"show_when": show_when} if show_when else {}),
            ),
            # Dynamic mode writes this companion value from the preview header.
            # It is deliberately persisted independently of the legacy colour
            # keys: the patcher consumes the light/dark colours, while this
            # flag records whether the web UI should present them as linked.
            {"id": f"bbar_{suffix}_theme_mode", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"onigiri_web_bbar_{suffix}_theme_mode"}, "default": "separate"},
            {"id": f"bbar_{suffix}_light", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"{config_key}_light"}, "default": default_light},
            {"id": f"bbar_{suffix}_dark", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"{config_key}_dark"}, "default": default_dark},
        ]

    def overview_color(suffix, key, label, default_light, default_dark):
        return [
            _color_pair_field(f"bbar_{suffix}", label, f"bbar_{suffix}_light", f"bbar_{suffix}_dark", None),
            {"id": f"bbar_{suffix}_theme_mode", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"onigiri_web_bbar_{suffix}_theme_mode"}, "default": "separate"},
            {"id": f"bbar_{suffix}_light", "type": "hidden", "label": "",
             "bind": path("overview_style", "colors", "light", key), "default": default_light},
            {"id": f"bbar_{suffix}_dark", "type": "hidden", "label": "",
             "bind": path("overview_style", "colors", "dark", key), "default": default_dark},
        ]

    CUSTOM_ONLY = {"field": "bbar_bg_mode", "values": ["color", "image_color"]}
    fields = [
        {
            "id": "bbar_bg_mode", "type": "select",
            # Keep configuration controls in the deck below the preview.
            "head": False,
            "label": tr("style", "Style"),
            "control_style": "modern",
            "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_mode"},
            "default": "match_reviewer_bg",
            "options": [
                {"value": "image_color", "label": tr("image", "Image")},
                {"value": "color", "label": tr("color_only", "Color only")},
                {"value": "main", "label": tr("bbar_match_main", "Match Main Menu")},
                {"value": "match_overview_bg", "label": tr("bbar_match_overview", "Match Overviewer")},
                {"value": "match_reviewer_bg", "label": tr("bbar_match_reviewer", "Match Reviewer Background")},
            ],
        },
        _color_pair_field(
            "bbar_bg_color", tr("color", "Color"), "bbar_bg_color_light", "bbar_bg_color_dark", None,
            show_when=CUSTOM_ONLY,
        ),
        {"id": "bbar_bg_color_theme_mode", "type": "hidden", "label": "",
         "bind": {"kind": "config", "key": "onigiri_web_bbar_bg_color_theme_mode"}, "default": "separate"},
        {"id": "bbar_bg_color_light", "type": "hidden", "label": "",
         "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_light_color"}, "default": "#f2f2f2"},
        {"id": "bbar_bg_color_dark", "type": "hidden", "label": "",
         "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_dark_color"}, "default": "#2C2C2C"},
        _image_field(
            "bbar_bg_image", "reviewer_bar_bg", tr("select_bg_image", "Background Image"),
            empty_label=tr("none_default", "Default"),
            show_when={"field": "bbar_bg_mode", "values": ["image_color"]},
            bind={"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_image"},
        ),
        {
            "id": "bbar_bg_blur", "type": "slider", "label": tr("blur_intensity", "Blur Intensity"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_blur"},
            "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
            "show_when": CUSTOM_ONLY,
        },
        {
            "id": "bbar_bg_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_bg_opacity"},
            "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
            "show_when": CUSTOM_ONLY,
        },
        {
            "id": "bbar_match_main_blur", "type": "slider", "label": tr("blur_intensity", "Blur Intensity"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_match_main_blur"},
            "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
            "show_when": {"field": "bbar_bg_mode", "values": ["main"]},
        },
        {
            "id": "bbar_match_main_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_bottom_bar_match_main_opacity"},
            "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
            "show_when": {"field": "bbar_bg_mode", "values": ["main"]},
        },
        {
            "id": "bbar_match_overview_note", "type": "note", "label": "",
            "desc": tr("bbar_inherits_overview", "Blur and opacity are inherited from the Overviewer Background."),
            "show_when": {"field": "bbar_bg_mode", "values": ["match_overview_bg"]},
        },
        {
            "id": "bbar_match_reviewer_note", "type": "note", "label": "",
            "desc": tr("bbar_inherits_reviewer", "Blur and opacity are inherited from the Reviewer Background."),
            "show_when": {"field": "bbar_bg_mode", "values": ["match_reviewer_bg"]},
        },
        {
            "id": "bbar_custom_enabled", "type": "toggle",
            "head": False,
            "label": tr("enable_custom_buttons_label", "Enable custom buttons"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_btn_custom_enabled"}, "default": True,
        },
        {
            "id": "bbar_stattxt_mode", "type": "choice",
            "head": False,
            "label": tr("stats_numbers_label", "Stats Numbers"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_stattxt_mode"}, "default": "hover",
            "options": [
                {"value": "hover", "label": tr("stats_numbers_hover_short", "Hover")},
                {"value": "inverted", "label": tr("stats_numbers_inverted_short", "Inverted")},
                {"value": "fixed", "label": tr("stats_numbers_fixed_short", "Fixed")},
                {"value": "off", "label": tr("stats_numbers_off_short", "Off")},
            ],
        },
        {
            "id": "bbar_timer_position", "type": "choice",
            "head": False,
            "label": tr("timer_position_label", "Timer Position"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_timer_position"}, "default": "right",
            "options": [
                {"value": "left", "label": tr("timer_position_left_short", "Left")},
                {"value": "right", "label": tr("timer_position_right_short", "Right")},
                {"value": "out", "label": tr("timer_position_out_short", "Out")},
                {"value": "off", "label": tr("timer_position_off_short", "Off")},
            ],
        },
        {
            "id": "bbar_btn_radius", "type": "slider", "label": tr("border_radius_label", "Border Radius"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_btn_radius"},
            "default": 12, "min": 0, "max": 100, "step": 1, "suffix": "px",
        },
        {
            "id": "bbar_btn_padding", "type": "slider", "label": tr("button_padding_label", "Button Padding"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_btn_padding"},
            "default": 5, "min": 0, "max": 100, "step": 1, "suffix": "px",
        },
        {
            "id": "bbar_btn_height", "type": "slider", "label": tr("min_height_label", "Min Height"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_btn_height"},
            "default": 40, "min": 0, "max": 200, "step": 1, "suffix": "px",
        },
        {
            "id": "bbar_bar_height", "type": "slider", "label": tr("bar_height_label", "Bar Height"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_bar_height"},
            "default": 60, "min": 20, "max": 300, "step": 1, "suffix": "px",
        },
    ]
    fields += color("timer_bg", "onigiri_reviewer_timer_bg", tr("bbar_timer_bg", "Timer Background"), "#e5e5e5", "#3a3a3a")
    fields += color("timer_text", "onigiri_reviewer_timer_text", tr("bbar_timer_text", "Timer Text"), "#2c2c2c", "#e0e0e0")
    fields += color("interval_text", "onigiri_reviewer_stattxt_color", tr("bbar_interval_text", "Interval Text"), "#666666", "#aaaaaa")
    fields += [
        {
            "id": "bbar_stats_sync", "type": "toggle",
            "head": False,
            "label": tr("sync_stats_bar_bg_label", "Sync with Stats Bar"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_show_answer_bar_bg_sync"}, "default": True,
        },
    ]
    fields += color(
        "stats_bar_bg", "onigiri_reviewer_show_answer_bar_bg", tr("stats_bar_bg_section_title", "Stats Bar Background"),
        "#2c2c2c", "#e0e0e0", show_when={"field": "bbar_stats_sync", "values": [False]},
    )
    fields += color("again_bg", "onigiri_reviewer_btn_again_bg", tr("bbar_again_button", "Again Button"), "#ffb3b3", "#ffcccb")
    fields += color("again_text", "onigiri_reviewer_btn_again_text", tr("bbar_again_text", "Again Text"), "#4d0000", "#4a0000")
    fields += color("hard_bg", "onigiri_reviewer_btn_hard_bg", tr("bbar_hard_button", "Hard Button"), "#ffe0b3", "#ffd699")
    fields += color("hard_text", "onigiri_reviewer_btn_hard_text", tr("bbar_hard_text", "Hard Text"), "#4d2600", "#4d1d00")
    fields += color("good_bg", "onigiri_reviewer_btn_good_bg", tr("bbar_good_button", "Good Button"), "#b3ffb3", "#90ee90")
    fields += color("good_text", "onigiri_reviewer_btn_good_text", tr("bbar_good_text", "Good Text"), "#004d00", "#004000")
    fields += color("easy_bg", "onigiri_reviewer_btn_easy_bg", tr("bbar_easy_button", "Easy Button"), "#b3d9ff", "#add8e6")
    fields += color("easy_text", "onigiri_reviewer_btn_easy_text", tr("bbar_easy_text", "Easy Text"), "#00264d", "#002952")
    fields += color("other_bg", "onigiri_reviewer_other_btn_bg", tr("bbar_other_button", "Other Button"), "#ffffff", "#3a3a3a")
    fields += color("other_text", "onigiri_reviewer_other_btn_text", tr("bbar_other_text", "Other Text"), "#2c2c2c", "#e0e0e0")
    fields += color("other_hover_bg", "onigiri_reviewer_other_btn_hover_bg", tr("bbar_other_hover_bg", "Hover Background"), "#2c2c2c", "#e0e0e0")
    fields += color("other_hover_text", "onigiri_reviewer_other_btn_hover_text", tr("bbar_other_hover_text", "Hover Text"), "#f0f0f0", "#3a3a3a")
    fields += overview_color("pre_new_bubble", "new_bubble", tr("new_count_label", "New Count"), "#1e8cff", "#0077C8")
    fields += overview_color("pre_new_text", "new_text", tr("new_count_fg_label", "New Count Text"), "#ffffff", "#f7fbff")
    fields += overview_color("pre_learn_bubble", "learn_bubble", tr("learn_count_label", "Learning Count"), "#ff5757", "#ff453a")
    fields += overview_color("pre_learn_text", "learn_text", tr("learn_count_fg_label", "Learning Count Text"), "#ffffff", "#fff5f5")
    fields += overview_color("pre_review_bubble", "review_bubble", tr("review_count_label", "Review Count"), "#19c96b", "#12b765")
    fields += overview_color("pre_review_text", "review_text", tr("review_count_fg_label", "Review Count Text"), "#ffffff", "#f4fff8")

    return _designer_preview_section(
        "reviewer_bottom_bar",
        "reviewer_bottom_bar",
        title=tr("bottom_bar_background_and_buttons", "Bottom Bar Background and Buttons"),
        icon="add-card.svg",
        dynamic_keys=[
            "bbar_bg_color_theme_mode", "bbar_timer_bg_theme_mode", "bbar_timer_text_theme_mode",
            "bbar_interval_text_theme_mode", "bbar_stats_bar_bg_theme_mode",
            "bbar_again_bg_theme_mode", "bbar_again_text_theme_mode",
            "bbar_hard_bg_theme_mode", "bbar_hard_text_theme_mode",
            "bbar_good_bg_theme_mode", "bbar_good_text_theme_mode",
            "bbar_easy_bg_theme_mode", "bbar_easy_text_theme_mode",
            "bbar_other_bg_theme_mode", "bbar_other_text_theme_mode",
            "bbar_other_hover_bg_theme_mode", "bbar_other_hover_text_theme_mode",
            "bbar_pre_new_bubble_theme_mode", "bbar_pre_new_text_theme_mode",
            "bbar_pre_learn_bubble_theme_mode", "bbar_pre_learn_text_theme_mode",
            "bbar_pre_review_bubble_theme_mode", "bbar_pre_review_text_theme_mode",
        ],
        head_to_deck=True,
        fields=fields,
    )


def _reviewer_progress_section():
    """The reviewer header's progress gauge (patcher.py's
    `_reviewer_progress_*` family).

    `left` is the scheduler's own new/learning/review counts — the same numbers
    Anki's bottom bar draws — and `done` is either this session's answers or
    today's whole revlog for the deck; the preview says which, because "12/40"
    means two different things under the two scopes.

    Segment colours default to *following* the count bubbles rather than owning
    their own values: the segmented gauge is a re-drawing of the bottom bar's
    counts, so two places to set "what colour is a review card" would be one
    place too many. Switching Segment Colors to Custom breaks that link and
    reveals this section's own three pairs."""
    IS_BAR = {"field": "rprog_style", "values": ["bar", "segments"]}
    IS_RING = {"field": "rprog_style", "values": ["ring"]}
    NOT_TEXT = {"not": {"field": "rprog_style", "values": ["text"]}}

    fields = [
        {
            "id": "rprog_enabled", "type": "toggle",
            # The one control that belongs in the preview header: everything
            # else is meaningless while the gauge is off.
            "head": True,
            "label": tr("progress_enable", "Show progress bar"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_enabled"},
            "default": True,
        },
        {
            "id": "rprog_style", "type": "choice",
            "head": False,
            "label": tr("progress_style", "Style"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_style"},
            "default": "bar",
            "options": [
                {"value": "bar", "label": tr("progress_style_bar", "Bar"),
                 "sub": tr("progress_style_bar_sub", "One filling track")},
                {"value": "segments", "label": tr("progress_style_segments", "Segments"),
                 "sub": tr("progress_style_segments_sub", "Split by card type")},
                {"value": "ring", "label": tr("progress_style_ring", "Ring"),
                 "sub": tr("progress_style_ring_sub", "Compact circle")},
                {"value": "text", "label": tr("progress_style_text", "Text only"),
                 "sub": tr("progress_style_text_sub", "Just the numbers")},
            ],
        },
        {
            "id": "rprog_label", "type": "choice",
            "head": False,
            "label": tr("progress_label", "Label"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_label"},
            "default": "fraction",
            "options": [
                {"value": "fraction", "label": tr("progress_label_fraction", "12/40")},
                {"value": "percent", "label": tr("progress_label_percent", "30%")},
                {"value": "remaining", "label": tr("progress_label_remaining", "28 left")},
                {"value": "done", "label": tr("progress_label_done", "12 done")},
                {"value": "none", "label": tr("progress_label_none", "None")},
            ],
        },
        {
            "id": "rprog_scope", "type": "choice",
            "head": False,
            "label": tr("progress_scope", "Counts from"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_scope"},
            "default": "session",
            "options": [
                {"value": "session", "label": tr("progress_scope_session", "This session"),
                 "sub": tr("progress_scope_session_sub", "Resets on every deck")},
                {"value": "today", "label": tr("progress_scope_today", "Today"),
                 "sub": tr("progress_scope_today_sub", "Includes earlier reviews")},
            ],
        },
        {
            "id": "rprog_position", "type": "choice",
            "head": False,
            "label": tr("progress_position", "Position"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_position"},
            "default": "right",
            "options": [
                {"value": "right", "label": tr("progress_position_right", "Right of buttons")},
                {"value": "left", "label": tr("progress_position_left", "Left of buttons")},
            ],
        },
        {
            "id": "rprog_width", "type": "slider", "label": tr("progress_width", "Bar Width"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_width"},
            "default": 96, "min": 40, "max": 320, "step": 1, "suffix": "px",
            "show_when": IS_BAR,
        },
        {
            "id": "rprog_ring_size", "type": "slider", "label": tr("progress_ring_size", "Ring Size"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_ring_size"},
            "default": 16, "min": 12, "max": 40, "step": 1, "suffix": "px",
            "show_when": IS_RING,
        },
        {
            "id": "rprog_thickness", "type": "slider", "label": tr("progress_thickness", "Thickness"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_thickness"},
            "default": 6, "min": 2, "max": 20, "step": 1, "suffix": "px",
            "show_when": NOT_TEXT,
        },
        {
            "id": "rprog_radius", "type": "slider", "label": tr("progress_radius", "Corner Radius"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_radius"},
            "default": 999, "min": 0, "max": 999, "step": 1, "suffix": "px",
            "show_when": IS_BAR,
        },
        {
            "id": "rprog_chrome", "type": "toggle",
            "head": False,
            "label": tr("progress_chrome", "Button-style background"),
            "desc": tr("progress_chrome_desc", "Wrap the gauge in the same chip the header buttons use."),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_chrome"},
            "default": True,
        },
        {
            "id": "rprog_animate", "type": "toggle",
            "head": False,
            "label": tr("progress_animate", "Animate changes"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_animate"},
            "default": True,
        },
        {
            "id": "rprog_hide_when_done", "type": "toggle",
            "head": False,
            "label": tr("progress_hide_when_done", "Hide when the deck is finished"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_hide_when_done"},
            "default": False,
        },
        {
            "id": "rprog_gradient", "type": "toggle",
            "head": False,
            "label": tr("progress_gradient", "Gradient fill"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_gradient"},
            "default": True,
            "show_when": NOT_TEXT,
        },
    ]

    def color(suffix, config_key, label, default_light, default_dark, show_when=None):
        return [
            _color_pair_field(
                f"rprog_{suffix}", label, f"rprog_{suffix}_light", f"rprog_{suffix}_dark", None,
                **({"show_when": show_when} if show_when else {}),
            ),
            {"id": f"rprog_{suffix}_theme_mode", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"onigiri_web_rprog_{suffix}_theme_mode"}, "default": "separate"},
            {"id": f"rprog_{suffix}_light", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"{config_key}_light"}, "default": default_light},
            {"id": f"rprog_{suffix}_dark", "type": "hidden", "label": "",
             "bind": {"kind": "config", "key": f"{config_key}_dark"}, "default": default_dark},
        ]

    fields += color(
        "fill", "onigiri_reviewer_progress_fill", tr("progress_fill", "Fill"),
        "#19c96b", "#12b765", show_when=NOT_TEXT,
    )
    fields += color(
        "fill_end", "onigiri_reviewer_progress_fill_end", tr("progress_fill_end", "Gradient End"),
        "#5ad6f0", "#4bc4de",
        show_when={"all": [NOT_TEXT, {"field": "rprog_gradient", "values": [True]}]},
    )
    fields += color(
        "track", "onigiri_reviewer_progress_track", tr("progress_track", "Track"),
        "rgba(0, 0, 0, 0.12)", "rgba(255, 255, 255, 0.16)", show_when=NOT_TEXT,
    )
    fields += color(
        "text", "onigiri_reviewer_progress_text", tr("progress_text_color", "Label Text"),
        "#2c2c2c", "#e8e8e8",
    )
    fields += [
        {
            "id": "rprog_segment_source", "type": "choice",
            "head": False,
            "label": tr("progress_segment_source", "Segment Colors"),
            "bind": {"kind": "config", "key": "onigiri_reviewer_progress_segment_source"},
            "default": "counts",
            "options": [
                {"value": "counts", "label": tr("progress_segment_counts", "Follow count bubbles"),
                 "sub": tr("progress_segment_counts_sub", "Same colors as the bottom bar")},
                {"value": "custom", "label": tr("progress_segment_custom", "Custom")},
            ],
            "show_when": {"field": "rprog_style", "values": ["segments"]},
        },
    ]
    SEG_CUSTOM = {"all": [
        {"field": "rprog_style", "values": ["segments"]},
        {"field": "rprog_segment_source", "values": ["custom"]},
    ]}
    fields += color("seg_new", "onigiri_reviewer_progress_seg_new", tr("new_count_label", "New Count"),
                    "#1e8cff", "#0a84ff", show_when=SEG_CUSTOM)
    fields += color("seg_learn", "onigiri_reviewer_progress_seg_learn", tr("learn_count_label", "Learning Count"),
                    "#ff5757", "#ff453a", show_when=SEG_CUSTOM)
    fields += color("seg_review", "onigiri_reviewer_progress_seg_review", tr("review_count_label", "Review Count"),
                    "#19c96b", "#12b765", show_when=SEG_CUSTOM)

    return _designer_preview_section(
        "reviewer_progress",
        "reviewer_progress",
        title=tr("progress_bar_section_title", "Header Progress Bar"),
        icon="stats.svg",
        dynamic_keys=[
            "rprog_fill_theme_mode", "rprog_fill_end_theme_mode", "rprog_track_theme_mode",
            "rprog_text_theme_mode", "rprog_seg_new_theme_mode", "rprog_seg_learn_theme_mode",
            "rprog_seg_review_theme_mode",
        ],
        head_to_deck=True,
        fields=fields,
    )


def _reviewer_page():
    """settings/_page_reviewer.py's transference, split into two sub-pages the
    same way Overviewer is (see _overviewer_page): Background
    (create_reviewer_tab's own Reviewer Background SectionGroup at
    _page_reviewer.py:2059-2088) and Bottom Bar Background and Buttons
    (_reviewer_bottom_bar_section)."""
    return {
        "id": "reviewer",
        "legacy_name": "Reviewer",
        "title": tr("reviewer", "Reviewer"),
        "icon": "add-card.svg",
        "group": "study",
        "description": "",
        "tabbed": True,
        "sections": [
            _reviewer_background_section(),
            _reviewer_bottom_bar_section(),
            _reviewer_progress_section(),
        ],
        "post_save": ["reviewer_progress"],
    }


def _overviewer_page():
    """settings/_page_overviews.py's transference, split into two sub-pages
    matching the legacy page's own two SectionGroups — Background (the
    designer at _page_overviews.py:15-44) and Style (the box/button/count
    colour designer at _page_overviews.py:587-1525) — the same way Main menu
    is split into its own sub-menu tabs (see _mainmenu_page)."""
    return {
        "id": "overviewer",
        "legacy_name": "Overviewer",
        "title": tr("overviewer", "Overviewer"),
        "icon": "stats.svg",
        "group": "study",
        "description": "",
        "tabbed": True,
        "sections": [_overview_background_section(), _overview_style_section()],
    }


def _mainmenu_widget_effect_section():
    """Widget Color and Effect — the shared "glass card" styling for boxed
    widgets app-wide (settings/_page_colors.py:168-410, settings/_infra.py:1378-1756).
    Retention star colours are edited in the Stats Widgets section, alongside
    the card they belong to."""
    return _designer_preview_section(
        "mainmenu_widget_effect",
        "widget_effect",
        title=tr("boxes_color_effect", "Widget Color and Effect"),
        icon="square.svg",
        dynamic_keys=["onigiri_canvas_inset_color_theme_mode"],
        fields=[
            _color_pair_field(
                "widget_box_color",
                tr("color", "Color"),
                "widget_box_color_light",
                "widget_box_color_dark",
                None,
                theme_mode_field="onigiri_canvas_inset_color_theme_mode",
            ),
            _hidden_config_field("widget_box_color_light", ["colors", "light", "--canvas-inset"], "#ffffff"),
            _hidden_config_field("widget_box_color_dark", ["colors", "dark", "--canvas-inset"], "#2c2c2c"),
            _color_pair_field(
                "widget_border_color",
                tr("border_color", "Border Color"),
                "widget_border_color_light",
                "widget_border_color_dark",
                None,
                theme_mode_field="onigiri_canvas_inset_color_theme_mode",
            ),
            _hidden_config_field("widget_border_color_light", ["colors", "light", "--border"], "#e0e0e0"),
            _hidden_config_field("widget_border_color_dark", ["colors", "dark", "--border"], "#424242"),
            _hidden_field("onigiri_canvas_inset_color_theme_mode", "separate"),
            {
                "id": "onigiri_canvas_inset_effect_blur",
                "type": "slider",
                "label": tr("blur", "Blur"),
                # Blur behind a 0%-opacity box or a flat "Color only" main
                # background has nothing to blur, so hide it in either case
                # rather than leave a control that visibly does nothing.
                "show_when": {"not": {"any": [
                    {"field": "onigiri_canvas_inset_effect_opacity", "values": [0]},
                    {"field": "modern_menu_background_mode", "values": ["color"]},
                ]}},
                "bind": {"kind": "col", "key": "onigiri_canvas_inset_effect_blur"},
                "default": 0,
                "min": 0,
                "max": 100,
                "step": 1,
                "suffix": "%",
            },
            {
                "id": "onigiri_canvas_inset_effect_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "col", "key": "onigiri_canvas_inset_effect_opacity"},
                "default": 100,
                "min": 0,
                "max": 100,
                "step": 1,
                "suffix": "%",
            },
            {
                "id": "onigiri_canvas_inset_border_radius",
                "type": "slider",
                "label": tr("border_radius", "Border Radius"),
                "bind": {"kind": "col", "key": "onigiri_canvas_inset_border_radius"},
                "default": 20,
                "min": 0,
                "max": 60,
                "step": 1,
                "suffix": "px",
            },
            {
                "id": "onigiri_canvas_inset_border_width",
                "type": "slider",
                "label": tr("border_width", "Border Width"),
                "bind": {"kind": "col", "key": "onigiri_canvas_inset_border_width"},
                "default": 1,
                "min": 0,
                "max": 10,
                "step": 1,
                "suffix": "px",
            },
        ],
    )


# Which design a Stats Widgets setting belongs to. Shared by the field list
# and by the conditions on the per-metric colours below it.
EXPRESSIVE_ONLY = {"field": "swidget_design", "values": ["expressive"]}
MINIMAL_ONLY = {"field": "swidget_design", "values": ["minimal"]}


def _mainmenu_stats_widgets_section():
    """Today's Stats cards (settings/_page_stats_widgets.py:201-1241). Storage
    root is `stats_widgets_style` (defaults: config.py:415-464). Retention star
    colors live here so they can be edited in either card design."""
    path = lambda *parts: {"kind": "config", "path": ["stats_widgets_style", *parts]}

    def color(key, label, default_light, default_dark, show_when=None):
        return [
            _color_pair_field(
                f"swidget_color_{key}", label,
                f"swidget_color_{key}_light", f"swidget_color_{key}_dark", None,
                **({"show_when": show_when} if show_when else {}),
            ),
            {"id": f"swidget_color_{key}_light", "type": "hidden", "label": "",
             "bind": path("colors", "light", key), "default": default_light},
            {"id": f"swidget_color_{key}_dark", "type": "hidden", "label": "",
             "bind": path("colors", "dark", key), "default": default_dark},
        ]

    # The deck's compact Font+Value Size row drops the "Font" caption and
    # shows only this chip, so its label has to name a font on its own — the
    # generic "Sync with theme" reads as a picker with nothing picked. This
    # value still just means "sync", but the button now says what it's
    # actually rendering with by default.
    font_options = [{"value": "sync", "label": tr("system", "System")}] + _font_options()

    fields = [
        {
            "id": "swidget_design", "type": "choice", "label": tr("design", "Design"),
            "head": True, "head_label": tr("style", "Style"),
            "bind": path("design"), "default": "minimal",
            "options": [
                {"value": "minimal", "label": tr("minimal", "Minimal")},
                {"value": "expressive", "label": tr("expressive", "Expressive")},
            ],
        },
        {
            # Two shapes, so the control shows the shapes themselves instead of
            # the words for them (icon-only segment, label as its tooltip). It
            # sits with the other switches below the stage rather than in the
            # header: only one of the two designs draws a chart at all.
            "id": "swidget_chart_shape", "type": "choice", "label": tr("chart", "Chart"),
            "show_when": EXPRESSIVE_ONLY,
            "bind": path("chart_shape"), "default": "sharp",
            "options": [
                {"value": "smooth", "label": tr("curved", "Curved"), "icon": "circle.svg"},
                {"value": "sharp", "label": tr("angular", "Angular"), "icon": "square.svg"},
            ],
        },
        {
            "id": "swidget_font", "type": "font", "label": tr("font", "Font"),
            "bind": path("font"), "default": "sync", "options": font_options,
        },
        {
            # 100% is the widget's own full size, so it is the slider's own
            # ceiling too — matches patcher.py's clamp on the same key. Sits
            # right under Font, its own full-width row, not fused into one.
            "id": "swidget_value_scale", "type": "slider", "label": tr("value_size", "Value Size"),
            "bind": path("value_scale"), "default": 100, "min": 60, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "swidget_sync_box_effect", "type": "toggle",
            "head": True, "head_label": tr("sync_with_widgets", "Sync with widgets"),
            "label": tr("sync_with_box_effect", "Sync with Widget Color and Effect"),
            "bind": path("sync_box_effect"), "default": True,
        },
        {
            # Dynamic mode governs which of this card's OWN light/dark colours
            # apply — moot once Sync with Widgets hands that over to Widget
            # Color and Effect's own dynamic mode instead.
            "id": "swidget_dynamic", "type": "toggle",
            "head": True, "head_label": tr("dynamic_mode", "Dynamic mode"),
            "show_when": {"field": "swidget_sync_box_effect", "values": [False]},
            "label": tr("dynamic_mode", "Dynamic mode"),
            "bind": path("dynamic"), "default": True,
        },
        # Icons, units and the trend line exist only in the Expressive card;
        # the retention star row is available in both designs.
        {
            "id": "swidget_show_icons", "type": "toggle", "label": tr("show_icons", "Show icons"),
            "show_when": EXPRESSIVE_ONLY,
            "bind": path("show_icons"), "default": True,
        },
        {
            "id": "swidget_show_units", "type": "toggle", "label": tr("show_units", "Show units"),
            "show_when": EXPRESSIVE_ONLY,
            "bind": path("show_units"), "default": True,
        },
        {
            "id": "swidget_show_sparkline", "type": "toggle", "label": tr("show_7day_trend", "Show 7-day trend"),
            "show_when": EXPRESSIVE_ONLY,
            "bind": path("show_sparkline"), "default": True,
        },
        {
            "id": "swidget_show_wash", "type": "toggle", "label": tr("show_background_wash", "Background wash"),
            "show_when": EXPRESSIVE_ONLY,
            "bind": path("show_wash"), "default": True,
        },
        {
            "id": "swidget_show_retention_stars", "type": "toggle",
            "label": tr("show_retention_stars", "Show retention stars"),
            "bind": path("show_retention_stars"), "default": True,
        },
        {
            "id": "swidget_blur", "type": "slider", "label": tr("blur", "Blur"),
            "bind": path("blur"), "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "swidget_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
            "bind": path("opacity"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "swidget_radius", "type": "slider", "label": tr("border_radius", "Border Radius"),
            "bind": path("radius"), "default": 20, "min": 0, "max": 60, "step": 1, "suffix": "px",
        },
        {
            "id": "swidget_stroke", "type": "slider", "label": tr("border_width", "Border Width"),
            "bind": path("stroke"), "default": 1, "min": 0, "max": 10, "step": 1, "suffix": "px",
        },
    ]
    fields += color("box_bg", tr("box_background", "Box Background"), "#ffffff", "#2c2c2c")
    fields += color("box_border", tr("border_color", "Border Color"), "#e0e0e0", "#424242")
    fields += color("label", tr("label_color", "Label Color"), "#757575", "#9c9c9c")
    # Expressive paints each value with that metric's own accent, so this colour
    # is not what is on screen there — it belongs to Minimal only.
    fields += color("value", tr("value_color", "Value Color"), "#212121", "#f0f0f0", MINIMAL_ONLY)
    # Only the Expressive design paints per-metric accents. Retention star
    # colours are separate because the stars should remain yellow by default
    # even though the Retention metric keeps its own green accent.
    fields += color("studied", tr("studied_color", "Studied Color"), "#5eaadf", "#6bb6ec", EXPRESSIVE_ONLY)
    fields += color("time", tr("time_color", "Time Color"), "#8b7bd8", "#a294ea", EXPRESSIVE_ONLY)
    fields += color("pace", tr("pace_color", "Pace Color"), "#f5a05a", "#f7ad6b", EXPRESSIVE_ONLY)
    fields += color("retention", tr("retention_color", "Retention Color"), "#26a641", "#35b850", EXPRESSIVE_ONLY)
    fields += color("retention_star", tr("retention_star_color", "Retention Star Color"), "#FFD700", "#FFD700")
    fields += color("retention_star_empty", tr("retention_empty_star_color", "Empty Retention Star Color"), "#e0e0e0", "#4a4a4a")
    # The Retention card's star glyph is a menu-wide icon (the same key the
    # icon CSS generator masks .star with), not part of stats_widgets_style —
    # declared here so the preview draws the user's own shape.
    fields += [_hidden_field("modern_menu_icon_retention_star")]
    fields += [
        {
            "id": f"swidget_icon_{key}", "type": "icon", "label": label,
            "show_when": {"all": [EXPRESSIVE_ONLY, {"field": "swidget_show_icons", "values": [True]}]},
            "bind": path("icons", key), "default": default,
        }
        for key, label, default in (
            ("studied", tr("studied_icon", "Studied Icon"), "system:check.svg"),
            ("time", tr("time_icon", "Time Icon"), "system:pomodoro.svg"),
            ("pace", tr("pace_icon", "Pace Icon"), "system:bolt.svg"),
            ("retention", tr("retention_icon", "Retention Icon"), "system:star.svg"),
        )
    ]

    return _designer_preview_section(
        "mainmenu_stats_widgets",
        "stats_widgets",
        title=tr("stats_widgets_section", "Stats Widgets"),
        icon="stats.svg",
        # Each metric's accent is shown under its icon tile as well as inside the
        # icon's popover: on this card the four accents are the main thing being
        # tuned, and having to open a popover per colour to compare them made
        # comparing them the one thing the card could not do.
        icon_colors_inline=True,
        sync_toggle_id="swidget_sync_box_effect",
        sync_hidden_fields=[
            "swidget_blur", "swidget_opacity", "swidget_radius", "swidget_stroke",
            "swidget_color_box_bg", "swidget_color_box_border",
        ],
        fields=fields,
    )


DECK_STATS_CATEGORY_KEYS = (
    "new", "learning", "relearning", "young", "mature", "unseen", "suspended", "buried",
)


def _mainmenu_deck_stats_section():
    """Deck Stats widget (learner_stats_widget.py's "grouped" view; CSS vars
    from patcher.py's _deck_stats_rules). Same sync/dynamic/effect-slider
    shape as Stats Widgets, plus the two group accents (In Progress/Mastered)
    and the Total tile's colour, which the real widget also draws with but
    this section did not previously expose."""
    path = lambda *parts: {"kind": "config", "path": ["deck_stats_style", *parts]}
    light_defaults = {
        "box_bg": "#ffffff", "box_border": "#e0e0e0", "new": "#5eaadf", "learning": "#f5a05a",
        "relearning": "#f4685f", "young": "#7cc87c", "mature": "#26a641", "unseen": "#b0b4b9",
        "suspended": "#ffdc41", "buried": "#9e9e9e", "in_progress": "#5eaadf", "mastered": "#26a641",
        "total": "#6f7177",
    }
    dark_defaults = {
        "box_bg": "#2c2c2c", "box_border": "#424242", "new": "#6bb6ec", "learning": "#f7ad6b",
        "relearning": "#f8776e", "young": "#8ad48a", "mature": "#35b850", "unseen": "#7a7f85",
        "suspended": "#ffe066", "buried": "#a8a8a8", "in_progress": "#6bb6ec", "mastered": "#35b850",
        "total": "#c4c4c4",
    }

    def color(key, label, show_when=None):
        return [
            _color_pair_field(
                f"dstats_color_{key}", label,
                f"dstats_color_{key}_light", f"dstats_color_{key}_dark", None,
                **({"show_when": show_when} if show_when else {}),
            ),
            {"id": f"dstats_color_{key}_light", "type": "hidden", "label": "",
             "bind": path("colors", "light", key), "default": light_defaults[key]},
            {"id": f"dstats_color_{key}_dark", "type": "hidden", "label": "",
             "bind": path("colors", "dark", key), "default": dark_defaults[key]},
        ]

    category_labels = {
        "new": tr("new", "New"), "learning": tr("learning", "Learning"),
        "relearning": tr("relearning", "Relearning"), "young": tr("young", "Young"),
        "mature": tr("mature", "Mature"), "unseen": tr("unseen", "Unseen"),
        "suspended": tr("suspended", "Suspended"), "buried": tr("buried", "Buried"),
    }

    # The two group accents (bar segments + group titles) only appear in the
    # Minimal chart's two-tone grouping — Full breaks every category out on
    # its own, with nothing left to call "In Progress" or "Mastered".
    minimal_only = {"field": "dstats_chart_type", "values": ["minimal"]}

    fields = [
        {
            "id": "dstats_chart_type", "type": "choice", "label": tr("chart_type", "Chart Type"),
            "head": True, "head_label": tr("chart", "Chart"),
            "bind": path("chart_type"), "default": "minimal",
            "options": [
                {"value": "minimal", "label": tr("minimal_chart", "Minimal Chart")},
                {"value": "full", "label": tr("full_chart", "Full Chart")},
            ],
        },
        {
            "id": "dstats_sync_box_effect", "type": "toggle",
            "head": True, "head_label": tr("sync_with_widgets", "Sync with widgets"),
            "label": tr("sync_with_box_effect", "Sync with Widget Color and Effect"),
            "bind": path("sync_box_effect"), "default": True,
        },
        {
            # Moot once Sync hands the card's colours to Widget Color and
            # Effect's own dynamic mode instead — see swidget_dynamic's twin
            # of this note in _mainmenu_stats_widgets_section.
            "id": "dstats_dynamic", "type": "toggle",
            "head": True, "head_label": tr("dynamic_mode", "Dynamic mode"),
            "show_when": {"field": "dstats_sync_box_effect", "values": [False]},
            "label": tr("dynamic_mode", "Dynamic mode"),
            "bind": path("dynamic"), "default": True,
        },
        {
            "id": "dstats_blur", "type": "slider", "label": tr("blur", "Blur"),
            "bind": path("blur"), "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "dstats_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
            "bind": path("opacity"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
        },
        {
            "id": "dstats_radius", "type": "slider", "label": tr("border_radius", "Border Radius"),
            "bind": path("radius"), "default": 20, "min": 0, "max": 60, "step": 1, "suffix": "px",
        },
        {
            "id": "dstats_stroke", "type": "slider", "label": tr("border_width", "Border Width"),
            "bind": path("stroke"), "default": 1, "min": 0, "max": 10, "step": 1, "suffix": "px",
        },
    ]
    fields += color("box_bg", tr("box_background", "Box Background"))
    fields += color("box_border", tr("border_color", "Border Color"))
    fields += color("in_progress", tr("group_in_progress_color", "In Progress Color"), minimal_only)
    fields += color("mastered", tr("group_mastered_color", "Mastered Color"), minimal_only)
    fields += color("total", tr("total_color", "Total Color"))
    for key in DECK_STATS_CATEGORY_KEYS:
        fields += color(key, category_labels[key])

    return _designer_preview_section(
        "mainmenu_deck_stats",
        "deck_stats",
        title=tr("deck_stats_section", "Deck Stats"),
        icon="deck.svg",
        sync_toggle_id="dstats_sync_box_effect",
        sync_hidden_fields=[
            "dstats_blur", "dstats_opacity", "dstats_radius", "dstats_stroke",
            "dstats_color_box_bg", "dstats_color_box_border",
        ],
        fields=fields,
    )


def _mainmenu_heatmap_section():
    """Activity heatmap (settings/_page_mainmenu.py:234-1432; defaults:
    config.py:193-202, 568-569/616-617). Sync with widgets on (default)
    follows Widget Color and Effect's glass-card chrome, same as legacy;
    off gives the card its own blur/opacity/radius/stroke/box colours,
    same sync/dynamic shape as Deck Stats. Dynamic Mode governs the two
    heatmap cell colours (light/dark split vs one shared value)."""
    path = lambda *parts: {"kind": "config", "path": ["heatmap_style", *parts]}
    box_defaults = {"light": "#ffffff", "dark": "#2c2c2c"}
    border_defaults = {"light": "#e0e0e0", "dark": "#424242"}
    return _designer_preview_section(
        "mainmenu_heatmap",
        "heatmap",
        title=tr("heatmap_section", "Heatmap"),
        icon="calendar-check.svg",
        sync_toggle_id="heatmap_sync_box_effect",
        sync_hidden_fields=[
            "heatmap_blur", "heatmap_opacity", "heatmap_radius", "heatmap_stroke",
            "heatmap_color_box_bg", "heatmap_color_box_border",
        ],
        fields=[
            {
                "id": "heatmapWeekStart", "type": "choice",
                "head": True, "head_label": tr("start", "Start"),
                "label": tr("week_start_label", "Week Starts On"),
                "bind": {"kind": "config", "key": "heatmapWeekStart"}, "default": "monday",
                "options": [
                    {"value": "monday", "label": tr("week_start_monday", "Monday"), "short": tr("week_start_monday_short", "M")},
                    {"value": "sunday", "label": tr("week_start_sunday", "Sunday"), "short": tr("week_start_sunday_short", "S")},
                ],
            },
            {
                "id": "heatmapDefaultView", "type": "choice",
                "head": True, "head_label": tr("view", "View"),
                "label": tr("default_view", "Default View"),
                "bind": {"kind": "config", "key": "heatmapDefaultView"}, "default": "year",
                "options": [
                    {"value": "year", "label": tr("view_year", "Year"), "short": tr("view_year_short", "Y")},
                    {"value": "month", "label": tr("view_month", "Month"), "short": tr("view_month_short", "M")},
                    {"value": "week", "label": tr("view_week", "Week"), "short": tr("view_week_short", "W")},
                ],
            },
            {
                "id": "heatmap_sync_box_effect", "type": "toggle",
                "head": True, "head_label": tr("sync_with_widgets", "Sync with widgets"),
                "label": tr("sync_with_box_effect", "Sync with Widget Color and Effect"),
                "bind": path("sync_box_effect"), "default": True,
            },
            {
                "id": "heatmap_dynamic", "type": "toggle",
                "head": True, "head_label": tr("dynamic_mode", "Dynamic mode"),
                "show_when": {"field": "heatmap_sync_box_effect", "values": [False]},
                "label": tr("dynamic_mode", "Dynamic mode"),
                "bind": path("dynamic"), "default": True,
            },
            {
                "id": "heatmap_blur", "type": "slider", "label": tr("blur", "Blur"),
                "bind": path("blur"), "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
            },
            {
                "id": "heatmap_opacity", "type": "slider", "label": tr("opacity", "Opacity"),
                "bind": path("opacity"), "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
            },
            {
                "id": "heatmap_radius", "type": "slider", "label": tr("border_radius", "Border Radius"),
                "bind": path("radius"), "default": 15, "min": 0, "max": 60, "step": 1, "suffix": "px",
            },
            {
                "id": "heatmap_stroke", "type": "slider", "label": tr("border_width", "Border Width"),
                "bind": path("stroke"), "default": 1, "min": 0, "max": 10, "step": 1, "suffix": "px",
            },
            {
                "id": "heatmapShowStreak", "type": "toggle", "label": tr("show_streak_counter", "Show streak counter"),
                "bind": {"kind": "config", "key": "heatmapShowStreak"}, "default": True,
            },
            {
                "id": "heatmapShowMonths", "type": "toggle", "label": tr("show_month_labels", "Show month labels"),
                "bind": {"kind": "config", "key": "heatmapShowMonths"}, "default": True,
            },
            {
                "id": "heatmapShowWeekdays", "type": "toggle", "label": tr("show_weekday_labels", "Show weekday labels"),
                "bind": {"kind": "config", "key": "heatmapShowWeekdays"}, "default": True,
            },
            {
                "id": "heatmapShowWeekHeader", "type": "toggle", "label": tr("show_day_labels", "Show day labels"),
                "bind": {"kind": "config", "key": "heatmapShowWeekHeader"}, "default": True,
            },
            {
                "id": "heatmapShape", "type": "icon", "label": tr("heatmap_shape_icon", "Heatmap Shape"),
                "bind": {"kind": "config", "key": "heatmapShape"}, "default": "square.svg",
            },
            {
                "id": "heatmapStreakIcon", "type": "icon", "label": tr("heatmap_streak_icon", "Streak Icon"),
                "bind": {"kind": "config", "key": "heatmapStreakIcon"}, "default": "system:fire.svg",
            },
            {
                "id": "heatmapStreakIconColor", "type": "color",
                "label": tr("heatmap_streak_icon_color", "Streak Icon Color"),
                "bind": {"kind": "config", "key": "heatmapStreakIconColor"}, "default": "#ff6b35",
            },
            {
                "id": "heatmapStreakIconZeroColor", "type": "color",
                "label": tr("heatmap_streak_icon_zero_color", "Streak Icon Color (0 days)"),
                "bind": {"kind": "config", "key": "heatmapStreakIconZeroColor"}, "default": "#8f8f8f",
            },
            _color_pair_field(
                # dynamic_field is a virtual, unbound flag (settings.js
                # stashes it into `values` right before this pair renders) —
                # neither Dynamic Mode nor Sync with Widgets is a single
                # plain boolean field this pair could bind to directly, since
                # which one applies depends on the sync toggle itself.
                "heatmap_color", tr("heatmap_shape_color", "Color"),
                "heatmap_color_light", "heatmap_color_dark", "heatmap_color_dynamic_virtual",
            ),
            _hidden_config_field("heatmap_color_light", ["colors", "light", "--heatmap-color"], "#0077C8"),
            _hidden_config_field("heatmap_color_dark", ["colors", "dark", "--heatmap-color"], "#0077C8"),
            _color_pair_field(
                "heatmap_color_zero", tr("heatmap_shape_zero_color", "Color (0 reviews)"),
                "heatmap_color_zero_light", "heatmap_color_zero_dark", "heatmap_color_dynamic_virtual",
            ),
            _hidden_config_field("heatmap_color_zero_light", ["colors", "light", "--heatmap-color-zero"], "#f0f0f0"),
            _hidden_config_field("heatmap_color_zero_dark", ["colors", "dark", "--heatmap-color-zero"], "#3a3a3a"),
            _color_pair_field(
                "heatmap_color_box_bg", tr("box_background", "Box Background"),
                "heatmap_color_box_bg_light", "heatmap_color_box_bg_dark", None,
            ),
            {"id": "heatmap_color_box_bg_light", "type": "hidden", "label": "",
             "bind": path("colors", "light", "box_bg"), "default": box_defaults["light"]},
            {"id": "heatmap_color_box_bg_dark", "type": "hidden", "label": "",
             "bind": path("colors", "dark", "box_bg"), "default": box_defaults["dark"]},
            _color_pair_field(
                "heatmap_color_box_border", tr("border_color", "Border Color"),
                "heatmap_color_box_border_light", "heatmap_color_box_border_dark", None,
            ),
            {"id": "heatmap_color_box_border_light", "type": "hidden", "label": "",
             "bind": path("colors", "light", "box_border"), "default": border_defaults["light"]},
            {"id": "heatmap_color_box_border_dark", "type": "hidden", "label": "",
             "bind": path("colors", "dark", "box_border"), "default": border_defaults["dark"]},
        ],
    )


def _mainmenu_organize_section():
    """Organize: the drag-and-drop widget grid editor
    (settings/_widget_grid_v2.py + _widget_grid_core.py). Layout state is 4
    whole-object config fields the `widget_grid` section (web/settings.js)
    reads/writes directly — there's no per-field control for grid contents,
    only for the global column/row/alignment/size settings below it.

    The two Stats Title fields ride along here because the title *is* one of the
    grid's widgets (`stats_title`): the legacy editor put them behind a
    right-click "Edit Title" dialog on that tile
    (settings/_widget_grid_v2.py:993), which is a place nobody finds. They are
    ordinary visible fields, rendered as a row under the canvas."""
    return {
        "id": "mainmenu_organize",
        "title": tr("organize_section", "Organize"),
        "icon": "organise.svg",
        "layout": "widget_grid",
        "fields": [
            {
                # Saved verbatim, exactly as the legacy dialog did: the word cap
                # belongs to the editor, and clamping again here would silently
                # truncate a longer title carried over from before the cap
                # (settings/_page_mainmenu.py:2149-2153).
                "id": "modern_menu_statsTitle",
                "type": "text",
                "label": tr("custom_stats_title", "Stats Title"),
                "bind": {"kind": "col", "key": "modern_menu_statsTitle"},
                "default": "",
            },
            {
                # "sync" (STATS_TITLE_SYNC_KEY) means "whatever the Small Title
                # font role is", which is what patcher.py:4962 falls back to.
                "id": "modern_menu_statsTitleFont",
                "type": "font",
                "label": tr("font", "Font"),
                "bind": {"kind": "col", "key": "modern_menu_statsTitleFont"},
                "default": "sync",
                "options": [{"value": "sync", "label": tr("sync_with_theme", "Sync with theme")}] + _font_options(),
            },
            {
                "id": "onigiriWidgetLayout", "type": "hidden", "label": "",
                "bind": {"kind": "config", "key": "onigiriWidgetLayout"},
                "default": {"grid": {}, "archive": {}, "column_count": 4, "grid_width": 260,
                            "grid_alignment": "center", "widget_height": 180},
            },
            {
                "id": "externalWidgetLayout", "type": "hidden", "label": "",
                "bind": {"kind": "config", "key": "externalWidgetLayout"},
                "default": {"grid": {}, "archive": {}},
            },
            {
                "id": "externalWidgetIdentity", "type": "hidden", "label": "",
                "bind": {"kind": "config", "key": "externalWidgetIdentity"},
                "default": {},
            },
            {
                "id": "unifiedGridRows", "type": "hidden", "label": "",
                "bind": {"kind": "config", "key": "unifiedGridRows"},
                "default": 6,
            },
        ],
    }


def _theme_color_pair(field_id, label, token, light_default, dark_default,
                      theme_mode_field=None, **extra):
    """One row for `colors.light[token]` + `colors.dark[token]`.

    The two real keys stay as `hidden` fields exactly like `_color_pair_field`'s
    docstring describes, so every existing reader keeps finding them where it
    always did. Without an explicit `theme_mode_field` the pair gets its own
    registered one (default "separate", i.e. both slots always visible) — a
    plain page has no grouped Dynamic-mode switch to drive a shared key, and an
    unregistered theme-mode field would fail to persist when a slot is split."""
    mode_field = theme_mode_field or f"{field_id}_theme_mode"
    fields = [
        _color_pair_field(
            field_id, label, f"{field_id}_light", f"{field_id}_dark", None,
            theme_mode_field=mode_field, **extra,
        ),
        _hidden_config_field(f"{field_id}_light", ["colors", "light", token], light_default),
        _hidden_config_field(f"{field_id}_dark", ["colors", "dark", token], dark_default),
    ]
    if theme_mode_field is None:
        fields.append(_hidden_config_field(mode_field, [mode_field], "separate"))
    return fields


def _single_color_slot(field_id, label, bind, default, **extra):
    """A colour that is one value for both themes, rendered as the same slot the
    light/dark pairs use instead of the smaller `color` chip.

    Declaring no light/dark companions is what marks it single —
    `renderColorPair` then reads and writes this field's own key (settings.js's
    `single` branch). Used for the marker colours and the heatmap streak icon
    colours, which sat on the Gallery page looking unlike every colour beside
    them."""
    field = {
        "id": field_id,
        "type": "color_pair",
        "label": label,
        "bind": bind,
        "default": default,
    }
    field.update(extra)
    return field


def _key_color_pair(field_id, label, light_key, dark_key, light_default, dark_default,
                    theme_mode_field=None, **extra):
    """Like `_theme_color_pair`, but for a setting stored as two flat config
    keys (`onigiri_reviewer_btn_again_bg_light` / `…_dark`) rather than as one
    token under `colors`."""
    mode_field = theme_mode_field or f"{field_id}_theme_mode"
    fields = [
        _color_pair_field(
            field_id, label, f"{field_id}_light", f"{field_id}_dark", None,
            theme_mode_field=mode_field, **extra,
        ),
        _hidden_config_field(f"{field_id}_light", [light_key], light_default),
        _hidden_config_field(f"{field_id}_dark", [dark_key], dark_default),
    ]
    if theme_mode_field is None:
        fields.append(_hidden_config_field(mode_field, [mode_field], "separate"))
    return fields


# ── Sidebar ───────────────────────────────────────────────────────────────────
#
# Ported from settings/_page_sidebar.py (+ the sidebar halves of _infra.py and
# _page_backgrounds.py), which between them ran to ~2,600 lines of Qt builders
# for what is four groups of settings: the sidebar frame's own background, the
# action buttons, the deck list, and the four favourite markers.

# The action buttons that sit on the sidebar, in the order the legacy reorder
# list offered them (settings/_legacy.py's ACTION_BUTTON_ORDER_IDS).
# "profile" is deliberately absent: it lives in `sidebarButtonLayout` but is not
# an action button, so the order editor carries it through untouched.
SIDEBAR_ACTION_BUTTONS = (
    ("add", "add_card", "Add", "add-card.svg"),
    ("browse", "browse", "Browse", "browse.svg"),
    ("stats", "stats", "Stats", "stats.svg"),
    ("sync", "sync", "Sync", "sync.svg"),
    ("settings", "settings", "Settings", "settings.svg"),
    ("gamification", "gamification", "Gamification", "gamepad.svg"),
    ("more", "more", "More", "more.svg"),
)

# Entries of the "More" menu (settings/_legacy.py's ACTION_BUTTON_MORE_CHILDREN).
# Their icons are editable, but they are NOT part of the sidebar's own order:
# they live inside More, so offering to reorder or archive them there would be
# offering something the sidebar cannot honour.
SIDEBAR_MORE_BUTTONS = (
    ("get_shared", "get_shared", "Get Shared", "get_shared.svg"),
    ("create_deck", "create_deck", "Create Deck", "add-deck.svg"),
    ("import_file", "import_file", "Import File", "import_file.svg"),
)

# Deck-list glyphs the legacy page let the user swap (its
# `deck_icons_to_configure` map), with the default each one falls back to
# (constants.ICON_DEFAULTS).
SIDEBAR_DECK_ICONS = (
    ("folder", "folder_icon", "Folder", "folder.svg"),
    ("deck", "deck_icon", "Deck", "deck.svg"),
    ("subdeck", "subdeck_icon", "Subdeck", "subdeck.svg"),
    ("filtered_deck", "filtered_deck_icon", "Filtered Deck", "filtered-deck.svg"),
    ("options", "options_icon", "Options", "options.svg"),
    ("collapse_closed", "collapse_icon", "Collapse", "right.svg"),
    ("collapse_open", "expand_icon", "Expand", "down.svg"),
)

MARKER_DEFINITIONS = (
    ("red", "#FF4B4B"),
    ("blue", "#4488FF"),
    ("green", "#44BB66"),
    ("yellow", "#FFB800"),
)


def _icon_field(field_id, label, default, **extra):
    """An icon slot backed by the icon popover. `default` is the fallback glyph
    written as a "system:<file>" reference, which every reader already resolves
    (patcher.py:4619, onigiri_renderer.py:1102)."""
    field = {
        "id": field_id,
        "type": "icon",
        "label": label,
        "bind": {"kind": "col", "key": field_id},
        "default": default,
    }
    field.update(extra)
    return field


# The sidebar card is really two cards in one: a custom background (its own
# colour/picture/effect) or the main menu's background seen through a tint. Every
# row belongs to exactly one of them, so both conditions are named once here
# rather than repeated inline a dozen times.
_SIDEBAR_CUSTOM = {"field": "modern_menu_sidebar_bg_mode", "values": ["custom"]}
_SIDEBAR_MAIN = {"field": "modern_menu_sidebar_bg_mode", "values": ["main"]}


def _sidebar_background_section():
    """The sidebar frame itself: fill, picture, effect and geometry. Config keys
    match the legacy save path exactly (settings/_page_sidebar.py:1654-1721).

    Background Source picks between the sidebar's own custom background and the
    main menu's, the latter drawn through either a glassmorphism blur or a
    tinted overlay (patcher.py:3017-3050). "Sync with Widget Color and Effect"
    is the switch that hands the custom fill/effect over to the shared widget
    styling, and it collapses the rows it takes over instead of leaving them
    greyed out."""
    return _designer_preview_section(
        "sidebar_background",
        "sidebar_background",
        title=tr("sidebar_background", "Sidebar Background"),
        icon="paintbrush.svg",
        dynamic_keys=[
            "modern_menu_sidebar_bg_color_theme_mode",
            "modern_menu_sidebar_bg_image_theme_mode",
        ],
        sync_toggle_id="modern_menu_sidebar_sync_box_effect",
        sync_hidden_fields=[
            "modern_menu_sidebar_bg_color",
            "modern_menu_sidebar_bg_blur",
            "modern_menu_sidebar_bg_opacity",
            "modern_menu_sidebar_radius",
            "modern_menu_sidebar_stroke",
        ],
        stage_side=True,
        # Order matters here: `stage_side` renders one column in schema order, so
        # this list *is* the layout — the four things that decide what the
        # sidebar is, then what fills it, then the effect and geometry sliders.
        fields=[
            {
                "id": "modern_menu_sidebar_position",
                "type": "choice",
                "label": tr("sidebar_position", "Sidebar position"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_position"},
                "default": "left",
                "options": [
                    {"value": "left", "label": tr("sidebar_position_left_short", "Left")},
                    {"value": "center", "label": tr("sidebar_position_center_short", "Center")},
                    {"value": "right", "label": tr("sidebar_position_right_short", "Right")},
                ],
            },
            {
                # `modern_menu_sidebar_bg_mode` and `modern_menu_sidebar_bg_type`
                # are two different keys in the collection config: the first
                # decides *where* the sidebar's fill comes from (its own custom
                # background, or the main menu's, tinted), the second decides
                # what that custom background is. The legacy page expressed the
                # first as a "Sync with Main Background" toggle
                # (settings/_page_sidebar.py:1719-1721); a two-value choice says
                # the same thing without hiding half the card behind a switch.
                "id": "modern_menu_sidebar_bg_mode",
                "type": "choice",
                "label": tr("sidebar_bg_source", "Background Source"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_bg_mode"},
                "default": "custom",
                "options": [
                    {"value": "custom", "label": tr("custom", "Custom")},
                    {"value": "main", "label": tr("match_main_menu", "Match Main Menu")},
                ],
            },
            {
                "id": "modern_menu_sidebar_bg_type",
                "type": "choice",
                "label": tr("bg_mode", "Background Mode"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_bg_type"},
                "default": "color",
                "show_when": _SIDEBAR_CUSTOM,
                "options": [
                    {"value": "image_color", "label": tr("image", "Image")},
                    {"value": "color", "label": tr("color_only", "Color only")},
                    {"value": "accent", "label": tr("accent_color", "Accent")},
                    {"value": "slideshow", "label": tr("slideshow", "Slideshow")},
                ],
            },
            {
                "id": "modern_menu_sidebar_sync_box_effect",
                "type": "toggle",
                "label": tr("sync_box_color_effect", "Sync with Widget Color and Effect"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_sync_box_effect"},
                "default": True,
                "show_when": _SIDEBAR_CUSTOM,
            },
            {
                "id": "modern_menu_hide_profile_bar",
                "type": "toggle",
                "label": tr("hide_profile_sidebar", "Hide profile on sidebar"),
                "bind": {"kind": "col", "key": "modern_menu_hide_profile_bar"},
                "default": False,
            },
            _color_pair_field(
                "modern_menu_sidebar_bg_color",
                tr("color", "Color"),
                "modern_menu_sidebar_bg_color_light",
                "modern_menu_sidebar_bg_color_dark",
                None,
                theme_mode_field="modern_menu_sidebar_bg_color_theme_mode",
                show_when={"all": [_SIDEBAR_CUSTOM,
                                   {"field": "modern_menu_sidebar_bg_type",
                                    "values": ["color", "image_color"]}]},
            ),
            _hidden_field("modern_menu_sidebar_bg_color_light", "#F3F3F3"),
            _hidden_field("modern_menu_sidebar_bg_color_dark", "#2C2C2C"),
            _hidden_field("modern_menu_sidebar_bg_color_theme_mode", "separate"),
            _image_field(
                "modern_menu_sidebar_bg_image",
                "sidebar_bg",
                tr("select_bg_image", "Background Image"),
                light_field="modern_menu_sidebar_bg_image_light",
                dark_field="modern_menu_sidebar_bg_image_dark",
                theme_mode_field="modern_menu_sidebar_bg_image_theme_mode",
                empty_label=tr("none_default", "Default"),
                show_when={"all": [_SIDEBAR_CUSTOM,
                                   {"field": "modern_menu_sidebar_bg_type",
                                    "values": ["image_color"]}]},
            ),
            _hidden_field("modern_menu_sidebar_bg_image_light"),
            _hidden_field("modern_menu_sidebar_bg_image_dark"),
            _hidden_field("modern_menu_sidebar_bg_image_theme_mode", "separate"),
            _image_list_field(
                "modern_menu_sidebar_slideshow_images",
                "sidebar_bg",
                tr("slideshow_images", "Slideshow Images"),
                show_when={"all": [_SIDEBAR_CUSTOM,
                                   {"field": "modern_menu_sidebar_bg_type",
                                    "values": ["slideshow"]}]},
            ),
            {
                "id": "modern_menu_sidebar_slideshow_interval",
                "type": "duration",
                "label": tr("slideshow_interval", "Slide Interval"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_slideshow_interval"},
                "default": 10,
                "show_when": {"all": [_SIDEBAR_CUSTOM,
                                      {"field": "modern_menu_sidebar_bg_type",
                                       "values": ["slideshow"]}]},
            },
            # ── Match Main Menu ───────────────────────────────────────────────
            # The main menu's own background shows through the sidebar; these
            # decide what is laid over it. patcher.py reads them only while
            # `modern_menu_sidebar_bg_mode` is "main".
            {
                "id": "onigiri_sidebar_main_bg_effect_mode",
                "type": "choice",
                "label": tr("effect", "Effect"),
                "bind": {"kind": "col", "key": "onigiri_sidebar_main_bg_effect_mode"},
                "default": "opaque",
                "show_when": _SIDEBAR_MAIN,
                "options": [
                    {"value": "opaque", "label": tr("color_overlay", "Color overlay")},
                    {"value": "glassmorphism", "label": tr("glassmorphism", "Glassmorphism")},
                ],
            },
            {
                "id": "onigiri_sidebar_main_bg_effect_intensity",
                "type": "slider",
                "label": tr("effect_intensity", "Effect Intensity"),
                "bind": {"kind": "col", "key": "onigiri_sidebar_main_bg_effect_intensity"},
                "default": 50, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"all": [_SIDEBAR_MAIN,
                                      {"field": "onigiri_sidebar_main_bg_effect_mode",
                                       "values": ["glassmorphism"]}]},
            },
            _color_pair_field(
                "onigiri_sidebar_opaque_tint_color",
                tr("overlay_color", "Overlay Color"),
                "onigiri_sidebar_opaque_tint_color_light",
                "onigiri_sidebar_opaque_tint_color_dark",
                None,
                show_when={"all": [_SIDEBAR_MAIN,
                                   {"field": "onigiri_sidebar_main_bg_effect_mode",
                                    "values": ["opaque"]}]},
            ),
            _hidden_field("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF"),
            _hidden_field("onigiri_sidebar_opaque_tint_color_dark", "#1D1D1D"),
            _hidden_field("onigiri_sidebar_opaque_tint_color_theme_mode", "separate"),
            {
                "id": "onigiri_sidebar_opaque_tint_intensity",
                "type": "slider",
                "label": tr("overlay_intensity", "Overlay Intensity"),
                "bind": {"kind": "col", "key": "onigiri_sidebar_opaque_tint_intensity"},
                "default": 30, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": {"all": [_SIDEBAR_MAIN,
                                      {"field": "onigiri_sidebar_main_bg_effect_mode",
                                       "values": ["opaque"]}]},
            },
            # Legacy zeroed this on every save through the designer: it is a
            # leftover of the pre-designer page, and a stale value would make
            # the frame semi-transparent behind the user's back. The `sidebar`
            # post-save hook keeps doing exactly that.
            _hidden_field("modern_menu_sidebar_bg_transparency", 0),
            {
                "id": "modern_menu_sidebar_bg_blur",
                "type": "slider",
                "label": tr("blur_intensity", "Blur Intensity"),
                # A flat fill has nothing to blur, so the slider goes away
                # instead of sitting there doing nothing. patcher.py reads both
                # of these only inside its `sidebar_mode == 'custom'` branch.
                "show_when": {"all": [_SIDEBAR_CUSTOM,
                                      {"field": "modern_menu_sidebar_bg_type",
                                       "values": ["image_color", "slideshow"]}]},
                "bind": {"kind": "col", "key": "modern_menu_sidebar_bg_blur"},
                "default": 0, "min": 0, "max": 100, "step": 1, "suffix": "%",
            },
            {
                "id": "modern_menu_sidebar_bg_opacity",
                "type": "slider",
                "label": tr("opacity", "Opacity"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_bg_opacity"},
                "default": 100, "min": 0, "max": 100, "step": 1, "suffix": "%",
                "show_when": _SIDEBAR_CUSTOM,
            },
            {
                "id": "modern_menu_sidebar_radius",
                "type": "slider",
                "label": tr("radius", "Radius"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_radius"},
                "default": 15, "min": 0, "max": 60, "step": 1, "suffix": "px",
            },
            {
                "id": "modern_menu_sidebar_stroke",
                "type": "slider",
                "label": tr("stroke", "Stroke"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_stroke"},
                "default": 1, "min": 0, "max": 10, "step": 1, "suffix": "px",
            },
            {
                "id": "modern_menu_sidebar_margin",
                "type": "slider",
                "label": tr("margin", "Margin"),
                "bind": {"kind": "col", "key": "modern_menu_sidebar_margin"},
                "default": 10, "min": 0, "max": 48, "step": 1, "suffix": "px",
            },
        ],
    )


def _sidebar_actions_section():
    """Action Button Customization (settings/_infra.py:683-828). The 3-zone
    drag/drop editor plus the per-button icon cards become one `button_order`
    field (the visible/archived split, reorderable) plus one icon slot per
    button — each carrying its own tint as an icon-popover companion, which is
    where the legacy right-click "customize" menu put it."""
    fields = [
        {
            "id": "sidebarActionsMode",
            "type": "choice",
            "label": tr("action_buttons_position_label", "Action Buttons Position"),
            "bind": {"kind": "config", "key": "sidebarActionsMode"},
            "default": "list",
            "options": [
                {"value": "list", "label": tr("list_default_short", "List")},
                {"value": "collapsed", "label": tr("collapsed_toolbar_short", "Collapsed")},
                {"value": "archived", "label": tr("archived_hidden_short", "Hidden")},
            ],
        },
        {
            "id": "modern_menu_icon_size_action_button",
            "type": "slider",
            "label": tr("action_button_icons", "Action button icons"),
            "bind": {"kind": "col", "key": "modern_menu_icon_size_action_button"},
            "default": 14, "min": 8, "max": 40, "step": 1, "suffix": "px",
        },
        {
            "id": "sidebarAddDashed",
            "type": "toggle",
            "label": tr("add_button_dashed_label", "Dashed outline on Add"),
            "bind": {"kind": "config", "key": "sidebarAddDashed"},
            "default": False,
        },
        {
            # The whole layout object, edited as one control: drag to reorder,
            # click the eye to archive. Entries this dialog does not know about
            # (the "profile" pill, sidebar-API buttons from other add-ons) are
            # carried through untouched — see renderButtonOrder in settings.js.
            "id": "sidebarButtonLayout",
            "type": "button_order",
            "label": tr("organize_action_buttons", "Organize Action Buttons"),
            # Its own string rather than the legacy page's
            # `action_buttons_reorder_help_v2`, which describes a right-click
            # menu this editor does not have.
            "desc": tr(
                "settings_web_button_order_help",
                "Drag to reorder. Use the eye to archive a button.",
            ),
            "bind": {"kind": "config", "key": "sidebarButtonLayout"},
            "default": {
                "visible": ["profile", "add", "browse", "stats", "sync", "settings",
                            "gamification", "more"],
                "archived": [],
            },
            "options": [
                {"value": key, "label": tr(string_key, fallback), "icon": icon}
                for key, string_key, fallback, icon in SIDEBAR_ACTION_BUTTONS
            ],
            "show_when": {"field": "sidebarActionsMode", "values": ["list", "collapsed"]},
        },
    ]
    # Icons first, then their tints: the deck's column balancer reads the field
    # list as contiguous runs of one type (see rebalanceDeck in settings.js), so
    # interleaving icon/colour/icon/colour would break the icon grid into ten
    # separate one-tile blocks.
    all_buttons = SIDEBAR_ACTION_BUTTONS + SIDEBAR_MORE_BUTTONS
    for key, string_key, fallback, icon in all_buttons:
        fields.append(_icon_field(
            f"modern_menu_icon_{key}", tr(string_key, fallback), f"system:{icon}",
        ))
    for key, _string_key, _fallback, _icon in all_buttons:
        fields.append({
            "id": f"modern_menu_icon_color_{key}",
            "type": "color",
            "label": tr("icon_color", "Icon Color"),
            "bind": {"kind": "col", "key": f"modern_menu_icon_color_{key}"},
            "default": "",
            # Unset means the shared icon colour, which is what the real sidebar
            # falls back to (onigiri_renderer.py:297) — the picker shows it
            # rather than an empty swatch.
            "fallback_light": "sb_icon_color_light",
            "fallback_dark": "sb_icon_color_dark",
        })
    return _designer_preview_section(
        "sidebar_actions",
        "sidebar_actions",
        title=tr("settings_web_tab_action_buttons", "Action Buttons"),
        icon="organise.svg",
        stage_side=True,
        fields=fields,
    )


def _sidebar_decks_section():
    """Deck Icons / Deck Customization (settings/_infra.py:1844-2123): the deck
    list's own glyphs, sizes, indentation, count badges and palette. All five
    colour pairs share one theme-mode key so the card's Dynamic-mode switch
    splits or links the whole palette at once, exactly like the legacy page's
    single light/dark palette toggle."""
    fields = [
        {
            "id": "deck_indentation_mode",
            "type": "choice",
            "label": tr("decks_indentation", "Deck indentation"),
            "bind": {"kind": "config", "key": "deck_indentation_mode"},
            "default": "default",
            "options": [
                {"value": "default", "label": tr("default", "Default")},
                {"value": "smaller", "label": tr("smaller", "Smaller")},
                {"value": "bigger", "label": tr("bigger", "Bigger")},
                {"value": "custom", "label": tr("custom", "Custom")},
            ],
        },
        {
            "id": "deck_indentation_custom_px",
            "type": "number",
            "label": tr("custom_indentation_px", "Custom indentation"),
            "bind": {"kind": "config", "key": "deck_indentation_custom_px"},
            "default": 20, "min": 0, "max": 100, "step": 1, "suffix": "px",
            "show_when": {"field": "deck_indentation_mode", "values": ["custom"]},
        },
        {
            "id": "modern_menu_count_badge_size",
            "type": "choice",
            "label": tr("count_badge_size", "Count Badge Size"),
            "bind": {"kind": "col", "key": "modern_menu_count_badge_size"},
            "default": "small",
            "options": [
                {"value": "small", "label": tr("badge_size_small", "Small")},
                {"value": "medium", "label": tr("badge_size_medium", "Medium")},
                {"value": "big", "label": tr("badge_size_big", "Big")},
                {"value": "custom", "label": tr("custom", "Custom")},
            ],
        },
        {
            "id": "modern_menu_count_badge_size_custom_px",
            "type": "number",
            "label": tr("custom_badge_size_px", "Custom badge size"),
            "bind": {"kind": "col", "key": "modern_menu_count_badge_size_custom_px"},
            "default": 16, "min": 8, "max": 40, "step": 1, "suffix": "px",
            "show_when": {"field": "modern_menu_count_badge_size", "values": ["custom"]},
        },
        {
            "id": "modern_menu_icon_size_deck_folder",
            "type": "slider",
            "label": tr("deck_folder_icons_label", "Deck & folder icons"),
            "bind": {"kind": "col", "key": "modern_menu_icon_size_deck_folder"},
            "default": 20, "min": 8, "max": 40, "step": 1, "suffix": "px",
        },
        {
            "id": "modern_menu_icon_size_collapse",
            "type": "slider",
            "label": tr("expand_collapse_icons_label", "Expand & collapse icons"),
            "bind": {"kind": "col", "key": "modern_menu_icon_size_collapse"},
            "default": 12, "min": 6, "max": 32, "step": 1, "suffix": "px",
        },
        {
            "id": "hideDeckCounts",
            "type": "toggle",
            "label": tr("hide_zero_counts", "Hide zero counts"),
            "bind": {"kind": "config", "key": "hideDeckCounts"},
            "default": True,
        },
        {
            "id": "hideAllDeckCounts",
            "type": "toggle",
            "label": tr("hide_all_counts", "Hide all counts"),
            "bind": {"kind": "config", "key": "hideAllDeckCounts"},
            "default": False,
        },
        {
            "id": "modern_menu_hide_folder_icon",
            "type": "toggle",
            "label": tr("hide_folder_icon", "Hide folder icon"),
            "bind": {"kind": "col", "key": "modern_menu_hide_folder_icon"},
            "default": False,
        },
        {
            "id": "modern_menu_hide_subdeck_icon",
            "type": "toggle",
            "label": tr("hide_subdeck_icon", "Hide subdeck icon"),
            "bind": {"kind": "col", "key": "modern_menu_hide_subdeck_icon"},
            "default": False,
        },
        {
            "id": "modern_menu_hide_deck_icon",
            "type": "toggle",
            "label": tr("hide_deck_icon", "Hide deck icon"),
            "bind": {"kind": "col", "key": "modern_menu_hide_deck_icon"},
            "default": False,
        },
        {
            "id": "modern_menu_hide_filtered_deck_icon",
            "type": "toggle",
            "label": tr("hide_filtered_deck_icon", "Hide filtered deck icon"),
            "bind": {"kind": "col", "key": "modern_menu_hide_filtered_deck_icon"},
            "default": False,
        },
        {
            "id": "modern_menu_hide_default_icons",
            "type": "toggle",
            "label": tr("hide_default_show_custom", "Hide default icons, keep custom ones"),
            "desc": tr(
                "hide_default_show_custom_desc",
                "Default icons disappear; a deck's own custom icon still shows.",
            ),
            "bind": {"kind": "col", "key": "modern_menu_hide_default_icons"},
            "default": False,
        },
    ]
    palette_mode = "onigiri_sidebar_deck_colors_theme_mode"
    # `--deck-list-bg` and `--highlight-fg` are stored empty by default, meaning
    # "inherit": the deck list lets the sidebar's own background through, and a
    # highlighted row keeps the normal text colour. `fallback_*` names where that
    # inherited colour lives so the row can show it (with its hex) instead of a
    # blank swatch, without writing a value that would stop the inheriting.
    for field_id, token, label, light, dark, fallback in (
        ("sb_deck_list_bg", "--deck-list-bg", tr("deck_list_bg_label", "Deck list background"),
         "", "", ("modern_menu_sidebar_bg_color_light", "modern_menu_sidebar_bg_color_dark")),
        ("sb_highlight_bg", "--highlight-bg", tr("highlight_bg_label", "Row highlight"),
         "#eeeeee", "#3c3c3c", None),
        ("sb_highlight_fg", "--highlight-fg", tr("highlight_fg_label", "Row highlight text"),
         "", "", ("gal_fg_light", "gal_fg_dark")),
    ):
        extra = {}
        if fallback:
            extra["fallback_light"], extra["fallback_dark"] = fallback
        fields.extend(_theme_color_pair(
            field_id, label, token, light, dark, theme_mode_field=palette_mode, **extra,
        ))
    fields.append(_hidden_config_field(palette_mode, [palette_mode], "separate"))
    # `--icon-color` / `--icon-color-filtered` have no rows of their own any
    # more: an icon's colour is set inside that icon's picker. They stay as
    # storage because they are still what an untinted glyph is painted with —
    # every picker shows the matching one as its "unchanged" colour.
    fields.extend([
        _hidden_config_field("sb_icon_color_light", ["colors", "light", "--icon-color"], "#333333"),
        _hidden_config_field("sb_icon_color_dark", ["colors", "dark", "--icon-color"], "#E0E0E0"),
        _hidden_config_field("sb_icon_color_filtered_light", ["colors", "light", "--icon-color-filtered"], "#0077C8"),
        _hidden_config_field("sb_icon_color_filtered_dark", ["colors", "dark", "--icon-color-filtered"], "#0077C8"),
    ])
    for key, string_key, fallback, icon in SIDEBAR_DECK_ICONS:
        fields.append(_icon_field(
            f"modern_menu_icon_{key}", tr(string_key, fallback), f"system:{icon}",
        ))
    # Each glyph's own tint, shown inside that glyph's picker (the colour and the
    # icon are one decision). Left empty it falls through to the palette keys
    # above — which `fallback_light`/`fallback_dark` name, so the picker can show
    # that colour instead of an empty swatch — and which
    # patcher.generate_icon_css paints with when the tint is unset.
    for key, _string_key, _fallback, _icon in SIDEBAR_DECK_ICONS:
        filtered = key == "filtered_deck"
        fields.append({
            "id": f"modern_menu_icon_color_{key}",
            "type": "color",
            "label": tr("icon_color", "Icon Color"),
            "bind": {"kind": "col", "key": f"modern_menu_icon_color_{key}"},
            "default": "",
            "fallback_light": "sb_icon_color_filtered_light" if filtered else "sb_icon_color_light",
            "fallback_dark": "sb_icon_color_filtered_dark" if filtered else "sb_icon_color_dark",
        })
    return _designer_preview_section(
        "sidebar_decks",
        "deck_list",
        title=tr("settings_web_tab_decks", "Decks"),
        icon="folder.svg",
        dynamic_keys=[palette_mode],
        stage_side=True,
        fields=fields,
    )


def _sidebar_markers_section():
    """The four favourite markers (settings/_page_sidebar.py:85-291).

    One card per marker, not twelve rows: a marker is a single thing the user
    recognises by how it looks in the deck list, so each card leads with that —
    a deck row drawn exactly as `patcher.py:6120-6141` draws it (the coloured
    dot, or the chosen glyph masked in that colour) — with its colour, glyph and
    name edited underneath. The `markers` list below tells the renderer which
    three fields belong to which marker."""
    fields = []
    for key, fallback_color in MARKER_DEFINITIONS:
        label = tr(f"marker_{key}", key.title())
        fields.append({
            "id": f"marker_color_{key}",
            "type": "color",
            "label": tr("color", "Color"),
            "bind": {"kind": "config", "path": ["markerColors", key]},
            "default": fallback_color,
        })
        fields.append({
            "id": f"marker_icon_{key}",
            "type": "icon",
            "label": tr("icon", "Icon"),
            "bind": {"kind": "config", "path": ["markerIcons", key]},
            # "default" is the plain coloured dot the deck list draws when no
            # glyph is chosen (patcher.py:6124) — not a missing value.
            "default": "default",
        })
        fields.append({
            "id": f"marker_name_{key}",
            "type": "text",
            "label": tr("name", "Name"),
            "placeholder": label,
            "bind": {"kind": "config", "path": ["markerNames", key]},
            "default": "",
        })
    return {
        "id": "sidebar_markers",
        "title": tr("markers", "Markers"),
        "icon": "star.svg",
        "layout": "markers",
        "preview_kind": "sidebar_markers",
        "markers": [
            {
                "key": key,
                "label": tr(f"marker_{key}", key.title()),
                "color_field": f"marker_color_{key}",
                "icon_field": f"marker_icon_{key}",
                "name_field": f"marker_name_{key}",
            }
            for key, _fallback in MARKER_DEFINITIONS
        ],
        "fields": fields,
    }


def _sidebar_page():
    return {
        "id": "sidebar",
        "legacy_name": "Sidebar",
        "title": tr("sidebar", "Sidebar"),
        "icon": "sidebar.svg",
        "group": "menu",
        "description": "",
        "tabbed": True,
        "sections": [
            _sidebar_background_section(),
            _sidebar_actions_section(),
            _sidebar_decks_section(),
            _sidebar_markers_section(),
        ],
        "post_save": ["sidebar"],
    }


# ── Gallery ───────────────────────────────────────────────────────────────────
#
# The legacy Gallery page (settings/_page_gallery.py:332-627) was a read-out of
# every colour in use plus every picture on disk, where a tile was a shortcut to
# the page that owned it. Here the colours are editable in place — a tile that
# only navigates somewhere else to be changed is a detour, not a feature — and
# the images become one browser over the same folders, wired to the gallery
# commands the picture popover already uses.

GALLERY_ASSET_FOLDERS = (
    ("profile", "profile_pictures", "Profile Pictures"),
    ("profile_bg", "profile_backgrounds", "Profile Backgrounds"),
    ("main_bg", "main_menu_overviewer_images", "Main Menu & Overviewer"),
    ("sidebar_bg", "sidebar_backgrounds", "Sidebar Backgrounds"),
    ("reviewer_bg", "reviewer_backgrounds", "Reviewer Backgrounds"),
    ("reviewer_bar_bg", "reviewer_bar_backgrounds", "Reviewer Bar Backgrounds"),
    ("toolbar_bg", "toolbar_backgrounds", "Toolbar Backgrounds"),
)


def _gallery_palette_section():
    fields = []
    for field_id, token, label, light, dark in (
        ("gal_accent", "--accent-color", tr("accent_color", "Accent"), "#0077C8", "#0077C8"),
        ("gal_bg", "--bg", tr("bg_label", "Background"), "#f3f3f3", "#2c2c2c"),
        ("gal_canvas_inset", "--canvas-inset", tr("canvas_inset_label", "Widget surface"), "#ffffff", "#2c2c2c"),
        ("gal_border", "--border", tr("border_color", "Border Color"), "#e0e0e0", "#424242"),
        ("gal_fg", "--fg", tr("fg_label", "Text"), "#212121", "#e0e0e0"),
        ("gal_fg_subtle", "--fg-subtle", tr("fg_subtle_label", "Subtle text"), "#757575", "#9e9e9e"),
    ):
        fields.extend(_theme_color_pair(field_id, label, token, light, dark))
    return {
        "id": "gallery_palette",
        "title": tr("category_palette", "Palette"),
        "icon": "themes.svg",
        "layout": "",
        "fields": fields,
    }


def _gallery_menu_colors_section():
    fields = []
    for field_id, token, label, light, dark in (
        ("gal_heatmap_color", "--heatmap-color", tr("heatmap_color_label", "Heatmap"), "#0077C8", "#0077C8"),
        ("gal_heatmap_zero", "--heatmap-color-zero", tr("heatmap_color_zero_label", "Heatmap (empty day)"), "#f0f0f0", "#3a3a3a"),
        ("gal_star", "--star-color", tr("star_color_label", "Star"), "#FFD700", "#FFD700"),
        ("gal_star_empty", "--empty-star-color", tr("empty_star_color_label", "Empty star"), "#e0e0e0", "#4a4a4a"),
    ):
        fields.extend(_theme_color_pair(field_id, label, token, light, dark))
    fields.extend([
        # Own ids, same keys as Main menu's Heatmap card owns: a field id has to
        # be unique across the whole dialog (it addresses one control and one
        # store slot), while the *setting* is deliberately reachable from both
        # places. Editing it here shows up on the Heatmap card next time that
        # page is mounted.
        _single_color_slot(
            "gal_streak_icon_color",
            tr("heatmap_streak_icon_color", "Streak Icon Color"),
            {"kind": "config", "key": "heatmapStreakIconColor"},
            "#ff6b35",
        ),
        _single_color_slot(
            "gal_streak_icon_zero_color",
            tr("heatmap_streak_icon_zero_color", "Streak Icon Color (0 days)"),
            {"kind": "config", "key": "heatmapStreakIconZeroColor"},
            "#8f8f8f",
        ),
    ])
    return {
        "id": "gallery_menu_colors",
        "title": tr("category_main_menu", "Main menu"),
        "icon": "main_menu.svg",
        "layout": "",
        "fields": fields,
    }


def _gallery_sidebar_colors_section():
    fields = []
    for field_id, token, label, light, dark in (
        ("gal_highlight_bg", "--highlight-bg", tr("highlight_bg_label", "Row highlight"), "#eeeeee", "#3c3c3c"),
        ("gal_deck_hover", "--deck-hover-bg", tr("deck_hover_bg_label", "Deck hover"), "rgba(128, 128, 128, 0.1)", "rgba(128, 128, 128, 0.1)"),
        ("gal_deck_dragging", "--deck-dragging-bg", tr("deck_dragging_bg_label", "Deck dragging"), "#cde4f9", "#3a3a3a"),
        ("gal_deck_edit_mode", "--deck-edit-mode-bg", tr("deck_edit_mode_bg_label", "Deck edit mode"), "rgba(128, 128, 128, 0.05)", "rgba(128, 128, 128, 0.05)"),
    ):
        fields.extend(_theme_color_pair(field_id, label, token, light, dark))
    for key, fallback_color in MARKER_DEFINITIONS:
        fields.append(_single_color_slot(
            f"gal_marker_{key}",
            tr(f"marker_{key}", key.title()),
            {"kind": "config", "path": ["markerColors", key]},
            fallback_color,
        ))
    return {
        "id": "gallery_sidebar_colors",
        "title": tr("category_sidebar", "Sidebar"),
        "icon": "sidebar.svg",
        "layout": "",
        "fields": fields,
    }


def _gallery_reviewer_colors_section():
    fields = []
    for grade, string_key, fallback in (
        ("again", "again", "Again"),
        ("hard", "hard", "Hard"),
        ("good", "good", "Good"),
        ("easy", "easy", "Easy"),
    ):
        grade_label = tr(string_key, fallback)
        fields.extend(_key_color_pair(
            f"gal_btn_{grade}_bg",
            tr(f"{grade}_bg", f"{grade_label} background"),
            f"onigiri_reviewer_btn_{grade}_bg_light",
            f"onigiri_reviewer_btn_{grade}_bg_dark",
            {"again": "#ffb3b3", "hard": "#ffe0b3", "good": "#b3ffb3", "easy": "#b3d9ff"}[grade],
            {"again": "#ffcccb", "hard": "#ffd699", "good": "#90ee90", "easy": "#add8e6"}[grade],
        ))
        fields.extend(_key_color_pair(
            f"gal_btn_{grade}_text",
            tr(f"{grade}_text", f"{grade_label} text"),
            f"onigiri_reviewer_btn_{grade}_text_light",
            f"onigiri_reviewer_btn_{grade}_text_dark",
            {"again": "#4d0000", "hard": "#4d2600", "good": "#004d00", "easy": "#00264d"}[grade],
            {"again": "#4a0000", "hard": "#4d1d00", "good": "#004000", "easy": "#002952"}[grade],
        ))
    return {
        "id": "gallery_reviewer_colors",
        "title": tr("category_reviewer", "Reviewer"),
        "icon": "add-card.svg",
        "layout": "",
        "fields": fields,
    }


def _gallery_images_section():
    return {
        "id": "gallery_images",
        "title": tr("images_gallery", "Images"),
        "icon": "folder.svg",
        "layout": "gallery_assets",
        # Read by settings.js's renderGalleryAssets and by render.gallery_context,
        # which ships each folder's contents with the page.
        "folders": [
            {"id": folder, "title": tr(string_key, fallback)}
            for folder, string_key, fallback in GALLERY_ASSET_FOLDERS
        ],
        "fields": [],
    }


def _gallery_page():
    return {
        "id": "gallery",
        "legacy_name": "Gallery",
        "title": tr("gallery", "Gallery"),
        "icon": "folder.svg",
        "group": "general",
        "description": tr(
            "colors_gallery_desc",
            "Every colour and picture in use, in one place.",
        ),
        "tabbed": True,
        "sections": [
            _gallery_palette_section(),
            _gallery_menu_colors_section(),
            _gallery_sidebar_colors_section(),
            _gallery_reviewer_colors_section(),
            _gallery_images_section(),
        ],
    }


def _mainmenu_page():
    """Main menu: Organize (widget grid), Background, Widget Color and Effect,
    Stats Widgets, Deck Stats, Heatmap — built up section by section as each
    is ported; not wired into `build_pages()` until every section lands (see
    the plan's "removing the legacy stub" step)."""
    return {
        "id": "mainmenu",
        "legacy_name": "Main menu",
        "title": tr("main_menu", "Main menu"),
        "icon": "main_menu.svg",
        "group": "menu",
        "description": "",
        # Sections are sub-menu tabs, one mounted at a time (settings.js
        # renderTabbedPage) instead of one long scrolling page.
        "tabbed": True,
        # Mirrors the Stats Widgets retention-star toggle into the older
        # `hideRetentionStars` key the renderer still gives priority to.
        "post_save": ["stats_widgets"],
        "sections": [
            _mainmenu_organize_section(),
            _mainmenu_background_section(),
            _mainmenu_widget_effect_section(),
            _mainmenu_stats_widgets_section(),
            _mainmenu_deck_stats_section(),
            _mainmenu_heatmap_section(),
        ],
    }


def build_pages():
    """Every nav entry, in order. Called fresh on each dialog open so
    translations, font lists and platform probes are current."""
    return [
        _profile_page(),
        _sync_page(),
        _modes_page(),
        _languages_page(),
        _fonts_page(),
        _themes_page(),
        _gallery_page(),
        _mainmenu_page(),
        _sidebar_page(),
        _overviewer_page(),
        _reviewer_page(),
        _prep_station_page(),
        _hashi_notes_page(),
        _pomodoro_page(),
    ] + games.build_pages()


NAV_GROUPS = [
    ("general", lambda: tr("general", "General")),
    ("menu", lambda: tr("menu", "Menu")),
    ("study", lambda: tr("study_pages", "Study pages")),
    ("tools", lambda: tr("study_tools", "Study Tools")),
    ("games", lambda: tr("games", "Games")),
]


def nav_groups():
    return [{"id": gid, "title": label()} for gid, label in NAV_GROUPS]


def iter_fields(pages):
    for page in pages:
        for section in page.get("sections", []):
            for field in section.get("fields", []):
                yield page, section, field
