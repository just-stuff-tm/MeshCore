#include "SerialWake.h"
#include <Arduino.h>
#include <string.h>

#if defined(ESP32) && !(defined(ARDUINO_USB_CDC_ON_BOOT) && ARDUINO_USB_CDC_ON_BOOT)
  #define SERIAL_WAKE_UART 1   // Serial is UART0 (not native USB CDC)
#endif

#ifndef SERIAL_WAKE_HOLD_MS
  #define SERIAL_WAKE_HOLD_MS 15000   // stay awake this long after the last received byte
#endif
#ifndef SERIAL_WAKE_GRACE_MS
  #define SERIAL_WAKE_GRACE_MS 1000   // after a UART wakeup, wait this long for the real data
#endif
#ifndef SERIAL_WAKE_THRESHOLD
  #define SERIAL_WAKE_THRESHOLD 3     // RX edges needed to wake; one CR or LF is enough
#endif

#ifdef SERIAL_WAKE_UART
#include <Preferences.h>
#include <esp_sleep.h>
#include <driver/uart.h>
#include <driver/gpio.h>
#if __has_include(<soc/uart_channel.h>)
  #include <soc/uart_channel.h>
#endif
#if __has_include(<soc/uart_pins.h>)
  #include <soc/uart_pins.h>
#endif

static int8_t s_enabled = -1;              // -1 = not loaded from NVS yet
static bool s_inited = false;
static volatile uint32_t s_awake_until = 0;

static bool swEnabled() {
  if (s_enabled < 0) {
    Preferences p;
    s_enabled = 1;  // default on
    if (p.begin("serialwake", true)) { s_enabled = p.getUChar("off", 0) ? 0 : 1; p.end(); }
  }
  return s_enabled == 1;
}

static void swSave(bool on) {
  Preferences p;
  if (p.begin("serialwake", false)) { p.putUChar("off", on ? 0 : 1); p.end(); }
  s_enabled = on ? 1 : 0;
}

static void swOnRx() { s_awake_until = millis() + SERIAL_WAKE_HOLD_MS; }

static void swInit() {
  s_inited = true;
  Serial.onReceive(swOnRx);
  uart_set_wakeup_threshold(UART_NUM_0, SERIAL_WAKE_THRESHOLD);
#if defined(UART_NUM_0_RXD_DIRECT_GPIO_NUM)
  gpio_pullup_en((gpio_num_t)UART_NUM_0_RXD_DIRECT_GPIO_NUM);  // no floating RX = no false wakeups
#elif defined(U0RXD_GPIO_NUM)
  gpio_pullup_en((gpio_num_t)U0RXD_GPIO_NUM);
#endif
}
#endif

namespace SerialWake {

bool handleCommand(const char* command, char* reply) {
  if (strncmp(command, "set serial.ondemand ", 20) == 0) {
    const char* v = command + 20;
#ifdef SERIAL_WAKE_UART
    if (strncmp(v, "on", 2) == 0) { swSave(true); strcpy(reply, "OK - serial.ondemand on (UART wakes the board during powersaving)"); }
    else if (strncmp(v, "off", 3) == 0) { swSave(false); strcpy(reply, "OK - serial.ondemand off (stock powersaving)"); }
    else strcpy(reply, "Error: use on or off");
#else
    (void)v;
    strcpy(reply, "Error: not needed on this board (serial is always serviced)");
#endif
    return true;
  }
  if (strcmp(command, "get serial.ondemand") == 0) {
#ifdef SERIAL_WAKE_UART
    strcpy(reply, swEnabled() ? "> on" : "> off");
#else
    strcpy(reply, "> on (always)");
#endif
    return true;
  }
  return false;
}

bool beforeSleep() {
#ifdef SERIAL_WAKE_UART
  if (!swEnabled()) {
    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_UART);
    return false;
  }
  if (!s_inited) swInit();
  if (Serial.available() > 0 || (int32_t)(s_awake_until - millis()) > 0) return true;  // CLI in use
  Serial.flush();                    // let the last reply finish sending
  esp_sleep_enable_uart_wakeup(0);   // UART0 RX wakes the MCU
#endif
  return false;
}

void afterSleep() {
#ifdef SERIAL_WAKE_UART
  if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_UART) {
    uint32_t t = millis() + SERIAL_WAKE_GRACE_MS;
    if ((int32_t)(t - s_awake_until) > 0) s_awake_until = t;
  }
#endif
}

}  // namespace SerialWake
