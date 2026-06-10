# Single-channel schematic (draft v0.1)

First schematic-level design for one EPG channel, implementing the locked decisions
(D1–D13). Split across the **probe-head daughtercard** (one per channel, in the Faraday
cage) and the shared **motherboard** (outside the cage). The analog chain's gain, the
Ohm's-law divider, and the front-end bandwidth are **verified by SPICE**
(`sim/single_channel.cir`); see §6.

## 1. Block diagram

```
            DAUGHTERCARD (probe head, in cage)                       MOTHERBOARD (outside cage)
  insect ─BNC(J1)─┬───────────────┐ M
                  │            +  ╱│ A1 = ADA4530-1
                  │   ┌────────┤+  │── a1 ──┐ (unity follower, GUARD-ringed)
                  │   │         ╲ │          │
              Cin═╪═  │          ─┘          │   ┌─ Rg ─┐         FDA = ADA4940-1
            (≤1pF)│   │  [Ri 1GΩ]            ├──[Rg]──┤−  ╲___ OUT+ ─Riso─�────►║  A B ►► ADS131M08
                  │   │  + K1(reed)          │        │FDA │              ║      AINxP/AINxN
                  │   └──/ ──────┐ S         │   ┌────┤+  ╱‾‾‾ OUT− ─Riso─�────►║   (24-bit, 8-ch,
  plant ─────── earth/GND        │           │   │    └ VOCM=ADC Vcm        ║    simul-sampling,
                  ┌──────────────┘           │   │                          ║    differential)
            Vs_in ┤ (filtered)   +  ╱│ A2     │  [Rf]                         SPI │ DRDY
                  └──────────────┤+  │── a2 ──┘   │                              ▼
                                  ╲ │            (a2 also feeds FDA + via Rg)  RP2040 ──USB-CDC──► host
                                   ─┘ A2=ADA4530-1                              │ SPI
                                                                                ▼
   Vs_in ◄── LPF(~10Hz) ◄── scale/offset(±0.5V) ◄── DAC8568 ◄────────────── (Vs servo + cal pulse)
   Ri_ctrl ◄── latching-relay driver ◄── GPIO ─────────────────────────────  (1GΩ/10TΩ select)
   Power: USB 5V ─► LM27762 ─► ±5V analog (clean) ;  ─► 3.3V LDO ─► digital
```

## 2. Analog signal chain (daughtercard)

1. **Insect electrode → node M** via BNC (J1). M is the high-impedance measuring point;
   guard ring driven by A1's GUARD pin; keep the trace tiny (see §5).
2. **A1, A2 = ADA4530-1** femtoampere electrometer op-amps, unity-gain followers. A1 senses
   M (insect); A2 senses S (the Vs side of Ri). Both present ~fA load so they don't corrupt
   the sub-nA current through Ri. (Two electrometer amps/channel — D8.)
3. **Ri network between M and S:** Ri = 1 GΩ precision resistor in series with **K1**, a
   latching reed relay. Closed → Ri = 1 GΩ (R+emf mode). Open → the only path left is the
   amps' intrinsic input resistance (~10 TΩ) → pure-emf mode (D2). Reed relay for true
   open isolation; latching so it's quiet during recording.
4. **Vs_in → node S:** the filtered, scaled supplied voltage from the motherboard DAC is
   applied at S (the "former grounded side" of Ri — differential config, D7). The −50 mV
   **cal pulse rides on Vs_in** (firmware step), so no extra hardware (D14).
5. **FDA = ADA4940-1:** takes (a1 − a2) differentially through gain-set resistors and
   produces a differential pair OUT+/OUT− with common-mode = the ADC's input Vcm. This one
   stage provides **both** the gain and the differential cable drive (D6). Gain
   `G = Rf/Rg`; with **Rg = 1.00 kΩ, Rf = 8.06 kΩ → G ≈ 8** (D13: maps ±150 mV Vi to the
   ±1.2 V ADC range). Series isolation resistors Riso (~24 Ω) at each output drive the cable.

## 3. Motherboard slice

- **ADS131M08** (8-ch, 24-bit, simultaneous-sampling Σ-Δ): the channel's differential pair
  (optionally through a small RC: ~33 Ω + 2.2 nF differential) → AINxP/AINxN. The Σ-Δ
  decimation filter handles anti-aliasing (D13) — the RC is just for charge-kickback. SPI +
  DRDY to RP2040; clean CLKIN oscillator.
