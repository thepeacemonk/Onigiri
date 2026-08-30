from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from html import escape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from aqt import gui_hooks, mw
from aqt.qt import QDesktopServices, QDialog, QTimer, QUrl, QVBoxLayout
from aqt.webview import AnkiWebView

from .. import config
from ..translations import tr


BUY_HEX_COINS_URL = "https://buymeacoffee.com/peacemonk"
HEXLAND_GUIDE_URL = "https://onigiri-addon-guide.notion.site/Hexagon-Land-3a43d4f0321380c19e8adfe630ca9a40"
KEYS_OF_THE_ISLAND_COST = 5000
SANDBOX_MODE = False

# --- Island leveling -------------------------------------------------------
# Level is derived from the number of land hexagons the island has:
#     level = floor(sqrt(2 * lands))   <=>   lands to reach level L = ceil(L^2 / 2)
# This hits exactly 50 lands at level 10, and stays achievable forever: the
# land requirement is always finite and each level only asks for ~L more lands.
# New-land price scales with level but is capped, so expanding never becomes
# impossible no matter how high the level climbs.
HEXLAND_EXPAND_COST_BASE = 18
HEXLAND_EXPAND_COST_STEP = 5
HEXLAND_EXPAND_COST_CAP = 140

# (min level, translation key, default title) - highest matching threshold wins.
HEXLAND_LEVEL_TITLES = [
    (0, "hexland_rank_castaway", "Castaway"),
    (2, "hexland_rank_beachcomber", "Beachcomber"),
    (4, "hexland_rank_settler", "Settler"),
    (6, "hexland_rank_homesteader", "Homesteader"),
    (8, "hexland_rank_landkeeper", "Landkeeper"),
    (10, "hexland_rank_ruler", "Ruler of the Island"),
    (13, "hexland_rank_baron", "Isle Baron"),
    (16, "hexland_rank_warden", "Warden of the Archipelago"),
    (20, "hexland_rank_sovereign", "Sovereign of the Tides"),
    (25, "hexland_rank_legend", "Living Legend of the Isles"),
]


def hexland_level_from_lands(lands: int) -> int:
    return int(math.isqrt(max(0, 2 * int(lands or 0))))


def hexland_lands_for_level(level: int) -> int:
    level = max(0, int(level or 0))
    return (level * level + 1) // 2


def hexland_level_title(level: int) -> Tuple[str, str]:
    title_key, title = HEXLAND_LEVEL_TITLES[0][1], HEXLAND_LEVEL_TITLES[0][2]
    for threshold, key, name in HEXLAND_LEVEL_TITLES:
        if level >= threshold:
            title_key, title = key, name
    return title_key, title

TERRAIN_ITEMS = {
    "grass": {
        "label": "Grass",
        "sprite": "Land/tileGrass.png",
        "unlock": 0,
        "cost": {"coins": 15},
    },
    "sand": {
        "label": "Sand",
        "sprite": "Land/tileSand.png",
        "unlock": 25,
        "cost": {"coins": 15},
    },
    "dirt": {
        "label": "Dirt",
        "sprite": "Land/tileDirt.png",
        "unlock": 45,
        "cost": {"coins": 15},
    },
    "stone": {
        "label": "Stone",
        "sprite": "Land/tileStone.png",
        "unlock": 70,
        "cost": {"coins": 15},
    },
    "snow": {
        "label": "Snow",
        "sprite": "Land/tileSnow.png",
        "unlock": 130,
        "cost": {"coins": 15},
    },
    "magic": {
        "label": "Magic",
        "sprite": "Land/tileMagic.png",
        "unlock": 220,
        "cost": {"coins": 15},
    },
    "water": {
        "label": "Water",
        "sprite": "Land/tileWater.png",
        "unlock": 0,
        "cost": {"coins": 15},
    },
}

TERRAIN_GROUPS_BY_KEY = {
    "grass": "Grass",
    "terrain_land_001": "Grass",
    "terrain_land_003": "Grass",
    "water": "Water",
    "terrain_land_007": "Water",
    "terrain_land_008": "Lava",
    "terrain_land_019": "Lava",
    "sand": "Sand",
    "terrain_land_004": "Sand",
    "terrain_land_014": "Sand",
    "dirt": "Dirt",
    "terrain_land_006": "Dirt",
    "stone": "Stone",
    "terrain_land_009": "Stone",
    "terrain_land_010": "Stone",
    "terrain_land_011": "Stone",
    "terrain_land_021": "Stone",
    "terrain_land_022": "Stone",
    "snow": "Snow",
    "terrain_land_005": "Snow",
    "magic": "Magic",
    "terrain_land_002": "Magic",
}

TERRAIN_LABELS_BY_KEY = {
    "stone": "Dark Stone",
    "terrain_land_009": "Dark Stone",
    "terrain_land_010": "Rock land",
    "snow": "Shallow Stone",
    "terrain_land_011": "Shallow Stone",
    "terrain_land_019": "Pure Lava",
    "terrain_land_021": "Light Stone",
}

DELETED_TERRAIN_KEYS = {"terrain_land_023"}

DECOR_ITEMS = {
    "tree_green": {
        "label": "Green tree",
        "sprite": "Land/treeGreen_high.png",
        "kind": "tree",
        "cost": {"coins": 15},
        "offset": {"x": 19, "y": -68, "w": 27},
    },
    "pine_green": {
        "label": "Pine tree",
        "sprite": "Land/pineGreen_high.png",
        "kind": "tree",
        "cost": {"coins": 15},
        "offset": {"x": 18, "y": -60, "w": 30},
    },
    "flower_yellow": {
        "label": "Yellow flowers",
        "sprite": "Land/flowerYellow.png",
        "kind": "flower",
        "cost": {"coins": 15},
        "offset": {"x": 24, "y": 22, "w": 18},
    },
    "flower_blue": {
        "label": "Blue flowers",
        "sprite": "Land/flowerBlue.png",
        "kind": "flower",
        "cost": {"coins": 15},
        "offset": {"x": 24, "y": 22, "w": 18},
    },
    "rock_moss": {
        "label": "Moss rock",
        "sprite": "Land/rockStone_moss1.png",
        "kind": "rock",
        "cost": {"coins": 15},
        "offset": {"x": 14, "y": -11, "w": 36},
    },
}

BUILDING_ITEMS = {
    "cottage": {
        "label": "Cottage",
        "wall": "Buildings/woodDoorWindow.png",
        "roof": "Buildings/redRoofShort.png",
        "cost": {"coins": 15},
    },
    "tower": {
        "label": "Stone Tower",
        "wall": "Buildings/stoneDoorWindow.png",
        "roof": "Buildings/stoneRoofPointy.png",
        "cost": {"coins": 15},
    },
    "sand_house": {
        "label": "Sand house",
        "wall": "Buildings/sandDoorWindow.png",
        "roof": "Buildings/sandRoofStraight.png",
        "cost": {"coins": 15},
    },
    "castle": {
        "label": "Castle Keep",
        "wall": "Buildings/stoneDoorWindowBlinds.png",
        "roof": "Buildings/stoneRoofTall.png",
        "cost": {"coins": 15},
    },
}

BUILDING_PART_ITEMS = {
    "stone_wall": {
        "label": "Stone wall",
        "sprite": "Buildings/stoneDoorWindow.png",
        "cost": {"coins": 15},
    },
    "wood_wall": {
        "label": "Wood wall",
        "sprite": "Buildings/woodDoorWindow.png",
        "cost": {"coins": 15},
    },
    "sand_wall": {
        "label": "Sand wall",
        "sprite": "Buildings/sandDoorWindow.png",
        "cost": {"coins": 15},
    },
    "red_roof": {
        "label": "Red roof",
        "sprite": "Buildings/redRoofPointy.png",
        "cost": {"coins": 15},
    },
    "stone_roof": {
        "label": "Stone roof",
        "sprite": "Buildings/stoneRoofPointy.png",
        "cost": {"coins": 15},
    },
}

BUILDING_PART_OVERRIDES = {
    "part_buildings_035": {"label": "Window Wall", "group": "Dark Stone", "subgroup": "Walls", "order": 100},
    "part_buildings_036": {"label": "Door Wall", "group": "Dark Stone", "subgroup": "Walls", "order": 101},
    "stone_wall": {"label": "Corner Wall R", "group": "Dark Stone", "subgroup": "Walls", "order": 102},
    "part_buildings_029": {"label": "Corner Wall L", "group": "Dark Stone", "subgroup": "Walls", "order": 103},
    "part_stonedoorwindowblinds": {"label": "Corner Window Blinds R", "group": "Dark Stone", "subgroup": "Walls", "order": 104},
    "part_buildings_033": {"label": "Corner Window Blinds L", "group": "Dark Stone", "subgroup": "Walls", "order": 105},
    "part_buildings_031": {"label": "Stone Windows I", "group": "Dark Stone", "subgroup": "Walls", "order": 106},
    "part_buildings_034": {"label": "Stone Windows III", "group": "Dark Stone", "subgroup": "Walls", "order": 108},
    "part_buildings_037": {"label": "Stone Gate R", "group": "Dark Stone", "subgroup": "Walls", "order": 109},
    "part_buildings_038": {"label": "Stone Gate L", "group": "Dark Stone", "subgroup": "Walls", "order": 110},
    "part_buildings_039": {"label": "Stone Window-Door", "group": "Dark Stone", "subgroup": "Walls", "order": 111},
    "part_buildings_040": {"label": "Stone Door-Window", "group": "Dark Stone", "subgroup": "Walls", "order": 112},
    "part_buildings_041": {"label": "Stone Window-Blind-Door", "group": "Dark Stone", "subgroup": "Walls", "order": 113},
    "part_buildings_042": {"label": "Stone Window-Door-Blind", "group": "Dark Stone", "subgroup": "Walls", "order": 114},
    "part_buildings_021": {"label": "Rock Ring", "group": "Dark Stone", "subgroup": "Rings", "order": 120},

    "part_buildings_043": {"label": "Corner Wall R", "group": "Light Stone", "subgroup": "Walls", "order": 200},
    "part_buildings_044": {"label": "Corner Wall L", "group": "Light Stone", "subgroup": "Walls", "order": 201},
    "part_buildings_045": {"label": "Stone Windows I", "group": "Light Stone", "subgroup": "Walls", "order": 202},
    "part_buildings_046": {"label": "Corner Window Blinds R", "group": "Light Stone", "subgroup": "Walls", "order": 203},
    "part_buildings_047": {"label": "Corner Window Blinds L", "group": "Light Stone", "subgroup": "Walls", "order": 204},
    "part_buildings_048": {"label": "Stone Window Blinds", "group": "Light Stone", "subgroup": "Walls", "order": 205},
    "part_buildings_049": {"label": "Door Wall R", "group": "Light Stone", "subgroup": "Walls", "order": 206},
    "part_buildings_050": {"label": "Door Wall L", "group": "Light Stone", "subgroup": "Walls", "order": 207},
    "part_buildings_051": {"label": "Stone Gate R", "group": "Light Stone", "subgroup": "Walls", "order": 208},
    "part_buildings_052": {"label": "Stone Gate L", "group": "Light Stone", "subgroup": "Walls", "order": 209},
    "part_buildings_053": {"label": "Stone Window-Door", "group": "Light Stone", "subgroup": "Walls", "order": 210},
    "part_buildings_054": {"label": "Stone Door-Window", "group": "Light Stone", "subgroup": "Walls", "order": 211},
    "part_buildings_055": {"label": "Stone Window-Blind-Door", "group": "Light Stone", "subgroup": "Walls", "order": 212},
    "part_buildings_056": {"label": "Stone Door-Window-Blind", "group": "Light Stone", "subgroup": "Walls", "order": 213},
    "part_buildings_027": {"label": "Light Rock Roof I", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 220},
    "part_buildings_028": {"label": "Light Rock Roof II", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 221},
    "part_buildings_022": {"label": "Light Rock Ring", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 222},
    "stone_roof": {"label": "Light Rock Roof III", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 223},
    "part_stonerooftall": {"label": "Light Rock Roof IV", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 224},
    "part_buildings_020": {"label": "Light Rock Roof V", "group": "Light Stone", "subgroup": "Roof & Ring", "order": 225},

    "wood_wall": {"label": "Clay Windows I", "group": "Clay", "subgroup": "Walls", "order": 300},
    "part_buildings_057": {"label": "Clay Window L", "group": "Clay", "subgroup": "Walls", "order": 301},
    "part_buildings_058": {"label": "Clay Window R", "group": "Clay", "subgroup": "Walls", "order": 302},
    "part_buildings_060": {"label": "Clay Window L", "group": "Clay", "subgroup": "Walls", "order": 303},
    "part_buildings_061": {"group": "DELETE"},
    "part_buildings_062": {"group": "DELETE"},
    "part_buildings_063": {"label": "Door Wall R", "group": "Clay", "subgroup": "Walls", "order": 304},
    "part_buildings_064": {"label": "Door Wall L", "group": "Clay", "subgroup": "Walls", "order": 305},
    "part_buildings_065": {"label": "Clay Gate R", "group": "Clay", "subgroup": "Walls", "order": 306},
    "part_buildings_066": {"label": "Clay Gate L", "group": "Clay", "subgroup": "Walls", "order": 307},
    "part_buildings_067": {"label": "Clay Window-Door", "group": "Clay", "subgroup": "Walls", "order": 308},
    "part_buildings_068": {"label": "Clay Door-Window", "group": "Clay", "subgroup": "Walls", "order": 309},
    "part_buildings_069": {"group": "DELETE"},
    "part_buildings_070": {"group": "DELETE"},
    "part_buildings_001": {"label": "Clay Roof I", "group": "Clay", "subgroup": "Roof & Ring", "order": 320},
    "part_buildings_002": {"label": "Clay Roof II", "group": "Clay", "subgroup": "Roof & Ring", "order": 321},
    "part_buildings_005": {"label": "Clay Roof III", "group": "Clay", "subgroup": "Roof & Ring", "order": 322},
    "part_buildings_007": {"label": "Clay Roof IV", "group": "Clay", "subgroup": "Roof & Ring", "order": 323},
    "part_buildings_008": {"label": "Clay Roof V", "group": "Clay", "subgroup": "Roof & Ring", "order": 324},
    "part_buildings_023": {"label": "Clay Ring", "group": "Clay", "subgroup": "Roof & Ring", "order": 325},
    "red_roof": {"label": "Red Clay Roof I", "group": "Clay", "subgroup": "Roof & Ring", "order": 326},
    "part_redroofshort": {"label": "Red Clay Roof II", "group": "Clay", "subgroup": "Roof & Ring", "order": 327},
    "part_buildings_016": {"label": "Red Clay Roof III", "group": "Clay", "subgroup": "Roof & Ring", "order": 328},
    "part_buildings_019": {"label": "Red Clay Roof IV", "group": "Clay", "subgroup": "Roof & Ring", "order": 329},
    "part_buildings_026": {"label": "Red Clay Roof V", "group": "Clay", "subgroup": "Roof & Ring", "order": 330},

    "sand_wall": {"label": "Sand Window L", "group": "Sand", "subgroup": "Wall", "order": 400},
    "part_buildings_071": {"label": "Sand Window R", "group": "Sand", "subgroup": "Wall", "order": 401},
    "part_buildings_074": {"label": "Sand Window-Blind L", "group": "Sand", "subgroup": "Wall", "order": 402},
    "part_buildings_075": {"label": "Sand Window-Blind R", "group": "Sand", "subgroup": "Wall", "order": 403},
    "part_buildings_076": {"label": "Sand Window-Blinds", "group": "Sand", "subgroup": "Wall", "order": 404},
    "part_buildings_077": {"label": "Sand Door R", "group": "Sand", "subgroup": "Wall", "order": 405},
    "part_buildings_078": {"label": "Sand Door L", "group": "Sand", "subgroup": "Wall", "order": 406},
    "part_buildings_079": {"label": "Sand Gate R", "group": "Sand", "subgroup": "Wall", "order": 407},
    "part_buildings_080": {"label": "Sand Gate L", "group": "Sand", "subgroup": "Wall", "order": 408},
    "part_buildings_081": {"label": "Sand Window-Door", "group": "Sand", "subgroup": "Wall", "order": 409},
    "part_buildings_082": {"label": "Sand Door-Window", "group": "Sand", "subgroup": "Wall", "order": 410},
    "part_buildings_083": {"label": "Sand Window-Blind-Door", "group": "Sand", "subgroup": "Wall", "order": 411},
    "part_buildings_084": {"label": "Sand Door-Window-Blind", "group": "Sand", "subgroup": "Wall", "order": 412},
    "part_buildings_073": {"label": "Sand Window-Window", "group": "Sand", "subgroup": "Wall", "order": 413},
    "part_sandroofstraight": {"label": "Sand Roof I", "group": "Sand", "subgroup": "Roof & Ring", "order": 420},
    "part_buildings_003": {"label": "Sand Roof II", "group": "Sand", "subgroup": "Roof & Ring", "order": 421},
    "part_buildings_024": {"label": "Sand Roof III", "group": "Sand", "subgroup": "Roof & Ring", "order": 422},
    "part_buildings_004": {"label": "Sand Roof IV", "group": "Sand", "subgroup": "Roof & Ring", "order": 423},
    "part_buildings_006": {"label": "Sand Roof V", "group": "Sand", "subgroup": "Roof & Ring", "order": 424},
    "part_buildings_010": {"label": "Sand Roof VI", "group": "Sand", "subgroup": "Roof & Ring", "order": 425},
}

ERASE_ITEMS = {
    "tile": {"label": "Delete land", "hint": "Removes the whole tile and refunds its Hex Coins.", "icon": "delete"},
    "layer": {"label": "Remove top layer", "hint": "Takes one stacked terrain layer off.", "icon": "down"},
    "spot": {"label": "Clear spot", "hint": "Clears a single spot on a tile.", "icon": "cancel"},
}

INHABITANT_ITEMS = {
    "alien_green": {
        "label": "Green inhabitant",
        "sprite": "Land/alienGreen.png",
        "cost": {"coins": 15},
        "unlock_lands": 5,
        "offset": {"x": 22, "y": -8, "w": 26},
        "group": "Aliens",
    },
    "alien_blue": {
        "label": "Blue inhabitant",
        "sprite": "Land/alienBlue.png",
        "cost": {"coins": 15},
        "unlock_lands": 5,
        "offset": {"x": 22, "y": -8, "w": 26},
        "group": "Aliens",
    },
    "alien_pink": {
        "label": "Pink inhabitant",
        "sprite": "Auto/land_091.svg",
        "cost": {"coins": 15},
        "unlock_lands": 8,
        "offset": {"x": 22, "y": -8, "w": 26},
        "group": "Aliens",
    },
    "alien_yellow": {
        "label": "Yellow inhabitant",
        "sprite": "Auto/land_092.svg",
        "cost": {"coins": 15},
        "unlock_lands": 8,
        "offset": {"x": 22, "y": -8, "w": 26},
        "group": "Aliens",
    },
    "alien_beige": {
        "label": "Beige inhabitant",
        "sprite": "Auto/land_093.svg",
        "cost": {"coins": 15},
        "unlock_lands": 8,
        "offset": {"x": 22, "y": -8, "w": 26},
        "group": "Aliens",
    },
    "dango_inhabitant": {
        "label": "Dango",
        "sprite": "dango_inhabitant.svg",
        "cost": {"coins": 15},
        "unlock_lands": 15,
        "offset": {"x": 20, "y": -12, "w": 26},
        "group": "Onigiri Fam",
    },
    "mochi_inhabitant": {
        "label": "Mochi",
        "sprite": "mochi_inhabitant.svg",
        "cost": {"coins": 15},
        "unlock_lands": 15,
        "offset": {"x": 20, "y": -12, "w": 26},
        "group": "Onigiri Fam",
    },
    "nigiri_inhabitant": {
        "label": "Nigiri",
        "sprite": "nigiri_inhabitant.svg",
        "cost": {"coins": 15},
        "unlock_lands": 15,
        "offset": {"x": 20, "y": -12, "w": 26},
        "group": "Onigiri Fam",
    },
    "onigi_alien": {
        "label": "Onigiri San",
        "sprite": "onigiri_san.svg",
        "cost": {"coins": 15},
        "unlock_lands": 15,
        "offset": {"x": 20, "y": -12, "w": 26},
        "group": "Onigiri Fam",
    },
    "pikachu_inhabitant": {
        "label": "Pikachu",
        "sprite": "pikachu_inhabitant.svg",
        "cost": {"coins": 15},
        "unlock_lands": 15,
        "offset": {"x": 20, "y": -12, "w": 26},
        "group": "Onigiri Fam",
    },
}

RESOURCE_KEYS = ("wood", "stone", "sand", "crystal")
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))
SPOT_KEYS = (
    "top_left",
    "top_right",
    "middle_left",
    "center",
    "middle_right",
    "bottom_left",
    "bottom_right",
)
LEGACY_SPOT_KEYS = {
    "top": "top_left",
    "upper_left": "top_left",
    "upper_right": "top_right",
    "left": "middle_left",
    "right": "middle_right",
    "lower_left": "bottom_left",
    "lower_right": "bottom_right",
    "bottom": "bottom_left",
}
SPOT_DELTAS = {
    "top_left": {"x": -11, "y": -12},
    "top_right": {"x": 11, "y": -12},
    "middle_left": {"x": -19, "y": 0},
    "center": {"x": 0, "y": 4},
    "middle_right": {"x": 19, "y": 0},
    "bottom_left": {"x": -11, "y": 14},
    "bottom_right": {"x": 11, "y": 14},
}
SPOT_POINTS = {
    "top_left": {"x": 22, "y": 20},
    "top_right": {"x": 44, "y": 20},
    "middle_left": {"x": 14, "y": 32},
    "center": {"x": 33, "y": 32},
    "middle_right": {"x": 52, "y": 32},
    "bottom_left": {"x": 22, "y": 46},
    "bottom_right": {"x": 44, "y": 46},
}
LAND_LEVEL_STEP = 24
LAND_SIDE_STEP = 24
BUILDING_BASE_OFFSET = 28
BUILDING_WALL_NUDGE = 4
BUILDING_LEVEL_STEP = 24
BUILDING_ROOF_NUDGE = 68
BUILDING_ROOF_X_NUDGE = 0
BUILDING_ROOF_Y_NUDGE = 0.0

SPRITE_SHEET_SIZES = {
    "land": (850, 640),
    "buildings": (1040, 590),
}

# Stable sprite ids from the old PNG catalog, now mapped to crops in the SVG sheets.
SPRITE_VIEWS = {
    "Land/tileGrass.png": ("land", 10, 109, 65, 89),
    "Land/tileSand.png": ("land", 235, 109, 65, 89),
    "Land/tileDirt.png": ("land", 385, 109, 65, 89),
    "Land/tileStone.png": ("land", 610, 109, 65, 89),
    "Land/tileSnow.png": ("land", 310, 109, 65, 89),
    "Land/tileMagic.png": ("land", 85, 109, 65, 89),
    "Land/tileWater.png": ("land", 460, 109, 65, 89),
    "Land/treeGreen_high.png": ("land", 394, 422, 27, 107),
    "Land/pineGreen_high.png": ("land", 354, 442, 27, 87),
    "Land/flowerYellow.png": ("land", 210, 504, 11.6, 10.6),
    "Land/flowerBlue.png": ("land", 300, 504, 11.6, 10.6),
    "Land/rockStone_moss1.png": ("land", 90, 305, 55, 62),
    "Land/treeCactus_2.png": ("land", 554, 486, 27, 43),
    "Land/alienGreen.png": ("land", 25, 571, 40, 67),
    "Land/alienBlue.png": ("land", 85, 571, 40, 67),
    "Buildings/woodDoorWindow.png": ("buildings", 150, 399, 65, 90),
    "Buildings/redRoofShort.png": ("buildings", 300, 126, 66, 68),
    "Buildings/redRoofPointy.png": ("buildings", 0, 100, 66, 92),
    "Buildings/stoneDoorWindow.png": ("buildings", 75, 201, 65, 90),
    "Buildings/stoneDoorWindowBlinds.png": ("buildings", 225, 201, 65, 90),
    "Buildings/stoneWindowBlinds.png": ("buildings", 866, 75, 18, 25),
    "Buildings/stoneGateLeft.png": ("buildings", 1013, 77, 23, 27),
    "Buildings/stoneRoofPointy.png": ("buildings", 375, 101, 66, 93),
    "Buildings/stoneRoofTall.png": ("buildings", 525, 103, 66, 93),
    "Buildings/sandDoorWindow.png": ("buildings", 75, 498, 65, 90),
    "Buildings/sandRoofStraight.png": ("buildings", 675, 28, 66, 68),
}

