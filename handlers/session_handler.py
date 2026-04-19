from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QInputDialog, QListWidgetItem

from application.session_application_service import SessionApplicationService
from navigators.main_navigator import MainNavigator
from views.session_list_panel import SessionListPanel


class SessionHandler:
    def __init__(
        self,
        panel: SessionListPanel,
        session_svc: SessionApplicationService,
        navigator: MainNavigator,
        on_session_changed: Callable[[], None],
        refresh: Callable[[], None],
    ) -> None:
        self._tb = panel
        self._session_svc = session_svc
        self._nav = navigator
        self._on_session_changed = on_session_changed
        self._refresh = refresh

    def bind(self) -> None:
        self._tb.add_button.clicked.connect(self._on_add)
        self._tb.delete_button.clicked.connect(self._on_delete)
        self._tb.session_list.currentRowChanged.connect(self._on_list_row)
        self._tb.session_list.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_add(self) -> None:
        self._session_svc.create_session()
        self._on_session_changed()
        self._refresh()

    def _on_delete(self) -> None:
        if self._session_svc.current_session() is None:
            return
        if not self._nav.confirm_delete_session(self._tb):
            return
        self._session_svc.delete_current_session()
        self._on_session_changed()
        self._refresh()

    def _on_list_row(self, row: int) -> None:
        if row < 0:
            return
        item = self._tb.session_list.item(row)
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        self._session_svc.set_current(str(sid))
        self._on_session_changed()
        self._refresh()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        row = self._tb.session_list.row(item)
        if row >= 0:
            self._rename_session_row(row)

    def _rename_session_row(self, row: int) -> None:
        if row < 0 or row >= self._tb.session_list.count():
            return
        it = self._tb.session_list.item(row)
        if it is None:
            return
        sid = it.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        cur = it.text()
        text, ok = QInputDialog.getText(self._tb, "セッション名", "新しい名前:", text=cur)
        if not ok or not text.strip():
            return
        self._session_svc.rename_session(str(sid), text.strip())
        self._refresh()
