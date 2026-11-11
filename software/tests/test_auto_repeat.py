#!/usr/bin/env python3
"""software/tests/test_auto_repeat.py
Kiểm thử tự động Chế độ Auto-Repeat / Repeat Run (Giai đoạn 1):
1. Kiểm tra khởi tạo và chuyển đổi chế độ Single Shot [1x] <-> Auto-Repeat [↻] (F6, nút Rail, Combobox).
2. Kiểm tra chu trình Auto-Repeat chạy liên tục trong Offline Mock mode (Frame counter tăng, Pause/Freeze frame).
3. Kiểm tra chu trình Auto-Repeat với cổng ảo serial giả lập STM32 (kết nối, nhận dữ liệu liên tục, Pause/Stop an toàn).
4. Kiểm tra phím tắt Space (Play/Pause) và F6 (Toggle mode).
"""

import os
import sys
import pty
import time
import struct
import threading
import tempfile
import numpy as np

# Thiết lập môi trường không hiển thị (Offscreen)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from software.gui.main_window import MainWindow
from software.gui.logic_client import LogicAnalyzerClient


def make_mock_data_frame(seq: int) -> bytes:
    """Tạo gói dữ liệu chuẩn 32.776B của STM32."""
    header = struct.pack("<BBBH H", 0x5A, 0xA5, 0x00, 6554, 32768)
    # Payload 32KB mô phỏng xung vuông đổi theo sequence
    t = np.arange(32768, dtype=np.uint8)
    payload = ((t + seq) % 16 < 8).astype(np.uint8)
    payload_bytes = payload.tobytes()
    checksum = 0
    for b in payload_bytes:
        checksum ^= b
    footer = bytes([checksum])
    return header + payload_bytes + footer


def mock_stm32_loop(master_fd: int, stop_event: threading.Event):
    """Giả lập vi điều khiển STM32 trả lời lệnh Ping và Start liên tục."""
    sample_bin = os.path.join(os.path.dirname(__file__), "sample_data_1mhz.bin")
    with open(sample_bin, "rb") as f:
        mock_packet = f.read()

    while not stop_event.is_set():
        try:
            cmd = os.read(master_fd, 5)
            if not cmd:
                time.sleep(0.01)
                continue
            if len(cmd) >= 2 and cmd[0] == 0xA5 and cmd[1] == 0x03:  # PING
                pong = bytes([0x5A, 0xA5, 0x04, 0x01, 0x00, 0x00, 0xFA])
                os.write(master_fd, pong)
            elif len(cmd) >= 2 and cmd[0] == 0xA5 and cmd[1] == 0x01:  # START
                # Gửi gói 32.776B theo từng khối
                chunk_size = 2048
                for i in range(0, len(mock_packet), chunk_size):
                    if stop_event.is_set():
                        break
                    os.write(master_fd, mock_packet[i:i + chunk_size])
                    time.sleep(0.001)
            elif len(cmd) >= 2 and cmd[0] == 0xA5 and cmd[1] == 0x02:  # ABORT
                resp = bytes([0x5A, 0xA5, 0x05, 0x00, 0x00, 0x00, 0xFA])
                os.write(master_fd, resp)
        except OSError:
            if stop_event.is_set():
                break
            time.sleep(0.01)


