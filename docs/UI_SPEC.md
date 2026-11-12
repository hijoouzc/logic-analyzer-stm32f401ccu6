# UI_SPEC.md — Đặc tả giao diện GUI Logic Analyzer (TV3 & GUI Team)

Tài liệu chuẩn hóa thiết kế giao diện người dùng (Desktop GUI) cho hệ thống Logic Analyzer 8 kênh 6 MHz (STM32F401CCU6).
* **Giao thức phần cứng STM32:** [`spec/protocol.md`](../spec/protocol.md) (Nguồn chân lý duy nhất cho khung truyền).
* **Mã nguồn Stylesheet dự án:** [`software/gui/theme.py`](../software/gui/theme.py) (SSoT về bảng màu và QSS trong code, không hardcode màu nơi khác).
* **Wireframe bố cục tham chiếu:** [`docs/ui_reference/wireframe.html`](ui_reference/wireframe.html).

---

## 1. Mục tiêu Thiết kế
Giao diện Dark Theme tối giản, hiện đại và tập trung cao độ cho kỹ sư hệ thống nhúng:
* Các hàng kênh xếp chồng độc lập, trục thời gian đồng bộ liên kết.
* Giải mã giao thức (UART / I2C / SPI) hiển thị dưới dạng bong bóng (Inline Annotation Bubbles) ngay trên track sóng.
* Thao tác chuột mượt mà: Cuộn chuột để Zoom tại vị trí con trỏ, kéo chuột trái/phải để Pan timeline.
* Thiết bị hoạt động dạng Single Shot (Bắt 32.768 mẫu / lần, truyền qua USB CDC).

---

## 2. Bố cục Tổng thể (Layout Architecture)

```
+-----------------------------------------------------------------------------------------+
| Top Bar: Window Title + Menu Bar (File, Edit, Capture, Measure, View, Help)    (~36 px) |
+-------------------------------------------------------------+-----------------+---------+
| Waveform & Channels Canvas                                  | Drawer Panel    | Rail    |
| +---------------------+-----------------------------------+ | (Width: 310 px) | (56 px) |
| | Cột nhãn (180 px)   | Thước thời gian (+0.1ms, +0.2ms)  | |                 |         |
| | [D0] Channel 0      | ──[ 0x55 ]─────────[ 0xAA ]───────| | Analyzers   [+] | [Play]  |
| |  ● Async Serial     |                                   | | Async Serial  ✓ |  (Ø 48) |
| | [D1] Channel 1      | ───────────────────────────────── | | > Device Set  ✕ |         |
| |  ● I2C - SDA        |                                   | | > Measure     ✕ | [Analy] |
| | [D2..D7]            | ... (Đường phân cách mảnh)        | |                 |         |
| |                     |                                   | | Data          ✓ | [Meas]  |
| |                     |                                   | | [Type to search]|         |
| |                     |                                   | | Type|Start|Dur  | [Sett]  |
| +---------------------+-----------------------------------+ | |0x55|1.2ms|... |         |
+-------------------------------------------------------------+-----------------+---------+
| Footer Bar: Tabs [Session 0] [Session 1] [+]                      Zoom Level: [128 µs ^]|
+-----------------------------------------------------------------------------------------+
```

### Kích thước & Tỉ lệ Pixel Logic (Chuẩn màn hình 1280×860 trở lên):
| Thành phần | Kích thước | Mô tả & Trách nhiệm |
|---|---|---|
| **Activity Rail (Phải cùng)** | `56 px` | Nền `#3a3a3e`, viền trái `1px solid #57575e`, chứa nút tròn Start Ø 48px xanh + các switcher dọc 56×56px |
| **Drawer Panel (Phải)** | `310 px` | Nền `#1b1b1c`, viền trái `1px solid #57575e`, chứa thẻ `#2c2c2e`, Analyzers, Measurements và bảng Data Table `#141415` |
| **Cột nhãn kênh (Trái)** | `180 px` | Nền `#1b1b1c`, viền phải `1px solid #57575e`, chứa badge kênh `D0`..`D7`, tên kênh và chip protocol |
| **Vùng sóng (Waveform Plot)** | Co giãn tự do | Nền `#1b1b1c`, vạch phân cách track `#57575e`, lưới nét đứt `#49494d` |
| **Thước thời gian (Timeline)** | `32 px` | Nền `#0f0f10`, viền dưới `1px solid #57575e`, hiển thị mốc thời gian nanosecond/microsecond/millisecond |
| **Thanh dưới (Session Tabs)** | `36 px` | Nền `#1b1b1c`, viền trên `1px solid #57575e`, quản lý session tabs, trạng thái thiết bị và độ phân giải zoom |
| **Nút Start / Capture** | Đường kính `48 px` | Nút tròn bo 24px, màu xanh `#00994d` với icon tam giác Play trắng, đặt tại đỉnh Activity Rail |

