**BÁO CÁO THÔNG SỐ MÔ PHỎNG
MẠCH BẢO VỆ ĐẦU VÀO LOGIC ANALYZER**

*Bốn kịch bản kiểm chứng trên một kênh*

|  |  |
| --- | --- |
| **Thông tin** | **Giá trị** |
| Đối tượng mô phỏng | Một kênh đầu vào của Logic Analyzer |
| Phần mềm | LTspice |
| Nguồn tín hiệu đầu vào | V1 |
| Điện trở nối tiếp | R1 = 1 kΩ |
| Diode bảo vệ | Hai diode BAT54S (U1, U2) theo sơ đồ đang mô phỏng |
| Tụ tại nút bảo vệ | C1 = 22 pF |
| Nguồn tham chiếu/kẹp | V2 = 3,3 V; mạch Zener D1 và tụ C2 = 10 µF theo sơ đồ |
| Nút quan sát | Vin (đầu vào), N\_PROTECT (sau mạng bảo vệ), Vout (đầu ra logic mô hình) |
| Mô hình Vout | B1: V = if(V(N\_PROTECT) > 1.65, 3.3, 0) |

# 1. Mục đích mô phỏng

Mô phỏng nhằm đánh giá khả năng tiếp nhận và xử lý tín hiệu của một kênh bảo vệ đầu vào. Các dạng sóng tại Vin, N\_PROTECT và Vout được quan sát để kiểm tra mức điện áp, khả năng kẹp quá áp, độ trễ/sườn chuyển mức và khả năng duy trì dạng xung ở các tần số khác nhau.

Trong giai đoạn này, mô phỏng được thực hiện trên một kênh. Sau khi xác nhận cấu hình và kết quả của một kênh, có thể nhân bản cùng cấu trúc cho 8 kênh để kiểm tra tính đồng nhất. Khi kiểm tra 8 kênh, mỗi kênh cần có nguồn tín hiệu, điện trở, diode, tụ và tên nút riêng; nguồn 3,3 V và GND có thể dùng chung theo cấu trúc nguồn chung.

# 2. Cấu hình mạch mô phỏng một kênh

Cấu trúc mô phỏng đang sử dụng: nguồn Vin → điện trở nối tiếp R1 → nút N\_PROTECT. Nút N\_PROTECT được nối với mạng diode BAT54S và tụ C1 xuống GND. Đầu ra Vout được tạo bởi nguồn hành vi B1 để biểu diễn ngưỡng logic 1,65 V: nếu N\_PROTECT lớn hơn 1,65 V thì Vout bằng 3,3 V; ngược lại Vout bằng 0 V.

Lưu ý: B1 là mô hình chuyển mức logic phục vụ quan sát trong LTspice, không phải linh kiện đệm vật lý. Khi hoàn thiện thiết kế phần cứng, cần thay/đối chiếu với đặc tính đầu vào thực tế của IC đệm 74LVC245 và tải đầu vào của STM32. ![](data:image/png;base64...)

# 3. Thông số bốn kịch bản kiểm thử

Các giá trị dưới đây được tổng hợp theo bốn kịch bản đã sử dụng trong quá trình mô phỏng và các ảnh mạch/dạng sóng đã cung cấp. Với các nguồn PULSE, cú pháp LTspice có dạng: PULSE(Vinitial Von Tdelay Trise Tfall Ton Tperiod).

## 3.1. Kịch bản 1 – Quá áp DC +20 V

|  |  |
| --- | --- |
| **Thông số** | **Giá trị/cấu hình** |
| Dạng tín hiệu Vin | Nguồn DC = +20 V |
| Thời gian mô phỏng | .tran 0 5m 0 1u |
| R1 | 1 kΩ |
| C1 | 22 pF |
| Điện áp cần quan sát | Vin, N\_PROTECT, Vout |
| Mục tiêu | Kiểm tra khả năng hạn dòng qua R1 và kẹp điện áp tại nút N\_PROTECT khi đầu vào bị quá áp dương. |
| Kết quả cần xác nhận | N\_PROTECT không vượt giới hạn an toàn của tầng logic; Vout không được xuất hiện mức điện áp nguy hiểm. |

Nhận xét khi đọc đồ thị: Vin phải giữ ở +20 V trong suốt thời gian mô phỏng. N\_PROTECT phải được giới hạn bởi mạng bảo vệ. Vout là tín hiệu logic mô hình hóa; không dùng riêng Vout để kết luận diode hoặc rail 3,3 V đã an toàn. ![](data:image/png;base64...)

