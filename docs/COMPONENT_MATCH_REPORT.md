# Báo Cáo Tiến Độ Đánh Giá Độ Giống Giao Diện Saleae Logic 2 (TV3)

> Tài liệu và ảnh crop lịch sử từ nhánh B. Các tỷ lệ bên dưới chưa được đo lại trên GUI tích hợp có bố cục/theme của A. Xem [báo cáo tích hợp](../software/INTEGRATION_REPORT.md). Lệnh `software.ui.proto` hiện chụp GUI đang dùng thay cho prototype độc lập.

> **Mục tiêu:** Tách nhỏ từng component trong ảnh chuẩn [`docs/ui_reference/saleae_logic_2.png`](ui_reference/saleae_logic_2.png) thành các ảnh crop riêng biệt, thiết kế và tối ưu lần lượt từng component, định lượng mức độ giống nhau (% Match Score) qua công cụ tự động [`software/ui/compare_components.py`](../software/ui/compare_components.py), đạt chuẩn $\ge 85\%$ mới chuyển sang component tiếp theo.

---

## 1. Phương Pháp Luận Định Lượng Độ Giống (% Match Score)

Điểm tương đồng tổng hợp được tính theo công thức trọng số khách quan:

$$\text{Total Match (\%)} = 0.40 \times \text{Color Histogram} + 0.40 \times \text{Block SSIM} + 0.20 \times \text{Feature Checklist}$$

* **Color Histogram Similarity (40%):** So sánh phân bố 3 kênh màu RGB (Cosine correlation), đảm bảo đúng mã màu đo đạc `#ffffff`, `#1b1b1c`, `#141415`, `#2c2c2e`, `#2e9949`.
* **Block SSIM (40%):** Chỉ số tương đồng cấu trúc chuẩn khối trượt $11\times 11$ (Wang et al. 2004), so khớp vị trí icon, glyph chữ, đường viền và khoảng cách pixel thực tế.
* **Feature Checklist (20%):** Kiểm tra danh sách các chi tiết trực quan bắt buộc của component.

---

## 2. Bảng Theo Dõi 8 Component (Lộ Trình Từng Bước)

Toàn bộ ảnh crop tham chiếu và render được lưu trữ tại `docs/ui_reference/crops/`:

| STT | Component | Tọa độ Bounding Box (X1, Y1, X2, Y2) | Kích thước Pixel | Trạng thái | Điểm Đạt Được |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **1** | **Right Action Rail** (Dải nút Start & Tools) | `(1690, 77, 1780, 1137)` | 90 × 1060 px | **ĐÃ HOÀN THÀNH** | **94.8%** (Đạt chuẩn) |
| **2** | **Top Menu Bar** (Thanh Menu đỉnh) | `(0, 0, 1780, 76)` | 1780 × 76 px | **ĐÃ HOÀN THÀNH** | **88.0%** (Đạt chuẩn) |
| **3** | **Bottom Bar** (Thanh Session & Zoom) | `(0, 1137, 1780, 1197)` | 1780 × 60 px | **ĐÃ HOÀN THÀNH** | **89.4%** (Đạt chuẩn) |
| **4** | **Channel Label Column** (Cột nhãn kênh) | `(0, 77, 270, 1137)` | 270 × 1060 px | **ĐÃ HOÀN THÀNH** | **85.7%** (Đạt chuẩn) |
| **5** | **Time Ruler** (Thước thời gian & Trigger) | `(270, 77, 1255, 123)` | 985 × 46 px | **ĐÃ HOÀN THÀNH** | **87.4%** (Đạt chuẩn) |
| **6** | **Analyzers Panel** (Panel Analyzers & Card Trigger) | `(1255, 77, 1690, 350)` | 435 × 273 px | **ĐÃ HOÀN THÀNH** | **88.7%** (Đạt chuẩn) |
| **7** | **Data Table & Search** (Bảng gói tin 4 cột) | `(1255, 350, 1690, 1137)` | 435 × 787 px | **ĐÃ HOÀN THÀNH** | **85.1%** (Đạt chuẩn) |
| **8** | **Waveform Viewport** (Khung sóng & Bong bóng) | `(270, 123, 1255, 1137)` | 985 × 1014 px | **ĐÃ HOÀN THÀNH** | **92.8%** (Đạt chuẩn) |

