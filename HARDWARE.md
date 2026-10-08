# NFC reader wiring

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
- Buck converter output: 5.02 V.
- Buck OUT+ → ESP32 5V/VIN and PN532 VCC.
- Buck OUT− → ESP32 GND and PN532 GND.
- ESP32 GPIO logic is 3.3 V and is not 5 V tolerant.
- Avoid simultaneous USB and external 5 V until the board's power circuitry is verified.

## Firmware

Board profile: ESP32 Dev Module (`esp32:esp32:esp32`).
Upload speed: 115200 baud.
PN532 read timeout: 1000 ms; passive activation retries: 1.

```sh
make install device=NFC_READER
```