---

## 3. Hệ Thống Màu Chuẩn (Dark Theme Design System)

### 3.1. Màu Nền & Khung Viền:
* **Canvas Sóng (Waveform Viewport):** `#1b1b1c`
* **Thước thời gian (Timeline Header):** `#0f0f10`
* **Thanh công cụ & Drawer Panel:** `#1b1b1c`
* **Nền hàng Data Table & Terminal:** `#141415`
* **Thẻ & Ô nhập liệu (Cards & Inputs):** `#2c2c2e`
* **Đường viền ngăn kênh (Borders):** `#303136`
* **Đường viền phụ / Vạch track:** `#57575e`
* **Hover / Selected Row:** `#3a3a3e`
* **Chữ chính (High Emphasis):** `#ffffff`
* **Chữ mờ (Medium Emphasis):** `#909091`
* **Lưới nét đứt (Grid Dash):** `#49494d`
* **Nền Tooltip / Floating HUD:** `#343438`
* **Điểm nhấn đang chọn (Selection Highlight):** `#26a3d9`

### 3.2. Bảng 8 Màu Kênh Kỹ Thuật Số (CH0 – CH7 - Chuẩn Mã Màu Điện Trở):
```python
CHANNEL_COLORS = [
    "#d4d4d4",  # CH0: Silver White
    "#c79579",  # CH1: Warm Copper
    "#ff6d7f",  # CH2: Coral / Salmon Red
    "#ffb45b",  # CH3: Amber Orange
    "#e8d836",  # CH4: Lemon Yellow
    "#58c667",  # CH5: Fresh Green
    "#53a9fd",  # CH6: Sky Blue
    "#af92fb",  # CH7: Lavender Purple
]
```

### 3.3. Trigger, Cursors & Bong Bóng Giải Mã (Annotations):
* **Vạch Trigger dọc:** `#fff06a`
* **Cờ / Điểm Trigger:** `#f1994b`
* **Con trỏ đo A / B:** Cursor A `#26a3d9`, Cursor B `#ea5757`
* **Nút Start (Capture):** `#00994d` (Hover: `#00b140`, Active: `#02992f`)
* **Nút Abort (Stop):** `#db4c39`
* **Bong bóng giải mã (Inline Decoded Bubbles):**
  * Chiều cao `18 px` trên dải decoder phía trên đường sóng.
  * **UART:** Nền `#d3ccb0`, chữ `#1b1b1c`.
  * **I2C:** Nền `#4060c0`, chữ `#ffffff`.
  * **SPI:** Nền `#53a9fd`, chữ `#1b1b1c`.

---

## 4. Typography
* **Font Family:** `"Roboto", "Segoe UI", "Helvetica Neue", sans-serif`
* **Font Monospace (Data Table / Measurements / Timeline):** `"Roboto Mono", "DejaVu Sans Mono", monospace`
* **Tiêu đề kênh (Channel Title):** `13px`, `font-weight: 500`.
* **Badge kênh (`D0`..`D7`):** `11px`, `font-weight: 700`.
* **Bảng dữ liệu & Thước đo:** `11px - 12px`, `font-weight: 400`.
* **Bong bóng ký tự giải mã:** `11px`, `font-weight: 700`.

---

