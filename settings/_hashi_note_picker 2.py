# Picker for the Hashi Notes widget's "Pinned note" setting.
#
# The setting used to be a plain QComboBox listing note titles, which said
# nothing about what the pinned note actually looks like. This dialog shows the
# real notes as miniatures (the same tinted card the widget/pop-up paints), plus
# an "Most recent note" tile for the automatic pin, and only writes the choice
# back when the user presses Save.
from ._common import *
from ._picker_chrome import (
    CELL_RADIUS,
    CONTROL_RADIUS,
    close_qss,
    container_qss,
    picker_palette,
    pill_qss,
    scroll_qss,
    section_title_qss,
    title_qss,
)


AUTO_NOTE_ID = ""  # "" == follow the newest note


class HashiNoteCell(QFrame):
    """One note miniature. Click selects, double-click selects and saves."""

    def __init__(self, note_id, on_select, on_activate, parent=None):
        super().__init__(parent)
        self.note_id = note_id
        self._on_select = on_select
        self._on_activate = on_activate
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self._on_select(self.note_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._on_select(self.note_id)
        self._on_activate()
        super().mouseDoubleClickEvent(event)


class HashiNotePickerDialog(QDialog):
    """Gallery of note miniatures; emits the chosen note id on Save."""

    noteSelected = pyqtSignal(str)

    COLUMNS = 3
    CELL_HEIGHT = 132

    def __init__(self, current_note_id, notes, parent=None, accent="#00A982", night_mode=None):
        super().__init__(parent)
        self._dark = bool(theme_manager.night_mode) if night_mode is None else bool(night_mode)
        self._accent = accent if QColor(accent).isValid() else "#00A982"
        self._pal = picker_palette(self._dark, self._accent)
        self.notes = list(notes or [])
        self.selected_note_id = str(current_note_id or AUTO_NOTE_ID)
        self._cells = {}

        self.setWindowTitle(tr("hashi_widget_pinned_note", "Pinned note"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.container = QFrame()
        self.container.setObjectName("IconPickerContainer")
        self.container.setStyleSheet(container_qss(self._pal))
        outer.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(tr("hashi_widget_pinned_note", "Pinned note"))
        title.setStyleSheet(title_qss(self._pal))
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(close_qss(self._pal))
        close_btn.clicked.connect(self.close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        subtitle = QLabel(
            tr("hashi_widget_pinned_note_desc", "Choose the note the widget shows in Single note mode.")
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(section_title_qss(self._pal))
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scroll_qss(self._pal))
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        grid_host = QWidget()
        self.grid = QGridLayout(grid_host)
        self.grid.setContentsMargins(0, 0, 6, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        scroll.setWidget(grid_host)
        layout.addWidget(scroll, 1)

        self._build_cells()

        footer = QHBoxLayout()
        footer.setSpacing(10)
        save_btn = QPushButton(tr("save", "Save"))
        cancel_btn = QPushButton(tr("cancel", "Cancel"))
        for btn in (save_btn, cancel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            # ID selector: the settings window's plain QPushButton rules would
            # otherwise square these off (same reason as the icon picker).
            btn.setObjectName("iconPickerFooterPill")
        save_btn.setStyleSheet(pill_qss(self._pal, primary=True))
        cancel_btn.setStyleSheet(pill_qss(self._pal))
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn.clicked.connect(self.close)
        footer.addStretch()
        footer.addWidget(save_btn)
        footer.addWidget(cancel_btn)
        footer.addStretch()
        layout.addLayout(footer)

    # --- cells ------------------------------------------------------------

    def _note_fill(self, color):
        """The note's colour tinted the same way the pop-up tints its shell."""
        color = str(color or "").strip()
        if not color:
            return self._pal["inset"]
        try:
            from .. import hashi_notes

            return hashi_notes._fill_tint(color, self._dark)
        except Exception:
            return self._pal["inset"]

    def _cell_qss(self, fill, selected):
        border = self._accent if selected else "transparent"
        width = 2 if selected else 1
        return (
            f"QFrame#hashiNoteCell {{ background: {fill}; border: {width}px solid {border};"
            f" border-radius: {CELL_RADIUS}px; }}"
            " QFrame#hashiNoteCell QLabel { background: transparent; border: none; }"
        )

    def _build_cells(self):
        cells = [(AUTO_NOTE_ID, None)] + [(str(n.get("id") or ""), n) for n in self.notes]
        for index, (note_id, note) in enumerate(cells):
            cell = self._build_cell(note_id, note)
            self._cells[note_id] = cell
            self.grid.addWidget(cell, index // self.COLUMNS, index % self.COLUMNS)
        rows = (len(cells) + self.COLUMNS - 1) // self.COLUMNS
        self.grid.setRowStretch(rows, 1)
        self._refresh_selection()

    def _build_cell(self, note_id, note):
        cell = HashiNoteCell(note_id, self._select, self._save_and_close)
        cell.setObjectName("hashiNoteCell")
        cell.setFixedHeight(self.CELL_HEIGHT)
        cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        box = QVBoxLayout(cell)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        if note is None:
            title_text = tr("hashi_widget_newest_note", "Most recent note")
            body_text = tr(
                "hashi_widget_newest_note_desc", "Always shows whichever note you edited last."
            )
            color = ""
            date_text = ""
        else:
            title_text = note.get("title") or tr("hashi_untitled", "Untitled")
            color = note.get("color") or ""
            try:
                from .. import hashi_notes

                body_text = hashi_notes._plain_excerpt(note.get("body_md"), 160)
                date_text = hashi_notes._widget_date_label(
                    note.get("updated_at") or note.get("created_at")
                )
            except Exception:
                body_text = str(note.get("body_md") or "")
                date_text = ""
            if not body_text:
                body_text = tr("hashi_empty_note", "Empty note")

        head = QHBoxLayout()
        head.setSpacing(6)
        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot_color = color or self._accent
        dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
        head.addWidget(dot)
        title_label = QLabel(title_text)
        title_label.setStyleSheet(
            f"color: {self._pal['fg']}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.addWidget(title_label, 1)
        box.addLayout(head)

        body_label = QLabel(body_text)
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body_label.setStyleSheet(
            f"color: {self._pal['muted']}; font-size: 11px; background: transparent;"
        )
        box.addWidget(body_label, 1)

        if date_text:
            date_label = QLabel(date_text)
            date_label.setStyleSheet(
                f"color: {self._pal['muted']}; font-size: 10px; background: transparent;"
            )
            box.addWidget(date_label)

        cell.setProperty("hashi_fill", self._note_fill(color))
        return cell

    def _refresh_selection(self):
        for note_id, cell in self._cells.items():
            fill = cell.property("hashi_fill") or self._pal["inset"]
            cell.setStyleSheet(self._cell_qss(fill, note_id == self.selected_note_id))

    def _select(self, note_id):
        self.selected_note_id = note_id
        self._refresh_selection()

    def _save_and_close(self):
        self.noteSelected.emit(self.selected_note_id)
        self.close()
