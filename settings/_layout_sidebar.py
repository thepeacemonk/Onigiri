import json
from aqt.qt import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFrame, QSizePolicy,
    QDrag, QMimeData, QPoint,
    QMenu, QAction,
    QGroupBox, QScrollArea,
    Qt, QPainter,
)
from PyQt6.QtCore import pyqtSignal, QSize

from aqt import mw
from aqt.theme import theme_manager
from ._layout_base import DraggableItem, VerticalDropZone


class DraggableSidebarItem(DraggableItem):
    def __init__(self, text, widget_id, style_colors, is_external=False, parent=None):
        self.is_external = bool(is_external)
        super().__init__(text, widget_id, style_colors, parent)
        self.locked = False


    def _update_display(self):
        super()._update_display()
        if self.is_external:
            self.setToolTip(f"{self.display_name}\nID: {self.widget_id}\nDouble-click to rename.")
        else:
            self.setToolTip(f"{self.display_name}\nID: {self.widget_id}")

    def mouseDoubleClickEvent(self, event):
        if not self.is_external:
            event.ignore()
            return
        super().mouseDoubleClickEvent(event)

    def setLocked(self, locked: bool):
        """Sets the locked state of the item. Locked items handle events differently."""
        self.locked = locked
        if locked:
            # Visual indication of locked state
            self.setGraphicsEffect(None) # Clear any previous effects
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            opacity = QGraphicsOpacityEffect(self)
            opacity.setOpacity(0.6)
            self.setGraphicsEffect(opacity)
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.setToolTip(f"{self.display_name} (Fixed in Full Mode)")
        else:
            self.setGraphicsEffect(None)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip(f"ID: {self.widget_id}\nDouble-click to rename.")

    def mouseMoveEvent(self, event):
        if self.locked:
            return
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        # Disable the right-click resize menu for sidebar items
        event.ignore()

# --- END: New Draggable Item for Sidebar ---

# --- START: New Drop Zones for Sidebar ---
# These zones only accept DraggableSidebarItem
class SidebarVisibleZone(VerticalDropZone):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drop_indicator = QLabel(self)
        self.drop_indicator.setFixedHeight(2)
        self.drop_indicator.hide()
        
    def update_drop_indicator(self, pos):
        # Find the position to show the drop indicator
        layout = self.layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item or not item.widget():
                continue
            widget = item.widget()
            if widget.y() + widget.height() // 2 > pos.y():
                self.drop_indicator.move(5, widget.y())
                self.drop_indicator.setFixedWidth(self.width() - 10)
                return widget
        # If not found, put at the end
        last_widget = self.findChild(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly)
        if last_widget:
            self.drop_indicator.move(5, last_widget.y() + last_widget.height())
        else:
            self.drop_indicator.move(5, 5)
        self.drop_indicator.setFixedWidth(self.width() - 10)
        return None
        
    def is_item_allowed(self, source_widget):
        return isinstance(source_widget, DraggableSidebarItem)

    def dragEnterEvent(self, event):
        source_widget = event.source()
        if event.mimeData().hasText() and self.is_item_allowed(source_widget):
            self.drop_indicator.setStyleSheet("background-color: #0078d7;")
            self.drop_indicator.raise_()
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and self.is_item_allowed(event.source()):
            self.drop_indicator.show()
            self.update_drop_indicator(event.position().toPoint())
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self.drop_indicator.hide()
        super().dragLeaveEvent(event)
        
    def dropEvent(self, event):
        self.drop_indicator.hide()
        pos = event.position().toPoint()
        source_widget = event.source()
        
        if self.is_item_allowed(source_widget):
            # Find the insert position
            insert_pos = self.layout.count() - 1  # Default to before the stretch
            for i in range(self.layout.count()):
                item = self.layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if widget.y() + widget.height() // 2 > pos.y():
                        insert_pos = i
                        break
            
            # Store the widget's state before removing it
            was_visible = source_widget.isVisible()
            
            # Remove from old position if needed
            if old_parent := source_widget.parent():
                if old_parent is self:
                    old_pos = self.layout.indexOf(source_widget)
                    if old_pos < insert_pos:
                        insert_pos -= 1  # Adjust if moving down in the same list
                    self.layout.removeWidget(source_widget)
                elif hasattr(old_parent, 'layout'):
                    if old_layout := old_parent.layout:
                        old_layout.removeWidget(source_widget)
            
            # Ensure the widget is properly reparented and shown
            source_widget.setParent(self)
            source_widget.show()
            
            # Insert at the new position
            self.layout.insertWidget(insert_pos, source_widget)
            event.acceptProposedAction()
        else:
            event.ignore()

