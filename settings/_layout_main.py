# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *


class OnigiriDraggableItem(DraggableItem):
    archive_requested = pyqtSignal(object)
    
    def contextMenuEvent(self, event):
        if not self.property("isOnGrid") or not self.grid_zone: return

        custom_menu = SettingsDialog.CustomMenu(self.window())
        is_heatmap = self.widget_id == 'heatmap'
        is_restaurant = self.widget_id == 'restaurant_level'
        is_prep_station = self.widget_id == 'prep_station'

        # --- Width Actions ---
        width_group = QButtonGroup(custom_menu)
        width_group.setExclusive(True)
        max_cols = 4
        width_options = []
        for i in range(1, max_cols + 1):
            if is_heatmap and i < 2: continue # Heatmap min 2 cols
            if is_restaurant:
                if i > 2: continue # Restaurant Level supports compact 1x2 or wide 2x2 layouts
            if self.widget_id == 'hexagon_land':
                if i != 2: continue # Hexagon Land preview is two columns wide
            if self.widget_id == 'deck_stats':
                if i > 2: continue
            width_options.append((str(i), i, self.col_span == i))
        custom_menu.add_section_label(tr("widget_menu_columns", "Columns"))
        custom_menu.add_segmented_row(width_options, width_group)

        custom_menu.add_separator()

        # --- Height Actions ---
        height_group = QButtonGroup(custom_menu)
        height_group.setExclusive(True)
        # Set row constraints
        min_rows = 2 if (is_heatmap or self.widget_id in ('restaurant_level', 'onigimon', 'hexagon_land', 'prep_station')) else 1
        if is_heatmap:
            max_rows = 2  # Heatmap: exactly 2 rows
        elif self.widget_id == 'restaurant_level':
            max_rows = 2  # Nook Level: exactly 2 rows, can never be less
        elif self.widget_id == 'onigimon':
            max_rows = 2  # Onigimon: companion card is two rows tall by default
        elif self.widget_id == 'hexagon_land':
            max_rows = 2  # Hexagon Land: island preview needs room to breathe
        elif is_prep_station:
            max_rows = 2  # Study Plans: always exactly 2 rows tall
        elif self.widget_id == 'deck_stats':
            max_rows = 2  # Deck Stats is capped at two rows
        elif self.widget_id == 'favorites':
            max_rows = 3  # Favorites: up to 3 rows
        else:
            max_rows = 1  # Other widgets: 1 row
        height_options = [(str(i), i, self.row_span == i) for i in range(min_rows, max_rows + 1)]
        custom_menu.add_section_label(tr("widget_menu_rows", "Rows"))
        custom_menu.add_segmented_row(height_options, height_group)

        orientation_group = None
        if is_restaurant:
            custom_menu.add_separator()
            orientation_group = QButtonGroup(custom_menu)
            orientation_group.setExclusive(True)
            custom_menu.add_section_label(tr("widget_menu_orientation", "Orientation"))
            custom_menu.add_segmented_row([
                (tr("orientation_side_by_side", "Side by Side"), "horizontal", self.restaurant_orientation == "horizontal"),
                (tr("orientation_image_top", "Image on Top"), "vertical", self.restaurant_orientation == "vertical"),
            ], orientation_group)

        custom_menu.add_separator()

        # --- Archive Action ---
        archive_button = QPushButton(tr("archived_widgets"))
        archive_button.setObjectName("MenuButton")
        archive_button.clicked.connect(lambda: (self.archive_requested.emit(self), custom_menu.close()))
        custom_menu.content_layout.addWidget(archive_button)

        def on_menu_action():
            new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
            new_row_span = height_group.checkedButton().property("action_data") if height_group.checkedButton() else self.row_span
            new_orientation = self.restaurant_orientation
            if orientation_group and orientation_group.checkedButton():
                new_orientation = orientation_group.checkedButton().property("action_data")

            if new_col_span != self.col_span or new_row_span != self.row_span:
                self.grid_zone.request_resize(self, new_row_span, new_col_span)
            self.restaurant_orientation = new_orientation
            custom_menu.close()

        width_group.buttonClicked.connect(on_menu_action)
        height_group.buttonClicked.connect(on_menu_action)
        if orientation_group:
            orientation_group.buttonClicked.connect(on_menu_action)

        custom_menu.move(self.mapToGlobal(event.pos()))
        custom_menu.show()


class UnifiedGridDropZone(GridDropZone):
    """A unified grid that accepts both Onigiri and External widgets."""
    def __init__(self, main_editor, parent=None):
        super().__init__(main_editor, parent)
        # Row count is controlled by the parent GridDropZone (default 6)

    def is_item_allowed(self, item):
        # Accept both Onigiri and External draggable items
        return isinstance(item, (SettingsDialog.OnigiriDraggableItem, SettingsDialog.DraggableItem))


class OnigiriGridDropZone(GridDropZone):
    def __init__(self, main_editor, parent=None, col_count=4):
        super().__init__(main_editor, parent)
        self.col_count = col_count
        # Initialize with default 3 rows
        self.update_grid_dimensions(3, self.col_count)

    def is_item_allowed(self, item):
        return isinstance(item, SettingsDialog.OnigiriDraggableItem)
    
    # Override region check for dynamic grid
    def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
        if col + col_span > self.col_count or row + row_span > self.row_count: return False
        for r in range(row, row + row_span):
            for c in range(col, col + col_span):
                pos = r * self.col_count + c
                if pos in self.shelves and self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
        return True


class OnigiriArchiveZone(VerticalDropZone):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80) # Make it a bit taller
    def is_item_allowed(self, item):
        return isinstance(item, SettingsDialog.OnigiriDraggableItem)


class ExternalArchiveZone(VerticalDropZone):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80) # Match OnigiriArchiveZone

    def is_item_allowed(self, item):
        if isinstance(item, SettingsDialog.OnigiriDraggableItem):
            return False
        return isinstance(item, SettingsDialog.DraggableItem)


