#!/usr/bin/env python3
"""software/gui/waveform_widget.py
Khung vẽ sóng logic 8 kênh (Waveform Viewport) theo chuẩn UI_SPEC.md:
- Cột nhãn bên trái (180 px) với dải màu 4 px, nhãn D0..D7, tên kênh và chip analyzer.
- Trục thời gian trên cùng (32 px) với mốc tương đối (+0.1 ms, +0.2 ms...), 0 tại Trigger.
- 8 track kênh số co giãn lấp đầy chiều cao (track có analyzer = 1.35x track thường).
- Nền canvas #1b1b1c, đường phân cách mỏng #57575e giữa các track.
- Dạng sóng số vẽ bằng stepMode="right", màu lấy từ theme.CHANNEL_COLORS.
- Nhãn H và L ở mép trái mỗi track sóng, bám sát khung nhìn khi pan/zoom.
- Vạch Trigger dọc màu vàng #fff06a và cờ trigger cam #f1994b tại mẫu 6554 (mốc t = 0 s).
- Khối giải mã (Inline Annotation Blocks) dạng chữ nhật phẳng trực tiếp trên dải decoder.
- Cặp thước đo thời gian (Cursor A & Cursor B) kéo thả chuột kèm HUD tính Δt và f.
"""

from typing import Optional, Dict, Any, List, Tuple, Callable
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from software.gui import theme as T

DEFAULT_CHANNEL_NAMES = [f"Channel {i}" for i in range(8)]
_BUBBLE_FONT_FAMILY: Optional[str] = None


def _get_bubble_font_family() -> str:
    """Lấy và lưu cache tên font tối ưu cho bong bóng giải mã (chỉ truy vấn QFontDatabase 1 lần)."""
    global _BUBBLE_FONT_FAMILY
    if _BUBBLE_FONT_FAMILY is None:
        _BUBBLE_FONT_FAMILY = (
            "Roboto Condensed" if "Roboto Condensed" in QtGui.QFontDatabase().families() else "Roboto"
        )
    return _BUBBLE_FONT_FAMILY


class HoverSeparatorLine(pg.InfiniteLine):
    """Đường phân cách track sóng sáng lên màu trắng mờ rgba(255, 255, 255, 0.6) khi rê chuột hover qua."""
    def hoverEvent(self, ev):
        if not ev.isExit():
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)


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

    def paint(self, p, opt, widget):
        p.save()
        axis_rect = QtCore.QRectF(0, 0, self.width(), self.height())
        p.fillRect(axis_rect, QtGui.QColor(T.BG_HEADER))
        p.restore()
        super().paint(p, opt, widget)

    def tickValues(self, minVal, maxVal, size):
        ticks = super().tickValues(minVal, maxVal, size)
        if not ticks:
            return ticks
        span = max(1e-12, abs(maxVal - minVal))
        # Chỉ giữ các mức tick có khoảng cách pixel >= 45px để grid nét đứt thoáng, đẹp
        filtered = []
        for spacing, values in ticks:
            px_dist = size * spacing / span
            if px_dist >= 45.0 or len(filtered) == 0:
                filtered.append((spacing, values))
            if len(filtered) >= 2:
                break
        return filtered

    def tickStrings(self, values, scale, spacing):
        strings = []
        has_negative = any(v < -1e-12 for v in values)
        for v in values:
            if abs(v) < 1e-12:
                strings.append("0")
                continue
            sign = ("+" if has_negative else "") if v > 0 else "-"
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


