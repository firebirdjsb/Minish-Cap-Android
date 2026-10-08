#!/usr/bin/env python3
from pathlib import Path

path = Path("upstream/tmc/port/port_voxel.cpp")
src = path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. Keep 3D active through transient BottomMapShown() misses.
#    A one-frame BG mismatch must never drop the presenter back to 2D.
# ---------------------------------------------------------------------------
old_scene = """bool SceneApplicable(void) {
    return gMain.task == TASK_GAME && gMain.state == GAMETASK_MAIN && gMain.substate != GAMEMAIN_SUBTASK &&
           gMapBottom.bgSettings != nullptr && gRoomControls.width != 0 && gRoomControls.width <= 1024 &&
           gRoomControls.height <= 1024 &&
           !(gRoomControls.area == AREA_BEANSTALKS && (gRoomControls.scroll_flags & 1)) && BottomMapShown();
}
"""

new_scene = """bool SceneApplicable(void) {
    const bool structural =
        gMain.task == TASK_GAME && gMain.state == GAMETASK_MAIN &&
        gMapBottom.bgSettings != nullptr && gRoomControls.width != 0 &&
        gRoomControls.width <= 1024 && gRoomControls.height <= 1024 &&
        !(gRoomControls.area == AREA_BEANSTALKS && (gRoomControls.scroll_flags & 1));

    static bool roomLatched = false;
    static int lastArea = -1;
    static int lastOriginX = 0, lastOriginY = 0, lastW = 0, lastH = 0;

    if (!structural) {
        roomLatched = false;
        lastArea = -1;
        return false;
    }

    const bool roomChanged =
        lastArea != gRoomControls.area ||
        lastOriginX != gRoomControls.origin_x ||
        lastOriginY != gRoomControls.origin_y ||
        lastW != gRoomControls.width ||
        lastH != gRoomControls.height;

    if (roomChanged) {
        roomLatched = false;
        lastArea = gRoomControls.area;
        lastOriginX = gRoomControls.origin_x;
        lastOriginY = gRoomControls.origin_y;
        lastW = gRoomControls.width;
        lastH = gRoomControls.height;
    }

    if (BottomMapShown())
        roomLatched = true;

    /* Once this exact room has produced a valid native bottom map, keep the
     * voxel presenter for the lifetime of the room. Live BG/HDMA updates can
     * make MapShownPct() miss for a frame while walking; that is not a reason
     * to flash the normal 2D presenter. */
    return roomLatched;
}
"""
if old_scene not in src:
    raise SystemExit("SceneApplicable block not found")
src = src.replace(old_scene, new_scene, 1)

# ---------------------------------------------------------------------------
# 2. Build geometry more conservatively.
# ---------------------------------------------------------------------------
old_start = """    sBuildShapes = CurrentShapes();
    const int wallTiles = sBuildShapes ? sBuildShapes->wall : kDefaultWallTiles;
    sPropCount = 0;
    std::memset(sMaskPixels, 0, sizeof(sMaskPixels));
    const int W = gRoomControls.width / 16, H = gRoomControls.height / 16;
    const u16 cb = LayerCnt(gMapBottom.bgSettings);
"""
new_start = """    sBuildShapes = CurrentShapes();
    const bool outdoors = (gArea.areaMetadata & AR_IS_OVERWORLD) != 0;
    const int wallTiles = sBuildShapes ? sBuildShapes->wall : kDefaultWallTiles;
    sPropCount = 0;
    std::memset(sMaskPixels, 0, sizeof(sMaskPixels));
    const int W = gRoomControls.width / 16, H = gRoomControls.height / 16;
    const u16 cb = LayerCnt(gMapBottom.bgSettings);
"""
if old_start not in src:
    raise SystemExit("BuildMap start block not found")
src = src.replace(old_start, new_start, 1)

old_outdoors = """    const bool outdoors = (gArea.areaMetadata & AR_IS_OVERWORLD) != 0;
    auto inRoom = [&](int x, int y) { return x >= 0 && y >= 0 && x < W && y < H; };
"""
new_outdoors = """    auto inRoom = [&](int x, int y) { return x >= 0 && y >= 0 && x < W && y < H; };
"""
if old_outdoors not in src:
    raise SystemExit("duplicate outdoors declaration not found")