class OnigiriLayoutEditor(QWidget):
    def __init__(self, settings_dialog):
        super().__init__()
        self.settings_dialog = settings_dialog
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        onigiri_group, onigiri_group_layout = SettingsDialog._create_layout_group("Onigiri Widgets")

        # Controls row
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel(tr("columns_label")))
        self.col_spin = QSpinBox()
        self.col_spin.setRange(2, 6)
        self.col_spin.setValue(4) # Default
        self.col_spin.setFixedWidth(50)
        self.col_spin.valueChanged.connect(self._on_col_count_changed)
        controls_layout.addWidget(self.col_spin)
        controls_layout.addStretch()
        onigiri_group_layout.addLayout(controls_layout)

        self.grid_zone = SettingsDialog.OnigiriGridDropZone(self, onigiri_group, col_count=4)
        onigiri_group_layout.addWidget(self.grid_zone)
        main_layout.addWidget(onigiri_group)

        archive_group, archive_group_layout = SettingsDialog._create_layout_group("Archived Widgets")
        self.archive_zone = SettingsDialog.OnigiriArchiveZone(archive_group)
        archive_group_layout.addWidget(self.archive_zone)
        main_layout.addWidget(archive_group)

        self.all_onigiri_items = {}
        self._populate_widgets()

    def _populate_widgets(self):
        style_colors = self.settings_dialog._layout_editor_style_colors()

        # Define default layout
        DEFAULTS = {
            "grid": {
                "studied": {"pos": 0, "row": 1, "col": 1},
                "time": {"pos": 1, "row": 1, "col": 1},
                "pace": {"pos": 2, "row": 1, "col": 1},
                "retention": {"pos": 3, "row": 1, "col": 1},
                "heatmap": {"pos": 4, "row": 2, "col": 4},
            },
            "archive": ["favorites", "restaurant_level", "onigimon", "hexagon_land"] # <-- optional widgets start archived
        }

        saved_layout = self.settings_dialog.current_config.get("onigiriWidgetLayout", DEFAULTS)
        
        # --- START: Robust config merging ---
        saved_grid_config = saved_layout.get("grid")
        
        # If we have a saved grid config, use it. Otherwise use defaults.
        if isinstance(saved_grid_config, dict):
            grid_config = copy.deepcopy(saved_grid_config)
        else:
            grid_config = copy.deepcopy(DEFAULTS["grid"])
        
        # Safely get archive_config, falling back to default if it's None or invalid
        archive_config = saved_layout.get("archive")
        if not isinstance(archive_config, (list, dict)):
             archive_config = DEFAULTS["archive"]

        # Ensure any widgets in DEFAULTS["grid"] that are not in grid_config OR archive_config are added to grid_config
        # This handles new widgets added in updates
        
        # Helper to get list of archived IDs
        if isinstance(archive_config, dict):
            archived_ids = set(archive_config.keys())
        else:
            archived_ids = set(archive_config)
        
        # --- FIXED: Remove archived items from grid_config ---
        # The config.merge_config function might have re-inserted default grid positions 
        # for items that the user moved to the archive.
        for widget_id in archived_ids:
            if widget_id in grid_config:
                del grid_config[widget_id]
        # -----------------------------------------------------

        for widget_id, default_pos in DEFAULTS["grid"].items():
            if widget_id not in grid_config and widget_id not in archived_ids:
                grid_config[widget_id] = default_pos
        # --- END: Robust config merging ---

        widget_definitions = {
            "studied": tr("widget_studied"), "time": tr("widget_time"), 
            "pace": tr("widget_pace"), "retention": tr("widget_retention"), "heatmap": tr("widget_heatmap"),
            "favorites": "Favorites Widget",
            "restaurant_level": "Nook Level",
            "onigimon": "Onigimon",
            "hexagon_land": "Hexagon Land",
        }

        placed_widgets = set()

        # Create all items
        for widget_id, text in widget_definitions.items():
            item = SettingsDialog.OnigiriDraggableItem(text, widget_id, style_colors)
            item.archive_requested.connect(self._archive_item)
            if widget_id == "restaurant_level":
                item.row_span = 2
                item.col_span = 2
            elif widget_id == "onigimon":
                item.row_span = 2
            elif widget_id == "hexagon_land":
                item.row_span = 2
                item.col_span = 2
            self.all_onigiri_items[widget_id] = item

        # Combine grid and archive configs to find all saved names
        all_saved_configs = grid_config.copy()
        if isinstance(archive_config, dict):
            all_saved_configs.update(archive_config)
        elif isinstance(archive_config, list):
            # Handle old list-based archive config
            for widget_id in archive_config:
                all_saved_configs.setdefault(widget_id, {}) # Add it with no display name

        # Update display names from saved config
        for widget_id, item in self.all_onigiri_items.items():
            if saved_item_config := all_saved_configs.get(widget_id):
                if custom_name := saved_item_config.get("display_name"):
                    item.set_display_name(custom_name)
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = saved_item_config.get("orientation", "horizontal")

        # Place items on grid
        for widget_id, config in grid_config.items():
            if item := self.all_onigiri_items.get(widget_id):
                item.row_span = config.get("row", 1)
                item.col_span = config.get("col", 1)
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = config.get("orientation", "horizontal")
                if widget_id == "hexagon_land":
                    item.row_span = 2
                    item.col_span = 2
                # Use a default 'pos' if missing (e.g., from old config)
                if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                    placed_widgets.add(widget_id)

        # Place items in archive (handle both list and dict for backward compatibility)
        archive_ids = []
        if isinstance(archive_config, list):
            archive_ids = archive_config
        elif isinstance(archive_config, dict):
            archive_ids = archive_config.keys()
        
        for widget_id in archive_ids:
            if item := self.all_onigiri_items.get(widget_id):
                # Don't place in archive if it was already placed on the grid
                if widget_id not in placed_widgets:
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                    placed_widgets.add(widget_id)

        # Place any new/unconfigured items into the archive
        for widget_id, item in self.all_onigiri_items.items():
            if widget_id not in placed_widgets:
                self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)

    def _archive_item(self, item):
        for shelf in self.grid_zone.shelves.values():
            if shelf.child_widget is item: shelf.child_widget = None
        self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
        # Reset spans when archiving
        if item.widget_id == "heatmap":
            item.row_span, item.col_span = 2, 4
        elif item.widget_id == "restaurant_level":
            item.row_span, item.col_span = 2, 2
            item.restaurant_orientation = "horizontal"
        elif item.widget_id == "onigimon":
            item.row_span, item.col_span = 2, 1
        elif item.widget_id == "hexagon_land":
            item.row_span, item.col_span = 2, 2
        else:
            item.row_span, item.col_span = 1, 1

    def get_layout_config(self):
        grid_config = {}
        processed_widgets = set()
        for pos, shelf in self.grid_zone.shelves.items():
            widget = shelf.child_widget
            if widget and widget not in processed_widgets:
                widget_config = {
                    "pos": pos, "row": widget.row_span, "col": widget.col_span,
                    "display_name": widget.display_name
                }
                if widget.widget_id == "restaurant_level":
                    widget_config["orientation"] = widget.restaurant_orientation
                grid_config[widget.widget_id] = widget_config
                processed_widgets.add(widget)

        archive_config = self.archive_zone.get_archive_config()
        return {"grid": grid_config, "archive": archive_config}


