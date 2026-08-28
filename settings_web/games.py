# The Games pages of the WebUI settings dialog.
#
# These replace the standalone PyQt "Gamification Settings" window
# (gamification_settings.py). Every field binds to the exact config location the
# old dialog wrote, so the games themselves needed no changes: what moved is the
# surface, not the storage.
#
#   Gamification   the games launcher, notifications, Profile Level styling
#   Nook Level     the restaurant game
#   Onigimon       the Ankimon-backed companion widget
#   Hexagon Land   the island builder
#   Bento Games    third-party mini-games detected on this profile
#   Focus Dango    study-zone lock messages
#   Mochi Messages study-zone encouragement messages
#
# Values that do not live in the addon config — the Nook's name, the active
# companion, the island name — bind through games_state's `game` accessors.

from .. import config
from ..translations import tr

# Per-game accent, mirroring the classic dialog's sidebar tint so a page still
# reads as "the Nook one" / "the Onigimon one" at a glance.
ACCENTS = {
    "nook": "#B94632",
    "onigimon": "#F2B705",
    "hexagon": "#1F6FE0",
    "bento": "#6A40E0",
    "dango": "#9D3D64",
    "mochi": "#00935C",
    "focused": "#5b8dee",
}

# Rows that only mean something while the profile draws a level *chip* — the
# Bar profile type. Ring and Minimal fill a ring/track instead, which takes the
# progress colour and nothing else.
# `modern_menu_profile_type` is the Profile page's own field; every page shares
# one values map in settings.js, so this reads the live selection rather than
# needing a copy of it here.
BAR_ONLY = {"field": "modern_menu_profile_type", "values": ["bar"]}


def _asset(relative):
    """Media-server URL for a bundled file. Imported lazily: render imports
    schema, which imports this module."""
    from .render import addon_uri

    return addon_uri(relative)


def _image(name):
    return _asset(f"system_files/gamification_images/{name}")


def _conf_path(*path):
    return {"kind": "config", "path": list(path)}


def _toggle(field_id, label, path, default=False, **extra):
    field = {
        "id": field_id,
        "type": "toggle",
        "label": label,
        "bind": _conf_path(*path) if len(path) > 1 else {"kind": "config", "key": path[0]},
        "default": default,
    }
    field.update(extra)
    return field


def _hero_toggle(field_id, label, desc, path, image, accent, default=False, **extra):
    """The big page header: artwork, title, description and the game's own
    on/off switch — the classic dialog's `_create_study_zone_header`.

    `image` is either a bundled .svg name (inlined so it follows the theme's
    text colour) or a URL to one of the games' raster illustrations."""
    if image and image.endswith(".svg") and "/" not in image:
        extra = dict(extra, icon=image)
    else:
        extra = dict(extra, hero_image=image)
    return _toggle(
        field_id, label, path, default,
        desc=desc, hero=True, accent=accent, **extra
    )


def _game_hero_toggle(field_id, label, desc, path, image, accent, **extra):
    """A hero for one of the games. Each game is now gated by its own switch
    alone: the Gamification Mode master switch it used to cascade into is
    gone."""
    return _hero_toggle(field_id, label, desc, path, image, accent, **extra)


def _note(field_id, label="", desc="", **extra):
    field = {"id": field_id, "type": "note", "label": label, "desc": desc}
    field.update(extra)
    return field


def _action(field_id, label, button_label, action, desc="", **extra):
    field = {
        "id": field_id,
        "type": "action",
        "label": label,
        "desc": desc,
        "button_label": button_label,
        # Routed through the dialog's `games_action` bridge command rather than
        # being its own command per button.
        "action": "games_action:" + action,
    }
    field.update(extra)
    return field


def _hidden(field_id, path, default=""):
    return {
        "id": field_id,
        "type": "hidden",
        "label": "",
        "bind": _conf_path(*path),
        "default": default,
    }


def _message_values(value, fallback):
    """Messages are stored as a list, but very old profiles hold one string with
    newlines. Same normalisation the classic editor did on load."""
    if isinstance(value, list):
        items = [str(item) for item in value]
    elif isinstance(value, str):
        items = value.splitlines()
    else:
        items = []
    items = [item for item in items if str(item).strip()]
    return items or list(fallback)


# ── page 1: Gamification ──────────────────────────────────────────────────────


