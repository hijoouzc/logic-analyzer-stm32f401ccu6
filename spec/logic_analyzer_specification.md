# Baseline Logic Analyzer Specification
**Tên dự án:** Thiết kế và xây dựng thiết bị Logic Analyzer đơn giản (Topic 1)  
**Nhóm sinh viên thực hiện:** Nguyễn Văn Hội (20233419) – Nguyễn Văn Khang (20233458) – Nguyễn Trường Giang (20233374)  
**Nền tảng phần cứng:** STM32F401CCU6 (Black Pill V3.0) + Mạch bảo vệ đầu vào 8 kênh + Python Desktop GUI  

---

## 1. Giới thiệu và Phạm vi Kỹ thuật (Introduction & Technical Scope)
* **Quy mô hệ thống:** Thiết bị Logic Analyzer 8 kênh đồng bộ (PA0–PA7), tốc độ lấy mẫu tối đa 6 MHz, bộ đệm vòng 32.768 mẫu (chiếm 32 KB, bằng 50% trong tổng số 64 KB SRAM của chip STM32F401CCU6). Thu thập dữ liệu Offline trong bộ đệm và truyền lên PC phân tích.
* **Mạch bảo vệ đầu vào:** 
  * Chịu điện áp một chiều liên tục: Tối thiểu +12 V đến +15 V cấp đồng thời trên cả 8 kênh (đáp ứng đúng yêu cầu sàn 12 V của đề bài), hoặc ±20 V khi cấp trên 1 kênh đơn lẻ.
  * Chịu xung vuông đơn lẻ: Tối thiểu ±200 V độ rộng đến 1 ms cấp trên 1 kênh đơn lẻ (đáp ứng đúng yêu cầu sàn 200 V / 1 ms của đề bài và được chứng minh qua mô phỏng).
* **Mô phỏng LTspice:** Bắt buộc kiểm tra quá áp DC $\pm 20\text{ V}$, xung vuông đơn lẻ $\pm 200\text{ V}$ độ rộng $1\text{ ms}$ và dạng xung 10 kHz–1 MHz (mở rộng đến 3 MHz). Mô hình nguồn 3,3 V không được dùng nguồn áp lý tưởng để kết luận an toàn: phải thể hiện LDO có giới hạn dòng/biên áp, tải MCU, tụ đầu ra và phần tử shunt/kẹp có model hoặc tham số phù hợp. Vì LDO thông thường chỉ điều tiết dòng cấp ra, không hút dòng bơm ngược, phải đo điện áp rail cực đại, dòng tải, dòng kẹp đi vào rail và công suất phần tử xả; chỉ đạt khi rail vẫn dưới giới hạn của linh kiện trong mọi ca mô phỏng. Với tín hiệu logic, đo thời gian vượt $V_{IH} \ge 2.0\text{ V}$ và xuống dưới $V_{IL} \le 0.8\text{ V}$.
* **An toàn thử nghiệm:** Xung cao áp 200 V chỉ chứng minh qua mô phỏng theo đúng yêu cầu đề bài; tuyệt đối không cấp xung 200 V vào kit thật trong phòng thí nghiệm để đảm bảo an toàn thiết bị và người dùng. Bổ sung cầu chì tự phục hồi PTC 500 mA trên đường nguồn USB bảo vệ máy tính PC.
* **Phương thức nạp & giao tiếp:** Sử dụng một cổng kết nối USB Type-C duy nhất phục vụ đồng thời cho 3 mục đích: cấp nguồn 5 V bảo vệ qua cầu chì PTC, truyền dữ liệu Full-Speed 12 Mbps lên PC qua USB-CDC, và nạp firmware trực tiếp thông qua STM32 ROM DFU Bootloader (`0483:df11`) bằng STM32CubeProgrammer (hoàn toàn không bắt buộc mạch nạp rời ST-Link, vẫn duy trì chân SWD PA13/PA14 cho debug chuyên sâu).
* **Giao thức giải mã:** Tích hợp bộ giải mã đa giao thức hoàn chỉnh trên Desktop GUI, hỗ trợ phân tích toàn diện 3 chuẩn giao tiếp thông dụng: UART (8N1, baudrate tùy biến), SPI (Mode 0..3, MSB/LSB first) và I²C (phát hiện Start/Stop condition, Address 7-bit/10-bit, Read/Write, ACK/NACK).
* **Phạm vi loại trừ (Non-Goals):** Không streaming thời gian thực ở tốc độ cao; không dùng màn hình LCD rời trên kit; không đo điện áp Analog.

---

## 2. Cơ sở và Giả định Thiết kế (Design Basis & Assumptions)
1. **Xung nhịp hệ thống (SYSCLK):** Cấu hình cố định ở mức **84 MHz** (từ thạch anh ngoài HSE 25.0 MHz của kit Black Pill V3.0 qua PLL với $M=25, N=336, P=4$) để các tần số lấy mẫu là các ước số nguyên chẵn (6 MHz, 3 MHz, 2 MHz, 1 MHz...), triệt tiêu sai số chu kỳ (jitter). Bộ chia USB PLL ($Q=7$) tạo chính xác $48.0\text{ MHz}$ cho USB Full-Speed OTG.
2. **Luận giải độ lệch kênh (Channel-to-Channel Skew):**
   * **Skew tại thời điểm chốt mẫu = 0 ns:** 8 kênh nằm trọn vẹn trên Port A (PA0–PA7), được DMA2 đọc đồng thời trong cùng 1 chu kỳ bus AHB1 thông qua thanh ghi `GPIOA->IDR`.
   * **Skew tương đối toàn hệ thống $\le 2\text{ ns}$ (Ước lượng lý thuyết, sẽ đo kiểm thực tế trên kit):** Do độ lệch thời gian truyền $\Delta t_{pd}$ giữa các cổng của IC đệm 74LVC245 ($\sim 0.5 - 1.5\text{ ns}$), dung sai linh kiện $R_1, C_1$ ($\pm 1\% - \pm 5\%$ gây lệch hằng số thời gian $\tau = RC$), cùng sai lệch chiều dài đường mạch PCB/probe dây nối ($\sim 0.1 - 0.2\text{ ns}$).
   * **Sai số lượng tử hóa thời gian:** Chu kỳ lấy mẫu ở 6 MHz là $T_s = 166.7\text{ ns}$, đây là sai số lấy mẫu chi phối áp đảo so với độ lệch phần cứng 2 ns của hệ thống.
3. **Ngưỡng nhận diện Logic:** IC đệm 74LVC245 (cấp nguồn 3.3 V) có ngưỡng $V_{IH} = 2.0\text{ V}$ và $V_{IL} = 0.8\text{ V}$, tương thích an toàn với cả chuẩn 3.3 V / 5 V CMOS và TTL.

---

## 3. Luận Chứng Kiến Trúc & Đặc Tả Giải Pháp Kỹ Thuật (System Architecture Rationale & Technical Decisions)

### 3.1. Ma trận Tổng hợp Kiến trúc Toàn Hệ thống (Full-System Architecture Matrix)

