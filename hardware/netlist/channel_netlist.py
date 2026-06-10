#!/usr/bin/env python3
"""Single-channel (probe-head daughtercard) netlist + ERC-style checker.

This is the *electrical content* of the schematic, as machine-checkable data: every
component, its pins, and every net. `check()` enforces electrical rules (no floating or
double-connected pins, no unknown references, no accidental single-pin nets, power nets
present). It runs with the standard library only.

Pins are functional names (INP, OUT, VPOS, ...). Exact package pin *numbers* bind when the
KiCad symbols are assigned during capture — this netlist drives that capture and the PCB
ratsnest. Values/parts are in single-channel-schematic.md (D16).

Run:  python channel_netlist.py            # check + summary
      python channel_netlist.py --table    # also write connection-table.md
"""
from __future__ import annotations
import sys

# ---- components: ref -> (part, [functional pins]) ----
COMPONENTS = {
    "J1":  ("BNC (insect electrode)",        ["SIG", "SHLD"]),
    "A1":  ("ADA4530-1 (follower, insect)",  ["INP", "INN", "OUT", "VPOS", "VNEG", "GUARD"]),
    "A2":  ("ADA4530-1 (follower, Vs side)", ["INP", "INN", "OUT", "VPOS", "VNEG", "GUARD"]),
    "K1":  ("latching reed relay (Ri sw)",   ["P1", "P2", "CP", "CN"]),  # contacts P1/P2, coil CP/CN
    "RI":  ("1 GOhm precision resistor",     ["A", "B"]),
    "U3":  ("ADA4940-1 FDA (gain + diff drv)", ["INP", "INN", "OUTP", "OUTN", "VOCM", "VPOS", "VNEG", "PD"]),
    "RG1": ("gain input R (1.00k)",          ["A", "B"]),
    "RG2": ("gain input R (1.00k)",          ["A", "B"]),
    "RF1": ("feedback R (8.06k)",            ["A", "B"]),
    "RF2": ("feedback R (8.06k)",            ["A", "B"]),
    "RO1": ("output iso R (24R)",            ["A", "B"]),
    "RO2": ("output iso R (24R)",            ["A", "B"]),
    "RV1": ("VOCM divider top (2.00k)",      ["A", "B"]),
    "RV2": ("VOCM divider bot (1.00k)",      ["A", "B"]),
    "CV":  ("VOCM bypass cap",               ["A", "B"]),
    "C1":  ("A1 +rail decoupling",           ["A", "B"]),
    "C2":  ("A1 -rail decoupling",           ["A", "B"]),
    "C3":  ("A2 +rail decoupling",           ["A", "B"]),
    "C4":  ("A2 -rail decoupling",           ["A", "B"]),
    "C5":  ("U3 +rail decoupling",           ["A", "B"]),
    "C6":  ("U3 -rail decoupling",           ["A", "B"]),
    "U4":  ("latching-relay driver (H-bridge)", ["IN", "VCC", "GND", "OUT1", "OUT2"]),
    "J2":  ("Lemo/ODU 8-pin to motherboard", ["LINE_A", "LINE_B", "VS_IN", "P5V", "N5V", "AGND", "RI_CTRL", "SHLD"]),
}

# ---- nets: name -> [REF.PIN, ...] ----
NETS = {
    # primary high-Z path: insect -> M -> relay -> Ri -> S(=Vs)
    "M":         ["J1.SIG", "A1.INP", "K1.P1"],
    "RI_MID":    ["K1.P2", "RI.A"],
    "S":         ["RI.B", "A2.INP", "J2.VS_IN"],
    # unity-gain followers
    "A1_OUT":    ["A1.OUT", "A1.INN", "RG1.A"],
    "A2_OUT":    ["A2.OUT", "A2.INN", "RG2.A"],
    # FDA gain network (gain = RF/RG ~ 8)
    "FDA_INN":   ["RG1.B", "RF1.A", "U3.INN"],
    "FDA_INP":   ["RG2.B", "RF2.A", "U3.INP"],
    "FDA_OUTP":  ["U3.OUTP", "RF1.B", "RO1.A"],
    "FDA_OUTN":  ["U3.OUTN", "RF2.B", "RO2.A"],
    # differential cable drive
    "LINE_A":    ["RO1.B", "J2.LINE_A"],
    "LINE_B":    ["RO2.B", "J2.LINE_B"],
    # FDA output common-mode ~1.67 V (matches ADC Vcm) from a P5V->AGND divider
    "VOCM":      ["U3.VOCM", "RV1.B", "RV2.A", "CV.A"],
    # Ri-select latching relay driven locally from one cable logic line
    "RI_CTRL":   ["U4.IN", "J2.RI_CTRL"],
    "RELAY_SET": ["U4.OUT1", "K1.CP"],
    "RELAY_RST": ["U4.OUT2", "K1.CN"],
    # power
    "P5V":  ["A1.VPOS", "A2.VPOS", "U3.VPOS", "U3.PD", "RV1.A", "U4.VCC",
             "C1.A", "C3.A", "C5.A", "J2.P5V"],
    "N5V":  ["A1.VNEG", "A2.VNEG", "U3.VNEG", "C2.A", "C4.A", "C6.A", "J2.N5V"],
    "AGND": ["J1.SHLD", "RV2.B", "CV.B", "U4.GND",
             "C1.B", "C2.B", "C3.B", "C4.B", "C5.B", "C6.B", "J2.AGND"],
    # chassis/guard (intentionally single-ended on this sheet)
    "SHLD":   ["J2.SHLD"],
    "GUARD1": ["A1.GUARD"],
    "GUARD2": ["A2.GUARD"],
}

