"""Native version controls also usable when a historical Settings UI is loaded."""
import shutil
import subprocess
import sys
from pathlib import Path
from aqt import mw
from aqt.qt import (QButtonGroup, QCheckBox, QColor, QDialog, QEasingCurve, QFont, QFontDatabase, QFrame,
                    QHBoxLayout, QIcon, QLabel, QMessageBox, QPainter, QPalette,
                    QPen, QPixmap, QProgressBar, QPushButton, QRadioButton, QRectF, Qt,
                    QStyle, QVariantAnimation, QVBoxLayout, pyqtSignal)
from . import capture_context, service
from .strings import translate
from .palettes import palette_for

_loaded_fonts = set()


def _blend_colors(start, end, amount):
    start, end = QColor(start), QColor(end)
    return QColor(*(round(a * (1 - amount) + b * amount) for a, b in
                    zip((start.red(), start.green(), start.blue()),
                        (end.red(), end.green(), end.blue()))))


def _allows_motion(widget):
    if sys.platform == "darwin":
        try:
            preference = subprocess.run(
                ["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                capture_output=True, text=True, timeout=0.4,
            )
            if preference.stdout.strip().lower() in {"1", "true", "yes"}:
                return False
        except (OSError, subprocess.TimeoutExpired):
            pass
    return bool(widget.style().styleHint(QStyle.StyleHint.SH_Widget_Animate))


class UpdateSwitch(QCheckBox):
    """Use checkbox keyboard/accessibility semantics with a quiet toggle face."""
    def __init__(self, text, colors, parent):
        super().__init__(text, parent)
        self.colors = colors
        self._position = 0.0
        self._allow_motion = _allows_motion(self)
        self._motion = QVariantAnimation(self)
        self._motion.setDuration(180)
        self._motion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._motion.valueChanged.connect(self._move_knob)
        self.setFixedSize(46, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text)
        self.toggled.connect(self._animate_toggle)

    def _move_knob(self, value):
        self._position = float(value)
        self.update()

    def _animate_toggle(self, checked):
        self._motion.stop()
        target = float(checked)
        if not self.isVisible() or not self._allow_motion:
            self._move_knob(target)
            return
        self._motion.setStartValue(self._position)
        self._motion.setEndValue(target)
        self._motion.start()

    def setChecked(self, checked):
        super().setChecked(checked)
        # Programmatic changes after a version switch block persistence signals,
        # but the painted state must still follow the checkbox.
        if self.signalsBlocked():
            self._animate_toggle(self.isChecked())

    def hideEvent(self, event):
        self._motion.stop()
        self._move_knob(float(self.isChecked()))
        super().hideEvent(event)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        color = _blend_colors(self.colors["switch_off"], self.colors["accent"], self._position)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(3, 4, 40, 22), 11, 11)
        painter.setBrush(QColor(self.colors["knob"]))
        # Track ends at x=43: an 18px knob at x=23 leaves the same 2px
        # inset as the unchecked position, including on Retina displays.
        painter.drawEllipse(QRectF(5 + 18 * self._position, 6, 18, 18))
        if self.hasFocus():
            painter.setOpacity(1)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self.colors["accent"]), 1.5))
            painter.drawRoundedRect(QRectF(0.75, 1.75, 44.5, 26.5), 13, 13)