AUTO_SPRITE_RE = re.compile(r"^Auto/(land|buildings)_(\d{3})\.svg$")
AUTO_TREE_INDICES = set(range(46, 51)) | set(range(59, 64)) | set(range(80, 89))
AUTO_FLOWER_INDICES = set(range(75, 79))
AUTO_ROCK_INDICES = set(range(33, 45)) | set(range(71, 75))
AUTO_GRASS_INDICES = set(range(51, 54)) | set(range(64, 67))
AUTO_NATURE_NAMES = {
    24: "Lime ground patch",
    25: "Purple ground patch",
    26: "Amber ground patch",
    27: "Ivory ground patch",
    28: "Frost ground patch",
    29: "Clay ground patch",
    30: "Aqua ground patch",
    31: "Sunset ground patch",
    32: "Slate ground patch",
    54: "Lime hill",
    55: "Purple hill",
    56: "Ivory hill",
    57: "Aqua ridge",
    67: "Amber hill",
    68: "Frost hill",
    69: "Clay hill",
    70: "Sunset ridge",
}
AUTO_NATURE_OVERRIDES = {
    33: {"kind": "decor", "label": "Rock ground patch", "group": "Others"},
    43: {"kind": "decor", "label": "Rock ground patch", "group": "Others"},
    54: {"kind": "decor", "label": "Lime hill", "group": "Hills"},
    55: {"kind": "decor", "label": "Magic hill", "group": "Hills"},
    56: {"kind": "decor", "label": "Ivory Hill", "group": "Hills"},
    57: {"kind": "decor", "label": "Aqua Ridge", "group": "Ridges"},
    67: {"kind": "decor", "label": "Red Sand hill", "group": "Hills"},
    68: {"kind": "decor", "label": "Frost hill", "group": "Hills"},
    69: {"kind": "decor", "label": "Sand hill", "group": "Hills"},
    70: {"kind": "decor", "label": "Red Sand Ridge", "group": "Ridges"},
    73: {"kind": "decor", "label": "Rock ground patch", "group": "Others"},
}
_AUTO_SPRITE_VIEWS: Optional[Dict[str, Tuple[str, float, float, float, float]]] = None
_DETECTED_SHEET_VIEWS: Dict[str, List[Tuple[str, float, float, float, float]]] = {}
_SHEET_SVG_PARTS: Dict[str, Tuple[Dict[str, str], List[Tuple[Tuple[float, float, float, float], str]]]] = {}
_CROPPED_SVG_URLS: Dict[Tuple[str, float, float, float, float], str] = {}


@dataclass
class HexagonLandState:
    hex_coins: int = 75
    pending_hex_coins: int = 0
    hex_coin_fraction: float = 0.0
    materials: Dict[str, int] = field(default_factory=lambda: {"wood": 8, "stone": 3, "sand": 2, "crystal": 0})
    pending_materials: Dict[str, int] = field(default_factory=dict)
    tiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    island_name: str = "Hexagon Land"
    keys_of_the_island: bool = False
    lifetime_reviews: int = 0
    today_reviews: int = 0
    current_streak: int = 0
    last_study_day: str = ""
    last_message: str = ""
    created_at: str = ""
    updated_at: str = ""
    widget_offset_x: float = 0.0
    widget_offset_y: float = 0.0
    widget_scale: float = 0.0

    def __post_init__(self) -> None:
        try:
            self.hex_coin_fraction = float(self.hex_coin_fraction or 0.0)
        except Exception:
            self.hex_coin_fraction = 0.0
        if not isinstance(self.materials, dict):
            self.materials = {}
        for key in RESOURCE_KEYS:
            self.materials.setdefault(key, 0)
        if not isinstance(self.tiles, dict) or not self.tiles:
            self.tiles = _starter_tiles()
        for tile in self.tiles.values():
            if not isinstance(tile.get("height"), int):
                tile["height"] = max(1, int(tile.get("height", 1) or 1))
            if not isinstance(tile.get("parts"), list):
                tile["parts"] = []
            _normalize_tile_spots(tile)
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

def _anki_today() -> date:
    try:
        from aqt import mw
        if mw and mw.col:
            day_cutoff = getattr(mw.col.sched, "day_cutoff", 0)
            if day_cutoff > 0:
                return datetime.fromtimestamp(day_cutoff - 86400).date()
    except Exception:
        pass
    return date.today()

def _starter_tiles() -> Dict[str, Dict[str, Any]]:
    return {
        "0,0": {"terrain": "grass", "decor": "flower_yellow", "building": "cottage"},
        "1,0": {"terrain": "grass", "decor": "tree_green"},
        "-1,0": {"terrain": "grass", "decor": "pine_green"},
        "0,1": {"terrain": "sand"},
        "0,-1": {"terrain": "grass", "decor": "flower_blue"},
        "1,-1": {"terrain": "stone"},
        "-1,1": {"terrain": "water"},
    }


def _coord_key(q: int, r: int) -> str:
    return f"{int(q)},{int(r)}"


def _parse_coord(key: str) -> Tuple[int, int]:
    q, r = key.split(",", 1)
    return int(q), int(r)


def _normalize_spot_key(value: Any) -> str:
    spot = str(value or "center")
    spot = LEGACY_SPOT_KEYS.get(spot, spot)
    return spot if spot in SPOT_KEYS else "center"


def _is_center_only_tree(item: Dict[str, Any], item_key: str = "") -> bool:
    text = f"{item_key} {item.get('kind', '')} {item.get('label', '')} {item.get('sprite', '')}".lower()
    return "rock" in text or (("tree" in text or "pine" in text) and "cactus" not in text)


def _placement_spot_for_item(item: Dict[str, Any], item_key: str, requested_spot: Any) -> str:
    if _is_center_only_tree(item, item_key):
        return "center"
    return _normalize_spot_key(requested_spot)


def _normalize_tile_spots(tile: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    raw_spots = tile.get("spots")
    spots: Dict[str, Dict[str, str]] = {}
    if isinstance(raw_spots, dict):
        for spot_key, entry in raw_spots.items():
            spot = _normalize_spot_key(spot_key)
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "")
            item = str(entry.get("item") or "")
            if category in {"decor", "inhabitant"} and item:
                if category == "decor" and "rock" in item.lower():
                    spot = "center"
                spots.setdefault(spot, {"category": category, "item": item})

    legacy_entries = [
        ("decor", str(tile.pop("decor", "") or "")),
        ("inhabitant", str(tile.pop("inhabitant", "") or "")),
    ]
    for category, item in legacy_entries:
        if not item:
            continue
        item_text = item.lower()
        preferred_spot = "center" if "rock" in item_text or (("tree" in item_text or "pine" in item_text) and "cactus" not in item_text) else ""
        if preferred_spot and preferred_spot not in spots:
            spots[preferred_spot] = {"category": category, "item": item}
            continue
        for spot in SPOT_KEYS:
            if spot not in spots:
                spots[spot] = {"category": category, "item": item}
                break
    tile["spots"] = spots
    return spots


def _spot_anchor_role(item: Dict[str, Any], category: str) -> str:
    if category == "inhabitant":
        return "foot"
    text = f"{item.get('kind', '')} {item.get('label', '')} {item.get('sprite', '')}".lower()
    if any(word in text for word in ("tree", "pine", "cactus")):
        return "foot"
    return "center"


def _spot_vertical_nudge(item: Dict[str, Any], category: str) -> int:
    if category != "decor":
        return 0
    text = f"{item.get('kind', '')} {item.get('label', '')} {item.get('sprite', '')}".lower()
    if ("tree" in text or "pine" in text) and "cactus" not in text:
        return 6
    return 0


def _spot_render_offset(item: Dict[str, Any], spot: str, category: str) -> Dict[str, Any]:
    point = SPOT_POINTS[_normalize_spot_key(spot)]
    offset = item.get("offset", {})
    width = int(offset.get("w", 26 if category == "inhabitant" else 30)) if isinstance(offset, dict) else 30
    source_w, source_h = _sprite_size(str(item.get("sprite", "")))
    height = int(round(source_h * (width / max(1, source_w))))
    x = int(round(point["x"] - width / 2))
    if _spot_anchor_role(item, category) == "foot":
        y = int(round(point["y"] - height))
    else:
        y = int(round(point["y"] - height / 2))
    y += _spot_vertical_nudge(item, category)
    return {"x": x, "y": y, "w": width, "h": height}


def _spot_depth(spot: str) -> int:
    point = SPOT_POINTS[_normalize_spot_key(spot)]
    return 30 + int(round(point["y"]))


def _spot_entries(tile: Dict[str, Any]) -> List[Tuple[str, Dict[str, str]]]:
    spots = _normalize_tile_spots(tile)
    return [(spot, spots[spot]) for spot in SPOT_KEYS if spot in spots]


def _addon_package() -> str:
    try:
        return mw.addonManager.addonFromModule(__name__)
    except Exception:
        return "1011095603"


def _addon_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sheet_file_path(sheet: str) -> str:
    return os.path.join(_addon_root(), "system_files", "gamification_images", "hexagon_land", f"{sheet}.svg")


def _path_bbox(path_data: str) -> Optional[Tuple[float, float, float, float]]:
    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path_data)]
    if len(numbers) < 2:
        return None
    points = list(zip(numbers[0::2], numbers[1::2]))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _boxes_overlap(first: Tuple[float, float, float, float], second: Tuple[float, float, float, float], pad: float = 1.0) -> bool:
    return not (
        first[2] + pad < second[0]
        or second[2] + pad < first[0]
        or first[3] + pad < second[1]
        or second[3] + pad < first[1]
    )


def _union_box(first: Tuple[float, float, float, float], second: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return min(first[0], second[0]), min(first[1], second[1]), max(first[2], second[2]), max(first[3], second[3])


def _detected_sheet_views(sheet: str) -> List[Tuple[str, float, float, float, float]]:
    cached = _DETECTED_SHEET_VIEWS.get(sheet)
    if cached is not None:
        return cached
    try:
        root = ET.parse(_sheet_file_path(sheet)).getroot()
    except Exception as exc:
        print(f"Onigiri: Error reading Hexagon Land SVG sheet {sheet}: {exc}")
        _DETECTED_SHEET_VIEWS[sheet] = []
        return []

    boxes: List[Tuple[float, float, float, float]] = []
    for element in root.iter():
        if not str(element.tag).endswith("path"):
            continue
        bbox = _path_bbox(element.attrib.get("d", ""))
        if bbox:
            boxes.append(bbox)
    parents = list(range(len(boxes)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(boxes)):
        for right in range(left + 1, len(boxes)):
            if _boxes_overlap(boxes[left], boxes[right]):
                join(left, right)

    components: Dict[int, Tuple[float, float, float, float]] = {}
    for index, box in enumerate(boxes):
        root_index = find(index)
        components[root_index] = _union_box(components[root_index], box) if root_index in components else box

    sheet_width, sheet_height = SPRITE_SHEET_SIZES[sheet]
    views: List[Tuple[str, float, float, float, float]] = []
    for x1, y1, x2, y2 in components.values():
        if x2 - x1 < 4 or y2 - y1 < 4:
            continue
        x1 = max(0.0, x1)
        y1 = max(0.0, y1)
        x2 = min(float(sheet_width), x2)
        y2 = min(float(sheet_height), y2)
        views.append((sheet, round(x1, 2), round(y1, 2), round(x2 - x1, 2), round(y2 - y1, 2)))
    views.sort(key=lambda view: (view[2], view[1]))
    _DETECTED_SHEET_VIEWS[sheet] = views
    return views


def _auto_sprite_views() -> Dict[str, Tuple[str, float, float, float, float]]:
    global _AUTO_SPRITE_VIEWS
    if _AUTO_SPRITE_VIEWS is None:
        views: Dict[str, Tuple[str, float, float, float, float]] = {}
        for sheet in SPRITE_SHEET_SIZES:
            for index, view in enumerate(_detected_sheet_views(sheet), 1):
                views[f"Auto/{sheet}_{index:03d}.svg"] = view
        _AUTO_SPRITE_VIEWS = views
    return _AUTO_SPRITE_VIEWS


def _view_box(view: Tuple[str, float, float, float, float]) -> Tuple[float, float, float, float]:
    return float(view[1]), float(view[2]), float(view[1]) + float(view[3]), float(view[2]) + float(view[4])


def _view_iou(first: Tuple[str, float, float, float, float], second: Tuple[str, float, float, float, float]) -> float:
    if first[0] != second[0]:
        return 0.0
    ax1, ay1, ax2, ay2 = _view_box(first)
    bx1, by1, bx2, by2 = _view_box(second)
    overlap_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    overlap_area = overlap_w * overlap_h
    if overlap_area <= 0:
        return 0.0
    first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return overlap_area / max(1.0, first_area + second_area - overlap_area)


def _is_legacy_view(view: Tuple[str, float, float, float, float]) -> bool:
    return any(_view_iou(view, legacy_view) > 0.65 for legacy_view in SPRITE_VIEWS.values())


def _is_land_tile_view(view: Tuple[str, float, float, float, float]) -> bool:
    _, _, y, width, height = view
    return 58 <= width <= 70 and 70 <= height <= 96 and y < 300


def _is_land_person_view(view: Tuple[str, float, float, float, float]) -> bool:
    _, _, y, width, height = view
    return y >= 560 and 34 <= width <= 45 and 55 <= height <= 75


def _is_building_roof_view(view: Tuple[str, float, float, float, float]) -> bool:
    sheet, _, y, width, height = view
    return sheet == "buildings" and y < 200 and width >= 58 and height >= 60


def _display_number(value: float) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _legacy_asset_url(path: str) -> str:
    return f"/_addons/{_addon_package()}/system_files/gamification_images/hexagon_land/{path}"


def _sheet_url(sheet: str) -> str:
    return f"/_addons/{_addon_package()}/system_files/gamification_images/hexagon_land/{sheet}.svg"


def _sheet_svg_parts(sheet: str) -> Tuple[Dict[str, str], List[Tuple[Tuple[float, float, float, float], str]]]:
    cached = _SHEET_SVG_PARTS.get(sheet)
    if cached is not None:
        return cached
    try:
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        root = ET.parse(_sheet_file_path(sheet)).getroot()
    except Exception as exc:
        print(f"Onigiri: Error reading Hexagon Land SVG sheet {sheet}: {exc}")
        _SHEET_SVG_PARTS[sheet] = ({}, [])
        return _SHEET_SVG_PARTS[sheet]

    defs_by_id: Dict[str, str] = {}
    paths: List[Tuple[Tuple[float, float, float, float], str]] = []
    for element in root.iter():
        tag = str(element.tag)
        if tag.endswith("linearGradient") or tag.endswith("radialGradient"):
            element_id = element.attrib.get("id")
            if element_id:
                defs_by_id[element_id] = ET.tostring(element, encoding="unicode")
        elif tag.endswith("path"):
            bbox = _path_bbox(element.attrib.get("d", ""))
            if bbox:
                paths.append((bbox, ET.tostring(element, encoding="unicode")))
    _SHEET_SVG_PARTS[sheet] = (defs_by_id, paths)
    return _SHEET_SVG_PARTS[sheet]


def _cropped_svg_url(view: Tuple[str, float, float, float, float]) -> str:
    sheet, x, y, width, height = view
    cache_key = (sheet, float(x), float(y), float(width), float(height))
    cached = _CROPPED_SVG_URLS.get(cache_key)
    if cached:
        return cached
    defs_by_id, paths = _sheet_svg_parts(sheet)
    crop_box = (float(x), float(y), float(x) + float(width), float(y) + float(height))
    selected_paths = [
        markup
        for bbox, markup in paths
        if _boxes_overlap(bbox, crop_box, pad=0.25)
    ]
    used_defs = sorted(set(re.findall(r"url\(#([^)]+)\)", "\n".join(selected_paths))))
    defs_markup = "".join(defs_by_id[def_id] for def_id in used_defs if def_id in defs_by_id)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_display_number(width)}" '
        f'height="{_display_number(height)}" viewBox="0 0 {_display_number(width)} {_display_number(height)}">'
        f'<defs>{defs_markup}</defs>'
        f'<g transform="translate(-{_display_number(x)} -{_display_number(y)})">'
        f'{"".join(selected_paths)}</g></svg>'
    )
    url = "data:image/svg+xml;charset=utf-8," + quote(svg, safe="(),/:;=")
    _CROPPED_SVG_URLS[cache_key] = url
    return url


def _asset_ref(path: str) -> Dict[str, Any]:
    view = SPRITE_VIEWS.get(path) or _auto_sprite_views().get(path)
    if view:
        sheet, x, y, width, height = view
        return {
            "kind": "image",
            "url": _cropped_svg_url(view),
            "sourceX": x,
            "sourceY": y,
            "width": width,
            "height": height,
        }
    w, h = _sprite_size(path)
    return {"kind": "image", "url": _legacy_asset_url(path), "width": w, "height": h}


def _sprite_html(asset: Dict[str, Any], css_class: str, x: float, y: float, width: float, attrs: str = "", style_extra: str = "") -> str:
    style = f"left:{x}px;top:{y}px;width:{width}px;overflow:hidden;{style_extra}"
    if asset.get("kind") == "svgSprite":
        source_x = float(asset.get("sourceX", 0))
        source_y = float(asset.get("sourceY", 0))
        return (
            f'<svg class="{css_class}" {attrs} viewBox="{escape(str(asset["viewBox"]))}" '
            f'width="{escape(_display_number(float(asset["width"])))}" height="{escape(_display_number(float(asset["height"])))}" '
            f'overflow="hidden" preserveAspectRatio="xMidYMid meet" style="{style}" aria-hidden="true">'
            f'<image href="{escape(str(asset["sheet"]))}" x="-{escape(_display_number(source_x))}" '
            f'y="-{escape(_display_number(source_y))}" width="{int(asset["sheetWidth"])}" '
            f'height="{int(asset["sheetHeight"])}"></image></svg>'
        )
    return f'<img class="{css_class}" {attrs} src="{escape(str(asset.get("url", "")))}" style="{style}">'


def _profile_name() -> str:
    try:
        return mw.pm.name or "default"
    except Exception:
        return "default"


def _asset_file_names(folder: str) -> List[str]:
    base = os.path.join(_addon_root(), "system_files", "gamification_images", "hexagon_land", folder)
    try:
        return sorted(name for name in os.listdir(base) if name.lower().endswith(".png"))
    except Exception:
        return []


def _asset_path(folder: str, filename: str) -> str:
    return os.path.join(_addon_root(), "system_files", "gamification_images", "hexagon_land", folder, filename)


def _png_size(folder: str, filename: str) -> Tuple[int, int]:
    key = f"{folder}/{filename}" if folder else filename
    view = SPRITE_VIEWS.get(key) or _auto_sprite_views().get(key)
    if view:
        return int(view[3]), int(view[4])
    try:
        path = _asset_path(folder, filename)
        if filename.lower().endswith(".svg"):
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read(1024)
            w_match = re.search(r'width="(\d+(?:\.\d+)?)"', content)
            h_match = re.search(r'height="(\d+(?:\.\d+)?)"', content)
            if w_match and h_match:
                return int(round(float(w_match.group(1)))), int(round(float(h_match.group(1))))
            viewbox_match = re.search(r'viewBox="[^"]*\s+[^"]*\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"', content)
            if viewbox_match:
                return int(round(float(viewbox_match.group(1)))), int(round(float(viewbox_match.group(2))))
        else:
            with open(path, "rb") as handle:
                header = handle.read(24)
            if header[:8] == b"\x89PNG\r\n\x1a\n":
                return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    except Exception:
        pass
    return 32, 32


def _sprite_size(sprite: str) -> Tuple[int, int]:
    view = SPRITE_VIEWS.get(sprite) or _auto_sprite_views().get(sprite)
    if view:
        return max(1, int(round(float(view[3])))), max(1, int(round(float(view[4]))))
    folder, filename = os.path.split(sprite)
    return _png_size(folder, filename)


def _label_from_filename(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem).replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in words.split())


