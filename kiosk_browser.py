"""
Киоск-браузер на PyQt6. Без venv, с блокировкой клавиш через WinAPI.
"""
import os
import sys
import winreg
import ctypes
from ctypes import wintypes
import threading
import time

# --- ФИКСЫ ДЛЯ WEBENGINE ---
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-gpu "
    "--ignore-certificate-errors "
    "--allow-running-insecure-content "
    "--no-sandbox "
    "--disable-features=RendererCodeIntegrity "
)
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt6.QtCore import Qt, QUrl, QEvent
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

# ---------- настройки ----------
START_URL = "https://xn----9sbdghb3btcbbvi1a0db.xn--p1ai/"
FULLSCREEN = True
WINDOW_TITLE = "Мой браузер"
AUTOSTART = True
AUTOSTART_NAME = "MyKioskBrowser"
# --------------------------------

# =========================================================
# БЛОКИРОВКА КЛАВИШ ЧЕРЕЗ WINAPI (без прав админа)
# =========================================================
user32 = ctypes.windll.user32

# Коды виртуальных клавиш
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_TAB = 0x09
VK_F4 = 0x73
VK_ESCAPE = 0x1B
VK_F11 = 0x7A
VK_F12 = 0x7B

# Флаги
LLKHF_ALTDOWN = 0x20

# Структура KBDLLHOOKSTRUCT
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

# Прототип функции хука
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

def low_level_handler(nCode, wParam, lParam):
    if nCode >= 0:
        kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT))[0]
        vk = kbd.vkCode
        flags = kbd.flags

        # Блокируем Win, Alt+Tab, Alt+F4, Alt+Esc
        if vk in (VK_LWIN, VK_RWIN):
            return 1 # Съедаем нажатие
        if (flags & LLKHF_ALTDOWN) and vk in (VK_TAB, VK_F4, VK_ESCAPE):
            return 1
        if vk in (VK_F11, VK_F12):
            return 1

    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def run_keyboard_hook():
    # Устанавливаем хук в отдельном потоке
    hook_proc = HOOKPROC(low_level_handler)
    hook = user32.SetWindowsHookExA(13, hook_proc, None, 0) # WH_KEYBOARD_LL = 13
    if not hook:
        print("Не удалось установить хук клавиатуры.")
        return

    print("Глобальный перехват клавиш (WinAPI) активен.")
    msg = wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))

# =========================================================
# АВТОЗАГРУЗКА
# =========================================================
def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    script = os.path.abspath(__file__)
    return f'"{pyw}" "{script}"'

def ensure_autostart() -> None:
    if not AUTOSTART:
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        )
        try:
            try:
                current, _ = winreg.QueryValueEx(key, AUTOSTART_NAME)
            except FileNotFoundError:
                current = None
            cmd = _launch_command()
            if current != cmd:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, cmd)
        finally:
            winreg.CloseKey(key)
    except OSError as e:
        print(f"Автозагрузка не удалась: {e}")

# =========================================================
# БРАУЗЕР
# =========================================================
class Page(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
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

        self.view.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

        if FULLSCREEN:
            self.showFullScreen()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Close:
            if obj is self:
                event.ignore()
                return True
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_F11, Qt.Key.Key_F12, Qt.Key.Key_Escape, Qt.Key.Key_F5):
                return True
            if mods & Qt.KeyboardModifier.ControlModifier and key in (
                Qt.Key.Key_W, Qt.Key.Key_Q, Qt.Key.Key_N, Qt.Key.Key_T, Qt.Key.Key_R
            ):
                return True
            if mods & Qt.KeyboardModifier.AltModifier and key in (
                Qt.Key.Key_F4, Qt.Key.Key_Tab, Qt.Key.Key_Left, Qt.Key.Key_Right
            ):
                return True
            if mods & Qt.KeyboardModifier.MetaModifier:
                return True

        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        event.ignore()

if __name__ == "__main__":
    # 1. Ставим в автозагрузку
    ensure_autostart()

    # 2. Запускаем хук клавиатуры в фоне
    t = threading.Thread(target=run_keyboard_hook, daemon=True)
    t.start()
    time.sleep(0.2) # Даем время хуку установиться

    # 3. Запускаем окно
    app = QApplication(sys.argv)
    window = Viewer()
    if not FULLSCREEN:
        window.show()
    sys.exit(app.exec())
