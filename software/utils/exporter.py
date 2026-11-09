#!/usr/bin/env python3
"""
software/utils/exporter.py
Xuất dữ liệu đo kiểm và đồ thị dạng sóng đa định dạng chuẩn thương mại:
1. export_image: Xuất hình ảnh đồ thị (PNG/SVG) độ phân giải cao phục vụ Báo cáo & Slide.
2. export_csv: Xuất ma trận dữ liệu mẫu 8 kênh ra file bảng tính CSV.
3. export_vcd: Xuất dữ liệu xung số ra định dạng chuẩn IEEE 1364 VCD (Value Change Dump) để mở bằng GTKWave / PulseView.
"""

import os
import csv
import time
import math
import numpy as np
from typing import Dict, Any, Optional
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg


def export_image(plot_widget: pg.PlotWidget, filepath: str) -> bool:
    """
    Xuất khung vẽ sóng hiện tại thành ảnh PNG hoặc SVG độ phân giải cao.

    :param plot_widget: Widget pyqtgraph chứa dạng sóng
    :param filepath: Đường dẫn lưu tệp (ví dụ: capture.png hoặc waveform.svg)
    :return: True nếu thành công, False nếu thất bại
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".svg":
            from pyqtgraph.exporters import SVGExporter
            SVGExporter(plot_widget.getPlotItem()).export(str(filepath))
            return os.path.getsize(filepath) > 0
        else:
            # Mặc định xuất ảnh PNG chất lượng cao
            pixmap = plot_widget.grab()
            return pixmap.save(filepath, "PNG", quality=100)
    except Exception as e:
        print(f"[EXPORTER ERROR] export_image failed: {e}")
        return False


def export_csv(data_dict: Dict[str, Any], filepath: str, time_relative_to_trigger: bool = True) -> bool:
    """
    Xuất toàn bộ 32.768 mẫu của 8 kênh ra tệp bảng tính CSV.

    :param data_dict: Dict kết quả thu thập chứa channels, sample_rate, sample_count, trig_offset
    :param filepath: Đường dẫn lưu tệp .csv
    :param time_relative_to_trigger: Nếu True, t=0 tại trigger; nếu False, t chạy từ 0 đến T_total
    :return: True nếu thành công, False nếu có lỗi
    """
    try:
        channels = data_dict.get("channels")
        sample_rate = float(data_dict.get("sample_rate", 1_000_000.0))
        sample_count = int(data_dict.get("sample_count", 32768))
        trig_offset = int(data_dict.get("trig_offset", 6554))

        if channels is None or len(channels) != 8 or sample_count <= 0 or not math.isfinite(sample_rate) or sample_rate <= 0 or any(len(c) < sample_count for c in channels):
            return False

        # Tính toán mốc thời gian cho từng mẫu
        if time_relative_to_trigger:
            time_col = (np.arange(sample_count, dtype=np.float64) - trig_offset) / sample_rate
        else:
            time_col = np.arange(sample_count, dtype=np.float64) / sample_rate

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Time_s", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7"])
            for i in range(sample_count):
                row = [f"{time_col[i]:.12g}"] + [int(channels[ch][i]) for ch in range(8)]
                writer.writerow(row)
        return True
    except Exception as e:
        print(f"[EXPORTER ERROR] export_csv failed: {e}")
        return False


def export_vcd(data_dict: Dict[str, Any], filepath: str) -> bool:
    """
    Xuất dữ liệu 8 kênh ra định dạng chuẩn IEEE 1364 VCD (Value Change Dump).
    Chỉ ghi các thời điểm chuyển mức logic (Event-driven Compression),
    tệp nén cực nhẹ và tương thích hoàn hảo với phần mềm GTKWave / Sigrok PulseView.
    """
    try:
        channels = data_dict.get("channels")
        sample_rate = float(data_dict.get("sample_rate", 1_000_000.0))
        sample_count = int(data_dict.get("sample_count", 32768))

        if channels is None or len(channels) != 8 or sample_count <= 0 or not math.isfinite(sample_rate) or sample_rate <= 0 or any(len(c) < sample_count for c in channels):
            return False

        vcd_symbols = ["!", '"', "#", "$", "%", "&", "'", "("]

        with open(filepath, "w", encoding="utf-8") as f:
            # 1. Header VCD
            f.write("$date\n")
            f.write(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("$end\n")
            f.write("$version\n")
            f.write("  HUST STM32 Logic Analyzer VCD Exporter v2.0\n")
            f.write("$end\n")
            f.write("$timescale 1ns $end\n")
            f.write(f"$comment sample_rate={sample_rate:g} Hz; trigger_offset={data_dict.get('trig_offset', 0)} samples $end\n")
            f.write("$scope module LogicAnalyzer $end\n")
            for ch in range(8):
                f.write(f"$var wire 1 {vcd_symbols[ch]} D{ch} $end\n")
            f.write("$upscope $end\n")
            f.write("$enddefinitions $end\n")

            # 2. Giá trị ban đầu tại mốc t = 0
            f.write("#0\n")
            f.write("$dumpvars\n")
            last_vals = []
            for ch in range(8):
                val = int(channels[ch][0])
                last_vals.append(val)
                f.write(f"{val}{vcd_symbols[ch]}\n")
            f.write("$end\n")

            # 3. Quét sự kiện chuyển mức bằng NumPy vectorization và ghi vào tệp
            last_time_written = 0
            mat = np.column_stack([np.asarray(channels[ch][:sample_count], dtype=np.uint8) for ch in range(8)])
            diffs = mat[1:] != mat[:-1]
            changed_rows = np.where(np.any(diffs, axis=1))[0] + 1
            for i in changed_rows:
                time_ns = int(round(int(i) * 1e9 / sample_rate))
                f.write(f"#{time_ns}\n")
                last_time_written = time_ns
                for ch in np.where(diffs[i - 1])[0]:
                    curr_val = int(mat[i, ch])
                    f.write(f"{curr_val}{vcd_symbols[ch]}\n")
            # Preserve capture duration even if no channels change near the end.
            end_time = int(round((sample_count - 1) * 1e9 / sample_rate))
            if end_time > last_time_written:
                f.write(f"#{end_time}\n")

        return True
    except Exception as e:
        print(f"[EXPORTER ERROR] export_vcd failed: {e}")
        return False
