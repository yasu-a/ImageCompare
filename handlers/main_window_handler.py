import cv2
import numpy as np
from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QListWidgetItem

from application.comparison_application_service import ComparisonApplicationService
from application.session_application_service import SessionApplicationService
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
        self._diff_highlight_pairs: list[
            tuple[tuple[int, int, int, int], tuple[int, int, int, int]]
        ] = []

        self._session_h = SessionHandler(
            window.session_list_panel,
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
        )
        self._preview_h = PreviewHandler(
            window.preview_panel,
            comparison_svc,
            self.refresh_all,
        )

    def wire(self) -> None:
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
        self._win.base_panel.diff_highlight_pair_clicked.connect(
            self._on_diff_highlight_pair_clicked
        )
        self._win.variant_panel.diff_highlight_pair_clicked.connect(
            self._on_diff_highlight_pair_clicked
        )

        self._shortcut_paste = QShortcut(QKeySequence.StandardKey.Paste, self._win)
        self._shortcut_paste.activated.connect(self._on_shortcut_paste)
        self._shortcut_undo = QShortcut(QKeySequence.StandardKey.Undo, self._win)
        self._shortcut_undo.activated.connect(self._on_shortcut_undo)
        self._shortcut_delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self._win)
        self._shortcut_delete.activated.connect(self._on_shortcut_delete)

        self._win.diff_group_slider.valueChanged.connect(self._on_diff_group_radius_changed)

        self._win.session_list_panel.collapse_button.clicked.connect(
            self._toggle_session_section
        )
        self._win.preview_collapse_button().clicked.connect(self._toggle_preview_section)

    def _toggle_session_section(self) -> None:
        """横3分割の左列（セッション）を狭くする。"""
        ms = self._win.main_split()
        p = self._win.session_list_panel
        new_collapsed = not p.is_section_collapsed()
        sizes = ms.sizes()
        if len(sizes) == 3 and new_collapsed:
            self._win._triple_split_session_backup = list(sizes)
        p.set_section_collapsed(new_collapsed)
        self._win.session_section_collapsed = new_collapsed
        if len(sizes) != 3:
            return
        if new_collapsed:
            w0, w1, w2 = sizes
            target = p.collapsed_column_outer_width()
            if w0 < target:
                need = target - w0
                den = w1 + w2
                if den > 0:
                    t1 = int(need * w1 / den)
                    t2 = need - t1
                    w1 -= t1
                    w2 -= t2
                w0 = target
                ms.setSizes([w0, w1, w2])
                return
            extra = w0 - target
            den = w1 + w2
            if den > 0:
                add1 = int(extra * w1 / den)
                add2 = extra - add1
            else:
                add1 = add2 = 0
            ms.setSizes([target, w1 + add1, w2 + add2])
        else:
            if self._win._triple_split_session_backup is not None:
                ms.setSizes(self._win._triple_split_session_backup)
                self._win._triple_split_session_backup = None

    def _toggle_preview_section(self) -> None:
        """横3分割の右列（プレビュー）を狭くする。"""
        ms = self._win.main_split()
        new_c = not self._win.preview_section_collapsed
        sizes = ms.sizes()
        if len(sizes) == 3 and new_c:
            self._win._triple_split_preview_backup = list(sizes)
        self._win.set_preview_section_collapsed(new_c)
        if len(sizes) != 3:
            return
        if new_c:
            w0, w1, w2 = sizes
            target = self._win.preview_collapsed_column_outer_width()
            if w2 < target:
                need = target - w2
                den = w0 + w1
                if den > 0:
                    t0 = int(need * w0 / den)
                    t1 = need - t0
                    w0 -= t0
                    w1 -= t1
                w2 = target
                ms.setSizes([w0, w1, w2])
                return
            extra = w2 - target
            den = w0 + w1
            if den > 0:
                add0 = int(extra * w0 / den)
                add1 = extra - add0
            else:
                add0 = add1 = 0
            ms.setSizes([w0 + add0, w1 + add1, target])
        else:
            if self._win._triple_split_preview_backup is not None:
                ms.setSizes(self._win._triple_split_preview_backup)
                self._win._triple_split_preview_backup = None

    def _on_diff_group_radius_changed(self, v: int) -> None:
        self._win.diff_group_value_label.setText(f"{v} px")
        self._comparison.set_diff_group_radius_px(v)
        self._update_diff_highlights()

    def _update_diff_highlights(self) -> None:
        sess = self._session_svc.current_session()
        st = self._comparison.state()
        if (
            sess is None
            or sess.base_image_bgr is None
            or st.best_match_xy is None
            or st.selected_variant_id is None
        ):
            self._diff_highlight_pairs = []
            self._win.base_panel.set_highlight_rects(None)
            self._win.variant_panel.set_highlight_rects(None)
            return
        v = sess.find_variant(st.selected_variant_id)
        if v is None or not v.has_image():
            self._diff_highlight_pairs = []
            self._win.base_panel.set_highlight_rects(None)
            self._win.variant_panel.set_highlight_rects(None)
            return
        pairs = self._comparison.diff_highlight_pairs()
        self._diff_highlight_pairs = pairs
        if not pairs:
            self._win.base_panel.set_highlight_rects(None)
            self._win.variant_panel.set_highlight_rects(None)
            return
        self._win.base_panel.set_highlight_rects([p[0] for p in pairs])
        self._win.variant_panel.set_highlight_rects([p[1] for p in pairs])

    def _on_diff_highlight_pair_clicked(self, index: int) -> None:
        if index < 0 or index >= len(self._diff_highlight_pairs):
            self._toast("この差分領域は比較表示できません。", error=True)
            return
        sess = self._session_svc.current_session()
        if sess is None or sess.base_image_bgr is None:
            self._toast("基準画像がありません。", error=True)
            return
        vid = self._comparison.state().selected_variant_id
        if vid is None:
            self._toast("比較スロットを選んでください。", error=True)
            return
        var = sess.find_variant(vid)
        if var is None or not var.has_image():
            self._toast("比較画像がありません。", error=True)
            return
        br, vr = self._diff_highlight_pairs[index]
        base_crop = image_ops.crop_bgr_xywh(sess.base_image_bgr, br)
        var_crop = image_ops.crop_bgr_xywh(var.image_bgr, vr)
        if base_crop.size == 0 or var_crop.size == 0:
            self._toast("この差分領域は比較表示できません。", error=True)
            return
        from views.diff_region_compare_dialog import DiffRegionCompareDialog

        dlg = DiffRegionCompareDialog(self._win, base_crop, var_crop)
        dlg.exec()

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

    def _require_session(self) -> bool:
        if self._session_svc.current_session() is None:
            self._toast(
                "先にセッション一覧の追加で作成するか、一覧から選んでください。",
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

    def refresh_all(self) -> None:
        lw = self._win.session_list_panel.session_list
        lw.blockSignals(True)
        lw.clear()
        cur_sid = self._session_svc.current_session_id
        for sess in self._session_svc.all_sessions_ordered():
            it = QListWidgetItem(sess.display_name)
            it.setData(Qt.ItemDataRole.UserRole, sess.session_id)
            lw.addItem(it)
        if cur_sid:
            for i in range(lw.count()):
                item = lw.item(i)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == cur_sid:
                    lw.setCurrentRow(i)
                    break
            else:
                lw.setCurrentRow(-1)
        else:
            lw.setCurrentRow(-1)
        lw.blockSignals(False)

        sess = self._session_svc.current_session()
        self._win.session_list_panel.delete_button.setEnabled(sess is not None)
        self._prune_variant_undo(sess)
        st = self._comparison.state()
        has_sess = sess is not None
        self._win.variant_toolbar.setEnabled(has_sess)
        self._win.base_panel.setEnabled(has_sess)
        self._win.variant_panel.setEnabled(has_sess)
        can_highlight = has_sess and st.best_match_xy is not None
        self._win.diff_group_slider.setEnabled(can_highlight)

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

        arr, msg, fit_rect = self._comparison.preview_tuple()
        if arr is not None:
            pm = image_ops.bgr_to_qpixmap(arr)
            self._win.preview_panel.set_preview(pm, msg, fit_rect)
        else:
            self._win.preview_panel.set_preview(None, msg, None)

        sl = self._win.diff_group_slider
        sl.blockSignals(True)
        sl.setValue(st.diff_group_radius_px)
        sl.blockSignals(False)
        self._win.diff_group_value_label.setText(f"{sl.value()} px")

        self._update_diff_highlights()

        self._sync_panel_selection()
