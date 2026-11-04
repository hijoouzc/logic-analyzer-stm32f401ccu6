"""software/gui/proto.py
Prototype GUI để đánh giá độ giống với ảnh tham chiếu (Saleae Logic 2).
Chạy: python3 -m software.gui.proto v3 out.png  hoặc  python3 software/gui/proto.py v3 out.png
"""
import os
import sys

# Khử cảnh báo Wayland requestActivate
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland=false")

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

try:
    from software.gui import theme as T
except ImportError:
    import theme as T

S = 1.39            # hệ số HiDPI giả định: cửa sổ logic 1280 -> 1780 px
W, H = 1780, 1197   # kích thước ảnh tham chiếu


def px(v):
    return int(round(v * S))


# ----- Cấu hình các phiên bản --------------------------------------------------
VERSIONS = {
    # v1: đúng đúng các giá trị trong UI_SPEC.md/theme.py (đơn vị px logic)
    "v1": dict(label_w=T.LABEL_COLUMN_WIDTH, row_h=T.CHANNEL_ROW_HEIGHT, dec_scale=1.0,
               right_w=T.RIGHT_PANEL_WIDTH, rail_w=0, axis_h=26, bottom_h=34,
               menu_dark=True, font=13, strip_w=4, grid_dash=False),
    # v2: đã chỉnh theo số đo từ ảnh tham chiếu (px vật lý / 1.39)
    "v2": dict(label_w=194, row_h=47, dec_scale=1.45,
               right_w=313, rail_w=65, axis_h=32, bottom_h=42,
               menu_dark=False, font=13, strip_w=4, grid_dash=True),
}

VERSIONS["v3"] = dict(VERSIONS["v2"], stretch=True, hl=True, bit_dots=True,
                      table_marker=True, hdr_style=True, lw=1.0, card_close=True)


