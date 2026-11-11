/**
  ******************************************************************************
  * @file    la_core.c
  * @brief   Triển khai bộ điều khiển lõi Logic Analyzer (FSM, Timer Cascade, DMA2, EXTI).
  * @author  Nguyen Van Hoi (Firmware Engineer)
  ******************************************************************************
  */

#include "la_core.h"
#include "la_protocol.h"

#if __has_include("main.h")
#include "main.h"
#endif

#if defined(HAL_TIM_MODULE_ENABLED) || defined(TIM1)
#if __has_include("tim.h")
#include "tim.h"
#endif
#if __has_include("dma.h")
#include "dma.h"
#endif
extern TIM_HandleTypeDef htim1;
extern TIM_HandleTypeDef htim2;
extern DMA_HandleTypeDef hdma_tim1_up;
#endif

/* Bộ đệm vòng 32 KB nằm trong SRAM STM32F401CCU6 (64 KB tổng, căn lề 4 byte) */
static uint8_t la_capture_buffer[LA_BUFFER_SIZE] __attribute__((aligned(4)));

/* Điều khiển LED trạng thái PC13 (Active Low trên WeAct Black Pill V3.0) */
static inline void la_set_led_active(bool active)
{
#if defined(LED_STATUS_GPIO_Port) && defined(LED_STATUS_Pin)
    HAL_GPIO_WritePin(LED_STATUS_GPIO_Port, LED_STATUS_Pin, active ? GPIO_PIN_RESET : GPIO_PIN_SET);
#else
    (void)active;
#endif
}

/* Biến trạng thái máy trạng thái FSM */
static volatile la_state_t g_la_state = LA_STATE_IDLE;
static volatile uint8_t  g_current_rate_idx = 0;
static volatile uint8_t  g_current_trig_cfg = 0;
static volatile uint16_t g_captured_write_pos = 0;
static volatile uint8_t  g_captured_status = LA_STATUS_FREERUN_OK;
static volatile uint32_t g_timeout_counter_ms = 0;
static volatile uint32_t g_timeout_limit_ms = 2000;

/* Bảng nạp ARR cho TIM1 (PSC = 0, Clock = 84 MHz) */
const uint16_t TIM1_ARR_TABLE[9] = {
    13,    /* Mức 0: 6 MHz */
    27,    /* Mức 1: 3 MHz */
    41,    /* Mức 2: 2 MHz */
    83,    /* Mức 3: 1 MHz */
    167,   /* Mức 4: 500 kHz */
    419,   /* Mức 5: 200 kHz */
    839,   /* Mức 6: 100 kHz */
    1679,  /* Mức 7: 50 kHz */
    8399   /* Mức 8: 10 kHz */
};

/* Bảng timeout động T = (16384 / fs) + 2000 ms */
static const uint32_t TIMEOUT_TABLE[9] = {
    2003,  /* Mức 0: 6 MHz */
    2006,  /* Mức 1: 3 MHz */
    2009,  /* Mức 2: 2 MHz */
    2017,  /* Mức 3: 1 MHz */
    2033,  /* Mức 4: 500 kHz */
    2082,  /* Mức 5: 200 kHz */
    2164,  /* Mức 6: 100 kHz */
    2328,  /* Mức 7: 50 kHz */
    3639   /* Mức 8: 10 kHz */
};

void la_core_init(void)
{
    g_la_state = LA_STATE_IDLE;
    g_captured_write_pos = 0;
    g_captured_status = LA_STATUS_FREERUN_OK;
    la_set_led_active(false);

#if defined(TIM1)
    /* 1. Cấu hình chu kỳ đếm Post-trigger cho TIM2 (đếm đúng 26.214 mẫu) */
    TIM2->ARR = LA_POST_TRIGGER_SAMPLES - 1; /* 26213 */

    /* Bật cờ ngắt Update cho TIM2 */
    __HAL_TIM_ENABLE_IT(&htim2, TIM_IT_UPDATE);

    /* 2. Xóa sạch cờ ngắt DMA2 Stream 5 */
    DMA2->HIFCR = DMA_HIFCR_CTCIF5 | DMA_HIFCR_CHTIF5 | DMA_HIFCR_CTEIF5 |
                  DMA_HIFCR_CDMEIF5 | DMA_HIFCR_CFEIF5;

    /* 3. Cấu hình SYSCFG định tuyến EXTI0..EXTI7 về GPIOA (0000 = PA[x]) */
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    SYSCFG->EXTICR[0] &= ~0xFFFFU; /* PA0, PA1, PA2, PA3 */
    SYSCFG->EXTICR[1] &= ~0xFFFFU; /* PA4, PA5, PA6, PA7 */

    /* 4. Cấu hình Pull-down nội cho PA0..PA7 để chống nhiễu chân thả nổi (Floating Inputs) */
    GPIOA->PUPDR &= ~0x0000FFFFU;
    GPIOA->PUPDR |=  0x0000AAAAU; /* 10 = Pull-down cho chân 0..7 */

    /* 5. Khóa toàn bộ ngắt EXTI và xóa cờ ngắt ban đầu */
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = 0x00FFU;

    /* 6. Cài đặt NVIC Priority 0 (Cao nhất - SSoT AGENTS.md) cho EXTI 0..7 */
    HAL_NVIC_SetPriority(EXTI0_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);

    HAL_NVIC_SetPriority(EXTI1_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI1_IRQn);

    HAL_NVIC_SetPriority(EXTI2_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI2_IRQn);

    HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI3_IRQn);

    HAL_NVIC_SetPriority(EXTI4_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI4_IRQn);

    HAL_NVIC_SetPriority(EXTI9_5_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);
