#!/usr/bin/env python3
"""
generate_test_data.py
Tạo file binary giả lập chuẩn software/tests/sample_data_1mhz.bin
Dùng để kiểm thử độc lập GUI và Decoder UART 115200 bps của TV3.
"""

import struct
import numpy as np

def create_sample_bin(filename="software/tests/sample_data_1mhz.bin"):
    SAMPLE_RATE = 1_000_000  # 1 MHz
    BAUDRATE = 115_200
    SAMPLES_PER_BIT = SAMPLE_RATE / BAUDRATE  # ~8.68 mẫu/bit
    TOTAL_SAMPLES = 32_768
    TRIG_OFFSET = 6554
    
    # 1. Khởi tạo mảng payload: mặc định Kênh 0 = 1 (UART Idle), Kênh 1..7 = 0
    # Mỗi byte biểu diễn 8 kênh: bit 0 là Kênh 0, bit 1 là Kênh 1...
    payload = np.full(TOTAL_SAMPLES, 0x01, dtype=np.uint8)
    
    # Chuỗi ký tự test
    TEST_STR = "TEST_LA_2026\r\n"
    
    # Tạo các bit UART cho từng ký tự
    uart_bits = []
    for char in TEST_STR:
        byte_val = ord(char)
        uart_bits.append(0)  # Start bit (LOW)
        for bit_idx in range(8):
            uart_bits.append((byte_val >> bit_idx) & 1)  # LSB first
        uart_bits.append(1)  # Stop bit (HIGH)
    
    # Ghi dạng sóng UART vào mảng payload bắt đầu từ TRIG_OFFSET (6554)
    # Sử dụng bộ tích lũy pha thực (fractional phase accumulator) để không bị trôi Baudrate
    exact_pos = float(TRIG_OFFSET)
    for bit in uart_bits:
        start_sample = int(round(exact_pos))
        exact_pos += SAMPLES_PER_BIT
        end_sample = min(int(round(exact_pos)), TOTAL_SAMPLES)
        payload[start_sample:end_sample] = 0x01 if bit else 0x00
        if end_sample >= TOTAL_SAMPLES:
            break
            
    # Tính XOR Checksum của 32.768 bytes payload
    xor_footer = 0
    for b in payload:
        xor_footer ^= int(b)
        
    # Tạo Header 7 bytes:
    # Magic: 0x5A, 0xA5
    # Status: 0x00 (STATUS_TRIGGER_OK)
    # trig_offset: 6554 (uint16 Little-Endian -> 0x9A, 0x19)
    # sample_count: 32768 (uint16 Little-Endian -> 0x00, 0x80)
    header = struct.pack("<BBHH", 0x5A, 0xA5, 0x00, TRIG_OFFSET) # Chờ: cần đúng 7 bytes
    # Đúng chuẩn 7 bytes Little-Endian:
    # 0x5A, 0xA5, Status (1B), trig_offset (2B), sample_count (2B)
    header_bytes = bytes([0x5A, 0xA5, 0x00, 0x9A, 0x19, 0x00, 0x80])
    
    # Ghép toàn bộ khung truyền 32.776 bytes:
    full_packet = header_bytes + bytes(payload) + bytes([xor_footer])
    
    assert len(full_packet) == 32776, f"Sai kích thước gói tin: {len(full_packet)} != 32776"
    
    with open(filename, "wb") as f:
        f.write(full_packet)
        
    print(f"Đã tạo thành công {filename} (Tổng kích thước: {len(full_packet)} bytes).")
    print(f"Header: {header_bytes.hex(' ')}")
    print(f"Footer XOR Checksum: 0x{xor_footer:02X}")

if __name__ == "__main__":
    create_sample_bin()