## 3.2. Kịch bản 2 – Xung quá áp ±30 V, độ rộng 1 ms

|  |  |
| --- | --- |
| **Thông số** | **Giá trị/cấu hình** |
| Dạng tín hiệu Vin | Xung quá áp âm −30 V, độ rộng 1 ms; kiểm tra cả cực tính dương +30 V trong lượt mô phỏng tương ứng nếu yêu cầu là ±30 V. |
| Cấu hình PULSE minh họa trong ảnh | PULSE(0 -30 1m 1u 1u 1m 3m) |
| Thời gian mô phỏng | .tran 0 5m 0 1u |
| R1 | 1 kΩ |
| C1 | 22 pF |
| Mục tiêu | Kiểm tra khả năng kẹp xung quá áp có biên độ lớn và thời gian tồn tại 1 ms. |
| Kết quả cần xác nhận | N\_PROTECT không bị kéo xuống mức gây hư hỏng tầng logic; kiểm tra dòng qua diode và công suất xung trên R1. |

Lưu ý quan trọng: Cấu hình PULSE(0 -30 1m 1u 1u 1m 3m) trong ảnh thể hiện xung âm −30 V. Để chứng minh khả năng bảo vệ hai cực ±30 V, cần chạy thêm một lượt với xung dương +30 V hoặc dùng nguồn xung hai cực có dạng sóng được xác định rõ. Không nên ghi nhận một lượt xung âm là đã kiểm chứng đầy đủ cả hai cực tính.

+30![](data:image/png;base64...)

-30

![](data:image/png;base64...)

## 3.3. Kịch bản 3 – Sóng vuông 10 kHz

|  |  |
| --- | --- |
| **Thông số** | **Giá trị/cấu hình** |
| Dạng tín hiệu Vin | Sóng vuông 0–3,3 V |
| Tần số | 10 kHz |
| Chu kỳ | 100 µs |
| Ton / Toff | 50 µs / 50 µs (duty cycle 50%) |
| PULSE | PULSE(0 3.3 0 10n 10n 50u 100u) |
| Thời gian mô phỏng | .tran 0 500u 0 10n |
| R1 / C1 | 1 kΩ / 22 pF |
| Mục tiêu | Kiểm tra khả năng truyền dạng sóng vuông qua mạng bảo vệ ở tần số 10 kHz. |
| Kết quả cần xác nhận | Vout giữ đúng hai mức logic; N\_PROTECT có sườn lên/xuống đủ nhanh, không bị suy giảm hoặc méo đáng kể. |

![](data:image/png;base64...)

## 3.4. Kịch bản 4 – Sóng vuông 1 MHz

|  |  |
| --- | --- |
| **Thông số** | **Giá trị/cấu hình** |
| Dạng tín hiệu Vin | Sóng vuông 0–3,3 V |
| Tần số | 1 MHz |
| Chu kỳ | 1 µs |
| Ton / Toff | 500 ns / 500 ns (duty cycle 50%) |
| PULSE | PULSE(0 3.3 0 5n 5n 500n 1u) |
| Thời gian mô phỏng | .tran 0 5u 0 5n |
| R1 / C1 | 1 kΩ / 22 pF |
| Mục tiêu | Kiểm tra khả năng bảo toàn xung ở tần số cao nhất trong bốn kịch bản. |
| Kết quả cần xác nhận | Vout vẫn nhận đủ các chu kỳ 1 MHz; không mất xung, không sai mức logic và độ trễ/sườn không vượt giới hạn thiết kế. |

![](data:image/png;base64...)

# 4. Tiêu chí đánh giá Vin → N\_PROTECT → Vout

|  |  |
| --- | --- |
| **Tiêu chí** | **Cách đánh giá** |
| Mức điện áp | So sánh điện áp cực đại/cực tiểu tại N\_PROTECT với giới hạn cho phép của IC đệm và STM32. |
| Bảo toàn logic | Với tín hiệu hợp lệ 0–3,3 V, Vout phải tái tạo đúng trạng thái thấp/cao theo ngưỡng logic. |
| Độ méo dạng sóng | So sánh hình dạng, độ rộng xung, sườn lên/xuống của Vin và N\_PROTECT; không chỉ so sánh hai đường có cùng mức đỉnh. |
| Độ trễ | Đo thời gian từ cạnh Vin đến khi N\_PROTECT/Vout vượt ngưỡng logic. |
| Mất xung / sai chu kỳ | Ở 1 MHz, xác nhận tất cả chu kỳ đầu vào đều xuất hiện ở đầu ra, chu kỳ đầu ra vẫn xấp xỉ 1 µs. |
| Dòng và công suất linh kiện | Đo dòng qua R1/diode và công suất tức thời, năng lượng xung; đối chiếu giới hạn datasheet. |
| Ảnh hưởng nguồn 3,3 V | Theo dõi rail 3,3 V khi có quá áp; bảo đảm rail không bị nâng vượt giới hạn do dòng kẹp dồn vào nguồn. |

