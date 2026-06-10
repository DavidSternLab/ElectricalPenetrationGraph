# Original Giga-8dd — circuit & spec reference

Facts extracted from the vendor manuals in `../../Giga_rig_manuals/`
(`Measuring principles.pdf`, `Manual-Giga-8dd 20.pdf`). This is the system we are
modernizing.

## Primary measurement principle

An insect with piercing mouthparts and a plant are placed in series in an electrical
circuit. The insect connects via a thin gold wire to the measuring point (M); the
plant/soil connects to the supplied voltage. The recorded signal **Vi** is the voltage
across the amplifier input resistor **Ri**.

Ohm's-law relations:
- `I = Vbe/Rbe = Vi/Ri`
- emf-component sensitivity: `Vi/V = Ri / (Ri + Rbe)`
- circuit voltage: `V = Vsbe + Vs = Vbe + Vi`

Signal has two component types:
- **emf-components** — streaming potentials in stylet canals + punctured-cell membrane
  potentials (biological voltage sources).
- **R-components** — modulation of those voltages by fluctuating insect resistance
  Rbe (valve movements, etc.).

## Front-end circuit (differential probe, Fig 13B)

Classic **3-op-amp instrumentation amplifier**:
- **Amp 1** buffer: + input = insect (gold wire), high-impedance node.
- **Amp 2** buffer: + input = supplied-voltage (Vs) side of Ri, high-impedance node.
- **Ri** sits **between the two buffer + inputs**. The tiny insect–plant current flows
  through Ri; both buffers read across it. (Both buffers must therefore be electrometer
  grade — see below.)
- **Amp 3** difference amp: 1 kΩ / 50 kΩ resistors set **50× primary gain**.
- Control box adds a 2nd stage up to 2× → 50–100× total.

### Input resistance Ri — 1 GΩ / 10 TΩ switch
- **1 GΩ (default, "R+emf" mode):** records entangled R- and emf-components. The routine
  mode for all insects incl. aphids.
- **10 TΩ ("pure emf" mode):** the 10 TΩ is **not a discrete resistor** — it is the
  op-amp's own intrinsic input resistance, exposed by switching the external 1 GΩ out.
  Specialized for plant electrophysiology (membrane potentials). Suppresses R-components,
  so NOT what aphid feeding-behavior work wants.

### Critical component
- **Electrometer op-amp, input bias current < 30 fA.** With Ri = 1 GΩ, 30 fA → ~30 µV
  error. A normal op-amp (nA bias) would error by volts and not work. Original part:
  CA3240; modern candidates: ADA4530-1, LMP7721, LMC6001. Needs PCB guard rings +
  cleanliness. The same op-amp's >10^13 Ω input R provides the 10 TΩ mode for free.

## Documented specifications

| Parameter | Value |
|---|---|
| Channels | 8 |
| Primary gain (probe) | 50× |
| Total gain | 50–100× (2nd stage up to 2×) |
| Input resistance | 1 GΩ default, 10 TΩ (emf-mode) |
| Input bias current | < 30 fA |
| Supplied voltage Vs | ± 0.5 V (user-set, per channel) |
| Calibration pulse | −50 mV (added on top of Vs) |
| ADC | 14-bit, 100 Hz default sample rate |
| Output range | ± 5.85 V |
| Power | 5 V from USB → converted to bipolar ± rails |
| Probe cable | ~75 cm, shielded; BNC at probe input |

## Drift & adjustment behavior (relevant to goal #4)

- The drift that requires manual re-centering is **electrode potential** drift (galvanic
  metal–electrolyte junctions at insect and soil electrodes), ±100–200 mV, slow. The
  manuals explicitly state **op-amp drift is negligible** by comparison.
- Vs is used to compensate it AND to set the V-level, which changes the R/emf balance and
  how waveforms appear (Figs 8–9). So any automatic correction must act slowly and be
  logged, to avoid silently altering the recorded signal's character.

## Front-end bandwidth (relevant to goal #1)

Limited by Ri × stray capacitance at the input node. At 1 GΩ with ~1–5 pF this is roughly
a few hundred Hz to ~1 kHz; at 10 TΩ it is ~1000× lower (sub-Hz). Because the buffers are
in the probe, cable capacitance is post-buffer and does not limit this. Implication:
oversampling to ~1–2 kHz at 1 GΩ is meaningful; beyond that mostly oversamples noise
unless Ri is reduced.

## Aphid waveform timing (design targets)

From `aphid waveform characteristics.pdf`: waveforms A, B, C (pathway), pd (potential
drops, intracellular punctures, fast edges), E1/E2 (phloem), G (xylem), F (derailed
stylet). Listed repetition rates span ~0.2 to ~19 Hz; the fastest features of interest
are the **edges** of potential drops and the calibration pulse.
