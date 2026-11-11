/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    stm32f4xx_it.c
  * @brief   Interrupt Service Routines.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32f4xx_it.h"
/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "la_core.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN TD */

/* USER CODE END TD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/* External variables --------------------------------------------------------*/
extern PCD_HandleTypeDef hpcd_USB_OTG_FS;
extern DMA_HandleTypeDef hdma_tim1_up;
extern TIM_HandleTypeDef htim2;
/* USER CODE BEGIN EV */

/* USER CODE END EV */

/******************************************************************************/
/*           Cortex-M4 Processor Interruption and Exception Handlers          */
/******************************************************************************/
/**
  * @brief This function handles Non maskable interrupt.
  */
void NMI_Handler(void)
{
  /* USER CODE BEGIN NonMaskableInt_IRQn 0 */

  /* USER CODE END NonMaskableInt_IRQn 0 */
  /* USER CODE BEGIN NonMaskableInt_IRQn 1 */
   while (1)
  {
  }
  /* USER CODE END NonMaskableInt_IRQn 1 */
}

/**
  * @brief This function handles Hard fault interrupt.
  */
void HardFault_Handler(void)
{
  /* USER CODE BEGIN HardFault_IRQn 0 */

  /* USER CODE END HardFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_HardFault_IRQn 0 */
    /* USER CODE END W1_HardFault_IRQn 0 */
  }
}

/**
  * @brief This function handles Memory management fault.
  */
void MemManage_Handler(void)
{
  /* USER CODE BEGIN MemoryManagement_IRQn 0 */

  /* USER CODE END MemoryManagement_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_MemoryManagement_IRQn 0 */
    /* USER CODE END W1_MemoryManagement_IRQn 0 */
  }
}

/**
  * @brief This function handles Pre-fetch fault, memory access fault.
  */
void BusFault_Handler(void)
{
  /* USER CODE BEGIN BusFault_IRQn 0 */

  /* USER CODE END BusFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_BusFault_IRQn 0 */
    /* USER CODE END W1_BusFault_IRQn 0 */
  }
}

/**
  * @brief This function handles Undefined instruction or illegal state.
  */
void UsageFault_Handler(void)
{
  /* USER CODE BEGIN UsageFault_IRQn 0 */

  /* USER CODE END UsageFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_UsageFault_IRQn 0 */
    /* USER CODE END W1_UsageFault_IRQn 0 */
  }
}

/**
  * @brief This function handles System service call via SWI instruction.
  */
void SVC_Handler(void)
{
  /* USER CODE BEGIN SVCall_IRQn 0 */

  /* USER CODE END SVCall_IRQn 0 */
  /* USER CODE BEGIN SVCall_IRQn 1 */

  /* USER CODE END SVCall_IRQn 1 */
}

/**
  * @brief This function handles Debug monitor.
  */
void DebugMon_Handler(void)
{
  /* USER CODE BEGIN DebugMonitor_IRQn 0 */

  /* USER CODE END DebugMonitor_IRQn 0 */
  /* USER CODE BEGIN DebugMonitor_IRQn 1 */

  /* USER CODE END DebugMonitor_IRQn 1 */
}

/**
  * @brief This function handles Pendable request for system service.
  */
void PendSV_Handler(void)
{
  /* USER CODE BEGIN PendSV_IRQn 0 */

  /* USER CODE END PendSV_IRQn 0 */
  /* USER CODE BEGIN PendSV_IRQn 1 */

  /* USER CODE END PendSV_IRQn 1 */
}

/**
  * @brief This function handles System tick timer.
  */
void SysTick_Handler(void)
{
  /* USER CODE BEGIN SysTick_IRQn 0 */

  /* USER CODE END SysTick_IRQn 0 */
  HAL_IncTick();
  /* USER CODE BEGIN SysTick_IRQn 1 */
  la_core_on_systick_tick();
  /* USER CODE END SysTick_IRQn 1 */
}

/******************************************************************************/
/* STM32F4xx Peripheral Interrupt Handlers                                    */
/* Add here the Interrupt Handlers for the used peripherals.                  */
/* For the available peripheral interrupt handler names,                      */
/* please refer to the startup file (startup_stm32f4xx.s).                    */
/******************************************************************************/

/**
  * @brief This function handles TIM2 global interrupt.
  */
