"""A modern, frameless date-picker popup matching OnigiriColorDialog's look
and interaction model (rounded card, soft shadow, click-outside/Escape to
dismiss) so pickers across the add-on feel consistent."""

import calendar
from datetime import date

from aqt import mw
from aqt.qt import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPen,
    Qt,
    QPoint,
    QRectF,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import QEvent, QEventLoop, QLocale, pyqtSignal

from .onigiri_color_picker import _is_dark_mode, _IconButton, REMOVE_ICON_PATH
from .translations import current_locale

POPUP_WIDTH = 280
CELL_SIZE = 34


class _DayCell(QToolButton):
    def __init__(self, dark: bool, accent: QColor, parent=None):
        super().__init__(parent)
        self._dark = dark
        self._accent = accent
        self.day = 0
        self._is_today = False
        self._is_selected = False
        self._is_disabled_day = False
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")

    def set_day(self, day: int, is_today: bool = False, is_selected: bool = False, disabled: bool = False) -> None:
        self.day = day
        self._is_today = is_today
        self._is_selected = is_selected
        self._is_disabled_day = disabled
        self.setVisible(day > 0)
        self.setEnabled(day > 0 and not disabled)
        self.update()

    def paintEvent(self, event) -> None:
        if self.day <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        fg = "#F5F5F6" if self._dark else "#171719"
        muted = "#5A5A60" if self._dark else "#C4C7CB"

        if self._is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._accent)
            painter.drawEllipse(rect)
            text_color = QColor("#ffffff")
        elif self.underMouse() and self.isEnabled():
            hover = QColor(255, 255, 255, 26) if self._dark else QColor(0, 0, 0, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hover)
            painter.drawEllipse(rect)
            text_color = QColor(fg)
        else:
            text_color = QColor(muted) if self._is_disabled_day else QColor(fg)

        if self._is_today and not self._is_selected:
            pen = QPen(self._accent, 1.4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        font = QFont()
        font.setPointSize(11)
        if self._is_selected or self._is_today:
            font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.day))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _OnigiriDatePopup(QFrame):
    finished = pyqtSignal(object, bool)

    def __init__(self, initial_date, parent=None, anchor=None, accent="#00A982", min_date=None):
        super().__init__(parent)
        self._anchor = anchor
        self._dark = _is_dark_mode()
        self._finished = False
        self._event_filter_installed = False
        self._accent = QColor(accent)
        self._min_date = min_date
        self._selected = initial_date or date.today()
        self._year = self._selected.year
        self._month = self._selected.month

        self.setObjectName("OnigiriDatePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(POPUP_WIDTH)

        bg = "#28282A" if self._dark else "#FFFFFF"
        border = "#3F3F44" if self._dark else "#F1F1F1"
        self.setStyleSheet(
            f"QFrame#OnigiriDatePopup {{ background-color: {bg}; border: 1px solid {border}; border-radius: 22px; }}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 95 if self._dark else 45))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        fg = "#F5F5F6" if self._dark else "#171719"

        header = QHBoxLayout()
        header.setSpacing(4)
        self.prev_btn = self._nav_button(-1, fg)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {fg}; background: transparent;")
        self.next_btn = self._nav_button(1, fg)
        self.close_button = _IconButton(REMOVE_ICON_PATH, self._dark, parent=self)
        self.close_button.clicked.connect(self.cancel)
        header.addWidget(self.prev_btn)
        header.addWidget(self.month_label, 1)
        header.addWidget(self.next_btn)
        header.addSpacing(6)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        weekday_row = QHBoxLayout()
        weekday_row.setSpacing(0)
        muted = "#8A8A90" if self._dark else "#9AA0A6"
        for letter in self._weekday_letters():
            lbl = QLabel(letter)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(CELL_SIZE)
            lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {muted}; background: transparent;")
            weekday_row.addWidget(lbl)
        layout.addLayout(weekday_row)

        grid = QGridLayout()
        grid.setSpacing(2)
        self._cells = []
        for r in range(6):
            row_cells = []
            for c in range(7):
                cell = _DayCell(self._dark, self._accent, self)
                cell.clicked.connect(lambda _=False, rr=r, cc=c: self._on_cell_clicked(rr, cc))
                grid.addWidget(cell, r, c)
                row_cells.append(cell)
            self._cells.append(row_cells)
        layout.addLayout(grid)

        today_row = QHBoxLayout()
        today_row.addStretch()
        self.today_btn = QToolButton()
        self.today_btn.setText(_tr_today())
        self.today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.today_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; color: {self._accent.name()}; "
            f"font-size: 11px; font-weight: 700; padding: 4px 8px; }}"
        )
        self.today_btn.clicked.connect(self._jump_today)
        today_row.addWidget(self.today_btn)
        today_row.addStretch()
        layout.addLayout(today_row)

        self._refresh_grid()

    def _nav_button(self, direction: int, fg: str) -> QToolButton:
        btn = QToolButton()
        btn.setFixedSize(26, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hover = "rgba(255,255,255,0.08)" if self._dark else "rgba(0,0,0,0.06)"
        btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 13px; "
            f"color: {fg}; font-size: 15px; font-weight: 700; }}"
            f"QToolButton:hover {{ background: {hover}; }}"
        )
        btn.setText("‹" if direction < 0 else "›")
        btn.clicked.connect(lambda: self._shift_month(direction))
        return btn

    def _weekday_letters(self) -> list:
        locale = current_locale()
        return [locale.dayName(d, QLocale.FormatType.NarrowFormat) for d in range(1, 8)]

    def _shift_month(self, delta: int) -> None:
        m = self._month - 1 + delta
        self._year += m // 12
        self._month = m % 12 + 1
        self._refresh_grid()

    def _jump_today(self) -> None:
        today = date.today()
        self._year, self._month = today.year, today.month
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        locale = current_locale()
        self.month_label.setText(f"{locale.monthName(self._month, QLocale.FormatType.LongFormat)} {self._year}")

        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)
        today = date.today()

        day_num = 1 - first_weekday
        for r in range(6):
            for c in range(7):
                cell = self._cells[r][c]
                if 1 <= day_num <= days_in_month:
                    d = date(self._year, self._month, day_num)
                    disabled = bool(self._min_date and d < self._min_date)
                    cell.set_day(day_num, is_today=(d == today), is_selected=(d == self._selected), disabled=disabled)
                else:
                    cell.set_day(0)
                day_num += 1

    def _on_cell_clicked(self, r: int, c: int) -> None:
        cell = self._cells[r][c]
        if cell.day <= 0:
            return
        self._selected = date(self._year, self._month, cell.day)
        self.accept()

    def _position_at_top(self) -> None:
        self.adjustSize()
        parent = self.parentWidget()
        if not parent:
            return
        margin = 8
        if self._anchor and self._anchor.window() is parent:
            anchor_pos = self._anchor.mapTo(parent, QPoint(0, 0))
            below_y = anchor_pos.y() + self._anchor.height() + 6
            above_y = anchor_pos.y() - self.height() - 6
            x = anchor_pos.x()
            y = below_y if below_y + self.height() <= parent.height() - margin else max(margin, above_y)
        else:
            cursor_pos = parent.mapFromGlobal(QCursor.pos())
            x = cursor_pos.x() - 18
            y = cursor_pos.y() + 10
            if y + self.height() > parent.height() - margin:
                y = cursor_pos.y() - self.height() - 10
        x = max(margin, min(x, parent.width() - self.width() - margin))
        y = max(margin, min(y, parent.height() - self.height() - margin))
        self.move(x, y)

    def show_at_top(self) -> None:
        self._position_at_top()
        if not self._event_filter_installed:
            QApplication.instance().installEventFilter(self)
            self._event_filter_installed = True
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def eventFilter(self, obj, event):
        if self._finished or not self.isVisible():
            return False
        if obj is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._position_at_top()
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            widget = QApplication.widgetAt(global_pos)
            while widget:
                if widget is self:
                    return False
                widget = widget.parentWidget()
            self.cancel()
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._finished:
            self.cancel()
        super().closeEvent(event)

    def accept(self) -> None:
        self._finish(self._selected, True)

    def cancel(self) -> None:
        self._finish(self._selected, False)

    def _finish(self, value, accepted: bool) -> None:
        if self._finished:
            return
        self._finished = True
        try:
            if self._event_filter_installed:
                QApplication.instance().removeEventFilter(self)
                self._event_filter_installed = False
        except Exception:
            pass
        self.hide()
        self.finished.emit(value, accepted)


def _tr_today() -> str:
    try:
        from .translations import tr

        return tr("today", "Today")
    except Exception:
        return "Today"


class OnigiriDateDialog:
    @staticmethod
    def getDate(initial_date, parent=None, anchor=None, accent="#00A982", min_date=None):
        app = QApplication.instance()
        if app is None:
            return initial_date, False

        root = parent.window() if parent else app.activeWindow()
        if root is None:
            root = mw.app.activeWindow() if mw and mw.app else None
        if root is None:
            return initial_date, False

        result = {"date": initial_date, "ok": False}
        loop = QEventLoop()
        popup = _OnigiriDatePopup(initial_date, root, anchor=anchor, accent=accent, min_date=min_date)

        def finish(value, accepted):
            result["date"] = value
            result["ok"] = accepted
            loop.quit()

        popup.finished.connect(finish)
        popup.show_at_top()
        loop.exec()
        popup.deleteLater()
        return result["date"], result["ok"]
