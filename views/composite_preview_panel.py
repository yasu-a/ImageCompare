from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from views.zoom_pan_image_viewport import ZoomPanImageViewport

_PAD_BTN_STYLE = (
    "QPushButton {"
    "  background-color: rgba(255,255,255,140);"
    "  border: 1px solid rgba(0,0,0,90);"
    "  border-radius: 6px;"
    "  min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;"
    "  font-size: 11px;"
    "}"
    "QPushButton:hover { background-color: rgba(255,255,255,200); }"
)

_HINT_BASE = (
    "クリックでフォーカス: Ctrl+ホイールで拡大縮小 / 左ドラッグで移動 / "
    "矢印またはWASDで1px / Spaceで比較位置と表示をリセット"
)


class _PreviewViewport(ZoomPanImageViewport):
    """プレビュー専用: 微調整ボタン・キーで比較オフセット操作。"""

    nudge = pyqtSignal(int, int)
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent, empty_hint="プレビュー", draw_viewport_border=True
        )
        self.setMinimumHeight(200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._pad_wrap = QWidget(self)
        self._pad_wrap.hide()
        grid = QGridLayout(self._pad_wrap)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(4)

        def mk(txt: str, dx: int, dy: int) -> QPushButton:
            b = QPushButton(txt)
            b.setStyleSheet(_PAD_BTN_STYLE)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, ddx=dx, ddy=dy: self.nudge.emit(ddx, ddy))
            return b

        self._btn_u = mk("↑", 0, -1)
        self._btn_d = mk("↓", 0, 1)
        self._btn_l = mk("←", -1, 0)
        self._btn_r = mk("→", 1, 0)
        self._btn_c = QPushButton("◎")
        self._btn_c.setStyleSheet(_PAD_BTN_STYLE)
        self._btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_c.clicked.connect(self.reset_requested.emit)

        grid.addWidget(self._btn_u, 0, 1)
        grid.addWidget(self._btn_l, 1, 0)
        grid.addWidget(self._btn_c, 1, 1)
        grid.addWidget(self._btn_r, 1, 2)
        grid.addWidget(self._btn_d, 2, 1)

    def set_source_pixmap(
        self,
        pm,
        reset_interaction: bool,
        fit_content_rect: tuple[int, int, int, int] | None,
    ) -> None:
        self.set_pixmap(pm, reset_interaction, fit_content_rect)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._place_pad()

    def _place_pad(self) -> None:
        self._pad_wrap.adjustSize()
        m = 10
        x = self.width() - self._pad_wrap.width() - m
        y = self.height() - self._pad_wrap.height() - m
        self._pad_wrap.move(max(m, x), max(m, y))

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._pad_wrap.show()
        self._place_pad()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        p = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(p):
            self._pad_wrap.hide()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        k = event.key()
        if k == Qt.Key.Key_Left or k == Qt.Key.Key_A:
            self.nudge.emit(-1, 0)
        elif k == Qt.Key.Key_Right or k == Qt.Key.Key_D:
            self.nudge.emit(1, 0)
        elif k == Qt.Key.Key_Up or k == Qt.Key.Key_W:
            self.nudge.emit(0, -1)
        elif k == Qt.Key.Key_Down or k == Qt.Key.Key_S:
            self.nudge.emit(0, 1)
        elif k == Qt.Key.Key_Space:
            self.reset_requested.emit()
        else:
            super().keyPressEvent(event)
            return
        event.accept()


class CompositePreviewPanel(QWidget):
    """プレビュー: アスペクト維持、Ctrl+ホイール、ドラッグパン、矢印・WASD・Space。"""

    nudge = pyqtSignal(int, int)
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_preview_wh: tuple[int, int] | None = None
        self._last_fit_rect: tuple[int, int, int, int] | None = None

        self._viewport = _PreviewViewport(self)
        self._viewport.nudge.connect(self.nudge.emit)
        self._viewport.reset_requested.connect(self.reset_requested.emit)

        self._hint = QLabel(_HINT_BASE)
        self._hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._viewport, stretch=1)
        lay.addWidget(self._hint)

    def set_preview(
        self,
        pixmap,
        subtitle: str = "",
        fit_content_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        if pixmap is None or pixmap.isNull():
            self._last_preview_wh = None
            self._last_fit_rect = None
            self._viewport.set_source_pixmap(None, True, None)
        else:
            wh = (pixmap.width(), pixmap.height())
            reset = self._last_preview_wh != wh or self._last_fit_rect != fit_content_rect
            self._last_preview_wh = wh
            self._last_fit_rect = fit_content_rect
            self._viewport.set_source_pixmap(pixmap, reset, fit_content_rect)
        if subtitle:
            self._hint.setText(f"{subtitle}\n\n{_HINT_BASE}")
        else:
            self._hint.setText(_HINT_BASE)

    def reset_view(self) -> None:
        self._viewport.reset_view()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._viewport.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)