def _key_from_path(prefix: str, filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    key = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return f"{prefix}_{key}"


def _auto_key(prefix: str, sprite_path: str) -> str:
    match = AUTO_SPRITE_RE.match(sprite_path)
    if not match:
        return _key_from_path(prefix, os.path.basename(sprite_path))
    sheet, index = match.groups()
    return f"{prefix}_{sheet}_{index}"


def _auto_label(prefix: str, sprite_path: str) -> str:
    match = AUTO_SPRITE_RE.match(sprite_path)
    if not match:
        return _label_from_filename(os.path.basename(sprite_path))
    _, index_str = match.groups()
    index = int(index_str)
    
    if prefix == "Terrain":
        terrains = {
            1: "Light Grass",
            2: "Purple Magic",
            3: "Autumn Grass",
            4: "Light Sand",
            5: "Glacier Ice",
            6: "Light Dirt",
            7: "Shallow Water",
            8: "Lava",
            9: "Stone",
            10: "Snowy Dirt",
            11: "Snow",
            12: "Deep Water",
            13: "Dark Water",
            14: "Desert Sand",
            15: "Dark Grass",
            16: "Swamp",
            17: "Mud",
            18: "Dark Dirt",
            19: "Red Sand",
            20: "Volcanic Rock",
            21: "White Stone",
            22: "Dark Stone",
            23: "Cobblestone",
            24: "Gravel",
            25: "Basalt"
        }
        if index in terrains:
            return tr(f"hexland_{terrains[index].lower().replace(' ', '_')}", terrains[index])
        
        fallback_names = ["Mossy Stone", "Cracked Earth", "Frozen Lake", "Oasis Water", "Burnt Grass", "Ash", "Limestone", "Sandstone"]
        fallback = fallback_names[index % len(fallback_names)]
        return tr(f"hexland_{fallback.lower().replace(' ', '_')}", fallback)
        
    if prefix == "Roof Sprite":
        names = ["Red Roof", "Stone Roof", "Wood Roof", "Sand Roof", "Straw Roof", "Dark Roof", "Blue Roof", "Green Roof", "Pointed Roof", "Flat Roof", "Sloped Roof", "Dome Roof", "Thatched Roof", "Tile Roof", "Slate Roof"]
        name = names[index % len(names)]
        translated = tr(f"hexland_{name.lower().replace(' ', '_')}", name)
        return f"{translated} ({index})"
        
    if prefix == "Building Sprite":
        names = ["Stone Wall", "Wood Wall", "Sand Wall", "Brick Wall", "Plank Wall", "Window Wall", "Door Wall", "Pillar", "Archway", "Tower Wall", "Castle Wall", "Cottage Wall", "Fortress Wall", "Gate Wall", "Corner Wall"]
        name = names[index % len(names)]
        translated = tr(f"hexland_{name.lower().replace(' ', '_')}", name)
        return f"{translated} ({index})"
        
    if prefix == "Nature Decor":
        return f"{tr('hexland_nature_decor', 'Nature decor')} ({index})"

    return f"{prefix} {index}"


def _auto_sprite_index(sprite_path: str) -> Optional[int]:
    match = AUTO_SPRITE_RE.match(sprite_path)
    if not match:
        return None
    return int(match.group(2))


def _auto_nature_info(sprite_path: str) -> Dict[str, str]:
    index = _auto_sprite_index(sprite_path)
    if index is None:
        index = 0
    override = AUTO_NATURE_OVERRIDES.get(index)
    if override:
        label = str(override.get("label", "Nature decor"))
        key = "hexland_" + label.lower().replace(" ", "_")
        return {
            "kind": str(override.get("kind", "decor")),
            "label": tr(key, label),
            "group": str(override.get("group", "Others")),
        }
    named_decor = AUTO_NATURE_NAMES.get(index)
    if named_decor:
        key = "hexland_" + named_decor.lower().replace(" ", "_")
        return {"kind": "decor", "label": tr(key, named_decor), "group": "Others"}
        
    if index in AUTO_TREE_INDICES:
        names = ["Pine Tree", "Oak Tree", "Birch Tree", "Maple Tree", "Cedar Tree", "Spruce Tree", "Elm Tree", "Willow Tree", "Ash Tree", "Cherry Tree", "Poplar Tree", "Fir Tree", "Redwood Tree", "Cactus", "Palm Tree", "Baobab Tree", "Bamboo", "Acacia Tree", "Sequoia Tree", "Cypress Tree", "Mahogany Tree", "Walnut Tree", "Chestnut Tree", "Sycamore Tree", "Alder Tree"]
        name = names[index % len(names)]
        return {"kind": "tree", "label": tr(f"hexland_{name.lower().replace(' ', '_')}", name), "group": "Trees"}
    if index in AUTO_FLOWER_INDICES:
        names = ["Yellow Tulip", "Red Rose", "Blue Lily", "Purple Orchid", "White Daisy", "Pink Peony", "Orange Marigold", "Violet Petunia", "Red Carnation", "Blue Iris", "Yellow Daffodil", "Pink Lotus"]
        name = names[index % len(names)]
        return {"kind": "flower", "label": tr(f"hexland_{name.lower().replace(' ', '_')}", name), "group": "Flowers"}
    if index in AUTO_ROCK_INDICES:
        names = ["Granite Rock", "Mossy Rock", "Obsidian Rock", "Limestone Rock", "Sandstone Rock", "Basalt Rock", "Slate Rock", "Quartz Rock", "Marble Rock", "Pumice Rock"]
        name = names[index % len(names)]
        return {"kind": "rock", "label": tr(f"hexland_{name.lower().replace(' ', '_')}", name), "group": "Rocks"}
    if index in AUTO_GRASS_INDICES:
        names = ["Tall Grass", "Fern", "Shrub", "Bush", "Wild Grass", "Pampas Grass", "Savanna Grass", "Dry Bush", "Green Sprout", "Thick Shrub"]
        name = names[index % len(names)]
        return {"kind": "grass", "label": tr(f"hexland_{name.lower().replace(' ', '_')}", name), "group": "Grass"}
        
    return {"kind": "decor", "label": _auto_label("Nature Decor", sprite_path), "group": "Others"}


def _auto_land_offset(sprite: str) -> Dict[str, int]:
    source_w, source_h = _sprite_size(sprite)
    if source_w >= 50:
        width = 36
    elif source_h >= 75:
        width = max(24, min(32, source_w))
    else:
        width = max(14, min(36, source_w))
    display_h = int(round(source_h * (width / max(1, source_w))))
    return {"x": int(round((65 - width) / 2)), "y": 39 - display_h, "w": width}


def _surface_offset(sprite: str, kind: str, offset: Dict[str, Any]) -> Dict[str, int]:
    source_w, source_h = _sprite_size(sprite)
    base_w = int(offset.get("w", source_w)) if isinstance(offset, dict) else source_w
    kind = str(kind or "").lower()
    if kind == "flower":
        max_w, max_h, min_w = 18, 18, 10
    elif kind == "tree":
        max_w, max_h, min_w = 26, 64, 14
    elif kind == "rock":
        max_w, max_h, min_w = 34, 34, 16
    elif kind == "grass":
        max_w, max_h, min_w = 28, 24, 10
    elif kind == "inhabitant":
        max_w, max_h, min_w = 18, 32, 10
    else:
        max_w, max_h, min_w = 28, 32, 10
    scale = min(base_w / max(1, source_w), max_w / max(1, source_w), max_h / max(1, source_h))
    width = max(min_w, int(round(source_w * scale)))
    display_h = int(round(source_h * (width / max(1, source_w))))
    return {"x": int(round((65 - width) / 2)), "y": 39 - display_h, "w": width}


def _fit_surface_catalog(catalog: Dict[str, Dict[str, Any]], default_kind: str = "decor") -> Dict[str, Dict[str, Any]]:
    for item in catalog.values():
        sprite = str(item.get("sprite") or "")
        if not sprite:
            continue
        kind = str(item.get("kind") or default_kind)
        item["offset"] = _surface_offset(sprite, kind, item.get("offset", {}))
    return catalog


def _decor_offset(filename: str) -> Dict[str, int]:
    low = filename.lower()
    source_w, source_h = _png_size("Land", filename)
    def centered(width: int, anchor_y: int = 39) -> Dict[str, int]:
        display_h = int((source_h * (width / max(1, source_w))) + 0.5)
        return {"x": int(round((65 - width) / 2)), "y": anchor_y - display_h, "w": width}
    if "flower" in low:
        return centered(18)
    if "alien" in low:
        return {"x": 22, "y": -8, "w": 26}
    if "pine" in low:
        return centered(30)
    if "tree" in low or "cactus" in low:
        if "cactus" in low:
            return centered(29)
        return centered(27)
    if "bush" in low:
        return centered(24)
    if "rock" in low:
        return centered(36)
    return centered(32)


def terrain_catalog() -> Dict[str, Dict[str, Any]]:
    catalog = copy.deepcopy(TERRAIN_ITEMS)
    for key, item in catalog.items():
        item["group"] = TERRAIN_GROUPS_BY_KEY.get(key, "Others")
        item["label"] = TERRAIN_LABELS_BY_KEY.get(key, item["label"])
    existing_sprites = {item["sprite"] for item in catalog.values()}
    for filename in _asset_file_names("Land"):
        if not filename.startswith("tile"):
            continue
        sprite = f"Land/{filename}"
        if sprite in existing_sprites:
            continue
        key = _key_from_path("terrain", filename)
        if key in DELETED_TERRAIN_KEYS:
            continue
        catalog[key] = {
            "label": TERRAIN_LABELS_BY_KEY.get(key, _label_from_filename(filename)),
            "sprite": sprite,
            "unlock": 0,
            "cost": {"coins": 8},
            "group": TERRAIN_GROUPS_BY_KEY.get(key, "Others"),
        }
    for sprite, view in _auto_sprite_views().items():
        if not sprite.startswith("Auto/land_") or not _is_land_tile_view(view) or _is_legacy_view(view):
            continue
        key = _auto_key("terrain", sprite)
        if key in DELETED_TERRAIN_KEYS:
            continue
        catalog[key] = {
            "label": TERRAIN_LABELS_BY_KEY.get(key, _auto_label("Terrain", sprite)),
            "sprite": sprite,
            "unlock": 0,
            "cost": {"coins": 8},
            "group": TERRAIN_GROUPS_BY_KEY.get(key, "Others"),
        }
    return catalog


def decor_catalog() -> Dict[str, Dict[str, Any]]:
    catalog = copy.deepcopy(DECOR_ITEMS)
    for item in catalog.values():
        kind = str(item.get("kind") or "decor")
        item.setdefault("group", {"tree": "Trees", "flower": "Flowers", "rock": "Rocks", "grass": "Grass"}.get(kind, "Others"))
    existing_sprites = {item["sprite"] for item in catalog.values()}
    for filename in _asset_file_names("Land"):
        if filename.startswith("tile") or filename.startswith("alien"):
            continue
        low = filename.lower()
        if low.startswith("wave") or low.startswith("hill"):
            continue
        sprite = f"Land/{filename}"
        if sprite in existing_sprites:
            continue
        kind = "flower" if "flower" in low else "tree" if ("tree" in low or "pine" in low or "cactus" in low) else "decor"
        catalog[_key_from_path("decor", filename)] = {
            "label": _label_from_filename(filename),
            "sprite": sprite,
            "kind": kind,
            "group": {"tree": "Trees", "flower": "Flowers", "rock": "Rocks", "grass": "Grass"}.get(kind, "Others"),
            "cost": {"coins": 15},
            "offset": _decor_offset(filename),
        }
    for sprite, view in _auto_sprite_views().items():
        if not sprite.startswith("Auto/land_") or _is_land_tile_view(view) or _is_land_person_view(view) or _is_legacy_view(view):
            continue
        info = _auto_nature_info(sprite)
        catalog[_auto_key("decor", sprite)] = {
            "label": info["label"],
            "sprite": sprite,
            "kind": info["kind"],
            "group": info["group"],
            "cost": {"coins": 15},
            "offset": _auto_land_offset(sprite),
        }
    return _fit_surface_catalog(catalog, "decor")


def inhabitant_catalog() -> Dict[str, Dict[str, Any]]:
    catalog = copy.deepcopy(INHABITANT_ITEMS)
    existing_sprites = {item["sprite"] for item in catalog.values()}
    for filename in _asset_file_names("Land"):
        if not filename.startswith("alien"):
            continue
        sprite = f"Land/{filename}"
        if sprite in existing_sprites:
            continue
        catalog[_key_from_path("person", filename)] = {
            "label": _label_from_filename(filename),
            "sprite": sprite,
            "cost": {"coins": 15}, "unlock_lands": 20,
            "offset": _decor_offset(filename),
        }
    for sprite, view in _auto_sprite_views().items():
        if not sprite.startswith("Auto/land_") or not _is_land_person_view(view) or _is_legacy_view(view):
            continue
        if sprite in existing_sprites:
            continue
        catalog[_auto_key("person", sprite)] = {
            "label": _auto_label("Inhabitant", sprite),
            "sprite": sprite,
            "cost": {"coins": 15}, "unlock_lands": 20,
            "offset": _auto_land_offset(sprite),
            "group": "Aliens",
        }
    return _fit_surface_catalog(catalog, "inhabitant")


def building_part_catalog() -> Dict[str, Dict[str, Any]]:
    catalog = copy.deepcopy(BUILDING_PART_ITEMS)
    existing_sprites = {item["sprite"] for item in catalog.values()}
    for key, item in catalog.items():
        item.setdefault("display", _building_part_display(item["sprite"]))
        item.setdefault("group", _building_part_group(key, item))
    for building in BUILDING_ITEMS.values():
        for sprite in (building["wall"], building["roof"]):
            if sprite in existing_sprites:
                continue
            catalog[_key_from_path("part", os.path.basename(sprite))] = {
                "label": _label_from_filename(os.path.basename(sprite)),
                "sprite": sprite,
                "cost": {"coins": 15},
                "display": _building_part_display(sprite),
            }
            key = _key_from_path("part", os.path.basename(sprite))
            catalog[key]["group"] = _building_part_group(key, catalog[key])
            existing_sprites.add(sprite)
    for filename in _asset_file_names("Buildings"):
        sprite = f"Buildings/{filename}"
        if sprite in existing_sprites:
            continue
        catalog[_key_from_path("part", filename)] = {
            "label": _label_from_filename(filename),
            "sprite": sprite,
            "cost": {"coins": 15},
            "display": _building_part_display(sprite),
        }
        key = _key_from_path("part", filename)
        catalog[key]["group"] = _building_part_group(key, catalog[key])
    for sprite, view in _auto_sprite_views().items():
        if not sprite.startswith("Auto/buildings_") or _is_legacy_view(view):
            continue
        display = _building_part_display(sprite)
        label_prefix = "Roof Sprite" if _is_building_roof_view(view) else "Building Sprite"
        if _is_building_roof_view(view):
            display["role"] = "roof"
        key = _auto_key("part", sprite)
        catalog[key] = {
            "label": _auto_label(label_prefix, sprite),
            "sprite": sprite,
            "cost": {"coins": 15},
            "display": display,
        }
        catalog[key]["group"] = _building_part_group(key, catalog[key])
    for key, item in catalog.items():
        override = BUILDING_PART_OVERRIDES.get(key)
        if override:
            if "label" in override:
                item["label"] = override["label"]
            item["group"] = override.get("group", item.get("group", "Others"))
            if "subgroup" in override:
                item["subgroup"] = override["subgroup"]
            if "order" in override:
                item["order"] = override["order"]
        elif item.get("group") != "DELETE":
            item["group"] = "DELETE"
    return {k: v for k, v in catalog.items() if v.get("group") != "DELETE"}


def _building_part_display(sprite: str) -> Dict[str, int]:
    filename = os.path.basename(sprite)
    source_w, source_h = _sprite_size(sprite)
    low = filename.lower()
    if source_w <= 32 and source_h <= 36:
        width = max(14, min(34, int(round(source_w * 1.55))))
        display_h = int(round(source_h * (width / max(1, source_w))))
        y = 34 if "door" in low or "gate" in low else 18
        return {
            "x": int(round((65 - width) / 2)),
            "y": y,
            "w": width,
            "h": display_h,
            "role": "detail",
        }
    if "roof" in low:
        return {"x": 0, "y": 0, "w": 66, "h": int(round(source_h * (66 / max(1, source_w)))), "role": "module"}
    return {"x": 0, "y": 0, "w": 65, "h": int(round(source_h * (65 / max(1, source_w)))), "role": "module"}


def _building_part_group(item_key: str, item: Dict[str, Any]) -> str:
    display = item.get("display", {})
    role = display.get("role") if isinstance(display, dict) else ""
    text = f"{item_key} {item.get('label', '')} {item.get('sprite', '')}".lower()

    is_roof = (role == "roof" or "roof" in text)
    is_wall = (role == "module" or "wall" in text or "door" in text)

    if not (is_roof or is_wall):
        return "DELETE"

    if "(13)" in text or "(14)" in text or "stone window" in text or "stone gate" in text:
        return "DELETE"

    sub = "Roof" if is_roof else "Walls"

    if "stone" in text or "grey" in text or "gray" in text:
        return f"Pedra - {sub}"
    elif "sand" in text or "beige" in text:
        return f"Areia - {sub}"
    else:
        return f"Argila - {sub}"


def _is_roof_part(part_key: str, catalog: Dict[str, Dict[str, Any]]) -> bool:
    base_part_key = str(part_key).split(":")[0] if part_key else ""
    item = catalog.get(base_part_key, {})
    display = item.get("display", {})
    if isinstance(display, dict) and display.get("role") == "roof":
        return True
    text = f"{base_part_key} {item.get('label', '')} {item.get('sprite', '')}".lower()
    return "roof" in text


def _is_detail_part(part_key: str, catalog: Dict[str, Dict[str, Any]]) -> bool:
    base_part_key = str(part_key).split(":")[0] if part_key else ""
    item = catalog.get(base_part_key, {})
    display = item.get("display", {})
    return isinstance(display, dict) and display.get("role") == "detail"


def _building_part_top_offset(parts: List[str], part_key: str, index: int, catalog: Dict[str, Dict[str, Any]]) -> int:
    wall_levels = 0
    roof_layers = 0
    for previous_key in parts[:index]:
        previous_key = str(previous_key)
        if _is_detail_part(previous_key, catalog):
            continue
        if _is_roof_part(previous_key, catalog):
            roof_layers += 1
        else:
            wall_levels += 1
    base_part_key = str(part_key).split(":")[0] if part_key else ""
    if _is_detail_part(base_part_key, catalog):
        display = catalog.get(base_part_key, {}).get("display", {})
        detail_y = int(display.get("y", 20)) if isinstance(display, dict) else 20
        return BUILDING_BASE_OFFSET + (max(0, wall_levels - 1) * BUILDING_LEVEL_STEP) - detail_y
    if _is_roof_part(base_part_key, catalog):
        item = catalog.get(base_part_key, {})
        display = item.get("display", {})
        display_w = int(display.get("w", 65)) if isinstance(display, dict) else 65
        asset = _asset_ref(item.get("sprite"))
        roof_h = int(round(asset["height"] * (display_w / asset["width"]))) if asset and asset.get("width") else 65
        wall_top_offset = BUILDING_BASE_OFFSET + (max(0, wall_levels - 1) * BUILDING_LEVEL_STEP) - BUILDING_WALL_NUDGE
        return wall_top_offset + roof_h - BUILDING_ROOF_NUDGE + (roof_layers * 8) - BUILDING_ROOF_Y_NUDGE
    return BUILDING_BASE_OFFSET + (wall_levels * BUILDING_LEVEL_STEP) - BUILDING_WALL_NUDGE


class HexagonLandManager:
    def __init__(self) -> None:
        self._state_cache: Optional[HexagonLandState] = None
        self._data_path_cache = ""
        self._last_session_notification_signature: Optional[Tuple[Any, ...]] = None

    def config(self) -> Dict[str, Any]:
        conf = config.get_config()
        land_conf = conf.get("hexagon_land")
        if not isinstance(land_conf, dict):
            land_conf = conf.get("hexagon_world", {})
        return land_conf if isinstance(land_conf, dict) else {}

    def is_enabled(self) -> bool:
        conf = config.get_config()
        return bool(self.config().get("enabled", False))

    def _anki_today_review_count(self) -> Optional[int]:
        try:
            if not mw or not mw.col or not getattr(mw.col, "db", None):
                return None
            day_cutoff = getattr(mw.col.sched, "day_cutoff", 0)
            if not day_cutoff:
                return None
            today_start_ms = (day_cutoff - 86400) * 1000
            return int(mw.col.db.scalar(
                "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3) AND id >= ?",
                today_start_ms,
            ) or 0)
        except Exception as exc:
            print(f"Onigiri: Error reading today's Hexagon Land reviews: {exc}")
            return None

    def _latest_today_review_eases(self, count: int) -> List[int]:
        if count <= 0:
            return []
        try:
            if not mw or not mw.col or not getattr(mw.col, "db", None):
                return [0] * count
            day_cutoff = getattr(mw.col.sched, "day_cutoff", 0)
            if not day_cutoff:
                return [0] * count
            today_start_ms = (day_cutoff - 86400) * 1000
            eases = mw.col.db.list(
                """
                SELECT ease FROM (
                    SELECT id, ease
                    FROM revlog
                    WHERE type IN (0,1,2,3) AND id >= ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id
                """,
                today_start_ms,
                count,
            )
            return [int(ease or 0) for ease in eases]
        except Exception as exc:
            print(f"Onigiri: Error reading Hexagon Land review eases: {exc}")
            return [0] * count

    def _prepare_study_day(self, state: HexagonLandState, anki_today: date) -> bool:
        today_iso = anki_today.isoformat()
        yesterday_iso = (anki_today - timedelta(days=1)).isoformat()
        if state.last_study_day == today_iso:
            return False
        if state.last_study_day == yesterday_iso:
            state.current_streak = getattr(state, "current_streak", 0) + 1
        else:
            state.current_streak = 1
        state.today_reviews = 0
        state.last_study_day = today_iso
        return True

    def _award_review_rewards(self, state: HexagonLandState, ease: int = 0) -> Tuple[int, int, Dict[str, int]]:
        coin_rate = self.coin_rate(state)
        coin_gain_total = float(coin_rate)
        if int(ease or 0) >= 4:
            coin_gain_total += 1
        coin_gain_with_fraction = coin_gain_total + float(getattr(state, "hex_coin_fraction", 0.0) or 0.0)
        coin_gain = max(1, int(math.floor(coin_gain_with_fraction)))
        state.hex_coin_fraction = max(0.0, coin_gain_with_fraction - coin_gain)
        state.pending_hex_coins = getattr(state, "pending_hex_coins", 0) + coin_gain

        import random
        water_coords = {k for k, v in state.tiles.items() if v.get("terrain") == "water"}
        fish_coins = 0
        for coord_str, tile in state.tiles.items():
            for _spot_key, entry in _spot_entries(tile):
                if entry.get("category") == "inhabitant":
                    q, r = _parse_coord(coord_str)
                    is_near_water = coord_str in water_coords
                    if not is_near_water:
                        for dq, dr in DIRECTIONS:
                            if _coord_key(q + dq, r + dr) in water_coords:
                                is_near_water = True
                                break
                    if is_near_water and random.random() < 0.1:
                        fish_coins += random.randint(1, 3)
        if fish_coins > 0:
            state.pending_hex_coins = getattr(state, "pending_hex_coins", 0) + fish_coins

        gained_materials = self._study_material_rewards(state.lifetime_reviews, ease)
        for key, amount in gained_materials.items():
            if not getattr(state, "pending_materials", None):
                state.pending_materials = {}
            state.pending_materials[key] = int(state.pending_materials.get(key, 0)) + amount
        return coin_gain, fish_coins, gained_materials

    def sync_today_reviews(self) -> bool:
        if not self.is_enabled():
            return False
        anki_count = self._anki_today_review_count()
        if anki_count is None:
            return False

        state = self.load()
        changed = False
        today = _anki_today()
        today_iso = today.isoformat()

        # A new day must clear the counter even when nothing was studied yet,
        # otherwise yesterday's total keeps showing as "reviews today".
        # Streak/day-stamping still waits for the first real review.
        if state.last_study_day != today_iso and int(getattr(state, "today_reviews", 0) or 0) != 0:
            state.today_reviews = 0
            changed = True

        if anki_count > 0 and state.last_study_day != today_iso:
            changed = self._prepare_study_day(state, today) or changed

        current_count = int(getattr(state, "today_reviews", 0) or 0) if state.last_study_day == today_iso else 0
        if current_count < anki_count:
            missing = anki_count - current_count
            for ease in self._latest_today_review_eases(missing):
                state.today_reviews += 1
                state.lifetime_reviews += 1
                self._award_review_rewards(state, ease)
            state.last_message = tr("hexland_synced_reviews", "{} synced.").format(missing)
            changed = True
        elif state.last_study_day == today_iso and current_count > anki_count:
            state.today_reviews = anki_count
            changed = True

        if changed:
            self.save(state)
        return changed

    def data_path(self) -> str:
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_files = os.path.join(addon_path, "user_files")
        os.makedirs(user_files, exist_ok=True)
        path = os.path.join(user_files, f"hexagon_land_{_profile_name()}.json")
        self._data_path_cache = path
        return path

    def load(self) -> HexagonLandState:
        path = self.data_path()
        if self._state_cache is not None and self._data_path_cache == path:
            return copy.deepcopy(self._state_cache)
        if not os.path.exists(path):
            state = HexagonLandState()
            self._state_cache = state
            self.save(state)
            return copy.deepcopy(state)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            state = HexagonLandState(**raw)
            today = _anki_today()
            if state.last_study_day:
                last_day = date.fromisoformat(state.last_study_day)
                missed_days = (today - last_day).days - 1
                if missed_days > 0 and len(state.tiles) > 1:
                    survival_mode = bool(self.config().get("survival_mode", False))
                    if survival_mode:
                        streak = getattr(state, "current_streak", 0)
                        tiles_to_lose = missed_days
                        if streak > 0:
                            # Extra penalty: 1 extra tile per 5 days of streak
                            tiles_to_lose += streak // 5

                        removed = 0
                        for _ in range(min(tiles_to_lose, len(state.tiles) - 1)):
                            edge_tile = min(state.tiles.keys(), key=lambda k: (
                                sum(1 for dq, dr in DIRECTIONS if _coord_key(_parse_coord(k)[0] + dq, _parse_coord(k)[1] + dr) in state.tiles),
                                -abs(_parse_coord(k)[0]) - abs(_parse_coord(k)[1])
                            ))
                            if edge_tile != "0,0":
                                state.tiles.pop(edge_tile)
                                removed += 1
                        if removed > 0:
                            state.last_message = f"You lost {removed} land tile(s) because you didn't study."
                    state.last_study_day = (today - timedelta(days=1)).isoformat()
                    state.current_streak = 0
                    # We save without using the cache so it persists immediately
                    self.save(state)
        except Exception as exc:
            print(f"Onigiri: Error loading Hexagon Land data: {exc}")
            state = HexagonLandState()
        self._state_cache = state
        return copy.deepcopy(state)

    def save(self, state: HexagonLandState) -> None:
        state.updated_at = datetime.now().isoformat()
        path = self.data_path()
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="hexagon_land_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(state), handle, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception as exc:
            print(f"Onigiri: Error saving Hexagon Land data: {exc}")
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        self._state_cache = copy.deepcopy(state)

    def reset(self) -> None:
        self.save(HexagonLandState(last_message="Hexagon Land has been rebuilt from its starter island."))

    def island_display_name(self, state: Optional[HexagonLandState] = None) -> str:
        state = state or self.load()
        name = str(getattr(state, "island_name", "") or "").strip()
        return name if name else "Hexagon Land"

    def buy_keys_of_the_island(self) -> str:
        state = self.load()
        if state.keys_of_the_island:
            return "You already own the Keys of the Island."
        if state.hex_coins < KEYS_OF_THE_ISLAND_COST:
            return f"Keys of the Island need {KEYS_OF_THE_ISLAND_COST} {tr('hexland_hex_coins', 'Hex Coins')}."
        state.hex_coins -= KEYS_OF_THE_ISLAND_COST
        state.keys_of_the_island = True
        state.last_message = "The Keys of the Island are yours. You can name your island now."
        self.save(state)
        return state.last_message

    def set_island_name(self, name: str) -> str:
        state = self.load()
        if not state.keys_of_the_island:
            return "Buy the Keys of the Island before naming your island."
        clean_name = re.sub(r"\s+", " ", str(name or "").strip())[:40]
        state.island_name = clean_name or "Hexagon Land"
        state.last_message = f"Your island is now called {state.island_name}."
        self.save(state)
        return state.last_message

    def on_answer(self, reviewer=None, card=None, ease: int = 0) -> None:
        if not self.is_enabled():
            return
        state = self.load()
        anki_today = _anki_today()
        self._prepare_study_day(state, anki_today)
        state.today_reviews += 1
        state.lifetime_reviews += 1

        coin_gain, fish_coins, gained_materials = self._award_review_rewards(state, ease)

        if gained_materials:
            materials_text = ", ".join(f"{amount} {key}" for key, amount in gained_materials.items())
            msg = f"Studying earned {coin_gain} {tr('hexland_hex_coins', 'Hex Coins')} and {materials_text}."
        else:
            msg = f"Studying earned {coin_gain} {tr('hexland_hex_coins', 'Hex Coins')}."
            
        if fish_coins > 0:
            msg += f" Inhabitants went fishing and found {fish_coins} extra coins!"
            
        state.last_message = msg
        self.save(state)

    def _study_material_rewards(self, reviews: int, ease: int = 0) -> Dict[str, int]:
        return {}

    def nature_counts(self, state: Optional[HexagonLandState] = None) -> Tuple[int, int]:
        state = state or self.load()
        trees = 0
        flowers = 0
        decors = decor_catalog()
        for tile in state.tiles.values():
            for _, entry in _spot_entries(tile):
                if entry.get("category") != "decor":
                    continue
                decor = decors.get(str(entry.get("item") or ""), {})
                if decor.get("kind") == "tree":
                    trees += 1
                elif decor.get("kind") == "flower":
                    flowers += 1
        return trees, flowers

    def on_state_did_change(self, state_str: str, old_state: str) -> None:
        if state_str in ("deckBrowser", "overview"):
            self.sync_today_reviews()
            state = self.load()
            pending_coins = getattr(state, "pending_hex_coins", 0)
            pending_mats = getattr(state, "pending_materials", {})
            if pending_coins > 0 or pending_mats:
                self._notify_session_rewards(state, pending_coins, pending_mats)

    def _notify_session_rewards(self, state: HexagonLandState, pending_coins: int, pending_mats: Dict[str, int]) -> None:
        mats_signature = tuple(sorted((str(key), int(value)) for key, value in (pending_mats or {}).items()))
        signature = (state.last_study_day, state.today_reviews, int(pending_coins or 0), mats_signature)
        if signature == self._last_session_notification_signature:
            return
        self._last_session_notification_signature = signature

        materials_text = ""
        if pending_mats:
            materials_text = tr('hexland_and_connector', ' and ') + ", ".join(f"{amount} {key}" for key, amount in pending_mats.items())
        message = tr(
            'hexland_earned_session_tooltip',
            "Hexagon Land: Você ganhou {} Hex Coins{} nesta sessão!"
        ).format(pending_coins, materials_text)
        coin_icon_url = f"/_addons/{_addon_package()}/system_files/gamification_images/hex_coin.webp"
        reward_items = []
        if pending_coins > 0:
            reward_items.append({
                "iconImage": coin_icon_url,
                "iconAlt": tr('hexland_hex_coins', 'Hex Coins'),
                "value": str(pending_coins),
            })
        for key, amount in (pending_mats or {}).items():
            reward_items.append({"value": f"{amount} {key}"})

        def show_notification() -> None:
            payload = {
                "id": "hexagon_land_rewards",
                "name": "Hexagon Land",
                "description": tr('hexland_earned_session_ui', 'Session Rewards:'),
                "rewardItems": reward_items,
                "iconImage": f"/_addons/{_addon_package()}/system_files/gamification_images/Hexagon_world.webp",
                "iconAlt": "Hexagon Land",
                "forceTop": True,
                "duration": 6500,
            }
            script = (
                "if (window.OnigiriNotifications) "
                f"window.OnigiriNotifications.show({json.dumps(payload, ensure_ascii=False)});"
            )
            delivered = False
            if getattr(mw, "state", None) != "review":
                return
            for owner_name in ("reviewer",):
                try:
                    owner = getattr(mw, owner_name, None)
                    web = getattr(owner, "web", None)
                    if web:
                        web.eval(script)
                        delivered = True
                        break
                except Exception:
                    pass
            if not delivered:
                try:
                    from aqt.utils import tooltip
                    tooltip(message)
                except Exception:
                    pass

        QTimer.singleShot(650, show_notification)

    def inhabitant_count(self, state: Optional[HexagonLandState] = None) -> int:
        state = state or self.load()
        count = 0
        for tile in state.tiles.values():
            for _, entry in _spot_entries(tile):
                if entry.get("category") == "inhabitant":
                    count += 1
        return count

    def coin_rate(self, state: Optional[HexagonLandState] = None) -> float:
        state = state or self.load()
        trees, flowers = self.nature_counts(state)
        extra_coins = min((trees * 0.10) + (flowers * 0.05), 20)
        return 1 + extra_coins

    def unlocked_terrains(self, state: Optional[HexagonLandState] = None) -> List[str]:
        state = state or self.load()
        if SANDBOX_MODE:
            return list(terrain_catalog().keys())
        reviews = int(state.lifetime_reviews)
        return [key for key, item in terrain_catalog().items() if reviews >= int(item.get("unlock", 0))]

    def adjacent_empty_coords(self, state: Optional[HexagonLandState] = None) -> List[Tuple[int, int]]:
        state = state or self.load()
        occupied = set(state.tiles.keys())
        coords = set()
        for key in occupied:
            q, r = _parse_coord(key)
            for dq, dr in DIRECTIONS:
                neighbor = _coord_key(q + dq, r + dr)
                if neighbor not in occupied:
                    coords.add((q + dq, r + dr))
        return sorted(coords, key=lambda item: (item[0] + item[1], item[0]))

    def apply_action(self, action: str, payload: Dict[str, Any]) -> str:
        state = self.load()
        message = ""
        try:
            if action == "place":
                message = self._place(state, payload)
            elif action == "clear_tile":
                message = self._clear_tile(state, payload)
            elif action == "reset":
                self.reset()
                return "Hexagon Land has been reset."
            else:
                message = "That Hexagon Land action is not available yet."
        except Exception as exc:
            message = f"Could not update Hexagon Land: {exc}"
        state.last_message = message
        self.save(state)
        return message

    def _place(self, state: HexagonLandState, payload: Dict[str, Any]) -> str:
        category = str(payload.get("category") or "")
        item_key = str(payload.get("item") or "")
        q = int(payload.get("q", 0))
        r = int(payload.get("r", 0))
        coord = _coord_key(q, r)
        tile = state.tiles.get(coord)
        terrains = terrain_catalog()
        decors = decor_catalog()
        inhabitants = inhabitant_catalog()
        building_parts = building_part_catalog()

        if category == "terrain":
            if item_key not in terrains:
                return "Choose a terrain first."
            if item_key not in self.unlocked_terrains(state):
                return f"{terrains[item_key]['label']} unlocks after more studying."
            if tile is None:
                if not self._can_expand_to(state, q, r):
                    return "Expand from the edge of your existing island."
                expand_cost = self._expand_cost(state)
                if not self._spend(state, expand_cost):
                    return self._cost_message("Expand land", expand_cost)
                # Remember the claim price so deleting the tile refunds exactly
                # what it cost, no matter how the level-scaled price has moved
                # since.
                tile = {
                    "terrain": item_key,
                    "height": 1,
                    "parts": [],
                    "land_cost": int(expand_cost.get("coins", 0)),
                }
                state.tiles[coord] = tile
                return f"Expanded the island with {terrains[item_key]['label']}."
            if tile.get("building") or tile.get("parts"):
                if tile.get("building"):
                    return "Cannot place on top of a roof."
                parts = tile.get("parts", [])
                if parts and _is_roof_part(parts[-1].split(":")[0], building_parts):
                    return "Cannot place on top of a roof."
                cost = terrains[item_key].get("cost", {})
                if not self._spend(state, cost):
                    return self._cost_message(terrains[item_key]["label"], cost)
                parts.append(item_key)
                return f"Stacked {terrains[item_key]['label']} on building."
            cost = terrains[item_key].get("cost", {})
            if not self._spend(state, cost):
                return self._cost_message(terrains[item_key]["label"], cost)
            current_height = max(1, int(tile.get("height", 1) or 1))
            current_terrain = tile.get("terrain", item_key)
            current_layers = tile.setdefault("layers", [])
            # Pad layers to match current height using the current terrain
            while len(current_layers) < current_height:
                current_layers.insert(0, current_terrain)
            tile["height"] = current_height + 1
            current_layers.append(item_key)
            tile["terrain"] = item_key
            return f"Stacked {terrains[item_key]['label']} on top."

        if tile is None:
            return "Pick an existing tile, or select terrain to expand."

        if category == "raise":
            current_height = max(1, int(tile.get("height", 1) or 1))
            current_terrain = tile.get("terrain", "grass")
            current_layers = tile.setdefault("layers", [])
            # Pad layers to match current height using the current terrain
            while len(current_layers) < current_height:
                current_layers.insert(0, current_terrain)
            current_layers.append(current_terrain)
            tile["height"] = current_height + 1
            return "Raised land one level."

        if category == "decor":
            item = decors.get(item_key)
            if not item:
                return "Choose a tree, flower, or rock first."
            label = item.get("label", "")
            if label.startswith("Nature "):
                try:
                    num = int(label.split(" ")[-1])
                    if 24 <= num <= 32:
                        target_spot = _placement_spot_for_item(item, item_key, payload.get("spot"))
                        for t_coord, t in state.tiles.items():
                            spots = _normalize_tile_spots(t)
                            for s_key, entry in spots.items():
                                if entry.get("category") == "decor" and entry.get("item") == item_key:
                                    if t_coord != coord or s_key != target_spot:
                                        return f"You can only place one {label} on your land."
                except (ValueError, IndexError):
                    pass
            cost = item.get("cost", {})
            if not self._spend(state, cost):
                return self._cost_message(item["label"], cost)
            if tile.get("building"):
                return "Cannot place on top of a roof."
            parts = tile.get("parts", [])
            if parts and _is_roof_part(parts[-1].split(":")[0], building_parts):
                return "Cannot place on top of a roof."
            spot = _placement_spot_for_item(item, item_key, payload.get("spot"))
            _normalize_tile_spots(tile)[spot] = {"category": "decor", "item": item_key}
            return f"Placed {item['label']}."

        if category in ("building", "buildingPart"):
            base_item_key = item_key.split(":")[0] if ":" in item_key else item_key
            item = BUILDING_ITEMS.get(base_item_key)
            if not item and base_item_key in building_parts:
                item = building_parts[base_item_key]
                parts = tile.setdefault("parts", [])
                if not isinstance(parts, list):
                    parts = []
                    tile["parts"] = parts
                if _is_roof_part(base_item_key, building_parts):
                    has_wall_base = bool(tile.get("building")) or any(
                        not _is_detail_part(str(part_key), building_parts)
                        and not _is_roof_part(str(part_key), building_parts)
                        for part_key in parts
                    )
                    if not has_wall_base:
                        return "Place a building wall before adding a roof."
                cost = item.get("cost", {})
                if not self._spend(state, cost):
                    return self._cost_message(item["label"], cost)
                tile.pop("spots", None)
                parts.append(item_key)
                return f"Stacked {item['label']}."
            if not item:
                return "Choose a building first."
            cost = item.get("cost", {})
            if not self._spend(state, cost):
                return self._cost_message(item["label"], cost)
            tile.pop("spots", None)
            tile["building"] = item_key
            return f"Built {item['label']}."

        if category == "inhabitant":
            item = inhabitants.get(item_key)
            if not item:
                return "Choose an inhabitant first."
            cost = item.get("cost", {})
            if not self._spend(state, cost):
                return self._cost_message(item["label"], cost)
            if tile.get("building"):
                return "Cannot place on top of a roof."
            parts = tile.get("parts", [])
            if parts and _is_roof_part(parts[-1].split(":")[0], building_parts):
                return "Cannot place on top of a roof."
            spot = _normalize_spot_key(payload.get("spot"))
            _normalize_tile_spots(tile)[spot] = {"category": "inhabitant", "item": item_key}
            return f"{item['label']} moved in."

        return "Choose something to build."

    def _tile_refund(self, state: HexagonLandState, tile: Dict[str, Any]) -> int:
        """Coins owed for scrapping a tile: the claim price plus everything
        currently standing on it.

        Valued from the tile's present contents rather than a running total, so
        removing a layer or a decoration first simply lowers the refund instead
        of leaving a stale balance behind."""
        terrains = terrain_catalog()
        decors = decor_catalog()
        inhabitants = inhabitant_catalog()
        parts = building_part_catalog()

        def coins(item: Optional[Dict[str, Any]]) -> int:
            if not isinstance(item, dict):
                return 0
            return int((item.get("cost") or {}).get("coins", 0) or 0)

        # Tiles claimed before land_cost was recorded fall back to today's price.
        refund = int(tile.get("land_cost", self._expand_cost(state).get("coins", 0)) or 0)

        # Every stacked terrain layer above the base was bought separately.
        height = max(1, int(tile.get("height", 1) or 1))
        layers = tile.get("layers")
        for index in range(1, height):
            terrain_key = layers[index] if isinstance(layers, list) and index < len(layers) else tile.get("terrain")
            refund += coins(terrains.get(str(terrain_key or "")))

        for _spot, entry in _spot_entries(tile):
            category = str(entry.get("category") or "")
            item_key = str(entry.get("item") or "")
            if category == "decor":
                refund += coins(decors.get(item_key))
            elif category == "inhabitant":
                refund += coins(inhabitants.get(item_key))

        if tile.get("building"):
            refund += coins(BUILDING_ITEMS.get(str(tile.get("building"))))
        for part in tile.get("parts") or []:
            refund += coins(parts.get(str(part).split(":")[0]))
        return max(0, refund)

    def _clear_tile(self, state: HexagonLandState, payload: Dict[str, Any]) -> str:
        coord = _coord_key(int(payload.get("q", 0)), int(payload.get("r", 0)))
        tile = state.tiles.get(coord)
        if not tile:
            return "There is no tile there yet."
        layer = str(payload.get("layer") or "decor")
        if layer == "tile":
            if len(state.tiles) <= 1:
                return "Keep at least one land tile."
            refund = self._tile_refund(state, tile)
            state.tiles.pop(coord, None)
            if refund > 0 and not SANDBOX_MODE:
                state.hex_coins += refund
                return f"Deleted land tile. Refunded {refund} {tr('hexland_hex_coins', 'Hex Coins')}."
            return "Deleted land tile."
        if layer == "construction":
            removed = False
            if tile.get("building"):
                tile.pop("building", None)
                removed = True
            if tile.get("parts"):
                tile["parts"] = []
                removed = True
            return "Removed construction." if removed else "No construction to remove."
        if layer == "part":
            parts = tile.get("parts")
            if isinstance(parts, list) and parts:
                parts.pop()
                return "Removed top stacked part."
            return "No stacked part to remove."
        if layer == "layer":
            current_height = max(1, int(tile.get("height", 1) or 1))
            if current_height <= 1:
                return "Land is already at the lowest level."
            tile["height"] = current_height - 1
            current_layers = tile.get("layers")
            if isinstance(current_layers, list) and len(current_layers) > 1:
                current_layers.pop()
                tile["terrain"] = current_layers[-1]
            return "Removed top terrain layer."
        if layer == "lower":
            current_height = max(1, int(tile.get("height", 1) or 1))
            if current_height > 1:
                tile["height"] = current_height - 1
                return "Lowered land one level."
            return "Land is already at the lowest level."
        if layer in ("spot", "decor", "inhabitant"):
            spots = _normalize_tile_spots(tile)
            requested_spot = payload.get("spot")
            if requested_spot:
                spot = _normalize_spot_key(requested_spot)
                entry = spots.get(spot)
                if entry and (layer == "spot" or entry.get("category") == layer):
                    spots.pop(spot, None)
                    # Also clear construction if clearing any spot
                    if layer == "spot":
                        tile.pop("building", None)
                        tile["parts"] = []
                    return f"Cleared the {spot.replace('_', ' ')} spot."
                # If spot layer and nothing in spots, try clearing construction
                if layer == "spot":
                    had_construction = bool(tile.get("building") or tile.get("parts"))
                    tile.pop("building", None)
                    tile["parts"] = []
                    if had_construction:
                        return "Cleared construction."
                return "Nothing to remove on that spot."
            removed = 0
            for spot, entry in list(spots.items()):
                if layer == "spot" or entry.get("category") == layer:
                    spots.pop(spot, None)
                    removed += 1
            # For 'spot' layer, also clear any construction
            if layer == "spot":
                had_construction = bool(tile.get("building") or tile.get("parts"))
                tile.pop("building", None)
                tile["parts"] = []
                if had_construction:
                    removed += 1
            if removed:
                return f"Cleared {removed} spot{'s' if removed != 1 else ''}."
            return "Nothing to remove on that layer."
        if layer == "building" and tile.get(layer):
            tile.pop(layer, None)
            return f"Removed {layer}."
        return "Nothing to remove on that layer."

    def _can_expand_to(self, state: HexagonLandState, q: int, r: int) -> bool:
        if not state.tiles:
            return True
        for dq, dr in DIRECTIONS:
            if _coord_key(q + dq, r + dr) in state.tiles:
                return True
        return False

    def level_info(self, state: Optional[HexagonLandState] = None) -> Dict[str, Any]:
        """Island level derived from land count. See HEXLAND_* notes above."""
        if state is None:
            state = self.load()
        lands = len(state.tiles)
        level = hexland_level_from_lands(lands)
        cur_floor = hexland_lands_for_level(level)
        next_floor = hexland_lands_for_level(level + 1)
        span = max(1, next_floor - cur_floor)
        fraction = max(0.0, min(1.0, (lands - cur_floor) / span))
        title_key, title = hexland_level_title(level)
        return {
            "level": level,
            "titleKey": title_key,
            "title": tr(title_key, title),
            "lands": lands,
            "landsForLevel": cur_floor,
            "landsForNext": next_floor,
            "landsToNext": max(0, next_floor - lands),
            "fraction": fraction,
        }

    def _expand_cost(self, state: HexagonLandState) -> Dict[str, int]:
        # Price rises with island level but is capped so buying new land never
        # becomes impossible.
        level = hexland_level_from_lands(len(state.tiles))
        coins = min(
            HEXLAND_EXPAND_COST_CAP,
            HEXLAND_EXPAND_COST_BASE + level * HEXLAND_EXPAND_COST_STEP,
        )
        return {"coins": coins}

    def _spend(self, state: HexagonLandState, cost: Dict[str, int]) -> bool:
        if SANDBOX_MODE:
            return True
        normalized = {key: int(value) for key, value in cost.items() if int(value or 0) > 0}
        if state.hex_coins < normalized.get("coins", 0):
            return False
        state.hex_coins -= normalized.get("coins", 0)
        return True

    def _cost_message(self, label: str, cost: Dict[str, int]) -> str:
        parts = []
        if cost.get("coins"):
            parts.append(f"{cost['coins']} {tr('hexland_hex_coins', 'Hex Coins')}")
        return f"{label} needs " + ", ".join(parts) + "."

    def payload(self) -> Dict[str, Any]:
        self.sync_today_reviews()
        state = self.load()
        trees, flowers = self.nature_counts(state)
        terrains = terrain_catalog()
        decors = decor_catalog()
        inhabitants = inhabitant_catalog()
        building_parts = building_part_catalog()
        
        # Read the count straight from revlog so the UI never shows a stale
        # cached total; fall back to the stored counter if the DB is unavailable.
        live_reviews = self._anki_today_review_count()
        today_reviews = int(state.today_reviews if live_reviews is None else live_reviews)

        risk_tile = None
        survival_mode = bool(self.config().get("survival_mode", False))
        if survival_mode and today_reviews == 0 and len(state.tiles) > 1:
            try:
                risk_tile = min(state.tiles.keys(), key=lambda k: (
                    sum(1 for dq, dr in DIRECTIONS if _coord_key(_parse_coord(k)[0] + dq, _parse_coord(k)[1] + dr) in state.tiles),
                    -abs(_parse_coord(k)[0]) - abs(_parse_coord(k)[1])
                ))
                if risk_tile == "0,0": risk_tile = None
            except Exception: pass

        import copy
        from ..translations import tr
        
        catalog = {
            "terrains": terrains,
            "terrainActions": {
                "raise": {"label": "Stack land", "hint": "Hover a tile to preview, then click to pile land higher."}
            },
            "decors": decors,
            "buildings": copy.deepcopy(BUILDING_ITEMS),
            "buildingParts": building_parts,
            "inhabitants": inhabitants,
            "erase": copy.deepcopy(ERASE_ITEMS),
        }
        
        for cat in catalog.values():
            if isinstance(cat, dict):
                for item in cat.values():
                    if isinstance(item, dict):
                        if "cost" in item and isinstance(item["cost"], dict):
                            item["cost"] = {"coins": item["cost"].get("coins", 0)} if "coins" in item["cost"] else {}
                        if "label" in item:
                            orig_label = str(item["label"])
                            key = "hexland_" + orig_label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
                            item["label"] = tr(key, orig_label)
                        if "hint" in item:
                            orig_hint = str(item["hint"])
                            # Key off the whole hint, not its first word -- every
                            # erase hint starts with "Click", so a first-word key
                            # collapsed all three onto one translation and made
                            # the buttons describe each other.
                            slug = re.sub(r"[^a-z0-9]+", "_", orig_hint.lower()).strip("_")
                            item["hint"] = tr("hexland_hint_" + slug[:60], orig_hint)
                        if "group" in item:
                            orig_group = str(item["group"])
                            key = "hexland_group_" + orig_group.lower().replace(" ", "_")
                            item["groupKey"] = orig_group
                            item["groupLabel"] = tr(key, orig_group)
        info = self.level_info(state)
        return {
            "enabled": self.is_enabled(),
            "state": asdict(state),
            "pendingCoins": getattr(state, "pending_hex_coins", 0),
            "pendingMaterials": getattr(state, "pending_materials", {}),
            "coinRate": self.coin_rate(state),
            "trees": trees,
            "flowers": flowers,
            "todayReviews": today_reviews,
            "builtLands": len(state.tiles),
            "level": info["level"],
            "levelTitle": info["title"],
            "levelLandsForLevel": info["landsForLevel"],
            "levelFraction": info["fraction"],
            "levelLandsToNext": info["landsToNext"],
            "levelLandsForNext": info["landsForNext"],
            "unlockedTerrains": self.unlocked_terrains(state),
            "adjacent": [{"q": q, "r": r} for q, r in self.adjacent_empty_coords(state)],
            "expandCost": self._expand_cost(state),
            "assets": self.assets_payload(),
            "catalog": catalog,
            "buyUrl": BUY_HEX_COINS_URL,
            "sandbox": SANDBOX_MODE,
            "riskTile": risk_tile,
        }

    def assets_payload(self) -> Dict[str, Any]:
        assets = {"terrain": {}, "decor": {}, "building": {}, "buildingPart": {}, "inhabitant": {}}
        for key, item in terrain_catalog().items():
            assets["terrain"][key] = _asset_ref(item["sprite"])
        for key, item in decor_catalog().items():
            assets["decor"][key] = _asset_ref(item["sprite"])
        for key, item in BUILDING_ITEMS.items():
            assets["building"][key] = {
                "wall": _asset_ref(item["wall"]),
                "roof": _asset_ref(item["roof"]),
            }
        for key, item in building_part_catalog().items():
            assets["buildingPart"][key] = _asset_ref(item["sprite"])
        for key, item in inhabitant_catalog().items():
            assets["inhabitant"][key] = _asset_ref(item["sprite"])
        return assets

    def preview_layers(self, limit: int = 99999) -> Tuple[List[str], int, int]:
        state = self.load()
        items: List[Tuple[int, str]] = []
        coords = [_parse_coord(key) for key in state.tiles.keys()]
        if not coords:
            return [], 260, 170
        raw_positions = {}
        for q, r in coords:
            x = (q - r) * 32
            y = (q + r) * 49.5
            raw_positions[_coord_key(q, r)] = (x, y)
        min_x = min(x for x, _ in raw_positions.values())
        min_y = min(y for _, y in raw_positions.values())
        max_x = max(x for x, _ in raw_positions.values())
        max_y = max(y for _, y in raw_positions.values())
        width = max(230, max_x - min_x + 118)
        height = max(150, max_y - min_y + 142)

        risk_tile = None
        survival_mode = bool(self.config().get("survival_mode", False))
        live_reviews = self._anki_today_review_count()
        today_reviews = int(state.today_reviews if live_reviews is None else live_reviews)
        if survival_mode and today_reviews == 0 and len(state.tiles) > 1:
            try:
                risk_tile = min(state.tiles.keys(), key=lambda k: (
                    sum(1 for dq, dr in DIRECTIONS if _coord_key(_parse_coord(k)[0] + dq, _parse_coord(k)[1] + dr) in state.tiles),
                    -abs(_parse_coord(k)[0]) - abs(_parse_coord(k)[1])
                ))
                if risk_tile == "0,0": risk_tile = None
            except Exception: pass

        rendered = 0
        terrains = terrain_catalog()
        decors = decor_catalog()
        inhabitants = inhabitant_catalog()
        building_parts = building_part_catalog()
        for key, tile in sorted(state.tiles.items(), key=lambda pair: sum(_parse_coord(pair[0]))):
            if rendered >= limit:
                break
            q, r = _parse_coord(key)
            x, y = raw_positions[key]
            x = x - min_x + 24
            y = y - min_y + 42
            z = (q + r) * 100000 + q * 10
            terrain = terrains.get(tile.get("terrain"), terrains["grass"])
            height = max(1, int(tile.get("height", 1) or 1))
            top_y = y - ((height - 1) * LAND_LEVEL_STEP)
            
            risk_cls = " risk-tile" if key == risk_tile else ""
            
            for level in range(1, height):
                side_y = top_y + (level * LAND_SIDE_STEP)
                items.append((z + int((height - level * 0.1) * 100), _sprite_html(_asset_ref(terrain["sprite"]), "hl-tile tile-side" + risk_cls, x, side_y, 65)))
            items.append((z + int(height * 100), _sprite_html(_asset_ref(terrain["sprite"]), "hl-tile" + risk_cls, x, top_y, 65)))
            z_base = (q + r) * 100000 + int(height * 100) + q * 10
            
            # Determine offset and z-index bump for elevated spots
            elevated_offset = 0
            z_bump = 0
            if tile.get("building"):
                elevated_offset = 24
            elif tile.get("parts"):
                wall_levels = 0
                for part_key in tile["parts"]:
                    pk = str(part_key).split(":")[0]
                    if _is_detail_part(pk, building_parts): continue
                    if not _is_roof_part(pk, building_parts): wall_levels += 1
                elevated_offset = wall_levels * 24
                z_bump = 100

            for spot_index, (spot, entry) in enumerate(_spot_entries(tile)):
                if entry.get("category") == "decor":
                    item_key = entry.get("item")
                    decor = decors.get(item_key)
                    if not decor:
                        continue
                    off = _spot_render_offset(decor, spot, "decor")
                    items.append((z_base + z_bump + _spot_depth(spot) + spot_index, self._preview_img(decor["sprite"], "hl-decor", x + off.get("x", 0), top_y - elevated_offset + off.get("y", 0), off.get("w", 30))))
                elif entry.get("category") == "inhabitant":
                    item_key = entry.get("item")
                    person = inhabitants.get(item_key)
                    if not person:
                        continue
                    off = _spot_render_offset(person, spot, "inhabitant")
                    items.append((z_base + z_bump + _spot_depth(spot) + spot_index, self._preview_img(person["sprite"], "hl-decor", x + off.get("x", 0), top_y - elevated_offset + off.get("y", 0), off.get("w", 26))))
            if tile.get("building") in BUILDING_ITEMS:
                building = BUILDING_ITEMS[tile["building"]]
                roof_asset = _asset_ref(building["roof"])
                roof_h = int(round(roof_asset["height"] * (65.0 / roof_asset["width"]))) if roof_asset and roof_asset.get("width") else 65
                roof_top = (top_y - 24) - roof_h + BUILDING_ROOF_NUDGE
                items.append((z_base + 60, self._preview_img(building["wall"], "hl-building", x, top_y - 24, 65)))
                items.append((z_base + 61, self._preview_img(building["roof"], "hl-building", x + BUILDING_ROOF_X_NUDGE, roof_top + BUILDING_ROOF_Y_NUDGE, 65)))
            for index, part_key in enumerate(tile.get("parts", []) if isinstance(tile.get("parts"), list) else []):
                part_key = str(part_key)
                parts = part_key.split(":")
                base_part_key = parts[0]
                side = parts[1] if len(parts) > 1 else None
                direction = parts[2] if len(parts) > 2 else None
                part = building_parts.get(base_part_key)
                if part:
                    stack_parts = tile.get("parts", []) if isinstance(tile.get("parts"), list) else []
                    offset = _building_part_top_offset(stack_parts, part_key, index, building_parts)
                    display = part.get("display", {})
                    display_x = int(display.get("x", 0)) if isinstance(display, dict) else 0
                    display_w = int(display.get("w", 65)) if isinstance(display, dict) else 65
                    if _is_roof_part(base_part_key, building_parts):
                        display_x += BUILDING_ROOF_X_NUDGE
                    elif side in ("left", "right") and _is_detail_part(base_part_key, building_parts):
                        side_center = 20 if side == "left" else 45
                        display_x = side_center - display_w // 2
                    flip_style = ""
                    if direction == "flipped":
                        flip_style = "transform:scaleX(-1);"
                    items.append((z_base + 5 + index, self._preview_img(part["sprite"], "hl-building", x + display_x, top_y - offset, display_w, style_extra=flip_style)))
                elif base_part_key in terrains:
                    partTop = top_y - ((index + 1) * 24)
                    items.append((z_base + 5 + index, self._preview_img(terrains[base_part_key]["sprite"], "hl-tile", x, partTop, 65)))
                    items.append((z_base + 5 + index - 0.1, self._preview_img(terrains[base_part_key]["sprite"], "hl-tile tile-side", x, partTop + 24, 65)))
                elif base_part_key in decors:
                    partTop = top_y - ((index + 1) * 24)
                    off = _spot_render_offset(decors[base_part_key], "center", "decor")
                    items.append((z_base + 5 + index, self._preview_img(decors[base_part_key]["sprite"], "hl-decor", x + off.get("x", 0), partTop + 24 + off.get("y", 0), off.get("w", 30))))
                elif base_part_key in inhabitants:
                    partTop = top_y - ((index + 1) * 24)
                    off = _spot_render_offset(inhabitants[base_part_key], "center", "inhabitant")
                    items.append((z_base + 5 + index, self._preview_img(inhabitants[base_part_key]["sprite"], "hl-decor", x + off.get("x", 0), partTop + 24 + off.get("y", 0), off.get("w", 26))))
            rendered += 1
        return [html for _, html in sorted(items, key=lambda item: item[0])], width, height

    def _preview_img(self, sprite: str, css_class: str, x: int, y: int, width: int, style_extra: str = "") -> str:
        return _sprite_html(_asset_ref(sprite), css_class, x, y, width, style_extra=style_extra)


manager = HexagonLandManager()


def _stat_asset_icon_html(sprite: str, css_class: str = "") -> str:
    asset = _asset_ref(sprite)
    return (
        f'<img class="hex-land-stat-sprite {escape(css_class)}" '
        f'src="{escape(str(asset.get("url", "")))}" alt="" aria-hidden="true">'
    )


def _coin_stat_icon_html() -> str:
    return f'<img class="hex-land-stat-sprite coin" src="/_addons/{_addon_package()}/system_files/gamification_images/hex_coin.webp" alt="" aria-hidden="true">'


def _stat_row_html(label: str, value: int, icon_html: str) -> str:
    return (
        '<div class="hex-land-stat-row">'
        f'<span class="hex-land-stat-icon">{icon_html}</span>'
        f'<span class="hex-land-stat-text">{escape(label)}: {int(value)}</span>'
        '</div>'
    )


def render_widget_html() -> str:
    state = manager.load()
    if not manager.is_enabled():
        # Render a visible disabled placeholder (matching how the Onigimon and
        # Nook Level widgets behave when their feature is off) instead of an
        # empty string. Returning "" makes the deck-browser grid drop the widget
        # entirely, so a widget placed in the grid would silently vanish.
        return f"""
    <div class="hex-land-widget disabled" ondblclick="pycmd('openHexagonLand')">
        <div class="hex-land-copy">
            <h3>{escape(tr('hexland_title'))}</h3>
            <p>{escape(tr('hexland_enable_settings', 'Enable Hexagon Land in Gamification Settings.'))}</p>
        </div>
    </div>
    """
    layers, width, height = manager.preview_layers()
    land_conf = manager.config()
    widget_display = "land_only"
    show_info = False
    scale_x = 220.0 / max(1, width)
    scale_y = 120.0 / max(1, height)
    scale = state.widget_scale if state.widget_scale > 0 else min(0.72, min(scale_x, scale_y))
    
    is_dark = False
    try:
        if mw and mw.pm.night_mode():
            is_dark = True
    except Exception:
        pass

    if is_dark:
        top_color = '#0c4a6e'
        bottom_color = '#082f49'
    else:
        top_color = '#48c0ee'
        bottom_color = '#1597d1'

    return f"""
    <style>
    @keyframes riskBlink {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.4; }}
    }}
    .risk-tile {{
        animation: riskBlink 4s ease-in-out infinite !important;
    }}
    </style>
    <div class="hex-land-widget {'land-only' if not show_info else 'land-info'}" ondblclick="pycmd('openHexagonLand')">
        <div class="hex-land-preview" style="--hl-scale: {scale:.3f}; --hl-top: {top_color}; --hl-bottom: {bottom_color};" 
             id="hl-preview-{state.created_at.replace(':', '-')}"
             data-pan-x="{state.widget_offset_x}" data-pan-y="{state.widget_offset_y}" data-scale="{scale:.3f}">
            <div class="hex-land-preview-stage" style="width:{width}px;height:{height}px; transform: translate(calc(-50% + {state.widget_offset_x}px), calc(-50% + {state.widget_offset_y}px)) scale(var(--hl-scale, .72));">
                {''.join(layers)}
            </div>
            <button class="hl-pin-btn" onclick="event.stopPropagation(); window.pinHexLandWidget(this);" style="display: none; position: absolute; bottom: 8px; right: 8px; background: rgba(255,255,255,0.9); border: 1px solid rgba(0,0,0,0.1); border-radius: 10px; padding: 4px 8px; font-size: 11px; font-weight: bold; cursor: pointer; color: #24363e; z-index: 10;">{tr('hexland_pin_position', 'Pin Position')}</button>
        </div>
        <script>
            (function() {{
                const preview = document.currentScript.previousElementSibling;
                const widget = preview.closest('.hex-land-widget');
                const stage = preview.querySelector('.hex-land-preview-stage');
                const pinBtn = preview.querySelector('.hl-pin-btn');
                let isDragging = false;
                let startX, startY;
                let startPanX = parseFloat(preview.dataset.panX || 0);
                let startPanY = parseFloat(preview.dataset.panY || 0);
                let currentPanX = startPanX;
                let currentPanY = startPanY;
                let currentScale = parseFloat(preview.dataset.scale || 0.72);
                
                function showPinBtn() {{
                    if (pinBtn) pinBtn.style.display = 'block';
                }}
                
                window.pinHexLandWidget = function(btn) {{
                    const coords = encodeURIComponent(JSON.stringify({{x: currentPanX, y: currentPanY, s: currentScale}}));
                    pycmd('hex_land_widget_pan:' + coords);
                    btn.textContent = "{tr('hexland_pinned', 'Pinned!')}";
                    setTimeout(() => {{ btn.style.display = 'none'; btn.textContent = "{tr('hexland_pin_position', 'Pin Position')}"; }}, 1500);
                }};
                
                widget.addEventListener('mousedown', e => {{
                    if (e.shiftKey) {{
                        isDragging = true;
                        startX = e.clientX;
                        startY = e.clientY;
                        startPanX = currentPanX;
                        startPanY = currentPanY;
                        e.preventDefault();
                        e.stopPropagation();
                    }}
                }});
                document.addEventListener('mousemove', e => {{
                    if (isDragging) {{
                        const dx = (e.clientX - startX) / currentScale;
                        const dy = (e.clientY - startY) / currentScale;
                        currentPanX = startPanX + dx;
                        currentPanY = startPanY + dy;
                        stage.style.transform = `translate(calc(-50% + ${{currentPanX}}px), calc(-50% + ${{currentPanY}}px)) scale(${{currentScale}})`;
                        showPinBtn();
                    }}
                }});
                document.addEventListener('mouseup', e => {{
                    if (isDragging) {{
                        isDragging = false;
                    }}
                }});
                widget.addEventListener('wheel', e => {{
                    if (!e.shiftKey) return;
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const zoomFactor = 1 - e.deltaY * 0.005;
                    let newScale = currentScale * zoomFactor;
                    newScale = Math.max(0.1, Math.min(newScale, 5.0));
                    
                    currentScale = newScale;
                    preview.style.setProperty('--hl-scale', currentScale);
                    stage.style.transform = `translate(calc(-50% + ${{currentPanX}}px), calc(-50% + ${{currentPanY}}px)) scale(${{currentScale}})`;
                    showPinBtn();
                }}, {{passive: false}});
                widget.addEventListener('click', e => {{
                    if (e.shiftKey) {{
                        e.preventDefault();
                        e.stopPropagation();
                    }}
                }}, true);
            }})();
        </script>
    </div>
    """

class HexagonLandDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("hexagon_land_window_title"))
        self.resize(1120, 760)
        self.setMinimumSize(760, 560)
        self._dirty = False
        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.render_page()

    def render_page(self) -> None:
        self.web.stdHtml(_dialog_html(manager.payload()), context=self)

    def push_payload(self) -> None:
        payload = json.dumps(manager.payload(), ensure_ascii=False)
        self.web.eval(f"window.HEX_LAND_DATA = {payload}; if (typeof render === 'function') render();")

    def closeEvent(self, event) -> None:
        if self._dirty:
            try:
                if mw and getattr(mw, "deckBrowser", None):
                    mw.deckBrowser.refresh()
            except Exception:
                pass
        super().closeEvent(event)

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd == "hex_land_guide":
            from aqt.utils import openLink

            openLink(HEXLAND_GUIDE_URL)
            return True
        if cmd == "hex_land_buy":
            from .reward_redemption import open_reward_redeem_dialog

            open_reward_redeem_dialog(self, context="hex")
            self.push_payload()
            return True
        if cmd == "hex_land_refresh":
            self.push_payload()
            return True
        if cmd == "claim_pending":
            state = manager.load()
            pending_coins = getattr(state, "pending_hex_coins", 0)
            if pending_coins > 0:
                state.hex_coins += pending_coins
                state.pending_hex_coins = 0
            pending_mats = getattr(state, "pending_materials", {})
            if pending_mats:
                for k, v in pending_mats.items():
                    state.materials[k] = int(state.materials.get(k, 0)) + v
                state.pending_materials = {}
            manager.save(state)
            self.push_payload()
            return True
        if cmd.startswith("hex_land:"):
            parts = cmd.split(":", 2)
            if len(parts) == 3:
                action = parts[1]
                try:
                    payload = json.loads(unquote(parts[2]))
                except Exception:
                    payload = {}
                manager.apply_action(action, payload)
                self._dirty = True
                self.push_payload()
                return True
        return False


