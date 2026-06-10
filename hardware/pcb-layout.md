# PCB layout specification — single-channel probe-head daughtercard

**Hand-off to the KiCad layout engineer.** The electrical design is fixed and verified
(schematic `netlist/single_channel.kicad_sch` with footprints; SPICE in `sim/`; ERC clean).
This board is a **femtoampere electrometer front end** — *layout is the design*. The rules
below are not style preferences; violating the input-node ones will sink the instrument's
performance. Do **not** autoroute the input section.

## What's provided vs. what you do
- **Provided:** schematic with footprints assigned; a starting board `pcb/single_channel.kicad_pcb`
  (23 footprints pre-placed with the intended signal flow, 60×40 mm outline, 4 layers) and a
  `pcb/single_channel.kicad_dru` with custom rules.
- **You do:** *Update PCB from Schematic* (pulls nets/ratsnest — the schematic carries
  footprints), refine placement (the starting board has ~41 courtyard/silk/edge DRC items
  from tight auto-placement — spread/rotate to clear), implement the guard scheme below,
  route, and get a clean DRC. Replace the PLACEHOLDER footprints (J2 Lemo/ODU, K1 latching
  reed relay, optionally U3 exact LFCSP) with the real vendor footprints.

## Board & stackup
- Small daughtercard, ~50–60 × 35–40 mm (refine to fit the probe-head enclosure + BNC + Lemo).
- **4-layer**, suggested: `L1 Signal / L2 Ground / L3 Power(±5) / L4 Signal`.
- **Exception (critical):** *no ground or power copper under the high-impedance input node*
  (see below) — pour reliefs / keep-outs there on all layers.

## The make-or-break input section (node M = J1→A1.INP; RI_MID; A2.INP/S)
This is the ≤1 pF, sub-fA-leakage region (validated: f₋₃dB = 1/(2π·(Rbe‖Ri)·Cin), so Cin
sets bandwidth — D13/D16).
1. **Minimize Cin:** A1 immediately adjacent to J1; M trace as short and thin as possible;
   **no vias** on M; **no copper plane under M** on any layer (cut out / keep-out). Keep RI
   and K1 contacts right at the node.
2. **Guard ring:** surround M (and the A1 +input pin/trace, RI, K1 contacts) with a guard
   trace driven by **A1.GUARD**; do the same for A2.INP using **A2.GUARD**. The guard
   follows the high-Z trace on the component layer *and* is mirrored on the layer beneath
   (guard "box"), connected only to the GUARD pin — never to ground. This bootstraps stray
   capacitance and intercepts surface-leakage currents.
3. **Surface leakage:** consider a **milled slot/moat** in the PCB around the M node to break
   surface conduction; specify **solder-mask opening** over the guard region and **conformal
   coat** (or PTFE) after a thorough clean. Use **no-clean-free** assembly or wash + bake;
   the input area must be contamination-free (fingerprints = picoamps).
4. **The ADA4530-1 guard pins** (A1, A2) must connect *only* to their guard rings.

## Net classes (set in Board Setup → Net Classes)
| Class | Nets | Trace | Clearance | Notes |
|---|---|---|---|---|
| **HighZ** | M, RI_MID | thin (~0.2 mm), no via | ≥0.6 mm to other copper | guarded; no plane under |
| **Guard** | GUARD1, GUARD2 | ~0.3 mm | hugs HighZ | from GUARD pins only |
| Power | P5V, N5V | ≥0.4 mm | 0.2 mm | decouple at each amp (C1–C6) |
| Signal | A1_OUT, A2_OUT, FDA_*, VOCM | 0.25 mm | 0.2 mm | keep FDA gain net symmetric |
| Diff | LINE_A, LINE_B | 0.25 mm, matched | 0.2 mm | route as a pair to J2 |
| default | rest | 0.25 mm | 0.2 mm | |

## Placement intent (as pre-placed)
Left→right flow: **J1 (BNC, input edge) → A1 → [K1, RI] input cluster → A2 → U3 (FDA) +
gain net (RG/RF) → RO1/RO2 → J2 (Lemo, output edge)**. VOCM divider (RV1/RV2/CV) and the
relay driver U4 near their loads. Decoupling C1–C6 hard against the amp power pins.

## Grounding / shielding
- One solid analog ground (L2), **relieved under the input node**. Tie to the probe-head
  shield/enclosure and to chassis/Faraday-cage ground via J2 (AGND + SHLD shell).
- The daughtercard carries **no digital/clocks** (D6) — ±5 V + filtered Vs + one slow Ri
  logic line arrive over the Lemo; the relay set/reset pulse is generated locally (U4).
- Differential pair LINE_A/LINE_B: route together, length-matched, over ground.

## Differential output + ADC interface (motherboard side, FYI)
LINE_A/B (FDA outputs through RO1/RO2) drive the cable into the ADS131M08 differential
input; common-mode = VOCM ≈ 1.67 V (RV1/RV2 divider). Anti-aliasing is handled by the Σ-Δ
decimation filter (no analog AA filter; D13).

## Acceptance
- DRC clean against `single_channel.kicad_dru`.
- Guard rings continuous and connected only to GUARD pins; no copper under M; no vias on M.
- Real footprints substituted for the three PLACEHOLDERs.
