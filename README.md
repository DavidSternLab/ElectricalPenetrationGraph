# EPG Rig Redesign

An open, modern redesign of the Electrical Penetration Graph (EPG) recording rig —
new hardware, firmware, and software — to replace the commercial **Giga-8dd**
(EPG Systems EU / W.F. Tjallingii). Used to record stylet-penetration / feeding
behavior of the pea aphid *Acyrthosiphon pisum*.

## Goals

1. **Improve temporal resolution** of sampling (original: 14-bit ADC @ 100 Hz default).
2. **Reduce production cost.**
3. **Simplify construction.**
4. **Automate voltage-drift correction** — the electrode-potential drift currently
   corrected by hand via the supplied voltage (Vs). An auto-detect/correct in firmware/software.
5. **Cross-platform software** — original Stylet+ is Windows-only and needs custom
   USB/COM/ActiveX drivers.

## Status

Early design phase — working through architecture decisions interactively.
See [docs/design-log.md](docs/design-log.md) for locked decisions and rationale.

## Document index

- [docs/design-log.md](docs/design-log.md) — decision log (what's locked + why).
- [docs/system-architecture.md](docs/system-architecture.md) — consolidated block diagram
  + signal chain as decided so far.
- [docs/noise-bandwidth-budget.md](docs/noise-bandwidth-budget.md) — quantitative noise &
  bandwidth analysis → gain, ADC, and the layout-critical input-capacitance spec.
- [docs/protocol-and-data-format.md](docs/protocol-and-data-format.md) — USB device↔host
  protocol + HDF5 recording format (draft v0.1).
- [docs/original-circuit-reference.md](docs/original-circuit-reference.md) — facts
  extracted from the Giga-8dd manuals (the circuit we're modernizing).
- [docs/conversation-log.md](docs/conversation-log.md) — chronological narrative of
  the design discussions.

## Folders

- `docs/` — design docs and decision records.
- `hardware/` — [single-channel-schematic.md](hardware/single-channel-schematic.md) (draft v0.1,
  SPICE-verified), [pcb-layout.md](hardware/pcb-layout.md) (layout spec / hand-off);
  `hardware/sim/` ngspice netlist; `hardware/netlist/` (ERC-checked netlist + generated
  `single_channel.kicad_sch` with footprints + SVG/PDF); `hardware/pcb/` (pre-placed
  `single_channel.kicad_pcb`, custom `.kicad_dru`, board render).
- `firmware/` — RP2040 firmware: portable C protocol (host-tested + interop-verified vs the
  Python codec) + Arduino app skeleton.
- `firmware/` — MCU firmware (to come).
- `software/` — cross-platform acquisition + analysis app, Python/pyqtgraph (to come).

## Source material

Original vendor documentation lives one level up in `../Giga_rig_manuals/`
(start with `Measuring principles.pdf`; differential probe circuit is Appendix 5 /
Fig 13B of `Manual-Giga-8dd 20.pdf`). The original Windows software in
`../original_rig_software/` is distributed only as `.exe` installers, so the Stylet+
data file format is not recoverable from it — we will define our own open format.
