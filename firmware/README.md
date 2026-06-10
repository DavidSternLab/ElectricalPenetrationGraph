# EPG rig — RP2040 firmware

Device-side firmware. The protocol layer is **portable C, shared with the host and
unit-tested on this machine**; the RP2040 application (USB CDC + ADC/DAC/relay drivers +
Vs servo) sits on top.

```
firmware/
  proto/         epg_proto.{h,c}   portable protocol codec (COBS+CRC, builders, parser)
  test/          test_proto.c + interop_test.py + Makefile   (host-compiled, runnable now)
  src/           RP2040 app: main.cpp, ads131m08.{h,cpp}, dac8568.{h,cpp}, board.h
  platformio.ini build/flash config (arduino-pico / earlephilhower core)
```

## Status
- **`proto/` + `test/`: built and verified on the host.** `make check` runs the C
  selftest; `make interop` proves the C codec and the Python host codec
  (`software/epgrig`) are **byte-for-byte compatible** in both directions. So when this
  firmware runs, it talks to the existing host GUI unchanged.
- **`src/`: a coherent skeleton, NOT yet hardware-tested.** The ADS131M08/DAC8568 register
  sequences and the relay/servo scaling are marked `TODO: verify vs datasheet`. It will not
  have been compiled in this environment (needs the RP2040 toolchain / PlatformIO).

## Protocol tests (run now, no hardware)
```bash
cd test
make check       # C selftest: COBS / CRC / i24 / frame / parser-resync
make interop     # cross-language: C <-> Python wire compatibility
```

## Build & flash the firmware (with hardware)
```bash
# install PlatformIO (pip install platformio), then:
pio run                 # compile
pio run -t upload       # flash a Pico/RP2040 over USB
pio device monitor      # (optional) serial monitor
```
Then point the host app at the serial port (replace the mock with a pyserial transport).

## Main loop (src/main.cpp)
On ADC **DRDY**: read 8 channels → run the keep-in-range **Vs servo** (D11) → append to the
current block. Every `BLOCK_MS` (default 50 ms) a **SAMPLES** frame is flushed. Host commands
(GET_INFO / CONFIGURE / START / STOP / SET_VS / SET_RI / CAL_PULSE / SERVO / PING) are parsed
from USB; **every state change emits a sample-stamped EVENT**, so recordings stay
reconstructable exactly as the format (D14) requires.

## To finish (hardware bring-up)
- ADS131M08 register init (CLOCK/MODE/GAIN/OSR for the selected rate) + CRC handling.
- DAC8568 reference-enable + Vs code↔volts calibration; servo step gain.
- 74HC595 latching-relay set/reset pulse for Ri (1 GΩ/10 TΩ) per channel.
- Pin map in `board.h` vs the actual PCB.
