# System architecture (working draft)

Consolidated view of the design as decided so far (see [design-log.md](design-log.md)
D1–D10). Two physical units: **probe heads** (one per channel, inside the Faraday cage)
and a single **motherboard** (all digital, outside the cage), joined by shielded
multi-conductor cables with Lemo/ODU connectors.

## Block diagram

```
  ┌───────────── PROBE HEAD ×8 (inside Faraday cage) ──────────────┐
  │                                                                │
  insect ─BNC─►(+)┌────────────┐                                   │
                  │ ADA4530-1  │A1 (electrometer buffer, guarded)  │
                  └─────┬──────┘                                   │
                        │   ┌──────[ Ri ]──────┐                   │
                        │   │ 1GΩ via latching  │                  │
                        ├───┤ reed relay (closed)│                 │
                        │   │ 10TΩ = amp intrinsic│                │
                        │   │      (relay open)   │                │
                  ┌─────┴──────┐  └──────────────┘                 │
                  │ ADA4530-1  │A2 (electrometer buffer)           │
                  └─────┬──────┘  ▲                                │
                        │         └─ Vs (filtered, from m'board)   │
                  ┌─────▼──────┐                                   │
                  │ diff amp   │  fixed gain ≥50× → Vsig           │
                  │ (amp 3)    │                                   │
                  └─────┬──────┘                                   │
                  ┌─────┴───────┐                                  │
            ┌─────┤ buf +1      ├──── line A ─┐                    │
   Vsig ────┤     └─────────────┘             │ differential       │
            │     ┌─────────────┐             │ pair (twisted)     │
            └─────┤ inv −1      ├──── line B ─┘                    │
                  └─────────────┘                                  │
  plant ─────────────────────────────────── earth/GND             │
  └─────────────────────── Lemo/ODU 8-pin + shielded cable ───────┘
        carries: A, B, Vs, +V, −V, AGND, Ri-switch ctrl, (shield)

  ┌──────────────── MOTHERBOARD (outside cage) ────────────────────┐
  │  A/B ►► ADS131M08  (8-ch, 24-bit, simul-sampling Σ-Δ,          │
  │           differential inputs = the diff receiver) ──SPI──┐    │
  │                                                           ▼    │
  │  Vs out ◄── LPF ◄── scale/offset ◄── DAC8568 ◄──SPI──► RP2040 ─┼─USB-CDC─► host
  │  Ri ctrl ◄── relay driver ◄─────────────────────────► (servo + │
  │                                                  streaming)    │
  │  Power: USB 5V ─► LM27762 ─► clean ±V analog                   │
  │                   └──────► 3.3V LDO ─► digital                 │
  └────────────────────────────────────────────────────────────────┘
```

## Signal chain (per channel)

1. **Insect electrode** (gold wire) → BNC → ADA4530-1 buffer **A1** (the critical
   high-impedance, guarded node).
2. **Ri** between A1 and A2 inputs: 1 GΩ resistor in series with a **latching reed relay**
   (closed = 1 GΩ R+emf mode; open = 10 TΩ pure-emf mode, set by the amps' intrinsic input
   resistance).
3. **A2** buffers the Vs side of Ri; **Vs** (slow, filtered) is applied here from the
   motherboard DAC.
4. **Difference amp (A3)**, fixed gain ≥50× → single-ended `Vsig`.
5. **Differential cable drive:** a unity buffer (line A) + an inverter (line B) present
   `Vsig` differentially to the cable. (These are ordinary precision op-amps — low-impedance
   side.)
6. **Cable** (Lemo/ODU) → motherboard.
7. **ADS131M08** differential input does the A−B subtraction (rejecting common-mode cable
   noise) and digitizes 24-bit, all 8 channels simultaneously.
8. **RP2040** streams samples over USB-CDC and runs the Vs servo + Ri-switch control.

## Key behaviors

- **Plant = earth ground** (differential primary circuit, D7/original differential design):
  enables multiple insects per plant and field use; adjustments are on the insect side.
- **Cal pulse** = firmware-commanded −50 mV step on the Vs line (no dedicated hardware).
- **Auto-drift correction** = slow Vs servo toward a user-set target baseline, every change
  logged (design TBD — next topic).
- **Only per-channel adjustment = Vs** (gain is fixed; mostly automated).

## Open / to-be-detailed
- Vs servo loop (sense, rate, target, logging, manual override).
- Noise budget → final fixed-gain value; ADS131M08 vs AD7768-8.
- Bipolar-supply detail + USB current budget; clean ADC clock.
- Mechanical: probe-head enclosure (shielded), guard-ring layout, conformal coating.
- Device↔host protocol + open data file format.