def _chip_color_pair(field_id, label, base_key, light_key, dark_key, role,
                    show_when=None):
    """One of the three Level Chip colours.

    Reuses the light/dark colour-pair control: with Dynamic chip colours off it
    writes the single `chip_*_color` key, and with it on the `_light`/`_dark`
    pair — exactly the branch nook_level.get_chip_style_values() reads. The two
    theme keys stay as hidden fields so they are persisted without being shown
    as rows of their own."""
    field = {
        "id": field_id,
        "type": "color_pair",
        "label": label,
        "bind": _conf_path("restaurant_level", base_key),
        "default": "",
        "light_field": field_id + "_light",
        "dark_field": field_id + "_dark",
        "dynamic_field": "g_rl_dynamic_chip_colors",
        # With Dynamic off the pair collapses onto this key, not onto the light
        # one — the chip reader looks at `chip_*_color` in that mode.
        "single_field": field_id,
        # ...and with Dynamic on it is always two slots: "the same colour for
        # both" is what Dynamic *off* already means here, so inferring a link
        # from the two values being equal would silently write the wrong key.
        "always_split": True,
        # Filled in by the page from chipDefaults, so an unset slot shows the
        # colour the chip will actually use instead of a blank swatch.
        "chip_role": role,
    }
    if show_when:
        field["show_when"] = show_when
    return field


def _chip_hidden(field_id, key):
    return _hidden(field_id, ("restaurant_level", key), "")


GAME_CARDS = (
    # Launcher tiles, in the order the 2×3 grid draws them: the Nook opens the
    # grid full width, then the four others pair off.
    {
        "id": "nook", "page": "nook_level", "toggle": "g_nook_enabled",
        "image": "nook.webp", "accent": "nook", "wide": True,
        "title_key": ("restaurant_level", "Nook Level"),
        "desc_key": ("game_card_nook_desc", "Grow your Nook restaurant as you study."),
    },
    {
        "id": "onigimon", "page": "onigimon", "toggle": "g_onigimon_enabled",
        "image": "pokemon_pikachu.webp", "accent": "onigimon",
        "title_key": ("onigimon_title", "Onigimon"),
        "desc_key": ("game_card_onigimon_desc", "Raise an Ankimon companion while you review."),
    },
    {
        "id": "hexagon", "page": "hexagon_land", "toggle": "g_hexagon_enabled",
        "image": "Hexagon_world.webp", "accent": "hexagon",
        "title_key": ("hexagon_land_title", "Hexagon Land"),
        "desc_key": ("game_card_hexagon_desc", "Build an island, tile by tile, as you study."),
    },
    {
        "id": "mochi", "page": "mochi_messages", "toggle": "g_mochi_enabled",
        "image": "mochi_messenger.webp", "accent": "mochi",
        "title_key": ("mochi_messages_title", "Mochi Messages"),
        "desc_key": ("game_card_mochi_desc", "Encouraging messages between cards."),
    },
    {
        "id": "dango", "page": "focus_dango", "toggle": "g_dango_enabled",
        "image": "dango.webp", "accent": "dango",
        "title_key": ("focus_dango", "Focus Dango"),
        "desc_key": ("game_card_dango_desc", "Keeps review sessions free of distractions."),
    },
)


def _game_cards():
    """The launcher tiles, resolved for the page. `toggle` names a field that
    lives on the game's own page — settings.js reads its live value, so a card
    shows whether the game is on without a second binding for the same key."""
    return [
        {
            "id": card["id"],
            "page": card["page"],
            "toggle": card["toggle"],
            "title": tr(*card["title_key"]),
            "desc": tr(*card["desc_key"]),
            "image": _image(card["image"]),
            "accent": ACCENTS[card["accent"]],
            "wide": bool(card.get("wide")),
        }
        for card in GAME_CARDS
    ]


