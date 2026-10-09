// ROM-free synthetic scenes exercise the actual prepared BuildMap function.
// Unused GPU functions are discarded by --gc-sections; no SDL device needed.
#include "../upstream/tmc/port/port_voxel.cpp"
#include <cassert>
#include <iostream>

extern "C" {
RoomControls gRoomControls;
MapLayer gMapBottom, gMapTop;
Area gArea;
Main gMain;
Screen gScreen;
PlayerEntity gPlayerEntity;
PlayerState gPlayerState;
u16 gMapDataBottomSpecial[0x4000], gMapDataTopSpecial[0x4000];
u16 gBgPltt[256], gObjPltt[256], gOamMem[512];
u8 gVram[0x18000], gIoMem[0x400];
bool voxelEnabled = true;
bool Port_Config_GetVoxelView(void) { return voxelEnabled; }
}

static void resetScene(bool outdoors, int w = 8, int h = 8) {
    std::memset(&gMapBottom, 0, sizeof(gMapBottom));
    std::memset(&gMapTop, 0, sizeof(gMapTop));
    std::memset(gMapDataTopSpecial, 0, sizeof(gMapDataTopSpecial));
    std::memset(gIoMem, 0, sizeof(gIoMem));
    gRoomControls = {};
    gRoomControls.width = w * 16;
    gRoomControls.height = h * 16;
    gArea.areaMetadata = outdoors ? AR_IS_OVERWORLD : 0;
    gMapBottom.bgSettings = &gScreen.bg1;
    gMapTop.bgSettings = reinterpret_cast<BgSettings*>(&gScreen.bg2);
    sBottomBinding = {};
    sBottomBinding.bg = 1;
    sTopBinding = {};
    sTopBinding.bg = 2;
    sTopBinding.control = 4;
    sShapesLoaded = true;
    sShapes.clear();
    gBgPltt[1] = 5 | (24 << 5) | (4 << 10);
    gBgPltt[2] = 20 | (12 << 5) | (5 << 10);
    std::memset(gVram, 0, sizeof(gVram));
    std::memset(gVram + 32, 0x11, 32); // solid green floor tile
    std::memset(gVram + 64, 0x22, 32); // brown facade tile
    std::memset(gVram + 0x4000 + 64, 0x22, 32);
    std::fill(std::begin(gMapDataBottomSpecial), std::end(gMapDataBottomSpecial), 1);
}

static void tile(u16* map, int x, int y, u16 art) {
    const int t = y * 256 + x * 2;
    map[t] = map[t + 1] = map[t + 128] = map[t + 129] = art;
}
static void block(int x, int y) {
    gMapBottom.collisionData[y * 64 + x] = 0x0f;
    tile(gMapDataBottomSpecial, x, y, 2);
}

static void outdoorRuns() {
    resetScene(true);
    for (int x = 2; x <= 4; ++x) {
        block(x, 2);
        block(x, 3);
        tile(gMapDataTopSpecial, x, 2, 2);
    }
    BuildMap();
    assert(sMapVertCount > 0 && sFrontCount == 3);
    bool texturedSide = false, closedNorth = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.pos[1] == c.pos[1])
            continue;
        if (a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]) {
            // Connected foliage/cliffs must never carry a prop mask.
            assert(((a.p[3] >> 8) & 511u) == 0);
            if (a.p[1] == 0) {
                assert(std::abs(a.uv[0] - b.uv[0]) == 16.0f);
                // Side facade owns row 3, not the green canopy's row 2.
                assert(((a.p[2] >> 22) & 63u) == 3);
                assert(a.p[3] & 2u); // opaque transparent-texel fallback
                texturedSide = true;
            }
        }
        if (a.pos[2] == 48 && b.pos[2] == 48 && c.pos[2] == 48)
            closedNorth = true;
    }
    assert(texturedSide && closedNorth);
    // Skirt tiles extend the view without cloning any raised scenery.
    for (int i = 0; i < sMapVertCount; ++i)
        if (sMapVerts[i].pos[0] < 0 || sMapVerts[i].pos[0] > 128 ||
            sMapVerts[i].pos[2] < 0 || sMapVerts[i].pos[2] > 128)
            assert(sMapVerts[i].pos[1] == 0);
}

