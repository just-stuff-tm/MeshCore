// Headless Heltec V3 (no OLED): hold the SSD1306 in reset from boot so it draws nothing.
// initVariant() is the Arduino-ESP32 hook that runs before setup().
#include <Arduino.h>

#if defined(HEADLESS_OLED_OFF)
#ifndef PIN_OLED_RESET
  #define PIN_OLED_RESET 21
#endif
void initVariant() {
  pinMode(PIN_OLED_RESET, OUTPUT);
  digitalWrite(PIN_OLED_RESET, LOW);   // SSD1306 in reset: display and charge pump off
  gpio_hold_en((gpio_num_t)PIN_OLED_RESET);  // keep it low through light sleep and resets
}
#endif