def _gamification_page():
    return {
        "id": "gamification",
        "legacy_name": "General",
        "title": "Gamification",
        "icon": "gamepad.svg",
        "group": "games",
        "description": "",
        "post_save": ["gamification"],
        # Three areas, one mounted at a time (settings.js renderTabbedPage):
        # the launcher, the notification rules, and the profile level.
        "tabbed": True,
        "sections": [
            {
                "id": "gamification_select",
                "title": tr("select_games", "Select Games"),
                "layout": "games_gallery",
                "description": tr(
                    "select_games_desc",
                    "Every game Onigiri ships with. Open one to set it up.",
                ),
                "cards": _game_cards(),
                "fields": [],
            },
            {
                # One container: the toast is previewed on the reviewer's own
                # background, and every rule that shapes it — style, silence,
                # position, dwell time — sits under that preview.
                "id": "gamification_notifications",
                "title": tr("notifications", "Notifications"),
                "layout": "designer_preview",
                "preview_kind": "notification",
                "stage_side": False,
                "head_to_deck": False,
                "icon_colors_inline": False,
                "dynamic_keys": [],
                "sync_toggle_id": "",
                "sync_hidden_fields": [],
                "fields": [
                    {
                        "id": "g_notification_mode",
                        "type": "choice",
                        "label": tr("notification_style", "Notification style"),
                        "bind": {"kind": "config", "key": "onigiri_reviewer_notification_mode"},
                        "default": "classic",
                        # The card's subject: the stage draws whichever of the
                        # two this picks, so it belongs in the header.
                        "head": True,
                        "options": [
                            {"value": "classic", "label": tr("notification_mode_classic", "Classic")},
                            {"value": "mini", "label": tr("notification_mode_mini", "Mini")},
                        ],
                    },
                    _toggle(
                        "g_silent_mode",
                        tr("silent_mode", "Silent mode"),
                        ("onigiri_reviewer_silent_notifications",),
                        head=True,
                        head_label=tr("silent_mode", "Silent mode"),
                    ),
                    {
                        "id": "g_notification_position",
                        "type": "notif_position",
                        "label": tr("reviewer_notification_pos_title", "Notification Position"),
                        "bind": {"kind": "config", "key": "onigiri_reviewer_notification_position"},
                        "default": "top-center",
                        # Mini notifications are anchored to the reviewer header
                        # and silenced ones are drawn nowhere at all, so in both
                        # states this picker has nothing to control.
                        "show_when": {"all": [
                            {"field": "g_notification_mode", "values": ["classic"]},
                            {"not": {"field": "g_silent_mode", "values": [True]}},
                        ]},
                    },
                    {
                        "id": "g_notification_duration",
                        "type": "number",
                        "label": tr("notification_display_time", "Show notifications for"),
                        "bind": {"kind": "config", "key": "onigiri_notification_duration_ms"},
                        "default": 5200,
                        "min": 1,
                        "max": 30,
                        # Stored in milliseconds (every reader expects that),
                        # edited in seconds.
                        "scale": 1000,
                        "suffix": tr("seconds_short", "sec"),
                        "show_when": {"not": {"field": "g_silent_mode", "values": [True]}},
                    },
                ],
            },
            {
                # The level on the profile card: which game it counts, and how
                # it is drawn. What "how" means depends on the Profile Type
                # picked in Profile — a chip in Bar, the ring's fill in Ring, the
                # track's fill in Minimal — so the preview and the colour rows
                # follow that selection rather than always showing the chip.
                "id": "gamification_profile_level",
                "title": tr("profile_level_title", "Profile Level"),
                "layout": "designer_preview",
                "preview_kind": "profile_level",
                # Dynamic mode controls whether the preview has distinct
                # light/dark values. When it is off, the shared designer
                # preview forces light mode and hides its theme button.
                "preview_dynamic_field": "profile",
                "stage_side": False,
                "head_to_deck": False,
                "icon_colors_inline": False,
                "dynamic_keys": [],
                "sync_toggle_id": "",
                "sync_hidden_fields": [],
                "description": tr(
                    "profile_level_desc",
                    "Choose which game's level is shown on your profile.",
                ),
                "fields": [
                    {
                        "id": "g_profile_level_game",
                        "type": "choice",
                        "label": tr("profile_level_game", "Level source"),
                        "bind": {"kind": "config", "key": "profile_level_game"},
                        "default": "nook",
                        "head": True,
                        "options": [
                            {"value": "nook", "label": tr("profile_level_opt_nook", "Nook")},
                            {"value": "onigimon", "label": tr("profile_level_opt_onigimon", "Onigimon XP")},
                            {"value": "hexagon", "label": tr("profile_level_opt_hexagon", "Hexagon Land")},
                        ],
                    },
                    # Profile owns Dynamic mode. Keep the legacy Nook key
                    # persisted as a hidden companion so the renderer follows
                    # Profile without exposing a second switch here.
                    _hidden(
                        "g_rl_dynamic_chip_colors",
                        ("restaurant_level", "dynamic_chip_colors"),
                        True,
                    ),
                    _chip_color_pair(
                        "g_rl_chip_bg", tr("level_chip_bg_color", "Chip background"),
                        "chip_bg_color", "chip_bg_color_light", "chip_bg_color_dark", "bg",
                        # Only the Bar profile draws a chip; Ring and Minimal fill
                        # a ring/track that has no background of its own.
                        show_when=BAR_ONLY,
                    ),
                    _chip_hidden("g_rl_chip_bg_light", "chip_bg_color_light"),
                    _chip_hidden("g_rl_chip_bg_dark", "chip_bg_color_dark"),
                    {
                        # Alpha of the chip background. Not a key of its own:
                        # the classic dialog stored it inside the colour as a Qt
                        # #AARRGGBB string, and the chip reader still parses it
                        # that way, so this slider edits the bound colour rather
                        # than staging a value of its own.
                        "id": "g_rl_chip_bg_opacity",
                        "type": "slider",
                        "label": tr("background_opacity", "Background opacity"),
                        "virtual": True,
                        "alpha_of": "g_rl_chip_bg",
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "suffix": "%",
                        "default": 100,
                        "show_when": BAR_ONLY,
                    },
                    _chip_color_pair(
                        "g_rl_chip_progress", tr("level_chip_progress_color", "Progress"),
                        "chip_progress_color", "chip_progress_color_light",
                        "chip_progress_color_dark", "progress",
                    ),
                    _chip_hidden("g_rl_chip_progress_light", "chip_progress_color_light"),
                    _chip_hidden("g_rl_chip_progress_dark", "chip_progress_color_dark"),
                    _chip_color_pair(
                        "g_rl_chip_text", tr("level_chip_text_color", "Text"),
                        "chip_text_color", "chip_text_color_light",
                        "chip_text_color_dark", "text",
                        show_when=BAR_ONLY,
                    ),
                    _chip_hidden("g_rl_chip_text_light", "chip_text_color_light"),
                    _chip_hidden("g_rl_chip_text_dark", "chip_text_color_dark"),
                ],
            },
        ],
    }


