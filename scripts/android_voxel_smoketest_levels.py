#!/usr/bin/env python3
from pathlib import Path

vox = Path("upstream/tmc/port/port_voxel.cpp")
src = vox.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Hidden internal 3D levels.
# 0 = ground, 1 = raised/cliff/wall top, 2 = overhead/roof visual.
# These are derived automatically and are deliberately not exposed in UI.
# ---------------------------------------------------------------------------
state_anchor = """static float sVoxelHeight[64 * 64] = {};
static int sVoxelHeightW = 0, sVoxelHeightH = 0;
static int sVoxelHeightArea = -1, sVoxelHeightRoom = -1;
static bool sVoxelHeightValid = false;
"""
state_repl = """static float sVoxelHeight[64 * 64] = {};
static Uint8 sVoxelLevel[64 * 64] = {};
static Uint8 sVoxelFrontFace[64 * 64] = {};
static int sVoxelHeightW = 0, sVoxelHeightH = 0;
static int sVoxelHeightArea = -1, sVoxelHeightRoom = -1;
static bool sVoxelHeightValid = false;

enum : Uint8 {
    VOXEL_LEVEL_GROUND = 0,
    VOXEL_LEVEL_RAISED = 1,
    VOXEL_LEVEL_OVERHEAD = 2,
};

float RoomLevelHeightAt(float roomX, float roomZ, int nativeCollisionLayer) {
    if (!sVoxelHeightValid || sVoxelHeightArea != gRoomControls.area ||
        sVoxelHeightRoom != gRoomControls.room)
        return nativeCollisionLayer >= 2 ? 16.0f : 0.0f;

    const int tx = (int)std::floor(roomX / 16.0f);
    const int ty = (int)std::floor(roomZ / 16.0f);
    if (tx < 0 || ty < 0 || tx >= sVoxelHeightW || ty >= sVoxelHeightH)
        return nativeCollisionLayer >= 2 ? 16.0f : 0.0f;

    const int t = ty * 64 + tx;
    const Uint8 nativeLevel = nativeCollisionLayer >= 2 ? VOXEL_LEVEL_RAISED : VOXEL_LEVEL_GROUND;

    /*
     * Native collision decides which walkable level the actor occupies.
     * Never auto-lift a bottom-layer actor merely because the visual wall
     * footprint overlaps his tile; that was the source of cliff clipping.
     */
    if (nativeLevel == VOXEL_LEVEL_GROUND)
        return 0.0f;

    return std::max(16.0f, sVoxelHeight[t]);
}
"""
if state_anchor not in src:
    raise SystemExit("voxel height state anchor not found")
src = src.replace(state_anchor, state_repl, 1)

# Publish automatic levels and the south-facing wall planes that actually exist.
publish_old = """    sVoxelHeightW = W;
    sVoxelHeightH = H;
    sVoxelHeightArea = gRoomControls.area;
    sVoxelHeightRoom = gRoomControls.room;
    std::memset(sVoxelHeight, 0, sizeof(sVoxelHeight));
    for (int cy = 0; cy < H; ++cy)
        for (int cx = 0; cx < W; ++cx)
            sVoxelHeight[cy * 64 + cx] = hmap[cy * 64 + cx];
    sVoxelHeightValid = true;

    auto hAt = [&](int x, int b) { return inRoom(x, b) ? hmap[b * 64 + x] : 0.0f; };

    /* ---- pass 2: draw ---- */
"""
publish_new = """    sVoxelHeightW = W;
    sVoxelHeightH = H;
    sVoxelHeightArea = gRoomControls.area;
    sVoxelHeightRoom = gRoomControls.room;
    std::memset(sVoxelHeight, 0, sizeof(sVoxelHeight));
    std::memset(sVoxelLevel, 0, sizeof(sVoxelLevel));
    std::memset(sVoxelFrontFace, 0, sizeof(sVoxelFrontFace));
    for (int cy = 0; cy < H; ++cy)
        for (int cx = 0; cx < W; ++cx) {
            const int t = cy * 64 + cx;
            sVoxelHeight[t] = hmap[t];
            sVoxelLevel[t] = hmap[t] >= 8.0f ? VOXEL_LEVEL_RAISED : VOXEL_LEVEL_GROUND;
            if (Cover(cx, cy))
                sVoxelLevel[t] = VOXEL_LEVEL_OVERHEAD;
        }

    auto hAt = [&](int x, int b) { return inRoom(x, b) ? hmap[b * 64 + x] : 0.0f; };

    for (const Run& rn : runs) {
        const int south = rn.yb + 1;
        if (rn.x >= 0 && rn.x < W && rn.yb >= 0 && rn.yb < H &&
            south < H && hAt(rn.x, south) + 0.5f < rn.topH)
            sVoxelFrontFace[rn.yb * 64 + rn.x] = 1;
    }

    sVoxelHeightValid = true;

    /* ---- pass 2: draw ---- */
"""
if publish_old not in src:
    raise SystemExit("voxel height publication block not found")