#endif
}

la_state_t la_core_get_state(void)
{
    return g_la_state;
}

bool la_core_start_capture(uint8_t rate_idx, uint8_t trig_cfg)
{
    if (g_la_state != LA_STATE_IDLE) {
        return false; /* Đang bận */
    }

    if (rate_idx > 8) {
        return false; /* RATE_IDX không hợp lệ */
    }

    g_current_rate_idx = rate_idx;
    g_current_trig_cfg = trig_cfg;

    /* Thiết lập thời gian timeout động */
    g_timeout_counter_ms = 0;
    g_timeout_limit_ms = TIMEOUT_TABLE[rate_idx];

    g_la_state = LA_STATE_ARMED;

#if defined(TIM1)
    /* 1. Dừng an toàn các Timer và DMA nếu đang chạy (đợi bit EN về 0 theo RM0368 9.3.17) */
    TIM1->CR1 &= ~TIM_CR1_CEN;
    TIM2->CR1 &= ~TIM_CR1_CEN;
    DMA2_Stream5->CR &= ~DMA_SxCR_EN;
    while (DMA2_Stream5->CR & DMA_SxCR_EN) {
        /* Đợi giao dịch AHB cuối cùng hoàn tất */
    }

    /* 2. Cấu hình tần số lấy mẫu trên TIM1 và nạp ngay vào Shadow Register (vì ARPE=1) */
    TIM1->ARR = TIM1_ARR_TABLE[rate_idx];
    TIM1->CNT = 0;
    TIM1->EGR = TIM_EGR_UG;
    TIM1->SR  = 0;

    /* 3. Cấu hình chu kỳ đếm cho TIM2 One-Pulse tùy theo chế độ trigger */
    uint8_t mode = trig_cfg & 0x0F;
    if (mode == 0x00) {
        /* Free-run: đếm trọn 32.768 mẫu không ngắt trung gian */
        TIM2->ARR = LA_BUFFER_SIZE - 1; /* 32767 */
    } else {
        /* Edge Trigger: Phase 1 đếm đúng 6.554 mẫu pre-trigger (20%) */
        TIM2->ARR = LA_PRE_TRIGGER_SAMPLES - 1; /* 6553 */
    }
    TIM2->CNT = 0;
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR  = 0;
    TIM2->CR1 |= TIM_CR1_CEN; /* Bật TIM2 đếm ngay từ mẫu đầu tiên */

    /* 4. Khóa toàn bộ ngắt EXTI trong giai đoạn Pre-trigger (chống rỗng pre-trigger) */
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = 0x00FFU;

    /* 5. Xóa sạch cờ ngắt DMA2 Stream 5 và đưa handle về READY */
    DMA2->HIFCR = DMA_HIFCR_CTCIF5 | DMA_HIFCR_CHTIF5 | DMA_HIFCR_CTEIF5 |
                  DMA_HIFCR_CDMEIF5 | DMA_HIFCR_CFEIF5;
    hdma_tim1_up.State = HAL_DMA_STATE_READY;
    __HAL_UNLOCK(&hdma_tim1_up);

    /* 6. Khởi động DMA2 Stream 5 đọc trực tiếp từ GPIOA->IDR vào buffer 32KB vòng */
    if (HAL_DMA_Start_IT(&hdma_tim1_up, (uint32_t)&(GPIOA->IDR), (uint32_t)la_capture_buffer, LA_BUFFER_SIZE) != HAL_OK) {
        g_la_state = LA_STATE_IDLE;
        la_set_led_active(false);
        return false;
    }

    /* 7. Cho phép TIM1 phát yêu cầu DMA Update (bit UDE) */
    __HAL_TIM_ENABLE_DMA(&htim1, TIM_DMA_UPDATE);

    /* 8. Bật LED trạng thái, chuyển FSM sang PRE_SAMPLING và kích hoạt TIM1 lấy mẫu */
    la_set_led_active(true);
    g_la_state = LA_STATE_PRE_SAMPLING;
    __HAL_TIM_ENABLE(&htim1);
#else
    la_set_led_active(true);
    g_la_state = LA_STATE_PRE_SAMPLING;
#endif

    return true;
}

