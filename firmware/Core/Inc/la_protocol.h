/**
  ******************************************************************************
  * @file    la_protocol.h
  * @brief   Xử lý khung truyền nhị phân và mã hóa gói tin USB-CDC.
  * @author  Nguyen Van Hoi (Firmware Engineer)
  ******************************************************************************
  */

#ifndef INC_LA_PROTOCOL_H_
#define INC_LA_PROTOCOL_H_

#include <stdint.h>
#include <stdbool.h>

/* Mã Status phản hồi Data Frame */
#define LA_STATUS_TRIGGER_OK   (0x00U)
#define LA_STATUS_FREERUN_OK   (0x01U)
#define LA_STATUS_TIMEOUT      (0x02U)

/* Mã RSP_CODE phản hồi Control Frame (7 Bytes) */
#define LA_RSP_PONG            (0x04U)
#define LA_RSP_ABORTED         (0x05U)
#define LA_ERR_CHECKSUM        (0xE0U)
#define LA_ERR_INVALID_RATE    (0xE1U)
#define LA_ERR_INVALID_TRIG    (0xE2U)
#define LA_ERR_BUSY            (0xE3U)

/* Khởi tạo giao thức và cấu hình TxFIFO USB OTG_FS (320 words chuẩn RM0368) */
void la_protocol_init(void);

/* Nhận và đẩy dòng byte từ USB CDC vào Ring Buffer (gọi trong CDC_Receive_FS - ISR context) */
void la_protocol_process_rx_bytes(const uint8_t *data, uint32_t len);

/* Quét Ring Buffer và thực thi lệnh nhận từ PC trong Thread Mode (gọi trong while(1)) */
void la_protocol_process(void);

/* Gửi khung phản hồi điều khiển 7 Bytes (PONG, ABORT ACK, NAK) */
void la_protocol_send_control_frame(uint8_t rsp_code, uint8_t d1, uint8_t d2, uint8_t d3);

/* Gửi khung phản hồi dữ liệu 32.776 Bytes kèm xoay vòng bộ đệm (Buffer Unrolling) */
void la_protocol_send_data_frame(uint8_t status, uint16_t trig_offset, const uint8_t *payload, uint16_t write_pos);

/* Non-blocking USB Streaming Engine (Nhiệm vụ 4) */
void la_protocol_start_data_stream(uint8_t status, uint16_t trig_offset, const uint8_t *payload, uint16_t write_pos);
bool la_protocol_process_stream(void);
bool la_protocol_is_streaming(void);
void la_protocol_abort_stream(void);

/* Tối ưu hóa tính Checksum XOR 32-bit unrolled (Nhiệm vụ 1) */
uint8_t la_protocol_fast_xor_checksum(const uint8_t *payload, uint32_t len);

#endif /* INC_LA_PROTOCOL_H_ */
