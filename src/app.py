"""智能出卷系统 v2.0 - 入口"""
import sys, os, logging
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path: sys.path.insert(0, _HERE)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from main_window import MainWindow

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName('智能出卷系统')
    app.setFont(QFont('Microsoft YaHei UI', 10))
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == '__main__': main()
