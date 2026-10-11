import os


EMOJI_SPRITES = [
    {"value": "🤍", "label": "White Heart", "asset": "heart_white.svg"},
    {"value": "🧼", "label": "Soap", "asset": "soap.svg"},
    {"value": "💀", "label": "Skull", "asset": "skull.svg"},
    {"value": "📄", "label": "Paper", "asset": "paper.svg"},
    {"value": "📝", "label": "Memo", "asset": "memo.svg"},
    {"value": "📖", "label": "Open Book", "asset": "open_book.svg"},
    {"value": "🍙", "label": "Onigiri", "asset": "onigiri.svg"},
    {"value": "🩷", "label": "Light Pink Heart", "asset": "heart_light_pink.svg"},
    {"value": "💕", "label": "Two Hearts", "asset": "two_hearts.svg"},
    {"value": "🌸", "label": "Cherry Blossom", "asset": "cherry_blossom.svg"},
    {"value": "🌷", "label": "Tulip", "asset": "tulip.svg"},
    {"value": "🪷", "label": "Lotus", "asset": "lotus.svg"},
    {"value": "🧠", "label": "Brain", "asset": "brain.svg"},
    {"value": "🦑", "label": "Squid", "asset": "squid.svg"},
    {"value": "❤️", "label": "Red Heart", "asset": "heart_red.svg"},
    {"value": "🫀", "label": "Anatomical Heart", "asset": "anatomical_heart.svg"},
    {"value": "📕", "label": "Red Book", "asset": "red_book.svg"},
    {"value": "🔥", "label": "Fire", "asset": "fire.svg"},
    {"value": "🍉", "label": "Watermelon", "asset": "watermelon.svg"},
    {"value": "🧡", "label": "Orange Heart", "asset": "heart_orange.svg"},
    {"value": "🍊", "label": "Tangerine", "asset": "tangerine.svg"},
    {"value": "🍹", "label": "Tropical Drink", "asset": "tropical_drink.svg"},
    {"value": "🧇", "label": "Waffle", "asset": "waffle.svg"},
    {"value": "🍍", "label": "Pineapple", "asset": "pineapple.svg"},
    {"value": "⭐", "label": "Star", "asset": "star.svg"},
    {"value": "✨", "label": "Sparkle", "asset": "sparkle.svg"},
    {"value": "⚡", "label": "Bolt", "asset": "bolt.svg"},
    {"value": "🏆", "label": "Trophy", "asset": "trophy.svg"},
    {"value": "💛", "label": "Yellow Heart", "asset": "heart_yellow.svg"},
    {"value": "📙", "label": "Yellow Book", "asset": "yellow_book.svg"},
    {"value": "✏️", "label": "Pen", "asset": "pen.svg"},
    {"value": "🍋‍🟩", "label": "Lime", "asset": "lime.svg"},
    {"value": "💚", "label": "Green Heart", "asset": "heart_green.svg"},
    {"value": "📗", "label": "Green Book", "asset": "green_book.svg"},
    {"value": "🌱", "label": "Plant", "asset": "emoji.svg"},
    {"value": "🍀", "label": "Four Leaf Clover", "asset": "four_leaf_clover.svg"},
    {"value": "🍃", "label": "Leaf Fluttering In Wind", "asset": "leaf_fluttering_in_wind.svg"},
    {"value": "🌳", "label": "Deciduous Tree", "asset": "deciduous_tree.svg"},
    {"value": "🌲", "label": "Evergreen Tree", "asset": "evergreen_tree.svg"},
    {"value": "🎄", "label": "Christmas Tree", "asset": "christmas_tree.svg"},
    {"value": "🍵", "label": "Teacup", "asset": "teacup_without_handle.svg"},
    {"value": "💙", "label": "Blue Heart", "asset": "blue_heart.svg"},
    {"value": "📘", "label": "Blue Book", "asset": "blue_book.svg"},
    {"value": "💧", "label": "Droplet", "asset": "droplet.svg"},
    {"value": "💎", "label": "Gem Stone", "asset": "gem_stone.svg"},
    {"value": "🧪", "label": "Test Tube", "asset": "test_tube.svg"},
    {"value": "🍇", "label": "Grapes", "asset": "grapes.svg"},
    {"value": "🔬", "label": "Microscope", "asset": "microscope.svg"},
    {"value": "💻", "label": "Computer", "asset": "computer.svg"},
    {"value": "📟", "label": "Pager", "asset": "pager.svg"},
    {"value": "🎮", "label": "Videogame", "asset": "videogame.svg"},
    {"value": "🍡", "label": "Dango", "asset": "dango.svg"},
    {"value": "📚", "label": "Books", "asset": "books.svg"},
    {"value": "🗺️", "label": "World Map", "asset": "world_map.svg"},
]

def _emoji_key(value):
    return str(value or "").replace("\ufe0e", "").replace("\ufe0f", "")


EMOJI_TO_ASSET = {}
for item in EMOJI_SPRITES:
    EMOJI_TO_ASSET[item["value"]] = item["asset"]
    EMOJI_TO_ASSET[_emoji_key(item["value"])] = item["asset"]


def asset_for_emoji(emoji):
    emoji = str(emoji or "")
    return EMOJI_TO_ASSET.get(emoji) or EMOJI_TO_ASSET.get(_emoji_key(emoji))


def path_for_emoji(addon_path, emoji):
    asset = asset_for_emoji(emoji)
    if not asset:
        return ""
    path = os.path.join(addon_path, "system_files", "emojis", asset)
    return path if os.path.exists(path) else ""
