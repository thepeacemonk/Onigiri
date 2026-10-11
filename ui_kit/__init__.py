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
  fonts          font registry and Qt/web font helpers
  emoji_sprites  emoji asset registry
  onigiri_color_picker, onigiri_date_picker  shared native pickers
  onigiri_notifications  native notifications
  menu_buttons   Onigiri menu actions
"""

__all__ = ["FlowLayout"]


def __getattr__(name):
    # Asset registries can be imported without loading the native Qt widgets.
    if name == "FlowLayout":
        from .flow_layout import FlowLayout

        globals()[name] = FlowLayout
        return FlowLayout
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
