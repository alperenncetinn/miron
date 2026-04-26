import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
import AppKit

app = QApplication(sys.argv)
AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
w = QWidget()
w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.BypassWindowManagerHint)
w.show()
sys.exit(app.exec())
