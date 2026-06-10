# Conversation log

Chronological narrative of the design discussions. Decisions are summarized formally in
[design-log.md](design-log.md); this file captures the reasoning and Q&A as it unfolded.

---

## Session 1 — 2026-06-09 / 2026-06-10

### Kickoff
David asked whether there is enough information (including a circuit model) to redesign and
build an entire new EPG rig, with five goals: better temporal resolution, lower cost,
simpler construction, automatic voltage-drift correction, and cross-platform software
(originally suggesting Java).

Read the vendor docs (`Measuring principles.pdf`, `Manual-Giga-8dd 20.pdf` incl. Appendix 5
/ Fig 13B, waveform characteristics). Conclusion: **yes**, enough to design an improved
equivalent — the front end is a textbook 3-op-amp instrumentation amp and all critical
specs are documented (see [original-circuit-reference.md](original-circuit-reference.md)).
The remaining items are design *decisions*, not missing information. Noted the original
software is Windows-only `.exe` installers, so the data format must be redefined.

### emf-mode (1 GΩ vs 10 TΩ)
David questioned whether dropping the 10 TΩ "pure emf" mode was wise, noting the docs imply
entangled R+emf is fine for small insects. Resolved: he's right — 1 GΩ entangled mode is
the correct routine mode for aphids; pure-emf is a specialized plant-electrophysiology tool
that actually suppresses the R-components used to identify waveforms. Key technical point:
the 10 TΩ is the op-amp's *own* input resistance (not a discrete part), so keeping the
switch is nearly free. → **Decision D2: keep the switch.**

### Channel count cost (1 vs 8)
David asked if 1- vs 8-channel differs much in build/cost. Explained that engineering
effort is ~channel-count-independent (front-end block designed once; ADC/DAC are already
multichannel); only the analog front-end BOM scales. → **Decision D3: per-channel
daughtercard, design for 8, build 1 first.**

### Location of digitization
Compared central digitization (analog over cable, shared ADC — like the original) vs
per-probe digitization (ADC at each probe, digital over cable). Central wins: keeps digital
switching away from the femtoamp node, gives free channel sync, lower cost, simpler
firmware. Added a cheap enhancement — drive the cable **differentially** for common-mode
noise rejection. → **Decision D6.**

### How differential cable drive works
David asked for the mechanism. Explained common-mode rejection: send the signal as the
difference between two paired wires; coupled 50/60 Hz noise and ground offsets land equally
on both and cancel in the receiver's A−B subtraction. Implementation for us: one extra
inverting op-amp per card (on the low-impedance side, post-electrometer) makes the
complementary line; the Σ-Δ ADC's native differential input is the receiver, so no separate
receiver chip is needed. Also noted the cal pulse can ride on the Vs line as a firmware
step.

### Housekeeping
Created this `EPG_redesign/` project folder and seeded README, design-log,
original-circuit-reference, and this conversation log.

### Cable & connector scheme
Established that EPG probes are positioned individually on stands (no backplane), so each
daughtercard sits in its own probe head on a multi-conductor cable. Counted ~7 conductors +
shield per channel (signal pair, Vs, ±V, AGND, Ri-switch control). Cal pulse rides on Vs
(no extra wire); ±V sent from motherboard (no switching at the probe). David chose
**Lemo/ODU push-pull 8-pin** for the probe-to-motherboard connector (premium: locking,
shielding, durability) and **BNC** stays at the probe tip. → **Decision D7.**

### Core component selection — electrometer front end
Presented the input op-amp as the make-or-break part (two electrometer amps per channel,
both across Ri). Compared ADA4530-1 (20 fA, integrated guard buffer, ~$11) vs LMP7721
(3 fA, manual guarding, ~$4). David chose **ADA4530-1** for lowest layout risk and 10 TΩ
suitability. Ri switch recommended as a **latching reed relay** for true open isolation.
→ **Decision D8.**

