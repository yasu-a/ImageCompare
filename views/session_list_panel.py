"""左カラム用: セッション一覧（QListWidget）と追加・削除・折りたたみ。"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class SessionListPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        # 折りたたみ後に main_split へ渡す列幅（set_section_collapsed で更新）
        self._collapsed_outer_w = 40

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._header_widget = QWidget(self)
        self._title_row_layout = QHBoxLayout(self._header_widget)
        self._title_row_layout.setContentsMargins(0, 0, 0, 0)
        self._title_row_layout.setSpacing(6)
        self._title_lbl = QLabel("セッション")
        self._title_lbl.setStyleSheet("font-weight: bold;")
        self._title_row_layout.addWidget(self._title_lbl)
        self._title_row_layout.addStretch(1)

        self.collapse_button = QToolButton()
        self.collapse_button.setAutoRaise(True)
        self.collapse_button.setToolTip("セクションを折りたたむ / 展開")
        self.collapse_button.setFixedSize(28, 28)
        self._set_collapse_icon(False)
        self._title_row_layout.addWidget(self.collapse_button)

        root.addWidget(self._header_widget, 0, Qt.AlignmentFlag.AlignTop)

        self._collapsed_strip = QWidget(self)
        self._collapsed_vl = QVBoxLayout(self._collapsed_strip)
        self._collapsed_vl.setContentsMargins(2, 2, 2, 2)
        self._collapsed_strip.hide()
        root.addWidget(self._collapsed_strip, 0, Qt.AlignmentFlag.AlignTop)

        self._content = QWidget(self)
        cv = QVBoxLayout(self._content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(6)

        self.session_list = QListWidget()
        self.session_list.setMinimumHeight(72)
        self.session_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        cv.addWidget(self.session_list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.add_button = self._mk_icon_btn(
            "list-add",
            QStyle.StandardPixmap.SP_FileDialogNewFolder,
            "新規セッション",
        )
        sp_del = getattr(
            QStyle.StandardPixmap, "SP_TrashIcon", QStyle.StandardPixmap.SP_DialogDiscardButton
        )
        self.delete_button = self._mk_icon_btn(
            "list-remove",
            sp_del,
            "現在のセッションを削除",
        )
        btn_row.addWidget(self.add_button)
        btn_row.addWidget(self.delete_button)
        btn_row.addStretch(1)
        cv.addLayout(btn_row)

        root.addWidget(self._content, stretch=1)

    def _mk_icon_btn(
        self, theme_name: str, fallback: QStyle.StandardPixmap, tip: str
    ) -> QToolButton:
        b = QToolButton(self._content)
        b.setAutoRaise(True)
        b.setToolTip(tip)
        b.setFixedSize(32, 32)
        ic = QIcon.fromTheme(theme_name)
        if ic.isNull():
            ic = self.style().standardIcon(fallback)
        b.setIcon(ic)
        b.setIconSize(QSize(22, 22))
        return b

    def _set_collapse_icon(self, collapsed: bool) -> None:
        # 開いている: 「<」、閉じた: 「>」
        sp = (
            QStyle.StandardPixmap.SP_ArrowRight
            if collapsed
            else QStyle.StandardPixmap.SP_ArrowLeft
        )
        self.collapse_button.setIcon(self.style().standardIcon(sp))

    def set_section_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._content.setVisible(not collapsed)
        self._set_collapse_icon(collapsed)

        if collapsed:
            self._title_row_layout.removeWidget(self.collapse_button)
            self.collapse_button.setParent(self._collapsed_strip)
            self._collapsed_vl.addWidget(
                self.collapse_button,
                0,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
            self._header_widget.hide()
            self._collapsed_strip.show()
            root = self.layout()
            if isinstance(root, QVBoxLayout):
                # 横は最小限（ボタンが枠に埋もれないよう左右はやや均等）
                root.setContentsMargins(3, 4, 3, 4)
            self._collapsed_vl.setContentsMargins(2, 2, 2, 2)
            self._collapsed_strip.adjustSize()
            inner = self._collapsed_strip.sizeHint().width()
            rm = 0
            if isinstance(root, QVBoxLayout):
                rm = root.contentsMargins().left() + root.contentsMargins().right()
            # QFrame の枠線（stylesheet）分の余裕
            border_pad = 4
            self._collapsed_outer_w = max(36, inner + rm + border_pad)
            self.setFixedWidth(self._collapsed_outer_w)
            self.setMinimumHeight(0)
            self.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
            )
        else:
            self._collapsed_vl.removeWidget(self.collapse_button)
            self.collapse_button.setParent(self._header_widget)
            self._title_row_layout.addWidget(self.collapse_button)
            self._collapsed_strip.hide()
            self._header_widget.show()
            root = self.layout()
            if isinstance(root, QVBoxLayout):
                root.setContentsMargins(8, 8, 8, 8)
            self.setMinimumWidth(160)
            self.setMaximumWidth(16777215)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
            )

    def collapsed_column_outer_width(self) -> int:
        """折りたたみ時の列幅（スプリッタ用）。展開中は最小幅。"""
        if self._collapsed:
            return self._collapsed_outer_w
        return max(160, self.minimumWidth())

    def is_section_collapsed(self) -> bool:
        return self._collapsed

    def toggle_section_collapsed(self) -> bool:
        self.set_section_collapsed(not self._collapsed)
        return self._collapsed
