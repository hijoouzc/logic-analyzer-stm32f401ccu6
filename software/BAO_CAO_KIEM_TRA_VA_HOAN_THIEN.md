# Báo cáo kiểm tra và hoàn thiện phần mềm PC

> Báo cáo lịch sử được giữ từ nhánh B. Các kết quả pytest, môi trường `.venv` và nhận xét UI bên dưới thuộc lần thực hiện được ghi trong tài liệu gốc; không phải xác nhận cho bản tích hợp hiện tại. Xem [báo cáo tích hợp](INTEGRATION_REPORT.md) để biết thay đổi và giới hạn kiểm chứng mới nhất.

Ngày thực hiện: 06/11/2026 (Asia/Bangkok). Nhánh phát triển ban đầu: `sw/complete-software`. Nhánh bàn giao theo yêu cầu: `feat/complete-stm32-software`.

Repository: https://github.com/NgTruongGiang2005/logic-analyzer-stm32f401ccu6

Commit nền: `2d327585fe687d6ecd93f05ab293cabcf6d8e1bc`.

## 1. Phạm vi và tài liệu đã đọc

Toàn bộ thay đổi mã nguồn, test, dữ liệu mẫu và báo cáo nằm trong `software/`. Nhánh bàn giao được tạo từ trạng thái local đã hoàn thiện, giữ nguyên toàn bộ mã nguồn và các thay đổi chưa commit trước khi đóng gói commit để đưa lên GitHub. Nhánh `main` được giữ nguyên.

Đã đọc 9 file Markdown có sẵn trong repository:

- `AGENTS.md` — quy chuẩn dành cho firmware; công việc lần này tuân theo yêu cầu trực tiếp chỉ sửa software của người dùng.
- `README.md` — phân công TV3, cấu trúc dự án, cách chạy và quy ước nhánh `sw/`.
- `spec/protocol.md` — nguồn ưu tiên cao nhất cho giao thức PC–MCU.
- `spec/logic_analyzer_specification.md` — kiến trúc và yêu cầu phần mềm/kiểm thử.
- `spec/Logic_analyzer_requirements.md` — đề bài và phạm vi đồ án.
- `docs/UI_SPEC.md` — bố cục, 8 kênh, trigger, giải mã, timeout và khóa điều khiển.
- `docs/COMPONENT_MATCH_REPORT.md` — bố cục tham chiếu; không sử dụng các điểm tương đồng trong báo cáo cũ làm bằng chứng kiểm thử cho lần sửa này.
- `firmware/tests/README.md` — điều kiện kiểm thử phần cứng và loopback.
- `report/slides_11_11/SLIDE_PROGRESS_REPORT_TV1.md` — ngữ cảnh bàn giao firmware và tích hợp TV3.

Giữ nguyên hợp đồng truyền thông: lệnh 5 byte; control frame 7 byte; data frame 32.776 byte; payload 32.768 mẫu; trigger offset 6554; little-endian; XOR payload và XOR control; 9 mức tần số theo đặc tả. Không thay đổi firmware, hardware hoặc spec.

## 2. Các lỗi được xác định và hướng xử lý

### 2.1. Lỗi Python/Qt trên Windows

1. **`NameError: name 'Tuple' is not defined`**: annotation trong `gui/cursors.py` dùng `Tuple` nhưng không import. Đã bổ sung import.
2. **`ModuleNotFoundError: No module named 'termios'`**: `test_gui_integration.py` và mock cũ import `pty`, vốn phụ thuộc Unix. Không thể sửa bằng cách cài `termios` qua pip trên Windows. Đã thay đường giả lập/test tích hợp bằng TCP loopback, dùng được trên Windows và Linux.
3. **Dừng khi tạo `QApplication`**: Qt 5.15.2 tự suy ra đường dẫn plugin thành `D:/Tài Li?u L?p Trình C...`; kiểm tra đường dẫn đó trả về không tồn tại. Đã bổ sung `qt_bootstrap.py`, lấy đường dẫn thật từ `PyQt5.__file__` và truyền qua API Unicode `QCoreApplication.setLibraryPaths` trước khi tạo ứng dụng. Đã xác nhận `QApplication` khởi tạo thành công tại chính thư mục có dấu hiện tại.
4. **Ảnh offscreen không có chữ**: Qt offscreen trên Windows trả về danh sách font rỗng. Bootstrap chỉ định thư mục font Windows qua `QT_QPA_FONTDIR` cho chế độ offscreen. Đã kiểm tra lại ảnh GUI có chữ, số, menu và bảng dữ liệu. Không cần đổi tên thư mục dự án hoặc cấu hình PATH toàn máy.

### 2.2. Giao thức và kết nối