static void indoorDoorsAndScraps() {
    resetScene(false);
    // Side opening with native wall support and top frame art.
    block(0, 1);
    block(0, 3);
    block(1, 1);
    block(1, 3);
    tile(gMapDataTopSpecial, 0, 2, 2);
    tile(gMapDataTopSpecial, 1, 2, 2);
    gMapBottom.collisionData[2 * 64 + 0] = 0x23;
    gMapBottom.collisionData[2 * 64 + 1] = 0x23;
    // An isolated 4-pixel overlay must not become a raised glyph.
    gVram[0x4000 + 96] = 0x22;
    gVram[0x4000 + 97] = 0x22;
    gMapDataTopSpecial[5 * 256 + 5 * 2] = 3;
    BuildMap();
    int westDoorBands[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.p[0] != 0 || a.p[1] != 128)
            continue;
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        assert(!(tx == 5 && ty == 5));
        if (tx < 2 && ty == 2) {
            assert(a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]);
            assert(a.pos[1] != c.pos[1]);
            float low = sMapVerts[i].pos[1], high = low;
            for (int j = 1; j < 6; ++j) {
                low = std::min(low, sMapVerts[i + j].pos[1]);
                high = std::max(high, sMapVerts[i + j].pos[1]);
            }
            assert(low == tx * 16.0f && high == low + 16.0f);
            ++westDoorBands[tx];
        }
    }
    assert(westDoorBands[0] == 1 && westDoorBands[1] == 1);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].tile != 2 * 64); // doorway never blocks movement

    resetScene(false);
    block(6, 1);
    block(6, 3);
    block(7, 1);
    block(7, 3);
    tile(gMapDataTopSpecial, 6, 2, 2);
    tile(gMapDataTopSpecial, 7, 2, 2);
    gMapBottom.collisionData[2 * 64 + 6] = 0x23;
    gMapBottom.collisionData[2 * 64 + 7] = 0x23;
    BuildMap();
    int eastDoorBands[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (a.p[1] == 128 && tx >= 6 && ty == 2) {
            assert(a.pos[0] == 96 && a.pos[0] == b.pos[0] && a.pos[0] == c.pos[0]);
            assert(a.pos[1] != c.pos[1]);
            float low = sMapVerts[i].pos[1], high = low;
            for (int j = 1; j < 6; ++j) {
                low = std::min(low, sMapVerts[i + j].pos[1]);
                high = std::max(high, sMapVerts[i + j].pos[1]);
            }
            assert(low == (7 - tx) * 16.0f && high == low + 16.0f);
            ++eastDoorBands[tx - 6];
        }
    }
    assert(eastDoorBands[0] == 1 && eastDoorBands[1] == 1);
}

static void longIndoorSideWall() {
    resetScene(false, 8, 10);
    for (int y = 0; y < 10; ++y)
        if (y != 5) {
            block(0, y);
            block(1, y);
            block(6, y);
            block(7, y);
        }
    // Native side-door collision (0x23) appears in both two-column openings.
    for (int x : {0, 1, 6, 7}) {
        gMapBottom.collisionData[5 * 64 + x] = 0x23;
        tile(gMapDataBottomSpecial, x, 5, 2);
    }
    BuildMap();

    int doorwayBands[4] = {};
    bool rowTwoSide[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.p[0] != 0 || a.p[1] != 0)
            continue;
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (ty == 5 && (tx < 2 || tx >= 6)) {
            const float plane = tx < 2 ? 32.0f : 96.0f;
            assert(a.pos[0] == plane && b.pos[0] == plane && c.pos[0] == plane);
            ++doorwayBands[tx < 2 ? tx : tx - 4];
        }
        if (ty == 2 && (tx == 1 || tx == 6)) {
            const float plane = tx == 1 ? 32.0f : 96.0f;
            if (a.pos[0] == plane && b.pos[0] == plane && c.pos[0] == plane &&
                a.pos[2] >= 32 && b.pos[2] <= 48)
                rowTwoSide[tx == 1 ? 0 : 1] = true;
        }
    }
    for (int count : doorwayBands) assert(count == 1);
    assert(rowTwoSide[0] && rowTwoSide[1]); // long walls sample their current row
}