class SidebarArchiveZone(VerticalDropZone):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drop_indicator = QLabel(self)
        self.drop_indicator.setFixedHeight(2)
        self.drop_indicator.hide()

    def is_item_allowed(self, source_widget):
        return (
            isinstance(source_widget, DraggableSidebarItem)
            and not getattr(source_widget, "is_external", False)
        )
        
    def update_drop_indicator(self, pos):
        # Find the position to show the drop indicator
        layout = self.layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item or not item.widget():
                continue
            widget = item.widget()
            if widget.y() + widget.height() // 2 > pos.y():
                self.drop_indicator.move(5, widget.y())
                self.drop_indicator.setFixedWidth(self.width() - 10)
                return widget
        # If not found, put at the end
        last_widget = self.findChild(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly)
        if last_widget:
            self.drop_indicator.move(5, last_widget.y() + last_widget.height())
        else:
            self.drop_indicator.move(5, 5)
        self.drop_indicator.setFixedWidth(self.width() - 10)
        return None
        
    def dragEnterEvent(self, event):
        source_widget = event.source()
        if event.mimeData().hasText() and self.is_item_allowed(source_widget):
            self.drop_indicator.setStyleSheet("background-color: #0078d7;")
            self.drop_indicator.raise_()
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and self.is_item_allowed(event.source()):
            self.drop_indicator.show()
            self.update_drop_indicator(event.position().toPoint())
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self.drop_indicator.hide()
        super().dragLeaveEvent(event)
        
    def dropEvent(self, event):
        self.drop_indicator.hide()
        pos = event.position().toPoint()
        source_widget = event.source()
        
        if self.is_item_allowed(source_widget):
            # Find the insert position
            insert_pos = self.layout.count() - 1  # Default to before the stretch
            for i in range(self.layout.count()):
                item = self.layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if widget.y() + widget.height() // 2 > pos.y():
                        insert_pos = i
                        break
            
            # Store the widget's state before removing it
            was_visible = source_widget.isVisible()
            
            # Remove from old position if needed
            if old_parent := source_widget.parent():
                if old_parent is self:
                    old_pos = self.layout.indexOf(source_widget)
                    if old_pos < insert_pos:
                        insert_pos -= 1  # Adjust if moving down in the same list
                    self.layout.removeWidget(source_widget)
                elif hasattr(old_parent, 'layout'):
                    if old_layout := old_parent.layout:
                        old_layout.removeWidget(source_widget)
            
            # Ensure the widget is properly reparented and shown
            source_widget.setParent(self)
            source_widget.show()
            
            # Insert at the new position
            self.layout.insertWidget(insert_pos, source_widget)
            event.acceptProposedAction()
        else:
            event.ignore()

class SidebarExternalArchiveZone(SidebarArchiveZone):
    def is_item_allowed(self, source_widget):
        return (
            isinstance(source_widget, DraggableSidebarItem)
            and getattr(source_widget, "is_external", False)
        )

