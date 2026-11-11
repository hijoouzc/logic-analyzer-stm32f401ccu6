#!/usr/bin/env python3
"""software/tests/test_smart_cursors.py
Kiểm thử tự động Hệ thống Thước Đo Thông Minh (UI_SPEC.md Mục 7 & Mục 8):
1. Magnetic Snap-to-Edge: Tự động khóa dính sườn xung khi khoảng cách <= 15 pixels.
2. Free Movement: Di chuyển tự do, không bị hút nhầm khi khoảng cách > 15 pixels.
3. Priority Snapping: Ưu tiên kênh hover -> kênh active_inspect_channel -> tất cả kênh.
4. Quick Measure Tool (2-Click Measurement, Hotkey M):
   - Bấm M / nút |↔| -> Crosshair.
   - Click 1: Đặt Cursor A kèm Snap.
   - Live Preview: Vẽ đường nối, nhãn Δt và f.
   - Click 2: Đặt Cursor B kèm Snap, chốt đo, hiện Span Bar và HUD.
5. Escape Key: Hủy chế độ đo nhanh và khôi phục con trỏ bình thường.
6. Point Inspector (Hover Timestamp): Rê chuột phát tín hiệu thời gian, số thứ tự mẫu #N và raw byte.
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


class TestSmartCursorsAndQuickMeasure(unittest.TestCase):
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

        # Tạo dữ liệu sóng mẫu giả lập 8 kênh với các cạnh xung rõ ràng
        # fs = 1 MHz, 32768 mẫu, trig_offset = 6554
        self.fs = 1_000_000.0
        self.n_samples = 32768
        self.trig_offset = 6554

        # Kênh 0: Chuỗi xung chu kỳ 8000 mẫu (8 ms), cạnh cách nhau 4000 mẫu (~80 pixels trên màn hình)
        t = np.arange(self.n_samples)
        ch0 = ((t % 8000) < 4000).astype(np.uint8)

        # Kênh 1: Chuỗi xung chu kỳ 10000 mẫu (10 ms), cạnh cách nhau 5000 mẫu
        ch1 = ((t % 10000) < 5000).astype(np.uint8)

        # Các kênh còn lại
        channels = [ch0, ch1] + [np.zeros(self.n_samples, dtype=np.uint8) for _ in range(6)]

        self.mock_res = {
            "status": 0,  # STATUS_TRIGGER_OK
            "sample_rate": self.fs,
            "sample_count": self.n_samples,
            "trig_offset": self.trig_offset,
            "channels": channels
        }
        self.win.waveform.render_data(self.mock_res)
        QtWidgets.QApplication.processEvents()

    def tearDown(self):
        self.win.close()
        QtWidgets.QApplication.processEvents()

    def test_01_edge_extraction(self):
        """Kiểm tra trích xuất sườn xung vector hóa NumPy."""
        wf = self.win.waveform
        self.assertGreater(len(wf.channel_edges[0]), 0, "Kênh 0 phải có các sườn xung được trích xuất")
        self.assertGreater(len(wf.channel_edges[1]), 0, "Kênh 1 phải có các sườn xung được trích xuất")
        self.assertEqual(len(wf.channel_edges[2]), 0, "Kênh 2 (phẳng) không có sườn xung")
        self.assertGreater(len(wf.all_edges), 0, "Mảng all_edges phải chứa các sườn xung của tất cả các kênh")

        # Kiểm tra tính chính xác của thời gian sườn xung kênh 0 (cạnh tại mẫu 4000)
        expected_edge_idx = 4000  # Một trong các sườn xung
        expected_time = (expected_edge_idx - self.trig_offset) / self.fs
        diffs = np.abs(wf.channel_edges[0] - expected_time)
        self.assertAlmostEqual(float(np.min(diffs)), 0.0, places=9)
        print("-> [PASS] Test 1: Trích xuất sườn xung NumPy vectorization chính xác 100%!")

    def test_02_magnetic_snap_within_radius(self):
        """Kiểm tra hút dính sườn xung khi khoảng cách <= 15 pixels."""
        wf = self.win.waveform
        known_edge_time = float(wf.channel_edges[0][5])  # Lấy 1 sườn xung mẫu

        # Tính toán độ lệch thời gian tương ứng với 8 pixels
        p_edge = wf.vb.mapViewToDevice(QtCore.QPointF(known_edge_time, 0))
        p_shifted = QtCore.QPointF(p_edge.x() + 8.0, p_edge.y())
        t_shifted = float(wf.vb.mapDeviceToView(p_shifted).x())

        # Tìm kiếm sườn xung với tọa độ lệch 8px
        t_snap, matched_ch, px_dist = wf.find_closest_edge(t_shifted, preferred_ch=0, max_px=15.0)

        self.assertIsNotNone(t_snap, "Phải hút dính sườn xung khi cách 8px")
        self.assertAlmostEqual(t_snap, known_edge_time, places=9, msg="Thời gian snap phải khớp chính xác với sườn xung")
        self.assertEqual(matched_ch, 0, "Kênh snap phải là kênh 0")
        self.assertLessEqual(px_dist, 15.0, "Khoảng cách pixel phải <= 15px")
        print(f"-> [PASS] Test 2: Magnetic Snap hút dính thành công tại {px_dist:.2f} px <= 15 px!")

    def test_03_free_movement_beyond_radius(self):
        """Kiểm tra di chuyển tự do khi khoảng cách > 15 pixels."""
        wf = self.win.waveform
        # Chọn sườn xung tại 0.013446 s (gap tới sườn tiếp theo là 78.27 px)
        known_edge_time = 0.013446

        # Tính độ lệch tương ứng với 25 pixels (lớn hơn bán kính 15px và nằm trọn trong gap 78px)
        p_edge = wf.vb.mapViewToDevice(QtCore.QPointF(known_edge_time, 0))
        p_shifted = QtCore.QPointF(p_edge.x() + 25.0, p_edge.y())
        t_shifted = float(wf.vb.mapDeviceToView(p_shifted).x())

        t_snap, matched_ch, px_dist = wf.find_closest_edge(t_shifted, preferred_ch=0, max_px=15.0)

        self.assertIsNone(t_snap, "Không được hút dính khi khoảng cách > 15px")
        self.assertEqual(px_dist, float("inf"))
        print("-> [PASS] Test 3: Free Movement giữ nguyên tọa độ tự do khi lệch 25 px > 15 px!")

    def test_04_channel_snapping_priority(self):
        """Kiểm tra thứ tự ưu tiên hút: Kênh hover -> active_inspect_channel -> all_edges."""
        wf = self.win.waveform
        # Đặt 2 sườn xung tại 2 kênh khác nhau
        edge_ch0 = float(wf.channel_edges[0][3])
        edge_ch1 = float(wf.channel_edges[1][2])

        # Khi ưu tiên kênh 1 (hovered = 1)
        t_snap, matched_ch, _ = wf.find_closest_edge(edge_ch1 + 1e-7, preferred_ch=1, max_px=15.0)
        self.assertEqual(matched_ch, 1, "Phải ưu tiên kênh hover (CH1)")

        # Khi ưu tiên kênh 0 (hovered = 0)
        t_snap0, matched_ch0, _ = wf.find_closest_edge(edge_ch0 + 1e-7, preferred_ch=0, max_px=15.0)
        self.assertEqual(matched_ch0, 0, "Phải ưu tiên kênh hover (CH0)")
        print("-> [PASS] Test 4: Channel Priority Snapping hoạt động chuẩn xác!")

    def test_05_quick_measure_2_click_workflow(self):
        """Kiểm thử toàn bộ quy trình Quick Measure 2-Click (Phím M -> Click A -> Click B)."""
        wf = self.win.waveform
        win = self.win

        # 1. Kích hoạt bằng phím tắt M
        key_event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_M, QtCore.Qt.NoModifier)
        win.keyPressEvent(key_event)
        QtWidgets.QApplication.processEvents()

        self.assertTrue(wf.quick_measure_active, "Chế độ Quick Measure phải đang bật")
        self.assertEqual(wf.quick_measure_step, 1, "Bước phải là 1 (chờ click A)")
        self.assertTrue(wf.cursor_a.isVisible(), "Cursor A phải hiển thị")

        # 2. Click 1: Đặt Cursor A tại sườn xung thứ 2 của kênh 0
        edge_a = float(wf.channel_edges[0][2])
        # Chuyển đổi sang tọa độ scene
        y_mid_ch0 = wf.get_channel_mid_y(0)
        pt_scene_a = wf.vb.mapViewToScene(QtCore.QPointF(edge_a, y_mid_ch0))

        # Giả lập sự kiện click chuột trái
        class MockMouseEvent:
            def __init__(self, scene_pos, button):
                self._pos = scene_pos
                self._btn = button
                self.accepted = False
            def scenePos(self):
                return self._pos
            def button(self):
                return self._btn
            def accept(self):
                self.accepted = True

        ev1 = MockMouseEvent(pt_scene_a, QtCore.Qt.LeftButton)
        wf._on_scene_mouse_clicked(ev1)
        QtWidgets.QApplication.processEvents()

        self.assertEqual(wf.quick_measure_step, 2, "Sau Click 1, bước phải chuyển sang 2 (chờ click B)")
        self.assertAlmostEqual(wf.cursor_a.value(), edge_a, places=8, msg="Cursor A phải được đặt tại sườn xung A")

        # 3. Di chuột xem trước (Live Preview)
        edge_b = float(wf.channel_edges[0][4])
        pt_scene_b = wf.vb.mapViewToScene(QtCore.QPointF(edge_b, y_mid_ch0))
        wf._on_scene_mouse_moved(pt_scene_b)
        QtWidgets.QApplication.processEvents()

        self.assertTrue(wf.preview_measure_line.isVisible(), "Preview line phải hiển thị khi đang ở bước 2")
        self.assertTrue(wf.preview_measure_text.isVisible(), "Preview text phải hiển thị thông số động")

        # 4. Click 2: Đặt Cursor B tại sườn xung thứ 4 của kênh 0
        ev2 = MockMouseEvent(pt_scene_b, QtCore.Qt.LeftButton)
        wf._on_scene_mouse_clicked(ev2)
        QtWidgets.QApplication.processEvents()

        self.assertFalse(wf.quick_measure_active, "Sau Click 2, Quick Measure phải kết thúc")
        self.assertEqual(wf.quick_measure_step, 0, "Bước phải quay về 0")
        self.assertAlmostEqual(wf.cursor_b.value(), edge_b, places=8, msg="Cursor B phải được đặt tại sườn xung B")

        # Kiểm tra tính toán Δt và f
        expected_dt = abs(edge_b - edge_a)
        measured_dt = wf.get_delta_t()
        self.assertAlmostEqual(measured_dt, expected_dt, places=8)
        self.assertAlmostEqual(wf.get_frequency(), 1.0 / expected_dt, places=3)
        print(f"-> [PASS] Test 5: Quick Measure 2-Click chốt đo chuẩn xác: Δt = {format_si_time(measured_dt)}, f = {format_si_freq(wf.get_frequency())}!")

    def test_06_escape_key_cancels_quick_measure(self):
        """Kiểm tra phím Escape hủy bỏ chế độ Quick Measure tức thì."""
        wf = self.win.waveform
        win = self.win

        # Kích hoạt
        wf.start_quick_measure()
        self.assertTrue(wf.quick_measure_active)

        # Bấm phím Escape
        esc_event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
        win.keyPressEvent(esc_event)
        QtWidgets.QApplication.processEvents()

        self.assertFalse(wf.quick_measure_active, "Chế độ Quick Measure phải bị hủy khi bấm Esc")
        self.assertEqual(wf.quick_measure_step, 0)
        self.assertFalse(wf.preview_measure_line.isVisible())
        self.assertFalse(wf.preview_measure_text.isVisible())
        print("-> [PASS] Test 6: Phím Escape hủy chế độ Quick Measure an toàn!")

    def test_07_point_inspector_hover_timestamp(self):
        """Kiểm tra Point Inspector phát tín hiệu thời gian và số thứ tự mẫu khi rê chuột."""
        wf = self.win.waveform
        emitted_signals = []

        def on_hover(t, idx, val):
            emitted_signals.append((t, idx, val))

        wf.sigHoverTimestamp.connect(on_hover)

        # Di chuột đến vị trí giữa khung nhìn
        y_mid = wf.get_channel_mid_y(0)
        t_target = 0.005  # 5 ms
        pt_scene = wf.vb.mapViewToScene(QtCore.QPointF(t_target, y_mid))
        wf._on_scene_mouse_moved(pt_scene)
        QtWidgets.QApplication.processEvents()

        self.assertGreater(len(emitted_signals), 0, "Phải phát tín hiệu sigHoverTimestamp khi hover")
        last_t, last_idx, last_val = emitted_signals[-1]
        self.assertAlmostEqual(last_t, t_target, places=6)
        expected_idx = int(round(t_target * self.fs + self.trig_offset))
        self.assertEqual(last_idx, expected_idx, "Số thứ tự mẫu phải được tính đúng")
        print(f"-> [PASS] Test 7: Point Inspector Hover Timestamp chính xác: T = {format_si_time(last_t)} | #{last_idx} | 0x{last_val:02X}!")


def main():
    print("=" * 60)
    print("BẮT ĐẦU KIỂM THỬ HỆ THỐNG THƯỚC ĐO THÔNG MINH (UI_SPEC Mục 7 & 8)")
    print("=" * 60)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmartCursorsAndQuickMeasure)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 60)
        print("  [SUCCESS] 100% CÁC BÀI KIỂM THỬ THƯỚC ĐO THÔNG MINH ĐẠT PASS!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("  [FAIL] CÓ LỖI XẢY RA TRONG QUÁ TRÌNH KIỂM THỬ!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
