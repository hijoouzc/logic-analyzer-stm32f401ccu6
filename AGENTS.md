# AGENTS.md: Quy Chuẩn Vận Hành Cho AI Agent (TV1 - Firmware Engineer)

Tài liệu này xác định các nguyên tắc ứng xử, ràng buộc kỹ thuật và quy trình kiểm thử bắt buộc đối với AI Coding Agent khi hỗ trợ **TV1 (Firmware Engineer)** phát triển firmware cho Đề tài 1: Logic Analyzer 8 kênh 6 MHz (STM32F401CCU6 WeAct Black Pill V3.0).

---

## 1. Giới Hạn Phần Cứng & Thiết Lập Hệ Thống

* **Vi điều khiển:** STM32F401CCU6 (SRAM 64 KB, Flash 256 KB). Mảng mẫu chiếm cố định 32 KB (50% RAM).
* **Clock Tree:** SYSCLK = 84 MHz (HSE 25 MHz), APB1 Prescaler = /2 (PCLK1 42 MHz, Timer TIM2 84 MHz), APB2 Prescaler = /1 (PCLK2 & Timer TIM1 84 MHz), USB OTG_FS = 48 MHz. Chi tiết xem [spec/logic_analyzer_specification.md](spec/logic_analyzer_specification.md).
* **Ánh xạ ngoại vi & Ràng buộc phần cứng:**
  * Kênh đo 0 – 7: Nối vào PA0 – PA7 (đọc trực tiếp `GPIOA->IDR`). Chân PA0 trên kit WeAct V3.0 nối nút KEY qua trở hạn dòng $330\,\Omega$ xuống GND (không nhấn nút khi đang đo xung).
  * Chân PA9 làm `USART1_TX` phát xung loopback test: **Bắt buộc tắt tính năng VBUS sensing của USB OTG_FS** trong CubeMX để giải phóng chân PA9.
  * Chân PC13: LED trạng thái (Active Low).
* **Quy trình nạp & debug:** Nạp chính qua ROM USB DFU Bootloader (`STM32_Programmer_CLI -c port=usb1 -d <file.elf> -v -s`). Duy trì cấu hình chân SWD và file `firmware/STM32F401_STLink.launch` trong git cho nhu cầu debug step-by-step khi có ST-Link.

---

## 2. Nguồn Chân Lý Duy Nhất (Single Source of Truth - SSoT)

Khi có mâu thuẫn kỹ thuật, Agent tuân thủ thứ bậc ưu tiên:
1. [**`spec/protocol.md`**](spec/protocol.md): Định dạng khung truyền, mã lệnh (5B), phản hồi/NAK (7B), gói dữ liệu (32.776B) và timeout.
2. [**`spec/logic_analyzer_specification.md`**](spec/logic_analyzer_specification.md): Kiến trúc Timer/DMA, bảng ARR, cấu hình clock và FSM.
3. **ST RM0368 Reference Manual & Datasheet STM32F401**: Căn cứ duy nhất về thanh ghi, cờ ngắt và pipeline DMA.
4. **Comment trong mã nguồn hiện có**.

---

## 3. Phạm Vi File & Quy Trình Ngoại Vi

### 3.1. File được phép tạo và chỉnh sửa:
* File nghiệp vụ: `firmware/Core/Inc/la_*`, `firmware/Core/Src/la_*`.
* File CubeMX sinh ra (`main.c`, `stm32f4xx_it.c`, `usbd_cdc_if.c`...): **Chỉ được sửa trong các khối `/* USER CODE BEGIN ... */` và `/* USER CODE END ... */`**.

### 3.2. File cấm can thiệp:
* Cấm sửa: `Drivers/`, `Middlewares/`, startup code, linker script (`*.ld`), file cấu hình `firmware/*.ioc`.
* Cấm tự ý sửa file ngoài thư mục firmware (`hardware/`, `software/`, `spec/`) trừ khi TV1 yêu cầu.

