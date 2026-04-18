from PyQt6.QtWidgets import QMessageBox, QWidget


class MainNavigator:
    def confirm_delete_session(self, parent: QWidget) -> bool:
        r = QMessageBox.question(
            parent,
            "セッション削除",
            "このセッションを削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return r == QMessageBox.StandardButton.Yes