class SidebarLayoutEditor(QWidget):
    """
    A widget with three vertical drop zones for reordering and archiving sidebar buttons.
    """
    BASE_BUTTON_MAP = {
        "profile": "Profile Bar",
        "add": "Add Button",
        "browse": "Browse Button",
        "stats": "Stats Button",
        "sync": "Sync Button",
        "settings": "Settings Button",
        "gamification": "Onigiri Games",
        "more": "More Menu"
    }

    def __init__(self, settings_dialog, parent=None):
        super().__init__(parent)
        self.settings_dialog = settings_dialog
        self.config = settings_dialog.current_config.get("sidebarButtonLayout", copy.deepcopy(DEFAULTS["sidebarButtonLayout"]))
        self.all_sidebar_items = {}

        if theme_manager.night_mode:
            button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
        else:
            button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
        self.style_colors = {"button_bg": button_bg, "border": border, "fg": fg}
        
        self._init_ui() # Call _init_ui
        
    def _init_ui(self):
        if theme_manager.night_mode:
            button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
        else:
            button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
        self.style_colors = {"button_bg": button_bg, "border": border, "fg": fg}

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Visible Items Zone ---
        visible_group = QGroupBox("Visible Items")
        visible_group.setObjectName("LayoutGroup")
        visible_layout = QVBoxLayout(visible_group)
        visible_layout.setSpacing(5)
        visible_layout.setContentsMargins(10, 15, 10, 10)
        
        self.visible_zone = SidebarVisibleZone(self)
        visible_layout.addWidget(self.visible_zone)
        main_layout.addWidget(visible_group, stretch=1)

        # --- Archived Onigiri Items Zone ---
        archived_group = QGroupBox("Archived Onigiri Items")
        archived_group.setObjectName("LayoutGroup")
        archived_layout = QVBoxLayout(archived_group)
        archived_layout.setSpacing(5)
        archived_layout.setContentsMargins(10, 15, 10, 10)
        
        self.archive_zone = SidebarArchiveZone(self)
        archived_layout.addWidget(self.archive_zone)
        main_layout.addWidget(archived_group, stretch=1)

        # --- Archived External Items Zone ---
        external_archived_group = QGroupBox("Archived External Items")
        external_archived_group.setObjectName("LayoutGroup")
        external_archived_layout = QVBoxLayout(external_archived_group)
        external_archived_layout.setSpacing(5)
        external_archived_layout.setContentsMargins(10, 15, 10, 10)
        
        self.external_archive_zone = SidebarExternalArchiveZone(self)
        external_archived_layout.addWidget(self.external_archive_zone)
        main_layout.addWidget(external_archived_group, stretch=1)
        
        # Set minimum heights for the drop zones
        self.visible_zone.setMinimumHeight(200)
        self.archive_zone.setMinimumHeight(100)
        self.external_archive_zone.setMinimumHeight(100)
        
        # Apply styles
        self.setStyleSheet("""
            QGroupBox#LayoutGroup {
                border: 1px solid %(border)s;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QLabel#DropIndicator {
                background-color: #0078d7;
            }
        """ % self.style_colors)
        
        self._populate_widgets()

    def _get_button_map(self, include_overrides: bool = True) -> dict:
        button_map = dict(self.BASE_BUTTON_MAP)
        button_map.update(sidebar_api.get_sidebar_labels(include_overrides=include_overrides))
        return button_map

    def _populate_widgets(self):
        # Get the saved layout config
        visible_order = self.config.get("visible", [])
        archived = self.config.get("archived", [])
        external_ids = set(sidebar_api.get_sidebar_labels().keys())
        
        # Use defaults from the top-level DEFAULTS constant
        default_archived = list(DEFAULTS["sidebarButtonLayout"]["archived"])

        # Check if Full Mode is enabled
        is_full_mode = self.settings_dialog.current_config.get("fullHideMode", False)

        label_overrides = self.config.get("labels", {}) if isinstance(self.config, dict) else {}
        default_labels = self._get_button_map(include_overrides=False)

        # Create all possible items
        for widget_id, text in default_labels.items():
            is_external = widget_id in external_ids
            item = DraggableSidebarItem(
                text, widget_id, self.style_colors, is_external=is_external
            )
            if isinstance(label_overrides, dict):
                override = label_overrides.get(widget_id)
                if isinstance(override, str) and override.strip():
                    item.set_display_name(override.strip())
            self.all_sidebar_items[widget_id] = item

        # If Full Mode is on, ensure "settings" is visible and not archived
        if is_full_mode:
            if "settings" in archived:
                archived.remove("settings")
            if "settings" not in visible_order:
                visible_order.append("settings")

        placed_items = set()
        
        # Place visible items
        for widget_id in visible_order:
            if item := self.all_sidebar_items.get(widget_id):
                self.visible_zone.layout.insertWidget(self.visible_zone.layout.count() - 1, item)
                placed_items.add(widget_id)
                
                # Lock settings button if in Full Mode
                if is_full_mode and widget_id == "settings":
                    item.setLocked(True)
        
        # Place archived items
        for widget_id in archived:
            if item := self.all_sidebar_items.get(widget_id):
                if widget_id not in placed_items: # Avoid duplicates
                    if widget_id in external_ids:
                        self.external_archive_zone.layout.insertWidget(
                            self.external_archive_zone.layout.count() - 1, item
                        )
                    else:
                        self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                    placed_items.add(widget_id)

        # Place any new/unconfigured items
        for widget_id, item in self.all_sidebar_items.items():
            if widget_id not in placed_items:
                # External items default to archived
                if widget_id in external_ids:
                    self.external_archive_zone.layout.insertWidget(
                        self.external_archive_zone.layout.count() - 1, item
                    )
                # Check against the DEFAULTS to see where new items should go
                elif widget_id in default_archived and not (is_full_mode and widget_id == "settings"):
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                else: # Default to visible if not in archived (or not in defaults at all)
                    self.visible_zone.layout.insertWidget(self.visible_zone.layout.count() - 1, item)
                     
                    # Lock settings button if in Full Mode (edge case where it wasn't in visible_order or archived)
                    if is_full_mode and widget_id == "settings":
                        item.setLocked(True)

    def get_layout_config(self) -> dict:
        # Get keys from the "Visible" zone
        visible = []
        for i in range(self.visible_zone.layout.count()):
            item = self.visible_zone.layout.itemAt(i)
            if item and (widget := item.widget()):
                if isinstance(widget, DraggableSidebarItem):
                    visible.append(widget.widget_id)

        # Get keys from the "Archived" zone
        archived = []
        for i in range(self.archive_zone.layout.count()):
            item = self.archive_zone.layout.itemAt(i)
            if item and (widget := item.widget()):
                if isinstance(widget, DraggableSidebarItem):
                    archived.append(widget.widget_id)
        for i in range(self.external_archive_zone.layout.count()):
            item = self.external_archive_zone.layout.itemAt(i)
            if item and (widget := item.widget()):
                if isinstance(widget, DraggableSidebarItem):
                    archived.append(widget.widget_id)
                    
        default_labels = self._get_button_map(include_overrides=False)
        labels = {}
        if isinstance(self.config, dict):
            saved_labels = self.config.get("labels", {})
            if isinstance(saved_labels, dict):
                labels.update(saved_labels)

        for widget_id, item in self.all_sidebar_items.items():
            default_label = default_labels.get(widget_id, item.display_name)
            if item.display_name and item.display_name != default_label:
                labels[widget_id] = item.display_name
            else:
                labels.pop(widget_id, None)

        layout = {"visible": visible, "archived": archived}
        if labels:
            layout["labels"] = labels
        return layout

