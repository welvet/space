# NFC reader

Board: ESP32 NodeMCU / DevKit, ESP32-WROOM-32, CH9102F USB-to-serial.
Device: `NFC_READER_582ABDD8ED94`.
Reader: PN532 V3 in SPI mode.

| PN532 | Wire | ESP32 GPIO |
| --- | --- | --- |
| SCK | Yellow | 18 |
| MISO | Blue | 19 |
| MOSI | Black | 23 |
| SS/CS | White | 5 |

```cpp
SPI.begin(18, 19, 23, 5);
Adafruit_PN532 reader(5, &SPI);
```

Use GPIO numbers in code; D5/D6/D7/D8 are diagram labels.
GPIO5 is a boot-strapping pin; the reader must not force an incorrect level at boot.

## Power

- Battery: 6 AAA cells in series, approximately 9 V nominal.
- Buck converter: Hailege 5Pcs 3A DC-DC Step Down Buck Power Regulator Power Conversion Module 24V to 12V 5V 3V Adjustable.
- Buck converter output: 5.02 V.
- Buck OUT+ → ESP32 5V/VIN and PN532 VCC.
- Buck OUT− → ESP32 GND and PN532 GND.
- Bulk capacitor: 1000 µF, 16 V electrolytic, across ESP32 5V/VIN (+) and GND (−), with short leads.
- ESP32 GPIO logic is 3.3 V and is not 5 V tolerant.
- Avoid simultaneous USB and external 5 V until the board's power circuitry is verified.

## Firmware

Board profile: ESP32 Dev Module (`esp32:esp32:esp32`).
Upload speed: 115200 baud.
PN532 read timeout: 1000 ms; passive activation retries: 1.

```sh
make install device=NFC_READER
```

# Switch servo

Board: ESP32 NodeMCU / DevKit, ESP32-WROOM-32, CH9102F USB-to-serial.
Servo: MG90S positional servo, on a separate ESP32.
Device identifier: `SWITCH_<MAC>`, using the same MAC source as the NFC reader.

| MG90S | Connection |
| --- | --- |
| Signal (orange/yellow), yellow extension wire | ESP32 GPIO18 |
| Power (red) | Buck OUT+ (5.02 V) |
| Ground (brown) | Buck OUT− and ESP32 GND |

Use the same battery, buck converter, board profile, upload speed, and 1000 µF capacitor as above. Buck OUT+ also supplies ESP32 5V/VIN; OUT− also connects to ESP32 GND. Do not power the servo from the 3.3 V pin. The same USB/external-power precaution applies.

The local `firmware.json` SWITCH profile uses task `switch` and pin `18`.

```sh
make install device=SWITCH
```

Control uses 50 Hz PWM with 1000–2000 µs pulses and requires Arduino-ESP32 3.x. `rotate` sets a signed target angle from −90 to +90 degrees, with 0 at centre; it is not a relative movement. Actual travel depends on servo calibration. `power` accepts 1 or 0 to enable or stop PWM; stopping PWM does not disconnect the 5 V supply. `sleep` waits for an integer number of milliseconds. Add a sleep after rotation to allow physical movement before disabling PWM.

POST a JSON list to `/device/SWITCH_<MAC>/switch`, or call `Automation.runSwitch(device, commands)`:

```json
[
  {"cmd": "power", "value": 1},
  {"cmd": "rotate", "value": 90},
  {"cmd": "sleep", "value": 5000},
  {"cmd": "rotate", "value": -50},
  {"cmd": "sleep", "value": 1000},
  {"cmd": "power", "value": 0}
]
```

The TCP envelope is `{"cmd":"batch","commands":[...]}`. Batches are validated before execution, run sequentially in the device task, and may contain at most 2047 encoded bytes. Networking and heartbeats continue during sleeps. The existing `/device/{device}/switch/{position}` route and `setSwitch` method accept a numeric target for SWITCH devices, enabling PWM before rotation. NFC reader messages are unchanged. Switch states report `ready`, `pin`, `power`, and `angle`, plus `error` on failure. A running batch completes if networking disconnects; queued batches are discarded by the existing connection logic.
