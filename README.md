# BÀI TẬP LỚN: HỆ THỐNG NHÚNG VÀ THIẾT KẾ GIAO TIẾP NHÚNG (2026.1)
## Đề tài: Thiết kế và Xây dựng Thiết bị Logic Analyzer Đơn Giản (Topic 1)
**Hệ thống thu thập 8 kênh / 6 MHz đồng bộ – Nền tảng STM32F401CCU6 (Black Pill V3.0) + Python Desktop GUI**

---

## 1. Phân công Thành viên & Vai trò (Team Roles)

| Mã vai trò | Họ và Tên | MSSV | Phân hệ Phụ trách | Thư mục Làm việc | Nhiệm vụ Trọng tâm |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **TV1** | **Nguyễn Văn Hội** | **20233419** | **Firmware STM32** | `firmware/` | Cấu hình SYSCLK 84MHz, USB-CDC 48MHz, TIM1+TIM2 Cascade, DMA2_Stream5 đọc `GPIOA->IDR`, FSM Pre/Post-trigger, kênh phát UART PA9, trọn bộ 5 kỹ thuật tối ưu hóa (Dynamic Pre-trigger, Inline ISR, Non-blocking Streaming, Fast Checksum, WFI). |
| **TV2** | **Nguyễn Văn Khang** | **20233458** | **Phần cứng & Mô phỏng** | `hardware/` | Mô phỏng LTspice 4 kịch bản (quá áp +12V..+15V 8 kênh, xung 200V / 1ms 1 kênh trên trở động, đáp ứng 1-3MHz), thiết kế Schematic/PCB bảo vệ & đệm 74LVC245. |
| **TV3** | **Nguyễn Trường Giang** | **20233374** | **Phần mềm PC (GUI & Decoder)** | `software/` | Viết Python Desktop GUI (PyQt5 + pyqtgraph 60 FPS), bộ giải mã đa giao thức (UART, SPI, I²C), cặp con trỏ đo Cursors A/B, bộ kiểm thử mock serial. |

---

## 2. Quy tắc Sống còn trong Dự án (Strict Project Rules)

### ⚠️ Quy tắc 1: Bảo vệ mã nguồn STM32CubeMX (Bắt buộc cho TV1)
* Mọi mã nguồn do STM32CubeMX tự động sinh ra (`main.c`, `stm32f4xx_it.c`, `usbd_cdc_if.c`) **CHỈ ĐƯỢC PHÉP VIẾT BÊN TRONG CÁC KHỐI `/* USER CODE BEGIN ... */` VÀ `/* USER CODE END ... */`**.
* Tuyệt đối không viết code xử lý logic dày đặc trong các file này. Hãy gọi các hàm callback hook (`la_core_*`, `la_protocol_*`) sang các file nghiệp vụ riêng: `Core/Src/la_core.c`, `Core/Src/la_protocol.c`, `Core/Src/la_testgen.c`.

### ⚠️ Quy tắc 2: Quản lý File Nhị phân & Tài nguyên Lớn
* **Tệp văn phòng (`.docx`, `.pptx`):** Không thể merge diff trên Git. Áp dụng nguyên tắc **Single Owner** (TV1 phụ trách Slide tiến độ; TV2 phụ trách Báo cáo Word cuối kỳ).
* **Video Demo:** Tuyệt đối không commit file video (`.mp4`, `.mov`) vào Git. Video demo được lưu trữ trên **MS Teams / Google Drive / YouTube Unlisted**, chỉ lưu kịch bản và đường dẫn link trong `report/demo/`.

### ⚠️ Quy tắc 3: Quy ước Phân nhánh Git (Branching Workflow)
* Không commit trực tiếp lên nhánh `main`.
* Mọi thành viên tạo nhánh làm việc tương ứng:
  * TV1: `git checkout -b fw/ten-tinh-nang`
  * TV2: `git checkout -b hw/ten-tinh-nang`
  * TV3: `git checkout -b sw/ten-tinh-nang`
* Hợp nhất vào `main` thông qua Pull Request (PR) sau khi đã tự kiểm tra cục bộ đạt chuẩn.

---

## 3. Cấu trúc Thư mục Tổng thể