def run_auto_repeat_test():
    print("==================================================")
    print("BẮT ĐẦU KIỂM THỬ CHẾ ĐỘ AUTO-REPEAT (GIAI ĐOẠN 1)")
    print("==================================================")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = MainWindow(load_sample_on_start=False)

    # -------------------------------------------------------------------------
    # TEST 1: Kiểm tra UI ban đầu và chuyển đổi Single Shot <-> Auto-Repeat
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Kiểm tra khởi tạo và chuyển đổi chế độ...")
    assert not win.repeat_mode, "Mặc định phải là Single Shot (repeat_mode = False)"
    assert not win.repeat_running, "Mặc định không được chạy repeat ngầm"
    assert win.btn_rail_mode.text() == "1x"
    assert win.combo_capture_mode.currentIndex() == 0

    # Chuyển đổi bằng nút trên Rail
    win._toggle_capture_mode()
    assert win.repeat_mode is True
    assert win.btn_rail_mode.text() == "↻"
    assert win.combo_capture_mode.currentIndex() == 1
    assert "Auto-Repeat" in win.btn_rail_start.toolTip()
    print("-> [PASS] Chuyển sang Auto-Repeat thành công qua nút Activity Rail!")

    # Chuyển đổi ngược lại bằng Combobox
    win.combo_capture_mode.setCurrentIndex(0)
    assert win.repeat_mode is False
    assert win.btn_rail_mode.text() == "1x"
    print("-> [PASS] Chuyển về Single Shot thành công qua Combobox Device Settings!")

    # Chuyển đổi bằng phím tắt F6
    event_f6 = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_F6, QtCore.Qt.NoModifier)
    win.keyPressEvent(event_f6)
    assert win.repeat_mode is True
    assert win.btn_rail_mode.text() == "↻"
    print("-> [PASS] Phím tắt F6 chuyển đổi chế độ mượt mà!")

    # -------------------------------------------------------------------------
    # TEST 2: Kiểm thử Auto-Repeat trong Offline Mock mode
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Kiểm thử chu trình Auto-Repeat chạy liên tục trong Offline Mock mode...")
    win.chk_mock.setChecked(True)
    win.repeat_mode = True
    win._update_capture_mode_ui()

    # Bấm Start Auto-Repeat
    win._on_start_or_abort()
    assert win.repeat_running is True
    assert win.btn_rail_start.text() == "⏸"
    assert "Pause" in win.btn_rail_start.toolTip()

    # Cho event loop chạy một vài chu kỳ để QTimer kích hoạt lặp
    for _ in range(12):
        app.processEvents()
        time.sleep(0.04)

    assert win.repeat_frame_count >= 2, f"Số frame phải >= 2, thực tế: {win.repeat_frame_count}"
    assert "Auto-Repeat" in win.lbl_status.text()
    print(f"-> [PASS] Auto-Repeat (Mock) đã chụp liên tục {win.repeat_frame_count} frames mượt mà!")

    # Bấm Pause (⏸) để đóng băng khung hình
    win._on_start_or_abort()
    assert win.repeat_running is False
    assert win.btn_rail_start.text() == "▶"
    assert "Paused" in win.lbl_status.text()
    assert win.current_data is not None, "Dữ liệu khung hình cuối cùng phải được bảo lưu trên sóng"
    frozen_frame_count = win.repeat_frame_count
    print(f"-> [PASS] Pause thành công! Khung hình #{frozen_frame_count} được đóng băng cố định để phân tích.")

    # -------------------------------------------------------------------------
    # TEST 3: Kiểm thử Auto-Repeat với phần cứng giả lập qua cổng ảo Serial
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Kiểm thử Auto-Repeat qua cổng ảo Serial USB-CDC...")
    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)

    stop_mock = threading.Event()
    th = threading.Thread(target=mock_stm32_loop, args=(master, stop_mock), daemon=True)
    th.start()

    # Cấu hình MainWindow trỏ vào cổng ảo
    win.chk_mock.setChecked(False)
    win.combo_ports.clear()
    win.combo_ports.addItem(slave_name, slave_name)
    win.combo_ports.setCurrentIndex(0)
    win.repeat_mode = True
    win._update_capture_mode_ui()

    # Khởi động Auto-Repeat với cổng ảo
    win._on_start_or_abort()
    assert win.repeat_running is True
    assert win.btn_rail_start.text() == "⏸"

    # Cho event loop chạy để nhận các khung hình từ cổng ảo
    start_time = time.time()
    while win.repeat_frame_count < 3 and time.time() - start_time < 3.0:
        app.processEvents()
        time.sleep(0.02)

    assert win.repeat_frame_count >= 2, f"Số frame từ cổng ảo phải >= 2, thực tế: {win.repeat_frame_count}"
    print(f"-> [PASS] Auto-Repeat đã nhận thành công {win.repeat_frame_count} khung 32.776B từ cổng ảo USB-CDC!")

    # Thử dừng bằng phím Space
    event_space = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Space, QtCore.Qt.NoModifier)
    win.keyPressEvent(event_space)
    assert win.repeat_running is False
    assert win.btn_rail_start.text() == "▶"
    print("-> [PASS] Phím Space tạm dừng Auto-Repeat (Pause/Resume) thành công!")

    # Dọn dẹp luồng giả lập
    stop_mock.set()
    try:
        os.close(master)
        os.close(slave)
    except OSError:
        pass
    th.join(timeout=1.0)

    # Đóng MainWindow
    win.close()

    print("\n==================================================")
    print("  [SUCCESS] 100% BÀI TEST AUTO-REPEAT ĐẠT PASS!")
    print("  Giai đoạn 1 đã hoàn thiện chuẩn xác và sẵn sàng!")
    print("==================================================")


if __name__ == "__main__":
    run_auto_repeat_test()
