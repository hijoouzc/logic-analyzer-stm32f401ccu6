"""software/gui/theme.py
Bảng màu + stylesheet + cấu hình pyqtgraph cho GUI Logic Analyzer.

Nguồn chân lý duy nhất (SSoT) về bảng màu và thiết kế giao diện:
- docs/UI_SPEC.md
"""

import os
from typing import List
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

# --- Đường dẫn tài nguyên UI (SVG assets) -----------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
CHECKMARK_SVG = os.path.join(ASSETS_DIR, "checkmark.svg").replace("\\", "/")
CLOSE_TAB_SVG = os.path.join(ASSETS_DIR, "close_tab.svg").replace("\\", "/")
CLOSE_TAB_HOVER_SVG = os.path.join(ASSETS_DIR, "close_tab_hover.svg").replace("\\", "/")

# --- Màu nền / chữ chuẩn Dark Theme (SSoT) ----------------------------------
BG_MAIN = "#1b1b1c"       # Nền khung chính, activity rail, session footer
BG_CANVAS = "#1b1b1c"     # Nền vùng vẽ sóng (đồng bộ liền mạch với khung chính)
BG_HEADER = "#0f0f10"     # Nền đen sâu của Thước thời gian Timeline (32px)
BG_DEEP = "#141415"       # Nền hàng bảng Data Table và Terminal
BG_CARD = "#2c2c2e"       # Thẻ, ô nhập, dropdowns
BG_CARD_SUBTLE = "#212224"# Nền phụ cho Drawer Panel
BG_SELECT = "#3a3a3e"     # Mục đang chọn / hover
BORDER = "#303136"        # Đường viền phân cách track tín hiệu
BORDER_MUTED = "#57575e"  # Đường viền thứ cấp / vạch phân cách track mỏng
TEXT = "#ffffff"          # Chữ chính high emphasis
TEXT_DIM = "#909091"      # Chữ chú thích medium emphasis
TEXT_MUTED = "#5c5c5d"    # Chữ mờ low emphasis
ACCENT_START = "#00994d"  # Nút tròn Start / Capture
ACCENT_START_HOVER = "#00b140" # Hover nút Start
ACCENT_START_PRESSED = "#02992f" # Active nút Start
ACCENT_ERROR = "#f52a66"  # Báo lỗi
ACCENT_STOP = "#db4c39"   # Nút dừng / hủy
ACCENT_WARN = "#fbd86f"   # Cảnh báo
HIGHLIGHT = "#26a3d9"     # Điểm nhấn đang chọn
GRID = "#303136"          # Lưới tọa độ pyqtgraph
GRID_DASH = "#49494d"     # Vạch lưới dọc nét đứt
TOOLTIP_BG = "#343438"    # Nền Tooltip / Floating HUD

# --- Bảng 8 màu kênh chuẩn mã màu điện trở (CH0..CH7) -----------------------
CHANNEL_COLORS = [
    "#d4d4d4",  # CH0: Silver White
    "#c79579",  # CH1: Warm Copper
    "#ff6d7f",  # CH2: Coral / Salmon Red
    "#ffb45b",  # CH3: Amber Orange
    "#e8d836",  # CH4: Lemon Yellow
    "#58c667",  # CH5: Fresh Green
    "#53a9fd",  # CH6: Sky Blue
    "#af92fb",  # CH7: Lavender Purple
]

# --- Màu chú thích giải mã / marker ----------------------------------------
DECODE_UART_BG = "#d3ccb0"   # Thẻ giải mã UART (nền sáng, chữ tối)
DECODE_UART_FG = "#1b1b1c"
DECODE_I2C_BG = "#4060c0"    # Thẻ giải mã I2C (nền xanh tím, chữ sáng)
DECODE_I2C_FG = "#ffffff"
TRIGGER_LINE = "#fff06a"     # Vạch dọc tại mẫu trigger
TRIGGER_MARKER = "#f1994b"   # Cờ / mũi tên trigger
CURSOR_A = "#26a3d9"
CURSOR_B = "#ea5757"

# --- Kích thước (px logic, chuẩn UI_SPEC.md) --------------------------------
CHANNEL_ROW_HEIGHT = 48      # Chiều cao tối thiểu 1 hàng kênh
DECODER_ROW_SCALE = 1.35     # Hàng có analyzer cao hơn 1.35 lần
LABEL_COLUMN_WIDTH = 180     # Cột nhãn kênh bên trái
RIGHT_PANEL_WIDTH = 310      # Drawer panel Analyzers / Data Table
RAIL_WIDTH = 56              # Dải Activity Rail bên phải
AXIS_HEIGHT = 32             # Thước thời gian Timeline
BOTTOM_BAR_HEIGHT = 36       # Thanh tab Session + mức zoom
START_BUTTON_DIAMETER = 48   # Nút Start tròn
FONT_FAMILY = "Roboto"       # Phông chữ chuẩn giao diện

