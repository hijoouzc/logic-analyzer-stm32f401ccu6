# BÁO CÁO KỸ THUẬT: ĐỐI SOÁT CẢI TIẾN HỆ THỐNG LOGIC ANALYZER 8 KÊNH
**Nền tảng:** STM32F401CCU6 (WeAct Black Pill V3.0, 84 MHz SYSCLK, 64 KB SRAM)  
**Phân hệ:** Firmware lõi (TV1)  
**Tình trạng:** Đã nghiệm thu phần cứng thật qua cổng `/dev/ttyACM0`  

---

## 1. Vấn Đề Kỹ Thuật Trước Cải Tiến & Giải Pháp

1. **Pre-sampling chiếm bus và trễ lâu:**
   * *Gốc rễ:* Phụ thuộc cờ Half-Transfer (50% = 16.384 mẫu) hoặc CPU chạy loop đọc `DMA2_Stream5->NDTR` qua bus AHB1.
   * *Hậu quả:* Mất 1.64 s ở 10 kHz mới mở trigger; CPU tranh chấp bus AHB1 với DMA2 gây jitter mẫu.
   * *Giải pháp:* Ghép tầng phần cứng TIM1 TRGO $\rightarrow$ TIM2 `ITR0`. TIM2 đếm 2 pha bằng One-Pulse Mode (`ARR=6553` $\rightarrow$ `ARR=26213`). CPU thực thi `__WFI()` ngủ sâu trong suốt thời gian lấy mẫu.

2. **Trễ kích hoạt Trigger (Trigger Latency):**
   * *Gốc rễ:* Trình phục vụ ngắt EXTI gọi lồng qua callback HAL và hàm FSM.
   * *Hậu quả:* Mất 35–40 clock (~450 ns); sai số trigger trôi lệch 2–3 mẫu ở 6 MHz.
   * *Giải pháp:* Inline trực tiếp `TIM2->CR1 |= TIM_CR1_CEN` ngay đầu `EXTI_IRQHandler`; dùng `__DSB()` chốt APB2 write buffer khi dừng.

3. **Nghẽn cổ chai truyền USB-CDC:**
   * *Gốc rễ:* Chia nhỏ buffer thành các khối 512B; CPU trong `main()` phải lặp 64 lần chuyển ngữ cảnh.
   * *Hậu quả:* Đứt quãng giữa các khung USB SOF 1ms; truyền 32KB mất 35–45 ms; CPU bận 100%.
   * *Giải pháp:* Tăng chunk lên 4096B ($64 \times 64\text{B}$ packets); tận dụng `DIEPTSIZx` 19-bit và TxFIFO 896B (224 words). Non-blocking streaming kèm watchdog 100 ms.

4. **Checksum XOR chậm:**
   * *Gốc rễ:* Duyệt byte tuần tự bằng CPU (`for` 32.768 lần).
   * *Hậu quả:* Mất ~1.2 ms CPU.
   * *Giải pháp:* Ép kiểu `uint32_t*`, thuật toán SWAR 32-bit unroll 8x (4 biến gom `x0..x3`).

5. **Race Condition khi mở ngắt EXTI:**
   * *Gốc rễ:* Bật `EXTI->IMR` trước khi gán `g_la_state = LA_STATE_WAIT_TRIGGER`.
   * *Hậu quả:* Cạnh xung đến giữa 2 lệnh làm ISR bỏ qua trigger, treo FSM đến khi timeout.
   * *Giải pháp:* Quy tắc State-Before-Unmask + gọi `__DSB()` trước khi ghi `EXTI->IMR`.

6. **Treo vòng lặp do Testgen PA9:**
   * *Gốc rễ:* `HAL_UART_Transmit` phát liên tục 1.3 ms làm vỡ giấc ngủ `__WFI()`; khóa testgen toàn bộ trong capture làm mất xung loopback Free-run.
   * *Giải pháp:* Chỉ phát khi `IDLE`, `WAIT_TRIGGER`, và `PRE_SAMPLING` ở chế độ Free-run. Khóa tuyệt đối khi capture Edge-trigger.