### Core support ICs + gain architecture + priority guidance
Recommended motherboard chipset: ADS131M08 (24-bit 8-ch simul-sampling Σ-Δ, doubles as the
differential receiver), DAC8568 (8-ch 16-bit Vs), RP2040 MCU, LM27762 bipolar power.
**David stated a standing priority:** not very cost-sensitive — maximize sensitivity and
operational simplicity at every step (saved to memory `epg-priorities`). On gain he asked me
to decide accordingly → **fixed gain, no PGA** (simplest to operate; PGA would add noise);
sensitivity comes from 24-bit + oversampling/decimation, gain value set by a noise budget.
Chose **RP2040**. → **Decisions D9, D10.** Consolidated everything into
[system-architecture.md](system-architecture.md) (block diagram + signal chain).

### Vs auto-servo design
Worked through the servo. Established it's needed even with 24-bit (50× amplifies DC
electrode drift into volts that would rail the ADC). Proposed a two-phase design: Acquire
(auto start-up adjustment) + Track. David chose **keep-in-range only** for the track phase
(hardware moves Vs only to prevent clipping; display centered in software; all Vs changes
logged). → **Decision D11.**

### Sample rate requirement
David: wants **≥ 1000 Hz** sampling (not the original 100 Hz). Already supported by the
chipset; the real implication is the front-end −3 dB bandwidth must reach ≥ ~500 Hz at
1 GΩ, which constrains input-node capacitance / guard-ring layout (ADA4530-1 guard buffer
helps). → **Decision D12.**

### Noise & bandwidth budget (D13)
Wrote [noise-bandwidth-budget.md](noise-bandwidth-budget.md). Key results: (1) noise floor =
1 GΩ thermal noise ~30–65 µV RMS, dominating op-amp/ADC by 100×+; (2) fixed gain ≈ **8×**,
not 50×, because the ADS131M08 ±1.2 V range + 24-bit depth need little analog gain; (3)
ADS131M08 confirmed, AD7768-8 unnecessary; (4) **realistic front-end bandwidth ~150–300 Hz**
at 1 GΩ — 500 Hz needs impractical sub-pF C_in, so 1 kHz sampling oversamples a ~250 Hz band
(great for edges/anti-alias, but not 500 Hz of content); C_in≈1 pF is the make-or-break
layout spec; capacitance-neutralization footprint left as future option; (5) Σ-Δ decimation
filter removes the need for an analog anti-alias filter.

### Sample-rate reconsidered (D12 revised)
David pushed back: aphid bandwidth is genuinely unknown (100 Hz prior sampling → only <50 Hz
known); worth exploring higher but maybe 1 kHz isn't required — does 500 Hz simplify the
design? Answer: **no** — sample rate is a runtime config setting, not a hardware driver
(ADC, front end, MCU, USB, layout, firmware all identical for 500 vs 1000 vs 2000 Hz; only
Nyquist ceiling + file size differ). So D12 revised to **runtime-configurable rate, default
1 kHz**, to let real recordings reveal whether faster content exists. The independent lever
is analog bandwidth (capacitance neutralization, footprint reserved). Also clarified
"railing" = amplifier/ADC output saturating at its supply rail / clipping.

### Device↔host protocol + data format (D14)
Drafted [protocol-and-data-format.md](protocol-and-data-format.md) v0.1. USB CDC + COBS
framing + CRC; typed messages; `sample_index` master timeline; every state change emitted as
a timestamped EVENT (authoritative log). Raw 24-bit codes on the wire. HDF5 file
(`/samples`, `/events`, metadata), incremental crash-safe writes, defined reconstruction
conventions, CSV + future NWB export. This unblocks the Python software to build against the
contract in parallel with hardware.

