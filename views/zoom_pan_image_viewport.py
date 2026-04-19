"""Ctrl+ホイール拡縮・ドラッグパン・フィット矩形付きの共通画像ビューポート。"""

from dataclasses import dataclass

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QSizePolicy, QWidget

_ZOOM_MIN = 0.25
_ZOOM_MAX = 8.0
_WHEEL_STEP = 1.12


@dataclass(frozen=True)
class ZoomPanViewState:
    """ビュー間同期用: 画像1pxあたりの画面px（_scale）とビュー中心の画像内位置（正規化座標）。"""

    scale: float
    center_u: float
    center_v: float


class ZoomPanImageViewport(QWidget):
    """画像を描画し、Ctrl+ホイールでズーム・左ドラッグでパンする。"""

    interaction_pressed = pyqtSignal()
    transform_changed = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        empty_hint: str = "",
        draw_viewport_border: bool = True,
    ) -> None:
        super().__init__(parent)
        self._empty_hint = empty_hint
        self._draw_viewport_border = draw_viewport_border
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._source: QPixmap | None = None
        self._iw = 0
        self._ih = 0
        self._fit_rx = 0
        self._fit_ry = 0
        self._fit_rw = 0
        self._fit_rh = 0

        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._zoom_mul = 1.0

        self._dragging = False
        self._drag_last: QPointF | None = None

    def set_pixmap(
        self,
        pm: QPixmap | None,
        reset_interaction: bool,
        fit_content_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        if pm is None or pm.isNull():
            self._source = None
            self._iw = self._ih = 0
            self._fit_rx = self._fit_ry = self._fit_rw = self._fit_rh = 0
            self._dragging = False
            self._drag_last = None
            self.update()
            self.transform_changed.emit()
            return
        self._source = pm
        self._iw = pm.width()
        self._ih = pm.height()
        self._apply_fit_content_rect(fit_content_rect)
        if reset_interaction:
            self._reset_transform_to_fit()
        self.update()
        self.transform_changed.emit()

    def reset_view(self) -> None:
        self._reset_transform_to_fit()
        self.update()
        self.transform_changed.emit()

    def has_pixmap(self) -> bool:
        return self._source is not None and not self._source.isNull() and self._iw > 0

    def view_state(self) -> ZoomPanViewState | None:
        """現在の実スケールとビュー中心の画像座標（正規化）。"""
        if not self.has_pixmap() or self._scale <= 0:
            return None
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        cx = vp_w / 2.0
        cy = vp_h / 2.0
        cix = (cx - self._ox) / self._scale
        ciy = (cy - self._oy) / self._scale
        u = cix / float(self._iw)
        v = ciy / float(self._ih)
        return ZoomPanViewState(scale=self._scale, center_u=u, center_v=v)

    def apply_view_state(self, state: ZoomPanViewState) -> None:
        """別ビューと同じ実スケール・同じ正規化中心で表示する（各ビューの clamp 内に収める）。"""
        if not self.has_pixmap():
            return
        s_fit = self._s_fit()
        if s_fit <= 0:
            return
        min_s = s_fit * _ZOOM_MIN
        max_s = s_fit * _ZOOM_MAX
        self._scale = max(min_s, min(max_s, state.scale))
        self._zoom_mul = self._scale / s_fit
        cix = state.center_u * float(self._iw)
        ciy = state.center_v * float(self._ih)
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        self._ox = vp_w / 2.0 - cix * self._scale
        self._oy = vp_h / 2.0 - ciy * self._scale
        self._clamp_origin()
        self.update()
        self.transform_changed.emit()

    def image_rect_to_viewport_rectf(
        self, ix: int, iy: int, iw: int, ih: int
    ) -> tuple[float, float, float, float]:
        """画像座標の矩形をビューポート座標 (x, y, w, h) float で返す。"""
        if not self.has_pixmap():
            return 0.0, 0.0, 0.0, 0.0
        s = self._scale
        return (
            self._ox + ix * s,
            self._oy + iy * s,
            iw * s,
            ih * s,
        )

    def _apply_fit_content_rect(
        self, fit_content_rect: tuple[int, int, int, int] | None
    ) -> None:
        if fit_content_rect is None or self._iw <= 0 or self._ih <= 0:
            self._fit_rx, self._fit_ry = 0, 0
            self._fit_rw, self._fit_rh = self._iw, self._ih
            return
        rx, ry, rw, rh = fit_content_rect
        rw = max(1, rw)
        rh = max(1, rh)
        rx = max(0, min(rx, self._iw - 1))
        ry = max(0, min(ry, self._ih - 1))
        rw = min(rw, self._iw - rx)
        rh = min(rh, self._ih - ry)
        self._fit_rx, self._fit_ry = rx, ry
        self._fit_rw, self._fit_rh = max(1, rw), max(1, rh)

    def _s_fit(self) -> float:
        if self._fit_rw <= 0 or self._fit_rh <= 0:
            return 1.0
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        return min(vp_w / self._fit_rw, vp_h / self._fit_rh)

    def _reset_transform_to_fit(self) -> None:
        self._zoom_mul = 1.0
        s_fit = self._s_fit()
        self._scale = s_fit * self._zoom_mul
        vp_w = max(self.width(), 1)
        vp_h = max(self.height(), 1)
        cx_img = self._fit_rx + self._fit_rw / 2.0
        cy_img = self._fit_ry + self._fit_rh / 2.0
        self._ox = vp_w / 2.0 - cx_img * self._scale
        self._oy = vp_h / 2.0 - cy_img * self._scale

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._source and not self._source.isNull():
            old = event.oldSize()
            old_bad = (
                not old.isValid()
                or old.width() <= 0
                or old.height() <= 0
            )
            # __init__ 直後など幅高さ0で set_pixmap すると極端な変換になり、
            # 初回レイアウト後のピボット補正で描画が画面外に飛ぶ。無効→有効のときは作り直す。
            if old_bad and self.width() > 0 and self.height() > 0:
                self._reset_transform_to_fit()
            else:
                s_fit = self._s_fit()
                min_s = s_fit * _ZOOM_MIN
                max_s = s_fit * _ZOOM_MAX
                old_scale = self._scale
                self._scale = max(min_s, min(max_s, self._scale))
                self._zoom_mul = self._scale / s_fit if s_fit > 0 else 1.0
                cx = self.width() / 2.0
                cy = self.height() / 2.0
                ix = (cx - self._ox) / old_scale if old_scale > 0 else 0.0
                iy = (cy - self._oy) / old_scale if old_scale > 0 else 0.0
                self._ox = cx - ix * self._scale
                self._oy = cy - iy * self._scale
        self.update()
        self.transform_changed.emit()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().base())
        if self._source is None or self._source.isNull() or self._iw <= 0:
            if self._empty_hint:
                p.setPen(QColor(120, 120, 120))
                p.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    self._empty_hint,
                )
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
        if self._draw_viewport_border:
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
        self.transform_changed.emit()
        event.accept()

    def _clamp_origin(self) -> None:
        if self._iw <= 0 or self._ih <= 0:
            return
        vp_w = float(self.width())
        vp_h = float(self.height())
        iw = self._iw * self._scale
        ih = self._ih * self._scale
        margin = 40.0
        # 画像がビューより小さいとき vp - size - margin > margin となり、
        # min(max(ox, 大), 小) だと常に小側に吸い付く（縦が上付きになる）ので端を正しく min/max する。
        ox_lo = min(margin, vp_w - iw - margin)
        ox_hi = max(margin, vp_w - iw - margin)
        oy_lo = min(margin, vp_h - ih - margin)
        oy_hi = max(margin, vp_h - ih - margin)
        self._ox = min(max(self._ox, ox_lo), ox_hi)
        self._oy = min(max(self._oy, oy_lo), oy_hi)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.interaction_pressed.emit()
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
            self.transform_changed.emit()
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
        if event.key() == Qt.Key.Key_Space:
            self.reset_view()
            event.accept()
            return
        super().keyPressEvent(event)