### 3.3. Quy trình thay đổi ngoại vi (CubeMX):
* Agent không tự sửa file khởi tạo ngoại vi do CubeMX quản lý. Phải hướng dẫn từng bước thao tác trong CubeMX GUI cho người dùng.
* Checklist sau khi người dùng Generate Code: (1) Kiểm tra VBUS sensing có bị CubeMX tự bật lại không; (2) Kiểm tra bảng ưu tiên NVIC; (3) Kiểm tra code trong các vùng USER CODE có nguyên vẹn không.

---

## 4. Kiến Trúc Firmware Đã Chốt

1. **Sampling Engine:** Sự kiện Update của TIM1 (bit `UDE = 1`) kích hoạt `DMA2_Stream5 Channel 6` đọc 1 byte từ `GPIOA->IDR` vào mảng tĩnh `la_capture_buffer[32768]` ở chế độ Circular. Bảng ARR (PSC=0, Clock 84 MHz) xem chi tiết tại spec.
2. **Post-trigger Counter:** TIM2 cấu hình Slave Mode ExtClock1 nhận TRGO từ TIM1 qua liên kết nội bộ `ITR0` (ST RM0368 Table 54), One-Pulse Mode, ARR = 26213 (đếm 26.214 mẫu = 80% bộ đệm sau trigger). Ngắt `TIM2_IRQHandler` dừng tức thì TIM1.
3. **Ưu tiên ngắt NVIC:** Priority 0 (EXTI Trigger) > Priority 1 (TIM2 Dừng lấy mẫu) > Priority 2 (USB OTG_FS).
4. **Máy trạng thái FSM (5 bước & Tối ưu hóa Chuyên sâu):**
   `IDLE ───> ARMED ───> PRE_SAMPLING ───> WAIT_TRIGGER ───(Ngắt EXTI Trigger)───> POST_SAMPLING ───> TRANSFERRING ───> IDLE`
   * Ở `PRE_SAMPLING`, áp dụng cơ chế **Dynamic Pre-trigger**: kiểm tra liên tục con trỏ ghi DMA `(32768 - DMA2_Stream5->NDTR) >= 6554` (kèm cờ dự phòng `HTIF5` tại 50%) để unmask EXTI ngay khi vừa đủ 20% pre-trigger danh định (tiết kiệm gần $1.0\text{ s}$ ở 10 kHz).
   * **Triệt tiêu Race Condition sống còn:** Khi unmask EXTI, bắt buộc thực hiện theo thứ tự: Gán `g_la_state = LA_STATE_WAIT_TRIGGER;`, gọi `__DSB();` để bảo đảm biến trạng thái được ghi xuống SRAM, rồi mới mở ngắt `EXTI->IMR |= (1U << ch);`.
   * Trong trạng thái `WAIT_TRIGGER`, CPU gọi lệnh `__WFI()` (Wait For Interrupt) đưa Cortex-M4 về chế độ Sleep tiết kiệm điện năng và triệt tiêu nhiễu xung nhịp nội bộ bus AHB/APB vào các kênh đo.
   * Chế độ Free-run bỏ qua EXTI, bật thẳng TIM2 khi vừa đủ 6.554 mẫu (hoặc cờ `HTIF5`). Timeout động $T = (16384/f_s) + 2.0\text{ s}$ quản lý bởi SysTick. Chi tiết xem `protocol.md`.
5. **Cơ chế Unrolling & Sai số Trigger (Inline Hardware Trigger & Memory Barrier):**
   * Dữ liệu truyền xoay vòng từ `write_pos = 32768 - NDTR` đến cuối mảng rồi tiếp tục từ đầu mảng đến `write_pos - 1`, định vị điểm trigger danh định tại mẫu $t_{6554}$ (`trig_offset = 6554`).
   * **Tối ưu hóa trễ ISR Inline:** Các chỉ thị kích hoạt timer được inline trực tiếp vào đầu ngắt `EXTI_IRQHandler` (`TIM2->CR1 |= TIM_CR1_CEN; EXTI->IMR &= ~0x00FFU; EXTI->PR = pr;`), rút ngắn độ trễ từ lúc có cạnh xung đến khi TIM2 đếm xung xuống mức tiệm cận phần cứng chỉ 18 clock cycles ($\approx 214\text{ ns}$ @ 84 MHz), sai số vật lý chỉ còn $\approx 1$ mẫu ở 6 MHz (thay vì 2–3 mẫu).
   * **Memory Barrier khi dừng:** Lệnh dừng `TIM1->CR1 &= ~TIM_CR1_CEN` trong `TIM2_IRQHandler` bắt buộc đi kèm `__DSB();` để xả sạch Write Buffer trên bus APB2 trước khi dừng DMA và chốt con trỏ `NDTR`.
