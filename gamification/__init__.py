import importlib

__all__ = [
    'gamification',
    'mochi_messages',
    'mod_transfer_window',
    'onigimon',
    'nook_level',
    'hexagon_land',
    'focus_dango',
    'reward_redemption',
    'nook_web_ui',
    'onigimon_web_ui',
]


def __getattr__(name):
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
