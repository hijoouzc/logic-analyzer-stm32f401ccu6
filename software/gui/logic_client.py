#!/usr/bin/env python3
"""
software/gui/logic_client.py
Lớp LogicAnalyzerClient kết nối, điều khiển và truyền nhận dữ liệu với STM32 Logic Analyzer.
Tuân thủ 100% tài liệu quy chuẩn spec/protocol.md (Phiên bản v1.0.0).
"""

import os
import time
import struct
import serial
import serial.tools.list_ports
import numpy as np
from typing import List, Tuple, Dict, Any, Optional


class LogicAnalyzerClient:
    """Client giao tiếp USB-CDC Virtual COM Port với STM32 Logic Analyzer."""

    # Bảng quy đổi tần số lấy mẫu (RATE_IDX -> Tần số Hz và nhãn hiển thị)
    RATE_TABLE = [
        {"idx": 0, "freq": 6_000_000, "label": "6 MHz (ARR=13)"},
        {"idx": 1, "freq": 3_000_000, "label": "3 MHz (ARR=27)"},
        {"idx": 2, "freq": 2_000_000, "label": "2 MHz (ARR=41)"},
        {"idx": 3, "freq": 1_000_000, "label": "1 MHz (ARR=83)"},
        {"idx": 4, "freq":   500_000, "label": "500 kHz (ARR=167)"},
        {"idx": 5, "freq":   200_000, "label": "200 kHz (ARR=419)"},
        {"idx": 6, "freq":   100_000, "label": "100 kHz (ARR=839)"},
        {"idx": 7, "freq":    50_000, "label": "50 kHz (ARR=1679)"},
        {"idx": 8, "freq":    10_000, "label": "10 kHz (ARR=8399)"},
    ]

    # Kiểu kích hoạt Trigger (Chuẩn giao thức nhị phân spec/protocol.md)
    TRIG_MODES = [
        {"mode": 0, "name": "Free-run (No Trigger)"},
        {"mode": 1, "name": "Rising Edge (↑)"},
        {"mode": 2, "name": "Falling Edge (↓)"},
    ]

    # Mã phản hồi Control / NAK từ MCU (protocol.md mục 2.2)
    RSP_CODES = {
        0x04: "RSP_PONG",
        0x05: "RSP_ABORTED",
        0xE0: "ERR_CHECKSUM (Command checksum mismatch)",
        0xE1: "ERR_INVALID_RATE (RATE_IDX > 8)",
        0xE2: "ERR_INVALID_TRIG (Channel > 7 or Mode > 2)",
        0xE3: "ERR_BUSY (MCU busy capturing)",
    }

    # Trạng thái trong Header Data Frame (protocol.md mục 2.1)
    STATUS_NAMES = {
        0x00: "Triggered (STATUS_TRIGGER_OK)",
        0x01: "Complete (STATUS_FREERUN_OK)",
        0x02: "Timeout (STATUS_TIMEOUT)",
    }

    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.port_name: str = ""
        self.baudrate: int = 115200
        self.is_offline_mock: bool = False
        self._abort_requested: bool = False

    @property
    def is_connected(self) -> bool:
        return self.is_offline_mock or (self.ser is not None and self.ser.is_open)

    @staticmethod
    def list_ports() -> List[Tuple[str, str]]:
        """
        Quét toàn bộ cổng serial khả dụng trên hệ thống (Linux /dev/ttyACM*, Windows COM*).
        Luôn đính kèm tùy chọn Offline Mock phục vụ kiểm thử không cần mạch thật.
        :return: Danh sách tuple (port_device, port_description)
        """
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append((p.device, f"{p.device} - {p.description}"))
        # Luôn cung cấp cổng ảo Offline Mock ở cuối danh sách
        result.append(("OFFLINE_MOCK", "Offline Mock (sample_data_1mhz.bin)"))
        return result

    def connect(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> Tuple[bool, str]:
        """
        Mở kết nối serial tới cổng được chỉ định hoặc kích hoạt chế độ Offline Mock.
        """
        self.disconnect()
        if port == "OFFLINE_MOCK":
            self.is_offline_mock = True
            self.port_name = port
            self.baudrate = baudrate
            return True, "Đã kết nối chế độ Offline Mock (sample_data_1mhz.bin)"

        try:
            self.ser = serial.Serial(port, baudrate=baudrate, timeout=0.1)
            self.port_name = port
            self.baudrate = baudrate
            self.is_offline_mock = False
            self._abort_requested = False
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.05)
            return True, f"Đã kết nối thành công tới {port}"
        except Exception as e:
            self.ser = None
            self.is_offline_mock = False
            return False, f"Không thể mở cổng {port}: {e}"

    def disconnect(self):
        """Đóng kết nối serial an toàn."""
        self.is_offline_mock = False
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.port_name = ""

    def _read_exact(self, count: int, timeout_s: float = 2.0) -> bytearray:
        """Đọc chính xác đúng số byte yêu cầu từ cổng serial với timeout."""
        buf = bytearray()
        if not self.ser:
            return buf
        t0 = time.time()
        orig_timeout = self.ser.timeout
        self.ser.timeout = 0.1
        try:
            while len(buf) < count:
                if time.time() - t0 > timeout_s:
                    break
                chunk = self.ser.read(count - len(buf))
                if chunk:
                    buf.extend(chunk)
        finally:
            self.ser.timeout = orig_timeout
        return buf

    def ping(self) -> Tuple[bool, str]:
        """
        Gửi lệnh CMD_PING (0x03) và chờ phản hồi RSP_PONG (0x04) 7 Bytes.
        :return: (Thành công: bool, Chuỗi phiên bản hoặc thông báo lỗi)
        """
        if not self.is_connected:
            return False, "Chưa kết nối cổng serial!"

        if self.is_offline_mock:
            return True, "v1.0.0-offline"

        try:
            # Lệnh PING 5B: [0xA5, 0x03, 0x00, 0x00, 0xA6]
            # Checksum = 0xA5 ^ 0x03 ^ 0x00 ^ 0x00 = 0xA6
            cmd = bytes([0xA5, 0x03, 0x00, 0x00, 0xA6])
            self.ser.reset_input_buffer()
            self.ser.write(cmd)
            self.ser.flush()

            resp = self._read_exact(7, timeout_s=2.0)
            if len(resp) != 7:
                return False, f"Không nhận đủ 7 Bytes phản hồi PING (nhận được {len(resp)}B)"

            if resp[0] != 0x5A or resp[1] != 0xA5:
                return False, f"Sai Magic Header phản hồi: 0x{resp[0]:02X} 0x{resp[1]:02X}"

            code = resp[2]
            if code == 0x04:
                # Kiểm tra Checksum Control Frame: XOR 6 bytes đầu
                calc_csum = resp[0] ^ resp[1] ^ resp[2] ^ resp[3] ^ resp[4] ^ resp[5]
                if resp[6] != calc_csum:
                    return False, f"Sai Checksum phản hồi PONG: nhận 0x{resp[6]:02X}, tính 0x{calc_csum:02X}"
                version_str = f"v{resp[3]}.{resp[4]}.{resp[5]}"
                return True, version_str
            else:
                err_desc = self.RSP_CODES.get(code, f"Mã phản hồi lạ 0x{code:02X}")
                return False, f"Phản hồi không phải PONG: {err_desc}"
        except Exception as e:
            return False, f"Lỗi ngoại lệ khi PING: {e}"

    def send_ping(self) -> Tuple[bool, str]:
        """Bí danh chuẩn thương mại cho ping()."""
        return self.ping()

    def request_abort(self):
        """Đặt cờ yêu cầu hủy thu thập an toàn từ luồng GUI."""
        self._abort_requested = True

    def abort(self) -> Tuple[bool, str]:
        """
        Gửi lệnh CMD_ABORT (0x02) dừng khẩn cấp capture và reset FSM về IDLE.
        """
        self._abort_requested = True
        if not self.is_connected:
            return False, "Chưa kết nối cổng serial!"

        if self.is_offline_mock:
            return True, "Đã hủy chế độ Offline Mock an toàn."

        try:
            # Lệnh ABORT 5B: [0xA5, 0x02, 0x00, 0x00, 0xA7]
            # Checksum = 0xA5 ^ 0x02 ^ 0x00 ^ 0x00 = 0xA7
            cmd = bytes([0xA5, 0x02, 0x00, 0x00, 0xA7])
            self.ser.write(cmd)
            self.ser.flush()

            resp = self._read_exact(7, timeout_s=1.0)
            if len(resp) == 7 and resp[0] == 0x5A and resp[1] == 0xA5 and resp[2] == 0x05:
                return True, "Đã gửi lệnh ABORT và MCU đã khôi phục về IDLE an toàn."
            return True, "Đã phát lệnh ABORT (MCU không phản hồi khung 7B nhưng đã reset luồng)."
        except Exception as e:
            return False, f"Lỗi khi gửi ABORT: {e}"

    def send_abort(self) -> bool:
        """Bí danh chuẩn thương mại cho abort() trả về boolean."""
        ok, _ = self.abort()
        return ok

    def start_capture(
        self,
        rate_idx: int = 3,
        trig_ch: int = 0,
        trig_mode: int = 0,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Gửi lệnh CMD_START và nhận trọn vẹn gói Data Frame 32.776 Bytes theo protocol.md.
        Hỗ trợ cả kết nối thực tế qua serial và chế độ giả lập Offline Mock.
        """
        if not self.is_connected:
            return {"success": False, "error": "Chưa kết nối cổng serial!"}

        if not (0 <= rate_idx <= 8):
            return {"success": False, "error": f"RATE_IDX không hợp lệ: {rate_idx} (phải từ 0 đến 8)"}
        if not (0 <= trig_ch <= 7):
            return {"success": False, "error": f"Trigger Channel không hợp lệ: {trig_ch} (phải từ 0 đến 7)"}
        if not (0 <= trig_mode <= 2):
            return {"success": False, "error": f"Trigger Mode không hợp lệ: {trig_mode} (phải từ 0 đến 2)"}

        sample_rate = self.RATE_TABLE[rate_idx]["freq"]

        # 0. Nếu đang ở chế độ Offline Mock: đọc tệp mẫu có sẵn
        if self.is_offline_mock:
            bin_path = os.path.join(os.path.dirname(__file__), "..", "tests", "sample_data_1mhz.bin")
            res = self.load_offline_file(bin_path)
            if res.get("success"):
                res["sample_rate"] = float(sample_rate)
            return res

        # 1. Tính toán thời gian chờ an toàn (protocol.md mục 4.3):
        # T_gui-timeout = 42598 / f_s + 3.5 s
        timeout_gui = (42598.0 / sample_rate) + 3.5

        # 2. Đóng gói lệnh CMD_START (5 Bytes):
        # Byte 0: 0xA5
        # Byte 1: 0x01 (CMD_START)
        # Byte 2: RATE_IDX (0..8)
        # Byte 3: TRIG_CFG = (trig_ch << 4) | (trig_mode & 0x0F)
        # Byte 4: Checksum = B0 ^ B1 ^ B2 ^ B3
        trig_cfg = ((trig_ch & 0x07) << 4) | (trig_mode & 0x0F)
        checksum = 0xA5 ^ 0x01 ^ rate_idx ^ trig_cfg
        cmd_bytes = bytes([0xA5, 0x01, rate_idx, trig_cfg, checksum])

        # 3. Gửi lệnh
        self._abort_requested = False
        try:
            self.ser.reset_input_buffer()
            self.ser.write(cmd_bytes)
            self.ser.flush()
        except Exception as e:
            return {"success": False, "error": f"Không thể gửi lệnh START: {e}"}

        t_start = time.time()

        # 4. Đón nhận gói tin bằng thuật toán quét trượt (Sliding Window Frame Dispatcher)
        # protocol.md mục 4.1: Tìm cặp đồng bộ 0x5A, 0xA5 -> Đọc 7 Bytes đầu
        raw_7b = bytearray()
        while len(raw_7b) < 7:
            if self._abort_requested:
                self.abort()
                return {"success": False, "error": "Đã hủy thu thập dữ liệu theo yêu cầu người dùng."}
            if time.time() - t_start > timeout_gui:
                return {
                    "success": False,
                    "error": f"Hết thời gian chờ phản hồi ({timeout_gui:.2f} s) mà chưa nhận được Header!"
                }
            byte_in = self.ser.read(1)
            if not byte_in:
                continue
            raw_7b.extend(byte_in)
            # Kiểm tra 2 byte đầu có phải 0x5A, 0xA5
            if len(raw_7b) >= 2 and (raw_7b[0] != 0x5A or raw_7b[1] != 0xA5):
                raw_7b.pop(0)

        # Kiểm tra Byte 2 (Status / RSP_CODE)
        code = raw_7b[2]

        # Ca 1: Nhận Control Frame / NAK (7 Bytes)
        if code in (0x04, 0x05, 0xE0, 0xE1, 0xE2, 0xE3):
            csum = raw_7b[6]
            calc_csum = raw_7b[0] ^ raw_7b[1] ^ raw_7b[2] ^ raw_7b[3] ^ raw_7b[4] ^ raw_7b[5]
            if csum != calc_csum:
                return {
                    "success": False,
                    "error": f"Sai Checksum Control Frame: nhận 0x{csum:02X}, tính 0x{calc_csum:02X}"
                }
            err_msg = self.RSP_CODES.get(code, f"Lỗi Control Frame mã 0x{code:02X}")
            return {
                "success": False,
                "error": f"MCU từ chối lệnh: {err_msg} (Echo={raw_7b[3]:#x},{raw_7b[4]:#x},{raw_7b[5]:#x})"
            }

        # Ca 2: Nhận Data Frame (32.776 Bytes)
        # Byte 2 phải là 0x00 (TRIGGER_OK), 0x01 (FREERUN_OK), hoặc 0x02 (TIMEOUT)
        if code not in (0x00, 0x01, 0x02):
            return {
                "success": False,
                "error": f"Mã trạng thái Data Frame không hợp lệ: 0x{code:02X} (Nhận: {[hex(b) for b in raw_7b]})"
            }

        status = code
        trig_offset = raw_7b[3] | (raw_7b[4] << 8)
        sample_count = raw_7b[5] | (raw_7b[6] << 8)

        # Đọc tiếp chính xác 32.769 Bytes còn lại (32.768B Payload + 1B Footer XOR)
        remaining_count = 32769
        rest_data = bytearray()
        while len(rest_data) < remaining_count:
            if self._abort_requested:
                self.abort()
                return {"success": False, "error": "Đã hủy thu thập dữ liệu theo yêu cầu người dùng."}
            if time.time() - t_start > timeout_gui + 2.0:
                return {
                    "success": False,
                    "error": f"Hết thời gian truyền USB: mới nhận được {len(rest_data)}/{remaining_count} Bytes payload!"
                }
            chunk = self.ser.read(min(4096, remaining_count - len(rest_data)))
            if chunk:
                rest_data.extend(chunk)
                if progress_callback:
                    progress_callback(len(rest_data), remaining_count)

        elapsed_s = time.time() - t_start

        payload_bytes = rest_data[:32768]
        footer_csum = rest_data[32768]

        # Kiểm tra Checksum XOR của toàn bộ 32KB payload bằng NumPy vectorization
        payload_np = np.frombuffer(payload_bytes, dtype=np.uint8)
        calc_csum = int(np.bitwise_xor.reduce(payload_np))

        checksum_ok = (calc_csum == footer_csum)
        if not checksum_ok:
            return {
                "success": False,
                "error": f"Sai lệch Footer XOR Checksum: nhận 0x{footer_csum:02X}, tính 0x{calc_csum:02X}!"
            }

        # Tách riêng 8 kênh tín hiệu số (D0 đến D7) từ mảng payload
        # Kênh n tương ứng với bit thứ n của từng byte mẫu
        channels = [((payload_np >> ch) & 1).astype(np.uint8) for ch in range(8)]

        return {
            "success": True,
            "error": "",
            "status": status,
            "status_name": self.STATUS_NAMES.get(status, f"Status 0x{status:02X}"),
            "trig_offset": trig_offset,
            "sample_count": sample_count,
            "sample_rate": sample_rate,
            "payload": payload_np,
            "channels": channels,
            "elapsed_s": elapsed_s,
            "checksum_ok": checksum_ok
        }

    def send_start(
        self,
        rate_idx: int = 3,
        trig_ch: int = 0,
        trig_mode: int = 0
    ) -> Tuple[int, int, int, np.ndarray, bool]:
        """
        Bí danh chuẩn thương mại trả về tuple (status, trig_offset, sample_count, np_payload, checksum_ok).
        """
        res = self.start_capture(rate_idx, trig_ch, trig_mode)
        if not res.get("success", False):
            return (0xFF, 0, 0, np.array([], dtype=np.uint8), False)
        return (
            res["status"],
            res["trig_offset"],
            res["sample_count"],
            res["payload"],
            res["checksum_ok"]
        )

    def load_offline_file(self, filepath: str) -> Dict[str, Any]:
        """
        Nạp file dữ liệu mẫu offline .bin (chuẩn 32.776 Bytes) phục vụ kiểm thử không cần phần cứng.
        """
        if not os.path.exists(filepath):
            return {"success": False, "error": f"Tệp không tồn tại: {filepath}"}

        try:
            with open(filepath, "rb") as f:
                data = f.read()

            if len(data) != 32776:
                return {"success": False, "error": f"Kích thước tệp không hợp lệ: {len(data)} != 32.776 Bytes"}

            if data[0] != 0x5A or data[1] != 0xA5:
                return {"success": False, "error": "Sai Sync Magic: 2 byte đầu không phải 0x5A, 0xA5"}

            status = data[2]
            trig_offset = data[3] | (data[4] << 8)
            sample_count = data[5] | (data[6] << 8)
            payload_bytes = data[7:32775]
            footer_csum = data[32775]

            # Kiểm tra Checksum XOR bằng NumPy vectorization
            payload_np = np.frombuffer(payload_bytes, dtype=np.uint8)
            calc_csum = int(np.bitwise_xor.reduce(payload_np))

            if calc_csum != footer_csum:
                return {"success": False, "error": f"Sai Checksum: nhận 0x{footer_csum:02X}, tính 0x{calc_csum:02X}"}

            channels = [((payload_np >> ch) & 1).astype(np.uint8) for ch in range(8)]

            return {
                "success": True,
                "error": "",
                "status": status,
                "status_name": self.STATUS_NAMES.get(status, f"Status 0x{status:02X}"),
                "trig_offset": trig_offset,
                "sample_count": sample_count,
                "sample_rate": 1_000_000.0,  # File mẫu mặc định 1 MHz
                "payload": payload_np,
                "channels": channels,
                "elapsed_s": 0.001,
                "checksum_ok": True
            }
        except Exception as e:
            return {"success": False, "error": f"Lỗi đọc tệp offline: {e}"}