## 5. Quy Tắc Hiển Thị Sóng & Kênh (Waveform Tracks)
1. **Co giãn lấp đầy (Dynamic Stretching):** 8 kênh chia đều chiều cao của vùng sóng (mỗi kênh tối thiểu `48 px`), đảm bảo không có khoảng trống thừa bên dưới. Hàng có gắn Protocol Analyzer cao gấp `1.35x` hàng thông thường để chứa bong bóng giải mã.
2. **Nét vẽ tín hiệu số:** Dùng `stepMode="right"` của pyqtgraph để vẽ xung vuông thẳng góc nét căng (độ dày 1.5px, màu theo kênh).
3. **Mốc thời gian Trigger:** Mẫu trigger danh định tại index 6554 tương ứng thời gian $t = 0\,\text{s}$. Dữ liệu trước trigger có thời gian âm, sau trigger có thời gian dương.
4. **Điểm đánh dấu tâm bit giao thức (Protocol Bit Markers):** Đường sóng số (`D0`..`D7`) giữ nét vuông phẳng mượt 100% ở mọi mức phóng đại (không vẽ chấm mẫu trên đường `H`/`L`); chỉ hiển thị 8 dấu chấm đánh dấu tâm bit dữ liệu (`D0`..`D7`) nằm ở chính giữa hai mức `H` và `L` khi người dùng Zoom vào gói tin.

---

## 6. Ánh Xạ Trạng Thái Giao Diện Với Giao Thức Firmware (SSoT)
Chi tiết khung truyền xem [`spec/protocol.md`](../spec/protocol.md):
* **Nhận Pong (`5A A5 04 ...`):** Đổi trạng thái kết nối sang xanh `"Connected: STM32F401 (v1.0.0)"`.
* **Nhận Data Frame (Status `0x00` - Triggered):** Vẽ dạng sóng, đặt vạch trigger vàng cam tại mẫu $t_0 = 0\,\text{s}$.
* **Nhận Data Frame (Status `0x01` - Free-run):** Vẽ dạng sóng với gốc thời gian $t = 0\,\text{s}$ tại mẫu đầu tiên, đặt vạch `"FREE-RUN"`.
* **Nhận Data Frame (Status `0x02` - Timeout):** Hiển thị vạch `"TIMEOUT"`, vẫn vẽ đầy đủ 32.768 mẫu thu được.
* **Nhận NAK (`0xE0` - Checksum, `0xE1` - Rate, `0xE2` - Trigger, `0xE3` - Busy):** Hiển thị hộp thoại cảnh báo chi tiết mã lỗi cho người dùng.
* **Đang thu thập 32.776 Byte:** Đổi nút tròn Start sang nút vuông Stop màu đỏ (`#db4c39`) hỗ trợ hủy lệnh tức thì (`CMD_ABORT`).

---

## 7. Đặc Tả Kỹ Thuật: Hệ Thống Đo Đạc Thông Minh (Magnetic Snap-To-Edge & Quick Measure Tool)

Hệ thống đo đạc thời gian thông minh mô phỏng cơ chế làm việc của các dòng máy phân tích logic thương mại cao cấp (Saleae Logic 2, DSLogic, Tektronix Smart Cursors):

### 7.1. Cơ chế Tự Khớp Sườn Xung Nam Châm (Magnetic Snap-to-Edge)

```text
Chuột di chuyển (t_mouse) ──────────> [Vùng bán kính hút R = 15 px]
                                                  │
                                         Sườn xung logic (t_edge)
                                                  │ (px_dist <= 15)
                                                  ▼
                                 [Cursor A/B Tự Hút Khóa Vào t_edge]
                                 [Hiển thị Snap Indicator Dot Ø 6px]
```

1. **Nguyên lý hoạt động:**
   * Khi người dùng kéo rê Cursor A hoặc Cursor B (hoặc dùng chế độ Quick Measure), hệ thống tự động dò tìm các sườn chuyển mức logic (Rising Edge / Falling Edge) gần nhất.
   * Nếu khoảng cách trên màn hình giữa vị trí chuột và sườn xung nhỏ hơn hoặc bằng **bán kính hút $R_{\text{snap}} = 15\text{ pixels}$**, vị trí con trỏ sẽ được khóa tự động (snap) dính chặt vào mốc thời gian $t_{\text{edge}}$ của mẫu chuyển mức logic thực tế.
   * Nếu khoảng cách $> 15\text{ px}$, con trỏ di chuyển tự do và mượt mà theo từng mẫu.