---

## 3. Nghiệm Thu Component 1: Right Action Rail
```text
Component 1 (Right Action Rail):
- Kích thước: (90, 1060) px
- Color Histogram Similarity: 99.98%
- Block SSIM Similarity:     86.92%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 94.8% (ĐẠT CHUẨN XUẤT SẮC)
--------------------------------------------------
```

---

## 4. Nghiệm Thu Component 2: Top Menu Bar
```text
Component 2 (Top Menu Bar):
- Kích thước: (1780, 76) px
- Color Histogram Similarity: 99.98%
- Block SSIM Similarity:     70.03%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 88.0% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```

---

## 5. Nghiệm Thu Component 3: Bottom Bar
```text
Component 3 (Bottom Bar):
- Kích thước: (1780, 60) px
- Color Histogram Similarity: 99.98%
- Block SSIM Similarity:     73.61%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 89.4% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```

---

## 6. Nghiệm Thu Component 4: Channel Label Column

### 6.1. Phân tích Pixel thực tế từ ảnh crop `ref_comp4_channel_labels.png`
1. **Khoảng đệm trên cùng:** Chiều cao đúng $45\text{ px}$ khớp với thước thời gian Viewport.
2. **Dải màu dọc mép trái:** Rộng đúng $4\text{ px}$, màu chuẩn theo `CHANNEL_COLORS`:
   - D0: `#d4d4d4` ($Y = 46 \dots 142\text{ px}$, cao $96\text{ px}$ do có gắn Analyzer).
   - D1: `#c39577` ($Y = 143 \dots 240\text{ px}$, cao $97\text{ px}$ do có gắn Analyzer).
   - D2: `#f66c7e` ($Y = 241 \dots 307\text{ px}$, cao $66\text{ px}$).
   - D3..D7: Các màu chuẩn tiếp theo.
3. **Nội dung nhãn:**
   - Mã kênh: In đậm `D0`..`D7`, màu sắc đồng bộ với dải màu kênh.
   - Tên kênh: In trắng `Channel 0`..`Channel 7`, Font Segoe UI 15px.
   - Chip gắn bộ giải mã:
     - D0: Ô vuông `#d3ccb0` + chữ `Async Serial`.
     - D1: Ô vuông `#4fc3e8` + chữ `I2C - SDA`.
4. **Vạch ngăn cách:** Đường viền dưới mỗi hàng `$1\text{ px}$` `#3f3f43`, đường viền phải ngăn cách với vùng sóng rộng `$1\text{ px}$` `#57575e`.

### 6.2. Kết Quả Định Lượng Bằng Công Cụ `compare_components.py`
```text
Component 4 (Channel Label Column):
- Kích thước: (270, 1060) px
- Color Histogram Similarity: 99.96%
- Block SSIM Similarity:     64.41%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 85.7% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```
* **Ảnh crop tham chiếu:** `docs/ui_reference/crops/ref_comp4_channel_labels.png`
* **Ảnh crop render:** `docs/ui_reference/crops/gen_comp4_channel_labels.png`

---

## 7. Nghiệm Thu Component 5: Time Ruler

### 7.1. Phân tích Pixel thực tế từ ảnh crop `ref_comp5_time_ruler.png`
1. **Kích thước hình học:** Rộng đúng $985\text{ px}$, cao $46\text{ px}$, tọa độ `(270, 77, 1255, 123)`.
2. **Cấu trúc 2 hàng mốc thời gian:**
   - **Hàng 1 (Tuyệt đối):** `395 ms` (bắt đầu tại $X = 10\text{ px}$), `396 ms` (bắt đầu tại $X = 627\text{ px}$), Font Segoe UI 8pt Bold `#ffffff`.
   - **Hàng 2 (Tương đối):** Mốc `+0.5 ms`, `+0.6 ms`, `+0.7 ms`, `+0.8 ms`, `+0.9 ms`, `+0.1 ms`, `+0.2 ms`, `+0.3 ms` căn giữa tại các vị trí tick thực tế: `[39, 157, 274, 391, 509, 743, 861, 978]`.
   - Vị trí $X = 627$ nằm dưới `396 ms` không có mốc tương đối ở hàng 2.
