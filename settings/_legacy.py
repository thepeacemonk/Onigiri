# Assembly facade for the settings dialog. Real code lives in the split modules.
from ._common import *
from ._color_picker import *
from ._icon_picker import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *
from ._infra import InfraMixin, InfraMixin2
from ._page_colors import PageColorsMixin
from ._page_themes import PageThemesMixin, PageThemesMixin2
from ._page_fonts import PageFontsMixin
from ._page_sidebar import PageSidebarMixin
from ._dialog_core import DialogCoreMixin, DialogCoreMixin2
from ._page_sync import PageSyncMixin
from ._page_profile import PageProfileMixin
from ._page_mainmenu import PageMainmenuMixin
from ._page_backgrounds import PageBackgroundsMixin, PageBackgroundsMixin2
from ._page_reviewer import PageReviewerMixin, PageReviewerMixin2
from ._page_hidemodes import PageHidemodesMixin
from ._page_overviews import PageOverviewsMixin
from ._page_languages import PageLanguagesMixin
from ._page_gallery import PageGalleryMixin
from ._page_study_tools import PageStudyToolsMixin
from ._page_hashi_notes import PageHashiNotesMixin
from . import _infra, _page_colors, _page_themes, _page_fonts, _page_sidebar, _dialog_core, _page_sync, _page_profile, _page_mainmenu, _page_backgrounds, _page_reviewer, _page_hidemodes, _page_overviews, _page_languages, _page_gallery, _page_study_tools, _page_hashi_notes, _layout_base, _layout_main, _layout_sidebar

class SettingsDialog(InfraMixin, InfraMixin2, PageColorsMixin, PageThemesMixin, PageThemesMixin2, PageFontsMixin, PageSidebarMixin, DialogCoreMixin, DialogCoreMixin2, PageSyncMixin, PageProfileMixin, PageMainmenuMixin, PageBackgroundsMixin, PageBackgroundsMixin2, PageReviewerMixin, PageReviewerMixin2, PageHidemodesMixin, PageOverviewsMixin, PageLanguagesMixin, PageGalleryMixin, PageStudyToolsMixin, PageHashiNotesMixin, QDialog):
    ACTION_BUTTON_ORDER_IDS = ("add", "browse", "stats", "sync", "settings", "gamification", "more")
    ACTION_BUTTON_MORE_CHILDREN = ("get_shared", "create_deck", "import_file")

SettingsDialog.CustomMenu = CustomMenu
SettingsDialog.DraggableItem = DraggableItem
SettingsDialog.DropZone = DropZone
SettingsDialog.VerticalDropZone = VerticalDropZone
SettingsDialog.GridDropZone = GridDropZone
SettingsDialog.Shelf = Shelf
SettingsDialog.OnigiriDraggableItem = OnigiriDraggableItem
SettingsDialog.UnifiedGridDropZone = UnifiedGridDropZone
SettingsDialog.OnigiriGridDropZone = OnigiriGridDropZone
SettingsDialog.OnigiriArchiveZone = OnigiriArchiveZone
SettingsDialog.ExternalArchiveZone = ExternalArchiveZone
SettingsDialog.DraggableSidebarItem = DraggableSidebarItem
SettingsDialog.SidebarVisibleZone = SidebarVisibleZone
SettingsDialog.SidebarArchiveZone = SidebarArchiveZone
SettingsDialog.SidebarExternalArchiveZone = SidebarExternalArchiveZone
SettingsDialog.SidebarLayoutEditor = SidebarLayoutEditor
SettingsDialog.OnigiriLayoutEditor = OnigiriLayoutEditor
SettingsDialog.MainMenuLayoutEditor = MainMenuLayoutEditor
SettingsDialog.UnifiedLayoutEditor = UnifiedLayoutEditor
SettingsDialog.AdaptiveModeCard = AdaptiveModeCard
SettingsDialog.ResponsiveModeCardsContainer = ResponsiveModeCardsContainer

for _m in (_infra, _page_colors, _page_themes, _page_fonts, _page_sidebar, _dialog_core, _page_sync, _page_profile, _page_mainmenu, _page_backgrounds, _page_reviewer, _page_hidemodes, _page_overviews, _page_languages, _page_gallery, _page_study_tools, _layout_base, _layout_main, _layout_sidebar):
    _m.SettingsDialog = SettingsDialog

_settings_dialog = None
def open_settings(initial_page_index=0):
    """Opens the Onigiri settings dialog."""
    global _settings_dialog
    if _settings_dialog is not None:
        _settings_dialog.close()
    
    addon_path = ADDON_ROOT
    
    _settings_dialog = SettingsDialog(
        parent=mw, 
        addon_path=addon_path, 
        initial_page_index=initial_page_index
    )
    _settings_dialog.show()