2. **Thuật toán & Hiệu năng xử lý:**
   * Mảng chuyển mức logic được trích xuất bằng NumPy vectorization khi nạp dữ liệu:
     $$\text{diff} = \Delta(\text{channel\_data}) \ne 0 \implies t_{\text{edge}} = \frac{\text{indices} - \text{trig\_offset}}{f_s}$$
   * Khi con trỏ di chuyển đến $t$, thuật toán tìm kiếm nhị phân $O(\log N)$ thông qua `np.searchsorted()` xác định sườn xung gần nhất trong thời gian $< 5\,\mu\text{s}$, không gây giật lag đồ họa ở 60 FPS.
   * Khoảng cách pixel được chuyển đổi động theo khung nhìn thực tế qua `ViewBox.mapViewToDevice()`, đảm bảo bán kính hút luôn là **15 pixels cố định** ở mọi mức Zoom (từ zoom bao quát toàn bộ 32K mẫu đến zoom sâu từng nano-giây).

3. **Thứ tự Ưu tiên Kênh để Hút (Channel Snapping Priority):**
   * **Ưu tiên 1:** Kênh mà con trỏ chuột đang trỏ vào (Track dưới trỏ chuột).
   * **Ưu tiên 2:** Kênh đang được chọn phân tích trong thẻ Measurements (`combo_meas_ch`).
   * **Ưu tiên 3:** Sườn xung gần nhất trên tất cả các kênh đang hiển thị.

4. **Chỉ thị trực quan khi Snap (Visual Snap Feedback):**
   * Vẽ một chấm tròn chỉ thị (Snap Indicator Dot) đường kính `6 px`, màu trắng viền xanh `#26a3d9` (cho Cursor A) hoặc viền đỏ `#ea5757` (cho Cursor B) tại giao điểm giữa sườn xung và vạch đo để người dùng nhận biết ngay lập tức là đã "hút dính".

---

### 7.2. Công Cụ Đo Nhanh Hai Điểm (Quick Measure Tool - Phím tắt `M`)

Bên cạnh thao tác kéo thả thước đo A & B truyền thống, hệ thống cung cấp công cụ đo nhanh 2-Click:

```
[Phím tắt 'M' hoặc Nút Thước Đo] ──> Trạng thái 1: Chờ Click điểm bắt đầu (Start Edge)
                                              │ (Click lần 1: Đặt Cursor A có Snap)
                                              ▼
                                     Trạng thái 2: Rê chuột xem trước (Live Preview Δt, f)
                                              │ (Click lần 2: Đặt Cursor B có Snap)
                                              ▼
                                     Trạng thái 3: Chốt đo, cập nhật HUD, mở Span bar
```

1. **Kích hoạt công cụ:**
   * Phím tắt bàn phím: **`M`** (Quick Measure Tool - chuẩn Saleae Logic).
   * Nút bấm trên Activity Rail / Toolbar: Nút công cụ thước đo nhanh `btn_rail_measure` với biểu tượng monochrome kỹ thuật **`|↔|`** (Dimension Span / Caliper) hoặc **`Δt`** (Delta Time).
   * Menu: `Measure` $\rightarrow$ `Quick Measure Tool (M)`.
2. **Quy trình tương tác:**
   * **Bước 1 (Chọn điểm đầu):** Con trỏ chuột chuyển thành hình chữ thập `Qt.CrossCursor`. Tooltip hướng dẫn hiển thị `"Click to place Cursor A (Snap active)"`. Khi người dùng click chuột trái, Cursor A được đặt tại vị trí click (tự động hút vào sườn xung nếu $\le 15\text{px}$).
   * **Bước 2 (Xem trước kết quả động):** Khi rê chuột, một vạch chỉ báo tạm thời nối từ Cursor A tới vị trí chuột. Nhãn thông số bám theo chuột hiển thị trực tiếp $\Delta t = |t_{\text{mouse}} - t_A|$ và tần số $f = 1/\Delta t$.
   * **Bước 3 (Chọn điểm cuối):** Click chuột trái lần 2 $\rightarrow$ Cursor B được đặt tại vị trí click (tự động hút vào sườn xung). Vùng đo được chốt lại, hiển thị thanh đo `|← Δt (f) →|` và cập nhật thông số lên HUD.
   * **Thoát / Hủy:** Bấm phím **`Escape`** ở bất kỳ bước nào sẽ hủy bỏ chế độ đo và khôi phục con trỏ chuột thông thường.