# ── page 2: Nook Level ────────────────────────────────────────────────────────


def _nook_page():
    from . import games_state

    progress = games_state.nook_context()
    can_rename = int(progress.get("level", 0)) >= 5

    name_fields = []
    if can_rename:
        name_fields.append({
            "id": "g_nook_name",
            "type": "text",
            "label": tr("custom_name", "Custom name"),
            # Lives in the Nook manager's own state, not the addon config.
            "bind": {"kind": "game", "key": "nook_name"},
            "default": progress.get("name", ""),
            "show_when": {"field": "g_nook_enabled", "values": [True]},
        })
    else:
        name_fields.append(_note(
            "g_nook_name_locked",
            tr("restaurant_name", "Name"),
            tr("reach_level_5", "").format(level=progress.get("level", 0)),
            show_when={"field": "g_nook_enabled", "values": [True]},
        ))

    return {
        "id": "nook_level",
        "legacy_name": "Nook Level",
        "title": tr("restaurant_level", "Nook Level"),
        "icon": "nook.svg",
        "group": "games",
        # No page description: the hero below is this page's subject and says it.
        "post_save": ["nook_level", "gamification"],
        "sections": [
            {
                "id": "nook_hero",
                "title": "",
                "fields": [
                    _game_hero_toggle(
                        "g_nook_enabled",
                        tr("restaurant_level", "Nook Level"),
                        tr("grow_restaurant_desc", ""),
                        ("restaurant_level", "enabled"),
                        _image("nook.webp"),
                        ACCENTS["nook"],
                        square=True,
                    ),
                    # Keep the name control in the same visual group as the
                    # game's switch. It collapses with the hero when Nook
                    # Level is disabled instead of leaving an orphan section.
                    *name_fields,
                ],
            },
            {
                "id": "nook_visibility",
                "title": tr("notifications_visibility", "Notifications & Visibility"),
                "layout": "nook_visibility",
                "fields": [
                    _toggle("g_nook_notifications", tr("show_levelup_notifications", ""),
                            ("restaurant_level", "notifications_enabled"), True, square=True),
                    _toggle("g_nook_profile_bar", tr("show_progress_sidebar", ""),
                            ("restaurant_level", "show_profile_bar_progress"), True, square=True),
                    _toggle("g_nook_reviewer_header", tr("show_level_reviewer", ""),
                            ("restaurant_level", "show_reviewer_header"), True, square=True),
                ],
            },
            {
                "id": "nook_difficulty",
                "title": tr("difficulty_level", "Difficulty"),
                "fields": [
                    {
                        "id": "g_nook_difficulty",
                        "type": "game_choice",
                        "label": "",
                        "bind": _conf_path("restaurant_level", "difficulty"),
                        "default": "Apprendice",
                        "options": [
                            {
                                "value": "Apprendice", "label": tr("difficulty_apprentice_option"),
                                "desc": tr("apprentice_desc", ""),
                                "icon": "seed.svg", "accent": "#4CAF50",
                            },
                            {
                                "value": "Experient", "label": tr("difficulty_experient_option"),
                                "desc": tr("cook_desc", ""),
                                "icon": "tree.svg", "accent": "#F2B705",
                            },
                            {
                                "value": "Legend", "label": tr("difficulty_legend_option"),
                                "desc": tr("chef_desc", ""),
                                "icon": "crown.svg", "accent": "#E8562F",
                            },
                        ],
                    },
                ],
            },
            {
                "id": "nook_rush_sync",
                "title": tr("recipe_rush_sync_title", "Nook Rush Sync"),
                "fields": [
                    _action(
                        "g_nook_rush_sync",
                        tr("recipe_rush_sync_title", "Nook Rush Sync"),
                        tr("recipe_rush_sync_button", "Sync Rush Now"),
                        "nook_rush_sync",
                        button_icon="sync",
                        neutral=True,
                        desc=tr(
                            "recipe_rush_sync_desc",
                            "If the equipped Nook's Rush still shows a generic ticket, force a "
                            "fresh pick for today - today's card progress is kept.",
                        ),
                    ),
                ],
            },
            {
                "id": "nook_reset",
                "title": tr("reset_progress_title", "Reset progress"),
                "fields": [
                    _action("g_nook_reset_progress", tr("reset_restaurant_level", ""),
                            tr("reset", "Reset"), "nook_reset_progress", neutral=True,
                            hold_to_confirm=True, button_icon="reset"),
                    _action("g_nook_reset_coins", tr("reset_coins", ""),
                            tr("reset", "Reset"), "nook_reset_coins", neutral=True,
                            hold_to_confirm=True, button_icon="reset"),
                    _action("g_nook_reset_purchases", tr("reset_purchases", ""),
                            tr("reset", "Reset"), "nook_reset_purchases", neutral=True,
                            hold_to_confirm=True, button_icon="reset"),
                ],
            },
        ],
    }