src = src.replace(old_outdoors, new_outdoors, 1)

# Absorbed overhead tiles are visual overhang, not solid boxes.
old_geom = """    auto Geom = [&](int x, int y) { return inRoom(x, y) && geom[y * 64 + x] != 0; };
"""
new_geom = """    auto Geom = [&](int x, int y) { return inRoom(x, y) && geom[y * 64 + x] != 0; };
"""
if old_geom not in src:
    raise SystemExit("Geom lambda not found")
src = src.replace(old_geom, new_geom, 1)

# Remove transient TopMapShown() from the geometry hash. Real map/layer data is
# already hashed; a one-frame visibility classification should not rebuild the room.
old_key = """    const bool topShown = TopMapShown();
    mix(&cb, sizeof(cb));
    mix(&ct, sizeof(ct));
    mix(&topShown, sizeof(topShown));
"""
new_key = """    mix(&cb, sizeof(cb));
    mix(&ct, sizeof(ct));
"""
if old_key not in src:
    raise SystemExit("MapKey topShown block not found")
src = src.replace(old_key, new_key, 1)

# Isolated outlined scenery beside one wall can still be a prop/billboard.
# Previously ANY solid neighbour forced it into a 3D wall run.
old_prop = """        if (ov != PORT_VOXEL_SHAPE_PROP && (Geom(x, y - 1) || Geom(x, y + 1) || Geom(x - 1, y) || Geom(x + 1, y)))
            return false;
        if (!BuildPropMask(x, y, sPropCount, bChar, b8 != 0))
"""
new_prop = """        if (ov != PORT_VOXEL_SHAPE_PROP &&
            (Geom(x, y - 1) || Geom(x, y + 1) || Geom(x - 1, y) || Geom(x + 1, y)))
            return false;
        if (!BuildPropMask(x, y, sPropCount, bChar, b8 != 0))
"""
if old_prop not in src:
    raise SystemExit("isProp neighbour block not found")
src = src.replace(old_prop, new_prop, 1)

# ---------------------------------------------------------------------------
# 2b. Keep the stable 3D scene frozen during transient BG/room hand-off frames.
# ---------------------------------------------------------------------------
old_scroll = """    const int viewW = Port_Widescreen_EffectiveViewWidth();
    const float scrollX = (float)(gRoomControls.scroll_x - gRoomControls.origin_x);
    const float scrollY = (float)(gRoomControls.scroll_y - gRoomControls.origin_y);
    const bool obj1d = (gIoMem[0] & 0x40) != 0;
"""
new_scroll = """    const int viewW = Port_Widescreen_EffectiveViewWidth();
    const float rawScrollX = (float)(gRoomControls.scroll_x - gRoomControls.origin_x);
    const float rawScrollY = (float)(gRoomControls.scroll_y - gRoomControls.origin_y);
    const float playerLocalX = (float)(gPlayerEntity.base.x.HALF.HI - gRoomControls.origin_x);
    const float playerLocalY = (float)(gPlayerEntity.base.y.HALF.HI - gRoomControls.origin_y);

    /*
     * gRoomControls scroll can transiently jump during room/collision handoff
     * while the player and room identity have not moved. Feeding that raw jump
     * into the perspective target shifts the entire 3D room off-screen for
     * several frames. Accept all normal native camera motion, but reject an
     * impossible same-room jump unless the player actually teleported too.
     */
    static bool haveCamera = false;
    static float stableScrollX = 0.0f, stableScrollY = 0.0f;
    static float lastPlayerX = 0.0f, lastPlayerY = 0.0f;
    static int camArea = -1, camOriginX = 0, camOriginY = 0, camW = 0, camH = 0;

    const bool cameraRoomChanged =
        camArea != gRoomControls.area ||
        camOriginX != gRoomControls.origin_x ||
        camOriginY != gRoomControls.origin_y ||
        camW != gRoomControls.width ||
        camH != gRoomControls.height;

    const bool playerTeleported =
        haveCamera && (std::abs(playerLocalX - lastPlayerX) > 64.0f ||
                       std::abs(playerLocalY - lastPlayerY) > 64.0f);

    if (!haveCamera || cameraRoomChanged || playerTeleported) {
        stableScrollX = rawScrollX;
        stableScrollY = rawScrollY;
        haveCamera = true;
        camArea = gRoomControls.area;
        camOriginX = gRoomControls.origin_x;
        camOriginY = gRoomControls.origin_y;
        camW = gRoomControls.width;
        camH = gRoomControls.height;
    } else {
        const float dx = rawScrollX - stableScrollX;
        const float dy = rawScrollY - stableScrollY;
        const float projectedX = playerLocalX - rawScrollX;
        const float projectedY = playerLocalY - rawScrollY;
        const bool playerStillInView =
            projectedX > -48.0f && projectedX < (float)viewW + 48.0f &&
            projectedY > -48.0f && projectedY < 208.0f;

        if (playerStillInView && std::abs(dx) <= 20.0f && std::abs(dy) <= 20.0f) {
            stableScrollX = rawScrollX;
            stableScrollY = rawScrollY;
        }
        /* else: keep the previous valid perspective camera for this frame. */
    }

    lastPlayerX = playerLocalX;
    lastPlayerY = playerLocalY;

    const float scrollX = stableScrollX;
    const float scrollY = stableScrollY;
    const bool roomMapStable = BottomMapShown();
    const bool obj1d = (gIoMem[0] & 0x40) != 0;
"""
if old_scroll not in src:
    raise SystemExit("voxel scroll block not found")
