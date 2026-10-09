#!/usr/bin/env python3
"""Doorway art UV ownership and paired jamb height (all indoor rooms).

North door flank tiles may contain a GBA-only placeholder/glyph intended to be
hidden behind the door sprite. Stretching those two rows up a 3D wall repeats
the placeholder visibly. The jamb uses matching adjacent solid wall art while
its arch opening retains its OWN untouched native pixels.

Side doors are two consecutive 16px-wide source BG columns forming one
32px-high vertical frame. Previous repairs only emitted the passable middle
column, misaligning the upper half. Emit both columns once at the end of the
wall mesh with native opacity and original transform, on the correct side plane.
"""
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
s=path.read_text(encoding="utf-8")
def patch(a,b):
    global s
    c=s.count(a)
    if c!=1: raise SystemExit(f"indoor door plane expected 1 anchor ({c}): {a[:90]!r}")
    s=s.replace(a,b,1)

# Keep the geometry at x but give flanking *solid* jambs nearby plain wall UVs.
# The centre arch itself uses native art. Only rows 0/1 of real north doors.
a=s.index("    auto wallV = ")
b=s.index("    auto sideV =",a)
part=s[a:b]
old="""        const float x0 = x * 16.0f, x1 = x0 + 16;"""
assert part.count(old)==1
part=part.replace(old,
"""        const float x0 = x * 16.0f, x1 = x0 + 16;
        // Door bordering GBA tiles sometimes contain placeholder glyphs
        // hidden by a 2D doorway overlay. Map them to contiguous wall trim,
        // never onto the neighbouring door's arch or floor tile.
        int artX = x;
        if (!outdoors && y < 2 && x >= 2 && x + 2 < W) {
            if (northDoorColumns[x + 1] && !northDoorColumns[x])
                artX = x - 1;
            else if (northDoorColumns[x - 1] && !northDoorColumns[x])
                artX = x + 1;
        }
        const float tx0=artX*16.0f, tx1=tx0+16.0f;""",1)
old2="""x0, y * 16.0f, x1, y * 16.0f + 16"""
if part.count(old2)!=2:
    raise SystemExit("north-wall UV ownership changed: "+str(part.count(old2)))
part=part.replace(old2,"tx0, y * 16.0f, tx1, y * 16.0f + 16")
s=s[:a]+part+s[b:]

# The earlier pass drew only one source column (sometimes twice) while
# the other column stayed on the floor. Remove those incomplete drawings;
# the paired-door pass below is the one visual owner for BOTH halves.
patch("""            if (sideOpening(x, y)) {
                underlay(x, y);
                sideDoor(x, y, x >= W - 2, false);
                if (Cover(x, y))
                    sideDoor(x, y, x >= W - 2, true);
                continue;""",
"""            if (sideOpening(x, y)) {
                underlay(x, y); // native doorway remains passable
                continue;""")
patch("""    for (int y = 2; y < H - 2; ++y)
        for (int x = 0; x < W; ++x)
            if (kind[y * 64 + x] != 0 && !solid[y * 64 + x] &&
                sideFrameArt(x, y))
                sideDoor(x, y, x >= W - 2, true);""", "")

patch("""    sMapVertCount = n;
    sBuildShapes = nullptr;""",
"""    /* Side doorway visual 2D X columns become the two 3D vertical jamb
     * segments. Run AFTER ordinary wall geometry so no wall cap paints
     * over the top of the door; keep the collision opening itself open. */
    if (!outdoors && W >= 4) {
        for (int y=2; y<H-2; ++y) {
            if (sideOpening(0,y) || sideOpening(1,y)) {
                for (int x=0; x<2; ++x) {
                    sideDoor(x,y,false,false);
                    if (Cover(x,y)) sideDoor(x,y,false,true);
                }
            }
            if (sideOpening(W-2,y) || sideOpening(W-1,y)) {
                for (int x=W-2; x<W; ++x) {
                    sideDoor(x,y,true,false);
                    if (Cover(x,y)) sideDoor(x,y,true,true);
                }
            }
        }
    }
    sMapVertCount = n;
    sBuildShapes = nullptr;""")
path.write_text(s,encoding="utf-8")
print("Indoor north-door glyph UVs isolated and left/right door top jamb pairs aligned")
