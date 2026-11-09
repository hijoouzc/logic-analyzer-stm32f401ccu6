#!/usr/bin/env python3
"""
software/decoders/i2c_decoder.py
Bộ giải mã giao thức I2C (Inter-Integrated Circuit) chuẩn công nghiệp.
Hỗ trợ: START / Repeated-START, 7-bit Address, R/W bit, ACK/NACK, Data Bytes và STOP.
"""

from typing import List, Dict, Any, Tuple, Optional
import math


class I2CDecoder:
    """Bộ giải mã I2C Bus Protocol."""

    def __init__(self, sample_rate: float = 1_000_000.0):
        self.sample_rate = float(sample_rate)

    def decode(
        self,
        scl_samples: List[int],
        sda_samples: List[int],
        start_idx: int = 0,
        end_idx: Optional[int] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Giải mã luồng tín hiệu I2C từ 2 kênh SCL và SDA.

        :param scl_samples: Mảng mức logic kênh SCL (0 hoặc 1)
        :param sda_samples: Mảng mức logic kênh SDA (0 hoặc 1)
        :param start_idx: Mẫu bắt đầu giải mã (mặc định: 0)
        :param end_idx: Mẫu kết thúc giải mã (mặc định: hết mảng)
        :return: (Chuỗi văn bản tổng hợp, Danh sách chi tiết các frame)
        """
        if len(scl_samples) == 0 or len(sda_samples) == 0 or len(scl_samples) != len(sda_samples) or not math.isfinite(self.sample_rate) or self.sample_rate <= 0:
            return "", []

        total_len = len(scl_samples)
        if end_idx is None or end_idx > total_len:
            end_idx = total_len

        frames: List[Dict[str, Any]] = []
        text_lines: List[str] = []

        in_transaction = False
        expect_address = False
        current_byte_bits: List[int] = []
        byte_start_sample = 0

        current_line_parts: List[str] = []

        i = max(0, start_idx)
        while i < end_idx - 1:
            scl_now, scl_next = scl_samples[i], scl_samples[i + 1]
            sda_now, sda_next = sda_samples[i], sda_samples[i + 1]

            # 1. Nhận diện điều kiện START / Repeated START: SDA rơi từ 1 xuống 0 khi SCL = 1
            if scl_now == 1 and scl_next == 1 and sda_now == 1 and sda_next == 0:
                is_repeated = in_transaction
                in_transaction = True
                expect_address = True
                current_byte_bits = []

                tag = "Sr" if is_repeated else "S"
                desc = "Repeated START" if is_repeated else "START"
                if is_repeated and current_line_parts:
                    text_lines.append(" ".join(current_line_parts))
                    current_line_parts = []

                current_line_parts.append(f"[{tag}]")
                frames.append({
                    "type": "START" if not is_repeated else "REPEATED_START",
                    "val": 0,
                    "desc": desc,
                    "ack": True,
                    "rw": "",
                    "start_sample": max(0, i - 1),
                    "stop_sample": min(end_idx - 1, i + 4),
                    "start_time_s": max(0, i - 1) / self.sample_rate,
                    "stop_time_s": min(end_idx - 1, i + 4) / self.sample_rate
                })
                i += 1
                continue

            # 2. Nhận diện điều kiện STOP: SDA tăng từ 0 lên 1 khi SCL = 1
            if scl_now == 1 and scl_next == 1 and sda_now == 0 and sda_next == 1:
                if in_transaction:
                    current_line_parts.append("[P]")
                    text_lines.append(" ".join(current_line_parts))
                    current_line_parts = []
                    frames.append({
                        "type": "STOP",
                        "val": 0,
                        "desc": "STOP",
                        "ack": True,
                        "rw": "",
                        "start_sample": max(0, i - 1),
                        "stop_sample": min(end_idx - 1, i + 4),
                        "start_time_s": max(0, i - 1) / self.sample_rate,
                        "stop_time_s": min(end_idx - 1, i + 4) / self.sample_rate
                    })
                    in_transaction = False
                    expect_address = False
                    current_byte_bits = []
                i += 1
                continue

            # 3. Lấy mẫu dữ liệu trên cạnh lên của SCL (0 -> 1) khi đang trong giao dịch
            if in_transaction and scl_now == 0 and scl_next == 1:
                sample_edge = i + 1
                bit_val = sda_next

                if len(current_byte_bits) == 0:
                    byte_start_sample = sample_edge

                current_byte_bits.append(bit_val)

                # Khi đã thu đủ 9 bits (8 bits dữ liệu + 1 bit ACK/NACK)
                if len(current_byte_bits) == 9:
                    raw_byte = 0
                    for b in range(8):
                        raw_byte = (raw_byte << 1) | current_byte_bits[b]

                    ack_bit = current_byte_bits[8]
                    is_ack = (ack_bit == 0)
                    ack_str = "ACK" if is_ack else "NACK"

                    if expect_address:
                        # 7-bit Address và R/W
                        addr_7bit = raw_byte >> 1
                        rw_bit = raw_byte & 1
                        rw_str = "Read" if rw_bit else "Write"
                        rw_short = "R" if rw_bit else "W"

                        desc = f"Addr: 0x{addr_7bit:02X} ({rw_short}) [{ack_str}]"
                        current_line_parts.append(desc)

                        frames.append({
                            "type": "ADDRESS",
                            "val": addr_7bit,
                            "desc": f"Addr 0x{addr_7bit:02X} ({rw_str})",
                            "ack": is_ack,
                            "rw": rw_short,
                            "start_sample": byte_start_sample,
                            "stop_sample": sample_edge,
                            "start_time_s": byte_start_sample / self.sample_rate,
                            "stop_time_s": sample_edge / self.sample_rate
                        })
                        expect_address = False
                    else:
                        # Data byte
                        char_rep = chr(raw_byte) if (32 <= raw_byte <= 126) else "."
                        desc = f"Data: 0x{raw_byte:02X} '{char_rep}' [{ack_str}]"
                        current_line_parts.append(f"0x{raw_byte:02X}[{ack_str}]")

                        frames.append({
                            "type": "DATA",
                            "val": raw_byte,
                            "desc": f"Data 0x{raw_byte:02X} ('{char_rep}')",
                            "ack": is_ack,
                            "rw": "",
                            "start_sample": byte_start_sample,
                            "stop_sample": sample_edge,
                            "start_time_s": byte_start_sample / self.sample_rate,
                            "stop_time_s": sample_edge / self.sample_rate
                        })

                    current_byte_bits = []

            i += 1

        if current_line_parts:
            text_lines.append(" ".join(current_line_parts))

        decoded_text = "\n".join(text_lines)
        return decoded_text, frames
