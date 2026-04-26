class HideModesPageMixin:
    def create_hide_modes_page(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("Modes")
        title.setObjectName("hideModePageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if theme_manager.night_mode:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #e0e0e0; background-color: #2c2c2c; padding: 0 5px;")
        else:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #212121; background-color: #f3f3f3; padding: 0 5px;")
        layout.addWidget(title)

        description = QLabel(
            "Choose either Focus or Zen Mode to hide elements of the interface for a more immersive experience, "
            "you can also enable Gamification Mode to track achievements and level up, making it fun to study."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 12px; color: #666; margin-bottom: 8px; padding: 10px;")
        layout.addWidget(description)

        layout.addSpacing(20)

        # (Gamification Mode card removed and moved to Onigiri Games dialog)
        layout.addSpacing(20)

        # Create responsive container for mode cards
        cards_container = ResponsiveModeCardsContainer(self)

        # Define what each mode hides - simplified flat structure
        # Focus mode - Basic hiding
        focus_items = [
            ("", [
                "Hide Anki's native bars",
                "Replaces top bar for a modern one"
            ])
        ]

        # Flow mode - Includes everything from Focus + hides onigiri header
        flow_items = [
            ("", [
                "Everything in Focus",
                "Hides Onigiri's modern top bar",
                "Restart Anki when applying this mode"
            ])
        ]

        # Zen mode - Includes everything from Flow + even more
        zen_items = [
            ("", [
                "Everything in Flow",
                "Hides the bottom bar on Reviewer",
                "(Button only navigation)",
                "Restart Anki when applying this mode"
            ])
        ]

        # Full mode - Hides the top menu bar (File, Edit, View, Tools, Help)
        full_items = [
            ("", [
                "Hide the top menu bar",
                "(File, Edit, View, Tools, Help)",
                "Works on Windows and Linux only",
                "Restart Anki when applying this mode"
            ])
        ]

        # Create mode cards using AdaptiveModeCard
        card1 = self._create_hide_mode_card("Focus", self.hide_native_header_checkbox, focus_items)
        card4 = self._create_hide_mode_card("Flow", self.flow_mode_checkbox, flow_items)
        card3 = self._create_hide_mode_card("Zen", self.max_hide_checkbox, zen_items)
        card_full = self._create_hide_mode_card("Full", self.full_hide_mode_checkbox, full_items)

        # Add cards to responsive container
        cards_container.add_mode_card(card1)
        cards_container.add_mode_card(card4)
        cards_container.add_mode_card(card3)
        cards_container.add_mode_card(card_full)

        layout.addWidget(cards_container)

        layout.addStretch()



        return page



    def _save_hide_modes_settings(self):
        self.current_config.update({
            "hideNativeHeaderAndBottomBar": self.hide_native_header_checkbox.isChecked(),
            # "proHide" removed from UI, but key might remain in config. No need to update it here.
            "maxHide": self.max_hide_checkbox.isChecked(),
            "flowMode": self.flow_mode_checkbox.isChecked(),
            "fullHideMode": self.full_hide_mode_checkbox.isChecked(),
        })


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
        # When Focus is turned ON, Flow and Zen remain as-is (no action needed)


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
        # When Zen is turned OFF, Flow and Focus remain as-is (no action needed)


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
    # <<< END NEW CODE >>>


    def _on_full_hide_toggled(self, checked):
        """Handle Full Hide Mode toggle"""
        if checked:
            QMessageBox.information(
                self,
                "Restart Required",
                "Please restart Anki for the Full Hide Mode to take effect."
            )


