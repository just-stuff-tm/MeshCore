#pragma once
// Serial-in-PowerSaving (just-stuff-tm/EasySkyMesh "serial" builds)
// Keeps the UART serial CLI usable while ESP32 PowerSaving light-sleeps:
//  - UART0 RX can wake the MCU (any byte, e.g. a bare CR or LF from an attached controller),
//  - the board stays awake while serial traffic continues (SERIAL_WAKE_HOLD_MS after the last byte),
//  - CLI (serial and remote admin): "set serial.ondemand on|off" (default on), "get serial.ondemand".
//    Stored in NVS (namespace "serialwake"), so it survives reboots and firmware updates
//    without changing the upstream prefs file layout.
// The byte that wakes the MCU is lost: send a CR/LF first, wait ~100 ms, then the command.

namespace SerialWake {
  bool handleCommand(const char* command, char* reply);  // true = handled
  bool beforeSleep();                                     // true = stay awake (skip this sleep)
  void afterSleep();
}
