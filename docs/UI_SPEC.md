# UI_SPEC.md — Đặc tả giao diện GUI Logic Analyzer (TV3)

Tài liệu cho người viết GUI và AI agent. Giao thức: `spec/protocol.md` (nguồn sự thật duy nhất).
Màu, kích thước, stylesheet: `software/gui/theme.py` (không ghi màu/kích thước trực tiếp ở nơi khác).
Prototype tham khảo: `software/gui/proto.py` (phiên bản v3). Ảnh tham chiếu bố cục: `docs/ui_reference/` (chỉ dùng nội bộ; dùng tên và logo riêng cho phần mềm của nhóm).

## 1. Mục tiêu
Giao diện nền tối, kiểu phần mềm phân tích logic phổ biến: các hàng kênh xếp chồng, trục thời gian chung, giải mã UART hiện ngay trên sóng. Thiết bị chỉ chụp một lần 32768 mẫu (không streaming).

## 2. Bố cục (cửa sổ logic 1280×860; mọi kích thước dưới đây là px logic)
```
+----------------------------------------------------------------------+
| File  Edit  Capture  Measure  View  Help                (menu trắng) |
+------------------------------------+------------------+--------------+
| nhãn | thước thời gian (0=trigger) | Analyzers   [+]  |  [Start]     |
| D0   | sóng CH0 + ô giải mã        | Async Serial  ✓  |  [icon]      |
| D1   | sóng CH1                    | > Trigger View ✕ |  [icon]      |
| ...  | ... (H/L ở mép trái)        | Data ✓           |  [icon]      |
| D7   | sóng CH7                    | [Type to search] |              |
|      |                             | bảng Data        |              |
+------+-----------------------------+------------------+--------------+
| Session 0 | Session 1 | +                              128 µs ^      |
+----------------------------------------------------------------------+
```

| Vùng | Kích thước | Ghi chú |
|---|---|---|
| Cột nhãn | 194 px | dải màu 4 px ở mép trái |
| Panel phải (Analyzers/Data) | 313 px | |
| Dải icon phải | 65 px | nút Start tròn ở trên cùng, Ø 50 px |
| Thước thời gian | 32 px | |
| Thanh dưới (tab Session + mức zoom) | 42 px | |
| Hàng kênh | **giãn lấp đầy** vùng sóng | xem mục 3 |
| Hàng có analyzer | 1.45 × hàng thường | |

## 3. Quy tắc hàng kênh
- Chiều cao hàng thường = (chiều cao vùng sóng) / (7 + 1.45), có tối thiểu 47 px. 8 hàng luôn lấp đầy vùng sóng, không để trống nửa dưới.
- Mỗi hàng: dải màu theo `CHANNEL_COLORS`; nhãn gồm mã nhỏ có màu ("D0") và tên lớn màu trắng ("Channel 0"); hàng gắn analyzer có thêm chip nhỏ (ô vuông màu + "Async Serial").
- Sóng số: nét 1 px màu kênh, dạng vuông đúng cạnh (`stepMode`); nhãn **H** và **L** ở mép trái mỗi hàng; vạch ngăn mảnh giữa các hàng.
- Vạch lưới dọc nét đứt, cách nhau 100 µs (đổi theo zoom).

## 4. Thước thời gian và trigger
- Mốc tương đối: "+0.1 ms", "+0.2 ms"… Đơn vị tự đổi theo zoom.
- Mốc 0 tại mẫu trigger (index 6554); mẫu pre-trigger ở phía âm.
- Vạch dọc màu `TRIGGER_MARKER` tại 0. Với Free-run (Status 0x01), vẫn vẽ vạch nhưng ghi chú "free-run" vì `trig_offset` chỉ mang tính tham khảo.
- Zoom/pan bằng chuột; các kênh dùng chung trục X.

