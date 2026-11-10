"""Generate the single line diagram (SLD) for the 415 V LT distribution system
with a 45 kVA DG set and changeover switch.

Outputs (same base name):
  .dxf  AutoCAD-ready drawing: named layers (SLD-*), reusable blocks (breaker, RCCB,
        meter, generator ...), text styles, A3 paper-space layout, millimetre units
  .png  preview image
  .pdf  A3 landscape print

Usage:  python generate_sld.py [output_dir] [base_name]
        (defaults: ./output  415V_LT_Distribution_SLD)

All ratings and loads are ASSUMED values - edit the `feeders` list to suit.

Author: Suvadeep Mallik
"""
import math
import os
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

OUT = sys.argv[1] if len(sys.argv) > 1 else "output"
BASE = sys.argv[2] if len(sys.argv) > 2 else "415V_LT_Distribution_SLD"
os.makedirs(OUT, exist_ok=True)

# layer key -> (matplotlib colour, DXF ACI colour, line weight in mm)
# In the DXF every layer is named "SLD-" + key.
LAYERS = {
    "BORDER": ("#000000", 7, 0.50),
    "TITLEBLOCK": ("#000000", 7, 0.50),
    "BUS": ("#000000", 7, 1.20),
    "WIRE": ("#000000", 7, 0.35),
    "SYMBOL": ("#000000", 7, 0.30),
    "EARTH": ("#1a7f37", 3, 0.40),
    "TABLE": ("#000000", 7, 0.30),
    "TEXT": ("#000000", 7, 0.18),
}

P = []  # drawing primitives (model space)


def line(x1, y1, x2, y2, layer="WIRE"):
    P.append(("line", x1, y1, x2, y2, layer))


def rect(x, y, w, h, layer="SYMBOL"):
    P.append(("rect", x, y, w, h, layer))


def circ(x, y, r, layer="SYMBOL"):
    P.append(("circ", x, y, r, layer))


def txt(x, y, s, h=2.2, al="c", layer="TEXT", bold=False):
    P.append(("txt", x, y, s, h, al, layer, bold))


def ins(name, x, y, s=1.0):
    """Insert a block (symbol) at x, y with uniform scale s."""
    P.append(("ins", name, x, y, s))


# ------------------------------------------------------------ block (symbol) library
# Geometry is in local coordinates, insertion point = (0, 0).
BLOCKS = {
    # circuit breaker (MCB / MCCB): open blade with a cross at the top contact
    "BREAKER": [
        ("line", 0, 8, 0, 4, "SYMBOL"),
        ("line", 0, -4, 3.5, 3.5, "SYMBOL"),
        ("line", 0, -4, 0, -8, "SYMBOL"),
        ("line", -1.6, 2.4, 1.6, 5.6, "SYMBOL"),
        ("line", -1.6, 5.6, 1.6, 2.4, "SYMBOL"),
    ],
    # four slashes = 3 phases + neutral (insertion point = lowest slash)
    "PHASE4": [("line", -1.8, i * 1.8 - 1.0, 1.8, i * 1.8 + 1.0, "WIRE") for i in range(4)],
    "RCCB": [("rect", -7, -4, 14, 8, "SYMBOL"), ("txt", 0, 0, "RCCB", 2.0, "c", "TEXT", False)],
    "DOL": [("rect", -7, -4, 14, 8, "SYMBOL"), ("txt", 0, 0, "DOL", 2.0, "c", "TEXT", False)],
    "KWH_METER": [("circ", 0, 0, 6, "SYMBOL"), ("txt", 0, 0, "kWh", 2.2, "c", "TEXT", False)],
    "SOURCE_AC": [("circ", 0, 0, 7, "SYMBOL"), ("txt", 0, 0, "~", 6, "c", "TEXT", False)],
    "GENERATOR": [("circ", 0, 0, 7, "SYMBOL"), ("txt", 0, 0, "G", 5, "c", "TEXT", False)],
    "EARTH_SYMBOL": [
        ("line", -4, 0, 4, 0, "EARTH"),
        ("line", -2.5, -2, 2.5, -2, "EARTH"),
        ("line", -1, -4, 1, -4, "EARTH"),
    ],
}


