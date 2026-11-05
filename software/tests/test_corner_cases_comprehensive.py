#!/usr/bin/env python3
"""
software/tests/test_corner_cases_comprehensive.py
Bộ kiểm thử toàn diện các Test Cases & Corner Cases (Edge Cases, Negative Cases, Stress Tests)
cho toàn bộ phân hệ Software (Client, Decoders, Measurements, Exporter, WaveformWidget, MainWindow).
"""

import os
import sys
import pty
import time
import threading
import tempfile
import numpy as np

# Chạy PyQt5 ở chế độ headless offscreen
os.environ["QT_QPA_PLATFORM"] = "offscreen"

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5 import QtCore, QtGui, QtWidgets
from software.gui.logic_client import LogicAnalyzerClient
from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder
from software.gui.measurements import (
    measure_channel_signal,
    format_measurement_results,
    find_most_active_channel,
    format_si_val,
)
from software.utils.exporter import export_image, export_csv, export_vcd
from software.gui.waveform_widget import format_si_time, format_si_freq
from software.gui.main_window import MainWindow


# ==============================================================================
# NHÓM 1: LOGIC ANALYZER CLIENT & PROTOCOL CORNER CASES (spec/protocol.md)
# ==============================================================================
def test_1_client_protocol_corner_cases():
    print("\n[GROUP 1] Kiểm thử LogicAnalyzerClient & Giao thức Nhị phân (Corner Cases)...")
    client = LogicAnalyzerClient()

    # 1.1. Gọi lệnh khi chưa kết nối
    ok_p, msg_p = client.ping()
    assert not ok_p and "Chưa kết nối" in msg_p
    ok_a, msg_a = client.abort()
    assert not ok_a and "Chưa kết nối" in msg_a
    res_s = client.start_capture()
    assert not res_s["success"] and "Chưa kết nối" in res_s["error"]
    print("  [1.1] Từ chối lệnh khi chưa kết nối cổng serial: PASS")

    # 1.2. Ràng buộc tham số đầu vào (Boundary Value Analysis)
    client.connect("OFFLINE_MOCK")
    for bad_rate in (-1, 9, 255):
        r = client.start_capture(rate_idx=bad_rate, trig_ch=0, trig_mode=0)
        assert not r["success"] and "RATE_IDX" in r["error"]
    for bad_ch in (-1, 8, 15):
        r = client.start_capture(rate_idx=3, trig_ch=bad_ch, trig_mode=0)
        assert not r["success"] and "Trigger Channel" in r["error"]
    for bad_mode in (-1, 3, 99):
        r = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=bad_mode)
        assert not r["success"] and "Trigger Mode" in r["error"]
    client.disconnect()
    print("  [1.2] Kiểm tra biên tham số (rate_idx 0..8, trig_ch 0..7, trig_mode 0..2): PASS")

    # 1.3. Kiểm thử load_offline_file với các file hỏng/lỗi
    with tempfile.TemporaryDirectory() as tmpdir:
        # File không tồn tại
        r = client.load_offline_file(os.path.join(tmpdir, "nonexistent.bin"))
        assert not r["success"] and "không tồn tại" in r["error"]

        # File sai kích thước (0B, 7B, 32775B, 32777B)
        for bad_size in (0, 7, 32775, 32777):
            p = os.path.join(tmpdir, f"size_{bad_size}.bin")
            with open(p, "wb") as f:
                f.write(b"\x5A\xA5" + b"\x00" * max(0, bad_size - 2))
            r = client.load_offline_file(p)
            assert not r["success"] and "Kích thước" in r["error"]

        # File đúng 32776B nhưng sai Magic Header
        p_magic = os.path.join(tmpdir, "bad_magic.bin")
        with open(p_magic, "wb") as f:
            f.write(b"\xA5\x5A" + b"\x00" * 32774)
        r = client.load_offline_file(p_magic)
        assert not r["success"] and "Magic" in r["error"]

        # File đúng Magic nhưng sai Footer Checksum XOR
        p_csum = os.path.join(tmpdir, "bad_csum.bin")
        payload = bytes([i & 0xFF for i in range(32768)])
        true_csum = int(np.bitwise_xor.reduce(np.frombuffer(payload, dtype=np.uint8)))
        bad_csum = (true_csum ^ 0xFF) & 0xFF
        with open(p_csum, "wb") as f:
            f.write(bytes([0x5A, 0xA5, 0x00, 0x9A, 0x19, 0x00, 0x80]) + payload + bytes([bad_csum]))
        r = client.load_offline_file(p_csum)
        assert not r["success"] and "Sai Checksum" in r["error"]
    print("  [1.3] Kiểm tra file .bin hỏng (0B, thiếu/thừa byte, sai Magic, sai XOR Checksum): PASS")

    # 1.4. Kiểm thử qua PTY ảo: Sliding Window chống nhiễu rác đầu dòng (0x5A lặp: 0x5A 0x5A 0xA5),
    #      tất cả mã NAK (0xE0..0xE3), gói bị đứt giữa chừng, và hủy giữa chừng (request_abort)
    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)
    try:
        ok, _ = client.connect(slave_name)
        assert ok

        # Ca A: Nhiễu rác + 0x5A lặp [0xFF, 0x00, 0x5A, 0x5A, 0xA5] trước gói NAK 0xE3 (ERR_BUSY)
        def responder_noise_and_nak():
            _ = os.read(master, 5)
            frame = bytes([0x5A, 0xA5, 0xE3, 0x01, 0x03, 0x00])
            csum = frame[0] ^ frame[1] ^ frame[2] ^ frame[3] ^ frame[4] ^ frame[5]
            os.write(master, b"\xFF\x00\x12\x5A" + frame + bytes([csum]))

        t = threading.Thread(target=responder_noise_and_nak, daemon=True)
        t.start()
        res = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=0)
        t.join(1.0)
        # Lưu ý: nếu cội nguồn Sliding Window gặp 0x5A 0x5A 0xA5 mà pop(0) đúng thì phải bắt được 0x5A 0xA5!
        assert not res["success"] and "ERR_BUSY" in res["error"], f"Lỗi Sliding Window khi gặp 0x5A lặp: {res}"
        print("  [1.4a] Sliding Window vượt qua nhiễu rác [0xFF, 0x00, 0x12, 0x5A, 0x5A, 0xA5] & bắt NAK 0xE3: PASS")

        # Ca B: Kiểm tra các mã NAK còn lại (0xE0, 0xE1, 0xE2) và Control Frame sai Checksum
        for nak_code, expected_name in [(0xE0, "ERR_CHECKSUM"), (0xE1, "ERR_INVALID_RATE"), (0xE2, "ERR_INVALID_TRIG")]:
            def responder_nak(code=nak_code):
                _ = os.read(master, 5)
                hdr = bytes([0x5A, 0xA5, code, 0x01, 0x09, 0x00])
                c = hdr[0] ^ hdr[1] ^ hdr[2] ^ hdr[3] ^ hdr[4] ^ hdr[5]
                os.write(master, hdr + bytes([c]))
            t = threading.Thread(target=responder_nak, daemon=True)
            t.start()
            res = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=0)
            t.join(1.0)
            assert not res["success"] and expected_name in res["error"]

        # Control frame sai Checksum
        def responder_bad_ctrl_csum():
            _ = os.read(master, 5)
            os.write(master, bytes([0x5A, 0xA5, 0xE1, 0x01, 0x09, 0x00, 0x00]))
        t = threading.Thread(target=responder_bad_ctrl_csum, daemon=True)
        t.start()
        res = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=0)
        t.join(1.0)
        assert not res["success"] and "Sai Checksum Control Frame" in res["error"]
        print("  [1.4b] Nhận diện đầy đủ các mã NAK (0xE0, 0xE1, 0xE2, 0xE3) & bắt lỗi Checksum khung 7B: PASS")

        # Ca C: Hủy thu thập bất đồng bộ từ luồng khác (request_abort) khi đang chờ sóng
        def abort_trigger():
            _ = os.read(master, 5)  # đọc CMD_START
            time.sleep(0.15)
            client.request_abort()
            # Đọc CMD_ABORT do client tự gửi và trả RSP_ABORTED
            cmd_ab = os.read(master, 5)
            if len(cmd_ab) == 5 and cmd_ab[1] == 0x02:
                os.write(master, bytes([0x5A, 0xA5, 0x05, 0x00, 0x00, 0x00, 0xFA]))

        t = threading.Thread(target=abort_trigger, daemon=True)
        t.start()
        t0 = time.time()
        res = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=1)
        dt = time.time() - t0
        t.join(1.0)
        assert not res["success"] and "Đã hủy" in res["error"] and dt < 1.5
        print(f"  [1.4c] Hủy thu thập đa luồng an toàn (request_abort) thoát trong {dt:.3f}s (< 1.5s): PASS")

    finally:
        client.disconnect()
        os.close(master)
        os.close(slave)


