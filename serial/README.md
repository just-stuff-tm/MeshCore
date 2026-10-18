# MeshCore + EasySkyMesh power saving + serial.ondemand

One repo, three ingredients, built for every board:
1. **Stock MeshCore**, newest release ([meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore)), currently v1.18.0.
2. **EasySkyMesh power saving** ([IoTThinks/EasySkyMesh](https://github.com/IoTThinks/EasySkyMesh)), ported onto that release. The port lives on branch [`powersaving`](https://github.com/just-stuff-tm/MeshCore/tree/powersaving).
3. **serial.ondemand**, so the serial console keeps working while power saving is on, plus **headless Heltec V3** builds.

## Power saving (branch `powersaving`)
The PowerSaving 17.1 feature set on MeshCore 1.18.0. The branch starts from MeshCore 1.18.0 and carries EasySkyMesh's power-saving commits (from IoTThinks/MeshCore `PowerSaving-v18`, which already sits on 1.18.0), plus our own completion:
- `PacketManager::getInboundTotal()` and `Dispatcher::isTransmitting()`, so a node doesn't sleep while a received packet waits out its rx delay or while a transmit is in flight;
- companion power saving from PowerSaving 17.1: ESP32 automatic light sleep (80/40 MHz) for BLE companions, BLE modem sleep, RX duty cycle, GPS power-saving profile (USB companions keep the CPU awake);
- stock `build.sh` file naming.

What it does:
- `powersaving on`: repeaters, room servers and sensors light-sleep between packets (30 s timer, woken by LoRa DIO1 or the user button; button wake keeps it awake 30 s). nRF52 boards sleep with WFE.
- RX duty cycle on SX1262/LR1110 (`get radio.rxps`, `set radio.rxps ...`): the radio sleeps between preamble checks. Default on, balanced level 6.
- GPS power saving (GPS on at most 10 min, then off), `reboot.interval`, power-off and deep-sleep fixes for many boards, keeping time across resets on nRF52.
- ESP32 boards use EasySkyMesh's low-power Arduino core 2.0.17 build.
- Defaults for a fresh install: `powersaving` on, RXPS on. An upgrade keeps your saved `powersaving` setting.

## serial.ondemand
- With `powersaving on`, ESP32 repeaters light-sleep between packets. While asleep, the UART is stopped, so a controller wired to the serial port gets no answer. In this setup that's a LilyGO T-SIM on a Heltec V3's GPIO44 (RX) / GPIO43 (TX).
- With `serial.ondemand` **on** (the default), any byte on UART0 RX wakes the board, and it stays awake 15 s after the last byte, so the whole command and reply get through.
- The byte that wakes the board is lost. Send CR or LF, wait about 100 ms, then send the command. The T-SIM firmware already does this.
- Commands, over serial or remote admin:
  - `set serial.ondemand on` / `set serial.ondemand off` (**off** = exactly the behaviour without this addition)
  - `get serial.ondemand`, which replies `> on` or `> off`
- The setting is stored in NVS (namespace `serialwake`), so it survives reboots and firmware updates.
- Applies to ESP32 boards whose serial port is a UART (e.g. Heltec V3). On nRF52 and native-USB ESP32 boards, serial already works during power saving, so nothing changes there. Those boards answer `get serial.ondemand` with `> on (always)`.
- Power cost: none while the line is idle (RX has a pull-up, so it doesn't wake on noise). Each burst of commands keeps the board awake for 15 s after the last byte.

## Headless Heltec V3
`Heltec_v3_repeater_headless`, `Heltec_v3_room_server_headless`, `Heltec_v3_companion_radio_usb_headless`, `Heltec_v3_companion_radio_ble_headless`, for boards with no screen fitted or where the screen should stay dark:
- generated from the matching `Heltec_v3_*` env at build time, so they stay identical to it except: no `DISPLAY_CLASS`, no display driver or UI code, so no display library is linked;
- the OLED is held in reset (GPIO21 low, latched with `gpio_hold_en`) from before `setup()`, so the panel stays off and draws nothing. Vext (GPIO36) is left as in the normal build, because it also powers the Vext header (external sensors);
- they include the same power saving as the normal builds.

## Releases
- Release tag `vX.Y.Z-powersaving`, e.g. `v1.18.0-powersaving` (title "MeshCore vX.Y.Z + power saving"; serial.ondemand and the headless builds are listed as features). Every env MeshCore releases is built (about 350 repeater, room server and companion boards), plus the headless Heltec V3 envs and `SHA256SUMS.txt`. The release notes list the exact MeshCore and power-saving commits.
- File names: `Heltec_v3_repeater-v1.18.0-powersaving-<commit>.bin` is the update image (keeps identity and settings). `...-merged.bin` is a fresh install (erases). nRF52 boards get `.zip` (DFU) and `.uf2`.
- Firmware version shown by `ver`: `v1.18.0-powersaving-<commit>`.

## When MeshCore or EasySkyMesh releases
Press **Run workflow** (Actions → "Serial builds" → Run workflow). You can press **Sync fork** on `main` first to keep the mirror current, but the build doesn't need it: it fetches the newest MeshCore release itself. There is no schedule; builds only run when you press Run workflow or push to `powersaving-serial`.

What a run does:
1. finds the newest MeshCore release;
2. checks it out and merges the `powersaving` branch into it;
3. **if the merge conflicts**, the run stops, lists the conflicting files in the run summary and opens an issue with the list (when Issues are enabled). Nothing is built or released. To fix: merge the new MeshCore release into `powersaving`, resolve those files, push, and press Run workflow;
4. otherwise applies `serial/`, builds everything and publishes the release.

If nothing changed since the last release (same MeshCore, power-saving branch and patch), the run ends after a few seconds.

When EasySkyMesh publishes new power-saving work (the watcher below reports it), bring it into `powersaving` and press Run workflow.

Run workflow options:
- **version**: build an older MeshCore release, e.g. `v1.17.0`.
- **force**: rebuild even if the release exists.
- **powersaving**: `port` (default, branch `powersaving`); `easyskymesh-latest` merges the source of EasySkyMesh's latest release instead (tag `vX.Y.Z-psNN-serial`); `off` builds MeshCore + serial.ondemand only (tag `vX.Y.Z-serial`).
- **esm_ref**: use another branch, tag or commit as the power-saving source (in this repo for `port`, in IoTThinks/MeshCore for `easyskymesh-latest`).
- **esm_conflicts**: `prefer-easyskymesh` resolves conflicting lines with the power-saving side instead of stopping. The result may not compile; boards that fail are listed in the release notes.

## EasySkyMesh change watcher
Actions → **EasySkyMesh watch** → Run workflow checks for new EasySkyMesh power-saving work:
- new commits to power-saving files on the newest `PowerSaving-vNN` branch of IoTThinks/MeshCore,
- and new EasySkyMesh releases.

For each change it opens one issue (label `easyskymesh-watch`) with the changed files, commits and a diff link, and never opens the same one twice. Issues must be enabled in Settings → General → Features. Until then, a change is reported once as a failed run with the details in the run summary. When it reports something, bring it into `powersaving` and press Run workflow on "Serial builds".

## Branches
- **powersaving-serial** (default branch): the complete firmware source — MeshCore 1.18.0 + power saving + serial.ondemand + headless Heltec V3 envs — with `serial/` (patch and build scripts) and the workflows. Build it locally with `pio run -e Heltec_v3_repeater` (or any env).
- **powersaving**: the power-saving port alone (MeshCore 1.18.0 + EasySkyMesh power saving). Builds merge this into the newest MeshCore release.
- **main**: a clean mirror of meshcore-dev/MeshCore, so **Sync fork** always works.
- Rulesets block force-pushes and deletion of `powersaving` and `powersaving-serial`.

## How the source is put together
- `serial/plan_stock.py` picks the MeshCore release and the power-saving commit; `serial/source.py` merges them (a fixed-identity merge commit, so every build job gets the same commit hash) and runs `serial/apply-serial.py`.
- `serial/apply-serial.py` copies `serial/src/helpers/SerialWake.{h,cpp}` in and adds three one-line hooks, found by matching code rather than line numbers:
  - an include in `ESP32Board.h`,
  - one hook before and one after `esp_light_sleep_start()` in `ESP32Board::sleep()`,
  - a call on the first line of `CommonCLI::handleCommand()`.
- It also generates `variants/heltec_v3_headless/platformio.ini` from `variants/heltec_v3/platformio.ini` and copies `serial/variants/heltec_v3_headless/headless.cpp`.

## Credits and license
- [MeshCore](https://github.com/meshcore-dev/MeshCore) by Scott Powell / rippleradios.com and contributors, MIT licensed (`license.txt`).
- Power saving by [IoTThinks / EasySkyMesh](https://github.com/IoTThinks/EasySkyMesh) (PowerSaving firmware and low-power Arduino core, MIT), from [IoTThinks/MeshCore](https://github.com/IoTThinks/MeshCore).
- The power-saving completion on `powersaving`, `serial.ondemand` and the headless envs (`serial/`) are released under the same MIT license.