class MainMenuLayoutEditor(QWidget):
    def __init__(self, settings_dialog):
        super().__init__()
        self.settings_dialog = settings_dialog
        main_layout = QVBoxLayout(self); main_layout.setSpacing(15)
        grid_group, grid_group_layout = SettingsDialog._create_layout_group("External Add-on Grid")
        self.grid_zone = SettingsDialog.GridDropZone(self, grid_group)

        # Setup layout for grid group to hold the grid
        grid_group_layout.addWidget(self.grid_zone)

        main_layout.addWidget(grid_group)

        archive_group, archive_group_layout = SettingsDialog._create_layout_group("Archived External Add-ons")
        self.archive_zone = SettingsDialog.ExternalArchiveZone(archive_group)
        archive_group_layout.addWidget(self.archive_zone)
        main_layout.addWidget(archive_group)

        self.all_external_items = {} # Will store all draggable items for external addons
        self._populate_widgets()

    def _populate_widgets(self):
        style_colors = self.settings_dialog._layout_editor_style_colors()

        saved_layout = self.settings_dialog.current_config.get("externalWidgetLayout", {})
        # Gracefully handle old config format
        if saved_layout and "grid" not in saved_layout:
            grid_config = saved_layout
            archive_config = {}
        else:
            grid_config = saved_layout.get("grid", {})
            archive_config = saved_layout.get("archive", {})

        external_hooks = self.settings_dialog._get_external_hooks()

        # Create and store all external addon items
        for hook_id in external_hooks:
            from .. import patcher
            item = SettingsDialog.DraggableItem(
                patcher.get_external_hook_display_name(hook_id, hook_id.split('.')[0]),
                hook_id,
                style_colors,
            )
            item.setProperty("isExternalWidget", True)
            item.row_span = 2
            item.archive_requested.connect(self._archive_item)
            self.all_external_items[hook_id] = item

        # Combine grid and archive configs to find all saved names
        all_saved_configs = {**grid_config, **archive_config}

        # Update display names from saved config
        for hook_id, item in self.all_external_items.items():
            if saved_item_config := all_saved_configs.get(hook_id):
                if custom_name := saved_item_config.get("display_name"):
                    item.set_display_name(custom_name)

        placed_hooks = set()
        # Place items that have a saved position on the grid
        for hook_id, config in grid_config.items():
            if hook_id in self.all_external_items:
                item = self.all_external_items[hook_id]
                item.row_span = max(2, config.get("row_span", 2))
                item.col_span = config.get("column_span", 1)
                if self.grid_zone.place_item(item, config.get("grid_position", 0), silent=True):
                    placed_hooks.add(hook_id)
        
        # Place items that have a saved position in the archive
        for hook_id in archive_config.keys():
            if hook_id in self.all_external_items:
                item = self.all_external_items[hook_id]
                self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                placed_hooks.add(hook_id)

        # Place any new/unplaced add-ons in the ARCHIVE
        for hook_id in external_hooks:
            if hook_id not in placed_hooks:
                item = self.all_external_items[hook_id]
                self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
    
    def _archive_item(self, item):
        """Moves an item from the grid to the archive zone."""
        for shelf in self.grid_zone.shelves.values():
            if shelf.child_widget is item:
                shelf.child_widget = None
        self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
        
    def get_layout_config(self):
        """Retrieves the current layout from the grid and archive zones."""
        grid_config = self.grid_zone.get_layout_config()
        archive_config = self.archive_zone.get_archive_config()
        # We are saving both onigiri and external layout into legacy structure for compatibility
        # But the 'column_count' specifically goes into 'onigiriWidgetLayout' usually.
        # However, this method returns a dict that the dialog uses to construct the full config.
        # We need to make sure the dialog knows how to unpack this or we just update the specific keys here.
        
        # actually, looking at apply_changes in SettingsDialog (which calls this),
        # it expects this to return the config for "unifiedWidgetLayout" or similar?
        # Wait, let's verify how this is used.
        return {
            "grid": grid_config, 
            "archive": archive_config,
            "column_count": self.col_spin.value(),
            "rows": self.row_spin.value()
        }


