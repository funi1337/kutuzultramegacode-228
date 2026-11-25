"""
Киоск-браузер на PyQt6 с полноэкранным режимом.

Безопасная версия: без глобальной блокировки клавиш,
скрытой автозагрузки и отключения защитных механизмов WebEngine.

Установка:
    pip install PyQt6 PyQt6-WebEngine

Запуск:
    python my_browser_safe.py
"""

import sys

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

START_URL = "https://xn----9sbdghb3btcbbvi1a0db.xn--p1ai/"
FULLSCREEN = True
SAME_DOMAIN_ONLY = False
WINDOW_TITLE = "Мой браузер"


class Page(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if SAME_DOMAIN_ONLY and is_main_frame:
            if url.host() != QUrl(START_URL).host():
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, _window_type):
        temp = QWebEnginePage(self.profile(), self)

        def redirect(url):
            if url.isValid() and url.scheme() != "about":
                self.load(url)
                try:
                    temp.urlChanged.disconnect(redirect)
                except (TypeError, RuntimeError):
                    pass

        temp.urlChanged.connect(redirect)
        return temp


class Viewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1200, 800)

        self.view = QWebEngineView()
        self.view.setPage(Page(self.view))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.view.load(QUrl(START_URL))
        self.setCentralWidget(self.view)

        if FULLSCREEN:
            self.showFullScreen()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Viewer()
    if not FULLSCREEN:
        window.show()
    sys.exit(app.exec())