def flatten(prims):
    """Expand block inserts into plain primitives (used for the PNG / PDF)."""
    out = []
    for p in prims:
        if p[0] != "ins":
            out.append(p)
            continue
        _, name, x, y, s = p
        for q in BLOCKS[name]:
            k = q[0]
            if k == "line":
                out.append(("line", x + s * q[1], y + s * q[2], x + s * q[3], y + s * q[4], q[5]))
            elif k == "rect":
                out.append(("rect", x + s * q[1], y + s * q[2], s * q[3], s * q[4], q[5]))
            elif k == "circ":
                out.append(("circ", x + s * q[1], y + s * q[2], s * q[3], q[4]))
            elif k == "txt":
                out.append(("txt", x + s * q[1], y + s * q[2], q[3], q[4] * s, q[5], q[6], q[7]))
    return out


# ---------------------------------------------------------------- data
SQ3 = math.sqrt(3)
V = 415
PF = 0.9


def amps(kw):
    return kw * 1000 / (SQ3 * V * PF)


feeders = [
    dict(tag="F1", brk=("MCB 25A, 4P", "(3P+N)"), rccb=("RCCB 40A", "30 mA, 4P"),
         box=("LIGHTING & FAN", "DB-1"), kw=6.0, cable="4C x 4 sq.mm Cu"),
    dict(tag="F2", brk=("MCB 32A, 4P", "(3P+N)"), rccb=("RCCB 40A", "30 mA, 4P"),
         box=("POWER SOCKET", "DB-2"), kw=10.0, cable="4C x 6 sq.mm Cu"),
    dict(tag="F3", brk=("MCB 40A, 4P", "(3P+N)"),
         box=("AIR CONDITIONING", "DB-3"), kw=18.0, cable="4C x 10 sq.mm Cu"),
    dict(tag="F4", brk=("MCCB 32A, TPN", "(MOTOR FEEDER)"), dol=True,
         box=("PUMP MOTOR", "10 HP, 3-PH"), kw=7.5, flc="~14", cable="4C x 4 sq.mm Cu"),
    dict(tag="F5", brk=("MCB 16A, 4P", "(3P+N)"),
         box=("OFFICE / UPS", "DB-5"), kw=5.0, cable="4C x 4 sq.mm Cu"),
    dict(tag="F6", brk=("MCB 32A, 4P", "(SPARE)"),
         box=("SPARE", "(FUTURE)"), kw=None, cable="CABLE AS REQUIRED"),
]
conn = sum(f["kw"] for f in feeders if f["kw"])
DF = 0.7
md_kw = conn * DF
md_kva = md_kw / PF
md_a = md_kva * 1000 / (SQ3 * V)
dg_kva = 45
dg_a = dg_kva * 1000 / (SQ3 * V)

# ---------------------------------------------------------------- frame
rect(5, 5, 410, 287, "BORDER")
txt(210, 286.5, "415V LT DISTRIBUTION SYSTEM WITH 45 kVA DG CHANGEOVER", 4.5, "c", bold=True)
txt(210, 281.5, "SINGLE LINE DIAGRAM  -  REFERENCE DRAWING, ALL VALUES ASSUMED (SEE NOTES)", 2.4, "c")
txt(210, 276, "DRAWN BY SUVADEEP MALLIK", 2.4, "c", bold=True)

# ---------------------------------------------------------------- sources
SRC_Y = 260
# utility
ins("SOURCE_AC", 150, SRC_Y)
txt(150, 274, "UTILITY SUPPLY", 2.6, "c")
txt(150, 270.5, "415V, 3-PH, 4-W, 50Hz", 2.2, "c")
line(150, SRC_Y - 7, 150, 246)
ins("KWH_METER", 150, 240)
txt(157, 240, "ENERGY METER", 2.2, "l")
txt(157, 236.5, "(CT OPERATED)", 2.0, "l")
line(150, 234, 150, 230)
ins("BREAKER", 150, 222)
txt(156, 224.5, "MCCB 100A, TPN", 2.3, "l")
txt(156, 221, "(UTILITY INCOMER)", 2.0, "l")
line(150, 214, 150, 196)
ins("PHASE4", 150, 203)

