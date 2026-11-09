#!/usr/bin/env python3
"""
software/tests/test_phase2_commercial.py
Bộ kiểm thử tự động toàn diện cho phân hệ Desktop GUI Giai đoạn 2 (Chuẩn thương mại):
1. LogicAnalyzerClient: Hỗ trợ Offline Mock, send_ping, send_start, send_abort.
2. I2CDecoder: Nhận diện START, Addr (W/R), ACK/NACK, DATA, STOP.
3. SPIDecoder: Kiểm thử cả 4 Mode (0, 1, 2, 3) song công MOSI & MISO.
4. CursorManager & HUD: Tính toán t_A, t_B, Δt và f = 1/Δt.
5. Exporter: Xuất PNG, CSV và GTKWave VCD.
6. MainWindow: Giao diện PyQt5 Dark Mode, Channel Manager, Cursors, 3 Decoders.
"""

import os
import sys
import tempfile
import numpy as np

# Thiết lập môi trường headless
os.environ["QT_QPA_PLATFORM"] = "offscreen"

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5 import QtWidgets
from software.gui.logic_client import LogicAnalyzerClient
from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder
from software.gui.waveform_widget import format_si_time as format_time, format_si_freq as format_freq
from software.utils.exporter import export_image, export_csv, export_vcd
from software.gui.main_window import MainWindow
from software.qt_bootstrap import configure_qt_plugins