# ── page 3: Onigimon ──────────────────────────────────────────────────────────


def _onigimon_page():
    return {
        "id": "onigimon",
        "legacy_name": "Onigimon",
        "title": "Onigimon",
        "icon": "pokeball.svg",
        "group": "games",
        "post_save": ["gamification"],
        "sections": [
            {
                "id": "onigimon_hero",
                "title": "",
                "fields": [
                    _game_hero_toggle(
                        "g_onigimon_enabled",
                        "Onigimon",
                        tr("onigimon_page_desc", ""),
                        ("onigimon", "enabled"),
                        _image("pokemon_pikachu.webp"),
                        ACCENTS["onigimon"],
                    ),
                    # Filled in from the live context once the page is open:
                    # asking Ankimon whether it is installed means importing
                    # onigimon.py, which no other page should pay for.
                    _note("g_onigimon_ankimon_status", context_key="ankimon", tone="warn"),
                ],
            },
            {
                "id": "onigimon_companions",
                "title": tr("onigimon_companion_title", "Companion"),
                "layout": "onigimon_companions",
                "fields": [
                    {
                        "id": "g_onigimon_companion",
                        "type": "hidden",
                        "label": "",
                        "bind": {"kind": "game", "key": "onigimon_companion"},
                        "default": "",
                    },
                    {
                        "id": "g_onigimon_nickname",
                        "type": "text",
                        "label": tr("onigimon_nickname_label", "Nickname"),
                        "placeholder": tr("onigimon_nickname_placeholder", ""),
                        "bind": {"kind": "game", "key": "onigimon_nickname"},
                        "default": "",
                    },
                ],
            },
            {
                "id": "onigimon_scene",
                "title": tr("onigimon_scene_title", "Scene"),
                "layout": "designer_preview",
                "preview_kind": "onigimon_scene",
                "stage_side": False,
                "head_to_deck": True,
                "icon_colors_inline": False,
                "dynamic_keys": [],
                "sync_toggle_id": "",
                "sync_hidden_fields": [],
                "description": tr(
                    "onigimon_scene_desc",
                    "Everything below styles the deck-browser widget shown here.",
                ),
                "fields": [
                    {
                        "id": "g_onigimon_scene_color",
                        "type": "color_pair",
                        "label": tr("background_color", "Background"),
                        "bind": _conf_path("onigimon", "scene_background_color"),
                        "default": "#6ea96a",
                    },
                    {
                        "id": "g_onigimon_scene_image",
                        "type": "image",
                        "label": tr("background_image", "Background image"),
                        "folder": "onigimon_bg",
                        # Read back by gamification/onigimon.py as an
                        # addon-relative path; the page only handles the
                        # filename (see store's asset_dir).
                        "bind": dict(
                            _conf_path("onigimon", "scene_background_image"),
                            asset_dir="user_files/onigimon_backgrounds",
                        ),
                        "default": "",
                    },
                    {
                        "id": "g_onigimon_bottom_color",
                        "type": "color_pair",
                        "label": tr("onigimon_stats_panel", "Stats panel"),
                        "bind": _conf_path("onigimon", "scene_bottom_color"),
                        "default": "",
                        # Empty means "the widget's own shade"; the slot shows
                        # that shade rather than a blank swatch.
                        "static_fallback": {"light": "#efefec", "dark": "#2e2e2d"},
                    },
                    {
                        "id": "g_onigimon_scene_blur",
                        "type": "slider",
                        "label": tr("onigimon_blur_intensity", "Blur"),
                        "bind": _conf_path("onigimon", "scene_background_blur"),
                        "default": 9, "min": 0, "max": 40, "step": 1, "suffix": "px",
                    },
                    {
                        "id": "g_onigimon_scene_opacity",
                        "type": "slider",
                        "label": tr("background_opacity", "Opacity"),
                        "bind": _conf_path("onigimon", "scene_background_opacity"),
                        "default": 90, "min": 0, "max": 100, "step": 1, "suffix": "%",
                    },
                    {
                        "id": "g_onigimon_sprite_motion",
                        "type": "choice",
                        "label": tr("onigimon_sprite_mode_label", "Sprite mode"),
                        "bind": _conf_path("onigimon", "sprite_motion"),
                        "default": "static",
                        "head": True,
                        "options": [
                            {"value": "static", "label": tr("onigimon_sprite_static", "Static")},
                            {"value": "gif", "label": tr("onigimon_sprite_animated", "Animated")},
                        ],
                    },
                ],
            },
            {
                "id": "onigimon_difficulty",
                "title": tr("onigimon_difficulty_title", "Difficulty"),
                "fields": [
                    _note("g_onigimon_difficulty_note", "", tr("onigimon_difficulty_note", "")),
                    {
                        "id": "g_onigimon_difficulty",
                        "type": "game_choice",
                        "label": "",
                        "bind": _conf_path("onigimon", "difficulty"),
                        "default": "pikachu",
                        "options": [
                            {
                                "value": "bulbassaur", "label": "Bulbassaur",
                                "desc": tr("onigimon_diff_easy_desc", ""),
                                "image": _image("onigimon/bulbasaur_pixel.webp"),
                                "accent": "#4CAF50",
                            },
                            {
                                "value": "pikachu", "label": "Pikachu",
                                "desc": tr("onigimon_diff_normal_desc", ""),
                                "image": _image("onigimon/pikachu_pixel.webp"),
                                "accent": "#F2B705",
                            },
                            {
                                "value": "charizard", "label": "Charizard",
                                "desc": tr("onigimon_diff_hard_desc", ""),
                                "image": _image("onigimon/charizard_pixel.webp"),
                                "accent": "#E8562F",
                            },
                        ],
                    },
                ],
            },
            {
                # Wording only: the tone never changes what a notification is
                # about, just how kindly it says it. Copy lives in
                # translations.py, keyed `onigimon_tone_<message>_<tone>`.
                "id": "onigimon_tone",
                "title": tr("onigimon_tone_title", "Notification tone"),
                "fields": [
                    _note("g_onigimon_tone_note", "", tr("onigimon_tone_note", "")),
                    {
                        "id": "g_onigimon_tone",
                        "type": "game_choice",
                        "label": "",
                        "bind": _conf_path("onigimon", "notification_tone"),
                        "default": "herdier",
                        "options": [
                            {
                                "value": "lillipup", "label": "Lillipup",
                                "desc": tr("onigimon_tone_lillipup_desc", ""),
                                "image": _image("onigimon/lillipup_pixel.webp"),
                                "accent": "#D9A05B",
                            },
                            {
                                "value": "herdier", "label": "Herdier",
                                "desc": tr("onigimon_tone_herdier_desc", ""),
                                "image": _image("onigimon/herdier_pixel.webp"),
                                "accent": "#4A6FA5",
                            },
                            {
                                "value": "stoutland", "label": "Stoutland",
                                "desc": tr("onigimon_tone_stoutland_desc", ""),
                                "image": _image("onigimon/stoutland_pixel.webp"),
                                "accent": "#7A8794",
                            },
                        ],
                    },
                ],
            },
            {
                "id": "onigimon_bridge",
                "title": tr("onigimon_bridge_title", "Ankimon bridge"),
                "fields": [
                    _toggle("g_onigimon_ankimon_updates", tr("onigimon_bridge_toggle", ""),
                            ("onigimon", "allow_ankimon_updates"), True,
                            desc=tr("onigimon_bridge_note", "")),
                ],
            },
            {
                "id": "onigimon_credits",
                "title": tr("onigimon_credits_title", "Credits"),
                "fields": [
                    _note("g_onigimon_credits", "", tr("onigimon_credits_text", "")),
                ],
            },
        ],
    }


