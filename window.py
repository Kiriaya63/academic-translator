"""主弹窗：左右双输入框 + 双向自动翻译。

左栏中文、右栏英文；在任意一侧停止输入后，自动把内容翻译到另一侧。
"""
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import translator
from config import debounce_ms, left_langs, right_langs

# 状态点颜色
_STATUS_COLORS = {
    "ready": "#9aa3b2",
    "busy": "#f59e0b",
    "done": "#22c55e",
    "error": "#ef4444",
}

# 面板语言色点
LEFT_DOT = "#e05a4e"   # 中文
RIGHT_DOT = "#2f6fed"  # English


class _TranslateTask(QRunnable):
    """在后台线程执行一次翻译，通过 signals 回传结果。"""

    class Signals(QObject):
        result = Signal(str)
        error = Signal(str)

    def __init__(self, text: str, source_lang: str, target_lang: str):
        super().__init__()
        self.setAutoDelete(False)  # 由 Python 管理生命周期，避免悬空指针
        self._text = text
        self._source = source_lang
        self._target = target_lang
        self.signals = self.Signals()

    def run(self):
        try:
            result = translator.translate(self._text, self._source, self._target)
            self.signals.result.emit(result)
        except translator.TranslateError as exc:
            self.signals.error.emit(str(exc))
        except Exception as exc:  # 兜底，避免线程内异常静默
            self.signals.error.emit(f"未知错误：{exc}")