- **Vs path:** RP2040 → SPI → **DAC8568** (16-bit) → scale/offset op-amp (**OPA2188**-class)
  to ±0.5 V → low-pass (~10 Hz, e.g. 16 kΩ + 1 µF; the servo is slow so heavy filtering is
  fine and keeps noise off the cable) → Vs_in on the cable.
- **Ri select:** RP2040 GPIO → on-card **latching-relay driver** (a logic transition emits a
  set/reset pulse to K1) via the Ri_ctrl line. Energized only on change → no coil
  current/field near the node during recording.
- **RP2040:** USB-CDC to host; SPI to ADC + DAC; GPIO for relay. Runs the Vs servo (D11).
- **Power:** USB 5 V → **LM27762** → clean ±5 V analog (LDO-quiet) for the op-amps; **3.3 V
  LDO** for digital (RP2040, ADC/DAC digital). Within the USB current budget.

## 4. Component table (one channel + shared motherboard)

| Ref | Part | Value / note | Where |
|---|---|---|---|
| A1, A2 | ADA4530-1ARZ | electrometer, <20 fA bias, guard buffer | daughtercard |
| FDA | ADA4940-1 | fully-differential amp / ADC + cable driver | daughtercard |
| Ri | precision Gigaohm R (Ohmite RX/Vishay VHM) | 1 GΩ, 0.1% | daughtercard |
| K1 | latching reed relay (Coto/Pickering) | >10¹⁴ Ω open | daughtercard |
| Rg, Rf | thin-film 0.1% | 1.00 kΩ, 8.06 kΩ (G≈8) | daughtercard |
| Riso | thin-film | ~24 Ω ×2 | daughtercard |
| J2 | Lemo/ODU push-pull 8-pin | A,B,Vs_in,+5,−5,AGND,Ri_ctrl,shield | daughtercard |
| ADC | ADS131M08 | 8-ch 24-bit Σ-Δ | motherboard (shared) |
| DAC | DAC8568 | 8-ch 16-bit | motherboard (shared) |
| Vs amp | OPA2188 (or similar precision) | scale/offset to ±0.5 V | motherboard |
| MCU | RP2040 | USB-CDC, SPI | motherboard (shared) |
| PSU | LM27762 + 3.3 V LDO | ±5 V analog, 3.3 V digital | motherboard (shared) |

## 5. Layout-critical (the make-or-break items)

- **Cin ≤ ~1 pF at node M.** The sim shows f₋₃dB scales as `1/Cin`; 1 pF → ~318 Hz, 2 pF →
  ~159 Hz. Short M trace, minimal copper, A1 close to J1.
- **Guard ring** around M (and the Ri/relay node) driven by ADA4530-1 GUARD; **conformal
  coat** the input region; keep flux/contamination off (sub-fA leakage).
- Star/seperated analog vs digital grounds; the daughtercard carries **no clocks/digital**.

## 6. Verification (SPICE — `sim/single_channel.cir`, ngspice)

Ideal-op-amp behavioral model (checks topology + values; real noise/bias come from the parts):

| Check | Expected | Simulated |
|---|---|---|
| Ohm's-law divider Vi (Vbio=1 mV, Rbe=Ri=1 GΩ) | 0.500 mV | **0.500 mV** |
| Differential output Vout = G·Vi (G=8) | 4.00 mV | **4.00 mV** |
| Front-end f₋₃dB (Rbe‖Ri = 0.5 GΩ, Cin = 1 pF) | 318.3 Hz | **318.3 Hz** |

The bandwidth result confirms the noise-bandwidth budget (D13): at 1 GΩ the analog band is
~few-hundred Hz, capacitance-limited — so 1 kHz+ sampling oversamples it (good for edges /
anti-alias), and Cin is the dominant lever.

## 7. Open items → next
- KiCad schematic capture + symbols/footprints from this spec.
- Finalize FDA supply rail + VOCM source (match ADC input Vcm ≈ AVDD/2); ADA4940 vs lower-noise alt.
- Latching-relay driver sub-circuit (single logic line → set/reset pulse).
- Exact ADC anti-alias/charge-kickback RC; CLKIN oscillator choice.
- Vs scale/offset stage exact values + filter corner; current budget for USB.
- RP2040 firmware skeleton speaking the existing protocol (talks to the current host GUI).
