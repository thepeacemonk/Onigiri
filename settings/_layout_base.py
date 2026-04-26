import os
import json
from aqt.qt import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QStackedWidget, QFrame, QSizePolicy,
    QPen, QBrush,
    QButtonGroup,
    QDrag, QMimeData, QPoint,
    QMenu, QAction, QActionGroup,
    QGridLayout, QGroupBox, QSpinBox,
    QPixmap, Qt, QPainter, QPainterPath, QScrollArea,
)
from PyQt6.QtCore import pyqtSignal, QSize, QTimer, QMimeData as _QMimeData

from aqt import mw
from aqt.theme import theme_manager


class CustomMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Make it a frameless pop-up window
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Background frame that we can style
        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("MenuBackground")
        self.layout.addWidget(self.background_frame)

        # Layout for the buttons inside the frame
        self.content_layout = QVBoxLayout(self.background_frame)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(4)

    def add_action_button(self, text, data, group, is_checked):
        button = QPushButton(text)
        button.setObjectName("MenuButton")
        button.setCheckable(True)
        button.setChecked(is_checked)
        group.addButton(button)
        
        # Store data in the button itself
        button.setProperty("action_data", data)
        
        self.content_layout.addWidget(button)
        return button

    def add_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("MenuSeparator")
        # Give it a fixed height and some margin
        sep.setFixedHeight(1)
        self.content_layout.addSpacing(4)
        self.content_layout.addWidget(sep)
        self.content_layout.addSpacing(4)
        
    def focusOutEvent(self, event):
        # Close the menu if the user clicks elsewhere
        self.close()

