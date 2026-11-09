#!/usr/bin/env python3
"""
software/decoders/spi_decoder.py
Bộ giải mã giao thức SPI (Serial Peripheral Interface) chuẩn công nghiệp 4 chế độ CPOL/CPHA.
Hỗ trợ truyền nhận song công đồng thời (Full-Duplex: MOSI & MISO) kèm chân chọn chip (CS/SS).
"""

from typing import List, Dict, Any, Tuple, Optional
import math


class SPIDecoder:
    """Bộ giải mã SPI Bus Protocol 4 Mode (0, 1, 2, 3)."""

    def __init__(
        self,
        sample_rate: float = 1_000_000.0,
        cpol: int = 0,
        cpha: int = 0,
        bit_order: str = "MSB",
        cs_active: str = "LOW"
    ):
        self.sample_rate = float(sample_rate)
        self.cpol = int(cpol)
        self.cpha = int(cpha)
        self.bit_order = bit_order.upper()
        self.cs_active = cs_active.upper()

    def decode(
        self,
        sck_samples: List[int],
        mosi_samples: Optional[List[int]] = None,
        miso_samples: Optional[List[int]] = None,
        cs_samples: Optional[List[int]] = None,
        start_idx: int = 0,
        end_idx: Optional[int] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Giải mã luồng tín hiệu SPI.

        :param sck_samples: Mảng mức logic kênh SCK (Clock)
        :param mosi_samples: Mảng mức logic kênh MOSI (Master Out Slave In)
        :param miso_samples: Mảng mức logic kênh MISO (Master In Slave Out)
        :param cs_samples: Mảng mức logic kênh CS (Chip Select, tùy chọn)
        :param start_idx: Mẫu bắt đầu giải mã
        :param end_idx: Mẫu kết thúc giải mã
        :return: (Chuỗi văn bản tổng hợp, Danh sách chi tiết các frame)
        """
        if len(sck_samples) == 0 or not math.isfinite(self.sample_rate) or self.sample_rate <= 0:
            return "", []
        if self.cpol not in (0, 1) or self.cpha not in (0, 1) or self.bit_order not in ('MSB', 'LSB') or self.cs_active not in ('LOW', 'HIGH'):
            raise ValueError('Invalid SPI mode, bit order or CS polarity')

        total_len = len(sck_samples)
        if mosi_samples is not None:
            total_len = min(total_len, len(mosi_samples))
        if miso_samples is not None:
            total_len = min(total_len, len(miso_samples))
        if cs_samples is not None:
            total_len = min(total_len, len(cs_samples))

        if end_idx is None or end_idx > total_len:
            end_idx = total_len

        # Xác định cạnh lấy mẫu (Sampling Edge):
        # Mode 0 (CPOL=0, CPHA=0): Cạnh lên (0 -> 1)
        # Mode 1 (CPOL=0, CPHA=1): Cạnh xuống (1 -> 0)
        # Mode 2 (CPOL=1, CPHA=0): Cạnh xuống (1 -> 0)
        # Mode 3 (CPOL=1, CPHA=1): Cạnh lên (0 -> 1)
        sample_on_rising = (self.cpol == self.cpha)

        frames: List[Dict[str, Any]] = []
        mosi_bytes: List[int] = []
        miso_bytes: List[int] = []

        curr_mosi_bits: List[int] = []
        curr_miso_bits: List[int] = []
        byte_start_sample = 0

        i = max(0, start_idx)
        while i < end_idx - 1:
            # 1. Kiểm tra trạng thái CS nếu có kênh CS
            if cs_samples is not None and i < len(cs_samples):
                cs_val = cs_samples[i + 1]
                is_active = (cs_val == 0) if self.cs_active == "LOW" else (cs_val == 1)
                if not is_active:
                    # CS không tích cực -> Reset bộ gom bit
                    curr_mosi_bits = []
                    curr_miso_bits = []
                    i += 1
                    continue

            # 2. Phát hiện cạnh xung nhịp SCK lấy mẫu
            sck_now = sck_samples[i]
            sck_next = sck_samples[i + 1]

            is_sample_edge = False
            if sample_on_rising and sck_now == 0 and sck_next == 1:
                is_sample_edge = True
            elif (not sample_on_rising) and sck_now == 1 and sck_next == 0:
                is_sample_edge = True

            if is_sample_edge:
                sample_pos = i + 1
                if len(curr_mosi_bits) == 0:
                    byte_start_sample = sample_pos

                # Đọc bit MOSI
                mosi_bit = int(mosi_samples[sample_pos]) if mosi_samples is not None else 0
                curr_mosi_bits.append(mosi_bit)

                # Đọc bit MISO
                miso_bit = int(miso_samples[sample_pos]) if miso_samples is not None else 0
                curr_miso_bits.append(miso_bit)

                # Khi đủ 8 bits = 1 Byte
                if len(curr_mosi_bits) == 8:
                    mosi_val = 0
                    miso_val = 0

                    for b in range(8):
                        m_bit = curr_mosi_bits[b]
                        s_bit = curr_miso_bits[b]
                        shift = (7 - b) if (self.bit_order == "MSB") else b
                        mosi_val |= (m_bit << shift)
                        miso_val |= (s_bit << shift)

                    mosi_bytes.append(mosi_val)
                    miso_bytes.append(miso_val)

                    mosi_chr = chr(mosi_val) if (32 <= mosi_val <= 126) else "."
                    miso_chr = chr(miso_val) if (32 <= miso_val <= 126) else "."

                    frames.append({
                        "mosi_val": mosi_val,
                        "miso_val": miso_val,
                        "mosi_hex": f"0x{mosi_val:02X}",
                        "miso_hex": f"0x{miso_val:02X}",
                        "mosi_ascii": mosi_chr,
                        "miso_ascii": miso_chr,
                        "start_sample": byte_start_sample,
                        "stop_sample": sample_pos,
                        "start_time_s": byte_start_sample / self.sample_rate,
                        "stop_time_s": sample_pos / self.sample_rate
                    })

                    curr_mosi_bits = []
                    curr_miso_bits = []

            i += 1

        # Xây dựng chuỗi văn bản tổng hợp
        lines = []
        if mosi_bytes:
            hex_str = " ".join(f"0x{b:02X}" for b in mosi_bytes)
            asc_str = "".join(chr(b) if (32 <= b <= 126) else "." for b in mosi_bytes)
            lines.append(f"MOSI ({len(mosi_bytes)} bytes): {hex_str} | ASCII: '{asc_str}'")
        if miso_bytes:
            hex_str = " ".join(f"0x{b:02X}" for b in miso_bytes)
            asc_str = "".join(chr(b) if (32 <= b <= 126) else "." for b in miso_bytes)
            lines.append(f"MISO ({len(miso_bytes)} bytes): {hex_str} | ASCII: '{asc_str}'")

        decoded_text = "\n".join(lines)
        return decoded_text, frames
