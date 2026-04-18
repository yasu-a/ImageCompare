import cv2
import numpy as np
from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication

from application.comparison_application_service import ComparisonApplicationService
from application.session_application_service import SessionApplicationService
from domain.render_mode import RenderMode
from handlers.preview_handler import PreviewHandler
from handlers.session_handler import SessionHandler
from handlers.variant_handler import VariantHandler
from navigators.main_navigator import MainNavigator
from services import image_ops
from views.main_window import MainWindow

_ActiveSlot = Literal["base", "variant"] | None


class MainWindowHandler:
    def __init__(
        self,
        window: MainWindow,
        session_svc: SessionApplicationService,
        comparison_svc: ComparisonApplicationService,
        navigator: MainNavigator,
    ) -> None:
        self._win = window
        self._session_svc = session_svc
        self._comparison = comparison_svc
        self._nav = navigator

        self._active_slot: _ActiveSlot = None
        self._base_undo_has = False
        self._base_undo_prev: np.ndarray | None = None
        self._variant_undo: dict[str, np.ndarray | None] = {}

        self._session_h = SessionHandler(
            window.session_toolbar,
            session_svc,
            navigator,
            self._on_session_changed,
            self.refresh_all,
        )
        self._variant_h = VariantHandler(
            window.variant_toolbar,
            session_svc,
            comparison_svc,
            self.refresh_all,
            on_clear_clicked=self._toolbar_clear_variant,
        )
        self._preview_h = PreviewHandler(
            window.preview_panel,
            comparison_svc,
            self.refresh_all,
        )

    def wire(self) -> None:
        for rm in RenderMode:
            self._win.render_mode_combo.addItem(rm.label_ja(), rm)
        self._win.render_mode_combo.currentIndexChanged.connect(self._on_render_mode)

        self._session_h.bind()
        self._variant_h.bind()
        self._preview_h.bind()

        self._win.base_panel.activated.connect(self._on_base_activated)
        self._win.variant_panel.activated.connect(self._on_variant_activated)
        self._win.base_panel.paste_requested.connect(self._paste_base_clipboard)
        self._win.base_panel.undo_requested.connect(self._undo_base)
        self._win.base_panel.clear_requested.connect(self._clear_base)
        self._win.variant_panel.paste_requested.connect(self._paste_variant_clipboard)
        self._win.variant_panel.undo_requested.connect(self._undo_variant)
        self._win.variant_panel.clear_requested.connect(self._clear_variant)
        self._win.base_panel.file_dropped.connect(self._paste_base_file)
        self._win.variant_panel.file_dropped.connect(self._paste_variant_file)

        self._shortcut_paste = QShortcut(QKeySequence.StandardKey.Paste, self._win)
        self._shortcut_paste.activated.connect(self._on_shortcut_paste)
        self._shortcut_undo = QShortcut(QKeySequence.StandardKey.Undo, self._win)
        self._shortcut_undo.activated.connect(self._on_shortcut_undo)
        self._shortcut_delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self._win)
        self._shortcut_delete.activated.connect(self._on_shortcut_delete)

    def _toast(self, message: str, *, error: bool = False) -> None:
        sb = self._win.statusBar()
        if error:
            sb.setStyleSheet(
                "QStatusBar { background-color: rgb(255, 220, 220); padding: 2px 8px; }"
            )
        else:
            sb.setStyleSheet(
                "QStatusBar { background-color: rgb(236, 236, 236); padding: 2px 8px; }"
            )
        sb.showMessage(message, 4500)

    def _on_base_activated(self) -> None:
        self._active_slot = "base"
        self._sync_panel_selection()

    def _on_variant_activated(self) -> None:
        self._active_slot = "variant"
        self._sync_panel_selection()

    def _sync_panel_selection(self) -> None:
        has = self._session_svc.current_session() is not None
        self._win.base_panel.set_selected(has and self._active_slot == "base")
        self._win.variant_panel.set_selected(has and self._active_slot == "variant")

    def _clear_undo_memory(self) -> None:
        self._base_undo_has = False
        self._base_undo_prev = None
        self._variant_undo.clear()

    def _on_session_changed(self) -> None:
        self._clear_undo_memory()
        self._active_slot = None
        self._comparison.reset_for_session_switch()

    def _on_render_mode(self, idx: int) -> None:
        if idx < 0:
            return
        m = self._win.render_mode_combo.itemData(idx, Qt.ItemDataRole.UserRole)
        if isinstance(m, RenderMode):
            self._comparison.set_render_mode(m)
            self.refresh_all()

    def _require_session(self) -> bool:
        if self._session_svc.current_session() is None:
            self._toast(
                "先にセッションの「+」で作成するか、一覧から選んでください。",
                error=True,
            )
            return False
        return True

    def _read_clipboard_bgr(self) -> np.ndarray | None:
        img = QApplication.clipboard().image()
        if img.isNull():
            return None
        return image_ops.qimage_to_bgr(QImage(img))

    def _read_file_bgr(self, path: str) -> np.ndarray | None:
        raw = np.fromfile(path, dtype=np.uint8)
        im = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        return im

    def _prune_variant_undo(self, sess) -> None:
        if sess is None:
            self._variant_undo.clear()
            return
        ids = {v.variant_id for v in sess.variants}
        for k in list(self._variant_undo.keys()):
            if k not in ids:
                del self._variant_undo[k]

    def _apply_base(self, new_bgr: np.ndarray | None, *, record_undo: bool) -> bool:
        if not self._require_session():
            return False
        sess = self._session_svc.current_session()
        assert sess is not None
        cur = sess.base_image_bgr
        if image_ops.bgr_equal(cur, new_bgr):
            self._toast("画像は変更されていません。")
            return False
        if record_undo:
            self._base_undo_prev = None if cur is None else cur.copy()
            self._base_undo_has = True
        self._session_svc.set_base_bgr(new_bgr)
        self._comparison.recompute_match()
        self.refresh_all()
        return True

    def _undo_base(self) -> None:
        if not self._require_session():
            return
        if not self._base_undo_has:
            self._toast("これ以上戻せません。", error=True)
            return
        prev = self._base_undo_prev
        self._base_undo_has = False
        self._base_undo_prev = None
        restored = None if prev is None else np.copy(prev)
        self._session_svc.set_base_bgr(restored)
        self._comparison.recompute_match()
        self.refresh_all()

    def _apply_variant_bgr(
        self, variant_id: str, new_bgr: np.ndarray | None, *, record_undo: bool
    ) -> bool:
        if not self._require_session():
            return False
        sess = self._session_svc.current_session()
        assert sess is not None
        v = sess.find_variant(variant_id)
        if v is None:
            self._toast("比較スロットが見つかりません。", error=True)
            return False
        cur = v.image_bgr
        if image_ops.bgr_equal(cur, new_bgr):
            self._toast("画像は変更されていません。")
            return False
        if record_undo:
            self._variant_undo[variant_id] = None if cur is None else cur.copy()
        self._session_svc.set_variant_bgr(variant_id, new_bgr)
        self._comparison.recompute_match()
        self.refresh_all()
        return True

    def _undo_variant(self) -> None:
        if not self._require_session():
            return
        vid = self._comparison.state().selected_variant_id
        if vid is None:
            self._toast("比較スロットを選んでください。", error=True)
            return
        if vid not in self._variant_undo:
            self._toast("これ以上戻せません。", error=True)
            return
        prev = self._variant_undo.pop(vid)
        restored = None if prev is None else np.copy(prev)
        self._session_svc.set_variant_bgr(vid, restored)
        self._comparison.recompute_match()
        self.refresh_all()

    def _on_shortcut_paste(self) -> None:
        if self._active_slot == "base":
            self._paste_base_clipboard()
        elif self._active_slot == "variant":
            self._paste_variant_clipboard()
        else:
            self._toast("基準または比較の画像エリアをクリックして選択してください。", error=True)

    def _on_shortcut_undo(self) -> None:
        if self._active_slot == "base":
            self._undo_base()
        elif self._active_slot == "variant":
            self._undo_variant()
        else:
            self._toast("画像エリアを選択してください。", error=True)

    def _on_shortcut_delete(self) -> None:
        if self._active_slot == "base":
            self._clear_base()
        elif self._active_slot == "variant":
            self._clear_variant()
        else:
            self._toast("画像エリアを選択してください。", error=True)

    def _paste_base_clipboard(self) -> None:
        if not self._require_session():
            return
        bgr = self._read_clipboard_bgr()
        if bgr is None:
            self._toast("クリップボードに画像がありません。", error=True)
            return
        self._apply_base(bgr, record_undo=True)

    def _paste_base_file(self, path: str) -> None:
        if not self._require_session():
            return
        im = self._read_file_bgr(path)
        if im is None:
            self._toast("画像として読み込めませんでした。", error=True)
            return
        self._apply_base(im, record_undo=True)

    def _clear_base(self) -> None:
        if not self._require_session():
            return
        self._apply_base(None, record_undo=True)

    def _ensure_variant_id(self) -> str | None:
        vid = self._comparison.state().selected_variant_id
        if vid is not None:
            return vid
        vid = self._session_svc.add_variant_slot()
        if vid is None:
            return None
        self._comparison.set_selected_variant(vid)
        return vid

    def _paste_variant_clipboard(self) -> None:
        if not self._require_session():
            return
        vid = self._ensure_variant_id()
        if vid is None:
            return
        bgr = self._read_clipboard_bgr()
        if bgr is None:
            self._toast("クリップボードに画像がありません。", error=True)
            return
        self._apply_variant_bgr(vid, bgr, record_undo=True)

    def _paste_variant_file(self, path: str) -> None:
        if not self._require_session():
            return
        vid = self._ensure_variant_id()
        if vid is None:
            return
        im = self._read_file_bgr(path)
        if im is None:
            self._toast("画像として読み込めませんでした。", error=True)
            return
        self._apply_variant_bgr(vid, im, record_undo=True)

    def _clear_variant(self) -> None:
        if not self._require_session():
            return
        vid = self._comparison.state().selected_variant_id
        if vid is None:
            self._toast("比較スロットを選ぶか、画像を貼り付けてください。", error=True)
            return
        self._apply_variant_bgr(vid, None, record_undo=True)

    def _toolbar_clear_variant(self) -> None:
        self._clear_variant()

    def refresh_all(self) -> None:
        scb = self._win.session_toolbar.session_combo
        scb.blockSignals(True)
        scb.clear()
        cur_sid = self._session_svc.current_session_id
        for sess in self._session_svc.all_sessions_ordered():
            scb.addItem(sess.display_name, sess.session_id)
        if cur_sid:
            for i in range(scb.count()):
                if scb.itemData(i, Qt.ItemDataRole.UserRole) == cur_sid:
                    scb.setCurrentIndex(i)
                    break
            else:
                scb.setCurrentIndex(-1)
        else:
            scb.setCurrentIndex(-1)
        scb.blockSignals(False)

        sess = self._session_svc.current_session()
        self._prune_variant_undo(sess)
        st = self._comparison.state()
        has_sess = sess is not None
        self._win.variant_toolbar.setEnabled(has_sess)
        self._win.base_panel.setEnabled(has_sess)
        self._win.variant_panel.setEnabled(has_sess)
        self._win.render_mode_combo.setEnabled(has_sess)

        vcb = self._win.variant_toolbar.variant_combo
        vcb.blockSignals(True)
        vcb.clear()
        if sess:
            for v in sess.variants:
                vcb.addItem(v.display_name, v.variant_id)
            if st.selected_variant_id:
                for i in range(vcb.count()):
                    if vcb.itemData(i, Qt.ItemDataRole.UserRole) == st.selected_variant_id:
                        vcb.setCurrentIndex(i)
                        break
                else:
                    if vcb.count() > 0:
                        vcb.setCurrentIndex(0)
                        self._comparison.set_selected_variant(
                            str(vcb.itemData(0, Qt.ItemDataRole.UserRole))
                        )
            elif vcb.count() > 0:
                vcb.setCurrentIndex(0)
                self._comparison.set_selected_variant(
                    str(vcb.itemData(0, Qt.ItemDataRole.UserRole))
                )
        vcb.blockSignals(False)

        if sess is None:
            self._win.base_panel.set_numpy_bgr(None)
            self._win.variant_panel.set_numpy_bgr(None)
        else:
            self._win.base_panel.set_numpy_bgr(sess.base_image_bgr)
            vid = self._comparison.state().selected_variant_id
            if vid:
                v = sess.find_variant(vid)
                self._win.variant_panel.set_numpy_bgr(
                    v.image_bgr if v is not None else None
                )
            else:
                self._win.variant_panel.set_numpy_bgr(None)

        rmc = self._win.render_mode_combo
        rmc.blockSignals(True)
        rm = st.render_mode
        for i in range(rmc.count()):
            m = rmc.itemData(i, Qt.ItemDataRole.UserRole)
            if m == rm:
                rmc.setCurrentIndex(i)
                break
        rmc.blockSignals(False)

        arr, msg = self._comparison.preview_tuple()
        if arr is not None:
            pm = image_ops.bgr_to_qpixmap(arr)
            self._win.preview_panel.set_preview(pm, msg)
        else:
            self._win.preview_panel.set_preview(None, msg)

        self._sync_panel_selection()