# ── page 4: Hexagon Land ──────────────────────────────────────────────────────




def _hexagon_page():
    return {
        "id": "hexagon_land",
        "legacy_name": "Hexagon Land",
        "title": tr("hexagon_land"),
        "icon": "hexagon_land.svg",
        "group": "games",
        "post_save": ["hexagon_land", "gamification"],
        "sections": [
            {
                "id": "hexagon_hero",
                "title": "",
                "fields": [
                    _game_hero_toggle(
                        "g_hexagon_enabled",
                        tr("hexagon_land"),
                        tr("hexagon_land_desc"),
                        ("hexagon_land", "enabled"),
                        _image("Hexagon_world.webp"),
                        ACCENTS["hexagon"],
                    ),
                    # The classic page pinned this alongside `enabled`; the only
                    # theme that exists, but the reader still expects the key.
                    _hidden("g_hexagon_theme", ("hexagon_land", "theme"), "island"),
                ],
            },
            {
                "id": "hexagon_builder",
                "title": tr("hexagon_builder_title"),
                "fields": [
                    _note(
                        "g_hexagon_builder_note", "",
                        tr("hexagon_builder_note"),
                    ),
                    _action("g_hexagon_open", tr("hexagon_land"), tr("hexagon_open_action"), "hexagon_open", button_icon="open"),
                    _action("g_hexagon_buy_coins", tr("hexland_hex_coins"), tr("hexagon_get_coins_action"), "hexagon_buy_coins", button_icon="coin"),
                ],
            },
            {
                "id": "hexagon_keys",
                "title": tr("hexagon_keys_title", "Keys of the Island"),
                "layout": "hexagon_keys",
                "description": tr(
                    "hexagon_keys_desc",
                    "Buy the keys to name your island. The name appears on the Hexagon "
                    "Land widget.",
                ),
                "fields": [
                    {
                        "id": "g_hexagon_island_name",
                        "type": "text",
                        "label": tr("hexagon_island_name", "Island name"),
                        "placeholder": tr("hexagon_island_name", "Island name"),
                        "bind": {"kind": "game", "key": "hexagon_island_name"},
                        "default": "",
                    },
                ],
            },
        ],
    }


