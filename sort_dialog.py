from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QRadioButton, QButtonGroup, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt
from aqt import mw
from aqt.utils import tooltip

SORT_MODE_KEY = "onigiri_sort_mode"
CUSTOM_ORDER_KEY = "onigiri_custom_deck_order"


class SortDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Sort Decks")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui()
        self._load_state()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Sort Order")
        f = title.font()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        self._radio_group = QButtonGroup(self)
        self._radios = {}
        for key, label in [
            ("alphabetical_az", "Alphabetical  A → Z"),
            ("alphabetical_za", "Alphabetical  Z → A"),
            ("most_due",        "Most Cards Due"),
            ("most_new",        "Most New Cards"),
            ("custom",          "Custom Order"),
        ]:
            rb = QRadioButton(label)
            self._radio_group.addButton(rb)
            self._radios[key] = rb
            layout.addWidget(rb)
            if key == "custom":
                rb.toggled.connect(self._on_custom_toggled)

        layout.addSpacing(4)

        self._custom_label = QLabel("Drag rows to reorder  ·  top = first in list")
        self._custom_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._custom_label)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setMinimumHeight(180)
        self._list.setStyleSheet("""
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 4px;
                outline: 0;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin: 1px 0;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:hover:!selected {
                background: palette(alternate-base);
            }
        """)
        layout.addWidget(self._list)
        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        self._populate_list()

    def _populate_list(self):
        self._list.clear()
        tree = mw.col.sched.deck_due_tree()
        nodes = list(tree.children)

        saved_order = [str(x) for x in mw.col.conf.get(CUSTOM_ORDER_KEY, [])]

        def sort_key(node):
            did = str(node.deck_id)
            return saved_order.index(did) if did in saved_order else len(saved_order)

        nodes.sort(key=sort_key)

        for node in nodes:
            name = node.name.split("::")[-1]
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, str(node.deck_id))
            self._list.addItem(item)

    def _load_state(self):
        mode = mw.col.conf.get(SORT_MODE_KEY, "alphabetical_az")
        self._radios.get(mode, self._radios["alphabetical_az"]).setChecked(True)

    def _on_custom_toggled(self, checked: bool):
        self._custom_label.setVisible(checked)
        self._list.setVisible(checked)
        if not checked:
            self.adjustSize()

    def _save_and_close(self):
        mode = next((k for k, rb in self._radios.items() if rb.isChecked()), "alphabetical_az")
        mw.col.conf[SORT_MODE_KEY] = mode

        if mode == "custom":
            order = [self._list.item(i).data(Qt.ItemDataRole.UserRole)
                     for i in range(self._list.count())]
            mw.col.conf[CUSTOM_ORDER_KEY] = order

        mw.col.setMod()
        self.accept()

        from . import deck_tree_updater
        if hasattr(mw, "deckBrowser"):
            mw.deckBrowser._render_data = None  # force fresh tree fetch + re-sort
            deck_tree_updater.refresh_deck_tree_state(mw.deckBrowser)

        tooltip("Sort order applied.")


def show_sort_dialog():
    SortDialog(mw).exec()