static void twoRowDoorframes() {
    resetScene(false, 8, 10);
    for (int x = 2; x <= 4; ++x)
        for (int y = 0; y <= 1; ++y)
            block(x, y);
    gMapBottom.mapData[3] = 0x3da;
    gMapBottom.mapData[64 + 3] = 0x91;
    gMapBottom.collisionData[2 * 64 + 3] = 0x27;
    BuildMap();
    int north[3][2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 1];
        const auto& c = sMapVerts[i + 2];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        const int physicalX = (int)std::lround(a.pos[0] / 16.0f);
        if (a.p[0] == 0 && a.p[1] == 0 &&
            physicalX >= 2 && physicalX <= 4 && ty <= 1 &&
            a.pos[2] == 32 && b.pos[2] == 32 && c.pos[2] == 32) {
            assert(a.pos[1] == (2 - ty) * 16.0f && b.pos[1] == (1 - ty) * 16.0f);
            // The arch centre retains native UVs; its flanking jambs
            // intentionally sample ordinary neighbouring wall trim, which
            // eliminates the visible placeholder glyph from their art.
            assert(tx == (physicalX == 2 ? 1 : physicalX == 4 ? 5 : 3));
            ++north[physicalX - 2][ty];
        }
    }
    // The true passage centre has two 16px frame rows. Adjacent jamb
    // columns retain the normal one-row wall cap, not glyph-bearing 32px
    // false doorway faces.
    assert(north[1][0] == 1 && north[1][1] == 1);
    assert(north[0][0] == 0 && north[2][0] == 0);
    assert(north[0][1] == 1 && north[2][1] == 1);

    resetScene(false, 8, 10);
    for (int x : {2, 4})
        for (int y : {8, 9}) block(x, y);
    gMapBottom.collisionData[8 * 64 + 3] = 0x27;
    gMapBottom.collisionData[9 * 64 + 3] = 0x27;
    BuildMap();
    int south[3][2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 1];
        const auto& c = sMapVerts[i + 2];
        const int tx = (a.p[2] >> 16) & 63, ty = (a.p[2] >> 22) & 63;
        if (a.p[0] == 0 && a.p[1] == 0 && tx >= 2 && tx <= 4 && ty >= 8 && ty <= 9 &&
            a.pos[2] == 160 && b.pos[2] == 160 && c.pos[2] == 160) {
            assert(a.pos[1] == (10 - ty) * 16.0f && b.pos[1] == (9 - ty) * 16.0f);
            ++south[tx - 2][ty - 8];
        }
    }
    assert(south[0][0] == 1 && south[0][1] == 1);
    assert(south[1][0] == 1 && south[1][1] == 0); // centre passage stays open
    assert(south[2][0] == 1 && south[2][1] == 1);
}

static void ledgeAndCapacity() {
    resetScene(true);
    block(2, 2);
    block(2, 3);
    block(3, 3); // neighbouring low ledge, 8 pixels high
    BuildMap();
    bool exposedBand = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 2];
        const auto& c = sMapVerts[i + 1];
        if (a.pos[0] == 48 && b.pos[0] == 48 && c.pos[0] == 48 &&
            a.pos[1] > c.pos[1] && a.pos[2] >= 48 && b.pos[2] <= 64) {
            assert(c.pos[1] >= 8); // no full-height internal duplicate wall
            exposedBand = true;
        }
    }
    assert(exposedBand);
    resetScene(true, 64, 64);
    for (int y = 0; y < 64; ++y)
        for (int x = 0; x < 64; ++x)
            if ((x + y) & 1) block(x, y);
    BuildMap();
    assert(sMapVertCount > 0 && sMapVertCount < kMaxMapVerts - 6);
}

