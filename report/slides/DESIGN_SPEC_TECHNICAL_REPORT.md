# SLIDE DESIGN SPECIFICATION (8 SLIDES) - HỆ THỐNG LOGIC ANALYZER 8 KÊNH 6 MHz
**Topic:** Báo Cáo Kỹ Thuật Toàn Bộ Hệ Thống Logic Analyzer 8 Kênh 6 MHz (STM32F401CCU6 Development Board)  
**Time Limit:** 260s (~4m20s) | **Template:** HUST Brand 16:9 (Red #C41230, White #FFFFFF)  
**Target:** Clean Technical Presentation (Visual Diagrams, Structured Tables, Metric Cards, Zero Walls of Text)

### Execution Rules (Bắt buộc):
- **Slide Layout:** Slide 1 (Bìa) dùng Title Slide; Slide 2 đến 7 (Nội dung) dùng **DUY NHẤT Layout 10 (`1_Comparison`)**; Slide 8 (Kết bài) dùng Closing/Thank You Slide.
- **Quy chuẩn Font & Cỡ chữ (Keyword-First Style):**
  - **100% Font chữ:** `Lato` (nhận diện chính thức của template HUST).
  - **Tiêu đề slide:** `28–30 pt` Bold Đỏ HUST (`#C41230`).
  - **Tiêu đề phụ:** `20–22 pt` Regular Xám chì (`#4B5563`).
  - **Metric chính:** `36–40 pt` (chuẩn 38 pt) Bold Đỏ HUST (`#C41230`) | Nhãn phụ `14 pt` Bold `#1F2937`.
  - **Nội dung trong Card:** `18 pt` Regular (Prefix in đậm `#1F2937`, tối đa 3–4 ý/card, cụm từ ngắn).
  - **Bảng thông số (Slide 2, 5):** `16–17 pt` (Header Bold nền Đỏ HUST, Data Cells Regular/Status Bold).
  - **Ngoại lệ Bảng tiến độ 8 dòng (Slide 7):** `14.5–15 pt` (áp dụng ngoại lệ linh hoạt để giữ đầy đủ 7 mốc mà không tràn viền).
  - **Chú thích hình / Proof box:** `14–16 pt` (nhận xét kỹ thuật, điều kiện mô phỏng).
  - **Footer / Số trang:** `11–12 pt` (chân slide).
  - **Cover Title (Slide 1):** `30 pt` (Dòng 1) & `26 pt` (Dòng 2) Bold | Subtitle: `16 pt`.
  - **Closing Title (Slide 8):** `34 pt` (Dòng 1) & `30 pt` (Dòng 2) Bold | Subtitle: `16 pt`.
- **Nguyên tắc biên tập Keyword-First:**
  - Không cắt bỏ thông số kỹ thuật cốt lõi (STM32F401, ARR=13, DMA2 vòng 32 KiB, TIM2 80%, Khung 32.776B). Chỉ rút gọn cách diễn đạt thành cụm từ khóa ngắn.
  - Toàn bộ phần diễn giải nguyên lý, cấu hình chi tiết và kết quả thực nghiệm được chuyển trọn vẹn vào **Presenter Notes** để phục vụ bài nói 4 phút 20 giây.
- **Bounding Box:** Tọa độ an toàn: `Left ≥ 0.4"`, `Right ≤ 12.8"`, `Top ≥ 1.15"`, `Bottom ≤ 6.6"`. Chống tràn viền, chống đè text (overlay).

---

## 1. TECHNICAL PARAMETERS (SINGLE SOURCE OF TRUTH)
- **MCU Platform:** STM32F401CCU6 (84 MHz SYSCLK, APB1 42MHz, APB2 84MHz, USB FS 48MHz).
- **Channels:** 8 digital channels mapped to `GPIOA->IDR` (PA0 – PA7).
- **Sampling Engine (Zero-CPU):** Sự kiện `TIM1 Update (UDE=1)` kích hoạt `DMA2_Stream5 Channel 6` ở chế độ Circular nạp vào `la_capture_buffer[32768]` (32 KiB SRAM tĩnh, căn lề 4 byte).
- **Hardware Timer Cascade:** `TIM1 TRGO` kết nối nội bộ qua bus `ITR0` kích hoạt `TIM2 Slave Mode ExtClock1` (One-Pulse Mode), $ARR = 26213$ (đếm đúng 26.214 mẫu = 80% mảng sau trigger).
- **Timer ARR Table:** 6 MHz (ARR=13), 3 MHz (ARR=27), 2 MHz (ARR=41), 1 MHz (ARR=83), 500 kHz (ARR=167), 200 kHz (ARR=419), 100 kHz (ARR=839), 50 kHz (ARR=1679), 10 kHz (ARR=8399).
- **Trigger Alignment & Unrolling:** Đọc thanh ghi $write\_pos = (32768 - NDTR) \pmod{32768}$; xoay vòng mảng từ `write_pos` đưa điểm trigger danh định về cố định tại $t_{6554}$ (đúng 20% bộ đệm).
- **Packet Format:** Khung 32.776 Bytes (7B Header + 32.768B Data + 1B Checksum XOR), phân đoạn truyền tối đa 512B/khối qua USB CDC kèm Watchdog 100 ms chống treo MCU.
- **Verification Status:** Đã kiểm chứng 100% trên kit thật WeAct Black Pill (Ping/Pong, Khung 32.776B, Loopback UART 115.2 kbps trên Ch0, Bắt trigger 6554 không jitter); đo tải 6 MHz và xung 200V thuộc mốc tiếp theo.

---

## 2. KIẾN TRÚC FIRMWARE & LUỒNG THỰC THI CODE CHI TIẾT (FIRMWARE ARCHITECTURE & CODE FLOW)

### 2.1. 6 Phương pháp & Kỹ thuật Thiết kế Cốt lõi
1. **Zero-CPU Hardware Cascade:** TIM1 (Master) $\rightarrow$ DMA2 Stream 5 bốc byte trực tiếp từ `GPIOA->IDR` vào SRAM; TIM1 TRGO $\rightarrow$ ITR0 $\rightarrow$ TIM2 (Slave One-Pulse) đếm 80% mẫu sau trigger. CPU hoàn toàn rảnh rỗi trong toàn bộ quá trình lấy mẫu.
2. **Event-Driven FSM (6 Trạng thái):** `IDLE` $\rightarrow$ `ARMED` $\rightarrow$ `PRE_SAMPLING` $\rightarrow$ `WAIT_TRIGGER` $\rightarrow$ `POST_SAMPLING` $\rightarrow$ `TRANSFERRING`.
3. **Bảo toàn Pre-trigger 20%:** Trong `PRE_SAMPLING`, ngắt EXTI bị khóa chặt (`EXTI->IMR &= ~0x00FF`). Chỉ khi cờ DMA Half-Transfer (`HTIF5`) bật (đã ghi được 50% = 16.384 mẫu $\ge$ 6.554 mẫu), firmware mới unmask EXTI để bắt trigger, loại trừ 100% nguy cơ rỗng bộ đệm quá khứ.
4. **Kỷ luật Thời gian thực & Phân cấp NVIC:**
   - `Priority 0` (Cao nhất): `EXTI0..EXTI9_5` — Bắt cạnh xung tức thì, trễ vào ngắt cực thấp (< 15 clock cycles).
   - `Priority 1`: `TIM2_IRQHandler` — Dừng lấy mẫu chính xác tại mẫu thứ 26.214 sau trigger.
   - `Priority 2`: `OTG_FS_IRQHandler` — Xử lý giao tiếp USB.
   - Kỷ luật ISR: < 30 dòng code, non-blocking, cấm `printf`/delay, sử dụng biến `volatile`.
5. **Thuật toán Duỗi mảng (NDTR Unrolling Math):**
   - Đọc con trỏ dừng: $write\_pos = (32768 - NDTR) \pmod{32768}$.
   - Chặng 1: Truyền từ $write\_pos \rightarrow 32767$ (đưa mẫu cũ nhất về thời điểm $t_0$).
   - Chặng 2: Truyền tiếp từ $0 \rightarrow write\_pos - 1$ (đưa mẫu mới nhất về $t_{32767}$).
   - Điểm trigger luôn nằm tại vị trí danh định cố định $t_{6554}$ (20% bộ đệm).
6. **Streaming Watchdog & Ring Buffer:**
   - Nhận lệnh qua Ring Buffer 64B bằng thuật toán cửa sổ trượt (Sliding Window) 5B có XOR Checksum.
   - Truyền phân đoạn tối đa 512B/khối; hàm `wait_cdc_tx_ready()` có timeout bảo vệ 100 ms chống treo hệ thống nếu PC rút cáp hoặc ngắt ứng dụng.

### 2.2. Luồng Thực thi Từng Bước của Code (End-to-End Flow)
```text
[BƯỚC 1: INIT] ──────► [BƯỚC 2: RX LỆNH] ──────► [BƯỚC 3: PRE-SAMPLING]
la_core_init()         la_protocol_process()     TIM1 nhịp, DMA2 ghi vòng
PUPDR pull-down        Sliding window 5B         EXTI MASKED (chống rỗng)
NVIC Priority 0..2     XOR Checksum kiểm tra     Chờ cờ DMA HTIF5
                                                        │
                                                        ▼
[BƯỚC 6: UNROLL & USB] ◄── [BƯỚC 5: TIM2 DỪNG] ◄── [BƯỚC 4: BẮT TRIGGER]
la_protocol_send_data()    TIM2 tràn 26.214 mẫu    EXTI ISR kích TIM2 CEN
Duỗi mảng 2 chặng          Dừng TIM1 & DMA2        Khóa ngay EXTI IMR
USB chunk 512B + WDT 100ms Chốt write_pos = 32K-NDTR FSM -> POST_SAMPLING
```

---

## 3. SLIDE-BY-SLIDE SPECIFICATIONS

### Slide 1: Cover (HUST Title Slide)
- **Layout:** Full-width Title layout with official HUST Logo crest.
- **Main Title:** BÁO CÁO KỸ THUẬT ĐỀ TÀI 1: THIẾT KẾ & XÂY DỰNG LOGIC ANALYZER 8 KÊNH
- **Metadata:** Học phần: Hệ thống nhúng & Thiết kế giao tiếp nhúng (2026.1) | Nền tảng: STM32F401CCU6 Development Board | 2026
- **Speaker Notes (30s):**
  > "Kính thưa thầy và các bạn, hôm nay đại diện cho nhóm, em xin báo cáo kỹ thuật toàn bộ hệ thống Đề tài 1: Thiết kế và xây dựng thiết bị Logic Analyzer 8 kênh trên nền tảng vi điều khiển STM32F401CCU6. Sau đây, em xin phép bắt đầu phần trình bày về kiến trúc và các giải pháp kỹ thuật đã triển khai thực tế của nhóm."

### Slide 2: 01 · Tổng quan Đề tài & Chỉ tiêu Thiết kế (35s)
- **Visual Structure:** 3 Big Metric Callout Cards on top + 40:60 Split Layout below.
  - *Top Row:* **3 Khối số liệu lớn nổi bật (Big Metric Cards)**:
    1. `8 KÊNH LOGIC` | Subtext: *Ánh xạ chân PA0 – PA7 (GPIOA IDR)*
    2. `6 MHz LẤY MẪU` | Subtext: *Cấu hình Timer danh định (ARR=13)*
    3. `32 KiB BỘ ĐỆM` | Subtext: *32.768 mẫu RAM tĩnh (50% SRAM)*
  - *Bottom Left Column (40%):* Card: Thông tin & Phân công kỹ thuật (Topic 1, STM32F401CCU6 84 MHz, HW, FW Khối thu thập DMA, SW).
  - *Bottom Right Column (60%):* **Traceable Comparison Table (4 rows × 3 cols)**:
    - Headers: `Chỉ tiêu` (HUST Red background) | `Yêu cầu đề bài` | `Thiết kế hiện tại`
    - Row 1: Số kênh: $\ge 2$ $\rightarrow$ 8 kênh logic (PA0 – PA7)
    - Row 2: Tần số lấy mẫu: $\ge 1\text{ kHz}$ $\rightarrow$ Cấu hình: 6 MHz (ARR=13) | Giới hạn thực tế: Đang xác minh
    - Row 3: Bộ đệm: Không bắt buộc $\rightarrow$ 32.768 mẫu (32 KiB tĩnh)
    - Row 4: Mạch bảo vệ: 12V DC / 200V xung 1ms $\rightarrow$ R-C-Diode (Sơ đồ mạch đã có; đang đo kiểm an toàn)
- **Speaker Notes (35s):**
  > "Kính thưa thầy và các bạn, đại diện cho nhóm, em xin báo cáo tiến độ Đề tài 1: Thiết kế và xây dựng thiết bị Logic Analyzer 8 kênh trên nền tảng vi điều khiển STM32F401CCU6. So với yêu cầu tối thiểu của đề bài là 2 kênh và tần số lấy mẫu 1 kHz, thiết kế của nhóm hướng tới cấu hình 8 kênh logic, tần số lấy mẫu tối đa 6 MHz và bộ đệm lưu trữ 32 KiB. Tiến độ triển khai tập trung vào 3 phần việc chính: mạch bảo vệ đầu vào, khối thu thập dữ liệu trên firmware và phần mềm hiển thị trên máy tính. Sau đây, em xin trình bày kiến trúc tổng thể của hệ thống."

### Slide 3: 02 · Kiến trúc Hệ thống & Luồng Dữ liệu (35s)
- **Visual Structure:**
  - *Top Half (Signal Pipeline):* **Sơ đồ Luồng Tín hiệu Toàn chuỗi 4 Tầng kết nối mũi tên**:
```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ 1. ĐẦU DÒ & KẸP │       │ 2. THU THẬP MCU │       │ 3. TRUYỀN THÔNG │       │ 4. DESKTOP APP  │
│  8 Que đo vào   │  ──►  │  TIM1 nhịp 6MHz │  ──►  │  USB FS CDC 12M │  ──►  │  PyQt5 GUI      │
│  R1 = 1 kΩ      │       │  DMA2 đọc IDR   │       │  Gói khối 512B  │       │  8 Kênh sóng    │
│  Diode BAT54S   │       │  RAM đệm 32 KiB │       │  Khung 32.776B  │       │  Giải mã UART/  │
│  Tụ C1 = 22 pF  │       │  TIM2 đếm dừng  │       │  Chống nghẽn    │       │  I2C / SPI      │
└─────────────────┘       └─────────────────┘       └─────────────────┘       └─────────────────┘
```
  - *Middle Bar (Packet Framing):* **Sơ đồ Cấu trúc Khung Gói tin 32.776 Byte**:
```text
┌──────────────┬──────────┬───────────────┬────────────────────────────────┬──────────────┐
│ Header (2B)  │ Cmd (1B) │ Length (4B)   │       Dữ liệu mẫu (32.768B)    │ Checksum (1B)│
│  0x5A  0xA5  │   0x03   │ 32768 (0x8000)│ D0..D7 của 32.768 thời điểm đo │   XOR Byte   │
└──────────────┴──────────┴───────────────┴────────────────────────────────┴──────────────┘
```
  - *Bottom Row:* 2 Card tóm tắt:
    - Card trái: Cơ chế Thu thập Ngoại tuyến (DMA ghi đè RAM 32 KiB tự động, TIM2 One-Pulse ngắt dừng an toàn).
    - Card phải: Ranh giới Xác minh Thực nghiệm (Mô phỏng LTspice 1 kênh vs MCU/PC đã chạy thật Kênh 0).
- **Speaker Notes (35s):**
  > "Kiến trúc hệ thống được chia làm 4 khối xử lý khép kín: Đầu tiên, tín hiệu từ que đo đi qua mạch bảo vệ đầu vào gồm trở hạn dòng R1 và diode BAT54S trước khi vào các chân GPIO của chip. Phần này nhóm đang mô phỏng trên LTspice. Tiếp theo, Timer 1 phát nhịp để DMA tự động bốc dữ liệu từ GPIOA->IDR ghi vào mảng 32 KiB trong RAM một cách liên tục, không làm nghẽn CPU. Timer 2 đếm đủ 80% số mẫu sau trigger thì kích hoạt ngắt để dừng lấy mẫu. Dữ liệu sau đó được đóng thành khung truyền chuẩn 32.776 byte rồi chia thành các khối 512 byte truyền qua cổng USB ảo CDC lên máy tính. Cuối cùng, phần mềm máy tính nhận dữ liệu, vẽ dạng sóng lên màn hình và giải mã giao thức. Sau đây là kết quả mô phỏng phần cứng."

### Slide 4: 03 · Phần cứng – Mạch Bảo vệ Đầu vào (40s)
- **Visual Structure:**
  - *Left Column (45%):* **Sơ đồ Nguyên lý Mạch Kẹp Áp 1 Kênh (R-C-Diode Schematic)**:
```text
                            Đường Nguồn Chung Rail +3.3V
                                   │
                                   ▲ Diode D1 (BAT54S) - Ghim áp dương ~3.6V
                                   │
Đầu vào Vin ───[ R1: 1 kΩ ]───●───●───●──────► Ngõ ra Vout ──► PA0 – PA7 (IDR)
                              │   │   │
                              │   │   ═╡ Tụ C1: 22 pF (Lọc sườn xung & nhiễu)
                              │   │   │
                              │   ▼ Diode D2 (BAT54S) - Kẹp áp âm ~ -0.3V
                              │   │
                             GND GND GND
```
    - Thẻ nguyên lý kẹp áp: `Vin > +3.3V` D1 dẫn thoát dòng lên 3.3V; `Vin < 0V` D2 dẫn xả dòng từ GND; bảo toàn sườn xung 1 MHz.
  - *Right Column (55%):* **Visual Proof Box** (Khung đồ thị LTspice kẹp quá áp và xung vuông 1 MHz) kèm Callout Notes: Ghim áp an toàn tại N_PROTECT, không méo sườn xung 1 MHz. Chú thích rõ: Mức 200V và bo mạch PCB thuộc mốc tiếp theo.
- **Speaker Notes (40s):**
  > "Về phần cứng, mạch bảo vệ đầu vào là yêu cầu bắt buộc của đề bài để tránh làm cháy chip. Nhóm thiết kế mạch gồm điện trở 1 kΩ để cản bớt dòng quá áp, đôi diode Schottky BAT54S để ghim áp về 3.3V và GND, cùng một tụ nhỏ 22 pF. Khi mô phỏng 4 kịch bản trên LTspice, mạch ghim điện áp rất tốt khi gặp quá áp dương 20V và xung âm 30V trong 1 mili-giây; đồng thời ở tần số 10 kHz và 1 MHz, xung vuông đi qua mạch vẫn giữ nguyên dạng, không bị méo góc. Nhóm xin báo cáo rõ: đây mới là mô phỏng trên một kênh. Việc đo đạc dòng điện cụ thể, thử nghiệm xung 200V thật và làm mạch in sẽ được thực hiện ở các tuần tiếp theo. Sau đây là phần firmware."

### Slide 5: 04 · Firmware – Khối Thu thập Tín hiệu & Xác minh Sơ bộ (50s)
- **Visual Structure:**
  - *Left Column (50%):* **Sơ đồ Cơ chế DMA Vòng & Thuật toán Duỗi Mảng (Circular DMA & Unrolling Diagram)**:
```text
         VÒNG TRÒN DMA (32 KiB)                       MẢNG DUỖI THẲNG (UNROLLED)
             ┌───────────┐
       ┌─────┤ write_pos ├─────┐              t0 (Cũ nhất)     t6554 (Trigger)    t32767 (Mới)
       │     └─────┬─────┘     │             ┌───────────────┬─────────────────┬───────────────┐
  20% Pre-Trig     │     80% Post-Trig       │ 6.554 mẫu     │   26.214 mẫu    │               │
  (Ghi đè liên tục)│     (TIM2 đếm dừng) ──► │ (Pre-trigger) │ (Post-trigger)  │ Khung 32 KiB  │
       │           ▼           │             └───────────────┴─────────────────┴───────────────┘
       └──────[TRIGGER]────────┘                            ▲
                                                   Cố định danh định 20%
```
    - Nguyên lý: Đọc xoay vòng từ `write_pos` đưa mẫu cũ nhất về `t0`, định vị điểm trigger danh định cố định tại mẫu 6.554 (20% bộ đệm).
  - *Right Column (50%):* **Bảng Kết quả Kiểm thử Tự động Thực tế (4 rows × 3 cols)** trích từ test script chạy trên kit WeAct Black Pill:
    - Ping/Pong: `Verified` (Firmware v1.0.0)
    - Khung truyền 32.776B & USB 4096B: `Verified` (Truyền 0.062s, Checksum XOR khớp 100%)
    - Loopback Kênh 0 (PA9 $\rightarrow$ PA0): `Verified` (90 transitions, giải mã chuẩn 'TEST_LA_2026\r\n')
    - Bắt cạnh Trigger & Jitter: `Verified` (Bắt đúng mẫu 6554, sai số Jitter = 0 mẫu)
    - Chú thích: Đã kiểm chứng 100% PASS trên kit thật; trễ ngắt ISR đạt 18 clock cycles.
- **Speaker Notes (50s):**
  > "Phần firmware được thiết kế để lấy mẫu đều đặn và không làm nghẽn CPU. Timer 1 phát nhịp để DMA tự động chuyển byte từ cổng GPIO vào mảng 32 KiB trong RAM. Timer 2 đếm đủ 80% số mẫu sau trigger thì kích hoạt ngắt để dừng lấy mẫu, sau đó sắp xếp lại mảng để đưa mẫu cũ nhất về đầu và điểm trigger về đúng vị trí danh định. Khối thu thập dữ liệu chạy hoàn toàn tự động bằng phần cứng; module phát xung UART loopback chỉ dùng để tự kiểm tra. Bằng script Python tự động, nhóm đã kiểm tra thành công việc bắt tay kết nối, tính toàn vẹn của gói tin 32 KiB và đọc chuẩn luồng ký tự UART 115.2 kbps trên Kênh 0. Xin lưu ý 6 MHz là tần số cấu hình timer; việc đo tải thực tế và đo trễ ngắt đang được nhóm tiến hành. Sau đây là phần mềm máy tính."

### Slide 6: 05 · Phần mềm PC & Video Thực nghiệm (65s)
- **Visual Structure:** 35:65 Split Layout.
  - *Left Column (35%):* 2 Cards:
    - Card 1: Chức năng Desktop (PyQt5 Dark Mode, 8 kênh sóng, Cursors A/B Δt & 1/Δt, UART Verified, I2C/SPI Implemented).
    - Card 2: 4 Bước trong Video (0-7s USB, 7-17s Capture, 17-26s Waveform, 26-35s Zoom UART & Giải mã).
  - *Right Column (65%):* **Video Showcase Box (16:9 viền đỏ HUST)** định vị video demo 35s từ kit STM32 qua cáp USB CDC lên giao diện PC.
- **Speaker Notes (65s):**
  > "Phần mềm máy tính được viết bằng Python với PyQt5 và pyqtgraph để vẽ đồ thị mượt mà. Ứng dụng hiển thị được 8 kênh sóng, có hai con trỏ A và B để đo thời gian và tích hợp bộ giải mã UART, I2C, SPI. Trong đó, giải mã UART đã chạy tốt với tín hiệu thật. Kính mời thầy và các bạn xem đoạn video ngắn 35 giây ghi lại quá trình phần mềm chạy thực tế với kit STM32. (Phát video: 35s) [Thuyết minh trong video]: 'Ứng dụng kết nối cổng USB, bấm lấy mẫu và nhận ngay gói dữ liệu 32 KiB. Sóng trên Kênh 0 hiện rõ các mức 0 và 1 của tín hiệu UART, đo chuẩn độ rộng từng bit và giải mã chính xác chuỗi ký tự truyền đi.' Sau đây, em xin tổng kết tiến độ và kế hoạch các tuần tiếp theo."

### Slide 7: 06 · Đánh giá Tiến độ, Rủi ro & Kế hoạch Tiếp theo (35s)
- **Visual Structure:** 58:42 Split Layout.
  - *Left Column (58%):* **Workstream Milestone Matrix (8 rows × 3 cols)** (Font 14.5 pt):
    - HW Mô phỏng 1 kênh: `Completed` | HW Đo dòng áp, 200V, PCB: `In Progress`
    - FW Khối thu thập DMA 32 KiB: `Completed` | FW Test Kênh 0: `Completed` | FW Tải 6MHz & trễ: `In Progress`
    - SW PyQt5 & UART: `Completed` | SW I2C/SPI cảm biến: `In Progress`
    - Tích hợp 8 kênh toàn chuỗi: `Pending`
  - *Right Column (42%):*
    - Top Card: Rủi ro kỹ thuật (Chịu xung 200V, quá áp nguồn 3.3V, sai số trễ ngắt).
    - Bottom Card: **Sơ đồ Lộ trình 3 Bước Dạng Trục Thời gian (Visual Step Timeline)**:
```text
┌─────────────────────────────────┐     ┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│        [MỐC 1 · TUẦN 1]         │     │        [MỐC 2 · TUẦN 2]         │     │        [MỐC 3 · TUẦN 3]         │
│  Mô phỏng 200V / 1ms trên 1 kênh│ ──► │  Gia công hàn mạch bảo vệ thật  │ ──► │  Lắp ráp hoàn chỉnh thiết bị    │
│  Thiết kế bo mạch in PCB 8 kênh │     │  Đo kiểm cảm biến ngoài I2C/SPI │     │  Báo cáo tổng kết & Video demo  │
└─────────────────────────────────┘     └─────────────────────────────────┘     └─────────────────────────────────┘
```
- **Speaker Notes (35s):**
  > "Để kết luận bài báo cáo: khối thu thập dữ liệu trên firmware, việc truyền dữ liệu qua USB, giao diện vẽ sóng và giải mã UART đều đã hoạt động tốt. Luồng kiểm tra bằng dây nối loopback đã chạy ổn định, trong khi việc đo giới hạn 6 MHz, thử nghiệm an toàn xung 200V và cắm cảm biến I2C, SPI ngoài là các công việc nhóm đang tiếp tục làm. Trong 3 tuần tới, nhóm sẽ hoàn thành mô phỏng xung 200V, làm mạch in bảo vệ 8 kênh và ghép nối đo kiểm với thiết bị thật bên ngoài. Nhóm em xin cảm ơn thầy và các bạn đã lắng nghe. Rất mong nhận được góp ý và câu hỏi từ thầy và các nhóm phản biện."

### Slide 8: Cảm ơn & Hỏi đáp (15s)
- **Visual Structure:** Centered HUST Logo, Red Divider, Large Title: CẢM ƠN THẦY VÀ CÁC BẠN ĐÃ LẮNG NGHE!
- **Subtitle:** PHIÊN HỎI ĐÁP & PHẢN BIỆN ĐỀ TÀI · Logic Analyzer 8 Kênh 6 MHz · STM32F401CCU6 Development Board
- **Speaker Notes (15s):**
  > "Nhóm em xin chân thành cảm ơn thầy và các bạn. Rất mong nhận được những nhận xét, góp ý và câu hỏi phản biện từ thầy và các nhóm bạn!"