## 5. Giải mã UART (giai đoạn 1)
- Chọn kênh, baud mặc định 115200, 8N1.
- Ô chữ nhật nền `DECODE_UART_BG`, chữ `DECODE_UART_FG`, nằm trên sóng, rộng bằng một ký tự (từ start đến stop bit); nội dung hex (0x54) hoặc ASCII.
- Chấm trắng nhỏ trên sóng tại tâm mỗi bit dữ liệu.
- I2C/SPI để giai đoạn 2.

## 6. Panel phải
- **Analyzers:** tiêu đề + nút "+"; mỗi analyzer một dòng (ô vuông màu, tên, dấu ✓ xanh). Mục thu gọn "Trigger View" có nút ✕.
- **Data:** tiêu đề + ✓; ô "Type to search"; bảng 4 cột: ô màu | Type | Start | Duration (không có thanh cuộn ngang).

## 7. Điều khiển capture (khớp lệnh 5 byte)
- Tốc độ lấy mẫu (RATE_IDX 0..8): 6 MHz, 3 MHz, 2 MHz, 1 MHz, 500 kHz, 200 kHz, 100 kHz, 50 kHz, 10 kHz.
- Kênh trigger CH0..CH7 + chế độ Free-run / Rising / Falling (TRIG_CFG).
- Nút Start, Stop/Abort, Check Connection (Ping).
- Con trỏ đo A/B: kéo được, hiện Δt và tần số = 1/Δt.

## 8. Ánh xạ trạng thái UI với giao thức
| Sự kiện | UI |
|---|---|
| Pong `5A A5 04 …` | "Connected (v1.0.0)" màu xanh |
| Data frame Status 0x00 | Vẽ sóng, đặt vạch trigger |
| Data frame Status 0x01 | Vẽ sóng, ghi "Free-run" |
| Data frame Status 0x02 | Cảnh báo "Timeout — không có trigger", vẫn vẽ 32 KB |
| Control frame 0x05 | "Capture aborted" |
| NAK 0xE0–0xE3 | Hộp thông báo lỗi theo mã (checksum / rate / trigger / busy) |
| Quá thời gian chờ | Báo mất kết nối; không gửi lệnh mới cho đến khi xử lý xong |

Trong lúc nhận gói 32776 byte: khóa mọi nút điều khiển.
Thời gian chờ GUI: T_gui = (16384 + 26214)/fs + 2.0 s + 1.5 s.

## 9. Kỹ thuật (PyQt5 + pyqtgraph)
- Một `PlotWidget`, mỗi kênh cộng độ lệch dọc; hoặc 8 `PlotItem` liên kết `setXLink`. Cột nhãn là các widget có chiều cao khớp từng hàng.
- Đọc serial trong `QThread`. Xác thực XOR payload trước khi vẽ; sai thì báo lỗi, không vẽ.
- Bit kênh k của mẫu: `(byte >> k) & 1`.
- Làm việc độc lập bằng `software/tests/sample_data_1mhz.bin`.

## 10. Đánh giá độ giống ảnh tham chiếu (prototype, thang điểm tự đặt)
| Phiên bản | Tổng hợp |
|---|---|
| v1 (spec đầu tiên) | ~65% |
| v2 (chỉnh kích thước theo ảnh) | ~77% |
| v3 (hàng giãn, nhãn, chấm bit, H/L, panel) | **~85%** |

Thang điểm gồm màu (histogram), cấu trúc bố cục (SSIM), tỉ lệ vùng và checklist 20 thành phần; chỉ dùng để so sánh các bản. Chạy lại: `python3 proto.py v3 v3.png && python3 compare.py`.

Còn thiếu so với ảnh gốc: hàng thời gian tuyệt đối ("395 ms"), chip giải mã bo góc có viền, một số nút nhỏ (đều không bắt buộc).

## 11. Ngoài phạm vi
Streaming thời gian thực, plugin analyzer, nhiều giao thức, kênh analog.

## 12. Ưu tiên cho mốc 11/11
1. Ping + Start + vẽ 8 kênh + vạch trigger + zoom/pan.
2. Giải mã UART trên sóng.
3. Con trỏ đo, lưu/mở file, đổi tên/màu kênh.