class ReleaseOption(QRadioButton):
    def __init__(self, version, latest, colors, parent):
        self.version = version
        self.latest = latest
        text = version + (" (" + latest + ")" if latest else "")
        super().__init__(text, parent)
        self.colors = colors
        self._keyboard_focus = False
        self.setAccessibleName(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(54)
        self.setMinimumWidth(144)
        self.toggled.connect(lambda _checked: self.update())

    def hitButton(self, position):
        return self.rect().contains(position)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def focusInEvent(self, event):
        self._keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        self._keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def mousePressEvent(self, event):
        self._keyboard_focus = False
        super().mousePressEvent(event)
        self.update()

    def keyPressEvent(self, event):
        step = {Qt.Key.Key_Right: 1, Qt.Key.Key_Down: 1,
                Qt.Key.Key_Left: -1, Qt.Key.Key_Up: -1}.get(event.key())
        if step is not None:
            selector = self.parentWidget()
            index = (selector._group.id(self) + step) % selector.count()
            selector.setCurrentIndex(index)
            selector.options[index].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.colors
        selected = self.isChecked()
        if not self.isEnabled():
            painter.setOpacity(0.5)
        fill = QColor(c["hover"] if self.underMouse() else c["field"])
        if selected:
            # A wash of the active palette keeps the choice visible without
            # turning the segment into another primary action.
            base, accent = QColor(c["field"]), QColor(c["accent"])
            amount = 0.18 if base.lightness() < 128 else 0.13
            fill = QColor(*(round(a * (1 - amount) + b * amount) for a, b in
                            zip((base.red(), base.green(), base.blue()),
                                (accent.red(), accent.green(), accent.blue()))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(bounds, 9, 9)
        painter.setPen(QColor(c["ink"]))
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Medium if selected else QFont.Weight.Normal)
        painter.setFont(font)
        # Keep (latest) on the same line at normal widths. Longer localized
        # labels wrap below the name rather than widening the entire dialog.
        text = self.text()
        if painter.fontMetrics().horizontalAdvance(text) <= self.width() - 14:
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.drawText(bounds.adjusted(6, 6, -6, -22), Qt.AlignmentFlag.AlignCenter, self.version)
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(bounds.adjusted(6, 28, -6, -3), Qt.AlignmentFlag.AlignCenter, "(" + self.latest + ")")
        if self.hasFocus() and self._keyboard_focus:
            painter.setOpacity(1)
            # Keyboard navigation retains a visible cue without outlining the
            # selected segment or showing a focus ring after a mouse click.
            painter.setPen(QPen(QColor(c["accent"]), 1.5))
            painter.drawLine(self.width() // 2 - 12, self.height() - 6,
                             self.width() // 2 + 12, self.height() - 6)


class VersionChoice(QFrame):
    """Three visible radio choices, avoiding platform-dependent popup styling."""
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, colors, latest, parent):
        super().__init__(parent)
        self._versions = list(service.RELEASES)
        self._group = QButtonGroup(self)
        self.options = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        for index, version in enumerate(self._versions):
            option = ReleaseOption(service.release_label(version), latest if index == 0 else "", colors, self)
            self._group.addButton(option, index)
            self.options.append(option)
            layout.addWidget(option, 1)
        self.options[0].setChecked(True)
        self._group.idToggled.connect(self._selection_changed)
        self.setFocusProxy(self.options[0])

    def _selection_changed(self, index, checked):
        if checked:
            self.setFocusProxy(self.options[index])
            self.currentIndexChanged.emit(index)

    def count(self):
        return len(self.options)

    def itemText(self, index):
        return self.options[index].text()

    def currentData(self):
        return self._versions[self._group.checkedId()]

    def findData(self, value):
        return self._versions.index(value) if value in self._versions else -1

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.options):
            self.options[index].setChecked(True)

    def set_colors(self, colors):
        for option in self.options:
            option.colors = colors
            option.update()


class VersionDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent or mw)
        self.root = root
        self.busy = False
        self._update_error = False
        self._dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        self._preview_version = service.installed_release(root) or "2.0-Bento"
        self.copy = lambda key: translate(key, self.root)
        self.setObjectName("onigiriVersionDialog")
        self.setWindowTitle("Onigiri · " + self.copy("title"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        logo = Path(__file__).parent / "assets/logo.svg"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))
        self._apply_style()
        self.setMinimumWidth(520)
        self.resize(600, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setSpacing(14)
        if logo.exists():
            mark = QLabel(self)
            mark.setObjectName("onigiriVersionLogo")
            mark.setPixmap(QPixmap(str(logo)).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            mark.setFixedSize(48, 48)
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(mark)
        headings = QVBoxLayout()
        headings.setSpacing(4)
        title = self._label("title")
        title.setObjectName("onigiriVersionHeading")
        title.setStyleSheet("")
        headings.addWidget(title)
        self.installed = QLabel(self.copy("installed").format(version=service.installed_version(root)))
        self.installed.setObjectName("onigiriInstalledVersion")
        headings.addWidget(self.installed)
        header.addLayout(headings, 1)
        layout.addLayout(header)
        layout.addSpacing(20)
        layout.addWidget(self._label("intro"))
        layout.addSpacing(24)
        choice_label = self._label("choose")
        choice_label.setObjectName("onigiriVersionFieldLabel")
        choice_label.setStyleSheet("")
        layout.addWidget(choice_label)
        layout.addSpacing(8)
        self.versions = VersionChoice(self.colors, self.copy("latest"), self)
        self.versions.setObjectName("onigiriVersionChoice")
        self.versions.setCurrentIndex(self.versions.findData(self._preview_version))
        self.versions.currentIndexChanged.connect(self._preview_selection)
        self.versions.setAccessibleName(self.copy("choose"))
        self.versions.setMinimumHeight(64)
        choice_label.setBuddy(self.versions)
        layout.addWidget(self.versions)
        layout.addSpacing(24)
        divider = QFrame(self)
        divider.setObjectName("onigiriVersionDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(20)
        update_row = QHBoxLayout()
        update_row.setSpacing(12)
        update_label = self._label("automatic")
        update_label.setObjectName("onigiriVersionFieldLabel")
        update_label.setStyleSheet("")
        update_row.addWidget(update_label, 1)
        self.automatic = UpdateSwitch(self.copy("automatic"), self.colors, self)
        self.automatic.setObjectName("onigiriAutomaticUpdates")
        try:
            self.automatic.setChecked(service.updates_enabled(root))
        except (OSError, ValueError):
            # The explicit confirmation below will report an unknown saved
            # state instead of claiming that updates were successfully paused.
            self.automatic.setChecked(False)
        self.automatic.toggled.connect(self._toggle_updates)
        update_label.setBuddy(self.automatic)
        update_row.addWidget(self.automatic)
        layout.addLayout(update_row)
        layout.addSpacing(6)
        self.update_state = QLabel(self)
        self.update_state.setObjectName("onigiriUpdateState")
        self.update_state.setWordWrap(True)
        layout.addWidget(self.update_state)
        layout.addSpacing(4)
        self.update_details = QLabel(self)
        self.update_details.setWordWrap(True)
        layout.addWidget(self.update_details)
        self.status = QLabel(self)
        self.status.setObjectName("onigiriVersionStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.hide()
        layout.addSpacing(18)
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName(self.copy("preparing"))
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel = QPushButton(self.copy("cancel"))
        self.cancel.setObjectName("onigiriCancelVersionSwitch")
        self.cancel.clicked.connect(self._cancel)
        layout.addWidget(self.cancel, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(20)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()
        self.close_button = QPushButton(self.copy("close"))
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        self.switch_button = QPushButton(self.copy("switch"))
        self.switch_button.setObjectName("onigiriSwitchVersion")
        self.switch_button.clicked.connect(self._switch)
        self.switch_button.setDefault(True)
        buttons.addWidget(self.switch_button)
        self.restart = QPushButton(self.copy("restart"))
        self.restart.setObjectName("onigiriApplyVersionSwitch")
        self.restart.clicked.connect(self._close_anki)
        buttons.addWidget(self.restart)
        layout.addLayout(buttons)
        self._refresh_pending()

    def adjustSize(self):
        super().adjustSize()
        layout = self.layout()
        if layout is not None:
            # QWidget.adjustSize caps itself against the screen. At increased
            # UI scaling that can squeeze wrapped copy below its needed height.
            # Keep the actual width, then honor the layout's height for it.
            height = layout.totalHeightForWidth(self.width())
            if height > 0:
                self.setMinimumHeight(height)
                self.resize(self.width(), height)

    def _apply_style(self):
        for filename in ("Poppins-Regular.ttf", "Poppins-Medium.ttf"):
            font = Path(__file__).parent / "assets" / filename
            if font.exists() and str(font) not in _loaded_fonts:
                QFontDatabase.addApplicationFont(str(font))
                _loaded_fonts.add(str(font))
        self.colors = palette_for(self._preview_version, self._dark)
        c = self.colors
        self.setStyleSheet(f"""
            QDialog#onigiriVersionDialog {{ background: {c['background']}; }}
            QWidget {{ font-family: 'Poppins'; font-size: 13px; color: {c['ink']}; }}
            QLabel {{ background: transparent; color: {c['muted']}; }}
            QLabel#onigiriVersionHeading {{ font-size: 25px; font-weight: 500; color: {c['ink']}; }}
            QLabel#onigiriInstalledVersion {{ font-size: 12px; color: {c['muted']}; }}
            QLabel#onigiriVersionFieldLabel {{ font-size: 14px; font-weight: 500; color: {c['ink']}; }}
            QLabel#onigiriUpdateState {{ font-weight: 500; color: {c['ink']}; }}
            QLabel#onigiriVersionStatus {{ padding: 12px; background: {c['hover']}; border-radius: 10px; }}
            QFrame#onigiriVersionDivider {{ background: {c['line']}; border: none; }}
            QFrame#onigiriVersionChoice {{ background: {c['field']}; border: 1px solid {c['line']}; border-radius: 12px; }}
            QRadioButton {{ background: transparent; border: none; }}
            QPushButton {{ background: {c['field']}; border: 1px solid {c['line']}; border-radius: 10px;
                           min-height: 40px; padding: 0 18px; font-weight: 500; }}
            QPushButton:hover {{ background: {c['hover']}; }}
            QPushButton:focus {{ border: 2px solid {c['accent']}; padding: 0 17px; }}
            QPushButton#onigiriSwitchVersion, QPushButton#onigiriApplyVersionSwitch {{
                background: {c['accent']}; color: {c['on_accent']}; border: 1px solid {c['accent']}; }}
            QPushButton#onigiriSwitchVersion:hover, QPushButton#onigiriApplyVersionSwitch:hover {{
                background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
            QPushButton#onigiriSwitchVersion:focus, QPushButton#onigiriApplyVersionSwitch:focus {{
                border: 2px solid {c['on_accent']}; padding: 0 17px; }}
            QPushButton#onigiriSwitchVersion:disabled {{ background: {c['line']}; color: {c['muted']}; border-color: {c['line']}; }}
            QPushButton#onigiriCancelVersionSwitch {{ background: transparent; border: none; color: {c['muted']};
                padding: 0; min-height: 32px; font-weight: 400; text-align: left; }}
            QPushButton#onigiriCancelVersionSwitch:hover {{ color: {c['ink']}; }}
            QPushButton#onigiriCancelVersionSwitch:focus {{ color: {c['accent']}; }}
            QProgressBar {{ border: none; border-radius: 3px; background: {c['line']}; height: 4px; max-height: 4px; }}
            QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
        """)

    def _preview_selection(self, _index):
        self._preview_version = self.versions.currentData()
        self._apply_style()
        self.versions.set_colors(self.colors)
        self.automatic.colors = self.colors
        self.automatic.update()

    def _label(self, key):
        label = QLabel(self.copy(key), self)
        label.setWordWrap(True)
        return label

    def _set_status(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.adjustSize()

    def _error(self, exc):
        self._set_status(self.copy("failed").format(error=str(exc)))

    def _refresh_pending(self):
        pending = service.pending_switch(self.root)
        self.cancel.setVisible(bool(pending))
        self.restart.setVisible(bool(pending))
        self.switch_button.setEnabled(not pending and not self.busy)
        self.switch_button.setVisible(not pending)
        self.versions.setEnabled(not pending and not self.busy)
        self.automatic.setEnabled(not pending and not self.busy)
        if pending:
            index = self.versions.findData(pending["target"])
            if index >= 0:
                self.versions.setCurrentIndex(index)
            if pending.get("error"):
                self._error(pending["error"])
            else:
                self._set_status(self.copy("ready").format(
                    version=pending.get("target_version") or service.installed_version(pending["stage"])))
        self._refresh_update_state()
        self.adjustSize()

    def _refresh_update_state(self):
        # Confirm the saved preference, rather than deriving this promise from
        # the switch's appearance or from a write that may have failed.
        try:
            enabled = service.updates_enabled(self.root)
        except Exception:
            self.update_state.setText(self.copy("updates_unknown"))
            self.update_details.setText(self.copy("updates_unknown_detail"))
            return
        key = "updates_on" if enabled else "updates_off"
        self.update_state.setText(self.copy(key))
        self.update_details.setText(self.copy(key + "_detail"))

    def _toggle_updates(self, enabled):
        try:
            service.set_updates_enabled(self.root, enabled)
            if self._update_error:
                self._set_status("")
                self._update_error = False
        except Exception as exc:
            self._update_error = True
            self.automatic.blockSignals(True)
            self.automatic.setChecked(not enabled)
            self.automatic.blockSignals(False)
            self._set_status(self.copy("updates_failed").format(error=str(exc)))
        finally:
            self._refresh_update_state()
            self.adjustSize()

    def _cancel(self):
        try:
            service.cancel_switch(self.root)
            self._set_status(self.copy("cancelled"))
            self._refresh_pending()
        except Exception as exc:
            self._error(exc)

    def _close_anki(self):
        self.reject()
        mw.close()

    def _switch(self):
        target = self.versions.currentData()
        if self.busy or service.pending_switch(self.root):
            return
        try:
            context = capture_context()
        except Exception as exc:
            self._error(exc)
            return
        box = QMessageBox(self)
        box.setWindowTitle(self.windowTitle())
        label = self.versions.itemText(self.versions.findData(target))
        box.setText(self.copy("confirm").format(version=label))
        box.setInformativeText(self.copy("confirm_body"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self.busy = True
        self._set_status(self.copy("preparing"))
        self.progress.show()
        self.close_button.setEnabled(False)
        self._refresh_pending()
        source_collection = mw.col
        source_profile = mw.pm.name

        def done(future):
            stage = None
            try:
                stage = future.result()
                if mw.col is not source_collection or mw.pm.name != source_profile:
                    raise RuntimeError("The Anki profile changed; choose the version again")
                # Re-read the current snapshot after the download. Collection
                # exports fail closed; no empty replacement backup is allowed.
                context = capture_context()
                service.queue_switch(self.root, target, stage, context)
                stage = None
                self.automatic.blockSignals(True)
                self.automatic.setChecked(False)
                self.automatic.blockSignals(False)
            except Exception as exc:
                self._error(exc)
            finally:
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)
                self.busy = False
                self.progress.hide()
                self.close_button.setEnabled(True)
                self._refresh_pending()

        try:
            mw.taskman.run_in_background(lambda: service.prepare_release(self.root, target), done)
        except Exception as exc:
            self.busy = False
            self.progress.hide()
            self.close_button.setEnabled(True)
            self._refresh_pending()
            self._error(exc)

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)