# --- Stylesheet QSS toàn cục ------------------------------------------------
QSS = f"""
QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT};
    font-family: "{FONT_FAMILY}", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMenuBar, QMenu {{
    background-color: {BG_MAIN};
    color: {TEXT};
    border-bottom: 1px solid {BORDER_MUTED};
}}
QMenu::item:selected, QMenuBar::item:selected {{
    background-color: {BG_SELECT};
}}
QLineEdit, QComboBox, QSpinBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_MUTED};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {HIGHLIGHT};
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER_MUTED};
    selection-background-color: {BG_SELECT};
    selection-color: #ffffff;
    outline: none;
    padding: 2px;
}}
QToolTip {{
    background-color: {TOOLTIP_BG};
    color: {TEXT};
    border: 1px solid {BORDER_MUTED};
    border-radius: 4px;
    padding: 4px 8px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 11px;
}}
QDialog, QMessageBox, QInputDialog, QFileDialog {{
    background-color: {BG_MAIN};
    color: {TEXT};
}}
QMessageBox QLabel, QInputDialog QLabel {{
    background-color: transparent;
    color: {TEXT};
    border: none;
}}
QTableCornerButton::section {{
    background-color: {BG_MAIN};
    border: none;
    border-bottom: 1px solid {BORDER_MUTED};
}}
QCheckBox {{
    spacing: 6px;
    color: {TEXT_DIM};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 11px;
}}
QCheckBox:hover {{
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER_MUTED};
    border-radius: 2px;
    background-color: {BG_CARD};
}}
QCheckBox::indicator:hover {{
    border: 1px solid {TEXT_DIM};
    background-color: {BG_SELECT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_START};
    border: 1px solid {ACCENT_START};
    image: url({CHECKMARK_SVG});
}}
QPushButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_MUTED};
    border-radius: 4px;
    padding: 6px 12px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: {BG_SELECT};
}}
QPushButton#startButton {{
    background-color: {ACCENT_START};
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
    background-color: {ACCENT_START_HOVER};
}}
QPushButton#startButton:pressed {{
    background-color: {ACCENT_START_PRESSED};
}}
QToolButton.circularButton {{
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 6px;
    background-color: transparent;
    border: none;
    color: {TEXT_DIM};
}}
QToolButton.circularButton:hover {{
    background-color: {BG_SELECT};
    color: {TEXT};
}}
QTableView, QTableWidget {{
    background-color: {BG_DEEP};
    gridline-color: transparent;
    alternate-background-color: {BG_MAIN};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {BG_SELECT};
    selection-color: {TEXT};
    font-family: "Roboto Mono", "DejaVu Sans Mono", monospace;
    font-size: 11px;
    font-weight: 400;
}}
QTableView::item, QTableWidget::item {{
    padding: 0px 4px;
    height: 22px;
}}
QHeaderView::section {{
    background-color: {BG_MAIN};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER_MUTED};
    padding: 5px 6px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 11px;
    font-weight: 700;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(176, 176, 176, 0.22);
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(176, 176, 176, 0.40);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(176, 176, 176, 0.22);
    min-width: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(176, 176, 176, 0.40);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 6px 12px;
    margin: 0px 2px;
    border: none;
    border-top: 2px solid transparent;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: transparent;
    color: {TEXT};
    font-weight: 500;
    border-top: 2px solid #ffffff;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    background: {BG_SELECT};
}}
QTabBar::close-button {{
    image: url({CLOSE_TAB_SVG});
    background: transparent;
    border: none;
    subcontrol-position: right;
    width: 12px;
    height: 12px;
    margin-left: 6px;
}}
QTabBar::close-button:hover {{
    image: url({CLOSE_TAB_HOVER_SVG});
    background-color: {BG_SELECT};
    border-radius: 3px;
}}
QToolButton#newSessionButton {{
    background-color: transparent;
    border: none;
    border-radius: 4px;
    color: {TEXT_DIM};
    font-size: 14px;
    font-weight: bold;
    padding: 0px;
}}
QToolButton#newSessionButton:hover {{
    background-color: {BG_SELECT};
    color: {TEXT};
}}
QStatusBar {{
    background-color: {BG_MAIN};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER_MUTED};
}}
"""


def apply_theme(app: QtWidgets.QApplication):
    """Thiết lập Fusion Dark Palette + Stylesheet QSS toàn cục cho QApplication."""
    app.setStyle("Fusion")
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(BG_MAIN))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(TEXT))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(BG_DEEP))
    pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(BG_MAIN))
    pal.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(TOOLTIP_BG))
    pal.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(TEXT))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor(TEXT))
    pal.setColor(QtGui.QPalette.Button, QtGui.QColor(BG_CARD))
    pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(TEXT))
    pal.setColor(QtGui.QPalette.BrightText, QtGui.QColor("#ffffff"))
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(BG_SELECT))
    pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def configure_pyqtgraph(plot_widget: pg.PlotWidget = None):
    """Cấu hình toàn cục hoặc cho PlotWidget pyqtgraph."""
    pg.setConfigOptions(antialias=False, background=BG_CANVAS, foreground=TEXT)
    if plot_widget is not None:
        plot_widget.setBackground(BG_CANVAS)
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
COLOR_BG_CANVAS = BG_CANVAS
COLOR_BG_DEEP = BG_DEEP
COLOR_CARD = BG_CARD
COLOR_SELECT = BG_SELECT
COLOR_BORDER = BORDER
COLOR_TEXT = TEXT
COLOR_TEXT_DIM = TEXT_DIM
COLOR_ACCENT_START = ACCENT_START
COLOR_TRIGGER_MARKER = TRIGGER_MARKER
COLOR_GRID = GRID
COLOR_GRID_DASH = GRID_DASH
COLOR_TOOLTIP_BG = TOOLTIP_BG

NEON_CHANNEL_COLORS = CHANNEL_COLORS
DEFAULT_CHANNEL_NAMES = [f"Channel {i}" for i in range(8)]
DARK_THEME_QSS = QSS
setup_pyqtgraph_theme = configure_pyqtgraph
