# Noise & bandwidth budget

Quantitative analysis that converts the architecture into component values. Numbers from
`scripts`-free hand calc (k=1.38e-23 J/K, T=300 K). **Headline: at Ri=1 GΩ the system is
dominated by two pieces of fundamental physics — the resistor's thermal noise and the
Ri·C_in bandwidth — and both are properties of the 1 GΩ choice, not of our electronics.
Our job is to sit comfortably under them, which is easy.**

## 1. Signal levels

- Original full-scale input ≈ ±117 mV (±5.85 V output ÷ 50×). Cal pulse = −50 mV input.
- After Vs cancels the DC electrode potential, the residual EPG swing is the signal itself:
  largest features ≈ ±100–150 mV; fine detail down to µV.
- Design target: **full-scale input ≈ ±150 mV** (covers large features + servo deadband).

## 2. Bandwidth — the honest constraint

Front-end −3 dB corner `f_c = 1/(2π · R_node · C_in)`, where `R_node = Rbe ‖ Ri`
(≈ 0.5 GΩ when an aphid is probing with Rbe≈Ri≈1 GΩ; = 1 GΩ when not probing).

| C_in | f_c @ R=0.5 GΩ (probing) | f_c @ R=1 GΩ |
|---|---|---|
| 0.5 pF | 637 Hz | 318 Hz |
| 1 pF | 318 Hz | 159 Hz |
| 2 pF | 159 Hz | 80 Hz |
| 5 pF | 64 Hz | 32 Hz |

To reach **500 Hz** you'd need C_in ≈ 0.32–0.64 pF — below the op-amp's own input
capacitance plus the relay and board stray. **Realistically, with aggressive guarding
(C_in ≈ 1 pF) the achievable analog bandwidth at 1 GΩ is ~150–300 Hz** (probing), ~80–160 Hz
when not probing. This is *already better than the original* (~100 Hz) but it is **not**
500 Hz.

**Implication for the 1 kHz sampling target:** sampling at ≥1 kHz is correct and worthwhile
— it oversamples the ~200–300 Hz analog band, which (a) captures the *edges* of potential
drops and the cal pulse far better than 100 Hz, (b) gives clean anti-aliasing margin, and
(c) enables oversample+decimate for SNR. But understand it as **10× better time resolution
of a ~200–300 Hz-bandwidth signal**, not 500 Hz of new spectral content. The aphid waveform
content of interest is < ~100 Hz, so this is comfortable.

**If more analog bandwidth is ever needed:** capacitance neutralization (active positive-C
feedback bootstrapping C_in, as patch-clamp amps do) can extend f_c. Recommend leaving a
populate-later footprint for it rather than building it in v1.

The 10 TΩ emf-mode is inherently sub-Hz and stays low-rate by nature (fine — it's for slow
plant potentials).

## 3. Noise — the resistor wins

Johnson noise density `e = √(4kT·R)`:
- R_node = 0.5 GΩ (aphid probing): **2.88 µV/√Hz**
- R_node = 1 GΩ (not probing): **4.07 µV/√Hz**

Integrated over the band:

| Band | R=0.5 GΩ | R=1 GΩ |
|---|---|---|
| 100 Hz | 28.8 µV RMS | 40.7 µV RMS |
| 250 Hz | 45.5 µV RMS | 64.4 µV RMS |

So the **input-referred noise floor is ~30–65 µV RMS, set entirely by the 1 GΩ resistor's
thermal noise.** Compare the other sources:
- **ADA4530-1 voltage noise** (~tens of nV/√Hz) over 250 Hz → ~1 µV — negligible.
- **ADA4530-1 current noise** (~0.07 fA/√Hz) × R_node → ~35 nV/√Hz → sub-µV — negligible.
- **ADC noise** input-referred (see §4) → ~0.3–0.4 µV — negligible (100×+ below).

This is fundamental to the 1 GΩ choice (which we keep for the science) — the original lives
at the same floor. Note: **decimation/averaging does not reduce the in-band resistor noise**
(it's already band-limited); it reduces only the wideband ADC/quantization noise and buys
anti-alias margin. Fine detail below ~30 µV is thermally limited, not electronics-limited.

## 4. Gain — much lower than the original (≈8×, not 50×)

ADS131M08 input range = ±1.2 V (internal 1.2 V ref). To map ±150 mV input FS → ±1.2 V:

`G = 1.2 V / 0.15 V ≈ 8` (±100 mV → 12; ±200 mV → 6).

**Recommended fixed gain G ≈ 8** (vs the original's 50×). It's lower purely because our ADC
has a modest input window *and* 24-bit depth — we don't need big analog gain to preserve
resolution. At G=8 the ADC noise referred to input is **0.31 µV** — 144× below the resistor
floor — so the ADC contributes nothing, and there's no case for the pricier AD7768-8.
The differential signal on the cable is ±1.2 V — plenty robust with differential drive.

## 5. Why 24-bit (since the resistor dominates)?

Not for the noise floor — even 16-bit gives a 4.6 µV input-referred LSB at G=8, already
below the 30 µV resistor floor. 24-bit is for **dynamic range / headroom**: capture the full
±150 mV signal plus residual servo offset with quantization utterly negligible, at a single
fixed gain, with no gain knob. Cheap insurance; keep it (D10).

## 6. Sampling & decimation scheme

- Run the ADS131M08 modulator fast; **output ≥1 kHz/channel** (D12). Offer selectable rates
  (e.g. 1, 2, 4 kHz) and optionally a high-rate raw stream.
- The Σ-Δ decimation filter provides anti-aliasing, so **no separate analog AA filter** is
  needed (a nice simplification) — the ~250 Hz front-end roll-off is extra margin.
- Oversample+decimate to the output rate to suppress wideband/quantization noise.

## 7. Conclusions → component commitments

1. **Fixed gain G ≈ 8** (confirm against final max-feature spec; ±150 mV input FS).
2. **ADS131M08 confirmed**; AD7768-8 not warranted (resistor floor masks the difference).
3. **Keep 24-bit** for dynamic range / no-gain-knob operation.
4. **Front-end bandwidth ~150–300 Hz** at 1 GΩ is the realistic target; **C_in ≈ 1 pF is the
   make-or-break layout spec** → drives guard-ring design (ADA4530-1 guard buffer), short
   input traces, relay placement, conformal coat.
5. **1 kHz+ sampling confirmed and beneficial**, understood as time-resolution/edge/anti-alias
   gains over a ~200–300 Hz band, not 500 Hz of bandwidth.
6. Leave a **populate-later footprint for capacitance neutralization** if higher analog
   bandwidth is ever required.