3. **Vạch Subtick:** Đường kẻ dọc 4px từ $Y = 40$ đến $Y = 43$, màu `#57575e` chỉ thẳng xuống mép trên vùng sóng.
4. **Đường viền:** Viền trên $1\text{ px}$ màu `#141415`, viền dưới $1\text{ px}$ màu `#303136`.

### 7.2. Kết Quả Định Lượng Bằng Công Cụ `compare_components.py`
```text
Component 5 (Time Ruler):
- Kích thước: (985, 46) px
- Color Histogram Similarity: 100.0%
- Block SSIM Similarity:      68.46%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 87.4% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```
* **Ảnh crop tham chiếu:** `docs/ui_reference/crops/ref_comp5_time_ruler.png`
* **Ảnh crop render:** `docs/ui_reference/crops/gen_comp5_time_ruler.png`

---

## 8. Nghiệm Thu Component 6: Analyzers Panel

### 8.1. Phân tích Pixel thực tế từ ảnh crop `ref_comp6_analyzers_panel.png`
1. **Kích thước hình học:** Rộng đúng $435\text{ px}$, cao $273\text{ px}$, tọa độ `(1255, 77, 1690, 350)`.
2. **Tiêu đề & Nút thêm Analyzer:**
   - Tiêu đề `Analyzers` tại $X = 23 \dots 126\text{ px}$, $Y = 35 \dots 57\text{ px}$, Font Segoe UI 21px Bold màu `#ffffff`.
   - Nút `+` tại $X = 389 \dots 403\text{ px}$, $Y = 37 \dots 51\text{ px}$, màu `#8b8b93`.
3. **Danh sách Analyzer đang hoạt động:**
   - **Hàng 1:** Ô vuông `#d3ccb0` + nhãn in đậm `Async Serial` + chấm tròn trạng thái màu xanh lá `#2e9949`, vị trí $Y = 101 \dots 120\text{ px}$.
   - **Hàng 2:** Ô vuông xanh dương `#4fc3e8` + nhãn in đậm `I2C` + chấm tròn trạng thái màu xanh lá `#2e9949`, vị trí $Y = 159 \dots 173\text{ px}$.
4. **Thẻ thu gọn Trigger View:**
   - Card bo góc $6\text{ px}$, viền `$1\text{ px}$` `#3a3a3e`, nền `#2c2c2e`, kích thước $393 \times 54\text{ px}$ tại $Y = 197 \dots 252\text{ px}$.
   - Nhãn `›  Trigger View ⚠` bên trái, nút đóng tròn `✕` nền `#3a3a3e` bên phải.
5. **Đường viền ngăn cách:**
   - Viền trái `$1\text{ px}$` `#57575e` ngăn cách với vùng Waveform.

### 8.2. Kết Quả Định Lượng Bằng Công Cụ `compare_components.py`
```text
Component 6 (Analyzers Panel):
- Kích thước: (435, 273) px
- Color Histogram Similarity: 99.94%
- Block SSIM Similarity:      71.69%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 88.7% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```
* **Ảnh crop tham chiếu:** `docs/ui_reference/crops/ref_comp6_analyzers_panel.png`
* **Ảnh crop render:** `docs/ui_reference/crops/gen_comp6_analyzers_panel.png`

---

## 9. Nghiệm Thu Component 7: Data Table & Search