6. **Khóa lệnh khi truyền & Non-blocking Streaming:**
   * Trong trạng thái `TRANSFERRING`, drop toàn bộ byte nhận từ USB để không làm gián đoạn luồng truyền 32KB. Ở các trạng thái bắt tín hiệu khác: nhận `CMD_START` trả NAK `0xE3`; nhận `CMD_PING` trả PONG `0x04`; nhận `CMD_ABORT` trả `0x05`.
   * **Non-blocking Streaming, TxFIFO & Fast XOR:** Quá trình truyền phân đoạn theo block 512B do máy trạng thái phi phong tỏa điều khiển; khi `hcdc->TxState != 0`, firmware nhượng CPU cho luồng chính để tiếp tục các tác vụ khác (tải CPU $< 2\%$, kèm watchdog 100ms bảo vệ chống treo). Tận dụng tối đa 320 words Dedicated Packet RAM của USB OTG_FS (Rx = 64 words, Tx0 = 32 words, Tx1 = 224 words = 896B Bulk IN). Tính Checksum XOR 32-bit unrolled 8x hoàn tất 32KB trong $< 0.12\text{ ms}$.
   * **Cô lập Kênh phát Testgen PA9:** `la_testgen_process()` chỉ được phép phát xung khi FSM ở `LA_STATE_IDLE`, ngắt hoàn toàn khi đang capture để không giam giữ CPU 1.3 ms và bảo toàn chế độ nghỉ `__WFI()`.

---

## 5. Quy Tắc Thời Gian Thực & Kỹ Thuật Mã Nguồn

* **Kỷ luật ISR:** ISR ngắn gọn (< 30 dòng), chỉ xóa cờ và cập nhật cờ FSM/thanh ghi. Các chỉ thị then chốt kích hoạt timer (`TIM2->CR1 |= TIM_CR1_CEN`) được inline trực tiếp để đạt trễ tiệm cận phần cứng (18 clock). Tuyệt đối không gọi `printf`, `HAL_Delay`, tính toán nặng hay vòng lặp chờ USB trong ISR.
* **Đồng bộ biến:** Khai báo `volatile` và kiểu kích thước cố định (`<stdint.h>`, `<stdbool.h>`) cho mọi biến chia sẻ giữa ISR và main.
* **Quản trị cờ DMA:** Trước mỗi lượt capture mới, bắt buộc xóa sạch cờ Half-Transfer (`HTIF5`), Transfer-Complete (`TCIF5`) và các cờ lỗi (`TEIF5`, `DMEIF5`, `FEIF5`) của DMA2 Stream 5 để tránh cờ tồn dư kích hoạt EXTI sớm làm rỗng pre-trigger.
* **Bộ nhớ an toàn:** Tuyệt đối cấm cấp phát động (`malloc`, `free`), cấm đệ quy, cấm mảng biến động (VLA). Mảng mẫu 32 KB khai báo tĩnh: `static uint8_t la_capture_buffer[32768];`.
* **USB Streaming Non-blocking & Watchdog:** Gửi gói tin 32.776B theo từng khối 512B dựa trên máy trạng thái phi phong tỏa; nhượng quyền CPU khi bận, kèm timeout bảo vệ 100 ms/khối để tránh treo máy nếu PC ngắt kết nối.
* **Tiết kiệm điện & Giảm nhiễu Bus:** Sử dụng lệnh `__WFI()` khi CPU ở trạng thái `WAIT_TRIGGER` để đưa Cortex-M4 về Sleep mode, triệt tiêu xung nhiễu chuyển mạch bus AHB/APB vào các chân PA0..PA7.
* **Quy ước đặt tên:** Hàm `la_<module>_<action>`, macro/hằng số `LA_<NAME>`, enum trạng thái `LA_STATE_*`. Kiểm tra mã trả về của mọi hàm ST HAL.

