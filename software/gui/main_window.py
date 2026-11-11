#!/usr/bin/env python3
"""software/gui/main_window.py
Giao diện người dùng Desktop Logic Analyzer 8 kênh 6 MHz:
- Cấu trúc bố cục theo docs/UI_SPEC.md:
  + Menu Bar: File, Edit, Capture, Measure, View, Help
  + Waveform Viewport (Vùng sóng chiếm ưu thế): Cột nhãn 180px + PlotWidget 8 kênh co giãn lấp đầy
  + Panel phải (310px): Analyzers, Device Settings card, Measurements card, Data Table 5 cột, Tìm kiếm
  + Dải Activity Rail bên phải (56px): Nút Start tròn xanh lá (Ø 48px) + các icon công cụ
  + Thanh đáy (36px): Session tabs (Session 0, Session 1, +) + Trạng thái kết nối + Mức zoom
- Giao thức nhị phân chuẩn spec/protocol.md (Khung lệnh 5B, Data Frame 32.776B)
- Tích hợp bộ giải mã UART/I2C/SPI trực tiếp trên sóng và bảng gói tin.
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
from software.gui.waveform_widget import WaveformWidget, format_si_time
from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder
from software.utils.exporter import export_image, export_csv, export_vcd
from software.gui.measurements import measure_channel_signal, format_measurement_results, find_most_active_channel

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
        self.is_aborted = False

    def run(self):
        try:
            res = self.client.start_capture(
                rate_idx=self.rate_idx,
                trig_ch=self.trig_ch,
                trig_mode=self.trig_mode
            )
            if self.is_aborted:
                return
            if res.get("success", False):
                self.capture_done.emit(res)
            else:
                self.capture_error.emit(res.get("error", "Lỗi thu thập dữ liệu"))
        except Exception as e:
            if not self.is_aborted:
                self.capture_error.emit(str(e))


class RailSwitcherSlot(QtWidgets.QFrame):
    """Slot chứa switcher trên Activity Rail.
    
    Kích thước 56x56px, vạch chỉ báo 2px border-left #ffffff và nền #2c2c2e khi được chọn.
    """
    def __init__(self, btn: QtWidgets.QToolButton, parent=None):
        super().__init__(parent)
        self.btn = btn
        self.btn.slot = self
        self.setFixedSize(56, 56)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(btn, 0, QtCore.Qt.AlignCenter)
        self.set_selected(False)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.btn.click()
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        font_sz = "12px" if len(self.btn.text()) >= 3 else "16px"
        if selected:
            self.setStyleSheet(f"""
                QFrame {{
                    border-left: 2px solid #ffffff;
                    background-color: {T.BG_CARD};
                }}
            """)
            self.btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 18px;
                    color: #ffffff;
                    font-size: {font_sz};
                    font-weight: 700;
                    padding: 0px;
                }}
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border-left: 2px solid transparent;
                    background-color: transparent;
                }
            """)
            self.btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 18px;
                    color: {T.TEXT_DIM};
                    font-size: {font_sz};
                    font-weight: 600;
                    padding: 0px;
                }}
                QToolButton:hover {{
                    background-color: #424246;
                    color: #ffffff;
                }}
            """)


class MainWindow(QtWidgets.QMainWindow):
    """Cửa sổ chính Desktop Logic Analyzer theo UI_SPEC.md."""

    def __init__(self, load_sample_on_start: bool = False):
        super().__init__()
        self.setWindowTitle("HUST Logic Analyzer (8 Channels, 6 MHz) — Lead Dev: Nguyen Van Hoi")
        self.resize(1280, 860)
        self.setMinimumSize(1080, 600)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            T.apply_theme(app)
        self.setStyleSheet(T.QSS)

        # Lớp Client & Worker
        self.client = LogicAnalyzerClient()
        self.worker: Optional[CaptureWorker] = None

        # Bộ giải mã
        self.uart_decoder = UARTDecoder(sample_rate=1_000_000, baudrate=115200)
        self.i2c_decoder = I2CDecoder(sample_rate=1_000_000)
        self.spi_decoder = SPIDecoder(sample_rate=1_000_000)

        # Dữ liệu hiện hành & Quản lý Session Tabs
        self.current_data: Optional[Dict[str, Any]] = None
        self.current_uart_frames: List[Dict[str, Any]] = []
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.current_analyzer: str = "uart"
        self._next_session_id: int = 1
        self.drawer_open: bool = True

        # Chế độ Capture: Single Shot vs Auto-Repeat Run
        self.repeat_mode: bool = False
        self.repeat_running: bool = False
        self.repeat_frame_count: int = 0

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
        self._update_capture_mode_ui()
        # Kết nối tín hiệu khung nhìn để cập nhật chỉ số Zoom trên thanh Footer
        self.waveform.sigXRangeChanged.connect(self._on_x_range_changed)
        # Kết nối tín hiệu điều hướng 2 chiều: Ctrl+Click vào bubble trên sóng -> cuộn bảng Data Table
        self.waveform.sigBubbleCtrlClicked.connect(self._on_bubble_ctrl_clicked)

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

        # Nạp dữ liệu giả lập ban đầu nếu có yêu cầu (mặc định False để màn hình sạch khi khởi động)
        if load_sample_on_start:
            sample_file = os.path.join(os.path.dirname(__file__), "..", "tests", "sample_data_1mhz.bin")
            if os.path.exists(sample_file):
                self._load_bin_file(sample_file)
                # Zoom mặc định vào vùng gói dữ liệu UART quanh Trigger để người dùng thấy rõ sóng & bong bóng ngay
                self.waveform.plot_widget.setXRange(-0.00015, 0.00145, padding=0)

        # Quét và tự động kết nối phần cứng STM32 USB-CDC
        self.connected_port: Optional[str] = None
        self._last_known_ports: set = set()
        self._refresh_ports(auto_connect=True)

        # Watchdog quét định kỳ hotplug (tự động nhận diện khi cắm/rút USB - mỗi 1.5s)
        self.timer_hotplug = QtCore.QTimer(self)
        self.timer_hotplug.setInterval(1500)
        self.timer_hotplug.timeout.connect(self._check_hotplug)
        self.timer_hotplug.start()

    # =========================================================================
    # THANH MENU (FILE / EDIT / CAPTURE / MEASURE / VIEW / HELP)
    # =========================================================================

    def _init_menu_bar(self):
        menubar = self.menuBar()

        # File
        menu_file = menubar.addMenu("&File")
        act_open = QtWidgets.QAction("&Open Capture (.bin)...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.setStatusTip("Open raw 32KB binary capture file")
        act_open.triggered.connect(self._open_capture_file)
        menu_file.addAction(act_open)

        menu_file.addSeparator()

        act_exp_img = QtWidgets.QAction("Export &Image (PNG, SVG)...", self)
        act_exp_img.setShortcut("Ctrl+S")
        act_exp_img.setStatusTip("Export current waveform view as image")
        act_exp_img.triggered.connect(self._export_image)
        menu_file.addAction(act_exp_img)

        act_exp_csv = QtWidgets.QAction("Export &CSV Data...", self)
        act_exp_csv.setShortcut("Ctrl+E")
        act_exp_csv.setStatusTip("Export all 32,768 samples to CSV spreadsheet")
        act_exp_csv.triggered.connect(self._export_csv)
        menu_file.addAction(act_exp_csv)

        act_exp_vcd = QtWidgets.QAction("Export &VCD (GTKWave)...", self)
        act_exp_vcd.setShortcut("Ctrl+V")
        act_exp_vcd.setStatusTip("Export digital waveforms in IEEE 1364 VCD format")
        act_exp_vcd.triggered.connect(self._export_vcd)
        menu_file.addAction(act_exp_vcd)

        menu_file.addSeparator()

        act_exit = QtWidgets.QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.setStatusTip("Exit Application")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Edit
        menu_edit = menubar.addMenu("&Edit")
        act_reset_cursors = QtWidgets.QAction("&Reset Cursors", self)
        act_reset_cursors.setStatusTip("Reset timing cursors A & B to default positions")
        act_reset_cursors.triggered.connect(lambda: self.waveform.set_cursor_positions(0.0, 8.68e-5))
        menu_edit.addAction(act_reset_cursors)

        act_clear = QtWidgets.QAction("&Clear Capture Data", self)
        act_clear.setStatusTip("Clear current waveform data and decoders")
        act_clear.triggered.connect(self._on_clear_capture_data)
        menu_edit.addAction(act_clear)

        # Capture
        menu_capture = menubar.addMenu("&Capture")
        act_start = QtWidgets.QAction("&Start / Pause Capture", self)
        act_start.setShortcut("F5")
        act_start.setStatusTip("Trigger capture or pause/resume continuous repeat")
        act_start.triggered.connect(self._on_start_or_abort)
        menu_capture.addAction(act_start)

        act_toggle_mode = QtWidgets.QAction("Toggle &Single / Repeat Mode", self)
        act_toggle_mode.setShortcut("F6")
        act_toggle_mode.setStatusTip("Switch between Single Shot [1x] and Auto-Repeat Continuous Run [🔁]")
        act_toggle_mode.triggered.connect(self._toggle_capture_mode)
        menu_capture.addAction(act_toggle_mode)

        act_abort = QtWidgets.QAction("&Abort Capture", self)
        act_abort.setShortcut("Escape")
        act_abort.setStatusTip("Stop/abort running capture session")
        act_abort.triggered.connect(self._on_abort)
        menu_capture.addAction(act_abort)

        menu_capture.addSeparator()

        act_ping = QtWidgets.QAction("Check Hardware (&Ping)", self)
        act_ping.setStatusTip("Send Ping (0x03) to STM32 and verify Pong (0x04)")
        act_ping.triggered.connect(self._on_ping)
        menu_capture.addAction(act_ping)

        # Measure
        menu_measure = menubar.addMenu("&Measure")
        act_toggle_cursors = QtWidgets.QAction("Toggle &Timing Cursors (A & B)", self)
        act_toggle_cursors.setShortcut("C")
        act_toggle_cursors.setStatusTip("Show/hide timing cursors A & B with delta measurement")
        act_toggle_cursors.triggered.connect(self._toggle_cursors)
        menu_measure.addAction(act_toggle_cursors)

        act_meas = QtWidgets.QAction("&Automated Channel Measurements", self)
        act_meas.setShortcut("M")
        act_meas.setStatusTip("Toggle Automated Channel Measurements panel")
        act_meas.triggered.connect(self._toggle_measurements_card)
        menu_measure.addAction(act_meas)

        act_autodetect = QtWidgets.QAction("⚡ &Auto-Detect Active Channel", self)
        act_autodetect.setShortcut("Ctrl+M")
        act_autodetect.setStatusTip("Auto-scan all channels and measure the one with active transitions")
        act_autodetect.triggered.connect(self._on_meas_autodetect)
        menu_measure.addAction(act_autodetect)

        # View
        menu_view = menubar.addMenu("&View")
        act_zoom_fit = QtWidgets.QAction("&Zoom to Fit", self)
        act_zoom_fit.setShortcut("Ctrl+F")
        act_zoom_fit.setStatusTip("Zoom and fit all waveform data into view")
        act_zoom_fit.triggered.connect(self.waveform.zoom_fit)
        menu_view.addAction(act_zoom_fit)

        act_toggle_drawer = QtWidgets.QAction("Toggle &Drawer Panel", self)
        act_toggle_drawer.setShortcut("Alt+A")
        act_toggle_drawer.setStatusTip("Show/hide right sidebar drawer panel")
        act_toggle_drawer.triggered.connect(self._toggle_drawer_panel)
        menu_view.addAction(act_toggle_drawer)

        act_toggle_device = QtWidgets.QAction("Toggle &Device Settings", self)
        act_toggle_device.setShortcut("Alt+D")
        act_toggle_device.setStatusTip("Show/hide device & trigger settings panel")
        act_toggle_device.triggered.connect(self._toggle_trigger_card)
        menu_view.addAction(act_toggle_device)

        # Help
        menu_help = menubar.addMenu("&Help")
        act_about = QtWidgets.QAction("&About Logic Analyzer...", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

        act_shortcuts = QtWidgets.QAction("&Keyboard Shortcuts...", self)
        act_shortcuts.triggered.connect(self._show_shortcuts)
        menu_help.addAction(act_shortcuts)

    def _show_shortcuts(self):
        QtWidgets.QMessageBox.information(
            self,
            "Keyboard Shortcuts - HUST Logic Analyzer",
            "<h3>Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>F5</b></td><td>Start Capture</td></tr>"
            "<tr><td><b>Escape</b></td><td>Abort / Stop Capture</td></tr>"
            "<tr><td><b>C</b></td><td>Toggle Timing Cursors (A & B)</td></tr>"
            "<tr><td><b>M</b></td><td>Toggle Automated Measurements</td></tr>"
            "<tr><td><b>Ctrl+M</b></td><td>Auto-Detect Active Channel</td></tr>"
            "<tr><td><b>Ctrl+F</b></td><td>Zoom to Fit</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Open Binary Capture (.bin)</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Export Waveform Image</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>Export CSV Data</td></tr>"
            "<tr><td><b>Ctrl+V</b></td><td>Export GTKWave VCD</td></tr>"
            "<tr><td><b>Ctrl+N</b></td><td>New Session Tab</td></tr>"
            "<tr><td><b>Alt+A</b></td><td>Toggle Analyzers Drawer</td></tr>"
            "<tr><td><b>Alt+D</b></td><td>Toggle Device Settings</td></tr>"
            "<tr><td><b>Ctrl+Click (Bubble)</b></td><td>Select Packet in Data Table</td></tr>"
            "</table>"
        )

    def _on_clear_capture_data(self):
        self.current_data = None
        self.waveform.clear_data()
        if hasattr(self, "txt_uart_decoded"):
            self.txt_uart_decoded.clear()
        if hasattr(self, "table_uart_packets"):
            self.table_uart_packets.setRowCount(0)
        curr_name = self.tab_sessions.tabText(self.tab_sessions.currentIndex())
        self.lbl_status.setText(f"{curr_name}: Ready for capture")

    def _show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About HUST Logic Analyzer",
            "<h3>HUST Logic Analyzer (8 Channels, 6 MHz)</h3>"
            "<p><b>Lead Developer:</b> Nguyen Van Hoi (TV1 - Firmware Engineer)</p>"
            "<p><b>Platform:</b> STM32F401CCU6 WeAct Black Pill V3.0 (84 MHz Clock Tree)</p>"
            "<p><b>SSoT Protocol:</b> spec/protocol.md (32,776 B Data Frame, XOR Checksum)</p>"
            "<p><b>Design Spec:</b> docs/UI_SPEC.md (Dark Theme UI Specification)</p>"
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

        # 4. Thanh đáy (Tab Session + Mức zoom - 36 px)
        self.bottom_bar = self._create_bottom_bar()
        outer.addWidget(self.bottom_bar)

    # =========================================================================
    # PANEL PHẢI (310 PX, DRAWER PANEL)
    # =========================================================================

    def _create_right_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget(self)
        panel.setObjectName("drawerPanel")
        panel.setFixedWidth(T.RIGHT_PANEL_WIDTH)
        panel.setStyleSheet(f"#drawerPanel {{ background-color: {T.BG_MAIN}; border-left: 1px solid {T.BORDER_MUTED}; }}")

        v_layout = QtWidgets.QVBoxLayout(panel)
        v_layout.setContentsMargins(14, 12, 14, 12)
        v_layout.setSpacing(10)

        # 1. Phần Analyzers (Tiêu đề 16px font-weight 500)
        h_ana = QtWidgets.QHBoxLayout()
        lbl_ana = QtWidgets.QLabel("Analyzers")
        lbl_ana.setStyleSheet(f"font-family: 'Roboto', sans-serif; font-size: 16px; font-weight: 500; color: #e0e0e0;")
        self.btn_add_ana = QtWidgets.QPushButton("+")
        self.btn_add_ana.setToolTip("Add Protocol Analyzer")
        self.btn_add_ana.setFixedSize(24, 24)
        self.btn_add_ana.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                color: {T.TEXT_DIM};
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
        """)
        self.btn_add_ana.clicked.connect(self._on_add_analyzer_dialog)
        h_ana.addWidget(lbl_ana)
        h_ana.addStretch(1)
        h_ana.addWidget(self.btn_add_ana)
        v_layout.addLayout(h_ana)

        # Mục analyzer đang kích hoạt (sidebarMenuItem)
        self.lbl_ana_item = QtWidgets.QLabel(
            f"<span style='color:{T.DECODE_UART_BG};font-size:10px;'>■</span> &nbsp;Async Serial &nbsp;"
            f"<span style='color:{T.ACCENT_START}'>✔</span>"
        )
        self.lbl_ana_item.setToolTip("Active Analyzer: Async Serial (Channel 0 @ 115,200 bps)")
        self.lbl_ana_item.setStyleSheet(f"""
            QLabel {{
                font-family: 'Roboto', sans-serif;
                font-size: 13px;
                font-weight: 500;
                color: {T.TEXT};
                background-color: {T.BG_MAIN};
                padding: 6px 8px;
                border-radius: 4px;
            }}
            QLabel:hover {{
                background-color: {T.BG_SELECT};
            }}
        """)
        v_layout.addWidget(self.lbl_ana_item)

        # 2. Thẻ thu gọn "Device Settings" (Card background-30 #2c2c2e)
        self.card_trigger = QtWidgets.QFrame()
        self.card_trigger.setObjectName("cardTrigger")
        self.card_trigger.setStyleSheet(f"""
            QFrame#cardTrigger {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
            }}
            QFrame#cardTrigger QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        card_v = QtWidgets.QVBoxLayout(self.card_trigger)
        card_v.setContentsMargins(10, 8, 10, 8)
        card_v.setSpacing(6)

        # Header của Card Device Settings
        card_h = QtWidgets.QHBoxLayout()
        self.lbl_card_title = QtWidgets.QLabel("› Device Settings")
        self.lbl_card_title.setStyleSheet("font-family: 'Roboto', sans-serif; font-size: 12px; font-weight: 600; color: #e0e0e0; background: transparent; border: none;")
        self.btn_close_card = QtWidgets.QPushButton("✕")
        self.btn_close_card.setToolTip("Collapse Section")
        self.btn_close_card.setFixedSize(20, 20)
        self.btn_close_card.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 10px;
                color: {T.TEXT_DIM};
                font-size: 11px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
        """)
        self.btn_close_card.clicked.connect(self._toggle_trigger_card)
        card_h.addWidget(self.lbl_card_title)
        card_h.addStretch(1)
        card_h.addWidget(self.btn_close_card)
        card_v.addLayout(card_h)

        # Nội dung thiết lập Trigger & Cổng kết nối bên trong Card
        self.trigger_body = QtWidgets.QWidget()
        self.trigger_body.setStyleSheet("background-color: transparent;")
        trig_layout = QtWidgets.QVBoxLayout(self.trigger_body)
        trig_layout.setContentsMargins(0, 4, 0, 0)
        trig_layout.setSpacing(6)

        # Nút làm mới cổng serial USB-CDC
        h_port = QtWidgets.QHBoxLayout()
        self.combo_ports = QtWidgets.QComboBox()
        self.combo_ports.currentIndexChanged.connect(self._on_port_changed)
        self.btn_refresh = QtWidgets.QPushButton("↻")
        self.btn_refresh.setFixedSize(28, 26)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
                padding: 0px;
                color: {T.TEXT};
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {T.BG_SELECT};
            }}
        """)
        self.btn_refresh.setToolTip("Rescan Serial Ports")
        self.btn_refresh.clicked.connect(lambda: self._refresh_ports(auto_connect=True))
        h_port.addWidget(self.combo_ports, 1)
        h_port.addWidget(self.btn_refresh)
        trig_layout.addLayout(h_port)

        # Tần số lấy mẫu
        h_rate = QtWidgets.QHBoxLayout()
        lbl_rate = QtWidgets.QLabel("Rate:")
        lbl_rate.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px; background: transparent; border: none;")
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
        self.combo_mode.addItem("Free-run (No Trigger)", 0)
        self.combo_mode.addItem("Rising Edge ↑", 1)
        self.combo_mode.addItem("Falling Edge ↓", 2)
        self.combo_mode.setCurrentIndex(2)  # Mặc định Falling PA0
        h_trig.addWidget(self.combo_ch)
        h_trig.addWidget(self.combo_mode)
        trig_layout.addLayout(h_trig)

        # Chế độ lấy mẫu (Single Shot / Auto-Repeat Run)
        h_cap_mode = QtWidgets.QHBoxLayout()
        lbl_cap_mode = QtWidgets.QLabel("Mode:")
        lbl_cap_mode.setStyleSheet(f"color: {T.TEXT_DIM};")
        self.combo_capture_mode = QtWidgets.QComboBox()
        self.combo_capture_mode.addItem("Single Shot (1x)", "single")
        self.combo_capture_mode.addItem("Auto-Repeat (Run) 🔁", "repeat")
        self.combo_capture_mode.currentIndexChanged.connect(self._on_capture_combo_changed)
        h_cap_mode.addWidget(lbl_cap_mode)
        h_cap_mode.addWidget(self.combo_capture_mode, 1)
        trig_layout.addLayout(h_cap_mode)

        # Checkbox Offline Mock
        self.chk_mock = QtWidgets.QCheckBox("Offline Mock (Sample File)")
        self.chk_mock.setToolTip("Load sample_data_1mhz.bin without physical STM32 hardware")
        trig_layout.addWidget(self.chk_mock)

        card_v.addWidget(self.trigger_body)
        v_layout.addWidget(self.card_trigger)

        # 3. Thẻ đo đạc & thống kê tự động "Measurements" (Card background-30 #2c2c2e)
        self.card_measurements = QtWidgets.QFrame()
        self.card_measurements.setObjectName("cardMeasurements")
        self.card_measurements.setStyleSheet(f"""
            QFrame#cardMeasurements {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
            }}
            QFrame#cardMeasurements QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        meas_v = QtWidgets.QVBoxLayout(self.card_measurements)
        meas_v.setContentsMargins(10, 8, 10, 8)
        meas_v.setSpacing(6)

        # Header của Card Measurements
        meas_h = QtWidgets.QHBoxLayout()
        self.lbl_meas_title = QtWidgets.QLabel(f"<span style='color:{T.CHANNEL_COLORS[0]}'>■</span> &nbsp;Measurements (D0)")
        self.lbl_meas_title.setStyleSheet("font-family: 'Roboto', sans-serif; font-size: 12px; font-weight: 600; color: #e0e0e0; background: transparent; border: none;")

        # Combo chọn kênh đo (CH0..CH7)
        self.combo_meas_ch = QtWidgets.QComboBox()
        self.combo_meas_ch.setToolTip("Select Channel to Measure")
        self.combo_meas_ch.setFixedHeight(22)
        for i in range(8):
            self.combo_meas_ch.addItem(f"CH{i} (D{i})", i)
        self.combo_meas_ch.setCurrentIndex(0)
        self.combo_meas_ch.currentIndexChanged.connect(self._update_automated_measurements)

        self.btn_close_meas = QtWidgets.QPushButton("✕")
        self.btn_close_meas.setToolTip("Collapse Section")
        self.btn_close_meas.setFixedSize(20, 20)
        self.btn_close_meas.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 10px;
                color: {T.TEXT_DIM};
                font-size: 11px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
        """)
        self.btn_close_meas.clicked.connect(self._toggle_measurements_card)

        meas_h.addWidget(self.lbl_meas_title)
        meas_h.addStretch(1)
        meas_h.addWidget(self.combo_meas_ch)
        meas_h.addWidget(self.btn_close_meas)
        meas_v.addLayout(meas_h)

        # Body chứa bảng các thông số kỹ thuật (Grid layout)
        self.meas_body = QtWidgets.QWidget()
        self.meas_body.setStyleSheet("background-color: transparent;")
        meas_grid = QtWidgets.QGridLayout(self.meas_body)
        meas_grid.setContentsMargins(0, 4, 0, 4)
        meas_grid.setHorizontalSpacing(10)
        meas_grid.setVerticalSpacing(4)

        # Helper tạo nhãn key/val chuẩn Dark Theme (nhãn xám mờ, giá trị trắng sáng monospace)
        def make_meas_row(row_idx, key_name, default_color="#ffffff"):
            lbl_k = QtWidgets.QLabel(key_name)
            lbl_k.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; font-family: 'Roboto', sans-serif; background: transparent; border: none;")
            lbl_v = QtWidgets.QLabel("N/A")
            lbl_v.setStyleSheet(f"color: {default_color}; font-size: 11px; font-weight: 600; font-family: 'Roboto Mono', 'DejaVu Sans Mono', monospace; background: transparent; border: none;")
            lbl_v.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            meas_grid.addWidget(lbl_k, row_idx, 0)
            meas_grid.addWidget(lbl_v, row_idx, 1)
            return lbl_v

        self.lbl_m_freq = make_meas_row(0, "Frequency (f):", "#58c667")
        self.lbl_m_period = make_meas_row(1, "Period (T):")
        self.lbl_m_duty = make_meas_row(2, "Duty Cycle:")
        self.lbl_m_thigh = make_meas_row(3, "+Width (t_high):")
        self.lbl_m_tlow = make_meas_row(4, "-Width (t_low):")
        self.lbl_m_trans = make_meas_row(5, "Transitions:")
        self.lbl_m_pulse = make_meas_row(6, "Min Pulse:")

        # Nút Auto-detect
        self.btn_meas_autodetect = QtWidgets.QPushButton("⚡ Auto-Detect Active Channel")
        self.btn_meas_autodetect.setToolTip("Scan all channels and measure the one with active transitions (Ctrl+M)")
        self.btn_meas_autodetect.setFixedHeight(22)
        self.btn_meas_autodetect.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.BG_MAIN};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 3px;
                color: #e0e0e0;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
                border: 1px solid {T.HIGHLIGHT};
            }}
        """)
        self.btn_meas_autodetect.clicked.connect(self._on_meas_autodetect)

        meas_v.addWidget(self.meas_body)
        meas_v.addWidget(self.btn_meas_autodetect)
        v_layout.addWidget(self.card_measurements)

        # 4. Phần Data Table
        d_header = QtWidgets.QHBoxLayout()
        d_title = QtWidgets.QLabel(f"Data &nbsp;<span style='color:{T.ACCENT_START}'>✔</span>")
        d_title.setStyleSheet("font-family: 'Roboto', sans-serif; font-size: 16px; font-weight: 500; color: #e0e0e0; background: transparent; border: none;")
        d_header.addWidget(d_title)
        d_header.addStretch(1)

        # Switcher Data View: Table [▦] vs Terminal [>_]
        self.btn_pane_table = QtWidgets.QToolButton()
        self.btn_pane_table.setText("▦")
        self.btn_pane_table.setToolTip("Data Table View")
        self.btn_pane_table.setFixedSize(24, 24)
        self.btn_pane_table.clicked.connect(lambda: self._switch_data_pane(0))

        self.btn_pane_terminal = QtWidgets.QToolButton()
        self.btn_pane_terminal.setText(">_")
        self.btn_pane_terminal.setToolTip("Terminal Console View")
        self.btn_pane_terminal.setFixedSize(24, 24)
        self.btn_pane_terminal.clicked.connect(lambda: self._switch_data_pane(1))

        d_header.addWidget(self.btn_pane_table)
        d_header.addWidget(self.btn_pane_terminal)
        v_layout.addLayout(d_header)

        # Ô tìm kiếm gói tin (background-30)
        self.edit_search = QtWidgets.QLineEdit()
        self.edit_search.setFixedHeight(28)
        self.edit_search.setPlaceholderText("Type to search")
        self.edit_search.setToolTip("Filter decoded packets")
        self.edit_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
                padding: 2px 8px;
                color: #ffffff;
                font-family: 'Roboto', sans-serif;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {T.HIGHLIGHT};
            }}
        """)
        self.edit_search.textChanged.connect(self._filter_packet_table)

        # Bảng dữ liệu gói tin 5 cột: [■ | Type | Start | Duration | Data]
        # Chiều cao hàng compact 22px
        self.table_uart_packets = QtWidgets.QTableWidget(0, 5)
        self.table_uart_packets.setHorizontalHeaderLabels(["", "Type", "Start", "Duration", "Data"])
        self.table_uart_packets.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.table_uart_packets.verticalHeader().setVisible(False)
        self.table_uart_packets.verticalHeader().setMinimumSectionSize(16)
        self.table_uart_packets.verticalHeader().setDefaultSectionSize(22)
        self.table_uart_packets.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.table_uart_packets.setAlternatingRowColors(True)
        self.table_uart_packets.setShowGrid(False)
        self.table_uart_packets.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_uart_packets.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_uart_packets.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table_uart_packets.setColumnWidth(0, 20)
        self.table_uart_packets.setColumnWidth(1, 44)
        self.table_uart_packets.setColumnWidth(2, 62)
        self.table_uart_packets.setColumnWidth(3, 62)
        self.table_uart_packets.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table_uart_packets.setStyleSheet(f"""
            QTableWidget {{
                background-color: {T.BG_DEEP};
                alternate-background-color: {T.BG_MAIN};
                gridline-color: transparent;
                border: 1px solid {T.BORDER};
                border-radius: 2px;
                color: #e0e0e0;
                font-family: 'Roboto Mono', 'DejaVu Sans Mono', monospace;
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {T.BG_MAIN};
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid {T.BORDER_MUTED};
                font-family: 'Roboto', sans-serif;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
        """)
        self.table_uart_packets.cellClicked.connect(self._on_table_row_clicked)
        self.table_uart_packets.itemSelectionChanged.connect(self._on_table_selection_changed)

        # Terminal hiển thị chuỗi ASCII (nền #141415, chữ #e0e0e0)
        self.txt_uart_decoded = QtWidgets.QTextEdit()
        self.txt_uart_decoded.setReadOnly(True)
        self.txt_uart_decoded.setStyleSheet(f"""
            QTextEdit {{
                background-color: {T.BG_DEEP};
                color: #e0e0e0;
                font-family: 'Roboto Mono', 'DejaVu Sans Mono', monospace;
                font-size: 11px;
                border: 1px solid {T.BORDER};
                border-radius: 4px;
                padding: 6px;
            }}
        """)

        # Stacked Widget chuyển đổi linh hoạt giữa Table View và Terminal View
        self.data_stack = QtWidgets.QStackedWidget()

        # Page 0: Table View
        page_table = QtWidgets.QWidget()
        l_table = QtWidgets.QVBoxLayout(page_table)
        l_table.setContentsMargins(0, 0, 0, 0)
        l_table.setSpacing(6)
        l_table.addWidget(self.edit_search)
        l_table.addWidget(self.table_uart_packets, 1)
        self.data_stack.addWidget(page_table)

        # Page 1: Terminal View (mở rộng tối đa chiều cao, không bị ép 75px)
        page_terminal = QtWidgets.QWidget()
        l_terminal = QtWidgets.QVBoxLayout(page_terminal)
        l_terminal.setContentsMargins(0, 0, 0, 0)
        l_terminal.setSpacing(6)
        l_terminal.addWidget(self.txt_uart_decoded, 1)
        self.data_stack.addWidget(page_terminal)

        v_layout.addWidget(self.data_stack, 1)
        self._update_data_pane_buttons()

        return panel

    # =========================================================================
    # DẢI ACTIVITY RAIL BÊN PHẢI (56 PX)
    # =========================================================================

    def _create_rail(self) -> QtWidgets.QWidget:
        rail = QtWidgets.QWidget(self)
        rail.setObjectName("activityRail")
        rail.setFixedWidth(T.RAIL_WIDTH)
        rail.setStyleSheet(f"""
            #activityRail {{
                background-color: {T.BG_SELECT};
                border-left: 1px solid {T.BORDER_MUTED};
            }}
        """)

        v_layout = QtWidgets.QVBoxLayout(rail)
        v_layout.setContentsMargins(0, 10, 0, 0)
        v_layout.setSpacing(4)

        # Nút START tròn màu xanh (#00994d, đường kính 48px) đặt tại đỉnh của Activity Rail
        self.btn_rail_start = QtWidgets.QPushButton("▶")
        self.btn_rail_start.setObjectName("startButton")
        self.btn_rail_start.setFixedSize(T.START_BUTTON_DIAMETER, T.START_BUTTON_DIAMETER)
        self.btn_rail_start.setToolTip("Start Capture (F5)")
        self.btn_rail_start.clicked.connect(self._on_start_or_abort)
        v_layout.addWidget(self.btn_rail_start, 0, QtCore.Qt.AlignHCenter)

        # Nút chuyển đổi nhanh Single Shot / Auto-Repeat 🔁
        self.btn_rail_mode = QtWidgets.QPushButton("1x")
        self.btn_rail_mode.setObjectName("railModeButton")
        self.btn_rail_mode.setToolTip("Capture Mode: Single Shot [1x] / Auto-Repeat [🔁] (F6)")
        self.btn_rail_mode.setFixedSize(36, 18)
        self.btn_rail_mode.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_rail_mode.clicked.connect(self._toggle_capture_mode)
        v_layout.addWidget(self.btn_rail_mode, 0, QtCore.Qt.AlignHCenter)

        v_layout.addSpacing(6)

        # Các nút switcher bọc trong RailSwitcherSlot (56x56px, vạch 2px #ffffff)
        self.btn_sw_analyzers = self._create_switcher_button(
            icon_text="{ }",
            tooltip="Analyzers (Alt+A)",
            callback=self._toggle_drawer_panel
        )
        self.slot_analyzers = RailSwitcherSlot(self.btn_sw_analyzers)
        v_layout.addWidget(self.slot_analyzers, 0, QtCore.Qt.AlignHCenter)

        self.btn_sw_trigger = self._create_switcher_button(
            icon_text="⚡",
            tooltip="Device Settings (Alt+D)",
            callback=self._toggle_trigger_card
        )
        self.slot_trigger = RailSwitcherSlot(self.btn_sw_trigger)
        v_layout.addWidget(self.slot_trigger, 0, QtCore.Qt.AlignHCenter)

        self.btn_sw_measurements = self._create_switcher_button(
            icon_text="f(t)",
            tooltip="Measurements (M)",
            callback=self._toggle_measurements_card
        )
        self.slot_measurements = RailSwitcherSlot(self.btn_sw_measurements)
        v_layout.addWidget(self.slot_measurements, 0, QtCore.Qt.AlignHCenter)

        self.btn_sw_cursors = self._create_switcher_button(
            icon_text="❙❙",
            tooltip="Timing Markers & Cursors (C)",
            callback=self._toggle_cursors
        )
        self.slot_cursors = RailSwitcherSlot(self.btn_sw_cursors)
        v_layout.addWidget(self.slot_cursors, 0, QtCore.Qt.AlignHCenter)

        self.btn_sw_export = self._create_switcher_button(
            icon_text="⤓",
            tooltip="Export Data (PNG, CSV, VCD)",
            callback=self._export_image
        )
        self.slot_export = RailSwitcherSlot(self.btn_sw_export)
        v_layout.addWidget(self.slot_export, 0, QtCore.Qt.AlignHCenter)

        v_layout.addStretch(1)

        # Nút Settings ⚙ đáy Activity Rail (.panelSwitcherBottomSection)
        self.btn_rail_settings = self._create_switcher_button(
            icon_text="⚙",
            tooltip="Preferences & Settings",
            callback=self._on_settings_clicked
        )
        self.slot_settings = RailSwitcherSlot(self.btn_rail_settings)
        v_layout.addWidget(self.slot_settings, 0, QtCore.Qt.AlignHCenter)
        v_layout.addSpacing(10)  # margin-bottom: var(--spacer-s) = 10px

        # Khởi tạo kiểu dáng selectedSwitcher cho switcher Analyzers
        self._update_switcher_styles()

        return rail

    def _create_switcher_button(self, icon_text: str, tooltip: str, callback) -> QtWidgets.QToolButton:
        btn = QtWidgets.QToolButton()
        btn.setText(icon_text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        btn.clicked.connect(callback)
        return btn

    def _toggle_cursors(self):
        """Bật/tắt cặp thước đo thời gian A & B và đồng bộ chỉ báo trạng thái trên Activity Rail."""
        self.waveform.toggle_cursors()
        self._update_switcher_styles()

    def _toggle_drawer_panel(self):
        """Bật/tắt Drawer Panel bên phải."""
        self.drawer_open = not getattr(self, "drawer_open", True)
        self.right_panel.setVisible(self.drawer_open)
        self._update_switcher_styles()

    def _update_switcher_styles(self):
        """Cập nhật trạng thái hiển thị của các nút switcher trên Activity Rail."""
        drawer_visible = getattr(self, "drawer_open", True)
        cursors_visible = False
        if hasattr(self, "waveform") and hasattr(self.waveform, "cursor_a"):
            cursors_visible = self.waveform.cursor_a.isVisible()

        trigger_active = drawer_visible and hasattr(self, "trigger_body") and self.trigger_body.isVisible()
        measurements_active = drawer_visible and hasattr(self, "card_measurements") and self.card_measurements.isVisible()
        analyzers_active = drawer_visible

        if hasattr(self, "btn_sw_analyzers"):
            self._apply_switcher_style(self.btn_sw_analyzers, selected=analyzers_active)
        if hasattr(self, "btn_sw_trigger"):
            self._apply_switcher_style(self.btn_sw_trigger, selected=trigger_active)
        if hasattr(self, "btn_sw_measurements"):
            self._apply_switcher_style(self.btn_sw_measurements, selected=measurements_active)
        if hasattr(self, "btn_sw_cursors"):
            self._apply_switcher_style(self.btn_sw_cursors, selected=cursors_visible)
        if hasattr(self, "btn_sw_export"):
            self._apply_switcher_style(self.btn_sw_export, selected=False)
        if hasattr(self, "btn_rail_settings"):
            self._apply_switcher_style(self.btn_rail_settings, selected=False)

    def _apply_switcher_style(self, btn: QtWidgets.QToolButton, selected: bool):
        if hasattr(btn, "slot") and btn.slot is not None:
            btn.slot.set_selected(selected)
        else:
            if selected:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {T.BG_CARD};
                        border: none;
                        border-radius: 18px;
                        color: #ffffff;
                        font-size: 16px;
                        font-weight: 500;
                        padding: 6px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 18px;
                        color: {T.TEXT_DIM};
                        font-size: 16px;
                        padding: 6px;
                    }}
                    QToolButton:hover {{
                        background-color: #424246;
                        color: #ffffff;
                    }}
                """)

    def _on_settings_clicked(self):
        """Mở hộp thoại Preferences & Settings."""
        QtWidgets.QMessageBox.information(
            self,
            "Preferences & Settings",
            "<h3>HUST Logic Analyzer - Preferences</h3>"
            "<p><b>Device:</b> STM32F401CCU6 WeAct Black Pill V3.0 (84 MHz)</p>"
            "<p><b>Sampling Engine:</b> TIM1 UP Event -> DMA2 Stream 5 (32 KB Buffer)</p>"
            "<p><b>Post-trigger:</b> TIM2 ITR0 Slave Mode One-Pulse (80% / 26,214 samples)</p>"
            "<p><b>Theme:</b> HUST Embedded Dark Theme (UI_SPEC.md SSoT)</p>"
        )

    def _switch_data_pane(self, index: int):
        """Chuyển đổi giữa Table View (0) và Terminal View (1)."""
        self.data_stack.setCurrentIndex(index)
        self._update_data_pane_buttons()

    def _update_data_pane_buttons(self):
        """Cập nhật trạng thái hiển thị của các nút chuyển pane Data Table / Terminal."""
        if not hasattr(self, "btn_pane_table") or not hasattr(self, "btn_pane_terminal"):
            return
        curr = self.data_stack.currentIndex()
        active_style = f"""
            QToolButton {{
                background-color: {T.BG_CARD};
                border: 1px solid {T.BORDER_MUTED};
                border-radius: 4px;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
            }}
        """
        inactive_style = f"""
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: {T.TEXT_DIM};
                font-size: 11px;
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {T.BG_SELECT};
                color: #ffffff;
            }}
        """
        self.btn_pane_table.setStyleSheet(active_style if curr == 0 else inactive_style)
        self.btn_pane_terminal.setStyleSheet(active_style if curr == 1 else inactive_style)

    def _on_start_or_abort(self):
        """Bấm nút tròn tại đỉnh Activity Rail: Start khi rảnh, Pause/Abort khi đang bắt tín hiệu."""
        if self.repeat_running:
            self._stop_repeat()
        elif self.worker is not None and self.worker.isRunning():
            self._on_abort()
        else:
            if self.repeat_mode:
                self._start_repeat()
            else:
                self._on_start_capture()

    def _toggle_capture_mode(self):
        """Chuyển đổi giữa chế độ Single Shot [1x] và Auto-Repeat Run [🔁]."""
        self.repeat_mode = not self.repeat_mode
        if not self.repeat_mode and self.repeat_running:
            self._stop_repeat()
        self._update_capture_mode_ui()

    def _on_capture_combo_changed(self, index: int):
        """Đồng bộ khi người dùng chọn chế độ từ combobox trong Device Settings."""
        data = self.combo_capture_mode.currentData()
        self.repeat_mode = (data == "repeat")
        if not self.repeat_mode and self.repeat_running:
            self._stop_repeat()
        self._update_capture_mode_ui()

    def _update_capture_mode_ui(self):
        """Cập nhật trạng thái hiển thị của các nút chế độ Capture."""
        is_repeat = getattr(self, "repeat_mode", False)
        if hasattr(self, "combo_capture_mode"):
            self.combo_capture_mode.blockSignals(True)
            self.combo_capture_mode.setCurrentIndex(1 if is_repeat else 0)
            self.combo_capture_mode.blockSignals(False)

        if hasattr(self, "btn_rail_mode"):
            if is_repeat:
                self.btn_rail_mode.setText("🔁")
                self.btn_rail_mode.setToolTip("Capture Mode: Auto-Repeat Run (Click to switch to Single Shot 1x) [F6]")
                self.btn_rail_mode.setStyleSheet("""
                    QPushButton#railModeButton {
                        background-color: #1b4d2e;
                        border: 1px solid #00994d;
                        border-radius: 9px;
                        color: #58c667;
                        font-size: 11px;
                        font-weight: bold;
                        padding: 0px;
                    }
                    QPushButton#railModeButton:hover {
                        background-color: #24633b;
                    }
                """)
            else:
                self.btn_rail_mode.setText("1x")
                self.btn_rail_mode.setToolTip("Capture Mode: Single Shot (Click to switch to Auto-Repeat 🔁) [F6]")
                self.btn_rail_mode.setStyleSheet("""
                    QPushButton#railModeButton {
                        background-color: #2c2c2e;
                        border: 1px solid #57575e;
                        border-radius: 9px;
                        color: #a0a0a6;
                        font-size: 11px;
                        font-weight: bold;
                        padding: 0px;
                    }
                    QPushButton#railModeButton:hover {
                        background-color: #3a3a3e;
                        color: #ffffff;
                    }
                """)

        if not getattr(self, "repeat_running", False) and (self.worker is None or not self.worker.isRunning()):
            self._set_capture_button_state(False)

    def _start_repeat(self):
        """Bắt đầu chu trình Auto-Repeat lấy mẫu liên tục."""
        self.repeat_running = True
        self.repeat_frame_count = 0
        self._set_capture_button_state(True)
        self.lbl_status.setText("⚡ Auto-Repeat: Starting continuous acquisition...")
        self._on_start_capture()

    def _stop_repeat(self):
        """Dừng chu trình Auto-Repeat và đóng băng khung hình hiện tại."""
        self.repeat_running = False
        if self.worker is not None and self.worker.isRunning():
            self._on_abort()
        else:
            self.client.disconnect()
            self._set_capture_button_state(False)
            self.lbl_status.setText(f"⏸ Auto-Repeat Paused: Frame #{self.repeat_frame_count} frozen for analysis")

    def _on_repeat_cycle_ready(self):
        """Kích hoạt chu kỳ tiếp theo trong vòng lặp Auto-Repeat."""
        if not getattr(self, "repeat_running", False):
            return
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(200)
            if self.worker.isRunning():
                QtCore.QTimer.singleShot(25, self._on_repeat_cycle_ready)
                return
        self._on_start_capture()

    def keyPressEvent(self, event):
        """Xử lý phím tắt Space (Play/Pause) và F6 (Toggle Single/Repeat)."""
        if event.key() == QtCore.Qt.Key_Space:
            self._on_start_or_abort()
            return
        elif event.key() == QtCore.Qt.Key_F6:
            self._toggle_capture_mode()
            return
        super().keyPressEvent(event)

    def _set_capture_button_state(self, capturing: bool):
        """Cập nhật nút Start tròn: Xanh Play khi rảnh, Đỏ Stop / Cam Pause khi đang capture."""
        if capturing:
            if getattr(self, "repeat_running", False):
                self.btn_rail_start.setText("⏸")
                self.btn_rail_start.setToolTip("Pause Auto-Repeat (Space / Escape / F5)")
            else:
                self.btn_rail_start.setText("⏹")
                self.btn_rail_start.setToolTip("Stop Capture (Escape)")
            self.btn_rail_start.setStyleSheet(f"""
                QPushButton#startButton {{
                    background-color: {T.ACCENT_STOP};
                    border: none;
                    border-radius: 24px;
                    min-width: 48px;
                    min-height: 48px;
                    max-width: 48px;
                    max-height: 48px;
                    padding: 0px;
                    color: #ffffff;
                    font-size: 16px;
                }}
                QPushButton#startButton:hover {{
                    background-color: #e5533f;
                }}
            """)
        else:
            self.btn_rail_start.setText("▶")
            if getattr(self, "repeat_mode", False):
                self.btn_rail_start.setToolTip("Start Auto-Repeat Run (F5 / Space)")
            else:
                self.btn_rail_start.setToolTip("Start Capture (F5 / Space)")
            self.btn_rail_start.setStyleSheet(f"""
                QPushButton#startButton {{
                    background-color: {T.ACCENT_START};
                    border: none;
                    border-radius: 24px;
                    min-width: 48px;
                    min-height: 48px;
                    max-width: 48px;
                    max-height: 48px;
                    padding: 0px;
                    color: #ffffff;
                    font-size: 18px;
                    font-weight: bold;
                }}
                QPushButton#startButton:hover {{
                    background-color: {T.ACCENT_START_HOVER};
                }}
                QPushButton#startButton:pressed {{
                    background-color: {T.ACCENT_START_PRESSED};
                }}
            """)

    # =========================================================================
    # THANH ĐÁY (36 PX)
    # =========================================================================

    def _create_bottom_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget(self)
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(T.BOTTOM_BAR_HEIGHT)
        bar.setStyleSheet(f"#bottomBar {{ background-color: {T.BG_MAIN}; border-top: 1px solid {T.BORDER_MUTED}; }}")

        h_layout = QtWidgets.QHBoxLayout(bar)
        h_layout.setContentsMargins(10, 0, 14, 0)
        h_layout.setSpacing(12)

        # Tab Session bên trái có nút ✕ đóng tab và nút + tạo mới
        self.tab_sessions = QtWidgets.QTabBar()
        self.tab_sessions.setExpanding(False)
        self.tab_sessions.setTabsClosable(True)
        self.tab_sessions.addTab("Session 0")
        self.tab_sessions.setTabData(0, 0)
        self.tab_sessions.setCurrentIndex(0)
        self.tab_sessions.tabCloseRequested.connect(self._on_close_session_tab)
        self.tab_sessions.currentChanged.connect(self._on_session_tab_changed)
        h_layout.addWidget(self.tab_sessions)

        self.btn_new_session = QtWidgets.QToolButton()
        self.btn_new_session.setObjectName("newSessionButton")
        self.btn_new_session.setText("+")
        self.btn_new_session.setToolTip("Add new capture session (Ctrl+N)")
        self.btn_new_session.setFixedSize(22, 22)
        self.btn_new_session.clicked.connect(self._on_add_session_tab)
        h_layout.addWidget(self.btn_new_session)

        # Trạng thái kết nối ở giữa
        self.lbl_status = QtWidgets.QLabel("Ready | Offline Mock available")
        self.lbl_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-family: 'Roboto', sans-serif; font-size: 12px;")
        h_layout.addWidget(self.lbl_status)

        h_layout.addStretch(1)

        # Mức thu phóng ở góc phải (@mixin dataRegular: 'Roboto Mono', 11px)
        self.lbl_zoom = QtWidgets.QLabel("128 µs ⌃")
        self.lbl_zoom.setStyleSheet(f"color: {T.TEXT_DIM}; font-family: 'Roboto Mono', 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 500;")
        h_layout.addWidget(self.lbl_zoom)

        return bar

    def _on_x_range_changed(self, x_min: float, x_max: float):
        """Cập nhật chỉ số Zoom ở thanh Footer khi khung nhìn thay đổi."""
        span = abs(x_max - x_min)
        self.lbl_zoom.setText(f"{format_si_time(span)} ⌃")

    def _on_add_session_tab(self):
        """Thêm session tab mới."""
        sess_id = getattr(self, "_next_session_id", self.tab_sessions.count())
        self._next_session_id = sess_id + 1
        idx = self.tab_sessions.addTab(f"Session {sess_id}")
        self.tab_sessions.setTabData(idx, sess_id)
        self.tab_sessions.setCurrentIndex(idx)
        self.lbl_status.setText(f"Session {sess_id}: Ready for capture")

    def _on_close_session_tab(self, index: int):
        """Đóng session tab (giữ tối thiểu 1 session)."""
        if self.tab_sessions.count() > 1:
            sess_id = self.tab_sessions.tabData(index)
            name = self.tab_sessions.tabText(index)
            if hasattr(self, "sessions") and sess_id in self.sessions:
                del self.sessions[sess_id]
            self.tab_sessions.removeTab(index)
            self.lbl_status.setText(f"Closed {name}")

    def _on_session_tab_changed(self, index: int):
        """Chuyển đổi session tab và cập nhật dạng sóng tương ứng."""
        if index < 0:
            return
        sess_id = self.tab_sessions.tabData(index)
        if sess_id is None:
            sess_id = index
        if hasattr(self, "sessions") and sess_id in self.sessions:
            data = self.sessions[sess_id]
            self.current_data = data
            self.waveform.render_data(data)
            self._redecode_current_analyzer()
            self.lbl_status.setText(f"Viewing {self.tab_sessions.tabText(index)}: Ready")
        else:
            self.current_data = None
            self.waveform.clear_data()
            if hasattr(self, "txt_uart_decoded"):
                self.txt_uart_decoded.clear()
            if hasattr(self, "table_uart_packets"):
                self.table_uart_packets.setRowCount(0)
            self.lbl_status.setText(f"{self.tab_sessions.tabText(index)}: Ready for capture")

    # =========================================================================
    # CÁC HÀNH ĐỘNG ĐIỀU KHIỂN & SỰ KIỆN
    # =========================================================================

    def _toggle_trigger_card(self):
        """Ẩn/hiện nội dung Card Device Settings và đồng bộ Activity Rail."""
        if not self.right_panel.isVisible():
            self.drawer_open = True
            self.right_panel.setVisible(True)
            self.trigger_body.setVisible(True)
        else:
            visible = not self.trigger_body.isVisible()
            self.trigger_body.setVisible(visible)
        
        vis = self.trigger_body.isVisible()
        self.lbl_card_title.setText("› Device Settings" if vis else "› Device Settings (Collapsed)")
        self._update_switcher_styles()

    def _get_available_ports(self) -> List[Tuple[str, str, bool]]:
        """
        Lọc thông minh các cổng serial:
        - Ưu tiên nhận diện kit STM32 Logic Analyzer (VID=0x0483, PID=0x5740 hoặc mô tả 'STM32')
        - Giữ lại các cổng USB Serial thực tế (/dev/ttyACM*, /dev/ttyUSB*, COM*)
        - Loại bỏ 32 cổng ttyS* rác trên Linux bo mạch chủ
        - Đính kèm Offline Mock ở cuối
        :return: Danh sách (port_device, display_label, is_stm32)
        """
        import serial.tools.list_ports
        all_ports = serial.tools.list_ports.comports()
        stm32_ports = []
        other_ports = []

        for p in all_ports:
            # Bỏ qua các cổng ttyS rác trên Linux không gắn thiết bị
            if p.device.startswith("/dev/ttyS") and (p.vid is None and p.hwid == "n/a"):
                continue

            desc = p.description or ""
            mfg = p.manufacturer or ""
            hwid = p.hwid or ""
            is_stm32 = False

            # Nhận diện phần cứng STM32 USB-CDC (VID:PID 0483:5740)
            if p.vid == 0x0483 and p.pid == 0x5740:
                is_stm32 = True
            elif "STM32" in desc.upper() or "STMICRO" in mfg.upper() or "0483:5740" in hwid:
                is_stm32 = True
            elif "ttyACM" in p.device:
                is_stm32 = True

            if is_stm32:
                label = f"⚡ [STM32] {p.device} ({desc})"
                stm32_ports.append((p.device, label, True))
            else:
                label = f"{p.device} ({desc})" if desc else p.device
                other_ports.append((p.device, label, False))

        result = stm32_ports + other_ports
        result.append(("OFFLINE_MOCK", "📁 Offline Mock (sample_data_1mhz.bin)", False))
        return result

    def _refresh_ports(self, auto_connect: bool = True):
        """Quét và làm mới danh sách cổng serial USB-CDC kèm bộ lọc thông minh."""
        ports = self._get_available_ports()
        current_selected = self.combo_ports.currentData()

        self.combo_ports.blockSignals(True)
        self.combo_ports.clear()

        stm32_port_to_select = None
        has_stm32 = False

        for p_dev, p_desc, is_stm32 in ports:
            self.combo_ports.addItem(p_desc, p_dev)
            if is_stm32 and stm32_port_to_select is None:
                stm32_port_to_select = p_dev
                has_stm32 = True

        # Khôi phục lựa chọn trước đó nếu vẫn còn, hoặc ưu tiên chọn cổng STM32
        if current_selected and any(p[0] == current_selected for p in ports):
            idx = self.combo_ports.findData(current_selected)
            if idx >= 0:
                self.combo_ports.setCurrentIndex(idx)
        elif stm32_port_to_select:
            idx = self.combo_ports.findData(stm32_port_to_select)
            if idx >= 0:
                self.combo_ports.setCurrentIndex(idx)
        self.combo_ports.blockSignals(False)

        # Cập nhật tập cổng hiện tại cho hotplug tracker
        self._last_known_ports = {p[0] for p in ports if p[0] != "OFFLINE_MOCK"}

        # Tự động kết nối & xác thực PING nếu tìm thấy STM32
        if auto_connect and stm32_port_to_select:
            self._try_auto_connect(stm32_port_to_select)
        elif not has_stm32:
            if getattr(self, "connected_port", None):
                self.connected_port = None
                self.lbl_status.setText("⚪ Disconnected: STM32 hardware unplugged")
                self.lbl_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px;")
            else:
                self.lbl_status.setText("⚪ Disconnected: No STM32 device found (Use 'Offline Mock' or connect USB)")
                self.lbl_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px;")

    def _try_auto_connect(self, port: str):
        """Tự động gửi lệnh PING bắt tay xác thực phần cứng Logic Analyzer."""
        if self.worker is not None and self.worker.isRunning():
            return

        # Tránh ping liên tục nếu cổng đã được kết nối và xác thực thành công
        if getattr(self, "connected_port", None) == port:
            return

        try:
            ok, msg = self.client.connect(port, timeout=0.5)
            if ok:
                ping_ok, ver = self.client.ping()
                self.client.disconnect()
                if ping_ok:
                    self.connected_port = port
                    self.lbl_status.setText(f"🟢 Connected: STM32F401 ({ver}) on {port} | Clock: 84 MHz")
                    self.lbl_status.setStyleSheet("color: #58c667; font-weight: 500; font-size: 12px;")
                    if hasattr(self, "chk_mock") and self.chk_mock.isChecked():
                        self.chk_mock.setChecked(False)
                    return True
                else:
                    self.lbl_status.setText(f"⚠ Found {port} but no PONG response ({ver})")
                    self.lbl_status.setStyleSheet(f"color: {T.ACCENT_WARN}; font-size: 12px;")
            else:
                self.lbl_status.setText(f"⚠ Cannot open port {port}: {msg}")
        except Exception as e:
            self.lbl_status.setText(f"⚠ Port scan error {port}: {e}")
        return False

    def _on_port_changed(self, index: int):
        """Xử lý khi người dùng đổi cổng trong combobox."""
        port = self.combo_ports.currentData()
        if port == "OFFLINE_MOCK":
            self.connected_port = None
            if hasattr(self, "chk_mock"):
                self.chk_mock.setChecked(True)
            self.lbl_status.setText("📁 Ready | Offline Mock Mode (sample_data_1mhz.bin)")
            self.lbl_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 12px;")
        elif port:
            if hasattr(self, "chk_mock"):
                self.chk_mock.setChecked(False)
            self._try_auto_connect(port)

    def _check_hotplug(self):
        """Kiểm tra thay đổi cắm/rút thiết bị USB ngầm (Hotplug Watchdog)."""
        if self.worker is not None and self.worker.isRunning():
            return  # Không can thiệp khi đang lấy mẫu tín hiệu

        import serial.tools.list_ports
        current_ports = {
            p.device for p in serial.tools.list_ports.comports()
            if not (p.device.startswith("/dev/ttyS") and p.vid is None and p.hwid == "n/a")
        }

        if not hasattr(self, "_last_known_ports"):
            self._last_known_ports = current_ports
            return

        if current_ports != self._last_known_ports:
            # Phát hiện cắm thêm hoặc rút thiết bị USB
            self._last_known_ports = current_ports
            self._refresh_ports(auto_connect=True)

    def _on_ping(self):
        """Gửi lệnh PING kiểm tra kết nối với kit STM32."""
        port = self.combo_ports.currentData() or self.combo_ports.currentText()
        if not port or "Không" in str(port) or "No" in str(port):
            QtWidgets.QMessageBox.warning(self, "Port Error", "Please connect STM32 hardware or select a valid port!")
            return

        ok, msg = self.client.connect(port)
        if not ok:
            QtWidgets.QMessageBox.critical(self, "Connection Error", f"Cannot open port {port}:\n{msg}")
            return

        ping_ok, ver = self.client.ping()
        self.client.disconnect()
        if ping_ok:
            self.connected_port = port
            self.lbl_status.setText(f"🟢 Connected: STM32F401 ({ver}) on {port} | Clock: 84 MHz")
            self.lbl_status.setStyleSheet("color: #58c667; font-weight: 500; font-size: 12px;")
            QtWidgets.QMessageBox.information(
                self, "Ping Successful",
                f"Firmware Version: {ver}\nConnection verified with STM32F401 hardware!"
            )
        else:
            QtWidgets.QMessageBox.warning(
                self, "Ping Failed",
                f"Did not receive expected PONG response:\n{ver}"
            )

    def closeEvent(self, event):
        """Dọn dẹp timer và worker khi đóng ứng dụng."""
        self.repeat_running = False
        if hasattr(self, "timer_hotplug") and self.timer_hotplug.isActive():
            self.timer_hotplug.stop()
        if self.worker is not None and self.worker.isRunning():
            self.worker.is_aborted = True
            try:
                self.client.abort()
            except Exception:
                pass
            self.worker.wait(1000)
            if self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait(500)
        if hasattr(self, "_old_workers"):
            for w in self._old_workers:
                if w.isRunning():
                    w.wait(500)
        event.accept()

    def _on_start_capture(self):
        """Khởi động tiến trình lấy mẫu dữ liệu."""
        use_mock = self.chk_mock.isChecked()
        port = self.combo_ports.currentData() or self.combo_ports.currentText()

        rate_idx = self.combo_rate.currentData()
        trig_ch = self.combo_ch.currentData()
        trig_mode = self.combo_mode.currentData()

        mode_names = {0: "Free-run", 1: "Rising Edge", 2: "Falling Edge"}
        mode_str = mode_names.get(trig_mode, "Edge")
        rate_name = self.combo_rate.currentText().split()[0]

        if use_mock or port == "OFFLINE_MOCK":
            self.client.connect("OFFLINE_MOCK")
            res = self.client.start_capture(rate_idx=rate_idx, trig_ch=trig_ch, trig_mode=trig_mode)
            self.client.disconnect()
            self._render_capture_data(res)
            if getattr(self, "repeat_running", False):
                self.repeat_frame_count += 1
                self.lbl_status.setText(f"⚡ Auto-Repeat (Mock): Frame #{self.repeat_frame_count} | Press Pause (⏸) to freeze")
                QtCore.QTimer.singleShot(40, self._on_repeat_cycle_ready)
            else:
                self.lbl_status.setText("Reading offline mock data (sample_data_1mhz.bin)...")
            return

        if not port or "Không" in str(port) or "No" in str(port):
            # Tự động chuyển sang Mock nếu chưa cắm kit
            if getattr(self, "repeat_running", False):
                self.chk_mock.setChecked(True)
                self._on_start_capture()
                return
            reply = QtWidgets.QMessageBox.question(
                self, "Hardware Not Detected",
                "No STM32 USB-CDC hardware found. Would you like to run in Offline Mock mode?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.chk_mock.setChecked(True)
                self._on_start_capture()
            return

        if not self.client.is_connected:
            ok, msg = self.client.connect(port)
            if not ok:
                if getattr(self, "repeat_running", False):
                    self.repeat_running = False
                    self._set_capture_button_state(False)
                    self.lbl_status.setText(f"⚠️ Auto-Repeat Connection Error: {msg}")
                else:
                    QtWidgets.QMessageBox.critical(self, "Connection Error", f"Cannot open port {port}:\n{msg}")
                return

        self._set_capture_button_state(True)
        self.btn_rail_start.setEnabled(True)
        if getattr(self, "repeat_running", False):
            self.lbl_status.setText(f"⚡ Auto-Repeat [Frame #{self.repeat_frame_count + 1}]: Waiting for trigger on CH{trig_ch} ({mode_str}) @ {rate_name}...")
        else:
            if trig_mode == 0:
                self.lbl_status.setText(f"⚡ Capturing: Free-run sampling @ {rate_name} on {port}...")
            else:
                self.lbl_status.setText(f"⚡ Capturing: Waiting for trigger on CH{trig_ch} ({mode_str}) @ {rate_name}...")

        # Dọn dẹp an toàn các worker cũ tránh Qt crash do garbage collection sớm
        if hasattr(self, "_old_workers"):
            self._old_workers = [w for w in self._old_workers if w.isRunning()]
        else:
            self._old_workers = []

        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.wait(500)
            self._old_workers.append(self.worker)

        self.worker = CaptureWorker(self.client, rate_idx, trig_ch, trig_mode)
        self.worker.capture_done.connect(self._on_capture_done)
        self.worker.capture_error.connect(self._on_capture_error)
        self.worker.start()

    def _on_capture_done(self, res: dict):
        self._render_capture_data(res)
        if getattr(self, "repeat_running", False):
            self.repeat_frame_count += 1
            rate_name = self.combo_rate.currentText().split()[0]
            status_name = res.get("status_name", "Triggered")
            self.lbl_status.setText(f"⚡ Auto-Repeat: Frame #{self.repeat_frame_count} ({status_name} @ {rate_name}) | Press Pause (⏸) to freeze")
            QtCore.QTimer.singleShot(25, self._on_repeat_cycle_ready)
        else:
            self.client.disconnect()
            self._set_capture_button_state(False)
            self.btn_rail_start.setEnabled(True)

    def _on_capture_error(self, err_msg: str):
        self.client.disconnect()
        if getattr(self, "repeat_running", False):
            self.repeat_running = False
            self._set_capture_button_state(False)
            self.btn_rail_start.setEnabled(True)
            self.lbl_status.setText(f"⚠️ Auto-Repeat Paused on Error: {err_msg}")
        else:
            self._set_capture_button_state(False)
            self.btn_rail_start.setEnabled(True)
            self.lbl_status.setText(f"Capture error: {err_msg}")
            QtWidgets.QMessageBox.critical(self, "Capture Error", err_msg)

    def _on_abort(self):
        """Gửi lệnh hủy thu thập dữ liệu an toàn không dùng QThread.terminate()."""
        was_repeat = getattr(self, "repeat_running", False)
        self.repeat_running = False
        self._set_capture_button_state(False)
        if self.worker and self.worker.isRunning():
            self.worker.is_aborted = True
            self.client.request_abort()
            if not self.worker.wait(1500):
                self.client.abort()
                self.worker.wait(500)
            self.btn_rail_start.setEnabled(True)
            self.client.disconnect()
            if was_repeat:
                self.lbl_status.setText(f"⏸ Auto-Repeat Paused: Frame #{self.repeat_frame_count} frozen")
            else:
                self.lbl_status.setText("Capture aborted by user")
        else:
            if was_repeat:
                self.lbl_status.setText(f"⏸ Auto-Repeat Paused: Frame #{self.repeat_frame_count} frozen")
            else:
                self.lbl_status.setText("No capture currently in progress")

    def _render_capture_data(self, res: dict):
        """Hiển thị kết quả thu thập dữ liệu và giải mã protocol."""
        self.current_data = res
        curr_idx = self.tab_sessions.currentIndex() if hasattr(self, "tab_sessions") else 0
        sess_id = self.tab_sessions.tabData(curr_idx) if hasattr(self, "tab_sessions") else curr_idx
        if sess_id is None:
            sess_id = curr_idx
        if hasattr(self, "sessions"):
            self.sessions[sess_id] = res
        self.waveform.render_data(res)

        fs = float(res.get("sample_rate", 1_000_000))
        status_name = res.get("status_name", "Triggered")
        elapsed = res.get("elapsed_s", 0.0)

        rate_str = f"{fs/1e6:.1f} MHz" if fs >= 1e6 else f"{fs/1e3:.0f} kHz"
        self.lbl_status.setText(f"Capture complete: 32,768 samples @ {rate_str} | {status_name} in {elapsed:.3f} s")

        # Tự động giải mã lại theo analyzer hiện hành mà người dùng đã chọn
        self._redecode_current_analyzer()

        # Tự động tính toán đo đạc thông số kỹ thuật (Automated Measurements)
        self._update_automated_measurements()

    def _redecode_current_analyzer(self):
        """Tự động giải mã lại theo analyzer hiện hành mà người dùng đã chọn."""
        analyzer = getattr(self, "current_analyzer", "uart")
        if analyzer == "i2c":
            self._decode_i2c()
        elif analyzer == "spi":
            self._decode_spi()
        else:
            self._decode_uart()

    def _populate_packet_table(self, rows: List[Dict[str, Any]], marker_color: str):
        """Điền dữ liệu 5 cột vào bảng Data Table."""
        self.table_uart_packets.setRowCount(0)
        self.table_uart_packets.setRowCount(len(rows))
        for r, row in enumerate(rows):
            it_m = QtWidgets.QTableWidgetItem("■")
            it_m.setForeground(QtGui.QBrush(QtGui.QColor(marker_color)))
            it_m.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_uart_packets.setItem(r, 0, it_m)

            it_type = QtWidgets.QTableWidgetItem(row["type"])
            it_type.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            if "tooltip" in row:
                it_type.setToolTip(row["tooltip"])
            it_type.setData(QtCore.Qt.UserRole, row["time_range"])
            self.table_uart_packets.setItem(r, 1, it_type)

            start_s = row["start_s"]
            start_str = f"{start_s * 1e6:.1f} µs" if abs(start_s) < 1e-3 else f"{start_s * 1e3:.2f} ms"
            it_start = QtWidgets.QTableWidgetItem(start_str)
            it_start.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_uart_packets.setItem(r, 2, it_start)

            dur_s = row["dur_s"]
            dur_str = f"{dur_s * 1e6:.2f} µs"
            it_dur = QtWidgets.QTableWidgetItem(dur_str)
            it_dur.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_uart_packets.setItem(r, 3, it_dur)

            it_data = QtWidgets.QTableWidgetItem(row["data"])
            it_data.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_uart_packets.setItem(r, 4, it_data)

    def _decode_uart(self):
        """Giải mã UART, điền bảng dữ liệu và vẽ bong bóng chú thích trực tiếp trên sóng."""
        if not self.current_data:
            return

        ch0_samples = self.current_data["channels"][0].tolist()
        fs = float(self.current_data.get("sample_rate", 1_000_000))
        trig_offset = int(self.current_data.get("trig_offset", 6554))
        status = int(self.current_data.get("status", 0))
        eff_offset = trig_offset if status == 0 else 0

        self.uart_decoder.sample_rate = fs
        self.uart_decoder.baudrate = 115200

        start_decode_idx = max(0, trig_offset - 50) if status == 0 else 0
        text, frames = self.uart_decoder.decode(ch0_samples, start_idx=start_decode_idx)
        self.current_uart_frames = frames
        self.txt_uart_decoded.setPlainText(text)

        rows = []
        for frame in frames:
            start_idx = frame.get("start_sample", frame.get("start_idx", 0))
            stop_idx = frame.get("stop_sample", frame.get("stop_idx", start_idx + 10))
            val = frame.get("byte_val", frame.get("val", 0))
            char = frame.get("char", "")
            data_str = f"'{char}' (0x{val:02X})" if (char and 32 <= ord(char[0]) <= 126) else f"0x{val:02X}"
            rows.append({
                "type": "data",
                "tooltip": f"Hex: 0x{val:02X} | ASCII: '{char}'",
                "start_s": (start_idx - eff_offset) / fs,
                "dur_s": (stop_idx - start_idx) / fs,
                "data": data_str,
                "time_range": (start_idx / fs, stop_idx / fs)
            })

        self._populate_packet_table(rows, T.DECODE_UART_BG)
        self.waveform.render_uart_decorations(frames, fs, eff_offset)

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

    def _on_table_selection_changed(self):
        """Khi điều hướng bằng bàn phím (mũi tên lên/xuống), tự động pan căn giữa gói tin."""
        rows = self.table_uart_packets.selectionModel().selectedRows()
        if rows:
            r = rows[0].row()
            self._on_table_row_clicked(r, 1)

    def _on_bubble_ctrl_clicked(self, frame_idx: int, frame_dict: Dict[str, Any]):
        """
        Điều hướng 2 chiều (Ctrl+Click to scroll to table row):
        Khi bấm Ctrl+Click vào một bubble trên đồ thị sóng, tự động bôi sáng (highlight)
        và cuộn bảng Data Table ở Drawer bên phải tới đúng dòng của gói tin đó.
        """
        if 0 <= frame_idx < self.table_uart_packets.rowCount():
            self.table_uart_packets.blockSignals(True)
            self.table_uart_packets.selectRow(frame_idx)
            self.table_uart_packets.blockSignals(False)
            item = self.table_uart_packets.item(frame_idx, 1)
            if item:
                self.table_uart_packets.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
            # Tự động mở Drawer Data Table nếu đang bị thu gọn
            if hasattr(self, "right_panel") and not self.right_panel.isVisible():
                self.right_panel.setVisible(True)

    def _update_automated_measurements(self):
        """Tính toán và cập nhật các chỉ số đo đạc tự động cho kênh đang chọn."""
        if not hasattr(self, "card_measurements"):
            return
        if not self.current_data or "channels" not in self.current_data:
            return
        ch = self.combo_meas_ch.currentIndex()
        if ch < 0 or ch >= len(self.current_data["channels"]):
            return

        samples = self.current_data["channels"][ch]
        fs = float(self.current_data.get("sample_rate", 1_000_000.0))

        raw = measure_channel_signal(samples, fs)
        fmt = format_measurement_results(raw)

        self.lbl_m_freq.setText(fmt["freq"])
        self.lbl_m_period.setText(fmt["period"])
        self.lbl_m_duty.setText(fmt["duty"])
        self.lbl_m_thigh.setText(fmt["thigh"])
        self.lbl_m_tlow.setText(fmt["tlow"])
        self.lbl_m_trans.setText(fmt["transitions"])
        self.lbl_m_pulse.setText(fmt["min_pulse"])

        # Đổi màu tiêu đề theo màu kênh
        ch_color = T.CHANNEL_COLORS[ch]
        self.lbl_meas_title.setText(f"<span style='color:{ch_color}'>■</span> &nbsp;Measurements (D{ch})")

    def _on_meas_autodetect(self):
        """Tự động tìm và chọn kênh có nhiều xung chuyển mức nhất."""
        if not self.current_data or "channels" not in self.current_data:
            return
        best_ch = find_most_active_channel(self.current_data["channels"])
        self.combo_meas_ch.setCurrentIndex(best_ch)
        self._update_automated_measurements()

    def _toggle_measurements_card(self):
        """Ẩn/hiện thẻ Card Measurements trong Drawer Panel."""
        if hasattr(self, "card_measurements"):
            vis = not self.card_measurements.isVisible()
            self.card_measurements.setVisible(vis)
            if vis and hasattr(self, "right_panel") and not self.right_panel.isVisible():
                self.drawer_open = True
                self.right_panel.setVisible(True)
            if vis:
                self._update_automated_measurements()
        self._update_switcher_styles()

    def _show_measurements_for_channel(self, ch: int):
        """Mở thẻ đo đạc và chọn kênh chỉ định (từ context menu trên waveform)."""
        if 0 <= ch < 8:
            self.combo_meas_ch.setCurrentIndex(ch)
            if hasattr(self, "card_measurements"):
                self.card_measurements.setVisible(True)
            if hasattr(self, "right_panel") and not self.right_panel.isVisible():
                self.drawer_open = True
                self.right_panel.setVisible(True)
            self._update_automated_measurements()
            self._update_switcher_styles()

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
        """Mở popover menu chọn nhanh Analyzer."""
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
        act_uart = menu.addAction("■ Async Serial (UART)")
        act_i2c = menu.addAction("■ I2C")
        act_spi = menu.addAction("■ SPI")
        menu.addSeparator()
        act_more = menu.addAction("Show All Analyzers...")

        pos = self.btn_add_ana.mapToGlobal(QtCore.QPoint(0, self.btn_add_ana.height() + 2))
        chosen = menu.exec_(pos)

        if chosen == act_uart:
            self.current_analyzer = "uart"
            self.lbl_ana_item.setText(
                f"<span style='color:{T.DECODE_UART_BG};font-size:10px;'>■</span> &nbsp;Async Serial &nbsp;"
                f"<span style='color:{T.ACCENT_START}'>✔</span>"
            )
            self.waveform.set_analyzer_channel(0, "Async Serial", T.DECODE_UART_BG)
            self._decode_uart()
        elif chosen == act_i2c:
            self.current_analyzer = "i2c"
            self.lbl_ana_item.setText(
                f"<span style='color:{T.DECODE_I2C_BG};font-size:10px;'>■</span> &nbsp;I2C &nbsp;"
                f"<span style='color:{T.ACCENT_START}'>✔</span>"
            )
            self.waveform.set_analyzer_channel(2, "I2C - SDA", T.DECODE_I2C_BG)
            self._decode_i2c()
        elif chosen == act_spi:
            self.current_analyzer = "spi"
            self.lbl_ana_item.setText(
                f"<span style='color:#53a9fd;font-size:10px;'>■</span> &nbsp;SPI &nbsp;"
                f"<span style='color:{T.ACCENT_START}'>✔</span>"
            )
            self.waveform.set_analyzer_channel(4, "SPI - MOSI", "#53a9fd")
            self._decode_spi()
        elif chosen == act_more:
            QtWidgets.QMessageBox.information(
                self, "Protocol Analyzers",
                "<h3>Built-in Protocol Analyzers</h3>"
                "<p>Tích hợp sẵn: <b>Async Serial (UART)</b>, <b>I2C</b>, <b>SPI</b>.</p>"
                "<p>Hỗ trợ giải mã đồng bộ trực tiếp lên sóng và bảng dữ liệu Data Table.</p>"
            )

    def _decode_i2c(self):
        """Giải mã I2C trên CH1 (SCL) và CH2 (SDA), điền dữ liệu bảng Data Table."""
        if not self.current_data or "channels" not in self.current_data:
            return
        channels = self.current_data["channels"]
        if len(channels) < 3:
            return
        scl = channels[1].tolist()
        sda = channels[2].tolist()
        fs = float(self.current_data.get("sample_rate", 1_000_000))
        trig_offset = int(self.current_data.get("trig_offset", 6554))
        status = int(self.current_data.get("status", 0))
        eff_offset = trig_offset if status == 0 else 0
        self.i2c_decoder.sample_rate = fs
        text, frames = self.i2c_decoder.decode(scl, sda)
        self.txt_uart_decoded.setPlainText(text)

        rows = []
        for f in frames:
            f_type = f.get("type", "i2c")
            s_idx = f.get("start_sample", 0)
            e_idx = f.get("stop_sample", s_idx + 10)
            val = f.get("val")
            desc = f.get("desc")
            if desc:
                val_str = desc
            elif f_type.upper() in ("START", "REPEATED_START", "STOP"):
                val_str = f_type.upper()
            elif val is not None:
                val_str = f"0x{val:02X}"
            else:
                val_str = f_type

            rows.append({
                "type": f_type,
                "start_s": (s_idx - eff_offset) / fs,
                "dur_s": (e_idx - s_idx) / fs,
                "data": val_str,
                "time_range": (s_idx / fs, e_idx / fs)
            })

        self._populate_packet_table(rows, T.DECODE_I2C_BG)
        self.waveform.render_i2c_decorations(frames, fs, eff_offset)

    def _decode_spi(self):
        """Giải mã SPI trên CH3 (SCK), CH4 (MOSI), CH5 (MISO), CH6 (CS)."""
        if not self.current_data or "channels" not in self.current_data:
            return
        channels = self.current_data["channels"]
        if len(channels) < 7:
            return
        sck = channels[3].tolist()
        mosi = channels[4].tolist()
        miso = channels[5].tolist()
        cs = channels[6].tolist()
        fs = float(self.current_data.get("sample_rate", 1_000_000))
        trig_offset = int(self.current_data.get("trig_offset", 6554))
        status = int(self.current_data.get("status", 0))
        eff_offset = trig_offset if status == 0 else 0
        self.spi_decoder.sample_rate = fs
        text, frames = self.spi_decoder.decode(sck, mosi, miso, cs)
        self.txt_uart_decoded.setPlainText(text)

        rows = []
        for f in frames:
            s_idx = f.get("start_sample", 0)
            e_idx = f.get("stop_sample", s_idx + 10)
            mv = f.get("mosi_val", 0)
            sv = f.get("miso_val", 0)
            rows.append({
                "type": "spi",
                "start_s": (s_idx - eff_offset) / fs,
                "dur_s": (e_idx - s_idx) / fs,
                "data": f"MOSI:0x{mv:02X} MISO:0x{sv:02X}",
                "time_range": (s_idx / fs, e_idx / fs)
            })

        self._populate_packet_table(rows, "#53a9fd")
        self.waveform.render_spi_decorations(frames, fs, eff_offset)

    def _load_bin_file(self, filepath: str):
        """Đọc và vẽ file dữ liệu nhị phân 32.776B (.bin) theo đúng protocol.md thông qua LogicAnalyzerClient."""
        res = self.client.load_offline_file(filepath)
        if not res.get("success", False):
            QtWidgets.QMessageBox.warning(
                self, "Capture File Error",
                res.get("error", f"Cannot load capture file:\n{filepath}")
            )
            return

        rate_idx = self.combo_rate.currentIndex() if hasattr(self, "combo_rate") else 3
        if not (0 <= rate_idx < len(LogicAnalyzerClient.RATE_TABLE)):
            rate_idx = 3
        res["rate_idx"] = rate_idx
        res["sample_rate"] = float(LogicAnalyzerClient.RATE_TABLE[rate_idx]["freq"])
        self._render_capture_data(res)

    def _open_capture_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Raw Capture File", "", "Binary Capture (*.bin);;All Files (*)"
        )
        if path:
            self._load_bin_file(path)

    def _export_image(self):
        if not self.current_data:
            QtWidgets.QMessageBox.warning(self, "No Data", "No capture data available to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Waveform Image", "waveform.png", "PNG Image (*.png);;SVG Image (*.svg)"
        )
        if path:
            ok = export_image(self.waveform.plot_widget, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Successful", f"Waveform image exported to:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Failed", "Failed to export waveform image.")

    def _export_csv(self):
        if not self.current_data:
            QtWidgets.QMessageBox.warning(self, "No Data", "No capture data available to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export CSV Data", "capture_data.csv", "CSV Spreadsheet (*.csv)"
        )
        if path:
            ok = export_csv(self.current_data, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Successful", f"CSV data exported to:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Failed", "Failed to export CSV file.")

    def _export_vcd(self):
        if not self.current_data:
            QtWidgets.QMessageBox.warning(self, "No Data", "No capture data available to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export VCD File", "capture.vcd", "Value Change Dump (*.vcd)"
        )
        if path:
            ok = export_vcd(self.current_data, path)
            if ok:
                QtWidgets.QMessageBox.information(self, "Export Successful", f"GTKWave VCD file exported to:\n{path}")
            else:
                QtWidgets.QMessageBox.critical(self, "Export Failed", "Failed to export VCD file.")