src = src.replace(old_scroll, new_scroll, 1)

old_dirty = """    bool mapDirty = mapKey != sMapKey;
    if (mapDirty)
        sSettleFrames = 20;
    else if (sSettleFrames > 0 && --sSettleFrames == 0)
        mapDirty = true;
"""
new_dirty = """    /*
     * Never rebuild room geometry from a one-frame map/collision glitch.
     * Require a changed room key to remain identical for three consecutive
     * stable frames. This eliminates the malformed-mesh blink seen while
     * walking across trigger/collision seams.
     */
    static Uint64 sPendingMapKey = 0;
    static int sPendingMapFrames = 0;
    bool mapDirty = false;

    if (sMapVertCount == 0 && roomMapStable) {
        mapDirty = true;
        sPendingMapKey = 0;
        sPendingMapFrames = 0;
    } else if (roomMapStable && mapKey != sMapKey) {
        if (mapKey == sPendingMapKey)
            ++sPendingMapFrames;
        else {
            sPendingMapKey = mapKey;
            sPendingMapFrames = 1;
        }
        if (sPendingMapFrames >= 3) {
            mapDirty = true;
            sPendingMapKey = 0;
            sPendingMapFrames = 0;
        }
    } else if (mapKey == sMapKey) {
        sPendingMapKey = 0;
        sPendingMapFrames = 0;
    }
"""
if old_dirty not in src:
    raise SystemExit("voxel mapDirty block not found")
src = src.replace(old_dirty, new_dirty, 1)

# Indoor art already contains the facade depth. Keep indoor walls thin and
# anchored to their native collision row instead of shifting a second copy south.
# Multi-tile trees/log piles/cliffs must remain closed solid geometry. The
# silhouette mask was carving their dark outline pixels into see-through slits.
old_masks = """        Uint32 rowMask[64] = {};
        bool anyMask = false;
        if (outdoors && !rn.ledge)
            for (int r = yt; r <= yb; ++r)
                anyMask |= (rowMask[r] = Foliage(x, r) ? silhouette(x, r) : 0u) != 0;
"""
new_masks = """        Uint32 rowMask[64] = {};
        bool anyMask = false;
        /* Keep multi-tile scenery closed. Per-pixel cutout masks are reserved
         * for isolated props; on tree/log/cliff runs they create missing tops
         * and thin transparent strips at perspective angles. */
"""
if old_masks not in src:
    raise SystemExit("run silhouette-mask block not found")
src = src.replace(old_masks, new_masks, 1)