class DraggableItem(QFrame):
    """A draggable QLabel that also stores its grid span and handles resizing."""
    archive_requested = pyqtSignal(object)
    
    # Constants for grid cell sizing
    CELL_WIDTH = 120
    CELL_HEIGHT = 60
    CELL_SPACING = 10

    def __init__(self, text, widget_id, style_colors, parent=None):
        super().__init__(parent)


        self.widget_id = widget_id
        self._col_span = 1
        self._row_span = 1
        self.display_name = text  # Store the display name
        self.grid_zone = None
        self.setObjectName("DraggableItem")
        
        # Initial size (will be updated when spans change)
        self._update_size()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)

        # Use a QStackedWidget to switch between label and line edit
        self.stack = QStackedWidget()
        self.label = QLabel(self.display_name)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.line_edit = QLineEdit(self.display_name)
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.stack.addWidget(self.label)
        self.stack.addWidget(self.line_edit)
        # FIX: Add stretch factor and alignment flag
        layout.addWidget(self.stack, 1)

        # Finish editing when Enter is pressed or focus is lost
        self.line_edit.editingFinished.connect(self._finish_editing)

        button_bg, border, fg = style_colors['button_bg'], style_colors['border'], style_colors['fg']
        self.setStyleSheet(f"""
            QFrame#DraggableItem {{
                background-color: {button_bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QLabel, QLineEdit {{
                color: {fg};
                font-weight: 500;
                background-color: transparent;
                border: none;
                padding-left: 5px; /* Add some padding for left alignment */
            }}
            QLineEdit {{
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """)

        # Set tooltip and truncated label logic
        self._update_display()
    
    def resizeEvent(self, event):
        self._update_display()
        super().resizeEvent(event)

    def _update_display(self):
        """Updates the label and tooltip based on the current display_name."""
        if not self.label: return

        # Calculate available width (total width - margins/padding)
        # 20px buffer: 10px margins (5+5) + 5px padding + safe buffer
        available_width = self.width() - 25  
        if available_width <= 0:
             # Fallback if width isn't ready yet (e.g. init)
             if self.property("isOnGrid"):
                 available_width = (self.CELL_WIDTH * self._col_span) - 25
             else:
                 available_width = 300 # Default/Archive width guess

        metrics = self.label.fontMetrics()
        elided = metrics.elidedText(self.display_name, Qt.TextElideMode.ElideRight, available_width)
        
        self.label.setText(elided)
        self.setToolTip(f"{self.display_name}\nID: {self.widget_id}\nDouble-click to rename.")
        
    def _update_size(self):
        """Update the widget's size based on its current spans.
        Uses minimum size with Expanding policy so QGridLayout can stretch it."""
        if self.property("isOnGrid"):
            width = self.CELL_WIDTH * self._col_span + self.CELL_SPACING * (self._col_span - 1)
            height = self.CELL_HEIGHT * self._row_span + self.CELL_SPACING * (self._row_span - 1)
            self.setMinimumSize(width, height)
            self.setMaximumSize(16777215, 16777215) # Reset max size
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            # Archived state: Compact size
            self.setMinimumSize(0, 45)
            self.setMaximumSize(16777215, 45) # Force fixed height
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    @property
    def col_span(self):
        return self._col_span
    
    @col_span.setter
    def col_span(self, value):
        self._col_span = value
        self._update_size()
    
    @property
    def row_span(self):
        return self._row_span
    
    @row_span.setter
    def row_span(self, value):
        self._row_span = value
        self._update_size()

    def set_display_name(self, name):
        """Updates the display name from outside the class."""
        self.display_name = name
        self.line_edit.setText(name)
        self._update_display()

    def _finish_editing(self):
        """Called when user finishes renaming."""
        new_name = self.line_edit.text()
        self.display_name = new_name
        self._update_display()
        self.stack.setCurrentIndex(0)  # Switch back to the label view

    def mouseDoubleClickEvent(self, event):
        """Switch to edit mode on double-click."""
        # FIX: Properly check button, state, and accept the event
        if self.stack.currentIndex() == 0 and event.button() == Qt.MouseButton.LeftButton:
            self.stack.setCurrentIndex(1)
            self.line_edit.selectAll()
            self.line_edit.setFocus()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
        if (event.pos() - self.drag_start_position).manhattanLength() < 10: return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"{self.widget_id}|{self.col_span}|{self.row_span}")
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.pos())
        
        # Make the widget semi-transparent using opacity effect instead of hiding
        # This maintains the widget's space in the layout
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        opacity_effect = QGraphicsOpacityEffect(self)
        opacity_effect.setOpacity(0.3)
        self.setGraphicsEffect(opacity_effect)
        
        result = drag.exec(Qt.DropAction.MoveAction)
        
        # Remove the opacity effect after drag
        self.setGraphicsEffect(None)
        
        # If the drop was cancelled, make sure the widget is visible
        if result == Qt.DropAction.IgnoreAction:
            self.show()
    
    def contextMenuEvent(self, event):
        if not self.property("isOnGrid") or not self.grid_zone: return

        custom_menu = CustomMenu(self.window())

        # --- Width Actions ---
        width_group = QButtonGroup(custom_menu)
        width_group.setExclusive(True)
        for i in range(1, 5):
            btn = custom_menu.add_action_button(f"{i} Column{'s' if i > 1 else ''}", i, width_group, self.col_span == i)

        custom_menu.add_separator()

        # --- Height Actions ---
        height_group = QButtonGroup(custom_menu)
        height_group.setExclusive(True)
        for i in range(1, 4):
            btn = custom_menu.add_action_button(f"{i} Row{'s' if i > 1 else ''}", i, height_group, self.row_span == i)
        
        # --- ADD THIS BLOCK ---
        custom_menu.add_separator()
        
        archive_button = QPushButton("Archive")
        archive_button.setObjectName("MenuButton")
        archive_button.clicked.connect(lambda: (self.archive_requested.emit(self), custom_menu.close()))
        custom_menu.content_layout.addWidget(archive_button)
        # --- END OF NEW BLOCK ---

        # --- Handle Clicks ---
        def on_menu_action():
            new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
        
        # --- Handle Clicks ---
        def on_menu_action():
            new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
            new_row_span = height_group.checkedButton().property("action_data") if height_group.checkedButton() else self.row_span

            if new_col_span != self.col_span or new_row_span != self.row_span:
                self.grid_zone.request_resize(self, new_row_span, new_col_span)
            custom_menu.close()

        width_group.buttonClicked.connect(on_menu_action)
        height_group.buttonClicked.connect(on_menu_action)

        # Show the menu at the cursor position
        custom_menu.move(self.mapToGlobal(event.pos()))
        custom_menu.show()