| STT | Khối Thiết kế | Giải pháp Lựa chọn (Selected Architecture) | Phương án Cân nhắc (Alternatives Evaluated) | Luận chứng Đánh đổi Kỹ thuật (Technical Trade-off & Rationale) |
| :---: | :--- | :--- | :--- | :--- |
| **S1** | **Vi điều khiển & Thu thập DMA** | STM32F401CCU6 (84 MHz, 64 KB RAM) + TIM1 + `DMA2_Stream5 Channel 6` đọc song song `GPIOA->IDR` ở chế độ **Direct Mode** | Arduino Uno, STM32F103; hoặc DMA FIFO Mode | DMA2 trên Cortex-M4 kết nối trực tiếp bus AHB1 giúp đọc 8 kênh song song chỉ trong 1 clock cycle không qua CPU; 64 KB SRAM chứa vừa vặn bộ đệm 32 KB (50% RAM); tích hợp USB Full-Speed OTG độc lập không cần IC chuyển đổi USB-UART.<br>• **Giữ Direct Mode (`FIFOMode=DISABLE`):** Tránh bẫy kẹt dữ liệu tồn dư trong FIFO (Residual FIFO Data trap theo RM0368 Mục 9.3.11) khi TIM2 dừng DMA đột ngột, bảo đảm 100% mẫu được ghi tức thời xuống SRAM.<br>• **Khóa trần 6 MHz:** Đảm bảo 14 clock cycles/mẫu cho DMA phục vụ an toàn, triệt tiêu nguy cơ quá tải yêu cầu DMA (DMA Request Overrun) và tương thích hoàn hảo với băng thông analog của mắt lọc bảo vệ $1\text{ k}\Omega \parallel 22\text{ pF}$ + 74LVC245. |
| **S2** | **Mạch Bảo vệ Đầu vào** | Mạng bù R-C ($1\text{ k}\Omega // 22\text{ pF}$) + Diode kép BAT54S + IC đệm 74LVC245 | Chỉ dùng điện trở nối tiếp + Diode Zener thông thường | Diode Zener có điện dung ký sinh lớn ($>50\text{ pF}$) làm méo dạng xung ở tần số cao. BAT54S ($C_d \approx 7-10\text{ pF}$, $I_{FSM} = 600\text{ mA}$) kết hợp trở cắm $1\text{ k}\Omega$ chịu xung 200 V an toàn. Tụ bù $C_1 \approx 22\text{ pF}$ bù trừ điện dung tải, tối ưu thời gian chuyển mức $t_r, t_f < 20\%$ chu kỳ xung tại 3 MHz. |
| **S3** | **Cơ chế Trigger & Pre-sampling 2 Pha** | Circular DMA Pre-Trigger (20% Pre / 80% Post) + **Bộ đếm TIM2 Phần cứng 2 Pha** + Low-power `__WFI()` 100% + **State-Before-Unmask** | Bắt ngắt EXTI mới bật Timer; hoặc CPU polling con trỏ NDTR | • **Đếm Pre-trigger bằng phần cứng TIM2:** Pha 1 cấu hình `TIM2->ARR = 6553` đếm đúng 6.554 mẫu pre-trigger rồi tự dừng bằng OPM. Ngắt `TIM2_IRQHandler` nạp lại `ARR = 26213` (80% post-trigger) và unmask `EXTI->IMR`. Ở Free-run, TIM2 nạp ngay `ARR = 32767` đếm trọn 32.768 mẫu không ngắt.<br>• **Giải phóng 100% Bus AHB1 & 0% Jitter:** CPU ngủ sâu `__WFI()` trọn vẹn trong cả `PRE_SAMPLING` và `WAIT_TRIGGER`, không sinh bất kỳ giao dịch bus nào, nhường 100% bus cho DMA2.<br>• **Triệt tiêu Race Condition:** Cập nhật `g_la_state = LA_STATE_WAIT_TRIGGER` và chốt rào nhớ `__DSB()` **TRƯỚC KHI** unmask `EXTI->IMR`. Cô lập Testgen PA9 khi không ở `IDLE` hoặc `WAIT_TRIGGER`. |
| **S4** | **Bộ đếm Post-Trigger & Inline ISR** | TIM1 Master cấp xung TRGO qua `ITR0` cho TIM2 (Slave One-Pulse, ARR = 26213) + Inline trực tiếp lệnh kích hoạt vào ISR + **Memory Barrier `__DSB()`** | Polling phần mềm thanh ghi NDTR; hoặc dùng Timer độc lập | TIM2 ghép tầng phần cứng đếm chính xác tuyệt đối 26.214 mẫu (sai số 0%). Inline trực tiếp `TIM2->CR1 |= TIM_CR1_CEN` vào `EXTI_IRQHandler` đưa trễ ngắt về 18 clock cycles ($\approx 214\text{ ns}$), sai số trigger vật lý chỉ $\approx 1$ mẫu ở 6 MHz.<br>• **Chốt dừng chính xác:** Bổ sung `__DSB()` ngay sau lệnh dừng `TIM1->CR1 &= ~TIM_CR1_CEN` để xả sạch Write Buffer trên cầu AHB-to-APB trước khi dừng DMA và chốt con trỏ `NDTR`. |
| **S5** | **Giao thức & Non-blocking Streaming** | Khung dữ liệu 32.776 B; máy trạng thái Non-blocking USB-CDC khối lớn **4096B**; Checksum XOR 32-bit unrolled; **Tối ưu TxFIFO 320 words** | Truyền chuỗi ASCII qua UART rời; hoặc chia nhỏ 512B chờ lặp 64 lần | Non-blocking streaming phân đoạn khối 4096B ($64 \times 64\text{ B}$ packets) giảm 8 lần số chu kỳ chuyển giao lặp trong `main()`, tận dụng tối đa thanh ghi `DIEPTSIZx` 19-bit và TxFIFO 896B để đẩy tốc độ truyền chạm trần vật lý $1.12\text{ MB/s}$ ($\sim 28\text{ ms}$ cho 32KB). Checksum XOR 32-bit unrolled 8x hoàn tất trong $< 0.12\text{ ms}$. |
| **S6** | **Bảo vệ Nguồn & Giới hạn Rail** | Trở cắm Through-hole $1\text{ k}\Omega$ (1W–2W Metal Film chịu xung) + Tầng ghim shunt TL431/Zener 1W trên rail 3.3V + PTC 500mA | Dùng trở dán SMD 0805 + TVS mà không tính đường dòng ngược qua LDO | Xung vuông 200 V / 1 ms bơm dòng đỉnh $196.3\text{ mA}$ ($38.5\text{ mJ}$) vào rail. Trở cắm 1W–2W chịu xung hấp thụ năng lượng an toàn; tầng ghim shunt hấp thụ dòng ngược bảo vệ rail $\le 4.0\text{ V}$ vì LDO onboard không hút dòng; PTC 500mA bảo vệ cổng USB máy tính. |
| **S7** | **Giao diện & Đa Giải mã Giao thức** | Desktop GUI viết bằng PyQt5 + pyqtgraph + vectorization NumPy; tích hợp bộ giải mã đa giao thức UART, SPI, I²C | Vẽ bằng Matplotlib/Tkinter; hoặc giải mã trực tiếp trên MCU | NumPy giải nén 32 KB bitstream chỉ mất $< 0.8\text{ ms}$; pyqtgraph render đồ thị 8 kênh ở 60 FPS mượt mà. Giải mã đa giao thức trực tiếp trên PC giúp giải phóng tài nguyên MCU và cho phép cấu hình lại tham số phân tích nhiều lần mà không cần capture lại. |
| **S8** | **Phương thức Nạp & Debug** | Nạp firmware qua cổng USB Type-C bằng STM32 ROM DFU Bootloader (`0483:df11`); duy trì SWD (PA13/PA14) cho ST-Link | Bắt buộc dùng mạch nạp rời ST-Link; hoặc tự viết bootloader Flash | Tận dụng ROM bootloader có sẵn của ST không thể bị brick hoặc ghi đè, không phụ thuộc thiết bị nạp rời, nạp trực tiếp qua cáp Type-C tiện dụng. Vẫn duy trì cấu hình chân SWD cho debug chuyên sâu. |

### 3.2. Luận chứng Phân tích Kỹ thuật Chi tiết theo Từng Khối Chức năng

#### 1. Khối Vi điều khiển & Thu thập Dữ liệu (MCU Core & Sampling Engine)
* **Giải pháp lựa chọn:** STM32F401CCU6 (ARM Cortex-M4F @ 84 MHz, Flash 256 KB, SRAM 64 KB). Sử dụng sự kiện Update của TIM1 kích hoạt `DMA2_Stream5 Channel 6` đọc song song 8 bit từ `GPIOA->IDR` vào mảng tĩnh `la_capture_buffer[32768]` ở chế độ **Direct Mode** (`FIFOMode = DMA_FIFOMODE_DISABLE`) và Circular.
* **Luận chứng kỹ thuật & Đánh đổi tài nguyên:**
  * Tại tần số lấy mẫu cực đại 6 MHz, chu kỳ lấy mẫu là $T_s = \frac{1}{6\text{ MHz}} \approx 166.7\text{ ns}$ (tương đương đúng 14 chu kỳ clock của CPU ở 84 MHz). Nếu dùng CPU đọc cổng và ghi vào RAM bằng lệnh phần mềm, việc xử lý vòng lặp, kiểm tra cờ và lưu bộ nhớ sẽ chiếm trọn 100% thời gian CPU, dễ bị giật jitter do ngắt hệ thống.
  * Bộ điều khiển DMA2 trên STM32F4 là Master độc lập kết nối thẳng vào ma trận Bus AHB1. DMA2 đọc thanh ghi `GPIOA->IDR` và ghi trực tiếp vào SRAM trong 1 chu kỳ bus mà hoàn toàn không tiêu tốn chu kỳ lệnh nào của CPU Cortex-M4, giải phóng hoàn toàn CPU và triệt tiêu triệt để hiện tượng trượt mẫu hay jitter.
  * **Tại sao bắt buộc chọn Direct Mode thay vì FIFO Mode (RM0368 Mục 9.3.11):** Khi dùng DMA FIFO Mode với ngưỡng đóng gói (Burst 4 words = 16 bytes), nếu quá trình capture bị dừng đột ngột (do TIM2 ngắt dừng TIM1 ở mẫu 26.214), các byte mẫu nằm dở dang trong FIFO nội của DMA chưa đạt ngưỡng 16 bytes sẽ **bị kẹt lại (Residual FIFO Data) và bị hủy khi tắt DMA Stream**, dẫn đến mất các mẫu cuối cùng và làm lệch thanh ghi `NDTR`. Ở Direct Mode, mỗi byte đọc từ GPIO được ghi thẳng lập tức xuống SRAM, bảo đảm 100% mẫu được bảo toàn nguyên vẹn.
  * **Tại sao khóa trần tần số ở 6 MHz (thay vì 10.5 MHz / 12 MHz):** Ở 12 MHz (chu kỳ 83.3 ns), giữa 2 yêu cầu DMA chỉ có đúng 7 chu kỳ clock 84 MHz; DMA Direct Mode sẽ chạm trần thời gian phục vụ bus, dễ phát sinh lỗi tràn yêu cầu DMA (DMA Request Overrun). Đồng thời, mắt lọc analog bảo vệ đầu vào $1\text{ k}\Omega \parallel 22\text{ pF}$ kết hợp điện dung ký sinh có hằng số thời gian $\tau \approx 30\text{ ns}$ ($t_r, t_f \approx 60-80\text{ ns}$), nếu chạy 12 MHz thì nửa chu kỳ chỉ có $41.6\text{ ns}$ khiến xung vuông bị méo dạng hoàn toàn. Mức 6 MHz bảo đảm biên an toàn (Safety Margin) $> 100\%$ cho cả tầng analog lẫn bus kỹ thuật số.
  * Dung lượng SRAM 64 KB được phân bổ tối ưu: Mảng mẫu 32 KB chiếm đúng 50% RAM, 32 KB còn lại dành cho Stack, Heap, HAL/USB Descriptors, và Ring-buffer truyền nhận lệnh.

#### 2. Khối Mạch Bảo vệ Ngõ vào & Bù Tần số Cao (Input Protection Front-End)
* **Giải pháp lựa chọn:** Mạng bù R-C ($R_1 = 1\text{ k}\Omega // C_1 = 22\text{ pF}$) kết hợp Diode Schottky kép BAT54S ghim áp vào rail 3.3V / GND và IC đệm logic 74LVC245.
* **Luận chứng kỹ thuật & Đáp ứng xung:**
  * Diode Zener thông thường có điện dung tiếp giáp lớn ($C_z > 50\text{ pF}$), tạo bộ lọc thông thấp với $R_1$ làm méo sườn xung nghiêm trọng tại tần số $> 1\text{ MHz}$. BAT54S có điện dung tiếp giáp cực nhỏ ($C_d \approx 7\text{ – }10\text{ pF}$), sụt áp thuận thấp ($V_F \approx 0.38\text{ V}$), ghim an toàn điện áp ngõ vào trong dải $-0.4\text{ V} \le V_{\text{in}} \le 3.7\text{ V}$.
  * Mạng bù tần số cao $C_1 \approx 22\text{ pF}$ song song với $R_1 = 1\text{ k}\Omega$ tạo thành mạch bù phân áp tần số cao với điện dung tải ngõ vào ($C_{\text{load}} = C_{\text{BAT54S}} + C_{\text{in\_74LVC245}} + C_{\text{trace}} \approx 16\text{ pF}$), đảm bảo dạng sóng xung vuông 1 MHz – 3 MHz có thời gian chuyển mức $t_r, t_f < 20\%$ chu kỳ, thỏa mãn tiêu chí vượt ngưỡng logic $V_{IH}=2.0\text{ V}$ và $V_{IL}=0.8\text{ V}$.
  * IC đệm 74LVC245 cách ly tuyệt đối vi điều khiển STM32 khỏi mọi nguy cơ sốc điện áp từ đầu đo, đồng thời chuẩn hóa trở kháng và mức logic tương thích an toàn với cả chuẩn TTL (5V) và CMOS (3.3V).

#### 3. Khối Quản lý Trigger & Hardware Pre-sampling 2 Pha (Two-Phase Hardware Counter & 100% WFI)
* **Giải pháp lựa chọn:** Bộ đệm xoay vòng 32 KB chia tỷ lệ danh định 20% Pre-trigger (6.554 mẫu) và 80% Post-trigger (26.214 mẫu). Tích hợp kiến trúc **TIM2 Two-Phase Hardware Counter** ghép tầng từ TIM1 TRGO, kỹ thuật **State-Before-Unmask + `__DSB()`** triệt tiêu Race Condition, và đưa CPU vào chế độ **`__WFI()` trong 100% thời gian lấy mẫu**.
* **Luận chứng kỹ thuật & Triệt tiêu Jitter Bus:**
  * **Đếm Pre-trigger hoàn toàn bằng phần cứng Timer Cascade:** Thay vì bắt CPU phải quay vòng lặp polling con trỏ `DMA2_Stream5->NDTR` (gây hao pin và tạo lưu lượng tranh chấp bus AHB1 với DMA2):
    1. Trong pha `PRE_SAMPLING`, TIM2 được nạp $\text{ARR} = 6554 - 1 = 6553$ và kích hoạt ở chế độ One-Pulse Mode.
    2. CPU lập tức vào trạng thái ngủ sâu `__WFI()`. Trong suốt 6.554 chu kỳ lấy mẫu, CPU không hề chạy bất kỳ lệnh nào, nhường **100% băng thông bus AHB1 cho DMA2** đọc GPIO và ghi SRAM với **0% Jitter**.
    3. Ngay khi đếm đủ 6.554 xung phần cứng, `TIM2` tự dừng (nhờ phần cứng OPM) và phát ngắt `TIM2_IRQHandler` (Ngắt lần 1). ISR thực hiện: nạp lại $\text{ARR} = 26214 - 1 = 26213$, reset $\text{CNT} = 0$, gán trạng thái `g_la_state = LA_STATE_WAIT_TRIGGER`, gọi `__DSB()`, unmask `EXTI->IMR`, rồi CPU lại tiếp tục ngủ `__WFI()`!
    4. Ở chế độ Free-Run: Ngay từ đầu nạp $\text{ARR}_{\text{TIM2}} = 32768 - 1 = 32767$, TIM2 đếm một mạch 32.768 mẫu (100% bộ đệm) rồi dừng thẳng, CPU ngủ trọn vẹn không cần thức giấc giữa chừng.
  * **Triệt tiêu Race Condition sống còn:** Để ngăn chặn kịch bản cạnh xung logic xuất hiện tức thì ngay sau lệnh mở ngắt EXTI trong khi trạng thái FSM chưa kịp cập nhật (khiến ISR bỏ qua và hệ thống treo ở `WAIT_TRIGGER`), firmware bắt buộc tuân thủ quy trình nguyên tử: Gán `g_la_state = LA_STATE_WAIT_TRIGGER`, gọi chỉ thị rào nhớ `__DSB()` để bảo đảm biến trạng thái được ghi xuống SRAM, rồi mới thực thi lệnh mở khóa ngắt `EXTI->IMR |= (1U << ch)`.
  * **Cô lập Kênh phát Testgen PA9:** Hàm `la_testgen_process()` chỉ được phép phát chuỗi test 115200 bps khi hệ thống ở trạng thái `LA_STATE_IDLE` hoặc `LA_STATE_WAIT_TRIGGER` (để cung cấp cạnh xung kích hoạt cho loopback PA0). Khi đang ở `ARMED`, `PRE_SAMPLING`, `POST_SAMPLING` hoặc `TRANSFERRING`, testgen bị khóa hoàn toàn, loại bỏ triệt để hiện tượng polling bận 1.3 ms của `HAL_UART_Transmit`, giúp CPU nghỉ trọn vẹn trong `__WFI()`.
  * Trong trạng thái `WAIT_TRIGGER`, CPU thực thi chỉ thị `__WFI()` đưa lõi Cortex-M4 về chế độ Sleep: Dòng tiêu thụ giảm từ $\sim 18\text{ mA}$ xuống $\sim 4\text{ mA}$, triệt tiêu toàn bộ sóng hài nhiễu xung nhịp nội bộ từ bus AHB/APB lan sang các đường tín hiệu đo PA0–PA7. Khi có ngắt EXTI hoặc SysTick, vi điều khiển thức giấc tức thì chỉ sau 2 chu kỳ clock.

#### 4. Khối Bộ đếm Post-Trigger Phần cứng & Giảm thiểu Độ trễ Ngắt (Hardware Post-Counter & Inline ISR)
* **Giải pháp lựa chọn:** Ghép tầng phần cứng (Timer Cascaded) TIM1 Master kích hoạt TIM2 Slave qua liên kết nội bộ `ITR0` ở chế độ One-Pulse Mode (ARR = 26213). Inline trực tiếp lệnh kích hoạt vào các ISR `EXTI0_IRQHandler`..`EXTI9_5_IRQHandler` và chốt dừng bằng rào nhớ `__DSB()`.
* **Luận chứng kỹ thuật & Triệt tiêu Jitter:**
  * TIM2 đóng vai trò bộ đếm phần cứng 32-bit: Nhận trực tiếp xung TRGO từ TIM1 khi có sự kiện Update, đếm chính xác tuyệt đối đúng 26.214 mẫu sau trigger (sai số đếm phần cứng bằng đúng 0%). Ngắt tràn `TIM2_IRQHandler` dừng tức thì TIM1.
  * Để triệt tiêu độ trễ kích hoạt trigger, lệnh `TIM2->CR1 |= TIM_CR1_CEN` được đưa trực tiếp vào đầu hàm phục vụ ngắt EXTI (chỉ mất 6 chỉ thị máy sau khi kiểm tra cờ PR), tiếp theo là khóa `EXTI->IMR` và xóa cờ `EXTI->PR`. Trễ phần cứng từ cạnh xung vật lý đến khi TIM2 đếm giảm xuống chỉ còn $18\text{ clock cycles}$ ($\approx 214\text{ ns}$ @ 84 MHz), đưa sai số trigger vật lý thực tế về mức tiệm cận phần cứng $\approx 1\text{ mẫu}$ ở 6 MHz (so với 2–3 mẫu khi gọi hàm trung gian).
  * **Chốt dừng chính xác bằng Memory Barrier `__DSB()`:** Do cầu nối AHB-to-APB có bộ đệm ghi (Write buffer), lệnh tắt `TIM1->CR1 &= ~TIM_CR1_CEN` trong `TIM2_IRQHandler` được theo sau ngay lập tức bởi chỉ thị `__DSB()`. Điều này bảo đảm xung Update của TIM1 dừng hẳn trên bus APB2 trước khi CPU tắt DMA2 và chốt con trỏ `NDTR`, loại bỏ hoàn toàn sai số $\pm 1$ mẫu của điểm dừng.

#### 5. Khối Giao tiếp USB-CDC & Non-blocking Streaming (4096B Chunking & 32-bit XOR Checksum)
* **Giải pháp lựa chọn:** Giao thức nhị phân khung cố định 32.776 Bytes; cơ chế Buffer Unrolling đưa mẫu cũ nhất $t_0$ về đầu gói; máy trạng thái Non-blocking USB Streaming chia khối lớn **4096 Bytes**; thuật toán tính XOR 32-bit unrolled 8x; cấu hình tối ưu TxFIFO USB OTG_FS 320 words theo RM0368.
* **Luận chứng kỹ thuật & Tối ưu Băng thông:**
  * USB-CDC Full-Speed 12 Mbps đạt tốc độ truyền thực tế $> 1\text{ MB/s}$, hoàn tất truyền toàn bộ 32KB dữ liệu trong $\sim 28\text{ ms}$.
  * **Tối ưu hóa TxFIFO phần cứng USB (RM0368 Mục 22.12.2):** Tận dụng trọn vẹn $1.25\text{ KB} = 320\text{ words}$ Dedicated Packet RAM của USB OTG_FS trên STM32F401: Phân bổ 64 words (256B) cho RxFIFO (thừa cho các lệnh 5B từ PC), 32 words (128B) cho EP0 Control Tx, và dồn **224 words (896 Bytes = 14 packets 64B Bulk IN)** cho TxFIFO1 của CDC Data. Dung lượng 896B cho phép bộ điều khiển USB phần cứng luôn có sẵn dữ liệu phản hồi liên tục các token IN từ Host trong cùng 1 microframe USB, triệt tiêu hiện tượng đói FIFO (FIFO Starvation).
  * **Tăng kích thước khối Chunk từ 512B lên 4096B:** Thanh ghi phần cứng `DIEPTSIZx` của STM32F401 hỗ trợ trường kích thước `XFRSIZ` lên tới 19-bit ($512\text{ KB}$). Trình xử lý ngắt PCD ISR tự động nạp các gói 64B từ RAM vào FIFO qua ngắt `TXFE` mà không cần CPU luồng chính can thiệp. Việc tăng kích thước khối lên 4096B ($64 \times 64\text{ B}$) giảm số chu kỳ chuyển giao lặp trong luồng chính từ 64 lần xuống chỉ còn **8 lần**, loại bỏ độ trễ chờ đợi giữa các khung USB SOF 1ms, đưa thời gian truyền 32KB xuống chạm mức trần vật lý $1.12\text{ MB/s}$ ($\approx 28\text{ ms}$). Biến đếm watchdog $100\text{ ms}$/khối bảo vệ hệ thống không bị treo nếu cáp USB bị rút đột ngột.
  * Thuật toán tính Checksum XOR 32-bit unrolled 8x duyệt trên các từ 32-bit với 4 thanh ghi tích lũy `x0..x3`, sau đó gộp 4 bytes lại bằng 2 phép dịch bit/XOR, đưa thời gian tính toán toàn bộ 32.768 bytes xuống dưới $0.12\text{ ms}$ (tăng tốc gấp ~10 lần so với vòng lặp byte tuần tự).

#### 6. Khối Bảo vệ Nguồn 3.3V & Giới hạn Rail (Surge Clamp & Safe Power Dissipation)
* **Giải pháp lựa chọn:** Điện trở cắm Through-hole $1\text{ k}\Omega$ (1W–2W Metal Film chịu xung) + Tầng ghim shunt TL431/Zener 1W trên rail 3.3V + Cầu chì tự phục hồi PTC 500mA trên đường USB VBUS.
* **Luận chứng kỹ thuật & Phân tích Nhiệt:**
  * Khi gặp xung vuông đơn lẻ $\pm 200\text{ V} / 1\text{ ms}$, dòng đỉnh bơm qua diode kẹp BAT54S vào rail 3.3V đạt $I_{\text{peak}} \approx 196.3\text{ mA}$, công suất tức thời trên trở đầu vào đạt $38.5\text{ W}$ và năng lượng hấp thụ là $38.5\text{ mJ}$. Điện trở dán SMD 0805 thông thường (công suất $0.125\text{ W}$) sẽ bị đánh thủng hoặc cháy đứt; việc sử dụng điện trở cắm Through-hole Metal Film 1W–2W chuyên dụng chịu xung bảo đảm an toàn tuyệt đối cho linh kiện.
  * Do IC ổn áp LDO onboard (AP7343) là bộ điều tiết dòng cấp ra (Source-only), không có khả năng hút dòng (Sink), nếu dòng bơm ngược lớn hơn dòng tiêu thụ của MCU, điện áp rail 3.3V sẽ bị đẩy vọt lên. Tầng kẹp shunt bổ sung trên rail 3.3V hấp thụ toàn bộ dòng xung dư thừa, giữ điện áp rail luôn dưới ngưỡng phá hủy $\le 4.0\text{ V}$. Cầu chì PTC 500mA trên đường VBUS bảo vệ máy tính PC khỏi hiện tượng chập nguồn hoặc quá dòng.

#### 7. Khối Giao diện Đồ họa & Bộ Giải mã Đa Giao thức (Desktop GUI & Multi-Protocol Decoders)
* **Giải pháp lựa chọn:** Phần mềm Desktop GUI xây dựng trên nền tảng Python 3, PyQt5, thư viện đồ họa cao tốc `pyqtgraph` và tính toán vector hóa `numpy`. Tích hợp bộ giải mã đa giao thức trực tiếp trên GUI hỗ trợ UART, SPI và I²C.
* **Luận chứng kỹ thuật & Hiệu năng Đồ họa:**
  * Khác với Matplotlib vẽ lại toàn bộ đồ họa qua CPU (chỉ đạt 5–10 FPS gây giật lag), `pyqtgraph` biên dịch và render đồ thị thông qua OpenGL/Qt GraphicsView, duy trì tốc độ khung hình mượt mà 60 FPS khi hiển thị đồng thời 8 kênh sóng với 32.768 điểm/kênh.
  * Vectorization của NumPy (`np.unpackbits`) giải nén mảng nhị phân 32KB thành 8 mảng logic số riêng biệt chỉ mất $< 0.8\text{ ms}$, hỗ trợ các thao tác thu phóng (zoom) và cuộn (pan) tức thời.
  * Kiến trúc giải mã đa giao thức trên máy tính PC (Host-side Decoding) giải phóng hoàn toàn vi điều khiển STM32 khỏi các tác vụ tính toán nặng, đồng thời mang lại sự linh hoạt tối đa: người dùng có thể điều chỉnh linh hoạt các thông số phân tích (tốc độ baudrate, cực tính xung CPOL/CPHA, ngưỡng điện áp) và chạy lại bộ giải mã nhiều lần trên cùng một tập dữ liệu đã thu thập mà không cần thực hiện lại chu trình capture phần cứng.

#### 8. Khối Phương thức Nạp Firmware & Công cụ Phát triển (Firmware Deployment & Toolchain)
* **Giải pháp lựa chọn:** Nạp firmware trực tiếp qua cổng USB Type-C bằng STM32 ROM DFU Bootloader (`0483:df11`) thông qua công cụ dòng lệnh `STM32_Programmer_CLI`. Duy trì cấu hình chân SWD (PA13/PA14) và cấu hình ST-Link IDE.
* **Luận chứng kỹ thuật & Tiện ích Vận hành:**
  * Kit WeAct Black Pill V3.0 tích hợp sẵn nút bấm BOOT0 và NRST, cho phép kích hoạt ROM Bootloader tích hợp sẵn trong vi điều khiển STM32F401. Phương thức này không thể bị ghi đè, không có nguy cơ brick vi điều khiển và hoàn toàn không cần mạch nạp rời ST-Link, giúp giảm thiểu chi phí và tạo sự gọn nhẹ, cơ động tối đa khi vận hành trong phòng thí nghiệm.
  * Cấu hình chân SWD (PA13/PA14) vẫn được giữ nguyên để tương thích với thiết bị nạp/debug phần cứng ST-Link V2/V3 khi cần đặt breakpoint, phân tích thanh ghi và debug bộ nhớ chuyên sâu.

---

## 4. Đặc tả Kiến trúc và Thiết kế Chi tiết (System Architecture & Detailed Design)

### 4.1. Phần cứng (Hardware Front-End): Giao tiếp & Bảo vệ (TV2)

```text
[Probe x8] --> [R1 = 1kΩ // C1 = 22pF] --+--> [Buffer 74LVC245] --> [STM32 PA0..PA7]
                                         |
                                      [BAT54S]
                                       /    \
                         [Rail 3.3V + Zener 3.6V] [GND]
```

* **Cảnh báo công suất & Danh mục Linh kiện (BOM):**
  * **Trở đầu vào $R_1 = 1\text{ k}\Omega$:** Bắt buộc sử dụng linh kiện cắm (Through-hole) công suất $1\text{ W} - 2\text{ W}$ Metal Film có khả năng chịu xung (pulse-withstanding).
    * *Quá áp một chiều âm $-20\text{ V}$ liên tục:* Diode kẹp xuống $-0.4\text{ V}$, sụt áp trên $R_1$ là $20.4\text{ V}$. Công suất tiêu tán cực đại:
      $$P = \frac{U^2}{R_1} = \frac{(20.4\text{ V})^2}{1000\,\Omega} = 0.416\text{ W}$$
    * *Quá áp một chiều dương $+20\text{ V}$ liên tục:* Diode kẹp lên $3.7\text{ V}$, sụt áp trên $R_1$ là $16.3\text{ V}$. Công suất tiêu tán:
      $$P = \frac{U^2}{R_1} = \frac{(16.3\text{ V})^2}{1000\,\Omega} = 0.266\text{ W}$$
    * *Xung vuông đơn lẻ $200\text{ V}$ độ rộng $1\text{ ms}$ (chuẩn đề bài):*
      * Dòng đỉnh qua diode kẹp: $I_{\text{peak}} = \frac{200\text{ V} - 3.7\text{ V}}{1000\,\Omega} \approx 196.3\text{ mA}$.
      * Công suất đỉnh tiêu tán trên trở: $P_{\text{peak}} = I^2 R = (0.1963\text{ A})^2 \times 1000\,\Omega \approx 38.5\text{ W}$.
      * Năng lượng xung tiêu tán trong trở: $E \approx P_{\text{peak}} \times t = 38.5\text{ W} \times 10^{-3}\text{ s} = 38.5\text{ mJ}$. Trở cắm 1W–2W Metal Film chịu xung hấp thụ mức năng lượng này an toàn mà không cháy đứt.
  * **Diode kẹp bảo vệ BAT54S (Schottky kép):** 
    * Điện dung tiếp giáp $C_d \approx 7 - 10\text{ pF}$ (tại $V_R = 1\text{ V}$).
    * Dòng xung đỉnh không lặp lại $I_{\text{FSM}} = 600\text{ mA}$ (độ rộng xung $t \le 10\text{ ms}$), chịu an toàn dòng đỉnh $196.3\text{ mA}$ của xung 200 V.
  * **Bảo vệ đường nguồn 3.3 V:** 
    * LDO trên kit (AP7343 trên bản gốc WeAct V3.0) là bộ điều tiết dòng cấp ra (*Source*), không phải tải xả (*Sink*). Khi tải cần nhiều dòng, mạch hồi tiếp mở transistor công suất thêm trong giới hạn dòng, biên áp và nhiệt; khi tải giảm, nó giảm dòng cấp. Nếu dòng từ diode kẹp bơm ngược vào rail lớn hơn dòng tải, LDO không tự hấp thụ phần dư, nên điện áp rail có thể tăng và có thể phát sinh dòng ngược qua LDO.
    * **Phân tích ca xấu nhất (Worst-Case Analysis):**
      - *Trường hợp xung đơn 200 V / 1 ms trên 1 kênh:* Dòng xung đỉnh xả vào rail 3.3 V là $I_{\text{peak}} \approx \frac{200 - 3.7}{1000} \approx 196.3\text{ mA}$. Đây là ca tải nặng nhất cho rail 3.3 V (vượt xa dòng DC 130 mA khi 8 kênh chạm +20 V).
      - *Ảnh hưởng trở động:* Diode Zener 3.6 V có điện trở động $r_d$ (vài $\Omega$ đến $10\,\Omega$). Tại dòng $196.3\text{ mA}$, sụt áp động $V_z + r_d \times \Delta I$ có thể đẩy rail vọt lên $> 4.0\text{ V}$ (vượt ngưỡng chịu đựng của STM32). Tụ $10\,\mu\text{F}$ cũng không thể tự gánh vì điện tích $Q = 196\text{ mA} \times 1\text{ ms} = 196\,\mu\text{C} \implies \Delta V = Q/C \approx 19.6\text{ V}$.
      - *Yêu cầu mô phỏng bắt buộc cho TV2:* Phải mô phỏng LTspice ca xung 200 V / 1 ms với model LDO hữu hạn, tải MCU, tụ đầu ra và phần tử shunt/active clamp có trở động thực tế. Nếu điện áp rail bị vượt quá 4.0 V, hoặc model LDO không thể xác định đường dòng ngược:
        1. Cân nhắc tăng $R_1$ lên $2.2\text{ k}\Omega - 4.7\text{ k}\Omega$ (giảm dòng xung xuống còn $42\text{ mA} - 89\text{ mA}$), kiểm chứng lại đáp ứng xung ở 3 MHz.
        2. Hoặc sử dụng cấu trúc diode kẹp 2 tầng / rail phụ, hoặc dùng mạch Shunt TL431 kèm bộ chia điện trở và kiểm tra điều kiện ổn định với tải dung (Stability Boundary).
    * *Trường hợp quá áp một chiều liên tục:*
      - Khi cấp quá áp trên 1 kênh đơn lẻ: Cho phép thử nghiệm đến $\pm 20\text{ V}$ ($I_{\text{sink}} \approx 16.3\text{ mA}$).
      - Khi cấp quá áp đồng thời trên cả 8 kênh: Giới hạn điện áp thử nghiệm an toàn từ $+12\text{ V}$ đến $+15\text{ V}$ (dòng xả tổng $66\text{ mA} - 90\text{ mA}$, bảo đảm nằm trong ngưỡng an toàn của mạch ghim và vượt chuẩn sàn 12 V của đề bài).
  * **Mạng bù tần số cao & Tiêu chí thời gian vượt ngưỡng:**
    * Điện dung tải tại ngõ vào IC đệm: C_load = C_BAT54S + C_in_74LVC245 + C_trace ≈ 10 pF + 4 pF + 2 pF = 16 pF.
    * Chọn tụ bù C1 ≈ 18 – 22 pF. TV2 mô phỏng LTspice kiểm chứng dạng sóng xung 1 MHz – 3 MHz theo tiêu chí thời gian vượt ngưỡng logic: đo thời gian chuyển mức vượt qua V_IH = 2.0 V và xuống dưới V_IL = 0.8 V (đảm bảo t_r, t_f < 20% chu kỳ xung, không làm méo độ rộng xung logic).
  * **Lưu ý phần cứng chân PA0 (Kit WeAct Black Pill V3.0):** Chân PA0 trên kit được nối qua trở hạn dòng $330\,\Omega$ (ký hiệu R1 trên kit, tránh nhầm với điện trở $R_1 = 1\text{ k}\Omega$ của mạch bảo vệ) tới nút nhấn KEY nối GND (hoàn toàn không có tụ lọc nối mass). Khi không bấm nút, nút bấm hở mạch hoàn toàn nên không gây suy hao xung cao tần. Lưu ý duy nhất: không ấn nút KEY trong khi đang đo xung logic trên Kênh 0.

---

### 4.2. Firmware (Core Control): Thu thập & Xử lý (TV1)

* **Bảng chia tần số TIM1 (Input Clock = 84 MHz, Prescaler PSC = 0):**
  * Mức 0 (ARR = 13): 6 MHz
  * Mức 1 (ARR = 27): 3 MHz
  * Mức 2 (ARR = 41): 2 MHz
  * Mức 3 (ARR = 83): 1 MHz
  * Mức 4 (ARR = 167): 500 kHz
  * Mức 5 (ARR = 419): 200 kHz
  * Mức 6 (ARR = 839): 100 kHz
  * Mức 7 (ARR = 1679): 50 kHz
  * Mức 8 (ARR = 8399): 10 kHz

* **Cơ chế Timer Cascade 2 Pha & Dừng Post-Trigger:**
  * **TIM2 cấu hình Slave Mode ExtClock1 nhận xung ITR0 từ TIM1 Update** (ST RM0368 Table 54), One-Pulse Mode. TIM2 đóng vai trò bộ đếm phần cứng 2 pha:
    * **Pha 1 (Pre-trigger 20%):** $\text{ARR}_{\text{TIM2}} = 6554 - 1 = 6553$. Đếm đúng 6.554 mẫu pre-trigger rồi tự dừng bằng OPM, phát ngắt `TIM2_IRQHandler` lần 1 để unmask EXTI.
    * **Pha 2 (Post-trigger 80%):** $\text{ARR}_{\text{TIM2}} = 26214 - 1 = 26213$. Sau khi có cạnh trigger EXTI, đếm đúng 26.214 mẫu rồi tự dừng, phát ngắt `TIM2_IRQHandler` lần 2 để dừng TIM1.
    * **Chế độ Free-Run:** $\text{ARR}_{\text{TIM2}} = 32768 - 1 = 32767$. Đếm thẳng 32.768 mẫu (100% bộ đệm) rồi dừng, không cần ngắt giữa chừng.
  * **Phân cấp ưu tiên ngắt (NVIC Priority Group 4):**
    * `EXTI Trigger`: Priority 0 (Cao nhất - triệt tiêu jitter ngắt).
    * `TIM2 IRQ`: Priority 1 (Chuyển pha Pre $\rightarrow$ Wait Trigger, và Dừng capture Post $\rightarrow$ Transferring).
    * `USB OTG_FS IRQ`: Priority 2 (Tránh ngắt USB làm trễ sự kiện chốt trigger).

* **Quy trình thực thi chi tiết (FSM State Machine & Kỹ thuật Tối ưu hóa Chuyên sâu):**
  1. **Trạng thái ARMED (Nhận lệnh 0x01):** Khởi tạo `DMA2_Stream5 Channel 6` ở chế độ **Direct Mode** (`FIFOMode = DISABLE`, Circular, độ dài 32.768 B, Peripheral = `&GPIOA->IDR`, Memory = `la_capture_buffer`). Khóa tạm thời toàn bộ ngắt EXTI. Kênh Testgen PA9 bị ngắt hoàn toàn.
     * Nếu Free-run (`mode == 0x00`): Cấu hình `TIM2->ARR = 32767`, `TIM2->CNT = 0`, kích hoạt `TIM2->CR1 |= TIM_CR1_CEN`.
     * Nếu Edge trigger: Cấu hình `TIM2->ARR = 6553`, `TIM2->CNT = 0`, kích hoạt `TIM2->CR1 |= TIM_CR1_CEN`.
     * Bật TIM1, chuyển trạng thái `g_la_state = LA_STATE_PRE_SAMPLING`.
  2. **Trạng thái PRE-SAMPLING (Bộ đếm TIM2 Phần cứng 2 Pha & 100% `__WFI()`):**
     * CPU lập tức gọi chỉ thị `__WFI()` (Wait For Interrupt) đưa Cortex-M4 về Sleep mode. TIM2 đếm xung TRGO từ TIM1 hoàn toàn bằng phần cứng. Trong suốt quá trình này, CPU không sinh bất kỳ giao dịch bus nào, nhường **100% bus AHB1 cho DMA2**.
     * Khi đếm đủ 6.554 mẫu: `TIM2` tự dừng (do OPM), phát ngắt `TIM2_IRQHandler` (Ngắt lần 1):
       1. Nạp lại thanh ghi cho pha Post-trigger: `TIM2->ARR = 26213; TIM2->CNT = 0;`.
       2. Cấu hình cạnh xung kích hoạt trên `EXTI->RTSR` / `EXTI->FTSR`.
       3. Reset bộ đếm timeout: `g_timeout_counter_ms = 0`.
       4. **Gán trạng thái FSM trước:** `g_la_state = LA_STATE_WAIT_TRIGGER;`.
       5. **Chốt rào nhớ:** Gọi `__DSB();` để bảo đảm biến trạng thái được ghi xuống SRAM trước khi mở ngắt phần cứng.
       6. Xóa cờ ngắt tồn dư và mở khóa ngắt: `EXTI->PR = (1U << ch); EXTI->IMR |= (1U << ch);`.
       7. CPU tiếp tục gọi chỉ thị `__WFI()` ngủ sâu trong `WAIT_TRIGGER`. Nếu quá hạn timeout mà không có cạnh trigger, SysTick ngắt và chuyển FSM sang dừng capture, gửi gói tin với `Status = 0x02`.
  3. **Sự kiện TRIGGER (Ngắt EXTI - Inline Hardware Trigger):** Khi cạnh tín hiệu xuất hiện trên kênh chỉ định, trình phục vụ ngắt `EXTI_IRQHandler` (Priority 0) thực thi lệnh kích hoạt TIM2 **inline trực tiếp ngay đầu hàm**: `TIM2->CR1 |= TIM_CR1_CEN`, tiếp theo là khóa ngắt `EXTI->IMR &= ~0x00FFU`, xóa cờ `EXTI->PR`, hủy bộ đếm timeout và chuyển FSM sang trạng thái `POST_SAMPLING`. CPU lại tiếp tục ngủ `__WFI()` trong suốt quá trình post-sampling!
     * *Phân tích trễ ngắt tối ưu:* Nhờ inline trực tiếp lệnh bật timer vào đầu ISR (chỉ mất 6 chỉ thị máy sau khi kiểm tra cờ PR), tổng thời gian trễ từ cạnh xung vật lý trên chân PA đến khi TIM2 đếm xung được đưa về mức tiệm cận phần cứng: chỉ $18\text{ clock cycles}$ ($\approx 214\text{ ns}$ @ 84 MHz, gồm 12 clock exception entry của Cortex-M4 và 6 clock rẽ nhánh/bật bit CEN). Ở 6 MHz ($T_s = 166.7\text{ ns}$), sai số trigger vật lý được ép chặt xuống chỉ còn $\approx 1\text{ mẫu}$ (thay vì 2–3 mẫu như trước).
  4. **Trạng thái POST-SAMPLING & Chốt Dừng Chuẩn xác (Ngắt TIM2 lần 2):** TIM2 đếm đủ 26.214 xung (hoặc 32.768 xung ở Free-run) → ngắt tràn `TIM2_IRQHandler` (Priority 1) nổ ra lần 2 thực hiện:
     1. Lập tức dừng TIM1: `TIM1->CR1 &= ~TIM_CR1_CEN;`.
     2. **Thực thi rào nhớ:** `__DSB();` để xả sạch Write Buffer trên cầu AHB-to-APB, bảo đảm xung Update của TIM1 dừng hoàn toàn trên bus.
     3. Dừng DMA2 Stream 5: `DMA2_Stream5->CR &= ~DMA_SxCR_EN; while (DMA2_Stream5->CR & DMA_SxCR_EN);`.
     4. Chốt con trỏ: `write_pos = (32768 - DMA2_Stream5->NDTR) % 32768` với độ chính xác tuyệt đối không bị trôi lệch $\pm 1$ mẫu.
     5. Chuyển FSM sang `TRANSFERRING`.
  5. **Trạng thái TRANSFERRING (Đóng gói & Non-blocking USB-CDC Streaming 4096B):**
     * Đọc vị trí con trỏ cuối: `write_pos = (32768 - DMA2_Stream5->NDTR) % 32768` (vị trí của mẫu cũ nhất $t_0$).
     * Điểm mốc Trigger chuẩn hóa: `trig_offset = 6554` (mẫu $t_{6554}$).
     * **Tính Checksum XOR 32-bit Siêu Tốc:** Áp dụng thuật toán ép kiểu `uint32_t*`, unroll 8x xử lý 32 bytes/vòng lặp với 4 thanh ghi tích lũy `x0, x1, x2, x3`, gộp 4 byte lại bằng bitwise shift/XOR, giảm thời gian tính checksum toàn bộ 32KB payload xuống $< 0.12\text{ ms}$ (tăng tốc gấp ~10 lần).
     * **Tối ưu hóa TxFIFO USB OTG_FS (320 words):** Cấu hình phần cứng Dedicated Packet RAM phân bổ 224 words (896 Bytes = 14 packets 64B Bulk IN) cho EP1 Tx, loại bỏ nghẽn FIFO giữa các microframe.
     * **Non-blocking State-driven USB Streaming 4096B:** Đóng gói khung 32.776 Bytes theo cơ chế Buffer Unrolling (Header 7B + Đoạn 1 dài `32768 - write_pos` + Đoạn 2 dài `write_pos` + Footer 1B). Quá trình truyền phân đoạn theo block lớn **$\le 4096\text{ Bytes}$** được điều khiển bởi máy trạng thái phi phong tỏa: Giảm số lần nạp từ 64 lần xuống 8 lần, đưa thời gian truyền 32KB xuống chạm trần vật lý $1.12\text{ MB/s}$ ($\sim 28\text{ ms}$). Kèm watchdog bảo vệ $100\text{ ms}$/block chống treo máy nếu host ngắt kết nối.

---

### 4.3. Giao thức Giao tiếp (Communication Protocol Contract)

> [!IMPORTANT]
> **Nguồn chân lý duy nhất (SSoT):** Toàn bộ đặc tả chi tiết byte-level, mã lệnh (5B), mã phản hồi điều khiển/NAK (7B), gói dữ liệu (32.776B), thuật toán sliding window và bộ vector test được quy định tuyệt đối tại [**`spec/protocol.md`**](protocol.md).

* **Tóm tắt Khung lệnh từ PC (5 Bytes cố định):**
  * `0xA5` (Magic) + `CMD_ID` (`0x01` Start, `0x02` Abort, `0x03` Ping) + `RATE_IDX` (`0..8`) + `TRIG_CFG` (Kênh `[7:4]`, Mode `[3:0]`) + `CHECKSUM` (XOR byte 0..3).
* **Tóm tắt Khung phản hồi từ STM32:**
  * **Data Frame (32.776 Bytes):** Header 7B (`0x5A, 0xA5`, Status `0x00..0x02`, `trig_offset = 6554` Little-Endian `0x9A, 0x19`, `sample_count = 32768` Little-Endian `0x00, 0x80`) + Payload 32.768B unrolled + Footer 1B XOR payload.
  * **Control / NAK Frame (7 Bytes):** `0x5A, 0xA5` + `RSP_CODE` (`0x04` Pong, `0x05` Abort ACK, `0xE0..0xE3` NAK) + 3 byte Echo/Data + Checksum XOR 6 byte trước.
  * Khi Abort, MCU trả khung Control 7B `RSP_ABORTED` (`0x05`) chứ không gửi khung Data 32KB dở dang. Chi tiết toàn diện xem tại [**`protocol.md`**](protocol.md).

---

### 4.4. Kịch bản Đo kiểm & Thử nghiệm Thực tế (Validation & Testbench)

1. **Kịch bản 1: Tự kiểm tra cục bộ (Internal Loopback):**
   * Kích hoạt chân **PA9 (USART1_TX)** phát chuỗi UART chuẩn `"TEST_LA_2026\r\n"` ở baudrate 115.200 bps.
   * Cắm jumper nối từ chân PA9 sang PA0 (hoặc PA1..PA7).
   * Cấu hình trigger: Kênh 0, cạnh xuống (Falling Edge - TRIG_CFG = 0x02) để bắt đúng Start bit UART (UART idle mức cao).
   * Kiểm chứng: GUI hiển thị chính xác dạng sóng vuông của frame UART và giải mã đúng chuỗi ASCII `"TEST_LA_2026"`.
2. **Kịch bản 2: Kiểm chứng Hiện tượng Aliasing & Định lý Nyquist (Trọng tâm Topic 1):**
   * Cấu hình Timer phụ TIM3 phát sóng vuông tần số $f_{\text{in}} = 500\text{ kHz}$ trên chân rảnh PB0 (nối jumper sang chân đo PA0).
   * Tiến hành đo ở 2 tần số lấy mẫu để so sánh:
     * *Ở $f_s = 6\text{ MHz}$ ($12 \times f_{\text{in}}$):* Dạng sóng tái tạo sắc nét, đo đúng tần số 500 kHz và chu kỳ $2\,\mu\text{s}$.
     * *Ở $f_s = 200\text{ kHz}$ (RATE_IDX = 5, vi phạm điều kiện Nyquist $f_s < 2 f_{\text{in}}$):* Tần số biểu kiến quan sát được trên GUI bị alias về $|500 - 2 \times 200| = 100\text{ kHz}$ (chu kỳ $10\,\mu\text{s}$). Minh họa trực quan và xuất dữ liệu phân tích hiện tượng Aliasing cho báo cáo.
3. **Kịch bản 3: Đo kiểm Sai lệch Pha thực tế giữa các Kênh (Skew Verification):**
   * Nối song song cùng một nguồn xung tốc độ cao vào đồng thời 2 kênh (ví dụ PA0 và PA1).
   * Thu thập dữ liệu ở 6 MHz và đo độ lệch vị trí cạnh xung giữa 2 kênh trên GUI để chứng minh sai số thời gian phần cứng $\Delta t \le 1$ mẫu.

---

## 5. Lộ trình Triển khai và Phân công Nhiệm vụ (Implementation Roadmap & Task Allocation)

> [!NOTE]
> **Hiện trạng Tiến độ Dự án:** Giai đoạn phát triển Vertical Slice cơ bản (mốc 11/11 ban đầu) đã hoàn thành và kiểm chứng thông suốt từ sớm. Dự án hiện đã chuyển sang **giai đoạn phát triển và hoàn thiện toàn diện toàn hệ thống (Full-System Development)** phục vụ nghiệm thu đồ án cuối kỳ.

| Thành viên | Nhiệm vụ Trọng tâm | Yêu cầu Kỹ thuật Toàn diện | Mục tiêu Hoàn thiện Toàn hệ thống (Cuối kỳ) |
| :--- | :--- | :--- | :--- |
| **TV1: Nguyễn Văn Hội** (20233419)<br>*(Firmware Engineer)* | Hoàn thiện toàn bộ firmware lõi STM32: FSM 5 trạng thái, 5 kỹ thuật tối ưu hóa, hỗ trợ 9 tần số lấy mẫu và tự kiểm tra loopback. | • Quản lý Clock Tree 84 MHz (HSE 25MHz) & USB OTG 48MHz chuẩn xác.<br>• Sampling Engine: TIM1 + DMA2_Stream5 đọc trực tiếp `GPIOA->IDR` vào mảng 32 KB Circular.<br>• FSM 5 bước hoàn chỉnh: Free-run, Edge Trigger (Rising/Falling trên 8 kênh PA0..PA7).<br>• Triển khai trọn bộ 5 kỹ thuật tối ưu hóa:<br>&nbsp;&nbsp;(1) Dynamic Pre-trigger 20% qua `NDTR` (tiết kiệm 60% thời gian ở tần số thấp).<br>&nbsp;&nbsp;(2) Trigger ISR Inline (rút ngắn trễ xuống 18 clock, sai số $\approx 1$ mẫu ở 6 MHz).<br>&nbsp;&nbsp;(3) Non-blocking USB Streaming 512B kèm watchdog 100ms (giải phóng CPU tải $<2\%$).<br>&nbsp;&nbsp;(4) Checksum XOR 32-bit unrolled 8x ($<0.12\text{ ms}$).<br>&nbsp;&nbsp;(5) Low-power `__WFI()` khi ở `WAIT_TRIGGER` (giảm dòng tiêu thụ và triệt tiêu nhiễu bus).<br>• Kênh phát xung UART testgen PA9 ("TEST_LA_2026\r\n", 115.200 bps). | **Hoàn thành 100% Firmware:** Toàn bộ firmware vượt qua 100% test suite tự động, biên dịch 0 error 0 warning, sẵn sàng nghiệm thu phần cứng và tích hợp thông suốt với GUI. |
| **TV2: Nguyễn Văn Khang** (20233458)<br>*(Hardware Engineer)* | Hoàn thiện mạch in PCB bảo vệ 8 kênh, lắp ráp mô-đun phần cứng và đo kiểm các kịch bản quá áp/xung vuông thực tế. | • Hoàn thiện mô phỏng LTspice 4 kịch bản xác nhận độ an toàn của rail 3.3V và đáp ứng xung logic đến 3 MHz.<br>• Thiết kế sơ đồ nguyên lý (Schematic) và layout mạch in (PCB) 8 kênh hoàn chỉnh:<br>&nbsp;&nbsp;- Bố trí mạng R-C bù tần số ($1\text{ k}\Omega // 22\text{ pF}$) và diode BAT54S tối ưu đường mạch chống nhiễu chéo.<br>&nbsp;&nbsp;- Tầng đệm 74LVC245 cách ly bảo vệ chân STM32.<br>&nbsp;&nbsp;- Tầng ghim shunt/active clamp xả ngược rail 3.3V và cầu chì PTC 500mA bảo vệ nguồn USB.<br>• Gia công bo mạch PCB, hàn linh kiện hoàn thiện mô-đun bảo vệ đầu vào 8 kênh.<br>• Đo đạc thực nghiệm: Kiểm chứng quá áp DC (+12V..+15V trên 8 kênh, ±20V trên 1 kênh), đo thời gian chuyển mức $t_r, t_f$ và lập bảng số liệu thực tế. | **Hoàn thành 100% Phần cứng:** Bo mạch bảo vệ 8 kênh hoàn chỉnh bằng linh kiện thật, vượt qua các bài đo kiểm thực nghiệm, ghép nối an toàn với kit WeAct Black Pill. |
| **TV3: Nguyễn Trường Giang** (20233374)<br>*(Software & GUI Engineer)* | Xây dựng ứng dụng Desktop GUI hoàn chỉnh: hiển thị 8 kênh 60 FPS, đo đạc thời gian và tích hợp bộ giải mã đa giao thức (UART, SPI, I²C). | • Giao diện Desktop GUI chuyên nghiệp (Python, PyQt5 + pyqtgraph) kết nối COM port, nhận gói 32.776 B và kiểm tra XOR Checksum.<br>• Render đồng thời 8 kênh sóng logic mượt mà ở tốc độ 60 FPS, hỗ trợ thu phóng (zoom) và cuộn (pan) trục thời gian.<br>• Định vị vạch chỉ thị Trigger danh định tại mẫu 6554.<br>• Thanh công cụ đo đạc thời gian: Cặp con trỏ đo (Cursors A & B) đo khoảng cách thời gian $\Delta t$, tần số $1/\Delta t$, và đếm chu kỳ xung.<br>• Bộ giải mã đa giao thức hoàn chỉnh (Multi-Protocol Decoders):<br>&nbsp;&nbsp;- **UART Decoder:** Tùy biến baudrate, data bits, parity, stop bits.<br>&nbsp;&nbsp;- **SPI Decoder:** Hỗ trợ 4 Mode (CPOL/CPHA), chọn kênh CS/SCK/MOSI/MISO, MSB/LSB first.<br>&nbsp;&nbsp;- **I²C Decoder:** Nhận diện Start/Stop, 7-bit/10-bit address, Read/Write, ACK/NACK và data.<br>• Tính năng xuất dữ liệu (Export) sang định dạng CSV và file VCD (Value Change Dump). | **Hoàn thành 100% Desktop GUI:** Ứng dụng hoạt động ổn định, hiển thị dạng sóng thời gian thực và giải mã chính xác cả 3 giao thức UART, SPI, I²C từ dữ liệu capture thực tế. |
