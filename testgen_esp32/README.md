# ESP32 TEST PATTERN GENERATOR CHO STM32 LOGIC ANALYZER

Firmware phát đồng thời 4 loại tín hiệu trên 8 kênh chân GPIO độc lập (3.3V logic) để kiểm thử toàn diện các tính năng của máy phân tích logic:
1. **CH0 (PA0):** UART TX 115.200 bps (`"ESP32_OK\r\n"`).
2. **CH1 & CH2 (PA1, PA2):** I2C Bus 100 kHz (SCL / SDA) ghi địa chỉ `0x3C` và đọc `0x68`.
3. **CH3 .. CH6 (PA3..PA6):** SPI Bus 500 kHz (SCK, MOSI, MISO, CS) gửi `0x9F`, `0x55`, `0xAA`.
4. **CH7 (PA7):** Sóng vuông 500 kHz (PWM 50% duty) kiểm chứng giới hạn Nyquist & Aliasing.

---

## 1. Sơ Đồ Đấu Nối Dây (ESP32 $\leftrightarrow$ STM32F401 Black Pill)

| Chân ESP32 | Chân Black Pill | Kênh LA | Tín hiệu | Ý nghĩa & Dạng sóng kiểm thử |
| :--- | :--- | :---: | :--- | :--- |
| **GND** | **GND** | - | **Chung Mass** | **Bắt buộc phải nối** |
| **GPIO 17** | **PA0** | **CH0** | **UART TX** | Chuỗi `"ESP32_OK\r\n"` (115.200 bps, 8-N-1) |
| **GPIO 22** | **PA1** | **CH1** | **I2C SCL** | Xung Clock I2C 100 kHz |
| **GPIO 21** | **PA2** | **CH2** | **I2C SDA** | Dữ liệu I2C (START, Addr 0x3C, 0x68, ACK, STOP) |
| **GPIO 18** | **PA3** | **CH3** | **SPI SCK** | Xung Clock SPI 500 kHz (Mode 0) |
| **GPIO 23** | **PA4** | **CH4** | **SPI MOSI** | Dữ liệu Master: `0x9F`, `0x55`, `0xAA` |
| **GPIO 19** | **PA5** | **CH5** | **SPI MISO** | Dữ liệu Slave |
| **GPIO 5**  | **PA6** | **CH6** | **SPI CS** | Chip Select (Active Low, chân Trigger chuẩn) |
| **GPIO 16** | **PA7** | **CH7** | **Square Wave** | Sóng vuông 500 kHz (Chu kỳ $2\,\mu\text{s}$) |

---

## 2. Hướng Dẫn Nạp Firmware Cho ESP32

### Cách 1: Nạp Bằng PlatformIO (Khuyên dùng)
Nếu máy tính đã cài `platformio`:
```bash
cd testgen_esp32
pio run -t upload
```

### Cách 2: Nạp Bằng Arduino IDE
1. Cài đặt board **ESP32** trong *Boards Manager* (`esp32 by Espressif Systems`).
2. Mở file `testgen_esp32/src/main.cpp` (hoặc đổi tên thành `testgen_esp32.ino`).
3. Chọn Board: **ESP32 Dev Module**.
4. Chọn đúng cổng COM của ESP32 và nhấn **Upload**.

---

## 3. Hướng Dẫn Đo Kiểm Trên Desktop GUI

Khởi chạy ứng dụng hiển thị:
```bash
python3 software/main.py
```

### Kịch bản A: Kiểm thử I2C (CH1 - SCL, CH2 - SDA)
1. **Trigger:** Chọn kênh **CH2 (SDA)**, kiểu **Falling Edge (Cạnh xuống)**.
2. **Sample Rate:** Chọn **`1 MHz`** hoặc **`2 MHz`**.
3. Bấm **Single Capture** (hoặc **↻ Auto-Repeat**).
4. Menu **Analyzers** $\rightarrow$ chọn **■ I2C**.
5. *Kết quả:* Dạng sóng nổi bong bóng `START`, `ADDR: 0x3C (W)`, `DATA: 0x00`, `DATA: 0xAF`, `STOP` và điền chi tiết vào bảng Data Table.

### Kịch bản B: Kiểm thử SPI (CH3 - SCK, CH4 - MOSI, CH6 - CS)
1. **Trigger:** Chọn kênh **CH6 (CS)**, kiểu **Falling Edge (Cạnh xuống)**.
2. **Sample Rate:** Chọn **`2 MHz`** hoặc **`6 MHz`**.
3. Bấm **Single Capture**.
4. Menu **Analyzers** $\rightarrow$ chọn **■ SPI**.
5. *Kết quả:* Dạng sóng nổi bong bóng `0x9F`, `0x55`, `0xAA` trên kênh MOSI.

### Kịch bản C: Kiểm thử UART (CH0)
1. **Trigger:** Chọn kênh **CH0**, kiểu **Falling Edge** (Start bit).
2. Menu **Analyzers** $\rightarrow$ chọn **■ Async Serial**.
3. *Kết quả:* Hiển thị giải mã chuỗi text: `"ESP32_OK"`.

### Kịch bản D: Kiểm tra tần số sóng vuông (CH7)
* Trên kênh 7, dùng cặp con trỏ **Cursor A** và **Cursor B** đo giữa 2 sườn lên liên tiếp:
  * Khoảng cách thời gian: $\Delta t = 2.000\,\mu\text{s}$.
  * Tần số đo được: $f = 1 / \Delta t = 500.00\text{ kHz}$.
