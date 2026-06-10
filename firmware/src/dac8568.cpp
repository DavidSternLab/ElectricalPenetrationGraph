/* DAC8568 driver SKELETON — see header. */
#include "dac8568.h"
#include <SPI.h>

void DAC8568::write32(uint32_t w) {
    SPI.beginTransaction(SPISettings(20000000, MSBFIRST, SPI_MODE1));
    digitalWrite(_cs, LOW);
    SPI.transfer((w >> 24) & 0xFF); SPI.transfer((w >> 16) & 0xFF);
    SPI.transfer((w >> 8) & 0xFF);  SPI.transfer(w & 0xFF);
    digitalWrite(_cs, HIGH);
    SPI.endTransaction();
}

void DAC8568::begin(int cs, int ldac) {
    _cs = cs; _ldac = ldac;
    pinMode(_cs, OUTPUT);   digitalWrite(_cs, HIGH);
    pinMode(_ldac, OUTPUT); digitalWrite(_ldac, LOW);  // update on write
    SPI.begin();
    // TODO: enable internal reference (static): command 0x08, data 0x01 (verify).
    write32(0x080000001UL & 0xFFFFFFFF);
}

// 32-bit word: [prefix(4)=0][control(4)=0x3 write&update][address(4)=ch][data(16)][feature(4)=0]
void DAC8568::writeChannel(uint8_t ch, uint16_t code) {
    uint32_t w = ((uint32_t)0x3 << 24) | ((uint32_t)(ch & 0xF) << 20) | ((uint32_t)code << 4);
    write32(w);
}