static void townGroundFidelity() {
    // Plaza colour is the most common walkable tile, but the town outskirts
    // are grass. The 3D distance skirt must use the local edge grass rather
    // than cloning the plaza beyond the buildings.
    resetScene(true, 8, 8);
    for (int y = 1; y <= 6; ++y)
        for (int x = 1; x <= 6; ++x) {
            gMapBottom.mapData[y * 64 + x] = 2;
            tile(gMapDataBottomSpecial, x, y, 2);
        }
    // Castle border is not a single grass texture: pavement also uses the
    // native top BG layer at real walkable ground height.
    tile(gMapDataTopSpecial, 0, 3, 2);
    // An opaque top BG painted over a walkable plaza square belongs on its
    // native floor; it must never become a floating one-tile-high platform.
    tile(gMapDataTopSpecial, 3, 3, 2);
    tile(gMapDataTopSpecial, 4, 3, 2);
    BuildMap();
    bool topOnFloor = false, skirtUsesGrass = false, skirtUsesPlaza = false, skirtCarriesStone = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& q = sMapVerts[i];
        const int tx = (q.p[2] >> 16) & 63, ty = (q.p[2] >> 22) & 63;
        if (q.p[0] == 0 && q.p[1] == 128 && tx == 3 && ty == 3) {
            assert(q.pos[1] >= 0 && q.pos[1] < 2.0f);
            topOnFloor = true;
        }
        if (q.p[0] == 0 && q.p[1] == 128 &&
            q.pos[0] < 0 && q.pos[2] >= 48 && q.pos[2] < 64) {
            assert(q.pos[1] >= 0 && q.pos[1] < 2.0f);
            skirtCarriesStone = true;
        }
        if (q.p[0] == 0 && q.p[1] == 0 &&
            q.pos[0] < 0 && q.pos[2] >= 32 && q.pos[2] < 96) {
            assert(tx < 8 && ty < 8);
            const u16 material = gMapBottom.mapData[ty * 64 + tx];
            assert(material == 0 || material == 2);
            skirtUsesGrass |= material == 0;
            skirtUsesPlaza |= material == 2;
        }
    }
    assert(topOnFloor && skirtUsesGrass && skirtUsesPlaza && skirtCarriesStone);
    assert(kDefaultWallTiles == 1);
}

static void intrinsicGeometryLevels() {
    // A 3x3 connected solid cliff should STILL be one tile tall. Native
    // collision remains authoritative, not the inferred size of a run.
    resetScene(true, 8, 9);
    for (int x = 2; x <= 4; ++x)
        for (int y = 1; y <= 3; ++y)
            block(x, y);
    BuildMap();
    assert(sFrontCount > 0);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].height <= 16.0f);
    for (int y = 1; y <= 3; ++y)
        for (int x = 2; x <= 4; ++x)
            assert(sVoxelHeight[y * 64 + x] <= 16.0f);

    // Even a 3x5 broad connected cliff must NOT be auto-promoted to
    // two or three levels: it creates giant malformed facade panels.
    resetScene(true, 8, 10);
    for (int x = 2; x <= 4; ++x)
        for (int y = 1; y <= 5; ++y)
            block(x, y);
    BuildMap();
    assert(sFrontCount > 0);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].height <= 16.0f);
    for (int y = 1; y <= 5; ++y)
        for (int x = 2; x <= 4; ++x)
            assert(sVoxelHeight[y * 64 + x] <= 16.0f);
    assert(kDefaultWallTiles == 1);

    // Doorway-specific geometry remains governed by the native doorway
    // topology, and decorative walls cannot become false 32px arches.
    resetScene(false, 8, 10);
    for (int x = 2; x <= 4; ++x)
        for (int y = 0; y < 2; ++y)
            block(x, y);
    gMapBottom.mapData[3] = 0x3da;
    gMapBottom.mapData[64 + 3] = 0x91;
    BuildMap();
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].height != 32.0f);
}

