# coloris_picker.py
import json
import os
import re
from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    Qt,
    pyqtSignal,
    pyqtSlot,
    QObject,
    QDialogButtonBox,
    QUrl
)
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

# --- The Bridge Object ---
# This object is exposed to JavaScript.
# JS can call its @pyqtSlot methods, and Python
# can emit its pyqtSignals.

class Bridge(QObject):
    # Signal to Python that a color was picked
    colorAccepted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initial_color = "#FFFFFF"

    def set_initial_color(self, color):
        """Called by Python to set the color before showing."""
        self._initial_color = color

    @pyqtSlot(result=str)
    def getInitialColor(self):
        """Called by JavaScript to get the starting color."""
        return self._initial_color

    @pyqtSlot(str)
    def onColorSelected(self, color_hex):
        """
        Called by JavaScript ONLY when the Python
        dialog's "OK" button is clicked.
        """
        self.colorAccepted.emit(color_hex)

    @pyqtSlot(result=str)
    def getFavoriteColors(self):
        try:
            colors = mw.col.conf.get("onigiri_coloris_favorites", []) if mw and mw.col else []
        except Exception:
            colors = []
        if not isinstance(colors, list):
            colors = []
        slots = []
        for color in colors[:9]:
            color = str(color).strip().upper()
            slots.append(color if re.match(r"^#[0-9A-F]{6}$", color) else "")
        while len(slots) < 9:
            slots.append("")
        return json.dumps(slots)

    @pyqtSlot(str)
    def setFavoriteColors(self, colors_json):
        try:
            colors = json.loads(colors_json)
        except Exception:
            colors = []
        if not isinstance(colors, list):
            colors = []
        slots = []
        for color in colors[:9]:
            color = str(color).strip().upper()
            slots.append(color if re.match(r"^#[0-9A-F]{6}$", color) else "")
        while len(slots) < 9:
            slots.append("")
        try:
            if mw and mw.col:
                mw.col.conf["onigiri_coloris_favorites"] = slots
                mw.col.setMod()
        except Exception as exc:
            print(f"Onigiri: Could not save Coloris favorites: {exc}")


# --- The Custom Color Dialog ---
# This dialog will replace QColorDialog

class ColorisColorDialog(QDialog):
    def __init__(self, initial_color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        # Set a fixed size that fits the inline Coloris picker nicely.
        self.setFixedSize(360, 405)

        # Store the selected color
        self.selected_color = initial_color

        # 1. Create the Web View and Page
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(self)
        self.view.setPage(self.page)
        # Make the web view background transparent
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.page.setBackgroundColor(Qt.GlobalColor.transparent)

        # 2. Create the Bridge and set initial color
        self.bridge = Bridge(self)
        self.bridge.set_initial_color(initial_color)

        # 3. Create the Web Channel
        self.channel = QWebChannel(self)
        self.page.setWebChannel(self.channel)
        
        # Expose the bridge object to JavaScript under the name "py_bridge"
        self.channel.registerObject("py_bridge", self.bridge)

        # 4. Connect signal from the bridge back to the dialog
        self.bridge.colorAccepted.connect(self.on_accept)
        
        # 5. Load the HTML file
        addon_path = os.path.dirname(__file__)
        html_path = os.path.join(
            addon_path, "system_files", "coloris", "color-picker.html"
        )
        if not os.path.exists(html_path):
            self.view.setHtml("<h1>Error: color-picker.html not found.</h1>")
        else:
            self.view.setUrl(QUrl.fromLocalFile(html_path))

        # 6. Create our own OK/Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setCenterButtons(True)
        done_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if done_button:
            done_button.setText("Done")
        if cancel_button:
            cancel_button.setText("Cancel")
        self.button_box.setStyleSheet("""
            QDialogButtonBox {
                qproperty-centerButtons: true;
            }
            QPushButton {
                min-width: 86px;
                min-height: 34px;
                padding: 0 18px;
                border-radius: 17px;
                border: 1px solid rgba(128, 128, 128, 0.35);
                background-color: rgba(128, 128, 128, 0.16);
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: rgba(10, 132, 255, 0.65);
                background-color: rgba(10, 132, 255, 0.16);
            }
        """)
        self.button_box.accepted.connect(self.on_ok_clicked)
        self.button_box.rejected.connect(self.reject)

        # 7. Set up the layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.view)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def on_ok_clicked(self):
        """
        When the user clicks "OK", we execute JavaScript
        to get the current color from the picker.
        The JS will then call py_bridge.onColorSelected(color).
        """
        self.page.runJavaScript(
            "(window.currentColor ? window.currentColor() : null);",
            lambda color: self.on_accept(color or self.selected_color),
        )

    @pyqtSlot(str)
    def on_accept(self, color_hex):
        """Internal slot to store the color and accept the dialog."""
        self.selected_color = color_hex
        self.accept()

    @staticmethod
    def getColor(initial_color, parent):
        """
        A static method that mimics QColorDialog.getColor().
        Returns (color_str, bool_ok)
        """
        dialog = ColorisColorDialog(initial_color, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            return dialog.selected_color, True
        else:
            return initial_color, False