---

## 6. Lộ Trình Triển Khai & Hoàn Thiện Toàn Hệ Thống

* **Bước 1 (Free-Run Base):** Chạy thông luồng TIM1 -> DMA2 -> Buffer 32KB -> USB-CDC gửi dữ liệu lên PC. *(✅ Đã hoàn thành)*
* **Bước 2 (Loopback Self-Test):** Cấu hình USART1 TX trên PA9 phát mẫu test 115200 bps nối jumper sang PA0. *(✅ Đã hoàn thành)*
* **Bước 3 (Full FSM Trigger):** Ghép nối ngắt DMA Half-Transfer -> Unmask EXTI -> Kích TIM2 One-Pulse -> Unroll Buffer. *(✅ Đã hoàn thành)*
* **Bước 4 (Edge Cases & Polish):** Hoàn thiện Timeout SysTick, Ping, Abort, NAK và USB Watchdog 100ms. *(✅ Đã hoàn thành)*
* **Bước 5 (Full-System Optimization):** Trọn bộ 5 kỹ thuật tối ưu hóa chuyên sâu: Fast Checksum XOR 32-bit unroll 8x (<0.12 ms), Dynamic Pre-trigger 20% qua `NDTR`, Inline Trigger ISR (18 clock cycles, ~1 mẫu @ 6 MHz), Non-blocking USB Streaming 512B (CPU load <2%), Tiết kiệm điện và triệt tiêu nhiễu bus qua `__WFI()`. *(✅ Đã hoàn thành)*

---

## 7. Tiêu Chí "Dừng Lại Và Hỏi" (Stop & Ask Criteria)

Agent phải dừng lại, nêu rõ vấn đề và xin ý kiến TV1 khi:
1. Yêu cầu sửa các file nằm ngoài phạm vi mục 3.1.
2. Phát hiện mâu thuẫn giữa các tài liệu đặc tả hoặc yêu cầu vi phạm kiến trúc phần cứng đã chốt.
3. Cần can thiệp vào tần số 84 MHz, clock APB, kênh DMA request hoặc bảng ưu tiên NVIC.
4. Hành vi thanh ghi không rõ ràng trong RM0368.
5. **Nguyên tắc trung thực kỹ thuật:** Nếu tính năng chỉ mới chạy mô phỏng/build code mà chưa nạp kit thật, bắt buộc phải nói rõ là *"chưa kiểm chứng trên phần cứng thật"*, không tự nhận đã hoàn thành 100%.

---

## 8. Báo Cáo Nghiệm Thu & Checklist Hoàn Thành

### 8.1. Định dạng Báo cáo Nghiệm thu (3 phần bắt buộc khi xong task):
1. **Đã thay đổi những gì:** Danh sách file và tóm tắt dòng/hàm đã sửa.
2. **Đã kiểm chứng bằng cách nào:** Kết quả biên dịch (0 error, 0 warning), map file SRAM, hoặc kết quả chạy script test.
3. **Điều gì CHƯA thể kiểm chứng:** Các phần cần máy đo, USB analyzer hoặc kit STM32F401 thực tế.

### 8.2. Quy chuẩn Git & Checklist trước khi báo hoàn thành:
* Nhánh làm việc có tiền tố `fw/` (ví dụ `fw/loopback-self-test`). Commit chuẩn Conventional Commits.
* Tuyệt đối không commit file build rác (`*.o`, `*.elf`, thư mục `Debug/`, `Release/`).
* **Checklist Đạt:** (1) 100% code tự viết nằm trong khối USER CODE; (2) Biên dịch 0 errors, 0 warnings; (3) Chạy toàn bộ script test Python (`verify_step*.py`, `verify_optimizations.py`) xác nhận Header `0x5A, 0xA5`, Little-Endian và XOR Checksum khớp `protocol.md`; (4) SRAM < 64 KB (buffer 32 KB chiếm đúng 50%).
