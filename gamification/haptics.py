"""Small, safe macOS haptic bridge shared by the mini-games."""

from __future__ import annotations


def trigger(pattern: int = 1) -> None:
    """Request native feedback when the current platform supports it.

    The settings WebUI owns the low-level Objective-C boundary.  Keeping this
    adapter tiny means every game gets identical macOS behaviour while the
    game code remains a no-op on Windows and Linux.
    """
    try:
        from ..settings_web.dialog import _trigger_mac_haptic_native

        _trigger_mac_haptic_native(pattern)
    except Exception:
        # Haptics are enhancement only; a missing runtime must never block a
        # game action or reviewer notification.
        pass