- Start giả lập trước đây gọi `start_capture(..., mock_mode=True)` trong khi client không có tham số đó. Đã thống nhất cách kết nối `OFFLINE_MOCK` và chạy qua worker.
- Bộ đọc trước đây chưa xử lý đầy đủ sync giả, header sai, phản hồi trễ; có tính checksum control nhưng không dùng kết quả. Đã gom quy tắc vào `protocol.py`, kiểm tra header/count/offset/status, XOR control và XOR payload trước khi trả dữ liệu.
- Thêm quét trượt qua byte nhiễu, khung phân mảnh, header không hợp lệ; đối chiếu echo của NAK với lệnh hiện tại, bỏ qua PONG hoặc NAK trễ của lệnh khác.
- Abort trước đây có thể báo thành công dù không có ACK hợp lệ. Nay chỉ thành công sau control frame ABORTED có checksum và nội dung đúng, hoặc trả lỗi timeout.
- Dùng đồng hồ monotonic và ngân sách chờ `42598 / fs + 3.5` giây. Tần số 10 kHz có ngân sách khoảng 7,76 giây.
- Dùng khóa thao tác để các luồng không tranh nhau đọc/ghi/đóng serial. Mở cổng bằng `serial_for_url` hỗ trợ cả COM thật và URL mock TCP.

### 2.3. Worker và GUI

- Ping và capture chạy trong `QThread`; tránh đọc serial đồng bộ trên luồng GUI.
- Khóa cả menu, shortcut và widget thay đổi capture khi đang bận. Gọi Start nhiều lần không tạo thêm worker.
- Yêu cầu Abort từ GUI chỉ đặt cờ; worker đang sở hữu serial thực hiện lệnh và đọc ACK. Khi đã nhận header data, khóa Abort theo trạng thái TRANSFERRING.
- Loại bỏ `QThread.terminate()`. Khi đóng cửa sổ lúc bận, app chờ worker kết thúc/timeout, đóng cổng rồi mới đóng cửa sổ.
- Tích hợp hộp cấu hình analyzer thật qua nút `+`: UART chọn kênh/baud; I2C chọn SCL/SDA; SPI chọn SCK/MOSI/MISO/CS, mode 0–3, bit order và cực tính CS. Một analyzer được chọn hoạt động tại một thời điểm; kết quả hiển thị ở bảng và chú thích sóng.
- Thêm `View > Channel settings...`: đổi tên, màu, ẩn/hiện kênh. Tên kênh được escape khi đưa vào nhãn HTML; metadata từ file được kiểm tra trước khi áp dụng.
- Session có dữ liệu và cấu hình riêng. Tab `+` tạo session mới; chuyển tab khôi phục dữ liệu và cấu hình đã lưu trong bộ nhớ. Chưa có thao tác đóng/xóa tab session.
- Bộ lọc bảng được áp dụng lại sau mỗi lần giải mã; bảng chỉ đọc để tránh sửa nhầm dữ liệu hiển thị.
- Mốc 0 thống nhất tại `trig_offset` cho cả triggered, free-run và timeout. Free-run/timeout được ghi là mốc tham chiếu, không khẳng định có cạnh trigger thật.
- Sửa nhãn trigger/cursor dùng `setFormat` để pyqtgraph không tự đổi lại nhãn cũ khi pan hoặc thay vị trí đường đo.
- Tách HUD con trỏ thành hàng riêng để không che thước thời gian; căn lại nhãn kênh theo kích thước PlotWidget sau khi layout resize; grid và chỉ báo zoom cập nhật theo vùng nhìn.
- Phần vẽ chỉ giữ các điểm chuyển mức và điểm đầu/cuối, giữ nguyên toàn bộ dữ liệu mẫu trong capture. Điều này giảm mạnh số điểm thừa trên tín hiệu có đoạn phẳng và tránh xuất SVG quá chậm trong kịch bản mẫu. Ẩn chữ packet khi zoom quá xa để giảm chồng chữ; các hình thể hiện khoảng packet vẫn còn.

### 2.4. Giải mã và dữ liệu mẫu

- UART/I2C/SPI nhận được NumPy array mà không gặp lỗi kiểm tra truth-value của array.
- Giới hạn chỉ số bắt đầu âm; xử lý dữ liệu rỗng và tần số không hợp lệ.
- UART bắt được cạnh ngay tại `start_idx`, đọc được frame sát cuối buffer khi còn điểm giữa stop bit hợp lệ, giải mã cả phần dữ liệu trước trigger.
- UART trả tâm từng bit và biên cuối frame 10 bit, để chấm bit và độ rộng ký tự trên GUI khớp cách lấy mẫu.
- SPI kiểm tra CS tại mẫu thực sự lấy dữ liệu; bổ sung kiểm tra cấu hình và bao phủ đủ 4 mode, MSB/LSB, CS thấp/cao trong test.
- Generator cũ làm tròn mỗi bit 8,68 mẫu thành 9 mẫu, tạo baud thực xấp xỉ 111.111 thay vì 115.200. Nay làm tròn các mốc thời gian tích lũy, rồi tạo lại `sample_data_1mhz.bin`.
- Fixture offline luôn mang tần số thật 1 MHz, kể cả khi lựa chọn capture của thiết bị thật đang ở mức khác. Mock TCP tạo tín hiệu theo tần số yêu cầu.

