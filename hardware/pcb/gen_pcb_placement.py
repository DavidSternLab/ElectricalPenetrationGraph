#!/usr/bin/env python3
"""Generate a STARTING PCB (footprints placed + outline + 4-layer stackup) for the
single-channel daughtercard, using KiCad's pcbnew API.

Run with KiCad's bundled Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 \
      gen_pcb_placement.py

This is a HAND-OFF artifact for the layout engineer: parts are pre-placed with
electrometer-aware intent (input cluster tight around the BNC; output/Lemo at the far
edge), the board outline + layer count are set. Nets/ratsnest come from "Update PCB from
Schematic" (the schematic carries footprints); ROUTING + guard ring are done by hand per
pcb-layout.md. No autorouting — layout IS the design for an fA front end.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "netlist"))
import pcbnew  # noqa: E402  (provided by KiCad's python)
from channel_netlist import COMPONENTS, FOOTPRINTS  # noqa: E402

FP_BASE = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
BOARD_W, BOARD_H = 60.0, 40.0
OUT = os.path.join(os.path.dirname(__file__), "single_channel.kicad_pcb")

# electrometer-aware placement (mm). Input cluster (J1,A1,K1,RI,A2) tight on the left;
# FDA + gain network centre; Lemo (J2) + relay driver on the right (output/digital-ish).
PLACE = {
    "J1": (8, 20), "A1": (20, 20), "K1": (20, 32), "RI": (30, 20), "A2": (30, 32),
    "U3": (42, 18), "RG1": (36, 12), "RG2": (36, 24), "RF1": (47, 10), "RF2": (47, 26),
    "RO1": (51, 15), "RO2": (51, 19), "RV1": (40, 31), "RV2": (40, 36), "CV": (46, 33),
    "C1": (15, 12), "C2": (15, 28), "C3": (25, 38), "C4": (34, 38), "C5": (46, 6),
    "C6": (51, 6), "U4": (55, 32), "J2": (57, 20),
}


def frommm(v):
    return pcbnew.FromMM(v)


def add_outline(board):
    pts = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H), (0, 0)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pcbnew.VECTOR2I(frommm(x1), frommm(y1)))
        seg.SetEnd(pcbnew.VECTOR2I(frommm(x2), frommm(y2)))
        seg.SetWidth(frommm(0.15))
        board.Add(seg)


def main():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    add_outline(board)

    placed, failed = 0, []
    for ref in COMPONENTS:
        libnick, name = FOOTPRINTS[ref].split(":")
        libdir = os.path.join(FP_BASE, libnick + ".pretty")
        try:
            fp = pcbnew.FootprintLoad(libdir, name)
        except Exception as e:  # noqa: BLE001
            fp = None
            print(f"  load error {ref} {FOOTPRINTS[ref]}: {e}")
        if fp is None:
            failed.append(ref)
            continue
        fp.SetReference(ref)
        x, y = PLACE.get(ref, (5, 5))
        fp.SetPosition(pcbnew.VECTOR2I(frommm(x), frommm(y)))
        board.Add(fp)
        placed += 1

    pcbnew.SaveBoard(OUT, board)
    print(f"placed {placed}/{len(COMPONENTS)} footprints, board {BOARD_W}x{BOARD_H} mm, "
          f"4 layers -> {os.path.basename(OUT)}")
    if failed:
        print(f"  FAILED to load: {failed}")


if __name__ == "__main__":
    main()
