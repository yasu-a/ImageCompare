from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QInputDialog

from application.comparison_application_service import ComparisonApplicationService
from application.session_application_service import SessionApplicationService
from views.variant_toolbar import VariantToolbar


class VariantHandler:
    def __init__(
        self,
        toolbar: VariantToolbar,
        session_svc: SessionApplicationService,
        comparison_svc: ComparisonApplicationService,
        refresh: Callable[[], None],
    ) -> None:
        self._tb = toolbar
        self._session_svc = session_svc
        self._comparison = comparison_svc
        self._refresh = refresh

    def bind(self) -> None:
        self._tb.add_button.clicked.connect(self._on_add)
        self._tb.delete_button.clicked.connect(self._on_delete)
        self._tb.rename_button.clicked.connect(self._on_rename_clicked)
        self._tb.variant_combo.currentIndexChanged.connect(self._on_combo_index)

    def _on_rename_clicked(self) -> None:
        row = self._tb.variant_combo.currentIndex()
        if row < 0:
            return
        self._rename_variant_row(row)

    def _on_add(self) -> None:
        if self._session_svc.current_session() is None:
            return
        vid = self._session_svc.add_variant_slot()
        if vid is None:
            return
        self._comparison.set_selected_variant(vid)
        self._refresh()

    def _on_delete(self) -> None:
        sess = self._session_svc.current_session()
        if sess is None:
            return
        idx = self._tb.variant_combo.currentIndex()
        if idx < 0:
            return
        vid = self._tb.variant_combo.itemData(idx, Qt.ItemDataRole.UserRole)
        if vid is None:
            return
        vid = str(vid)
        sel = self._comparison.state().selected_variant_id
        self._session_svc.remove_variant(vid)
        sess = self._session_svc.current_session()
        if sess is None:
            self._comparison.set_selected_variant(None)
            self._refresh()
            return
        ids = {v.variant_id for v in sess.variants}
        if sel == vid or (sel is not None and sel not in ids):
            if sess.variants:
                self._comparison.set_selected_variant(sess.variants[0].variant_id)
            else:
                self._comparison.set_selected_variant(None)
        self._refresh()

    def _on_combo_index(self, idx: int) -> None:
        if idx < 0:
            return
        vid = self._tb.variant_combo.itemData(idx, Qt.ItemDataRole.UserRole)
        if vid is None:
            return
        self._comparison.set_selected_variant(str(vid))
        self._refresh()

    def _rename_variant_row(self, row: int) -> None:
        if row < 0 or row >= self._tb.variant_combo.count():
            return
        vid = self._tb.variant_combo.itemData(row, Qt.ItemDataRole.UserRole)
        if vid is None:
            return
        cur = self._tb.variant_combo.itemText(row)
        text, ok = QInputDialog.getText(self._tb, "比較名", "新しい名前:", text=cur)
        if not ok or not text.strip():
            return
        self._session_svc.rename_variant(str(vid), text.strip())
        self._refresh()
