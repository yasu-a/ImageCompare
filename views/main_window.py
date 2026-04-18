from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from views.composite_preview_panel import CompositePreviewPanel
from views.paste_image_panel import PasteImagePanel
from views.session_toolbar import SessionToolbar
from views.variant_toolbar import VariantToolbar

# QLabel は QFrame のサブクラスのため、親に「QFrame { ... }」だけだと子ラベルにも当たる。
# セクション枠だけを対象にするため objectName で限定する。
_SECTION_FRAME_QSS = (
    "QFrame#section_base, QFrame#section_cmp, QFrame#section_right {"
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
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ImageCompare")
        self.resize(1100, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        status = QStatusBar()
        status.setMinimumHeight(28)
        status.setSizeGripEnabled(False)
        status.messageChanged.connect(self._on_status_message_changed)
        self.setStatusBar(status)

        self.session_toolbar = SessionToolbar()
        root.addWidget(self.session_toolbar)

        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.setHandleWidth(6)
        self._left_split = QSplitter(Qt.Orientation.Vertical)
        self._left_split.setHandleWidth(5)

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

        self._left_split.addWidget(frame_base)
        self._left_split.addWidget(frame_cmp)
        self._left_split.setStretchFactor(0, 1)
        self._left_split.setStretchFactor(1, 1)

        frame_right = QFrame()
        _style_section_frame(frame_right, "section_right")
        rr = QVBoxLayout(frame_right)
        rr.setContentsMargins(8, 8, 8, 8)
        title_r = QLabel("プレビュー")
        title_r.setStyleSheet("font-weight: bold;")
        rr.addWidget(title_r)

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
        rr.addLayout(diff_row)

        self.preview_panel = CompositePreviewPanel()
        rr.addWidget(self.preview_panel, stretch=1)

        self._main_split.addWidget(self._left_split)
        self._main_split.addWidget(frame_right)
        self._main_split.setStretchFactor(0, 1)
        self._main_split.setStretchFactor(1, 2)
        root.addWidget(self._main_split, stretch=1)

        self._split_done = False

    def _on_status_message_changed(self, text: str) -> None:
        if not text.strip():
            self.statusBar().setStyleSheet("")

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._split_done:
            self._split_done = True
            w = max(self.width(), 600)
            self._main_split.setSizes([w // 3, 2 * w // 3])
            h = max(self.height() - 100, 240)
            self._left_split.setSizes([h // 2, h // 2])
