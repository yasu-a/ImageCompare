from dataclasses import dataclass


@dataclass
class ComparisonState:
    """ランタイムのみ保持する比較表示状態。"""

    selected_variant_id: str | None = None
    manual_offset_xy: tuple[int, int] = (0, 0)
    best_match_xy: tuple[int, int] | None = None
    last_match_message: str = ""
    # 差分グループ化用モルフォロジー半径（1〜50px）。セッション切替では維持、起動時のみ既定。
    diff_group_radius_px: int = 10

    def reset_offset_to_best(self) -> None:
        self.manual_offset_xy = (0, 0)

    def nudge(self, dx: int, dy: int) -> None:
        ox, oy = self.manual_offset_xy
        self.manual_offset_xy = (ox + dx, oy + dy)