# ==============================================================================
# NHÓM 2: BỘ GIẢI MÃ GIAO THỨC (UART, I2C, SPI) CORNER CASES
# ==============================================================================
def test_2_decoders_corner_cases():
    print("\n[GROUP 2] Kiểm thử Bộ giải mã UART, I2C, SPI (Corner Cases)...")

    # 2.1. UART Decoder Corner Cases
    uart = UARTDecoder(sample_rate=1_000_000, baudrate=115200)
    assert uart.decode([]) == ("", [])
    assert uart.decode([1] * 500) == ("", [])  # Idle HIGH liên tục
    assert uart.decode([0] * 500) == ("", [])  # Break LOW liên tục (không có cạnh xuống hoặc thiếu Stop bit)

    # Vi phạm định lý Nyquist (sample_rate < 2 * baudrate)
    uart_low_fs = UARTDecoder(sample_rate=100_000, baudrate=115200)
    txt_nyq, frames_nyq = uart_low_fs.decode([1, 0, 1] * 50)
    assert "Nyquist" in txt_nyq and frames_nyq == []

    # Glitch nhiễu ngắn (1 mẫu rơi về 0 rồi lên 1 ngay -> không phải Start bit thật)
    glitch_signal = [1] * 50 + [0] + [1] * 200
    assert uart.decode(glitch_signal) == ("", [])

    # Framing Error (Start bit = 0, 8 data bits = 0, nhưng Stop bit cũng bị kéo = 0)
    spb = 1_000_000 / 115200.0  # ~8.68 mẫu/bit
    bad_stop_frame = [1] * 20 + [0] * int(spb * 11) + [1] * 20
    assert uart.decode(bad_stop_frame) == ("", [])

    # Ký tự Non-ASCII (0x00, 0xFF, 0x80) phải được escape dạng \xHH
    def build_uart_byte(b_val: int, spb_val: float = 10.0) -> list:
        bits = [0] + [(b_val >> i) & 1 for i in range(8)] + [1]
        out = [1] * 15
        for b in bits:
            out.extend([b] * int(spb_val))
        out.extend([1] * 15)
        return out

    uart_1m_100k = UARTDecoder(sample_rate=1_000_000, baudrate=100_000)  # đúng 10 mẫu/bit
    sig_non_ascii = build_uart_byte(0x00) + build_uart_byte(0xFF) + build_uart_byte(0x41)
    txt_na, fr_na = uart_1m_100k.decode(sig_non_ascii)
    assert len(fr_na) == 3
    assert fr_na[0]["byte_val"] == 0x00 and fr_na[0]["char"] == "\\x00"
    assert fr_na[1]["byte_val"] == 0xFF and fr_na[1]["char"] == "\\xFF"
    assert fr_na[2]["byte_val"] == 0x41 and fr_na[2]["char"] == "A"
    print("  [2.1] UART Decoder (Empty, Idle, Break, Nyquist, Glitch, Framing Error, Non-ASCII \\x00/\\xFF): PASS")

    # 2.2. I2C Decoder Corner Cases (Repeated START, Read + NACK, Incomplete Byte)
    i2c = I2CDecoder(sample_rate=1_000_000)
    assert i2c.decode([], []) == ("", [])
    assert i2c.decode([1, 1], [1]) == ("", [])  # Độ dài lệch nhau

    # Tạo giao dịch: [S] -> Addr 0x50 Write + ACK -> [Sr] (Repeated START) -> Addr 0x50 Read + NACK -> [P]
    scl, sda = [1] * 5, [1] * 5
    # START: SCL=1, SDA 1->0
    scl += [1, 1, 0]; sda += [1, 0, 0]
    # Hàm phát 8 bit + ack
    def i2c_push_byte(byte_v: int, ack_bit: int):
        nonlocal scl, sda
        for b in range(7, -1, -1):
            bit = (byte_v >> b) & 1
            scl += [0, 1, 1, 0]
            sda += [bit, bit, bit, bit]
        scl += [0, 1, 1, 0]
        sda += [ack_bit, ack_bit, ack_bit, ack_bit]

    i2c_push_byte((0x50 << 1) | 0, 0)  # 0x50 Write + ACK (0)
    # Repeated START: đưa SDA lên 1 khi SCL=0, rồi kéo SCL lên 1, rồi kéo SDA xuống 0 khi SCL=1
    scl += [0, 1, 1, 0]; sda += [1, 1, 0, 0]
    i2c_push_byte((0x50 << 1) | 1, 1)  # 0x50 Read + NACK (1)
    # STOP: SDA từ 0 lên 1 khi SCL=1
    scl += [0, 1, 1, 1]; sda += [0, 0, 1, 1]

    i2c_txt, i2c_fr = i2c.decode(scl, sda)
    types = [f["type"] for f in i2c_fr]
    assert types == ["START", "ADDRESS", "REPEATED_START", "ADDRESS", "STOP"], f"Sai chuỗi frame I2C: {types}"
    assert i2c_fr[1]["rw"] == "W" and i2c_fr[1]["ack"] is True
    assert i2c_fr[3]["rw"] == "R" and i2c_fr[3]["ack"] is False
    assert all(f["stop_sample"] > f["start_sample"] for f in i2c_fr), "Mọi frame I2C phải có độ rộng > 0"
    print("  [2.2] I2C Decoder (Repeated START [Sr], Read/Write, ACK/NACK, Bubble Width > 0): PASS")

    # 2.3. SPI Decoder Corner Cases (Cả 4 Mode CPOL/CPHA, LSB-first, CS deasserted giữa chừng)
    for cpol in (0, 1):
        for cpha in (0, 1):
            for bit_order in ("MSB", "LSB"):
                spi = SPIDecoder(sample_rate=1_000_000, cpol=cpol, cpha=cpha, bit_order=bit_order)
                sample_rising = (cpol == cpha)
                idle_clk = cpol
                active_clk = 1 - cpol

                sck_s, mosi_s, miso_s, cs_s = [idle_clk] * 4, [0] * 4, [0] * 4, [1] * 4
                target_mosi = 0xA5
                target_miso = 0x3C

                for b_i in range(8):
                    bit_idx = (7 - b_i) if bit_order == "MSB" else b_i
                    m_b = (target_mosi >> bit_idx) & 1
                    s_b = (target_miso >> bit_idx) & 1
                    if sample_rising:
                        # Tạo cạnh lên 0 -> 1
                        sck_s += [0, 0, 1, 1]
                    else:
                        # Tạo cạnh xuống 1 -> 0
                        sck_s += [1, 1, 0, 0]
                    mosi_s += [m_b] * 4
                    miso_s += [s_b] * 4
                    cs_s += [0] * 4

                # Thêm 4 xung clock nhiễu khi CS = 1 (không tích cực -> phải bị bỏ qua)
                for _ in range(4):
                    sck_s += [0, 1, 0, 1]
                    mosi_s += [1] * 4
                    miso_s += [1] * 4
                    cs_s += [1] * 4

                _, sp_frames = spi.decode(sck_s, mosi_s, miso_s, cs_s)
                assert len(sp_frames) == 1, f"Mode ({cpol},{cpha},{bit_order}) giải mã sai số frame: {len(sp_frames)}"
                assert sp_frames[0]["mosi_val"] == target_mosi
                assert sp_frames[0]["miso_val"] == target_miso
    print("  [2.3] SPI Decoder (Tất cả 4 Mode CPOL/CPHA x MSB/LSB + lọc nhiễu khi CS=HIGH): PASS")


