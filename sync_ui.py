from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    Qt, QFrame, QSizePolicy, QGraphicsDropShadowEffect, QColor
)
from datetime import datetime
from .sync import onigiri_sync

class SyncConflictDialog(QDialog):
    """
    Dialog shown when there is a difference between local and cloud data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Onigiri Sync Conflict")
        self.setFixedWidth(500)
        self.result_choice = None # 'local' or 'cloud'

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("Sync Conflict Detected")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #B94632;")
        layout.addWidget(header)

        desc = QLabel("Your local Onigiri progress differs from the data on AnkiWeb. Please choose which version you would like to keep.")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #555;")
        layout.addWidget(desc)

        # Comparison Area
        comp_layout = QHBoxLayout()
        comp_layout.setSpacing(15)

        local_time = onigiri_sync.get_local_mtime()
        cloud_time = onigiri_sync.get_cloud_mtime()

        self.local_card = self._create_info_card(
            "Local Device", 
            local_time, 
            is_newer=(local_time > cloud_time)
        )
        self.cloud_card = self._create_info_card(
            "AnkiWeb (Cloud)", 
            cloud_time, 
            is_newer=(cloud_time > local_time)
        )

        comp_layout.addWidget(self.local_card)
        comp_layout.addWidget(self.cloud_card)
        layout.addLayout(comp_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.keep_local_btn = QPushButton("Keep Local (Upload)")
        self.keep_local_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_local_btn.clicked.connect(self._on_keep_local)
        self.keep_local_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e0e0e0; }
        """)

        self.keep_cloud_btn = QPushButton("Keep Cloud (Download)")
        self.keep_cloud_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_cloud_btn.clicked.connect(self._on_keep_cloud)
        self.keep_cloud_btn.setStyleSheet("""
            QPushButton {
                background-color: #B94632;
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #a83e25; }
        """)

        btn_layout.addWidget(self.keep_local_btn)
        btn_layout.addWidget(self.keep_cloud_btn)
        layout.addLayout(btn_layout)

    def _create_info_card(self, title, timestamp, is_newer=False):
        card = QFrame()
        card.setObjectName("infoCard")
        border_color = "#B94632" if is_newer else "#ccc"
        card.setStyleSheet(f"""
            QFrame#infoCard {{
                background-color: white;
                border: 2px solid {border_color};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(t_lbl)

        time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp > 0 else "Never"
        l_lbl = QLabel(f"Last modified:\n{time_str}")
        l_lbl.setStyleSheet("font-size: 12px; color: #666;")
        l_lbl.setWordWrap(True)
        layout.addWidget(l_lbl)

        if is_newer:
            newer_badge = QLabel("NEWER")
            newer_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            newer_badge.setStyleSheet("""
                background-color: #B94632;
                color: white;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 5px;
            """)
            layout.addWidget(newer_badge)
        else:
            layout.addStretch()

        return card

    def _on_keep_local(self):
        self.result_choice = 'local'
        self.accept()

    def _on_keep_cloud(self):
        self.result_choice = 'cloud'
        self.accept()

def show_sync_conflict_dialog(parent=None):
    dialog = SyncConflictDialog(parent)
    if dialog.exec():
        return dialog.result_choice
    return None
