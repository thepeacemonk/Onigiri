# coloris_picker.py
import os
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


# --- The Custom Color Dialog ---
# This dialog will replace QColorDialog

class ColorisColorDialog(QDialog):
    def __init__(self, initial_color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        # Set a fixed size that fits the inline picker nicely
        self.setFixedSize(300, 420) 

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
        self.page.runJavaScript("requestCurrentColor();")

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