static void transitionsAndBindings() {
    voxel::LayerBinding b;
    b.observe(1, 4, true);
    b.observe(1, 4, true);
    assert(b.bg == -1);
    b.observe(1, 4, true);
    assert(b.bg == 1);
    b.observe(2, 8, true);
    b.observe(1, 0xc004, true); // screen block change, same material
    assert(b.bg == 1 && b.control == 4);
    for (int i = 0; i < 5; ++i) b.observe(2, 8, true);
    assert(b.bg == 2 && b.control == 8);

    voxel::MeshGate g;
    assert(!g.observe(1, true));
    assert(!g.observe(1, false));
    assert(!g.observe(1, true));
    assert(!g.observe(2, true));
    assert(!g.observe(2, true));
    assert(g.observe(2, true));
    assert(!g.observe(3, true) && g.accepted == 2);
    assert(!g.observe(3, false));
    assert(!g.observe(3, true));
    assert(!g.observe(3, true));
    assert(g.observe(3, true));

    resetScene(false);
    sSceneRoom = CurrentRoomId();
    sMapVertCount = 6;
    sVoxelHeightValid = true;
    sFrontCount = 1;
    gRoomControls.room++;
    ObserveRoomScene();
    assert(sMapVertCount == 0 && !sVoxelHeightValid && sFrontCount == 0);
    assert(!sMeshGate.ready);
}

static void movementAndOcclusion() {
    const voxel::FrontFace f{16, 32, 48, 16, 0, 0};
    float contact = 0;
    assert(voxel::crossFront(f, 24, 52, 25, 50, contact) && contact == 51);
    assert(!voxel::crossFront(f, 24, 50, 24, 48, contact)); // overlap never teleports out
    assert(!voxel::crossFront(f, 24, 50, 24, 54, contact)); // leaving remains free
    assert(!voxel::crossFront(f, 40, 52, 40, 50, contact)); // only local face span
    assert(!voxel::crossFront(f, 24, 100, 24, 40, contact)); // teleport
    const float pitch = 60.0f * 3.14159265f / 180.0f;
    assert(voxel::frontDepthHeight(f, 24, 54, pitch) == 16);
    assert(voxel::frontDepthHeight(f, 24, 47, pitch) == 0); // behind remains occluded
    assert(voxel::frontDepthHeight(f, 40, 54, pitch) == 0);
    assert(voxel::frontDepthHeight(f, 24, 90, pitch) == 0);

    // Exercise the public game hook, including mode/layer and stale-face
    // guards. Native BG screen blocks confirm this synthetic room normally.
    resetScene(false);
    block(1, 2);
    block(1, 1);
    BuildMap();
    sSceneRoom = CurrentRoomId();
    gMain.task = TASK_GAME;
    gMain.state = GAMETASK_MAIN;
    gMain.substate = GAMEMAIN_UPDATE;
    gIoMem[1] = 1 << 1;
    gIoMem[11] = 16; // screen block 16, away from our character art
    auto* screen = reinterpret_cast<u16*>(gVram + 0x8000);
    std::fill(screen, screen + 1024, 1);
    gPlayerEntity = {};
    gPlayerEntity.base.collisionLayer = 1;
    gPlayerState = {};
    const int32_t oldX = 24 * 65536, oldZ = 52 * 65536;
    int32_t nx = 25 * 65536, nz = 50 * 65536;
    assert(Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz) && nz == 51 * 65536);
    assert(nx == 25 * 65536); // lateral native movement is preserved
    voxelEnabled = false;
    nz = 50 * 65536;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz) && nz == 50 * 65536);
    voxelEnabled = true;
    gPlayerEntity.base.collisionLayer = 2;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
    gPlayerEntity.base.collisionLayer = 1;
    gPlayerState.jump_status = 1;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
    gPlayerState.jump_status = 0;
    gMapBottom.collisionData[2 * 64 + 1] = 0;
    assert(!Port_Voxel_AssistPlayerMovement(oldX, oldZ, &nx, &nz));
}

