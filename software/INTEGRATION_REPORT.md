# Báo cáo tích hợp hai nhánh STM32 Logic Analyzer

Ngày kiểm tra: 09/11/2026. Repository: `hijoouzc/logic-analyzer-stm32f401ccu6`.

## 1. Git và phạm vi tích hợp

| Thành phần | Nhánh / commit |
| --- | --- |
| Nền A | `origin/sw/complete2_stm32_software` — `777539f2281e49090352adb4129689ec95f78ba6` |
| Nguồn B | `origin/sw/complete-stm32-software` — `8b9988512e4ea5b034c8669a80d2dd1fdc9a925a` |
| Tổ tiên chung | `a67aa395a912ad6cd71b2d1dac9e7303c14419c6` |
| Nhánh kết quả | `sw/integration-stm32`, dùng lại sau khi người dùng xác nhận |
| Cách tích hợp | `git merge --no-ff --no-commit origin/sw/complete-stm32-software` |

Fetch `origin` thành công. Hai đầu nhánh có 5 commit riêng ở A và 9 commit riêng ở B; nội dung đầu nhánh khác nhau ở 61 đường dẫn. Đây là hai phép so sánh khác nhau: số commit thể hiện lịch sử, số đường dẫn thể hiện khác biệt nội dung.

Các commit riêng của A, đã nằm trong HEAD nền:

- `5cd597d`: gom theme và GUI, bỏ kiến trúc UI trùng lặp.
- `0dfcac0`: củng cố firmware/capture, GUI và bộ test.
- `075ff87`: sửa căn tâm bit UART.
- `355bfd2`: căn bong bóng theo 8 data bit UART.
- `777539f`: tắt chấm mẫu phần cứng trên đường sóng số.

Các commit riêng của B được đưa vào quá trình merge, theo thứ tự lịch sử:

- `3df6d22`: phương pháp crop và so sánh thành phần UI.
- `5f62d75`: menu.
- `264c5e4`: thanh dưới.
- `ac30e80`: nhãn kênh.
- `041d219`: thước thời gian.
- `f3d2dee`: panel analyzer.
- `a13a8a5`: bảng dữ liệu và tìm kiếm.
- `2d32758`: waveform và báo cáo đánh giá UI.
- `8b99885`: phần mềm desktop, giao thức và test hồi quy.

**Chưa có merge commit.** HEAD vẫn tại A; MERGE_HEAD tại B. Nội dung đã được kết hợp để review; lịch sử hai cha chỉ chính thức được ghi khi người dùng cho phép tạo merge commit.

## 2. Nội dung được bảo toàn và kết hợp

### Giữ từ A

- Toàn bộ `firmware/` và `spec/` giữ nguyên nội dung so với A, bao gồm các sửa capture/USB đã có ở nhánh nền. Không chỉnh clock, DMA, NVIC, CubeMX, Drivers, Middlewares hoặc linker script.
- GUI dark theme, assets SVG, drawer, measurements, hotplug, thêm/đóng session bằng ID ổn định, phím tắt, điều hướng bảng hai chiều.
- `gui/measurements.py`: đo tần số, duty, độ rộng xung và tìm kênh hoạt động.
- Waveform: SingleBubble/MultiBubble, tooltip, Ctrl+Click chọn hàng, menu kênh, H/L, cursors và tắt dấu chấm mẫu phần cứng.
- UART: mẫu lấy tròn `bit_positions`, tâm bit phân số `bit_centers`, bong bóng ôm phần data từ 1 đến 9 chu kỳ bit.

### Giữ từ B

- `protocol.py`: tạo lệnh 5 byte, kiểm tra header/count/offset, XOR, parse/serialize capture dùng chung cho serial và file.
- `gui/logic_client.py`: lock serial, một worker sở hữu I/O, parser quét trượt, khung phân mảnh, phân biệt control/data, đối chiếu NAK echo, timeout, Abort có ACK và khóa lệnh khi nhận payload.
- `qt_bootstrap.py`, `main.py`, `RUN_APP.cmd`: cấu hình Qt và khởi chạy Windows.
- Lưu/mở `.lacapture` kèm tần số, analyzer, tên/màu/hiển thị kênh; mở `.bin` yêu cầu chọn tần số.
- Cấu hình UART channel/baudrate, I2C SCL/SDA và SPI channel/mode/order/polarity; giải mã cả dữ liệu trước trigger.
- `tests/mock_device.py`, `tests/mock_serial.py`: mock TCP loopback đa nền tảng.
- Các test protocol/decoder/workflow và script HIL chỉ chạy thủ công khi chỉ định cổng.
- `docs/COMPONENT_MATCH_REPORT.md`, 16 ảnh crop và công cụ `ui/compare_components.py`. Khôi phục ảnh tham chiếu đầy đủ vì báo cáo mới cần đường dẫn này.

### Kết hợp và sửa lỗi tích hợp