# ==============================================================================
# NHÓM 3: AUTOMATED MEASUREMENTS & EXPORTER CORNER CASES
# ==============================================================================
def test_3_measurements_and_exporter_corner_cases():
    print("\n[GROUP 3] Kiểm thử Automated Measurements & Data Exporter (Corner Cases)...")

    # 3.1. Mảng rỗng hoặc sample_rate <= 0
    m_empty = measure_channel_signal([], 1_000_000)
    assert m_empty["state"] == "NO_DATA"
    assert format_measurement_results(m_empty)["state"] == "No Data"

    # 3.2. Constant HIGH và Constant LOW
    m_hi = measure_channel_signal(np.ones(1000, dtype=np.uint8), 1_000_000)
    assert m_hi["state"] == "CONSTANT_HIGH" and m_hi["duty_mean"] == 100.0
    m_lo = measure_channel_signal(np.zeros(1000, dtype=np.uint8), 1_000_000)
    assert m_lo["state"] == "CONSTANT_LOW" and m_lo["duty_mean"] == 0.0

    # 3.3. Chỉ có đúng 1 sườn lên duy nhất (Single Edge -> không có chu kỳ hoàn chỉnh, không chia cho 0)
    single_edge = np.array([0] * 500 + [1] * 500, dtype=np.uint8)
    m_se = measure_channel_signal(single_edge, 1_000_000)
    assert m_se["state"] == "TOGGLING"
    assert m_se["num_transitions"] == 1 and m_se["freq_mean"] == 0.0
    fmt_se = format_measurement_results(m_se)
    assert fmt_se["freq"] == "N/A" and fmt_se["period"] == "N/A"

    # 3.4. Xung đơn (1 sườn lên + 1 sườn xuống -> có t_high nhưng chưa đủ 2 sườn lên để tính Period)
    single_pulse = np.array([0] * 200 + [1] * 100 + [0] * 200, dtype=np.uint8)
    m_sp = measure_channel_signal(single_pulse, 1_000_000)
    assert abs(m_sp["thigh_mean"] - 100e-6) < 1e-9
    assert m_sp["freq_mean"] == 0.0

    # 3.5. Xung PWM chuẩn: f = 10 kHz (100 mẫu @ 1 MHz), Duty = 25% (25 mẫu HIGH, 75 mẫu LOW)
    pwm_25 = np.tile(np.array([1] * 25 + [0] * 75, dtype=np.uint8), 50)
    m_pwm = measure_channel_signal(pwm_25, 1_000_000)
    assert abs(m_pwm["freq_mean"] - 10_000.0) < 1e-3
    assert abs(m_pwm["duty_mean"] - 25.0) < 1e-3
    assert abs(m_pwm["thigh_mean"] - 25e-6) < 1e-9
    assert abs(m_pwm["tlow_mean"] - 75e-6) < 1e-9
    print("  [3.1-3.5] Measurements (Empty, Flat High/Low, Single Edge, Single Pulse, 25% PWM 10kHz): PASS")

    # 3.6. Exporter với dữ liệu thiếu/hỏng và VCD trên kênh phẳng (0 transitions) vs kênh dao động mạnh
    assert export_csv({}, "/tmp/should_not_exist.csv") is False
    assert export_vcd({}, "/tmp/should_not_exist.vcd") is False

    flat_data = {
        "channels": [np.zeros(1024, dtype=np.uint8) for _ in range(8)],
        "sample_rate": 6_000_000.0,
        "sample_count": 1024,
        "trig_offset": 0,
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        vcd_flat = os.path.join(tmpdir, "flat.vcd")
        assert export_vcd(flat_data, vcd_flat) is True
        with open(vcd_flat, "r", encoding="utf-8") as f:
            vcd_txt = f.read()
        # Kênh phẳng hoàn toàn chỉ có mốc #0 ban đầu, không có mốc # nào khác sau $end
        after_dumpvars = vcd_txt.split("$dumpvars")[1].split("$end")[1].strip()
        assert after_dumpvars == "", f"File VCD phẳng không được sinh thêm sự kiện: {after_dumpvars}"
    print("  [3.6] Exporter (Từ chối dict rỗng, VCD nén 0 byte sự kiện cho kênh phẳng ở 6 MHz): PASS")


# ==============================================================================
# NHÓM 4: WAVEFORM WIDGET & MAIN WINDOW GUI CORNER CASES
# ==============================================================================
def test_4_gui_and_waveform_corner_cases():
    print("\n[GROUP 4] Kiểm thử Giao diện MainWindow & WaveformWidget (Corner Cases)...")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = MainWindow(load_sample_on_start=True)

    # 4.1. Kiểm tra định dạng SI tại các giá trị biên (0, số âm, ns, µs, ms, s, inf)
    assert format_si_time(0.0) == "0.0 ns"
    assert "-" in format_si_time(-1.5e-3) and "ms" in format_si_time(-1.5e-3)
    assert format_si_freq(0.0) == "-- Hz"
    assert format_si_freq(-10.0) == "-- Hz"
    assert format_si_freq(float("inf")) == "-- Hz"
    assert "MHz" in format_si_freq(6_000_000.0)

    # 4.2. Kiểm tra Hardware Sample Points (Loại A) chỉ hiện khi Zoom sâu (>= 6 px/sample)
    # Khi Zoom toàn cảnh (32.768 mẫu): chấm phần cứng phải ẩn hoàn toàn
    win.waveform.zoom_fit()
    win.waveform._update_hardware_sample_points()
    assert all(not sp.isVisible() for sp in win.waveform.sample_points_items), (
        "Lỗi: Hardware Sample Points không được hiển thị khi đang Zoom xa!"
    )

    # Khi Zoom cực sâu (chỉ nhìn 20 mẫu = 20 µs trên màn hình rộng ~800px -> ~40 px/sample): chấm phần cứng phải hiện
    win.waveform.plot_widget.resize(800, 500)
    win.waveform.plot_widget.setXRange(0.0, 20e-6, padding=0)
    win.waveform._update_hardware_sample_points()
    assert win.waveform.sample_points_items[0].isVisible() is True, (
        "Lỗi: Hardware Sample Points phải hiển thị khi Zoom sâu >= 6 px/sample!"
    )
    x_pts, _ = win.waveform.sample_points_items[0].getData()
    assert len(x_pts) >= 15 and abs((x_pts[1] - x_pts[0]) - 1e-6) < 1e-12, (
        "Khoảng cách giữa 2 chấm mẫu phần cứng ở 1 MHz phải đúng bằng 1 µs!"
    )
    print("  [4.1-4.2] Hardware Sample Points (Ẩn khi Zoom xa, Hiện chuẩn Δt = 1 µs khi Zoom sâu): PASS")

    # 4.3. Kiểm tra 3 trạng thái Banner & Vạch Trigger: Triggered (0), Free-run (1), Timeout (2)
    for st_code in (0, 1, 2):
        d = dict(win.current_data)
        d["status"] = st_code
        d["trig_offset"] = 6554
        win._render_capture_data(d)
        assert win.waveform.trigger_line.isVisible() is True
        if st_code == 0:
            assert abs(win.waveform.trigger_line.value() - 0.0) < 1e-12
            assert win.waveform.trigger_line.label.toPlainText() == "T"
        elif st_code == 1:
            expected_freerun_pos = 6554 / float(d["sample_rate"])
            assert abs(win.waveform.trigger_line.value() - expected_freerun_pos) < 1e-9
            assert win.waveform.trigger_line.label.toPlainText() == "FREE-RUN"
        elif st_code == 2:
            expected_timeout_pos = 6554 / float(d["sample_rate"])
            assert abs(win.waveform.trigger_line.value() - expected_timeout_pos) < 1e-9
            assert win.waveform.trigger_line.label.toPlainText() == "TIMEOUT"
    print("  [4.3] Hiển thị vạch Trigger chuẩn xác cho cả 3 trạng thái (Triggered=0s 'T', Free-run=t_marker 'FREE-RUN', Timeout='TIMEOUT'): PASS")

    # 4.4. Kiểm tra Quản lý Đa Phiên (Multi-Session Tabs): Tạo tab mới, chuyển tab, đóng tab, không cho đóng tab cuối
    initial_tabs = win.tab_sessions.count()
    win._on_add_session_tab()
    assert win.tab_sessions.count() == initial_tabs + 1
    # Tab mới tạo phải trống (current_data = None)
    assert win.current_data is None
    # Chuyển về tab 0 phải khôi phục lại dữ liệu cũ
    win.tab_sessions.setCurrentIndex(0)
    assert win.current_data is not None
    # Đóng tất cả các tab cho tới khi chỉ còn 1 tab -> thử đóng tiếp vẫn phải giữ lại ít nhất 1 tab
    while win.tab_sessions.count() > 1:
        win._on_close_session_tab(win.tab_sessions.count() - 1)
    win._on_close_session_tab(0)
    assert win.tab_sessions.count() == 1, "Không được phép đóng tab phiên làm việc cuối cùng!"
    print("  [4.4] Quản lý Multi-Session Tabs (Thêm tab, chuyển đổi trạng thái, bảo vệ tab cuối cùng): PASS")

    # 4.5. Kiểm tra Lọc tìm kiếm bảng Data Table (_filter_packet_table) và Điều hướng 2 chiều (Ctrl+Click)
    win._decode_uart()
    total_rows = win.table_uart_packets.rowCount()
    assert total_rows == 14
    win._filter_packet_table("0x54")  # Ký tự 'T' (0x54) xuất hiện 2 lần trong 'TEST_LA_2026\r\n'
    visible_rows = [r for r in range(total_rows) if not win.table_uart_packets.isRowHidden(r)]
    assert len(visible_rows) == 2
    win._filter_packet_table("NON_EXISTENT_QUERY_XYZ")
    visible_rows_none = [r for r in range(total_rows) if not win.table_uart_packets.isRowHidden(r)]
    assert len(visible_rows_none) == 0
    win._filter_packet_table("")  # Xóa bộ lọc -> hiện lại đủ 14 dòng
    assert all(not win.table_uart_packets.isRowHidden(r) for r in range(total_rows))

    # Điều hướng Ctrl+Click từ bong bóng thứ 5 sang bảng Data Table
    win._on_bubble_ctrl_clicked(5, win.current_uart_frames[5])
    selected = win.table_uart_packets.selectionModel().selectedRows()
    assert len(selected) == 1 and selected[0].row() == 5
    # Click vào hàng trong bảng với chỉ số ngoài phạm vi không gây crash
    win._on_table_row_clicked(999, 1)
    win._on_bubble_ctrl_clicked(999, {})
    print("  [4.5] Bộ lọc tìm kiếm Data Table & Điều hướng 2 chiều (Ctrl+Click Bubble <-> Row): PASS")

    # 4.6. Kiểm tra Clear Data và gọi các hàm khi current_data = None (Null-safety)
    win._on_clear_capture_data()
    assert win.current_data is None
    assert win.table_uart_packets.rowCount() == 0
    # Gọi toàn bộ các tác vụ khi không có dữ liệu -> phải an toàn 100%, không văng ngoại lệ
    win._decode_uart()
    win._decode_i2c()
    win._decode_spi()
    win._update_automated_measurements()
    win._on_meas_autodetect()
    win.waveform.zoom_fit()
    win.waveform.zoom_to_window(0.0, 0.001)
    print("  [4.6] Null-Safety (Gọi Decode, Measure, Zoom khi current_data = None không gây lỗi): PASS")


if __name__ == "__main__":
    print("=" * 72)
    print(" BẮT ĐẦU CHẠY BỘ KIỂM THỬ TOÀN DIỆN CÁC TEST CASES & CORNER CASES")
    print("=" * 72)
    t_start_all = time.time()
    test_1_client_protocol_corner_cases()
    test_2_decoders_corner_cases()
    test_3_measurements_and_exporter_corner_cases()
    test_4_gui_and_waveform_corner_cases()
    elapsed = time.time() - t_start_all
    print("\n" + "=" * 72)
    print(f" [SUCCESS] TẤT CẢ 4 NHÓM CORNER CASES ĐỀU ĐẠT PASS 100% ({elapsed:.2f}s)!")
    print("=" * 72)