class PillBubbleItem(QtWidgets.QGraphicsItem):
    """Bong bóng giải mã (Inline Annotation Bubble) dạng khối chữ nhật phẳng:
    - Co rút văn bản thích ứng 3 cấp (Adaptive Text Truncation: text_full -> text_mid -> text_short -> hide).
    - Tương tác chuột phong phú: Hover tooltip, Click zoom, Ctrl+Click chọn dòng trong Data Table, Right-click context menu.
    """

    def __init__(
        self,
        t_start: float,
        t_stop: float,
        y_top: float,
        height: float,
        text: str,
        bg_color: str,
        text_color: str,
        radius: float = 0.0,
        tooltip: str = "",
        text_mid: str = "",
        text_short: str = "",
        raw_data: Optional[Dict[str, Any]] = None,
        on_clicked: Optional[Callable[[], None]] = None,
        on_ctrl_clicked: Optional[Callable[[], None]] = None
    ):
        super().__init__()
        self.t_start = t_start
        self.t_stop = t_stop
        self.y_top = y_top
        self.height = height
        self.text_full = text
        self.text_mid = text_mid or text
        self.text_short = text_short or (text[:2] if len(text) >= 2 else text)
        self.raw_data = raw_data or {}
        self.bg_brush = QtGui.QBrush(QtGui.QColor(bg_color))
        self.text_color = QtGui.QColor(text_color)
        self.radius = radius
        self.on_clicked = on_clicked
        self.on_ctrl_clicked = on_ctrl_clicked
        self.is_hovered = False
        self.setAcceptHoverEvents(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.font = QtGui.QFont(_get_bubble_font_family())
        self.font.setPixelSize(11)
        self.font.setBold(True)
        if tooltip:
            full_tip = tooltip + "\n\n💡 Click: Zoom to Frame | Ctrl+Click: Select in Data Table | Right-Click: Context Menu"
            self.setToolTip(full_tip)

    def boundingRect(self) -> QtCore.QRectF:
        dt = max(1e-12, self.t_stop - self.t_start)
        return QtCore.QRectF(self.t_start, self.y_top, dt, self.height)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if (event.modifiers() & QtCore.Qt.ControlModifier) and self.on_ctrl_clicked:
                self.on_ctrl_clicked()
                event.accept()
                return
            elif self.on_clicked:
                self.on_clicked()
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
                padding: 4px 0px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {T.TEXT};
                padding: 6px 20px 6px 12px;
                font-family: 'Roboto', sans-serif;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {T.BORDER_MUTED};
                margin: 4px 6px;
            }}
        """)

        val = self.raw_data.get("val", self.raw_data.get("byte_val"))
        char = self.raw_data.get("char", "")
        t_start = self.t_start

        act_hex = menu.addAction(f"Copy Hex (0x{val:02X})") if val is not None else None
        act_char = menu.addAction(f"Copy Character ('{char}')") if char else None
        act_time = menu.addAction(f"Copy Timestamp ({format_si_time(t_start)})")
        menu.addSeparator()
        act_zoom = menu.addAction("🔍 Zoom to Frame")
        act_table = menu.addAction("📋 Select in Data Table (Ctrl+Click)")

        chosen = menu.exec_(event.screenPos())
        if chosen and chosen == act_hex and val is not None:
            QtWidgets.QApplication.clipboard().setText(f"0x{val:02X}")
        elif chosen and chosen == act_char and char:
            QtWidgets.QApplication.clipboard().setText(char)
        elif chosen and chosen == act_time:
            QtWidgets.QApplication.clipboard().setText(format_si_time(t_start))
        elif chosen and chosen == act_zoom and self.on_clicked:
            self.on_clicked()
        elif chosen and chosen == act_table and self.on_ctrl_clicked:
            self.on_ctrl_clicked()

        event.accept()

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        painter.save()
        # Chuyển đổi tọa độ scene/view sang pixel thiết bị màn hình
        p1 = painter.worldTransform().map(QtCore.QPointF(self.t_start, self.y_top))
        p2 = painter.worldTransform().map(QtCore.QPointF(self.t_stop, self.y_top + self.height))

        px_left = min(p1.x(), p2.x())
        px_right = max(p1.x(), p2.x())
        px_top = min(p1.y(), p2.y())
        px_bottom = max(p1.y(), p2.y())
        w = px_right - px_left
        h = px_bottom - px_top

        # Vẽ trong hệ tọa độ pixel để khối chữ nhật sắc nét không bị méo theo tỷ lệ thời gian
        painter.setTransform(QtGui.QTransform())
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True if self.radius > 0 else False)

        if w >= 2.0:
            rect = QtCore.QRectF(px_left, px_top, w, h)
            painter.setBrush(self.bg_brush)
            if self.is_hovered:
                painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.5))
            else:
                # Viền tối mảnh 1px phân tách các gói tin liền kề
                painter.setPen(QtGui.QPen(QtGui.QColor("#1b1b1c"), 1.0))

            if self.radius > 0:
                r = min(self.radius, h / 2.0, w / 2.0)
                painter.drawRoundedRect(rect, r, r)
            else:
                painter.drawRect(rect)

            # Thuật toán co rút văn bản thích ứng 3 cấp độ (Adaptive Text Truncation)
            if w >= 48.0:
                display_txt = self.text_full
            elif w >= 24.0:
                display_txt = self.text_mid
            elif w >= 12.0:
                display_txt = self.text_short
            else:
                display_txt = ""

            if display_txt:
                painter.setPen(self.text_color)
                painter.setFont(self.font)
                painter.drawText(rect, QtCore.Qt.AlignCenter, display_txt)

        painter.restore()


class MultiBubbleItem(QtWidgets.QGraphicsItem):
    """
    Bong bóng gộp cụm (MultiBubble):
    Khi Zoom xa (khoảng cách giữa các byte quá nhỏ), tự động gộp các byte liên tiếp lại
    thành một khối kèm Badge đếm số lượng [N] và xem trước chuỗi.
    """

    def __init__(
        self,
        t_start: float,
        t_stop: float,
        y_top: float,
        height: float,
        count: int,
        preview_text: str,
        bg_color: str,
        text_color: str,
        tooltip: str = "",
        on_clicked: Optional[Callable[[], None]] = None
    ):
        super().__init__()
        self.t_start = t_start
        self.t_stop = t_stop
        self.y_top = y_top
        self.height = height
        self.count = count
        self.preview_text = preview_text
        self.bg_brush = QtGui.QBrush(QtGui.QColor(bg_color))
        self.text_color = QtGui.QColor(text_color)
        self.on_clicked = on_clicked
        self.is_hovered = False
        self.setAcceptHoverEvents(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.badge_font = QtGui.QFont("Roboto", 8, QtGui.QFont.Bold)
        self.badge_font.setPixelSize(9)
        self.preview_font = QtGui.QFont(_get_bubble_font_family())
        self.preview_font.setPixelSize(10)
        self.preview_font.setBold(True)
        if tooltip:
            self.setToolTip(tooltip + "\n\n💡 Click / Double-click: Zoom In to Cluster")

    def boundingRect(self) -> QtCore.QRectF:
        dt = max(1e-12, self.t_stop - self.t_start)
        return QtCore.QRectF(self.t_start, self.y_top, dt, self.height)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.on_clicked:
            self.on_clicked()
            event.accept()
        else:
            super().mousePressEvent(event)

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        painter.save()
        p1 = painter.worldTransform().map(QtCore.QPointF(self.t_start, self.y_top))
        p2 = painter.worldTransform().map(QtCore.QPointF(self.t_stop, self.y_top + self.height))

        px_left = min(p1.x(), p2.x())
        px_right = max(p1.x(), p2.x())
        px_top = min(p1.y(), p2.y())
        px_bottom = max(p1.y(), p2.y())
        w = max(4.0, px_right - px_left)
        h = px_bottom - px_top

        painter.setTransform(QtGui.QTransform())
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)

        rect = QtCore.QRectF(px_left, px_top, w, h)
        painter.setBrush(self.bg_brush)
        if self.is_hovered:
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.5))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor("#1b1b1c"), 1.0))
        painter.drawRect(rect)

        # Badge đếm số lượng gói [N] (bubbleCounterStyle)
        badge_str = f"[{self.count}]" if self.count <= 99 else "[99+]"

        if w >= 26.0:
            badge_w = 22.0 if self.count <= 99 else 28.0
            badge_rect = QtCore.QRectF(px_left + 2, px_top + 2, badge_w, h - 4)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#242528")))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(badge_rect, 3.0, 3.0)

            painter.setPen(QtGui.QColor("#ffffff"))
            painter.setFont(self.badge_font)
            painter.drawText(badge_rect, QtCore.Qt.AlignCenter, badge_str)

            # Vẽ text xem trước bên cạnh badge nếu còn đủ chỗ
            if w >= 65.0 and self.preview_text:
                text_rect = QtCore.QRectF(px_left + badge_w + 5, px_top, w - badge_w - 7, h)
                painter.setPen(self.text_color)
                painter.setFont(self.preview_font)
                painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.preview_text)

        painter.restore()


class WaveformHUD(QtWidgets.QFrame):
    """Bảng HUD bán trong suốt hiển thị thông số Cursors A & B góc trên bên phải."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("waveformHud")
        self.setStyleSheet(f"""
            QFrame#waveformHud {{
                background-color: {T.TOOLTIP_BG};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QLabel {{
                font-family: 'Consolas', 'DejaVu Sans Mono', monospace;
                font-size: 11px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(12)

        self.lbl_title = QtWidgets.QLabel("<b>CURSORS</b>")
        self.lbl_title.setStyleSheet(f"color: {T.TEXT_DIM}; background: transparent; border: none;")

        self.lbl_a = QtWidgets.QLabel("A: 0.000 ms")
        self.lbl_a.setStyleSheet(f"color: {T.CURSOR_A}; background: transparent; border: none;")

        self.lbl_b = QtWidgets.QLabel("B: 0.000 ms")
        self.lbl_b.setStyleSheet(f"color: {T.CURSOR_B}; background: transparent; border: none;")

        self.lbl_dt = QtWidgets.QLabel("Δt: 0.000 µs")
        self.lbl_dt.setStyleSheet(f"color: {T.TEXT}; background: transparent; border: none;")

        self.lbl_freq = QtWidgets.QLabel("f: -- Hz")
        self.lbl_freq.setStyleSheet(f"color: {T.ACCENT_START}; background: transparent; border: none;")

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
        if self.parentWidget() is not None:
            self.adjustSize()
            hud_w = max(self.sizeHint().width() + 28, 395)
            hud_h = max(self.sizeHint().height(), 26)
            self.setGeometry(self.parentWidget().width() - hud_w - 16, self.parentWidget().height() - hud_h - 10, hud_w, hud_h)


class WaveformWidget(QtWidgets.QWidget):
    """
    Widget khung vẽ sóng 8 kênh tích hợp Cột nhãn bên trái (180px) và PlotWidget (pyqtgraph)
    đáp ứng 100% đặc tả UI_SPEC.md:
    - Nền canvas #1b1b1c.
    - 8 track kênh tự co giãn lấp đầy chiều cao.
    - Dạng sóng số stepMode="right".
    - Nhãn H/L và vạch phân cách mỏng #57575e.
    - Vạch Trigger vàng #fff06a và cờ trigger cam #f1994b tại mẫu 6554 (t = 0 s).
    - Bong bóng giải mã trực tiếp trên track sóng.
    """
    sigCursorChanged = QtCore.pyqtSignal(float, float, float)  # t_a, t_b, dt
    sigXRangeChanged = QtCore.pyqtSignal(float, float)        # x_min, x_max
    sigBubbleCtrlClicked = QtCore.pyqtSignal(int, dict)        # (frame_idx, frame_dict)
    sigQuickMeasureState = QtCore.pyqtSignal(bool, str)        # (active, prompt_message)
    sigHoverTimestamp = QtCore.pyqtSignal(float, int, int)     # (t_sec, sample_idx, raw_byte_val)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.channel_names = list(DEFAULT_CHANNEL_NAMES)
        self.channel_visible = [True] * 8
        self.current_data: Optional[Dict[str, Any]] = None
        self.row_h = T.CHANNEL_ROW_HEIGHT
        self.dec_scale = T.DECODER_ROW_SCALE
        self.row_heights: List[int] = [int(self.row_h * self.dec_scale)] + [self.row_h] * 7

        # Hệ thống Magnetic Snap-to-Edge & Quick Measure Tool (chuẩn UI_SPEC.md Mục 7)
        self.snap_enabled: bool = True
        self.snap_radius_px: float = 15.0
        self.channel_edges: Dict[int, np.ndarray] = {i: np.array([], dtype=np.float64) for i in range(8)}
        self.decoder_edges: Dict[int, np.ndarray] = {i: np.array([], dtype=np.float64) for i in range(8)}
        self.all_edges: np.ndarray = np.array([], dtype=np.float64)
        self.current_time_axis: Optional[np.ndarray] = None
        self.hovered_channel: int = -1
        self.active_inspect_channel: int = 0
        self._is_snapping: bool = False

        # Trạng thái Quick Measure Tool (2-Click Measurement)
        self.quick_measure_active: bool = False
        self.quick_measure_step: int = 0  # 0: Idle, 1: Waiting A click, 2: Waiting B click
        self.quick_measure_t1: float = 0.0

        # Lưu trữ frame UART phục vụ cơ chế chuyển đổi MultiBubble <-> SingleBubble khi Zoom
        self._uart_frames: List[Dict[str, Any]] = []
        self._uart_sample_rate: float = 1_000_000.0
        self._uart_trig_offset: int = 6554
        self._is_multibubble: bool = False

        # Danh sách đồ họa chú thích decoder & bit dots
        self.decode_items: List[QtWidgets.QGraphicsItem] = []
        self.bit_dots_item: Optional[pg.ScatterPlotItem] = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. CỘT NHÃN BÊN TRÁI (180 px, chuẩn UI_SPEC.md)
        # ---------------------------------------------------------------------
        self.lab = QtWidgets.QWidget(self)
        self.lab.setObjectName("channelLabelColumn")
        self.lab.setFixedWidth(T.LABEL_COLUMN_WIDTH)
        self.lab.setStyleSheet(f"#channelLabelColumn {{ background-color: {T.BG_MAIN}; border-right: 1px solid {T.BORDER_MUTED}; }}")

        self.vl_labels = QtWidgets.QVBoxLayout(self.lab)
        self.vl_labels.setContentsMargins(0, 0, 0, 0)
        self.vl_labels.setSpacing(0)

        # Khoảng đệm tương ứng chiều cao thước thời gian trên cùng (32 px, channelLabelHeader)
        self.top_spacer = QtWidgets.QWidget()
        self.top_spacer.setFixedHeight(T.AXIS_HEIGHT)
        self.top_spacer.setStyleSheet(f"background-color: {T.BG_HEADER}; border-right: 1px solid {T.BORDER_MUTED}; border-bottom: 1px solid {T.BORDER_MUTED};")
        self.vl_labels.addWidget(self.top_spacer)

        # 8 khung nhãn kênh
        self.channel_frames: List[QtWidgets.QFrame] = []
        self.channel_labels_top: List[QtWidgets.QLabel] = []
        self.channel_chips: List[QtWidgets.QLabel] = []
        self.channel_menu_buttons: List[QtWidgets.QToolButton] = []

        for i in range(8):
            f = QtWidgets.QFrame()
            col = T.CHANNEL_COLORS[i]
            f.setStyleSheet(f"""
                QFrame {{
                    background-color: {T.BG_MAIN};
                    border-left: 4px solid {col};
                    border-bottom: 1px solid {T.BORDER_MUTED};
                }}
                QFrame:hover {{
                    background-color: {T.BG_SELECT};
                }}
                QLabel {{ border: none; background: transparent; }}
            """)
            f_lay = QtWidgets.QVBoxLayout(f)
            f_lay.setContentsMargins(12, 6, 8, 6)
            f_lay.setSpacing(2)

            h_ch = QtWidgets.QHBoxLayout()
            h_ch.setContentsMargins(0, 0, 0, 0)
            h_ch.setSpacing(4)

            top_lbl = QtWidgets.QLabel(
                f"<span style=\"color:{col};font-family:'Roboto Condensed','Roboto',sans-serif;font-weight:700;font-size:11px;letter-spacing:0.165px;\">D{i}</span>"
                f"&nbsp;&nbsp;&nbsp;<span style=\"font-family:'Roboto',sans-serif;font-size:13px;font-weight:500;letter-spacing:0.065px;color:{T.TEXT};\">Channel {i}</span>"
            )
            h_ch.addWidget(top_lbl, 1)

            # Nút Menu kênh [...] tùy chọn cho từng kênh số
            btn_menu = QtWidgets.QToolButton()
            btn_menu.setText("•••")
            btn_menu.setToolTip(f"Channel {i} Settings & Options")
            btn_menu.setFixedSize(22, 20)
            btn_menu.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    color: {T.TEXT_MUTED};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 0px;
                }}
                QToolButton:hover {{
                    background-color: {T.BG_SELECT};
                    color: {T.TEXT};
                }}
            """)
            btn_menu.clicked.connect(lambda checked, ch=i, b=btn_menu: self._show_channel_menu(ch, b))
            h_ch.addWidget(btn_menu, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.channel_menu_buttons.append(btn_menu)

            f_lay.addLayout(h_ch)
            self.channel_labels_top.append(top_lbl)

            # Chip hiển thị analyzer (chuẩn hóa đồng nhất cho cả 8 kênh)
            chip = QtWidgets.QLabel(f"<span style='color:{T.DECODE_UART_BG};font-size:9px;'>■</span> &nbsp;Async Serial" if i == 0 else "")
            chip.setStyleSheet(f"color: {T.TEXT_DIM}; font-family: 'Roboto', sans-serif; font-size: 11px;")
            chip.setVisible(i == 0)
            f_lay.addWidget(chip)
            f_lay.addStretch(1)
            self.channel_chips.append(chip)

            self.channel_frames.append(f)
            self.vl_labels.addWidget(f)

        self.vl_labels.addStretch(1)
        main_layout.addWidget(self.lab)

        # ---------------------------------------------------------------------
        # 2. KHUNG VẼ SÓNG PYQTGRAPH (Canvas #1b1b1c, Trục thời gian trên cùng)
        # ---------------------------------------------------------------------
        self.time_axis = RelativeTimeAxis("top")
        self.time_axis.setHeight(T.AXIS_HEIGHT)

        self.plot_widget = pg.PlotWidget(background=T.BG_CANVAS, axisItems={"top": self.time_axis})
        T.configure_pyqtgraph(self.plot_widget)

        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.hideAxis("left")
        self.plot_item.hideAxis("bottom")
        self.plot_item.showAxis("top")
        self.plot_item.hideButtons()
        self.plot_item.setMenuEnabled(False)
        self.plot_item.layout.setContentsMargins(0, 0, 0, 0)
        self.plot_item.layout.setSpacing(0)

        # Cấu hình grid nét đứt (#49494d) và chữ mốc thời gian trắng đậm theo chuẩn UI_SPEC.md
        self.time_axis.setPen(pg.mkPen(T.BORDER_MUTED, width=1))
        self.time_axis.setTextPen(pg.mkPen("#e0e0e0"))
        self.time_axis.setTickPen(pg.mkPen(color=T.GRID_DASH, width=1, style=QtCore.Qt.DashLine))
        self.time_axis.setGrid(255)
        self.time_axis.setStyle(
            tickAlpha=255,
            tickFont=QtGui.QFont(
                "Roboto Mono" if "Roboto Mono" in QtGui.QFontDatabase().families() else "DejaVu Sans Mono",
                8,
                QtGui.QFont.Bold
            )
        )

        self.vb = self.plot_item.getViewBox()
        self.vb.setMouseEnabled(x=True, y=False)
        self.vb.invertY(True)  # D0 ở trên, D7 ở dưới
        self.vb.disableAutoRange(pg.ViewBox.XYAxes)
        self.vb.sigRangeChanged.connect(self._on_view_range_changed)

        # Đường phân cách hàng mỏng theo chuẩn border-20 (#57575e), hover sáng 60% trắng (.resizeHandle:hover)
        self.row_separator_lines: List[HoverSeparatorLine] = []
        for _ in range(8):
            sep = HoverSeparatorLine(
                pos=0,
                angle=0,
                pen=pg.mkPen(T.BORDER_MUTED, width=1),
                hoverPen=pg.mkPen((255, 255, 255, 153), width=1.5),
                movable=False
            )
            sep.setZValue(15)
            self.vb.addItem(sep, ignoreBounds=True)
            self.row_separator_lines.append(sep)

        # Nhãn H và L mép trái mỗi track (@mixin smallLabelHeavy: Roboto 8px Bold)
        self.hl_text_items: List[Tuple[pg.TextItem, pg.TextItem]] = []
        hl_font = QtGui.QFont("Roboto", 8, QtGui.QFont.Bold)
        hl_font.setPixelSize(8)
        hl_font.setBold(True)
        for _ in range(8):
            t_h = pg.TextItem("H", color=T.TEXT_DIM, anchor=(0, 0.5))
            t_h.setFont(hl_font)
            t_h.setZValue(16)
            t_l = pg.TextItem("L", color=T.TEXT_DIM, anchor=(0, 0.5))
            t_l.setFont(hl_font)
            t_l.setZValue(16)
            self.vb.addItem(t_h, ignoreBounds=True)
            self.vb.addItem(t_l, ignoreBounds=True)
            self.hl_text_items.append((t_h, t_l))

        # 8 đường cong PlotCurveItem cho 8 kênh với màu từ CHANNEL_COLORS (zValue 10, trên grid)
        self.curves: List[pg.PlotCurveItem] = []
        for ch in range(8):
            pen = pg.mkPen(color=T.CHANNEL_COLORS[ch], width=1.5)
            curve = pg.PlotCurveItem(pen=pen)
            curve.setZValue(10)
            self.vb.addItem(curve)
            self.curves.append(curve)

        # Trên các kênh số (Digital Channels D0..D7), tắt hoàn toàn dấu chấm mẫu phần cứng trên đường sóng
        # để đường xung vuông (H/L) luôn phẳng mượt 100%, chỉ hiển thị 8 dấu chấm tâm bit giao thức ở giữa xung.
        self.show_hardware_sample_points: bool = False
        self.sample_points_items: List[pg.ScatterPlotItem] = []
        for ch in range(8):
            sp = pg.ScatterPlotItem(
                size=3,
                pen=pg.mkPen(None),
                brush=pg.mkBrush(T.CHANNEL_COLORS[ch]),
                pxMode=True
            )
            sp.setZValue(12)
            sp.setVisible(False)
            self.vb.addItem(sp, ignoreBounds=True)
            self.sample_points_items.append(sp)

        # Vạch Trigger dọc màu vàng #fff06a và cờ trigger cam #f18d4b (zValue 20)
        self.trigger_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            pen=pg.mkPen(color=T.TRIGGER_LINE, width=1.5, style=QtCore.Qt.SolidLine),
            label="T",
            labelOpts={
                "color": "#ffffff",
                "fill": QtGui.QBrush(QtGui.QColor(T.TRIGGER_MARKER)),
                "position": 0.03,
                "anchors": [(0.5, 0.5), (0.5, 0.5)]
            }
        )
        self.trigger_line.label.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
        self.trigger_line.setZValue(20)
        self.vb.addItem(self.trigger_line, ignoreBounds=True)
        self.trigger_line.hide()

        # Cặp thước đo thời gian (Cursors A & B) (zValue 25)
        self.cursor_a = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=True,
            pen=pg.mkPen(color=T.CURSOR_A, width=1.6, style=QtCore.Qt.SolidLine),
            hoverPen=pg.mkPen(color="#80d8ff", width=2.5),
            label="A",
            labelOpts={
                "color": "#ffffff",
                "fill": QtGui.QBrush(QtGui.QColor(T.CURSOR_A)),
                "position": 0.90,
                "anchors": [(0.5, 0.5), (0.5, 0.5)]
            }
        )
        self.cursor_a.label.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
        self.cursor_a.setZValue(25)

        self.cursor_b = pg.InfiniteLine(
            pos=8.68e-5,
            angle=90,
            movable=True,
            pen=pg.mkPen(color=T.CURSOR_B, width=1.6, style=QtCore.Qt.SolidLine),
            hoverPen=pg.mkPen(color="#ff8a80", width=2.5),
            label="B",
            labelOpts={
                "color": "#ffffff",
                "fill": QtGui.QBrush(QtGui.QColor(T.CURSOR_B)),
                "position": 0.93,
                "anchors": [(0.5, 0.5), (0.5, 0.5)]
            }
        )
        self.cursor_b.label.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
        self.cursor_b.setZValue(25)

        self.vb.addItem(self.cursor_a, ignoreBounds=True)
        self.vb.addItem(self.cursor_b, ignoreBounds=True)

        # Vùng span đo đạc bán trong suốt giữa Cursor A và Cursor B (RangeDisplay / Measurement Span Bar)
        self.cursor_region = pg.LinearRegionItem(
            values=[0.0, 8.68e-5],
            movable=False,
            brush=QtGui.QBrush(QtGui.QColor(38, 163, 217, 24)),
            pen=pg.mkPen(color=QtGui.QColor(38, 163, 217, 80), width=1, style=QtCore.Qt.DashLine)
        )
        self.cursor_region.setZValue(18)
        self.vb.addItem(self.cursor_region, ignoreBounds=True)

        # Nhãn text span trên sóng hiển thị |← Δt →|
        self.cursor_span_text = pg.TextItem(text="", color="#ffffff", anchor=(0.5, 0.5))
        self.cursor_span_text.setFont(QtGui.QFont("Roboto Mono", 8, QtGui.QFont.Bold))
        self.cursor_span_text.setZValue(26)
        self.vb.addItem(self.cursor_span_text, ignoreBounds=True)

        # Chấm tròn chỉ thị nam châm hút sườn xung (Snap Indicator Dot Ø 8px) (zValue 30)
        self.snap_dot = pg.ScatterPlotItem(
            size=8,
            pen=pg.mkPen(color=T.CURSOR_A, width=2.0),
            brush=pg.mkBrush("#ffffff"),
            hoverable=False
        )
        self.snap_dot.setZValue(30)
        self.vb.addItem(self.snap_dot, ignoreBounds=True)
        self.snap_dot.hide()

        # Đường xem trước khoảng cách đo nhanh Quick Measure (zValue 28)
        self.preview_measure_line = pg.PlotCurveItem(
            pen=pg.mkPen(color=QtGui.QColor(T.ACCENT_START), width=1.8, style=QtCore.Qt.DashLine)
        )
        self.preview_measure_line.setZValue(28)
        self.vb.addItem(self.preview_measure_line, ignoreBounds=True)
        self.preview_measure_line.hide()

        # Nhãn xem trước thông số đo nhanh bám theo trỏ chuột (zValue 29)
        self.preview_measure_text = pg.TextItem(text="", color="#ffffff", anchor=(0.5, 1.2))
        self.preview_measure_text.setFont(QtGui.QFont("Roboto Mono", 9, QtGui.QFont.Bold))
        self.preview_measure_text.setZValue(29)
        self.vb.addItem(self.preview_measure_text, ignoreBounds=True)
        self.preview_measure_text.hide()

        # Kết nối sự kiện di chuyển và thả thước đo A & B (kèm Magnetic Snap)
        self.cursor_a.sigPositionChanged.connect(lambda: self._on_cursor_dragged(self.cursor_a))
        self.cursor_b.sigPositionChanged.connect(lambda: self._on_cursor_dragged(self.cursor_b))
        self.cursor_a.sigPositionChangeFinished.connect(lambda: self._on_cursor_drag_finished(self.cursor_a))
        self.cursor_b.sigPositionChangeFinished.connect(lambda: self._on_cursor_drag_finished(self.cursor_b))

        # Kết nối sự kiện chuột Scene cho Magnetic Snap, Live Measure Preview & Point Inspector
        self.plot_widget.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
        self.plot_widget.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)

        main_layout.addWidget(self.plot_widget, 1)

        # ---------------------------------------------------------------------
        # 3. FLOATING HUD (Góc trên bên phải dưới Timeline)
        # ---------------------------------------------------------------------
        self.hud = WaveformHUD(self.plot_widget)
        self.hud_widget = self.hud
        self.hud.raise_()
        self._update_hud()
        # Ẩn con trỏ đo mặc định để giao diện sạch khi khởi động (bấm phím C hoặc nút ❙❙ để bật)
        self.toggle_cursors(False)

        # Tính toán hình học ban đầu
        self._recompute_row_heights()
        # Đặt phạm vi X ban đầu cố định (0 đến 32.768 ms ứng với 32.768 mẫu 1MHz)
        self.plot_widget.setXRange(0.0, 0.032768, padding=0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recompute_row_heights()

        # Căn góc dưới bên phải cho HUD để không bao giờ che dải bong bóng giải mã của CH0
        hud_w = max(self.hud.sizeHint().width() + 24, 380)
        hud_h = max(self.hud.sizeHint().height(), 26)
        self.hud.setGeometry(self.plot_widget.width() - hud_w - 16, self.plot_widget.height() - hud_h - 10, hud_w, hud_h)

    def _recompute_row_heights(self):
        """Tính toán chiều cao 8 track co giãn lấp đầy chiều cao cửa sổ theo UI_SPEC.md."""
        avail_h = self.plot_widget.height() - T.AXIS_HEIGHT
        if avail_h <= 0:
            avail_h = self.height() - T.AXIS_HEIGHT
        if avail_h <= 0:
            avail_h = 600

        # Phân bổ chiều cao lấp đầy: Hàng có gắn Protocol Analyzer cao gấp 1.35x hàng thường
        active_channels = getattr(self, "active_analyzer_channels", {0})
        weights = [self.dec_scale if ch in active_channels else 1.0 for ch in range(8)]
        total_weight = sum(weights)

        min_total = int(T.CHANNEL_ROW_HEIGHT * (8 - len(active_channels) + len(active_channels) * self.dec_scale))
        target_h = max(avail_h, min_total)

        heights = [int(target_h * w / total_weight) for w in weights]
        diff = target_h - sum(heights)
        for i in range(diff):
            heights[i % 8] += 1

        self.row_heights = heights
        self.row_h = heights[1]  # Chiều cao track chuẩn
        total_h = sum(self.row_heights)

        # Cập nhật chiều cao các frame cột nhãn
        for i, h in enumerate(self.row_heights):
            self.channel_frames[i].setFixedHeight(h)

        # Cập nhật phạm vi ViewBox Y
        self.vb.setYRange(0, total_h, padding=0)

        # Cập nhật vị trí vạch ngăn mỏng giữa các track
        y0 = 0
        for i, h in enumerate(self.row_heights):
            self.row_separator_lines[i].setValue(y0 + h)
            y0 += h

        self._update_hl_positions()

        # Nếu đang có dữ liệu, vẽ lại dữ liệu và cập nhật vị trí Y của bong bóng / dấu chấm bit theo chiều cao track mới
        if self.current_data:
            self._update_curve_data()
            if self._uart_frames:
                self._render_uart_bubbles()

    def _on_view_range_changed(self):
        """Khi vùng nhìn X thay đổi do Zoom hoặc Pan."""
        self._update_hl_positions()
        self._update_hardware_sample_points()
        self._check_multibubble_transition()
        if hasattr(self, "cursor_a") and self.cursor_a.isVisible():
            self._update_cursor_span_visibility()
        vr = self.vb.viewRange()
        self.sigXRangeChanged.emit(vr[0][0], vr[0][1])

    def _update_cursor_span_visibility(self):
        """Chỉ hiển thị nhãn |← Δt →| khi khoảng cách pixel giữa A và B >= 85px để không đè lên bong bóng."""
        if not hasattr(self, "cursor_span_text") or not self.cursor_a.isVisible():
            if hasattr(self, "cursor_span_text"):
                self.cursor_span_text.setVisible(False)
            return
        t_a = self.cursor_a.value()
        t_b = self.cursor_b.value()
        dt = abs(t_b - t_a)
        vr = self.vb.viewRange()
        t_span = max(1e-12, vr[0][1] - vr[0][0])
        vb_w = max(10, self.vb.width())
        px_dist = (dt / t_span) * vb_w
        self.cursor_span_text.setVisible(px_dist >= 85.0)

    def _check_multibubble_transition(self):
        """Kiểm tra và chuyển đổi giữa SingleBubble và MultiBubble khi vượt ngưỡng Zoom."""
        if not self._uart_frames or len(self._uart_frames) < 2:
            return
        vr = self.vb.viewRange()
        t_span = max(1e-12, vr[0][1] - vr[0][0])
        vb_w = max(10, self.vb.width())
        px_per_sample = vb_w / (t_span * self._uart_sample_rate)
        px_per_byte = px_per_sample * 87.0
        should_be_multi = (px_per_byte < 18.0)
        if should_be_multi != self._is_multibubble:
            self._render_uart_bubbles()

    def _update_hardware_sample_points(self):
        """
        Cập nhật trạng thái hiển thị của 8 dấu chấm giải mã tâm bit (Protocol Bit Markers) theo mức Zoom.
        Đường sóng số (Digital Channels D0..D7) luôn giữ phẳng mượt không vẽ chấm mẫu phần cứng trên đường H/L.
        """
        if not self.current_data:
            return

        vr = self.vb.viewRange()
        x_min, x_max = vr[0][0], vr[0][1]
        t_span = max(1e-12, x_max - x_min)
        vb_width_px = max(10, self.vb.width())

        sample_rate = float(self.current_data["sample_rate"])
        sample_count = int(self.current_data["sample_count"])
        trig_offset = int(self.current_data["trig_offset"])
        status = self.current_data.get("status", 0)

        # Số mẫu hiển thị trên màn hình hiện tại
        sample_span = t_span * sample_rate
        px_per_sample = vb_width_px / sample_span

        # Kiểm soát ẩn/hiện Protocol Bit Markers khi zoom quá xa (nếu 1 bit hiển thị < 6 px)
        if self.bit_dots_item:
            self.bit_dots_item.setVisible(px_per_sample * 8.0 >= 6.0)

        # Kênh Digital mặc định tắt dấu chấm trên đường line (show_hardware_sample_points = False)
        if not getattr(self, "show_hardware_sample_points", False) or px_per_sample < 6.0:
            for sp in self.sample_points_items:
                if sp.isVisible():
                    sp.clear()
                    sp.setVisible(False)
            return

        # Zoom sâu: Tính chỉ số mẫu trong khung nhìn [idx_start, idx_end]
        if status == 0:
            idx_start = int(x_min * sample_rate + trig_offset) - 1
            idx_end = int(x_max * sample_rate + trig_offset) + 2
        else:
            idx_start = int(x_min * sample_rate) - 1
            idx_end = int(x_max * sample_rate) + 2

        idx_start = max(0, min(sample_count, idx_start))
        idx_end = max(0, min(sample_count, idx_end))

        if idx_end <= idx_start:
            for sp in self.sample_points_items:
                sp.clear()
                sp.setVisible(False)
            return

        # Mảng thời gian của các mẫu nằm trong khung nhìn
        if status == 0:
            t_pts = (np.arange(idx_start, idx_end, dtype=np.float64) - trig_offset) / sample_rate
        else:
            t_pts = np.arange(idx_start, idx_end, dtype=np.float64) / sample_rate

        channels = self.current_data["channels"]
        y0 = 0
        active_channels = getattr(self, "active_analyzer_channels", {0})
        for ch in range(8):
            sp = self.sample_points_items[ch]
            if not self.channel_visible[ch]:
                sp.clear()
                sp.setVisible(False)
                continue

            h = self.row_heights[ch]
            if ch in active_channels:
                decoder_space = h - self.row_h
                wave_top = y0 + decoder_space
                hi = wave_top + self.row_h * 0.22
                lo = wave_top + self.row_h * 0.78
            else:
                hi = y0 + h * 0.22
                lo = y0 + h * 0.78

            ch_slice = channels[ch][idx_start:idx_end]
            y_pts = np.where(ch_slice == 1, hi, lo)

            sp.setData(x=t_pts, y=y_pts)
            sp.setVisible(True)
            y0 += h

    def _update_hl_positions(self):
        """Cập nhật vị trí nhãn H và L bám sát mép trái ViewBox."""
        if not hasattr(self, "hl_text_items") or not self.hl_text_items:
            return
        view_range = self.vb.viewRange()
        x_min, x_max = view_range[0][0], view_range[0][1]
        x_span = max(1e-9, x_max - x_min)
        x_pos = x_min + x_span * 0.005

        y0 = 0
        active_channels = getattr(self, "active_analyzer_channels", {0})
        for i, h in enumerate(self.row_heights):
            if i in active_channels:
                decoder_space = h - self.row_h
                wave_top = y0 + decoder_space
                hi = wave_top + self.row_h * 0.22
                lo = wave_top + self.row_h * 0.78
            else:
                hi = y0 + h * 0.22
                lo = y0 + h * 0.78

            t_h, t_l = self.hl_text_items[i]
            t_h.setPos(x_pos, hi)
            t_l.setPos(x_pos, lo)
            y0 += h

    def set_channel_name(self, ch: int, name: str):
        """Đổi tên hiển thị của kênh số."""
        if 0 <= ch < 8:
            self.channel_names[ch] = name
            col = T.CHANNEL_COLORS[ch]
            self.channel_labels_top[ch].setText(
                f"<span style=\"color:{col};font-family:'Roboto Condensed','Roboto',sans-serif;font-weight:700;font-size:11px;letter-spacing:0.165px;\">D{ch}</span>"
                f"&nbsp;&nbsp;&nbsp;<span style=\"font-family:'Roboto',sans-serif;font-size:13px;font-weight:500;letter-spacing:0.065px;color:{T.TEXT};\">{name}</span>"
            )

    def _show_channel_menu(self, ch: int, button: QtWidgets.QToolButton):
        """Mở menu ngữ cảnh tùy chọn cho kênh số."""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
                padding: 4px 0px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {T.TEXT};
                padding: 6px 20px 6px 12px;
                font-family: 'Roboto', sans-serif;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {T.BORDER_MUTED};
                margin: 4px 6px;
            }}
        """)
        act_rename = menu.addAction(f"Rename Channel {ch}...")
        vis = self.channel_visible[ch]
        act_toggle = menu.addAction(f"Hide Channel {ch}" if vis else f"Show Channel {ch}")
        act_reset_h = menu.addAction("Reset Row Height")
        act_measure = menu.addAction(f"📊 Measure Channel {ch}...")
        menu.addSeparator()
        act_trig_none = menu.addAction("Trigger: None (Free-run)")
        act_trig_rise = menu.addAction(f"Trigger: CH{ch} Rising Edge ↑")
        act_trig_fall = menu.addAction(f"Trigger: CH{ch} Falling Edge ↓")

        pos = button.mapToGlobal(QtCore.QPoint(0, button.height() + 2))
        chosen = menu.exec_(pos)

        if chosen == act_rename:
            curr_name = self.channel_names[ch]
            new_name, ok = QtWidgets.QInputDialog.getText(
                self, f"Rename Channel {ch}", "Channel Name:", QtWidgets.QLineEdit.Normal, curr_name
            )
            if ok and new_name.strip():
                self.set_channel_name(ch, new_name.strip())
                mw = self.window()
                if hasattr(mw, "ch_name_edits") and ch < len(mw.ch_name_edits):
                    mw.ch_name_edits[ch].setText(new_name.strip())
        elif chosen == act_toggle:
            self.set_channel_visible(ch, not vis)
        elif chosen == act_reset_h:
            self.row_heights[ch] = T.CHANNEL_ROW_HEIGHT * (T.DECODER_ROW_SCALE if ch == 0 else 1.0)
            self._recompute_row_heights()
        elif chosen in (act_trig_none, act_trig_rise, act_trig_fall):
            mw = self.window()
            if hasattr(mw, "combo_ch") and hasattr(mw, "combo_mode"):
                mw.combo_ch.setCurrentIndex(ch)
                if chosen == act_trig_none:
                    mw.combo_mode.setCurrentIndex(0)
                elif chosen == act_trig_rise:
                    mw.combo_mode.setCurrentIndex(1)
                elif chosen == act_trig_fall:
                    mw.combo_mode.setCurrentIndex(2)
        elif chosen == act_measure:
            mw = self.window()
            if hasattr(mw, "_show_measurements_for_channel"):
                mw._show_measurements_for_channel(ch)

    def set_channel_visible(self, ch: int, visible: bool):
        """Ẩn / hiện một kênh sóng trên đồ thị."""
        if 0 <= ch < 8:
            self.channel_visible[ch] = visible
            self.curves[ch].setVisible(visible)
            if hasattr(self, "sample_points_items") and ch < len(self.sample_points_items):
                if not visible:
                    self.sample_points_items[ch].clear()
                    self.sample_points_items[ch].setVisible(False)
            self.channel_frames[ch].setVisible(visible)
            if hasattr(self, "hl_text_items") and ch < len(self.hl_text_items):
                t_h, t_l = self.hl_text_items[ch]
                t_h.setVisible(visible)
                t_l.setVisible(visible)
            self._update_hardware_sample_points()

    def toggle_cursors(self, visible: Optional[bool] = None):
        """Bật / tắt hiển thị cặp thước đo A & B, vùng span và HUD."""
        if visible is None:
            visible = not self.cursor_a.isVisible()
        self.cursor_a.setVisible(visible)
        self.cursor_b.setVisible(visible)
        self.cursor_region.setVisible(visible)
        self.hud.setVisible(visible)
        self._update_cursor_span_visibility()

    def _on_cursor_dragged(self, cursor: pg.InfiniteLine):
        """Xử lý kéo thước đo A hoặc B kèm cơ chế Magnetic Snap-to-Edge chuẩn UI_SPEC Mục 7.1."""
        if self._is_snapping:
            return

        t_val = cursor.value()
        if self.snap_enabled and self.current_data is not None:
            t_snap, ch, _ = self.find_closest_edge(
                t_val,
                preferred_ch=self.hovered_channel if self.hovered_channel >= 0 else None,
                max_px=self.snap_radius_px
            )
            if t_snap is not None:
                self._is_snapping = True
                cursor.setValue(t_snap)
                self._is_snapping = False

                # Hiển thị Snap Indicator Dot Ø 8px tại giao điểm sườn xung
                y_mid = self.get_channel_mid_y(ch if ch is not None else (self.hovered_channel if self.hovered_channel >= 0 else 0))
                pen_color = T.CURSOR_A if cursor == self.cursor_a else T.CURSOR_B
                self.snap_dot.setData(
                    pos=[[t_snap, y_mid]],
                    pen=pg.mkPen(color=pen_color, width=2.0),
                    brush=pg.mkBrush("#ffffff")
                )
                self.snap_dot.show()
            else:
                self.snap_dot.hide()

        self._update_hud()

    def _on_cursor_drag_finished(self, cursor: pg.InfiniteLine):
        """Ẩn nhẹ chấm snap dot sau khi kết thúc kéo thả thước đo."""
        QtCore.QTimer.singleShot(400, self.snap_dot.hide)

    def _on_cursor_moved(self):
        self._update_hud()

    def _update_hud(self):
        t_a = self.cursor_a.value()
        t_b = self.cursor_b.value()
        dt = abs(t_b - t_a)
        self.cursor_a.label.setText(f"A: {format_si_time(t_a)}")
        self.cursor_b.label.setText(f"B: {format_si_time(t_b)}")
        self.hud.update_values(t_a, t_b)

        # Cập nhật Span Region & Span Bar Text giữa A và B
        t_min = min(t_a, t_b)
        t_max = max(t_a, t_b)
        self.cursor_region.setRegion([t_min, t_max])
        t_mid = (t_min + t_max) / 2.0
        freq_str = format_si_freq(1.0 / dt) if dt > 1e-12 else "-- Hz"
        self.cursor_span_text.setText(f"|← {format_si_time(dt)} ({freq_str}) →|")
        total_h = sum(self.row_heights) if hasattr(self, "row_heights") and self.row_heights else 400
        self.cursor_span_text.setPos(t_mid, total_h * 0.84)
        self._update_cursor_span_visibility()

        self.sigCursorChanged.emit(t_a, t_b, dt)

    def set_cursor_positions(self, t_a: float, t_b: float):
        """Đặt vị trí Cursor A và Cursor B theo chương trình (không bị can thiệp bởi snap)."""
        self._is_snapping = True
        self.cursor_a.setValue(t_a)
        self.cursor_b.setValue(t_b)
        self._is_snapping = False
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

    # -------------------------------------------------------------------------
    # HỆ THỐNG MAGNETIC SNAP & QUICK MEASURE TOOL (UI_SPEC Mục 7)
    # -------------------------------------------------------------------------
    def get_channel_at_y(self, y_val: float) -> int:
        """Xác định số thứ tự kênh (0..7) dựa trên tọa độ trục Y."""
        y_cum = 0
        for ch, h in enumerate(self.row_heights):
            if y_cum <= y_val < y_cum + h:
                return ch
            y_cum += h
        return -1

    def get_channel_mid_y(self, ch: int) -> float:
        """Lấy tọa độ Y tâm của một track kênh để vẽ Snap Dot hoặc Preview Line."""
        if 0 <= ch < len(self.row_heights):
            y_start = sum(self.row_heights[:ch])
            return y_start + self.row_heights[ch] / 2.0
        return sum(self.row_heights) / 2.0 if self.row_heights else 200.0

    def find_closest_edge(
        self,
        t: float,
        preferred_ch: Optional[int] = None,
        max_px: Optional[float] = None
    ) -> Tuple[Optional[float], Optional[int], float]:
        """
        Tìm kiếm sườn xung gần nhất với mốc thời gian t theo chuẩn UI_SPEC.md Mục 7.1:
        - Bán kính hút: mặc định 15 pixels (độc lập với mức Zoom).
        - Thứ tự ưu tiên kênh: (1) preferred_ch (track dưới trỏ chuột) -> (2) active_inspect_channel -> (3) tất cả kênh.
        - Trả về: (t_snap, matched_ch, pixel_dist). Nếu vượt quá bán kính hút, trả về (None, None, inf).
        """
        if self.current_data is None:
            return None, None, float("inf")

        threshold_px = max_px if max_px is not None else self.snap_radius_px

        def _calc_px_dist(t_cand: float) -> float:
            p1 = self.vb.mapViewToDevice(QtCore.QPointF(t, 0))
            p2 = self.vb.mapViewToDevice(QtCore.QPointF(t_cand, 0))
            return abs(p2.x() - p1.x())

        def _get_combined_edges(ch: Optional[int]) -> np.ndarray:
            """Hợp nhất sườn xung phần cứng và ranh giới nhịp bit của Decoder (UI_SPEC 7.4)."""
            if ch is not None and 0 <= ch < 8:
                hw = self.channel_edges.get(ch, np.array([]))
                dec = self.decoder_edges.get(ch, np.array([]))
                if len(hw) > 0 and len(dec) > 0:
                    return np.unique(np.concatenate([hw, dec]))
                return hw if len(hw) > 0 else dec
            else:
                all_dec = [arr for arr in self.decoder_edges.values() if len(arr) > 0]
                if all_dec:
                    return np.unique(np.concatenate([self.all_edges] + all_dec))
                return self.all_edges

        # Xây dựng danh sách ưu tiên tìm kiếm
        priority_targets: List[Tuple[Optional[int], np.ndarray]] = []
        if preferred_ch is not None and 0 <= preferred_ch < 8:
            priority_targets.append((preferred_ch, _get_combined_edges(preferred_ch)))

        if self.active_inspect_channel != preferred_ch and 0 <= self.active_inspect_channel < 8:
            priority_targets.append((self.active_inspect_channel, _get_combined_edges(self.active_inspect_channel)))

        priority_targets.append((None, _get_combined_edges(None)))

        for ch_target, edges in priority_targets:
            if edges is None or len(edges) == 0:
                continue

            idx = np.searchsorted(edges, t)
            candidates = []
            if idx > 0:
                candidates.append(edges[idx - 1])
            if idx < len(edges):
                candidates.append(edges[idx])

            if not candidates:
                continue

            best_edge = min(candidates, key=lambda cand: abs(cand - t))
            px_dist = _calc_px_dist(best_edge)
            if px_dist <= threshold_px:
                # Nếu matched kênh là None (tìm từ all_edges), truy hồi xem mốc này thuộc kênh nào
                resolved_ch = ch_target
                if resolved_ch is None:
                    for c in range(8):
                        c_comb = _get_combined_edges(c)
                        if len(c_comb) > 0 and np.any(np.abs(c_comb - best_edge) < 1e-12):
                            resolved_ch = c
                            break
                return float(best_edge), resolved_ch, float(px_dist)

        return None, None, float("inf")

    def _on_scene_mouse_moved(self, pos: QtCore.QPointF):
        """Xử lý sự kiện di chuột trong PlotWidget: cập nhật Point Inspector và Quick Measure Preview."""
        if not self.vb.sceneBoundingRect().contains(pos):
            return

        view_pt = self.vb.mapSceneToView(pos)
        t_mouse = float(view_pt.x())
        y_mouse = float(view_pt.y())
        self.hovered_channel = self.get_channel_at_y(y_mouse)

        # 1. Point Inspector (Hover Timestamp)
        if self.current_data is not None and self.current_time_axis is not None and len(self.current_time_axis) > 0:
            fs = float(self.current_data["sample_rate"])
            trig_offset = self._effective_trig_offset(int(self.current_data["trig_offset"]))
            sample_count = int(self.current_data["sample_count"])
            sample_idx = int(np.clip(round(t_mouse * fs + trig_offset), 0, sample_count - 1))
            raw_val = 0
            for ch in range(8):
                if self.current_data["channels"][ch][sample_idx]:
                    raw_val |= (1 << ch)
            self.sigHoverTimestamp.emit(t_mouse, sample_idx, raw_val)

        # 2. Quick Measure Live Preview
        if self.quick_measure_active:
            t_snap, ch, _ = self.find_closest_edge(
                t_mouse,
                preferred_ch=self.hovered_channel if self.hovered_channel >= 0 else None,
                max_px=self.snap_radius_px
            )
            t_target = t_snap if t_snap is not None else t_mouse
            y_mid = self.get_channel_mid_y(ch if ch is not None else (self.hovered_channel if self.hovered_channel >= 0 else 0))

            if t_snap is not None:
                pen_color = T.CURSOR_A if self.quick_measure_step == 1 else T.CURSOR_B
                self.snap_dot.setData(
                    pos=[[t_snap, y_mid]],
                    pen=pg.mkPen(color=pen_color, width=2.0),
                    brush=pg.mkBrush("#ffffff")
                )
                self.snap_dot.show()
            else:
                self.snap_dot.hide()

            if self.quick_measure_step == 2:
                # Vẽ đường xem trước từ t1 đến t_target
                self.preview_measure_line.setData(x=[self.quick_measure_t1, t_target], y=[y_mid, y_mid])
                self.preview_measure_line.show()

                dt = abs(t_target - self.quick_measure_t1)
                freq_str = format_si_freq(1.0 / dt) if dt > 1e-12 else "-- Hz"
                self.preview_measure_text.setText(f"Δt: {format_si_time(dt)} ({freq_str})")
                self.preview_measure_text.setPos(t_target, y_mid)
                self.preview_measure_text.show()

    def _on_scene_mouse_clicked(self, ev):
        """Xử lý sự kiện click chuột trong PlotWidget cho Quick Measure Tool."""
        if not self.quick_measure_active:
            return

        # Bấm chuột phải để hủy chế độ Quick Measure
        if ev.button() == QtCore.Qt.RightButton:
            self.cancel_quick_measure()
            ev.accept()
            return

        if ev.button() == QtCore.Qt.LeftButton:
            pos = ev.scenePos()
            if not self.vb.sceneBoundingRect().contains(pos):
                return
            view_pt = self.vb.mapSceneToView(pos)
            t_mouse = float(view_pt.x())
            y_mouse = float(view_pt.y())
            target_ch = self.get_channel_at_y(y_mouse)
            t_snap, _, _ = self.find_closest_edge(
                t_mouse,
                preferred_ch=target_ch if target_ch >= 0 else None,
                max_px=self.snap_radius_px
            )
            t_final = t_snap if t_snap is not None else t_mouse

            if self.quick_measure_step == 1:
                self._is_snapping = True
                self.cursor_a.setValue(t_final)
                self._is_snapping = False
                self.quick_measure_t1 = t_final
                self.quick_measure_step = 2
                self._update_hud()
                self.sigQuickMeasureState.emit(True, "Quick Measure: Click on end edge (B) to finish (Esc to cancel)")
                ev.accept()
            elif self.quick_measure_step == 2:
                self._is_snapping = True
                self.cursor_b.setValue(t_final)
                self._is_snapping = False
                self.finish_quick_measure()
                ev.accept()

    def start_quick_measure(self):
        """Kích hoạt công cụ đo nhanh Quick Measure Tool (phím M hoặc nút |↔|)."""
        self.quick_measure_active = True
        self.quick_measure_step = 1
        self.toggle_cursors(True)
        self.plot_widget.setCursor(QtCore.Qt.CrossCursor)
        self.sigQuickMeasureState.emit(True, "Quick Measure: Click to place Cursor A (Snap active, Esc to cancel)")

    def cancel_quick_measure(self):
        """Hủy bỏ chế độ đo nhanh và khôi phục con trỏ chuột thông thường."""
        self.quick_measure_active = False
        self.quick_measure_step = 0
        self.preview_measure_line.hide()
        self.preview_measure_text.hide()
        self.snap_dot.hide()
        self.plot_widget.setCursor(QtCore.Qt.ArrowCursor)
        self.sigQuickMeasureState.emit(False, "")

    def finish_quick_measure(self):
        """Chốt kết quả đo nhanh hai điểm, cập nhật HUD và mở thanh đo span."""
        dt = abs(self.cursor_b.value() - self.cursor_a.value())
        freq_str = format_si_freq(1.0 / dt) if dt > 1e-12 else "-- Hz"
        self.cancel_quick_measure()
        self._update_hud()
        self.sigQuickMeasureState.emit(False, f"Measured: Δt = {format_si_time(dt)}, f = {freq_str}")

    def toggle_quick_measure(self):
        """Chuyển đổi bật / tắt công cụ đo nhanh Quick Measure Tool."""
        if self.quick_measure_active:
            self.cancel_quick_measure()
        else:
            self.start_quick_measure()

    def render_data(self, res: Dict[str, Any]):
        """Vẽ 8 kênh dữ liệu lên viewport với mốc thời gian t = 0 tại Trigger (mẫu 6554)."""
        self.current_data = res
        sample_rate = float(res["sample_rate"])
        sample_count = int(res["sample_count"])
        trig_offset = int(res["trig_offset"])
        status = res.get("status", 0)

        # Thiết lập vạch Trigger màu vàng #fff06a và cờ cam #f18d4b tại mẫu 6554 (t = 0s)
        if status == 0:  # STATUS_TRIGGER_OK
            t_marker = 0.0
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.TRIGGER_LINE, width=1.5, style=QtCore.Qt.SolidLine))
            self.trigger_line.label.setText("T")
            self.trigger_line.label.setColor(QtGui.QColor("#ffffff"))
            self.trigger_line.label.fill = QtGui.QBrush(QtGui.QColor(T.TRIGGER_MARKER))
            self.trigger_line.show()
            x_min = -trig_offset / sample_rate
            x_max = (sample_count - trig_offset) / sample_rate
            self.current_time_axis = (np.arange(sample_count, dtype=np.float64) - trig_offset) / sample_rate
        elif status == 1:  # STATUS_FREERUN_OK
            t_marker = trig_offset / sample_rate
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.TEXT_DIM, width=1.5, style=QtCore.Qt.DotLine))
            self.trigger_line.label.setText("FREE-RUN")
            self.trigger_line.label.setColor(QtGui.QColor("#ffffff"))
            self.trigger_line.label.fill = QtGui.QBrush(QtGui.QColor(T.TEXT_DIM))
            self.trigger_line.show()
            x_min = 0.0
            x_max = sample_count / sample_rate
            self.current_time_axis = np.arange(sample_count, dtype=np.float64) / sample_rate
        else:  # STATUS_TIMEOUT
            t_marker = trig_offset / sample_rate
            self.trigger_line.setValue(t_marker)
            self.trigger_line.setPen(pg.mkPen(color=T.ACCENT_WARN, width=1.5, style=QtCore.Qt.DashDotLine))
            self.trigger_line.label.setText("TIMEOUT")
            self.trigger_line.label.setColor(QtGui.QColor("#ffffff"))
            self.trigger_line.label.fill = QtGui.QBrush(QtGui.QColor(T.ACCENT_WARN))
            self.trigger_line.show()
            x_min = 0.0
            x_max = sample_count / sample_rate
            self.current_time_axis = np.arange(sample_count, dtype=np.float64) / sample_rate

        # Trích xuất vector sườn xung chuyển mức (Edge Transitions) phục vụ Magnetic Snap
        channels = res.get("channels", [])
        all_edges_list = []
        for ch in range(min(8, len(channels))):
            ch_data = channels[ch]
            diff_indices = np.where(np.diff(ch_data) != 0)[0] + 1
            if len(diff_indices) > 0 and self.current_time_axis is not None:
                edge_times = self.current_time_axis[diff_indices]
                self.channel_edges[ch] = edge_times
                all_edges_list.append(edge_times)
            else:
                self.channel_edges[ch] = np.array([], dtype=np.float64)

        if all_edges_list:
            self.all_edges = np.unique(np.concatenate(all_edges_list))
        else:
            self.all_edges = np.array([], dtype=np.float64)

        self._update_curve_data()

        # Đặt thước đo A và B gần điểm bắt sóng
        if status == 0:
            self.set_cursor_positions(0.0, 8.68e-5)
        else:
            self.set_cursor_positions(t_marker, t_marker + 8.68e-5)

        # Đặt vùng nhìn X
        self.plot_widget.setXRange(x_min, x_max, padding=0.01)

    def _update_curve_data(self):
        """Vẽ các đường sóng số bằng stepMode='right' và màu theo theme.CHANNEL_COLORS."""
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
        active_channels = getattr(self, "active_analyzer_channels", {0})
        for ch in range(8):
            h = self.row_heights[ch]
            if ch in active_channels:
                decoder_space = h - self.row_h
                wave_top = y0 + decoder_space
                hi = wave_top + self.row_h * 0.22
                lo = wave_top + self.row_h * 0.78
            else:
                hi = y0 + h * 0.22
                lo = y0 + h * 0.78

            ch_samples = channels[ch]
            yy = np.where(ch_samples == 1, hi, lo)
            self.curves[ch].setData(x=time_axis, y=yy, stepMode="right")
            self.curves[ch].setVisible(self.channel_visible[ch])
            y0 += h

        self._update_hardware_sample_points()

    def _effective_trig_offset(self, trig_offset: int) -> int:
        """Chỉ dịch gốc thời gian theo trig_offset khi status == 0 (STATUS_TRIGGER_OK)."""
        if self.current_data and self.current_data.get("status", 0) != 0:
            return 0
        return int(trig_offset)

    def render_uart_decorations(self, frames: List[Dict[str, Any]], sample_rate: float, trig_offset: int):
        """
        Vẽ các khối giải mã UART trực tiếp trên sóng (SingleBubble & MultiBubble)
        và các điểm đánh dấu mẫu bit (Protocol Bit Markers) tại tâm nhịp bit.
        """
        self.clear_decoder_decorations()
        self._uart_frames = list(frames) if frames else []
        self._uart_sample_rate = sample_rate
        self._uart_trig_offset = self._effective_trig_offset(trig_offset)

        if not frames:
            return

        self._render_uart_bubbles()

    def _render_uart_bubbles(self):
        """Dựng các bong bóng UART (SingleBubble hoặc MultiBubble tùy mức Zoom)."""
        # Xóa các graphics item chú thích cũ
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

        if not self._uart_frames:
            return

        frames = self._uart_frames
        sample_rate = self._uart_sample_rate
        trig_offset = self._uart_trig_offset

        h0 = self.row_heights[0]
        # Chiều cao khối giải mã chuẩn 18px dạng chữ nhật phẳng
        bubble_h = 18.0
        decoder_space = max(0, h0 - self.row_h)
        # Căn giữa khối giải mã trong dải decoder phía trên dạng sóng của CH0
        bubble_top = max(1.0, (decoder_space - bubble_h) / 2.0)

        # Mức High, Low và trục tâm giữa của track sóng CH0
        top0 = h0 - self.row_h
        hi0 = top0 + self.row_h * 0.22
        lo0 = top0 + self.row_h * 0.78
        mid0 = (hi0 + lo0) / 2.0

        ch_color = QtGui.QColor(T.CHANNEL_COLORS[0])
        err_color = QtGui.QColor("#ea5757")

        # Kiểm tra tỷ lệ Zoom để quyết định MultiBubble vs SingleBubble
        vr = self.vb.viewRange()
        t_span = max(1e-12, vr[0][1] - vr[0][0])
        vb_w = max(10, self.vb.width())
        px_per_sample = vb_w / (t_span * sample_rate)
        px_per_byte = px_per_sample * 87.0  # 1 byte UART ~87 mẫu ở 115200bps / 1MHz

        use_multibubble = (px_per_byte < 18.0 and len(frames) >= 2)
        self._is_multibubble = use_multibubble

        if use_multibubble:
            # Gom các gói tin liên tiếp thành các cụm MultiBubble (MultiBubble LOD)
            clusters: List[List[Dict[str, Any]]] = []
            current_cluster: List[Dict[str, Any]] = []

            for f in frames[:256]:
                if not current_cluster:
                    current_cluster.append(f)
                else:
                    prev_f = current_cluster[-1]
                    prev_stop = prev_f.get("stop_sample", prev_f.get("stop_idx", 0))
                    curr_start = f.get("start_sample", f.get("start_idx", 0))
                    # Nếu khoảng cách giữa 2 byte < 2000 mẫu thì gom vào cùng 1 cụm
                    if curr_start - prev_stop < 2000:
                        current_cluster.append(f)
                    else:
                        clusters.append(current_cluster)
                        current_cluster = [f]
            if current_cluster:
                clusters.append(current_cluster)

            for cluster in clusters:
                if len(cluster) >= 2:
                    s_idx = cluster[0].get("start_sample", cluster[0].get("start_idx", 0))
                    e_idx = cluster[-1].get("stop_sample", cluster[-1].get("stop_idx", s_idx + 10))
                    t_start = (s_idx - trig_offset) / sample_rate
                    t_stop = (e_idx - trig_offset) / sample_rate

                    chars = ''.join(c.get('char', '') for c in cluster if 32 <= ord(c.get('char', ' ')[0]) <= 126)
                    preview = f"'{chars}'" if chars else f"0x{cluster[0].get('byte_val', cluster[0].get('val', 0)):02X}..."
                    tip = f"MultiBubble: {len(cluster)} packets\nStart: {format_si_time(t_start)}\nDuration: {format_si_time(t_stop - t_start)}\nContent: {chars}"

                    mb = MultiBubbleItem(
                        t_start=t_start,
                        t_stop=t_stop,
                        y_top=bubble_top,
                        height=bubble_h,
                        count=len(cluster),
                        preview_text=preview,
                        bg_color=T.DECODE_UART_BG,
                        text_color=T.DECODE_UART_FG,
                        tooltip=tip,
                        on_clicked=lambda s_abs=s_idx/sample_rate, e_abs=e_idx/sample_rate: self.zoom_to_window(s_abs, e_abs)
                    )
                    mb.setZValue(30)
                    self.vb.addItem(mb)
                    self.decode_items.append(mb)
                else:
                    f = cluster[0]
                    s_idx = f.get("start_sample", f.get("start_idx", 0))
                    e_idx = f.get("stop_sample", f.get("stop_idx", s_idx + 10))
                    val = f.get("byte_val", f.get("val", 0))
                    char = f.get("char", "")
                    t_start = (s_idx - trig_offset) / sample_rate
                    t_stop = (e_idx - trig_offset) / sample_rate
                    sb = PillBubbleItem(
                        t_start=t_start,
                        t_stop=t_stop,
                        y_top=bubble_top,
                        height=bubble_h,
                        text=f"0x{val:02X}",
                        bg_color=T.DECODE_UART_BG,
                        text_color=T.DECODE_UART_FG,
                        radius=0.0,
                        on_clicked=lambda s_abs=s_idx/sample_rate, e_abs=e_idx/sample_rate: self.zoom_to_window(s_abs, e_abs)
                    )
                    sb.setZValue(30)
                    self.vb.addItem(sb)
                    self.decode_items.append(sb)
            return

        # SingleBubble Mode (khi Zoom vừa & gần):
        bit_dots_x: List[float] = []
        bit_dots_y: List[float] = []
        bit_dots_brushes: List[QtGui.QBrush] = []
        uart_dec_edges: List[float] = []

        max_bubbles = min(len(frames), 256)

        for frame_i, frame in enumerate(frames[:max_bubbles]):
            start_idx = frame.get("start_sample", frame.get("start_idx", 0))
            stop_idx = frame.get("stop_sample", frame.get("stop_idx", start_idx + 10))
            val = frame.get("byte_val", frame.get("val", 0))
            char = frame.get("char", "")

            # Dịch -0.5 mẫu để khớp tuyệt đối với cạnh dọc của stepMode="right" (vẽ tại idx - 1)
            edge_idx = start_idx - 0.5
            bit_len_idx = (stop_idx - start_idx) / 9.5

            # Trích xuất ranh giới từng nhịp bit phục vụ Analyzer-Aware Snapping (UI_SPEC 7.4)
            # Bao gồm mép Start bit, ranh giới 8 Data bits D0..D7 và Stop bit (k = 0..10)
            for k in range(11):
                t_bound = (edge_idx + k * bit_len_idx - trig_offset) / sample_rate
                uart_dec_edges.append(t_bound)

            # Chuẩn công nghiệp: Bong bóng dữ liệu ôm đúng 8 Data Bits (1.0 * T_bit đến 9.0 * T_bit)
            # sao cho mép trái bong bóng bắt đầu ngay sau Start bit và mép phải kết thúc ngay trước Stop bit
            b_start_idx = frame.get("data_start_sample", edge_idx + 1.0 * bit_len_idx)
            b_stop_idx = frame.get("data_end_sample", edge_idx + 9.0 * bit_len_idx)
            t_start = (b_start_idx - trig_offset) / sample_rate
            t_stop = (b_stop_idx - trig_offset) / sample_rate

            text_full = f"0x{val:02X}"
            if char and 32 <= ord(char[0]) <= 126:
                text_full += f" '{char}'"
            text_mid = f"0x{val:02X}"
            text_short = f"'{char}'" if (char and 32 <= ord(char[0]) <= 126) else f"{val:02X}"

            tip_str = f"Byte: 0x{val:02X} ('{char}')\nStart: {format_si_time((start_idx - trig_offset) / sample_rate)}\nDuration: {format_si_time(t_stop - t_start)}"

            bubble = PillBubbleItem(
                t_start=t_start,
                t_stop=t_stop,
                y_top=bubble_top,
                height=bubble_h,
                text=text_full,
                bg_color=T.DECODE_UART_BG,
                text_color=T.DECODE_UART_FG,
                radius=0.0,
                tooltip=tip_str,
                text_mid=text_mid,
                text_short=text_short,
                raw_data=frame,
                on_clicked=lambda s=start_idx/sample_rate, e=stop_idx/sample_rate: self.zoom_to_window(s, e),
                on_ctrl_clicked=lambda idx=frame_i, f=frame: self.sigBubbleCtrlClicked.emit(idx, f)
            )
            bubble.setZValue(30)
            self.vb.addItem(bubble)
            self.decode_items.append(bubble)

            # Protocol Bit Markers (Loại B): 8 dấu chấm đánh dấu tâm của 8 Data Bits (D0..D7)
            # Lấy trực tiếp từ mảng bit_centers của UARTDecoder (hoặc tính từ edge_idx)
            bit_centers = frame.get("bit_centers")
            if bit_centers and len(bit_centers) == 8:
                for center_idx in bit_centers:
                    t_center = (center_idx - trig_offset) / sample_rate
                    bit_dots_x.append(t_center)
                    bit_dots_y.append(mid0)
                    bit_dots_brushes.append(QtGui.QBrush(ch_color))
            else:
                for bit_i in range(8):
                    center_idx = edge_idx + (bit_i + 1.5) * bit_len_idx
                    t_center = (center_idx - trig_offset) / sample_rate
                    bit_dots_x.append(t_center)
                    bit_dots_y.append(mid0)
                    bit_dots_brushes.append(QtGui.QBrush(ch_color))

            # Nếu có lỗi Framing Error ở Stop bit thì đánh dấu chấm đỏ tại tâm Stop bit
            if frame.get("error", False):
                t_stop_bit = (edge_idx + 9.5 * bit_len_idx - trig_offset) / sample_rate
                bit_dots_x.append(t_stop_bit)
                bit_dots_y.append(mid0)
                bit_dots_brushes.append(QtGui.QBrush(err_color))

        if bit_dots_x:
            self.bit_dots_item = pg.ScatterPlotItem(
                x=bit_dots_x,
                y=bit_dots_y,
                size=4,
                brush=bit_dots_brushes,
                pen=pg.mkPen(None),
                pxMode=True
            )
            self.bit_dots_item.setZValue(35)
            self.vb.addItem(self.bit_dots_item)

        # Lưu trữ các ranh giới nhịp bit phục vụ Analyzer-Aware Snapping (UI_SPEC 7.4)
        active_ch = 0
        if hasattr(self, "active_analyzer_channels") and self.active_analyzer_channels:
            active_ch = list(self.active_analyzer_channels)[0]
        self.decoder_edges[active_ch] = np.unique(np.array(uart_dec_edges, dtype=np.float64)) if uart_dec_edges else np.array([], dtype=np.float64)

    def render_i2c_decorations(self, frames: List[Dict[str, Any]], sample_rate: float, trig_offset: int):
        """Vẽ khối giải mã I2C dạng chữ nhật (#4060c0) trên dòng sóng Kênh 2 (SDA)."""
        self.clear_decoder_decorations()
        if not frames:
            return

        eff_offset = self._effective_trig_offset(trig_offset)
        ch_target = 2
        y0 = sum(self.row_heights[:ch_target])
        h_target = self.row_heights[ch_target]
        decoder_space = max(0, h_target - self.row_h)
        bubble_h = 18.0
        bubble_top = y0 + max(1.0, (decoder_space - bubble_h) / 2.0)

        i2c_dec_edges: List[float] = []
        max_bubbles = min(len(frames), 256)
        for f in frames[:max_bubbles]:
            s_idx = f.get("start_sample", 0)
            e_idx = f.get("stop_sample", s_idx + 10)
            f_type = str(f.get("type", "data")).upper()
            val = f.get("val")

            t_start = (s_idx - eff_offset) / sample_rate
            t_stop = (e_idx - eff_offset) / sample_rate
            i2c_dec_edges.extend([t_start, t_stop])

            if "START" in f_type:
                txt = "START"
            elif f_type == "STOP":
                txt = "STOP"
            elif f_type == "ADDRESS":
                rw_str = "R" if f.get("rw") == "R" or f.get("read") else "W"
                txt = f"0x{val:02X} {rw_str}" if val is not None else "ADDR"
            else:
                txt = f"0x{val:02X}" if val is not None else f_type

            tip = f"I2C {f_type}: {f.get('desc', txt)}\nStart: {format_si_time(t_start)}\nDuration: {format_si_time(t_stop - t_start)}"

            bubble = PillBubbleItem(
                t_start=t_start,
                t_stop=t_stop,
                y_top=bubble_top,
                height=bubble_h,
                text=txt,
                bg_color=T.DECODE_I2C_BG,
                text_color=T.DECODE_I2C_FG,
                radius=0.0,
                tooltip=tip,
                on_clicked=lambda s_abs=s_idx/sample_rate, e_abs=e_idx/sample_rate: self.zoom_to_window(s_abs, e_abs)
            )
            bubble.setZValue(30)
            self.vb.addItem(bubble)
            self.decode_items.append(bubble)

        self.decoder_edges[ch_target] = np.unique(np.array(i2c_dec_edges, dtype=np.float64)) if i2c_dec_edges else np.array([], dtype=np.float64)

    def render_spi_decorations(self, frames: List[Dict[str, Any]], sample_rate: float, trig_offset: int):
        """Vẽ khối giải mã SPI dạng chữ nhật (#53a9fd) trên Kênh 4 (MOSI)."""
        self.clear_decoder_decorations()
        if not frames:
            return

        eff_offset = self._effective_trig_offset(trig_offset)
        ch_target = 4
        y0 = sum(self.row_heights[:ch_target])
        h_target = self.row_heights[ch_target]
        decoder_space = max(0, h_target - self.row_h)
        bubble_h = 18.0
        bubble_top = y0 + max(1.0, (decoder_space - bubble_h) / 2.0)

        spi_dec_edges: List[float] = []
        max_bubbles = min(len(frames), 256)
        for f in frames[:max_bubbles]:
            s_idx = f.get("start_sample", 0)
            e_idx = f.get("stop_sample", s_idx + 10)
            mv = f.get("mosi_val", 0)
            sv = f.get("miso_val", 0)

            t_start = (s_idx - eff_offset) / sample_rate
            t_stop = (e_idx - eff_offset) / sample_rate
            spi_dec_edges.extend([t_start, t_stop])

            txt = f"M:0x{mv:02X}"
            tip = f"SPI Byte\nMOSI: 0x{mv:02X}\nMISO: 0x{sv:02X}\nStart: {format_si_time(t_start)}"

            bubble = PillBubbleItem(
                t_start=t_start,
                t_stop=t_stop,
                y_top=bubble_top,
                height=bubble_h,
                text=txt,
                bg_color="#53a9fd",
                text_color="#1b1b1c",
                radius=0.0,
                tooltip=tip,
                on_clicked=lambda s_abs=s_idx/sample_rate, e_abs=e_idx/sample_rate: self.zoom_to_window(s_abs, e_abs)
            )
            bubble.setZValue(30)
            self.vb.addItem(bubble)
            self.decode_items.append(bubble)

        self.decoder_edges[ch_target] = np.unique(np.array(spi_dec_edges, dtype=np.float64)) if spi_dec_edges else np.array([], dtype=np.float64)

    def set_analyzer_channel(self, ch: int, name: str, color: str = T.DECODE_UART_BG):
        """Thiết lập kênh số có analyzer và tăng chiều cao 1.35x."""
        self.active_analyzer_channels = {ch}
        for i in range(8):
            if i == ch:
                self.channel_chips[i].setText(f"<span style='color:{color};font-size:9px;'>■</span> &nbsp;{name}")
                self.channel_chips[i].setVisible(True)
            else:
                self.channel_chips[i].setVisible(False)
        self._recompute_row_heights()

    def clear_decoder_decorations(self):
        """Xóa toàn bộ các bong bóng chú thích và chấm bit trên đồ thị."""
        self.decoder_edges = {i: np.array([], dtype=np.float64) for i in range(8)}
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

    def clear_data(self):
        """Xóa sạch dữ liệu hiển thị trên đồ thị, ẩn vạch trigger và chú thích."""
        self.current_data = None
        self._uart_frames = []
        self._is_multibubble = False
        for curve in self.curves:
            curve.clear()
        if hasattr(self, "sample_points_items"):
            for sp in self.sample_points_items:
                sp.clear()
                sp.setVisible(False)
        self.trigger_line.hide()
        self.clear_decoder_decorations()
        self.plot_widget.setXRange(0.0, 0.032768, padding=0)

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
        self.set_cursor_positions(t1, t2)
