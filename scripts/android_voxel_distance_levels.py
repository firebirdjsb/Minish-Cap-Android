#!/usr/bin/env python3
"""Final 3D quality pass: deeper terrain, automatic geometry heights, doorway validation.

Runs on the *prepared upstream* after scene_fix, room_edges and town_fidelity.
Keeps the 2D renderer and native collision unchanged. Every code anchor is
asserted so a partial transform never silently ships to Android.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
voxel = root / "upstream/tmc/port/port_voxel.cpp"
view = voxel.read_text(encoding="utf-8")


def replace_one(old: str, new: str):
    global view
    count = view.count(old)
    if count != 1:
        raise SystemExit(f"3D depth pass: {count} source anchors: {old[:110]!r}")
    view = view.replace(old, new, 1)


# Mobile memory: 64 tiles around each room (was 40); 64x64 room plus skirt
# fits within the bounded map-vertex staging arrays. The GPU frustum culls
# invisible patches. Raised geometry stays room-local.
replace_one(
    "constexpr int kMaxMapVerts = (64 * 64 * 12 + 144 * 144 * 2) * 6;",
    "constexpr int kMaxMapVerts = (64 * 64 * 12 + 192 * 192 * 2) * 6;",
)
replace_one("    constexpr int kGroundMargin = 40;", "    constexpr int kGroundMargin = 64;")

# User-adjusted global wall heights create broken rooftops in other areas.
# Leave the default one tile, automatically promote *only* real continuous
# native collision-backed multi-row structures inside BuildMap.
replace_one(
    "    const int wallTiles = sBuildShapes ? sBuildShapes->wall : kDefaultWallTiles;",
    "    const int wallTiles = kDefaultWallTiles; /* intrinsic, not user-configurable */",
)
replace_one(
    "            rn.face = std::min(len, wallTiles);",
    """            // Native collision topology controls internal wall level count.
            // Single props and small scenery stay one tile high. Wider,
            // genuinely connected structures can have two or three tile
            // height bands without a user-visible height selector.
            int adjacentRuns = 0;
            if (len >= 3 && solid[yb * 64 + x]) {
                for (int dx : {-1, 1}) {
                    if (!inRoom(x + dx, yb) || yb - 2 < yt)
                        continue;
                    bool continued = true;
                    for (int row = yb - 2; row <= yb; ++row)
                        continued &= solid[row * 64 + x + dx] != 0;
                    if (continued)
                        ++adjacentRuns;
                }
            }
            int nativeFaceTiles = wallTiles;
            if (adjacentRuns >= 1 && len >= 3)
                nativeFaceTiles = 2;
            if (adjacentRuns == 2 && len >= 5)
                nativeFaceTiles = 3;
            rn.face = std::min(len, nativeFaceTiles);""",
)

# False-positive north "arches" on patterned walls are a known source of
# flipped symbols. Real top exits need a native passage trigger immediately
# beyond the arch. Do not reinterpret ordinary art-only differences.
replace_one(
    """            if (arch)
                northDoorColumns[x - 1] = northDoorColumns[x] = northDoorColumns[x + 1] = true;""",
    """            const u8 passage = gMapBottom.collisionData[2 * 64 + x];
            if (arch && (passage == 0x27 || passage == 0x23))
                northDoorColumns[x - 1] = northDoorColumns[x] = northDoorColumns[x + 1] = true;""",
)
replace_one(
    """        // A side-boundary opening, or its immediately adjacent jamb. Solid
        // frame tiles also need this treatment, not only walkable overhang.
        return !solid[y * 64 + x] ||
               !solid[(y - 1) * 64 + x] || !solid[(y + 1) * 64 + x];""",
    """        // Only genuine 0x23 side openings and their adjoining solid
        // jambs belong on a rotated doorway plane. Ordinary decorative
        // upper-wall art previously appeared as cryptic floating symbols.
        const int t = y * 64 + x;
        return sideOpening(x, y) ||
               (solid[t] && gMapBottom.collisionData[t] == 0x0f &&
                (sideOpening(x, y - 1) || sideOpening(x, y + 1)));""",
)

# A valid walkable perimeter floor may also have an opaque top BG used for
# pavement, flags, flowerbeds or Hyrule Castle stone detail. Sample BOTH
# layers of its actual local material in the scenery extension.
replace_one(
    """            return !solid[t] && !Geom(sx, sy) && !Cover(sx, sy) &&
                   SinkDepth(sx, sy) == 0.0f;""",
    """            return !solid[t] && !Geom(sx, sy) &&
                   SinkDepth(sx, sy) == 0.0f;""",
)

replace_one(
    """                const GroundArt ground = dx > dy
                    ? (x < 0 ? leftSource[ay] : rightSource[ay])
                    : (y < 0 ? topSource[ax] : bottomSource[ax]);
                flatL(false, x, ground.x, ground.y, 0.0f,
                      y * 16.0f, y * 16.0f + 16.0f, 0);""",
    """                // Reflect a narrow band of native floor art past each
                // border. This preserves local path/grass/stone patterns
                // instead of extending a single plain tile for 64 rows.
                // Never mirror a roof, cliff, wall or decorative overhang.
                auto reflect = [](int c, int size) {
                    constexpr int band = 8;
                    if (c < 0)
                        return std::min(size - 1, (-c - 1) % band);
                    if (c >= size)
                        return std::max(0, size - 1 - ((c - size) % band));
                    return c;
                };
                const int rx = reflect(x, W), ry = reflect(y, H);
                const GroundArt nearest = dx > dy
                    ? (x < 0 ? leftSource[ay] : rightSource[ay])
                    : (y < 0 ? topSource[ax] : bottomSource[ax]);
                const GroundArt ground = skirtFloor(rx, ry) ? GroundArt{rx, ry} : nearest;
                flatL(false, x, ground.x, ground.y, 0.0f,
                      y * 16.0f, y * 16.0f + 16.0f, 0);
                if (Cover(ground.x, ground.y))
                    flatL(true, x, ground.x, ground.y, kSurfaceEpsilon,
                          y * 16.0f, y * 16.0f + 16.0f, 0);""",
)
voxel.write_text(view, encoding="utf-8")

# 3D levels and shape classification are automatic. Keep view toggle and
# camera pitch control but no wall-height or per-tile user-editing controls.
display = root / "upstream/tmc/port/port_imgui_display_tab.inc"
ui = display.read_text(encoding="utf-8")
start = "        /* Phase-3 shape editor: fix what the height heuristic misreads, per"
end = '        StepperRow("Internal scale", "iscale",'
if ui.count(start) != 1 or ui.count(end) != 1:
    raise SystemExit("3D display controls have changed unexpectedly")
a = ui.index(start)
b = ui.index(end, a)
ui = ui[:a] + """        // Geometry height and classification are managed by the 3D view.
        // Users can still control the camera angle, but not scene levels.
        const int voxArea = Port_Config_GetVoxelView() ? Port_Voxel_CurrentArea() : -1;
        if (voxArea >= 0)
            StepperRow("3D camera angle", "voxpitch",
                       [](char* b, size_t n) -> const char* {
                           std::snprintf(b, n, "%d deg", Port_Config_GetVoxelPitch());
                           return b;
                       },
                       Port_Config_CycleVoxelPitch);

""" + ui[b:]
display.write_text(ui, encoding="utf-8")
print("Applied 64-tile view extension, native terrain BG materials, internal height inference and verified doorframe geometry")
