from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget


class VariantToolbar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.variant_combo = QComboBox()
        self.variant_combo.setMinimumWidth(160)
        self.add_button = QPushButton("+")
        self.add_button.setToolTip("比較スロット追加")
        self.delete_button = QPushButton("-")
        self.delete_button.setToolTip("選択中の比較スロットを削除")
        self.clear_button = QPushButton("クリア")
        self.clear_button.setToolTip("選択中スロットの画像をクリア")
        row = QHBoxLayout(self)
        row.addWidget(self.variant_combo, stretch=1)
        row.addWidget(self.add_button)
        row.addWidget(self.delete_button)
        row.addWidget(self.clear_button)