### 9.1. Phân tích Pixel thực tế từ ảnh crop `ref_comp7_data_table.png`
1. **Kích thước hình học:** Rộng đúng $435\text{ px}$, cao $787\text{ px}$, tọa độ `(1255, 350, 1690, 1137)`.
2. **Thanh Header tiêu đề:**
   - Tiêu đề `Data` tại $X = 23 \dots 75\text{ px}$, $Y = 7 \dots 23\text{ px}$, Font Segoe UI 21px Bold màu `#ffffff`.
   - Vòng tròn trợ giúp `?` đường kính $18\text{ px}$, viền `#57575e`, chữ xám `#8b8b93`.
   - Chấm tròn xanh lá `✓` `#2e9949`.
   - Cụm nút công cụ bên phải: Icon bảng `▦` màu `#ffffff` và Icon Terminal `>_` có viền `#57575e`.
3. **Ô tìm kiếm Type to search:**
   - Chiều cao $47\text{ px}$ ($Y = 53 \dots 100\text{ px}$), nền `#2c2c2e`, viền `$1\text{ px}$` `#3a3a3e`, bo góc $4\text{ px}$.
   - Chữ placeholder `Type to search` font 14px Segoe UI, nút menu ba chấm `⋮` bên phải.
4. **Bảng dữ liệu 4 cột chuyên dụng:**
   - **Cột 0 (Marker):** Rộng $26\text{ px}$ (`setMinimumSectionSize(10)`), vẽ ô vuông màu $8 \times 8\text{ px}$ qua `QStyledItemDelegate`:
     - Gói UART: Ô vuông vàng `#cdb469`.
     - Gói I2C: Ô vuông xanh dương `#4a90e2`.
   - **Cột 1 (Type):** Rộng $113\text{ px}$, chứa các giá trị `data`, `start`, `address`, `stop`.
   - **Cột 2 (Start):** Rộng $165\text{ px}$, mốc thời gian SI độ phân giải cao (`86.8 µs`, `1.277496 ms`...).
   - **Cột 3 (Duration):** Rộng $86\text{ px}$ (co giãn vừa khít lề phải), độ rộng xung (`82.464 µs`, `8 ns`...).
   - **Chiều cao hàng & Màu nền:** Chiều cao hàng đúng $42\text{ px}$, màu nền xen kẽ (Alternating Rows) `#141415` và `#1b1b1c`. Viền dọc phân cách giữa các cột `$1\text{ px}$` `#57575e`.

### 9.2. Kết Quả Định Lượng Bằng Công Cụ `compare_components.py`
```text
Component 7 (Data Table & Search):
- Kích thước: (435, 787) px
- Color Histogram Similarity: 99.91%
- Block SSIM Similarity:      62.82%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 85.1% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```
* **Ảnh crop tham chiếu:** `docs/ui_reference/crops/ref_comp7_data_table.png`
* **Ảnh crop render:** `docs/ui_reference/crops/gen_comp7_data_table.png`

---

## 10. Nghiệm Thu Component 8: Waveform Viewport

### 10.1. Phân tích Pixel thực tế từ ảnh crop `ref_comp8_waveform_viewport.png`
1. **Kích thước hình học:** Rộng đúng $985\text{ px}$, cao $1014\text{ px}$, tọa độ `(270, 123, 1255, 1137)`.
2. **Hệ thống Lưới dọc nét đứt (Vertical Dashed Grid):**
   - Vạch lưới dọc nét đứt màu `#303136` xuất phát đồng bộ từ các mốc tick của Thước thời gian: `X = [39, 157, 274, 391, 509, 626, 743, 861, 978]`.
   - Vạch $X = 626$ (mốc 396 ms chính) có mật độ điểm đậm rõ nét.
3. **Phân tầng kênh & Đường viền ngang:**
   - Đường kẻ ngang $1\text{ px}$ `#57575e` phân tách chuẩn xác các hàng kênh tại tọa độ $Y = [95, 193, 260, 328, 395, 463, 596, 730, 863, 997]$.
   - Chiều cao các hàng kỹ thuật số: D0 ($95\text{ px}$), D1 ($98\text{ px}$), D2..D5 ($67\text{ px}$).
   - Chiều cao các hàng tương tự (A0..A3): $133\text{ px}$ mỗi hàng.
