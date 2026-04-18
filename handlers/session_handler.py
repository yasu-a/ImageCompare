from collections.abc import Callable

from PyQt6.QtCore import QEvent, QObject, Qt, QModelIndex
from PyQt6.QtWidgets import QInputDialog

from application.session_application_service import SessionApplicationService
from navigators.main_navigator import MainNavigator
from views.session_toolbar import SessionToolbar


class _ComboDblClickRenameFilter(QObject):
    def __init__(self, combo: QObject, rename_row: Callable[[int], None]) -> None:
        super().__init__(combo)
        self._combo = combo
        self._rename_row = rename_row

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if obj is self._combo and event.type() == QEvent.Type.MouseButtonDblClick:
            idx = self._combo.currentIndex()  # type: ignore[attr-defined]
            if idx >= 0:
                self._rename_row(idx)
                return True
        return False


class SessionHandler:
    def __init__(
        self,
        toolbar: SessionToolbar,
        session_svc: SessionApplicationService,
        navigator: MainNavigator,
        on_session_changed: Callable[[], None],
        refresh: Callable[[], None],
    ) -> None:
        self._tb = toolbar
        self._session_svc = session_svc
        self._nav = navigator
        self._on_session_changed = on_session_changed
        self._refresh = refresh
        self._combo_dbl_filter = _ComboDblClickRenameFilter(
            self._tb.session_combo, self._rename_session_row
        )

    def bind(self) -> None:
        self._tb.add_button.clicked.connect(self._on_add)
        self._tb.delete_button.clicked.connect(self._on_delete)
        self._tb.session_combo.currentIndexChanged.connect(self._on_combo_index)
        self._tb.session_combo.view().doubleClicked.connect(self._on_session_rename)
        self._tb.session_combo.installEventFilter(self._combo_dbl_filter)

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

    def _on_combo_index(self, idx: int) -> None:
        if idx < 0:
            return
        sid = self._tb.session_combo.itemData(idx, Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        self._session_svc.set_current(str(sid))
        self._on_session_changed()
        self._refresh()

    def _on_session_rename(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        self._rename_session_row(index.row())

    def _rename_session_row(self, row: int) -> None:
        if row < 0 or row >= self._tb.session_combo.count():
            return
        sid = self._tb.session_combo.itemData(row, Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        cur = self._tb.session_combo.itemText(row)
        text, ok = QInputDialog.getText(self._tb, "セッション名", "新しい名前:", text=cur)
        if not ok or not text.strip():
            return
        self._session_svc.rename_session(str(sid), text.strip())
        self._refresh()