### 2.5. Lưu, mở và xuất dữ liệu

- Mở `.bin` dùng cùng parser kiểm tra như nhận serial; tệp lỗi không thay capture đang hiển thị. Vì raw `.bin` không lưu tần số, hộp mở file yêu cầu người dùng chọn tần số đã dùng khi thu.
- Thêm định dạng `.lacapture` (JSON version 1): khung nhị phân kèm tần số, cấu hình analyzer, tên/màu/trạng thái hiển thị kênh. Lưu bằng `Ctrl+Shift+S`; mở bằng `Ctrl+O`. Khung và metadata được kiểm tra trước khi nạp.
- CSV tăng độ chính xác cột thời gian và kiểm tra tần số/kích thước đầu vào.
- VCD tính `round(i * 1e9 / fs)` cho từng mốc; không nhân chỉ số với chu kỳ đã làm tròn. Ví dụ 600 mẫu ở 6 MHz ra 100.000 ns thay vì 100.200 ns. Giữ mốc kết thúc ngay cả khi tín hiệu không đổi; ghi tần số và offset vào comment. VCD bắt đầu ở thời gian không âm, còn CSV mặc định tương đối với trigger.
- SVG sử dụng exporter của pyqtgraph; PNG giữ cơ chế chụp plot. Đã thử xuất cả PNG và SVG với capture mẫu.

## 3. Danh mục file thay đổi

Các đường dẫn trong bảng tương đối với `software/`.

| File | Thay đổi |
|---|---|
| `protocol.py` | Mới: hằng giao thức, command/XOR, parser và đóng gói capture |
| `qt_bootstrap.py` | Mới: sửa đường dẫn plugin Unicode và font offscreen Windows |
| `main.py` | Gọi bootstrap trước QApplication |
| `gui/logic_client.py` | Bộ đọc stream, kiểm tra khung, khóa thao tác, Abort và offline |
| `gui/main_window.py` | Worker, khóa điều khiển, analyzer, channel settings, session, lưu/mở capture |
| `gui/waveform_widget.py` | Mốc thời gian, chấm bit, kênh động, bố cục HUD, grid, nén điểm vẽ |
| `gui/cursors.py` | Bổ sung import Tuple |
| `decoders/uart_decoder.py` | NumPy, biên dữ liệu và tâm bit/độ rộng frame |
| `decoders/i2c_decoder.py` | NumPy, kiểm tra tần số và chỉ số |
| `decoders/spi_decoder.py` | NumPy, mode, CS tại sample và chỉ số |
| `utils/exporter.py` | SVG, CSV chính xác hơn, VCD không trôi thời gian và giữ thời lượng |
| `ui/theme.py` | Hằng chiều cao HUD |
| `tests/generate_test_data.py` | Sinh tín hiệu theo thời gian tích lũy, hỗ trợ tần số/kênh |
| `tests/sample_data_1mhz.bin` | Tạo lại fixture đúng baud và giao thức |
| `tests/mock_device.py` | Mới: mock TCP loopback, hỗ trợ control, NAK và capture phân mảnh |
| `tests/mock_serial.py` | Launcher mock TCP đa nền tảng |
| `tests/test_gui_integration.py` | Test tích hợp TCP → parser → UART → GUI, chạy bằng pytest hoặc script |
| `tests/test_phase2_commercial.py` | Bootstrap Qt và điều chỉnh thông báo nghiệm thu offline |
| `tests/test_live_hardware_full.py` | CLI `--port`, `--output-dir`, đường xuất dùng được trên Windows |
| `tests/conftest.py` | Mới: Qt offscreen và fixture kiểm thử GUI |
| `tests/test_protocol_regressions.py` | Mới: parser/serial, khung lỗi/phân mảnh, khóa lệnh, Abort |
| `tests/test_decoders_regressions.py` | Mới: UART phân số, I2C repeated-start/NACK, 4 mode SPI |
| `tests/test_workflows_regressions.py` | Mới: thao tác GUI, file, session, time origin, export, resize |
| `requirements-dev.txt` | Mới: requirements và pytest cho kiểm thử |
| `RUN_APP.cmd` | Mới: mở app bằng môi trường .venv trên Windows |
| `BAO_CAO_KIEM_TRA_VA_HOAN_THIEN.md` | Báo cáo này |

