from collections.abc import Callable

from application.comparison_application_service import ComparisonApplicationService
from views.composite_preview_panel import CompositePreviewPanel


class PreviewHandler:
    def __init__(
        self,
        panel: CompositePreviewPanel,
        comparison_svc: ComparisonApplicationService,
        refresh: Callable[[], None],
    ) -> None:
        self._panel = panel
        self._comparison = comparison_svc
        self._refresh = refresh

    def bind(self) -> None:
        self._panel.nudge.connect(self._on_nudge)
        self._panel.reset_requested.connect(self._on_reset)

    def _on_nudge(self, dx: int, dy: int) -> None:
        self._comparison.nudge_offset(dx, dy)
        self._refresh()

    def _on_reset(self) -> None:
        self._comparison.reset_offset()
        self._refresh()
        self._panel.reset_view()