class UnifiedLayoutEditor(QWidget):
    """
    A unified layout editor that combines both Onigiri widgets and External add-on widgets
    in a single grid, with separate archive zones for each type.
    """
    
    # Default layout configuration for Onigiri widgets
    _ONIGIRI_DEFAULTS = {
        "grid": {
            "studied": {"pos": 0, "row": 1, "col": 1},
            "time": {"pos": 1, "row": 1, "col": 1},
            "pace": {"pos": 2, "row": 1, "col": 1},
            "retention": {"pos": 3, "row": 1, "col": 1},
            "heatmap": {"pos": 4, "row": 2, "col": 4},
        },
        "archive": ["favorites", "restaurant_level", "onigimon", "hexagon_land", "deck_stats", "prep_station"]
    }

    # Default display names for Onigiri widgets
    _WIDGET_DEFINITIONS = {
        "studied": tr("widget_studied"), "time": tr("widget_time"),
        "pace": tr("widget_pace"), "retention": tr("widget_retention"), "heatmap": tr("widget_heatmap"),
        "favorites": tr("widget_favorites"),
        "restaurant_level": tr("widget_restaurant_level"),
        "onigimon": "Onigimon",
        "hexagon_land": "Hexagon Land",
        "deck_stats": "Deck Stats",
        "prep_station": tr("widget_study_plans", "Study Plans"),
    }

    def __init__(self, settings_dialog):
        super().__init__()
        self.settings_dialog = settings_dialog
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # --- Grid Settings ---
        grid_settings_group, grid_settings_layout = SettingsDialog._create_layout_group(tr("grid_settings", "Grid Settings"))
        
        panel = QFrame()
        panel.setObjectName("organizeCompactPanel")
        panel.setStyleSheet(self.settings_dialog._organize_compact_stylesheet())
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 4, 0, 4)
        panel_layout.setSpacing(0)
        
        grid_settings_colors = self.settings_dialog._layout_editor_style_colors()

        def add_setting_row(label, control):
            if isinstance(control, QAbstractSpinBox):
                control.setObjectName("organizeCompactSpinBox")
                control.setFixedHeight(30)
            panel_layout.addWidget(self.settings_dialog._create_organize_compact_row(str(label).strip().rstrip(":"), control))

        row_label = QLabel(tr("unified_grid_rows")) # User friendly label
        self.row_spin = QSpinBox()
        self.row_spin.setRange(0, 200)
        # Get saved row count or default to 6
        current_rows = self.settings_dialog.current_config.get("unifiedGridRows", 6)
        try:
            current_rows = int(current_rows)
        except (TypeError, ValueError):
            current_rows = 6
        current_rows = max(0, min(200, current_rows))
        self.row_spin.setValue(current_rows)
        add_setting_row(row_label.text(), self.row_spin)

        col_label = QLabel(tr("unified_grid_cols"))
        self.col_spin = QSpinBox()
        self.col_spin.setRange(0, 6)
        self.col_spin.setValue(4) # Default
        add_setting_row(col_label.text(), self.col_spin)

        width_label = QLabel(tr("grid_width_label", "Grid Width:"))
        self.grid_width_spin = QSpinBox()
        self.grid_width_spin.setRange(200, 340)
        self.grid_width_spin.setSuffix(" px")
        self.grid_width_spin.setValue(230)
        add_setting_row(width_label.text(), self.grid_width_spin)

        alignment_label = QLabel(tr("grid_alignment_label", "Grid Alignment:"))
        self.grid_alignment_group = QButtonGroup(self)
        self.grid_alignment_group.setExclusive(True)
        current_alignment = self.settings_dialog.current_config.get("onigiriWidgetLayout", {}).get("grid_alignment", "center")
        alignment_container = self.settings_dialog._create_organize_segmented_control(
            [
                ("left", tr("align_left", "Left")),
                ("center", tr("align_center", "Center")),
                ("right", tr("align_right", "Right")),
            ],
            self.grid_alignment_group,
            current_alignment,
            "grid_alignment",
            fill_width=True,
            segment_height=26,
            min_button_width=64,
        )
        alignment_container.setFixedHeight(34)
        add_setting_row(alignment_label.text(), alignment_container)

        height_label = QLabel(tr("widget_height_label", "Widget Height:"))
        self.widget_height_spin = QSpinBox()
        self.widget_height_spin.setRange(120, 320)
        self.widget_height_spin.setSuffix(" px")
        self.widget_height_spin.setValue(120)
        add_setting_row(height_label.text(), self.widget_height_spin)

        grid_settings_layout.addWidget(panel)

        self._applied_row_count = self.row_spin.value()
        self._applied_col_count = 4
        accent_hint = QColor(grid_settings_colors.get("accent", "#00A982"))
        if not accent_hint.isValid():
            accent_hint = QColor("#00A982")
        hint_bg = f"rgba({accent_hint.red()}, {accent_hint.green()}, {accent_hint.blue()}, 179)"
        hint_fg = "#111827" if accent_hint.lightness() > 165 else "#ffffff"
        self.row_apply_hint_label = self._create_grid_dimension_hint_label(self.row_spin, hint_bg, hint_fg)
        self.col_apply_hint_label = self._create_grid_dimension_hint_label(self.col_spin, hint_bg, hint_fg)
        main_layout.addWidget(grid_settings_group)

        # --- Unified Grid ---
        grid_group, grid_group_layout = SettingsDialog._create_layout_group(tr("widget_grid_title"))
        self.grid_zone = SettingsDialog.UnifiedGridDropZone(self, grid_group)
        
        # Apply initial row count and column count
        current_cols = self.settings_dialog.current_config.get("onigiriWidgetLayout", {}).get("column_count", 4)
        try:
            current_cols = int(current_cols)
        except (TypeError, ValueError):
            current_cols = 4
        current_cols = max(0, min(6, current_cols))
        self.col_spin.blockSignals(True)
        self.col_spin.setValue(current_cols)
        self.col_spin.blockSignals(False)
        self._applied_col_count = self.col_spin.value()

        self.row_spin.valueChanged.connect(self._on_grid_dimension_input_changed)
        self.col_spin.valueChanged.connect(self._on_grid_dimension_input_changed)

        current_grid_width = self.settings_dialog.current_config.get("onigiriWidgetLayout", {}).get("grid_width", 230)
        try:
            current_grid_width = int(current_grid_width)
        except (TypeError, ValueError):
            current_grid_width = 230
        self.grid_width_spin.setValue(max(200, min(340, current_grid_width)))

        if not self.grid_alignment_group.checkedButton():
            for btn in self.grid_alignment_group.buttons():
                btn.setChecked(btn.property("grid_alignment") == "center")

        current_widget_height = self.settings_dialog.current_config.get("onigiriWidgetLayout", {}).get("widget_height", 120)
        try:
            current_widget_height = int(current_widget_height)
        except (TypeError, ValueError):
            current_widget_height = 120
        self.widget_height_spin.setValue(max(120, min(320, current_widget_height)))
        
        # FIX: Use at least 4 columns for visual layout if 0 is selected (Sidebar Only Mode)
        # This prevents ZeroDivisionError in place_item
        effective_cols = current_cols if current_cols > 0 else 4
        self.grid_zone.update_grid_dimensions(current_rows, effective_cols)
            
        grid_group_layout.addWidget(self.grid_zone)
        main_layout.addWidget(grid_group)

        # --- Archive Zones Container (side by side) ---
        archives_container = QWidget()
        archives_layout = QHBoxLayout(archives_container)
        archives_layout.setContentsMargins(0, 0, 0, 0)
        archives_layout.setSpacing(15)

        # Scroll Area Stylesheet
        scroll_style = """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(128, 128, 128, 0.5); min-height: 20px; border-radius: 5px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """

        # Archived Onigiri Widgets
        onigiri_archive_group, onigiri_archive_layout = SettingsDialog._create_layout_group(tr("archived_onigiri_widgets"))
        
        # Wrap in ScrollArea
        self.onigiri_scroll = QScrollArea()
        self.onigiri_scroll.setWidgetResizable(True)
        self.onigiri_scroll.setFixedHeight(200)
        self.onigiri_scroll.setStyleSheet(scroll_style)
        
        self.onigiri_archive_zone = SettingsDialog.OnigiriArchiveZone(onigiri_archive_group)
        self.onigiri_scroll.setWidget(self.onigiri_archive_zone)
        
        onigiri_archive_layout.addWidget(self.onigiri_scroll)
        archives_layout.addWidget(onigiri_archive_group)

        # Archived External Widgets
        external_archive_group, external_archive_layout = SettingsDialog._create_layout_group(tr("archived_external_widgets"))
        
        # Wrap in ScrollArea
        self.external_scroll = QScrollArea()
        self.external_scroll.setWidgetResizable(True)
        self.external_scroll.setFixedHeight(200)
        self.external_scroll.setStyleSheet(scroll_style)
        
        self.external_archive_zone = SettingsDialog.ExternalArchiveZone(external_archive_group)
        self.external_scroll.setWidget(self.external_archive_zone)

        external_archive_layout.addWidget(self.external_scroll)
        archives_layout.addWidget(external_archive_group)

        main_layout.addWidget(archives_container)
        
        # --- Reset Buttons ---
        reset_buttons_layout = QHBoxLayout()
        reset_buttons_layout.setSpacing(10)
        
        reset_names_btn = QPushButton(tr("reset_widget_names"))
        reset_names_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_names_btn.setStyleSheet(self.settings_dialog._reset_button_stylesheet())
        reset_names_btn.clicked.connect(self.reset_widget_names)
        reset_buttons_layout.addWidget(reset_names_btn)
        
        reset_layout_btn = QPushButton(tr("reset_layout_default_btn"))
        reset_layout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_layout_btn.setStyleSheet(self.settings_dialog._reset_button_stylesheet())
        reset_layout_btn.clicked.connect(self.reset_layout)
        reset_buttons_layout.addWidget(reset_layout_btn)
        
        reset_buttons_layout.addStretch()
        main_layout.addLayout(reset_buttons_layout)

        # Push everything up
        main_layout.addStretch()

        self.all_onigiri_items = {}
        self.all_external_items = {}
        self._populate_widgets()
    
    def _on_grid_dimension_input_changed(self, *_):
        self._update_grid_dimension_hint()

    def _update_grid_dimension_hint(self):
        row_pending = self.row_spin.value() != self._applied_row_count
        col_pending = self.col_spin.value() != self._applied_col_count
        self.row_apply_hint_label.setVisible(row_pending)
        self.col_apply_hint_label.setVisible(col_pending)
        self._position_grid_dimension_hint(self.row_spin)
        self._position_grid_dimension_hint(self.col_spin)

    def _create_grid_dimension_hint_label(self, spinbox, bg_color, fg_color):
        label = QLabel("Hit enter to save", spinbox)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "QLabel {"
            f"background: {bg_color};"
            f"color: {fg_color};"
            "border-radius: 12px;"
            "font-weight: 700;"
            "padding: 3px 12px;"
            "}"
        )
        label.hide()
        label.raise_()
        spinbox.installEventFilter(self)
        spinbox.lineEdit().installEventFilter(self)
        return label

    def _grid_dimension_source_for_widget(self, watched):
        if watched is getattr(self, "row_spin", None) or watched is getattr(getattr(self, "row_spin", None), "lineEdit", lambda: None)():
            return "rows"
        if watched is getattr(self, "col_spin", None) or watched is getattr(getattr(self, "col_spin", None), "lineEdit", lambda: None)():
            return "cols"
        return None

    def _position_grid_dimension_hint(self, spinbox):
        label = None
        if spinbox is getattr(self, "row_spin", None):
            label = getattr(self, "row_apply_hint_label", None)
        elif spinbox is getattr(self, "col_spin", None):
            label = getattr(self, "col_apply_hint_label", None)
        if not label:
            return
        label.adjustSize()
        label_width = min(label.sizeHint().width(), max(0, spinbox.width() - 56))
        label_height = min(max(label.sizeHint().height(), 24), max(0, spinbox.height() - 8))
        label_x = max(8, spinbox.width() - label_width - 12)
        label_y = max(4, (spinbox.height() - label_height) // 2)
        label.setGeometry(label_x, label_y, label_width, label_height)
        label.raise_()

    def eventFilter(self, watched, event):
        dimension_source = self._grid_dimension_source_for_widget(watched)
        if dimension_source:
            if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                event.accept()
                return True
            if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._apply_grid_dimensions_from_inputs(dimension_source)
                event.accept()
                return True
            spinbox = self.row_spin if dimension_source == "rows" else self.col_spin
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._position_grid_dimension_hint(spinbox)
        return super().eventFilter(watched, event)

    def _set_grid_dimension_inputs(self, rows, cols):
        self.row_spin.blockSignals(True)
        self.col_spin.blockSignals(True)
        try:
            self.row_spin.setValue(rows)
            self.col_spin.setValue(cols)
        finally:
            self.row_spin.blockSignals(False)
            self.col_spin.blockSignals(False)
        self._update_grid_dimension_hint()

    def _apply_grid_dimensions_from_inputs(self, source):
        rows = self.row_spin.value()
        cols = self.col_spin.value()

        if source == "rows":
            if rows == 0:
                cols = 0
            elif cols == 0:
                cols = max(1, self._applied_col_count or 1)
        elif source == "cols":
            if cols == 0:
                rows = 0
            elif rows == 0:
                rows = max(1, self._applied_row_count or 1)

        self._applied_row_count = rows
        self._applied_col_count = cols
        self._set_grid_dimension_inputs(rows, cols)

        effective_cols = cols if cols > 0 else 4
        self.grid_zone.update_grid_dimensions(rows, effective_cols)
        self.row_apply_hint_label.setVisible(False)
        self.col_apply_hint_label.setVisible(False)

    def _populate_widgets(self):
        style_colors = self.settings_dialog._layout_editor_style_colors()

        # --- Onigiri Widgets ---
        # --- Onigiri Widgets ---
        saved_onigiri_layout = self.settings_dialog.current_config.get("onigiriWidgetLayout", self._ONIGIRI_DEFAULTS)

        # Load column count (sync with spinbox which was set in __init__)
        saved_col_count = saved_onigiri_layout.get("column_count", 4)
        try:
            saved_col_count = int(saved_col_count)
        except (TypeError, ValueError):
            saved_col_count = 4
        saved_col_count = max(0, min(6, saved_col_count))
        # Spinner already set in __init__, but good to ensure sync if config reloaded
        if self.col_spin.value() != saved_col_count:
            self.col_spin.blockSignals(True)
            self.col_spin.setValue(saved_col_count)
            self.col_spin.blockSignals(False)
            self._applied_col_count = saved_col_count
            # FIX: Use at least 4 columns for visual layout if 0 is selected
            effective_cols = saved_col_count if saved_col_count > 0 else 4
            self.grid_zone.update_grid_dimensions(self.grid_zone.row_count, effective_cols)
        
        # Get grid and archive configs
        saved_grid_config = saved_onigiri_layout.get("grid")
        if isinstance(saved_grid_config, dict):
            onigiri_grid_config = copy.deepcopy(saved_grid_config)
        else:
            onigiri_grid_config = copy.deepcopy(self._ONIGIRI_DEFAULTS["grid"])
        
        onigiri_archive_config = saved_onigiri_layout.get("archive")
        if not isinstance(onigiri_archive_config, (list, dict)):
            onigiri_archive_config = self._ONIGIRI_DEFAULTS["archive"]

        # Get archived IDs
        if isinstance(onigiri_archive_config, dict):
            onigiri_archived_ids = set(onigiri_archive_config.keys())
        else:
            onigiri_archived_ids = set(onigiri_archive_config)
        
        # Remove archived items from grid config
        for widget_id in onigiri_archived_ids:
            if widget_id in onigiri_grid_config:
                del onigiri_grid_config[widget_id]

        # Add missing widgets to grid
        for widget_id, default_pos in self._ONIGIRI_DEFAULTS["grid"].items():
            if widget_id not in onigiri_grid_config and widget_id not in onigiri_archived_ids:
                onigiri_grid_config[widget_id] = default_pos

        placed_onigiri = set()

        # Create all Onigiri items
        for widget_id, text in self._WIDGET_DEFINITIONS.items():
            item = SettingsDialog.OnigiriDraggableItem(text, widget_id, style_colors)
            item.archive_requested.connect(self._archive_onigiri_item)
            if widget_id == "restaurant_level":
                item.row_span = 2
                item.col_span = 2
            elif widget_id == "onigimon":
                item.row_span = 2
            elif widget_id == "hexagon_land":
                item.row_span = 2
                item.col_span = 2
            elif widget_id == "deck_stats":
                item.row_span = 2
            elif widget_id == "prep_station":
                item.row_span = 2
                item.col_span = 2
            self.all_onigiri_items[widget_id] = item

        # Update display names from saved config
        all_saved_onigiri = onigiri_grid_config.copy()
        if isinstance(onigiri_archive_config, dict):
            all_saved_onigiri.update(onigiri_archive_config)
        elif isinstance(onigiri_archive_config, list):
            for widget_id in onigiri_archive_config:
                all_saved_onigiri.setdefault(widget_id, {})

        for widget_id, item in self.all_onigiri_items.items():
            if saved_item_config := all_saved_onigiri.get(widget_id):
                if custom_name := saved_item_config.get("display_name"):
                    item.set_display_name(custom_name)
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = saved_item_config.get("orientation", "horizontal")

        # Place Onigiri items on unified grid
        for widget_id, config in onigiri_grid_config.items():
            if item := self.all_onigiri_items.get(widget_id):
                item.row_span = config.get("row", 1)
                item.col_span = config.get("col", 1)
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = config.get("orientation", "horizontal")
                    # Nook Level can never be less than 2 rows tall
                    item.row_span = 2
                    item.col_span = max(1, min(2, item.col_span))
                if widget_id == "hexagon_land":
                    item.row_span = 2
                    item.col_span = 2
                if widget_id == "deck_stats":
                    item.row_span = max(1, min(2, item.row_span))
                    item.col_span = max(1, min(2, item.col_span))
                if widget_id == "prep_station":
                    # Study Plans is always exactly 2 rows tall; columns (1-4) set how many plans show
                    item.row_span = 2
                    item.col_span = max(1, min(4, item.col_span))
                if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                    placed_onigiri.add(widget_id)

        # Place Onigiri items in archive
        archive_ids = []
        if isinstance(onigiri_archive_config, list):
            archive_ids = onigiri_archive_config
        elif isinstance(onigiri_archive_config, dict):
            archive_ids = onigiri_archive_config.keys()
        
        for widget_id in archive_ids:
            if item := self.all_onigiri_items.get(widget_id):
                if widget_id not in placed_onigiri:
                    self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
                    placed_onigiri.add(widget_id)

        # Place any unconfigured Onigiri items into archive
        for widget_id, item in self.all_onigiri_items.items():
            if widget_id not in placed_onigiri:
                self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)

        # --- External Widgets ---
        saved_external_layout = self.settings_dialog.current_config.get("externalWidgetLayout", {})
        if saved_external_layout and "grid" not in saved_external_layout:
            external_grid_config = saved_external_layout
            external_archive_config = {}
        else:
            external_grid_config = saved_external_layout.get("grid", {})
            external_archive_config = saved_external_layout.get("archive", {})

        external_hooks = self.settings_dialog._get_external_hooks()

        # Create all external items
        debug_shown = False
        from .. import patcher
        for hook_id in external_hooks:
            if "learner_stats_widget" in hook_id:
                continue

            # Try to get friendly name from addonManager
            addon_id = hook_id.split('.')[0]
            try:
                display_name = mw.addonManager.addonName(addon_id)
            except:
                display_name = addon_id
            display_name = patcher.get_external_hook_display_name(hook_id, display_name or addon_id)

            item = SettingsDialog.DraggableItem(display_name or addon_id, hook_id, style_colors)
            item.setProperty("isExternalWidget", True)
            item.row_span = 2
            item.archive_requested.connect(self._archive_external_item)
            self.all_external_items[hook_id] = item

        template_name = "Deck Stats"

        for hook_id in external_grid_config.keys():
            if hook_id == "learner_stats_widget" or hook_id.startswith("learner_stats_widget_instance_"):
                item = SettingsDialog.DraggableItem(template_name, hook_id, style_colors)
                item.setProperty("isExternalWidget", True)
                item.archive_requested.connect(self._archive_external_item)
                self.all_external_items[hook_id] = item

        # Combine grid and archive configs for display names
        all_saved_external = {**external_grid_config, **external_archive_config}

        for hook_id, item in self.all_external_items.items():
            if saved_item_config := all_saved_external.get(hook_id):
                if custom_name := saved_item_config.get("display_name"):
                    # If the custom name is just the package ID, assume it was the old default
                    # and let the new friendly name take precedence.
                    package_id = hook_id.split('.')[0]
                    if custom_name != package_id:
                        item.set_display_name(custom_name)

        placed_external = set()
        
        # Place external items on unified grid
        for hook_id, config in external_grid_config.items():
            if hook_id in self.all_external_items:
                item = self.all_external_items[hook_id]
                item.row_span = max(2, config.get("row_span", 2))
                item.col_span = config.get("column_span", 1)
                if self.grid_zone.place_item(item, config.get("grid_position", 0), silent=True):
                    placed_external.add(hook_id)
        
        # Place external items in archive
        for hook_id in external_archive_config.keys():
            if hook_id in self.all_external_items:
                item = self.all_external_items[hook_id]
                self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
                placed_external.add(hook_id)

        # Place any new/unplaced external add-ons in the archive
        for hook_id in external_hooks:
            if "learner_stats_widget" in hook_id:
                continue
            if hook_id not in placed_external:
                item = self.all_external_items[hook_id]
                self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)

    def _archive_onigiri_item(self, item):
        """Moves an Onigiri item from the grid to the Onigiri archive zone."""
        for shelf in self.grid_zone.shelves.values():
            if shelf.child_widget is item:
                shelf.child_widget = None
                shelf.show() # Make the shelf visible again
        self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
        # Reset properties and visibility
        item.setProperty("isOnGrid", False)
        item.grid_zone = None
        item._update_size() # Apply compact size
        item.show()
        
        # Reset spans when archiving
        if item.widget_id == "heatmap":
            item.row_span, item.col_span = 2, 4
        elif item.widget_id == "restaurant_level":
            item.row_span, item.col_span = 2, 2
            item.restaurant_orientation = "horizontal"
        elif item.widget_id == "onigimon":
            item.row_span, item.col_span = 2, 1
        elif item.widget_id == "hexagon_land":
            item.row_span, item.col_span = 2, 2
        elif item.widget_id == "deck_stats":
            item.row_span, item.col_span = 2, 1
        elif item.widget_id == "prep_station":
            item.row_span, item.col_span = 2, 2
        else:
            item.row_span, item.col_span = 1, 1

    def _archive_external_item(self, item):
        """Moves an external item from the grid to the archive, or deletes dynamic learner stats clones."""
        for shelf in self.grid_zone.shelves.values():
            if shelf.child_widget is item:
                shelf.child_widget = None
                shelf.show() # Make the shelf visible again

        if item.widget_id.startswith("learner_stats_widget_instance_"):
            item.setParent(None)
            item.deleteLater()
            self.all_external_items.pop(item.widget_id, None)
        else:
            self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
            item.setProperty("isOnGrid", False)
            item.setProperty("isExternalWidget", True)
            item.grid_zone = None
            item._update_size() # Apply compact size
            item.show()

    def get_layout_config(self):
        """Returns separate configs for Onigiri and External layouts."""
        onigiri_grid_config = {}
        external_grid_config = {}
        processed_widgets = set()

        for pos, shelf in self.grid_zone.shelves.items():
            widget = shelf.child_widget
            if widget and widget not in processed_widgets:
                # Check if it's an Onigiri widget
                if isinstance(widget, SettingsDialog.OnigiriDraggableItem):
                    row_span = widget.row_span
                    col_span = widget.col_span
                    if widget.widget_id == "deck_stats":
                        row_span = max(1, min(2, row_span))
                        col_span = max(1, min(2, col_span))
                    widget_config = {
                        "pos": pos, "row": row_span, "col": col_span,
                        "display_name": widget.display_name
                    }
                    if widget.widget_id == "restaurant_level":
                        widget_config["orientation"] = widget.restaurant_orientation
                    onigiri_grid_config[widget.widget_id] = widget_config
                else:
                    # External widget
                    external_grid_config[widget.widget_id] = {
                        "grid_position": pos, "row_span": max(2, widget.row_span), "column_span": widget.col_span,
                        "display_name": widget.display_name
                    }
                processed_widgets.add(widget)

        onigiri_archive_config = self.onigiri_archive_zone.get_archive_config()
        external_archive_config = self.external_archive_zone.get_archive_config()
        
        return {
            "onigiri": {
                "grid": onigiri_grid_config, 
                "archive": onigiri_archive_config,
                "column_count": self._applied_col_count,
                "grid_width": self.grid_width_spin.value(),
                "grid_alignment": (
                    self.grid_alignment_group.checkedButton().property("grid_alignment")
                    if self.grid_alignment_group.checkedButton()
                    else "center"
                ),
                "widget_height": self.widget_height_spin.value()
            },
            "external": {"grid": external_grid_config, "archive": external_archive_config}
        }

    def reset_widget_names(self):
        """Resets all widget display names to their defaults."""
        changes_made = False
        
        # Reset Onigiri widgets
        for widget_id, default_name in self._WIDGET_DEFINITIONS.items():
            if item := self.all_onigiri_items.get(widget_id):
                # Check if name is different to avoid unnecessary updates? 
                # Simpler to just reset.
                if item.display_name != default_name:
                    item.set_display_name(default_name)
                    changes_made = True
        
        # Reset External widgets
        from .. import patcher
        for hook_id, item in self.all_external_items.items():
            default_name = patcher.get_external_hook_display_name(hook_id, hook_id.split('.')[0])
            if item.display_name != default_name:
                item.set_display_name(default_name)
                changes_made = True
                
        if changes_made:
            showInfo("Widget names have been reset to defaults.")
        else:
            showInfo("Widget names are already at defaults.")

    def reset_layout(self):
        """
        Resets everything to default:
        - Grid height = 6 rows
        - Onigiri widgets in default positions
        - All external widgets archived
        """
        # 1. Reset Row Count
        self._applied_row_count = 6
        self._applied_col_count = 4
        self._set_grid_dimension_inputs(6, 4)
        self.row_apply_hint_label.setVisible(False)
        self.col_apply_hint_label.setVisible(False)

        self.grid_width_spin.setValue(230)
        self.widget_height_spin.setValue(120)
        for btn in self.grid_alignment_group.buttons():
            btn.setChecked(btn.property("grid_alignment") == "center")
        
        # Re-initialize grid with 6 rows (this clears current shelves)
        self.grid_zone.row_count = 6
        # We need to manually clear items because update_grid_rows tries to restore them
        # So let's fully clear the grid first
        
        # Move all grid items to a temporary holding state (or just detach them)
        grid_items = []
        for shelf in self.grid_zone.shelves.values():
            if widget := shelf.child_widget:
                grid_items.append(widget)
                shelf.child_widget = None
                widget.setParent(None)
                widget.grid_zone = None
                widget.setProperty("isOnGrid", False)
        
        # Also clear layouts of shelves, just in case
        for i in reversed(range(self.grid_zone.grid_layout.count())): 
            item = self.grid_zone.grid_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        self.grid_zone.shelves = {}
        
        # Re-create shelves structure for 6 rows
        self.grid_zone.update_grid_dimensions(6, 4) # Reset to default 6x4

        # 2. Reset Onigiri Widgets
        placed_onigiri = set()
        
        # Place default items
        for widget_id, config in self._ONIGIRI_DEFAULTS["grid"].items():
            if item := self.all_onigiri_items.get(widget_id):
                item.row_span = config.get("row", 1)
                item.col_span = config.get("col", 1)
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = "horizontal"
                
                # Ensure item is clean
                item.grid_zone = None
                item.setProperty("isOnGrid", False)
                
                if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                    placed_onigiri.add(widget_id)
        
        # Archive remaining Onigiri widgets
        for widget_id, item in self.all_onigiri_items.items():
            if widget_id not in placed_onigiri:
                # Move to archive if not already there
                current_archive_items = self.onigiri_archive_zone.get_item_order()
                # If it was on grid, it's now detached. If it was in archive, it might still be there.
                # Safest is to remove from wherever it is and add to archive
                if item.parent() == self.onigiri_archive_zone:
                     # Already in archive zone, but maybe we want to reorder? 
                     # Let's just ensure properties are correct
                     pass
                else:
                    # Add to archive layout
                    self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
                
                item.setProperty("isOnGrid", False)
                item.grid_zone = None
                if widget_id == "restaurant_level":
                    item.restaurant_orientation = "horizontal"
                item._update_size() # Compact size
                item.show()

        # 3. Archive ALL External Widgets
        for hook_id, item in self.all_external_items.items():
            # Move to archive if not already there
            if item.parent() != self.external_archive_zone:
                 self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
            
            item.setProperty("isOnGrid", False)
            item.grid_zone = None
            item.row_span = 1
            item.col_span = 1
            item._update_size() # Compact size
            item.show()

        showInfo("Layout has been reset to defaults.")