- `gui/main_window.py`: bố cục và measurements của A, lifecycle worker/storage/configuration của B. Ping tự động/hotplug cũng chạy qua worker. Đóng cửa sổ chờ worker kết thúc, không `terminate()`.
- `gui/waveform_widget.py`: giữ tương tác của A, thêm nén các đoạn phẳng, ẩn kênh có chiều cao bằng 0, màu riêng từng instance, escape tên kênh, analyzer ở kênh tùy chọn và redraw sau resize.
- Nén đường sóng giữ cả mẫu trước mỗi cạnh để bảo toàn hình học `stepMode='right'` của A; dữ liệu capture vẫn đầy đủ 32.768 mẫu.
- HUD có hàng riêng để không che timeline/dữ liệu; cột nhãn cộng cùng chiều cao HUD.
- Một gốc thời gian tham chiếu tại mẫu 6554 cho sóng, bảng và CSV ở cả ba status. Free-run/timeout được ghi rõ là mốc tham chiếu, không phải cạnh trigger thật.
- Lưu cấu hình theo ID session của A; đóng tab không nhầm dữ liệu theo index; Clear không làm dữ liệu cũ xuất hiện lại khi đổi tab.
- `decoders/uart_decoder.py`: giữ metadata hình học A, kết hợp đầu vào NumPy/rate hợp lệ và giới hạn cuối buffer của B; `stop_sample`/`stop_time_s` cùng mô tả hết 10 bit frame.
- `decoders/i2c_decoder.py`: giữ START/STOP có độ rộng để vẽ được từ A, kết hợp kiểm tra đầu vào/rate/range của B. SPI giữ sửa CS và hỗ trợ NumPy của B.
- `utils/exporter.py`: vector hóa VCD từ A, timestamp tính trực tiếp theo chỉ số mẫu và giữ mốc cuối từ B; CSV đủ độ phân giải và xuất SVG qua exporter pyqtgraph.
- `requirements-dev.txt` thêm Pillow cho công cụ so ảnh; dependencies chạy ứng dụng trong `requirements.txt` giữ nguyên.
- Các test cũ được chỉnh các kỳ vọng đã thay đổi: full-frame UART so với data bubble, gốc thời gian free-run, VCD có mốc cuối, nhãn trigger, session UI. PTY tách riêng để chỉ bỏ qua phần Unix khi chạy Windows; test serial TCP/FakeSerial vẫn giữ.
- `test_branch_integration.py` kiểm tra chéo giữa chức năng A/B. `verify_integration_stdlib.py` cung cấp kiểm tra độc lập khi chưa có dependencies.

## 3. Xung đột

Git báo đúng **10 file conflict** (cập nhật ban đầu đếm nhầm thành 11):

| File | Nguyên nhân | Giải quyết |
| --- | --- | --- |
| `decoders/uart_decoder.py` | Cùng sửa metadata frame | Kết hợp vị trí bit/data span A và full-frame boundary B; bỏ khóa dict trùng |
| `gui/logic_client.py` | Hai cách quản lý serial/cancel | Dùng owner lock/parser B thay cơ chế cờ A, giữ API tương thích và nhãn rate; đọc header buffered trước khi gửi Abort |
| `gui/main_window.py` | Hai kiến trúc GUI/lifecycle/session | Giữ GUI A, ghép worker/storage/config B và cấu hình theo ID session |
| `gui/waveform_widget.py` | Cùng sửa render/layout/timing | Kết hợp tương tác A với compression, visibility, cấu hình kênh và reference timing B |
| `tests/generate_test_data.py` | Hai generator khác nhau | Giữ API generator chung B; bảo toàn fractional phase của A, bỏ hàm cũ bị trùng/đoạn pack header lỗi |
| `tests/sample_data_1mhz.bin` | Binary khác nhau | Sinh lại theo generator đã hợp nhất; byte-identical với fixture B; kiểm tra header/LE/XOR/UART |
| `gui/cursors.py` | A xóa, B sửa | Adapter tới cursors/HUD đang có trong WaveformWidget, không tạo bộ cursor thứ hai |
| `ui/theme.py` | A xóa, B sửa | Re-export theme chuẩn từ `gui/theme.py`; không có hai bảng màu độc lập |
| `ui/proto.py` | A xóa prototype, B tiếp tục phát triển | Giữ lệnh preview cũ, render GUI tích hợp; không duy trì MainWindow giả lập trùng với ứng dụng |
| `utils/exporter.py` | Hai vòng xuất VCD | Vector hóa A + timestamp chính xác và mốc cuối B |

Không dùng lựa chọn toàn bộ ours/theirs cho merge. File auto-merge như decoder I2C/SPI, `main.py`, HIL và các test cũng đã được rà soát. Không còn vấn đề nghiệp vụ được xác định là buộc phải chọn một trong hai chức năng; các giới hạn kiểm chứng nằm ở mục 4.

## 4. Kiểm chứng và giới hạn

Đã chạy với Python 3.11.9 có sẵn:

```powershell
& 'C:/Users/Admin/AppData/Local/Programs/Python/Python311/python.exe' software/tests/verify_integration_stdlib.py
```

Kết quả: **7 nhóm test đạt**. Bao gồm cú pháp/import nội bộ/định nghĩa và khóa dict trùng, binary header/LE/XOR, 14 byte UART mong đợi, UART ở 500 kHz/1/2/3/6 MHz, cuối buffer/input lỗi, I2C repeated-start/read/NACK và 16 tổ hợp SPI (4 mode × 2 order × 2 polarity) cùng biên CS. Đây là kiểm thử decoder với đầu vào list; chưa kiểm tra thực thi đường NumPy.

Các kiểm tra bổ sung: không còn dấu conflict; `git diff --check` sạch; firmware/spec byte-identical với A. Không có build artifacts được thêm vào index.

Đã tìm Python MSYS2 3.14.4, Python 3.11.9 và bản Python 3.14.7 ở thư mục Downloads. Python 3.11 có pip nhưng tất cả đều thiếu PyQt5, pyqtgraph, NumPy, pyserial và pytest. Lệnh `python311 -m pytest software/tests -q` dừng trước collection với `No module named pytest`.

**Chưa chạy toàn bộ pytest, GUI offscreen, mock TCP end-to-end, serialize `.lacapture`, export CSV/VCD/PNG/SVG và kiểm tra ảnh sau tích hợp.** Các chức năng này đã có code/test kết hợp nhưng chưa thể xác nhận runtime. Không tự tạo/cài môi trường khi chưa nhận được trả lời cho đề nghị dùng `.venv`; không thay đổi Python toàn cục.

**Chưa build firmware, chưa đo SRAM bằng map file** (không thấy ARM toolchain trong PATH). Firmware không thay đổi so với A. Không chạy các script `firmware/tests/verify_step*.py` vì chúng cần kit/cổng serial thực.

**Chưa kiểm chứng trên phần cứng thật.** Chưa xác nhận USB-CDC thật, DMA, TIM1/TIM2, NVIC, trigger, loopback PA9→PA0 hoặc watchdog trên STM32F401.

## 5. Thay đổi cần nhóm chú ý khi review

- Free-run/timeout trước đây ở A bắt đầu trục tại mẫu 0; bản kết hợp dùng mẫu tham chiếu 6554 đồng nhất với CSV và B. Nhãn cho biết đây là reference.
- `stop_sample` UART nay là hết frame 10 bit; code cần data-only span dùng `data_start_sample`/`data_end_sample` được giữ từ A.
- `Ctrl+S` lưu capture; xuất ảnh chuyển sang `Ctrl+Shift+S` để hai chức năng không tranh phím tắt.
- Khởi động vẫn giữ màn hình trống mặc định của A; test/preview dùng `load_sample_on_start=True` rõ ràng.
- Các phần trăm UI trong báo cáo/crops của B là kết quả lịch sử, chưa đo lại cho GUI tích hợp. Preview `v1/v2/v3` hiện cùng render ứng dụng đang dùng, không tái tạo các bố cục prototype cũ. Mã lịch sử vẫn còn trong nhánh B.
- Module cursor cũ là adapter cho plot thuộc WaveformWidget; không tạo một bộ cursor độc lập trên PlotWidget bất kỳ.
- Bộ pytest đầy đủ cần chạy trước khi chấp nhận bản tích hợp là hoạt động thống nhất. Bảy nhóm stdlib không thay thế kiểm thử GUI/NumPy/serial.

## 6. An toàn và bước tiếp theo

- `main`, đầu nhánh nguồn A/B và HEAD nền được giữ nguyên; không rebase, squash, reset hard hoặc force push.
- Chưa commit, chưa push, chưa tạo/merge PR.
- Người dùng kiểm tra `git status`, `git diff --cached --stat` và `git diff --cached`.
- Nhánh tích hợp đang kế thừa upstream A từ trước; nếu push sau này phải chỉ định đích rõ ràng như dưới đây, tránh dùng lệnh thiếu tên nhánh.

Nếu được phép tạo môi trường riêng, từ thư mục gốc:

```powershell
& 'C:/Users/Admin/AppData/Local/Programs/Python/Python311/python.exe' -m venv software/.venv
& software/.venv/Scripts/python.exe -m pip install -r software/requirements-dev.txt
& software/.venv/Scripts/python.exe -m pytest software/tests -q
& software/.venv/Scripts/python.exe -m software.ui.proto v3 "$env:TEMP/la-integration-preview.png"
```

Sau khi test đạt và **người dùng xác nhận commit/push**, các lệnh dự kiến (chưa thực hiện):

```powershell
git commit -m "feat(software): integrate STM32 analyzer branches"
git push -u origin sw/integration-stm32
```

Sau đó người dùng có thể mở PR với base `main`, compare `sw/integration-stm32`, đính kèm báo cáo và kết quả test thực tế để nhóm review. Không tự merge PR.