_dialog: Optional[HexagonLandDialog] = None


def open_hexagon_land_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
    _dialog = HexagonLandDialog(mw)
    _dialog.show()


def open_buy_hex_coins() -> None:
    from .reward_redemption import open_reward_redeem_dialog

    open_reward_redeem_dialog(mw, context="hex")


def _dialog_html(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* { box-sizing: border-box; }
:root {
    --ocean-top: #48c0ee;
    --ocean-bottom: #1597d1;
    --ocean-wave: rgba(220, 250, 255, .055);
}
@keyframes riskBlink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}
.risk-tile {
    animation: riskBlink 4s ease-in-out infinite;
}
/* Mirrors POPPINS_WEIGHTS in fonts.py: typography is capped at Medium (500),
   so Medium claims the whole 500-900 range. Anything asking for a heavier
   weight then matches a real face and renders Medium instead of falling back
   to synthetic bolding. Poppins-Bold.ttf is deliberately not declared, and
   Poppins-Black.ttf does not ship at all. Do not add either. */
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-Light.ttf'); font-weight: 300; font-style: normal; }
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-LightItalic.ttf'); font-weight: 300; font-style: italic; }
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-Regular.ttf'); font-weight: 400; font-style: normal; }
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-Italic.ttf'); font-weight: 400; font-style: italic; }
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-Medium.ttf'); font-weight: 500 900; font-style: normal; }
@font-face { font-family: 'Poppins'; src: url('/_addons/__ADDON__/system_files/fonts/system_fonts/Poppins/Poppins-MediumItalic.ttf'); font-weight: 500 900; font-style: italic; }
html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; }
body {
    font-family: 'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--ocean-bottom);
    color: #21313a;
}
/* Anki's webview.css fights us on three fronts, each at a specificity a bare
   element selector cannot beat, so every rule below is scoped to .app:
     .fancy button      -> drop shadow on every button (body gets class "fancy")
     .fancy button:hover-> a second, larger shadow plus a transition
     .isMac button      -> hard font-size:13px, overriding our type scale
     * { box-sizing: content-box } -> padding added to every declared width */