void TIM2_IRQHandler(void)
{
  /* USER CODE BEGIN TIM2_IRQn 0 */
  if (TIM2->SR & TIM_SR_UIF) {
    la_core_on_tim2_period_elapsed_isr();
  }
  /* USER CODE END TIM2_IRQn 0 */
  HAL_TIM_IRQHandler(&htim2);
  /* USER CODE BEGIN TIM2_IRQn 1 */

  /* USER CODE END TIM2_IRQn 1 */
}

/**
  * @brief This function handles USB On The Go FS global interrupt.
  */
void OTG_FS_IRQHandler(void)
{
  /* USER CODE BEGIN OTG_FS_IRQn 0 */

  /* USER CODE END OTG_FS_IRQn 0 */
  HAL_PCD_IRQHandler(&hpcd_USB_OTG_FS);
  /* USER CODE BEGIN OTG_FS_IRQn 1 */

  /* USER CODE END OTG_FS_IRQn 1 */
}

/**
  * @brief This function handles DMA2 stream5 global interrupt.
  */
void DMA2_Stream5_IRQHandler(void)
{
  /* USER CODE BEGIN DMA2_Stream5_IRQn 0 */
  if (DMA2->HISR & DMA_HISR_HTIF5) {
    la_core_on_dma_ht_isr();
  }
  /* USER CODE END DMA2_Stream5_IRQn 0 */
  HAL_DMA_IRQHandler(&hdma_tim1_up);
  /* USER CODE BEGIN DMA2_Stream5_IRQn 1 */

  /* USER CODE END DMA2_Stream5_IRQn 1 */
}

/* USER CODE BEGIN 1 */

/**
  * @brief Trình phục vụ ngắt EXTI Line 0 (PA0 - Logic Analyzer Channel 0)
  *        Nhiệm vụ 3: Inline trực tiếp lệnh kích hoạt TIM2 vào ISR để đưa trễ về mức tối thiểu.
  */
void EXTI0_IRQHandler(void)
{
  if (EXTI->PR & EXTI_PR_PR0) {
    TIM2->CR1 |= TIM_CR1_CEN;     /* Kích hoạt TIM2 ngay lập tức tiệm cận phần cứng */
    EXTI->IMR &= ~0x00FFU;        /* Khóa ngay ngắt EXTI 0..7 */
    EXTI->PR = EXTI_PR_PR0;       /* Xóa cờ ngắt EXTI0 */
    la_core_on_exti_trigger_isr(); /* Cập nhật trạng thái FSM */
  }
}

/**
  * @brief Trình phục vụ ngắt EXTI Line 1 (PA1 - Logic Analyzer Channel 1)
  */
void EXTI1_IRQHandler(void)
{
  if (EXTI->PR & EXTI_PR_PR1) {
    TIM2->CR1 |= TIM_CR1_CEN;
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = EXTI_PR_PR1;
    la_core_on_exti_trigger_isr();
  }
}

/**
  * @brief Trình phục vụ ngắt EXTI Line 2 (PA2 - Logic Analyzer Channel 2)
  */
void EXTI2_IRQHandler(void)
{
  if (EXTI->PR & EXTI_PR_PR2) {
    TIM2->CR1 |= TIM_CR1_CEN;
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = EXTI_PR_PR2;
    la_core_on_exti_trigger_isr();
  }
}

/**
  * @brief Trình phục vụ ngắt EXTI Line 3 (PA3 - Logic Analyzer Channel 3)
  */
void EXTI3_IRQHandler(void)
{
  if (EXTI->PR & EXTI_PR_PR3) {
    TIM2->CR1 |= TIM_CR1_CEN;
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = EXTI_PR_PR3;
    la_core_on_exti_trigger_isr();
  }
}

/**
  * @brief Trình phục vụ ngắt EXTI Line 4 (PA4 - Logic Analyzer Channel 4)
  */
void EXTI4_IRQHandler(void)
{
  if (EXTI->PR & EXTI_PR_PR4) {
    TIM2->CR1 |= TIM_CR1_CEN;
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = EXTI_PR_PR4;
    la_core_on_exti_trigger_isr();
  }
}

/**
  * @brief Trình phục vụ ngắt EXTI Lines 9..5 (PA5, PA6, PA7 - Logic Analyzer Channels 5, 6, 7)
  */
void EXTI9_5_IRQHandler(void)
{
  uint32_t pr = EXTI->PR & 0x00E0U; /* Lines 5, 6, 7 */
  if (pr != 0U) {
    TIM2->CR1 |= TIM_CR1_CEN;
    EXTI->IMR &= ~0x00FFU;
    EXTI->PR = pr;
    la_core_on_exti_trigger_isr();
  }
}

/* USER CODE END 1 */
