"""Shared UI widgets for Onigiri.

Extracted from the settings widget library so feature modules (Prep Station,
Pomodoro, gamification hub) can use them without importing the settings UI.
"""

from aqt.qt import (
    QAbstractButton,
    QBrush,
    QColor,
    QEasingCurve,
    QLayout,
    QPainter,
    QPainterPath,
    QPen,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QSizePolicy,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QWidgetItem,
    Qt,
    pyqtProperty,
)
from aqt.theme import theme_manager

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


class AnimatedToggleButton(QAbstractButton):
    """Modern toggle switch that follows the active user accent color."""
    def __init__(self, parent=None, accent_color="#00A982"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.accent_color = QColor(accent_color)
        self.track_color_off = QColor("#d1d5db") if not theme_manager.night_mode else QColor("#4b5563")
        self.thumb_color = QColor("#ffffff")

        self.setFixedSize(50, 30)
        self._thumb_x_pos = 0.0
        self._gooey_amount = 0.0
        self._gooey_direction = 1.0

        self.animation = QPropertyAnimation(self, b"thumb_x_pos", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.gooey_animation = QPropertyAnimation(self, b"gooey_amount", self)
        self.gooey_animation.setDuration(230)
        self.gooey_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._start_animation)

    def _track_rect(self):
        return QRectF(3, 3, self.width() - 6, self.height() - 6)

    def _checked_thumb_position(self, checked=None):
        if checked is None:
            checked = self.isChecked()
        track = self._track_rect()
        thumb_r = (track.height() / 2.0) - 3
        if checked:
            return float(track.right() - 3 - (thumb_r * 2))
        return float(track.left() + 3)

    def _sync_thumb_to_checked(self):
        self._thumb_x_pos = self._checked_thumb_position()
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            self.animation.stop()
            self.gooey_animation.stop()
            self._gooey_amount = 0.0
            self._sync_thumb_to_checked()

    def setAccentColor(self, accent_color):
        self.accent_color = QColor(accent_color)
        self.update()

    def setThemeMode(self, is_dark):
        self.track_color_off = QColor("#4b5563") if is_dark else QColor("#d1d5db")
        self.update()

    @pyqtProperty(float)
    def thumb_x_pos(self):
        return self._thumb_x_pos

    @thumb_x_pos.setter
    def thumb_x_pos(self, value):
        self._thumb_x_pos = value
        self.update()

    @pyqtProperty(float)
    def gooey_amount(self):
        return self._gooey_amount

    @gooey_amount.setter
    def gooey_amount(self, value):
        self._gooey_amount = max(0.0, min(1.0, float(value)))
        self.update()

    def _start_animation(self, checked):
        end_pos = self._checked_thumb_position(checked)
        self._gooey_direction = 1.0 if checked else -1.0
        self.animation.setStartValue(self.thumb_x_pos)
        self.animation.setEndValue(float(end_pos))
        self.animation.start()
        self.gooey_animation.stop()
        self.gooey_animation.setStartValue(1.0)
        self.gooey_animation.setEndValue(0.0)
        self.gooey_animation.start()

    @staticmethod
    def draw_lock_icon(painter, center, color, scale=1.0):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), max(1.2, 1.6 * scale))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        body_w = 8.0 * scale
        body_h = 6.2 * scale
        body_x = center.x() - body_w / 2
        body_y = center.y() - body_h / 2 + 1.6 * scale
        painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 1.5 * scale, 1.5 * scale)
        shackle_w = 5.2 * scale
        shackle_h = 7.0 * scale
        shackle_x = center.x() - shackle_w / 2
        shackle_y = body_y - shackle_h * 0.62
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_w, shackle_h), 0, 180 * 16)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_rect = self._track_rect()
        radius = track_rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        locked = not self.isEnabled()
        if locked:
            track_color = QColor("#cfd6df" if not theme_manager.night_mode else "#3f4652")
        else:
            track_color = self.accent_color if self.isChecked() else self.track_color_off
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)
        thumb_r = radius - 3
        thumb_color = QColor("#f8fafc" if locked else self.thumb_color.name())
        thumb_center = QPointF(self._thumb_x_pos + thumb_r, track_rect.center().y())
        if self._gooey_amount > 0.01:
            gooey_path = QPainterPath()
            stretch = (3.5 + 4.5 * self._gooey_amount) * self._gooey_direction
            min_center_x = track_rect.left() + 3 + thumb_r
            max_center_x = track_rect.right() - 3 - thumb_r
            trail_x = max(min_center_x, min(max_center_x, thumb_center.x() - stretch))
            trail_center = QPointF(trail_x, thumb_center.y())
            trail_r = max(thumb_r * 0.56, thumb_r * (0.70 - 0.12 * self._gooey_amount))
            gooey_path.addEllipse(thumb_center, thumb_r + 0.8 * self._gooey_amount, thumb_r)
            gooey_path.addEllipse(trail_center, trail_r, trail_r * 0.94)
            bridge_left = min(thumb_center.x(), trail_center.x())
            bridge_width = abs(thumb_center.x() - trail_center.x())
            gooey_path.addRoundedRect(
                QRectF(bridge_left, track_rect.center().y() - trail_r, bridge_width, trail_r * 2),
                trail_r,
                trail_r,
            )
            painter.setBrush(thumb_color)
            painter.drawPath(gooey_path)
        painter.setBrush(thumb_color)
        painter.drawEllipse(thumb_center, thumb_r, thumb_r)
        if locked:
            lock_color = "#6b7280" if not theme_manager.night_mode else "#cbd5e1"
            thumb_center_x = self._thumb_x_pos + thumb_r
            lock_center_x = track_rect.left() + radius if thumb_center_x > self.width() / 2 else track_rect.right() - radius
            self.draw_lock_icon(painter, QPointF(lock_center_x, track_rect.center().y()), lock_color, 1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_thumb_to_checked()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_thumb_to_checked()


class MainBackgroundEffectSlider(QSlider):
    """Rounded, segmented slider used by the main background effect controls."""
    def __init__(self, accent_color, track_color, border_color, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._accent_color = QColor(accent_color)
        self._track_color = QColor(track_color)
        self._border_color = QColor(border_color)
        self._handle_color = QColor("#ffffff")
        self.setFixedHeight(30)
        self.setMouseTracking(True)

    def wheelEvent(self, event):
        event.ignore()

    @staticmethod
    def draw_lock_icon(painter, center, color, scale=1.0):
        AnimatedToggleButton.draw_lock_icon(painter, center, color, scale)

    def setColors(self, accent_color, track_color, border_color):
        self._accent_color = QColor(accent_color)
        self._track_color = QColor(track_color)
        self._border_color = QColor(border_color)
        self.update()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(max(220, hint.width()), 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        locked = not self.isEnabled()

        paint_pad = 4
        track_height = 22
        handle_radius = (track_height / 2) - 3
        track_left = paint_pad
        track_right = max(track_left + track_height + 1, self.width() - paint_pad)
        track_width = track_right - track_left
        track_top = (self.height() - track_height) / 2
        track_rect = QRectF(track_left, track_top, track_width, track_height)
        handle_min_x = track_rect.left() + (track_height / 2)
        handle_max_x = track_rect.right() - (track_height / 2)

        value_range = max(1, self.maximum() - self.minimum())
        progress = max(0.0, min(1.0, (self.value() - self.minimum()) / value_range))
        handle_x = handle_min_x + (handle_max_x - handle_min_x) * progress

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(track_rect, track_height / 2, track_height / 2)

        if progress <= 0.0:
            active_width = 0.0
        elif progress >= 1.0:
            active_width = track_width
        else:
            active_width = min(track_width, max(0.0, handle_x + handle_radius - track_left))
        if active_width > 0:
            active_rect = QRectF(track_left, track_top, active_width, track_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._accent_color))
            painter.drawRoundedRect(active_rect, track_height / 2, track_height / 2)

        for step in range(1, 6):
            x = track_left + track_width * step / 6
            if x <= track_left + active_width:
                continue
            mark_color = QColor(self._border_color)
            mark_color.setAlpha(95)
            painter.setPen(QPen(mark_color, 1))
            painter.drawLine(QPointF(x, track_top + 4), QPointF(x, track_top + track_height - 4))

        handle_rect = QRectF(
            handle_x - handle_radius,
            (self.height() / 2) - handle_radius,
            handle_radius * 2,
            handle_radius * 2,
        )
        painter.setBrush(QBrush(self._handle_color))
        painter.setPen(QPen(self._accent_color, 3))
        painter.drawEllipse(handle_rect)
        if locked:
            self.draw_lock_icon(
                painter,
                QPointF(handle_rect.center().x(), handle_rect.center().y()),
                "#6b7280" if not theme_manager.night_mode else "#6f6f6f",
                0.88,
            )