def uart_bits(fs=1e6, n=32768, trig=6554, text="TEST_LA_2026\r\n", baud=115200):
    y = np.ones(n, dtype=np.uint8)
    bl = fs / baud
    for i in range(trig, n):
        t = (i - trig) / bl
        f = int(t // 10)
        if f < len(text):
            pos = int(t) % 10
            if pos == 0:
                y[i] = 0
            elif pos <= 8:
                y[i] = (ord(text[f]) >> (pos - 1)) & 1
    return y


def square(n, period, duty=0.5, phase=0):
    i = (np.arange(n) + phase) % period
    return (i < period * duty).astype(np.uint8)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, P):
        super().__init__()
        self.P = P
        self.setStyleSheet(T.QSS + f"""
            QWidget {{ font-size: {px(P['font'])}px; font-family: "Segoe UI", "Inter"; }}
            QPushButton#startButton {{ border-radius: {px(25)}px; min-width: {px(50)}px;
                                       min-height: {px(50)}px; max-width: {px(50)}px; max-height: {px(50)}px; padding: 0px; }}
        """)
        if not P["menu_dark"]:
            self.setStyleSheet(self.styleSheet() +
                               "QMenuBar { background-color: #ffffff; color: #1b1b1c; }")
        mb = self.menuBar()
        for m in ("File", "Edit", "Capture", "Measure", "View", "Help"):
            mb.addMenu(m)
        if not P["menu_dark"]:
            mb.setStyleSheet("QMenuBar { background-color: #ffffff; color: #1b1b1c; }")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._wave_area(), 1)
        body.addWidget(self._right_panel())
        if P["rail_w"]:
            body.addWidget(self._rail())
        outer.addWidget(self._bottom_bar())

    # ---- vùng sóng -----------------------------------------------------------
    def _wave_area(self):
        P = self.P
        row_h = px(P["row_h"])
        axis_h = px(P["axis_h"])
        if P.get("stretch"):
            avail = H - self.menuBar().sizeHint().height() - px(P["bottom_h"]) - axis_h
            row_h = int(avail / (7 + P["dec_scale"]))
        heights = [int(row_h * P["dec_scale"])] + [row_h] * 7
        total = sum(heights)
        self.row_h_used = row_h
        w = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        # cột nhãn
        lab = QtWidgets.QWidget()
        lab.setFixedWidth(px(P["label_w"]))
        vl = QtWidgets.QVBoxLayout(lab)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addSpacing(axis_h)
        for i, h in enumerate(heights):
            f = QtWidgets.QFrame()
            f.setFixedHeight(h)
            col = T.CHANNEL_COLORS[i]
            f.setStyleSheet(f"QFrame{{background:{T.BG_MAIN};border-left:{px(P['strip_w'])}px solid {col};"
                            f"border-bottom:1px solid {T.BORDER};}} QLabel{{border:none;}}")
            lay = QtWidgets.QVBoxLayout(f)
            lay.setContentsMargins(px(14), px(6), 0, px(6))
            lay.setSpacing(0)
            if P.get("hdr_style"):
                top = QtWidgets.QLabel(f"<span style='color:{col};font-size:{px(11)}px'>D{i}</span>"
                                       f"&nbsp;&nbsp;&nbsp;<span style='font-size:{px(15)}px'>Channel {i}</span>")
            else:
                top = QtWidgets.QLabel(f"<span style='color:{col}'>CH{i}</span> &nbsp; Channel {i}")
            lay.addWidget(top, 0, QtCore.Qt.AlignTop if i == 0 else QtCore.Qt.AlignVCenter)
            if i == 0:
                chip = QtWidgets.QLabel(f"<span style='color:{T.DECODE_UART_BG}'>&#9632;</span> Async Serial")
                chip.setStyleSheet(f"color:{T.TEXT_DIM};font-size:{px(11)}px;")
                lay.addWidget(chip)
                lay.addStretch(1)
            vl.addWidget(f)
        vl.addStretch(1)
        hl.addWidget(lab)
        # vùng đồ thị
        class Ax(pg.AxisItem):
            def tickStrings(self, values, scale, spacing):
                return [f"+{v / 1000:.1f} ms" for v in values]
        pw = pg.PlotWidget(background=T.BG_MAIN, axisItems={"top": Ax("top")})
        pw.setFixedHeight(axis_h + total)
        plot = pw.getPlotItem()
        plot.hideAxis("left"); plot.hideAxis("bottom"); plot.showAxis("top")
        plot.hideButtons(); plot.setMenuEnabled(False)
        plot.layout.setContentsMargins(0, 0, 0, 0)
        plot.layout.setSpacing(0)
        ax = plot.getAxis("top")
        ax.setHeight(axis_h)
        ax.setPen(pg.mkPen(T.GRID)); ax.setTextPen(pg.mkPen(T.TEXT))
        ax.setTickSpacing(100, 50)
        vb = plot.getViewBox()
        vb.setMouseEnabled(False, False)
        vb.invertY(True)
        vb.setYRange(0, total, padding=0)
        vb.setXRange(-60, 640, padding=0)
        # dữ liệu
        n, trig = 32768, 6554
        sig = [uart_bits(), square(n, 10), square(n, 20), square(n, 50), square(n, 100),
               square(n, 200), square(n, 37, 0.3), square(n, 5)]
        lo_i, hi_i = trig - 80, trig + 700
        xs = np.arange(lo_i, hi_i) - trig
        y0 = 0
        hl_list = []
        grid_pen = pg.mkPen(T.GRID, width=1, style=QtCore.Qt.DashLine if P["grid_dash"] else QtCore.Qt.SolidLine)
        for gx in range(0, 700, 100):
            vb.addItem(pg.InfiniteLine(pos=gx, angle=90, pen=grid_pen))
        for i, h in enumerate(heights):
            top = y0 + (h - row_h)
            hi, lo = top + row_h * 0.22, top + row_h * 0.78
            hl_list.append((hi, lo))
            yy = np.where(sig[i][lo_i:hi_i] == 1, hi, lo)
            curve = pg.PlotCurveItem(xs, yy, stepMode="left", pen=pg.mkPen(T.CHANNEL_COLORS[i], width=P.get('lw', 1.4)))
            vb.addItem(curve)
            vb.addItem(pg.InfiniteLine(pos=y0 + h, angle=0, pen=pg.mkPen(T.BORDER)))
            y0 += h
        if P.get("hl"):
            for (hi_, lo_) in hl_list:
                for lbl, yv in (("H", hi_), ("L", lo_)):
                    t_ = pg.TextItem(lbl, color=T.TEXT, anchor=(0, 0.5))
                    t_.setPos(-57, yv); vb.addItem(t_)
        # chú thích UART
        text = "TEST_LA_2026\r\n"
        bl = 1e6 / 115200
        for k, ch in enumerate(text[:8]):
            xa, xb = k * 10 * bl + bl, (k * 10 + 9) * bl
            r = QtWidgets.QGraphicsRectItem(xa, heights[0] * 0.08, xb - xa, row_h * 0.30)
            r.setBrush(pg.mkBrush(T.DECODE_UART_BG)); r.setPen(pg.mkPen(None))
            vb.addItem(r)
            tx = pg.TextItem(f"0x{ord(ch):02X}", color=T.DECODE_UART_FG, anchor=(0.5, 0.5))
            tx.setPos((xa + xb) / 2, heights[0] * 0.08 + row_h * 0.15)
            vb.addItem(tx)
        if P.get("bit_dots"):
            hi0, lo0 = hl_list[0]
            dx, dy = [], []
            for k, ch in enumerate(text[:8]):
                for j in range(8):
                    xc = (k * 10 + 1 + j + 0.5) * bl
                    bit = (ord(ch) >> j) & 1
                    dx.append(xc); dy.append(hi0 if bit else lo0)
            sc = pg.ScatterPlotItem(dx, dy, size=px(4), brush=pg.mkBrush(T.TEXT), pen=pg.mkPen(None))
            vb.addItem(sc)
        vb.addItem(pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen(T.TRIGGER_MARKER, width=2)))
        hl.addWidget(pw, 1, QtCore.Qt.AlignTop)
        self.rows_total = total
        return w

    # ---- panel phải ----------------------------------------------------------
    def _right_panel(self):
        P = self.P
        w = QtWidgets.QWidget()
        w.setFixedWidth(px(P["right_w"]))
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(px(12), px(8), px(12), px(8))
        v.setSpacing(px(8))
        h = QtWidgets.QHBoxLayout()
        t = QtWidgets.QLabel("Analyzers"); t.setStyleSheet(f"font-size:{px(19)}px;font-weight:bold;")
        h.addWidget(t); h.addStretch(1); h.addWidget(QtWidgets.QLabel("+"))
        v.addLayout(h)
        a = QtWidgets.QLabel(f"<span style='color:{T.DECODE_UART_BG}'>&#9632;</span> &nbsp;Async Serial &nbsp;"
                             f"<span style='color:{T.ACCENT_START}'>&#10004;</span>")
        a.setStyleSheet(f"font-size:{px(16)}px;")
        v.addWidget(a)
        card = QtWidgets.QFrame(); card.setStyleSheet(f"QFrame{{background:{T.BG_CARD};border-radius:{px(4)}px;}}")
        cl = QtWidgets.QHBoxLayout(card); cl.setContentsMargins(px(10), px(8), px(10), px(8))
        cl.addWidget(QtWidgets.QLabel("› Trigger View ⚠")); cl.addStretch(1)
        if P.get("card_close"):
            x = QtWidgets.QLabel("✕"); x.setStyleSheet(f"background:{T.BG_SELECT};border-radius:{px(10)}px;padding:{px(2)}px {px(8)}px;")
            cl.addWidget(x)
        v.addWidget(card)
        d = QtWidgets.QLabel(f"Data &nbsp;<span style='color:{T.ACCENT_START}'>&#10004;</span>")
        d.setStyleSheet(f"font-size:{px(19)}px;font-weight:bold;")
        v.addWidget(d)
        s = QtWidgets.QLineEdit(); s.setPlaceholderText("Type to search")
        v.addWidget(s)
        mk = bool(P.get("table_marker"))
        nc = 4 if mk else 3
        tb = QtWidgets.QTableWidget(14, nc)
        tb.setHorizontalHeaderLabels((["", "Type", "Start", "Duration"] if mk else ["Type", "Start", "Duration"]))
        tb.verticalHeader().setVisible(False)
        tb.setAlternatingRowColors(False)
        tb.setShowGrid(False)
        tb.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for r in range(14):
            vals = ["data", f"{86.8 + r * 86.8:.1f} µs", "82.46 µs"]
            if mk:
                vals = ["■"] + vals
            for c, val in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(val)
                if mk and c == 0:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(T.DECODE_UART_BG)))
                tb.setItem(r, c, it)
            tb.setRowHeight(r, px(30))
        tb.horizontalHeader().setStretchLastSection(True)
        tb.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        if mk:
            for c, wd in enumerate((28, 62, 104)):
                tb.setColumnWidth(c, px(wd))
        else:
            for c, wd in enumerate((70, 120)):
                tb.setColumnWidth(c, px(wd))
        v.addWidget(tb, 1)
        return w

    # ---- dải icon phải -------------------------------------------------------
    def _rail(self):
        P = self.P
        w = QtWidgets.QWidget()
        w.setFixedWidth(px(P["rail_w"]))
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, px(8), 0, px(8))
        v.setSpacing(px(14))
        b = QtWidgets.QPushButton("▶"); b.setObjectName("startButton")
        v.addWidget(b, 0, QtCore.Qt.AlignHCenter)
        for ch in ("▭", "1F", "✎", "▦"):
            bt = QtWidgets.QToolButton(); bt.setText(ch)
            bt.setStyleSheet(f"QToolButton{{border:none;color:{T.TEXT_DIM};font-size:{px(20)}px;}}")
            v.addWidget(bt, 0, QtCore.Qt.AlignHCenter)
        v.addStretch(1)
        return w

    # ---- thanh dưới ----------------------------------------------------------
    def _bottom_bar(self):
        P = self.P
        w = QtWidgets.QWidget()
        w.setFixedHeight(px(P["bottom_h"]))
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(px(8), 0, px(12), 0)
        if P["rail_w"]:
            tabs = QtWidgets.QTabBar(); tabs.setExpanding(False)
            for t in ("Session 0", "Session 1", "+"):
                tabs.addTab(t)
            tabs.setCurrentIndex(1)
            h.addWidget(tabs)
            h.addStretch(1)
            h.addWidget(QtWidgets.QLabel("128 µs ⌃"))
        else:
            h.addWidget(QtWidgets.QLabel("Connected (v1.0.0)  |  1 MHz  |  32768 samples"))
            h.addStretch(1)
            b = QtWidgets.QPushButton("Start"); b.setStyleSheet(f"background:{T.ACCENT_START};border:none;")
            h.addWidget(b)
        return w


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else "v3"
    out = sys.argv[2] if len(sys.argv) > 2 else "proto_out.png"
    app = QtWidgets.QApplication([])
    pg.setConfigOptions(antialias=False, foreground=T.TEXT)
    win = MainWindow(VERSIONS[ver])
    win.resize(W, H)
    win.show()
    for _ in range(5):
        app.processEvents()
    win.grab().save(out)
    print("row_h_used_px", getattr(win, "row_h_used", None), "ratio", getattr(win, "row_h_used", 0) / 1197)
    print("saved", out, win.size())


if __name__ == "__main__":
    main()
