#!/usr/bin/env python3
"""
software/main.py
Điểm khởi chạy ứng dụng chính của phần mềm Logic Analyzer Desktop (TV3).

Khởi động giao diện PyQt5 + pyqtgraph:
- Hỗ trợ màn hình độ phân giải cao (High-DPI scaling)
- Thiết lập Dark Theme đồng bộ
- Bắt tín hiệu ngắt Ctrl+C an toàn
"""

import sys
import os
import signal

# Khử thông báo cảnh báo Wayland requestActivate() trên Linux
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")

# Đảm bảo đường dẫn import tương đối từ thư mục gốc dự án
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from software.gui import theme as T
from software.gui.main_window import MainWindow
from software.qt_bootstrap import configure_qt_plugins


def main():
    configure_qt_plugins()
    # 1. Bật tính năng co giãn giao diện cho màn hình High-DPI (Retina, 2K, 4K)
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("STM32 Logic Analyzer")
    app.setOrganizationName("HUST - Embedded Systems")
    T.apply_theme(app)

    # 2. Xử lý tín hiệu Ctrl+C từ terminal để đóng ứng dụng mượt mà
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    # 3. Khởi tạo và hiển thị cửa sổ chính
    window = MainWindow()
    window.show()

    # 4. Vòng lặp sự kiện chính của ứng dụng
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