# DG
ins("GENERATOR", 270, SRC_Y)
txt(270, 274, "DG SET 45 kVA", 2.6, "c")
txt(270, 270.5, "415V, 3-PH, 4-W, 50Hz", 2.2, "c")
line(270, SRC_Y - 7, 270, 230)
ins("BREAKER", 270, 222)
txt(276, 224.5, "MCCB 80A, TPN", 2.3, "l")
txt(276, 221, "(DG INCOMER)", 2.0, "l")
line(270, 214, 270, 196)
ins("PHASE4", 270, 203)

# changeover
rect(130, 180, 160, 16)
txt(210, 190.5, "4-POLE CHANGEOVER SWITCH / ATS - 100 A", 2.5, "c")
txt(210, 185.5, "(UTILITY <-> DG, MECHANICALLY INTERLOCKED)", 2.0, "c")

# main incomer
line(210, 180, 210, 168)
ins("PHASE4", 210, 172)
ins("BREAKER", 210, 160)
txt(216, 162.5, "MAIN MCCB 100A, TPN", 2.3, "l")
txt(216, 159, "(MAIN INCOMER)", 2.0, "l")
line(210, 152, 210, 140)
ins("PHASE4", 210, 143.5)

# ---------------------------------------------------------------- busbar
line(35, 140, 385, 140, "BUS")
txt(216, 147, "MAIN BUSBAR 125A, Cu, 3-PH 4-W (R-Y-B-N)", 2.2, "l")

# ---------------------------------------------------------------- feeders
for i, f in enumerate(feeders):
    x = 60 + 60 * i
    txt(x + 2.5, 142.8, f["tag"], 2.8, "l", bold=True)
    line(x, 140, x, 134)
    ins("BREAKER", x, 126)
    txt(x + 6, 128.5, f["brk"][0], 2.2, "l")
    txt(x + 6, 125, f["brk"][1], 1.9, "l")
    if "rccb" in f:
        line(x, 118, x, 114)
        ins("RCCB", x, 110)
        txt(x + 9, 111.5, f["rccb"][0], 2.0, "l")
        txt(x + 9, 108, f["rccb"][1], 1.9, "l")
        line(x, 106, x, 98)
    elif f.get("dol"):
        line(x, 118, x, 114)
        ins("DOL", x, 110)
        txt(x + 9, 111.5, "STARTER WITH", 1.9, "l")
        txt(x + 9, 108, "O/L RELAY", 1.9, "l")
        line(x, 106, x, 98)
    else:
        line(x, 118, x, 98)
    rect(x - 24, 82, 48, 16)
    txt(x, 92.5, f["box"][0], 2.3, "c")
    txt(x, 87.5, f["box"][1], 2.1, "c")
    if f["kw"]:
        cur = f.get("flc") or f"{amps(f['kw']):.1f}"
        txt(x, 77.5, f"{f['kw']:.1f} kW | {cur} A", 2.2, "c")
    else:
        txt(x, 77.5, "FUTURE PROVISION", 2.2, "c")
    txt(x, 73.5, f["cable"], 2.1, "c")

# ---------------------------------------------------------------- earthing
line(35, 66, 385, 66, "EARTH")
txt(37, 68.5, "EARTH BUS (CU/GI STRIP) - ALL DB ENCLOSURES & METAL PARTS BONDED", 2.0, "l")
line(35, 66, 35, 60, "EARTH")
ins("EARTH_SYMBOL", 35, 60)
txt(42, 58, "TO EARTH PIT (2 NOS.) - EARTHING AS PER IS 3043", 2.0, "l")

# ---------------------------------------------------------------- load summary
rect(15, 212, 100, 48, "TABLE")
txt(65, 255.5, "LOAD SUMMARY (ASSUMED)", 2.6, "c", bold=True)
summary = [
    f"CONNECTED LOAD : {conn:.1f} kW",
    f"DIVERSITY FACTOR : {DF}",
    f"MAX. DEMAND : ~{md_kw:.1f} kW",
    f"  = ~{md_kva:.0f} kVA / ~{md_a:.0f} A @ {PF} PF",
    f"DG SET : {dg_kva} kVA (~{dg_a:.0f} A RATED)",
    "MAIN MCCB / BUSBAR : 100 A / 125 A",
]
for j, s in enumerate(summary):
    txt(18, 249 - j * 5.5, s, 2.2, "l")