class DropZone(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")

    def is_item_allowed(self, item):
        """
        Determines if a dragged item is allowed to be dropped in this zone.
        Default implementation allows DraggableItem but rejects OnigiriDraggableItem
        (matching the behavior for generic/external zones).
        """
        if isinstance(item, OnigiriDraggableItem):
            return False
        return isinstance(item, DraggableItem)

    def dragEnterEvent(self, event):
        source_widget = event.source()
        if event.mimeData().hasText() and self.is_item_allowed(source_widget):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        source_widget = event.source()
        if self.is_item_allowed(source_widget):
            event.acceptProposedAction()
            # --- FIX: Pass the event to _handle_drop for position info ---
            self._handle_drop(source_widget, event)
        else:
            event.ignore()
    
    def _handle_drop(self, widget, event): pass # Subclasses will implement this

class VerticalDropZone(DropZone):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(5); self.layout.addStretch()
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        
        # Placeholder to open space during drag
        self.drop_placeholder = QWidget()
        self.drop_placeholder.setFixedHeight(45)
        # Fully transparent
        self.drop_placeholder.setStyleSheet("background-color: transparent;")
        self.drop_placeholder.hide()

    def update_drop_indicator(self, pos):
        # Calculate where the placeholder should be
        layout = self.layout
        
        # Get all widgets except placeholder and non-widgets (like stretch)
        widgets = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and item.widget() is not self.drop_placeholder:
                widgets.append(item.widget())
        
        target_index = len(widgets) # Default to end
        
        for i, widget in enumerate(widgets):
            # If mouse is above the center of this widget
            if pos.y() < widget.y() + widget.height() // 2:
                target_index = i
                break
        
        # Check if placeholder is already at the right spot
        current_index = layout.indexOf(self.drop_placeholder)
        
        if current_index != target_index:
            if current_index != -1:
                layout.removeWidget(self.drop_placeholder)
                # When we remove it, indices shift. But target_index was calculated
                # based on the "clean" list of widgets, so it represents the
                # intended insertion point among them.
            
            layout.insertWidget(target_index, self.drop_placeholder)
            self.drop_placeholder.show()
        
        return target_index

    def dragEnterEvent(self, event):
        source_widget = event.source()
        if self.is_item_allowed(source_widget):
             event.acceptProposedAction()
             self.update_drop_indicator(event.position().toPoint())
        else:
             event.ignore()

    def dragMoveEvent(self, event):
        source_widget = event.source()
        if self.is_item_allowed(source_widget):
             event.acceptProposedAction()
             self.update_drop_indicator(event.position().toPoint())
        else:
             event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_placeholder.hide()
        self.layout.removeWidget(self.drop_placeholder)
        event.accept()

    def dropEvent(self, event):
        # Find where the placeholder is, that's our drop spot
        index = self.layout.indexOf(self.drop_placeholder)
        
        self.drop_placeholder.hide()
        self.layout.removeWidget(self.drop_placeholder)
        
        # If placeholder wasn't there (fallback)
        if index == -1:
             index = self.update_drop_indicator(event.position().toPoint())
             self.drop_placeholder.hide()
             self.layout.removeWidget(self.drop_placeholder)
        
        source_widget = event.source()
        if self.is_item_allowed(source_widget):
             self._handle_drop(source_widget, event, insert_index=index)
             event.acceptProposedAction()
        else:
             event.ignore()

    def _handle_drop(self, widget, event, insert_index=-1):
        # If the widget came from a grid, tell the grid to release it
        if hasattr(widget, 'grid_zone') and widget.grid_zone:
            # Get a reference to the grid's layout before we change the parent
            grid_layout = widget.grid_zone.layout()

            # Remove the logical reference from all shelves
            for shelf in widget.grid_zone.shelves.values():
                if shelf.child_widget is widget:
                    shelf.child_widget = None
                    shelf.show() # Make the shelf visible again
            
            # Explicitly remove the widget from the grid's layout
            grid_layout.removeWidget(widget)

        # This part handles items being reordered within the archive itself
        elif old_parent := widget.parent():
            if old_layout := old_parent.layout:
                old_layout.removeWidget(widget)
        
        widget.row_span, widget.col_span = 1, 1
        widget.setProperty("isOnGrid", False)
        widget.grid_zone = None
        widget.setParent(self)
        widget._update_size() # Apply compact size
        
        if insert_index != -1:
            # insertWidget(index, widget)
            # Note: QVBoxLayout.insertWidget inserts at index. 
            # Be careful about the stretch item at the end.
            # If insert_index is larger than current count, it appends.
            self.layout.insertWidget(insert_index, widget)
        else:
            # Insert before the stretch (which is at count-1 normally)
            # But layout.count() includes the stretch.
            # Usually we want to append to the list of widgets.
            # The stretch is added at __init__.
            # So inserting at count()-1 puts it before the stretch.
            self.layout.insertWidget(self.layout.count() - 1, widget)
            
        widget.show()
        
    def get_item_order(self):
        return [self.layout.itemAt(i).widget().widget_id for i in range(self.layout.count()) if isinstance(self.layout.itemAt(i).widget(), DraggableItem)]
    
    def get_archive_config(self):
        config = {}
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            if item and (widget := item.widget()):
                if isinstance(widget, DraggableItem):
                    config[widget.widget_id] = {"display_name": widget.display_name}
        return config

class GridDropZone(DropZone):
    def __init__(self, main_editor, parent=None):
        super().__init__(parent)
        self.main_editor = main_editor
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        # Adapt size to content
        self.grid_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.shelves = {}
        self.highlighted_shelf = None
        self.row_count = 6
        self.col_count = 4
        
        # Initialize grid
        # Initialize grid
        self.update_grid_dimensions(self.row_count)

    def update_grid_dimensions(self, rows, cols=None):
        if cols is None:
            cols = self.col_count
        
        # Use safe defaults if 0 to avoid errors during logic, 
        # but we will skip shelf creation if dimensions are zero.
        safe_rows = max(1, rows)
        safe_cols = max(1, cols) if cols > 0 else 1

        # Use a dict mapped by their primary (top-left) position to avoid duplicates
        current_widgets = {}
        processed_widgets = set()
        
        # Find all widgets currently on the grid
        for pos, shelf in self.shelves.items():
            try:
                widget = shelf.child_widget
                # check if widget is valid (not C++ deleted)
                if widget and not widget.isHidden() and widget not in processed_widgets:
                     # Trying to access property or method will raise RuntimeError if deleted
                    widget_pos = self.get_widget_pos(widget) 
                    current_widgets[widget] = widget_pos
                    processed_widgets.add(widget)
                    # Important: Hide widget before causing it to detach from layout
                    # otherwise it might flash as a separate window
                    widget.hide()
            except RuntimeError:
                # Widget primitive deleted, skip
                continue
        
        # Detach widgets from shelves to avoid issues during shelf deletion
        for shelf in self.shelves.values():
            shelf.child_widget = None
        
        # Clear existing layout items (shelves and widgets)
        # CAREFUL: Use safer deletion loop
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.hide()
                w.setParent(None)
                if w.objectName() == "Shelf":
                    w.deleteLater() # Explicitly schedule deletion for shelves only
        
        self.shelves = {}
        
        self.row_count = rows
        self.col_count = cols
        
        # If dimensions are zero, we just clear and return (Sidebar Only Mode)
        if rows == 0 or cols == 0:
            return

        # Create shelves
        for i in range(rows * self.col_count):
            shelf = Shelf(self)
            self.shelves[i] = shelf
            row, col = divmod(i, self.col_count)
            self.grid_layout.addWidget(shelf, row, col)
        
        # Set column sizing
        for col in range(self.col_count):
            self.grid_layout.setColumnMinimumWidth(col, 120)
            self.grid_layout.setColumnStretch(col, 1)
        
        # Clear sizing for unused columns
        for col in range(self.col_count, 10):
            self.grid_layout.setColumnMinimumWidth(col, 0)
            self.grid_layout.setColumnStretch(col, 0)

        # Set row sizing
        for row in range(rows):
            self.grid_layout.setRowMinimumHeight(row, 60)
            self.grid_layout.setRowStretch(row, 1)
        
        # Clear sizing for unused rows (up to a reasonable max)
        for row in range(rows, 20):
            self.grid_layout.setRowMinimumHeight(row, 0)
            self.grid_layout.setRowStretch(row, 0)

        # Restore widgets if they fit
        # Sort widgets by their original position to try and maintain order
        sorted_widgets = sorted(current_widgets.items(), key=lambda item: item[1])
        
        # List of widgets to archive (if they don't fit)
        widgets_to_archive = []

        for widget, old_pos in sorted_widgets:
            # CRITICAL FIX: Ensure widget fits in new column count
            # If widget is wider than the grid, shrink it to fit max width
            if widget.col_span > cols:
                widget.col_span = cols
            
            # Check for row span consistency too (optional but good safety)
            if widget.row_span > rows:
                 widget.row_span = rows

            # Try to place at the same approximate relative position or first available
            if self.place_item(widget, old_pos, silent=True):
                continue
            
            # If exact old pos didn't work (e.g. because cols changed), try finding first free spot
            if self.place_item_auto(widget):
                continue
                
            # If still fails, add to archive list
            widgets_to_archive.append(widget)

        # Process archiving asynchronously to avoid layout issues
        if widgets_to_archive:
            from aqt.utils import QTimer
            QTimer.singleShot(0, lambda: self._archive_detached_widgets(widgets_to_archive))

    def _archive_detached_widgets(self, widgets):
        for widget in widgets:
            try:
                if widget: # Check if still valid
                    widget.archive_requested.emit(widget)
            except RuntimeError:
                pass

    def get_widget_pos(self, widget):
        for pos, shelf in self.shelves.items():
            if shelf.child_widget is widget:
                return pos
        return 0
        
    def place_item_auto(self, item):
        grid_size = self.row_count * self.col_count
        for i in range(grid_size):
            r, c = divmod(i, self.col_count)
            try:
                if self.is_region_free(r, c, item.row_span, item.col_span, ignored_widget=item):
                    if self.place_item(item, i, silent=True):
                        return True
            except Exception:
                continue # specific error handling if needed
        return False



    def dragMoveEvent(self, event):
        # Check if the item is allowed before processing the move
        if not self.is_item_allowed(event.source()):
            event.ignore()
            return

        if self.highlighted_shelf:
            self.highlighted_shelf.set_highlight(False)
            self.highlighted_shelf = None
        
        for shelf in self.shelves.values():
            # --- FIX: Use event.position() instead of event.pos() ---
            if shelf.geometry().contains(event.position().toPoint()):
                shelf.set_highlight(True)
                self.highlighted_shelf = shelf
                break
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if self.highlighted_shelf:
            self.highlighted_shelf.set_highlight(False)
            self.highlighted_shelf = None
        event.accept()

    def _handle_drop(self, widget, event):
        if self.highlighted_shelf:
            self.highlighted_shelf.set_highlight(False)
            self.highlighted_shelf = None

        target_pos = -1
        for pos, shelf in self.shelves.items():
            # --- FIX: Use event.position() instead of event.pos() ---
            if shelf.geometry().contains(event.position().toPoint()):
                target_pos = pos
                break
        
        if target_pos != -1:
            # <<< START NEW CODE >>>
            # If widget is coming from outside a grid (e.g., the archive), reset its size
            if not widget.property("isOnGrid"):
                if isinstance(widget, OnigiriDraggableItem):
                    if widget.widget_id == "heatmap":
                        widget.row_span, widget.col_span = 2, 4
                    elif widget.widget_id == "restaurant_level":
                        widget.row_span, widget.col_span = 2, 2
                    else: # It's a stat card
                        widget.row_span, widget.col_span = 1, 1
                else: # External add-on
                    # Default external widgets to 2 rows height as requested
                    widget.row_span, widget.col_span = 2, 1
            # <<< END NEW CODE >>>
            self.place_item(widget, target_pos)
        else:
            widget.show()
    
    def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
        if col + col_span > self.col_count or row + row_span > self.row_count: return False
        for r in range(row, row + row_span):
            for c in range(col, col + col_span):
                pos = r * self.col_count + c
                if pos not in self.shelves: return False
                if self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
        return True

    def place_item(self, item, pos, silent=False):
        # First, uncover any shelves this item was previously covering
        for shelf_pos, shelf in self.shelves.items():
            if shelf.child_widget is item:
                shelf.child_widget = None
                shelf.show()  # Show the shelf again when item is removed
                
        row, col = divmod(pos, self.col_count)
        if not self.is_region_free(row, col, item.row_span, item.col_span, ignored_widget=item):
            grid_size = self.row_count * self.col_count
            for i in range(grid_size):
                r, c = divmod(i, self.col_count)
                if self.is_region_free(r, c, item.row_span, item.col_span, ignored_widget=item):
                    row, col = r, c; break
            else:
                if not silent:
                    QMessageBox.warning(self.window(), "Placement Error", "No available slot was found for this item.")
                item.show() # Ensure the item reappears if the drop fails
                return False
        
        item.setProperty("isOnGrid", True); item.grid_zone = self
        item.setParent(self)
        item._update_size() # Apply grid size
        self.grid_layout.addWidget(item, row, col, item.row_span, item.col_span)
        
        # Mark all covered shelves and hide them (except the first one which stays as anchor)
        for r in range(row, row + item.row_span):
            for c in range(col, col + item.col_span):
                shelf_pos = r * self.col_count + c
                if shelf_pos in self.shelves:
                    self.shelves[shelf_pos].child_widget = item
                    # Hide covered shelves so they don't show through the spanning widget
                    self.shelves[shelf_pos].hide()
        
        item.show()
        
        # Force layout update to ensure geometry is correct
        # This helps prevent floating window glitches or incorrect positioning
        self.grid_layout.update()
        
        return True
    
    def request_resize(self, item, new_row_span, new_col_span):
        new_pos = -1
        # Use dynamic range based on grid size
        grid_size = self.row_count * self.col_count
        for i in range(grid_size):
            r, c = divmod(i, self.col_count)
            if self.is_region_free(r, c, new_row_span, new_col_span, ignored_widget=item):
                new_pos = i; break
        if new_pos == -1:
            QMessageBox.warning(self.window(), "Resize Error", f"No available {new_row_span}x{new_col_span} slot was found on the grid."); return
        
        # Show shelves that are about to be uncovered
        for shelf in self.shelves.values():
            if shelf.child_widget is item: 
                shelf.child_widget = None
                shelf.show()
                
        new_row, new_col = divmod(new_pos, self.col_count)
        conflicting_widgets = set()
        for r in range(new_row, new_row + new_row_span):
            for c in range(new_col, new_col + new_col_span):
                pos = r * self.col_count + c
                if pos in self.shelves and self.shelves[pos].child_widget: 
                    conflicting_widgets.add(self.shelves[pos].child_widget)
        
        for conflicting_item in conflicting_widgets:
            for shelf in self.shelves.values():
                if shelf.child_widget is conflicting_item: 
                    shelf.child_widget = None
                    shelf.show() # Show shelves for conflicting items too

            # Find the first available spot for it and place it there
            found_spot = False
            for i in range(grid_size):
                r, c = divmod(i, self.col_count)
                # Use the item's own size for finding a new spot, default to 1x1 if needed
                r_span = getattr(conflicting_item, 'row_span', 1)
                c_span = getattr(conflicting_item, 'col_span', 1)
                if self.is_region_free(r, c, r_span, c_span):
                    self.place_item(conflicting_item, i)
                    found_spot = True
                    break
            if not found_spot:
                # Fallback: if no space for its size is found, try to place as 1x1
                for i in range(grid_size):
                    r, c = divmod(i, self.col_count)
                    if self.is_region_free(r, c, 1, 1):
                        conflicting_item.row_span = 1
                        conflicting_item.col_span = 1
                        self.place_item(conflicting_item, i)
                        break
        
        item.row_span, item.row_span = new_row_span, new_row_span # Wait, typo in original? No, item.row_span...
        # The replacement content has a typo, let me fix it
        item.row_span = new_row_span
        item.col_span = new_col_span
        self.place_item(item, new_pos)
    
    # settings.py

    def get_layout_config(self):
        layout, processed_widgets = {}, set()
        for pos, shelf in self.shelves.items():
            widget = shelf.child_widget
            if widget and widget not in processed_widgets:
                layout[widget.widget_id] = { 
                    "grid_position": pos, 
                    "row_span": widget.row_span, 
                    "column_span": widget.col_span,
                    "display_name": widget.display_name
                }
                processed_widgets.add(widget)
        return layout

class Shelf(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Shelf")
        # Use minimum size but allow expansion to fill the grid cell
        # This ensures it matches the size of widgets which also expand
        self.setMinimumSize(120, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.child_widget = None

    def set_highlight(self, highlighted):
        # --- FIX: Use setProperty to make the state visible to the stylesheet ---
        # Check the current property to avoid unnecessary style refreshes
        current_highlight = self.property("is_highlighted") or False
        if current_highlight != highlighted:
            self.setProperty("is_highlighted", highlighted)
            self.style().polish(self)

# =================================================================
# START: Onigiri Widget Layout Editor
# =================================================================

