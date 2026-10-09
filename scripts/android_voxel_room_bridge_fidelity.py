#!/usr/bin/env python3
"""General native-layer fidelity for interiors, Hyrule Town and bridges.

Runs after all earlier Android 3D transforms. It fixes the systemic causes,
not hardcoded world coordinates: background priorities, doorway collision,
and whether an outdoor surface is a walkable floor or an overhead crossing.
2D mode and the game's native collision/AI remain unchanged.
"""
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
src=path.read_text(encoding="utf-8")

def patch(old, new):
    global src
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"native room/bridge fidelity: {n} anchors: {old[:110]!r}")
    src=src.replace(old,new,1)

# INDOORS: do not let the generic forest/canopy expansion absorb ordinary
# shelves, doorway trim and furniture from the upper BG into collision walls.
# This was losing furniture tiles and giving many rooms malformed top walls.
patch(
    """                if (geom[t] || !cover[t] || VoxelNativeJumpLedge(t) ||
                    SinkDepth(x, y) != 0.0f)
                    continue;""",
    """                // Outdoors canopies can overhang collision walls. Inside,
                // the tile maps are precise room art: absorbing their decor
                // into walls destroys bookshelves, furniture and trim.
                if (!outdoors || geom[t] || !cover[t] || VoxelNativeJumpLedge(t) ||
                    SinkDepth(x, y) != 0.0f)
                    continue;""")

# NORTH DOORS: the 3-column fake-arch conversion was rendering both rows
# of decorative collision tiles as glyph-bearing jambs. Keep the centre
# passage arch; the flanking wall columns follow normal native art rules.
patch(
    """            if (arch && (passage == 0x27 || passage == 0x23))
                northDoorColumns[x - 1] = northDoorColumns[x] = northDoorColumns[x + 1] = true;""",
    """            // Only the centre has a real passage. Reinterpreting both
            // adjacent art columns as 32px high doorway halves displayed
            // stray symbol/glyph strips beside the opening.
            if (arch && (passage == 0x27 || passage == 0x23) &&
                gMapBottom.collisionData[3 * 64 + x] != 0x0f)
                northDoorColumns[x] = true;""")

# Native side door jambs need two-column vertical art to preserve source
# orientation. Retain the established sideFrameArt topology; flattening only
# the passable centre breaks west/east room entrances and their tests.

# A bridge deck is a long, narrow top-map band spanning WALKABLE bottom
# tiles. Town ground, broad plaza overlays, houses and cliffs do not match.
# Infer from native BG occupancy + collision; no map coordinates or ROM IDs.
# Crucially: the player's native layer stays at ground Y=0, with the
# overhead deck at Y=32. Never raise the ground below the deck.
patch(
    """    auto Cover = [&](int x, int y) { return inRoom(x, y) ? cover[y * 64 + x] : 0; };""",
    """    auto Cover = [&](int x, int y) { return inRoom(x, y) ? cover[y * 64 + x] : 0; };
    // Bridges are visually overhead spans, not new native collision floors.
    // The thin/narrow test prevents broad top-BG plazas from floating.
    auto BridgeDeck = [&](int x, int y) -> bool {
        if (!outdoors || !hasTop || !inRoom(x, y) || Cover(x, y) < 2)
            return false;
        const int t = y * 64 + x;
        if (solid[t] || geom[t] || gMapBottom.collisionData[t] == 0x0f ||
            VoxelNativeJumpLedge(t) || SinkDepth(x, y) != 0.0f)
            return false;
        auto deckCandidate = [&](int ax, int ay) -> bool {
            if (!inRoom(ax, ay))
                return false;
            const int i = ay * 64 + ax;
            return cover[i] == 2 && !solid[i] && !geom[i] &&
                   gMapBottom.collisionData[i] != 0x0f &&
                   !VoxelNativeJumpLedge(i) && SinkDepth(ax, ay) == 0.0f;
        };
        // Only supported horizontal spans; vertical/wide fields are native
        // decorative floor tiles and must never become raised platforms.
        int l=x, r=x;
        while (l>0 && deckCandidate(l-1,y)) --l;
        while (r+1<W && deckCandidate(r+1,y)) ++r;
        if (r-l+1 < 6) return false;
        for (int row=y-2; row<=y+2; ++row) {
            if (row==y || row<0 || row>=H) continue;
            int n=0;
            for (int cx=l; cx<=r; ++cx)
                n+=deckCandidate(cx,row) ? 1 : 0;
            if (n>=r-l) { // broad paving/roof, not a narrow passage
                const int thickness = row>y ? row-y+1 : y-row+1;
                if (thickness>=3) return false;
            }
        }
        return true;
    };""")

