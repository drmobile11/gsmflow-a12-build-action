# main.py
import sys
import os

# Handle PyInstaller and Nuitka bundles
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        BASE_DIR = sys._MEIPASS
    else:
        # Nuitka bundle - use executable directory
        BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add base dir to path for imports
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt5.QtWidgets import QApplication
from core.detector import DeviceDetector
from utils.helpers import hide_console

if __name__ == "__main__":
    hide_console()
    app = QApplication(sys.argv)
    app.setApplicationName("RhaulH A12 Bypass")
    window = DeviceDetector()
    window.show()
    sys.exit(app.exec_())