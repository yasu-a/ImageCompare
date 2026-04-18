from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget


class SessionToolbar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.add_button = QPushButton("+")
        self.add_button.setToolTip("新規セッション")
        self.delete_button = QPushButton("-")
        self.delete_button.setToolTip("現在のセッションを削除")
        row = QHBoxLayout(self)
        row.addWidget(self.session_combo, stretch=1)
        row.addWidget(self.add_button)
        row.addWidget(self.delete_button)