# ---------------------------------------------------------------------------
# 3. Do not clone edge walls/trees/cliffs 24 tiles into the distance.
#    Extend only the room's common walkable ground under the perspective view.
# ---------------------------------------------------------------------------
old_margin = """    /* Outdoors, the perspective camera sees past the room edge the 2D camera
     * clamps to: continue the room outward with its edge tiles' visible art,
     * at the height they stand at. Interiors and dungeons keep the void. */
    constexpr int kMargin = 24;
    const int margin = outdoors ? kMargin : 0;
    for (int y = -margin; y < H + margin; ++y)
        for (int x = -margin; x < W + margin; ++x) {
            if (inRoom(x, y))
                continue;
            const int ex = std::clamp(x, 0, W - 1), ey = std::clamp(y, 0, H - 1);
            const float h = hAt(ex, ey); /* meet the edge cell exactly: no open step */
            flatL(false, x, ex, ey, h, y * 16.0f, y * 16.0f + 16, 0);
            if (Cover(ex, ey))
                flatL(true, x, ex, ey, h + 0.3f, y * 16.0f, y * 16.0f + 16, 0);
            /* Step to the next margin cell east: close it with a face wearing
             * the higher cell's art (see-through texels in its material). */
            const int nx = x + 1;
            if (nx < W + margin && !inRoom(nx, y)) {
                const int ex2 = std::clamp(nx, 0, W - 1);
                const float h2 = hAt(ex2, ey);
                if (h2 != h) {
                    const int sx = h > h2 ? ex : ex2;
                    const float lo = std::min(h, h2), hi = std::max(h, h2), xs = nx * 16.0f;
                    const bool topArt = Cover(sx, ey) != 0;
                    int dom = 0, domN = 0;
                    std::map<int, int> cnts;
                    for (int i = 0; i < 256; i += 4) {
                        const int ci = topArt ? TopIndex(sx, ey, i & 15, i >> 4, tChar, t8 != 0)
                                              : BottomIndex(sx, ey, i & 15, i >> 4, bChar, b8 != 0);
                        if (ci >= 0 && !Dark555(gBgPltt[ci]) && ++cnts[ci] > domN)
                            domN = cnts[ci], dom = ci;
                    }
                    const float c[4][3] = { { xs, hi, y * 16.0f }, { xs, hi, y * 16.0f + 16 }, { xs, lo, y * 16.0f },
                                            { xs, lo, y * 16.0f + 16 } };
                    Quad(sMapVerts, kMaxMapVerts, n, c, sx * 16.0f, ey * 16.0f, sx * 16.0f + 16, ey * 16.0f + 16, 0,
                         topArt ? 128u : 0u, topArt ? tChar : bChar, (topArt ? t8 : b8) | 2u | ((Uint32)dom << 20));
                }
            }
        }
"""
new_margin = """    /*
     * Perspective safety skirt for overworlds.
     *
     * The old implementation cloned the room-edge tile art for 24 tiles in
     * every direction. If the edge happened to be a tree, cliff or wall, that
     * scenery was repeated into obvious parallel copies. Extend only the
     * common walkable ground tile instead. Real room geometry ends once.
     */
    constexpr int kGroundMargin = 18;
    if (outdoors && groundX >= 0 && groundY >= 0) {
        for (int y = -kGroundMargin; y < H + kGroundMargin; ++y)
            for (int x = -kGroundMargin; x < W + kGroundMargin; ++x) {
                if (inRoom(x, y))
                    continue;
                flatL(false, x, groundX, groundY, 0.0f,
                      y * 16.0f, y * 16.0f + 16.0f, 0);
            }
    }
"""
if old_margin not in src:
    raise SystemExit("outdoor repeated-edge margin block not found")
src = src.replace(old_margin, new_margin, 1)

# Requested Android default: one tile high everywhere unless an area override explicitly changes it.
old_default_height = "constexpr int kDefaultWallTiles = 2;"
if old_default_height not in src:
    raise SystemExit("default wall height constant not found")
src = src.replace(old_default_height, "constexpr int kDefaultWallTiles = 1;", 1)

# The debounced map-key path no longer uses the old periodic settle rebuild.
src = src.replace("    static int sSettleFrames = 0;\\n", "", 1)

path.write_text(src, encoding="utf-8")
print("Applied stable 3D scene latch and conservative clean geometry")
