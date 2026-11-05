#!/usr/bin/env python3
"""
software/decoders/uart_decoder.py
Bộ giải mã giao thức UART (Universal Asynchronous Receiver-Transmitter).

Đặc tả kỹ thuật:
- Chuẩn: 8-N-1 (8 Data bits, No parity, 1 Stop bit)
- Hỗ trợ baudrate tùy biến (mặc định: 115.200 bps)
- Thuật toán: Lấy mẫu tại tâm bit (Center-bit sampling)
  - Số mẫu mỗi bit: samples_per_bit = sample_rate / baudrate
  - Dò cạnh xuống (Falling Edge) để xác định Start bit
  - Kiểm tra điều kiện Start bit hợp lệ tại sample_mid = start_edge + 0.5 * samples_per_bit
  - Đọc 8 bit dữ liệu LSB first tại (1.5 + bit_idx) * samples_per_bit
  - Kiểm tra Stop bit tại 9.5 * samples_per_bit (phải ở mức HIGH = 1)
  - Nhảy tới điểm an toàn (9.0 * samples_per_bit) để bắt cạnh xuống của frame tiếp theo
"""

from typing import List, Dict, Any, Tuple, Optional


class UARTDecoder:
    """Bộ giải mã tín hiệu UART từ mảng bit logic của một kênh đo."""

    def __init__(self, sample_rate: float = 1_000_000.0, baudrate: int = 115_200):
        """
        Khởi tạo bộ giải mã UART.
        :param sample_rate: Tần số lấy mẫu của kênh (Hz, e.g. 1_000_000)
        :param baudrate: Tốc độ baud của tín hiệu UART (bps, e.g. 115_200)
        """
        self.sample_rate = float(sample_rate)
        self.baudrate = int(baudrate)

    def decode(
        self,
        samples: List[int],
        start_idx: int = 0,
        end_idx: Optional[int] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Giải mã toàn bộ dữ liệu mẫu thành chuỗi ký tự và danh sách chi tiết các frame.

        :param samples: Mảng mức logic (0 hoặc 1) của kênh cần giải mã
        :param start_idx: Vị trí mẫu bắt đầu giải mã (mặc định: 0)
        :param end_idx: Vị trí mẫu kết thúc giải mã (mặc định: hết mảng)
        :return: Tuple gồm:
                 - text: Chuỗi ký tự ASCII giải mã được (e.g. "TEST_LA_2026\\r\\n")
                 - frames: Danh sách các dict chi tiết từng ký tự:
                   {
                       'char': str,
                       'byte_val': int,
                       'start_sample': int,
                       'stop_sample': int,
                       'start_time_s': float,
                       'stop_time_s': float,
                       'bit_samples': List[int]
                   }
        """
        if not samples or self.baudrate <= 0 or self.sample_rate <= 0:
            return "", []

        total_len = len(samples)
        if end_idx is None or end_idx > total_len:
            end_idx = total_len

        samples_per_bit = self.sample_rate / self.baudrate
        # Nếu sample rate quá thấp (< 2 lần baudrate), vi phạm Nyquist
        if samples_per_bit < 2.0:
            return "[LỖI: Tần số lấy mẫu quá thấp so với Baudrate (Nyquist < 2x)]", []

        decoded_chars: List[str] = []
        frames: List[Dict[str, Any]] = []

        idx = start_idx
        max_idx = end_idx - int(samples_per_bit * 10)  # Cần đủ tối thiểu 10 bit cho 1 frame

        while idx < max_idx:
            # Tìm cạnh xuống từ HIGH (1) về LOW (0) - Start bit
            if samples[idx] == 1 and samples[idx + 1] == 0:
                start_edge = idx + 1
                # Kiểm tra điểm giữa Start bit có thực sự là mức LOW (0)
                start_mid = int(start_edge + samples_per_bit * 0.5)
                if start_mid < end_idx and samples[start_mid] == 0:
                    byte_val = 0
                    valid_byte = True
                    bit_samples = []

                    # Đọc 8 bit dữ liệu (LSB first)
                    bit_positions = []
                    for bit_num in range(8):
                        sample_pos = int(round(start_edge + samples_per_bit * (1.5 + bit_num)))
                        if sample_pos >= end_idx:
                            valid_byte = False
                            break
                        bit_val = samples[sample_pos]
                        bit_samples.append(bit_val)
                        bit_positions.append(sample_pos)
                        byte_val |= (bit_val << bit_num)

                    # Kiểm tra Stop bit (phải ở mức HIGH = 1)
                    stop_pos = int(round(start_edge + samples_per_bit * 9.5))
                    if valid_byte and stop_pos < end_idx and samples[stop_pos] == 1:
                        # Chuyển đổi mã byte sang ký tự ASCII
                        if 32 <= byte_val <= 126 or byte_val in (10, 13, 9):  # printable + \r, \n, \t
                            char_ascii = chr(byte_val)
                        else:
                            char_ascii = f"\\x{byte_val:02X}"

                        decoded_chars.append(char_ascii)

                        # Lưu thông tin frame phục vụ hiển thị trên đồ thị
                        # Chuẩn công nghiệp: Bong bóng dữ liệu ôm đúng 8 Data Bits (1.0 * T_bit -> 9.0 * T_bit)
                        data_start_sample = start_edge + samples_per_bit * 1.0 - 0.5
                        data_end_sample = start_edge + samples_per_bit * 9.0 - 0.5
                        bit_centers = [start_edge + (1.5 + b) * samples_per_bit - 0.5 for b in range(8)]
                        frames.append({
                            "char": char_ascii,
                            "byte_val": byte_val,
                            "start_sample": start_edge,
                            "stop_sample": stop_pos,
                            "data_start_sample": data_start_sample,
                            "data_end_sample": data_end_sample,
                            "bit_positions": bit_positions,
                            "bit_centers": bit_centers,
                            "start_time_s": start_edge / self.sample_rate,
                            "stop_time_s": stop_pos / self.sample_rate,
                            "bit_samples": bit_samples
                        })

                        # Nhảy tới vị trí giữa Stop bit (bit 9), để bộ dò cạnh tự bắt Falling edge kế tiếp
                        idx = int(start_edge + samples_per_bit * 9.0)
                        continue

            idx += 1

        decoded_text = "".join(decoded_chars)
        return decoded_text, frames