# ---------------------------------------------------------------- legend
rect(318, 196, 92, 68, "TABLE")
txt(364, 259.5, "LEGEND", 2.8, "c", bold=True)
ins("BREAKER", 326, 250, 0.5)
txt(338, 250, "MCB / MCCB (CIRCUIT BREAKER)", 2.1, "l")
ins("RCCB", 326, 241, 0.75)
txt(338, 241, "RCCB (30 mA EARTH LEAKAGE)", 2.1, "l")
ins("KWH_METER", 326, 232, 0.667)
txt(338, 232, "ENERGY METER (CT OPERATED)", 2.1, "l")
rect(320, 220, 12, 6)
txt(338, 223, "CHANGEOVER SWITCH / ATS", 2.1, "l")
ins("GENERATOR", 326, 214, 0.571)
txt(338, 214, "DG SET (GENERATOR)", 2.1, "l")
line(320, 205, 332, 205, "BUS")
txt(338, 205, "BUSBAR", 2.1, "l")

# ---------------------------------------------------------------- notes + title block
rect(5, 5, 250, 45, "TITLEBLOCK")
txt(10, 45, "NOTES:", 2.8, "l", bold=True)
notes = [
    "1. ALL RATINGS, LOADS AND CABLE SIZES ARE ASSUMED FOR A TYPICAL SMALL COMMERCIAL LOAD - REPLACE WITH ACTUAL VALUES.",
    "2. CABLES: 4-CORE Cu XLPE ARMOURED, INDICATIVE SIZES (DERATING / VOLTAGE DROP / FAULT LEVEL NOT CHECKED).",
    "3. UTILITY AND DG MUST NEVER BE PARALLELED - CHANGEOVER IS INTERLOCKED. N-E BONDING PER LOCAL CODE.",
    "4. RCCB 30 mA PROVIDED ON LIGHTING AND SOCKET CIRCUITS FOR PERSONNEL PROTECTION.",
    "5. REFERENCE DRAWING ONLY - VERIFY WITH A LICENSED ELECTRICAL ENGINEER BEFORE INSTALLATION.",
]
for j, s in enumerate(notes):
    txt(10, 40 - j * 5.5, s, 2.0, "l")

rect(255, 5, 160, 45, "TITLEBLOCK")
line(255, 30, 415, 30, "TITLEBLOCK")
line(255, 21, 415, 21, "TITLEBLOCK")
line(255, 13, 415, 13, "TITLEBLOCK")
line(335, 5, 335, 30, "TITLEBLOCK")
txt(335, 41.5, "SINGLE LINE DIAGRAM", 5, "c", bold=True)
txt(335, 34, "415V LT DISTRIBUTION SYSTEM WITH 45 kVA DG CHANGEOVER", 2.4, "c")
txt(258, 25.5, "DATE: 11-11-2026", 2.4, "l")
txt(338, 25.5, "SCALE: NTS", 2.4, "l")
txt(258, 17, "DRAWN BY: SUVADEEP MALLIK", 2.4, "l")
txt(338, 17, "CHECKED BY: ______________", 2.4, "l")
txt(258, 9, "SHEET: 1 OF 1", 2.4, "l")
txt(338, 9, "REV: A", 2.4, "l")

# ================================================================ DXF (AutoCAD)
doc = ezdxf.new("R2010", setup=True)
doc.units = ezdxf.units.MM
doc.header["$MEASUREMENT"] = 1
doc.header["$LWDISPLAY"] = 1
doc.header["$LTSCALE"] = 1.0
doc.header["$PROJECTNAME"] = "415V-LT-Distribution-with-DG"
doc.header["$EXTMIN"] = (5, 5, 0)
doc.header["$EXTMAX"] = (415, 292, 0)
doc.header["$LIMMIN"] = (0, 0)
doc.header["$LIMMAX"] = (420, 297)