# ── page 5: Bento Games ───────────────────────────────────────────────────────


def _bento_page():
    return {
        "id": "bento_games",
        "legacy_name": "Bento Games",
        "title": tr("bento_games_title"),
        "icon": "bento.svg",
        "group": "games",
        "description": tr("bento_games_desc"),
        "sections": [
            {
                "id": "bento_list",
                "title": "",
                "layout": "bento_games",
                "fields": [],
            },
        ],
    }


# ── page 6: Focus Dango ───────────────────────────────────────────────────────


def _focus_dango_page():
    conf = config.get_config()
    dango_conf = (conf.get("achievements", {}) or {}).get("focusDango", {}) or {}
    fallback = _message_values(
        dango_conf.get("message"),
        [tr("dont_give_up", ""), tr("stay_focused", "")],
    )
    messages = _message_values(dango_conf.get("messages"), fallback)

    return {
        "id": "focus_dango",
        "legacy_name": "Focus Dango",
        "title": tr("focus_dango", "Focus Dango"),
        "icon": "dango.svg",
        "group": "games",
        "post_save": ["gamification"],
        "sections": [
            {
                "id": "dango_hero",
                "title": "",
                "fields": [
                    _game_hero_toggle(
                        "g_dango_enabled",
                        tr("focus_dango", "Focus Dango"),
                        tr("dango_help_focus", ""),
                        ("achievements", "focusDango", "enabled"),
                        _image("dango.webp"),
                        ACCENTS["dango"],
                    ),
                ],
            },
            {
                "id": "dango_messages",
                "title": tr("focus_dango_messages", "Messages"),
                "fields": [
                    {
                        "id": "g_dango_messages",
                        "type": "message_list",
                        "label": "",
                        "desc": tr(
                            "message_editor_desc",
                            "Create one message per card. Add, reorder, or remove them "
                            "without worrying about line breaks.",
                        ),
                        "bind": _conf_path("achievements", "focusDango", "messages"),
                        "default": messages,
                        "accent": ACCENTS["dango"],
                    },
                ],
            },
            {
                "id": "dango_lock_mode",
                "title": tr("focus_dango_lock_mode", "Lock Mode"),
                "fields": [
                    _note("g_dango_lock_note", "", tr(
                        "focus_dango_lock_mode_desc",
                        "Keep the default mode light, or make Focus Dango stricter "
                        "during reviews.",
                    )),
                    _toggle(
                        "g_dango_self_sabotage",
                        tr("focus_dango_self_sabotage", "Self-Sabotage Mode"),
                        ("achievements", "focusDango", "self_sabotage"),
                        desc=tr(
                            "focus_dango_self_sabotage_desc",
                            "Aggressively blocks attempts to reach the rest of Anki "
                            "while reviewing.",
                        ),
                    ),
                ],
            },
        ],
    }


# ── page 7: Mochi Messages ────────────────────────────────────────────────────


