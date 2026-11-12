#!/usr/bin/env python3
"""software/tests/test_active_channel_sync.py
Kiểm thử tự động Hệ Thống Đồng Bộ Kênh Tác Vụ Toàn Diện (Unified Active Channel Synchronization)
và Bảng Dữ Liệu Tự Thích Ứng Thông Minh Smart Dual-Mode (UI_SPEC.md Mục 9 & Mục 10):
1. Khởi động mặc định: Active Channel = 0, Cột nhãn, Device Settings (CH0), Measurements (CH0) đồng bộ.
2. Click khung nhãn kênh (channel_frames[N]): Toàn bộ hệ thống đồng bộ về Kênh N.
3. Click track sóng (Waveform Track): Xác định Kênh N theo tọa độ Y và đồng bộ toàn bộ hệ thống.
4. Chọn từ Combobox (combo_ch hoặc combo_meas_ch): Đồng bộ 2 chiều qua lại không giật lag.
5. Smart Dual-Mode - Chế độ Protocol Packets:
   - Khi chọn kênh có Analyzer (CH0 UART): Hiện 5 cột ["", "Type", "Start", "Duration", "Data"],
     tiêu đề "Data (UART D0)", click dòng phóng to byte.
6. Smart Dual-Mode - Chế độ Transition Edge Timing List:
   - Khi chọn kênh số thô (CH1 PWM/Square wave): Tự động chuyển 5 cột ["#", "Edge", "Timestamp", "Δt (Pulse)", "Frequency"],
     tiêu đề "Transitions (D1)", tính toán thời gian, delta_t, freq.
7. Điều hướng 2 chiều Transitions -> Viewport:
   - Click vào dòng sườn xung -> Viewport tự động căn giữa (Pan to Center) sườn xung đó,
     đặt thước đo Cursor A tại vị trí sườn xung làm vạch chỉ báo rõ ràng.
8. Lọc tìm kiếm trên bảng Transitions (Filter Search).
9. Ưu tiên Magnetic Snap theo Active Channel.
"""

import os
import sys
import unittest
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from software.gui.main_window import MainWindow
from software.gui.waveform_widget import WaveformWidget, format_si_time, format_si_freq
from software.gui import theme as T