.app,
.app *,
.app *::before,
.app *::after {
    box-sizing: border-box;
}
.app button {
    appearance: none;
    -webkit-appearance: none;
    background: transparent;
    border: 0;
    margin: 0;
    outline: none;
    box-shadow: none;
    transition: none;
    color: inherit;
    font-family: inherit;
    font-size: inherit;
    font-weight: inherit;
    line-height: inherit;
    cursor: pointer;
}
/* Deliberately no `padding: 0` above. At (0,1,1) it outranked every
   single-class control rule and silently flattened their padding; Anki's own
   `button { padding: 8px 10px }` is only (0,0,1), so any class rule beats it.
   Every button-classed control therefore states its own padding -- keep it
   that way when adding new ones. */
.app .actions button    { padding: 9px 12px; }
.app .land-choice button { padding: 9px 12px; }
.app button:hover,
.app button:focus,
.app button:active {
    box-shadow: none;
    transform: none;
    filter: none;
    transition: none;
    border: 0;
}
/* ---------------------------------------------------------------------------
   CORNER SCALE. Every control here is a <button>, so each rule needs two
   classes to outrank Anki's `.fancy button { border-radius: 15px }` (0,1,1);
   a single-class rule silently loses and the control renders with Anki's
   corner instead of ours.
     18 floating card | 16 control bar | 14 cards & blocks
     12 chips & tabs  | 10 small buttons
   --------------------------------------------------------------------------- */
.app .tool              { border-radius: 14px; }
.app .tab               { border-radius: 12px; }
.app .tool-group-toggle { border-radius: 12px; }
.app .side-toggle       { border-radius: 12px; }
.app .actions button    { border-radius: 12px; }
.app .hl-icon-btn       { border-radius: 10px; }
.app .hl-wallet-add     { border-radius: 10px; }
.app .zoom-controls button { border-radius: 10px; }
/* The tools panel floats over a full-bleed ocean instead of splitting the
   window into two columns, so the island always owns the whole canvas.
   --side-w / --side-gap are read back by the JS that keeps the island centred
   in the space the panel leaves free. */
.app {
    --side-w: 348px;
    --side-gap: 16px;
    position: relative;
    height: 100vh;
    min-width: 0;
    overflow: hidden;
}
.app.side-collapsed {
    --side-w: 0px;
}
.app.side-collapsed .side {
    display: none;
}
.side-toggle {
    position: absolute;
    top: 22px;
    right: calc(var(--side-gap) + var(--side-w) + 10px);
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    padding: 0;
    border-radius: 12px;
    background: rgba(255,255,255,.92);
    border: 1px solid rgba(33,49,58,.14);
    box-shadow: 0 2px 6px rgba(15,45,60,.14);
    cursor: pointer;
    z-index: 40;
}
.side-toggle .ui-icon {
    width: 15px;
    height: 15px;
}
.side-toggle:hover {
    background: #ffffff;
}
.world {
    position: absolute;
    inset: 0;
    min-width: 0;
    overflow: hidden;
    background-color: var(--ocean-bottom);
    background-image:
        radial-gradient(140% 74% at 50% -48%, transparent 63%, var(--ocean-wave) 64%, transparent 65%),
        radial-gradient(130% 68% at 50% -42%, transparent 69%, var(--ocean-wave) 70%, transparent 71%),
        linear-gradient(180deg, var(--ocean-top), var(--ocean-bottom));
    background-size: 260px 92px, 260px 92px, 100% 100%;
    background-position: 0 12px, 130px 58px, center center;
}
.world::before,
.world::after {
    content: none;
    position: absolute;
    inset: auto;
    width: 360px;
    height: 180px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,.14);
    opacity: .38;
    transform: rotate(-12deg);
    pointer-events: none;
}
.world::before {
    left: 10%;
    bottom: 12%;
}
.world::after {
    right: 12%;
    top: 22%;
    transform: rotate(18deg);
}
.topbar {
    position: absolute;
    left: 18px;
    right: 18px;
    top: 16px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 10px;
    pointer-events: none;
}
.brand, .wallet, .notice {
    pointer-events: auto;
    border: 2px solid rgba(33,49,58,.10);
    background: rgba(255,255,255,.92);
}
.brand {
    padding: 12px 15px;
    border-radius: 14px;
    min-width: 170px;
}
.brand h1 {
    margin: 0;
    font-size: 21px;
    line-height: 1;
    letter-spacing: 0;
}
.brand p {
    margin: 5px 0 0;
    color: #5d7681;
    font-size: 12px;
    font-weight: 500;
}
.wallet {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 10px 12px;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 500;
}
.wallet button, .side button, .tool {
    border: 0;
    cursor: pointer;
    font: inherit;
}
.wallet button {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    background: #f5bf36;
    color: #3b2604;
    display: grid;
    place-items: center;
    padding: 0;
}
.ui-icon {
    width: 18px;
    height: 18px;
    display: block;
    pointer-events: none;
}
.dark-icon {
    filter: brightness(0) invert(1);
}
.gold-icon {
    filter: brightness(0) saturate(100%) invert(16%) sepia(31%) saturate(2093%) hue-rotate(8deg) brightness(92%) contrast(98%);
}
.notice {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    padding: 10px 13px;
    border-radius: 14px;
    color: #39525b;
    font-size: 12px;
    font-weight: 500;
}
.stage-wrap {
    position: absolute;
    inset: 0;
    overflow: hidden;
    padding: 34px 34px 54px;
    display: grid;
    place-items: center;
}
.stage {
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 520px;
    min-height: 420px;
    transform-origin: center;
}
.stage-content {
    position: absolute;
    inset: 0;
    transform-origin: center center;
    will-change: transform;
}
.tile, .ghost, .obj, .hit, .hex-base {
    position: absolute;
    user-select: none;
    -webkit-user-drag: none;
}
.tile, .hl-tile {
    width: 65px;
    height: auto;
    image-rendering: auto;
    overflow: hidden;
    overflow: hidden;
}
.tile-side {
    clip-path: polygon(0 25%, 50% 50%, 100% 25%, 100% 100%, 0 100%);
}
.ghost {
    width: 65px;
    height: 89px;
    cursor: pointer;
    opacity: 1;
}
/* Expanding costs the island-level expand price, not the terrain price shown
   in the palette. Edge tiles you cannot afford yet are desaturated; the price
   itself is stated once, in the sidebar. */
.ghost-unaffordable .ghost-tile {
    filter: grayscale(.7);
}
.ghost-tile,
.placement-preview {
    position: absolute;
    left: 0;
    top: 0;
    width: 65px;
    height: auto;
    pointer-events: none;
    image-rendering: auto;
    overflow: hidden;
    overflow: hidden;
}
.ghost-tile {
    opacity: 0;
    filter: brightness(0) saturate(0) drop-shadow(0 10px 7px rgba(31, 73, 95, .28));
    transition: opacity .12s ease;
}
.ghost:hover .ghost-tile {
    opacity: .22;
}
.obj {
    pointer-events: none;
    image-rendering: auto;
    overflow: hidden;
}
.placement-preview {
    opacity: 0;
    filter: drop-shadow(0 10px 7px rgba(31, 73, 95, .16));
    transition: opacity .1s ease;
}
.placement-preview.visible {
    opacity: .74;
}
.hit {
    width: 65px;
    height: 89px;
    clip-path: polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);
    cursor: pointer;
    z-index: 9999;
    background: rgba(255,255,255,0);
}
.hit:hover {
    background: transparent;
}
.hex-base {
    width: 65px;
    height: 89px;
    clip-path: polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.16);
    pointer-events: none;
}
.side {
    position: absolute;
    top: var(--side-gap);
    right: var(--side-gap);
    bottom: var(--side-gap);
    width: var(--side-w);
    display: flex;
    flex-direction: column;
    min-width: 0;
    gap: 14px;
    padding: 16px;
    background: rgba(255,255,255,.95);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,.6);
    border-radius: 18px;
    box-shadow: 0 18px 44px rgba(10,40,56,.24), 0 2px 6px rgba(10,40,56,.10);
    overflow: auto;
    overscroll-behavior: contain;
    z-index: 30;
}
/* Scrollbar tuned for the floating card: a thin rounded thumb floating in a
   transparent track, inset far enough that the card's 18px corners never clip
   it. The transparent border plus background-clip is what creates the inset --
   ::-webkit-scrollbar-thumb has no margin.
   Do NOT add scrollbar-width/scrollbar-color here: in Chromium the standard
   properties and the ::-webkit-scrollbar pseudo-elements are mutually
   exclusive, and the standard ones win, which silently reverts all of this to
   a default overlay bar. */
.side::-webkit-scrollbar {
    width: 10px;
}
.side::-webkit-scrollbar-track {
    background: transparent;
    margin: 10px 0;
}
.side::-webkit-scrollbar-thumb {
    min-height: 32px;
    border: 3px solid transparent;
    background-clip: padding-box;
    background-color: rgba(33,49,58,.20);
    border-radius: 999px;
    transition: background-color .15s ease;
}
.side::-webkit-scrollbar-thumb:hover {
    background-color: rgba(33,49,58,.34);
}
.side::-webkit-scrollbar-thumb:active {
    background-color: rgba(33,49,58,.46);
}
.side::-webkit-scrollbar-corner {
    background: transparent;
}
/* Panels are sections of the floating card, not cards of their own -- nesting
   bordered boxes inside a bordered box reads as clutter. */
.panel {
    border: 0;
    border-radius: 0;
    background: transparent;
    padding: 0;
}
.panel + .panel {
    border-top: 1px solid rgba(33,49,58,.10);
    padding-top: 14px;
}
.panel h2 {
    margin: 0 0 10px;
    font-size: 14px;
}
.resources-panel {
    display: grid;
    gap: 12px;
}
.resources-panel.is-collapsed .hl-top-body {
    display: none;
}
.hl-top-body {
    display: grid;
    gap: 12px;
}
/* Header: name + rank on the left, level pill and the three panel controls
   (guide, minimise details, hide panel) on the right. */
.hl-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    align-items: center;
}
.hl-head-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 0 0 auto;
    margin-right: -6px;
}
/* Title and controls share a row; the subtitle gets the full width below so it
   is never squeezed into an ellipsis by the control cluster. */
