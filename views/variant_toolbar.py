from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QStyle,
    QToolButton,
    QWidget,
)


class VariantToolbar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.variant_combo = QComboBox()
        self.variant_combo.setMinimumWidth(160)

        self.rename_button = self._mk_icon_btn(
            "document-edit",
            QStyle.StandardPixmap.SP_FileDialogInfoView,
            "名前を変更",
        )
        self.add_button = self._mk_icon_btn(
            "list-add",
            QStyle.StandardPixmap.SP_FileDialogNewFolder,
            "比較スロット追加",
        )
        sp_del = getattr(
            QStyle.StandardPixmap, "SP_TrashIcon", QStyle.StandardPixmap.SP_DialogDiscardButton
        )
        self.delete_button = self._mk_icon_btn(
            "list-remove",
            sp_del,
            "選択中の比較スロットを削除",
        )

        row = QHBoxLayout(self)
        row.setSpacing(6)
        row.addWidget(self.variant_combo, stretch=1)
        row.addWidget(self.rename_button)
        row.addWidget(self.add_button)
        row.addWidget(self.delete_button)

    def _mk_icon_btn(
        self, theme_name: str, fallback: QStyle.StandardPixmap, tip: str
    ) -> QToolButton:
        b = QToolButton(self)
        b.setAutoRaise(True)
        b.setToolTip(tip)
        b.setFixedSize(32, 32)
        ic = QIcon.fromTheme(theme_name)
        if ic.isNull():
            ic = self.style().standardIcon(fallback)
        b.setIcon(ic)
        b.setIconSize(QSize(22, 22))
        return b
