#!/usr/bin/env python3
"""Conservative town/overworld rendering pass after the voxel room-edge fixes.

The native bottom map and collision define walkable ground.  A purely visual
top map on such a tile must not be promoted to a 16-pixel flying platform.
The out-of-room ground skirt uses *local boundary* floor art, not the globally
most common walkable tile (which can be the town plaza).
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "upstream" / "tmc" / "port" / "port_voxel.cpp"
src = path.read_text(encoding="utf-8")


def replace_one(old: str, new: str):
    global src
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"voxel town fidelity: expected 1 anchor, got {count}: {old[:100]!r}")
    src = src.replace(old, new, 1)


# In pass 2, kind==0 is native floor. All its BG layers must remain on the
# same floor plane. Structural roof/canopy meshes are emitted by solid runs,
# not by arbitrary fully opaque pixels of a walkable floor BG.
old_floor = """                    } else if (!outdoors || coverPixels[t] <= 24) {
                        // Interior details keep native floor placement. Real
                        // furniture/wall tops already belong to solid runs.
                        flatL(true, x, x, y, d + kSurfaceEpsilon,
                              y * 16.0f, y * 16.0f + 16, 0);
                    } else {
                        int clear = 0;
                        for (int i = 0; i < 256; i += 3)
                            clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                        if (clear >= 4)
                            flatL(true, x, x, y, d + kSurfaceEpsilon, y * 16.0f, y * 16.0f + 16, 0);
                        else
                            flatL(true, x, x, y, kTopLayerLift,
                                  y * 16.0f + kTopLayerLift, y * 16.0f + 16 + kTopLayerLift, 0);
                    }"""
new_floor = """                    } else {
                        /*
                         * The native collision says this is walkable floor.
                         * Opaque top-map plaza/path/decor tiles are not roofs:
                         * the old opacity heuristic floated them by 16px,
                         * making the town square a giant false platform.
                         * True roofs and supported canopy overhangs are
                         * handled by the separate solid/absorbed run pass.
                         */
                        flatL(true, x, x, y, d + kSurfaceEpsilon,
                              y * 16.0f, y * 16.0f + 16, 0);
                    }"""
replace_one(old_floor, new_floor)

old_skirt = """    constexpr int kGroundMargin = 40;
    if (outdoors && groundX >= 0 && groundY >= 0) {
        for (int y = -kGroundMargin; y < H + kGroundMargin; ++y)
            for (int x = -kGroundMargin; x < W + kGroundMargin; ++x) {
                if (inRoom(x, y))
                    continue;
                flatL(false, x, groundX, groundY, 0.0f,
                      y * 16.0f, y * 16.0f + 16.0f, 0);
            }
    }"""
new_skirt = """    constexpr int kGroundMargin = 40;
    if (outdoors && groundX >= 0 && groundY >= 0) {
        struct GroundArt { int x, y; };
        // The modal floor tile can be the beige town plaza; using it for
        // the entire perspective skirt draws huge beige plains beyond the
        // town. Instead locate a real, walkable, uncovered floor near each
        // corresponding boundary point, falling back to the modal floor only
        // when a boundary genuinely has no exposed floor.
        auto skirtFloor = [&](int sx, int sy) {
            if (!inRoom(sx, sy))
                return false;
            const int t = sy * 64 + sx;
            return !solid[t] && !Geom(sx, sy) && !Cover(sx, sy) &&
                   SinkDepth(sx, sy) == 0.0f;
        };
        auto boundaryFloor = [&](int edge, int coord) -> GroundArt {
            const bool vertical = edge >= 2;
            const int along = vertical ? H : W;
            const int inward = vertical ? W : H;
            const int a = std::clamp(coord, 0, along - 1);
            // Search along the actual border first, then a narrow inner
            // band. Never take art from a collision wall or a raised roof.
            for (int depth = 0; depth < std::min(12, inward); ++depth)
                for (int offset = 0; offset <= 6; ++offset)
                    for (int sign = -1; sign <= 1; sign += 2) {
                        if (offset == 0 && sign == 1)
                            continue;
                        const int b = a + offset * sign;
                        if (b < 0 || b >= along)
                            continue;
                        const int px = vertical ? (edge == 2 ? depth : W - 1 - depth) : b;
                        const int py = vertical ? b : (edge == 0 ? depth : H - 1 - depth);
                        if (skirtFloor(px, py))
                            return {px, py};
                    }
            return {groundX, groundY};
        };
        GroundArt topSource[64], bottomSource[64], leftSource[64], rightSource[64];
        for (int x = 0; x < W; ++x) {
            topSource[x] = boundaryFloor(0, x);
            bottomSource[x] = boundaryFloor(1, x);
        }
        for (int y = 0; y < H; ++y) {
            leftSource[y] = boundaryFloor(2, y);
            rightSource[y] = boundaryFloor(3, y);
        }
        for (int y = -kGroundMargin; y < H + kGroundMargin; ++y)
            for (int x = -kGroundMargin; x < W + kGroundMargin; ++x) {
                if (inRoom(x, y))
                    continue;
                const int ax = std::clamp(x, 0, W - 1);
                const int ay = std::clamp(y, 0, H - 1);
                const int dx = x < 0 ? -x : (x >= W ? x - W + 1 : 0);
                const int dy = y < 0 ? -y : (y >= H ? y - H + 1 : 0);
                const GroundArt ground = dx > dy
                    ? (x < 0 ? leftSource[ay] : rightSource[ay])
                    : (y < 0 ? topSource[ax] : bottomSource[ax]);
                flatL(false, x, ground.x, ground.y, 0.0f,
                      y * 16.0f, y * 16.0f + 16.0f, 0);
            }
    }"""
replace_one(old_skirt, new_skirt)
path.write_text(src, encoding="utf-8")
print("Town/overworld: grounded native floor overlays and boundary-matched distant ground")
