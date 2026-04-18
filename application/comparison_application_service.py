import numpy as np

from application.session_application_service import SessionApplicationService
from domain.comparison_state import ComparisonState
from services import image_ops


class ComparisonApplicationService:
    def __init__(
        self,
        sessions: SessionApplicationService,
        state: ComparisonState,
    ) -> None:
        self._sessions = sessions
        self._state = state

    def state(self) -> ComparisonState:
        return self._state

    def reset_for_session_switch(self) -> None:
        sess = self._sessions.current_session()
        if sess is None or not sess.variants:
            self._state.selected_variant_id = None
        else:
            self._state.selected_variant_id = sess.variants[0].variant_id
        self._state.manual_offset_xy = (0, 0)
        self._state.best_match_xy = None
        self._state.last_match_message = ""
        self.recompute_match()

    def set_selected_variant(self, variant_id: str | None) -> None:
        self._state.selected_variant_id = variant_id
        self._state.manual_offset_xy = (0, 0)
        self.recompute_match()

    def nudge_offset(self, dx: int, dy: int) -> None:
        self._state.nudge(dx, dy)

    def reset_offset(self) -> None:
        if self._state.best_match_xy is None:
            return
        self._state.reset_offset_to_best()

    def set_diff_group_radius_px(self, radius_px: int) -> None:
        r = int(radius_px)
        r = max(image_ops.DIFF_GROUP_RADIUS_MIN, min(image_ops.DIFF_GROUP_RADIUS_MAX, r))
        self._state.diff_group_radius_px = r

    def diff_highlight_rects(
        self,
    ) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
        """基準・比較それぞれの画像座標での差分グループ矩形 (x, y, w, h)。"""
        sess = self._sessions.current_session()
        if sess is None or sess.base_image_bgr is None:
            return [], []
        vid = self._state.selected_variant_id
        if vid is None:
            return [], []
        v = sess.find_variant(vid)
        if v is None or not v.has_image():
            return [], []
        if self._state.best_match_xy is None:
            return [], []
        return image_ops.diff_group_rects_native(
            sess.base_image_bgr,
            v.image_bgr,
            self._state.best_match_xy,
            self._state.manual_offset_xy,
            self._state.diff_group_radius_px,
        )

    def recompute_match(self) -> None:
        sess = self._sessions.current_session()
        if sess is None or sess.base_image_bgr is None:
            self._state.best_match_xy = None
            self._state.last_match_message = ""
            return
        vid = self._state.selected_variant_id
        if vid is None:
            self._state.best_match_xy = None
            self._state.last_match_message = ""
            return
        v = sess.find_variant(vid)
        if v is None or not v.has_image():
            self._state.best_match_xy = None
            self._state.last_match_message = ""
            return
        res = image_ops.match_template_full(sess.base_image_bgr, v.image_bgr)
        if res.ok and res.best_xy is not None:
            self._state.best_match_xy = res.best_xy
            self._state.manual_offset_xy = (0, 0)
            self._state.last_match_message = ""
        else:
            self._state.best_match_xy = None
            self._state.last_match_message = res.message or image_ops.MATCH_ADJUST_USER_MESSAGE

    def preview_tuple(self) -> tuple[np.ndarray | None, str]:
        """合成結果 BGR とメッセージ。画像が無い場合は (None, メッセージ)。"""
        sess = self._sessions.current_session()
        if sess is None:
            return None, "セッションを作成してください。"
        if sess.base_image_bgr is None:
            return None, "基準画像を貼り付けてください。"
        vid = self._state.selected_variant_id
        if vid is None:
            return None, "比較画像スロットを追加してください。"
        v = sess.find_variant(vid)
        if v is None or not v.has_image():
            return None, "比較画像を貼り付けてください。"
        if self._state.best_match_xy is None:
            pad = image_ops.pad_base(sess.base_image_bgr)
            return pad, self._state.last_match_message or image_ops.MATCH_ADJUST_USER_MESSAGE
        best = self._state.best_match_xy
        out, msg = image_ops.render_preview(
            sess.base_image_bgr,
            v.image_bgr,
            best,
            self._state.manual_offset_xy,
        )
        return out, msg
