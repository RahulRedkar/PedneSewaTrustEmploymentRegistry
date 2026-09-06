"""
Non-blocking animated notification banner / toast for PySide6 desktop.
"""

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer


class ToastNotification(QFrame):
    """Floating notification card that auto-dismisses after a timeout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.icon_label = QLabel("ℹ️", self)
        self.icon_label.setStyleSheet("font-size: 16px;")
        self.msg_label = QLabel("", self)
        self.msg_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        close_btn = QPushButton("✕", self)
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("border: none; background: transparent; font-weight: bold; color: inherit;")
        close_btn.clicked.connect(self.hide)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.msg_label)
        layout.addStretch()
        layout.addWidget(close_btn)

        self.hide()

    def show_toast(self, message: str, level: str = "success", duration_ms: int = 4000):
        """Displays toast message with appropriate styling."""
        icons = {
            "success": "✅",
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌"
        }
        bg_colors = {
            "success": ("#ECFDF5", "#065F46", "#10B981"),
            "info": ("#EFF6FF", "#1E40AF", "#3B82F6"),
            "warning": ("#FFFBEB", "#92400E", "#F59E0B"),
            "error": ("#FEF2F2", "#991B1B", "#EF4444")
        }

        bg, text_color, border_color = bg_colors.get(level, bg_colors["info"])
        self.icon_label.setText(icons.get(level, "ℹ️"))
        self.msg_label.setText(message)
        self.msg_label.setStyleSheet(f"color: {text_color}; font-weight: 600; font-size: 13px;")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1.5px solid {border_color};
                border-radius: 8px;
                color: {text_color};
            }}
        """)

        # Position at top center of parent
        if self.parent():
            parent_geom = self.parent().geometry()
            toast_width = max(360, len(message) * 9 + 80)
            self.setFixedWidth(min(toast_width, parent_geom.width() - 40))
            x = (parent_geom.width() - self.width()) // 2
            y = 75  # Just below header bar
            self.move(x, y)

        self.show()
        self.raise_()
        self._timer.start(duration_ms)