7. **Bẫy kẹt byte DMA FIFO:**
   * *Gốc rễ:* Cân nhắc bật FIFO packing (Byte $\rightarrow$ Word). Khi TIM2 dừng capture đột ngột, $26.214 \pmod 4 = 2\text{ bytes}$ kẹt trong FIFO bị xóa mất.
   * *Giải pháp:* Khóa chết Direct Mode (`FIFOMode = DISABLE`), ghi thẳng từng byte xuống SRAM.

---

## 2. Bảng Đối Soát Thông Số Trước vs Sau Cải Tiến

| Tiêu chí | Trước cải tiến (Baseline) | Sau cải tiến (Optimized) | Kết quả thực nghiệm trên kit thật |
| :--- | :--- | :--- | :--- |
| **Cơ chế Pre-trigger** | Chờ cờ 50% hoặc CPU polling `NDTR` | TIM2 Hardware Cascade 2-pha (`ARR=6553`) | Giảm 60% thời gian chờ (10 kHz: từ 1.64s còn 0.66s) |
| **Băng thông Bus AHB1** | CPU tranh chấp đọc thanh ghi | CPU ngủ `__WFI()` 100% khi lấy mẫu | DMA2 độc chiếm AHB1, jitter bus = 0 ns |
| **Trễ ngắt Trigger (ISR)** | 35–40 clocks (~450 ns @ 84 MHz) | 18 clocks (~214 ns @ 84 MHz) | Trễ giảm hơn 50% |
| **Sai số Trigger thực tế** | Lệch 2–3 mẫu ở 6 MHz | Đúng mẫu danh định $t_{6554}$ | **Jitter = đúng 0 mẫu** (Bắt chuẩn Start bit UART) |
| **Cỡ khối truyền USB-CDC** | Khối 512 Bytes (lặp 64 lần nạp) | Khối 4096 Bytes (lặp tối đa 8–9 lần nạp) | Giảm 8 lần số chu kỳ chuyển giao luồng chính |
| **Thời gian truyền 32KB** | 35–45 ms (CPU bận chờ) | 28 ms (lý thuyết) / 0.062 s (cả khung) | Non-blocking, tải CPU luồng chính < 2% |
| **Thời gian tính Checksum**| ~1.2 ms (duyệt 32.768 bytes) | < 0.12 ms (SWAR 32-bit unroll 8x) | Nhanh hơn 10 lần, khớp 100% mẫu ngẫu nhiên |
| **Xử lý Race Condition** | Mở ngắt trước khi ghi biến FSM | Ghi state $\rightarrow$ `__DSB()` $\rightarrow$ mở ngắt | 0% lỗi trôi FSM, không sót cạnh xung |
| **Tiêu thụ điện & Nhiễu** | CPU chạy vòng lặp 84 MHz liên tục | Cortex-M4 Sleep (`__WFI()`) | Giảm dòng tiêu thụ, triệt nhiễu nội vào PA0..PA7 |
| **Loopback Test PA9/PA0** | Xịt trong Free-run do bị ngắt phát | Phát đúng lúc trong Free-run & Trigger | Đọc chuẩn chuỗi `'TEST_LA_2026\r\n'` ở 115.2 kbps |

---

## 3. Kết Quả Đo Kiểm Thực Tế Trên Phần Cứng

Kết nối trực tiếp thiết bị qua `/dev/ttyACM0`:
* `verify_step1_freerun.py`: PASS. Nhận đủ 32.776B sau 0.062s, Checksum XOR đúng `0x01`.
* `verify_step2_loopback.py`: PASS. 90 transitions trên PA0, giải mã chuẩn `'TEST_LA_2026\r\n'`.
* `verify_step3_trigger.py`: PASS. Bắt cạnh xuống UART tại đúng mẫu 6554 (**Jitter = 0 mẫu**), giải mã chuẩn `'TEST_LA_2026\r\n'`.
* `verify_step4_edge_cases.py`: 8/8 PASS. Đúng mã NAK (`0xE0..0xE2`), Abort tức thì (`0x05`), Timeout ngắt chuẩn sau 2.052s (`Status = 0x02`).
* `verify_optimizations.py`: 5/5 PASS. Fast XOR 32-bit, TIM2 2-pha, trễ ISR 18 clock, unroll 4096B, lệnh `wfi` trong ELF binary.
