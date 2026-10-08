#!/usr/bin/env python3
from pathlib import Path

vox = Path("upstream/tmc/port/port_voxel.cpp")
src = vox.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Native gameplay collision stays authoritative.
#
# This transform publishes only the renderer's HEIGHT field for sprite placement.
# It deliberately does NOT modify movement.c, collision.c, or port_voxel.h.
# The prior supplemental 3D collision layer caused side-wall / ledge regressions.
# ---------------------------------------------------------------------------

state_anchor = """const AreaShapes* sBuildShapes = nullptr; /* CurrentShapes() for the BuildMap in progress */
"""
state_repl = state_anchor + """
static float sVoxelHeight[64 * 64] = {};
static int sVoxelHeightW = 0, sVoxelHeightH = 0;
static int sVoxelHeightOriginX = 0, sVoxelHeightOriginY = 0;
static int sVoxelHeightArea = -1;
static bool sVoxelHeightValid = false;

float WorldHeightAt(float worldX, float worldZ) {
    if (!sVoxelHeightValid || sVoxelHeightArea != gRoomControls.area ||
        sVoxelHeightOriginX != gRoomControls.origin_x ||
        sVoxelHeightOriginY != gRoomControls.origin_y)
        return 0.0f;

    const int tx = (int)std::floor((worldX - (float)sVoxelHeightOriginX) / 16.0f);
    const int ty = (int)std::floor((worldZ - (float)sVoxelHeightOriginY) / 16.0f);
    if (tx < 0 || ty < 0 || tx >= sVoxelHeightW || ty >= sVoxelHeightH)
        return 0.0f;
    return sVoxelHeight[ty * 64 + tx];
}
"""
if state_anchor not in src:
    raise SystemExit("voxel build-shape state anchor not found")
src = src.replace(state_anchor, state_repl, 1)

build_anchor = """void BuildMap(void) {
    int n = 0;
    sBuildShapes = CurrentShapes();
"""
build_repl = """void BuildMap(void) {
    int n = 0;
    sVoxelHeightValid = false;
    sBuildShapes = CurrentShapes();
"""
if build_anchor not in src:
    raise SystemExit("BuildMap start anchor not found")
src = src.replace(build_anchor, build_repl, 1)

height_anchor = """    auto hAt = [&](int x, int b) { return inRoom(x, b) ? hmap[b * 64 + x] : 0.0f; };

    /* ---- pass 2: draw ---- */
"""
height_repl = """    sVoxelHeightW = W;
    sVoxelHeightH = H;
    sVoxelHeightOriginX = gRoomControls.origin_x;
    sVoxelHeightOriginY = gRoomControls.origin_y;
    sVoxelHeightArea = gRoomControls.area;
    std::memset(sVoxelHeight, 0, sizeof(sVoxelHeight));
    for (int cy = 0; cy < H; ++cy)
        for (int cx = 0; cx < W; ++cx)
            sVoxelHeight[cy * 64 + cx] = hmap[cy * 64 + cx];
    sVoxelHeightValid = true;

    auto hAt = [&](int x, int b) { return inRoom(x, b) ? hmap[b * 64 + x] : 0.0f; };

    /* ---- pass 2: draw ---- */
"""
if height_anchor not in src:
    raise SystemExit("hmap publication anchor not found")
src = src.replace(height_anchor, height_repl, 1)

# Use the entity's native feet/ground row for a tagged entity. OAM pieces often
# extend below that row; using each piece's bottom makes the card jump and clip.
sprite_anchor = """        const float x0 = o.x + scrollX, x1 = x0 + o.w;
        const int sy0 = o.y, sy1 = sy0 + o.h;
        const float elev = tag.layer == 2 ? kTopLayerLift : 0.0f;
        float c[4][3];
"""
sprite_repl = """        const float x0 = o.x + scrollX, x1 = x0 + o.w;
        const int sy0 = o.y, sy1 = sy0 + o.h;
        const int entityFoot = tag.kind == PORT_VOXEL_OAM_ENTITY
                                   ? (int)tag.groundY
                                   : std::max<int>(tag.groundY, sy1);
        const float entityFootZ = (float)entityFoot + scrollY;
        const float entityCenterX = (x0 + x1) * 0.5f;
        const float groundHeight =
            WorldHeightAt(entityCenterX + gRoomControls.origin_x,
                          entityFootZ + gRoomControls.origin_y);
        const float nativeLayerHeight = tag.layer == 2 ? kTopLayerLift : 0.0f;
        const float elev = tag.kind == PORT_VOXEL_OAM_ENTITY
                               ? std::max(groundHeight, nativeLayerHeight)
                               : nativeLayerHeight;
        float c[4][3];
"""
if sprite_anchor not in src:
    raise SystemExit("entity elevation anchor not found")
src = src.replace(sprite_anchor, sprite_repl, 1)

foot_old = """            const int foot = std::max<int>(tag.groundY, sy1);
            const float footZ = foot + scrollY, footY = elev + 0.5f;
"""
foot_new = """            const int foot = entityFoot;
            const float footZ = entityFootZ, footY = elev + 0.5f;
"""
if foot_old not in src:
    raise SystemExit("entity billboard foot anchor not found")
src = src.replace(foot_old, foot_new, 1)

vox.write_text(src, encoding="utf-8")
print("Kept native collision authoritative and aligned entity height to rendered 3D floors")
