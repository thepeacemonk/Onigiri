"""Shared, ordered catalog for independently selectable Pomodoro tone pairs."""

# Existing keys stay valid so saved Start/End choices are not reset.
# Family id, display name, start key, end key.
TONE_PAIRS = (
    ("soft_bell", "Soft Bell", "soft_start", "soft_bell"),
    ("classic_chime", "Classic Chime", "classic_chime_start", "classic_chime"),
    ("bamboo", "Bamboo", "bamboo_start", "bamboo_end"),
    ("glass", "Glass", "glass_start", "glass_end"),
    ("digital", "Digital", "digital_start", "digital_end"),
    ("warm_keys", "Warm Keys", "warm_keys_start", "warm_keys_end"),
    ("singing_bowl", "Singing Bowl", "singing_bowl_start", "singing_bowl_end"),
)

BUILTIN_SOUNDS = {
    sound_key: f"pomodoro_{family}_{event}.wav"
    for family, _label, start_key, end_key in TONE_PAIRS
    for event, sound_key in (("start", start_key), ("end", end_key))
}
