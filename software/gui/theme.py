"""software/gui/theme.py
Bảng màu + stylesheet + cấu hình pyqtgraph cho GUI Logic Analyzer.

Phong cách: nền tối, kênh xếp chồng, màu riêng cho từng kênh (lấy cảm hứng từ
giao diện phần mềm phân tích logic phổ biến). Màu đo từ ảnh tham chiếu;
CH6, CH7 là màu chọn thêm. Chỉ sửa màu ở đây, không rải màu trong code khác.
(Quy chuẩn SSoT: docs/UI_SPEC.md)
"""

from typing import List
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

# --- Màu nền / chữ ---------------------------------------------------------
BG_MAIN = "#1b1b1c"      # nền chính
BG_DEEP = "#141415"      # nền hàng bảng, vùng sâu
BG_CARD = "#2c2c2e"      # thẻ, ô nhập
BG_SELECT = "#3a3a3e"    # mục đang chọn
BORDER = "#3f3f43"
TEXT = "#ffffff"
TEXT_DIM = "#a0a0a6"
ACCENT_START = "#2e9949"  # nút Start
ACCENT_ERROR = "#d96c6d"
ACCENT_WARN = "#f9b353"
GRID = "#57575e"

# --- Màu 8 kênh (CH0..CH7) ---------------------------------------------------
CHANNEL_COLORS = [
    "#d4d4d4",  # CH0
    "#c39577",  # CH1
    "#f66c7e",  # CH2
    "#f9b353",  # CH3
    "#e6d71a",  # CH4
    "#67c662",  # CH5
    "#4fc3e8",  # CH6 (chọn thêm)
    "#b48ead",  # CH7 (chọn thêm)
]

# --- Màu chú thích giải mã / marker ----------------------------------------
DECODE_UART_BG = "#d3ccb0"   # ô ký tự UART (nền sáng, chữ tối)
DECODE_UART_FG = "#1b1b1c"
TRIGGER_MARKER = "#f9b353"   # vạch dọc tại mẫu trigger
CURSOR_A = "#4fc3e8"
CURSOR_B = "#f66c7e"

# --- Kích thước (px logic, ứng với màn hình 1280 rộng; v2 sau khi đánh giá) ---
CHANNEL_ROW_HEIGHT = 47      # px, hàng kênh số (có thể giãn để lấp đầy vùng sóng)
DECODER_ROW_SCALE = 1.45     # hàng có analyzer cao hơn 1.45 lần
LABEL_COLUMN_WIDTH = 194     # px, cột nhãn bên trái
RIGHT_PANEL_WIDTH = 313      # px, panel Analyzers/Data
RAIL_WIDTH = 65              # px, dải icon bên phải (nút Start ở trên cùng)
AXIS_HEIGHT = 32             # px, thước thời gian
BOTTOM_BAR_HEIGHT = 42       # px, thanh tab Session + mức zoom
START_BUTTON_DIAMETER = 50   # px
FONT_FAMILY = "Segoe UI"     # có thể đổi sang Inter

# --- Stylesheet QSS toàn cục ------------------------------------------------
QSS = f"""
QWidget {{ background-color: {BG_MAIN}; color: {TEXT};
          font-family: "{FONT_FAMILY}", "Inter", sans-serif; font-size: 13px; }}
QMenuBar, QMenu {{ background-color: {BG_MAIN}; color: {TEXT}; }}
QMenu::item:selected, QMenuBar::item:selected {{ background-color: {BG_SELECT}; }}
QLineEdit, QComboBox, QSpinBox {{ background-color: {BG_CARD};
          border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 8px; color: {TEXT}; }}
QPushButton {{ background-color: {BG_CARD}; border: 1px solid {BORDER};
          border-radius: 4px; padding: 6px 12px; color: {TEXT}; }}
QPushButton:hover {{ background-color: {BG_SELECT}; }}
QPushButton#startButton {{ background-color: {ACCENT_START}; border: none;
          border-radius: 25px; min-width: 50px; min-height: 50px;
          max-width: 50px; max-height: 50px; padding: 0px; }}
QPushButton#startButton:hover {{ background-color: #38b457; }}
QTableView, QTableWidget {{ background-color: {BG_DEEP}; gridline-color: {BORDER};
          alternate-background-color: {BG_MAIN}; color: {TEXT}; border: 1px solid {BORDER}; }}
QHeaderView::section {{ background-color: {BG_MAIN}; color: {TEXT};
          border: none; padding: 6px; font-weight: bold; }}
QTabBar::tab {{ background: {BG_MAIN}; color: {TEXT_DIM}; padding: 8px 16px; border: none; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {TEXT}; font-weight: bold; }}
QStatusBar {{ background-color: {BG_MAIN}; color: {TEXT_DIM}; border-top: 1px solid {BORDER}; }}
"""


def apply_theme(app: QtWidgets.QApplication):
    """Gọi một lần sau khi tạo QApplication."""
    app.setStyleSheet(QSS)


def configure_pyqtgraph(plot_widget: pg.PlotWidget = None):
    """Cấu hình toàn cục hoặc cho PlotWidget pyqtgraph."""
    pg.setConfigOptions(antialias=False, background=BG_MAIN, foreground=TEXT)
    if plot_widget is not None:
        plot_widget.setBackground(BG_MAIN)
        plot_item = plot_widget.getPlotItem()
        for axis_name in ("left", "bottom", "top", "right"):
            axis = plot_item.getAxis(axis_name)
            if axis:
                axis.setPen(pg.mkPen(color=GRID, width=1))
                axis.setTextPen(pg.mkPen(color=TEXT_DIM))


# =============================================================================
# CÁC ALIAS TƯƠNG THÍCH NGƯỢC (BACKWARD COMPATIBILITY)
# =============================================================================
COLOR_BG_MAIN = BG_MAIN
COLOR_BG_DEEP = BG_DEEP
COLOR_CARD = BG_CARD
COLOR_SELECT = BG_SELECT
COLOR_BORDER = BORDER
COLOR_TEXT = TEXT
COLOR_TEXT_DIM = TEXT_DIM
COLOR_ACCENT_START = ACCENT_START
COLOR_TRIGGER_MARKER = TRIGGER_MARKER
COLOR_GRID = GRID

SALEAE_CHANNEL_COLORS = CHANNEL_COLORS
NEON_CHANNEL_COLORS = CHANNEL_COLORS
DEFAULT_CHANNEL_NAMES = [f"Channel {i}" for i in range(8)]
DARK_THEME_QSS = QSS
setup_pyqtgraph_theme = configure_pyqtgraph