def _mochi_page():
    conf = config.get_config()
    mochi_conf = conf.get("mochi_messages", {}) or {}
    messages = _message_values(mochi_conf.get("messages"), [
        tr("mochi_msg_1", ""), tr("mochi_msg_2", ""), tr("mochi_msg_3", ""),
        tr("mochi_msg_4", ""), tr("mochi_msg_5", ""), tr("mochi_msg_6", ""),
        tr("mochi_msg_7", ""),
    ])

    return {
        "id": "mochi_messages",
        "legacy_name": "Mochi Messages",
        "title": tr("mochi_messages_title", "Mochi Messages"),
        "icon": "mochi.svg",
        "group": "games",
        "post_save": ["mochi_messages", "gamification"],
        "sections": [
            {
                "id": "mochi_hero",
                "title": "",
                "fields": [
                    _game_hero_toggle(
                        "g_mochi_enabled",
                        tr("mochi_messages_title", "Mochi Messages"),
                        tr("mochi_cheer_on", ""),
                        ("mochi_messages", "enabled"),
                        _image("mochi_messenger.webp"),
                        ACCENTS["mochi"],
                    ),
                ],
            },
            {
                "id": "mochi_timing",
                "title": tr("settings", "Settings"),
                "fields": [
                    {
                        "id": "g_mochi_interval",
                        "type": "number",
                        "label": tr("show_message_every", "Show a message every"),
                        "bind": _conf_path("mochi_messages", "cards_interval"),
                        "default": 15, "min": 1, "max": 1000,
                        "suffix": tr("mochi_interval_suffix", "cards"),
                    },
                ],
            },
            {
                "id": "mochi_looks",
                "title": tr("mochi_looks_title", "Messenger Looks"),
                "layout": "designer_preview",
                "preview_kind": "mochi_message",
                "stage_side": True,
                "head_to_deck": True,
                "icon_colors_inline": False,
                "dynamic_keys": [],
                "sync_toggle_id": "",
                "sync_hidden_fields": [],
                "description": tr(
                    "mochi_looks_desc",
                    "Choose who delivers the messages, and how the notification text reads.",
                ),
                "fields": [
                    {
                        "id": "g_mochi_icon_choice",
                        "type": "choice",
                        "label": tr("mochi_source_label", "Messenger"),
                        "bind": _conf_path("mochi_messages", "icon_choice"),
                        "default": "mochi",
                        "options": [
                            {"value": "mochi", "label": tr("mochi_option_mochi", "Mochi")},
                            {"value": "custom", "label": tr("mochi_option_custom", "Custom")},
                        ],
                    },
                    {
                        "id": "g_mochi_custom_icon",
                        "type": "image",
                        "label": tr("mochi_custom_image_label", "Custom image"),
                        "desc": tr(
                            "mochi_image_hint_short",
                            "WebP, PNG, JPG or GIF — a square ~256×256 px image with a "
                            "transparent background looks best.",
                        ),
                        "folder": "mochi_icon",
                        # Stored as an addon-relative path, the shape
                        # gamification/mochi_messages.py reads.
                        "bind": dict(
                            _conf_path("mochi_messages", "custom_icon"),
                            asset_dir="user_files/mochi_messenger",
                        ),
                        "default": "",
                        # Picking an image is what "Custom" means, so choosing
                        # one selects that source in the same gesture.
                        "cascade": {"on": {"g_mochi_icon_choice": "custom"}},
                        "show_when": {"field": "g_mochi_icon_choice", "values": ["custom"]},
                    },
                    {
                        "id": "g_mochi_text_color",
                        "type": "color_pair",
                        "label": tr("mochi_message_color", "Message color"),
                        "bind": _conf_path("mochi_messages", "text_color"),
                        "default": "",
                        # web/notifications.css's own
                        # --onigiri-notification-text-{light,dark}.
                        "static_fallback": {"light": "#2c2c2c", "dark": "#ffffff"},
                    },
                    {
                        "id": "g_mochi_font",
                        "type": "font",
                        "label": tr("mochi_message_font", "Message font"),
                        "bind": _conf_path("mochi_messages", "font"),
                        "default": "system",
                    },
                    {
                        "id": "g_mochi_title_name",
                        "type": "text",
                        "label": tr("mochi_title_label", "Title text"),
                        "placeholder": tr("mochi_title_placeholder", "Mochi says…"),
                        "bind": _conf_path("mochi_messages", "title_name"),
                        "default": "",
                        "show_when": {"not": {"field": "g_mochi_hide_title", "values": [True]}},
                    },
                    _toggle("g_mochi_hide_title", tr("mochi_hide_title", "Hide notification title"),
                            ("mochi_messages", "hide_title")),
                ],
            },
            {
                "id": "mochi_message_list",
                "title": tr("mochi_messages_title", "Messages"),
                "fields": [
                    {
                        "id": "g_mochi_messages",
                        "type": "message_list",
                        "label": "",
                        "desc": tr(
                            "message_editor_desc",
                            "Create one message per card. Add, reorder, or remove them "
                            "without worrying about line breaks.",
                        ),
                        "bind": _conf_path("mochi_messages", "messages"),
                        "default": messages,
                        "accent": ACCENTS["mochi"],
                    },
                ],
            },
        ],
    }


def build_pages():
    """Every Games page, rebuilt on each dialog open so live game state (the
    Nook's level, Ankimon's status) is current."""
    return [
        _gamification_page(),
        _nook_page(),
        _onigimon_page(),
        _hexagon_page(),
        _bento_page(),
        _focus_dango_page(),
        _mochi_page(),
    ]
