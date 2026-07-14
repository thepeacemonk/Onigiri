# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageSyncMixin:
    def _open_donate_link(self):
        from ..donations_dialog import DonationsDialog
        dialog = DonationsDialog(self)
        dialog.exec()

    def _open_bugs_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/thepeacemonk/Onigiri"))

    def create_sync_page(self):
        page_container, layout = self._create_scrollable_page()

        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        item_bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        text_col = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        muted_col = palette.get("--fg-subtle", "#d1d5db" if theme_manager.night_mode else "#4b5563")
        border_col = palette.get("--border", "#454545" if theme_manager.night_mode else "#e5e7eb")
        accent = self.accent_color

        layout.setContentsMargins(0, 0, 8, 24)

        card_style = f"""
            QFrame#syncHeroCard, QFrame#syncInfoCard, QFrame#syncStateCard {{
                background-color: {card_bg};
                border: 1px solid {border_col};
                border-radius: 16px;
            }}
            QFrame#syncInfoCard {{
                background-color: {item_bg};
                border-radius: 12px;
            }}
        """

        card = QFrame()
        card.setObjectName("syncHeroCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card.setStyleSheet(card_style)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(20, 18, 20, 20)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)

        mark = SyncHeaderIcon(
            system_icon_path("sync.svg"),
            accent,
            item_bg,
            border_col,
            self._settings_icon_color(),
        )
        mark.setActive(self.ankiweb_sync_toggle.isChecked())
        self.ankiweb_sync_toggle.toggled.connect(mark.setActive)

        title_stack = QWidget()
        title_stack.setStyleSheet("background: transparent;")
        title_stack_layout = QVBoxLayout(title_stack)
        title_stack_layout.setContentsMargins(0, 0, 0, 0)
        title_stack_layout.setSpacing(3)

        title_label = QLabel(tr("sync_title"))
        title_label.setStyleSheet(f"font-size: 18px; font-weight: 400; color: {text_col}; background: transparent;")
        title_stack_layout.addWidget(title_label)

        made_by = tr("sync_made_by")
        footer_label = QLabel()
        footer_label.setTextFormat(Qt.TextFormat.RichText)
        footer_label.setOpenExternalLinks(True)
        h0tp_link = f'<a href="https://github.com/h0tp-ftw" style="color:{accent};">h0tp</a>'
        footer_label.setText(made_by.replace("h0tp", h0tp_link))
        footer_label.setStyleSheet(f"font-size: 11px; color: {muted_col}; background: transparent;")
        title_stack_layout.addWidget(footer_label)

        header_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(title_stack, 1)
        header_layout.addWidget(self.ankiweb_sync_toggle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        card_layout.addWidget(header)

        state_card = QFrame()
        state_card.setObjectName("syncStateCard")
        state_card.setStyleSheet(card_style)
        state_layout = QVBoxLayout(state_card)
        state_layout.setContentsMargins(14, 12, 14, 12)
        state_layout.setSpacing(6)

        state_title = QLabel(tr("sync_bullet_1"))
        state_title.setWordWrap(True)
        state_title.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {text_col}; background: transparent;")
        state_layout.addWidget(state_title)

        state_desc = QLabel(tr("sync_bullet_4"))
        state_desc.setWordWrap(True)
        state_desc.setStyleSheet(f"font-size: 12px; color: {muted_col}; background: transparent;")
        state_layout.addWidget(state_desc)
        card_layout.addWidget(state_card)

        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_layout = QGridLayout(content)
        content_layout.setHorizontalSpacing(10)
        content_layout.setVerticalSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        for text in [tr("sync_bullet_2"), tr("sync_bullet_3")]:
            index = content_layout.count()
            item_box = QFrame()
            item_box.setObjectName("syncInfoCard")
            item_box.setStyleSheet(card_style)
            box_layout = QHBoxLayout(item_box)
            box_layout.setContentsMargins(14, 12, 14, 12)

            item_label = QLabel(text)
            item_label.setWordWrap(True)
            item_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item_label.setStyleSheet(f"font-size: 12px; color: {text_col}; background: transparent;")
            box_layout.addWidget(item_label)
            content_layout.addWidget(item_box, index // 2, index % 2)


        card_layout.addWidget(content)
        layout.addWidget(card)
        layout.addStretch()
        return page_container

    def _sync_action_buttons_mode_control(self):
        group = getattr(self, "action_buttons_mode_group", None)
        if group is None:
            return
        mode = self._sidebar_actions_mode()
        for button in group.buttons():
            if button.property("sidebar_actions_mode") == mode and not button.isChecked():
                with QSignalBlocker(group):
                    button.setChecked(True)

