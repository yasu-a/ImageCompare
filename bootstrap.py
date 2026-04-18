from PyQt6.QtWidgets import QApplication

from application.comparison_application_service import ComparisonApplicationService
from application.session_application_service import SessionApplicationService
from domain.comparison_state import ComparisonState
from handlers.main_window_handler import MainWindowHandler
from navigators.main_navigator import MainNavigator
from repositories.session_repository import SessionRepository
from views.main_window import MainWindow


def run_app(app: QApplication) -> None:
    app.setApplicationName("ImageCompare")
    repo = SessionRepository()
    session_svc = SessionApplicationService(repo)
    session_svc.reload_from_disk()

    comparison_state = ComparisonState()
    comparison_svc = ComparisonApplicationService(session_svc, comparison_state)

    win = MainWindow()
    navigator = MainNavigator()
    handler = MainWindowHandler(win, session_svc, comparison_svc, navigator)
    handler.wire()
    handler.refresh_all()
    win.show()
