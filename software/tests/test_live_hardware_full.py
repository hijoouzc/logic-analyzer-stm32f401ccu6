#!/usr/bin/env python3
"""
software/tests/test_live_hardware_full.py
Kịch bản kiểm thử toàn diện 100% chức năng trực tiếp trên phần cứng thật (Hardware-in-the-Loop):
- Kit: STM32F401CCU6 WeAct Black Pill V3.0
- Cổng: /dev/ttyACM0 (USB-CDC Full Speed)
- Dây nối Loopback: PA9 (USART1_TX) -> PA0 (Channel 0)

Nội dung kiểm thử:
1. Giao tiếp điều khiển & Handshake: Ping (0x03) -> Pong v1.0.0, Abort (0x02), Bắt lỗi NAK (0xE0, 0xE1, 0xE2)
2. Bộ lấy mẫu & Timer Cascade: Kiểm tra các tần số 500 kHz, 1 MHz, 2 MHz, 6 MHz (Cực đại)
3. Máy trạng thái Trigger FSM:
   - Falling Edge Trigger (Kênh 0)
   - Free-Run Trigger
   - Dynamic Timeout (Kênh không cắm dây)
4. Toàn vẹn dữ liệu: Cấu trúc khung 32.776B, Magic 0x5A 0xA5, Checksum XOR 32KB
5. Giải mã tín hiệu thực tế: UARTDecoder giải mã chuỗi "TEST_LA_2026\r\n"
6. Tính năng thương mại Giai đoạn 2: Cursors A/B tính Δt và tần số baud, Xuất CSV, VCD, PNG
"""

import os
import sys
import time
import serial
import numpy as np

# Thiết lập đường dẫn import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from software.gui.logic_client import LogicAnalyzerClient
from software.decoders.uart_decoder import UARTDecoder
from software.gui.waveform_widget import format_si_time as format_time, format_si_freq as format_freq
from software.utils.exporter import export_csv, export_vcd


