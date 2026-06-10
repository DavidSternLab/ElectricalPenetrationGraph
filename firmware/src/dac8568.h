/* Minimal DAC8568 driver (8-ch, 16-bit) for the per-channel Vs supply.
 * SKELETON: verify command word format / internal-reference enable vs datasheet. */
#ifndef DAC8568_H
#define DAC8568_H

#include <Arduino.h>
#include <stdint.h>

class DAC8568 {
public:
    void begin(int cs, int ldac);
    void writeChannel(uint8_t ch, uint16_t code);  // write + update channel ch
private:
    int _cs, _ldac;
    void write32(uint32_t w);
};

#endif
