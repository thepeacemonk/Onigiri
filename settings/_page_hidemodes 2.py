# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageHidemodesMixin:
    def _retention_stars_hidden(self):
        """Single source of truth for whether the Retention card shows stars.

        The Stats Widgets section owns the switch now (phrased positively, as
        "Show retention stars"); `hideRetentionStars` remains the stored key so
        older configs and the renderer keep working unchanged.
        """
        toggle = getattr(self, "stats_widgets_show_retention_stars_toggle", None)
        if toggle is not None:
            return not toggle.isChecked()
        return bool(self.current_config.get("hideRetentionStars", False))

    def _on_hide_retention_stars_changed(self, checked=False):
        self.current_config["hideRetentionStars"] = bool(checked)
        self._update_box_effect_preview()
        try:
            if getattr(mw, "deckBrowser", None) and getattr(mw.deckBrowser, "web", None):
                display = "none" if checked else ""
                mw.deckBrowser.web.eval(
                    "document.querySelectorAll('.retention-card').forEach(card => {"
                    "card.classList.toggle('retention-stars-hidden', %s);"
                    "card.querySelectorAll('.star-rating').forEach(el => { el.style.display = %s; });"
                    "});"
                    % (json.dumps(bool(checked)), json.dumps(display))
                )
        except Exception:
            pass

    def _create_hide_mode_card(self, title, toggle_widget, items):
        """Wrapper method for backwards compatibility - creates AdaptiveModeCard."""
        return self.AdaptiveModeCard(title, toggle_widget, items, self.addon_path, self)

    def create_hide_modes_page(self):
        page, layout = self._create_scrollable_page()
        layout.setContentsMargins(0, 12, 12, 24)

        description = QLabel(tr("modes_description"))
        description.setObjectName("sectionDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        modes_list = QVBoxLayout()
        modes_list.setContentsMargins(0, 8, 0, 0)
        modes_list.setSpacing(10)

        cards = [
            self._create_mode_option_card(
                tr("mode_focus"),
                tr("hide_anki_bars"),
                self.hide_native_header_checkbox,
                [tr("replaces_top_bar")],
                "mode-focus-eye.svg"
            ),
            self._create_mode_option_card(
                tr("mode_flow"),
                tr("everything_in_focus"),
                self.flow_mode_checkbox,
                [tr("hides_onigiri_top_bar"), tr("restart_anki_note")],
                "mode-flow-wind.svg"
            ),
            self._create_mode_option_card(
                tr("mode_zen"),
                tr("everything_in_flow"),
                self.max_hide_checkbox,
                [tr("hides_reviewer_bottom_bar"), tr("button_only_navigation"), tr("restart_anki_note")],
                "mode-zen-moon-regular.svg"
            ),
            self._create_mode_option_card(
                tr("mode_full"),
                tr("hide_top_menu_bar"),
                self.full_hide_mode_checkbox,
                [tr("menu_bar_items_example"), tr("windows_linux_only"), tr("restart_anki_note")],
                "mode-full-window-maximize-regular.svg"
            ),
        ]

        from .. import patcher
        if patcher.is_synapsepro_identified():
            cards.append(self._create_mode_option_card(
                tr("synapsepro_sidebar"),
                tr("hide_synapsepro_sidebar"),
                self.hide_synapsepro_sidebar_checkbox,
                [tr("synapsepro_sidebar_desc")],
                "sidebar_left_hidden.svg"
            ))

        for card in cards:
            modes_list.addWidget(card)

        layout.addLayout(modes_list)
        layout.addStretch()
        
        return page

    def _reflow_shape_icons(self, width=0):
        if not hasattr(self, 'shape_buttons') or not self.shape_buttons:
            return

        if not hasattr(self, "shape_scroll_content"):
            return

        # This can run from a QTimer.singleShot(0, ...) callback queued by a
        # resize/eventFilter; if the user has since navigated away from this
        # settings page, self and its child widgets may already be destroyed.
        # hasattr() only checks the Python attribute exists, not that the
        # underlying C++ object is still alive, so guard explicitly.
        if sip is not None and sip.isdeleted(self):
            return
        try:
            button_size = getattr(self, "shape_button_size", 48)
            spacing = getattr(self, "shape_grid_spacing", 10)
            if not width and hasattr(self, "shape_selector_widget"):
                width = self.shape_selector_widget.width()
            if not width and hasattr(self, "shape_scroll_area"):
                width = self.shape_scroll_area.viewport().width()

            # The settings content can be clipped by its parent even while Qt reports a
            # wider child width. Keep a full tile of right-side breathing room so the
            # last visible column wraps before it reaches that clipped edge.
            right_gutter = button_size + spacing + 24
            available_width = max(button_size, (width or 640) - right_gutter)
            columns = max(1, int((available_width + spacing) // (button_size + spacing)))

            for i, button in enumerate(self.shape_buttons):
                if button is not None:
                    row = i // columns
                    col = i % columns
                    button.setParent(self.shape_scroll_content)
                    button.move(col * (button_size + spacing), row * (button_size + spacing))
                    button.show()

            rows = (len(self.shape_buttons) + columns - 1) // columns
            grid_height = rows * button_size + max(0, rows - 1) * spacing
            content_width = columns * button_size + max(0, columns - 1) * spacing
            self.shape_scroll_content.setMinimumSize(1, grid_height)
            self.shape_scroll_content.resize(content_width, grid_height)

            if hasattr(self, "shape_scroll_area"):
                self.shape_scroll_area.setFixedHeight(max(96, grid_height + 4))
                self.shape_scroll_area.updateGeometry()
        except RuntimeError:
            # A widget referenced above was deleted between the timer firing
            # and this callback running; nothing to reflow anymore.
            pass

    def _on_hide_all_stats_toggled(self, checked):
        self.hide_studied_stat_checkbox.setChecked(checked)
        self.hide_time_stat_checkbox.setChecked(checked)
        self.hide_pace_stat_checkbox.setChecked(checked)
        self.hide_retention_stat_checkbox.setChecked(checked)

    def _on_hide_toggled(self, checked):
        """Handle Focus mode toggle - Focus is the child/base level"""
        if not checked:
            # When Focus is turned OFF, turn OFF both Flow and Zen
            # Turn OFF Flow
            self.flow_mode_checkbox.blockSignals(True)
            if self.flow_mode_checkbox.isChecked():
                self.flow_mode_checkbox.setChecked(False)
                self.flow_mode_checkbox._start_animation(False)
            self.flow_mode_checkbox.blockSignals(False)
            
            # Turn OFF Zen
            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)

    def _on_max_hide_toggled(self, checked):
        """Handle Zen mode toggle - Zen is the parent/highest level"""
        if checked:
            # When Zen is turned ON, turn ON both Flow and Focus
            # Turn ON Flow
            self.flow_mode_checkbox.blockSignals(True)
            if not self.flow_mode_checkbox.isChecked():
                self.flow_mode_checkbox.setChecked(True)
                self.flow_mode_checkbox._start_animation(True)
            self.flow_mode_checkbox.blockSignals(False)
            
            # Turn ON Focus
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)

    def _on_flow_toggled(self, checked):
        """Handle Flow mode toggle - Flow is the middle level"""
        if checked:
            # When Flow is turned ON, turn ON Focus
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)
            # Zen remains as-is (no action needed)
        else:
            # When Flow is turned OFF, turn OFF Zen (but Focus stays as-is)
            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)

    def _on_full_hide_toggled(self, checked):
        """Handle Full Hide Mode toggle"""
        if checked:
            show_settings_toast(self, tr("full_hide_restart_toast", "Restart Anki for Full Hide Mode to take effect"))

    def _save_hide_modes_settings(self):
        self.current_config.update({
            "hideNativeHeaderAndBottomBar": self.hide_native_header_checkbox.isChecked(),
            # "proHide" removed from UI, but key might remain in config. No need to update it here.
            "maxHide": self.max_hide_checkbox.isChecked(),
            "flowMode": self.flow_mode_checkbox.isChecked(),
            "fullHideMode": self.full_hide_mode_checkbox.isChecked(),
            "hideSynapseProSidebar": self.hide_synapsepro_sidebar_checkbox.isChecked(),
        })
        from .. import patcher
        patcher.apply_synapsepro_sidebar_visibility(self.current_config)

