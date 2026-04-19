import sys

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

from bootstrap import run_app


def _apply_fusion_light_theme(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    c = QPalette.ColorRole
    pal.setColor(c.Window, QColor(239, 239, 239))
    pal.setColor(c.WindowText, QColor(0, 0, 0))
    pal.setColor(c.Base, QColor(255, 255, 255))
    pal.setColor(c.AlternateBase, QColor(233, 233, 233))
    pal.setColor(c.Text, QColor(0, 0, 0))
    pal.setColor(c.Button, QColor(239, 239, 239))
    pal.setColor(c.ButtonText, QColor(0, 0, 0))
    pal.setColor(c.Highlight, QColor(66, 133, 244))
    pal.setColor(c.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)


def main() -> int:
    app = QApplication(sys.argv)
    _apply_fusion_light_theme(app)
    _win, _handler = run_app(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