.hl-head-block {
    display: grid;
    gap: 2px;
}
.hl-head h2 {
    min-width: 0;
    margin: 0;
    font-size: 19px;
    line-height: 1.15;
    letter-spacing: -.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.hl-subtitle {
    margin: 0;
    color: #7d919b;
    font-size: 11.5px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.hl-icon-btn {
    width: 26px;
    height: 26px;
    display: grid;
    place-items: center;
    padding: 0;
    border-radius: 10px;
    background: transparent;
    border: 0 !important;
    cursor: pointer;
}
.hl-icon-btn:hover {
    background: rgba(33,49,58,.06);
}
.hl-icon-btn .ui-icon {
    width: 13px;
    height: 13px;
    opacity: .45;
}
.hl-icon-btn:hover .ui-icon {
    opacity: .75;
}
.hl-level-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(33,49,58,.06);
    border: 0;
    color: #3b515c;
    font-size: 11.5px;
    font-weight: 500;
    line-height: 1.45;
    letter-spacing: .01em;
    white-space: nowrap;
}
.hl-level-progress {
    display: grid;
    gap: 6px;
}
.hl-level-progress-track {
    height: 5px;
    border-radius: 999px;
    background: rgba(33,49,58,.09);
    overflow: hidden;
}
.hl-level-progress-track span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: #24363e;
    transition: width .25s ease;
}
.hl-level-progress-meta {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    color: #7d919b;
    font-size: 11px;
    font-weight: 500;
}
/* Wallet and expand price: soft filled pills, no outlines. */
.hl-wallet {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 11px 11px 13px;
    border-radius: 14px;
    background: rgba(33,49,58,.05);
}
.hl-wallet-coin {
    width: 22px;
    height: 22px;
    object-fit: contain;
    flex: 0 0 auto;
}
.hl-wallet-value {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 17px;
    font-weight: 500;
    letter-spacing: -.01em;
}
/* Text button rather than a bare "+" glyph: it says what it does, and a flat
   background swap is the only thing that happens on hover. */