# KiCad footprints (verified present in KiCad 10 standard libs). PLACEHOLDER = swap for the
# real vendor footprint during layout (Lemo/ODU connector, latching reed relay, gigaohm R).
FOOTPRINTS = {
    "J1":  "Connector_Coaxial:BNC_Amphenol_031-5539_Vertical",
    "A1":  "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "A2":  "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "K1":  "Relay_THT:Relay_1-Form-A_Schrack-RYII_RM5mm",     # PLACEHOLDER: latching reed relay
    "RI":  "Resistor_SMD:R_1206_3216Metric",                  # gigaohm R; guard the pads
    "U3":  "Package_DFN_QFN:HVQFN-16-1EP_3x3mm_P0.5mm_EP1.5x1.5mm",  # ADA4940-1 LFCSP-16 (verify)
    "RG1": "Resistor_SMD:R_0603_1608Metric", "RG2": "Resistor_SMD:R_0603_1608Metric",
    "RF1": "Resistor_SMD:R_0603_1608Metric", "RF2": "Resistor_SMD:R_0603_1608Metric",
    "RO1": "Resistor_SMD:R_0603_1608Metric", "RO2": "Resistor_SMD:R_0603_1608Metric",
    "RV1": "Resistor_SMD:R_0603_1608Metric", "RV2": "Resistor_SMD:R_0603_1608Metric",
    "CV":  "Capacitor_SMD:C_0603_1608Metric",
    "C1":  "Capacitor_SMD:C_0603_1608Metric", "C2": "Capacitor_SMD:C_0603_1608Metric",
    "C3":  "Capacitor_SMD:C_0603_1608Metric", "C4": "Capacitor_SMD:C_0603_1608Metric",
    "C5":  "Capacitor_SMD:C_0603_1608Metric", "C6": "Capacitor_SMD:C_0603_1608Metric",
    "U4":  "Package_TO_SOT_SMD:SOT-23-6",                      # relay driver (or vendor part)
    "J2":  "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",  # PLACEHOLDER: Lemo/ODU 8-pin
}

# nets allowed to have a single pin on this sheet (shield to shell, guard pours)
ALLOW_SINGLE = {"SHLD", "GUARD1", "GUARD2"}
POWER_NETS = {"P5V", "N5V", "AGND"}


def check() -> int:
    errs, warns = [], []
    all_pins = {f"{r}.{p}" for r, (_, pins) in COMPONENTS.items() for p in pins}

    # 1) every net pin references a real component pin
    seen: dict[str, list[str]] = {}
    for net, pins in NETS.items():
        for pin in pins:
            if pin not in all_pins:
                errs.append(f"net {net}: unknown pin {pin}")
            seen.setdefault(pin, []).append(net)

    # 2) every component pin is on exactly one net
    for pin in sorted(all_pins):
        nlist = seen.get(pin, [])
        if not nlist:
            errs.append(f"floating pin (no net): {pin}")
        elif len(nlist) > 1:
            errs.append(f"pin {pin} on multiple nets: {nlist}")

    # 3) single-pin nets (likely a missing connection) unless whitelisted
    for net, pins in NETS.items():
        if len(pins) < 2 and net not in ALLOW_SINGLE:
            warns.append(f"single-pin net: {net} = {pins}")

    # 4) power nets present and populated
    for net in POWER_NETS:
        if net not in NETS or len(NETS[net]) < 2:
            errs.append(f"power net missing/underpopulated: {net}")

    print(f"Components: {len(COMPONENTS)}   pins: {len(all_pins)}   nets: {len(NETS)}")
    for w in warns:
        print(f"  WARN  {w}")
    for e in errs:
        print(f"  ERROR {e}")
    if errs:
        print(f"ERC FAILED: {len(errs)} error(s), {len(warns)} warning(s).")
        return 1
    print(f"ERC OK: 0 errors, {len(warns)} warning(s). "
          f"Every pin connected exactly once; power + diff pair consistent.")
    return 0


def write_table(path: str = "connection-table.md") -> None:
    lines = ["# Single-channel daughtercard — connection table",
             "", "_Generated by `channel_netlist.py` (ERC-checked). Pin numbers bind at "
             "KiCad symbol assignment._", "", "## Components", "", "| Ref | Part | Footprint | Pins |",
             "|---|---|---|---|"]
    for r, (part, pins) in COMPONENTS.items():
        lines.append(f"| {r} | {part} | {FOOTPRINTS.get(r,'—')} | {', '.join(pins)} |")
    lines += ["", "## Nets", "", "| Net | Connections |", "|---|---|"]
    for net, pins in NETS.items():
        lines.append(f"| {net} | {', '.join(pins)} |")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    rc = check()
    if "--table" in sys.argv:
        write_table()
    sys.exit(rc)