---

### 7.3. Điểm Soi Thời Gian Đơn Điểm (Point Inspector / Hover Timestamp)

* **Hover chuột trên Timeline hoặc Sóng:** Thanh trạng thái Status Bar hoặc Timeline hiển thị mốc thời gian tuyệt đối và tương đối so với Trigger:
  `T: +1.234500 ms | Sample: #13962 | Value: 0x55`
* **Click một lần vào sườn xung hoặc bong bóng ký tự giải mã:**
  * Tự động hiển thị thẻ chi tiết: Thời điểm bắt đầu ($t_{\text{start}}$), độ rộng xung ($t_{\text{width}}$), giá trị logic/ASCII của byte dữ liệu.

---

### 7.4. Cơ Chế Hút Ranh Giới Nhịp Bit Giao Thức (Analyzer-Aware Snapping)

Giải quyết bài toán đo đạc trên **chuỗi nhiều bit cùng mức logic (ví dụ chuỗi `1111` hoặc `0000`)** khi điện áp giữ nguyên đường thẳng tắp và không có sườn xung vật lý ($\Delta(\text{channel}) = 0$):

```text
Điện áp:       ┌────────────────────────────────────────────────────────┐
               │    Bit 0 (1)   │    Bit 1 (1)   │    Bit 2 (1)   │ ...     │
               └────────────────┴────────────────┴────────────────┴─────────
Ranh giới:     ▲                ▲                ▲                ▲
               │                │                │                │
            Start Edge    t_start+1*Tbit   t_start+2*Tbit   t_start+3*Tbit
          (Sườn xung thật) (Ranh giới ảo 1) (Ranh giới ảo 2) (Ranh giới ảo 3)
                 │                │                │                │
               [Cursor A]   [Cursor B Hút]  [Cursor B Hút]   [Cursor B Hút]
               (Snap dính)   (Snap dính!)    (Snap dính!)     (Snap dính!)
```

1. **Nguyên tắc phân biệt hai chế độ (Theo chuẩn Saleae Logic 2 & Sigrok PulseView):**
   * **Khi KHÔNG có Protocol Analyzer:** Trên các đoạn sóng phẳng lì (không có sườn xung $\Delta \ne 0$), con trỏ di chuyển hoàn toàn tự do (Free Movement), tuyệt đối không tự ý suy đoán tạo ra điểm hút ảo (tránh hiện tượng "khựng ma" làm phiền người đo).
   * **Khi CÓ Protocol Analyzer (UART, I2C, SPI):** Hệ thống tự động trích xuất các mốc thời gian logic của giao thức (Protocol Timing Boundaries) từ bộ giải mã:
     * *Với UART (8-N-1):* Ranh giới từng bit nhịp $k \cdot T_{\text{bit}}$ với $k = 0, 1, 2, \dots, 9$ (Start bit, 8 Data bits $D_0 \dots D_7$, Stop bit):
       $$t_{\text{bit\_boundary}}(k) = \frac{\text{start\_edge} + k \cdot T_{\text{bit}} - \text{trig\_offset}}{f_s}$$
     * *Với I2C:* Mốc thời gian điều kiện START, ranh giới byte Address, Read/Write bit, ACK/NACK bit, Data bytes, và điều kiện STOP.
     * *Với SPI:* Ranh giới bắt đầu/kết thúc từng byte truyền nhận trên MOSI và MISO.
2. **Hợp nhất danh sách Snap (Unified Snap List):**
   * Mảng ranh giới nhịp bit `decoder_edges[ch]` được hợp nhất vào danh sách điểm hút của kênh tương ứng.
   * Khi người dùng kéo Cursor B qua chuỗi `1111` trên kênh UART, con trỏ sẽ **tự động hút dính (khựng nam châm) tại đúng điểm kết thúc của Bit 1** ($t = t_{\text{start}} + 1 \times T_{\text{bit}}$), hiển thị đúng boong $\Delta t = T_{\text{bit}}$ (ví dụ $8.680\,\mu\text{s}$ ở 115200 bps).