static void offscreenOamVisibility() {
    // Upstream PR #219: draw across a 256px top/side 3D margin, and never
    // spend offscreen OAM while native 2D mode is presenting.
    for (int width : {240, 320, 512, 576}) {
        assert(Port_Voxel_PieceVisible3D(-256, -256, 16, width));
        assert(Port_Voxel_PieceVisible3D(width + 255, 16, 16, width));
        assert(Port_Voxel_PieceVisible3D(20, -200, 16, width));
        assert(!Port_Voxel_PieceVisible3D(-273, 0, 16, width));
        assert(!Port_Voxel_PieceVisible3D(width + 256, 0, 16, width));
        assert(!Port_Voxel_PieceVisible3D(15, -257, 16, width));
        assert(!Port_Voxel_PieceVisible3D(15, 160, 16, width));
        assert(Port_Voxel_PieceNeedsParking(20, -97, width));
        assert(!Port_Voxel_PieceNeedsParking(20, -96, width));
        assert(!Port_Voxel_PieceNeedsParking(20, 0, width));
    }
    // GBA x is stored as 9 bits. At 576px native output, negative coords
    // and coords > 511 alias a *different* valid x unless parked.
    assert(Port_Voxel_PieceNeedsParking(-20, 0, 576));
    assert(Port_Voxel_PieceNeedsParking(512, 0, 576));
    assert(!Port_Voxel_PieceNeedsParking(511, 0, 576));
    assert(!Port_Voxel_PieceNeedsParking(-20, 0, 240));
    assert(Port_Voxel_PieceNeedsParking(-300, 0, 240));
    assert(Port_Voxel_PieceNeedsParking(240, 0, 240));
    // Even if last frame was 3D, turning off the setting prevents expansion.
    sDrewVoxelLastFrame = true;
    voxelEnabled = false;
    assert(!Port_Voxel_IsDrawing());
    voxelEnabled = true;
    assert(Port_Voxel_IsDrawing());
    sDrewVoxelLastFrame = false;
    assert(!Port_Voxel_IsDrawing());
}

static void nativeJumpEdgesAndScenery() {
    // PR210 visual overrides MUST NOT turn game-defined jump-off cliff
    // edges or passable plants into solid geometry.
    resetScene(true);
    gMapBottom.tileTypes[2] = 123; // curated BLOCK art, not native collision
    gMapBottom.mapData[2 * 64 + 2] = 2;
    sShapes[0].tiles[123] = PORT_VOXEL_SHAPE_BLOCK;
    BuildMap();
    assert(sVoxelHeight[2 * 64 + 2] == 0.0f);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].tile != 2 * 64 + 2);

    resetScene(true);
    gMapBottom.tileTypes[2] = 123;
    gMapBottom.mapData[2 * 64 + 2] = 2;
    gMapBottom.collisionData[2 * 64 + 2] = 0x0f;
    gMapBottom.actTiles[2 * 64 + 2] = 116; // native SURFACE_EDGE
    sShapes[0].tiles[123] = PORT_VOXEL_SHAPE_BLOCK;
    tile(gMapDataTopSpecial, 2, 2, 2); // absorption also must stay flat
    block(3, 2); // structural neighbour
    BuildMap();
    assert(sVoxelHeight[2 * 64 + 2] == 0.0f);
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].tile != 2 * 64 + 2);

    resetScene(true);
    gMapBottom.tileTypes[2] = 28; // small native grass / cut bush art
    gMapBottom.mapData[2 * 64 + 2] = 2;
    block(2, 2);
    block(3, 2); // neighbouring collision wall must not turn grass into a cube
    sShapes[0].tiles[28] = PORT_VOXEL_SHAPE_BLOCK;
    BuildMap();
    assert(sVoxelHeight[2 * 64 + 2] == 0.0f); // no erroneous cube
    for (int i = 0; i < sFrontCount; ++i)
        assert(sFrontFaces[i].tile != 2 * 64 + 2);
}