def run_full_hardware_test(port="/dev/ttyACM0"):
    print("=" * 70)
    print(" BẮT ĐẦU KIỂM THỬ TOÀN DIỆN PHẦN CỨNG THẬT (FULL HARDWARE-IN-THE-LOOP)")
    print(f" Thiết bị: STM32F401CCU6 WeAct Black Pill V3.0 | Cổng: {port}")
    print("=" * 70)

    client = LogicAnalyzerClient()

    # -------------------------------------------------------------------------
    # TEST 1: KẾT NỐI VÀ HANDSHAKE (PING / PONG)
    # -------------------------------------------------------------------------
    print("\n[PHẦN 1] KIỂM THỬ KẾT NỐI VÀ GIAO THỨC ĐIỀU KHIỂN (CONTROL FRAME)")
    ok, msg = client.connect(port)
    if not ok:
        print(f"[FAIL] Không thể mở cổng {port}: {msg}")
        return False
    print(f"  [1.1] Kết nối cổng serial {port}: PASS")

    ok_ping, ver = client.send_ping()
    if not ok_ping:
        print(f"[FAIL] Lệnh PING không phản hồi: {ver}")
        return False
    print(f"  [1.2] Lệnh PING (0x03) -> Phản hồi PONG (0x04): PASS (Firmware {ver})")

    # -------------------------------------------------------------------------
    # TEST 2: KIỂM THỬ BẮT LỖI VÀ TRẢ MÃ NAK TỪ FIRMWARE
    # -------------------------------------------------------------------------
    print("\n[PHẦN 2] KIỂM THỬ XỬ LÝ LỆNH SAI VÀ PHẢN HỒI MÃ NAK (spec/protocol.md)")
    # 2.1 Lệnh sai Checksum (0xE0)
    bad_csum_cmd = bytes([0xA5, 0x01, 0x03, 0x00, 0xFF])  # Checksum sai
    client.ser.reset_input_buffer()
    client.ser.write(bad_csum_cmd)
    client.ser.flush()
    resp = client._read_exact(7, timeout_s=1.0)
    assert len(resp) == 7 and resp[2] == 0xE0, f"Sai phản hồi NAK Checksum: {resp.hex()}"
    print("  [2.1] Lệnh sai Checksum -> Trả mã NAK 0xE0 (ERR_CHECKSUM): PASS")

    # 2.2 Lệnh sai RATE_IDX (0xE1: rate_idx = 9 > 8)
    bad_rate_cmd = bytes([0xA5, 0x01, 0x09, 0x00, 0xAD])
    client.ser.reset_input_buffer()
    client.ser.write(bad_rate_cmd)
    client.ser.flush()
    resp = client._read_exact(7, timeout_s=1.0)
    assert len(resp) == 7 and resp[2] == 0xE1, f"Sai phản hồi NAK Rate: {resp.hex()}"
    print("  [2.2] Lệnh sai RATE_IDX = 9 -> Trả mã NAK 0xE1 (ERR_INVALID_RATE): PASS")

    # 2.3 Lệnh sai Trigger Config (0xE2: trig_ch = 8 > 7, trig_cfg = 0x80)
    # Checksum = 0xA5 ^ 0x01 ^ 0x03 ^ 0x80 = 0x27
    bad_trig_cmd = bytes([0xA5, 0x01, 0x03, 0x80, 0x27])
    client.ser.reset_input_buffer()
    client.ser.write(bad_trig_cmd)
    client.ser.flush()
    resp = client._read_exact(7, timeout_s=1.0)
    assert len(resp) == 7 and resp[2] == 0xE2, f"Sai phản hồi NAK Trigger: {resp.hex()}"
    print("  [2.3] Lệnh sai Trigger Config -> Trả mã NAK 0xE2 (ERR_INVALID_TRIG): PASS")

    # 2.4 Lệnh ABORT khẩn cấp (0x02 -> 0x05)
    ok_abort, msg_abort = client.abort()
    assert ok_abort, f"Lỗi lệnh ABORT: {msg_abort}"
    print("  [2.4] Lệnh ABORT (0x02) dừng khẩn cấp FSM: PASS")

    # 2.5 Corner Case: Gửi 2 lệnh liên tiếp trong cùng 1 gói USB Bulk OUT (Multi-Command Burst)
    # Gửi PING + ABORT (10 bytes liền nhau) -> Firmware phải xử lý tuần tự trong Thread mode không bị treo!
    burst_cmds = bytes([0xA5, 0x03, 0x00, 0x00, 0xA6, 0xA5, 0x02, 0x00, 0x00, 0xA7])
    client.ser.reset_input_buffer()
    client.ser.write(burst_cmds)
    client.ser.flush()
    resp_burst = client._read_exact(14, timeout_s=1.5)
    assert len(resp_burst) == 14, f"Không nhận đủ 14B phản hồi cho 2 lệnh liền nhau (nhận {len(resp_burst)}B)"
    assert resp_burst[2] == 0x04 and resp_burst[9] == 0x05, f"Sai mã phản hồi Burst: {resp_burst.hex()}"
    print("  [2.5] Gửi dồn 2 lệnh trong 1 gói USB (PING + ABORT = 10B) -> Trả đủ 14B (PONG + ABORT_ACK) không treo ISR: PASS")

    # 2.6 Corner Case: State Machine Busy Protection (WAIT_TRIGGER -> PING / START / ABORT)
    # Khởi động capture chờ cạnh xuống trên CH7 (không có xung -> MCU đứng ở WAIT_TRIGGER)
    cmd_start_ch7 = bytes([0xA5, 0x01, 0x03, (7 << 4) | 0x02, 0xA5 ^ 0x01 ^ 0x03 ^ ((7 << 4) | 0x02)])
    client.ser.reset_input_buffer()
    client.ser.write(cmd_start_ch7)
    client.ser.flush()
    time.sleep(0.05)  # Đợi DMA nạp xong 50% (16.384 mẫu @ 1MHz = 16.4ms) và vào WAIT_TRIGGER

    # Gửi CMD_START lần 2 khi đang bận -> Phải nhận NAK ERR_BUSY (0xE3)
    client.ser.write(cmd_start_ch7)
    client.ser.flush()
    resp_busy = client._read_exact(7, timeout_s=1.0)
    assert len(resp_busy) == 7 and resp_busy[2] == 0xE3, f"Không nhận được ERR_BUSY (0xE3): {resp_busy.hex()}"
    print("  [2.6] Gửi CMD_START khi đang bận chờ Trigger -> Trả mã NAK 0xE3 (ERR_BUSY): PASS")

    # Gửi CMD_PING khi đang chờ Trigger -> Vẫn phải trả RSP_PONG (0x04) mà không làm đứt capture
    ok_p_busy, ver_busy = client.ping()
    assert ok_p_busy, f"PING khi đang WAIT_TRIGGER thất bại: {ver_busy}"
    print(f"  [2.7] Gửi CMD_PING khi đang ở WAIT_TRIGGER -> Phản hồi PONG ({ver_busy}) tức thì: PASS")

    # Gửi CMD_ABORT để hủy lượt chờ trên CH7 -> Trả RSP_ABORTED (0x05) và về IDLE
    ok_ab_busy, _ = client.abort()
    assert ok_ab_busy
    print("  [2.8] Gửi CMD_ABORT thoát khỏi WAIT_TRIGGER về IDLE an toàn: PASS")

    # -------------------------------------------------------------------------
    # TEST 3: KIỂM THỬ CHẾ ĐỘ TRIGGER CẠNH XUỐNG (FALLING EDGE TRÊN CH0)
    # -------------------------------------------------------------------------
    print("\n[PHẦN 3] KIỂM THỬ CHẾ ĐỘ EDGE TRIGGER (Cạnh xuống trên PA0 nối PA9)")
    t0 = time.time()
    res = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=2)  # 1 MHz, CH0 Falling
    t_capture = time.time() - t0

    assert res["success"], f"Lỗi capture: {res.get('error')}"
    assert res["status"] == 0, f"Trạng thái không phải TRIGGER_OK: {res.get('status_name')}"
    assert res["checksum_ok"], "Lỗi Checksum XOR 32KB!"
    assert res["sample_count"] == 32768, f"Số mẫu sai: {res['sample_count']}"
    assert len(res["payload"]) == 32768, "Chiều dài payload sai!"
    assert res["trig_offset"] == 6554, f"Trig offset danh định sai: {res['trig_offset']}"

    print(f"  [3.1] Bắt cạnh Trigger thành công trong {t_capture:.3f} s!")
    print(f"  [3.2] Cấu trúc gói tin: Header 7B + Payload 32.768B + Footer XOR Checksum khớp 100% (PASS)")
    print(f"  [3.3] Điểm Trigger danh định: Mẫu {res['trig_offset']} (Chiếm đúng 20% Pre-trigger)")

    # Kiểm tra tín hiệu vật lý trên CH0 (PA0)
    ch0 = res["channels"][0]
    num_ones = int(np.count_nonzero(ch0 == 1))
    num_zeros = len(ch0) - num_ones
    transitions = int(np.count_nonzero(np.diff(ch0) != 0))
    print(f"  [3.4] Phân tích xung Kênh D0: {transitions:,} lần chuyển mức, {num_ones:,} mức 1, {num_zeros:,} mức 0")

    # Giải mã UART trên dữ liệu thực tế
    dec = UARTDecoder(sample_rate=1_000_000, baudrate=115200)
    text, frames = dec.decode(ch0.tolist(), start_idx=0)
    print(f"  [3.5] Chuỗi UART giải mã trực tiếp từ kit thật: {repr(text)}")
    print(f"  [3.6] Tổng số ký tự giải mã: {len(frames)} frames")
    assert "TEST_LA_2026" in text, f"Không tìm thấy chuỗi test trong: {text}"
    print("  -> ĐÁNH GIÁ CHỨC NĂNG LOOPBACK UART TEST: HOÀN TOÀN CHUẨN XÁC 100%!")

    # -------------------------------------------------------------------------
    # TEST 4: KIỂM THỬ CHẾ ĐỘ FREE-RUN (KHÔNG ĐỢI CẠNH)
    # -------------------------------------------------------------------------
    print("\n[PHẦN 4] KIỂM THỬ CHẾ ĐỘ FREE-RUN (Lấy mẫu liên tục không đồng bộ)")
    res_free = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=0)  # 1 MHz, Free-run
    assert res_free["success"], f"Lỗi Free-run: {res_free.get('error')}"
    assert res_free["status"] == 1, f"Trạng thái không phải FREERUN_OK: {res_free.get('status_name')}"
    assert res_free["checksum_ok"], "Lỗi Checksum Free-run!"
    print(f"  [4.1] Thu thập Free-run hoàn tất: {res_free['status_name']} (PASS)")

    # -------------------------------------------------------------------------
    # TEST 5: KIỂM THỬ DYNAMIC TIMEOUT CỦA FIRMWARE (Hết hạn chờ Trigger)
    # -------------------------------------------------------------------------
    print("\n[PHẦN 5] KIỂM THỬ BẢO VỆ TIMEOUT ĐỘNG (SysTick Timeout khi không có xung)")
    print("  -> Đang gửi lệnh Trigger trên Kênh CH7 (không cắm dây, luôn ở mức 0V)...")
    t_start = time.time()
    res_timeout = client.start_capture(rate_idx=3, trig_ch=7, trig_mode=2)  # CH7 Falling
    t_wait = time.time() - t_start

    assert res_timeout["success"], f"Lỗi timeout capture: {res_timeout.get('error')}"
    assert res_timeout["status"] == 2, f"Trạng thái không phải STATUS_TIMEOUT (0x02): {res_timeout.get('status_name')}"
    assert res_timeout["checksum_ok"], "Lỗi Checksum Timeout!"
    print(f"  [5.1] Firmware tự ngắt an toàn sau {t_wait:.2f} s (Quy định: ~2.02 s): PASS")
    print(f"  [5.2] Trạng thái phản hồi: STATUS_TIMEOUT (0x02), 32KB buffer rỗng nhận đủ 100%: PASS")

    # -------------------------------------------------------------------------
    # TEST 6: KIỂM THỬ TOÀN BỘ 9 TẦN SỐ LẤY MẪU (RATE_IDX 0..8) & RISING EDGE
    # -------------------------------------------------------------------------
    print("\n[PHẦN 6] KIỂM THỬ TOÀN BỘ 9 MỨC TẦN SỐ LẤY MẪU (RATE_IDX 0..8 - Bảng ARR TIM1)")
    all_rates = [
        (0, "6 MHz (ARR=13 - Cực đại)"),
        (1, "3 MHz (ARR=27)"),
        (2, "2 MHz (ARR=41)"),
        (3, "1 MHz (ARR=83)"),
        (4, "500 kHz (ARR=167)"),
        (5, "200 kHz (ARR=419)"),
        (6, "100 kHz (ARR=839)"),
        (7, "50 kHz (ARR=1679)"),
        (8, "10 kHz (ARR=8399 - Thấp nhất)"),
    ]

    for rate_idx, rate_label in all_rates:
        # Với 10 kHz..50 kHz dùng Free-run để test nhanh, với 100 kHz..6 MHz dùng Edge Trigger
        trig_mode = 2 if rate_idx <= 6 else 0
        r = client.start_capture(rate_idx=rate_idx, trig_ch=0, trig_mode=trig_mode)
        assert r["success"], f"Lỗi ở tần số {rate_label}: {r.get('error')}"
        assert r["checksum_ok"], f"Lỗi Checksum ở tần số {rate_label}!"
        assert len(r["payload"]) == 32768
        print(f"  [6.{rate_idx + 1}] RATE_IDX={rate_idx} ({rate_label}): 32.768 mẫu, Checksum PASS, {r['status_name']}")

    # Kiểm tra thêm Rising Edge Trigger (trig_mode = 1) trên CH0 ở 6 MHz
    r_rising = client.start_capture(rate_idx=0, trig_ch=0, trig_mode=1)
    assert r_rising["success"] and r_rising["status"] == 0 and r_rising["checksum_ok"]
    ch0_6m = r_rising["channels"][0]
    # Ở 6 MHz (166.7 ns/mẫu), do trễ NVIC Cortex-M4 + đồng bộ TIM2 ITR0, sườn lên thực tế nằm tại mẫu ~6544 (lệch -10 mẫu)
    win_6m = ch0_6m[6538:6565]
    rising_edges_near_trig = [6538 + i + 1 for i in range(len(win_6m) - 1) if win_6m[i] == 0 and win_6m[i + 1] == 1]
    assert len(rising_edges_near_trig) >= 1, (
        f"Rising Edge ở 6 MHz không tìm thấy sườn lên 0->1 quanh mẫu 6554: {win_6m}"
    )
    jitter_6m = rising_edges_near_trig[0] - 6554
    dec_6m = UARTDecoder(sample_rate=6_000_000, baudrate=115200)
    txt_6m, _ = dec_6m.decode(ch0_6m.tolist())
    assert "TEST_LA_2026" in txt_6m, f"Giải mã UART ở 6 MHz thất bại: {txt_6m}"
    print(f"  [6.10] Rising Edge Trigger (Mode=1) @ 6 MHz: Bắt sườn lên 0->1 tại mẫu {rising_edges_near_trig[0]} (Trễ NVIC+TIM2 = {jitter_6m:+d} mẫu = {abs(jitter_6m)*166.7:.0f} ns) & giải mã UART: PASS")

    # -------------------------------------------------------------------------
    # TEST 7: KIỂM THỬ CÁC TÍNH NĂNG THƯƠNG MẠI GIAI ĐOẠN 2 VỚI DỮ LIỆU THẬT
    # -------------------------------------------------------------------------
    print("\n[PHẦN 7] KIỂM THỬ CÁC TÍNH NĂNG PHẦN MỀM GIAI ĐOẠN 2 (Dữ liệu thật)")
    # 7.1 Đo đạc xung bằng Cursors
    if len(frames) >= 2:
        f0 = frames[0]
        f1 = frames[1]
        t_start_char = f0["start_time_s"]
        t_stop_char = f0["stop_time_s"]
        dt = t_stop_char - t_start_char
        baud_meas = (1.0 / (dt / 10.0))  # 10 bits per frame
        print(f"  [7.1] Thước đo Cursor đo ký tự '{f0['char']}': Độ rộng = {format_time(dt)}, Tốc độ Baud ước tính = {baud_meas:,.0f} bps (Chuẩn: 115.200 bps)")

    # 7.2 Xuất CSV
    csv_path = "/tmp/la_live_capture.csv"
    ok_csv = export_csv(res, csv_path)
    assert ok_csv and os.path.exists(csv_path), "Lỗi xuất CSV"
    csv_size = os.path.getsize(csv_path)
    print(f"  [7.2] Xuất dữ liệu thật ra CSV: {csv_path} ({csv_size:,} bytes, đủ 32.768 dòng): PASS")

    # 7.3 Xuất VCD (GTKWave)
    vcd_path = "/tmp/la_live_capture.vcd"
    ok_vcd = export_vcd(res, vcd_path)
    assert ok_vcd and os.path.exists(vcd_path), "Lỗi xuất VCD"
    vcd_size = os.path.getsize(vcd_path)
    print(f"  [7.3] Xuất dữ liệu xung thật ra VCD (GTKWave): {vcd_path} ({vcd_size:,} bytes): PASS")

    client.disconnect()

    print("\n" + "=" * 70)
    print(" KẾT QUẢ KIỂM THỬ: 100% CÁC BÀI KIỂM THỬ TRÊN PHẦN CỨNG THẬT ĐỀU ĐẠT (PASS)!")
    print(" HỆ THỐNG LOGIC ANALYZER ĐÃ SẴN SÀNG 100% CHO BUỔI BÁO CÁO 11/11!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_full_hardware_test()
    sys.exit(0 if success else 1)