void la_core_abort(void)
{
    la_protocol_abort_stream();
#if defined(TIM1)
    /* Dừng khẩn cấp TIM1, TIM2, DMA2 */
    TIM1->CR1 &= ~TIM_CR1_CEN;
    TIM2->CR1 &= ~TIM_CR1_CEN;
    __DSB();
    DMA2_Stream5->CR &= ~DMA_SxCR_EN;
    while (DMA2_Stream5->CR & DMA_SxCR_EN) {
    }

    /* Khóa ngắt EXTI */
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = 0x00FFU;

    DMA2->HIFCR = DMA_HIFCR_CTCIF5 | DMA_HIFCR_CHTIF5 | DMA_HIFCR_CTEIF5 |
                  DMA_HIFCR_CDMEIF5 | DMA_HIFCR_CFEIF5;

    hdma_tim1_up.State = HAL_DMA_STATE_READY;
    __HAL_UNLOCK(&hdma_tim1_up);
#endif
    la_set_led_active(false);
    g_la_state = LA_STATE_IDLE;
}

/**
 * @brief  Chuyển FSM từ PRE_SAMPLING sang WAIT_TRIGGER hoặc kết thúc Free-run
 *         được gọi từ TIM2 ngắt Phase 1 (đủ 6.554 mẫu pre-trigger = 20%).
 */
static void la_core_arm_trigger(void)
{
    if (g_la_state != LA_STATE_PRE_SAMPLING) {
        return;
    }
    uint8_t mode = g_current_trig_cfg & 0x0F;
    if (mode == 0x00) {
        /* Free-run: Đã đếm trọn 32.768 mẫu -> Dừng ngay lập tức */
#if defined(TIM1)
        TIM1->CR1 &= ~TIM_CR1_CEN;
        __DSB(); /* Memory barrier: Xả sạch Write Buffer trên bus APB2 trước khi dừng DMA */

        DMA2_Stream5->CR &= ~DMA_SxCR_EN;
        while (DMA2_Stream5->CR & DMA_SxCR_EN) {
        }

        uint16_t ndtr = (uint16_t)(DMA2_Stream5->NDTR);
        g_captured_write_pos = (LA_BUFFER_SIZE - ndtr) % LA_BUFFER_SIZE;

        hdma_tim1_up.State = HAL_DMA_STATE_READY;
        __HAL_UNLOCK(&hdma_tim1_up);
#else
        g_captured_write_pos = 0;
#endif
        g_captured_status = LA_STATUS_FREERUN_OK;
        g_la_state = LA_STATE_TRANSFERRING;
    } else {
        /* Chế độ Edge Trigger: Phase 1 kết thúc -> Cấu hình TIM2 Phase 2 (26.214 mẫu) và mở ngắt EXTI */
#if defined(TIM2)
        TIM2->CR1 &= ~TIM_CR1_CEN; /* Đảm bảo TIM2 dừng, chờ EXTI kích hoạt */
        TIM2->ARR = LA_POST_TRIGGER_SAMPLES - 1; /* 26213 */
        TIM2->CNT = 0;
        TIM2->SR = 0;
#endif
        uint8_t ch = (g_current_trig_cfg >> 4) & 0x07; /* Kênh 0..7 */

        if (mode == 0x01) {
            /* Cạnh lên (Rising Edge) */
            EXTI->RTSR |= (1U << ch);
            EXTI->FTSR &= ~(1U << ch);
        } else if (mode == 0x02) {
            /* Cạnh xuống (Falling Edge) */
            EXTI->FTSR |= (1U << ch);
            EXTI->RTSR &= ~(1U << ch);
        }

        /* Bắt đầu đếm timeout SysTick và cập nhật trạng thái TRƯỚC KHI mở ngắt EXTI */
        g_timeout_counter_ms = 0;
        g_la_state = LA_STATE_WAIT_TRIGGER;
        __DSB(); /* Memory barrier: Bảo đảm state được ghi xuống SRAM trước khi unmask ngắt */

        /* Xóa cờ ngắt cũ và mở ngắt EXTI trên kênh chỉ định */
        EXTI->PR = (1U << ch);
        EXTI->IMR |= (1U << ch);
    }
}

