/**
  ******************************************************************************
  * @file    la_core.h
  * @brief   Bộ điều khiển lõi Logic Analyzer (FSM, Timer Cascade, DMA2).
  * @author  Nguyen Van Hoi (Firmware Engineer)
  ******************************************************************************
  */

#ifndef INC_LA_CORE_H_
#define INC_LA_CORE_H_

#include <stdint.h>
#include <stdbool.h>

#define LA_BUFFER_SIZE         (32768U)      /* 32 KB SRAM bộ đệm vòng */
#define LA_PRE_TRIGGER_SAMPLES (6554U)       /* 20% Pre-trigger */
#define LA_POST_TRIGGER_SAMPLES (26214U)     /* 80% Post-trigger */
#define LA_TRIG_OFFSET_DEFAULT (6554U)

/* Máy trạng thái FSM lõi của Logic Analyzer */
typedef enum {
    LA_STATE_IDLE = 0,
    LA_STATE_ARMED,
    LA_STATE_PRE_SAMPLING,     /* Đang nạp 20% Pre-trigger (chờ cờ Half-Transfer) */
    LA_STATE_WAIT_TRIGGER,    /* Đã unmask EXTI, đang đợi cạnh xung */
    LA_STATE_POST_SAMPLING,    /* TIM2 One-pulse đang đếm 26.214 mẫu */
    LA_STATE_TRANSFERRING      /* Đang đẩy dữ liệu 32KB qua USB-CDC (khóa nhận lệnh) */
} la_state_t;

/* Khởi tạo hệ thống Logic Analyzer */
void la_core_init(void);

/* Vòng lặp xử lý State Machine (gọi trong while(1) của main.c) */
void la_core_process(void);

/* Bắt đầu chu trình Capture từ lệnh PC */
bool la_core_start_capture(uint8_t rate_idx, uint8_t trig_cfg);

/* Hủy khẩn cấp chu trình Capture */
void la_core_abort(void);

/* Callback gọi từ ngắt DMA Half-Transfer (HTIF5) */
void la_core_on_dma_ht_isr(void);

/* Callback gọi từ ngắt EXTI Trigger */
void la_core_on_exti_trigger_isr(void);

/* Callback gọi từ ngắt tràn TIM2 (đủ 26.214 mẫu) */
void la_core_on_tim2_period_elapsed_isr(void);

/* Callback gọi từ ngắt SysTick (quản lý Timeout động) */
void la_core_on_systick_tick(void);

/* Lấy trạng thái hiện tại của FSM */
la_state_t la_core_get_state(void);

/* Lấy chế độ trigger hiện tại (0x00 = Free-run, 0x01 = Rising, 0x02 = Falling) */
uint8_t la_core_get_trig_mode(void);

#endif /* INC_LA_CORE_H_ */
