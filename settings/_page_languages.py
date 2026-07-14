# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageLanguagesMixin:
    def _style_language_selector(self, selector, selected, accent=None):
        accent = accent or getattr(self, "accent_color", "#00A982")
        muted_border = QColor(accent)
        muted_border.setAlpha(150 if theme_manager.night_mode else 115)
        border = accent if selected else muted_border
        background = accent if selected else "transparent"

        if hasattr(selector, "setColors"):
            selector.setColors(accent, border)
            return

        border = accent if selected else QColor(muted_border).name()

        selector.setStyleSheet(f"""
            /* onigiri-rounded-button-fix */
            QPushButton#languageSelector {{
                background-color: {background};
                border: 2px solid {border};
                border-radius: 11px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                padding: 0;
                margin: 0;
            }}
            QPushButton#languageSelector:hover,
            QPushButton#languageSelector:pressed,
            QPushButton#languageSelector:checked {{
                border-color: {accent};
                border-radius: 11px;
            }}
        """)

    def _create_language_option_row(self, lang_name, flag, is_selected, button_group):
        row = LanguageOptionRow()
        row.setObjectName("languageOptionRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        palette = self._settings_palette()
        row_bg = palette.get("--canvas-inset", "#ffffff")
        row_hover = palette.get("--hover-bg", "#e9e9e9")
        row_border = palette.get("--border", "#dcdde1")
        row.setColors(row_bg, row_hover, row_border)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(12)

        selector_color = self._language_selector_color(lang_name)
        selector = LanguageSelectorButton()
        selector.setObjectName("languageSelector")
        selector.setAccessibleName(lang_name)
        selector.setToolTip(lang_name)
        button_group.addButton(selector)
        selector.setChecked(is_selected)
        selector.toggled.connect(
            lambda checked, name=lang_name: self._on_language_option_selected(name) if checked else None
        )
        selector.toggled.connect(
            lambda checked, button=selector, color=selector_color: self._style_language_selector(button, checked, color)
        )
        self._style_language_selector(selector, is_selected, selector_color)

        flag_label = QLabel(flag)
        flag_label.setFixedWidth(24)
        flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flag_label.setStyleSheet("font-size: 18px; background: transparent; border: none;")

        name_label = QLabel(lang_name)
        name_label.setObjectName("settingRowTitle")
        name_label.setWordWrap(True)

        layout.addWidget(selector)
        layout.addWidget(flag_label)
        layout.addWidget(name_label, 1)

        def _click_row(event, button=selector):
            if event.button() == Qt.MouseButton.LeftButton:
                button.setChecked(True)

        row.mousePressEvent = _click_row
        flag_label.mousePressEvent = _click_row
        name_label.mousePressEvent = _click_row

        return row

    def create_languages_page(self):
        page, layout = self._create_scrollable_page()

        flags = {
            "English (Default)": "🇺🇸",
            "Português (Brasil)": "🇧🇷",
            "Español (España)": "🇪🇸",
            "简体中文": "🇨🇳",
            "日本語": "🇯🇵",
            "Français": "🇫🇷",
            "한국어": "🇰🇷"
        }
        
        current_lang = self.current_config.get("language", "English (Default)")
        self.language_buttons = {}
        self.language_button_group = QButtonGroup(self)
        self.language_button_group.setExclusive(True)

        description_label = QLabel(tr("language_description"))
        description_label.setObjectName("sectionDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        
        for lang_name in LANGUAGES:
            flag = flags.get(lang_name, "🌐")
            is_selected = (lang_name == current_lang)

            row = self._create_language_option_row(
                lang_name,
                flag,
                is_selected,
                self.language_button_group,
            )
            self.language_buttons[lang_name] = row
            layout.addWidget(row)
        layout.addStretch()

        return page

    def _on_language_option_selected(self, lang_name):
        # Keep the selected language pending until Save or dialog close.
        self.current_config["language"] = lang_name
        self.save_button.setEnabled(True)

    def _apply_language_setting(self, lang_name=None):
        lang_name = lang_name or self.current_config.get("language", "English (Default)")
        lang_code = LANGUAGES.get(lang_name, "en")
        if mw.pm.profile.get('onigiri_language') != lang_code:
            mw.pm.profile['onigiri_language'] = lang_code

    def _save_language_settings(self):
        self._apply_language_setting()

