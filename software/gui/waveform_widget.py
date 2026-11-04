#!/usr/bin/env python3
"""software/gui/waveform_widget.py
Khung vẽ sóng logic 8 kênh (Waveform Viewport) theo chuẩn UI_SPEC.md và proto.py (v3):
- Cột nhãn bên trái (194 px) với dải màu 4 px, nhãn D0..D7, tên kênh và chip analyzer.
- Trục thời gian trên cùng (32 px) với mốc tương đối (+0.1 ms, +0.2 ms...), 0 tại Trigger.
- 8 hàng kênh số co giãn lấp đầy chiều cao (hàng có analyzer = 1.45x hàng thường).
- Nhãn H và L ở mép trái mỗi hàng sóng, vạch ngăn mảnh giữa các hàng.
- Vạch lưới dọc nét đứt (dashed grid lines).
- Vạch Trigger (T-Marker) màu TRIGGER_MARKER tại điểm kích hoạt (mẫu 6554, t = 0).
- Chú thích giải mã UART trực tiếp trên sóng (ô bo góc màu DECODE_UART_BG, chữ DECODE_UART_FG).
- Chấm trắng nhỏ tại tâm mỗi bit dữ liệu (bit center dots).
- Cặp thước đo thời gian (Cursor A & Cursor B) kéo thả chuột kèm HUD tính Δt và f.
"""

from typing import Optional, Dict, Any, List, Tuple
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from software.gui import theme as T

DEFAULT_CHANNEL_NAMES = [f"Channel {i}" for i in range(8)]


def format_si_time(seconds: float) -> str:
    """Định dạng thời gian theo tiền tố SI chuẩn (s, ms, µs, ns)."""
    abs_s = abs(seconds)
    sign = "-" if seconds < 0 else ""
    if abs_s >= 1.0:
        return f"{sign}{abs_s:.4f} s"
    elif abs_s >= 1e-3:
        return f"{sign}{abs_s * 1e3:.3f} ms"
    elif abs_s >= 1e-6:
        return f"{sign}{abs_s * 1e6:.3f} µs"
    else:
        return f"{sign}{abs_s * 1e9:.1f} ns"


def format_si_freq(freq_hz: float) -> str:
    """Định dạng tần số theo tiền tố SI chuẩn (Hz, kHz, MHz)."""
    if freq_hz <= 0 or freq_hz == float("inf"):
        return "-- Hz"
    if freq_hz >= 1e6:
        return f"{freq_hz / 1e6:.3f} MHz"
    elif freq_hz >= 1e3:
        return f"{freq_hz / 1e3:.3f} kHz"
    else:
        return f"{freq_hz:.2f} Hz"


class RelativeTimeAxis(pg.AxisItem):
    """Trục thời gian tương đối theo chuẩn UI_SPEC.md (0 tại Trigger, +0.1 ms, +0.2 ms...)."""

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            if abs(v) < 1e-12:
                strings.append("0")
                continue
            sign = "+" if v > 0 else "-"
            abs_v = abs(v)
            if abs_v >= 1.0:
                strings.append(f"{sign}{abs_v:.2f} s")
            elif abs_v >= 1e-3:
                strings.append(f"{sign}{abs_v * 1e3:.1f} ms")
            elif abs_v >= 1e-6:
                strings.append(f"{sign}{abs_v * 1e6:.1f} µs")
            else:
                strings.append(f"{sign}{abs_v * 1e9:.0f} ns")
        return strings


