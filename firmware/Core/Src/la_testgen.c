/**
  ******************************************************************************
  * @file    la_testgen.c
  * @brief   Triển khai kênh phát tín hiệu mẫu tự kiểm tra trên chân PA9.
  * @author  Nguyen Van Hoi (Firmware Engineer)
  ******************************************************************************
  */

#include "la_testgen.h"
#include "la_core.h"
#include <string.h>

#if __has_include("main.h")
#include "main.h"
#endif

#if __has_include("usart.h")
#include "usart.h"
#endif

static const char *TEST_MESSAGE = "TEST_LA_2026\r\n";
static uint32_t g_last_tx_tick = 0;

extern uint32_t HAL_GetTick(void);
#if defined(HAL_UART_MODULE_ENABLED) || defined(USART1)
extern UART_HandleTypeDef huart1;
#endif

void la_testgen_init(void)
{
    g_last_tx_tick = 0;
}

void la_testgen_process(void)
{
    /* 
     * Chỉ phát xung test khi hệ thống ở IDLE hoặc WAIT_TRIGGER (cung cấp cạnh xung cho loopback sang PA0).
     * Tuyệt đối khóa trong ARMED, PRE_SAMPLING, POST_SAMPLING và TRANSFERRING để giải phóng CPU 1.3 ms và bảo toàn chế độ nghỉ __WFI().
     */
    la_state_t state = la_core_get_state();
    if (state != LA_STATE_IDLE && state != LA_STATE_WAIT_TRIGGER) {
        return;
    }

    uint32_t now = HAL_GetTick();
    /* Phát chuỗi test định kỳ mỗi 20 ms để đảm bảo khung 32ms luôn bắt trọn ít nhất 1 frame */
    if ((now - g_last_tx_tick) >= 20) {
        g_last_tx_tick = now;
#if defined(HAL_UART_MODULE_ENABLED) || defined(USART1)
        HAL_UART_Transmit(&huart1, (uint8_t*)TEST_MESSAGE, (uint16_t)strlen(TEST_MESSAGE), 10);
#endif
    }
}
