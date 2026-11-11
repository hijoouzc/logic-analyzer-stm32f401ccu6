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
* **Giao thức giải mã:** Hỗ trợ UART (giai đoạn 1 - mốc 11/11); bổ sung hoàn thiện SPI và I²C (giai đoạn 2 - cuối kỳ).
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

## 3. Phân tích và Lựa chọn Giải pháp (Design Decision Log)

| ID | Thành phần Thiết kế | Giải pháp Lựa chọn | Giải pháp Thay thế | Lý do chọn |
| :--- | :--- | :--- | :--- | :--- |
| **D1** | **Vi điều khiển & DMA** | STM32F401CCU6 (64 KB SRAM), dùng TIM1 + DMA2_Stream5 Channel 6 | Arduino Uno, STM32F103 (Blue Pill) | DMA2 trên dòng F4 kết nối trực tiếp bus AHB1 giúp đọc `GPIOA->IDR` ở tốc độ 84 MHz; SRAM 64 KB đủ chứa bộ đệm 32 KB (50% RAM) và tích hợp sẵn USB Full-Speed OTG không cần IC chuyển đổi USB-UART ngoài. |
| **D2** | **Mạch bảo vệ đầu vào** | Mạng bù R-C ($1\text{ k}\Omega // 18-22\text{ pF}$) + Diode Schottky BAT54S + Buffer 74LVC245 | Chỉ dùng điện trở nối tiếp + Diode Zener thông thường | Diode Zener có điện dung ký sinh lớn ($>50\text{ pF}$) làm tù sườn xung ở tần số cao. BAT54S ($C_d \approx 7-10\text{ pF}$, $I_{FSM} = 600\text{ mA}$) kết hợp trở cắm $1\text{ k}\Omega$ gánh xung 200 V an toàn. Tụ bù $C_1 \approx 18-22\text{ pF}$ bù trừ điện dung ký sinh, tối ưu thời gian chuyển mức $t_r, t_f$ vượt ngưỡng $V_{IH}=2.0\text{ V}$ và $V_{IL}=0.8\text{ V}$ tại 3 MHz. |
| **D3** | **Chiến lược Trigger** | Circular DMA Pre-Trigger (20% Pre / 80% Post) + Đồng bộ cờ Half-Transfer (HT) | Bắt ngắt EXTI mới bật Timer; hoặc lọc phần mềm trên PC | Tránh bẫy polling DMA quay vòng bằng cách đợi cờ DMA Half-Transfer bật (đã nạp $\ge 20\%$ bộ đệm) rồi mới Unmask ngắt EXTI. Lưu trữ trọn vẹn 20% lịch sử trước sự kiện trigger. |
| **D4** | **Bộ đếm Post-Trigger** | TIM1 (Master) cấp xung qua ITR0 cho TIM2 (Slave 32-bit One-Pulse Mode) | CPU đọc thanh ghi NDTR trong vòng lặp; hoặc dùng Timer độc lập | Đếm chính xác tuyệt đối 26.214 mẫu bằng phần cứng với TIM2 (sai số phần cứng 0% ở 6 MHz), hoàn toàn giải phóng CPU trong quá trình capture. |
| **D5** | **Giao thức PC ↔ MCU** | Khung lệnh 5 B; Gói dữ liệu trả về 32.776 B truyền phân đoạn qua USB-CDC | Truyền chuỗi ASCII qua UART rời | Truyền nhị phân qua USB-CDC đạt tốc độ $>1\text{ MB/s}$; truyền toàn bộ 32.768 mẫu ước tính ~27–33 ms (ước lượng lý thuyết, sẽ đo kiểm thực tế trên phần cứng). Quản lý phân đoạn (chunking 512B) tránh nghẽn Endpoint Bulk. |
| **D6** | **Bảo vệ nguồn & Linh kiện** | Trở cắm Through-hole $1\text{ k}\Omega$ (1 W–2 W chịu xung) + phần tử shunt/active clamp được chọn theo dòng xả và giới hạn rail | Dùng trở dán SMD 0805 + TVS SMAJ3.3A mà chưa kiểm tra model và dòng xả | Khi đặt áp $-20\text{ V}$ trên 1 kênh, trở gánh khoảng $0.416\text{ W}$; với xung 200 V / 1 ms trên 1 kênh, dòng ban đầu theo mô hình lý tưởng khoảng $196.3\text{ mA}$ và công suất tức thời trên trở khoảng $38.5\text{ W}$, nhưng giá trị thực tế phụ thuộc điện áp kẹp và trở động. Không được mặc định Zener 3.6 V giữ rail dưới 4.0 V: LDO thông thường không hút dòng bơm ngược, nên cần mô phỏng và kiểm tra phần tử shunt/active clamp, tải, tụ và đường dòng ngược theo datasheet. |
| **D7** | **Đồ thị & Giải mã** | pyqtgraph + numpy.unpackbits + Center-bit Sampling | Vẽ bằng Matplotlib, giải nén bit bằng vòng lặp Python thuần | NumPy giải nén 32 KB bitstream trong thời gian $<1\text{ ms}$; pyqtgraph render đồ thị 8 kênh ở 60 FPS, đảm bảo thao tác thu phóng/cuộn mượt mà. |
| **D8** | **Kế hoạch mốc 11/11** | Vertical Slice: Chạy Free-run loopback PA9 (UART Tx 115200) $\rightarrow$ PA0 $\rightarrow$ USB-CDC $\rightarrow$ GUI | Triển khai đồng thời cả Trigger phức tạp và giải mã SPI/I2C | Đảm bảo trước 11/11 có sản phẩm chạy được thực tế từ phần cứng đến giao diện PC để quay video demo và chụp ảnh báo cáo tiến độ. |
| **D9** | **Phương thức Nạp Firmware** | Nạp trực tiếp qua cổng USB Type-C bằng STM32 ROM DFU Bootloader (`0483:df11`) | Mạch nạp rời ST-Link V2/V3 qua cổng SWD | Tận dụng sẵn bootloader phần cứng trong ROM của STM32F401, không phụ thuộc vào thiết bị nạp rời, tối ưu chi phí và tiện lợi khi mang đi thử nghiệm thực tế. Vẫn giữ nguyên cấu hình chân SWD (PA13/PA14) để tương thích ST-Link khi cần. |

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

* **Cơ chế Timer Cascade & Dừng Post-Trigger:**
  * Đảm bảo đếm chính xác 26.214 mẫu sau kích hoạt Trigger (chiếm 80% dung lượng bộ đệm 32.768 mẫu), thanh ghi nạp tự động của TIM2 (Slave 32-bit One-Pulse Mode nhận xung ITR0 từ TIM1 Update) được thiết lập:
    $$\text{ARR}_{\text{TIM2}} = 26214 - 1 = 26213$$
  * **Phân cấp ưu tiên ngắt (NVIC Priority Group 4):**
    * `EXTI Trigger`: Priority 0 (Cao nhất - triệt tiêu jitter ngắt).
    * `TIM2 IRQ`: Priority 1 (Dừng capture).
    * `USB OTG_FS IRQ`: Priority 2 (Tránh ngắt USB làm trễ sự kiện chốt trigger).

* **Quy trình thực thi chi tiết (FSM State Machine):**
  1. **Trạng thái ARMED (Nhận lệnh 0x01):** Khởi tạo `DMA2_Stream5 Channel 6` (Circular Mode, độ dài 32.768 B, Peripheral = `&GPIOA->IDR`, Memory = `la_capture_buffer`). Kích hoạt TIM1. Khóa tạm thời ngắt EXTI.
  2. **Trạng thái PRE-SAMPLING (Đồng bộ cờ Half-Transfer):** Đợi cờ ngắt DMA Half-Transfer (`HTIF5` bật khi ghi được 50% = 16.384 mẫu $\ge 20\%$ yêu cầu). Khi cờ bật, chắc chắn 100% dữ liệu lịch sử pre-trigger đã đầy đủ:
     * Nếu chế độ Trigger cạnh: Unmask cho phép ngắt EXTI trên kênh được chỉ định, chuyển FSM sang `WAIT_TRIGGER`, đồng thời kích hoạt bộ đếm thời gian thực SysTick theo dõi Timeout: $T_{\text{mcu-timeout}} = (16384 / f_s) + 2.0\text{ s}$. Nếu quá hạn mà không có cạnh trigger, SysTick ngắt và chuyển FSM sang dừng capture, gửi gói tin với `Status = 0x02`.
     * Nếu chế độ Free-Run: Kích hoạt ngay lập tức TIM2 One-Pulse (bỏ qua ngắt EXTI và không kích hoạt bộ đếm timeout), chuyển FSM sang `POST_SAMPLING`.
  3. **Sự kiện TRIGGER (Ngắt EXTI):** Khi cạnh tín hiệu xuất hiện trên kênh chỉ định, trình phục vụ ngắt `EXTI_IRQHandler` (Priority 0) thực thi lệnh kích hoạt TIM2: `TIM2->CR1 |= TIM_CR1_CEN`, hủy bộ đếm timeout, vô hiệu hóa ngắt EXTI và chuyển FSM sang trạng thái `POST_SAMPLING`.
     * *Phân tích trễ ngắt:* Ước lượng lý thuyết trễ vào ngắt NVIC Cortex-M4 ($\approx 12-14$ clock cycles @ 84 MHz) kết hợp với các lệnh trong handler, việc TIM2 đồng bộ theo chu kỳ update kế tiếp của TIM1, và độ trễ khi dừng TIM1 trong ISR TIM2 tạo ra độ bất định thực tế cỡ vài mẫu ở 6 MHz. Firmware sẽ toggle một chân GPIO debug (PB1) trong ISR để đo đạc chính xác bằng oscilloscope/logic analyzer và ghi số liệu thực nghiệm vào báo cáo.
  4. **Trạng thái POST-SAMPLING:** TIM2 đếm đủ 26.214 xung → ngắt tràn `TIM2_IRQHandler` (Priority 1) lập tức dừng TIM1 (`TIM1->CR1 &= ~TIM_CR1_CEN`). Chuyển FSM sang `TRANSFERRING`.
  5. **Trạng thái TRANSFERRING (Đóng gói & Truyền USB-CDC):**
     * Đọc vị trí con trỏ cuối: `write_pos = 32768 - DMA2_Stream5->NDTR` (vị trí của mẫu cũ nhất $t_0$).
     * Điểm mốc Trigger chuẩn hóa: `trig_offset = 6554` (mẫu $t_{6554}$).
     * Đóng gói khung truyền 32.776 Bytes theo cơ chế Buffer Unrolling: Header (7B) + Đoạn 1 (`&la_capture_buffer[write_pos]`, dài `32768 - write_pos`) + Đoạn 2 (`&la_capture_buffer[0]`, dài `write_pos`) + Footer Checksum XOR (1B).
     * Quản lý truyền USB-CDC: Phân đoạn truyền theo block (512 Bytes) và kiểm tra cờ bận `hcdc->TxState == 0` kết hợp callback `CDC_TransmitCplt_FS()` trước mỗi lượt gửi để tránh nghẽn Endpoint Bulk.

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

| Thành viên | Nhiệm vụ ưu tiên | Yêu cầu kỹ thuật chi tiết | Kế hoạch mốc 11/11 |
| :--- | :--- | :--- | :--- |
| **TV1: Nguyễn Văn Hội** (20233419)<br>*(Firmware STM32)* | Hoàn thiện luồng lấy mẫu DMA, quản lý USB-CDC, FSM đồng bộ Pre/Post Trigger và kênh phát UART test. | • Thiết lập SYSCLK 84 MHz (HSE 25MHz) & USB 48MHz chuẩn xác.<br>• Viết driver TIM1 + TIM2 cascade + DMA2_Stream5 Circular reading `GPIOA->IDR` (32 KB buffer).<br>• Cài đặt FSM: Đồng bộ cờ Half-Transfer trước khi mở EXTI, quản lý ưu tiên ngắt NVIC.<br>• Phân đoạn truyền USB-CDC theo block an toàn, kiểm tra cờ `TxState == 0` (timeout 100ms/block).<br>• Cấu hình PA9 phát chuỗi UART test ("TEST_LA_2026\r\n", 115.200 bps).<br>• Báo cáo phân tích: Ghi nhận trễ ngắt thực tế (đo bằng toggle chân GPIO debug PB1 trong ISR) và độ lệch kênh skew thực đo. | **Hoàn thành Vertical Slice:** Chạy thông Free-run thu thập 32 KB từ loopback PA9 $\rightarrow$ PA0 và gửi thành công lên PC qua USB-CDC. |
| **TV2: Nguyễn Văn Khang** (20233458)<br>*(Phần cứng & Mô phỏng)* | Hoàn thiện mô phỏng LTspice 4 kịch bản; thiết kế sơ đồ nguyên lý và danh mục BOM. | • File mô phỏng LTspice `.asc` với mô hình rail 3.3V thực tế (LDO + tải MCU + trở động diode ghim):<br>&nbsp;&nbsp;(1) Quá áp liên tục +12V..+15V trên 8 kênh (hoặc ±20V trên 1 kênh).<br>&nbsp;&nbsp;(2) Xung đơn lẻ $\pm 200\text{ V} / 1\text{ ms}$ trên 1 kênh (mô phỏng dòng đỉnh 196.3 mA xả vào rail 3.3V, kiểm chứng điện áp rail $\le 4.0\text{ V}$).<br>&nbsp;&nbsp;(3) Sóng vuông 10 kHz & 1 MHz (mở rộng 3 MHz, đo thời điểm chuyển mức $t_r, t_f$ vượt $V_{IH}=2.0\text{ V}, V_{IL}=0.8\text{ V}$).<br>• Schematic Altium/KiCad mạch bảo vệ 8 kênh + IC đệm 74LVC245 + PTC 500mA trên đường USB VBUS.<br>• BOM chi tiết: Trở cắm 1W–2W Metal Film chịu xung, BAT54S, Zener 3.6V / 1W (hoặc TL431), 74LVC245. | **Hoàn thành mô phỏng:** Xuất biểu đồ sóng LTspice đạt chuẩn 4 kịch bản để đưa vào slide báo cáo tiến độ. |
| **TV3: Nguyễn Trường Giang** (20233374)<br>*(Python GUI & Decoder)* | Xây dựng giao diện PyQt hiển thị 8 kênh, nhận dữ liệu USB-CDC và giải mã UART. | • Viết GUI Python (PyQt5 + pyqtgraph) kết nối COM port, nhận gói 32.776 B và kiểm tra XOR checksum.<br>• Hiển thị đồng thời 8 kênh sóng cùng vạch chỉ thị Trigger tại mẫu 6554.<br>• Xây dựng thuật toán giải mã UART 115.200 bps (Center-bit sampling) hiển thị ký tự ASCII trực tiếp trên dạng sóng.<br>• Tạo script mock test đọc file `.bin` giả lập để kiểm thử GUI độc lập trước khi có kit thật. | **Hoàn thành GUI & Decoder:** Kết nối nhận gói dữ liệu từ TV1, hiển thị dạng sóng và giải mã ra chữ "TEST_LA_2026" trên đồ thị. |