static void indoorNativeUnderlay() {
    resetScene(false);
    sTopBinding.control = 7; // native top BG priority is lower than bottom
    tile(gMapDataTopSpecial, 3, 3, 2);
    BuildMap();
    bool found = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        if (a.p[0] != 0 || a.p[1] != 128)
            continue;
        const int tx = (a.p[2] >> 16) & 63;
        const int ty = (a.p[2] >> 22) & 63;
        if (tx == 3 && ty == 3) {
            assert(a.pos[1] >= -1.0f && a.pos[1] < 0.0f);
            assert(a.pos[2] >= 48.0f && a.pos[2] <= 64.0f);
            found = true;
        }
    }
    assert(found);
}

static void pr210CuratedTileShapes() {
    // Curated classifications from tmc PR #210 ship as embedded defaults.
    // They must never restore the old per-area two/three-tile wall height.
    sShapesLoaded = false;
    sShapes.clear();
    LoadShapes();
    assert(sShapes.size() >= 59);
    size_t classified = 0;
    for (const auto& [area, shape] : sShapes) {
        assert(shape.wall == kDefaultWallTiles);
        classified += shape.tiles.size();
    }
    assert(classified >= 510);
    assert(sShapes.at(0).tiles.at(63) == PORT_VOXEL_SHAPE_PROP);
    assert(sShapes.at(0).tiles.at(123) == PORT_VOXEL_SHAPE_BLOCK);
    assert(kDefaultWallTiles == 1);
}

static void festivalCutoutsAndBridgeForeground() {
    resetScene(true, 12, 12);
    // A bright, partially transparent top-BG flower/flag is ART, not a
    // solid floor strip. Place its original pixelated sprite vertically.
    gBgPltt[3] = 31 | (2 << 5); // bright red GBA colour
    std::memset(gVram + 0x4000 + 3 * 32, 0x33, 12);
    tile(gMapDataTopSpecial, 6, 6, 3);
    BuildMap();
    bool standing = false, floor = false;
    for (int i=0;i<sMapVertCount;i+=6) {
        const auto& v=sMapVerts[i];
        if (v.pos[0]==96.0f && v.pos[2]==112.35f &&
            v.pos[1]==16.0f && v.p[1]==128)
            standing=true;
        if (v.pos[0]==96.0f && v.pos[2]==96.0f &&
            v.pos[1]==0.0f && v.p[1]==0)
            floor=true;
    }
    assert(standing && floor); // no 3D collision changes

    resetScene(true,12,12);
    for (int x=2;x<=9;++x)
        tile(gMapDataTopSpecial,x,5,2);
    BuildMap();
    assert(sBridgeFirstVert < sMapVertCount);
    for(int i=0;i<sBridgeFirstVert;i+=6)
        assert((sMapVerts[i].p[3] & 0x40000000u)==0u);
    for(int i=sBridgeFirstVert;i<sMapVertCount;i+=6)
        assert((sMapVerts[i].p[3] & 0x40000000u)!=0u);

    resetScene(true,12,12);
    for(int y=3;y<=7;++y)
        for(int x=2;x<=9;++x)
            tile(gMapDataTopSpecial,x,y,2);
    BuildMap();
    assert(sBridgeFirstVert == sMapVertCount);
}

static void fullNativeNorthWall() {
    // Ordinary two-row room back walls must preserve BOTH 16px facade art
    // rows on a SINGLE north-facing plane. Previously the upper row became
    // a duplicated horizontal roof stripe and the room lost wall furniture.
    resetScene(false, 8, 10);
    for (int x = 0; x < 8; ++x)
        for (int y = 0; y < 2; ++y) {
            block(x, y);
            tile(gMapDataTopSpecial, x, y, 2); // authentic two-row BG2 facade art
        }
    BuildMap();
    bool rows[2] = {};
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& a = sMapVerts[i];
        const auto& b = sMapVerts[i + 1];
        const auto& c = sMapVerts[i + 2];
        if (a.p[0] != 0 || a.p[1] != 0)
            continue;
        const int tx = (a.p[2] >> 16) & 63;
        const int ty = (a.p[2] >> 22) & 63;
        if (tx != 3 || ty > 1)
            continue;
        if (a.pos[2] == 32 && b.pos[2] == 32 && c.pos[2] == 32) {
            assert(a.pos[1] == (2 - ty) * 16.0f);
            assert(b.pos[1] == (1 - ty) * 16.0f);
            rows[ty] = true;
        }
    }
    assert(rows[0] && rows[1]);
}