4. **Chú thích In-line Protocol Overlays & Điểm chấm Bit:**
   - **Kênh D0 (UART):** Các khối bo góc màu vàng `#d3ccb0` hiển thị giá trị hex (`0xE6`, `0xE7`, `0xE8`, `0xE9`, `0xEA`...) chu kỳ $204\text{ px}$, bề rộng $97\text{ px}$. Dưới mỗi khối là 8 chấm trắng nhỏ đánh dấu tâm từng bit. Nhãn `H` và `L` ở mép trái.
   - **Kênh D1 (I2C):** Các khối bo góc màu xanh dương `#6c84cd` (`W[0x2]`, `0xDC`, `R`, `0xDF`...), chấm tròn START màu xanh lá `#22c55e`, ô vuông STOP/ACK màu cam `#f97316`.
5. **Thang đo & Nút tự động co giãn Analog:**
   - Thang đo $\pm 10\text{ V}$ (`10 V`, `0 V`, `-10 V`) màu `#8b8b93` ở mép trái mỗi hàng analog.
   - Nút tự động co giãn `↕` trong khung bo góc bán trong suốt ở mép phải.

### 10.2. Kết Quả Định Lượng Bằng Công Cụ `compare_components.py`
```text
Component 8 (Waveform Viewport):
- Kích thước: (985, 1014) px
- Color Histogram Similarity: 100.0%
- Block SSIM Similarity:      81.92%
- Visual Feature Checklist:   100.0%
--------------------------------------------------
TỔNG ĐIỂM TƯƠNG ĐỒNG: 92.8% (CHÍNH THỨC ĐẠT CHUẨN)
--------------------------------------------------
```
* **Ảnh crop tham chiếu:** `docs/ui_reference/crops/ref_comp8_waveform_viewport.png`
* **Ảnh crop render:** `docs/ui_reference/crops/gen_comp8_waveform_viewport.png`

---

## 11. Bảng Tổng Hợp Nghiệm Thu Toàn Diện 8/8 Component

| STT | Component Tên Gọi | Tọa độ Bounding Box | Kích thước | Histogram | Block SSIM | Checklist | Điểm Đạt Được | Đánh giá |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **Right Action Rail** | `(1690, 77, 1780, 1137)` | 90 × 1060 px | 99.98% | 86.92% | 100% | **94.8%** | **ĐẠT XUẤT SẮC** |
| **2** | **Top Menu Bar** | `(0, 0, 1780, 76)` | 1780 × 76 px | 99.98% | 70.03% | 100% | **88.0%** | **ĐẠT CHUẨN** |
| **3** | **Bottom Bar** | `(0, 1137, 1780, 1197)` | 1780 × 60 px | 99.98% | 73.61% | 100% | **89.4%** | **ĐẠT CHUẨN** |
| **4** | **Channel Label Column** | `(0, 77, 270, 1137)` | 270 × 1060 px | 99.96% | 64.41% | 100% | **85.7%** | **ĐẠT CHUẨN** |
| **5** | **Time Ruler** | `(270, 77, 1255, 123)` | 985 × 46 px | 100.00% | 68.46% | 100% | **87.4%** | **ĐẠT CHUẨN** |
| **6** | **Analyzers Panel** | `(1255, 77, 1690, 350)` | 435 × 273 px | 99.94% | 71.69% | 100% | **88.7%** | **ĐẠT CHUẨN** |
| **7** | **Data Table & Search** | `(1255, 350, 1690, 1137)` | 435 × 787 px | 99.91% | 62.82% | 100% | **85.1%** | **ĐẠT CHUẨN** |
| **8** | **Waveform Viewport** | `(270, 123, 1255, 1137)` | 985 × 1014 px | 100.00% | 81.92% | 100% | **92.8%** | **ĐẠT CHUẨN** |
| **Σ** | **TOÀN BỘ GIAO DIỆN (8/8)** | `(0, 0, 1780, 1197)` | 1780 × 1197 px | **99.97%** | **72.48%** | **100%** | **89.0%** | **100% ĐẠT CHUẨN ($\ge 85\%$)** |
