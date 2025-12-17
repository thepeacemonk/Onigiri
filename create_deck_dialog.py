from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

class CreateDeckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Deck")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Explanation
        info_label = QLabel("Enter the name of the new deck and optionally select a parent deck.")
        info_label.setWordWrap(True)
        self.layout.addWidget(info_label)

        # Deck Name Input
        self.layout.addWidget(QLabel("Deck Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Chapter 1")
        self.layout.addWidget(self.name_input)
        
        # Focus name input
        self.name_input.setFocus()

        # Parent Deck Selection
        self.layout.addWidget(QLabel("Parent Deck:"))
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("None (Top Level)", "")
        
        # Enable search
        self.parent_combo.setEditable(True)
        self.parent_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.parent_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.parent_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.parent_combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        # Populate with existing decks
        # We get all deck names. 
        # Note: mw.col.decks.all_names_and_ids() returns a list of objects with .name and .id attributes in newer Anki versions,
        # or we can iterate mw.col.decks.all()
        
        decks = []
        try:
             # Try modern API first
             for d in mw.col.decks.all_names_and_ids():
                 if d.name != "Default": # Optional: filter out Default if desired, but user might want it
                     decks.append(d.name)
        except AttributeError:
             # Fallback for older API if needed (unlikely for addons21 but good practice)
             for d in mw.col.decks.all():
                 if d['name'] != "Default":
                     decks.append(d['name'])
        
        decks.sort()
        
        for name in decks:
            self.parent_combo.addItem(name, name)
            
        self.layout.addWidget(self.parent_combo)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            showInfo("Please enter a deck name.")
            return

        idx = self.parent_combo.currentIndex()
        if idx != -1:
            parent_name = self.parent_combo.itemData(idx)
        else:
            parent_name = self.parent_combo.currentText().strip()
            if parent_name == "None (Top Level)":
                parent_name = ""
        
        if parent_name:
            full_name = f"{parent_name}::{name}"
        else:
            full_name = name
            
        try:
            # Check if deck exists
            # mw.col.decks.id() creates it if missing, returns id if exists.
            # We might want to warn if it exists?
            # Standard Anki behavior just opens/selects it.
            
            deck_id = mw.col.decks.id(full_name)
            
            # Select the new deck
            mw.col.decks.select(deck_id)
            
            # Refresh main window to show new deck
            mw.reset()
            
            tooltip(f"Created deck: {full_name}")
            super().accept()
            
        except Exception as e:
            showInfo(f"Error creating deck: {e}")