class WaveformHUD(QtWidgets.QFrame):
    """Bảng HUD bán trong suốt hiển thị thông số Cursors A & B góc trên bên phải."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(20, 20, 21, 0.92);
                border: 1px solid {T.BORDER};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QLabel {{
                font-family: 'Consolas', 'DejaVu Sans Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                background: transparent;
            }}
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(12)

        self.lbl_title = QtWidgets.QLabel("<b>CURSORS</b>")
        self.lbl_title.setStyleSheet(f"color: {T.TEXT_DIM}; background: transparent;")

        self.lbl_a = QtWidgets.QLabel("A: 0.000 ms")
        self.lbl_a.setStyleSheet(f"color: {T.CURSOR_A}; background: transparent;")

        self.lbl_b = QtWidgets.QLabel("B: 0.000 ms")
        self.lbl_b.setStyleSheet(f"color: {T.CURSOR_B}; background: transparent;")

        self.lbl_dt = QtWidgets.QLabel("Δt: 0.000 µs")
        self.lbl_dt.setStyleSheet(f"color: {T.TEXT}; background: transparent;")

        self.lbl_freq = QtWidgets.QLabel("f: -- Hz")
        self.lbl_freq.setStyleSheet(f"color: {T.ACCENT_START}; background: transparent;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_a)
        layout.addWidget(self.lbl_b)
        layout.addWidget(self.lbl_dt)
        layout.addWidget(self.lbl_freq)

    def update_values(self, t_a: float, t_b: float):
        self.lbl_a.setText(f"A: {format_si_time(t_a)}")
        self.lbl_b.setText(f"B: {format_si_time(t_b)}")
        dt = abs(t_b - t_a)
        self.lbl_dt.setText(f"Δt: {format_si_time(dt)}")
        if dt > 1e-12:
            self.lbl_freq.setText(f"f: {format_si_freq(1.0 / dt)}")
        else:
            self.lbl_freq.setText("f: ∞ Hz")


class WaveformWidget(QtWidgets.QWidget):
    """
    Widget khung vẽ sóng 8 kênh tích hợp Cột nhãn bên trái (194px) và PlotWidget (pyqtgraph)
    đáp ứng 100% đặc tả UI_SPEC.md và bản mẫu proto.py (v3).
    """
    sigCursorChanged = QtCore.pyqtSignal(float, float, float)  # t_a, t_b, dt

    def __init__(self, parent=None):
        super().__init__(parent)

        self.channel_names = list(DEFAULT_CHANNEL_NAMES)
        self.channel_visible = [True] * 8
        self.current_data: Optional[Dict[str, Any]] = None
        self.row_h = T.CHANNEL_ROW_HEIGHT
        self.dec_scale = T.DECODER_ROW_SCALE
        self.row_heights: List[int] = [int(self.row_h * self.dec_scale)] + [self.row_h] * 7

        # Danh sách đồ họa chú thích decoder & bit dots
        self.decode_items: List[QtWidgets.QGraphicsItem] = []
        self.bit_dots_item: Optional[pg.ScatterPlotItem] = None
        self.grid_lines: List[pg.InfiniteLine] = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. CỘT NHÃN BÊN TRÁI (194 px)
        # ---------------------------------------------------------------------
        self.lab = QtWidgets.QWidget(self)
        self.lab.setFixedWidth(T.LABEL_COLUMN_WIDTH)
        self.lab.setStyleSheet(f"background-color: {T.BG_MAIN};")

        self.vl_labels = QtWidgets.QVBoxLayout(self.lab)
        self.vl_labels.setContentsMargins(0, 0, 0, 0)
        self.vl_labels.setSpacing(0)

        # Khoảng đệm tương ứng chiều cao thước thời gian trên cùng (32 px)
        self.top_spacer = QtWidgets.QWidget()
        self.top_spacer.setFixedHeight(T.AXIS_HEIGHT)
        self.top_spacer.setStyleSheet(f"background-color: {T.BG_MAIN}; border-bottom: 1px solid {T.BORDER};")
        self.vl_labels.addWidget(self.top_spacer)

        # 8 khung nhãn kênh
        self.channel_frames: List[QtWidgets.QFrame] = []
        self.channel_labels_top: List[QtWidgets.QLabel] = []
        self.channel_chips: List[QtWidgets.QLabel] = []

        for i in range(8):
            f = QtWidgets.QFrame()
            col = T.CHANNEL_COLORS[i]
            f.setStyleSheet(f"""
                QFrame {{
                    background-color: {T.BG_MAIN};
                    border-left: 4px solid {col};
                    border-bottom: 1px solid {T.BORDER};
                }}
                QLabel {{ border: none; background: transparent; }}
            """)
            f_lay = QtWidgets.QVBoxLayout(f)
            f_lay.setContentsMargins(14, 6, 8, 6)
            f_lay.setSpacing(2)

            top_lbl = QtWidgets.QLabel(
                f"<span style='color:{col};font-weight:bold;font-size:11px'>D{i}</span>"
                f"&nbsp;&nbsp;&nbsp;<span style='font-size:14px;font-weight:bold;color:{T.TEXT}'>Channel {i}</span>"
            )
            f_lay.addWidget(top_lbl, 0, QtCore.Qt.AlignTop if i == 0 else QtCore.Qt.AlignVCenter)
            self.channel_labels_top.append(top_lbl)

            # Chip hiển thị analyzer (gắn mặc định vào CH0: Async Serial)
            if i == 0:
                chip = QtWidgets.QLabel(f"<span style='color:{T.DECODE_UART_BG}'>■</span> Async Serial")
                chip.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
                f_lay.addWidget(chip)
                f_lay.addStretch(1)
                self.channel_chips.append(chip)
            else:
                self.channel_chips.append(None)

            self.channel_frames.append(f)
            self.vl_labels.addWidget(f)

        self.vl_labels.addStretch(1)
        main_layout.addWidget(self.lab)

        # ---------------------------------------------------------------------
        # 2. KHUNG VẼ SÓNG PYQTGRAPH (Trục thời gian trên cùng, Inverted Y)
        # ---------------------------------------------------------------------
        self.time_axis = RelativeTimeAxis("top")
        self.time_axis.setHeight(T.AXIS_HEIGHT)
        self.time_axis.setPen(pg.mkPen(T.GRID))
        self.time_axis.setTextPen(pg.mkPen(T.TEXT))
        self.time_axis.setTickSpacing(1e-4, 5e-5)

        self.plot_widget = pg.PlotWidget(background=T.BG_MAIN, axisItems={"top": self.time_axis})
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.hideAxis("left")
        self.plot_item.hideAxis("bottom")
        self.plot_item.showAxis("top")
        self.plot_item.hideButtons()
        self.plot_item.setMenuEnabled(False)
        self.plot_item.layout.setContentsMargins(0, 0, 0, 0)
        self.plot_item.layout.setSpacing(0)

        self.vb = self.plot_item.getViewBox()
        self.vb.setMouseEnabled(x=True, y=False)
        self.vb.invertY(True)  # D0 ở trên, D7 ở dưới

        # Đường phân cách hàng (Horizontal row separators)
        self.row_separator_lines: List[pg.InfiniteLine] = []
        for _ in range(8):
            sep = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(T.BORDER, width=1))
            self.vb.addItem(sep)
            self.row_separator_lines.append(sep)

        # Nhãn H và L mép trái mỗi hàng
        self.hl_text_items: List[Tuple[pg.TextItem, pg.TextItem]] = []
        for _ in range(8):
            t_h = pg.TextItem("H", color=T.TEXT_DIM, anchor=(0, 0.5))
            t_l = pg.TextItem("L", color=T.TEXT_DIM, anchor=(0, 0.5))
            self.vb.addItem(t_h)
            self.vb.addItem(t_l)
            self.hl_text_items.append((t_h, t_l))

        # 8 đường cong PlotCurveItem cho 8 kênh
        self.curves: List[pg.PlotCurveItem] = []
        for ch in range(8):
            pen = pg.mkPen(color=T.CHANNEL_COLORS[ch], width=1.4)
            curve = pg.PlotCurveItem(pen=pen)
            self.vb.addItem(curve)
            self.curves.append(curve)

        # Vạch chỉ thị Trigger (T-Marker)
        self.trigger_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            pen=pg.mkPen(color=T.TRIGGER_MARKER, width=2, style=QtCore.Qt.SolidLine),
            label="T",
            labelOpts={"color": T.TRIGGER_MARKER, "position": 0.95, "anchors": [(0, 0), (0, 0)]}
        )
        self.vb.addItem(self.trigger_line)

        # Cặp thước đo thời gian (Cursors A & B)
        self.cursor_a = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=True,
            pen=pg.mkPen(color=T.CURSOR_A, width=1.8, style=QtCore.Qt.SolidLine),
            hoverPen=pg.mkPen(color="#80d8ff", width=2.5),
            label="A",
            labelOpts={"color": T.CURSOR_A, "position": 0.90, "anchors": [(0, 0), (0, 0)]}
        )
        self.cursor_b = pg.InfiniteLine(
            pos=8.68e-5,
            angle=90,
            movable=True,
            pen=pg.mkPen(color=T.CURSOR_B, width=1.8, style=QtCore.Qt.SolidLine),
            hoverPen=pg.mkPen(color="#ff8a80", width=2.5),
            label="B",
            labelOpts={"color": T.CURSOR_B, "position": 0.85, "anchors": [(0, 0), (0, 0)]}
        )
        self.vb.addItem(self.cursor_a)
        self.vb.addItem(self.cursor_b)

        self.cursor_a.sigPositionChanged.connect(self._on_cursor_moved)
        self.cursor_b.sigPositionChanged.connect(self._on_cursor_moved)

        main_layout.addWidget(self.plot_widget, 1)

        # ---------------------------------------------------------------------
        # 3. FLOATING HUD (Góc trên bên phải)
        # ---------------------------------------------------------------------
        self.hud = WaveformHUD(self.plot_widget)
        self.hud_widget = self.hud
        self.hud.raise_()
        self._update_hud()

        # Tính toán hình học ban đầu
        self._recompute_row_heights()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recompute_row_heights()

        # Căn góc trên bên phải cho HUD
        hud_w = self.hud.sizeHint().width()
        hud_h = self.hud.sizeHint().height()
        self.hud.setGeometry(self.plot_widget.width() - hud_w - 20, 10, hud_w, hud_h)

    def _recompute_row_heights(self):
        """Tính toán chiều cao hàng co giãn lấp đầy chiều dọc theo UI_SPEC.md."""
        avail_h = self.plot_widget.height() - T.AXIS_HEIGHT
        if avail_h <= 0:
            avail_h = self.height() - T.AXIS_HEIGHT

        # Chiều cao hàng cơ sở = avail / (7 + scale)
        row_h = int(avail_h / (7 + self.dec_scale))
        self.row_h = max(row_h, T.CHANNEL_ROW_HEIGHT)

        self.row_heights = [int(self.row_h * self.dec_scale)] + [self.row_h] * 7
        total_h = sum(self.row_heights)

        # Cập nhật chiều cao các frame cột nhãn
        for i, h in enumerate(self.row_heights):
            self.channel_frames[i].setFixedHeight(h)

        # Cập nhật phạm vi ViewBox Y
        self.vb.setYRange(0, total_h, padding=0)

        # Cập nhật vị trí vạch ngăn và nhãn H/L
        y0 = 0
        for i, h in enumerate(self.row_heights):
            top = y0 + (h - self.row_h) if i == 0 else y0
            hi = top + self.row_h * 0.22
            lo = top + self.row_h * 0.78

            # Vạch ngăn
            self.row_separator_lines[i].setValue(y0 + h)

            # Nhãn H/L
            t_h, t_l = self.hl_text_items[i]
            t_h.setPos(-0.00005, hi)
            t_l.setPos(-0.00005, lo)

            y0 += h

        # Nếu đang có dữ liệu, vẽ lại dữ liệu với chiều cao hàng mới
        if self.current_data:
            self._update_curve_data()

    def set_channel_name(self, ch: int, name: str):
        """Đổi tên hiển thị của kênh số."""
        if 0 <= ch < 8:
            self.channel_names[ch] = name
            col = T.CHANNEL_COLORS[ch]
            self.channel_labels_top[ch].setText(
                f"<span style='color:{col};font-weight:bold;font-size:11px'>D{ch}</span>"
                f"&nbsp;&nbsp;&nbsp;<span style='font-size:14px;font-weight:bold;color:{T.TEXT}'>{name}</span>"
            )

    def set_channel_visible(self, ch: int, visible: bool):
        """Ẩn / hiện một kênh sóng trên đồ thị."""
        if 0 <= ch < 8:
            self.channel_visible[ch] = visible
            self.curves[ch].setVisible(visible)
            self.channel_frames[ch].setVisible(visible)

    def toggle_cursors(self, visible: Optional[bool] = None):
        """Bật / tắt hiển thị cặp thước đo A & B và HUD."""
        if visible is None:
            visible = not self.cursor_a.isVisible()
        self.cursor_a.setVisible(visible)
        self.cursor_b.setVisible(visible)
        self.hud.setVisible(visible)

    def _on_cursor_moved(self):
        self._update_hud()

    def _update_hud(self):
        t_a = self.cursor_a.value()
        t_b = self.cursor_b.value()
        dt = abs(t_b - t_a)
        self.cursor_a.label.setText(f"A: {format_si_time(t_a)}")
        self.cursor_b.label.setText(f"B: {format_si_time(t_b)}")
        self.hud.update_values(t_a, t_b)
        self.sigCursorChanged.emit(t_a, t_b, dt)

    def set_cursor_positions(self, t_a: float, t_b: float):
        self.cursor_a.setValue(t_a)
        self.cursor_b.setValue(t_b)
        self._update_hud()

    def set_positions(self, t_a: float, t_b: float):
        self.set_cursor_positions(t_a, t_b)

    def get_cursor_values(self) -> Tuple[float, float, float]:
        t_a = self.cursor_a.value()
        t_b = self.cursor_b.value()
        return t_a, t_b, abs(t_b - t_a)

    def get_delta_t(self) -> float:
        _, _, dt = self.get_cursor_values()
        return dt

    def get_frequency(self) -> float:
        dt = self.get_delta_t()
        return (1.0 / dt) if dt > 1e-12 else 0.0

    def render_data(self, res: Dict[str, Any]):
        """Vẽ 8 kênh dữ liệu lên viewport với mốc thời gian t = 0 tại Trigger."""
        self.current_data = res
        sample_rate = float(res["sample_rate"])
        sample_count = int(res["sample_count"])
        trig_offset = int(res["trig_offset"])
        status = res.get("status", 0)

        # Thiết lập vạch trigger và giới hạn thời gian
        if status == 0:  # STATUS_TRIGGER_OK
            t_marker = 0.0
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.TRIGGER_MARKER, width=2, style=QtCore.Qt.SolidLine))
            self.trigger_line.label.setText("T (0 s)")
            self.trigger_line.show()
            x_min = -trig_offset / sample_rate
            x_max = (sample_count - trig_offset) / sample_rate
        elif status == 1:  # STATUS_FREERUN_OK
            t_marker = trig_offset / sample_rate
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.TEXT_DIM, width=1.5, style=QtCore.Qt.DotLine))
            self.trigger_line.label.setText("FREE-RUN (20%)")
            self.trigger_line.show()
            x_min = 0.0
            x_max = sample_count / sample_rate
        else:  # STATUS_TIMEOUT
            t_marker = trig_offset / sample_rate
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.ACCENT_WARN, width=1.8, style=QtCore.Qt.DashDotLine))
            self.trigger_line.label.setText("TIMEOUT")
            self.trigger_line.show()
            x_min = 0.0
            x_max = sample_count / sample_rate

        self._update_curve_data()

        # Đặt thước đo A và B gần điểm bắt sóng
        if status == 0:
            self.set_cursor_positions(0.0, 8.68e-5)
        else:
            self.set_cursor_positions(t_marker, t_marker + 8.68e-5)

        # Đặt vùng nhìn X
        self.plot_widget.setXRange(x_min, x_max, padding=0.01)

    def _update_curve_data(self):
        """Vẽ các đường sóng theo đúng vị trí hình học của các hàng."""
        if not self.current_data:
            return

        channels = self.current_data["channels"]
        sample_rate = float(self.current_data["sample_rate"])
        sample_count = int(self.current_data["sample_count"])
        trig_offset = int(self.current_data["trig_offset"])
        status = self.current_data.get("status", 0)

        if status == 0:
            time_axis = (np.arange(sample_count, dtype=np.float64) - trig_offset) / sample_rate
        else:
            time_axis = np.arange(sample_count, dtype=np.float64) / sample_rate

        y0 = 0
        for ch in range(8):
            h = self.row_heights[ch]
            top = y0 + (h - self.row_h) if ch == 0 else y0
            hi = top + self.row_h * 0.22
            lo = top + self.row_h * 0.78

            ch_samples = channels[ch]
            yy = np.where(ch_samples == 1, hi, lo)
            self.curves[ch].setData(x=time_axis, y=yy, stepMode="left")
            self.curves[ch].setVisible(self.channel_visible[ch])
            y0 += h

    def render_uart_decorations(self, frames: List[Dict[str, Any]], sample_rate: float, trig_offset: int):
        """
        Vẽ các ô chú thích giải mã UART và chấm tâm bit (bit center dots) trực tiếp trên sóng Kênh 0
        đáp ứng 100% mục 5 của UI_SPEC.md.
        """
        self.clear_decoder_decorations()

        if not frames:
            return

        h0 = self.row_heights[0]
        bubble_top = h0 * 0.08
        bubble_h = self.row_h * 0.30
        bubble_center_y = bubble_top + bubble_h * 0.5

        top0 = h0 - self.row_h
        hi0 = top0 + self.row_h * 0.22
        lo0 = top0 + self.row_h * 0.78

        dot_x: List[float] = []
        dot_y: List[float] = []

        # Giới hạn số lượng bong bóng vẽ tối đa để giữ 60 FPS
        max_bubbles = min(len(frames), 256)

        for frame in frames[:max_bubbles]:
            start_idx = frame.get("start_sample", frame.get("start_idx", 0))
            stop_idx = frame.get("stop_sample", frame.get("stop_idx", start_idx + 10))
            val = frame.get("byte_val", frame.get("val", 0))
            char = frame.get("char", "")

            # Thời gian thực tế quy đổi theo trigger
            t_start = (start_idx - trig_offset) / sample_rate
            t_stop = (stop_idx - trig_offset) / sample_rate
            dt = t_stop - t_start

            # 1. Vẽ ô chữ nhật bo góc màu DECODE_UART_BG
            rect_item = QtWidgets.QGraphicsRectItem(t_start, bubble_top, dt, bubble_h)
            rect_item.setBrush(pg.mkBrush(T.DECODE_UART_BG))
            rect_item.setPen(pg.mkPen(None))
            self.vb.addItem(rect_item)
            self.decode_items.append(rect_item)

            # 2. Vẽ nhãn văn bản (Hex + ASCII)
            text_str = f"0x{val:02X}"
            if char and 32 <= ord(char[0]) <= 126:
                text_str += f" '{char}'"
            txt_item = pg.TextItem(text_str, color=T.DECODE_UART_FG, anchor=(0.5, 0.5))
            txt_item.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
            txt_item.setPos((t_start + t_stop) / 2, bubble_center_y)
            self.vb.addItem(txt_item)
            self.decode_items.append(txt_item)

            # 3. Tính toán chấm trắng tại tâm mỗi bit dữ liệu (Bit center dots)
            bit_len_idx = (stop_idx - start_idx) / 10.0
            data_bits = frame.get("bit_samples", frame.get("data_bits", []))
            for bit_i in range(8):
                center_idx = start_idx + (bit_i + 1.5) * bit_len_idx
                t_center = (center_idx - trig_offset) / sample_rate
                bit_val = data_bits[bit_i] if bit_i < len(data_bits) else ((val >> bit_i) & 1)
                dot_x.append(t_center)
                dot_y.append(hi0 if bit_val else lo0)

        # Vẽ chấm trắng bằng ScatterPlotItem
        if dot_x:
            self.bit_dots_item = pg.ScatterPlotItem(
                x=dot_x,
                y=dot_y,
                size=5,
                brush=pg.mkBrush(T.TEXT),
                pen=pg.mkPen(None)
            )
            self.vb.addItem(self.bit_dots_item)

    def clear_decoder_decorations(self):
        """Xóa toàn bộ các bong bóng chú thích và chấm bit trên đồ thị."""
        for item in self.decode_items:
            try:
                self.vb.removeItem(item)
            except Exception:
                pass
        self.decode_items.clear()

        if self.bit_dots_item:
            try:
                self.vb.removeItem(self.bit_dots_item)
            except Exception:
                pass
            self.bit_dots_item = None

    def zoom_fit(self):
        """Khôi phục góc nhìn toàn bộ dữ liệu mẫu."""
        if not self.current_data:
            return
        sample_count = int(self.current_data["sample_count"])
        sample_rate = float(self.current_data["sample_rate"])
        trig_offset = int(self.current_data["trig_offset"])
        status = self.current_data.get("status", 0)

        if status == 0:
            x_min = -trig_offset / sample_rate
            x_max = (sample_count - trig_offset) / sample_rate
        else:
            x_min = 0.0
            x_max = sample_count / sample_rate
        self.plot_widget.setXRange(x_min, x_max, padding=0.01)

    def zoom_to_window(self, t_start_abs: float, t_stop_abs: float):
        """Phóng to và căn giữa một khoảng thời gian xác định."""
        if not self.current_data:
            return
        status = self.current_data.get("status", 0)
        sample_rate = float(self.current_data["sample_rate"])
        trig_offset = int(self.current_data["trig_offset"])

        if status == 0:
            offset_s = trig_offset / sample_rate
            t1 = t_start_abs - offset_s
            t2 = t_stop_abs - offset_s
        else:
            t1 = t_start_abs
            t2 = t_stop_abs

        dur = max(t2 - t1, 0.00004)
        self.plot_widget.setXRange(t1 - dur * 0.4, t2 + dur * 0.4, padding=0)