# When copying ground from the nearby edge of town, never clone the
# elevated bridge/roof deck as ground just because its bottom map is walkable.
patch(
    """                if (Cover(ground.x, ground.y))
                    flatL(true, x, ground.x, ground.y, kSurfaceEpsilon,""",
    """                if (Cover(ground.x, ground.y) && !BridgeDeck(ground.x, ground.y))
                    flatL(true, x, ground.x, ground.y, kSurfaceEpsilon,""")

# Keep source art, floor and overhead deck separate, including depth tests.
# vParams.w bit30 is not used by map texel/mask/fill decoding. It identifies
# real overhead geometry for PR210: do not create a circular hole through
# a bridge when an entity passes below it.
patch(
    """    auto flatL = [&](bool top, int x, int ux, int uy, float h, float z0, float z1, Uint32 mask) {""",
    """    auto flatL = [&](bool top, int x, int ux, int uy, float h, float z0, float z1,
                     Uint32 mask, Uint32 geometryFlags = 0) {""")
patch(
    """             top ? 128u : 0u, top ? tChar : bChar, (top ? t8 : b8) | (mask << 8));""",
    """             top ? 128u : 0u, top ? tChar : bChar,
             (top ? t8 : b8) | (mask << 8) | geometryFlags);""")

patch(
    """                        flatL(true, x, x, y, d + kSurfaceEpsilon,
                              y * 16.0f, y * 16.0f + 16, 0);
                    }
                }
            }""",
    """                        if (BridgeDeck(x, y)) {
                            // Bridge is OVER Link. Keep its native top-map
                            // artwork at this exact room X/Z rather than
                            // sliding it south into the player's floor.
                            flatL(true, x, x, y, 32.0f,
                                  y * 16.0f, y * 16.0f + 16.0f, 0,
                                  0x40000000u);
                        } else {
                            flatL(true, x, x, y, d + kSurfaceEpsilon,
                                  y * 16.0f, y * 16.0f + 16, 0);
                        }
                    }
                }
            }""")

# General Hyrule ground: "most common tile" makes beige town plazas replace
# grass below unrelated scenery. Choose the NEAREST walkable native floor
# with the correct local bottom-BG material when a 1-tile neighbour is
# blocked, rather than a room-wide guessed modal tile.
patch(
    """        ux = groundX, uy = groundY;
        return groundX >= 0;""",
    """        // Nearby native material search is for outdoor town ground ONLY.
        // Indoors, the normal room ground source rule must not sample a side
        // door's bottom-map jamb tiles as walkable art (fake glyph floors).
        if (outdoors) {
            for (int radius = 2; radius <= 6; ++radius)
                for (int dy = -radius; dy <= radius; ++dy) {
                const int adx = radius - std::abs(dy);
                for (int sign : {-1, 1}) {
                    if (adx == 0 && sign < 0) continue;
                    const int nx = x + sign * adx, ny = y + dy;
                    if (inRoom(nx, ny) && !Geom(nx, ny) && !sideOpening(nx, ny) &&
                        Cover(nx, ny) < 2 && SinkDepth(nx, ny) == 0.0f &&
                        !BridgeDeck(nx, ny)) {
                        ux = nx; uy = ny;
                        return true;
                    }
                }
                }
        }
        ux = groundX, uy = groundY;
        return groundX >= 0;""")

path.write_text(src, encoding="utf-8")

# Bit30 tags authentic overhead span quads. The PR210 wall dither is for
# obstructing solid walls; perforating a bridge deck makes Link appear ON it
# and produces the large dark Bayer circle seen in Hyrule Town.
frag=Path(__file__).resolve().parents[1]/"upstream/tmc/port/shaders/voxel.frag"
shader=frag.read_text(encoding="utf-8")
anchor="""float roomFadeKeep() {
    if (uFadeCamera.w < 0.5) return 1.0;"""
if shader.count(anchor)!=1:
    raise SystemExit("bridge: PR210 shader dither anchor missing")
shader=shader.replace(anchor, """float roomFadeKeep() {
    // Link's native bottom collision layer is UNDER overhead BG2 bridges.
    // Preserve opaque depth occlusion: only actual walls can be dithered.
    if ((vParams.w & 0x40000000u) != 0u) return 1.0;
    if (uFadeCamera.w < 0.5) return 1.0;""", 1)
frag.write_text(shader, encoding="utf-8")

print("Native indoor BG/art preserved; doorway glyph columns unpromoted; overhead bridge and local Hyrule ground fixed")
