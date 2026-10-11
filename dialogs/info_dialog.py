"""Window positioning shared by the Donations and Credits dialogs."""

from aqt.qt import QApplication, QDialog, QTimer


class CenteredInfoDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_screen()
        # Recalculate once the native window frame has been laid out.
        QTimer.singleShot(0, self._center_on_screen)

    def _center_on_screen(self):
        if not self.isVisible():
            return
        parent = self.parentWidget()
        screen = (parent.screen() if parent is not None else self.screen())
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        available = screen.availableGeometry()
        self.move(
            available.x() + (available.width() - frame.width()) // 2,
            available.y() + (available.height() - frame.height()) // 2,
        )
