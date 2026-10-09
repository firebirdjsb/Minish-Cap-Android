#!/usr/bin/env python3
"""Fix scene ownership after PR #213: indoor facades, outlined props, overhead bridges.

Do not change native player collision, OAM visibility, HUD or 2D rendering.
The late pass deliberately acts on the final code resulting from the earlier
Android transformations, making earlier shared PR branches reusable.
"""
from pathlib import Path
srcpath=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
src=srcpath.read_text(encoding="utf-8")

def change(old,new):
    global src
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"final room/prop/bridge transform expected 1, got {n}: {old[:130]!r}")
    src=src.replace(old,new,1)

# Do not take an empty patch of carpet/paint on an indoor wall and reproject
# it onto the plane belonging to a *different* row or a jamb. Render true
# side-door opening at x=0/W-1 once; adjacent solid wall stays wallV/sideV.
# In the fully transformed renderer sideFrameArt is a short lambda.
# Match its END within the lambda, not the older source text's exact
# indentation; the earlier room and side-door passes may reformat it.
import re
p=src.index("    auto sideFrameArt = ")
q=src.index("\n    };",p)
chunk=src[p:q]
newChunk,n=re.subn(
    r"return\s+sideOpening\(x, y\)\s*\|\|.*?;",
    """return sideOpening(x, y);""",
    chunk, count=1, flags=re.S)
if n!=1:
    raise SystemExit("sideFrameArt source mismatch: "+repr(chunk[-450:]))
src=src[:p]+newChunk+src[q:]


# Only use the special side door draw for passable room openings, not
# already-generated solid wall/corner tiles. Those duplicated UV panels
# project a random character onto the side wall next to the proper door.
change(
    """            if (kind[y * 64 + x] != 0 && sideFrameArt(x, y))
                sideDoor(x, y, x >= W - 2, true);""",
    """            if (kind[y * 64 + x] != 0 && !solid[y * 64 + x] &&
                sideFrameArt(x, y))
                sideDoor(x, y, x >= W - 2, true);""")

# Common native house interiors encode their entire north facade in two
# successive rows, not a roof tile plus a wall face. Use BOTH native tile
# rows at the correct same plane (not a duplicate horizontal lid), including
# windows/forge shelving that straddle the two rows.
change(
    """        if (northFrame || southFrame) {
            for (int y = yt; y <= yb; ++y)""",
    """        const bool nearNorthDoor = northDoorColumns[x] ||
            (x > 0 && northDoorColumns[x-1]) ||
            (x+1 < W && northDoorColumns[x+1]);
        const bool northPerimeter = !outdoors && yt == 0 && yb == 1 &&
            !nearNorthDoor &&
            gMapBottom.collisionData[x] == 0x0f &&
            gMapBottom.collisionData[64 + x] == 0x0f;
        if (northFrame || southFrame || northPerimeter) {
            for (int y = yt; y <= yb; ++y)""")

# Per-pixel native outlines must be preserved. PR210's one-cell PROP tiles
# can have a top BG, e.g. indoor decorations and flags. Rejecting all Cover()
# tile art forced them through the opaque cube/extrusion path.
change(
    """        if (ov == PORT_VOXEL_SHAPE_FLOOR || sPropCount >= kMaxProps || Cover(x, y))
            return false;""",
    """        if (ov == PORT_VOXEL_SHAPE_FLOOR || sPropCount >= kMaxProps ||
            (Cover(x, y) && ov != PORT_VOXEL_SHAPE_PROP))
            return false;""")
change(
    """        if (!BuildPropMask(x, y, sPropCount, bChar, b8 != 0))
            return false;""",
    """        bool hasOutline = false;
        if (Cover(x, y) && ov == PORT_VOXEL_SHAPE_PROP)
            hasOutline = BuildMask([&](int px, int py) {
                return VisPixel(x, y, px, py);
            }, sPropCount);
        else
            hasOutline = BuildPropMask(x, y, sPropCount, bChar, b8 != 0);
        if (!hasOutline)
            return false;""")

# The previous span recognizer required a contiguous row of FULLY opaque
# overhead top tiles. Town bridge decks contain lamps, seams and translucent
# edge pixels and therefore frequently missed the check. Count coverage
# while still rejecting contiguous wide plaza BG regions and solid walls.
change(
    """if (!outdoors || !hasTop || !inRoom(x, y) || Cover(x, y) < 2)""",
    """if (!outdoors || !hasTop || !inRoom(x, y) || Cover(x, y) == 0)""")
change(
    """return cover[i] == 2 && !solid[i] && !geom[i] &&""",
    """return cover[i] != 0 && !solid[i] && !geom[i] &&""")
change(
    """        if (r-l+1 < 6) return false;""",
    """        if (r-l+1 < 5) return false;""")
change(
    """            if (n>=r-l) { // broad paving/roof, not a narrow passage
                const int thickness = row>y ? row-y+1 : y-row+1;
                if (thickness>=3) return false;
            }""",
    """            // A plaza is a wide 2D painted area. True elevated bridges
            // remain narrow across their full horizontal span.
            if (n>=r-l && std::abs(row-y)>=2) return false;""")

srcpath.write_text(src,encoding="utf-8")
print("Final renderer: native two-row north walls, door UV ownership, silhouette props and wider overhead bridge coverage")