## 4. Kiểm chứng đã thực hiện

Môi trường: Windows, Python 3.11.9 trong `software/.venv`; PyQt5 5.15.11 / Qt 5.15.2; pyqtgraph 0.14.0; NumPy 2.4.6; pyserial 3.5; pytest 9.2.0.

- **102 ca pytest đạt**; lượt chạy sau sửa căn hàng GUI: `102 passed in 16.69s`.
- 27 file Python qua kiểm tra cú pháp AST.
- `git diff --check` không báo lỗi; kiểm tra danh sách thay đổi xác nhận phạm vi `software/`.
- CLI `test_live_hardware_full.py --help` chạy được; chưa chạy HIL.
- Đã khởi tạo/chụp/xem ảnh GUI offscreen tại 1280×860; test resize thêm 1500×960 và 1080×600. Kiểm tra font, thước thời gian, HUD, 8 hàng kênh, trigger và bảng dữ liệu.
- Test dữ liệu lỗi, header giả, checksum sai, phân mảnh 1/2/7/64/512/4096 byte, status 00/01/02, NAK, thiếu dữ liệu và timeout.
- Test khóa lệnh khi nhận payload, Abort qua worker, đóng cửa sổ chờ worker, Start giả lập, Ping/Abort qua TCP.
- Test UART 500 kHz–6 MHz, I2C repeated-start/read/NACK và 16 tổ hợp SPI (4 mode × 2 bit order × 2 CS polarity).
- Test lưu/mở `.lacapture`, `.bin` hỏng, kênh giải mã tùy chọn, dữ liệu trước trigger, session, CSV/VCD/PNG/SVG và căn hàng sau resize.

## 5. Hướng dẫn chạy trên máy này

Mở thư mục `software` và nhấp đúp **`RUN_APP.cmd`**. Môi trường `.venv` đã được tạo trên máy hiện tại.

Hoặc chạy trong PowerShell từ `software/`:

```powershell
.\.venv\Scripts\python.exe app.py
```

Khi chuyển sang máy khác, tạo lại môi trường (không sao chép .venv):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

Luyện thử không cần kit: chọn `Offline Mock` trong danh sách cổng, hoặc đánh dấu checkbox Offline Mock, rồi Start. Fixture là UART 115200, 8N1, CH0, 1 MHz; văn bản mong đợi `TEST_LA_2026\r\n`.

Thử đường giao tiếp bằng mock TCP trong terminal riêng:

```powershell
.\.venv\Scripts\python.exe tests/mock_serial.py --port 8765
```

Trong GUI bỏ chọn checkbox Offline Mock, nhập `socket://127.0.0.1:8765` vào ô cổng, dùng Ping/Start. Mock chỉ bind loopback trên máy.

Chạy bộ test từ `software/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Khi có kit thật, người vận hành xác định đúng COM, cắm PA9 → PA0 theo tài liệu rồi chủ động chạy, ví dụ:

```powershell
.\.venv\Scripts\python.exe tests/test_live_hardware_full.py --port COM3
```

`COM3` chỉ là ví dụ, phải thay bằng cổng thực tế. Script HIL không được tự chạy trong bộ pytest.

## 6. Giới hạn và phần chưa kiểm chứng

**Chưa kiểm chứng trên phần cứng thật trong lần làm việc này.** Kết quả trên xác nhận phần mềm với dữ liệu tổng hợp, mock và GUI offscreen; không thay thế đo USB-CDC, timeout MCU, DMA, jitter/skew, hoặc độ chính xác tín hiệu điện trên STM32.

Mock TCP mô phỏng các luồng giao thức phục vụ kiểm thử; không mô phỏng đầy đủ thời gian thực, mọi race của USB hoặc toàn bộ FSM phần cứng. Header trong giao thức v1.0.0 không có checksum riêng; parser chỉ có thể kiểm tra các trường hằng và XOR payload theo hợp đồng hiện có.

Mỗi lần chỉ chọn một analyzer trên GUI. Session trong RAM mất khi đóng app nếu chưa lưu `.lacapture`. Raw `.bin` không chứa tần số nên người dùng phải cung cấp đúng. Giải mã UART ở tốc độ lấy mẫu thấp hơn 2 mẫu/bit sẽ báo thiếu độ phân giải; tín hiệu UART 115200 không thể được khôi phục đúng ở mọi mức tần số của thiết bị.

Các test đạt không phải chứng nhận thương mại hoặc xác nhận mọi thiết bị/driver đều tương thích. Khi tích hợp kit, cần chạy HIL trên đúng COM và bổ sung kết quả thực nghiệm vào báo cáo dự án.