```text
Embedded_System/
├── .gitattributes                  # Chuẩn hóa xuống dòng LF đa nền tảng
├── .gitignore                      # Chặn build artifacts (C/Python/LTspice)
├── README.md                       # Tài liệu hướng dẫn chung của dự án
│
├── docs/                           # Datasheets chip, RM0368, Sơ đồ nguyên lý kit Black Pill V3.0
├── spec/                           # Tài liệu kỹ thuật dự án
│   ├── Logic_analyzer_requirements.md   # Đề bài gốc của môn học
│   ├── logic_analyzer_specification.md  # Đặc tả kiến trúc kỹ thuật chi tiết
│   └── protocol.md                      # Hợp đồng truyền thông nhị phân giữa TV1 và TV3
│
├── firmware/                       # Mã nguồn STM32CubeIDE (TV1)
│   ├── firmware.ioc                # File cấu hình STM32CubeMX
│   ├── .project, .cproject         # Project descriptors của Eclipse/CubeIDE
│   ├── STM32F401CCUX_FLASH.ld      # Linker script
│   ├── STM32F401_STLink.launch     # Cấu hình nạp debug ST-Link dùng chung
│   ├── Core/Startup/               # startup_stm32f401ccux.s
│   ├── Core/Inc/, Core/Src/        # Code hệ thống + la_core, la_protocol, la_testgen
│   ├── tests/                      # Bộ kịch bản Python kiểm thử phần cứng HIL (Steps 1-4)
│   ├── USB_DEVICE/                 # Middleware USB-CDC
│   ├── Drivers/                    # CMSIS & ST HAL/LL Drivers (Commit trực tiếp để build ngay)
│   └── Middlewares/                # ST USB Device Library (Commit trực tiếp)
│
├── hardware/                       # Thiết kế mạch & Mô phỏng LTspice (TV2)
│   ├── sim/                        # Các file mô phỏng .asc (quá áp 12-15V/20V, xung 200V/1ms, tần số 1-3MHz)
│   ├── design/                     # Schematic & PCB (Altium / KiCad) + bản xuất PDF
│   └── bom/                        # Danh mục linh kiện chi tiết (BOM.csv / BOM.xlsx)
│
├── software/                       # Giao diện Python Desktop & Decoder (TV3)
│   ├── requirements.txt            # Danh sách thư viện Python
│   ├── app.py                      # Điểm khởi chạy giao diện GUI
│   ├── gui/                        # Giao diện hiển thị đồ thị 8 kênh
│   ├── decoders/                   # Module giải mã giao thức (UART, SPI, I2C)
│   └── tests/                      # Bộ test độc lập (mock_serial.py, sample_data_1mhz.bin)
│
└── report/                         # Báo cáo và trình bày
    ├── slides_11_11/               # Slide báo cáo tiến độ mốc 11/11 (TV1 giữ file chính)
    ├── final_report/               # File Word báo cáo tổng hợp cuối kỳ (TV2 giữ file chính)
    └── demo/                       # Kịch bản demo và link video trên Teams/Drive
```

---

## 4. Hướng dẫn Bắt đầu Nhanh (Quick Start)

### Dành cho TV1 (Firmware):
1. Mở **STM32CubeIDE**, chọn `File -> Open Projects from File System...`, trỏ tới thư mục `firmware/`.
2. Bấm nút **Build** (`Ctrl+B`) để kiểm tra biên dịch dự án (hoặc chạy CLI make từ terminal).
3. **Nạp Firmware:**
   * *Cách 1 (Chính thức - ROM USB DFU qua cáp Type-C):* Giữ `BOOT0`, bấm nhả `NRST`, chạy:
     `STM32_Programmer_CLI -c port=usb1 -d firmware/STM32CubeIDE/Debug/firmware.elf -v -s`
   * *Cách 2 (Debug SWD nâng cao):* Nối ST-Link (SWDIO, SWCLK, GND, 3V3), chọn Run Debug với profile `STM32F401_STLink.launch`.

### Dành cho TV3 (Python GUI & Decoder):
1. Di chuyển vào thư mục `software/` và cài đặt thư viện phụ thuộc:
   ```bash
   cd software
   pip install -r requirements.txt
   ```
2. Chạy thử nghiệm giả lập độc lập mà không cần kit thật:
   * Terminal 1: Chạy script giả lập phát gói dữ liệu 32KB mẫu:
     ```bash
     python tests/mock_serial.py
     ```
   * Terminal 2: Chạy giao diện người dùng:
     ```bash
     python app.py
     ```
   * Trên GUI bấm **Start**, đồ thị sẽ hiển thị dạng sóng UART và giải mã ra chuỗi `"TEST_LA_2026"`.

---

## 5. Tiến độ Triển khai Firmware (TV1)

| Mốc triển khai | Nội dung kỹ thuật | Trạng thái |
| :--- | :--- | :---: |
| **Bước 1: Free-Run Base** | Thông luồng TIM1 -> DMA2 -> Buffer 32KB -> USB-CDC streaming. Kiểm chứng PING và 32KB data. | ✅ **Đã hoàn thành** |
| **Bước 2: Loopback Self-Test** | USART1 TX trên PA9 phát test frame 115200 bps nối jumper sang PA0. | ✅ **Đã hoàn thành** |
| **Bước 3: Full FSM Trigger** | DMA Half-Transfer -> Unmask EXTI -> Kích TIM2 One-Pulse -> Unroll Buffer. | ✅ **Đã hoàn thành** |
| **Bước 4: Edge Cases & Polish**| Timeout SysTick, Ping, Abort, NAK, USB Watchdog 100ms. | ✅ **Đã hoàn thành** |
| **Bước 5: Tối ưu hóa Toàn diện Hệ thống** | Fast Checksum XOR 32-bit (unroll 8x, <0.12 ms), Dynamic Pre-trigger 20% qua `NDTR` (rút ngắn 60% thời gian chờ ở tần số thấp), Inline Trigger ISR (18 clock cycles, sai số $\approx 1$ mẫu @ 6 MHz), Non-blocking USB Streaming 512B (CPU load <2%), Tiết kiệm điện và triệt tiêu nhiễu bus qua `__WFI()`. | ✅ **Đã hoàn thành** |

---

## 6. Tài liệu Tham khảo Chính
* [Đề bài Yêu cầu Kỹ thuật](spec/Logic_analyzer_requirements.md)
* [Bản Đặc tả Kỹ thuật Hệ thống](spec/logic_analyzer_specification.md)
* [Hợp đồng Giao thức Truyền thông](spec/protocol.md)
