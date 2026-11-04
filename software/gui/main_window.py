#!/usr/bin/env python3
"""software/gui/main_window.py
Giao diện người dùng Desktop chuẩn thương mại công nghiệp (Saleae Logic 2 / DSView):
- Cấu trúc chuẩn theo UI_SPEC.md và proto.py (v3):
  + Menu Bar: File, Edit, Capture, Measure, View, Help
  + Waveform Viewport (Vùng sóng chiếm ưu thế): Cột nhãn 194px + PlotWidget 8 kênh co giãn lấp đầy
  + Panel phải (313px): Analyzers, Trigger View card thu gọn, Data Table 4 cột, Tìm kiếm
  + Dải Action Rail bên phải (65px): Nút Start tròn xanh lá (Ø 50px) + các icon công cụ
  + Thanh đáy (42px): Session tabs (Session 0, Session 1, +) + Trạng thái kết nối + Mức zoom
- Giao thức nhị phân chuẩn spec/protocol.md (Khung lệnh 5B, Data Frame 32.776B)
- Tích hợp bộ giải mã UART trực tiếp trên sóng (ô bo góc + chấm tâm bit) và bảng gói tin.
"""

import os
import sys
import time
import numpy as np
from typing import Optional, Dict, Any, List

# Khử cảnh báo Wayland requestActivate() trên Linux
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")

from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from software.gui import theme as T
from software.gui.logic_client import LogicAnalyzerClient
from software.gui.waveform_widget import WaveformWidget
from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder
from software.utils.exporter import export_image, export_csv, export_vcd

# Bảng tra cứu tốc độ lấy mẫu (spec/protocol.md Table 2)
RATE_OPTIONS = [
    ("6 MHz", 6_000_000, 0),
    ("3 MHz", 3_000_000, 1),
    ("2 MHz", 2_000_000, 2),
    ("1 MHz (Mặc định)", 1_000_000, 3),
    ("500 kHz", 500_000, 4),
    ("200 kHz", 200_000, 5),
    ("100 kHz", 100_000, 6),
    ("50 kHz", 50_000, 7),
    ("10 kHz", 10_000, 8),
]


class CaptureWorker(QtCore.QThread):
    """Luồng phụ thu thập dữ liệu serial ngầm không gây block UI."""
    capture_done = QtCore.pyqtSignal(dict)
    capture_error = QtCore.pyqtSignal(str)

    def __init__(self, client: LogicAnalyzerClient, rate_idx: int, trig_ch: int, trig_mode: int):
        super().__init__()
        self.client = client
        self.rate_idx = rate_idx
        self.trig_ch = trig_ch
        self.trig_mode = trig_mode

    def run(self):
        try:
            res = self.client.start_capture(
                rate_idx=self.rate_idx,
                trig_ch=self.trig_ch,
                trig_mode=self.trig_mode
            )
            if res.get("success", False):
                self.capture_done.emit(res)
            else:
                self.capture_error.emit(res.get("error", "Lỗi thu thập dữ liệu"))
        except Exception as e:
            self.capture_error.emit(str(e))


