"""Custom rename dialog with a 'Show full path' toggle."""

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QColor,
)
from aqt import mw
from aqt.theme import theme_manager
from .color_utils import get_contrast_text_color


def show_rename_dialog(parent, leaf_name: str, full_name: str, parent_prefix: str):
    """Show a rename dialog.

    Returns the new name string (leaf or full path as the user left it),
    or None if the user cancelled.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Rename Deck")
    dialog.setMinimumWidth(500)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(8)
    layout.setContentsMargins(16, 16, 16, 14)

    # --- Label ---
    label = QLabel("Deck name:")
    layout.addWidget(label)

    # --- Input field ---
    input_field = QLineEdit()
    input_field.setText(leaf_name)
    input_field.setMinimumHeight(32)
    input_field.selectAll()
    layout.addWidget(input_field)
    layout.addStretch()

    # --- Accent color (hardcoded) ---
    accent = "#007aff"
    accent_qc = QColor(accent)
    accent_hover = accent_qc.darker(115).name()
    save_text = "#ffffff"

    # --- Theme-aware secondary button colours (match settings.py conventions) ---
    if theme_manager.night_mode:
        sec_bg, sec_border, sec_text, sec_hover = "#3a3a3a", "#555", "#e0e0e0", "#4a4a4a"
    else:
        sec_bg, sec_border, sec_text, sec_hover = "#f0f0f0", "#ccc", "#212121", "#e0e0e0"
    sec_style = (
        f"QPushButton {{ padding: 2px 12px; border-radius: 8px; border: 1px solid {sec_border}; "
        f"background: {sec_bg}; color: {sec_text}; }}"
        f"QPushButton:hover {{ background: {sec_hover}; }}"
    )
    save_style = (
        f"QPushButton {{ padding: 2px 12px; border-radius: 8px; border: 1px solid {accent}; "
        f"background: {accent}; color: {save_text}; }}"
        f"QPushButton:hover {{ padding: 2px 12px; border-radius: 8px; border: 1px solid {accent}; "
        f"background: {accent_hover}; color: {save_text}; }}"
    )

    # --- Toggle + Buttons ---
    showing_full = [False]
    btn_row = QHBoxLayout()

    path_btn = QPushButton("Full path")
    path_btn.setCheckable(True)
    path_btn.setChecked(False)
    path_btn.setStyleSheet(sec_style + f" QPushButton:checked {{ background: {accent}; color: {save_text}; border-color: {accent}; }}")

    def toggle_path():
        showing_full[0] = not showing_full[0]
        path_btn.setChecked(showing_full[0])
        if showing_full[0]:
            input_field.setText(full_name)
            path_btn.setText("Leaf name")
        else:
            current = input_field.text()
            leaf = current.split("::")[-1] if "::" in current else current
            input_field.setText(leaf)
            path_btn.setText("Full path")
        input_field.setFocus()
        input_field.selectAll()

    path_btn.clicked.connect(toggle_path)
    btn_row.addWidget(path_btn)

    btn_row.addStretch()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(sec_style)
    save_btn = QPushButton("Save")
    save_btn.setStyleSheet(save_style)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    result = [None, False]

    def on_save():
        text = input_field.text().strip()
        if text:
            result[0] = text
            result[1] = showing_full[0]
        dialog.accept()

    def on_cancel():
        dialog.reject()

    save_btn.clicked.connect(on_save)
    cancel_btn.clicked.connect(on_cancel)
    input_field.returnPressed.connect(on_save)

    dialog.exec()
    return result