class AdaptiveModeCard(QWidget):
    """A mode card that can switch between vertical and horizontal layouts."""
    def __init__(self, title, toggle_widget, items, addon_path, parent=None):
        super().__init__(parent)
        self.title = title
        self.toggle_widget = toggle_widget
        self.items = items
        self.addon_path = addon_path
        self.current_mode = "vertical"
        
        # Main layout that will hold either vertical or horizontal card
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create both layouts
        self.vertical_card = self._create_vertical_layout()
        self.horizontal_card = self._create_horizontal_layout()
        
        # Start with vertical by default
        self.main_layout.addWidget(self.vertical_card)
        self.horizontal_card.hide()

    def _theme_tokens(self):
        settings = self.parent()
        palette = settings._settings_palette() if hasattr(settings, "_settings_palette") else {}
        return {
            "card_bg": palette.get("--highlight-bg", "#1e1e1e" if theme_manager.night_mode else "#e8e8e8"),
            "item_bg": palette.get("--canvas-inset", "#2c2c2c" if theme_manager.night_mode else "#f2f2f2"),
            "text": palette.get("--fg", "#f2f2f2" if theme_manager.night_mode else "#2c2c2c"),
            "muted": palette.get("--fg-subtle", "#aaaaaa" if theme_manager.night_mode else "#555555"),
            "warning_bg": palette.get("--highlight-bg", "rgba(255, 235, 59, 0.15)" if theme_manager.night_mode else "#fff9c4"),
            "warning_text": palette.get("--fg", "#fff9c4" if theme_manager.night_mode else "#665c00"),
        }
        
    def _create_vertical_layout(self):
        """Create the vertical card layout (original style)."""
        card = QFrame()
        card.setObjectName("hideModeCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tokens = self._theme_tokens()
        card.setStyleSheet(f"""
            QFrame#hideModeCard {{
                background-color: {tokens["card_bg"]};
                border-radius: 16px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 15, 8, 20)

        # Title
        title_label = QLabel(self.title)
        title_label.setObjectName("hideModeTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: rgba(128, 128, 128, 0.3); max-height: 1px; }")
        layout.addWidget(separator)
        layout.addSpacing(1)

        # Content area for items
        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background: transparent; }")
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(7)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Add items
        for section_name, item_list in self.items:
            for item in item_list:
                item_box = QFrame()
                item_box.setObjectName("hideModeItemBox")
                
                # Check if this item is a warning (Restart note or OS specific note)
                is_warning = any(w in item for w in [tr("restart_anki_note"), tr("windows_linux_only")])
                
                if is_warning:
                    bg_color = tokens["warning_bg"]
                    text_color = tokens["warning_text"]
                    item_box.setStyleSheet(f"""
                        QFrame#hideModeItemBox {{
                            background-color: {bg_color};
                            border-radius: 10px;
                            padding: 12px 10px;
                            min-height: 20px;
                        }}
                    """)
                else:
                    item_box.setStyleSheet(f"""
                        QFrame#hideModeItemBox {{
                            background-color: {tokens["item_bg"]};
                            border-radius: 10px;
                            padding: 12px 10px;
                            min-height: 20px;
                        }}
                    """)
                
                box_layout = QHBoxLayout(item_box)
                box_layout.setContentsMargins(0, 0, 0, 0)
                
                item_label = QLabel(item)
                item_label.setWordWrap(True)
                
                if is_warning:
                    item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    item_label.setStyleSheet(f"font-size: 11px; color: {text_color}; background: transparent; font-weight: bold;")
                else:
                    item_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    item_label.setStyleSheet(f"font-size: 11px; color: {tokens['text']}; background: transparent;")
                        
                box_layout.addWidget(item_label)
                content_layout.addWidget(item_box)

        content_layout.addStretch()
        layout.addWidget(content_widget)

        # Toggle button at bottom using simple alignment
        layout.addStretch()
        layout.addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignHCenter)

        return card
        
    def _create_horizontal_layout(self):
        """Create the horizontal hero-style card layout."""
        card = QFrame()
        card.setObjectName("hideModeHeroCard")
        card.setMinimumHeight(140)
        tokens = self._theme_tokens()
        card.setStyleSheet(f"""
            QFrame#hideModeHeroCard {{
                background-color: {tokens["card_bg"]};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        
        main_layout = QHBoxLayout(card)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Align all items vertically
        
        # Left side - Title as large text (no icon for modes)
        title_label = QLabel(self.title)
        title_label.setObjectName("hideModeHeroTitle")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: 300; color: {tokens['text']}; background: transparent;")
        title_label.setMinimumWidth(80)
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Center - Features with proper warning styling
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(6)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # Collect all features and check for warnings
        all_features = []
        for section_name, item_list in self.items:
            all_features.extend(item_list)
        
        # Display features, with warnings in yellow containers
        for feature in all_features:
            # Check if this feature is a warning
            is_warning = any(w in feature for w in [tr("restart_anki_note"), tr("windows_linux_only")])
            
            if is_warning:
                # Create compact yellow warning container
                warning_container = QWidget()
                warning_container_layout = QHBoxLayout(warning_container)
                warning_container_layout.setContentsMargins(0, 0, 0, 0)
                
                warning_box = QFrame()
                warning_box.setObjectName("hideModeWarningBox")
                
                bg_color = tokens["warning_bg"]
                text_color = tokens["warning_text"]
                
                warning_box.setStyleSheet(f"""
                    QFrame#hideModeWarningBox {{
                        background-color: {bg_color};
                        border-radius: 16px;
                        padding: 6px 12px;
                    }}
                """)
                
                warning_layout = QHBoxLayout(warning_box)
                warning_layout.setContentsMargins(0, 0, 0, 0)
                
                warning_label = QLabel(feature)
                warning_label.setWordWrap(True)
                warning_label.setStyleSheet(f"font-size: 10px; color: {text_color}; background: transparent; font-weight: bold;")
                warning_layout.addWidget(warning_label)
                
                # Add warning box to container and align left
                warning_container_layout.addWidget(warning_box)
                warning_container_layout.addStretch()
                
                center_layout.addWidget(warning_container)
            else:
                # Regular feature text
                feature_label = QLabel(f"• {feature}")
                feature_label.setObjectName("sectionDescription")
                feature_label.setWordWrap(True)
                center_layout.addWidget(feature_label)
        
        center_layout.addStretch()
        
        main_layout.addWidget(center_widget, 1)
        
        # Right side - Toggle (aligned vertically with title)
        # Add directly to main layout for proper vertical centering
        main_layout.addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        return card
        
    def set_layout_mode(self, mode):
        """Switch between vertical and horizontal layouts."""
        if mode == self.current_mode:
            return
            
        self.current_mode = mode
        
        # Remove toggle from current parent before switching
        if self.toggle_widget.parent():
            self.toggle_widget.setParent(None)
        
        if mode == "horizontal":
            self.vertical_card.hide()
            if self.horizontal_card.parent() is None:
                self.main_layout.addWidget(self.horizontal_card)
            self.horizontal_card.show()
            # Re-add toggle to horizontal layout
            self.horizontal_card.layout().addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:  # vertical
            self.horizontal_card.hide()
            if self.vertical_card.parent() is None:
                self.main_layout.addWidget(self.vertical_card)
            self.vertical_card.show()
            # Re-add toggle to vertical layout
            self.vertical_card.layout().addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignHCenter)


