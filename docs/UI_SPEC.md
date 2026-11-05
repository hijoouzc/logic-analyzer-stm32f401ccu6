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
4. **Điểm mẫu phần cứng (Hardware Sample Points):** Tự động hiển thị chấm mẫu rời rạc khi người dùng Zoom sâu ($\ge 6\,\text{px/sample}$) và ẩn khi Zoom xa.

---

## 6. Ánh Xạ Trạng Thái Giao Diện Với Giao Thức Firmware (SSoT)
Chi tiết khung truyền xem [`spec/protocol.md`](../spec/protocol.md):
* **Nhận Pong (`5A A5 04 ...`):** Đổi trạng thái kết nối sang xanh `"Connected: STM32F401 (v1.0.0)"`.
* **Nhận Data Frame (Status `0x00` - Triggered):** Vẽ dạng sóng, đặt vạch trigger vàng cam tại mẫu $t_0 = 0\,\text{s}$.
* **Nhận Data Frame (Status `0x01` - Free-run):** Vẽ dạng sóng với gốc thời gian $t = 0\,\text{s}$ tại mẫu đầu tiên, đặt vạch `"FREE-RUN"`.
* **Nhận Data Frame (Status `0x02` - Timeout):** Hiển thị vạch `"TIMEOUT"`, vẫn vẽ đầy đủ 32.768 mẫu thu được.
* **Nhận NAK (`0xE0` - Checksum, `0xE1` - Rate, `0xE2` - Trigger, `0xE3` - Busy):** Hiển thị hộp thoại cảnh báo chi tiết mã lỗi cho người dùng.
* **Đang thu thập 32.776 Byte:** Đổi nút tròn Start sang nút vuông Stop màu đỏ (`#db4c39`) hỗ trợ hủy lệnh tức thì (`CMD_ABORT`).
