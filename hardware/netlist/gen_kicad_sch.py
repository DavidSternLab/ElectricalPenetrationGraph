#!/usr/bin/env python3
"""Generate a KiCad schematic (.kicad_sch) from the ERC'd netlist (channel_netlist.py).

Strategy that's robust to auto-generation: each component becomes a labeled box symbol
(pins on left/right); connectivity is expressed with a global label of the net name on a
short wire stub at every pin. Net names matching = connection, so no wire routing is needed
and the result is whatever channel_netlist.py defines. Validate with:
    kicad-cli sch upgrade ... ; kicad-cli sch erc ... ; kicad-cli sch export svg ...

Boxes (not pretty op-amp glyphs) are intentional for a first machine-generated capture;
swap to library symbols + footprints during manual cleanup in KiCad.
"""
from __future__ import annotations
import uuid as _uuid
from channel_netlist import COMPONENTS, NETS, FOOTPRINTS

def U(): return str(_uuid.uuid4())

# pin -> net lookup
PIN_NET = {pin: net for net, pins in NETS.items() for pin in pins}

W = 7.62          # box half width (mm)
L = 2.54          # pin length
STUB = 5.08       # wire stub before the label
PITCH = 5.08      # vertical pin pitch
COLS = 4          # grid columns
DX, DY = 63.5, 76.2

def box_height(npins_side): return max(2, npins_side) * PITCH + PITCH

def split_pins(pins):
    half = (len(pins) + 1) // 2
    return pins[:half], pins[half:]   # left, right

def lib_symbol(ref, part, pins):
    left, right = split_pins(pins)
    h = box_height(max(len(left), len(right)))
    top = h / 2
    s = [f'    (symbol "epg:{ref}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes)']
    s.append(f'      (property "Reference" "{ref}" (at 0 {top+2.5:.2f} 0) (effects (font (size 1.27 1.27))))')
    s.append(f'      (property "Value" "{part}" (at 0 {-top-2.5:.2f} 0) (effects (font (size 1.0 1.0))))')
    s.append(f'      (symbol "{ref}_1_1"')
    s.append(f'        (rectangle (start {-W:.2f} {top:.2f}) (end {W:.2f} {-top:.2f}) '
             f'(stroke (width 0.254) (type default)) (fill (type background)))')
    num = 1
    def emit_pin(name, x, y, ang):
        nonlocal num
        ln = (f'        (pin passive line (at {x:.2f} {y:.2f} {ang}) (length {L})\n'
              f'          (name "{name}" (effects (font (size 1.0 1.0))))\n'
              f'          (number "{num}" (effects (font (size 1.0 1.0)))))')
        num += 1
        return ln
    for i, name in enumerate(left):
        y = top - PITCH * (i + 1)
        s.append(emit_pin(name, -(W + L), y, 0))     # left pin, body to the right
    for i, name in enumerate(right):
        y = top - PITCH * (i + 1)
        s.append(emit_pin(name, (W + L), y, 180))    # right pin, body to the left
    s.append('      )')
    s.append('    )')
    return "\n".join(s), left, right, h

def main():
    sheet_uuid = U()
    out = ['(kicad_sch (version 20231120) (generator "epg_gen") (generator_version "8.0")',
           f'  (uuid "{sheet_uuid}")', '  (paper "A2")', '  (lib_symbols']
    geom = {}
    for ref, (part, pins) in COMPONENTS.items():
        sym, left, right, h = lib_symbol(ref, part, pins)
        out.append(sym)
        geom[ref] = (left, right, h)
    out.append('  )')

    wires, labels, insts = [], [], []
    refs = list(COMPONENTS)
    for idx, ref in enumerate(refs):
        col, row = idx % COLS, idx // COLS
        X, Y = 50.8 + col * DX, 50.8 + row * DY   # 50.8 = 40*1.27 keeps all pins on grid
        left, right, h = geom[ref]
        top = h / 2
        insts.append(
            f'  (symbol (lib_id "epg:{ref}") (at {X:.2f} {Y:.2f} 0) (unit 1)\n'
            f'    (in_bom yes) (on_board yes) (dnp no) (uuid "{U()}")\n'
            f'    (property "Reference" "{ref}" (at {X:.2f} {Y-top-2.5:.2f} 0) (effects (font (size 1.27 1.27))))\n'
            f'    (property "Value" "{COMPONENTS[ref][0]}" (at {X:.2f} {Y+top+2.5:.2f} 0) (effects (font (size 1.0 1.0))))\n'
            f'    (property "Footprint" "{FOOTPRINTS.get(ref, "")}" (at {X:.2f} {Y:.2f} 0) (effects (font (size 1.0 1.0)) (hide yes)))\n'
            f'    (instances (project "epg" (path "/{sheet_uuid}" (reference "{ref}") (unit 1)))))')
        # place wires + global labels at each pin connection point (schematic Y is flipped)
        def place(name, side):
            i = (left if side == "L" else right).index(name)
            py = top - PITCH * (i + 1)
            ax = X + (-(W + L) if side == "L" else (W + L))
            ay = Y - py
            ox = ax + (-STUB if side == "L" else STUB)
            wires.append(f'  (wire (pts (xy {ax:.2f} {ay:.2f}) (xy {ox:.2f} {ay:.2f})) '
                         f'(stroke (width 0) (type default)) (uuid "{U()}"))')
            net = PIN_NET[f"{ref}.{name}"]
            just = "right" if side == "L" else "left"
            ang = 180 if side == "L" else 0
            labels.append(f'  (global_label "{net}" (shape bidirectional) (at {ox:.2f} {ay:.2f} {ang}) '
                          f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid "{U()}"))')
        for nm in left:  place(nm, "L")
        for nm in right: place(nm, "R")

    out += insts + wires + labels
    out.append(')')
    open("single_channel.kicad_sch", "w").write("\n".join(out) + "\n")
    print(f"wrote single_channel.kicad_sch  ({len(COMPONENTS)} symbols, "
          f"{len(wires)} pins, {len(set(NETS))} nets)")

if __name__ == "__main__":
    main()
