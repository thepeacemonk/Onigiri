"""Custom rename dialog with a 'Show full path' toggle."""

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton,
)


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

    # --- Buttons ---
    showing_full = [False]
    btn_row = QHBoxLayout()

    if parent_prefix:
        path_btn = QPushButton("Full path")

        def toggle_path():
            showing_full[0] = not showing_full[0]
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
    save_btn = QPushButton("Save")
    save_btn.setDefault(True)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    result = [None]

    def on_save():
        text = input_field.text().strip()
        if text:
            result[0] = text
        dialog.accept()

    def on_cancel():
        dialog.reject()

    save_btn.clicked.connect(on_save)
    cancel_btn.clicked.connect(on_cancel)
    input_field.returnPressed.connect(on_save)

    dialog.exec()
    return result[0]
