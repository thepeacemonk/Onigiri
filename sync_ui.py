from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    Qt, QFrame, QSizePolicy, QGraphicsDropShadowEffect, QColor
)
from datetime import datetime
from .sync import onigiri_sync
from .translations import tr

from aqt.theme import theme_manager
from aqt import mw

class SyncConflictDialog(QDialog):
    """
    Dialog shown when there is a difference between local and cloud data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("sync_conflict_title"))
        self.setFixedWidth(500)
        self.result_choice = None # 'local' or 'cloud'

        self._setup_ui()

    def _setup_ui(self):
        is_dark = theme_manager.night_mode
        bg_color = "#2c2c2c" if is_dark else "#f5f5f5"
        text_color = "#e0e0e0" if is_dark else "#333"
        desc_color = "#aaa" if is_dark else "#555"
        btn_local_bg = "#3c3c3c" if is_dark else "#f0f0f0"
        btn_local_hover = "#4c4c4c" if is_dark else "#e0e0e0"
        
        self.setStyleSheet(f"background-color: {bg_color}; color: {text_color};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)

        # Header
        header = QLabel(tr("sync_conflict_heading"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #E74C3C; background: transparent;")
        layout.addWidget(header)

        desc = QLabel(tr("sync_conflict_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 13px; color: {desc_color}; background: transparent;")
        layout.addWidget(desc)

        # Comparison Area
        comp_layout = QHBoxLayout()
        comp_layout.setSpacing(15)

        local_time = onigiri_sync.get_local_mtime()
        cloud_time = onigiri_sync.get_cloud_mtime()

        self.local_card = self._create_info_card(
            tr("sync_local_device"), 
            local_time, 
            is_newer=(local_time > cloud_time)
        )
        self.cloud_card = self._create_info_card(
            tr("sync_ankiweb_cloud"), 
            cloud_time, 
            is_newer=(cloud_time > local_time)
        )

        comp_layout.addWidget(self.local_card)
        comp_layout.addWidget(self.cloud_card)
        layout.addLayout(comp_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.keep_local_btn = QPushButton(tr("sync_keep_local"))
        self.keep_local_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_local_btn.clicked.connect(self._on_keep_local)
        self.keep_local_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_local_bg};
                color: {text_color};
                border-radius: 10px;
                padding: 12px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{ background-color: {btn_local_hover}; }}
        """)

        self.keep_cloud_btn = QPushButton(tr("sync_keep_cloud"))
        self.keep_cloud_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keep_cloud_btn.clicked.connect(self._on_keep_cloud)
        self.keep_cloud_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border-radius: 10px;
                padding: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #C0392B; }
        """)

        btn_layout.addWidget(self.keep_local_btn)
        btn_layout.addWidget(self.keep_cloud_btn)
        layout.addLayout(btn_layout)

    def _create_info_card(self, title, timestamp, is_newer=False):
        is_dark = theme_manager.night_mode
        card_bg = "#3c3c3c" if is_dark else "white"
        text_color = "#e0e0e0" if is_dark else "#333"
        sub_text_color = "#aaa" if is_dark else "#666"
        border_color = "#E74C3C" if is_newer else ("#555" if is_dark else "#ddd")
        
        card = QFrame()
        card.setObjectName("infoCard")
        card.setStyleSheet(f"""
            QFrame#infoCard {{
                background-color: {card_bg};
                border: 2px solid {border_color};
                border-radius: 14px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {text_color}; background: transparent;")
        layout.addWidget(t_lbl)

        time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp > 0 else tr("sync_never")
        l_lbl = QLabel(f'{tr("sync_last_modified")}\n{time_str}')
        l_lbl.setStyleSheet(f"font-size: 12px; color: {sub_text_color}; background: transparent;")
        l_lbl.setWordWrap(True)
        layout.addWidget(l_lbl)

        if is_newer:
            newer_badge = QLabel(tr("sync_newer_badge"))
            newer_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            newer_badge.setStyleSheet("""
                background-color: #E74C3C;
                color: white;
                font-size: 10px;
                font-weight: bold;
                border-radius: 5px;
                padding: 4px 8px;
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
