from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QKeyEvent, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_ZOOM_MIN = 0.25
_ZOOM_MAX = 8.0
_WHEEL_STEP = 1.12
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


class _PreviewViewport(QWidget):
    nudge = pyqtSignal(int, int)
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._source: QPixmap | None = None
        self._iw = 0
        self._ih = 0

        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._zoom_mul = 1.0

        self._dragging = False
        self._drag_last: QPointF | None = None

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

    def set_source_pixmap(self, pm: QPixmap | None, reset_interaction: bool) -> None:
        if pm is None or pm.isNull():
            self._source = None
            self._iw = self._ih = 0
            self._dragging = False
            self._drag_last = None
            self.update()
            return
        self._source = pm
        self._iw = pm.width()
        self._ih = pm.height()
        if reset_interaction:
            self._reset_transform_to_fit()
        self.update()

    def reset_view(self) -> None:
        self._reset_transform_to_fit()
        self.update()

    def _s_fit(self) -> float:
        if self._iw <= 0 or self._ih <= 0:
            return 1.0
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        return min(vp_w / self._iw, vp_h / self._ih)

    def _reset_transform_to_fit(self) -> None:
        self._zoom_mul = 1.0
        s_fit = self._s_fit()
        self._scale = s_fit * self._zoom_mul
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        self._ox = (vp_w - self._iw * self._scale) / 2.0
        self._oy = (vp_h - self._ih * self._scale) / 2.0

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._source and not self._source.isNull():
            s_fit = self._s_fit()
            min_s = s_fit * _ZOOM_MIN
            max_s = s_fit * _ZOOM_MAX
            self._scale = max(min_s, min(max_s, self._scale))
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            ix = (cx - self._ox) / self._scale if self._scale > 0 else 0.0
            iy = (cy - self._oy) / self._scale if self._scale > 0 else 0.0
            self._ox = cx - ix * self._scale
            self._oy = cy - iy * self._scale
        self._place_pad()
        self.update()

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

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().base())
        if self._source is None or self._source.isNull() or self._iw <= 0:
            p.setPen(QColor(120, 120, 120))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "プレビュー")
            p.end()
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.drawPixmap(
            int(self._ox),
            int(self._oy),
            int(self._iw * self._scale),
            int(self._ih * self._scale),
            self._source,
        )
        pen = p.pen()
        p.setPen(QColor(136, 136, 136))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.setPen(pen)
        p.end()

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            super().wheelEvent(event)
            return
        if self._source is None or self._source.isNull():
            return
        s_fit = self._s_fit()
        min_s = s_fit * _ZOOM_MIN
        max_s = s_fit * _ZOOM_MAX
        pos = event.position()
        mx, my = float(pos.x()), float(pos.y())
        old_scale = self._scale
        ix = (mx - self._ox) / old_scale if old_scale > 0 else 0.0
        iy = (my - self._oy) / old_scale if old_scale > 0 else 0.0
        delta = event.angleDelta().y()
        factor = _WHEEL_STEP if delta > 0 else 1.0 / _WHEEL_STEP
        new_scale = max(min_s, min(max_s, old_scale * factor))
        self._scale = new_scale
        self._zoom_mul = self._scale / s_fit if s_fit > 0 else 1.0
        self._ox = mx - ix * new_scale
        self._oy = my - iy * new_scale
        self._clamp_origin()
        self.update()
        event.accept()

    def _clamp_origin(self) -> None:
        if self._iw <= 0 or self._ih <= 0:
            return
        vp_w = float(self.width())
        vp_h = float(self.height())
        iw = self._iw * self._scale
        ih = self._ih * self._scale
        margin = 40.0
        self._ox = min(max(self._ox, vp_w - iw - margin), margin)
        self._oy = min(max(self._oy, vp_h - ih - margin), margin)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_last = event.position()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._dragging and self._drag_last is not None:
            cur = event.position()
            dx = cur.x() - self._drag_last.x()
            dy = cur.y() - self._drag_last.y()
            self._ox += dx
            self._oy += dy
            self._drag_last = cur
            self._clamp_origin()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

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

        self._viewport = _PreviewViewport(self)
        self._viewport.nudge.connect(self.nudge.emit)
        self._viewport.reset_requested.connect(self.reset_requested.emit)

        self._hint = QLabel(_HINT_BASE)
        self._hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._viewport, stretch=1)
        lay.addWidget(self._hint)

    def set_preview(self, pixmap: QPixmap | None, subtitle: str = "") -> None:
        if pixmap is None or pixmap.isNull():
            self._last_preview_wh = None
            self._viewport.set_source_pixmap(None, True)
        else:
            wh = (pixmap.width(), pixmap.height())
            reset = self._last_preview_wh != wh
            self._last_preview_wh = wh
            self._viewport.set_source_pixmap(pixmap, reset)
        if subtitle:
            self._hint.setText(f"{subtitle}\n\n{_HINT_BASE}")
        else:
            self._hint.setText(_HINT_BASE)

    def reset_view(self) -> None:
        self._viewport.reset_view()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self._viewport.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)