---

## 8. Quy Chuẩn Kiểm Thử Tự Động Cho Hệ Thống Thước Đo Thông Minh

Mọi thay đổi mã nguồn liên quan đến thước đo bắt buộc phải vượt qua bộ kiểm thử tự động `software/tests/test_smart_cursors.py`:
1. **Kiểm thử Snap:** Đặt cursor lệch sườn xung 8px $\rightarrow$ Vị trí cursor phải tự động nhảy trùng khít với $t_{\text{edge}}$.
2. **Kiểm thử Free Movement:** Đặt cursor lệch sườn xung 25px ($> 15\text{px}$) trong vùng phẳng $\rightarrow$ Vị trí cursor giữ nguyên tọa độ tự do, không bị hút nhầm.
3. **Kiểm thử Ưu tiên Kênh:** Hover kênh nào thì ưu tiên hút sườn xung trên kênh đó.
4. **Kiểm thử Phím tắt `M` (2-Click Measure):** Kích hoạt chế độ đo bằng phím `M`, mô phỏng 2 sự kiện click chuột trái $\rightarrow$ Cursors A và B phải được ghim chính xác tại 2 mốc và tính đúng $\Delta t$.
5. **Kiểm thử Phím `Escape`:** Kích hoạt chế độ đo rồi bấm `Escape` $\rightarrow$ Trạng thái phải quay về thông thường, không bị kẹt chuột chữ thập.
6. **Kiểm thử Point Inspector:** Rê chuột trên sóng phát tín hiệu thời gian thực và số thứ tự mẫu.
7. **Kiểm thử Analyzer-Aware Snapping trên chuỗi phẳng `1111`:** Khi có UART Decoder, kéo cursor trên chuỗi `1111` phẳng lì (không có sườn xung vật lý) $\rightarrow$ Vị trí cursor phải tự động hút dính chính xác vào ranh giới bit thứ 1 ($t_{\text{start}} + 1 \times T_{\text{bit}}$), đo đúng $\Delta t = T_{\text{bit}}$.
8. **Kiểm thử hồi quy:** 100% PASS trên `test_auto_repeat.py`, `test_gui_integration.py`, `test_phase2_commercial.py` và `test_corner_cases_comprehensive.py`.

---

## 9. Đặc Tả Kỹ Thuật: Hệ Thống Đồng Bộ Kênh Tác Vụ Toàn Diện (Unified Active Channel Synchronization)

Hệ thống đồng bộ kênh tác vụ (`Active Channel`) tạo ra mối liên kết động, nhất quán và tức thì giữa toàn bộ các phân hệ trên giao diện: Cột nhãn sóng (Labels), Khung sóng (Viewport), Thiết lập Trigger (Device Settings), Đo đạc tự động (Measurements), và Bảng dữ liệu (Data Table).

```text
                                [Người dùng nhấp chọn Kênh N]
                    (Click vào Nhãn D0..D7 hoặc Track sóng Kênh N)
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ▼                                 ▼                                 ▼
[Cột Nhãn Sóng]                 [Device Settings]                  [Measurements]
• Highlight khung nhãn N        • Đồng bộ combo Trigger:           • Đồng bộ combo Đo:
  (Nền sáng #262628)              combo_ch = CHN (DN)                combo_meas_ch = CHN
• Vạch màu kênh rực rỡ          • Sẵn sàng bắt cạnh xung          • Tự động tính toán f, T,
• Các kênh khác về chìm                                              Duty, t_high, t_low...
        │                                                                   │
        └─────────────────────────────────┬─────────────────────────────────┘
                                          ▼
                                    [Data Table]
                   (Bảng Dữ Liệu Tự Thích Ứng Thông Minh - Dual Mode)
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼                                                 ▼
      [Kênh N có Protocol Analyzer]                     [Kênh N là Sóng Số Thô]
      (Ví dụ: CH0 UART, CH2 I2C, CH4 SPI)              (Ví dụ: CH1 PWM, CH3 Clock, GPIO)
      • Bảng hiện Packets giải mã                       • Bảng hiện Danh Sách Sườn Xung
      • Cột: Type, Start, Duration, Data                  (Transition Edge Timing List)
      • Click dòng -> Zoom tới byte                     • Cột: #, Edge (↑/↓), Time, Δt, f
                                                        • Click dòng -> Cuộn tới sườn xung
```