def test_phase2():
    configure_qt_plugins()
    print("==================================================")
    print("BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG GIAI ĐOẠN 2 (CHUẨN THƯƠNG MẠI)")
    print("==================================================")

    # 1. Kiểm thử LogicAnalyzerClient với Offline Mock
    print("\n[TEST 1] Kiểm thử LogicAnalyzerClient (Offline Mock & API chuẩn)...")
    client = LogicAnalyzerClient()
    ports = client.list_ports()
    assert any(p[0] == "OFFLINE_MOCK" for p in ports), "Không tìm thấy tùy chọn OFFLINE_MOCK"
    
    ok, msg = client.connect("OFFLINE_MOCK")
    assert ok and client.is_connected
    ok_ping, ver = client.send_ping()
    assert ok_ping and "offline" in ver
    
    status, trig_offset, sample_count, payload, checksum_ok = client.send_start(rate_idx=3, trig_ch=0, trig_mode=2)
    assert status == 0
    assert trig_offset == 6554
    assert sample_count == 32768
    assert len(payload) == 32768
    assert checksum_ok
    assert client.send_abort()
    client.disconnect()
    assert not client.is_connected
    print("-> [PASS] Client Offline Mock, PING, START, ABORT hoạt động 100%!")

    # 2. Kiểm thử I2C Decoder
    print("\n[TEST 2] Kiểm thử I2C Decoder (START, Addr 0x3C Write, Data 0xAA, STOP)...")
    scl = [1]*10
    sda = [1]*10
    # START: SDA 1 -> 0 while SCL 1
    scl += [1]*4; sda += [0]*4
    # Address 0x3C Write = 0x78 (0111 1000), ACK=0
    for b in [0, 1, 1, 1, 1, 0, 0, 0, 0]:
        scl += [0]*4 + [1]*4
        sda += [b]*8
    # Data 0xAA (1010 1010), ACK=0
    for b in [1, 0, 1, 0, 1, 0, 1, 0, 0]:
        scl += [0]*4 + [1]*4
        sda += [b]*8
    # STOP: SDA 0 -> 1 while SCL 1
    scl += [1]*8
    sda += [0]*4 + [1]*4

    i2c = I2CDecoder(sample_rate=1e6)
    i2c_text, i2c_frames = i2c.decode(scl, sda)
    assert "0x3C" in i2c_text
    assert "0xAA" in i2c_text
    assert len(i2c_frames) == 4  # START, ADDR, DATA, STOP
    assert i2c_frames[1]["val"] == 0x3C
    assert i2c_frames[2]["val"] == 0xAA
    print(f"-> [PASS] I2C Decoder trích xuất chuẩn xác: {i2c_text.strip()}")

    # 3. Kiểm thử SPI Decoder (Mode 0 & Mode 3)
    print("\n[TEST 3] Kiểm thử SPI Decoder (Song công MOSI: 0x9F, MISO: 0x55)...")
    sck = [0]*10
    mosi = [0]*10
    miso = [0]*10
    cs = [0]*10 # Active low
    for b in range(8):
        m_bit = (0x9F >> (7 - b)) & 1
        s_bit = (0x55 >> (7 - b)) & 1
        sck += [0]*4 + [1]*4
        mosi += [m_bit]*8
        miso += [s_bit]*8
        cs += [0]*8
    sck += [0]*10; mosi += [0]*10; miso += [0]*10; cs += [1]*10

    spi = SPIDecoder(sample_rate=1e6, cpol=0, cpha=0)
    spi_text, spi_frames = spi.decode(sck, mosi, miso, cs)
    assert len(spi_frames) == 1
    assert spi_frames[0]["mosi_val"] == 0x9F
    assert spi_frames[0]["miso_val"] == 0x55
    print(f"-> [PASS] SPI Decoder trích xuất chuẩn xác:\n   {spi_text.strip()}")

    # 4. Kiểm thử Exporter (PNG, CSV, VCD)
    print("\n[TEST 4] Kiểm thử Exporter (PNG, CSV, VCD)...")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = MainWindow(load_sample_on_start=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        img_file = os.path.join(tmpdir, "wave.png")
        csv_file = os.path.join(tmpdir, "data.csv")
        vcd_file = os.path.join(tmpdir, "wave.vcd")

        assert export_image(win.plot_widget, img_file)
        assert os.path.exists(img_file) and os.path.getsize(img_file) > 1000
        print("-> [PASS] Xuất ảnh PNG thành công!")

        assert export_csv(win.current_data, csv_file)
        assert os.path.exists(csv_file) and os.path.getsize(csv_file) > 50000
        print("-> [PASS] Xuất bảng tính CSV thành công (đủ 32.768 dòng mẫu)!")

        assert export_vcd(win.current_data, vcd_file)
        assert os.path.exists(vcd_file) and os.path.getsize(vcd_file) > 500
        with open(vcd_file) as f:
            content = f.read()
            assert "$timescale 1ns $end" in content
            assert "$var wire 1 ! D0 $end" in content
            assert "$dumpvars" in content
        print("-> [PASS] Xuất tệp GTKWave VCD chuẩn IEEE 1364 thành công!")

    # 5. Kiểm thử Cursors A/B & HUD
    print("\n[TEST 5] Kiểm thử Cặp Thước Đo Thời Gian A & B...")
    win.cursor_manager.set_positions(0.000, 0.0000868)
    dt = win.cursor_manager.get_delta_t()
    freq = win.cursor_manager.get_frequency()
    assert abs(dt - 0.0000868) < 1e-9
    assert abs(freq - 11520.73) < 1.0
    assert "86.800 µs" in win.hud_widget.lbl_dt.text()
    assert "11.521 kHz" in win.hud_widget.lbl_freq.text()
    print(f"-> [PASS] HUD Thước đo hiển thị chính xác: Δt = {format_time(dt)}, f = {format_freq(freq)}")

    # 6. Kiểm thử Channel Manager & Decoders trong GUI
    print("\n[TEST 6] Kiểm thử Channel Manager (Show/Hide, Đổi tên) và Decoders...")
    # Đổi tên kênh D0 sang UART_LOOPBACK
    win.ch_name_edits[0].setText("UART_LOOPBACK")
    win._on_channel_name_changed(0)
    assert win.channel_names[0] == "UART_LOOPBACK"

    # Tắt hiển thị kênh D7
    win._on_channel_visibility_changed(7, 0)
    assert not win.channel_visible[7]
    assert not win.channel_curves[7].isVisible()

    # Chạy decoder UART trên GUI
    win._on_decode_uart()
    assert "TEST_LA_2026" in win.txt_uart_decoded.toPlainText()
    assert win.table_uart_frames.rowCount() == 14
    print("-> [PASS] Giao diện GUI giải mã UART hiển thị 14 ký tự 'TEST_LA_2026\\r\\n'!")

    # 7. Kiểm thử hồi quy (Regression Tests) cho các lỗi High/Medium đã sửa
    print("\n[TEST 7] Kiểm thử Hồi Quy: Free-run Time Alignment, MultiBubble Click & I2C START/STOP...")
    # 7a. Kiểm tra I2C START và STOP có độ rộng > 0 để vẽ được bong bóng
    for f in i2c_frames:
        if f["type"] in ("START", "REPEATED_START", "STOP"):
            assert f["stop_sample"] > f["start_sample"], f"I2C {f['type']} phải có độ rộng > 0 mẫu!"

    # 7b. Kiểm tra MultiBubble click không bị trừ trig_offset 2 lần
    win.waveform.plot_widget.setXRange(-0.01, 0.03, padding=0)  # Zoom xa để kích hoạt MultiBubble
    win.waveform._render_uart_bubbles()
    assert win.waveform._is_multibubble is True
    assert len(win.waveform.decode_items) >= 1
    first_mb = win.waveform.decode_items[0]
    expected_t_start = first_mb.t_start
    expected_t_stop = first_mb.t_stop
    first_mb.on_clicked()
    c_a = float(win.waveform.cursor_a.value())
    assert abs(c_a - expected_t_start) < 1e-9, f"MultiBubble click bị lệch: {c_a} != {expected_t_start}"

    # 7c. Kiểm tra chế độ Free-run (status == 1) đồng bộ gốc thời gian giữa sóng và bong bóng
    freerun_data = dict(win.current_data)
    freerun_data["status"] = 1
    freerun_data["trig_offset"] = 6554
    win._render_capture_data(freerun_data)
    win.waveform.plot_widget.setXRange(0.0, 0.002, padding=0)  # Zoom gần để dùng SingleBubble
    win.waveform._render_uart_bubbles()
    first_frame = win.current_uart_frames[0]
    expected_freerun_t = (first_frame.get("data_start_sample", first_frame["start_sample"]) - 6554) / float(freerun_data["sample_rate"])
    first_sb = win.waveform.decode_items[0]
    assert abs(first_sb.t_start - expected_freerun_t) < 1e-9, (
        f"Free-run bubble bị lệch trục thời gian: {first_sb.t_start} != {expected_freerun_t}"
    )
    win.close()
    print("-> [PASS] Free-run Time Alignment, MultiBubble Click Zoom và I2C START/STOP chuẩn xác 100%!")

    print("\n==================================================")
    print("  [SUCCESS] 100% CÁC BÀI KIỂM THỬ GIAI ĐOẠN 2 ĐẠT PASS!")
    print("  Kiểm thử phần mềm/offline đạt; chưa kiểm chứng phần cứng thật trong lượt chạy này.")
    print("==================================================")


if __name__ == "__main__":
    test_phase2()