doc.styles.add("SLD", font="arial.ttf")
doc.styles.add("SLD-BOLD", font="arialbd.ttf")
for key, (_, aci, lw) in LAYERS.items():
    doc.layers.add("SLD-" + key, color=aci, lineweight=int(round(lw * 100)), linetype="Continuous")

AL = {"l": TextEntityAlignment.MIDDLE_LEFT, "c": TextEntityAlignment.MIDDLE_CENTER,
      "r": TextEntityAlignment.MIDDLE_RIGHT}


def to_dxf(target, p):
    k = p[0]
    if k == "line":
        target.add_line((p[1], p[2]), (p[3], p[4]), dxfattribs={"layer": "SLD-" + p[5]})
    elif k == "rect":
        _, x, y, w, h, ly = p
        target.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True,
                              dxfattribs={"layer": "SLD-" + ly})
    elif k == "circ":
        target.add_circle((p[1], p[2]), p[3], dxfattribs={"layer": "SLD-" + p[4]})
    elif k == "txt":
        _, x, y, s, h, al, ly, bold = p
        t = target.add_text(s, height=h, dxfattribs={"layer": "SLD-" + ly,
                                                      "style": "SLD-BOLD" if bold else "SLD"})
        t.set_placement((x, y), align=AL[al])
    elif k == "ins":
        _, name, x, y, s = p
        target.add_blockref(name, (x, y), dxfattribs={"layer": "SLD-SYMBOL", "xscale": s,
                                                       "yscale": s, "zscale": s})


for name, prims in BLOCKS.items():
    blk = doc.blocks.new(name=name)
    for q in prims:
        to_dxf(blk, q)

msp = doc.modelspace()
for p in P:
    to_dxf(msp, p)

doc.set_modelspace_vport(height=300, center=(210, 148.5))

# A3 landscape layout with one full-sheet viewport at 1:1 (millimetres)
layout = doc.layout("Layout1")
layout.page_setup(size=(420, 297), margins=(0, 0, 0, 0), units="mm", offset=(0, 0),
                  rotation=0, scale=16, name="ISO_A3_(420.00_x_297.00_MM)", device="DWG To PDF.pc3")
layout.add_viewport(center=(210, 148.5), size=(420, 297), view_center_point=(210, 148.5),
                    view_height=297, status=1)
doc.layouts.rename("Layout1", "A3-SLD")

dxf_path = os.path.join(OUT, BASE + ".dxf")
doc.saveas(dxf_path)

# ================================================================ PNG / PDF
MM = 72 / 25.4
fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 420)
ax.set_ylim(0, 297)
ax.set_aspect("equal")
ax.axis("off")
HA = {"l": "left", "c": "center", "r": "right"}
for p in flatten(P):
    k = p[0]
    if k == "line":
        _, x1, y1, x2, y2, ly = p
        col, _, lw = LAYERS[ly]
        ax.plot([x1, x2], [y1, y2], color=col, lw=lw * MM, solid_capstyle="butt")
    elif k == "rect":
        _, x, y, w, h, ly = p
        col, _, lw = LAYERS[ly]
        ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=col, lw=lw * MM))
    elif k == "circ":
        _, x, y, r, ly = p
        col, _, lw = LAYERS[ly]
        ax.add_patch(Circle((x, y), r, fill=False, ec=col, lw=lw * MM))
    elif k == "txt":
        _, x, y, s, h, al, ly, bold = p
        ax.text(x, y, s, fontsize=h * 3.88, ha=HA[al], va="center", color=LAYERS[ly][0],
                fontweight="bold" if bold else "normal")
png_path = os.path.join(OUT, BASE + ".png")
pdf_path = os.path.join(OUT, BASE + ".pdf")
fig.savefig(png_path, dpi=200, facecolor="white")
fig.savefig(pdf_path, facecolor="white")
plt.close(fig)

print("model-space entities:", len(P), "| block definitions:", len(BLOCKS))
print("connected kW:", conn, "| max demand kW:", round(md_kw, 2), "| kVA:", round(md_kva, 1),
      "| A:", round(md_a, 1), "| DG rated A:", round(dg_a, 1))
print(dxf_path)
print(png_path)
print(pdf_path)
