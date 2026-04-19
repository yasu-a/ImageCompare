from pathlib import Path

import numpy as np
from PyQt6.QtCore import QEvent, QObject, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStyle,
    QToolButton,
    QWidget,
)

from views.zoom_pan_image_viewport import ZoomPanImageViewport


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

# 枠線の太さは当たり判定に含めず、矩形の外側に足すヒット用マージン（ビューポート座標 px）
_HIT_MARGIN_PX = 6.0


class _RectHighlightOverlay(QWidget):
    """画像上に差分グループの枠を描画。ホバー中はオレンジ。"""

    def __init__(
        self, viewport: ZoomPanImageViewport, panel: "PasteImagePanel"
    ) -> None:
        super().__init__(viewport)
        self._viewport = viewport
        self._panel = panel
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        rects = self._panel._highlight_rects
        if not rects or not self._viewport.has_pixmap():
            return
        hover = self._panel._hover_highlight_idx
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for i, (x, y, w, h) in enumerate(rects):
            vx, vy, vw, vh = self._viewport.image_rect_to_viewport_rectf(x, y, w, h)
            pen = QPen(
                QColor(255, 140, 0) if hover == i else QColor(255, 0, 0)
            )
            pen.setWidth(2)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawRect(QRectF(vx, vy, vw, vh))
        p.end()