class ResponsiveModeCardsContainer(QWidget):
    """Container that switches mode cards between horizontal and vertical layouts based on width."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode_cards = []
        self.current_layout_mode = "vertical"
        self.threshold_width = 900  # Width below which cards switch to horizontal
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create initial layout container with horizontal layout
        self.layout_container = QWidget()
        self.current_cards_layout = QHBoxLayout(self.layout_container)
        self.current_cards_layout.setSpacing(20)
        self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.layout_container)
        
    def add_mode_card(self, card):
        """Add a mode card to the container."""
        self.mode_cards.append(card)
        self.current_cards_layout.addWidget(card)
        
    def resizeEvent(self, event):
        """Handle resize events to switch layouts."""
        super().resizeEvent(event)
        new_width = event.size().width()
        
        # Determine which mode we should be in
        should_be_horizontal = new_width < self.threshold_width
        
        # Switch layouts if needed
        if should_be_horizontal and self.current_layout_mode == "vertical":
            self._switch_to_horizontal_mode()
        elif not should_be_horizontal and self.current_layout_mode == "horizontal":
            self._switch_to_vertical_mode()
            
    def _switch_to_horizontal_mode(self):
        """Switch all cards to horizontal hero-style layout and stack them vertically."""
        self.current_layout_mode = "horizontal"
        
        # Remove all cards from current layout
        while self.current_cards_layout.count():
            item = self.current_cards_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Remove and delete old layout container
        self.main_layout.removeWidget(self.layout_container)
        self.layout_container.deleteLater()
        
        # Create new layout container with vertical layout
        self.layout_container = QWidget()
        self.current_cards_layout = QVBoxLayout(self.layout_container)
        self.current_cards_layout.setSpacing(15)
        self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.layout_container)
        
        # Add cards back in vertical layout and switch card mode
        for card in self.mode_cards:
            card.set_layout_mode("horizontal")
            self.current_cards_layout.addWidget(card)
            
    def _switch_to_vertical_mode(self):
        """Switch all cards to vertical layout and arrange them horizontally."""
        self.current_layout_mode = "vertical"
        
        # Remove all cards from current layout
        while self.current_cards_layout.count():
            item = self.current_cards_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Remove and delete old layout container
        self.main_layout.removeWidget(self.layout_container)
        self.layout_container.deleteLater()
        
        # Create new layout container with horizontal layout
        self.layout_container = QWidget()
        self.current_cards_layout = QHBoxLayout(self.layout_container)
        self.current_cards_layout.setSpacing(20)
        self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.layout_container)
        
        # Add cards back in horizontal layout and switch card mode
        for card in self.mode_cards:
            card.set_layout_mode("vertical")
            self.current_cards_layout.addWidget(card)
