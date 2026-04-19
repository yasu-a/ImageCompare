"""差分矩形ペアを上下に並べて拡大・パン・Space リセットで閲覧するモーダル。"""

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services import image_ops
from views.zoom_pan_image_viewport import ZoomPanImageViewport

_HINT = (
    "Ctrl+ホイールで拡大縮小 / 左ドラッグで移動 / Spaceで表示をリセット。"
    "上下の表示は連動します。"
)


class DiffRegionCompareDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        base_crop_bgr: np.ndarray,
        variant_crop_bgr: np.ndarray,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("差分領域の比較")
        self.resize(1200, 720)
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        lb0 = QLabel("基準画像（該当部分）")
        lb0.setStyleSheet("font-weight: bold;")
        root.addWidget(lb0)
        self._vp_base = ZoomPanImageViewport(
            self, empty_hint="", draw_viewport_border=True
        )
        self._vp_base.setMinimumHeight(200)
        self._vp_base.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._vp_base, stretch=1)

        lb1 = QLabel("比較画像（該当部分）")
        lb1.setStyleSheet("font-weight: bold;")
        root.addWidget(lb1)
        self._vp_variant = ZoomPanImageViewport(
            self, empty_hint="", draw_viewport_border=True
        )
        self._vp_variant.setMinimumHeight(200)
        self._vp_variant.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._vp_variant, stretch=1)

        hint = QLabel(_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")
        root.addWidget(hint)

        pm_b = image_ops.bgr_to_qpixmap(base_crop_bgr)
        pm_v = image_ops.bgr_to_qpixmap(variant_crop_bgr)
        self._vp_base.set_pixmap(pm_b, True, None)
        self._vp_variant.set_pixmap(pm_v, True, None)

        self._vp_base.transform_changed.connect(self._sync_base_to_variant)
        self._vp_variant.transform_changed.connect(self._sync_variant_to_base)

        # レイアウト確定後に基準ビューの実スケール・中心で比較側を揃える（画像サイズ違いで fit だけ同期すると見かけがずれる）
        QTimer.singleShot(0, self._initial_align_linked_views)

    def _initial_align_linked_views(self) -> None:
        self._sync_base_to_variant()
        self._vp_base.setFocus(Qt.FocusReason.PopupFocusReason)

    def _sync_base_to_variant(self) -> None:
        if self._syncing:
            return
        st = self._vp_base.view_state()
        if st is None:
            return
        self._syncing = True
        try:
            self._vp_variant.apply_view_state(st)
        finally:
            self._syncing = False

    def _sync_variant_to_base(self) -> None:
        if self._syncing:
            return
        st = self._vp_variant.view_state()
        if st is None:
            return
        self._syncing = True
        try:
            self._vp_base.apply_view_state(st)
        finally:
            self._syncing = False