void la_core_on_dma_ht_isr(void)
{
    /* TIM2 Hardware Counter 2-Pha đã tự động hoàn thành Pre-trigger tại mẫu 6.554 (20%).
     * Hàm này giữ lại để tương thích ngắt DMA2 Stream 5 HTIF5 (fallback an toàn). */
    if (g_la_state == LA_STATE_PRE_SAMPLING) {
        la_core_arm_trigger();
    }
}

void la_core_on_exti_trigger_isr(void)
{
    if (g_la_state == LA_STATE_WAIT_TRIGGER) {
        /* Khóa ngay lập tức ngắt EXTI và kích hoạt TIM2 One-Pulse */
        EXTI->IMR &= ~0x00FFU;
#if defined(TIM2)
        TIM2->CR1 |= TIM_CR1_CEN;
#endif
        /* Đánh dấu bắt được trigger thành công */
        g_captured_status = LA_STATUS_TRIGGER_OK; /* 0x00 */
        g_la_state = LA_STATE_POST_SAMPLING;
    }
}

void la_core_on_tim2_period_elapsed_isr(void)
{
    if (g_la_state == LA_STATE_PRE_SAMPLING) {
        /* Phase 1 kết thúc (đủ 6.554 mẫu pre-trigger = 20% hoặc 32.768 mẫu Free-run) */
        la_core_arm_trigger();
    } else if (g_la_state == LA_STATE_POST_SAMPLING) {
#if defined(TIM1)
        /* Dừng TIM1 ngay lập tức */
        TIM1->CR1 &= ~TIM_CR1_CEN;
        __DSB(); /* Memory barrier: Xả sạch Write Buffer trên bus APB2 trước khi dừng DMA */

        /* Dừng DMA2 Stream 5 và đợi thanh ghi NDTR ổn định */
        DMA2_Stream5->CR &= ~DMA_SxCR_EN;
        while (DMA2_Stream5->CR & DMA_SxCR_EN) {
        }

        /* Lưu vị trí con trỏ ghi DMA hiện tại (vị trí mẫu cũ nhất t0) */
        uint16_t ndtr = (uint16_t)(DMA2_Stream5->NDTR);
        g_captured_write_pos = (LA_BUFFER_SIZE - ndtr) % LA_BUFFER_SIZE;

        /* Đưa handle DMA về trạng thái READY */
        hdma_tim1_up.State = HAL_DMA_STATE_READY;
        __HAL_UNLOCK(&hdma_tim1_up);
#else
        g_captured_write_pos = 0;
#endif
        uint8_t mode = g_current_trig_cfg & 0x0F;
        g_captured_status = (mode == 0x00) ? LA_STATUS_FREERUN_OK : LA_STATUS_TRIGGER_OK;
        g_la_state = LA_STATE_TRANSFERRING;
    }
}

void la_core_on_systick_tick(void)
{
    if (g_la_state == LA_STATE_WAIT_TRIGGER) {
        g_timeout_counter_ms++;
        if (g_timeout_counter_ms >= g_timeout_limit_ms) {
            /* Hết thời gian chờ trigger -> Tự động dừng theo quy tắc Timeout */
            EXTI->IMR &= ~0x00FFU;

#if defined(TIM1)
            TIM1->CR1 &= ~TIM_CR1_CEN;
            TIM2->CR1 &= ~TIM_CR1_CEN;
            __DSB();
            DMA2_Stream5->CR &= ~DMA_SxCR_EN;
            while (DMA2_Stream5->CR & DMA_SxCR_EN) {
            }

            uint16_t ndtr = (uint16_t)(DMA2_Stream5->NDTR);
            g_captured_write_pos = (LA_BUFFER_SIZE - ndtr) % LA_BUFFER_SIZE;

            hdma_tim1_up.State = HAL_DMA_STATE_READY;
            __HAL_UNLOCK(&hdma_tim1_up);
#else
            g_captured_write_pos = 0;
#endif
            g_captured_status = LA_STATUS_TIMEOUT; /* 0x02 */
            g_la_state = LA_STATE_TRANSFERRING;
        }
    }
}

void la_core_process(void)
{
    /* Trong PRE_SAMPLING: TIM2 cascade phần cứng tự động đếm 6.554 mẫu,
       CPU ngủ __WFI() hoàn toàn trong main loop mà không cần polling NDTR. */
    if (g_la_state == LA_STATE_TRANSFERRING) {
        if (!la_protocol_is_streaming()) {
            la_protocol_start_data_stream(g_captured_status, LA_TRIG_OFFSET_DEFAULT, la_capture_buffer, g_captured_write_pos);
        } else {
            if (la_protocol_process_stream()) {
                la_set_led_active(false);
                g_la_state = LA_STATE_IDLE;
            }
        }
    }
}
