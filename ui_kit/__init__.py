"""Qt building blocks shared by the dialogs that are *not* the settings window.

The classic PyQt settings dialog used to own all of this under `settings/`, and
Gamification, Prep Station, Hashi Notes and the deck renderer imported it from
there. `settings/` is gone — the settings window is `settings_web/` now — so the
handful of pieces with real users outside it live here:

  flow_layout    FlowLayout          wrapping QLayout
  common         system_icon_path, svg_contain_rect, icon/SVG helpers
  widgets        AnimatedToggleButton, MainBackgroundEffectSlider
  picker_chrome  shared popup chrome for the pickers below
  font_picker    FontPickerDialog
  icon_picker    DeckIconPickerDialog
"""

from .flow_layout import FlowLayout

__all__ = ["FlowLayout"]
