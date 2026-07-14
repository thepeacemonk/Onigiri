from aqt.qt import QLayout, QPoint, QRect, QSize, QSizePolicy, Qt, QWidgetItem


class FlowLayout(QLayout):
    """A responsive layout that arranges widgets horizontally when space permits."""

    def __init__(self, parent=None, margin=0, spacing=-1, stretch_rows=False):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list = []
        # When True, each row's items are grouped using their natural sizeHint
        # widths (to decide how many fit per row) but then stretched evenly so
        # the row fills the full available width, leaving no trailing gap.
        self._stretch_rows = stretch_rows

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def indexOf(self, widget):
        for i, item in enumerate(self._item_list):
            if item.widget() is widget:
                return i
        return -1

    def insertWidget(self, index, widget):
        """Inserts widget into the layout at index without disturbing the
        rest of the item order, for live drag-to-reorder feedback."""
        self.addChildWidget(widget)
        index = max(0, min(index, len(self._item_list)))
        self._item_list.insert(index, QWidgetItem(widget))
        self.invalidate()

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        if self._stretch_rows:
            return self._do_layout_stretch(rect, test_only)

        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            widget = item.widget()
            if widget is None:
                continue

            space_x = spacing
            space_y = spacing
            item_size = item.sizeHint()
            # A widget alone on its row that wants to expand horizontally (e.g. an
            # empty-state panel) should stretch to fill the available width rather
            # than shrink to its content's sizeHint.
            if widget.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding and x == rect.x():
                item_width = max(1, rect.width())
            else:
                item_width = min(item_size.width(), max(1, rect.width()))
            next_x = x + item_width + space_x

            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item_width + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_width, item_size.height())))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y()

    def _do_layout_stretch(self, rect, test_only):
        spacing = self.spacing()

        # First pass: group items into rows using their natural sizeHint widths,
        # wrapping exactly like the default packing logic would.
        rows = []
        current_row = []
        current_width = 0
        for item in self._item_list:
            widget = item.widget()
            if widget is None:
                continue

            item_size = item.sizeHint()
            natural_width = min(item_size.width(), max(1, rect.width()))
            projected_width = natural_width if not current_row else current_width + spacing + natural_width

            if current_row and projected_width > rect.width():
                rows.append(current_row)
                current_row = []
                current_width = 0

            current_row.append((item, item_size))
            current_width = current_width + (spacing if len(current_row) > 1 else 0) + natural_width

        if current_row:
            rows.append(current_row)

        # Second pass: stretch each row's items evenly to fill the full width.
        y = rect.y()
        for row_index, row in enumerate(rows):
            count = len(row)
            total_spacing = spacing * (count - 1)
            available = max(1, rect.width() - total_spacing)
            per_item_width = available / count
            row_height = max(size.height() for _, size in row)

            x = rect.x()
            for item, _ in row:
                if not test_only:
                    item.setGeometry(QRect(QPoint(round(x), round(y)), QSize(round(per_item_width), row_height)))
                x += per_item_width + spacing

            y += row_height
            if row_index < len(rows) - 1:
                y += spacing

        return y - rect.y()