class TestActiveChannelSynchronization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication(sys.argv)

    def setUp(self):
        self.win = MainWindow(load_sample_on_start=False)
        self.win.resize(1200, 750)
        self.win.show()
        QtWidgets.QApplication.processEvents()

        # Nạp dữ liệu kiểm thử giả lập 8 kênh
        self.fs = 1_000_000.0
        self.n_samples = 32768
        self.trig_offset = 6554

        # Kênh 0: UART 115200 bps
        # Kênh 1: Xung vuông chu kỳ 2000 mẫu (2 ms), cạnh cách nhau 1000 mẫu (1 ms)
        # Kênh 2: Xung vuông chu kỳ 5000 mẫu
        # Kênh 3..7: Tín hiệu số đa dạng
        t = np.arange(self.n_samples)
        channels = []
        for i in range(8):
            period = 1000 * (i + 1)
            ch_data = ((t % period) < (period // 2)).astype(np.uint8)
            channels.append(ch_data)

        self.mock_data = {
            "channels": channels,
            "sample_rate": self.fs,
            "sample_count": self.n_samples,
            "trig_offset": self.trig_offset,
            "status": 0,
            "status_name": "Triggered",
            "elapsed_s": 0.035
        }
        self.win._render_capture_data(self.mock_data)
        QtWidgets.QApplication.processEvents()

    def tearDown(self):
        self.win.close()
        QtWidgets.QApplication.processEvents()

    def test_01_default_active_channel_initialization(self):
        """Xác nhận khởi động mặc định: Active Channel = 0, Device Settings = 0, Measurements = 0."""
        self.assertEqual(self.win.active_channel, 0)
        self.assertEqual(self.win.combo_ch.currentIndex(), 0)
        self.assertEqual(self.win.combo_meas_ch.currentIndex(), 0)
        self.assertEqual(self.win.waveform.active_channel, 0)
        self.assertEqual(self.win.waveform.active_inspect_channel, 0)

        # Khung nhãn 0 được highlight nền #262628
        frame_0_style = self.win.waveform.channel_frames[0].styleSheet()
        self.assertIn(T.BG_CARD, frame_0_style)
        self.assertIn(f"4px solid {T.CHANNEL_COLORS[0]}", frame_0_style)

        # Khung nhãn 1 giữ nền #1b1b1c và giữ nguyên 100% vạch màu gốc
        frame_1_style = self.win.waveform.channel_frames[1].styleSheet()
        self.assertIn(T.BG_MAIN, frame_1_style)
        self.assertIn(f"4px solid {T.CHANNEL_COLORS[1]}", frame_1_style)
        self.assertNotIn("99;", frame_1_style)

    def test_02_click_channel_label_frame_sync(self):
        """Mô phỏng nhấp chuột trái vào khung nhãn Kênh 2 -> Toàn bộ phân hệ đồng bộ về CH2."""
        # Tạo sự kiện click chuột trái vào frame 2
        ev = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            QtCore.QPoint(20, 20),
            QtCore.Qt.LeftButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier
        )
        self.win.waveform.channel_frames[2].mousePressEvent(ev)
        QtWidgets.QApplication.processEvents()

        # Kiểm tra đồng bộ toàn diện
        self.assertEqual(self.win.active_channel, 2)
        self.assertEqual(self.win.combo_ch.currentIndex(), 2)
        self.assertEqual(self.win.combo_meas_ch.currentIndex(), 2)
        self.assertEqual(self.win.waveform.active_channel, 2)
        self.assertEqual(self.win.waveform.active_inspect_channel, 2)

        # Khung nhãn 2 được highlight, khung nhãn 0 trở về tối
        self.assertIn(T.BG_CARD, self.win.waveform.channel_frames[2].styleSheet())
        self.assertIn(T.BG_MAIN, self.win.waveform.channel_frames[0].styleSheet())

        # Tiêu đề Measurements Card cập nhật màu và tên kênh D2
        meas_title = self.win.lbl_meas_title.text()
        self.assertIn("D2", meas_title)
        self.assertIn(T.CHANNEL_COLORS[2], meas_title)

    def test_03_click_waveform_track_sync(self):
        """Mô phỏng click vào Waveform Track Kênh 4 -> Toàn bộ hệ thống đồng bộ về CH4."""
        # Lấy tọa độ Y tâm của Kênh 4
        y_mid_ch4 = self.win.waveform.get_channel_mid_y(4)
        scene_pos = self.win.waveform.vb.mapViewToScene(QtCore.QPointF(0.001, y_mid_ch4))

        # Giả lập sự kiện MouseClickEvent của pyqtgraph
        class DummyMouseEvent:
            def __init__(self, sp):
                self._sp = sp
                self.currentItem = None
            def button(self):
                return QtCore.Qt.LeftButton
            def scenePos(self):
                return self._sp
            def accept(self):
                pass
            def isAccepted(self):
                return False

        dummy_ev = DummyMouseEvent(scene_pos)
        self.win.waveform._on_scene_mouse_clicked(dummy_ev)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.win.active_channel, 4)
        self.assertEqual(self.win.combo_ch.currentIndex(), 4)
        self.assertEqual(self.win.combo_meas_ch.currentIndex(), 4)
        self.assertEqual(self.win.waveform.active_inspect_channel, 4)

    def test_04_combobox_change_bidirectional_sync(self):
        """Thay đổi combo_ch hoặc combo_meas_ch -> Đồng bộ 2 chiều không tạo vòng lặp vô hạn."""
        # 1. Đổi combo_ch sang CH3
        self.win.combo_ch.setCurrentIndex(3)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.win.active_channel, 3)
        self.assertEqual(self.win.combo_meas_ch.currentIndex(), 3)
        self.assertEqual(self.win.waveform.active_channel, 3)

        # 2. Đổi combo_meas_ch sang CH6
        self.win.combo_meas_ch.setCurrentIndex(6)
        QtWidgets.QApplication.processEvents()
        self.assertEqual(self.win.active_channel, 6)
        self.assertEqual(self.win.combo_ch.currentIndex(), 6)
        self.assertEqual(self.win.waveform.active_channel, 6)

    def test_05_smart_dual_mode_protocol_on_ch0(self):
        """Kênh 0 có gắn UART Analyzer -> Data Table ở chế độ 'protocol' với 5 cột chuẩn."""
        self.win._on_channel_selected(0)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.win.data_table_mode, "protocol")
        self.assertIn("Data", self.win.lbl_data_title.text())
        self.assertEqual(self.win.table_uart_packets.columnCount(), 5)

        # Tiêu đề 5 cột của protocol packets
        headers = [self.win.table_uart_packets.horizontalHeaderItem(c).text() for c in range(5)]
        self.assertEqual(headers, ["", "Type", "Start", "Duration", "Data"])

    def test_06_smart_dual_mode_transitions_on_ch1(self):
        """Kênh 1 là tín hiệu số thô (không có Analyzer) -> Data Table tự chuyển sang Transition Edge Timing List."""
        self.win._on_channel_selected(1)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(self.win.data_table_mode, "transitions")
        self.assertIn("Transitions (D1)", self.win.lbl_data_title.text())
        self.assertEqual(self.win.table_uart_packets.columnCount(), 5)

        # Tiêu đề 5 cột của Transitions List (Spec 9.4)
        headers = [self.win.table_uart_packets.horizontalHeaderItem(c).text() for c in range(5)]
        self.assertEqual(headers, ["#", "Edge", "Timestamp", "Δt (Pulse)", "Frequency"])

        # Bảng phải có dữ liệu sườn xung (Kênh 1 có chu kỳ 2000 mẫu -> ~32 sườn xung trong 32K mẫu)
        row_count = self.win.table_uart_packets.rowCount()
        self.assertGreater(row_count, 10)

        # Kiểm tra nội dung hàng đầu tiên
        item_num = self.win.table_uart_packets.item(0, 0)
        item_edge = self.win.table_uart_packets.item(0, 1)
        item_t = self.win.table_uart_packets.item(0, 2)
        item_dt = self.win.table_uart_packets.item(0, 3)
        item_freq = self.win.table_uart_packets.item(0, 4)

        self.assertEqual(item_num.text(), "1")
        self.assertTrue("RISING" in item_edge.text() or "FALLING" in item_edge.text())
        self.assertTrue("µs" in item_t.text() or "ms" in item_t.text())
        self.assertIsNotNone(item_dt.text())
        self.assertIsNotNone(item_freq.text())

    def test_07_transition_row_click_pan_to_center(self):
        """Click vào hàng trong bảng Transitions -> Viewport căn giữa đúng mốc thời gian và đặt Cursor A."""
        self.win._on_channel_selected(1)
        QtWidgets.QApplication.processEvents()

        # Chọn hàng thứ 3 trong bảng
        item_t = self.win.table_uart_packets.item(2, 2)
        self.assertIsNotNone(item_t)
        t_target = item_t.data(QtCore.Qt.UserRole)
        self.assertIsNotNone(t_target)

        # Click vào hàng 2
        self.win._on_table_row_clicked(2, 2)
        QtWidgets.QApplication.processEvents()

        # Kiểm tra Cursor A đã được đặt ngay tại t_target
        self.assertAlmostEqual(self.win.waveform.cursor_a.value(), float(t_target), places=6)

        # Kiểm tra Viewport đã căn giữa (t_target nằm giữa x_min và x_max)
        x_min, x_max = self.win.waveform.vb.viewRange()[0]
        center = (x_min + x_max) / 2.0
        self.assertAlmostEqual(center, float(t_target), places=5)

    def test_08_search_filter_in_transitions_table(self):
        """Tìm kiếm trong bảng Transitions: Lọc theo sườn xung 'RISING' hoặc 'FALLING'."""
        self.win._on_channel_selected(1)
        QtWidgets.QApplication.processEvents()

        total_rows = self.win.table_uart_packets.rowCount()

        # Lọc chữ "rising"
        self.win.edit_search.setText("rising")
        QtWidgets.QApplication.processEvents()

        visible_count = sum(not self.win.table_uart_packets.isRowHidden(r) for r in range(total_rows))
        self.assertGreater(visible_count, 0)
        self.assertLess(visible_count, total_rows)

        # Xóa tìm kiếm -> Hiện lại toàn bộ
        self.win.edit_search.setText("")
        QtWidgets.QApplication.processEvents()
        visible_all = sum(not self.win.table_uart_packets.isRowHidden(r) for r in range(total_rows))
        self.assertEqual(visible_all, total_rows)

    def test_09_magnetic_snap_priority_to_active_channel(self):
        """Magnetic Snap luôn ưu tiên hút vào sườn xung của Kênh tác vụ hiện tại."""
        self.win._on_channel_selected(2)
        QtWidgets.QApplication.processEvents()

        # active_inspect_channel phải là 2
        self.assertEqual(self.win.waveform.active_inspect_channel, 2)

        # Tìm sườn xung gần nhất quanh mốc 0.0s: Phải trả về cạnh của kênh 2 nếu cùng khoảng cách
        edges_ch2 = self.win.waveform.channel_edges[2]
        if len(edges_ch2) > 0:
            target_edge = edges_ch2[0]
            # Đặt chuột lệch 5 mẫu (~5 µs)
            t_mouse = target_edge + 5e-6
            t_snap, edge_ch, _ = self.win.waveform.find_closest_edge(t_mouse, preferred_ch=2, max_px=50.0)
            self.assertEqual(edge_ch, 2)
            self.assertAlmostEqual(t_snap, target_edge, places=6)


if __name__ == "__main__":
    unittest.main()