class MainWindow(QtWidgets.QMainWindow):
    """Cửa sổ chính Desktop chuẩn Saleae Logic 2 theo UI_SPEC.md."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HUST Logic Analyzer (8 Channels, 6 MHz) — Lead Dev: Nguyen Van Hoi")
        self.resize(1280, 860)
        self.setMinimumSize(1080, 600)
        self.setStyleSheet(T.QSS)

        # Lớp Client & Worker
        self.client = LogicAnalyzerClient()
        self.worker: Optional[CaptureWorker] = None

        # Bộ giải mã
        self.uart_decoder = UARTDecoder(sample_rate=1_000_000, baudrate=115200)
        self.i2c_decoder = I2CDecoder(sample_rate=1_000_000)
        self.spi_decoder = SPIDecoder(sample_rate=1_000_000)

        # Dữ liệu hiện hành
        self.current_data: Optional[Dict[str, Any]] = None
        self.current_uart_frames: List[Dict[str, Any]] = []

        # Các widget điều khiển kênh hỗ trợ tương thích ngược
        self.ch_edits: List[QtWidgets.QLineEdit] = []
        self.ch_checks: List[QtWidgets.QCheckBox] = []
        for i in range(8):
            ed = QtWidgets.QLineEdit(f"Channel {i}")
            ed.textChanged.connect(lambda txt, ch=i: self._on_channel_name_changed(ch))
            self.ch_edits.append(ed)

            chk = QtWidgets.QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(lambda st, ch=i: self._on_channel_visibility_changed(ch, st))
            self.ch_checks.append(chk)

        # Khởi tạo giao diện
        self._init_layout()
        self._init_menu_bar()
        self._refresh_ports()

        # Backward compatibility aliases
        self.plot_widget = self.waveform.plot_widget
        self.trigger_line = self.waveform.trigger_line
        self.cursor_manager = self.waveform
        self.hud_widget = self.waveform.hud
        self.txt_decoded = self.txt_uart_decoded
        self.table_frames = self.table_uart_packets
        self.table_uart_frames = self.table_uart_packets
        self.ch_name_edits = self.ch_edits
        self.ch_checkboxes = self.ch_checks
        self.channel_names = self.waveform.channel_names
        self.channel_visible = self.waveform.channel_visible
        self.channel_curves = self.waveform.curves

        # Nạp dữ liệu giả lập ban đầu để sẵn sàng hiển thị ngay khi mở
        sample_file = os.path.join(os.path.dirname(__file__), "..", "tests", "sample_data_1mhz.bin")
        if os.path.exists(sample_file):
            self._load_bin_file(sample_file)

    # =========================================================================
    # THANH MENU (FILE / EDIT / CAPTURE / MEASURE / VIEW / HELP)
    # =========================================================================

    def _init_menu_bar(self):
        menubar = self.menuBar()

        # File
        menu_file = menubar.addMenu("&File")
        act_open = QtWidgets.QAction("&Open Capture (.bin)...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_capture_file)
        menu_file.addAction(act_open)

        menu_file.addSeparator()

        act_exp_img = QtWidgets.QAction("Export &Image (PNG, SVG)...", self)
        act_exp_img.setShortcut("Ctrl+S")
        act_exp_img.triggered.connect(self._export_image)
        menu_file.addAction(act_exp_img)

        act_exp_csv = QtWidgets.QAction("Export &CSV Data...", self)
        act_exp_csv.setShortcut("Ctrl+E")
        act_exp_csv.triggered.connect(self._export_csv)
        menu_file.addAction(act_exp_csv)

        act_exp_vcd = QtWidgets.QAction("Export &VCD (GTKWave)...", self)
        act_exp_vcd.setShortcut("Ctrl+V")
        act_exp_vcd.triggered.connect(self._export_vcd)
        menu_file.addAction(act_exp_vcd)

        menu_file.addSeparator()

        act_exit = QtWidgets.QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Edit
        menu_edit = menubar.addMenu("&Edit")
        act_reset_cursors = QtWidgets.QAction("&Reset Cursors", self)
        act_reset_cursors.triggered.connect(lambda: self.waveform.set_cursor_positions(0.0, 8.68e-5))
        menu_edit.addAction(act_reset_cursors)

        # Capture
        menu_capture = menubar.addMenu("&Capture")
        act_start = QtWidgets.QAction("&Start Capture", self)
        act_start.setShortcut("F5")
        act_start.triggered.connect(self._on_start_capture)
        menu_capture.addAction(act_start)

        act_abort = QtWidgets.QAction("&Abort Capture", self)
        act_abort.setShortcut("Escape")
        act_abort.triggered.connect(self._on_abort)
        menu_capture.addAction(act_abort)

        act_ping = QtWidgets.QAction("Check Connection (&Ping)", self)
        act_ping.triggered.connect(self._on_ping)
        menu_capture.addAction(act_ping)

        # Measure
        menu_measure = menubar.addMenu("&Measure")
        act_toggle_cursors = QtWidgets.QAction("Toggle &Cursors (A & B)", self)
        act_toggle_cursors.setShortcut("C")
        act_toggle_cursors.triggered.connect(self.waveform.toggle_cursors)
        menu_measure.addAction(act_toggle_cursors)

        # View
        menu_view = menubar.addMenu("&View")
        act_zoom_fit = QtWidgets.QAction("&Zoom Fit", self)
        act_zoom_fit.setShortcut("Ctrl+F")
        act_zoom_fit.triggered.connect(self.waveform.zoom_fit)
        menu_view.addAction(act_zoom_fit)

        # Help
        menu_help = menubar.addMenu("&Help")
        act_about = QtWidgets.QAction("&About Logic Analyzer", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    def _show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About HUST Logic Analyzer",
            "<h3>HUST Logic Analyzer (8 Channels, 6 MHz)</h3>"
            "<p><b>Lead Developer:</b> Nguyen Van Hoi (TV1 - Firmware Engineer)</p>"
            "<p><b>Platform:</b> STM32F401CCU6 WeAct Black Pill V3.0 (84 MHz Clock Tree)</p>"
            "<p><b>SSoT Protocol:</b> spec/protocol.md (32,776 B Data Frame, XOR Checksum)</p>"
            "<p><b>Design Spec:</b> docs/UI_SPEC.md (Saleae Logic 2 Commercial Standard)</p>"
            "<p>Hanoi University of Science and Technology (HUST) - 2026</p>"
        )

    # =========================================================================
    # BỐ CỤC CHÍNH (MAIN BODY + RIGHT PANEL + RAIL + BOTTOM BAR)
    # =========================================================================

    def _init_layout(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Vùng thân (Horizontal layout)
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # 1. Khung vẽ sóng (Waveform Widget)
        self.waveform = WaveformWidget(self)
        body.addWidget(self.waveform, 1)

        # 2. Panel phải (Analyzers / Trigger View / Data Table - 313 px)
        self.right_panel = self._create_right_panel()
        body.addWidget(self.right_panel)

        # 3. Dải Action Rail bên phải (Nút Start tròn Ø 50px - 65 px)
        self.rail = self._create_rail()
        body.addWidget(self.rail)

        # 4. Thanh đáy (Tab Session + Mức zoom - 42 px)
        self.bottom_bar = self._create_bottom_bar()
        outer.addWidget(self.bottom_bar)

    # =========================================================================
    # PANEL PHẢI (313 PX)
    # =========================================================================

    def _create_right_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget(self)
        panel.setFixedWidth(T.RIGHT_PANEL_WIDTH)
        panel.setStyleSheet(f"background-color: {T.BG_MAIN}; border-left: 1px solid {T.BORDER};")

        v_layout = QtWidgets.QVBoxLayout(panel)
        v_layout.setContentsMargins(12, 10, 12, 10)
        v_layout.setSpacing(8)

        # 1. Phần Analyzers
        h_ana = QtWidgets.QHBoxLayout()
        lbl_ana = QtWidgets.QLabel("Analyzers")
        lbl_ana.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {T.TEXT};")
        btn_add_ana = QtWidgets.QPushButton("+")
        btn_add_ana.setFixedSize(24, 24)
        btn_add_ana.setStyleSheet(f"font-size: 14px; font-weight: bold; padding: 0px;")
        btn_add_ana.clicked.connect(self._on_add_analyzer_dialog)
        h_ana.addWidget(lbl_ana)
        h_ana.addStretch(1)
        h_ana.addWidget(btn_add_ana)
        v_layout.addLayout(h_ana)

        # Mục analyzer đang kích hoạt
        self.lbl_ana_item = QtWidgets.QLabel(
            f"<span style='color:{T.DECODE_UART_BG}'>■</span> &nbsp;Async Serial &nbsp;"
            f"<span style='color:{T.ACCENT_START}'>✔</span>"
        )
        self.lbl_ana_item.setStyleSheet(f"font-size: 13px; color: {T.TEXT}; padding: 2px 4px;")
        v_layout.addWidget(self.lbl_ana_item)

        # 2. Thẻ thu gọn "Trigger View" (Card)
        self.card_trigger = QtWidgets.QFrame()
        self.card_trigger.setStyleSheet(f"""
            QFrame {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER};
                border-radius: 6px;
            }}
        """)
        card_v = QtWidgets.QVBoxLayout(self.card_trigger)
        card_v.setContentsMargins(10, 8, 10, 8)
        card_v.setSpacing(6)

        # Header của Card Trigger View
        card_h = QtWidgets.QHBoxLayout()
        self.lbl_card_title = QtWidgets.QLabel("› Trigger View ⚠")
        self.lbl_card_title.setStyleSheet("font-weight: bold; color: #f9b353;")
        self.btn_close_card = QtWidgets.QPushButton("✕")
        self.btn_close_card.setFixedSize(20, 20)
        self.btn_close_card.setStyleSheet(f"background: {T.BG_SELECT}; border-radius: 10px; padding: 0px;")
        self.btn_close_card.clicked.connect(self._toggle_trigger_card)
        card_h.addWidget(self.lbl_card_title)
        card_h.addStretch(1)
        card_h.addWidget(self.btn_close_card)
        card_v.addLayout(card_h)

        # Nội dung thiết lập Trigger & Cổng kết nối bên trong Card
        self.trigger_body = QtWidgets.QWidget()
        trig_layout = QtWidgets.QVBoxLayout(self.trigger_body)
        trig_layout.setContentsMargins(0, 4, 0, 0)
        trig_layout.setSpacing(6)

        # Cổng COM/ACM
        h_port = QtWidgets.QHBoxLayout()
        self.combo_ports = QtWidgets.QComboBox()
        self.btn_refresh = QtWidgets.QPushButton("⟳")
        self.btn_refresh.setFixedWidth(28)
        self.btn_refresh.setToolTip("Quét lại danh sách cổng serial")
        self.btn_refresh.clicked.connect(self._refresh_ports)
        h_port.addWidget(self.combo_ports, 1)
        h_port.addWidget(self.btn_refresh)
        trig_layout.addLayout(h_port)

        # Tần số lấy mẫu
        h_rate = QtWidgets.QHBoxLayout()
        lbl_rate = QtWidgets.QLabel("Rate:")
        lbl_rate.setStyleSheet(f"color: {T.TEXT_DIM};")
        self.combo_rate = QtWidgets.QComboBox()
        for label, val, idx in RATE_OPTIONS:
            self.combo_rate.addItem(label, idx)
        self.combo_rate.setCurrentIndex(3)  # Mặc định 1 MHz
        h_rate.addWidget(lbl_rate)
        h_rate.addWidget(self.combo_rate, 1)
        trig_layout.addLayout(h_rate)

        # Kênh Trigger & Chế độ
        h_trig = QtWidgets.QHBoxLayout()
        self.combo_ch = QtWidgets.QComboBox()
        for i in range(8):
            self.combo_ch.addItem(f"CH{i} (D{i})", i)
        self.combo_ch.setCurrentIndex(0)

        self.combo_mode = QtWidgets.QComboBox()
        self.combo_mode.addItem("Free-run", 0)
        self.combo_mode.addItem("Rising ↑", 1)
        self.combo_mode.addItem("Falling ↓", 2)
        self.combo_mode.setCurrentIndex(2)  # Mặc định Falling PA0
        h_trig.addWidget(self.combo_ch)
        h_trig.addWidget(self.combo_mode)
        trig_layout.addLayout(h_trig)

        # Checkbox Offline Mock
        self.chk_mock = QtWidgets.QCheckBox("Offline Mock (Test file .bin)")
        self.chk_mock.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
        trig_layout.addWidget(self.chk_mock)

        card_v.addWidget(self.trigger_body)
        v_layout.addWidget(self.card_trigger)

        # 3. Phần Data Table
        d_header = QtWidgets.QHBoxLayout()
        d_title = QtWidgets.QLabel(f"Data &nbsp;<span style='color:{T.ACCENT_START}'>✔</span>")
        d_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {T.TEXT};")
        d_header.addWidget(d_title)
        d_header.addStretch(1)
        v_layout.addLayout(d_header)

        # Ô tìm kiếm gói tin
        self.edit_search = QtWidgets.QLineEdit()
        self.edit_search.setPlaceholderText("Type to search")
        self.edit_search.textChanged.connect(self._filter_packet_table)
        v_layout.addWidget(self.edit_search)

        # Bảng dữ liệu gói tin 4 cột theo proto.py v3: [■ | Type | Start | Duration]
        self.table_uart_packets = QtWidgets.QTableWidget(0, 4)
        self.table_uart_packets.setHorizontalHeaderLabels(["", "Type", "Start", "Duration"])
        self.table_uart_packets.verticalHeader().setVisible(False)
        self.table_uart_packets.setAlternatingRowColors(True)
        self.table_uart_packets.setShowGrid(False)
        self.table_uart_packets.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_uart_packets.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_uart_packets.horizontalHeader().setStretchLastSection(True)
        self.table_uart_packets.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table_uart_packets.setColumnWidth(0, 26)
        self.table_uart_packets.setColumnWidth(1, 64)
        self.table_uart_packets.setColumnWidth(2, 95)
        self.table_uart_packets.cellClicked.connect(self._on_table_row_clicked)
        v_layout.addWidget(self.table_uart_packets, 1)

        # Terminal hiển thị chuỗi ASCII (hỗ trợ kiểm thử tự động)
        self.txt_uart_decoded = QtWidgets.QTextEdit()
        self.txt_uart_decoded.setReadOnly(True)
        self.txt_uart_decoded.setFixedHeight(75)
        self.txt_uart_decoded.setStyleSheet(f"""
            QTextEdit {{
                background-color: {T.BG_DEEP};
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                border: 1px solid {T.BORDER};
            }}
        """)
        v_layout.addWidget(self.txt_uart_decoded)

        return panel

    # =========================================================================
    # DẢI ACTION RAIL BÊN PHẢI (65 PX)
    # =========================================================================

    def _create_rail(self) -> QtWidgets.QWidget:
        rail = QtWidgets.QWidget(self)
        rail.setFixedWidth(T.RAIL_WIDTH)
        rail.setStyleSheet(f"background-color: {T.BG_MAIN}; border-left: 1px solid {T.BORDER};")

        v_layout = QtWidgets.QVBoxLayout(rail)
        v_layout.setContentsMargins(0, 10, 0, 10)
        v_layout.setSpacing(14)

        # Nút START tròn to màu xanh lá (Ø 50px)
        self.btn_rail_start = QtWidgets.QPushButton("▶")
        self.btn_rail_start.setObjectName("startButton")
        self.btn_rail_start.setToolTip("Bắt đầu lấy mẫu (F5)")
        self.btn_rail_start.clicked.connect(self._on_start_capture)
        v_layout.addWidget(self.btn_rail_start, 0, QtCore.Qt.AlignHCenter)

        # Nút ABORT nhỏ
        self.btn_rail_abort = QtWidgets.QPushButton("⏹")
        self.btn_rail_abort.setFixedSize(36, 36)
        self.btn_rail_abort.setToolTip("Hủy lượt lấy mẫu hiện tại (Esc)")
        self.btn_rail_abort.setStyleSheet("background-color: #ef4444; border-radius: 18px; color: #ffffff;")
        self.btn_rail_abort.clicked.connect(self._on_abort)
        v_layout.addWidget(self.btn_rail_abort, 0, QtCore.Qt.AlignHCenter)

        # Các icon công cụ theo chuẩn Saleae Logic 2
        tool_icons = [
            ("▭", "Bật/Tắt Card Trigger & Device Settings", self._toggle_trigger_card),
            ("1F", "Bộ giải mã & Bảng gói tin", lambda: self.edit_search.setFocus()),
            ("✎", "Bật/Tắt Cặp thước đo thời gian A & B (C)", self.waveform.toggle_cursors),
            ("▦", "Xuất báo cáo & Dữ liệu", self._export_image),
        ]
        for icon_text, tip, callback in tool_icons:
            btn = QtWidgets.QToolButton()
            btn.setText(icon_text)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"QToolButton {{ border: none; color: {T.TEXT_DIM}; font-size: 18px; }}")
            btn.clicked.connect(callback)
            v_layout.addWidget(btn, 0, QtCore.Qt.AlignHCenter)

        v_layout.addStretch(1)
        return rail

    # =========================================================================
    # THANH ĐÁY (42 PX)
    # =========================================================================

    def _create_bottom_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget(self)
        bar.setFixedHeight(T.BOTTOM_BAR_HEIGHT)
        bar.setStyleSheet(f"background-color: {T.BG_MAIN}; border-top: 1px solid {T.BORDER};")

        h_layout = QtWidgets.QHBoxLayout(bar)
        h_layout.setContentsMargins(10, 0, 14, 0)
        h_layout.setSpacing(12)

        # Tab Session bên trái
        self.tab_sessions = QtWidgets.QTabBar()
        self.tab_sessions.setExpanding(False)
        self.tab_sessions.addTab("Session 0")
        self.tab_sessions.addTab("Session 1")
        self.tab_sessions.addTab("+")
        self.tab_sessions.setCurrentIndex(1)
        h_layout.addWidget(self.tab_sessions)

        # Trạng thái kết nối ở giữa
        self.lbl_status = QtWidgets.QLabel("Ready | Offline Mock available")
        self.lbl_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px;")
        h_layout.addWidget(self.lbl_status)

        h_layout.addStretch(1)

        # Mức thu phóng ở góc phải
        self.lbl_zoom = QtWidgets.QLabel("128 µs ⌃")
        self.lbl_zoom.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px; font-weight: bold;")
        h_layout.addWidget(self.lbl_zoom)

        return bar

    # =========================================================================
    # CÁC HÀNH ĐỘNG ĐIỀU KHIỂN & SỰ KIỆN
    # =========================================================================

    def _toggle_trigger_card(self):
        """Ẩn/hiện nội dung Card Trigger View."""
        visible = not self.trigger_body.isVisible()
        self.trigger_body.setVisible(visible)
        self.lbl_card_title.setText("› Trigger View ⚠" if visible else "› Trigger View (Hidden)")

    def _refresh_ports(self):
        """Quét và làm mới danh sách cổng serial USB-CDC."""
        self.combo_ports.clear()
        ports = self.client.list_ports()
        if ports:
            for item in ports:
                if isinstance(item, (tuple, list)):
                    p_dev, p_desc = item[0], item[1]
                else:
                    p_dev, p_desc = str(item), str(item)
                self.combo_ports.addItem(p_desc, p_dev)
            self.lbl_status.setText(f"Tìm thấy {len(ports)} cổng serial USB-CDC")
        else:
            self.combo_ports.addItem("Không tìm thấy kit USB", None)
            self.lbl_status.setText("Chưa cắm kit STM32 (Bật 'Offline Mock' để test)")

    def _on_ping(self):
        """Gửi lệnh PING kiểm tra kết nối với kit STM32."""
        port = self.combo_ports.currentData() or self.combo_ports.currentText()
        if not port or "Không" in str(port):
            QtWidgets.QMessageBox.warning(self, "Lỗi cổng", "Vui lòng cắm kit STM32 hoặc chọn cổng phù hợp!")
            return

        ok, msg = self.client.connect(port)
        if not ok:
            QtWidgets.QMessageBox.critical(self, "Lỗi kết nối", f"Không thể mở cổng {port}:\n{msg}")
            return

        ping_ok, ver = self.client.ping()
        self.client.disconnect()
        if ping_ok:
            self.lbl_status.setText(f"Connected ({ver})")
            QtWidgets.QMessageBox.information(self, "PING thành công", f"Firmware Version: {ver}\nKết nối hoạt động 100%!")
        else:
            QtWidgets.QMessageBox.warning(self, "PING thất bại", f"Không nhận được phản hồi PONG:\n{ver}")

    def _on_start_capture(self):
        """Khởi động tiến trình lấy mẫu dữ liệu."""
        use_mock = self.chk_mock.isChecked()
        port = self.combo_ports.currentData() or self.combo_ports.currentText()

        rate_idx = self.combo_rate.currentData()
        trig_ch = self.combo_ch.currentData()
        trig_mode = self.combo_mode.currentData()

        if use_mock or port == "OFFLINE_MOCK":
            self.lbl_status.setText("Đang đọc dữ liệu giả lập offline (sample_data_1mhz.bin)...")
            res = self.client.start_capture(rate_idx=rate_idx, trig_ch=trig_ch, trig_mode=trig_mode, mock_mode=True)
            self._render_capture_data(res)
            return

        if not port or "Không" in str(port):
            # Tự động chuyển sang Mock nếu chưa cắm kit
            reply = QtWidgets.QMessageBox.question(
                self, "Chưa cắm kit",
                "Chưa tìm thấy kit STM32 USB-CDC. Bạn có muốn chạy chế độ Offline Mock không?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.chk_mock.setChecked(True)
                self._on_start_capture()
            return

        ok, msg = self.client.connect(port)
        if not ok:
            QtWidgets.QMessageBox.critical(self, "Lỗi kết nối", f"Không thể mở cổng {port}:\n{msg}")
            return

        self.btn_rail_start.setEnabled(False)
        self.lbl_status.setText(f"Đang chờ bắt tín hiệu trên cổng {port}...")

        self.worker = CaptureWorker(self.client, rate_idx, trig_ch, trig_mode)
        self.worker.capture_done.connect(self._on_capture_done)
        self.worker.capture_error.connect(self._on_capture_error)
        self.worker.start()

    def _on_capture_done(self, res: dict):
        self.btn_rail_start.setEnabled(True)
        self.client.disconnect()
        self._render_capture_data(res)

    def _on_capture_error(self, err_msg: str):
        self.btn_rail_start.setEnabled(True)
        self.client.disconnect()
        self.lbl_status.setText(f"Lỗi: {err_msg}")
        QtWidgets.QMessageBox.critical(self, "Lỗi lấy mẫu", err_msg)

    def _on_abort(self):
        """Gửi lệnh hủy thu thập dữ liệu."""
        if self.worker and self.worker.isRunning():
            self.client.abort()
            self.worker.terminate()
            self.worker.wait()
            self.btn_rail_start.setEnabled(True)
            self.client.disconnect()
            self.lbl_status.setText("Đã hủy lượt lấy mẫu (Capture aborted)")
        else:
            self.lbl_status.setText("Không có tiến trình lấy mẫu nào đang chạy")

    def _render_capture_data(self, res: dict):
        """Hiển thị kết quả thu thập dữ liệu và giải mã protocol."""
        self.current_data = res
        self.waveform.render_data(res)

        fs = float(res.get("sample_rate", 1_000_000))
        status_name = res.get("status_name", "Triggered")
        elapsed = res.get("elapsed_s", 0.0)

        rate_str = f"{fs/1e6:.1f} MHz" if fs >= 1e6 else f"{fs/1e3:.0f} kHz"
        self.lbl_status.setText(f"Hoàn tất: 32,768 mẫu ({rate_str}) | {status_name} trong {elapsed:.3f} s")

        # Tự động giải mã UART trên Kênh 0
        self._decode_uart()

    def _decode_uart(self):
        """Giải mã UART, điền bảng dữ liệu và vẽ bong bóng chú thích trực tiếp trên sóng."""
        if not self.current_data:
            return

        ch0_samples = self.current_data["channels"][0].tolist()
        fs = float(self.current_data.get("sample_rate", 1_000_000))
        trig_offset = int(self.current_data.get("trig_offset", 6554))

        self.uart_decoder.sample_rate = fs
        self.uart_decoder.baudrate = 115200

        text, frames = self.uart_decoder.decode(ch0_samples, start_idx=max(0, trig_offset - 50))
        self.current_uart_frames = frames

        # 1. Điền chuỗi văn bản ASCII
        self.txt_uart_decoded.setPlainText(text)

        # 2. Điền Bảng dữ liệu 4 cột: [■ | Type | Start | Duration]
        self.table_uart_packets.setRowCount(0)
        self.table_uart_packets.setRowCount(len(frames))

        for r, frame in enumerate(frames):
            start_idx = frame.get("start_sample", frame.get("start_idx", 0))
            stop_idx = frame.get("stop_sample", frame.get("stop_idx", start_idx + 10))
            val = frame.get("byte_val", frame.get("val", 0))
            char = frame.get("char", "")
            start_s = (start_idx - trig_offset) / fs
            dur_s = (stop_idx - start_idx) / fs

            # Cột 0: Marker màu DECODE_UART_BG
            it_m = QtWidgets.QTableWidgetItem("■")
            it_m.setForeground(QtGui.QBrush(QtGui.QColor(T.DECODE_UART_BG)))
            it_m.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_uart_packets.setItem(r, 0, it_m)

            # Cột 1: Type (data: 0x54 'T')
            type_str = f"data"
            it_type = QtWidgets.QTableWidgetItem(type_str)
            it_type.setToolTip(f"Hex: 0x{val:02X} | ASCII: '{char}'")
            self.table_uart_packets.setItem(r, 1, it_type)

            # Cột 2: Start time
            start_str = f"{start_s * 1e6:.1f} µs" if abs(start_s) < 1e-3 else f"{start_s * 1e3:.2f} ms"
            it_start = QtWidgets.QTableWidgetItem(start_str)
            it_start.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table_uart_packets.setItem(r, 2, it_start)

            # Cột 3: Duration
            dur_str = f"{dur_s * 1e6:.2f} µs"
            it_dur = QtWidgets.QTableWidgetItem(dur_str)
            it_dur.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table_uart_packets.setItem(r, 3, it_dur)

            # Lưu mốc thời gian tuyệt đối để click nhảy sóng
            it_type.setData(QtCore.Qt.UserRole, (start_idx / fs, stop_idx / fs))

        # 3. Vẽ các bong bóng chú thích UART và chấm bit trực tiếp lên sóng Kênh 0
        self.waveform.render_uart_decorations(frames, fs, trig_offset)

    def _filter_packet_table(self, query: str):
        """Lọc các hàng trong bảng dữ liệu theo chuỗi tìm kiếm."""
        q = query.strip().lower()
        for r in range(self.table_uart_packets.rowCount()):
            match = False
            for c in range(1, self.table_uart_packets.columnCount()):
                item = self.table_uart_packets.item(r, c)
                if item and (q in item.text().lower() or (item.toolTip() and q in item.toolTip().lower())):
                    match = True
                    break
            self.table_uart_packets.setRowHidden(r, not match and len(q) > 0)

    def _on_table_row_clicked(self, row: int, col: int):
        """Khi bấm vào một hàng trong bảng, phóng to và căn giữa byte đó trên sóng."""
        item = self.table_uart_packets.item(row, 1)
        if item:
            data = item.data(QtCore.Qt.UserRole)
            if data:
                t_start_abs, t_stop_abs = data
                self.waveform.zoom_to_window(t_start_abs, t_stop_abs)

    def _on_channel_name_changed(self, ch: int):
        if 0 <= ch < 8:
            new_name = self.ch_edits[ch].text().strip()
            self.waveform.set_channel_name(ch, new_name)

    def _on_channel_visibility_changed(self, ch: int, state):
        if 0 <= ch < 8:
            visible = (state == QtCore.Qt.Checked or state == 1 or state is True)
            self.waveform.set_channel_visible(ch, visible)

    def _on_decode_uart(self):
        self._decode_uart()

    def _on_add_analyzer_dialog(self):
        QtWidgets.QMessageBox.information(
            self, "Analyzers",
            "Async Serial (UART) đã được kích hoạt trên Kênh 0 (115200 bps, 8-N-1).\n"
            "Các bộ giải mã I2C và SPI có thể bổ sung trong menu Capture/Decoders."
        )

    def _load_bin_file(self, filepath: str):
        """Đọc và vẽ file dữ liệu nhị phân 32.776B (.bin)."""
        with open(filepath, "rb") as f:
            raw_bytes = f.read()

        if len(raw_bytes) != 32776:
            return

        payload = np.frombuffer(raw_bytes[7:32775], dtype=np.uint8)
        channels = [((payload >> bit) & 1).astype(np.uint8) for bit in range(8)]
        res = {
            "success": True,
            "status": 0,
            "status_name": "Triggered (STATUS_TRIGGER_OK)",
            "rate_idx": 3,
            "sample_rate": 1_000_000,
            "trig_offset": 6554,
            "sample_count": 32768,
            "channels": channels,
            "checksum_ok": True,
            "elapsed_s": 0.05
        }
        self._render_capture_data(res)

    def _open_capture_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Raw Capture File", "", "Binary Capture (*.bin);;All Files (*)"
        )
        if path:
            self._load_bin_file(path)

    def _export_image(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Waveform Image", "waveform.png", "PNG Image (*.png);;SVG Image (*.svg)"
        )
        if path:
            ok = export_image(self.waveform.plot_widget, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Thành Công", f"Đã xuất ảnh đồ thị ra:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Thất Bại", "Không thể xuất ảnh đồ thị.")

    def _export_csv(self):
        if not self.current_data:
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Chưa có dữ liệu capture để xuất CSV.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export CSV Data", "capture_data.csv", "CSV Spreadsheet (*.csv)"
        )
        if path:
            ok = export_csv(self.current_data, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Thành Công", f"Đã xuất dữ liệu CSV ra:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Thất Bại", "Không thể xuất file CSV.")

    def _export_vcd(self):
        if not self.current_data:
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Chưa có dữ liệu capture để xuất VCD.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export VCD File", "capture.vcd", "Value Change Dump (*.vcd)"
        )
        if path:
            ok = export_vcd(self.current_data, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Thành Công", f"Đã xuất file VCD GTKWave ra:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Thất Bại", "Không thể xuất file VCD.")
