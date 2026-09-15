"""入口：创建应用、系统托盘、主窗口、全局快捷键。"""
import sys

from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from window import MainWindow

# 全局快捷键：呼出/隐藏窗口。keyboard 为可选依赖，缺失或失败时静默降级（托盘仍可用）。
HOTKEY = "ctrl+alt+t"
try:
    import keyboard as _keyboard
except Exception:
    _keyboard = None


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，常驻托盘

    window = MainWindow()
    window.show()

    tray = QSystemTrayIcon(window)
    tray.setToolTip(f"学术翻译弹窗（{HOTKEY} 呼出）")
    tray.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))

    def show_window():
        window.show()
        window.raise_()
        window.activateWindow()

    def toggle_window():
        if window.isHidden():
            show_window()
        else:
            window.hide()

    def on_tray_activated(reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            show_window()

    menu = QMenu()

    toggle_action = menu.addAction("显示 / 隐藏")
    toggle_action.triggered.connect(toggle_window)

    pin_action = menu.addAction("始终置顶")
    pin_action.setCheckable(True)
    pin_action.setChecked(True)
    pin_action.toggled.connect(window.set_pinned)

    menu.addSeparator()
    hotkey_hint = menu.addAction(f"快捷键：{HOTKEY.replace('+', ' + ')}")
    hotkey_hint.setEnabled(False)

    quit_action = menu.addAction("退出")
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.activated.connect(on_tray_activated)
    tray.show()

    # 注册全局快捷键（失败则静默降级）
    hotkey_handler = None
    if _keyboard is not None:
        try:
            hotkey_handler = _keyboard.add_hotkey(HOTKEY, toggle_window)
        except Exception:
            hotkey_handler = None

    def on_quit():
        if _keyboard is not None and hotkey_handler is not None:
            try:
                _keyboard.remove_hotkey(hotkey_handler)
            except Exception:
                pass

    app.aboutToQuit.connect(on_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