src = src.replace(publish_old, publish_new, 1)

# Actor elevation must follow the actor's native level, not the visual footprint.
elev_old = """        const float groundHeight =
            RoomHeightAt(entityCenterX, entityFootZ);
        const float nativeLayerHeight = (tag.layer & 0x7Fu) == 2 ? kTopLayerLift : 0.0f;
        const float elev = tag.kind == PORT_VOXEL_OAM_ENTITY
                               ? std::max(groundHeight, nativeLayerHeight)
                               : nativeLayerHeight;
"""
elev_new = """        const int nativeCollisionLayer = (int)(tag.layer & 0x7Fu);
        const float nativeLayerHeight = nativeCollisionLayer >= 2 ? kTopLayerLift : 0.0f;
        const float groundHeight =
            RoomLevelHeightAt(entityCenterX, entityFootZ, nativeCollisionLayer);
        const float elev = tag.kind == PORT_VOXEL_OAM_ENTITY
                               ? groundHeight
                               : nativeLayerHeight;
"""
if elev_old not in src:
    raise SystemExit("entity elevation block not found")
src = src.replace(elev_old, elev_new, 1)

# ---------------------------------------------------------------------------
# Side-room doorways + tiny top-map symbols.
# ---------------------------------------------------------------------------
# Add a dedicated side-door card. Generated box sideV intentionally samples a
# narrow interior texel column; doorway art needs its real full 16x16 top tile.
side_anchor = """    /* Vertical lip of a sunk tile along one edge, heights d..0. */
"""
door_helper = r'''    auto doorSideV = [&](int x, int y, bool east, Uint32 mask) {
        const float xs = east ? (float)W * 16.0f : 0.0f;
        const float z0 = y * 16.0f, z1 = z0 + 16.0f;
        const float c[4][3] = {
            { xs, 16.0f, z0 }, { xs, 16.0f, z1 },
            { xs, 0.0f, z0 },  { xs, 0.0f, z1 }
        };
        const float u0 = x * 16.0f, v0 = y * 16.0f;
        Quad(sMapVerts, kMaxMapVerts, n, c,
             east ? u0 : u0 + 16.0f, v0,
             east ? u0 + 16.0f : u0, v0 + 16.0f,
             0, 128u, tChar, t8 | (mask << 8));
    };

'''
if side_anchor not in src:
    raise SystemExit("door helper insertion anchor not found")
src = src.replace(side_anchor, door_helper + side_anchor, 1)

cover_old = """                if (Cover(x, y)) {
                    if (outdoors && coverPixels[t] < 24) {
                        /* Outdoor tiny top-map scraps become floating black
                         * glyphs in perspective. Indoors, small overlays are
                         * often legitimate doorway/workshop/wall details. */
                    } else {
                        int clear = 0;
                        for (int i = 0; i < 256; i += 3)
                            clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                        if (clear >= 4)
                            flatL(true, x, x, y, d + 0.25f, y * 16.0f, y * 16.0f + 16, 0);
                        else
                            flatL(true, x, x, y, kTopLayerLift, y * 16.0f + kTopLayerLift,
                                  y * 16.0f + 16 + kTopLayerLift, 0);
                    }
                }
"""
cover_new = """                if (Cover(x, y)) {
                    int neighbourPixels = 0;
                    if (x > 0) neighbourPixels += coverPixels[t - 1];
                    if (x + 1 < W) neighbourPixels += coverPixels[t + 1];
                    if (y > 0) neighbourPixels += coverPixels[t - 64];
                    if (y + 1 < H) neighbourPixels += coverPixels[t + 64];

                    const bool tinyOrphan =
                        coverPixels[t] < 28 && neighbourPixels < 48;

                    /*
                     * Side-room exits are vertical wall openings, not floating
                     * horizontal roof scraps. Put their real top-layer art on
                     * the room boundary plane. This removes the giant left/right
                     * doorway panels and symbol-like cards seen in smoke tests.
                     */
                    const bool sideExit =
                        !outdoors && !solid[t] &&
                        (x <= 1 || x >= W - 2) &&
                        coverPixels[t] >= 8;

                    if (tinyOrphan) {
                        /* Ignore isolated top-map crumbs/glyphs in 3D. */
                    } else if (sideExit) {
                        const bool east = x >= W - 2;
                        const Uint32 mask = visibleMask(x, y);
                        doorSideV(x, y, east, mask);
                    } else {
                        int clear = 0;
                        for (int i = 0; i < 256; i += 3)
                            clear += BottomPixel(x, y, i & 15, i >> 4, bChar, b8 != 0) < 0;
                        if (clear >= 4)
                            flatL(true, x, x, y, d + 0.25f, y * 16.0f, y * 16.0f + 16, 0);
                        else
                            flatL(true, x, x, y, kTopLayerLift, y * 16.0f + kTopLayerLift,
                                  y * 16.0f + 16 + kTopLayerLift, 0);
                    }
                }
"""
if cover_old not in src:
    raise SystemExit("top-map cover draw block not found")