class TitleBar(QWidget):
    """可拖动的自定义标题栏。"""

    def __init__(self, window: QWidget):
        super().__init__()
        self._window = window
        self._dragging = False
        self._offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self._offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._updating = False      # 程序写入对侧文本时置位，防止回环
        self._pending_side = None   # "left" / "right"：等待翻译的一侧
        self._generation = 0        # 每次编辑递增，用于丢弃过期结果
        self._tasks = []            # 保活后台任务，避免其 signals 被 GC

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms())
        self._timer.timeout.connect(self._start_translate)

        # 复制提示的短暂状态复位
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.setInterval(1500)
        self._flash_timer.timeout.connect(self._reset_status)

        self._build_ui()
        self._apply_style()
        self._set_status("就绪", "ready")

    # ---------- UI 构建 ----------
    def _build_ui(self):
        self.setWindowTitle("学术翻译")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(780, 400)
        self.setMinimumSize(560, 320)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        self._container = QFrame()
        self._container.setObjectName("container")

        shadow = QGraphicsDropShadowEffect(self._container)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self._container)
        root.setContentsMargins(16, 10, 16, 12)
        root.setSpacing(10)

        # ---- 标题栏（可拖动） ----
        self._title_bar = TitleBar(self)
        tb = QHBoxLayout(self._title_bar)
        tb.setContentsMargins(2, 0, 2, 0)
        tb.setSpacing(4)

        self._title_label = QLabel("学术翻译")
        self._title_label.setObjectName("titleLabel")
        self._title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._subtitle = QLabel("DeepL · 双向同步")
        self._subtitle.setObjectName("subtitle")
        self._subtitle.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._min_btn = self._make_title_button("−", "minBtn", "隐藏到托盘")
        self._min_btn.clicked.connect(self.hide)
        self._close_btn = self._make_title_button("✕", "closeBtn", "关闭（隐藏到托盘）")
        self._close_btn.clicked.connect(self.hide)

        tb.addWidget(self._title_label)
        tb.addSpacing(8)
        tb.addWidget(self._subtitle)
        tb.addStretch(1)
        tb.addWidget(self._min_btn)
        tb.addWidget(self._close_btn)
        root.addWidget(self._title_bar)

        # ---- 左右输入框 ----
        self._splitter = QSplitter(Qt.Horizontal)
        left_panel, self._left = self._make_panel("中文", LEFT_DOT)
        right_panel, self._right = self._make_panel("English", RIGHT_DOT)
        self._splitter.addWidget(left_panel)
        self._splitter.addWidget(right_panel)
        self._splitter.setSizes([390, 390])
        self._splitter.setHandleWidth(8)
        root.addWidget(self._splitter, 1)

        self._left.textChanged.connect(lambda: self._on_edited("left"))
        self._right.textChanged.connect(lambda: self._on_edited("right"))

        # ---- 状态栏 ----
        status_row = QWidget()
        sl = QHBoxLayout(status_row)
        sl.setContentsMargins(2, 0, 2, 0)
        sl.setSpacing(6)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)

        self._status = QLabel("就绪")
        self._status.setObjectName("status")

        sl.addWidget(self._status_dot)
        sl.addWidget(self._status)
        sl.addStretch(1)
        root.addWidget(status_row)

        outer.addWidget(self._container)

    def _make_title_button(self, text: str, name: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(name)
        btn.setFixedSize(26, 26)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        return btn

    def _make_panel(self, label_text: str, dot_color: str):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(2, 0, 2, 0)
        hl.setSpacing(6)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 4px;")

        title = QLabel(label_text)
        title.setObjectName("panelLabel")

        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("copyBtn")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setToolTip("复制该栏内容到剪贴板")

        hl.addWidget(dot)
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(copy_btn)
        layout.addWidget(header)

        editor = QPlainTextEdit()
        editor.setObjectName("editor")
        layout.addWidget(editor, 1)

        def copy():
            QApplication.clipboard().setText(editor.toPlainText())
            self._set_status("已复制", "done")
            self._flash_timer.start()

        copy_btn.clicked.connect(copy)

        return panel, editor

    def _apply_style(self):
        self.setStyleSheet(
            """
            QFrame#container {
                background-color: #ffffff;
                border-radius: 14px;
                border: 1px solid #e4e7ee;
            }
            QLabel#titleLabel {
                font-size: 15px;
                font-weight: 600;
                color: #1a2233;
            }
            QLabel#subtitle {
                font-size: 11px;
                color: #9aa3b2;
            }
            QLabel#panelLabel {
                font-size: 13px;
                font-weight: 600;
                color: #3c4350;
            }
            QPlainTextEdit#editor {
                background-color: #f6f8fb;
                border: 1px solid #e3e8f0;
                border-radius: 10px;
                padding: 10px;
                font-size: 15px;
                color: #1f2733;
                selection-background-color: #cfe0ff;
            }
            QPlainTextEdit#editor:focus {
                border: 1px solid #2f6fed;
                background-color: #ffffff;
            }
            QSplitter::handle {
                background-color: transparent;
                border: none;
            }
            QLabel#status {
                font-size: 12px;
                color: #8a93a6;
            }
            QPushButton#minBtn, QPushButton#closeBtn {
                border: none;
                border-radius: 13px;
                background: transparent;
                color: #8a93a6;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton#minBtn:hover {
                background: #eef1f6;
                color: #3c4350;
            }
            QPushButton#closeBtn:hover {
                background: #ff5f56;
                color: #ffffff;
            }
            QPushButton#copyBtn {
                border: 1px solid #e3e8f0;
                border-radius: 6px;
                background: transparent;
                color: #6b7280;
                padding: 3px 10px;
                font-size: 12px;
            }
            QPushButton#copyBtn:hover {
                background: #f0f4ff;
                color: #2f6fed;
                border-color: #2f6fed;
            }
            """
        )

    # ---------- 翻译逻辑 ----------
    def _on_edited(self, side: str):
        if self._updating:
            return

        self._generation += 1
        editor = self._left if side == "left" else self._right
        other = self._right if side == "left" else self._left

        if not editor.toPlainText().strip():
            # 清空时直接同步清空对侧，不调用 API
            self._pending_side = None
            self._timer.stop()
            self._updating = True
            other.setPlainText("")
            self._updating = False
            self._set_status("就绪", "ready")
            return

        self._pending_side = side
        self._timer.start()
        self._set_status("翻译中…", "busy")

    def _start_translate(self):
        if self._pending_side is None:
            return

        side = self._pending_side
        self._pending_side = None
        editor = self._left if side == "left" else self._right
        text = editor.toPlainText().strip()
        if not text:
            return

        source, target = left_langs() if side == "left" else right_langs()
        gen = self._generation

        task = _TranslateTask(text, source, target)
        self._tasks.append(task)
        task.signals.result.connect(lambda r, g=gen, t=task: self._on_done(side, r, g, t))
        task.signals.error.connect(lambda e, g=gen, t=task: self._on_done(side, e, g, t, is_error=True))
        QThreadPool.globalInstance().start(task)
        self._set_status("翻译中…", "busy")

    def _on_done(self, side: str, text: str, gen: int, task, is_error: bool = False):
        if task in self._tasks:
            self._tasks.remove(task)

        if gen != self._generation:
            return  # 结果已过期，丢弃

        if is_error:
            self._set_status(f"错误：{text}", "error")
            return

        other = self._right if side == "left" else self._left
        self._updating = True
        other.setPlainText(text)
        self._updating = False
        self._set_status("已翻译", "done")

    # ---------- 状态 ----------
    def _set_status(self, message: str, state: str = "ready"):
        self._status.setText(message)
        color = _STATUS_COLORS.get(state, _STATUS_COLORS["ready"])
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")

    def _reset_status(self):
        if self._tasks or self._pending_side is not None:
            return  # 有翻译进行中，保持当前状态
        self._set_status("就绪", "ready")

    # ---------- 窗口行为 ----------
    def set_pinned(self, pinned: bool):
        was_visible = not self.isHidden()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, pinned)
        if was_visible:
            self.show()

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()
