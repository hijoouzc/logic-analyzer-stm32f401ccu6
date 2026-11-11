# Firmware Hardware Verification Test Suite

Thư mục này chứa toàn bộ các kịch bản kiểm thử tích hợp phần cứng (**Hardware-in-the-Loop Integration Tests**) và kiểm chứng tối ưu hóa thuật toán cho firmware Logic Analyzer (STM32F401CCU6 WeAct Black Pill V3.0), tương ứng với 5 bước trong Lộ trình triển khai (Roadmap):

## 1. Yêu Cầu Môi Trường
- **Python 3.8+** kèm thư viện `pyserial`:
  ```bash
  pip install pyserial
  ```
- **Quyền truy cập cổng Serial (Linux):**
  ```bash
  sudo chmod 666 /dev/ttyACM0
  # Hoặc thêm user vào nhóm dialout: sudo usermod -a -G dialout $USER
  ```

---

## 2. Danh Sách Kịch Bản Kiểm Thử

| Tên File | Mục Tiêu Kiểm Thử | Yêu Cầu Phần Cứng | Lệnh Chạy |
| :--- | :--- | :--- | :--- |
| **`verify_step1_freerun.py`** | Kiểm tra thông luồng Free-run: PING -> PONG, TIM1 + DMA2 thu thập 32.768B, truyền USB CDC 32.776B, kiểm tra Header và XOR Checksum. | Cắm kit STM32 vào cổng USB máy tính. | `python3 verify_step1_freerun.py [/dev/ttyACM0]` |
| **`verify_step2_loopback.py`** | Loopback Self-Test: USART1 TX trên PA9 phát chuỗi `"TEST_LA_2026\r\n"` (115200 bps, 8-N-1); LA kênh 0 (PA0) thu thập mẫu ở 1 MHz và giải mã UART phần mềm. | **Cắm dây jumper nối PA9 sang PA0.** | `python3 verify_step2_loopback.py [/dev/ttyACM0]` |
| **`verify_step3_trigger.py`** | FSM Trigger toàn phần: Chế độ Edge Trigger (cạnh xuống PA0), Dynamic Pre-trigger ($\ge 20\% = 6.554\text{ mẫu}$), Inline Trigger ISR (18 clock cycles), TIM2 One-Pulse post-trigger counter, giải thuật xoay vòng Circular Buffer (Unrolling) đưa điểm Trigger về danh định tại mẫu 6554 với sai số jitter vật lý tiệm cận $\approx 1$ mẫu ở 6 MHz. | **Cắm dây jumper nối PA9 sang PA0.** | `python3 verify_step3_trigger.py [/dev/ttyACM0]` |
| **`verify_step4_edge_cases.py`** | Kiểm thử biên & độ bền giao thức: 8 bài test gồm PING, NAK sai sample rate (0xE1), NAK sai kênh/mode trigger (0xE2), NAK sai checksum (0xE0), ABORT khi IDLE, ABORT khẩn cấp khi đang capture, và Dynamic Timeout ($T_{\text{timeout}} = 16384/f_s + 2.0\text{ s}$) trả về Status 0x02. | Cắm kit STM32 vào cổng USB máy tính. | `python3 verify_step4_edge_cases.py [/dev/ttyACM0]` |
| **`verify_optimizations.py`** | Kiểm chứng 5 kỹ thuật tối ưu hóa chuyên sâu: (1) Fast Checksum XOR 32-bit unroll 8x trên 500 block ngẫu nhiên; (2) Dynamic Pre-trigger 20% qua `NDTR`; (3) Phân tích mã máy assembly Trigger ISR đạt 18 clock cycles; (4) Unrolling và chia khối 512B non-blocking ở vị trí ghi bất kỳ; (5) Phân tích mã máy xác nhận opcode `__WFI()` (`bf30`). | **Không cần cắm kit thật** (chạy trực tiếp trên Host / phân tích mã biên dịch). | `python3 verify_optimizations.py` |

---

## 3. Chú Ý Kỹ Thuật
- Cổng kết nối mặc định là `/dev/ttyACM0`. Nếu kit nhận cổng khác (ví dụ `/dev/ttyACM1` trên Linux hoặc `COM3` trên Windows), có thể truyền tên cổng vào đối số đầu tiên:
  ```bash
  python3 verify_step1_freerun.py COM3
  ```
- Mọi gói tin truyền nhận đều tuân thủ 100% tài liệu quy chuẩn [**`spec/protocol.md`**](../../spec/protocol.md).