static void nativeBridgeDepthAndIndoorLayering() {
    resetScene(true, 12, 12);
    // A long thin BG2 deck across passable bottom-map ground must be
    // overhead rather than a duplicated ground/plaza tile.
    for (int x = 2; x <= 9; ++x)
        tile(gMapDataTopSpecial, x, 5, 2);
    BuildMap();
    bool elevated = false, groundBelow = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& v = sMapVerts[i];
        if (v.pos[0] >= 2 * 16 && v.pos[0] <= 9 * 16 &&
            v.pos[2] == 5 * 16 && v.p[1] == 128) {
            if ((v.p[3] & 0x40000000u) != 0u) {
                assert(v.pos[1] == 32.0f);
                elevated = true;
            } else {
                assert(v.pos[1] < 2.0f || v.pos[1] > 32.0f);
            }
        }
        if (v.pos[0] == 5 * 16 && v.pos[2] == 5 * 16 &&
            v.p[1] == 0 && v.pos[1] == 0.0f)
            groundBelow = true;
    }
    assert(elevated && groundBelow);

    resetScene(true, 12, 12);
    // Wide opaque plaza backgrounds are FLOOR, not overhead decks.
    for (int y = 3; y <= 7; ++y)
        for (int x = 2; x <= 9; ++x)
            tile(gMapDataTopSpecial, x, y, 2);
    BuildMap();
    for (int i = 0; i < sMapVertCount; i += 6)
        if (sMapVerts[i].p[1] == 128)
            assert((sMapVerts[i].p[3] & 0x40000000u) == 0u);

    resetScene(false, 10, 10);
    // Interior furniture/trim in the top BG next to collision wall must
    // remain at native floor X/Z, not be absorbed into a fake wall run.
    block(4, 5);
    tile(gMapDataTopSpecial, 5, 5, 2);
    BuildMap();
    bool nativeFloorDetail = false;
    for (int i = 0; i < sMapVertCount; i += 6) {
        const auto& v = sMapVerts[i];
        if (v.p[1] == 128 && v.pos[0] == 5 * 16 &&
            v.pos[2] == 5 * 16 && v.pos[1] < 2.0f)
            nativeFloorDetail = true;
    }
    assert(nativeFloorDetail);
}

static void aspects() {
    for (float aspect : {1.5f, 16.0f/9, 21.0f/9, 32.0f/9, 3120.0f/1440}) {
        for (auto size : {std::pair{3120, 1440}, std::pair{960, 540}, std::pair{800, 600}}) {
            const auto v = voxel::fitViewport(size.first, size.second, aspect);
            assert(v.w > 0 && v.h > 0);
            assert(v.x >= 0 && v.y >= 0);
            assert(v.x + v.w <= size.first + 0.01f && v.y + v.h <= size.second + 0.01f);
            assert(std::abs(v.w / v.h - aspect) < 0.00001f);
            assert(std::isfinite(Perspective(0.785f, v.w / v.h, 24, 3072).m[0]));
        }
    }
}

int main() {
    outdoorRuns();
    indoorDoorsAndScraps();
    longIndoorSideWall();
    twoRowDoorframes();
    ledgeAndCapacity();
    townGroundFidelity();
    intrinsicGeometryLevels();
    transitionsAndBindings();
    movementAndOcclusion();
    offscreenOamVisibility();
    pr210CuratedTileShapes();
    nativeJumpEdgesAndScenery();
    indoorNativeUnderlay();
    fullNativeNorthWall();
    nativeBridgeDepthAndIndoorLayering();
    festivalCutoutsAndBridgeForeground();
    aspects();
    std::cout << "voxel scene regression tour passed (BuildMap, room transitions, movement, occlusion, aspects)\n";
}