### Python software + mock device (D15) — BUILT & TESTED
Chose to build the software first. Implemented `software/epgrig` (protocol/mock/acquisition/
recorder/reader/dsp/gui) + scripts + tests. Fixed three bugs during bring-up (COBS encoder,
an Info struct size, and over-strict test thresholds). **All 15 tests pass**; headless demo
records 30 s × 8 ch @ 1 kHz to HDF5 with 0 CRC errors and demonstrates the Vs servo +
reconstruction. The D14 protocol/format contract is now validated by real code; real
hardware will drop in behind the same protocol via pyserial. See [design-log D15](design-log.md).

### GUI bring-up feedback + real acquisition app
David ran the demo GUI: it displayed, but the detrend toggle did nothing. Cause: the
keypress handler was attached as an instance attribute (`win.keyPressEvent = ...`), which
Qt never calls (it dispatches the virtual to the class method). Replaced the hidden keypress
with on-screen controls. Rebuilt `gui.py` into a real acquisition window: live plots with a
working **Detrend** checkbox + cutoff, **Record/Stop**, folder/filename/operator/experiment
fields, status (state/elapsed/samples/clip/CRC), and **Add marker** (writes EV_COMMENT).
Added recorder support for **starting mid-stream**: the file stores `device_start_sample_index`
and events are written file-relative so reconstruction stays correct (new test
`test_midstream_recording_offsets_are_file_relative`). 16 tests pass; GUI parse-checked
(Qt still not installed here, so not launched by me — David runs it).

### Sample-rate toggle + per-channel controls + GitHub repo
David: GUI looks good; add a sample-rate toggle; wire up per-channel controls; create a
GitHub repo `ElectricalPenetrationGraph` under github.com/DavidSternLab.
- **Sample-rate selector** added to the GUI (combo from `Info.supported_rates`; reconfigures
  buffers live; disabled while recording).
- **Per-channel controls** wired end-to-end through the mock: Vs (mV→DAC, SET_VS), servo mode
  off/acquire/track (SERVO), Ri 1 GΩ/10 TΩ (SET_RI), cal pulse (CAL_PULSE). The mock now
  *acts* on these and emits the corresponding logged events; cal pulse injects −50 mV and
  auto-offs; servo respects the mode. New `tests/test_commands.py` (3 tests). **19 tests pass.**
- **Git:** initialized a local repo rooted at `EPG_redesign/` (excludes the copyrighted
  vendor PDFs/installers in sibling folders) and made the initial commit. **Could NOT create
  or push the GitHub remote** — no `gh`, token, or SSH key in this environment; that step
  needs David's GitHub auth. Push instructions provided.

### GitHub repo pushed
Created + pushed **public** repo github.com/DavidSternLab/ElectricalPenetrationGraph (account
`dstern`). First `gh repo create --push` made the repo but failed to push (gh set to SSH, no
trusted key); fixed by `gh auth setup-git` + switching origin to HTTPS. 3 commits on `main`.

### Single-channel schematic v0.1 (D16) — SPICE-verified
Built `hardware/single-channel-schematic.md` and `hardware/sim/single_channel.cir`. Topology:
ADA4530-1 ×2 electrometer followers across Ri (1 GΩ + latching reed relay), FDA (ADA4940-1)
giving gain≈8 + the differential cable drive in one stage; motherboard = ADS131M08 / DAC8568
/ RP2040 / LM27762. Installed ngspice (brew) and simulated: divider Vi=0.500 mV ✓, gain
Vout=4.00 mV (8×) ✓, **f₋₃dB=318.3 Hz = analytic to 100%** → confirms the D13 bandwidth
budget and that Cin≤~1 pF is the key layout lever.

### Next (candidates)
(1) KiCad capture from the spec; (2) RP2040 firmware skeleton (same protocol → talks to the
host GUI); (3) finalize FDA supply/VOCM + relay driver + Vs stage + USB budget; (4) probe-head
mechanical/guard-ring layout; (5) software Y-zoom/analysis, NWB export, real pyserial transport.
