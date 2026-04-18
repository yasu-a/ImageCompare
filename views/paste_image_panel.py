from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRect, QRectF, QSize, Qt, pyqtSignal
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
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QWidget,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


class _RectHighlightOverlay(QWidget):
    """画像上に差分グループの赤枠のみ描画。マウスは下へ透過。"""

    def __init__(self, panel: "PasteImagePanel") -> None:
        super().__init__(panel)
        self._panel = panel
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        rects = self._panel._highlight_rects
        if not rects or self._panel._full_pixmap.isNull():
            return
        iw = self._panel._full_pixmap.width()
        ih = self._panel._full_pixmap.height()
        if iw < 1 or ih < 1:
            return
        dr = self._panel._scaled_pixmap_draw_rect()
        if dr.width() < 1 or dr.height() < 1:
            return
        s = min(dr.width() / float(iw), dr.height() / float(ih))
        ox = dr.x() + 0.5 * (dr.width() - iw * s)
        oy = dr.y() + 0.5 * (dr.height() - ih * s)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(2)
        pen.setCosmetic(True)
        p.setPen(pen)
        for x, y, w, h in rects:
            rf = QRectF(ox + x * s, oy + y * s, w * s, h * s)
            p.drawRect(rf)
        p.end()


class PasteImagePanel(QWidget):
    """選択後に Ctrl+V / ツールバーで貼付。D&D対応。ホバーで操作ボタン。"""

    activated = pyqtSignal()
    paste_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    file_dropped = pyqtSignal(str)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected = False
        self._label = QLabel(placeholder, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setScaledContents(False)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._label.setMinimumHeight(120)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._placeholder = placeholder
        self._full_pixmap = QPixmap()
        self._highlight_rects: list[tuple[int, int, int, int]] = []
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._rect_overlay = _RectHighlightOverlay(self)
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

    def label(self) -> QLabel:
        return self._label

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

    def _scaled_pixmap_draw_rect(self) -> QRect:
        if self._full_pixmap.isNull():
            return QRect()
        iw = self._full_pixmap.width()
        ih = self._full_pixmap.height()
        lw, lh = self.width(), self.height()
        scaled = QSize(iw, ih).scaled(
            lw, lh, Qt.AspectRatioMode.KeepAspectRatio
        )
        sw, sh = scaled.width(), scaled.height()
        ox = (lw - sw) // 2
        oy = (lh - sh) // 2
        return QRect(ox, oy, sw, sh)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._label.setGeometry(self.rect())
        self._rect_overlay.setGeometry(self.rect())
        self._apply_scaled_pixmap()
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

    def _apply_scaled_pixmap(self) -> None:
        if self._full_pixmap.isNull():
            self._label.setPixmap(QPixmap())
            self._label.setText(self._placeholder)
            return
        target = self._label.size()
        if target.width() < 2 or target.height() < 2:
            return
        scaled = self._full_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._label.setText("")
        self._rect_overlay.update()

    def set_highlight_rects(
        self, rects: list[tuple[int, int, int, int]] | None
    ) -> None:
        self._highlight_rects = list(rects) if rects else []
        if self._highlight_rects and not self._full_pixmap.isNull():
            self._rect_overlay.show()
        else:
            self._rect_overlay.hide()
        self._rect_overlay.update()

    def set_numpy_bgr(self, arr: np.ndarray | None) -> None:
        from services import image_ops

        if arr is None:
            self._full_pixmap = QPixmap()
            self._highlight_rects = []
            self._rect_overlay.hide()
            self._label.setPixmap(QPixmap())
            self._label.setText(self._placeholder)
            return
        self._full_pixmap = image_ops.bgr_to_qpixmap(arr)
        self._apply_scaled_pixmap()