# 5. Cách đo và trình bày kết quả

1. Trên đồ thị LTspice, lần lượt chọn và hiển thị ba nút: Vin, N\_PROTECT và Vout.
2. Với kịch bản quá áp, đặt thang thời gian đủ dài để quan sát toàn bộ thời điểm xuất hiện và kết thúc xung.
3. Với kịch bản 10 kHz, quan sát ít nhất vài chu kỳ; với 1 MHz, nên phóng to vùng 1–3 chu kỳ để đo sườn và độ trễ.
4. Dùng cursors của LTspice để đo điện áp cực đại/cực tiểu, thời gian lên/xuống và độ trễ giữa các cạnh.
5. Lưu riêng file .asc và ảnh dạng sóng cho từng kịch bản; đặt tên rõ ràng, ví dụ: Test1\_Overvoltage20V, Test2\_Pulse30V, Test3\_10kHz, Test4\_1MHz.

# 6. Lưu ý kỹ thuật trước khi kết luận

* Các kết quả trên chỉ xác nhận mạch theo mô hình linh kiện đang khai báo trong LTspice. Cần dùng đúng model SPICE/datasheet của BAT54S và Zener/TVS thực tế.
* Mô hình B1 với ngưỡng 1,65 V tạo ra đầu ra logic lý tưởng, không mô phỏng đầy đủ độ trễ, dòng vào, điện dung và giới hạn điện áp của 74LVC245.
* Ở kịch bản quá áp, cần theo dõi thêm dòng qua diode, công suất trên R1, điện áp rail 3,3 V và dòng mà nguồn 3,3 V phải hấp thụ. Chỉ nhìn thấy N\_PROTECT được kẹp không đủ chứng minh toàn bộ mạch an toàn.
* Thông số xung ±30 V cần được kiểm chứng riêng cho cả cực dương và cực âm. Ảnh cấu hình xung âm không đại diện cho phép thử xung dương.
* Sau khi kiểm chứng một kênh, nhân bản thành 8 nhánh độc lập. Để kiểm tra đồng thời 8 kênh, có thể cấp cùng dạng sóng cho cả 8 đầu vào và so sánh các nút N\_PROTECT1…N\_PROTECT8, Vout1…Vout8. Nguồn 3,3 V/GND dùng chung, nhưng không nối chung các nút tín hiệu giữa các kênh.

# 7. Bảng tổng hợp nhanh

|  |  |  |  |
| --- | --- | --- | --- |
| **Kịch bản** | **Vin** | **Thời gian mô phỏng** | **Thông số chính cần xem** |
| 1. Quá áp DC | +20 V DC | 5 ms; max step 1 µs | N\_PROTECT, dòng diode, dòng/công suất R1, rail 3,3 V |
| 2. Xung quá áp | ±30 V; 1 ms | 5 ms; max step 1 µs | Điện áp kẹp, dòng xung, năng lượng xung, cả hai cực tính |
| 3. Sóng vuông | 0–3,3 V; 10 kHz | 500 µs; max step 10 ns | Độ rộng xung, sườn lên/xuống, trễ |
| 4. Sóng vuông | 0–3,3 V; 1 MHz | 5 µs; max step 5 ns | Bảo toàn chu kỳ, mất xung, méo và trễ |

**Kết luận:** Bốn kịch bản trên tạo thành bộ kiểm thử ban đầu cho một kênh bảo vệ. Chỉ kết luận mạch đạt yêu cầu sau khi đã lưu dạng sóng và đo được các thông số định lượng tại Vin, N\_PROTECT, Vout, dòng qua linh kiện và rail nguồn. Việc lặp lại cùng phép thử trên 8 kênh là bước tiếp theo để xác nhận tính đồng nhất và ảnh hưởng khi nhiều kênh hoạt động đồng thời.