class PasteImagePanel(QWidget):
    """選択後に Ctrl+V / ツールバーで貼付。D&D対応。ホバーで操作ボタン。Ctrl+ホイール・パン対応。"""

    activated = pyqtSignal()
    paste_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    file_dropped = pyqtSignal(str)
    diff_highlight_pair_clicked = pyqtSignal(int)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected = False
        self._placeholder = placeholder
        self._highlight_rects: list[tuple[int, int, int, int]] = []
        self._hover_highlight_idx: int | None = None
        self._last_wh: tuple[int, int] | None = None
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._viewport = ZoomPanImageViewport(
            self,
            empty_hint=placeholder,
            draw_viewport_border=False,
        )
        self._viewport.setMinimumHeight(120)
        self._viewport.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._viewport.interaction_pressed.connect(self.activated.emit)
        self._viewport.installEventFilter(self)

        self._rect_overlay = _RectHighlightOverlay(self._viewport, self)
        self._viewport.transform_changed.connect(self._rect_overlay.update)
        self._rect_overlay.hide()

        self._overlay = QWidget(self)
        self._overlay.hide()
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        row = QHBoxLayout(self._overlay)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(6)

        self._btn_paste = self._mk_tool_btn("edit-paste", QStyle.StandardPixmap.SP_FileDialogStart)
        self._btn_paste.setToolTip("貼り付け (Ctrl+V)")
        self._btn_paste.clicked.connect(self.paste_requested.emit)

        self._btn_undo = self._mk_tool_btn("edit-undo", QStyle.StandardPixmap.SP_ArrowBack)
        self._btn_undo.setToolTip("元に戻す (Ctrl+Z)")
        self._btn_undo.clicked.connect(self.undo_requested.emit)

        sp_clear = getattr(
            QStyle.StandardPixmap, "SP_TrashIcon", QStyle.StandardPixmap.SP_DialogDiscardButton
        )
        self._btn_clear = self._mk_tool_btn("edit-delete", sp_clear)
        self._btn_clear.setToolTip("クリア (Delete)")
        self._btn_clear.clicked.connect(self.clear_requested.emit)

        row.addWidget(self._btn_paste)
        row.addWidget(self._btn_undo)
        row.addWidget(self._btn_clear)
        self._apply_selection_style()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._viewport:
            return super().eventFilter(obj, event)

        et = event.type()
        if et == QEvent.Type.MouseMove:
            me = event
            assert isinstance(me, QMouseEvent)
            idx = self._hit_highlight_index_at(me.position().x(), me.position().y())
            if idx != self._hover_highlight_idx:
                self._hover_highlight_idx = idx
                self._rect_overlay.update()
            if idx is not None:
                self._viewport.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self._viewport.setCursor(Qt.CursorShape.ArrowCursor)
            return False

        if et == QEvent.Type.Leave:
            if self._hover_highlight_idx is not None:
                self._hover_highlight_idx = None
                self._rect_overlay.update()
            self._viewport.setCursor(Qt.CursorShape.ArrowCursor)
            return False

        if et == QEvent.Type.MouseButtonPress:
            me = event
            assert isinstance(me, QMouseEvent)
            if me.button() == Qt.MouseButton.LeftButton:
                idx = self._hit_highlight_index_at(me.position().x(), me.position().y())
                if idx is not None:
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                    self.activated.emit()
                    self.diff_highlight_pair_clicked.emit(idx)
                    return True
            return False

        return super().eventFilter(obj, event)

    def _hit_highlight_index_at(self, vx: float, vy: float) -> int | None:
        if not self._highlight_rects or not self._viewport.has_pixmap():
            return None
        m = _HIT_MARGIN_PX
        for i in range(len(self._highlight_rects) - 1, -1, -1):
            x, y, w, h = self._highlight_rects[i]
            rx, ry, rw, rh = self._viewport.image_rect_to_viewport_rectf(x, y, w, h)
            rx -= m
            ry -= m
            rw += 2 * m
            rh += 2 * m
            if rx <= vx <= rx + rw and ry <= vy <= ry + rh:
                return i
        return None

    def _mk_tool_btn(self, theme_name: str, fallback: QStyle.StandardPixmap) -> QToolButton:
        b = QToolButton(self._overlay)
        b.setAutoRaise(True)
        b.setIcon(self._themed_icon(theme_name, fallback))
        b.setIconSize(QSize(22, 22))
        b.setFixedSize(34, 34)
        return b

    def _themed_icon(self, theme_name: str, fallback: QStyle.StandardPixmap) -> QIcon:
        ic = QIcon.fromTheme(theme_name)
        if not ic.isNull():
            return ic
        return self.style().standardIcon(fallback)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_selection_style()

    def _apply_selection_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                "PasteImagePanel { border: 2px solid #3b7ddd; border-radius: 4px; }"
            )
        else:
            self.setStyleSheet("PasteImagePanel { border: 1px solid #bbb; border-radius: 4px; }")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._viewport.setGeometry(self.rect())
        self._rect_overlay.setGeometry(0, 0, self._viewport.width(), self._viewport.height())
        self._overlay.adjustSize()
        m = 8
        x = self.width() - self._overlay.width() - m
        y = self.height() - self._overlay.height() - m
        self._overlay.move(max(m, x), max(m, y))
        self._rect_overlay.raise_()
        if self._overlay.isVisible():
            self._overlay.raise_()
        super().resizeEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._overlay.show()
        self._overlay.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        p = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(p):
            self._overlay.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.activated.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                p = Path(u.toLocalFile())
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        for u in event.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
                self.file_dropped.emit(str(p))
                event.acceptProposedAction()
                return
        event.ignore()

    def set_highlight_rects(
        self, rects: list[tuple[int, int, int, int]] | None
    ) -> None:
        self._highlight_rects = list(rects) if rects else []
        self._hover_highlight_idx = None
        if self._highlight_rects and self._viewport.has_pixmap():
            self._rect_overlay.show()
        else:
            self._rect_overlay.hide()
        self._rect_overlay.update()

    def set_numpy_bgr(self, arr: np.ndarray | None) -> None:
        from services import image_ops

        if arr is None:
            self._highlight_rects = []
            self._hover_highlight_idx = None
            self._rect_overlay.hide()
            self._last_wh = None
            self._viewport.set_pixmap(None, True, None)
            return
        pm = image_ops.bgr_to_qpixmap(arr)
        wh = (pm.width(), pm.height())
        reset = self._last_wh != wh
        self._last_wh = wh
        self._viewport.set_pixmap(pm, reset, None)
        self._rect_overlay.update()
