/* ADS131M08 driver SKELETON — see header. Verify timing/registers vs datasheet. */
#include "ads131m08.h"
#include <SPI.h>

// ADS131M08 SPI frames are words of 24 bits, MSB first, SPI mode 1.
uint32_t ADS131M08::xfer24(uint32_t tx) {
    uint8_t b0 = (tx >> 16) & 0xFF, b1 = (tx >> 8) & 0xFF, b2 = tx & 0xFF;
    uint32_t r = 0;
    r |= (uint32_t)SPI.transfer(b0) << 16;
    r |= (uint32_t)SPI.transfer(b1) << 8;
    r |= (uint32_t)SPI.transfer(b2);
    return r;
}

void ADS131M08::begin(int cs, int drdy, int reset) {
    _cs = cs; _drdy = drdy; _reset = reset;
    pinMode(_cs, OUTPUT);   digitalWrite(_cs, HIGH);
    pinMode(_drdy, INPUT_PULLUP);
    pinMode(_reset, OUTPUT);
    digitalWrite(_reset, LOW);  delay(1);
    digitalWrite(_reset, HIGH); delay(5);
    SPI.begin();
    SPI.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE1));
    // TODO: write CLOCK, MODE, GAIN, CFG registers here (datasheet §register map):
    //  - set OSR for the desired output rate (decimation), gain=1, channels enabled.
    //  - UNLOCK before register writes; LOCK after.
    SPI.endTransaction();
}

// One data frame = STATUS word + 8 channel words (+ CRC). We issue NULL command
// words and read back the response frame.
bool ADS131M08::readFrame(int32_t ch[8]) {
    if (digitalRead(_drdy) != LOW) return false;
    SPI.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE1));
    digitalWrite(_cs, LOW);
    xfer24(0x000000);                 // STATUS / response to previous command
    for (int i = 0; i < 8; i++) {
        uint32_t w = xfer24(0x000000);
        ch[i] = (w & 0x800000) ? (int32_t)(w | 0xFF000000) : (int32_t)w; // sign-extend 24->32
    }
    xfer24(0x000000);                 // CRC word (TODO: verify)
    digitalWrite(_cs, HIGH);
    SPI.endTransaction();
    return true;
}
