"""Data engine for Kome's optional advanced statistics view.

The original attachment shipped as a standalone add-on with its own Qt
dialog, Anki menubar entry, and remote web dependencies. Onigiri consumes only
the collection-analysis layer: Kome owns the visible HTML, CSS, icons, and
navigation, so enabling the feature never installs parallel application
chrome or a second settings surface.
"""

from .formatter import build_dashboard_data

__all__ = ("build_dashboard_data",)
