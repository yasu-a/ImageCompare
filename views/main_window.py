from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSlider,
    QSplitter,
    QStatusBar,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from views.composite_preview_panel import CompositePreviewPanel
from views.paste_image_panel import PasteImagePanel
from views.session_list_panel import SessionListPanel
from views.variant_toolbar import VariantToolbar

# QLabel は QFrame のサブクラスのため、親に「QFrame { ... }」だけだと子ラベルにも当たる。
# セクション枠だけを対象にするため objectName で限定する。
_SECTION_FRAME_QSS = (
    "QFrame#section_session, QFrame#section_base, QFrame#section_cmp, QFrame#section_right {"
    "  border: 1px solid #b0b0b0;"
    "  border-radius: 8px;"
    "  background-color: palette(base);"
    "}"
)


def _style_section_frame(frame: QFrame, section_id: str) -> None:
    frame.setObjectName(section_id)
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setStyleSheet(_SECTION_FRAME_QSS)


class MainWindow(QMainWindow):
    """横3分割: 左=セッション一覧 / 中央=基準+比較 / 右=プレビュー。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ImageCompare")
        self.resize(1200, 720)

        self.session_section_collapsed = False
        self.preview_section_collapsed = False
        self._preview_collapsed_outer_w = 40
        self._triple_split_session_backup: list[int] | None = None
        self._triple_split_preview_backup: list[int] | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        status = QStatusBar()
        status.setMinimumHeight(28)
        status.setSizeGripEnabled(False)
        status.messageChanged.connect(self._on_status_message_changed)
        self.setStatusBar(status)

        # 横: [セッション] [基準+比較] [プレビュー]
        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.setHandleWidth(6)
        # 縦: 基準画像 / 比較画像（メイン列）
        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.setHandleWidth(5)

        self.session_list_panel = SessionListPanel()
        self.session_list_panel.setMinimumWidth(160)
        _style_section_frame(self.session_list_panel, "section_session")

        frame_base = QFrame()
        _style_section_frame(frame_base, "section_base")
        fb = QVBoxLayout(frame_base)
        fb.setContentsMargins(8, 8, 8, 8)
        title_b = QLabel("基準画像")
        title_b.setStyleSheet("font-weight: bold;")
        fb.addWidget(title_b)
        self.base_panel = PasteImagePanel(
            "クリックで選択 / Ctrl+Vで貼付 / 画像をドロップ"
        )
        fb.addWidget(self.base_panel, stretch=1)

        frame_cmp = QFrame()
        _style_section_frame(frame_cmp, "section_cmp")
        fc = QVBoxLayout(frame_cmp)
        fc.setContentsMargins(8, 8, 8, 8)
        title_c = QLabel("比較画像")
        title_c.setStyleSheet("font-weight: bold;")
        fc.addWidget(title_c)
        self.variant_toolbar = VariantToolbar()
        fc.addWidget(self.variant_toolbar)
        self.variant_panel = PasteImagePanel(
            "クリックで選択 / Ctrl+Vで貼付 / 画像をドロップ"
        )
        fc.addWidget(self.variant_panel, stretch=1)

        self._center_split.addWidget(frame_base)
        self._center_split.addWidget(frame_cmp)
        self._center_split.setStretchFactor(0, 1)
        self._center_split.setStretchFactor(1, 1)

        self._preview_frame = QFrame()
        _style_section_frame(self._preview_frame, "section_right")
        self._preview_rr = QVBoxLayout(self._preview_frame)
        self._preview_rr.setContentsMargins(8, 8, 8, 8)
        self._preview_rr.setSpacing(6)

        self._preview_header_widget = QWidget(self._preview_frame)
        self._preview_title_row_layout = QHBoxLayout(self._preview_header_widget)
        self._preview_title_row_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_title_row_layout.setSpacing(6)
        self._preview_collapse_btn = QToolButton()
        self._preview_collapse_btn.setAutoRaise(True)
        self._preview_collapse_btn.setToolTip("プレビューセクションを折りたたむ / 展開")
        self._preview_collapse_btn.setFixedSize(28, 28)
        self._set_preview_collapse_icon(False)
        self._preview_title_row_layout.addWidget(self._preview_collapse_btn)
        self._preview_title_lbl = QLabel("プレビュー")
        self._preview_title_lbl.setStyleSheet("font-weight: bold;")
        self._preview_title_row_layout.addWidget(self._preview_title_lbl)
        self._preview_title_row_layout.addStretch(1)
        self._preview_rr.addWidget(self._preview_header_widget, 0, Qt.AlignmentFlag.AlignTop)

        self._preview_collapsed_strip = QWidget(self._preview_frame)
        self._preview_collapsed_vl = QVBoxLayout(self._preview_collapsed_strip)
        self._preview_collapsed_vl.setContentsMargins(2, 2, 2, 2)
        self._preview_collapsed_strip.hide()
        self._preview_rr.addWidget(self._preview_collapsed_strip, 0, Qt.AlignmentFlag.AlignTop)

        self._preview_section_content = QWidget(self._preview_frame)
        prc = QVBoxLayout(self._preview_section_content)
        prc.setContentsMargins(0, 0, 0, 0)
        prc.setSpacing(6)

        diff_row = QHBoxLayout()
        diff_lbl = QLabel("差分グループ半径")
        self.diff_group_slider = QSlider(Qt.Orientation.Horizontal)
        self.diff_group_slider.setRange(1, 50)
        self.diff_group_slider.setValue(10)
        self.diff_group_slider.setPageStep(5)
        self.diff_group_value_label = QLabel("10 px")
        self.diff_group_value_label.setMinimumWidth(48)
        diff_row.addWidget(diff_lbl)
        diff_row.addWidget(self.diff_group_slider, stretch=1)
        diff_row.addWidget(self.diff_group_value_label)
        prc.addLayout(diff_row)

        self.preview_panel = CompositePreviewPanel()
        prc.addWidget(self.preview_panel, stretch=1)

        self._preview_rr.addWidget(self._preview_section_content, stretch=1)

        self._main_split.addWidget(self.session_list_panel)
        self._main_split.addWidget(self._center_split)
        self._main_split.addWidget(self._preview_frame)
        self._main_split.setStretchFactor(0, 0)
        self._main_split.setStretchFactor(1, 1)
        self._main_split.setStretchFactor(2, 1)
        root.addWidget(self._main_split, stretch=1)

        self._split_done = False

    def center_split(self) -> QSplitter:
        """中央列（基準画像・比較画像の縦分割）。"""
        return self._center_split

    def main_split(self) -> QSplitter:
        """左・中央・右の横3分割。"""
        return self._main_split

    def _set_preview_collapse_icon(self, collapsed: bool) -> None:
        # 開いている: 「>」、閉じた: 「<」（左セクションと逆）
        sp = (
            QStyle.StandardPixmap.SP_ArrowLeft
            if collapsed
            else QStyle.StandardPixmap.SP_ArrowRight
        )
        self._preview_collapse_btn.setIcon(self.style().standardIcon(sp))

    def set_preview_section_collapsed(self, collapsed: bool) -> None:
        self.preview_section_collapsed = collapsed
        self._preview_section_content.setVisible(not collapsed)
        self._set_preview_collapse_icon(collapsed)

        if collapsed:
            self._preview_title_row_layout.removeWidget(self._preview_collapse_btn)
            self._preview_collapse_btn.setParent(self._preview_collapsed_strip)
            self._preview_collapsed_vl.addWidget(
                self._preview_collapse_btn,
                0,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
            self._preview_header_widget.hide()
            self._preview_collapsed_strip.show()
            self._preview_rr.setContentsMargins(3, 4, 3, 4)
            self._preview_collapsed_vl.setContentsMargins(2, 2, 2, 2)
            self._preview_collapsed_strip.adjustSize()
            inner = self._preview_collapsed_strip.sizeHint().width()
            rm = self._preview_rr.contentsMargins().left() + self._preview_rr.contentsMargins().right()
            border_pad = 4
            self._preview_collapsed_outer_w = max(36, inner + rm + border_pad)
            self._preview_frame.setFixedWidth(self._preview_collapsed_outer_w)
            self._preview_frame.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
            )
        else:
            self._preview_collapsed_vl.removeWidget(self._preview_collapse_btn)
            self._preview_collapse_btn.setParent(self._preview_header_widget)
            self._preview_title_row_layout.insertWidget(0, self._preview_collapse_btn)
            self._preview_collapsed_strip.hide()
            self._preview_header_widget.show()
            self._preview_rr.setContentsMargins(8, 8, 8, 8)
            self._preview_frame.setMinimumWidth(0)
            self._preview_frame.setMaximumWidth(16777215)
            self._preview_frame.setMinimumHeight(0)
            self._preview_frame.setMaximumHeight(16777215)
            self._preview_frame.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
            )

    def preview_collapsed_column_outer_width(self) -> int:
        """折りたたみ直後の右列幅。展開中は参照されない想定。"""
        return self._preview_collapsed_outer_w

    def preview_collapse_button(self) -> QToolButton:
        return self._preview_collapse_btn

    def _on_status_message_changed(self, text: str) -> None:
        if not text.strip():
            self.statusBar().setStyleSheet("")

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._split_done:
            self._split_done = True
            tw = max(self.width(), 700)
            # 左:セッション / 中央:メイン / 右:プレビュー
            self._main_split.setSizes([200, tw // 2, tw - 200 - tw // 2])
            h = max(self.height() - 80, 280)
            self._center_split.setSizes([h // 2, h // 2])
