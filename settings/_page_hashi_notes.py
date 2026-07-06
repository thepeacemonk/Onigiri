# Hashi Notes settings page. Follows the PageStudyToolsMixin structure and
# reuses the shared study-tools UI helpers (segmented controls, section groups, row builders).
from ._common import *
from ._widgets import *
from ._layout_base import *


class PageHashiNotesMixin:
    def create_hashi_notes_page(self):
        page, layout = self._create_scrollable_page()

        prefs = self.current_config.setdefault(
            "hashi_notes",
            copy.deepcopy(DEFAULTS.get("hashi_notes", {})),
        )
        for key, value in DEFAULTS.get("hashi_notes", {}).items():
            prefs.setdefault(key, copy.deepcopy(value))

        intro = QLabel(
            "Hashi Notes are quick, temporary study notes. Take one from the Reviewer "
            "or the Onigiri menu; each note auto-deletes after its retention window."
        )
        intro.setObjectName("sectionDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Open button
        open_section = SectionGroup("", self, border=False)
        open_btn = QPushButton("Open Hashi Notes")
        open_btn.setObjectName("toolsOpenButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedHeight(40)
        try:
            self._decorate_button(open_btn, "hashi_notes.svg", 16)
        except Exception:
            pass
        open_btn.clicked.connect(self._open_hashi_notes)
        open_section.content_layout.addWidget(open_btn)
        layout.addWidget(open_section)

        options_section = SectionGroup(
            "Options",
            self,
            border=False,
            description="Defaults applied to new notes and the gallery.",
        )
        opt_layout = options_section.content_layout

        # Retention default
        self.hashi_retention_group = QButtonGroup(self)
        self.hashi_retention_group.setExclusive(True)
        retention_value = str(prefs.get("retention_default", 30))
        retention_segment = self._create_tools_segmented_control(
            [("7", "7 days"), ("30", "30 days"), ("0", "Never")],
            self.hashi_retention_group,
            retention_value,
            "hashi_retention",
            min_button_width=120,
        )
        opt_layout.addWidget(self._create_tools_control_row(
            "Default retention",
            "How long new notes are kept before they move to trash and are purged.",
            retention_segment,
        ))

        # Default sort
        self.hashi_sort_group = QButtonGroup(self)
        self.hashi_sort_group.setExclusive(True)
        sort_value = str(prefs.get("default_sort", "age"))
        sort_segment = self._create_tools_segmented_control(
            [("age", "Age"), ("tags", "Tags"), ("priority", "Priority"), ("title", "Title")],
            self.hashi_sort_group,
            sort_value,
            "hashi_sort",
            min_button_width=96,
        )
        opt_layout.addWidget(self._create_tools_control_row(
            "Default sort",
            "Initial ordering of notes in the gallery.",
            sort_segment,
        ))
        layout.addWidget(options_section)

        # Custom CSS
        css_section = SectionGroup(
            "Custom CSS",
            self,
            border=False,
            description="Injected into the note editor and gallery to extend their styling.",
        )
        self.hashi_custom_css_input = QPlainTextEdit(str(prefs.get("custom_css", "") or ""))
        self.hashi_custom_css_input.setObjectName("toolsPromptInput")
        self.hashi_custom_css_input.setPlaceholderText(".hl { background: #ffe08a; }")
        self.hashi_custom_css_input.setFixedHeight(120)
        css_section.content_layout.addWidget(self.hashi_custom_css_input)
        layout.addWidget(css_section)

        layout.addStretch()
        try:
            self._style_tools_page(page)
        except Exception:
            pass
        return page

    def _save_hashi_notes_settings(self):
        if not hasattr(self, "hashi_retention_group"):
            return
        prefs = self.current_config.setdefault("hashi_notes", {})
        retention_button = self.hashi_retention_group.checkedButton()
        sort_button = self.hashi_sort_group.checkedButton()
        try:
            prefs["retention_default"] = int(
                retention_button.property("hashi_retention") if retention_button else 30
            )
        except Exception:
            prefs["retention_default"] = 30
        prefs["default_sort"] = (
            sort_button.property("hashi_sort") if sort_button else "age"
        )
        prefs["custom_css"] = self.hashi_custom_css_input.toPlainText()

    def _open_hashi_notes(self):
        self._save_hashi_notes_settings()
        config.write_config(self.current_config)
        from .. import hashi_notes

        hashi_notes.open_hashi_gallery(self)