.hl-wallet-add {
    flex: 0 0 auto;
    padding: 6px 12px;
    border-radius: 10px;
    background: rgba(33,49,58,.07);
    color: #3b515c;
    border: 0 !important;
    font-size: 11.5px;
    font-weight: 500;
    letter-spacing: .01em;
    white-space: nowrap;
    cursor: pointer;
}
.hl-wallet-add:hover {
    background: rgba(33,49,58,.13);
}
/* .coin-value is still used by the dashboard widget markup. */
.coin-value {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    font-size: 15px;
    font-weight: 500;
}
.coin-value img {
    width: 22px;
    height: 22px;
    object-fit: contain;
    flex: 0 0 auto;
}
.resource-status {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-radius: 12px;
    background: transparent;
    color: #6c828c;
    padding: 2px 0;
    font-size: 12px;
    font-weight: 500;
}
.stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
}
.stat {
    border-radius: 14px;
    background: rgba(33,49,58,.05);
    border: 0;
    padding: 10px 11px;
    min-width: 0;
}
.stat b {
    display: block;
    font-size: 16px;
}
.stat span {
    color: #5e7168;
    font-size: 11px;
    font-weight: 500;
}
.stat small {
    display: block;
    margin-top: 4px;
    color: #0b7c60;
    font-size: 11px;
    font-weight: 500;
}
.tabs {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 6px;
}
.tab {
    border-radius: 12px;
    background: #f0f0f0;
    min-height: 42px;
    display: grid;
    place-items: center;
    padding: 8px 4px;
    color: #42534c;
    font-size: 11px;
    font-weight: 500;
}
.tab .ui-icon {
    width: 22px;
    height: 22px;
    opacity: .86;
}
.tab.active .ui-icon {
    filter: brightness(0) invert(1);
    opacity: 1;
}
.tab.active { background: #333333; color: #ffffff; }
.tools {
    display: grid;
    gap: 8px;
    margin-top: 10px;
}
/* Gallery layout: sprites read as a browsable grid instead of one tall
   scrolling column. Headings and subgroup labels span the full width. */
.tool-group {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
    align-items: stretch;
    gap: 8px;
}
.tool-group + .tool-group {
    margin-top: 6px;
}
.tool-group > h3,
.tool-group > .tool-subgroup {
    grid-column: 1 / -1;
}
.tool-group h3 {
    margin: 0;
}
.tool-group-toggle {
    width: 100%;
    min-height: 38px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    background: #f0f0f0;
    border: 0;
    border-radius: 12px;
    color: #26383f;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
}
.tool-group-toggle:hover {
    background: #e0e0e0;
}
.tool-group-toggle .ui-icon {
    width: 14px;
    height: 14px;
    opacity: 0.6;
    transition: transform 0.2s ease;
}
.tool-subgroup {
    margin: 2px 0 -2px;
    padding: 0 4px;
    color: #65757d;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-transform: uppercase;
}
/* Fixed-height media row, then the label. Every sprite kind -- flat png, cropped
   svg, composite building, blank icon -- centres inside the same box, so cards
   line up whatever they hold and nothing sits flush against an edge. */
.tool {
    display: grid;
    grid-template-rows: 72px auto;
    align-items: center;
    justify-items: center;
    gap: 9px;
    width: 100%;
    text-align: center;
    border-radius: 14px;
    padding: 14px 8px 15px;
    background: #fafafa;
    color: #24363e;
    border: 2px solid rgba(33,49,58,.08);
}
.tool .tool-media {
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    min-width: 0;
}
.tool .tool-label {
    display: block;
    width: 100%;
    min-width: 0;
}
.tool .tool-label small {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-width: 0;
    white-space: nowrap;
}
.tool.active {
    border-color: #0e7f60;
    background: #e8f8e8;
}
/* Erase actions: one full-width row each, icon chip beside the text. */
.tool-group-actions {
    grid-template-columns: minmax(0, 1fr);
}
/* Erase entries opt out of the sprite grid and lay out as a row instead. */
.tool-action {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 11px;
    min-height: 0;
    padding: 12px;
    text-align: left;
}
/* Two-class selectors on purpose: the sprite-card rule `.tool > span` stretches
   every child span to full width and pins it to the bottom, and it outranks a
   single class. These rows lay out side by side instead. */
.tool-action .tool-action-icon {
    flex: 0 0 auto;
    width: 34px;
    height: 34px;
    margin-top: 0;
    display: grid;
    place-items: center;
    border-radius: 12px;
    background: rgba(33,49,58,.07);
}
.tool-action .tool-action-icon .ui-icon {
    width: 16px;
    height: 16px;
    opacity: .72;
}
.tool-action .tool-action-text {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
    margin-top: 0;
}
.tool-action strong {
    font-size: 12.5px;
    white-space: normal;
}
.tool-action small {
    display: block;
    margin-top: 1px;
    color: #7d919b;
    font-size: 10.5px;
    line-height: 1.35;
    white-space: normal;
    justify-content: flex-start;
}
.tool-action.active .tool-action-icon {
    background: rgba(14,127,96,.14);
}
.tool.locked {
    opacity: .48;
    cursor: not-allowed;
}
.tool .tool-media > img,
.tool .tool-media > svg {
    max-width: 100%;
    width: 64px;
    height: 58px;
    object-fit: contain;
    image-rendering: auto;
    overflow: hidden;
}
.tool-building-sprite {
    position: relative;
    display: block;
    width: 76px;
    height: 72px;
    overflow: hidden;
}
.tool-building-sprite img,
.tool-building-sprite svg {
    position: absolute;
    object-fit: fill;
}
.tool-blank {
    width: 64px;
    height: 58px;
    display: grid;
    place-items: center;
    border-radius: 12px;
    background: #f0f0f0;
    color: #333333;
    font-size: 20px;
    font-weight: 500;
}
.tool strong {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    line-height: 1.3;
}
.tool small {
    display: block;
    color: #687971;
    font-size: 10px;
    line-height: 1.25;
    /* markup sets display:flex inline, so centre the cost row here */
    justify-content: center;
}
.actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}
.actions button {
    min-height: 38px;
    border-radius: 12px;
    background: #333333;
    color: #fff;
    font-weight: 500;
}
.actions button.secondary {
    background: #f0f0f0;
    color: #333333;
}
.zoom-controls {
    position: absolute;
    left: 18px;
    bottom: 18px;
    z-index: 24;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    border-radius: 16px;
    border: 2px solid rgba(33,49,58,.10);
    background: rgba(255,255,255,.92);
}
.zoom-controls button {
    width: 34px;
    height: 34px;
    border: 0;
    border-radius: 10px;
    background: #333333;
    color: #ffffff;
    display: grid;
    place-items: center;
    padding: 0;
    cursor: pointer;
}
.zoom-controls button.active {
    background: #f5bf36;
    color: #3b2604;
}
.zoom-controls button.active .ui-icon {
    filter: brightness(0) saturate(100%) invert(16%) sepia(31%) saturate(2093%) hue-rotate(8deg) brightness(92%) contrast(98%);
}
.zoom-controls span {
    min-width: 48px;
    text-align: center;
    font-size: 12px;
    font-weight: 500;
    color: #21313a;
}
.land-choice {
    position: absolute;
    display: flex;
    gap: 6px;
    padding: 6px;
    border-radius: 10px;
    background: rgba(255,255,255,.94);
    border: 2px solid rgba(33,49,58,.10);
    transform: translate(-50%, -100%);
    z-index: 5000;
}
.land-choice button {
    min-width: 52px;
    min-height: 30px;
    border: 0;
    border-radius: 8px;
    background: #333333;
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
}
@keyframes waterHover {
    0%, 100% { transform: translateY(0) scale(1); filter: brightness(1); }
    50% { transform: translateY(-1px) scale(1.015); filter: brightness(1.04); }
}
.water-tile.water-hover {
    animation: waterHover 1.8s ease-in-out infinite;
}
/* Narrow windows: the panel becomes a floating bottom sheet. */
@media (max-width: 900px) {
    .app { --side-w: auto; }
    .side {
        top: auto;
        left: var(--side-gap);
        right: var(--side-gap);
        bottom: var(--side-gap);
        width: auto;
        max-height: 46vh;
    }
    .side-toggle { right: var(--side-gap); }
}
body.nightMode .brand, body.nightMode .wallet, body.nightMode .notice, body.nightMode .side, body.nightMode .tool, body.nightMode .panel, body.nightMode .zoom-controls, body.nightMode .land-choice {
    background: rgba(38, 38, 38, .92);
    border-color: rgba(255, 255, 255, .1);
    color: #e0e0e0;
}
body.nightMode .side {
    background: rgba(28,28,30,.94);
    border-color: rgba(255,255,255,.10);
    box-shadow: 0 18px 44px rgba(0,0,0,.46), 0 2px 6px rgba(0,0,0,.28);
}
body.nightMode .side::-webkit-scrollbar-thumb {
    background-color: rgba(255,255,255,.20);
}
body.nightMode .side::-webkit-scrollbar-thumb:hover {
    background-color: rgba(255,255,255,.34);
}
body.nightMode .side::-webkit-scrollbar-thumb:active {
    background-color: rgba(255,255,255,.46);
}
body.nightMode .panel {
    background: transparent;
    border: 0;
}
body.nightMode .panel + .panel {
    border-top: 1px solid rgba(255,255,255,.10);
}
body.nightMode .brand p { color: #a0aab0; }
body.nightMode .stat,
body.nightMode .hl-wallet,
body.nightMode .hl-level-badge,
body.nightMode .hl-wallet-add {
    background: rgba(255,255,255,.07);
    border-color: transparent;
}
body.nightMode .hl-wallet-add {
    color: #cdd6dc;
}
body.nightMode .hl-icon-btn:hover,
body.nightMode .hl-wallet-add:hover {
    background: rgba(255,255,255,.14);
}
body.nightMode .resource-status {
    background: transparent;
}
body.nightMode .stat span,
body.nightMode .hl-subtitle,
body.nightMode .resource-status,
body.nightMode .hl-level-progress-meta {
    color: #8a9ba3;
}
body.nightMode .hl-level-badge {
    color: #d7e0e5;
}
body.nightMode .hl-level-progress-track {
    background: rgba(255,255,255,.12);
}
body.nightMode .hl-level-progress-track span {
    background: #e0e0e0;
}
body.nightMode .side-toggle {
    background: rgba(38,38,38,.94);
    border-color: rgba(255,255,255,.16);
}
body.nightMode .resource-status { color: #cdd6dc; }
body.nightMode .stat small { color: #65d7aa; }
body.nightMode .tab { background: #262626; color: #a0aab0; }
body.nightMode .tab.active { background: #4faede; color: #111d25; }
body.nightMode .tab.active .ui-icon { filter: brightness(0); }
body.nightMode .tool { background: #262626; color: #e0e0e0; border-color: rgba(255,255,255,.05); }
body.nightMode .tool.active { border-color: #4faede; background: #333333; }
body.nightMode .tool small { color: #8a9ba3; }
body.nightMode .tool-action-icon { background: rgba(255,255,255,.09); }
body.nightMode .tool-action.active .tool-action-icon { background: rgba(79,174,222,.22); }
body.nightMode .tool-blank { background: #2c2c2c; color: #a0aab0; }
body.nightMode .tool-group-toggle { background: #2c2c2c; color: #e0e0e0; }
body.nightMode .tool-group-toggle:hover { background: #333333; }
body.nightMode .actions button.secondary { background: #2c2c2c; color: #e0e0e0; }
body.nightMode .wallet button, body.nightMode .zoom-controls button.active { background: #c29729; color: #241702; }
body.nightMode .zoom-controls button { background: #2c2c2c; color: #e0e0e0; }
body.nightMode .zoom-controls span { color: #e0e0e0; }
body.nightMode .land-choice button { background: #2c2c2c; color: #e0e0e0; }
body.nightMode .ui-icon:not(.gold-icon) { filter: brightness(0) invert(1); }

/* ---------------------------------------------------------------------------
   TYPE SCALE — single source of truth.
   One family (Poppins), two weights: 400 for everything, 500 for the few things
   that lead a block. Nothing here may exceed 500: heavier values have no real
   face behind them and get synthesised, which is what made the panel look like
   several fonts at once. Sizes are fixed px, not rem: Anki sets
   html { font-size: 15px }, so rem units would drift with its theme.
   --------------------------------------------------------------------------- */
.side {
    font-size: 12px;
    font-weight: 400;
    line-height: 1.45;
    letter-spacing: 0;
}
/* UA defaults ask for bold on headings and b/strong. Cap them at Medium so no
   rule in this panel ever requests a weight the design does not use. */
.app h1, .app h2, .app h3, .app h4, .app h5, .app h6,
.app b, .app strong {
    font-weight: 500;
}
.hl-head h2        { font-size: 17px; font-weight: 500; letter-spacing: -.01em; }
.hl-subtitle       { font-size: 11.5px; font-weight: 400; }
.hl-level-badge    { font-size: 11px; font-weight: 500; letter-spacing: 0; }
.hl-level-progress-meta { font-size: 11px; font-weight: 400; }
.side .hl-wallet-value  { font-size: 19px; font-weight: 500; letter-spacing: -.01em; }
.side .hl-wallet-add    { font-size: 11.5px; font-weight: 500; }
.resource-status   { font-size: 11.5px; font-weight: 400; }
.stat b            { font-size: 17px; font-weight: 500; letter-spacing: -.01em; }
.stat span         { font-size: 11px; font-weight: 400; }
.stat small        { font-size: 10.5px; font-weight: 400; }
.panel h2          { font-size: 12.5px; font-weight: 500; letter-spacing: .01em; }
.side .tab         { font-size: 10.5px; font-weight: 400; }
/* The toggle is a <button> inside an <h3>. `.app button { font-weight: inherit }`
   outranks a single-class rule, so it picks up the h3's default bold unless the
   heading itself is normalised. */
.tool-group h3 { font-weight: 400; }
.side .tool-group-toggle { font-size: 12px; font-weight: 500; letter-spacing: 0; }
.tool-subgroup     { font-size: 10.5px; font-weight: 400; letter-spacing: .04em; }
.tool strong       { font-size: 11px; font-weight: 400; }
.tool small        { font-size: 10px; font-weight: 400; }
.tool-action strong { font-size: 12px; font-weight: 500; }
.tool-action small  { font-size: 10.5px; font-weight: 400; }
.side .zoom-controls span { font-weight: 400; }
</style>
</head>
<body>
<div id="app"></div>
<script>
window.HEX_LAND_DATA = __DATA__;
const ADDON_BASE = '/_addons/__ADDON__';
const SYSTEM_ICON_BASE = `${ADDON_BASE}/system_files/system_icons/unavailable_for_users/`;
const HEATMAP_ICON_BASE = `${ADDON_BASE}/system_files/system_icons/available_for_users/`;
const HEATMAP_ICONS = new Set(['hexagon','leaf','mountain','tree','ghost','land','nature','castle','people']);
const TILE_W = 65;
const STEP_X = 32;
const STEP_Y = 49.5;
const TILE_H = 89;
const LAND_LEVEL_STEP = 24;
const LAND_SIDE_STEP = 24;
const BUILDING_BASE_OFFSET = 28;
const BUILDING_WALL_NUDGE = 4;
const BUILDING_LEVEL_STEP = 24;
const BUILDING_ROOF_NUDGE = 68;
const BUILDING_ROOF_X_NUDGE = 0;
const BUILDING_ROOF_Y_NUDGE = 0;
const TILE_SPOTS = ['top_left', 'top_right', 'middle_left', 'center', 'middle_right', 'bottom_left', 'bottom_right'];
const LEGACY_SPOTS = {
    top: 'top_left',
    upper_left: 'top_left',
    upper_right: 'top_right',
    left: 'middle_left',
    right: 'middle_right',
    lower_left: 'bottom_left',
    lower_right: 'bottom_right',
    bottom: 'bottom_left'
};
const SPOT_DELTAS = {
    top_left: {x: -11, y: -12},
    top_right: {x: 11, y: -12},
    middle_left: {x: -19, y: 0},
    center: {x: 0, y: 4},
    middle_right: {x: 19, y: 0},
    bottom_left: {x: -11, y: 14},
    bottom_right: {x: 11, y: 14}
};
const SPOT_HIT_POINTS = {
    top_left: {x: 22, y: 20},
    top_right: {x: 44, y: 20},
    middle_left: {x: 14, y: 32},
    center: {x: 33, y: 32},
    middle_right: {x: 52, y: 32},
    bottom_left: {x: 22, y: 46},
    bottom_right: {x: 44, y: 46}
};
let selected = JSON.parse(localStorage.getItem('hexLandSelected') || 'null') || {category:'terrain', item:'grass'};
let activeTab = localStorage.getItem('hexLandTab') || 'terrain';
let zoom = Math.max(0.55, Math.min(5.0, Number(localStorage.getItem('hexLandZoom') || 1)));
let panX = Number(localStorage.getItem('hexLandPanX') || 0);
let panY = Number(localStorage.getItem('hexLandPanY') || 0);
let collapsedToolGroups = JSON.parse(localStorage.getItem('hexLandCollapsedGroups') || '{}');
let toolFlipped = localStorage.getItem('hexLandToolFlipped') === 'true';
let sideCollapsed = localStorage.getItem('hexLandSideCollapsed') === 'true';
let topCollapsed = localStorage.getItem('hexLandTopCollapsed') === 'true';
const hasSavedView = localStorage.getItem('hexLandZoom') !== null;

let audioCtx = null;
let layoutCache = null;

function softSound(freq = 420, dur = 0.055, gain = 0.018) {
    try {
        audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const g = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
        g.gain.exponentialRampToValueAtTime(gain, audioCtx.currentTime + 0.01);
        g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
        osc.connect(g);
        g.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + dur + 0.02);
    } catch (err) {}
}

function applyDayNightTheme() {
    const isDark = document.body.classList.contains('nightMode') || window.matchMedia('(prefers-color-scheme: dark)').matches;
    let top = '#48c0ee';
    let bottom = '#1597d1';
    let wave = 'rgba(220, 250, 255, .055)';
    
    if (isDark) {
        top = '#0c4a6e';
        bottom = '#082f49';
        wave = 'rgba(255, 255, 255, .03)';
        document.body.classList.add('nightMode');
    } else {
        document.body.classList.remove('nightMode');
    }

    document.documentElement.style.setProperty('--ocean-top', top);
    document.documentElement.style.setProperty('--ocean-bottom', bottom);
    document.documentElement.style.setProperty('--ocean-wave', wave);
}

function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

function iconPath(name) {
    const base = HEATMAP_ICONS.has(name) ? HEATMAP_ICON_BASE : SYSTEM_ICON_BASE;
    return `${base}${name}.svg`;
}

function faIcon(name, className = '') {
    return `<img class="ui-icon ${className}" src="${esc(iconPath(name))}" alt="" aria-hidden="true">`;
}

function spriteHtml(asset, className, style = '', attrs = '') {
    if (!asset) return '';
    const safeStyle = `${style || ''};overflow:hidden;`;
    if (asset.kind === 'svgSprite') {
        const sourceX = Number(asset.sourceX || 0);
        const sourceY = Number(asset.sourceY || 0);
        return `<svg class="${className}" ${attrs} viewBox="${esc(asset.viewBox)}" width="${Number(asset.width) || 0}" height="${Number(asset.height) || 0}" overflow="hidden" preserveAspectRatio="xMidYMid meet" style="${safeStyle}" aria-hidden="true"><image href="${esc(asset.sheet)}" x="${-sourceX}" y="${-sourceY}" width="${Number(asset.sheetWidth) || 0}" height="${Number(asset.sheetHeight) || 0}"></image></svg>`;
    }
    return `<img class="${className}" ${attrs} src="${esc(asset.url || asset)}" style="${safeStyle}" alt="">`;
}

function scaledBuildingPart(asset, width) {
    const sourceW = Number(asset?.width || width || 1);
    const sourceH = Number(asset?.height || width || 1);
    return {
        w: width,
        h: Math.round(sourceH * (width / Math.max(1, sourceW)))
    };
}

function costText(cost) {
    const parts = [];
    if (cost.coins) parts.push(cost.coins + " {tr('hexland_hex_coins', 'Hex Coins')}");
    const mats = {
        'wood': "{tr('hexland_wood', 'Wood')}",
        'stone': "{tr('hexland_stone', 'Stone')}",
        'sand': "{tr('hexland_sand', 'Sand')}",
        'crystal': "{tr('hexland_crystal', 'Crystal')}"
    };
    ['wood','stone','sand','crystal'].forEach(k => { 
        if (cost[k]) parts.push(cost[k] + ' ' + mats[k]); 
    });
    return parts.length ? parts.join(' + ') : 'Free';
}

function command(action, payload) {
    softSound(action === 'clear_tile' ? 260 : 520);
    pycmd('hex_land:' + action + ':' + encodeURIComponent(JSON.stringify(payload || {})));
}

function coords() {
    const data = window.HEX_LAND_DATA;
    const keys = Object.keys(data.state.tiles);
    const occupied = keys.map(key => key.split(',').map(Number));
    const adjacent = data.adjacent.map(c => [c.q, c.r]);
    return occupied.concat(adjacent);
}

function projectedPoints() {
    const points = coords();
    if (!points.length) return [{x: 0, y: 0}];
    return points.map(([q,r]) => ({x:(q-r)*STEP_X, y:(q+r)*STEP_Y}));
}

// The tools panel floats on top of the canvas, so "centred" means centred in
// what the panel leaves visible, not in the raw stage. Derived from constants
// rather than the DOM because computeLayout runs while the markup is being
// rebuilt, when .side still holds its previous geometry.
const SIDE_WIDTH = 348;
const SIDE_GAP = 16;
const SIDE_BREAKPOINT = 900;

function sideInsetX() {
    if (sideCollapsed || window.innerWidth <= SIDE_BREAKPOINT) return 0;
    return SIDE_WIDTH + SIDE_GAP * 2;
}

function sideInsetY() {
    if (sideCollapsed || window.innerWidth > SIDE_BREAKPOINT) return 0;
    const side = document.querySelector('.side');
    const sheetH = side ? side.getBoundingClientRect().height : window.innerHeight * 0.46;
    return sheetH + SIDE_GAP * 2;
}

// Keep the island centred in the stage itself. Offsetting it here would be
// multiplied by the zoom (.stage-content scales about its own centre); the
// floating panel is compensated for with pan instead, which sits outside the
// scaled element and so stays in screen pixels.
function computeLayout() {
    const stage = document.querySelector('.stage');
    const width = stage ? stage.clientWidth : Math.max(640, window.innerWidth);
    const height = stage ? stage.clientHeight : Math.max(420, window.innerHeight - 170);
    const projected = projectedPoints();
    const minX = Math.min(...projected.map(p => p.x));
    const minY = Math.min(...projected.map(p => p.y));
    const maxX = Math.max(...projected.map(p => p.x));
    const maxY = Math.max(...projected.map(p => p.y));
    const islandW = (maxX - minX) + TILE_W;
    const islandH = (maxY - minY) + TILE_H + 74;
    // Centre unconditionally. Clamping the origin used to shove oversized
    // islands into the top-left corner, which broke centred zooming because
    // .stage-content scales about its own centre.
    return {
        minX,
        minY,
        originX: (width - islandW) / 2,
        originY: (height - islandH) / 2 + 20
    };
}

function pos(q, r) {
    const b = layoutCache || computeLayout();
    return {x:(q-r)*STEP_X - b.minX + b.originX, y:(q+r)*STEP_Y - b.minY + b.originY};
}

function z(q, r, extra = 0) {
    return 1000000 + (q + r) * 100000 + Math.floor(extra * 100) + q * 10;
}

function setZoom(nextZoom) {
    zoom = Math.max(0.55, Math.min(10.0, nextZoom));
    localStorage.setItem('hexLandZoom', String(zoom));
    render();
    softSound(330, 0.04, 0.01);
}

function islandBounds() {
    const projected = projectedPoints();
    const xs = projected.map(p => p.x);
    const ys = projected.map(p => p.y);
    return {
        w: (Math.max(...xs) - Math.min(...xs)) + TILE_W,
        h: (Math.max(...ys) - Math.min(...ys)) + TILE_H + 74
    };
}

// Resets pan and picks the largest zoom that still shows the whole island.
// computeLayout() already centres the island inside .stage, so pan 0/0 plus a
// fitted scale puts it dead centre in the window.
function fitIsland(silent = false) {
    const wrap = document.querySelector('.stage-wrap');
    if (!wrap) return;
    const box = islandBounds();
    const insetX = sideInsetX();
    const insetY = sideInsetY();
    const availW = Math.max(120, wrap.clientWidth - 56 - insetX);
    const availH = Math.max(120, wrap.clientHeight - 56 - insetY);
    const ratio = Math.min(availW / Math.max(1, box.w), availH / Math.max(1, box.h));
    // Slide the stage clear of the floating panel. Pan is applied outside the
    // scaled content, so this stays a plain screen-pixel offset.
    panX = -insetX / 2;
    panY = -insetY / 2;
    zoom = Math.max(0.55, Math.min(3.0, ratio));
    localStorage.setItem('hexLandPanX', String(panX));
    localStorage.setItem('hexLandPanY', String(panY));
    localStorage.setItem('hexLandZoom', String(zoom));
    render();
    if (!silent) softSound(380, 0.05, 0.012);
}

function toggleSide() {
    const wasX = sideInsetX();
    const wasY = sideInsetY();
    sideCollapsed = !sideCollapsed;
    localStorage.setItem('hexLandSideCollapsed', sideCollapsed ? 'true' : 'false');
    // Reclaiming (or giving up) the panel's footprint moves the free area's
    // centre; slide the island by half that so it stays put visually.
    panX += (wasX - sideInsetX()) / 2;
    panY += (wasY - sideInsetY()) / 2;
    localStorage.setItem('hexLandPanX', String(panX));
    localStorage.setItem('hexLandPanY', String(panY));
    render();
    softSound(sideCollapsed ? 300 : 460, 0.04, 0.012);
}

function toggleTopInfo() {
    topCollapsed = !topCollapsed;
    localStorage.setItem('hexLandTopCollapsed', topCollapsed ? 'true' : 'false');
    render();
    softSound(topCollapsed ? 320 : 440, 0.04, 0.012);
}

// Land count -> level progress. Level N needs ceil(N^2 / 2) lands, so the bar
// fills across the current level's band, not from zero. The caption states the
// lands still owed rather than a ratio -- an absolute "7 / 8" next to a bar
// measuring the band (5 -> 8) reads as two different numbers for one thing.
function levelProgressHtml() {
    const data = window.HEX_LAND_DATA;
    const toNext = Math.max(0, Number(data.levelLandsToNext) || 0);
    const pct = Math.round(Math.max(0, Math.min(1, Number(data.levelFraction) || 0)) * 100);
    const nextLevel = (Number(data.level) || 0) + 1;
    const landWord = toNext === 1
        ? "{tr('hexland_land_singular', 'land')}"
        : "{tr('hexland_lands', 'lands')}";
    return `<div class="hl-level-progress">
        <div class="hl-level-progress-track"><span style="width:${pct}%"></span></div>
        <div class="hl-level-progress-meta">
            <span>${toNext} ${landWord} {tr('hexland_to_level', 'to')} {tr('hexland_level_short', 'Lv')} ${nextLevel}</span>
        </div>
    </div>`;
}


function normalizeSelectedTool() {
    const data = window.HEX_LAND_DATA;
    if (selected.category === 'raise') {
        selected = {category:'terrain', item:'grass'};
    }
    if (selected.category === 'terrain' && !data.catalog.terrains[selected.item]) {
        selected = {category:'terrain', item:'grass'};
    }
    if (selected.category === 'buildingPart' && !data.catalog.buildingParts[selected.item]) {
        const firstBuilding = Object.keys(data.catalog.buildings)[0] || '';
        selected = firstBuilding ? {category:'building', item:firstBuilding} : {category:'terrain', item:'grass'};
    }
    if (selected.category === 'building' && !data.catalog.buildings[selected.item]) {
        selected = {category:'terrain', item:'grass'};
    }
    if (selected.category === 'erase' && !data.catalog.erase[selected.item]) {
        selected = {category:'erase', item:'tile'};
    }
    localStorage.setItem('hexLandSelected', JSON.stringify(selected));
}

function toolImage(category, key) {
    const data = window.HEX_LAND_DATA;
    if (category === 'terrain') return data.assets.terrain[key];
    if (category === 'decor') return data.assets.decor[key];
    if (category === 'inhabitant') return data.assets.inhabitant[key];
    if (category === 'building') return data.assets.building[key]?.roof || data.assets.building[key]?.wall;
    if (category === 'buildingPart') return data.assets.buildingPart[key];
    if (category === 'raise') return data.assets.terrain.grass;
    if (category === 'erase') return '';
    return '';
}

function toolPreviewHtml(category, key) {
    const data = window.HEX_LAND_DATA;
    if (category === 'building' && data.assets.building[key]) {
        const b = data.assets.building[key];
        const width = 30;
        const wall = scaledBuildingPart(b.wall, width);
        const roof = scaledBuildingPart(b.roof, width + 0.5);
        const overlap = Math.round(BUILDING_ROOF_NUDGE * (width / 65));
        const totalH = wall.h + roof.h - overlap;
        const top = Math.max(0, Math.round((72 - totalH) / 2));
        const left = Math.round((76 - width) / 2);
        return `<span class="tool-building-sprite">${
            spriteHtml(b.wall, 'tool-sprite', `left:${left}px;top:${top + roof.h - overlap}px;width:${width}px !important;height:${wall.h}px !important;`)
        }${
            spriteHtml(b.roof, 'tool-sprite', `left:${left}px;top:${top}px;width:${width + 0.5}px !important;height:${roof.h}px !important;`)
        }</span>`;
    }
    if (category === 'erase') {
        const iconName = data.catalog.erase[key]?.icon || 'delete';
        return `<span class="tool-blank">${faIcon(iconName)}</span>`;
    }
    const img = toolImage(category, key);
    return img ? spriteHtml(img, 'tool-sprite') : `<span class="tool-blank">${faIcon('add')}</span>`;
}

function selectedTerrainPreview() {
    const data = window.HEX_LAND_DATA;
    if (selected.category === 'terrain' && data.assets.terrain[selected.item]) {
        return data.assets.terrain[selected.item];
    }
    return data.assets.terrain.grass || Object.values(data.assets.terrain)[0] || '';
}

function isRoofPart(partKey) {
    const baseKey = String(partKey).split(':')[0];
    const data = window.HEX_LAND_DATA;
    const item = data.catalog.buildingParts[baseKey] || {};
    if ((item.display || {}).role === 'roof') return true;
    return `${baseKey || ''} ${item.label || ''} ${item.sprite || ''}`.toLowerCase().includes('roof');
}

function buildingPartDisplay(partKey) {
    const baseKey = String(partKey).split(':')[0];
    const data = window.HEX_LAND_DATA;
    return data.catalog.buildingParts[baseKey]?.display || {x:0, y:0, w:65, role:'module'};
}

function isDetailPart(partKey) {
    return buildingPartDisplay(partKey).role === 'detail';
}

function normalizedSpot(spot) {
    spot = LEGACY_SPOTS[spot] || spot;
    return TILE_SPOTS.includes(spot) ? spot : 'center';
}

function isCenterOnlyTree(item, key = '') {
    const text = `${key || ''} ${item?.kind || ''} ${item?.label || ''} ${item?.sprite || ''}`.toLowerCase();
    return text.includes('rock') || ((text.includes('tree') || text.includes('pine')) && !text.includes('cactus'));
}

function placementSpotKeys(category = selected.category, itemKey = selected.item) {
    const data = window.HEX_LAND_DATA;
    if (category === 'decor' && isCenterOnlyTree(data.catalog.decors[itemKey], itemKey)) {
        return ['center'];
    }
    return TILE_SPOTS;
}

function spotOffset(offset, spot) {
    const delta = SPOT_DELTAS[normalizedSpot(spot)] || SPOT_DELTAS.center;
    return {
        ...offset,
        x: Number(offset?.x || 0) + delta.x,
        y: Number(offset?.y || 0) + delta.y
    };
}

function assetDisplayHeight(asset, width) {
    return Math.round((Number(asset?.height) || width) * (width / Math.max(1, Number(asset?.width) || width)));
}

function spotAnchorRole(item, category) {
    if (category === 'inhabitant') return 'foot';
    const text = `${item?.kind || ''} ${item?.label || ''} ${item?.sprite || ''}`.toLowerCase();
    return /(tree|pine|cactus)/.test(text) ? 'foot' : 'center';
}

function spotVerticalNudge(item, category) {
    if (category !== 'decor') return 0;
    const text = `${item?.kind || ''} ${item?.label || ''} ${item?.sprite || ''}`.toLowerCase();
    return ((text.includes('tree') || text.includes('pine')) && !text.includes('cactus')) ? 6 : 0;
}

function spotPlacement(item, asset, spot, category) {
    const point = SPOT_HIT_POINTS[normalizedSpot(spot)] || SPOT_HIT_POINTS.center;
    const width = Number(item?.offset?.w || (category === 'inhabitant' ? 26 : 30));
    const height = assetDisplayHeight(asset, width);
    return {
        x: Math.round(point.x - width / 2),
        y: Math.round(spotAnchorRole(item, category) === 'foot' ? point.y - height : point.y - height / 2) + spotVerticalNudge(item, category),
        w: width,
        h: height
    };
}

function spotDepth(spot) {
    const point = SPOT_HIT_POINTS[normalizedSpot(spot)] || SPOT_HIT_POINTS.center;
    return 30 + Math.round(point.y);
}

function tileSpotFromEvent(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const localX = ((event.clientX - rect.left) / Math.max(1, rect.width)) * TILE_W;
    const localY = ((event.clientY - rect.top) / Math.max(1, rect.height)) * TILE_H;
    return TILE_SPOTS.reduce((best, spot) => {
        const point = SPOT_HIT_POINTS[spot];
        const distance = Math.hypot(localX - point.x, localY - point.y);
        return distance < best.distance ? {spot, distance} : best;
    }, {spot: 'center', distance: Infinity}).spot;
}

function placementSpotFromEvent(event) {
    const spots = placementSpotKeys();
    if (spots.length === 1) return spots[0];
    const spot = tileSpotFromEvent(event);
    return spots.includes(spot) ? spot : 'center';
}

function tileSpotEntries(tile) {
    const spots = tile && typeof tile.spots === 'object' && !Array.isArray(tile.spots) ? tile.spots : {};
    const normalized = {};
    Object.entries(spots).forEach(([spot, entry]) => {
        const normalizedKey = normalizedSpot(spot);
        if (entry && entry.category && entry.item && !normalized[normalizedKey]) {
            normalized[normalizedKey] = entry;
        }
    });
    const entries = TILE_SPOTS
        .filter(spot => normalized[spot] && normalized[spot].category && normalized[spot].item)
        .map(spot => [spot, normalized[spot]]);
    if (tile?.decor && !entries.some(([spot]) => spot === 'center')) {
        entries.push(['center', {category: 'decor', item: tile.decor}]);
    }
    if (tile?.inhabitant && entries.length < TILE_SPOTS.length) {
        const openSpot = TILE_SPOTS.find(spot => !entries.some(([used]) => used === spot));
        if (openSpot) entries.push([openSpot, {category: 'inhabitant', item: tile.inhabitant}]);
    }
    return entries;
}

function buildingPartTop(parts, partKey, index, topY) {
    let wallLevels = 0;
    let roofLayers = 0;
    (Array.isArray(parts) ? parts.slice(0, index) : []).forEach(previousKey => {
        if (isDetailPart(previousKey)) {
            return;
        }
        if (isRoofPart(previousKey)) {
            roofLayers += 1;
        } else {
            wallLevels += 1;
        }
    });
    if (isDetailPart(partKey)) {
        const display = buildingPartDisplay(partKey);
        return topY - BUILDING_BASE_OFFSET - (Math.max(0, wallLevels - 1) * BUILDING_LEVEL_STEP) + (display.y || 0);
    }
    if (isRoofPart(partKey)) {
        const baseKey = String(partKey).split(':')[0];
        const asset = window.HEX_LAND_DATA.assets.buildingPart[baseKey];
        const display = buildingPartDisplay(partKey);
        const roofH = scaledBuildingPart(asset, display.w || 65).h;
        const wallTop = topY - BUILDING_BASE_OFFSET - (Math.max(0, wallLevels - 1) * BUILDING_LEVEL_STEP) + BUILDING_WALL_NUDGE;
        return wallTop - roofH + BUILDING_ROOF_NUDGE - (roofLayers * 8) + BUILDING_ROOF_Y_NUDGE;
    }
    return topY - BUILDING_BASE_OFFSET - (wallLevels * BUILDING_LEVEL_STEP) + BUILDING_WALL_NUDGE;
}

function togglePlacementPreview(key, visible, spot = '') {
    const previews = document.querySelectorAll(`[data-preview-key="${key}"]`);
    if (!visible) {
        previews.forEach(el => el.classList.remove('visible'));
        return;
    }
    document.querySelectorAll('.placement-preview.visible').forEach(el => {
        if (el.dataset.previewKey !== key || spot && el.dataset.previewSpot !== spot) {
            el.classList.remove('visible');
        }
    });
    if (spot) {
        previews.forEach(el => el.classList.toggle('visible', el.dataset.previewSpot === spot));
        return;
    }
    previews.forEach(el => el.classList.add('visible'));
}

function setWaterHover(key, hovering) {
    document.querySelectorAll(`[data-water-key="${key}"]`).forEach(el => {
        el.classList.toggle('water-hover', hovering);
    });
}

function trackPlacementPreview(event, key) {
    let spot = '';
    if (selected.category === 'decor' || selected.category === 'inhabitant') {
        spot = placementSpotFromEvent(event);
    } else if (selected.category === 'buildingPart' && isDetailPart(selected.item)) {
        const rect = event.currentTarget.getBoundingClientRect();
        const localX = ((event.clientX - rect.left) / Math.max(1, rect.width)) * TILE_W;
        spot = localX < TILE_W / 2 ? 'left' : 'right';
    }
    togglePlacementPreview(key, true, spot);
}


function placementPreview(tile, p, topY, q, r, key) {
    const data = window.HEX_LAND_DATA;
    const height = Math.max(1, Number(tile.height || 1));
    const previewAttr = `data-preview-key="${esc(key)}"`;
    const stackIndex = Array.isArray(tile.parts) ? tile.parts.length : 0;
    
    let wallLevels = 0;
    if (stackIndex > 0) {
        for (const partKey of tile.parts) {
            const pk = String(partKey).split(':')[0];
            if (isDetailPart(pk)) continue;
            if (!isRoofPart(pk)) wallLevels++;
        }
    }
    const renderTopY = topY - (wallLevels * 24);
    
    if (selected.category === 'raise' || selected.category === 'terrain') {
        const previewSrc = selected.category === 'raise' ? (data.assets.terrain[tile.terrain] || selectedTerrainPreview()) : selectedTerrainPreview();
        return spriteHtml(previewSrc, 'placement-preview ghost-tile', `left:${p.x}px;top:${renderTopY-24}px;width:65px;z-index:${z(q,r,height + 120)}`, previewAttr);
    }
    if (selected.category === 'buildingPart' && data.assets.buildingPart[selected.item]) {
        const partTop = buildingPartTop(tile.parts, selected.item, stackIndex, topY);
        const display = buildingPartDisplay(selected.item);
        if (isDetailPart(selected.item)) {
            const w = display.w || 65;
            return ['left', 'right'].map(side => {
                const sideCenter = side === 'left' ? 20 : 45;
                const sideX = sideCenter - Math.round(w / 2);
                const defaultFlip = (side === 'right');
                const finalFlipped = toolFlipped ? !defaultFlip : defaultFlip;
                const flipStyle = finalFlipped ? 'transform:scaleX(-1);' : '';
                return spriteHtml(data.assets.buildingPart[selected.item], 'placement-preview', `left:${p.x + sideX}px;top:${partTop}px;width:${w}px;${flipStyle}z-index:${z(q,r,height + 120)}`, `${previewAttr} data-preview-spot="${side}"`);
            }).join('');
        }
        const roofX = isRoofPart(selected.item) ? BUILDING_ROOF_X_NUDGE : 0;
        return spriteHtml(data.assets.buildingPart[selected.item], 'placement-preview', `left:${p.x+(display.x||0)+roofX}px;top:${partTop}px;width:${display.w||65}px;z-index:${z(q,r,height + 120)}`, previewAttr);
    }
    if (selected.category === 'building' && data.assets.building[selected.item]) {
        const b = data.assets.building[selected.item];
        const roofH = scaledBuildingPart(b.roof, 65).h;
        const roofTop = topY - 24 - roofH + BUILDING_ROOF_NUDGE + BUILDING_ROOF_Y_NUDGE;
        return [
            spriteHtml(b.wall, 'placement-preview', `left:${p.x}px;top:${topY-24}px;width:65px;z-index:${z(q,r,height + 120)}`, previewAttr),
            spriteHtml(b.roof, 'placement-preview', `left:${p.x+BUILDING_ROOF_X_NUDGE}px;top:${roofTop}px;width:65px;z-index:${z(q,r,height + 121)}`, previewAttr)
        ].join('');
    }
    if (selected.category === 'decor' && data.catalog.decors[selected.item] && data.assets.decor[selected.item]) {
        const decor = data.catalog.decors[selected.item];
        return placementSpotKeys('decor', selected.item).map(spot => {
            const off = spotPlacement(decor, data.assets.decor[selected.item], spot, 'decor');
            return spriteHtml(data.assets.decor[selected.item], 'placement-preview', `left:${p.x+(off.x||0)}px;top:${renderTopY+(off.y||0)}px;width:${off.w||30}px;height:${off.h||30}px;z-index:${z(q,r,height + 120)}`, `${previewAttr} data-preview-spot="${spot}"`);
        }).join('');
    }
    if (selected.category === 'inhabitant' && data.catalog.inhabitants[selected.item] && data.assets.inhabitant[selected.item]) {
        const person = data.catalog.inhabitants[selected.item];
        return placementSpotKeys('inhabitant', selected.item).map(spot => {
            const off = spotPlacement(person, data.assets.inhabitant[selected.item], spot, 'inhabitant');
            return spriteHtml(data.assets.inhabitant[selected.item], 'placement-preview', `left:${p.x+(off.x||0)}px;top:${renderTopY+(off.y||0)}px;width:${off.w||26}px;height:${off.h||26}px;z-index:${z(q,r,height + 120)}`, `${previewAttr} data-preview-spot="${spot}"`);
        }).join('');
    }
    return '';
}

function renderStage() {
    const data = window.HEX_LAND_DATA;
    const layers = [];
    layoutCache = computeLayout();
    Object.entries(data.state.tiles).sort((a,b) => {
        const [aq, ar] = a[0].split(',').map(Number);
        const [bq, br] = b[0].split(',').map(Number);
        return (aq + ar) - (bq + br) || aq - bq;
    }).forEach(([key, tile]) => {
        const [q, r] = key.split(',').map(Number);
        const p = pos(q, r);
        const terrain = data.catalog.terrains[tile.terrain] || data.catalog.terrains.grass;
        const height = Math.max(1, Number(tile.height || 1));
        const topY = p.y - ((height - 1) * LAND_LEVEL_STEP);
        layers.push(`<div class="hex-base" style="left:${p.x}px;top:${topY}px;z-index:${z(q,r,-1)}"></div>`);
        const tileLayers = Array.isArray(tile.layers) && tile.layers.length >= height ? tile.layers : null;
        for (let level = 1; level < height; level++) {
            const sideTerrain = tileLayers ? tileLayers[height - level - 1] : tile.terrain;
            const sideY = topY + (level * LAND_SIDE_STEP);
            layers.push(spriteHtml(data.assets.terrain[sideTerrain] || data.assets.terrain.grass, `tile tile-side ${key === data.riskTile ? 'risk-tile' : ''}`, `left:${p.x}px;top:${sideY}px;z-index:${z(q,r, height - level * 0.1)}`));
        }
        const tileKey = esc(key);
        const topTerrain = tileLayers ? tileLayers[height - 1] : tile.terrain;
        const isWater = topTerrain === 'water';
        layers.push(spriteHtml(data.assets.terrain[topTerrain] || data.assets.terrain.grass, `tile ${isWater ? 'water-tile' : ''} ${key === data.riskTile ? 'risk-tile' : ''}`, `left:${p.x}px;top:${topY}px;z-index:${z(q,r, height)}`, isWater ? `data-water-key="${tileKey}"` : ''));
        
        const stackIndex = Array.isArray(tile.parts) ? tile.parts.length : 0;
        let elevatedOffsetY = 0;
        let zBump = 0;
        if (tile.building) {
            elevatedOffsetY = 24;
        } else if (stackIndex > 0) {
            zBump = 100;
            let wallLevels = 0;
            for (const partKey of tile.parts) {
                const pk = String(partKey).split(':')[0];
                if (isDetailPart(pk)) continue;
                if (!isRoofPart(pk)) wallLevels++;
            }
            elevatedOffsetY = wallLevels * 24;
        }
        
        tileSpotEntries(tile).forEach(([spot, entry], spotIndex) => {
            if (entry.category === 'decor' && data.catalog.decors[entry.item] && data.assets.decor[entry.item]) {
                const decor = data.catalog.decors[entry.item];
                const off = spotPlacement(decor, data.assets.decor[entry.item], spot, 'decor');
                layers.push(spriteHtml(data.assets.decor[entry.item], 'obj', `left:${p.x+(off.x||0)}px;top:${topY-elevatedOffsetY+(off.y||0)}px;width:${off.w||30}px;z-index:${z(q,r,height + zBump + spotDepth(spot))}`));
            } else if (entry.category === 'inhabitant' && data.catalog.inhabitants[entry.item] && data.assets.inhabitant[entry.item]) {
                const person = data.catalog.inhabitants[entry.item];
                const off = spotPlacement(person, data.assets.inhabitant[entry.item], spot, 'inhabitant');
                layers.push(spriteHtml(data.assets.inhabitant[entry.item], 'obj', `left:${p.x+(off.x||0)}px;top:${topY-elevatedOffsetY+(off.y||0)}px;width:${off.w||26}px;z-index:${z(q,r,height + zBump + spotDepth(spot))}`));
            }
        });
        if (tile.building && data.catalog.buildings[tile.building]) {
            const b = data.assets.building[tile.building];
            const roofH = scaledBuildingPart(b.roof, 65).h;
            const roofTop = topY - 24 - roofH + BUILDING_ROOF_NUDGE + BUILDING_ROOF_Y_NUDGE;
            layers.push(spriteHtml(b.wall, 'obj', `left:${p.x}px;top:${topY-24}px;width:65px;z-index:${z(q,r,height + 60)}`));
            layers.push(spriteHtml(b.roof, 'obj', `left:${p.x+BUILDING_ROOF_X_NUDGE}px;top:${roofTop}px;width:65px;z-index:${z(q,r,height + 61)}`));
        }
        if (Array.isArray(tile.parts)) {
            tile.parts.forEach((partKey, index) => {
                const partsStr = String(partKey);
                const [basePartKey, side, dir] = partsStr.split(':');
                const src = data.assets.buildingPart[basePartKey];
                if (src) {
                    const partTop = buildingPartTop(tile.parts, partKey, index, topY);
                    const display = buildingPartDisplay(basePartKey);
                    let displayX = display.x || 0;
                    const roofX = isRoofPart(basePartKey) ? BUILDING_ROOF_X_NUDGE : 0;
                    let flipStyle = '';
                    if (isDetailPart(basePartKey) && (side === 'left' || side === 'right')) {
                        const w = display.w || 65;
                        const sideCenter = side === 'left' ? 20 : 45;
                        displayX = sideCenter - Math.round(w / 2);
                        if (dir === 'flipped') {
                            flipStyle = 'transform:scaleX(-1);';
                        }
                    }
                    layers.push(spriteHtml(src, 'obj', `left:${p.x+displayX+roofX}px;top:${partTop}px;width:${display.w||65}px;${flipStyle}z-index:${z(q,r,height + 70+index)}`));
                } else if (data.assets.terrain[basePartKey]) {
                    const baseY = topY - ((index + 1) * 24);
                    layers.push(spriteHtml(data.assets.terrain[basePartKey], 'tile', `left:${p.x}px;top:${baseY}px;z-index:${z(q,r,height + 70+index)}`));
                    layers.push(spriteHtml(data.assets.terrain[basePartKey], 'tile tile-side', `left:${p.x}px;top:${baseY + 24}px;z-index:${z(q,r,height + 70+index - 0.1)}`));
                } else if (data.assets.decor[basePartKey] && data.catalog.decors[basePartKey]) {
                    const baseY = topY - ((index + 1) * 24);
                    const off = spotPlacement(data.catalog.decors[basePartKey], data.assets.decor[basePartKey], 'center', 'decor');
                    layers.push(spriteHtml(data.assets.decor[basePartKey], 'obj', `left:${p.x+(off.x||0)}px;top:${baseY+24+(off.y||0)}px;width:${off.w||30}px;z-index:${z(q,r,height + 70+index)}`));
                } else if (data.assets.inhabitant[basePartKey] && data.catalog.inhabitants[basePartKey]) {
                    const baseY = topY - ((index + 1) * 24);
                    const off = spotPlacement(data.catalog.inhabitants[basePartKey], data.assets.inhabitant[basePartKey], 'center', 'inhabitant');
                    layers.push(spriteHtml(data.assets.inhabitant[basePartKey], 'obj', `left:${p.x+(off.x||0)}px;top:${baseY+24+(off.y||0)}px;width:${off.w||26}px;z-index:${z(q,r,height + 70+index)}`));
                }
            });
        }
        const preview = placementPreview(tile, p, topY, q, r, key);
        if (preview) layers.push(preview);
        layers.push(`<div class="hit" onmousemove="trackPlacementPreview(event,'${key}')" onmouseenter="setWaterHover('${key}', true); trackPlacementPreview(event,'${key}')" onmouseleave="setWaterHover('${key}', false); togglePlacementPreview('${key}', false)" onclick="placeAtEvent(event,${q},${r})" oncontextmenu="event.preventDefault(); clearAtEvent(event,${q},${r})" style="left:${p.x}px;top:${topY - elevatedOffsetY}px;z-index:${z(q,r,height + 140)}"></div>`);
    });
    if (selected.category === 'terrain') {
        const expandCoins = Number((data.expandCost || {}).coins) || 0;
        const canAfford = (Number(data.state.hex_coins) || 0) >= expandCoins;
        data.adjacent.forEach(c => {
            const p = pos(c.q, c.r);
            const src = selectedTerrainPreview();
            layers.push(`<div class="ghost ${canAfford ? '' : 'ghost-unaffordable'}" onclick="placeAt(${c.q},${c.r})" style="left:${p.x}px;top:${p.y}px;z-index:${z(c.q,c.r)}">${spriteHtml(src, 'ghost-tile', '')}</div>`);
        });
    }

    return layers.join('');
}

function placeAtEvent(event, q, r) {
    if (window.wasDragged) return;
    if (selected.category === 'terrain' && window.HEX_LAND_DATA.state.tiles[`${q},${r}`]) {
        command('place', {category:'terrain', item:selected.item, q, r});
        return;
    }
    let spot = '';
    if (selected.category === 'decor' || selected.category === 'inhabitant') {
        spot = placementSpotFromEvent(event);
    } else if (selected.category === 'erase') {
        spot = tileSpotFromEvent(event);
    } else if (selected.category === 'buildingPart' && isDetailPart(selected.item)) {
        const rect = event.currentTarget.getBoundingClientRect();
        const localX = ((event.clientX - rect.left) / Math.max(1, rect.width)) * TILE_W;
        spot = localX < TILE_W / 2 ? 'left' : 'right';
    }
    placeAt(q, r, spot);
}

function placeAt(q, r, spot = '') {
    if (selected.category === 'erase') {
        const payload = {q, r, layer:selected.item};
        if (selected.item === 'decor' || selected.item === 'inhabitant' || selected.item === 'spot') payload.spot = spot;
        command('clear_tile', payload);
        return;
    }
    const payload = {category:selected.category, item:selected.item, q, r};
    if (selected.category === 'decor' || selected.category === 'inhabitant') payload.spot = spot;
    if (selected.category === 'buildingPart' && isDetailPart(selected.item) && spot) {
        const defaultFlip = (spot === 'right');
        const finalFlipped = toolFlipped ? !defaultFlip : defaultFlip;
        const dir = finalFlipped ? 'flipped' : 'normal';
        payload.item = `${selected.item}:${spot}:${dir}`;
    }
    command('place', payload);
}

function clearAtEvent(event, q, r) {
    if (window.wasDragged) return;
    const spot = selected.category === 'decor' || selected.category === 'inhabitant' || selected.category === 'erase' ? tileSpotFromEvent(event) : '';
    clearAt(q, r, spot);
}

function clearAt(q, r, spot = '') {
    const layer = selected.category === 'erase' ? selected.item : selected.category === 'building' || selected.category === 'buildingPart' ? 'construction' : selected.category === 'inhabitant' ? 'inhabitant' : 'decor';
    const payload = {q, r, layer};
    if (layer === 'decor' || layer === 'inhabitant' || layer === 'spot') payload.spot = spot;
    command('clear_tile', payload);
}

function selectTool(category, item) {
    selected = {category, item};
    activeTab = category === 'buildingPart' ? 'building' : category === 'raise' ? 'terrain' : category;
    localStorage.setItem('hexLandSelected', JSON.stringify(selected));
    localStorage.setItem('hexLandTab', activeTab);
    render();
    softSound(360, 0.04, 0.012);
}

function tabs() {
    const tabData = [
        ['terrain', 'Land', 'land'],
        ['decor', 'Nature', 'nature'],
        ['building', 'Build', 'castle'],
        ['inhabitant', 'People', 'people'],
        ['erase', 'Erase', 'trash']
    ];
    return tabData.map(([id, label, iconName]) => `<button class="tab ${activeTab === id ? 'active' : ''}" aria-label="${esc(label)}" onclick="activeTab='${id}';localStorage.setItem('hexLandTab', activeTab);render();">${faIcon(iconName)}</button>`).join('');
}

function toggleToolGroup(groupName) {
    const key = `${activeTab}:${groupName || 'all'}`;
    collapsedToolGroups[key] = !collapsedToolGroups[key];
    localStorage.setItem('hexLandCollapsedGroups', JSON.stringify(collapsedToolGroups));
    render();
}

function tools() {
    const data = window.HEX_LAND_DATA;
    let groups = [['', '', []]];
    if (activeTab === 'terrain') {
        const order = [
            ['Grass', "{tr('hexland_group_grass', 'Grass')}"],
            ['Water', "{tr('hexland_group_water', 'Water')}"],
            ['Lava', "{tr('hexland_group_lava', 'Lava')}"],
            ['Sand', "{tr('hexland_group_sand', 'Sand')}"],
            ['Dirt', "{tr('hexland_group_dirt', 'Dirt')}"],
            ['Stone', "{tr('hexland_group_stone', 'Stone')}"],
            ['Snow', "{tr('hexland_group_snow', 'Snow')}"],
            ['Magic', "{tr('hexland_group_magic', 'Magic')}"],
            ['Others', "{tr('hexland_group_ground_patch', 'Ground patch')}"]
        ];
        groups = order.map(([key, label]) => [
            key,
            label,
            Object.entries(data.catalog.terrains)
                .filter(([, item]) => (item.groupKey || item.group || 'Others') === key)
                .map(([id, item]) => ['terrain', id, item])
        ]).filter(([, , entries]) => entries.length);
    } else if (activeTab === 'decor') {
        const order = [
            ['Trees', "{tr('hexland_group_trees', 'Trees')}"],
            ['Flowers', "{tr('hexland_group_flowers', 'Flowers')}"],
            ['Grass', "{tr('hexland_group_grass', 'Grass')}"],
            ['Rocks', "{tr('hexland_group_rocks', 'Rocks')}"],
            ['Hills', "{tr('hexland_group_hills', 'Hills')}"],
            ['Ridges', "{tr('hexland_group_ridges', 'Ridges')}"],
            ['Others', "{tr('hexland_group_ground_patch', 'Ground patch')}"]
        ];
        groups = order.map(([key, label]) => [
            key,
            label,
            Object.entries(data.catalog.decors)
                .filter(([, item]) => (item.groupKey || item.group || 'Others') === key)
                .map(([id, item]) => ['decor', id, item])
        ]).filter(([, , entries]) => entries.length);
    } else if (activeTab === 'building') {
        const order = [
            ['Full', "{tr('hexland_group_full', 'Full')}", []],
            ['Dark Stone', "{tr('hexland_group_dark_stone', 'Dark Stone')}", []],
            ['Light Stone', "{tr('hexland_group_light_stone', 'Light Stone')}", []],
            ['Sand', "{tr('hexland_group_sand', 'Sand')}", []],
            ['Clay', "{tr('hexland_group_clay', 'Clay')}", []]
        ];
        Object.entries(data.catalog.buildingParts).forEach(([id, item]) => {
            const groupName = item.groupKey || item.group || '';
            const group = order.find(([name]) => name === groupName);
            if (group) group[2].push(['buildingPart', id, item]);
        });
        Object.entries(data.catalog.buildings).forEach(([id, item], index) => {
            const group = order[0];
            group[2].push(['building', id, {...item, order: index, subgroup: ''}]);
        });
        groups = order.map(([groupName, groupLabel, entries]) => {
            const sortedEntries = entries.slice().sort((left, right) => Number(left[2]?.order ?? 9000) - Number(right[2]?.order ?? 9000));
            const groupedEntries = [];
            let currentSubgroup = '';
            sortedEntries.forEach(entry => {
                const subgroup = entry[2]?.subgroup || '';
                if (subgroup && subgroup !== currentSubgroup) {
                    currentSubgroup = subgroup;
                    groupedEntries.push(['subgroup', subgroup, {label: subgroup}]);
                }
                groupedEntries.push(entry);
            });
            return [groupName, groupLabel, groupedEntries];
        }).filter(([, , entries]) => entries.length);
    } else if (activeTab === 'inhabitant') {
        groups[0][2] = Object.entries(data.catalog.inhabitants).map(([id, item]) => ['inhabitant', id, item]);
    } else {
        groups[0][2] = Object.entries(data.catalog.erase).map(([id, item]) => ['erase', id, item]);
    }
    return groups.map(([groupName, groupLabel, entries]) => {
        const collapseKey = `${activeTab}:${groupName || 'all'}`;
        const collapsed = !!collapsedToolGroups[collapseKey];
        const buttons = entries.map(([category, id, item]) => {
            if (category === 'subgroup') {
                return `<div class="tool-subgroup">${esc(item.label || id)}</div>`;
            }
            const active = selected.category === category && selected.item === id;
            // Erase entries are actions, not sprites: a full-width row with the
            // icon beside the text, so nothing is squeezed into an empty
            // thumbnail box or truncated to an ellipsis.
            if (category === 'erase') {
                const iconName = item.icon || 'delete';
                return `<button class="tool tool-action ${active ? 'active' : ''}" onclick="selectTool('${category}','${id}')">
                    <span class="tool-action-icon">${faIcon(iconName)}</span>
                    <span class="tool-action-text"><strong>${esc(item.label)}</strong><small>${esc(item.hint || '')}</small></span>
                </button>`;
            }
            const locked = (category === 'terrain' && !data.unlockedTerrains.includes(id)) || (category === 'inhabitant' && data.builtLands < (item.unlock_lands || 0));
            const unlock = item.hint || (locked ? (category === 'inhabitant' ? `{tr('hexland_unlocks_at', 'Unlocks at')} ${item.unlock_lands || 0} {tr('hexland_lands', 'lands')}` : `{tr('hexland_unlocks_after', 'Unlocks after')} ${item.unlock} {tr('hexland_reviews', 'reviews')}`) : costText(item.cost || {}));
            // Beside a hex-coin glyph the words "Hex Coins" are redundant, and
            // spelling them out wraps the price onto two lines in a card this
            // narrow. Show the number; the full phrasing stays in the tooltip.
            const coinCost = Number((item.cost || {}).coins) || 0;
            const compactCost = coinCost ? String(coinCost) : unlock;
            const unlockHtml = (unlock === item.hint || locked || unlock === 'Free') ? esc(unlock) : `<span style="display: inline-block; width: 11px; height: 11px; flex: 0 0 auto; opacity: 0.7; background-color: currentColor; -webkit-mask: url(/_addons/__ADDON__/system_files/system_icons/available_for_users/hexagon.svg) no-repeat center / contain; mask: url(/_addons/__ADDON__/system_files/system_icons/available_for_users/hexagon.svg) no-repeat center / contain;"></span>` + esc(compactCost);
            return `<button class="tool ${active ? 'active' : ''} ${locked ? 'locked' : ''}" ${locked ? '' : `onclick="selectTool('${category}','${id}')"`}>
                <span class="tool-media">${toolPreviewHtml(category, id)}</span>
                <span class="tool-label"><strong>${esc(item.label)}</strong><small title="${esc(unlock)}">${unlockHtml}</small></span>
            </button>`;
        }).join('');
        const header = groupName ? `<h3><button class="tool-group-toggle" onclick="toggleToolGroup('${esc(groupName)}')"><span>${esc(groupLabel || groupName)}</span>${faIcon(collapsed ? 'right' : 'down')}</button></h3>` : '';
        return `<div class="tool-group ${activeTab === 'erase' ? 'tool-group-actions' : ''}">${header}${collapsed ? '' : buttons}</div>`;
    }).join('');
}

function coinLabelHtml(value, label = null) {
    const displayLabel = label || "{tr('hexland_hex_coins', 'Hex Coins')}";
    return `<span class="coin-value"><img src="/_addons/__ADDON__/system_files/gamification_images/hex_coin.webp" alt=""> <span>${esc(value)} ${esc(displayLabel)}</span></span>`;
}

// Wallets can reach ten digits; abbreviate so the pill never wraps. The exact
// figure stays available as a tooltip.
function formatCoins(value) {
    const n = Math.floor(Number(value) || 0);
    if (n < 100000) return n.toLocaleString();
    const units = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']];
    for (const [size, suffix] of units) {
        if (n >= size) {
            const scaled = n / size;
            return (scaled >= 100 ? Math.round(scaled) : scaled.toFixed(1).replace(/\\.0$/, '')) + suffix;
        }
    }
    return String(n);
}

function fullCoinText(value) {
    return `${(Math.floor(Number(value) || 0)).toLocaleString()} {tr('hexland_hex_coins', 'Hex Coins')}`;
}

function formatCoinRate(value) {
    const rate = Number(value) || 1;
    return Number.isInteger(rate) ? String(rate) : rate.toFixed(2).replace(/0+$/, '').replace(/\\.$/, '');
}

function compactStatusText(message) {
    const text = String(message || '');
    const match = text.match(/^Synced\\s+(\\d+)\\s+(?:missing\\s+Hexagon Land\\s+review\\(s\\)\\s+from Anki\\.|reviews\\.|synced\\.)$/i);
    if (match) {
        return "{tr('hexland_synced_reviews', '{} synced.')}".replace('{}', match[1]);
    }
    return text || "{tr('hexland_default_status', 'Study to grow your island.')}";
}

function render() {
    const sideEl = document.querySelector('.side');
    const savedScrollTop = sideEl ? sideEl.scrollTop : 0;
    applyDayNightTheme();
    const data = window.HEX_LAND_DATA;
    normalizeSelectedTool();
    const s = data.state;
    const m = s.materials;
    const treeCoinBonus = (Number(data.trees) || 0) * 0.10;
    const flowerCoinBonus = (Number(data.flowers) || 0) * 0.05;
    const totalNatureBonus = Math.min(treeCoinBonus + flowerCoinBonus, 20);
    const todayReviews = Number(data.todayReviews ?? s.today_reviews) || 0;
    let noticeText = compactStatusText(s.last_message);
    if (selected.category === 'buildingPart' && isDetailPart(selected.item)) {
        const label = data.catalog.buildingParts[selected.item]?.label || selected.item;
        noticeText = `Placing ${label}. Press [R] to flip direction (current: ${toolFlipped ? 'flipped' : 'normal'}).`;
    }
    document.getElementById('app').innerHTML = `
        <div class="app ${sideCollapsed ? 'side-collapsed' : ''}">
            <main class="world">
                <div class="stage-wrap"><div class="stage" style="transform:translate(${panX}px, ${panY}px);"><div class="stage-content" style="transform:scale(${zoom});">${renderStage()}</div></div></div>
                ${sideCollapsed ? `<button class="side-toggle" aria-label="{tr('hexland_toggle_panel', 'Show or hide the tools panel')}" title="{tr('hexland_toggle_panel', 'Show or hide the tools panel')}" onclick="toggleSide()">${faIcon('angle-left')}</button>` : ''}
                <div class="zoom-controls">
                    <button aria-label="Zoom out" onclick="setZoom(zoom - 0.1)">${faIcon('minus', 'dark-icon')}</button>
                    <span>${Math.round(zoom * 100)}%</span>
                    <button aria-label="Zoom in" onclick="setZoom(zoom + 0.1)">${faIcon('add', 'dark-icon')}</button>
                    <button aria-label="{tr('hexland_fit_island', 'Fit island to view')}" title="{tr('hexland_fit_island', 'Fit island to view')}" onclick="fitIsland()">${faIcon('mode-focus-eye', 'dark-icon')}</button>
                    <button aria-label="Clear spot" class="${selected.category === 'erase' && selected.item === 'spot' ? 'active' : ''}" onclick="selectTool('erase','spot')">${faIcon('cancel', 'dark-icon')}</button>
                </div>
            </main>
            <aside class="side">
                <section class="panel resources-panel ${topCollapsed ? 'is-collapsed' : ''}">
                    <div class="hl-head-block">
                        <div class="hl-head">
                            <h2>{tr('hexland_title', 'Hexagon Land')}</h2>
                            <div class="hl-head-actions">
                            <span class="hl-level-badge">{tr('hexland_level_short', 'Lv')} ${data.level}</span>
                            <button class="hl-icon-btn" aria-label="{tr('hexland_open_guide', 'Open the Hexagon Land guide')}" title="{tr('hexland_open_guide', 'Open the Hexagon Land guide')}" onclick="pycmd('hex_land_guide'); softSound(560);">${faIcon('info-circle')}</button>
                            <button class="hl-icon-btn" aria-label="${topCollapsed ? "{tr('hexland_show_stats', 'Show island details')}" : "{tr('hexland_hide_stats', 'Hide island details')}"}" title="${topCollapsed ? "{tr('hexland_show_stats', 'Show island details')}" : "{tr('hexland_hide_stats', 'Hide island details')}"}" aria-expanded="${topCollapsed ? 'false' : 'true'}" onclick="toggleTopInfo()">${faIcon(topCollapsed ? 'down' : 'up')}</button>
                            <button class="hl-icon-btn" aria-label="{tr('hexland_toggle_panel', 'Show or hide the tools panel')}" title="{tr('hexland_toggle_panel', 'Show or hide the tools panel')}" onclick="toggleSide()">${faIcon('right')}</button>
                            </div>
                        </div>
                        <p class="hl-subtitle">${esc(data.levelTitle)} &middot; ${todayReviews} {tr('hexland_reviews_today', 'reviews today')}</p>
                    </div>
                    <div class="hl-top-body">
                        ${levelProgressHtml()}
                        <div class="hl-wallet">
                            <img class="hl-wallet-coin" src="/_addons/__ADDON__/system_files/gamification_images/hex_coin.webp" alt="">
                            <span class="hl-wallet-value" title="${esc(fullCoinText(s.hex_coins))}">${esc(formatCoins(s.hex_coins))}</span>
                            <button class="hl-wallet-add" aria-label="Redeem {tr('hexland_hex_coins', 'Hex Coins')}" onclick="event.stopPropagation(); pycmd('hex_land_buy'); softSound(700);">{tr('hexland_get_more', 'Get more')}</button>
                        </div>
                        <div class="resource-status">${esc(noticeText)}</div>
                        <div class="stats">
                            <div class="stat"><b>${data.builtLands}</b><span>{tr('hexland_lands', 'lands')}</span></div>
                            <div class="stat"><b>${formatCoinRate(data.coinRate)}x</b><span>{tr('hexland_coin_rate', 'coin rate')}</span><small>+${Math.round(totalNatureBonus * 100)}%</small></div>
                            <div class="stat"><b>${data.trees}</b><span>{tr('hexland_trees', 'trees')}</span><small>+${Math.round(treeCoinBonus * 100)}%</small></div>
                            <div class="stat"><b>${data.flowers}</b><span>{tr('hexland_flowers', 'flowers')}</span><small>+${Math.round(flowerCoinBonus * 100)}%</small></div>
                        </div>
                    </div>
                </section>
                <section class="panel">
                    <h2>{tr('hexland_hexagons_panel', 'Hexagons')}</h2>
                    <div class="tabs">${tabs()}</div>
                    <div class="tools">${tools()}</div>
                </section>
            </aside>
        </div>`;
    const newSideEl = document.querySelector('.side');
    if (newSideEl) newSideEl.scrollTop = savedScrollTop;
}
window.wasDragged = false;
let isDragging = false;
let startDragX = 0;
let startDragY = 0;
let startPanX = 0;
let startPanY = 0;

document.addEventListener('pointerdown', e => {
    if (e.target.closest('button, .tab, .tool')) return;
    if (e.button === 1 || e.button === 2) {
        isDragging = true;
        window.wasDragged = false;
        startDragX = e.clientX;
        startDragY = e.clientY;
        startPanX = panX;
        startPanY = panY;
    }
});

document.addEventListener('pointermove', e => {
    if (isDragging) {
        const dx = e.clientX - startDragX;
        const dy = e.clientY - startDragY;
        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
            window.wasDragged = true;
        }
        if (window.wasDragged) {
            panX = startPanX + dx;
            panY = startPanY + dy;
            const stage = document.querySelector('.stage');
            if (stage) stage.style.transform = `translate(${panX}px, ${panY}px)`;
        }
    }
});

document.addEventListener('pointerup', e => {
    if (isDragging && (e.button === 1 || e.button === 2)) {
        isDragging = false;
        localStorage.setItem('hexLandPanX', String(panX));
        localStorage.setItem('hexLandPanY', String(panY));
        setTimeout(() => { window.wasDragged = false; }, 50);
    }
});

document.addEventListener('contextmenu', e => {
    if (window.wasDragged) {
        e.preventDefault();
    }
});

document.addEventListener('wheel', e => {
    if (!e.target.closest('.stage-wrap')) return;
    if (e.ctrlKey) {
        e.preventDefault();
        const zoomDelta = -e.deltaY * 0.005;
        setZoom(zoom + zoomDelta);
    } else {
        panX -= e.deltaX;
        panY -= e.deltaY;
        const stage = document.querySelector('.stage');
        if (stage) stage.style.transform = `translate(${panX}px, ${panY}px)`;
        localStorage.setItem('hexLandPanX', String(panX));
        localStorage.setItem('hexLandPanY', String(panY));
        e.preventDefault();
    }
}, {passive: false});

document.addEventListener('keydown', e => {
    if (e.key.toLowerCase() === 'r') {
        if (selected.category === 'buildingPart' && isDetailPart(selected.item)) {
            toolFlipped = !toolFlipped;
            localStorage.setItem('hexLandToolFlipped', String(toolFlipped));
            render();
            softSound(480, 0.05, 0.015);
        }
    }
});

render();

// First ever open: frame the whole island instead of dropping the user at 100%
// on an arbitrary corner. Deferred so .stage-wrap has real dimensions.
if (!hasSavedView) {
    requestAnimationFrame(() => fitIsland(true));
}

let resizeFitTimer = null;
window.addEventListener('resize', () => {
    clearTimeout(resizeFitTimer);
    resizeFitTimer = setTimeout(() => render(), 120);
});

if (window.HEX_LAND_DATA.pendingCoins > 0 || Object.keys(window.HEX_LAND_DATA.pendingMaterials || {}).length > 0) {
    const data = window.HEX_LAND_DATA;
    const toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;top:40px;left:50%;transform:translateX(-50%);background:#1597d1;color:white;padding:12px 24px;border-radius:20px;font-weight:bold;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.5s;';
    
    let parts = [];
    const coinIcon = "/_addons/__ADDON__/system_files/gamification_images/hex_coin.webp";
    if (data.pendingCoins > 0) {
        parts.push(`<span style="display:inline-flex;align-items:center;gap:5px;"><img src="${coinIcon}" alt="" style="width:20px;height:20px;object-fit:contain;">${data.pendingCoins}</span>`);
    }
    for (const [k, v] of Object.entries(data.pendingMaterials || {})) {
        parts.push(`<span>${v} ${esc(k)}</span>`);
    }
    toast.innerHTML = "{tr('hexland_earned_session_ui', 'Session Rewards:')} " + parts.join(" ");
    document.body.appendChild(toast);
    softSound(700);
    
    setTimeout(() => { toast.style.opacity = '0'; }, 3000);
    setTimeout(() => { toast.remove(); }, 3500);
    
    const walletSpan = document.querySelector('.hl-wallet-value');
    if (walletSpan && data.pendingCoins > 0) {
        let current = data.state.hex_coins;
        let target = current + data.pendingCoins;
        let step = Math.max(1, Math.floor(data.pendingCoins / 20));
        let intv = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(intv);
                pycmd('claim_pending');
            }
            walletSpan.textContent = formatCoins(current);
            walletSpan.title = fullCoinText(current);
        }, 50);
    } else {
        pycmd('claim_pending');
    }
}
</script>
</body>
</html>
""".replace("__DATA__", data).replace("__ADDON__", _addon_package())
    
    import re
    from ..translations import tr
    def replacer(m): return str(tr(m.group(1), m.group(2)))
    return re.sub(r"\{tr\('([^']+)',\s*'([^']+)'\)\}", replacer, html)


def register_hooks() -> None:
    gui_hooks.reviewer_did_answer_card.append(manager.on_answer)
    gui_hooks.state_did_change.append(manager.on_state_did_change)
    gui_hooks.webview_will_set_content.append(manager.on_webview_will_set_content)
