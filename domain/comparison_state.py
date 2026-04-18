from dataclasses import dataclass, field

from domain.render_mode import RenderMode


@dataclass
class ComparisonState:
    """ランタイムのみ保持する比較表示状態。"""

    selected_variant_id: str | None = None
    render_mode: RenderMode = field(default_factory=RenderMode.default)
    manual_offset_xy: tuple[int, int] = (0, 0)
    best_match_xy: tuple[int, int] | None = None
    last_match_message: str = ""

    def reset_offset_to_best(self) -> None:
        self.manual_offset_xy = (0, 0)

    def nudge(self, dx: int, dy: int) -> None:
        ox, oy = self.manual_offset_xy
        self.manual_offset_xy = (ox + dx, oy + dy)