src = src.replace(cover_old, cover_new, 1)

# Public collision query for a very small strip immediately south of a real
# rendered cliff/wall face. The native game remains authoritative everywhere else.
public_anchor = """int Port_Voxel_CurrentArea(void) {
"""
public_fn = r'''extern "C" bool Port_Voxel_PlayerFaceCollision(int worldX, int worldY, int collisionLayer) {
    if (!Port_Config_GetVoxelView() || !sVoxelHeightValid ||
        sVoxelHeightArea != gRoomControls.area || sVoxelHeightRoom != gRoomControls.room)
        return false;

    /* Native top-layer movement already describes a raised walkable surface.
     * Never apply bottom-level wall clearance there. */
    if (collisionLayer >= 2)
        return false;

    const int relX = worldX - gRoomControls.origin_x;
    const int relY = worldY - gRoomControls.origin_y;
    if (relX < 0 || relY < 0)
        return false;

    const int tx = relX >> 4;
    const int ty = relY >> 4;
    if (tx < 0 || ty <= 0 || tx >= sVoxelHeightW || ty >= sVoxelHeightH)
        return false;

    if (!sVoxelFrontFace[(ty - 1) * 64 + tx])
        return false;

    const float pitch =
        std::abs((float)Port_Config_GetVoxelPitch()) * 3.14159265f / 180.0f;
    const int clearance =
        std::clamp((int)std::lround(2.0f + 6.0f * std::cos(pitch)), 3, 8);

    return (relY & 15) < clearance;
}

'''
if public_anchor not in src:
    raise SystemExit("Port_Voxel_CurrentArea anchor not found")
src = src.replace(public_anchor, public_fn + public_anchor, 1)

vox.write_text(src, encoding="utf-8")

# ---------------------------------------------------------------------------
# C ABI + Link-only collision integration.
# ---------------------------------------------------------------------------
hdr = Path("upstream/tmc/port/port_voxel.h")
h = hdr.read_text(encoding="utf-8")
h_anchor = """void Port_Voxel_RequestShot(const char* path);
"""
h_repl = h_anchor + """/* Hidden 3D smoke-test collision: adds only the small visual clearance
 * strip in front of a rendered wall face. Levels are automatic, not user-facing. */
bool Port_Voxel_PlayerFaceCollision(int worldX, int worldY, int collisionLayer);
"""
if h_anchor not in h:
    raise SystemExit("voxel header request-shot anchor not found")
h = h.replace(h_anchor, h_repl, 1)
hdr.write_text(h, encoding="utf-8")

move = Path("upstream/tmc/src/movement.c")
m = move.read_text(encoding="utf-8")

inc_old = """#ifdef PC_PORT
#include "player.h"  /* gPlayerEntity for the debug noclip hook */
extern int Port_Debug_NoclipEnabled(void);
#endif
"""
inc_new = """#ifdef PC_PORT
#include "player.h"  /* gPlayerEntity for the debug noclip hook */
#include "port_voxel.h"
extern int Port_Debug_NoclipEnabled(void);
#endif
"""
if inc_old not in m:
    raise SystemExit("movement PC_PORT include block not found")
m = m.replace(inc_old, inc_new, 1)

calc_pos = m.find("void CalculateEntityTileCollisions(Entity* this, u32 direction, u32 collisionType) {")
if calc_pos < 0:
    raise SystemExit("CalculateEntityTileCollisions not found")

helper = r'''#ifdef PC_PORT
static bool32 Port_PlayerTileCollision(Entity* entity, const u8* collisionData,
                                       s32 x, s32 y, u32 collisionType) {
    if (IsTileCollision(collisionData, x, y, collisionType))
        return TRUE;
    if (entity == &gPlayerEntity.base &&
        Port_Voxel_PlayerFaceCollision(x, y, entity->collisionLayer))
        return TRUE;
    return FALSE;
}
#else
static bool32 Port_PlayerTileCollision(Entity* entity, const u8* collisionData,
                                       s32 x, s32 y, u32 collisionType) {
    (void)entity;
    return IsTileCollision(collisionData, x, y, collisionType);
}
#endif

'''
m = m[:calc_pos] + helper + m[calc_pos:]
calc_pos = m.find("void CalculateEntityTileCollisions(Entity* this, u32 direction, u32 collisionType) {")
calc_end = m.find("\n}\n\nbool32 ProcessMovementInternal", calc_pos)
if calc_end < 0:
    raise SystemExit("CalculateEntityTileCollisions end not found")
calc_end += 3
block = m[calc_pos:calc_end]
replaced = block.replace("IsTileCollision(collisionData,", "Port_PlayerTileCollision(this, collisionData,")
if replaced == block:
    raise SystemExit("no movement collision probes replaced")
m = m[:calc_pos] + replaced + m[calc_end:]
move.write_text(m, encoding="utf-8")

print("Applied hidden multi-level 3D smoke-test model, side-door cleanup, and cliff-face collision")
