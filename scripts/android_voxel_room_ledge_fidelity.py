#!/usr/bin/env python3
"""Preserve native indoor room layering, small scenery and jump-off ledges.

Run LAST in prepare_android.sh, after the PR210 classification and heart passes.
The 2D renderer, player physics and PR219 OAM extensions are left untouched.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "upstream/tmc/port/port_voxel.cpp"
src = path.read_text(encoding="utf-8")


def checked(before: str, after: str):
    global src
    n = src.count(before)
    if n != 1:
        raise SystemExit(f"room/ledge fidelity: expected one anchor, got {n}: {before[:110]!r}")
    src = src.replace(before, after, 1)


# The game defines ACT_TILE_116 as SURFACE_EDGE (jump-off ledge).
# ACT_TILE_38/39 are walkable ground slopes. They are not vertical 3D
# walls, even if a heuristic / PR210 per-area override labels them "block".
checked(
    "bool SolidTile(int x, int y) {\n",
    """bool VoxelNativeJumpLedge(int t) {
    switch (gMapBottom.actTiles[t]) {
        case 116: /* ACT_TILE_116 -> SURFACE_EDGE */
        case 38:  /* ACT_TILE_38  -> SURFACE_SLOPE_GNDGND_V */
        case 39:  /* ACT_TILE_39  -> SURFACE_SLOPE_GNDGND_H */
            return true;
        default:
            return false;
    }
}

bool SolidTile(int x, int y) {
""")
checked(
    """    const int ov = TileOverride(t);
    if (ov != PORT_VOXEL_SHAPE_AUTO)
        return ov != PORT_VOXEL_SHAPE_FLOOR;
    if (gMapBottom.collisionData[t] != 0x0F)
        return false;""",
    """    // Never let an art-only classification change the topology of Link's
    // real collision map. This was turning walkable flowers/sticks, stairs
    // and ledge edges into huge green blocks after PR210.
    if (VoxelNativeJumpLedge(t) || gMapBottom.collisionData[t] != 0x0F)
        return false;
    const int ov = TileOverride(t);
    if (ov == PORT_VOXEL_SHAPE_FLOOR)
        return false;""")

# Some native edge cells have overhead artwork that gets absorbed into an
# adjacent solid column. Stop that absorption on a real jump/slope surface.
# Geometry should never be able to remove a valid native one-way jump.
checked(
    """        if (!geom[t])
            return false;""",
    """        if (!geom[t] || VoxelNativeJumpLedge(t))
            return false;""")

# Never accidentally convert a passable ledge into absorbed wall before the
# Geom() lambda is evaluated; this keeps its true floor material visible.
checked(
    """                if (geom[t] || !cover[t] || SinkDepth(x, y) != 0.0f)
                    continue;""",
    """                if (geom[t] || !cover[t] || VoxelNativeJumpLedge(t) ||
                    SinkDepth(x, y) != 0.0f)
                    continue;""")

# Native action tiles take priority over PR210 artistic guesses. Tiny bushes,
# cut grass and signs are sprites/cutouts, not opaque boxes even when their
# tileset has a curated block label. Large connected trees/cliffs remain
# structural, and all collision is still handled by the game.
checked(
    """        if (ov == PORT_VOXEL_SHAPE_FLOOR || ov == PORT_VOXEL_SHAPE_BLOCK || sPropCount >= kMaxProps || Cover(x, y))
            return false;""",
    """        const int type = BottomTileType(y * 64 + x);
        const bool nativeSmallScenery =
            type == 28 || type == 29 || type == 30 || type == 31 ||
            type == 85 || type == 118 || type == 119 || type == 374;
        if (ov == PORT_VOXEL_SHAPE_FLOOR || sPropCount >= kMaxProps || Cover(x, y))
            return false;
        if (ov == PORT_VOXEL_SHAPE_BLOCK && !nativeSmallScenery)
            return false;""")

# For curated props without an outline mask, preserve the native 2D art on
# the ground instead of displaying a solid cube. A successful mask stands as
# a sprite card; no gameplay collision is added or removed.
checked(
    """            if (!Geom(x, y)) {
                --y;
                continue;
            }
            if (isProp(x, y)) {""",
    """            if (!Geom(x, y)) {
                // A passable PR210 prop may have a standing sprite while its
                // native floor/collision remains perfectly walkable.
                if (!VoxelNativeJumpLedge(y * 64 + x) &&
                    TileOverride(y * 64 + x) == PORT_VOXEL_SHAPE_PROP &&
                    isProp(x, y)) {
                    kind[y * 64 + x] = 1;
                    propSlot[y * 64 + x] = (Uint32)sPropCount;
                }
                --y;
                continue;
            }
            if (isProp(x, y)) {""")

# Isolated explicitly-prop/native-small-scene tiles that cannot produce a
# silhouette must never fall back to a solid wall box.
checked(
    """            int yb = y;
            while (y >= 0 && Geom(x, y))
                --y;""",
    """            if (TileOverride(y * 64 + x) == PORT_VOXEL_SHAPE_PROP ||
                (BottomTileType(y * 64 + x) == 28 ||
                 BottomTileType(y * 64 + x) == 29 ||
                 BottomTileType(y * 64 + x) == 30 ||
                 BottomTileType(y * 64 + x) == 374)) {
                bool connected = false;
                for (int dx : {-1, 1})
                    connected |= Geom(x + dx, y);
                for (int dy : {-1, 1})
                    connected |= Geom(x, y + dy);
                if (!connected) {
                    // BuildPropMask failed; use faithful flat source artwork
                    // rather than inventing a vertical closed cube.
                    geom[y * 64 + x] = 0;
                    solid[y * 64 + x] = 0; /* visual only; native collision unmodified */
                    --y;
                    continue;
                }
            }
            int yb = y;
            while (y >= 0 && Geom(x, y))
                --y;""")

# A lower-priority indoor BG is a 2D underlay, not a physical floor 64px
# underground. Preserve its artwork beneath the main layer at the SAME
# native tile location; bottom BG transparency still determines visibility.
# This restores shelves/furniture/trim missing from rooms with two map BGs.
checked(
    """        constexpr float kBelow = 64.0f;
        for (int y = 0; y < H; ++y)
            for (int x = 0; x < W; ++x)
                if (!TopTileEmpty(x, y))
                    flatL(true, x, x, y, -kBelow, y * 16.0f - kBelow, y * 16.0f + 16 - kBelow, 0);""",
    """        constexpr float kBelow = 64.0f;
        for (int y = 0; y < H; ++y)
            for (int x = 0; x < W; ++x)
                if (!TopTileEmpty(x, y)) {
                    if (outdoors) {
                        // Existing exterior/overworld second-floor treatment
                        flatL(true, x, x, y, -kBelow,
                              y * 16.0f - kBelow, y * 16.0f + 16 - kBelow, 0);
                    } else {
                        // Indoor art priority: underlay same X/Z as native BG.
                        // A small negative epsilon prevents Z fighting without
                        // dropping the source art 64px into the void.
                        flatL(true, x, x, y, -kSurfaceEpsilon,
                              y * 16.0f, y * 16.0f + 16, 0);
                    }
                }""")

path.write_text(src, encoding="utf-8")
print("Native collision ledges stay flat; indoor underlays preserved; small plants and props avoid blocks")
