/**
 * @file    main.cpp
 * @brief   ESP32 Test Pattern Generator cho STM32F401 Logic Analyzer.
 *          Phát đồng thời 4 loại tín hiệu trên 8 chân: UART, I2C, SPI, PWM.
 * @target  ESP32-WROOM-32 / ESP32 DevKit V1 (Mức logic 3.3V)
 */

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>

/* Ánh xạ chân GPIO ESP32 sang 8 kênh Logic Analyzer PA0..PA7 */
#define PIN_UART_TX   17  // -> Black Pill PA0 (CH0: UART RX)
#define PIN_I2C_SCL   22  // -> Black Pill PA1 (CH1: I2C SCL)
#define PIN_I2C_SDA   21  // -> Black Pill PA2 (CH2: I2C SDA)
#define PIN_SPI_SCK   18  // -> Black Pill PA3 (CH3: SPI SCK)
#define PIN_SPI_MOSI  23  // -> Black Pill PA4 (CH4: SPI MOSI)
#define PIN_SPI_MISO  19  // -> Black Pill PA5 (CH5: SPI MISO)
#define PIN_SPI_CS     5  // -> Black Pill PA6 (CH6: SPI CS - Trigger)
#define PIN_PWM_SQR   16  // -> Black Pill PA7 (CH7: Sóng vuông 500 kHz)

#define LED_BUILTIN_PIN 2 // LED báo trạng thái trên board ESP32

void setup() {
    /* 1. Serial Debug trên cổng USB */
    Serial.begin(115200);
    delay(200);
    Serial.println("\n==============================================");
    Serial.println("  ESP32 SIGNAL GENERATOR FOR LOGIC ANALYZER   ");
    Serial.println("==============================================");

    pinMode(LED_BUILTIN_PIN, OUTPUT);
    digitalWrite(LED_BUILTIN_PIN, HIGH);

    /* 2. CH0 (PA0): UART TX (115200 bps, 8-N-1) */
    Serial2.begin(115200, SERIAL_8N1, -1, PIN_UART_TX);
    Serial.println("-> [CH0] UART TX khởi tạo trên GPIO 17 (115200 bps)");

    /* 3. CH1, CH2 (PA1, PA2): I2C Master (100 kHz) */
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 100000);
    Serial.println("-> [CH1, CH2] I2C Master khởi tạo trên GPIO 22 (SCL), GPIO 21 (SDA) - 100 kHz");

    /* 4. CH3..CH6 (PA3..PA6): SPI Master (500 kHz, Mode 0) */
    pinMode(PIN_SPI_CS, OUTPUT);
    digitalWrite(PIN_SPI_CS, HIGH); // CS mặc định ở mức cao (Inactive)
    SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_SPI_CS);
    Serial.println("-> [CH3..CH6] SPI Master khởi tạo: SCK=18, MOSI=23, MISO=19, CS=5 (500 kHz, Mode 0)");

    /* 5. CH7 (PA7): Sóng vuông 500 kHz (Duty 50%) qua LEDC Hardware Timer */
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    ledcAttach(PIN_PWM_SQR, 500000, 4);
    ledcWrite(PIN_PWM_SQR, 8); // 8/16 = 50% duty
#else
    ledcSetup(0, 500000, 4);   // Kênh 0, tần số 500 kHz, độ phân giải 4-bit (0..15)
    ledcAttachPin(PIN_PWM_SQR, 0);
    ledcWrite(0, 8);           // 8/16 = 50% duty cycle
#endif
    Serial.println("-> [CH7] Sóng vuông 500 kHz khởi tạo trên GPIO 16 (Duty 50%)");

    Serial.println("-> Hệ thống đã sẵn sàng phát tín hiệu tuần hoàn mỗi 50 ms.\n");
}

void loop() {
    /* Đảo trạng thái LED báo hiệu mỗi nhịp phát */
    static bool led_state = false;
    led_state = !led_state;
    digitalWrite(LED_BUILTIN_PIN, led_state ? HIGH : LOW);

    /* --- 1. PHÁT GÓI UART TRÊN CH0 (PA0) --- */
    Serial2.print("ESP32_OK\r\n");

    /* Nghỉ ngắn giữa các chuẩn truyền thông */
    delayMicroseconds(100);

    /* --- 2. PHÁT GÓI I2C TRÊN CH1 (SCL), CH2 (SDA) --- */
    // Frame A: Ghi địa chỉ 0x3C (OLED) kèm 2 byte dữ liệu 0x00, 0xAF
    Wire.beginTransmission(0x3C);
    Wire.write(0x00); // Command byte
    Wire.write(0xAF); // Display ON
    Wire.endTransmission(true); // Gửi STOP

    delayMicroseconds(50);

    // Frame B: Repeated START ghi địa chỉ 0x68 (MPU6050) rồi đọc 1 byte
    Wire.beginTransmission(0x68);
    Wire.write(0x75); // Thanh ghi WHO_AM_I
    Wire.endTransmission(false); // Gửi Repeated START (không nhả bus)
    Wire.requestFrom((uint8_t)0x68, (uint8_t)1, (uint8_t)true); // Đọc 1 byte và STOP

    delayMicroseconds(100);

    /* --- 3. PHÁT GÓI SPI TRÊN CH3 (SCK), CH4 (MOSI), CH5 (MISO), CH6 (CS) --- */
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PIN_SPI_CS, LOW); // CS rơi xuống mức 0 (Kích hoạt Trigger cạnh xuống trên CH6)
    
    // Gửi 3 byte đặc trưng: 0x9F (Read ID), 0x55, 0xAA
    SPI.transfer(0x9F);
    SPI.transfer(0x55);
    SPI.transfer(0xAA);

    digitalWrite(PIN_SPI_CS, HIGH); // CS kéo lên mức 1 kết thúc frame
    SPI.endTransaction();

    /* Chu kỳ lặp lại: 50 ms (cho phép Auto-Repeat trên GUI bắt nhịp ổn định) */
    delay(50);
}