### 9.1. Quy Trình Kích Hoạt Kênh Tác Vụ (Active Channel Activation)
* Trạng thái `active_channel` ($0 \dots 7$) được quản lý tập trung ở `MainWindow` và đồng bộ với `WaveformWidget`.
* Mặc định khi khởi động: `active_channel = 0` (CH0).
* **3 Cách chuyển đổi kênh tác vụ:**
  1. Nhấp chuột trái vào Khung nhãn `D0..D7 Channel X` ở Cột nhãn bên trái.
  2. Hoặc nhấp chuột trái vào Track sóng của kênh đó trên khung vẽ (Plot Viewport).
  3. Hoặc chọn kênh từ Combobox trong thẻ Device Settings (`combo_ch`) hay thẻ Measurements (`combo_meas_ch`).

### 9.2. Cơ Chế Phản Hồi Trực Quan (Visual Channel Feedback)
* Khi `active_channel = N`:
  * Khung nhãn `channel_frames[N]` được làm nổi bật với màu nền `#262628`, tên kênh `Channel N` chuyển sang màu trắng sáng `#ffffff` (font-weight 700).
  * Toàn bộ 8 kênh (kể cả khi không được chọn) **luôn giữ nguyên 100% vạch màu sắc nhận diện đặc trưng gốc** (`border-left: 4px solid T.CHANNEL_COLORS[i]`) và chữ số `D0..D7` mang màu kênh gốc tương ứng; tuyệt đối không làm mờ, không thêm alpha/độ trong suốt để kỹ sư luôn nhận diện kênh tức thì tại mọi thời điểm.
  * Các khung nhãn không chọn giữ màu nền tối mặc định `#1b1b1c` và tên kênh màu xám sáng tiêu chuẩn `T.TEXT` (`#e0e0e0`, font-weight 500).
  * Thuật toán Magnetic Snap tự động gán `self.active_inspect_channel = N`, ưu tiên hút nam châm vào các sườn xung của kênh `N`.

### 9.3. Đồng Bộ Phân Hệ Device Settings & Measurements
* **Device Settings Card:** Tự động gọi `combo_ch.setCurrentIndex(N)`. Kỹ sư chỉ cần click vào sóng để chọn kênh trigger mà không cần mở danh sách chọn thủ công.
* **Measurements Card:** Tự động gọi `combo_meas_ch.setCurrentIndex(N)`. Cập nhật tức thì 7 chỉ số đo đạc thời gian thực và đổi màu tiêu đề thẻ theo màu kênh `N`.

### 9.4. Đề Xuất Kiến Trúc Xử Lý Bảng Dữ Liệu (Data Table Handling)

Để giải quyết câu hỏi kiến trúc cốt lõi: *"Khi người dùng chọn kênh, Bảng Dữ Liệu (Data Table) ở góc dưới bên phải nên phản ứng như thế nào cho chuẩn xác và chuyên nghiệp nhất?"*, hệ thống đề xuất **3 phương án kiến trúc**:

#### 🌟 Phương Án 1 (Khuyến nghị chuẩn công nghiệp - "Smart Dual-Mode Data Table"):
* **Bản chất:** Bảng dữ liệu tự động chuyển đổi chế độ hiển thị linh hoạt tùy theo việc kênh được chọn có gắn Protocol Analyzer hay là kênh số logic thông thường:
  1. **Nếu Kênh N có gắn Analyzer (UART / I2C / SPI):**
     * Tiêu đề bảng: `Data Table - UART (CHN)` hoặc `I2C (CHN)`.
     * Cột dữ liệu (5 cột): `[Marker] [Type] [Start Time] [Duration] [Decoded Data / ASCII]`.
     * Tương tác: Click vào dòng packet $\rightarrow$ Khung nhìn phóng to (zoom) trọn vẹn gói tin đó.
  2. **Nếu Kênh N KHÔNG có Analyzer (Kênh logic thô, ví dụ xung Clock, PWM, chân ngắt, Chip Select):**
     * Tiêu đề bảng: `Transition Edge List (CHN)` (Bảng danh sách thời điểm chuyển mức logic).
     * Cột dữ liệu (5 cột):
       * `#`: Số thứ tự sườn xung ($1, 2, 3\dots$).
       * `Edge`: Cạnh xung (`↑ RISING` màu xanh lá hoặc `↓ FALLING` màu cam).
       * `Timestamp`: Mốc thời gian xuất hiện sườn xung ($t$).
       * `Δt (Pulse)`: Khoảng thời gian từ sườn xung trước tới sườn xung này (độ rộng mức xung logic).
       * `Frequency`: Tần số chu kỳ tương ứng $f = 1 / (2 \cdot \Delta t)$ hoặc $1/\Delta t$.
     * Tương tác: Click vào bất kỳ sườn xung nào trong bảng $\rightarrow$ Viewport tự động căn giữa (Pan to Center) sườn xung đó trên màn hình với vạch chỉ báo rõ ràng!
* **Ưu điểm vượt trội:** Tận dụng 100% không gian bảng Data Table cho mọi kênh; giúp kỹ sư phần cứng phân tích chi tiết từng sườn xung GPIO/PWM bất thường (glitch, jitter) mà không máy đo nào tầm giá này có được.

#### Phương Án 2 ("Protocol Filter Only"):
* Bảng dữ liệu chỉ phục vụ Protocol Analyzer.
* Khi chọn Kênh N: Nếu kênh N có Analyzer thì hiện bảng dữ liệu của kênh N; nếu không có Analyzer thì làm mờ bảng và hiện thông báo: `No Protocol Analyzer attached to CHN. Click '•••' to attach UART/I2C/SPI.`
* **Đánh giá:** Đơn giản nhưng để trống lãng phí không gian bảng khi đo các kênh GPIO/PWM thông thường.

#### Phương Án 3 ("Tab Switcher: Packets vs Transitions"):
* Đặt 2 tab cố định phía trên bảng: Tab `Protocol Packets` và Tab `Transitions List`.
* Khi chọn kênh: Người dùng có thể chủ động chuyển qua lại giữa xem gói tin giải mã và xem danh sách sườn xung của kênh đó.
* **Đánh giá:** Tốt, nhưng tốn thêm một hàng tab chuyển đổi trên Drawer Panel vốn có chiều rộng giới hạn (310 px).

---

## 10. Quy Chuẩn Kiểm Thử Cho Tính Năng Đồng Bộ Kênh Tác Vụ

Mọi cập nhật mã nguồn liên quan đến đồng bộ kênh phải vượt qua bài kiểm thử tự động trong `software/tests/test_active_channel_sync.py`:
1. **Kiểm thử Click Label Sync:** Mô phỏng click vào khung nhãn Kênh 2 $\rightarrow$ Xác nhận `active_channel = 2`, `combo_ch` chọn CH2, `combo_meas_ch` chọn CH2, và khung nhãn 2 được highlight.
2. **Kiểm thử Click Waveform Track Sync:** Mô phỏng click vào tọa độ Y thuộc Track Kênh 4 $\rightarrow$ Xác nhận toàn bộ hệ thống đồng bộ về CH4.
3. **Kiểm thử Data Table Dual-Mode:**
   * Khi chọn CH0 (có UART): Bảng hiển thị 14 dòng ký tự UART.
   * Khi chọn CH1 (xung thô không có UART): Bảng tự động nạp danh sách Transition Edges của CH1 với đầy đủ cột Timestamp, Edge (↑/↓) và Δt.
4. **Kiểm thử Điều Hướng 2 Chiều Transitions:** Click vào dòng sườn xung thứ 5 trong bảng Transitions $\rightarrow$ Khung nhìn Viewport tự động cuộn đến đúng mốc thời gian của sườn xung đó.
